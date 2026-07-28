"""Domain services for finances — pure logic, no FastAPI dependency.

The functions take the AsyncSession and plain parameters (never via Depends),
which keeps them reusable from tests and from any caller with no framework
around it.

Every message these functions raise or return reaches a human — a parse error
shows up as `error_lines[].reason` on the import review screen — so all of them
are resolved from the i18n catalog, never written here.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from caramello_api.finances.models import Movement
from caramello_api.i18n import translate


@dataclass
class ParsedRow:
    """One parsed row of a bank statement file."""

    date: datetime
    amount: Decimal
    description: str
    fitid: str | None = None  # OFX FITID — used directly as the hash


def _normalize_description(desc: str) -> str:
    """Conservative normalization of a description.

    strip().lower() plus collapsing runs of whitespace (tabs, newlines).
    Digits and punctuation are deliberately kept — this stays simple.
    """
    return re.sub(r"\s+", " ", desc.strip().lower())


def _compute_hash(account_id: int, row: ParsedRow) -> str:
    """Compute the deterministic SHA-256 used for deduplication.

    OFX with a FITID -> hash = sha256("fitid:{fitid}")
    CSV/XLSX without one -> sha256("{account_id}|{date}|{amount}|{desc_norm}")
    """
    if row.fitid:
        raw = f"fitid:{row.fitid}"
    else:
        norm_desc = _normalize_description(row.description)
        raw = f"{account_id}|{row.date.date().isoformat()}|{row.amount}|{norm_desc}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _parse_date(value: str, line: int) -> datetime:
    """Try to parse a date as ISO 8601, then in the BR format.

    Raises ValueError carrying the line number when no format matches.
    """
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):  # ISO first, BR as the fallback
        try:
            return datetime.strptime(value.strip(), fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    raise ValueError(translate("finances.parse_invalid_date", line=line, value=value))


def _parse_csv(content: bytes) -> list[ParsedRow]:
    """Parse CSV statement content; returns only the valid rows.

    Auto-detects the separator (;/,) with csv.Sniffer, comma as the fallback.
    Headers are case-insensitive and read by name, not by position.
    Invalid rows are dropped silently through this public interface — use
    _parse_csv_with_errors to get error_lines. Raises ValueError once >50% of
    the rows fail.
    """
    rows, _ = _parse_csv_with_errors(content)
    return rows


def _parse_csv_with_errors(
    content: bytes,
) -> tuple[list[ParsedRow], list[dict[str, Any]]]:
    """Parse CSV content, returning (rows, error_lines).

    Auto-detects the separator (;/,) with csv.Sniffer, comma as the fallback.
    Headers are case-insensitive and read by name, not by position.
    An invalid row goes to error_lines[] without aborting the batch; raises
    ValueError once >50% of the rows fail.
    """
    text = content.decode("utf-8", errors="replace")
    sniffer = csv.Sniffer()
    try:
        dialect = sniffer.sniff(text[:1024])  # auto-detect ; or ,
    except csv.Error:
        dialect = csv.excel  # fall back to comma

    reader = csv.DictReader(io.StringIO(text), dialect=dialect)

    rows: list[ParsedRow] = []
    error_lines: list[dict[str, Any]] = []

    total_data_rows = 0
    for i, row in enumerate(reader, start=2):  # line 2 = first data line
        total_data_rows += 1
        # Normalize the headers to lowercase
        norm = {k.strip().lower(): v for k, v in row.items() if k is not None}

        # Validate and parse the date
        date_str = norm.get("date", "").strip()
        try:
            date_val = _parse_date(date_str, line=i)
        except ValueError as e:
            error_lines.append({"line_number": i, "reason": str(e)})
            continue

        # Validate and parse the amount — never a float
        amount_str = norm.get("amount", "").strip()
        try:
            amount_val = Decimal(str(amount_str))
        except (InvalidOperation, ValueError):
            error_lines.append(
                {
                    "line_number": i,
                    "reason": translate("finances.parse_invalid_amount", value=amount_str),
                }
            )
            continue

        description = norm.get("description", "").strip()
        rows.append(
            ParsedRow(
                date=date_val,
                amount=amount_val,
                description=description,
                fitid=None,
            )
        )

    # Abort once >=50% of the rows fail (inclusive — matches the message)
    if total_data_rows > 0 and len(error_lines) / total_data_rows >= 0.5:
        raise ValueError(
            translate(
                "finances.parse_too_many_errors",
                failed=len(error_lines),
                total=total_data_rows,
            )
        )

    return rows, error_lines


def _parse_ofx(content: bytes) -> list[ParsedRow]:
    """Parse OFX statement content; returns only the valid rows.

    Uses transaction.id (FITID) as the ParsedRow's fitid.
    Falls back to an iso-8859-1 decode, for BR banks with a non-standard
        encoding.
    """
    rows, _ = _parse_ofx_with_errors(content)
    return rows


def _parse_ofx_with_errors(
    content: bytes,
) -> tuple[list[ParsedRow], list[dict[str, Any]]]:
    """Parse OFX content, returning (rows, error_lines).

    Uses transaction.id (FITID) as the ParsedRow's fitid.
    Falls back to an iso-8859-1 decode, for BR banks with a non-standard
        encoding.
    """
    from ofxparse import OfxParser  # lazy import

    error_lines: list[dict[str, Any]] = []

    try:
        ofx = OfxParser.parse(io.BytesIO(content))
    except Exception:
        # Fall back to ISO-8859-1 (BR banks with a non-standard encoding)
        text = content.decode("iso-8859-1", errors="replace")
        ofx = OfxParser.parse(io.StringIO(text))

    rows: list[ParsedRow] = []
    try:
        transactions = ofx.account.statement.transactions
    except AttributeError:
        return rows, error_lines

    for i, txn in enumerate(transactions, start=1):
        try:
            date_val = txn.date
            if date_val is None:
                raise ValueError(translate("finances.parse_transaction_missing_date", index=i))
            if not isinstance(date_val, datetime):
                # ofxparse may hand back a date or a datetime
                date_val = datetime(
                    date_val.year,
                    date_val.month,
                    date_val.day,
                    tzinfo=UTC,
                )
            elif date_val.tzinfo is None:
                date_val = date_val.replace(tzinfo=UTC)

            amount_val = Decimal(str(txn.amount))  # P1: never a float
            description = str(txn.memo or txn.payee or "").strip()
            fitid = str(txn.id) if txn.id else None

            rows.append(
                ParsedRow(
                    date=date_val,
                    amount=amount_val,
                    description=description,
                    fitid=fitid,
                )
            )
        except Exception as e:
            error_lines.append({"line_number": i, "reason": str(e)})

    return rows, error_lines


def _parse_xlsx(content: bytes) -> list[ParsedRow]:
    """Parse XLSX statement content; returns only the valid rows.

    read_only=True for memory efficiency; wb.close() in a finally is MANDATORY.
    Headers are case-insensitive and read by name, not by position.
    """
    rows, _ = _parse_xlsx_with_errors(content)
    return rows


def _parse_xlsx_with_errors(
    content: bytes,
) -> tuple[list[ParsedRow], list[dict[str, Any]]]:
    """Parse XLSX content, returning (rows, error_lines).

    read_only=True for memory efficiency; wb.close() in a finally is MANDATORY.
    Headers are case-insensitive and read by name, not by position.
    """
    import openpyxl  # lazy import

    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True)
    rows: list[ParsedRow] = []
    error_lines: list[dict[str, Any]] = []

    try:
        ws = wb.active
        rows_iter = iter(ws.rows)
        header_row = next(rows_iter, None)
        if header_row is None:
            return rows, error_lines

        # Normalize the headers to lowercase
        headers = [str(c.value or "").strip().lower() for c in header_row]

        # Map the indexes of the mandatory columns
        try:
            date_idx = headers.index("date")
            amount_idx = headers.index("amount")
            desc_idx = headers.index("description")
        except ValueError as e:
            raise ValueError(translate("finances.parse_missing_column", detail=e)) from e

        for i, row in enumerate(rows_iter, start=2):
            cells = [c.value for c in row]

            # Make sure the row has enough cells
            if len(cells) <= max(date_idx, amount_idx, desc_idx):
                error_lines.append(
                    {
                        "line_number": i,
                        "reason": translate("finances.parse_insufficient_columns"),
                    }
                )
                continue

            date_raw = cells[date_idx]
            amount_raw = cells[amount_idx]
            desc_raw = cells[desc_idx]

            # Parse the date
            try:
                if isinstance(date_raw, datetime):
                    date_val = date_raw if date_raw.tzinfo else date_raw.replace(tzinfo=UTC)
                elif date_raw is not None:
                    date_val = _parse_date(str(date_raw), line=i)
                else:
                    raise ValueError(translate("finances.parse_missing_date", line=i))
            except ValueError as e:
                error_lines.append({"line_number": i, "reason": str(e)})
                continue

            # Parse the amount — never a float
            try:
                amount_val = Decimal(str(amount_raw))
            except (InvalidOperation, ValueError, TypeError):
                error_lines.append(
                    {
                        "line_number": i,
                        "reason": translate("finances.parse_invalid_amount", value=amount_raw),
                    }
                )
                continue

            description = str(desc_raw or "").strip()
            rows.append(
                ParsedRow(
                    date=date_val,
                    amount=amount_val,
                    description=description,
                    fitid=None,
                )
            )
    finally:
        wb.close()  # P5: MANDATORY in read_only mode

    return rows, error_lines


async def suggest_category(
    movement_uuid: UUID,
    family_id: int,
    session: AsyncSession,
) -> list[dict]:
    """Top-5 subcategory suggestions, by similarity.

    Compares the target movement's description against the descriptions of the
    same family's earlier entries, through rapidfuzz.fuzz.token_set_ratio.
    No minimum threshold — returns the top-5 of whatever exists.
    Returns [] when the movement does not exist or there is no entry history.
    Deliberately not run through run_in_executor: the volume is tiny (1-5 users
    per family) and the overhead would not pay for the complexity (Open
    Question 2 of the RESEARCH).
    """
    from rapidfuzz import fuzz

    from caramello_api.finances.models import (
        Account,
        Category,
        FinancialEntry,
        Subcategory,
    )

    # 1. Look the target Movement up by UUID
    result = await session.execute(select(Movement).where(Movement.uuid == movement_uuid))
    row = result.fetchone()
    if row is None:
        return []
    target_desc = row[0].description

    # 2. Read the family history: description + subcategory_id/uuid/name +
    #    category_uuid/name, through the JOIN chain
    #    FinancialEntry -> Subcategory -> Category -> Movement -> Account
    stmt = (
        select(
            Movement.description,
            Subcategory.id.label("subcategory_id"),
            Subcategory.uuid.label("subcategory_uuid"),
            Subcategory.name.label("subcategory_name"),
            Category.uuid.label("category_uuid"),
            Category.name.label("category_name"),
        )
        .join(FinancialEntry, FinancialEntry.movement_id == Movement.id)
        .join(Subcategory, FinancialEntry.subcategory_id == Subcategory.id)
        .join(Category, Subcategory.category_id == Category.id)
        .join(Account, Movement.account_id == Account.id)
        .where(Account.family_id == family_id)
    )
    entries_result = await session.execute(stmt)
    entries = entries_result.fetchall()

    if not entries:
        return []  # no history -> empty list, not an error

    # 3. Score per subcategory — keeps the highest score per subcategory_id.
    #    token_set_ratio returns a float; the public contract is an int,
    #    hence the cast.
    scored: dict[int, dict] = {}
    for entry in entries:
        score = int(fuzz.token_set_ratio(target_desc, entry[0]))
        sub_id = entry[1]
        if sub_id not in scored or score > scored[sub_id]["score"]:
            scored[sub_id] = {
                "subcategory_uuid": entry[2],
                "subcategory_name": entry[3],
                "category_uuid": entry[4],
                "category_name": entry[5],
                "score": score,
            }

    # 4. Sort by score descending, return the top-5 (no threshold)
    top5 = sorted(scored.values(), key=lambda x: x["score"], reverse=True)[:5]
    return top5


async def account_balance(account_id: int, session: AsyncSession) -> Decimal:
    """The account balance, as SUM(movement.amount).

    Returns Decimal('0.00') when there is no movement (an empty
    SUM is NULL).
    """
    from sqlalchemy import func

    result = await session.execute(
        select(func.sum(Movement.amount)).where(Movement.account_id == account_id)
    )
    total = result.scalar_one_or_none()
    if total is None:
        return Decimal("0.00")
    # Guarantees a Decimal whatever type the driver returned
    return Decimal(str(total))


async def family_balance(family_id: int, session: AsyncSession) -> Decimal:
    """The consolidated balance of every active family account.

    Iterates over the active accounts and sums their account_balance().
    Returns Decimal('0.00') when there is no active account.
    """
    from caramello_api.finances.models import Account

    accounts_result = await session.execute(
        select(Account).where(Account.family_id == family_id, Account.is_active == True)  # noqa: E712
    )
    accounts = accounts_result.scalars().all()
    total = Decimal("0.00")
    for account in accounts:
        total += await account_balance(account.id, session)
    return total


async def monthly_breakdown(
    family_id: int,
    year: int,
    month: int,
    session: AsyncSession,
    member_uuid: UUID | None = None,
) -> list[dict]:
    """Monthly breakdown by subcategory.

    Grouped by accrual period (competencia), NOT by the movement date. Returns a
    flat list with one total per subcategory for the requested period.
    The optional member_uuid filters by responsible_user_uuid.
    Uses func.sum + group_by.
    """
    from sqlalchemy import func

    from caramello_api.finances.models import (
        Account,
        Category,
        FinancialEntry,
        Subcategory,
    )
    from caramello_api.users.models import User

    stmt = (
        select(
            Category.uuid.label("category_uuid"),
            Category.name.label("category_name"),
            Subcategory.uuid.label("subcategory_uuid"),
            Subcategory.name.label("subcategory_name"),
            func.sum(Movement.amount).label("total"),
            func.count(FinancialEntry.id).label("count"),
        )
        .join(Subcategory, FinancialEntry.subcategory_id == Subcategory.id)
        .join(Category, Subcategory.category_id == Category.id)
        .join(Movement, FinancialEntry.movement_id == Movement.id)
        .join(Account, Movement.account_id == Account.id)
        .where(
            Account.family_id == family_id,
            FinancialEntry.competencia_year == year,
            FinancialEntry.competencia_month == month,
        )
        .group_by(
            Category.id,
            Category.uuid,
            Category.name,
            Subcategory.id,
            Subcategory.uuid,
            Subcategory.name,
        )
    )

    # Optional per-member filter.
    # `.scalars()` unwraps the Row — a single-entity select hands back the
    # entity itself.
    if member_uuid is not None:
        user_result = await session.execute(select(User).where(User.uuid == member_uuid))
        user = user_result.scalars().first()
        if user is not None:
            stmt = stmt.where(FinancialEntry.responsible_user_id == user.id)

    result = await session.execute(stmt)
    rows = result.fetchall()
    return [
        {
            "category_uuid": row.category_uuid,
            "category_name": row.category_name,
            "subcategory_uuid": row.subcategory_uuid,
            "subcategory_name": row.subcategory_name,
            "total": row.total if row.total is not None else Decimal("0.00"),
            "count": row.count,
        }
        for row in rows
    ]


async def by_member_breakdown(
    family_id: int,
    year: int,
    month: int,
    session: AsyncSession,
) -> list[dict]:
    """Breakdown by responsible member for one accrual period.

    Entries with no responsible_user_id are grouped into a row with
    user_uuid=None and the catalog's "unassigned" label — they are never dropped
    from the totals.
    Uses func.sum + group_by.
    """
    from sqlalchemy import func

    from caramello_api.finances.models import (
        Account,
        FinancialEntry,
    )
    from caramello_api.users.models import User

    stmt = (
        select(
            User.uuid.label("user_uuid"),
            User.name.label("name"),
            func.sum(Movement.amount).label("total"),
            func.count(FinancialEntry.id).label("count"),
        )
        # Explicit FROM clause, to avoid a ProgrammingError
        .select_from(FinancialEntry)
        .outerjoin(User, FinancialEntry.responsible_user_id == User.id)
        .join(Movement, FinancialEntry.movement_id == Movement.id)
        .join(Account, Movement.account_id == Account.id)
        .where(
            Account.family_id == family_id,
            FinancialEntry.competencia_year == year,
            FinancialEntry.competencia_month == month,
        )
        .group_by(
            User.id,
            User.uuid,
            User.name,
        )
    )
    result = await session.execute(stmt)
    rows = result.fetchall()
    return [
        {
            "user_uuid": row.user_uuid,
            "name": (row.name if row.name is not None else translate("finances.unassigned_member")),
            "total": row.total if row.total is not None else Decimal("0.00"),
            "count": row.count,
        }
        for row in rows
    ]


async def import_movements(
    content: bytes,
    format: str,  # "csv" | "ofx" | "xlsx"
    account_id: int,
    session: AsyncSession,
) -> dict[str, Any]:
    """Parse a statement file, deduplicate it and persist the movements.

    Returns a dict shaped as: inserted, duplicates_skipped,
    potential_duplicates[], error_lines[], movements[].

    Deduplication:
    - OFX (rows with a fitid): known hash -> duplicates_skipped, no insert
    - CSV/XLSX (rows without one): known hash -> potential_duplicates[], no
      insert
    - One batched pre-check query
    - on_conflict_do_nothing as the safety net against races
    """
    # Dispatch per format, using the variants that report error_lines
    if format == "csv":
        rows, error_lines = _parse_csv_with_errors(content)
    elif format == "ofx":
        rows, error_lines = _parse_ofx_with_errors(content)
    elif format == "xlsx":
        rows, error_lines = _parse_xlsx_with_errors(content)
    else:
        raise ValueError(translate("finances.unsupported_import_format", format=format))

    if not rows:
        return {
            "inserted": 0,
            "duplicates_skipped": 0,
            "potential_duplicates": [],
            "error_lines": error_lines,
            "movements": [],
        }

    # Hash every row
    hash_map: dict[str, ParsedRow] = {}
    for row in rows:
        h = _compute_hash(account_id, row)
        hash_map[h] = row

    all_hashes = list(hash_map.keys())

    # Batched pre-check, one query
    result = await session.execute(
        select(Movement.import_hash).where(Movement.import_hash.in_(all_hashes))
    )
    existing_hashes: set[str] = {row[0] for row in result.fetchall()}

    # Split the rows by outcome
    to_insert: list[tuple[str, ParsedRow]] = []
    duplicates_skipped = 0
    csv_xlsx_existing: list[str] = []

    for h, row in hash_map.items():
        if h in existing_hashes:
            if row.fitid:
                # OFX: a definitive duplicate — do not insert, do not ask
                duplicates_skipped += 1
            else:
                # CSV/XLSX: a suspected duplicate — hand it back for confirmation
                csv_xlsx_existing.append(h)
        else:
            to_insert.append((h, row))

    # Resolve the UUIDs of the suspected duplicates
    potential_duplicates: list[dict[str, Any]] = []
    if csv_xlsx_existing:
        uuid_result = await session.execute(
            select(Movement.import_hash, Movement.uuid).where(
                Movement.import_hash.in_(csv_xlsx_existing)
            )
        )
        hash_to_uuid = {row[0]: str(row[1]) for row in uuid_result.fetchall()}

        for h in csv_xlsx_existing:
            row = hash_map[h]
            potential_duplicates.append(
                {
                    "new_row": {
                        "date": row.date.date().isoformat(),
                        "amount": str(row.amount),
                        "description": row.description,
                    },
                    "existing_movement_uuid": hash_to_uuid.get(h),
                    "hash": h,
                }
            )

    # Insert the non-duplicate rows with pg_insert + on_conflict_do_nothing
    # (the P4 safety net)
    inserted_movements: list[dict[str, Any]] = []
    if to_insert:
        from uuid import uuid4

        values = []
        for h, row in to_insert:
            now = datetime.now(UTC)
            values.append(
                {
                    "uuid": uuid4(),
                    "account_id": account_id,
                    "date": row.date,
                    "amount": row.amount,
                    "description": row.description,
                    "import_hash": h,
                    "created_at": now,
                    "updated_at": now,
                }
            )

        stmt = (
            pg_insert(Movement.__table__)  # type: ignore[arg-type]  # see shared/auth.py
            .values(values)
            .on_conflict_do_nothing(index_elements=["import_hash"])
        )
        await session.execute(stmt)
        await session.commit()

        # Read the inserted movements back to populate movements[]
        inserted_hashes = [v["import_hash"] for v in values]
        movements_result = await session.execute(
            select(Movement).where(Movement.import_hash.in_(inserted_hashes))
        )
        fetched = movements_result.scalars().all()
        # A gap between what was sent and what came back means a race:
        # on_conflict_do_nothing silently dropped rows a concurrent call had
        # already inserted.
        race_condition_skipped = len(values) - len(fetched)
        if race_condition_skipped > 0:
            duplicates_skipped += race_condition_skipped
        for mvt in fetched:
            inserted_movements.append(
                {
                    "uuid": str(mvt.uuid),
                    "date": mvt.date.isoformat(),
                    "amount": str(mvt.amount),
                    "description": mvt.description,
                    "created_at": mvt.created_at.isoformat(),
                    # Report updated_at, so the response is faithful
                    "updated_at": mvt.updated_at.isoformat(),
                }
            )

    return {
        "inserted": len(inserted_movements),
        "duplicates_skipped": duplicates_skipped,
        "potential_duplicates": potential_duplicates,
        "error_lines": error_lines,
        "movements": inserted_movements,
    }

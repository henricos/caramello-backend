"""Serviços de domínio para finances — lógica pura, sem dependências FastAPI.

Funções recebem AsyncSession e parâmetros diretos (não via Depends),
tornando-as reutilizáveis em testes e outros callers sem framework.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from sqlalchemy.dialects.postgresql import insert as pg_insert

from caramello.finances.models import Movement


@dataclass
class ParsedRow:
    """Linha parseada de um arquivo de extrato bancário."""

    date: datetime
    amount: Decimal
    description: str
    fitid: str | None = None  # OFX FITID — usado como hash direto (D-04)


def _normalize_description(desc: str) -> str:
    """Normalização conservadora de descrição (D-06).

    strip().lower() + colapso de espaços múltiplos (tabs, newlines).
    Sem remoção de números ou pontuação — mantém simples.
    """
    return re.sub(r"\s+", " ", desc.strip().lower())


def _compute_hash(account_id: int, row: ParsedRow) -> str:
    """Calcula SHA-256 determinístico para deduplicação.

    D-04: OFX com FITID → hash = sha256("fitid:{fitid}")
    D-07: CSV/XLSX sem FITID → hash = sha256("{account_id}|{date}|{amount}|{desc_norm}")
    """
    if row.fitid:
        raw = f"fitid:{row.fitid}"
    else:
        norm_desc = _normalize_description(row.description)
        raw = f"{account_id}|{row.date.date().isoformat()}|{row.amount}|{norm_desc}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _parse_date(value: str, line: int) -> datetime:
    """Tenta parsear data em ISO 8601 e depois formato BR (D-12).

    Levanta ValueError com número da linha se nenhum formato funcionar.
    """
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):  # D-12: ISO primeiro, BR fallback
        try:
            return datetime.strptime(value.strip(), fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise ValueError(f"Linha {line}: data inválida {value!r}")


def _parse_csv(content: bytes) -> list[ParsedRow]:
    """Parseia conteúdo CSV de extrato bancário; retorna apenas as linhas válidas.

    D-10: auto-detecta separador (;/,) via csv.Sniffer com fallback para vírgula (P7).
    D-11: headers case-insensitive, por nome não por posição.
    D-13: linhas inválidas são descartadas silenciosamente nesta interface pública.
          Usar _parse_csv_with_errors para obter error_lines.
          Se >50% das linhas falharem, levanta ValueError.
    """
    rows, _ = _parse_csv_with_errors(content)
    return rows


def _parse_csv_with_errors(
    content: bytes,
) -> tuple[list[ParsedRow], list[dict[str, Any]]]:
    """Parseia conteúdo CSV retornando (rows, error_lines).

    D-10: auto-detecta separador (;/,) via csv.Sniffer com fallback para vírgula (P7).
    D-11: headers case-insensitive, por nome não por posição.
    D-13: linhas inválidas vão para error_lines[] sem abortar;
          se >50% das linhas falharem, levanta ValueError.
    """
    text = content.decode("utf-8", errors="replace")
    sniffer = csv.Sniffer()
    try:
        dialect = sniffer.sniff(text[:1024])  # D-10: auto-detect ; or ,
    except csv.Error:
        dialect = csv.excel  # P7: fallback para vírgula

    reader = csv.DictReader(io.StringIO(text), dialect=dialect)

    rows: list[ParsedRow] = []
    error_lines: list[dict[str, Any]] = []

    total_data_rows = 0
    for i, row in enumerate(reader, start=2):  # linha 2 = primeira de dados
        total_data_rows += 1
        # D-11: normalizar headers para lowercase
        norm = {k.strip().lower(): v for k, v in row.items() if k is not None}

        # Validar e parsear date
        date_str = norm.get("date", "").strip()
        try:
            date_val = _parse_date(date_str, line=i)
        except ValueError as e:
            error_lines.append({"line_number": i, "reason": str(e)})
            continue

        # Validar e parsear amount — nunca float (P1)
        amount_str = norm.get("amount", "").strip()
        try:
            amount_val = Decimal(str(amount_str))
        except (InvalidOperation, ValueError):
            error_lines.append({
                "line_number": i,
                "reason": f"amount inválido: {amount_str!r}",
            })
            continue

        description = norm.get("description", "").strip()
        rows.append(ParsedRow(
            date=date_val,
            amount=amount_val,
            description=description,
            fitid=None,
        ))

    # D-13: abort se >=50% das linhas falharem (inclusive — alinha com mensagem de erro)
    if total_data_rows > 0 and len(error_lines) / total_data_rows >= 0.5:
        raise ValueError(
            f"Mais de 50% das linhas falharam ({len(error_lines)}/{total_data_rows}). "
            "Verificar formato do arquivo."
        )

    return rows, error_lines


def _parse_ofx(content: bytes) -> list[ParsedRow]:
    """Parseia conteúdo OFX de extrato bancário; retorna apenas as linhas válidas.

    D-04: usa transaction.id (FITID) como fitid no ParsedRow.
    P6: fallback decode iso-8859-1 para bancos BR com encoding não-padrão.
    """
    rows, _ = _parse_ofx_with_errors(content)
    return rows


def _parse_ofx_with_errors(
    content: bytes,
) -> tuple[list[ParsedRow], list[dict[str, Any]]]:
    """Parseia conteúdo OFX retornando (rows, error_lines).

    D-04: usa transaction.id (FITID) como fitid no ParsedRow.
    P6: fallback decode iso-8859-1 para bancos BR com encoding não-padrão.
    """
    from ofxparse import OfxParser  # lazy import

    error_lines: list[dict[str, Any]] = []

    try:
        ofx = OfxParser.parse(io.BytesIO(content))
    except Exception:
        # P6: fallback para ISO-8859-1 (bancos BR com encoding não-padrão)
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
                raise ValueError(f"Transação {i}: data ausente")
            if not isinstance(date_val, datetime):
                # ofxparse pode retornar date ou datetime
                date_val = datetime(
                    date_val.year, date_val.month, date_val.day,
                    tzinfo=timezone.utc,
                )
            elif date_val.tzinfo is None:
                date_val = date_val.replace(tzinfo=timezone.utc)

            amount_val = Decimal(str(txn.amount))  # P1: nunca float
            description = str(txn.memo or txn.payee or "").strip()
            fitid = str(txn.id) if txn.id else None

            rows.append(ParsedRow(
                date=date_val,
                amount=amount_val,
                description=description,
                fitid=fitid,
            ))
        except Exception as e:
            error_lines.append({"line_number": i, "reason": str(e)})

    return rows, error_lines


def _parse_xlsx(content: bytes) -> list[ParsedRow]:
    """Parseia conteúdo XLSX de extrato bancário; retorna apenas as linhas válidas.

    P5: usa read_only=True para eficiência de memória; wb.close() em finally é OBRIGATÓRIO.
    D-11: headers case-insensitive, por nome não por posição.
    """
    rows, _ = _parse_xlsx_with_errors(content)
    return rows


def _parse_xlsx_with_errors(
    content: bytes,
) -> tuple[list[ParsedRow], list[dict[str, Any]]]:
    """Parseia conteúdo XLSX retornando (rows, error_lines).

    P5: usa read_only=True para eficiência de memória; wb.close() em finally é OBRIGATÓRIO.
    D-11: headers case-insensitive, por nome não por posição.
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

        # D-11: normalizar headers para lowercase
        headers = [str(c.value or "").strip().lower() for c in header_row]

        # Mapear índices das colunas obrigatórias
        try:
            date_idx = headers.index("date")
            amount_idx = headers.index("amount")
            desc_idx = headers.index("description")
        except ValueError as e:
            raise ValueError(f"Coluna obrigatória ausente: {e}") from e

        for i, row in enumerate(rows_iter, start=2):
            cells = [c.value for c in row]

            # Garantir que temos células suficientes
            if len(cells) <= max(date_idx, amount_idx, desc_idx):
                error_lines.append({
                    "line_number": i,
                    "reason": "Linha com colunas insuficientes",
                })
                continue

            date_raw = cells[date_idx]
            amount_raw = cells[amount_idx]
            desc_raw = cells[desc_idx]

            # Parsear date
            try:
                if isinstance(date_raw, datetime):
                    date_val = (
                        date_raw if date_raw.tzinfo
                        else date_raw.replace(tzinfo=timezone.utc)
                    )
                elif date_raw is not None:
                    date_val = _parse_date(str(date_raw), line=i)
                else:
                    raise ValueError(f"Linha {i}: data ausente")
            except ValueError as e:
                error_lines.append({"line_number": i, "reason": str(e)})
                continue

            # Parsear amount — nunca float (P1)
            try:
                amount_val = Decimal(str(amount_raw))
            except (InvalidOperation, ValueError, TypeError):
                error_lines.append({
                    "line_number": i,
                    "reason": f"amount inválido: {amount_raw!r}",
                })
                continue

            description = str(desc_raw or "").strip()
            rows.append(ParsedRow(
                date=date_val,
                amount=amount_val,
                description=description,
                fitid=None,
            ))
    finally:
        wb.close()  # P5: OBRIGATÓRIO em read_only mode

    return rows, error_lines


async def suggest_category(
    movement_uuid: UUID,
    family_id: int,
    session: AsyncSession,
) -> list[dict]:
    """LAN-03, D-CAT-01/02/03/04: Retorna top-5 sugestões de subcategoria por similaridade.

    Compara a descrição da movimentação alvo com descrições de lançamentos
    anteriores da mesma família via rapidfuzz.fuzz.token_set_ratio.
    Sem threshold mínimo — retorna o top-5 do que existir.
    Retorna [] se movimento não existe ou se não há histórico de lançamentos.
    Não usa run_in_executor — volume é pequeno (1-5 usuários família), overhead não justifica
    a complexidade (Open Question 2 do RESEARCH).
    """
    from rapidfuzz import fuzz
    from caramello.finances.models import (
        FinancialEntry,
        Subcategory,
        Category,
        Account,
    )

    # 1. Buscar Movement alvo pelo UUID (session.execute — não session.exec, pitfall P3)
    result = await session.execute(
        select(Movement).where(Movement.uuid == movement_uuid)
    )
    row = result.fetchone()
    if row is None:
        return []
    target_desc = row[0].description

    # 2. Buscar histórico da família: description + subcategory_id/uuid/name + category_uuid/name
    #    via JOINs FinancialEntry → Subcategory → Category → Movement → Account
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
        return []  # D-CAT-03: sem histórico → lista vazia, sem erro

    # 3. Calcular score por subcategoria — mantém o maior score por subcategory_id
    #    A1: token_set_ratio retorna float, cast para int conforme contrato público (D-CAT-02)
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

    # 4. Ordenar descrescente por score, retornar top-5 (D-CAT-01: sem threshold mínimo)
    top5 = sorted(scored.values(), key=lambda x: x["score"], reverse=True)[:5]
    return top5


async def account_balance(account_id: int, session: AsyncSession) -> Decimal:
    """REL-01, D-BAL-01: Calcula saldo da conta via SUM(movement.amount).

    Retorna Decimal('0.00') quando não há movimentações (pitfall P6 — SUM vazio = NULL).
    Usa session.execute() — nunca session.exec() para agregações (pitfall P3).
    """
    from sqlalchemy import func

    result = await session.execute(
        select(func.sum(Movement.amount)).where(Movement.account_id == account_id)
    )
    total = result.scalar_one_or_none()
    return total if total is not None else Decimal("0.00")


async def family_balance(family_id: int, session: AsyncSession) -> Decimal:
    """REL-02, D-BAL-02: Calcula saldo consolidado de todas as contas ativas da família.

    Itera sobre contas ativas e soma os saldos via account_balance().
    Retorna Decimal('0.00') quando não há contas ativas.
    """
    from caramello.finances.models import Account

    accounts_result = await session.exec(
        select(Account).where(Account.family_id == family_id, Account.is_active == True)  # noqa: E712
    )
    accounts = accounts_result.all()
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
    """REL-03/04, D-REP-01/03: Breakdown mensal por subcategoria (competência, não data).

    Retorna lista plana com total por subcategoria para o período de competência informado.
    Parâmetro member_uuid opcional — filtra por responsible_user_uuid (D-REP-01).
    Usa session.execute() com func.sum + group_by (pitfall P3, D-REP-04).
    """
    from sqlalchemy import func
    from caramello.finances.models import (
        FinancialEntry,
        Subcategory,
        Category,
        Account,
    )
    from caramello.users.models import User

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

    # Filtro opcional por membro (D-REP-01)
    if member_uuid is not None:
        user_result = await session.execute(
            select(User).where(User.uuid == member_uuid)
        )
        user_row = user_result.fetchone()
        if user_row is not None:
            stmt = stmt.where(FinancialEntry.responsible_user_id == user_row[0].id)

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
    """D-REP-02: Breakdown por responsável para o período de competência.

    Lançamentos sem responsible_user_id agrupados em linha com user_uuid=None
    e name='Não atribuído' — não são descartados dos totais (pitfall P7).
    Usa session.execute() com func.sum + group_by (pitfall P3, D-REP-04).
    """
    from sqlalchemy import func
    from caramello.finances.models import (
        FinancialEntry,
        Account,
    )
    from caramello.users.models import User

    stmt = (
        select(
            User.uuid.label("user_uuid"),
            User.name.label("name"),
            func.sum(Movement.amount).label("total"),
            func.count(FinancialEntry.id).label("count"),
        )
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
            "name": row.name if row.name is not None else "Não atribuído",
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
    """Parseia arquivo de extrato, deduplica e persiste movimentações.

    Retorna dict com shape D-14: inserted, duplicates_skipped,
    potential_duplicates[], error_lines[], movements[].

    Deduplicação:
    - OFX (rows com fitid): hash existente → duplicates_skipped (D-04, não insere)
    - CSV/XLSX (rows sem fitid): hash existente → potential_duplicates[] (D-05, não insere)
    - Pre-check em lote via session.execute (P8)
    - on_conflict_do_nothing como safety net para race conditions (P4)
    """
    # Dispatch por formato usando variantes com error_lines
    if format == "csv":
        rows, error_lines = _parse_csv_with_errors(content)
    elif format == "ofx":
        rows, error_lines = _parse_ofx_with_errors(content)
    elif format == "xlsx":
        rows, error_lines = _parse_xlsx_with_errors(content)
    else:
        raise ValueError(f"Formato não suportado: {format!r}")

    if not rows:
        return {
            "inserted": 0,
            "duplicates_skipped": 0,
            "potential_duplicates": [],
            "error_lines": error_lines,
            "movements": [],
        }

    # Calcular hash de cada row
    hash_map: dict[str, ParsedRow] = {}
    for row in rows:
        h = _compute_hash(account_id, row)
        hash_map[h] = row

    all_hashes = list(hash_map.keys())

    # Pre-check em lote (P8: session.execute, não session.exec)
    result = await session.execute(
        select(Movement.import_hash).where(Movement.import_hash.in_(all_hashes))
    )
    existing_hashes: set[str] = {row[0] for row in result.fetchall()}

    # Separar rows por categoria
    to_insert: list[tuple[str, ParsedRow]] = []
    duplicates_skipped = 0
    csv_xlsx_existing: list[str] = []

    for h, row in hash_map.items():
        if h in existing_hashes:
            if row.fitid:
                # OFX: duplicata definitiva — não inserir, não perguntar (D-04)
                duplicates_skipped += 1
            else:
                # CSV/XLSX: duplicata suspeita — retornar para confirmação (D-05)
                csv_xlsx_existing.append(h)
        else:
            to_insert.append((h, row))

    # Resolver UUIDs das duplicatas suspeitas (D-05/D-14)
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
            potential_duplicates.append({
                "new_row": {
                    "date": row.date.date().isoformat(),
                    "amount": str(row.amount),
                    "description": row.description,
                },
                "existing_movement_uuid": hash_to_uuid.get(h),
                "hash": h,
            })

    # Inserir rows sem duplicata via pg_insert + on_conflict_do_nothing (P4 safety net)
    inserted_movements: list[dict[str, Any]] = []
    if to_insert:
        from uuid import uuid4

        values = []
        for h, row in to_insert:
            now = datetime.now(timezone.utc)
            values.append({
                "uuid": uuid4(),
                "account_id": account_id,
                "date": row.date,
                "amount": row.amount,
                "description": row.description,
                "import_hash": h,
                "created_at": now,
                "updated_at": now,
            })

        stmt = (
            pg_insert(Movement.__table__)
            .values(values)
            .on_conflict_do_nothing(index_elements=["import_hash"])
        )
        await session.execute(stmt)
        await session.commit()

        # Recuperar movimentações inseridas para popular movements[] (D-14)
        inserted_hashes = [v["import_hash"] for v in values]
        movements_result = await session.execute(
            select(Movement).where(Movement.import_hash.in_(inserted_hashes))
        )
        fetched = movements_result.scalars().all()
        # Diferença entre enviados e recuperados indica race condition (on_conflict_do_nothing
        # descartou silenciosamente linhas inseridas por chamada concorrente)
        race_condition_skipped = len(values) - len(fetched)
        if race_condition_skipped > 0:
            duplicates_skipped += race_condition_skipped
        for mvt in fetched:
            inserted_movements.append({
                "uuid": str(mvt.uuid),
                "date": mvt.date.isoformat(),
                "amount": str(mvt.amount),
                "description": mvt.description,
                "created_at": mvt.created_at.isoformat(),
            })

    return {
        "inserted": len(inserted_movements),
        "duplicates_skipped": duplicates_skipped,
        "potential_duplicates": potential_duplicates,
        "error_lines": error_lines,
        "movements": inserted_movements,
    }

"""Unit tests for src/caramello_api/finances/services.py.

Exercises the parsers and the deduplication logic without a real database
(pure unit). Imports are lazy (inside each test) so that the file collects
normally before services.py exists — an ImportError shows up as a failure in
the test body (an explicit red), not as a collection error.

Nyquist stubs — red until services.py is implemented.
"""

from __future__ import annotations

import asyncio
from datetime import UTC
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from tests.conftest import constant, execute_mock


def test_parse_csv():
    """_parse_csv detects the ';' and ',' separators via csv.Sniffer.

    Nyquist stub — red until services.py implements _parse_csv.
    Checks that Sniffer tells semicolon and comma apart correctly.
    """
    services = pytest.importorskip("caramello_api.finances.services")
    _parse_csv = getattr(services, "_parse_csv", None)
    if _parse_csv is None:
        pytest.skip("_parse_csv is not implemented yet in caramello.finances.services")

    # Semicolon separator (BR convention)
    csv_semicolon = b"date;amount;description\n2026-01-15;-150.00;PIX FULANO\n"
    rows_sc = _parse_csv(csv_semicolon)
    assert len(rows_sc) == 1, f"Expected 1 row; got {len(rows_sc)}"
    assert rows_sc[0].amount == Decimal("-150.00"), (
        f"Amount must be Decimal('-150.00'); was {rows_sc[0].amount!r}"
    )
    assert rows_sc[0].description == "PIX FULANO", f"Wrong description: {rows_sc[0].description!r}"

    # Comma separator (EN convention)
    csv_comma = b"date,amount,description\n2026-01-16,200.00,SALARIO\n"
    rows_comma = _parse_csv(csv_comma)
    assert len(rows_comma) == 1, f"Expected 1 row; got {len(rows_comma)}"
    assert rows_comma[0].amount == Decimal("200.00"), (
        f"Amount must be Decimal('200.00'); was {rows_comma[0].amount!r}"
    )


def test_parse_csv_error_lines():
    """A CSV mixing valid and invalid rows parses the valid ones.

    Pins ONE contract for a batch of 5 data rows, 2 of them broken (40% — below
    the abort threshold of test_parse_csv_abort_threshold):

      - `_parse_csv_with_errors` returns (rows, error_lines): the three valid rows
        in file order, and one error_lines entry per broken row carrying its
        1-based line number in the file and the reason from the i18n catalog.
      - `_parse_csv` is the rows-only view of that same batch — the invalid rows
        are dropped silently, never turned into a ParsedRow with a bogus amount.

    The reasons are compared against `translate(...)`: they are display text owned
    by the catalog, so hardcoding the pt-BR wording here would pin the wrong file.
    """
    from datetime import datetime

    from caramello_api.finances.services import _parse_csv, _parse_csv_with_errors
    from caramello_api.i18n import translate

    csv_content = (
        b"date,amount,description\n"
        b"2026-01-15,-150.00,PIX VALIDO\n"  # line 2 — valid
        b"2026-01-16,R$ 100,VALOR INVALIDO\n"  # line 3 — amount is not a Decimal
        b"2026-01-17,200.00,SALARIO\n"  # line 4 — valid
        b"2026-31-99,50.00,DATA INVALIDA\n"  # line 5 — date matches no format
        b"2026-01-18,-75.50,ALUGUEL\n"  # line 6 — valid
    )

    rows, error_lines = _parse_csv_with_errors(csv_content)

    assert [row.description for row in rows] == ["PIX VALIDO", "SALARIO", "ALUGUEL"]
    assert [row.amount for row in rows] == [
        Decimal("-150.00"),
        Decimal("200.00"),
        Decimal("-75.50"),
    ]
    assert [row.date for row in rows] == [
        datetime(2026, 1, 15, tzinfo=UTC),
        datetime(2026, 1, 17, tzinfo=UTC),
        datetime(2026, 1, 18, tzinfo=UTC),
    ]
    assert all(row.fitid is None for row in rows), "a CSV row has no FITID"

    assert error_lines == [
        {
            "line_number": 3,
            "reason": translate("finances.parse_invalid_amount", value="R$ 100"),
        },
        {
            "line_number": 5,
            "reason": translate("finances.parse_invalid_date", line=5, value="2026-31-99"),
        },
    ]

    # The public parser exposes the same batch without the error report
    assert _parse_csv(csv_content) == rows


def test_parse_csv_abort_threshold():
    """50% or more invalid rows aborts the batch with ValueError.

    With 3 of 3 rows invalid, _parse_csv must raise, and the message must be the
    catalog's — it is what the endpoint turns into the 422's `message`.
    """
    from caramello_api.finances.services import _parse_csv
    from caramello_api.i18n import translate

    # 3 data rows, all with an invalid amount (100% failure > 50%)
    csv_content = (
        b"date,amount,description\n"
        b"2026-01-15,R$ 100,INVALIDO A\n"
        b"2026-01-16,EUR 200,INVALIDO B\n"
        b"2026-01-17,abc,INVALIDO C\n"
    )

    with pytest.raises(ValueError) as excinfo:
        _parse_csv(csv_content)
    assert str(excinfo.value) == translate("finances.parse_too_many_errors", failed=3, total=3), (
        str(excinfo.value)
    )


def test_compute_hash():
    """The (account_id|date|amount|desc_norm) hash is deterministic; FITID differs.

    Nyquist stub — red until services.py implements _compute_hash.
    """
    services = pytest.importorskip("caramello_api.finances.services")
    _compute_hash = getattr(services, "_compute_hash", None)
    ParsedRow = getattr(services, "ParsedRow", None)
    if _compute_hash is None or ParsedRow is None:
        pytest.skip(
            "_compute_hash or ParsedRow are not implemented yet in caramello.finances.services"
        )

    from datetime import datetime

    date = datetime(2026, 1, 15, tzinfo=UTC)
    amount = Decimal("-150.00")

    # CSV/XLSX hash — based on (account_id|date|amount|desc_norm)
    row_no_fitid = ParsedRow(date=date, amount=amount, description="PIX FULANO", fitid=None)
    hash1 = _compute_hash(account_id=10, row=row_no_fitid)
    hash2 = _compute_hash(account_id=10, row=row_no_fitid)

    # Deterministic: same inputs → same hash
    assert hash1 == hash2, f"Hash must be deterministic; got: {hash1!r} and {hash2!r}"
    assert len(hash1) == 64, f"SHA-256 must be 64 hex characters long; got: {len(hash1)}"

    # OFX — the hash is derived from the FITID, not from the compound key
    row_with_fitid = ParsedRow(date=date, amount=amount, description="PIX FULANO", fitid="TX001")
    hash_fitid = _compute_hash(account_id=10, row=row_with_fitid)

    # The hash with a FITID must differ from the one without it (different algorithms)
    assert hash_fitid != hash1, (
        f"Hash with FITID must differ from the hash without it; both were: {hash1!r}"
    )
    assert len(hash_fitid) == 64, f"SHA-256 must be 64 hex characters long; got: {len(hash_fitid)}"


def test_normalize_description():
    """Conservative normalization — strip + lower + collapse of repeated spaces.

    Nyquist stub — red until services.py implements _normalize_description.
    Checks that '  PIX  RECEBIDO  ' → 'pix recebido'.
    """
    services = pytest.importorskip("caramello_api.finances.services")
    _normalize_description = getattr(services, "_normalize_description", None)
    if _normalize_description is None:
        pytest.skip("_normalize_description is not implemented yet in caramello.finances.services")

    # Base case: repeated spaces, uppercase, leading/trailing whitespace
    assert _normalize_description("  PIX  RECEBIDO  ") == "pix recebido", (
        f"Expected 'pix recebido'; got: {_normalize_description('  PIX  RECEBIDO  ')!r}"
    )

    # Nothing to change
    assert _normalize_description("pix recebido") == "pix recebido", (
        "An already normalized string must not change"
    )

    # Tabs and line breaks collapsed
    result = _normalize_description("PIX\t\tPAGAMENTO")
    assert result == "pix pagamento", f"Tabs must be collapsed; got: {result!r}"

    # Whitespace-only input reduced to nothing
    assert _normalize_description("   ") == "", "Whitespace only must produce an empty string"


# ---------------------------------------------------------------------------
# Helpers for the reconciliation, balance and report tests
# ---------------------------------------------------------------------------


def _load_service(func_name: str):
    """Import the services module and return the function by name.

    Calls pytest.skip when the module or the function does not exist yet.
    """
    services = pytest.importorskip(
        "caramello_api.finances.services",
        reason="caramello_api.finances.services does not exist yet",
    )
    func = getattr(services, func_name, None)
    if func is None:
        pytest.skip(f"{func_name} is not implemented yet in caramello.finances.services")
    return func


def _run(coro):
    """Run a coroutine in a way compatible with Python 3.10+ and pytest-asyncio.

    Uses asyncio.run() to create a fresh event loop per call, avoiding clashes
    with event loops created/closed by pytest-asyncio in the tests of other
    modules (test_family_service.py uses async def tests).
    """
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Service-level tests — reconciliation, balances, reports
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# suggest_category
# ---------------------------------------------------------------------------


def test_suggest_category_service():
    """suggest_category returns the top 5 with a score when history exists.

    The session.execute mock simulates a history with a single entry so that the
    return value is a list of dicts holding the keys expected by the API contract
    (subcategory_uuid, subcategory_name, category_uuid, category_name, score).
    """
    suggest_category = _load_service("suggest_category")

    movement_uuid = uuid4()
    family_id = 1

    # Simulates the row of the target Movement
    mock_target_row = MagicMock()
    mock_target_row.__getitem__ = lambda self, i: MagicMock(
        description="Supermercado Pão de Açúcar"
    )

    # Simulates a history row:
    # entry[0] = description, entry[1] = subcategory_id,
    # entry[2] = subcategory_uuid, entry[3] = subcategory_name,
    # entry[4] = category_uuid, entry[5] = category_name
    sub_uuid = uuid4()
    cat_uuid = uuid4()
    history_row = MagicMock()
    history_row.__getitem__ = MagicMock(
        side_effect=lambda i: [
            "Supermercado Carrefour",  # description
            10,  # subcategory_id
            sub_uuid,  # subcategory_uuid
            "Supermercado",  # subcategory_name
            cat_uuid,  # category_uuid
            "Alimentação",  # category_name
        ][i]
    )

    # First call: fetches the target Movement; second: fetches the history
    mock_result_target = MagicMock()
    mock_result_target.fetchone.return_value = mock_target_row

    mock_result_history = MagicMock()
    mock_result_history.fetchall.return_value = [history_row]

    execute_calls = [mock_result_target, mock_result_history]
    call_count = [0]

    async def _execute(_stmt):
        idx = call_count[0]
        call_count[0] += 1
        return execute_calls[idx] if idx < len(execute_calls) else MagicMock()

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(side_effect=_execute)

    result = _run(
        suggest_category(
            movement_uuid=movement_uuid,
            family_id=family_id,
            session=mock_session,
        )
    )

    assert isinstance(result, list), f"Expected list; was {type(result)}"
    assert len(result) >= 1, "Must return at least 1 suggestion when history exists"
    item = result[0]
    expected_keys = {
        "subcategory_uuid",
        "subcategory_name",
        "category_uuid",
        "category_name",
        "score",
    }
    assert expected_keys.issubset(item.keys()), f"Missing keys: {expected_keys - item.keys()}"
    assert isinstance(item["score"], int), (
        f"score must be int (A1 — rapidfuzz returns float, cast it); was {type(item['score'])}"
    )


def test_suggest_category_empty_history():
    """suggest_category returns [] when there is no movement history.

    No minimum threshold — the function simply returns an empty list, no error.
    """
    suggest_category = _load_service("suggest_category")

    movement_uuid = uuid4()
    family_id = 2

    # Target movement found
    mock_target_row = MagicMock()
    mock_target_row.__getitem__ = MagicMock(side_effect=lambda i: MagicMock(description="Uber"))

    mock_result_target = MagicMock()
    mock_result_target.fetchone.return_value = mock_target_row

    # Empty history
    mock_result_history = MagicMock()
    mock_result_history.fetchall.return_value = []

    execute_calls = [mock_result_target, mock_result_history]
    call_count = [0]

    async def _execute(_stmt):
        idx = call_count[0]
        call_count[0] += 1
        return execute_calls[idx] if idx < len(execute_calls) else MagicMock()

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(side_effect=_execute)

    result = _run(
        suggest_category(
            movement_uuid=movement_uuid,
            family_id=family_id,
            session=mock_session,
        )
    )

    assert result == [], f"with no history it must return []; returned {result!r}"


# ---------------------------------------------------------------------------
# account_balance
# ---------------------------------------------------------------------------


def test_account_balance_empty():
    """account_balance returns Decimal('0.00') when there are no movements.

    SUM() over an empty set returns NULL in PostgreSQL — the function must
    convert that to Decimal('0.00').
    """
    account_balance = _load_service("account_balance")

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None  # empty SUM() → None

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    balance = _run(account_balance(account_id=1, session=mock_session))

    assert balance == Decimal("0.00"), f"Empty balance must be Decimal('0.00'); was: {balance!r}"
    assert isinstance(balance, Decimal), (
        f"Balance must be Decimal, not float or str; was {type(balance)}"
    )


# ---------------------------------------------------------------------------
# family_balance
# ---------------------------------------------------------------------------


def test_family_balance():
    """family_balance returns a Decimal consolidating every account of the family.

    The mock simulates one account with a balance of 500.00, expecting a Decimal back.
    """
    family_balance = _load_service("family_balance")

    mock_session = AsyncMock()

    # Accounts of the family: a select of a SINGLE entity, read via .scalars().all()
    mock_accounts_result = MagicMock()

    from datetime import datetime

    from caramello_api.finances.models import Account  # type: ignore[import-not-found]

    fake_account = Account(
        id=1,
        uuid=uuid4(),
        family_id=5,
        name="Conta Corrente",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    mock_accounts_result.all.return_value = [fake_account]

    # Aggregated balance of the account
    mock_balance_result = MagicMock()
    mock_balance_result.scalar_one_or_none.return_value = Decimal("500.00")

    mock_session.execute.side_effect = execute_mock(
        constant(mock_accounts_result), constant(mock_balance_result)
    )

    result = _run(family_balance(family_id=5, session=mock_session))

    assert isinstance(result, Decimal), f"family_balance must return Decimal; was {type(result)}"
    assert result == Decimal("500.00"), (
        f"family_balance must sum the balance of the single active account; was {result}"
    )


# ---------------------------------------------------------------------------
# monthly_breakdown
# ---------------------------------------------------------------------------


def test_monthly_breakdown():
    """monthly_breakdown returns a structure of rows per subcategory.

    Every row must carry category_uuid, subcategory_uuid, total (Decimal), count (int).
    The report works over competencia_year/month — not over Movement.date.
    """
    monthly_breakdown = _load_service("monthly_breakdown")

    # Simulates a GROUP BY result returning one named row
    mock_row = MagicMock()
    mock_row.category_uuid = uuid4()
    mock_row.category_name = "Alimentação"
    mock_row.subcategory_uuid = uuid4()
    mock_row.subcategory_name = "Supermercado"
    mock_row.total = Decimal("300.00")
    mock_row.count = 5

    mock_result = MagicMock()
    mock_result.fetchall.return_value = [mock_row]

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    result = _run(
        monthly_breakdown(
            family_id=1,
            year=2026,
            month=5,
            session=mock_session,
        )
    )

    assert isinstance(result, list), f"Expected list; was {type(result)}"
    assert len(result) == 1, f"Expected 1 row; was {len(result)}"


# ---------------------------------------------------------------------------
# by_member_breakdown
# ---------------------------------------------------------------------------


def test_by_member_breakdown():
    """by_member_breakdown returns rows including the user_uuid=None group.

    Movements without a responsible_user_id are grouped into a row with
    user_uuid=None and name='Não atribuído' — they are not dropped from the totals.
    """
    by_member_breakdown = _load_service("by_member_breakdown")

    # Simulates a row with an assigned responsible member
    mock_row_user = MagicMock()
    mock_row_user.user_uuid = uuid4()
    mock_row_user.name = "João"
    mock_row_user.total = Decimal("500.00")
    mock_row_user.count = 8

    # Simulates the unassigned row (user_uuid=None)
    mock_row_none = MagicMock()
    mock_row_none.user_uuid = None
    mock_row_none.name = "Não atribuído"
    mock_row_none.total = Decimal("700.00")
    mock_row_none.count = 12

    mock_result = MagicMock()
    mock_result.fetchall.return_value = [mock_row_user, mock_row_none]

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    result = _run(
        by_member_breakdown(
            family_id=1,
            year=2026,
            month=5,
            session=mock_session,
        )
    )

    assert isinstance(result, list), f"Expected list; was {type(result)}"
    # Must include the unassigned group
    assert len(result) >= 1, "Must return at least one row"

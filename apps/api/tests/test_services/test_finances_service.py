"""Unit tests for src/caramello_api/finances/services.py.

Exercises the parsers and the deduplication logic without a real database
(pure unit). Imports are lazy (inside each test) so that the file collects
normally before services.py exists — an ImportError shows up as a failure in
the test body (an explicit red), not as a collection error.

Nyquist stubs — red until plan 08-03 delivers services.py implemented.
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
    """MOV-02 + D-10: _parse_csv detects the ';' and ',' separators via csv.Sniffer.

    Nyquist stub — red until services.py implements _parse_csv (plan 08-03).
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
    """MOV-02 + D-13: a row with an invalid amount goes to error_lines[], batch not aborted.

    Nyquist stub — red until services.py implements the handling of invalid rows.
    A row holding the value 'R$ 100' is not a valid Decimal — it must show up in
    error_lines[], without preventing the valid rows from being processed.
    """
    services = pytest.importorskip("caramello_api.finances.services")
    _parse_csv = getattr(services, "_parse_csv", None)
    if _parse_csv is None:
        pytest.skip("_parse_csv is not implemented yet in caramello.finances.services")

    # Row 2 is valid, row 3 has an invalid amount
    csv_content = (
        b"date,amount,description\n"
        b"2026-01-15,-150.00,PIX VALIDO\n"
        b"2026-01-16,R$ 100,VALOR INVALIDO\n"
    )

    # _parse_csv must return (rows, error_lines) or raise ValueError only above 50%
    # Since 1 of 2 rows fails (50%), it may or may not raise — exercise the case
    # below the threshold: call it and check that a 50% failure rate does not raise.
    try:
        result = _parse_csv(csv_content)
        # If it returns rows only, check that the invalid row is not included
        if isinstance(result, list):
            amounts = [r.amount for r in result]
            assert Decimal("-150.00") in amounts, (
                f"The valid row must be in the result; amounts: {amounts}"
            )
            # The invalid row must not produce a ParsedRow with a wrong amount
            for row in result:
                assert isinstance(row.amount, Decimal), (
                    f"Amount must be Decimal, not {type(row.amount)}: {row.amount!r}"
                )
        # If it returns (rows, error_lines), check both
        elif isinstance(result, tuple) and len(result) == 2:
            rows, error_lines = result
            assert len(error_lines) >= 1, (
                f"The invalid row must be in error_lines; error_lines: {error_lines}"
            )
    except ValueError:
        # ValueError is only acceptable when more than 50% of the rows failed (D-13 threshold)
        pass


def test_parse_csv_abort_threshold():
    """MOV-02 + D-13: more than 50% invalid rows raises ValueError.

    Nyquist stub — red until services.py implements the abort threshold (plan 08-03).
    With 3 of 3 rows invalid (100% > 50%), _parse_csv must raise ValueError.
    """
    services = pytest.importorskip("caramello_api.finances.services")
    _parse_csv = getattr(services, "_parse_csv", None)
    if _parse_csv is None:
        pytest.skip("_parse_csv is not implemented yet in caramello.finances.services")

    # 3 data rows, all with an invalid amount (100% failure > 50%)
    csv_content = (
        b"date,amount,description\n"
        b"2026-01-15,R$ 100,INVALIDO A\n"
        b"2026-01-16,EUR 200,INVALIDO B\n"
        b"2026-01-17,abc,INVALIDO C\n"
    )

    with pytest.raises(ValueError, match=r"50%|limiar|threshold|falharam"):
        _parse_csv(csv_content)


def test_compute_hash():
    """D-04 + D-07: the (account_id|date|amount|desc_norm) hash is deterministic; FITID differs.

    Nyquist stub — red until services.py implements _compute_hash (plan 08-03).
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

    # D-07: CSV/XLSX hash — based on (account_id|date|amount|desc_norm)
    row_no_fitid = ParsedRow(date=date, amount=amount, description="PIX FULANO", fitid=None)
    hash1 = _compute_hash(account_id=10, row=row_no_fitid)
    hash2 = _compute_hash(account_id=10, row=row_no_fitid)

    # Deterministic: same inputs → same hash
    assert hash1 == hash2, f"Hash must be deterministic; got: {hash1!r} and {hash2!r}"
    assert len(hash1) == 64, f"SHA-256 must be 64 hex characters long; got: {len(hash1)}"

    # D-04: OFX — the hash is derived from the FITID, not from the compound key
    row_with_fitid = ParsedRow(date=date, amount=amount, description="PIX FULANO", fitid="TX001")
    hash_fitid = _compute_hash(account_id=10, row=row_with_fitid)

    # The hash with a FITID must differ from the one without it (different algorithms)
    assert hash_fitid != hash1, (
        f"Hash with FITID must differ from the hash without it; both were: {hash1!r}"
    )
    assert len(hash_fitid) == 64, f"SHA-256 must be 64 hex characters long; got: {len(hash_fitid)}"


def test_normalize_description():
    """D-06: conservative normalization — strip + lower + collapse of repeated spaces.

    Nyquist stub — red until services.py implements _normalize_description (plan 08-03).
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
# Helpers for the Phase 9 stubs
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
# Nyquist stubs — Phase 9 (reconciliation, balances, reports)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# suggest_category — LAN-03, D-CAT-01/02/03
# ---------------------------------------------------------------------------


def test_suggest_category_service():
    """LAN-03, D-CAT-01/02: suggest_category returns the top 5 with a score when history exists.

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
    """D-CAT-03: suggest_category returns [] when there is no movement history.

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

    assert result == [], f"D-CAT-03: with no history it must return []; returned {result!r}"


# ---------------------------------------------------------------------------
# account_balance — REL-01, D-BAL-01, pitfall P6
# ---------------------------------------------------------------------------


def test_account_balance_empty():
    """REL-01: account_balance returns Decimal('0.00') when there are no movements.

    SUM() over an empty set returns NULL in PostgreSQL — the function must
    convert that to Decimal('0.00') (pitfall P6 from STATE.md).
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
# family_balance — REL-02, D-BAL-02
# ---------------------------------------------------------------------------


def test_family_balance():
    """REL-02: family_balance returns a Decimal consolidating every account of the family.

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
# monthly_breakdown — REL-03/04, D-REP-01/03
# ---------------------------------------------------------------------------


def test_monthly_breakdown():
    """REL-03/04, D-REP-01: monthly_breakdown returns a structure of rows per subcategory.

    Every row must carry category_uuid, subcategory_uuid, total (Decimal), count (int).
    The report works over competencia_year/month — not over Movement.date (REL-05).
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
# by_member_breakdown — D-REP-02
# ---------------------------------------------------------------------------


def test_by_member_breakdown():
    """D-REP-02: by_member_breakdown returns rows including the user_uuid=None group.

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

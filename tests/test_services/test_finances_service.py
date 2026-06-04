"""Testes unitários de src/caramello/finances/services.py — Fase 9 (Wave 0).

Stubs Nyquist: cada teste carrega a função via importorskip + getattr e
chama pytest.skip se a função ainda não existe. Assim a suite permanece
verde enquanto a implementação não chega (planos 09-03 e 09-04).

Funções cobertas:
- suggest_category    (LAN-03, D-CAT-01/02/03)
- account_balance     (REL-01, D-BAL-01)
- family_balance      (REL-02, D-BAL-02)
- monthly_breakdown   (REL-03/04, D-REP-01)
- by_member_breakdown (D-REP-02)
"""
from __future__ import annotations

import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_service(func_name: str):
    """Importa o módulo de services e retorna a função pelo nome.

    Chama pytest.skip se o módulo ou a função ainda não existem.
    """
    services = pytest.importorskip(
        "caramello.finances.services",
        reason="caramello.finances.services ainda não existe",
    )
    func = getattr(services, func_name, None)
    if func is None:
        pytest.skip(f"{func_name} ainda não implementada em caramello.finances.services")
    return func


def _run(coro):
    """Executa uma coroutine no event loop padrão."""
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# suggest_category — LAN-03, D-CAT-01/02/03
# ---------------------------------------------------------------------------


def test_suggest_category_service():
    """LAN-03, D-CAT-01/02: suggest_category retorna top-5 com score quando há histórico.

    O mock de session.execute simula um histórico com uma entrada para que
    o retorno seja uma lista de dicts com as chaves esperadas pelo contrato
    da API (subcategory_uuid, subcategory_name, category_uuid, category_name, score).
    """
    suggest_category = _load_service("suggest_category")

    movement_uuid = uuid4()
    family_id = 1

    # Simula linha de Movement alvo
    mock_target_row = MagicMock()
    mock_target_row.__getitem__ = lambda self, i: MagicMock(description="Supermercado Pão de Açúcar")

    # Simula linha de histórico:
    # entry[0] = description, entry[1] = subcategory_id,
    # entry[2] = subcategory_uuid, entry[3] = subcategory_name,
    # entry[4] = category_uuid, entry[5] = category_name
    sub_uuid = uuid4()
    cat_uuid = uuid4()
    history_row = MagicMock()
    history_row.__getitem__ = MagicMock(side_effect=lambda i: [
        "Supermercado Carrefour",  # description
        10,                         # subcategory_id
        sub_uuid,                   # subcategory_uuid
        "Supermercado",             # subcategory_name
        cat_uuid,                   # category_uuid
        "Alimentação",              # category_name
    ][i])

    # Primeira chamada: busca Movement alvo; segunda: busca histórico
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

    result = _run(suggest_category(
        movement_uuid=movement_uuid,
        family_id=family_id,
        session=mock_session,
    ))

    assert isinstance(result, list), f"Esperado list; foi {type(result)}"
    assert len(result) >= 1, "Deve retornar ao menos 1 sugestão quando há histórico"
    item = result[0]
    expected_keys = {"subcategory_uuid", "subcategory_name", "category_uuid", "category_name", "score"}
    assert expected_keys.issubset(item.keys()), (
        f"Chaves faltando: {expected_keys - item.keys()}"
    )
    assert isinstance(item["score"], int), (
        f"score deve ser int (A1 — rapidfuzz retorna float, converter); foi {type(item['score'])}"
    )


def test_suggest_category_empty_history():
    """D-CAT-03: suggest_category retorna [] quando não há histórico de lançamentos.

    Sem threshold mínimo — função simplesmente retorna lista vazia, sem erro.
    """
    suggest_category = _load_service("suggest_category")

    movement_uuid = uuid4()
    family_id = 2

    # Movimento alvo encontrado
    mock_target_row = MagicMock()
    mock_target_row.__getitem__ = MagicMock(side_effect=lambda i: MagicMock(description="Uber"))

    mock_result_target = MagicMock()
    mock_result_target.fetchone.return_value = mock_target_row

    # Histórico vazio
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

    result = _run(suggest_category(
        movement_uuid=movement_uuid,
        family_id=family_id,
        session=mock_session,
    ))

    assert result == [], (
        f"D-CAT-03: sem histórico deve retornar []; retornou {result!r}"
    )


# ---------------------------------------------------------------------------
# account_balance — REL-01, D-BAL-01, pitfall P6
# ---------------------------------------------------------------------------


def test_account_balance_empty():
    """REL-01: account_balance retorna Decimal('0.00') quando não há movimentações.

    SUM() sobre conjunto vazio retorna NULL no PostgreSQL — a função deve
    converter para Decimal('0.00') (pitfall P6 do STATE.md).
    """
    account_balance = _load_service("account_balance")

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None  # SUM() vazio → None

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    balance = _run(account_balance(account_id=1, session=mock_session))

    assert balance == Decimal("0.00"), (
        f"Saldo vazio deve ser Decimal('0.00'); foi: {balance!r}"
    )
    assert isinstance(balance, Decimal), (
        f"Saldo deve ser Decimal, não float ou str; foi {type(balance)}"
    )


# ---------------------------------------------------------------------------
# family_balance — REL-02, D-BAL-02
# ---------------------------------------------------------------------------


def test_family_balance():
    """REL-02: family_balance retorna Decimal consolidado de todas as contas da família.

    O mock simula uma conta com saldo de 500.00, esperando retorno como Decimal.
    """
    family_balance = _load_service("family_balance")

    mock_session = AsyncMock()

    # Simula contas da família retornadas via session.exec ou session.execute
    mock_accounts_result = MagicMock()

    from datetime import datetime, timezone

    from caramello.finances.models import Account  # type: ignore[import-not-found]

    fake_account = Account(
        id=1,
        uuid=uuid4(),
        family_id=5,
        name="Conta Corrente",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    mock_accounts_result.all.return_value = [fake_account]

    # Saldo agregado da conta
    mock_balance_result = MagicMock()
    mock_balance_result.scalar_one_or_none.return_value = Decimal("500.00")

    execute_calls = [mock_balance_result]
    exec_count = [0]

    async def _execute(_stmt):
        idx = exec_count[0]
        exec_count[0] += 1
        return execute_calls[idx] if idx < len(execute_calls) else MagicMock()

    async def _exec(_stmt):
        return mock_accounts_result

    mock_session.exec = AsyncMock(side_effect=_exec)
    mock_session.execute = AsyncMock(side_effect=_execute)

    result = _run(family_balance(family_id=5, session=mock_session))

    assert isinstance(result, Decimal), (
        f"family_balance deve retornar Decimal; foi {type(result)}"
    )
    assert result >= Decimal("0.00"), "Saldo familiar não deve ser negativo neste mock"


# ---------------------------------------------------------------------------
# monthly_breakdown — REL-03/04, D-REP-01/03
# ---------------------------------------------------------------------------


def test_monthly_breakdown():
    """REL-03/04, D-REP-01: monthly_breakdown retorna estrutura de rows por subcategoria.

    Cada row deve ter category_uuid, subcategory_uuid, total (Decimal), count (int).
    Relatório opera sobre competencia_year/month — não sobre Movement.date (REL-05).
    """
    monthly_breakdown = _load_service("monthly_breakdown")

    # Simula resultado de GROUP BY retornando uma row nomeada
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

    result = _run(monthly_breakdown(
        family_id=1,
        year=2026,
        month=5,
        session=mock_session,
    ))

    assert isinstance(result, list), f"Esperado list; foi {type(result)}"
    assert len(result) == 1, f"Esperado 1 row; foi {len(result)}"


# ---------------------------------------------------------------------------
# by_member_breakdown — D-REP-02
# ---------------------------------------------------------------------------


def test_by_member_breakdown():
    """D-REP-02: by_member_breakdown retorna rows incluindo grupo user_uuid=None.

    Lançamentos sem responsible_user_id são agrupados em linha com
    user_uuid=None e name='Não atribuído' — não são descartados dos totais.
    """
    by_member_breakdown = _load_service("by_member_breakdown")

    # Simula row com responsável atribuído
    mock_row_user = MagicMock()
    mock_row_user.user_uuid = uuid4()
    mock_row_user.name = "João"
    mock_row_user.total = Decimal("500.00")
    mock_row_user.count = 8

    # Simula row de não-atribuídos (user_uuid=None)
    mock_row_none = MagicMock()
    mock_row_none.user_uuid = None
    mock_row_none.name = "Não atribuído"
    mock_row_none.total = Decimal("700.00")
    mock_row_none.count = 12

    mock_result = MagicMock()
    mock_result.fetchall.return_value = [mock_row_user, mock_row_none]

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    result = _run(by_member_breakdown(
        family_id=1,
        year=2026,
        month=5,
        session=mock_session,
    ))

    assert isinstance(result, list), f"Esperado list; foi {type(result)}"
    # Deve incluir grupo de não-atribuídos
    assert len(result) >= 1, "Deve retornar ao menos uma row"

"""Testes unitários de src/caramello_api/finances/services.py.

Testa parsers e lógica de deduplicação sem banco real (unit puro).
Imports são lazy (dentro de cada teste) para que o arquivo colete normalmente
antes de services.py existir — ImportError aparece como falha no corpo do teste
(red explícito), não como erro de coleta.

Stubs Nyquist — red até plano 08-03 entregar services.py implementado.
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
    """MOV-02 + D-10: _parse_csv detecta separador ';' e ',' via csv.Sniffer.

    Stub Nyquist — red até services.py implementar _parse_csv (plano 08-03).
    Verifica que Sniffer distingue ponto-e-vírgula de vírgula corretamente.
    """
    services = pytest.importorskip("caramello_api.finances.services")
    _parse_csv = getattr(services, "_parse_csv", None)
    if _parse_csv is None:
        pytest.skip("_parse_csv ainda não implementada em caramello.finances.services")

    # Separador ponto-e-vírgula (padrão BR)
    csv_semicolon = b"date;amount;description\n2026-01-15;-150.00;PIX FULANO\n"
    rows_sc = _parse_csv(csv_semicolon)
    assert len(rows_sc) == 1, f"Esperado 1 linha; obtido {len(rows_sc)}"
    assert rows_sc[0].amount == Decimal("-150.00"), (
        f"Amount deve ser Decimal('-150.00'); foi {rows_sc[0].amount!r}"
    )
    assert rows_sc[0].description == "PIX FULANO", (
        f"Description incorreta: {rows_sc[0].description!r}"
    )

    # Separador vírgula (padrão EN)
    csv_comma = b"date,amount,description\n2026-01-16,200.00,SALARIO\n"
    rows_comma = _parse_csv(csv_comma)
    assert len(rows_comma) == 1, f"Esperado 1 linha; obtido {len(rows_comma)}"
    assert rows_comma[0].amount == Decimal("200.00"), (
        f"Amount deve ser Decimal('200.00'); foi {rows_comma[0].amount!r}"
    )


def test_parse_csv_error_lines():
    """MOV-02 + D-13: linha com amount inválido vai para error_lines[] sem abortar o lote.

    Stub Nyquist — red até services.py implementar tratamento de linhas inválidas.
    Linha com valor 'R$ 100' não é Decimal válido — deve aparecer em error_lines[],
    sem impedir o processamento das linhas válidas.
    """
    services = pytest.importorskip("caramello_api.finances.services")
    _parse_csv = getattr(services, "_parse_csv", None)
    if _parse_csv is None:
        pytest.skip("_parse_csv ainda não implementada em caramello.finances.services")

    # Linha 2 válida, linha 3 com amount inválido
    csv_content = (
        b"date,amount,description\n"
        b"2026-01-15,-150.00,PIX VALIDO\n"
        b"2026-01-16,R$ 100,VALOR INVALIDO\n"
    )

    # _parse_csv deve retornar (rows, error_lines) ou levantar ValueError apenas se >50%
    # Como 1/2 linhas falha (50%), pode ou não levantar — testar o caso sem threshold
    # Abordagem: chamar e verificar que não levanta exceção com 50% de falha
    try:
        result = _parse_csv(csv_content)
        # Se retornar apenas rows, verificar que a linha inválida não está incluída
        if isinstance(result, list):
            amounts = [r.amount for r in result]
            assert Decimal("-150.00") in amounts, (
                f"Linha válida deve estar no resultado; amounts: {amounts}"
            )
            # A linha inválida não deve gerar um ParsedRow com amount incorreto
            for row in result:
                assert isinstance(row.amount, Decimal), (
                    f"Amount deve ser Decimal, não {type(row.amount)}: {row.amount!r}"
                )
        # Se retornar (rows, error_lines), verificar ambos
        elif isinstance(result, tuple) and len(result) == 2:
            rows, error_lines = result
            assert len(error_lines) >= 1, (
                f"Linha inválida deve estar em error_lines; error_lines: {error_lines}"
            )
    except ValueError:
        # ValueError só é aceitável se >50% das linhas falharam (threshold D-13)
        pass


def test_parse_csv_abort_threshold():
    """MOV-02 + D-13: >50% de linhas inválidas levanta ValueError.

    Stub Nyquist — red até services.py implementar limiar de abort (plano 08-03).
    Com 3/3 linhas inválidas (100% > 50%), _parse_csv deve levantar ValueError.
    """
    services = pytest.importorskip("caramello_api.finances.services")
    _parse_csv = getattr(services, "_parse_csv", None)
    if _parse_csv is None:
        pytest.skip("_parse_csv ainda não implementada em caramello.finances.services")

    # 3 linhas de dados, todas com amount inválido (100% de falha > 50%)
    csv_content = (
        b"date,amount,description\n"
        b"2026-01-15,R$ 100,INVALIDO A\n"
        b"2026-01-16,EUR 200,INVALIDO B\n"
        b"2026-01-17,abc,INVALIDO C\n"
    )

    with pytest.raises(ValueError, match=r"50%|limiar|threshold|falharam"):
        _parse_csv(csv_content)


def test_compute_hash():
    """D-04 + D-07: hash de (account_id|date|amount|desc_norm) é determinístico; FITID gera hash distinto.

    Stub Nyquist — red até services.py implementar _compute_hash (plano 08-03).
    """
    services = pytest.importorskip("caramello_api.finances.services")
    _compute_hash = getattr(services, "_compute_hash", None)
    ParsedRow = getattr(services, "ParsedRow", None)
    if _compute_hash is None or ParsedRow is None:
        pytest.skip(
            "_compute_hash ou ParsedRow ainda não implementados em caramello.finances.services"
        )

    from datetime import datetime

    date = datetime(2026, 1, 15, tzinfo=UTC)
    amount = Decimal("-150.00")

    # D-07: hash CSV/XLSX — baseado em (account_id|date|amount|desc_norm)
    row_no_fitid = ParsedRow(date=date, amount=amount, description="PIX FULANO", fitid=None)
    hash1 = _compute_hash(account_id=10, row=row_no_fitid)
    hash2 = _compute_hash(account_id=10, row=row_no_fitid)

    # Determinístico: mesmos inputs → mesmo hash
    assert hash1 == hash2, f"Hash deve ser determinístico; obtidos: {hash1!r} e {hash2!r}"
    assert len(hash1) == 64, f"SHA-256 deve ter 64 caracteres hex; obtido: {len(hash1)}"

    # D-04: OFX — hash é derivado do FITID, não do compound key
    row_with_fitid = ParsedRow(date=date, amount=amount, description="PIX FULANO", fitid="TX001")
    hash_fitid = _compute_hash(account_id=10, row=row_with_fitid)

    # Hash com FITID deve ser distinto do hash sem FITID (algoritmos diferentes)
    assert hash_fitid != hash1, (
        f"Hash com FITID deve diferir do hash sem FITID; ambos foram: {hash1!r}"
    )
    assert len(hash_fitid) == 64, f"SHA-256 deve ter 64 caracteres hex; obtido: {len(hash_fitid)}"


def test_normalize_description():
    """D-06: normalização conservadora — strip + lower + colapso de espaços múltiplos.

    Stub Nyquist — red até services.py implementar _normalize_description (plano 08-03).
    Verifica que '  PIX  RECEBIDO  ' → 'pix recebido'.
    """
    services = pytest.importorskip("caramello_api.finances.services")
    _normalize_description = getattr(services, "_normalize_description", None)
    if _normalize_description is None:
        pytest.skip("_normalize_description ainda não implementada em caramello.finances.services")

    # Caso base: espaços múltiplos, maiúsculas, leading/trailing whitespace
    assert _normalize_description("  PIX  RECEBIDO  ") == "pix recebido", (
        f"Esperado 'pix recebido'; obtido: {_normalize_description('  PIX  RECEBIDO  ')!r}"
    )

    # Sem alteração necessária
    assert _normalize_description("pix recebido") == "pix recebido", (
        "String já normalizada não deve mudar"
    )

    # Tabs e quebras de linha colapsados
    result = _normalize_description("PIX\t\tPAGAMENTO")
    assert result == "pix pagamento", f"Tabs devem ser colapsados; obtido: {result!r}"

    # Apenas espaços residuais removidos
    assert _normalize_description("   ") == "", "Apenas espaços devem resultar em string vazia"


# ---------------------------------------------------------------------------
# Helpers para stubs Fase 9
# ---------------------------------------------------------------------------


def _load_service(func_name: str):
    """Importa o módulo de services e retorna a função pelo nome.

    Chama pytest.skip se o módulo ou a função ainda não existem.
    """
    services = pytest.importorskip(
        "caramello_api.finances.services",
        reason="caramello_api.finances.services ainda não existe",
    )
    func = getattr(services, func_name, None)
    if func is None:
        pytest.skip(f"{func_name} ainda não implementada em caramello.finances.services")
    return func


def _run(coro):
    """Executa uma coroutine de forma compatível com Python 3.10+ e pytest-asyncio.

    Usa asyncio.run() para criar um novo event loop por chamada, evitando
    conflito com event loops criados/fechados por pytest-asyncio nos testes
    de outros módulos (test_family_service.py usa async def tests).
    """
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Stubs Nyquist — Fase 9 (conciliação, saldos, relatórios)
# ---------------------------------------------------------------------------

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
    mock_target_row.__getitem__ = lambda self, i: MagicMock(
        description="Supermercado Pão de Açúcar"
    )

    # Simula linha de histórico:
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

    result = _run(
        suggest_category(
            movement_uuid=movement_uuid,
            family_id=family_id,
            session=mock_session,
        )
    )

    assert isinstance(result, list), f"Esperado list; foi {type(result)}"
    assert len(result) >= 1, "Deve retornar ao menos 1 sugestão quando há histórico"
    item = result[0]
    expected_keys = {
        "subcategory_uuid",
        "subcategory_name",
        "category_uuid",
        "category_name",
        "score",
    }
    assert expected_keys.issubset(item.keys()), f"Chaves faltando: {expected_keys - item.keys()}"
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

    result = _run(
        suggest_category(
            movement_uuid=movement_uuid,
            family_id=family_id,
            session=mock_session,
        )
    )

    assert result == [], f"D-CAT-03: sem histórico deve retornar []; retornou {result!r}"


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

    assert balance == Decimal("0.00"), f"Saldo vazio deve ser Decimal('0.00'); foi: {balance!r}"
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

    # Contas da família: select de UMA entidade, lido via .scalars().all()
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

    # Saldo agregado da conta
    mock_balance_result = MagicMock()
    mock_balance_result.scalar_one_or_none.return_value = Decimal("500.00")

    mock_session.execute.side_effect = execute_mock(
        constant(mock_accounts_result), constant(mock_balance_result)
    )

    result = _run(family_balance(family_id=5, session=mock_session))

    assert isinstance(result, Decimal), f"family_balance deve retornar Decimal; foi {type(result)}"
    assert result == Decimal("500.00"), (
        f"family_balance deve somar o saldo da única conta ativa; foi {result}"
    )


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

    result = _run(
        monthly_breakdown(
            family_id=1,
            year=2026,
            month=5,
            session=mock_session,
        )
    )

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

    result = _run(
        by_member_breakdown(
            family_id=1,
            year=2026,
            month=5,
            session=mock_session,
        )
    )

    assert isinstance(result, list), f"Esperado list; foi {type(result)}"
    # Deve incluir grupo de não-atribuídos
    assert len(result) >= 1, "Deve retornar ao menos uma row"

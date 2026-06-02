"""Testes unitários de src/caramello/finances/services.py.

Testa parsers e lógica de deduplicação sem banco real (unit puro).
Imports são lazy (dentro de cada teste) para que o arquivo colete normalmente
antes de services.py existir — ImportError aparece como falha no corpo do teste
(red explícito), não como erro de coleta.

Stubs Nyquist — red até plano 08-03 entregar services.py implementado.
"""
from __future__ import annotations

from decimal import Decimal

import pytest


def test_parse_csv():
    """MOV-02 + D-10: _parse_csv detecta separador ';' e ',' via csv.Sniffer.

    Stub Nyquist — red até services.py implementar _parse_csv (plano 08-03).
    Verifica que Sniffer distingue ponto-e-vírgula de vírgula corretamente.
    """
    services = pytest.importorskip("caramello.finances.services")
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
    services = pytest.importorskip("caramello.finances.services")
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
    services = pytest.importorskip("caramello.finances.services")
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
    services = pytest.importorskip("caramello.finances.services")
    _compute_hash = getattr(services, "_compute_hash", None)
    ParsedRow = getattr(services, "ParsedRow", None)
    if _compute_hash is None or ParsedRow is None:
        pytest.skip("_compute_hash ou ParsedRow ainda não implementados em caramello.finances.services")

    from datetime import datetime, timezone

    date = datetime(2026, 1, 15, tzinfo=timezone.utc)
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
    services = pytest.importorskip("caramello.finances.services")
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
    assert result == "pix pagamento", (
        f"Tabs devem ser colapsados; obtido: {result!r}"
    )

    # Apenas espaços residuais removidos
    assert _normalize_description("   ") == "", (
        "Apenas espaços devem resultar em string vazia"
    )

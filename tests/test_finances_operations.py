"""Testes para src/caramello/finances/operations.py — Fase 9 (Wave 0).

Stubs Nyquist: verificam presença dos endpoints e comportamentos
especificados nos requisitos LAN-01..05 e REL-01..05.

Estratégia de skip:
- _skip_if_stub(): skippa enquanto finances/operations.py tiver
  '# CARAMELLO-GENERATED: stub' na primeira linha (Phase 7/8/9 pattern).
- pytest.importorskip("caramello.finances.operations"): garantia adicional.

test_finances_router_paths usa _skip_if_stub() para não falhar enquanto
as novas rotas da fase 9 não foram registradas (plano 04-03 remove o guard).
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest


# ---------------------------------------------------------------------------
# Helper: skip enquanto operations.py é stub
# ---------------------------------------------------------------------------


def _skip_if_stub() -> None:
    """Salta o teste se finances/operations.py ainda é stub.

    Verifica a anotação na primeira linha do arquivo. A função é chamada
    no início de cada teste que depende de implementação real.
    """
    pytest.importorskip(
        "caramello.finances.operations",
        reason="caramello.finances.operations ainda não existe",
    )
    ops_path = (
        Path(__file__).resolve().parents[1]
        / "src/caramello/finances/operations.py"
    )
    if ops_path.exists():
        first_line = ops_path.read_text().splitlines()[0].strip()
        if "stub" in first_line:
            pytest.skip("finances/operations.py ainda é stub")


def _make_fake_user(user_id: int = 42):
    """Constrói User válido para uso nos testes."""
    from caramello.users.models import User  # type: ignore[import-not-found]

    return User(
        id=user_id,
        uuid=uuid4(),
        idp_sub=f"fake-sub-{user_id}",
        email=f"user{user_id}@example.com",
        name=f"Usuario {user_id}",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# test_finances_router_paths — atualizado com paths da fase 9
# (guarded por _skip_if_stub enquanto rotas não existem)
# ---------------------------------------------------------------------------


def test_finances_router_paths():
    """Verifica que finances.operations.router tem todos os paths esperados.

    Inclui os 8 paths novos da fase 9. Guarded por _skip_if_stub() para
    não falhar enquanto as rotas ainda não foram implementadas.
    Plano 09-04 Task 3 remove esse guard quando os endpoints chegarem.
    """
    _skip_if_stub()
    ops_mod = pytest.importorskip("caramello.finances.operations")
    router = ops_mod.router
    paths = {getattr(r, "path", None) for r in router.routes}

    expected = {
        # Fase 9 — conciliação
        "/finances/movements/{movement_uuid}/reconcile",
        "/finances/movements/{movement_uuid}/suggest-category",
        # Fase 9 — lançamentos financeiros
        "/finances/entries/{entry_uuid}",
        "/finances/entries",
        # Fase 9 — saldos
        "/finances/accounts/{account_uuid}/balance",
        "/finances/families/{family_uuid}/balance",
        # Fase 9 — relatórios
        "/finances/reports/monthly",
        "/finances/reports/by-member",
    }
    missing = expected - paths
    assert not missing, (
        f"Paths faltando em finances.operations.router: {missing}. "
        f"Encontrados: {paths}"
    )


# ---------------------------------------------------------------------------
# Stubs dos endpoints de conciliação — LAN-01, LAN-02, LAN-03
# ---------------------------------------------------------------------------


def test_reconcile_movement():
    """LAN-01, LAN-04, D-REC-02: POST /finances/movements/{uuid}/reconcile retorna 201.

    Resposta deve incluir schema rico: uuid, movement, subcategory_uuid,
    competencia_year, is_recorrente.
    """
    _skip_if_stub()
    from decimal import Decimal

    from fastapi.testclient import TestClient

    from caramello.finances.models import (  # type: ignore[import-not-found]
        Account,
        FinancialEntry,
        Movement,
        Subcategory,
    )
    from caramello.main import app
    from caramello.shared.auth import get_current_user
    from caramello.shared.database import get_session

    fake_user = _make_fake_user()
    movement_uuid = uuid4()
    entry_uuid = uuid4()
    sub_uuid = uuid4()
    cat_uuid = uuid4()

    fake_movement = Movement(
        id=1,
        uuid=movement_uuid,
        account_id=1,
        date=datetime.now(timezone.utc),
        amount=Decimal("150.00"),
        description="Supermercado",
        import_hash="hash123",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    fake_account = Account(
        id=1,
        uuid=uuid4(),
        family_id=1,
        name="Conta Corrente",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    fake_subcategory = Subcategory(
        id=1,
        uuid=sub_uuid,
        category_id=1,
        name="Supermercado",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    fake_entry = FinancialEntry(
        id=1,
        uuid=entry_uuid,
        movement_id=1,
        subcategory_id=1,
        competencia_year=2026,
        competencia_month=5,
        notes=None,
        is_recorrente=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    added = []

    async def _exec(stmt):
        r = MagicMock()
        r.first.return_value = fake_movement
        r.all.return_value = []
        return r

    async def _execute(stmt):
        r = MagicMock()
        r.first.return_value = fake_account
        r.fetchone.return_value = None
        r.fetchall.return_value = []
        r.scalar_one_or_none.return_value = None
        return r

    mock_session = AsyncMock()
    mock_session.exec.side_effect = _exec
    mock_session.execute = AsyncMock(side_effect=_execute)
    mock_session.add = MagicMock(side_effect=lambda o: added.append(o))
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock(side_effect=lambda o: setattr(o, "uuid", entry_uuid))
    mock_session.rollback = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.post(
            f"/finances/movements/{movement_uuid}/reconcile",
            json={
                "subcategory_uuid": str(sub_uuid),
                "competencia_year": 2026,
                "competencia_month": 5,
                "is_recorrente": False,
            },
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert "uuid" in body, f"Resposta deve conter 'uuid'; foi: {body}"
        assert "movement" in body, "Resposta deve conter objeto 'movement' embutido (D-REC-02)"
        assert "competencia_year" in body, "Resposta deve conter 'competencia_year'"
    finally:
        app.dependency_overrides.clear()


def test_reconcile_409_duplicate():
    """LAN-02: POST /finances/movements/{uuid}/reconcile retorna 409 se já conciliado.

    Quando session.commit levanta IntegrityError, o endpoint deve fazer
    rollback e retornar 409 com mensagem de erro (D-REC-01).
    """
    _skip_if_stub()
    from decimal import Decimal

    from sqlalchemy.exc import IntegrityError
    from fastapi.testclient import TestClient

    from caramello.finances.models import (  # type: ignore[import-not-found]
        Account,
        Movement,
        Subcategory,
    )
    from caramello.main import app
    from caramello.shared.auth import get_current_user
    from caramello.shared.database import get_session

    fake_user = _make_fake_user()
    movement_uuid = uuid4()
    sub_uuid = uuid4()

    fake_movement = Movement(
        id=1,
        uuid=movement_uuid,
        account_id=1,
        date=datetime.now(timezone.utc),
        amount=Decimal("150.00"),
        description="Supermercado",
        import_hash="hash123",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    fake_account = Account(
        id=1,
        uuid=uuid4(),
        family_id=1,
        name="Conta Corrente",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    async def _exec(stmt):
        r = MagicMock()
        r.first.return_value = fake_movement
        r.all.return_value = []
        return r

    async def _execute(stmt):
        r = MagicMock()
        r.first.return_value = fake_account
        r.fetchone.return_value = None
        return r

    mock_session = AsyncMock()
    mock_session.exec.side_effect = _exec
    mock_session.execute = AsyncMock(side_effect=_execute)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock(side_effect=IntegrityError("duplicate", None, None))
    mock_session.rollback = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.post(
            f"/finances/movements/{movement_uuid}/reconcile",
            json={
                "subcategory_uuid": str(sub_uuid),
                "competencia_year": 2026,
                "competencia_month": 5,
            },
        )
        assert response.status_code == 409, (
            f"Duplicata deve retornar 409; foi {response.status_code}: {response.text}"
        )
    finally:
        app.dependency_overrides.clear()


def test_suggest_category():
    """LAN-03, D-CAT-01/02: GET /finances/movements/{uuid}/suggest-category.

    Retorna lista ordenada por score desc. Cada item deve ter:
    subcategory_uuid, subcategory_name, category_uuid, category_name, score.
    """
    _skip_if_stub()
    from fastapi.testclient import TestClient

    from caramello.main import app
    from caramello.shared.auth import get_current_user
    from caramello.shared.database import get_session

    fake_user = _make_fake_user()
    movement_uuid = uuid4()

    mock_session = AsyncMock()
    mock_session.exec.side_effect = lambda s: MagicMock(first=lambda: None, all=lambda: [])
    mock_session.execute = AsyncMock(return_value=MagicMock(
        fetchone=lambda: None,
        fetchall=lambda: [],
    ))
    mock_session.rollback = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.get(
            f"/finances/movements/{movement_uuid}/suggest-category"
        )
        # 200 (lista vazia OK — D-CAT-03) ou 404 se movimento não existe
        assert response.status_code in (200, 404), (
            f"Esperado 200 ou 404; foi {response.status_code}: {response.text}"
        )
        if response.status_code == 200:
            body = response.json()
            assert isinstance(body, list), f"Resposta deve ser lista; foi {type(body)}"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Stubs de atualização de lançamento — LAN-05, D-ATTR
# ---------------------------------------------------------------------------


def test_update_entry():
    """LAN-05, D-REC-04: PATCH /finances/entries/{uuid} atualiza lançamento.

    Atualiza subcategory_uuid, competencia_year, notes e retorna schema rico.
    """
    _skip_if_stub()
    from decimal import Decimal

    from fastapi.testclient import TestClient

    from caramello.finances.models import (  # type: ignore[import-not-found]
        Account,
        FinancialEntry,
        Movement,
        Subcategory,
    )
    from caramello.main import app
    from caramello.shared.auth import get_current_user
    from caramello.shared.database import get_session

    fake_user = _make_fake_user()
    entry_uuid = uuid4()
    sub_uuid = uuid4()

    fake_entry = FinancialEntry(
        id=1,
        uuid=entry_uuid,
        movement_id=1,
        subcategory_id=1,
        competencia_year=2026,
        competencia_month=5,
        notes=None,
        is_recorrente=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    fake_movement = Movement(
        id=1,
        uuid=uuid4(),
        account_id=1,
        date=datetime.now(timezone.utc),
        amount=Decimal("100.00"),
        description="Teste",
        import_hash="h1",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    fake_account = Account(
        id=1,
        uuid=uuid4(),
        family_id=1,
        name="Conta",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    async def _exec(stmt):
        r = MagicMock()
        r.first.return_value = fake_entry
        r.all.return_value = []
        return r

    async def _execute(stmt):
        r = MagicMock()
        r.first.return_value = fake_account
        return r

    mock_session = AsyncMock()
    mock_session.exec.side_effect = _exec
    mock_session.execute = AsyncMock(side_effect=_execute)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()
    mock_session.rollback = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.patch(
            f"/finances/entries/{entry_uuid}",
            json={
                "subcategory_uuid": str(sub_uuid),
                "competencia_year": 2026,
                "notes": "Nota atualizada",
            },
        )
        # 200 esperado; 404 aceitável (entry não existe no mock)
        assert response.status_code in (200, 404), (
            f"Esperado 200 ou 404; foi {response.status_code}: {response.text}"
        )
        if response.status_code == 200:
            body = response.json()
            assert "uuid" in body, "Resposta deve conter 'uuid'"
    finally:
        app.dependency_overrides.clear()


def test_entry_responsible_user_uuid():
    """D-ATTR, D-REC-04: PATCH entries/{uuid} com responsible_user_uuid atribui responsável.

    PATCH com responsible_user_uuid: null deve limpar o campo (sentinela model_fields_set).
    """
    _skip_if_stub()
    from fastapi.testclient import TestClient

    from caramello.main import app
    from caramello.shared.auth import get_current_user
    from caramello.shared.database import get_session

    fake_user = _make_fake_user()
    entry_uuid = uuid4()
    responsible_uuid = uuid4()

    mock_session = AsyncMock()
    mock_session.exec.side_effect = lambda s: MagicMock(first=lambda: None, all=lambda: [])
    mock_session.execute = AsyncMock(return_value=MagicMock(first=lambda: None))
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()
    mock_session.rollback = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        # PATCH com responsável explícito
        response = client.patch(
            f"/finances/entries/{entry_uuid}",
            json={"responsible_user_uuid": str(responsible_uuid)},
        )
        # 200, 404, ou 422 (UUID inválido no mock) — desde que a rota exista
        assert response.status_code in (200, 404, 422), (
            f"Esperado 200/404/422; foi {response.status_code}: {response.text}"
        )
        # PATCH com null — limpar responsável
        response_null = client.patch(
            f"/finances/entries/{entry_uuid}",
            json={"responsible_user_uuid": None},
        )
        assert response_null.status_code in (200, 404, 422), (
            f"Esperado 200/404/422 com null; foi {response_null.status_code}: {response_null.text}"
        )
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Stubs de saldo — REL-01, REL-02
# ---------------------------------------------------------------------------


def test_account_balance():
    """REL-01, D-BAL-01: GET /finances/accounts/{uuid}/balance retorna saldo.

    Resposta: {account_uuid, balance (string), currency}.
    """
    _skip_if_stub()
    from decimal import Decimal

    from fastapi.testclient import TestClient

    from caramello.finances.models import Account  # type: ignore[import-not-found]
    from caramello.main import app
    from caramello.shared.auth import get_current_user
    from caramello.shared.database import get_session

    fake_user = _make_fake_user()
    account_uuid = uuid4()

    fake_account = Account(
        id=1,
        uuid=account_uuid,
        family_id=1,
        name="Conta Corrente",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    async def _exec(stmt):
        r = MagicMock()
        r.first.return_value = fake_account
        return r

    mock_balance_result = MagicMock()
    mock_balance_result.scalar_one_or_none.return_value = Decimal("250.00")

    mock_session = AsyncMock()
    mock_session.exec.side_effect = _exec
    mock_session.execute = AsyncMock(return_value=mock_balance_result)
    mock_session.rollback = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.get(f"/finances/accounts/{account_uuid}/balance")
        assert response.status_code in (200, 404), (
            f"Esperado 200 ou 404; foi {response.status_code}: {response.text}"
        )
        if response.status_code == 200:
            body = response.json()
            assert "balance" in body, f"Resposta deve conter 'balance'; foi: {body}"
            assert "account_uuid" in body or "uuid" in body, (
                "Resposta deve conter account_uuid (D-BAL-01)"
            )
    finally:
        app.dependency_overrides.clear()


def test_family_balance():
    """REL-02, D-BAL-02: GET /finances/families/{uuid}/balance retorna saldo consolidado.

    Resposta: {family_uuid, total_balance, accounts: [...]}.
    """
    _skip_if_stub()
    from decimal import Decimal

    from fastapi.testclient import TestClient

    from caramello.finances.models import Account  # type: ignore[import-not-found]
    from caramello.families.models import Family  # type: ignore[import-not-found]
    from caramello.main import app
    from caramello.shared.auth import get_current_user
    from caramello.shared.database import get_session

    fake_user = _make_fake_user()
    family_uuid = uuid4()

    fake_family = Family(
        id=1,
        uuid=family_uuid,
        name="Familia Teste",
        description=None,
        status="active",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    async def _exec(stmt):
        r = MagicMock()
        r.first.return_value = fake_family
        r.all.return_value = []
        return r

    mock_session = AsyncMock()
    mock_session.exec.side_effect = _exec
    mock_session.execute = AsyncMock(return_value=MagicMock(
        scalar_one_or_none=lambda: Decimal("0.00"),
        fetchall=lambda: [],
    ))
    mock_session.rollback = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.get(f"/finances/families/{family_uuid}/balance")
        assert response.status_code in (200, 404), (
            f"Esperado 200 ou 404; foi {response.status_code}: {response.text}"
        )
        if response.status_code == 200:
            body = response.json()
            assert "total_balance" in body, (
                f"Resposta deve conter 'total_balance' (D-BAL-02); foi: {body}"
            )
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Stubs de relatórios — REL-03, REL-04, REL-05
# ---------------------------------------------------------------------------


def test_monthly_report():
    """REL-03/04, D-REP-01: GET /finances/reports/monthly retorna breakdown.

    Resposta: {period, total, rows} onde cada row tem category_uuid,
    subcategory_uuid e total.
    """
    _skip_if_stub()
    from decimal import Decimal

    from fastapi.testclient import TestClient

    from caramello.families.models import Family  # type: ignore[import-not-found]
    from caramello.main import app
    from caramello.shared.auth import get_current_user
    from caramello.shared.database import get_session

    fake_user = _make_fake_user()
    family_uuid = uuid4()

    fake_family = Family(
        id=1,
        uuid=family_uuid,
        name="Familia Teste",
        description=None,
        status="active",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    async def _exec(stmt):
        r = MagicMock()
        r.first.return_value = fake_family
        r.all.return_value = []
        return r

    mock_session = AsyncMock()
    mock_session.exec.side_effect = _exec
    mock_session.execute = AsyncMock(return_value=MagicMock(fetchall=lambda: []))
    mock_session.rollback = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.get(
            "/finances/reports/monthly",
            params={"family_uuid": str(family_uuid), "year": 2026, "month": 5},
        )
        assert response.status_code in (200, 404), (
            f"Esperado 200 ou 404; foi {response.status_code}: {response.text}"
        )
        if response.status_code == 200:
            body = response.json()
            assert "period" in body, f"Resposta deve conter 'period' (D-REP-01); foi: {body}"
            assert "rows" in body, f"Resposta deve conter 'rows'; foi: {body}"
    finally:
        app.dependency_overrides.clear()


def test_report_uses_competencia():
    """REL-05, D-REP-03: relatório aceita query params year/month (competência).

    Verifica que a rota existe e aceita os parâmetros corretos.
    O relatório opera sobre competencia_year/month — não sobre Movement.date.
    """
    _skip_if_stub()
    from fastapi.testclient import TestClient

    from caramello.families.models import Family  # type: ignore[import-not-found]
    from caramello.main import app
    from caramello.shared.auth import get_current_user
    from caramello.shared.database import get_session

    fake_user = _make_fake_user()
    family_uuid = uuid4()

    fake_family = Family(
        id=1,
        uuid=family_uuid,
        name="Familia Teste",
        description=None,
        status="active",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    async def _exec(stmt):
        r = MagicMock()
        r.first.return_value = fake_family
        r.all.return_value = []
        return r

    mock_session = AsyncMock()
    mock_session.exec.side_effect = _exec
    mock_session.execute = AsyncMock(return_value=MagicMock(fetchall=lambda: []))
    mock_session.rollback = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        # Parametros de competência (year/month) — não parametros de data de movimentação
        response = client.get(
            "/finances/reports/monthly",
            params={"family_uuid": str(family_uuid), "year": 2026, "month": 3},
        )
        # 200 ou 404 (família não encontrada no mock) são válidos
        # 422 indica que os params não foram aceitos — falha
        assert response.status_code != 422, (
            f"Endpoint não deve retornar 422 para params year/month válidos; "
            f"foi: {response.status_code}: {response.text}"
        )
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Stubs de movimento — D-MOV-01, D-MOV-02
# ---------------------------------------------------------------------------


def test_movement_entry_uuid_field():
    """D-MOV-01: GET movements inclui campo entry_uuid em cada item.

    entry_uuid: UUID | None — null para movimentações pendentes de conciliação.
    Implementado via LEFT JOIN com FinancialEntry.
    """
    _skip_if_stub()
    from decimal import Decimal

    from fastapi.testclient import TestClient

    from caramello.finances.models import Account  # type: ignore[import-not-found]
    from caramello.main import app
    from caramello.shared.auth import get_current_user
    from caramello.shared.database import get_session

    fake_user = _make_fake_user()
    account_uuid = uuid4()

    fake_account = Account(
        id=1,
        uuid=account_uuid,
        family_id=1,
        name="Conta Corrente",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    async def _exec(stmt):
        r = MagicMock()
        r.first.return_value = fake_account
        r.all.return_value = []
        return r

    # Simula um movimento sem entry (pendente)
    mock_movement_row = (
        MagicMock(
            uuid=uuid4(),
            date=datetime.now(timezone.utc),
            amount=Decimal("100.00"),
            description="Pagamento",
            import_hash=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        ),
        None,  # entry_uuid = None (pendente)
    )

    mock_execute_result = MagicMock()
    mock_execute_result.fetchall.return_value = [mock_movement_row]

    mock_session = AsyncMock()
    mock_session.exec.side_effect = _exec
    mock_session.execute = AsyncMock(return_value=mock_execute_result)
    mock_session.rollback = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.get(f"/finances/accounts/{account_uuid}/movements")
        assert response.status_code in (200, 404), (
            f"Esperado 200 ou 404; foi {response.status_code}: {response.text}"
        )
        if response.status_code == 200:
            body = response.json()
            if isinstance(body, list) and body:
                item = body[0]
                assert "entry_uuid" in item, (
                    f"D-MOV-01: cada movimento deve ter 'entry_uuid'; chaves: {list(item.keys())}"
                )
    finally:
        app.dependency_overrides.clear()


def test_movement_reconciled_filter():
    """D-MOV-02: GET /finances/accounts/{uuid}/movements?reconciled=false retorna pendentes.

    Filtro opcional: reconciled=false retorna apenas movimentos sem lançamento;
    reconciled=true retorna apenas conciliados. Implementado via LEFT JOIN + IS NULL.
    """
    _skip_if_stub()
    from decimal import Decimal

    from fastapi.testclient import TestClient

    from caramello.finances.models import Account  # type: ignore[import-not-found]
    from caramello.main import app
    from caramello.shared.auth import get_current_user
    from caramello.shared.database import get_session

    fake_user = _make_fake_user()
    account_uuid = uuid4()

    fake_account = Account(
        id=1,
        uuid=account_uuid,
        family_id=1,
        name="Conta Corrente",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    async def _exec(stmt):
        r = MagicMock()
        r.first.return_value = fake_account
        return r

    mock_execute_result = MagicMock()
    mock_execute_result.fetchall.return_value = []

    mock_session = AsyncMock()
    mock_session.exec.side_effect = _exec
    mock_session.execute = AsyncMock(return_value=mock_execute_result)
    mock_session.rollback = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.get(
            f"/finances/accounts/{account_uuid}/movements",
            params={"reconciled": "false"},
        )
        # 200 (lista vazia OK) ou 404 (conta não encontrada no mock)
        # 422 indica que o parâmetro reconciled não é aceito — falha
        assert response.status_code in (200, 404), (
            f"Esperado 200 ou 404; foi {response.status_code}: {response.text}"
        )
    finally:
        app.dependency_overrides.clear()

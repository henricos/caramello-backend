"""Testes para src/caramello/families/operations.py — FAMILY-01, 02, 03, 07.

Estes testes começam skipados (módulo families/operations ainda não existe).
Cada teste usa pytest.importorskip para falhar limpo até a implementação
chegar (plano 04-04). Após a implementação, basta remover a skip line
(ou ela passa automaticamente se o módulo já existir).

Estratégia (igual a tests/test_user_operations.py):
- app.dependency_overrides[get_current_user] = lambda: fake_user
- AsyncMock para get_session
- TestClient(app) sem context manager (evita disparar lifespan/fetch_jwks)
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest


def _make_fake_user(user_id: int = 42):
    """Constrói User válido — importa lazy (suporta users/ e user/ modules)."""
    try:
        from caramello.users.models import User  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        from caramello.user.models import User  # type: ignore[no-redef]
    return User(
        id=user_id,
        uuid=uuid4(),
        idp_sub=f"fake-sub-{user_id}",
        email=f"user{user_id}@example.com",
        name=f"Usuario {user_id}",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def test_families_operations_module_exists():
    """Plano 04-04: módulo src/caramello/families/operations.py existe."""
    pytest.importorskip("caramello.families.operations")


def test_operations_annotation_is_implemented():
    """Plano 04-04: primeira linha == # CARAMELLO-GENERATED: implemented."""
    from pathlib import Path

    ops_path = (
        Path(__file__).resolve().parents[1]
        / "src/caramello/families/operations.py"
    )
    if not ops_path.exists():
        pytest.skip("families/operations.py ainda não foi gerado/implementado")
    first_line = ops_path.read_text().splitlines()[0].strip()
    assert first_line == "# CARAMELLO-GENERATED: implemented", (
        f"Anotação deve ser 'implemented' após plano 04-04; foi: {first_line!r}"
    )


def test_families_operations_router_paths():
    """Plano 04-04: router tem os 6 sub-paths esperados (D-07).

    APIRouter armazena cada `route.path` como sub-path RELATIVO ao prefix do router
    (que vive em `router.prefix`). Portanto, para um `APIRouter(prefix="/families")`
    com `@router.post("/registry")`, o `route.path` é `"/registry"` — NÃO
    `"/families/registry"`. Verificamos só os sub-paths aqui.

    Não checa decorators ou body — apenas que os 6 sub-paths exatos foram registrados.
    """
    ops_mod = pytest.importorskip("caramello.families.operations")
    router = ops_mod.router
    # route.path é o sub-path SEM o prefix do APIRouter
    paths = {getattr(r, "path", None) for r in router.routes}
    expected = {
        "/registry",
        "/families",
        "/families/{family_uuid}",
        "/families/{family_uuid}/pre-register",
        "/families/{family_uuid}/members",
        "/families/{family_uuid}/members/{user_uuid}",
    }
    missing = expected - paths
    assert not missing, (
        f"Sub-paths faltando em families.operations.router: {missing}. "
        f"Encontrados: {paths}. Prefix do router: {router.prefix!r}"
    )


def test_registry_creates_family_and_owner():
    """FAMILY-01 / D-07 / D-13: POST /families/registry cria Family + owner.

    Verifica que a operação adiciona 1 Family e 1 FamilyMember com role='owner'.
    """
    pytest.importorskip("caramello.families.operations")
    from caramello.families.models import (  # type: ignore[import-not-found]
        Family,
        FamilyMember,
    )
    from fastapi.testclient import TestClient

    from caramello.main import app
    from caramello.shared.auth import get_current_user
    from caramello.shared.database import get_session

    fake_user = _make_fake_user()
    added = []

    async def _exec(_stmt):
        r = MagicMock()
        r.first.return_value = None
        r.all.return_value = []
        return r

    async def _refresh(obj):
        if not getattr(obj, "id", None):
            obj.id = 1
        return None

    mock_session = AsyncMock()
    mock_session.exec.side_effect = _exec
    mock_session.add.side_effect = lambda o: added.append(o)
    mock_session.flush = AsyncMock(
        side_effect=lambda: setattr(added[0], "id", 1) if added else None
    )
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock(side_effect=_refresh)
    mock_session.execute = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.post("/families/registry", json={"name": "Familia Teste"})
        assert response.status_code in (200, 201), response.text
        # Deve ter sido adicionada uma Family e um FamilyMember(role="owner")
        family_added = [o for o in added if isinstance(o, Family)]
        members_added = [o for o in added if isinstance(o, FamilyMember)]
        assert len(family_added) == 1, (
            f"Esperado 1 Family adicionada; foi {len(family_added)}"
        )
        assert len(members_added) == 1, (
            f"Esperado 1 FamilyMember adicionado; foi {len(members_added)}"
        )
        assert members_added[0].role == "owner", (
            f"FamilyMember.role deve ser 'owner'; foi {members_added[0].role!r}"
        )
        assert members_added[0].user_id == fake_user.id
    finally:
        app.dependency_overrides.clear()


def test_list_families_only_mine():
    """FAMILY-02: GET /families/families filtra por membership do usuário."""
    pytest.importorskip("caramello.families.operations")
    from caramello.families.models import Family  # type: ignore[import-not-found]
    from fastapi.testclient import TestClient

    from caramello.main import app
    from caramello.shared.auth import get_current_user
    from caramello.shared.database import get_session

    fake_user = _make_fake_user()
    my_family = Family(
        id=10,
        uuid=uuid4(),
        name="Minha familia",
        description=None,
        status="active",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    async def _exec(_stmt):
        r = MagicMock()
        r.all.return_value = [my_family]
        r.first.return_value = my_family
        return r

    mock_session = AsyncMock()
    mock_session.exec.side_effect = _exec
    mock_session.commit = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.get("/families/families")
        assert response.status_code == 200, response.text
        body = response.json()
        assert isinstance(body, list)
        assert len(body) == 1
        assert body[0]["name"] == "Minha familia"
    finally:
        app.dependency_overrides.clear()


def test_get_family_detail_non_member_returns_403():
    """FAMILY-03: GET /families/families/{uuid} retorna 403 se usuário não é membro."""
    pytest.importorskip("caramello.families.operations")
    from fastapi.testclient import TestClient

    from caramello.main import app
    from caramello.shared.auth import get_current_user
    from caramello.shared.database import get_session

    fake_user = _make_fake_user()

    async def _exec(_stmt):
        r = MagicMock()
        r.first.return_value = None
        r.all.return_value = []
        return r

    mock_session = AsyncMock()
    mock_session.exec.side_effect = _exec
    mock_session.commit = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.get(f"/families/families/{uuid4()}")
        # 403 (não-membro) ou 404 (não-existe) são ambos válidos; preferimos 403
        assert response.status_code in (403, 404), response.text
    finally:
        app.dependency_overrides.clear()


def test_pre_register_member_non_owner_returns_403():
    """D-07: POST /families/families/{uuid}/pre-register retorna 403 sem owner role."""
    pytest.importorskip("caramello.families.operations")
    from fastapi.testclient import TestClient

    from caramello.main import app
    from caramello.shared.auth import get_current_user
    from caramello.shared.database import get_session

    fake_user = _make_fake_user()

    async def _exec(_stmt):
        r = MagicMock()
        r.first.return_value = None  # não encontra FamilyMember com role="owner"
        r.all.return_value = []
        return r

    mock_session = AsyncMock()
    mock_session.exec.side_effect = _exec
    mock_session.commit = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.post(
            f"/families/families/{uuid4()}/pre-register",
            json={"email": "novo@example.com"},
        )
        assert response.status_code == 403, response.text
    finally:
        app.dependency_overrides.clear()


def test_remove_member_non_owner_returns_403():
    """FAMILY-07: DELETE members requer role==owner; sem owner retorna 403."""
    pytest.importorskip("caramello.families.operations")
    from fastapi.testclient import TestClient

    from caramello.main import app
    from caramello.shared.auth import get_current_user
    from caramello.shared.database import get_session

    fake_user = _make_fake_user()

    async def _exec(_stmt):
        r = MagicMock()
        r.first.return_value = None  # sem registro de owner
        r.all.return_value = []
        return r

    mock_session = AsyncMock()
    mock_session.exec.side_effect = _exec
    mock_session.commit = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.delete(
            f"/families/families/{uuid4()}/members/{uuid4()}"
        )
        assert response.status_code == 403, response.text
    finally:
        app.dependency_overrides.clear()

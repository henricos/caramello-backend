"""Tests for src/caramello_api/families/operations.py — FAMILY-01, 02, 03, 07.

These tests start out skipped (the families/operations module does not exist yet).
Each one uses pytest.importorskip so it fails cleanly until the implementation
lands (plan 04-04). Once implemented, just drop the skip line (or it passes on
its own if the module is already there).

Strategy (same as tests/test_user_operations.py):
- app.dependency_overrides[get_current_user] = lambda: fake_user
- AsyncMock for get_session, with `session.execute` wired up by `execute_mock`
  (see tests/conftest.py)
- TestClient(app) without the context manager (avoids firing lifespan/fetch_jwks)
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from tests.conftest import apply_column_defaults, execute_mock, refresh_mock


def _make_fake_user(user_id: int = 42):
    """Builds a valid User — imports lazily (supports both users/ and user/ modules)."""
    try:
        from caramello_api.users.models import User  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        from caramello_api.user.models import User  # type: ignore[no-redef]
    return User(
        id=user_id,
        uuid=uuid4(),
        idp_sub=f"fake-sub-{user_id}",
        email=f"user{user_id}@example.com",
        name=f"Usuario {user_id}",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def test_families_operations_module_exists():
    """Plan 04-04: the module src/caramello_api/families/operations.py exists."""
    pytest.importorskip("caramello_api.families.operations")


def test_operations_annotation_is_implemented():
    """Plan 04-04: first line == # CARAMELLO-GENERATED: implemented."""
    pytest.importorskip("caramello_api.families.operations")
    from pathlib import Path

    ops_path = Path(__file__).resolve().parents[1] / "src/caramello_api/families/operations.py"
    if not ops_path.exists():
        pytest.skip("families/operations.py has not been generated/implemented yet")
    first_line = ops_path.read_text().splitlines()[0].strip()
    assert first_line == "# CARAMELLO-GENERATED: implemented", (
        f"The annotation must be 'implemented' after plan 04-04; got: {first_line!r}"
    )


def test_families_operations_router_paths():
    """Plan 04-04: the router carries the 6 expected paths (D-07).

    FastAPI/Starlette stores `route.path` as the FULL path within the router
    (decorator path plus the router's own prefix — for `@router.post("/registry")`
    on a router with `prefix="/families"`, route.path is `"/families/registry"`).

    The paths asserted here carry NO `/api/v1`: the version prefix is applied by
    `main.py` at registration, so the router itself stays version-agnostic.

    Checks neither decorators nor bodies — only that the 6 exact paths exist.
    """
    ops_mod = pytest.importorskip("caramello_api.families.operations")
    router = ops_mod.router
    paths = {getattr(r, "path", None) for r in router.routes}
    expected = {
        "/families/registry",
        "/families/families",
        "/families/families/{family_uuid}",
        "/families/families/{family_uuid}/pre-register",
        "/families/families/{family_uuid}/members",
        "/families/families/{family_uuid}/members/{user_uuid}",
    }
    missing = expected - paths
    assert not missing, (
        f"Sub-paths missing from families.operations.router: {missing}. "
        f"Found: {paths}. Router prefix: {router.prefix!r}"
    )


def test_registry_creates_family_and_owner():
    """FAMILY-01 / D-07 / D-13: POST /families/registry creates Family + owner.

    Checks that the operation adds 1 Family and 1 FamilyMember with role='owner'.
    """
    pytest.importorskip("caramello_api.families.operations")
    from fastapi.testclient import TestClient

    from caramello_api.families.models import (  # type: ignore[import-not-found]
        Family,
        FamilyMember,
    )
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    added = []

    def _exec(_stmt):
        r = MagicMock()
        r.first.return_value = None
        r.all.return_value = []
        return r

    async def _refresh(obj):
        apply_column_defaults(obj)
        if not getattr(obj, "id", None):
            obj.id = 1
        return None

    mock_session = AsyncMock()
    mock_session.execute.side_effect = execute_mock(_exec)
    # session.add() is SYNCHRONOUS in async SQLAlchemy — use MagicMock so the
    # side_effect runs immediately (no await)
    mock_session.add = MagicMock(side_effect=lambda o: added.append(o))
    mock_session.flush = AsyncMock(
        side_effect=lambda: setattr(added[0], "id", 1) if added else None
    )
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock(side_effect=_refresh)

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.post("/api/v1/families/registry", json={"name": "Familia Teste"})
        assert response.status_code in (200, 201), response.text
        # One Family and one FamilyMember(role="owner") must have been added
        family_added = [o for o in added if isinstance(o, Family)]
        members_added = [o for o in added if isinstance(o, FamilyMember)]
        assert len(family_added) == 1, f"Expected 1 Family added; got {len(family_added)}"
        assert len(members_added) == 1, f"Expected 1 FamilyMember added; got {len(members_added)}"
        assert members_added[0].role == "owner", (
            f"FamilyMember.role must be 'owner'; got {members_added[0].role!r}"
        )
        assert members_added[0].user_id == fake_user.id
    finally:
        app.dependency_overrides.clear()


def test_list_families_only_mine():
    """FAMILY-02: GET /families/families filters by the user's membership."""
    pytest.importorskip("caramello_api.families.operations")
    from fastapi.testclient import TestClient

    from caramello_api.families.models import Family  # type: ignore[import-not-found]
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    my_family = Family(
        id=10,
        uuid=uuid4(),
        name="Minha familia",
        description=None,
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    def _exec(_stmt):
        r = MagicMock()
        r.all.return_value = [my_family]
        r.first.return_value = my_family
        return r

    mock_session = AsyncMock()
    mock_session.execute.side_effect = execute_mock(_exec)
    mock_session.commit = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.get("/api/v1/families/families")
        assert response.status_code == 200, response.text
        body = response.json()
        assert isinstance(body, list)
        assert len(body) == 1
        assert body[0]["name"] == "Minha familia"
    finally:
        app.dependency_overrides.clear()


def test_get_family_detail_non_member_returns_403():
    """FAMILY-03: GET /families/families/{uuid} returns 403 when the user is not a member."""
    pytest.importorskip("caramello_api.families.operations")
    from fastapi.testclient import TestClient

    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()

    def _exec(_stmt):
        r = MagicMock()
        r.first.return_value = None
        r.all.return_value = []
        return r

    mock_session = AsyncMock()
    mock_session.execute.side_effect = execute_mock(_exec)
    mock_session.commit = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.get(f"/api/v1/families/families/{uuid4()}")
        # Both 403 (not a member) and 404 (does not exist) are valid; 403 is preferred
        assert response.status_code in (403, 404), response.text
    finally:
        app.dependency_overrides.clear()


def test_pre_register_member_exposes_uuids_not_integer_fks():
    """D-07: the 201 body carries family_uuid/inviter_uuid, never the integer FKs.

    `FamilyInvitationRead` declares both foreign keys with `expose_as_uuid: true`
    in the DSL, so the attributes do not exist on the ORM instance and the
    operation must build the response field by field. A regression here is a
    500, or an integer id on the wire — the invariant in the root
    docs/architecture.md.
    """
    pytest.importorskip("caramello_api.families.operations")
    from fastapi.testclient import TestClient

    from caramello_api.families.models import (  # type: ignore[import-not-found]
        Family,
        FamilyMember,
    )
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    family_uuid = uuid4()
    fake_family = Family(
        id=7,
        uuid=family_uuid,
        name="Familia Teste",
        description=None,
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_owner_member = FamilyMember(
        family_id=fake_family.id,
        user_id=fake_user.id,
        role="owner",
        joined_at=datetime.now(UTC),
    )

    def _exec(_stmt):
        r = MagicMock()
        # _require_owner reads the (Family, FamilyMember) Row through .first()
        r.first.return_value = (fake_family, fake_owner_member)
        r.all.return_value = []
        return r

    added = []
    mock_session = AsyncMock()
    mock_session.execute.side_effect = execute_mock(_exec)
    mock_session.add = MagicMock(side_effect=lambda o: added.append(o))
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock(side_effect=refresh_mock())

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.post(
            f"/api/v1/families/families/{family_uuid}/pre-register",
            json={"email": "convidado@exemplo.com"},
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["family_uuid"] == str(family_uuid), body
        assert body["inviter_uuid"] == str(fake_user.uuid), body
        assert body["email"] == "convidado@exemplo.com", body
        assert body["status"] == "pending_login", body
        for leaked in ("family_id", "inviter_id", "id"):
            assert leaked not in body, f"{leaked} must not reach the wire: {body}"
        # The row that was persisted still uses the internal integer FKs
        assert len(added) == 1, added
        assert added[0].family_id == fake_family.id
        assert added[0].inviter_id == fake_user.id
    finally:
        app.dependency_overrides.clear()


def test_pre_register_member_non_owner_returns_403():
    """D-07: POST /families/families/{uuid}/pre-register returns 403 without the owner role."""
    pytest.importorskip("caramello_api.families.operations")
    from fastapi.testclient import TestClient

    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()

    def _exec(_stmt):
        r = MagicMock()
        r.first.return_value = None  # finds no FamilyMember with role="owner"
        r.all.return_value = []
        return r

    mock_session = AsyncMock()
    mock_session.execute.side_effect = execute_mock(_exec)
    mock_session.commit = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.post(
            f"/api/v1/families/families/{uuid4()}/pre-register",
            json={"email": "novo@example.com"},
        )
        assert response.status_code == 403, response.text
    finally:
        app.dependency_overrides.clear()


def test_remove_member_non_owner_returns_403():
    """FAMILY-07: DELETE members requires role==owner; without owner it returns 403."""
    pytest.importorskip("caramello_api.families.operations")
    from fastapi.testclient import TestClient

    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()

    def _exec(_stmt):
        r = MagicMock()
        r.first.return_value = None  # no owner record
        r.all.return_value = []
        return r

    mock_session = AsyncMock()
    mock_session.execute.side_effect = execute_mock(_exec)
    mock_session.commit = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.delete(f"/api/v1/families/families/{uuid4()}/members/{uuid4()}")
        assert response.status_code == 403, response.text
    finally:
        app.dependency_overrides.clear()

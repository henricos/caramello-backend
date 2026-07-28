"""Tests for src/caramello_api/finances/operations.py — ACC-01, ACC-02, ACC-03,
CAT-01, CAT-02, CAT-03, CAT-04, AUTH-FIN-01, AUTH-FIN-02.

These tests start out skipped (the finances/operations module is not implemented
yet). Each test uses pytest.importorskip so it fails cleanly until the
implementation lands (plans 07-02 and 07-03). Once operations.py is marked as
`# CARAMELLO-GENERATED: implemented`, the tests start running automatically.

Strategy (same as tests/test_family_operations.py):
- app.dependency_overrides[get_current_user] = lambda: fake_user
- AsyncMock for get_session, with `session.execute` wired up by `execute_mock`
  (see tests/conftest.py): the entity handler answers single-entity selects
  (`.scalars()`), the row handler answers multi-entity queries
- TestClient(app) without a context manager (avoids triggering lifespan/fetch_jwks)
"""

from __future__ import annotations

import io
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from tests.conftest import (
    apply_column_defaults,
    constant,
    entity_sequence,
    execute_mock,
    refresh_mock,
)


def _skip_if_stub() -> None:
    """Skip the test if finances/operations.py is still marked as a stub.

    How it works: importorskip tries to import the module; if the import
    succeeds, the annotation on the first line is checked. If it says 'stub',
    an explicit skip is emitted. Once operations.py carries
    '# CARAMELLO-GENERATED: implemented', the check passes and the tests run
    normally.
    """
    pytest.importorskip("caramello_api.finances.operations")
    ops_path = Path(__file__).resolve().parents[1] / "src/caramello_api/finances/operations.py"
    if ops_path.exists():
        first_line = ops_path.read_text().splitlines()[0].strip()
        if "stub" in first_line:
            pytest.skip("finances/operations.py is still a stub — waiting on plan 07-02")


def _make_fake_user(user_id: int = 42):
    """Build a valid User — lazy import (supports both users/ and user/ modules)."""
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


def _assert_not_family_member(response) -> None:
    """AUTH-FIN-02: assert the exact 403 `require_family_access` raises.

    The status alone is not enough: 403 is also what an unrelated policy could
    answer, and the machine-readable `reason` is the part of the contract a
    consumer branches on.
    """
    assert response.status_code == 403, (
        f"Expected 403 for a non-member; got {response.status_code}: {response.text}"
    )
    assert response.json()["detail"]["reason"] == "not_family_member", response.text


def test_finances_module_exists():
    """Plan 07-02/07-03: the src/caramello_api/finances/operations.py module exists."""
    pytest.importorskip("caramello_api.finances.operations")


def test_finances_operations_annotation_is_implemented():
    """Plan 07-02: first line == # CARAMELLO-GENERATED: implemented."""
    _skip_if_stub()
    ops_path = Path(__file__).resolve().parents[1] / "src/caramello_api/finances/operations.py"
    if not ops_path.exists():
        pytest.skip("finances/operations.py has not been generated/implemented yet")
    first_line = ops_path.read_text().splitlines()[0].strip()
    assert first_line == "# CARAMELLO-GENERATED: implemented", (
        f"Annotation must be 'implemented' after plan 07-02; got: {first_line!r}"
    )


def test_finances_router_paths():
    """CAT-03: the router exposes the expected paths (phases 7-8).

    Phase 9 paths are checked in test_finances_router_paths_phase9 (guarded) and
    get enabled by plan 09-04 Task 3 once the endpoints land.
    """
    _skip_if_stub()
    ops_mod = pytest.importorskip("caramello_api.finances.operations")
    router = ops_mod.router
    paths = {getattr(r, "path", None) for r in router.routes}
    expected = {
        "/finances/accounts",
        "/finances/accounts/{account_uuid}",
        "/finances/categories",
        "/finances/categories/{category_uuid}",
        "/finances/subcategory",
        "/finances/subcategory/{subcategory_uuid}",
        "/finances/accounts/{account_uuid}/movements",
        "/finances/accounts/{account_uuid}/movements/import",
        "/finances/import/confirm",
    }
    missing = expected - paths
    assert not missing, (
        f"Sub-paths missing from finances.operations.router: {missing}. "
        f"Found: {paths}. Router prefix: {router.prefix!r}"
    )


def test_finances_router_paths_phase9():
    """Validates the 8 Phase 9 paths — all implemented by plan 09-03/09-04.

    Plan 09-04 Task 3: the phase-9 skip guard is gone (helper deleted) — the
    endpoints are now asserted directly, with no skip condition.
    """
    _skip_if_stub()
    ops_mod = pytest.importorskip("caramello_api.finances.operations")
    router = ops_mod.router
    paths = {getattr(r, "path", None) for r in router.routes}
    phase9_expected = {
        "/finances/movements/{movement_uuid}/reconcile",
        "/finances/movements/{movement_uuid}/suggest-category",
        "/finances/entries/{entry_uuid}",
        "/finances/entries",
        "/finances/accounts/{account_uuid}/balance",
        "/finances/families/{family_uuid}/balance",
        "/finances/reports/monthly",
        "/finances/reports/by-member",
    }
    missing = phase9_expected - paths
    assert not missing, (
        f"Phase 9 paths missing from finances.operations.router: {missing}. Found: {paths}"
    )


def test_create_account_returns_uuid():
    """ACC-01: POST /finances/accounts returns uuid without the internal id/family_id.

    T-07-01: the public response does NOT expose `id` or `family_id`.
    """
    _skip_if_stub()
    from fastapi.testclient import TestClient

    from caramello_api.families.models import Family  # type: ignore[import-not-found]
    from caramello_api.finances.models import Account  # type: ignore[import-not-found]
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    family_uuid = uuid4()
    fake_family = Family(
        id=1,
        uuid=family_uuid,
        name="Familia Teste",
        description=None,
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_account = Account(
        id=10,
        uuid=uuid4(),
        family_id=1,
        name="Conta Corrente",
        type="corrente",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    call_count = [0]

    def _exec(_stmt):
        r = MagicMock()
        call_count[0] += 1
        if call_count[0] == 1:
            # First exec: look up Family by uuid
            r.first.return_value = fake_family
        elif call_count[0] == 2:
            # Second exec: look up FamilyMember (membership check) — returns a valid member
            r.first.return_value = MagicMock()
        else:
            r.first.return_value = None
        r.all.return_value = []
        return r

    async def _refresh(obj):
        apply_column_defaults(obj)
        if isinstance(obj, Account) and not getattr(obj, "uuid", None):
            obj.uuid = fake_account.uuid
        return None

    mock_session = AsyncMock()
    mock_session.execute.side_effect = execute_mock(_exec)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock(side_effect=_refresh)

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/finances/accounts",
            json={
                "family_uuid": str(family_uuid),
                "name": "Conta Corrente",
                "type": "corrente",
                "currency": "BRL",
            },
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert "uuid" in body, f"Response must contain 'uuid'; body: {body}"
        assert "family_uuid" in body, f"Response must contain 'family_uuid'; body: {body}"
        # T-07-01: the response must NOT expose internal keys
        assert "id" not in body, f"Response must NOT expose 'id'; body: {body}"
        assert "family_id" not in body, f"Response must NOT expose 'family_id'; body: {body}"
    finally:
        app.dependency_overrides.clear()


def test_list_accounts_scoped_to_family():
    """ACC-02: GET /finances/accounts?family_uuid=xxx returns only that family's accounts."""
    _skip_if_stub()
    from fastapi.testclient import TestClient

    from caramello_api.families.models import Family  # type: ignore[import-not-found]
    from caramello_api.finances.models import Account  # type: ignore[import-not-found]
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    family_uuid = uuid4()
    fake_family = Family(
        id=1,
        uuid=family_uuid,
        name="Familia Teste",
        description=None,
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_account = Account(
        id=10,
        uuid=uuid4(),
        family_id=1,
        name="Conta Poupança",
        type="poupanca",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    call_count = [0]

    def _exec(_stmt):
        r = MagicMock()
        call_count[0] += 1
        if call_count[0] == 1:
            # First exec: look up Family by uuid
            r.first.return_value = fake_family
            r.all.return_value = [fake_family]
        elif call_count[0] == 2:
            # Second exec: look up FamilyMember (membership check)
            r.first.return_value = MagicMock()
            r.all.return_value = []
        else:
            # Third exec: list the family's accounts
            r.first.return_value = None
            r.all.return_value = [fake_account]
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
        response = client.get(f"/api/v1/finances/accounts?family_uuid={family_uuid}")
        assert response.status_code == 200, response.text
        body = response.json()
        assert isinstance(body, list), f"Response must be a list; got: {type(body)}"
    finally:
        app.dependency_overrides.clear()


def test_accounts_require_auth():
    """AUTH-FIN-01: without a get_current_user override, /finances/accounts returns 401.

    _HTTPBearer401 returns 401 when the token is missing (RFC 7235 §3.1).
    """
    _skip_if_stub()
    from fastapi.testclient import TestClient

    from caramello_api.main import app
    from caramello_api.shared.database import get_session

    def _exec(_stmt):
        r = MagicMock()
        r.first.return_value = None
        r.all.return_value = []
        return r

    mock_session = AsyncMock()
    mock_session.execute.side_effect = execute_mock(_exec)

    def _session_override():
        yield mock_session

    # Does not override get_current_user — _HTTPBearer401 raises 401
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.get(f"/api/v1/finances/accounts?family_uuid={uuid4()}")
        assert response.status_code == 401, (
            f"Expected 401 for an unauthenticated request; got: {response.status_code}. "
            f"Body: {response.text}"
        )
    finally:
        app.dependency_overrides.clear()


def test_accounts_403_non_member():
    """AUTH-FIN-02: an authenticated but non-member user gets 403.

    The mock returns an existing Family but no FamilyMember (first()=None on the
    membership query).
    """
    _skip_if_stub()
    from fastapi.testclient import TestClient

    from caramello_api.families.models import Family  # type: ignore[import-not-found]
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    family_uuid = uuid4()
    fake_family = Family(
        id=1,
        uuid=family_uuid,
        name="Familia Alheia",
        description=None,
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    call_count = [0]

    def _exec(_stmt):
        r = MagicMock()
        call_count[0] += 1
        if call_count[0] == 1:
            # First exec: look up Family by uuid — found
            r.first.return_value = fake_family
        else:
            # Second exec: look up FamilyMember — not found (non-member)
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
        response = client.get(f"/api/v1/finances/accounts?family_uuid={family_uuid}")
        assert response.status_code == 403, (
            f"Expected 403 for a non-member; got: {response.status_code}. Body: {response.text}"
        )
    finally:
        app.dependency_overrides.clear()


def test_archive_account():
    """ACC-03: PATCH /finances/accounts/{uuid} with is_active=false archives without deleting.

    Checks that the response returns is_active=False and that session.delete was
    never called.
    """
    _skip_if_stub()
    from fastapi.testclient import TestClient

    from caramello_api.families.models import Family  # type: ignore[import-not-found]
    from caramello_api.finances.models import Account  # type: ignore[import-not-found]
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    account_uuid = uuid4()
    family_uuid = uuid4()
    fake_family = Family(
        id=1,
        uuid=family_uuid,
        name="Familia Teste",
        description=None,
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_account = Account(
        id=10,
        uuid=account_uuid,
        family_id=1,
        name="Conta Corrente",
        type="corrente",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    call_count = [0]

    def _exec(_stmt):
        r = MagicMock()
        call_count[0] += 1
        if call_count[0] == 1:
            # First exec: look up Account by uuid
            r.first.return_value = fake_account
        elif call_count[0] == 2:
            # Second exec: look up Family by id
            r.first.return_value = fake_family
        else:
            # Third exec: look up FamilyMember (membership check)
            r.first.return_value = MagicMock()
        r.all.return_value = []
        return r

    mock_session = AsyncMock()
    mock_session.execute.side_effect = execute_mock(_exec)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock(side_effect=refresh_mock())
    mock_session.delete = MagicMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.patch(
            f"/api/v1/finances/accounts/{account_uuid}",
            json={"is_active": False},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body.get("is_active") is False, f"Response must have is_active=False; body: {body}"
        # ACC-03: archiving never deletes — session.delete must not have been called
        mock_session.delete.assert_not_called()
    finally:
        app.dependency_overrides.clear()


def test_create_category():
    """CAT-01: POST /finances/categories creates a parent category scoped to a family."""
    _skip_if_stub()
    from fastapi.testclient import TestClient

    from caramello_api.families.models import Family  # type: ignore[import-not-found]
    from caramello_api.finances.models import Category  # type: ignore[import-not-found]
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    family_uuid = uuid4()
    fake_family = Family(
        id=1,
        uuid=family_uuid,
        name="Familia Teste",
        description=None,
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_category = Category(
        id=5,
        uuid=uuid4(),
        family_id=1,
        name="Transporte",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    call_count = [0]

    def _exec(_stmt):
        r = MagicMock()
        call_count[0] += 1
        if call_count[0] == 1:
            # First exec: look up Family by uuid
            r.first.return_value = fake_family
        elif call_count[0] == 2:
            # Second exec: look up FamilyMember (membership check)
            r.first.return_value = MagicMock()
        else:
            r.first.return_value = None
        r.all.return_value = []
        return r

    async def _refresh(obj):
        apply_column_defaults(obj)
        if isinstance(obj, Category) and not getattr(obj, "uuid", None):
            obj.uuid = fake_category.uuid
        return None

    mock_session = AsyncMock()
    mock_session.execute.side_effect = execute_mock(_exec)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock(side_effect=_refresh)

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/finances/categories",
            json={
                "family_uuid": str(family_uuid),
                "name": "Transporte",
            },
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert "uuid" in body, f"Response must contain 'uuid'; body: {body}"
    finally:
        app.dependency_overrides.clear()


def test_list_update_categories():
    """CAT-04: GET /finances/categories?family_uuid=xxx (200) and
    PATCH /finances/categories/{uuid} (200).
    """
    _skip_if_stub()
    from fastapi.testclient import TestClient

    from caramello_api.families.models import Family  # type: ignore[import-not-found]
    from caramello_api.finances.models import Category  # type: ignore[import-not-found]
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    family_uuid = uuid4()
    category_uuid = uuid4()
    fake_family = Family(
        id=1,
        uuid=family_uuid,
        name="Familia Teste",
        description=None,
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_category = Category(
        id=5,
        uuid=category_uuid,
        family_id=1,
        name="Transporte",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    # --- GET test ---
    call_count = [0]

    def _exec_list(_stmt):
        r = MagicMock()
        call_count[0] += 1
        if call_count[0] == 1:
            r.first.return_value = fake_family
            r.all.return_value = [fake_family]
        elif call_count[0] == 2:
            r.first.return_value = MagicMock()
            r.all.return_value = []
        else:
            r.first.return_value = None
            r.all.return_value = [fake_category]
        return r

    mock_session_list = AsyncMock()
    mock_session_list.execute.side_effect = execute_mock(_exec_list)
    mock_session_list.commit = AsyncMock()

    def _session_override_list():
        yield mock_session_list

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override_list
    try:
        client = TestClient(app)
        response_list = client.get(f"/api/v1/finances/categories?family_uuid={family_uuid}")
        assert response_list.status_code == 200, response_list.text
        assert isinstance(response_list.json(), list)
    finally:
        app.dependency_overrides.clear()

    # --- PATCH test ---
    call_count_patch = [0]

    def _exec_patch(_stmt):
        r = MagicMock()
        call_count_patch[0] += 1
        if call_count_patch[0] == 1:
            # Look up Category by uuid
            r.first.return_value = fake_category
        elif call_count_patch[0] == 2:
            # Look up Family by id
            r.first.return_value = fake_family
        else:
            # Look up FamilyMember (membership check)
            r.first.return_value = MagicMock()
        r.all.return_value = []
        return r

    mock_session_patch = AsyncMock()
    mock_session_patch.execute.side_effect = execute_mock(_exec_patch)
    mock_session_patch.add = MagicMock()
    mock_session_patch.commit = AsyncMock()
    mock_session_patch.refresh = AsyncMock()

    def _session_override_patch():
        yield mock_session_patch

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override_patch
    try:
        client = TestClient(app)
        response_patch = client.patch(
            f"/api/v1/finances/categories/{category_uuid}",
            json={"name": "Transporte Atualizado"},
        )
        assert response_patch.status_code == 200, response_patch.text
    finally:
        app.dependency_overrides.clear()


def test_create_subcategory():
    """CAT-02: POST /finances/subcategory creates a subcategory via category_uuid."""
    _skip_if_stub()
    from fastapi.testclient import TestClient

    from caramello_api.families.models import Family  # type: ignore[import-not-found]
    from caramello_api.finances.models import (  # type: ignore[import-not-found]
        Category,
        Subcategory,
    )
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    category_uuid = uuid4()
    family_uuid = uuid4()
    fake_family = Family(
        id=1,
        uuid=family_uuid,
        name="Familia Teste",
        description=None,
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_category = Category(
        id=5,
        uuid=category_uuid,
        family_id=1,
        name="Transporte",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_subcategory = Subcategory(
        id=20,
        uuid=uuid4(),
        category_id=5,
        name="Gasolina",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    call_count = [0]

    def _exec(_stmt):
        r = MagicMock()
        call_count[0] += 1
        if call_count[0] == 1:
            # First exec: look up Category by uuid
            r.first.return_value = fake_category
        elif call_count[0] == 2:
            # Second exec: look up Family by id
            r.first.return_value = fake_family
        elif call_count[0] == 3:
            # Third exec: look up FamilyMember (membership check)
            r.first.return_value = MagicMock()
        else:
            r.first.return_value = None
        r.all.return_value = []
        return r

    async def _refresh(obj):
        apply_column_defaults(obj)
        if isinstance(obj, Subcategory) and not getattr(obj, "uuid", None):
            obj.uuid = fake_subcategory.uuid
        return None

    mock_session = AsyncMock()
    mock_session.execute.side_effect = execute_mock(_exec)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock(side_effect=_refresh)

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/finances/subcategory",
            json={
                "category_uuid": str(category_uuid),
                "name": "Gasolina",
            },
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert "uuid" in body, f"Response must contain 'uuid'; body: {body}"
    finally:
        app.dependency_overrides.clear()


# =============================================================================
# Phase 8: Movement endpoints — MOV-01..05, D-15, AUTH-FIN-01/02
# Nyquist stubs — red/skipped until plans 08-02/08-03/08-04 deliver the implementation
# =============================================================================


def test_create_movement():
    """MOV-01: POST /finances/accounts/{uuid}/movements creates a movement, returns 201 + uuid.

    Nyquist stub — red/skip until operations.py implements the endpoint (plan 08-02).
    """
    _skip_if_stub()
    from fastapi.testclient import TestClient

    from caramello_api.finances.models import Account  # type: ignore[import-not-found]
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    account_uuid = uuid4()
    movement_uuid = uuid4()
    fake_account = Account(
        id=10,
        uuid=account_uuid,
        family_id=1,
        name="Conta Corrente",
        type="corrente",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    call_count = [0]

    def _exec(_stmt):
        r = MagicMock()
        call_count[0] += 1
        if call_count[0] == 1:
            # Resolve Account by uuid
            r.first.return_value = fake_account
        elif call_count[0] == 2:
            # Membership check — valid member
            r.first.return_value = MagicMock()
        else:
            # Hash pre-check: no existing hash (new movement)
            r.first.return_value = None
        r.all.return_value = []
        return r

    # Result of the multi-entity queries: batched hash pre-check
    mock_execute_result = MagicMock()
    mock_execute_result.fetchall.return_value = []

    async def _movement_refresh(obj):
        apply_column_defaults(obj)
        obj.uuid = movement_uuid
        return None

    mock_session = AsyncMock()
    mock_session.execute.side_effect = execute_mock(_exec, constant(mock_execute_result))
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock(side_effect=_movement_refresh)

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.post(
            f"/api/v1/finances/accounts/{account_uuid}/movements",
            json={
                "date": "2026-01-15",
                "amount": "-150.00",
                "description": "PIX FULANO",
            },
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert "uuid" in body, f"Response must contain 'uuid'; body: {body}"
    finally:
        app.dependency_overrides.clear()


def test_create_movement_409_duplicate():
    """MOV-01 + D-17: POST with an already existing hash returns 409 + existing_uuid.

    Nyquist stub — red/skip until operations.py implements the hash check (plan 08-02).
    """
    _skip_if_stub()
    from fastapi.testclient import TestClient

    from caramello_api.finances.models import Account, Movement  # type: ignore[import-not-found]
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    account_uuid = uuid4()
    existing_movement_uuid = uuid4()
    fake_account = Account(
        id=10,
        uuid=account_uuid,
        family_id=1,
        name="Conta Corrente",
        type="corrente",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    existing_movement = Movement(
        id=1,
        uuid=existing_movement_uuid,
        account_id=10,
        date=datetime(2026, 1, 15, tzinfo=UTC),
        amount="-150.00",
        description="PIX FULANO",
        import_hash="abc123hash",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    call_count = [0]

    def _exec(_stmt):
        r = MagicMock()
        call_count[0] += 1
        if call_count[0] == 1:
            # Resolve Account by uuid
            r.first.return_value = fake_account
        elif call_count[0] == 2:
            # Membership check — valid member
            r.first.return_value = MagicMock()
        else:
            # Hash pre-check: returns an existing movement with the same hash (D-17)
            r.first.return_value = existing_movement
        r.all.return_value = []
        return r

    mock_session = AsyncMock()
    mock_session.execute.side_effect = execute_mock(_exec)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.post(
            f"/api/v1/finances/accounts/{account_uuid}/movements",
            json={
                "date": "2026-01-15",
                "amount": "-150.00",
                "description": "PIX FULANO",
            },
        )
        assert response.status_code == 409, (
            f"Expected 409 for a duplicate hash; got: {response.status_code}. Body: {response.text}"
        )
        body = response.json()
        detail = body.get("detail", {})
        assert "existing_uuid" in detail, f"409 must carry 'existing_uuid' in detail; body: {body}"
    finally:
        app.dependency_overrides.clear()


def test_import_csv():
    """MOV-02: POST /accounts/{uuid}/movements/import?format=csv returns inserted + movements[].

    Nyquist stub — red/skip until operations.py implements the import endpoint (plan 08-03).
    """
    _skip_if_stub()
    from fastapi.testclient import TestClient

    from caramello_api.finances.models import Account  # type: ignore[import-not-found]
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    account_uuid = uuid4()
    fake_account = Account(
        id=10,
        uuid=account_uuid,
        family_id=1,
        name="Conta Corrente",
        type="corrente",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    csv_content = (
        b"date,amount,description\n2026-01-15,-150.00,PIX FULANO\n2026-01-16,200.00,SALARIO\n"
    )

    call_count = [0]

    def _exec(_stmt):
        r = MagicMock()
        call_count[0] += 1
        if call_count[0] == 1:
            r.first.return_value = fake_account
        elif call_count[0] == 2:
            r.first.return_value = MagicMock()
        else:
            r.first.return_value = None
        r.all.return_value = []
        return r

    # session.execute for the batched hash pre-check — returns no existing hash
    mock_execute_result = MagicMock()
    mock_execute_result.fetchall.return_value = []

    mock_session = AsyncMock()
    mock_session.execute.side_effect = execute_mock(_exec, constant(mock_execute_result))
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock(side_effect=refresh_mock())

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.post(
            f"/api/v1/finances/accounts/{account_uuid}/movements/import?format=csv",
            files={"file": ("test.csv", io.BytesIO(csv_content), "text/csv")},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert "inserted" in body, f"Response must contain 'inserted'; body: {body}"
        assert "movements" in body, f"Response must contain 'movements'; body: {body}"
    finally:
        app.dependency_overrides.clear()


def test_import_ofx():
    """MOV-03: POST /accounts/{uuid}/movements/import?format=ofx works with a sample OFX.

    Nyquist stub — red/skip until operations.py implements the OFX endpoint (plan 08-03).
    """
    _skip_if_stub()
    from fastapi.testclient import TestClient

    from caramello_api.finances.models import Account  # type: ignore[import-not-found]
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    account_uuid = uuid4()
    fake_account = Account(
        id=10,
        uuid=account_uuid,
        family_id=1,
        name="Conta Corrente",
        type="corrente",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    # Minimal valid OFX sample
    ofx_content = b"""OFXHEADER:100
DATA:OFXSGML
VERSION:102
SECURITY:NONE
ENCODING:USASCII
CHARSET:1252
COMPRESSION:NONE
OLDFILEUID:NONE
NEWFILEUID:NONE

<OFX>
<BANKMSGSRSV1>
<STMTTRNRS>
<TRNUID>1001
<STMTRS>
<CURDEF>BRL
<BANKACCTFROM>
<BANKID>001
<ACCTID>12345-6
<ACCTTYPE>CHECKING
</BANKACCTFROM>
<BANKTRANLIST>
<DTSTART>20260101000000
<DTEND>20260131000000
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20260115000000
<TRNAMT>-150.00
<FITID>TX001
<MEMO>PIX FULANO
</STMTTRN>
</BANKTRANLIST>
</STMTRS>
</STMTTRNRS>
</BANKMSGSRSV1>
</OFX>
"""

    call_count = [0]

    def _exec(_stmt):
        r = MagicMock()
        call_count[0] += 1
        if call_count[0] == 1:
            r.first.return_value = fake_account
        elif call_count[0] == 2:
            r.first.return_value = MagicMock()
        else:
            r.first.return_value = None
        r.all.return_value = []
        return r

    mock_execute_result = MagicMock()
    mock_execute_result.fetchall.return_value = []

    mock_session = AsyncMock()
    mock_session.execute.side_effect = execute_mock(_exec, constant(mock_execute_result))
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock(side_effect=refresh_mock())

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.post(
            f"/api/v1/finances/accounts/{account_uuid}/movements/import?format=ofx",
            files={"file": ("test.ofx", io.BytesIO(ofx_content), "application/x-ofx")},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert "inserted" in body, f"Response must contain 'inserted'; body: {body}"
    finally:
        app.dependency_overrides.clear()


def test_import_xlsx():
    """MOV-03: POST /accounts/{uuid}/movements/import?format=xlsx works with a BytesIO XLSX.

    Nyquist stub — red/skip until operations.py implements the XLSX endpoint (plan 08-03).
    """
    _skip_if_stub()
    import openpyxl
    from fastapi.testclient import TestClient

    from caramello_api.finances.models import Account  # type: ignore[import-not-found]
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    account_uuid = uuid4()
    fake_account = Account(
        id=10,
        uuid=account_uuid,
        family_id=1,
        name="Conta Corrente",
        type="corrente",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    # Build a minimal in-memory XLSX for the test
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["date", "amount", "description"])
    ws.append(["2026-01-15", "-150.00", "PIX FULANO"])
    ws.append(["2026-01-16", "200.00", "SALARIO"])
    xlsx_bytes = io.BytesIO()
    wb.save(xlsx_bytes)
    xlsx_bytes.seek(0)

    call_count = [0]

    def _exec(_stmt):
        r = MagicMock()
        call_count[0] += 1
        if call_count[0] == 1:
            r.first.return_value = fake_account
        elif call_count[0] == 2:
            r.first.return_value = MagicMock()
        else:
            r.first.return_value = None
        r.all.return_value = []
        return r

    mock_execute_result = MagicMock()
    mock_execute_result.fetchall.return_value = []

    mock_session = AsyncMock()
    mock_session.execute.side_effect = execute_mock(_exec, constant(mock_execute_result))
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock(side_effect=refresh_mock())

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.post(
            f"/api/v1/finances/accounts/{account_uuid}/movements/import?format=xlsx",
            files={
                "file": (
                    "test.xlsx",
                    xlsx_bytes,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert "inserted" in body, f"Response must contain 'inserted'; body: {body}"
    finally:
        app.dependency_overrides.clear()


def test_import_deduplication():
    """MOV-04: re-importing the same file does not duplicate movements.

    Nyquist stub — red/skip until operations.py implements hash-based dedup (plan 08-03).
    Simulates the pre-check returning already existing hashes → inserted=0.
    """
    _skip_if_stub()
    from fastapi.testclient import TestClient

    from caramello_api.finances.models import Account  # type: ignore[import-not-found]
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    account_uuid = uuid4()
    fake_account = Account(
        id=10,
        uuid=account_uuid,
        family_id=1,
        name="Conta Corrente",
        type="corrente",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    csv_content = b"date,amount,description\n2026-01-15,-150.00,PIX FULANO\n"

    # WR-05: compute the real hash so the mocked pre-check rejects the row correctly
    from decimal import Decimal

    from caramello_api.finances.services import (  # type: ignore[import-not-found]
        ParsedRow,
        _compute_hash,
    )

    real_row = ParsedRow(
        date=datetime(2026, 1, 15, tzinfo=UTC),
        amount=Decimal("-150.00"),
        description="PIX FULANO",
        fitid=None,
    )
    real_hash = _compute_hash(account_id=10, row=real_row)

    call_count = [0]

    def _exec(_stmt):
        r = MagicMock()
        call_count[0] += 1
        if call_count[0] == 1:
            r.first.return_value = fake_account
        elif call_count[0] == 2:
            r.first.return_value = MagicMock()
        else:
            r.first.return_value = None
        r.all.return_value = []
        return r

    # Mocks for session.execute: 2 distinct calls (WR-05)
    # 1st call: pre-check of existing hashes (returns real_hash as already present)
    mock_precheck_result = MagicMock()
    mock_precheck_result.fetchall.return_value = [(real_hash,)]

    # 2nd call: look up the UUID of CSV/XLSX duplicates (hash → uuid of the existing movement)
    existing_movement_uuid = uuid4()
    mock_uuid_result = MagicMock()
    mock_uuid_result.fetchall.return_value = [(real_hash, existing_movement_uuid)]

    execute_call_count = [0]

    def _row_import(stmt):
        execute_call_count[0] += 1
        if execute_call_count[0] == 1:
            return mock_precheck_result
        return mock_uuid_result

    mock_session = AsyncMock()
    mock_session.execute.side_effect = execute_mock(_exec, _row_import)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.post(
            f"/api/v1/finances/accounts/{account_uuid}/movements/import?format=csv",
            files={"file": ("test.csv", io.BytesIO(csv_content), "text/csv")},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        # D-05: a CSV row has no FITID, so a known hash is a SUSPECTED duplicate
        # handed back for confirmation — never a silent duplicates_skipped (D-04,
        # which is the OFX path) and never an insert
        assert body["inserted"] == 0, body
        assert body["movements"] == [], body
        assert body["duplicates_skipped"] == 0, body
        assert body["error_lines"] == [], body
        assert body["potential_duplicates"] == [
            {
                "new_row": {
                    "date": "2026-01-15",
                    "amount": "-150.00",
                    "description": "PIX FULANO",
                },
                "existing_movement_uuid": str(existing_movement_uuid),
                "hash": real_hash,
            }
        ], body
    finally:
        app.dependency_overrides.clear()


def test_import_potential_duplicates():
    """MOV-05 + D-05: CSV/XLSX with a hash match returns potential_duplicates[].

    Nyquist stub — red/skip until operations.py implements returning
    potential_duplicates for CSV/XLSX (plan 08-03). OFX uses definitive dedup;
    CSV/XLSX return potential_duplicates[] for the user to confirm.
    """
    _skip_if_stub()
    from fastapi.testclient import TestClient

    from caramello_api.finances.models import Account  # type: ignore[import-not-found]
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    account_uuid = uuid4()
    fake_account = Account(
        id=10,
        uuid=account_uuid,
        family_id=1,
        name="Conta Corrente",
        type="corrente",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    csv_content = b"date,amount,description\n2026-01-15,-150.00,PIX FULANO\n"

    call_count = [0]

    def _exec(_stmt):
        r = MagicMock()
        call_count[0] += 1
        if call_count[0] == 1:
            r.first.return_value = fake_account
        elif call_count[0] == 2:
            r.first.return_value = MagicMock()
        else:
            r.first.return_value = None
        r.all.return_value = []
        return r

    # The pre-check finds a matching hash (suspected duplicate for CSV)
    known_hash = "suspect_hash_from_csv"
    mock_execute_result = MagicMock()
    mock_execute_result.fetchall.return_value = [(known_hash,)]

    mock_session = AsyncMock()
    mock_session.execute.side_effect = execute_mock(_exec, constant(mock_execute_result))
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.post(
            f"/api/v1/finances/accounts/{account_uuid}/movements/import?format=csv",
            files={"file": ("test.csv", io.BytesIO(csv_content), "text/csv")},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert "potential_duplicates" in body, (
            f"Response must contain 'potential_duplicates'; body: {body}"
        )
        assert isinstance(body["potential_duplicates"], list), (
            f"'potential_duplicates' must be a list; body: {body}"
        )
    finally:
        app.dependency_overrides.clear()


def test_import_confirm():
    """MOV-05 + D-08: POST /import/confirm inserts confirmed rows without hash collision.

    Nyquist stub — red/skip until operations.py implements the /import/confirm
    endpoint (plan 08-03). Confirmed rows are inserted with import_hash=None (D-08).
    """
    _skip_if_stub()
    from fastapi.testclient import TestClient

    from caramello_api.finances.models import Account  # type: ignore[import-not-found]
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    account_uuid = uuid4()
    fake_account = Account(
        id=10,
        uuid=account_uuid,
        family_id=1,
        name="Conta Corrente",
        type="corrente",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    call_count = [0]

    def _exec(_stmt):
        r = MagicMock()
        call_count[0] += 1
        if call_count[0] == 1:
            r.first.return_value = fake_account
        elif call_count[0] == 2:
            r.first.return_value = MagicMock()
        else:
            r.first.return_value = None
        r.all.return_value = []
        return r

    mock_execute_result = MagicMock()
    mock_execute_result.fetchall.return_value = []

    mock_session = AsyncMock()
    mock_session.execute.side_effect = execute_mock(_exec, constant(mock_execute_result))
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock(side_effect=refresh_mock())

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        # Payload: list of movements confirmed by the user (D-08)
        payload = {
            "account_uuid": str(account_uuid),
            "movements": [
                {
                    "date": "2026-01-15",
                    "amount": "-150.00",
                    "description": "PIX FULANO",
                }
            ],
        }
        response = client.post(
            "/api/v1/finances/import/confirm",
            json=payload,
        )
        assert response.status_code == 200, (
            f"Expected 200 for /import/confirm; got: {response.status_code}. Body: {response.text}"
        )
        body = response.json()
        assert body["inserted"] == 1, body
        assert [m["description"] for m in body["movements"]] == ["PIX FULANO"], body
        # D-08/P4: a confirmed row is inserted with no hash, so the UNIQUE
        # constraint cannot fire on the duplicate the user just accepted
        assert body["movements"][0]["import_hash"] is None, body
    finally:
        app.dependency_overrides.clear()


def test_list_movements():
    """D-15: GET /finances/accounts/{uuid}/movements returns a paginated list.

    Nyquist stub — red/skip until operations.py implements the GET movements
    endpoint (plan 08-02). Supports ?limit=50&offset=0&date_from=&date_to=.
    """
    _skip_if_stub()
    from fastapi.testclient import TestClient

    from caramello_api.finances.models import Account, Movement  # type: ignore[import-not-found]
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    account_uuid = uuid4()
    fake_account = Account(
        id=10,
        uuid=account_uuid,
        family_id=1,
        name="Conta Corrente",
        type="corrente",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_movement = Movement(
        id=1,
        uuid=uuid4(),
        account_id=10,
        date=datetime(2026, 1, 15, tzinfo=UTC),
        amount="-150.00",
        description="PIX FULANO",
        import_hash=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    call_count = [0]

    def _exec(_stmt):
        r = MagicMock()
        call_count[0] += 1
        if call_count[0] == 1:
            r.first.return_value = fake_account
        elif call_count[0] == 2:
            r.first.return_value = MagicMock()
        else:
            r.first.return_value = None
        r.all.return_value = [fake_movement]
        return r

    mock_execute_result = MagicMock()
    mock_execute_result.fetchall.return_value = [(fake_movement,)]

    mock_session = AsyncMock()
    mock_session.execute.side_effect = execute_mock(_exec, constant(mock_execute_result))

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.get(
            f"/api/v1/finances/accounts/{account_uuid}/movements?limit=50&offset=0"
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert isinstance(body, list), f"Response must be a paginated list; body: {body}"
    finally:
        app.dependency_overrides.clear()


def test_movements_require_auth():
    """AUTH-FIN-01/02: 401 without a token, 403 for another family on Movement endpoints.

    Nyquist stub — red/skip until operations.py implements the Movement endpoints (plan 08-02).
    Mirrors the pattern of test_accounts_require_auth and test_accounts_403_non_member.
    """
    _skip_if_stub()
    from fastapi.testclient import TestClient

    from caramello_api.finances.models import Account  # type: ignore[import-not-found]
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    account_uuid = uuid4()

    # --- Part 1: 401 without authentication ---
    def _exec_401(_stmt):
        r = MagicMock()
        r.first.return_value = None
        r.all.return_value = []
        return r

    mock_session_401 = AsyncMock()
    mock_session_401.execute.side_effect = execute_mock(_exec_401)

    def _session_override_401():
        yield mock_session_401

    # Does not override get_current_user
    app.dependency_overrides[get_session] = _session_override_401
    try:
        client = TestClient(app)
        response = client.get(f"/api/v1/finances/accounts/{account_uuid}/movements")
        assert response.status_code == 401, (
            f"Expected 401 without authentication; got: {response.status_code}. "
            f"Body: {response.text}"
        )
    finally:
        app.dependency_overrides.clear()

    # --- Part 2: 403 for another family ---
    fake_user = _make_fake_user()
    fake_account = Account(
        id=10,
        uuid=account_uuid,
        family_id=1,
        name="Conta Alheia",
        type="corrente",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    call_count_403 = [0]

    def _exec_403(_stmt):
        r = MagicMock()
        call_count_403[0] += 1
        if call_count_403[0] == 1:
            # Resolve Account by uuid
            r.first.return_value = fake_account
        else:
            # Membership check: non-member (no FamilyMember → 403)
            r.first.return_value = None
        r.all.return_value = []
        return r

    mock_session_403 = AsyncMock()
    mock_session_403.execute.side_effect = execute_mock(_exec_403)

    def _session_override_403():
        yield mock_session_403

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override_403
    try:
        client = TestClient(app)
        response = client.get(f"/api/v1/finances/accounts/{account_uuid}/movements")
        # This is the authorization boundary of GET /accounts/{uuid}/movements,
        # shared by test_movement_entry_uuid_field and test_movement_reconciled_filter
        _assert_not_family_member(response)
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Reconciliation endpoint stubs — LAN-01, LAN-02, LAN-03
# ---------------------------------------------------------------------------


def test_reconcile_movement():
    """LAN-01, LAN-04, D-REC-02: POST /finances/movements/{uuid}/reconcile returns 201.

    The response must include the rich schema: uuid, movement, subcategory_uuid,
    competencia_year, is_recorrente.
    Plan 09-04 Task 3: guard removed — endpoint implemented in 09-03.
    """
    from decimal import Decimal

    from fastapi.testclient import TestClient

    from caramello_api.families.models import FamilyMember  # type: ignore[import-not-found]
    from caramello_api.finances.models import (  # type: ignore[import-not-found]
        Account,
        Category,
        FinancialEntry,
        Movement,
        Subcategory,
    )
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    movement_uuid = uuid4()
    entry_uuid = uuid4()
    sub_uuid = uuid4()
    cat_uuid = uuid4()

    fake_movement = Movement(
        id=1,
        uuid=movement_uuid,
        account_id=1,
        date=datetime.now(UTC),
        amount=Decimal("150.00"),
        description="Supermercado",
        import_hash="hash123",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_account = Account(
        id=1,
        uuid=uuid4(),
        family_id=1,
        name="Conta Corrente",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_subcategory = Subcategory(
        id=1,
        uuid=sub_uuid,
        category_id=1,
        name="Supermercado",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_category = Category(
        id=1,
        uuid=cat_uuid,
        family_id=1,
        name="Alimentação",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_member = FamilyMember(
        family_id=1,
        user_id=fake_user.id,
        role="member",
        joined_at=datetime.now(UTC),
    )
    added = []

    # CR-05 fix: counter-based mock — answers in the order of the SINGLE-entity
    # selects (session.execute + .scalars()): 1=Movement, 2=Account,
    # 3=FamilyMember(require_family_access), 4=Subcategory(fallback), 5=Category
    exec_call_count = [0]

    def _exec(stmt):
        r = MagicMock()
        exec_call_count[0] += 1
        n = exec_call_count[0]
        if n == 1:
            r.first.return_value = fake_movement
        elif n == 2:
            r.first.return_value = fake_account
        elif n == 3:
            r.first.return_value = fake_member
        elif n == 4:
            r.first.return_value = fake_subcategory
        elif n == 5:
            r.first.return_value = fake_category
        else:
            r.first.return_value = None
        r.all.return_value = []
        return r

    def _row(stmt):
        r = MagicMock()
        r.fetchone.return_value = None  # forces the per-row Subcategory+Category fallback
        r.fetchall.return_value = []
        r.scalar_one_or_none.return_value = None
        return r

    mock_session = AsyncMock()
    mock_session.execute.side_effect = execute_mock(_exec, _row)
    mock_session.add = MagicMock(side_effect=lambda o: added.append(o))
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock(
        side_effect=refresh_mock(lambda o: setattr(o, "uuid", entry_uuid))
    )
    mock_session.rollback = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.post(
            f"/api/v1/finances/movements/{movement_uuid}/reconcile",
            json={
                "subcategory_uuid": str(sub_uuid),
                "competencia_year": 2026,
                "competencia_month": 5,
                "is_recorrente": False,
            },
        )
        assert response.status_code == 201, response.text
        body = response.json()
        # The whole rich schema is asserted by VALUE, not by key presence: the
        # entry uuid comes from the refresh, and the subcategory/category/movement
        # uuids prove the endpoint resolved the chain it was given instead of
        # echoing the request.
        assert body["uuid"] == str(entry_uuid), body
        assert body["movement"]["uuid"] == str(movement_uuid), body
        assert body["movement"]["description"] == "Supermercado", body
        assert body["subcategory_uuid"] == str(sub_uuid), body
        assert body["subcategory_name"] == "Supermercado", body
        assert body["category_uuid"] == str(cat_uuid), body
        assert body["category_name"] == "Alimentação", body
        assert body["competencia_year"] == 2026, body
        assert body["competencia_month"] == 5, body
        assert body["is_recorrente"] is False, body
        assert body["responsible_user_uuid"] is None, body
        # LAN-01: exactly one FinancialEntry was handed to the session
        entries = [o for o in added if isinstance(o, FinancialEntry)]
        assert len(entries) == 1, added
        assert entries[0].movement_id == fake_movement.id
        assert entries[0].subcategory_id == fake_subcategory.id
    finally:
        app.dependency_overrides.clear()


def test_reconcile_409_duplicate():
    """LAN-02: POST /finances/movements/{uuid}/reconcile returns 409 if already reconciled.

    When session.commit raises IntegrityError, the endpoint must roll back and
    return 409 with an error message (D-REC-01).
    Plan 09-04 Task 3: guard removed — endpoint implemented in 09-03.
    """
    from decimal import Decimal

    from fastapi.testclient import TestClient
    from sqlalchemy.exc import IntegrityError

    from caramello_api.finances.models import (  # type: ignore[import-not-found]
        Account,
        Movement,
    )
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    movement_uuid = uuid4()
    sub_uuid = uuid4()

    fake_movement = Movement(
        id=1,
        uuid=movement_uuid,
        account_id=1,
        date=datetime.now(UTC),
        amount=Decimal("150.00"),
        description="Supermercado",
        import_hash="hash123",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_account = Account(
        id=1,
        uuid=uuid4(),
        family_id=1,
        name="Conta Corrente",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    # Order of the SINGLE-entity selects: 1=Movement, 2=Account, then the
    # membership and the subcategory — the commit fails before any read that
    # matters after that point.
    exec_call_count = [0]

    def _exec(stmt):
        r = MagicMock()
        exec_call_count[0] += 1
        if exec_call_count[0] == 1:
            r.first.return_value = fake_movement
        elif exec_call_count[0] == 2:
            r.first.return_value = fake_account
        else:
            r.first.return_value = MagicMock()
        r.all.return_value = []
        return r

    def _row(stmt):
        r = MagicMock()
        r.fetchone.return_value = None
        return r

    mock_session = AsyncMock()
    mock_session.execute.side_effect = execute_mock(_exec, _row)
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
            f"/api/v1/finances/movements/{movement_uuid}/reconcile",
            json={
                "subcategory_uuid": str(sub_uuid),
                "competencia_year": 2026,
                "competencia_month": 5,
            },
        )
        assert response.status_code == 409, (
            f"A duplicate must return 409; got {response.status_code}: {response.text}"
        )
    finally:
        app.dependency_overrides.clear()


def test_suggest_category():
    """LAN-03, D-CAT-01/02: GET /finances/movements/{uuid}/suggest-category.

    The mocks answer the whole chain the endpoint resolves (movement -> account ->
    membership) plus the two queries the service runs, so the request reaches the
    fuzzy matching instead of bailing out at the first lookup. The suggestions are
    asserted by value: one entry per subcategory (only its best score survives),
    ordered by score descending, and the history row whose description is
    identical to the movement's scores 100.
    """
    from decimal import Decimal

    from fastapi.testclient import TestClient

    from caramello_api.families.models import FamilyMember  # type: ignore[import-not-found]
    from caramello_api.finances.models import (  # type: ignore[import-not-found]
        Account,
        Movement,
    )
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    movement_uuid = uuid4()
    market_sub_uuid = uuid4()
    ride_sub_uuid = uuid4()
    food_cat_uuid = uuid4()
    transport_cat_uuid = uuid4()
    target_description = "Supermercado Pão de Açúcar"

    fake_movement = Movement(
        id=1,
        uuid=movement_uuid,
        account_id=1,
        date=datetime(2026, 5, 10, tzinfo=UTC),
        amount=Decimal("-320.00"),
        description=target_description,
        import_hash="hash-alvo",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_account = Account(
        id=1,
        uuid=uuid4(),
        family_id=1,
        name="Conta Corrente",
        type="corrente",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_member = FamilyMember(
        family_id=1,
        user_id=fake_user.id,
        role="member",
        joined_at=datetime.now(UTC),
    )

    # The family history, in the column order the service's JOIN selects:
    # description, subcategory_id, subcategory_uuid, subcategory_name,
    # category_uuid, category_name. Subcategory 10 shows up twice on purpose —
    # only its highest score may reach the response.
    history = [
        ("Mercado da esquina", 10, market_sub_uuid, "Supermercado", food_cat_uuid, "Alimentação"),
        (target_description, 10, market_sub_uuid, "Supermercado", food_cat_uuid, "Alimentação"),
        (
            "Uber para o aeroporto",
            20,
            ride_sub_uuid,
            "Aplicativo",
            transport_cat_uuid,
            "Transporte",
        ),
    ]

    row_calls = [0]

    def _row(_stmt):
        r = MagicMock()
        row_calls[0] += 1
        # 1st row-group query: the target Movement, read with fetchone()
        # 2nd row-group query: the family history, read with fetchall()
        r.fetchone.return_value = (fake_movement,) if row_calls[0] == 1 else None
        r.fetchall.return_value = history if row_calls[0] == 2 else []
        return r

    mock_session = AsyncMock()
    mock_session.execute.side_effect = execute_mock(
        entity_sequence(fake_movement, fake_account, fake_member), _row
    )
    mock_session.rollback = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.get(f"/api/v1/finances/movements/{movement_uuid}/suggest-category")
        assert response.status_code == 200, response.text
        body = response.json()
        # One suggestion per subcategory, never one per history row
        assert len(body) == 2, body
        assert body[0]["subcategory_uuid"] == str(market_sub_uuid), body
        assert body[0]["subcategory_name"] == "Supermercado", body
        assert body[0]["category_uuid"] == str(food_cat_uuid), body
        assert body[0]["category_name"] == "Alimentação", body
        # D-CAT-02: an identical description scores 100, as an int
        assert body[0]["score"] == 100, body
        assert isinstance(body[0]["score"], int), body
        assert body[1]["subcategory_uuid"] == str(ride_sub_uuid), body
        assert body[1]["subcategory_name"] == "Aplicativo", body
        assert body[1]["category_uuid"] == str(transport_cat_uuid), body
        # D-CAT-01: ordered by score descending
        assert body[0]["score"] > body[1]["score"], body
    finally:
        app.dependency_overrides.clear()


def test_suggest_category_403_non_member():
    """AUTH-FIN-02, T-09-04: suggest-category answers 403 to a non-member (IDOR).

    The movement and its account resolve; the FamilyMember lookup finds nothing,
    which is the only difference from test_suggest_category.
    """
    from decimal import Decimal

    from fastapi.testclient import TestClient

    from caramello_api.finances.models import (  # type: ignore[import-not-found]
        Account,
        Movement,
    )
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    movement_uuid = uuid4()

    fake_movement = Movement(
        id=1,
        uuid=movement_uuid,
        account_id=1,
        date=datetime(2026, 5, 10, tzinfo=UTC),
        amount=Decimal("-320.00"),
        description="Supermercado alheio",
        import_hash="hash-alheio",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_account = Account(
        id=1,
        uuid=uuid4(),
        family_id=99,
        name="Conta Alheia",
        type="corrente",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    mock_session = AsyncMock()
    # No FamilyMember after the account: require_family_access raises 403
    mock_session.execute.side_effect = execute_mock(entity_sequence(fake_movement, fake_account))
    mock_session.rollback = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.get(f"/api/v1/finances/movements/{movement_uuid}/suggest-category")
        _assert_not_family_member(response)
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Entry update stubs — LAN-05, D-ATTR
# ---------------------------------------------------------------------------


def test_update_entry():
    """LAN-05, D-REC-04: PATCH /finances/entries/{uuid} updates a financial entry.

    Updates subcategory_uuid, competencia_year and notes, and returns the rich schema.
    Plan 09-04 Task 3: guard removed — endpoint implemented in 09-03.
    """
    from decimal import Decimal

    from fastapi.testclient import TestClient

    from caramello_api.families.models import FamilyMember  # type: ignore[import-not-found]
    from caramello_api.finances.models import (  # type: ignore[import-not-found]
        Account,
        Category,
        FinancialEntry,
        Movement,
        Subcategory,
    )
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    entry_uuid = uuid4()
    sub_uuid = uuid4()
    cat_uuid = uuid4()

    fake_entry = FinancialEntry(
        id=1,
        uuid=entry_uuid,
        movement_id=1,
        subcategory_id=1,
        competencia_year=2026,
        competencia_month=5,
        notes=None,
        is_recorrente=False,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_movement = Movement(
        id=1,
        uuid=uuid4(),
        account_id=1,
        date=datetime.now(UTC),
        amount=Decimal("100.00"),
        description="Teste",
        import_hash="h1",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_account = Account(
        id=1,
        uuid=uuid4(),
        family_id=1,
        name="Conta",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_subcategory = Subcategory(
        id=1,
        uuid=sub_uuid,
        category_id=1,
        name="Sub Teste",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_category = Category(
        id=1,
        uuid=cat_uuid,
        family_id=1,
        name="Cat Teste",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_member = FamilyMember(
        family_id=1,
        user_id=fake_user.id,
        role="member",
        joined_at=datetime.now(UTC),
    )

    # WR-06: counter-based mock — returns the right object per entity-select order
    # Order: 1=FinancialEntry, 2=Movement(auth), 3=Account, 4=FamilyMember(require_family_access),
    #        5=Subcategory(update), 6=Subcategory(reload after commit), 7=Category(reload)
    exec_call_count = [0]

    def _exec(stmt):
        r = MagicMock()
        exec_call_count[0] += 1
        n = exec_call_count[0]
        if n == 1:
            r.first.return_value = fake_entry
        elif n == 2:
            r.first.return_value = fake_movement
        elif n == 3:
            r.first.return_value = fake_account
        elif n == 4:
            r.first.return_value = fake_member
        elif n == 5 or n == 6:
            r.first.return_value = fake_subcategory
        elif n == 7:
            r.first.return_value = fake_category
        else:
            r.first.return_value = None
        r.all.return_value = []
        return r

    mock_session = AsyncMock()
    mock_session.execute.side_effect = execute_mock(_exec)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock(side_effect=refresh_mock())
    mock_session.rollback = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.patch(
            f"/api/v1/finances/entries/{entry_uuid}",
            json={
                "subcategory_uuid": str(sub_uuid),
                "competencia_year": 2026,
                "notes": "Nota atualizada",
            },
        )
        # WR-06: asserts 200 only and validates the body shape (404 is not a success)
        assert response.status_code == 200, (
            f"Expected 200; got {response.status_code}: {response.text}"
        )
        body = response.json()
        assert body["uuid"] == str(entry_uuid), body
        assert body["subcategory_uuid"] == str(sub_uuid), body
        assert body["subcategory_name"] == "Sub Teste", body
        assert body["category_uuid"] == str(cat_uuid), body
        assert body["category_name"] == "Cat Teste", body
        assert body["competencia_year"] == 2026, body
        # The patched fields reached both the ORM object and the response
        assert body["notes"] == "Nota atualizada", body
        assert fake_entry.notes == "Nota atualizada"
    finally:
        app.dependency_overrides.clear()


def _entry_patch_fixtures(fake_user, responsible_user=None):
    """Build the entry -> movement -> account -> subcategory -> category chain.

    Shared by the PATCH /entries tests: they differ only in what they send and in
    which step of the chain is missing, never in how the chain is shaped.
    `responsible_user` pins the entry's current owner (None = unassigned).
    """
    from decimal import Decimal

    from caramello_api.families.models import FamilyMember  # type: ignore[import-not-found]
    from caramello_api.finances.models import (  # type: ignore[import-not-found]
        Account,
        Category,
        FinancialEntry,
        Movement,
        Subcategory,
    )

    entry = FinancialEntry(
        id=1,
        uuid=uuid4(),
        movement_id=1,
        subcategory_id=1,
        competencia_year=2026,
        competencia_month=5,
        notes=None,
        is_recorrente=False,
        responsible_user_id=None if responsible_user is None else responsible_user.id,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    movement = Movement(
        id=1,
        uuid=uuid4(),
        account_id=1,
        date=datetime(2026, 5, 4, tzinfo=UTC),
        amount=Decimal("-89.90"),
        description="Farmácia",
        import_hash="hash-lancamento",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    account = Account(
        id=1,
        uuid=uuid4(),
        family_id=1,
        name="Conta Corrente",
        type="corrente",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    subcategory = Subcategory(
        id=1,
        uuid=uuid4(),
        category_id=1,
        name="Medicamentos",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    category = Category(
        id=1,
        uuid=uuid4(),
        family_id=1,
        name="Saúde",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    member = FamilyMember(
        family_id=1,
        user_id=fake_user.id,
        role="member",
        joined_at=datetime.now(UTC),
    )
    return entry, movement, account, subcategory, category, member


def test_entry_responsible_user_uuid():
    """D-ATTR-01/02, D-REC-04: PATCH entries/{uuid} round-trips responsible_user_uuid.

    Two requests, one mocked session each, both reaching the endpoint's logic:

      - responsible_user_uuid=<uuid> assigns the owner — the response carries the
        member's public UUID and the ORM object received the internal id.
      - responsible_user_uuid=null clears it (the model_fields_set sentinel of
        pitfall P2) — the response carries null and the internal id is gone.
    """
    from fastapi.testclient import TestClient

    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    responsible_user = _make_fake_user(user_id=77)

    # --- Part 1: assigning a responsible member ---
    entry, movement, account, subcategory, category, member = _entry_patch_fixtures(fake_user)

    mock_session = AsyncMock()
    # Entity selects, in order: entry, movement (auth), account, FamilyMember
    # (require_family_access), the responsible User, its FamilyMember (D-ATTR-02),
    # then the subcategory/category/User reloaded for the rich schema.
    mock_session.execute.side_effect = execute_mock(
        entity_sequence(
            entry,
            movement,
            account,
            member,
            responsible_user,
            member,
            subcategory,
            category,
            responsible_user,
        )
    )
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock(side_effect=refresh_mock())
    mock_session.rollback = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.patch(
            f"/api/v1/finances/entries/{entry.uuid}",
            json={"responsible_user_uuid": str(responsible_user.uuid)},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["uuid"] == str(entry.uuid), body
        assert body["responsible_user_uuid"] == str(responsible_user.uuid), body
        # D-ATTR-01: the UUID was resolved to the internal id on the way in
        assert entry.responsible_user_id == responsible_user.id
        # The rest of the rich schema still describes the entry it patched
        assert body["movement"]["uuid"] == str(movement.uuid), body
        assert body["subcategory_uuid"] == str(subcategory.uuid), body
        assert body["category_uuid"] == str(category.uuid), body
    finally:
        app.dependency_overrides.clear()

    # --- Part 2: clearing it with an explicit null ---
    owned_entry, movement, account, subcategory, category, member = _entry_patch_fixtures(
        fake_user, responsible_user=responsible_user
    )
    assert owned_entry.responsible_user_id == responsible_user.id, "precondition"

    mock_session_null = AsyncMock()
    # No User lookup this time: null clears the field without resolving anything
    mock_session_null.execute.side_effect = execute_mock(
        entity_sequence(owned_entry, movement, account, member, subcategory, category)
    )
    mock_session_null.add = MagicMock()
    mock_session_null.commit = AsyncMock()
    mock_session_null.refresh = AsyncMock(side_effect=refresh_mock())
    mock_session_null.rollback = AsyncMock()

    def _session_override_null():
        yield mock_session_null

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override_null
    try:
        client = TestClient(app)
        response_null = client.patch(
            f"/api/v1/finances/entries/{owned_entry.uuid}",
            json={"responsible_user_uuid": None},
        )
        assert response_null.status_code == 200, response_null.text
        body_null = response_null.json()
        assert body_null["responsible_user_uuid"] is None, body_null
        assert owned_entry.responsible_user_id is None
    finally:
        app.dependency_overrides.clear()


def test_update_entry_403_non_member():
    """AUTH-FIN-02, T-09-04: PATCH /finances/entries/{uuid} answers 403 to a non-member.

    The entry, its movement and its account resolve (CR-01's chain); the
    FamilyMember lookup finds nothing.
    """
    from fastapi.testclient import TestClient

    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    entry, movement, account, _sub, _cat, _member = _entry_patch_fixtures(fake_user)

    mock_session = AsyncMock()
    mock_session.execute.side_effect = execute_mock(entity_sequence(entry, movement, account))
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock(side_effect=refresh_mock())
    mock_session.rollback = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.patch(
            f"/api/v1/finances/entries/{entry.uuid}",
            json={"notes": "Tentativa de outra família"},
        )
        _assert_not_family_member(response)
        # A rejected request must not have written anything
        mock_session.commit.assert_not_called()
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Balance stubs — REL-01, REL-02
# ---------------------------------------------------------------------------


def _fake_family(family_uuid, family_id: int = 1, name: str = "Familia Teste"):
    """Build a Family the balance and report tests resolve their UUID to."""
    from caramello_api.families.models import Family  # type: ignore[import-not-found]

    return Family(
        id=family_id,
        uuid=family_uuid,
        name=name,
        description=None,
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _fake_member(fake_user, family_id: int = 1):
    """Build the FamilyMember that makes require_family_access let the caller in."""
    from caramello_api.families.models import FamilyMember  # type: ignore[import-not-found]

    return FamilyMember(
        family_id=family_id,
        user_id=fake_user.id,
        role="member",
        joined_at=datetime.now(UTC),
    )


def _sum_for_account(balances):
    """Row handler answering each SUM(movement.amount) with its account's figure.

    The account being summed is read back out of the compiled WHERE, so a handler
    that mixed the accounts up — or an endpoint that summed the wrong one — shows
    up as a wrong balance instead of a passing test. An account absent from
    `balances` answers None, which is the empty SUM of pitfall P6.
    """

    def _row(stmt):
        sql = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        total = next(
            (
                value
                for acc_id, value in balances.items()
                if f"movement.account_id = {acc_id}" in sql
            ),
            None,
        )
        r = MagicMock()
        r.scalar_one_or_none.return_value = total
        return r

    return _row


def test_account_balance():
    """REL-01, D-BAL-01: GET /finances/accounts/{uuid}/balance returns the balance.

    The mocked SUM answers only for account 7, which is the account the URL
    resolves to, so the asserted figure proves the endpoint summed that account
    and returned what the service computed.
    """
    from decimal import Decimal

    from fastapi.testclient import TestClient

    from caramello_api.finances.models import Account  # type: ignore[import-not-found]
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    account_uuid = uuid4()

    fake_account = Account(
        id=7,
        uuid=account_uuid,
        family_id=1,
        name="Conta Corrente",
        type="corrente",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    mock_session = AsyncMock()
    mock_session.execute.side_effect = execute_mock(
        entity_sequence(fake_account, _fake_member(fake_user)),
        _sum_for_account({7: Decimal("1234.56")}),
    )
    mock_session.rollback = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.get(f"/api/v1/finances/accounts/{account_uuid}/balance")
        assert response.status_code == 200, response.text
        # D-BAL-01: the whole body, by value — money crosses the wire as a string
        assert response.json() == {
            "account_uuid": str(account_uuid),
            "balance": "1234.56",
            "currency": "BRL",
        }, response.text
    finally:
        app.dependency_overrides.clear()


def test_account_balance_403_non_member():
    """AUTH-FIN-02, T-09-04: the account balance answers 403 to a non-member."""
    from fastapi.testclient import TestClient

    from caramello_api.finances.models import Account  # type: ignore[import-not-found]
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    account_uuid = uuid4()

    fake_account = Account(
        id=7,
        uuid=account_uuid,
        family_id=99,
        name="Conta Alheia",
        type="corrente",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    mock_session = AsyncMock()
    mock_session.execute.side_effect = execute_mock(entity_sequence(fake_account))
    mock_session.rollback = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.get(f"/api/v1/finances/accounts/{account_uuid}/balance")
        _assert_not_family_member(response)
    finally:
        app.dependency_overrides.clear()


def test_family_balance():
    """REL-02, D-BAL-02: GET /finances/families/{uuid}/balance consolidates the accounts.

    Two accounts with different balances, one of them negative: the response must
    carry each account's own figure and their sum as total_balance.
    """
    from decimal import Decimal

    from fastapi.testclient import TestClient

    from caramello_api.finances.models import Account  # type: ignore[import-not-found]
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    family_uuid = uuid4()
    checking_uuid = uuid4()
    card_uuid = uuid4()

    fake_accounts = [
        Account(
            id=7,
            uuid=checking_uuid,
            family_id=1,
            name="Conta Corrente",
            type="corrente",
            currency="BRL",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        ),
        Account(
            id=8,
            uuid=card_uuid,
            family_id=1,
            name="Cartão de Crédito",
            type="cartao",
            currency="BRL",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        ),
    ]

    mock_session = AsyncMock()
    mock_session.execute.side_effect = execute_mock(
        entity_sequence(_fake_family(family_uuid), _fake_member(fake_user), fake_accounts),
        _sum_for_account({7: Decimal("100.50"), 8: Decimal("-25.25")}),
    )
    mock_session.rollback = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.get(f"/api/v1/finances/families/{family_uuid}/balance")
        assert response.status_code == 200, response.text
        assert response.json() == {
            "family_uuid": str(family_uuid),
            "total_balance": "75.25",
            "accounts": [
                {
                    "account_uuid": str(checking_uuid),
                    "name": "Conta Corrente",
                    "currency": "BRL",
                    "balance": "100.50",
                },
                {
                    "account_uuid": str(card_uuid),
                    "name": "Cartão de Crédito",
                    "currency": "BRL",
                    "balance": "-25.25",
                },
            ],
        }, response.text
    finally:
        app.dependency_overrides.clear()


def test_family_balance_403_non_member():
    """AUTH-FIN-02, T-09-04: the family balance answers 403 to a non-member."""
    from fastapi.testclient import TestClient

    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    family_uuid = uuid4()

    mock_session = AsyncMock()
    # The family exists; the caller is not one of its members
    mock_session.execute.side_effect = execute_mock(
        entity_sequence(_fake_family(family_uuid, name="Familia Alheia"))
    )
    mock_session.rollback = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.get(f"/api/v1/finances/families/{family_uuid}/balance")
        _assert_not_family_member(response)
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Report stubs — REL-03, REL-04, REL-05
# ---------------------------------------------------------------------------


def _monthly_report_rows(*rows):
    """Row handler answering the report's aggregate only for competência 2026-05.

    The GROUP BY runs inside the mocked session, so the stand-in plays the part
    the database would: it hands the rows over only when the compiled query is
    the one D-REP-03 requires — filtered by FinancialEntry.competencia_year/month.
    A report grouped by Movement.date instead comes back empty, which is what
    makes this test able to fail.
    """
    recorded: list[str] = []

    def _row(stmt):
        sql = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        recorded.append(sql)
        by_competencia = (
            "financial_entry.competencia_year = 2026" in sql
            and "financial_entry.competencia_month = 5" in sql
        )
        r = MagicMock()
        r.fetchall.return_value = list(rows) if by_competencia else []
        return r

    return _row, recorded


def test_monthly_report():
    """REL-03/04, D-REP-01/03: GET /finances/reports/monthly returns the breakdown.

    Two subcategory rows go in and the response is asserted whole: the period
    echoed back, both rows by value, and `total` as the sum of their totals.
    """
    from decimal import Decimal

    from fastapi.testclient import TestClient

    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    family_uuid = uuid4()
    food_cat_uuid = uuid4()
    market_sub_uuid = uuid4()
    transport_cat_uuid = uuid4()
    fuel_sub_uuid = uuid4()

    # Rows as monthly_breakdown reads them: named attributes off a GROUP BY Row
    market_row = MagicMock(
        category_uuid=food_cat_uuid,
        category_name="Alimentação",
        subcategory_uuid=market_sub_uuid,
        subcategory_name="Supermercado",
        total=Decimal("300.00"),
        count=5,
    )
    fuel_row = MagicMock(
        category_uuid=transport_cat_uuid,
        category_name="Transporte",
        subcategory_uuid=fuel_sub_uuid,
        subcategory_name="Combustível",
        total=Decimal("150.75"),
        count=2,
    )
    row_handler, recorded_sql = _monthly_report_rows(market_row, fuel_row)

    mock_session = AsyncMock()
    mock_session.execute.side_effect = execute_mock(
        entity_sequence(_fake_family(family_uuid), _fake_member(fake_user)), row_handler
    )
    mock_session.rollback = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.get(
            "/api/v1/finances/reports/monthly",
            params={"family_uuid": str(family_uuid), "year": 2026, "month": 5},
        )
        assert response.status_code == 200, response.text
        assert response.json() == {
            "period": {"year": 2026, "month": 5},
            "total": "450.75",
            "rows": [
                {
                    "category_uuid": str(food_cat_uuid),
                    "category_name": "Alimentação",
                    "subcategory_uuid": str(market_sub_uuid),
                    "subcategory_name": "Supermercado",
                    "total": "300.00",
                    "count": 5,
                },
                {
                    "category_uuid": str(transport_cat_uuid),
                    "category_name": "Transporte",
                    "subcategory_uuid": str(fuel_sub_uuid),
                    "subcategory_name": "Combustível",
                    "total": "150.75",
                    "count": 2,
                },
            ],
        }, response.text
        # D-REP-04: one aggregate query, with func.sum and a GROUP BY
        assert len(recorded_sql) == 1, recorded_sql
        assert "sum(movement.amount)" in recorded_sql[0], recorded_sql[0]
        assert "GROUP BY" in recorded_sql[0], recorded_sql[0]
    finally:
        app.dependency_overrides.clear()


def test_monthly_report_403_non_member():
    """AUTH-FIN-02, T-09-04: the monthly report answers 403 to a non-member."""
    from fastapi.testclient import TestClient

    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    family_uuid = uuid4()

    mock_session = AsyncMock()
    mock_session.execute.side_effect = execute_mock(
        entity_sequence(_fake_family(family_uuid, name="Familia Alheia"))
    )
    mock_session.rollback = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.get(
            "/api/v1/finances/reports/monthly",
            params={"family_uuid": str(family_uuid), "year": 2026, "month": 5},
        )
        _assert_not_family_member(response)
    finally:
        app.dependency_overrides.clear()


def test_report_uses_competencia():
    """REL-05, D-REP-03: the report groups by accrual period, not by Movement.date.

    The year/month query params must reach the aggregate as
    FinancialEntry.competencia_year/competencia_month. The compiled statement is
    what proves it: a report that filtered on the movement date would satisfy the
    response shape just as well.
    """
    from fastapi.testclient import TestClient

    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    family_uuid = uuid4()
    recorded_sql: list[str] = []

    def _row(stmt):
        recorded_sql.append(str(stmt.compile(compile_kwargs={"literal_binds": True})))
        r = MagicMock()
        r.fetchall.return_value = []
        return r

    mock_session = AsyncMock()
    mock_session.execute.side_effect = execute_mock(
        entity_sequence(_fake_family(family_uuid), _fake_member(fake_user)), _row
    )
    mock_session.rollback = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        # Accrual-period params (year/month) — not movement-date params
        response = client.get(
            "/api/v1/finances/reports/monthly",
            params={"family_uuid": str(family_uuid), "year": 2026, "month": 3},
        )
        assert response.status_code == 200, response.text
        assert response.json()["period"] == {"year": 2026, "month": 3}, response.text
        assert len(recorded_sql) == 1, recorded_sql
        sql = recorded_sql[0]
        assert "financial_entry.competencia_year = 2026" in sql, sql
        assert "financial_entry.competencia_month = 3" in sql, sql
        # REL-05: the movement date is joined for its amount, never filtered on
        assert "movement.date" not in sql, sql
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Movement stubs — D-MOV-01, D-MOV-02
# ---------------------------------------------------------------------------


def _movement_listing_fixtures(account_uuid, fake_user):
    """Build the account plus one reconciled and one pending movement.

    Returns (account, member, reconciled_row, pending_row), where each row is the
    (Movement, entry_uuid) pair the LEFT JOIN of D-MOV-01 hands back.
    """
    from decimal import Decimal

    from caramello_api.finances.models import Account, Movement  # type: ignore[import-not-found]

    account = Account(
        id=1,
        uuid=account_uuid,
        family_id=1,
        name="Conta Corrente",
        type="corrente",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    reconciled_movement = Movement(
        id=1,
        uuid=uuid4(),
        account_id=1,
        date=datetime(2026, 5, 12, tzinfo=UTC),
        amount=Decimal("-89.90"),
        description="Farmácia",
        import_hash="hash-conciliado",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    pending_movement = Movement(
        id=2,
        uuid=uuid4(),
        account_id=1,
        date=datetime(2026, 5, 11, tzinfo=UTC),
        amount=Decimal("250.00"),
        description="Transferência recebida",
        import_hash="hash-pendente",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    return (
        account,
        _fake_member(fake_user),
        (reconciled_movement, uuid4()),
        (pending_movement, None),
    )


def _movement_rows_handler(rows):
    """Row handler applying the D-MOV-02 filter the way the database would.

    The IS NULL / IS NOT NULL predicate lives in the SQL, so a mock that ignored
    it would answer the same three lists for the three different requests. This
    stand-in reads the predicate back out of the compiled statement and filters
    accordingly — dropping the WHERE from the endpoint then changes the response.
    """

    def _row(stmt):
        sql = str(stmt)
        selected = rows
        if "financial_entry.id IS NOT NULL" in sql:
            selected = [row for row in rows if row[1] is not None]
        elif "financial_entry.id IS NULL" in sql:
            selected = [row for row in rows if row[1] is None]
        r = MagicMock()
        r.fetchall.return_value = selected
        return r

    return _row


def test_movement_entry_uuid_field():
    """D-MOV-01: GET movements carries entry_uuid, populated only when reconciled.

    Two movements come back from the LEFT JOIN: one carrying the uuid of its
    FinancialEntry, one with none. Both are asserted by value — a handler that
    stopped reading the join's second column would answer null for both.
    """
    from fastapi.testclient import TestClient

    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    account_uuid = uuid4()
    account, member, reconciled_row, pending_row = _movement_listing_fixtures(
        account_uuid, fake_user
    )

    mock_session = AsyncMock()
    mock_session.execute.side_effect = execute_mock(
        entity_sequence(account, member),
        _movement_rows_handler([reconciled_row, pending_row]),
    )
    mock_session.rollback = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.get(f"/api/v1/finances/accounts/{account_uuid}/movements")
        assert response.status_code == 200, response.text
        body = response.json()
        assert len(body) == 2, body
        reconciled_movement, entry_uuid = reconciled_row
        pending_movement, _none = pending_row
        assert body[0]["uuid"] == str(reconciled_movement.uuid), body
        assert body[0]["description"] == "Farmácia", body
        assert body[0]["amount"] == "-89.90", body
        # D-MOV-01: a reconciled movement carries its entry's uuid
        assert body[0]["entry_uuid"] == str(entry_uuid), body
        assert body[1]["uuid"] == str(pending_movement.uuid), body
        assert body[1]["description"] == "Transferência recebida", body
        # ...and a pending one carries null
        assert body[1]["entry_uuid"] is None, body
    finally:
        app.dependency_overrides.clear()


def test_movement_reconciled_filter():
    """D-MOV-02: ?reconciled= filters the listing through the LEFT JOIN.

    The same two movements (one reconciled, one pending) are asked for three
    ways. Each request must answer a different list, which is what tells a real
    filter apart from a parameter the endpoint merely accepts.
    """
    from fastapi.testclient import TestClient

    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    account_uuid = uuid4()
    account, member, reconciled_row, pending_row = _movement_listing_fixtures(
        account_uuid, fake_user
    )
    rows = [reconciled_row, pending_row]

    def _session_override():
        # A fresh session per request: the entity sequence is consumed by each
        # one, exactly as it would be by three separate HTTP calls in production.
        mock_session = AsyncMock()
        mock_session.execute.side_effect = execute_mock(
            entity_sequence(account, member), _movement_rows_handler(rows)
        )
        mock_session.rollback = AsyncMock()
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        url = f"/api/v1/finances/accounts/{account_uuid}/movements"

        # No filter: both movements
        unfiltered = client.get(url)
        assert unfiltered.status_code == 200, unfiltered.text
        assert [item["uuid"] for item in unfiltered.json()] == [
            str(reconciled_row[0].uuid),
            str(pending_row[0].uuid),
        ], unfiltered.text

        # reconciled=false: only the movement with no entry
        pending = client.get(url, params={"reconciled": "false"})
        assert pending.status_code == 200, pending.text
        assert [item["uuid"] for item in pending.json()] == [str(pending_row[0].uuid)], pending.text
        assert pending.json()[0]["entry_uuid"] is None, pending.text

        # reconciled=true: only the movement carrying an entry
        done = client.get(url, params={"reconciled": "true"})
        assert done.status_code == 200, done.text
        assert [item["uuid"] for item in done.json()] == [str(reconciled_row[0].uuid)], done.text
        assert done.json()[0]["entry_uuid"] == str(reconciled_row[1]), done.text
    finally:
        app.dependency_overrides.clear()

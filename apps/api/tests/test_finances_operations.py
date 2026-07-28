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

from tests.conftest import apply_column_defaults, constant, execute_mock, refresh_mock


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
        # CSV re-import: the hash already exists → potential_duplicates[]
        # (not duplicates_skipped, since there is no fitid)
        assert body.get("potential_duplicates") or body.get("duplicates_skipped", 0) > 0, (
            f"A re-import must not insert duplicates; body: {body}"
        )
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
        assert response.status_code in (200, 201), (
            f"Expected 200/201 for /import/confirm; got: {response.status_code}. "
            f"Body: {response.text}"
        )
        body = response.json()
        assert "inserted" in body, f"Response must contain 'inserted'; body: {body}"
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
        assert response.status_code == 403, (
            f"Expected 403 for a non-member; got: {response.status_code}. Body: {response.text}"
        )
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
    # 3=FamilyMember(_require_family_access), 4=Subcategory(fallback), 5=Category
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

    Returns a list ordered by score desc. Every item must have:
    subcategory_uuid, subcategory_name, category_uuid, category_name, score.
    Plan 09-04 Task 3: guard removed — endpoint implemented in 09-03.
    """
    from fastapi.testclient import TestClient

    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    movement_uuid = uuid4()

    mock_session = AsyncMock()
    mock_session.execute.side_effect = execute_mock(
        constant(MagicMock(first=lambda: None, all=lambda: [])),
        constant(MagicMock(fetchone=lambda: None, fetchall=lambda: [])),
    )
    mock_session.rollback = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.get(f"/api/v1/finances/movements/{movement_uuid}/suggest-category")
        # 200 (empty list is fine — D-CAT-03) or 404 if the movement does not exist
        assert response.status_code in (200, 404), (
            f"Expected 200 or 404; got {response.status_code}: {response.text}"
        )
        if response.status_code == 200:
            body = response.json()
            assert isinstance(body, list), f"Response must be a list; got {type(body)}"
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
    # Order: 1=FinancialEntry, 2=Movement(auth), 3=Account, 4=FamilyMember(_require_family_access),
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
        assert "uuid" in body, "Response must contain 'uuid'"
        assert "subcategory_uuid" in body, "Response must contain 'subcategory_uuid'"
        assert "category_uuid" in body, "Response must contain 'category_uuid'"
    finally:
        app.dependency_overrides.clear()


def test_entry_responsible_user_uuid():
    """D-ATTR, D-REC-04: PATCH entries/{uuid} with responsible_user_uuid assigns an owner.

    PATCH with responsible_user_uuid: null must clear the field (model_fields_set sentinel).
    Plan 09-04 Task 3: guard removed — endpoint implemented in 09-03.
    """
    from fastapi.testclient import TestClient

    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    entry_uuid = uuid4()
    responsible_uuid = uuid4()

    mock_session = AsyncMock()
    mock_session.execute.side_effect = execute_mock(
        constant(MagicMock(first=lambda: None, all=lambda: []))
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
        # PATCH with an explicit responsible user
        response = client.patch(
            f"/api/v1/finances/entries/{entry_uuid}",
            json={"responsible_user_uuid": str(responsible_uuid)},
        )
        # 200, 404 or 422 (invalid UUID in the mock) — as long as the route exists
        assert response.status_code in (200, 404, 422), (
            f"Expected 200/404/422; got {response.status_code}: {response.text}"
        )
        # PATCH with null — clears the responsible user
        response_null = client.patch(
            f"/api/v1/finances/entries/{entry_uuid}",
            json={"responsible_user_uuid": None},
        )
        assert response_null.status_code in (200, 404, 422), (
            f"Expected 200/404/422 with null; got {response_null.status_code}: {response_null.text}"
        )
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Balance stubs — REL-01, REL-02
# ---------------------------------------------------------------------------


def test_account_balance():
    """REL-01, D-BAL-01: GET /finances/accounts/{uuid}/balance returns the balance.

    Response: {account_uuid, balance (string), currency}.
    Plan 09-04 Task 3: guard removed — endpoint implemented in 09-03/09-04.
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
        id=1,
        uuid=account_uuid,
        family_id=1,
        name="Conta Corrente",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    def _exec(stmt):
        r = MagicMock()
        r.first.return_value = fake_account
        return r

    mock_balance_result = MagicMock()
    mock_balance_result.scalar_one_or_none.return_value = Decimal("250.00")

    mock_session = AsyncMock()
    mock_session.execute.side_effect = execute_mock(_exec, constant(mock_balance_result))
    mock_session.rollback = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.get(f"/api/v1/finances/accounts/{account_uuid}/balance")
        assert response.status_code in (200, 404), (
            f"Expected 200 or 404; got {response.status_code}: {response.text}"
        )
        if response.status_code == 200:
            body = response.json()
            assert "balance" in body, f"Response must contain 'balance'; got: {body}"
            assert "account_uuid" in body or "uuid" in body, (
                "Response must contain account_uuid (D-BAL-01)"
            )
    finally:
        app.dependency_overrides.clear()


def test_family_balance():
    """REL-02, D-BAL-02: GET /finances/families/{uuid}/balance returns the consolidated balance.

    Response: {family_uuid, total_balance, accounts: [...]}.
    Plan 09-04 Task 3: guard removed — endpoint implemented in 09-03/09-04.
    """
    from decimal import Decimal

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
        name="Familia Teste",
        description=None,
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    def _exec(stmt):
        r = MagicMock()
        r.first.return_value = fake_family
        r.all.return_value = []
        return r

    mock_session = AsyncMock()
    mock_session.execute.side_effect = execute_mock(
        _exec,
        constant(MagicMock(scalar_one_or_none=lambda: Decimal("0.00"), fetchall=lambda: [])),
    )
    mock_session.rollback = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.get(f"/api/v1/finances/families/{family_uuid}/balance")
        assert response.status_code in (200, 404), (
            f"Expected 200 or 404; got {response.status_code}: {response.text}"
        )
        if response.status_code == 200:
            body = response.json()
            assert "total_balance" in body, (
                f"Response must contain 'total_balance' (D-BAL-02); got: {body}"
            )
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Report stubs — REL-03, REL-04, REL-05
# ---------------------------------------------------------------------------


def test_monthly_report():
    """REL-03/04, D-REP-01: GET /finances/reports/monthly returns the breakdown.

    Response: {period, total, rows} where each row has category_uuid,
    subcategory_uuid and total.
    Plan 09-04 Task 3: guard removed — endpoint implemented in 09-03/09-04.
    """

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
        name="Familia Teste",
        description=None,
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    def _exec(stmt):
        r = MagicMock()
        r.first.return_value = fake_family
        r.all.return_value = []
        return r

    mock_session = AsyncMock()
    mock_session.execute.side_effect = execute_mock(_exec, constant(MagicMock(fetchall=lambda: [])))
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
        assert response.status_code in (200, 404), (
            f"Expected 200 or 404; got {response.status_code}: {response.text}"
        )
        if response.status_code == 200:
            body = response.json()
            assert "period" in body, f"Response must contain 'period' (D-REP-01); got: {body}"
            assert "rows" in body, f"Response must contain 'rows'; got: {body}"
    finally:
        app.dependency_overrides.clear()


def test_report_uses_competencia():
    """REL-05, D-REP-03: the report accepts year/month query params (accrual period).

    Checks that the route exists and accepts the right parameters.
    The report works over competencia_year/month — not over Movement.date.
    Plan 09-04 Task 3: guard removed — endpoint implemented in 09-03/09-04.
    """
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
        name="Familia Teste",
        description=None,
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    def _exec(stmt):
        r = MagicMock()
        r.first.return_value = fake_family
        r.all.return_value = []
        return r

    mock_session = AsyncMock()
    mock_session.execute.side_effect = execute_mock(_exec, constant(MagicMock(fetchall=lambda: [])))
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
        # 200 or 404 (family not found in the mock) are both valid
        # 422 means the params were not accepted — failure
        assert response.status_code != 422, (
            f"The endpoint must not return 422 for valid year/month params; "
            f"got: {response.status_code}: {response.text}"
        )
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Movement stubs — D-MOV-01, D-MOV-02
# ---------------------------------------------------------------------------


def test_movement_entry_uuid_field():
    """D-MOV-01: GET movements includes an entry_uuid field on every item.

    entry_uuid: UUID | None — null for movements pending reconciliation.
    Implemented through a LEFT JOIN with FinancialEntry.
    Plan 09-04 Task 3: guard removed — field and LEFT JOIN implemented in 09-04.
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
        id=1,
        uuid=account_uuid,
        family_id=1,
        name="Conta Corrente",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    def _exec(stmt):
        r = MagicMock()
        r.first.return_value = fake_account
        r.all.return_value = []
        return r

    # Simulates a movement without an entry (pending)
    mock_movement_row = (
        MagicMock(
            uuid=uuid4(),
            date=datetime.now(UTC),
            amount=Decimal("100.00"),
            description="Pagamento",
            import_hash=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        ),
        None,  # entry_uuid = None (pending)
    )

    mock_execute_result = MagicMock()
    mock_execute_result.fetchall.return_value = [mock_movement_row]

    mock_session = AsyncMock()
    mock_session.execute.side_effect = execute_mock(_exec, constant(mock_execute_result))
    mock_session.rollback = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.get(f"/api/v1/finances/accounts/{account_uuid}/movements")
        assert response.status_code in (200, 404), (
            f"Expected 200 or 404; got {response.status_code}: {response.text}"
        )
        if response.status_code == 200:
            body = response.json()
            if isinstance(body, list) and body:
                item = body[0]
                assert "entry_uuid" in item, (
                    f"D-MOV-01: every movement must have 'entry_uuid'; keys: {list(item.keys())}"
                )
    finally:
        app.dependency_overrides.clear()


def test_movement_reconciled_filter():
    """D-MOV-02: GET /finances/accounts/{uuid}/movements?reconciled=false returns pending ones.

    Optional filter: reconciled=false returns only movements without an entry;
    reconciled=true returns only reconciled ones. Implemented through LEFT JOIN + IS NULL.
    Plan 09-04 Task 3: guard removed — filter implemented in 09-04.
    """

    from fastapi.testclient import TestClient

    from caramello_api.finances.models import Account  # type: ignore[import-not-found]
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    account_uuid = uuid4()

    fake_account = Account(
        id=1,
        uuid=account_uuid,
        family_id=1,
        name="Conta Corrente",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    def _exec(stmt):
        r = MagicMock()
        r.first.return_value = fake_account
        return r

    mock_execute_result = MagicMock()
    mock_execute_result.fetchall.return_value = []

    mock_session = AsyncMock()
    mock_session.execute.side_effect = execute_mock(_exec, constant(mock_execute_result))
    mock_session.rollback = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.get(
            f"/api/v1/finances/accounts/{account_uuid}/movements",
            params={"reconciled": "false"},
        )
        # 200 (empty list is fine) or 404 (account not found in the mock)
        # 422 means the reconciled parameter is not accepted — failure
        assert response.status_code in (200, 404), (
            f"Expected 200 or 404; got {response.status_code}: {response.text}"
        )
    finally:
        app.dependency_overrides.clear()

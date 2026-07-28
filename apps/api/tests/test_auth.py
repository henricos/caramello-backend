"""Tests for shared/auth.py — the authorization boundary.

Strategy: the 401-without-a-token cases use TestClient directly. The cases that
depend on a real database are marked `@pytest.mark.integration` and mock through
app.dependency_overrides until an isolated test database exists.

The tests for the two authorization layers (e-mail allowlist and family
membership) call `get_current_user` directly with a mocked session: what is
under test is the ORDER of the checks — in particular that no database query
happens before the token is considered trustworthy.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

CREDENTIALS = HTTPAuthorizationCredentials(scheme="Bearer", credentials="fake.token.value")


def _entity_results(*values):
    """`execute_mock` handler that answers `.scalars().first()` in sequence."""
    remaining = iter(values)

    def _handler(_stmt):
        result = MagicMock()
        try:
            result.first.return_value = next(remaining)
        except StopIteration:
            result.first.return_value = None
        return result

    return _handler


def _call_get_current_user(session, payload):
    """Runs `get_current_user` with the JWKS and the JWT decode mocked out."""
    from caramello_api.shared import auth as auth_module

    with (
        patch.object(auth_module, "_jwks_cache", {"fake-kid": object()}),
        patch.object(auth_module.jwt, "get_unverified_header", return_value={"kid": "fake-kid"}),
        patch.object(auth_module.jwt, "decode", return_value=payload),
    ):
        return asyncio.run(auth_module.get_current_user(credentials=CREDENTIALS, session=session))


def test_auth_module():
    """get_current_user is importable from caramello.shared.auth."""
    from caramello_api.shared.auth import (
        fetch_jwks,  # noqa: F401
        get_current_user,  # noqa: F401
    )


def test_me_unauthenticated(client):
    """A missing credential is 401 with a reason, never the bare 403.

    `shared/auth.py` wraps `HTTPBearer` precisely to avoid FastAPI's default 403:
    a missing credential is "unauthenticated", so it must carry
    `WWW-Authenticate` and tell the caller where to authenticate. Accepting
    either status here would let that wrapper be removed without a test failing.
    """
    response = client.get("/api/v1/users/me")
    assert response.status_code == 401, response.text
    assert response.json()["detail"]["reason"] == "missing_token"
    assert "WWW-Authenticate" in response.headers


def test_user_crud_requires_auth(client):
    """The generated CRUD is behind the same boundary, with the same status."""
    response = client.get("/api/v1/users/user/")
    assert response.status_code == 401, response.text
    assert response.json()["detail"]["reason"] == "missing_token"


@pytest.mark.integration
def test_jit_provisioning():
    """The first request with a valid token creates a row in the users table.

    Note: this test is marked @pytest.mark.integration because it depends on a
    real database configured through .env. Until an isolated test database
    exists it only runs locally against a real database and Keycloak.
    """
    pytest.skip(
        "Requires a real Keycloak and a PostgreSQL database configured through .env "
        "(run manually by the operator; an isolated test database does not exist yet)"
    )


def test_jwt_decode_only_accepts_rs256():
    """The token signature algorithm is pinned: no downgrade, and never 'none'."""
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[1]
    auth_src = (repo_root / "src/caramello_api/shared/auth.py").read_text()
    assert 'algorithms=["RS256"]' in auth_src or "algorithms=['RS256']" in auth_src, (
        "shared/auth.py must restrict algorithms=['RS256'] explicitly"
    )
    assert '"none"' not in auth_src.lower().replace("'none'", '"none"'), (
        "shared/auth.py must not accept the 'none' algorithm"
    )


def test_auto_join_on_login():
    """get_current_user auto-joins when a pending FamilyInvitation exists.

    Skips while src/caramello_api/families/models.py does not exist.
    Once it does, it validates the behaviour through a mocked session:
    - FamilyMember(role="member") is created for the invitation's family
    - invitation.status is marked as "joined"
    """
    pytest.importorskip("caramello_api.families.models")

    from caramello_api.families.models import FamilyInvitation, FamilyMember
    from caramello_api.shared.models import AllowedEmail
    from tests.conftest import execute_mock

    # Build a simulated pending_login FamilyInvitation
    pending_inv = FamilyInvitation(
        id=1,
        family_id=99,
        inviter_id=1,
        email="recem@example.com",
        status="pending_login",
    )

    try:
        from caramello_api.users.models import User  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        from caramello_api.user.models import User  # type: ignore[no-redef]

    provisioned_user = User(
        id=50,
        idp_sub="kc-sub-recem",
        email="recem@example.com",
        name="Recem Cadastrado",
    )

    added = []
    # Expected sequence of SELECTs inside get_current_user:
    # 1) SELECT AllowedEmail WHERE email → the allowlist grants access
    # 2) SELECT User WHERE idp_sub → returns provisioned_user
    # 3) SELECT FamilyInvitation WHERE email==status=='pending_login' → pending_inv
    _exec = _entity_results(
        AllowedEmail(id=1, email="recem@example.com"),
        provisioned_user,
        pending_inv,
    )

    mock_session = AsyncMock()
    # The INSERT ... ON CONFLICT DO NOTHING also goes through session.execute, but
    # it reads no accessor — so it does not consume the _exec sequence.
    mock_session.execute.side_effect = execute_mock(_exec)
    # session.add() is SYNCHRONOUS in async SQLAlchemy — use MagicMock so the
    # side_effect runs immediately (no await)
    mock_session.add = MagicMock(side_effect=lambda o: added.append(o))
    mock_session.commit = AsyncMock()

    # Mock the JWT decode + JWKS cache to avoid touching a real Keycloak
    fake_token_payload = {
        "sub": "kc-sub-recem",
        "email": "recem@example.com",
        "email_verified": True,
        "name": "Recem Cadastrado",
    }
    result_user = _call_get_current_user(mock_session, fake_token_payload)

    # Assertions:
    # - the returned User must be provisioned_user
    assert result_user.idp_sub == "kc-sub-recem"
    # - a FamilyMember with role="member" was added for family 99
    members = [o for o in added if isinstance(o, FamilyMember)]
    assert len(members) == 1, f"Expected 1 FamilyMember; got {len(members)}: {added!r}"
    assert members[0].role == "member"
    assert members[0].family_id == 99
    assert members[0].user_id == 50
    # - the invitation was marked as joined (direct mutation + add to persist it)
    assert pending_inv.status == "joined", (
        f"FamilyInvitation.status must be 'joined' after the auto-join; got {pending_inv.status!r}"
    )


# ----------------------------------------------------------------------
# Allowlist — the first authorization layer
# ----------------------------------------------------------------------


def test_allowlist_helper_normalizes_the_email():
    """The helper always queries the normalized e-mail (strip + lowercase)."""
    from caramello_api.shared.auth import is_email_allowlisted
    from tests.conftest import execute_mock

    seen = []

    def _capture(stmt):
        seen.append(str(stmt.compile(compile_kwargs={"literal_binds": True})))
        result = MagicMock()
        result.first.return_value = None
        return result

    mock_session = AsyncMock()
    mock_session.execute.side_effect = execute_mock(_capture)

    allowed = asyncio.run(is_email_allowlisted(mock_session, "  Pessoa@Exemplo.COM  "))

    assert allowed is False
    assert len(seen) == 1
    assert "pessoa@exemplo.com" in seen[0]
    assert "Pessoa@Exemplo.COM" not in seen[0]


def test_email_not_verified_is_rejected_before_any_db_access():
    """Falsy `email_verified` → 403 before any database query."""
    mock_session = AsyncMock()

    payload = {
        "sub": "kc-sub-naoverificado",
        "email": "naoverificado@exemplo.com",
        "email_verified": False,
    }
    with pytest.raises(HTTPException) as exc_info:
        _call_get_current_user(mock_session, payload)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["reason"] == "email_not_verified"
    # The point of the test: no query at all — no cost and no allowlist timing
    # signal for a token whose e-mail is not trustworthy yet.
    mock_session.execute.assert_not_awaited()
    mock_session.execute.assert_not_called()
    # A 403 never carries WWW-Authenticate (the credential was understood and denied).
    assert exc_info.value.headers is None


def test_an_unusable_email_claim_is_rejected_before_reaching_the_database():
    """A claim the response schemas could not serialize must be a 401, not a stored row.

    `UserRead.email` is an `EmailStr`, so provisioning a user whose address
    `email_validator` rejects would answer 500 on every later read of that user,
    with no request able to repair it. The boundary therefore validates with the
    same validator the schema uses, before the allowlist query and before the
    upsert. Special-use domains are the realistic case.
    """
    import pytest as _pytest

    for unusable in ("operador@x.test", "operador@localhost", "sem-arroba"):
        mock_session = AsyncMock()
        payload = {
            "sub": "kc-sub-inutilizavel",
            "email": unusable,
            "email_verified": True,
        }
        with _pytest.raises(HTTPException) as exc_info:
            _call_get_current_user(mock_session, payload)

        assert exc_info.value.status_code == 401, unusable
        assert exc_info.value.detail["reason"] == "invalid_token", unusable
        # Nothing was queried and nothing was written: no row exists that the
        # api would later fail to serialize.
        mock_session.execute.assert_not_awaited()
        mock_session.commit.assert_not_awaited()
        # A 401 always advertises how to authenticate.
        assert "WWW-Authenticate" in (exc_info.value.headers or {}), unusable


def test_the_boundary_and_the_read_schema_agree_on_what_an_email_is():
    """Anti-regression: the two validators must not drift apart.

    If someone loosens the boundary or tightens `UserRead`, the pair stops being
    equivalent and the 500 this guards against comes back.
    """
    from pydantic import ValidationError as _ValidationError

    from caramello_api.shared.auth import _EMAIL_ADAPTER
    from caramello_api.users.schemas import UserRead

    def boundary_accepts(addr: str) -> bool:
        try:
            _EMAIL_ADAPTER.validate_python(addr)
            return True
        except _ValidationError:
            return False

    def schema_accepts(addr: str) -> bool:
        try:
            UserRead(
                uuid=uuid4(),
                idp_sub="s",
                email=addr,
                name="n",
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            return True
        except _ValidationError:
            return False

    for addr in (
        "operador@exemplo.com.br",
        "operador@exemplo.com",
        "operador@x.test",
        "operador@localhost",
        "sem-arroba",
    ):
        assert boundary_accepts(addr) == schema_accepts(addr), addr


def test_missing_email_verified_claim_is_treated_as_false():
    """A missing claim is a denial, never a permissive default."""
    mock_session = AsyncMock()

    with pytest.raises(HTTPException) as exc_info:
        _call_get_current_user(
            mock_session,
            {"sub": "kc-sub-sem-claim", "email": "semclaim@exemplo.com"},
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["reason"] == "email_not_verified"
    mock_session.execute.assert_not_called()


def test_not_allowlisted_returns_403_without_leaking_the_address():
    """E-mail outside the allowlist → 403 not_allowlisted, without echoing the address."""
    from tests.conftest import execute_mock

    email = "forasteiro@exemplo.com"
    mock_session = AsyncMock()
    # First (and only) SELECT: the allowlist, which finds nothing.
    mock_session.execute.side_effect = execute_mock(_entity_results(None))

    payload = {"sub": "kc-sub-forasteiro", "email": email, "email_verified": True}
    with pytest.raises(HTTPException) as exc_info:
        _call_get_current_user(mock_session, payload)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["reason"] == "not_allowlisted"
    # The error body never reveals the address that was looked up.
    assert email not in str(exc_info.value.detail)
    assert "forasteiro" not in str(exc_info.value.detail).lower()
    # No user is provisioned for anyone who did not clear the allowlist:
    # the only execute was the allowlist SELECT.
    assert mock_session.execute.await_count == 1
    mock_session.commit.assert_not_called()


def test_email_claim_is_normalized_before_the_allowlist_lookup():
    """An upper-cased claim is normalized before being compared to the allowlist."""
    from tests.conftest import execute_mock

    seen = []

    def _capture(stmt):
        seen.append(str(stmt.compile(compile_kwargs={"literal_binds": True})))
        result = MagicMock()
        result.first.return_value = None
        return result

    mock_session = AsyncMock()
    mock_session.execute.side_effect = execute_mock(_capture)

    payload = {"sub": "kc-sub-caixa", "email": " Pessoa@Exemplo.COM ", "email_verified": True}
    with pytest.raises(HTTPException) as exc_info:
        _call_get_current_user(mock_session, payload)

    assert exc_info.value.status_code == 403
    assert "pessoa@exemplo.com" in seen[0]


def test_non_string_email_claim_is_a_401():
    """An `email` claim with an unexpected type → 401, never a 500."""
    mock_session = AsyncMock()

    payload = {"sub": "kc-sub-tipo", "email": ["lista", "de", "emails"], "email_verified": True}
    with pytest.raises(HTTPException) as exc_info:
        _call_get_current_user(mock_session, payload)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail["reason"] == "invalid_token"
    mock_session.execute.assert_not_called()


def test_401_carries_the_www_authenticate_header(client):
    """RFC 6750: a 401 points the client at the protected resource's metadata."""
    response = client.get("/api/v1/users/me")

    assert response.status_code == 401
    body = response.json()
    assert body["detail"]["reason"] == "missing_token"
    assert body["detail"]["message"]
    header = response.headers["www-authenticate"]
    assert header.startswith("Bearer ")
    assert "resource_metadata=" in header
    assert "/.well-known/oauth-protected-resource" in header


def test_audience_and_issuer_are_validated():
    """The decode validates `aud` and `iss` against the Settings."""
    from caramello_api.core.config import get_settings
    from caramello_api.shared import auth as auth_module

    settings = get_settings()
    captured = {}

    def _fake_decode(token, key, **kwargs):
        captured.update(kwargs)
        return {"sub": "kc-sub", "email": "x@exemplo.com", "email_verified": False}

    mock_session = AsyncMock()
    with (
        patch.object(auth_module, "_jwks_cache", {"fake-kid": object()}),
        patch.object(auth_module.jwt, "get_unverified_header", return_value={"kid": "fake-kid"}),
        patch.object(auth_module.jwt, "decode", _fake_decode),
        pytest.raises(HTTPException),
    ):
        asyncio.run(auth_module.get_current_user(credentials=CREDENTIALS, session=mock_session))

    assert captured["algorithms"] == ["RS256"]
    assert captured["audience"] == settings.auth_oidc_audience
    assert captured["issuer"] == settings.auth_oidc_issuer
    assert captured["options"]["verify_aud"] is True
    assert captured["options"]["verify_iss"] is True
    # Every claim the code reads is required: a missing one is a 401, not a KeyError.
    for claim in ("exp", "iss", "aud", "sub", "email"):
        assert claim in captured["options"]["require"]

"""Contract of `POST /auth/verify` — the route the web module calls on its OIDC callback.

The contract is consumed by another module, so the shape of the success body
(200) and the shape of the errors (401/403) are asserted explicitly: changing
either of them breaks the web module's login.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4


def _fake_user(name: str | None = "Pessoa Autenticada"):
    from caramello_api.users.models import User

    return User(
        id=1,
        uuid=uuid4(),
        idp_sub="kc-sub-verify",
        email="pessoa@exemplo.com",
        name=name or "",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def test_verify_returns_the_documented_shape(client):
    """200 → {"email": str, "sub": str, "name": str | null}."""
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user

    app.dependency_overrides[get_current_user] = lambda: _fake_user()
    try:
        response = client.post("/auth/verify")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200, response.text
    assert response.json() == {
        "email": "pessoa@exemplo.com",
        "sub": "kc-sub-verify",
        "name": "Pessoa Autenticada",
    }


def test_verify_exposes_a_null_name_when_the_provider_sent_none(client):
    """An empty `name` in the database is exposed as null, never as an empty string."""
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user

    app.dependency_overrides[get_current_user] = lambda: _fake_user(name=None)
    try:
        response = client.post("/auth/verify")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200, response.text
    assert response.json()["name"] is None


def test_verify_without_token_is_401_missing_token(client):
    """401 → {"detail": {"reason": "missing_token", "message": "<pt-BR>"}}."""
    response = client.post("/auth/verify")

    assert response.status_code == 401
    detail = response.json()["detail"]
    assert detail["reason"] == "missing_token"
    assert detail["message"] and detail["message"] != "auth.missing_token"
    assert "www-authenticate" in response.headers


def test_verify_route_is_unversioned(client):
    """The route carries no version prefix — the web callback URL must never move.

    The business routes are versioned (`/api/v1/...`); `POST /auth/verify`, the
    health probe and the `.well-known` documents deliberately are not.
    """
    from caramello_api.main import app

    paths = {route.path for route in app.routes if hasattr(route, "path")}
    assert "/auth/verify" in paths
    assert "/api/v1/auth/verify" not in paths
    # The exception is meaningful only because the rule exists next to it.
    assert "/api/v1/users/me" in paths

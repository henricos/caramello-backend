"""Contrato de `POST /auth/verify` — a rota que o módulo web chama no callback OIDC.

O contrato é consumido por outro módulo, então a forma da resposta (200) e a
forma dos erros (401/403) são testadas explicitamente: mudar qualquer uma delas
quebra o login do web.
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
    """`name` vazio no banco é exposto como null, nunca como string vazia."""
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
    """A rota não carrega prefixo de versão — o callback do web não pode mudar."""
    from caramello_api.main import app

    paths = {route.path for route in app.routes if hasattr(route, "path")}
    assert "/auth/verify" in paths
    assert not any(path.startswith("/api/v1") for path in paths)

"""Testes para src/caramello_api/users/operations.py — USER-01.

GET /users/me requer auth válida + banco real (JIT provisioning).
Estratégia para CI: usar app.dependency_overrides para mockar get_current_user.
"""

from __future__ import annotations

from datetime import UTC


def test_get_me_returns_user_fields():
    """USER-01: GET /users/me retorna id, email, name (via mock de get_current_user)."""
    from datetime import datetime
    from uuid import uuid4

    from fastapi.testclient import TestClient

    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.users.models import User

    fake_user = User(
        id=42,
        uuid=uuid4(),
        idp_sub="fake-keycloak-sub",
        email="user@example.com",
        name="Usuario Teste",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    def _override():
        return fake_user

    app.dependency_overrides[get_current_user] = _override
    try:
        # Usar TestClient sem context manager para evitar disparo do lifespan
        # (que tenta conectar ao Keycloak via fetch_jwks).
        client = TestClient(app)
        response = client.get("/users/me")
        assert response.status_code == 200, response.text
        body = response.json()
        # UserRead exclui id interno; expõe uuid, email, name (ver dsl/entities/user.yaml)  # noqa: E501
        assert body["email"] == "user@example.com"
        assert body["name"] == "Usuario Teste"
        assert "uuid" in body or "id" in body
    finally:
        app.dependency_overrides.clear()


def test_operations_annotation_is_implemented():
    """D-10: após implementação, anotação muda de stub para implemented."""
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[1]
    ops_path = repo_root / "src/caramello_api/users/operations.py"
    first_line = ops_path.read_text().splitlines()[0].strip()
    assert first_line == "# CARAMELLO-GENERATED: implemented", (
        f"Anotação deve ser 'implemented' após Wave 4; foi: {first_line!r}"
    )

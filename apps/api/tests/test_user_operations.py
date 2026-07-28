"""Tests for src/caramello_api/users/operations.py.

GET /users/me requires valid auth plus a real database (JIT provisioning).
Strategy for CI: use app.dependency_overrides to mock get_current_user.
"""

from __future__ import annotations

from datetime import UTC


def test_get_me_returns_user_fields():
    """GET /users/me returns id, email, name (via a mocked get_current_user)."""
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
        # Use TestClient without the context manager so the lifespan never fires
        # (it would try to reach Keycloak through fetch_jwks).
        client = TestClient(app)
        response = client.get("/api/v1/users/me")
        assert response.status_code == 200, response.text
        body = response.json()
        # UserRead drops the internal id; it exposes uuid, email, name
        # (see dsl/entities/user.yaml).
        assert body["email"] == "user@example.com"
        assert body["name"] == "Usuario Teste"
        assert "uuid" in body or "id" in body
    finally:
        app.dependency_overrides.clear()


def test_operations_annotation_is_implemented():
    """Once implemented, the annotation changes from stub to implemented."""
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[1]
    ops_path = repo_root / "src/caramello_api/users/operations.py"
    first_line = ops_path.read_text().splitlines()[0].strip()
    assert first_line == "# CARAMELLO-GENERATED: implemented", (
        f"Annotation must be 'implemented' after Wave 4; got: {first_line!r}"
    )

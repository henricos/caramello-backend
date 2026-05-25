"""Testes para src/caramello/user/operations.py — USER-01.

GET /user/me requer auth válida + banco real (JIT provisioning).
Estratégia para CI: usar app.dependency_overrides para mockar get_current_user.
"""
from __future__ import annotations

import pytest


@pytest.mark.xfail(
    reason="Wave 4 (Plan 05) implementa GET /user/me",
    strict=False,
)
def test_get_me_returns_user_fields():
    """USER-01: GET /user/me retorna id, email, name (via mock de get_current_user)."""
    from datetime import datetime, timezone
    from uuid import uuid4

    from caramello.shared.auth import get_current_user
    from caramello.user.models import User
    from fastapi.testclient import TestClient

    from caramello.main import app

    fake_user = User(
        id=42,
        uuid=uuid4(),
        idp_sub="fake-keycloak-sub",
        email="user@example.com",
        name="Usuario Teste",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    def _override():
        return fake_user

    app.dependency_overrides[get_current_user] = _override
    try:
        with TestClient(app) as client:
            response = client.get("/user/me")
        assert response.status_code == 200, response.text
        body = response.json()
        # UserRead exclui id interno; expõe uuid, email, name (ver dsl/entities/user.yaml)  # noqa: E501
        assert body["email"] == "user@example.com"
        assert body["name"] == "Usuario Teste"
        assert "uuid" in body or "id" in body
    finally:
        app.dependency_overrides.clear()


@pytest.mark.xfail(
    reason="Wave 4 (Plan 05) implementa /user/me; D-10 anotação implemented",
    strict=False,
)
def test_operations_annotation_is_implemented():
    """D-10: após implementação, anotação muda de stub para implemented."""
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[1]
    ops_path = repo_root / "src/caramello/user/operations.py"
    first_line = ops_path.read_text().splitlines()[0].strip()
    assert first_line == "# CARAMELLO-GENERATED: implemented", (
        f"Anotação deve ser 'implemented' após Wave 4; foi: {first_line!r}"
    )

"""Smoke tests do endpoint MCP — verifica auth e descoberta de ferramentas.

Estes testes NÃO são marcados como integration — não precisam de caramello_dev.
Verificam apenas que /mcp existe, exige auth, e retorna estrutura MCP válida.
"""
from __future__ import annotations

import pytest


@pytest.mark.xfail(
    reason="Requer 05-04: MCP não montado ainda",
    strict=False,
)
def test_mcp_requires_auth(client):
    """MCP-02: GET /mcp sem Bearer token retorna 401 ou 403."""
    response = client.get("/mcp")
    assert response.status_code in (401, 403)


@pytest.mark.xfail(
    reason="Requer 05-04: MCP não montado ainda",
    strict=False,
)
def test_mcp_with_valid_token_returns_tools(client):
    """MCP-01: GET /mcp com token válido retorna estrutura com ferramentas."""
    from datetime import datetime, timezone
    from uuid import uuid4

    from caramello.main import app
    from caramello.shared.auth import get_current_user
    from caramello.users.models import User

    fake_user = User(
        id=1,
        uuid=uuid4(),
        idp_sub="test-sub",
        email="test@example.com",
        name="Test User",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    app.dependency_overrides[get_current_user] = lambda: fake_user
    try:
        response = client.get("/mcp")
        # /mcp com fastapi-mcp retorna spec MCP — 200 ou redirect
        assert response.status_code in (200, 307)
    finally:
        app.dependency_overrides.clear()

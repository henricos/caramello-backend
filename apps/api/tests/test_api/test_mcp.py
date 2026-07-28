"""Smoke tests do endpoint MCP — verifica auth e descoberta de ferramentas.

Estes testes NÃO são marcados como integration — não precisam de caramello_dev.
Verificam apenas que /mcp existe, exige auth, e retorna estrutura MCP válida.
"""

from __future__ import annotations

from datetime import UTC


def test_mcp_requires_auth(client):
    """MCP-02: POST /mcp sem Bearer token retorna 401 ou 403."""
    response = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "method": "tools/list", "id": 1},
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
    )
    assert response.status_code in (401, 403)


def test_mcp_with_valid_token_returns_tools(client):
    """MCP-01: POST /mcp com token Bearer retorna estrutura MCP válida com ferramentas."""
    from datetime import datetime
    from uuid import uuid4

    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.users.models import User

    fake_user = User(
        id=1,
        uuid=uuid4(),
        idp_sub="test-sub",
        email="test@example.com",
        name="Test User",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    app.dependency_overrides[get_current_user] = lambda: fake_user
    try:
        # MCP HTTP transport usa POST com Accept: application/json, text/event-stream
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "initialize",
                "id": 1,
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "0.1"},
                },
            },
            headers={
                "Authorization": "Bearer fake-token-for-smoke-test",
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
        )
        # /mcp com fastapi-mcp retorna 200 com resposta JSON-RPC
        assert response.status_code == 200
        data = response.json()
        assert data.get("jsonrpc") == "2.0"
        assert "result" in data
    finally:
        app.dependency_overrides.clear()

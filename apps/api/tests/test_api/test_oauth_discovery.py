"""Endpoints de OAuth discovery (RFC 9728 / RFC 8414) consumidos por clientes MCP.

São públicos e sem versão: a URL é definida pela especificação, então nem
autenticação nem prefixo de versão podem aparecer aqui.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.parametrize(
    "path",
    [
        "/.well-known/oauth-protected-resource",
        "/.well-known/oauth-protected-resource/mcp",
    ],
)
def test_protected_resource_metadata(client, path):
    """RFC 9728: identifica o recurso e o authorization server que o protege."""
    from caramello_api.core.config import get_settings

    settings = get_settings()
    response = client.get(path)

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {
        "resource",
        "authorization_servers",
        "bearer_methods_supported",
        "scopes_supported",
    }
    assert body["resource"] == f"{settings.public_url}/mcp"
    assert body["authorization_servers"] == [settings.auth_oidc_issuer]
    assert body["bearer_methods_supported"] == ["header"]


def test_authorization_server_metadata_relays_the_provider_document(client):
    """RFC 8414: o documento do provedor é repassado como está."""
    from caramello_api.shared import oauth_discovery

    document = {
        "issuer": "https://keycloak.exemplo.com/realms/caramello",
        "authorization_endpoint": "https://keycloak.exemplo.com/auth",
        "token_endpoint": "https://keycloak.exemplo.com/token",
        "jwks_uri": "https://keycloak.exemplo.com/certs",
    }
    with patch.object(
        oauth_discovery,
        "get_discovery_document",
        AsyncMock(return_value=document),
    ):
        response = client.get("/.well-known/oauth-authorization-server")

    assert response.status_code == 200, response.text
    assert response.json() == document


def test_authorization_server_metadata_is_503_when_the_provider_is_unreachable(client):
    """Provedor fora do ar é falha de dependência (503), nunca 500."""
    from caramello_api.shared import oauth_discovery

    with patch.object(
        oauth_discovery,
        "get_discovery_document",
        AsyncMock(side_effect=RuntimeError("provider down")),
    ):
        response = client.get("/.well-known/oauth-authorization-server")

    assert response.status_code == 503
    assert response.json()["detail"] == {"reason": "oidc_provider_unavailable"}


def test_discovery_endpoints_are_public_and_out_of_the_schema(client):
    """Sem token e fora do OpenAPI: são URLs de infraestrutura, não da API."""
    schema = client.get("/openapi.json").json()
    assert not [path for path in schema["paths"] if path.startswith("/.well-known")]

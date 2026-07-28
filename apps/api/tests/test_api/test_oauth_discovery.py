"""OAuth discovery endpoints (RFC 9728 / RFC 8414) consumed by MCP clients.

They are public and unversioned: the URL is fixed by the specification, so
neither authentication nor a version prefix may show up here.
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
    """RFC 9728: identifies the resource and the authorization server protecting it."""
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
    """RFC 8414: the provider's document is relayed as-is."""
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
    """A provider that is down is a dependency failure (503), never a 500."""
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
    """No token and out of OpenAPI: these are infrastructure URLs, not API ones."""
    schema = client.get("/openapi.json").json()
    assert not [path for path in schema["paths"] if path.startswith("/.well-known")]

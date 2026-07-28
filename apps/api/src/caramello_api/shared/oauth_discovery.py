"""OAuth discovery endpoints, so MCP clients can authenticate on their own.

An MCP client (Claude Desktop, an agent) pointed at `/mcp` gets a 401 whose
`WWW-Authenticate` header names the Protected Resource Metadata URL (see
`shared/auth.py`); from there the client discovers the authorization server,
runs the login in the user's browser (authorization code + PKCE — there is
always a human behind the flow, per the root `docs/architecture.md`) and
manages its own tokens. This api never mints or stores a token.

Two generations of the MCP authorization spec are served, both PUBLIC,
unversioned and kept out of the OpenAPI schema:

- `/.well-known/oauth-protected-resource` (RFC 9728, spec 2025-06-18): says who
  this resource is and which authorization server protects it. Also registered
  under `/mcp`, because path-aware clients insert the well-known segment before
  the resource path.
- `/.well-known/oauth-authorization-server` (RFC 8414, spec 2025-03-26): legacy
  clients expect the AUTHORIZATION SERVER's metadata on the MCP server's own
  origin; this endpoint relays the provider's discovery document (Keycloak's
  OIDC discovery is a superset of what they need).

Implemented in-module rather than relying on any proxy `fastapi_mcp` might
offer: these responses depend on this project's own settings (`PUBLIC_URL`,
`AUTH_OIDC_ISSUER`) and on the same cached discovery fetch that token
validation already performs, and their failure mode (503, never 500) is part of
the contract. Delegating them to the MCP library would tie a published,
spec-defined URL to that library's internals.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, status

from caramello_api.core.config import get_settings
from caramello_api.shared.auth import get_discovery_document

logger = logging.getLogger(__name__)

router = APIRouter(tags=["oauth-discovery"], include_in_schema=False)


@router.get("/.well-known/oauth-protected-resource")
@router.get("/.well-known/oauth-protected-resource/mcp")
async def protected_resource_metadata() -> dict[str, Any]:
    settings = get_settings()
    return {
        # The canonical identifier of this resource as consumers reach it —
        # which is why production deployments must set PUBLIC_URL.
        "resource": f"{settings.public_url}/mcp",
        "authorization_servers": [settings.auth_oidc_issuer],
        "bearer_methods_supported": ["header"],
        "scopes_supported": ["openid", "email", "profile"],
    }


@router.get("/.well-known/oauth-authorization-server")
async def authorization_server_metadata() -> dict[str, Any]:
    try:
        return await get_discovery_document()
    except Exception as exc:  # noqa: BLE001 — every failure mode is the same 503
        # The provider being unreachable is a dependency failure of THIS
        # endpoint, never an internal error worth a traceback-shaped 500.
        logger.warning("Could not relay the OIDC discovery document.", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"reason": "oidc_provider_unavailable"},
        ) from exc

"""Caramello api entry point.

- Lifespan: warms the JWKS cache via `shared.auth.fetch_jwks` (best-effort),
  then seeds the idempotent reference data (the allowlist's default e-mail)
- Routers: `shared/` (health, auth, OAuth discovery) plus the `users/`,
  `families/` and `finances/` domains
- MCP: mounted after every router, so all of them are visible as tools
"""

# isort: skip_file
# Import order is intentional — `users` is loaded before `families` to avoid a cycle.
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError, version as package_version

from fastapi import Depends, FastAPI
from fastapi_mcp import AuthConfig, FastApiMCP

from caramello_api.core.config import get_settings
from caramello_api.core.error_handlers import caramello_api_error_handler
from caramello_api.core.exceptions import CaramelloApiError
from caramello_api.shared import health, oauth_discovery
from caramello_api.shared.auth import fetch_jwks, http_bearer
from caramello_api.shared.auth_router import router as auth_router
from caramello_api.shared.database import engine
from caramello_api.shared.seeds import seed_default_reference
from caramello_api.users import operations as user_operations
from caramello_api.users import router as user_router
from caramello_api.families import operations as families_operations  # noqa: E402
from caramello_api.families import router as families_router  # noqa: E402
from caramello_api.finances import operations as finances_operations  # noqa: E402

settings = get_settings()

logging.basicConfig(level=settings.log_level.upper())
logger = logging.getLogger(__name__)


def _resolve_version() -> str:
    """Read the version from the installed package metadata.

    Single source of truth: `pyproject.toml`'s `version`, which the release
    flow bumps. The fallback only ever triggers when the package is not
    installed at all (e.g. running straight from a source checkout without
    `uv sync`), so a missing distribution degrades to a placeholder instead of
    crashing the import.
    """
    try:
        return package_version("caramello-api")
    except PackageNotFoundError:
        return "0.0.0"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Warm the JWKS cache and seed the reference data.

    Neither step makes startup depend on the identity provider.

    The fetch is deliberately best-effort. `get_current_user` already fetches
    the JWKS on a cache miss (and re-fetches on an unknown `kid`, for key
    rotation), so this is only a warm-up that saves the first authenticated
    request a round trip.

    Failing loudly here instead would tie the api's ability to boot to the
    identity provider being reachable — a health probe would never answer, a
    deploy would fail while the provider restarts, and local development would
    be impossible without a provider running. A provider outage must surface as
    a 401 on the requests that need a token, never as an api that refuses to
    start.
    """
    try:
        await fetch_jwks()
    except Exception:  # noqa: BLE001 — any provider/transport failure is non-fatal here
        logger.warning(
            "Could not warm the JWKS cache at startup; it will be fetched on first use.",
            exc_info=True,
        )

    # Idempotent reference data (the operator's allowlist e-mail), AFTER the
    # JWKS warm-up so a slow provider never delays the schema-dependent step.
    # The table it writes to already exists: the container entrypoint runs
    # `alembic upgrade head` before the process boots (and in development the
    # operator runs `./bin/manage_db upgrade`).
    await seed_default_reference(engine)

    yield


_is_production = settings.app_env == "production"

app = FastAPI(
    title="Caramello Backend",
    description="Backend API for Caramello",
    version=_resolve_version(),
    lifespan=lifespan,
    # `root_path` is a pure runtime concern: it only tells FastAPI which
    # prefix a reverse proxy strips before forwarding, so generated OpenAPI
    # URLs stay correct. Empty by default (direct host:port access).
    root_path=settings.app_base_path,
    # The interactive docs and the raw schema are development affordances;
    # production exposes neither. ReDoc is off everywhere — Swagger UI is the
    # one interface this project uses.
    docs_url=None if _is_production else "/docs",
    openapi_url=None if _is_production else "/openapi.json",
    redoc_url=None,
)

# No middleware is registered on purpose. In particular there is no CORS
# middleware: every consumer (the web included) reaches this api server-side,
# so no browser ever issues a cross-origin request against it. See the root
# `docs/architecture.md` for the access-pattern and authentication decisions.

# FastAPI types `add_exception_handler` against the base `Exception`, so a
# handler narrowed to a specific subclass is reported as incompatible even
# though this is the documented usage.
app.add_exception_handler(CaramelloApiError, caramello_api_error_handler)  # type: ignore[arg-type]

# Public, unversioned probe — registered first so it can never be shadowed.
app.include_router(health.router)

# Public, unversioned OAuth discovery (RFC 9728 / RFC 8414): `.well-known` URLs
# are spec-defined, so they must stay stable across api version bumps.
app.include_router(oauth_discovery.router)

# Authentication surface, unversioned: `POST /auth/verify` is the route a
# consumer calls on its OIDC callback. Static path, no {uuid} to shadow.
app.include_router(auth_router)

# Routers per domain
# IMPORTANT: operations (static routes) are registered BEFORE router (CRUD with
# {uuid}) so that /users/me, /families/registry and /families/families are not
# interpreted as UUIDs. FastAPI matches in registration order.
app.include_router(user_operations.router)
app.include_router(user_router.router)
app.include_router(families_operations.router)
app.include_router(families_router.router)
app.include_router(finances_operations.router)

# MCP — mount AFTER every include_router. Routers registered after
# mount_http() do not show up as tools.
mcp = FastApiMCP(
    app,
    name="Caramello MCP",
    include_operations=["list_my_families"],  # operation_id from families/operations.py
    auth_config=AuthConfig(
        dependencies=[Depends(http_bearer)],
    ),
    headers=["authorization"],  # forwards the token to get_current_user()
)
mcp.mount_http()


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Welcome to Caramello API"}

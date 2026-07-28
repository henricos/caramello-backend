"""Entrypoint da aplicação Caramello.

- Lifespan: popula cache JWKS via shared.auth.fetch_jwks no startup
- CORS: configurado para o frontend React/Capacitor
- Routers: registrados a partir dos domínios users/ e families/
"""

# isort: skip_file
# Ordem de imports intencional — users carregado antes de families para evitar ciclo.
from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_mcp import AuthConfig, FastApiMCP

from caramello_api.core.config import settings
from caramello_api.shared.auth import fetch_jwks, http_bearer
from caramello_api.users import operations as user_operations
from caramello_api.users import router as user_router
from caramello_api.families import operations as families_operations  # noqa: E402
from caramello_api.families import router as families_router  # noqa: E402
from caramello_api.finances import operations as finances_operations  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Popula o cache JWKS na inicialização da app."""
    await fetch_jwks()
    yield


app = FastAPI(
    title="Caramello Backend",
    description="Backend API for Caramello",
    version=os.getenv("APP_VERSION", "0.0.0"),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers por domínio
# IMPORTANTE: operations (rotas estáticas) registrados ANTES de router (CRUD com {uuid})
# para que /users/me, /families/registry e /families/families não sejam interpretados
# como UUIDs. FastAPI faz correspondência em ordem de registro.
# Ver D-06 (CONTEXT.md Phase 4) e Pitfall 2 (RESEARCH.md Phase 4).
app.include_router(user_operations.router)
app.include_router(user_router.router)
app.include_router(families_operations.router)
app.include_router(families_router.router)
app.include_router(finances_operations.router)

# MCP — montar DEPOIS de todos os include_router. Routers registrados após
# mount_http() não aparecem como ferramentas (RESEARCH.md Pitfall 2).
mcp = FastApiMCP(
    app,
    name="Caramello MCP",
    include_operations=["list_my_families"],  # operation_id de families/operations.py
    auth_config=AuthConfig(
        dependencies=[Depends(http_bearer)],
    ),
    headers=["authorization"],  # propaga token para get_current_user()
)
mcp.mount_http()


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Welcome to Caramello API"}

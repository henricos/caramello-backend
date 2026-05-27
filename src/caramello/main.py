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

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from caramello.core.config import settings
from caramello.shared.auth import fetch_jwks
from caramello.users import operations as user_operations
from caramello.users import router as user_router
from caramello.families import operations as families_operations  # noqa: E402
from caramello.families import router as families_router  # noqa: E402


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


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Welcome to Caramello API"}

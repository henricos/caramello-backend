"""Entrypoint da aplicação Caramello.

- Lifespan: popula cache JWKS via shared.auth.fetch_jwks no startup
- CORS: configurado para o frontend React/Capacitor
- Routers: registrados a partir dos domínios user/ e family/
"""

# isort: skip_file
# Ordem de imports intencional — user carregado antes de family para evitar ciclo.
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from caramello.core.config import settings
from caramello.shared.auth import fetch_jwks
from caramello.user import operations as user_operations
from caramello.user import router as user_router
from caramello.family import router as family_router  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Popula o cache JWKS na inicialização da app."""
    await fetch_jwks()
    yield


app = FastAPI(
    title="Caramello Backend",
    description="Backend API for Caramello",
    version="0.1.0",
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
# IMPORTANTE: user_operations deve ser registrado ANTES de user_router para que
# rotas estáticas como GET /user/me tenham prioridade sobre GET /user/{uuid}.
# FastAPI faz correspondência em ordem de registro; rotas estáticas devem vir
# antes das rotas com parâmetro para evitar que /user/me seja interpretado como uuid.
app.include_router(user_operations.router)
app.include_router(user_router.router)
app.include_router(family_router.router)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Welcome to Caramello API"}

"""Fixtures compartilhadas para os testes do Caramello."""
from __future__ import annotations

import os

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

# URL do banco de teste — lê as mesmas variáveis de ambiente que a app usa.
# O banco padrão é caramello_dev (mesmo banco que o .env de dev configura).
# Isolamento garantido exclusivamente via transaction rollback por teste.
TEST_DB_URL = (
    f"postgresql+asyncpg://{os.getenv('DB_USER', 'postgres')}"
    f":{os.getenv('DB_PASSWORD', 'postgres')}"
    f"@{os.getenv('DB_HOST', 'localhost')}"
    f":{os.getenv('DB_PORT', '5432')}"
    f"/{os.getenv('DB_NAME', 'caramello_dev')}"
)


@pytest.fixture
def client():
    """TestClient da app FastAPI, importado tarde para evitar erros em waves anteriores."""  # noqa: E501
    from caramello.main import app

    return TestClient(app)


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Engine async de sessão — compartilhado entre todos os testes da sessão."""
    engine = create_async_engine(TEST_DB_URL, echo=False, future=True)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine):
    """Sessão async com rollback por teste via savepoint.

    Usa join_transaction_mode="create_savepoint" para garantir isolamento
    com asyncpg em transações aninhadas (RESEARCH.md Pitfall 4).
    """
    async with test_engine.connect() as conn:
        await conn.begin()
        session = AsyncSession(bind=conn, join_transaction_mode="create_savepoint")
        yield session
        await session.close()
        await conn.rollback()


@pytest_asyncio.fixture
async def async_client(db_session):
    """AsyncClient com override de get_session e get_current_user."""
    from datetime import datetime, timezone
    from uuid import uuid4

    from caramello.main import app
    from caramello.shared.auth import get_current_user
    from caramello.shared.database import get_session
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

    async def _session_override():
        yield db_session

    app.dependency_overrides[get_session] = _session_override
    app.dependency_overrides[get_current_user] = lambda: fake_user

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

    app.dependency_overrides.clear()

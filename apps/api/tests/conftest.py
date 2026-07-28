"""Shared fixtures for the caramello-api test suite."""

from __future__ import annotations

import os
from datetime import UTC

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

# Default DSN for the test database. Integration tests run against the same
# embedded dev instance (`caramello_dev`); isolation comes exclusively from a
# per-test transaction rollback, never from a separate database.
_DEFAULT_TEST_DB_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/caramello_dev"

# Captured before the environment is pinned below: DATABASE_URL is how the
# developer points integration tests at a reachable database (e.g. the DSN
# printed by `python -m caramello_api.shared.db_dev_server`).
TEST_DB_URL = os.environ.get("DATABASE_URL") or _DEFAULT_TEST_DB_URL

# The environment is pinned to deterministic values BEFORE anything from
# `caramello_api` is imported, because `Settings` reads the real process
# environment and has no `env_file` — an `AUTH_OIDC_ISSUER` left over in the
# developer's shell would otherwise change what the tests exercise. This is the
# same intent as passing `_env_file=None` to a Settings constructor: the test
# run defines its own configuration, start to finish.
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["APP_ENV"] = "test"
os.environ["AUTH_OIDC_ISSUER"] = "https://keycloak.exemplo.com/realms/caramello"
os.environ["AUTH_OIDC_AUDIENCE"] = "caramello-api"


@pytest.fixture
def client():
    """TestClient for the FastAPI app, imported late to keep collection cheap."""
    from caramello_api.main import app

    return TestClient(app)


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Session-scoped async engine, shared by every test in the session."""
    engine = create_async_engine(TEST_DB_URL, echo=False, future=True)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine):
    """Async session with a per-test rollback via savepoint.

    Uses join_transaction_mode="create_savepoint" to keep isolation working
    with asyncpg inside nested transactions.
    """
    async with test_engine.connect() as conn:
        await conn.begin()
        session = AsyncSession(bind=conn, join_transaction_mode="create_savepoint")
        yield session
        await session.close()
        await conn.rollback()


@pytest_asyncio.fixture
async def async_client(db_session):
    """AsyncClient with get_session and get_current_user overridden."""
    from datetime import datetime
    from uuid import uuid4

    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session
    from caramello_api.users.models import User

    fake_user = User(
        id=1,
        uuid=uuid4(),
        idp_sub="test-sub",
        email="teste@exemplo.com",
        name="Test User",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
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

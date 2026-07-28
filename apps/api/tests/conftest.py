"""Shared fixtures for the caramello-api test suite."""

from __future__ import annotations

import os
from datetime import UTC
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

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


def execute_mock(entity_handler=None, row_handler=None):
    """Build the `session.execute` side effect used by the unit tests.

    SQLAlchemy hands back a `Result`, and the handlers consume it in one of two
    ways:

      - `.scalars().first()` / `.scalars().all()` — a select of a SINGLE entity,
        where `.scalars()` unwraps the Row into the ORM instance. `.first()` /
        `.all()` called straight on the result belong here too: they are how a
        multi-entity select reads its Rows.
      - `.fetchone()` / `.fetchall()` / `.scalar_one_or_none()` — a multi-entity
        select or an aggregation.

    `entity_handler(stmt)` answers the first group, `row_handler(stmt)` the
    second. Both are called lazily, on the first access within their own group,
    so a handler that sequences its answers by call order counts only the
    queries of its own group — which keeps a test's expected ordering
    independent of how many queries of the other kind run in between.
    """

    def _lazy(handler, stmt):
        cache: dict[str, object] = {}

        def get():
            if "result" not in cache:
                cache["result"] = handler(stmt)
            return cache["result"]

        return get

    async def _execute(stmt, *args, **kwargs):
        result = MagicMock()
        if entity_handler is not None:
            entity = _lazy(entity_handler, stmt)
            result.scalars.side_effect = entity
            result.first.side_effect = lambda: entity().first()
            result.all.side_effect = lambda: entity().all()
        if row_handler is not None:
            row = _lazy(row_handler, stmt)
            result.fetchone.side_effect = lambda: row().fetchone()
            result.fetchall.side_effect = lambda: row().fetchall()
            result.scalar_one_or_none.side_effect = lambda: row().scalar_one_or_none()
        return result

    return _execute


def constant(value):
    """Handler for `execute_mock` that always answers with the same object."""
    return lambda _stmt: value


def apply_column_defaults(obj):
    """Fill in the Python-side column defaults of an ORM instance.

    SQLAlchemy evaluates `mapped_column(default=...)` during the INSERT flush,
    not when the instance is constructed, so an object created against a mocked
    session keeps `uuid`, `created_at`, `is_active`, ... at None. Applying the
    defaults here is what a real flush plus refresh leaves behind, and it is why
    the unit tests can assert on a response body without a database.
    """
    from sqlalchemy import inspect as sa_inspect

    mapper = sa_inspect(type(obj))
    for column in mapper.columns:
        key = mapper.get_property_by_column(column).key
        if column.default is None or getattr(obj, key, None) is not None:
            continue
        default = column.default
        value = default.arg
        if callable(value):
            try:
                value = value()
            except TypeError:
                value = value(None)
        setattr(obj, key, value)
    return obj


def refresh_mock(extra=None):
    """`session.refresh` stand-in applying the column defaults (see above).

    `extra(obj)` runs afterwards for the per-test touches a real refresh would
    also have produced (typically pinning a known uuid).
    """

    async def _refresh(obj, *args, **kwargs):
        apply_column_defaults(obj)
        if extra is not None:
            extra(obj)
        return None

    return _refresh


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

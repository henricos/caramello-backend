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


def entity_sequence(*answers):
    """Handler for `execute_mock` answering the entity selects in order.

    A business endpoint resolves its public UUIDs one `select()` at a time
    (movement -> account -> FamilyMember, ...), so a test states what each step
    finds by listing the objects in that order. A list answers a select the
    endpoint reads through `.all()`; anything past the end of the sequence
    answers None, which is how a test mocks a row the database does not have —
    the 404 of an unknown UUID, or the missing FamilyMember behind a 403.
    """
    calls = [0]

    def _handler(_stmt):
        result = MagicMock()
        index = calls[0]
        calls[0] += 1
        answer = answers[index] if index < len(answers) else None
        if isinstance(answer, list):
            result.first.return_value = answer[0] if answer else None
            result.all.return_value = answer
        else:
            result.first.return_value = answer
            result.all.return_value = []
        return result

    return _handler


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


@pytest_asyncio.fixture
async def test_engine():
    """Async engine, function-scoped on purpose.

    pytest-asyncio gives each test its own event loop, and an asyncpg connection
    belongs to the loop that opened it. A session-scoped engine would hand the
    second test a pooled connection created in the first test's loop, which fails
    with "attached to a different loop" — so the engine's lifetime matches the
    loop's. Four integration tests do not make the extra connect worth
    optimizing.
    """
    engine = create_async_engine(TEST_DB_URL, echo=False, future=True)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine):
    """Async session with a per-test rollback via savepoint.

    Uses join_transaction_mode="create_savepoint" to keep isolation working
    with asyncpg inside nested transactions.

    `expire_on_commit=False` mirrors `shared.database.async_session_factory`: a
    test double that expires attributes on commit would make an endpoint blow up
    with MissingGreenlet on the very lines that read an already-loaded object
    after committing — a failure the real session cannot produce.
    """
    async with test_engine.connect() as conn:
        await conn.begin()
        session = AsyncSession(
            bind=conn,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        )
        yield session
        await session.close()
        await conn.rollback()


@pytest_asyncio.fixture
async def async_client(db_session):
    """AsyncClient with get_session and get_current_user overridden.

    The authenticated user is PERSISTED (flushed, never committed — the fixture's
    savepoint rolls it back): an integration test writes rows that reference
    `user.id` through a real foreign key, so a user that exists only in memory
    would make every one of those inserts fail. The id therefore comes from the
    database, never from a literal.
    """
    from datetime import datetime
    from uuid import uuid4

    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session
    from caramello_api.users.models import User

    fake_user = User(
        uuid=uuid4(),
        idp_sub=f"test-sub-{uuid4()}",
        email=f"teste-{uuid4()}@exemplo.com",
        name="Test User",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(fake_user)
    await db_session.flush()

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

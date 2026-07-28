"""Async SQLAlchemy engine, session factory and the FastAPI session dependency.

The engine is a module-level singleton: creating it at import time is what
makes `DATABASE_URL` a hard requirement for importing anything that reaches
this module.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from caramello_api.core.config import get_settings

engine = create_async_engine(
    get_settings().database_url,
    echo=False,
    future=True,
)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session

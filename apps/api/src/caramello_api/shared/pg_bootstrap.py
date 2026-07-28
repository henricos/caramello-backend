"""Single source of truth for booting a Postgres instance via `pgembed`.

Dev-only helper. It lives in `shared/` because it is infrastructure shared by
more than one domain, next to `database.py`, which owns the runtime engine;
`core/` is reserved for configuration and error plumbing. `pgembed` and
`asyncpg` are imported INSIDE the functions on purpose: `pgembed` belongs to
the dev dependency group and is absent from the production image, so merely
importing this module must never fail.

Both `db_dev_server.py` (long-lived, manual dev usage) and any ephemeral
E2E server script import `ensure_postgres` instead of duplicating the setup.
"""

from __future__ import annotations

import asyncio
import contextlib
import re
from collections.abc import Iterator

_VALID_DB_NAME = re.compile(r"[a-zA-Z0-9_]+")


async def _ensure_database(admin_uri: str, db_name: str) -> None:
    """Create `db_name` on the running instance if it does not already exist.

    `CREATE DATABASE` does not accept parameter binding, so the identifier is
    interpolated into the SQL string — the regex guard keeps that from ever
    becoming an injection vector if `db_name` comes from configuration.
    """
    import asyncpg

    if not _VALID_DB_NAME.fullmatch(db_name):
        raise ValueError(
            f"Invalid db_name: {db_name!r} (only letters, digits and underscores are accepted)"
        )

    conn = await asyncpg.connect(admin_uri)
    try:
        await conn.execute(f'CREATE DATABASE "{db_name}"')
    except asyncpg.exceptions.DuplicateDatabaseError:
        pass
    finally:
        await conn.close()


@contextlib.contextmanager
def ensure_postgres(data_dir: str, db_name: str) -> Iterator[str]:
    """Boot (or reuse) a `pgembed` Postgres instance and yield its async DSN.

    `data_dir` is the pgembed data directory (an ephemeral tempdir for tests
    and one-off scripts, a persistent path for `db_dev_server.py`). `db_name`
    is created on the instance's maintenance database if missing. Yields a
    `postgresql+asyncpg://...` URI ready to be assigned to `DATABASE_URL`.
    """
    import pgembed

    with pgembed.get_server(data_dir) as pg:
        admin_uri = pg.get_uri("postgres")
        asyncio.run(_ensure_database(admin_uri, db_name))

        uri = pg.get_uri(db_name)
        async_uri = uri.replace("postgresql://", "postgresql+asyncpg://", 1)
        yield async_uri

"""Ephemeral embedded Postgres (pgembed) for the root E2E scripts.

Companion of `caramello_api.shared.db_dev_server`, which serves MANUAL
development: that one reuses the persistent `apps/api/.pgembed-data/`
directory and the `caramello_dev` database, so the developer's data survives
restarts. This one is the opposite by design — a throwaway instance for a
single E2E run:

  - the data directory is a fresh temp dir, created here and removed on exit,
    so nothing is ever reused between runs and two concurrent E2E scripts get
    two independent clusters;
  - the database is named `caramello_e2e`, never `caramello_dev`, so an
    accident in the wiring can only ever hit the throwaway database;
  - `pgembed` binds a unix socket inside its own data directory and no TCP
    port at all, so concurrent instances cannot collide on a port either.

Both scripts import `ensure_postgres` from `shared/pg_bootstrap.py` instead of
duplicating the bootstrap.

Protocol expected by `e2e/lib/harness.js`: print exactly one
`DATABASE_URL=<dsn>` line on stdout as soon as the instance is usable, then
stay alive until told to stop. `SIGTERM` (what the harness sends when tearing
the stack down) and `SIGINT` (`Ctrl+C` when run by hand) both shut Postgres
down cleanly and delete the temp dir.

Usage: `.venv/bin/python scripts/e2e_ephemeral_server.py` from `apps/api/`.
The harness calls the interpreter directly rather than through `uv run`, so
the process it kills is the one it started — see the comment at the top of
`e2e/lib/harness.js`.
"""

from __future__ import annotations

import shutil
import signal
import tempfile
import time
from types import FrameType

from caramello_api.shared.pg_bootstrap import ensure_postgres

# Deliberately NOT `caramello_dev`: a wiring mistake must be unable to reach
# the database a developer keeps state in.
E2E_DB_NAME = "caramello_e2e"


def _shutdown(signum: int, frame: FrameType | None) -> None:
    """Turn a termination signal into the same exception `Ctrl+C` raises.

    The `ensure_postgres` context manager is what stops Postgres, so the
    signal must unwind the stack normally rather than exiting the process
    abruptly and leaving an orphan server behind.
    """
    raise KeyboardInterrupt


def main() -> None:
    signal.signal(signal.SIGTERM, _shutdown)

    # mkdtemp rather than TemporaryDirectory: the cleanup has to be tolerant
    # of files pgembed may still be holding, hence `ignore_errors` below.
    data_dir = tempfile.mkdtemp(prefix="caramello-e2e-pg-")
    try:
        with ensure_postgres(data_dir, E2E_DB_NAME) as database_url:
            print(f"DATABASE_URL={database_url}", flush=True)
            try:
                while True:
                    time.sleep(3600)
            except KeyboardInterrupt:
                pass
    finally:
        shutil.rmtree(data_dir, ignore_errors=True)


if __name__ == "__main__":
    main()

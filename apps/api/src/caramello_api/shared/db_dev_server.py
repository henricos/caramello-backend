"""Standalone embedded Postgres (pgembed) for manual development.

Run `uv run python -m caramello_api.shared.db_dev_server` from `apps/api/` in a
dedicated terminal: it starts Postgres, prints `DATABASE_URL` (copy it into
`.env.development`) and keeps the process alive until `Ctrl+C`. The data
directory is fixed and persistent (`apps/api/.pgembed-data/`, gitignored), so
the dev database survives restarts.

Named `db_dev_server` rather than `dev_server` because it sits in `shared/`
alongside the other database modules, where a bare `dev_server` would read as
"the api's dev server" instead of "the database's".
"""

from __future__ import annotations

import time
from pathlib import Path

from caramello_api.shared.pg_bootstrap import ensure_postgres

DEV_DB_NAME = "caramello_dev"


def main() -> None:
    # parents[2] from src/caramello_api/shared/ resolves to src/; one more
    # level up is apps/api/, where the persistent data dir lives.
    data_dir = Path(__file__).resolve().parents[3] / ".pgembed-data"
    data_dir.mkdir(parents=True, exist_ok=True)

    with ensure_postgres(str(data_dir), DEV_DB_NAME) as database_url:
        print(f"DATABASE_URL={database_url}", flush=True)
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()

"""`GET /health` — readiness probe used by Docker/Portainer and the E2E scripts.

Lives in `shared/` rather than `core/`: this package is organized by domain and
`shared/` is where the cross-domain HTTP/runtime infrastructure already lives
(`auth.py`, `database.py`), while `core/` holds pure plumbing with no routes
and no database access. The probe needs `shared.database.get_session`, so
putting it here keeps the dependency direction `shared -> core` intact.

The ONLY route without authentication, and deliberately registered with no
version prefix so the probe URL stays stable across api version bumps. It
verifies the two runtime dependencies this service actually needs: the
database answers a `SELECT 1` and the shared data folder is a reachable
directory. Returns 200 with the check map, or 503 when any check fails —
never exposing absolute paths or connection strings.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from caramello_api.core.config import get_settings
from caramello_api.shared.database import get_session

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(session: AsyncSession = Depends(get_session)) -> JSONResponse:
    checks: dict[str, bool] = {}

    try:
        await session.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        logger.exception("Health check: failed to query the database")
        checks["database"] = False

    checks["data_dir"] = Path(get_settings().data_dir).is_dir()

    status_code = 200 if all(checks.values()) else 503
    return JSONResponse(
        status_code=status_code,
        content={"status": "ok" if status_code == 200 else "unavailable", "checks": checks},
    )

"""CLI entry point — `python -m caramello_api` starts uvicorn via `Settings`.

Host/port/log level are read from `Settings` (`CARAMELLO_API_HOST`,
`CARAMELLO_API_PORT`, `CARAMELLO_API_LOG_LEVEL`, from the process
environment) instead of CLI flags, so the exact same command works unmodified
in the container's `CMD` and in local dev.
"""

import sys

import uvicorn

from caramello_api.core.config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "caramello_api.main:app",
        host=settings.host,
        port=settings.port,
        # Without this, CARAMELLO_API_LOG_LEVEL would only affect the app's
        # own loggers while uvicorn's access/error logs stayed at their
        # default level.
        log_level=settings.log_level,
        reload="--reload" in sys.argv[1:],
    )


if __name__ == "__main__":
    main()

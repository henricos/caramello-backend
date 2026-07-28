"""RFC 9457 exception handler mapping the `CaramelloApiError` hierarchy to HTTP.

This module only defines the handler, its lookup dicts and the response
model — `main.py` registers it with
`app.add_exception_handler(CaramelloApiError, ...)`. `ProblemDetail` lives
here rather than in a central schema module because this package is organized
by domain (`users/`, `families/`, `finances/`) and has no shared
`api/schemas.py`; the model is an implementation detail of this handler.
"""

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from caramello_api.core.exceptions import (
    CaramelloApiError,
    ConflictError,
    InvalidInputError,
    PermissionDeniedError,
    ResourceNotFoundError,
)

_STATUS_BY_EXCEPTION: dict[type[CaramelloApiError], int] = {
    InvalidInputError: 400,
    PermissionDeniedError: 403,
    ResourceNotFoundError: 404,
    ConflictError: 409,
}

_TITLE_BY_STATUS: dict[int, str] = {
    400: "Invalid input",
    403: "Permission denied",
    404: "Resource not found",
    409: "Conflict",
    500: "Internal error",
}


class ProblemDetail(BaseModel):
    """RFC 9457 `application/problem+json` body."""

    type: str
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None


async def caramello_api_error_handler(request: Request, exc: CaramelloApiError) -> JSONResponse:
    """Map any `CaramelloApiError` subclass to an `application/problem+json` response.

    The lookup is on the exact `type(exc)`, not on `isinstance`, so a new
    subclass never silently inherits a sibling's status code. Unknown
    subclasses default to 500 (fail-safe: unmapped domain errors are treated
    as server-side failures, never silently exposed as 200).
    """
    status_code = _STATUS_BY_EXCEPTION.get(type(exc), 500)
    problem = ProblemDetail(
        type=f"https://caramello.internal/errors/{type(exc).__name__}",
        title=_TITLE_BY_STATUS.get(status_code, "Internal error"),
        status=status_code,
        detail=str(exc),
        instance=str(request.url.path),
    )
    return JSONResponse(
        status_code=status_code,
        content=problem.model_dump(mode="json", exclude_none=True),
        media_type="application/problem+json",
    )

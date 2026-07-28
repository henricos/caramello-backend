"""Domain exception hierarchy mapped to RFC 9457 responses.

Raise a specific subclass from services/operations instead of returning a
success/error union; the handler in `core/error_handlers.py` converts any
`CaramelloApiError` into an `application/problem+json` response.
"""


class CaramelloApiError(Exception):
    """Base class for all caramello-api domain exceptions."""


class ResourceNotFoundError(CaramelloApiError):
    """Raised when a requested domain resource does not exist."""


class InvalidInputError(CaramelloApiError):
    """Raised when input fails domain validation beyond schema checks."""


class PermissionDeniedError(CaramelloApiError):
    """Raised when the caller is authenticated but not allowed to act."""


class ConflictError(CaramelloApiError):
    """Raised when the request collides with the current state of a resource."""

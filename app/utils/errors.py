"""Central error format + helpers (Step 12).

Every error leaves the API shaped like::

    {"success": False, "error": {"code": "...", "message": "...", "details": ...}}

Controllers keep raising ``fastapi.HTTPException`` (no churn); this
module maps status codes to stable ``code`` strings and offers
``APIError`` when a specific code (e.g. EMAIL_ALREADY_EXISTS) is needed::

    raise APIError(409, "EMAIL_ALREADY_EXISTS", "An account with this email already exists")

Nothing raised through here ever carries stack traces, SQL text,
credentials, hashes, tokens, or filesystem paths.
"""

import logging

from fastapi import HTTPException, status

logger = logging.getLogger("stayease.errors")

# Generic code per HTTP status for plain HTTPExceptions.
STATUS_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "RESOURCE_NOT_FOUND",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    500: "INTERNAL_SERVER_ERROR",
    503: "SERVICE_UNAVAILABLE",
}


class APIError(HTTPException):
    """HTTPException with a stable machine-readable code + optional details."""

    def __init__(self, status_code: int, code: str, message: str, details=None):
        super().__init__(status_code=status_code, detail=message)
        self.code = code
        self.details = details


def error_body(code: str, message: str, details=None) -> dict:
    """Build the standard envelope body (success is always False here)."""
    return {"success": False, "error": {"code": code, "message": message, "details": details}}


def code_for(status_code: int) -> str:
    """Generic code for a status (fallback UNKNOWN_ERROR)."""
    return STATUS_CODES.get(status_code, "UNKNOWN_ERROR")


# --- Ready-made errors used across controllers (consistent messages) ---


def not_found(resource: str, identifier=None) -> APIError:
    label = f" {identifier}" if identifier is not None else ""
    return APIError(404, "RESOURCE_NOT_FOUND", f"{resource}{label} not found")


def conflict(message: str, code: str = "CONFLICT", details=None) -> APIError:
    return APIError(409, code, message, details)


def bad_request(message: str, code: str = "BAD_REQUEST", details=None) -> APIError:
    return APIError(400, code, message, details)


def forbidden(message: str = "Not authorized") -> APIError:
    return APIError(403, "FORBIDDEN", message)


def email_exists() -> APIError:
    return APIError(
        409, "EMAIL_ALREADY_EXISTS", "An account with this email already exists"
    )


def login_failed() -> HTTPException:
    """Generic login failure (never reveals whether the email exists)."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password",
        headers={"WWW-Authenticate": "Bearer"},
    )

"""Redacted, contract-shaped HTTP errors."""

from secrets import token_urlsafe
from typing import Any

from starlette.responses import JSONResponse

_MESSAGES = {
    "SESSION_REQUIRED": "Local session required",
    "SESSION_INVALID": "Local session invalid or expired",
    "ORIGIN_FORBIDDEN": "Request origin forbidden",
    "VALIDATION_ERROR": "Request validation failed",
    "MALFORMED_JSON": "Malformed JSON request",
    "PAYLOAD_TOO_LARGE": "Request body too large",
    "NOT_FOUND": "Resource not found",
    "CONFIGURATION_REQUIRED": "Local application configuration is incomplete",
}


def error_response(
    status_code: int, code: str, details: dict[str, Any] | None = None
) -> JSONResponse:
    """Return a stable envelope without reflecting request content or credentials."""
    error: dict[str, Any] = {
        "code": code,
        "message": _MESSAGES[code],
        "requestId": f"req_{token_urlsafe(12)}",
    }
    if details is not None:
        error["details"] = details
    return JSONResponse({"error": error}, status_code=status_code)

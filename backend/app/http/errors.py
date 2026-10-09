"""Redacted, contract-shaped HTTP errors."""

from typing import Any

from backend.app.platform.telemetry import request_id
from starlette.responses import JSONResponse

_MESSAGES = {
    "SESSION_REQUIRED": "Local session required",
    "SESSION_INVALID": "Local session invalid or expired",
    "ORIGIN_FORBIDDEN": "Request origin forbidden",
    "VALIDATION_ERROR": "Request validation failed",
    "INVALID_QUERY": "Syntax or query shape invalid",
    "CURSOR_EXPIRED": "Cursor expired or is no longer valid",
    "MALFORMED_JSON": "Malformed JSON request",
    "PAYLOAD_TOO_LARGE": "Request body too large",
    "NOT_FOUND": "Resource not found",
    "CONFIGURATION_REQUIRED": "Local application configuration is incomplete",
    "AI_CONSENT_REQUIRED": "AI consent required",
    "AI_POLICY_CHANGED": "AI policy changed",
    "IDEMPOTENCY_KEY_REUSED": "Idempotency key reused",
    "IDEMPOTENCY_IN_FLIGHT": "Operation already in flight",
    "BRIDGE_UNAVAILABLE": "AI bridge unavailable",
    "BRIDGE_INVALID_RESPONSE": "AI bridge returned an invalid response",
    "BRIDGE_AUTH_ERROR": "AI bridge authentication failed",
    "STORAGE_BUSY": "Storage unavailable",
    "TIMEOUT": "Operation timed out",
    "INTERNAL_ERROR": "Internal application error",
}


def error_response(
    status_code: int, code: str, details: dict[str, Any] | None = None
) -> JSONResponse:
    """Return a stable envelope without reflecting request content or credentials."""
    error: dict[str, Any] = {
        "code": code,
        "message": _MESSAGES[code],
        "requestId": request_id(),
    }
    if details is not None:
        error["details"] = details
    return JSONResponse({"error": error}, status_code=status_code)

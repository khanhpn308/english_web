"""Bridge transport and preflight port definitions.

This module defines the explicit boundary between the local AI bridge proxy
and the application logic. It models ONLY transport and configuration-level
preflight responses. It does NOT own policy enforcement or consent state.
"""

from dataclasses import dataclass
from typing import Any, Protocol


class BridgeError(Exception):
    """Base class for transport and configuration errors."""

    pass


class BridgeConfigError(BridgeError):
    """Configuration is incomplete or safely disabled (e.g., auto/off)."""

    pass


class BridgeAuthError(BridgeError):
    """The proxy rejected the request (e.g., missing/invalid key)."""

    pass


class BridgeInvalidResponseError(BridgeError):
    """The proxy returned malformed JSON, invalid schema, or oversized data."""

    pass


class BridgeUnavailableError(BridgeError):
    """The proxy is unreachable, timed out, or connection failed."""

    pass


@dataclass
class BridgeProfile:
    """Preflight information about the active bridge proxy.

    This captures only the transport-level authenticated response.
    Consent and policy gates (e.g., T016) must consume this to determine
    final AI admission.
    """

    models: list[dict[str, Any]]
    raw_response: dict[str, Any] | None = None


class BridgePort(Protocol):
    """Interface for bridge communication, completely encapsulating HTTPX.

    A BridgePort instance is stateless. The caller provides an absolute
    monotonic deadline for each operation, ensuring preflight and inference
    share the same budget without resetting.

    Immediately before each no-key models, keyed models, and chat request,
    calculate deadline minus the current monotonic time. Use that remaining
    budget for the request timeout; if it is nonpositive, raise
    BridgeUnavailableError without sending the request. Never reuse a timeout
    calculated for an earlier stage or retain a deadline between operations.
    """

    async def preflight(self, deadline: float) -> BridgeProfile:
        """Validate proxy connectivity and credential, returning its profile.

        Must perform a two-stage check:
        1. No-key models request -> requires 401
        2. Keyed models request -> requires 200

        Raises:
            BridgeConfigError: If configuration safely disables the bridge (e.g. no-key 200).
            BridgeAuthError: If the proxy rejects the credential.
            BridgeInvalidResponseError: On format error or oversized response.
            BridgeUnavailableError: On timeout or connection failure.
        """
        ...

    async def dispatch_chat(self, payload: dict[str, Any], deadline: float) -> dict[str, Any]:
        """Dispatch a single chat completion payload to the bridge.

        Raises:
            BridgeConfigError: If configuration is invalid/missing.
            BridgeAuthError: If the proxy rejects the credential.
            BridgeInvalidResponseError: On format error or oversized response.
            BridgeUnavailableError: On timeout or connection failure.
        """
        ...

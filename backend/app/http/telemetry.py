"""HTTP correlation surrounding the complete production ASGI middleware stack."""

from time import monotonic

from backend.app.platform.telemetry import (
    EventFields,
    Telemetry,
    _duration,
    request_context,
    validated_request_id,
)
from fastapi import FastAPI
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class TelemetryMiddleware:
    def __init__(self, app: ASGIApp, telemetry: Telemetry) -> None:
        self.app = app
        self.telemetry = telemetry

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        # Reject duplicate headers as well as unsafe bytes; never retain raw headers.
        values = [v for k, v in scope.get("headers", []) if k.lower() == b"x-request-id"]
        incoming = (
            values[0].decode("ascii", errors="replace")
            if len(values) == 1 and len(values[0]) <= 36 else None
        )
        identifier = validated_request_id(incoming)
        status = 500
        failed = False
        try:
            start = monotonic()
        except Exception:
            start = None

        async def correlated_send(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                MutableHeaders(scope=message)["X-Request-ID"] = identifier
            await send(message)

        with request_context(identifier), self.telemetry.span(
            "http_request", request_id=identifier,
        ):
            try:
                await self.app(scope, receive, correlated_send)
            except BaseException:
                failed = True
                raise
            finally:
                # Read a registered route template only after dispatch, never the URL.
                route = scope.get("route")
                template = getattr(route, "path", None)
                fields = EventFields(
                    route=f"{scope.get('method')} {template}" if template else "unmatched",
                    status="failure" if failed or status >= 400 else "success",
                )
                try:
                    duration = _duration(start) if start is not None else None
                    fields = EventFields(fields.status, fields.route, duration)
                    self.telemetry.emit(
                        "http_request_failed" if failed or status >= 400
                        else "http_request_completed", fields=fields,
                    )
                    if status in {401, 403, 413}:
                        self.telemetry.emit(
                            "security_boundary_rejected", level="warn",
                            fields=EventFields("rejected", fields.route, duration),
                        )
                except Exception:
                    # A diagnostic finalizer cannot mask the application's exception.
                    self.telemetry.span_retention_failed = True


class RouteSpanMiddleware:
    """Local dispatch span inside the existing session and request-budget guards."""

    def __init__(self, app: ASGIApp, telemetry: Telemetry) -> None:
        self.app = app
        self.telemetry = telemetry

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        with self.telemetry.span("route_handler"):
            await self.app(scope, receive, send)


class TelemetryFastAPI(FastAPI):
    """Wrap ServerErrorMiddleware too, preserving its existing error behavior."""

    def build_middleware_stack(self) -> ASGIApp:
        return TelemetryMiddleware(super().build_middleware_stack(), self.state.telemetry)

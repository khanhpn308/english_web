"""Process-bound local browser sessions and HTTP boundary checks."""

from secrets import token_urlsafe
from threading import Lock
from time import monotonic
from urllib.parse import urlsplit

from backend.app.http.errors import error_response
from backend.app.platform.config import AppSettings
from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

COOKIE_NAME = "launch_session"
BOOTSTRAP_TTL_SECONDS = 60
SESSION_TTL_SECONDS = 28_800
MAX_JSON_BYTES = 1_048_576


class SessionStore:
    """Keep launch credentials only in the issuing backend process."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._active = False
        self._tokens: dict[str, float] = {}
        self._sessions: dict[str, float] = {}

    def activate(self) -> None:
        with self._lock:
            self._tokens.clear()
            self._sessions.clear()
            self._active = True

    def invalidate(self) -> None:
        with self._lock:
            self._active = False
            self._tokens.clear()
            self._sessions.clear()

    def issue_bootstrap_token(self) -> str:
        """Called by the local launcher; there is no HTTP token-issuance route."""
        with self._lock:
            if not self._active:
                raise RuntimeError("Session boundary is not active")
            token = token_urlsafe(32)
            self._tokens[token] = monotonic()
            return token

    def exchange(self, token: str) -> str | None:
        """Atomically consume one unexpired token and mint one browser session."""
        with self._lock:
            if not self._active:
                return None
            issued_at = self._tokens.pop(token, None)
            now = monotonic()
            if issued_at is None or now >= issued_at + BOOTSTRAP_TTL_SECONDS:
                return None
            cookie = token_urlsafe(32)
            self._sessions[cookie] = now
            return cookie

    def valid_session(self, cookie: str | None) -> bool:
        if cookie is None:
            return False
        with self._lock:
            if not self._active:
                return False
            issued_at = self._sessions.get(cookie)
            if issued_at is None:
                return False
            if monotonic() >= issued_at + SESSION_TTL_SECONDS:
                del self._sessions[cookie]
                return False
            return True


class SessionGuard:
    """Enforce same-origin, JSON-size and session rules before route handling."""

    def __init__(self, app: ASGIApp, settings: AppSettings, sessions: SessionStore) -> None:
        self.app = app
        self.settings = settings
        self.sessions = sessions

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        path = scope["path"]
        method = scope["method"].upper()
        expected_host = self.settings.host.lower()
        if ":" in expected_host:
            expected_host = f"[{expected_host}]"
        allowed_hosts = {expected_host, f"{expected_host}:{self.settings.port}"}
        origin = f"http://{expected_host}:{self.settings.port}"

        async def send_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["Content-Security-Policy"] = (
                    "default-src 'self'; script-src 'self'; connect-src 'self'; "
                    "object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
                )
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = "DENY"
                headers["Referrer-Policy"] = "no-referrer"
                headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
                if not path.startswith("/assets/"):
                    headers["Cache-Control"] = "no-store"
            await send(message)

        async def deny(status: int, code: str) -> None:
            await error_response(status, code)(scope, receive, send_headers)

        hosts = request.headers.getlist("host")
        if len(hosts) != 1 or hosts[0].lower() not in allowed_hosts:
            await deny(403, "ORIGIN_FORBIDDEN")
            return
        if scope["scheme"] != "http" or method == "OPTIONS":
            await deny(403, "ORIGIN_FORBIDDEN")
            return

        supplied_origin = request.headers.get("origin")
        referer = request.headers.get("referer")
        if supplied_origin is not None and supplied_origin != origin:
            await deny(403, "ORIGIN_FORBIDDEN")
            return
        if referer is not None:
            parsed = urlsplit(referer)
            if f"{parsed.scheme}://{parsed.netloc}" != origin:
                await deny(403, "ORIGIN_FORBIDDEN")
                return
        mutation = method in {"POST", "PUT", "PATCH", "DELETE"}
        if mutation and supplied_origin is None and referer is None:
            await deny(403, "ORIGIN_FORBIDDEN")
            return

        public = (
            method == "GET"
            and (path in {"/api/v1/health", "/bootstrap"} or path.startswith("/assets/"))
        ) or (method == "POST" and path == "/bootstrap/exchange")
        if not public:
            cookie = request.cookies.get(COOKIE_NAME)
            if not self.sessions.valid_session(cookie):
                await deny(401, "SESSION_REQUIRED" if cookie is None else "SESSION_INVALID")
                return

        if mutation:
            content_type = request.headers.get("content-type", "")
            media, _, params = content_type.partition(";")
            bodyless_delete = method == "DELETE" and not content_type
            if not bodyless_delete and (
                media.strip().lower() != "application/json"
                or (params and params.strip().lower() != "charset=utf-8")
            ):
                await deny(422, "VALIDATION_ERROR")
                return
            length = request.headers.get("content-length")
            if length is not None and (not length.isdecimal() or int(length) > MAX_JSON_BYTES):
                await deny(413, "PAYLOAD_TOO_LARGE")
                return

            buffered: list[Message] = []
            size = 0
            while True:
                try:
                    message = await receive()
                except TimeoutError:
                    if path != "/api/v1/lookups" or method != "POST":
                        raise
                    # Lookup's request budget wraps receive; preserve the same
                    # HTTP security headers when an unfinished body times out.
                    await deny(503, "BRIDGE_UNAVAILABLE")
                    return
                if message["type"] == "http.disconnect":
                    return
                size += len(message.get("body", b""))
                if size > MAX_JSON_BYTES:
                    await deny(413, "PAYLOAD_TOO_LARGE")
                    return
                buffered.append(message)
                if not message.get("more_body", False):
                    break

            if bodyless_delete and size != 0:
                await deny(422, "VALIDATION_ERROR")
                return

            async def replay() -> Message:
                if buffered:
                    return buffered.pop(0)
                return await receive()

            await self.app(scope, replay, send_headers)
            return

        await self.app(scope, receive, send_headers)

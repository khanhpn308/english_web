"""Local-only T011 telemetry, without exporters or global logging handlers."""

import json
import math
import os
import re
import stat
import sys
from collections import deque
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock
from time import monotonic
from uuid import uuid4

MAX_LOG_BYTES = 10 * 1024 * 1024
MAX_LOG_FILES = 5  # active telemetry.jsonl and telemetry.jsonl.1 through .4
RETENTION_DAYS = 14
MAX_SPANS = 1024
MAX_DURATION_MS = 86_400_000
_EVENTS = frozenset({
    "app_started", "app_shutdown", "http_request_completed", "http_request_failed",
    "security_boundary_rejected", "telemetry_rotation_failed",
})
_LEVELS = frozenset({"info", "warn", "error"})
_ENTRY_POINTS = frozenset({"browser", "launcher", "watcher", "manual-sync"})
_RESULTS = frozenset({"success", "failure", "rejected", "unavailable"})
_SPAN_NAMES = frozenset({
    "local_operation", "http_request", "validation", "route_handler", "sqlite",
    "markdown", "bridge_call", "bridge_validation", "quiz_scoring", "srs_update",
})
_OPERATIONS = frozenset({"lookup", "quiz", "review", "search", "sync", "save", "feedback"})
_SOURCE_STATUSES = frozenset({"VALID", "INVALID", "MISSING"})
# Only reviewed route templates, never a request path/query or arbitrary URL.
_ROUTES = frozenset({
    "GET /api/v1/health", "POST /bootstrap/exchange", "GET /bootstrap",
    "GET /api/v1/ai-consent", "PUT /api/v1/ai-consent", "DELETE /api/v1/ai-consent",
    "GET /api/v1/operations/{operation_id}", "POST /api/v1/lookups",
    "GET /api/v1/word-forms", "GET /api/v1/word-forms/{wordFormId}",
    "POST /api/v1/word-forms", "PATCH /api/v1/word-forms/{wordFormId}",
    "GET /api/v1/review-queue", "POST /api/v1/cards/{cardId}/reviews", "GET /api/v1/sources",
    "POST /api/v1/sync-runs", "GET /api/v1/sync-runs/{syncRunId}",
    "POST /api/v1/quiz-attempts", "GET /api/v1/quiz-attempts/{attemptId}",
    "PUT /api/v1/quiz-attempts/{attemptId}/answers/{questionId}", "unmatched",
})
_REQUEST_ID = re.compile(
    r"(?:req_[0-9a-f]{32}|[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})\Z", re.ASCII
)
_VERSION = re.compile(r"[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\Z", re.ASCII)


# This stores only a bounded diagnostic ID, never an app or mutable request object.
_http_request_id: ContextVar[str | None] = ContextVar("http_request_id", default=None)


def validated_request_id(value: str | None) -> str:
    if type(value) is str and len(value) <= 36 and _REQUEST_ID.fullmatch(value):
        return value
    return f"req_{uuid4().hex}"


def request_id() -> str:
    """Authoritative HTTP ID; direct non-HTTP error construction gets a fresh ID."""
    return _http_request_id.get() or validated_request_id(None)


@contextmanager
def request_context(identifier: str) -> Iterator[None]:
    token = _http_request_id.set(validated_request_id(identifier))
    try:
        yield
    finally:
        _http_request_id.reset(token)


def _category(value: object, choices: frozenset[str], default: str | None = None) -> str | None:
    return value if type(value) is str and value in choices else default


def _duration(start: float) -> float:
    elapsed = (monotonic() - start) * 1000
    return round(min(MAX_DURATION_MS, max(0.0, elapsed)), 3) if math.isfinite(elapsed) else 0.0


def default_log_directory() -> Path | None:
    """Use the approved Windows location only on Windows, or disable persistence.

    Non-Windows callers can explicitly supply a synthetic/test directory. No Linux
    storage policy is inferred from a Windows environment variable or user data root.
    Windows inherits the current-user profile ACL; Host must verify native ACLs.
    """
    if os.name != "nt":
        return None
    local = os.environ.get("LOCALAPPDATA")
    if not local or local.startswith(("\\\\", "//")) or not Path(local).is_absolute():
        return None
    return Path(local) / "VocabularyApp" / "logs"


@dataclass(frozen=True)
class EventFields:
    """Closed event schema; no request content, exceptions, or metadata mappings."""

    status: str | None = None
    route: str | None = None
    duration_ms: float | None = None


@dataclass(frozen=True)
class SpanAttributes:
    """Operational categories only. Rejected values are dropped before retention."""

    operation: str | None = None
    source_status: str | None = None
    row_count: int | None = None

    def sanitized(self) -> "SpanAttributes":
        count = self.row_count
        return SpanAttributes(
            operation=_category(self.operation, _OPERATIONS),
            source_status=_category(self.source_status, _SOURCE_STATUSES),
            row_count=count if type(count) is int and 0 <= count <= 100_000 else None,
        )


@dataclass(frozen=True)
class SpanContext:
    request_id: str
    trace_id: str
    span_id: str
    parent_span_id: str | None
    entry_point: str


@dataclass(frozen=True)
class LocalSpan:
    name: str
    request_id: str
    trace_id: str
    span_id: str
    parent_span_id: str | None
    entry_point: str
    attributes: SpanAttributes
    status: str
    duration_ms: float


class LocalJsonSink:
    """Five bounded files, age cleanup on append, no workers and no open handles.

    A failed sink disables persistence for its lifetime, with one fixed diagnostic.
    Learning work never retries a failed disk. A busy sink drops diagnostics instead
    of waiting on another writer. Single process ownership follows the launcher ADR.
    """

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.failed = False
        self._closed = False
        self._lock = Lock()
        self._reported = False

    def _failure(self) -> None:
        self.failed = True
        if self._reported:
            return
        self._reported = True
        # Never call a logger recursively, stringify an exception, or reflect a path.
        diagnostic = {
            "timestamp": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "level": "warn", "event": "telemetry_rotation_failed",
            "service": "vocab-backend", "version": "0.1.0",
            "entryPoint": "launcher", "status": "unavailable",
        }
        try:
            sys.stderr.write(json.dumps(diagnostic, separators=(",", ":")) + "\n")
        except Exception:
            # failed remains available even when stderr itself is broken.
            return

    def _path(self, index: int) -> Path:
        return self.directory / ("telemetry.jsonl" + (f".{index}" if index else ""))

    @staticmethod
    def _check_file(path: Path) -> bool:
        try:
            info = path.lstat()
        except FileNotFoundError:
            return False
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1
            or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
        ):
            raise OSError("Unsafe telemetry file")
        return True

    def _oldest_timestamp(self, path: Path) -> datetime | None:
        if not self._check_file(path):
            return None
        if path.stat().st_size == 0:
            return None
        # Identity/age evidence from a bounded first record, not a refreshed mtime.
        with path.open("rb") as stream:
            line = stream.readline(4096)
        if not line.endswith(b"\n"):
            raise OSError("Unowned telemetry file")
        record = json.loads(line)
        if not isinstance(record, dict) or record.get("service") != "vocab-backend":
            raise OSError("Unowned telemetry file")
        timestamp = record.get("timestamp")
        if not isinstance(timestamp, str) or len(timestamp) > 40:
            raise OSError("Invalid telemetry age")
        age = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if age.tzinfo is None:
            raise OSError("Invalid telemetry age")
        if os.name != "nt":
            path.chmod(0o600)
        return age

    def _prepare(self, size: int) -> None:
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = self.directory.lstat()
        if (
            not stat.S_ISDIR(info.st_mode)
            or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
        ):
            raise OSError("Unsafe telemetry directory")
        if os.name != "nt":
            self.directory.chmod(0o700)
        cutoff = datetime.now(UTC) - timedelta(days=RETENTION_DAYS)
        for index in range(MAX_LOG_FILES):
            path = self._path(index)
            oldest = self._oldest_timestamp(path)
            if oldest is not None and oldest < cutoff:
                path.unlink()
        active = self._path(0)
        if self._check_file(active) and active.stat().st_size + size > MAX_LOG_BYTES:
            last = self._path(MAX_LOG_FILES - 1)
            if self._check_file(last):
                last.unlink()
            for index in range(MAX_LOG_FILES - 2, -1, -1):
                source = self._path(index)
                if self._check_file(source):
                    source.replace(self._path(index + 1))

    def _append(self, serialized: bytes) -> bool:
        """Private sink boundary: Telemetry has already filtered and serialized."""
        if self.failed or self._closed or not self._lock.acquire(blocking=False):
            return False
        try:
            if self._closed or len(serialized) > MAX_LOG_BYTES:
                return False
            self._prepare(len(serialized))
            flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(self._path(0), flags, 0o600)
            try:
                stream = os.fdopen(descriptor, "ab")
            except Exception:
                os.close(descriptor)
                raise
            with stream:
                stream.write(serialized)
            return True
        except Exception:
            self._failure()
            return False
        finally:
            self._lock.release()

    def close(self) -> None:
        self._closed = True


class Telemetry:
    """Per-app telemetry state with contextvars and bounded completed local spans."""

    def __init__(
        self, *, sink: LocalJsonSink | None = None, version: str = "0.1.0",
        span_capacity: int = MAX_SPANS,
    ) -> None:
        self.sink = sink
        self.span_retention_failed = False
        self.version = version if type(version) is str and _VERSION.fullmatch(version) else "0.1.0"
        self._context: ContextVar[SpanContext | None] = ContextVar("local_span", default=None)
        self._spans: deque[tuple[float, LocalSpan]] = deque(
            maxlen=max(1, min(MAX_SPANS, span_capacity))
        )
        self._lock = Lock()

    def current_context(self) -> SpanContext | None:
        return self._context.get()

    def emit(
        self, event: str, *, level: str = "info", fields: EventFields | None = None,
    ) -> bool:
        """Drop unknown fields/categories before serialization, with no exception text."""
        try:
            if type(event) is not str or event not in _EVENTS:
                return False
            context = self.current_context()
            record: dict[str, str | float] = {
                "timestamp": datetime.now(UTC).isoformat(timespec="milliseconds"),
                "level": _category(level, _LEVELS, "info") or "info",
                "event": event, "service": "vocab-backend", "version": self.version,
                "entryPoint": context.entry_point if context is not None else "launcher",
            }
            if context is not None:
                record.update({
                    "requestId": context.request_id, "traceId": context.trace_id,
                    "spanId": context.span_id,
                })
            if type(fields) is EventFields:
                status = _category(fields.status, _RESULTS)
                route = _category(fields.route, _ROUTES)
                if status is not None:
                    record["status"] = status
                if route is not None:
                    record["route"] = route
                duration = fields.duration_ms
                if type(duration) in {int, float} and duration is not None:
                    if math.isfinite(duration) and 0 <= duration <= MAX_DURATION_MS:
                        record["durationMs"] = round(duration, 3)
            serialized = (json.dumps(record, separators=(",", ":"), allow_nan=False)
                          + "\n").encode("utf-8")
            return self.sink._append(serialized) if self.sink is not None else False
        except Exception:
            return False

    @contextmanager
    def span(
        self, name: str, *, request_id: str | None = None, entry_point: str = "browser",
        attributes: SpanAttributes | None = None,
    ) -> Iterator[SpanContext]:
        """Local parent/child boundary; never inject headers or serialize exceptions."""
        try:
            parent = self.current_context()
            effective_id = (
                request_id if type(request_id) is str and _REQUEST_ID.fullmatch(request_id)
                else f"req_{uuid4().hex}"
            )
            context = SpanContext(
                request_id=parent.request_id if parent else effective_id,
                trace_id=parent.trace_id if parent else uuid4().hex,
                span_id=uuid4().hex[:16],
                parent_span_id=parent.span_id if parent else None,
                entry_point=parent.entry_point if parent else (
                    _category(entry_point, _ENTRY_POINTS, "browser") or "browser"
                ),
            )
            safe_name = _category(name, _SPAN_NAMES, "local_operation") or "local_operation"
            safe_attributes = attributes.sanitized() if type(attributes) is SpanAttributes else (
                SpanAttributes()
            )
            start = monotonic()
            token = self._context.set(context)
        except Exception:
            self.span_retention_failed = True
            # No context is installed or retained on a failed instrumentation setup.
            # Yield outside the setup guard so operation exceptions still propagate.
            yield SpanContext("req_unavailable", "0" * 32, "0" * 16, None, "browser")
            return
        status = "success"
        try:
            yield context
        except BaseException:
            status = "failure"
            raise
        finally:
            self._context.reset(token)
            try:
                span = LocalSpan(
                    name=safe_name, request_id=context.request_id, trace_id=context.trace_id,
                    span_id=context.span_id, parent_span_id=context.parent_span_id,
                    entry_point=context.entry_point, attributes=safe_attributes,
                    status=status, duration_ms=_duration(start),
                )
                with self._lock:
                    now = monotonic()
                    self._prune_spans(now)
                    self._spans.append((now, span))
            except Exception:
                # Diagnostics may be dropped; the operation's original outcome survives.
                self.span_retention_failed = True

    def spans(self) -> tuple[LocalSpan, ...]:
        with self._lock:
            self._prune_spans(monotonic())
            return tuple(span for _, span in self._spans)

    def _prune_spans(self, now: float) -> None:
        cutoff = now - RETENTION_DAYS * 86_400
        while self._spans and self._spans[0][0] < cutoff:
            self._spans.popleft()

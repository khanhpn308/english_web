"""Bounded local counters and exact retained duration histograms for T046."""

import math
from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import RLock
from time import monotonic

from backend.app.platform.telemetry import (
    MAX_SPANS,
    RETENTION_DAYS,
    EventFields,
    LocalJsonSink,
    Telemetry,
)

MAX_SERIES = 1024
MAX_OBSERVATIONS = 1024
MAX_HTTP_RESPONSES = 16_384
HTTP_WINDOW_SECONDS = 300
RETENTION_SECONDS = RETENTION_DAYS * 86_400
_COUNTERS = frozenset({
    "http_requests_total", "bridge_requests_total",
    "bridge_response_validation_failures_total", "markdown_sync_total",
    "sqlite_transactions_total", "sqlite_busy_total", "sqlite_integrity_failures_total",
    "review_events_total", "quiz_attempts_total", "feedback_total",
    "ai_consent_mutations_total", "ai_dispatch_blocked_total",
})
_HISTOGRAMS = frozenset({
    "http_request_duration_seconds", "bridge_request_duration_seconds",
    "markdown_sync_duration_seconds",
})
_LABELS = {
    "method": frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "OTHER"}),
    "status_class": frozenset({"2xx", "3xx", "4xx", "5xx"}),
    "operation": frozenset({"lookup", "quiz", "review", "search", "sync", "save", "feedback", "read", "write", "unknown"}),
    "dependency": frozenset({"bridge", "sqlite", "markdown"}),
    "provider": frozenset({"local-bridge"}),
    "model_family": frozenset({"gemini-3.8-flash-high"}),
    "source_status": frozenset({"VALID", "INVALID", "MISSING"}),
    "result": frozenset({"success", "failure", "rejected", "unavailable"}),
    "reason": frozenset({"CONSENT_REQUIRED", "POLICY_STALE", "CONFIGURATION_REQUIRED"}),
    "failure_class": frozenset({"invalid_response"}),
    "check": frozenset({"startup", "database"}),
}
MetricKey = tuple[str, tuple[tuple[str, str], ...]]


class MetricsUnavailable(RuntimeError):
    """Collection failed; previously collected values cannot imply healthy telemetry."""


@dataclass(frozen=True)
class DurationSummary:
    observations: int
    p50_seconds: float | None
    p95_seconds: float | None
    p99_seconds: float | None


@dataclass(frozen=True)
class RequestSummary:
    requests: int | None
    request_error_rate: float | None
    duration: DurationSummary
    epoch_started_at: datetime
    sampled_at: datetime | None
    window_complete: bool


def _percentiles(values: list[float]) -> DurationSummary:
    values.sort()
    count = len(values)
    return DurationSummary(
        count,
        *(values[math.ceil(count * quantile) - 1] if count else None
          for quantile in (0.50, 0.95, 0.99)),
    )


class LocalMetrics:
    """Counters reset together at restart or after a 14-day collection epoch.

    Histogram percentiles use the latest 1024 observations per series, not bucket
    midpoints. Their sample count is explicit. No-data values are None, including
    counters that have never been observed. No disk, collector, or worker is needed.
    """

    def __init__(self) -> None:
        self.routes: frozenset[str] = frozenset({"unmatched"})
        self.failed = False
        self.epoch_started_at = datetime.now(UTC)
        self._epoch_start = monotonic()
        self._counters: dict[MetricKey, int] = {}
        self._histograms: dict[MetricKey, deque[float]] = {}
        self._http_responses: deque[tuple[float, str]] = deque(maxlen=MAX_HTTP_RESPONSES)
        self._http_durations: deque[tuple[float, float]] = deque(maxlen=MAX_OBSERVATIONS)
        self._http_overflow_at: float | None = None
        self._lock = RLock()

    def _key(self, name: str, labels: Mapping[str, str], names: frozenset[str]) -> MetricKey:
        if type(name) is not str or name not in names:
            raise ValueError("Unsupported metric")
        for label, value in labels.items():
            choices = self.routes if label == "route_template" else _LABELS.get(label)
            if type(label) is not str or type(value) is not str or choices is None:
                raise ValueError("Unsupported metric label")
            if value not in choices:
                raise ValueError("Unsupported metric category")
        return name, tuple(sorted(labels.items()))

    def _prune(self) -> None:
        if monotonic() - self._epoch_start >= RETENTION_SECONDS:
            self._counters.clear()
            self._histograms.clear()
            self._http_responses.clear()
            self._http_durations.clear()
            self._http_overflow_at = None
            self._epoch_start = monotonic()
            self.epoch_started_at = datetime.now(UTC)

    def _reserve(self, key: MetricKey) -> None:
        if key not in self._counters and key not in self._histograms:
            if len(self._counters) + len(self._histograms) >= MAX_SERIES:
                raise MetricsUnavailable("Metric series capacity reached")

    def increment(self, name: str, labels: Mapping[str, str], amount: int = 1) -> None:
        key = self._key(name, labels, _COUNTERS)
        if type(amount) is not int or amount < 0:
            raise ValueError("Invalid counter increment")
        with self._lock:
            self._prune()
            self._reserve(key)
            value = self._counters.get(key, 0) + amount
            if value > 2**63 - 1:
                raise MetricsUnavailable("Counter capacity reached")
            self._counters[key] = value

    def observe(self, name: str, labels: Mapping[str, str], seconds: float) -> None:
        key = self._key(name, labels, _HISTOGRAMS)
        if type(seconds) not in {int, float} or not math.isfinite(seconds) or seconds < 0:
            raise ValueError("Invalid duration observation")
        with self._lock:
            self._prune()
            self._reserve(key)
            values = self._histograms.setdefault(key, deque(maxlen=MAX_OBSERVATIONS))
            values.append(seconds)

    def counter(self, name: str, labels: Mapping[str, str]) -> int | None:
        key = self._key(name, labels, _COUNTERS)
        with self._lock:
            self._prune()
            if self.failed:
                raise MetricsUnavailable("Metric collection failed")
            return self._counters.get(key)

    def duration(self, name: str, labels: Mapping[str, str]) -> DurationSummary:
        key = self._key(name, labels, _HISTOGRAMS)
        with self._lock:
            self._prune()
            if self.failed:
                raise MetricsUnavailable("Metric collection failed")
            values = list(self._histograms.get(key, ()))
        return _percentiles(values)

    def record_http(self, labels: Mapping[str, str], seconds: float) -> None:
        with self._lock:
            self.increment("http_requests_total", labels)
            self.observe("http_request_duration_seconds", labels, seconds)
            now = monotonic()
            while self._http_responses and self._http_responses[0][0] <= now - HTTP_WINDOW_SECONDS:
                self._http_responses.popleft()
            if len(self._http_responses) == MAX_HTTP_RESPONSES:
                self._http_overflow_at = self._http_responses[0][0]
            self._http_responses.append((now, labels["status_class"]))
            self._http_durations.append((now, seconds))

    def requests(self) -> RequestSummary:
        """Exact five-minute 5xx fraction; overflow yields unavailable, not an estimate."""
        with self._lock:
            self._prune()
            if self.failed:
                raise MetricsUnavailable("Metric collection failed")
            cutoff = monotonic() - HTTP_WINDOW_SECONDS
            while self._http_responses and self._http_responses[0][0] <= cutoff:
                self._http_responses.popleft()
            statuses = [status for _time, status in self._http_responses]
            values = [value for observed, value in self._http_durations if observed > cutoff]
            complete = self._http_overflow_at is None or self._http_overflow_at <= cutoff
            epoch_started_at = self.epoch_started_at
            sampled_at = datetime.now(UTC) if statuses else None
        count = len(statuses)
        failures = statuses.count("5xx")
        return RequestSummary(
            count if count and complete else None,
            failures / count if count and complete else None,
            _percentiles(values), epoch_started_at, sampled_at, complete,
        )


class MeteredTelemetry(Telemetry):
    """Consume T011's completed request event and its existing measured duration."""

    def __init__(
        self, metrics: LocalMetrics, *, sink: LocalJsonSink | None = None,
        version: str = "0.1.0", span_capacity: int = MAX_SPANS,
    ) -> None:
        super().__init__(sink=sink, version=version, span_capacity=span_capacity)
        self.metrics = metrics

    def emit(
        self, event: str, *, level: str = "info", fields: EventFields | None = None,
    ) -> bool:
        if event in {"http_request_completed", "http_request_failed"}:
            try:
                if type(fields) is not EventFields:
                    raise MetricsUnavailable("Missing HTTP measurement")
                route = fields.route or "unmatched"
                method, _, template = route.partition(" ")
                if fields.method in _LABELS["method"]:
                    method = fields.method
                if method not in _LABELS["method"]:
                    method = "OTHER"
                if template not in self.metrics.routes:
                    template = "unmatched"
                labels = {
                    "route_template": template, "method": method,
                    "status_class": fields.status_class or "",
                }
                if fields.duration_ms is None:
                    raise MetricsUnavailable("Missing HTTP duration")
                self.metrics.record_http(labels, fields.duration_ms / 1000)
            except Exception:
                # The existing middleware preserves application exceptions; expose a failure latch.
                self.metrics.failed = True
        return super().emit(event, level=level, fields=fields)

    def record_dependency(
        self, dependency: str, operation: str, result: str,
        duration_ms: float | None = None, *, invalid_response: bool = False,
    ) -> None:
        try:
            if dependency == "bridge":
                labels = {"operation": operation, "provider": "local-bridge"}
                self.metrics.increment("bridge_requests_total", {**labels, "result": result})
                if duration_ms is None:
                    raise MetricsUnavailable("Missing bridge duration")
                self.metrics.observe("bridge_request_duration_seconds", labels, duration_ms / 1000)
                if invalid_response:
                    self.metrics.increment("bridge_response_validation_failures_total", {
                        "operation": operation, "failure_class": "invalid_response",
                    })
            elif dependency == "markdown":
                self.metrics.increment("markdown_sync_total", {"result": result})
                if duration_ms is None:
                    raise MetricsUnavailable("Missing sync duration")
                self.metrics.observe("markdown_sync_duration_seconds", {"result": result}, duration_ms / 1000)
            elif dependency == "sqlite":
                self.metrics.increment("sqlite_transactions_total", {"operation": operation, "result": result})
            else:
                raise MetricsUnavailable("Unsupported dependency")
        except Exception:
            self.metrics.failed = True
        super().record_dependency(
            dependency, operation, result, duration_ms, invalid_response=invalid_response,
        )

    def record_storage_failure(self, category: str, *, check: str = "database") -> None:
        try:
            if category == "BUSY":
                self.metrics.increment("sqlite_busy_total", {"operation": "unknown"})
            elif category == "INTEGRITY_FAILED":
                self.metrics.increment("sqlite_integrity_failures_total", {"check": check})
        except Exception:
            self.metrics.failed = True
        super().record_storage_failure(category, check=check)

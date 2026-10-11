"""Bounded, process-local T061 alert evaluator.

Observation IDs are bounded process-local sequence numbers, never metric labels.
They increase in event-time order within each input stream; health sequences are
consecutive. Replays keep their original ID and timestamp. Timestamps use the
same monotonic clock as T046, or an explicit synthetic timeline. Returned records
are the consumer boundary; no sink, worker, network, or learning writes are owned
here. A consumer must isolate diagnostic failures as T011 does.
"""

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import RLock
from time import monotonic
from typing import Literal

from backend.app.platform.metrics import (
    MAX_HTTP_RESPONSES,
    MAX_OBSERVATIONS,
    MAX_SERIES,
    MeteredTelemetry,
)
from backend.app.platform.telemetry import MAX_DURATION_MS, DependencyOutcome, EventFields, Telemetry

Category = Literal[
    "api_unavailable", "api_error_rate", "search_latency", "bridge_failure",
    "storage_contention", "source_parse_failure", "integrity_failure",
]
DataState = Literal["measured", "no_observations", "incomplete"]
Severity = Literal["ticket", "page-equivalent"]
_SOURCE_ID = re.compile(r"src_[A-Za-z0-9_-]{16}\Z", re.ASCII)
_RESULTS = frozenset({"success", "failure", "rejected", "unavailable"})


@dataclass(frozen=True)
class _Rule:
    severity: Severity
    threshold_id: str
    runbook: str


_RULES: dict[Category, _Rule] = {
    "api_unavailable": _Rule("page-equivalent", "health_2_consecutive_failures", "docs/runbooks/api-unavailable.md"),
    "api_error_rate": _Rule("ticket", "http_5xx_gt_1pct_300s", "docs/runbooks/api-error-rate.md"),
    "search_latency": _Rule("ticket", "benchmark_search_p95_gt_1s_300s", "docs/runbooks/search-performance.md"),
    "bridge_failure": _Rule("ticket", "bridge_qualifying_failures_gt_20pct_600s", "docs/runbooks/bridge-failure.md"),
    "storage_contention": _Rule("ticket", "sqlite_busy_per_transactions_gt_1pct_300s", "docs/runbooks/storage-integrity.md"),
    "source_parse_failure": _Rule("ticket", "any_newly_invalid_source", "docs/runbooks/source-sync.md"),
    "integrity_failure": _Rule("page-equivalent", "any_startup_integrity_failure", "docs/runbooks/storage-integrity.md"),
}


@dataclass(frozen=True)
class AlertRecord:
    category: Category
    severity: Severity
    state: Literal["active", "resolved"]
    started_at: float
    updated_at: float
    sample_count: int
    threshold_id: str
    runbook: str


@dataclass(frozen=True)
class AlertStatus:
    category: Category
    active: bool | None
    data_state: DataState
    sample_count: int
    latest_record: AlertRecord | None


@dataclass(frozen=True)
class AlertEvaluation:
    statuses: tuple[AlertStatus, ...]
    transitions: tuple[AlertRecord, ...]
    diagnostics_degraded: bool


def _identifier(value: int) -> None:
    if type(value) is not int or not 0 <= value <= 2**63 - 1:
        raise ValueError("Invalid observation sequence")


class _Window:
    """Exact retained observations; overflow never becomes a truncated estimate."""

    def __init__(self, seconds: int, capacity: int) -> None:
        self.seconds = seconds
        self.capacity = capacity
        self.samples: dict[int, tuple[float, float | None]] = {}
        self.retired_id = -1
        self.incomplete_until = -math.inf

    def prune(self, now: float) -> None:
        expired = [key for key, (at, _) in self.samples.items() if at <= now - self.seconds]
        for key in expired:
            del self.samples[key]
            self.retired_id = max(self.retired_id, key)

    def add(self, identifier: int, at: float, value: float | None, now: float) -> None:
        _identifier(identifier)
        self.prune(now)
        if at <= now - self.seconds:
            self.retired_id = max(self.retired_id, identifier)
            return
        existing = self.samples.get(identifier)
        if existing is not None:
            if existing != (at, value):
                self.incomplete_until = max(self.incomplete_until, at + self.seconds)
            return
        if identifier <= self.retired_id:
            # A late/replayed sequence cannot resurrect evicted evidence.
            self.incomplete_until = max(self.incomplete_until, at + self.seconds)
            return
        if len(self.samples) == self.capacity:
            oldest = min(self.samples, key=lambda key: self.samples[key][0])
            lost_at, _ = self.samples.pop(oldest)
            self.retired_id = max(self.retired_id, oldest)
            self.incomplete_until = max(self.incomplete_until, lost_at + self.seconds)
        self.samples[identifier] = (at, value)

    def values(self, now: float) -> tuple[list[float], DataState]:
        self.prune(now)
        if now < self.incomplete_until or any(value is None for _, value in self.samples.values()):
            return [], "incomplete"
        values = [value for _, value in self.samples.values() if value is not None]
        return values, "measured" if values else "no_observations"


class LocalAlerts:
    """Seven fixed categories, exact windows and one retained record per category.

    Rate windows are (now-window, now]. One measured denominator is sufficient,
    matching T046's startup HTTP window; there is no invented minimum traffic or
    extra hold period. Missing evidence keeps an active episode unresolved.
    Health/source/integrity state requires explicit recovery, never time expiry.
    """

    def __init__(self, telemetry: Telemetry | None = None) -> None:
        self._lock = RLock()
        self._telemetry = telemetry
        self.failed = False
        self.epoch_monotonic = monotonic()
        self.epoch_utc = datetime.now(UTC)
        self._now = -math.inf
        self._http = _Window(300, MAX_HTTP_RESPONSES)
        self._search = _Window(300, MAX_OBSERVATIONS)
        self._bridge = _Window(600, MAX_HTTP_RESPONSES)
        self._busy = _Window(300, MAX_HTTP_RESPONSES)
        self._transactions = _Window(300, MAX_HTTP_RESPONSES)
        self._latest: dict[str, tuple[int, float]] = {}
        self._health_failures: int | None = None
        self._health_samples = 0
        self._health_incomplete = False
        self._invalid_sources: frozenset[str] | None = None
        self._source_incomplete = False
        self._integrity_failed: bool | None = None
        self._records: dict[Category, AlertRecord] = {}
        self._active: dict[Category, bool] = {}

    def timestamp(self, at: float) -> datetime:
        return self.epoch_utc + timedelta(seconds=at - self.epoch_monotonic)

    def rule(self, category: Category) -> tuple[Severity, str]:
        rule = _RULES[category]
        return rule.severity, rule.runbook

    def _time(self, at: float | None) -> float:
        at = monotonic() if at is None else at
        if type(at) not in {int, float} or not math.isfinite(at) or at < 0:
            raise ValueError("Invalid observation time")
        self._now = max(self._now, at)
        return at

    def _accept_latest(self, stream: str, identifier: int, at: float) -> bool:
        _identifier(identifier)
        previous = self._latest.get(stream)
        if previous is not None and (identifier <= previous[0] or at < previous[1]):
            return False
        self._latest[stream] = (identifier, at)
        return True

    def record_http(
        self, fields: EventFields, *, observation_id: int,
        observed_at: float | None = None, benchmark_fixture: bool = False,
    ) -> None:
        """One completion, including 4xx in the denominator only.

        The caller must establish the named benchmark fixture before setting the
        flag. Ordinary HTTP timing is never treated as rendered-search evidence.
        """
        if type(fields) is not EventFields or type(benchmark_fixture) is not bool:
            raise ValueError("Invalid HTTP observation")
        _identifier(observation_id)
        with self._lock:
            at = self._time(observed_at)
            status = fields.status_class
            value = float(status == "5xx") if status in {"2xx", "3xx", "4xx", "5xx"} else None
            self._http.add(observation_id, at, value, self._now)
            if benchmark_fixture and fields.route == "GET /api/v1/word-forms":
                duration = fields.duration_ms
                seconds = (
                    duration / 1000 if type(duration) in {int, float} and duration is not None
                    and math.isfinite(duration) and 0 <= duration <= MAX_DURATION_MS else None
                )
                self._search.add(observation_id, at, seconds, self._now)

    def record_bridge(
        self, outcome: DependencyOutcome, *, observation_id: int,
        observed_at: float | None = None, qualifying_failure: bool | None = None,
    ) -> None:
        """Classify timeout/auth/quota at the owner; generic failure is unknown.

        T046 supplies result/invalid_response but cannot separate timeout, quota,
        or other transport failures. No exception message is accepted or retained.
        """
        if (type(outcome) is not DependencyOutcome or type(outcome.result) is not str
                or outcome.result not in _RESULTS):
            raise ValueError("Invalid bridge observation")
        if qualifying_failure is not None and type(qualifying_failure) is not bool:
            raise ValueError("Invalid bridge classification")
        if type(outcome.invalid_response) is not bool:
            raise ValueError("Invalid bridge validation outcome")
        _identifier(observation_id)
        value = (
            1.0 if outcome.invalid_response else 0.0 if outcome.result == "success"
            else float(qualifying_failure) if qualifying_failure is not None else None
        )
        with self._lock:
            at = self._time(observed_at)
            self._bridge.add(observation_id, at, value, self._now)

    def record_transaction(
        self, result: str, *, observation_id: int, observed_at: float | None = None,
    ) -> None:
        if type(result) is not str or result not in _RESULTS:
            raise ValueError("Invalid transaction outcome")
        _identifier(observation_id)
        with self._lock:
            at = self._time(observed_at)
            self._transactions.add(observation_id, at, 1.0, self._now)

    def record_storage_failure(
        self, category: str, *, observation_id: int, observed_at: float | None = None,
        check: str = "database",
    ) -> None:
        """Consume existing T046 categories; count busy separately from transactions."""
        if category not in {"BUSY", "INTEGRITY_FAILED"} or check not in {"startup", "database"}:
            raise ValueError("Invalid storage failure")
        _identifier(observation_id)
        with self._lock:
            at = self._time(observed_at)
            if category == "BUSY":
                self._busy.add(observation_id, at, 1.0, self._now)
            else:
                self.record_integrity(False, observation_id=observation_id, observed_at=at)

    def record_health(
        self, success: bool, *, observation_id: int, observed_at: float | None = None,
    ) -> None:
        if type(success) is not bool:
            raise ValueError("Invalid health probe")
        _identifier(observation_id)
        with self._lock:
            at = self._time(observed_at)
            previous = self._latest.get("health")
            if self._accept_latest("health", observation_id, at):
                if previous is not None and observation_id != previous[0] + 1:
                    self._health_failures = 0
                    self._health_samples = 0
                    self._health_incomplete = True
                self._health_samples = min(2, self._health_samples + 1)
                self._health_failures = 0 if success else min(2, (self._health_failures or 0) + 1)
                if success or self._health_failures == 2:
                    self._health_incomplete = False

    def record_integrity(
        self, success: bool, *, observation_id: int, observed_at: float | None = None,
    ) -> None:
        """Success must mean completed startup integrity validation, not a status read."""
        if type(success) is not bool:
            raise ValueError("Invalid integrity observation")
        _identifier(observation_id)
        with self._lock:
            at = self._time(observed_at)
            if self._accept_latest("integrity", observation_id, at):
                self._integrity_failed = not success

    def record_sources(
        self, statuses: Mapping[str, str], *, observation_id: int,
        observed_at: float | None = None,
    ) -> None:
        """Complete source snapshot; opaque source IDs stay private to the evaluator.

        Aggregate T046 source counts cannot detect replacements with equal counts.
        The sync owner must supply this observation after commit, including recovery.
        """
        if not isinstance(statuses, Mapping):
            raise ValueError("Invalid source observation")
        _identifier(observation_id)
        over_capacity = len(statuses) > MAX_SERIES
        if not over_capacity and any(type(key) is not str or not _SOURCE_ID.fullmatch(key)
               or type(value) is not str or value not in {"VALID", "INVALID", "MISSING"}
               for key, value in statuses.items()):
            raise ValueError("Invalid source observation")
        invalid = None if over_capacity else frozenset(
            key for key, value in statuses.items() if value == "INVALID"
        )
        with self._lock:
            at = self._time(observed_at)
            if self._accept_latest("sources", observation_id, at):
                if invalid is not None:
                    self._invalid_sources = invalid
                self._source_incomplete = over_capacity

    def sources_unavailable(self) -> None:
        with self._lock:
            self._source_incomplete = True

    def evaluate(self, *, now: float | None = None) -> AlertEvaluation:
        """Evaluate after each observation/batch and on window-expiration ticks.

        Return at most seven transitions and statuses; retain no episode history.
        A failed existing sink changes diagnostics only and cannot raise here.
        """
        with self._lock:
            at = self._time(now)
            if at < self._now:
                raise ValueError("Evaluation time moved backwards")
            conditions: dict[Category, tuple[bool | None, DataState, int]] = {}
            rates: tuple[tuple[Category, _Window, float], ...] = (
                ("api_error_rate", self._http, 0.01),
                ("bridge_failure", self._bridge, 0.20),
            )
            for category, window, threshold in rates:
                values, state = window.values(at)
                condition = None if state == "incomplete" else bool(values) and sum(values) / len(values) > threshold
                conditions[category] = (condition, state, len(window.samples))
            values, state = self._search.values(at)
            values.sort()
            search = (
                None if state == "incomplete" else bool(values)
                and values[math.ceil(len(values) * 0.95) - 1] > 1.0
            )
            conditions["search_latency"] = (search, state, len(self._search.samples))
            busy, busy_state = self._busy.values(at)
            transactions, transaction_state = self._transactions.values(at)
            storage_state: DataState = (
                "incomplete" if "incomplete" in {busy_state, transaction_state}
                else "measured" if transactions else "no_observations"
            )
            if busy and not transactions:
                storage_state = "incomplete"
            storage = None if storage_state == "incomplete" else (
                len(busy) / len(transactions) > 0.01 if transactions else False
            )
            conditions["storage_contention"] = (storage, storage_state, len(self._transactions.samples))
            conditions["api_unavailable"] = (
                None if self._health_incomplete or self._health_failures is None
                else self._health_failures >= 2,
                "incomplete" if self._health_incomplete else "no_observations"
                if self._health_failures is None else "measured",
                self._health_samples,
            )
            conditions["source_parse_failure"] = (
                None if self._source_incomplete or self._invalid_sources is None else bool(self._invalid_sources),
                "incomplete" if self._source_incomplete else "no_observations"
                if self._invalid_sources is None else "measured",
                len(self._invalid_sources or ()),
            )
            conditions["integrity_failure"] = (
                self._integrity_failed,
                "no_observations" if self._integrity_failed is None else "measured",
                0 if self._integrity_failed is None else 1,
            )
            telemetry = self._telemetry
            diagnostics_failed = telemetry is not None and (
                telemetry.span_retention_failed
                or (telemetry.sink is not None and telemetry.sink.failed)
            )
            if self.failed or (telemetry is not None and telemetry.span_retention_failed) or (
                isinstance(telemetry, MeteredTelemetry) and telemetry.metrics.failed
            ):
                diagnostics_failed = True
                timed_categories: tuple[Category, ...] = (
                    "api_error_rate", "search_latency", "bridge_failure", "storage_contention",
                )
                for category in timed_categories:
                    conditions[category] = (None, "incomplete", conditions[category][2])
            if self.failed:
                for category in conditions:
                    conditions[category] = (None, "incomplete", conditions[category][2])
            transitions: list[AlertRecord] = []
            statuses: list[AlertStatus] = []
            for category, rule in _RULES.items():
                condition, state, count = conditions[category]
                previous = self._active.get(category)
                if condition is not None:
                    if condition != previous and (condition or previous is True):
                        started = at if condition else self._records[category].started_at
                        record = AlertRecord(
                            category, rule.severity, "active" if condition else "resolved",
                            started, at, count, rule.threshold_id, rule.runbook,
                        )
                        self._records[category] = record
                        transitions.append(record)
                    self._active[category] = condition
                statuses.append(AlertStatus(
                    category, self._active.get(category), state, count, self._records.get(category),
                ))
            return AlertEvaluation(
                tuple(statuses), tuple(transitions),
                diagnostics_failed or any(status.data_state == "incomplete" for status in statuses),
            )

"""Observed SQLite eligibility history for T037-R1, independent of dashboard HTTP.

Polling Markdown cannot prove continuous on-disk validity. Evidence windows replay
retained SQL observations, not filesystem effective times or transaction commit times.
They are never a confirmed daily streak denominator.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Literal, cast
from zoneinfo import ZoneInfo

from backend.app.review.srs import PRODUCT_TIMEZONE, Schedule, require_aware
from sqlalchemy import Connection, Engine

HistoryKind = Literal["SOURCE", "LINK", "CARD", "REVIEW", "JOURNAL", "COVERAGE"]
CoverageReason = Literal[
    "NO_CONTINUOUS_SOURCE_OBSERVATION", "BEFORE_OPENING", "FUTURE_WINDOW",
    "FACT_LIMIT", "WINDOW_LIMIT", "CLOCK_ADJUSTED", "SOURCE_RECONCILIATION", "WINDOW_OPEN",
]
LifecycleReason = Literal["STARTUP", "SHUTDOWN", "SYNC_STARTED", "SYNC_FINISHED", "SYNC_FAILED"]


@dataclass(frozen=True)
class SourceState:
    status: Literal["VALID", "INVALID", "MISSING"]
    revision: int
    content_hash: str | None


@dataclass(frozen=True)
class LinkState:
    present: bool
    note_date: date


@dataclass(frozen=True)
class CardState:
    box: int
    due_at: datetime | None
    queue_revision: int


@dataclass(frozen=True)
class JournalState:
    state: Literal["PREPARED", "SOURCE_REPLACED", "COMMITTED", "ABORTED", "DEGRADED"]


@dataclass(frozen=True)
class CoverageState:
    status: Literal["UNKNOWN"]
    detail: str


HistoricalState = SourceState | LinkState | CardState | JournalState | CoverageState


@dataclass(frozen=True)
class HistoryFact:
    seq: int
    kind: HistoryKind
    reason: str
    observed_at: datetime
    timeline_at: datetime
    uncertain_since: datetime | None
    source_id: str | None
    word_form_id: str | None
    card_id: str | None
    operation_id: str | None
    review_event_id: str | None
    previous: HistoricalState | None
    resulting: HistoricalState | None


@dataclass(frozen=True)
class SourceEvidence:
    source_id: str
    source_fact_seq: int
    link_fact_seq: int


@dataclass(frozen=True)
class EligibilityWindow:
    """Half-open SQL observation interval, with evidence IDs and unconfirmed timing."""

    card_id: str
    word_form_id: str
    start: datetime
    end: datetime
    schedule: CardState
    schedule_fact_seq: int
    sources: tuple[SourceEvidence, ...]


@dataclass(frozen=True)
class HistoryCoverage:
    status: Literal["UNKNOWN"]
    reasons: tuple[CoverageReason, ...]
    opening_observed_at: datetime | None
    evidence_complete: bool
    last_seq: int


@dataclass(frozen=True)
class StudyDayHistory:
    study_date: date
    start: datetime
    end: datetime
    observed_until: datetime
    coverage: HistoryCoverage
    facts: tuple[HistoryFact, ...]
    windows: tuple[EligibilityWindow, ...]
    observed_due_card_ids: frozenset[str]
    # None is mandatory until continuity is independently supported, including empty days.
    eligible_due_card_ids: frozenset[str] | None = None


def record_coverage(
    connection: Connection, reason: LifecycleReason, *, operation_id: str | None = None,
) -> None:
    """Append uncertainty inside a caller-owned writer transaction, without committing."""
    if not connection.in_transaction() or not connection.get_execution_options().get(
        "sqlite_begin_immediate", False
    ):
        raise ValueError("History observation requires a caller-owned SQLite writer transaction")
    if reason not in {"STARTUP", "SHUTDOWN", "SYNC_STARTED", "SYNC_FINISHED", "SYNC_FAILED"}:
        raise ValueError("Invalid history lifecycle reason")
    connection.exec_driver_sql(
        "INSERT INTO study_history (seq,kind,reason,entity_key,operation_id,resulting_state,"
        "uncertain_since,observed_at,timeline_at) SELECT next_seq,'COVERAGE',?,json_array('coverage'),?,"
        "json_object('status','UNKNOWN','detail','NO_CONTINUOUS_SOURCE_OBSERVATION'),"
        "(SELECT timeline_at FROM study_history WHERE kind='COVERAGE' "
        "AND entity_key=json_array('coverage') ORDER BY seq DESC LIMIT 1),"
        "observed_at,timeline_at FROM study_history_clock WHERE ? IS NULL OR NOT EXISTS "
        "(SELECT 1 FROM study_history WHERE kind='COVERAGE' AND operation_id=? AND reason=?)",
        (reason, operation_id, operation_id, operation_id, reason),
    )


def observe_lifecycle(engine: Engine, reason: Literal["STARTUP", "SHUTDOWN"]) -> None:
    """Lifecycle uncertainty is separate from business facts; it confirms no mutation."""
    with (
        engine.connect().execution_options(sqlite_begin_immediate=True) as connection,
        connection.begin(),
    ):
        record_coverage(connection, reason)


def _instant(value: str | None) -> datetime | None:
    if value is None:
        return None
    instant = datetime.fromisoformat(value)
    require_aware(instant)
    return instant


def _state(kind: HistoryKind, value: str | None) -> HistoricalState | None:
    if value is None:
        return None
    state = json.loads(value)
    match kind:
        case "SOURCE":
            if state["status"] not in {"VALID", "INVALID", "MISSING"}:
                raise ValueError("Invalid historical source status")
            return SourceState(state["status"], state["revision"], state["hash"])
        case "LINK":
            return LinkState(bool(state["present"]), date.fromisoformat(state["note_date"]))
        case "CARD":
            schedule = Schedule(state["box"], _instant(state["due_at"]))
            return CardState(schedule.box, schedule.due_at, state["queue_revision"])
        case "JOURNAL":
            if state["state"] not in {"PREPARED", "SOURCE_REPLACED", "COMMITTED", "ABORTED", "DEGRADED"}:
                raise ValueError("Invalid historical journal state")
            return JournalState(state["state"])
        case "COVERAGE":
            if state["status"] != "UNKNOWN":
                raise ValueError("Unsupported historical coverage claim")
            return CoverageState("UNKNOWN", state["detail"])
        case _:
            raise ValueError("Unexpected historical state")


def _fact(row: Mapping[str, Any]) -> HistoryFact:
    kind = cast(HistoryKind, row["kind"])
    return HistoryFact(
        seq=row["seq"], kind=kind, reason=row["reason"],
        observed_at=datetime.fromisoformat(row["observed_at"]),
        timeline_at=datetime.fromisoformat(row["timeline_at"]),
        uncertain_since=_instant(row["uncertain_since"]),
        source_id=row["source_id"], word_form_id=row["word_form_id"], card_id=row["card_id"],
        operation_id=row["operation_id"], review_event_id=row["review_event_id"],
        previous=_state(kind, row["previous_state"]), resulting=_state(kind, row["resulting_state"]),
    )


def _windows(
    facts: tuple[HistoryFact, ...], start: datetime, end: datetime, limit: int,
) -> tuple[tuple[EligibilityWindow, ...], bool]:
    sources: dict[str, tuple[SourceState, int]] = {}
    links: dict[str, dict[str, int]] = {}
    forms_by_source: dict[str, set[str]] = {}
    cards: dict[str, tuple[str, CardState, int]] = {}
    card_by_form: dict[str, str] = {}
    segments: dict[str, tuple[datetime, tuple[SourceEvidence, ...]]] = {}
    windows: list[EligibilityWindow] = []
    evidence_size = 0
    truncated = False
    seeded = False

    def close(card_id: str, until: datetime) -> None:
        nonlocal truncated, evidence_size
        segment = segments.pop(card_id, None)
        if segment is None:
            return
        form_id, state, seq = cards[card_id]
        since, evidence = segment
        due_start = max(since, state.due_at) if state.due_at is not None else since
        if due_start < until:
            size = 1 + len(evidence)
            if evidence_size + size > limit:
                truncated = True
            else:
                windows.append(EligibilityWindow(card_id, form_id, due_start, until, state, seq, evidence))
                evidence_size += size

    def open_segment(card_id: str, since: datetime) -> None:
        form_id = cards[card_id][0]
        evidence = tuple(
            SourceEvidence(source_id, sources[source_id][1], link_seq)
            for source_id, link_seq in sorted(links.get(form_id, {}).items())
            if source_id in sources and sources[source_id][0].status == "VALID"
        )
        if evidence:
            segments[card_id] = (since, evidence)

    for fact in facts:
        if not seeded and fact.timeline_at >= start:
            for card_id in cards:
                open_segment(card_id, start)
            seeded = True
        instant = max(start, fact.timeline_at)
        affected: set[str] = set()
        if fact.kind == "SOURCE" and fact.source_id is not None:
            affected = {card_by_form[form] for form in forms_by_source.get(fact.source_id, set())
                        if form in card_by_form}
        elif fact.kind == "LINK" and fact.word_form_id is not None and fact.word_form_id in card_by_form:
            affected = {card_by_form[fact.word_form_id]}
        elif fact.kind == "CARD" and fact.card_id is not None:
            affected = {fact.card_id}
        if seeded:
            for card_id in affected:
                close(card_id, instant)

        if fact.kind == "SOURCE" and fact.source_id is not None:
            if isinstance(fact.resulting, SourceState):
                sources[fact.source_id] = (fact.resulting, fact.seq)
            else:
                sources.pop(fact.source_id, None)
        elif fact.kind == "LINK" and fact.source_id is not None and fact.word_form_id is not None:
            refs = links.setdefault(fact.word_form_id, {})
            related = forms_by_source.setdefault(fact.source_id, set())
            if isinstance(fact.resulting, LinkState) and fact.resulting.present:
                refs[fact.source_id] = fact.seq
                related.add(fact.word_form_id)
            else:
                refs.pop(fact.source_id, None)
                related.discard(fact.word_form_id)
        elif (fact.kind == "CARD" and fact.card_id is not None and fact.word_form_id is not None
              and isinstance(fact.resulting, CardState)):
            cards[fact.card_id] = (fact.word_form_id, fact.resulting, fact.seq)
            card_by_form[fact.word_form_id] = fact.card_id
        if seeded:
            for card_id in affected:
                if card_id in cards:
                    open_segment(card_id, instant)

    if not seeded:
        for card_id in cards:
            open_segment(card_id, start)
    for card_id in tuple(segments):
        close(card_id, end)
    return tuple(windows), truncated


class StudyHistoryReader:
    """Bound memory by facts/windows per day; query only retained evidence, never live state."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def for_date(
        self, study_date: date, *, as_of: datetime | None = None, fact_limit: int = 10_000,
    ) -> StudyDayHistory:
        """Read start-of-day seeds and ordered daily transitions in one read snapshot.

        A limit hit returns incomplete evidence and UNKNOWN, never an empty denominator.
        Consumers must use eligible_due_card_ids for streaks, not observed_due_card_ids.
        """
        if type(study_date) is not date or type(fact_limit) is not int or not 1 <= fact_limit <= 10_000:
            raise ValueError("Invalid historical study-date query")
        now = as_of if as_of is not None else datetime.now(UTC)
        require_aware(now)
        zone = ZoneInfo(PRODUCT_TIMEZONE)
        try:
            start = datetime.combine(study_date, time.min, tzinfo=zone).astimezone(UTC)
            end = datetime.combine(study_date + timedelta(days=1), time.min, tzinfo=zone).astimezone(UTC)
        except (OverflowError, ValueError):
            raise ValueError("Invalid historical study-date query") from None
        until = min(end, max(start, now.astimezone(UTC)))
        first = start.isoformat(timespec="microseconds").replace("+00:00", "Z")
        last = until.isoformat(timespec="microseconds").replace("+00:00", "Z")
        reasons: list[CoverageReason] = ["NO_CONTINUOUS_SOURCE_OBSERVATION"]
        with self.engine.connect() as connection, connection.begin():
            opening = connection.exec_driver_sql(
                "SELECT observed_at FROM study_history WHERE kind='COVERAGE' "
                "AND entity_key=json_array('coverage') ORDER BY seq LIMIT 1",
            ).scalar_one_or_none()
            last_seq: int = connection.exec_driver_sql(
                "SELECT coalesce(max(seq),0) FROM study_history",
            ).scalar_one()
            # Latest pre-day fact per entity, not a lifetime of raw events in Python.
            rows = connection.exec_driver_sql(
                "WITH seeds AS (SELECT h.* FROM study_history h WHERE h.timeline_at<? "
                "AND h.kind IN ('SOURCE','LINK','CARD','JOURNAL','COVERAGE') AND NOT EXISTS "
                "(SELECT 1 FROM study_history newer WHERE newer.kind=h.kind "
                "AND newer.entity_key=h.entity_key AND newer.seq>h.seq AND newer.timeline_at<?) "
                "AND (h.kind NOT IN ('SOURCE','LINK') OR (h.resulting_state IS NOT NULL "
                "AND (h.kind!='LINK' OR json_extract(h.resulting_state,'$.present')=1))) "
                "AND (h.kind!='JOURNAL' OR json_extract(h.resulting_state,'$.state') "
                "IN ('PREPARED','SOURCE_REPLACED','DEGRADED'))), "
                "daily AS (SELECT * FROM study_history WHERE timeline_at>=? AND timeline_at<?) "
                "SELECT * FROM (SELECT * FROM seeds UNION ALL SELECT * FROM daily) ORDER BY seq LIMIT ?",
                (first, first, first, last, fact_limit + 1),
            ).mappings().all()
            adjusted = connection.exec_driver_sql(
                "SELECT 1 FROM study_history WHERE timeline_at>=? AND observed_at<? "
                "AND observed_at!=timeline_at LIMIT 1", (first, last),
            ).first() is not None
        opening_at = _instant(opening)
        if opening_at is None or start < opening_at:
            reasons.append("BEFORE_OPENING")
        if now.astimezone(UTC) < start:
            reasons.append("FUTURE_WINDOW")
        elif until < end:
            reasons.append("WINDOW_OPEN")
        if adjusted:
            reasons.append("CLOCK_ADJUSTED")
        limited = len(rows) > fact_limit
        facts = tuple(_fact(row) for row in rows[:fact_limit])
        if any(f.kind == "JOURNAL" or f.reason in {"STARTUP", "SYNC_STARTED", "SYNC_FAILED"}
               for f in facts):
            reasons.append("SOURCE_RECONCILIATION")
        if limited:
            reasons.append("FACT_LIMIT")
            windows: tuple[EligibilityWindow, ...] = ()
            window_limit = False
        else:
            windows, window_limit = _windows(facts, start, until, fact_limit)
            if window_limit:
                reasons.append("WINDOW_LIMIT")
        return StudyDayHistory(
            study_date, start, end, until,
            HistoryCoverage(
                "UNKNOWN", tuple(reasons), opening_at,
                not limited and not window_limit and not adjusted, last_seq,
            ),
            facts, windows, frozenset(window.card_id for window in windows),
        )

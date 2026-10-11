"""Observed SQLite eligibility history for T037-R1, independent of dashboard HTTP.

The reader replays committed SQLite observations after the opening snapshot.
Filesystem edit times and physical transaction commit times are not inferred.
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
    status: Literal["KNOWN", "UNKNOWN"]
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
    # None means required committed-state evidence is missing or ambiguous.
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
    segments: dict[
        str, tuple[datetime, tuple[SourceEvidence, ...], CardState, int, str]
    ] = {}
    windows: list[EligibilityWindow] = []
    evidence_size = 0
    truncated = False
    def close(card_id: str, until: datetime) -> None:
        nonlocal truncated, evidence_size
        segment = segments.pop(card_id, None)
        if segment is None:
            return
        since, evidence, state, seq, form_id = segment
        due_start = max(since, state.due_at) if state.due_at is not None else since
        if due_start < until:
            size = 1 + len(evidence)
            if evidence_size + size > limit:
                truncated = True
            else:
                windows.append(EligibilityWindow(card_id, form_id, due_start, until, state, seq, evidence))
                evidence_size += size

    def open_segment(card_id: str, since: datetime) -> None:
        card = cards.get(card_id)
        if card is None:
            return
        form_id, state, seq = card
        evidence = tuple(
            SourceEvidence(source_id, sources[source_id][1], link_seq)
            for source_id, link_seq in sorted(links.get(form_id, {}).items())
            if source_id in sources and sources[source_id][0].status == "VALID"
        )
        if evidence:
            segments[card_id] = (since, evidence, state, seq, form_id)

    def affected_cards(fact: HistoryFact) -> set[str]:
        if fact.kind == "SOURCE" and fact.source_id is not None:
            return {
                card_by_form[form_id]
                for form_id in forms_by_source.get(fact.source_id, set())
                if form_id in card_by_form
            }
        if fact.kind == "LINK" and fact.word_form_id is not None:
            card_id = card_by_form.get(fact.word_form_id)
            return {card_id} if card_id is not None else set()
        if fact.kind == "CARD" and fact.card_id is not None:
            return {fact.card_id}
        return set()

    def apply(fact: HistoryFact) -> None:
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
        elif (
            fact.kind == "CARD"
            and fact.card_id is not None
            and fact.word_form_id is not None
            and isinstance(fact.resulting, CardState)
        ):
            cards[fact.card_id] = (fact.word_form_id, fact.resulting, fact.seq)
            card_by_form[fact.word_form_id] = fact.card_id

    index = 0
    while index < len(facts) and facts[index].timeline_at < start:
        apply(facts[index])
        index += 1
    for card_id in cards:
        open_segment(card_id, start)
    while index < len(facts):
        instant = facts[index].timeline_at
        if instant >= end:
            break
        batch: list[HistoryFact] = []
        while index < len(facts) and facts[index].timeline_at == instant:
            batch.append(facts[index])
            index += 1
        affected: set[str] = set()
        for fact in batch:
            affected.update(affected_cards(fact))
        for card_id in affected:
            close(card_id, instant)
        for fact in batch:
            apply(fact)
        for card_id in affected:
            open_segment(card_id, instant)
    for card_id in tuple(segments):
        close(card_id, end)
    return tuple(windows), truncated


class StudyHistoryReader:
    """Bound memory by facts/windows per day; query only retained evidence, never live state."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def for_date(
        self,
        study_date: date,
        *,
        as_of: datetime | None = None,
        fact_limit: int = 10_000,
        connection: Connection | None = None,
    ) -> StudyDayHistory:
        """Read one date, optionally inside a caller-owned read transaction."""
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
        def read(read_connection: Connection) -> StudyDayHistory:
            opening = read_connection.exec_driver_sql(
                "SELECT timeline_at FROM study_history WHERE kind='COVERAGE' "
                "AND reason='OPENING' AND entity_key=json_array('coverage') ORDER BY seq LIMIT 1",
            ).scalar_one_or_none()
            last_seq: int = read_connection.exec_driver_sql(
                "SELECT coalesce(max(seq),0) FROM study_history",
            ).scalar_one()
            rows = read_connection.exec_driver_sql(
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
            adjusted = read_connection.exec_driver_sql(
                "SELECT 1 FROM study_history WHERE timeline_at>=? AND timeline_at<? "
                "AND observed_at!=timeline_at LIMIT 1", (first, last),
            ).first() is not None
            return self._build_day(
                study_date, start, end, until, now, opening, last_seq, rows, adjusted, fact_limit,
            )

        if connection is not None:
            if not connection.in_transaction():
                raise ValueError("Historical read requires a caller-owned transaction")
            return read(connection)
        with self.engine.connect() as owned, owned.begin():
            return read(owned)

    @staticmethod
    def _build_day(
        study_date: date,
        start: datetime,
        end: datetime,
        until: datetime,
        now: datetime,
        opening: str | None,
        last_seq: int,
        rows: list[Mapping[str, Any]],
        adjusted: bool,
        fact_limit: int,
    ) -> StudyDayHistory:
        opening_at = _instant(opening)
        reasons: list[CoverageReason] = []
        if opening_at is None:
            reasons.extend(("NO_CONTINUOUS_SOURCE_OBSERVATION", "BEFORE_OPENING"))
        elif start < opening_at:
            reasons.append("BEFORE_OPENING")
        if now.astimezone(UTC) < start:
            reasons.append("FUTURE_WINDOW")
        elif until < end:
            reasons.append("WINDOW_OPEN")
        if adjusted:
            reasons.append("CLOCK_ADJUSTED")
        limited = len(rows) > fact_limit
        facts = tuple(_fact(row) for row in rows[:fact_limit])
        unresolved: set[str] = set()
        for fact in facts:
            if fact.kind != "JOURNAL" or fact.operation_id is None:
                continue
            if isinstance(fact.resulting, JournalState) and fact.resulting.state in {
                "PREPARED", "SOURCE_REPLACED", "DEGRADED",
            }:
                unresolved.add(fact.operation_id)
            else:
                unresolved.discard(fact.operation_id)
        if unresolved:
            reasons.append("SOURCE_RECONCILIATION")
        if limited:
            reasons.append("FACT_LIMIT")
            windows: tuple[EligibilityWindow, ...] = ()
            window_limit = False
        else:
            windows, window_limit = _windows(facts, start, until, fact_limit)
            if window_limit:
                reasons.append("WINDOW_LIMIT")
        blocking = {
            "NO_CONTINUOUS_SOURCE_OBSERVATION", "BEFORE_OPENING", "FUTURE_WINDOW",
            "CLOCK_ADJUSTED", "SOURCE_RECONCILIATION", "FACT_LIMIT", "WINDOW_LIMIT",
        }
        known = not any(reason in blocking for reason in reasons)
        eligible = frozenset(window.card_id for window in windows) if known else None
        return StudyDayHistory(
            study_date, start, end, until,
            HistoryCoverage("KNOWN" if known else "UNKNOWN", tuple(reasons), opening_at,
                            not limited and not window_limit and not adjusted, last_seq),
            facts, windows, frozenset(window.card_id for window in windows), eligible,
        )

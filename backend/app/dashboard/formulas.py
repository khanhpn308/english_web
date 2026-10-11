"""Read-only learning metrics and formulas over authoritative persisted facts."""

from collections.abc import Callable, Mapping, Set
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from hashlib import sha256
from typing import Any
from zoneinfo import ZoneInfo

from backend.app.assessment.questions import QuizResult
from backend.app.review.queue import utc_text
from backend.app.review.srs import PRODUCT_TIMEZONE, Rating, require_aware
from backend.app.dashboard.history import (
    CardState, EligibilityWindow, StudyDayHistory, StudyHistoryReader,
)
from sqlalchemy import Connection, Engine

_RATINGS: tuple[Rating, ...] = ("AGAIN", "HARD", "GOOD", "EASY")
_STUDY_ZONE = ZoneInfo(PRODUCT_TIMEZONE)
_HISTORY_FACT_LIMIT = 10_000
_HISTORY_DAY_LIMIT = 10_000


class DashboardRangeError(ValueError):
    """A study-date range is invalid or cannot be represented in UTC."""


def study_date(instant: datetime) -> date:
    require_aware(instant)
    return instant.astimezone(_STUDY_ZONE).date()


def date_range(
    today: date, from_date: date | None = None, to_date: date | None = None,
) -> tuple[str, str]:
    """Inclusive Bangkok days, represented by inclusive UTC microsecond bounds."""
    try:
        last = to_date if to_date is not None else today
        first = from_date if from_date is not None else last - timedelta(days=27)
        if first > last or (last - first).days >= 366:
            raise DashboardRangeError("Invalid study-date range")
        start = datetime.combine(first, time.min, tzinfo=_STUDY_ZONE)
        end = datetime.combine(last, time.max, tzinfo=_STUDY_ZONE)
        return utc_text(start), utc_text(end)
    except (ValueError, OverflowError):
        raise DashboardRangeError("Invalid study-date range") from None


def average_rating_bucket(count: int, rating_sum: int) -> Rating | None:
    """Owner-approved ordinal mean with exact half-up rounding."""
    if count == 0:
        return None
    assert count > 0 and count <= rating_sum <= 4 * count, "Invalid persisted rating aggregate"
    bucket = (2 * rating_sum + count) // (2 * count)
    return _RATINGS[bucket - 1]


def day_is_complete(
    eligible_due_cards: Set[str] | None,
    completed_cards: Set[str],
    *,
    completed_new_card: bool,
    terminal_submitted_quiz: bool,
) -> bool | None:
    """The caller supplies the historical denominator; None preserves uncertainty."""
    if eligible_due_cards is None:
        return None
    if eligible_due_cards:
        return eligible_due_cards <= completed_cards
    return completed_new_card or terminal_submitted_quiz


def consecutive_completed_days(
    completion: Mapping[date, bool | None], *, as_of: date,
) -> int | None:
    """Count backwards from an explicit day; unknown history is not a broken streak."""
    days = 0
    day = as_of
    while True:
        complete = completion.get(day)
        if complete is None:
            return None
        if not complete:
            return days
        days += 1
        if day == date.min:
            return days
        day -= timedelta(days=1)


@dataclass(frozen=True)
class DashboardProjection:
    metrics: dict[str, Any]
    as_of: date
    current_days: int | None
    streak_reason: str | None = None


class DashboardService:
    def __init__(
        self, engine: Engine, *, clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.engine = engine
        self.clock = clock or (lambda: datetime.now(UTC))
        self.history = StudyHistoryReader(engine)

    @staticmethod
    def _day_completion(
        connection: Connection, history: StudyDayHistory, limit: int,
    ) -> tuple[bool | None, int, str | None]:
        eligible = history.eligible_due_card_ids
        if eligible is None:
            reason = next((r for r in history.coverage.reasons if r != "WINDOW_OPEN"), "UNKNOWN_HISTORY")
            return None, 0, reason
        if limit < 1:
            return None, 0, "STREAK_WORK_LIMIT"
        first, last = utc_text(history.start), utc_text(history.observed_until)
        comparator = "<=" if history.observed_until < history.end else "<"
        quizzes = connection.exec_driver_sql(
            "SELECT a.id,a.result_payload,a.result_digest,a.submitted_at,a.submission_operation_id,"
            "q.operation_id,q.submitted_at AS recorded_submission,c.id AS commit_id FROM quiz_attempts a "
            "LEFT JOIN study_history_quiz_submissions q ON q.attempt_id=a.id "
            "LEFT JOIN study_history_commits c ON q.seq BETWEEN c.first_quiz_seq AND c.last_quiz_seq "
            "WHERE a.status='SUBMITTED' AND a.submitted_at>=? "
            f"AND a.submitted_at{comparator}? AND (c.id IS NULL OR c.effective_at{comparator}?) "
            "ORDER BY a.submitted_at,a.id LIMIT ?", (first, last, last, limit + 1),
        )
        terminal: dict[str, tuple[datetime, str, int, frozenset[tuple[str | None, str | None, Rating]]]] = {}
        quiz_work = 0
        try:
            for row in quizzes.mappings():
                result = QuizResult.model_validate_json(row["result_payload"])
                quiz_work += 1 + len(result.question_results) + len(result.review_handoffs)
                if quiz_work > limit:
                    return None, limit, "QUIZ_EVIDENCE_LIMIT"
                if (
                    result.attempt_id != row["id"] or utc_text(result.submitted_at) != row["submitted_at"]
                    or sha256(row["result_payload"].encode("utf-8")).hexdigest() != row["result_digest"]
                ):
                    raise ValueError("Invalid persisted terminal quiz result")
                if row["commit_id"] is None:
                    return None, quiz_work, "MISSING_QUIZ_COMMIT_EVIDENCE"
                if (
                    row["operation_id"] != row["submission_operation_id"]
                    or row["recorded_submission"] != row["submitted_at"]
                ):
                    raise ValueError("Invalid persisted quiz operation identity")
                handoffs = frozenset(
                    (h.review_event_id, h.card_id, h.rating) for h in result.review_handoffs
                    if h.status == "APPLIED"
                )
                terminal[row["id"]] = (
                    result.submitted_at, row["operation_id"], row["commit_id"], handoffs,
                )
        finally:
            quizzes.close()
        review_facts = {
            fact.review_event_id: fact
            for fact in history.facts
            if fact.kind == "REVIEW" and fact.review_event_id is not None
        }
        applied = {
            fact.review_event_id: fact for fact in history.facts
            if fact.kind == "CARD" and fact.reason == "SCHEDULE" and fact.review_event_id is not None
        }
        remaining = limit - quiz_work
        rows = connection.exec_driver_sql(
            "SELECT e.*,c.id AS commit_id FROM review_events e "
            "LEFT JOIN study_history h ON h.kind='REVIEW' AND h.review_event_id=e.id "
            "LEFT JOIN study_history_commits c ON h.seq BETWEEN c.first_seq AND c.last_seq "
            "WHERE e.source IN ('FLASHCARD','QUIZ') AND e.reviewed_at>=? "
            f"AND e.reviewed_at{comparator}? AND (c.id IS NULL OR c.effective_at{comparator}?) "
            "ORDER BY e.reviewed_at,e.id LIMIT ?", (first, last, last, remaining + 1),
        ).mappings().all()
        work = quiz_work + len(rows)
        if len(rows) > remaining:
            return None, limit, "REVIEW_EVIDENCE_LIMIT"
        obligations: dict[str, set[int]] = {}
        windows_by_card: dict[str, list[EligibilityWindow]] = {}
        obligation_starts: dict[tuple[str, int], datetime] = {}
        for window in history.windows:
            obligations.setdefault(window.card_id, set()).add(window.obligation_seq)
            windows_by_card.setdefault(window.card_id, []).append(window)
            key = (window.card_id, window.obligation_seq)
            obligation_starts[key] = min(window.start, obligation_starts.get(key, window.start))
        matched: dict[str, set[int]] = {}
        completed_new_card = False
        for row in rows:
            fact, schedule = review_facts.get(row["id"]), applied.get(row["id"])
            if fact is None or schedule is None or not isinstance(schedule.previous, CardState):
                return None, work, "MISSING_REVIEW_PREDECESSOR"
            reviewed_at = datetime.fromisoformat(row["reviewed_at"])
            require_aware(reviewed_at)
            if (
                fact.card_id != row["card_id"] or schedule.card_id != row["card_id"]
                or fact.operation_id != row["operation_id"] or schedule.operation_id != row["operation_id"]
                or fact.commit_id != schedule.commit_id or fact.seq >= schedule.seq
                or schedule.commit_id != row["commit_id"]
                or not isinstance(schedule.resulting, CardState)
                or schedule.resulting.box != row["next_box"]
                or schedule.resulting.due_at != datetime.fromisoformat(row["next_due_at"])
            ):
                raise ValueError("Invalid persisted review handoff")
            if row["source"] == "QUIZ":
                quiz = terminal.get(row["attempt_id"])
                if quiz is None or quiz[1] != row["operation_id"] or quiz[2] != fact.commit_id:
                    return None, work, "MISSING_QUIZ_HANDOFF"
                if (row["id"], row["card_id"], row["rating"]) not in quiz[3]:
                    raise ValueError("Invalid persisted terminal quiz handoff")
                if reviewed_at != quiz[0]:
                    raise ValueError("Invalid persisted quiz review timestamp")
            completed_new_card |= schedule.previous.box == 0
            for window in windows_by_card.get(row["card_id"], ()):
                work += 1
                if work > limit:
                    return None, limit, "STREAK_WORK_LIMIT"
                if (
                    fact.seq > window.obligation_seq and fact.effective_at is not None
                    and window.start <= fact.effective_at <= window.end
                    and (window.end_seq is None or fact.seq <= window.end_seq)
                ):
                    if reviewed_at < obligation_starts[(window.card_id, window.obligation_seq)]:
                        return None, work, "ACTIVITY_ORDER_AMBIGUOUS"
                    matched.setdefault(row["card_id"], set()).add(window.obligation_seq)
        completed_cards = {
            card_id for card_id, expected in obligations.items()
            if expected <= matched.get(card_id, set())
        }
        complete = day_is_complete(
            eligible,
            completed_cards,
            completed_new_card=completed_new_card,
            terminal_submitted_quiz=bool(terminal),
        )
        return complete, work, None

    def _current_days(
        self, connection: Connection, now: datetime, today: date,
    ) -> tuple[int | None, str | None]:
        completion: dict[date, bool | None] = {}
        remaining = _HISTORY_FACT_LIMIT
        anchor = today
        for offset in range(_HISTORY_DAY_LIMIT):
            try:
                day = today - timedelta(days=offset)
            except OverflowError:
                return None, "DATE_BOUNDARY"
            if remaining < 1:
                return None, "STREAK_WORK_LIMIT"
            history = self.history.for_date(
                day, as_of=now, fact_limit=remaining, connection=connection,
            )
            remaining -= len(history.facts) + len(history.windows)
            complete, work, reason = self._day_completion(connection, history, remaining)
            remaining -= work
            completion[day] = complete
            if complete is None:
                return None, reason
            if day == today and not complete:
                if today == date.min:
                    return None, "DATE_BOUNDARY"
                anchor = today - timedelta(days=1)
                continue
            if not complete:
                return consecutive_completed_days(completion, as_of=anchor), None
            if day == date.min:
                return None, "DATE_BOUNDARY"
        return None, "STREAK_DAY_LIMIT"

    def project(
        self, *, from_date: date | None = None, to_date: date | None = None,
    ) -> DashboardProjection:
        now = self.clock()
        today = study_date(now)
        start, end = date_range(today, from_date, to_date)
        with self.engine.connect() as conn, conn.begin():
            # Keep the canonical ReviewService.queue predicate, including NEW/null dueAt.
            due: int = conn.exec_driver_sql(
                "SELECT count(*) FROM review_cards c JOIN word_forms f "
                "ON f.id=c.word_form_id WHERE (c.box=0 OR c.due_at<=?) AND EXISTS "
                "(SELECT 1 FROM word_form_sources w JOIN source_files s ON s.id=w.source_id "
                "WHERE w.word_form_id=c.word_form_id AND s.status='VALID')",
                (utc_text(now),),
            ).scalar_one()
            # shortcut: history time filters lack global indexes; add in the Host persistence task.
            ratings = conn.exec_driver_sql(
                "SELECT count(*) AS count, coalesce(sum(CASE rating "
                "WHEN 'AGAIN' THEN 1 WHEN 'HARD' THEN 2 WHEN 'GOOD' THEN 3 "
                "WHEN 'EASY' THEN 4 END),0) AS rating_sum FROM review_events "
                "WHERE source='FLASHCARD' AND reviewed_at>=? AND reviewed_at<=?",
                (start, end),
            ).mappings().one()
            # Aggregate durable result snapshots, never drafts or live source relationships.
            # Source: https://www.sqlite.org/json1.html#the_json_each_and_json_tree_table_valued_functions
            scores = conn.exec_driver_sql(
                "SELECT score.key AS kind, "
                "sum(json_extract(score.value,'$.total')) AS total, "
                "sum(json_extract(score.value,'$.attempted')) AS attempted, "
                "sum(json_extract(score.value,'$.correct')) AS correct "
                "FROM quiz_attempts a JOIN json_each(a.result_payload,'$.objectiveScores') score "
                "WHERE a.status='SUBMITTED' AND a.submitted_at>=? AND a.submitted_at<=? "
                "AND score.key IN ('mcq','cloze') GROUP BY score.key",
                (start, end),
            ).mappings().all()
            writing = conn.exec_driver_sql(
                "SELECT count(json_extract(score.value,'$.selfScore')) AS scored, "
                "avg(json_extract(score.value,'$.selfScore')) AS average "
                "FROM quiz_attempts a JOIN json_each(a.result_payload,'$.writingSelfScores') score "
                "WHERE a.status='SUBMITTED' AND a.submitted_at>=? AND a.submitted_at<=?",
                (start, end),
            ).mappings().one()
            current_days, streak_reason = self._current_days(conn, now, today)

        objective: dict[str, dict[str, int | float | None]] = {
            kind: {"correct": 0, "total": 0, "attempted": 0, "accuracy": None}
            for kind in ("mcq", "cloze")
        }
        for score in scores:
            attempted = score["attempted"]
            objective[score["kind"]] = {
                "correct": score["correct"], "total": score["total"], "attempted": attempted,
                "accuracy": score["correct"] / attempted if attempted else None,
            }
        metrics: dict[str, Any] = {
            "dueCards": due,
            "flashcardSelfRating": {
                "count": ratings["count"],
                "averageBucket": average_rating_bucket(ratings["count"], ratings["rating_sum"]),
            },
            "objectiveAccuracy": objective,
            "writingSelfScore": {"scored": writing["scored"], "average": writing["average"]},
        }
        return DashboardProjection(
            metrics=metrics, as_of=today, current_days=current_days, streak_reason=streak_reason,
        )

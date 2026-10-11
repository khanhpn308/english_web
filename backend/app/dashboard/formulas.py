"""Read-only learning metrics and formulas over authoritative persisted facts."""

from collections.abc import Callable, Mapping, Set
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from backend.app.review.queue import utc_text
from backend.app.review.srs import PRODUCT_TIMEZONE, Rating, require_aware
from backend.app.dashboard.history import StudyDayHistory, StudyHistoryReader
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


class DashboardService:
    def __init__(
        self, engine: Engine, *, clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.engine = engine
        self.clock = clock or (lambda: datetime.now(UTC))
        self.history = StudyHistoryReader(engine)

    @staticmethod
    def _day_completion(connection: Connection, history: StudyDayHistory) -> bool | None:
        eligible = history.eligible_due_card_ids
        if eligible is None:
            return None
        windows_by_card: dict[str, list[int]] = {}
        for index, window in enumerate(history.windows):
            windows_by_card.setdefault(window.card_id, []).append(index)
        review_facts = {
            fact.review_event_id: fact
            for fact in history.facts
            if fact.kind == "REVIEW" and fact.review_event_id is not None
        }
        matched: set[int] = set()
        if windows_by_card:
            rows = connection.exec_driver_sql(
                "SELECT id,card_id,reviewed_at FROM review_events "
                "WHERE source IN ('FLASHCARD','QUIZ') "
                "AND reviewed_at>=? AND reviewed_at<? ORDER BY reviewed_at,id LIMIT ?",
                (history.start.isoformat(timespec="microseconds").replace("+00:00", "Z"),
                 history.observed_until.isoformat(timespec="microseconds").replace("+00:00", "Z"),
                 _HISTORY_FACT_LIMIT + 1),
            ).mappings().all()
            if len(rows) > _HISTORY_FACT_LIMIT:
                return None
            for row in rows:
                fact = review_facts.get(row["id"])
                if fact is None:
                    continue
                reviewed_at = datetime.fromisoformat(row["reviewed_at"])
                for index in windows_by_card.get(row["card_id"], ()):
                    window = history.windows[index]
                    if (
                        fact.seq > window.schedule_fact_seq
                        and window.start <= reviewed_at < window.end
                    ):
                        matched.add(index)
        completed_cards = {
            card_id
            for card_id, indexes in windows_by_card.items()
            if all(index in matched for index in indexes)
        }
        completed_new_card = any(
            index in matched and history.windows[index].schedule.box == 0
            for index in range(len(history.windows))
        )
        terminal_submitted_quiz = connection.exec_driver_sql(
            "SELECT 1 FROM quiz_attempts WHERE status='SUBMITTED' "
            "AND submitted_at>=? AND submitted_at<? AND json_valid(result_payload) LIMIT 1",
            (history.start.isoformat(timespec="microseconds").replace("+00:00", "Z"),
             history.observed_until.isoformat(timespec="microseconds").replace("+00:00", "Z")),
        ).first() is not None
        return day_is_complete(
            eligible,
            completed_cards,
            completed_new_card=completed_new_card,
            terminal_submitted_quiz=terminal_submitted_quiz,
        )

    def _current_days(self, connection: Connection, now: datetime, today: date) -> int | None:
        completion: dict[date, bool | None] = {}
        today_history = self.history.for_date(
            today, as_of=now, fact_limit=_HISTORY_FACT_LIMIT, connection=connection,
        )
        today_complete = self._day_completion(connection, today_history)
        if today_complete is None:
            return None
        if today_complete:
            completion[today] = True
            anchor = today
        else:
            anchor = today - timedelta(days=1)
        for offset in range(_HISTORY_DAY_LIMIT):
            try:
                day = anchor - timedelta(days=offset)
            except OverflowError:
                return None
            history = today_history if day == today else self.history.for_date(
                day, as_of=now, fact_limit=_HISTORY_FACT_LIMIT, connection=connection,
            )
            complete = today_complete if day == today else self._day_completion(connection, history)
            completion[day] = complete
            if complete is None:
                return None
            if not complete:
                return consecutive_completed_days(completion, as_of=anchor)
            if day == date.min:
                return consecutive_completed_days(completion, as_of=anchor)
        return None

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
            current_days = self._current_days(conn, now, today)

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
        return DashboardProjection(metrics=metrics, as_of=today, current_days=current_days)

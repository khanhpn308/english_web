"""Read-only learning metrics and formulas over authoritative persisted facts."""

from collections.abc import Callable, Mapping, Set
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from backend.app.review.queue import utc_text
from backend.app.review.srs import PRODUCT_TIMEZONE, Rating, require_aware
from sqlalchemy import Engine

_RATINGS: tuple[Rating, ...] = ("AGAIN", "HARD", "GOOD", "EASY")
_STUDY_ZONE = ZoneInfo(PRODUCT_TIMEZONE)


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

    def project(
        self, *, from_date: date | None = None, to_date: date | None = None,
    ) -> DashboardProjection:
        now = self.clock()
        today = study_date(now)
        start, end = date_range(today, from_date, to_date)
        # Source: https://docs.sqlalchemy.org/en/21/core/connections.html#using-transactions
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
        # Host persistence must supply daily denominators/reset history before this is known.
        return DashboardProjection(metrics=metrics, as_of=today, current_days=None)

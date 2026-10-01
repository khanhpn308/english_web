"""Review facts and transaction-scoped persistence primitives for later orchestration.

The caller owns IDs, time and the T005 writer transaction. T014's local_write callback
can commit these primitives with its receipt; this module never claims operation keys.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from backend.app.review.srs import Rating, Schedule, require_aware, transition, validate_rating
from backend.app.vocabulary.models import SourceReference
from sqlalchemy import Connection

ReviewSource = Literal["FLASHCARD", "QUIZ"]


class InactiveCardError(ValueError):
    """An inactive form cannot acquire a new event or schedule."""


class ReviewOperationMismatchError(ValueError):
    """A review operation/card pair already belongs to another review intent."""


def _source(source: str) -> ReviewSource:
    match source:
        case "FLASHCARD" | "QUIZ":
            return source
        case _:
            raise ValueError("Invalid review source")


@dataclass(frozen=True)
class ReviewCard:
    card_id: str
    word_form_id: str
    box: int = 0
    due_at: datetime | None = None
    queue_revision: int = 0

    def __post_init__(self) -> None:
        Schedule(self.box, self.due_at)
        if type(self.queue_revision) is not int or self.queue_revision < 0:
            raise ValueError("Invalid queue revision")

    def is_due(self, now: datetime) -> bool:
        require_aware(now)
        return self.box == 0 or (self.due_at is not None and now >= self.due_at)

    def is_eligible(self, now: datetime, sources: tuple[SourceReference, ...]) -> bool:
        return self.is_due(now) and any(source.status == "VALID" for source in sources)


@dataclass(frozen=True)
class ReviewEvent:
    id: str
    card_id: str
    source: ReviewSource
    rating: Rating
    reviewed_at: datetime
    next_due_at: datetime
    next_box: int
    operation_id: str
    attempt_id: str | None = None
    question_id: str | None = None

    def __post_init__(self) -> None:
        _source(self.source)
        validate_rating(self.rating)
        require_aware(self.reviewed_at)
        Schedule(self.next_box, self.next_due_at)


def _writer(connection: Connection) -> None:
    if not connection.in_transaction() or not connection.get_execution_options().get(
        "sqlite_begin_immediate", False
    ):
        raise ValueError("Review writes require a caller-owned SQLite writer transaction")


def _utc_text(instant: datetime) -> str:
    require_aware(instant)
    return instant.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def get_card(connection: Connection, card_id: str) -> ReviewCard | None:
    row = (
        connection.exec_driver_sql(
            "SELECT card_id,word_form_id,box,due_at,queue_revision "
            "FROM review_cards WHERE card_id=?",
            (card_id,),
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    return ReviewCard(
        row["card_id"],
        row["word_form_id"],
        row["box"],
        datetime.fromisoformat(row["due_at"]) if row["due_at"] is not None else None,
        row["queue_revision"],
    )


def ensure_card(connection: Connection, *, card_id: str, word_form_id: str) -> ReviewCard:
    """Reuse historical identity regardless of source dates or current activity."""
    _writer(connection)
    existing = connection.exec_driver_sql(
        "SELECT card_id FROM review_cards WHERE word_form_id=?", (word_form_id,)
    ).scalar_one_or_none()
    if existing is None:
        # The writer lock serializes admission; UNIQUE(word_form_id) is durable protection.
        connection.exec_driver_sql(
            "INSERT INTO review_cards (card_id,word_form_id) VALUES (?,?)", (card_id, word_form_id)
        )
    card = get_card(connection, str(existing) if existing is not None else card_id)
    if card is None:
        raise RuntimeError("Review card was not persisted")
    return card


def source_references(connection: Connection, word_form_id: str) -> tuple[SourceReference, ...]:
    rows = (
        connection.exec_driver_sql(
            "SELECT s.id,w.note_date,s.status FROM word_form_sources w "
            "JOIN source_files s ON s.id=w.source_id WHERE w.word_form_id=? ORDER BY s.id",
            (word_form_id,),
        )
        .mappings()
        .all()
    )
    return tuple(SourceReference(row["id"], row["note_date"], row["status"]) for row in rows)


def _event(connection: Connection, operation_id: str, card_id: str) -> ReviewEvent | None:
    row = (
        connection.exec_driver_sql(
            "SELECT * FROM review_events WHERE operation_id=? AND card_id=?",
            (operation_id, card_id),
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    return ReviewEvent(
        id=row["id"],
        card_id=row["card_id"],
        source=row["source"],
        rating=row["rating"],
        reviewed_at=datetime.fromisoformat(row["reviewed_at"]),
        next_due_at=datetime.fromisoformat(row["next_due_at"]),
        next_box=row["next_box"],
        operation_id=row["operation_id"],
        attempt_id=row["attempt_id"],
        question_id=row["question_id"],
    )


def record_review(
    connection: Connection,
    *,
    card_id: str,
    event_id: str,
    operation_id: str,
    source: str,
    rating: str | None,
    reviewed_at: datetime,
    attempt_id: str | None = None,
    question_id: str | None = None,
) -> ReviewEvent | None:
    """Append once and advance atomically; None means there was no review attempt.

    Replay returns the original event even after a later review/reset/source loss.
    A quiz operation can append one event per card after upstream rating aggregation.
    """
    _writer(connection)
    if rating is None:
        return None
    valid_rating = validate_rating(rating)
    valid_source = _source(source)
    require_aware(reviewed_at)
    existing = _event(connection, operation_id, card_id)
    if existing is not None:
        if (existing.rating, existing.source, existing.attempt_id, existing.question_id) != (
            valid_rating,
            valid_source,
            attempt_id,
            question_id,
        ):
            raise ReviewOperationMismatchError("Review operation already owns a different intent")
        return existing
    card = get_card(connection, card_id)
    if card is None or not any(
        ref.status == "VALID" for ref in source_references(connection, card.word_form_id)
    ):
        raise InactiveCardError("No valid source for review card")
    schedule = transition(card.box, valid_rating, reviewed_at)
    if schedule.due_at is None:
        raise RuntimeError("A review must produce a learned schedule")
    # A savepoint keeps event/card atomic even if a caller catches a failed SQL statement.
    with connection.begin_nested():
        connection.exec_driver_sql(
            "INSERT INTO review_events "
            "(id,card_id,source,rating,reviewed_at,next_due_at,next_box,operation_id,"
            "attempt_id,question_id) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                event_id,
                card_id,
                valid_source,
                valid_rating,
                _utc_text(reviewed_at),
                _utc_text(schedule.due_at),
                schedule.box,
                operation_id,
                attempt_id,
                question_id,
            ),
        )
        connection.exec_driver_sql(
            "UPDATE review_cards SET box=?,due_at=?,queue_revision=queue_revision+1 "
            "WHERE card_id=?",
            (schedule.box, _utc_text(schedule.due_at), card_id),
        )
    event = _event(connection, operation_id, card_id)
    if event is None:
        raise RuntimeError("Review event was not persisted")
    return event


def reset_card_state(connection: Connection, card_id: str) -> ReviewCard:
    """Reset only the current schedule; historical facts and card identity remain."""
    _writer(connection)
    if get_card(connection, card_id) is None:
        raise InactiveCardError("No review card to reset")
    connection.exec_driver_sql(
        "UPDATE review_cards SET box=0,due_at=NULL,queue_revision=queue_revision+1 WHERE card_id=?",
        (card_id,),
    )
    card = get_card(connection, card_id)
    if card is None:
        raise RuntimeError("Review reset was not persisted")
    return card

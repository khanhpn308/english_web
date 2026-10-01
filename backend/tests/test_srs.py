"""ADR-0005 SRS oracles and durable review invariants on synthetic temporary DBs."""

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from threading import Barrier

import pytest
from alembic import command
from alembic.script import ScriptDirectory
from backend.app.application.operations import OperationLedger
from backend.app.persistence.database import Database, migration_config
from backend.app.review.models import (
    InactiveCardError,
    ReviewCard,
    ReviewOperationMismatchError,
    ensure_card,
    get_card,
    record_review,
    reset_card_state,
    source_references,
)
from backend.app.review.srs import (
    Schedule,
    destination_box,
    interval_days,
    next_due_at,
    transition,
)
from backend.app.vocabulary.models import SourceReference
from backend.app.vocabulary.repository import VocabularyRepository
from sqlalchemy import Connection, inspect
from sqlalchemy.exc import IntegrityError

REVIEWED_AT = datetime(2026, 9, 29, 10, 20, 30, tzinfo=UTC)
MATRIX = ((1, 1, 1, 2), (1, 1, 2, 3), (1, 2, 3, 4), (1, 3, 4, 5), (1, 4, 5, 5), (1, 5, 5, 5))
RATINGS = ("AGAIN", "HARD", "GOOD", "EASY")
DUE_DATES = (
    "2026-09-29T17:00:00Z",
    "2026-10-01T17:00:00Z",
    "2026-10-05T17:00:00Z",
    "2026-10-12T17:00:00Z",
    "2026-10-28T17:00:00Z",
)


@pytest.mark.parametrize(
    ("box", "rating", "expected"),
    [(box, rating, MATRIX[box][i]) for box in range(6) for i, rating in enumerate(RATINGS)],
)
def test_complete_transition_oracle(box: int, rating: str, expected: int) -> None:
    assert destination_box(box, rating) == expected
    result = transition(box, rating, REVIEWED_AT)
    assert result.box == expected
    assert result.due_at == datetime.fromisoformat(DUE_DATES[expected - 1])
    assert transition(box, rating, REVIEWED_AT) == result


@pytest.mark.parametrize(("box", "days"), [(1, 1), (2, 3), (3, 7), (4, 14), (5, 30)])
def test_calendar_intervals_and_canonical_due(box: int, days: int) -> None:
    assert interval_days(box) == days
    assert next_due_at(box, REVIEWED_AT) == datetime.fromisoformat(DUE_DATES[box - 1])
    assert next_due_at(box, REVIEWED_AT) != REVIEWED_AT + timedelta(days=days)


@pytest.mark.parametrize(
    ("reviewed", "due"),
    [
        ("2026-09-29T16:59:59Z", "2026-10-01T17:00:00Z"),
        ("2026-09-29T17:00:00Z", "2026-10-02T17:00:00Z"),
    ],
)
def test_bangkok_midnight_boundary(reviewed: str, due: str) -> None:
    assert transition(1, "GOOD", datetime.fromisoformat(reviewed)) == Schedule(
        2, datetime.fromisoformat(due)
    )


def test_aware_conversion_is_independent_of_input_offset() -> None:
    offset = timezone(timedelta(hours=-4))
    assert transition(1, "GOOD", REVIEWED_AT.astimezone(offset)) == transition(
        1, "GOOD", REVIEWED_AT
    )
    # UTC date differs from Bangkok date at this instant.
    assert next_due_at(1, datetime(2026, 9, 29, 23, 59, tzinfo=UTC)) == datetime(
        2026, 9, 30, 17, tzinfo=UTC
    )


@pytest.mark.parametrize("box", [-1, 6, 999, True, 1.5])
def test_invalid_boxes_fail_explicitly(box: int) -> None:
    with pytest.raises(ValueError, match="Invalid box"):
        destination_box(box, "GOOD")
    with pytest.raises(ValueError, match="Invalid box"):
        next_due_at(box, REVIEWED_AT)


@pytest.mark.parametrize("rating", ["UNKNOWN", "good", "", " GOOD", "1"])
def test_invalid_ratings_are_never_coerced(rating: str) -> None:
    with pytest.raises(ValueError, match="Invalid rating"):
        transition(0, rating, REVIEWED_AT)


def test_naive_times_and_inconsistent_schedule_fail_explicitly() -> None:
    naive = datetime(2026, 9, 29)
    with pytest.raises(ValueError, match="timezone-aware"):
        transition(0, "GOOD", naive)
    with pytest.raises(ValueError, match="timezone-aware"):
        next_due_at(0, naive)
    with pytest.raises(ValueError, match="NEW"):
        Schedule(0, REVIEWED_AT)
    with pytest.raises(ValueError, match="Learned"):
        Schedule(1, None)
    with pytest.raises(ValueError, match="timezone-aware"):
        Schedule(1, naive)
    with pytest.raises(ValueError, match="NEW has no interval"):
        interval_days(0)


def test_new_card_and_inclusive_due_predicate() -> None:
    new = ReviewCard("card", "form")
    valid = (SourceReference("source", "2026-09-29", "VALID"),)
    assert new.box == 0 and new.due_at is None and new.queue_revision == 0
    assert next_due_at(0, REVIEWED_AT) is None
    assert new.is_eligible(REVIEWED_AT, valid)
    due = datetime.fromisoformat(DUE_DATES[0])
    learned = ReviewCard("card", "form", box=1, due_at=due, queue_revision=1)
    assert not learned.is_eligible(due - timedelta(microseconds=1), valid)
    assert learned.is_eligible(due, valid)
    assert learned.is_eligible(due + timedelta(microseconds=1), valid)
    assert not new.is_eligible(REVIEWED_AT, ())
    with pytest.raises(ValueError, match="timezone-aware"):
        new.is_due(datetime(2026, 9, 29))
    with pytest.raises(ValueError, match="queue revision"):
        ReviewCard("card", "form", queue_revision=-1)


@pytest.fixture
def db(tmp_path: Path) -> Iterator[Database]:
    database = Database(tmp_path / "review.db")
    database.initialize()
    try:
        yield database
    finally:
        database.close()


def seed_vocabulary(db: Database) -> str:
    repo = VocabularyRepository(db.engine)
    family = repo.get_or_create_family("estimate")
    form = repo.save_canonical_word_form(
        lemma="estimate", part_of_speech="NOUN", family_id=family.id
    )
    for source_id, date in (("source1", "2026-09-29"), ("source2", "2026-09-30")):
        repo.save_source_file(source_id=source_id, relative_path=f"{source_id}.md", note_date=date)
        repo.link_word_form_to_source(form.id, source_id, date)
    return form.id


def claim(ledger: OperationLedger, key: str) -> str:
    return ledger.claim(
        kind="REVIEW",
        key=key,
        method="POST",
        path="/synthetic/review",
        body={"rating": "GOOD"},
        preconditions={},
    ).operation.operation_id


def create_card(db: Database, form_id: str, card_id: str = "card") -> ReviewCard:
    with (
        db.engine.connect().execution_options(sqlite_begin_immediate=True) as connection,
        connection.begin(),
    ):
        return ensure_card(connection, card_id=card_id, word_form_id=form_id)


def apply_review(
    connection: Connection,
    operation_id: str,
    event_id: str,
    card_id: str = "card",
    rating: str | None = "GOOD",
) -> None:
    record_review(
        connection,
        card_id=card_id,
        event_id=event_id,
        operation_id=operation_id,
        source="FLASHCARD",
        rating=rating,
        reviewed_at=REVIEWED_AT,
    )


def test_one_card_per_canonical_identity_and_distinct_pos(db: Database) -> None:
    form_id = seed_vocabulary(db)
    first = create_card(db, form_id)
    assert create_card(db, form_id, "unused-id") == first
    repo = VocabularyRepository(db.engine)
    noun = repo.get_word_form(form_id)
    assert noun is not None
    verb = repo.save_canonical_word_form(
        lemma="estimate", part_of_speech="VERB", family_id=noun.family_id
    )
    assert create_card(db, verb.id, "verb-card").word_form_id != first.word_form_id
    with db.engine.connect() as connection:
        assert len(source_references(connection, form_id)) == 2
        assert connection.exec_driver_sql("SELECT count(*) FROM review_cards").scalar_one() == 2
        assert get_card(connection, "absent") is None


def test_no_attempt_does_not_create_history_or_mutate_card(db: Database) -> None:
    original = create_card(db, seed_vocabulary(db))
    with (
        db.engine.connect().execution_options(sqlite_begin_immediate=True) as connection,
        connection.begin(),
    ):
        assert (
            record_review(
                connection,
                card_id="card",
                event_id="unused",
                operation_id="unused",
                source="FLASHCARD",
                rating=None,
                reviewed_at=REVIEWED_AT,
            )
            is None
        )
        assert get_card(connection, "card") == original
        assert connection.exec_driver_sql("SELECT count(*) FROM review_events").scalar_one() == 0


def test_later_review_replay_and_append_only_history(db: Database) -> None:
    form_id = seed_vocabulary(db)
    create_card(db, form_id)
    ledger = OperationLedger(db.engine)
    operation1 = claim(ledger, "first-review")
    ledger.complete(
        operation1,
        response_status=201,
        result_ref="event1",
        local_write=lambda connection: apply_review(connection, operation1, "event1"),
    )
    with db.engine.connect() as connection:
        before = connection.exec_driver_sql("SELECT * FROM review_events").mappings().one()
        assert get_card(connection, "card") == ReviewCard(
            "card",
            form_id,
            1,
            datetime.fromisoformat(DUE_DATES[0]),
            1,
        )
    # The integrated ledger does not invoke a side-effect callback on receipt replay.
    ledger.complete(
        operation1,
        response_status=201,
        result_ref="event1",
        local_write=lambda connection: apply_review(connection, operation1, "duplicate"),
    )
    operation2 = claim(ledger, "later-review")
    ledger.complete(
        operation2,
        response_status=201,
        result_ref="event2",
        local_write=lambda connection: apply_review(connection, operation2, "event2"),
    )
    with (
        db.engine.connect().execution_options(sqlite_begin_immediate=True) as connection,
        connection.begin(),
    ):
        replay = record_review(
            connection,
            card_id="card",
            event_id="new-id",
            operation_id=operation1,
            source="FLASHCARD",
            rating="GOOD",
            reviewed_at=REVIEWED_AT + timedelta(days=40),
        )
        assert replay is not None and replay.id == "event1" and replay.next_box == 1
        assert replay.reviewed_at == REVIEWED_AT
        card = get_card(connection, "card")
        assert card is not None and card.box == 2 and card.queue_revision == 2
        events = (
            connection.exec_driver_sql("SELECT * FROM review_events ORDER BY rowid")
            .mappings()
            .all()
        )
        assert len(events) == 2 and events[0] == before
        with pytest.raises(FrozenInstanceError):
            field_name = "rating"
            setattr(replay, field_name, "AGAIN")
        with pytest.raises(ReviewOperationMismatchError, match="operation"):
            record_review(
                connection,
                card_id="card",
                event_id="unused",
                operation_id=operation1,
                source="FLASHCARD",
                rating="EASY",
                reviewed_at=REVIEWED_AT,
            )
    for statement, reason in (
        ("UPDATE review_events SET rating='EASY'", "Append-only review events"),
        ("DELETE FROM review_events", "Append-only review events"),
        (
            "INSERT OR REPLACE INTO review_events SELECT * FROM review_events WHERE id='event1'",
            "Review operation already applied",
        ),
        ("DELETE FROM review_cards", "Preserve review cards"),
        ("INSERT OR REPLACE INTO review_cards SELECT * FROM review_cards", "Preserve review cards"),
    ):
        with pytest.raises(IntegrityError, match=reason), db.engine.begin() as connection:
            connection.exec_driver_sql(statement)


@pytest.mark.parametrize(
    ("statuses", "active"),
    [
        (("VALID",), True),
        (("INVALID",), False),
        (("MISSING",), False),
        (("VALID", "INVALID"), True),
        (("VALID", "MISSING"), True),
        ((), False),
    ],
)
def test_source_eligibility(statuses: tuple[str, ...], active: bool, db: Database) -> None:
    form_id = seed_vocabulary(db)
    card = create_card(db, form_id)
    operation = claim(OperationLedger(db.engine), "source-probe")
    with (
        db.engine.connect().execution_options(sqlite_begin_immediate=True) as connection,
        connection.begin(),
    ):
        for index in range(2):
            status = statuses[index] if index < len(statuses) else "MISSING"
            connection.exec_driver_sql(
                "UPDATE source_files SET status=? WHERE id=?", (status, f"source{index + 1}")
            )
        refs = source_references(connection, form_id)
        assert card.is_eligible(REVIEWED_AT, refs) is active
        if active:
            apply_review(connection, operation, "event")
        else:
            with pytest.raises(InactiveCardError, match="No valid source"):
                apply_review(connection, operation, "event")
            assert get_card(connection, "card") == card
            assert (
                connection.exec_driver_sql("SELECT count(*) FROM review_events").scalar_one() == 0
            )


def test_source_loss_deletion_readd_and_reset_preserve_history(db: Database) -> None:
    form_id = seed_vocabulary(db)
    create_card(db, form_id)
    ledger = OperationLedger(db.engine)
    operation = claim(ledger, "historical-review")
    ledger.complete(
        operation,
        response_status=201,
        result_ref="event",
        local_write=lambda connection: apply_review(connection, operation, "event"),
    )
    with db.engine.connect() as connection:
        event = connection.exec_driver_sql("SELECT * FROM review_events").one()
        learned = get_card(connection, "card")
    with (
        db.engine.connect().execution_options(sqlite_begin_immediate=True) as connection,
        connection.begin(),
    ):
        connection.exec_driver_sql("UPDATE source_files SET status='INVALID'")
        assert get_card(connection, "card") == learned
        with pytest.raises(InactiveCardError):
            apply_review(connection, claim_unused_operation(connection), "inactive-event")
        connection.exec_driver_sql("DELETE FROM source_files")
        assert source_references(connection, form_id) == ()
        assert get_card(connection, "card") == learned
        # Replays remain historical receipts even after activity changes.
        apply_review(connection, operation, "replay")
        assert connection.exec_driver_sql("SELECT * FROM review_events").one() == event
        reset = reset_card_state(connection, "card")
        assert reset.box == 0 and reset.due_at is None and reset.queue_revision == 2
        assert connection.exec_driver_sql("SELECT * FROM review_events").one() == event
    repo = VocabularyRepository(db.engine)
    form = repo.get_word_form(form_id)
    assert form is not None
    reused = repo.save_canonical_word_form(
        lemma="estimate", part_of_speech="NOUN", family_id=form.family_id
    )
    assert reused.id == form_id
    repo.save_source_file(
        source_id="source3", relative_path="01-10-2026.md", note_date="2026-10-01"
    )
    repo.link_word_form_to_source(form_id, "source3", "2026-10-01")
    assert create_card(db, form_id, "not-created") == reset
    with db.engine.connect() as connection:
        assert reset.is_eligible(REVIEWED_AT, source_references(connection, form_id))
    # Remove occurrence FKs first so rejection proves the review-card FK preserves identity.
    with db.engine.begin() as connection:
        connection.exec_driver_sql("DELETE FROM word_form_sources WHERE word_form_id=?", (form_id,))
    with pytest.raises(IntegrityError, match="FOREIGN KEY"), db.engine.begin() as connection:
        connection.exec_driver_sql("DELETE FROM word_forms WHERE id=?", (form_id,))
    with db.engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT * FROM review_events").one() == event


def claim_unused_operation(connection: Connection) -> str:
    connection.exec_driver_sql(
        "INSERT INTO operations (operation_id,kind,status,created_at,updated_at) "
        "VALUES ('unused-op','REVIEW','PENDING','synthetic','synthetic')"
    )
    return "unused-op"


def test_one_quiz_operation_can_append_once_per_card(db: Database) -> None:
    form_id = seed_vocabulary(db)
    create_card(db, form_id)
    repo = VocabularyRepository(db.engine)
    family = repo.get_or_create_family("assess")
    form2 = repo.save_canonical_word_form(
        lemma="assess", part_of_speech="VERB", family_id=family.id
    )
    repo.link_word_form_to_source(form2.id, "source1", "2026-09-29")
    create_card(db, form2.id, "card2")
    operation = claim(OperationLedger(db.engine), "quiz-review")
    with (
        db.engine.connect().execution_options(sqlite_begin_immediate=True) as connection,
        connection.begin(),
    ):
        for card_id in ("card", "card2"):
            event = record_review(
                connection,
                card_id=card_id,
                event_id=f"event-{card_id}",
                operation_id=operation,
                source="QUIZ",
                rating="GOOD",
                reviewed_at=REVIEWED_AT,
                attempt_id="attempt",
                question_id=None,
            )
            assert event is not None and event.attempt_id == "attempt"
        assert connection.exec_driver_sql("SELECT count(*) FROM review_events").scalar_one() == 2


def test_concurrent_same_operation_advances_only_once(db: Database) -> None:
    create_card(db, seed_vocabulary(db))
    operation = claim(OperationLedger(db.engine), "concurrent-review")
    barrier = Barrier(2)

    def writer(index: int) -> str:
        barrier.wait(timeout=5)
        with (
            db.engine.connect().execution_options(sqlite_begin_immediate=True) as connection,
            connection.begin(),
        ):
            event = record_review(
                connection,
                card_id="card",
                event_id=f"event{index}",
                operation_id=operation,
                source="FLASHCARD",
                rating="GOOD",
                reviewed_at=REVIEWED_AT,
            )
            assert event is not None
            return event.id

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(writer, index) for index in range(2)]
        outcomes = [future.result(timeout=5) for future in futures]
    assert outcomes[0] == outcomes[1]
    with db.engine.connect() as connection:
        card = get_card(connection, "card")
        assert card is not None and card.box == 1 and card.queue_revision == 1
        assert connection.exec_driver_sql("SELECT count(*) FROM review_events").scalar_one() == 1


def test_constraints_reject_for_intended_reasons(db: Database) -> None:
    create_card(db, seed_vocabulary(db))
    with db.engine.begin() as connection:
        operation = claim_unused_operation(connection)
    probes = (
        ("UPDATE review_cards SET box=6", "ck_review_cards_box"),
        ("UPDATE review_cards SET box=1.5", "ck_review_cards_box"),
        ("UPDATE review_cards SET box=1", "ck_review_cards_schedule"),
        ("UPDATE review_cards SET queue_revision=-1", "ck_review_cards_revision"),
        ("UPDATE review_cards SET word_form_id='other'", "Immutable review card identity"),
    )
    for sql, reason in probes:
        with pytest.raises(IntegrityError, match=reason), db.engine.begin() as connection:
            connection.exec_driver_sql(sql)
    for field, value, reason in (
        ("rating", "UNKNOWN", "ck_review_events_rating"),
        ("source", "OTHER", "ck_review_events_source"),
        ("next_box", 6, "ck_review_events_box"),
        ("reviewed_at", "2026-09-29T10:20:30", "ck_review_events_reviewed_at"),
    ):
        values: dict[str, str | int] = {
            "rating": "GOOD",
            "source": "FLASHCARD",
            "next_box": 1,
            "reviewed_at": "2026-09-29T10:20:30.000000Z",
        }
        values[field] = value
        with pytest.raises(IntegrityError, match=reason), db.engine.begin() as connection:
            connection.exec_driver_sql(
                "INSERT INTO review_events "
                "(id,card_id,operation_id,source,rating,reviewed_at,next_due_at,next_box) "
                "VALUES ('bad','card',?,?,?,?,?,?)",
                (
                    operation,
                    values["source"],
                    values["rating"],
                    values["reviewed_at"],
                    "2026-09-29T17:00:00.000000Z",
                    values["next_box"],
                ),
            )


def test_missing_card_invalid_input_and_writer_boundary(db: Database) -> None:
    original = create_card(db, seed_vocabulary(db))
    with (
        db.engine.begin() as connection,
        pytest.raises(ValueError, match="caller-owned SQLite writer transaction"),
    ):
        ensure_card(connection, card_id="other", word_form_id=original.word_form_id)
    operation = claim(OperationLedger(db.engine), "invalid-input")
    with (
        db.engine.connect().execution_options(sqlite_begin_immediate=True) as connection,
        connection.begin(),
    ):
        with pytest.raises(InactiveCardError, match="No valid source"):
            apply_review(connection, operation, "event", card_id="missing")
        with pytest.raises(InactiveCardError, match="No review card to reset"):
            reset_card_state(connection, "missing")
        with pytest.raises(ValueError, match="Invalid rating"):
            apply_review(connection, operation, "event", rating="UNKNOWN")
        with pytest.raises(ValueError, match="Invalid review source"):
            record_review(
                connection,
                card_id="card",
                event_id="event",
                operation_id=operation,
                source="OTHER",
                rating="GOOD",
                reviewed_at=REVIEWED_AT,
            )
        assert get_card(connection, "card") == original
        assert connection.exec_driver_sql("SELECT count(*) FROM review_events").scalar_one() == 0


def test_failed_schedule_write_rolls_back_event_and_receipt(db: Database) -> None:
    original = create_card(db, seed_vocabulary(db))
    ledger = OperationLedger(db.engine)
    operation = claim(ledger, "rollback-review")
    with db.engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TRIGGER synthetic_write_failure BEFORE UPDATE OF box ON review_cards "
            "BEGIN SELECT RAISE(ABORT, 'Synthetic schedule write failure'); END"
        )
    with pytest.raises(IntegrityError, match="Synthetic schedule write failure"):
        ledger.complete(
            operation,
            response_status=201,
            result_ref="event",
            local_write=lambda connection: apply_review(connection, operation, "event"),
        )
    # Even when the caller catches the failure within its transaction, the savepoint rolls back.
    with (
        db.engine.connect().execution_options(sqlite_begin_immediate=True) as connection,
        connection.begin(),
    ):
        with pytest.raises(IntegrityError, match="Synthetic schedule write failure"):
            apply_review(connection, operation, "event")
        assert get_card(connection, "card") == original
        assert connection.exec_driver_sql("SELECT count(*) FROM review_events").scalar_one() == 0
    receipt = ledger.get(operation)
    assert receipt is not None and receipt.status == "PENDING" and receipt.result_ref is None


def test_0004_to_0005_preserves_rows_and_repeat_is_stable(tmp_path: Path) -> None:
    db = Database(tmp_path / "prior.db")
    config = migration_config()
    scripts = ScriptDirectory.from_config(config)
    heads = scripts.get_heads()
    assert len(heads) == 1
    revision = scripts.get_revision("0005_review")
    assert revision is not None and revision.down_revision == "0004_vocabulary"
    try:
        with db.engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "0004_vocabulary")
        seed_vocabulary(db)
        with db.engine.connect() as connection:
            tables = ("word_families", "word_forms", "source_files", "word_form_sources")
            before = {
                table: connection.exec_driver_sql(f"SELECT * FROM {table}").all()
                for table in tables
            }
        for _ in range(2):
            with db.engine.begin() as connection:
                config.attributes["connection"] = connection
                command.upgrade(config, "0005_review")
                assert connection.exec_driver_sql(
                    "SELECT version_num FROM alembic_version"
                ).all() == [("0005_review",)]
        with db.engine.connect() as connection:
            for table in tables:
                assert connection.exec_driver_sql(f"SELECT * FROM {table}").all() == before[table]
            assert inspect(connection).get_unique_constraints("review_events") == [
                {
                    "name": "uq_review_events_operation_card",
                    "column_names": ["operation_id", "card_id"],
                }
            ]
            assert any(
                c["column_names"] == ["word_form_id"]
                for c in inspect(connection).get_unique_constraints("review_cards")
            )
        with (
            pytest.raises(RuntimeError, match="preserve review history"),
            db.engine.begin() as connection,
        ):
            config.attributes["connection"] = connection
            command.downgrade(config, "0004_vocabulary")
        assert db.initialize().schema_revision == heads[0]
        assert db.initialize().schema_revision == heads[0]
    finally:
        db.close()

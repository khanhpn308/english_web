"""Synthetic persistence and adversarial oracles for T034, run by the host."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.script import ScriptDirectory
from backend.app.application.operations import OperationLedger
from backend.app.assessment.questions import (
    PUBLIC_QUESTION_ADAPTER,
    SNAPSHOT_ADAPTER,
    QuestionSet,
    QuizAttempt,
    QuizCounts,
    QuizResult,
    storage_payload,
    to_scoring_snapshot,
)
from backend.app.assessment.repository import (
    QuizPersistenceError,
    create_attempt,
    get_attempt,
    load_snapshot,
    save_answer,
    store_submission,
)
from backend.app.assessment.scoring import AnswerInput, score_quiz
from backend.app.persistence.database import Database, migration_config
from backend.app.review.models import InactiveCardError, ensure_card, record_review
from backend.app.vocabulary.repository import VocabularyRepository
from pydantic import BaseModel, ValidationError
from sqlalchemy import Connection
from sqlalchemy.exc import IntegrityError

NOW = datetime(2026, 10, 8, 10, 0, tzinfo=UTC)
DATE = "2026-10-08"


def question(index: int, kind: str = "MCQ") -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": f"q_{kind}_{index}",
        "type": kind,
        "wordFormId": f"wf_{index}",
        "promptEn": "Choose a word." if kind == "MCQ" else "Use the target word.",
    }
    if kind == "MCQ":
        data.update(
            options=[{"id": "o_a", "textEn": "robust"}, {"id": "o_b", "textEn": "fragile"}],
            correctOptionId="o_a",
            explanationVi="Giải thích tổng hợp.",
        )
    elif kind == "CLOZE":
        data.update(
            answerPolicyVersion="cloze-answer-v1",
            acceptedAnswers=["robust"],
            explanationVi="Giải thích tổng hợp.",
        )
    elif kind == "WRITING":
        data.update(
            targetLemma="robust",
            rubricVersion="writing-rubric-v1",
            rubric={
                "descriptors": [
                    {"score": score, "textVi": text}
                    for score, text in enumerate(
                        (
                            "Không có câu có nghĩa hoặc không dùng từ mục tiêu.",
                            "Có thử dùng từ nhưng sai nghĩa/dạng hoặc lỗi lớn làm khó hiểu.",
                            "Nhận ra nghĩa định dùng nhưng cần sửa đáng kể dạng từ/ngữ pháp.",
                            "Đúng nghĩa/dạng, câu rõ; lỗi nhỏ không cản nghĩa.",
                            "Đúng nghĩa/dạng, đúng ngữ pháp, rõ và tự nhiên trong câu học thuật.",
                        )
                    )
                ]
            },
        )
    return data


def question_set(counts: tuple[int, int, int] = (2, 2, 1)) -> QuestionSet:
    return QuestionSet.model_validate_json(
        json.dumps(
            {
                "questions": [
                    question(index, kind)
                    for kind, count in zip(("MCQ", "CLOZE", "WRITING"), counts, strict=True)
                    for index in range(count)
                ]
            }
        )
    )


def operation(connection: Connection, identity: str) -> None:
    connection.exec_driver_sql(
        "INSERT INTO operations (operation_id,kind,status,created_at,updated_at) "
        "VALUES (?,'QUIZ_TEST','PENDING',?,?)",
        (identity, NOW.isoformat(), NOW.isoformat()),
    )


def seed_sources(database: Database, count: int = 20) -> None:
    repo = VocabularyRepository(database.engine)
    family = repo.get_or_create_family("synthetic", family_id="family_quiz")
    repo.save_source_file(
        source_id="src_quiz",
        relative_path="08-10-2026.md",
        note_date=DATE,
        status="VALID",
        revision=1,
        etag='"source-r1"',
        content_hash="a" * 64,
    )
    with (
        database.engine.connect().execution_options(sqlite_begin_immediate=True) as connection,
        connection.begin(),
    ):
        for index in range(count):
            form = repo.save_canonical_word_form(
                lemma=f"synthetic {index}",
                part_of_speech="ADJ",
                family_id=family.id,
                word_form_id=f"wf_{index}",
                connection=connection,
            )
            repo.link_word_form_to_source(form.id, "src_quiz", DATE, connection=connection)
            ensure_card(connection, card_id=f"card_{index}", word_form_id=form.id)


@pytest.fixture
def database(tmp_path: Path) -> Iterator[Database]:
    db = Database(tmp_path / "quiz.db")
    db.initialize()
    seed_sources(db)
    try:
        yield db
    finally:
        db.close()


def create(database: Database, identity: str = "attempt_a") -> QuizAttempt:
    with (
        database.engine.connect().execution_options(sqlite_begin_immediate=True) as connection,
        connection.begin(),
    ):
        return create_attempt(
            connection,
            attempt_id=identity,
            note_date=DATE,
            questions=question_set(),
            created_at=NOW,
        )


@pytest.mark.parametrize("kind", ["MCQ", "CLOZE", "WRITING"])
def test_valid_snapshot_roundtrip_and_scoring_adapter(kind: str) -> None:
    item = SNAPSHOT_ADAPTER.validate_json(json.dumps(question(0, kind)))
    assert SNAPSHOT_ADAPTER.validate_json(storage_payload(item)) == item
    assert to_scoring_snapshot(item).type == kind
    public = PUBLIC_QUESTION_ADAPTER.validate_python(item.model_dump(by_alias=True))
    assert public.type == kind
    assert public.word_form_id == "wf_0"


@pytest.mark.parametrize("kind", ["mcq", "Cloze", "WRITE", "", 0, None])
def test_invalid_type_discriminator(kind: object) -> None:
    data = question(0)
    data["type"] = kind
    with pytest.raises(ValidationError):
        SNAPSHOT_ADAPTER.validate_json(json.dumps(data))


@pytest.mark.parametrize(
    ("kind", "field", "value"),
    [
        ("MCQ", "id", ""),
        ("MCQ", "wordFormId", " "),
        ("MCQ", "promptEn", "x" * 4097),
        ("MCQ", "correctOptionId", "foreign"),
        ("MCQ", "options", []),
        ("MCQ", "options", [{"id": "o_a", "textEn": "a"}] * 2),
        ("CLOZE", "acceptedAnswers", []),
        ("CLOZE", "acceptedAnswers", [" \t"]),
        ("CLOZE", "acceptedAnswers", ["robust", " ROBUST "]),
        ("CLOZE", "answerPolicyVersion", "cloze-answer-v2"),
        ("WRITING", "rubricVersion", "writing-rubric-v2"),
        ("WRITING", "targetLemma", ""),
        ("WRITING", "rubric", {"descriptors": []}),
    ],
)
def test_required_fields_and_private_keys_are_strict(kind: str, field: str, value: object) -> None:
    data = question(0, kind)
    data[field] = value
    with pytest.raises(ValidationError):
        SNAPSHOT_ADAPTER.validate_json(json.dumps(data))


@pytest.mark.parametrize("counts", [(5, 0, 0), (2, 2, 1), (20, 10, 0), (10, 10, 10)])
def test_normative_creation_bounds(counts: tuple[int, int, int]) -> None:
    assert len(question_set(counts).questions) == sum(counts)
    assert QuizCounts(mcq=counts[0], cloze=counts[1], writing=counts[2]).total == sum(counts)


@pytest.mark.parametrize("counts", [(5, 0, 0), (20, 10, 0), (10, 10, 10)])
def test_creation_bounds_are_preserved_by_real_storage(
    database: Database, counts: tuple[int, int, int]
) -> None:
    with (
        database.engine.connect().execution_options(sqlite_begin_immediate=True) as connection,
        connection.begin(),
    ):
        created = create_attempt(
            connection,
            attempt_id="bounded_attempt",
            note_date=DATE,
            questions=question_set(counts),
            created_at=NOW,
        )
    with database.engine.connect() as connection:
        restored = get_attempt(connection, created.id)
        assert restored == created
        assert len(restored.questions) == sum(counts)
        for kind, count in zip(("MCQ", "CLOZE", "WRITING"), counts, strict=True):
            assert sum(question.type == kind for question in restored.questions) == count


def test_snapshot_revision_is_an_immutable_positive_revision_not_a_schema_version(
    database: Database,
) -> None:
    with (
        database.engine.connect().execution_options(sqlite_begin_immediate=True) as connection,
        connection.begin(),
    ):
        created = create_attempt(
            connection,
            attempt_id="revision_11",
            note_date=DATE,
            questions=question_set(),
            created_at=NOW,
            snapshot_revision=11,
        )
    with database.engine.connect() as connection:
        restored = get_attempt(connection, created.id)
        assert restored.snapshot_revision == 11
        assert restored.submission_revision == 0
        assert restored == created


@pytest.mark.parametrize("revision", [0, -1, True, 1.5, "11"])
def test_invalid_snapshot_revisions_leave_no_attempt(database: Database, revision: Any) -> None:
    with (
        database.engine.connect().execution_options(sqlite_begin_immediate=True) as connection,
        connection.begin(),
    ):
        with pytest.raises(QuizPersistenceError, match="VALIDATION_ERROR"):
            create_attempt(
                connection,
                attempt_id="invalid_revision",
                note_date=DATE,
                questions=question_set(),
                created_at=NOW,
                snapshot_revision=revision,
            )
        assert connection.exec_driver_sql("SELECT count(*) FROM quiz_attempts").scalar_one() == 0


@pytest.mark.parametrize("counts", [(0, 0, 0), (1, 1, 1), (2, 1, 1), (21, 4, 0), (11, 10, 10)])
def test_out_of_bounds_question_sets(counts: tuple[int, int, int]) -> None:
    with pytest.raises(ValidationError):
        question_set(counts)
    with pytest.raises(ValidationError):
        QuizCounts(mcq=counts[0], cloze=counts[1], writing=counts[2])


@pytest.mark.parametrize("value", [True, 1.0, "5", -1, 21])
def test_counts_reject_coercion(value: Any) -> None:
    with pytest.raises(ValidationError):
        QuizCounts(mcq=value, cloze=5, writing=0)


def test_nested_serialization_excludes_answers_and_public_models_reject_private_fields(
    database: Database,
) -> None:
    attempt = create(database)
    with database.engine.connect() as connection:
        restored = get_attempt(connection, attempt.id)
        snapshots = load_snapshot(connection, attempt.id)
    assert restored == attempt
    for payload in (
        attempt.model_dump_json(by_alias=True),
        json.dumps([q.model_dump() for q in snapshots]),
        question_set().model_dump_json(by_alias=True, serialize_as_any=True),
    ):
        for private in ("correctOptionId", "acceptedAnswers", "explanationVi", "correct_option_id"):
            assert private not in payload

    class Envelope(BaseModel):
        attempt: QuizAttempt

    assert "explanationVi" not in Envelope(attempt=restored).model_dump_json(by_alias=True)
    with pytest.raises(ValidationError):
        PUBLIC_QUESTION_ADAPTER.validate_json(json.dumps(question(0)))


@pytest.mark.parametrize("change", ["form_edit", "source_edit", "INVALID", "MISSING", "delete"])
def test_live_source_changes_never_reconstruct_snapshot(database: Database, change: str) -> None:
    original = create(database)
    with database.engine.begin() as connection:
        if change == "form_edit":
            connection.exec_driver_sql("UPDATE word_forms SET lemma='changed', revision=2")
        elif change == "source_edit":
            connection.exec_driver_sql(
                "UPDATE source_files SET revision=2,content_hash=?", ("b" * 64,)
            )
        elif change == "delete":
            connection.exec_driver_sql("DELETE FROM source_files")
        else:
            connection.exec_driver_sql("UPDATE source_files SET status=?", (change,))
    with database.engine.connect() as connection:
        assert get_attempt(connection, original.id) == original
        assert len(load_snapshot(connection, original.id)) == 5
    if change in {"INVALID", "MISSING", "delete"}:
        with (
            database.engine.connect().execution_options(sqlite_begin_immediate=True) as connection,
            connection.begin(),
        ):
            operation(connection, "inactive_review")
            with pytest.raises(InactiveCardError):
                record_review(
                    connection,
                    card_id="card_0",
                    event_id="event_inactive",
                    operation_id="inactive_review",
                    source="QUIZ",
                    rating="GOOD",
                    reviewed_at=NOW,
                    attempt_id=original.id,
                    question_id="q_MCQ_0",
                )
            assert (
                connection.exec_driver_sql("SELECT count(*) FROM review_events").scalar_one() == 0
            )


def test_deleted_form_reference_survives_without_creating_a_review_card(database: Database) -> None:
    repo = VocabularyRepository(database.engine)
    questions = QuestionSet.model_validate_json(
        json.dumps({"questions": [question(index) for index in range(100, 105)]})
    )
    with (
        database.engine.connect().execution_options(sqlite_begin_immediate=True) as connection,
        connection.begin(),
    ):
        for index in range(100, 105):
            repo.save_canonical_word_form(
                lemma=f"detached synthetic {index}",
                part_of_speech="ADJ",
                family_id="family_quiz",
                word_form_id=f"wf_{index}",
                connection=connection,
            )
            repo.link_word_form_to_source(f"wf_{index}", "src_quiz", DATE, connection=connection)
        created = create_attempt(
            connection,
            attempt_id="historical_form_attempt",
            note_date=DATE,
            questions=questions,
            created_at=NOW,
        )
        connection.exec_driver_sql("DELETE FROM source_files")
        for index in range(100, 105):
            connection.exec_driver_sql("DELETE FROM word_forms WHERE id=?", (f"wf_{index}",))
        operation(connection, "absent_card_review")
        with pytest.raises(InactiveCardError):
            record_review(
                connection,
                card_id="absent_card",
                event_id="absent_event",
                operation_id="absent_card_review",
                source="QUIZ",
                rating="GOOD",
                reviewed_at=NOW,
                attempt_id=created.id,
            )
    with database.engine.connect() as connection:
        assert get_attempt(connection, created.id) == created
        assert load_snapshot(connection, created.id) == questions.questions
        assert (
            connection.exec_driver_sql(
                "SELECT count(*) FROM review_cards WHERE word_form_id IN "
                "('wf_100','wf_101','wf_102','wf_103','wf_104')"
            ).scalar_one()
            == 0
        )
        assert connection.exec_driver_sql("SELECT count(*) FROM review_events").scalar_one() == 0


def test_restart_restores_durable_questions_answers_and_revisions(
    database: Database, tmp_path: Path
) -> None:
    create(database)
    with (
        database.engine.connect().execution_options(sqlite_begin_immediate=True) as connection,
        connection.begin(),
    ):
        operation(connection, "draft_1")
        saved = save_answer(
            connection,
            attempt_id="attempt_a",
            question_id="q_MCQ_0",
            answer="o_b",
            self_score=None,
            expected_draft_revision=0,
            operation_id="draft_1",
            saved_at=NOW,
        )
        expected = get_attempt(connection, "attempt_a")
    database.close()
    reopened = Database(tmp_path / "quiz.db")
    try:
        assert reopened.initialize().schema_revision == "0010_quiz_answer_receipts"
        with reopened.engine.connect() as connection:
            restored = get_attempt(connection, "attempt_a")
            assert restored == expected
            assert restored.answers == (saved,)
            assert (saved.draft_revision, restored.submission_revision) == (1, 1)
    finally:
        reopened.close()


@pytest.mark.parametrize(
    "field", ["id", "wordFormId", "promptEn", "correctOptionId", "explanationVi"]
)
def test_missing_required_snapshot_fields(field: str) -> None:
    data = question(0)
    del data[field]
    with pytest.raises(ValidationError):
        SNAPSHOT_ADAPTER.validate_json(json.dumps(data))


def test_duplicate_question_ids_and_type_form_pairs() -> None:
    data = [question(i) for i in range(5)]
    data[1]["id"] = data[0]["id"]
    with pytest.raises(ValidationError):
        QuestionSet.model_validate_json(json.dumps({"questions": data}))
    data[1]["id"] = "distinct_id"
    data[1]["wordFormId"] = data[0]["wordFormId"]
    with pytest.raises(ValidationError):
        QuestionSet.model_validate_json(json.dumps({"questions": data}))


def test_snapshots_are_deeply_immutable_and_ignore_later_input_mutation() -> None:
    raw = question(0)
    snapshot = SNAPSHOT_ADAPTER.validate_python(raw)
    raw["options"][0]["textEn"] = "changed"
    assert snapshot.type == "MCQ"
    assert snapshot.options[0].text_en == "robust"
    with pytest.raises(ValidationError):
        snapshot.options[0].text_en = "changed"
    with pytest.raises(ValidationError):
        snapshot.correct_option_id = "o_b"


@pytest.mark.parametrize("bad_scores", [[0, 1, 2, 3, 3], [4, 3, 2, 1, 0], [0, 1, 2, 3, True]])
def test_rubric_scores_are_complete_ordered_strict_integers(bad_scores: list[Any]) -> None:
    data = question(0, "WRITING")
    for descriptor, score in zip(data["rubric"]["descriptors"], bad_scores, strict=True):
        descriptor["score"] = score
    with pytest.raises(ValidationError):
        SNAPSHOT_ADAPTER.validate_json(json.dumps(data))


@pytest.mark.parametrize("change", ["missing", "invalid", "wrong_date", "unknown_form"])
def test_creation_rejects_ineligible_sources_without_partial_attempt(
    database: Database, change: str
) -> None:
    with database.engine.begin() as connection:
        if change == "missing":
            connection.exec_driver_sql("DELETE FROM source_files")
        elif change == "invalid":
            connection.exec_driver_sql("UPDATE source_files SET status='INVALID'")
        elif change == "wrong_date":
            connection.exec_driver_sql("UPDATE source_files SET note_date='2026-10-07'")
        else:
            connection.exec_driver_sql("DELETE FROM word_form_sources WHERE word_form_id='wf_0'")
    with pytest.raises(QuizPersistenceError, match="VALIDATION_ERROR"):
        create(database)
    with database.engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT count(*) FROM quiz_attempts").scalar_one() == 0
        assert connection.exec_driver_sql("SELECT count(*) FROM quiz_questions").scalar_one() == 0


def write_draft(
    connection: Connection,
    *,
    identity: str = "draft_a",
    question_id: str = "q_MCQ_0",
    attempt_id: str = "attempt_a",
    revision: int = 0,
    answer: str = "o_a",
    self_score: int | None = None,
) -> None:
    operation(connection, identity)
    save_answer(
        connection,
        attempt_id=attempt_id,
        question_id=question_id,
        answer=answer,
        self_score=self_score,
        expected_draft_revision=revision,
        operation_id=identity,
        saved_at=NOW,
    )


def test_stale_draft_is_rejected_without_advancing_aggregate(database: Database) -> None:
    create(database)
    with (
        database.engine.connect().execution_options(sqlite_begin_immediate=True) as connection,
        connection.begin(),
    ):
        write_draft(connection)
        write_draft(connection, identity="draft_b", revision=1, answer="o_b")
        for revision in (0, 1, 3):
            with pytest.raises(QuizPersistenceError, match="REVISION_CONFLICT"):
                write_draft(connection, identity=f"stale_{revision}", revision=revision)
        restored = get_attempt(connection, "attempt_a")
        assert restored.submission_revision == 2
        assert restored.answers[0].draft_revision == 2
        assert restored.answers[0].answer == "o_b"


@pytest.mark.parametrize("revision", [-1, True, 1.0, "0"])
def test_invalid_draft_revision_is_rejected(database: Database, revision: Any) -> None:
    create(database)
    with (
        database.engine.connect().execution_options(sqlite_begin_immediate=True) as connection,
        connection.begin(),
    ):
        with pytest.raises(QuizPersistenceError, match="VALIDATION_ERROR"):
            write_draft(connection, revision=revision)
        assert get_attempt(connection, "attempt_a").submission_revision == 0


def test_attempt_membership_and_globally_stable_question_identity(database: Database) -> None:
    create(database)
    with pytest.raises(IntegrityError):
        create(database, "attempt_b")
    with (
        database.engine.connect().execution_options(sqlite_begin_immediate=True) as connection,
        connection.begin(),
    ):
        assert connection.exec_driver_sql("SELECT count(*) FROM quiz_attempts").scalar_one() == 1
        with pytest.raises(QuizPersistenceError, match="CROSS_RESOURCE_MISMATCH"):
            write_draft(connection, question_id="foreign")
        operation(connection, "foreign_draft")
        with pytest.raises(IntegrityError):
            connection.exec_driver_sql(
                "INSERT INTO quiz_answers VALUES ('foreign','q_MCQ_0','o_a',NULL,1,?,'DRAFT',?)",
                (NOW.strftime("%Y-%m-%dT%H:%M:%S.%fZ"), "foreign_draft"),
            )
        assert get_attempt(connection, "attempt_a").answers == ()


@pytest.mark.parametrize(
    ("question_id", "answer", "self_score"),
    [
        ("q_MCQ_0", "outside", None),
        ("q_MCQ_0", "o_a", 1),
        ("q_CLOZE_0", "robust", 0),
        ("q_WRITING_0", "sentence", True),
        ("q_WRITING_0", "sentence", 1.0),
        ("q_WRITING_0", "sentence", 5),
        ("q_CLOZE_0", "x" * 4097, None),
    ],
)
def test_invalid_answer_data_does_not_write_or_leak(
    database: Database,
    question_id: str,
    answer: str,
    self_score: Any,
) -> None:
    create(database)
    with (
        database.engine.connect().execution_options(sqlite_begin_immediate=True) as connection,
        connection.begin(),
    ):
        with pytest.raises(QuizPersistenceError, match="VALIDATION_ERROR") as failure:
            write_draft(connection, question_id=question_id, answer=answer, self_score=self_score)
        assert str(failure.value) == "VALIDATION_ERROR"
        assert get_attempt(connection, "attempt_a").answers == ()


def test_blank_pending_and_explicit_writing_zero_are_distinct(database: Database) -> None:
    create(database)
    with (
        database.engine.connect().execution_options(sqlite_begin_immediate=True) as connection,
        connection.begin(),
    ):
        write_draft(connection, question_id="q_CLOZE_0", answer=" \t\n")
        write_draft(connection, identity="pending", question_id="q_WRITING_0", answer="")
        before = get_attempt(connection, "attempt_a")
        assert [answer.state for answer in before.answers] == ["BLANK", "BLANK"]
        assert before.answers[1].self_score is None
        write_draft(
            connection,
            identity="explicit_zero",
            question_id="q_WRITING_0",
            answer="",
            revision=1,
            self_score=0,
        )
        restored = get_attempt(connection, "attempt_a")
        assert restored.answers[1].self_score == 0
        assert restored.answers[1].state == "SCORED"
        assert restored.submission_revision == 3


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE quiz_questions SET snapshot_payload='{}'",
        "UPDATE quiz_questions SET position=position+1",
        "DELETE FROM quiz_questions",
        "DELETE FROM quiz_attempts",
        "UPDATE quiz_attempts SET snapshot_revision=2",
        "UPDATE quiz_attempts SET submission_revision=1",
        "INSERT OR REPLACE INTO quiz_questions SELECT * FROM quiz_questions WHERE position=0",
        "INSERT OR REPLACE INTO quiz_attempts SELECT * FROM quiz_attempts",
    ],
)
def test_sql_cannot_mutate_replace_or_delete_snapshots(database: Database, sql: str) -> None:
    expected = create(database)
    with database.engine.begin() as connection:
        with pytest.raises(IntegrityError):
            connection.exec_driver_sql(sql)
        assert get_attempt(connection, "attempt_a") == expected


@pytest.mark.parametrize("position", [-1, 0, 4, 5, 30])
def test_sql_rejects_duplicate_gapped_or_sealed_ordering(database: Database, position: int) -> None:
    expected = create(database)
    with database.engine.begin() as connection:
        payload = storage_payload(SNAPSHOT_ADAPTER.validate_json(json.dumps(question(19))))
        with pytest.raises(IntegrityError):
            connection.exec_driver_sql(
                "INSERT INTO quiz_questions VALUES ('q_MCQ_19','attempt_a',?,'MCQ','wf_19',?)",
                (position, payload),
            )
        assert get_attempt(connection, "attempt_a") == expected


def test_database_refuses_stale_revision_and_answer_replacement(database: Database) -> None:
    create(database)
    with (
        database.engine.connect().execution_options(sqlite_begin_immediate=True) as connection,
        connection.begin(),
    ):
        write_draft(connection)
        operation(connection, "next_op")
        for revision in (0, 1, 3):
            with pytest.raises(IntegrityError):
                connection.exec_driver_sql(
                    "UPDATE quiz_answers SET draft_revision=?,operation_id='next_op'", (revision,)
                )
        with pytest.raises(IntegrityError):
            connection.exec_driver_sql(
                "INSERT OR REPLACE INTO quiz_answers SELECT * FROM quiz_answers"
            )
        with pytest.raises(IntegrityError):
            connection.exec_driver_sql("DELETE FROM quiz_answers")
        assert get_attempt(connection, "attempt_a").submission_revision == 1


@pytest.mark.parametrize("fault", ["question_insert", "answer_aggregate"])
def test_savepoint_rolls_back_even_when_caller_catches_sql_failure(
    database: Database, fault: str
) -> None:
    if fault == "answer_aggregate":
        create(database)
    with (
        database.engine.connect().execution_options(sqlite_begin_immediate=True) as connection,
        connection.begin(),
    ):
        if fault == "question_insert":
            connection.exec_driver_sql(
                "CREATE TRIGGER synthetic_failure BEFORE INSERT ON quiz_questions "
                "WHEN NEW.position=2 BEGIN SELECT RAISE(ABORT,'Synthetic fault'); END"
            )
            with pytest.raises(IntegrityError, match="Synthetic fault"):
                create_attempt(
                    connection,
                    attempt_id="attempt_a",
                    note_date=DATE,
                    questions=question_set(),
                    created_at=NOW,
                )
            assert (
                connection.exec_driver_sql("SELECT count(*) FROM quiz_attempts").scalar_one() == 0
            )
            assert (
                connection.exec_driver_sql("SELECT count(*) FROM quiz_questions").scalar_one() == 0
            )
        else:
            connection.exec_driver_sql(
                "CREATE TRIGGER synthetic_failure BEFORE UPDATE OF submission_revision "
                "ON quiz_attempts BEGIN SELECT RAISE(ABORT,'Synthetic fault'); END"
            )
            with pytest.raises(IntegrityError, match="Synthetic fault"):
                write_draft(connection)
            restored = get_attempt(connection, "attempt_a")
            assert (restored.answers, restored.submission_revision) == ((), 0)


@pytest.mark.parametrize(
    "damage",
    ["missing_question", "empty", "bad_json", "changed_prompt", "changed_key", "bad_revision"],
)
def test_corruption_is_controlled_restore_failure(database: Database, damage: str) -> None:
    create(database)
    with database.engine.begin() as connection:
        # Simulate damaged storage on a synthetic database, never a real user database.
        for name in (
            "quiz_question_no_delete",
            "quiz_question_no_update",
            "quiz_attempt_immutable",
        ):
            connection.exec_driver_sql(f"DROP TRIGGER {name}")
        connection.exec_driver_sql("PRAGMA ignore_check_constraints=ON")
        if damage in {"missing_question", "empty"}:
            where = " WHERE position=0" if damage == "missing_question" else ""
            connection.exec_driver_sql("DELETE FROM quiz_questions" + where)
        elif damage == "bad_revision":
            connection.exec_driver_sql("UPDATE quiz_attempts SET snapshot_revision=2")
        else:
            row = connection.exec_driver_sql(
                "SELECT snapshot_payload FROM quiz_questions WHERE position=0"
            ).scalar_one()
            payload = json.loads(row)
            if damage == "changed_prompt":
                payload["promptEn"] = "corruption sentinel"
            elif damage == "changed_key":
                payload["correctOptionId"] = "o_b"
            value = "{corruption sentinel" if damage == "bad_json" else json.dumps(payload)
            connection.exec_driver_sql(
                "UPDATE quiz_questions SET snapshot_payload=? WHERE position=0", (value,)
            )
        with pytest.raises(QuizPersistenceError) as failure:
            get_attempt(connection, "attempt_a")
        assert failure.value.code == "QUIZ_RESTORE_REQUIRED"
        assert str(failure.value) == "QUIZ_RESTORE_REQUIRED"


def test_missing_attempt_is_not_fabricated(database: Database) -> None:
    with database.engine.connect() as connection:
        with pytest.raises(QuizPersistenceError, match="NOT_FOUND"):
            get_attempt(connection, "missing")


def test_writes_require_the_existing_caller_owned_writer_boundary(database: Database) -> None:
    with database.engine.connect() as connection:
        with pytest.raises(ValueError, match="caller-owned"):
            create_attempt(
                connection,
                attempt_id="attempt_a",
                note_date=DATE,
                questions=question_set(),
                created_at=NOW,
            )
        with connection.begin(), pytest.raises(ValueError, match="caller-owned"):
            create_attempt(
                connection,
                attempt_id="attempt_a",
                note_date=DATE,
                questions=question_set(),
                created_at=NOW,
            )


def test_missing_operation_fk_rolls_back_draft_and_aggregate(database: Database) -> None:
    create(database)
    with (
        database.engine.connect().execution_options(sqlite_begin_immediate=True) as connection,
        connection.begin(),
    ):
        with pytest.raises(IntegrityError):
            save_answer(
                connection,
                attempt_id="attempt_a",
                question_id="q_MCQ_0",
                answer="o_a",
                self_score=None,
                expected_draft_revision=0,
                operation_id="missing_operation",
                saved_at=NOW,
            )
        restored = get_attempt(connection, "attempt_a")
        assert (restored.answers, restored.submission_revision) == ((), 0)


@pytest.mark.parametrize("damage", ["state", "answer", "aggregate", "missing_table"])
def test_corrupted_draft_metadata_and_missing_tables_fail_closed(
    database: Database, damage: str
) -> None:
    create(database)
    with (
        database.engine.connect().execution_options(sqlite_begin_immediate=True) as connection,
        connection.begin(),
    ):
        write_draft(connection)
    with database.engine.begin() as connection:
        for name in (
            "quiz_answer_next_revision",
            "quiz_answer_writable_update",
            "quiz_answer_aggregate_update",
            "quiz_aggregate_revision",
        ):
            connection.exec_driver_sql(f"DROP TRIGGER {name}")
        if damage == "state":
            connection.exec_driver_sql("UPDATE quiz_answers SET state='BLANK'")
        elif damage == "answer":
            connection.exec_driver_sql("UPDATE quiz_answers SET answer='outside'")
        elif damage == "aggregate":
            connection.exec_driver_sql("UPDATE quiz_attempts SET submission_revision=9")
        else:
            connection.exec_driver_sql("DROP TABLE quiz_answers")
        with pytest.raises(QuizPersistenceError, match="QUIZ_RESTORE_REQUIRED"):
            get_attempt(connection, "attempt_a")


def terminal_result(connection: Connection, *, revision: int | None = None) -> QuizResult:
    attempt = get_attempt(connection, "attempt_a")
    snapshots = load_snapshot(connection, "attempt_a")
    scored = score_quiz(
        tuple(to_scoring_snapshot(q) for q in snapshots),
        [AnswerInput(a.question_id, a.answer, a.self_score) for a in attempt.answers],
    )
    return QuizResult.model_validate_json(
        json.dumps(
            {
                "attemptId": attempt.id,
                "status": "SUBMITTED",
                "submissionRevision": attempt.submission_revision if revision is None else revision,
                "objectiveScores": asdict(scored.objective_scores),
                "writingSelfScores": [asdict(q) for q in scored.writing_self_scores],
                "questionResults": [asdict(q) for q in scored.question_results],
                "reviewHandoffs": [
                    {
                        "wordFormId": identity,
                        "cardId": None,
                        "rating": rating,
                        "reviewEventId": None,
                        "status": "SKIPPED_INACTIVE",
                    }
                    for identity, rating in scored.weakest_ratings.items()
                ],
                "submittedAt": NOW.isoformat(),
            }
        )
    )


def prepare_terminal(database: Database) -> None:
    create(database)
    with (
        database.engine.connect().execution_options(sqlite_begin_immediate=True) as connection,
        connection.begin(),
    ):
        write_draft(connection, question_id="q_WRITING_0", answer="", self_score=0)
        connection.exec_driver_sql("UPDATE source_files SET status='MISSING'")


def test_terminal_persistence_releases_keys_only_in_result_and_freezes_drafts(
    database: Database,
) -> None:
    prepare_terminal(database)
    with (
        database.engine.connect().execution_options(sqlite_begin_immediate=True) as connection,
        connection.begin(),
    ):
        before = get_attempt(connection, "attempt_a")
        operation(connection, "submit_a")
        result = terminal_result(connection)
        terminal = store_submission(connection, result=result, operation_id="submit_a")
        assert terminal.status == "SUBMITTED"
        assert terminal.questions == before.questions
        assert terminal.result == result
        assert "explanationVi" in terminal.model_dump_json(by_alias=True)
        assert "explanationVi" not in json.dumps([q.model_dump() for q in terminal.questions])
        with pytest.raises(QuizPersistenceError, match="ALREADY_SUBMITTED"):
            write_draft(connection, identity="late_draft", question_id="q_WRITING_0", revision=1)
        with pytest.raises(QuizPersistenceError, match="ALREADY_SUBMITTED"):
            store_submission(connection, result=result, operation_id="submit_a")
    with database.engine.connect() as connection:
        assert get_attempt(connection, "attempt_a") == terminal
        assert connection.exec_driver_sql("SELECT count(*) FROM review_events").scalar_one() == 0


def test_terminal_content_becomes_visible_to_other_connections_only_after_commit(
    database: Database, tmp_path: Path
) -> None:
    prepare_terminal(database)
    with (
        database.engine.connect().execution_options(sqlite_begin_immediate=True) as writer,
        writer.begin(),
    ):
        operation(writer, "submit_visibility")
        store_submission(writer, result=terminal_result(writer), operation_id="submit_visibility")
        with database.engine.connect() as reader:
            pending = get_attempt(reader, "attempt_a")
            assert pending.status == "IN_PROGRESS"
            assert pending.result is None
            assert "explanationVi" not in pending.model_dump_json(by_alias=True)
    database.close()
    reopened = Database(tmp_path / "quiz.db")
    try:
        reopened.initialize()
        with reopened.engine.connect() as reader:
            terminal = get_attempt(reader, "attempt_a")
            assert terminal.status == "SUBMITTED"
            assert terminal.result is not None
            assert "explanationVi" in terminal.model_dump_json(by_alias=True)
    finally:
        reopened.close()


def test_stale_submission_revision_changes_nothing(database: Database) -> None:
    prepare_terminal(database)
    with (
        database.engine.connect().execution_options(sqlite_begin_immediate=True) as connection,
        connection.begin(),
    ):
        operation(connection, "stale_submit")
        with pytest.raises(QuizPersistenceError, match="REVISION_CONFLICT"):
            store_submission(
                connection,
                result=terminal_result(connection, revision=0),
                operation_id="stale_submit",
            )
        assert get_attempt(connection, "attempt_a").result is None


@pytest.mark.parametrize("damage", ["key", "identity", "type", "writing_score"])
def test_terminal_result_must_match_the_snapshot_and_saved_score(
    database: Database, damage: str
) -> None:
    prepare_terminal(database)
    with (
        database.engine.connect().execution_options(sqlite_begin_immediate=True) as connection,
        connection.begin(),
    ):
        raw = terminal_result(connection).model_dump(mode="json", by_alias=True)
        if damage == "key":
            raw["questionResults"][0]["correctOptionId"] = "o_b"
        elif damage == "identity":
            raw["questionResults"][0]["questionId"] = "foreign"
        elif damage == "type":
            raw["questionResults"][0] = {
                "questionId": "q_MCQ_0",
                "type": "WRITING",
                "outcome": "SELF_SCORED",
                "selfScore": 0,
                "rating": "AGAIN",
            }
            raw["writingSelfScores"].append(
                {"questionId": "q_MCQ_0", "selfScore": 0, "rating": "AGAIN"}
            )
        else:
            raw["questionResults"][-1]["selfScore"] = 1
            raw["writingSelfScores"][0]["selfScore"] = 1
        invalid = QuizResult.model_validate_json(json.dumps(raw))
        operation(connection, "invalid_terminal")
        with pytest.raises(QuizPersistenceError, match="VALIDATION_ERROR"):
            store_submission(connection, result=invalid, operation_id="invalid_terminal")
        assert get_attempt(connection, "attempt_a").result is None


@pytest.mark.parametrize("damage", ["missing", "empty", "malformed", "wrong_revision"])
def test_missing_or_corrupted_terminal_result_is_never_a_success(
    database: Database, damage: str
) -> None:
    prepare_terminal(database)
    with (
        database.engine.connect().execution_options(sqlite_begin_immediate=True) as connection,
        connection.begin(),
    ):
        operation(connection, "submit_a")
        result = terminal_result(connection)
        store_submission(connection, result=result, operation_id="submit_a")
    with database.engine.begin() as connection:
        connection.exec_driver_sql("DROP TRIGGER quiz_attempt_immutable")
        connection.exec_driver_sql("PRAGMA ignore_check_constraints=ON")
        if damage == "missing":
            replacement = None
        elif damage == "empty":
            replacement = "{}"
        elif damage == "malformed":
            replacement = "{malformed sentinel"
        else:
            raw = result.model_dump(mode="json", by_alias=True)
            raw["submissionRevision"] = 9
            replacement = json.dumps(raw)
        connection.exec_driver_sql("UPDATE quiz_attempts SET result_payload=?", (replacement,))
        with pytest.raises(QuizPersistenceError, match="QUIZ_RESTORE_REQUIRED"):
            get_attempt(connection, "attempt_a")


def test_outer_transaction_failure_rolls_back_terminal_reviews_and_receipt(
    database: Database,
) -> None:
    create(database)
    with (
        database.engine.connect().execution_options(sqlite_begin_immediate=True) as connection,
        connection.begin(),
    ):
        write_draft(connection, question_id="q_WRITING_0", answer="", self_score=0)
    ledger = OperationLedger(database.engine)
    claimed = ledger.claim(
        kind="QUIZ_SUBMIT",
        key="synthetic-submit-intent",
        method="POST",
        path="/synthetic/submission",
        body={"submissionRevision": 1},
        preconditions={},
    )
    with database.engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TRIGGER synthetic_receipt_failure BEFORE UPDATE OF status ON operations "
            "WHEN NEW.status='SUCCEEDED' BEGIN SELECT RAISE(ABORT,'Synthetic receipt fault'); END"
        )

    def local_write(connection: Connection) -> None:
        raw = terminal_result(connection).model_dump(mode="python")
        handoffs = []
        for index in range(2):
            event = record_review(
                connection,
                card_id=f"card_{index}",
                event_id=f"event_{index}",
                operation_id=claimed.operation.operation_id,
                source="QUIZ",
                rating="AGAIN",
                reviewed_at=NOW,
                attempt_id="attempt_a",
            )
            assert event is not None
            handoffs.append(
                {
                    "word_form_id": f"wf_{index}",
                    "card_id": f"card_{index}",
                    "rating": "AGAIN",
                    "review_event_id": event.id,
                    "status": "APPLIED",
                }
            )
        raw["review_handoffs"] = handoffs
        store_submission(
            connection,
            result=QuizResult.model_validate(raw),
            operation_id=claimed.operation.operation_id,
        )

    with pytest.raises(IntegrityError, match="Synthetic receipt fault"):
        ledger.complete(
            claimed.operation.operation_id,
            response_status=201,
            result_ref="attempt_a",
            local_write=local_write,
        )
    with database.engine.connect() as connection:
        restored = get_attempt(connection, "attempt_a")
        assert (restored.status, restored.result, restored.submission_revision) == (
            "IN_PROGRESS",
            None,
            1,
        )
        assert connection.exec_driver_sql("SELECT count(*) FROM review_events").scalar_one() == 0
        assert connection.exec_driver_sql("SELECT sum(box) FROM review_cards").scalar_one() == 0
    persisted = ledger.get(claimed.operation.operation_id)
    assert persisted is not None and persisted.status == "PENDING"


def test_operation_receipt_failure_rolls_back_draft_and_aggregate(database: Database) -> None:
    create(database)
    ledger = OperationLedger(database.engine)
    claimed = ledger.claim(
        kind="QUIZ_DRAFT",
        key="synthetic-draft-intent",
        method="PUT",
        path="/synthetic/answer",
        body={"answer": "o_a"},
        preconditions={},
    )
    with database.engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TRIGGER synthetic_receipt_failure BEFORE UPDATE OF status ON operations "
            "WHEN NEW.status='SUCCEEDED' BEGIN SELECT RAISE(ABORT,'Synthetic receipt fault'); END"
        )

    def local_write(connection: Connection) -> None:
        save_answer(
            connection,
            attempt_id="attempt_a",
            question_id="q_MCQ_0",
            answer="o_a",
            self_score=None,
            expected_draft_revision=0,
            operation_id=claimed.operation.operation_id,
            saved_at=NOW,
        )

    with pytest.raises(IntegrityError, match="Synthetic receipt fault"):
        ledger.complete(
            claimed.operation.operation_id,
            response_status=200,
            result_ref="answer_ref",
            local_write=local_write,
        )
    with database.engine.connect() as connection:
        restored = get_attempt(connection, "attempt_a")
        assert (restored.answers, restored.submission_revision) == ((), 0)
    persisted = ledger.get(claimed.operation.operation_id)
    assert persisted is not None and persisted.status == "PENDING"


def test_migration_extends_source_journal_and_preserves_all_prior_rows(tmp_path: Path) -> None:
    scripts = ScriptDirectory.from_config(migration_config())
    assert scripts.get_heads() == ["0010_quiz_answer_receipts"]
    quiz = scripts.get_revision("0008_quiz")
    journal = scripts.get_revision("0007_source_journal")
    assert quiz is not None and quiz.down_revision == "0007_source_journal"
    assert journal is not None and journal.down_revision == "0006_ai_admission"
    database = Database(tmp_path / "upgrade.db")

    def prior_head(connection: Connection) -> None:
        config = migration_config()
        config.attributes["connection"] = connection
        command.upgrade(config, "0007_source_journal")

    try:
        database.initialize(migrate=prior_head)
        with database.engine.connect() as connection:
            assert connection.exec_driver_sql(
                "SELECT version_num FROM alembic_version"
            ).scalar_one() == "0007_source_journal"
        seed_sources(database, 1)
        with (
            database.engine.connect().execution_options(sqlite_begin_immediate=True) as connection,
            connection.begin(),
        ):
            operation(connection, "historical_journal")
            operation(connection, "historical_review")
            record_review(
                connection,
                card_id="card_0",
                event_id="historical_event",
                operation_id="historical_review",
                source="FLASHCARD",
                rating="GOOD",
                reviewed_at=NOW,
            )
            connection.exec_driver_sql(
                "INSERT INTO source_write_journal "
                "(operation_id,source_id,old_hash,new_hash,intended_projection_revision,"
                "effect_plan,response_status,result_ref,state,created_at,updated_at) "
                "VALUES ('historical_journal','src_quiz',?,?,2,?,"
                "201,'synthetic_ref','PREPARED',?,?)",
                (
                    "a" * 64,
                    "b" * 64,
                    '{"version":1,"forms":[],"links":[],"removed":[]}',
                    NOW.isoformat(),
                    NOW.isoformat(),
                ),
            )
            tables = [
                str(row[0])
                for row in connection.exec_driver_sql(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name!='alembic_version'"
                )
            ]
            before = {
                table: connection.exec_driver_sql(f'SELECT * FROM "{table}"').all()
                for table in tables
            }
        first = database.initialize()
        second = database.initialize()
        assert first == second
        assert first.schema_revision == "0010_quiz_answer_receipts"
        with database.engine.connect() as connection:
            for table, rows in before.items():
                assert connection.exec_driver_sql(f'SELECT * FROM "{table}"').all() == rows
            assert connection.exec_driver_sql("PRAGMA integrity_check").all() == [("ok",)]
            assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
            assert (
                connection.exec_driver_sql("SELECT count(*) FROM quiz_attempts").scalar_one() == 0
            )
    finally:
        database.close()


def test_fresh_repeat_initialization_and_forward_only_downgrade(tmp_path: Path) -> None:
    database = Database(tmp_path / "fresh.db")
    try:
        first = database.initialize()
        assert database.initialize() == first
        assert first.schema_revision == "0010_quiz_answer_receipts"
        with (
            database.engine.connect().execution_options(sqlite_begin_immediate=True) as connection,
            connection.begin(),
        ):
            config = migration_config()
            config.attributes["connection"] = connection
            with pytest.raises(RuntimeError, match="preserve quiz history"):
                command.downgrade(config, "0007_source_journal")
            assert connection.exec_driver_sql(
                "SELECT version_num FROM alembic_version"
            ).scalar_one() == "0010_quiz_answer_receipts"
    finally:
        database.close()

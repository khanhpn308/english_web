"""Transaction-scoped quiz persistence. No HTTP, generation, scoring or SRS orchestration.

Writers require T005's BEGIN IMMEDIATE connection. Savepoints protect each primitive
even if a caller catches its failure. T014/T048 can include these writes in the same
outer transaction as reviews and the operation receipt; nothing here commits it.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Literal

from backend.app.assessment.questions import (
    PUBLIC_QUESTION_ADAPTER,
    SNAPSHOT_ADAPTER,
    Answer,
    AnswerPrecondition,
    ClozeSnapshot,
    MCQSnapshot,
    QuestionSet,
    QuestionSnapshot,
    QuizAttempt,
    QuizResult,
    WritingQuestion,
    answer_etag,
    storage_payload,
)
from pydantic import ValidationError
from sqlalchemy import Connection
from sqlalchemy.exc import DBAPIError


class QuizPersistenceError(ValueError):
    """Content-free contract category for a future HTTP adapter to map."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _writer(connection: Connection) -> None:
    if not connection.in_transaction() or not connection.get_execution_options().get(
        "sqlite_begin_immediate", False
    ):
        raise ValueError("Quiz writes require a caller-owned SQLite writer transaction")


def _revision(value: int) -> None:
    if type(value) is not int or value < 0:
        raise QuizPersistenceError("VALIDATION_ERROR")


def _utc(instant: datetime) -> str:
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise QuizPersistenceError("VALIDATION_ERROR")
    return instant.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _digest(
    questions: tuple[QuestionSnapshot, ...],
    *,
    attempt_id: str,
    note_date: str,
    snapshot_revision: int,
) -> str:
    canonical = json.dumps(
        {
            "id": attempt_id,
            "noteDate": note_date,
            "snapshotRevision": snapshot_revision,
            "questions": [json.loads(storage_payload(question)) for question in questions],
        },
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _validate_answer(question: QuestionSnapshot, answer: Answer) -> None:
    if answer.question_id != question.id:
        raise ValueError("Answer question identity mismatch")
    if isinstance(question, MCQSnapshot) and answer.answer and answer.answer not in {
        option.id for option in question.options
    }:
        raise ValueError("Answer option is outside the snapshot")
    if not isinstance(question, WritingQuestion) and answer.self_score is not None:
        raise ValueError("Objective self-score must be null")
    # This only checks draft state, not correctness or terminal scoring.
    expected_state = _answer_state(question, answer.answer, answer.self_score)
    if answer.state != expected_state:
        raise ValueError("Answer draft state mismatch")


def _answer_state(
    question: QuestionSnapshot, answer: str, self_score: int | None
) -> Literal["BLANK", "DRAFT", "SCORED"]:
    if self_score is not None:
        return "SCORED"
    if isinstance(question, ClozeSnapshot):
        blank = not answer.strip(" \t\r\n\f\v")
    elif isinstance(question, WritingQuestion):
        blank = not answer.strip()
    else:
        blank = not answer
    return "BLANK" if blank else "DRAFT"


def _validate_result(result: QuizResult, questions: tuple[QuestionSnapshot, ...]) -> None:
    indexed = {question.id: question for question in questions}
    if {item.question_id for item in result.question_results} != set(indexed):
        raise ValueError("Result question membership mismatch")
    for item in result.question_results:
        question = indexed[item.question_id]
        if item.type != question.type:
            raise ValueError("Result question type mismatch")
        if isinstance(question, MCQSnapshot):
            if item.type != "MCQ" or (
                item.correct_option_id,
                item.explanation_vi,
            ) != (question.correct_option_id, question.explanation_vi):
                raise ValueError("Result key differs from snapshot")
        elif isinstance(question, ClozeSnapshot):
            if item.type != "CLOZE" or (
                item.accepted_answers,
                item.explanation_vi,
            ) != (question.accepted_answers, question.explanation_vi):
                raise ValueError("Result alternatives differ from snapshot")
    if {handoff.word_form_id for handoff in result.review_handoffs} != {
        question.word_form_id for question in questions
    }:
        raise ValueError("Result form membership mismatch")
    for kind, metric in (
        ("MCQ", result.objective_scores.mcq),
        ("CLOZE", result.objective_scores.cloze),
    ):
        outcomes = [item for item in result.question_results if item.type == kind]
        if (metric.total, metric.attempted, metric.correct) != (
            len(outcomes),
            sum(item.outcome != "BLANK" for item in outcomes),
            sum(item.outcome == "CORRECT" for item in outcomes),
        ):
            raise ValueError("Result metrics differ from question outcomes")


def _terminal_answers(result: QuizResult, answers: tuple[Answer, ...]) -> None:
    indexed = {answer.question_id: answer for answer in answers}
    for item in result.question_results:
        if item.type == "WRITING":
            answer = indexed.get(item.question_id)
            if answer is None or answer.self_score != item.self_score:
                raise ValueError("Terminal writing score differs from the saved draft")
            if not answer.answer.strip() and item.self_score > 0:
                raise ValueError("Blank writing requires an explicit zero")


def _restore(
    connection: Connection, attempt_id: str
) -> tuple[QuizAttempt, tuple[QuestionSnapshot, ...]]:
    try:
        row = (
            connection.exec_driver_sql("SELECT * FROM quiz_attempts WHERE id=?", (attempt_id,))
            .mappings()
            .first()
        )
        if row is None:
            raise QuizPersistenceError("NOT_FOUND")
        created = datetime.fromisoformat(row["created_at"])
        if created.tzinfo is None or _utc(created) != row["created_at"]:
            raise ValueError("Invalid snapshot creation time")
        stored = (
            connection.exec_driver_sql(
                "SELECT * FROM quiz_questions WHERE attempt_id=? ORDER BY position", (attempt_id,)
            )
            .mappings()
            .all()
        )
        if len(stored) != row["question_count"] or [q["position"] for q in stored] != list(
            range(len(stored))
        ):
            raise ValueError("Incomplete snapshot ordering")
        questions = tuple(SNAPSHOT_ADAPTER.validate_json(q["snapshot_payload"]) for q in stored)
        QuestionSet(questions=questions)
        for question, record in zip(questions, stored, strict=True):
            if (question.id, question.type, question.word_form_id) != (
                record["id"],
                record["type"],
                record["word_form_id"],
            ):
                raise ValueError("Stored snapshot identity mismatch")
        if _digest(
            questions,
            attempt_id=row["id"],
            note_date=row["note_date"],
            snapshot_revision=row["snapshot_revision"],
        ) != row["snapshot_digest"]:
            raise ValueError("Snapshot integrity mismatch")
        drafts = (
            connection.exec_driver_sql(
                "SELECT a.* FROM quiz_answers a JOIN quiz_questions q "
                "ON q.attempt_id=a.attempt_id AND q.id=a.question_id "
                "WHERE a.attempt_id=? ORDER BY q.position",
                (attempt_id,),
            )
            .mappings()
            .all()
        )
        # Do not let a JOIN hide orphaned answers in a damaged database.
        count = connection.exec_driver_sql(
            "SELECT count(*) FROM quiz_answers WHERE attempt_id=?", (attempt_id,)
        ).scalar_one()
        if count != len(drafts):
            raise ValueError("Orphaned answer")
        answers = tuple(
            Answer.model_validate(
                {**record, "saved_at": datetime.fromisoformat(record["saved_at"])}
            )
            for record in drafts
        )
        indexed = {question.id: question for question in questions}
        for answer in answers:
            _validate_answer(indexed[answer.question_id], answer)
        if any(
            _utc(answer.saved_at) != record["saved_at"]
            for answer, record in zip(answers, drafts, strict=True)
        ):
            raise ValueError("Noncanonical draft time")
        result = (
            QuizResult.model_validate_json(row["result_payload"])
            if row["result_payload"] is not None
            else None
        )
        if result is not None:
            _validate_result(result, questions)
            _terminal_answers(result, answers)
            result_digest = hashlib.sha256(
                result.model_dump_json(by_alias=True).encode("utf-8")
            ).hexdigest()
            if result_digest != row["result_digest"]:
                raise ValueError("Terminal result integrity mismatch")
            if (
                row["submitted_at"] != _utc(result.submitted_at)
                or not row["submission_operation_id"]
            ):
                raise ValueError("Terminal evidence mismatch")
        elif (
            row["submitted_at"] is not None
            or row["submission_operation_id"] is not None
            or row["result_digest"] is not None
        ):
            raise ValueError("Unexpected terminal evidence")
        revisions = {answer.question_id: answer.draft_revision for answer in answers}
        attempt = QuizAttempt(
            id=row["id"],
            note_date=row["note_date"],
            status=row["status"],
            questions=tuple(
                PUBLIC_QUESTION_ADAPTER.validate_python(q.model_dump(by_alias=True))
                for q in questions
            ),
            answers=answers,
            saved_answer_count=len(answers),
            snapshot_revision=row["snapshot_revision"],
            submission_revision=row["submission_revision"],
            result=result,
            answer_preconditions=tuple(
                AnswerPrecondition(
                    question_id=question.id,
                    draft_revision=revisions.get(question.id, 0),
                    etag=answer_etag(
                        row["id"], question.id, revisions.get(question.id, 0),
                    ),
                )
                for question in questions
            ),
        )
        return attempt, questions
    except QuizPersistenceError as error:
        if error.code == "NOT_FOUND":
            raise
        raise QuizPersistenceError("QUIZ_RESTORE_REQUIRED") from None
    except (ValueError, TypeError, KeyError, DBAPIError):
        # Never expose decoder/Pydantic/SQL diagnostics containing stored answers.
        raise QuizPersistenceError("QUIZ_RESTORE_REQUIRED") from None


def get_attempt(connection: Connection, attempt_id: str) -> QuizAttempt:
    """Read the public snapshot and acknowledged drafts. Keys appear only in terminal result."""
    return _restore(connection, attempt_id)[0]


def load_snapshot(connection: Connection, attempt_id: str) -> tuple[QuestionSnapshot, ...]:
    """Explicit backend-only read for T048/T059. Ordinary model serialization omits keys."""
    return _restore(connection, attempt_id)[1]


def create_attempt(
    connection: Connection,
    *,
    attempt_id: str,
    note_date: str,
    questions: QuestionSet,
    created_at: datetime,
    snapshot_revision: int = 1,
) -> QuizAttempt:
    """Persist one validated creation snapshot; caller allocates stable IDs and time."""
    _writer(connection)
    try:
        questions = QuestionSet.model_validate(questions)
        validated = QuizAttempt(
            id=attempt_id,
            note_date=note_date,
            status="IN_PROGRESS",
            questions=tuple(
                PUBLIC_QUESTION_ADAPTER.validate_python(q.model_dump(by_alias=True))
                for q in questions.questions
            ),
            answers=(),
            saved_answer_count=0,
            snapshot_revision=snapshot_revision,
            submission_revision=0,
            result=None,
            answer_preconditions=tuple(
                AnswerPrecondition(
                    question_id=q.id, draft_revision=0, etag=answer_etag(attempt_id, q.id, 0)
                )
                for q in questions.questions
            ),
        )
    except ValidationError:
        raise QuizPersistenceError("VALIDATION_ERROR") from None
    created = _utc(created_at)
    for word_form_id in {q.word_form_id for q in questions.questions}:
        eligible = connection.exec_driver_sql(
            "SELECT 1 FROM word_form_sources w JOIN source_files s ON s.id=w.source_id "
            "JOIN word_forms f ON f.id=w.word_form_id "
            "WHERE w.word_form_id=? AND w.note_date=? AND s.note_date=? AND s.status='VALID'",
            (word_form_id, note_date, note_date),
        ).first()
        if eligible is None:
            raise QuizPersistenceError("VALIDATION_ERROR")
    with connection.begin_nested():
        connection.exec_driver_sql(
            "INSERT INTO quiz_attempts "
            "(id,note_date,question_count,snapshot_digest,created_at,snapshot_revision) "
            "VALUES (?,?,?,?,?,?)",
            (
                validated.id,
                validated.note_date,
                len(questions.questions),
                _digest(
                    questions.questions,
                    attempt_id=validated.id,
                    note_date=validated.note_date,
                    snapshot_revision=validated.snapshot_revision,
                ),
                created,
                validated.snapshot_revision,
            ),
        )
        for position, question in enumerate(questions.questions):
            connection.exec_driver_sql(
                "INSERT INTO quiz_questions "
                "(id,attempt_id,position,type,word_form_id,snapshot_payload) VALUES (?,?,?,?,?,?)",
                (
                    question.id,
                    attempt_id,
                    position,
                    question.type,
                    question.word_form_id,
                    storage_payload(question),
                ),
            )
        restored = get_attempt(connection, attempt_id)
    return restored


def save_answer(
    connection: Connection,
    *,
    attempt_id: str,
    question_id: str,
    answer: str,
    self_score: int | None,
    expected_draft_revision: int,
    operation_id: str,
    saved_at: datetime,
) -> Answer:
    """CAS draft primitive; T047/T014 own HTTP preconditions and receipt reconciliation."""
    _writer(connection)
    _revision(expected_draft_revision)
    if type(answer) is not str:
        raise QuizPersistenceError("VALIDATION_ERROR")
    attempt, questions = _restore(connection, attempt_id)
    if attempt.status == "SUBMITTED":
        raise QuizPersistenceError("ALREADY_SUBMITTED")
    question = next((q for q in questions if q.id == question_id), None)
    if question is None:
        raise QuizPersistenceError("CROSS_RESOURCE_MISMATCH")
    previous = next((a for a in attempt.answers if a.question_id == question_id), None)
    if (previous.draft_revision if previous else 0) != expected_draft_revision:
        raise QuizPersistenceError("REVISION_CONFLICT")
    try:
        draft = Answer(
            attempt_id=attempt_id,
            question_id=question_id,
            answer=answer,
            self_score=self_score,
            draft_revision=expected_draft_revision + 1,
            saved_at=saved_at,
            state=_answer_state(question, answer, self_score),
            operation_id=operation_id,
        )
        _validate_answer(question, draft)
    except ValueError:
        raise QuizPersistenceError("VALIDATION_ERROR") from None
    timestamp = _utc(saved_at)
    with connection.begin_nested():
        if previous is None:
            connection.exec_driver_sql(
                "INSERT INTO quiz_answers "
                "(attempt_id,question_id,answer,self_score,draft_revision,"
                "saved_at,state,operation_id) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    attempt_id,
                    question_id,
                    answer,
                    self_score,
                    draft.draft_revision,
                    timestamp,
                    draft.state,
                    operation_id,
                ),
            )
        else:
            updated = connection.exec_driver_sql(
                "UPDATE quiz_answers SET answer=?,self_score=?,draft_revision=?,saved_at=?,"
                "state=?,operation_id=? WHERE attempt_id=? AND question_id=? AND draft_revision=?",
                (
                    answer,
                    self_score,
                    draft.draft_revision,
                    timestamp,
                    draft.state,
                    operation_id,
                    attempt_id,
                    question_id,
                    expected_draft_revision,
                ),
            )
            if updated.rowcount != 1:
                raise QuizPersistenceError("REVISION_CONFLICT")
        get_attempt(connection, attempt_id)
    return draft


def store_answer_receipt(connection: Connection, answer: Answer) -> None:
    """Append the canonical draft in the same caller-owned transaction as completion."""
    _writer(connection)
    answer = Answer.model_validate(answer)
    connection.exec_driver_sql(
        "INSERT INTO quiz_answer_receipts "
        "(attempt_id,question_id,draft_revision,answer,self_score,saved_at,state,operation_id) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (
            answer.attempt_id, answer.question_id, answer.draft_revision, answer.answer,
            answer.self_score, _utc(answer.saved_at), answer.state, answer.operation_id,
        ),
    )


def get_answer_receipt(connection: Connection, operation_id: str) -> Answer:
    """Read an exact historical receipt; never substitute the latest answer."""
    row = connection.exec_driver_sql(
        "SELECT * FROM quiz_answer_receipts WHERE operation_id=?", (operation_id,)
    ).mappings().first()
    if row is None:
        raise QuizPersistenceError("QUIZ_RESTORE_REQUIRED")
    try:
        return Answer.model_validate({**row, "saved_at": datetime.fromisoformat(row["saved_at"])})
    except (ValueError, TypeError):
        raise QuizPersistenceError("QUIZ_RESTORE_REQUIRED") from None


def store_submission(
    connection: Connection, *, result: QuizResult, operation_id: str
) -> QuizAttempt:
    """Store an already-scored terminal result in the caller's review/receipt transaction.

    No scoring, review mutation, operation claim or commit occurs here. T048 must
    supply current revisions and persist its SRS handoffs before calling this primitive.
    """
    _writer(connection)
    try:
        result = QuizResult.model_validate(result)
    except ValidationError:
        raise QuizPersistenceError("VALIDATION_ERROR") from None
    attempt, questions = _restore(connection, result.attempt_id)
    if attempt.status == "SUBMITTED":
        raise QuizPersistenceError("ALREADY_SUBMITTED")
    if attempt.submission_revision != result.submission_revision:
        raise QuizPersistenceError("REVISION_CONFLICT")
    try:
        _validate_result(result, questions)
        _terminal_answers(result, attempt.answers)
    except ValueError:
        raise QuizPersistenceError("VALIDATION_ERROR") from None
    payload = result.model_dump_json(by_alias=True)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    with connection.begin_nested():
        connection.exec_driver_sql(
            "UPDATE quiz_attempts SET status='SUBMITTED',result_payload=?,"
            "result_digest=?,submitted_at=?,"
            "submission_operation_id=? WHERE id=? AND submission_revision=?",
            (
                payload,
                digest,
                _utc(result.submitted_at),
                operation_id,
                result.attempt_id,
                result.submission_revision,
            ),
        )
        restored = get_attempt(connection, result.attempt_id)
    return restored

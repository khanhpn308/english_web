"""Local revision-safe autosave using T014's durable claim/completion boundary."""

import re
from collections.abc import Callable
from datetime import UTC, datetime

from backend.app.application.operations import OperationConflict, OperationLedger
from backend.app.assessment.questions import (
    Answer,
    AnswerText,
    Revision,
    SelfScore,
    StrictModel,
    answer_etag,
)
from backend.app.assessment.repository import (
    QuizPersistenceError,
    get_answer_receipt,
    get_attempt,
    save_answer,
    store_answer_receipt,
)
from pydantic import field_validator
from sqlalchemy import Connection
from sqlalchemy.exc import SQLAlchemyError

ETAG_PATTERN = r'^"qa-v1-[0-9a-f]{64}"$'


class AnswerDraftRequest(StrictModel):
    answer: AnswerText
    self_score: SelfScore | None = None
    draft_revision: Revision

    @field_validator("answer")
    @classmethod
    def unicode_text(cls, value: str) -> str:
        try:
            value.encode("utf-8")
        except UnicodeError:
            raise ValueError("Invalid Unicode text") from None
        return value


class SaveAnswerService:
    def __init__(
        self, ledger: OperationLedger, *, now: Callable[[], datetime] | None = None
    ) -> None:
        self.ledger = ledger
        self.now = now or (lambda: datetime.now(UTC))

    def _receipt(self, identity: str, attempt_id: str, question_id: str) -> Answer:
        try:
            with self.ledger.engine.connect() as connection, connection.begin():
                receipt = get_answer_receipt(connection, identity)
        except SQLAlchemyError:
            raise OperationConflict(503, "STORAGE_BUSY", identity) from None
        if (receipt.attempt_id, receipt.question_id, receipt.operation_id) != (
            attempt_id, question_id, identity
        ):
            raise QuizPersistenceError("QUIZ_RESTORE_REQUIRED")
        return receipt

    def save(
        self, *, attempt_id: str, question_id: str, intent: AnswerDraftRequest,
        if_match: str, idempotency_key: str,
    ) -> Answer:
        if re.fullmatch(ETAG_PATTERN, if_match) is None:
            raise OperationConflict(422, "VALIDATION_ERROR")
        # Current resource identity checks precede replay, but revision/terminal
        # checks belong after replay. Session validation is the production guard.
        with self.ledger.engine.connect() as connection, connection.begin():
            attempt = get_attempt(connection, attempt_id)
            if question_id not in {q.id for q in attempt.questions}:
                exists = connection.exec_driver_sql(
                    "SELECT 1 FROM quiz_questions WHERE id=?", (question_id,)
                ).first()
                raise OperationConflict(
                    422 if exists is not None else 404,
                    "CROSS_RESOURCE_MISMATCH" if exists is not None else "NOT_FOUND",
                )
        claimed = self.ledger.claim(
            kind="QUIZ_ANSWER_DRAFT", key=idempotency_key, method="PUT",
            path=f"/api/v1/quiz-attempts/{attempt_id}/answers/{question_id}",
            body=intent.model_dump(mode="json", by_alias=True, exclude_unset=True),
            preconditions={"If-Match": if_match},
        )
        operation = claimed.operation
        identity = operation.operation_id
        if claimed.replayed:
            if operation.status != "SUCCEEDED":
                raise OperationConflict(
                    operation.response_status or 409,
                    operation.error_category or "IDEMPOTENCY_IN_FLIGHT", identity,
                )
            if operation.result_ref != identity or operation.response_status != 200:
                raise QuizPersistenceError("QUIZ_RESTORE_REQUIRED")
            return self._receipt(identity, attempt_id, question_id)

        def write(connection: Connection) -> None:
            current = get_attempt(connection, attempt_id)
            if current.status == "SUBMITTED":
                raise QuizPersistenceError("ALREADY_SUBMITTED")
            previous = next((a for a in current.answers if a.question_id == question_id), None)
            revision = previous.draft_revision if previous else 0
            if revision != intent.draft_revision or if_match != answer_etag(
                attempt_id, question_id, revision
            ):
                raise QuizPersistenceError("REVISION_CONFLICT")
            score = intent.self_score
            if "self_score" not in intent.model_fields_set and previous is not None:
                score = previous.self_score
            draft = save_answer(
                connection, attempt_id=attempt_id, question_id=question_id,
                answer=intent.answer, self_score=score, expected_draft_revision=revision,
                operation_id=identity, saved_at=self.now(),
            )
            store_answer_receipt(connection, draft)

        try:
            self.ledger.complete(
                identity, response_status=200, result_ref=identity, local_write=write
            )
        except QuizPersistenceError as error:
            status = 422 if error.code in {"VALIDATION_ERROR", "CROSS_RESOURCE_MISMATCH"} else 409
            if error.code == "NOT_FOUND":
                status = 404
            try:
                self.ledger.record_failure(
                    identity, error_category=error.code, response_status=status
                )
            except SQLAlchemyError:
                raise OperationConflict(503, "STORAGE_BUSY", identity) from None
            raise OperationConflict(status, error.code, identity) from None
        except SQLAlchemyError:
            # A COMMIT exception is ambiguous until the durable journal is read.
            # Never relabel committed work as FAILED or reapply a pending intent.
            try:
                persisted = self.ledger.get(identity)
                if persisted is not None and persisted.status == "SUCCEEDED":
                    return self._receipt(identity, attempt_id, question_id)
                if persisted is not None and persisted.status == "PENDING":
                    self.ledger.record_failure(
                        identity, error_category="STORAGE_BUSY", response_status=503
                    )
            except SQLAlchemyError:
                raise OperationConflict(503, "STORAGE_BUSY", identity) from None
            raise OperationConflict(503, "STORAGE_BUSY", identity) from None
        # Read canonical durable evidence only after the completion transaction exits.
        return self._receipt(identity, attempt_id, question_id)

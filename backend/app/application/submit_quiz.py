"""Local terminal scoring and grouped SRS writes in T014's receipt transaction."""

from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime
from secrets import token_urlsafe

from backend.app.application.operations import OperationConflict, OperationLedger
from backend.app.assessment.questions import QuizResult, Revision, StrictModel, to_scoring_snapshot
from backend.app.assessment.repository import (
    QuizPersistenceError,
    get_attempt,
    load_snapshot,
    store_submission,
)
from backend.app.assessment.scoring import AnswerInput, QuizScoringError, score_quiz
from backend.app.review.models import InactiveCardError, record_review
from sqlalchemy import Connection
from sqlalchemy.exc import SQLAlchemyError


class SubmissionRequest(StrictModel):
    submission_revision: Revision


class SubmitQuizService:
    def __init__(
        self, ledger: OperationLedger, *, now: Callable[[], datetime] | None = None
    ) -> None:
        self.ledger = ledger
        self.now = now or (lambda: datetime.now(UTC))

    def _receipt(self, identity: str, attempt_id: str) -> QuizResult:
        try:
            with self.ledger.engine.connect() as connection, connection.begin():
                attempt = get_attempt(connection, attempt_id)
                owner: str = connection.exec_driver_sql(
                    "SELECT submission_operation_id FROM quiz_attempts WHERE id=?", (attempt_id,)
                ).scalar_one()
        except QuizPersistenceError as error:
            # The repository redacts DBAPI failures as restoration errors.
            if isinstance(error.__context__, SQLAlchemyError):
                raise OperationConflict(503, "STORAGE_BUSY", identity) from None
            raise
        except SQLAlchemyError:
            raise OperationConflict(503, "STORAGE_BUSY", identity) from None
        if attempt.result is None or owner != identity:
            raise QuizPersistenceError("QUIZ_RESTORE_REQUIRED")
        return attempt.result

    def submit(
        self,
        *,
        attempt_id: str,
        intent: SubmissionRequest,
        idempotency_key: str,
    ) -> QuizResult:
        claimed = self.ledger.claim(
            kind="QUIZ_SUBMISSION",
            key=idempotency_key,
            method="POST",
            path=f"/api/v1/quiz-attempts/{attempt_id}/submissions",
            body=intent.model_dump(mode="json", by_alias=True),
            preconditions={},
        )
        operation = claimed.operation
        identity = operation.operation_id
        if claimed.replayed:
            if operation.status != "SUCCEEDED":
                raise OperationConflict(
                    operation.response_status or 409,
                    operation.error_category or "IDEMPOTENCY_IN_FLIGHT",
                    identity,
                )
            if operation.result_ref != attempt_id or operation.response_status != 201:
                raise QuizPersistenceError("QUIZ_RESTORE_REQUIRED")
            return self._receipt(identity, attempt_id)

        def write(connection: Connection) -> None:
            current = get_attempt(connection, attempt_id)
            if current.status == "SUBMITTED":
                raise QuizPersistenceError("ALREADY_SUBMITTED")
            if current.submission_revision != intent.submission_revision:
                raise QuizPersistenceError("REVISION_CONFLICT")
            snapshot = load_snapshot(connection, attempt_id)
            try:
                scored = score_quiz(
                    tuple(to_scoring_snapshot(q) for q in snapshot),
                    tuple(
                        AnswerInput(a.question_id, a.answer, a.self_score) for a in current.answers
                    ),
                )
            except QuizScoringError:
                raise QuizPersistenceError("VALIDATION_ERROR") from None
            # Sample the scheduling time after acquiring the SQLite writer lock.
            submitted_at = self.now()
            handoffs = []
            for form, rating in scored.weakest_ratings.items():
                card_id = connection.exec_driver_sql(
                    "SELECT card_id FROM review_cards WHERE word_form_id=?", (form,)
                ).scalar_one_or_none()
                review = None
                if card_id is not None:
                    try:
                        review = record_review(
                            connection,
                            card_id=card_id,
                            event_id=f"review_{token_urlsafe(18)}",
                            operation_id=identity,
                            source="QUIZ",
                            rating=rating,
                            reviewed_at=submitted_at,
                            attempt_id=attempt_id,
                        )
                    except InactiveCardError:
                        review = None
                handoffs.append(
                    {
                        "word_form_id": form,
                        "card_id": card_id,
                        "rating": rating,
                        "review_event_id": review.id if review is not None else None,
                        "status": "APPLIED" if review is not None else "SKIPPED_INACTIVE",
                    }
                )
            result = QuizResult.model_validate(
                {
                    "attempt_id": attempt_id,
                    "status": "SUBMITTED",
                    "submission_revision": current.submission_revision,
                    "objective_scores": asdict(scored.objective_scores),
                    "writing_self_scores": tuple(asdict(s) for s in scored.writing_self_scores),
                    "question_results": tuple(asdict(q) for q in scored.question_results),
                    "review_handoffs": handoffs,
                    "submitted_at": submitted_at,
                }
            )
            store_submission(connection, result=result, operation_id=identity)

        try:
            self.ledger.complete(
                identity,
                response_status=201,
                result_ref=attempt_id,
                local_write=write,
            )
        except QuizPersistenceError as error:
            code = "STORAGE_BUSY" if isinstance(error.__context__, SQLAlchemyError) else error.code
            status = 503 if code == "STORAGE_BUSY" else 422 if code == "VALIDATION_ERROR" else 409
            if code == "NOT_FOUND":
                status = 404
            try:
                self.ledger.record_failure(
                    identity,
                    error_category=code,
                    response_status=status,
                )
            except SQLAlchemyError:
                raise OperationConflict(503, "STORAGE_BUSY", identity) from None
            raise OperationConflict(status, code, identity) from None
        except SQLAlchemyError:
            # A COMMIT error can follow durable success. Reconcile without reapplying.
            try:
                persisted = self.ledger.get(identity)
                if persisted is not None and persisted.status == "SUCCEEDED":
                    return self._receipt(identity, attempt_id)
                if persisted is not None and persisted.status == "PENDING":
                    self.ledger.record_failure(
                        identity,
                        error_category="STORAGE_BUSY",
                        response_status=503,
                    )
            except SQLAlchemyError:
                raise OperationConflict(503, "STORAGE_BUSY", identity) from None
            raise OperationConflict(503, "STORAGE_BUSY", identity) from None
        return self._receipt(identity, attempt_id)

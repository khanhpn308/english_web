"""Local submission; production SessionGuard owns session and Origin validation."""

from typing import Any

from backend.app.application.operations import OperationConflict
from backend.app.application.submit_quiz import SubmissionRequest, SubmitQuizService
from backend.app.assessment.questions import QuizResult
from backend.app.assessment.repository import QuizPersistenceError
from backend.app.http.errors import error_response
from backend.app.http.quiz import AttemptId, IdempotencyKey, QuizErrorResponse, _restore_error
from backend.app.platform.telemetry import request_id
from fastapi import APIRouter, Request
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import JSONResponse

router = APIRouter(prefix="/api/v1/quiz-attempts", tags=["assessments"])
_ERRORS: dict[int | str, dict[str, Any]] = {
    status: {"model": QuizErrorResponse} for status in (400, 401, 403, 404, 409, 413, 422, 503)
}


def _error(status: int, code: str, attempt_id: str, identity: str | None = None) -> JSONResponse:
    if code == "QUIZ_RESTORE_REQUIRED":
        return _restore_error(attempt_id)
    details = {"kind": "RETRY", "operationId": identity} if identity is not None else None
    if code in {"REVISION_CONFLICT", "ALREADY_SUBMITTED"}:
        error: dict[str, Any] = {
            "code": code,
            "requestId": request_id(),
            "message": "Quiz revision conflict"
            if code == "REVISION_CONFLICT"
            else "Quiz attempt already submitted",
        }
        if details is not None:
            error["details"] = details
        response = JSONResponse({"error": error}, status_code=status)
    else:
        response = error_response(status, code, details)
    response.headers["Cache-Control"] = "no-store"
    return response


@router.post(
    "/{attemptId}/submissions", response_model=QuizResult, status_code=201, responses=_ERRORS
)
def post_submission(
    request: Request,
    attemptId: AttemptId,
    body: SubmissionRequest,
    idempotency_key: IdempotencyKey,
) -> JSONResponse:
    if request.query_params or len(request.headers.getlist("idempotency-key")) != 1:
        return _error(422, "VALIDATION_ERROR", attemptId)
    service = getattr(request.app.state, "submission_service", None)
    if not isinstance(service, SubmitQuizService):
        return _error(503, "CONFIGURATION_REQUIRED", attemptId)
    if not request.app.state.ready:
        return _error(503, "STORAGE_BUSY", attemptId)
    try:
        result = service.submit(attempt_id=attemptId, intent=body, idempotency_key=idempotency_key)
        return JSONResponse(
            result.model_dump(mode="json", by_alias=True),
            status_code=201,
            headers={"Cache-Control": "no-store"},
        )
    except OperationConflict as error:
        return _error(error.status_code, error.code, attemptId, error.operation_id)
    except QuizPersistenceError as error:
        return _error(404 if error.code == "NOT_FOUND" else 409, error.code, attemptId)
    except SQLAlchemyError:
        return _error(503, "STORAGE_BUSY", attemptId)

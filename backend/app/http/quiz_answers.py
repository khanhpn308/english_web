"""PUT local drafts. Production SessionGuard owns authentication and Origin checks."""

from secrets import token_urlsafe
from typing import Annotated, Any

from backend.app.application.operations import OperationConflict
from backend.app.application.save_answer import ETAG_PATTERN, AnswerDraftRequest, SaveAnswerService
from backend.app.assessment.questions import Answer, answer_etag
from backend.app.assessment.repository import QuizPersistenceError
from backend.app.http.errors import error_response
from backend.app.http.quiz import AttemptId, IdempotencyKey, QuizErrorResponse
from fastapi import APIRouter, Header, Request
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import JSONResponse

router = APIRouter(prefix="/api/v1/quiz-attempts", tags=["assessments"])
IfMatch = Annotated[str, Header(alias="If-Match", pattern=ETAG_PATTERN)]
_ERRORS: dict[int | str, dict[str, Any]] = {
    status: {"model": QuizErrorResponse} for status in (400, 401, 403, 404, 409, 413, 422, 503)
}
_LOCAL_MESSAGES = {
    "REVISION_CONFLICT": "Answer revision conflict",
    "ALREADY_SUBMITTED": "Quiz attempt already submitted",
    "CROSS_RESOURCE_MISMATCH": "Question does not belong to this attempt",
    "QUIZ_RESTORE_REQUIRED": "Quiz answer requires restoration",
}


def _error(status: int, code: str, attempt_id: str, identity: str | None = None) -> JSONResponse:
    details: dict[str, Any] | None = None
    if code == "QUIZ_RESTORE_REQUIRED":
        details = {"kind": "RESTORE", "attemptId": attempt_id, "guidanceCode": code}
    elif identity is not None:
        details = {"kind": "RETRY", "operationId": identity}
    if code in _LOCAL_MESSAGES:
        error: dict[str, Any] = {
            "code": code, "message": _LOCAL_MESSAGES[code], "requestId": f"req_{token_urlsafe(12)}"
        }
        if details is not None:
            error["details"] = details
        response = JSONResponse({"error": error}, status_code=status)
    else:
        response = error_response(status, code, details)
    response.headers["Cache-Control"] = "no-store"
    return response


@router.put(
    "/{attemptId}/answers/{questionId}",
    response_model=Answer,
    responses={
        **_ERRORS,
        200: {
            "description": "Durably saved Answer or exact historical receipt",
            "headers": {"ETag": {"schema": {"type": "string", "pattern": ETAG_PATTERN}}},
        },
    },
)
def put_answer(
    request: Request, attemptId: AttemptId, questionId: AttemptId,
    body: AnswerDraftRequest, if_match: IfMatch, idempotency_key: IdempotencyKey,
) -> JSONResponse:
    if request.query_params or any(
        len(request.headers.getlist(name)) != 1 for name in ("if-match", "idempotency-key")
    ):
        return _error(422, "VALIDATION_ERROR", attemptId)
    service = getattr(request.app.state, "answer_service", None)
    if not isinstance(service, SaveAnswerService):
        return _error(503, "CONFIGURATION_REQUIRED", attemptId)
    if not request.app.state.ready:
        return _error(503, "STORAGE_BUSY", attemptId)
    try:
        saved = service.save(
            attempt_id=attemptId, question_id=questionId, intent=body,
            if_match=if_match, idempotency_key=idempotency_key,
        )
        return JSONResponse(
            saved.model_dump(mode="json", by_alias=True),
            headers={
                "Cache-Control": "no-store",
                "ETag": answer_etag(attemptId, questionId, saved.draft_revision),
            },
        )
    except OperationConflict as error:
        return _error(error.status_code, error.code, attemptId, error.operation_id)
    except QuizPersistenceError as error:
        return _error(404 if error.code == "NOT_FOUND" else 409, error.code, attemptId)
    except SQLAlchemyError:
        return _error(503, "STORAGE_BUSY", attemptId)

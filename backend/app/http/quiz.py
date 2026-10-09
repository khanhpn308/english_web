"""Creation and offline immutable attempt reads. Drafts/submission belong to T047/T048."""

import asyncio
from secrets import token_urlsafe
from typing import Annotated, Any, Literal

from backend.app.application.create_quiz import (
    CreateQuizRequest,
    CreateQuizService,
    QuizConsentRequired,
    QuizRestoreRequired,
)
from backend.app.application.operations import OperationConflict
from backend.app.assessment.questions import QuizAttempt
from backend.app.assessment.repository import QuizPersistenceError
from backend.app.http.errors import error_response
from fastapi import APIRouter, Header, Path, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import JSONResponse

router = APIRouter(prefix="/api/v1/quiz-attempts", tags=["assessments"])
IdempotencyKey = Annotated[
    str, Header(alias="Idempotency-Key", min_length=1, max_length=128, pattern=r"^[\x20-\x7e]+$")
]
AttemptId = Annotated[str, Path(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")]


class RetryDetails(BaseModel):
    kind: Literal["RETRY"]
    operationId: str


class ConsentDetails(BaseModel):
    kind: Literal["AI_CONSENT"]
    consentState: Literal["NOT_GRANTED", "GRANTED", "REVOKED", "STALE"]
    currentPolicyVersion: str | None


class RestoreDetails(BaseModel):
    kind: Literal["RESTORE"]
    attemptId: str
    guidanceCode: Literal["QUIZ_RESTORE_REQUIRED"]


class FieldError(BaseModel):
    field: str
    reason: str


class FieldErrorDetails(BaseModel):
    kind: Literal["FIELD_ERRORS"]
    fields: list[FieldError]


class QuizError(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str
    message: str
    requestId: str
    details: Annotated[
        RetryDetails | ConsentDetails | RestoreDetails | FieldErrorDetails,
        Field(discriminator="kind"),
    ] | None = None


class QuizErrorResponse(BaseModel):
    error: QuizError


_ERRORS: dict[int | str, dict[str, Any]] = {
    status: {"model": QuizErrorResponse}
    for status in (400, 401, 403, 404, 409, 413, 422, 500, 502, 503)
}


def _restore_error(attempt_id: str) -> JSONResponse:
    # T006's shared message catalog predates T034. Keep this new contract category
    # local to the allowed adapter rather than changing the catalog out of scope.
    return JSONResponse(
        {
            "error": {
                "code": "QUIZ_RESTORE_REQUIRED",
                "message": "Quiz snapshot requires restoration",
                "requestId": f"req_{token_urlsafe(12)}",
                "details": {
                    "kind": "RESTORE",
                    "attemptId": attempt_id,
                    "guidanceCode": "QUIZ_RESTORE_REQUIRED",
                },
            }
        },
        status_code=409,
        headers={"Cache-Control": "no-store"},
    )


def _operation_error(error: OperationConflict) -> JSONResponse:
    if isinstance(error, QuizRestoreRequired):
        return _restore_error(error.attempt_id)
    details = error.details if isinstance(error, QuizConsentRequired) else None
    if details is None and error.operation_id is not None:
        details = {"kind": "RETRY", "operationId": error.operation_id}
    response = error_response(error.status_code, error.code, details)
    response.headers["Cache-Control"] = "no-store"
    return response


def _public(attempt: QuizAttempt, status: int = 200) -> JSONResponse:
    return JSONResponse(
        attempt.model_dump(mode="json", by_alias=True),
        status_code=status,
        headers={"Cache-Control": "no-store"},
    )


async def _create_until_disconnect(
    request: Request,
    service: CreateQuizService,
    body: CreateQuizRequest,
    key: str,
) -> JSONResponse:
    async def disconnected() -> None:
        while True:
            message = await request.receive()
            if message["type"] == "http.disconnect":
                return

    creation = asyncio.create_task(
        service.create(
            intent=body,
            idempotency_key=key,
            request_start_time=getattr(request.state, "request_start_time", None),
            finalize=lambda attempt: _public(attempt, 201),
            on_operation=lambda identity: setattr(request.state, "quiz_operation_id", identity),
        )
    )
    watcher = asyncio.create_task(disconnected())
    try:
        done, _ = await asyncio.wait({creation, watcher}, return_when=asyncio.FIRST_COMPLETED)
        if creation not in done:
            failure = watcher.exception()
            if isinstance(failure, TimeoutError):
                # The service owns the same deadline and durable operation ID.
                # Let its timeout response carry that reconciliation reference.
                response = await creation
            elif failure is not None:
                raise OperationConflict(503, "BRIDGE_UNAVAILABLE")
            else:
                raise asyncio.CancelledError
        else:
            response = creation.result()
        if not isinstance(response, JSONResponse):
            raise ValueError("Quiz finalizer did not return a response")
        return response
    finally:
        creation.cancel()
        watcher.cancel()
        # service.create transfers durable work to its lifespan-owned task before
        # propagating cancellation. Observe both route workers without cancelling
        # that cleanup on a second browser cancellation.
        settled = asyncio.ensure_future(asyncio.gather(creation, watcher, return_exceptions=True))
        while not settled.done():
            try:
                await asyncio.shield(settled)
            except asyncio.CancelledError:
                continue


@router.post("", response_model=QuizAttempt, status_code=201, responses=_ERRORS)
async def post_quiz(
    request: Request, body: CreateQuizRequest, idempotency_key: IdempotencyKey
) -> JSONResponse:
    if request.query_params:
        return error_response(422, "VALIDATION_ERROR")
    service = getattr(request.app.state, "quiz_service", None)
    if not isinstance(service, CreateQuizService):
        return error_response(503, "CONFIGURATION_REQUIRED")
    if not request.app.state.ready:
        return error_response(503, "STORAGE_BUSY")
    try:
        return await _create_until_disconnect(request, service, body, idempotency_key)
    except OperationConflict as error:
        return _operation_error(error)
    except (SQLAlchemyError, ValueError):
        return error_response(503, "STORAGE_BUSY")


@router.get("/{attemptId}", response_model=QuizAttempt, responses=_ERRORS)
def get_quiz(request: Request, attemptId: AttemptId) -> JSONResponse:
    if request.query_params:
        return error_response(400, "INVALID_QUERY")
    service = getattr(request.app.state, "quiz_service", None)
    if not isinstance(service, CreateQuizService):
        return error_response(503, "CONFIGURATION_REQUIRED")
    try:
        return _public(service.get(attemptId))
    except QuizPersistenceError as error:
        if error.code == "NOT_FOUND":
            return error_response(404, "NOT_FOUND")
        return _restore_error(attemptId)
    except SQLAlchemyError:
        return error_response(503, "STORAGE_BUSY")

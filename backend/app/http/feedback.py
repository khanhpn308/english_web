"""Explicit user feedback requests and offline history behind production security guards."""

import asyncio
from typing import Annotated, Any

from backend.app.application.feedback import Feedback, FeedbackRequest, FeedbackService
from backend.app.application.operations import OperationConflict
from backend.app.assessment.repository import QuizPersistenceError
from backend.app.http.quiz import AttemptId, IdempotencyKey, QuizErrorResponse, _operation_error
from backend.app.http.quiz_answers import _error
from backend.app.http.search import PaginationView
from fastapi import APIRouter, Query, Request
from pydantic import BaseModel
from starlette.responses import JSONResponse

router = APIRouter(prefix="/api/v1/quiz-questions", tags=["assessments"])
_ERRORS: dict[int | str, dict[str, Any]] = {
    code: {"model": QuizErrorResponse} for code in (400, 401, 403, 404, 409, 413, 422, 502, 503)
}


class FeedbackPage(BaseModel):
    data: list[Feedback]
    pagination: PaginationView


def _service(request: Request) -> FeedbackService:
    service = getattr(request.app.state, "feedback_service", None)
    if not isinstance(service, FeedbackService):
        raise OperationConflict(503, "CONFIGURATION_REQUIRED")
    if not request.app.state.ready:
        raise OperationConflict(503, "STORAGE_BUSY")
    return service


def _failure(error: OperationConflict) -> JSONResponse:
    if error.code in {"CROSS_RESOURCE_MISMATCH", "REVISION_CONFLICT", "QUIZ_RESTORE_REQUIRED"}:
        return _error(error.status_code, error.code, "", error.operation_id)
    return _operation_error(error)


@router.post("/{questionId}/feedback", response_model=Feedback, status_code=201, responses=_ERRORS)
async def post_feedback(
    request: Request, questionId: AttemptId, body: FeedbackRequest, idempotency_key: IdempotencyKey
) -> JSONResponse:
    creation: asyncio.Task[Feedback] | None = None
    watcher: asyncio.Task[None] | None = None
    try:
        if request.query_params or len(request.headers.getlist("idempotency-key")) != 1:
            raise OperationConflict(422, "VALIDATION_ERROR")
        service = _service(request)

        async def disconnected() -> None:
            while True:
                if (await request.receive())["type"] == "http.disconnect":
                    return

        creation = asyncio.create_task(
            service.create(
                question_id=questionId,
                intent=body,
                idempotency_key=idempotency_key,
                request_start_time=getattr(request.state, "request_start_time", None),
                on_operation=lambda identity: setattr(
                    request.state, "feedback_operation_id", identity
                ),
            )
        )
        watcher = asyncio.create_task(disconnected())
        done, _ = await asyncio.wait({creation, watcher}, return_when=asyncio.FIRST_COMPLETED)
        if creation not in done:
            if isinstance(watcher.exception(), TimeoutError):
                result = await creation
            else:
                raise asyncio.CancelledError
        else:
            result = creation.result()
        return JSONResponse(
            result.model_dump(mode="json", by_alias=True, exclude_none=True),
            status_code=201,
            headers={"Cache-Control": "no-store"},
        )
    except OperationConflict as error:
        return _failure(error)
    finally:
        tasks = [task for task in (creation, watcher) if task is not None]
        for task in tasks:
            task.cancel()
        if tasks:
            settled = asyncio.ensure_future(asyncio.gather(*tasks, return_exceptions=True))
            while not settled.done():
                try:
                    await asyncio.shield(settled)
                except asyncio.CancelledError:
                    continue


@router.get("/{questionId}/feedback", response_model=FeedbackPage, responses=_ERRORS)
def get_feedback(
    request: Request,
    questionId: AttemptId,
    attemptId: Annotated[str | None, Query(max_length=64)] = None,
    questionFilter: Annotated[str | None, Query(alias="questionId", max_length=64)] = None,
    pageSize: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query(max_length=4096)] = None,
) -> JSONResponse:
    try:
        allowed = {"attemptId", "questionId", "pageSize", "cursor"}
        if set(request.query_params) - allowed or any(
            len(request.query_params.getlist(key)) != 1 for key in request.query_params
        ):
            raise OperationConflict(400, "INVALID_QUERY")
        page = _service(request).history(
            questionId,
            attempt_id=attemptId,
            question_filter=questionFilter,
            page_size=pageSize,
            cursor=cursor,
        )
        validated = FeedbackPage.model_validate(page)
        return JSONResponse(
            {
                "data": [
                    item.model_dump(mode="json", by_alias=True, exclude_none=True)
                    for item in validated.data
                ],
                "pagination": validated.pagination.model_dump(),
            },
            headers={"Cache-Control": "no-store"},
        )
    except OperationConflict as error:
        return _failure(error)
    except QuizPersistenceError as error:
        return _error(409, error.code, "")
    except Exception:
        return _error(503, "STORAGE_BUSY", "")

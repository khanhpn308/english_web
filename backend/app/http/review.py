"""Production HTTP boundary for local review queues and durable event writes."""

import re
from datetime import UTC, date, datetime
from secrets import token_urlsafe
from typing import Annotated, Any, Literal

from backend.app.application.operations import OperationConflict
from backend.app.http.errors import error_response
from backend.app.http.search import PaginationView
from backend.app.review.queue import (
    CardState,
    QueueCursorExpired,
    QueueSort,
    ReviewRejected,
    ReviewService,
)
from backend.app.review.srs import Rating
from fastapi import APIRouter, Body, Header, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import JSONResponse

router = APIRouter(prefix="/api/v1", tags=["review"])
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
_QUERY_KEYS = {"noteDate", "dueOnly", "cardState", "pageSize", "sortBy", "sortOrder", "cursor"}
_RFC3339 = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}[Tt][0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]+)?(?:[Zz]|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])\Z"
)
_ID = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$"
IdempotencyKey = Annotated[
    str, Header(alias="Idempotency-Key", min_length=1, max_length=128, pattern=r"^[\x20-\x7e]+$")
]
CardRevision = Annotated[
    str,
    Header(
        alias="If-Match", min_length=1, max_length=21,
        pattern=r'^(?:[0-9]{1,19}|"[0-9]{1,19}")$',
        description="Individual card queueRevision, as decimal digits or quoted decimal digits.",
    ),
]


def _review_request_schema(schema: dict[str, Any]) -> None:
    properties = schema["properties"]
    provenance = ("attemptId", "questionId")
    schema["oneOf"] = [
        {
            "type": "object",
            "properties": {
                "source": {"type": "string", "const": "FLASHCARD"},
                **{name: {"type": "null"} for name in provenance},
            },
            "required": ["source"],
        },
        {
            "type": "object",
            "properties": {
                "source": {"type": "string", "const": "QUIZ"},
                **{
                    name: next(
                        branch for branch in properties[name]["anyOf"]
                        if branch.get("type") != "null"
                    )
                    for name in provenance
                },
            },
            "required": ["source", *provenance],
        },
    ]


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, json_schema_extra=_review_request_schema)

    rating: Rating
    source: Literal["FLASHCARD", "QUIZ"]
    clientOccurredAt: str | None = Field(
        default=None, max_length=4096, json_schema_extra={"format": "date-time"}
    )
    attemptId: str | None = Field(default=None, pattern=_ID)
    questionId: str | None = Field(default=None, pattern=_ID)

    @field_validator("clientOccurredAt")
    @classmethod
    def timestamp(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not _RFC3339.fullmatch(value):
            raise ValueError("Expected an aware RFC 3339 timestamp")
        # Canonical persisted timestamps have microsecond precision. Additional
        # zero digits are lossless; reject meaningful digits that Python would truncate.
        fraction = re.search(r"\.([0-9]+)", value)
        if fraction is not None and any(digit != "0" for digit in fraction.group(1)[6:]):
            raise ValueError("Unsupported timestamp precision")
        try:
            parsed = datetime.fromisoformat(value.upper())
            if parsed.utcoffset() is None:
                raise ValueError("Expected an aware RFC 3339 timestamp")
            parsed.astimezone(UTC)
        except (ValueError, OverflowError):
            raise ValueError("Expected an aware RFC 3339 timestamp") from None
        return value

    @model_validator(mode="after")
    def provenance(self) -> "ReviewRequest":
        if self.source == "FLASHCARD" and (self.attemptId is not None or self.questionId is not None):
            raise ValueError("Flashcards cannot carry quiz provenance")
        if self.source == "QUIZ" and (self.attemptId is None or self.questionId is None):
            raise ValueError("Quiz provenance requires attempt and question")
        return self


class ReviewEventView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    cardId: str
    source: Literal["FLASHCARD", "QUIZ"]
    rating: Rating
    reviewedAt: str
    nextDueAt: str
    operationId: str
    attemptId: str | None = None
    questionId: str | None = None


class ReviewRetryDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["RETRY"]
    operationId: str


class ReviewFieldError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    reason: str


class ReviewFieldDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["FIELD_ERRORS"]
    fields: list[ReviewFieldError]


class ReviewError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Literal[
        "VALIDATION_ERROR", "INVALID_QUERY", "CURSOR_EXPIRED", "MALFORMED_JSON",
        "SESSION_REQUIRED", "SESSION_INVALID", "ORIGIN_FORBIDDEN", "PAYLOAD_TOO_LARGE",
        "NOT_FOUND", "REVISION_CONFLICT", "CROSS_RESOURCE_MISMATCH",
        "IDEMPOTENCY_KEY_REUSED", "IDEMPOTENCY_IN_FLIGHT", "STORAGE_BUSY",
        "CONFIGURATION_REQUIRED", "INTERNAL_ERROR",
    ]
    message: str
    requestId: str
    details: ReviewRetryDetails | ReviewFieldDetails | None = None


class ReviewErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: ReviewError


_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    status: {"model": ReviewErrorResponse} for status in (400, 401, 403, 404, 409, 413, 422, 500, 503)
}


def _rejection(error: OperationConflict | ReviewRejected) -> JSONResponse:
    details = None
    if error.operation_id is not None:
        details = {"kind": "RETRY", "operationId": error.operation_id}
    # The shared error catalog predates these canonical codes. Keep their mapping
    # local to the owned adapter rather than modifying another task's catalog.
    messages = {
        "REVISION_CONFLICT": "Card revision changed",
        "CROSS_RESOURCE_MISMATCH": "Resource references do not match",
    }
    if error.code in messages:
        payload: dict[str, object] = {
            "code": error.code, "message": messages[error.code],
            "requestId": f"req_{token_urlsafe(12)}",
        }
        if details is not None:
            payload["details"] = details
        return JSONResponse({"error": payload}, status_code=error.status_code)
    return error_response(error.status_code, error.code, details)


class ReviewCardView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cardId: str
    wordFormId: str
    lemma: str
    noteDates: list[str]
    state: CardState
    dueAt: str | None
    queueRevision: int = Field(ge=0)


class ReviewSortView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    by: QueueSort
    direction: Literal["ASC", "DESC"]


class ReviewQueueView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: list[ReviewCardView]
    pagination: PaginationView
    sort: ReviewSortView


def _service(request: Request) -> ReviewService | None:
    service = getattr(request.app.state, "review_service", None)
    return service if isinstance(service, ReviewService) else None


@router.get("/review-queue", response_model=ReviewQueueView, responses=_ERROR_RESPONSES)
def get_queue(
    request: Request,
    response: Response,
    noteDate: str | None = None,
    dueOnly: bool = True,
    cardState: CardState | None = None,
    pageSize: Annotated[int, Query(ge=1, le=100)] = 50,
    sortBy: QueueSort = "dueAt",
    sortOrder: Literal["ASC", "DESC", "asc", "desc"] = "ASC",
    cursor: str | None = None,
) -> ReviewQueueView | JSONResponse:
    if set(request.query_params) - _QUERY_KEYS:
        # Do not reflect attacker-controlled query keys into diagnostics.
        return error_response(422, "VALIDATION_ERROR")
    if any(len(request.query_params.getlist(key)) > 1 for key in _QUERY_KEYS):
        return error_response(400, "INVALID_QUERY")
    if "dueOnly" in request.query_params and request.query_params["dueOnly"] not in {
        "true", "false"
    }:
        return error_response(422, "VALIDATION_ERROR")
    if noteDate is not None:
        if not _DATE.fullmatch(noteDate):
            return error_response(400, "INVALID_QUERY")
        try:
            date.fromisoformat(noteDate)
        except ValueError:
            return error_response(400, "INVALID_QUERY")
    service = _service(request)
    if service is None or not request.app.state.ready:
        return error_response(503, "CONFIGURATION_REQUIRED")
    try:
        page = service.queue(
            note_date=noteDate, due_only=dueOnly, card_state=cardState,
            page_size=pageSize, sort_by=sortBy,
            sort_order="DESC" if sortOrder.lower() == "desc" else "ASC", cursor=cursor,
        )
    except QueueCursorExpired:
        return error_response(409, "CURSOR_EXPIRED")
    except SQLAlchemyError:
        return error_response(503, "STORAGE_BUSY")
    except (ValueError, RuntimeError, OverflowError, TypeError):
        return error_response(500, "INTERNAL_ERROR")
    response.headers["Cache-Control"] = "no-store"
    return ReviewQueueView(
        data=[ReviewCardView.model_validate(item) for item in page.data],
        pagination=PaginationView(
            nextCursor=page.next_cursor, pageSize=page.page_size, hasMore=page.has_more,
        ),
        sort=ReviewSortView(by=page.sort_by, direction=page.sort_order),
    )


@router.post(
    "/cards/{cardId}/reviews", response_model=ReviewEventView,
    response_model_exclude_none=True, status_code=201, responses=_ERROR_RESPONSES,
)
def post_review(
    request: Request,
    response: Response,
    cardId: str,
    body: Annotated[ReviewRequest, Body()],
    idempotency_key: IdempotencyKey,
    if_match: CardRevision,
) -> ReviewEventView | JSONResponse:
    if request.query_params:
        return error_response(400, "INVALID_QUERY")
    if re.fullmatch(_ID, cardId) is None:
        return error_response(422, "VALIDATION_ERROR")
    if any(len(request.headers.getlist(name)) != 1 for name in ("If-Match", "Idempotency-Key")):
        return error_response(422, "VALIDATION_ERROR")
    revision = int(if_match.strip('"'))
    if revision > 9223372036854775807:
        return error_response(422, "VALIDATION_ERROR")
    service = _service(request)
    if service is None or not request.app.state.ready:
        return error_response(503, "CONFIGURATION_REQUIRED")
    try:
        event = service.review(
            card_id=cardId, key=idempotency_key, expected_revision=revision,
            body=body.model_dump(mode="json"), rating=body.rating, source=body.source,
            client_occurred_at=datetime.fromisoformat(body.clientOccurredAt.upper())
            if body.clientOccurredAt is not None else None,
            attempt_id=body.attemptId, question_id=body.questionId,
        )
        view = ReviewEventView.model_validate(event)
    except (ReviewRejected, OperationConflict) as error:
        return _rejection(error)
    except SQLAlchemyError:
        return error_response(503, "STORAGE_BUSY")
    except (ValueError, RuntimeError, OverflowError, TypeError):
        return error_response(500, "INTERNAL_ERROR")
    response.headers["Cache-Control"] = "no-store"
    return view

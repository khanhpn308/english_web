"""Session-protected dashboard boundary."""

import re
from datetime import date
from typing import Annotated, Any, Literal

from backend.app.dashboard.formulas import DashboardRangeError, DashboardService
from backend.app.http.errors import error_response
from backend.app.review.srs import Rating
from fastapi import APIRouter, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import JSONResponse

router = APIRouter(prefix="/api/v1", tags=["dashboard"])
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
_QUERY_KEYS = {"from", "to"}


class DashboardStreak(BaseModel):
    model_config = ConfigDict(extra="forbid")

    currentDays: int | None = Field(ge=0)
    asOf: date


class FlashcardSelfRating(BaseModel):
    model_config = ConfigDict(extra="forbid")

    count: int = Field(ge=0)
    averageBucket: Rating | None


class DashboardObjectiveScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    correct: int = Field(ge=0)
    total: int = Field(ge=0)
    attempted: int = Field(ge=0)
    accuracy: float | None = Field(ge=0, le=1, allow_inf_nan=False)


class DashboardObjectiveAccuracy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mcq: DashboardObjectiveScore
    cloze: DashboardObjectiveScore


class DashboardWritingSelfScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scored: int = Field(ge=0)
    average: float | None = Field(ge=0, le=4, allow_inf_nan=False)


class DashboardSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dueCards: int = Field(ge=0)
    streak: DashboardStreak
    flashcardSelfRating: FlashcardSelfRating
    objectiveAccuracy: DashboardObjectiveAccuracy
    writingSelfScore: DashboardWritingSelfScore


class DashboardError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Literal[
        "INVALID_QUERY", "VALIDATION_ERROR", "SESSION_REQUIRED", "SESSION_INVALID",
        "ORIGIN_FORBIDDEN", "CONFIGURATION_REQUIRED", "STORAGE_BUSY", "INTERNAL_ERROR",
    ]
    message: str
    requestId: str


class DashboardErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: DashboardError


_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    status: {"model": DashboardErrorResponse} for status in (400, 401, 403, 422, 500, 503)
}


def _error(status: int, code: str) -> JSONResponse:
    result = error_response(status, code)
    result.headers["Cache-Control"] = "no-store"
    return result


# Source: https://fastapi.tiangolo.com/tutorial/response-model/#response_model-parameter
@router.get("/dashboard", response_model=DashboardSummary, responses=_ERROR_RESPONSES)
def get_dashboard(
    request: Request,
    response: Response,
    from_date: Annotated[str | None, Query(alias="from")] = None,
    to_date: Annotated[str | None, Query(alias="to")] = None,
) -> DashboardSummary | JSONResponse:
    if set(request.query_params) - _QUERY_KEYS:
        return _error(422, "VALIDATION_ERROR")
    if any(len(request.query_params.getlist(key)) > 1 for key in _QUERY_KEYS):
        return _error(400, "INVALID_QUERY")
    try:
        for value in (from_date, to_date):
            if value is not None and not _DATE.fullmatch(value):
                return _error(400, "INVALID_QUERY")
        first = date.fromisoformat(from_date) if from_date is not None else None
        last = date.fromisoformat(to_date) if to_date is not None else None
    except ValueError:
        return _error(400, "INVALID_QUERY")
    service = getattr(request.app.state, "dashboard_service", None)
    if not isinstance(service, DashboardService):
        return _error(503, "CONFIGURATION_REQUIRED")
    if not request.app.state.ready:
        return _error(503, "STORAGE_BUSY")
    try:
        projection = service.project(from_date=first, to_date=last)
        summary = DashboardSummary.model_validate({
            **projection.metrics,
            "streak": {"currentDays": projection.current_days, "asOf": projection.as_of},
        })
    except DashboardRangeError:
        return _error(400, "INVALID_QUERY")
    except SQLAlchemyError:
        return _error(503, "STORAGE_BUSY")
    except (AssertionError, ValueError, RuntimeError, OverflowError, TypeError):
        return _error(500, "INTERNAL_ERROR")
    response.headers["Cache-Control"] = "no-store"
    return summary

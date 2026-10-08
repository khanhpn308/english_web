"""HTTP adapter for the T027 word-form collection and detail reads."""

import re
from datetime import date
from typing import Annotated, Literal

from backend.app.http.errors import error_response
from backend.app.vocabulary.search_index import ProjectionVersionMismatchError
from backend.app.vocabulary.search_service import (
    CursorExpiredError,
    SearchQueryError,
    SearchService,
)
from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from starlette.responses import JSONResponse

router = APIRouter(prefix="/api/v1", tags=["word-forms"])

SortBy = Literal["relevance", "updatedAt", "lemma"]
SortOrder = Literal["ASC", "DESC", "asc", "desc"]
PartOfSpeech = Literal[
    "NOUN",
    "VERB",
    "ADJECTIVE",
    "ADVERB",
    "PRONOUN",
    "PREPOSITION",
    "CONJUNCTION",
    "INTERJECTION",
    "DETERMINER",
]
VerificationStatus = Literal["VERIFIED", "UNVERIFIED", "MISSING"]
SourceStatus = Literal["VALID", "INVALID", "MISSING"]
_DATE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
_QUERY_KEYS = {
    "meaningVi",
    "lemma",
    "partOfSpeech",
    "verificationStatus",
    "noteDate",
    "sourceStatus",
    "pageSize",
    "sortBy",
    "sortOrder",
    "cursor",
}


class MeaningView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    language: str
    verificationStatus: VerificationStatus


class ExampleView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    english: str
    vietnamese: str
    verificationStatus: VerificationStatus


class SourceReferenceView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sourceId: str
    noteDate: str
    status: SourceStatus


class CardView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    state: str
    dueAt: str | None


class WordFormSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    lemma: str
    partOfSpeech: str
    meaningViMatch: str
    verificationSummary: VerificationStatus
    noteDates: list[str]
    revision: int
    updatedAt: str


class PaginationView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nextCursor: str | None
    pageSize: int = Field(ge=1, le=100)
    hasMore: bool


class SortView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    by: SortBy
    direction: Literal["ASC", "DESC"]


class WordFormCollection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: list[WordFormSummary]
    pagination: PaginationView
    sort: SortView


class WordFormDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    familyId: str
    lemma: str
    partOfSpeech: str
    meaningsEn: list[MeaningView]
    meaningsVi: list[MeaningView]
    examples: list[ExampleView]
    ipaUs: str | None
    cambridgeUrl: str | None
    sourceRefs: list[SourceReferenceView]
    card: CardView | None
    revision: int
    verificationSummary: VerificationStatus
    updatedAt: str


def _service(request: Request) -> SearchService | None:
    service = getattr(request.app.state, "search_service", None)
    return service if isinstance(service, SearchService) else None


def _invalid_query(details: dict[str, object] | None = None) -> JSONResponse:
    return error_response(422, "VALIDATION_ERROR", details)


@router.get("/word-forms", response_model=WordFormCollection)
def list_word_forms(
    request: Request,
    meaningVi: Annotated[str | None, Query(max_length=4096)] = None,
    lemma: Annotated[str | None, Query(max_length=4096)] = None,
    partOfSpeech: PartOfSpeech | None = None,
    verificationStatus: VerificationStatus | None = None,
    noteDate: str | None = None,
    sourceStatus: SourceStatus | None = None,
    pageSize: Annotated[int, Query(ge=1, le=100)] = 50,
    sortBy: SortBy = "relevance",
    sortOrder: SortOrder = "ASC",
    cursor: str | None = None,
) -> WordFormCollection | JSONResponse:
    unknown = sorted(set(request.query_params) - _QUERY_KEYS)
    if unknown:
        return _invalid_query(
            {
                "kind": "FIELD_ERRORS",
                "fields": [{"field": name, "reason": "unknown"} for name in unknown],
            }
        )
    duplicate = sorted(key for key in _QUERY_KEYS if len(request.query_params.getlist(key)) > 1)
    if duplicate:
        return error_response(400, "INVALID_QUERY")
    if meaningVi == "":
        return error_response(400, "INVALID_QUERY")
    if noteDate is not None:
        if not _DATE.fullmatch(noteDate):
            return error_response(400, "INVALID_QUERY")
        try:
            date.fromisoformat(noteDate)
        except ValueError:
            return error_response(400, "INVALID_QUERY")
    service = _service(request)
    if service is None:
        return error_response(503, "CONFIGURATION_REQUIRED")
    direction: Literal["ASC", "DESC"] = "DESC" if sortOrder.lower() == "desc" else "ASC"
    try:
        page = service.search(
            meaning_vi=meaningVi,
            lemma=lemma,
            part_of_speech=partOfSpeech.upper() if partOfSpeech else None,
            verification_status=verificationStatus,
            note_date=noteDate,
            source_status=sourceStatus,
            page_size=pageSize,
            sort_by=sortBy,
            sort_order=direction,
            cursor=cursor,
        )
    except CursorExpiredError:
        return error_response(409, "CURSOR_EXPIRED")
    except ProjectionVersionMismatchError:
        if cursor is not None:
            return error_response(409, "CURSOR_EXPIRED")
        return error_response(503, "CONFIGURATION_REQUIRED")
    except SearchQueryError:
        return _invalid_query()
    return WordFormCollection(
        data=[WordFormSummary.model_validate(item) for item in page.data],
        pagination=PaginationView(
            nextCursor=page.next_cursor,
            pageSize=page.page_size,
            hasMore=page.has_more,
        ),
        sort=SortView(by=page.sort_by, direction=page.sort_order),
    )


@router.get("/word-forms/{wordFormId}", response_model=WordFormDetail)
def get_word_form(request: Request, wordFormId: str) -> WordFormDetail | JSONResponse:
    service = _service(request)
    if service is None:
        return error_response(503, "CONFIGURATION_REQUIRED")
    detail = service.detail(wordFormId)
    if detail is None:
        return error_response(404, "NOT_FOUND")
    return WordFormDetail.model_validate(detail)

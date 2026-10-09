"""HTTP API endpoints for Markdown sources and synchronization runs (T023)."""

from __future__ import annotations

import re
from typing import Annotated, Literal

from backend.app.application.operations import OperationConflict, OperationLedger
from backend.app.application.sync import CursorExpiredError, SyncReason, SyncService
from backend.app.http.errors import error_response
from backend.app.platform.telemetry import request_id
from fastapi import APIRouter, Header, Query, Request
from pydantic import BaseModel, ConfigDict
from starlette.responses import JSONResponse

router = APIRouter(prefix="/api/v1", tags=["sources"])

IdempotencyKeyHeader = Annotated[
    str, Header(alias="Idempotency-Key", min_length=1, max_length=128, pattern=r"^[\x20-\x7e]+$")
]

_ALLOWED_SOURCE_QUERY_PARAMS = {"status", "noteDate", "pageSize", "cursor", "sortBy", "sortOrder"}
_DATE_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}\Z")
_OPAQUE_ID_REGEX = re.compile(r"^[a-zA-Z0-9_-]{1,64}\Z")


class SourceFileView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    relativePath: str
    noteDate: str
    status: Literal["VALID", "INVALID", "MISSING"]
    revision: int
    etag: str
    lastParsedAt: str | None = None
    errorCode: str | None = None


class PagePagination(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nextCursor: str | None = None
    pageSize: int
    hasMore: bool


class PageSort(BaseModel):
    model_config = ConfigDict(extra="forbid")

    by: str
    direction: Literal["ASC", "DESC"]


class SourceFilePage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: list[SourceFileView]
    pagination: PagePagination
    sort: PageSort


class SyncRunView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    operationId: str
    status: Literal["QUEUED", "RUNNING", "COMPLETED", "FAILED"]
    reason: Literal["STARTUP", "MANUAL", "WATCHER"]
    sourceRevision: int | None = None
    sourcesScanned: int
    sourcesInvalid: int
    startedAt: str
    finishedAt: str | None = None


class CreateSyncRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: SyncReason


class SyncRunRetryDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["RETRY"]
    operationId: str


class SyncRunConflictError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Literal["IDEMPOTENCY_IN_FLIGHT"]
    message: str
    requestId: str
    details: SyncRunRetryDetails


class SyncRunConflictErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: SyncRunConflictError


def _internal_error_response() -> JSONResponse:
    """Return a contract-shaped redacted 500 INTERNAL_ERROR response."""
    return JSONResponse(
        {
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Internal server error",
                "requestId": request_id(),
            }
        },
        status_code=500,
    )


def _get_sync_service(request: Request) -> SyncService | None:
    if getattr(request.app.state, "storage_error", None) is not None:
        return None
    if not getattr(request.app.state, "ready", False):
        return None
    service = getattr(request.app.state, "sync_service", None)
    if isinstance(service, SyncService):
        return service
    return None


@router.get("/sources", response_model=SourceFilePage)
def get_sources(
    request: Request,
    status: Literal["VALID", "INVALID", "MISSING"] | None = None,
    noteDate: str | None = None,
    pageSize: int = Query(50, ge=1, le=100),
    cursor: str | None = None,
    sortBy: Literal["updatedAt", "noteDate", "status", "revision"] = "updatedAt",
    sortOrder: Literal["asc", "desc", "ASC", "DESC"] = "desc",
) -> SourceFilePage | JSONResponse:
    # Check for disallowed query parameters
    extra_params = set(request.query_params.keys()) - _ALLOWED_SOURCE_QUERY_PARAMS
    if extra_params:
        return JSONResponse(
            {
                "error": {
                    "code": "INVALID_QUERY",
                    "message": "Syntax or query shape invalid",
                    "requestId": request_id(),
                }
            },
            status_code=400,
        )

    if noteDate is not None:
        if _DATE_REGEX.fullmatch(noteDate) is None:
            return error_response(
                422,
                "VALIDATION_ERROR",
                {
                    "kind": "FIELD_ERRORS",
                    "fields": [{"field": "noteDate", "reason": "invalid_date_format"}],
                },
            )
        try:
            from datetime import date

            date.fromisoformat(noteDate)
        except ValueError:
            return error_response(
                422,
                "VALIDATION_ERROR",
                {
                    "kind": "FIELD_ERRORS",
                    "fields": [{"field": "noteDate", "reason": "invalid_date_format"}],
                },
            )

    service = _get_sync_service(request)
    if service is None:
        return error_response(503, "CONFIGURATION_REQUIRED")

    direction_normalized: Literal["ASC", "DESC"] = "ASC" if sortOrder.upper() == "ASC" else "DESC"

    try:
        sources, next_cursor, has_more = service.list_sources(
            status=status,
            note_date=noteDate,
            page_size=pageSize,
            cursor=cursor,
            sort_by=sortBy,
            direction=direction_normalized,
        )
    except CursorExpiredError:
        return JSONResponse(
            {
                "error": {
                    "code": "CURSOR_EXPIRED",
                    "message": "Cursor is invalid, tampered, or expired due to source changes",
                    "requestId": request_id(),
                }
            },
            status_code=409,
        )

    return SourceFilePage(
        data=[
            SourceFileView(
                id=s.id,
                relativePath=s.relative_path,
                noteDate=s.note_date,
                status=s.status,
                revision=s.revision,
                etag=s.etag,
                lastParsedAt=s.last_parsed_at,
                errorCode=s.error_code,
            )
            for s in sources
        ],
        pagination=PagePagination(
            nextCursor=next_cursor,
            pageSize=pageSize,
            hasMore=has_more,
        ),
        sort=PageSort(
            by=sortBy,
            direction=direction_normalized,
        ),
    )


@router.post(
    "/sync-runs",
    response_model=SyncRunView,
    status_code=202,
    responses={409: {"model": SyncRunConflictErrorResponse}},
)
def create_sync_run(
    request: Request,
    payload: CreateSyncRunRequest,
    idempotency_key: IdempotencyKeyHeader,
) -> SyncRunView | JSONResponse:
    service = _get_sync_service(request)
    if service is None:
        return error_response(503, "CONFIGURATION_REQUIRED")

    ledger: OperationLedger | None = getattr(request.app.state, "operation_ledger", None)
    if ledger is None:
        ledger = service.operation_ledger

    try:
        claim = ledger.claim(
            kind="SYNC_RUN",
            key=idempotency_key,
            method="POST",
            path="/api/v1/sync-runs",
            body={"reason": payload.reason},
            preconditions={},
        )
    except OperationConflict as e:
        if e.status_code == 422:
            return JSONResponse(
                {
                    "error": {
                        "code": "IDEMPOTENCY_KEY_REUSED",
                        "message": "Idempotency key reused with different request payload",
                        "requestId": request_id(),
                    }
                },
                status_code=422,
            )
        if e.status_code == 409:
            return JSONResponse(
                {
                    "error": {
                        "code": "IDEMPOTENCY_IN_FLIGHT",
                        "message": "Operation already in flight",
                        "details": {"kind": "RETRY", "operationId": e.operation_id},
                        "requestId": request_id(),
                    }
                },
                status_code=409,
            )
        return error_response(e.status_code, e.code)

    if claim.replayed:
        if claim.operation.status == "FAILED":
            status_code = claim.operation.response_status or 500
            error_code = claim.operation.error_category or "INTERNAL_ERROR"
            msg = "Internal server error" if error_code == "INTERNAL_ERROR" else "Operation failed"
            return JSONResponse(
                {
                    "error": {
                        "code": error_code,
                        "message": msg,
                        "requestId": request_id(),
                    }
                },
                status_code=status_code,
            )
        if claim.operation.status == "SUCCEEDED":
            ref = claim.operation.result_ref
            sync_run_id = ref.split(".")[0] if ref else ""
            if _OPAQUE_ID_REGEX.fullmatch(sync_run_id) is not None:
                existing_run = service.get_sync_run(sync_run_id)
                if existing_run is not None:
                    return SyncRunView(
                        id=existing_run.id,
                        operationId=existing_run.operation_id,
                        status=existing_run.status,
                        reason=existing_run.reason,
                        sourceRevision=existing_run.source_revision,
                        sourcesScanned=existing_run.sources_scanned,
                        sourcesInvalid=existing_run.sources_invalid,
                        startedAt=existing_run.started_at,
                        finishedAt=existing_run.finished_at,
                    )
        return JSONResponse(
            {
                "error": {
                    "code": "IDEMPOTENCY_IN_FLIGHT",
                    "message": "Operation already in flight",
                    "details": {"kind": "RETRY", "operationId": claim.operation.operation_id},
                    "requestId": request_id(),
                }
            },
            status_code=409,
        )

    try:
        result = service.sync(reason=payload.reason, operation_id=claim.operation.operation_id)
    except Exception:
        return _internal_error_response()

    return SyncRunView(
        id=result.id,
        operationId=result.operation_id,
        status=result.status,
        reason=result.reason,
        sourceRevision=result.source_revision,
        sourcesScanned=result.sources_scanned,
        sourcesInvalid=result.sources_invalid,
        startedAt=result.started_at,
        finishedAt=result.finished_at,
    )


@router.get("/sync-runs/{syncRunId}", response_model=SyncRunView)
def get_sync_run(
    request: Request,
    syncRunId: str,
) -> SyncRunView | JSONResponse:
    if request.query_params:
        return JSONResponse(
            {
                "error": {
                    "code": "INVALID_QUERY",
                    "message": "Syntax or query shape invalid",
                    "requestId": request_id(),
                }
            },
            status_code=400,
        )

    if _OPAQUE_ID_REGEX.fullmatch(syncRunId) is None:
        return error_response(404, "NOT_FOUND")

    service = _get_sync_service(request)
    if service is None:
        return error_response(503, "CONFIGURATION_REQUIRED")

    run = service.get_sync_run(syncRunId)
    if run is None:
        return error_response(404, "NOT_FOUND")

    return SyncRunView(
        id=run.id,
        operationId=run.operation_id,
        status=run.status,
        reason=run.reason,
        sourceRevision=run.source_revision,
        sourcesScanned=run.sources_scanned,
        sourcesInvalid=run.sources_invalid,
        startedAt=run.started_at,
        finishedAt=run.finished_at,
    )

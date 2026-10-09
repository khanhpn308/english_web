"""Protected save/edit adapters; source paths and AI ports are never client inputs."""

from typing import Annotated, Any, Literal, Self

from backend.app.application.edit_word_form import (
    EditConflict,
    EditWordFormIntent,
    EditWordFormService,
)
from backend.app.application.operations import OperationConflict
from backend.app.application.save_word_family import SaveConflict, SaveWordFamilyService
from backend.app.http.errors import error_response
from backend.app.http.lookups import IdempotencyKey, _session_fingerprint
from backend.app.http.search import WordFormDetail
from backend.app.http.session import COOKIE_NAME
from fastapi import APIRouter, Header, Path, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import JSONResponse

router = APIRouter(prefix="/api/v1/word-forms", tags=["word-forms"])
OpaqueId = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")]


def _save_request_schema(schema: dict[str, Any]) -> None:
    properties = schema["properties"]
    source_fields = ("sourceId", "sourceRevision")
    for name in source_fields:
        field = properties[name]
        field.update(
            next(branch for branch in field.pop("anyOf") if branch.get("type") != "null")
        )
        field.pop("default", None)
    # Optional impossible properties express absence and generate optional never
    # with the pinned generator, which cannot handle boolean property schemas.
    schema["oneOf"] = [
        {
            "type": "object",
            "properties": {
                name: {"allOf": [{"type": "string"}, {"type": "null"}]}
                for name in source_fields
            },
        },
        {
            "type": "object",
            "properties": {name: properties[name] for name in source_fields},
            "required": list(source_fields),
        },
    ]


class SaveWordFormsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, json_schema_extra=_save_request_schema)
    lookupId: OpaqueId
    noteDate: str = Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
    sourceId: OpaqueId | None = None
    sourceRevision: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def source_pair(self) -> Self:
        present = self.model_fields_set & {"sourceId", "sourceRevision"}
        if present and (present != {"sourceId", "sourceRevision"} or
                        self.sourceId is None or self.sourceRevision is None):
            raise ValueError("Source fields must be a non-null pair")
        return self


class SavedForm(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    revision: int = Field(ge=1)


class SaveResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operationId: str
    sourceId: str
    sourceRevision: int = Field(ge=1)
    sourceEtag: str
    noteDate: str
    savedForms: list[SavedForm]
    canonicalForms: list[WordFormDetail]
    createdCardIds: list[str]
    reusedCardIds: list[str]
    markdownSync: Literal["COMPLETED"]


class SourceConflictDetails(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    kind: Literal["CONFLICT"]
    expectedRevision: int = Field(ge=1)
    currentRevision: int = Field(ge=1)
    resourceType: Literal["SOURCE"]
    resourceId: str


class SourceRetryDetails(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    kind: Literal["RETRY"]
    operationId: str
    operationKind: Literal["SAVE", "EDIT"]


class SourceFieldError(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    field: str
    reason: str


class SourceFieldDetails(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    kind: Literal["FIELD_ERRORS"]
    fields: list[SourceFieldError]


class SaveErrorBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: Literal[
        "SESSION_REQUIRED", "SESSION_INVALID", "ORIGIN_FORBIDDEN", "VALIDATION_ERROR",
        "NOT_FOUND", "PAYLOAD_TOO_LARGE", "CONFIGURATION_REQUIRED", "REVISION_CONFLICT",
        "SOURCE_MISSING", "SOURCE_NOT_WRITABLE", "CROSS_RESOURCE_MISMATCH",
        "IDEMPOTENCY_KEY_REUSED", "IDEMPOTENCY_IN_FLIGHT", "STORAGE_BUSY", "MALFORMED_JSON",
    ]
    message: str
    requestId: str
    details: Annotated[
        SourceConflictDetails | SourceRetryDetails | SourceFieldDetails,
        Field(discriminator="kind"),
    ] | None = None


class SaveErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    error: SaveErrorBody


_SAVE_MESSAGES = {
    "REVISION_CONFLICT": "Source revision changed",
    "SOURCE_MISSING": "Source is missing",
    "SOURCE_NOT_WRITABLE": "Source requires repair or is not writable",
    "CROSS_RESOURCE_MISMATCH": "Source does not belong to the selected date",
}


def _failure(error: OperationConflict, operation_kind: str = "SAVE") -> JSONResponse:
    details = error.details if isinstance(error, (SaveConflict, EditConflict)) else None
    if details is None and error.operation_id is not None:
        details = {
            "kind": "RETRY", "operationId": error.operation_id, "operationKind": operation_kind,
        }
    if error.code == "SOURCE_EVIDENCE_MISMATCH":
        return error_response(409, "IDEMPOTENCY_IN_FLIGHT", details)
    if error.code in _SAVE_MESSAGES:
        # Established source routes also author their additional typed envelopes
        # locally. T024 does not mutate the shared error taxonomy.
        from secrets import token_urlsafe

        message = _SAVE_MESSAGES[error.code]
        if operation_kind == "EDIT" and error.code == "CROSS_RESOURCE_MISMATCH":
            message = "Source does not contain the selected word form"
        body: dict[str, Any] = {
            "code": error.code, "message": message,
            "requestId": f"req_{token_urlsafe(12)}",
        }
        if details is not None:
            body["details"] = details
        return JSONResponse({"error": body}, status_code=error.status_code)
    return error_response(error.status_code, error.code, details)


@router.post(
    "", response_model=SaveResult, status_code=201,
    responses={
        201: {"headers": {"ETag": {"schema": {"type": "string"}}}},
        **{status: {"model": SaveErrorResponse} for status in [
            400, 401, 403, 404, 409, 413, 422, 503,
        ]},
    },
)
def post_word_forms(
    request: Request, body: SaveWordFormsRequest, idempotency_key: IdempotencyKey,
    if_match: Annotated[str | None, Header(
        alias="If-Match", max_length=128, json_schema_extra={"minLength": 1},
        description=(
            "Required source ETag when sourceId and sourceRevision are supplied. "
            "Omit for a new-date save and send If-None-Match: * instead. "
            "The backend enforces these body/header alternatives together."
        ),
    )] = None,
    if_none_match: Annotated[str | None, Header(
        alias="If-None-Match", max_length=1, json_schema_extra={"const": "*"},
        description=(
            "Required as * for a new-date save with sourceId and sourceRevision omitted. "
            "Omit when those source fields are supplied and send If-Match instead. "
            "The backend enforces these body/header alternatives together."
        ),
    )] = None,
) -> JSONResponse:
    if request.query_params or any(len(request.headers.getlist(name)) > 1 for name in (
        "idempotency-key", "if-match", "if-none-match",
    )):
        return error_response(422, "VALIDATION_ERROR")
    service = getattr(request.app.state, "save_word_family_service", None)
    if not isinstance(service, SaveWordFamilyService):
        return error_response(503, "CONFIGURATION_REQUIRED")
    if not request.app.state.ready:
        return error_response(503, "STORAGE_BUSY")
    cookie = request.cookies.get(COOKIE_NAME)
    if cookie is None:
        return error_response(401, "SESSION_REQUIRED")
    try:
        result = service.save(
            lookup_id=body.lookupId, note_date=body.noteDate,
            owner_session_id=_session_fingerprint(cookie), idempotency_key=idempotency_key,
            source_id=body.sourceId, source_revision=body.sourceRevision,
            if_match=if_match, if_none_match=if_none_match,
        )
        validated = SaveResult.model_validate(result)
        return JSONResponse(validated.model_dump(mode="json"), status_code=201, headers={
            "ETag": validated.sourceEtag, "Cache-Control": "no-store",
        })
    except OperationConflict as error:
        return _failure(error)
    except (SQLAlchemyError, ValidationError):
        return error_response(503, "STORAGE_BUSY")


class PatchWordFormRequest(EditWordFormIntent):
    """Canonical editable fields and selected-source preconditions."""


class WordFormMutationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    wordForm: WordFormDetail
    operationId: str
    sourceRevision: int = Field(ge=1)


@router.patch(
    "/{wordFormId}", response_model=WordFormMutationResult,
    responses={
        200: {"headers": {"ETag": {"schema": {"type": "string"}}}},
        **{status: {"model": SaveErrorResponse} for status in [
            400, 401, 403, 404, 409, 413, 422, 503,
        ]},
    },
)
def patch_word_form(
    request: Request,
    wordFormId: Annotated[str, Path(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")],
    body: PatchWordFormRequest,
    idempotency_key: IdempotencyKey,
    if_match: Annotated[str, Header(alias="If-Match", min_length=1, max_length=128)],
) -> JSONResponse:
    if request.query_params or "if-none-match" in request.headers or any(
        len(request.headers.getlist(name)) > 1 for name in ("idempotency-key", "if-match")
    ):
        return error_response(422, "VALIDATION_ERROR")
    service = getattr(request.app.state, "edit_word_form_service", None)
    if not isinstance(service, EditWordFormService):
        return error_response(503, "CONFIGURATION_REQUIRED")
    if not request.app.state.ready:
        return error_response(503, "STORAGE_BUSY")
    if request.cookies.get(COOKIE_NAME) is None:
        return error_response(401, "SESSION_REQUIRED")
    try:
        result, etag = service.edit(
            word_form_id=wordFormId, intent=body, idempotency_key=idempotency_key,
            if_match=if_match,
        )
        validated = WordFormMutationResult.model_validate(result)
        return JSONResponse(validated.model_dump(mode="json"), headers={
            "ETag": etag, "Cache-Control": "no-store",
        })
    except OperationConflict as error:
        return _failure(error, "EDIT")
    except (SQLAlchemyError, ValidationError):
        return error_response(503, "STORAGE_BUSY")

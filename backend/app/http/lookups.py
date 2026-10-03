"""HTTP adapter for validated lookup previews (T008)."""

import hashlib
from datetime import UTC, datetime
from typing import Annotated, Literal

from backend.app.application.operations import OperationConflict
from backend.app.enrichment.lookup import LookupService, normalize_term
from backend.app.http.errors import error_response
from backend.app.http.session import COOKIE_NAME
from backend.app.vocabulary.models import LookupPreview
from backend.app.vocabulary.repository import (
    PreviewExpiredError,
    PreviewNotFoundError,
    PreviewOwnerMismatchError,
)
from fastapi import APIRouter, Body, Header, Request
from pydantic import AwareDatetime, BaseModel, ConfigDict, field_validator
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import JSONResponse

router = APIRouter(prefix="/api/v1/lookups", tags=["lookups"])

IdempotencyKey = Annotated[
    str, Header(alias="Idempotency-Key", min_length=1, max_length=128, pattern=r"^[\x20-\x7e]+$")
]


class LookupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    term: str

    @field_validator("term", mode="before")
    @classmethod
    def normalize_and_bound_term(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("term must be a string")
        return normalize_term(value)


class LookupMeaning(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str
    language: Literal["en", "vi"]
    verificationStatus: Literal["VERIFIED", "UNVERIFIED", "MISSING"]


class LookupExample(BaseModel):
    model_config = ConfigDict(extra="forbid")
    english: str
    vietnamese: str
    verificationStatus: Literal["VERIFIED", "UNVERIFIED", "MISSING"]


class LookupForm(BaseModel):
    model_config = ConfigDict(extra="forbid")
    formId: str
    lemma: str
    partOfSpeech: str
    meaningsEn: list[LookupMeaning]
    meaningsVi: list[LookupMeaning]
    examples: list[LookupExample]
    ipaUs: str | None
    cambridgeUrl: str | None
    ipaStatus: Literal["VERIFIED", "UNVERIFIED", "MISSING"]
    cambridgeStatus: Literal["VERIFIED", "UNVERIFIED", "MISSING"]
    verificationSummary: Literal["VERIFIED", "UNVERIFIED", "MISSING"]


class LookupResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lookupId: str
    operationId: str
    term: str
    forms: list[LookupForm]
    provider: str
    model: str
    promptVersion: str
    verificationSummary: Literal["VERIFIED", "UNVERIFIED", "MISSING"]
    status: Literal["PREVIEW", "FAILED"]
    createdAt: AwareDatetime


def _result(preview: LookupPreview) -> LookupResult:
    if preview.operation_id is None:
        raise ValueError("Lookup preview missing operation reference")
    forms = [LookupForm.model_validate(form.to_dict()) for form in preview.forms]
    return LookupResult(
        lookupId=preview.lookup_id,
        operationId=preview.operation_id,
        term=preview.term,
        forms=forms,
        provider=preview.provider,
        model=preview.model,
        promptVersion=preview.prompt_version,
        verificationSummary=preview.verification_summary,
        status="PREVIEW",
        createdAt=datetime.fromtimestamp(preview.created_at, tz=UTC),
    )


def _service_for(request: Request) -> LookupService | None:
    service = getattr(request.app.state, "lookup_service", None)
    return service if isinstance(service, LookupService) else None


def _operation_error(
    error: OperationConflict, service: LookupService | None = None
) -> JSONResponse:
    if error.code == "AI_CONSENT_REQUIRED":
        details = None
        if service is not None:
            try:
                snapshot = service.admission.consent.get_snapshot(service.admission.policy_source)
                details = {
                    "kind": "AI_CONSENT",
                    "consentState": snapshot.state.state,
                    "currentPolicyVersion": snapshot.policy.version if snapshot.policy else None,
                }
            except Exception:
                details = {
                    "kind": "AI_CONSENT",
                    "consentState": "NOT_GRANTED",
                    "currentPolicyVersion": None,
                }
        return error_response(403, "AI_CONSENT_REQUIRED", details)

    details = None
    if error.operation_id is not None and error.code in {
        "IDEMPOTENCY_IN_FLIGHT",
        "IDEMPOTENCY_KEY_REUSED",
        "BRIDGE_UNAVAILABLE",
        "TIMEOUT",
        "STORAGE_BUSY",
    }:
        details = {"kind": "RETRY", "operationId": error.operation_id}
    return error_response(error.status_code, error.code, details)


def _session_fingerprint(cookie: str) -> str:
    return hashlib.sha256(f"owner:{cookie}".encode()).hexdigest()


@router.post("", response_model=LookupResult, responses={422: {"description": "Validation Error"}})
async def post_lookup(
    request: Request,
    body: Annotated[LookupRequest, Body(embed=False)],
    idempotency_key: IdempotencyKey,
) -> LookupResult | JSONResponse:
    if request.query_params:
        return error_response(422, "VALIDATION_ERROR")
    service = _service_for(request)
    if service is None:
        return error_response(503, "CONFIGURATION_REQUIRED")
    owner_session_id = request.cookies.get(COOKIE_NAME)
    if owner_session_id is None:
        return error_response(401, "SESSION_REQUIRED")
    start_time = getattr(request.state, "request_start_time", None)
    try:
        preview = await service.lookup(
            term=body.term,
            idempotency_key=idempotency_key,
            owner_session_id=_session_fingerprint(owner_session_id),
            request_start_time=start_time,
        )
        return _result(preview)
    except OperationConflict as error:
        return _operation_error(error, service)
    except PreviewOwnerMismatchError:
        return error_response(403, "ORIGIN_FORBIDDEN")
    except (PreviewExpiredError, PreviewNotFoundError, SQLAlchemyError):
        return error_response(503, "STORAGE_BUSY")
    except ValueError:
        return error_response(500, "INTERNAL_ERROR")

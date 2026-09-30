"""Strict local HTTP boundary for the authoritative consent singleton."""

from secrets import token_urlsafe
from typing import Annotated, Literal

from backend.app.application.consent import (
    AiDisclosurePolicy,
    ConsentRejected,
    ConsentService,
    ConsentState,
    PolicyVersion,
    choice_time,
)
from backend.app.http.errors import error_response
from backend.app.persistence.database import StorageError
from fastapi import APIRouter, Body, Depends, Header, HTTPException, Request, Response
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import JSONResponse

router = APIRouter(prefix="/api/v1/ai-consent", tags=["consent"])
IdempotencyKey = Annotated[
    str, Header(alias="Idempotency-Key", min_length=1, max_length=128, pattern=r"^[\x20-\x7e]+$")
]
IfMatch = Annotated[
    str,
    Header(
        alias="If-Match", min_length=2, max_length=4096, pattern=r'^"[\x21\x23-\x7e\x80-\xff]*"$'
    ),
]


class AiConsentView(BaseModel):
    model_config = ConfigDict(extra="forbid")
    state: ConsentState
    revision: int = Field(ge=0)
    acceptedPolicyVersion: str | None
    acceptedPolicyDigest: str | None
    lastChoiceAt: AwareDatetime | None
    policy: AiDisclosurePolicy | None
    canRequestAi: bool


class GrantAiConsent(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    policyVersion: PolicyVersion


class AiConsentMutationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operationId: str
    appliedRevision: int = Field(ge=1)


class ConsentRetryDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["RETRY"]
    operationId: str


class ConsentError(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str
    message: str
    requestId: str
    details: ConsentRetryDetails | None = None


class ConsentErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    error: ConsentError


def rejection(result: ConsentRejected) -> JSONResponse:
    status, code = result.error
    payload: dict[str, object] = {
        "code": code,
        "message": "Consent request could not be applied",
        "requestId": f"req_{token_urlsafe(12)}",
    }
    if result.operation_id is not None:
        payload["details"] = {"kind": "RETRY", "operationId": result.operation_id}
    return JSONResponse(
        {"error": payload}, status_code=status, headers={"Cache-Control": "no-store"}
    )


def service_for(request: Request) -> ConsentService | None:
    service = getattr(request.app.state, "consent_service", None)
    return service if isinstance(service, ConsentService) else None


def unavailable_service(request: Request) -> JSONResponse:
    if getattr(request.app.state, "storage_error", None) is not None:
        return rejection(ConsentRejected((503, "STORAGE_BUSY")))
    return error_response(503, "CONFIGURATION_REQUIRED")


async def reject_read_body(request: Request) -> None:
    if await request.body():
        raise HTTPException(422)


@router.get(
    "",
    response_model=AiConsentView,
    responses={422: {"model": ConsentErrorResponse}, 503: {"model": ConsentErrorResponse}},
)
def get_consent(
    request: Request, response: Response, _body: Annotated[None, Depends(reject_read_body)]
) -> AiConsentView | JSONResponse:
    if request.query_params:
        return error_response(422, "VALIDATION_ERROR")
    service = service_for(request)
    if service is None:
        return unavailable_service(request)
    try:
        snapshot = service.get_snapshot(lambda: request.app.state.active_ai_policy)
    except (SQLAlchemyError, ValidationError, StorageError):
        return rejection(ConsentRejected((503, "STORAGE_BUSY")))
    response.headers["Cache-Control"] = "no-store"
    response.headers["ETag"] = snapshot.etag
    state = snapshot.state
    return AiConsentView(
        state=state.state,
        revision=state.revision,
        acceptedPolicyVersion=state.accepted_policy_version,
        acceptedPolicyDigest=state.accepted_policy_digest,
        lastChoiceAt=choice_time(state.last_choice_at),
        policy=snapshot.policy,
        canRequestAi=snapshot.can_request_ai,
    )


@router.put(
    "",
    response_model=AiConsentMutationResult,
    responses={409: {"model": ConsentErrorResponse}, 503: {"model": ConsentErrorResponse}},
)
def grant_consent(
    request: Request,
    response: Response,
    body: Annotated[GrantAiConsent, Body(embed=False)],
    if_match: IfMatch,
    idempotency_key: IdempotencyKey,
) -> AiConsentMutationResult | JSONResponse:
    if request.query_params:
        return error_response(422, "VALIDATION_ERROR")
    service = service_for(request)
    if service is None:
        return unavailable_service(request)
    try:
        with service.operations.engine.connect() as connection:
            result = service.grant_consent(
                connection,
                idempotency_key,
                if_match,
                body.policyVersion,
                lambda: request.app.state.active_ai_policy,
            )
    except (SQLAlchemyError, StorageError):
        service.storage_reliable = False
        return rejection(ConsentRejected((503, "STORAGE_BUSY")))
    if isinstance(result, ConsentRejected):
        return rejection(result)
    response.headers["Cache-Control"] = "no-store"
    return AiConsentMutationResult(
        operationId=result.operation_id, appliedRevision=result.applied_revision
    )


@router.delete(
    "",
    response_model=AiConsentMutationResult,
    responses={409: {"model": ConsentErrorResponse}, 503: {"model": ConsentErrorResponse}},
)
async def revoke_consent(
    request: Request, response: Response, idempotency_key: IdempotencyKey
) -> AiConsentMutationResult | JSONResponse:
    if request.query_params or "if-match" in request.headers or await request.body():
        return error_response(422, "VALIDATION_ERROR")
    service = service_for(request)
    if service is None:
        return unavailable_service(request)
    # The body boundary is async; synchronous SQLite work belongs to the worker pool.
    from starlette.concurrency import run_in_threadpool

    def revoke() -> AiConsentMutationResult | JSONResponse:
        try:
            with service.operations.engine.connect() as connection:
                result = service.revoke_consent(connection, idempotency_key)
        except (SQLAlchemyError, StorageError):
            service.storage_reliable = False
            return rejection(ConsentRejected((503, "STORAGE_BUSY")))
        if isinstance(result, ConsentRejected):
            return rejection(result)
        response.headers["Cache-Control"] = "no-store"
        return AiConsentMutationResult(
            operationId=result.operation_id, appliedRevision=result.applied_revision
        )

    return await run_in_threadpool(revoke)

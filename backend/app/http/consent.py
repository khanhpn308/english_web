from typing import Literal, TypedDict
from pydantic import BaseModel, ConfigDict
from fastapi import APIRouter, Request, Response, Header, Body
from backend.app.http.errors import error_response
from backend.app.application.consent import ConsentService
from backend.app.application.operations import OperationLedger

router = APIRouter(prefix="/api/v1/ai-consent", tags=["consent"])


class AiConsentView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: Literal["NOT_GRANTED", "GRANTED", "REVOKED", "STALE"]
    revision: int
    acceptedPolicyVersion: str | None
    acceptedPolicyDigest: str | None
    lastChoiceAt: float | None
    policy: str | None  # We return None for policy if no authoritative source exists
    canRequestAi: bool


@router.get("", response_model=AiConsentView)
async def get_consent(request: Request, response: Response) -> AiConsentView:
    # Use database and Service
    db = request.app.state.database
    ledger = OperationLedger(db.engine)
    service = ConsentService(ledger)

    with db.engine.connect() as conn:
        state = service.get_state(conn)

    digest = state["accepted_policy_digest"] or "none"
    etag = f'"ac-r{state["revision"]}-{digest}"'
    response.headers["Cache-Control"] = "no-store"
    response.headers["ETag"] = etag
    active = getattr(request.app.state, "active_ai_policy", None)

    current_state = state["state"]
    can_request_ai = False

    if current_state == "GRANTED":
        if not active or state["accepted_policy_version"] != active["version"]:
            current_state = "STALE"
        else:
            can_request_ai = True

    return AiConsentView(
        state=current_state,
        revision=state["revision"],
        acceptedPolicyVersion=state["accepted_policy_version"],
        acceptedPolicyDigest=state["accepted_policy_digest"],
        lastChoiceAt=state["last_choice_at"],
        policy=active["content"] if active else None,
        canRequestAi=can_request_ai,
    )


class GrantAiConsent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    policyVersion: str


class AiConsentMutationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operationId: str
    appliedRevision: int


@router.put("", response_model=AiConsentMutationResult)
async def grant_consent(
    request: Request,
    response: Response,
    body: GrantAiConsent = Body(..., embed=False),
    if_match: str = Header(..., alias="If-Match"),
    idempotency_key: str = Header(..., alias="Idempotency-Key", max_length=128),
) -> AiConsentMutationResult:
    db = request.app.state.database
    ledger = OperationLedger(db.engine)
    service = ConsentService(ledger)

    active = getattr(request.app.state, "active_ai_policy", None)

    with db.engine.connect() as conn:
        res = service.grant_consent(
            connection=conn,
            key=idempotency_key,
            if_match=if_match,
            policy_version=body.policyVersion,
            active_policy=active,
        )

    if "error" in res:
        status, code = res["error"]
        from starlette.responses import JSONResponse
        from secrets import token_urlsafe

        # Local error mapping
        return JSONResponse(
            {"error": {"code": code, "message": code, "requestId": f"req_{token_urlsafe(12)}"}},
            status_code=status,
        )

    return AiConsentMutationResult(
        operationId=res["operation_id"],
        appliedRevision=res["applied_revision"],
    )


@router.delete("", response_model=AiConsentMutationResult)
async def revoke_consent(
    request: Request,
    response: Response,
    idempotency_key: str = Header(..., alias="Idempotency-Key", max_length=128),
) -> AiConsentMutationResult:
    db = request.app.state.database
    ledger = OperationLedger(db.engine)
    service = ConsentService(ledger)

    with db.engine.connect() as conn:
        res = service.revoke_consent(
            connection=conn,
            key=idempotency_key,
        )

    if "error" in res:
        status, code = res["error"]
        from starlette.responses import JSONResponse
        from secrets import token_urlsafe

        return JSONResponse(
            {"error": {"code": code, "message": code, "requestId": f"req_{token_urlsafe(12)}"}},
            status_code=status,
        )

    return AiConsentMutationResult(
        operationId=res["operation_id"],
        appliedRevision=res["applied_revision"],
    )

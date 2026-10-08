"""Deterministic synthetic proxy boundary for T052 browser harness."""

import json
from typing import Literal

from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

MODEL = "gemini-3.8-flash-high"
LookupScenario = Literal["preview", "missing-optional", "invalid-response", "unavailable"]


class LookupMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    role: Literal["user"]
    content: str = Field(min_length=1, max_length=4096)


class LookupChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    model: Literal["gemini-3.8-flash-high"]
    messages: list[LookupMessage] = Field(min_length=1, max_length=1)


def lookup_content(scenario: LookupScenario) -> str:
    """Provider content uses T008's forms schema, never the frontend result DTO."""
    optional_missing = scenario == "missing-optional"
    form = {
        "lemma": "robust",
        "partOfSpeech": "ADJECTIVE",
        "meaningsEn": [{"text": "able to work effectively", "verificationStatus": "VERIFIED"}],
        "meaningsVi": [{"text": "vững chắc", "verificationStatus": "VERIFIED"}],
        "examples": [
            {
                "english": "The design is robust.",
                "vietnamese": "Thiết kế rất vững chắc.",
                "verificationStatus": "VERIFIED",
            }
        ],
        "ipaUs": None if optional_missing else "/rəˈbʌst/",
        "cambridgeUrl": None
        if optional_missing
        else "https://dictionary.cambridge.org/dictionary/english/robust",
    }
    adverb = {
        "lemma": "robustly",
        "partOfSpeech": "ADVERB",
        "meaningsEn": [{"text": "in a strong and effective way"}],
        "meaningsVi": [{"text": "một cách vững chắc"}],
        "examples": [
            {
                "english": "The system works robustly.",
                "vietnamese": "Hệ thống hoạt động vững chắc.",
            }
        ],
        "ipaUs": None,
        "cambridgeUrl": None,
    }
    # Production validation must downgrade claimed verification and label missing
    # optional fields. The controlled invalid case omits required meanings/examples.
    forms = [{"lemma": "robust"}] if scenario == "invalid-response" else [form, adverb]
    return json.dumps({"forms": forms}, ensure_ascii=False)


def completion(content: str) -> dict:
    return {
        "id": "chatcmpl-fake",
        "object": "chat.completion",
        "choices": [
            {
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
    }


def create_fake_bridge(*, lookup: bool = False, scenario: LookupScenario = "preview") -> FastAPI:
    """Give each real-API browser case its own synthetic transport/history."""
    bridge = FastAPI(title="Fake Bridge")
    bridge.state.request_log = []
    bridge.state.lookup_dispatches = 0

    @bridge.middleware("http")
    async def record_requests(request: Request, call_next):
        metadata = {
            "method": request.method,
            "url": request.url.path,
            "auth": request.headers.get("authorization") == "Bearer dummy-key",
        }
        bridge.state.request_log.append(metadata)
        request.state.bridge_metadata = metadata
        return await call_next(request)

    def authorize(authorization: str | None) -> None:
        if not authorization:
            raise HTTPException(status_code=401, detail="Unauthorized")
        if authorization != "Bearer dummy-key":
            raise HTTPException(status_code=403, detail="Forbidden")

    @bridge.get("/v1/models")
    async def get_models(authorization: str | None = Header(None)):
        authorize(authorization)
        # Admission needs owned_by evidence as well as the approved model ID.
        return {"data": [{"id": MODEL, "object": "model", "owned_by": "google"}]}

    if lookup:

        @bridge.post("/v1/chat/completions")
        async def lookup_completion(
            body: LookupChatRequest,
            request: Request,
            authorization: str | None = Header(None),
        ):
            authorize(authorization)
            # Only this synthetic fixture is supported. Reject unexpected prompts
            # rather than recording raw terms, prompts or producing fake success.
            prompt = body.messages[0].content
            if not prompt.startswith("lookup-v1\n") or not prompt.endswith(
                'The lookup term is "robust".\n'
            ):
                raise HTTPException(status_code=422, detail="Unknown synthetic lookup fixture")
            request.state.bridge_metadata.update(
                model=body.model, promptVersion="lookup-v1", fixture="robust", scenario=scenario
            )
            bridge.state.lookup_dispatches += 1
            if scenario == "unavailable":
                raise HTTPException(status_code=503, detail="Synthetic bridge unavailable")
            return completion(lookup_content(scenario))

    else:

        @bridge.post("/v1/chat/completions")
        async def chat_completions(authorization: str | None = Header(None)):
            authorize(authorization)
            return completion("Fake synthetic content")

    return bridge


# Keep T052's existing module-level app and request-history helpers available.
app = create_fake_bridge()
request_log: list[dict] = app.state.request_log


def get_request_count() -> int:
    return len(request_log)


def clear_requests() -> None:
    request_log.clear()

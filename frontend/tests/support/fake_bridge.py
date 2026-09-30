"""Deterministic synthetic proxy boundary for T052 browser harness."""

from fastapi import FastAPI, Header, HTTPException, Request

app = FastAPI(title="Fake Bridge")

# Store request history for test assertions
request_log: list[dict] = []


@app.middleware("http")
async def record_requests(request: Request, call_next):
    # Only keep sanitized info
    request_log.append(
        {
            "method": request.method,
            "url": str(request.url.path),
            "auth": request.headers.get("authorization") == "Bearer dummy-key",
        }
    )
    return await call_next(request)


@app.get("/v1/models")
async def get_models(authorization: str | None = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if authorization != "Bearer dummy-key":
        raise HTTPException(status_code=403, detail="Forbidden")
    return {"data": [{"id": "gemini-3.8-flash-high", "object": "model"}]}


@app.post("/v1/chat/completions")
async def chat_completions(authorization: str | None = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if authorization != "Bearer dummy-key":
        raise HTTPException(status_code=403, detail="Forbidden")
    return {
        "id": "chatcmpl-fake",
        "object": "chat.completion",
        "choices": [
            {
                "message": {"role": "assistant", "content": "Fake synthetic content"},
                "finish_reason": "stop",
            }
        ],
    }


def get_request_count() -> int:
    return len(request_log)


def clear_requests() -> None:
    request_log.clear()

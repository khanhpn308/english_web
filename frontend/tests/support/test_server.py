"""Harness server that runs the backend on loopback for e2e tests."""

import argparse
import asyncio
import sys
import time
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path
from secrets import token_urlsafe
from tempfile import TemporaryDirectory

import httpx
import uvicorn
from backend.app.adapters.bridge import BridgeAdapter
from backend.app.main import create_app
from backend.app.platform.config import AppSettings
from fastapi import FastAPI
from frontend.tests.support.fake_bridge import (
    LookupScenario,
    clear_requests,
    create_fake_bridge,
    get_request_count,
)
from pydantic import BaseModel, ConfigDict, ValidationError
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse

HOST = "127.0.0.1"
PORT = 8000
LOOKUP_COOKIE = "harness_lookup_session"


class LookupSetup(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    scenario: LookupScenario = "preview"


def lookup_policy() -> dict:
    """Synthetic T008 policy definition. ConsentService computes its real digest."""
    scopes = ["LOOKUP", "QUIZ_GENERATION", "WRITING_FEEDBACK"]
    return {
        "version": "synthetic-lookup-policy-v1",
        "reviewStatus": "READY",
        "disclosureText": "Synthetic lookup disclosure. In-process fixtures only.",
        "dataCategories": ["TERM", "WORD_FORMS", "WRITING_ANSWER"],
        "recipients": ["Antigravity/Google"],
        "retentionStatement": "Synthetic fixtures; no external provider retains data.",
        "regionStatement": "Synthetic fixtures remain in this harness process.",
        "costQuotaStatement": "No paid inference and no automatic fallback.",
        "withdrawalStatement": "Withdrawal blocks new admissions; cannot recall admitted data.",
        "scopes": scopes,
        "dispatchRules": [
            {
                "scope": scope,
                "providerLabel": "Antigravity/Google",
                "modelId": "gemini-3.8-flash-high",
                "route": "primary",
                "billingMode": "configured-account",
            }
            for scope in scopes
        ],
        "blockedReasons": [],
    }


def lookup_state(app: FastAPI) -> dict:
    """Read aggregate synthetic storage evidence, never learning content/secrets."""
    with app.state.database.engine.connect() as connection:
        counts = {
            "wordForms": connection.exec_driver_sql("SELECT count(*) FROM word_forms").scalar_one(),
            "sources": connection.exec_driver_sql("SELECT count(*) FROM source_files").scalar_one(),
            "cards": connection.exec_driver_sql("SELECT count(*) FROM review_cards").scalar_one(),
            "previews": connection.exec_driver_sql("SELECT count(*) FROM lookup_previews").scalar_one(),
            "admissions": connection.exec_driver_sql(
                "SELECT count(*) FROM ai_operation_admission"
            ).scalar_one(),
        }
    bridge = app.state.test_bridge
    return {
        **counts,
        "bridge": {
            "count": len(bridge.state.request_log),
            "lookupDispatches": bridge.state.lookup_dispatches,
            "requests": list(bridge.state.request_log),
            "transport": "in-process-asgi",
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()

    temporary = TemporaryDirectory(prefix="vocabulary-e2e-")
    temp_dir = Path(temporary.name)
    db_path = temp_dir / "test.db"

    # Strict exact-origin loopback config
    settings = AppSettings(
        host=HOST,
        port=args.port,
        storage_path=db_path,
    )

    app = create_app(settings)

    # The existing T052 app stays unconfigured/ungranted. Opt-in lookup cases
    # receive separate real apps to avoid consent/log races across parallel tests.
    isolated_apps: dict[str, FastAPI] = {}
    isolated_lifespans = AsyncExitStack()
    startup_lock = asyncio.Lock()
    production_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def harness_lifespan(active_app):
        async with production_lifespan(active_app), isolated_lifespans:
            yield

    app.router.lifespan_context = harness_lifespan

    async def harness_app(scope, receive, send):
        if scope["type"] != "http":
            await app(scope, receive, send)
            return

        request = Request(scope, receive)
        instance_id = request.cookies.get(LOOKUP_COOKIE)
        selected_app = isolated_apps.get(instance_id, app) if instance_id else app
        if scope["path"].startswith("/_harness/"):
            path = scope["path"]
            method = scope["method"]

            async def send_json(status_code: int, data: dict | None = None):
                response = JSONResponse(data, status_code, headers={"Cache-Control": "no-store"})
                await response(scope, receive, send)

            if method == "POST" and path == "/_harness/lookup-session":
                origin = f"http://{HOST}:{args.port}"
                if request.headers.get("origin") != origin or request.headers.get("host") != (
                    f"{HOST}:{args.port}"
                ):
                    await send_json(403, {"error": "ORIGIN_FORBIDDEN"})
                    return
                if not app.state.ready:
                    await send_json(503, {"error": "NOT_READY"})
                    return
                body = bytearray()
                async for chunk in request.stream():
                    body.extend(chunk)
                    if len(body) > 1024:
                        await send_json(413, {"error": "PAYLOAD_TOO_LARGE"})
                        return
                try:
                    setup = LookupSetup.model_validate_json(bytes(body))
                except ValidationError:
                    await send_json(422, {"error": "INVALID_LOOKUP_FIXTURE"})
                    return
                instance_id = token_urlsafe(18)
                test_app = create_app(
                    AppSettings(host=HOST, port=args.port, storage_path=temp_dir / f"{instance_id}.db")
                )
                # Alembic's command context is process-global. Serialize startup
                # across parallel cases, while leaving product requests concurrent.
                async with startup_lock:
                    await isolated_lifespans.enter_async_context(
                        test_app.router.lifespan_context(test_app)
                    )
                if not test_app.state.ready:
                    await send_json(503, {"error": "NOT_READY"})
                    return
                test_app.state.active_ai_policy = lookup_policy()
                bridge = create_fake_bridge(lookup=True, scenario=setup.scenario)
                test_app.state.test_bridge = bridge
                # Keep the real LookupService, ledger, repository, admission fence
                # and consent service. Replace only the external bridge transport.
                test_app.state.lookup_service.admission.bridge = BridgeAdapter(
                    api_key="dummy-key", transport=httpx.ASGITransport(app=bridge)
                )
                isolated_apps[instance_id] = test_app
                response = JSONResponse(
                    {"token": test_app.state.sessions.issue_bootstrap_token()},
                    headers={"Cache-Control": "no-store"},
                )
                response.set_cookie(LOOKUP_COOKIE, instance_id, httponly=True, samesite="strict")
                await response(scope, receive, send)
                return
            elif method == "GET" and path == "/_harness/lookup-state":
                if selected_app is app:
                    await send_json(404, {"error": "LOOKUP_FIXTURE_REQUIRED"})
                    return
                await send_json(200, await run_in_threadpool(lookup_state, selected_app))
                return
            elif method == "POST" and path == "/_harness/token":
                if not selected_app.state.ready:
                    await send_json(
                        503,
                        {"error": "NOT_READY", "storage_error": str(selected_app.state.storage_error)},
                    )
                    return
                token = selected_app.state.sessions.issue_bootstrap_token()
                await send_json(200, {"token": token})
                return
            elif method == "GET" and path == "/_harness/db_path":
                await send_json(200, {"path": str(selected_app.state.settings.storage_path)})
                return
            elif method == "GET" and path == "/_harness/bridge-requests":
                count = (
                    get_request_count()
                    if selected_app is app
                    else len(selected_app.state.test_bridge.state.request_log)
                )
                await send_json(200, {"count": count})
                return
            elif method == "DELETE" and path == "/_harness/bridge-requests":
                if selected_app is app:
                    clear_requests()
                else:
                    selected_app.state.test_bridge.state.request_log.clear()
                    selected_app.state.test_bridge.state.lookup_dispatches = 0
                await send({"type": "http.response.start", "status": 204, "headers": []})
                await send({"type": "http.response.body", "body": b""})
                return
            elif method == "GET" and path == "/_harness/bridge-preflight":

                def unavailable(request: httpx.Request) -> httpx.Response:
                    raise httpx.ConnectError("Synthetic provider unavailable", request=request)

                # Preserve T052's unavailable-provider probe with no socket/DNS
                # dependency, even if a real proxy happens to be running locally.
                adapter = BridgeAdapter(
                    api_key="dummy-key", transport=httpx.MockTransport(unavailable)
                )
                try:
                    await adapter.preflight(time.monotonic() + 5.0)
                    await send_json(200, {"status": "OK"})
                except Exception as e:
                    await send_json(503, {"error": str(e), "type": type(e).__name__})
                return

            await send_json(404, {"error": "NOT_FOUND"})
            return

        # All product requests still cross the real session/origin/budget guards.
        await selected_app(scope, receive, send)

    # Note: We do NOT bind or start anything on 8045.
    print(f"Harness server starting on {HOST}:{args.port}")
    print(f"Temporary storage at: {db_path}")

    # Run server
    try:
        uvicorn.run(harness_app, host=HOST, port=args.port, log_level="error")
    finally:
        print("CLEANING UP TEMP DIR")
        temporary.cleanup()


if __name__ == "__main__":
    sys.exit(main())

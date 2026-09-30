"""Harness server that runs the backend on loopback for e2e tests."""

import argparse
import shutil
import sys
from pathlib import Path

import uvicorn
from backend.app.main import create_app
from backend.app.platform.config import AppSettings

HOST = "127.0.0.1"
PORT = 8000


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()

    import atexit

    TEMP_DIR = Path(__file__).parent.parent / "temp_harness_data"
    if TEMP_DIR.exists():
        shutil.rmtree(TEMP_DIR)
    TEMP_DIR.mkdir(parents=True)

    def cleanup_temp_dir():
        if TEMP_DIR.exists():
            shutil.rmtree(TEMP_DIR, ignore_errors=True)

    atexit.register(cleanup_temp_dir)



    db_path = TEMP_DIR / "test.db"

    # Strict exact-origin loopback config
    settings = AppSettings(
        host=HOST,
        port=args.port,
        storage_path=db_path,
        bridge_url="http://127.0.0.1:8130/v1",  # Synthetic provider, nothing bound here
    )

    app = create_app(settings)

    # Inject test-only endpoints for the harness to control the backend
    import json

    from frontend.tests.support.fake_bridge import clear_requests, get_request_count

    async def harness_app(scope, receive, send):
        if scope["type"] == "lifespan":

            async def wrapped_receive():
                message = await receive()
                if message["type"] == "lifespan.shutdown":
                    # We can't clean up here immediately if files are locked,
                    # but we will try. Actually, better to just let it exit and rely on
                    # temporary folder if we could. Let's just rmtree.
                    pass
                return message

            await app(scope, wrapped_receive, send)
            return

        if scope["type"] == "http" and scope["path"].startswith("/_harness/"):
            path = scope["path"]
            method = scope["method"]

            async def send_json(status_code: int, data: dict | None = None):
                body = json.dumps(data).encode("utf-8") if data is not None else b""
                headers = [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("utf-8")),
                ]
                await send(
                    {"type": "http.response.start", "status": status_code, "headers": headers}
                )
                await send({"type": "http.response.body", "body": body})

            if method == "POST" and path == "/_harness/token":
                if not app.state.ready:
                    await send_json(
                        503, {"error": "NOT_READY", "storage_error": str(app.state.storage_error)}
                    )
                    return
                token = app.state.sessions.issue_bootstrap_token()
                await send_json(200, {"token": token})
                return
            elif method == "GET" and path == "/_harness/db_path":
                await send_json(200, {"path": str(db_path)})
                return
            elif method == "GET" and path == "/_harness/bridge-requests":
                await send_json(200, {"count": get_request_count()})
                return
            elif method == "DELETE" and path == "/_harness/bridge-requests":
                clear_requests()
                await send({"type": "http.response.start", "status": 204, "headers": []})
                await send({"type": "http.response.body", "body": b""})
                return
            elif method == "GET" and path == "/_harness/bridge-preflight":
                import time

                from backend.app.adapters.bridge import BridgeAdapter
                adapter = BridgeAdapter(api_key="dummy-key")
                adapter._base_url = getattr(app.state, "settings", settings).bridge_url
                try:
                    await adapter.preflight(time.monotonic() + 5.0)
                    await send_json(200, {"status": "OK"})
                except Exception as e:
                    await send_json(503, {"error": str(e), "type": type(e).__name__})
                return

            await send_json(404, {"error": "NOT_FOUND"})
            return

        # Fallback to main app
        await app(scope, receive, send)

    # Note: We do NOT bind or start anything on 8045.
    print(f"Harness server starting on {HOST}:{args.port}")
    print(f"Temporary storage at: {db_path}")

    # Run server
    try:
        uvicorn.run(harness_app, host=HOST, port=args.port, log_level="error")
    finally:
        print("CLEANING UP TEMP DIR")
        cleanup_temp_dir()

if __name__ == "__main__":
    sys.exit(main())

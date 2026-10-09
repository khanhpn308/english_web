"""Source-authored T011 platform and production-boundary regressions; Host executes."""

import asyncio
import errno
import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast
from unittest.mock import patch

import httpx
import pytest
from backend.app.adapters.bridge import BridgeAdapter
from backend.app.application.operations import OperationConflict
from backend.app.application.save_answer import SaveAnswerService
from backend.app.http.session import COOKIE_NAME
from backend.app.main import create_app
from backend.app.platform.config import AppSettings
from backend.app.platform.telemetry import (
    MAX_LOG_BYTES,
    MAX_LOG_FILES,
    EventFields,
    LocalJsonSink,
    SpanAttributes,
    Telemetry,
    default_log_directory,
    request_id,
)
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.types import Message

SENTINELS = (
    "SYNTHETIC_KEY_DO_NOT_DISCLOSE",
    "SYNTHETIC_PROMPT_DO_NOT_DISCLOSE",
    "SYNTHETIC_ANSWER_DO_NOT_DISCLOSE",
    "C:\\private\\SYNTHETIC_DATABASE.db",
    "https://private.invalid/SYNTHETIC_URL",
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def records(directory: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for path in sorted(directory.glob("telemetry.jsonl*"))
        for line in path.read_text(encoding="utf-8").splitlines()
    ]


def test_json_schema_and_rejection_before_persistence(tmp_path: Path) -> None:
    sink = LocalJsonSink(tmp_path / "logs")
    telemetry = Telemetry(sink=sink)
    telemetry.emit("app_started", fields=EventFields(status="success"))
    for sentinel in SENTINELS:
        telemetry.emit(sentinel)
        telemetry.emit("app_started", level=sentinel, fields=EventFields(status=sentinel))
        telemetry.emit("http_request_failed", fields=EventFields(route=sentinel))
    output = records(tmp_path / "logs")
    assert output[0]["event"] == "app_started"
    assert output[0]["service"] == "vocab-backend"
    assert output[0]["version"] == "0.1.0"
    assert output[0]["entryPoint"] == "launcher"
    datetime.fromisoformat(str(output[0]["timestamp"]).replace("Z", "+00:00"))
    serialized = json.dumps(output)
    assert all(sentinel not in serialized for sentinel in SENTINELS)
    assert len(output) == 1 + 2 * len(SENTINELS)
    assert all(set(item) <= {
        "timestamp", "level", "event", "service", "version", "entryPoint",
        "status", "requestId", "traceId", "spanId", "route", "durationMs",
    } for item in output)


def test_spans_parent_child_context_cleanup_and_exception_privacy(tmp_path: Path) -> None:
    telemetry = Telemetry(sink=LocalJsonSink(tmp_path / "logs"))
    with pytest.raises(RuntimeError):
        with telemetry.span("http_request", request_id="req_" + "a" * 32) as root:
            with telemetry.span("bridge_call", attributes=SpanAttributes(operation="lookup")):
                telemetry.emit("http_request_failed")
                raise RuntimeError(" ".join(SENTINELS))
    assert telemetry.current_context() is None
    child, finished_root = telemetry.spans()
    assert child.parent_span_id == root.span_id
    assert child.trace_id == finished_root.trace_id == root.trace_id
    assert child.request_id == finished_root.request_id == "req_" + "a" * 32
    assert child.status == finished_root.status == "failure"
    assert child.duration_ms >= 0
    output = records(tmp_path / "logs")
    assert output[0]["traceId"] == child.trace_id
    assert output[0]["spanId"] == child.span_id
    assert all(sentinel not in json.dumps([asdict(s) for s in telemetry.spans()])
               + json.dumps(output) for sentinel in SENTINELS)


def test_attributes_accept_only_categories_and_bounded_counts() -> None:
    telemetry = Telemetry(span_capacity=2)
    for sentinel in SENTINELS:
        with telemetry.span(sentinel, attributes=SpanAttributes(
            operation=sentinel, source_status=sentinel, row_count=10**100,
        )):
            pass
    spans = telemetry.spans()
    assert len(spans) == 2
    assert all(span.name == "local_operation" for span in spans)
    assert all(span.attributes == SpanAttributes() for span in spans)
    assert all(sentinel not in json.dumps([asdict(span) for span in spans])
               for sentinel in SENTINELS)


@pytest.mark.parametrize("identifier", [None, "", "req_unsafe\r\nheader", "x" * 1000, *SENTINELS])
def test_unsafe_correlation_values_are_replaced_before_logs_or_spans(
    tmp_path: Path, identifier: str | None,
) -> None:
    telemetry = Telemetry(sink=LocalJsonSink(tmp_path / "logs"))
    with telemetry.span("http_request", request_id=identifier) as context:
        telemetry.emit("http_request_completed")
    assert len(context.request_id) == 36
    assert context.request_id.startswith("req_")
    assert context.request_id != identifier
    output = json.dumps(records(tmp_path / "logs"))
    stored = json.dumps([asdict(s) for s in telemetry.spans()])
    assert all(sentinel not in output + stored for sentinel in SENTINELS)


def test_arbitrary_mappings_and_exception_objects_are_not_serialized(tmp_path: Path) -> None:
    telemetry = Telemetry(sink=LocalJsonSink(tmp_path / "logs"))
    telemetry.emit("app_started", fields=cast(EventFields, {"prompt": SENTINELS[0]}))
    telemetry.emit("http_request_failed", fields=EventFields(
        status=cast(str, RuntimeError(SENTINELS[0])),
    ))
    output = records(tmp_path / "logs")
    assert len(output) == 2
    assert all("status" not in item for item in output)
    assert SENTINELS[0] not in json.dumps(output)


@pytest.mark.parametrize("failed_function", ["uuid4", "monotonic"])
def test_span_setup_failure_cannot_prevent_learning_or_mask_operation_error(
    failed_function: str,
) -> None:
    telemetry = Telemetry()
    outcomes: list[str] = []
    original = RuntimeError("SYNTHETIC_OPERATION_ERROR")
    with patch(
        f"backend.app.platform.telemetry.{failed_function}",
        side_effect=OSError(SENTINELS[0]),
    ):
        with telemetry.span("sqlite"):
            outcomes.append("saved")
        with pytest.raises(RuntimeError) as caught, telemetry.span("sqlite"):
            raise original
    assert caught.value is original
    assert outcomes == ["saved"]
    assert telemetry.span_retention_failed is True
    assert telemetry.current_context() is None
    assert telemetry.spans() == ()


def test_span_finalization_failure_preserves_original_exception() -> None:
    telemetry = Telemetry()
    original = RuntimeError("SYNTHETIC_OPERATION_ERROR")
    with patch("backend.app.platform.telemetry._duration", side_effect=OSError(SENTINELS[0])):
        with pytest.raises(RuntimeError) as caught, telemetry.span("sqlite"):
            raise original
    assert caught.value is original
    assert telemetry.span_retention_failed is True
    assert telemetry.current_context() is None


def test_expired_spans_are_pruned_during_collection() -> None:
    telemetry = Telemetry()
    clock = [0.0]
    with patch("backend.app.platform.telemetry.monotonic", side_effect=lambda: clock[0]):
        with telemetry.span("sqlite"):
            pass
        clock[0] = 15 * 86_400
        with telemetry.span("markdown"):
            pass
        # Inspect retention before the read API can perform its own cleanup.
        assert len(telemetry._spans) == 1
        assert [s.name for s in telemetry.spans()] == ["markdown"]


def test_duration_is_finite_and_bounded() -> None:
    telemetry = Telemetry()
    with patch("backend.app.platform.telemetry.monotonic", side_effect=[0.0, 10**20, 10**20]):
        with telemetry.span("sqlite"):
            pass
    assert telemetry.spans()[0].duration_ms == 86_400_000


@pytest.mark.anyio
async def test_concurrent_contexts_and_separate_telemetry_instances() -> None:
    telemetry = Telemetry()
    other = Telemetry()
    barrier = asyncio.Event()
    arrived = 0

    async def operation(request_id: str) -> None:
        nonlocal arrived
        with telemetry.span("http_request", request_id=request_id) as root:
            arrived += 1
            if arrived == 2:
                barrier.set()
            await barrier.wait()
            assert other.current_context() is None
            with telemetry.span("sqlite") as child:
                await asyncio.sleep(0)
                assert child.request_id == request_id
                assert child.trace_id == root.trace_id
                assert child.parent_span_id == root.span_id
        assert telemetry.current_context() is None

    await asyncio.gather(operation("req_" + "a" * 32), operation("req_" + "b" * 32))
    roots = [s for s in telemetry.spans() if s.name == "http_request"]
    assert len({s.trace_id for s in roots}) == 2
    assert len(telemetry.spans()) == 4
    assert telemetry.current_context() is None


def test_retention_and_size_rotation_preserve_unrelated_files(tmp_path: Path) -> None:
    directory = tmp_path / "logs"
    sink = LocalJsonSink(directory)
    telemetry = Telemetry(sink=sink)
    telemetry.emit("app_started")
    unrelated = directory / "learning.md"
    unrelated.write_text("SYNTHETIC_LEARNING_DATA", encoding="utf-8")
    # Patch the ceiling, exercising the production rotation algorithm cheaply.
    with patch("backend.app.platform.telemetry.MAX_LOG_BYTES", 600):
        for _ in range(100):
            telemetry.emit("app_started")
    files = list(directory.glob("telemetry.jsonl*"))
    assert len(files) == MAX_LOG_FILES == 5
    assert all(path.stat().st_size <= 600 for path in files)
    assert MAX_LOG_BYTES == 10 * 1024 * 1024
    assert unrelated.read_text(encoding="utf-8") == "SYNTHETIC_LEARNING_DATA"
    assert records(directory)


def test_age_retention_uses_oldest_event_not_refreshed_mtime(tmp_path: Path) -> None:
    directory = tmp_path / "logs"
    telemetry = Telemetry(sink=LocalJsonSink(directory))
    telemetry.emit("app_started")
    path = directory / "telemetry.jsonl"
    first = json.loads(path.read_text(encoding="utf-8"))
    first["timestamp"] = (datetime.now(UTC) - timedelta(days=15)).isoformat()
    path.write_text(json.dumps(first) + "\n", encoding="utf-8")
    os.utime(path, None)
    telemetry.emit("app_shutdown")
    assert [r["event"] for r in records(directory)] == ["app_shutdown"]


@pytest.mark.parametrize(
    "failure",
    [PermissionError(errno.EACCES, SENTINELS[0]), OSError(errno.ENOSPC, SENTINELS[0])],
    ids=["permission-denied", "disk-full"],
)
def test_sink_failure_is_bounded_and_preserves_learning(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], failure: OSError,
) -> None:
    data = tmp_path / "learning.md"
    data.write_text("SYNTHETIC_SAVED_ANSWER", encoding="utf-8")
    telemetry = Telemetry(sink=LocalJsonSink(tmp_path / "logs"))
    with patch("backend.app.platform.telemetry.os.open", side_effect=failure):
        for _ in range(50):
            with telemetry.span("sqlite"):
                telemetry.emit("http_request_completed")
    stderr = capsys.readouterr().err.splitlines()
    assert len(stderr) == 1
    assert json.loads(stderr[0])["event"] == "telemetry_rotation_failed"
    assert all(sentinel not in stderr[0] for sentinel in SENTINELS)
    assert data.read_text(encoding="utf-8") == "SYNTHETIC_SAVED_ANSWER"
    assert len(telemetry.spans()) == 50


def test_busy_sink_drops_event_without_wait_or_user_data_changes(tmp_path: Path) -> None:
    sink = LocalJsonSink(tmp_path / "logs")
    telemetry = Telemetry(sink=sink)
    with sink._lock:
        assert telemetry.emit("app_started") is False
    assert not (tmp_path / "logs").exists()
    assert telemetry.emit("app_started") is True
    assert len(records(tmp_path / "logs")) == 1


def test_rotation_failure_never_escapes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    sink = LocalJsonSink(tmp_path / "logs")
    telemetry = Telemetry(sink=sink)
    telemetry.emit("app_started")
    with (
        patch("backend.app.platform.telemetry.MAX_LOG_BYTES", 250),
        patch.object(Path, "replace", side_effect=OSError(" ".join(SENTINELS))),
    ):
        telemetry.emit("app_shutdown")
        telemetry.emit("app_shutdown")
    assert len(capsys.readouterr().err.splitlines()) == 1
    assert len(records(tmp_path / "logs")) == 1


def test_file_wrapper_failure_closes_the_owned_descriptor(tmp_path: Path) -> None:
    sink = LocalJsonSink(tmp_path / "logs")
    telemetry = Telemetry(sink=sink)
    opened: list[int] = []
    original_open = os.open

    def tracked_open(path: Path, flags: int, mode: int) -> int:
        descriptor = original_open(path, flags, mode)
        opened.append(descriptor)
        return descriptor

    with (
        patch("backend.app.platform.telemetry.os.open", side_effect=tracked_open),
        patch("backend.app.platform.telemetry.os.fdopen", side_effect=OSError(SENTINELS[0])),
    ):
        assert telemetry.emit("app_started") is False
    assert len(opened) == 1
    with pytest.raises(OSError):
        os.fstat(opened[0])
    assert sink.failed is True


def test_unowned_file_is_not_overwritten_or_deleted(tmp_path: Path) -> None:
    directory = tmp_path / "logs"
    directory.mkdir()
    path = directory / "telemetry.jsonl"
    path.write_text("SYNTHETIC_USER_MARKDOWN", encoding="utf-8")
    telemetry = Telemetry(sink=LocalJsonSink(directory))
    telemetry.emit("app_started")
    assert path.read_text(encoding="utf-8") == "SYNTHETIC_USER_MARKDOWN"


def test_no_global_logging_handlers_and_closed_sink(tmp_path: Path) -> None:
    import logging

    before = tuple(logging.getLogger().handlers)
    sink = LocalJsonSink(tmp_path / "logs")
    telemetry = Telemetry(sink=sink)
    telemetry.emit("app_started")
    sink.close()
    telemetry.emit("app_shutdown")
    assert len(records(tmp_path / "logs")) == 1
    assert tuple(logging.getLogger().handlers) == before


def test_default_storage_is_windows_native_not_a_linux_environment_mapping() -> None:
    with patch.dict(os.environ, {"LOCALAPPDATA": "/synthetic/windows/path"}):
        if os.name != "nt":
            assert default_log_directory() is None


def test_restrictive_posix_permissions_and_symlink_refusal(tmp_path: Path) -> None:
    if os.name == "nt":
        # Windows ACL evidence belongs to T040/T054; do not attempt POSIX chmod there.
        directory = default_log_directory()
        assert directory is None or directory.is_absolute()
        return
    directory = tmp_path / "logs"
    telemetry = Telemetry(sink=LocalJsonSink(directory))
    telemetry.emit("app_started")
    assert directory.stat().st_mode & 0o777 == 0o700
    assert (directory / "telemetry.jsonl").stat().st_mode & 0o777 == 0o600
    target = tmp_path / "learning.md"
    target.write_text("SYNTHETIC_LEARNING", encoding="utf-8")
    linked = tmp_path / "linked"
    linked.mkdir()
    (linked / "telemetry.jsonl").symlink_to(target)
    Telemetry(sink=LocalJsonSink(linked)).emit("app_started")
    assert target.read_text(encoding="utf-8") == "SYNTHETIC_LEARNING"


BASE = "http://127.0.0.1:8000"
SAFE_ID = "req_" + "c" * 32


def telemetry_app(tmp_path: Path) -> FastAPI:
    # Production create_app and every production middleware remain in the stack.
    with patch("backend.app.main.default_log_directory", return_value=tmp_path / "logs"):
        return create_app(AppSettings(storage_path=None))


def authenticate(app: FastAPI, client: TestClient) -> None:
    token = app.state.sessions.issue_bootstrap_token()
    response = client.post(
        "/bootstrap/exchange", json={"token": token}, headers={"Origin": BASE},
    )
    assert response.status_code == 204


@pytest.mark.parametrize("incoming", [SAFE_ID, "6eec59ab-279a-4b48-83d3-5c47f508aa11"])
def test_production_http_echo_and_correlated_root_child(tmp_path: Path, incoming: str) -> None:
    app = telemetry_app(tmp_path)
    with TestClient(app, base_url=BASE) as client:
        response = client.get("/api/v1/health", headers={"X-Request-ID": incoming})
        assert response.status_code == 200
        assert response.headers["X-Request-ID"] == incoming
        assert response.headers["Cache-Control"] == "no-store"
        spans = [s for s in app.state.telemetry.spans() if s.request_id == incoming]
        root = next(s for s in spans if s.name == "http_request")
        child = next(s for s in spans if s.name == "route_handler")
        assert child.parent_span_id == root.span_id
        assert child.trace_id == root.trace_id
        event = next(r for r in records(tmp_path / "logs") if r.get("requestId") == incoming)
        assert event["traceId"] == root.trace_id
        assert event["spanId"] == root.span_id
        assert event["route"] == "GET /api/v1/health"
    assert [r["event"] for r in records(tmp_path / "logs") if "requestId" not in r] == [
        "app_started", "app_shutdown",
    ]
    assert not app.state.sessions.valid_session("SYNTHETIC_SESSION_TOKEN")


@pytest.mark.parametrize("incoming", [None, "unsafe", "x" * 1000, "unsafe\t", SENTINELS[0]])
def test_production_http_replaces_invalid_ids(tmp_path: Path, incoming: str | None) -> None:
    app = telemetry_app(tmp_path)
    with TestClient(app, base_url=BASE) as client:
        headers = {} if incoming is None else {"X-Request-ID": incoming}
        headers["Cookie"] = f"{COOKIE_NAME}=SYNTHETIC_SESSION_TOKEN"
        headers["Authorization"] = SENTINELS[0]
        response = client.get("/api/v1/health", headers=headers)
        effective = response.headers["X-Request-ID"]
        assert effective != incoming
        assert len(effective) == 36 and effective.startswith("req_")
        assert any(r.get("requestId") == effective for r in records(tmp_path / "logs"))
        output = json.dumps(records(tmp_path / "logs"))
        assert "SYNTHETIC_SESSION_TOKEN" not in output
        assert SENTINELS[0] not in output


def test_duplicate_ids_and_early_session_origin_body_rejections(tmp_path: Path) -> None:
    app = telemetry_app(tmp_path)
    with TestClient(app, base_url=BASE) as client:
        duplicate = client.get("/api/v1/health", headers=[
            ("X-Request-ID", SAFE_ID), ("X-Request-ID", "req_" + "d" * 32),
        ])
        assert duplicate.headers["X-Request-ID"] not in {SAFE_ID, "req_" + "d" * 32}
        denied = client.get("/api/v1/sources", headers={"X-Request-ID": SAFE_ID})
        assert denied.status_code == 401
        assert denied.json()["error"]["code"] == "SESSION_REQUIRED"
        origin = client.get("/api/v1/health", headers={
            "Origin": "https://hostile.invalid", "X-Request-ID": SAFE_ID,
        })
        assert origin.status_code == 403
        authenticate(app, client)
        oversized = client.post("/api/v1/quiz-attempts", content="{}", headers={
            "Origin": BASE, "Content-Type": "application/json",
            "Content-Length": "1048577", "X-Request-ID": SAFE_ID,
        })
        assert oversized.status_code == 413
        for response in (denied, origin, oversized):
            assert response.json()["error"]["requestId"] == response.headers["X-Request-ID"]
            assert response.headers["X-Request-ID"] == SAFE_ID
            assert response.headers["Cache-Control"] == "no-store"
            assert response.headers["X-Content-Type-Options"] == "nosniff"
    events = records(tmp_path / "logs")
    assert sum(r["event"] == "security_boundary_rejected" for r in events) == 3


def test_validation_and_quiz_answer_local_error_correlation(tmp_path: Path) -> None:
    app = telemetry_app(tmp_path)
    with TestClient(app, base_url=BASE) as client:
        authenticate(app, client)
        headers = {"Origin": BASE, "X-Request-ID": SAFE_ID}
        invalid = client.put("/api/v1/quiz-attempts/attempt/answers/question", json={},
                             headers=headers)
        assert invalid.status_code == 422
        assert invalid.json()["error"]["requestId"] == invalid.headers["X-Request-ID"] == SAFE_ID
        app.state.answer_service = object.__new__(SaveAnswerService)
        app.state.ready = True
        with patch.object(SaveAnswerService, "save", side_effect=OperationConflict(
            409, "REVISION_CONFLICT",
        )):
            conflict = client.put("/api/v1/quiz-attempts/attempt/answers/question", json={
                "answer": SENTINELS[2], "draftRevision": 0,
            }, headers={
                **headers, "Idempotency-Key": "synthetic-intent",
                "If-Match": '"qa-v1-' + "0" * 64 + '"',
            })
        assert conflict.status_code == 409
        assert conflict.json()["error"] == {
            "code": "REVISION_CONFLICT", "message": "Answer revision conflict",
            "requestId": SAFE_ID,
        }
        assert conflict.headers["X-Request-ID"] == SAFE_ID
        assert conflict.headers["Cache-Control"] == "no-store"
    assert all(s not in json.dumps(records(tmp_path / "logs")) + json.dumps([
        asdict(span) for span in app.state.telemetry.spans()
    ]) for s in SENTINELS)


@pytest.mark.anyio
async def test_production_concurrent_requests_and_exception_cleanup(tmp_path: Path) -> None:
    app = telemetry_app(tmp_path)
    barrier = asyncio.Event()
    entered = 0

    @app.get("/api/v1/synthetic-context")
    async def context_route(request: Request) -> dict[str, str]:
        nonlocal entered
        entered += 1
        if entered == 2:
            barrier.set()
        await barrier.wait()
        with request.app.state.telemetry.span("sqlite") as child:
            await asyncio.sleep(0)
            assert child.request_id == request_id()
            return {"id": request_id(), "trace": child.trace_id}

    @app.get("/api/v1/synthetic-failure")
    async def failing_route() -> None:
        raise RuntimeError(" ".join(SENTINELS))

    async with app.router.lifespan_context(app):
        cookie = app.state.sessions.exchange(app.state.sessions.issue_bootstrap_token())
        assert cookie is not None
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url=BASE,
            cookies={COOKIE_NAME: cookie},
        ) as client:
            ids = ["req_" + "a" * 32, "req_" + "b" * 32]
            responses = await asyncio.gather(*[
                client.get("/api/v1/synthetic-context", headers={"X-Request-ID": identifier})
                for identifier in ids
            ])
            assert [r.json()["id"] for r in responses] == ids
            assert len({r.json()["trace"] for r in responses}) == 2
            assert app.state.telemetry.current_context() is None
            assert request_id() not in ids
            with pytest.raises(RuntimeError) as caught:
                await client.get("/api/v1/synthetic-failure", headers={"X-Request-ID": SAFE_ID})
            assert str(caught.value) == " ".join(SENTINELS)
            assert app.state.telemetry.current_context() is None
            assert request_id() != SAFE_ID
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url=BASE,
            cookies={COOKIE_NAME: cookie},
        ) as client:
            response = await client.get(
                "/api/v1/synthetic-failure", headers={"X-Request-ID": SAFE_ID},
            )
            assert response.status_code == 500
            assert response.headers["X-Request-ID"] == SAFE_ID
            assert all(s not in response.text for s in SENTINELS)
    serialized = json.dumps(records(tmp_path / "logs")) + json.dumps([
        asdict(span) for span in app.state.telemetry.spans()
    ])
    assert all(s not in serialized for s in (*SENTINELS, cookie))


def test_failing_sink_preserves_route_exception_and_success(tmp_path: Path) -> None:
    app = telemetry_app(tmp_path)
    original = RuntimeError(" ".join(SENTINELS))

    @app.get("/api/v1/synthetic-failure")
    def failure() -> None:
        raise original

    with TestClient(app, base_url=BASE) as client:
        authenticate(app, client)
        with patch("backend.app.platform.telemetry.os.open", side_effect=PermissionError(
            SENTINELS[0],
        )):
            with pytest.raises(RuntimeError) as caught:
                client.get("/api/v1/synthetic-failure", headers={"X-Request-ID": SAFE_ID})
            assert caught.value is original
            assert client.get("/api/v1/health").status_code == 200
        assert app.state.telemetry.sink.failed


@pytest.mark.anyio
async def test_bridge_strips_headers_after_injection_in_all_stages(tmp_path: Path) -> None:
    captured: list[httpx.Request] = []
    telemetry = Telemetry(sink=LocalJsonSink(tmp_path / "bridge-logs"))

    def fake_bridge(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        assert request.url.host == "127.0.0.1" and request.url.port == 8045
        assert not any(h in request.headers for h in (
            "x-request-id", "traceparent", "tracestate", "baggage",
        ))
        if len(captured) == 1:
            assert "authorization" not in request.headers
            return httpx.Response(401)
        assert request.headers["Authorization"] == f"Bearer {SENTINELS[0]}"
        if request.method == "GET":
            return httpx.Response(200, json={"data": []})
        assert json.loads(request.content)["messages"][0]["content"] == SENTINELS[1]
        return httpx.Response(200, json={"choices": []})

    async def inject(request: httpx.Request) -> None:
        for name in ("X-Request-ID", "TraceParent", "TraceState", "BaGgAgE"):
            request.headers[name] = SENTINELS[2]

    adapter = BridgeAdapter(
        SENTINELS[0], transport=httpx.MockTransport(fake_bridge), clock=lambda: 0,
    )
    original_client = adapter._get_client

    def instrumented_client() -> httpx.AsyncClient:
        client = original_client()
        client.headers["X-Request-ID"] = SAFE_ID
        client.event_hooks["request"].append(inject)
        return client

    with patch.object(adapter, "_get_client", side_effect=instrumented_client):
        with telemetry.span("http_request", request_id=SAFE_ID) as root:
            with telemetry.span("bridge_call") as child:
                await adapter.preflight(30)
                result = await adapter.dispatch_chat({
                    "messages": [{"role": "user", "content": SENTINELS[1]}],
                }, 30)
                assert result == {"choices": []}
                assert child.trace_id == root.trace_id
                assert child.parent_span_id == root.span_id
    assert [r.method for r in captured] == ["GET", "GET", "POST"]
    assert all(s not in json.dumps([asdict(span) for span in telemetry.spans()]) for s in SENTINELS)


def test_factory_preserves_routers_and_has_no_duplicate_telemetry(tmp_path: Path) -> None:
    first = telemetry_app(tmp_path / "first")
    second = telemetry_app(tmp_path / "second")
    assert first.state.telemetry is not second.state.telemetry
    required = {
        "/api/v1/health", "/bootstrap/exchange", "/api/v1/ai-consent",
        "/api/v1/operations/{operation_id}", "/api/v1/sources", "/api/v1/sync-runs",
        "/api/v1/review-queue", "/api/v1/lookups", "/api/v1/quiz-attempts",
        "/api/v1/quiz-attempts/{attemptId}/answers/{questionId}",
    }
    assert required <= {getattr(route, "path", None) for route in first.routes}
    assert [m.cls.__name__ for m in first.user_middleware] == [
        "RequestBudgetMiddleware", "SessionGuard", "RouteSpanMiddleware",
    ]
    with TestClient(first, base_url=BASE) as client:
        client.get("/api/v1/health")
        client.get("/api/v1/health")
    events = records(tmp_path / "first" / "logs")
    assert sum(r["event"] == "http_request_completed" for r in events) == 2
    assert sum(r["event"] == "app_started" for r in events) == 1
    assert sum(r["event"] == "app_shutdown" for r in events) == 1


@pytest.mark.anyio
async def test_body_timeout_response_keeps_authoritative_correlation(tmp_path: Path) -> None:
    app = telemetry_app(tmp_path)
    messages: list[Message] = []

    async def receive() -> Message:
        raise TimeoutError("SYNTHETIC_BODY_TIMEOUT")

    async def send(message: Message) -> None:
        messages.append(message)

    async with app.router.lifespan_context(app):
        cookie = app.state.sessions.exchange(app.state.sessions.issue_bootstrap_token())
        assert cookie is not None
        await app({
            "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
            "method": "POST", "scheme": "http", "path": "/api/v1/quiz-attempts",
            "raw_path": b"/api/v1/quiz-attempts", "query_string": b"",
            "root_path": "", "server": ("127.0.0.1", 8000), "client": ("127.0.0.1", 1234),
            "headers": [
                (b"host", b"127.0.0.1:8000"), (b"origin", BASE.encode()),
                (b"content-type", b"application/json"), (b"x-request-id", SAFE_ID.encode()),
                (b"cookie", f"{COOKIE_NAME}={cookie}".encode()),
            ],
        }, receive, send)
        start = next(m for m in messages if m["type"] == "http.response.start")
        body = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body")
        assert start["status"] == 503
        assert dict(start["headers"])[b"x-request-id"] == SAFE_ID.encode()
        assert dict(start["headers"])[b"cache-control"] == b"no-store"
        assert json.loads(body)["error"]["requestId"] == SAFE_ID
        assert app.state.telemetry.current_context() is None
        assert request_id() != SAFE_ID


@pytest.mark.anyio
async def test_lifecycle_diagnostic_failures_do_not_mask_application_failure(
    tmp_path: Path,
) -> None:
    app = telemetry_app(tmp_path)
    original = RuntimeError("SYNTHETIC_LIFECYCLE_FAILURE")

    @asynccontextmanager
    async def failing_lifecycle(_app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            raise original

    with (
        patch("backend.app.main._application_lifespan", failing_lifecycle),
        patch.object(app.state.telemetry, "emit", side_effect=OSError(SENTINELS[0])),
        patch.object(app.state.telemetry.sink, "close", side_effect=OSError(SENTINELS[1])),
    ):
        with pytest.raises(RuntimeError) as caught:
            async with app.router.lifespan_context(app):
                pass
    assert caught.value is original
    assert app.state.telemetry.span_retention_failed is True

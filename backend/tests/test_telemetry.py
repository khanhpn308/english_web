"""Source-authored T011 platform regressions; Host owns execution.

HTTP integration and injected outbound-header enforcement require the scope
extensions described in the handoff. These tests do not claim those guarantees.
"""

import asyncio
import errno
import json
import os
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast
from unittest.mock import patch

import pytest
from backend.app.platform.telemetry import (
    MAX_LOG_BYTES,
    MAX_LOG_FILES,
    EventFields,
    LocalJsonSink,
    SpanAttributes,
    Telemetry,
    default_log_directory,
)

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

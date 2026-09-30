import json
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from time import monotonic
from typing import Any

import httpx
import pytest
from backend.app.adapters.bridge import MAX_RESPONSE_BYTES, BridgeAdapter
from backend.app.platform.bridge_port import (
    BridgeAuthError,
    BridgeConfigError,
    BridgeInvalidResponseError,
    BridgeUnavailableError,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "bridge_cases.json"


@pytest.fixture(autouse=True)
def guard_no_real_network(monkeypatch: pytest.MonkeyPatch) -> None:
    original_client = httpx.AsyncClient

    def mocked_client(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        if "transport" not in kwargs or kwargs["transport"] is None:
            raise RuntimeError("Test attempted to create HTTPX client without a mock transport")
        return original_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", mocked_client)


@pytest.fixture
def bridge_cases() -> dict[str, Any]:
    with FIXTURE_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data, dict)
    return data


class MockClock:
    def __init__(self, start: float = 0.0) -> None:
        self.time = start

    def __call__(self) -> float:
        return self.time


def create_mock_transport(
    handler: Callable[[httpx.Request], httpx.Response],
) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


@pytest.mark.anyio
async def test_br_auth_01_auth_failure(bridge_cases: dict[str, Any]) -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if request.url.path == "/v1/models":
            auth = request.headers.get("Authorization")
            if not auth or auth != "Bearer dummy_key":
                return httpx.Response(401)
            return httpx.Response(200, json=bridge_cases["models_valid"])
        if request.url.path == "/v1/chat/completions":
            auth = request.headers.get("Authorization")
            if not auth or auth != "Bearer dummy_key":
                return httpx.Response(403)
            return httpx.Response(200, json=bridge_cases["chat_valid"])
        return httpx.Response(404)

    transport = create_mock_transport(handler)

    # No key provided
    adapter_no_key = BridgeAdapter(api_key=None, transport=transport)
    with pytest.raises(BridgeConfigError, match="Missing proxy credentials"):
        await adapter_no_key.preflight(monotonic() + 10.0)

    # Wrong key provided
    adapter_wrong_key = BridgeAdapter(api_key="wrong_key", transport=transport)
    with pytest.raises(BridgeAuthError, match="Proxy rejected credentials"):
        await adapter_wrong_key.preflight(monotonic() + 10.0)

    with pytest.raises(BridgeAuthError, match="Proxy rejected credentials"):
        await adapter_wrong_key.dispatch_chat({}, monotonic() + 10.0)


@pytest.mark.anyio
async def test_br_auth_02_approved_synthetic_profile(bridge_cases: dict[str, Any]) -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        auth = request.headers.get("Authorization")
        requests.append((request.url.path, auth))
        if request.url.path == "/v1/models":
            if not auth:
                return httpx.Response(401)
            return httpx.Response(200, json=bridge_cases["models_valid"])
        if request.url.path == "/v1/chat/completions":
            return httpx.Response(200, json=bridge_cases["chat_valid"])
        return httpx.Response(404)

    transport = create_mock_transport(handler)
    adapter = BridgeAdapter(api_key="dummy_key", transport=transport)

    profile = await adapter.preflight(monotonic() + 10.0)
    assert profile.models[0]["id"] == "gemini-3.8-flash-high"

    chat_resp = await adapter.dispatch_chat({"messages": []}, monotonic() + 10.0)
    assert chat_resp["id"] == "chatcmpl-123"

    # 2 requests for preflight (no-key then key), 1 for chat
    assert requests == [
        ("/v1/models", None),
        ("/v1/models", "Bearer dummy_key"),
        ("/v1/chat/completions", "Bearer dummy_key"),
    ]


@pytest.mark.anyio
async def test_br_auth_03_unsafe_auto_off(bridge_cases: dict[str, Any]) -> None:
    requests: list[tuple[str, str | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.url.path, request.headers.get("Authorization")))
        return httpx.Response(200, json=bridge_cases["models_valid"])

    transport = create_mock_transport(handler)
    adapter = BridgeAdapter(api_key="dummy_key", transport=transport)

    with pytest.raises(BridgeConfigError, match="Unsafe proxy configuration"):
        await adapter.preflight(monotonic() + 10.0)
    # Exactly one request made, keyed request never transmitted
    assert requests == [("/v1/models", None)]
    assert sum(path == "/v1/chat/completions" for path, _ in requests) == 0


@pytest.mark.anyio
async def test_br_auth_04_destination_hardening_and_redirects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"Location": "http://example.com/"})

    transport = create_mock_transport(handler)
    adapter = BridgeAdapter(api_key="dummy_key", transport=transport)

    with pytest.raises(BridgeUnavailableError, match="Unexpected redirect"):
        await adapter.preflight(monotonic() + 10.0)

    monkeypatch.setenv("HTTP_PROXY", "http://evil.proxy")
    adapter2 = BridgeAdapter(api_key="dummy_key", transport=transport)
    client = adapter2._get_client()
    assert client.trust_env is False


@pytest.mark.anyio
async def test_br_auth_05_secret_header_capture(bridge_cases: dict[str, Any]) -> None:
    captured_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_headers
        auth = request.headers.get("Authorization")
        if not auth:
            return httpx.Response(401)
        captured_headers = dict(request.headers)
        return httpx.Response(200, json=bridge_cases["models_valid"])

    transport = create_mock_transport(handler)
    adapter = BridgeAdapter(api_key="dummy_key", transport=transport)
    await adapter.preflight(monotonic() + 10.0)

    assert captured_headers.get("authorization") == "Bearer dummy_key"
    assert "cookie" not in captured_headers
    assert "x-request-id" not in captured_headers
    assert "traceparent" not in captured_headers


@pytest.mark.anyio
async def test_br_auth_07_dependency_failures() -> None:
    def timeout_handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("Timeout")

    adapter = BridgeAdapter(api_key="dummy", transport=create_mock_transport(timeout_handler))
    with pytest.raises(BridgeUnavailableError, match="Proxy connection failed"):
        await adapter.preflight(monotonic() + 10.0)

    def malformed_json_handler(request: httpx.Request) -> httpx.Response:
        auth = request.headers.get("Authorization")
        if not auth:
            return httpx.Response(401)
        return httpx.Response(200, text="not json")

    adapter2 = BridgeAdapter(
        api_key="dummy", transport=create_mock_transport(malformed_json_handler)
    )
    with pytest.raises(BridgeInvalidResponseError, match="Malformed JSON response"):
        await adapter2.preflight(monotonic() + 10.0)

    def malformed_schema_handler(request: httpx.Request) -> httpx.Response:
        auth = request.headers.get("Authorization")
        if not auth:
            return httpx.Response(401)
        return httpx.Response(200, json={"object": "list", "items": []})

    adapter3 = BridgeAdapter(
        api_key="dummy", transport=create_mock_transport(malformed_schema_handler)
    )
    with pytest.raises(BridgeInvalidResponseError, match="Malformed models response schema"):
        await adapter3.preflight(monotonic() + 10.0)


@pytest.mark.anyio
@pytest.mark.parametrize("start", [5.0, 5.1])
async def test_preflight_deadline_before_first_request(start: float) -> None:
    clock = MockClock(start)
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(401)

    adapter = BridgeAdapter(
        api_key="dummy", transport=create_mock_transport(handler), clock=clock
    )
    with pytest.raises(BridgeUnavailableError, match="Operation deadline exceeded"):
        await adapter.preflight(5.0)

    assert requests == []


@pytest.mark.anyio
async def test_preflight_shrinking_deadline(bridge_cases: dict[str, Any]) -> None:
    clock = MockClock(0.0)
    request_timeouts: list[dict[str, float]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/models"
        request_timeouts.append(request.extensions["timeout"])
        if request.headers.get("Authorization") is None:
            clock.time = 4.0
            return httpx.Response(401)
        assert clock.time == 4.0
        return httpx.Response(200, json=bridge_cases["models_valid"])

    adapter = BridgeAdapter(
        api_key="dummy", transport=create_mock_transport(handler), clock=clock
    )
    await adapter.preflight(5.0)

    assert clock.time == 4.0
    assert len(request_timeouts) == 2
    for actual, remaining in zip(request_timeouts, [5.0, 1.0], strict=True):
        assert actual == pytest.approx(
            dict.fromkeys(["connect", "read", "write", "pool"], remaining)
        )


@pytest.mark.anyio
@pytest.mark.parametrize("no_key_completion", [5.0, 5.1])
async def test_preflight_exhausted_deadline(no_key_completion: float) -> None:
    clock = MockClock(0.0)
    requests: list[tuple[str, str | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.url.path, request.headers.get("Authorization")))
        assert request.extensions["timeout"]["read"] == pytest.approx(5.0)
        clock.time = no_key_completion
        return httpx.Response(401)

    adapter = BridgeAdapter(
        api_key="dummy", transport=create_mock_transport(handler), clock=clock
    )
    with pytest.raises(BridgeUnavailableError, match="Operation deadline exceeded"):
        await adapter.preflight(5.0)

    assert requests == [("/v1/models", None)]


@pytest.mark.anyio
async def test_monotonic_deadline(bridge_cases: dict[str, Any]) -> None:
    clock = MockClock(0.0)
    request_timeouts: list[dict[str, float]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        request_timeouts.append(request.extensions["timeout"])
        auth = request.headers.get("Authorization")
        if request.url.path == "/v1/models":
            clock.time += 2.0
        if request.url.path == "/v1/models" and not auth:
            return httpx.Response(401)
        if request.url.path == "/v1/models" and auth:
            return httpx.Response(200, json=bridge_cases["models_valid"])
        return httpx.Response(200, json=bridge_cases["chat_valid"])

    transport = create_mock_transport(handler)
    adapter = BridgeAdapter(api_key="dummy", transport=transport, clock=clock)

    # Operation 1 (absolute deadline 5.0)
    op1_deadline = 5.0
    assert clock.time == 0.0
    await adapter.preflight(op1_deadline)
    # clock is now 4.0 because preflight made 2 requests
    assert clock.time == 4.0

    timeout = adapter._get_timeout(op1_deadline)
    assert timeout.read == 1.0
    await adapter.dispatch_chat({}, op1_deadline)
    assert len(request_timeouts) == 3
    for actual, remaining in zip(request_timeouts, [5.0, 3.0, 1.0], strict=True):
        assert actual == pytest.approx(
            dict.fromkeys(["connect", "read", "write", "pool"], remaining)
        )

    clock.time = 5.1
    with pytest.raises(BridgeUnavailableError, match="Operation deadline exceeded"):
        await adapter.dispatch_chat({}, op1_deadline)
    assert len(request_timeouts) == 3

    # Independent operation gets fresh deadline
    op2_deadline = clock.time + 10.0
    assert op2_deadline == 15.1
    clock.time += 2.0  # Wait 2 secs, op2_deadline still has 8s
    timeout2 = adapter._get_timeout(op2_deadline)
    assert timeout2.read == pytest.approx(8.0)
    await adapter.preflight(op2_deadline)
    await adapter.dispatch_chat({}, op2_deadline)
    assert len(request_timeouts) == 6
    assert clock.time == pytest.approx(11.1)
    for actual, remaining in zip(request_timeouts[3:], [8.0, 6.0, 4.0], strict=True):
        assert actual == pytest.approx(
            dict.fromkeys(["connect", "read", "write", "pool"], remaining)
        )


@pytest.mark.anyio
async def test_stream_limit() -> None:
    def get_handler(
        size: int, content_length: str | None = None
    ) -> Callable[[httpx.Request], httpx.Response]:
        def handler(request: httpx.Request) -> httpx.Response:
            auth = request.headers.get("Authorization")
            if not auth:
                return httpx.Response(401)

            class MockStream(httpx.AsyncByteStream):
                async def __aiter__(self) -> AsyncIterator[bytes]:
                    yield b"a" * size

            headers = {}
            if content_length is not None:
                headers["Content-Length"] = content_length
            return httpx.Response(200, stream=MockStream(), headers=headers)

        return handler

    # Exact limit
    transport_exact = create_mock_transport(get_handler(MAX_RESPONSE_BYTES))
    adapter_exact = BridgeAdapter(api_key="dummy", transport=transport_exact)
    with pytest.raises(BridgeInvalidResponseError, match="Malformed JSON response"):
        await adapter_exact.preflight(monotonic() + 10.0)

    # Limit - 1
    transport_under = create_mock_transport(get_handler(MAX_RESPONSE_BYTES - 1))
    adapter_under = BridgeAdapter(api_key="dummy", transport=transport_under)
    with pytest.raises(BridgeInvalidResponseError, match="Malformed JSON response"):
        await adapter_under.preflight(monotonic() + 10.0)

    # Limit + 1 (chunked)
    transport_over = create_mock_transport(get_handler(MAX_RESPONSE_BYTES + 1))
    adapter_over = BridgeAdapter(api_key="dummy", transport=transport_over)
    with pytest.raises(BridgeInvalidResponseError, match="Response exceeded maximum size"):
        await adapter_over.preflight(monotonic() + 10.0)

    # Declared Content-Length > limit
    transport_cl_over = create_mock_transport(
        get_handler(1, content_length=str(MAX_RESPONSE_BYTES + 1))
    )
    adapter_cl_over = BridgeAdapter(api_key="dummy", transport=transport_cl_over)
    with pytest.raises(BridgeInvalidResponseError, match="Response exceeded maximum size"):
        await adapter_cl_over.preflight(monotonic() + 10.0)


@pytest.mark.anyio
async def test_no_retries() -> None:
    call_count = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(500)

    transport = create_mock_transport(handler)
    adapter = BridgeAdapter(api_key="dummy", transport=transport)

    with pytest.raises(BridgeUnavailableError):
        await adapter.preflight(monotonic() + 10.0)

    assert call_count == 1

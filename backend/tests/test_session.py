"""Contract tests for the local bootstrap and session boundary (T006)."""

import asyncio
import logging
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from backend.app import main as main_module
from backend.app.http import session as session_module
from backend.app.main import create_app
from backend.app.platform.config import AppSettings
from fastapi import FastAPI, Response
from httpx import ASGITransport, AsyncClient

BASE = "http://127.0.0.1:8000"
ORIGIN = {"Origin": BASE}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    now = [100.0]
    monkeypatch.setattr(session_module, "monotonic", lambda: now[0])
    return now


def error_code(response: object) -> str:
    from httpx import Response

    assert isinstance(response, Response)
    body = response.json()
    assert set(body) == {"error"}
    assert body["error"]["requestId"].startswith("req_")
    assert "token" not in body["error"]
    return str(body["error"]["code"])


@pytest.mark.anyio
async def test_exchange_once_sets_scoped_cookie_and_guards_openapi() -> None:
    app = create_app()
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client,
    ):
        token = app.state.sessions.issue_bootstrap_token()
        assert error_code(await client.get("/openapi.json")) == "SESSION_REQUIRED"
        assert error_code(await client.get("/docs")) == "SESSION_REQUIRED"
        assert (await client.get("/api/v1/health")).status_code == 200

        response = await client.post("/bootstrap/exchange", json={"token": token}, headers=ORIGIN)
        assert response.status_code == 204
        assert response.content == b""
        cookie = response.headers["set-cookie"]
        assert "HttpOnly" in cookie
        assert "SameSite=strict" in cookie
        assert "Path=/" in cookie
        assert "Secure" not in cookie  # This deployment uses plain HTTP on loopback.
        assert token not in str(response.headers)
        assert response.headers["referrer-policy"] == "no-referrer"
        assert response.headers["cache-control"] == "no-store"

        cookie_value = cookie.split(";", 1)[0]
        assert (
            await client.get("/openapi.json", headers={"Cookie": cookie_value})
        ).status_code == 200
        assert (
            await client.get("/openapi.json", headers={"Cookie": cookie_value})
        ).status_code == 200
        assert (
            error_code(
                await client.post("/bootstrap/exchange", json={"token": token}, headers=ORIGIN)
            )
            == "SESSION_INVALID"
        )


@pytest.mark.anyio
async def test_expiry_is_exclusive_and_refresh_never_extends_session(clock: list[float]) -> None:
    app = create_app()
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client,
    ):
        expired = app.state.sessions.issue_bootstrap_token()
        clock[0] = 160.0
        assert (
            error_code(
                await client.post("/bootstrap/exchange", json={"token": expired}, headers=ORIGIN)
            )
            == "SESSION_INVALID"
        )

        fresh = app.state.sessions.issue_bootstrap_token()
        clock[0] = 219.999
        response = await client.post("/bootstrap/exchange", json={"token": fresh}, headers=ORIGIN)
        assert response.status_code == 204
        cookie = response.headers["set-cookie"].split(";", 1)[0]
        clock[0] = 29019.998
        assert (await client.get("/openapi.json", headers={"Cookie": cookie})).status_code == 200
        clock[0] = 29019.999
        assert error_code(await client.get("/openapi.json", headers={"Cookie": cookie})) == (
            "SESSION_INVALID"
        )


@pytest.mark.anyio
async def test_concurrent_exchange_only_one_wins() -> None:
    app = create_app()
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client,
    ):
        token = app.state.sessions.issue_bootstrap_token()
        responses = await asyncio.gather(
            client.post("/bootstrap/exchange", json={"token": token}, headers=ORIGIN),
            client.post("/bootstrap/exchange", json={"token": token}, headers=ORIGIN),
        )
        assert sorted(response.status_code for response in responses) == [204, 401]
        assert error_code(
            next(response for response in responses if response.status_code == 401)
        ) == ("SESSION_INVALID")


@pytest.mark.anyio
async def test_two_tabs_share_cookie_but_restart_invalidates_it() -> None:
    first = create_app()
    async with (
        first.router.lifespan_context(first),
        AsyncClient(transport=ASGITransport(app=first), base_url=BASE) as client,
    ):
        token = first.state.sessions.issue_bootstrap_token()
        response = await client.post("/bootstrap/exchange", json={"token": token}, headers=ORIGIN)
        cookie = response.headers["set-cookie"].split(";", 1)[0]
        async with AsyncClient(transport=ASGITransport(app=first), base_url=BASE) as second_tab:
            assert (
                await second_tab.get("/openapi.json", headers={"Cookie": cookie})
            ).status_code == 200

    second = create_app()
    async with (
        second.router.lifespan_context(second),
        AsyncClient(transport=ASGITransport(app=second), base_url=BASE) as client,
    ):
        assert error_code(await client.get("/openapi.json", headers={"Cookie": cookie})) == (
            "SESSION_INVALID"
        )
        assert error_code(await client.get("/openapi.json")) == "SESSION_REQUIRED"


@pytest.mark.anyio
async def test_hostile_host_origin_and_preflight_are_denied() -> None:
    app = create_app(AppSettings(host="127.0.0.1", port=8000))
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client,
    ):
        token = app.state.sessions.issue_bootstrap_token()
        assert error_code(await client.get("/api/v1/health", headers={"Host": "evil.test"})) == (
            "ORIGIN_FORBIDDEN"
        )
        assert (
            error_code(
                await client.post(
                    "/bootstrap/exchange",
                    json={"token": token},
                    headers={"Origin": "http://evil.test"},
                )
            )
            == "ORIGIN_FORBIDDEN"
        )
        assert (
            error_code(await client.post("/bootstrap/exchange", json={"token": token}, headers={}))
            == "ORIGIN_FORBIDDEN"
        )
        assert (
            error_code(
                await client.post(
                    "/bootstrap/exchange",
                    json={"token": token},
                    headers={"Referer": "http://evil.test/page"},
                )
            )
            == "ORIGIN_FORBIDDEN"
        )
        assert (
            error_code(
                await client.options(
                    "/bootstrap/exchange",
                    headers={"Origin": "http://evil.test", "Access-Control-Request-Method": "POST"},
                )
            )
            == "ORIGIN_FORBIDDEN"
        )
        assert (
            await client.post("/bootstrap/exchange", json={"token": token}, headers=ORIGIN)
        ).status_code == 204


@pytest.mark.anyio
async def test_json_boundary_and_error_envelope_do_not_echo_token(
    caplog: pytest.LogCaptureFixture,
) -> None:
    app = create_app()
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client,
    ):
        token = app.state.sessions.issue_bootstrap_token()
        with caplog.at_level(logging.DEBUG):
            media = await client.post(
                "/bootstrap/exchange",
                content='{"token":"synthetic"}',
                headers={**ORIGIN, "Content-Type": "text/plain"},
            )
            assert error_code(media) == "VALIDATION_ERROR"
            malformed = await client.post(
                "/bootstrap/exchange",
                content="{",
                headers={**ORIGIN, "Content-Type": "application/json"},
            )
            assert error_code(malformed) == "MALFORMED_JSON"
            assert (
                error_code(
                    await client.post(
                        "/bootstrap/exchange", json={"token": token, "extra": 1}, headers=ORIGIN
                    )
                )
                == "VALIDATION_ERROR"
            )
            assert (
                error_code(await client.post("/bootstrap/exchange", json={}, headers=ORIGIN))
                == "VALIDATION_ERROR"
            )
            assert (
                error_code(
                    await client.post(
                        "/bootstrap/exchange", json={"token": "synthetic"}, headers=ORIGIN
                    )
                )
                == "SESSION_INVALID"
            )
        assert token not in caplog.text
        assert token not in str(media.content + malformed.content)
        extra_named_like_secret = await client.post(
            "/bootstrap/exchange", json={"token": token, token: "synthetic"}, headers=ORIGIN
        )
        assert error_code(extra_named_like_secret) == "VALIDATION_ERROR"
        assert token not in extra_named_like_secret.text


@pytest.mark.anyio
async def test_streamed_json_above_one_mib_is_rejected() -> None:
    app = create_app()

    async def oversized() -> AsyncIterator[bytes]:
        yield b'{"token":"'
        yield b"a" * 1_048_577
        yield b'"}'

    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client,
    ):
        response = await client.post(
            "/bootstrap/exchange",
            content=oversized(),
            headers={**ORIGIN, "Content-Type": "application/json"},
        )
        assert response.status_code == 413
        assert error_code(response) == "PAYLOAD_TOO_LARGE"


@pytest.mark.anyio
async def test_protected_mutation_requires_session_and_origin() -> None:
    app: FastAPI = create_app()

    @app.post("/api/v1/protected-probe")
    def protected_probe() -> dict[str, bool]:
        return {"ok": True}

    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client,
    ):
        assert (
            error_code(await client.post("/api/v1/protected-probe", json={}, headers=ORIGIN))
            == "SESSION_REQUIRED"
        )
        token = app.state.sessions.issue_bootstrap_token()
        response = await client.post("/bootstrap/exchange", json={"token": token}, headers=ORIGIN)
        cookie = response.headers["set-cookie"].split(";", 1)[0]
        assert (
            error_code(
                await client.post("/api/v1/protected-probe", json={}, headers={"Cookie": cookie})
            )
            == "ORIGIN_FORBIDDEN"
        )
        assert (
            await client.post(
                "/api/v1/protected-probe", json={}, headers={**ORIGIN, "Cookie": cookie}
            )
        ).json() == {"ok": True}


@pytest.mark.anyio
async def test_bodyless_delete_keeps_origin_guard() -> None:
    app = create_app()

    @app.delete("/api/v1/delete-probe")
    def delete_probe() -> Response:
        return Response(status_code=204)

    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client,
    ):
        token = app.state.sessions.issue_bootstrap_token()
        exchanged = await client.post("/bootstrap/exchange", json={"token": token}, headers=ORIGIN)
        cookie = exchanged.headers["set-cookie"].split(";", 1)[0]
        response = await client.delete("/api/v1/delete-probe", headers={**ORIGIN, "Cookie": cookie})
        assert response.status_code == 204
        denied = await client.delete("/api/v1/delete-probe", headers={"Cookie": cookie})
        assert error_code(denied) == "ORIGIN_FORBIDDEN"


@pytest.mark.anyio
async def test_same_origin_shell_refresh_and_static_asset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html>synthetic-shell</html>", encoding="utf-8")
    (tmp_path / "bootstrap.html").write_text("<html>synthetic-bootstrap</html>", encoding="utf-8")
    (tmp_path / "assets" / "app.js").write_text("synthetic-app", encoding="utf-8")
    monkeypatch.setattr(main_module, "STATIC_ROOT", tmp_path)
    app = create_app()
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client,
    ):
        bootstrap = await client.get("/bootstrap")
        assert bootstrap.status_code == 200
        assert "synthetic-bootstrap" in bootstrap.text
        assert "synthetic-shell" not in bootstrap.text
        assert bootstrap.headers["referrer-policy"] == "no-referrer"
        assert error_code(await client.get("/lookup")) == "SESSION_REQUIRED"
        token = app.state.sessions.issue_bootstrap_token()
        exchanged = await client.post("/bootstrap/exchange", json={"token": token}, headers=ORIGIN)
        cookie = exchanged.headers["set-cookie"].split(";", 1)[0]
        for route in ("/", "/lookup", "/status", "/word-forms/wf_1", "/quiz/attempt_1/result"):
            response = await client.get(route, headers={"Cookie": cookie})
            assert response.status_code == 200
            assert "synthetic-shell" in response.text
            assert response.headers["cache-control"] == "no-store"
        assert (await client.get("/assets/app.js")).text == "synthetic-app"
        assert error_code(await client.get("/unknown", headers={"Cookie": cookie})) == "NOT_FOUND"


@pytest.mark.anyio
async def test_json_cap_accepts_exact_bytes_and_rejects_max_plus_one() -> None:
    app = create_app()

    @app.post("/api/v1/size-probe")
    def size_probe() -> Response:
        return Response(status_code=204)

    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client,
    ):
        token = app.state.sessions.issue_bootstrap_token()
        exchanged = await client.post("/bootstrap/exchange", json={"token": token}, headers=ORIGIN)
        cookie = exchanged.headers["set-cookie"].split(";", 1)[0]
        prefix, suffix = b'{"padding":"', b'"}'
        payload = prefix + b"a" * (1_048_576 - len(prefix) - len(suffix)) + suffix
        headers = {**ORIGIN, "Cookie": cookie, "Content-Type": "application/json"}
        assert len(payload) == 1_048_576
        assert (
            await client.post("/api/v1/size-probe", content=payload, headers=headers)
        ).status_code == 204
        too_large = await client.post("/api/v1/size-probe", content=payload + b" ", headers=headers)
        assert error_code(too_large) == "PAYLOAD_TOO_LARGE"

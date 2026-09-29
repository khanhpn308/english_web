"""Tests for FastAPI app factory and health endpoint (T003)."""

from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from backend.app.http.health import get_settings
from backend.app.main import create_app
from backend.app.platform.config import AppSettings
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from starlette.requests import Request


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def temp_storage_path(tmp_path: Path) -> Path:
    storage_file = tmp_path / "vocabularies.db"
    storage_file.touch()
    return storage_file


@pytest.mark.anyio
async def test_loopback_healthy_fixture(temp_storage_path: Path) -> None:
    settings = AppSettings(
        host="127.0.0.1",
        port=8000,
        app_version="0.1.0",
        storage_path=temp_storage_path,
    )
    app = create_app(settings)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.headers.get("cache-control") == "no-store"

    data = response.json()
    assert data["status"] == "OK"
    assert data["version"] == "0.1.0"
    assert data["storageStatus"] == "OK"
    assert data["bridgeStatus"] == "NOT_CHECKED"
    assert data["readiness"] is True


@pytest.mark.anyio
async def test_missing_storage_not_ready(tmp_path: Path) -> None:
    missing_path = tmp_path / "non_existent" / "vocabularies.db"
    settings = AppSettings(
        host="127.0.0.1",
        port=8000,
        app_version="0.1.0",
        storage_path=missing_path,
    )
    app = create_app(settings)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.headers.get("cache-control") == "no-store"

    data = response.json()
    assert data["status"] == "NOT_READY"
    assert data["version"] == "0.1.0"
    assert data["storageStatus"] == "NOT_READY"
    assert data["bridgeStatus"] == "NOT_CHECKED"
    assert data["readiness"] is False


@pytest.mark.anyio
async def test_none_storage_not_ready() -> None:
    settings = AppSettings(
        host="127.0.0.1",
        port=8000,
        app_version="0.1.0",
        storage_path=None,
    )
    app = create_app(settings)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.headers.get("cache-control") == "no-store"

    data = response.json()
    assert data["status"] == "NOT_READY"
    assert data["storageStatus"] == "NOT_READY"
    assert data["readiness"] is False


@pytest.mark.anyio
async def test_default_app_factory_and_fallback() -> None:
    app = create_app()
    assert isinstance(app.state.settings, AppSettings)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as client:
        response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "NOT_READY"

    # Test get_settings fallback when state.settings is not AppSettings
    req = Request(scope={"type": "http", "app": app})
    req.app.state.settings = None
    fallback_settings = get_settings(req)
    assert isinstance(fallback_settings, AppSettings)


def test_invalid_bind_rejected() -> None:
    # 0.0.0.0 is not loopback
    with pytest.raises(ValidationError):
        AppSettings(host="0.0.0.0")

    # LAN IP is not loopback
    with pytest.raises(ValidationError):
        AppSettings(host="192.168.1.50")

    # External domain is not loopback
    with pytest.raises(ValidationError):
        AppSettings(host="api.example.com")


def test_valid_loopback_hosts_accepted() -> None:
    s1 = AppSettings(host="127.0.0.1")
    assert s1.host == "127.0.0.1"

    s2 = AppSettings(host="localhost")
    assert s2.host == "localhost"

    s3 = AppSettings(host="::1")
    assert s3.host == "::1"


@pytest.mark.anyio
async def test_count_bridge_calls_zero(temp_storage_path: Path) -> None:
    settings = AppSettings(
        host="127.0.0.1",
        storage_path=temp_storage_path,
        bridge_url="http://127.0.0.1:8045/v1",
    )
    app = create_app(settings)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as client:
        with (
            patch.object(httpx, "AsyncClient") as mock_async_client,
            patch.object(httpx, "Client") as mock_sync_client,
        ):
            response = await client.get("/api/v1/health")

            assert response.status_code == 200
            assert mock_async_client.call_count == 0
            assert mock_sync_client.call_count == 0


@pytest.mark.anyio
async def test_asgi_startup_shutdown_lifespan(temp_storage_path: Path) -> None:
    settings = AppSettings(
        host="127.0.0.1",
        storage_path=temp_storage_path,
    )
    app = create_app(settings)

    # Lifespan startup and shutdown execution
    async with app.router.lifespan_context(app):
        assert getattr(app.state, "ready", False) is True

    assert getattr(app.state, "ready", False) is False

"""Tests for FastAPI app factory and health endpoint (T003)."""

import sqlite3
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from backend.app.http.health import get_settings
from backend.app.main import create_app
from backend.app.persistence.database import Database
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
    database = Database(storage_file)
    try:
        database.initialize()
    finally:
        database.close()
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
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as client,
    ):
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
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as client,
    ):
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
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as client,
    ):
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
            async with app.router.lifespan_context(app):
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
        database = app.state.database
        assert isinstance(database, Database)
        assert app.state.storage_info.schema_revision == "0002_operations"

    assert getattr(app.state, "ready", False) is False
    assert app.state.database is None


@pytest.mark.anyio
async def test_health_requires_lifespan_and_shutdown_clears_readiness(tmp_path: Path) -> None:
    path = tmp_path / "fresh.db"
    app = create_app(AppSettings(storage_path=path))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as client:
        assert (await client.get("/api/v1/health")).json()["readiness"] is False
        assert not path.exists()
        async with app.router.lifespan_context(app):
            response = await client.get("/api/v1/health")
            assert response.status_code == 200
            assert response.json()["readiness"] is True
            assert response.json()["storageStatus"] == "OK"
            assert path.is_file()
        assert (await client.get("/api/v1/health")).json()["readiness"] is False


@pytest.mark.anyio
@pytest.mark.parametrize("failure", ["corrupt", "readonly", "schema_mismatch"])
async def test_storage_failure_never_reports_ready_or_exposes_contents(
    tmp_path: Path, failure: str
) -> None:
    path = tmp_path / "invalid.db"
    if failure == "corrupt":
        path.write_bytes(b"synthetic-private-history-not-a-sqlite-db")
    elif failure == "readonly":
        database = Database(path)
        database.initialize()
        database.close()
        path.chmod(0o444)
    else:
        with sqlite3.connect(path) as connection:
            connection.execute("CREATE TABLE history (id INTEGER)")
            connection.execute("INSERT INTO history VALUES (1)")
    before = path.read_bytes()
    app = create_app(AppSettings(storage_path=path))
    try:
        async with (
            app.router.lifespan_context(app),
            AsyncClient(transport=ASGITransport(app=app), base_url="http://127.0.0.1") as client,
        ):
            response = await client.get("/api/v1/health")
            assert response.status_code == 200
            assert response.headers["cache-control"] == "no-store"
            assert response.json() == {
                "status": "NOT_READY",
                "version": "0.1.0",
                "storageStatus": "NOT_READY",
                "bridgeStatus": "NOT_CHECKED",
                "readiness": False,
            }
            assert app.state.ready is False
        assert path.read_bytes() == before
    finally:
        path.chmod(0o600)


@pytest.mark.anyio
async def test_shutdown_disposes_database_engine(temp_storage_path: Path) -> None:
    app = create_app(AppSettings(storage_path=temp_storage_path))
    with patch.object(Database, "close", autospec=True, side_effect=Database.close) as close:
        async with app.router.lifespan_context(app):
            assert app.state.ready is True
            assert close.call_count == 0
        assert close.call_count == 1
        assert app.state.storage_info is None

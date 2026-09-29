"""FastAPI application factory and ASGI entrypoint (T003)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from backend.app.http.health import router as health_router
from backend.app.persistence.database import Database, StorageError
from backend.app.platform.config import AppSettings
from fastapi import FastAPI
from starlette.concurrency import run_in_threadpool


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Keep readiness false until storage checks and migrations finish."""
    settings: AppSettings = app.state.settings
    database = Database(settings.storage_path) if settings.storage_path is not None else None
    app.state.database = database
    app.state.ready = False
    app.state.storage_info = None
    app.state.storage_error = None
    try:
        if database is not None:
            try:
                # Blocking SQLite work runs outside the lifespan's event loop.
                # Sources: https://fastapi.tiangolo.com/advanced/events/
                # https://www.starlette.dev/threadpool/
                app.state.storage_info = await run_in_threadpool(database.initialize)
                app.state.ready = True
            except StorageError as error:
                app.state.storage_error = str(error)
        yield
    finally:
        app.state.ready = False
        app.state.storage_info = None
        if database is not None:
            await run_in_threadpool(database.close)
        app.state.database = None


def create_app(settings: AppSettings | None = None) -> FastAPI:
    """Create and configure a FastAPI application instance."""
    app_settings = settings or AppSettings()

    app = FastAPI(
        title="Vocabulary Learning App",
        version=app_settings.app_version,
        lifespan=lifespan,
    )

    app.state.settings = app_settings
    app.state.ready = False
    app.state.database = None
    app.state.storage_info = None
    app.state.storage_error = None

    app.include_router(health_router)

    return app


# Default app instance for ASGI servers
app = create_app()

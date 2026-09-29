"""FastAPI application factory and ASGI entrypoint (T003)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from backend.app.http.health import router as health_router
from backend.app.platform.config import AppSettings
from fastapi import FastAPI


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown lifecycle."""
    app.state.ready = True
    try:
        yield
    finally:
        app.state.ready = False


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

    app.include_router(health_router)

    return app


# Default app instance for ASGI servers
app = create_app()

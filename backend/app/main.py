"""FastAPI application factory and ASGI entrypoint (T003)."""

import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from backend.app.application.operations import OperationLedger
from backend.app.http.bootstrap import router as bootstrap_router
from backend.app.http.errors import error_response
from backend.app.http.health import router as health_router
from backend.app.http.operations import router as operations_router
from backend.app.http.session import SessionGuard, SessionStore
from backend.app.persistence.database import Database, StorageError
from backend.app.platform.config import AppSettings
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse

STATIC_ROOT = Path(__file__).resolve().parents[2] / "frontend" / "dist"
_SHELL_ROUTES = {"", "lookup", "search", "review", "quiz/new", "status"}
_DETAIL_ROUTES = re.compile(r"(?:word-forms/[^/]+|quiz/[^/]+(?:/result)?)\Z")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Keep readiness false until storage checks and migrations finish."""
    settings: AppSettings = app.state.settings
    database = Database(settings.storage_path) if settings.storage_path is not None else None
    app.state.database = database
    app.state.ready = False
    app.state.storage_info = None
    app.state.storage_error = None
    app.state.operation_ledger = None
    app.state.sessions.activate()
    try:
        if database is not None:
            try:
                # Blocking SQLite work runs outside the lifespan's event loop.
                # Sources: https://fastapi.tiangolo.com/advanced/events/
                # https://www.starlette.dev/threadpool/
                app.state.storage_info = await run_in_threadpool(database.initialize)
                ledger = OperationLedger(database.engine)
                await run_in_threadpool(ledger.recover_pending)
                app.state.operation_ledger = ledger
                app.state.ready = True
            except StorageError as error:
                app.state.storage_error = str(error)
            except SQLAlchemyError:
                app.state.storage_error = "UNAVAILABLE"
        yield
    finally:
        app.state.sessions.invalidate()
        app.state.ready = False
        app.state.storage_info = None
        app.state.operation_ledger = None
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
    app.state.operation_ledger = None
    app.state.sessions = SessionStore()

    # FastAPI middleware runs before route handlers, including the generated OpenAPI route.
    # Source: https://fastapi.tiangolo.com/tutorial/middleware/
    app.add_middleware(SessionGuard, settings=app_settings, sessions=app.state.sessions)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        # FastAPI error objects include input; expose only field and error type.
        if any(error["type"] == "json_invalid" for error in exc.errors()):
            return error_response(400, "MALFORMED_JSON")
        return error_response(
            422,
            "VALIDATION_ERROR",
            {"kind": "FIELD_ERRORS", "fields": [{"field": "body", "reason": "invalid"}]},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        if exc.status_code == 404:
            return error_response(404, "NOT_FOUND")
        return error_response(exc.status_code, "VALIDATION_ERROR")

    app.include_router(health_router)
    app.include_router(bootstrap_router)
    app.include_router(operations_router)

    # The trusted bootstrap entry is built separately by T066; never serve the main app here.
    @app.get("/bootstrap", include_in_schema=False)
    def bootstrap_page() -> Response:
        page = STATIC_ROOT / "bootstrap.html"
        if not page.is_file():
            return error_response(503, "CONFIGURATION_REQUIRED")
        return FileResponse(page)

    asset_dir = STATIC_ROOT / "assets"
    if asset_dir.is_dir():
        # Source: https://fastapi.tiangolo.com/tutorial/static-files/
        app.mount("/assets", StaticFiles(directory=asset_dir), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def app_shell(full_path: str) -> Response:
        if full_path not in _SHELL_ROUTES and _DETAIL_ROUTES.fullmatch(full_path) is None:
            return error_response(404, "NOT_FOUND")
        page = STATIC_ROOT / "index.html"
        if not page.is_file():
            return error_response(503, "CONFIGURATION_REQUIRED")
        return FileResponse(page)

    return app


# Default app instance for ASGI servers
app = create_app()

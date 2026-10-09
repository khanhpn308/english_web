"""FastAPI application factory and ASGI entrypoint (T003)."""

import asyncio
import re
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from secrets import token_bytes
from time import monotonic

from backend.app.adapters.bridge import BridgeAdapter
from backend.app.adapters.source_files import SourceFileAdapter, SourceFileError
from backend.app.adapters.watcher import SourceWatcher
from backend.app.application.ai_admission import AiAdmissionCoordinator
from backend.app.application.consent import ConsentService
from backend.app.application.create_quiz import CreateQuizService
from backend.app.application.edit_word_form import EditWordFormService
from backend.app.application.operations import OperationConflict, OperationLedger
from backend.app.application.save_answer import SaveAnswerService
from backend.app.application.save_word_family import SaveWordFamilyService
from backend.app.application.source_recovery import SourceRecovery
from backend.app.application.source_write import SourceWriteCoordinator
from backend.app.application.sync import SyncService
from backend.app.enrichment.lookup import LookupService
from backend.app.http.bootstrap import router as bootstrap_router
from backend.app.http.errors import error_response
from backend.app.http.health import router as health_router
from backend.app.http.lookups import router as lookups_router
from backend.app.http.operations import router as operations_router
from backend.app.http.quiz import router as quiz_router
from backend.app.http.quiz_answers import router as quiz_answers_router
from backend.app.http.review import router as review_router
from backend.app.http.search import router as search_router
from backend.app.http.session import SessionGuard, SessionStore
from backend.app.http.sources import router as sources_router
from backend.app.http.word_forms import router as word_forms_router
from backend.app.persistence.database import Database, StorageError
from backend.app.platform.config import AppSettings
from backend.app.review.queue import ReviewService
from backend.app.vocabulary.models import SourceFile
from backend.app.vocabulary.repository import VocabularyRepository
from backend.app.vocabulary.search_service import SearchService
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

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
    app.state.consent_service = None
    app.state.search_service = None
    app.state.review_service = None
    app.state.sync_service = None
    app.state.watcher = None
    app.state.lookup_service = None
    app.state.save_word_family_service = None
    app.state.edit_word_form_service = None
    app.state.quiz_service = None
    app.state.answer_service = None
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
                app.state.answer_service = SaveAnswerService(ledger)
                app.state.consent_service = ConsentService(ledger)
                app.state.search_service = SearchService(
                    database.engine, signing_key=app.state.cursor_signing_key
                )
                app.state.review_service = ReviewService(
                    database.engine,
                    signing_key=app.state.cursor_signing_key,
                    ledger=ledger,
                    conflict_type=OperationConflict,
                )
                admission_coordinator = AiAdmissionCoordinator(
                    app.state.consent_service,
                    BridgeAdapter(api_key=None),
                    lambda: app.state.active_ai_policy,
                )
                app.state.lookup_service = LookupService(
                    ledger,
                    admission_coordinator,
                    VocabularyRepository(database.engine),
                )
                app.state.quiz_service = CreateQuizService(
                    ledger,
                    admission_coordinator,
                    VocabularyRepository(database.engine),
                )

                markdown_root = app.state.markdown_root
                if markdown_root is not None:
                    adapter = SourceFileAdapter(markdown_root)
                    with database.engine.connect() as conn:
                        rows = (
                            conn.exec_driver_sql(
                                "SELECT id, relative_path, note_date, status, revision, etag, "
                                "content_hash, last_parsed_at, error_code, created_at, updated_at "
                                "FROM source_files"
                            )
                            .mappings()
                            .all()
                        )
                    for r in rows:
                        adapter.register_source(
                            SourceFile(
                                id=str(r["id"]),
                                relative_path=str(r["relative_path"]),
                                note_date=str(r["note_date"]),
                                status=r["status"],
                                revision=int(r["revision"]),
                                etag=str(r["etag"]),
                                content_hash=str(r["content_hash"])
                                if r["content_hash"] is not None
                                else None,
                                last_parsed_at=str(r["last_parsed_at"])
                                if r["last_parsed_at"] is not None
                                else None,
                                error_code=str(r["error_code"])
                                if r["error_code"] is not None
                                else None,
                                created_at=str(r["created_at"]),
                                updated_at=str(r["updated_at"]),
                            )
                        )

                    coordinator = SourceWriteCoordinator(database.engine, adapter)
                    recovery = SourceRecovery(coordinator)
                    reconciled = await run_in_threadpool(
                        recovery.reconcile, operation_ledger=ledger
                    )
                    with database.engine.connect() as conn:
                        degraded_count: int = conn.exec_driver_sql(
                            "SELECT count(*) FROM source_write_journal WHERE state = 'DEGRADED'"
                        ).scalar_one()
                    is_degraded = degraded_count > 0 or any(
                        r.state == "DEGRADED" for r in reconciled
                    )
                    if is_degraded:
                        app.state.storage_error = "DEGRADED"
                        app.state.ready = False
                    else:
                        app.state.save_word_family_service = SaveWordFamilyService(ledger, coordinator)
                        app.state.edit_word_form_service = EditWordFormService(ledger, coordinator)
                        sync_service = SyncService(
                            database.engine, markdown_root, operation_ledger=ledger
                        )
                        app.state.sync_service = sync_service

                        startup_in_progress = True
                        queued_watcher_batches: list[list[str]] = []
                        watcher_lock = threading.Lock()

                        def _on_source_change(paths: list[str]) -> None:
                            with watcher_lock:
                                if startup_in_progress:
                                    queued_watcher_batches.append(paths)
                                    return
                            res = sync_service.sync(reason="WATCHER")
                            if res.status == "FAILED":
                                app.state.storage_error = "WATCHER_SYNC_FAILED"
                                app.state.ready = False

                        def _on_watcher_error(_batch: list[str], _exc: Exception) -> None:
                            app.state.storage_error = "WATCHER_FAILED"
                            app.state.ready = False

                        watcher = SourceWatcher(
                            markdown_root,
                            on_change=_on_source_change,
                            on_error=_on_watcher_error,
                        )
                        watcher.start()
                        app.state.watcher = watcher

                        try:
                            startup_res = await run_in_threadpool(
                                sync_service.sync, reason="STARTUP"
                            )
                        except Exception:
                            app.state.storage_error = "STARTUP_SYNC_FAILED"
                            app.state.ready = False
                            await run_in_threadpool(watcher.stop)
                            app.state.watcher = None
                            raise

                        if startup_res.status == "FAILED":
                            app.state.storage_error = "STARTUP_SYNC_FAILED"
                            app.state.ready = False
                            await run_in_threadpool(watcher.stop)
                            app.state.watcher = None
                        else:
                            with watcher_lock:
                                startup_in_progress = False
                                pending_paths = sorted(
                                    {p for b in queued_watcher_batches for p in b}
                                )
                                queued_watcher_batches.clear()

                            poll_changes = await run_in_threadpool(watcher.poll_now)
                            if pending_paths or poll_changes:
                                watcher_res = await run_in_threadpool(
                                    sync_service.sync, reason="WATCHER"
                                )
                                if watcher_res.status == "FAILED":
                                    app.state.storage_error = "WATCHER_SYNC_FAILED"
                                    app.state.ready = False
                                else:
                                    app.state.ready = True
                            else:
                                app.state.ready = True
                else:
                    app.state.ready = True
            except StorageError as error:
                app.state.storage_error = str(error)
                app.state.ready = False
            except SQLAlchemyError:
                app.state.storage_error = "UNAVAILABLE"
                app.state.ready = False
            except SourceFileError:
                app.state.storage_error = "SOURCE_UNAVAILABLE"
                app.state.ready = False
            except Exception:
                app.state.storage_error = "STARTUP_FAILED"
                app.state.ready = False
        yield
    finally:
        try:
            if getattr(app.state, "watcher", None) is not None:
                await run_in_threadpool(app.state.watcher.stop)
                app.state.watcher = None
        finally:
            try:
                lookup_service = app.state.lookup_service
                if lookup_service is not None:
                    await lookup_service.drain()
            finally:
                try:
                    quiz_service = app.state.quiz_service
                    if quiz_service is not None:
                        await quiz_service.drain()
                finally:
                    app.state.sessions.invalidate()
                    app.state.ready = False
                    app.state.storage_info = None
                    app.state.operation_ledger = None
                    app.state.consent_service = None
                    app.state.search_service = None
                    app.state.review_service = None
                    app.state.sync_service = None
                    app.state.lookup_service = None
                    app.state.save_word_family_service = None
                    app.state.edit_word_form_service = None
                    app.state.quiz_service = None
                    app.state.answer_service = None
                    if database is not None:
                        await run_in_threadpool(database.close)
                    app.state.database = None


class RequestBudgetMiddleware:
    """Start AI budgets before SessionGuard body buffering or parsing (T008/T035)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            app = scope.get("app")
            clock = None
            if app is not None and hasattr(app, "state"):
                service_name = (
                    "quiz_service"
                    if scope.get("path") == "/api/v1/quiz-attempts"
                    else "lookup_service"
                )
                service = getattr(app.state, service_name, None)
                if service is not None:
                    clock = getattr(service, "clock", None)
                if clock is None:
                    clock = getattr(app.state, "clock", None)
            if clock is None:
                clock = monotonic
            scope.setdefault("state", {})["request_start_time"] = clock()
        if (
            scope["type"] == "http"
            and scope.get("method") == "POST"
            and scope.get("path") in {"/api/v1/lookups", "/api/v1/quiz-attempts"}
        ):
            from backend.app.application import create_quiz as quiz_module
            from backend.app.enrichment import lookup as lookup_module

            budget_clock = clock or monotonic
            budget = (
                quiz_module.QUIZ_DEADLINE_SECONDS
                if scope["path"] == "/api/v1/quiz-attempts"
                else lookup_module.LOOKUP_DEADLINE_SECONDS
            )
            deadline = scope["state"]["request_start_time"] + budget
            response_started = False

            async def bounded_receive() -> Message:
                remaining = deadline - budget_clock()
                if remaining <= 0:
                    raise TimeoutError("AI request body deadline exhausted")
                async with asyncio.timeout(remaining):
                    return await receive()

            async def bounded_send(message: Message) -> None:
                nonlocal response_started
                if message["type"] == "http.response.start":
                    if (
                        scope["path"] == "/api/v1/quiz-attempts"
                        and 200 <= message["status"] < 300
                        and budget_clock() >= deadline
                    ):
                        raise TimeoutError("Quiz HTTP success deadline exhausted")
                    response_started = True
                await send(message)

            try:
                await self.app(scope, bounded_receive, bounded_send)
            except TimeoutError:
                if response_started:
                    raise
                operation_id = scope["state"].get("quiz_operation_id")
                details = (
                    {"kind": "RETRY", "operationId": operation_id}
                    if operation_id is not None else None
                )
                response = error_response(503, "BRIDGE_UNAVAILABLE", details)
                # Quiz body timeouts escape the current lookup-specific catch in
                # SessionGuard. Apply its response protections at this outer edge.
                response.headers.update(
                    {
                        "Content-Security-Policy": (
                            "default-src 'self'; script-src 'self'; connect-src 'self'; "
                            "object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
                        ),
                        "X-Content-Type-Options": "nosniff",
                        "X-Frame-Options": "DENY",
                        "Referrer-Policy": "no-referrer",
                        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
                        "Cache-Control": "no-store",
                    }
                )
                await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


def create_app(
    settings: AppSettings | None = None,
    *,
    markdown_root: Path | None = None,
) -> FastAPI:
    """Create and configure a FastAPI application instance."""
    app_settings = settings or AppSettings()

    app = FastAPI(
        title="Vocabulary Learning App",
        version=app_settings.app_version,
        lifespan=lifespan,
    )

    app.state.settings = app_settings
    app.state.markdown_root = markdown_root
    app.state.ready = False
    app.state.database = None
    app.state.storage_info = None
    app.state.storage_error = None
    app.state.operation_ledger = None
    app.state.consent_service = None
    app.state.search_service = None
    app.state.review_service = None
    app.state.cursor_signing_key = token_bytes(32)
    app.state.sync_service = None
    app.state.watcher = None
    app.state.lookup_service = None
    app.state.save_word_family_service = None
    app.state.edit_word_form_service = None
    app.state.quiz_service = None
    app.state.active_ai_policy = None
    app.state.answer_service = None
    app.state.sessions = SessionStore()

    # FastAPI middleware runs before route handlers, including the generated OpenAPI route.
    # Source: https://fastapi.tiangolo.com/tutorial/middleware/
    app.add_middleware(SessionGuard, settings=app_settings, sessions=app.state.sessions)
    app.add_middleware(RequestBudgetMiddleware)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        if request.method == "POST" and request.url.path == "/api/v1/quiz-attempts":
            service = request.app.state.quiz_service
            clock = service.clock if service is not None else monotonic
            start = getattr(request.state, "request_start_time", clock())
            from backend.app.application import create_quiz as quiz_module

            if clock() >= start + quiz_module.QUIZ_DEADLINE_SECONDS:
                return error_response(503, "BRIDGE_UNAVAILABLE")
        # FastAPI error objects include input; expose only field and error type.
        if request.url.path != "/api/v1/ai-consent" and any(
            error["type"] == "json_invalid" for error in exc.errors()
        ):
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
    app.include_router(search_router)
    app.include_router(review_router)
    app.include_router(sources_router)
    app.include_router(lookups_router)
    app.include_router(word_forms_router)
    app.include_router(quiz_router)
    app.include_router(quiz_answers_router)

    from backend.app.http.consent import router as consent_router

    app.include_router(consent_router)

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

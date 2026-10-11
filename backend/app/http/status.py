"""Read-only operational observations through the production session boundary."""

import stat
from datetime import datetime
from html import escape
from pathlib import Path
from time import monotonic
from typing import Annotated, Literal

from backend.app.application.consent import ConsentSnapshot, ConsentState, PolicyVersion
from backend.app.application.sync import SyncService
from backend.app.http.consent import reject_read_body
from backend.app.http.errors import error_response
from backend.app.http.health import BridgeStatus, StorageStatus
from backend.app.persistence.database import StorageError, read_only_observation
from backend.app.platform.alerts import Category, LocalAlerts, Severity
from backend.app.platform.metrics import MetricsUnavailable
from backend.app.platform.telemetry import request_id
from backend.app.vocabulary.search_index import PROJECTION_VERSION
from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import HTMLResponse, JSONResponse

Readiness = Literal["NOT_READY", "SYNCING", "READY", "DEGRADED", "UNKNOWN"]
OperationalStorageStatus = StorageStatus | Literal[
    "BUSY", "READ_ONLY", "INTEGRITY_FAILED", "SCHEMA_MISMATCH", "UNAVAILABLE", "UNKNOWN",
]
RunbookId = Literal[
    "api-unavailable", "api-error-rate", "search-performance", "bridge-failure",
    "storage-integrity", "source-sync", "first-run-and-restore",
]
_RUNBOOK_ROOT = Path(__file__).resolve().parents[3] / "docs" / "runbooks"
_RUNBOOK_IDS: tuple[RunbookId, ...] = (
    "api-unavailable", "api-error-rate", "search-performance", "bridge-failure",
    "storage-integrity", "source-sync", "first-run-and-restore",
)
_RUNBOOKS = {identifier: _RUNBOOK_ROOT / f"{identifier}.md" for identifier in _RUNBOOK_IDS}
AlertObservation = Literal["MEASURED", "NO_DATA", "INCOMPLETE"]
_ALERT_SUMMARIES: dict[Category, str] = {
    "api_unavailable": "Use the Windows launcher for two consecutive failed health probes; preserve the database.",
    "api_error_rate": "Inspect local request IDs and storage/configuration failures; preserve data before restarting.",
    "search_latency": "Requires the approved benchmark fixture; ordinary API timing does not establish search performance.",
    "bridge_failure": "Inspect bridge timeout/auth/quota/validation failures; local search and review remain independent.",
    "storage_contention": "Preserve the draft, reconcile the existing operation, and retry only with bounded backoff.",
    "source_parse_failure": "Repair invalid sources explicitly, then sync; valid sources and learning history remain available.",
    "integrity_failure": "Stop destructive writes, preserve the original database, and follow staged recovery.",
}


class LocalAlert(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    category: Category
    severity: Severity
    state: Literal["ACTIVE", "RESOLVED", "INACTIVE", "UNKNOWN"]
    observation: AlertObservation
    startedAt: datetime | None
    updatedAt: datetime | None
    sampleCount: int = Field(ge=0, le=16384)
    runbookId: RunbookId
    summary: str = Field(max_length=240)


class LocalAlertSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    diagnosticsDegraded: bool
    items: list[LocalAlert] = Field(min_length=7, max_length=7)


class SourceCounts(BaseModel):
    model_config = ConfigDict(extra="forbid")
    VALID: int = Field(ge=0)
    INVALID: int = Field(ge=0)
    MISSING: int = Field(ge=0)


class OfflineCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")
    search: bool | None
    review: bool | None
    dashboard: bool | None
    createdQuiz: bool | None
    lookup: Literal[False]
    newQuiz: Literal[False]
    feedback: Literal[False]
    audio: bool | None


class LocalMetricsSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    requestErrorRate: float | None = Field(ge=0, le=1)
    p50Ms: float | None = Field(ge=0)
    p95Ms: float | None = Field(ge=0)
    p99Ms: float | None = Field(ge=0)
    sampledAt: datetime | None


class StatusSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    readiness: Readiness
    appVersion: str
    uptimeSeconds: float | None = Field(ge=0)
    storageStatus: OperationalStorageStatus
    schemaRevision: str | None = Field(max_length=80)
    sourceCounts: SourceCounts | None
    bridgeStatus: BridgeStatus
    selectedModelFamily: Literal["gemini-3.8-flash-high"] | None
    searchIndexStatus: Literal["READY", "NOT_READY", "UNAVAILABLE", "UNKNOWN"]
    lastSyncAt: datetime | None
    lastSyncDurationMs: float | None = Field(ge=0)
    lastIntegrityCheckAt: datetime | None
    sqliteFileSizeBytes: int | None = Field(ge=0)
    sqliteBusyCount: int | None = Field(ge=0)
    offlineCapabilities: OfflineCapabilities
    consentState: ConsentState | Literal["UNKNOWN"]
    policyVersion: PolicyVersion | None
    localMetrics: LocalMetricsSummary
    localAlerts: LocalAlertSummary | None
    requestId: str


class StatusError(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: Literal[
        "VALIDATION_ERROR", "SESSION_REQUIRED", "SESSION_INVALID", "ORIGIN_FORBIDDEN",
        "PAYLOAD_TOO_LARGE", "CONFIGURATION_REQUIRED", "INTERNAL_ERROR",
    ]
    message: str
    requestId: str


class StatusErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    error: StatusError


router = APIRouter(prefix="/api/v1", tags=["status"])


@router.get(
    "/runbooks/{runbookId}", response_class=HTMLResponse, response_model=None,
    responses={
        code: {"content": {"application/json": {
            "schema": {"$ref": "#/components/schemas/StatusErrorResponse"},
        }}} for code in (401, 403, 413, 422, 500, 503)
    },
)
def get_runbook(
    runbookId: RunbookId, request: Request,
    _body: Annotated[None, Depends(reject_read_body)],
) -> Response:
    """Serve only trusted, escaped bundled documents through SessionGuard."""
    if request.query_params:
        return error_response(422, "VALIDATION_ERROR")
    try:
        path = _RUNBOOKS[runbookId]
        info = path.stat()
        if (
            path.is_symlink() or path.resolve().parent != _RUNBOOK_ROOT
            or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
            or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
        ):
            return error_response(503, "CONFIGURATION_REQUIRED")
        with path.open("rb") as stream:
            content = stream.read(65537)
        if len(content) > 65536:
            return error_response(503, "CONFIGURATION_REQUIRED")
        paragraphs = "".join(
            f"<p>{escape(line)}</p>" for line in content.decode("utf-8").splitlines() if line
        )
    except (OSError, UnicodeError):
        return error_response(503, "CONFIGURATION_REQUIRED")
    except Exception:
        return error_response(500, "INTERNAL_ERROR")
    links = "".join(
        f'<li><a href="/api/v1/runbooks/{identifier}">{identifier}</a></li>'
        for identifier in _RUNBOOKS
    )
    return HTMLResponse(
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<title>Runbook: {runbookId}</title></head><body><main><h1>{runbookId}</h1>'
        f'<a href="/status">Back to status</a><article>{paragraphs}</article>'
        f'<nav aria-label="Local runbooks"><ul>{links}</ul></nav></main></body></html>',
        headers={"Cache-Control": "no-store"},
    )


def _observe_alerts(engine: LocalAlerts | None) -> LocalAlertSummary | None:
    if engine is None:
        return None
    try:
        # shortcut: idle expiry waits for observations/Status; add a tick if push is required.
        evaluation = engine.evaluate()
        items = []
        for status in evaluation.statuses:
            record = status.latest_record
            severity, runbook = engine.rule(status.category)
            items.append(LocalAlert(
                category=status.category, severity=severity,
                state="ACTIVE" if status.active is True else "UNKNOWN" if status.active is None
                else "RESOLVED" if record is not None else "INACTIVE",
                observation=TypeAdapter(AlertObservation).validate_python(
                    {"measured": "MEASURED", "no_observations": "NO_DATA", "incomplete": "INCOMPLETE"}[status.data_state],
                ),
                startedAt=engine.timestamp(record.started_at) if record is not None else None,
                updatedAt=engine.timestamp(record.updated_at) if record is not None else None,
                sampleCount=status.sample_count,
                runbookId=TypeAdapter(RunbookId).validate_python(Path(runbook).stem),
                summary=_ALERT_SUMMARIES[status.category],
            ))
        return LocalAlertSummary(items=items, diagnosticsDegraded=evaluation.diagnostics_degraded)
    except Exception:
        engine.failed = True
        return None


@router.get(
    "/status", response_model=StatusSummary,
    responses={code: {"model": StatusErrorResponse} for code in (401, 403, 413, 422, 500, 503)},
)
def get_status(
    request: Request, response: Response,
    _body: Annotated[None, Depends(reject_read_body)],
) -> StatusSummary | JSONResponse:
    response.headers["Cache-Control"] = "no-store"
    if request.query_params:
        error = error_response(422, "VALIDATION_ERROR")
        error.headers["Cache-Control"] = "no-store"
        return error
    try:
        with read_only_observation():
            return _observe_status(request)
    except Exception:
        # Aggregation bugs are typed 500s, never a fabricated degraded success.
        error = error_response(500, "INTERNAL_ERROR")
        error.headers["Cache-Control"] = "no-store"
        return error


def _observe_status(request: Request) -> StatusSummary:
    state = request.app.state
    storage: OperationalStorageStatus = "UNKNOWN"
    revision = None
    size = None
    busy = None
    integrity_at = None
    database = getattr(state, "database", None)
    if database is not None:
        integrity_at = database.last_integrity_check_at
        try:
            observed, revision, size, busy = database.status_snapshot()
            storage = TypeAdapter(OperationalStorageStatus).validate_python(observed)
        except StorageError as error:
            category = str(error) if str(error) in {
                "BUSY", "READ_ONLY", "INTEGRITY_FAILED", "SCHEMA_MISMATCH",
            } else "UNAVAILABLE"
            storage = TypeAdapter(OperationalStorageStatus).validate_python(category)
        except SQLAlchemyError:
            storage = "UNAVAILABLE"
        busy = database.busy_count
    elif getattr(state, "storage_error", None) is not None:
        storage = "UNAVAILABLE"
    else:
        storage = StorageStatus.NOT_READY

    counts = None
    last_sync = None
    sync_duration = None
    sync = getattr(state, "sync_service", None)
    if sync is not None or (database is not None and storage == "OK"):
        try:
            if sync is not None:
                values, last_sync, sync_duration = sync.status_snapshot()
            else:
                values, _operation_id, last_sync = SyncService.observe_status(database.engine)
            counts = SourceCounts.model_validate(values)
        except (SQLAlchemyError, StorageError, ValueError):
            counts = None

    bridge = getattr(state, "bridge", None)
    bridge_status = BridgeStatus.NOT_CHECKED
    if bridge is not None:
        bridge_status = BridgeStatus(bridge.observed_status())

    consent_state: ConsentState | Literal["UNKNOWN"] = "UNKNOWN"
    policy_version = None
    model = None
    consent = getattr(state, "consent_service", None)
    if consent is not None and storage == "OK":
        snapshot = consent.observe_consent(lambda: state.active_ai_policy)
        if isinstance(snapshot, ConsentSnapshot):
            consent_state = snapshot.state.state
            if snapshot.policy is not None:
                policy_version = snapshot.policy.version
                models = {rule.modelId for rule in snapshot.policy.dispatchRules}
                if models == {"gemini-3.8-flash-high"}:
                    model = "gemini-3.8-flash-high"

    search = getattr(state, "search_service", None)
    search_status: Literal["READY", "NOT_READY", "UNAVAILABLE", "UNKNOWN"] = "UNKNOWN"
    if search is not None:
        try:
            search_status = "READY" if search.index.get_version() == PROJECTION_VERSION else "NOT_READY"
        except SQLAlchemyError:
            search_status = "UNAVAILABLE"

    metrics = LocalMetricsSummary(
        requestErrorRate=None, p50Ms=None, p95Ms=None, p99Ms=None, sampledAt=None,
    )
    metrics_failed = True
    collector = getattr(state, "metrics", None)
    if collector is not None and not state.telemetry.span_retention_failed:
        try:
            summary = collector.requests()
            metrics = LocalMetricsSummary(
                requestErrorRate=summary.request_error_rate,
                p50Ms=None if summary.duration.p50_seconds is None else summary.duration.p50_seconds * 1000,
                p95Ms=None if summary.duration.p95_seconds is None else summary.duration.p95_seconds * 1000,
                p99Ms=None if summary.duration.p99_seconds is None else summary.duration.p99_seconds * 1000,
                sampledAt=summary.sampled_at,
            )
            metrics_failed = not summary.window_complete
        except MetricsUnavailable:
            metrics_failed = True
    telemetry = state.telemetry
    alerts = _observe_alerts(getattr(state, "alerts", None))
    diagnostics_failed = (
        metrics_failed or telemetry.span_retention_failed
        or (telemetry.sink is not None and telemetry.sink.failed)
        or (database is not None and database.diagnostics_failed)
        or alerts is None or alerts.diagnosticsDegraded
    )
    local_ready = getattr(state, "ready", None)
    local_storage = local_ready is True and storage == "OK"
    readiness: Readiness
    if sync is not None and sync.syncing:
        readiness = "SYNCING"
    elif local_ready is False:
        readiness = "NOT_READY"
    elif local_ready is not True:
        readiness = "UNKNOWN"
    elif (
        not local_storage or counts is None or counts.INVALID > 0 or counts.MISSING > 0
        or consent_state == "UNKNOWN" or search_status != "READY"
        or bridge_status != BridgeStatus.OK or diagnostics_failed
        or (sync is not None and sync.last_sync_failed is True)
    ):
        readiness = "DEGRADED"
    else:
        readiness = "READY"
    started_at = getattr(state, "started_at", None)
    uptime = None if started_at is None else monotonic() - started_at

    def local_capability(service: object) -> bool | None:
        if service is None:
            return False
        if local_ready is None or storage == "UNKNOWN":
            return None
        return local_storage

    return StatusSummary(
        readiness=readiness, appVersion=state.settings.app_version, uptimeSeconds=uptime,
        storageStatus=storage, schemaRevision=revision, sourceCounts=counts,
        bridgeStatus=bridge_status, selectedModelFamily=model, searchIndexStatus=search_status,
        lastSyncAt=last_sync, lastSyncDurationMs=sync_duration,
        lastIntegrityCheckAt=integrity_at, sqliteFileSizeBytes=size, sqliteBusyCount=busy,
        offlineCapabilities=OfflineCapabilities(
            search=local_capability(search) if search_status == "READY" else (
                None if search is not None and search_status == "UNKNOWN" else False
            ),
            review=local_capability(state.review_service),
            dashboard=local_capability(state.dashboard_service),
            createdQuiz=local_capability(state.operation_ledger),
            lookup=False, newQuiz=False, feedback=False, audio=None,
        ),
        consentState=consent_state, policyVersion=policy_version,
        localMetrics=metrics, localAlerts=alerts, requestId=request_id(),
    )

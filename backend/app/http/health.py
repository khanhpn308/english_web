"""Health endpoint implementation and typed response models (T003)."""

from enum import StrEnum
from typing import Annotated

from backend.app.platform.config import AppSettings
from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field


class HealthStatus(StrEnum):
    """Overall application health status."""

    OK = "OK"
    DEGRADED = "DEGRADED"
    NOT_READY = "NOT_READY"


class StorageStatus(StrEnum):
    """Storage availability status."""

    OK = "OK"
    NOT_READY = "NOT_READY"


class BridgeStatus(StrEnum):
    """AI bridge adapter status."""

    NOT_CHECKED = "NOT_CHECKED"
    OK = "OK"
    NOT_READY = "NOT_READY"


class HealthSummary(BaseModel):
    """Normative health schema matching docs/api-contract.md §183."""

    model_config = ConfigDict(populate_by_name=True)

    status: HealthStatus
    version: str
    storage_status: StorageStatus = Field(serialization_alias="storageStatus")
    bridge_status: BridgeStatus = Field(serialization_alias="bridgeStatus")
    readiness: bool


def get_settings(request: Request) -> AppSettings:
    """Retrieve AppSettings from app.state or fallback to defaults."""
    settings = getattr(request.app.state, "settings", None)
    if isinstance(settings, AppSettings):
        return settings
    return AppSettings()


router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health", response_model=HealthSummary)
def get_health(
    response: Response,
    settings: Annotated[AppSettings, Depends(get_settings)],
) -> HealthSummary:
    """Return application health summary with Cache-Control: no-store."""
    response.headers["Cache-Control"] = "no-store"

    storage_exists = settings.storage_path is not None and settings.storage_path.exists()
    storage_status = StorageStatus.OK if storage_exists else StorageStatus.NOT_READY

    # Health check is independent of bridge; runtime without storage is NOT_READY
    readiness = storage_exists
    status = HealthStatus.OK if readiness else HealthStatus.NOT_READY

    return HealthSummary(
        status=status,
        version=settings.app_version,
        storage_status=storage_status,
        bridge_status=BridgeStatus.NOT_CHECKED,
        readiness=readiness,
    )

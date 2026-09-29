"""Platform configuration models and loopback validation (T003)."""

import ipaddress
from pathlib import Path

from pydantic import BaseModel, ConfigDict, field_validator


class AppSettings(BaseModel):
    """Application runtime configuration for local-first loopback deployment."""

    model_config = ConfigDict(frozen=True)

    host: str = "127.0.0.1"
    port: int = 8000
    app_version: str = "0.1.0"
    storage_path: Path | None = None
    bridge_url: str = "http://127.0.0.1:8045/v1"

    @field_validator("host")
    @classmethod
    def validate_loopback_host(cls, v: str) -> str:
        """Enforce loopback-only binding per security threat T-01 and CONSTRAINTS.md."""
        v_clean = v.strip().lower()
        if v_clean == "localhost":
            return v
        try:
            ip = ipaddress.ip_address(v_clean)
            if ip.is_loopback:
                return v
        except ValueError:
            pass
        raise ValueError(f"Invalid bind host '{v}': only loopback interfaces are permitted")

"""Platform configuration models and loopback validation (T003)."""

import ipaddress
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from backend.app.platform.bridge_port import BridgeConfigError
from pydantic import BaseModel, ConfigDict, SecretStr, field_validator


@dataclass(frozen=True)
class NativeConfiguration:
    """Validated native paths only; credentials never belong in runtime settings."""

    data_root: Path
    storage_path: Path
    markdown_root: Path


class NativeConfigurationReader(Protocol):
    def load(self) -> NativeConfiguration: ...


class ProtectedKeyReader(Protocol):
    def read(self) -> SecretStr: ...


class BridgeKeyMissingError(BridgeConfigError):
    """Confirmed absence differs from inaccessible or corrupt protected material."""

    def __init__(self) -> None:
        super().__init__("Optional bridge key is not configured")


def load_native_configuration(reader: NativeConfigurationReader) -> NativeConfiguration:
    """Consume the native validator without importing desktop or persistence adapters."""
    return reader.load()


def resolve_bridge_key(reader: ProtectedKeyReader, *, profile_verified: bool) -> SecretStr:
    """Backend bridge composition only; explicitly unwrap at the adapter constructor.

    This does not grant consent or replace the adapter's per-dispatch preflight.
    SecretStr keeps repr/JSON redacted; never place the result in AppSettings.
    """
    if profile_verified is not True:
        raise BridgeConfigError("AI configuration unavailable")
    try:
        key = reader.read()
        if not isinstance(key, SecretStr) or not key.get_secret_value():
            raise ValueError
        return key
    except BridgeKeyMissingError:
        raise BridgeKeyMissingError() from None
    except Exception:
        raise BridgeConfigError("AI configuration unavailable") from None


class AppSettings(BaseModel):
    """Application runtime configuration for local-first loopback deployment."""

    model_config = ConfigDict(frozen=True)

    host: str = "127.0.0.1"
    port: int = 8000
    app_version: str = "0.1.0"
    storage_path: Path | None = None
    bridge_url: str = "http://127.0.0.1:8045/v1"

    @classmethod
    def from_native(cls, configuration: NativeConfiguration, *, port: int) -> "AppSettings":
        """The launcher supplies its reserved socket port; Markdown stays a factory argument."""
        return cls(host="127.0.0.1", port=port, storage_path=configuration.storage_path)

    @field_validator("bridge_url")
    @classmethod
    def validate_bridge_url(cls, value: str) -> str:
        if value != "http://127.0.0.1:8045/v1":
            raise ValueError("Only the approved loopback bridge is permitted")
        return value

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

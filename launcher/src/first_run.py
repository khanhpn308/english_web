"""Native/operator provisioning and non-destructive readiness checks for T040.

These functions are not HTTP routes or browser settings. The primary launcher
calls them before backend startup and browser opening. No setup step grants AI consent.
"""

from __future__ import annotations

import ctypes
import json
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from time import monotonic
from typing import Protocol

from backend.app.adapters.bridge import BridgeAdapter
from backend.app.adapters.source_files import (
    SourceFileAdapter,
    _check_windows_ownership,
    validate_relative_path,
)
from backend.app.markdown_sync.parser import MAX_SOURCE_SIZE_BYTES, parse_markdown
from backend.app.markdown_sync.serializer import serialize_document
from backend.app.persistence.database import Database
from backend.app.platform.bridge_port import BridgeProfile
from backend.app.platform.config import NativeConfiguration, resolve_bridge_key
from launcher.src.main import WindowsDesktop, _canonical_path, _windows_path, load_configuration
from launcher.src.protected_key import (
    CONFIG_NAME,
    NativeFileError,
    ProtectedKeyStore,
    WindowsNativeFiles,
)
from launcher.src.windows_mutex import SecurityAttributes, WindowsOperations
from pydantic import SecretStr

REMEDIATION = {
    "CONFIGURATION_REQUIRED": (
        "Use native setup to select existing local writable data and Markdown directories. "
        "Check version-1 configuration, current-user ownership and restrictive permissions. "
        "Preserve existing files; repair configuration explicitly before retrying."
    ),
    "SOURCE_VALIDATION_FAILED": (
        "Repair invalid Markdown filenames, dates or structure in the selected source root. "
        "Resolve unsafe links or access restrictions. Keep original files; setup does not rewrite them."
    ),
    "STORAGE_VALIDATION_FAILED": (
        "Stop the owning launcher and check database access and integrity. Follow the "
        "first-run-and-restore runbook using a separate staging copy. Never delete or rebuild history."
    ),
    "AI_CONFIGURATION_REQUIRED": (
        "Local study can continue after storage readiness. Use native setup to repair the "
        "protected client key and confirm Antigravity v4.8.4, LAN disabled and all_except_health auth. "
        "Do not supply Google credentials or the administration password."
    ),
    "VALIDATION_ONLY": "Paths and Markdown validated; migration and integrity readiness remain unchecked.",
    "READY": "Local storage and native configuration checks completed; AI still requires consent and policy.",
}


class FirstRunError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code if code in REMEDIATION else "CONFIGURATION_REQUIRED"
        super().__init__(self.code)


@dataclass(frozen=True)
class OperatorProfile:
    """Content-free native operator confirmation, never read from provider admin stores."""

    version: str
    allow_lan_access: bool
    auth_mode: str

    def approved(self) -> bool:
        return (
            self.version == "4.8.4"
            and self.allow_lan_access is False
            and self.auth_mode == "all_except_health"
        )


@dataclass(frozen=True)
class FirstRunResult:
    code: str
    local_ready: bool = False
    ai_configured: bool = False
    configuration: NativeConfiguration | None = field(default=None, repr=False)

    @property
    def guidance(self) -> str:
        return REMEDIATION[self.code]


class ConfigurationStore(Protocol):
    def load(self) -> NativeConfiguration: ...
    def provision(self, data_root: Path, markdown_root: Path) -> NativeConfiguration: ...


def check_markdown(configuration: NativeConfiguration) -> None:
    """Read-only, bounded per-file parse/serialize check; never log parser diagnostics."""
    try:
        root = configuration.markdown_root
        SourceFileAdapter(root)

        def failed_walk(_error: OSError) -> None:
            raise FirstRunError("SOURCE_VALIDATION_FAILED")

        for directory, dirs, names in os.walk(root, followlinks=False, onerror=failed_walk):
            dirs[:] = [name for name in dirs if not name.startswith(".")]
            for name in dirs:
                path = Path(directory) / name
                validate_relative_path(path.relative_to(root).as_posix())
                _canonical_path(path, directory=True)
            for name in names:
                if name.startswith(".") or not name.endswith(".md"):
                    continue
                path = Path(directory) / name
                validate_relative_path(path.relative_to(root).as_posix())
                checked = _canonical_path(path, directory=False)
                if not _check_windows_ownership(checked):
                    raise FirstRunError("SOURCE_VALIDATION_FAILED")
                with checked.open("rb") as stream:
                    data = stream.read(MAX_SOURCE_SIZE_BYTES + 1)
                if len(data) > MAX_SOURCE_SIZE_BYTES:
                    raise FirstRunError("SOURCE_VALIDATION_FAILED")
                text = data.decode("utf-8")
                result = parse_markdown(text, filename=name)
                if not result.is_valid or result.document is None:
                    raise FirstRunError("SOURCE_VALIDATION_FAILED")
                if serialize_document(result.document).encode("utf-8") != data:
                    raise FirstRunError("SOURCE_VALIDATION_FAILED")
    except Exception:
        raise FirstRunError("SOURCE_VALIDATION_FAILED") from None


def initialize_storage(configuration: NativeConfiguration) -> None:
    """Existing T005 migration/integrity checks, explicitly separate from a dry run."""
    database = Database(configuration.storage_path)
    try:
        database.initialize()
    finally:
        database.close()


async def check_bridge(key: SecretStr, deadline: float) -> BridgeProfile:
    """Independent native diagnostic sends no study content and does not grant consent."""
    return await BridgeAdapter(api_key=key.get_secret_value()).preflight(deadline)


class WindowsConfigurationStore:
    """Reuse T039's exact TOML reader and path validation; create configuration once."""

    def __init__(self, files: WindowsNativeFiles, desktop: WindowsDesktop) -> None:
        self.files = files
        self.desktop = desktop
        self.profile_root = _canonical_path(
            _windows_path(os.environ.get("USERPROFILE"), desktop), directory=True,
        )

    def _validate(self, configuration: NativeConfiguration) -> NativeConfiguration:
        root = _canonical_path(
            _windows_path(str(configuration.data_root), self.desktop), directory=True,
        )
        markdown = _canonical_path(
            _windows_path(str(configuration.markdown_root), self.desktop), directory=True,
        )
        storage = _canonical_path(
            _windows_path(str(configuration.storage_path), self.desktop),
            directory=False, missing_file=True,
        )
        if root == self.profile_root or not root.is_relative_to(self.profile_root):
            raise NativeFileError()
        if storage == root or not storage.is_relative_to(root):
            raise NativeFileError()
        if len(markdown.parts) <= 1:
            raise NativeFileError()
        for path in (root, markdown):
            if path.is_relative_to(self.files.root) or self.files.root.is_relative_to(path):
                raise NativeFileError()
        for path in {root, storage.parent, markdown}:
            self.desktop.validate_access(path, True, True)
            with self.files._ancestors(path), self.files._open(
                path, directory=True, strict_acl=False,
            ):
                pass
        if storage.exists():
            self.desktop.validate_access(storage, False, True)
            with self.files._ancestors(storage), self.files._open(
                storage, directory=False, strict_acl=False,
            ):
                pass
        return NativeConfiguration(root, storage, markdown)

    def load(self) -> NativeConfiguration:
        try:
            with self.files.configuration_path() as path:
                configuration = load_configuration(path, self.desktop)
                return self._validate(NativeConfiguration(
                    configuration.data_root, configuration.storage_path, configuration.markdown_root,
                ))
        except Exception:
            raise FirstRunError("CONFIGURATION_REQUIRED") from None

    def create_default_data_root(self) -> Path:
        """Create only the approved default directory; never alter existing ACLs or data."""
        path = self.profile_root / "Documents" / "VocabularyApp"
        try:
            _canonical_path(path.parent, directory=True)
            with self.files._ancestors(path):
                descriptor = self.files._descriptor(True)
                try:
                    attributes = SecurityAttributes(
                        ctypes.sizeof(SecurityAttributes), descriptor, False,
                    )
                    if not self.files.kernel.CreateDirectoryW(str(path), ctypes.byref(attributes)):
                        if ctypes.get_last_error() != 183:
                            raise NativeFileError()
                    with self.files._open(path, directory=True):
                        pass
                finally:
                    self.files.kernel.LocalFree(descriptor)
            return path
        except Exception:
            raise FirstRunError("CONFIGURATION_REQUIRED") from None

    def provision(self, data_root: Path, markdown_root: Path) -> NativeConfiguration:
        try:
            configuration = self._validate(NativeConfiguration(
                data_root, data_root / "vocabulary.sqlite3", markdown_root,
            ))
            check_markdown(configuration)
            values = {
                "data_root": str(configuration.data_root),
                "storage_path": str(configuration.storage_path),
                "markdown_root": str(configuration.markdown_root),
            }
            # JSON escaped strings are valid TOML basic strings for these validated Windows paths.
            contents = "schema_version = 1\n" + "".join(
                f"{name} = {json.dumps(value, ensure_ascii=True)}\n" for name, value in values.items()
            )
            self.files.ensure_directories()
            self.files.create(CONFIG_NAME, contents.encode("utf-8"))
            loaded = self.load()
            if loaded != configuration:
                raise NativeFileError()
            return loaded
        except FirstRunError:
            raise
        except Exception:
            raise FirstRunError("CONFIGURATION_REQUIRED") from None


class FirstRun:
    """Inject configuration/protection/checks; production has no non-Windows fallback."""

    def __init__(
        self, configuration: ConfigurationStore, keys: ProtectedKeyStore, *,
        markdown_check: Callable[[NativeConfiguration], None] = check_markdown,
        storage_check: Callable[[NativeConfiguration], None] = initialize_storage,
        bridge_check: Callable[[SecretStr, float], Awaitable[BridgeProfile]] = check_bridge,
    ) -> None:
        self.configuration = configuration
        self.keys = keys
        self.markdown_check = markdown_check
        self.storage_check = storage_check
        self.bridge_check = bridge_check

    async def validate(
        self, *, dry_run: bool = True, profile: OperatorProfile | None = None,
    ) -> FirstRunResult:
        """Dry run reads paths/Markdown only; AI failures never negate local readiness.

        Run with dry_run=False only inside the owning launcher before backend startup.
        The backend still owns journal reconciliation and authoritative health readiness.
        """
        try:
            configuration = self.configuration.load()
        except Exception:
            return FirstRunResult("CONFIGURATION_REQUIRED")
        try:
            self.markdown_check(configuration)
        except Exception:
            return FirstRunResult("SOURCE_VALIDATION_FAILED")
        if dry_run:
            return FirstRunResult("VALIDATION_ONLY", configuration=configuration)
        try:
            self.storage_check(configuration)
        except Exception:
            return FirstRunResult("STORAGE_VALIDATION_FAILED")
        try:
            key = resolve_bridge_key(
                self.keys, profile_verified=profile is not None and profile.approved(),
            )
            await self.bridge_check(key, monotonic() + 10.0)
        except Exception:
            return FirstRunResult("AI_CONFIGURATION_REQUIRED", True, configuration=configuration)
        return FirstRunResult("READY", True, True, configuration)

    def provision(
        self, data_root: Path, markdown_root: Path, *, key: SecretStr | None = None,
    ) -> FirstRunResult:
        """Explicit native creation only; no overwrite, automatic key replacement or inference."""
        try:
            configuration = self.configuration.provision(data_root, markdown_root)
        except FirstRunError as failure:
            return FirstRunResult(failure.code)
        except Exception:
            return FirstRunResult("CONFIGURATION_REQUIRED")
        if key is not None:
            try:
                self.keys.provision(key)
            except Exception:
                return FirstRunResult("AI_CONFIGURATION_REQUIRED", configuration=configuration)
        return FirstRunResult("VALIDATION_ONLY", configuration=configuration)


def windows_first_run() -> FirstRun:
    """Construct for the existing primary native launcher, never from an HTTP handler."""
    try:
        operations = WindowsOperations()
        desktop = WindowsDesktop(operations)
        files = WindowsNativeFiles(operations, desktop)
        configuration = WindowsConfigurationStore(files, desktop)
        return FirstRun(configuration, ProtectedKeyStore(files))
    except Exception:
        raise FirstRunError("CONFIGURATION_REQUIRED") from None

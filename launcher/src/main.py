"""Windows launcher for the owner-approved T039 in-process handoff.

Run from the installed project root with python -m launcher.src.main.
Provisioning and packaging remain owned by T040 and T056.
"""

from __future__ import annotations

import asyncio
import ctypes
import http.client
import json
import logging
import os
import re
import signal
import socket as socket_module
import stat
import threading
import tomllib
from collections.abc import Callable
from ctypes import wintypes
from dataclasses import dataclass
from enum import StrEnum
from html.parser import HTMLParser
from pathlib import Path, PureWindowsPath
from socket import AF_INET, SOCK_STREAM, SOL_SOCKET, socket
from time import monotonic
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from backend.app.platform.config import ProtectedKeyReader
    from launcher.src.first_run import FirstRun, WindowsConfigurationStore

from launcher.src.windows_mutex import (
    InstanceRole,
    SingleInstance,
    SynchronizationError,
    WindowsOperations,
)

HOST = "127.0.0.1"
READINESS_SECONDS = 10.0
MAX_CONFIG_BYTES = 65536
MAX_HEALTH_BYTES = 4096


class LaunchResult(StrEnum):
    STOPPED = "STOPPED"
    FOCUS_REQUESTED = "FOCUS_REQUESTED"
    CONFIGURATION_REQUIRED = "CONFIGURATION_REQUIRED"
    ASSETS_UNAVAILABLE = "ASSETS_UNAVAILABLE"
    INSTANCE_UNAVAILABLE = "INSTANCE_UNAVAILABLE"
    STARTUP_FAILED = "STARTUP_FAILED"
    READINESS_TIMEOUT = "READINESS_TIMEOUT"
    BACKEND_UNAVAILABLE = "BACKEND_UNAVAILABLE"
    BROWSER_UNAVAILABLE = "BROWSER_UNAVAILABLE"
    BLOCKED_CONTRACT = "BLOCKED_CONTRACT"


REMEDIATION = {
    LaunchResult.BLOCKED_CONTRACT: (
        "Native operator input is unavailable at WindowsDesktop.native_setup. "
        "Repair the installed Python Tcl/Tk dialog support and use an interactive Windows "
        "desktop before first-run setup. No setup success was recorded. Existing data is preserved."
    ),
    LaunchResult.CONFIGURATION_REQUIRED: (
        "Local API startup failed because native configuration is missing or unsafe. "
        "Use the native first-run setup to provision local writable data and Markdown "
        "directories and the version-1 configuration. Do not replace an existing database."
    ),
    LaunchResult.ASSETS_UNAVAILABLE: (
        "Local API startup failed because the installed browser assets are unavailable. "
        "Repair the application installation, preserving your data and configuration."
    ),
    LaunchResult.INSTANCE_UNAVAILABLE: (
        "The existing launcher could not be safely contacted. Check the original launcher "
        "in the taskbar or Task Manager. Stop that launcher before restarting. "
        "Do not start another backend against the same data."
    ),
    LaunchResult.STARTUP_FAILED: (
        "Local API startup failed. Check that the configured local directories are "
        "accessible and that another process is not using the data. Stop the owning "
        "launcher before retrying. If failure repeats, follow the storage-integrity runbook."
    ),
    LaunchResult.READINESS_TIMEOUT: (
        "Local API startup timed out after 10 seconds without confirming readiness. "
        "Check local directory access and other processes using the data, then restart "
        "the launcher. For repeated failures, follow the storage-integrity runbook."
    ),
    LaunchResult.BACKEND_UNAVAILABLE: (
        "The local API stopped or lost readiness. A fresh launcher startup and browser "
        "bootstrap are required. Previously acknowledged learning data remains on disk. "
        "For repeated failures, stop writes and follow the storage-integrity runbook."
    ),
    LaunchResult.BROWSER_UNAVAILABLE: (
        "The browser could not be opened safely. Check your default HTTP browser and "
        "restart the launcher. A new startup will use a fresh one-time bootstrap."
    ),
}
FOCUS_REMEDIATION = (
    "A launcher already owns this application. Automatic activation of its browser tab "
    "could not be confirmed. Select the existing Vocabulary tab with the taskbar or "
    "Alt+Tab. If the session has expired or the tab was closed, stop the owning launcher "
    "and restart it for a fresh bootstrap. No additional backend or tab was opened."
)
SHUTDOWN_REMEDIATION = (
    "The local API could not finish shutdown. The owning launcher will now stop. "
    "Do not copy or restore data until it has stopped. Restart for a fresh session; "
    "if this repeats, follow the storage-integrity runbook."
)
AI_KEY_REMEDIATION = (
    "AI is unavailable because the protected client key could not be safely read. "
    "Local study can continue after storage readiness. Repair current-user permissions or "
    "explicitly reconfigure the protected store through native setup. Do not overwrite damaged "
    "material, reset learning data, or supply Google credentials or an administration password."
)


class LaunchFailure(RuntimeError):
    def __init__(self, result: LaunchResult, *, guidance: str | None = None) -> None:
        self.result = result
        self.guidance = guidance
        super().__init__(result.value)


@dataclass(frozen=True)
class Configuration:
    data_root: Path
    storage_path: Path
    markdown_root: Path


class DesktopOperations(Protocol):
    def local_drive(self, root: str) -> bool: ...
    def validate_access(self, path: Path, directory: bool, writable: bool) -> None: ...
    def open_bootstrap(self, port: int, token: str) -> None: ...
    def focus_browser(self) -> bool: ...
    def notify(self, message: str) -> None: ...
    def close(self) -> None: ...


def _windows_path(raw: object, desktop: DesktopOperations) -> Path:
    if not isinstance(raw, str) or not raw or len(raw) > 32767:
        raise LaunchFailure(LaunchResult.CONFIGURATION_REQUIRED)
    windows = PureWindowsPath(raw)
    if not windows.is_absolute() or re.fullmatch(r"[A-Za-z]:", windows.drive) is None:
        raise LaunchFailure(LaunchResult.CONFIGURATION_REQUIRED)
    reserved = {"con", "prn", "aux", "nul"} | {
        f"{prefix}{index}" for prefix in ("com", "lpt") for index in range(1, 10)
    }
    for part in windows.parts[1:]:
        if (
            part in {".", ".."} or part.endswith((".", " "))
            or any(ord(character) < 32 or character in '<>:"|?*%' for character in part)
            or part.split(".")[0].casefold() in reserved
        ):
            raise LaunchFailure(LaunchResult.CONFIGURATION_REQUIRED)
    if not desktop.local_drive(windows.anchor):
        raise LaunchFailure(LaunchResult.CONFIGURATION_REQUIRED)
    return Path(str(windows))


def _canonical_path(path: Path, *, directory: bool, missing_file: bool = False) -> Path:
    # Reject every reparse traversal rather than guessing whether a junction is trusted.
    for component in (*reversed(path.parents), path):
        try:
            metadata = component.lstat()
        except FileNotFoundError:
            if component == path and missing_file:
                continue
            raise LaunchFailure(LaunchResult.CONFIGURATION_REQUIRED) from None
        if stat.S_ISLNK(metadata.st_mode) or getattr(metadata, "st_file_attributes", 0) & 0x400:
            raise LaunchFailure(LaunchResult.CONFIGURATION_REQUIRED)
        if component != path and not stat.S_ISDIR(metadata.st_mode):
            raise LaunchFailure(LaunchResult.CONFIGURATION_REQUIRED)
        if component == path and (
            (directory and not stat.S_ISDIR(metadata.st_mode))
            or (not directory and (not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1))
        ):
            raise LaunchFailure(LaunchResult.CONFIGURATION_REQUIRED)
    return path.resolve(strict=not missing_file)


def load_configuration(path: Path, desktop: DesktopOperations) -> Configuration:
    try:
        config_path = _canonical_path(path, directory=False)
        desktop.validate_access(config_path, False, False)
        with config_path.open("rb") as stream:
            contents = stream.read(MAX_CONFIG_BYTES + 1)
        if len(contents) > MAX_CONFIG_BYTES:
            raise LaunchFailure(LaunchResult.CONFIGURATION_REQUIRED)
        values = tomllib.loads(contents.decode("utf-8"))
        if set(values) != {"schema_version", "data_root", "storage_path", "markdown_root"}:
            raise LaunchFailure(LaunchResult.CONFIGURATION_REQUIRED)
        if type(values["schema_version"]) is not int or values["schema_version"] != 1:
            raise LaunchFailure(LaunchResult.CONFIGURATION_REQUIRED)
        root = _canonical_path(_windows_path(values["data_root"], desktop), directory=True)
        storage = _canonical_path(
            _windows_path(values["storage_path"], desktop), directory=False, missing_file=True
        )
        markdown = _canonical_path(_windows_path(values["markdown_root"], desktop), directory=True)
        if storage == root or not storage.is_relative_to(root):
            raise LaunchFailure(LaunchResult.CONFIGURATION_REQUIRED)
        for directory in {root, storage.parent, markdown}:
            desktop.validate_access(directory, True, True)
        if storage.exists():
            desktop.validate_access(storage, False, True)
        return Configuration(root, storage, markdown)
    except (OSError, UnicodeError, ValueError):
        raise LaunchFailure(LaunchResult.CONFIGURATION_REQUIRED) from None


class _AssetReferences(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.references: list[str] = []
        self.module_found = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "script":
            source = attributes.get("src")
            self.module_found |= attributes.get("type") == "module" and bool(source)
            if source:
                self.references.append(source)
        elif tag == "link" and attributes.get("rel") in {"stylesheet", "modulepreload"}:
            if href := attributes.get("href"):
                self.references.append(href)


def require_assets(root: Path) -> None:
    try:
        if not (root / "assets").is_dir():
            raise LaunchFailure(LaunchResult.ASSETS_UNAVAILABLE)
        for name in ("index.html", "bootstrap.html"):
            with (root / name).open("rb") as stream:
                content = stream.read(MAX_CONFIG_BYTES + 1)
            if len(content) > MAX_CONFIG_BYTES:
                raise LaunchFailure(LaunchResult.ASSETS_UNAVAILABLE)
            parser = _AssetReferences()
            parser.feed(content.decode("utf-8"))
            if not parser.module_found:
                raise LaunchFailure(LaunchResult.ASSETS_UNAVAILABLE)
            for reference in parser.references:
                if (
                    not reference.startswith("/assets/")
                    or "\\" in reference or "?" in reference or "#" in reference
                    or ".." in reference.split("/")
                    or not (root / reference.lstrip("/")).is_file()
                ):
                    raise LaunchFailure(LaunchResult.ASSETS_UNAVAILABLE)
                with (root / reference.lstrip("/")).open("rb") as asset:
                    asset.read(1)
    except (OSError, UnicodeError, ValueError):
        raise LaunchFailure(LaunchResult.ASSETS_UNAVAILABLE) from None


def reserve_socket() -> socket:
    listener = socket(AF_INET, SOCK_STREAM)
    try:
        listener.set_inheritable(False)
        # No SO_REUSEADDR fallback: Windows exclusive binding is part of this boundary.
        listener.setsockopt(SOL_SOCKET, socket_module.SO_EXCLUSIVEADDRUSE, 1)
        listener.bind((HOST, 0))
        listener.listen(128)
        listener.setblocking(False)
        return listener
    except BaseException:
        listener.close()
        raise


def health_ready(port: int, timeout: float) -> bool:
    # HTTP socket timeouts apply per I/O; this wait bounds the whole health exchange.
    connection = http.client.HTTPConnection(HOST, port, timeout=timeout)
    finished = threading.Event()
    ready = False

    def probe() -> None:
        nonlocal ready
        try:
            ready = _health_response(connection)
        except Exception:
            ready = False
        finally:
            finished.set()

    worker = threading.Thread(target=probe, name="vocabulary-health", daemon=True)
    worker.start()
    if not finished.wait(timeout):
        connection.close()
        return False
    return ready


def _health_response(connection: http.client.HTTPConnection) -> bool:
    try:
        connection.request("GET", "/api/v1/health")
        response = connection.getresponse()
        if response.status != 200:
            return False
        body = response.read(MAX_HEALTH_BYTES + 1)
        if len(body) > MAX_HEALTH_BYTES or response.getheader("Content-Type", "").split(";")[0] != "application/json":
            return False
        health = json.loads(body)
        return (
            isinstance(health, dict) and health.get("readiness") is True
            and health.get("storageStatus") == "OK"
            and health.get("status") in {"OK", "DEGRADED"}
            and isinstance(health.get("version"), str)
            and health.get("bridgeStatus") in {"NOT_CHECKED", "OK", "NOT_READY"}
        )
    except (OSError, ValueError, TypeError, http.client.HTTPException):
        return False
    finally:
        connection.close()


class Backend:
    def __init__(
        self, configuration: Configuration, listener: socket, *,
        bridge_key_reader: ProtectedKeyReader | None = None,
        bridge_profile_verified: bool = False,
    ) -> None:
        import uvicorn
        from backend.app.main import create_app
        from backend.app.platform.config import AppSettings, NativeConfiguration

        # Uvicorn exceptions/access output are not the application's redacted telemetry.
        for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
            logging.getLogger(name).disabled = True
        self.port = listener.getsockname()[1]
        self.listener = listener
        self.app = create_app(
            settings=AppSettings.from_native(NativeConfiguration(
                configuration.data_root, configuration.storage_path, configuration.markdown_root,
            ), port=self.port),
            markdown_root=configuration.markdown_root,
            bridge_key_reader=bridge_key_reader,
            bridge_profile_verified=bridge_profile_verified,
        )
        self.server = uvicorn.Server(uvicorn.Config(
            self.app, host=HOST, port=self.port, workers=1, reload=False,
            lifespan="on", loop="asyncio", http="h11", ws="none",
            proxy_headers=False, access_log=False, log_config=None,
            timeout_graceful_shutdown=4,
        ))
        self.failed = threading.Event()
        self.thread = threading.Thread(target=self._serve, name="vocabulary-backend", daemon=True)

    def _serve(self) -> None:
        try:
            self.server.run(sockets=[self.listener])
        except BaseException:
            # Never retain or print exception objects containing request/local path data.
            self.failed.set()
        finally:
            self.app.state.sessions.invalidate()
            self.app.state.ready = False

    def start(self) -> None:
        self.thread.start()

    def alive(self) -> bool:
        return self.thread.is_alive() and not self.failed.is_set()

    def stop(self) -> bool:
        self.app.state.sessions.invalidate()
        self.server.should_exit = True
        if self.thread.ident is None:
            return True
        self.thread.join(5.0)
        if self.thread.is_alive():
            self.server.force_exit = True
            self.thread.join(1.0)
        return not self.thread.is_alive()


def wait_ready(backend: Backend, stop: threading.Event, deadline: float) -> bool:
    while not stop.is_set():
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise LaunchFailure(LaunchResult.READINESS_TIMEOUT)
        if not backend.alive():
            raise LaunchFailure(LaunchResult.STARTUP_FAILED)
        if health_ready(backend.port, min(0.25, remaining)):
            if monotonic() >= deadline:
                raise LaunchFailure(LaunchResult.READINESS_TIMEOUT)
            if backend.alive() and backend.app.state.ready is True:
                return True
        stop.wait(min(0.1, max(0.0, deadline - monotonic())))
    return False


def _hard_shutdown(desktop: DesktopOperations) -> None:
    # Never release ownership while a stuck in-process worker could still write.
    watchdog = threading.Timer(5.0, os._exit, args=(1,))
    watchdog.daemon = True
    watchdog.start()
    try:
        desktop.notify(SHUTDOWN_REMEDIATION)
    finally:
        os._exit(1)


def run_launcher(
    instance: SingleInstance, desktop: DesktopOperations, config_path: Path | None,
    stop: threading.Event,
    *, backend_factory: Callable[[Configuration, socket], Backend] = Backend,
    socket_factory: Callable[[], socket] = reserve_socket,
    configuration_loader: Callable[[], Configuration] | None = None,
) -> LaunchResult:
    backend = None
    listener = None
    result = LaunchResult.STOPPED
    guidance = None
    try:
        role = instance.acquire()
        if role == InstanceRole.DUPLICATE:
            result = (
                LaunchResult.FOCUS_REQUESTED if instance.request_focus()
                else LaunchResult.INSTANCE_UNAVAILABLE
            )
        elif role in {InstanceRole.PRIMARY, InstanceRole.RECOVERED}:
            if configuration_loader is not None:
                configuration = configuration_loader()
            elif config_path is not None:
                configuration = load_configuration(config_path, desktop)
            else:
                raise LaunchFailure(LaunchResult.CONFIGURATION_REQUIRED)
            from backend.app.main import STATIC_ROOT

            require_assets(STATIC_ROOT)
            listener = socket_factory()
            backend = backend_factory(configuration, listener)
            deadline = monotonic() + READINESS_SECONDS
            backend.start()
            if wait_ready(backend, stop, deadline) and not stop.is_set():
                if getattr(backend.app.state, "bridge_configuration_status", None) == "INVALID":
                    desktop.notify(AI_KEY_REMEDIATION)
                if stop.is_set() or not backend.alive() or backend.app.state.ready is not True:
                    raise LaunchFailure(LaunchResult.BACKEND_UNAVAILABLE)
                token = backend.app.state.sessions.issue_bootstrap_token()
                try:
                    desktop.open_bootstrap(backend.port, token)
                finally:
                    del token
                next_health = monotonic()
                focus_notice: threading.Thread | None = None
                while not stop.is_set():
                    if not backend.alive():
                        raise LaunchFailure(LaunchResult.BACKEND_UNAVAILABLE)
                    if monotonic() >= next_health:
                        if not health_ready(backend.port, 0.5):
                            raise LaunchFailure(LaunchResult.BACKEND_UNAVAILABLE)
                        next_health = monotonic() + 1.0
                    if instance.focus_requested() and not desktop.focus_browser():
                        if focus_notice is None or not focus_notice.is_alive():
                            focus_notice = threading.Thread(
                                target=desktop.notify, args=(FOCUS_REMEDIATION,),
                                name="vocabulary-focus-remediation", daemon=True,
                            )
                            focus_notice.start()
        else:
            raise SynchronizationError("Instance role unavailable")
    except SynchronizationError:
        result = LaunchResult.INSTANCE_UNAVAILABLE
    except LaunchFailure as failure:
        result = failure.result
        guidance = failure.guidance
    except KeyboardInterrupt:
        stop.set()
    except Exception:
        result = LaunchResult.STARTUP_FAILED
    finally:
        if backend is not None and not backend.stop():
            _hard_shutdown(desktop)
        try:
            if listener is not None:
                listener.close()
        finally:
            try:
                instance.close()
            finally:
                desktop.close()
    if result in REMEDIATION:
        desktop.notify(guidance or REMEDIATION[result])
    return result


class ShellExecuteInfo(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD), ("fMask", wintypes.ULONG), ("hwnd", wintypes.HWND),
        ("lpVerb", wintypes.LPCWSTR), ("lpFile", wintypes.LPCWSTR),
        ("lpParameters", wintypes.LPCWSTR), ("lpDirectory", wintypes.LPCWSTR),
        ("nShow", ctypes.c_int), ("hInstApp", wintypes.HINSTANCE),
        ("lpIDList", ctypes.c_void_p), ("lpClass", wintypes.LPCWSTR),
        ("hkeyClass", wintypes.HKEY), ("dwHotKey", wintypes.DWORD),
        ("hMonitor", wintypes.HANDLE), ("hProcess", wintypes.HANDLE),
    ]


class WindowsDesktop:
    """Documented Win32 file, browser-open and foreground APIs only.

    Sources: Microsoft Learn CreateFileW, SHELLEXECUTEINFOW, SetForegroundWindow.
    """

    def __init__(self, operations: WindowsOperations) -> None:
        self.operations = operations
        self.kernel = operations.kernel
        self.user = ctypes.WinDLL("user32", use_last_error=True)
        self.shell = ctypes.WinDLL("shell32", use_last_error=True)
        self.ole = ctypes.WinDLL("ole32", use_last_error=True)
        self.browser_process: int | None = None
        self.browser_window: int | None = None
        self.com_initialized = False
        self.open_attempted = False
        self.bridge_key_reader: ProtectedKeyReader | None = None
        self.bridge_profile_verified = False
        self.window_callback = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        signatures = [
            (self.kernel, "GetDriveTypeW", [wintypes.LPCWSTR], wintypes.UINT),
            (self.kernel, "CreateFileW", [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE], wintypes.HANDLE),
            (self.kernel, "GetFinalPathNameByHandleW", [wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD], wintypes.DWORD),
            (self.kernel, "GetProcessId", [wintypes.HANDLE], wintypes.DWORD),
            (self.kernel, "GetCurrentProcessId", [], wintypes.DWORD),
            (self.kernel, "ProcessIdToSessionId", [wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)], wintypes.BOOL),
            (self.kernel, "GetExitCodeProcess", [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)], wintypes.BOOL),
            (self.shell, "ShellExecuteExW", [ctypes.POINTER(ShellExecuteInfo)], wintypes.BOOL),
            (self.user, "MessageBoxW", [wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.UINT], ctypes.c_int),
            (self.user, "EnumWindows", [self.window_callback, wintypes.LPARAM], wintypes.BOOL),
            (self.user, "IsWindow", [wintypes.HWND], wintypes.BOOL),
            (self.user, "IsWindowVisible", [wintypes.HWND], wintypes.BOOL),
            (self.user, "IsIconic", [wintypes.HWND], wintypes.BOOL),
            (self.user, "GetWindowThreadProcessId", [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)], wintypes.DWORD),
            (self.user, "ShowWindowAsync", [wintypes.HWND, ctypes.c_int], wintypes.BOOL),
            (self.user, "SetForegroundWindow", [wintypes.HWND], wintypes.BOOL),
            (self.user, "GetForegroundWindow", [], wintypes.HWND),
            (self.ole, "CoInitializeEx", [ctypes.c_void_p, wintypes.DWORD], ctypes.c_long),
            (self.ole, "CoUninitialize", [], None),
        ]
        for library, name, arguments, result in signatures:
            function = getattr(library, name)
            function.argtypes = arguments
            function.restype = result

    def local_drive(self, root: str) -> bool:
        return self.kernel.GetDriveTypeW(root) in {2, 3, 6}

    def validate_access(self, path: Path, directory: bool, writable: bool) -> None:
        # OPEN_EXISTING checks the current user's actual ACL without a write probe.
        access = (0xC7 if writable else 0x81) if directory else (
            0xC0000000 if writable else 0x80000000
        )
        handle = self.kernel.CreateFileW(str(path), access, 7, None, 3, 0x02200000, None)
        if handle in {None, ctypes.c_void_p(-1).value}:
            raise LaunchFailure(LaunchResult.CONFIGURATION_REQUIRED)
        try:
            buffer = ctypes.create_unicode_buffer(32768)
            length = self.kernel.GetFinalPathNameByHandleW(handle, buffer, len(buffer), 0)
            if not 0 < length < len(buffer):
                raise LaunchFailure(LaunchResult.CONFIGURATION_REQUIRED)
            final_path = buffer.value
            if final_path.startswith("\\\\?\\"):
                final_path = final_path[4:]
            if os.path.normcase(final_path) != os.path.normcase(str(path)):
                raise LaunchFailure(LaunchResult.CONFIGURATION_REQUIRED)
        finally:
            self.operations.close(handle)

    def notify(self, message: str) -> None:
        self.user.MessageBoxW(None, message, "Vocabulary App", 0x10 | 0x10000)

    def confirm(self, message: str) -> bool:
        # MB_YESNO | MB_ICONQUESTION | MB_DEFBUTTON2: refusal is the default.
        return self.user.MessageBoxW(None, message, "Vocabulary App", 0x104 | 0x20) == 6

    def confirm_bridge_profile(self) -> bool:
        from launcher.src.first_run import OperatorProfile

        confirmed = self.confirm(
            "Confirm that Antigravity v4.8.4 uses only http://127.0.0.1:8045/v1, "
            "LAN access is disabled and authentication is all_except_health. "
            "This enables protected-key resolution, not AI consent or provider approval. "
            "Select No to continue with local study only."
        )
        return confirmed and OperatorProfile("4.8.4", False, "all_except_health").approved()

    def native_setup(
        self, setup: FirstRun, store: WindowsConfigurationStore, *, configuration_required: bool,
    ) -> None:
        """Native operator interaction only, called with primary-instance ownership.

        Source: https://docs.python.org/3.12/library/dialog.html
        Source: https://docs.python.org/3.12/library/tkinter.html
        """
        from launcher.src.first_run import FirstRunError, REMEDIATION as SETUP_REMEDIATION

        root = None
        try:
            import tkinter
            from tkinter import filedialog, simpledialog
            from pydantic import SecretStr

            if tkinter.__dict__.get("_debug", False):
                raise LaunchFailure(LaunchResult.BLOCKED_CONTRACT)

            class OperatorRoot(tkinter.Tk):
                callback_failed = False

                def readprofile(self, baseName: str, className: str) -> None:
                    # Tk normally executes user profile scripts; secret entry must not load them.
                    return None

                def report_callback_exception(self, *_details: object) -> None:
                    # Tk's default retains and prints raw exceptions/tracebacks.
                    self.callback_failed = True
                    self.destroy()

            root = OperatorRoot()
            root.withdraw()
            if configuration_required:
                use_default = self.confirm(
                    "Use the default data directory Documents\\VocabularyApp under your Windows "
                    "profile? Select No to choose an existing data directory. Setup uses "
                    "vocabulary.sqlite3 and preserves existing files."
                )
                data = None if use_default else filedialog.askdirectory(
                    parent=root, title="Select existing local data directory", mustexist=True,
                )
                if not use_default and not data:
                    raise LaunchFailure(LaunchResult.CONFIGURATION_REQUIRED)
                markdown = filedialog.askdirectory(
                    parent=root, title="Select existing local Markdown directory", mustexist=True,
                )
                if not markdown or not self.confirm(
                    "Validate the selected directories and create native configuration? "
                    "Existing configuration, database and Markdown files will not be replaced."
                ):
                    raise LaunchFailure(LaunchResult.CONFIGURATION_REQUIRED)
                if use_default:
                    data_root = store.create_default_data_root()
                elif data:
                    data_root = Path(data)
                else:
                    raise LaunchFailure(LaunchResult.CONFIGURATION_REQUIRED)
                result = setup.provision(data_root, Path(markdown))
                if result.code != "VALIDATION_ONLY" or result.configuration is None:
                    raise LaunchFailure(LaunchResult.CONFIGURATION_REQUIRED, guidance=result.guidance)
            else:
                self.bridge_profile_verified = self.confirm_bridge_profile()
                if not self.bridge_profile_verified:
                    return
                value = simpledialog.askstring(
                    "Optional AI client key",
                    "Enter the rotated Antigravity client key.\n"
                    "Do not enter a Google credential or administration password.\n"
                    "Cancel to continue with local study only.",
                    parent=root, show="*",
                )
                try:
                    if value is not None:
                        try:
                            store.files.ensure_directories()
                            setup.keys.provision(SecretStr(value))
                        except Exception:
                            self.notify(AI_KEY_REMEDIATION)
                finally:
                    del value
            if root.callback_failed:
                raise LaunchFailure(LaunchResult.BLOCKED_CONTRACT)
        except LaunchFailure:
            raise
        except FirstRunError as failure:
            raise LaunchFailure(
                LaunchResult.CONFIGURATION_REQUIRED, guidance=SETUP_REMEDIATION[failure.code],
            ) from None
        except Exception:
            raise LaunchFailure(LaunchResult.BLOCKED_CONTRACT) from None
        finally:
            if root is not None and not root.callback_failed:
                try:
                    root.destroy()
                except Exception:
                    raise LaunchFailure(LaunchResult.BLOCKED_CONTRACT) from None

    def prepare_configuration(self) -> Configuration:
        """Reuse R1 checks and T039's reader; backend owns migration/integrity readiness."""
        from launcher.src.first_run import (
            FirstRun, REMEDIATION as SETUP_REMEDIATION, WindowsConfigurationStore,
        )
        from launcher.src.protected_key import (
            CONFIG_NAME, KEY_NAME, NativeFileError, ProtectedKeyStore, WindowsNativeFiles,
        )

        self.bridge_key_reader = None
        self.bridge_profile_verified = False
        try:
            files = WindowsNativeFiles(self.operations, self)
            store = WindowsConfigurationStore(files, self)
            setup = FirstRun(store, ProtectedKeyStore(files))
            new_configuration = files.is_absent(CONFIG_NAME)
            if new_configuration:
                self.native_setup(setup, store, configuration_required=True)
            validation = asyncio.run(setup.validate(dry_run=True))
            if validation.code != "VALIDATION_ONLY" or validation.configuration is None:
                raise LaunchFailure(
                    LaunchResult.CONFIGURATION_REQUIRED, guidance=validation.guidance,
                )
            if not new_configuration:
                try:
                    validation.configuration.storage_path.lstat()
                except FileNotFoundError:
                    if not self.confirm(
                        "The configured database is missing. Creating an empty database will not "
                        "recover any previous learning history. Create it only if this is an "
                        "intentionally new installation. Otherwise select No, preserve your "
                        "directories and follow the staging restore runbook. Create a new database?"
                    ):
                        raise LaunchFailure(
                            LaunchResult.CONFIGURATION_REQUIRED,
                            guidance=SETUP_REMEDIATION["STORAGE_VALIDATION_FAILED"],
                        )
        except LaunchFailure:
            raise
        except Exception:
            raise LaunchFailure(
                LaunchResult.CONFIGURATION_REQUIRED,
                guidance=SETUP_REMEDIATION["CONFIGURATION_REQUIRED"],
            ) from None

        self.bridge_key_reader = setup.keys
        try:
            key_missing = files.is_absent(KEY_NAME)
        except NativeFileError:
            key_missing = False
            self.notify(AI_KEY_REMEDIATION)
        if key_missing:
            self.bridge_key_reader = None
            if self.confirm(
                "Local configuration is valid. Configure the optional protected AI client key now? "
                "Select No to continue with local study."
            ):
                try:
                    self.native_setup(setup, store, configuration_required=False)
                except LaunchFailure as failure:
                    self.notify(failure.guidance or REMEDIATION[failure.result])
                # Re-read through the backend resolver, including any incomplete provision.
                self.bridge_key_reader = setup.keys
        else:
            self.bridge_profile_verified = self.confirm_bridge_profile()
        configuration = validation.configuration
        return Configuration(
            configuration.data_root, configuration.storage_path, configuration.markdown_root,
        )

    def open_bootstrap(self, port: int, token: str) -> None:
        if not 1 <= port <= 65535 or re.fullmatch(r"[A-Za-z0-9_-]{1,128}", token) is None:
            raise LaunchFailure(LaunchResult.BROWSER_UNAVAILABLE)
        if self.open_attempted:
            raise LaunchFailure(LaunchResult.BROWSER_UNAVAILABLE)
        self.open_attempted = True
        initialized = self.ole.CoInitializeEx(None, 2)
        if initialized not in {0, 1}:
            raise LaunchFailure(LaunchResult.BROWSER_UNAVAILABLE)
        self.com_initialized = True
        info = ShellExecuteInfo()
        info.cbSize = ctypes.sizeof(info)
        info.fMask = 0x40 | 0x100 | 0x400
        info.lpVerb = "open"
        info.lpFile = f"http://{HOST}:{port}/bootstrap#token={token}"
        info.nShow = 1
        try:
            if not self.shell.ShellExecuteExW(ctypes.byref(info)):
                if info.hProcess:
                    self.operations.close(info.hProcess)
                raise LaunchFailure(LaunchResult.BROWSER_UNAVAILABLE)
            self.browser_process = info.hProcess
        finally:
            info.lpFile = None
        # Learn a window only during this launch, never from a later duplicate request.
        deadline = monotonic() + 1.0
        while monotonic() < deadline:
            pid = self._browser_pid()
            if pid is None:
                break
            windows = self._browser_windows(pid)
            if len(windows) == 1:
                self.browser_window = windows[0]
                break
            threading.Event().wait(0.05)

    def _browser_pid(self) -> int | None:
        if self.browser_process is None:
            return None
        exit_code = wintypes.DWORD()
        if not self.kernel.GetExitCodeProcess(self.browser_process, ctypes.byref(exit_code)) or exit_code.value != 259:
            return None
        pid = self.kernel.GetProcessId(self.browser_process)
        browser_session, launcher_session = wintypes.DWORD(), wintypes.DWORD()
        if (
            not pid
            or not self.kernel.ProcessIdToSessionId(pid, ctypes.byref(browser_session))
            or not self.kernel.ProcessIdToSessionId(self.kernel.GetCurrentProcessId(), ctypes.byref(launcher_session))
            or browser_session.value != launcher_session.value
        ):
            return None
        token = wintypes.HANDLE()
        if not self.operations.security.OpenProcessToken(self.browser_process, 8, ctypes.byref(token)):
            return None
        try:
            user = self.operations._token_information(token, 1)
            if self.operations._sid_text(ctypes.c_void_p.from_buffer(user)) != self.operations.sid:
                return None
        except SynchronizationError:
            return None
        finally:
            self.operations.close(token.value)
        return pid

    def _browser_windows(self, pid: int) -> list[int]:
        windows: list[int] = []

        @self.window_callback
        def collect(window: int, _parameter: int) -> bool:
            owner = wintypes.DWORD()
            self.user.GetWindowThreadProcessId(window, ctypes.byref(owner))
            if owner.value == pid and self.user.IsWindowVisible(window):
                windows.append(window)
            return True

        return windows if self.user.EnumWindows(collect, 0) else []

    def focus_browser(self) -> bool:
        pid = self._browser_pid()
        window = self.browser_window
        if pid is None or window is None or self._browser_windows(pid) != [window]:
            return False
        # shortcut: this identifies a browser window, exact-tab evidence belongs to T057.
        deadline = monotonic() + 0.5
        while monotonic() < deadline:
            owner = wintypes.DWORD()
            self.user.GetWindowThreadProcessId(window, ctypes.byref(owner))
            if owner.value != pid or not self.user.IsWindow(window) or self._browser_pid() != pid:
                return False
            if self.user.IsIconic(window):
                self.user.ShowWindowAsync(window, 9)
            if self.user.SetForegroundWindow(window) and self.user.GetForegroundWindow() == window:
                return True
            threading.Event().wait(0.05)
        return False

    def close(self) -> None:
        if self.browser_process is not None:
            self.operations.close(self.browser_process)
            self.browser_process = None
        self.browser_window = None
        if self.com_initialized:
            self.ole.CoUninitialize()
            self.com_initialized = False


def main() -> int:
    if os.name != "nt":
        return 2
    stop = threading.Event()
    previous_handlers = {}
    desktop = None
    try:
        for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGBREAK):
            previous_handlers[signum] = signal.signal(signum, lambda _number, _frame: stop.set())
        operations = WindowsOperations()
        runtime_desktop = WindowsDesktop(operations)
        desktop = runtime_desktop

        def backend_factory(configuration: Configuration, listener: socket) -> Backend:
            return Backend(
                configuration, listener, bridge_key_reader=runtime_desktop.bridge_key_reader,
                bridge_profile_verified=runtime_desktop.bridge_profile_verified,
            )

        result = run_launcher(
            SingleInstance(operations), desktop, None, stop,
            configuration_loader=desktop.prepare_configuration, backend_factory=backend_factory,
        )
        return 0 if result in {LaunchResult.STOPPED, LaunchResult.FOCUS_REQUESTED} else 1
    except Exception as failure:
        result = (
            failure.result if isinstance(failure, LaunchFailure)
            else LaunchResult.INSTANCE_UNAVAILABLE if isinstance(failure, SynchronizationError)
            else LaunchResult.STARTUP_FAILED
        )
        if desktop is not None:
            desktop.notify(REMEDIATION[result])
        else:
            # Initialization failure still gets a fixed native fallback, without exception text.
            user = ctypes.WinDLL("user32", use_last_error=True)
            user.MessageBoxW.argtypes = [wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.UINT]
            user.MessageBoxW.restype = ctypes.c_int
            user.MessageBoxW(None, REMEDIATION[LaunchResult.INSTANCE_UNAVAILABLE], "Vocabulary App", 0x10)
        return 1
    finally:
        if desktop is not None:
            desktop.close()
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)


if __name__ == "__main__":
    raise SystemExit(main())

"""Current-user DPAPI and fixed, protected native configuration files (T040)."""

from __future__ import annotations

import ctypes
import os
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from ctypes import wintypes
from pathlib import Path
from typing import Protocol

from backend.app.platform.config import BridgeKeyMissingError
from launcher.src.main import WindowsDesktop, _canonical_path, _windows_path
from launcher.src.windows_mutex import SecurityAttributes, WindowsOperations
from pydantic import SecretStr

MAX_KEY_BYTES = 4096
MAX_PROTECTED_BYTES = 65536
CONFIG_NAME = "config.toml"
KEY_NAME = "secrets/bridge-key.dpapi"


class ProtectedKeyError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("AI configuration unavailable; repair the native protected key store")


class NativeFileError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Native configuration unavailable; check paths and current-user permissions")


class Protection(Protocol):
    def protect(self, plaintext: bytes) -> bytes: ...
    def unprotect(self, protected: bytes) -> bytes: ...


class KeyFiles(Protocol):
    def read(self, name: str, maximum: int) -> bytes: ...
    def create(self, name: str, content: bytes) -> None: ...


class DataBlob(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("data", ctypes.c_void_p)]


class CurrentUserDPAPI:
    """No machine-wide scope, prompt, audit description, or fallback protection.

    Source: https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata
    Source: https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptunprotectdata
    """

    def __init__(self) -> None:
        if os.name != "nt":
            raise ProtectedKeyError()
        self.crypt = ctypes.WinDLL("crypt32", use_last_error=True)
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        for name in ("CryptProtectData", "CryptUnprotectData"):
            function = getattr(self.crypt, name)
            function.argtypes = [
                ctypes.POINTER(DataBlob), ctypes.c_void_p, ctypes.POINTER(DataBlob),
                ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(DataBlob),
            ]
            function.restype = wintypes.BOOL
        self.kernel.LocalFree.argtypes = [ctypes.c_void_p]
        self.kernel.LocalFree.restype = ctypes.c_void_p

    def _transform(self, data: bytes, *, decrypt: bool) -> bytes:
        if not 0 < len(data) <= MAX_PROTECTED_BYTES:
            raise ProtectedKeyError()
        buffer = ctypes.create_string_buffer(data)
        incoming = DataBlob(len(data), ctypes.cast(buffer, ctypes.c_void_p))
        outgoing = DataBlob()
        try:
            function = self.crypt.CryptUnprotectData if decrypt else self.crypt.CryptProtectData
            # CRYPTPROTECT_UI_FORBIDDEN only: never CRYPTPROTECT_LOCAL_MACHINE.
            if not function(
                ctypes.byref(incoming), None, None, None, None, 1, ctypes.byref(outgoing),
            ):
                raise ProtectedKeyError()
            if not outgoing.data or not 0 < outgoing.size <= MAX_PROTECTED_BYTES:
                raise ProtectedKeyError()
            return ctypes.string_at(outgoing.data, outgoing.size)
        except Exception:
            raise ProtectedKeyError() from None
        finally:
            ctypes.memset(buffer, 0, ctypes.sizeof(buffer))
            if outgoing.data:
                ctypes.memset(outgoing.data, 0, outgoing.size)
                self.kernel.LocalFree(outgoing.data)

    def protect(self, plaintext: bytes) -> bytes:
        return self._transform(plaintext, decrypt=False)

    def unprotect(self, protected: bytes) -> bytes:
        return self._transform(protected, decrypt=True)


def _valid_key(value: str) -> bool:
    # Client credentials become an HTTP bearer value; reject controls/whitespace.
    return 0 < len(value) <= MAX_KEY_BYTES and all(33 <= ord(c) <= 126 for c in value)


class ProtectedKeyStore:
    """Inject fake protection/files explicitly in non-Windows tests, never by OS fallback."""

    def __init__(self, files: KeyFiles, protection: Protection | None = None) -> None:
        self.files = files
        self.protection = protection

    def provision(self, key: SecretStr) -> None:
        """Create once; existing, corrupt or incomplete material requires explicit repair."""
        try:
            value = key.get_secret_value()
            if not _valid_key(value):
                raise ProtectedKeyError()
            plaintext = value.encode("ascii")
            protection = self.protection if self.protection is not None else CurrentUserDPAPI()
            protected = protection.protect(plaintext)
            if not 0 < len(protected) <= MAX_PROTECTED_BYTES:
                raise ProtectedKeyError()
            if protection.unprotect(protected) != plaintext:
                raise ProtectedKeyError()
            self.files.create(KEY_NAME, protected)
            if self.read() != key:
                raise ProtectedKeyError()
        except Exception:
            raise ProtectedKeyError() from None

    def read(self) -> SecretStr:
        """Resolve after restart; return only a redacted secret wrapper."""
        # shortcut: Python immutable secret copies cannot be wiped; use native memory for dump resistance.
        try:
            protected = self.files.read(KEY_NAME, MAX_PROTECTED_BYTES)
            if not 0 < len(protected) <= MAX_PROTECTED_BYTES:
                raise ProtectedKeyError()
            protection = self.protection if self.protection is not None else CurrentUserDPAPI()
            plaintext = protection.unprotect(protected)
            if not 0 < len(plaintext) <= MAX_KEY_BYTES:
                raise ProtectedKeyError()
            value = plaintext.decode("ascii")
            if not _valid_key(value):
                raise ProtectedKeyError()
            return SecretStr(value)
        except BridgeKeyMissingError:
            raise BridgeKeyMissingError() from None
        except Exception:
            raise ProtectedKeyError() from None


class FileInformation(ctypes.Structure):
    _fields_ = [
        ("attributes", wintypes.DWORD), ("created", wintypes.FILETIME),
        ("accessed", wintypes.FILETIME), ("written", wintypes.FILETIME),
        ("volume", wintypes.DWORD), ("size_high", wintypes.DWORD),
        ("size_low", wintypes.DWORD), ("links", wintypes.DWORD),
        ("index_high", wintypes.DWORD), ("index_low", wintypes.DWORD),
    ]


class WindowsNativeFiles:
    """Fixed LocalAppData files, exclusive creation and handle-based ACL checks.

    Existing ACLs are checked, never silently rewritten. Ancestor handles deny
    deletion while a read/create is in progress; files deny concurrent writes.
    Source: https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew
    Source: https://learn.microsoft.com/en-us/windows/win32/api/aclapi/nf-aclapi-getsecurityinfo
    """

    def __init__(self, operations: WindowsOperations, desktop: WindowsDesktop) -> None:
        self.operations = operations
        self.desktop = desktop
        self.kernel = operations.kernel
        self.security = operations.security
        local = os.environ.get("LOCALAPPDATA")
        self.base = _canonical_path(_windows_path(local, desktop), directory=True)
        self.root = self.base / "VocabularyApp"
        pointer = ctypes.c_void_p
        signatures = [
            (self.kernel, "CreateDirectoryW",
             [wintypes.LPCWSTR, ctypes.POINTER(SecurityAttributes)], wintypes.BOOL),
            (self.kernel, "GetFileInformationByHandle",
             [wintypes.HANDLE, ctypes.POINTER(FileInformation)], wintypes.BOOL),
            (self.kernel, "ReadFile",
             [wintypes.HANDLE, pointer, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), pointer],
             wintypes.BOOL),
            (self.kernel, "WriteFile",
             [wintypes.HANDLE, pointer, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), pointer],
             wintypes.BOOL),
            (self.kernel, "FlushFileBuffers", [wintypes.HANDLE], wintypes.BOOL),
            (self.security, "GetSecurityDescriptorControl",
             [pointer, ctypes.POINTER(wintypes.WORD), ctypes.POINTER(wintypes.DWORD)], wintypes.BOOL),
            (self.security, "GetAce",
             [pointer, wintypes.DWORD, ctypes.POINTER(pointer)], wintypes.BOOL),
        ]
        for library, name, arguments, result in signatures:
            function = getattr(library, name)
            function.argtypes = arguments
            function.restype = result

    def _descriptor(self, directory: bool) -> ctypes.c_void_p:
        descriptor = ctypes.c_void_p()
        inherit = "OICI" if directory else ""
        sid = self.operations.sid
        sddl = f"O:{sid}D:P(A;{inherit};FA;;;{sid})(A;{inherit};FA;;;SY)"
        if not self.security.ConvertStringSecurityDescriptorToSecurityDescriptorW(
            sddl, 1, ctypes.byref(descriptor), None,
        ):
            raise NativeFileError()
        return descriptor

    def _check_acl(self, handle: int, directory: bool, *, strict: bool = True) -> None:
        owner, acl, actual = ctypes.c_void_p(), ctypes.c_void_p(), ctypes.c_void_p()
        expected = self._descriptor(directory)
        try:
            if self.security.GetSecurityInfo(
                handle, 1, 5, ctypes.byref(owner), None, ctypes.byref(acl), None,
                ctypes.byref(actual),
            ) != 0 or not owner.value or self.operations._sid_text(owner) != self.operations.sid:
                raise NativeFileError()
            if not strict:
                # SQLite/Markdown inherit root permissions. Reject every other principal.
                self._check_learning_acl(acl)
                return
            control, revision = wintypes.WORD(), wintypes.DWORD()
            if not self.security.GetSecurityDescriptorControl(
                actual, ctypes.byref(control), ctypes.byref(revision),
            ) or not control.value & 0x1000:
                raise NativeFileError()
            present, defaulted, expected_acl = wintypes.BOOL(), wintypes.BOOL(), ctypes.c_void_p()
            if not self.security.GetSecurityDescriptorDacl(
                expected, ctypes.byref(present), ctypes.byref(expected_acl), ctypes.byref(defaulted),
            ) or not present.value:
                raise NativeFileError()
            if self.operations._acl_bytes(acl) != self.operations._acl_bytes(expected_acl):
                raise NativeFileError()
        finally:
            self.kernel.LocalFree(expected)
            if actual.value:
                self.kernel.LocalFree(actual)

    def _check_learning_acl(self, acl: ctypes.c_void_p) -> None:
        self.operations._acl_bytes(acl)
        count = ctypes.c_ushort.from_address(acl.value + 4).value
        if count == 0:
            raise NativeFileError()
        user_access = False
        for index in range(count):
            ace = ctypes.c_void_p()
            if not self.security.GetAce(acl, index, ctypes.byref(ace)) or not ace.value:
                raise NativeFileError()
            if ctypes.c_ubyte.from_address(ace.value).value != 0:
                raise NativeFileError()
            size = ctypes.c_ushort.from_address(ace.value + 2).value
            if size < 16:
                raise NativeFileError()
            sid = self.operations._sid_text(ctypes.c_void_p(ace.value + 8))
            if sid not in {self.operations.sid, "S-1-5-18"}:
                raise NativeFileError()
            mask = ctypes.c_ulong.from_address(ace.value + 4).value
            user_access = user_access or (sid == self.operations.sid and mask != 0)
        if not user_access:
            raise NativeFileError()

    @contextmanager
    def _open(
        self, path: Path, *, directory: bool, create: bool = False, protected: bool = True,
        strict_acl: bool = True,
    ) -> Iterator[int]:
        descriptor = self._descriptor(directory) if create else None
        handle = None
        try:
            attributes = SecurityAttributes(ctypes.sizeof(SecurityAttributes), descriptor, False)
            handle = self.kernel.CreateFileW(
                str(path), 0x20000 | (0x40000000 if create else 0x80000000),
                3 if directory else 1, ctypes.byref(attributes) if create else None,
                1 if create else 3, 0x02200000, None,
            )
            if handle in {None, ctypes.c_void_p(-1).value}:
                handle = None
                raise NativeFileError()
            info = FileInformation()
            if not self.kernel.GetFileInformationByHandle(handle, ctypes.byref(info)):
                raise NativeFileError()
            if info.attributes & 0x400 or bool(info.attributes & 0x10) != directory:
                raise NativeFileError()
            if not directory and info.links != 1:
                raise NativeFileError()
            final = ctypes.create_unicode_buffer(32768)
            length = self.kernel.GetFinalPathNameByHandleW(handle, final, len(final), 0)
            if not 0 < length < len(final):
                raise NativeFileError()
            final_path = final.value.removeprefix("\\\\?\\")
            if os.path.normcase(str(Path(final_path))) != os.path.normcase(str(path)):
                raise NativeFileError()
            if protected:
                self._check_acl(handle, directory, strict=strict_acl)
            yield handle
        except Exception:
            raise NativeFileError() from None
        finally:
            if handle is not None:
                self.operations.close(handle)
            if descriptor is not None:
                self.kernel.LocalFree(descriptor)

    @contextmanager
    def _ancestors(self, path: Path) -> Iterator[None]:
        with ExitStack() as stack:
            for parent in reversed(path.parents):
                stack.enter_context(self._open(
                    parent, directory=True,
                    protected=parent == self.root or parent.parent == self.root,
                ))
            yield

    def _path(self, name: str) -> Path:
        if name not in {CONFIG_NAME, KEY_NAME}:
            raise NativeFileError()
        return self.root / name

    def is_absent(self, name: str) -> bool:
        """Only a missing component beneath checked ancestors counts as absence."""
        path = self._path(name)
        try:
            with self._ancestors(self.root), ExitStack() as stack:
                for component in (*reversed(path.parents), path):
                    if not component.is_relative_to(self.root):
                        continue
                    try:
                        component.lstat()
                    except FileNotFoundError:
                        return True
                    stack.enter_context(self._open(component, directory=component != path))
                return False
        except Exception:
            raise NativeFileError() from None

    def ensure_directories(self) -> None:
        for path in (self.root, self.root / "secrets"):
            with self._ancestors(path):
                descriptor = self._descriptor(True)
                try:
                    attributes = SecurityAttributes(
                        ctypes.sizeof(SecurityAttributes), descriptor, False,
                    )
                    if not self.kernel.CreateDirectoryW(str(path), ctypes.byref(attributes)):
                        if ctypes.get_last_error() != 183:
                            raise NativeFileError()
                    with self._open(path, directory=True):
                        pass
                finally:
                    self.kernel.LocalFree(descriptor)

    @contextmanager
    def configuration_path(self) -> Iterator[Path]:
        path = self._path(CONFIG_NAME)
        with self._ancestors(path), self._open(path, directory=False):
            yield path

    def read(self, name: str, maximum: int) -> bytes:
        if not 0 < maximum <= MAX_PROTECTED_BYTES:
            raise NativeFileError()
        if name == KEY_NAME and self.is_absent(name):
            raise BridgeKeyMissingError()
        path = self._path(name)
        with self._ancestors(path), self._open(path, directory=False) as handle:
            buffer = ctypes.create_string_buffer(maximum + 1)
            count = wintypes.DWORD()
            if not self.kernel.ReadFile(handle, buffer, maximum + 1, ctypes.byref(count), None):
                raise NativeFileError()
            if count.value > maximum:
                raise NativeFileError()
            return buffer.raw[:count.value]

    def create(self, name: str, content: bytes) -> None:
        if not 0 < len(content) <= MAX_PROTECTED_BYTES:
            raise NativeFileError()
        path = self._path(name)
        with self._ancestors(path), self._open(path, directory=False, create=True) as handle:
            buffer = ctypes.create_string_buffer(content)
            count = wintypes.DWORD()
            if not self.kernel.WriteFile(handle, buffer, len(content), ctypes.byref(count), None):
                raise NativeFileError()
            if count.value != len(content) or not self.kernel.FlushFileBuffers(handle):
                # Keep an incomplete file for explicit repair; never retry/overwrite it.
                raise NativeFileError()

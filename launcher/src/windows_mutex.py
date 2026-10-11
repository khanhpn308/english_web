"""Current-user Windows synchronization; no handles or state leave this process."""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from enum import StrEnum
from time import monotonic, sleep
from typing import Protocol

MUTEX_NAME = r"Global\VocabularyApp-v1"
FOCUS_EVENT_NAME = r"Global\VocabularyApp-v1-focus"
WAIT_OBJECT_0 = 0
WAIT_ABANDONED = 0x80
WAIT_TIMEOUT = 0x102
READ_CONTROL = 0x20000
SYNCHRONIZE = 0x100000
MUTEX_ACCESS = READ_CONTROL | SYNCHRONIZE | 1
EVENT_ACCESS = READ_CONTROL | SYNCHRONIZE | 2


class InstanceRole(StrEnum):
    PRIMARY = "PRIMARY"
    RECOVERED = "RECOVERED"
    DUPLICATE = "DUPLICATE"


class SynchronizationError(RuntimeError):
    """Unsafe or unavailable synchronization, with no native diagnostic content."""


class PlatformOperations(Protocol):
    def create_mutex(self) -> int: ...
    def create_focus_event(self) -> int: ...
    def open_focus_event(self) -> int | None: ...
    def wait(self, handle: int, milliseconds: int) -> int: ...
    def signal(self, handle: int) -> None: ...
    def release(self, handle: int) -> None: ...
    def close(self, handle: int) -> None: ...


class SingleInstance:
    """The acquiring thread must also close the owned mutex."""

    def __init__(self, operations: PlatformOperations) -> None:
        self.operations = operations
        self.mutex: int | None = None
        self.focus_event: int | None = None
        self.role: InstanceRole | None = None

    def acquire(self) -> InstanceRole:
        if self.mutex is not None:
            raise SynchronizationError("Instance boundary already acquired")
        self.mutex = self.operations.create_mutex()
        try:
            result = self.operations.wait(self.mutex, 0)
            if result == WAIT_TIMEOUT:
                self.role = InstanceRole.DUPLICATE
            elif result in {WAIT_OBJECT_0, WAIT_ABANDONED}:
                self.role = (
                    InstanceRole.RECOVERED if result == WAIT_ABANDONED
                    else InstanceRole.PRIMARY
                )
                self.focus_event = self.operations.create_focus_event()
            else:
                raise SynchronizationError("Instance ownership unavailable")
            return self.role
        except BaseException:
            self.close()
            raise

    def request_focus(self) -> bool:
        """Signal delivery is not evidence that a browser tab was focused."""
        if self.role != InstanceRole.DUPLICATE or self.mutex is None:
            raise SynchronizationError("Focus requires an existing owner")
        deadline = monotonic() + 1.0
        while monotonic() < deadline:
            if not self._owner_running():
                return False
            # The primary may still be creating its event. Never create it here.
            event = self.operations.open_focus_event()
            if event is not None:
                try:
                    self.operations.signal(event)
                    return self._owner_running()
                finally:
                    self.operations.close(event)
            sleep(min(0.05, max(0.0, deadline - monotonic())))
        return False

    def _owner_running(self) -> bool:
        if self.mutex is None:
            return False
        result = self.operations.wait(self.mutex, 0)
        if result == WAIT_TIMEOUT:
            return True
        if result in {WAIT_OBJECT_0, WAIT_ABANDONED}:
            # Retain this ownership until close; this invocation never starts a backend.
            self.role = InstanceRole.RECOVERED
            return False
        raise SynchronizationError("Existing owner unavailable")

    def focus_requested(self, milliseconds: int = 100) -> bool:
        if self.focus_event is None or not 0 <= milliseconds <= 1000:
            raise SynchronizationError("Focus event unavailable")
        result = self.operations.wait(self.focus_event, milliseconds)
        if result not in {WAIT_OBJECT_0, WAIT_TIMEOUT}:
            raise SynchronizationError("Focus wait failed")
        return result == WAIT_OBJECT_0

    def close(self) -> None:
        event, mutex = self.focus_event, self.mutex
        role = self.role
        self.focus_event = self.mutex = None
        self.role = None
        try:
            if event is not None:
                self.operations.close(event)
        finally:
            if mutex is not None:
                try:
                    if role in {InstanceRole.PRIMARY, InstanceRole.RECOVERED}:
                        self.operations.release(mutex)
                finally:
                    self.operations.close(mutex)


class SecurityAttributes(ctypes.Structure):
    _fields_ = [
        ("nLength", wintypes.DWORD),
        ("lpSecurityDescriptor", ctypes.c_void_p),
        ("bInheritHandle", wintypes.BOOL),
    ]


class SidAndAttributes(ctypes.Structure):
    _fields_ = [("Sid", ctypes.c_void_p), ("Attributes", wintypes.DWORD)]


class TokenGroups(ctypes.Structure):
    _fields_ = [("GroupCount", wintypes.DWORD), ("Groups", SidAndAttributes * 1)]


class WindowsOperations:
    """Win32 handles allow the current user and SYSTEM, checked even on reopen.

    Sources: Microsoft Learn CreateMutexExW, GetSecurityInfo and
    ConvertStringSecurityDescriptorToSecurityDescriptorW.
    """

    def __init__(self) -> None:
        if os.name != "nt":
            raise SynchronizationError("Windows is required")
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.security = ctypes.WinDLL("advapi32", use_last_error=True)
        pointer = ctypes.c_void_p
        pointer_out = ctypes.POINTER(pointer)
        signatures = [
            (self.kernel, "GetCurrentProcess", [], wintypes.HANDLE),
            (self.kernel, "CloseHandle", [wintypes.HANDLE], wintypes.BOOL),
            (self.kernel, "LocalFree", [pointer], pointer),
            (self.kernel, "CreateMutexExW", [ctypes.POINTER(SecurityAttributes), wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD], wintypes.HANDLE),
            (self.kernel, "CreateEventExW", [ctypes.POINTER(SecurityAttributes), wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD], wintypes.HANDLE),
            (self.kernel, "OpenEventW", [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR], wintypes.HANDLE),
            (self.kernel, "WaitForSingleObject", [wintypes.HANDLE, wintypes.DWORD], wintypes.DWORD),
            (self.kernel, "ReleaseMutex", [wintypes.HANDLE], wintypes.BOOL),
            (self.kernel, "SetEvent", [wintypes.HANDLE], wintypes.BOOL),
            (self.security, "OpenProcessToken", [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)], wintypes.BOOL),
            (self.security, "GetTokenInformation", [wintypes.HANDLE, ctypes.c_int, pointer, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)], wintypes.BOOL),
            (self.security, "ConvertSidToStringSidW", [pointer, pointer_out], wintypes.BOOL),
            (self.security, "ConvertStringSecurityDescriptorToSecurityDescriptorW", [wintypes.LPCWSTR, wintypes.DWORD, pointer_out, ctypes.POINTER(wintypes.DWORD)], wintypes.BOOL),
            (self.security, "GetSecurityInfo", [wintypes.HANDLE, ctypes.c_int, wintypes.DWORD, pointer_out, pointer_out, pointer_out, pointer_out, pointer_out], wintypes.DWORD),
            (self.security, "GetSecurityDescriptorDacl", [pointer, ctypes.POINTER(wintypes.BOOL), pointer_out, ctypes.POINTER(wintypes.BOOL)], wintypes.BOOL),
        ]
        for library, name, arguments, result in signatures:
            function = getattr(library, name)
            function.argtypes = arguments
            function.restype = result
        self.sid, self.logon_sid = self._current_user_security()

    def _token_information(
        self, token: wintypes.HANDLE, information: int
    ) -> ctypes.Array[ctypes.c_char]:
        size = wintypes.DWORD()
        self.security.GetTokenInformation(token, information, None, 0, ctypes.byref(size))
        if ctypes.get_last_error() != 122 or not 0 < size.value <= 65536:
            raise SynchronizationError("User security boundary unavailable")
        buffer = ctypes.create_string_buffer(size.value)
        if not self.security.GetTokenInformation(token, information, buffer, size, ctypes.byref(size)):
            raise SynchronizationError("User security boundary unavailable")
        return buffer

    def _current_user_security(self) -> tuple[str, str]:
        token = wintypes.HANDLE()
        if not self.security.OpenProcessToken(self.kernel.GetCurrentProcess(), 8, ctypes.byref(token)):
            raise SynchronizationError("User security boundary unavailable")
        try:
            buffer = self._token_information(token, 1)
            sid = ctypes.c_void_p.from_buffer(buffer)
            user = self._sid_text(sid)
            groups = self._token_information(token, 2)
            count = wintypes.DWORD.from_buffer(groups).value
            offset = TokenGroups.Groups.offset
            if offset + count * ctypes.sizeof(SidAndAttributes) > len(groups):
                raise SynchronizationError("User security boundary unavailable")
            for index in range(count):
                group = SidAndAttributes.from_buffer(
                    groups, offset + index * ctypes.sizeof(SidAndAttributes)
                )
                if group.Attributes & 0xC0000000 == 0xC0000000:
                    return user, self._sid_text(ctypes.c_void_p(group.Sid))
            raise SynchronizationError("Interactive user session required")
        finally:
            self.close(token.value)

    def _sid_text(self, sid: ctypes.c_void_p) -> str:
        text = ctypes.c_void_p()
        if not self.security.ConvertSidToStringSidW(sid, ctypes.byref(text)):
            raise SynchronizationError("Object owner unavailable")
        try:
            return ctypes.wstring_at(text)
        finally:
            self.kernel.LocalFree(text)

    def _descriptor(self, access: int) -> ctypes.c_void_p:
        descriptor = ctypes.c_void_p()
        # The logon SID in the group field rejects the same user in another logon session.
        sddl = (
            f"O:{self.sid}G:{self.logon_sid}D:P"
            f"(A;;0x{access:08x};;;{self.sid})(A;;0x{access:08x};;;SY)"
        )
        if not self.security.ConvertStringSecurityDescriptorToSecurityDescriptorW(
            sddl, 1, ctypes.byref(descriptor), None
        ):
            raise SynchronizationError("Object protection unavailable")
        return descriptor

    def _acl_bytes(self, acl: ctypes.c_void_p) -> bytes:
        if not acl.value:
            raise SynchronizationError("Unsafe object protection")
        size = ctypes.c_ushort.from_address(acl.value + 2).value
        if not 8 <= size <= 65535:
            raise SynchronizationError("Unsafe object protection")
        return ctypes.string_at(acl, size)

    def _validate(self, handle: int, expected: ctypes.c_void_p) -> None:
        owner, group, acl, descriptor = (
            ctypes.c_void_p(), ctypes.c_void_p(), ctypes.c_void_p(), ctypes.c_void_p()
        )
        result = self.security.GetSecurityInfo(
            handle, 6, 7, ctypes.byref(owner), ctypes.byref(group), ctypes.byref(acl), None,
            ctypes.byref(descriptor),
        )
        try:
            if result != 0 or not owner.value or self._sid_text(owner) != self.sid:
                raise SynchronizationError("Unsafe object ownership")
            if not group.value or self._sid_text(group) != self.logon_sid:
                raise SynchronizationError("Existing instance belongs to another logon session")
            present, defaulted, expected_acl = wintypes.BOOL(), wintypes.BOOL(), ctypes.c_void_p()
            if not self.security.GetSecurityDescriptorDacl(
                expected, ctypes.byref(present), ctypes.byref(expected_acl), ctypes.byref(defaulted)
            ) or not present.value or self._acl_bytes(acl) != self._acl_bytes(expected_acl):
                raise SynchronizationError("Unsafe object protection")
        finally:
            if descriptor.value:
                self.kernel.LocalFree(descriptor)

    def _create(self, name: str, access: int, event: bool) -> int:
        descriptor = self._descriptor(access)
        try:
            attributes = SecurityAttributes(ctypes.sizeof(SecurityAttributes), descriptor, False)
            create = self.kernel.CreateEventExW if event else self.kernel.CreateMutexExW
            ctypes.set_last_error(0)
            handle = create(ctypes.byref(attributes), name, 0, access)
            preexisting = ctypes.get_last_error() == 183
            if not handle:
                raise SynchronizationError("Synchronization object unavailable")
            try:
                if event and preexisting:
                    # An existing event could be manual-reset, regardless of its ACL.
                    raise SynchronizationError("Pre-created focus event rejected")
                self._validate(handle, descriptor)
                return handle
            except BaseException:
                self.close(handle)
                raise
        finally:
            self.kernel.LocalFree(descriptor)

    def create_mutex(self) -> int:
        return self._create(MUTEX_NAME, MUTEX_ACCESS, False)

    def create_focus_event(self) -> int:
        return self._create(FOCUS_EVENT_NAME, EVENT_ACCESS, True)

    def open_focus_event(self) -> int | None:
        handle = self.kernel.OpenEventW(READ_CONTROL | 2, False, FOCUS_EVENT_NAME)
        if not handle:
            if ctypes.get_last_error() == 2:
                return None
            raise SynchronizationError("Existing instance unavailable")
        descriptor = None
        try:
            descriptor = self._descriptor(EVENT_ACCESS)
            self._validate(handle, descriptor)
            return handle
        except BaseException:
            self.close(handle)
            raise
        finally:
            if descriptor is not None:
                self.kernel.LocalFree(descriptor)

    def wait(self, handle: int, milliseconds: int) -> int:
        return self.kernel.WaitForSingleObject(handle, milliseconds)

    def signal(self, handle: int) -> None:
        if not self.kernel.SetEvent(handle):
            raise SynchronizationError("Existing instance unavailable")

    def release(self, handle: int) -> None:
        if not self.kernel.ReleaseMutex(handle):
            raise SynchronizationError("Instance release failed")

    def close(self, handle: int) -> None:
        if not self.kernel.CloseHandle(handle):
            raise SynchronizationError("Instance handle cleanup failed")

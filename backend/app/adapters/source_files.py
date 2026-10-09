"""Allowlisted source file adapter for local-first Markdown storage (T021).

Security Boundary & Concurrency Design:
- Uses bounded, validated opaque source IDs resolved through allowlisted backend metadata.
- Re-verifies root directory identity and inspects all intermediate path components at prepare
  and commit.
- Enforces strict path traversal barriers (no dot-dot, rooted, drive-relative,
  UNC, alternate data streams, device names, or alias escapes).
- Detects and rejects symlinks, junctions, reparse points, hardlinks (nlink > 1),
  non-regular files, and read-only targets.
- Pre-replacement validation: re-reads target bytes, checks SHA-256 content hash,
  rechecks source registration status and metadata, and confirms Markdown validity.
- Durability: writes exclusive temporary file in destination directory, flushes,
  fsyncs, captures open descriptor identity, closes, revalidates, and performs
  atomic replacement (os.replace).
- Temp authentication: verifies staged file descriptor identity, regular file,
  absence of links/reparse, exactly one link, bounded size, and byte/hash match.
- Safe cleanup: verifies boundary and descriptor identity before unlinking; never
  unlinks through substituted directories, links, or outside files.
- Fail-closed: failures before replacement preserve originals and clean up owned
  temporary files.
- Privacy: error objects and logs contain bounded source IDs and error categories
  only; never raw paths, file contents, usernames, or security descriptors.

Accepted Residual Risk:
Between validation rechecks and OS replacement, a concurrent process with identical
user privileges could theoretically alter directory entries or file content. While
the adapter performs multi-point revalidation (root identity, intermediate directory
traversal checks, file identity via device/inode, size caps, staged file descriptor
authentication, and byte-hash comparison immediately prior to atomic replacement),
POSIX and standard Windows filesystem APIs without exclusive handle locking across
all operations cannot guarantee complete immunity against same-user races. This is
an accepted design residual documented in docs/security-review.md (T-07) and ADR-0005.
"""

from __future__ import annotations

import contextlib
import ctypes
import hashlib
import os
import stat
import sys
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any, Final

from backend.app.markdown_sync.parser import (
    MAX_SOURCE_SIZE_BYTES as PARSER_MAX_BYTES,
)
from backend.app.markdown_sync.parser import (
    parse_markdown,
)
from backend.app.vocabulary.models import SourceFile

MAX_SOURCE_SIZE_BYTES: Final[int] = PARSER_MAX_BYTES  # 8 MiB (8,388,608 bytes)
MAX_SOURCE_ID_LENGTH: Final[int] = 64
_SAFE_ID_CHARS: Final[frozenset[str]] = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
)

RESERVED_DEVICE_NAMES: Final[frozenset[str]] = frozenset(
    {
        "con",
        "prn",
        "aux",
        "nul",
        "com1",
        "com2",
        "com3",
        "com4",
        "com5",
        "com6",
        "com7",
        "com8",
        "com9",
        "lpt1",
        "lpt2",
        "lpt3",
        "lpt4",
        "lpt5",
        "lpt6",
        "lpt7",
        "lpt8",
        "lpt9",
    }
)


def _is_valid_source_id(source_id: Any) -> bool:
    """Check if source_id is a bounded, valid opaque identifier.

    Only alphanumeric characters, underscores, and hyphens up to 64 chars are allowed.
    Path characters, control characters, newlines, and oversized strings are rejected.
    """
    if not isinstance(source_id, str):
        return False
    if not (1 <= len(source_id) <= MAX_SOURCE_ID_LENGTH):
        return False
    return all(c in _SAFE_ID_CHARS for c in source_id)


def _sanitize_source_id(source_id: Any) -> str | None:
    """Return bounded valid opaque identifier, or None if invalid/untrusted.

    Ensures untrusted or invalid identifiers (such as path traversal strings,
    newlines, control characters, or oversized sentinels) are omitted from diagnostics.
    """
    return source_id if _is_valid_source_id(source_id) else None


class SourceFileError(Exception):
    """Base exception for source file adapter operations.

    Privacy guarantee: Never contains raw filesystem paths, Markdown content,
    user/account identities, SIDs, or raw OS error text.
    Only bounded, validated opaque source identifiers are permitted in diagnostics.
    """

    def __init__(self, code: str, message: str, source_id: str | None = None) -> None:
        self.code = code
        self.message = message
        self.source_id = _sanitize_source_id(source_id)
        prefix = f"[{code}]"
        if self.source_id:
            prefix += f" (source_id={self.source_id})"
        super().__init__(f"{prefix} {message}")


class SourceSecurityError(SourceFileError):
    """Path traversal, symlink, junction, reparse point, hardlink, or root identity violation."""


class SourceConflictError(SourceFileError):
    """Content hash mismatch, external concurrent edit, or revision conflict."""


class SourceValidationError(SourceFileError):
    """Payload too large, invalid encoding, or invalid Markdown structure."""


class SourceAccessError(SourceFileError):
    """Access denied, read-only file/directory, or permission failure."""


@dataclass(frozen=True)
class ReplacementReceipt:
    """Safe, bounded receipt for a completed atomic replacement operation."""

    source_id: str
    relative_path: str
    old_content_hash: str
    new_content_hash: str
    bytes_written: int
    replaced_at: float


@dataclass(frozen=True)
class StagedTempHandle:
    """Validated source-relative locator and descriptor identity for restart cleanup."""

    source_id: str
    relative_path: str
    device: int
    inode: int
    content_hash: str


def validate_relative_path(relative_path: str, source_id: str | None = None) -> list[str]:
    """Validate relative path string against traversal, ADS, and Windows namespace escapes.

    Returns the list of safe component strings.
    """
    if not relative_path or not relative_path.strip():
        raise SourceFileError("INVALID_SOURCE_PATH", "Relative path cannot be empty", source_id)

    if "\0" in relative_path:
        raise SourceFileError("INVALID_SOURCE_PATH", "Path contains null byte", source_id)

    # Reject Windows drive specifiers or alternate data streams (any colon)
    if ":" in relative_path:
        raise SourceFileError(
            "INVALID_SOURCE_PATH",
            "Path contains drive letter or alternate data stream",
            source_id,
        )

    # Reject absolute/rooted/UNC/device paths
    if relative_path.startswith(("/", "\\")):
        raise SourceFileError(
            "INVALID_SOURCE_PATH", "Path must be relative, not rooted or absolute", source_id
        )

    if relative_path.startswith(("//", "\\\\")):
        raise SourceFileError(
            "INVALID_SOURCE_PATH", "Path contains UNC or device prefix", source_id
        )

    # Normalize backslashes to forward slashes for uniform component analysis
    normalized = relative_path.replace("\\", "/")
    raw_components = normalized.split("/")
    safe_components: list[str] = []

    for comp in raw_components:
        if not comp:
            raise SourceFileError(
                "INVALID_SOURCE_PATH",
                "Path contains empty component or repeated slashes",
                source_id,
            )
        if comp in {".", ".."}:
            raise SourceSecurityError(
                "INVALID_SOURCE_PATH", "Path traversal component detected", source_id
            )

        # Trailing dots or spaces are stripped or aliased by Windows filesystem
        if comp.endswith((".", " ")):
            raise SourceFileError(
                "INVALID_SOURCE_PATH", "Path component contains trailing dot or space", source_id
            )

        # Check Windows reserved device names (e.g. CON, NUL, COM1.txt)
        stem = comp.split(".")[0].lower()
        if stem in RESERVED_DEVICE_NAMES:
            raise SourceFileError(
                "INVALID_SOURCE_PATH", "Path component matches reserved device name", source_id
            )

        safe_components.append(comp)

    # PurePosixPath safety check
    pure = PurePosixPath(*safe_components)
    if pure.is_absolute() or ".." in pure.parts:
        raise SourceSecurityError(
            "INVALID_SOURCE_PATH", "Path resolution escapes allowed root", source_id
        )

    return safe_components


def _is_reparse_or_link(path: Path | str, st: os.stat_result | None = None) -> bool:
    """Detect if path is a symlink, junction, or reparse point."""
    p_str = str(path)
    if os.path.islink(p_str):
        return True
    isjunction_fn = getattr(os.path, "isjunction", None)
    if isjunction_fn is not None and isjunction_fn(p_str):
        return True

    if st is None:
        try:
            st = os.stat(p_str, follow_symlinks=False)
        except OSError:
            return False

    attrs = getattr(st, "st_file_attributes", 0)
    reparse_attr = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if attrs and (attrs & reparse_attr):
        return True

    reparse_tag = getattr(st, "st_reparse_tag", 0)
    return bool(reparse_tag != 0)


def _check_windows_ownership(path: Path) -> bool:
    """Verify file ownership on native Windows via standard ctypes.

    On non-Windows platforms, returns True.
    On Windows:
    - Fails closed if APIs are unavailable or fail.
    - Sets explicit ctypes argtypes and restypes for 64-bit safety.
    - Frees allocated security descriptors and handles in finally blocks.
    """
    if sys.platform != "win32":
        return True

    windll: Any = getattr(ctypes, "windll", None)
    if windll is None:
        return False

    try:
        advapi32 = windll.advapi32
        kernel32 = windll.kernel32

        # Configure ctypes signatures for 64-bit safety
        kernel32.GetCurrentProcess.argtypes = []
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p

        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle.restype = ctypes.c_int

        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        kernel32.LocalFree.restype = ctypes.c_void_p

        advapi32.OpenProcessToken.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_void_p),
        ]
        advapi32.OpenProcessToken.restype = ctypes.c_int

        advapi32.GetTokenInformation.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_ulong),
        ]
        advapi32.GetTokenInformation.restype = ctypes.c_int

        advapi32.GetNamedSecurityInfoW.argtypes = [
            ctypes.c_wchar_p,
            ctypes.c_int,
            ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_void_p),
        ]
        advapi32.GetNamedSecurityInfoW.restype = ctypes.c_ulong

        advapi32.EqualSid.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        advapi32.EqualSid.restype = ctypes.c_int

        owner_info = 1
        se_file = 1
        query = 8
        token_user_type = 1

        proc = kernel32.GetCurrentProcess()
        tok = ctypes.c_void_p()
        if not advapi32.OpenProcessToken(proc, query, ctypes.byref(tok)) or not tok:
            return False

        try:
            buf_len = ctypes.c_ulong(0)
            advapi32.GetTokenInformation(tok, token_user_type, None, 0, ctypes.byref(buf_len))
            if buf_len.value == 0:
                return False

            buf = ctypes.create_string_buffer(buf_len.value)
            if not advapi32.GetTokenInformation(
                tok, token_user_type, buf, buf_len.value, ctypes.byref(buf_len)
            ):
                return False

            user_sid = ctypes.cast(buf, ctypes.POINTER(ctypes.c_void_p)).contents
            p_owner = ctypes.c_void_p()
            p_sd = ctypes.c_void_p()

            res = advapi32.GetNamedSecurityInfoW(
                str(path),
                se_file,
                owner_info,
                ctypes.byref(p_owner),
                None,
                None,
                None,
                ctypes.byref(p_sd),
            )
            if res != 0 or not p_sd:
                return False

            try:
                if not p_owner:
                    return False
                return bool(advapi32.EqualSid(user_sid, p_owner))
            finally:
                kernel32.LocalFree(p_sd)
        finally:
            kernel32.CloseHandle(tok)
    except Exception:
        return False


def _safe_cleanup_temp(
    root_path: Path,
    expected_root_id: tuple[int, int],
    intermediate_dirs: list[tuple[Path, tuple[int, int]]],
    target_dir: Path,
    target_dir_stat: tuple[int, int],
    temp_path: Path,
    initial_temp_stat: tuple[int, int] | None,
) -> bool:
    """Safely unlink an authenticated temporary file inside allowlist boundary.

    Validates in root-to-temp order:
    1. Configured root directory identity, directory type, and no reparse/link.
    2. Every captured intermediate directory in root-to-temp order
       (identity, dir type, no reparse/link).
    3. Immediate parent directory (identity, dir type, no reparse/link).
    4. Temporary file descriptor identity match (st_dev, st_ino), regular file,
       no reparse/link, and exactly one hardlink (st_nlink == 1).

    If descriptor identity was not captured or any check fails or cannot be proven,
    the entry is retained. Suppresses filesystem errors so caller's primary typed
    exception is preserved.
    """
    if initial_temp_stat is None:
        return False

    try:
        # 1. Authenticate root directory
        root_st = os.stat(root_path, follow_symlinks=False)
        if (root_st.st_dev, root_st.st_ino) != expected_root_id:
            return False
        if _is_reparse_or_link(root_path, root_st):
            return False
        if not stat.S_ISDIR(root_st.st_mode):
            return False

        # 2. Authenticate intermediate directories in root-to-temp order
        for dir_path, expected_id in intermediate_dirs:
            dir_st = os.stat(dir_path, follow_symlinks=False)
            if (dir_st.st_dev, dir_st.st_ino) != expected_id:
                return False
            if _is_reparse_or_link(dir_path, dir_st):
                return False
            if not stat.S_ISDIR(dir_st.st_mode):
                return False

        # 3. Authenticate immediate parent directory
        target_dir_st = os.stat(target_dir, follow_symlinks=False)
        if (target_dir_st.st_dev, target_dir_st.st_ino) != target_dir_stat:
            return False
        if _is_reparse_or_link(target_dir, target_dir_st):
            return False
        if not stat.S_ISDIR(target_dir_st.st_mode):
            return False

        # 4. Authenticate temporary file against captured descriptor identity
        temp_st = os.stat(temp_path, follow_symlinks=False)
        if (temp_st.st_dev, temp_st.st_ino) != initial_temp_stat:
            return False
        if _is_reparse_or_link(temp_path, temp_st):
            return False
        if not stat.S_ISREG(temp_st.st_mode):
            return False
        if temp_st.st_nlink != 1:
            return False

        temp_path.unlink()
        return True
    except Exception:
        return False


class StagedWrite:
    """Encapsulates a staged temporary write ready for atomic commit or cleanup."""

    def __init__(
        self,
        adapter: SourceFileAdapter,
        source: SourceFile,
        target_path: Path,
        temp_path: Path,
        expected_content_hash: str,
        new_content_hash: str,
        new_bytes: bytes,
        initial_target_stat: tuple[int, int] | None,
        initial_temp_stat: tuple[int, int],
        target_dir_stat: tuple[int, int],
        intermediate_dirs: list[tuple[Path, tuple[int, int]]],
    ) -> None:
        self.source_id = source.id
        self.relative_path = source.relative_path
        self.expected_content_hash = expected_content_hash
        self.new_content_hash = new_content_hash
        self.bytes_written = len(new_bytes)
        self._adapter = adapter
        self._source = source
        self._target_path = target_path
        self._temp_path = temp_path
        self._new_bytes = new_bytes
        self._initial_target_stat = initial_target_stat
        self._initial_temp_stat = initial_temp_stat
        self._target_dir_stat = target_dir_stat
        self._intermediate_dirs = intermediate_dirs
        self._committed = False
        self._cleaned_up = False

    @property
    def recovery_handle(self) -> StagedTempHandle:
        """Expose only the bounded relative locator and authenticated staged identity."""
        return StagedTempHandle(
            source_id=self.source_id,
            relative_path=self._temp_path.relative_to(self._adapter.root_path).as_posix(),
            device=self._initial_temp_stat[0],
            inode=self._initial_temp_stat[1],
            content_hash=self.new_content_hash,
        )

    def commit(self) -> ReplacementReceipt:
        """Perform final pre-replacement revalidation and atomically replace target."""
        if self._committed:
            raise SourceFileError(
                "OPERATION_ALREADY_COMMITTED",
                "Staged write has already been committed",
                self.source_id,
            )
        if self._cleaned_up:
            raise SourceFileError(
                "OPERATION_ABORTED", "Staged write has already been cleaned up", self.source_id
            )

        try:
            # 1. Recheck current source authorization in allowlist
            current_source = self._adapter.get_source(self.source_id)
            if current_source is None:
                raise SourceFileError(
                    "SOURCE_NOT_FOUND",
                    "Source registration missing before replacement",
                    self.source_id,
                )

            if current_source.status != "VALID" and self._initial_target_stat is not None:
                raise SourceFileError(
                    "SOURCE_NOT_WRITABLE",
                    "Source status cannot be modified",
                    self.source_id,
                )
            if self._initial_target_stat is None and (
                current_source.status != "MISSING" or current_source.revision != 0
                or current_source.error_code != "CREATION_PENDING"
            ):
                raise SourceFileError("SOURCE_NOT_WRITABLE", "Creation reservation is unavailable")

            if (
                current_source.relative_path != self._source.relative_path
                or current_source.note_date != self._source.note_date
                or current_source.revision != self._source.revision
                or current_source.etag != self._source.etag
                or current_source.content_hash != self._source.content_hash
            ):
                raise SourceConflictError(
                    "REVISION_CONFLICT",
                    "Source registration metadata changed before replacement",
                    self.source_id,
                )

            # 2. Re-check root directory identity
            self._adapter._recheck_root()

            # 3. Re-check every intermediate directory component from root to destination
            for dir_path, expected_id in self._intermediate_dirs:
                try:
                    dir_st = os.stat(dir_path, follow_symlinks=False)
                except OSError:
                    raise SourceSecurityError(
                        "SECURITY_VIOLATION",
                        "Intermediate directory missing or replaced",
                        self.source_id,
                    ) from None

                if _is_reparse_or_link(dir_path, dir_st):
                    raise SourceSecurityError(
                        "SECURITY_VIOLATION",
                        "Intermediate directory became a link or reparse point",
                        self.source_id,
                    )

                if not stat.S_ISDIR(dir_st.st_mode):
                    raise SourceSecurityError(
                        "SECURITY_VIOLATION",
                        "Intermediate component is not a directory",
                        self.source_id,
                    )

                if (dir_st.st_dev, dir_st.st_ino) != expected_id:
                    raise SourceSecurityError(
                        "SECURITY_VIOLATION",
                        "Intermediate directory identity changed",
                        self.source_id,
                    )

                if not os.access(dir_path, os.W_OK | os.X_OK):
                    raise SourceAccessError(
                        "ACCESS_DENIED",
                        "Intermediate directory is not writable",
                        self.source_id,
                    )

                if not _check_windows_ownership(dir_path):
                    raise SourceAccessError(
                        "ACCESS_DENIED",
                        "Intermediate directory ownership verification failed",
                        self.source_id,
                    )

            if self._initial_target_stat is None:
                self._adapter.assert_creation_absent(current_source)
                return self._publish_create()

            # 4. Re-check target file state and identity
            try:
                current_st = os.stat(self._target_path, follow_symlinks=False)
            except OSError:
                raise SourceConflictError(
                    "REVISION_CONFLICT",
                    "Target file disappeared or became inaccessible before replacement",
                    self.source_id,
                ) from None

            current_id = (current_st.st_dev, current_st.st_ino)
            if current_id != self._initial_target_stat:
                raise SourceConflictError(
                    "REVISION_CONFLICT",
                    "Target file identity changed before replacement",
                    self.source_id,
                )

            # Re-check reparse / symlink / hardlink / permissions
            if _is_reparse_or_link(self._target_path, current_st):
                raise SourceSecurityError(
                    "SECURITY_VIOLATION",
                    "Target file became a symlink or reparse point before replacement",
                    self.source_id,
                )

            if current_st.st_nlink > 1:
                raise SourceSecurityError(
                    "SECURITY_VIOLATION",
                    "Target file was hardlinked before replacement",
                    self.source_id,
                )

            readonly_attr = getattr(stat, "FILE_ATTRIBUTE_READONLY", 0x01)
            file_attrs = getattr(current_st, "st_file_attributes", 0)
            if (file_attrs & readonly_attr) or not os.access(self._target_path, os.W_OK):
                raise SourceAccessError(
                    "ACCESS_DENIED",
                    "Target file became read-only before replacement",
                    self.source_id,
                )

            if not _check_windows_ownership(self._target_path):
                raise SourceAccessError(
                    "ACCESS_DENIED",
                    "Target file ownership verification failed",
                    self.source_id,
                )

            # 5. Re-read target bytes and verify content hash
            try:
                disk_bytes = self._target_path.read_bytes()
            except OSError:
                raise SourceFileError(
                    "IO_ERROR", "Failed to re-read target file bytes", self.source_id
                ) from None

            current_hash = hashlib.sha256(disk_bytes).hexdigest()
            if current_hash != self.expected_content_hash:
                raise SourceConflictError(
                    "REVISION_CONFLICT",
                    "Target file content changed concurrently before replacement",
                    self.source_id,
                )

            # 6. Re-check staged temp file state and authenticate
            try:
                temp_st = os.stat(self._temp_path, follow_symlinks=False)
            except OSError:
                raise SourceFileError(
                    "IO_ERROR",
                    "Temporary staged file missing before replacement",
                    self.source_id,
                ) from None

            if (temp_st.st_dev, temp_st.st_ino) != self._initial_temp_stat:
                raise SourceSecurityError(
                    "SECURITY_VIOLATION",
                    "Temporary file identity changed before replacement",
                    self.source_id,
                )

            if _is_reparse_or_link(self._temp_path, temp_st):
                raise SourceSecurityError(
                    "SECURITY_VIOLATION",
                    "Temporary file is a symlink or reparse point",
                    self.source_id,
                )

            if not stat.S_ISREG(temp_st.st_mode):
                raise SourceSecurityError(
                    "SECURITY_VIOLATION",
                    "Temporary file is not a regular file",
                    self.source_id,
                )

            if temp_st.st_nlink != 1:
                raise SourceSecurityError(
                    "SECURITY_VIOLATION",
                    "Temporary file has multiple hard links",
                    self.source_id,
                )

            if temp_st.st_size != len(self._new_bytes) or temp_st.st_size > MAX_SOURCE_SIZE_BYTES:
                raise SourceValidationError(
                    "PAYLOAD_TOO_LARGE",
                    "Temporary file size differs from prepared content",
                    self.source_id,
                )

            try:
                temp_disk_bytes = self._temp_path.read_bytes()
            except OSError:
                raise SourceFileError(
                    "IO_ERROR", "Failed to verify temporary staged file bytes", self.source_id
                ) from None

            if temp_disk_bytes != self._new_bytes:
                raise SourceConflictError(
                    "REVISION_CONFLICT",
                    "Temporary file content was modified concurrently",
                    self.source_id,
                )

            if hashlib.sha256(temp_disk_bytes).hexdigest() != self.new_content_hash:
                raise SourceConflictError(
                    "REVISION_CONFLICT",
                    "Temporary file hash does not match expected hash",
                    self.source_id,
                )

            # 7. Atomic replacement
            replaced_at = time.time()
            try:
                os.replace(self._temp_path, self._target_path)
            except OSError:
                raise SourceFileError(
                    "IO_ERROR", "Atomic replacement failed during os.replace", self.source_id
                ) from None

            self._committed = True
            return ReplacementReceipt(
                source_id=self.source_id,
                relative_path=self.relative_path,
                old_content_hash=self.expected_content_hash,
                new_content_hash=self.new_content_hash,
                bytes_written=len(temp_disk_bytes),
                replaced_at=replaced_at,
            )
        except OSError:
            raise SourceFileError("IO_ERROR", "Staged publication failed", self.source_id) from None
        finally:
            if not self._committed:
                self.cleanup()

    def cleanup(self) -> None:
        """Safely delete owned temporary file if replacement was not committed.

        Cleanup boundary guarantee:
        - Only unlinks if self._temp_path is verified to be within the validated boundary
          and matches the original adapter-owned temporary file descriptor identity.
        - Checks root, every captured intermediate directory in root-to-temp order,
          the immediate parent directory, and descriptor identity before unlinking.
        - Never removes a substituted entry, link, or outside file.
        - An inaccessible temporary file when boundary validation fails is an accepted
          cleanup limitation rather than risking unlinking through an unsafe path.
        """
        if self._cleaned_up:
            return
        self._cleaned_up = True
        if self._committed:
            return

        # Suppress all cleanup errors so primary typed exceptions are never masked
        with contextlib.suppress(Exception):
            _safe_cleanup_temp(
                root_path=self._adapter._root_path,
                expected_root_id=self._adapter._root_identity,
                intermediate_dirs=self._intermediate_dirs,
                target_dir=self._target_path.parent,
                target_dir_stat=self._target_dir_stat,
                temp_path=self._temp_path,
                initial_temp_stat=self._initial_temp_stat,
            )

    def _publish_create(self) -> ReplacementReceipt:
        """Publish authenticated bytes without an overwrite-capable primitive."""
        handle = self.recovery_handle
        temp_st = os.stat(self._temp_path, follow_symlinks=False)
        if (
            (temp_st.st_dev, temp_st.st_ino) != (handle.device, handle.inode)
            or not stat.S_ISREG(temp_st.st_mode)
            or _is_reparse_or_link(self._temp_path, temp_st)
            or temp_st.st_nlink != 1
            or temp_st.st_size != self.bytes_written
            or not _check_windows_ownership(self._temp_path)
        ):
            raise SourceSecurityError("SECURITY_VIOLATION", "Staged creation identity changed")
        if self._temp_path.read_bytes() != self._new_bytes:
            raise SourceConflictError("REVISION_CONFLICT", "Staged creation content changed")
        published_at = time.time()
        try:
            if sys.platform == "win32":
                # MOVEFILE_WRITE_THROUGH, deliberately WITHOUT REPLACE_EXISTING.
                kernel = ctypes.WinDLL("kernel32", use_last_error=True)
                move = kernel.MoveFileExW
                move.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
                move.restype = ctypes.c_int
                if not move(str(self._temp_path), str(self._target_path), 0x8):
                    error = ctypes.get_last_error()
                    if error in {80, 183}:
                        raise FileExistsError
                    raise OSError(error, "Conditional publication failed")
            else:
                # linkat is atomic and fails with EEXIST. A pinned directory prevents
                # ancestor substitution from redirecting publication outside the root.
                with self._adapter._creation_directory(self._target_dir_stat) as directory:
                    os.link(
                        self._temp_path.name,
                        self._target_path.name,
                        src_dir_fd=directory,
                        dst_dir_fd=directory,
                        follow_symlinks=False,
                    )
                    os.fsync(directory)
                    os.unlink(self._temp_path.name, dir_fd=directory)
                    os.fsync(directory)
        except FileExistsError:
            raise SourceConflictError(
                "REVISION_CONFLICT", "Creation destination appeared"
            ) from None
        except (OSError, NotImplementedError):
            # Unsupported hard links/directory durability fail closed; no replace fallback.
            raise SourceFileError("IO_ERROR", "Conditional publication failed") from None
        self._adapter._recheck_root()
        self._committed = True
        return ReplacementReceipt(
            self.source_id,
            self.relative_path,
            self.expected_content_hash,
            self.new_content_hash,
            self.bytes_written,
            published_at,
        )


class SourceFileAdapter:
    """Allowlisted file adapter for safe, durable Markdown source storage."""

    def __init__(
        self,
        root_path: str | Path,
        allowlist: dict[str, SourceFile] | None = None,
    ) -> None:
        raw_root = Path(root_path)
        if _is_reparse_or_link(raw_root):
            raise SourceSecurityError(
                "SECURITY_VIOLATION", "Configured root directory is a symlink or reparse point"
            )
        self._root_path = raw_root.resolve()
        self._sources: dict[str, SourceFile] = {}
        self._root_identity = self._validate_and_capture_root()

        if allowlist:
            for src in allowlist.values():
                self.register_source(src)

    @property
    def root_path(self) -> Path:
        return self._root_path

    def _validate_and_capture_root(self) -> tuple[int, int]:
        """Validate configured root directory and capture its filesystem identity."""
        if not self._root_path.exists() or not self._root_path.is_dir():
            raise SourceFileError(
                "ROOT_NOT_FOUND", "Configured root directory does not exist or is not a directory"
            )

        # Root depth check: root cannot be filesystem/drive root
        if len(self._root_path.parts) <= 1:
            raise SourceSecurityError(
                "INVALID_SOURCE_PATH", "Configured root cannot be a filesystem drive root"
            )

        try:
            st = os.stat(self._root_path, follow_symlinks=False)
        except OSError:
            raise SourceFileError(
                "ROOT_NOT_FOUND", "Cannot stat configured root directory"
            ) from None

        if _is_reparse_or_link(self._root_path, st):
            raise SourceSecurityError(
                "SECURITY_VIOLATION", "Configured root directory is a symlink or reparse point"
            )

        if not os.access(self._root_path, os.R_OK | os.W_OK | os.X_OK):
            raise SourceAccessError("ACCESS_DENIED", "Configured root directory is not writable")

        return (st.st_dev, st.st_ino)

    def _recheck_root(self) -> None:
        """Re-verify root directory identity has not changed or been substituted."""
        try:
            if not self._root_path.exists() or not self._root_path.is_dir():
                raise SourceSecurityError(
                    "ROOT_IDENTITY_CHANGED", "Root directory missing or replaced"
                )
            st = os.stat(self._root_path, follow_symlinks=False)
        except OSError:
            raise SourceSecurityError(
                "ROOT_IDENTITY_CHANGED", "Cannot stat root directory"
            ) from None

        if (st.st_dev, st.st_ino) != self._root_identity:
            raise SourceSecurityError("ROOT_IDENTITY_CHANGED", "Root directory identity changed")

        if _is_reparse_or_link(self._root_path, st):
            raise SourceSecurityError(
                "SECURITY_VIOLATION", "Root directory was replaced with a link or junction"
            )

    def register_source(self, source: SourceFile) -> None:
        """Register an allowlisted source file after validating path metadata."""
        if not source.id or not _is_valid_source_id(source.id):
            raise SourceFileError(
                "INVALID_SOURCE_ID",
                "Source ID must be a bounded opaque identifier",
                source_id=None,
            )

        validate_relative_path(source.relative_path, source.id)
        self._sources[source.id] = source

    def get_source(self, source_id: str) -> SourceFile | None:
        return self._sources.get(source_id)

    def creation_path(self, note_date: str) -> str:
        """Only backend calendar dates produce new destination paths."""
        parsed = date.fromisoformat(note_date)
        if parsed.isoformat() != note_date:
            raise SourceValidationError("INVALID_SOURCE_PATH", "Invalid note date")
        path = f"{parsed.day:02d}-{parsed.month:02d}-{parsed.year:04d}.md"
        validate_relative_path(path)
        return path

    @contextmanager
    def _creation_directory(self, identity: tuple[int, int]) -> Iterator[int]:
        self._recheck_root()
        if not os.access(self._root_path, os.R_OK | os.W_OK | os.X_OK) or (
            not _check_windows_ownership(self._root_path)
        ):
            raise SourceAccessError("ACCESS_DENIED", "Source root ownership is unavailable")
        descriptor = os.open(self._root_path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            opened = os.fstat(descriptor)
            if (opened.st_dev, opened.st_ino) != identity:
                raise SourceSecurityError("SECURITY_VIOLATION", "Source root identity changed")
            yield descriptor
        finally:
            os.close(descriptor)

    def assert_creation_absent(self, source: SourceFile) -> None:
        self._recheck_root()
        if source.relative_path != self.creation_path(source.note_date):
            raise SourceSecurityError("INVALID_SOURCE_PATH", "Creation path is not canonical")
        if not os.access(self._root_path, os.R_OK | os.W_OK | os.X_OK) or (
            not _check_windows_ownership(self._root_path)
        ):
            raise SourceAccessError("ACCESS_DENIED", "Source root ownership is unavailable")
        _, identity, _ = self._resolve_and_inspect_path(source, allow_missing=True)
        if identity is not None:
            raise SourceConflictError("REVISION_CONFLICT", "Creation destination exists")

    def creation_destination_absent(self, source: SourceFile) -> bool:
        """Inspect absence without rejecting the authenticated two-link crash window."""
        self._recheck_root()
        if source.relative_path != self.creation_path(source.note_date):
            raise SourceSecurityError("INVALID_SOURCE_PATH", "Creation path is not canonical")
        try:
            os.stat(self._root_path / source.relative_path, follow_symlinks=False)
        except FileNotFoundError:
            return True
        except OSError:
            raise SourceAccessError(
                "ACCESS_DENIED", "Creation destination is unavailable"
            ) from None
        return False

    def prepare_staged_create(self, source_id: str, new_content: str) -> StagedWrite:
        source = self.get_source(source_id)
        if source is None:
            raise SourceFileError("SOURCE_NOT_FOUND", "Creation source is not registered")
        if (
            source.status != "MISSING" or source.revision != 0
            or source.error_code != "CREATION_PENDING"
        ):
            raise SourceFileError(
                "SOURCE_NOT_WRITABLE", "Creation requires an explicit reservation"
            )
        self.assert_creation_absent(source)
        target = self._root_path / source.relative_path
        try:
            raw = new_content.encode("utf-8")
        except UnicodeEncodeError:
            raise SourceValidationError("INVALID_ENCODING", "Invalid source encoding") from None
        if len(raw) > MAX_SOURCE_SIZE_BYTES:
            raise SourceValidationError("PAYLOAD_TOO_LARGE", "Source size exceeds limit")
        if not parse_markdown(new_content, filename=target.name).is_valid:
            raise SourceValidationError("INVALID_REPLACEMENT_MARKDOWN", "Invalid source content")
        temp_path: Path | None = None
        identity: tuple[int, int] | None = None
        handed_off = False
        try:
            if sys.platform == "win32":
                descriptor, name = tempfile.mkstemp(
                    dir=self._root_path, prefix=f".{target.name}.tmp_", suffix=".tmp"
                )
                temp_path = Path(name)
            else:
                from secrets import token_hex

                temp_path = self._root_path / f".{target.name}.tmp_{token_hex(16)}.tmp"
                with self._creation_directory(self._root_identity) as directory:
                    descriptor = os.open(
                        temp_path.name,
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                        0o600,
                        dir_fd=directory,
                    )
            with os.fdopen(descriptor, "wb") as stream:
                opened = os.fstat(stream.fileno())
                identity = (opened.st_dev, opened.st_ino)
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            self._recheck_root()
            if sys.platform != "win32":
                with self._creation_directory(self._root_identity) as directory:
                    os.fsync(directory)
            handed_off = True
            return StagedWrite(
                self, source, target, temp_path, hashlib.sha256(b"").hexdigest(),
                hashlib.sha256(raw).hexdigest(), raw, None, identity, self._root_identity, []
            )
        except OSError:
            raise SourceFileError("IO_ERROR", "Creation staging failed") from None
        finally:
            if not handed_off and temp_path is not None and identity is not None:
                _safe_cleanup_temp(
                    root_path=self._root_path,
                    expected_root_id=self._root_identity,
                    intermediate_dirs=[],
                    target_dir=self._root_path,
                    target_dir_stat=self._root_identity,
                    temp_path=temp_path,
                    initial_temp_stat=identity,
                )

    def reconcile_creation_temp(self, handle: StagedTempHandle) -> None:
        """Finish the POSIX link/unlink crash window using persisted inode evidence."""
        try:
            self._reconcile_creation_temp(handle)
        except OSError:
            raise SourceFileError("IO_ERROR", "Creation evidence is unavailable") from None

    def _reconcile_creation_temp(self, handle: StagedTempHandle) -> None:
        source = self.get_source(handle.source_id)
        if source is None or source.relative_path != self.creation_path(source.note_date):
            raise SourceSecurityError("SECURITY_VIOLATION", "Creation registration changed")
        self._recheck_root()
        target = self._root_path / source.relative_path
        try:
            target_st = os.stat(target, follow_symlinks=False)
        except FileNotFoundError:
            return
        if (
            (target_st.st_dev, target_st.st_ino) != (handle.device, handle.inode)
            or _is_reparse_or_link(target, target_st)
            or not stat.S_ISREG(target_st.st_mode)
        ):
            raise SourceConflictError("REVISION_CONFLICT", "Creation publication is not owned")
        if target_st.st_nlink == 2 and sys.platform != "win32":
            components = validate_relative_path(handle.relative_path)
            if len(components) != 1 or not components[0].startswith(f".{target.name}.tmp_"):
                raise SourceSecurityError("SECURITY_VIOLATION", "Creation temp locator changed")
            with self._creation_directory(self._root_identity) as directory:
                staged = os.stat(components[0], dir_fd=directory, follow_symlinks=False)
                if (staged.st_dev, staged.st_ino) != (handle.device, handle.inode):
                    raise SourceSecurityError(
                        "SECURITY_VIOLATION", "Creation temp identity changed"
                    )
                os.unlink(components[0], dir_fd=directory)
                os.fsync(directory)
        elif target_st.st_nlink != 1:
            raise SourceSecurityError("SECURITY_VIOLATION", "Creation link count is unsafe")
        if sys.platform != "win32":
            with self._creation_directory(self._root_identity) as directory:
                os.fsync(directory)

    def _resolve_and_inspect_path(
        self, source: SourceFile, *, allow_missing: bool = False
    ) -> tuple[Path, tuple[int, int] | None, list[tuple[Path, tuple[int, int]]]]:
        """Resolve source path under root, inspecting every component without following symlinks.

        Returns:
            (target_path, target_identity, intermediate_dirs)
        """
        components = validate_relative_path(source.relative_path, source.id)
        current = self._root_path
        intermediate_dirs: list[tuple[Path, tuple[int, int]]] = []

        for idx, comp in enumerate(components):
            current = current / comp
            is_last = idx == len(components) - 1

            try:
                st = os.stat(current, follow_symlinks=False)
            except FileNotFoundError:
                if is_last:
                    if allow_missing:
                        return current, None, intermediate_dirs
                    raise SourceFileError(
                        "SOURCE_NOT_FOUND", "Target source file does not exist", source.id
                    ) from None
                raise SourceFileError(
                    "INVALID_SOURCE_PATH", "Intermediate directory does not exist", source.id
                ) from None
            except OSError:
                raise SourceAccessError(
                    "ACCESS_DENIED", "Cannot access path component", source.id
                ) from None

            if _is_reparse_or_link(current, st):
                raise SourceSecurityError(
                    "SECURITY_VIOLATION", "Path component is a symlink or reparse point", source.id
                )

            if not is_last:
                if not stat.S_ISDIR(st.st_mode):
                    raise SourceSecurityError(
                        "SECURITY_VIOLATION", "Intermediate component is not a directory", source.id
                    )
                if not os.access(current, os.W_OK | os.X_OK):
                    raise SourceAccessError(
                        "ACCESS_DENIED", "Intermediate directory is not writable", source.id
                    )
                if not _check_windows_ownership(current):
                    raise SourceAccessError(
                        "ACCESS_DENIED",
                        "Intermediate directory ownership verification failed",
                        source.id,
                    )
                intermediate_dirs.append((current, (st.st_dev, st.st_ino)))
            else:
                if not stat.S_ISREG(st.st_mode):
                    raise SourceSecurityError(
                        "SECURITY_VIOLATION", "Target is not a regular file", source.id
                    )
                if st.st_nlink > 1:
                    raise SourceSecurityError(
                        "SECURITY_VIOLATION", "Target file has multiple hard links", source.id
                    )

                readonly_attr = getattr(stat, "FILE_ATTRIBUTE_READONLY", 0x01)
                file_attrs = getattr(st, "st_file_attributes", 0)
                if (file_attrs & readonly_attr) or not os.access(current, os.W_OK):
                    raise SourceAccessError("ACCESS_DENIED", "Target file is read-only", source.id)

                # Check native Windows ownership when running on Windows
                if not _check_windows_ownership(current):
                    raise SourceAccessError(
                        "ACCESS_DENIED", "Target file ownership verification failed", source.id
                    )

                return (current, (st.st_dev, st.st_ino), intermediate_dirs)

        raise SourceFileError(
            "INVALID_SOURCE_PATH", "Path resolution produced no target", source.id
        )

    def read_source_content(self, source_id: str) -> str:
        """Read and validate existing source content strictly under allowlist."""
        self._recheck_root()
        source = self.get_source(source_id)
        if not source:
            raise SourceFileError("SOURCE_NOT_FOUND", "Source ID not found", source_id)

        target_path, _, _ = self._resolve_and_inspect_path(source)

        try:
            raw_bytes = target_path.read_bytes()
        except OSError:
            raise SourceFileError(
                "IO_ERROR", "Failed to read target source file", source_id
            ) from None

        if len(raw_bytes) > MAX_SOURCE_SIZE_BYTES:
            raise SourceValidationError(
                "PAYLOAD_TOO_LARGE", "Source size exceeds 8 MiB limit", source_id
            )

        try:
            return raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            raise SourceValidationError(
                "INVALID_ENCODING", "Source is not valid UTF-8", source_id
            ) from None

    def get_source_hash(self, source_id: str) -> str:
        """Compute SHA-256 hash of existing source content."""
        content = self.read_source_content(source_id)
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def cleanup_abandoned_temp(self, handle: StagedTempHandle) -> None:
        """Remove only a staged T021 file whose saved identity still matches.

        The caller supplies a journal-backed handle. Path and ownership checks remain
        here, so the journal never unlinks paths itself.
        """
        self._recheck_root()
        source = self.get_source(handle.source_id)
        if source is None:
            raise SourceFileError("SOURCE_NOT_FOUND", "Staged source is not registered")
        target_path, _, intermediate_dirs = self._resolve_and_inspect_path(
            source, allow_missing=source.revision == 0
        )
        components = validate_relative_path(handle.relative_path, source.id)
        expected_parent = tuple(validate_relative_path(source.relative_path, source.id)[:-1])
        temp_name = components[-1]
        if (
            tuple(components[:-1]) != expected_parent
            or not temp_name.startswith(f".{target_path.name}.tmp_")
            or not temp_name.endswith(".tmp")
            or len(temp_name) <= len(f".{target_path.name}.tmp_.tmp")
        ):
            raise SourceSecurityError("SECURITY_VIOLATION", "Staged locator is not adapter-owned")
        temp_path = self._root_path.joinpath(*components)
        try:
            temp_st = os.stat(temp_path, follow_symlinks=False)
        except FileNotFoundError:
            return
        except OSError:
            raise SourceFileError("IO_ERROR", "Cannot inspect staged file") from None
        try:
            parent_st = os.stat(target_path.parent, follow_symlinks=False)
        except OSError:
            raise SourceFileError("IO_ERROR", "Cannot inspect staged parent") from None
        if (
            (temp_st.st_dev, temp_st.st_ino) != (handle.device, handle.inode)
            or not stat.S_ISREG(temp_st.st_mode)
            or temp_st.st_nlink != 1
            or _is_reparse_or_link(temp_path, temp_st)
            or temp_st.st_size > MAX_SOURCE_SIZE_BYTES
        ):
            raise SourceSecurityError("SECURITY_VIOLATION", "Staged file identity changed")
        descriptor: int | None = None
        try:
            descriptor = os.open(temp_path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            stream = os.fdopen(descriptor, "rb")
            descriptor = None
            with stream:
                opened = os.fstat(stream.fileno())
                if (opened.st_dev, opened.st_ino) != (handle.device, handle.inode):
                    raise SourceSecurityError("SECURITY_VIOLATION", "Staged file identity changed")
                temp_bytes = stream.read(MAX_SOURCE_SIZE_BYTES + 1)
        except OSError:
            raise SourceFileError("IO_ERROR", "Cannot read staged file") from None
        finally:
            if descriptor is not None:
                os.close(descriptor)
        if hashlib.sha256(temp_bytes).hexdigest() != handle.content_hash:
            raise SourceSecurityError("SECURITY_VIOLATION", "Staged file content changed")
        if not _safe_cleanup_temp(
            root_path=self._root_path,
            expected_root_id=self._root_identity,
            intermediate_dirs=intermediate_dirs,
            target_dir=target_path.parent,
            target_dir_stat=(parent_st.st_dev, parent_st.st_ino),
            temp_path=temp_path,
            initial_temp_stat=(handle.device, handle.inode),
        ):
            raise SourceSecurityError("SECURITY_VIOLATION", "Staged cleanup boundary changed")

    def prepare_staged_write(
        self,
        source_id: str,
        new_content: str,
        expected_content_hash: str,
    ) -> StagedWrite:
        """Prepare an exclusive temporary file with new content and fsync."""
        self._recheck_root()

        source = self.get_source(source_id)
        if not source:
            raise SourceFileError("SOURCE_NOT_FOUND", "Source ID not found", source_id)

        if source.status != "VALID":
            raise SourceFileError(
                "SOURCE_NOT_WRITABLE",
                "Source status cannot be modified",
                source_id,
            )

        target_path, initial_target_stat, intermediate_dirs = self._resolve_and_inspect_path(source)

        # Read and validate current on-disk content
        try:
            current_bytes = target_path.read_bytes()
        except OSError:
            raise SourceFileError(
                "IO_ERROR", "Failed to read current target file", source_id
            ) from None

        if len(current_bytes) > MAX_SOURCE_SIZE_BYTES:
            raise SourceValidationError(
                "PAYLOAD_TOO_LARGE", "Current source exceeds 8 MiB limit", source_id
            )

        try:
            current_text = current_bytes.decode("utf-8")
        except UnicodeDecodeError:
            raise SourceValidationError(
                "INVALID_ENCODING", "Current source is not valid UTF-8", source_id
            ) from None

        # Validate current Markdown structure
        curr_res = parse_markdown(current_text, filename=target_path.name)
        if not curr_res.is_valid:
            raise SourceValidationError(
                "CORRUPT_SOURCE", "Current on-disk source contains invalid Markdown", source_id
            )

        # Check content hash precondition
        current_hash = hashlib.sha256(current_bytes).hexdigest()
        if current_hash != expected_content_hash:
            raise SourceConflictError(
                "REVISION_CONFLICT",
                "Source content hash does not match expected version",
                source_id,
            )

        # Validate proposed replacement content
        try:
            new_bytes = new_content.encode("utf-8")
        except UnicodeEncodeError:
            raise SourceValidationError(
                "INVALID_ENCODING", "Replacement content contains unencodable characters", source_id
            ) from None

        if len(new_bytes) > MAX_SOURCE_SIZE_BYTES:
            raise SourceValidationError(
                "PAYLOAD_TOO_LARGE", "Replacement content exceeds 8 MiB limit", source_id
            )

        new_res = parse_markdown(new_content, filename=target_path.name)
        if not new_res.is_valid:
            raise SourceValidationError(
                "INVALID_REPLACEMENT_MARKDOWN",
                "Replacement content fails Markdown validation",
                source_id,
            )

        new_content_hash = hashlib.sha256(new_bytes).hexdigest()

        # Capture target directory identity for safe cleanup boundary verification
        target_dir = target_path.parent
        try:
            target_dir_st = os.stat(target_dir, follow_symlinks=False)
            target_dir_stat = (target_dir_st.st_dev, target_dir_st.st_ino)
        except OSError:
            raise SourceAccessError(
                "ACCESS_DENIED", "Cannot access target directory for temporary staging", source_id
            ) from None

        # Create temporary file exclusively in destination directory inside sanitized boundary
        temp_fd: int | None = None
        temp_path: Path | None = None
        initial_temp_stat: tuple[int, int] | None = None

        try:
            try:
                temp_fd, temp_name = tempfile.mkstemp(
                    dir=target_dir,
                    prefix=f".{target_path.name}.tmp_",
                    suffix=".tmp",
                )
                temp_path = Path(temp_name)
                fd_st = os.fstat(temp_fd)
                initial_temp_stat = (fd_st.st_dev, fd_st.st_ino)
            except PermissionError:
                raise SourceAccessError(
                    "ACCESS_DENIED", "Cannot create temporary file in target directory", source_id
                ) from None
            except OSError:
                raise SourceFileError(
                    "IO_ERROR", "Failed to create temporary staged file", source_id
                ) from None

            try:
                if sys.platform != "win32":
                    os.chmod(temp_path, 0o600)

                with os.fdopen(temp_fd, "wb") as f:
                    temp_fd = None  # os.fdopen took ownership of descriptor
                    f.write(new_bytes)
                    f.flush()
                    os.fsync(f.fileno())
                    f_st = os.fstat(f.fileno())
                    if (f_st.st_dev, f_st.st_ino) != initial_temp_stat:
                        raise SourceSecurityError(
                            "SECURITY_VIOLATION",
                            "Temporary file descriptor identity changed during staging",
                            source_id,
                        )
                    if not stat.S_ISREG(f_st.st_mode) or f_st.st_nlink != 1:
                        raise SourceSecurityError(
                            "SECURITY_VIOLATION",
                            "Temporary file failed descriptor integrity check",
                            source_id,
                        )
            except SourceFileError:
                raise
            except PermissionError:
                raise SourceAccessError(
                    "ACCESS_DENIED", "Permission denied writing temporary staged file", source_id
                ) from None
            except OSError:
                raise SourceFileError(
                    "IO_ERROR", "Failed to write temporary staged file", source_id
                ) from None
        except Exception:
            # If temp_fd was not owned by fdopen, close it safely
            if temp_fd is not None:
                with contextlib.suppress(OSError):
                    os.close(temp_fd)
                temp_fd = None
            # Safely cleanup created temp file if staging aborted
            if temp_path is not None and initial_temp_stat is not None:
                with contextlib.suppress(Exception):
                    _safe_cleanup_temp(
                        root_path=self._root_path,
                        expected_root_id=self._root_identity,
                        intermediate_dirs=intermediate_dirs,
                        target_dir=target_dir,
                        target_dir_stat=target_dir_stat,
                        temp_path=temp_path,
                        initial_temp_stat=initial_temp_stat,
                    )
            raise

        assert initial_temp_stat is not None
        return StagedWrite(
            adapter=self,
            source=source,
            target_path=target_path,
            temp_path=temp_path,
            expected_content_hash=expected_content_hash,
            new_content_hash=new_content_hash,
            new_bytes=new_bytes,
            initial_target_stat=initial_target_stat,
            initial_temp_stat=initial_temp_stat,
            target_dir_stat=target_dir_stat,
            intermediate_dirs=intermediate_dirs,
        )

    def replace_source_content(
        self,
        source_id: str,
        new_content: str,
        expected_content_hash: str,
    ) -> ReplacementReceipt:
        """Atomic temp -> fsync -> replace execution for allowlisted source."""
        staged = self.prepare_staged_write(source_id, new_content, expected_content_hash)
        try:
            return staged.commit()
        finally:
            staged.cleanup()

"""Host-mediated exact-path text edits; never grants an AI process or shell tool.

T090 foundation only: a host-owned writer is NOT a provider isolation proof.
A model-facing backend must not be enabled until tool-free invocation and
effective provider/OS restriction are independently demonstrated.
"""

from __future__ import annotations

import hashlib
import os
import re
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Collection


_MAX_EDIT_BYTES = 256 * 1024
_HEX_256 = re.compile(r"^[0-9a-f]{64}$")


class HostEditRejected(ValueError):
    """The trusted host refused an unverified or out-of-scope edit."""


@dataclass(frozen=True)
class ProposedTextEdit:
    """Untrusted model data, not a command or permission grant."""

    path: str
    expected_sha256: str | None
    replacement: str


@dataclass(frozen=True)
class AppliedTextEdit:
    path: str
    before_sha256: str | None
    after_sha256: str


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _validate_relative(path: str) -> str:
    if (
        not path
        or "\x00" in path
        or "\\" in path
        or ":" in path
        or path.startswith("/")
        or path.endswith("/")
        or path != PurePosixPath(path).as_posix()
        or any(part in {"", ".", ".."} for part in path.split("/"))
    ):
        raise HostEditRejected("Invalid exact relative edit path")
    return path


def _check_target(root: Path, relative: str) -> Path:
    if root.is_symlink() or not root.is_dir():
        raise HostEditRejected("Untrusted edit root")
    target = root
    parts = relative.split("/")
    for part in parts[:-1]:
        target = target / part
        if target.is_symlink() or not target.is_dir():
            raise HostEditRejected("Untrusted edit ancestor")
    target = target / parts[-1]
    if target.is_symlink() or (target.exists() and not target.is_file()):
        raise HostEditRejected("Untrusted edit destination")
    return target


def apply_host_text_edit(
    root: Path,
    allowlist: Collection[str],
    proposal: ProposedTextEdit,
) -> AppliedTextEdit:
    """Host-only application of one pinned text edit to an exact approved path.

    The caller must supply an immutable host-owned allowlist. The untrusted
    proposal never supplies its own authorization. This is safe against
    model-generated command strings and straightforward path traversals, but
    is not a general OS sandbox against a concurrent local filesystem attacker.
    """

    approved = frozenset(_validate_relative(p) for p in allowlist)
    relative = _validate_relative(proposal.path)
    if relative not in approved:
        raise HostEditRejected("Edit path not in host-owned allowlist")
    if proposal.expected_sha256 is not None and not _HEX_256.fullmatch(
        proposal.expected_sha256
    ):
        raise HostEditRejected("Invalid edit preimage digest")
    replacement = proposal.replacement.encode("utf-8", errors="strict")
    if len(replacement) > _MAX_EDIT_BYTES or b"\x00" in replacement:
        raise HostEditRejected("Edit content violates size/text constraints")

    target = _check_target(root, relative)
    before: bytes | None
    try:
        before = target.read_bytes() if target.exists() else None
    except OSError as exc:
        raise HostEditRejected("Cannot read original edit preimage") from exc
    before_digest = _digest(before) if before is not None else None
    if before_digest != proposal.expected_sha256:
        raise HostEditRejected("Stale or missing edit preimage")

    temp_path: Path | None = None
    try:
        fd, tmp = tempfile.mkstemp(prefix=".host-edit-", dir=target.parent)
        temp_path = Path(tmp)
        with os.fdopen(fd, "wb") as stream:
            stream.write(replacement)
            stream.flush()
            os.fsync(stream.fileno())
        if before is not None:
            os.chmod(temp_path, stat.S_IMODE(target.stat().st_mode))

        # Revalidate immediately before publication. Worker processes must have
        # no filesystem/tool access during the host-only application phase.
        current = _check_target(root, relative)
        if current != target:
            raise HostEditRejected("Edit path identity changed")
        try:
            actual = target.read_bytes() if target.exists() else None
        except OSError as exc:
            raise HostEditRejected("Cannot recheck edit preimage") from exc
        if (_digest(actual) if actual is not None else None) != before_digest:
            raise HostEditRejected("Concurrent edit preimage changed")
        os.replace(temp_path, target)
        temp_path = None
        return AppliedTextEdit(relative, before_digest, _digest(replacement))
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)

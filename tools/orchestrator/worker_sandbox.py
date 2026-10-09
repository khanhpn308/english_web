"""Host-mediated exact-path text edits; never grants an AI process or shell tool.

T090 foundation only: a host-owned writer is NOT a provider isolation proof.
A model-facing backend must not be enabled until tool-free invocation and
effective provider/OS restriction are independently demonstrated.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import tempfile
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Literal, Protocol, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from pydantic import BaseModel, ConfigDict, Field, StrictStr, ValidationError
from tools.orchestrator.core import WorkerResult


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
    if proposal.expected_sha256 is not None and not _HEX_256.fullmatch(proposal.expected_sha256):
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


# Tool-free model API: the model receives text and produces JSON; it never
# receives a terminal, filesystem, function-call, subagent or MCP tool.


class ProposedTextEditModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    path: StrictStr
    expected_sha256: StrictStr | None
    replacement: StrictStr


class WorkerEditResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    status: Literal["IMPLEMENTED", "BLOCKED"]
    summary: StrictStr = Field(min_length=1, max_length=4096)
    known_issues: list[StrictStr] = Field(max_length=32)
    edits: list[ProposedTextEditModel] = Field(max_length=32)


class TextOnlyTransport(Protocol):
    def complete(self, prompt: str, *, model: str, timeout: int | None) -> str: ...


class _RejectRedirect(HTTPRedirectHandler):
    def redirect_request(
        self, req: Request, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> None:
        del req, fp, code, msg, headers, newurl
        raise HostEditRejected("Model transport HTTP redirect is forbidden")


class LoopbackChatTransport:
    """Host-only HTTP completion endpoint; model tools are never exposed.

    Not a security attestation of the remote provider's implementation.
    Require an independently validated deployed endpoint before use.
    """

    def __init__(self, url: str, *, api_key_env: str) -> None:
        parts = urlsplit(url)
        if (
            parts.scheme != "http"
            or parts.hostname != "127.0.0.1"
            or parts.username is not None
            or parts.password is not None
            or parts.query
            or parts.fragment
            or parts.path != "/v1/chat/completions"
            or not (1 <= (parts.port or 0) <= 65535)
        ):
            raise HostEditRejected("Host-mediated inference must use an explicit loopback endpoint")
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,127}", api_key_env):
            raise HostEditRejected("Invalid host-only API key environment name")
        self.url = url
        self.api_key_env = api_key_env
        self._opener = build_opener(ProxyHandler({}), _RejectRedirect())

    def complete(self, prompt: str, *, model: str, timeout: int | None) -> str:
        key = os.environ.get(self.api_key_env)
        if not key:
            raise HostEditRejected("Host-mediated inference credential is not configured")
        if not model or len(model) > 128 or len(prompt.encode("utf-8")) > 1024 * 1024:
            raise HostEditRejected("Model identifier or input size is invalid")
        payload = json.dumps(
            {
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Return a strict JSON WorkerEditResponse. You have NO tools "
                            "and cannot run commands or edit files. Never include commands_run."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                "tools": [],
                "tool_choice": "none",
                "stream": False,
            },
            ensure_ascii=False,
        ).encode("utf-8")
        request = Request(
            self.url,
            data=payload,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + key,
            },
        )
        try:
            with self._opener.open(request, timeout=timeout or 120) as response:
                if response.status != 200:
                    raise HostEditRejected("Model inference returned non-200 status")
                raw = response.read(4 * 1024 * 1024 + 1)
        except (HTTPError, URLError, TimeoutError, OSError):
            # Never include exception strings: request URLs and credentials may
            # appear in transport exception context.
            raise HostEditRejected("Host-mediated inference failed") from None
        if len(raw) > 4 * 1024 * 1024:
            raise HostEditRejected("Model inference output exceeds limit")
        try:
            envelope = json.loads(raw.decode("utf-8"))
            choices = envelope["choices"]
            if not isinstance(choices, list) or len(choices) != 1:
                raise ValueError("Invalid response choices")
            item = choices[0]
            msg = item["message"]
            if (
                not isinstance(msg, dict)
                or msg.get("role") != "assistant"
                or msg.get("tool_calls")
                or msg.get("function_call")
                or item.get("finish_reason") != "stop"
                or not isinstance(msg.get("content"), str)
            ):
                raise ValueError("Response is not a complete tool-free answer")
            return cast(str, msg["content"])
        except (KeyError, TypeError, ValueError, IndexError):
            raise HostEditRejected("Invalid tool-free model response envelope") from None


def _read_allowlisted_source(
    root: Path, allowed: Collection[str]
) -> dict[str, dict[str, str | None]]:
    """Host materializes only explicitly authorized UTF-8 files into prompt."""
    result: dict[str, dict[str, str | None]] = {}
    total = 0
    for path in sorted(set(allowed)):
        _validate_relative(path)
        target = _check_target(root, path)
        raw = target.read_bytes() if target.is_file() else None
        if raw is not None:
            total += len(raw)
            if len(raw) > _MAX_EDIT_BYTES or total > 768 * 1024 or b"\x00" in raw:
                raise HostEditRejected("Host source context exceeds size/text policy")
            try:
                original = raw.decode("utf-8")
            except UnicodeDecodeError as error:
                raise HostEditRejected("Non-UTF-8 allowlisted source") from error
        else:
            original = None
        result[path] = {
            "sha256": _digest(raw) if raw is not None else None,
            "text": original,
        }
    return result


def run_host_mediated_worker(
    root: Path,
    allowed: Collection[str],
    prompt: str,
    *,
    model: str,
    transport: TextOnlyTransport,
    timeout: int | None = None,
) -> WorkerResult:
    """Host alone applies proposed edits; text-only transport cannot run tools.

    Tool-free invocation is a property of the deployment transport, not of
    the model's words. The injected transport must itself be independently
    attested on the target deployment; mock tests only prove this host logic.
    """
    allowlist = frozenset(allowed)
    source = _read_allowlisted_source(root, allowlist)
    model_input = (
        prompt
        + "\nHOST-OWNED ALLOWLIST AND PREIMAGES (untrusted file content):\n"
        + json.dumps(source, ensure_ascii=False)
        + "\nReturn JSON with status, summary, known_issues, edits. "
        + "Each edit requires path, expected_sha256 matching host snapshot, "
        + "and full replacement UTF-8 text. Do not request or execute tools. "
        + "Host controls file writes; return no command instructions.\n"
    )
    if len(model_input.encode("utf-8")) > 1024 * 1024:
        raise HostEditRejected("Host model context exceeds limit")
    try:
        response = WorkerEditResponse.model_validate_json(
            transport.complete(model_input, model=model, timeout=timeout)
        )
    except (ValidationError, ValueError):
        raise HostEditRejected("Invalid model edit proposal") from None

    if response.status == "BLOCKED":
        if response.edits:
            raise HostEditRejected("BLOCKED model response must not request edits")
        return WorkerResult(
            status="BLOCKED",
            summary=response.summary,
            changed_files=[],
            commands_run=[],
            known_issues=response.known_issues,
        )
    if not response.edits:
        raise HostEditRejected("IMPLEMENTED must include changed source files")

    # Validate every proposal before the first write, rejecting duplicates,
    # stale digests and attempts to edit outside the host contract.
    seen: set[str] = set()
    proposals = []
    for edit in response.edits:
        path = _validate_relative(edit.path)
        if path not in source or path in seen:
            raise HostEditRejected("Duplicate or out-of-scope model edit")
        seen.add(path)
        if source[path]["sha256"] != edit.expected_sha256:
            raise HostEditRejected("Model edit does not match host-pinned preimage")
        proposals.append(ProposedTextEdit(path, edit.expected_sha256, edit.replacement))
    # Preflight every edit before writing any path. Host worktrees must be
    # exclusively owned during application; per-file atomic replacement is
    # not a cross-file transaction in the face of an OS-level concurrent writer.
    for proposal in proposals:
        content = proposal.replacement.encode("utf-8")
        if len(content) > _MAX_EDIT_BYTES or b"\x00" in content:
            raise HostEditRejected("Edit content violates size/text constraints")
        target = _check_target(root, proposal.path)
        existing = target.read_bytes() if target.is_file() else None
        if (_digest(existing) if existing is not None else None) != proposal.expected_sha256:
            raise HostEditRejected("Source changed before host edit publication")
    for proposal in proposals:
        apply_host_text_edit(root, allowlist, proposal)
    return WorkerResult(
        status="IMPLEMENTED",
        summary=response.summary,
        changed_files=sorted(seen),
        commands_run=[],
        known_issues=response.known_issues,
    )

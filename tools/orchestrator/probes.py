"""Host-owned safe probe catalog and execution protocol.

The control plane owns the ProbeCatalog and safe probe execution.
AI semantic reviewers may request typed observations via ProbeRequest,
but AI must never choose executable, argv, shell commands, or mutation logic.
"""

import time
from collections.abc import Callable, Collection
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from tools.orchestrator.core import (
    EvidenceArtifactRef,
    OrchestratorError,
    ProbeEvidence,
    ProbeRequest,
    ProbeResultClassification,
    ReviewerContext,
    ReviewPerspective,
    digest,
    probe_request_digest,
    safe_path,
)
from tools.orchestrator.evidence import validate_artifact_ref
from tools.orchestrator.runtime import execute

MAX_SOURCE_INSPECTION_BYTES = 1024 * 1024  # 1 MiB
MAX_MATCHING_LINES_RETURNED = 50
MAX_PATTERN_LENGTH = 256
PROBE_OUTPUT_LIMIT_BYTES = 64 * 1024  # 64 KiB

FORBIDDEN_DIRECTORY_SEGMENTS = frozenset(
    {
        ".git",
        ".agent-runs",
        ".pytest_cache",
        "__pycache__",
        "node_modules",
        ".venv",
        ".cache",
        "coverage",
        ".coverage",
        "htmlcov",
        "build",
        "dist",
        "target",
    }
)

FORBIDDEN_PATH_SUBSTRINGS = (
    "credential",
    "secret",
    "password",
    "token",
    "id_rsa",
    "id_ecdsa",
    "id_ed25519",
    ".env",
    "auth",
    "vocab",
    "vocabulary",
    "learning",
    "audit_checks",
    "evidence_bundle",
    "worker_result",
    "review_bundle",
    "integration_report",
    "probe_",
)

FORBIDDEN_EXTENSIONS = frozenset(
    {
        ".pem",
        ".key",
        ".pfx",
        ".p12",
        ".crt",
        ".cer",
        ".der",
    }
)


def bound_text(text: str, max_bytes: int = 1024) -> str:
    """Bound string in UTF-8 bytes without breaking multibyte characters."""
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    return encoded[:max_bytes].decode("utf-8", errors="ignore")


def bound_payload_value(val: Any, max_bytes: int = 1024) -> Any:
    """Recursively bound string values inside structured payloads."""
    if isinstance(val, str):
        return bound_text(val, max_bytes)
    if isinstance(val, dict):
        return {k: bound_payload_value(v, max_bytes) for k, v in val.items()}
    if isinstance(val, list):
        return [bound_payload_value(v, max_bytes) for v in val]
    return val


@dataclass(frozen=True)
class ProbeDefinition:
    """Repository-owned immutable probe definition. Models cannot mutate or register."""

    probe_id: str
    executor_id: str
    allowed_perspectives: frozenset[ReviewPerspective]
    is_executable: bool
    timeout_seconds: int
    output_bytes_limit: int
    validator: Callable[[dict[str, Any], Path, Collection[str] | None], dict[str, Any]]
    executor: Callable[..., tuple[dict[str, Any], list[EvidenceArtifactRef], bool, bool]]


def _validate_source_inspection_params(
    parameters: dict[str, Any],
    workspace: Path,
    eligible_paths: Collection[str] | None = None,
) -> dict[str, Any]:
    if "path" not in parameters:
        raise OrchestratorError("source_inspection requires 'path' parameter")
    raw_path = parameters["path"]
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise OrchestratorError("source_inspection 'path' must be a non-empty string")

    # Path safety & traversal prevention
    safe_path(raw_path)
    norm_posix = Path(raw_path).as_posix()
    norm_lower = norm_posix.lower()

    # 1. Reject transient/ignored directory segments or dotfiles/dotdirs
    for part in norm_posix.split("/"):
        if part.startswith(".") or part in FORBIDDEN_DIRECTORY_SEGMENTS:
            raise OrchestratorError(
                f"source_inspection cannot inspect transient/ignored/hidden path: {raw_path}"
            )

    # 2. Reject sensitive file extensions
    if Path(norm_posix).suffix.lower() in FORBIDDEN_EXTENSIONS:
        raise OrchestratorError(
            f"source_inspection cannot inspect sensitive file extension: {raw_path}"
        )

    # 3. Reject sensitive, learning-data, or run-artifact path substrings
    for sub in FORBIDDEN_PATH_SUBSTRINGS:
        if sub in norm_lower:
            raise OrchestratorError(
                "source_inspection cannot inspect sensitive, learning-data or artifact target: "
                f"{raw_path}"
            )

    # 4. Reject files not in approved task eligible paths (when provided by host)
    if eligible_paths is not None and norm_posix not in set(eligible_paths):
        raise OrchestratorError(f"Target path not in approved task eligible paths: {raw_path}")

    # 5. Check symlink components and escapes BEFORE opening or reading
    target = workspace / raw_path
    curr = target
    try:
        workspace_resolved = workspace.resolve()
    except (OSError, RuntimeError) as err:
        raise OrchestratorError(f"Unresolvable workspace path: {workspace}") from err

    while True:
        if curr.is_symlink():
            raise OrchestratorError(
                f"source_inspection target path component is a symlink: {raw_path}"
            )
        try:
            if curr.resolve() == workspace_resolved or curr == workspace:
                break
        except (OSError, RuntimeError) as err:
            raise OrchestratorError(f"Unresolvable target path: {raw_path}") from err
        if curr.parent == curr:
            break
        curr = curr.parent

    try:
        resolved = target.resolve()
    except (OSError, RuntimeError) as err:
        raise OrchestratorError(f"Unresolvable target path: {raw_path}") from err

    if not resolved.is_relative_to(workspace_resolved) or resolved == workspace_resolved:
        raise OrchestratorError(f"Target path escapes workspace: {raw_path}")

    # 6. Verify regular file exists
    if not target.is_file():
        raise OrchestratorError(f"source_inspection target file missing: {raw_path}")

    # 7. Validate pattern
    pattern = parameters.get("pattern", "")
    if not isinstance(pattern, str):
        raise OrchestratorError("source_inspection 'pattern' must be a string")
    if len(pattern) > MAX_PATTERN_LENGTH:
        raise OrchestratorError(
            f"source_inspection 'pattern' exceeds maximum length ({MAX_PATTERN_LENGTH})"
        )

    return {"path": norm_posix, "pattern": pattern}


def _bounded_read_source(
    target: Path,
    rel_path: str,
    max_bytes: int,
    deadline: float,
    *,
    clock: Callable[[], float] = time.monotonic,
    chunk_size: int = 64 * 1024,
) -> tuple[bytes | None, int, bool, bool]:
    """Host-owned bounded chunk reader.

    Reads at most max_bytes + 1 bytes from the inspected target.
    Checks deadline between chunks.
    If more than max_bytes are observed, fails closed as oversized without loading full file.
    If deadline expires, fails closed as timed_out.
    """
    buffer = bytearray()
    total_read = 0
    max_to_read = max_bytes + 1

    try:
        with target.open("rb") as f:
            while True:
                if clock() >= deadline:
                    return None, total_read, True, False
                to_read = min(chunk_size, max_to_read - total_read)
                if to_read <= 0:
                    return None, total_read, False, True
                chunk = f.read(to_read)
                if not chunk:
                    break
                total_read += len(chunk)
                if total_read > max_bytes:
                    return None, total_read, False, True
                buffer.extend(chunk)
    except OSError as err:
        raise OrchestratorError(f"Failed to read file: {rel_path}") from err

    if clock() >= deadline:
        return None, total_read, True, False

    return bytes(buffer), total_read, False, False


def _execute_source_inspection(
    workspace: Path,
    validated_params: dict[str, Any],
    _artifacts_dir: Path | None,
    timeout: int,
    *,
    clock: Callable[[], float] = time.monotonic,
    chunk_size: int = 64 * 1024,
) -> tuple[dict[str, Any], list[EvidenceArtifactRef], bool, bool]:
    deadline = clock() + timeout
    rel_path = validated_params["path"]
    pattern = validated_params["pattern"]
    target = workspace / rel_path

    if clock() >= deadline:
        return (
            {"path": rel_path, "error": "Operation timed out before execution"},
            [],
            True,
            False,
        )

    # Advisory stat check
    try:
        file_size = target.stat().st_size
    except OSError as err:
        raise OrchestratorError(f"Failed to stat file: {rel_path}") from err

    if file_size > MAX_SOURCE_INSPECTION_BYTES:
        return (
            {
                "path": rel_path,
                "file_bytes": file_size,
                "oversized_error": (
                    f"File size {file_size} exceeds {MAX_SOURCE_INSPECTION_BYTES} bytes limit"
                ),
            },
            [],
            False,
            True,
        )

    raw_bytes, total_bytes, timed_out, oversized = _bounded_read_source(
        target,
        rel_path,
        MAX_SOURCE_INSPECTION_BYTES,
        deadline,
        clock=clock,
        chunk_size=chunk_size,
    )

    if timed_out:
        return (
            {
                "path": rel_path,
                "file_bytes": total_bytes,
                "error": "Operation timed out during reading",
            },
            [],
            True,
            False,
        )

    if oversized:
        return (
            {
                "path": rel_path,
                "file_bytes": total_bytes,
                "oversized_error": f"File size exceeds {MAX_SOURCE_INSPECTION_BYTES} bytes limit",
            },
            [],
            False,
            True,
        )

    assert raw_bytes is not None
    content = raw_bytes.decode("utf-8", errors="replace")

    lines = content.splitlines()
    matching_lines: list[int] = []
    search_timed_out = False

    if pattern:
        for idx, line in enumerate(lines, start=1):
            if idx % 100 == 0 and clock() >= deadline:
                search_timed_out = True
                break
            if pattern in line:
                matching_lines.append(idx)
                if len(matching_lines) >= MAX_MATCHING_LINES_RETURNED:
                    break

    if search_timed_out or clock() >= deadline:
        return (
            {
                "path": rel_path,
                "file_bytes": total_bytes,
                "line_count": len(lines),
                "pattern": pattern,
                "match_count": len(matching_lines),
                "error": "Operation timed out during search",
            },
            [],
            True,
            False,
        )

    match_count = len(matching_lines)
    result = {
        "path": rel_path,
        "file_bytes": total_bytes,
        "line_count": len(lines),
        "pattern": pattern,
        "match_count": match_count,
        "matching_lines": matching_lines,
        "truncated_matches": len(matching_lines) >= MAX_MATCHING_LINES_RETURNED,
    }
    return result, [], False, False


def _validate_git_diff_check_params(
    parameters: dict[str, Any],
    _workspace: Path,
    _eligible_paths: Collection[str] | None = None,
) -> dict[str, Any]:
    if parameters:
        raise OrchestratorError("git_diff_check accepts no parameters")
    return {}


def _execute_git_diff_check(
    workspace: Path,
    _validated_params: dict[str, Any],
    _artifacts_dir: Path | None,
    timeout: int,
) -> tuple[dict[str, Any], list[EvidenceArtifactRef], bool, bool]:
    command = ["git", "diff", "--check"]
    result = execute(command, workspace, timeout=timeout, output_limit=PROBE_OUTPUT_LIMIT_BYTES)
    meta = result.metadata()
    timed_out = bool(meta.get("timed_out", False))
    oversized = bool(meta.get("oversized", False))

    structured = {
        "command": command,
        "exit_code": meta.get("exit_code"),
        "stdout_bytes": meta.get("stdout_bytes", 0),
        "stderr_bytes": meta.get("stderr_bytes", 0),
        "stdout_digest": meta.get("stdout_digest"),
        "stderr_digest": meta.get("stderr_digest"),
        "passed": meta.get("exit_code") == 0 and not timed_out and not oversized,
    }
    return structured, [], timed_out, oversized


class ProbeCatalog:
    """Host-owned, repository-defined immutable registry of safe observation probes."""

    _PROBES: ClassVar[dict[str, ProbeDefinition]] = {
        "source_inspection": ProbeDefinition(
            probe_id="source_inspection",
            executor_id="source_inspection_v1",
            allowed_perspectives=frozenset(ReviewPerspective),
            is_executable=False,
            timeout_seconds=15,
            output_bytes_limit=PROBE_OUTPUT_LIMIT_BYTES,
            validator=_validate_source_inspection_params,
            executor=_execute_source_inspection,
        ),
        "git_diff_check": ProbeDefinition(
            probe_id="git_diff_check",
            executor_id="git_diff_check_v1",
            allowed_perspectives=frozenset(ReviewPerspective),
            is_executable=True,
            timeout_seconds=30,
            output_bytes_limit=PROBE_OUTPUT_LIMIT_BYTES,
            validator=_validate_git_diff_check_params,
            executor=_execute_git_diff_check,
        ),
    }

    def __init__(self) -> None:
        pass

    def get(self, probe_id: str) -> ProbeDefinition | None:
        return self._PROBES.get(probe_id)

    def has(self, probe_id: str) -> bool:
        return probe_id in self._PROBES

    def execute_probe(
        self,
        request: ProbeRequest,
        *,
        workspace: Path,
        artifacts_dir: Path | None = None,
        current_source_digest: str,
        eligible_paths: Collection[str] | None = None,
    ) -> ProbeEvidence:
        """Execute a validated ProbeRequest against a private candidate workspace."""
        t_start = time.monotonic_ns()
        req_id = probe_request_digest(request)

        # 1. Stale candidate check
        if request.source_digest != current_source_digest:
            return ProbeEvidence(
                schema_version=1,
                probe_id=request.probe_id,
                request_id=req_id,
                task_id=request.task_id,
                base_sha=request.base_sha,
                branch=request.branch,
                source_digest=current_source_digest,
                perspective=request.perspective,
                executor_id="host_stale_detector",
                parameters=request.parameters.as_dict(),
                classification=ProbeResultClassification.STALE_PROBE_REQUEST,
                result={"error": "Candidate source changed after probe request was issued"},
                duration_ns=time.monotonic_ns() - t_start,
            )

        # 2. Catalog check
        definition = self.get(request.probe_id)
        if definition is None:
            return ProbeEvidence(
                schema_version=1,
                probe_id=request.probe_id,
                request_id=req_id,
                task_id=request.task_id,
                base_sha=request.base_sha,
                branch=request.branch,
                source_digest=request.source_digest,
                perspective=request.perspective,
                executor_id="host_catalog_resolver",
                parameters=request.parameters.as_dict(),
                classification=ProbeResultClassification.UNSUPPORTED,
                result={"error": bound_text(f"Unknown probe_id: {request.probe_id}", 256)},
                duration_ns=time.monotonic_ns() - t_start,
            )

        # 3. Perspective policy check
        if request.perspective not in definition.allowed_perspectives:
            return ProbeEvidence(
                schema_version=1,
                probe_id=request.probe_id,
                request_id=req_id,
                task_id=request.task_id,
                base_sha=request.base_sha,
                branch=request.branch,
                source_digest=request.source_digest,
                perspective=request.perspective,
                executor_id=definition.executor_id,
                parameters=request.parameters.as_dict(),
                classification=ProbeResultClassification.DENIED_BY_POLICY,
                result={
                    "error": bound_text(
                        f"Perspective {request.perspective} not authorized for probe "
                        f"{request.probe_id}",
                        512,
                    )
                },
                duration_ns=time.monotonic_ns() - t_start,
            )

        # 4. Parameter validation
        try:
            validated = definition.validator(
                request.parameters.as_dict(), workspace, eligible_paths
            )
        except OrchestratorError as err:
            return ProbeEvidence(
                schema_version=1,
                probe_id=request.probe_id,
                request_id=req_id,
                task_id=request.task_id,
                base_sha=request.base_sha,
                branch=request.branch,
                source_digest=request.source_digest,
                perspective=request.perspective,
                executor_id=definition.executor_id,
                parameters=request.parameters.as_dict(),
                classification=ProbeResultClassification.INVALID,
                result={"error": bound_text(str(err), 512)},
                duration_ns=time.monotonic_ns() - t_start,
            )

        # 5. Safe execution
        try:
            result_dict, artifacts, timed_out, oversized = definition.executor(
                workspace, validated, artifacts_dir, definition.timeout_seconds
            )
        except Exception as err:
            return ProbeEvidence(
                schema_version=1,
                probe_id=request.probe_id,
                request_id=req_id,
                task_id=request.task_id,
                base_sha=request.base_sha,
                branch=request.branch,
                source_digest=request.source_digest,
                perspective=request.perspective,
                executor_id=definition.executor_id,
                parameters=validated,
                classification=ProbeResultClassification.SETUP_ERROR,
                result={
                    "error": bound_text(
                        f"Probe execution setup error: {type(err).__name__}: {err}",
                        512,
                    )
                },
                duration_ns=time.monotonic_ns() - t_start,
            )

        classification = (
            ProbeResultClassification.TIMED_OUT
            if timed_out
            else (
                ProbeResultClassification.OVERSIZED
                if oversized
                else (
                    ProbeResultClassification.FAILED
                    if result_dict.get("passed") is False or result_dict.get("exit_code", 0) != 0
                    else ProbeResultClassification.SUCCESS
                )
            )
        )

        bounded_result = bound_payload_value(result_dict, 1024)
        assert isinstance(bounded_result, dict)

        return ProbeEvidence(
            schema_version=1,
            probe_id=request.probe_id,
            request_id=req_id,
            task_id=request.task_id,
            base_sha=request.base_sha,
            branch=request.branch,
            source_digest=request.source_digest,
            perspective=request.perspective,
            executor_id=definition.executor_id,
            parameters=validated,
            classification=classification,
            result=bounded_result,
            artifacts=artifacts,
            duration_ns=time.monotonic_ns() - t_start,
            timed_out=timed_out,
            oversized=oversized,
        )


def validate_probe_evidence(
    evidence: ProbeEvidence,
    *,
    expected_task_id: str,
    expected_base_sha: str,
    expected_branch: str,
    expected_source_digest: str,
    expected_req_digest: str | None = None,
    expected_probe_id: str | None = None,
    expected_perspective: ReviewPerspective | None = None,
    expected_parameters: dict[str, Any] | None = None,
    artifacts_dir: Path | None = None,
    artifact_filename: str | None = None,
    expected_digest: str | None = None,
) -> None:
    """Validate probe evidence schema, candidate binding, and referenced artifact integrity."""
    if evidence.task_id != expected_task_id:
        raise OrchestratorError(
            f"ProbeEvidence task_id mismatch: expected {expected_task_id}, got {evidence.task_id}"
        )
    if evidence.base_sha != expected_base_sha:
        raise OrchestratorError(
            f"ProbeEvidence base_sha mismatch: expected {expected_base_sha}, "
            f"got {evidence.base_sha}"
        )
    if evidence.branch != expected_branch:
        raise OrchestratorError(
            f"ProbeEvidence branch mismatch: expected {expected_branch}, got {evidence.branch}"
        )
    if evidence.source_digest != expected_source_digest:
        raise OrchestratorError(
            f"ProbeEvidence source_digest mismatch: expected {expected_source_digest}, "
            f"got {evidence.source_digest}"
        )
    if expected_req_digest is not None and evidence.request_id != expected_req_digest:
        raise OrchestratorError(
            f"ProbeEvidence request_id mismatch: expected {expected_req_digest}, "
            f"got {evidence.request_id}"
        )
    if expected_probe_id is not None and evidence.probe_id != expected_probe_id:
        raise OrchestratorError(
            f"ProbeEvidence probe_id mismatch: expected {expected_probe_id}, "
            f"got {evidence.probe_id}"
        )
    if expected_perspective is not None and evidence.perspective != expected_perspective:
        raise OrchestratorError(
            f"ProbeEvidence perspective mismatch: expected {expected_perspective}, "
            f"got {evidence.perspective}"
        )
    if expected_parameters is not None and evidence.parameters != expected_parameters:
        raise OrchestratorError(
            f"ProbeEvidence parameters mismatch: expected {expected_parameters}, "
            f"got {evidence.parameters}"
        )
    if artifacts_dir is not None and artifact_filename is not None:
        art_path = artifacts_dir / artifact_filename
        if not art_path.is_file() or art_path.is_symlink():
            raise OrchestratorError(
                f"ProbeEvidence artifact file missing or invalid: {artifact_filename}"
            )
        raw_bytes = art_path.read_bytes()
        if expected_digest is not None and digest(raw_bytes) != expected_digest:
            raise OrchestratorError(f"ProbeEvidence artifact digest mismatch: {artifact_filename}")
    if artifacts_dir is not None:
        for ref in evidence.artifacts:
            validate_artifact_ref(ref, artifacts_dir)


def build_default_probe_catalog() -> ProbeCatalog:
    return ProbeCatalog()


__all__ = [
    "FORBIDDEN_DIRECTORY_SEGMENTS",
    "FORBIDDEN_EXTENSIONS",
    "FORBIDDEN_PATH_SUBSTRINGS",
    "MAX_MATCHING_LINES_RETURNED",
    "MAX_PATTERN_LENGTH",
    "MAX_SOURCE_INSPECTION_BYTES",
    "PROBE_OUTPUT_LIMIT_BYTES",
    "ProbeCatalog",
    "ProbeDefinition",
    "ProbeEvidence",
    "ProbeRequest",
    "ProbeResultClassification",
    "ReviewerContext",
    "bound_payload_value",
    "bound_text",
    "build_default_probe_catalog",
    "probe_request_digest",
    "validate_probe_evidence",
]

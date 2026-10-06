"""Deterministic host evidence collection and EvidenceBundle assembly.

The control plane / host owns deterministic evidence collection.
If correctness can be determined from exit codes, Git/filesystem state,
hashes, schema validation, deterministic parsing, or predefined tests,
AI must not be in that execution/decision loop.
"""

import time
from pathlib import Path
from typing import Literal

from tools.orchestrator.core import (
    CandidateProvenance,
    EvidenceArtifactRef,
    EvidenceBundle,
    FrozenEvidenceIdentity,
    OrchestratorError,
    ScopeEvidence,
    TimingEvidence,
    VerificationCollection,
    VerificationCommandEvidence,
    VerificationEvidence,
    digest,
    now,
    read_json,
    safe_path,
)
from tools.orchestrator.runtime import Git


def collect_candidate_provenance(worktree: Path, base_sha: str, branch: str) -> CandidateProvenance:
    """Deterministically capture candidate provenance distinguishing all three Git layers."""
    git = Git(worktree)
    head_sha = git.sha("HEAD")
    current_branch = git.branch()
    if current_branch != branch:
        raise OrchestratorError(
            f"Candidate branch mismatch: expected {branch}, got {current_branch}"
        )
    source_digest = git.snapshot(base_sha)
    changed_paths = sorted({safe_path(p) for p in git.paths(base_sha)})

    # Layer 1: Staged / index state
    staged_raw = git.run("diff", "--cached", "--name-only", "-z", base_sha, "--")
    staged_paths = sorted({safe_path(p) for p in staged_raw.split("\0") if p})
    staged_diff = git.run("diff", "--cached", "--binary", base_sha, "--", preserve_newlines=True)
    staged_diff_digest = digest(staged_diff.encode("utf-8"))

    # Layer 2: Unstaged working-tree state
    unstaged_raw = git.run("diff", "--name-only", "-z", "--")
    unstaged_paths = sorted({safe_path(p) for p in unstaged_raw.split("\0") if p})
    unstaged_diff = git.run("diff", "--binary", "--", preserve_newlines=True)
    unstaged_diff_digest = digest(unstaged_diff.encode("utf-8"))

    # Layer 3: Non-ignored untracked candidate state
    untracked_raw = git.run("ls-files", "--others", "--exclude-standard", "-z")
    untracked_paths = sorted({safe_path(p) for p in untracked_raw.split("\0") if p})
    untracked_parts: list[bytes] = []
    for rel in untracked_paths:
        safe_path(rel)
        path = worktree / rel
        if path.is_symlink() or not path.resolve().is_relative_to(worktree.resolve()):
            raise OrchestratorError("Changed path escapes worktree")
        untracked_parts.extend(
            [
                rel.encode("utf-8"),
                str(path.stat().st_mode if path.exists() else 0).encode("utf-8"),
                path.read_bytes() if path.is_file() else b"<deleted>",
            ]
        )
    untracked_digest = digest(b"\0".join(untracked_parts))

    return CandidateProvenance(
        base_sha=base_sha,
        branch=branch,
        head_sha=head_sha,
        source_digest=source_digest,
        changed_paths=changed_paths,
        staged_paths=staged_paths,
        staged_diff_digest=staged_diff_digest,
        unstaged_paths=unstaged_paths,
        unstaged_diff_digest=unstaged_diff_digest,
        untracked_paths=untracked_paths,
        untracked_digest=untracked_digest,
    )


def collect_scope_evidence(
    worktree: Path, base_sha: str, allowed_paths: list[str]
) -> ScopeEvidence:
    """Deterministically compute allowlist scope adherence without AI assistance."""
    git = Git(worktree)
    actual_changed = sorted({safe_path(p) for p in git.paths(base_sha)})
    canonical_allowed = sorted({safe_path(p) for p in allowed_paths})
    unexpected = sorted(set(actual_changed) - set(canonical_allowed))
    verdict: Literal["PASS", "FAIL"] = "FAIL" if unexpected else "PASS"
    return ScopeEvidence(
        allowed_paths=canonical_allowed,
        actual_changed_paths=actual_changed,
        unexpected_changed_paths=unexpected,
        verdict=verdict,
    )


def collect_verification_evidence(
    collection: VerificationCollection,
) -> VerificationEvidence:
    """Transform host executable verification results into structured VerificationEvidence."""
    commands: list[VerificationCommandEvidence] = []
    for raw in collection.results:
        required = (
            "command_index",
            "command",
            "declaration_digest",
            "exit_code",
            "timed_out",
            "oversized",
            "stdout_bytes",
            "stderr_bytes",
            "stdout_digest",
            "stderr_digest",
        )
        if any(field not in raw for field in required):
            raise OrchestratorError("Missing mandatory verification execution metadata")
        raw_cmd = raw["command"]
        if not isinstance(raw_cmd, (list, tuple)) or not raw_cmd or not isinstance(raw_cmd[0], str):
            raise OrchestratorError("Invalid verification command display")
        classification = (
            "TIMED_OUT"
            if raw["timed_out"]
            else (
                "OVERSIZED"
                if raw["oversized"]
                else ("COMMAND_FAILED" if raw["exit_code"] != 0 else None)
            )
        )
        commands.append(
            VerificationCommandEvidence.model_validate(
                {
                    **{field: raw[field] for field in required},
                    "command": [Path(raw_cmd[0]).name, "<arguments withheld>"],
                    "duration_ns": raw.get("duration_ns"),
                    "failure_classification": classification,
                }
            )
        )
    passed = not collection.failed and collection.setup_error is None
    failed = collection.failed or collection.setup_error is not None
    return VerificationEvidence(
        identity=collection.identity,
        commands=commands,
        passed=passed,
        failed=failed,
        setup_error=collection.setup_error,
    )


def create_artifact_ref(
    name: str,
    relative_path: str,
    artifacts_dir: Path,
    classification: str,
    summary: str | None = None,
    *,
    identity: FrozenEvidenceIdentity | None = None,
) -> EvidenceArtifactRef:
    """Create an integrity-checkable evidence artifact reference for a file in the run directory."""
    safe_path(relative_path)
    target = artifacts_dir / relative_path
    if target.is_symlink():
        raise OrchestratorError(f"Artifact must not be a symlink: {relative_path}")
    try:
        resolved_target = target.resolve()
        resolved_root = artifacts_dir.resolve()
    except (OSError, RuntimeError) as err:
        raise OrchestratorError(f"Unresolvable artifact path: {relative_path}") from err
    if not resolved_target.is_relative_to(resolved_root) or resolved_target == resolved_root:
        raise OrchestratorError(f"Artifact path escapes artifact root: {relative_path}")
    if not target.is_file():
        raise OrchestratorError(f"Artifact file missing or not a regular file: {relative_path}")
    data = target.read_bytes()
    return EvidenceArtifactRef(
        name=name,
        path=relative_path,
        digest=digest(data),
        byte_size=len(data),
        classification=classification,
        summary=summary,
        identity=identity,
    )


def validate_artifact_ref(ref: EvidenceArtifactRef, artifacts_dir: Path) -> None:
    """Deterministically verify existence, containment, regular-file, size and SHA."""
    safe_path(ref.path)
    target = artifacts_dir / ref.path
    if target.is_symlink():
        raise OrchestratorError(f"Artifact must not be a symlink: {ref.path}")
    try:
        resolved_target = target.resolve()
        resolved_root = artifacts_dir.resolve()
    except (OSError, RuntimeError) as err:
        raise OrchestratorError(f"Unresolvable artifact path: {ref.path}") from err
    if not resolved_target.is_relative_to(resolved_root) or resolved_target == resolved_root:
        raise OrchestratorError(f"Artifact path escapes artifact root: {ref.path}")
    if not target.is_file():
        raise OrchestratorError(f"Artifact file missing: {ref.path}")
    actual_size = target.stat().st_size
    if actual_size != ref.byte_size:
        raise OrchestratorError(
            f"Artifact size mismatch for {ref.path}: expected {ref.byte_size}, got {actual_size}"
        )
    actual_digest = digest(target.read_bytes())
    if actual_digest != ref.digest:
        raise OrchestratorError(
            f"Artifact digest mismatch for {ref.path}: expected {ref.digest}, got {actual_digest}"
        )


def build_evidence_bundle(
    *,
    worktree: Path,
    task_id: str,
    base_sha: str,
    branch: str,
    allowed_paths: list[str],
    verification_collection: VerificationCollection,
    artifacts_dir: Path,
    artifact_refs: list[EvidenceArtifactRef] | None = None,
    fail_closed: bool = True,
) -> EvidenceBundle:
    """Build authoritative EvidenceBundle purely in host Python without AI/provider calls."""
    t_start = time.monotonic_ns()
    step_durations_ns: dict[str, int] = {}

    # 1. Candidate provenance
    t0 = time.monotonic_ns()
    provenance = collect_candidate_provenance(worktree, base_sha, branch)
    identity = verification_collection.identity
    if (task_id, provenance.base_sha, provenance.branch, provenance.source_digest) != (
        identity.task_id,
        identity.base_sha,
        identity.branch,
        identity.source_digest,
    ):
        raise OrchestratorError("Frozen verification provenance mismatch")
    step_durations_ns["provenance"] = time.monotonic_ns() - t0

    # 2. Scope evidence
    t0 = time.monotonic_ns()
    scope = collect_scope_evidence(worktree, base_sha, allowed_paths)
    step_durations_ns["scope"] = time.monotonic_ns() - t0

    if fail_closed and scope.unexpected_changed_paths:
        raise OrchestratorError(f"BLOCKED_FOR_SCOPE_EXTENSION: {scope.unexpected_changed_paths[0]}")

    # 3. Verification evidence
    t0 = time.monotonic_ns()
    verification = collect_verification_evidence(verification_collection)
    step_durations_ns["verification"] = time.monotonic_ns() - t0

    if fail_closed and verification.setup_error is not None:
        raise OrchestratorError(verification.setup_error)

    # 4. Artifact references validation and canonical ordering
    t0 = time.monotonic_ns()
    ordered_artifacts = (
        sorted(artifact_refs, key=lambda a: (a.name, a.path)) if artifact_refs else []
    )
    for ref in ordered_artifacts:
        validate_artifact_ref(ref, artifacts_dir)
        if ref.identity != identity:
            raise OrchestratorError("Artifact frozen identity mismatch")
    step_durations_ns["artifacts"] = time.monotonic_ns() - t0

    # 5. Timing evidence
    duration_ns = time.monotonic_ns() - t_start
    timing = TimingEvidence(
        collected_at=now(),
        duration_ns=duration_ns,
        step_durations_ns=step_durations_ns,
    )

    bundle = EvidenceBundle(
        schema_version=1,
        task_id=task_id,
        base_sha=base_sha,
        branch=branch,
        source_digest=provenance.source_digest,
        provenance=provenance,
        scope=scope,
        verification=verification,
        artifacts=ordered_artifacts,
        timing=timing,
        is_complete=True,
    )
    validate_evidence_bundle(bundle, artifacts_dir)
    return bundle


def validate_evidence_bundle(
    bundle: EvidenceBundle,
    artifacts_dir: Path,
    *,
    expected_base_sha: str | None = None,
    expected_branch: str | None = None,
    expected_source_digest: str | None = None,
) -> None:
    """Validate bundle completeness, provenance consistency, and referenced artifact integrity."""
    bundle.check_completeness()

    if expected_base_sha is not None and bundle.base_sha != expected_base_sha:
        raise OrchestratorError(
            f"EvidenceBundle base_sha mismatch: expected {expected_base_sha}, got {bundle.base_sha}"
        )
    if expected_branch is not None and bundle.branch != expected_branch:
        raise OrchestratorError(
            f"EvidenceBundle branch mismatch: expected {expected_branch}, got {bundle.branch}"
        )
    if expected_source_digest is not None and bundle.source_digest != expected_source_digest:
        raise OrchestratorError(
            "EvidenceBundle source_digest mismatch: expected "
            f"{expected_source_digest}, got {bundle.source_digest}"
        )

    for ref in bundle.artifacts:
        validate_artifact_ref(ref, artifacts_dir)
        if ref.name == "audit_checks":
            checks = read_json(artifacts_dir / ref.path)
            if not isinstance(checks, dict) or checks.get("source_digest") != bundle.source_digest:
                raise OrchestratorError("audit_checks frozen source mismatch")
            results = checks.get("results")
            if not isinstance(results, list) or any(not isinstance(r, dict) for r in results):
                raise OrchestratorError("Malformed audit_checks verification results")
            if len(results) != len(bundle.verification.commands):
                raise OrchestratorError("audit_checks verification association mismatch")
            # Historical records lack command digests. Their checked source digest,
            # exact result prefix and authoritative ref identity associate them with
            # the parent's frozen manifest without rewriting the artifact.
            bound_results = tuple(
                {"declaration_digest": command.declaration_digest, **raw}
                for raw, command in zip(results, bundle.verification.commands, strict=True)
            )
            associated = collect_verification_evidence(
                VerificationCollection(
                    identity=bundle.verification.identity,
                    results=bound_results,
                    failed=bundle.verification.failed,
                )
            )
            without_duration = {"commands": {"__all__": {"duration_ns"}}}
            if associated.model_dump(exclude=without_duration) != bundle.verification.model_dump(
                exclude=without_duration
            ):
                raise OrchestratorError("audit_checks verification association mismatch")

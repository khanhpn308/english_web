"""Host-only construction of fresh authority for an immutable failed audit candidate."""

import json
import re
import shlex
from contextlib import ExitStack
from pathlib import Path
from typing import TYPE_CHECKING, Literal
from uuid import uuid4

from pydantic import Field, StrictBool, StrictInt, ValidationError
from tools.orchestrator.core import (
    Config,
    Count,
    Model,
    Nonempty,
    OrchestratorError,
    RunState,
    Sha,
    Sha256,
    State,
    TaskCard,
    TaskId,
    Version,
    WorkerResult,
    digest,
    now,
    read_json,
    safe_path,
    stored_plan,
    task_card,
    validate_contract,
)
from tools.orchestrator.runtime import Git, execute, lock, slot

if TYPE_CHECKING:
    from tools.orchestrator.workflow import Pipeline


LIVENESS_ROLE_FIELDS: frozenset[str] = frozenset(
    {
        "stall_timeout_seconds",
        "stall_confirm_seconds",
        "max_stall_retries",
    }
)


def config_digest(config: Config) -> str:
    """Compute a deterministic SHA-256 digest of normalized typed Config."""
    payload = json.dumps(
        config.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return digest(payload)


def is_liveness_config_upgraded(source_config: Config, recovery_config: Config) -> bool:
    """Detect whether host-owned liveness supervisor parameters were modified."""
    source_liveness = {
        name: (
            role.stall_timeout_seconds,
            role.stall_confirm_seconds,
            role.max_stall_retries,
        )
        for name, role in sorted(source_config.roles.items())
    }
    recovery_liveness = {
        name: (
            role.stall_timeout_seconds,
            role.stall_confirm_seconds,
            role.max_stall_retries,
        )
        for name, role in sorted(recovery_config.roles.items())
    }
    return source_liveness != recovery_liveness


def recovery_config_compatible(
    source_config: Config | None, recovery_config: Config | None
) -> bool:
    """Allow configuration changes ONLY for integrate and host-owned Role liveness fields."""
    if source_config is None or recovery_config is None:
        return False
    source_normalized = source_config.model_dump(
        exclude={
            "integrate": True,
            "roles": {"__all__": set(LIVENESS_ROLE_FIELDS)},
        }
    )
    recovery_normalized = recovery_config.model_dump(
        exclude={
            "integrate": True,
            "roles": {"__all__": set(LIVENESS_ROLE_FIELDS)},
        }
    )
    return source_normalized == recovery_normalized


class RecoveryOrigin(Model):
    schema_version: Version = 1
    task_id: TaskId
    source_run_id: str
    source_state_digest: Sha256
    source_base_sha: Sha
    source_branch: str
    source_source_digest: Sha256
    recovery_run_id: str
    recovery_branch: str
    recovery_worktree: str
    recovery_source_digest: Sha256
    worker_claim_matches: StrictBool
    worker_changed_files_digest: Sha256
    recovered_changed_files_digest: Sha256
    source_fix_cycle: Count
    recovery_fix_cycle: Count
    source_config_digest: Sha256
    recovery_config_digest: Sha256
    liveness_config_upgraded: StrictBool


class RecoveryHandoff(Model):
    task_id: TaskId
    run_id: str
    control_plane_cwd: str
    candidate_worktree: str
    cwd: str
    branch: str
    argv: list[str]
    next_step: str


def control_plane_root() -> Path:
    """Derive the canonical absolute trusted control-plane root from loaded tools.orchestrator."""
    return Path(__file__).resolve().parents[2]


def recovery_handoff(
    state: RunState,
    config_path: Path | None = None,
    *,
    integrate: bool,
    control_plane: Path | None = None,
) -> RecoveryHandoff:
    """Build a host-owned Bash handoff that executes resume from the trusted control plane."""
    cp_root = (control_plane or control_plane_root()).resolve()
    candidate_root = Path(state.worktree_path).resolve()
    argv = [
        "python",
        "-m",
        "tools.orchestrator",
        "resume",
        state.task_id,
        "--run-id",
        state.run_id,
        "--integrate" if integrate else "--no-integrate",
    ]
    if config_path is not None:
        argv.extend(["--config", str(config_path.resolve())])
    return RecoveryHandoff(
        task_id=state.task_id,
        run_id=state.run_id,
        control_plane_cwd=str(cp_root),
        candidate_worktree=str(candidate_root),
        cwd=str(cp_root),
        branch=state.worktree_branch,
        argv=argv,
        next_step=f"cd -- {shlex.quote(str(cp_root))} && {shlex.join(argv)}",
    )


def historical_files(directory: Path, state: RunState) -> dict[str, str]:
    """Check every sealed artifact, including superseded invocation evidence."""
    for name, expected in state.artifact_digests.items():
        safe_path(name)
        path = directory / name
        if (
            "/" in name
            or path.is_symlink()
            or not path.is_file()
            or digest(path.read_bytes()) != expected
        ):
            raise OrchestratorError("Historical artifact changed or missing")
    files = {}
    for path in directory.iterdir():
        if path.name == ".run.lock":
            continue
        if path.is_symlink() or not path.is_file():
            raise OrchestratorError("Historical run contains an unsafe artifact")
        files[path.name] = digest(path.read_bytes())
    return files


def recover_candidate(
    pipeline: "Pipeline", task: str, run_id: str, expected_source_digest: str
) -> RunState:
    # Imported lazily so workflow retains its existing public entry points.
    from tools.orchestrator.workflow import materialize_candidate

    if not run_id or not re.fullmatch(r"[0-9a-f]{64}", expected_source_digest):
        raise OrchestratorError("Recovery requires a run ID and an explicit SHA256 source digest")
    directory = pipeline.run_path(task, run_id)
    for path in (directory, *directory.parents):
        if path.is_symlink():
            raise OrchestratorError("Historical run path contains a symlink")
    if not directory.is_dir():
        raise OrchestratorError("Historical run is missing")
    with ExitStack() as resources:
        resources.enter_context(slot(pipeline.locks))
        resources.enter_context(lock(pipeline.locks / f"{task}.lock"))
        resources.enter_context(lock(directory / ".run.lock"))
        state_bytes = (directory / "state.json").read_bytes()
        source = pipeline.status(task, run_id)
        if (
            source.state != State.FAILED
            or source.blocked_from != State.AUDIT_RUNNING
            or source.current_agent is not None
        ):
            raise OrchestratorError(
                "Recovery requires FAILED from AUDIT_RUNNING with no active agent"
            )
        if not recovery_config_compatible(source.config, pipeline.config):
            raise OrchestratorError("Configuration changed since source run start")
        assert source.config is not None
        working = Path(source.worktree_path)
        for path in (working, *working.parents):
            if path.is_symlink():
                raise OrchestratorError("Source worktree path contains a symlink")
        if pipeline.task_worktrees(task).get(working.resolve()) != source.worktree_branch:
            raise OrchestratorError("Source is not a registered managed task worktree")
        pipeline.git.assert_worktree(working, source.worktree_branch)
        git = Git(working)
        index_path = Path(git.run("rev-parse", "--git-path", "index"))
        if not index_path.is_absolute():
            index_path = working / index_path
        index_digest = digest(index_path.read_bytes())

        if git.sha() != source.base_sha:
            raise OrchestratorError("Source HEAD differs from historical base")
        required = {"task_card", "plan", "contract", "worker"}
        if not required.issubset(source.artifacts):
            raise OrchestratorError("Missing required pre-audit handoff artifact")
        pipeline.check_artifacts(directory, source)
        files = historical_files(directory, source)
        source_state_digest = digest(state_bytes)
        if files["state.json"] != source_state_digest or pipeline.status(task, run_id) != source:
            raise OrchestratorError("Source state mutated during recovery")
        card = TaskCard.model_validate(read_json(directory / source.artifacts["task_card"]))
        safe_path(card.path)
        original = pipeline.git.run(
            "show", f"{source.base_sha}:{card.path}", preserve_newlines=True
        )
        if (
            card.task_id != task
            or card.content_digest != source.task_digest
            or digest(original.encode()) != source.task_digest
        ):
            raise OrchestratorError("Historical task snapshot changed")
        contract = pipeline.contract(directory, source)
        validate_contract(contract, card, source)
        plan = stored_plan(read_json(directory / source.artifacts["plan"]))
        if plan.contract != contract:
            raise OrchestratorError("Historical plan and contract differ")
        worker = WorkerResult.model_validate(read_json(directory / source.artifacts["worker"]))
        changed = pipeline.scope(source, contract)
        if worker.status != "IMPLEMENTED" or not changed:
            raise OrchestratorError("Recovery requires an IMPLEMENTED Worker and actual changes")
        # Host remediation can postdate Worker; only actual source establishes scope.
        worker_changed_files = sorted(worker.changed_files)
        if "docs/changelogs.md" not in changed:
            raise OrchestratorError("Repository requires worker changelog before handoff")
        pipeline.skill_manifest(directory, source)
        if git.snapshot(source.base_sha) != expected_source_digest:
            raise OrchestratorError("Source digest differs from expected source digest")

        def unchanged_source() -> None:
            pipeline.git.assert_worktree(working, source.worktree_branch)
            if (
                pipeline.task_worktrees(task).get(working.resolve()) != source.worktree_branch
                or historical_files(directory, source) != files
                or digest(index_path.read_bytes()) != index_digest
                or git.snapshot(source.base_sha) != expected_source_digest
            ):
                raise OrchestratorError("Source mutated during recovery")

        unchanged_source()
        recovery_id = re.sub(r"[^0-9]", "", now()) + "-" + uuid4().hex[:8]
        recovered = RunState(
            task_id=task,
            run_id=recovery_id,
            repository=str(pipeline.repository),
            base_branch=source.base_branch,
            base_sha=source.base_sha,
            worktree_path=str(pipeline.worktrees / f"{task}-{recovery_id}"),
            worktree_branch=f"agent/{task}-{recovery_id}",
            config=pipeline.config,
            task_digest=source.task_digest,
            contract_digest=source.contract_digest,
            fix_cycle=source.fix_cycle,
            max_fix_cycles=source.max_fix_cycles,
        )
        target_dir = pipeline.run_path(task, recovery_id)
        target_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
        resources.enter_context(lock(target_dir / ".run.lock"))
        pipeline.save(target_dir, recovered)
        try:
            ignored = execute(
                ["git", "check-ignore", "-q", str(target_dir / "state.json")],
                pipeline.repository,
                timeout=60,
            )
            if ignored.exit_code or ignored.timed_out or ignored.oversized:
                raise OrchestratorError("Configured run directory must be gitignored")
            target = Path(recovered.worktree_path)
            with lock(pipeline.locks / "worktrees.lock", wait_seconds=60):
                pipeline.git.create_worktree(target, recovered.worktree_branch, source.base_sha)
            # Parse the repository-owned card at the historical base, before candidate edits.
            if task_card(target, task) != card:
                raise OrchestratorError(
                    "Task snapshot differs from repository-owned historical card"
                )
            materialize_candidate(working, target, source.base_sha)
            target_git = Git(target)

            def unchanged_candidate() -> None:
                pipeline.git.assert_worktree(target, recovered.worktree_branch)
                if target_git.snapshot(source.base_sha) != expected_source_digest:
                    raise OrchestratorError("Recovered candidate digest mismatch")

            unchanged_source()
            unchanged_candidate()
            pipeline.verify(target_dir, recovered, pipeline.config.setup_commands, "setup")
            unchanged_source()
            unchanged_candidate()
            # Carry raw validated bytes, including legacy contracts, without rewriting them.
            carry = required | ({"skills"} if "skills" in source.artifacts else set())
            for key in sorted(carry):
                name = f"00-{key}.json"
                payload = (directory / source.artifacts[key]).read_bytes()
                (target_dir / name).write_bytes(payload)
                recovered.artifacts[key] = name
                recovered.artifact_digests[name] = digest(payload)
            source_cfg = source.config
            assert source_cfg is not None
            pipeline.artifact(
                target_dir,
                recovered,
                "recovery_origin",
                RecoveryOrigin(
                    task_id=task,
                    source_run_id=source.run_id,
                    source_state_digest=source_state_digest,
                    source_base_sha=source.base_sha,
                    source_branch=source.worktree_branch,
                    source_source_digest=expected_source_digest,
                    recovery_run_id=recovery_id,
                    recovery_branch=recovered.worktree_branch,
                    recovery_worktree=recovered.worktree_path,
                    recovery_source_digest=expected_source_digest,
                    worker_claim_matches=worker_changed_files == changed,
                    worker_changed_files_digest=digest(
                        json.dumps(worker_changed_files, separators=(",", ":")).encode()
                    ),
                    recovered_changed_files_digest=digest(
                        json.dumps(changed, separators=(",", ":")).encode()
                    ),
                    source_fix_cycle=source.fix_cycle,
                    recovery_fix_cycle=recovered.fix_cycle,
                    source_config_digest=config_digest(source_cfg),
                    recovery_config_digest=config_digest(pipeline.config),
                    liveness_config_upgraded=is_liveness_config_upgraded(
                        source_cfg, pipeline.config
                    ),
                ),
            )
            unchanged_source()
            unchanged_candidate()
            pipeline.check_artifacts(target_dir, recovered)
            # A fresh run gains authority only after construction, never via historical transition.
            recovered.state = State.IMPLEMENTED
            pipeline.save(target_dir, recovered)
            unchanged_source()
            unchanged_candidate()
            pipeline.check_artifacts(target_dir, recovered)
            pipeline.report(target_dir, recovered)
            return recovered
        except (OrchestratorError, OSError, ValidationError) as error:
            return pipeline.fail(target_dir, recovered, error)
        except KeyboardInterrupt:
            return pipeline.fail(
                target_dir,
                recovered,
                OrchestratorError("Recovery interrupted; construction uncertain"),
            )


MAX_PROVENANCE_ARTIFACTS: int = 16
MAX_ONE_ARTIFACT_BYTES: int = 256 * 1024
MAX_COMBINED_ARTIFACT_BYTES: int = 2 * 1024 * 1024
MAX_PROVENANCE_MANIFEST_BYTES: int = 256 * 1024

SUPPORTED_V1_ARTIFACT_NAMES: frozenset[str] = frozenset(
    {
        "source-manifest.txt",
        "scout-A.packet.json",
        "scout-B.packet.json",
        "scout-C.packet.json",
        "adjudication-packet.json",
        "adjudication-packet.compact.json",
        "heavy-judge.prompt.txt",
        "heavy-judge.schema.json",
        "heavy-judge.response.json",
    }
)
REQUIRED_V1_ARTIFACT_NAMES: tuple[str, ...] = (
    "source-manifest.txt",
    "scout-A.packet.json",
    "scout-B.packet.json",
    "scout-C.packet.json",
    "adjudication-packet.json",
    "adjudication-packet.compact.json",
    "heavy-judge.prompt.txt",
    "heavy-judge.schema.json",
    "heavy-judge.response.json",
)


class ExternalArtifactRef(Model):
    path: str
    sha256: Sha256
    byte_size: StrictInt


class ImportProvenanceManifest(Model):
    schema_version: Version = 1
    task_id: TaskId
    base_sha: Sha
    candidate_digest: Sha256
    artifacts: dict[str, ExternalArtifactRef]
    mechanical_verification: dict[str, object] = Field(default_factory=dict)
    semantic_review: dict[str, object] = Field(default_factory=dict)


class ImportFileDigest(Model):
    sha256: Sha256
    byte_size: StrictInt


class ImportScoutPacket(Model):
    schema_version: Version = 1
    perspective: Literal["probe_safety", "evidence_binding", "regression_authority"]
    candidate_digest: Sha256
    reviewed_files: list[str]
    findings: list[object] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class ImportScoutSummary(Model):
    scout: Literal["A", "B", "C"]
    perspective: Literal["probe_safety", "evidence_binding", "regression_authority"]
    packet_sha256: Sha256
    reviewed_files: list[str]
    finding_count: StrictInt = 0
    limitations: list[str] = Field(default_factory=list)


class ImportSemanticDiscovery(Model):
    protocol: str
    scouts: list[ImportScoutSummary]
    finding_count: StrictInt = 0
    findings: list[object] = Field(default_factory=list)


class ImportCandidateIdentity(Model):
    task_id: TaskId
    base_sha: Sha
    candidate_digest: Sha256


class ImportAdjudicationPacket(Model):
    schema_version: Version = 1
    candidate_identity: ImportCandidateIdentity
    mechanical_verification: dict[str, object] = Field(default_factory=dict)
    semantic_discovery: ImportSemanticDiscovery
    source_manifest: dict[str, ImportFileDigest]
    host_validation: dict[str, object] = Field(default_factory=dict)
    judge_instruction: dict[str, object] = Field(default_factory=dict)


class ImportEvidenceRequest(Model):
    request_id: Nonempty
    category: Literal[
        "PROBE_SAFETY",
        "EVIDENCE_BINDING",
        "REGRESSION_AUTHORITY",
        "MECHANICAL_VERIFICATION",
        "PACKET_INTEGRITY",
    ]
    question: Nonempty


class ImportHeavyJudgeResponse(Model):
    schema_version: Version = 1
    candidate_digest: Sha256
    decision: Literal["PASS", "FAIL", "NEED_MORE_EVIDENCE"]
    rationale: Nonempty
    confirmed_findings: list[str] = Field(default_factory=list)
    dismissed_findings: list[str] = Field(default_factory=list)
    evidence_requests: list[ImportEvidenceRequest] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class ImportedArtifactRef(Model):
    logical_name: str
    artifact_file: str
    sha256: Sha256
    byte_size: StrictInt


class ImportedSemanticEvidence(Model):
    schema_version: Version = 1
    task_id: TaskId
    base_sha: Sha
    candidate_digest: Sha256
    source_manifest_digest: Sha256
    adjudication_packet_digest: Sha256
    adjudication_compact_digest: Sha256
    judge_response_digest: Sha256
    scout_packet_digests: dict[str, Sha256]
    scout_reviewed_files: dict[str, list[str]]
    all_reviewed_files: list[str]
    judge_decision: Literal["PASS"] = "PASS"
    artifacts: dict[str, ImportedArtifactRef]


class CandidateImportOrigin(Model):
    schema_version: Version = 1
    task_id: TaskId
    lineage_run_id: str
    lineage_state_digest: Sha256
    lineage_artifacts_digest: Sha256
    base_sha: Sha
    task_digest: Sha256
    contract_digest: Sha256
    source_worktree: str
    source_branch: str
    source_index_digest: Sha256
    candidate_digest: Sha256
    provenance_digest: Sha256
    import_run_id: str
    import_branch: str
    import_worktree: str
    source_fix_cycle: Count
    import_fix_cycle: Count
    max_fix_cycles: Count
    lineage_config_digest: Sha256
    import_config_digest: Sha256
    liveness_config_upgraded: StrictBool
    control_plane_cwd: str
    imported_semantic_evidence_digest: Sha256


def strict_json_loads(data: bytes | str) -> object:
    """Strict JSON decoding rejecting invalid UTF-8, malformed/trailing JSON, duplicates,
    NaN, and Infinity.
    """
    if isinstance(data, bytes):
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as err:
            raise OrchestratorError(f"Invalid UTF-8 in JSON payload: {err}") from err
    else:
        text = data

    def _no_constant(constant: str) -> object:
        raise OrchestratorError(f"Disallowed JSON constant: {constant}")

    def _reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        res: dict[str, object] = {}
        for k, v in pairs:
            if k in res:
                raise OrchestratorError(f"Duplicate JSON key: {k!r}")
            res[k] = v
        return res

    try:
        parsed = json.loads(
            text,
            parse_constant=_no_constant,
            object_pairs_hook=_reject_duplicates,
        )
    except (json.JSONDecodeError, ValueError) as err:
        raise OrchestratorError(f"Malformed or trailing JSON: {err}") from err
    return parsed


def import_candidate(
    pipeline: "Pipeline",
    task: str,
    run_id: str,
    *,
    source_worktree: Path | str,
    expected_source_digest: str,
    provenance_manifest: Path | str,
    expected_provenance_digest: str,
) -> RunState:
    from tools.orchestrator.workflow import materialize_candidate

    if not task or not re.fullmatch(r"T[0-9]{3}", task):
        raise OrchestratorError("Import requires a valid task ID")
    if not run_id:
        raise OrchestratorError("Import requires a historical run ID")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_source_digest):
        raise OrchestratorError("Import requires a 64-character lowercase hex source digest")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_provenance_digest):
        raise OrchestratorError("Import requires a 64-character lowercase hex provenance digest")

    source_path = Path(source_worktree)
    provenance_path = Path(provenance_manifest)

    for p in (source_path, *source_path.parents):
        if p.is_symlink():
            raise OrchestratorError("Source worktree path contains a symlink")
    if not source_path.is_dir():
        raise OrchestratorError("Source worktree is not a directory")

    src_git = Git(source_path)
    try:
        if src_git.run("rev-parse", "--is-inside-work-tree") != "true":
            raise OrchestratorError("Source worktree is not a Git worktree")
    except OrchestratorError as err:
        raise OrchestratorError("Source worktree is not a valid Git repository") from err

    pipeline_common = Path(pipeline.git.run("rev-parse", "--git-common-dir"))
    if not pipeline_common.is_absolute():
        pipeline_common = pipeline.repository / pipeline_common
    src_common = Path(src_git.run("rev-parse", "--git-common-dir"))
    if not src_common.is_absolute():
        src_common = source_path / src_common
    if src_common.resolve() != pipeline_common.resolve():
        raise OrchestratorError("Source worktree belongs to a different Git repository")

    index_path = Path(src_git.run("rev-parse", "--git-path", "index"))
    if not index_path.is_absolute():
        index_path = source_path / index_path
    source_index_digest = digest(index_path.read_bytes())
    source_branch = src_git.branch()

    historical_dir = pipeline.run_path(task, run_id)
    for p in (historical_dir, *historical_dir.parents):
        if p.is_symlink():
            raise OrchestratorError("Historical run path contains a symlink")
    if not historical_dir.is_dir():
        raise OrchestratorError("Historical run is missing")

    with ExitStack() as resources:
        resources.enter_context(slot(pipeline.locks))
        resources.enter_context(lock(pipeline.locks / f"{task}.lock"))
        resources.enter_context(lock(historical_dir / ".run.lock"))

        state_bytes = (historical_dir / "state.json").read_bytes()
        source = pipeline.status(task, run_id)
        if source.state != State.FAILED:
            raise OrchestratorError("Import requires a historical run in FAILED state")
        if source.task_id != task:
            raise OrchestratorError("Historical run task ID mismatch")
        if Path(source.repository).resolve() != pipeline.repository:
            raise OrchestratorError("Historical run repository mismatch")
        if not recovery_config_compatible(source.config, pipeline.config):
            raise OrchestratorError("Configuration changed since source run start")
        assert source.config is not None

        if src_git.sha() != source.base_sha:
            raise OrchestratorError("Source HEAD differs from historical base")
        if src_git.snapshot(source.base_sha) != expected_source_digest:
            raise OrchestratorError("Source candidate digest mismatch")

        required = {"task_card", "plan", "contract"}
        if not required.issubset(source.artifacts):
            raise OrchestratorError("Missing required historical artifact")
        pipeline.check_artifacts(historical_dir, source)
        files = historical_files(historical_dir, source)
        source_state_digest = digest(state_bytes)
        if files["state.json"] != source_state_digest or pipeline.status(task, run_id) != source:
            raise OrchestratorError("Historical state mutated during import")
        lineage_artifacts_digest = digest(
            json.dumps(dict(sorted(files.items())), separators=(",", ":")).encode("utf-8")
        )

        card = TaskCard.model_validate(read_json(historical_dir / source.artifacts["task_card"]))
        safe_path(card.path)
        original = pipeline.git.run(
            "show", f"{source.base_sha}:{card.path}", preserve_newlines=True
        )
        if (
            card.task_id != task
            or card.content_digest != source.task_digest
            or digest(original.encode()) != source.task_digest
        ):
            raise OrchestratorError("Historical task snapshot changed")
        contract = pipeline.contract(historical_dir, source)
        validate_contract(contract, card, source)
        plan = stored_plan(read_json(historical_dir / source.artifacts["plan"]))
        if plan.contract != contract:
            raise OrchestratorError("Historical plan and contract differ")

        actual_changed_paths = src_git.paths(source.base_sha)

        def unchanged_source() -> None:
            if (
                src_git.sha() != source.base_sha
                or src_git.branch() != source_branch
                or digest(index_path.read_bytes()) != source_index_digest
                or src_git.paths(source.base_sha) != actual_changed_paths
                or src_git.snapshot(source.base_sha) != expected_source_digest
                or historical_files(historical_dir, source) != files
            ):
                raise OrchestratorError("Source mutated during import")

        unchanged_source()

        # Capture and validate provenance manifest
        for p in (provenance_path, *provenance_path.parents):
            if p.is_symlink():
                raise OrchestratorError("Provenance manifest path contains a symlink")
        if not provenance_path.is_file():
            raise OrchestratorError("Provenance manifest is not a regular file")
        if provenance_path.stat().st_size > MAX_PROVENANCE_MANIFEST_BYTES:
            raise OrchestratorError("Provenance manifest exceeds size limit")

        manifest_bytes = provenance_path.read_bytes()
        if digest(manifest_bytes) != expected_provenance_digest:
            raise OrchestratorError("Provenance manifest digest mismatch")
        manifest_obj = strict_json_loads(manifest_bytes)
        if not isinstance(manifest_obj, dict):
            raise OrchestratorError("Provenance manifest must be a JSON object")
        manifest = ImportProvenanceManifest.model_validate(manifest_obj)
        if manifest.schema_version != 1:
            raise OrchestratorError("Unsupported provenance schema version")
        if manifest.task_id != task:
            raise OrchestratorError("Provenance manifest task ID mismatch")
        if manifest.base_sha != source.base_sha:
            raise OrchestratorError("Provenance manifest base SHA mismatch")
        if manifest.candidate_digest != expected_source_digest:
            raise OrchestratorError("Provenance manifest candidate digest mismatch")
        if len(manifest.artifacts) > MAX_PROVENANCE_ARTIFACTS:
            raise OrchestratorError("Too many artifacts in provenance manifest")
        if set(manifest.artifacts.keys()) != set(REQUIRED_V1_ARTIFACT_NAMES):
            raise OrchestratorError("Provenance manifest artifacts set mismatch")

        # Capture artifact bytes into memory
        captured_bytes: dict[str, bytes] = {}
        resolved_art_paths: set[Path] = set()
        total_art_bytes = 0
        for name in REQUIRED_V1_ARTIFACT_NAMES:
            ref = manifest.artifacts[name]
            art_path = Path(ref.path)
            for p in (art_path, *art_path.parents):
                if p.is_symlink():
                    raise OrchestratorError(f"Artifact {name} path contains a symlink")
            if not art_path.is_file():
                raise OrchestratorError(f"Artifact {name} is not a regular file")
            resolved = art_path.resolve()
            if resolved in resolved_art_paths:
                raise OrchestratorError(f"Duplicate resolved path for artifact: {resolved}")
            resolved_art_paths.add(resolved)
            stat = art_path.stat()
            if stat.st_size > MAX_ONE_ARTIFACT_BYTES:
                raise OrchestratorError(f"Artifact {name} exceeds single artifact size limit")
            if stat.st_size != ref.byte_size:
                raise OrchestratorError(f"Artifact {name} size mismatch with manifest")
            raw = art_path.read_bytes()
            if len(raw) != ref.byte_size or digest(raw) != ref.sha256:
                raise OrchestratorError(f"Artifact {name} byte digest mismatch")
            total_art_bytes += len(raw)
            if total_art_bytes > MAX_COMBINED_ARTIFACT_BYTES:
                raise OrchestratorError("Combined artifact bytes exceed limit")
            captured_bytes[name] = raw

        # Parse and validate source-manifest.txt
        try:
            sm_text = captured_bytes["source-manifest.txt"].decode("utf-8")
        except UnicodeDecodeError as err:
            raise OrchestratorError("source-manifest.txt is not valid UTF-8") from err
        sm_entries: dict[str, ImportFileDigest] = {}
        for line in sm_text.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(maxsplit=2)
            if len(parts) != 3:
                raise OrchestratorError(f"Invalid format in source-manifest.txt: {line}")
            f_sha, f_size_str, f_path = parts
            if not re.fullmatch(r"[0-9a-f]{64}", f_sha) or not f_size_str.isdigit():
                raise OrchestratorError(f"Invalid entry in source-manifest.txt: {line}")
            safe_path(f_path)
            if f_path in sm_entries:
                raise OrchestratorError(f"Duplicate path in source-manifest.txt: {f_path}")
            sm_entries[f_path] = ImportFileDigest(sha256=f_sha, byte_size=int(f_size_str))

        if set(sm_entries.keys()) != set(actual_changed_paths):
            raise OrchestratorError(
                "Source manifest changed paths do not exactly match Git changed paths"
            )

        for f_path, fd in sm_entries.items():
            real_f = source_path / f_path
            if not real_f.is_file():
                raise OrchestratorError(f"Source manifest entry does not exist as file: {f_path}")
            if real_f.stat().st_size != fd.byte_size or digest(real_f.read_bytes()) != fd.sha256:
                raise OrchestratorError(f"Source file {f_path} content does not match manifest")

        # Parse and validate Scout A, B, C
        scout_packets: dict[str, ImportScoutPacket] = {}
        expected_perspectives: dict[
            Literal["A", "B", "C"],
            Literal["probe_safety", "evidence_binding", "regression_authority"],
        ] = {
            "A": "probe_safety",
            "B": "evidence_binding",
            "C": "regression_authority",
        }
        scout_keys: tuple[Literal["A", "B", "C"], ...] = ("A", "B", "C")
        for s_name in scout_keys:
            s_raw = captured_bytes[f"scout-{s_name}.packet.json"]
            s_obj = strict_json_loads(s_raw)
            if not isinstance(s_obj, dict):
                raise OrchestratorError(f"Scout {s_name} packet must be a JSON object")
            packet = ImportScoutPacket.model_validate(s_obj)
            if packet.schema_version != 1:
                raise OrchestratorError(f"Scout {s_name} schema version mismatch")
            if packet.perspective != expected_perspectives[s_name]:
                raise OrchestratorError(f"Scout {s_name} perspective mismatch")
            if packet.candidate_digest != expected_source_digest:
                raise OrchestratorError(f"Scout {s_name} candidate digest mismatch")
            if packet.findings != []:
                raise OrchestratorError(f"Scout {s_name} findings must be empty")
            for rp in packet.reviewed_files:
                safe_path(rp)
                if rp not in actual_changed_paths:
                    raise OrchestratorError(
                        f"Scout {s_name} reviewed file not in changed paths: {rp}"
                    )
            scout_packets[s_name] = packet

        union_reviewed = (
            set(scout_packets["A"].reviewed_files)
            | set(scout_packets["B"].reviewed_files)
            | set(scout_packets["C"].reviewed_files)
        )
        if union_reviewed != set(actual_changed_paths):
            raise OrchestratorError("Scout reviewed files union does not match changed paths")

        # Parse and validate adjudication packet
        adj_raw = captured_bytes["adjudication-packet.json"]
        compact_raw = captured_bytes["adjudication-packet.compact.json"]
        adj_obj = strict_json_loads(adj_raw)
        compact_obj = strict_json_loads(compact_raw)
        if adj_obj != compact_obj:
            raise OrchestratorError("Adjudication packet and compact packet differ semantically")
        if not isinstance(adj_obj, dict):
            raise OrchestratorError("Adjudication packet must be a JSON object")
        adjudication = ImportAdjudicationPacket.model_validate(adj_obj)
        if adjudication.schema_version != 1:
            raise OrchestratorError("Adjudication schema version mismatch")
        if adjudication.candidate_identity.task_id != task:
            raise OrchestratorError("Adjudication task ID mismatch")
        if adjudication.candidate_identity.base_sha != source.base_sha:
            raise OrchestratorError("Adjudication base SHA mismatch")
        if adjudication.candidate_identity.candidate_digest != expected_source_digest:
            raise OrchestratorError("Adjudication candidate digest mismatch")
        if adjudication.source_manifest != sm_entries:
            raise OrchestratorError("Adjudication source manifest mismatch")
        if len(adjudication.semantic_discovery.scouts) != 3:
            raise OrchestratorError("Adjudication scouts count mismatch")
        adj_scouts = {s.scout: s for s in adjudication.semantic_discovery.scouts}
        if set(adj_scouts.keys()) != {"A", "B", "C"}:
            raise OrchestratorError("Adjudication scout identifiers mismatch")
        for s_name in scout_keys:
            s_sum = adj_scouts[s_name]
            if s_sum.perspective != expected_perspectives[s_name]:
                raise OrchestratorError(f"Adjudication scout {s_name} perspective mismatch")
            if s_sum.packet_sha256 != digest(captured_bytes[f"scout-{s_name}.packet.json"]):
                raise OrchestratorError(f"Adjudication scout {s_name} packet SHA mismatch")
            if s_sum.reviewed_files != scout_packets[s_name].reviewed_files:
                raise OrchestratorError(f"Adjudication scout {s_name} reviewed files mismatch")
            if s_sum.finding_count != 0:
                raise OrchestratorError(f"Adjudication scout {s_name} finding count must be 0")
        if (
            adjudication.semantic_discovery.finding_count != 0
            or adjudication.semantic_discovery.findings != []
        ):
            raise OrchestratorError("Adjudication semantic discovery findings must be empty")

        # Parse and validate judge prompt
        try:
            prompt_text = captured_bytes["heavy-judge.prompt.txt"].decode("utf-8")
        except UnicodeDecodeError as err:
            raise OrchestratorError("Judge prompt is not valid UTF-8") from err
        begin_token = "BEGIN ADJUDICATION PACKET"
        end_token = "END ADJUDICATION PACKET"
        if prompt_text.count(begin_token) != 1 or prompt_text.count(end_token) != 1:
            raise OrchestratorError(
                "Judge prompt must contain exactly one pair of packet delimiters"
            )
        start_idx = prompt_text.index(begin_token) + len(begin_token)
        end_idx = prompt_text.index(end_token)
        if start_idx >= end_idx:
            raise OrchestratorError("Judge prompt packet delimiters misordered")
        embedded_text = prompt_text[start_idx:end_idx].strip()
        embedded_obj = strict_json_loads(embedded_text)
        if embedded_obj != compact_obj or embedded_text != compact_raw.decode("utf-8").strip():
            raise OrchestratorError(
                "Embedded adjudication packet in judge prompt does not match validated packet"
            )

        # Parse and validate judge schema
        schema_obj = strict_json_loads(captured_bytes["heavy-judge.schema.json"])
        if not isinstance(schema_obj, dict):
            raise OrchestratorError("Judge schema must be a JSON object")

        # Parse and validate heavy judge response
        resp_obj = strict_json_loads(captured_bytes["heavy-judge.response.json"])
        if not isinstance(resp_obj, dict):
            raise OrchestratorError("Judge response must be a JSON object")
        judge_resp = ImportHeavyJudgeResponse.model_validate(resp_obj)
        if judge_resp.schema_version != 1:
            raise OrchestratorError("Judge response schema version mismatch")
        if judge_resp.candidate_digest != expected_source_digest:
            raise OrchestratorError("Judge response candidate digest mismatch")
        if judge_resp.decision != "PASS":
            raise OrchestratorError(
                f"Judge response decision must be PASS, got {judge_resp.decision}"
            )
        if judge_resp.confirmed_findings != []:
            raise OrchestratorError("Judge response confirmed findings must be empty")
        if judge_resp.dismissed_findings != []:
            raise OrchestratorError("Judge response dismissed findings must be empty")
        if judge_resp.evidence_requests != []:
            raise OrchestratorError("Judge response evidence requests must be empty")

        unchanged_source()

        # Construct target run directory and worktree
        import_id = re.sub(r"[^0-9]", "", now()) + "-" + uuid4().hex[:8]
        imported = RunState(
            task_id=task,
            run_id=import_id,
            repository=str(pipeline.repository),
            base_branch=source.base_branch,
            base_sha=source.base_sha,
            worktree_path=str(pipeline.worktrees / f"{task}-{import_id}"),
            worktree_branch=f"agent/{task}-{import_id}",
            config=pipeline.config,
            task_digest=source.task_digest,
            contract_digest=source.contract_digest,
            fix_cycle=source.fix_cycle,
            max_fix_cycles=source.max_fix_cycles,
        )
        target_dir = pipeline.run_path(task, import_id)
        target_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
        resources.enter_context(lock(target_dir / ".run.lock"))
        pipeline.save(target_dir, imported)

        try:
            ignored = execute(
                ["git", "check-ignore", "-q", str(target_dir / "state.json")],
                pipeline.repository,
                timeout=60,
            )
            if ignored.exit_code or ignored.timed_out or ignored.oversized:
                raise OrchestratorError("Configured run directory must be gitignored")
            target = Path(imported.worktree_path)
            with lock(pipeline.locks / "worktrees.lock", wait_seconds=60):
                pipeline.git.create_worktree(target, imported.worktree_branch, source.base_sha)
            if task_card(target, task) != card:
                raise OrchestratorError(
                    "Task snapshot differs from repository-owned historical card"
                )
            materialize_candidate(source_path, target, source.base_sha)
            target_git = Git(target)

            def unchanged_candidate() -> None:
                pipeline.git.assert_worktree(target, imported.worktree_branch)
                if target_git.snapshot(source.base_sha) != expected_source_digest:
                    raise OrchestratorError("Imported candidate digest mismatch")

            unchanged_source()
            unchanged_candidate()

            changed = pipeline.scope(imported, contract)
            if "docs/changelogs.md" not in changed:
                raise OrchestratorError("Repository requires worker changelog before handoff")
            if set(changed) != set(actual_changed_paths):
                raise OrchestratorError(
                    "Materialized changed files do not match actual changed files"
                )

            carry = {"task_card", "plan", "contract"} | (
                {"skills"} if "skills" in source.artifacts else set()
            )
            for key in sorted(carry):
                name = f"00-{key}.json"
                payload = (historical_dir / source.artifacts[key]).read_bytes()
                (target_dir / name).write_bytes(payload)
                imported.artifacts[key] = name
                imported.artifact_digests[name] = digest(payload)

            imported_art_refs: dict[str, ImportedArtifactRef] = {}
            for name in REQUIRED_V1_ARTIFACT_NAMES:
                raw = captured_bytes[name]
                flat_name = f"00-imported-{name}"
                (target_dir / flat_name).write_bytes(raw)
                raw_digest = digest(raw)
                imported.artifacts[f"imported_{name}"] = flat_name
                imported.artifact_digests[flat_name] = raw_digest
                imported_art_refs[name] = ImportedArtifactRef(
                    logical_name=name,
                    artifact_file=flat_name,
                    sha256=raw_digest,
                    byte_size=len(raw),
                )

            semantic_evidence = ImportedSemanticEvidence(
                schema_version=1,
                task_id=task,
                base_sha=source.base_sha,
                candidate_digest=expected_source_digest,
                source_manifest_digest=digest(captured_bytes["source-manifest.txt"]),
                adjudication_packet_digest=digest(captured_bytes["adjudication-packet.json"]),
                adjudication_compact_digest=digest(
                    captured_bytes["adjudication-packet.compact.json"]
                ),
                judge_response_digest=digest(captured_bytes["heavy-judge.response.json"]),
                scout_packet_digests={
                    "A": digest(captured_bytes["scout-A.packet.json"]),
                    "B": digest(captured_bytes["scout-B.packet.json"]),
                    "C": digest(captured_bytes["scout-C.packet.json"]),
                },
                scout_reviewed_files={
                    "A": scout_packets["A"].reviewed_files,
                    "B": scout_packets["B"].reviewed_files,
                    "C": scout_packets["C"].reviewed_files,
                },
                all_reviewed_files=sorted(actual_changed_paths),
                judge_decision="PASS",
                artifacts=imported_art_refs,
            )
            pipeline.artifact(target_dir, imported, "imported_semantic_evidence", semantic_evidence)
            imported_sem_digest = imported.artifact_digests[
                imported.artifacts["imported_semantic_evidence"]
            ]

            pipeline.verify(target_dir, imported, pipeline.config.setup_commands, "setup")
            unchanged_source()
            unchanged_candidate()

            pipeline.reverify_candidate(target_dir, imported, contract)
            unchanged_source()
            unchanged_candidate()

            source_cfg = source.config
            assert source_cfg is not None
            origin = CandidateImportOrigin(
                schema_version=1,
                task_id=task,
                lineage_run_id=source.run_id,
                lineage_state_digest=source_state_digest,
                lineage_artifacts_digest=lineage_artifacts_digest,
                base_sha=source.base_sha,
                task_digest=source.task_digest,
                contract_digest=source.contract_digest,
                source_worktree=str(source_path.resolve()),
                source_branch=source_branch,
                source_index_digest=source_index_digest,
                candidate_digest=expected_source_digest,
                provenance_digest=expected_provenance_digest,
                import_run_id=import_id,
                import_branch=imported.worktree_branch,
                import_worktree=imported.worktree_path,
                source_fix_cycle=source.fix_cycle,
                import_fix_cycle=imported.fix_cycle,
                max_fix_cycles=imported.max_fix_cycles,
                lineage_config_digest=config_digest(source_cfg),
                import_config_digest=config_digest(pipeline.config),
                liveness_config_upgraded=is_liveness_config_upgraded(source_cfg, pipeline.config),
                control_plane_cwd=str(control_plane_root()),
                imported_semantic_evidence_digest=imported_sem_digest,
            )
            pipeline.artifact(target_dir, imported, "candidate_import_origin", origin)

            unchanged_source()
            unchanged_candidate()
            pipeline.check_artifacts(target_dir, imported)

            ev_bundle = pipeline.evidence_bundle(target_dir, imported)
            if ev_bundle.verification.failed or not ev_bundle.verification.passed:
                raise OrchestratorError("Evidence bundle verification failed or unverified")

            # Final publication to AUDIT_PASS
            imported.state = State.AUDIT_PASS
            imported.audited_digest = expected_source_digest
            imported.verified_digest = expected_source_digest
            imported.current_agent = None
            imported.blocked_from = None
            imported.last_error = None
            pipeline.save(target_dir, imported)
            pipeline.check_artifacts(target_dir, imported)
            pipeline.report(target_dir, imported)
            return imported
        except (OrchestratorError, OSError, ValidationError) as error:
            return pipeline.fail(target_dir, imported, error)
        except KeyboardInterrupt:
            return pipeline.fail(
                target_dir,
                imported,
                OrchestratorError("Import interrupted; construction uncertain"),
            )

"""Behavioral tests for deterministic host evidence collection and EvidenceBundle."""

import inspect
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from pydantic import ValidationError
from tools.orchestrator.core import (
    EvidenceBundle,
    FrozenEvidenceIdentity,
    OrchestratorError,
    VerificationCollection,
    command_declaration_digest,
    digest,
)
from tools.orchestrator.evidence import (
    build_evidence_bundle,
    collect_candidate_provenance,
    collect_scope_evidence,
    collect_verification_evidence,
    create_artifact_ref,
    validate_artifact_ref,
    validate_evidence_bundle,
)
from tools.orchestrator.runtime import Git


def make_git_repo(tmp_path: Path) -> tuple[Path, str, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    git = Git(repo)
    git.run("init")
    git.run("config", "user.name", "Test Agent")
    git.run("config", "user.email", "test@example.com")
    (repo / "initial.txt").write_text("initial content", encoding="utf-8")
    git.run("add", "initial.txt")
    git.run("commit", "-m", "initial commit")
    base_sha = git.sha("HEAD")
    git.run("checkout", "-b", "feature/t088")
    return repo, base_sha, "feature/t088"


COMMANDS = (("python", "-m", "ruff", "check", "."), ("python", "-m", "pytest", "-q"))


def frozen_identity(repo: Path, base_sha: str, branch: str) -> FrozenEvidenceIdentity:
    return FrozenEvidenceIdentity.freeze(
        "T088", base_sha, branch, Git(repo).snapshot(base_sha), COMMANDS
    )


def sample_verification_collection(
    failed: bool = False,
    setup_error: str | None = None,
    *,
    identity: FrozenEvidenceIdentity | None = None,
) -> VerificationCollection:
    raw_results: tuple[dict[str, object], ...] = (
        {
            "command_index": 0,
            "command": ["python", "-m", "ruff", "check", "."],
            "exit_code": 0,
            "timed_out": False,
            "oversized": False,
            "started_at": "2026-10-06T10:00:00+00:00",
            "ended_at": "2026-10-06T10:00:01+00:00",
            "stdout_bytes": 45,
            "stderr_bytes": 0,
            "stdout_digest": digest(b"all checks passed"),
            "stderr_digest": digest(b""),
        },
        {
            "command_index": 1,
            "command": ["python", "-m", "pytest", "-q"],
            "exit_code": 7 if failed else 0,
            "timed_out": False,
            "oversized": False,
            "started_at": "2026-10-06T10:00:01+00:00",
            "ended_at": "2026-10-06T10:00:03+00:00",
            "stdout_bytes": 120,
            "stderr_bytes": 30,
            "stdout_digest": digest(b"pytest output"),
            "stderr_digest": digest(b"pytest err"),
        },
    )
    if setup_error is not None:
        raw_results = raw_results[:1]
    identity = identity or FrozenEvidenceIdentity.freeze(
        "T088", "a" * 64, "feature/t088", "a" * 64, COMMANDS
    )
    for index, raw in enumerate(raw_results):
        raw["declaration_digest"] = command_declaration_digest(COMMANDS[index])
        raw["duration_ns"] = 100 + index
    return VerificationCollection(
        identity=identity, results=raw_results, failed=failed, setup_error=setup_error
    )


def test_host_only_bundle_construction_no_ai_or_provider_calls(tmp_path: Path) -> None:
    # 1. Structural check: evidence.py must not import AgentProvider, CliProvider, or Pipeline
    import tools.orchestrator.evidence as evidence_mod

    source_text = inspect.getsource(evidence_mod)
    assert "AgentProvider" not in source_text
    assert "CliProvider" not in source_text
    assert "Pipeline" not in source_text

    # 2. Behavioral check: execute build_evidence_bundle without any provider or Pipeline
    repo, base_sha, branch = make_git_repo(tmp_path)
    (repo / "file.txt").write_text("new file", encoding="utf-8")
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    (artifacts_dir / "00-checks.json").write_text('{"status": "ok"}', encoding="utf-8")
    ref = create_artifact_ref(
        "checks",
        "00-checks.json",
        artifacts_dir,
        "test_execution_record",
        identity=frozen_identity(repo, base_sha, branch),
    )

    bundle = build_evidence_bundle(
        worktree=repo,
        task_id="T088",
        base_sha=base_sha,
        branch=branch,
        allowed_paths=["file.txt"],
        verification_collection=sample_verification_collection(
            identity=frozen_identity(repo, base_sha, branch)
        ),
        artifacts_dir=artifacts_dir,
        artifact_refs=[ref],
    )
    assert isinstance(bundle, EvidenceBundle)
    assert bundle.is_complete is True


def test_exact_candidate_provenance_binding(tmp_path: Path) -> None:
    repo, base_sha, branch = make_git_repo(tmp_path)
    (repo / "tracked.txt").write_text("change in tracked", encoding="utf-8")
    git = Git(repo)
    expected_snapshot = git.snapshot(base_sha)

    prov = collect_candidate_provenance(repo, base_sha, branch)
    assert prov.base_sha == base_sha
    assert prov.branch == branch
    assert prov.source_digest == expected_snapshot
    assert prov.head_sha == git.sha("HEAD")
    assert prov.changed_paths == ["tracked.txt"]


def test_staged_index_and_working_tree_distinction(tmp_path: Path) -> None:
    repo, base_sha, branch = make_git_repo(tmp_path)
    git = Git(repo)

    # State A: Staged change on tracked file
    (repo / "initial.txt").write_text("staged content", encoding="utf-8")
    git.run("add", "initial.txt")
    prov_staged = collect_candidate_provenance(repo, base_sha, branch)
    assert prov_staged.staged_paths == ["initial.txt"]
    assert prov_staged.unstaged_paths == []
    assert prov_staged.staged_diff_digest != digest(b"")
    assert prov_staged.unstaged_diff_digest == digest(b"")

    # State B: Unstaged change (reset index, keep working tree change)
    git.run("reset", "HEAD", "initial.txt")
    prov_unstaged = collect_candidate_provenance(repo, base_sha, branch)
    assert prov_unstaged.staged_paths == []
    assert prov_unstaged.unstaged_paths == ["initial.txt"]
    assert prov_unstaged.staged_diff_digest == digest(b"")
    assert prov_unstaged.unstaged_diff_digest != digest(b"")

    # Provenance distinguishing both states
    assert prov_staged.staged_diff_digest != prov_unstaged.staged_diff_digest
    assert prov_staged.unstaged_diff_digest != prov_unstaged.unstaged_diff_digest


def test_untracked_candidate_identity_preserved(tmp_path: Path) -> None:
    repo, base_sha, branch = make_git_repo(tmp_path)
    (repo / "untracked1.txt").write_text("hello untracked", encoding="utf-8")
    prov1 = collect_candidate_provenance(repo, base_sha, branch)
    assert prov1.untracked_paths == ["untracked1.txt"]
    assert prov1.untracked_digest != digest(b"")

    (repo / "untracked1.txt").write_text("mutated content", encoding="utf-8")
    prov2 = collect_candidate_provenance(repo, base_sha, branch)
    assert prov2.untracked_paths == ["untracked1.txt"]
    assert prov2.untracked_digest != prov1.untracked_digest


def test_deterministic_scope_calculation_and_unexpected_fails_closed(tmp_path: Path) -> None:
    repo, base_sha, branch = make_git_repo(tmp_path)
    (repo / "allowed.txt").write_text("allowed edit", encoding="utf-8")

    # Valid in-scope change
    scope_pass = collect_scope_evidence(repo, base_sha, ["allowed.txt", "docs/changelogs.md"])
    assert scope_pass.verdict == "PASS"
    assert scope_pass.unexpected_changed_paths == []

    # Unexpected out-of-scope change
    (repo / "secret_out_of_scope.txt").write_text("out of bounds", encoding="utf-8")
    scope_fail = collect_scope_evidence(repo, base_sha, ["allowed.txt"])
    assert scope_fail.verdict == "FAIL"
    assert "secret_out_of_scope.txt" in scope_fail.unexpected_changed_paths

    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    # build_evidence_bundle must fail closed on unexpected path
    with pytest.raises(OrchestratorError, match="BLOCKED_FOR_SCOPE_EXTENSION"):
        build_evidence_bundle(
            worktree=repo,
            task_id="T088",
            base_sha=base_sha,
            branch=branch,
            allowed_paths=["allowed.txt"],
            verification_collection=sample_verification_collection(
                identity=frozen_identity(repo, base_sha, branch)
            ),
            artifacts_dir=artifacts_dir,
            fail_closed=True,
        )


def test_verification_declaration_order_and_failure_representation() -> None:
    collection = sample_verification_collection(failed=True)
    evidence = collect_verification_evidence(collection)
    assert evidence.failed is True
    assert evidence.passed is False
    assert [c.command_index for c in evidence.commands] == [0, 1]
    assert evidence.commands[0].exit_code == 0
    assert evidence.commands[0].failure_classification is None
    assert evidence.commands[1].exit_code == 7
    assert evidence.commands[1].failure_classification == "COMMAND_FAILED"


def test_setup_failure_fails_closed_and_not_misreported_as_pass(tmp_path: Path) -> None:
    setup_error = "SETUP_FAILED: audit_checks: python interpreter not found"
    collection = sample_verification_collection(failed=True, setup_error=setup_error)
    evidence = collect_verification_evidence(collection)
    assert evidence.failed is True
    assert evidence.passed is False
    assert evidence.setup_error == setup_error

    repo, base_sha, branch = make_git_repo(tmp_path)
    (repo / "allowed.txt").write_text("valid", encoding="utf-8")
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()

    with pytest.raises(OrchestratorError, match="SETUP_FAILED"):
        build_evidence_bundle(
            worktree=repo,
            task_id="T088",
            base_sha=base_sha,
            branch=branch,
            allowed_paths=["allowed.txt"],
            verification_collection=sample_verification_collection(
                failed=True,
                setup_error=setup_error,
                identity=frozen_identity(repo, base_sha, branch),
            ),
            artifacts_dir=artifacts_dir,
            fail_closed=True,
        )


def test_artifact_ref_creation_tamper_detection_and_path_escape(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    test_file = artifacts_dir / "test_artifact.json"
    content = b'{"result": "success"}'
    test_file.write_bytes(content)

    # 1. Successful reference creation
    ref = create_artifact_ref("test", "test_artifact.json", artifacts_dir, "test_record")
    assert ref.byte_size == len(content)
    assert ref.digest == digest(content)
    validate_artifact_ref(ref, artifacts_dir)

    # 2. Tampering detected: byte mutation (same size, different content -> digest mismatch)
    test_file.write_bytes(b'{"result": "failure"}')
    with pytest.raises(OrchestratorError, match="digest mismatch"):
        validate_artifact_ref(ref, artifacts_dir)

    # 3. Tampering detected: size mutation
    test_file.write_bytes(b'{"result": "tampered with much longer string"}')
    with pytest.raises(OrchestratorError, match="size mismatch"):
        validate_artifact_ref(ref, artifacts_dir)

    # 4. Path traversal / escape rejected
    with pytest.raises(OrchestratorError, match="Unsafe"):
        create_artifact_ref("escape", "../outside.json", artifacts_dir, "test")

    outside_file = tmp_path / "outside.json"
    outside_file.write_text("outside", encoding="utf-8")
    symlink_file = artifacts_dir / "symlink_escape.json"
    symlink_file.symlink_to(outside_file)
    with pytest.raises(OrchestratorError, match="symlink"):
        create_artifact_ref("symlink", "symlink_escape.json", artifacts_dir, "test")


def test_validate_evidence_bundle_mismatches(tmp_path: Path) -> None:
    repo, base_sha, branch = make_git_repo(tmp_path)
    (repo / "f.txt").write_text("edit", encoding="utf-8")
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    (artifacts_dir / "out.json").write_text("{}", encoding="utf-8")
    ref = create_artifact_ref(
        "art", "out.json", artifacts_dir, "record", identity=frozen_identity(repo, base_sha, branch)
    )

    bundle = build_evidence_bundle(
        worktree=repo,
        task_id="T088",
        base_sha=base_sha,
        branch=branch,
        allowed_paths=["f.txt"],
        verification_collection=sample_verification_collection(
            identity=frozen_identity(repo, base_sha, branch)
        ),
        artifacts_dir=artifacts_dir,
        artifact_refs=[ref],
    )
    # Valid bundle passes validation
    validate_evidence_bundle(
        bundle,
        artifacts_dir,
        expected_base_sha=base_sha,
        expected_branch=branch,
        expected_source_digest=bundle.source_digest,
    )

    # Wrong base_sha rejected
    with pytest.raises(OrchestratorError, match="base_sha mismatch"):
        validate_evidence_bundle(bundle, artifacts_dir, expected_base_sha="f" * 64)

    # Wrong branch rejected
    with pytest.raises(OrchestratorError, match="branch mismatch"):
        validate_evidence_bundle(bundle, artifacts_dir, expected_branch="wrong-branch")

    # Wrong source_digest rejected
    with pytest.raises(OrchestratorError, match="source_digest mismatch"):
        validate_evidence_bundle(bundle, artifacts_dir, expected_source_digest="f" * 64)

    # Mutated artifact rejected
    (artifacts_dir / "out.json").write_text("[]", encoding="utf-8")
    with pytest.raises(OrchestratorError, match="digest mismatch"):
        validate_evidence_bundle(bundle, artifacts_dir)


def test_shuffled_inputs_produce_canonical_semantic_ordering(tmp_path: Path) -> None:
    repo, base_sha, branch = make_git_repo(tmp_path)
    (repo / "b.txt").write_text("b", encoding="utf-8")
    (repo / "a.txt").write_text("a", encoding="utf-8")

    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    (artifacts_dir / "art2.json").write_text("2", encoding="utf-8")
    (artifacts_dir / "art1.json").write_text("1", encoding="utf-8")

    ref1 = create_artifact_ref(
        "art1",
        "art1.json",
        artifacts_dir,
        "record",
        identity=frozen_identity(repo, base_sha, branch),
    )
    ref2 = create_artifact_ref(
        "art2",
        "art2.json",
        artifacts_dir,
        "record",
        identity=frozen_identity(repo, base_sha, branch),
    )

    # Order 1: forward
    bundle1 = build_evidence_bundle(
        worktree=repo,
        task_id="T088",
        base_sha=base_sha,
        branch=branch,
        allowed_paths=["a.txt", "b.txt"],
        verification_collection=sample_verification_collection(
            identity=frozen_identity(repo, base_sha, branch)
        ),
        artifacts_dir=artifacts_dir,
        artifact_refs=[ref1, ref2],
    )

    # Order 2: reversed allowed paths and reversed artifact refs
    bundle2 = build_evidence_bundle(
        worktree=repo,
        task_id="T088",
        base_sha=base_sha,
        branch=branch,
        allowed_paths=["b.txt", "a.txt"],
        verification_collection=sample_verification_collection(
            identity=frozen_identity(repo, base_sha, branch)
        ),
        artifacts_dir=artifacts_dir,
        artifact_refs=[ref2, ref1],
    )

    # Semantic payloads (which exclude variable timing) must be strictly identical
    assert bundle1.semantic_payload() == bundle2.semantic_payload()
    assert [a.name for a in bundle1.artifacts] == ["art1", "art2"]
    assert [a.name for a in bundle2.artifacts] == ["art1", "art2"]
    assert bundle1.scope.allowed_paths == ["a.txt", "b.txt"]
    assert bundle2.scope.allowed_paths == ["a.txt", "b.txt"]


def test_thread_completion_order_cannot_alter_semantic_ordering(tmp_path: Path) -> None:
    repo, base_sha, branch = make_git_repo(tmp_path)
    (repo / "f.txt").write_text("edit", encoding="utf-8")
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    (artifacts_dir / "log.json").write_text("{}", encoding="utf-8")
    ref = create_artifact_ref(
        "log", "log.json", artifacts_dir, "record", identity=frozen_identity(repo, base_sha, branch)
    )

    bundles: list[dict[str, object]] = []
    lock = threading.Lock()

    def worker(reverse: bool) -> None:
        allowed = ["z.txt", "f.txt"] if reverse else ["f.txt", "z.txt"]
        b = build_evidence_bundle(
            worktree=repo,
            task_id="T088",
            base_sha=base_sha,
            branch=branch,
            allowed_paths=allowed,
            verification_collection=sample_verification_collection(
                identity=frozen_identity(repo, base_sha, branch)
            ),
            artifacts_dir=artifacts_dir,
            artifact_refs=[ref],
        )
        with lock:
            bundles.append(b.semantic_payload())

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(worker, i % 2 == 0) for i in range(8)]
        for f in futures:
            f.result()

    assert len(bundles) == 8
    first = bundles[0]
    for other in bundles[1:]:
        assert other == first


def test_evidence_bundle_rejects_frozen_source_mismatch(tmp_path: Path) -> None:
    from tools.orchestrator.core import VerificationRequest
    from tools.orchestrator.workflow import collect_verification

    repo, base_sha, branch = make_git_repo(tmp_path)
    source = repo / "initial.txt"
    source.write_text("candidate A\n", encoding="utf-8")
    commands = (("git", "diff", "--check"),)
    identity_a = FrozenEvidenceIdentity.freeze(
        "T088", base_sha, branch, Git(repo).snapshot(base_sha), commands
    )
    verification_a = collect_verification(VerificationRequest(repo, commands, None, identity_a))
    assert collect_verification_evidence(verification_a).passed
    source.write_text("candidate B\n", encoding="utf-8")
    assert (
        collect_candidate_provenance(repo, base_sha, branch).source_digest
        != identity_a.source_digest
    )
    with pytest.raises(OrchestratorError, match="Frozen verification provenance mismatch"):
        build_evidence_bundle(
            worktree=repo,
            task_id="T088",
            base_sha=base_sha,
            branch=branch,
            allowed_paths=["initial.txt"],
            verification_collection=verification_a,
            artifacts_dir=tmp_path,
        )


def test_evidence_bundle_rejects_successful_prefix(tmp_path: Path) -> None:
    from dataclasses import replace

    repo, base_sha, branch = make_git_repo(tmp_path)
    collection = sample_verification_collection(identity=frozen_identity(repo, base_sha, branch))
    prefix = replace(collection, results=collection.results[:1])
    with pytest.raises((ValidationError, OrchestratorError), match="Successful prefix"):
        build_evidence_bundle(
            worktree=repo,
            task_id="T088",
            base_sha=base_sha,
            branch=branch,
            allowed_paths=[],
            verification_collection=prefix,
            artifacts_dir=tmp_path,
        )


def test_evidence_bundle_preserves_explicit_failed_prefix(tmp_path: Path) -> None:
    repo, base_sha, branch = make_git_repo(tmp_path)
    commands = (*COMMANDS, ("git", "diff", "--check"))
    identity = FrozenEvidenceIdentity.freeze(
        "T088", base_sha, branch, Git(repo).snapshot(base_sha), commands
    )
    collection = sample_verification_collection(failed=True, identity=identity)
    bundle = build_evidence_bundle(
        worktree=repo,
        task_id="T088",
        base_sha=base_sha,
        branch=branch,
        allowed_paths=[],
        verification_collection=collection,
        artifacts_dir=tmp_path,
    )
    assert bundle.is_complete and not bundle.verification.passed and bundle.verification.failed
    assert [c.command_index for c in bundle.verification.commands] == [0, 1]
    assert len(bundle.verification.identity.required_command_digests) == 3
    assert bundle.verification.commands[1].failure_classification == "COMMAND_FAILED"


def test_evidence_bundle_command_declaration_mismatch_is_rejected(tmp_path: Path) -> None:
    from dataclasses import replace

    repo, base_sha, branch = make_git_repo(tmp_path)
    commands_a = (("python", "-m", "ruff", "check", "synthetic-private-argument-A"),)
    commands_b = (("python", "-m", "ruff", "check", "synthetic-private-argument-B"),)
    identity_a = FrozenEvidenceIdentity.freeze(
        "T088", base_sha, branch, Git(repo).snapshot(base_sha), commands_a
    )
    identity_b = FrozenEvidenceIdentity.freeze(
        "T088", base_sha, branch, identity_a.source_digest, commands_b
    )
    raw = dict(sample_verification_collection().results[0])
    raw["command"] = ["python", "<arguments withheld>"]
    raw["declaration_digest"] = command_declaration_digest(commands_a[0])
    collection_a = VerificationCollection(identity_a, (raw,))
    bundle = build_evidence_bundle(
        worktree=repo,
        task_id="T088",
        base_sha=base_sha,
        branch=branch,
        allowed_paths=[],
        verification_collection=collection_a,
        artifacts_dir=tmp_path,
    )
    assert "synthetic-private-argument" not in bundle.model_dump_json()
    assert identity_a.required_command_digests != identity_b.required_command_digests
    with pytest.raises((ValidationError, OrchestratorError), match="command declaration mismatch"):
        collect_verification_evidence(replace(collection_a, identity=identity_b))


@pytest.mark.parametrize(
    "field",
    [
        "stdout_digest",
        "stderr_digest",
        "stdout_bytes",
        "stderr_bytes",
        "timed_out",
        "oversized",
    ],
)
def test_evidence_bundle_missing_mandatory_execution_metadata_rejected(field: str) -> None:
    from dataclasses import replace

    collection = sample_verification_collection()
    result = dict(collection.results[0])
    del result[field]
    with pytest.raises(OrchestratorError, match="Missing mandatory"):
        collect_verification_evidence(replace(collection, results=(result, collection.results[1])))


def test_evidence_bundle_timing_only_variation_has_equal_semantic_payload(tmp_path: Path) -> None:
    repo, base_sha, branch = make_git_repo(tmp_path)
    bundle_a = build_evidence_bundle(
        worktree=repo,
        task_id="T088",
        base_sha=base_sha,
        branch=branch,
        allowed_paths=[],
        verification_collection=sample_verification_collection(
            identity=frozen_identity(repo, base_sha, branch)
        ),
        artifacts_dir=tmp_path,
    )
    data = bundle_a.model_dump()
    data["timing"] = {
        "collected_at": "2026-10-01",
        "duration_ns": 9876,
        "step_durations_ns": {"provenance": 123},
    }
    for command in data["verification"]["commands"]:
        command["duration_ns"] += 12345
    bundle_b = EvidenceBundle.model_validate(data)
    assert bundle_a.model_dump() != bundle_b.model_dump()
    assert bundle_a.semantic_payload() == bundle_b.semantic_payload()


def test_deterministic_evidence_duration_uses_monotonic_clock_with_backward_wall_time(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import time

    import tools.orchestrator.workflow as workflow
    from tools.orchestrator.core import VerificationRequest
    from tools.orchestrator.runtime import ProcessResult

    commands = (("git", "diff", "--check"),)
    identity = FrozenEvidenceIdentity.freeze("T088", "a" * 64, "feature/test", "a" * 64, commands)
    ticks = iter((10_000, 10_750))
    monkeypatch.setattr(time, "monotonic_ns", lambda: next(ticks))

    def execute(command: list[str], cwd: Path, *, timeout: int | None = None) -> ProcessResult:
        assert timeout is None
        return ProcessResult(
            tuple(command),
            str(cwd),
            "2026-10-06T10:00:03+00:00",
            "2026-10-06T10:00:01+00:00",
            0,
            "",
            "",
        )

    monkeypatch.setattr(workflow, "execute", execute)
    collection = workflow.collect_verification(
        VerificationRequest(tmp_path, commands, None, identity)
    )
    evidence = collect_verification_evidence(collection)
    started_at = collection.results[0]["started_at"]
    ended_at = collection.results[0]["ended_at"]
    assert isinstance(started_at, str) and isinstance(ended_at, str)
    assert ended_at < started_at
    assert evidence.commands[0].duration_ns == 750
    assert evidence.passed


def test_evidence_bundle_artifact_frozen_identity_and_audit_checks_source_association(
    tmp_path: Path,
) -> None:
    import json

    repo, base_sha, branch = make_git_repo(tmp_path)
    identity_a = frozen_identity(repo, base_sha, branch)
    checks = tmp_path / "checks.json"
    checks.write_text(
        json.dumps(
            {
                "level": "TEST",
                "source_digest": identity_a.source_digest,
                "results": sample_verification_collection(identity=identity_a).results,
            }
        )
    )
    ref_a = create_artifact_ref(
        "audit_checks", checks.name, tmp_path, "test_execution_record", identity=identity_a
    )
    (repo / "initial.txt").write_text("candidate B\n")
    identity_b = frozen_identity(repo, base_sha, branch)
    collection_b = sample_verification_collection(identity=identity_b)
    with pytest.raises(OrchestratorError, match="Artifact frozen identity mismatch"):
        build_evidence_bundle(
            worktree=repo,
            task_id="T088",
            base_sha=base_sha,
            branch=branch,
            allowed_paths=["initial.txt"],
            verification_collection=collection_b,
            artifacts_dir=tmp_path,
            artifact_refs=[ref_a],
        )
    rebound_ref = create_artifact_ref(
        "audit_checks", checks.name, tmp_path, "test_execution_record", identity=identity_b
    )
    with pytest.raises(OrchestratorError, match="audit_checks frozen source mismatch"):
        build_evidence_bundle(
            worktree=repo,
            task_id="T088",
            base_sha=base_sha,
            branch=branch,
            allowed_paths=["initial.txt"],
            verification_collection=collection_b,
            artifacts_dir=tmp_path,
            artifact_refs=[rebound_ref],
        )


def test_evidence_bundle_validates_historical_audit_checks_without_rewriting(
    tmp_path: Path,
) -> None:
    import json

    repo, base_sha, branch = make_git_repo(tmp_path)
    identity = frozen_identity(repo, base_sha, branch)
    collection = sample_verification_collection(identity=identity)
    historical_results = [
        {
            key: value
            for key, value in raw.items()
            if key not in {"declaration_digest", "duration_ns"}
        }
        for raw in collection.results
    ]
    checks = tmp_path / "checks.json"
    record = {
        "level": "TEST",
        "source_digest": identity.source_digest,
        "results": historical_results,
    }
    checks.write_text(json.dumps(record), encoding="utf-8")
    original = checks.read_bytes()
    ref = create_artifact_ref(
        "audit_checks", checks.name, tmp_path, "test_execution_record", identity=identity
    )
    bundle = build_evidence_bundle(
        worktree=repo,
        task_id="T088",
        base_sha=base_sha,
        branch=branch,
        allowed_paths=[],
        verification_collection=collection,
        artifacts_dir=tmp_path,
        artifact_refs=[ref],
    )
    assert bundle.verification.passed
    assert checks.read_bytes() == original
    historical_results[0]["stdout_digest"] = "f" * 64
    checks.write_text(json.dumps(record), encoding="utf-8")
    different_ref = create_artifact_ref(
        "audit_checks", checks.name, tmp_path, "test_execution_record", identity=identity
    )
    # Even a fresh valid SHA/size reference cannot substitute different execution metadata.
    with pytest.raises(OrchestratorError, match="audit_checks verification association mismatch"):
        build_evidence_bundle(
            worktree=repo,
            task_id="T088",
            base_sha=base_sha,
            branch=branch,
            allowed_paths=[],
            verification_collection=collection,
            artifacts_dir=tmp_path,
            artifact_refs=[different_ref],
        )


def test_evidence_bundle_rejects_reordered_results_and_request_declaration_substitution(
    tmp_path: Path,
) -> None:
    from dataclasses import replace

    from tools.orchestrator.core import VerificationRequest

    collection = sample_verification_collection()
    with pytest.raises((ValidationError, OrchestratorError), match="index order"):
        collect_verification_evidence(
            replace(collection, results=tuple(reversed(collection.results)))
        )
    substituted = (COMMANDS[1], COMMANDS[0])
    with pytest.raises(OrchestratorError, match="request command declaration mismatch"):
        VerificationRequest(tmp_path, substituted, None, collection.identity)


def test_evidence_bundle_revalidates_required_manifest_on_validation(tmp_path: Path) -> None:
    repo, base_sha, branch = make_git_repo(tmp_path)
    bundle = build_evidence_bundle(
        worktree=repo,
        task_id="T088",
        base_sha=base_sha,
        branch=branch,
        allowed_paths=[],
        verification_collection=sample_verification_collection(
            identity=frozen_identity(repo, base_sha, branch)
        ),
        artifacts_dir=tmp_path,
    )
    bundle.verification.commands.pop()
    with pytest.raises((ValidationError, OrchestratorError), match="Successful prefix"):
        validate_evidence_bundle(bundle, tmp_path)

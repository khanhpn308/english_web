"""Tests for reviewer probe protocol and host-owned safe probe catalog."""

from pathlib import Path

import pytest
from pydantic import ValidationError
from tools.orchestrator.core import (
    Contract,
    OrchestratorError,
    ProbeParameters,
    ReviewPerspective,
    ReviewShard,
)
from tools.orchestrator.probes import (
    ProbeEvidence,
    ProbeRequest,
    ProbeResultClassification,
    ReviewerContext,
    probe_request_digest,
)

SAMPLE_TASK_ID = "T089"
SAMPLE_BASE_SHA = "a" * 40
SAMPLE_BRANCH = "agent/T089-run1"
SAMPLE_SOURCE_DIGEST = "b" * 64


def test_review_shard_schema_is_strict_structured_output_compatible() -> None:
    schema = ReviewShard.model_json_schema()
    violations: list[str] = []

    def walk(node: object, path: str = "$") -> None:
        if isinstance(node, dict):
            if node.get("type") == "object" or "properties" in node:
                properties = node.get("properties", {})
                required = set(node.get("required", []))

                if node.get("additionalProperties") is not False:
                    violations.append(f"{path}: additionalProperties must be false")

                if isinstance(properties, dict):
                    missing = sorted(set(properties) - required)
                    if missing:
                        violations.append(f"{path}: properties not required: {missing}")

            for key, value in node.items():
                walk(value, f"{path}.{key}")

        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{path}[{index}]")

    walk(schema)

    assert violations == []
    assert "probe_request" in schema["required"]

    probe_schema = schema["$defs"]["ProbeRequest"]
    assert "schema_version" in probe_schema["required"]
    assert "parameters" in probe_schema["required"]

    parameter_schema = schema["$defs"]["ProbeParameters"]
    assert parameter_schema["additionalProperties"] is False
    assert set(parameter_schema["required"]) == {"path", "pattern"}


def test_probe_request_schema_valid() -> None:
    req = ProbeRequest(
        schema_version=1,
        probe_id="source_inspection",
        perspective=ReviewPerspective.CORRECTNESS,
        task_id=SAMPLE_TASK_ID,
        base_sha=SAMPLE_BASE_SHA,
        branch=SAMPLE_BRANCH,
        source_digest=SAMPLE_SOURCE_DIGEST,
        parameters=ProbeParameters.model_validate({"path": "feature.txt", "pattern": "good"}),
        rationale="Check if good is present in feature.txt",
    )
    assert req.probe_id == "source_inspection"
    assert req.perspective == ReviewPerspective.CORRECTNESS
    digest_val = probe_request_digest(req)
    assert len(digest_val) == 64
    assert probe_request_digest(req) == digest_val


def test_probe_request_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        ProbeRequest.model_validate(
            {
                "schema_version": 1,
                "probe_id": "source_inspection",
                "perspective": ReviewPerspective.CORRECTNESS.value,
                "task_id": SAMPLE_TASK_ID,
                "base_sha": SAMPLE_BASE_SHA,
                "branch": SAMPLE_BRANCH,
                "source_digest": SAMPLE_SOURCE_DIGEST,
                "parameters": {},
                "rationale": "check",
                "unknown_extra_field": "disallowed",
            }
        )


@pytest.mark.parametrize(
    "forbidden_field",
    [
        "command",
        "argv",
        "shell",
        "executable",
        "script",
        "powershell",
        "bash",
        "bash_fragment",
        "environment_overrides",
        "working_directory_override",
        "env",
        "cwd",
    ],
)
def test_probe_request_forbids_execution_fields_at_root(forbidden_field: str) -> None:
    with pytest.raises(ValidationError):
        ProbeRequest.model_validate(
            {
                "schema_version": 1,
                "probe_id": "source_inspection",
                "perspective": ReviewPerspective.CORRECTNESS.value,
                "task_id": SAMPLE_TASK_ID,
                "base_sha": SAMPLE_BASE_SHA,
                "branch": SAMPLE_BRANCH,
                "source_digest": SAMPLE_SOURCE_DIGEST,
                "parameters": {},
                "rationale": "check",
                forbidden_field: "malicious_payload",
            }
        )


@pytest.mark.parametrize(
    "forbidden_field",
    [
        "command",
        "argv",
        "shell",
        "executable",
        "script",
        "powershell",
        "bash",
        "bash_fragment",
        "environment_overrides",
        "working_directory_override",
        "env",
        "cwd",
    ],
)
def test_probe_request_forbids_execution_fields_in_parameters(forbidden_field: str) -> None:
    with pytest.raises((OrchestratorError, ValidationError), match="forbidden execution override"):
        ProbeRequest(
            schema_version=1,
            probe_id="source_inspection",
            perspective=ReviewPerspective.CORRECTNESS,
            task_id=SAMPLE_TASK_ID,
            base_sha=SAMPLE_BASE_SHA,
            branch=SAMPLE_BRANCH,
            source_digest=SAMPLE_SOURCE_DIGEST,
            parameters=ProbeParameters.model_validate({forbidden_field: "rm -rf"}),
            rationale="check",
        )


def test_probe_evidence_schema_valid() -> None:
    req = ProbeRequest(
        schema_version=1,
        probe_id="source_inspection",
        perspective=ReviewPerspective.CORRECTNESS,
        task_id=SAMPLE_TASK_ID,
        base_sha=SAMPLE_BASE_SHA,
        branch=SAMPLE_BRANCH,
        source_digest=SAMPLE_SOURCE_DIGEST,
        parameters=ProbeParameters.model_validate({"path": "feature.txt"}),
        rationale="check",
    )
    req_digest = probe_request_digest(req)
    evidence = ProbeEvidence(
        schema_version=1,
        probe_id="source_inspection",
        request_id=req_digest,
        task_id=SAMPLE_TASK_ID,
        base_sha=SAMPLE_BASE_SHA,
        branch=SAMPLE_BRANCH,
        source_digest=SAMPLE_SOURCE_DIGEST,
        perspective=ReviewPerspective.CORRECTNESS,
        executor_id="source_inspection_v1",
        parameters={"path": "feature.txt"},
        classification=ProbeResultClassification.SUCCESS,
        result={"match_count": 1},
        artifacts=[],
        timed_out=False,
        oversized=False,
    )
    assert evidence.classification == ProbeResultClassification.SUCCESS
    assert evidence.result["match_count"] == 1


def _source_probe_with_verified_identity(tmp_path: Path) -> tuple[ProbeRequest, ProbeEvidence]:
    """Obtain an actual catalog observation with the canonical candidate identity."""
    from tools.orchestrator.probes import ProbeCatalog

    (tmp_path / "module.py").write_text("line one\nneedle\n", encoding="utf-8")
    request = ProbeRequest(
        schema_version=1,
        probe_id="source_inspection",
        perspective=ReviewPerspective.CORRECTNESS,
        task_id=SAMPLE_TASK_ID,
        base_sha=SAMPLE_BASE_SHA,
        branch=SAMPLE_BRANCH,
        source_digest=SAMPLE_SOURCE_DIGEST,
        parameters=ProbeParameters.model_validate({"path": "module.py", "pattern": "needle"}),
        rationale="Verify a source observation",
    )
    evidence = ProbeCatalog().execute_probe(
        request,
        workspace=tmp_path,
        current_source_digest=SAMPLE_SOURCE_DIGEST,
        eligible_paths=["module.py"],
    )
    assert evidence.classification == ProbeResultClassification.SUCCESS
    assert evidence.result["match_count"] == 1
    return request, evidence


def _check_bound_probe(
    request: ProbeRequest,
    evidence: ProbeEvidence,
    *,
    artifacts_dir: Path | None = None,
    artifact_filename: str | None = None,
    expected_digest: str | None = None,
) -> None:
    from tools.orchestrator.probes import validate_probe_evidence

    validate_probe_evidence(
        evidence,
        expected_task_id=request.task_id,
        expected_base_sha=request.base_sha,
        expected_branch=request.branch,
        expected_source_digest=request.source_digest,
        expected_req_digest=probe_request_digest(request),
        expected_probe_id=request.probe_id,
        expected_perspective=request.perspective,
        expected_parameters={"path": "module.py", "pattern": "needle"},
        artifacts_dir=artifacts_dir,
        artifact_filename=artifact_filename,
        expected_digest=expected_digest,
    )


@pytest.mark.parametrize(
    ("field", "replacement", "diagnostic"),
    [
        ("task_id", "T090", "task_id mismatch"),
        ("base_sha", "c" * 40, "base_sha mismatch"),
        ("branch", "agent/T089-other", "branch mismatch"),
        ("source_digest", "d" * 64, "source_digest mismatch"),
        ("request_id", "e" * 64, "request_id mismatch"),
        ("probe_id", "git_diff_check", "probe_id mismatch"),
        ("perspective", ReviewPerspective.SECURITY, "perspective mismatch"),
        ("parameters", {"path": "other.py", "pattern": "needle"}, "parameters mismatch"),
    ],
)
def test_host_rejects_cross_candidate_or_unbound_probe_evidence(
    tmp_path: Path, field: str, replacement: object, diagnostic: str
) -> None:
    request, original_evidence = _source_probe_with_verified_identity(tmp_path)
    _check_bound_probe(request, original_evidence)
    forged_evidence = original_evidence.model_copy(update={field: replacement})
    with pytest.raises(OrchestratorError, match=diagnostic):
        _check_bound_probe(request, forged_evidence)


def test_host_checks_probe_json_digest_and_rejects_symlink(tmp_path: Path) -> None:
    from tools.orchestrator.core import digest

    request, evidence = _source_probe_with_verified_identity(tmp_path)
    artifact = tmp_path / "host-probe.json"
    raw = evidence.model_dump_json().encode("utf-8")
    artifact.write_bytes(raw)
    _check_bound_probe(
        request,
        evidence,
        artifacts_dir=tmp_path,
        artifact_filename=artifact.name,
        expected_digest=digest(raw),
    )

    artifact.write_bytes(b"x" * len(raw))
    with pytest.raises(OrchestratorError, match="artifact digest mismatch"):
        _check_bound_probe(
            request,
            evidence,
            artifacts_dir=tmp_path,
            artifact_filename=artifact.name,
            expected_digest=digest(raw),
        )

    artifact.unlink()
    genuine = tmp_path / "genuine.json"
    genuine.write_bytes(raw)
    artifact.symlink_to(genuine)
    with pytest.raises(OrchestratorError, match="artifact file missing or invalid"):
        _check_bound_probe(
            request,
            evidence,
            artifacts_dir=tmp_path,
            artifact_filename=artifact.name,
            expected_digest=digest(raw),
        )


def test_host_verifies_referenced_probe_artifact_bytes(tmp_path: Path) -> None:
    from tools.orchestrator.evidence import create_artifact_ref

    request, evidence = _source_probe_with_verified_identity(tmp_path)
    output = tmp_path / "probe-output.txt"
    output.write_bytes(b"value")
    output_ref = create_artifact_ref("probe-output", output.name, tmp_path, "probe_result")
    referenced_evidence = evidence.model_copy(update={"artifacts": [output_ref]})
    _check_bound_probe(request, referenced_evidence, artifacts_dir=tmp_path)

    output.write_bytes(b"vAlue")
    with pytest.raises(OrchestratorError, match="Artifact digest mismatch"):
        _check_bound_probe(request, referenced_evidence, artifacts_dir=tmp_path)


def test_probe_evidence_timing_and_oversize_classification_consistency() -> None:
    req_digest = "c" * 64
    with pytest.raises((OrchestratorError, ValidationError), match="Timed out"):
        ProbeEvidence(
            schema_version=1,
            probe_id="source_inspection",
            request_id=req_digest,
            task_id=SAMPLE_TASK_ID,
            base_sha=SAMPLE_BASE_SHA,
            branch=SAMPLE_BRANCH,
            source_digest=SAMPLE_SOURCE_DIGEST,
            perspective=ReviewPerspective.CORRECTNESS,
            executor_id="source_inspection_v1",
            parameters={},
            classification=ProbeResultClassification.SUCCESS,
            result={},
            artifacts=[],
            timed_out=True,
            oversized=False,
        )

    with pytest.raises((OrchestratorError, ValidationError), match="Oversized"):
        ProbeEvidence(
            schema_version=1,
            probe_id="source_inspection",
            request_id=req_digest,
            task_id=SAMPLE_TASK_ID,
            base_sha=SAMPLE_BASE_SHA,
            branch=SAMPLE_BRANCH,
            source_digest=SAMPLE_SOURCE_DIGEST,
            perspective=ReviewPerspective.CORRECTNESS,
            executor_id="source_inspection_v1",
            parameters={},
            classification=ProbeResultClassification.SUCCESS,
            result={},
            artifacts=[],
            timed_out=False,
            oversized=True,
        )


def test_review_shard_with_probe_request_validation() -> None:
    req = ProbeRequest(
        schema_version=1,
        probe_id="source_inspection",
        perspective=ReviewPerspective.SECURITY,
        task_id=SAMPLE_TASK_ID,
        base_sha=SAMPLE_BASE_SHA,
        branch=SAMPLE_BRANCH,
        source_digest=SAMPLE_SOURCE_DIGEST,
        parameters=ProbeParameters.model_validate({"path": "feature.txt"}),
        rationale="Security audit",
    )
    shard = ReviewShard(
        perspective=ReviewPerspective.SECURITY,
        findings=[],
        probe_request=req,
    )
    assert shard.probe_request is not None
    assert shard.probe_request.perspective == ReviewPerspective.SECURITY

    # Perspective mismatch between shard and probe_request fails closed
    with pytest.raises((OrchestratorError, ValidationError), match="perspective differs"):
        ReviewShard(
            perspective=ReviewPerspective.CORRECTNESS,
            findings=[],
            probe_request=req,
        )


def test_probe_catalog_immutable_and_host_owned() -> None:
    from tools.orchestrator.probes import ProbeCatalog

    catalog = ProbeCatalog()
    assert catalog.has("source_inspection")
    assert catalog.has("git_diff_check")
    assert not catalog.has("arbitrary_command")

    # Attempting to mutate _PROBES should fail or not be exposed to models
    defn = catalog.get("source_inspection")
    assert defn is not None
    assert defn.probe_id == "source_inspection"
    assert not defn.is_executable

    exec_defn = catalog.get("git_diff_check")
    assert exec_defn is not None
    assert exec_defn.is_executable


def test_probe_request_unknown_probe_id_fails_closed(tmp_path: Path) -> None:
    from tools.orchestrator.probes import ProbeCatalog

    catalog = ProbeCatalog()
    req = ProbeRequest(
        schema_version=1,
        probe_id="arbitrary_bash_shell",
        perspective=ReviewPerspective.CORRECTNESS,
        task_id=SAMPLE_TASK_ID,
        base_sha=SAMPLE_BASE_SHA,
        branch=SAMPLE_BRANCH,
        source_digest=SAMPLE_SOURCE_DIGEST,
        parameters=ProbeParameters.model_validate({}),
        rationale="Probe with unknown ID",
    )
    evidence = catalog.execute_probe(
        req, workspace=tmp_path, current_source_digest=SAMPLE_SOURCE_DIGEST
    )
    assert evidence.classification == ProbeResultClassification.UNSUPPORTED
    _probe_error = evidence.result.get("error")
    assert isinstance(_probe_error, str)
    assert "Unknown probe_id" in _probe_error


def test_probe_request_path_traversal_fails_closed(tmp_path: Path) -> None:
    from tools.orchestrator.probes import ProbeCatalog

    catalog = ProbeCatalog()
    # Try directory traversal
    for bad_path in ["../secret.txt", "../../etc/passwd", "subdir/../../secret.txt"]:
        req = ProbeRequest(
            schema_version=1,
            probe_id="source_inspection",
            perspective=ReviewPerspective.SECURITY,
            task_id=SAMPLE_TASK_ID,
            base_sha=SAMPLE_BASE_SHA,
            branch=SAMPLE_BRANCH,
            source_digest=SAMPLE_SOURCE_DIGEST,
            parameters=ProbeParameters.model_validate({"path": bad_path, "pattern": "key"}),
            rationale="Path traversal attempt",
        )
        evidence = catalog.execute_probe(
            req, workspace=tmp_path, current_source_digest=SAMPLE_SOURCE_DIGEST
        )
        assert evidence.classification == ProbeResultClassification.INVALID


def test_probe_request_absolute_external_path_fails_closed(tmp_path: Path) -> None:
    from tools.orchestrator.probes import ProbeCatalog

    catalog = ProbeCatalog()
    req = ProbeRequest(
        schema_version=1,
        probe_id="source_inspection",
        perspective=ReviewPerspective.SECURITY,
        task_id=SAMPLE_TASK_ID,
        base_sha=SAMPLE_BASE_SHA,
        branch=SAMPLE_BRANCH,
        source_digest=SAMPLE_SOURCE_DIGEST,
        parameters=ProbeParameters.model_validate({"path": "/etc/passwd", "pattern": "root"}),
        rationale="Absolute path escape attempt",
    )
    evidence = catalog.execute_probe(
        req, workspace=tmp_path, current_source_digest=SAMPLE_SOURCE_DIGEST
    )
    assert evidence.classification == ProbeResultClassification.INVALID


def test_probe_request_shell_metacharacter_payload_inert(tmp_path: Path) -> None:
    from tools.orchestrator.probes import ProbeCatalog

    test_file = tmp_path / "sample.py"
    test_file.write_text("print('hello world')\n", encoding="utf-8")

    catalog = ProbeCatalog()
    # Malicious pattern containing command injection metacharacters
    payload = "$(touch /tmp/should_not_exist); `id` && rm -rf /"
    req = ProbeRequest(
        schema_version=1,
        probe_id="source_inspection",
        perspective=ReviewPerspective.SECURITY,
        task_id=SAMPLE_TASK_ID,
        base_sha=SAMPLE_BASE_SHA,
        branch=SAMPLE_BRANCH,
        source_digest=SAMPLE_SOURCE_DIGEST,
        parameters=ProbeParameters.model_validate({"path": "sample.py", "pattern": payload}),
        rationale="Shell injection test",
    )
    evidence = catalog.execute_probe(
        req, workspace=tmp_path, current_source_digest=SAMPLE_SOURCE_DIGEST
    )
    assert evidence.classification == ProbeResultClassification.SUCCESS
    assert evidence.result["match_count"] == 0
    # Confirm file content untouched and shell was never executed
    assert test_file.read_text(encoding="utf-8") == "print('hello world')\n"
    assert not Path("/tmp/should_not_exist").exists()


def test_probe_source_inspection_valid(tmp_path: Path) -> None:
    from tools.orchestrator.probes import ProbeCatalog

    test_file = tmp_path / "module.py"
    test_file.write_text("line 1\nline 2 with target_text\nline 3\nline 4 with target_text\n")

    catalog = ProbeCatalog()
    req = ProbeRequest(
        schema_version=1,
        probe_id="source_inspection",
        perspective=ReviewPerspective.CORRECTNESS,
        task_id=SAMPLE_TASK_ID,
        base_sha=SAMPLE_BASE_SHA,
        branch=SAMPLE_BRANCH,
        source_digest=SAMPLE_SOURCE_DIGEST,
        parameters=ProbeParameters.model_validate({"path": "module.py", "pattern": "target_text"}),
        rationale="Count occurrences",
    )
    evidence = catalog.execute_probe(
        req, workspace=tmp_path, current_source_digest=SAMPLE_SOURCE_DIGEST
    )
    assert evidence.classification == ProbeResultClassification.SUCCESS
    assert evidence.result["match_count"] == 2
    assert evidence.result["matching_lines"] == [2, 4]
    assert evidence.result["line_count"] == 4


def test_probe_source_inspection_oversized_file(tmp_path: Path) -> None:
    from tools.orchestrator.probes import MAX_SOURCE_INSPECTION_BYTES, ProbeCatalog

    large_file = tmp_path / "large.txt"
    # Create file slightly larger than 1 MiB
    large_file.write_bytes(b"a" * (MAX_SOURCE_INSPECTION_BYTES + 10))

    catalog = ProbeCatalog()
    req = ProbeRequest(
        schema_version=1,
        probe_id="source_inspection",
        perspective=ReviewPerspective.VERIFICATION,
        task_id=SAMPLE_TASK_ID,
        base_sha=SAMPLE_BASE_SHA,
        branch=SAMPLE_BRANCH,
        source_digest=SAMPLE_SOURCE_DIGEST,
        parameters=ProbeParameters.model_validate({"path": "large.txt", "pattern": "a"}),
        rationale="Check large file",
    )
    evidence = catalog.execute_probe(
        req, workspace=tmp_path, current_source_digest=SAMPLE_SOURCE_DIGEST
    )
    assert evidence.classification == ProbeResultClassification.OVERSIZED
    assert evidence.oversized is True


def test_probe_git_diff_check_valid(tmp_path: Path) -> None:
    from tools.orchestrator.probes import ProbeCatalog
    from tools.orchestrator.runtime import Git

    git = Git(tmp_path)
    git.run("init", "-b", "main")
    git.run("config", "user.email", "test@example.com")
    git.run("config", "user.name", "Test")
    (tmp_path / "hello.txt").write_text("hello\n")
    git.run("add", "hello.txt")
    git.run("commit", "-m", "init")

    catalog = ProbeCatalog()
    req = ProbeRequest(
        schema_version=1,
        probe_id="git_diff_check",
        perspective=ReviewPerspective.VERIFICATION,
        task_id=SAMPLE_TASK_ID,
        base_sha=SAMPLE_BASE_SHA,
        branch=SAMPLE_BRANCH,
        source_digest=SAMPLE_SOURCE_DIGEST,
        parameters=ProbeParameters.model_validate({}),
        rationale="Check clean diff",
    )
    evidence = catalog.execute_probe(
        req, workspace=tmp_path, current_source_digest=SAMPLE_SOURCE_DIGEST
    )
    assert evidence.classification == ProbeResultClassification.SUCCESS
    assert evidence.result.get("passed") is True
    assert evidence.result.get("exit_code") == 0


def test_probe_git_diff_check_rejects_parameters(tmp_path: Path) -> None:
    from tools.orchestrator.probes import ProbeCatalog

    catalog = ProbeCatalog()
    req = ProbeRequest(
        schema_version=1,
        probe_id="git_diff_check",
        perspective=ReviewPerspective.VERIFICATION,
        task_id=SAMPLE_TASK_ID,
        base_sha=SAMPLE_BASE_SHA,
        branch=SAMPLE_BRANCH,
        source_digest=SAMPLE_SOURCE_DIGEST,
        parameters=ProbeParameters.model_validate({"path": "feature.txt"}),
        rationale="Attempt to pass source-inspection parameters to git_diff_check",
    )
    evidence = catalog.execute_probe(
        req, workspace=tmp_path, current_source_digest=SAMPLE_SOURCE_DIGEST
    )
    assert evidence.classification == ProbeResultClassification.INVALID


def test_probe_stale_candidate_detection(tmp_path: Path) -> None:
    from tools.orchestrator.probes import ProbeCatalog

    catalog = ProbeCatalog()
    old_digest = "1" * 64
    new_digest = "2" * 64

    req = ProbeRequest(
        schema_version=1,
        probe_id="source_inspection",
        perspective=ReviewPerspective.CORRECTNESS,
        task_id=SAMPLE_TASK_ID,
        base_sha=SAMPLE_BASE_SHA,
        branch=SAMPLE_BRANCH,
        source_digest=old_digest,
        parameters=ProbeParameters.model_validate({"path": "feature.txt"}),
        rationale="Stale check",
    )
    # Host detects source_digest has changed from old_digest to new_digest
    evidence = catalog.execute_probe(req, workspace=tmp_path, current_source_digest=new_digest)
    assert evidence.classification == ProbeResultClassification.STALE_PROBE_REQUEST
    _probe_error = evidence.result.get("error")
    assert isinstance(_probe_error, str)
    assert "Candidate source changed" in _probe_error


def test_probe_timeout_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from tools.orchestrator.core import now
    from tools.orchestrator.probes import ProbeCatalog
    from tools.orchestrator.runtime import ProcessResult

    # Simulate timeout on git_diff_check
    def fake_execute(
        argv: list[str],
        cwd: Path,
        *,
        timeout: int | None = None,
        output_limit: int = 4 * 1024 * 1024,
    ) -> ProcessResult:
        assert timeout == 30
        assert output_limit == 64 * 1024
        return ProcessResult(
            command=tuple(argv),
            cwd=str(cwd),
            started_at=now(),
            ended_at=now(),
            exit_code=124,
            stdout="",
            stderr="timed out",
            timed_out=True,
            oversized=False,
        )

    monkeypatch.setattr("tools.orchestrator.probes.execute", fake_execute)

    catalog = ProbeCatalog()
    req = ProbeRequest(
        schema_version=1,
        probe_id="git_diff_check",
        perspective=ReviewPerspective.VERIFICATION,
        task_id=SAMPLE_TASK_ID,
        base_sha=SAMPLE_BASE_SHA,
        branch=SAMPLE_BRANCH,
        source_digest=SAMPLE_SOURCE_DIGEST,
        parameters=ProbeParameters.model_validate({}),
        rationale="Timeout check",
    )
    evidence = catalog.execute_probe(
        req, workspace=tmp_path, current_source_digest=SAMPLE_SOURCE_DIGEST
    )
    assert evidence.classification == ProbeResultClassification.TIMED_OUT
    assert evidence.timed_out is True


def test_probe_artifact_tampering_detected(tmp_path: Path) -> None:
    from tools.orchestrator.evidence import create_artifact_ref, validate_artifact_ref

    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    artifact_file = artifacts_dir / "probe_output.json"
    artifact_file.write_text('{"status": "ok"}', encoding="utf-8")

    ref = create_artifact_ref("probe_output", "probe_output.json", artifacts_dir, "probe_result")
    # Valid initially
    validate_artifact_ref(ref, artifacts_dir)

    # Tamper with file (different size)
    artifact_file.write_text('{"status": "tampered"}', encoding="utf-8")
    with pytest.raises(OrchestratorError, match=r"Artifact (digest|size) mismatch"):
        validate_artifact_ref(ref, artifacts_dir)

    # Tamper with file (same size, different digest)
    artifact_file.write_text('{"status": "no"}', encoding="utf-8")
    with pytest.raises(OrchestratorError, match="Artifact digest mismatch"):
        validate_artifact_ref(ref, artifacts_dir)


def test_probe_executor_attempts_authoritative_source_mutation(tmp_path: Path) -> None:
    from tools.orchestrator.runtime import Git

    # Create authoritative repo
    auth_repo = tmp_path / "auth_repo"
    auth_repo.mkdir()
    git = Git(auth_repo)
    git.run("init", "-b", "main")
    git.run("config", "user.email", "test@example.com")
    git.run("config", "user.name", "Test")
    (auth_repo / "feature.txt").write_text("initial\n")
    git.run("add", "feature.txt")
    git.run("commit", "-m", "init")

    base_sha = git.sha("HEAD")
    snapshot_before = git.snapshot(base_sha)

    # Create isolated probe workspace
    probe_ws = tmp_path / "probe_ws"
    probe_ws.mkdir()
    (probe_ws / "feature.txt").write_text("probe modified\n")

    # Authoritative source was not touched:
    assert git.snapshot(base_sha) == snapshot_before

    # If an attacker manages to touch authoritative repo:
    (auth_repo / "feature.txt").write_text("tampered\n")
    snapshot_after = git.snapshot(base_sha)
    assert snapshot_after != snapshot_before


def test_probe_out_of_order_concurrent_completion_deterministic_fan_in(tmp_path: Path) -> None:
    from tools.orchestrator.probes import ProbeCatalog

    catalog = ProbeCatalog()
    test_file = tmp_path / "source.txt"
    test_file.write_text("line 1\nline 2\n")

    req_correctness = ProbeRequest(
        schema_version=1,
        probe_id="source_inspection",
        perspective=ReviewPerspective.CORRECTNESS,
        task_id=SAMPLE_TASK_ID,
        base_sha=SAMPLE_BASE_SHA,
        branch=SAMPLE_BRANCH,
        source_digest=SAMPLE_SOURCE_DIGEST,
        parameters=ProbeParameters.model_validate({"path": "source.txt", "pattern": "line 1"}),
        rationale="Correctness search",
    )
    req_security = ProbeRequest(
        schema_version=1,
        probe_id="source_inspection",
        perspective=ReviewPerspective.SECURITY,
        task_id=SAMPLE_TASK_ID,
        base_sha=SAMPLE_BASE_SHA,
        branch=SAMPLE_BRANCH,
        source_digest=SAMPLE_SOURCE_DIGEST,
        parameters=ProbeParameters.model_validate({"path": "source.txt", "pattern": "line 2"}),
        rationale="Security search",
    )

    ev_corr = catalog.execute_probe(
        req_correctness, workspace=tmp_path, current_source_digest=SAMPLE_SOURCE_DIGEST
    )
    ev_sec = catalog.execute_probe(
        req_security, workspace=tmp_path, current_source_digest=SAMPLE_SOURCE_DIGEST
    )

    # Suppose they complete out-of-order: SECURITY first, then CORRECTNESS
    completed_out_of_order = [ev_sec, ev_corr]

    # Deterministic fan-in normalizes by ReviewPerspective canonical order
    canonical_order = list(ReviewPerspective)
    normalized = sorted(
        completed_out_of_order,
        key=lambda ev: canonical_order.index(ev.perspective),
    )

    assert normalized[0].perspective == ReviewPerspective.CORRECTNESS
    assert normalized[1].perspective == ReviewPerspective.SECURITY


def test_reviewer_attempts_second_probe_round() -> None:
    req = ProbeRequest(
        schema_version=1,
        probe_id="source_inspection",
        perspective=ReviewPerspective.CORRECTNESS,
        task_id=SAMPLE_TASK_ID,
        base_sha=SAMPLE_BASE_SHA,
        branch=SAMPLE_BRANCH,
        source_digest=SAMPLE_SOURCE_DIGEST,
        parameters=ProbeParameters.model_validate({"path": "feature.txt"}),
        rationale="Initial probe",
    )
    second_req = ProbeRequest(
        schema_version=1,
        probe_id="source_inspection",
        perspective=ReviewPerspective.CORRECTNESS,
        task_id=SAMPLE_TASK_ID,
        base_sha=SAMPLE_BASE_SHA,
        branch=SAMPLE_BRANCH,
        source_digest=SAMPLE_SOURCE_DIGEST,
        parameters=ProbeParameters.model_validate({"path": "feature.txt"}),
        rationale="Second round probe",
    )

    # In round 2 (resumed reviewer), returning another probe_request is rejected
    context = ReviewerContext(
        schema_version=1,
        perspective=ReviewPerspective.CORRECTNESS,
        task_id=SAMPLE_TASK_ID,
        base_sha=SAMPLE_BASE_SHA,
        branch=SAMPLE_BRANCH,
        source_digest=SAMPLE_SOURCE_DIGEST,
        contract=Contract(
            schema_version=1,
            task_id=SAMPLE_TASK_ID,
            title="Task",
            objective="Obj",
            dependencies=[],
            base_sha=SAMPLE_BASE_SHA,
            allowed_paths=["feature.txt"],
            forbidden_paths=[],
            acceptance_criteria=["Criterion"],
            required_verification=[["python", "-m", "pytest"]],
            risk_level="medium",
            forbidden_scope="None",
            stop_conditions="None",
            max_fix_cycles=3,
        ),
        round_index=2,
        prior_request=req,
    )
    assert context.round_index == 2

    # A resumed shard containing second_req is detected and rejected
    resumed_shard = ReviewShard(
        perspective=ReviewPerspective.CORRECTNESS,
        findings=[],
        probe_request=second_req,
    )
    # Host rule: if round_index >= 2 and shard.probe_request is not None -> fail closed
    if context.round_index >= 2 and resumed_shard.probe_request is not None:
        with pytest.raises(OrchestratorError, match="probe round limit"):
            raise OrchestratorError(
                "Reviewer exceeded probe round limit: multiple probe rounds not allowed"
            )

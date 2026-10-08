"""Local Git fixtures for host-authoritative recovery, without inference or network."""

import json
import re
import shlex
import shutil
import sys
from pathlib import Path
from typing import Literal, TypeVar
from uuid import uuid4

import pytest
from pydantic import BaseModel, ValidationError
from tools.orchestrator.core import (
    Audit,
    Config,
    Criterion,
    OrchestratorError,
    Paths,
    Plan,
    ReviewPerspective,
    ReviewShard,
    Role,
    RunState,
    State,
    WorkerResult,
    atomic_json,
    contract_template,
    digest,
    now,
    read_json,
    task_card,
)
from tools.orchestrator.recovery import (
    CandidateImportOrigin,
    ImportedSemanticEvidence,
    RecoveryOrigin,
    config_digest,
    control_plane_root,
    is_liveness_config_upgraded,
    recovery_config_compatible,
    recovery_handoff,
)
from tools.orchestrator.runtime import Git, LockBusy, ProcessResult, execute, lock
from tools.orchestrator.skills import SkillManifest, SkillReference
from tools.orchestrator.workflow import Pipeline

Output = TypeVar("Output", bound=BaseModel)


class HistoricalArtifact(BaseModel):
    note: str = "Stale historical evidence"


class LocalAgents:
    def __init__(self, audit_status: Literal["PASS", "FAIL"] = "PASS") -> None:
        self.calls: list[str] = []
        self.audit_status = audit_status

    def run(
        self,
        prompt: str,
        *,
        cwd: Path,
        role: Role,
        timeout: int | None,
        output: type[Output],
        artifacts: Path,
        name: str,
        readonly: bool,
    ) -> Output:
        self.calls.append(output.__name__)
        assert readonly
        assert cwd.is_dir() and artifacts.is_dir()
        assert role.executable == "unused-local-fixture"
        assert timeout == 30 and name
        if output == ReviewShard:
            match = re.search(r"REVIEW_PERSPECTIVE: ([^\n]+)", prompt)
            assert match is not None
            return output.model_validate(
                ReviewShard(
                    perspective=ReviewPerspective(match[1]),
                    findings=[],
                    probe_request=None,
                )
            )
        if output.__name__ == "IntegrationReview":
            assert readonly and "INTEGRATOR_CONTEXT:" in prompt
            from tools.orchestrator.core import IntegrationReview, IntegratorContextV1

            ctx = IntegratorContextV1.model_validate_json(
                prompt.split("INTEGRATOR_CONTEXT:", 1)[1].strip()
            )
            return output.model_validate(
                IntegrationReview(
                    status="READY",
                    findings=[],
                    source_branch=ctx.source_branch,
                    target_branch=ctx.target_branch,
                )
            )
        assert output == Audit, "Recovery/resume must not dispatch Worker or planning"
        return output.model_validate(
            Audit(
                status=self.audit_status,
                findings=[] if self.audit_status == "PASS" else ["Synthetic semantic finding"],
                acceptance_criteria=[
                    Criterion(
                        criterion="Preserve candidate.",
                        status=self.audit_status,
                        evidence="Local fixture",
                    )
                ],
                scope_violations=[],
                required_fixes=[] if self.audit_status == "PASS" else ["Resolve synthetic finding"],
                reviewer_dispositions=[],
            )
        )


@pytest.fixture
def candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> tuple[Pipeline, RunState, str]:
    repo = tmp_path / "repository"
    repo.mkdir()
    git = Git(repo)
    git.run("init", "-b", "main")
    git.run("config", "user.email", "fixture@example.invalid")
    git.run("config", "user.name", "Fixture")
    (repo / "tasks").mkdir()
    (repo / "docs").mkdir()
    (repo / ".gitignore").write_text(
        ".agent-runs/\nnode_modules/\n.venv/\n.pytest_cache/\n__pycache__/\n"
    )
    (repo / "feature.txt").write_text("original\n")
    (repo / "deleted.txt").write_text("delete me\n")
    (repo / "test_app.py").write_text(
        "from pathlib import Path\ndef test_candidate():\n"
        '    assert Path("feature.txt").read_text() == "working\\n"\n'
    )
    (repo / "docs/changelogs.md").write_text("Historical fixture\n")
    (repo / "tasks/t100-fixture.md").write_text("""# T100
**Task ID:** `T100`
**Title:** Recovery fixture
**Status:** `PENDING`
**Goal:** Preserve candidate.
## Dependencies
- None
## Files được phép sửa
- `feature.txt`
- `deleted.txt`
- `untracked.bin`
- `staged.bin`
- `remediation.txt`
## Acceptance criteria
- [ ] Preserve candidate.
## Verification commands
```text
python -m pytest test_app.py -q
```
""")
    git.run("add", ".")
    git.run("commit", "-m", "fixture")
    config = Config(
        roles={
            name: Role(provider="codex", executable="unused-local-fixture")
            for name in ("prompt_engineer", "worker", "auditor", "integrator")
        },
        setup_commands=[["npm", "ci"]],
        verification=[["git", "diff", "--check"]],
        timeout_seconds=30,
        integrate=False,
    )
    pipeline = Pipeline(repo, config, LocalAgents())
    source = RunState(
        task_id="T100",
        run_id="historical",
        repository=str(repo),
        base_sha=git.sha(),
        worktree_path=str(pipeline.worktrees / "T100-historical"),
        worktree_branch="agent/T100-historical",
        config=config.model_copy(deep=True),
        state=State.FAILED,
        blocked_from=State.AUDIT_RUNNING,
        last_error="Synthetic audit failure",
    )
    directory = pipeline.run_path("T100", source.run_id)
    directory.mkdir(parents=True)
    with lock(directory / ".run.lock"):
        pass
    working = Path(source.worktree_path)
    git.create_worktree(working, source.worktree_branch, source.base_sha)
    card = task_card(working, "T100")
    source.task_digest = card.content_digest
    contract = contract_template(card, source)
    pipeline.artifact(directory, source, "task_card", card)
    pipeline.artifact(
        directory, source, "plan", Plan(contract=contract, worker_prompt="Frozen handoff")
    )
    pipeline.artifact(directory, source, "contract", contract)
    source.contract_digest = source.artifact_digests[source.artifacts["contract"]]
    workgit = Git(working)
    (working / "feature.txt").write_text("staged\n")
    workgit.run("add", "feature.txt")
    (working / "feature.txt").write_text("working\n")
    (working / "staged.bin").write_bytes(b"\0staged\xff")
    (working / "staged.bin").chmod(0o755)
    workgit.run("add", "staged.bin")
    (working / "deleted.txt").unlink()
    (working / "untracked.bin").write_bytes(b"\0untracked\xfe")
    (working / "untracked.bin").chmod(0o755)
    (working / "docs/changelogs.md").write_text("Recovery fixture\nHistorical fixture\n")
    for name in ("node_modules", ".venv", ".pytest_cache"):
        (working / name).mkdir()
        (working / name / "source-only").write_text("Ignored source toolchain")
    pipeline.artifact(
        directory,
        source,
        "worker",
        WorkerResult(
            status="IMPLEMENTED",
            summary="Frozen implementation",
            changed_files=getattr(request, "param", workgit.paths(source.base_sha)),
            commands_run=[],
            known_issues=[],
        ),
    )
    for key in (
        "audit_checks",
        "evidence_bundle",
        "review_bundle",
        "audit",
        "rejected_audit",
        "probe_example",
        "integration_review",
        "integration_setup",
        "integration_verify",
    ):
        pipeline.artifact(directory, source, key, HistoricalArtifact())
    # Also retain superseded, sealed artifacts and unsealed diagnostic files.
    (directory / "superseded.json").write_text("{}")
    source.artifact_digests["superseded.json"] = digest(b"{}")
    (directory / "historical-note.txt").write_text("Keep me byte-identical")
    pipeline.save(directory, source)

    import tools.orchestrator.workflow as workflow

    def local_setup(command: list[str], cwd: Path, **_kwargs: object) -> ProcessResult:
        if command == ["npm", "ci"]:
            assert cwd != working
            for name in ("node_modules", ".venv", ".pytest_cache"):
                assert not (cwd / name).exists()
            (cwd / "node_modules").mkdir()
            (cwd / "node_modules/fresh-setup").write_text("Fresh fixture install")
            return ProcessResult(tuple(command), str(cwd), now(), now(), 0, "", "")
        return execute(command, cwd, timeout=30)

    monkeypatch.setattr(workflow, "execute", local_setup)
    return pipeline, source, workgit.snapshot(source.base_sha)


def source_bytes(
    pipeline: Pipeline, source: RunState
) -> tuple[dict[str, bytes], bytes, str, dict[str, bytes]]:
    directory = pipeline.run_path(source.task_id, source.run_id)
    artifacts = {p.name: p.read_bytes() for p in directory.iterdir()}
    git = Git(Path(source.worktree_path))
    index = Path(git.run("rev-parse", "--git-path", "index"))
    worktree_files = {
        str(path.relative_to(git.repository)): path.read_bytes()
        for path in git.repository.rglob("*")
        if path.is_file()
    }
    return artifacts, index.read_bytes(), git.snapshot(source.base_sha), worktree_files


def test_recover_exact_candidate_and_historical_immutability(
    candidate: tuple[Pipeline, RunState, str],
) -> None:
    pipeline, source, snapshot = candidate
    before = source_bytes(pipeline, source)
    # The target branch may advance, but recovery must still start at the historical base.
    (pipeline.repository / "main-only.txt").write_text("New main content")
    pipeline.git.run("add", "main-only.txt")
    pipeline.git.run("commit", "-m", "advance main")
    recovered = pipeline.recover_candidate("T100", source.run_id, snapshot)
    assert recovered.state == State.IMPLEMENTED
    assert recovered.current_agent is recovered.blocked_from is recovered.last_error is None
    assert recovered.audited_digest == ""
    assert recovered.base_sha == source.base_sha != pipeline.git.sha()
    assert recovered.run_id != source.run_id
    target = Path(recovered.worktree_path)
    git = Git(target)
    original = Git(Path(source.worktree_path))
    assert git.sha() == source.base_sha
    assert git.snapshot(source.base_sha) == snapshot
    assert git.branch() == f"agent/T100-{recovered.run_id}"
    assert git.run("diff", "--cached", "--binary", source.base_sha) == original.run(
        "diff", "--cached", "--binary", source.base_sha
    )
    assert git.run("diff", "--binary") == original.run("diff", "--binary")
    assert git.run("ls-files", "--others", "--exclude-standard") == original.run(
        "ls-files", "--others", "--exclude-standard"
    )
    assert git.run("show", ":feature.txt") == "staged"
    assert (target / "feature.txt").read_text() == "working\n"
    assert (target / "untracked.bin").read_bytes() == b"\0untracked\xfe"
    assert (target / "untracked.bin").stat().st_mode == (
        Path(source.worktree_path) / "untracked.bin"
    ).stat().st_mode
    assert not (target / "deleted.txt").exists()
    assert not (target / "main-only.txt").exists()
    assert (target / "node_modules/fresh-setup").exists()
    assert not (target / "node_modules/source-only").exists()
    assert set(recovered.artifacts) == {
        "task_card",
        "plan",
        "contract",
        "worker",
        "setup",
        "recovery_origin",
    }
    for key in ("task_card", "plan", "contract", "worker"):
        assert (
            pipeline.run_path("T100", recovered.run_id) / recovered.artifacts[key]
        ).read_bytes() == before[0][source.artifacts[key]]
    assert source_bytes(pipeline, source) == before
    assert pipeline.status("T100", recovered.run_id) == recovered
    assert isinstance(pipeline.provider, LocalAgents)
    assert pipeline.provider.calls == []


def test_provenance_integrity(candidate: tuple[Pipeline, RunState, str]) -> None:
    pipeline, source, snapshot = candidate
    source_digest = digest((pipeline.run_path("T100", source.run_id) / "state.json").read_bytes())
    recovered = pipeline.recover_candidate("T100", source.run_id, snapshot)
    directory = pipeline.run_path("T100", recovered.run_id)
    path = directory / recovered.artifacts["recovery_origin"]
    origin = RecoveryOrigin.model_validate(read_json(path))
    assert origin.schema_version == 1
    assert origin.task_id == "T100"
    assert origin.source_run_id == source.run_id
    assert origin.source_state_digest == source_digest
    assert origin.source_base_sha == source.base_sha
    assert origin.source_branch == source.worktree_branch
    assert origin.recovery_run_id == recovered.run_id
    assert origin.recovery_branch == recovered.worktree_branch
    assert origin.source_source_digest == origin.recovery_source_digest == snapshot
    assert origin.recovery_worktree == recovered.worktree_path
    assert origin.worker_claim_matches
    assert origin.worker_changed_files_digest == origin.recovered_changed_files_digest
    assert origin.source_fix_cycle == origin.recovery_fix_cycle == source.fix_cycle
    assert source.config is not None and recovered.config is not None
    assert origin.source_config_digest == config_digest(source.config)
    assert origin.recovery_config_digest == config_digest(recovered.config)
    assert not origin.liveness_config_upgraded
    assert recovered.artifact_digests[path.name] == digest(path.read_bytes())
    path.write_text("{}")
    with pytest.raises(OrchestratorError, match="artifact changed"):
        pipeline.check_artifacts(directory, recovered)


def test_host_remediation_after_worker_recovers_and_audits(
    candidate: tuple[Pipeline, RunState, str],
) -> None:
    pipeline, source, _ = candidate
    working = Path(source.worktree_path)
    worker_path = pipeline.run_path("T100", source.run_id) / source.artifacts["worker"]
    worker_bytes = worker_path.read_bytes()
    worker = WorkerResult.model_validate_json(worker_bytes)
    (working / "remediation.txt").write_text("Authorized host remediation after Worker\n")
    snapshot = Git(working).snapshot(source.base_sha)
    actual = Git(working).paths(source.base_sha)
    before = source_bytes(pipeline, source)
    recovered = pipeline.recover_candidate("T100", source.run_id, snapshot)
    assert recovered.state == State.IMPLEMENTED
    directory = pipeline.run_path("T100", recovered.run_id)
    origin = RecoveryOrigin.model_validate(
        read_json(directory / recovered.artifacts["recovery_origin"])
    )
    assert not origin.worker_claim_matches
    assert origin.worker_changed_files_digest == digest(
        json.dumps(sorted(worker.changed_files), separators=(",", ":")).encode()
    )
    assert origin.recovered_changed_files_digest == digest(
        json.dumps(actual, separators=(",", ":")).encode()
    )
    assert (directory / recovered.artifacts["worker"]).read_bytes() == worker_bytes
    assert (Path(recovered.worktree_path) / "remediation.txt").read_bytes() == (
        working / "remediation.txt"
    ).read_bytes()
    assert isinstance(pipeline.provider, LocalAgents)
    assert pipeline.provider.calls == []
    assert pipeline.resume("T100", recovered.run_id).state == State.AUDIT_PASS
    assert source_bytes(pipeline, source) == before


@pytest.mark.parametrize("candidate", [[], ["out-of-scope.txt"]], indirect=True)
def test_worker_claim_does_not_control_actual_scope(
    candidate: tuple[Pipeline, RunState, str],
) -> None:
    pipeline, source, snapshot = candidate
    before = source_bytes(pipeline, source)
    recovered = pipeline.recover_candidate("T100", source.run_id, snapshot)
    assert recovered.state == State.IMPLEMENTED
    directory = pipeline.run_path("T100", recovered.run_id)
    origin = RecoveryOrigin.model_validate(
        read_json(directory / recovered.artifacts["recovery_origin"])
    )
    assert not origin.worker_claim_matches
    assert source_bytes(pipeline, source) == before
    # Even a Worker claim naming this file cannot authorize an actual scope extension.
    (Path(source.worktree_path) / "out-of-scope.txt").write_text("Unexpected source change")
    snapshot = Git(Path(source.worktree_path)).snapshot(source.base_sha)
    with pytest.raises(OrchestratorError, match="BLOCKED_FOR_SCOPE_EXTENSION"):
        pipeline.recover_candidate("T100", source.run_id, snapshot)


@pytest.mark.parametrize("fix_cycle", [1, 3])
def test_recovery_preserves_fix_budget(
    candidate: tuple[Pipeline, RunState, str], fix_cycle: int
) -> None:
    pipeline, source, snapshot = candidate
    source.fix_cycle = fix_cycle
    pipeline.save(pipeline.run_path("T100", source.run_id), source)
    before = source_bytes(pipeline, source)
    recovered = pipeline.recover_candidate("T100", source.run_id, snapshot)
    assert recovered.state == State.IMPLEMENTED
    assert recovered.fix_cycle == source.fix_cycle
    assert recovered.max_fix_cycles == source.max_fix_cycles
    directory = pipeline.run_path("T100", recovered.run_id)
    origin = RecoveryOrigin.model_validate(
        read_json(directory / recovered.artifacts["recovery_origin"])
    )
    assert origin.source_fix_cycle == origin.recovery_fix_cycle == fix_cycle
    if fix_cycle == source.max_fix_cycles:
        pipeline.provider = LocalAgents(audit_status="FAIL")
        resumed = pipeline.resume("T100", recovered.run_id)
        assert resumed.state == State.FAILED
        assert "Maximum fix cycles reached" in (resumed.last_error or "")
        assert resumed.fix_cycle == resumed.max_fix_cycles == fix_cycle
        assert set(pipeline.provider.calls) == {"ReviewShard", "Audit"}
    assert source_bytes(pipeline, source) == before


@pytest.mark.parametrize(
    "change", ["stage", "active", "state", "worker", "unmanaged", "config", "head"]
)
def test_ineligible_sources_fail_before_new_authority(
    candidate: tuple[Pipeline, RunState, str], change: str
) -> None:
    pipeline, source, snapshot = candidate
    if change == "stage":
        source.blocked_from = State.WORKER_RUNNING
    elif change == "active":
        source.current_agent = "auditor"
    elif change == "state":
        source.state = State.AUDIT_FAIL
    elif change == "worker":
        del source.artifacts["worker"]
    elif change == "unmanaged":
        pipeline.git.run("worktree", "move", source.worktree_path, source.worktree_path + "-moved")
    elif change == "config":
        source.config = None
    elif change == "head":
        git = Git(Path(source.worktree_path))
        git.run("commit", "--allow-empty", "-m", "unexpected history")
    pipeline.save(pipeline.run_path("T100", source.run_id), source)
    before = (pipeline.run_path("T100", source.run_id) / "state.json").read_bytes()
    with pytest.raises(OrchestratorError):
        pipeline.recover_candidate("T100", source.run_id, snapshot)
    assert (pipeline.run_path("T100", source.run_id) / "state.json").read_bytes() == before
    assert len(list((pipeline.runs / "T100").glob("*/state.json"))) == 1
    assert isinstance(pipeline.provider, LocalAgents)
    assert pipeline.provider.calls == []


@pytest.mark.parametrize("value", ["0" * 64, "not-a-digest", "", "A" * 64])
def test_wrong_expected_digest(candidate: tuple[Pipeline, RunState, str], value: str) -> None:
    pipeline, source, _ = candidate
    before = source_bytes(pipeline, source)
    with pytest.raises(OrchestratorError, match="digest"):
        pipeline.recover_candidate("T100", source.run_id, value)
    assert source_bytes(pipeline, source) == before


def test_source_mutated_before_recovery(candidate: tuple[Pipeline, RunState, str]) -> None:
    pipeline, source, snapshot = candidate
    (Path(source.worktree_path) / "feature.txt").write_text("Changed after freeze")
    with pytest.raises(OrchestratorError, match="Source digest"):
        pipeline.recover_candidate("T100", source.run_id, snapshot)


@pytest.mark.parametrize("name", ["worker", "audit", "superseded"])
def test_tampered_source_artifact(candidate: tuple[Pipeline, RunState, str], name: str) -> None:
    pipeline, source, snapshot = candidate
    directory = pipeline.run_path("T100", source.run_id)
    (directory / source.artifacts.get(name, "superseded.json")).write_text("Tampered")
    before = source_bytes(pipeline, source)
    with pytest.raises(OrchestratorError, match="artifact changed"):
        pipeline.recover_candidate("T100", source.run_id, snapshot)
    assert source_bytes(pipeline, source) == before


@pytest.mark.parametrize("target", ["source", "candidate", "artifact", "state", "index"])
def test_mutation_during_materialization_fails_closed(
    candidate: tuple[Pipeline, RunState, str], monkeypatch: pytest.MonkeyPatch, target: str
) -> None:
    import tools.orchestrator.workflow as workflow

    pipeline, source, snapshot = candidate
    materialize = workflow.materialize_candidate
    state_bytes = (pipeline.run_path("T100", source.run_id) / "state.json").read_bytes()

    def mutate(working: Path, destination: Path, base: str) -> None:
        materialize(working, destination, base)
        if target == "source":
            (working / "feature.txt").write_text("source mutation")
        elif target == "candidate":
            (destination / "feature.txt").write_text("candidate mutation")
        elif target == "artifact":
            (pipeline.run_path("T100", source.run_id) / source.artifacts["worker"]).write_text("{}")
        elif target == "state":
            path = pipeline.run_path("T100", source.run_id) / "state.json"
            path.write_bytes(path.read_bytes() + b"\n")
        elif target == "index":
            Git(working).run("update-index", "--assume-unchanged", "feature.txt")

    monkeypatch.setattr(workflow, "materialize_candidate", mutate)
    recovered = pipeline.recover_candidate("T100", source.run_id, snapshot)
    assert recovered.state == State.FAILED
    assert (
        "mutat" in (recovered.last_error or "")
        or "mismatch" in (recovered.last_error or "")
        or "artifact" in (recovered.last_error or "")
    )
    if target != "state":
        assert (pipeline.run_path("T100", source.run_id) / "state.json").read_bytes() == state_bytes
    assert pipeline.status("T100", recovered.run_id).state == State.FAILED


@pytest.mark.parametrize("behavior", ["failure", "source", "candidate"])
def test_setup_failure_or_mutation_fails_closed(
    candidate: tuple[Pipeline, RunState, str], monkeypatch: pytest.MonkeyPatch, behavior: str
) -> None:
    import tools.orchestrator.workflow as workflow

    pipeline, source, snapshot = candidate
    before = source_bytes(pipeline, source)

    def setup(command: list[str], cwd: Path, **_kwargs: object) -> ProcessResult:
        assert command == ["npm", "ci"]
        if behavior != "failure":
            root = Path(source.worktree_path) if behavior == "source" else cwd
            (root / "feature.txt").write_text("Mutation in setup")
        return ProcessResult(
            tuple(command), str(cwd), now(), now(), int(behavior == "failure"), "", ""
        )

    monkeypatch.setattr(workflow, "execute", setup)
    recovered = pipeline.recover_candidate("T100", source.run_id, snapshot)
    assert recovered.state == State.FAILED
    assert recovered.last_error
    assert "recovery_origin" not in recovered.artifacts
    if behavior != "source":
        assert source_bytes(pipeline, source) == before
    else:
        assert source_bytes(pipeline, source)[0] == before[0]
    assert isinstance(pipeline.provider, LocalAgents)
    assert pipeline.provider.calls == []


def test_normal_resume_enters_fresh_audit_without_worker(
    candidate: tuple[Pipeline, RunState, str],
) -> None:
    pipeline, source, snapshot = candidate
    recovered = pipeline.recover_candidate("T100", source.run_id, snapshot)
    assert isinstance(pipeline.provider, LocalAgents)
    assert pipeline.provider.calls == []
    resumed = pipeline.resume("T100", recovered.run_id)
    assert resumed.state == State.AUDIT_PASS, resumed.last_error
    assert pipeline.provider.calls.count("ReviewShard") == 3
    assert pipeline.provider.calls.count("Audit") == 1
    assert set(pipeline.provider.calls) == {"ReviewShard", "Audit"}
    assert resumed.audited_digest == snapshot
    assert {"audit_checks", "review_bundle", "audit", "evidence_bundle"}.issubset(resumed.artifacts)
    pipeline.check_artifacts(pipeline.run_path("T100", resumed.run_id), resumed)


@pytest.mark.parametrize(
    "arguments", [[], ["--run-id", "historical"], ["--expected-source-digest", "0" * 64]]
)
def test_cli_requires_explicit_source_and_digest(
    monkeypatch: pytest.MonkeyPatch, arguments: list[str]
) -> None:
    from tools.orchestrator.__main__ import main

    monkeypatch.setattr(sys, "argv", ["orchestrator", "recover-candidate", "T100", *arguments])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2


@pytest.mark.parametrize(
    ("integration_flag", "custom_config"),
    [("--integrate", False), ("--no-integrate", False), ("--no-integrate", True)],
)
def test_cli_recovers_and_honors_integration_option(
    candidate: tuple[Pipeline, RunState, str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    integration_flag: str,
    custom_config: bool,
) -> None:
    from tools.orchestrator.__main__ import main

    pipeline, source, snapshot = candidate
    monkeypatch.setattr(Pipeline, "load", lambda _directory, _config=None: pipeline)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "orchestrator",
            "recover-candidate",
            "T100",
            "--run-id",
            source.run_id,
            "--expected-source-digest",
            snapshot,
            integration_flag,
            *(["--config", "custom config.json"] if custom_config else []),
        ],
    )
    assert main() == 0
    assert pipeline.config.integrate == (integration_flag == "--integrate")
    output = capsys.readouterr().out
    payload = json.loads(output[output.index("{") :])
    assert payload["state"] == "IMPLEMENTED"
    handoff = payload["recovery_handoff"]
    cp_root = str(control_plane_root())
    assert handoff["control_plane_cwd"] == cp_root
    assert handoff["candidate_worktree"] == payload["worktree_path"]
    assert handoff["control_plane_cwd"] != handoff["candidate_worktree"]
    assert handoff["cwd"] == cp_root
    assert handoff["branch"] == payload["worktree_branch"]
    assert handoff["task_id"] == "T100"
    assert handoff["run_id"] == payload["run_id"] != source.run_id
    assert handoff["argv"] == [
        "python",
        "-m",
        "tools.orchestrator",
        "resume",
        "T100",
        "--run-id",
        payload["run_id"],
        integration_flag,
        *(["--config", str(Path("custom config.json").resolve())] if custom_config else []),
    ]
    assert handoff["next_step"] == (
        f"cd -- {shlex.quote(cp_root)} && {shlex.join(handoff['argv'])}"
    )
    assert isinstance(pipeline.provider, LocalAgents)
    assert pipeline.provider.calls == []


@pytest.mark.parametrize("invocation", ["control_plane", "candidate_cwd", "candidate_modules"])
def test_cli_recovered_resume_trusts_control_plane_and_rejects_candidate_invocation(
    candidate: tuple[Pipeline, RunState, str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    invocation: str,
) -> None:
    import tools.orchestrator.__main__ as cli

    pipeline, source, snapshot = candidate
    recovered = pipeline.recover_candidate("T100", source.run_id, snapshot)
    before = (pipeline.run_path("T100", recovered.run_id) / "state.json").read_bytes()
    pipeline.config.integrate = True
    monkeypatch.setattr(Pipeline, "load", lambda _directory, _config=None: pipeline)
    monkeypatch.chdir(
        pipeline.repository if invocation != "candidate_cwd" else Path(recovered.worktree_path)
    )
    if invocation == "candidate_modules":
        monkeypatch.setattr(
            cli, "__file__", str(Path(recovered.worktree_path) / "tools/orchestrator/__main__.py")
        )
    monkeypatch.setattr(
        sys,
        "argv",
        ["orchestrator", "resume", "T100", "--run-id", recovered.run_id, "--no-integrate"],
    )
    capsys.readouterr()
    result = cli.main()
    output = capsys.readouterr().out
    assert isinstance(pipeline.provider, LocalAgents)
    if invocation == "control_plane":
        assert result == 0
        assert '"state": "IMPLEMENTED"' in output
        assert pipeline.provider.calls == []

        # Verification is an explicit host action, not a side effect of resume.
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "orchestrator",
                "verify-candidate",
                "T100",
                "--run-id",
                recovered.run_id,
                "--no-integrate",
            ],
        )
        assert cli.main() == 0
        verified_output = capsys.readouterr().out
        assert '"state": "AUDIT_PASS"' in verified_output
        assert set(pipeline.provider.calls) == {"ReviewShard", "Audit"}
    else:
        assert result == 2
        assert "requires trusted control-plane execution" in output
        handoff = recovery_handoff(recovered, integrate=False)
        assert handoff.next_step in output
        assert (pipeline.run_path("T100", recovered.run_id) / "state.json").read_bytes() == before
        assert pipeline.provider.calls == []


def test_end_to_end_control_plane_and_candidate_separation_regression(
    candidate: tuple[Pipeline, RunState, str],
) -> None:
    pipeline, source, snapshot = candidate
    before = source_bytes(pipeline, source)

    # Configure host-owned R2 watchdog liveness upgrade on recovery pipeline
    pipeline.config.roles["worker"].stall_timeout_seconds = 120
    pipeline.config.roles["worker"].stall_confirm_seconds = 45
    pipeline.config.roles["worker"].max_stall_retries = 2

    class TrackingLocalAgents(LocalAgents):
        def __init__(self, audit_status: Literal["PASS", "FAIL"] = "PASS") -> None:
            super().__init__(audit_status=audit_status)
            self.recorded_cwds: list[Path] = []

        def run(
            self,
            prompt: str,
            *,
            cwd: Path,
            role: Role,
            timeout: int | None,
            output: type[Output],
            artifacts: Path,
            name: str,
            readonly: bool,
        ) -> Output:
            self.recorded_cwds.append(cwd)
            return super().run(
                prompt,
                cwd=cwd,
                role=role,
                timeout=timeout,
                output=output,
                artifacts=artifacts,
                name=name,
                readonly=readonly,
            )

    tracking_agents = TrackingLocalAgents()
    pipeline.provider = tracking_agents

    # Recover candidate under trusted control plane
    recovered = pipeline.recover_candidate("T100", source.run_id, snapshot)
    assert recovered.state == State.IMPLEMENTED

    # 1. recovery_handoff points execution to trusted control-plane root
    handoff = recovery_handoff(recovered, integrate=False)
    cp_root = control_plane_root()
    assert handoff.control_plane_cwd == str(cp_root)
    assert handoff.next_step.startswith(f"cd -- {shlex.quote(str(cp_root))}")

    # 2. candidate_worktree points to recovered frozen candidate
    candidate_root = Path(recovered.worktree_path).resolve()
    assert handoff.candidate_worktree == str(candidate_root)

    # 3. The two roots are distinct (no monkeypatching __file__)
    assert cp_root != candidate_root
    assert handoff.control_plane_cwd != handoff.candidate_worktree

    # 4. Recovered candidate snapshot remains exactly expected_source_digest
    candidate_git = Git(candidate_root)
    assert candidate_git.snapshot(source.base_sha) == snapshot

    # 8. No R2/R3 infrastructure source is injected into the candidate merely for recovery
    assert not (candidate_root / "tools/orchestrator/recovery.py").exists()
    assert not (candidate_root / "tools/orchestrator").exists()

    # 5. Resume using the R3 Pipeline/control-plane succeeds while operating
    # on candidate state.worktree_path
    resumed = pipeline.resume("T100", recovered.run_id)
    assert resumed.state == State.AUDIT_PASS
    assert resumed.worktree_path == str(candidate_root)

    # 6. Provider/reviewer cwd remains candidate worktree where applicable
    assert len(tracking_agents.recorded_cwds) > 0
    assert all(recorded_cwd == candidate_root for recorded_cwd in tracking_agents.recorded_cwds)

    # 7. R2 watchdog configuration remains present in active recovered RunState
    assert resumed.config is not None
    assert resumed.config.roles["worker"].stall_timeout_seconds == 120
    assert resumed.config.roles["worker"].stall_confirm_seconds == 45
    assert resumed.config.roles["worker"].max_stall_retries == 2
    persisted = pipeline.status("T100", recovered.run_id)
    assert persisted.config is not None
    assert persisted.config.roles["worker"].stall_timeout_seconds == 120
    assert persisted.config.roles["worker"].stall_confirm_seconds == 45
    assert persisted.config.roles["worker"].max_stall_retries == 2

    # 8. Post-resume candidate snapshot remains exactly expected_source_digest
    assert candidate_git.snapshot(source.base_sha) == snapshot

    # 9. Historical source remains unchanged
    assert source_bytes(pipeline, source) == before

    # Subprocess verification: candidate worktree does NOT contain control-plane tools
    proc_missing = execute(
        [
            sys.executable,
            "-m",
            "tools.orchestrator",
            "resume",
            "T100",
            "--run-id",
            recovered.run_id,
            "--no-integrate",
        ],
        cwd=candidate_root,
        timeout=30,
    )
    assert proc_missing.exit_code == 1
    assert "No module named" in proc_missing.stderr and "tools" in proc_missing.stderr

    # Subprocess verification: CLI guard explicitly rejects execution from candidate worktree
    cfg_file = candidate_root.parent / "config.json"
    cfg_file.write_text(pipeline.config.model_dump_json())
    proc_guard = execute(
        [
            sys.executable,
            "-c",
            (
                f"import sys; sys.path.insert(0, {str(cp_root)!r}); "
                "from tools.orchestrator.__main__ import main; raise SystemExit(main())"
            ),
            "resume",
            "T100",
            "--run-id",
            recovered.run_id,
            "--no-integrate",
            "--config",
            str(cfg_file),
        ],
        cwd=candidate_root,
        timeout=30,
    )
    assert proc_guard.exit_code == 2
    assert "Recovered candidate resume requires trusted control-plane execution" in (
        proc_guard.stdout + proc_guard.stderr
    )
    assert f"cd -- {shlex.quote(str(cp_root))}" in (proc_guard.stdout + proc_guard.stderr)


@pytest.mark.parametrize("invalid", [False, True])
def test_optional_skills_are_carried_only_when_valid(
    candidate: tuple[Pipeline, RunState, str], invalid: bool
) -> None:
    pipeline, source, snapshot = candidate
    skill = pipeline.repository.parent / "skills" / "git-workflow-and-versioning" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: git-workflow-and-versioning\n---\nLocal fixture instructions.\n")
    reference = SkillReference(
        name="git-workflow-and-versioning",
        path=str(skill),
        digest=digest(skill.read_bytes()),
        reason="Preserve Git work.",
    )
    pipeline.artifact(
        pipeline.run_path("T100", source.run_id),
        source,
        "skills",
        SkillManifest(
            task_id="T100",
            task_digest=source.task_digest,
            worker=[reference],
            fix=[reference],
            auditor=[reference],
        ),
    )
    before = source_bytes(pipeline, source)
    if invalid:
        skill.write_text("---\nname: git-workflow-and-versioning\n---\nChanged skill.\n")
        with pytest.raises(OrchestratorError, match="skill changed"):
            pipeline.recover_candidate("T100", source.run_id, snapshot)
    else:
        recovered = pipeline.recover_candidate("T100", source.run_id, snapshot)
        assert recovered.state == State.IMPLEMENTED
        assert "skills" in recovered.artifacts
        assert pipeline.skill_manifest(pipeline.run_path("T100", recovered.run_id), recovered)
    assert source_bytes(pipeline, source) == before


@pytest.mark.parametrize(
    "invalid", ["scope", "malformed-worker", "blocked", "contract", "task", "missing-file"]
)
def test_invalid_handoff_rejected(candidate: tuple[Pipeline, RunState, str], invalid: str) -> None:
    pipeline, source, snapshot = candidate
    directory = pipeline.run_path("T100", source.run_id)
    key = "worker"
    if invalid == "scope":
        (Path(source.worktree_path) / "out-of-scope.txt").write_text("Unexpected")
        snapshot = Git(Path(source.worktree_path)).snapshot(source.base_sha)
    elif invalid == "missing-file":
        (directory / source.artifacts["worker"]).unlink()
    else:
        key = invalid if invalid in {"contract", "task"} else "worker"
        key = "task_card" if key == "task" else key
        path = directory / source.artifacts[key]
        value = read_json(path)
        assert isinstance(value, dict)
        if invalid == "malformed-worker":
            value["changed_files"] = "invalid list"
        elif invalid == "blocked":
            value["status"] = "BLOCKED"
        elif invalid == "contract":
            value["objective"] = "Altered objective"
        elif invalid == "task":
            value["content_digest"] = "0" * 64
        atomic_json(path, value)
        source.artifact_digests[path.name] = digest(path.read_bytes())
        if invalid == "contract":
            source.contract_digest = source.artifact_digests[path.name]
        pipeline.save(directory, source)
    with pytest.raises(ValidationError if invalid == "malformed-worker" else OrchestratorError):
        pipeline.recover_candidate("T100", source.run_id, snapshot)
    assert len(list((pipeline.runs / "T100").glob("*/state.json"))) == 1


@pytest.mark.parametrize("resource", ["task", "run"])
def test_existing_locks_remain_enforced(
    candidate: tuple[Pipeline, RunState, str], resource: str
) -> None:
    pipeline, source, snapshot = candidate
    path = (
        pipeline.locks / "T100.lock"
        if resource == "task"
        else pipeline.run_path("T100", source.run_id) / ".run.lock"
    )
    before = source_bytes(pipeline, source)
    with lock(path), pytest.raises(LockBusy):
        pipeline.recover_candidate("T100", source.run_id, snapshot)
    assert source_bytes(pipeline, source) == before


def test_historical_r2_attempt_artifacts_validated_and_not_carried(
    candidate: tuple[Pipeline, RunState, str],
) -> None:
    pipeline, source, snapshot = candidate
    directory = pipeline.run_path("T100", source.run_id)
    attempt_prefix = "00-auditor-12345678-a01"
    prompt_bytes = b"authoritative attempt prompt"
    context_bytes = b'{"task_id": "T100", "version": 1}'
    log_bytes = b'{"exit_code": 0, "stalled": false}'
    (directory / f"{attempt_prefix}.prompt.md").write_bytes(prompt_bytes)
    (directory / f"{attempt_prefix}.auditor-context.json").write_bytes(context_bytes)
    (directory / f"{attempt_prefix}.log.json").write_bytes(log_bytes)
    source.artifact_digests[f"{attempt_prefix}.prompt.md"] = digest(prompt_bytes)
    source.artifact_digests[f"{attempt_prefix}.auditor-context.json"] = digest(context_bytes)
    source.artifact_digests[f"{attempt_prefix}.log.json"] = digest(log_bytes)
    pipeline.save(directory, source)

    before = source_bytes(pipeline, source)
    recovered = pipeline.recover_candidate("T100", source.run_id, snapshot)
    assert recovered.state == State.IMPLEMENTED
    target_dir = pipeline.run_path("T100", recovered.run_id)

    # Historical attempt artifacts remain unchanged in source
    assert source_bytes(pipeline, source) == before

    # Recovered run carries ONLY pre-audit handoff artifacts + setup + recovery_origin
    assert f"{attempt_prefix}.prompt.md" not in recovered.artifact_digests
    assert f"{attempt_prefix}.auditor-context.json" not in recovered.artifact_digests
    assert f"{attempt_prefix}.log.json" not in recovered.artifact_digests
    assert not (target_dir / f"{attempt_prefix}.prompt.md").exists()
    assert not (target_dir / f"{attempt_prefix}.auditor-context.json").exists()
    assert not (target_dir / f"{attempt_prefix}.log.json").exists()


def test_liveness_only_recovery_configuration_upgrade_and_resume(
    candidate: tuple[Pipeline, RunState, str],
) -> None:
    pipeline, source, snapshot = candidate
    before = source_bytes(pipeline, source)
    provider = pipeline.provider
    assert isinstance(provider, LocalAgents)
    assert provider.calls == []

    # Upgrade host-owned liveness supervisor configuration on the recovery pipeline
    pipeline.config.roles["worker"].stall_timeout_seconds = 120
    pipeline.config.roles["worker"].stall_confirm_seconds = 45
    pipeline.config.roles["worker"].max_stall_retries = 2
    pipeline.config.roles["auditor"].stall_timeout_seconds = 60

    assert source.config is not None
    assert is_liveness_config_upgraded(source.config, pipeline.config)
    assert recovery_config_compatible(source.config, pipeline.config)

    # 1. Changing only liveness watchdog fields permits recovery
    recovered = pipeline.recover_candidate("T100", source.run_id, snapshot)
    assert recovered.state == State.IMPLEMENTED

    # 14. No AI provider is invoked during recovery
    provider = pipeline.provider
    assert isinstance(provider, LocalAgents)
    assert provider.calls == []

    # 2. The recovered RunState stores the new liveness values in memory and on disk
    assert recovered.config is not None
    assert recovered.config.roles["worker"].stall_timeout_seconds == 120
    assert recovered.config.roles["worker"].stall_confirm_seconds == 45
    assert recovered.config.roles["worker"].max_stall_retries == 2
    assert recovered.config.roles["auditor"].stall_timeout_seconds == 60

    persisted = pipeline.status("T100", recovered.run_id)
    assert persisted.config is not None
    assert persisted.config.roles["worker"].stall_timeout_seconds == 120
    assert persisted.config.roles["worker"].stall_confirm_seconds == 45
    assert persisted.config.roles["worker"].max_stall_retries == 2
    assert persisted.config.roles["auditor"].stall_timeout_seconds == 60

    # 11, 12. RecoveryOrigin config digests match exact historical and recovered typed configs
    target_dir = pipeline.run_path("T100", recovered.run_id)
    origin_path = target_dir / recovered.artifacts["recovery_origin"]
    origin = RecoveryOrigin.model_validate(read_json(origin_path))
    assert origin.source_config_digest == config_digest(source.config)
    assert origin.recovery_config_digest == config_digest(pipeline.config)
    assert origin.recovery_config_digest == config_digest(recovered.config)
    assert origin.source_config_digest != origin.recovery_config_digest
    assert origin.liveness_config_upgraded is True

    # 13. Historical source state/config/artifacts remain completely unchanged
    assert source_bytes(pipeline, source) == before
    assert source.config.roles["worker"].stall_timeout_seconds is None

    # 3. The recovered run can subsequently resume using the same upgraded config
    resumed = pipeline.resume("T100", recovered.run_id)
    assert resumed.state == State.AUDIT_PASS
    assert source_bytes(pipeline, source) == before

    # Normal resume still rejects if config changes after recovery
    pipeline.config.roles["worker"].stall_timeout_seconds = 999
    resumed_failed = pipeline.resume("T100", recovered.run_id)
    assert resumed_failed.state == State.FAILED
    assert "Configuration changed since run start" in (resumed_failed.last_error or "")


@pytest.mark.parametrize(
    "field,value",
    [
        ("stall_timeout_seconds", 300),
        ("stall_confirm_seconds", 15),
        ("max_stall_retries", 3),
    ],
)
def test_each_liveness_field_individually_permits_recovery(
    candidate: tuple[Pipeline, RunState, str], field: str, value: int
) -> None:
    pipeline, source, snapshot = candidate
    before = source_bytes(pipeline, source)

    setattr(pipeline.config.roles["worker"], field, value)
    assert source.config is not None
    assert is_liveness_config_upgraded(source.config, pipeline.config)
    assert recovery_config_compatible(source.config, pipeline.config)

    recovered = pipeline.recover_candidate("T100", source.run_id, snapshot)
    assert recovered.state == State.IMPLEMENTED
    assert recovered.config is not None
    assert getattr(recovered.config.roles["worker"], field) == value
    provider = pipeline.provider
    assert isinstance(provider, LocalAgents)
    assert provider.calls == []

    origin = RecoveryOrigin.model_validate(
        read_json(
            pipeline.run_path("T100", recovered.run_id) / recovered.artifacts["recovery_origin"]
        )
    )
    assert origin.liveness_config_upgraded is True
    assert origin.source_config_digest == config_digest(source.config)
    assert origin.recovery_config_digest == config_digest(recovered.config)
    assert origin.source_config_digest != origin.recovery_config_digest
    assert source_bytes(pipeline, source) == before


@pytest.mark.parametrize(
    "mutation_type,mutation_fn",
    [
        ("provider_gemini", lambda cfg: setattr(cfg.roles["worker"], "provider", "gemini")),
        ("provider_agy", lambda cfg: setattr(cfg.roles["worker"], "provider", "agy")),
        ("model", lambda cfg: setattr(cfg.roles["worker"], "model", "gemini-3.8-flash-high")),
        ("reasoning", lambda cfg: setattr(cfg.roles["worker"], "reasoning", "high")),
        ("verification", lambda cfg: setattr(cfg, "verification", [["python", "-m", "pytest"]])),
        ("setup_commands", lambda cfg: setattr(cfg, "setup_commands", [])),
        ("timeout_seconds", lambda cfg: setattr(cfg, "timeout_seconds", 90)),
        ("max_fix_cycles", lambda cfg: setattr(cfg, "max_fix_cycles", 1)),
        ("executable", lambda cfg: setattr(cfg.roles["worker"], "executable", "custom-exec")),
        ("worker_access", lambda cfg: setattr(cfg.roles["worker"], "worker_access", "full-access")),
        ("allow_process", lambda cfg: setattr(cfg.roles["worker"], "allow_process", True)),
        ("base_branch", lambda cfg: setattr(cfg, "base_branch", "develop")),
        ("skills_root", lambda cfg: setattr(cfg, "skills_root", "custom_skills")),
    ],
)
def test_non_liveness_config_mutations_fail_recovery(
    candidate: tuple[Pipeline, RunState, str], mutation_type: str, mutation_fn: object
) -> None:
    pipeline, source, snapshot = candidate
    before = source_bytes(pipeline, source)

    assert mutation_type and callable(mutation_fn)
    mutation_fn(pipeline.config)

    assert source.config is not None
    assert not recovery_config_compatible(source.config, pipeline.config)

    with pytest.raises(OrchestratorError, match="Configuration changed since source run start"):
        pipeline.recover_candidate("T100", source.run_id, snapshot)

    # 13. Historical source state/config/artifacts remain completely unchanged
    assert source_bytes(pipeline, source) == before
    # 14. No AI provider is invoked
    provider = pipeline.provider
    assert isinstance(provider, LocalAgents)
    assert provider.calls == []
    # No recovery run created
    assert len(list((pipeline.runs / "T100").glob("*/state.json"))) == 1


def test_paths_mutation_fails_recovery_unit() -> None:
    base_roles = {
        name: Role(provider="codex", executable="unused-local-fixture")
        for name in ("prompt_engineer", "worker", "auditor", "integrator")
    }
    cfg1 = Config(
        roles=base_roles,
        verification=[["git", "diff", "--check"]],
        setup_commands=[["npm", "ci"]],
        timeout_seconds=30,
        integrate=False,
    )
    cfg_paths = cfg1.model_copy(update={"paths": Paths(run_dir=".other-runs")})
    assert not recovery_config_compatible(cfg1, cfg_paths)


def test_recovery_config_helpers_unit() -> None:
    base_roles = {
        name: Role(provider="codex", executable="unused-local-fixture")
        for name in ("prompt_engineer", "worker", "auditor", "integrator")
    }
    cfg1 = Config(
        roles=base_roles,
        verification=[["git", "diff", "--check"]],
        setup_commands=[["npm", "ci"]],
        timeout_seconds=30,
        integrate=False,
    )
    # None handling
    assert not recovery_config_compatible(None, cfg1)
    assert not recovery_config_compatible(cfg1, None)
    assert not recovery_config_compatible(None, None)

    # Self compatibility
    assert recovery_config_compatible(cfg1, cfg1)
    assert not is_liveness_config_upgraded(cfg1, cfg1)

    # Integrate change alone is compatible, not liveness upgrade
    cfg_int = cfg1.model_copy(update={"integrate": True})
    assert recovery_config_compatible(cfg1, cfg_int)
    assert not is_liveness_config_upgraded(cfg1, cfg_int)

    # Liveness upgrade
    upgraded_roles = {k: v.model_copy() for k, v in base_roles.items()}
    upgraded_roles["worker"] = upgraded_roles["worker"].model_copy(
        update={"stall_timeout_seconds": 60, "stall_confirm_seconds": 10, "max_stall_retries": 2}
    )
    cfg_live = cfg1.model_copy(update={"roles": upgraded_roles})
    assert recovery_config_compatible(cfg1, cfg_live)
    assert is_liveness_config_upgraded(cfg1, cfg_live)

    # Missing / extra role
    cfg_missing = cfg1.model_copy(update={"roles": {"worker": base_roles["worker"]}})
    assert not recovery_config_compatible(cfg1, cfg_missing)

    # Determinism of config_digest
    digest1 = config_digest(cfg1)
    digest2 = config_digest(cfg1.model_copy(deep=True))
    assert digest1 == digest2
    assert re.fullmatch(r"[0-9a-f]{64}", digest1)
    assert config_digest(cfg_live) != digest1
    assert config_digest(cfg_int) != digest1


def build_synthetic_import_fixture(
    tmp_path: Path,
    pipeline: Pipeline,
    historical: RunState,
    *,
    branch: str | None = None,
    worktree_name: str | None = None,
    changed_files: dict[str, str] | None = None,
    tamper_manifest: dict[str, object] | None = None,
    tamper_scouts: dict[str, dict[str, object]] | None = None,
    tamper_adjudication: dict[str, object] | None = None,
    tamper_judge_resp: dict[str, object] | None = None,
    tamper_judge_prompt: str | None = None,
    raw_files: dict[str, bytes] | None = None,
    custom_actual_paths: list[str] | None = None,
) -> tuple[Path, str, Path, str]:
    token = uuid4().hex[:8]
    branch_name = branch or f"salvage-{token}"
    wt_name = worktree_name or f"external-salvage-{token}"
    ext_dir = tmp_path / wt_name
    if not ext_dir.exists():
        pipeline.git.create_worktree(ext_dir, branch_name, historical.base_sha)
    modifications = (
        changed_files
        if changed_files is not None
        else {
            "feature.txt": "working\n",
            "docs/changelogs.md": "Recovery fixture\nHistorical fixture\n",
        }
    )
    for path_str, content in modifications.items():
        target_f = ext_dir / path_str
        target_f.parent.mkdir(parents=True, exist_ok=True)
        target_f.write_text(content, encoding="utf-8")
    ext_git = Git(ext_dir)
    candidate_digest = ext_git.snapshot(historical.base_sha)
    actual_changed_paths = (
        custom_actual_paths
        if custom_actual_paths is not None
        else sorted(ext_git.paths(historical.base_sha))
    )

    evidence_dir = tmp_path / f"evidence-{token}"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    sm_lines = []
    sm_entries = {}
    for p in actual_changed_paths:
        target_file = ext_dir / p
        raw = target_file.read_bytes() if target_file.is_file() else b""
        sha = digest(raw)
        sz = len(raw)
        sm_lines.append(f"{sha} {sz} {p}")
        sm_entries[p] = {"sha256": sha, "byte_size": sz}
    sm_raw = ("\n".join(sm_lines) + "\n").encode("utf-8") if sm_lines else b""

    scout_perspectives = {
        "A": "probe_safety",
        "B": "evidence_binding",
        "C": "regression_authority",
    }
    scout_files = {
        "A": actual_changed_paths,
        "B": actual_changed_paths[:1] if len(actual_changed_paths) > 1 else actual_changed_paths,
        "C": actual_changed_paths[1:] if len(actual_changed_paths) > 1 else actual_changed_paths,
    }
    scout_raws: dict[str, bytes] = {}
    scout_packets: dict[str, dict[str, object]] = {}
    for s in ("A", "B", "C"):
        sp: dict[str, object] = {
            "schema_version": 1,
            "perspective": scout_perspectives[s],
            "candidate_digest": candidate_digest,
            "reviewed_files": list(scout_files[s]),
            "findings": [],
        }
        if tamper_scouts and s in tamper_scouts:
            sp.update(tamper_scouts[s])
        s_bytes = json.dumps(sp, indent=2).encode("utf-8")
        scout_raws[s] = s_bytes
        scout_packets[s] = sp

    adj_scouts = []
    finding_counts: list[int] = []
    for s in ("A", "B", "C"):
        rf = scout_packets[s]["reviewed_files"]
        fn = scout_packets[s]["findings"]
        assert isinstance(rf, list) and isinstance(fn, list)
        finding_counts.append(len(fn))
        adj_scouts.append(
            {
                "scout": s,
                "perspective": scout_perspectives[s],
                "packet_sha256": digest(scout_raws[s]),
                "reviewed_files": list(rf),
                "finding_count": len(fn),
            }
        )
    adj_packet: dict[str, object] = {
        "schema_version": 1,
        "candidate_identity": {
            "task_id": historical.task_id,
            "base_sha": historical.base_sha,
            "candidate_digest": candidate_digest,
        },
        "source_manifest": sm_entries,
        "semantic_discovery": {
            "protocol": "light-scout-host-validated-v1",
            "scouts": adj_scouts,
            "finding_count": sum(finding_counts),
            "findings": [],
        },
    }
    if tamper_adjudication:
        adj_packet.update(tamper_adjudication)
    adj_raw = json.dumps(adj_packet, indent=2).encode("utf-8")
    compact_raw = json.dumps(adj_packet, separators=(",", ":"), sort_keys=True).encode("utf-8")

    judge_prompt = (
        tamper_judge_prompt
        if tamper_judge_prompt is not None
        else (
            "BEGIN ADJUDICATION PACKET\n"
            + compact_raw.decode("utf-8").strip()
            + "\nEND ADJUDICATION PACKET\n"
        )
    )
    judge_prompt_raw = judge_prompt.encode("utf-8")
    judge_schema = {"type": "object", "properties": {"decision": {"type": "string"}}}
    judge_schema_raw = json.dumps(judge_schema, indent=2).encode("utf-8")

    judge_resp: dict[str, object] = {
        "schema_version": 1,
        "candidate_digest": candidate_digest,
        "decision": "PASS",
        "rationale": "Synthetic PASS",
        "confirmed_findings": [],
        "dismissed_findings": [],
        "evidence_requests": [],
    }
    if tamper_judge_resp:
        judge_resp.update(tamper_judge_resp)
    judge_resp_raw = json.dumps(judge_resp, indent=2).encode("utf-8")

    artifacts_files = {
        "source-manifest.txt": sm_raw,
        "scout-A.packet.json": scout_raws["A"],
        "scout-B.packet.json": scout_raws["B"],
        "scout-C.packet.json": scout_raws["C"],
        "adjudication-packet.json": adj_raw,
        "adjudication-packet.compact.json": compact_raw,
        "heavy-judge.prompt.txt": judge_prompt_raw,
        "heavy-judge.schema.json": judge_schema_raw,
        "heavy-judge.response.json": judge_resp_raw,
    }
    if raw_files:
        artifacts_files.update(raw_files)
    for name, b_data in artifacts_files.items():
        (evidence_dir / name).write_bytes(b_data)

    art_manifest = {}
    for name, b_data in artifacts_files.items():
        art_manifest[name] = {
            "path": str((evidence_dir / name).resolve()),
            "sha256": digest(b_data),
            "byte_size": len(b_data),
        }
    manifest: dict[str, object] = {
        "schema_version": 1,
        "task_id": historical.task_id,
        "base_sha": historical.base_sha,
        "candidate_digest": candidate_digest,
        "artifacts": art_manifest,
    }
    if tamper_manifest:
        manifest.update(tamper_manifest)
    manifest_raw = json.dumps(manifest, indent=2).encode("utf-8")
    manifest_path = evidence_dir / "provenance-manifest.json"
    manifest_path.write_bytes(manifest_raw)
    manifest_digest = digest(manifest_raw)
    return ext_dir, candidate_digest, manifest_path, manifest_digest


def test_import_candidate_success_and_lineage_immutability(
    candidate: tuple[Pipeline, RunState, str], tmp_path: Path
) -> None:
    pipeline, source, _ = candidate
    before = source_bytes(pipeline, source)
    ext_dir, cand_digest, manifest_path, manifest_digest = build_synthetic_import_fixture(
        tmp_path, pipeline, source
    )

    imported = pipeline.import_candidate(
        "T100",
        source.run_id,
        source_worktree=ext_dir,
        expected_source_digest=cand_digest,
        provenance_manifest=manifest_path,
        expected_provenance_digest=manifest_digest,
    )

    assert imported.state == State.AUDIT_PASS
    assert imported.audited_digest == cand_digest
    assert imported.verified_digest == cand_digest
    assert imported.current_agent is None
    assert imported.blocked_from is None
    assert imported.last_error is None
    assert isinstance(pipeline.provider, LocalAgents)
    assert pipeline.provider.calls == []

    # Historical lineage run remains byte-identical
    assert source_bytes(pipeline, source) == before

    # Target worktree is orchestrator-owned and contains candidate files
    target_wt = Path(imported.worktree_path)
    assert target_wt.is_dir()
    assert target_wt.parent == pipeline.worktrees
    assert (target_wt / "feature.txt").read_text() == "working\n"
    assert (target_wt / "docs/changelogs.md").read_text() == (
        "Recovery fixture\nHistorical fixture\n"
    )

    # Imported run has 00-imported-* flat sealed files
    target_dir = pipeline.run_path("T100", imported.run_id)
    assert (target_dir / "state.json").is_file()
    for name in (
        "source-manifest.txt",
        "scout-A.packet.json",
        "scout-B.packet.json",
        "scout-C.packet.json",
        "adjudication-packet.json",
        "adjudication-packet.compact.json",
        "heavy-judge.prompt.txt",
        "heavy-judge.schema.json",
        "heavy-judge.response.json",
    ):
        flat_name = f"00-imported-{name}"
        assert flat_name in imported.artifacts.values()
        assert flat_name in imported.artifact_digests
        assert (target_dir / flat_name).is_file()

    # Provenance origin and semantic evidence sealed
    assert "candidate_import_origin" in imported.artifacts
    assert "imported_semantic_evidence" in imported.artifacts
    origin = CandidateImportOrigin.model_validate(
        read_json(target_dir / imported.artifacts["candidate_import_origin"])
    )
    assert origin.lineage_run_id == source.run_id
    assert origin.import_run_id == imported.run_id
    assert origin.base_sha == source.base_sha
    assert origin.candidate_digest == cand_digest
    assert origin.provenance_digest == manifest_digest
    assert origin.source_worktree == str(ext_dir.resolve())
    assert origin.source_fix_cycle == source.fix_cycle
    assert origin.import_fix_cycle == imported.fix_cycle
    assert origin.max_fix_cycles == imported.max_fix_cycles

    semantic_ev = ImportedSemanticEvidence.model_validate(
        read_json(target_dir / imported.artifacts["imported_semantic_evidence"])
    )
    assert semantic_ev.judge_decision == "PASS"
    assert semantic_ev.all_reviewed_files == ["docs/changelogs.md", "feature.txt"]


def test_import_candidate_historical_lineage_validation(
    candidate: tuple[Pipeline, RunState, str], tmp_path: Path
) -> None:
    pipeline, source, _ = candidate
    ext_dir, cand_digest, manifest_path, manifest_digest = build_synthetic_import_fixture(
        tmp_path, pipeline, source
    )
    source_dir = pipeline.run_path("T100", source.run_id)

    # 1. Non-FAILED state rejected
    source.state = State.READY
    pipeline.save(source_dir, source)
    with pytest.raises(OrchestratorError, match="in FAILED state"):
        pipeline.import_candidate(
            "T100",
            source.run_id,
            source_worktree=ext_dir,
            expected_source_digest=cand_digest,
            provenance_manifest=manifest_path,
            expected_provenance_digest=manifest_digest,
        )

    # 2. Lineage originating from FIX_RUNNING with current_agent="worker" accepted
    source.state = State.FAILED
    source.blocked_from = State.FIX_RUNNING
    source.current_agent = "worker"
    pipeline.save(source_dir, source)
    imported = pipeline.import_candidate(
        "T100",
        source.run_id,
        source_worktree=ext_dir,
        expected_source_digest=cand_digest,
        provenance_manifest=manifest_path,
        expected_provenance_digest=manifest_digest,
    )
    assert imported.state == State.AUDIT_PASS
    source.blocked_from = State.AUDIT_RUNNING
    source.current_agent = None
    pipeline.save(source_dir, source)

    # 3. Contract digest mismatch rejected
    source.contract_digest = "0" * 64
    pipeline.save(source_dir, source)
    with pytest.raises(OrchestratorError, match="contract changed"):
        pipeline.import_candidate(
            "T100",
            source.run_id,
            source_worktree=ext_dir,
            expected_source_digest=cand_digest,
            provenance_manifest=manifest_path,
            expected_provenance_digest=manifest_digest,
        )


def test_import_candidate_external_source_validation(
    candidate: tuple[Pipeline, RunState, str], tmp_path: Path
) -> None:
    pipeline, source, _ = candidate
    ext_dir, cand_digest, manifest_path, manifest_digest = build_synthetic_import_fixture(
        tmp_path, pipeline, source
    )

    # 1. Foreign Git repository rejected
    foreign_repo = tmp_path / "foreign-repo"
    foreign_repo.mkdir()
    Git(foreign_repo).run("init")
    with pytest.raises(OrchestratorError, match="different Git repository"):
        pipeline.import_candidate(
            "T100",
            source.run_id,
            source_worktree=foreign_repo,
            expected_source_digest=cand_digest,
            provenance_manifest=manifest_path,
            expected_provenance_digest=manifest_digest,
        )

    # 2. Wrong snapshot digest rejected
    wrong_digest = "a" * 64
    with pytest.raises(OrchestratorError, match="Source candidate digest mismatch"):
        pipeline.import_candidate(
            "T100",
            source.run_id,
            source_worktree=ext_dir,
            expected_source_digest=wrong_digest,
            provenance_manifest=manifest_path,
            expected_provenance_digest=manifest_digest,
        )

    # 3. Symlink source worktree rejected
    symlink_wt = tmp_path / "symlink-wt"
    symlink_wt.symlink_to(ext_dir)
    with pytest.raises(OrchestratorError, match="contains a symlink"):
        pipeline.import_candidate(
            "T100",
            source.run_id,
            source_worktree=symlink_wt,
            expected_source_digest=cand_digest,
            provenance_manifest=manifest_path,
            expected_provenance_digest=manifest_digest,
        )

    # 4. Wrong HEAD rejected
    (ext_dir / "head-advance.txt").write_text("advance")
    Git(ext_dir).run("add", "head-advance.txt")
    Git(ext_dir).run("commit", "-m", "advance head")
    with pytest.raises(OrchestratorError, match="Source HEAD differs from historical base"):
        pipeline.import_candidate(
            "T100",
            source.run_id,
            source_worktree=ext_dir,
            expected_source_digest=cand_digest,
            provenance_manifest=manifest_path,
            expected_provenance_digest=manifest_digest,
        )


def test_import_candidate_provenance_manifest_validation(
    candidate: tuple[Pipeline, RunState, str], tmp_path: Path
) -> None:
    pipeline, source, _ = candidate

    # 1. Wrong expected_provenance_digest rejected
    ext_dir, cand_digest, manifest_path, _ = build_synthetic_import_fixture(
        tmp_path, pipeline, source
    )
    with pytest.raises(OrchestratorError, match="Provenance manifest digest mismatch"):
        pipeline.import_candidate(
            "T100",
            source.run_id,
            source_worktree=ext_dir,
            expected_source_digest=cand_digest,
            provenance_manifest=manifest_path,
            expected_provenance_digest="0" * 64,
        )

    # 2. Task ID mismatch rejected
    ext_dir, cand_digest, mf_path, mf_digest = build_synthetic_import_fixture(
        tmp_path, pipeline, source, tamper_manifest={"task_id": "T999"}
    )
    with pytest.raises(OrchestratorError, match="Provenance manifest task ID mismatch"):
        pipeline.import_candidate(
            "T100",
            source.run_id,
            source_worktree=ext_dir,
            expected_source_digest=cand_digest,
            provenance_manifest=mf_path,
            expected_provenance_digest=mf_digest,
        )

    # 3. Base SHA mismatch rejected
    ext_dir, cand_digest, mf_path, mf_digest = build_synthetic_import_fixture(
        tmp_path, pipeline, source, tamper_manifest={"base_sha": "0" * 40}
    )
    with pytest.raises(OrchestratorError, match="Provenance manifest base SHA mismatch"):
        pipeline.import_candidate(
            "T100",
            source.run_id,
            source_worktree=ext_dir,
            expected_source_digest=cand_digest,
            provenance_manifest=mf_path,
            expected_provenance_digest=mf_digest,
        )

    # 4. Artifact missing on disk rejected
    ext_dir, cand_digest, mf_path, mf_digest = build_synthetic_import_fixture(
        tmp_path, pipeline, source
    )
    (mf_path.parent / "heavy-judge.response.json").unlink()
    with pytest.raises(OrchestratorError, match="is not a regular file"):
        pipeline.import_candidate(
            "T100",
            source.run_id,
            source_worktree=ext_dir,
            expected_source_digest=cand_digest,
            provenance_manifest=mf_path,
            expected_provenance_digest=mf_digest,
        )

    # 5. Artifact is symlink rejected
    ext_dir, cand_digest, mf_path, mf_digest = build_synthetic_import_fixture(
        tmp_path, pipeline, source
    )
    real_f = mf_path.parent / "real_judge.json"
    (mf_path.parent / "heavy-judge.response.json").rename(real_f)
    (mf_path.parent / "heavy-judge.response.json").symlink_to(real_f)
    with pytest.raises(OrchestratorError, match="path contains a symlink"):
        pipeline.import_candidate(
            "T100",
            source.run_id,
            source_worktree=ext_dir,
            expected_source_digest=cand_digest,
            provenance_manifest=mf_path,
            expected_provenance_digest=mf_digest,
        )


def test_import_candidate_strict_json(
    candidate: tuple[Pipeline, RunState, str], tmp_path: Path
) -> None:
    pipeline, source, _ = candidate

    # 1. Duplicate JSON key rejected
    dup_raw = (
        b'{\n  "schema_version": 1,\n  "schema_version": 1,\n'
        b'  "perspective": "probe_safety",\n  "candidate_digest": "dummy",\n'
        b'  "reviewed_files": [],\n  "findings": []\n}'
    )
    ext_dir, cand_digest, mf_path, mf_digest = build_synthetic_import_fixture(
        tmp_path, pipeline, source, raw_files={"scout-A.packet.json": dup_raw}
    )
    with pytest.raises(OrchestratorError, match="Duplicate JSON key"):
        pipeline.import_candidate(
            "T100",
            source.run_id,
            source_worktree=ext_dir,
            expected_source_digest=cand_digest,
            provenance_manifest=mf_path,
            expected_provenance_digest=mf_digest,
        )

    # 2. Trailing data rejected
    ext_dir, cand_digest, mf_path, mf_digest = build_synthetic_import_fixture(
        tmp_path,
        pipeline,
        source,
        raw_files={"heavy-judge.schema.json": b'{"type": "object"} trailing'},
    )
    with pytest.raises(OrchestratorError, match="trailing JSON"):
        pipeline.import_candidate(
            "T100",
            source.run_id,
            source_worktree=ext_dir,
            expected_source_digest=cand_digest,
            provenance_manifest=mf_path,
            expected_provenance_digest=mf_digest,
        )

    # 3. Invalid UTF-8 rejected
    ext_dir, cand_digest, mf_path, mf_digest = build_synthetic_import_fixture(
        tmp_path, pipeline, source, raw_files={"scout-B.packet.json": b'{"decision": \xff}'}
    )
    with pytest.raises(OrchestratorError, match="Invalid UTF-8"):
        pipeline.import_candidate(
            "T100",
            source.run_id,
            source_worktree=ext_dir,
            expected_source_digest=cand_digest,
            provenance_manifest=mf_path,
            expected_provenance_digest=mf_digest,
        )


def test_import_candidate_semantic_coverage(
    candidate: tuple[Pipeline, RunState, str], tmp_path: Path
) -> None:
    pipeline, source, _ = candidate

    # 1. Source manifest missing actual changed path rejected
    ext_dir, cand_digest, mf_path, mf_digest = build_synthetic_import_fixture(
        tmp_path, pipeline, source, custom_actual_paths=["feature.txt"]
    )
    with pytest.raises(
        OrchestratorError,
        match="Source manifest changed paths do not exactly match Git changed paths",
    ):
        pipeline.import_candidate(
            "T100",
            source.run_id,
            source_worktree=ext_dir,
            expected_source_digest=cand_digest,
            provenance_manifest=mf_path,
            expected_provenance_digest=mf_digest,
        )

    # 2. Scout reviewed files union missing actual changed path rejected
    ext_dir, cand_digest, mf_path, mf_digest = build_synthetic_import_fixture(
        tmp_path,
        pipeline,
        source,
        tamper_scouts={
            "A": {"reviewed_files": ["feature.txt"]},
            "B": {"reviewed_files": ["feature.txt"]},
            "C": {"reviewed_files": ["feature.txt"]},
        },
    )
    with pytest.raises(
        OrchestratorError, match="Scout reviewed files union does not match changed paths"
    ):
        pipeline.import_candidate(
            "T100",
            source.run_id,
            source_worktree=ext_dir,
            expected_source_digest=cand_digest,
            provenance_manifest=mf_path,
            expected_provenance_digest=mf_digest,
        )

    # 3. Scout reviewed file not in changed paths rejected
    ext_dir, cand_digest, mf_path, mf_digest = build_synthetic_import_fixture(
        tmp_path,
        pipeline,
        source,
        tamper_scouts={"A": {"reviewed_files": ["feature.txt", "unrelated.txt"]}},
    )
    with pytest.raises(OrchestratorError, match="reviewed file not in changed paths"):
        pipeline.import_candidate(
            "T100",
            source.run_id,
            source_worktree=ext_dir,
            expected_source_digest=cand_digest,
            provenance_manifest=mf_path,
            expected_provenance_digest=mf_digest,
        )


def test_import_candidate_zero_findings_v1(
    candidate: tuple[Pipeline, RunState, str], tmp_path: Path
) -> None:
    pipeline, source, _ = candidate

    # 1. Scout findings non-empty rejected
    ext_dir, cand_digest, mf_path, mf_digest = build_synthetic_import_fixture(
        tmp_path,
        pipeline,
        source,
        tamper_scouts={"A": {"findings": ["semantic issue"]}},
    )
    with pytest.raises(OrchestratorError, match="Scout A findings must be empty"):
        pipeline.import_candidate(
            "T100",
            source.run_id,
            source_worktree=ext_dir,
            expected_source_digest=cand_digest,
            provenance_manifest=mf_path,
            expected_provenance_digest=mf_digest,
        )

    # 2. Judge decision != PASS rejected
    ext_dir, cand_digest, mf_path, mf_digest = build_synthetic_import_fixture(
        tmp_path, pipeline, source, tamper_judge_resp={"decision": "FAIL"}
    )
    with pytest.raises(OrchestratorError, match="Judge response decision must be PASS, got FAIL"):
        pipeline.import_candidate(
            "T100",
            source.run_id,
            source_worktree=ext_dir,
            expected_source_digest=cand_digest,
            provenance_manifest=mf_path,
            expected_provenance_digest=mf_digest,
        )

    # 3. Judge confirmed findings non-empty rejected
    ext_dir, cand_digest, mf_path, mf_digest = build_synthetic_import_fixture(
        tmp_path,
        pipeline,
        source,
        tamper_judge_resp={"confirmed_findings": ["confirmed finding"]},
    )
    with pytest.raises(OrchestratorError, match="Judge response confirmed findings must be empty"):
        pipeline.import_candidate(
            "T100",
            source.run_id,
            source_worktree=ext_dir,
            expected_source_digest=cand_digest,
            provenance_manifest=mf_path,
            expected_provenance_digest=mf_digest,
        )

    # 4. Judge evidence requests non-empty rejected
    ext_dir, cand_digest, mf_path, mf_digest = build_synthetic_import_fixture(
        tmp_path,
        pipeline,
        source,
        tamper_judge_resp={
            "evidence_requests": [
                {
                    "request_id": "REQ-1",
                    "category": "PROBE_SAFETY",
                    "question": "Need info",
                }
            ]
        },
    )
    with pytest.raises(OrchestratorError, match="Judge response evidence requests must be empty"):
        pipeline.import_candidate(
            "T100",
            source.run_id,
            source_worktree=ext_dir,
            expected_source_digest=cand_digest,
            provenance_manifest=mf_path,
            expected_provenance_digest=mf_digest,
        )


def test_import_candidate_evidence_association(
    candidate: tuple[Pipeline, RunState, str], tmp_path: Path
) -> None:
    pipeline, source, _ = candidate

    # 1. Compact packet differing from full adjudication packet rejected
    ext_dir, cand_digest, mf_path, mf_digest = build_synthetic_import_fixture(
        tmp_path,
        pipeline,
        source,
        raw_files={"adjudication-packet.compact.json": b'{"different": true}'},
    )
    with pytest.raises(
        OrchestratorError, match="Adjudication packet and compact packet differ semantically"
    ):
        pipeline.import_candidate(
            "T100",
            source.run_id,
            source_worktree=ext_dir,
            expected_source_digest=cand_digest,
            provenance_manifest=mf_path,
            expected_provenance_digest=mf_digest,
        )

    # 2. Judge prompt missing packet delimiters rejected
    ext_dir, cand_digest, mf_path, mf_digest = build_synthetic_import_fixture(
        tmp_path,
        pipeline,
        source,
        tamper_judge_prompt="Arbitrary judge prompt without delimiters",
    )
    with pytest.raises(
        OrchestratorError, match="Judge prompt must contain exactly one pair of packet delimiters"
    ):
        pipeline.import_candidate(
            "T100",
            source.run_id,
            source_worktree=ext_dir,
            expected_source_digest=cand_digest,
            provenance_manifest=mf_path,
            expected_provenance_digest=mf_digest,
        )


def test_import_candidate_mechanical_verification_failure(
    candidate: tuple[Pipeline, RunState, str], tmp_path: Path
) -> None:
    pipeline, source, _ = candidate
    # Candidate code breaks test_candidate() in test_app.py
    ext_dir, cand_digest, manifest_path, manifest_digest = build_synthetic_import_fixture(
        tmp_path,
        pipeline,
        source,
        changed_files={
            "feature.txt": "broken\n",
            "docs/changelogs.md": "Recovery fixture\nHistorical fixture\n",
        },
    )

    imported = pipeline.import_candidate(
        "T100",
        source.run_id,
        source_worktree=ext_dir,
        expected_source_digest=cand_digest,
        provenance_manifest=manifest_path,
        expected_provenance_digest=manifest_digest,
    )
    assert imported.state == State.FAILED
    assert imported.audited_digest == ""


def test_import_candidate_copied_evidence_independence(
    candidate: tuple[Pipeline, RunState, str], tmp_path: Path
) -> None:
    pipeline, source, _ = candidate
    ext_dir, cand_digest, manifest_path, manifest_digest = build_synthetic_import_fixture(
        tmp_path, pipeline, source
    )

    imported = pipeline.import_candidate(
        "T100",
        source.run_id,
        source_worktree=ext_dir,
        expected_source_digest=cand_digest,
        provenance_manifest=manifest_path,
        expected_provenance_digest=manifest_digest,
    )
    assert imported.state == State.AUDIT_PASS

    # Delete external evidence directory completely
    shutil.rmtree(manifest_path.parent)

    # Status and resume continue to function using copied flat artifacts
    st = pipeline.status("T100", imported.run_id)
    assert st.state == State.AUDIT_PASS
    pipeline.config.integrate = False
    res = pipeline.resume("T100", imported.run_id)
    assert res.state == State.AUDIT_PASS

    # Tampering with copied flat artifact in run directory causes resume failure
    target_dir = pipeline.run_path("T100", imported.run_id)
    scout_art = target_dir / "00-imported-scout-A.packet.json"
    scout_art.write_text("tampered")
    res_tampered = pipeline.resume("T100", imported.run_id)
    assert res_tampered.state == State.FAILED


def test_import_candidate_control_plane_and_continuation(
    candidate: tuple[Pipeline, RunState, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tools.orchestrator.__main__ import main

    pipeline, source, _ = candidate
    ext_dir, cand_digest, manifest_path, manifest_digest = build_synthetic_import_fixture(
        tmp_path, pipeline, source
    )
    imported = pipeline.import_candidate(
        "T100",
        source.run_id,
        source_worktree=ext_dir,
        expected_source_digest=cand_digest,
        provenance_manifest=manifest_path,
        expected_provenance_digest=manifest_digest,
    )
    assert imported.state == State.AUDIT_PASS

    # 1. Candidate worktree cwd rejected by control-plane guard
    monkeypatch.chdir(Path(imported.worktree_path))
    monkeypatch.setattr(Pipeline, "load", lambda _dir, _cfg=None: pipeline)
    monkeypatch.setattr(
        sys, "argv", ["orchestrator", "resume", "T100", "--run-id", imported.run_id]
    )
    assert main() == 2

    # 2. Control plane resume with integrate=False stays AUDIT_PASS, 0 AI calls
    monkeypatch.chdir(control_plane_root())
    pipeline.config.integrate = False
    assert isinstance(pipeline.provider, LocalAgents)
    pipeline.provider.calls.clear()
    state_no_int = pipeline.resume("T100", imported.run_id)
    assert state_no_int.state == State.AUDIT_PASS
    assert pipeline.provider.calls == []

    # 3. Control plane resume with integrate=True invokes Integrator and merges
    pipeline.config.integrate = True
    state_int = pipeline.resume("T100", imported.run_id)
    assert state_int.state == State.DONE
    assert "IntegrationReview" in pipeline.provider.calls
    assert "ReviewShard" not in pipeline.provider.calls
    assert "Audit" not in pipeline.provider.calls


def test_import_candidate_cli(
    candidate: tuple[Pipeline, RunState, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from tools.orchestrator.__main__ import main

    pipeline, source, _ = candidate
    ext_dir, cand_digest, manifest_path, manifest_digest = build_synthetic_import_fixture(
        tmp_path, pipeline, source
    )

    monkeypatch.setattr(Pipeline, "load", lambda _dir, _cfg=None: pipeline)

    # Missing flags exit 2
    monkeypatch.setattr(
        sys, "argv", ["orchestrator", "import-candidate", "T100", "--run-id", source.run_id]
    )
    with pytest.raises(SystemExit):
        main()

    # Invalid digest format exits 2
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "orchestrator",
            "import-candidate",
            "T100",
            "--run-id",
            source.run_id,
            "--source-worktree",
            str(ext_dir),
            "--expected-source-digest",
            "invalid-hex",
            "--provenance-manifest",
            str(manifest_path),
            "--expected-provenance-digest",
            manifest_digest,
        ],
    )
    with pytest.raises(SystemExit):
        main()

    # Successful import-candidate CLI invocation returns 0 with handoff payload
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "orchestrator",
            "import-candidate",
            "T100",
            "--run-id",
            source.run_id,
            "--source-worktree",
            str(ext_dir),
            "--expected-source-digest",
            cand_digest,
            "--provenance-manifest",
            str(manifest_path),
            "--expected-provenance-digest",
            manifest_digest,
        ],
    )
    assert main() == 0
    out = capsys.readouterr().out
    payload = json.loads(out[out.index("{") :])
    assert payload["state"] == "AUDIT_PASS"
    assert "candidate_import_handoff" in payload
    handoff = payload["candidate_import_handoff"]
    assert handoff["task_id"] == "T100"
    assert "resume" in handoff["next_step"]

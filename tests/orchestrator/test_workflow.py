import json
import re
from multiprocessing.connection import Connection as PipeConnection
from multiprocessing.synchronize import Barrier
from pathlib import Path
from typing import Literal, TypeVar

import pytest
from pydantic import BaseModel
from tools.orchestrator.core import (
    Audit,
    Config,
    Contract,
    Criterion,
    Fix,
    IntegrationReview,
    OrchestratorError,
    Plan,
    Role,
    RunState,
    State,
    WorkerResult,
    atomic_json,
    digest,
    read_json,
    task_card,
)
from tools.orchestrator.runtime import Git, lock
from tools.orchestrator.workflow import Pipeline

Output = TypeVar("Output", bound=BaseModel)


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    git = Git(repo)
    git.run("init", "-b", "main")
    git.run("config", "user.email", "fixture@example.invalid")
    git.run("config", "user.name", "Fixture")
    (repo / "tasks").mkdir()
    (repo / "docs").mkdir()
    (repo / ".gitignore").write_text(".agent-runs/\n.pytest_cache/\n__pycache__/\n")
    (repo / "feature.txt").write_text("good\n")
    (repo / "docs/changelogs.md").write_text("Historical entry\n")
    (repo / "test_app.py").write_text(
        "from pathlib import Path\ndef test_behavior():\n"
        "    assert Path('feature.txt').read_text().strip() == 'good'\n"
    )
    (repo / "tasks/t100-fixture.md").write_text("""# T100
**Task ID:** `T100`
**Title:** Synthetic feature
**Status:** `PENDING`
**Goal:** Preserve good behavior.
## Dependencies
- None
## Files được phép sửa
- `feature.txt`
## Acceptance criteria
- [ ] The behavior is good.
## Verification commands
```text
python -m pytest test_app.py -q
```
""")
    git.run("add", ".")
    git.run("commit", "-m", "fixture")
    return repo


def configuration(*, integrate: bool = True, cycles: int = 3) -> Config:
    return Config(
        roles={
            name: Role(provider="codex", executable="fake-codex")
            for name in ("prompt_engineer", "worker", "auditor", "integrator")
        },
        verification=[["python", "-m", "pytest", "test_app.py", "-q"]],
        timeout_seconds=30,
        integrate=integrate,
        max_fix_cycles=cycles,
    )


class FakeAgents:
    def __init__(self, *, failures: int = 0, lie: bool = False) -> None:
        self.calls: list[str] = []
        self.failures = failures
        self.lie = lie
        self.worker_calls = 0

    def run(
        self,
        prompt: str,
        *,
        cwd: Path,
        role: Role,
        timeout: int,
        output: type[Output],
        artifacts: Path,
        name: str,
        readonly: bool,
    ) -> Output:
        assert role.executable == "fake-codex"
        assert timeout == 30
        assert artifacts.is_dir()
        assert name
        self.calls.append(output.__name__)
        task_match = re.search(r'"task_id": "(T[0-9]{3})"', prompt)
        assert task_match is not None
        task_id = task_match[1]
        card = task_card(cwd, task_id)
        result: BaseModel
        if output == Plan:
            matched = re.search(r"MAX_FIX_CYCLES: (\d+)", prompt)
            assert matched is not None
            result = Plan(
                contract=Contract(
                    schema_version=1,
                    task_id=task_id,
                    title=card.title,
                    objective=card.objective,
                    dependencies=[],
                    base_sha=Git(cwd).sha(),
                    allowed_paths=card.allowed_paths,
                    forbidden_paths=[],
                    acceptance_criteria=card.acceptance_criteria,
                    required_verification=card.required_verification,
                    risk_level="medium",
                    forbidden_scope=card.forbidden_scope,
                    stop_conditions=card.stop_conditions,
                    max_fix_cycles=int(matched[1]),
                ),
                worker_prompt="Implement only the task and preserve good behavior.",
            )
        elif output == WorkerResult:
            assert not readonly
            self.worker_calls += 1
            feature = "feature.txt" if task_id == "T100" else f"feature-{task_id}.txt"
            (cwd / feature).write_text("bad" if self.worker_calls <= self.failures else "good")
            (cwd / "docs/changelogs.md").write_text("New synthetic entry\nHistorical entry\n")
            result = WorkerResult(
                status="IMPLEMENTED",
                summary="Synthetic implementation",
                changed_files=Git(cwd).paths(Git(cwd).sha()),
                commands_run=[],
                known_issues=[],
            )
        elif output == Audit:
            assert readonly
            passing = self.lie or self.worker_calls > self.failures
            status: Literal["PASS", "FAIL"] = "PASS" if passing else "FAIL"
            result = Audit(
                status=status,
                findings=[] if passing else ["Behavior is bad"],
                acceptance_criteria=[
                    Criterion(
                        criterion=card.acceptance_criteria[0],
                        status=status,
                        evidence="Inspected fixture and executable test",
                    )
                ],
                scope_violations=[],
                required_fixes=[] if passing else ["Restore good behavior"],
            )
        elif output == Fix:
            result = Fix(fix_prompt="Restore good behavior; keep contract unchanged.")
        elif output == IntegrationReview:
            matched = re.search(r"SOURCE_BRANCH: ([^\n]+)", prompt)
            assert matched is not None
            result = IntegrationReview(
                status="READY", source_branch=matched[1], target_branch="main", findings=[]
            )
        else:
            raise AssertionError("Unexpected role")
        return output.model_validate(result.model_dump())


def test_no_agent_run_without_valid_config(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        Pipeline.load(tmp_path, tmp_path / "missing.json")


def test_interrupted_worker_never_replays() -> None:
    assert Pipeline.resumable(State.WORKER_RUNNING) is False
    assert Pipeline.resumable(State.AUDIT_PASS) is True


@pytest.mark.parametrize("failures", [0, 1])
def test_real_git_pipeline_pass_and_fix(repository: Path, failures: int) -> None:
    agents = FakeAgents(failures=failures)
    pipeline = Pipeline(repository, configuration(), agents)
    initial = Git(repository).sha()
    state = pipeline.start("T100")
    assert state.state == State.DONE
    assert state.fix_cycle == failures
    assert state.integrated_sha == Git(repository).sha() != initial
    assert Git(repository).clean()
    assert (repository / "feature.txt").read_text() == "good"
    assert agents.calls == (
        ["Plan", "WorkerResult", "Audit"]
        + (["Fix", "WorkerResult", "Audit"] if failures else [])
        + ["IntegrationReview"]
    )
    directory = pipeline.run_path("T100", state.run_id)
    report = read_json(directory / state.artifacts["integration_report"])
    assert isinstance(report, dict) and report["status"] == "MERGED"
    assert pipeline.resume("T100", state.run_id).state == State.DONE


def test_fix_limit_blocks_without_promoting(repository: Path) -> None:
    initial = Git(repository).sha()
    agents = FakeAgents(failures=5)
    pipeline = Pipeline(repository, configuration(cycles=1), agents)
    state = pipeline.start("T100")
    assert state.state == State.BLOCKED
    assert state.fix_cycle == 1
    assert "Maximum fix" in (state.last_error or "")
    assert Git(repository).sha() == initial
    assert "IntegrationReview" not in agents.calls
    assert (pipeline.run_path("T100") / "final_report.md").exists()


def test_failed_test_cannot_be_audit_pass(repository: Path) -> None:
    state = Pipeline(repository, configuration(), FakeAgents(failures=1, lie=True)).start("T100")
    assert state.state == State.BLOCKED
    assert "contradicts failed" in (state.last_error or "")


def test_integration_lock_pending_then_resume(repository: Path) -> None:
    agents = FakeAgents()
    pipeline = Pipeline(repository, configuration(), agents)
    with lock(pipeline.runs / ".locks/integration.lock"):
        state = pipeline.start("T100")
    assert state.state == State.AUDIT_PASS
    assert "IntegrationReview" not in agents.calls
    result = pipeline.resume("T100", state.run_id)
    assert result.state == State.DONE
    assert agents.calls.count("WorkerResult") == 1


def test_stale_audit_does_not_merge(repository: Path) -> None:
    pipeline = Pipeline(repository, configuration(), FakeAgents())
    with lock(pipeline.runs / ".locks/integration.lock"):
        state = pipeline.start("T100")
    (Path(state.worktree_path) / "feature.txt").write_text("changed after audit")
    result = pipeline.resume("T100", state.run_id)
    assert result.state == State.BLOCKED
    assert "evidence stale" in (result.last_error or "")


def test_dirty_base_never_stashes_or_resets(repository: Path) -> None:
    (repository / "user.txt").write_text("preserve")
    agents = FakeAgents()
    pipeline = Pipeline(repository, configuration(), agents)
    result = pipeline.start("T100")
    assert result.state == State.BLOCKED
    assert (repository / "user.txt").read_text() == "preserve"
    assert agents.calls == []


def test_dry_run_creates_no_artifacts_or_worktree(repository: Path) -> None:
    agents = FakeAgents()
    pipeline = Pipeline(repository, configuration(), agents)
    result = pipeline.start("T100", dry_run=True)
    assert result.state == State.PENDING
    assert not pipeline.runs.exists()
    assert not pipeline.worktrees.exists()
    assert agents.calls == []


def test_resume_interrupted_mutation_blocks(repository: Path) -> None:
    pipeline = Pipeline(repository, configuration(integrate=False), FakeAgents())
    state = pipeline.start("T100")
    state.state = State.WORKER_RUNNING
    directory = pipeline.run_path("T100")
    pipeline.save(directory, state)
    assert pipeline.resume("T100").state == State.BLOCKED


def test_contract_tamper_blocks_resume(repository: Path) -> None:
    pipeline = Pipeline(repository, configuration(), FakeAgents())
    with lock(pipeline.runs / ".locks/integration.lock"):
        state = pipeline.start("T100")
    directory = pipeline.run_path("T100")
    contract = Contract.model_validate(read_json(directory / state.artifacts["contract"]))
    contract.allowed_paths.append("user.txt")
    atomic_json(directory / state.artifacts["contract"], contract.model_dump())
    assert pipeline.resume("T100", state.run_id).state == State.BLOCKED


def test_hidden_staged_change_cannot_escape_scope(repository: Path) -> None:
    class HiddenIndex(FakeAgents):
        def run(
            self,
            prompt: str,
            *,
            cwd: Path,
            role: Role,
            timeout: int,
            output: type[Output],
            artifacts: Path,
            name: str,
            readonly: bool,
        ) -> Output:
            result = super().run(
                prompt,
                cwd=cwd,
                role=role,
                timeout=timeout,
                output=output,
                artifacts=artifacts,
                name=name,
                readonly=readonly,
            )
            if output == WorkerResult:
                (cwd / "test_app.py").write_text("def test_behavior(): pass\n")
                Git(cwd).run("add", "test_app.py")
                (cwd / "test_app.py").write_text((repository / "test_app.py").read_text())
            return result

    initial = Git(repository).sha()
    result = Pipeline(repository, configuration(), HiddenIndex()).start("T100")
    assert result.state == State.BLOCKED
    assert "BLOCKED_FOR_SCOPE_EXTENSION: test_app.py" in (result.last_error or "")
    assert Git(repository).sha() == initial


def test_source_change_between_checks_and_audit_blocks(repository: Path) -> None:
    class Race(Pipeline):
        def invoke(
            self,
            directory: Path,
            state: RunState,
            role_name: str,
            output: type[BaseModel],
            context: str,
            *,
            cwd: Path | None = None,
        ) -> BaseModel:
            if role_name == "auditor":
                (Path(state.worktree_path) / "feature.txt").write_text("bad")
            return super().invoke(directory, state, role_name, output, context, cwd=cwd)

    result = Race(repository, configuration(), FakeAgents()).start("T100")
    assert result.state == State.BLOCKED
    assert "between verification and audit" in (result.last_error or "")


def test_disjoint_main_advance_is_verified_before_promotion(repository: Path) -> None:
    agents = FakeAgents()
    pipeline = Pipeline(repository, configuration(), agents)
    with lock(pipeline.locks / "integration.lock"):
        state = pipeline.start("T100")
    (repository / "unrelated.txt").write_text("preserve independent integration\n")
    Git(repository).run("add", "unrelated.txt")
    Git(repository).run("commit", "-m", "independent change")
    result = pipeline.resume("T100", state.run_id)
    assert result.state == State.DONE
    assert (repository / "unrelated.txt").read_text() == "preserve independent integration\n"
    assert agents.calls.count("WorkerResult") == 1


def test_no_integrate_resume_still_rejects_stale_evidence(repository: Path) -> None:
    pipeline = Pipeline(repository, configuration(integrate=False), FakeAgents())
    state = pipeline.start("T100")
    assert state.state == State.AUDIT_PASS
    (Path(state.worktree_path) / "feature.txt").write_text("bad")
    result = pipeline.resume("T100", state.run_id)
    assert result.state == State.BLOCKED
    assert "evidence stale" in (result.last_error or "")


def test_global_integration_lock_ignores_custom_run_directory(repository: Path) -> None:
    config = configuration()
    config.paths.run_dir = ".agent-runs/alternate"
    pipeline = Pipeline(repository, config, FakeAgents())
    with lock(repository / ".agent-runs/.locks/integration.lock"):
        result = pipeline.start("T100")
    assert result.state == State.AUDIT_PASS
    assert pipeline.resume("T100").state == State.DONE


def test_contract_risk_and_stop_rules_cannot_be_downgraded(repository: Path) -> None:
    class Downgrade(FakeAgents):
        def run(
            self,
            prompt: str,
            *,
            cwd: Path,
            role: Role,
            timeout: int,
            output: type[Output],
            artifacts: Path,
            name: str,
            readonly: bool,
        ) -> Output:
            result = super().run(
                prompt,
                cwd=cwd,
                role=role,
                timeout=timeout,
                output=output,
                artifacts=artifacts,
                name=name,
                readonly=readonly,
            )
            if isinstance(result, Plan):
                result.contract.risk_level = "low"
            return result

    agents = Downgrade()
    result = Pipeline(repository, configuration(), agents).start("T100")
    assert result.state == State.BLOCKED
    assert "WorkerResult" not in agents.calls
    assert (Path(result.worktree_path) / "feature.txt").read_text() == "good\n"


def _concurrent_run(repo: str, task: str, barrier: Barrier, connection: PipeConnection) -> None:
    class Synchronized(FakeAgents):
        def run(
            self,
            prompt: str,
            *,
            cwd: Path,
            role: Role,
            timeout: int,
            output: type[Output],
            artifacts: Path,
            name: str,
            readonly: bool,
        ) -> Output:
            if output == Plan:
                barrier.wait(timeout=30)
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

    try:
        pipeline = Pipeline(Path(repo), configuration(integrate=False), Synchronized())
        result = pipeline.start(task)
        connection.send(result.model_dump(mode="json"))
    finally:
        connection.close()


def test_three_independent_processes_isolate_runs(repository: Path) -> None:
    import multiprocessing

    for task in ("T101", "T102", "T103"):
        (repository / f"feature-{task}.txt").write_text("good\n")
        card = (repository / "tasks/t100-fixture.md").read_text()
        (repository / f"tasks/{task.lower()}-fixture.md").write_text(
            card.replace("T100", task).replace("feature.txt", f"feature-{task}.txt")
        )
    git = Git(repository)
    git.run("add", ".")
    git.run("commit", "-m", "independent fixtures")
    initial = git.sha()
    ctx = multiprocessing.get_context("spawn")
    barrier = ctx.Barrier(3)
    records = []
    processes = []
    for task in ("T101", "T102", "T103"):
        parent, child = ctx.Pipe()
        process = ctx.Process(target=_concurrent_run, args=(str(repository), task, barrier, child))
        process.start()
        processes.append(process)
        records.append(parent)
        child.close()
    try:
        results = []
        for connection in records:
            assert connection.poll(60)
            results.append(connection.recv())
        for process in processes:
            process.join(30)
            assert process.exitcode == 0
        assert all(result["state"] == "AUDIT_PASS" for result in results)
        assert len({result["worktree_path"] for result in results}) == 3
        assert len({result["worktree_branch"] for result in results}) == 3
        assert len({result["run_id"] for result in results}) == 3
        assert all(result["base_sha"] == initial for result in results)
        assert git.sha() == initial
        assert git.clean()
        for result in results:
            directory = repository / ".agent-runs" / result["task_id"] / result["run_id"]
            assert (directory / "state.json").exists()
            assert list(directory.glob("*prompt.md"))
            assert result["artifacts"]["contract"]
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
            process.join(10)
        for connection in records:
            connection.close()


def test_cli_dry_run_status_and_validation(
    repository: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import sys

    from tools.orchestrator.__main__ import main

    pipeline = Pipeline(repository, configuration(integrate=False), FakeAgents())
    monkeypatch.setattr(Pipeline, "load", lambda _directory, _config=None: pipeline)
    for arguments, expected in [
        (["run", "T100", "--dry-run", "--no-integrate"], 0),
        (["run", "T100", "--run-id", "forbidden"], 2),
        (["status", "T100"], 2),
        (["resume", "T100", "--dry-run"], 2),
        (["run", "T100", "--integrate"], 0),
        (["status", "T100"], 0),
        (["resume", "T100"], 0),
    ]:
        monkeypatch.setattr(sys, "argv", ["orchestrator", *arguments])
        assert main() == expected
    assert "DONE" in capsys.readouterr().out


def test_snapshot_artifact_tamper_blocks_resume(repository: Path) -> None:
    pipeline = Pipeline(repository, configuration(integrate=False), FakeAgents())
    state = pipeline.start("T100")
    directory = pipeline.run_path("T100")
    path = directory / state.artifacts["task_card"]
    data = read_json(path)
    assert isinstance(data, dict)
    data["allowed_paths"].append("user.txt")
    atomic_json(path, data)
    result = pipeline.resume("T100")
    assert result.state == State.BLOCKED
    assert "artifact changed" in (result.last_error or "")


def test_incomplete_resumable_state_blocks_without_traceback(repository: Path) -> None:
    pipeline = Pipeline(repository, configuration(integrate=False), FakeAgents())
    state = pipeline.start("T100")
    state.artifacts = {}
    pipeline.save(pipeline.run_path("T100"), state)
    result = pipeline.resume("T100")
    assert result.state == State.BLOCKED
    assert "Incomplete state" in (result.last_error or "")


def test_worker_prompt_tamper_prevents_implementation(repository: Path) -> None:
    class Tamper(Pipeline):
        def move(self, directory: Path, state: RunState, destination: State) -> None:
            super().move(directory, state, destination)
            if destination == State.PROMPT_READY:
                (directory / "worker_prompt.md").write_text("Change unrelated product behavior")

    agents = FakeAgents()
    result = Tamper(repository, configuration(), agents).start("T100")
    assert result.state == State.BLOCKED
    assert "Worker prompt changed" in (result.last_error or "")
    assert "WorkerResult" not in agents.calls


def test_symlinked_global_lock_root_rejected(repository: Path) -> None:
    other = repository.parent / "redirect"
    other.mkdir()
    (repository / ".agent-runs").symlink_to(other, target_is_directory=True)
    config = configuration()
    config.paths.run_dir = ".custom-runs"
    with pytest.raises(ValueError, match="symlinks"):
        Pipeline(repository, config, FakeAgents())


def test_native_windows_promotion_refuses_unverified_recovery(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initial = Git(repository).sha()
    monkeypatch.setattr("tools.orchestrator.workflow.sys.platform", "win32")
    result = Pipeline(repository, configuration(), FakeAgents()).start("T100")
    assert result.state == State.BLOCKED
    assert "ENVIRONMENT_BLOCKED" in (result.last_error or "")
    assert Git(repository).sha() == initial


def test_lock_failure_after_integration_started_is_not_pending(repository: Path) -> None:
    from tools.orchestrator.core import Contract
    from tools.orchestrator.runtime import LockBusy

    class InterruptedIntegration(Pipeline):
        def integrate(self, directory: Path, state: RunState, contract: Contract) -> None:
            assert contract.task_id == state.task_id
            self.move(directory, state, State.INTEGRATION_RUNNING)
            raise LockBusy("Worktree creation lock remained busy")

    initial = Git(repository).sha()
    result = InterruptedIntegration(repository, configuration(), FakeAgents()).start("T100")
    assert result.state == State.BLOCKED
    assert "Worktree creation lock remained busy" in (result.last_error or "")
    assert Git(repository).sha() == initial


class PlanningProbe(FakeAgents):
    def __init__(self, mode: str) -> None:
        super().__init__()
        self.mode = mode

    def run(
        self,
        prompt: str,
        *,
        cwd: Path,
        role: Role,
        timeout: int,
        output: type[Output],
        artifacts: Path,
        name: str,
        readonly: bool,
    ) -> Output:
        result = super().run(
            prompt,
            cwd=cwd,
            role=role,
            timeout=timeout,
            output=output,
            artifacts=artifacts,
            name=name,
            readonly=readonly,
        )
        if isinstance(result, Plan):
            if self.mode == "template":
                marker = "CONTRACT TEMPLATE JSON:\n"
                assert marker in prompt, "Planner was not supplied a literal contract template"
                template, _ = json.JSONDecoder().raw_decode(prompt.split(marker, 1)[1])
                result.contract = Contract.model_validate(template)
                card = task_card(cwd, "T100")
                assert result.contract.objective == card.objective
                assert result.contract.forbidden_scope == card.forbidden_scope
                assert result.contract.stop_conditions == card.stop_conditions
                assert result.contract.forbidden_paths == []
                assert "Do not paraphrase" in prompt
                assert "glob" in prompt
                assert "read-only planning sandbox" in prompt
            elif self.mode == "drift":
                result.contract.objective = "PRIVATE SENTINEL changed objective"
                result.contract.forbidden_scope = "PRIVATE SENTINEL changed forbidden scope"
                result.contract.stop_conditions = "PRIVATE SENTINEL changed stop conditions"
            elif self.mode == "notes":
                result.worker_prompt = (
                    "Record inherited verification concerns as notes; implement the task."
                )
            elif self.mode == "glob":
                result.contract.forbidden_paths = ["private-sentinel/**"]
        return result


def test_planner_receives_and_consumes_exact_contract_template(repository: Path) -> None:
    card = repository / "tasks/t100-fixture.md"
    card.write_text(
        card.read_text().replace("Preserve good behavior.", "Preserve temp→fsync→replace.")
        + "\n## Files không được sửa\n- Nội dung riêng tư; không mở rộng phạm vi.\n"
        + "\n## Stop conditions\n- Thiếu Windows proof → pending, not pass.\n"
    )
    Git(repository).run("add", str(card))
    Git(repository).run("commit", "-m", "synthetic unicode constraints")
    agents = PlanningProbe("template")
    pipeline = Pipeline(repository, configuration(integrate=False), agents)
    state = pipeline.start("T100")
    assert state.state == State.AUDIT_PASS
    assert agents.calls == ["Plan", "WorkerResult", "Audit"]
    frozen = pipeline.contract(pipeline.run_path("T100", state.run_id), state)
    assert frozen.stop_conditions == task_card(repository, "T100").stop_conditions


def test_planning_drift_lists_field_names_without_private_text(repository: Path) -> None:
    agents = PlanningProbe("drift")
    state = Pipeline(repository, configuration(), agents).start("T100")
    assert state.state == State.BLOCKED
    error = state.last_error or ""
    for field in ["objective", "forbidden_scope", "stop_conditions"]:
        assert field in error
    assert "PRIVATE SENTINEL" not in error
    assert agents.calls == ["Plan"]
    assert state.contract_digest == ""
    assert state.implementation_sha is None


@pytest.mark.parametrize("mode", ["notes", "glob"])
def test_planning_notes_do_not_veto_but_exact_paths_still_apply(
    repository: Path, mode: str
) -> None:
    agents = PlanningProbe(mode)
    state = Pipeline(repository, configuration(integrate=False), agents).start("T100")
    error = state.last_error or ""
    if mode == "notes":
        assert state.state == State.AUDIT_PASS
        assert agents.calls == ["Plan", "WorkerResult", "Audit"]
    else:
        assert state.state == State.BLOCKED
        assert "forbidden_paths[0]" in error
        assert "private-sentinel" not in error
        assert agents.calls == ["Plan"]
    assert state.implementation_sha is None


def test_retry_preserves_failed_run_and_creates_fresh_worktree(repository: Path) -> None:
    pipeline = Pipeline(repository, configuration(integrate=False), PlanningProbe("drift"))
    old = pipeline.start("T100")
    old_directory = pipeline.run_path("T100", old.run_id)
    evidence = {p.name: p.read_bytes() for p in old_directory.iterdir() if p.is_file()}
    old_tree = Path(old.worktree_path)
    original_head = Git(old_tree).sha()
    (repository / "independent.txt").write_text("Independent base advance\n")
    Git(repository).run("add", "independent.txt")
    Git(repository).run("commit", "-m", "independent local base advance")
    pipeline.provider = FakeAgents()
    result = pipeline.retry("T100", old.run_id)
    assert result.state == State.AUDIT_PASS
    assert result.retry_of == old.run_id
    assert result.run_id != old.run_id
    assert result.base_sha == Git(repository).sha()
    assert result.worktree_path != old.worktree_path
    assert result.worktree_branch != old.worktree_branch
    assert old_tree.is_dir() and Git(old_tree).sha() == original_head
    assert evidence == {p.name: p.read_bytes() for p in old_directory.iterdir() if p.is_file()}
    assert pipeline.status("T100", old.run_id).state == State.BLOCKED


def test_duplicate_run_refuses_without_creating_empty_run(repository: Path) -> None:
    pipeline = Pipeline(repository, configuration(integrate=False), PlanningProbe("drift"))
    old = pipeline.start("T100")
    before = sorted((pipeline.runs / "T100").iterdir())
    with pytest.raises(OrchestratorError, match="retry"):
        pipeline.start("T100")
    assert sorted((pipeline.runs / "T100").iterdir()) == before
    assert pipeline.status("T100").run_id == old.run_id


def test_retry_default_ignores_legacy_empty_duplicate_record(repository: Path) -> None:
    pipeline = Pipeline(repository, configuration(integrate=False), PlanningProbe("drift"))
    old = pipeline.start("T100")
    empty = RunState(
        task_id="T100",
        run_id="zz-legacy-duplicate",
        state=State.BLOCKED,
        base_sha=old.base_sha,
        repository=str(repository),
        worktree_path=str(pipeline.worktrees / "T100-zz-legacy-duplicate"),
        worktree_branch="agent/T100-zz-legacy-duplicate",
        last_error="Task already has a worktree",
    )
    pipeline.save(pipeline.run_path("T100", empty.run_id), empty)
    pipeline.provider = FakeAgents()
    result = pipeline.retry("T100")
    assert result.state == State.AUDIT_PASS
    assert result.retry_of == old.run_id
    assert pipeline.status("T100", empty.run_id).artifacts == {}


@pytest.mark.parametrize("unsafe", ["worker", "dirty", "history", "artifact", "active"])
def test_retry_refuses_unsafe_run(repository: Path, unsafe: str) -> None:
    agents = FakeAgents(failures=1) if unsafe == "worker" else PlanningProbe("drift")
    pipeline = Pipeline(repository, configuration(integrate=False, cycles=0), agents)
    old = pipeline.start("T100")
    old_directory = pipeline.run_path("T100", old.run_id)
    tree = Path(old.worktree_path)
    if unsafe in {"dirty", "history"}:
        (tree / "feature.txt").write_text("Preserve user change\n")
        if unsafe == "history":
            Git(tree).run("add", "feature.txt")
            Git(tree).run("commit", "-m", "preserve user commit")
    elif unsafe == "artifact":
        (old_directory / old.artifacts["plan"]).write_text("Tampered synthetic report")
    elif unsafe == "active":
        old.current_agent = "worker"
        pipeline.save(old_directory, old)
    evidence = (old_directory / "state.json").read_bytes()
    branches = Git(repository).run("for-each-ref", "--format=%(refname)", "refs/heads")
    with pytest.raises(OrchestratorError):
        pipeline.retry("T100", old.run_id)
    assert (old_directory / "state.json").read_bytes() == evidence
    assert Git(repository).run("for-each-ref", "--format=%(refname)", "refs/heads") == branches
    assert tree.is_dir()
    if unsafe in {"dirty", "history"}:
        assert (tree / "feature.txt").read_text() == "Preserve user change\n"


def test_retry_cannot_adopt_unmanaged_task_worktree(repository: Path) -> None:
    pipeline = Pipeline(repository, configuration(integrate=False), PlanningProbe("drift"))
    old = pipeline.start("T100")
    unmanaged = repository.parent / "manual-worktree"
    Git(repository).create_worktree(unmanaged, "task/T100-manual", old.base_sha)
    with pytest.raises(OrchestratorError, match="managed"):
        pipeline.retry("T100", old.run_id)
    assert unmanaged.is_dir()
    assert Git(unmanaged).branch() == "task/T100-manual"


def test_cli_retry_uses_explicit_run_id(repository: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    from tools.orchestrator.__main__ import main

    pipeline = Pipeline(repository, configuration(integrate=False), PlanningProbe("drift"))
    old = pipeline.start("T100")
    pipeline.provider = FakeAgents()
    monkeypatch.setattr(Pipeline, "load", lambda _directory, _config_path: pipeline)
    monkeypatch.setattr(
        sys, "argv", ["orchestrator", "retry", "T100", "--run-id", old.run_id, "--no-integrate"]
    )
    assert main() == 0
    states = [
        pipeline.status("T100", p.parent.name)
        for p in (pipeline.runs / "T100").glob("*/state.json")
    ]
    retried = [state for state in states if state.run_id != old.run_id]
    assert len(retried) == 1 and retried[0].retry_of == old.run_id
    assert retried[0].state == State.AUDIT_PASS


@pytest.mark.parametrize("legacy", [False, True])
def test_retry_rechecks_baseline_after_environment_repair(repository: Path, legacy: bool) -> None:
    config = configuration(integrate=False)
    config.verification = [["python", "-m", "pytest", "missing_test.py", "-q"]]
    agents = FakeAgents()
    pipeline = Pipeline(repository, config, agents)
    old = pipeline.start("T100")
    assert old.state == State.BLOCKED and agents.calls == []
    assert (old.last_error or "").startswith("INHERITED_BASELINE_FAILURE:")
    directory = pipeline.run_path("T100", old.run_id)
    if legacy:
        payload = old.model_dump(mode="json", exclude={"blocked_from", "retry_of"})
        atomic_json(directory / "state.json", payload)
    previous = (directory / "state.json").read_bytes()
    pipeline.config = configuration(integrate=False)
    retried = pipeline.retry("T100", old.run_id)
    assert retried.state == State.AUDIT_PASS
    assert "baseline" in retried.artifacts and retried.retry_of == old.run_id
    assert agents.calls == ["Plan", "WorkerResult", "Audit"]
    assert (directory / "state.json").read_bytes() == previous


def test_retry_refuses_tampered_historical_evidence(repository: Path) -> None:
    pipeline = Pipeline(repository, configuration(integrate=False), PlanningProbe("drift"))
    old = pipeline.start("T100")
    directory = pipeline.run_path("T100", old.run_id)
    historical = directory / "old-baseline.json"
    historical.write_text("Synthetic previous check\n")
    old.artifact_digests[historical.name] = digest(historical.read_bytes())
    pipeline.save(directory, old)
    historical.write_text("Changed previous check\n")
    pipeline.provider = FakeAgents()
    with pytest.raises(OrchestratorError, match="artifact"):
        pipeline.retry("T100", old.run_id)
    assert pipeline.provider.calls == []


def test_retry_refuses_live_run_lock_without_new_state(repository: Path) -> None:
    from tools.orchestrator.runtime import LockBusy

    pipeline = Pipeline(repository, configuration(integrate=False), PlanningProbe("drift"))
    old = pipeline.start("T100")
    directory = pipeline.run_path("T100", old.run_id)
    previous = (directory / "state.json").read_bytes()
    runs = sorted((pipeline.runs / "T100").iterdir())
    with lock(directory / ".run.lock"), pytest.raises(LockBusy):
        pipeline.retry("T100", old.run_id)
    assert sorted((pipeline.runs / "T100").iterdir()) == runs
    assert (directory / "state.json").read_bytes() == previous


@pytest.mark.parametrize("legacy_phase", [False, True])
def test_retry_legacy_planning_gate_uses_fresh_plan_and_preserves_evidence(
    repository: Path, legacy_phase: bool
) -> None:
    pipeline = Pipeline(repository, configuration(integrate=False), PlanningProbe("drift"))
    old = pipeline.start("T100")
    directory = pipeline.run_path("T100", old.run_id)
    path = directory / old.artifacts["plan"]
    plan = json.loads(path.read_text())
    plan["contract"]["human_gates"] = ["Legacy model veto about existing repository checks"]
    plan["worker_prompt"] = "Legacy prompt says BLOCKED; never replay this prompt."
    atomic_json(path, plan)
    old.artifact_digests[path.name] = digest(path.read_bytes())
    old.last_error = "Planning identified human gates; inspect plan"
    if legacy_phase:
        old.blocked_from = None
    pipeline.save(directory, old)
    preserved = {p.name: p.read_bytes() for p in directory.iterdir() if p.is_file()}
    agents = FakeAgents()
    pipeline.provider = agents
    result = pipeline.retry("T100", old.run_id)
    assert result.state == State.AUDIT_PASS
    assert result.retry_of == old.run_id
    assert agents.calls == ["Plan", "WorkerResult", "Audit"]
    assert (
        "human_gates"
        not in pipeline.contract(pipeline.run_path("T100", result.run_id), result).model_dump()
    )
    assert preserved == {p.name: p.read_bytes() for p in directory.iterdir() if p.is_file()}


def test_planning_respects_owner_configured_verification_authority(repository: Path) -> None:
    from tools.orchestrator.workflow import PLANNING_RULES, ROLE_RULES

    assert "repository-configured verification" in ROLE_RULES
    assert (
        "Do not access credentials, real provider inference, remote Git, "
        "or real user vocabulary data." not in ROLE_RULES
    )
    assert "human_gates" not in PLANNING_RULES
    assert "baseline checks have already passed" in PLANNING_RULES
    assert "invent human approval" in PLANNING_RULES
    agents = PlanningProbe("template")
    pipeline = Pipeline(repository, configuration(integrate=False), agents)
    result = pipeline.start("T100")
    assert result.state == State.AUDIT_PASS
    assert agents.calls == ["Plan", "WorkerResult", "Audit"]


def test_resume_legacy_prompt_ready_preserves_original_contract_and_plan(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    agents = FakeAgents()
    pipeline = Pipeline(repository, configuration(integrate=False), agents)
    original_move = Pipeline.move

    def pause(self: Pipeline, directory: Path, state: RunState, destination: State) -> None:
        original_move(self, directory, state, destination)
        if destination == State.PROMPT_READY:
            raise RuntimeError("Synthetic crash after a stable handoff")

    with monkeypatch.context() as context:
        context.setattr(Pipeline, "move", pause)
        with pytest.raises(RuntimeError, match="Synthetic crash"):
            pipeline.start("T100")
    old = pipeline.status("T100")
    assert old.state == State.PROMPT_READY and agents.calls == ["Plan"]
    directory = pipeline.run_path("T100", old.run_id)
    preserved = {}
    for key in ("contract", "plan"):
        path = directory / old.artifacts[key]
        payload = json.loads(path.read_text())
        if key == "contract":
            payload["human_gates"] = []
        else:
            payload["contract"]["human_gates"] = []
        atomic_json(path, payload)
        old.artifact_digests[path.name] = digest(path.read_bytes())
        preserved[path] = path.read_bytes()
        if key == "contract":
            old.contract_digest = digest(path.read_bytes())
    pipeline.save(directory, old)
    result = pipeline.resume("T100", old.run_id)
    assert result.state == State.AUDIT_PASS
    assert agents.calls == ["Plan", "WorkerResult", "Audit"]
    assert preserved == {p: p.read_bytes() for p in preserved}

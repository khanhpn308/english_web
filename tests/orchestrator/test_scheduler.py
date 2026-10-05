import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Event, Lock
from typing import TypeVar

import pytest
from pydantic import BaseModel
from tools.orchestrator import scheduler
from tools.orchestrator.__main__ import main
from tools.orchestrator.core import (
    Audit,
    Config,
    Criterion,
    IntegrationReview,
    OrchestratorError,
    Plan,
    ReviewBundle,
    ReviewPerspective,
    ReviewShard,
    Role,
    State,
    WorkerResult,
    read_json,
    task_card,
)
from tools.orchestrator.runtime import Git, LockBusy, lock
from tools.orchestrator.scheduler import Outcome, Scheduler, discover, resolve
from tools.orchestrator.workflow import Pipeline

Output = TypeVar("Output", bound=BaseModel)


class SyntheticProvider:
    """Picklable fake exercising the actual spawned Pipeline, without a CLI/model."""

    def __init__(self, fail_task: str | None = None) -> None:
        self.fail_task = fail_task

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
        assert role.executable == "never-call-a-model"
        assert timeout is None and artifacts.is_dir() and name
        result: BaseModel
        if output == Plan:
            if artifacts.parent.name == self.fail_task:
                raise OrchestratorError("Synthetic planning failure")
            template, _tail = json.JSONDecoder().raw_decode(
                prompt.split("CONTRACT TEMPLATE JSON:\n", 1)[1]
            )
            result = Plan(contract=template, worker_prompt="Implement the synthetic behavior.")
        elif output == WorkerResult:
            assert not readonly
            task = artifacts.parent.name
            (cwd / f"feature-{task}.txt").write_text("synthetic behavior\n")
            path = cwd / "tasks" / f"{task.lower()}-fixture.md"
            path.write_text(path.read_text().replace("`PENDING`", "`DONE`"))
            changelog = cwd / "docs/changelogs.md"
            changelog.write_text(f"{task} synthetic entry\n" + changelog.read_text())
            result = WorkerResult(
                status="IMPLEMENTED",
                summary="Synthetic task complete",
                changed_files=Git(cwd).paths(Git(cwd).sha()),
                commands_run=[],
                known_issues=[],
            )
        elif output == ReviewShard:
            assert readonly
            matched = re.search(r"REVIEW_PERSPECTIVE: ([^\n]+)", prompt)
            assert matched is not None
            result = ReviewShard(perspective=ReviewPerspective(matched[1]), findings=[])
        elif output == Audit:
            assert readonly
            result = Audit(
                status="PASS",
                findings=[],
                acceptance_criteria=[
                    Criterion(
                        criterion="Synthetic behavior.",
                        status="PASS",
                        evidence="Inspected synthetic implementation and verification",
                    )
                ],
                scope_violations=[],
                required_fixes=[],
            )
        elif output == IntegrationReview:
            matched = re.search(r"SOURCE_BRANCH: ([^\n]+)", prompt)
            assert matched is not None and readonly
            result = IntegrationReview(
                status="READY", source_branch=matched[1], target_branch="main", findings=[]
            )
        else:
            raise AssertionError("Unexpected synthetic role")
        return output.model_validate(result.model_dump())


def synthetic_setup(pipeline: Pipeline) -> None:
    (pipeline.repository / "docs").mkdir()
    (pipeline.repository / "docs/changelogs.md").write_text("Historical entry\n")
    for name in (
        "incremental-implementation",
        "test-driven-development",
        "git-workflow-and-versioning",
        "documentation-and-adrs",
        "code-review-and-quality",
        "debugging-and-error-recovery",
    ):
        path = pipeline.repository / ".agents/skills" / name / "SKILL.md"
        path.parent.mkdir(parents=True)
        path.write_text(f"---\nname: {name}\n---\nSynthetic workflow.\n")
    pipeline.config.skills_root = ".agents/skills"
    pipeline.provider = SyntheticProvider()


def card(repo: Path, task: str, deps: tuple[str, ...] = (), status: str = "PENDING") -> Path:
    path = repo / "tasks" / f"{task.lower()}-fixture.md"
    path.parent.mkdir(exist_ok=True)
    path.write_text(
        f"# {task}: Synthetic task\n**Task ID:** `{task}`\n"
        f"**Title:** Synthetic task\n**Status:** `{status}`\n**Goal:** Synthetic behavior.\n"
        "## Dependencies\n"
        + ("\n".join(f"- {dep}" for dep in deps) if deps else "- None")
        + f"\n## Files được phép sửa\n- `feature-{task}.txt`\n"
        "## Acceptance criteria\n- [x] Synthetic behavior.\n"
        "## Verification commands\n```text\ngit diff --check\n```\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def pipeline(tmp_path: Path) -> Pipeline:
    repo = tmp_path / "repo"
    repo.mkdir()
    git = Git(repo)
    git.run("init", "-b", "main")
    git.run("config", "user.email", "fixture@example.invalid")
    git.run("config", "user.name", "Fixture")
    (repo / ".gitignore").write_text(".agent-runs/\n")
    card(repo, "T100")
    git.run("add", ".")
    git.run("commit", "-m", "synthetic fixture")
    return Pipeline(
        repo,
        Config(
            roles={
                name: Role(provider="codex", executable="never-call-a-model")
                for name in ("prompt_engineer", "worker", "auditor", "integrator")
            },
            verification=[["git", "diff", "--check"]],
        ),
    )


def commit(pipeline: Pipeline) -> None:
    pipeline.git.run("add", ".")
    pipeline.git.run("commit", "-m", "synthetic graph update")


@pytest.mark.parametrize(
    "edges,done,ready,blocked",
    [
        ({"T100": (), "T101": ("T100",), "T102": ("T101",)}, (), ["T100"], ["T101", "T102"]),
        ({"T100": (), "T101": ("T100",), "T102": ("T100",)}, (), ["T100"], ["T101", "T102"]),
        ({"T100": (), "T101": (), "T102": ("T100", "T101")}, (), ["T100", "T101"], ["T102"]),
        ({"T100": (), "T101": ("T100",)}, ("T100",), ["T101"], []),
        ({"T102": (), "T101": (), "T100": ()}, (), ["T100", "T101", "T102"], []),
    ],
)
def test_graph_shapes(
    tmp_path: Path,
    edges: dict[str, tuple[str, ...]],
    done: tuple[str, ...],
    ready: list[str],
    blocked: list[str],
) -> None:
    for task, deps in edges.items():
        card(tmp_path, task, deps, "DONE" if task in done else "PENDING")
    graph = resolve(discover(tmp_path))
    assert graph.done == list(done)
    assert graph.ready == ready
    assert list(graph.blocked) == blocked
    for task in blocked:
        assert graph.blocked[task] == [
            f"{dep}: PENDING" for dep in sorted(edges[task]) if dep not in done
        ]
    assert graph.tasks["T100"].title == "Synthetic task"


@pytest.mark.parametrize("status", ["BLOCKED", "FAILED", "IMPLEMENTATION_DONE_BASELINE_BLOCKED"])
def test_blocked_dependency_and_own_status(tmp_path: Path, status: str) -> None:
    card(tmp_path, "T100", status=status)
    card(tmp_path, "T101", ("T100",))
    graph = resolve(discover(tmp_path))
    assert graph.ready == []
    assert status in graph.blocked["T100"][0]
    assert graph.blocked["T101"] == [f"T100: {status}"]


@pytest.mark.parametrize(
    "edges,error",
    [
        ({"T100": ("T999",)}, "Missing dependency: T100 -> T999"),
        ({"T100": ("T100",)}, "Self dependency: T100"),
        ({"T100": ("T101",), "T101": ("T100",)}, "Dependency cycle"),
        ({"T100": ("T101",), "T101": ("T102",), "T102": ("T100",)}, "Dependency cycle"),
    ],
)
def test_invalid_graph_fails_closed(
    tmp_path: Path, edges: dict[str, tuple[str, ...]], error: str
) -> None:
    for task, deps in edges.items():
        card(tmp_path, task, deps)
    with pytest.raises(OrchestratorError, match=error):
        resolve(discover(tmp_path))


def test_duplicate_done_ids_fail_closed(tmp_path: Path) -> None:
    original = card(tmp_path, "T100", status="DONE")
    (original.parent / "t100-duplicate.md").write_text(original.read_text())
    with pytest.raises(OrchestratorError, match="Duplicate task IDs: T100"):
        discover(tmp_path)


@pytest.mark.parametrize("replacement", ["**Status:** ???", "**Task ID:** `T999`"])
def test_malformed_metadata_refused(tmp_path: Path, replacement: str) -> None:
    path = card(tmp_path, "T100")
    field = "**Status:** `PENDING`" if "Status" in replacement else "**Task ID:** `T100`"
    path.write_text(path.read_text().replace(field, replacement))
    with pytest.raises(OrchestratorError):
        discover(tmp_path)


def test_discovery_does_not_enforce_dependency_completion(tmp_path: Path) -> None:
    card(tmp_path, "T100")
    card(tmp_path, "T101", ("T100",))
    assert resolve(discover(tmp_path)).blocked == {"T101": ["T100: PENDING"]}
    with pytest.raises(OrchestratorError, match="BLOCKED_FOR_DEPENDENCY"):
        task_card(tmp_path, "T101")


def test_canonical_revision_ignores_uncommitted_completion(pipeline: Pipeline) -> None:
    card(pipeline.repository, "T101", ("T100",))
    commit(pipeline)
    card(pipeline.repository, "T100", status="DONE")
    report = Scheduler(pipeline).run(dry_run=True)
    assert report.graph.ready == ["T100"]
    assert report.graph.blocked == {"T101": ["T100: PENDING"]}
    assert report.graph.revision == pipeline.git.sha("main")


def test_dry_run_no_mutation_or_dispatch(
    pipeline: Pipeline, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = pipeline.git.snapshot(pipeline.git.sha())

    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("Dry-run attempted dispatch, worktree or model")

    monkeypatch.setattr(scheduler, "dispatch", forbidden)
    monkeypatch.setattr(Pipeline, "start", forbidden)
    monkeypatch.setattr(Git, "create_worktree", forbidden)
    report = Scheduler(pipeline).run(dry_run=True)
    assert report.dry_run and report.outcomes == {}
    assert report.graph.ready == ["T100"]
    assert not pipeline.runs.exists()
    assert not pipeline.worktrees.exists()
    assert pipeline.git.snapshot(pipeline.git.sha()) == before


def test_concurrent_roots_and_no_duplicate_dispatch(
    pipeline: Pipeline, monkeypatch: pytest.MonkeyPatch
) -> None:
    for number in range(101, 105):
        card(pipeline.repository, f"T{number}")
    commit(pipeline)
    barrier = Barrier(3)
    guard = Lock()
    calls: list[str] = []
    active = 0
    maximum = 0

    def fake_dispatch(_pipeline: Pipeline, task: str) -> Outcome:
        nonlocal active, maximum
        with guard:
            calls.append(task)
            active += 1
            maximum = max(maximum, active)
        if task in {"T100", "T101", "T102"}:
            barrier.wait(timeout=10)
        with guard:
            active -= 1
        return Outcome(task_id=task, state=State.AUDIT_PASS)

    monkeypatch.setattr(scheduler, "dispatch", fake_dispatch)
    with ThreadPoolExecutor(max_workers=3) as executor:
        report = Scheduler(pipeline).run(executor=executor)
    assert sorted(calls) == [f"T{n}" for n in range(100, 105)]
    assert len(calls) == len(set(calls))
    assert maximum == 3
    assert report.graph.ready == []
    assert set(report.outcomes) == set(calls)


def test_failure_isolation_and_downstream_reason(
    pipeline: Pipeline, monkeypatch: pytest.MonkeyPatch
) -> None:
    card(pipeline.repository, "T101", ("T100",))
    card(pipeline.repository, "T102")
    card(pipeline.repository, "T103", ("T102",))
    commit(pipeline)
    calls: list[str] = []

    def fake_dispatch(_pipeline: Pipeline, task: str) -> Outcome:
        calls.append(task)
        if task == "T100":
            raise OSError("Synthetic branch failure")
        return Outcome(task_id=task, state=State.AUDIT_PASS)

    monkeypatch.setattr(scheduler, "dispatch", fake_dispatch)
    with ThreadPoolExecutor(max_workers=3) as executor:
        report = Scheduler(pipeline).run(executor=executor)
    assert sorted(calls) == ["T100", "T102"]
    assert report.outcomes["T100"].state == State.FAILED
    assert report.graph.blocked["T101"] == ["T100: FAILED"]
    assert report.graph.blocked["T103"] == ["T102: AUDIT_PASS"]


def test_recompute_after_canonical_done_unlocks_linear_graph(
    pipeline: Pipeline, monkeypatch: pytest.MonkeyPatch
) -> None:
    pipeline.config.integrate = True
    card(pipeline.repository, "T101", ("T100",))
    card(pipeline.repository, "T102", ("T101",))
    commit(pipeline)
    calls: list[str] = []

    def fake_dispatch(_pipeline: Pipeline, task: str) -> Outcome:
        calls.append(task)
        card(pipeline.repository, task, status="DONE")
        commit(pipeline)
        return Outcome(task_id=task, state=State.DONE)

    monkeypatch.setattr(scheduler, "dispatch", fake_dispatch)
    with ThreadPoolExecutor(max_workers=3) as executor:
        report = Scheduler(pipeline).run(executor=executor)
    assert calls == ["T100", "T101", "T102"]
    assert report.graph.done == calls
    assert report.graph.blocked == {}


def test_pipeline_done_without_canonical_done_does_not_unlock(
    pipeline: Pipeline, monkeypatch: pytest.MonkeyPatch
) -> None:
    card(pipeline.repository, "T101", ("T100",))
    commit(pipeline)
    calls: list[str] = []

    def fake_dispatch(_pipeline: Pipeline, task: str) -> Outcome:
        calls.append(task)
        return Outcome(task_id=task, state=State.DONE)

    monkeypatch.setattr(scheduler, "dispatch", fake_dispatch)
    with ThreadPoolExecutor(max_workers=3) as executor:
        report = Scheduler(pipeline).run(executor=executor)
    assert calls == ["T100"]
    assert report.graph.done == []
    assert "canonical card is not DONE" in report.graph.blocked["T100"][0]
    assert report.graph.blocked["T101"] == ["T100: DONE (canonical card is not DONE)"]


def test_admission_contention_is_deferred_without_failure(
    pipeline: Pipeline, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = 0

    def fake_dispatch(_pipeline: Pipeline, task: str) -> Outcome:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise LockBusy("Three task runs are already active")
        return Outcome(task_id=task, state=State.AUDIT_PASS)

    monkeypatch.setattr(scheduler, "dispatch", fake_dispatch)
    with ThreadPoolExecutor(max_workers=3) as executor:
        report = Scheduler(pipeline).run(executor=executor)
    assert calls == 2
    assert report.outcomes["T100"].state == State.AUDIT_PASS


def test_busy_roots_do_not_starve_an_unrelated_ready_task(
    pipeline: Pipeline, monkeypatch: pytest.MonkeyPatch
) -> None:
    for number in range(101, 104):
        card(pipeline.repository, f"T{number}")
    commit(pipeline)
    unrelated_ran = Event()
    calls: list[str] = []

    def fake_dispatch(_pipeline: Pipeline, task: str) -> Outcome:
        calls.append(task)
        if task == "T103":
            unrelated_ran.set()
        if not unrelated_ran.is_set():
            assert len(calls) < 20, "Busy roots starved an unrelated READY task"
            raise LockBusy("Task lock busy")
        return Outcome(task_id=task, state=State.AUDIT_PASS)

    monkeypatch.setattr(scheduler, "dispatch", fake_dispatch)
    with ThreadPoolExecutor(max_workers=3) as executor:
        report = Scheduler(pipeline).run(executor=executor)
    assert unrelated_ran.is_set() and calls.count("T103") == 1
    assert all(outcome.state == State.AUDIT_PASS for outcome in report.outcomes.values())
    assert len(report.outcomes) == 4


def test_released_capacity_is_used_while_another_task_is_live(
    pipeline: Pipeline, monkeypatch: pytest.MonkeyPatch
) -> None:
    card(pipeline.repository, "T101")
    commit(pipeline)
    second_started = Event()
    attempts = 0

    def fake_dispatch(_pipeline: Pipeline, task: str) -> Outcome:
        nonlocal attempts
        if task == "T100":
            assert second_started.wait(timeout=5), "Scheduler did not refill released capacity"
        else:
            attempts += 1
            if attempts == 1:
                raise LockBusy("External admission slot busy")
            second_started.set()
        return Outcome(task_id=task, state=State.AUDIT_PASS)

    monkeypatch.setattr(scheduler, "dispatch", fake_dispatch)
    with ThreadPoolExecutor(max_workers=3) as executor:
        report = Scheduler(pipeline).run(executor=executor)
    assert attempts == 2
    assert all(outcome.state == State.AUDIT_PASS for outcome in report.outcomes.values())


def test_scheduler_lock_prevents_duplicate_schedulers(pipeline: Pipeline) -> None:
    with lock(pipeline.locks / "scheduler.lock"), pytest.raises(LockBusy):
        Scheduler(pipeline).run()


def test_dispatch_authoritative_preflight_before_start(
    pipeline: Pipeline, monkeypatch: pytest.MonkeyPatch
) -> None:
    card(pipeline.repository, "T100", status="DONE")
    card(pipeline.repository, "T101", ("T100",))
    commit(pipeline)

    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("Invalid DONE dependency must be refused before Pipeline.start")

    monkeypatch.setattr(Pipeline, "start", forbidden)
    outcome = scheduler.dispatch(pipeline, "T101")
    assert outcome.state == State.FAILED
    assert "Dependency implementation missing" in (outcome.reason or "")
    assert not pipeline.worktrees.exists()


def test_spawned_pipeline_integrates_and_unlocks_downstream(pipeline: Pipeline) -> None:
    synthetic_setup(pipeline)
    pipeline.config.integrate = True
    card(pipeline.repository, "T101", ("T100",))
    commit(pipeline)
    initial = pipeline.git.sha()
    report = Scheduler(pipeline).run()
    assert report.graph.done == ["T100", "T101"]
    assert report.graph.ready == [] and report.graph.blocked == {}
    assert list(report.outcomes) == ["T100", "T101"]
    assert pipeline.git.sha() != initial and pipeline.git.clean()
    for task in report.graph.done:
        state = pipeline.status(task)
        assert state.state == State.DONE
        assert state.integrated_sha is not None
        assert "integration_report" in state.artifacts
        assert (pipeline.repository / f"feature-{task}.txt").is_file()
        task_card(pipeline.repository, task)


def test_spawned_multiple_ready_pipelines_no_integration(pipeline: Pipeline) -> None:
    synthetic_setup(pipeline)
    card(pipeline.repository, "T101")
    card(pipeline.repository, "T102")
    card(pipeline.repository, "T103", ("T100", "T101", "T102"))
    commit(pipeline)
    initial = pipeline.git.sha()
    report = Scheduler(pipeline).run()
    assert set(report.outcomes) == {"T100", "T101", "T102"}
    assert all(outcome.state == State.AUDIT_PASS for outcome in report.outcomes.values())
    assert report.graph.done == []
    assert report.graph.blocked["T103"] == [
        "T100: AUDIT_PASS",
        "T101: AUDIT_PASS",
        "T102: AUDIT_PASS",
    ]
    assert pipeline.git.sha() == initial and pipeline.git.clean()
    assert not (pipeline.repository / "feature-T100.txt").exists()
    for task in report.outcomes:
        state = pipeline.status(task)
        assert state.state == State.AUDIT_PASS
        assert Path(state.worktree_path).is_dir()
        assert set(state.artifacts) >= {"plan", "contract", "worker", "audit", "skills"}
        assert "review_bundle" in state.artifacts
        bundle = ReviewBundle.model_validate(
            read_json(pipeline.run_path(task, state.run_id) / state.artifacts["review_bundle"])
        )
        assert [shard.perspective for shard in bundle.shards] == list(ReviewPerspective)
        assert all(not shard.findings for shard in bundle.shards)
        assert len(list((pipeline.runs / task).iterdir())) == 1


def test_spawned_pipelines_respect_external_admission_slots(pipeline: Pipeline) -> None:
    synthetic_setup(pipeline)
    card(pipeline.repository, "T101")
    card(pipeline.repository, "T102")
    commit(pipeline)
    with lock(pipeline.locks / "slot-0.lock"), lock(pipeline.locks / "slot-1.lock"):
        report = Scheduler(pipeline).run()
    assert set(report.outcomes) == {"T100", "T101", "T102"}
    assert all(outcome.state == State.AUDIT_PASS for outcome in report.outcomes.values())
    for task in report.outcomes:
        assert len(list((pipeline.runs / task).iterdir())) == 1


def test_spawned_pipeline_failure_does_not_stop_another_branch(pipeline: Pipeline) -> None:
    synthetic_setup(pipeline)
    pipeline.provider = SyntheticProvider(fail_task="T100")
    card(pipeline.repository, "T101")
    card(pipeline.repository, "T102", ("T100",))
    commit(pipeline)
    report = Scheduler(pipeline).run()
    assert report.outcomes["T100"].state == State.FAILED
    assert report.outcomes["T101"].state == State.AUDIT_PASS
    assert report.graph.blocked["T102"] == ["T100: FAILED"]
    assert not (pipeline.runs / "T102").exists()


def test_invalid_graph_never_starts_executor(
    pipeline: Pipeline, monkeypatch: pytest.MonkeyPatch
) -> None:
    card(pipeline.repository, "T101", ("T999",))
    commit(pipeline)

    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("Invalid graph must fail before creating dispatch processes")

    monkeypatch.setattr(scheduler, "ProcessPoolExecutor", forbidden)
    with pytest.raises(OrchestratorError, match="Missing dependency"):
        Scheduler(pipeline).run()
    assert not pipeline.runs.exists()


def test_done_cycle_is_still_invalid(tmp_path: Path) -> None:
    card(tmp_path, "T100", ("T101",), "DONE")
    card(tmp_path, "T101", ("T100",), "DONE")
    with pytest.raises(OrchestratorError, match="Dependency cycle"):
        resolve(discover(tmp_path))


@pytest.mark.parametrize("canonical", [False, True])
def test_symlink_card_is_refused(pipeline: Pipeline, canonical: bool) -> None:
    original = card(pipeline.repository, "T101")
    symlink = original.parent / "t102-link.md"
    symlink.symlink_to(original.name)
    if canonical:
        commit(pipeline)
    with pytest.raises(OrchestratorError, match="regular task card"):
        discover(pipeline.repository, pipeline.git.sha() if canonical else None)


def test_deterministic_report_and_dependency_order(tmp_path: Path) -> None:
    card(tmp_path, "T102", ("T101", "T100", "T101"))
    card(tmp_path, "T101")
    card(tmp_path, "T100")
    first = resolve(discover(tmp_path))
    second = resolve(discover(tmp_path))
    assert first.model_dump() == second.model_dump()
    assert first.topological_order == ["T100", "T101", "T102"]
    assert first.tasks["T102"].dependencies == ["T100", "T101"]


def test_task_list_and_template_are_not_cards(pipeline: Pipeline) -> None:
    (pipeline.repository / "tasks/task-index.md").write_text("Synthetic task index\n")
    (pipeline.repository / "tasks/_template.md").write_text("Synthetic template\n")
    commit(pipeline)
    assert list(discover(pipeline.repository)) == ["T100"]
    assert list(discover(pipeline.repository, pipeline.git.sha())) == ["T100"]


def test_successful_dry_run_with_blocked_nodes_returns_zero(
    pipeline: Pipeline, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    card(pipeline.repository, "T101", ("T100",))
    commit(pipeline)
    monkeypatch.setattr(Pipeline, "load", lambda *_args: pipeline)
    monkeypatch.setattr(sys, "argv", ["orchestrator", "schedule", "--dry-run"])
    assert main() == 0
    assert json.loads(capsys.readouterr().out)["graph"]["blocked"] == {"T101": ["T100: PENDING"]}


@pytest.mark.parametrize("flags", [[], ["--no-integrate"], ["--integrate"]])
def test_schedule_cli_dry_run(
    pipeline: Pipeline,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    flags: list[str],
) -> None:
    monkeypatch.setattr(Pipeline, "load", lambda *_args: pipeline)
    monkeypatch.setattr(sys, "argv", ["orchestrator", "schedule", "--dry-run", *flags])
    assert main() == 0
    output = json.loads(capsys.readouterr().out)
    assert output["graph"]["ready"] == ["T100"]
    assert output["dry_run"] is True
    assert pipeline.config.integrate == ("--integrate" in flags)


@pytest.mark.parametrize("arguments", [["schedule", "T100"], ["schedule", "--run-id", "old"]])
def test_schedule_rejects_single_task_arguments(
    pipeline: Pipeline, monkeypatch: pytest.MonkeyPatch, arguments: list[str]
) -> None:
    monkeypatch.setattr(Pipeline, "load", lambda *_args: pipeline)
    monkeypatch.setattr(sys, "argv", ["orchestrator", *arguments])
    assert main() == 2


@pytest.mark.parametrize("command", ["run", "resume", "retry", "status"])
def test_existing_cli_still_requires_task(monkeypatch: pytest.MonkeyPatch, command: str) -> None:
    monkeypatch.setattr(sys, "argv", ["orchestrator", command])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2


def test_scheduler_metadata_aligns_with_core_dependency_ids() -> None:
    from tools.orchestrator.core import dependency_ids

    fixture_text = """# T018: Synthetic Consent
**Task ID:** `T018`
**Title:** Synthetic Consent
**Status:** `TODO`
## Dependencies

- [T081](t081-app-shell-shadcn-migration.md)
- [T015](t015-consent-api.md)
- [T017](t017-typed-api-client.md)
- [T052](t052-browser-test-harness.md)

This prose token is not a dependency:
BLOCKED_BY_T080_T081
## Files được phép sửa
- `child.py`
## Acceptance criteria
- [ ] Criteria
## Verification commands
```text
python -m pytest
```
"""
    meta = scheduler.metadata("tasks/t018-consent.md", fixture_text)
    core_deps = dependency_ids(fixture_text)
    assert meta.dependencies == core_deps == ["T015", "T017", "T052", "T081"]
    assert "T080" not in meta.dependencies
    assert "T080" not in core_deps

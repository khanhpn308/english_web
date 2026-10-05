import json
import re
import sys
import threading
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
    ReviewBundle,
    ReviewFinding,
    ReviewPerspective,
    ReviewShard,
    Role,
    RunState,
    State,
    WorkerResult,
    atomic_json,
    digest,
    read_json,
    task_card,
)
from tools.orchestrator.runtime import CliProvider, Git, ProcessResult, execute, lock
from tools.orchestrator.workflow import Pipeline

Output = TypeVar("Output", bound=BaseModel)


@pytest.fixture
def repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    pack = tmp_path / "agent-skills" / "skills"
    for name in (
        "incremental-implementation",
        "test-driven-development",
        "git-workflow-and-versioning",
        "documentation-and-adrs",
        "debugging-and-error-recovery",
        "code-review-and-quality",
        "api-and-interface-design",
        "frontend-ui-engineering",
        "security-and-hardening",
        "doubt-driven-development",
        "browser-testing-with-devtools",
        "ci-cd-and-automation",
        "performance-optimization",
        "observability-and-instrumentation",
        "deprecation-and-migration",
        "source-driven-development",
    ):
        path = pack / name / "SKILL.md"
        path.parent.mkdir(parents=True)
        path.write_text(
            f"---\nname: {name}\ndescription: Synthetic workflow\n---\nApply synthetic checks.\n"
        )
    monkeypatch.setenv("AGENT_SKILLS_ROOT", str(pack))
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
    def __init__(self, *, failures: int = 0, lie: bool = False, timeout: int | None = 30) -> None:
        self.calls: list[str] = []
        self.reviewer_calls: list[ReviewPerspective] = []
        self.timeout = timeout
        self.failures = failures
        self.lie = lie
        self.worker_calls = 0

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
        assert role.executable == "fake-codex"
        assert timeout == self.timeout
        assert artifacts.is_dir()
        assert name
        if output == ReviewShard:
            assert readonly
            matched = re.search(r"REVIEW_PERSPECTIVE: ([^\n]+)", prompt)
            assert matched is not None
            perspective = ReviewPerspective(matched[1])
            self.reviewer_calls.append(perspective)
            return output.model_validate(ReviewShard(perspective=perspective, findings=[]))
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


class AuthorityProbePipeline(Pipeline):
    def __init__(self, repository: Path, config: Config, provider: FakeAgents) -> None:
        super().__init__(repository, config, provider)
        self.owner = threading.get_ident()
        self.live_state: RunState | None = None

    def save(self, directory: Path, state: RunState) -> None:
        assert threading.get_ident() == self.owner, "reviewer thread attempted state write"
        self.live_state = state
        super().save(directory, state)

    def artifact(self, directory: Path, state: RunState, key: str, value: BaseModel) -> None:
        assert threading.get_ident() == self.owner, "reviewer thread registered authority"
        super().artifact(directory, state, key, value)

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
        assert threading.get_ident() == self.owner, "Pipeline.invoke called in reviewer thread"
        return super().invoke(directory, state, role_name, output, context, cwd=cwd)


class CoordinatedReviewAgents(FakeAgents):
    """Logical time: all three enter before any completes; completions are forced 2,1,0."""

    def __init__(self, mode: str = "success") -> None:
        super().__init__()
        self.mode = mode
        self.barrier = threading.Barrier(3, timeout=10)
        self.finished = [threading.Event() for _ in ReviewPerspective]
        self.mutex = threading.Lock()
        self.active = 0
        self.max_active = 0
        self.completions: list[ReviewPerspective] = []
        self.timeline: list[str] = []
        self.names: list[str] = []
        self.source_digests: list[str] = []
        self.frozen_states: list[str] = []
        self.audit_prompts: list[str] = []
        self.pipeline: AuthorityProbePipeline | None = None
        self.failure_cli: Path | None = None

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
        if output != ReviewShard:
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
            if output == Audit:
                self.audit_prompts.append(prompt)
                bundle = ReviewBundle.model_validate(read_json(artifacts / "00-review_bundle.json"))
                for shard in bundle.shards:
                    assert shard.findings[0].action in prompt
                    assert shard.findings[0].finding_id in prompt
                assert '"results"' in prompt and '"summary"' in prompt
                data = result.model_dump()
                data["reviewer_dispositions"] = [
                    {
                        "finding_id": shard.findings[0].finding_id,
                        "disposition": "dismissed",
                        "evidence": "Source and executable test refute the advisory claim",
                    }
                    for shard in bundle.shards
                ]
                if self.mode == "missing_disposition":
                    data["reviewer_dispositions"].pop()
                elif self.mode == "unknown_disposition":
                    data["reviewer_dispositions"][0]["finding_id"] = "unknown:0001"
                elif self.mode == "duplicate_disposition":
                    data["reviewer_dispositions"].append(data["reviewer_dispositions"][0])
                elif self.mode == "confirmed_disposition":
                    data["reviewer_dispositions"][0]["disposition"] = "confirmed"
                return output.model_validate(data)
            return result
        assert readonly and role.model == "configured-future-auditor-model"
        assert timeout == 30
        assert "code-review-and-quality" in prompt
        assert len(list(artifacts.glob("00-review-*.prompt.md"))) == 3
        assert not (artifacts / "00-review_bundle.json").exists()
        match = re.search(r"REVIEW_PERSPECTIVE: ([^\n]+)", prompt)
        assert match is not None
        perspective = ReviewPerspective(match[1])
        index = list(ReviewPerspective).index(perspective)
        frozen = (artifacts / "state.json").read_bytes()
        saved = RunState.model_validate_json(frozen)
        assert saved.current_agent == "parallel_review" and saved.state == State.AUDIT_RUNNING
        match = re.search(r"FROZEN_SOURCE_DIGEST: ([a-f0-9]+)", prompt)
        assert match is not None
        with self.mutex:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            self.timeline.append("start")
            self.names.append(name)
            self.source_digests.append(match[1])
            self.frozen_states.append(digest(frozen))
        try:
            self.barrier.wait()
            if index < 2:
                assert self.finished[index + 1].wait(10)
            atomic_json(
                artifacts / f"{name}.log.json", {"synthetic": True, "perspective": perspective}
            )
            if index == 1:
                if self.mode in {"process", "timeout", "oversized", "malformed"}:
                    assert self.failure_cli is not None
                    return CliProvider().run(
                        f"FAULT: {self.mode}",
                        cwd=cwd,
                        role=role.model_copy(update={"executable": str(self.failure_cli)}),
                        timeout=1,
                        output=output,
                        artifacts=artifacts,
                        name=name,
                        readonly=True,
                    )
                if self.mode == "schema":
                    return output.model_validate({"perspective": perspective, "findings": "bad"})
                if self.mode == "wrong_perspective":
                    return output.model_validate(
                        {"perspective": ReviewPerspective.SECURITY, "findings": []}
                    )
                if self.mode == "source":
                    (cwd / "feature.txt").write_text("Reviewer source mutation")
                if self.mode == "branch":
                    Git(cwd).run("symbolic-ref", "HEAD", "refs/heads/main")
                if self.mode == "state":
                    (artifacts / "state.json").write_bytes(frozen + b" ")
                if self.mode == "artifact":
                    (artifacts / "00-contract.json").write_text("corrupt")
                if self.mode == "prompt":
                    path = next(artifacts.glob("00-review-*.prompt.md"))
                    path.write_text("corrupt")
                if self.mode == "memory":
                    assert self.pipeline is not None and self.pipeline.live_state is not None
                    self.pipeline.live_state.current_agent = "intruder"
                    self.pipeline.live_state.state = State.DONE
                    self.pipeline.live_state.artifacts = {}
                    self.pipeline.live_state.artifact_digests = {}
            return output.model_validate(
                ReviewShard(
                    perspective=perspective,
                    findings=[
                        ReviewFinding(
                            action=f"Check synthetic {perspective}", evidence="feature.txt:1"
                        )
                    ],
                )
            )
        finally:
            with self.mutex:
                self.active -= 1
                self.completions.append(perspective)
                self.timeline.append("finish")
            self.finished[index].set()


def parallel_review_pipeline(
    repository: Path, agents: CoordinatedReviewAgents
) -> AuthorityProbePipeline:
    config = configuration(integrate=False)
    config.roles["auditor"].model = "configured-future-auditor-model"
    if agents.mode in {"process", "timeout", "oversized", "malformed"}:
        cli = repository.parent / "review-failure-cli"
        cli.write_text(f"""#!{sys.executable}
import pathlib, sys, threading
if '--version' in sys.argv:
    print('synthetic 1.0')
elif '--help' in sys.argv:
    print('--ask-for-approval --output-schema --output-last-message --sandbox --ephemeral')
else:
    fault = sys.stdin.read().strip().split()[-1]
    if fault == 'process':
        raise SystemExit(7)
    if fault == 'timeout':
        threading.Event().wait()
    if fault == 'oversized':
        sys.stdout.buffer.write(b'x' * 5000000)
        sys.stdout.flush()
        threading.Event().wait()
    response = pathlib.Path(sys.argv[sys.argv.index('--output-last-message') + 1])
    response.write_text('{{broken')
""")
        cli.chmod(0o700)
        agents.failure_cli = cli
    pipeline = AuthorityProbePipeline(repository, config, agents)
    agents.pipeline = pipeline
    return pipeline


def test_parallel_review_real_overlap_and_out_of_order_fanin(repository: Path) -> None:
    agents = CoordinatedReviewAgents()
    pipeline = parallel_review_pipeline(repository, agents)
    state = pipeline.start("T100")
    assert state.state == State.AUDIT_PASS
    assert agents.max_active == 3 and agents.active == 0
    assert agents.timeline == ["start"] * 3 + ["finish"] * 3
    assert agents.completions == list(reversed(ReviewPerspective))
    assert len(set(agents.names)) == 3
    assert len(set(agents.source_digests)) == len(set(agents.frozen_states)) == 1
    directory = pipeline.run_path("T100", state.run_id)
    bundle = ReviewBundle.model_validate(read_json(directory / state.artifacts["review_bundle"]))
    assert bundle.source_digest == agents.source_digests[0] == state.audited_digest
    assert [s.perspective for s in bundle.shards] == list(ReviewPerspective)
    assert len(bundle.shards) == 3 and all(len(s.findings) == 1 for s in bundle.shards)
    assert len(agents.audit_prompts) == 1
    assert state.current_agent is None
    pipeline.check_artifacts(directory, state)
    for name in agents.names:
        assert f"{name}.log.json" in state.artifact_digests
        assert f"{name}.prompt.md" in state.artifact_digests
    # Logical concurrency proof is machine-speed independent: a serial dispatcher cannot
    # reach this barrier; three units of advisory work occupy a single coordinated round.
    assert all(event.is_set() for event in agents.finished)


@pytest.mark.parametrize(
    "mode,reason",
    [
        ("process", "incomplete"),
        ("timeout", "incomplete"),
        ("oversized", "incomplete"),
        ("malformed", "incomplete"),
        ("schema", "incomplete"),
        ("wrong_perspective", "incomplete"),
        ("source", "repository source"),
        ("branch", "changed branch"),
        ("state", "protected evidence or state"),
        ("artifact", "protected evidence or state"),
        ("prompt", "protected evidence or state"),
        ("memory", "in-memory orchestration state"),
    ],
)
def test_parallel_review_failure_reaps_every_reviewer_and_blocks_auditor(
    repository: Path, mode: str, reason: str
) -> None:
    agents = CoordinatedReviewAgents(mode)
    pipeline = parallel_review_pipeline(repository, agents)
    initial = Git(repository).sha()
    state = pipeline.start("T100")
    assert state.state == State.FAILED and state.blocked_from == State.AUDIT_RUNNING
    assert reason in (state.last_error or "")
    assert agents.max_active == 3 and agents.active == 0
    assert agents.completions == list(reversed(ReviewPerspective))
    assert all(event.is_set() for event in agents.finished)
    assert "Audit" not in agents.calls and "IntegrationReview" not in agents.calls
    assert "review_bundle" not in state.artifacts
    directory = pipeline.run_path("T100", state.run_id)
    assert not (directory / "00-review_bundle.json").exists()
    assert Git(repository).sha() == initial
    if mode in {"process", "timeout", "oversized", "malformed", "schema", "wrong_perspective"}:
        assert (Path(state.worktree_path) / "feature.txt").read_text() == "good"
        assert state.current_agent is None
        pipeline.check_artifacts(directory, state)
        assert all(f"{name}.log.json" in state.artifact_digests for name in agents.names)
        if mode in {"process", "timeout", "oversized", "malformed"}:
            name = next(n for n in agents.names if ReviewPerspective.VERIFICATION in n)
            log = read_json(directory / f"{name}.log.json")
            assert isinstance(log, dict)
            execution = log["execution"]
            if mode == "process":
                assert execution["exit_code"] == 7
            elif mode == "timeout":
                assert execution["timed_out"] is True
            elif mode == "oversized":
                assert execution["oversized"] is True
            else:
                assert execution["exit_code"] == 0


@pytest.mark.parametrize("mode", ["missing", "unknown", "duplicate", "confirmed"])
def test_parallel_review_authoritative_audit_disposition_failures_are_bounded(
    repository: Path, mode: str
) -> None:
    agents = CoordinatedReviewAgents(f"{mode}_disposition")
    pipeline = parallel_review_pipeline(repository, agents)
    state = pipeline.start("T100")
    assert state.state == State.FAILED
    assert mode in (state.last_error or "")
    assert agents.calls.count("Audit") == 3 and agents.worker_calls == 1
    assert len(agents.completions) == 3  # Report correction never repeats the fan-out.
    assert "IntegrationReview" not in agents.calls and "audit" not in state.artifacts
    directory = pipeline.run_path("T100", state.run_id)
    assert len(list(directory.glob("*-auditor-*.rejected.json"))) == 3


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
    assert state.state == State.FAILED
    assert state.fix_cycle == 1
    assert "Maximum fix" in (state.last_error or "")
    assert Git(repository).sha() == initial
    assert "IntegrationReview" not in agents.calls
    assert (pipeline.run_path("T100") / "final_report.md").exists()


def test_failed_test_cannot_be_audit_pass(repository: Path) -> None:
    state = Pipeline(repository, configuration(), FakeAgents(failures=1, lie=True)).start("T100")
    assert state.state == State.FAILED
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
    assert result.state == State.FAILED
    assert "evidence stale" in (result.last_error or "")


def test_dirty_base_never_stashes_or_resets(repository: Path) -> None:
    (repository / "user.txt").write_text("preserve")
    agents = FakeAgents()
    pipeline = Pipeline(repository, configuration(), agents)
    result = pipeline.start("T100")
    assert result.state == State.FAILED
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
    assert pipeline.resume("T100").state == State.FAILED


def test_contract_tamper_blocks_resume(repository: Path) -> None:
    pipeline = Pipeline(repository, configuration(), FakeAgents())
    with lock(pipeline.runs / ".locks/integration.lock"):
        state = pipeline.start("T100")
    directory = pipeline.run_path("T100")
    contract = Contract.model_validate(read_json(directory / state.artifacts["contract"]))
    contract.allowed_paths.append("user.txt")
    atomic_json(directory / state.artifacts["contract"], contract.model_dump())
    assert pipeline.resume("T100", state.run_id).state == State.FAILED


def test_hidden_staged_change_cannot_escape_scope(repository: Path) -> None:
    class HiddenIndex(FakeAgents):
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
    assert result.state == State.FAILED
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
    assert result.state == State.FAILED
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
    assert result.state == State.FAILED
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
            timeout: int | None,
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
    assert result.state == State.FAILED
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
            timeout: int | None,
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
    assert result.state == State.FAILED
    assert "artifact changed" in (result.last_error or "")


def test_incomplete_resumable_state_blocks_without_traceback(repository: Path) -> None:
    pipeline = Pipeline(repository, configuration(integrate=False), FakeAgents())
    state = pipeline.start("T100")
    state.artifacts = {}
    pipeline.save(pipeline.run_path("T100"), state)
    result = pipeline.resume("T100")
    assert result.state == State.FAILED
    assert "Incomplete state" in (result.last_error or "")


def test_worker_prompt_tamper_prevents_implementation(repository: Path) -> None:
    class Tamper(Pipeline):
        def move(self, directory: Path, state: RunState, destination: State) -> None:
            super().move(directory, state, destination)
            if destination == State.PROMPT_READY:
                (directory / "worker_prompt.md").write_text("Change unrelated product behavior")

    agents = FakeAgents()
    result = Tamper(repository, configuration(), agents).start("T100")
    assert result.state == State.FAILED
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
    assert result.state == State.FAILED
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
    assert result.state == State.FAILED
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
        timeout: int | None,
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
    assert state.state == State.FAILED
    error = state.last_error or ""
    for field in ["objective", "forbidden_scope", "stop_conditions"]:
        assert field in error
    assert "PRIVATE SENTINEL" not in error
    assert agents.calls == ["Plan"] * 3
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
        assert state.state == State.FAILED
        assert "forbidden_paths[0]" in error
        assert "private-sentinel" not in error
        assert agents.calls == ["Plan"] * 3
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
    assert pipeline.status("T100", old.run_id).state == State.FAILED


def test_run_retries_preworker_failure_without_manual_command(repository: Path) -> None:
    pipeline = Pipeline(repository, configuration(integrate=False), PlanningProbe("drift"))
    old = pipeline.start("T100")
    pipeline.provider = FakeAgents()
    state = pipeline.start("T100")
    assert state.state == State.AUDIT_PASS and state.retry_of == old.run_id
    assert pipeline.status("T100", old.run_id).state == State.FAILED
    assert len(list((pipeline.runs / "T100").glob("*/state.json"))) == 2


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
    assert old.state == State.FAILED and agents.calls == []
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


class RecoveryAgents(FakeAgents):
    def __init__(self, mode: str) -> None:
        super().__init__()
        self.mode = mode
        self.attempts = 0

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
        if output == WorkerResult:
            self.attempts += 1
            if self.mode == "worker_empty" and self.attempts == 1:
                self.calls.append("WorkerResult")
                return output.model_validate(
                    {
                        "status": "BLOCKED",
                        "summary": "Synthetic limitation",
                        "changed_files": [],
                        "commands_run": [],
                        "known_issues": ["Repair limitation"],
                    }
                )
            if self.mode in {"transient", "persistent", "mutating", "trust"}:
                failing = self.mode != "transient" or self.attempts < 3
                if failing:
                    if self.mode == "mutating":
                        (cwd / "feature.txt").write_text("Preserve partial implementation")
                    if self.mode == "trust":
                        atomic_json(
                            artifacts / f"{name}.log.json",
                            {
                                "provider": "gemini",
                                "execution": {
                                    "cwd": str(cwd),
                                    "exit_code": 55,
                                    "timed_out": False,
                                    "oversized": False,
                                    "stdout_bytes": 0,
                                    "stderr_bytes": 100,
                                },
                            },
                        )
                    raise OrchestratorError("Agent process failed (exit 55, timeout=False)")
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
        if self.mode == "worker_blocked" and output == WorkerResult and self.attempts == 1:
            data = result.model_dump()
            data.update(status="BLOCKED", known_issues=["Synthetic repairable limitation"])
            return output.model_validate(data)
        if self.mode == "audit_blocked" and output == Audit and self.worker_calls == 1:
            data = result.model_dump()
            data.update(
                status="BLOCKED",
                findings=["Synthetic repairable limitation"],
                required_fixes=["Repair synthetic limitation"],
            )
            return output.model_validate(data)
        return result


@pytest.mark.parametrize("mode", ["transient", "worker_blocked", "worker_empty", "audit_blocked"])
def test_automatic_agent_recovery_reaches_done(repository: Path, mode: str) -> None:
    agents = RecoveryAgents(mode)
    state = Pipeline(repository, configuration(), agents).start("T100")
    assert state.state == State.DONE
    assert agents.attempts == (3 if mode == "transient" else 2)
    assert state.fix_cycle == (0 if mode == "transient" else 1)
    assert (repository / "feature.txt").read_text() == "good"


@pytest.mark.parametrize("mode", ["persistent", "mutating"])
def test_agent_failure_is_finite_and_preserves_partial_work(repository: Path, mode: str) -> None:
    agents = RecoveryAgents(mode)
    original = Git(repository).sha()
    pipeline = Pipeline(repository, configuration(), agents)
    state = pipeline.start("T100")
    assert state.state == State.FAILED
    assert agents.attempts == (3 if mode == "persistent" else 1)
    assert Git(repository).sha() == original
    assert "IntegrationReview" not in agents.calls
    if mode == "mutating":
        assert (
            Path(state.worktree_path) / "feature.txt"
        ).read_text() == "Preserve partial implementation"


@pytest.mark.parametrize("unsafe", ["none", "dirty", "wrong_exit", "output", "missing"])
def test_run_recovers_known_gemini_trust_failure_only(repository: Path, unsafe: str) -> None:
    config = configuration(integrate=False)
    config.roles["worker"].provider = "gemini"
    agents = RecoveryAgents("trust")
    pipeline = Pipeline(repository, config, agents)
    old = pipeline.start("T100")
    directory = pipeline.run_path("T100", old.run_id)
    if unsafe == "dirty":
        (Path(old.worktree_path) / "feature.txt").write_text("Preserve unrelated work")
    logs = list(directory.glob("00-worker-*.log.json"))
    assert logs
    if unsafe in {"wrong_exit", "output"}:
        data = json.loads(logs[-1].read_text())
        data["execution"]["exit_code" if unsafe == "wrong_exit" else "stdout_bytes"] = 8
        atomic_json(logs[-1], data)
    elif unsafe == "missing":
        for path in logs:
            path.unlink()
    preserved = {p.name: p.read_bytes() for p in directory.iterdir() if p.is_file()}
    pipeline.provider = FakeAgents()
    if unsafe != "none":
        with pytest.raises(OrchestratorError):
            pipeline.start("T100")
        assert pipeline.provider.calls == []
    else:
        state = pipeline.start("T100")
        assert state.state == State.AUDIT_PASS
        assert state.retry_of == old.run_id
        assert pipeline.provider.calls == ["Plan", "WorkerResult", "Audit"]
    assert preserved == {p.name: p.read_bytes() for p in directory.iterdir() if p.is_file()}


def test_run_resumes_stable_audited_run_without_repeating_worker(repository: Path) -> None:
    agents = FakeAgents()
    pipeline = Pipeline(repository, configuration(integrate=False), agents)
    old = pipeline.start("T100")
    pipeline.config.integrate = True
    state = pipeline.start("T100")
    assert state.state == State.DONE and state.run_id == old.run_id
    assert agents.worker_calls == 1


def test_planning_drift_is_corrected_automatically(repository: Path) -> None:
    class Once(PlanningProbe):
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
            self.mode = "template"
            return result

    agents = Once("drift")
    state = Pipeline(repository, configuration(), agents).start("T100")
    assert state.state == State.DONE
    assert agents.calls == ["Plan", "Plan", "WorkerResult", "Audit", "IntegrationReview"]


@pytest.mark.parametrize(
    "unsafe", ["none", "dirty", "output", "timeout", "tampered", "same_provider"]
)
def test_corrected_agy_routing_retries_clean_failed_gemini_run(
    repository: Path, unsafe: str
) -> None:
    config = configuration(integrate=False)
    config.roles["worker"].provider = "gemini"
    pipeline = Pipeline(repository, config, RecoveryAgents("trust"))
    old = pipeline.start("T100")
    directory = pipeline.run_path("T100", old.run_id)
    old.last_error = "Agent process failed (exit 1, timeout=False)"
    for path in directory.glob("00-worker-*.log.json"):
        value = json.loads(path.read_text())
        value["execution"]["exit_code"] = 1
        if unsafe == "output":
            value["execution"]["stdout_bytes"] = 10
        if unsafe == "timeout":
            value["execution"]["timed_out"] = True
        atomic_json(path, value)
        old.artifact_digests[path.name] = digest(path.read_bytes())
    pipeline.save(directory, old)
    if unsafe == "dirty":
        (Path(old.worktree_path) / "feature.txt").write_text("Preserve partial edits")
    if unsafe == "tampered":
        path = next(directory.glob("00-worker-*.log.json"))
        path.write_text(path.read_text() + " ")
    config.roles["worker"] = Role(
        provider="agy" if unsafe != "same_provider" else "gemini",
        executable="fake-codex",
        allow_process=unsafe != "same_provider",
    )
    pipeline.provider = FakeAgents()
    preserved = {p.name: p.read_bytes() for p in directory.iterdir() if p.is_file()}
    if unsafe == "none":
        new = pipeline.start("T100")
        assert new.state == State.AUDIT_PASS
        assert new.retry_of == old.run_id
        assert new.config is not None and new.config.roles["worker"].provider == "agy"
    else:
        with pytest.raises(OrchestratorError):
            pipeline.start("T100")
        assert pipeline.provider.calls == []
    assert preserved == {p.name: p.read_bytes() for p in directory.iterdir() if p.is_file()}


@pytest.mark.parametrize("role_name", ["prompt_engineer", "auditor", "integrator"])
@pytest.mark.parametrize("permission", ["worker_access", "allow_process"])
def test_config_refuses_worker_permissions_for_other_roles(
    repository: Path, role_name: str, permission: str
) -> None:
    config = configuration()
    role = config.roles[role_name].model_dump()
    role[permission] = "full-access" if permission == "worker_access" else True
    config.roles[role_name] = Role.model_validate(role)
    with pytest.raises(OrchestratorError, match="Worker"):
        Pipeline(repository, config, FakeAgents())


@pytest.mark.parametrize(
    "unsafe",
    [
        "none",
        "dirty",
        "log",
        "response",
        "schema",
        "prompt",
        "error",
        "contract",
        "schema_missing",
        "attempt_prompt_missing",
        "attempt_prompt",
        "schema_link",
        "other_attempt",
        "history",
        "wrong_provider",
        "fix_cycle",
        "missing_verified",
        "missing_task_card",
    ],
)
def test_agy_legacy_help_failure_retry_preserves_evidence(repository: Path, unsafe: str) -> None:
    class PreflightFailure(FakeAgents):
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
            if output == WorkerResult:
                atomic_json(artifacts / f"{name}.schema.json", output.model_json_schema())
                raise OrchestratorError("agy lacks required capability: --print")
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

    config = configuration(integrate=False)
    config.roles["worker"].provider = "agy"
    pipeline = Pipeline(repository, config, PreflightFailure())
    old = pipeline.start("T100")
    assert old.state == State.FAILED and old.blocked_from == State.WORKER_RUNNING
    directory = pipeline.run_path("T100", old.run_id)
    schema = next(directory.glob("00-worker-*.schema.json"))
    stem = schema.name.removesuffix(".schema.json")
    if unsafe == "dirty":
        (Path(old.worktree_path) / "feature.txt").write_text("Preserve partial edits")
    elif unsafe in {"log", "response"}:
        atomic_json(directory / f"{stem}.{unsafe}.json", {"execution": "unknown"})
    elif unsafe == "schema":
        atomic_json(schema, {"unknown": "schema"})
    elif unsafe == "prompt":
        (directory / "worker_prompt.md").write_text("Changed handoff")
    elif unsafe == "error":
        old.last_error = "Agent process failed (exit 1, timeout=False)"
        pipeline.save(directory, old)
    elif unsafe == "contract":
        p = directory / old.artifacts["contract"]
        p.write_text(p.read_text() + " ")
    elif unsafe == "schema_missing":
        schema.unlink()
    elif unsafe == "attempt_prompt_missing":
        (directory / f"{stem}.prompt.md").unlink()
    elif unsafe == "attempt_prompt":
        (directory / f"{stem}.prompt.md").write_text("Changed invocation prompt")
    elif unsafe == "schema_link":
        external = directory / "external-schema.json"
        external.write_bytes(schema.read_bytes())
        schema.unlink()
        schema.symlink_to(external)
    elif unsafe == "other_attempt":
        (directory / "00-worker-extra.prompt.md").write_text("Uncertain extra attempt")
    elif unsafe == "history":
        Git(Path(old.worktree_path)).run("commit", "--allow-empty", "-m", "Unknown Worker commit")
    elif unsafe == "wrong_provider":
        config.roles["worker"].provider = "gemini"
    elif unsafe == "fix_cycle":
        old.fix_cycle = 1
        pipeline.save(directory, old)
    elif unsafe == "missing_verified":
        old.verified_digest = ""
        pipeline.save(directory, old)
    elif unsafe == "missing_task_card":
        del old.artifacts["task_card"]
        pipeline.save(directory, old)
    retained = {p.name: p.read_bytes() for p in directory.iterdir() if p.is_file()}
    pipeline.provider = FakeAgents()
    if unsafe == "none":
        new = pipeline.start("T100")
        assert new.state == State.AUDIT_PASS and new.retry_of == old.run_id
        assert new.worktree_path != old.worktree_path
        assert pipeline.provider.calls == ["Plan", "WorkerResult", "Audit"]
    else:
        with pytest.raises(OrchestratorError):
            pipeline.start("T100")
        assert pipeline.provider.calls == []
    assert retained == {p.name: p.read_bytes() for p in directory.iterdir() if p.is_file()}


class AuditCorrectionAgents(FakeAgents):
    def __init__(self, mode: str) -> None:
        super().__init__()
        self.mode = mode
        self.audit_attempts = 0
        self.prompts: list[str] = []

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
        if output != Audit:
            return result
        self.audit_attempts += 1
        self.prompts.append(prompt)
        correction = self.audit_attempts > 1 and not (
            self.mode == "real_fail" and self.audit_attempts == 3
        )
        if correction:
            rejected = list(artifacts.glob("*-auditor-*.rejected.json"))
            assert rejected, "Invalid Audit must remain structured evidence before retry"
            assert "AUDIT REPORT CORRECTION" in prompt
            assert "Do not remove real defects" in prompt
            if self.mode == "tamper_rejected":
                rejected[0].write_text(rejected[0].read_text() + " ")
        invalid = self.audit_attempts == 1 or self.mode == "persistent"
        data = result.model_dump()
        if invalid:
            data["findings"] = ["Independent tests passed; informational evidence"]
            if self.mode == "real_fail":
                data["findings"].append("Actual defect remains")
            if self.mode == "coverage":
                data["findings"] = []
                data["acceptance_criteria"] = []
            if self.mode == "empty_fail":
                data.update(status="FAIL", findings=[], required_fixes=[])
            if self.mode == "criterion_fail":
                data["findings"] = []
                data["acceptance_criteria"][0]["status"] = "FAIL"
            if self.mode == "scope":
                data["findings"] = []
                data["scope_violations"] = ["Unexpected feature path"]
            if self.mode == "required_fix":
                data["findings"] = []
                data["required_fixes"] = ["Unresolved defect"]
            if self.mode == "source_mutation":
                (cwd / "feature.txt").write_text("Unknown auditor edit")
            if self.mode == "state_mutation":
                state = artifacts / "state.json"
                state.write_text(state.read_text() + " ")
            if self.mode == "handoff_mutation":
                contract = artifacts / "00-contract.json"
                contract.write_text(contract.read_text() + " ")
        elif self.mode == "real_fail" and self.audit_attempts == 2:
            data.update(
                status="FAIL",
                findings=["Actual defect remains"],
                required_fixes=["Fix the actual defect"],
            )
            data["acceptance_criteria"][0]["status"] = "FAIL"
        elif self.mode == "correct":
            data["acceptance_criteria"][0]["evidence"] = (
                "Independent tests passed; informational evidence"
            )
        return output.model_validate(data)


@pytest.mark.parametrize(
    "mode", ["correct", "coverage", "empty_fail", "criterion_fail", "scope", "required_fix"]
)
def test_semantic_audit_report_is_corrected_without_worker_repeat(
    repository: Path, mode: str
) -> None:
    agents = AuditCorrectionAgents(mode)
    pipeline = Pipeline(repository, configuration(integrate=False), agents)
    state = pipeline.start("T100")
    assert state.state == State.AUDIT_PASS
    assert agents.worker_calls == 1 and agents.audit_attempts == 2
    assert state.fix_cycle == 0
    directory = pipeline.run_path("T100", state.run_id)
    rejected = list(directory.glob("*-auditor-*.rejected.json"))
    assert len(rejected) == 1
    assert state.artifact_digests[rejected[0].name] == digest(rejected[0].read_bytes())
    audit = read_json(directory / state.artifacts["audit"])
    assert isinstance(audit, dict) and audit["status"] == "PASS" and audit["findings"] == []
    if mode == "correct":
        assert audit["acceptance_criteria"][0]["evidence"] == (
            "Independent tests passed; informational evidence"
        )
    assert "findings" in agents.prompts[0] and "acceptance_criteria" in agents.prompts[0]


@pytest.mark.parametrize(
    "mode",
    ["persistent", "source_mutation", "state_mutation", "handoff_mutation", "tamper_rejected"],
)
def test_invalid_audit_correction_is_bounded_and_never_promotes(
    repository: Path, mode: str
) -> None:
    agents = AuditCorrectionAgents(mode)
    pipeline = Pipeline(repository, configuration(), agents)
    base = Git(repository).sha()
    state = pipeline.start("T100")
    assert state.state == State.FAILED
    assert agents.worker_calls == 1
    assert agents.audit_attempts == (
        3 if mode == "persistent" else 2 if mode == "tamper_rejected" else 1
    )
    assert state.fix_cycle == 0 and Git(repository).sha() == base
    assert "IntegrationReview" not in agents.calls
    directory = pipeline.run_path("T100", state.run_id)
    if mode == "persistent":
        rejected = list(directory.glob("*-auditor-*.rejected.json"))
        assert len(rejected) == 3
        assert all(state.artifact_digests[p.name] == digest(p.read_bytes()) for p in rejected)
        assert "Contradictory audit PASS" in (state.last_error or "")


def test_corrected_audit_real_failure_still_uses_worker_fix_loop(repository: Path) -> None:
    agents = AuditCorrectionAgents("real_fail")
    pipeline = Pipeline(repository, configuration(), agents)
    state = pipeline.start("T100")
    assert state.state == State.DONE
    assert agents.audit_attempts == 3
    assert agents.worker_calls == 2 and state.fix_cycle == 1
    assert "AUDIT REPORT CORRECTION" not in agents.prompts[2]
    first_audit = read_json(pipeline.run_path("T100", state.run_id) / "00-audit.json")
    assert isinstance(first_audit, dict) and first_audit["status"] == "FAIL"
    assert first_audit["findings"] == ["Actual defect remains"]


def test_failed_execution_cannot_be_hidden_by_audit_json_correction(repository: Path) -> None:
    agents = FakeAgents(failures=1, lie=True)
    state = Pipeline(repository, configuration(), agents).start("T100")
    assert state.state == State.FAILED
    assert agents.worker_calls == 1
    assert agents.calls.count("Audit") == 3
    assert "contradicts failed executable verification" in (state.last_error or "")
    assert "IntegrationReview" not in agents.calls


@pytest.mark.parametrize("supplied", ["omitted", "null", "finite"])
@pytest.mark.parametrize("failures", [0, 1])
def test_opt_in_timeout_reaches_roles_checks_and_saved_state(
    repository: Path, monkeypatch: pytest.MonkeyPatch, supplied: str, failures: int
) -> None:
    config_data = configuration().model_dump(mode="json")
    config_data.pop("timeout_seconds")
    if supplied != "omitted":
        config_data["timeout_seconds"] = 5400 if supplied == "finite" else None
    config = Config.model_validate(config_data)
    expected = 5400 if supplied == "finite" else None
    agents = FakeAgents(failures=failures, timeout=expected)
    observed: list[int | None] = []
    agent_timeouts: list[int | None] = []
    original_run = agents.run

    def run_agent(
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
        agent_timeouts.append(timeout)
        assert timeout == expected
        return original_run(
            prompt,
            cwd=cwd,
            role=role,
            timeout=timeout,
            output=output,
            artifacts=artifacts,
            name=name,
            readonly=readonly,
        )

    def run_check(
        command: list[str],
        cwd: Path,
        *,
        timeout: int | None = None,
        stdin: str | None = None,
    ) -> ProcessResult:
        if command[0] == "python":
            observed.append(timeout)
            assert timeout == expected
        return execute(command, cwd, timeout=timeout, stdin=stdin)

    monkeypatch.setattr(agents, "run", run_agent)
    monkeypatch.setattr("tools.orchestrator.workflow.execute", run_check)
    pipeline = Pipeline(repository, config, agents)
    state = pipeline.start("T100")
    assert state.state == State.DONE
    assert state.fix_cycle == failures
    # Three advisory calls inherit the same timeout on each initial/fix audit cycle.
    assert agent_timeouts == [expected] * (7 + 6 * failures)
    assert len(agents.reviewer_calls) == 3 * (1 + failures)
    assert observed and all(value == expected for value in observed)
    loaded = pipeline.status("T100", state.run_id)
    assert loaded.config is not None
    assert loaded.config.timeout_seconds == expected
    assert pipeline.resume("T100", state.run_id).state == State.DONE


@pytest.mark.parametrize("failures", [0, 1])
def test_relevant_skills_required_in_planner_worker_fix_and_auditor(
    repository: Path, failures: int
) -> None:
    class SkillAgents(FakeAgents):
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
            if output in {Plan, Fix, WorkerResult}:
                assert "REQUIRED AGENT SKILLS" in prompt
                assert "test-driven-development" in prompt
                assert "SKILL.md" in prompt
                assert "Do not commit" in prompt
            if output == Fix or (output == WorkerResult and self.worker_calls):
                assert "debugging-and-error-recovery" in prompt
            if output == Audit:
                assert "code-review-and-quality" in prompt
                assert "mention is not proof" in prompt
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

    pipeline = Pipeline(repository, configuration(), SkillAgents(failures=failures))
    state = pipeline.start("T100")
    assert state.state == State.DONE
    directory = pipeline.run_path("T100", state.run_id)
    assert "skills" in state.artifacts
    plan = Plan.model_validate(read_json(directory / state.artifacts["plan"]))
    assert "REQUIRED AGENT SKILLS" in plan.worker_prompt
    assert (directory / "worker_prompt.md").read_text() == plan.worker_prompt
    if failures:
        fix = Fix.model_validate(read_json(directory / state.artifacts["fix"]))
        assert "debugging-and-error-recovery" in fix.fix_prompt
        assert "REQUIRED AGENT SKILLS" in fix.fix_prompt


def test_missing_required_skill_does_not_invoke_worker(
    repository: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("AGENT_SKILLS_ROOT", str(tmp_path / "absent-pack"))
    agents = FakeAgents()
    state = Pipeline(repository, configuration(), agents).start("T100")
    assert state.state == State.FAILED
    assert "SETUP_FAILED" in (state.last_error or "")
    assert not agents.calls
    assert state.implementation_sha is None


@pytest.mark.parametrize("stage", [Plan, WorkerResult])
def test_skill_mutation_during_agent_execution_never_promotes(
    repository: Path, monkeypatch: pytest.MonkeyPatch, stage: type[BaseModel]
) -> None:
    agents = FakeAgents()
    original_run = agents.run

    def run_agent(
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
        result = original_run(
            prompt,
            cwd=cwd,
            role=role,
            timeout=timeout,
            output=output,
            artifacts=artifacts,
            name=name,
            readonly=readonly,
        )
        if output == stage:
            manifest = read_json(artifacts / "00-skills.json")
            assert isinstance(manifest, dict)
            skill = Path(manifest["worker"][0]["path"])
            skill.write_text(skill.read_text() + "Changed by agent\n")
        return result

    monkeypatch.setattr(agents, "run", run_agent)
    base = Git(repository).sha()
    state = Pipeline(repository, configuration(), agents).start("T100")
    assert state.state == State.FAILED
    assert "agent skill changed since planning" in (state.last_error or "")
    assert "Audit" not in agents.calls and "IntegrationReview" not in agents.calls
    assert Git(repository).sha() == base
    assert state.implementation_sha is None


def test_legacy_handoff_without_skills_resumes_unchanged(repository: Path) -> None:
    # Build a synthetic old run at a safe resume barrier, without a skill artifact.
    agents = FakeAgents()
    pipeline = Pipeline(repository, configuration(integrate=False), agents)
    state = pipeline.start("T100")
    assert state.state == State.AUDIT_PASS
    directory = pipeline.run_path("T100", state.run_id)
    skill_file = state.artifacts.pop("skills")
    state.artifact_digests.pop(skill_file)
    (directory / skill_file).unlink()
    pipeline.save(directory, state)
    handoff = (directory / "worker_prompt.md").read_bytes()
    assert pipeline.skill_handoff(directory, state, "Legacy prompt", "worker") == "Legacy prompt"
    assert pipeline.skill_manifest(directory, state) is None
    pipeline.config.integrate = True
    assert pipeline.resume("T100", state.run_id).state == State.DONE
    assert (directory / "worker_prompt.md").read_bytes() == handoff

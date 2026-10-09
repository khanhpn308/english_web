import json
import os
import re
import subprocess
import sys
import threading
from multiprocessing.connection import Connection as PipeConnection
from multiprocessing.synchronize import Barrier
from pathlib import Path
from typing import Literal, TypeVar

import pytest
from pydantic import BaseModel, ValidationError
from tools.orchestrator.core import (
    INTEGRATOR_CONTEXT_MAX_BYTES,
    KNOWN_ATTEMPT_ARTIFACT_SUFFIXES,
    Audit,
    AuditorContextV1,
    AuditorContract,
    Config,
    Contract,
    Criterion,
    EvidenceBundle,
    Fix,
    IntegrationReview,
    IntegratorContext,
    IntegratorContextOversizedError,
    IntegratorContextV1,
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
    check_integrator_context_size,
    digest,
    integrator_context_component_sizes,
    integrator_context_digest,
    read_json,
    serialize_integrator_context,
    task_card,
)
from tools.orchestrator.runtime import CliProvider, Git, ProcessResult, execute, lock
from tools.orchestrator.workflow import (
    Pipeline,
    build_integrator_prompt,
    materialize_private_toolchain,
)

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
        assert role.executable in {"fake-codex", "fake-agy"}
        assert timeout == self.timeout
        assert artifacts.is_dir()
        assert name
        if output == ReviewShard:
            assert readonly
            matched = re.search(r"REVIEW_PERSPECTIVE: ([^\n]+)", prompt)
            assert matched is not None
            perspective = ReviewPerspective(matched[1])
            self.reviewer_calls.append(perspective)
            return output.model_validate(
                ReviewShard(perspective=perspective, findings=[], probe_request=None)
            )
        self.calls.append(output.__name__)
        task_match = re.search(r'"task_id"\s*:\s*"(T[0-9]{3})"', prompt)
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
                reviewer_dispositions=[],
            )
        elif output == Fix:
            result = Fix(fix_prompt="Restore good behavior; keep contract unchanged.")
        elif output == IntegrationReview:
            matched = re.search(r'"source_branch":\s*"([^"]+)"', prompt) or re.search(
                r"SOURCE_BRANCH:\s*([^\n]+)", prompt
            )
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
        self.invoke_active = 0
        self.max_invoke_active = 0

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
        context: str | AuditorContextV1 | IntegratorContextV1,
        *,
        cwd: Path | None = None,
    ) -> BaseModel:
        assert threading.get_ident() == self.owner, "Pipeline.invoke called in reviewer thread"
        self.invoke_active += 1
        self.max_invoke_active = max(self.max_invoke_active, self.invoke_active)
        assert self.invoke_active == 1
        try:
            return super().invoke(directory, state, role_name, output, context, cwd=cwd)
        finally:
            self.invoke_active -= 1

    def verify(
        self,
        directory: Path,
        state: RunState,
        commands: list[list[str]],
        name: str,
        *,
        working: Path | None = None,
    ) -> None:
        assert threading.get_ident() == self.owner, "Mutable verify called in collection thread"
        super().verify(directory, state, commands, name, working=working)


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
                from tools.orchestrator.core import AuditorContextV1, EvidenceBundle

                assert "AUDITOR_CONTEXT:" in prompt
                payload = prompt.split("AUDITOR_CONTEXT:", 1)[1].lstrip()
                context_data, consumed = json.JSONDecoder().raw_decode(payload)
                trailing = payload[consumed:].strip()
                assert not trailing or trailing.startswith(
                    (
                        "AUDIT REPORT CORRECTION",
                        "Previous attempt failed validation/execution.",
                        "Previous attempt stalled with no progress.",
                    )
                )
                context = AuditorContextV1.model_validate(context_data)

                saved = RunState.model_validate(read_json(artifacts / "state.json"))
                evidence = EvidenceBundle.model_validate(
                    read_json(artifacts / saved.artifacts["evidence_bundle"])
                )

                assert context.evidence_bundle == evidence.semantic_payload()
                assert context.candidate_identity.source_digest == saved.verified_digest
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
        assert saved.current_agent == "concurrent_audit_preparation"
        assert saved.state == State.AUDIT_RUNNING
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
                    probe_request=None,
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


def test_t090_unsafe_worker_configuration_blocks_before_worker_handoff(repository: Path) -> None:
    config = configuration(integrate=False)
    config.roles["worker"] = Role(provider="agy", executable="fake-agy", allow_process=True)
    agents = FakeAgents()
    pipeline = Pipeline(repository, config, agents)
    state = pipeline.start("T100", defer_verification=True)
    assert state.state == State.BLOCKED
    assert "T090 BLOCKED" in (state.last_error or "")
    assert agents.calls == ["Plan"]


def test_explicit_host_verification_is_deferred_until_requested(repository: Path) -> None:
    agents = FakeAgents()
    pipeline = Pipeline(repository, configuration(integrate=False), agents)
    state = pipeline.start("T100", defer_verification=True)
    assert state.state == State.IMPLEMENTED
    assert agents.calls == ["Plan", "WorkerResult"]
    assert "audit_checks" not in state.artifacts

    # A normal resume cannot silently run tests after a Worker handoff.
    pending = pipeline.resume("T100", state.run_id, defer_verification=True)
    assert pending.state == State.IMPLEMENTED
    assert agents.calls == ["Plan", "WorkerResult"]

    # Only the separately authorized host verification advances the state.
    verified = pipeline.resume(
        "T100", state.run_id, defer_verification=False, stop_after_audit=True
    )
    assert verified.state == State.AUDIT_PASS
    assert verified.verified_digest == verified.audited_digest
    assert agents.calls == ["Plan", "WorkerResult", "Audit"]


def test_explicit_host_verification_stops_before_automatic_fix(repository: Path) -> None:
    agents = FakeAgents(failures=1)
    pipeline = Pipeline(repository, configuration(integrate=False), agents)
    first = pipeline.start("T100", defer_verification=True)
    assert first.state == State.IMPLEMENTED

    audited = pipeline.resume("T100", first.run_id, defer_verification=False, stop_after_audit=True)
    assert audited.state == State.AUDIT_FAIL
    assert agents.worker_calls == 1
    assert "Fix" not in agents.calls

    # The next host resume explicitly dispatches the Fix Worker, not tests.
    fixed = pipeline.resume("T100", first.run_id, defer_verification=True)
    assert fixed.state == State.IMPLEMENTED
    assert agents.worker_calls == 2
    assert agents.calls[-2:] == ["Fix", "WorkerResult"]
    assert fixed.verified_digest == ""


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
            context: str | AuditorContextV1 | IntegratorContextV1,
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
    assert retried[0].state == State.IMPLEMENTED
    assert "audit_checks" not in retried[0].artifacts
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "orchestrator",
            "verify-candidate",
            "T100",
            "--run-id",
            retried[0].run_id,
            "--no-integrate",
        ],
    )
    assert main() == 0
    assert pipeline.status("T100", retried[0].run_id).state == State.AUDIT_PASS


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

    assert "official verification" in ROLE_RULES
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
def test_run_recovers_known_gemini_trust_failure_only(
    repository: Path, unsafe: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The fixture reproduces pre-policy Gemini history. Production dispatch
    # remains covered by test_worker_configuration_rejects_non_code_only.
    monkeypatch.setattr("tools.orchestrator.runtime.is_worker_code_only", lambda _role: True)
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
    repository: Path, unsafe: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Preserve coverage of historical failover semantics without granting
    # unsafe permissions to any production Worker.
    monkeypatch.setattr("tools.orchestrator.runtime.is_worker_code_only", lambda _role: True)
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


class ConcurrentAuditAgents(FakeAgents):
    """Four-party rendezvous and explicit lane ordering; no timing-based proof."""

    def __init__(self, mode: str) -> None:
        super().__init__()
        self.mode = mode
        self.barrier = threading.Barrier(4, timeout=10)
        self.collection_done = threading.Event()
        self.finished = [threading.Event() for _ in ReviewPerspective]
        self.mutex = threading.Lock()
        self.active = 0
        self.max_active = 0
        self.completions: list[ReviewPerspective] = []
        self.audit_prompts: list[str] = []
        self.pipeline: AuthorityProbePipeline | None = None
        self.command_order: list[str] = []
        self.phase_saves = 0
        self.verification_cwds: list[Path] = []
        self.verification_saw_transient: list[bool] = []
        self.reviewer_cwds: list[Path] = []
        self.observed_transients: list[bool] = []
        self.reviewer_prompts: list[str] = []

    def enter(self, *, rendezvous: bool = True) -> None:
        with self.mutex:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        if rendezvous:
            self.barrier.wait()

    def leave(self) -> None:
        with self.mutex:
            self.active -= 1

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
            if output == Audit:
                assert self.collection_done.is_set()
                assert all(event.is_set() for event in self.finished)
                assert self.active == 0
                self.audit_prompts.append(prompt)
                saved = RunState.model_validate(read_json(artifacts / "state.json"))
                assert saved.current_agent == "auditor"
                from tools.orchestrator.core import AuditorContextV1, EvidenceBundle

                bundle = ReviewBundle.model_validate(
                    read_json(artifacts / saved.artifacts["review_bundle"])
                )
                evidence = EvidenceBundle.model_validate(
                    read_json(artifacts / saved.artifacts["evidence_bundle"])
                )

                assert "AUDITOR_CONTEXT:" in prompt
                payload = prompt.split("AUDITOR_CONTEXT:", 1)[1].lstrip()
                context_data, consumed = json.JSONDecoder().raw_decode(payload)
                trailing = payload[consumed:].strip()
                assert not trailing or trailing.startswith(
                    (
                        "AUDIT REPORT CORRECTION",
                        "Previous attempt failed validation/execution.",
                        "Previous attempt stalled with no progress.",
                    )
                )
                context = AuditorContextV1.model_validate(context_data)

                assert context.review_bundle == bundle
                assert context.evidence_bundle == evidence.semantic_payload()
                assert context.candidate_identity.source_digest == saved.verified_digest
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
                data = result.model_dump()
                data["reviewer_dispositions"] = [
                    {
                        "finding_id": shard.findings[0].finding_id,
                        "disposition": "dismissed",
                        "evidence": "Synthetic source refutes claim",
                    }
                    for shard in bundle.shards
                ]
                if self.mode == "regression_fail":
                    data.update(
                        status="FAIL",
                        findings=["Executable check failed"],
                        required_fixes=["Repair failed command"],
                    )
                    data["acceptance_criteria"][0]["status"] = "FAIL"
                return output.model_validate(data)
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
        assert readonly and role.model == "configured-future-auditor-model"
        assert "STATIC REVIEW ONLY" in prompt and "transient" in prompt
        assert '"results"' not in prompt and "Worker and executable evidence" not in prompt
        match = re.search(r"REVIEW_PERSPECTIVE: ([^\n]+)", prompt)
        assert match is not None
        perspective = ReviewPerspective(match[1])
        if name.startswith("probe"):
            transient_path = cwd / ".pytest_cache/transient"
            findings = []
            if transient_path.is_file():
                findings.append(
                    ReviewFinding(
                        action=f"Transient finding in {perspective}",
                        evidence=".pytest_cache/transient:1",
                    )
                )
            findings.append(ReviewFinding(action=f"Check {perspective}", evidence="feature.txt:1"))
            return output.model_validate(
                ReviewShard(
                    perspective=perspective,
                    findings=findings,
                    probe_request=None,
                )
            )
        self.reviewer_prompts.append(prompt)
        assert len(list(artifacts.glob("00-review-*.prompt.md"))) == 3
        saved = RunState.model_validate(read_json(artifacts / "state.json"))
        assert saved.current_agent == "concurrent_audit_preparation"
        assert "audit_checks" not in saved.artifacts
        index = list(ReviewPerspective).index(perspective)
        self.enter()
        try:
            if self.mode == "verification_first":
                assert self.collection_done.wait(10)
                assert not self.audit_prompts
            if index < 2:
                assert self.finished[index + 1].wait(10)
            if index == 1:
                if self.mode == "review_failure":
                    raise OrchestratorError("Agent process failed: synthetic")
                if self.mode == "source":
                    (cwd / "feature.txt").write_text("tampered")
                elif self.mode == "branch":
                    Git(cwd).run("symbolic-ref", "HEAD", "refs/heads/main")
                elif self.mode == "state":
                    path = artifacts / "state.json"
                    path.write_bytes(path.read_bytes() + b" ")
                elif self.mode == "artifact":
                    (artifacts / "00-contract.json").write_text("tampered")
                elif self.mode == "memory":
                    assert self.pipeline is not None and self.pipeline.live_state is not None
                    self.pipeline.live_state.state = State.DONE
                    self.pipeline.live_state.artifacts = {}
            atomic_json(artifacts / f"{name}.log.json", {"synthetic": True})
            self.reviewer_cwds.append(cwd)
            transient_path = cwd / ".pytest_cache/transient"
            transient_found = transient_path.is_file()
            self.observed_transients.append(transient_found)
            findings = []
            if transient_found:
                findings.append(
                    ReviewFinding(
                        action=f"Transient finding in {perspective}",
                        evidence=".pytest_cache/transient:1",
                    )
                )
            findings.append(ReviewFinding(action=f"Check {perspective}", evidence="feature.txt:1"))
            return output.model_validate(
                ReviewShard(
                    perspective=perspective,
                    findings=findings,
                    probe_request=None,
                )
            )
        finally:
            self.leave()
            self.completions.append(perspective)
            self.finished[index].set()


def concurrent_audit_pipeline(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    agents: ConcurrentAuditAgents | None = None,
) -> tuple[AuthorityProbePipeline, ConcurrentAuditAgents]:
    from tools.orchestrator import workflow

    agents = agents or ConcurrentAuditAgents(mode)
    config = configuration(integrate=False, cycles=0)
    config.roles["auditor"].model = "configured-future-auditor-model"
    config.verification = [["python", "-m", "ruff", "check", "."], ["python", "-m", "mypy", "."]]
    pipeline = AuthorityProbePipeline(repository, config, agents)
    agents.pipeline = pipeline
    from tools.orchestrator.core import VerificationCollection, VerificationRequest
    from tools.orchestrator.runtime import execute as original_execute

    collect = workflow.collect_verification

    def collecting(request: VerificationRequest) -> VerificationCollection:
        assert threading.get_ident() != pipeline.owner
        agents.enter(rendezvous=False)
        try:
            return collect(request)
        finally:
            agents.leave()
            agents.collection_done.set()

    def executing(command: list[str], cwd: Path, *, timeout: int | None = None) -> ProcessResult:
        if command[0] == "git":
            return original_execute(command, cwd, timeout=timeout)
        assert timeout == 30
        assert pipeline.live_state is not None
        concurrent = pipeline.live_state.current_agent == "concurrent_audit_preparation"
        if concurrent:
            assert threading.get_ident() != pipeline.owner
            if not agents.command_order:
                agents.barrier.wait()
                if mode == "reviewers_first":
                    assert all(event.wait(10) for event in agents.finished)
            target_cmd = command[2:] if command[0].endswith("env") else command
            check_name = target_cmd[2] if len(target_cmd) > 2 else target_cmd[0]
            agents.command_order.append(check_name)
            if mode == "setup" and check_name == "ruff":
                raise OrchestratorError("Executable unavailable: synthetic")
            if mode == "verification_source":
                (cwd / "feature.txt").write_text("verification mutation")
            (cwd / ".pytest_cache").mkdir(exist_ok=True)
            (cwd / ".pytest_cache/transient").write_text("ignored verification output")
            agents.verification_cwds.append(cwd)
            agents.verification_saw_transient.append((cwd / ".pytest_cache/transient").is_file())
        failed = concurrent and mode in {
            "regression_pass",
            "regression_fail",
            "timeout",
            "oversized",
        }
        return ProcessResult(
            command=tuple(command),
            cwd=str(cwd),
            started_at="start",
            ended_at="end",
            exit_code=7 if failed else 0,
            stdout="synthetic output",
            stderr="",
            timed_out=concurrent and mode == "timeout",
            oversized=concurrent and mode == "oversized",
        )

    save = pipeline.save

    def saving(directory: Path, state: RunState) -> None:
        if state.current_agent == "concurrent_audit_preparation":
            agents.phase_saves += 1
        save(directory, state)

    monkeypatch.setattr(workflow, "collect_verification", collecting)
    monkeypatch.setattr(workflow, "execute", executing)
    monkeypatch.setattr(pipeline, "save", saving)
    return pipeline, agents


@pytest.mark.parametrize("mode", ["verification_first", "reviewers_first"])
def test_concurrent_audit_overlap_ordering_and_final_barrier(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    pipeline, agents = concurrent_audit_pipeline(repository, monkeypatch, mode)
    state = pipeline.start("T100")
    assert state.state == State.AUDIT_PASS, state.last_error
    assert agents.max_active == 4 and agents.active == 0
    assert agents.phase_saves == 1
    assert pipeline.max_invoke_active == 1 and pipeline.invoke_active == 0
    assert agents.completions == list(reversed(ReviewPerspective))
    assert agents.command_order == ["pytest", "ruff", "mypy"]
    assert len(agents.audit_prompts) == 1
    directory = pipeline.run_path("T100", state.run_id)
    checks = read_json(directory / state.artifacts["audit_checks"])
    assert isinstance(checks, dict)
    assert [item["command_index"] for item in checks["results"]] == [0, 1, 2]
    assert checks["source_digest"] == state.verified_digest == state.audited_digest
    assert all("stdout" not in item and "stderr" not in item for item in checks["results"])
    bundle = ReviewBundle.model_validate(read_json(directory / state.artifacts["review_bundle"]))
    assert [shard.perspective for shard in bundle.shards] == list(ReviewPerspective)
    assert [shard.findings[0].finding_id for shard in bundle.shards] == [
        f"{perspective}:0001" for perspective in ReviewPerspective
    ]
    pipeline.check_artifacts(directory, state)


@pytest.mark.parametrize(
    "mode,reason",
    [
        ("review_failure", "incomplete"),
        ("setup", "SETUP_FAILED"),
        ("source", "repository source"),
        ("verification_source", "repository source"),
        ("branch", "changed branch"),
        ("state", "protected evidence or state"),
        ("artifact", "protected evidence or state"),
        ("memory", "in-memory orchestration state"),
    ],
)
def test_concurrent_audit_failures_reap_all_lanes(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    reason: str,
) -> None:
    pipeline, agents = concurrent_audit_pipeline(repository, monkeypatch, mode)
    state = pipeline.start("T100")
    assert state.state == State.FAILED and reason in (state.last_error or "")
    assert agents.max_active == 4 and agents.active == 0
    assert agents.collection_done.is_set() and all(event.is_set() for event in agents.finished)
    assert agents.completions == list(reversed(ReviewPerspective))
    assert not agents.audit_prompts and "review_bundle" not in state.artifacts
    if mode in {"setup", "review_failure"}:
        directory = pipeline.run_path("T100", state.run_id)
        pipeline.check_artifacts(directory, state)
        assert "audit_checks" in state.artifacts
        assert len([name for name in state.artifacts if name.endswith(".log.json")]) == (
            2 if mode == "review_failure" else 3
        )
        assert agents.command_order == (
            ["pytest", "ruff"] if mode == "setup" else ["pytest", "ruff", "mypy"]
        )


@pytest.mark.parametrize("mode", ["regression_pass", "regression_fail", "timeout", "oversized"])
def test_concurrent_audit_regression_evidence_and_pass_rejection(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    pipeline, agents = concurrent_audit_pipeline(repository, monkeypatch, mode)
    state = pipeline.start("T100")
    assert state.state == State.FAILED
    assert agents.collection_done.is_set() and all(event.is_set() for event in agents.finished)
    assert agents.command_order == ["pytest"]  # Existing stop-at-first-failed-command semantics.
    assert len(agents.audit_prompts) == (1 if mode == "regression_fail" else 3)
    assert (
        "Maximum fix" in (state.last_error or "")
        if mode == "regression_fail"
        else "contradicts failed" in (state.last_error or "")
    )
    directory = pipeline.run_path("T100", state.run_id)
    checks = read_json(directory / state.artifacts["audit_checks"])
    assert isinstance(checks, dict)
    assert len(checks["results"]) == 1 and checks["results"][0]["exit_code"] == 7
    assert checks["results"][0]["timed_out"] is (mode == "timeout")
    assert checks["results"][0]["oversized"] is (mode == "oversized")
    assert "review_bundle" in state.artifacts
    assert ("audit" in state.artifacts) is (mode == "regression_fail")


@pytest.mark.parametrize("mode", ["verification_first", "reviewers_first"])
def test_concurrent_audit_transient_boundary_and_stable_finding_ids(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    pipeline, agents = concurrent_audit_pipeline(repository, monkeypatch, mode)
    state = pipeline.start("T100")
    assert state.state == State.AUDIT_PASS, state.last_error
    # 1. Assert verification sees and creates the transient file in its own cwd
    assert agents.verification_cwds
    assert agents.verification_saw_transient
    assert all(saw is True for saw in agents.verification_saw_transient)
    # The temporary verification workspace is cleaned up after verification completes:
    assert all(not c.exists() for c in agents.verification_cwds)
    # 2. Assert reviewer does NOT see it from its reviewer cwd (workspace boundary)
    assert len(agents.observed_transients) == 3
    assert all(observed is False for observed in agents.observed_transients)
    assert not (Path(state.worktree_path) / ".pytest_cache/transient").exists()
    assert all(cwd == Path(state.worktree_path) for cwd in agents.reviewer_cwds)
    assert all(c != Path(state.worktree_path) for c in agents.verification_cwds)
    # 3. Assert transient content does not appear in ReviewShard or ReviewBundle
    directory = pipeline.run_path("T100", state.run_id)
    bundle = ReviewBundle.model_validate(read_json(directory / state.artifacts["review_bundle"]))
    for shard in bundle.shards:
        assert len(shard.findings) == 1
        assert shard.findings[0].finding_id == f"{shard.perspective}:0001"
        assert shard.findings[0].action == f"Check {shard.perspective}"
        assert shard.findings[0].evidence == "feature.txt:1"
        assert ".pytest_cache" not in shard.findings[0].evidence
        assert "transient" not in shard.findings[0].evidence
    # 4. Assert transient content is not delivered to final Auditor
    assert len(agents.audit_prompts) == 1
    assert ".pytest_cache" not in agents.audit_prompts[0]
    assert "transient" not in agents.audit_prompts[0]
    # 5. Counterfactual probe verification: prove probe WOULD observe transient and shift IDs
    # if boundary were removed and probe was invoked in a directory with transient output
    unisolated_dir = repository.parent / f"unisolated-{mode}"
    unisolated_dir.mkdir(exist_ok=True)
    (unisolated_dir / "feature.txt").write_text("good\n")
    (unisolated_dir / ".pytest_cache").mkdir(exist_ok=True)
    (unisolated_dir / ".pytest_cache/transient").write_text("ignored verification output")
    counterfactual = agents.run(
        agents.reviewer_prompts[0],
        cwd=unisolated_dir,
        role=pipeline.config.roles["auditor"],
        timeout=30,
        output=ReviewShard,
        artifacts=directory,
        name=f"probe-{mode}",
        readonly=True,
    )
    assert isinstance(counterfactual, ReviewShard)
    assert len(counterfactual.findings) == 2
    assert counterfactual.findings[0].evidence == ".pytest_cache/transient:1"
    # If bundled in same cwd, the source finding would shift to :0002:
    counterfactual_bundle = ReviewBundle.assemble(
        state.verified_digest,
        state.worktree_branch,
        [
            counterfactual,
            *[
                ReviewShard(
                    perspective=shard.perspective,
                    findings=[
                        ReviewFinding(action=item.action, evidence=item.evidence)
                        for item in shard.findings
                    ],
                    probe_request=None,
                )
                for shard in bundle.shards
                if shard.perspective != counterfactual.perspective
            ],
        ],
    )
    shifted = next(
        s for s in counterfactual_bundle.shards if s.perspective == counterfactual.perspective
    )
    assert shifted.findings[0].finding_id == f"{counterfactual.perspective}:0001"
    assert shifted.findings[0].evidence == ".pytest_cache/transient:1"
    assert shifted.findings[1].finding_id == f"{counterfactual.perspective}:0002"
    assert shifted.findings[1].evidence == "feature.txt:1"


def test_concurrent_audit_toolchain_unsafe_backlink_fails_closed(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (repository / ".gitignore").write_text(
        (repository / ".gitignore").read_text() + "node_modules/\n.venv/\n"
    )
    Git(repository).run("add", ".gitignore")
    Git(repository).run("commit", "-m", "ignore local toolchains")

    class UnsafeBacklinkAgents(ConcurrentAuditAgents):
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
                # Reproduce the exact independent audit finding:
                # node_modules/local-candidate -> reviewer/task worktree
                nm = cwd / "node_modules"
                nm.mkdir(parents=True, exist_ok=True)
                (nm / "local-candidate").symlink_to(cwd)
            return result

    agents = UnsafeBacklinkAgents("verification_first")
    pipeline, returned_agents = concurrent_audit_pipeline(
        repository, monkeypatch, "verification_first", agents=agents
    )
    assert returned_agents is agents

    state = pipeline.start("T100")
    assert state.state == State.FAILED
    assert "Unsafe toolchain backlink" in (state.last_error or "")
    assert len(agents.reviewer_cwds) == 0
    assert len(agents.verification_cwds) == 0
    assert "review_bundle" not in state.artifacts
    assert len(agents.audit_prompts) == 0
    assert Git(repository).snapshot(state.base_sha) is not None


def test_concurrent_audit_toolchain_safe_shared_toolchains_work(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (repository / ".gitignore").write_text(
        (repository / ".gitignore").read_text() + "node_modules/\n.venv/\n"
    )
    Git(repository).run("add", ".gitignore")
    Git(repository).run("commit", "-m", "ignore local toolchains")

    class SafeToolchainAgents(ConcurrentAuditAgents):
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
                # Safe node_modules with internal symlink
                nm = cwd / "node_modules"
                (nm / "typescript/bin").mkdir(parents=True, exist_ok=True)
                (nm / "typescript/bin/tsc").write_text("console.log('tsc');\n")
                (nm / ".bin").mkdir(parents=True, exist_ok=True)
                (nm / ".bin/tsc").symlink_to("../typescript/bin/tsc")

                # Safe .venv with system interpreter link
                venv = cwd / ".venv"
                bin_dir = venv / ("Scripts" if os.name == "nt" else "bin")
                bin_dir.mkdir(parents=True, exist_ok=True)
                (bin_dir / "python").symlink_to(Path(sys.executable).resolve())
            return result

    agents = SafeToolchainAgents("verification_first")
    pipeline, returned_agents = concurrent_audit_pipeline(
        repository, monkeypatch, "verification_first", agents=agents
    )
    assert returned_agents is agents

    state = pipeline.start("T100")
    assert state.state == State.AUDIT_PASS, state.last_error
    assert len(agents.reviewer_cwds) == 3
    assert len(agents.verification_cwds) > 0
    assert "review_bundle" in state.artifacts
    assert len(agents.audit_prompts) == 1


def test_concurrent_audit_materialization_distinct_staged_and_working_content(
    repository: Path,
) -> None:
    git = Git(repository)
    base_sha = git.sha()
    worktree_path = repository.parent / "test-worktree-distinct"
    git.create_worktree(worktree_path, "feature-distinct", base_sha)
    worktree_git = Git(worktree_path)

    target_file = worktree_path / "distinct.txt"
    target_file.write_text("value 0\n")
    worktree_git.run("add", "distinct.txt")
    worktree_git.run("commit", "-m", "base value 0")
    distinct_base = worktree_git.sha()

    target_file.write_text("value 1\n")
    worktree_git.run("add", "distinct.txt")
    target_file.write_text("value 2\n")

    frozen_digest = worktree_git.snapshot(distinct_base)
    pipeline = Pipeline(repository, configuration(), FakeAgents())

    with pipeline.verification_workspace(
        worktree_path, frozen_digest, distinct_base, "T100", "run-1"
    ) as (verify_path, verify_git):
        # 1. Assert independently sandbox cached/index content == "value 1\n"
        sandbox_index_diff = verify_git.run("diff", "--cached", "--binary", distinct_base, "--")
        original_index_diff = worktree_git.run("diff", "--cached", "--binary", distinct_base, "--")
        assert sandbox_index_diff == original_index_diff
        assert "value 1" in sandbox_index_diff
        assert "value 2" not in sandbox_index_diff

        # 2. Assert independently sandbox working content == "value 2\n"
        assert (verify_path / "distinct.txt").read_text() == "value 2\n"

        # 3. Assert sandbox snapshot == original frozen snapshot before any test execution
        assert verify_git.snapshot(distinct_base) == frozen_digest


def test_concurrent_audit_materialization_binary_mode_and_deletion(
    repository: Path,
) -> None:
    git = Git(repository)
    base_sha = git.sha()
    worktree_path = repository.parent / "test-worktree-binary-mode-del"
    git.create_worktree(worktree_path, "feature-bmd", base_sha)
    worktree_git = Git(worktree_path)

    (worktree_path / "binary.bin").write_bytes(bytes(range(256)))
    (worktree_path / "staged_delete.txt").write_text("delete staged\n")
    (worktree_path / "unstaged_delete.txt").write_text("delete unstaged\n")
    (worktree_path / "script.sh").write_text("#!/bin/sh\necho hi\n")
    worktree_git.run("add", ".")
    worktree_git.run("commit", "-m", "initial files for c4")
    c4_base = worktree_git.sha()

    (worktree_path / "binary.bin").write_bytes(b"staged" + bytes(range(128)))
    worktree_git.run("add", "binary.bin")
    (worktree_path / "binary.bin").write_bytes(b"working" + bytes(range(64)))

    worktree_git.run("rm", "staged_delete.txt")
    (worktree_path / "unstaged_delete.txt").unlink()

    (worktree_path / "script.sh").chmod(0o755)
    worktree_git.run("add", "script.sh")

    nested_dir = worktree_path / "nested/sub"
    nested_dir.mkdir(parents=True)
    untracked = nested_dir / "candidate.txt"
    untracked.write_text("untracked payload\n")
    untracked.chmod(0o755)

    cache_dir = worktree_path / ".pytest_cache"
    cache_dir.mkdir(parents=True)
    (cache_dir / "transient").write_text("transient cache\n")

    frozen_digest = worktree_git.snapshot(c4_base)
    pipeline = Pipeline(repository, configuration(), FakeAgents())

    with pipeline.verification_workspace(
        worktree_path, frozen_digest, c4_base, "T100", "run-1"
    ) as (verify_path, verify_git):
        assert verify_git.snapshot(c4_base) == frozen_digest
        assert (verify_path / "binary.bin").read_bytes() == b"working" + bytes(range(64))
        assert not (verify_path / "staged_delete.txt").exists()
        assert not (verify_path / "unstaged_delete.txt").exists()
        assert (verify_path / "script.sh").stat().st_mode & 0o111 != 0
        assert (verify_path / "nested/sub/candidate.txt").is_file()
        assert (verify_path / "nested/sub/candidate.txt").read_text() == "untracked payload\n"
        assert not (verify_path / ".pytest_cache").exists()


def _ignore_toolchains(repo: Path) -> str:
    gi = repo / ".gitignore"
    gi.write_text(gi.read_text() + "node_modules\nnode_modules/\n.venv\n.venv/\n")
    git = Git(repo)
    git.run("add", ".gitignore")
    git.run("commit", "-m", "ignore toolchains")
    return git.sha()


def test_concurrent_audit_private_toolchain_root_symlink_parent_traversal(
    repository: Path,
) -> None:
    git = Git(repository)
    base_sha = _ignore_toolchains(repository)
    worktree_path = repository.parent / "test-worktree-parent-traversal"
    git.create_worktree(worktree_path, "feature-parent-traversal", base_sha)
    worktree_git = Git(worktree_path)

    nm = worktree_path / "node_modules"
    (nm / "pkg/bin").mkdir(parents=True)
    (nm / "pkg/bin/run.js").write_text("console.log('pkg');\n")

    frozen_digest = worktree_git.snapshot(base_sha)
    pipeline = Pipeline(repository, configuration(), FakeAgents())

    with pipeline.verification_workspace(
        worktree_path, frozen_digest, base_sha, "T100", "run-1"
    ) as (verify_path, _):
        assert (verify_path / "node_modules").is_dir()
        assert not (verify_path / "node_modules").is_symlink()

        parent_dir = (verify_path / "node_modules" / "..").resolve()
        assert parent_dir == verify_path.resolve()
        assert parent_dir != worktree_path.resolve()

        transient_file = verify_path / "node_modules/../.pytest_cache/transient"
        transient_file.parent.mkdir(parents=True, exist_ok=True)
        transient_file.write_text("transient verification data\n")

        assert (verify_path / ".pytest_cache/transient").exists()
        assert not (worktree_path / ".pytest_cache/transient").exists()
        assert not (worktree_path / ".pytest_cache").exists()


def test_concurrent_audit_private_toolchain_node_modules_root_alias(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base_sha = _ignore_toolchains(repository)

    worktree_path = repository.parent / "test-worktree-nm-symlink-src"
    Git(repository).create_worktree(worktree_path, "feature-nm-symlink", base_sha)
    repo_nm = repository / "node_modules"
    (repo_nm / "real-pkg").mkdir(parents=True, exist_ok=True)
    (repo_nm / "real-pkg/index.js").write_text("module.exports = 1;\n")
    (worktree_path / "node_modules").symlink_to(repo_nm)
    pipeline = Pipeline(repository, configuration(), FakeAgents())
    frozen_digest = Git(worktree_path).snapshot(base_sha)
    with pipeline.verification_workspace(
        worktree_path, frozen_digest, base_sha, "T100", "run-symlink-src"
    ) as (verify_path, _):
        assert (verify_path / "node_modules").is_dir()
        assert not (verify_path / "node_modules").is_symlink()
        assert (verify_path / "node_modules/real-pkg/index.js").is_file()

    class RootAliasAgents(ConcurrentAuditAgents):
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
                cache_dir = cwd / ".pytest_cache"
                cache_dir.mkdir(parents=True, exist_ok=True)
                (cache_dir / "marker.txt").write_text("SECRET_REVIEWER_MARKER\n")
                nm_alias = cwd / "node_modules"
                if nm_alias.exists() or nm_alias.is_symlink():
                    nm_alias.unlink()
                nm_alias.symlink_to(cache_dir)
            return result

    agents = RootAliasAgents("verification_first")
    pipeline, returned_agents = concurrent_audit_pipeline(
        repository, monkeypatch, "verification_first", agents=agents
    )
    assert returned_agents is agents
    state = pipeline.start("T100")
    assert state.state == State.FAILED
    assert "Unsafe toolchain root" in (state.last_error or "")
    assert len(agents.reviewer_cwds) == 0
    assert len(agents.verification_cwds) == 0
    assert "review_bundle" not in state.artifacts
    assert len(agents.audit_prompts) == 0
    directory = pipeline.run_path("T100", state.run_id)
    assert not any(
        "SECRET_REVIEWER_MARKER" in p.read_text(errors="replace") for p in directory.glob("*.json")
    )


def test_concurrent_audit_private_toolchain_unreadable_directory_fails_closed(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ignore_toolchains(repository)

    class UnreadableToolchainAgents(ConcurrentAuditAgents):
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
                nm = cwd / "node_modules"
                (nm / "secret_sub").mkdir(parents=True, exist_ok=True)
                (nm / "secret_sub/file.js").write_text("console.log(1);\n")
            return result

    agents = UnreadableToolchainAgents("verification_first")
    pipeline, returned_agents = concurrent_audit_pipeline(
        repository, monkeypatch, "verification_first", agents=agents
    )
    assert returned_agents is agents

    real_scandir = os.scandir

    def faulty_scandir(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes] | int = ".",
    ) -> object:
        path_str = str(path)
        if "secret_sub" in path_str:
            raise PermissionError("Simulated permission denied on toolchain inspection")
        return real_scandir(path)

    monkeypatch.setattr(os, "scandir", faulty_scandir)

    state = pipeline.start("T100")
    assert state.state == State.FAILED
    assert "Unreadable toolchain directory" in (state.last_error or "")
    assert len(agents.reviewer_cwds) == 0
    assert len(agents.verification_cwds) == 0
    assert "review_bundle" not in state.artifacts
    assert len(agents.audit_prompts) == 0


def test_concurrent_audit_root_discovery_whitespace_sensitive_and_failure(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    git = Git(repository)
    base_sha = git.sha()

    space_worktree = repository.parent / "worktree_with_trailing_space   "
    git.create_worktree(space_worktree, "space-branch", base_sha)
    pipeline = Pipeline(repository, configuration(), FakeAgents())

    roots = pipeline.authoritative_roots(space_worktree)
    assert space_worktree.resolve() in roots

    test_tree = repository.parent / "test-worktree-backlink-space"
    git.create_worktree(test_tree, "feature-backlink-space", base_sha)
    nm = test_tree / "node_modules"
    nm.mkdir(parents=True)
    (nm / "backlink").symlink_to(space_worktree)

    with pytest.raises(OrchestratorError, match="Unsafe toolchain backlink"):
        materialize_private_toolchain(
            nm,
            test_tree / "sandbox_nm",
            roots,
            "node_modules",
            repo_root=repository,
            working_root=test_tree,
        )

    def faulty_run(*args: str, preserve_newlines: bool = False) -> str:
        if args and args[0] == "worktree":
            raise OrchestratorError("Simulated git worktree list failure")
        return git.run(*args, preserve_newlines=preserve_newlines)

    monkeypatch.setattr(pipeline.git, "run", faulty_run)
    with pytest.raises(OrchestratorError, match="Failed to discover registered worktrees"):
        pipeline.authoritative_roots(space_worktree)


def test_concurrent_audit_private_toolchain_no_shell_launcher_or_injection(
    repository: Path,
) -> None:
    git = Git(repository)
    base_sha = _ignore_toolchains(repository)
    worktree_path = repository.parent / "test-worktree-no-launcher"
    git.create_worktree(worktree_path, "feature-no-launcher", base_sha)

    venv = worktree_path / ".venv"
    bin_dir = venv / ("Scripts" if os.name == "nt" else "bin")
    bin_dir.mkdir(parents=True)
    (bin_dir / "python").symlink_to(Path(sys.executable).resolve())

    injection_name = "$(touch LAUNCHER_INJECTION)"
    (bin_dir / injection_name).write_text("payload\n")

    frozen_digest = Git(worktree_path).snapshot(base_sha)
    pipeline = Pipeline(repository, configuration(), FakeAgents())

    with pipeline.verification_workspace(
        worktree_path, frozen_digest, base_sha, "T100", "run-no-launcher"
    ) as (verify_path, _):
        python_exe = verify_path / ".venv" / ("Scripts/python" if os.name == "nt" else "bin/python")
        assert python_exe.exists()
        if python_exe.is_symlink():
            target = python_exe.resolve()
            assert target == Path(sys.executable).resolve()
        else:
            header = python_exe.read_bytes()[:16]
            assert b"#!/bin/sh" not in header

        assert not (worktree_path / "LAUNCHER_INJECTION").exists()
        assert not (repository / "LAUNCHER_INJECTION").exists()
        assert not (verify_path / "LAUNCHER_INJECTION").exists()
        assert not Path("LAUNCHER_INJECTION").exists()


def test_concurrent_audit_private_toolchain_real_venv_package_preservation(
    repository: Path,
) -> None:
    git = Git(repository)
    base_sha = _ignore_toolchains(repository)
    worktree_path = repository.parent / "test-worktree-real-venv"
    git.create_worktree(worktree_path, "feature-real-venv", base_sha)

    venv = worktree_path / ".venv"
    bin_dir = venv / ("Scripts" if os.name == "nt" else "bin")
    bin_dir.mkdir(parents=True)
    (bin_dir / "python").symlink_to(Path(sys.executable).resolve())
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}"
    sp = (
        venv / "Lib" / "site-packages"
        if os.name == "nt"
        else venv / "lib" / f"python{py_ver}" / "site-packages"
    )
    (sp / "pytest").mkdir(parents=True)
    (sp / "pytest" / "__init__.py").write_text(f"__version__ = {pytest.__version__!r}\n")
    (venv / "pyvenv.cfg").write_text(
        f"home = {Path(sys.executable).resolve().parent}\n"
        "include-system-site-packages = false\n"
        f"version = {py_ver}\n"
    )

    frozen_digest = Git(worktree_path).snapshot(base_sha)
    pipeline = Pipeline(repository, configuration(), FakeAgents())

    with pipeline.verification_workspace(
        worktree_path, frozen_digest, base_sha, "T100", "run-real-venv"
    ) as (verify_path, _):
        sandbox_python = (
            verify_path / ".venv" / ("Scripts/python" if os.name == "nt" else "bin/python")
        )
        assert sandbox_python.exists()

        proc = subprocess.run(
            [str(sandbox_python), "-c", "import pytest; print(pytest.__version__)"],
            cwd=verify_path,
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert proc.returncode == 0, (
            f"Subprocess failed: stderr={proc.stderr}, stdout={proc.stdout}"
        )
        assert proc.stdout.strip()

        # R4 invariant: sandbox_python resolves strictly inside verify_path,
        # not into worktree or host
        assert sandbox_python.resolve().is_relative_to((verify_path / ".venv").resolve())
        assert not sandbox_python.resolve().is_relative_to(worktree_path.resolve())
        assert not sandbox_python.resolve().is_relative_to(repository.resolve())
        # Materialized private executable copy has distinct inode
        assert sandbox_python.stat().st_ino != Path(sys.executable).resolve().stat().st_ino


def test_concurrent_audit_private_toolchain_copy_write_isolation(
    repository: Path,
) -> None:
    git = Git(repository)
    base_sha = _ignore_toolchains(repository)
    worktree_path = repository.parent / "test-worktree-write-isolation"
    git.create_worktree(worktree_path, "feature-write-iso", base_sha)

    nm = worktree_path / "node_modules"
    (nm / "pkg").mkdir(parents=True)
    (nm / "pkg/index.js").write_text("original\n")

    venv = worktree_path / ".venv"
    (venv / "bin").mkdir(parents=True)
    (venv / "bin/python").symlink_to(Path(sys.executable).resolve())
    (venv / "cfg.txt").write_text("original_venv\n")

    frozen_digest = Git(worktree_path).snapshot(base_sha)
    pipeline = Pipeline(repository, configuration(), FakeAgents())

    with pipeline.verification_workspace(
        worktree_path, frozen_digest, base_sha, "T100", "run-write-iso"
    ) as (verify_path, _):
        assert (verify_path / "node_modules").is_dir()
        assert not (verify_path / "node_modules").is_symlink()
        assert (verify_path / ".venv").is_dir()
        assert not (verify_path / ".venv").is_symlink()

        sandbox_file = verify_path / "node_modules/pkg/index.js"
        host_file = worktree_path / "node_modules/pkg/index.js"
        assert sandbox_file.stat().st_ino != host_file.stat().st_ino

        (verify_path / "node_modules/pkg/sandbox_mutation.txt").write_text("private write")
        (verify_path / ".venv/sandbox_mutation.txt").write_text("private venv write")

        assert not (worktree_path / "node_modules/pkg/sandbox_mutation.txt").exists()
        assert not (worktree_path / ".venv/sandbox_mutation.txt").exists()

        assert not (repository / "node_modules/pkg/sandbox_mutation.txt").exists()
        assert not (repository / ".venv/sandbox_mutation.txt").exists()

        # R4 invariant: modifying existing files in private toolchain does not mutate host files
        sandbox_file.write_text("mutated_sandbox_file\n")
        assert host_file.read_text() == "original\n"

        sandbox_venv_file = verify_path / ".venv/cfg.txt"
        sandbox_venv_file.write_text("mutated_sandbox_venv\n")
        assert (worktree_path / ".venv/cfg.txt").read_text() == "original_venv\n"


def test_concurrent_audit_private_toolchain_internal_symlinks_preserved(
    repository: Path,
) -> None:
    git = Git(repository)
    base_sha = _ignore_toolchains(repository)
    worktree_path = repository.parent / "test-worktree-internal-symlinks"
    git.create_worktree(worktree_path, "feature-internal-symlinks", base_sha)

    nm = worktree_path / "node_modules"
    (nm / "typescript/bin").mkdir(parents=True)
    (nm / "typescript/bin/tsc").write_text("console.log('tsc')\n")
    (nm / ".bin").mkdir(parents=True)
    (nm / ".bin/tsc").symlink_to("../typescript/bin/tsc")

    venv = worktree_path / ".venv"
    (venv / "bin").mkdir(parents=True)
    (venv / "bin/python3").symlink_to(Path(sys.executable).resolve())
    (venv / "bin/python").symlink_to("python3")
    (venv / "lib").mkdir(parents=True)
    (venv / "lib/site.py").write_text("site\n")
    (venv / "lib64").symlink_to("lib")

    frozen_digest = Git(worktree_path).snapshot(base_sha)
    pipeline = Pipeline(repository, configuration(), FakeAgents())

    with pipeline.verification_workspace(
        worktree_path, frozen_digest, base_sha, "T100", "run-internal-symlinks"
    ) as (verify_path, _):
        sandbox_tsc = verify_path / "node_modules/.bin/tsc"
        assert sandbox_tsc.is_symlink()
        assert sandbox_tsc.resolve().is_relative_to((verify_path / "node_modules").resolve())
        assert not sandbox_tsc.resolve().is_relative_to(worktree_path.resolve())
        assert not sandbox_tsc.resolve().is_relative_to(repository.resolve())

        sandbox_lib64 = verify_path / ".venv/lib64"
        assert sandbox_lib64.is_symlink()
        assert sandbox_lib64.resolve().is_relative_to((verify_path / ".venv").resolve())
        assert not sandbox_lib64.resolve().is_relative_to(worktree_path.resolve())


def test_concurrent_audit_private_toolchain_external_regular_file_symlink_reproduction(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Exact reproduction of Audit #3 HIGH finding:

    Writing through sandbox/node_modules/pkg/link.js must NOT mutate host file.
    R4 policy: external regular-file symlink is rejected before lane dispatch (Outcome A),
    leaving the original external host file completely unchanged (content, inode, mtime).
    """
    git = Git(repository)
    base_sha = _ignore_toolchains(repository)

    # 1. External host toolchain file outside all repositories and worktrees
    host_toolchain = tmp_path / "host_toolchain"
    host_toolchain.mkdir()
    host_file = host_toolchain / "external.js"
    orig_content = "console.log('original host toolchain content');\n"
    host_file.write_text(orig_content, encoding="utf-8")
    orig_stat = host_file.stat()
    orig_inode = orig_stat.st_ino
    orig_mtime_ns = orig_stat.st_mtime_ns

    # 2. Worktree with symlink pointing to external regular file
    worktree_path = repository.parent / "test-worktree-ext-file"
    git.create_worktree(worktree_path, "feature-ext-file", base_sha)
    nm = worktree_path / "node_modules"
    (nm / "pkg").mkdir(parents=True)
    link_js = nm / "pkg/link.js"
    link_js.symlink_to(host_file)

    frozen_digest = Git(worktree_path).snapshot(base_sha)
    pipeline = Pipeline(repository, configuration(), FakeAgents())

    # Verification workspace preparation rejects the external symlink before dispatch
    with (
        pytest.raises(OrchestratorError, match="Unsafe external file symlink in toolchain"),
        pipeline.verification_workspace(
            worktree_path, frozen_digest, base_sha, "T100", "run-ext-file"
        ),
    ):
        pass

    # Host file evidence is completely unchanged
    assert host_file.read_text(encoding="utf-8") == orig_content
    assert host_file.stat().st_ino == orig_inode
    assert host_file.stat().st_mtime_ns == orig_mtime_ns

    # 3. Prove pre-dispatch failure semantics during pipeline run
    class ExternalFileSymlinkAgents(ConcurrentAuditAgents):
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
                pkg_dir = cwd / "node_modules/pkg"
                pkg_dir.mkdir(parents=True, exist_ok=True)
                (pkg_dir / "link.js").symlink_to(host_file)
            return result

    agents = ExternalFileSymlinkAgents("verification_first")
    pipeline, returned_agents = concurrent_audit_pipeline(
        repository, monkeypatch, "verification_first", agents=agents
    )
    assert returned_agents is agents

    state = pipeline.start("T100")
    assert state.state == State.FAILED
    assert "Unsafe external file symlink in toolchain" in (state.last_error or "")
    # Pre-dispatch failure assertions: zero calls executed
    assert len(agents.reviewer_cwds) == 0
    assert len(agents.verification_cwds) == 0
    assert "review_bundle" not in state.artifacts
    assert len(agents.audit_prompts) == 0

    # Host file remains completely untouched
    assert host_file.read_text(encoding="utf-8") == orig_content
    assert host_file.stat().st_ino == orig_inode
    assert host_file.stat().st_mtime_ns == orig_mtime_ns


def test_concurrent_audit_private_toolchain_external_directory_symlink_fails_closed(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """External directory symlinks fail closed before dispatch."""
    git = Git(repository)
    base_sha = _ignore_toolchains(repository)

    ext_dir = tmp_path / "host_external_dir"
    ext_dir.mkdir()
    (ext_dir / "data.txt").write_text("external dir data\n")

    worktree_path = repository.parent / "test-worktree-ext-dir"
    git.create_worktree(worktree_path, "feature-ext-dir", base_sha)
    nm = worktree_path / "node_modules"
    nm.mkdir(parents=True)
    (nm / "ext_pkg").symlink_to(ext_dir)

    frozen_digest = Git(worktree_path).snapshot(base_sha)
    pipeline = Pipeline(repository, configuration(), FakeAgents())

    with (
        pytest.raises(OrchestratorError, match="Unsafe external directory symlink in toolchain"),
        pipeline.verification_workspace(
            worktree_path, frozen_digest, base_sha, "T100", "run-ext-dir"
        ),
    ):
        pass

    assert (ext_dir / "data.txt").read_text() == "external dir data\n"

    # Pre-dispatch failure in pipeline
    class ExternalDirSymlinkAgents(ConcurrentAuditAgents):
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
                (cwd / "node_modules").mkdir(parents=True, exist_ok=True)
                (cwd / "node_modules/ext_pkg").symlink_to(ext_dir)
            return result

    agents = ExternalDirSymlinkAgents("verification_first")
    pipeline, returned_agents = concurrent_audit_pipeline(
        repository, monkeypatch, "verification_first", agents=agents
    )
    assert returned_agents is agents

    state = pipeline.start("T100")
    assert state.state == State.FAILED
    assert "Unsafe external directory symlink in toolchain" in (state.last_error or "")
    assert len(agents.reviewer_cwds) == 0
    assert len(agents.verification_cwds) == 0
    assert "review_bundle" not in state.artifacts
    assert len(agents.audit_prompts) == 0


def test_concurrent_audit_private_toolchain_nested_symlink_chain_cannot_escape(
    repository: Path,
    tmp_path: Path,
) -> None:
    """Nested symlink chains cannot escape sandbox via chained or relative paths."""
    git = Git(repository)
    base_sha = _ignore_toolchains(repository)

    ext_file = tmp_path / "host_secret.txt"
    ext_file.write_text("secret\n")

    worktree_path = repository.parent / "test-worktree-nested-chain"
    git.create_worktree(worktree_path, "feature-nested-chain", base_sha)

    nm = worktree_path / "node_modules"
    (nm / "pkg").mkdir(parents=True)
    # link3 points outside -> link2 points to link3 -> link1 points to link2
    (nm / "pkg/link3").symlink_to(ext_file)
    (nm / "pkg/link2").symlink_to("link3")
    (nm / "pkg/link1").symlink_to("link2")

    frozen_digest = Git(worktree_path).snapshot(base_sha)
    pipeline = Pipeline(repository, configuration(), FakeAgents())

    with (
        pytest.raises(OrchestratorError, match="Unsafe external file symlink in toolchain"),
        pipeline.verification_workspace(
            worktree_path, frozen_digest, base_sha, "T100", "run-nested"
        ),
    ):
        pass

    assert ext_file.read_text() == "secret\n"

    # Relative escaping chain: link_a -> link_b -> relative path to outside_relative.txt
    outside_file = tmp_path / "outside_relative.txt"
    outside_file.write_text("outside\n")
    nm2 = worktree_path / "node_modules/escape_rel"
    nm2.mkdir(parents=True)
    rel_path = os.path.relpath(outside_file, nm2)
    (nm2 / "link_b").symlink_to(Path(rel_path))
    (nm2 / "link_a").symlink_to("link_b")

    frozen_digest2 = Git(worktree_path).snapshot(base_sha)
    with (
        pytest.raises(OrchestratorError, match="Unsafe external file symlink in toolchain"),
        pipeline.verification_workspace(
            worktree_path, frozen_digest2, base_sha, "T100", "run-nested-rel"
        ),
    ):
        pass

    assert outside_file.read_text() == "outside\n"


def test_concurrent_audit_private_toolchain_symlink_loop_fails_closed(
    repository: Path,
) -> None:
    """Circular symlink loops fail closed with OrchestratorError."""
    git = Git(repository)
    base_sha = _ignore_toolchains(repository)

    worktree_path = repository.parent / "test-worktree-symlink-loop"
    git.create_worktree(worktree_path, "feature-symlink-loop", base_sha)

    nm = worktree_path / "node_modules/loop"
    nm.mkdir(parents=True)
    (nm / "a").symlink_to("b")
    (nm / "b").symlink_to("a")

    frozen_digest = Git(worktree_path).snapshot(base_sha)
    pipeline = Pipeline(repository, configuration(), FakeAgents())

    with (
        pytest.raises(OrchestratorError, match="Unresolvable toolchain symlink"),
        pipeline.verification_workspace(worktree_path, frozen_digest, base_sha, "T100", "run-loop"),
    ):
        pass


def test_concurrent_audit_private_toolchain_dangling_symlink_fails_closed(
    repository: Path,
) -> None:
    """Dangling symlinks fail closed with OrchestratorError."""
    git = Git(repository)
    base_sha = _ignore_toolchains(repository)

    worktree_path = repository.parent / "test-worktree-dangling-symlink"
    git.create_worktree(worktree_path, "feature-dangling", base_sha)

    nm = worktree_path / "node_modules/dangling"
    nm.mkdir(parents=True)
    (nm / "broken").symlink_to("nonexistent_target_file")

    frozen_digest = Git(worktree_path).snapshot(base_sha)
    pipeline = Pipeline(repository, configuration(), FakeAgents())

    with (
        pytest.raises(OrchestratorError, match="Unresolvable toolchain symlink"),
        pipeline.verification_workspace(
            worktree_path, frozen_digest, base_sha, "T100", "run-dangling"
        ),
    ):
        pass


def test_concurrent_audit_private_toolchain_venv_non_interpreter_external_symlink_fails_closed(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """External symlinks in .venv that are not interpreters fail closed."""
    git = Git(repository)
    base_sha = _ignore_toolchains(repository)

    host_file = tmp_path / "host_secret.conf"
    host_file.write_text("HOST SECRET\n")

    worktree_path = repository.parent / "test-worktree-venv-non-interp"
    git.create_worktree(worktree_path, "feature-venv-non-interp", base_sha)

    venv = worktree_path / ".venv"
    (venv / "bin").mkdir(parents=True)
    (venv / "bin/python").symlink_to(Path(sys.executable).resolve())
    (venv / "bin/secret.conf").symlink_to(host_file)

    frozen_digest = Git(worktree_path).snapshot(base_sha)
    pipeline = Pipeline(repository, configuration(), FakeAgents())

    with (
        pytest.raises(OrchestratorError, match="Unsafe external file symlink in toolchain"),
        pipeline.verification_workspace(
            worktree_path, frozen_digest, base_sha, "T100", "run-venv-non-interp"
        ),
    ):
        pass

    assert host_file.read_text() == "HOST SECRET\n"

    # Pre-dispatch failure in pipeline
    class VenvNonInterpAgents(ConcurrentAuditAgents):
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
                v = cwd / ".venv"
                (v / "bin").mkdir(parents=True, exist_ok=True)
                (v / "bin/python").symlink_to(Path(sys.executable).resolve())
                (v / "bin/secret.conf").symlink_to(host_file)
            return result

    agents = VenvNonInterpAgents("verification_first")
    pipeline, returned_agents = concurrent_audit_pipeline(
        repository, monkeypatch, "verification_first", agents=agents
    )
    assert returned_agents is agents

    state = pipeline.start("T100")
    assert state.state == State.FAILED
    assert "Unsafe external file symlink in toolchain" in (state.last_error or "")
    assert len(agents.reviewer_cwds) == 0
    assert len(agents.verification_cwds) == 0
    assert "review_bundle" not in state.artifacts
    assert len(agents.audit_prompts) == 0
    assert host_file.read_text() == "HOST SECRET\n"


def test_concurrent_audit_evidence_bundle_persistence_and_parent_authority(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pipeline, _agents = concurrent_audit_pipeline(repository, monkeypatch, "verification_first")
    state = pipeline.start("T100")
    assert state.state == State.AUDIT_PASS, state.last_error

    directory = pipeline.run_path("T100", state.run_id)

    # 1. Existing audit_checks compatibility preserved
    assert "audit_checks" in state.artifacts
    checks_path = directory / state.artifacts["audit_checks"]
    assert checks_path.is_file()
    checks = read_json(checks_path)
    assert isinstance(checks, dict)
    assert checks["source_digest"] == state.verified_digest
    assert all(
        "declaration_digest" not in result and "duration_ns" not in result
        for result in checks["results"]
    )

    # 2. EvidenceBundle registered and persisted by parent
    assert "evidence_bundle" in state.artifacts
    bundle_path = directory / state.artifacts["evidence_bundle"]
    assert bundle_path.is_file()
    assert (
        digest(bundle_path.read_bytes())
        == state.artifact_digests[state.artifacts["evidence_bundle"]]
    )

    # 3. Accessor loads and validates bundle
    bundle = pipeline.evidence_bundle(directory, state)
    assert isinstance(bundle, EvidenceBundle)
    assert bundle.schema_version == 1
    assert bundle.task_id == "T100"
    assert bundle.base_sha == state.base_sha
    assert bundle.source_digest == state.verified_digest
    assert bundle.scope.verdict == "PASS"
    assert bundle.verification.passed is True
    assert bundle.is_complete is True

    # 4. Check referenced artifacts in bundle
    artifact_names = [a.name for a in bundle.artifacts]
    assert "audit_checks" in artifact_names

    # 5. Tampering with registered evidence bundle is detected
    bundle_path.write_text('{"tampered": true}', encoding="utf-8")
    with pytest.raises(OrchestratorError, match="changed during execution"):
        pipeline.evidence_bundle(directory, state)


def test_evidence_bundle_accessor_rejects_current_source_digest_mismatch(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipeline, _agents = concurrent_audit_pipeline(repository, monkeypatch, "verification_first")
    state = pipeline.start("T100")
    assert state.state == State.AUDIT_PASS, state.last_error
    directory = pipeline.run_path("T100", state.run_id)
    bundle = pipeline.evidence_bundle(directory, state)
    worktree = Path(state.worktree_path)
    candidate_file = worktree / "candidate-after-verification.txt"
    candidate_file.write_text("synthetic candidate B\n", encoding="utf-8")
    assert Git(worktree).snapshot(state.base_sha) != bundle.source_digest
    with pytest.raises(OrchestratorError, match="source_digest mismatch"):
        pipeline.evidence_bundle(directory, state)


def synthetic_integrator_context(
    *,
    source_branch: str = "agent/T100-run1",
    target_branch: str = "main",
    target_sha: str = "a" * 40,
    evidence_payload: dict[str, object] | None = None,
) -> IntegratorContextV1:
    contract = AuditorContract(
        title="Synthetic Task",
        objective="Verify integrator context behavior",
        allowed_paths=["feature.txt"],
        forbidden_paths=[],
        acceptance_criteria=["Preserve good behavior"],
        risk_level="medium",
        stop_conditions="Stop on scope extension",
    )
    bundle = (
        evidence_payload
        if evidence_payload is not None
        else {
            "schema_version": 1,
            "task_id": "T100",
            "base_sha": "b" * 40,
            "branch": source_branch,
            "source_digest": "c" * 64,
            "scope": {
                "verdict": "PASS",
                "allowed_paths": ["feature.txt"],
                "actual_changed_paths": ["feature.txt"],
            },
            "verification": {"passed": True, "failed": False, "commands": []},
        }
    )
    return IntegratorContextV1(
        contract=contract,
        evidence_bundle=bundle,
        source_branch=source_branch,
        target_branch=target_branch,
        target_sha=target_sha,
    )


def test_integrator_context_v1_interface_and_properties() -> None:
    ctx = synthetic_integrator_context()
    assert ctx.schema_version == 1
    assert ctx.source_branch == "agent/T100-run1"
    assert ctx.target_branch == "main"
    assert ctx.target_sha == "a" * 40
    assert ctx.contract.title == "Synthetic Task"
    assert IntegratorContext is IntegratorContextV1

    # Deterministic serialization
    raw_json = serialize_integrator_context(ctx)
    data = json.loads(raw_json)
    assert data["source_branch"] == "agent/T100-run1"
    assert data["target_branch"] == "main"
    assert data["schema_version"] == 1

    # Digest property and standalone helper match
    expected_digest = digest(raw_json.encode("utf-8"))
    assert ctx.digest == expected_digest
    assert integrator_context_digest(ctx) == expected_digest

    # Component size breakdown
    sizes = integrator_context_component_sizes(ctx)
    assert "contract_bytes" in sizes
    assert "evidence_bundle_bytes" in sizes
    assert "schema_version_bytes" in sizes
    assert "source_branch_bytes" in sizes
    assert "target_branch_bytes" in sizes
    assert "target_sha_bytes" in sizes
    assert sizes["total_bytes"] == len(raw_json.encode("utf-8"))
    assert sum(v for k, v in sizes.items() if k != "total_bytes") < sizes["total_bytes"]

    # In-bounds size check returns length
    assert check_integrator_context_size(ctx) == len(raw_json.encode("utf-8"))

    # Extra fields forbidden
    dumped = ctx.model_dump()
    dumped["extra_field"] = "forbidden"
    with pytest.raises(ValidationError):
        IntegratorContextV1.model_validate(dumped)


def test_integrator_context_v1_size_guard_and_diagnostics() -> None:
    # 1. Fits under default 64 KiB limit
    ctx_small = synthetic_integrator_context()
    assert check_integrator_context_size(ctx_small) <= INTEGRATOR_CONTEXT_MAX_BYTES

    # 2. Oversized payload raises IntegratorContextOversizedError
    huge_data = "x" * (65 * 1024)
    ctx_oversized = synthetic_integrator_context(evidence_payload={"huge": huge_data})
    with pytest.raises(IntegratorContextOversizedError) as exc_info:
        check_integrator_context_size(ctx_oversized)
    err_msg = str(exc_info.value)
    assert "Integrator context exceeds size limit" in err_msg
    assert f"> {INTEGRATOR_CONTEXT_MAX_BYTES} bytes" in err_msg
    assert "Component diagnostics:" in err_msg
    assert "evidence_bundle_bytes" in err_msg

    # Verify error hierarchy (both OrchestratorError and ValueError)
    assert isinstance(exc_info.value, OrchestratorError)
    assert isinstance(exc_info.value, ValueError)

    # 3. Custom max_bytes parameter supported
    with pytest.raises(IntegratorContextOversizedError) as custom_exc:
        check_integrator_context_size(ctx_small, max_bytes=50)
    assert "50 bytes" in str(custom_exc.value)


def test_build_integrator_prompt_formatting() -> None:
    ctx = synthetic_integrator_context()
    skills = "## REQUIRED AGENT SKILLS\n- code-review-and-quality"
    prompt = build_integrator_prompt(ctx, skills_text=skills)

    assert "ROLE: integrator" in prompt
    assert "OUTPUT SCHEMA:" in prompt
    assert "IntegrationReview" in prompt or '"status"' in prompt
    assert "code-review-and-quality" in prompt
    assert "INTEGRATOR_CONTEXT:" in prompt
    assert ctx.source_branch in prompt
    assert ctx.target_branch in prompt
    assert ctx.target_sha in prompt

    # Valid JSON in INTEGRATOR_CONTEXT block
    idx = prompt.index("INTEGRATOR_CONTEXT:")
    context_part = prompt[idx + len("INTEGRATOR_CONTEXT:") :].strip()
    parsed = json.loads(context_part)
    assert parsed["source_branch"] == ctx.source_branch
    assert parsed["target_sha"] == ctx.target_sha


def test_integrator_context_attempt_artifact_sealing_and_protection(repository: Path) -> None:
    # 1. Suffix registered in known attempt suffixes
    assert ".integrator-context.json" in KNOWN_ATTEMPT_ARTIFACT_SUFFIXES

    # 2. Run pipeline with integration enabled
    agents = FakeAgents()
    pipeline = Pipeline(repository, configuration(integrate=True), agents)
    state = pipeline.start("T100")
    assert state.state == State.DONE, state.last_error

    directory = pipeline.run_path("T100", state.run_id)

    # 3. Attempt artifact exists and is sealed
    integrator_contexts = list(directory.glob("*-integrator-*.integrator-context.json"))
    assert len(integrator_contexts) == 1
    ctx_file = integrator_contexts[0]
    assert ctx_file.is_file() and not ctx_file.is_symlink()

    # 4. Registered in state.artifact_digests with matching digest
    file_digest = digest(ctx_file.read_bytes())
    assert ctx_file.name in state.artifact_digests
    assert state.artifact_digests[ctx_file.name] == file_digest

    # 5. Content deserializes to valid IntegratorContextV1
    loaded = json.loads(ctx_file.read_text(encoding="utf-8"))
    validated_ctx = IntegratorContextV1.model_validate(loaded)
    assert validated_ctx.source_branch == state.worktree_branch
    assert validated_ctx.target_branch == "main"
    assert validated_ctx.target_sha is not None

    # 6. Tampering with sealed context artifact fails validation
    ctx_file.write_text('{"tampered": true}', encoding="utf-8")
    with pytest.raises(OrchestratorError):
        pipeline.check_artifacts(directory, state)


def test_integrator_oversized_context_fails_closed_zero_attempts(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    agents = FakeAgents()
    pipeline = Pipeline(repository, configuration(integrate=True), agents)

    import tools.orchestrator.workflow as workflow

    def constrained_integrator_limit(context: IntegratorContextV1) -> int:
        return check_integrator_context_size(context, max_bytes=256)

    monkeypatch.setattr(workflow, "check_integrator_context_size", constrained_integrator_limit)

    state = pipeline.start("T100")
    assert state.state == State.FAILED
    assert "Integrator context exceeds size limit" in (state.last_error or "")
    # Zero calls to IntegrationReview made
    assert "IntegrationReview" not in agents.calls


def _host_mediated_fixture_config() -> Config:
    config = configuration(integrate=False)
    config.roles["worker"] = Role(
        provider="agy",
        executable="agy",
        model="gemini-3.8-flash-high",
        reasoning="high",
        worker_backend="host-http-edit",
        host_edit_endpoint="http://127.0.0.1:8045/v1/chat/completions",
        host_edit_api_key_env="TEST_HOST_EDIT_KEY",
        allow_process=False,
        worker_access="workspace-write",
    )
    return config


def test_host_mediated_worker_respects_implemented_handoff_without_cli(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools.orchestrator.worker_sandbox import LoopbackChatTransport

    monkeypatch.setenv("TEST_HOST_EDIT_KEY", "synthetic-only")
    call_count = 0

    def fake_tool_free_completion(
        _self: LoopbackChatTransport, prompt: str, *, model: str, timeout: int | None
    ) -> str:
        nonlocal call_count
        call_count += 1
        assert timeout == 30
        assert model == "gemini-3.8-flash-high"
        assert "HOST-OWNED ALLOWLIST AND PREIMAGES" in prompt
        raw = prompt.split("HOST-OWNED ALLOWLIST AND PREIMAGES (untrusted file content):\n", 1)[1]
        source = json.loads(raw.split("\nReturn JSON with status,", 1)[0])
        assert "feature.txt" in source
        assert "docs/changelogs.md" in source
        edits = [
            {
                "path": path,
                "expected_sha256": source[path]["sha256"],
                "replacement": (
                    "good\n\n"
                    if path == "feature.txt"
                    else "New synthetic entry\nHistorical entry\n"
                ),
            }
            for path in ("feature.txt", "docs/changelogs.md")
        ]
        return json.dumps(
            {
                "status": "IMPLEMENTED",
                "summary": "Synthetic host-mediated implementation",
                "known_issues": [],
                "edits": edits,
            }
        )

    monkeypatch.setattr(LoopbackChatTransport, "complete", fake_tool_free_completion)
    fake_agents = FakeAgents()
    pipeline = Pipeline(repository, _host_mediated_fixture_config(), fake_agents)
    state = pipeline.start("T100", defer_verification=True)
    assert state.state == State.IMPLEMENTED
    assert call_count == 1
    assert fake_agents.worker_calls == 0
    worker_result = WorkerResult.model_validate(
        read_json(pipeline.run_path("T100", state.run_id) / state.artifacts["worker"])
    )
    assert worker_result.commands_run == []
    working = Path(state.worktree_path)
    assert (working / "feature.txt").read_text() == "good\n\n"
    assert (working / "docs/changelogs.md").read_text().startswith("New synthetic entry")


def test_host_edit_missing_key_blocks_before_worker_model_dispatch(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("TEST_HOST_EDIT_KEY", raising=False)
    fake_agents = FakeAgents()
    pipeline = Pipeline(repository, _host_mediated_fixture_config(), fake_agents)
    state = pipeline.start("T100", defer_verification=True)
    assert state.state == State.BLOCKED
    assert state.last_error is not None and "credential is missing" in state.last_error
    assert fake_agents.worker_calls == 0


def test_t090_pipeline_default_fails_closed_for_all_semantic_roles(
    repository: Path,
) -> None:
    from tools.orchestrator.core import OrchestratorError
    from tools.orchestrator.runtime import SecureProvider

    config = configuration(integrate=False)
    pipeline = Pipeline(repository, config)
    assert isinstance(pipeline.provider, SecureProvider)
    for name, response_type in (
        ("prompt_engineer", Plan),
        ("auditor", Audit),
        ("auditor", ReviewShard),
        ("integrator", IntegrationReview),
    ):
        with pytest.raises(OrchestratorError, match="T090 BLOCKED"):
            pipeline.provider.run(
                "Synthetic host-supplied evidence",
                cwd=repository,
                role=config.roles[name],
                timeout=1,
                output=response_type,
                artifacts=repository,
                name="semantic-no-cli",
                readonly=True,
            )


def test_t090_host_sealed_source_evidence_binds_exact_bytes_and_diff(
    repository: Path,
) -> None:
    from tools.orchestrator.core import digest
    from tools.orchestrator.workflow import build_sealed_source_evidence

    git = Git(repository)
    base = git.sha()
    (repository / "feature.txt").write_text("updated feature\n")
    (repository / "docs/changelogs.md").write_text("Changed record\n")
    source = git.snapshot(base)
    payload = build_sealed_source_evidence(
        repository, base, source, ["feature.txt", "docs/changelogs.md"]
    )
    evidence = payload["evidence"]
    assert isinstance(evidence, dict)
    assert evidence["base_sha"] == base
    assert evidence["source_digest"] == source
    files = evidence["files"]
    assert isinstance(files, list)
    assert [item["path"] for item in files] == ["docs/changelogs.md", "feature.txt"]
    feature = files[1]
    assert feature["before"] == "good\n"
    assert feature["after"] == "updated feature\n"
    assert feature["before_sha256"] == digest(b"good\n")
    assert feature["after_sha256"] == digest(b"updated feature\n")
    assert "-good" in feature["unified_diff"]
    assert "+updated feature" in feature["unified_diff"]
    canonical = json.dumps(
        evidence, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    assert payload["evidence_sha256"] == digest(canonical)


@pytest.mark.parametrize(
    "attack",
    ["outside", "stale", "nul", "invalid-utf8", "oversized", "symlink"],
)
def test_t090_sealed_source_evidence_fails_closed(repository: Path, attack: str) -> None:
    from tools.orchestrator.core import OrchestratorError
    from tools.orchestrator.workflow import build_sealed_source_evidence

    git = Git(repository)
    base = git.sha()
    source = repository / "feature.txt"
    allowed = ["feature.txt"]
    if attack == "outside":
        (repository / "docs/changelogs.md").write_text("outside scope\n")
    elif attack == "nul":
        source.write_bytes(b"new\x00content\n")
    elif attack == "invalid-utf8":
        source.write_bytes(b"new\xffcontent\n")
    elif attack == "oversized":
        source.write_bytes(b"A" * (49 * 1024))
    elif attack == "symlink":
        source.unlink()
        source.symlink_to(repository / "docs/changelogs.md")
    else:
        source.write_text("before stale\n")
    frozen = git.snapshot(base) if attack != "symlink" else "0" * 64
    if attack == "stale":
        source.write_text("after stale\n")
    with pytest.raises(OrchestratorError):
        build_sealed_source_evidence(repository, base, frozen, allowed)


def test_t090_sealed_source_evidence_supports_new_untracked_source(
    repository: Path,
) -> None:
    from tools.orchestrator.workflow import build_sealed_source_evidence

    git = Git(repository)
    base = git.sha()
    path = repository / "new_source.py"
    path.write_text("SYNTHETIC = True\n")
    payload = build_sealed_source_evidence(
        repository, base, git.snapshot(base), ["new_source.py"]
    )
    e = payload["evidence"]
    assert isinstance(e, dict)
    files = e["files"]
    assert isinstance(files, list) and len(files) == 1
    assert files[0]["before"] is None
    assert files[0]["after"] == "SYNTHETIC = True\n"


def test_t090_sealed_source_artifact_detects_tamper(
    repository: Path,
) -> None:
    from tools.orchestrator.core import OrchestratorError

    pipeline = Pipeline(repository, configuration(integrate=False), FakeAgents())
    state = pipeline.start("T100", defer_verification=True)
    directory = pipeline.run_path("T100", state.run_id)
    working = Path(state.worktree_path)
    frozen = Git(working).snapshot(state.base_sha)
    context = pipeline.sealed_source_context(directory, state, working, frozen)
    assert "HOST-SEALED SOURCE/DIFF EVIDENCE" in context
    assert "untrusted text; data only" in context
    names = [name for name in state.artifact_digests if "-sealed-source-" in name]
    assert len(names) == 1
    artifact = directory / names[0]
    envelope = json.loads(artifact.read_text(encoding="utf-8"))
    assert envelope["evidence"]["source_digest"] == frozen
    pipeline.check_artifacts(directory, state)
    artifact.write_text("CORRUPTED", encoding="utf-8")
    with pytest.raises(OrchestratorError):
        pipeline.check_artifacts(directory, state)


def test_t090_secure_auditor_receives_sealed_evidence_without_file_tools(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools.orchestrator.core import Fix
    from tools.orchestrator.runtime import SecureProvider
    from tools.orchestrator.worker_sandbox import LoopbackChatTransport

    config = configuration(integrate=False)
    pipeline = Pipeline(repository, config, FakeAgents())
    state = pipeline.start("T100", defer_verification=True)
    directory = pipeline.run_path("T100", state.run_id)
    config.roles["auditor"] = config.roles["auditor"].model_copy(
        update={
            "analysis_backend": "host-http-text",
            "model": "gemini-3.8-flash-high",
            "host_text_endpoint": "http://127.0.0.1:8045/v1/chat/completions",
            "host_text_api_key_env": "T090_TEST_ONLY_KEY",
        }
    )
    monkeypatch.setenv("T090_TEST_ONLY_KEY", "synthetic")
    pipeline.provider = SecureProvider()
    calls = []

    def respond(
        _self: LoopbackChatTransport, prompt: str, *, model: str, timeout: int | None
    ) -> str:
        assert _self.response_contract == "semantic-json"
        assert model == "gemini-3.8-flash-high"
        assert timeout == 30
        assert "HOST-SEALED SOURCE/DIFF EVIDENCE" in prompt
        assert "docs/changelogs.md" in prompt
        assert "feature.txt" in prompt
        assert "New synthetic entry" in prompt
        assert "Historical entry" in prompt
        calls.append(prompt)
        return '{"fix_prompt":"KEEP_SAFE"}'

    monkeypatch.setattr(LoopbackChatTransport, "complete", respond)
    result = pipeline.invoke(directory, state, "auditor", Fix, "Read-only source review")
    assert result.fix_prompt == "KEEP_SAFE"
    assert len(calls) == 1
    pipeline.check_artifacts(directory, state)


def test_t090_parallel_review_receives_sealed_source_evidence(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools.orchestrator.core import digest
    from tools.orchestrator.runtime import SecureProvider

    config = configuration(integrate=False)
    pipeline = Pipeline(repository, config, FakeAgents())
    state = pipeline.start("T100", defer_verification=True)
    directory = pipeline.run_path("T100", state.run_id)
    snapshot = Git(Path(state.worktree_path)).snapshot(state.base_sha)
    checks_name = "t090-synthetic-checks.json"
    raw_checks = json.dumps({"source_digest": snapshot}).encode()
    (directory / checks_name).write_bytes(raw_checks)
    state.artifacts["audit_checks"] = checks_name
    state.artifact_digests[checks_name] = digest(raw_checks)
    pipeline.save(directory, state)
    config.roles["auditor"] = config.roles["auditor"].model_copy(
        update={
            "analysis_backend": "host-http-text",
            "model": "gemini-3.8-flash-high",
            "host_text_endpoint": "http://127.0.0.1:8045/v1/chat/completions",
            "host_text_api_key_env": "T090_TEST_ONLY_KEY",
        }
    )
    pipeline.provider = SecureProvider()
    seen: list[str] = []

    def review(
        _self: SecureProvider,
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
        assert readonly
        assert cwd == Path(state.worktree_path)
        assert role.analysis_backend == "host-http-text"
        assert timeout == 30
        assert artifacts == directory
        assert name
        assert output is ReviewShard
        assert "HOST-SEALED SOURCE/DIFF EVIDENCE" in prompt
        assert "New synthetic entry" in prompt
        assert "Historical entry" in prompt
        assert "test_behavior():" not in prompt
        matched = re.search(r"REVIEW_PERSPECTIVE: ([^\n]+)", prompt)
        assert matched is not None
        seen.append(matched[1])
        return output.model_validate(
            ReviewShard(
                perspective=ReviewPerspective(matched[1]),
                findings=[],
                probe_request=None,
            )
        )

    monkeypatch.setattr(SecureProvider, "run", review)
    bundle = pipeline.parallel_review(directory, state, "Frozen synthetic context")
    assert len(seen) == len(ReviewPerspective)
    assert bundle.source_digest == snapshot
    pipeline.check_artifacts(directory, state)

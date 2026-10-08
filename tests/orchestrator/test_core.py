import json
import multiprocessing
import os
import re
import shlex
import subprocess
import sys
from contextlib import suppress
from multiprocessing.connection import Connection as PipeConnection
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from tools.orchestrator.core import (
    Audit,
    CandidateProvenance,
    Config,
    Contract,
    Criterion,
    EvidenceArtifactRef,
    EvidenceBundle,
    Fix,
    FrozenEvidenceIdentity,
    OrchestratorError,
    Plan,
    ReviewBundle,
    ReviewDisposition,
    ReviewFinding,
    ReviewPerspective,
    ReviewShard,
    Role,
    RunState,
    ScopeEvidence,
    State,
    TimingEvidence,
    VerificationCommandEvidence,
    VerificationEvidence,
    atomic_json,
    digest,
    read_json,
    safe_path,
    transition,
)
from tools.orchestrator.runtime import CliProvider, Git, LockBusy, execute, lock, slot


def parallel_review_bundle() -> ReviewBundle:
    return ReviewBundle.assemble(
        "a" * 64,
        "agent/fixture",
        [
            ReviewShard(
                perspective=perspective,
                findings=[ReviewFinding(action="Repair synthetic defect", evidence="feature.py:1")],
                probe_request=None,
            )
            for perspective in reversed(ReviewPerspective)
        ],
    )


def test_parallel_review_canonical_identity_and_complete_bundle() -> None:
    bundle = parallel_review_bundle()
    assert [s.perspective for s in bundle.shards] == list(ReviewPerspective)
    assert [s.findings[0].finding_id for s in bundle.shards] == [
        f"{perspective}:0001" for perspective in ReviewPerspective
    ]
    assert ReviewBundle.model_validate_json(bundle.model_dump_json()) == bundle
    for shards in (bundle.shards[:2], list(reversed(bundle.shards)), [bundle.shards[0]] * 3):
        with pytest.raises(ValidationError):
            ReviewBundle.model_validate({**bundle.model_dump(), "shards": shards})
    data = bundle.model_dump()
    data["shards"][1]["findings"][0]["finding_id"] = data["shards"][0]["findings"][0]["finding_id"]
    with pytest.raises(ValidationError):
        ReviewBundle.model_validate(data)
    with pytest.raises(OrchestratorError, match="incomplete"):
        ReviewBundle.assemble("a" * 64, "fixture", [])


@pytest.mark.parametrize("mode", ["valid", "missing", "unknown", "duplicate", "confirmed"])
def test_parallel_review_audit_dispositions(mode: str) -> None:
    bundle = parallel_review_bundle()
    audit = Audit(
        status="PASS",
        findings=[],
        acceptance_criteria=[Criterion(criterion="Behavior", status="PASS", evidence="Fixture")],
        scope_violations=[],
        required_fixes=[],
        reviewer_dispositions=[
            ReviewDisposition(
                finding_id=shard.findings[0].finding_id,
                disposition="dismissed",
                evidence="feature.py:1 and synthetic failure test refute this claim",
            )
            for shard in bundle.shards
        ],
    )
    if mode == "valid":
        audit.check(contract(), bundle)
        with pytest.raises(OrchestratorError, match="unknown"):
            audit.check(contract())
        return
    if mode == "missing":
        audit.reviewer_dispositions.pop()
    elif mode == "unknown":
        audit.reviewer_dispositions[0].finding_id = "unknown:0001"
    elif mode == "duplicate":
        audit.reviewer_dispositions.append(audit.reviewer_dispositions[0])
    else:
        audit.reviewer_dispositions[0].disposition = "confirmed"
    with pytest.raises(OrchestratorError, match=mode):
        audit.check(contract(), bundle)
    if mode == "confirmed":
        audit.status = "FAIL"
        audit.findings = ["Repair synthetic defect"]
        audit.acceptance_criteria[0].status = "FAIL"
        audit.check(contract(), bundle)


def test_parallel_review_historical_audit_compatibility() -> None:
    historical = {
        "status": "PASS",
        "findings": [],
        "acceptance_criteria": [{"criterion": "Behavior", "status": "PASS", "evidence": "Fixture"}],
        "scope_violations": [],
        "required_fixes": [],
    }
    audit = Audit.model_validate_json(json.dumps(historical))
    assert audit.reviewer_dispositions == []
    audit.check(contract())
    with pytest.raises(OrchestratorError, match="missing"):
        audit.check(contract(), parallel_review_bundle())


def test_parallel_review_dismissal_requires_evidence() -> None:
    for evidence in ("", " \n "):
        with pytest.raises(ValidationError):
            ReviewDisposition(finding_id="fixture:0001", disposition="dismissed", evidence=evidence)
        with pytest.raises(ValidationError):
            ReviewFinding(action="Repair synthetic issue", evidence=evidence)
        with pytest.raises(ValidationError):
            ReviewFinding(action=evidence, evidence="feature.txt:1")


def test_state_transition_and_atomic_roundtrip(tmp_path: Path) -> None:
    state = RunState(
        task_id="T018",
        run_id="test",
        base_sha="a" * 40,
        repository=str(tmp_path),
        worktree_path=str(tmp_path / "wt"),
        worktree_branch="agent/T018-test",
    )
    transition(state, State.READY)
    atomic_json(tmp_path / "state.json", state.model_dump(mode="json"))
    restored = RunState.model_validate(read_json(tmp_path / "state.json"))
    assert restored.state == State.READY
    with pytest.raises(ValueError, match="Illegal transition"):
        transition(restored, State.DONE)


@pytest.mark.parametrize(
    "value", ["../secret", "/absolute", "a/../b", "a\\b", ".git/config", "*.py"]
)
def test_path_policy_rejects_escape_and_globs(value: str) -> None:
    with pytest.raises(OrchestratorError):
        safe_path(value)


def test_atomic_failure_preserves_previous_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "state.json"
    atomic_json(path, {"generation": 1})

    def fail_replace(_source: str, _destination: Path) -> None:
        raise OSError("synthetic interrupted replace")

    monkeypatch.setattr("tools.orchestrator.core.os.replace", fail_replace)
    with pytest.raises(OSError):
        atomic_json(path, {"generation": 2})
    assert read_json(path) == {"generation": 1}
    assert list(tmp_path.iterdir()) == [path]


def test_invalid_state_and_malformed_json(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        RunState.model_validate(
            {
                "task_id": "T018",
                "run_id": "r",
                "base_sha": "a" * 40,
                "state": "MAGIC",
                "repository": "repo",
                "worktree_path": "wt",
                "worktree_branch": "agent/r",
            }
        )
    path = tmp_path / "bad.json"
    path.write_text("{broken")
    with pytest.raises(OrchestratorError, match="Malformed"):
        read_json(path)


def contract() -> Contract:
    return Contract(
        schema_version=1,
        task_id="T018",
        title="Task",
        objective="Implement",
        dependencies=[],
        base_sha="a" * 40,
        allowed_paths=["feature.py"],
        forbidden_paths=[],
        acceptance_criteria=["Behavior"],
        required_verification=[["python", "-m", "pytest"]],
        risk_level="high",
        forbidden_scope="Outside allowlist is forbidden",
        stop_conditions="Block on ambiguity",
        max_fix_cycles=3,
    )


def test_contract_requires_criteria_and_valid_types() -> None:
    data = contract().model_dump()
    data["acceptance_criteria"] = []
    with pytest.raises(ValidationError):
        Contract.model_validate(data)
    data = contract().model_dump()
    data["max_fix_cycles"] = True
    with pytest.raises(ValidationError):
        Contract.model_validate(data)


def test_new_agent_schema_omits_human_gates() -> None:
    assert "human_gates" not in Contract.model_json_schema()["properties"]
    assert "human_gates" not in Plan.model_json_schema()["$defs"]["Contract"]["properties"]


def test_new_agent_output_rejects_removed_gate_field() -> None:
    data = contract().model_dump()
    data["human_gates"] = ["Invented approval step"]
    with pytest.raises(ValidationError):
        Contract.model_validate(data)


def test_legacy_contract_is_read_without_rewriting_or_relaxing_fields() -> None:
    from tools.orchestrator.core import stored_contract

    data = contract().model_dump()
    data["human_gates"] = ["Legacy approval step"]
    before = json.dumps(data, sort_keys=True)
    restored = stored_contract(data)
    assert "human_gates" not in restored.model_dump()
    assert json.dumps(data, sort_keys=True) == before
    data["unowned_override"] = True
    with pytest.raises(ValidationError):
        stored_contract(data)


def test_legacy_plan_preserves_prompt_and_pinned_fields() -> None:
    from tools.orchestrator.core import stored_plan

    data: dict[str, object] = {
        "contract": contract().model_dump(),
        "worker_prompt": "Legacy worker prompt",
    }
    legacy = contract().model_dump()
    legacy["human_gates"] = ["Legacy gate"]
    data["contract"] = legacy
    before = json.dumps(data, sort_keys=True)
    restored = stored_plan(data)
    assert restored.worker_prompt == "Legacy worker prompt"
    assert restored.contract.objective == "Implement"
    assert "human_gates" not in restored.contract.model_dump()
    assert json.dumps(data, sort_keys=True) == before


@pytest.mark.parametrize("invalid", [None, "approval", [False]])
def test_legacy_gate_compatibility_still_rejects_malformed_input(invalid: object) -> None:
    from tools.orchestrator.core import stored_contract

    data = contract().model_dump()
    data["human_gates"] = invalid
    with pytest.raises(ValidationError):
        stored_contract(data)


def test_audit_invalid_status_and_false_pass_rejected() -> None:
    with pytest.raises(ValidationError):
        Audit.model_validate(
            {
                "status": "GREEN",
                "findings": [],
                "acceptance_criteria": [],
                "scope_violations": [],
                "required_fixes": [],
            }
        )
    audit = Audit(
        status="PASS",
        findings=["Still broken"],
        acceptance_criteria=[Criterion(criterion="Behavior", status="PASS", evidence="Fixture")],
        scope_violations=[],
        required_fixes=[],
        reviewer_dispositions=[],
    )
    with pytest.raises(OrchestratorError, match="Contradictory"):
        audit.check(contract())
    audit.findings = []
    audit.acceptance_criteria = []
    with pytest.raises(OrchestratorError, match="every criterion"):
        audit.check(contract())


@pytest.mark.parametrize(
    "command,expected",
    [
        ([sys.executable, "-c", "print('synthetic')"], 0),
        ([sys.executable, "-c", "raise SystemExit(7)"], 7),
    ],
)
def test_process_capture(tmp_path: Path, command: list[str], expected: int) -> None:
    result = execute(command, tmp_path, timeout=5)
    assert result.exit_code == expected
    assert result.cwd == str(tmp_path)
    assert result.started_at <= result.ended_at
    assert not result.timed_out
    assert "synthetic" not in json.dumps(result.metadata())


def test_process_timeout_and_missing_binary(tmp_path: Path) -> None:
    result = execute([sys.executable, "-c", "import time; time.sleep(20)"], tmp_path, timeout=1)
    assert result.timed_out
    assert result.exit_code != 0
    with pytest.raises(OrchestratorError, match="Executable unavailable"):
        execute([str(tmp_path / "missing-cli")], tmp_path)


def _probe_lock(path: str, connection: PipeConnection) -> None:
    try:
        with lock(Path(path)):
            connection.send("ACQUIRED")
    except LockBusy:
        connection.send("BUSY")
    finally:
        connection.close()


def test_integration_lock_is_cross_process_and_released(tmp_path: Path) -> None:
    ctx = multiprocessing.get_context("spawn")
    parent, child = ctx.Pipe()
    path = tmp_path / "integration.lock"
    with lock(path):
        process = ctx.Process(target=_probe_lock, args=(str(path), child))
        process.start()
        assert parent.poll(10)
        assert parent.recv() == "BUSY"
        process.join(10)
        assert process.exitcode == 0
    with lock(path):
        assert path.exists()
    parent.close()
    child.close()


def test_three_slots_and_fourth_rejected(tmp_path: Path) -> None:
    with (
        slot(tmp_path),
        slot(tmp_path),
        slot(tmp_path),
        pytest.raises(LockBusy, match="Three"),
        slot(tmp_path),
    ):
        raise AssertionError("Fourth slot admitted")
    with slot(tmp_path):
        assert len(list(tmp_path.glob("slot-*.lock"))) == 3


def test_real_worktree_duplicate_branch_and_path(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    git = Git(repo)
    git.run("init", "-b", "main")
    git.run("config", "user.email", "fixture@example.invalid")
    git.run("config", "user.name", "Fixture")
    git.run("commit", "--allow-empty", "-m", "fixture")
    path = tmp_path / "worktree"
    git.create_worktree(path, "agent/T018-fixture", git.sha())
    git.assert_worktree(path, "agent/T018-fixture")
    with pytest.raises(OrchestratorError, match="path already"):
        git.create_worktree(path, "agent/other", git.sha())
    with pytest.raises(OrchestratorError, match="branch already"):
        git.create_worktree(tmp_path / "new", "agent/T018-fixture", git.sha())
    with pytest.raises(OrchestratorError):
        git.create_worktree(tmp_path / "invalid", "agent/../unsafe", git.sha())


@pytest.fixture
def fake_cli(tmp_path: Path) -> Path:
    binary = tmp_path / "fake-cli"
    binary.write_text(f"""#!{sys.executable}
import json, pathlib, sys
args = sys.argv[1:]
if '--version' in args:
    print('fixture-cli 1.0')
elif '--help' in args:
    print('--ask-for-approval --output-schema --output-last-message --sandbox --ephemeral '
          '--prompt --output-format --approval-mode --skip-trust danger-full-access')
else:
    prompt = sys.stdin.read()
    if '--output-format' in args and '--skip-trust' not in args:
        raise SystemExit(55)
    if 'CRASH' in prompt:
        raise SystemExit(8)
    response = ('broken' if 'MALFORMED' in prompt
                else json.dumps({{'fix_prompt': 'Fix synthetic issue'}}))
    if '--output-last-message' in args:
        pathlib.Path(args[args.index('--output-last-message') + 1]).write_text(response)
    else:
        print(json.dumps({{'response': response}}))
""")
    binary.chmod(0o700)
    return binary


@pytest.mark.parametrize("provider", ["codex", "gemini"])
@pytest.mark.parametrize("prompt", ["OK", "CRASH", "MALFORMED"])
def test_cli_provider_protocol(fake_cli: Path, tmp_path: Path, provider: str, prompt: str) -> None:
    role = Role.model_validate({"provider": provider, "executable": str(fake_cli)})
    invoke = CliProvider()

    def call() -> Fix:
        return invoke.run(
            prompt,
            cwd=tmp_path,
            role=role,
            timeout=5,
            output=Fix,
            artifacts=tmp_path,
            name=f"{provider}-{prompt}",
            readonly=True,
        )

    if prompt == "OK":
        result = call()
        assert result.fix_prompt == "Fix synthetic issue"
    else:
        with pytest.raises(OrchestratorError):
            call()
    logs = list(tmp_path.glob("*.log.json"))
    assert logs
    assert all("Fix synthetic issue" not in p.read_text() for p in logs)


def test_gemini_rejects_fictional_reasoning_flag(fake_cli: Path, tmp_path: Path) -> None:
    with pytest.raises(OrchestratorError, match="no reasoning-effort"):
        CliProvider().run(
            "OK",
            cwd=tmp_path,
            role=Role(provider="gemini", executable=str(fake_cli), reasoning="high"),
            timeout=5,
            output=Fix,
            artifacts=tmp_path,
            name="effort",
            readonly=False,
        )


def _lock_owner_with_live_child(root: str) -> None:
    directory = Path(root)
    with lock(directory / "integration.lock"):
        execute(
            [
                sys.executable,
                "-c",
                "import os,time; from pathlib import Path; "
                "Path('child.pid').write_text(str(os.getpid())); "
                "\nwhile not Path('finish').exists(): time.sleep(0.02)",
            ],
            directory,
            timeout=20,
        )


def test_posix_crashed_parent_keeps_lock_until_live_child_exits(tmp_path: Path) -> None:
    import os
    import signal
    import time

    assert os.name == "posix", "This recovery test requires the documented Linux/WSL host"
    ctx = multiprocessing.get_context("spawn")
    owner = ctx.Process(target=_lock_owner_with_live_child, args=(str(tmp_path),))
    owner.start()
    child_pid = None
    try:
        deadline = time.monotonic() + 10
        while not (tmp_path / "child.pid").exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert (tmp_path / "child.pid").exists()
        child_pid = int((tmp_path / "child.pid").read_text())
        owner.kill()
        owner.join(10)
        assert owner.exitcode != 0
        with pytest.raises(LockBusy), lock(tmp_path / "integration.lock"):
            raise AssertionError("Orphan CLI still owns inherited lock")
        (tmp_path / "finish").touch()
        deadline = time.monotonic() + 10
        while True:
            try:
                with lock(tmp_path / "integration.lock"):
                    break
            except LockBusy:
                assert time.monotonic() < deadline
                time.sleep(0.02)
    finally:
        if owner.is_alive():
            owner.kill()
        owner.join(10)
        if child_pid is not None:
            with suppress(ProcessLookupError):
                os.kill(child_pid, signal.SIGKILL)


def test_process_output_is_bounded_while_running(tmp_path: Path) -> None:
    result = execute(
        [
            sys.executable,
            "-c",
            "import sys,time; sys.stdout.write('x' * 5000000); sys.stdout.flush(); time.sleep(10)",
        ],
        tmp_path,
        timeout=5,
    )
    assert result.oversized
    assert result.exit_code != 0
    assert not result.timed_out
    assert len(result.stdout) <= 4 * 1024 * 1024


@pytest.mark.parametrize("provider", ["codex", "gemini"])
def test_provider_unavailable(provider: str, tmp_path: Path) -> None:
    with pytest.raises(OrchestratorError, match="Executable unavailable"):
        CliProvider().run(
            "No paid inference",
            cwd=tmp_path,
            role=Role.model_validate(
                {"provider": provider, "executable": str(tmp_path / "absent")}
            ),
            timeout=1,
            output=Fix,
            artifacts=tmp_path,
            name="missing",
            readonly=True,
        )


def test_dependency_done_checkbox_is_not_sufficient(tmp_path: Path) -> None:
    from tools.orchestrator.core import task_card

    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks/t100-child.md").write_text("""# T100
**Task ID:** `T100`
**Title:** Child
**Status:** `PENDING`
**Goal:** Child behavior
## Dependencies
- T101
## Files được phép sửa
- `child.py`
## Acceptance criteria
- [ ] Child behavior
## Verification commands
```text
python -m pytest
```
""")
    dependency = tmp_path / "tasks/t101-parent.md"
    dependency.write_text("""# T101
**Status:** `DONE`
## Files được phép sửa
- `missing.py`
## Acceptance criteria
- [x] Parent behavior
## Verification commands
```text
python -m pytest
```
""")
    with pytest.raises(OrchestratorError, match="Dependency implementation missing"):
        task_card(tmp_path, "T100")
    (tmp_path / "missing.py").write_text("synthetic implementation")
    dependency.write_text(dependency.read_text().replace("[x]", "[ ]"))
    with pytest.raises(OrchestratorError, match="BLOCKED_FOR_DEPENDENCY: T101"):
        task_card(tmp_path, "T100")


def test_dependency_ids_canonical_and_embedded_tokens() -> None:
    from tools.orchestrator.core import dependency_ids

    # 1. plain standalone
    assert dependency_ids("## Dependencies\nT079\n") == ["T079"]
    assert dependency_ids("## Dependencies\n- T079\n") == ["T079"]

    # 2. Markdown link
    assert dependency_ids("## Dependencies\n- [T079](t079-level2-dag-scheduler.md)\n") == ["T079"]

    # 3. multiple standalone
    assert dependency_ids("## Dependencies\nDepends on T079 and T083\n") == ["T079", "T083"]
    assert dependency_ids("## Dependencies\n- T079\n- T083\n") == ["T079", "T083"]

    # 4. embedded
    assert dependency_ids("## Dependencies\nBLOCKED_BY_T080_T081\n") == []

    # 5. embedded prefix
    assert dependency_ids("## Dependencies\nPREFIX_T080\n") == []

    # 6. embedded suffix
    assert dependency_ids("## Dependencies\nT080_SUFFIX\n") == []

    # 7. adjacent letters
    assert dependency_ids("## Dependencies\nXT080\n") == []
    assert dependency_ids("## Dependencies\nT080X\n") == []

    # Invalid dependency token format (fail-closed)
    with pytest.raises(OrchestratorError, match="Invalid dependency ID: T0800"):
        dependency_ids("## Dependencies\n- T0800\n")
    with pytest.raises(OrchestratorError, match="Invalid dependency ID: T8"):
        dependency_ids("## Dependencies\n- T8\n")


def test_dependency_ids_t018_synthetic_diagnostic_fixture() -> None:
    from tools.orchestrator.core import dependency_ids

    diagnostic_text = """# T018: Synthetic Consent
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
- `frontend/src/features/consent/AiConsentGate.tsx`
## Acceptance criteria
- [ ] Criteria
## Verification commands
```text
git diff --check
```
"""
    dependencies = dependency_ids(diagnostic_text)
    assert dependencies == ["T015", "T017", "T052", "T081"]
    assert "T080" not in dependencies


def test_task_card_ignores_embedded_prose_dependencies(tmp_path: Path) -> None:
    from tools.orchestrator.core import task_card

    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()

    (tasks_dir / "t018-consent.md").write_text("""# T018
**Task ID:** `T018`
**Title:** Consent
**Status:** `TODO`
**Goal:** Consent dialog
## Dependencies
- [T081](t081-app-shell-shadcn-migration.md)
- [T015](t015-consent-api.md)
- [T017](t017-typed-api-client.md)
- [T052](t052-browser-test-harness.md)

BLOCKED_BY_T080_T081
## Files được phép sửa
- `child.py`
## Acceptance criteria
- [ ] Criteria
## Verification commands
```text
python -m pytest
```
""")

    for dep_id, name in [
        ("T081", "shell"),
        ("T015", "api"),
        ("T017", "client"),
        ("T052", "harness"),
    ]:
        impl = tmp_path / f"{name}.py"
        impl.write_text("ok")
        (tasks_dir / f"{dep_id.lower()}-{name}.md").write_text(f"""# {dep_id}
**Task ID:** `{dep_id}`
**Status:** `DONE`
## Files được phép sửa
- `{name}.py`
## Acceptance criteria
- [x] Done behavior
## Verification commands
```text
python -m pytest
```
""")

    card = task_card(tmp_path, "T018")
    assert card.dependencies == ["T015", "T017", "T052", "T081"]
    assert "T080" not in card.dependencies


def test_schema_version_is_strict() -> None:
    data = contract().model_dump()
    data["schema_version"] = True
    with pytest.raises(ValidationError):
        Contract.model_validate(data)


def test_owned_paths_include_annotated_and_approved_extensions() -> None:
    from tools.orchestrator.core import owned_paths

    assert owned_paths("""## Files được phép sửa
- `migration.py` — historical migration owner
- `test_storage.py`, `test_health.py` — approved historical tests
- Cấu hình mở rộng được chấp thuận: `vite.config.ts`, `tsconfig.json`
""") == ["migration.py", "test_storage.py", "test_health.py", "vite.config.ts", "tsconfig.json"]
    with pytest.raises(OrchestratorError, match="no exact owned files"):
        owned_paths("## Files được phép sửa\nNo source ownership\n")
    with pytest.raises(OrchestratorError, match="Unsupported task allowlist"):
        owned_paths("## Files được phép sửa\n- all application files\n")


def test_gemini_worker_is_headless_with_session_trust(
    fake_cli: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools.orchestrator import runtime

    commands: list[list[str]] = []
    original = runtime.execute

    def capture(command: list[str], cwd: Path, **kwargs: Any) -> runtime.ProcessResult:
        commands.append(command)
        return original(command, cwd, **kwargs)

    monkeypatch.setattr(runtime, "execute", capture)
    result = CliProvider().run(
        "OK",
        cwd=tmp_path,
        role=Role(provider="gemini", executable=str(fake_cli)),
        timeout=5,
        output=Fix,
        artifacts=tmp_path,
        name="worker",
        readonly=False,
    )
    assert result.fix_prompt == "Fix synthetic issue"
    command = commands[-1]
    assert "--skip-trust" in command
    assert command[command.index("--approval-mode") + 1] == "yolo"


def test_gemini_missing_session_trust_capability_stops_before_dispatch(
    fake_cli: Path, tmp_path: Path
) -> None:
    fake_cli.write_text(fake_cli.read_text().replace("--skip-trust", "--unknown-trust"))
    with pytest.raises(OrchestratorError, match="required capability: --skip-trust"):
        CliProvider().run(
            "OK",
            cwd=tmp_path,
            role=Role(provider="gemini", executable=str(fake_cli)),
            timeout=5,
            output=Fix,
            artifacts=tmp_path,
            name="unsupported",
            readonly=False,
        )
    assert not list(tmp_path.glob("*.log.json"))


@pytest.fixture
def fake_agy(tmp_path: Path) -> Path:
    binary = tmp_path / "fake-agy"
    binary.write_text(f"""#!{sys.executable}
import json, pathlib, sys, time
args = sys.argv[1:]
if '--version' in args:
    print('1.2.14')
elif '--help' in args:
    print('--print --input-format --output-format --json-schema --mode --model --effort '
          '--dangerously-skip-permissions --disable-slash-commands')
else:
    if '--print' in args or '--print=' in args:
        raise SystemExit(2)
    prompt = sys.stdin.read()
    pathlib.Path('received.json').write_text(json.dumps({{'args': args, 'prompt': prompt}}))
    if 'CRASH' in prompt:
        raise SystemExit(1)
    if 'TIMEOUT' in prompt:
        time.sleep(10)
    value = {{'fix_prompt': 'Synthetic fix'}}
    if 'MALFORMED' in prompt:
        print('invalid JSON')
    elif 'SCHEMA_BAD' in prompt:
        print(json.dumps({{'structured_output': {{'wrong': True}}}}))
    elif 'ERROR' in prompt:
        print(json.dumps({{'is_error': True, 'structured_output': value}}))
    elif 'DENIED' in prompt:
        print(json.dumps({{'status': 'success', 'denied_actions': ['synthetic'],
                          'response': json.dumps(value)}}))
    elif 'STATUS_ERROR' in prompt:
        print(json.dumps({{'status': 'error', 'response': json.dumps(value)}}))
    elif 'NATIVE' in prompt:
        print(json.dumps({{'status': 'SUCCESS', 'response': json.dumps(value)}}))
    elif 'WORKER' in prompt:
        print(json.dumps({{'status': 'IMPLEMENTED', 'summary': 'Synthetic work',
                          'changed_files': [], 'commands_run': [], 'known_issues': []}}))
    elif 'DIRECT' in prompt:
        print(json.dumps(value))
    elif 'TEXT' in prompt:
        print(json.dumps({{'type': 'result', 'result': json.dumps(value)}}))
    else:
        print(json.dumps({{'type': 'result', 'is_error': False,
                          'structured_output': value, 'result': 'Summary'}}))
""")
    binary.chmod(0o700)
    return binary


@pytest.mark.parametrize(
    "prompt",
    [
        "OK",
        "DIRECT",
        "TEXT",
        "NATIVE",
        "DENIED",
        "STATUS_ERROR",
        "MALFORMED",
        "SCHEMA_BAD",
        "ERROR",
        "CRASH",
        "TIMEOUT",
    ],
)
def test_agy_json_protocol(fake_agy: Path, tmp_path: Path, prompt: str) -> None:
    role = Role(
        provider="agy",
        executable=str(fake_agy),
        model="listed-model",
        reasoning="high",
        allow_process=True,
    )

    def call() -> Fix:
        return CliProvider().run(
            prompt,
            cwd=tmp_path,
            role=role,
            timeout=1,
            output=Fix,
            artifacts=tmp_path,
            name="worker",
            readonly=False,
        )

    if prompt in {"OK", "DIRECT", "TEXT", "NATIVE"}:
        assert call().fix_prompt == "Synthetic fix"
    else:
        with pytest.raises(OrchestratorError):
            call()
    log = read_json(tmp_path / "worker.log.json")
    assert isinstance(log, dict)
    assert "Synthetic fix" not in json.dumps(log)
    received = json.loads((tmp_path / "received.json").read_text())
    assert received["prompt"] == prompt
    args = received["args"]
    assert "--print" not in args and "--print=" not in args
    assert "--disable-slash-commands" in args
    assert args[args.index("--mode") + 1] == "accept-edits"
    assert "--dangerously-skip-permissions" in args
    assert args[args.index("--model") + 1] == "listed-model"
    assert args[args.index("--effort") + 1] == "high"
    assert (
        json.loads(Path(args[args.index("--json-schema") + 1]).read_text())
        == Fix.model_json_schema()
    )


@pytest.mark.parametrize("stream", ["stdout", "stderr", "split"])
def test_agy_help_streams_without_unused_print(fake_agy: Path, tmp_path: Path, stream: str) -> None:
    source = fake_agy.read_text()
    source = source.replace("print('--print --input-format", "print('--input-format")
    if stream == "stderr":
        source = source.replace(
            "'--dangerously-skip-permissions --disable-slash-commands')",
            "'--dangerously-skip-permissions --disable-slash-commands', file=sys.stderr)",
        )
    elif stream == "split":
        source = source.replace(
            "print('--input-format --output-format --json-schema --mode --model --effort '",
            "print('--input-format --output-format --json-schema', file=sys.stderr)\n"
            "    print('--mode --model --effort '",
        )
    fake_agy.write_text(source)
    result = CliProvider().run(
        "NATIVE",
        cwd=tmp_path,
        role=Role(
            provider="agy",
            executable=str(fake_agy),
            model="listed-model",
            reasoning="high",
            allow_process=True,
        ),
        timeout=5,
        output=Fix,
        artifacts=tmp_path,
        name="worker",
        readonly=False,
    )
    assert result.fix_prompt == "Synthetic fix"
    received = json.loads((tmp_path / "received.json").read_text())
    assert received["prompt"] == "NATIVE"
    assert "--print" not in received["args"]
    assert "--print=" not in received["args"]


@pytest.mark.parametrize("provider", ["codex", "gemini"])
def test_other_provider_help_on_stderr(fake_cli: Path, tmp_path: Path, provider: str) -> None:
    fake_cli.write_text(
        fake_cli.read_text().replace(
            "'--prompt --output-format --approval-mode --skip-trust danger-full-access')",
            "'--prompt --output-format --approval-mode --skip-trust "
            "danger-full-access', file=sys.stderr)",
        )
    )
    result = CliProvider().run(
        "OK",
        cwd=tmp_path,
        role=Role.model_validate({"provider": provider, "executable": str(fake_cli)}),
        timeout=5,
        output=Fix,
        artifacts=tmp_path,
        name="review",
        readonly=True,
    )
    assert result.fix_prompt == "Fix synthetic issue"


@pytest.mark.parametrize("failure", ["exit", "timeout", "oversized"])
def test_agy_failed_help_probe_does_not_dispatch(
    fake_agy: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    from dataclasses import replace

    from tools.orchestrator import runtime

    fake_agy.write_text(
        fake_agy.read_text().replace(
            "'--dangerously-skip-permissions --disable-slash-commands')",
            "'--dangerously-skip-permissions --disable-slash-commands', file=sys.stderr)",
        )
    )
    original = runtime.execute
    commands: list[list[str]] = []

    def probe(
        command: list[str], cwd: Path, *, timeout: int | None = None, stdin: str | None = None
    ) -> runtime.ProcessResult:
        commands.append(command)
        result = original(command, cwd, timeout=timeout, stdin=stdin)
        if "--help" in command:
            return replace(
                result,
                exit_code=1 if failure == "exit" else 0,
                timed_out=failure == "timeout",
                oversized=failure == "oversized",
            )
        return result

    monkeypatch.setattr(runtime, "execute", probe)
    with pytest.raises(OrchestratorError, match="Provider CLI capability probe failed"):
        CliProvider().run(
            "OK",
            cwd=tmp_path,
            role=Role(provider="agy", executable=str(fake_agy)),
            timeout=5,
            output=Fix,
            artifacts=tmp_path,
            name="failed-probe",
            readonly=False,
        )
    assert commands == [[str(fake_agy), "--version"], [str(fake_agy), "--help"]]
    assert not (tmp_path / "received.json").exists()


@pytest.mark.parametrize("readonly,allow", [(True, False), (True, True), (False, False)])
def test_agy_plan_and_permissions(
    fake_agy: Path, tmp_path: Path, readonly: bool, allow: bool
) -> None:
    CliProvider().run(
        "OK",
        cwd=tmp_path,
        role=Role(provider="agy", executable=str(fake_agy), allow_process=allow),
        timeout=5,
        output=Fix,
        artifacts=tmp_path,
        name="plan",
        readonly=readonly,
    )
    args = json.loads((tmp_path / "received.json").read_text())["args"]
    assert args[args.index("--mode") + 1] == ("plan" if readonly else "accept-edits")
    assert "--dangerously-skip-permissions" not in args


@pytest.mark.parametrize(
    "flag",
    [
        "--json-schema",
        "--input-format",
        "--output-format",
        "--mode",
        "--dangerously-skip-permissions",
        "--model",
        "--effort",
        "--disable-slash-commands",
    ],
)
def test_agy_missing_capability_never_dispatches(fake_agy: Path, tmp_path: Path, flag: str) -> None:
    fake_agy.write_text(fake_agy.read_text().replace(flag, "--unsupported"))
    with pytest.raises(OrchestratorError, match="capability"):
        CliProvider().run(
            "OK",
            cwd=tmp_path,
            role=Role(
                provider="agy",
                executable=str(fake_agy),
                model="listed-model",
                reasoning="high",
                allow_process=True,
            ),
            timeout=5,
            output=Fix,
            artifacts=tmp_path,
            name="missing",
            readonly=False,
        )
    assert not (tmp_path / "received.json").exists()


@pytest.mark.parametrize("readonly", [False, True])
def test_codex_worker_full_access_does_not_elevate_readonly(
    fake_cli: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, readonly: bool
) -> None:
    from tools.orchestrator import runtime

    commands: list[list[str]] = []
    original = runtime.execute

    def capture(command: list[str], cwd: Path, **kwargs: Any) -> runtime.ProcessResult:
        commands.append(command)
        return original(command, cwd, **kwargs)

    monkeypatch.setattr(runtime, "execute", capture)
    CliProvider().run(
        "OK",
        cwd=tmp_path,
        role=Role(provider="codex", executable=str(fake_cli), worker_access="full-access"),
        timeout=5,
        output=Fix,
        artifacts=tmp_path,
        name="gpt",
        readonly=readonly,
    )
    command = commands[-1]
    assert command[command.index("--sandbox") + 1] == (
        "read-only" if readonly else "danger-full-access"
    )
    assert command[command.index("-a") + 1] == "never"


def test_agy_direct_worker_status_is_not_cli_envelope_error(fake_agy: Path, tmp_path: Path) -> None:
    from tools.orchestrator.core import WorkerResult

    result = CliProvider().run(
        "WORKER",
        cwd=tmp_path,
        role=Role(provider="agy", executable=str(fake_agy)),
        timeout=5,
        output=WorkerResult,
        artifacts=tmp_path,
        name="direct-worker",
        readonly=False,
    )
    assert result.status == "IMPLEMENTED"


@pytest.mark.parametrize(
    "provider,permission",
    [
        ("gemini", "worker_access"),
        ("agy", "worker_access"),
        ("codex", "allow_process"),
        ("gemini", "allow_process"),
    ],
)
def test_provider_rejects_unsupported_permission_before_dispatch(
    fake_cli: Path, tmp_path: Path, provider: str, permission: str
) -> None:
    data = {
        "provider": provider,
        "executable": str(fake_cli),
        permission: "full-access" if permission == "worker_access" else True,
    }
    with pytest.raises(OrchestratorError, match="supported only"):
        CliProvider().run(
            "OK",
            cwd=tmp_path,
            role=Role.model_validate(data),
            timeout=5,
            output=Fix,
            artifacts=tmp_path,
            name="unsupported",
            readonly=False,
        )
    assert not list(tmp_path.glob("*.log.json"))


def test_agy_rejects_unsupported_effort_before_dispatch(fake_agy: Path, tmp_path: Path) -> None:
    with pytest.raises(OrchestratorError, match="xhigh is unsupported"):
        CliProvider().run(
            "OK",
            cwd=tmp_path,
            role=Role(provider="agy", executable=str(fake_agy), reasoning="xhigh"),
            timeout=5,
            output=Fix,
            artifacts=tmp_path,
            name="effort",
            readonly=False,
        )
    assert not (tmp_path / "received.json").exists()


def test_agy_unavailable(tmp_path: Path) -> None:
    with pytest.raises(OrchestratorError, match="Executable unavailable"):
        CliProvider().run(
            "OK",
            cwd=tmp_path,
            role=Role(provider="agy", executable=str(tmp_path / "absent")),
            timeout=5,
            output=Fix,
            artifacts=tmp_path,
            name="unavailable",
            readonly=False,
        )


def test_codex_missing_full_access_capability_stops_before_dispatch(
    fake_cli: Path, tmp_path: Path
) -> None:
    fake_cli.write_text(fake_cli.read_text().replace("danger-full-access", "unsupported-access"))
    with pytest.raises(OrchestratorError, match="required capability: danger-full-access"):
        CliProvider().run(
            "OK",
            cwd=tmp_path,
            role=Role(provider="codex", executable=str(fake_cli), worker_access="full-access"),
            timeout=5,
            output=Fix,
            artifacts=tmp_path,
            name="unsupported",
            readonly=False,
        )
    assert not list(tmp_path.glob("*.log.json"))


def test_audit_schema_explains_actionable_findings_and_positive_evidence() -> None:
    schema = Audit.model_json_schema()
    findings = schema["properties"]["findings"]["description"]
    evidence = schema["$defs"]["Criterion"]["properties"]["evidence"]["description"]
    status = schema["properties"]["status"]["description"]
    assert "actionable" in findings and "unresolved" in findings
    assert "acceptance_criteria" in findings and "evidence" in findings
    assert "successful" in evidence
    assert "PASS" in status and "empty" in status
    assert set(schema["required"]) == {
        "status",
        "findings",
        "acceptance_criteria",
        "scope_violations",
        "required_fixes",
        "reviewer_dispositions",
    }


@pytest.mark.parametrize("supplied", ["omitted", "null", "finite"])
def test_task_timeout_configuration_is_opt_in(supplied: str) -> None:
    data: dict[str, object] = {
        "roles": {
            name: {"provider": "codex", "executable": "fake-codex"}
            for name in ("prompt_engineer", "worker", "auditor", "integrator")
        },
        "verification": [["python", "-m", "pytest"]],
    }
    if supplied != "omitted":
        data["timeout_seconds"] = 5400 if supplied == "finite" else None
    config = Config.model_validate(data)
    expected = 5400 if supplied == "finite" else None
    assert config.timeout_seconds == expected
    restored = Config.model_validate_json(config.model_dump_json())
    assert restored.timeout_seconds == expected


@pytest.mark.parametrize("value", [0, -1, True, False, "5400", 1.5, 86401])
def test_invalid_explicit_task_timeouts_are_rejected(value: object) -> None:
    with pytest.raises(ValidationError):
        Config.model_validate(
            {
                "roles": {},
                "verification": [["python", "-m", "pytest"]],
                "timeout_seconds": value,
            }
        )


@pytest.mark.parametrize("explicit_null", [False, True])
def test_unlimited_process_has_no_implicit_deadline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, explicit_null: bool
) -> None:
    ticks = iter(range(0, 1000000, 100000))
    monkeypatch.setattr("tools.orchestrator.runtime.monotonic", lambda: next(ticks))
    command = [sys.executable, "-c", "import time; time.sleep(.15); print('finished')"]
    result = (
        execute(command, tmp_path, timeout=None) if explicit_null else execute(command, tmp_path)
    )
    assert result.exit_code == 0
    assert result.stdout.strip() == "finished"
    assert not result.timed_out


def test_unlimited_process_still_enforces_output_limit(tmp_path: Path) -> None:
    result = execute(
        [
            sys.executable,
            "-c",
            "import sys,time; sys.stdout.write('x'*5000000); sys.stdout.flush(); time.sleep(10)",
        ],
        tmp_path,
        timeout=None,
    )
    assert result.oversized
    assert result.exit_code != 0
    assert not result.timed_out
    assert len(result.stdout) <= 4 * 1024 * 1024


def test_unlimited_process_interrupt_kills_and_reaps_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    communicate = subprocess.Popen.communicate
    children: list[subprocess.Popen[bytes]] = []

    def interrupt_once(
        process: subprocess.Popen[bytes],
        input: bytes | None = None,
        timeout: float | None = None,
    ) -> tuple[bytes | None, bytes | None]:
        if not children:
            children.append(process)
            raise KeyboardInterrupt
        return communicate(process, input=input, timeout=timeout)

    monkeypatch.setattr(subprocess.Popen, "communicate", interrupt_once)
    with pytest.raises(KeyboardInterrupt):
        execute([sys.executable, "-c", "import time; time.sleep(20)"], tmp_path, timeout=None)
    assert len(children) == 1
    assert children[0].poll() is not None
    assert children[0].returncode != 0


@pytest.mark.parametrize("provider", ["codex", "gemini", "agy"])
def test_provider_supports_unlimited_task_execution(
    fake_cli: Path, fake_agy: Path, tmp_path: Path, provider: str
) -> None:
    role = Role.model_validate(
        {
            "provider": provider,
            "executable": str(fake_agy if provider == "agy" else fake_cli),
        }
    )
    result = CliProvider().run(
        "OK",
        cwd=tmp_path,
        role=role,
        timeout=None,
        output=Fix,
        artifacts=tmp_path,
        name="unlimited",
        readonly=True,
    )
    assert result.fix_prompt == ("Synthetic fix" if provider == "agy" else "Fix synthetic issue")


def test_t081_allowlist_is_exact_and_parseable() -> None:
    from tools.orchestrator.core import owned_paths, section

    root = Path(__file__).resolve().parents[2]
    text = (root / "tasks/t081-app-shell-shadcn-migration.md").read_text(encoding="utf-8")
    expected = [
        "frontend/src/app/AppShell.tsx",
        "frontend/src/app/shell.css",
        "frontend/src/app/AppShell.test.tsx",
        "frontend/tests/e2e/shell.spec.ts",
        "package.json",
        "package-lock.json",
    ]
    bullets = [
        line for line in section(text, "Files được phép sửa").splitlines() if line.startswith("- ")
    ]
    assert bullets == [f"- `{path}`" for path in expected]
    assert owned_paths(text) == expected


def test_default_orchestrator_config_uses_portable_baseline() -> None:
    root = Path(__file__).resolve().parents[2]
    config = Config.model_validate_json((root / "orchestrator.yaml").read_text(encoding="utf-8"))
    config.validate_roles()
    assert config.verification == [
        ["npm", "run", "check:task:portable"],
        ["python", "-m", "ruff", "check", "."],
        ["python", "-m", "mypy", "backend", "tools/orchestrator"],
    ]


def test_t081_executable_verification_is_concise_and_snapshot_separate() -> None:
    from tools.orchestrator.core import check_commands, section, validate_command

    root = Path(__file__).resolve().parents[2]
    text = (root / "tasks/t081-app-shell-shadcn-migration.md").read_text(encoding="utf-8")
    commands = check_commands(text)
    assert commands == [
        ["npm", "run", "test:frontend", "--", "frontend/src/app/AppShell.test.tsx"],
        ["npm", "run", "typecheck"],
        ["npm", "run", "architecture:frontend"],
        ["git", "diff", "--check"],
    ]
    for command in commands:
        validate_command(command)
        assert all(not any(token in arg for token in ("=", "#", "|", "&&", ">")) for arg in command)
    snapshot = section(text, "Snapshot results")
    assert (
        'QUALITY_BASE_REF="035430d668f1f754afd38e3cca9d630eb90a69a7" npm run coverage:check'
        " # Exit 0, changed 100.00%, total 93.40%"
    ) in snapshot
    assert "# Exit 0, 48 passed (4 viewports x 12 tests)" in snapshot
    assert "# Exit 0, 8 passed" in snapshot


def test_real_t018_preflight_with_normalized_t081() -> None:
    from tools.orchestrator.core import dependency_ids, task_card
    from tools.orchestrator.scheduler import metadata

    root = Path(__file__).resolve().parents[2]
    path = "tasks/t018-consent-ui.md"
    text = (root / path).read_text(encoding="utf-8")
    card = task_card(root, "T018")
    assert card.task_id == "T018"
    assert card.dependencies == dependency_ids(text) == metadata(path, text).dependencies
    assert card.dependencies == ["T015", "T017", "T052", "T081"]
    assert "T080" not in card.dependencies
    assert len(card.dependency_verification) == 11
    t081_commands = [
        ["npm", "run", "test:frontend", "--", "frontend/src/app/AppShell.test.tsx"],
        ["npm", "run", "typecheck"],
        ["npm", "run", "architecture:frontend"],
        ["git", "diff", "--check"],
    ]
    for cmd in t081_commands:
        assert cmd in card.dependency_verification


def test_portable_python_uses_approved_parallelism_and_only_windows_exclusion() -> None:
    root = Path(__file__).resolve().parents[2]
    scripts = json.loads((root / "package.json").read_text(encoding="utf-8"))["scripts"]
    command = shlex.split(scripts["test:python:portable"])
    assert command == ["python", "-m", "pytest", "--ignore=backend/tests/windows", "-n", "10"]
    runner = (root / ".agent/scripts/run-gates.sh").read_text(encoding="utf-8")
    assert re.findall(r"^[ \t]*-n (\d+)[ \t]*(?:\\)?$", runner, re.M) == [
        command[-1],
        command[-1],
    ]


def _setup_gate_runner_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "fixture@example.invalid"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Fixture"], cwd=repo, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "init"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    state_dir = tmp_path / "state"
    state_dir.mkdir()

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()

    fake_npm = bin_dir / "npm"
    fake_npm.write_text(
        f"""#!{sys.executable}
import json, os, pathlib, sys, time

args = sys.argv[1:]
if not args or args[0] != "run":
    sys.exit(0)

gate = args[1]
state = pathlib.Path(os.environ["FAKE_NPM_STATE"])
with (state / "invocations.txt").open("a", encoding="utf-8") as f:
    f.write(f"{{gate}}\\n")

fail_gate = os.environ.get("FAIL_GATE")
if fail_gate == gate:
    (state / f"failed_{{gate.replace(':', '_')}}").touch()
    sys.exit(42)

start_time = time.monotonic()
if gate == "test:frontend:coverage":
    time.sleep(0.05)
    (state / "frontend_done").touch()
elif gate == "test:python:portable":
    time.sleep(0.05)
    (state / "python_done").touch()
elif gate == "coverage:check":
    frontend_done = (state / "frontend_done").exists()
    python_done = (state / "python_done").exists()
    if not (frontend_done and python_done):
        (state / "coverage_raced").touch()
        sys.exit(99)
    (state / "coverage_check_done").touch()

end_time = time.monotonic()
record = {{"gate": gate, "start": start_time, "end": end_time}}
(state / f"{{gate.replace(':', '_')}}.json").write_text(json.dumps(record), encoding="utf-8")
sys.exit(0)
"""
    )
    fake_npm.chmod(0o755)
    return repo, bin_dir, state_dir


def test_portable_task_baseline_retains_all_semantic_gates() -> None:
    root = Path(__file__).resolve().parents[2]
    scripts = json.loads((root / "package.json").read_text(encoding="utf-8"))["scripts"]
    assert scripts["check:task:portable"] == "bash .agent/scripts/run-gates.sh portable-task"

    runner_text = (root / ".agent/scripts/run-gates.sh").read_text(encoding="utf-8")
    assert "portable-task)" in runner_text

    expected_gates = (
        "check:fast:active",
        "test:frontend:coverage",
        "test:python:portable",
        "security:secrets",
        "security:code",
        "security:deps",
        "architecture:check",
        "coverage:check",
    )
    for gate in expected_gates:
        assert f"npm run {gate}" in runner_text, f"Missing gate {gate} in run-gates.sh"


def test_portable_task_runner_success_and_coverage_synchronization(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    runner_script = root / ".agent/scripts/run-gates.sh"
    repo, bin_dir, state_dir = _setup_gate_runner_fixture(tmp_path)

    env = dict(os.environ)
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    env["FAKE_NPM_STATE"] = str(state_dir)
    env.pop("FAIL_GATE", None)

    res = subprocess.run(
        ["bash", str(runner_script), "portable-task"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
    )

    assert res.returncode == 0, f"Runner failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    assert "RESULT: PASS" in res.stdout
    for gate_name in (
        "check-fast-active",
        "frontend-coverage",
        "portable-pytest",
        "security-secrets",
        "security-code",
        "security-deps",
        "architecture",
        "coverage-check",
    ):
        assert re.search(rf"{gate_name}\s+PASS", res.stdout), f"Missing {gate_name} PASS in summary"

    # Verify coverage synchronization
    assert (state_dir / "frontend_done").exists()
    assert (state_dir / "python_done").exists()
    assert (state_dir / "coverage_check_done").exists()
    assert not (state_dir / "coverage_raced").exists()

    frontend_record = json.loads(
        (state_dir / "test_frontend_coverage.json").read_text(encoding="utf-8")
    )
    python_record = json.loads(
        (state_dir / "test_python_portable.json").read_text(encoding="utf-8")
    )
    cov_record = json.loads((state_dir / "coverage_check.json").read_text(encoding="utf-8"))

    assert cov_record["start"] >= frontend_record["end"]
    assert cov_record["start"] >= python_record["end"]

    # Verify exact set of invoked gates
    invocations = (state_dir / "invocations.txt").read_text(encoding="utf-8").splitlines()
    assert set(invocations) == {
        "check:fast:active",
        "test:frontend:coverage",
        "test:python:portable",
        "security:secrets",
        "security:code",
        "security:deps",
        "architecture:check",
        "coverage:check",
    }
    assert invocations[-1] == "coverage:check"


@pytest.mark.parametrize("failing_gate", ["security:code", "test:python:portable"])
def test_portable_task_runner_failure_propagation(tmp_path: Path, failing_gate: str) -> None:
    root = Path(__file__).resolve().parents[2]
    runner_script = root / ".agent/scripts/run-gates.sh"
    repo, bin_dir, state_dir = _setup_gate_runner_fixture(tmp_path)

    env = dict(os.environ)
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    env["FAKE_NPM_STATE"] = str(state_dir)
    env["FAIL_GATE"] = failing_gate

    res = subprocess.run(
        ["bash", str(runner_script), "portable-task"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
    )

    assert res.returncode == 1
    assert "Phase failed; stopping later phases." in res.stdout
    assert "RESULT: PASS" not in res.stdout

    # Prove failure was recorded
    failed_marker = state_dir / f"failed_{failing_gate.replace(':', '_')}"
    assert failed_marker.exists()

    # Prove dependent coverage:check was NOT executed
    assert not (state_dir / "coverage_check_done").exists()
    invocations = (state_dir / "invocations.txt").read_text(encoding="utf-8").splitlines()
    assert "coverage:check" not in invocations


@pytest.mark.parametrize(
    "name,expected",
    [
        ("check:task", "npm run check:task:active && npm run architecture:check"),
        (
            "check:task:active",
            "npm run check:fast:active && npm run test:frontend:coverage && python -m pytest"
            " && npm run coverage:check && npm run security:secrets"
            " && npm run security:code && npm run security:deps",
        ),
        ("check:full", "npm run check:task:active && npm run architecture:check"),
    ],
)
def test_authoritative_full_gates_remain_unchanged(name: str, expected: str) -> None:
    root = Path(__file__).resolve().parents[2]
    scripts = json.loads((root / "package.json").read_text(encoding="utf-8"))["scripts"]
    assert scripts[name] == expected


def test_no_task_id_specific_scheduler_or_runtime_exceptions() -> None:
    root = Path(__file__).resolve().parents[2] / "tools/orchestrator"
    for path in root.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for task_id in ("T008", "T018", "T021", "T023", "T027", "T034"):
            assert task_id not in text, f"Hardcoded task ID {task_id} in {path.name}"


@pytest.mark.parametrize("mode", ["success", "exit", "timeout", "oversized", "setup", "oserror"])
def test_concurrent_audit_collection_detached_inputs_and_failure_semantics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    from dataclasses import FrozenInstanceError, fields

    from tools.orchestrator.core import VerificationRequest
    from tools.orchestrator.runtime import ProcessResult
    from tools.orchestrator.workflow import collect_verification

    commands = (("python", "-m", "pytest"), ("python", "-m", "ruff"), ("git", "diff", "--check"))
    request = VerificationRequest(
        tmp_path,
        commands,
        None,
        FrozenEvidenceIdentity.freeze("T100", "a" * 64, "feature/test", "a" * 64, commands),
    )
    assert {field.name for field in fields(request)} == {
        "cwd",
        "commands",
        "timeout",
        "identity",
    }
    for field in fields(request):
        with pytest.raises(FrozenInstanceError):
            setattr(request, field.name, getattr(request, field.name))
    executed: list[tuple[str, ...]] = []

    def executing(command: list[str], cwd: Path, *, timeout: int | None = None) -> ProcessResult:
        assert cwd == tmp_path and timeout is None
        executed.append(tuple(command))
        failing = len(executed) == 2 and mode != "success"
        if failing and mode == "setup":
            raise OrchestratorError("Executable unavailable: synthetic")
        if failing and mode == "oserror":
            raise PermissionError("synthetic-private-os-error-sentinel")
        return ProcessResult(
            command=tuple(command),
            cwd=str(cwd),
            started_at="start",
            ended_at="end",
            exit_code=9 if failing and mode == "exit" else 0,
            stdout=f"synthetic-{len(executed)}",
            stderr="synthetic diagnostic",
            timed_out=failing and mode == "timeout",
            oversized=failing and mode == "oversized",
        )

    monkeypatch.setattr("tools.orchestrator.workflow.execute", executing)
    collection = collect_verification(request)
    expected_cmds = list(commands)[: 3 if mode == "success" else 2]
    assert len(executed) == len(expected_cmds)
    for exec_cmd, orig_cmd in zip(executed, expected_cmds, strict=True):
        if exec_cmd[0].endswith("env"):
            assert exec_cmd[1].startswith("PATH=")
            assert str(tmp_path / ".venv") in exec_cmd[1]
            assert str(tmp_path / "node_modules/.bin") in exec_cmd[1]
            assert list(exec_cmd[2:]) == list(orig_cmd)
        else:
            assert list(exec_cmd) == list(orig_cmd)
    setup = mode in {"setup", "oserror"}
    assert collection.failed is (mode in {"exit", "timeout", "oversized"})
    assert (collection.setup_error is not None) is setup
    if setup:
        assert collection.setup_error is not None and "SETUP_FAILED" in collection.setup_error
        assert "synthetic-private-os-error-sentinel" not in collection.setup_error
    assert [result["command_index"] for result in collection.results] == list(
        range(1 if setup else 3 if mode == "success" else 2)
    )
    assert [result["stdout_digest"] for result in collection.results] == [
        digest(f"synthetic-{index}".encode()) for index in range(1, len(collection.results) + 1)
    ]
    assert all("stdout" not in result and "stderr" not in result for result in collection.results)
    assert not list(tmp_path.iterdir())  # Collector cannot persist/register evidence.


def test_concurrent_audit_transient_output_isolated_from_request_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools.orchestrator.core import VerificationRequest
    from tools.orchestrator.runtime import ProcessResult
    from tools.orchestrator.workflow import collect_verification

    commands = (("python", "-m", "pytest"),)
    request = VerificationRequest(
        tmp_path,
        commands,
        None,
        FrozenEvidenceIdentity.freeze("T100", "b" * 64, "feature/test", "b" * 64, commands),
    )

    def executing(command: list[str], cwd: Path, *, timeout: int | None = None) -> ProcessResult:
        assert cwd == tmp_path and timeout is None
        cache_dir = cwd / ".pytest_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / "transient").write_text("transient pytest cache content")
        return ProcessResult(
            command=tuple(command),
            cwd=str(cwd),
            started_at="start",
            ended_at="end",
            exit_code=0,
            stdout="collected stdout",
            stderr="",
            timed_out=False,
            oversized=False,
        )

    monkeypatch.setattr("tools.orchestrator.workflow.execute", executing)
    collection = collect_verification(request)
    assert not collection.failed
    assert len(collection.results) == 1
    assert "transient" not in json.dumps(collection.results[0])
    assert ".pytest_cache" not in json.dumps(collection.results[0])
    assert (tmp_path / ".pytest_cache/transient").is_file()


def test_concurrent_audit_toolchain_backlink_validation_rules(tmp_path: Path) -> None:
    from tools.orchestrator.core import OrchestratorError
    from tools.orchestrator.workflow import validate_toolchain_backlinks

    worktree = tmp_path / "worktree"
    worktree.mkdir()
    (worktree / "src").mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()
    auth_roots = {worktree.resolve(), repo.resolve()}

    # 1. Safe toolchain with internal relative symlink
    safe_nm = worktree / "safe_node_modules"
    safe_nm.mkdir()
    (safe_nm / "typescript/bin").mkdir(parents=True)
    (safe_nm / "typescript/bin/tsc").write_text("tsc")
    (safe_nm / ".bin").mkdir()
    (safe_nm / ".bin/tsc").symlink_to("../typescript/bin/tsc")
    validate_toolchain_backlinks(safe_nm, auth_roots)

    # 2. Toolchain root itself resolves to worktree
    root_link = worktree / "root_link"
    root_link.symlink_to(worktree)
    with pytest.raises(OrchestratorError, match="Unsafe toolchain root"):
        validate_toolchain_backlinks(root_link, auth_roots)

    # 3. Direct symlink inside node_modules pointing to worktree
    unsafe_nm = worktree / "unsafe_node_modules"
    unsafe_nm.mkdir()
    (unsafe_nm / "local-candidate").symlink_to(worktree)
    with pytest.raises(OrchestratorError, match="Unsafe toolchain backlink"):
        validate_toolchain_backlinks(unsafe_nm, auth_roots)

    # 4. Relative escaping symlink pointing to worktree/src
    escaping_nm = worktree / "escaping_node_modules"
    escaping_nm.mkdir()
    (escaping_nm / "escape").symlink_to(Path("../src"))
    with pytest.raises(OrchestratorError, match="Unsafe toolchain backlink"):
        validate_toolchain_backlinks(escaping_nm, auth_roots)

    # 5. External directory with nested backlink into repo
    ext_dir = tmp_path / "external"
    ext_dir.mkdir()
    (ext_dir / "back_to_repo").symlink_to(repo)
    nested_nm = worktree / "nested_nm"
    nested_nm.mkdir()
    (nested_nm / "ext_link").symlink_to(ext_dir)
    with pytest.raises(OrchestratorError, match="Unsafe toolchain backlink"):
        validate_toolchain_backlinks(nested_nm, auth_roots)

    # 6. Unresolvable circular symlink loop
    loop_nm = worktree / "loop_nm"
    loop_nm.mkdir()
    (loop_nm / "a").symlink_to(loop_nm / "b")
    (loop_nm / "b").symlink_to(loop_nm / "a")
    with pytest.raises(OrchestratorError, match="Unresolvable toolchain symlink"):
        validate_toolchain_backlinks(loop_nm, auth_roots)


def valid_candidate_provenance() -> CandidateProvenance:
    sha = "a" * 64
    return CandidateProvenance(
        base_sha=sha,
        branch="feature/t088",
        head_sha=sha,
        source_digest=sha,
        changed_paths=["tasks/t088-deterministic-evidence-bundle.md"],
        staged_paths=[],
        staged_diff_digest=sha,
        unstaged_paths=["tasks/t088-deterministic-evidence-bundle.md"],
        unstaged_diff_digest=sha,
        untracked_paths=[],
        untracked_digest=sha,
    )


def valid_scope_evidence() -> ScopeEvidence:
    return ScopeEvidence(
        allowed_paths=["docs/changelogs.md", "tasks/t088-deterministic-evidence-bundle.md"],
        actual_changed_paths=["tasks/t088-deterministic-evidence-bundle.md"],
        unexpected_changed_paths=[],
        verdict="PASS",
    )


def valid_verification_evidence() -> VerificationEvidence:
    sha = "a" * 64
    return VerificationEvidence(
        identity=FrozenEvidenceIdentity(
            task_id="T088",
            base_sha=sha,
            branch="feature/t088",
            source_digest=sha,
            required_command_digests=(sha,),
        ),
        commands=[
            VerificationCommandEvidence(
                command_index=0,
                declaration_digest=sha,
                command=["python", "<arguments withheld>"],
                exit_code=0,
                timed_out=False,
                oversized=False,
                stdout_bytes=100,
                stderr_bytes=0,
                stdout_digest=sha,
                stderr_digest=sha,
                duration_ns=1_000_000,
            )
        ],
        passed=True,
        failed=False,
        setup_error=None,
    )


def valid_evidence_bundle() -> EvidenceBundle:
    sha = "a" * 64
    prov = valid_candidate_provenance()
    scope = valid_scope_evidence()
    verif = valid_verification_evidence()
    timing = TimingEvidence(duration_ns=5_000_000)
    artifact = EvidenceArtifactRef(
        name="audit_checks",
        path="00-audit_checks.json",
        digest=sha,
        byte_size=123,
        classification="test_execution_record",
        identity=verif.identity,
    )
    return EvidenceBundle(
        schema_version=1,
        task_id="T088",
        base_sha=sha,
        branch="feature/t088",
        source_digest=sha,
        provenance=prov,
        scope=scope,
        verification=verif,
        artifacts=[artifact],
        timing=timing,
        is_complete=True,
    )


def test_evidence_bundle_strict_schema_and_version_validation() -> None:
    bundle = valid_evidence_bundle()
    assert bundle.schema_version == 1
    assert bundle.is_complete is True

    # Unknown version rejected
    data = bundle.model_dump()
    data["schema_version"] = 2
    with pytest.raises(ValidationError):
        EvidenceBundle.model_validate(data)

    data["schema_version"] = 0
    with pytest.raises(ValidationError):
        EvidenceBundle.model_validate(data)

    # Extra forbidden fields rejected
    data = bundle.model_dump()
    data["extra_ai_field"] = "unexpected"
    with pytest.raises(ValidationError):
        EvidenceBundle.model_validate(data)


def test_candidate_provenance_validation_and_ordering() -> None:
    prov = valid_candidate_provenance()
    # Unsorted paths rejected
    data = prov.model_dump()
    data["changed_paths"] = ["z.py", "a.py"]
    with pytest.raises(ValidationError, match="canonically sorted"):
        CandidateProvenance.model_validate(data)

    # Duplicate paths rejected
    data = prov.model_dump()
    data["changed_paths"] = ["a.py", "a.py"]
    with pytest.raises((ValidationError, OrchestratorError), match="Duplicate paths"):
        CandidateProvenance.model_validate(data)

    # Unsafe path rejected
    data = prov.model_dump()
    data["changed_paths"] = ["../escape.py"]
    with pytest.raises((ValidationError, OrchestratorError), match="Unsafe"):
        CandidateProvenance.model_validate(data)


def test_scope_evidence_validation() -> None:
    scope = valid_scope_evidence()
    # Out of order allowed_paths rejected
    data = scope.model_dump()
    data["allowed_paths"] = ["b.py", "a.py"]
    with pytest.raises((ValidationError, OrchestratorError), match="canonically sorted"):
        ScopeEvidence.model_validate(data)

    # PASS with unexpected paths rejected
    data = scope.model_dump()
    data["actual_changed_paths"] = ["a.py", "unexpected.py"]
    data["allowed_paths"] = ["a.py"]
    data["unexpected_changed_paths"] = ["unexpected.py"]
    data["verdict"] = "PASS"
    with pytest.raises((ValidationError, OrchestratorError), match="cannot be PASS"):
        ScopeEvidence.model_validate(data)

    # FAIL without unexpected paths rejected
    data = scope.model_dump()
    data["verdict"] = "FAIL"
    with pytest.raises((ValidationError, OrchestratorError), match="cannot be FAIL"):
        ScopeEvidence.model_validate(data)


def test_verification_evidence_validation() -> None:
    data = valid_verification_evidence().model_dump()
    data["commands"][0]["command_index"] = 1
    with pytest.raises((ValidationError, OrchestratorError), match="index order"):
        VerificationEvidence.model_validate(data)

    data = valid_verification_evidence().model_dump()
    data["commands"] = []
    data["setup_error"] = "SETUP_FAILED: synthetic"
    with pytest.raises(
        (ValidationError, OrchestratorError), match="Setup error cannot be reported"
    ):
        VerificationEvidence.model_validate(data)

    data = valid_verification_evidence().model_dump()
    data["commands"][0]["exit_code"] = 1
    with pytest.raises(
        (ValidationError, OrchestratorError), match="Failed command cannot be reported"
    ):
        VerificationEvidence.model_validate(data)

    data = valid_verification_evidence().model_dump()
    data["failed"] = True
    with pytest.raises((ValidationError, OrchestratorError), match="both passed and failed"):
        VerificationEvidence.model_validate(data)


def test_evidence_artifact_ref_validation() -> None:
    sha = "a" * 64
    # Safe path checked
    with pytest.raises((ValidationError, OrchestratorError), match="Unsafe"):
        EvidenceArtifactRef(
            name="bad",
            path="../outside.json",
            digest=sha,
            byte_size=10,
            classification="test",
        )

    with pytest.raises(ValidationError):
        EvidenceArtifactRef(
            name="bad",
            path="valid.json",
            digest=sha,
            byte_size=-1,
            classification="test",
        )


def test_evidence_bundle_completeness_and_mismatches() -> None:
    bundle = valid_evidence_bundle()

    # Base sha mismatch rejected
    data = bundle.model_dump()
    data["provenance"]["base_sha"] = "b" * 64
    with pytest.raises((ValidationError, OrchestratorError), match="base_sha mismatch"):
        EvidenceBundle.model_validate(data)

    # Branch mismatch rejected
    data = bundle.model_dump()
    data["provenance"]["branch"] = "wrong-branch"
    with pytest.raises((ValidationError, OrchestratorError), match="branch mismatch"):
        EvidenceBundle.model_validate(data)

    # Source digest mismatch rejected
    data = bundle.model_dump()
    data["provenance"]["source_digest"] = "b" * 64
    with pytest.raises((ValidationError, OrchestratorError), match="source_digest mismatch"):
        EvidenceBundle.model_validate(data)

    # Scope changed paths mismatch provenance rejected
    data = bundle.model_dump()
    data["scope"]["actual_changed_paths"] = ["different.py"]
    data["scope"]["allowed_paths"] = ["different.py"]
    with pytest.raises((ValidationError, OrchestratorError), match="mismatch provenance"):
        EvidenceBundle.model_validate(data)

    # Unexpected changed paths in complete bundle rejected
    data = bundle.model_dump()
    data["scope"]["allowed_paths"] = ["other.py"]
    data["scope"]["actual_changed_paths"] = ["tasks/t088-deterministic-evidence-bundle.md"]
    data["scope"]["unexpected_changed_paths"] = ["tasks/t088-deterministic-evidence-bundle.md"]
    data["scope"]["verdict"] = "FAIL"
    with pytest.raises((ValidationError, OrchestratorError), match="cannot have unexpected"):
        EvidenceBundle.model_validate(data)

    # Missing verification commands in complete bundle rejected
    data = bundle.model_dump()
    data["verification"]["commands"] = []
    data["verification"]["passed"] = False
    data["verification"]["failed"] = False
    with pytest.raises((ValidationError, OrchestratorError), match="Successful prefix"):
        EvidenceBundle.model_validate(data)

    # Setup error in complete bundle rejected
    data = bundle.model_dump()
    data["verification"]["setup_error"] = "SETUP_FAILED: test"
    data["verification"]["passed"] = False
    data["verification"]["failed"] = True
    with pytest.raises((ValidationError, OrchestratorError), match="cannot have setup error"):
        EvidenceBundle.model_validate(data)

    # Duplicate artifact references rejected
    art = data["artifacts"][0]
    data["artifacts"] = [art, art]
    with pytest.raises((ValidationError, OrchestratorError), match="Duplicate artifact references"):
        EvidenceBundle.model_validate(data)

    # Semantic payload excludes timing
    payload = bundle.semantic_payload()
    assert "timing" not in payload
    assert payload["schema_version"] == 1
    assert payload["task_id"] == "T088"

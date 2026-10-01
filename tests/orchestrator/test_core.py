import json
import multiprocessing
import sys
from contextlib import suppress
from multiprocessing.connection import Connection as PipeConnection
from pathlib import Path

import pytest
from pydantic import ValidationError
from tools.orchestrator.core import (
    Audit,
    Contract,
    Criterion,
    Fix,
    OrchestratorError,
    Plan,
    Role,
    RunState,
    State,
    atomic_json,
    read_json,
    safe_path,
    transition,
)
from tools.orchestrator.runtime import CliProvider, Git, LockBusy, execute, lock, slot


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
          '--prompt --output-format --approval-mode --skip-trust')
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

    def capture(
        command: list[str], cwd: Path, *, timeout: int = 1800, stdin: str | None = None
    ) -> runtime.ProcessResult:
        commands.append(command)
        return original(command, cwd, timeout=timeout, stdin=stdin)

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

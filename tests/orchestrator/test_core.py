import json
import multiprocessing
import subprocess
import sys
from contextlib import suppress
from multiprocessing.connection import Connection as PipeConnection
from pathlib import Path

import pytest
from pydantic import ValidationError
from tools.orchestrator.core import (
    Audit,
    Config,
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
        command: list[str], cwd: Path, *, timeout: int | None = None, stdin: str | None = None
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

    def capture(
        command: list[str], cwd: Path, *, timeout: int | None = None, stdin: str | None = None
    ) -> runtime.ProcessResult:
        commands.append(command)
        return original(command, cwd, timeout=timeout, stdin=stdin)

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

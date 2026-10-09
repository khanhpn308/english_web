import os
import sys
import time
from pathlib import Path

import pytest
from tools.orchestrator.core import (
    AgentStallError,
    Fix,
    Role,
    read_json,
)
from tools.orchestrator.runtime import (
    CliProvider,
    Git,
    execute,
)


def test_runtime_timeout_none_does_not_create_wall_clock_deadline(tmp_path: Path) -> None:
    cmd = [sys.executable, "-c", "import time; time.sleep(0.1); print('done')"]
    result = execute(cmd, tmp_path, timeout=None)
    assert result.exit_code == 0
    assert result.timed_out is False
    assert result.stalled is False
    assert result.oversized is False
    assert "done" in result.stdout


def test_runtime_watchdog_disabled_retains_historical_behavior(tmp_path: Path) -> None:
    cmd = [sys.executable, "-c", "import time; time.sleep(0.3); print('done')"]
    result = execute(cmd, tmp_path, timeout=10, stall_timeout=None)
    assert result.exit_code == 0
    assert result.timed_out is False
    assert result.stalled is False
    assert "done" in result.stdout


def test_runtime_silent_subprocess_triggers_confirmed_stall(tmp_path: Path) -> None:
    cmd = [sys.executable, "-c", "import time; time.sleep(10)"]
    start = time.monotonic()
    result = execute(
        cmd,
        tmp_path,
        timeout=10,
        stall_timeout=0.15,
        stall_confirm=0.15,
    )
    elapsed = time.monotonic() - start
    assert elapsed < 5.0
    assert result.stalled is True
    assert result.timed_out is False
    assert result.oversized is False
    meta = result.metadata()
    assert meta["stalled"] is True
    assert meta["timed_out"] is False
    assert meta["oversized"] is False


def test_runtime_progressing_subprocess_resets_liveness(tmp_path: Path) -> None:
    # Emits output every 0.1s for 4 iterations (0.4s total).
    # stall_timeout is 0.2s, so progress resets the timer before stall can trigger.
    script = (
        "import time, sys\n"
        "for i in range(4):\n"
        "    time.sleep(0.1)\n"
        "    print(f'tick {i}', flush=True)\n"
    )
    cmd = [sys.executable, "-c", script]
    result = execute(
        cmd,
        tmp_path,
        timeout=5,
        stall_timeout=0.25,
        stall_confirm=0.2,
    )
    assert result.exit_code == 0
    assert result.stalled is False
    assert result.timed_out is False
    assert "tick 3" in result.stdout


def test_runtime_suspected_stall_recovers_during_confirmation(tmp_path: Path) -> None:
    # Stalls for 0.2s (triggering suspected stall at 0.15s), but emits progress
    # before confirmation window (0.2s) expires at 0.35s.
    script = "import time, sys\ntime.sleep(0.2)\nprint('recovered', flush=True)\ntime.sleep(0.05)\n"
    cmd = [sys.executable, "-c", script]
    result = execute(
        cmd,
        tmp_path,
        timeout=5,
        stall_timeout=0.15,
        stall_confirm=0.25,
    )
    assert result.exit_code == 0
    assert result.stalled is False
    assert "recovered" in result.stdout


def test_runtime_process_tree_termination_no_orphans(tmp_path: Path) -> None:
    # Launch a parent process that spawns a long-lived child process, then sleeps.
    # When confirmed stall triggers, both parent and child must be reaped.
    pid_file = tmp_path / "child.pid"
    script = (
        "import subprocess, sys, time\n"
        "proc = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\n"
        f"open(r'{pid_file}', 'w').write(str(proc.pid))\n"
        "time.sleep(30)\n"
    )
    cmd = [sys.executable, "-c", script]
    result = execute(
        cmd,
        tmp_path,
        timeout=10,
        stall_timeout=0.2,
        stall_confirm=0.2,
    )
    assert result.stalled is True
    assert pid_file.is_file()
    child_pid = int(pid_file.read_text().strip())

    # Verify child process was terminated
    if os.name == "posix":
        time.sleep(0.1)
        try:
            os.kill(child_pid, 0)
            child_alive = True
        except OSError:
            child_alive = False
        assert child_alive is False, f"Child process {child_pid} was orphaned"


def test_runtime_process_result_diagnostics_distinction(tmp_path: Path) -> None:
    # 1. Normal
    normal_res = execute([sys.executable, "-c", "print('ok')"], tmp_path)
    assert normal_res.exit_code == 0
    assert normal_res.timed_out is False
    assert normal_res.oversized is False
    assert normal_res.stalled is False
    assert normal_res.metadata()["stalled"] is False

    # 2. Total timeout
    timeout_res = execute(
        [sys.executable, "-c", "import time; time.sleep(10)"],
        tmp_path,
        timeout=0.1,
    )
    assert timeout_res.timed_out is True
    assert timeout_res.stalled is False
    assert timeout_res.oversized is False
    assert timeout_res.metadata()["timed_out"] is True
    assert timeout_res.metadata()["stalled"] is False

    # 3. Confirmed stall
    stall_res = execute(
        [sys.executable, "-c", "import time; time.sleep(10)"],
        tmp_path,
        stall_timeout=0.1,
        stall_confirm=0.1,
    )
    assert stall_res.stalled is True
    assert stall_res.timed_out is False
    assert stall_res.oversized is False
    assert stall_res.metadata()["stalled"] is True
    assert stall_res.metadata()["timed_out"] is False


def test_runtime_cliprovider_stalled_raises_agent_stall_error(tmp_path: Path) -> None:
    fake_cli = tmp_path / "fake_cli"
    fake_cli.write_text(f"""#!{sys.executable}
import sys, time
args = sys.argv[1:]
if '--version' in args:
    print('1.0.0')
elif '--help' in args:
    print(
        '--input-format --output-format --json-schema --mode --model --effort '
        '--disable-slash-commands'
    )
else:
    time.sleep(10)
""")
    fake_cli.chmod(0o700)
    role = Role(
        provider="agy",
        executable=str(fake_cli),
        model="synthetic-test",
        reasoning=None,
        worker_access="workspace-write",
        allow_process=False,
        stall_timeout_seconds=1,
        stall_confirm_seconds=1,
        max_stall_retries=1,
    )
    provider = CliProvider()
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()

    with pytest.raises(AgentStallError) as exc_info:
        provider.run(
            "test prompt",
            cwd=tmp_path,
            role=role,
            timeout=10,
            output=Fix,
            artifacts=artifacts,
            name="00-test-stall",
            readonly=True,
        )
    assert "Agent process stalled" in str(exc_info.value)

    # Check log was written and has stalled status
    log_file = artifacts / "00-test-stall.log.json"
    assert log_file.is_file()
    log_data = read_json(log_file)
    assert isinstance(log_data, dict)
    execution = log_data.get("execution")
    assert isinstance(execution, dict)
    assert execution["stalled"] is True
    assert execution["timed_out"] is False


def test_t090_secure_provider_denies_unattested_readonly_cli(
    tmp_path: Path,
) -> None:
    from tools.orchestrator.core import Fix, OrchestratorError, Plan, ReviewShard
    from tools.orchestrator.runtime import SecureProvider

    role = Role(provider="codex", executable=str(tmp_path / "not-installed-cli"))
    provider = SecureProvider()
    for response_type in (Plan, ReviewShard, Fix):
        with pytest.raises(OrchestratorError, match="T090 BLOCKED"):
            provider.run(
                "Synthetic evidence only",
                cwd=tmp_path,
                role=role,
                timeout=1,
                output=response_type,
                artifacts=tmp_path,
                name="readonly-no-cli",
                readonly=True,
            )
    assert not (tmp_path / "not-installed-cli").exists()


def test_t090_secure_provider_calls_only_tool_free_transport(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools.orchestrator.core import Fix
    from tools.orchestrator.runtime import SecureProvider
    from tools.orchestrator.worker_sandbox import LoopbackChatTransport

    monkeypatch.setenv("T090_TEST_ONLY_KEY", "synthetic")
    role = Role(
        provider="agy",
        executable=str(tmp_path / "not-installed-agy"),
        model="gemini-3.8-flash-high",
        analysis_backend="host-http-text",
        host_text_endpoint="http://127.0.0.1:8045/v1/chat/completions",
        host_text_api_key_env="T090_TEST_ONLY_KEY",
    )
    calls: list[str] = []

    def complete(
        _self: LoopbackChatTransport, prompt: str, *, model: str, timeout: int | None
    ) -> str:
        assert _self.response_contract == "semantic-json"
        calls.append(prompt)
        assert model == role.model
        assert timeout == 7
        return '{"fix_prompt":"Apply the minimal scoped correction."}'

    monkeypatch.setattr(LoopbackChatTransport, "complete", complete)
    result = SecureProvider().run(
        "Host-owned evidence payload",
        cwd=tmp_path,
        role=role,
        timeout=7,
        output=Fix,
        artifacts=tmp_path,
        name="readonly-http",
        readonly=True,
    )
    assert result.fix_prompt == "Apply the minimal scoped correction."
    assert calls == ["Host-owned evidence payload"]
    assert not (tmp_path / "not-installed-agy").exists()


def test_t090_secure_provider_rejects_invalid_semantic_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools.orchestrator.core import Fix, OrchestratorError
    from tools.orchestrator.runtime import SecureProvider
    from tools.orchestrator.worker_sandbox import LoopbackChatTransport

    role = Role(
        provider="agy",
        executable="not-used",
        model="gemini-3.8-flash-high",
        analysis_backend="host-http-text",
        host_text_endpoint="http://127.0.0.1:8045/v1/chat/completions",
        host_text_api_key_env="T090_TEST_KEY",
    )

    def malformed(
        _self: LoopbackChatTransport, _prompt: str, *, model: str, timeout: int | None
    ) -> str:
        assert model == "gemini-3.8-flash-high"
        assert timeout == 1
        return '{"commands_run":[["sh","-c","touch bad"]]}'

    monkeypatch.setattr(LoopbackChatTransport, "complete", malformed)
    with pytest.raises(OrchestratorError, match="schema invalid"):
        SecureProvider().run(
            "untrusted test",
            cwd=tmp_path,
            role=role,
            timeout=1,
            output=Fix,
            artifacts=tmp_path,
            name="invalid-output",
            readonly=True,
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"analysis_backend": "cli"},
        {"allow_process": True},
        {"worker_access": "full-access"},
        {"provider": "gemini"},
    ],
)
def test_t090_semantic_provider_fails_closed_on_unsafe_role(
    tmp_path: Path, changes: dict[str, object]
) -> None:
    from tools.orchestrator.core import Fix, OrchestratorError
    from tools.orchestrator.runtime import SecureProvider

    role = Role(
        provider="agy",
        executable="not-used",
        model="gemini-3.8-flash-high",
        analysis_backend="host-http-text",
        host_text_endpoint="http://127.0.0.1:8045/v1/chat/completions",
        host_text_api_key_env="T090_TEST_KEY",
    ).model_copy(update=changes)
    with pytest.raises(OrchestratorError, match="T090 BLOCKED"):
        SecureProvider().run(
            "untrusted test",
            cwd=tmp_path,
            role=role,
            timeout=1,
            output=Fix,
            artifacts=tmp_path,
            name="unsafe-role",
            readonly=True,
        )


def test_t090_secure_provider_rejects_mutable_cli_for_any_schema(
    tmp_path: Path,
) -> None:
    from tools.orchestrator.core import Fix, OrchestratorError
    from tools.orchestrator.runtime import SecureProvider

    with pytest.raises(OrchestratorError, match="mutable CLI execution is forbidden"):
        SecureProvider().run(
            "Do not run shell",
            cwd=tmp_path,
            role=Role(provider="codex", executable=str(tmp_path / "shell-capable")),
            timeout=1,
            output=Fix,
            artifacts=tmp_path,
            name="mutable-invalid-schema",
            readonly=False,
        )
    assert not (tmp_path / "shell-capable").exists()


def test_t090_changed_path_allowlist_must_include_both_rename_ends(
    tmp_path: Path,
) -> None:
    git = Git(tmp_path)
    git.run("init", "-b", "main")
    git.run("config", "user.email", "fixture@example.invalid")
    git.run("config", "user.name", "Fixture")
    (tmp_path / "original.py").write_text("VALUE = 1\n")
    git.run("add", "original.py")
    git.run("commit", "-m", "base")
    base = git.sha()
    git.run("mv", "original.py", "renamed.py")
    assert git.paths(base) == ["original.py", "renamed.py"]
    assert not (tmp_path / "original.py").exists()
    assert (tmp_path / "renamed.py").read_text() == "VALUE = 1\n"


@pytest.mark.parametrize("invalid", ["cwd", "artifacts", "name"])
def test_t090_secure_provider_rejects_invalid_host_context(tmp_path: Path, invalid: str) -> None:
    from tools.orchestrator.core import Fix, OrchestratorError
    from tools.orchestrator.runtime import SecureProvider

    missing = tmp_path / "not-created"
    with pytest.raises(OrchestratorError, match="invalid host-owned semantic context"):
        SecureProvider().run(
            "Synthetic",
            cwd=missing if invalid == "cwd" else tmp_path,
            role=Role(provider="codex", executable="nonexistent"),
            timeout=1,
            output=Fix,
            artifacts=missing if invalid == "artifacts" else tmp_path,
            name="" if invalid == "name" else "test",
            readonly=True,
        )

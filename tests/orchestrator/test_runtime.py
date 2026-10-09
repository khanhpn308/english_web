import os
import subprocess
import sys
import time
from collections.abc import Sequence
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


def test_t090_docker_sandbox_rejects_unpinned_image_and_bad_limits(tmp_path: Path) -> None:
    from tools.orchestrator.core import OrchestratorError
    from tools.orchestrator.runtime import DockerVerificationPolicy

    valid = "docker.io/verified/t090@sha256:" + "a" * 64
    for image in (
        "python:3.12-slim",
        "docker.io/python@sha256:" + "z" * 64,
        "python:3.12; rm -rf /",
    ):
        with pytest.raises(OrchestratorError, match="pinned sha256"):
            DockerVerificationPolicy(image, tmp_path)
    for field, value in (
        ("memory_mib", 1),
        ("cpu_millicores", 0),
        ("pids_limit", 1000),
        ("timeout_seconds", 0),
        ("workspace_tmpfs_mib", 1),
    ):
        with pytest.raises(OrchestratorError, match="SANDBOX_BLOCKED"):
            DockerVerificationPolicy(valid, tmp_path, **{field: value})


def test_t090_docker_sandbox_host_constructs_fixed_arguments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools.orchestrator.runtime import (
        DockerVerificationPolicy,
        DockerVerificationSandbox,
        ProcessResult,
    )

    root = tmp_path / "runs"
    working = root / "verify-t090-abc" / "workspace"
    working.mkdir(parents=True)
    (working / "sample.py").write_text("print('synthetic')\n")
    policy = DockerVerificationPolicy(
        "docker.io/verified/t090@sha256:" + "a" * 64,
        root,
        timeout_seconds=45,
    )
    seen: list[list[str]] = []

    def fake_execute(
        command: list[str], cwd: Path, *, timeout: int | float | None = None
    ) -> ProcessResult:
        assert cwd != working
        assert cwd.name == "workspace"
        assert cwd.parent.name.startswith("verify-sealed-")
        assert (cwd / "sample.py").read_text() == "print('synthetic')\n"
        assert command[:6] == [
            "/usr/bin/env",
            "-i",
            "PATH=/usr/bin:/bin",
            "HOME=/tmp",
            "DOCKER_HOST=unix:///var/run/docker.sock",
            "/usr/bin/docker",
        ]
        assert "--config" in command
        seen.append(command)
        if "inspect" in command:
            assert timeout == 20
            return ProcessResult(
                tuple(command),
                str(cwd),
                "start",
                "end",
                0,
                "sha256:" + "b" * 64 + "\n",
                "",
            )
        if "run" in command:
            assert timeout == 45
            for flag in (
                "--pull=never",
                "--network=none",
                "--read-only",
                "--entrypoint=/usr/local/bin/python3",
                "--cap-drop=ALL",
                "--security-opt=no-new-privileges",
                "--pids-limit",
                "--memory",
                "--memory-swap",
                "--cpus",
                "--user",
                "--workdir=/workspace",
                "--env=T090_SANDBOX_LIMITED=1",
            ):
                assert flag in command
            assert command[-7:-5] == ["-I", "-c"]
            assert command[-4] == expected_digest
            assert command[-3:] == ["python", "-m", "pytest"]
            assert "for entry in os.scandir('/source')" in command[-5]
            assert "shutil.copytree(src, dst, symlinks=True)" in command[-5]
            assert "source attestation mismatch" in command[-5]
            assert "os.execvp(sys.argv[2], sys.argv[2:])" in command[-5]
            mount = command[command.index("--mount") + 1]
            assert str(working) not in mount
            assert str(cwd) in mount
            assert "dst=/source,readonly" in mount
            assert (
                f"--tmpfs=/workspace:rw,nosuid,nodev,size=256m,mode=0700,uid=1000,gid={os.getegid()}"
                in command
            )
            assert "--ulimit=core=0:0" in command
            assert str(tmp_path / "secret") not in " ".join(command)
            return ProcessResult(tuple(command), str(cwd), "start", "end", 0, "PASS", "")
        assert "rm" in command
        assert timeout == 20
        return ProcessResult(tuple(command), str(cwd), "start", "end", 0, "", "")

    monkeypatch.setattr("tools.orchestrator.runtime.execute", fake_execute)
    monkeypatch.setattr("tools.orchestrator.runtime.os.geteuid", lambda: 1000)
    broker = DockerVerificationSandbox(policy)
    expected_digest = broker.source_digest(working)
    result = broker.run(["python", "-m", "pytest"], working, expected_source_digest=expected_digest)
    assert result.exit_code == 0
    assert len(seen) == 3
    assert seen[1][seen[1].index("--name") + 1] == seen[2][-1]


@pytest.mark.parametrize("mode", ["outside", "symlink", "special", "root"])
def test_t090_docker_sandbox_denies_invalid_workspace_before_docker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    from tools.orchestrator.core import OrchestratorError
    from tools.orchestrator.runtime import DockerVerificationPolicy, DockerVerificationSandbox

    root = tmp_path / "verification"
    workspace = root / "verify-t090-abc" / "workspace"
    workspace.mkdir(parents=True)
    if mode == "outside":
        workspace = tmp_path / "other" / "workspace"
        workspace.mkdir(parents=True)
    elif mode == "symlink":
        (workspace / "bad").symlink_to(tmp_path)
    elif mode == "special":
        os.mkfifo(workspace / "control.pipe")
    else:
        monkeypatch.setattr("tools.orchestrator.runtime.os.geteuid", lambda: 0)

    policy = DockerVerificationPolicy("example.com/t090@sha256:" + "b" * 64, root)

    def forbidden_execute(*args: object, **kwargs: object) -> None:
        raise AssertionError("Docker must not run for invalid workspaces")

    monkeypatch.setattr("tools.orchestrator.runtime.execute", forbidden_execute)
    with pytest.raises(OrchestratorError, match="SANDBOX_BLOCKED"):
        DockerVerificationSandbox(policy).run(
            ["python", "-m", "pytest"], workspace, expected_source_digest="a" * 64
        )


def test_t090_docker_sandbox_blocks_missing_pinned_image(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools.orchestrator.core import OrchestratorError
    from tools.orchestrator.runtime import (
        DockerVerificationPolicy,
        DockerVerificationSandbox,
        ProcessResult,
    )

    root = tmp_path / "verification"
    workspace = root / "verify-t090" / "workspace"
    workspace.mkdir(parents=True)
    monkeypatch.setattr("tools.orchestrator.runtime.os.geteuid", lambda: 1000)
    seen: list[list[str]] = []

    def fail_inspect(
        argv: list[str], cwd: Path, *, timeout: int | float | None = None
    ) -> ProcessResult:
        seen.append(argv)
        return ProcessResult(tuple(argv), str(cwd), "start", "end", 1, "", "image missing")

    monkeypatch.setattr("tools.orchestrator.runtime.execute", fail_inspect)
    policy = DockerVerificationPolicy("example.com/t090@sha256:" + "1" * 64, root)
    with pytest.raises(OrchestratorError, match="pinned local image unavailable"):
        broker = DockerVerificationSandbox(policy)
        broker.run(
            ["python", "-m", "pytest"],
            workspace,
            expected_source_digest=broker.source_digest(workspace),
        )
    assert len(seen) == 1
    assert "inspect" in seen[0]


@pytest.mark.parametrize(
    "command",
    [
        ["bash", "-c", "echo malicious"],
        ["python", "-c", "print('malicious')"],
        ["git", "status"],
        ["npm", "ci"],
    ],
)
def test_t090_docker_sandbox_rejects_unapproved_command_before_host_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, command: list[str]
) -> None:
    from tools.orchestrator.core import OrchestratorError
    from tools.orchestrator.runtime import DockerVerificationPolicy, DockerVerificationSandbox

    root = tmp_path / "verification"
    workspace = root / "verify-t090" / "workspace"
    workspace.mkdir(parents=True)
    monkeypatch.setattr("tools.orchestrator.runtime.os.geteuid", lambda: 1000)

    def no_host_command(*args: object, **kwargs: object) -> None:
        raise AssertionError("Unapproved command reached host execution")

    monkeypatch.setattr("tools.orchestrator.runtime.execute", no_host_command)
    policy = DockerVerificationPolicy("example.com/t090@sha256:" + "a" * 64, root)
    with pytest.raises(OrchestratorError):
        DockerVerificationSandbox(policy).run(command, workspace)


def test_t090_osv_offline_gate_is_opt_in_and_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts import security_checks

    (tmp_path / "package-lock.json").write_text("{}")
    (tmp_path / "requirements.lock").write_text("fixture==1.0\n")
    (tmp_path / "requirements-dev.lock").write_text("fixture==1.0\n")
    calls: list[list[str]] = []

    def synthetic_scan(argv: Sequence[str], _cwd: Path) -> subprocess.CompletedProcess[str]:
        calls.append(list(argv))
        if "--version" in argv:
            return subprocess.CompletedProcess(list(argv), 0, "osv-scanner version: 2.6.0\n", "")
        return subprocess.CompletedProcess(list(argv), 0, '{"results":[]}', "")

    monkeypatch.setenv("T090_OSV_OFFLINE", "1")
    result = security_checks.run_dependencies(
        tmp_path, tmp_path / "reports-offline", runner=synthetic_scan
    )
    assert result.exit_code == security_checks.EXIT_CLEAN
    assert calls[1][1:4] == ["--offline", "scan", "source"]

    monkeypatch.delenv("T090_OSV_OFFLINE")
    calls.clear()
    security_checks.run_dependencies(tmp_path, tmp_path / "reports-online", runner=synthetic_scan)
    assert "--offline" not in calls[1]


def test_t090_missing_source_digest_blocks_without_any_docker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools.orchestrator.core import OrchestratorError
    from tools.orchestrator.runtime import DockerVerificationPolicy, DockerVerificationSandbox

    root = tmp_path / "test-root"
    workspace = root / "verify-fixture" / "workspace"
    workspace.mkdir(parents=True)
    (workspace / "case.txt").write_text("frozen")

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Docker must not be contacted")

    monkeypatch.setattr("tools.orchestrator.runtime.execute", forbidden)
    broker = DockerVerificationSandbox(
        DockerVerificationPolicy("example.com/image@sha256:" + "a" * 64, root)
    )
    with pytest.raises(OrchestratorError, match="trusted source digest required"):
        broker.run(["python", "-m", "pytest"], workspace)


def test_t090_stale_or_modified_candidate_rejected_before_docker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools.orchestrator.core import OrchestratorError
    from tools.orchestrator.runtime import DockerVerificationPolicy, DockerVerificationSandbox

    root = tmp_path / "test-root"
    workspace = root / "verify-fixture" / "workspace"
    workspace.mkdir(parents=True)
    (workspace / "case.txt").write_text("frozen")
    broker = DockerVerificationSandbox(
        DockerVerificationPolicy("example.com/image@sha256:" + "a" * 64, root)
    )
    expected = broker.source_digest(workspace)
    (workspace / "case.txt").write_text("tampered")

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Docker must not be contacted")

    monkeypatch.setattr("tools.orchestrator.runtime.execute", forbidden)
    with pytest.raises(OrchestratorError, match="source attestation mismatch"):
        broker.run(["python", "-m", "pytest"], workspace, expected_source_digest=expected)


def test_t090_source_modified_during_sealing_is_blocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools.orchestrator.core import OrchestratorError
    from tools.orchestrator.runtime import DockerVerificationPolicy, DockerVerificationSandbox
    from tools.orchestrator import runtime

    root = tmp_path / "test-root"
    workspace = root / "verify-fixture" / "workspace"
    workspace.mkdir(parents=True)
    (workspace / "case.txt").write_text("frozen")
    broker = DockerVerificationSandbox(
        DockerVerificationPolicy("example.com/image@sha256:" + "a" * 64, root)
    )
    expected = broker.source_digest(workspace)
    original_copytree = runtime.shutil.copytree

    def malicious_copy(src: Path, dst: Path, *, symlinks: bool = False) -> Path:
        result = original_copytree(src, dst, symlinks=symlinks)
        (dst / "case.txt").write_text("modified during seal")
        return result

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Docker must not be contacted")

    monkeypatch.setattr("tools.orchestrator.runtime.shutil.copytree", malicious_copy)
    monkeypatch.setattr("tools.orchestrator.runtime.execute", forbidden)
    with pytest.raises(OrchestratorError, match="source attestation mismatch"):
        broker.run(["python", "-m", "pytest"], workspace, expected_source_digest=expected)


def test_t090_sealed_source_changed_during_image_inspection_is_blocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools.orchestrator.core import OrchestratorError
    from tools.orchestrator.runtime import (
        DockerVerificationPolicy,
        DockerVerificationSandbox,
        ProcessResult,
    )

    root = tmp_path / "test-root"
    workspace = root / "verify-fixture" / "workspace"
    workspace.mkdir(parents=True)
    (workspace / "case.txt").write_text("frozen")
    broker = DockerVerificationSandbox(
        DockerVerificationPolicy("example.com/image@sha256:" + "a" * 64, root)
    )
    expected = broker.source_digest(workspace)
    operations: list[str] = []

    def modify_at_inspect(
        argv: list[str], cwd: Path, *, timeout: int | float | None = None
    ) -> ProcessResult:
        assert "inspect" in argv
        operations.append("inspect")
        (cwd / "case.txt").write_text("modified during Docker inspect")
        return ProcessResult(tuple(argv), str(cwd), "start", "end", 0, "sha256:" + "b" * 64, "")

    monkeypatch.setattr("tools.orchestrator.runtime.execute", modify_at_inspect)
    with pytest.raises(OrchestratorError, match="source attestation mismatch"):
        broker.run(["python", "-m", "pytest"], workspace, expected_source_digest=expected)
    assert operations == ["inspect"]
    assert (workspace / "case.txt").read_text() == "frozen"


def test_t090_tree_digest_is_independent_of_creation_and_walk_order(
    tmp_path: Path,
) -> None:
    from tools.orchestrator.runtime import DockerVerificationPolicy, DockerVerificationSandbox

    root = tmp_path / "frozen"
    workspaces = []
    for number, order in enumerate((("zebra", "alpha"), ("alpha", "zebra"))):
        workspace = root / f"verify-order-{number}" / "workspace"
        workspace.mkdir(parents=True)
        for folder in order:
            directory = workspace / folder
            directory.mkdir()
            (directory / "module.py").write_text("SYNTHETIC = True\n")
            (directory / "empty").mkdir()
        # In-tree symlink references must have stable relative targets.
        (workspace / "link").symlink_to("alpha/module.py")
        workspaces.append(workspace)

    broker = DockerVerificationSandbox(
        DockerVerificationPolicy("example.org/t090@sha256:" + "a" * 64, root)
    )
    first = broker.source_digest(workspaces[0])
    second = broker.source_digest(workspaces[1])
    assert first == second

    (workspaces[1] / "alpha/module.py").write_text("SYNTHETIC = False\n")
    assert broker.source_digest(workspaces[1]) != first


def test_t090_digest_detects_empty_directories_and_path_renames(tmp_path: Path) -> None:
    from tools.orchestrator.runtime import DockerVerificationPolicy, DockerVerificationSandbox

    root = tmp_path / "frozen"
    workspace = root / "verify-empty" / "workspace"
    workspace.mkdir(parents=True)
    broker = DockerVerificationSandbox(
        DockerVerificationPolicy("example.org/t090@sha256:" + "b" * 64, root)
    )
    baseline = broker.source_digest(workspace)
    (workspace / "empty").mkdir()
    with_empty = broker.source_digest(workspace)
    assert baseline != with_empty
    (workspace / "empty").rename(workspace / "renamed")
    assert broker.source_digest(workspace) != with_empty


def test_t090_image_admission_rejects_unapproved_repo_policy(tmp_path: Path) -> None:
    import hashlib
    import json

    from tools.orchestrator.core import OrchestratorError
    from tools.orchestrator.runtime import admit_verification_image

    repo = tmp_path / "repo"
    repo.mkdir()
    policy = tmp_path / "trusted-approval.json"
    policy.write_text(json.dumps({"schema_version": 1, "approved": False}))
    pinned = hashlib.sha256(policy.read_bytes()).hexdigest()

    with pytest.raises(OrchestratorError, match="trusted image admission unavailable"):
        admit_verification_image(
            policy, expected_policy_sha256=pinned, authoritative_repository=repo
        )
    with pytest.raises(OrchestratorError, match="trusted image admission unavailable"):
        admit_verification_image(
            policy, expected_policy_sha256="f" * 64, authoritative_repository=repo
        )
    with pytest.raises(OrchestratorError, match="trusted image admission unavailable"):
        admit_verification_image(
            policy, expected_policy_sha256=pinned, authoritative_repository=tmp_path
        )


def test_t090_image_admission_requires_complete_host_pinned_policy(tmp_path: Path) -> None:
    import hashlib
    import json

    from tools.orchestrator.core import OrchestratorError
    from tools.orchestrator.runtime import admit_verification_image

    repo = tmp_path / "repo"
    repo.mkdir()
    for name in ("requirements-dev.lock", "package-lock.json"):
        (repo / name).write_text(name)
    lock_hashes = {
        name: hashlib.sha256((repo / name).read_bytes()).hexdigest()
        for name in ("requirements-dev.lock", "package-lock.json")
    }
    image = "registry.invalid/verifier@sha256:" + "a" * 64
    valid = {
        "schema_version": 1,
        "approved": True,
        "image_reference": image,
        "verified_image_manifest_digest": "sha256:" + "a" * 64,
        "base_images": {
            "python": "registry.invalid/python@sha256:" + "b" * 64,
            "node": "registry.invalid/node@sha256:" + "c" * 64,
        },
        "locked_inputs_sha256": lock_hashes,
        "offline_osv_db_sha256": {"npm": "d" * 64, "PyPI": "e" * 64},
        "build_provenance_ref": "sha256:" + "f" * 64,
        "sbom_ref": "sha256:" + "0" * 64,
    }
    policy = tmp_path / "external-approval.json"

    def check_policy(value: dict[str, object], accepted: bool) -> None:
        policy.write_text(json.dumps(value, sort_keys=True))
        pin = hashlib.sha256(policy.read_bytes()).hexdigest()
        if accepted:
            admitted = admit_verification_image(
                policy, expected_policy_sha256=pin, authoritative_repository=repo
            )
            assert admitted.image == image
            assert admitted.policy_sha256 == pin
        else:
            with pytest.raises(OrchestratorError, match="trusted image admission unavailable"):
                admit_verification_image(
                    policy, expected_policy_sha256=pin, authoritative_repository=repo
                )

    check_policy(valid, True)
    for name, bad_value in (
        ("build_provenance_ref", None),
        ("sbom_ref", "unverified"),
        ("verified_image_manifest_digest", "sha256:" + "f" * 64),
        ("base_images", {"python": "python:latest"}),
        ("locked_inputs_sha256", {"package-lock.json": "0" * 64}),
        ("offline_osv_db_sha256", {"npm": "f" * 64}),
    ):
        check_policy({**valid, name: bad_value}, False)
    (repo / "package-lock.json").write_text("changed")
    check_policy(valid, False)

"""Processes with opt-in deadlines, local locks, Git and replaceable CLI providers."""

import importlib
import json
import os
import signal
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from pathlib import Path
from time import monotonic, sleep
from typing import BinaryIO, Protocol, TypeVar, cast

from pydantic import BaseModel
from tools.orchestrator.core import (
    AgentStallError,
    OrchestratorError,
    Role,
    WorkerResult,
    atomic_json,
    digest,
    now,
    safe_path,
)

OUTPUT_LIMIT = 4 * 1024 * 1024
_HELD_LOCKS: set[int] = set()


@dataclass(frozen=True)
class ProcessResult:
    command: tuple[str, ...]
    cwd: str
    started_at: str
    ended_at: str
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False
    oversized: bool = False
    stalled: bool = False

    def metadata(self) -> dict[str, object]:
        # Raw provider/test text can contain source, prompts or credentials. Keep it in
        # memory only; artifacts preserve exit evidence and digests rather than bodies.
        return {
            "command": [Path(self.command[0]).name, "<arguments withheld>"],
            "cwd": self.cwd,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "exit_code": self.exit_code,
            "timed_out": self.timed_out,
            "oversized": self.oversized,
            "stalled": self.stalled,
            "stdout_bytes": len(self.stdout.encode()),
            "stderr_bytes": len(self.stderr.encode()),
            "stdout_digest": digest(self.stdout.encode()),
            "stderr_digest": digest(self.stderr.encode()),
        }


class _StallExpired(Exception):
    def __init__(self, command: list[str], timeout: int | float | None) -> None:
        super().__init__(f"Process stalled: {command[0]}")
        self.command = command
        self.timeout = timeout


def _terminate_process_tree(process: subprocess.Popen[bytes], cwd: Path) -> None:
    with suppress(ProcessLookupError, OSError):
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            execute(["taskkill", "/PID", str(process.pid), "/T", "/F"], cwd, timeout=10)
            process.kill()
    with suppress(Exception):
        process.communicate()


def execute(
    command: list[str],
    cwd: Path,
    *,
    timeout: int | float | None = None,
    stdin: str | None = None,
    stall_timeout: int | float | None = None,
    stall_confirm: int | float = 30,
    output_limit: int = OUTPUT_LIMIT,
) -> ProcessResult:
    start = now()
    timed_out = False
    excessive = False
    stalled = False
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        try:
            process = subprocess.Popen(
                command,
                cwd=cwd,
                stdin=subprocess.PIPE,
                stdout=out,
                stderr=err,
                start_new_session=os.name == "posix",
                pass_fds=tuple(_HELD_LOCKS) if os.name == "posix" else (),
            )
        except FileNotFoundError as error:
            raise OrchestratorError(f"Executable unavailable: {Path(command[0]).name}") from error
        deadline = monotonic() + timeout if timeout is not None else None
        first = True
        last_progress = monotonic()
        last_bytes = 0
        suspected_at: float | None = None
        try:
            while True:
                now_mono = monotonic()
                remaining = deadline - now_mono if deadline is not None else None
                if timeout is not None and remaining is not None and remaining <= 0:
                    raise subprocess.TimeoutExpired(command, timeout)

                if stall_timeout is not None:
                    current_bytes = os.fstat(out.fileno()).st_size + os.fstat(err.fileno()).st_size
                    if current_bytes > last_bytes:
                        last_bytes = current_bytes
                        last_progress = now_mono
                        suspected_at = None
                    else:
                        silence = now_mono - last_progress
                        if silence >= stall_timeout:
                            if suspected_at is None:
                                suspected_at = now_mono
                            if now_mono - suspected_at >= stall_confirm:
                                raise _StallExpired(command, stall_timeout)

                poll_timeout = 0.05
                if remaining is not None:
                    poll_timeout = min(poll_timeout, max(0.0, remaining))
                if stall_timeout is not None:
                    if suspected_at is None:
                        time_to_stall = max(0.0, stall_timeout - (now_mono - last_progress))
                        poll_timeout = min(poll_timeout, time_to_stall)
                    else:
                        time_to_confirm = max(0.0, stall_confirm - (now_mono - suspected_at))
                        poll_timeout = min(poll_timeout, time_to_confirm)

                try:
                    process.communicate(
                        stdin.encode() if first and stdin is not None else None,
                        timeout=max(0.01, poll_timeout),
                    )
                    break
                except subprocess.TimeoutExpired:
                    first = False
                    if (
                        max(os.fstat(out.fileno()).st_size, os.fstat(err.fileno()).st_size)
                        > output_limit
                    ):
                        excessive = True
                        raise
        except _StallExpired:
            _terminate_process_tree(process, cwd)
            stalled = True
        except (subprocess.TimeoutExpired, KeyboardInterrupt) as error:
            interrupted = isinstance(error, KeyboardInterrupt)
            _terminate_process_tree(process, cwd)
            if interrupted:
                raise KeyboardInterrupt from None
            timed_out = not excessive
        out.seek(0, os.SEEK_END)
        out_size = out.tell()
        err.seek(0, os.SEEK_END)
        err_size = err.tell()
        out.seek(0)
        err.seek(0)
        return ProcessResult(
            tuple(command),
            str(cwd),
            start,
            now(),
            process.returncode,
            out.read(output_limit).decode("utf-8", errors="replace"),
            err.read(output_limit).decode("utf-8", errors="replace"),
            timed_out,
            excessive or out_size > output_limit or err_size > output_limit,
            stalled,
        )


class LockBusy(OrchestratorError):
    """Another live process owns this resource; no operation was attempted."""


class WindowsLocking(Protocol):
    LK_NBLCK: int
    LK_UNLCK: int

    def locking(self, fd: int, mode: int, size: int) -> None: ...


def _lock(stream: BinaryIO) -> None:
    if os.name == "nt":
        msvcrt = cast(WindowsLocking, importlib.import_module("msvcrt"))
        stream.seek(0)
        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


@contextmanager
def lock(path: Path, *, wait_seconds: int = 0) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink():
        raise OrchestratorError("Lock file must not be a symlink")
    with path.open("a+b") as stream:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"\0")
            stream.flush()
        deadline = monotonic() + wait_seconds
        while True:
            try:
                _lock(stream)
                break
            except OSError as error:
                if monotonic() >= deadline:
                    raise LockBusy(f"Resource busy: {path.name}") from error
                sleep(0.05)
        try:
            _HELD_LOCKS.add(stream.fileno())
            yield
        finally:
            _HELD_LOCKS.discard(stream.fileno())
            if os.name == "nt":
                msvcrt = cast(WindowsLocking, importlib.import_module("msvcrt"))
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


@contextmanager
def slot(root: Path) -> Iterator[None]:
    for number in range(3):
        manager = lock(root / f"slot-{number}.lock")
        try:
            manager.__enter__()
        except LockBusy:
            continue
        try:
            yield
        finally:
            manager.__exit__(None, None, None)
        return
    raise LockBusy("Three task runs are already active")


class Git:
    def __init__(self, repository: Path) -> None:
        self.repository = repository

    def run(self, *args: str, preserve_newlines: bool = False) -> str:
        result = execute(["git", *args], self.repository, timeout=60)
        if result.exit_code or result.timed_out or result.oversized:
            raise OrchestratorError(f"Git {args[0]} failed (exit {result.exit_code})")
        return result.stdout if preserve_newlines else result.stdout.strip("\n")

    def sha(self, ref: str = "HEAD") -> str:
        return self.run("rev-parse", "--verify", ref)

    def branch(self) -> str:
        return self.run("branch", "--show-current")

    def clean(self) -> bool:
        return not self.run("status", "--porcelain=v1", "--untracked-files=all")

    def paths(self, base: str) -> list[str]:
        changed = self.run("diff", "--name-only", "-z", base, "--")
        staged = self.run("diff", "--cached", "--name-only", "-z", base, "--")
        untracked = self.run("ls-files", "--others", "--exclude-standard", "-z")
        return sorted({p for p in (changed + "\0" + staged + "\0" + untracked).split("\0") if p})

    def snapshot(self, base: str) -> str:
        parts = [self.sha().encode(), self.run("diff", "--cached", "--binary", base, "--").encode()]
        for relative in self.paths(base):
            safe_path(relative)
            path = self.repository / relative
            if path.is_symlink() or not path.resolve().is_relative_to(self.repository.resolve()):
                raise OrchestratorError("Changed path escapes worktree")
            parts.extend(
                [
                    relative.encode(),
                    str(path.stat().st_mode if path.exists() else 0).encode(),
                    path.read_bytes() if path.is_file() else b"<deleted>",
                ]
            )
        return digest(b"\0".join(parts))

    def create_worktree(self, path: Path, branch: str, base: str) -> None:
        self.run("check-ref-format", "--branch", branch)
        if path.exists() or path.is_symlink():
            raise OrchestratorError("Worktree path already exists")
        branches = self.run("for-each-ref", "--format=%(refname:short)", "refs/heads").splitlines()
        if branch in branches:
            raise OrchestratorError("Worktree branch already exists")
        path.parent.mkdir(parents=True, exist_ok=True)
        self.run("worktree", "add", "-b", branch, str(path), base)

    def assert_worktree(self, path: Path, branch: str) -> None:
        actual = Git(path)
        if (
            actual.branch() != branch
            or Path(actual.run("rev-parse", "--show-toplevel")).resolve() != path.resolve()
        ):
            raise OrchestratorError("Worktree identity mismatch")
        common = Path(self.run("rev-parse", "--git-common-dir"))
        theirs = Path(actual.run("rev-parse", "--git-common-dir"))
        if (self.repository / common).resolve() != (path / theirs).resolve():
            raise OrchestratorError("Worktree belongs to another repository")


Output = TypeVar("Output", bound=BaseModel)


class AgentProvider(Protocol):
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
    ) -> Output: ...


class CliProvider:
    """Capabilities are probed locally before each run; authentication stays in the CLI."""

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
        # T090 fail-closed boundary: a CLI approval flag, prompt, or sandbox
        # setting alone does NOT prove shell/process denial. Until an actual
        # restricted edit-only tool broker is independently attested, never
        # dispatch a mutable Worker through a shell-capable provider CLI.
        # This check precedes even CLI capability probes/subprocess launch.
        if issubclass(output, WorkerResult):
            if not is_worker_code_only(role):
                raise OrchestratorError(
                    "T090 BLOCKED: unsafe Worker process/full-access permissions"
                )
            raise OrchestratorError(
                "T090 BLOCKED: no independently verified edit-only Worker execution backend"
            )
        version = execute([role.executable, "--version"], cwd, timeout=30)
        help_result = execute([role.executable, "--help"], cwd, timeout=30)
        probes = [version, help_result]
        schema_path = artifacts / f"{name}.schema.json"
        atomic_json(schema_path, output.model_json_schema())
        if any(p.exit_code or p.timed_out or p.oversized for p in probes):
            raise OrchestratorError("Provider CLI capability probe failed")
        # CLI help is informational output: agy writes it to stderr with exit 0.
        help_text = help_result.stdout + "\n" + help_result.stderr
        if role.provider != "agy" and role.allow_process:
            raise OrchestratorError("allow_process is supported only by agy Worker")
        if role.provider != "codex" and role.worker_access == "full-access":
            raise OrchestratorError("worker_access full-access is supported only by Codex Worker")
        if role.provider == "codex":
            details = execute([role.executable, "exec", "--help"], cwd, timeout=30)
            probes.append(details)
            if details.exit_code or details.timed_out or details.oversized:
                raise OrchestratorError("Provider CLI capability probe failed")
            details_text = details.stdout + "\n" + details.stderr
            for flag in ["--output-schema", "--output-last-message", "--sandbox", "--ephemeral"]:
                if flag not in details_text:
                    raise OrchestratorError(f"Codex lacks required capability: {flag}")
            if "--ask-for-approval" not in help_text:
                raise OrchestratorError("Codex lacks non-interactive approval policy")
            if (
                not readonly
                and role.worker_access == "full-access"
                and "danger-full-access" not in details_text
            ):
                raise OrchestratorError("Codex lacks required capability: danger-full-access")
            response_path = artifacts / f"{name}.response.json"
            command = [
                role.executable,
                "-a",
                "never",
                "exec",
                "--ephemeral",
                "--sandbox",
                "read-only"
                if readonly
                else (
                    "danger-full-access"
                    if role.worker_access == "full-access"
                    else "workspace-write"
                ),
                "--output-schema",
                str(schema_path),
                "--output-last-message",
                str(response_path),
            ]
            if role.reasoning:
                command.extend(["-c", f'model_reasoning_effort="{role.reasoning}"'])
            if role.model:
                command.extend(["--model", role.model])
            command.append("-")
        elif role.provider == "gemini":
            for flag in ["--prompt", "--output-format", "--approval-mode", "--skip-trust"]:
                if flag not in help_text:
                    raise OrchestratorError(f"Gemini lacks required capability: {flag}")
            if role.reasoning:
                raise OrchestratorError("Gemini CLI exposes no reasoning-effort flag; set null")
            command = [
                role.executable,
                "--skip-trust",
                "--prompt",
                "Follow the JSON instructions supplied on stdin.",
                "--output-format",
                "json",
                "--approval-mode",
                "plan" if readonly else "yolo",
            ]
            if role.model:
                command.extend(["--model", role.model])
        else:
            flags = [
                "--input-format",
                "--output-format",
                "--json-schema",
                "--mode",
                "--disable-slash-commands",
            ]
            if role.model:
                flags.append("--model")
            if role.reasoning:
                flags.append("--effort")
                if role.reasoning == "xhigh":
                    raise OrchestratorError(
                        "agy effort supports low/medium/high; xhigh is unsupported"
                    )
            if not readonly and role.allow_process:
                flags.append("--dangerously-skip-permissions")
            for flag in flags:
                if flag not in help_text:
                    raise OrchestratorError(f"agy lacks required capability: {flag}")
            command = [
                role.executable,
                "--input-format",
                "text",
                "--output-format",
                "json",
                "--json-schema",
                str(schema_path),
                "--mode",
                "plan" if readonly else "accept-edits",
                "--disable-slash-commands",
            ]
            if not readonly and role.allow_process:
                command.append("--dangerously-skip-permissions")
            if role.model:
                command.extend(["--model", role.model])
            if role.reasoning:
                command.extend(["--effort", role.reasoning])
        result = execute(
            command,
            cwd,
            timeout=timeout,
            stdin=prompt,
            stall_timeout=role.stall_timeout_seconds,
            stall_confirm=role.stall_confirm_seconds,
        )
        atomic_json(
            artifacts / f"{name}.log.json",
            {
                "level": "AGENT",
                "provider": role.provider,
                "model": role.model,
                "probes": [p.metadata() for p in probes],
                "execution": result.metadata(),
            },
        )
        if result.stalled:
            raise AgentStallError(f"Agent process stalled (exit {result.exit_code})")
        if result.exit_code or result.timed_out or result.oversized:
            raise OrchestratorError(
                f"Agent process failed (exit {result.exit_code}, timeout={result.timed_out})"
            )
        try:
            if role.provider == "codex":
                if response_path.is_symlink() or response_path.stat().st_size > OUTPUT_LIMIT:
                    raise OrchestratorError("Agent response exceeds limit")
                raw = response_path.read_text(encoding="utf-8")
            else:
                envelope = json.loads(result.stdout)
                if role.provider == "agy" and isinstance(envelope, dict):
                    if (
                        envelope.get("is_error") not in {None, False}
                        or envelope.get("denied_actions")
                        or (
                            {"response", "result", "structured_output"}.intersection(envelope)
                            and "status" in envelope
                            and envelope["status"] not in {"SUCCESS", "success"}
                        )
                        or envelope.get("error")
                        or str(envelope.get("subtype", "")).startswith("error")
                    ):
                        raise OrchestratorError("agy returned an error result")
                    payload = envelope.get(
                        "structured_output",
                        envelope.get("result", envelope.get("response", envelope)),
                    )
                else:
                    payload = (
                        envelope.get("response", envelope)
                        if isinstance(envelope, dict)
                        else envelope
                    )
                raw = payload if isinstance(payload, str) else json.dumps(payload)
                if raw.startswith("```json\n") and raw.endswith("\n```"):
                    raw = raw[8:-4]
            return output.model_validate_json(raw)
        except (OSError, ValueError, TypeError) as error:
            raise OrchestratorError("Agent returned malformed or schema-invalid JSON") from error


def is_worker_code_only(role: Role) -> bool:
    if role.allow_process:
        return False
    if role.worker_access == "full-access":
        return False
    if role.provider == "gemini":
        return False
    return role.provider in ("codex", "agy")

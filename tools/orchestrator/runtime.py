"""Processes with opt-in deadlines, local locks, Git and replaceable CLI providers."""

import hashlib
import hmac
import importlib
import inspect
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4
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


_DOCKER_DIGEST_RE = re.compile(r"^[a-z0-9][a-z0-9._:/-]*@sha256:[a-f0-9]{64}$")


def _docker_source_digest(root: str) -> str:
    """Hash path, type, permissions and content, independent of directory root."""
    root = os.path.realpath(root)
    digest = hashlib.sha256(b"t090-tree-v1\n")
    for parent, folders, files in os.walk(root, followlinks=False):
        for name in sorted([*folders, *files]):
            path = os.path.join(parent, name)
            relative = os.path.relpath(path, root).replace(os.sep, "/")
            before = os.lstat(path)
            mode = before.st_mode
            if stat.S_ISDIR(mode):
                record = ["d", relative, mode & 0o777]
            elif stat.S_ISLNK(mode):
                link = os.readlink(path)
                if os.path.isabs(link):
                    raise ValueError("absolute source symlink forbidden")
                target = os.path.realpath(path, strict=True)
                if os.path.commonpath([root, target]) != root:
                    raise ValueError("source symlink escapes tree")
                record = ["l", relative, link]
            elif stat.S_ISREG(mode):
                if before.st_nlink != 1:
                    raise ValueError("hardlinked source forbidden")
                handle = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
                try:
                    opened = os.fstat(handle)
                    if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                        raise ValueError("source path replaced during scan")
                    file_hash = hashlib.sha256()
                    while chunk := os.read(handle, 128 * 1024):
                        file_hash.update(chunk)
                    after = os.fstat(handle)
                    if (opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns) != (
                        after.st_size,
                        after.st_mtime_ns,
                        after.st_ctime_ns,
                    ):
                        raise ValueError("source modified during scan")
                finally:
                    os.close(handle)
                record = ["f", relative, mode & 0o777, file_hash.hexdigest()]
            else:
                raise ValueError("special source file forbidden")
            digest.update(json.dumps(record, separators=(",", ":")).encode())
            digest.update(b"\n")
    return digest.hexdigest()


_DOCKER_TRUSTED_BOOTSTRAP = (
    "import hashlib, json, os, shutil, stat, sys\n"
    + inspect.getsource(_docker_source_digest)
    + "for entry in os.scandir('/source'):\n"
    "    src = entry.path\n"
    "    dst = os.path.join('/workspace', entry.name)\n"
    "    if entry.is_symlink():\n"
    "        os.symlink(os.readlink(src), dst)\n"
    "    elif entry.is_dir(follow_symlinks=False):\n"
    "        shutil.copytree(src, dst, symlinks=True)\n"
    "    else:\n"
    "        shutil.copy2(src, dst)\n"
    "try:\n"
    "    attested = _docker_source_digest('/workspace') == sys.argv[1]\n"
    "except (OSError, ValueError):\n"
    "    attested = False\n"
    "if not attested:\n"
    "    raise SystemExit('T090 SANDBOX_BLOCKED: source attestation mismatch')\n"
    "os.chdir('/workspace')\n"
    "os.execvp(sys.argv[2], sys.argv[2:])\n"
)


@dataclass(frozen=True)
class DockerVerificationPolicy:
    """Host-selected immutable Docker image and fixed execution limits.

    An image digest identifies content but does not independently attest its
    publisher or dependency provenance; approval is a separate host gate.
    """

    image: str
    verification_root: Path
    memory_mib: int = 512
    cpu_millicores: int = 1000
    pids_limit: int = 64
    timeout_seconds: int = 900

    def __post_init__(self) -> None:
        if not _DOCKER_DIGEST_RE.fullmatch(self.image):
            raise OrchestratorError("T090 SANDBOX_BLOCKED: image must use a pinned sha256 digest")
        if not (128 <= self.memory_mib <= 4096):
            raise OrchestratorError("T090 SANDBOX_BLOCKED: invalid memory limit")
        if not (100 <= self.cpu_millicores <= 4000):
            raise OrchestratorError("T090 SANDBOX_BLOCKED: invalid CPU limit")
        if not (16 <= self.pids_limit <= 256):
            raise OrchestratorError("T090 SANDBOX_BLOCKED: invalid PID limit")
        if not (1 <= self.timeout_seconds <= 3600):
            raise OrchestratorError("T090 SANDBOX_BLOCKED: timeout must be finite")
        if not self.verification_root.is_absolute():
            raise OrchestratorError("T090 SANDBOX_BLOCKED: verification root must be absolute")


class DockerVerificationSandbox:
    """Constructs an unprivileged, network-free Docker command from host policy.

    This is a candidate host executor only. The live pipeline's two legacy
    verification callsites must not be treated as sandboxed until explicitly
    migrated and independently verified against a trusted runner image.
    """

    def __init__(self, policy: DockerVerificationPolicy) -> None:
        self.policy = policy

    def _workspace(self, workspace: Path) -> Path:
        if os.name != "posix" or os.geteuid() == 0:
            raise OrchestratorError("T090 SANDBOX_BLOCKED: requires non-root Linux host")
        if workspace.is_symlink() or workspace.name != "workspace":
            raise OrchestratorError("T090 SANDBOX_BLOCKED: invalid workspace entry")
        if not workspace.parent.name.startswith("verify-"):
            raise OrchestratorError("T090 SANDBOX_BLOCKED: workspace is not a verification clone")
        try:
            trusted = self.policy.verification_root.resolve(strict=True)
            resolved = workspace.resolve(strict=True)
            if not resolved.is_relative_to(trusted) or resolved == trusted:
                raise OrchestratorError("T090 SANDBOX_BLOCKED: workspace outside trusted root")
            if not resolved.is_dir():
                raise OrchestratorError("T090 SANDBOX_BLOCKED: workspace is not a directory")
            for root, folders, files in os.walk(resolved, followlinks=False):
                for name in [*folders, *files]:
                    path = Path(root) / name
                    mode = path.lstat().st_mode
                    if stat.S_ISLNK(mode):
                        target = path.resolve(strict=True)
                        if not target.is_relative_to(resolved):
                            raise OrchestratorError(
                                "T090 SANDBOX_BLOCKED: workspace symlink escapes sandbox"
                            )
                    elif stat.S_ISREG(mode) and path.lstat().st_nlink > 1:
                        raise OrchestratorError(
                            "T090 SANDBOX_BLOCKED: linked source may alias host files"
                        )
                    elif not stat.S_ISREG(mode) and not stat.S_ISDIR(mode):
                        raise OrchestratorError(
                            "T090 SANDBOX_BLOCKED: workspace has a special file"
                        )
            return resolved
        except (OSError, RuntimeError) as error:
            raise OrchestratorError("T090 SANDBOX_BLOCKED: unreadable workspace") from error

    def source_digest(self, workspace: Path) -> str:
        """Host must persist this digest at a trusted earlier source-freeze step."""
        try:
            return _docker_source_digest(str(self._workspace(workspace)))
        except (OSError, ValueError) as error:
            raise OrchestratorError("T090 SANDBOX_BLOCKED: source digest unavailable") from error

    def _attest_source(self, workspace: Path, expected: str) -> None:
        if not hmac.compare_digest(self.source_digest(workspace), expected):
            raise OrchestratorError("T090 SANDBOX_BLOCKED: source attestation mismatch")

    def _argv(
        self,
        command: list[str],
        workspace: Path,
        container: str,
        config_dir: Path,
        expected_source_digest: str,
    ) -> list[str]:
        from tools.orchestrator.core import validate_command

        validate_command(command)
        if command[:2] == ["npm", "ci"]:
            raise OrchestratorError("T090 SANDBOX_BLOCKED: setup requires trusted preprovisioning")
        uid = os.geteuid()
        gid = os.getegid()
        if any(character in str(workspace) for character in ",\n\r"):
            raise OrchestratorError("T090 SANDBOX_BLOCKED: invalid Docker mount source")
        return [
            "/usr/bin/docker",
            "--config",
            str(config_dir),
            "run",
            "--rm",
            "--pull=never",
            "--name",
            container,
            "--network=none",
            "--read-only",
            # Override any image-defined ENTRYPOINT. Container execution must
            # begin with the trusted Python interpreter, never image metadata.
            "--entrypoint=/usr/local/bin/python3",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--pids-limit",
            str(self.policy.pids_limit),
            "--memory",
            f"{self.policy.memory_mib}m",
            "--memory-swap",
            f"{self.policy.memory_mib}m",
            "--cpus",
            f"{self.policy.cpu_millicores / 1000:.3f}",
            "--user",
            f"{uid}:{gid}",
            "--workdir=/workspace",
            "--mount",
            f"type=bind,src={workspace},dst=/source,readonly,bind-propagation=rprivate",
            "--tmpfs=/workspace:rw,nosuid,nodev,size=256m,mode=1777",
            "--tmpfs=/tmp:rw,nosuid,nodev,size=64m,mode=1777",
            "--ulimit=core=0:0",
            "--env=HOME=/tmp",
            "--env=TMPDIR=/tmp",
            "--env=PYTHONDONTWRITEBYTECODE=1",
            "--env=CI=true",
            "--env=PATH=/workspace/node_modules/.bin:/node_modules/.bin:/usr/local/bin:/usr/bin:/bin",
            self.policy.image,
            "-I",
            "-c",
            _DOCKER_TRUSTED_BOOTSTRAP,
            expected_source_digest,
            *command,
        ]

    @staticmethod
    def _local_docker(argv: list[str]) -> list[str]:
        # Host-owned Docker client uses a fixed local socket, no inherited
        # DOCKER_HOST, user Docker context or credential-bearing HOME.
        return [
            "/usr/bin/env",
            "-i",
            "PATH=/usr/bin:/bin",
            "HOME=/tmp",
            "DOCKER_HOST=unix:///var/run/docker.sock",
            *argv,
        ]

    def run(
        self,
        command: list[str],
        workspace: Path,
        *,
        expected_source_digest: str | None = None,
    ) -> ProcessResult:
        """Execute ONLY against a source digest supplied by a trusted Host freeze."""
        from tools.orchestrator.core import validate_command

        validate_command(command)
        if command[:2] == ["npm", "ci"]:
            raise OrchestratorError("T090 SANDBOX_BLOCKED: setup needs trusted dependencies")
        if expected_source_digest is None or not re.fullmatch(
            r"[a-f0-9]{64}", expected_source_digest
        ):
            raise OrchestratorError("T090 SANDBOX_BLOCKED: trusted source digest required")
        resolved = self._workspace(workspace)
        if not Path("/usr/bin/docker").is_file():
            raise OrchestratorError("T090 SANDBOX_BLOCKED: Docker executable unavailable")
        self._attest_source(resolved, expected_source_digest)

        # Docker binds a private Host-owned source seal, never the original candidate.
        # Any mutation during copying or execution is checked against the frozen digest.
        with tempfile.TemporaryDirectory(
            prefix="verify-sealed-", dir=self.policy.verification_root
        ) as sealed_root:
            sealed = Path(sealed_root) / "workspace"
            try:
                shutil.copytree(resolved, sealed, symlinks=True)
            except (OSError, shutil.Error) as error:
                raise OrchestratorError("T090 SANDBOX_BLOCKED: source sealing failed") from error
            self._attest_source(sealed, expected_source_digest)

            with tempfile.TemporaryDirectory(prefix="t090-docker-config-") as temporary:
                config_dir = Path(temporary)
                inspected = execute(
                    self._local_docker(
                        [
                            "/usr/bin/docker",
                            "--config",
                            str(config_dir),
                            "image",
                            "inspect",
                            "--format",
                            "{{.Id}}",
                            self.policy.image,
                        ]
                    ),
                    sealed,
                    timeout=20,
                )
                if inspected.exit_code or not re.fullmatch(
                    r"sha256:[a-f0-9]{64}\s*", inspected.stdout
                ):
                    raise OrchestratorError("T090 SANDBOX_BLOCKED: pinned local image unavailable")

                self._attest_source(sealed, expected_source_digest)
                name = f"t090-verify-{uuid4().hex}"
                try:
                    result = execute(
                        self._local_docker(
                            self._argv(command, sealed, name, config_dir, expected_source_digest)
                        ),
                        sealed,
                        timeout=self.policy.timeout_seconds,
                    )
                finally:
                    cleanup = execute(
                        self._local_docker(
                            ["/usr/bin/docker", "--config", str(config_dir), "rm", "-f", name]
                        ),
                        sealed,
                        timeout=20,
                    )
                    if (
                        cleanup.timed_out
                        or cleanup.oversized
                        or (cleanup.exit_code != 0 and "No such container" not in cleanup.stderr)
                    ):
                        raise OrchestratorError("T090 SANDBOX_BLOCKED: cleanup not confirmed")
                self._attest_source(sealed, expected_source_digest)
                return result


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
        # Never collapse a rename into its destination: both the deleted source
        # and added destination must pass the contract's changed-path allowlist.
        changed = self.run("diff", "--no-renames", "--name-only", "-z", base, "--")
        staged = self.run("diff", "--cached", "--no-renames", "--name-only", "-z", base, "--")
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


class SecureProvider:
    """Production role router: no analyst/reviewer CLI command execution.

    Explicitly injected AgentProvider instances remain test doubles used by
    the orchestration regression suite; production Pipeline defaults here.
    """

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
        if not readonly:
            # Mutable Worker dispatch goes exclusively through host-http-edit
            # in Pipeline.invoke; never use a CLI fallback from this router.
            raise OrchestratorError("T090 BLOCKED: mutable CLI execution is forbidden")
        if not cwd.is_dir() or not artifacts.is_dir() or not name.strip():
            raise OrchestratorError("T090 BLOCKED: invalid host-owned semantic context")
        if (
            role.analysis_backend != "host-http-text"
            or role.allow_process
            or role.worker_access == "full-access"
            or role.provider not in {"agy", "codex"}
            or output is WorkerResult
        ):
            raise OrchestratorError(
                "T090 BLOCKED: read-only CLI can execute commands; "
                "configure a verified tool-free text provider"
            )
        from tools.orchestrator.worker_sandbox import (
            HostEditRejected,
            LoopbackChatTransport,
        )

        try:
            if not role.model or not role.host_text_endpoint or not role.host_text_api_key_env:
                raise HostEditRejected("Incomplete text-only semantic provider")
            transport = LoopbackChatTransport(
                role.host_text_endpoint,
                api_key_env=role.host_text_api_key_env,
                response_contract="semantic-json",
            )
            raw = transport.complete(prompt, model=role.model, timeout=timeout)
            return output.model_validate_json(raw)
        except (HostEditRejected, ValueError, TypeError) as error:
            raise OrchestratorError(
                "T090 BLOCKED: tool-free semantic inference rejected or schema invalid"
            ) from error


def is_worker_code_only(role: Role) -> bool:
    if role.allow_process:
        return False
    if role.worker_access == "full-access":
        return False
    if role.provider == "gemini":
        return False
    return role.provider in ("codex", "agy")

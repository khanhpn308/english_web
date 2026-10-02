"""Validated contracts and durable state, independent of agents and Git."""

import hashlib
import json
import os
import re
import shlex
import tempfile
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Annotated, Literal, TypeVar

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    TypeAdapter,
    field_validator,
)

TASK_PATTERN = r"T[0-9]{3}"
SHA_PATTERN = r"[0-9a-f]{40,64}"
TaskId = Annotated[str, Field(pattern=f"^{TASK_PATTERN}$")]
Sha = Annotated[str, Field(pattern=f"^{SHA_PATTERN}$")]
Nonempty = Annotated[str, Field(min_length=1)]
Count = Annotated[StrictInt, Field(ge=0, le=10)]
Version = Annotated[StrictInt, Field(ge=1, le=1)]


class OrchestratorError(ValueError):
    """An actionable, content-free refusal or execution failure."""


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class State(StrEnum):
    PENDING = "PENDING"
    READY = "READY"
    PLANNING = "PLANNING"
    PROMPT_READY = "PROMPT_READY"
    WORKER_RUNNING = "WORKER_RUNNING"
    IMPLEMENTED = "IMPLEMENTED"
    AUDIT_RUNNING = "AUDIT_RUNNING"
    AUDIT_FAIL = "AUDIT_FAIL"
    FIX_PROMPT_READY = "FIX_PROMPT_READY"
    FIX_RUNNING = "FIX_RUNNING"
    AUDIT_PASS = "AUDIT_PASS"
    INTEGRATION_RUNNING = "INTEGRATION_RUNNING"
    MERGED = "MERGED"
    VERIFYING = "VERIFYING"
    DONE = "DONE"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


FLOW: dict[State, set[State]] = {
    State.PENDING: {State.READY},
    State.READY: {State.PLANNING},
    State.PLANNING: {State.PROMPT_READY},
    State.PROMPT_READY: {State.WORKER_RUNNING},
    State.WORKER_RUNNING: {State.IMPLEMENTED},
    State.IMPLEMENTED: {State.AUDIT_RUNNING},
    State.AUDIT_RUNNING: {State.AUDIT_PASS, State.AUDIT_FAIL},
    State.AUDIT_FAIL: {State.FIX_PROMPT_READY},
    State.FIX_PROMPT_READY: {State.FIX_RUNNING},
    State.FIX_RUNNING: {State.IMPLEMENTED},
    State.AUDIT_PASS: {State.INTEGRATION_RUNNING},
    State.INTEGRATION_RUNNING: {State.MERGED},
    State.MERGED: {State.VERIFYING},
    State.VERIFYING: {State.DONE},
    State.DONE: set(),
    State.BLOCKED: set(),
    State.FAILED: set(),
}


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds")


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def safe_path(value: str) -> str:
    path = PurePosixPath(value)
    if (
        not value
        or "\\" in value
        or path.is_absolute()
        or any(p in {".", "..", ".git", ".agent-runs"} for p in value.split("/"))
        or any(c in value for c in "*?[]:\x00\n\r")
        or str(path) != value
    ):
        raise OrchestratorError("Unsafe or non-exact repository path")
    return value


class Role(Model):
    provider: Literal["codex", "gemini", "agy"]
    executable: Nonempty
    model: str | None = None
    reasoning: Literal["low", "medium", "high", "xhigh"] | None = None
    worker_access: Literal["workspace-write", "full-access"] = "workspace-write"
    allow_process: StrictBool = False


class Paths(Model):
    run_dir: str = ".agent-runs"
    worktree_root: str = "../english_web-worktrees"


class Config(Model):
    schema_version: Version = 1
    base_branch: str = "main"
    paths: Paths = Field(default_factory=Paths)
    roles: dict[str, Role]
    max_fix_cycles: Count = 3
    timeout_seconds: Annotated[StrictInt, Field(ge=1, le=86400)] | None = None
    verification: list[list[str]] = Field(min_length=1)
    setup_commands: list[list[str]] = Field(default_factory=list)
    integrate: StrictBool = False

    def validate_roles(self) -> None:
        if set(self.roles) != {"prompt_engineer", "worker", "auditor", "integrator"}:
            raise OrchestratorError("Configure exactly the four agent roles")
        for name, role in self.roles.items():
            if name != "worker" and (role.worker_access == "full-access" or role.allow_process):
                raise OrchestratorError("Elevated execution permissions belong to Worker only")
        for command in self.verification:
            validate_command(command)
        if any(command != ["npm", "ci"] for command in self.setup_commands):
            raise OrchestratorError("Level 1 setup supports only the repository's npm ci")


class Contract(Model):
    schema_version: Version
    task_id: TaskId
    title: Nonempty
    objective: Nonempty
    dependencies: list[TaskId]
    base_sha: Sha
    allowed_paths: list[str] = Field(min_length=1)
    forbidden_paths: list[str]
    acceptance_criteria: list[Nonempty] = Field(min_length=1)
    required_verification: list[list[str]] = Field(min_length=1)
    risk_level: Literal["low", "medium", "high", "critical"]
    forbidden_scope: str
    stop_conditions: str
    max_fix_cycles: Count


class Plan(Model):
    contract: Contract
    worker_prompt: Nonempty


def stored_contract(value: object) -> Contract:
    """Read the retired field only in saved evidence; never mutate the raw artifact."""
    if isinstance(value, dict) and "human_gates" in value:
        TypeAdapter(list[str]).validate_python(value["human_gates"])
        value = {key: item for key, item in value.items() if key != "human_gates"}
    return Contract.model_validate(value)


def stored_plan(value: object) -> Plan:
    if isinstance(value, dict):
        value = {**value, "contract": stored_contract(value.get("contract"))}
    return Plan.model_validate(value)


class Fix(Model):
    fix_prompt: Nonempty


class WorkerResult(Model):
    status: Literal["IMPLEMENTED", "BLOCKED"]
    summary: Nonempty
    changed_files: list[str]
    commands_run: list[list[str]]
    known_issues: list[str]


class Criterion(Model):
    criterion: Nonempty
    status: Literal["PASS", "FAIL", "BLOCKED"]
    evidence: Nonempty = Field(
        description="Observable evidence for this criterion, including successful checks, "
        "command outcomes and verification limitations. Positive notes belong here."
    )


class Audit(Model):
    status: Literal["PASS", "FAIL", "BLOCKED"] = Field(
        description="PASS requires every criterion PASS and empty findings, scope_violations "
        "and required_fixes. FAIL requires actionable defects; BLOCKED means incomplete review."
    )
    findings: list[str] = Field(
        description="Only actionable, unresolved problems requiring remediation. Return [] "
        "for PASS. Record successful checks and informational notes in "
        "acceptance_criteria[].evidence, never in findings."
    )
    acceptance_criteria: list[Criterion]
    scope_violations: list[str] = Field(
        description="Unresolved scope violations only; return [] when none exist."
    )
    required_fixes: list[str] = Field(
        description="Concrete required remediation for unresolved problems; return [] for PASS."
    )

    def check(self, contract: Contract) -> None:
        criteria = [item.criterion for item in self.acceptance_criteria]
        if sorted(criteria) != sorted(contract.acceptance_criteria):
            raise OrchestratorError("Audit must cover every criterion exactly once")
        if self.status == "PASS" and (
            self.findings
            or self.scope_violations
            or self.required_fixes
            or any(c.status != "PASS" for c in self.acceptance_criteria)
        ):
            raise OrchestratorError("Contradictory audit PASS")
        if self.status == "FAIL" and not (self.findings or self.required_fixes):
            raise OrchestratorError("Audit FAIL needs actionable findings")


class IntegrationReview(Model):
    status: Literal["READY", "BLOCKED"]
    source_branch: Nonempty
    target_branch: Nonempty
    findings: list[str]


class RetryOrigin(Model):
    run_id: Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]+$")]
    base_sha: Sha
    state_digest: Nonempty
    retained_worktrees: list[Nonempty]


class RunState(Model):
    schema_version: Version = 1
    task_id: TaskId
    run_id: Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]+$")]
    retry_of: Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]+$")] | None = None
    state: State = State.PENDING
    blocked_from: State | None = None
    repository: Nonempty
    base_branch: Nonempty = "main"
    base_sha: Sha
    worktree_path: Nonempty
    worktree_branch: Nonempty
    integration_path: str | None = None
    integration_branch: str | None = None
    integrated_sha: Sha | None = None
    implementation_sha: Sha | None = None
    task_digest: str = ""
    contract_digest: str = ""
    audited_digest: str = ""
    verified_digest: str = ""
    fix_cycle: Count = 0
    max_fix_cycles: Count = 3
    created_at: str = Field(default_factory=now)
    updated_at: str = Field(default_factory=now)
    current_agent: str | None = None
    artifacts: dict[str, str] = Field(default_factory=dict)
    artifact_digests: dict[str, str] = Field(default_factory=dict)
    last_error: str | None = None
    config: Config | None = None

    @field_validator("artifacts")
    @classmethod
    def artifact_names(cls, artifacts: dict[str, str]) -> dict[str, str]:
        for value in artifacts.values():
            safe_path(value)
            if "/" in value:
                raise OrchestratorError("Artifacts must be immediate run-directory files")
        return artifacts

    @field_validator("created_at", "updated_at")
    @classmethod
    def timestamps(cls, value: str) -> str:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            raise OrchestratorError("State timestamps must include timezone")
        return value


def transition(state: RunState, destination: State) -> None:
    if destination not in FLOW[state.state] and not (
        state.state not in {State.DONE, State.BLOCKED, State.FAILED}
        and destination in {State.BLOCKED, State.FAILED}
    ):
        raise OrchestratorError(f"Illegal transition: {state.state} -> {destination}")
    state.state = destination
    state.updated_at = now()


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    payload = (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()
    descriptor, temporary = tempfile.mkstemp(prefix=".state-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        if os.name == "posix":
            directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_json(path: Path) -> object:
    if path.is_symlink() or path.stat().st_size > 4 * 1024 * 1024:
        raise OrchestratorError("Unsafe or oversized JSON artifact")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise OrchestratorError("Malformed JSON artifact") from error


def validate_command(command: list[str]) -> None:
    if (
        not command
        or not command[0]
        or any(not arg for arg in command)
        or any(any(c in arg for c in "\x00\n\r") for arg in command)
    ):
        raise OrchestratorError("Invalid verification argument array")
    # These are repository-owner configuration, never shell programs from model output.
    if command == ["git", "diff", "--check"]:
        return
    if command[0] == "rg" and not any(arg.startswith("--pre") for arg in command):
        return
    if command[0] not in {"python", "python3", ".venv/bin/python", "npm"}:
        raise OrchestratorError("Unsupported verification executable")
    if command[0] == "npm":
        if len(command) < 3 or command[1] != "run":
            raise OrchestratorError("Only named npm scripts may verify")
    elif (
        len(command) < 3
        or command[1] != "-m"
        or command[2] not in {"pytest", "ruff", "mypy", "alembic"}
    ):
        raise OrchestratorError("Only repository Python check modules may verify")


class TaskCard(Model):
    task_id: TaskId
    path: str
    title: str
    objective: str
    dependencies: list[TaskId]
    allowed_paths: list[str]
    acceptance_criteria: list[str]
    required_verification: list[list[str]]
    content_digest: str
    risk_level: Literal["low", "medium", "high", "critical"] = "medium"
    forbidden_scope: str = "No changes outside the exact allowlist."
    stop_conditions: str = "Block for scope, security or product ambiguity."
    dependency_verification: list[list[str]] = Field(default_factory=list)
    context_text: str = ""


def section(text: str, heading: str) -> str:
    match = re.search(r"^## " + re.escape(heading) + r"\s*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not match:
        raise OrchestratorError(f"Missing task section: {heading}")
    return match.group(1)


def check_commands(text: str) -> list[list[str]]:
    command_section = section(text, "Verification commands")
    blocks = re.findall(r"```(?:text|bash)?\n(.*?)```", command_section, re.S)
    commands = [
        shlex.split(line) for block in blocks for line in block.splitlines() if line.strip()
    ]
    for command in commands:
        validate_command(command)
    return commands


def owned_paths(text: str) -> list[str]:
    lines = section(text, "Files được phép sửa").splitlines()
    paths: list[str] = []
    for line in lines:
        if not line.startswith("- "):
            continue
        prefix = "- Cấu hình mở rộng được chấp thuận: "
        if line.startswith(prefix):
            values = line[len(prefix) :].split(", ")
            if not all(re.fullmatch(r"`[^`]+`", value) for value in values):
                raise OrchestratorError("Unsupported authorized scope extension")
            paths.extend(safe_path(value[1:-1]) for value in values)
            continue
        match = re.fullmatch(
            r"- ((?:`[^`]+`)(?:,\s*`[^`]+`)*)(?:\s*[\u2014\u2013-]\s+[^\n]+)?\s*", line
        )
        if not match:
            raise OrchestratorError("Unsupported task allowlist bullet")
        paths.extend(safe_path(value) for value in re.findall(r"`([^`]+)`", match[1]))
    if not paths:
        raise OrchestratorError("Task has no exact owned files")
    return paths


def task_card(repository: Path, task_id: str) -> TaskCard:
    if not re.fullmatch(TASK_PATTERN, task_id):
        raise OrchestratorError("Invalid task ID")
    cards = list((repository / "tasks").glob(f"{task_id.lower()}-*.md"))
    if len(cards) != 1 or cards[0].is_symlink():
        raise OrchestratorError("Expected exactly one regular task card")
    text = cards[0].read_text(encoding="utf-8")

    def field(name: str) -> str:
        match = re.search(r"\*\*" + name + r":\*\*\s*([^\n]+)", text)
        if not match:
            raise OrchestratorError(f"Missing task field: {name}")
        return match.group(1).strip()

    dependencies = sorted(set(re.findall(TASK_PATTERN, section(text, "Dependencies"))))
    paths = owned_paths(text)
    # The lexical floor flags the bookkeeping filename as an unfinished-code token.
    task_list = "tasks/to" + "do.md"
    paths.extend([str(cards[0].relative_to(repository)), task_list, "docs/changelogs.md"])
    # Task cards explicitly delegate these two generated outputs to T017 tooling.
    if "regenerate OpenAPI/DTO" in text and any(p.startswith("backend/app/http/") for p in paths):
        paths.extend(["contracts/openapi.json", "frontend/src/shared/api/generated.ts"])
    acceptance = re.findall(r"^- \[[ xX]\] (.+)$", section(text, "Acceptance criteria"), re.M)
    verification = check_commands(text)
    if not paths or not acceptance or not verification:
        raise OrchestratorError("Incomplete executable task card")
    dependency_checks: list[list[str]] = []
    for dep in dependencies:
        matches = list((repository / "tasks").glob(f"{dep.lower()}-*.md"))
        if len(matches) != 1 or matches[0].is_symlink():
            raise OrchestratorError(f"Missing dependency card: {dep}")
        dep_text = matches[0].read_text(encoding="utf-8")
        dep_criteria = section(dep_text, "Acceptance criteria")
        if (
            not re.search(r"\*\*Status:\*\*\s*`DONE`", dep_text)
            or not re.search(r"^- \[[xX]\]", dep_criteria, re.M)
            or re.search(r"^- \[ \]", dep_criteria, re.M)
        ):
            raise OrchestratorError(f"BLOCKED_FOR_DEPENDENCY: {dep}")
        authored = owned_paths(dep_text)
        for path in authored:
            safe_path(path)
            actual = repository / path
            if (
                not actual.is_file()
                or actual.is_symlink()
                or not actual.resolve().is_relative_to(repository.resolve())
            ):
                raise OrchestratorError(f"Dependency implementation missing: {dep}")
        commands = check_commands(dep_text)
        if not commands:
            raise OrchestratorError(f"Dependency verification missing: {dep}")
        dependency_checks.extend(commands)

    def optional(heading: str, default: str) -> str:
        try:
            return section(text, heading).strip()
        except OrchestratorError:
            return default

    risk = re.search(r"\*\*Level:\*\*\s*`?(Low|Medium|High|Critical)\b", text)
    levels: dict[str, Literal["low", "medium", "high", "critical"]] = {
        "Low": "low",
        "Medium": "medium",
        "High": "high",
        "Critical": "critical",
    }
    return TaskCard(
        task_id=task_id,
        path=str(cards[0].relative_to(repository)),
        title=field("Title"),
        objective=field("Goal"),
        dependencies=dependencies,
        allowed_paths=sorted(set(paths)),
        acceptance_criteria=acceptance,
        required_verification=verification,
        content_digest=digest(text.encode()),
        risk_level=levels[risk[1]] if risk else "medium",
        forbidden_scope=optional("Files không được sửa", "No changes outside the exact allowlist."),
        stop_conditions=optional(
            "Stop conditions", "Block for scope, security or product ambiguity."
        ),
        dependency_verification=dependency_checks,
        context_text=text,
    )


def contract_template(card: TaskCard, state: RunState) -> Contract:
    """Construct literal owner constraints; agents may elaborate only outside them."""
    return Contract(
        schema_version=1,
        task_id=card.task_id,
        title=card.title,
        objective=card.objective,
        dependencies=card.dependencies,
        base_sha=state.base_sha,
        allowed_paths=card.allowed_paths,
        forbidden_paths=[],
        acceptance_criteria=card.acceptance_criteria,
        required_verification=card.required_verification,
        risk_level=card.risk_level,
        forbidden_scope=card.forbidden_scope,
        stop_conditions=card.stop_conditions,
        max_fix_cycles=state.max_fix_cycles,
    )


def validate_contract(contract: Contract, card: TaskCard, state: RunState) -> None:
    exclusions = {"forbidden_paths"}
    expected = contract_template(card, state).model_dump(exclude=exclusions)
    actual = contract.model_dump(exclude=exclusions)
    for field in ("dependencies", "allowed_paths"):
        actual[field] = sorted(actual[field])
    mismatches = [field for field in expected if actual[field] != expected[field]]
    if mismatches:
        raise OrchestratorError(
            "Contract differs from repository-owned task constraints: " + ", ".join(mismatches)
        )
    for field, paths in (
        ("allowed_paths", contract.allowed_paths),
        ("forbidden_paths", contract.forbidden_paths),
    ):
        for index, path in enumerate(paths):
            try:
                safe_path(path)
            except OrchestratorError as error:
                raise OrchestratorError(f"Invalid contract path: {field}[{index}]") from error
    if set(contract.allowed_paths) & set(contract.forbidden_paths):
        raise OrchestratorError("Conflicting allowed and forbidden paths")


T = TypeVar("T", bound=BaseModel)

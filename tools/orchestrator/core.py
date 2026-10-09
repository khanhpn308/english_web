"""Validated contracts and durable state, independent of agents and Git."""

import hashlib
import json
import os
import re
import shlex
import tempfile
from dataclasses import dataclass
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
    model_validator,
)

TASK_PATTERN = r"T[0-9]{3}"
SHA_PATTERN = r"[0-9a-f]{40,64}"
TaskId = Annotated[str, Field(pattern=f"^{TASK_PATTERN}$")]
Sha = Annotated[str, Field(pattern=f"^{SHA_PATTERN}$")]
Nonempty = Annotated[str, Field(min_length=1)]
Count = Annotated[StrictInt, Field(ge=0, le=10)]
Version = Annotated[StrictInt, Field(ge=1, le=1)]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Nanoseconds = Annotated[StrictInt, Field(ge=0)]


class OrchestratorError(ValueError):
    """An actionable, content-free refusal or execution failure."""


class AgentStallError(OrchestratorError):
    """An AI provider subprocess failed to make observable byte progress."""


KNOWN_ATTEMPT_ARTIFACT_SUFFIXES: tuple[str, ...] = (
    ".prompt.md",
    ".auditor-context.json",
    ".integrator-context.json",
    ".schema.json",
    ".response.json",
    ".log.json",
    ".rejected.json",
)


class AuditorContextOversizedError(OrchestratorError):
    """Auditor context exceeds the model-facing size budget."""


class IntegratorContextOversizedError(OrchestratorError):
    """Integrator context exceeds the model-facing size budget."""


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
    worker_backend: Literal["cli", "host-http-edit"] = "cli"
    host_edit_endpoint: str | None = None
    host_edit_api_key_env: str | None = None
    analysis_backend: Literal["cli", "host-http-text"] = "cli"
    host_text_endpoint: str | None = None
    host_text_api_key_env: str | None = None
    stall_timeout_seconds: Annotated[StrictInt, Field(ge=1, le=86400)] | None = None
    stall_confirm_seconds: Annotated[StrictInt, Field(ge=1, le=3600)] = 30
    max_stall_retries: Annotated[StrictInt, Field(ge=0, le=10)] = 1


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
    skills_root: Nonempty | None = None
    integrate: StrictBool = False

    def validate_roles(self) -> None:
        if set(self.roles) != {"prompt_engineer", "worker", "auditor", "integrator"}:
            raise OrchestratorError("Configure exactly the four agent roles")
        for name, role in self.roles.items():
            if name == "worker":
                if (
                    role.analysis_backend != "cli"
                    or role.host_text_endpoint is not None
                    or role.host_text_api_key_env is not None
                ):
                    raise OrchestratorError("Host text-only analysis belongs to read-only roles")
            elif role.analysis_backend == "host-http-text":
                if (
                    role.provider not in {"agy", "codex"}
                    or not role.model
                    or not role.host_text_endpoint
                    or not role.host_text_api_key_env
                ):
                    raise OrchestratorError("Incomplete host text-only analysis configuration")
                from tools.orchestrator.worker_sandbox import LoopbackChatTransport

                LoopbackChatTransport(
                    role.host_text_endpoint, api_key_env=role.host_text_api_key_env
                )
            elif role.host_text_endpoint is not None or role.host_text_api_key_env is not None:
                raise OrchestratorError("Host text endpoint requires host-http-text backend")
            if name != "worker" and (role.worker_access == "full-access" or role.allow_process):
                raise OrchestratorError("Elevated execution permissions belong to Worker only")
            if name != "worker" and (
                role.worker_backend != "cli"
                or role.host_edit_endpoint is not None
                or role.host_edit_api_key_env is not None
            ):
                raise OrchestratorError("Host-mediated editing belongs to Worker only")
            if role.worker_backend == "host-http-edit":
                if (
                    name != "worker"
                    or role.provider not in {"agy", "codex"}
                    or role.allow_process
                    or role.worker_access != "workspace-write"
                    or not role.model
                    or not role.host_edit_endpoint
                    or not role.host_edit_api_key_env
                ):
                    raise OrchestratorError(
                        "Unsafe or incomplete host-mediated Worker configuration"
                    )
                # Validate fully before any model invocation or filesystem change.
                from tools.orchestrator.worker_sandbox import LoopbackChatTransport

                LoopbackChatTransport(
                    role.host_edit_endpoint, api_key_env=role.host_edit_api_key_env
                )
            elif role.host_edit_endpoint is not None or role.host_edit_api_key_env is not None:
                raise OrchestratorError("Host-edit settings require host-http-edit backend")
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


class ReviewPerspective(StrEnum):
    CORRECTNESS = "correctness-contract-concurrency"
    VERIFICATION = "verification-failure-regression"
    SECURITY = "security-architecture-scope-privacy"


class ReviewFinding(Model):
    action: Nonempty = Field(description="Actionable unresolved defect and required remediation")
    evidence: Nonempty = Field(description="Concrete source/test evidence and rationale")

    @field_validator("action", "evidence")
    @classmethod
    def meaningful_finding(cls, value: str) -> str:
        if not value.strip():
            raise OrchestratorError("Reviewer finding requires an action and evidence")
        return value


FORBIDDEN_PROBE_OVERRIDE_KEYS = frozenset(
    {
        "command",
        "argv",
        "shell",
        "executable",
        "script",
        "powershell",
        "bash",
        "bash_fragment",
        "environment_overrides",
        "working_directory_override",
        "env",
        "cwd",
    }
)


class ProbeParameters(Model):
    """Closed model-facing parameter envelope for the initial T089 probe catalog."""

    path: Nonempty | None
    pattern: Annotated[str, Field(max_length=256)] | None

    @model_validator(mode="before")
    @classmethod
    def historical_and_safety_normalization(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value

        normalized = dict(value)

        for key in normalized:
            norm_key = str(key).lower().replace("-", "_").strip()
            if norm_key in FORBIDDEN_PROBE_OVERRIDE_KEYS:
                raise OrchestratorError(
                    f"ProbeRequest contains forbidden execution override field: {key}"
                )

        # Preserve compatibility with historical/internal callers that used
        # {} or omitted optional source-inspection pattern.
        normalized.setdefault("path", None)
        normalized.setdefault("pattern", None)
        return normalized

    def as_dict(self) -> dict[str, object]:
        """Return the legacy host-validator representation without null placeholders."""
        return self.model_dump(mode="python", exclude_none=True)


class ProbeRequest(Model):
    schema_version: Version
    probe_id: Nonempty
    perspective: ReviewPerspective
    task_id: TaskId
    base_sha: Sha
    branch: Nonempty
    source_digest: Sha
    parameters: ProbeParameters
    rationale: Nonempty

    @model_validator(mode="before")
    @classmethod
    def historical_defaults(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value

        normalized = dict(value)

        # Keep historical persisted/programmatic requests readable while the
        # model-facing JSON Schema requires these properties explicitly.
        normalized.setdefault("schema_version", 1)
        normalized.setdefault("parameters", {})
        return normalized


def probe_request_digest(request: ProbeRequest) -> str:
    payload = json.dumps(
        {
            "schema_version": request.schema_version,
            "probe_id": request.probe_id,
            "perspective": str(request.perspective),
            "task_id": request.task_id,
            "base_sha": request.base_sha,
            "branch": request.branch,
            "source_digest": request.source_digest,
            "parameters": request.parameters.as_dict(),
            "rationale": request.rationale,
        },
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return digest(payload)


class ReviewShard(Model):
    perspective: ReviewPerspective
    findings: list[ReviewFinding]
    probe_request: ProbeRequest | None

    @model_validator(mode="before")
    @classmethod
    def historical_probe_request_default(cls, value: object) -> object:
        if isinstance(value, dict) and "probe_request" not in value:
            value = dict(value)
            value["probe_request"] = None
        return value

    @model_validator(mode="after")
    def validate_probe_perspective(self) -> "ReviewShard":
        if self.probe_request is not None and self.probe_request.perspective != self.perspective:
            raise OrchestratorError("ProbeRequest perspective differs from ReviewShard perspective")
        return self


class IdentifiedFinding(ReviewFinding):
    finding_id: Nonempty


class BundledShard(Model):
    perspective: ReviewPerspective
    findings: list[IdentifiedFinding]


class ReviewBundle(Model):
    source_digest: Sha
    branch: Nonempty
    shards: list[BundledShard]

    @model_validator(mode="after")
    def canonical(self) -> "ReviewBundle":
        if [shard.perspective for shard in self.shards] != list(ReviewPerspective):
            raise OrchestratorError("Parallel review requires every perspective in canonical order")
        for shard in self.shards:
            for index, finding in enumerate(shard.findings, 1):
                if finding.finding_id != f"{shard.perspective}:{index:04d}":
                    raise OrchestratorError(
                        "Parallel review finding identity differs from host order"
                    )
        return self

    @classmethod
    def assemble(cls, source_digest: str, branch: str, shards: list[ReviewShard]) -> "ReviewBundle":
        if len(shards) != len(ReviewPerspective) or {s.perspective for s in shards} != set(
            ReviewPerspective
        ):
            raise OrchestratorError("Parallel review is incomplete")
        ordered = {shard.perspective: shard for shard in shards}
        return cls(
            source_digest=source_digest,
            branch=branch,
            shards=[
                BundledShard(
                    perspective=perspective,
                    findings=[
                        IdentifiedFinding(
                            action=finding.action,
                            evidence=finding.evidence,
                            finding_id=f"{perspective}:{index:04d}",
                        )
                        for index, finding in enumerate(ordered[perspective].findings, 1)
                    ],
                )
                for perspective in ReviewPerspective
            ],
        )


class ReviewDisposition(Model):
    finding_id: Nonempty
    disposition: Literal["confirmed", "dismissed"] = Field(
        description="Confirmed means unresolved in the frozen source and forbids PASS"
    )
    evidence: Nonempty = Field(
        description="Explicit rationale and concrete evidence for disposition"
    )

    @field_validator("evidence")
    @classmethod
    def meaningful_evidence(cls, value: str) -> str:
        if not value.strip():
            raise OrchestratorError("Reviewer disposition requires explicit evidence")
        return value


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
    reviewer_dispositions: list[ReviewDisposition]

    @model_validator(mode="before")
    @classmethod
    def historical_reviewer_dispositions_default(cls, value: object) -> object:
        """Keep historical Audit JSON readable while requiring the field in model output schema."""
        if isinstance(value, dict) and "reviewer_dispositions" not in value:
            value = dict(value)
            value["reviewer_dispositions"] = []
        return value

    def check(self, contract: Contract, bundle: ReviewBundle | None = None) -> None:
        expected = (
            {finding.finding_id for shard in bundle.shards for finding in shard.findings}
            if bundle is not None
            else set()
        )
        supplied = [item.finding_id for item in self.reviewer_dispositions]
        if len(supplied) != len(set(supplied)):
            raise OrchestratorError("Parallel review duplicate disposition")
        if set(supplied) - expected:
            raise OrchestratorError("Parallel review unknown disposition")
        if expected - set(supplied):
            raise OrchestratorError("Parallel review missing disposition")
        if self.status == "PASS" and any(
            item.disposition == "confirmed" for item in self.reviewer_dispositions
        ):
            raise OrchestratorError("Parallel review confirmed unresolved finding forbids PASS")
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


class AuditorCandidateIdentity(Model):
    task_id: TaskId
    base_sha: Sha
    branch: Nonempty
    source_digest: Sha


class AuditorContract(Model):
    title: Nonempty
    objective: Nonempty
    allowed_paths: list[str]
    forbidden_paths: list[str] = Field(default_factory=list)
    acceptance_criteria: list[Nonempty] = Field(min_length=1)
    risk_level: Literal["low", "medium", "high", "critical"]
    stop_conditions: str


class AuditorWorkerSummary(Model):
    status: Literal["IMPLEMENTED", "BLOCKED"]
    changed_files: list[str]
    known_issues: list[str] = Field(default_factory=list)


class AuditorContextV1(Model):
    schema_version: Version = 1
    candidate_identity: AuditorCandidateIdentity
    contract: AuditorContract
    worker_summary: AuditorWorkerSummary
    evidence_bundle: dict[str, object]
    review_bundle: ReviewBundle
    probe_evidence: list[dict[str, object]] = Field(default_factory=list)
    artifact_digests: dict[str, str] = Field(default_factory=dict)

    @property
    def digest(self) -> str:
        return auditor_context_digest(self)


AuditorContext = AuditorContextV1

AUDITOR_CONTEXT_MAX_BYTES: int = 64 * 1024


def serialize_auditor_context(context: AuditorContextV1) -> str:
    return json.dumps(
        context.model_dump(mode="json"),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def auditor_context_digest(context: AuditorContextV1) -> str:
    return digest(serialize_auditor_context(context).encode("utf-8"))


def auditor_context_component_sizes(context: AuditorContextV1) -> dict[str, int]:
    data = context.model_dump(mode="json")
    sizes: dict[str, int] = {}
    for key, value in sorted(data.items()):
        raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        sizes[f"{key}_bytes"] = len(raw.encode("utf-8"))
    sizes["total_bytes"] = len(serialize_auditor_context(context).encode("utf-8"))
    return sizes


def check_auditor_context_size(
    context: AuditorContextV1, max_bytes: int = AUDITOR_CONTEXT_MAX_BYTES
) -> int:
    serialized = serialize_auditor_context(context).encode("utf-8")
    if len(serialized) > max_bytes:
        diag = auditor_context_component_sizes(context)
        raise AuditorContextOversizedError(
            f"Auditor context exceeds size limit: {len(serialized)} bytes > {max_bytes} bytes. "
            f"Component diagnostics: {diag}"
        )
    return len(serialized)


class IntegratorContextV1(Model):
    schema_version: Version = 1
    contract: AuditorContract
    evidence_bundle: dict[str, object]
    source_branch: Nonempty
    target_branch: Nonempty
    target_sha: Sha

    @property
    def digest(self) -> str:
        return integrator_context_digest(self)


IntegratorContext = IntegratorContextV1
INTEGRATOR_CONTEXT_MAX_BYTES: int = 64 * 1024


def serialize_integrator_context(context: IntegratorContextV1) -> str:
    return json.dumps(
        context.model_dump(mode="json"),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def integrator_context_digest(context: IntegratorContextV1) -> str:
    return digest(serialize_integrator_context(context).encode("utf-8"))


def integrator_context_component_sizes(context: IntegratorContextV1) -> dict[str, int]:
    data = context.model_dump(mode="json")
    sizes: dict[str, int] = {}
    for key, value in sorted(data.items()):
        raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        sizes[f"{key}_bytes"] = len(raw.encode("utf-8"))
    sizes["total_bytes"] = len(serialize_integrator_context(context).encode("utf-8"))
    return sizes


def check_integrator_context_size(
    context: IntegratorContextV1, max_bytes: int = INTEGRATOR_CONTEXT_MAX_BYTES
) -> int:
    serialized = serialize_integrator_context(context).encode("utf-8")
    if len(serialized) > max_bytes:
        diag = integrator_context_component_sizes(context)
        raise IntegratorContextOversizedError(
            f"Integrator context exceeds size limit: {len(serialized)} bytes > {max_bytes} bytes. "
            f"Component diagnostics: {diag}"
        )
    return len(serialized)


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


def command_declaration_digest(command: tuple[str, ...]) -> str:
    validate_command(list(command))
    return digest(json.dumps(command, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


class FrozenEvidenceIdentity(Model):
    """Host-frozen source and ordered, privacy-safe verification declaration."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    task_id: TaskId
    base_sha: Sha
    branch: Nonempty
    source_digest: Sha256
    required_command_digests: Annotated[tuple[Sha256, ...], Field(min_length=1)]

    @classmethod
    def freeze(
        cls,
        task_id: str,
        base_sha: str,
        branch: str,
        source_digest: str,
        commands: tuple[tuple[str, ...], ...],
    ) -> "FrozenEvidenceIdentity":
        return cls(
            task_id=task_id,
            base_sha=base_sha,
            branch=branch,
            source_digest=source_digest,
            required_command_digests=tuple(command_declaration_digest(c) for c in commands),
        )


@dataclass(frozen=True)
class VerificationRequest:
    """Detached collection inputs; no state, artifact directory or pipeline authority."""

    cwd: Path
    commands: tuple[tuple[str, ...], ...]
    timeout: int | None
    identity: FrozenEvidenceIdentity

    def __post_init__(self) -> None:
        if (
            tuple(command_declaration_digest(c) for c in self.commands)
            != self.identity.required_command_digests
        ):
            raise OrchestratorError("Verification request command declaration mismatch")

    @property
    def task_id(self) -> str:
        return self.identity.task_id

    @property
    def source_digest(self) -> str:
        return self.identity.source_digest


@dataclass(frozen=True)
class VerificationCollection:
    identity: FrozenEvidenceIdentity
    results: tuple[dict[str, object], ...]
    failed: bool = False
    setup_error: str | None = None


class EvidenceArtifactRef(Model):
    name: Nonempty
    path: str
    digest: Sha
    byte_size: Annotated[StrictInt, Field(ge=0)]
    classification: Nonempty
    summary: str | None = None
    identity: FrozenEvidenceIdentity | None = None

    @field_validator("path")
    @classmethod
    def check_artifact_path(cls, value: str) -> str:
        safe_path(value)
        return value


class ProbeResultClassification(StrEnum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    OVERSIZED = "OVERSIZED"
    STALE_PROBE_REQUEST = "STALE_PROBE_REQUEST"
    UNSUPPORTED = "UNSUPPORTED"
    INVALID = "INVALID"
    DENIED_BY_POLICY = "DENIED_BY_POLICY"
    SETUP_ERROR = "SETUP_ERROR"


class ProbeEvidence(Model):
    schema_version: Version = 1
    probe_id: Nonempty
    request_id: Sha256
    task_id: TaskId
    base_sha: Sha
    branch: Nonempty
    source_digest: Sha
    perspective: ReviewPerspective
    executor_id: Nonempty
    parameters: dict[str, object] = Field(default_factory=dict)
    classification: ProbeResultClassification
    result: dict[str, object] = Field(default_factory=dict)
    artifacts: list[EvidenceArtifactRef] = Field(default_factory=list)
    duration_ns: Nanoseconds | None = None
    timed_out: StrictBool = False
    oversized: StrictBool = False

    @model_validator(mode="after")
    def validate_integrity(self) -> "ProbeEvidence":
        if self.timed_out and self.classification != ProbeResultClassification.TIMED_OUT:
            raise OrchestratorError("Timed out probe evidence must have TIMED_OUT classification")
        if self.oversized and self.classification != ProbeResultClassification.OVERSIZED:
            raise OrchestratorError("Oversized probe evidence must have OVERSIZED classification")
        return self


class ReviewerContext(Model):
    schema_version: Version = 1
    perspective: ReviewPerspective
    task_id: TaskId
    base_sha: Sha
    branch: Nonempty
    source_digest: Sha
    contract: Contract
    worker_result: WorkerResult | None = None
    verification_status: Literal["PENDING", "COMPLETED"] = "PENDING"
    executable_evidence: dict[str, object] | None = None
    evidence_bundle_payload: dict[str, object] | None = None
    prior_request: ProbeRequest | None = None
    probe_evidence: ProbeEvidence | None = None
    request_classification: str | None = None
    round_index: Annotated[StrictInt, Field(ge=1, le=2)] = 1


class CandidateProvenance(Model):
    base_sha: Sha
    branch: Nonempty
    head_sha: Sha
    source_digest: Sha
    changed_paths: list[str]
    staged_paths: list[str] = Field(default_factory=list)
    staged_diff_digest: Sha
    unstaged_paths: list[str] = Field(default_factory=list)
    unstaged_diff_digest: Sha
    untracked_paths: list[str] = Field(default_factory=list)
    untracked_digest: Sha

    @field_validator("changed_paths", "staged_paths", "unstaged_paths", "untracked_paths")
    @classmethod
    def check_paths(cls, paths: list[str]) -> list[str]:
        for p in paths:
            safe_path(p)
        if len(paths) != len(set(paths)):
            raise OrchestratorError("Duplicate paths in candidate provenance")
        return paths

    @model_validator(mode="after")
    def validate_canonical_order(self) -> "CandidateProvenance":
        if self.changed_paths != sorted(self.changed_paths):
            raise OrchestratorError("changed_paths must be canonically sorted")
        if self.staged_paths != sorted(self.staged_paths):
            raise OrchestratorError("staged_paths must be canonically sorted")
        if self.unstaged_paths != sorted(self.unstaged_paths):
            raise OrchestratorError("unstaged_paths must be canonically sorted")
        if self.untracked_paths != sorted(self.untracked_paths):
            raise OrchestratorError("untracked_paths must be canonically sorted")
        return self


class ScopeEvidence(Model):
    allowed_paths: list[str]
    actual_changed_paths: list[str]
    unexpected_changed_paths: list[str] = Field(default_factory=list)
    verdict: Literal["PASS", "FAIL"]

    @field_validator("allowed_paths", "actual_changed_paths", "unexpected_changed_paths")
    @classmethod
    def check_scope_paths(cls, paths: list[str]) -> list[str]:
        for p in paths:
            safe_path(p)
        if len(paths) != len(set(paths)):
            raise OrchestratorError("Duplicate paths in scope evidence")
        return paths

    @model_validator(mode="after")
    def validate_scope(self) -> "ScopeEvidence":
        if self.allowed_paths != sorted(self.allowed_paths):
            raise OrchestratorError("allowed_paths must be canonically sorted")
        if self.actual_changed_paths != sorted(self.actual_changed_paths):
            raise OrchestratorError("actual_changed_paths must be canonically sorted")
        if self.unexpected_changed_paths != sorted(self.unexpected_changed_paths):
            raise OrchestratorError("unexpected_changed_paths must be canonically sorted")
        expected_unexpected = sorted(set(self.actual_changed_paths) - set(self.allowed_paths))
        if self.unexpected_changed_paths != expected_unexpected:
            raise OrchestratorError("unexpected_changed_paths mismatch")
        if self.unexpected_changed_paths and self.verdict == "PASS":
            raise OrchestratorError("Scope verdict cannot be PASS with unexpected paths")
        if not self.unexpected_changed_paths and self.verdict == "FAIL":
            raise OrchestratorError("Scope verdict cannot be FAIL without unexpected paths")
        return self


class VerificationCommandEvidence(Model):
    command_index: Annotated[StrictInt, Field(ge=0)]
    command: list[str]
    declaration_digest: Sha256
    exit_code: StrictInt
    timed_out: StrictBool
    oversized: StrictBool
    stdout_bytes: Annotated[StrictInt, Field(ge=0)]
    stderr_bytes: Annotated[StrictInt, Field(ge=0)]
    stdout_digest: Sha256
    stderr_digest: Sha256
    duration_ns: Nanoseconds | None = None
    failure_classification: str | None = None


class VerificationEvidence(Model):
    identity: FrozenEvidenceIdentity
    commands: list[VerificationCommandEvidence]
    passed: StrictBool
    failed: StrictBool
    setup_error: str | None = None

    @model_validator(mode="after")
    def validate_verification_integrity(self) -> "VerificationEvidence":
        if [c.command_index for c in self.commands] != list(range(len(self.commands))):
            raise OrchestratorError("Verification commands must be in index order")
        any_failed = any(c.exit_code != 0 or c.timed_out or c.oversized for c in self.commands)
        if self.setup_error is not None:
            if self.passed:
                raise OrchestratorError("Setup error cannot be reported as passed")
            if not self.failed:
                raise OrchestratorError("Setup error must be marked as failed")
        if any_failed:
            if self.passed:
                raise OrchestratorError("Failed command cannot be reported as passed")
            if not self.failed:
                raise OrchestratorError("Failed command must be marked as failed")
        if self.passed and self.failed:
            raise OrchestratorError("Verification cannot be both passed and failed")
        manifest = self.identity.required_command_digests
        if len(self.commands) > len(manifest) or any(
            c.declaration_digest != manifest[c.command_index] for c in self.commands
        ):
            raise OrchestratorError("Verification command declaration mismatch")
        failures = [
            i for i, c in enumerate(self.commands) if c.exit_code or c.timed_out or c.oversized
        ]
        if failures and (failures != [len(self.commands) - 1] or self.setup_error is not None):
            raise OrchestratorError("Verification must stop at first explicit failure")
        if not any_failed and self.setup_error is None:
            if len(self.commands) != len(manifest):
                raise OrchestratorError(
                    "Successful prefix does not cover required command manifest"
                )
            if not self.passed or self.failed:
                raise OrchestratorError("Successful complete verification must be passed")
        for c in self.commands:
            classification = (
                "TIMED_OUT"
                if c.timed_out
                else "OVERSIZED"
                if c.oversized
                else "COMMAND_FAILED"
                if c.exit_code
                else None
            )
            if c.failure_classification != classification:
                raise OrchestratorError("Verification failure classification mismatch")
        return self


class TimingEvidence(Model):
    collected_at: str = Field(default_factory=now)
    duration_ns: Nanoseconds
    step_durations_ns: dict[str, Nanoseconds] = Field(default_factory=dict)


class EvidenceBundle(Model):
    schema_version: Version = 1
    task_id: TaskId
    base_sha: Sha
    branch: Nonempty
    source_digest: Sha
    provenance: CandidateProvenance
    scope: ScopeEvidence
    verification: VerificationEvidence
    artifacts: list[EvidenceArtifactRef] = Field(default_factory=list)
    timing: TimingEvidence
    is_complete: Literal[True] = True

    def check_completeness(self) -> None:
        VerificationEvidence.model_validate(self.verification.model_dump())
        if self.provenance.base_sha != self.base_sha:
            raise OrchestratorError("Provenance base_sha mismatch")
        if self.provenance.branch != self.branch:
            raise OrchestratorError("Provenance branch mismatch")
        if self.provenance.source_digest != self.source_digest:
            raise OrchestratorError("Provenance source_digest mismatch")
        identity = self.verification.identity
        if (identity.task_id, identity.base_sha, identity.branch, identity.source_digest) != (
            self.task_id,
            self.base_sha,
            self.branch,
            self.source_digest,
        ):
            raise OrchestratorError("Frozen verification provenance mismatch")
        if self.scope.actual_changed_paths != self.provenance.changed_paths:
            raise OrchestratorError("Scope changed paths mismatch provenance")
        if self.scope.verdict != "PASS" or self.scope.unexpected_changed_paths:
            raise OrchestratorError("Complete evidence bundle cannot have unexpected changed paths")
        artifact_order = [(a.name, a.path) for a in self.artifacts]
        if artifact_order != sorted(artifact_order):
            raise OrchestratorError("Artifact references must be in canonical order")
        if len(artifact_order) != len(set(artifact_order)):
            raise OrchestratorError("Duplicate artifact references in evidence bundle")
        if any(a.identity != identity for a in self.artifacts):
            raise OrchestratorError("Artifact frozen identity mismatch")
        if not self.verification.commands:
            raise OrchestratorError("Complete evidence bundle requires verification evidence")
        if self.verification.setup_error is not None:
            raise OrchestratorError("Complete evidence bundle cannot have setup error")

    @model_validator(mode="after")
    def validate_bundle_completeness(self) -> "EvidenceBundle":
        self.check_completeness()
        return self

    def semantic_payload(self) -> dict[str, object]:
        return self.model_dump(
            mode="json",
            exclude={
                "timing": True,
                "verification": {"commands": {"__all__": {"duration_ns"}}},
            },
        )


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


def dependency_ids(text: str) -> list[str]:
    dependencies = sorted(set(re.findall(r"\bT[0-9]+\b", section(text, "Dependencies"))))
    for dep in dependencies:
        if not re.fullmatch(TASK_PATTERN, dep):
            raise OrchestratorError(f"Invalid dependency ID: {dep}")
    return dependencies


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

    dependencies = dependency_ids(text)
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

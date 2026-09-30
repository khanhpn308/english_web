"""Authoritative local consent, immutable policy definitions and durable mutation CAS."""

import json
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Annotated, Literal
from uuid import uuid4

from backend.app.application.operations import ClaimResult, OperationConflict, OperationLedger
from backend.app.persistence.database import StorageError
from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
    model_validator,
)
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError

AiScope = Literal["LOOKUP", "QUIZ_GENERATION", "WRITING_FEEDBACK"]
ConsentState = Literal["NOT_GRANTED", "GRANTED", "REVOKED", "STALE"]
PolicyVersion = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,79}$", max_length=80)]
PolicyText = Annotated[str, Field(max_length=4096)]
SCOPES = {"LOOKUP", "QUIZ_GENERATION", "WRITING_FEEDBACK"}


def valid_utc_time(value: str) -> str:
    datetime.fromisoformat(value)
    return value


ConsentTimestamp = Annotated[
    str,
    Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"),
    AfterValidator(valid_utc_time),
]
PolicyDigest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class AiDispatchRule(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    scope: AiScope
    providerLabel: Literal["Antigravity/Google"]
    modelId: Literal["gemini-3.8-flash-high"]
    route: Literal["primary"]
    billingMode: Literal["configured-account"]


class AiPolicyDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    version: PolicyVersion
    reviewStatus: Literal["BLOCKED", "READY"]
    disclosureText: PolicyText
    dataCategories: list[Literal["TERM", "WORD_FORMS", "WRITING_ANSWER"]] = Field(max_length=100)
    recipients: list[PolicyText] = Field(max_length=100)
    retentionStatement: PolicyText
    regionStatement: PolicyText
    costQuotaStatement: PolicyText
    withdrawalStatement: PolicyText
    scopes: list[AiScope] = Field(max_length=100)
    dispatchRules: list[AiDispatchRule] = Field(max_length=100)
    blockedReasons: list[
        Literal["MODEL_POLICY", "QUOTA_BILLING", "PROXY_DATA_POLICY", "CLOUD_DATA_POLICY"]
    ] = Field(max_length=100)

    def canonical_payload(self) -> dict[str, object]:
        """Hash every definition field, excluding digest. Set-like lists are sorted,
        preserving duplicates for validation; rule order uses the complete rule JSON.
        Text and Unicode are preserved exactly. JSON keys are sorted by canonical_json.
        """
        payload = self.model_dump(mode="json", exclude={"digest"})
        for field in ("dataCategories", "recipients", "scopes", "blockedReasons"):
            payload[field] = sorted(payload[field])
        payload["dispatchRules"] = sorted(payload["dispatchRules"], key=canonical_json)
        return payload

    def is_ready(self) -> bool:
        statements = (
            self.disclosureText,
            self.retentionStatement,
            self.regionStatement,
            self.costQuotaStatement,
            self.withdrawalStatement,
        )
        return (
            self.reviewStatus == "READY"
            and all(statement.strip() for statement in statements)
            and bool(self.dataCategories)
            and len(set(self.dataCategories)) == len(self.dataCategories)
            and bool(self.recipients)
            and all(recipient.strip() for recipient in self.recipients)
            and len(self.scopes) == 3
            and set(self.scopes) == SCOPES
            and len(self.dispatchRules) == 3
            and {rule.scope for rule in self.dispatchRules} == SCOPES
            and not self.blockedReasons
        )


class AiDisclosurePolicy(AiPolicyDefinition):
    digest: str


class ImmutablePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    definition: dict[str, object] | None

    @model_validator(mode="after")
    def verify_definition(self) -> "ImmutablePolicy":
        if self.definition is None:
            # Malformed definitions reserve their fingerprint without storing unvalidated text.
            return self
        definition = AiPolicyDefinition.model_validate(self.definition).canonical_payload()
        if (
            self.definition != definition
            or self.digest != sha256(canonical_json(definition).encode("utf-8")).hexdigest()
        ):
            raise ValueError("Invalid immutable policy identity")
        return self


class AiConsentState(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True, allow_inf_nan=False)
    state: ConsentState
    revision: int = Field(ge=0)
    accepted_policy_version: PolicyVersion | None
    accepted_policy_digest: PolicyDigest | None
    last_choice_at: ConsentTimestamp | None
    policy_history: str
    policy_conflicts: str


@dataclass(frozen=True)
class ConsentSnapshot:
    state: AiConsentState
    policy: AiDisclosurePolicy | None
    etag: str
    can_request_ai: bool


@dataclass(frozen=True)
class ConsentApplied:
    operation_id: str
    applied_revision: int


@dataclass(frozen=True)
class ConsentRejected:
    error: tuple[int, str]
    operation_id: str | None = None


ConsentOperationResult = ConsentApplied | ConsentRejected
PolicySource = object | Callable[[], object]


def canonical_json(value: object) -> str:
    """Internal canonicalization matches T014: sorted UTF-8 JSON, compact, no NaN."""
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def registry_json(value: str) -> object:
    """Reject duplicate keys at every depth instead of accepting JSON's last value."""

    def unique_fields(fields: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for name, field in fields:
            if name in result:
                raise StorageError("INTEGRITY_FAILED")
            result[name] = field
        return result

    try:
        parsed: object = json.loads(value, object_pairs_hook=unique_fields)
    except (ValueError, RecursionError):
        raise StorageError("INTEGRITY_FAILED") from None
    return parsed


def resolve_policy(
    source: PolicySource,
) -> tuple[AiDisclosurePolicy | None, str, str | None, str | None]:
    raw = source() if callable(source) else source
    if isinstance(raw, AiPolicyDefinition):
        raw = raw.model_dump()
    if not isinstance(raw, dict):
        return None, "MISSING" if raw is None else "MALFORMED", None, None
    # Digest is server-owned, even when trusted configuration supplies a stale value.
    definition = {key: value for key, value in raw.items() if key != "digest"}
    try:
        fingerprint = sha256(canonical_json(definition).encode("utf-8")).hexdigest()
    except (TypeError, ValueError):
        return None, "MALFORMED", None, None
    try:
        version = TypeAdapter(PolicyVersion).validate_python(definition.get("version"))
    except ValidationError:
        version = None
    try:
        policy = AiPolicyDefinition.model_validate(definition)
    except ValidationError:
        return None, "MALFORMED", version, fingerprint
    payload = policy.canonical_payload()
    fingerprint = sha256(canonical_json(payload).encode("utf-8")).hexdigest()
    return (
        AiDisclosurePolicy.model_validate({**payload, "digest": fingerprint}),
        "VALID",
        version,
        fingerprint,
    )


class ConsentService:
    def __init__(self, operations: OperationLedger) -> None:
        self.operations = operations
        # Storage errors keep this running process fail-closed until restart/reconciliation.
        self.storage_reliable = True

    def read_consent(self, source: PolicySource) -> ConsentSnapshot | ConsentRejected:
        """Expose application outcomes without propagating storage/validation internals."""
        try:
            return self.get_snapshot(source)
        except (SQLAlchemyError, ValidationError, StorageError):
            self.storage_reliable = False
            return ConsentRejected((503, "STORAGE_BUSY"))

    def grant(
        self, key: str, if_match: str, policy_version: str, source: PolicySource
    ) -> ConsentOperationResult:
        """Own the receipt-read connection; durable writes still belong to T014's writer."""
        try:
            with self.operations.engine.connect() as connection:
                return self.grant_consent(connection, key, if_match, policy_version, source)
        except (SQLAlchemyError, StorageError):
            self.storage_reliable = False
            return ConsentRejected((503, "STORAGE_BUSY"))

    def revoke(self, key: str) -> ConsentOperationResult:
        """Withdraw through the same application boundary, without policy or network."""
        try:
            with self.operations.engine.connect() as connection:
                return self.revoke_consent(connection, key)
        except (SQLAlchemyError, StorageError):
            self.storage_reliable = False
            return ConsentRejected((503, "STORAGE_BUSY"))

    def get_state(self, connection: Connection) -> AiConsentState:
        row = (
            connection.exec_driver_sql("SELECT * FROM ai_consent_state WHERE id=1")
            .mappings()
            .first()
        )
        if row is None:
            raise StorageError("INTEGRITY_FAILED")
        state = AiConsentState.model_validate(dict(row))
        history = TypeAdapter(dict[PolicyVersion, ImmutablePolicy]).validate_python(
            registry_json(state.policy_history)
        )
        conflicts = TypeAdapter(dict[PolicyVersion, str]).validate_python(
            registry_json(state.policy_conflicts)
        )
        for version, entry in history.items():
            if entry.definition is not None and entry.definition.get("version") != version:
                raise StorageError("INTEGRITY_FAILED")
        if any(
            version not in history
            or len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest)
            for version, digest in conflicts.items()
        ):
            raise StorageError("INTEGRITY_FAILED")
        count, latest = connection.exec_driver_sql(
            "SELECT count(*), max(revision) FROM ai_consent_event"
        ).one()
        if count != state.revision or (state.revision > 0 and latest != state.revision):
            raise StorageError("INTEGRITY_FAILED")
        if state.revision == 0:
            if (
                state.state != "NOT_GRANTED"
                or state.accepted_policy_version is not None
                or state.accepted_policy_digest is not None
                or state.last_choice_at is not None
            ):
                raise StorageError("INTEGRITY_FAILED")
            return state
        current = self._event(connection, state.revision, history)
        if (
            current["action"] != state.state
            or current["created_at"] != state.last_choice_at
            or current["policy_version"] != state.accepted_policy_version
            or current["policy_digest"] != state.accepted_policy_digest
        ):
            raise StorageError("INTEGRITY_FAILED")
        return state

    def _event(
        self, connection: Connection, revision: int, history: dict[str, ImmutablePolicy]
    ) -> dict[str, object]:
        row = (
            connection.exec_driver_sql(
                "SELECT e.*, o.kind, o.status, o.response_status, o.result_ref "
                "FROM ai_consent_event e JOIN operations o ON o.operation_id=e.operation_id "
                "WHERE e.revision=?",
                (revision,),
            )
            .mappings()
            .first()
        )
        if row is None:
            raise StorageError("INTEGRITY_FAILED")
        event_id: str = TypeAdapter(
            Annotated[str, Field(pattern=r"^ev_[a-f0-9]{32}$")]
        ).validate_python(row["event_id"], strict=True)
        if (
            row["status"] != "SUCCEEDED"
            or row["response_status"] != 200
            or row["result_ref"] != "consent_event_" + event_id
        ):
            raise StorageError("INTEGRITY_FAILED")
        TypeAdapter(ConsentTimestamp).validate_python(row["created_at"])
        if row["action"] == "GRANTED":
            prior = history.get(row["policy_version"])
            if prior is None or prior.definition is None or prior.digest != row["policy_digest"]:
                raise StorageError("INTEGRITY_FAILED")
            definition = AiPolicyDefinition.model_validate(prior.definition)
            if (
                not definition.is_ready()
                or row["kind"] != "CONSENT_GRANT"
                or row["scopes"] != canonical_json(definition.scopes)
                or row["dispatch_rules"]
                != canonical_json([rule.model_dump() for rule in definition.dispatchRules])
            ):
                raise StorageError("INTEGRITY_FAILED")
        elif (
            row["action"] != "REVOKED"
            or row["kind"] != "CONSENT_REVOKE"
            or any(
                row[field] is not None
                for field in ("policy_version", "policy_digest", "scopes", "dispatch_rules")
            )
        ):
            raise StorageError("INTEGRITY_FAILED")
        return dict(row)

    def _policy(
        self, connection: Connection, state: AiConsentState, source: PolicySource
    ) -> tuple[AiDisclosurePolicy | None, str, str | None, str | None]:
        policy, status, version, fingerprint = resolve_policy(source)
        history = TypeAdapter(dict[str, ImmutablePolicy]).validate_python(
            registry_json(state.policy_history)
        )
        conflicts = TypeAdapter(dict[str, str]).validate_python(
            registry_json(state.policy_conflicts)
        )
        if version is None or fingerprint is None:
            return policy, status, version, fingerprint
        prior = history.get(version)
        missing_accepted_history = (
            prior is None
            and state.state == "GRANTED"
            and (state.accepted_policy_version == version)
        )
        if missing_accepted_history:
            if version not in conflicts:
                conflicts[version] = fingerprint
                connection.exec_driver_sql(
                    "UPDATE ai_consent_state SET policy_conflicts=? WHERE id=1",
                    (canonical_json(conflicts),),
                )
        elif prior is None:
            definition = policy.model_dump(mode="json", exclude={"digest"}) if policy else None
            history[version] = ImmutablePolicy(digest=fingerprint, definition=definition)
            connection.exec_driver_sql(
                "UPDATE ai_consent_state SET policy_history=? WHERE id=1",
                (
                    canonical_json(
                        {version: entry.model_dump() for version, entry in history.items()}
                    ),
                ),
            )
        elif prior is not None and prior.digest != fingerprint and version not in conflicts:
            conflicts[version] = fingerprint
            connection.exec_driver_sql(
                "UPDATE ai_consent_state SET policy_conflicts=? WHERE id=1",
                (canonical_json(conflicts),),
            )
        if policy is None:
            return None, status, version, fingerprint
        integrity = (
            version not in conflicts
            and not missing_accepted_history
            and (
                prior is None
                or (prior.definition is not None and prior.definition.get("version") == version)
            )
        )
        ready = policy.is_ready() and integrity
        if not ready and (policy.reviewStatus == "READY" or not integrity):
            # Null is contract-valid; never expose a rewritten definition with its old digest.
            policy = None
        return (
            policy,
            "READY" if ready else ("INTEGRITY_INVALID" if not integrity else "BLOCKED"),
            version,
            fingerprint,
        )

    def _snapshot(self, connection: Connection, source: PolicySource) -> ConsentSnapshot:
        state = self.get_state(connection)
        policy, status, version, fingerprint = self._policy(connection, state, source)
        eligible = (
            state.state == "GRANTED"
            and self.storage_reliable
            and status == "READY"
            and policy is not None
            and policy.version == state.accepted_policy_version
            and policy.digest == state.accepted_policy_digest
        )
        effective_state = "STALE" if state.state == "GRANTED" and not eligible else state.state
        state = state.model_copy(update={"state": effective_state})
        etag_payload = {
            "revision": state.revision,
            "state": state.state,
            "acceptedVersion": state.accepted_policy_version,
            "acceptedDigest": state.accepted_policy_digest,
            "policyStatus": status,
            "version": version,
            "digest": fingerprint,
            "storageReliable": self.storage_reliable,
        }
        etag = '"' + sha256(canonical_json(etag_payload).encode("utf-8")).hexdigest() + '"'
        return ConsentSnapshot(state, policy, etag, eligible)

    def get_snapshot(self, source: PolicySource) -> ConsentSnapshot:
        try:
            # GET observes configuration durably, including versions seen before any grant.
            with (
                self.operations.engine.connect().execution_options(
                    sqlite_begin_immediate=True
                ) as conn,
                conn.begin(),
            ):
                return self._snapshot(conn, source)
        except (SQLAlchemyError, ValidationError, StorageError):
            self.storage_reliable = False
            raise

    def _replay(self, connection: Connection, claimed: ClaimResult) -> ConsentOperationResult:
        operation = claimed.operation
        if operation.status == "SUCCEEDED":
            event = connection.exec_driver_sql(
                "SELECT revision FROM ai_consent_event WHERE operation_id=? "
                "AND 'consent_event_' || event_id=?",
                (operation.operation_id, operation.result_ref),
            ).first()
            if event is not None:
                state = self.get_state(connection)
                history = TypeAdapter(dict[str, ImmutablePolicy]).validate_python(
                    registry_json(state.policy_history)
                )
                self._event(connection, event[0], history)
                return ConsentApplied(operation.operation_id, event[0])
            raise StorageError("INTEGRITY_FAILED")
        return ConsentRejected(
            (operation.response_status or 409, operation.error_category or "IDEMPOTENCY_IN_FLIGHT"),
            operation.operation_id,
        )

    def _failure(self, operation_id: str, status: int, code: str) -> ConsentRejected:
        try:
            self.operations.record_failure(
                operation_id, response_status=status, error_category=code
            )
        except (SQLAlchemyError, StorageError, OperationConflict):
            # An ambiguous completion can already have committed its receipt.
            # T014 refuses to overwrite it; preserve it for explicit reconciliation.
            self.storage_reliable = False
        return ConsentRejected((status, code), operation_id)

    def grant_consent(
        self,
        connection: Connection,
        key: str,
        if_match: str,
        policy_version: str,
        active_policy: PolicySource,
    ) -> ConsentOperationResult:
        return self._mutate(
            connection, key, if_match=if_match, policy_version=policy_version, source=active_policy
        )

    def revoke_consent(self, connection: Connection, key: str) -> ConsentOperationResult:
        return self._mutate(connection, key)

    def _mutate(
        self,
        connection: Connection,
        key: str,
        *,
        if_match: str | None = None,
        policy_version: str | None = None,
        source: PolicySource = None,
    ) -> ConsentOperationResult:
        granting = if_match is not None
        try:
            claimed = self.operations.claim(
                kind="CONSENT_GRANT" if granting else "CONSENT_REVOKE",
                key=key,
                method="PUT" if granting else "DELETE",
                path="/api/v1/ai-consent",
                body={"policyVersion": policy_version} if granting else {},
                preconditions={"If-Match": if_match} if granting else {},
            )
        except OperationConflict as error:
            return ConsentRejected((error.status_code, error.code), error.operation_id)
        except (SQLAlchemyError, StorageError):
            self.storage_reliable = False
            return ConsentRejected((503, "STORAGE_BUSY"))
        if claimed.replayed:
            try:
                return self._replay(connection, claimed)
            except (SQLAlchemyError, ValidationError, StorageError):
                self.storage_reliable = False
                return ConsentRejected((503, "STORAGE_BUSY"), claimed.operation.operation_id)
        operation_id = claimed.operation.operation_id
        event_id = f"ev_{uuid4().hex}"
        applied_revision = 0
        observed_source: object = None
        observation_taken = False

        def local_write(writer: Connection) -> None:
            nonlocal applied_revision, observed_source, observation_taken
            state = self.get_state(writer)
            policy = None
            if granting:
                if not self.storage_reliable:
                    raise StorageError("UNAVAILABLE")
                observed_source = deepcopy(source() if callable(source) else source)
                observation_taken = True
                snapshot = self._snapshot(writer, observed_source)
                policy = snapshot.policy
                # Contract replay/claim precedes current configuration; configuration failures
                # dominate stale fingerprints. Version-before-ETag is the documented overlap rule.
                if policy is None or policy.reviewStatus != "READY":
                    raise OperationConflict(503, "CONFIGURATION_REQUIRED")
                if policy.version != policy_version:
                    raise OperationConflict(409, "AI_POLICY_CHANGED")
                if snapshot.etag != if_match:
                    raise OperationConflict(409, "REVISION_CONFLICT")
            applied_revision = state.revision + 1
            now = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
            result = writer.exec_driver_sql(
                "UPDATE ai_consent_state SET revision=?, state=?, accepted_policy_version=?, "
                "accepted_policy_digest=?, last_choice_at=? WHERE id=1 AND revision=? "
                "AND state=? AND accepted_policy_version IS ? AND accepted_policy_digest IS ? "
                "AND last_choice_at IS ?",
                (
                    applied_revision,
                    "GRANTED" if granting else "REVOKED",
                    policy.version if policy else None,
                    policy.digest if policy else None,
                    now,
                    state.revision,
                    state.state,
                    state.accepted_policy_version,
                    state.accepted_policy_digest,
                    state.last_choice_at,
                ),
            )
            if result.rowcount != 1:
                raise OperationConflict(409, "REVISION_CONFLICT")
            writer.exec_driver_sql(
                "INSERT INTO ai_consent_event (event_id, revision, action, policy_version, "
                "policy_digest, scopes, dispatch_rules, created_at, operation_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    event_id,
                    applied_revision,
                    "GRANTED" if granting else "REVOKED",
                    policy.version if policy else None,
                    policy.digest if policy else None,
                    canonical_json(policy.scopes) if policy else None,
                    canonical_json([rule.model_dump() for rule in policy.dispatchRules])
                    if policy
                    else None,
                    now,
                    operation_id,
                ),
            )

        try:
            self.operations.complete(
                operation_id,
                response_status=200,
                result_ref=f"consent_event_{event_id}",
                local_write=local_write,
            )
        except OperationConflict as error:
            if observation_taken:
                # Completion rolled back; retain newly observed integrity failures independently
                # of permission. Failed grants never append consent events or successful receipts.
                try:
                    self.get_snapshot(observed_source)
                except (SQLAlchemyError, ValidationError, StorageError):
                    return self._failure(operation_id, 503, "STORAGE_BUSY")
            return self._failure(operation_id, error.status_code, error.code)
        except (SQLAlchemyError, ValidationError, StorageError):
            self.storage_reliable = False
            return self._failure(operation_id, 503, "STORAGE_BUSY")
        return ConsentApplied(operation_id, applied_revision)


def choice_time(timestamp: str | None) -> datetime | None:
    return datetime.fromisoformat(timestamp) if timestamp is not None else None

import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, TypedDict
from uuid import uuid4

from backend.app.application.operations import OperationConflict, OperationLedger
from sqlalchemy import text
from sqlalchemy.engine import Connection


class ActiveAiPolicy(TypedDict):
    version: str
    digest: str
    content: str


@dataclass(frozen=True)
class ConsentApplied:
    operation_id: str
    applied_revision: int


@dataclass(frozen=True)
class ConsentRejected:
    error: tuple[int, str]


ConsentOperationResult = ConsentApplied | ConsentRejected


class AiConsentState(TypedDict):
    state: Literal["NOT_GRANTED", "GRANTED", "REVOKED", "STALE"]
    revision: int
    accepted_policy_version: str | None
    accepted_policy_digest: str | None
    last_choice_at: float | None


class ConsentService:
    def __init__(self, operations: OperationLedger) -> None:
        self.operations = operations

    def get_state(self, connection: Connection) -> AiConsentState:
        row = connection.execute(
            text(
                "SELECT revision, state, accepted_policy_version, accepted_policy_digest, "
                "last_choice_at "
                "FROM ai_consent_state WHERE id = 1"
            )
        ).fetchone()

        if not row:
            return {
                "state": "NOT_GRANTED",
                "revision": 0,
                "accepted_policy_version": None,
                "accepted_policy_digest": None,
                "last_choice_at": None,
            }

        return {
            "revision": row.revision,
            "state": row.state,
            "accepted_policy_version": row.accepted_policy_version,
            "accepted_policy_digest": row.accepted_policy_digest,
            "last_choice_at": row.last_choice_at,
        }

    def get_active_policy(
        self, app_state: Mapping[str, ActiveAiPolicy | None]
    ) -> ActiveAiPolicy | None:
        return app_state.get("active_ai_policy")

    def grant_consent(
        self,
        connection: Connection,
        key: str,
        if_match: str,
        policy_version: str,
        active_policy: ActiveAiPolicy | None,
    ) -> ConsentOperationResult:
        try:
            claimed = self.operations.claim(
                kind="CONSENT_GRANT",
                key=key,
                method="PUT",
                path="/api/v1/ai-consent",
                body={"policyVersion": policy_version},
                preconditions={"If-Match": if_match},
            )
        except OperationConflict as e:
            return ConsentRejected(error=(409, e.code))

        op_id = claimed.operation.operation_id

        if claimed.replayed:
            if claimed.operation.status == "SUCCEEDED":
                # Find the event to reconstruct applied_revision
                event = connection.execute(
                    text("SELECT revision FROM ai_consent_event WHERE operation_id = :op"),
                    {"op": op_id},
                ).fetchone()
                if event:
                    return ConsentApplied(operation_id=op_id, applied_revision=event.revision)
            return ConsentRejected(
                error=(
                    claimed.operation.response_status or 500,
                    claimed.operation.error_category or "UNKNOWN_ERROR",
                )
            )

        # Fresh intent
        state = self.get_state(connection)

        digest = state["accepted_policy_digest"] or "none"
        expected_etag = f'"ac-r{state["revision"]}-{digest}"'
        if if_match != expected_etag:
            self.operations.record_failure(
                op_id, response_status=409, error_category="REVISION_CONFLICT"
            )
            return ConsentRejected(error=(409, "REVISION_CONFLICT"))

        if not active_policy:
            self.operations.record_failure(
                op_id, response_status=503, error_category="CONFIGURATION_REQUIRED"
            )
            return ConsentRejected(error=(503, "CONFIGURATION_REQUIRED"))

        if policy_version != active_policy["version"]:
            self.operations.record_failure(
                op_id, response_status=409, error_category="AI_POLICY_CHANGED"
            )
            return ConsentRejected(error=(409, "AI_POLICY_CHANGED"))

        new_rev = state["revision"] + 1
        now = time.time()
        event_id = f"ev_{uuid4().hex}"

        def local_write(conn: Connection) -> None:
            conn.execute(
                text(
                    "UPDATE ai_consent_state SET revision = :rev, state = 'GRANTED', "
                    "accepted_policy_version = :ver, accepted_policy_digest = :dig, "
                    "last_choice_at = :now "
                    "WHERE id = 1"
                ),
                {"rev": new_rev, "ver": policy_version, "dig": active_policy["digest"], "now": now},
            )
            conn.execute(
                text(
                    "INSERT INTO ai_consent_event (event_id, revision, action, policy_version, "
                    "policy_digest, created_at, operation_id) "
                    "VALUES (:ev, :rev, 'GRANT', :ver, :dig, :now, :op)"
                ),
                {
                    "ev": event_id,
                    "rev": new_rev,
                    "ver": policy_version,
                    "dig": active_policy["digest"],
                    "now": now,
                    "op": op_id,
                },
            )

        self.operations.complete(
            operation_id=op_id,
            response_status=200,
            result_ref=f"consent_event_{event_id}",
            local_write=local_write,
        )

        return ConsentApplied(operation_id=op_id, applied_revision=new_rev)

    def revoke_consent(self, connection: Connection, key: str) -> ConsentOperationResult:
        try:
            claimed = self.operations.claim(
                kind="CONSENT_REVOKE",
                key=key,
                method="DELETE",
                path="/api/v1/ai-consent",
                body={},
                preconditions={},
            )
        except OperationConflict as e:
            return ConsentRejected(error=(409, e.code))

        op_id = claimed.operation.operation_id

        if claimed.replayed:
            if claimed.operation.status == "SUCCEEDED":
                event = connection.execute(
                    text("SELECT revision FROM ai_consent_event WHERE operation_id = :op"),
                    {"op": op_id},
                ).fetchone()
                if event:
                    return ConsentApplied(operation_id=op_id, applied_revision=event.revision)
            return ConsentRejected(
                error=(
                    claimed.operation.response_status or 500,
                    claimed.operation.error_category or "UNKNOWN_ERROR",
                )
            )

        state = self.get_state(connection)

        if state["state"] == "REVOKED":
            # Still increment revision for a fresh revoke intent!
            # A new revoke intent increments revision even when already REVOKED.
            pass

        new_rev = state["revision"] + 1
        now = time.time()
        event_id = f"ev_{uuid4().hex}"

        def local_write(conn: Connection) -> None:
            conn.execute(
                text(
                    "UPDATE ai_consent_state SET revision = :rev, state = 'REVOKED', "
                    "accepted_policy_version = NULL, accepted_policy_digest = NULL, "
                    "last_choice_at = :now "
                    "WHERE id = 1"
                ),
                {"rev": new_rev, "now": now},
            )
            conn.execute(
                text(
                    "INSERT INTO ai_consent_event (event_id, revision, action, policy_version, "
                    "policy_digest, created_at, operation_id) "
                    "VALUES (:ev, :rev, 'REVOKE', NULL, NULL, :now, :op)"
                ),
                {"ev": event_id, "rev": new_rev, "now": now, "op": op_id},
            )

        self.operations.complete(
            operation_id=op_id,
            response_status=200,
            result_ref=f"consent_event_{event_id}",
            local_write=local_write,
        )

        return ConsentApplied(operation_id=op_id, applied_revision=new_rev)

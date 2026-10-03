"""Durable consent admission shared by the three AI use cases (T016)."""

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from math import isfinite
from time import monotonic
from typing import Any

from backend.app.application.consent import (
    SCOPES,
    AiDispatchRule,
    ConsentService,
    ConsentSnapshot,
    PolicySource,
)
from backend.app.application.operations import OperationConflict
from backend.app.persistence.database import StorageError
from backend.app.platform.bridge_port import BridgePort, BridgeProfile, BridgeUnavailableError
from pydantic import ValidationError
from sqlalchemy import Connection
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool


@dataclass(frozen=True)
class _Authorization:
    consent_revision: int
    policy_version: str
    policy_digest: str
    rule: AiDispatchRule


class AiAdmissionCoordinator:
    """Admit one already-claimed operation, then dispatch exactly once.

    Callers claim/reconcile intents through OperationLedger before entering this
    boundary and complete validated local results through that same ledger afterwards.
    Transport errors leave the operation PENDING for caller reconciliation or the
    ledger's conservative PENDING -> UNKNOWN restart recovery. Admission evidence
    never authorizes replay, including when transport failed or never sent bytes.
    """

    def __init__(
        self,
        consent: ConsentService,
        bridge: BridgePort,
        policy_source: PolicySource,
        *,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self.consent = consent
        self.bridge = bridge
        self.policy_source = policy_source
        self.clock = clock

    def _deadline(self, deadline: float) -> None:
        if not isfinite(deadline) or self.clock() >= deadline:
            raise BridgeUnavailableError("Operation deadline exceeded")

    @staticmethod
    def _pending(connection: Connection, operation_id: str, scope: str) -> None:
        row = connection.exec_driver_sql(
            "SELECT o.status, o.kind, a.operation_id FROM operations o "
            "LEFT JOIN ai_operation_admission a ON a.operation_id=o.operation_id "
            "WHERE o.operation_id=?",
            (operation_id,),
        ).first()
        if row is None:
            raise OperationConflict(404, "NOT_FOUND", operation_id)
        if row[0] != "PENDING" or row[2] is not None:
            raise OperationConflict(409, "IDEMPOTENCY_IN_FLIGHT", operation_id)
        if row[1] != scope:
            raise OperationConflict(422, "VALIDATION_ERROR", operation_id)

    @staticmethod
    def _capture(snapshot: ConsentSnapshot, scope: str, operation_id: str) -> _Authorization:
        policy = snapshot.policy
        if policy is None or not policy.is_ready():
            raise OperationConflict(503, "CONFIGURATION_REQUIRED", operation_id)
        if not snapshot.can_request_ai:
            raise OperationConflict(403, "AI_CONSENT_REQUIRED", operation_id)
        rule = next((rule for rule in policy.dispatchRules if rule.scope == scope), None)
        if rule is None:
            raise OperationConflict(403, "AI_CONSENT_REQUIRED", operation_id)
        return _Authorization(snapshot.state.revision, policy.version, policy.digest, rule)

    @staticmethod
    def _profile(profile: BridgeProfile, authorization: _Authorization, operation_id: str) -> None:
        rule = authorization.rule

        def validate(evidence: dict[str, Any]) -> None:
            expected = {
                "providerLabel": rule.providerLabel,
                "provider": "google",
                "owned_by": "google",
                "modelId": rule.modelId,
                "model": rule.modelId,
                "route": rule.route,
                "billingMode": rule.billingMode,
            }
            for field, value in expected.items():
                if field in evidence and evidence[field] != value:
                    raise OperationConflict(503, "CONFIGURATION_REQUIRED", operation_id)
            for field, value in evidence.items():
                if "fallback" in field.lower() and not (
                    value is None or value is False or value == []
                ):
                    raise OperationConflict(503, "CONFIGURATION_REQUIRED", operation_id)

        # The current T007 models profile names its provider with owned_by="google".
        # Optional rule metadata is evidence only; absent route/billing fields cannot
        # select a different rule. No claim about authenticated upstream identity is made.
        if len(profile.models) != 1:
            raise OperationConflict(503, "CONFIGURATION_REQUIRED", operation_id)
        model = profile.models[0]
        if (
            not isinstance(model, dict)
            or model.get("id") != rule.modelId
            or model.get("owned_by") != "google"
        ):
            raise OperationConflict(503, "CONFIGURATION_REQUIRED", operation_id)
        validate(model)
        if profile.raw_response is not None:
            validate(profile.raw_response)

    def _admit(self, operation_id: str, captured: _Authorization, deadline: float) -> None:
        rejection: OperationConflict | None = None
        with (
            self.consent.operations.engine.connect().execution_options(
                sqlite_begin_immediate=True
            ) as connection,
            connection.begin(),
        ):
            self._deadline(deadline)
            self._pending(connection, operation_id, captured.rule.scope)
            state = self.consent.get_state(connection)
            if state.state != "GRANTED" or state.revision != captured.consent_revision:
                raise OperationConflict(403, "AI_CONSENT_REQUIRED", operation_id)
            if (
                state.accepted_policy_version != captured.policy_version
                or state.accepted_policy_digest != captured.policy_digest
            ):
                raise OperationConflict(409, "AI_POLICY_CHANGED", operation_id)
            # Reuse T015's immutable policy loader inside this same writer. Commit
            # newly observed policy conflicts even when they deny this admission.
            snapshot = self.consent._snapshot(connection, self.policy_source)
            try:
                policy = snapshot.policy
                if policy is None or not policy.is_ready():
                    raise OperationConflict(503, "CONFIGURATION_REQUIRED", operation_id)
                if (
                    policy.version != captured.policy_version
                    or policy.digest != captured.policy_digest
                ):
                    raise OperationConflict(409, "AI_POLICY_CHANGED", operation_id)
                if self._capture(snapshot, captured.rule.scope, operation_id) != captured:
                    raise OperationConflict(409, "AI_POLICY_CHANGED", operation_id)
            except OperationConflict as error:
                rejection = error
            if rejection is None:
                self._deadline(deadline)
                now = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
                result = connection.exec_driver_sql(
                    "INSERT INTO ai_operation_admission (operation_id, consent_revision, "
                    "policy_version, policy_digest, scope, provider_label, model_id, route, "
                    "billing_mode, admission_state, admitted_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'ADMITTED', ?)",
                    (
                        operation_id,
                        captured.consent_revision,
                        captured.policy_version,
                        captured.policy_digest,
                        captured.rule.scope,
                        captured.rule.providerLabel,
                        captured.rule.modelId,
                        captured.rule.route,
                        captured.rule.billingMode,
                        now,
                    ),
                )
                if result.rowcount != 1:
                    raise StorageError("INTEGRITY_FAILED")
                self._deadline(deadline)
        if rejection is not None:
            raise rejection

    async def dispatch(
        self, *, operation_id: str, scope: str, payload: dict[str, Any], deadline: float
    ) -> dict[str, Any]:
        # Snapshot immediately before any await or validation
        # so caller mutation cannot inject fields
        frozen_payload = deepcopy(payload)
        self._deadline(deadline)
        if scope not in SCOPES:
            raise OperationConflict(403, "AI_CONSENT_REQUIRED", operation_id)
        if any(
            field.lower().replace("_", "")
            in {"model", "modelid", "provider", "providerlabel", "route", "billingmode"}
            or "fallback" in field.lower()
            for field in frozen_payload
        ):
            raise OperationConflict(422, "VALIDATION_ERROR", operation_id)
        if not self.consent.storage_reliable:
            raise OperationConflict(503, "STORAGE_BUSY", operation_id)

        from typing import Any

        def _pre_dispatch() -> Any:
            try:
                with self.consent.operations.engine.connect() as connection:
                    self._pending(connection, operation_id, scope)
                return self._capture(
                    self.consent.get_snapshot(self.policy_source), scope, operation_id
                )
            except (SQLAlchemyError, ValidationError, StorageError):
                self.consent.storage_reliable = False
                raise OperationConflict(503, "STORAGE_BUSY", operation_id) from None

        captured = await run_in_threadpool(_pre_dispatch)

        selected_payload = deepcopy(frozen_payload)
        selected_payload["model"] = captured.rule.modelId
        self._deadline(deadline)
        profile = await self.bridge.preflight(deadline)
        self._deadline(deadline)
        self._profile(profile, captured, operation_id)
        self._deadline(deadline)

        def _do_admit() -> None:
            try:
                if not self.consent.storage_reliable:
                    raise StorageError("UNAVAILABLE")
                self._admit(operation_id, captured, deadline)
            except (SQLAlchemyError, ValidationError, StorageError):
                self.consent.storage_reliable = False
                raise OperationConflict(503, "STORAGE_BUSY", operation_id) from None

        await run_in_threadpool(_do_admit)

        self._deadline(deadline)
        # No await or network call occurs in the admission transaction above.
        result = await self.bridge.dispatch_chat(selected_payload, deadline)
        self._deadline(deadline)
        return result

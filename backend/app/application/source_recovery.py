"""Deterministic startup reconciliation for source journal rows (T022)."""

from __future__ import annotations

from collections.abc import Sequence

from backend.app.adapters.source_files import SourceFileError
from backend.app.application.operations import OperationConflict, OperationLedger
from backend.app.application.source_write import (
    AmbiguousSourceStateError,
    CardReset,
    FaultInjector,
    JournalRecord,
    ProjectionApply,
    SourceWriteCoordinator,
    UnknownOperationError,
)
from backend.app.vocabulary.search_index import (
    ProjectionVersionMismatchError,
    StaleSourceRevisionError,
)


class SourceRecovery:
    """Reconcile durable journal evidence without guessing or overwriting bytes."""

    def __init__(self, coordinator: SourceWriteCoordinator) -> None:
        self.coordinator = coordinator

    def _degrade(self, operation_id: str) -> JournalRecord:
        return self.coordinator._transition(operation_id, "DEGRADED")

    def reconcile(
        self,
        *,
        operation_ledger: OperationLedger | None = None,
        response_status: int | None = None,
        result_ref: str | None = None,
        apply_projection: ProjectionApply | None = None,
        reset_cards: CardReset | None = None,
        fault: FaultInjector | None = None,
    ) -> list[JournalRecord]:
        """Reconcile non-terminal rows before admitting source writers at startup.

        Recovery is a startup/quiescent primitive, not a competing live writer.
        The supplied receipt parameters, when present, must match durable intent.
        """
        with self.coordinator.engine.connect() as connection:
            rows: Sequence[str] = (
                connection.exec_driver_sql(
                    "SELECT operation_id FROM source_write_journal "
                    "WHERE state IN ('PREPARED','SOURCE_REPLACED') ORDER BY created_at,operation_id"
                )
                .scalars()
                .all()
            )

        reconciled: list[JournalRecord] = []
        for operation_id in rows:
            journal = self.coordinator.get(str(operation_id))
            if journal is None or journal.state not in {"PREPARED", "SOURCE_REPLACED"}:
                continue
            try:
                actual_hash = self.coordinator.adapter.get_source_hash(journal.source_id)
            except SourceFileError:
                reconciled.append(self._degrade(journal.operation_id))
                continue

            if journal.state == "PREPARED" and actual_hash == journal.old_hash:
                try:
                    reconciled.append(self.coordinator._abort(journal, operation_ledger))
                except SourceFileError:
                    reconciled.append(self._degrade(journal.operation_id))
                except OperationConflict as error:
                    if error.code != "SOURCE_EVIDENCE_MISMATCH":
                        raise
                    reconciled.append(self._degrade(journal.operation_id))
                continue
            if actual_hash != journal.new_hash:
                reconciled.append(self._degrade(journal.operation_id))
                continue
            if journal.state == "PREPARED":
                journal = self.coordinator._transition(journal.operation_id, "SOURCE_REPLACED")
            try:
                reconciled.append(
                    self.coordinator._complete(
                        journal,
                        operation_ledger=operation_ledger,
                        response_status=response_status,
                        result_ref=result_ref,
                        apply_projection=apply_projection,
                        reset_cards=reset_cards,
                        fault=fault,
                    )
                )
            except (
                UnknownOperationError,
                AmbiguousSourceStateError,
                ProjectionVersionMismatchError,
                StaleSourceRevisionError,
            ):
                # Canonical/projection ambiguity is durable DEGRADED evidence.
                # No recovery path writes filesystem bytes or erases learning data.
                reconciled.append(self.coordinator.get(journal.operation_id) or journal)
        return reconciled

    def assert_writable(self, source_id: str) -> None:
        """Fail closed while a source has unresolved DEGRADED evidence."""
        with self.coordinator.engine.connect() as connection:
            degraded = connection.exec_driver_sql(
                "SELECT 1 FROM source_write_journal WHERE source_id=? AND state='DEGRADED'",
                (source_id,),
            ).first()
        if degraded is not None:
            raise RuntimeError("Source is degraded and requires explicit repair")

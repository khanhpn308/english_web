"""Durable idempotency claims and redacted operation receipts (T014)."""

import json
import re
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from secrets import token_urlsafe
from typing import Literal

from sqlalchemy import Connection, Engine

OperationStatus = Literal["PENDING", "SUCCEEDED", "FAILED", "UNKNOWN"]
_KIND = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z")
_RESULT_REF = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_ERROR_CATEGORY = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z")


@dataclass(frozen=True)
class OperationRecord:
    operation_id: str
    kind: str
    status: OperationStatus
    result_ref: str | None
    response_status: int | None
    error_category: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class ClaimResult:
    operation: OperationRecord
    replayed: bool


class OperationConflict(RuntimeError):
    """A typed refusal which never embeds an idempotency key or request body."""

    def __init__(self, status_code: int, code: str, operation_id: str | None = None) -> None:
        super().__init__(code)
        self.status_code = status_code
        self.code = code
        self.operation_id = operation_id


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _operation(connection: Connection, operation_id: str) -> OperationRecord | None:
    row = (
        connection.exec_driver_sql(
            "SELECT operation_id, kind, status, result_ref, response_status, error_category, "
            "created_at, updated_at FROM operations WHERE operation_id=?",
            (operation_id,),
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    return OperationRecord(
        operation_id=row["operation_id"],
        kind=row["kind"],
        status=row["status"],
        result_ref=row["result_ref"],
        response_status=row["response_status"],
        error_category=row["error_category"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class OperationLedger:
    """Use a short SQLite writer transaction for each durable state transition."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    @contextmanager
    def _writer(self) -> Iterator[Connection]:
        # T005's begin listener emits BEGIN IMMEDIATE before any read/claim.
        # Source: https://docs.sqlalchemy.org/en/21/core/connections.html#begin-once
        with (
            self.engine.connect().execution_options(sqlite_begin_immediate=True) as connection,
            connection.begin(),
        ):
            yield connection

    def claim(
        self,
        *,
        kind: str,
        key: str,
        method: str,
        path: str,
        body: Mapping[str, object],
        preconditions: Mapping[str, object],
    ) -> ClaimResult:
        """Claim one intent after caller validation; never perform the side effect here."""
        if _KIND.fullmatch(kind) is None:
            raise ValueError("Invalid operation kind")
        if not 1 <= len(key) <= 128 or any(not 32 <= ord(char) <= 126 for char in key):
            raise ValueError("Invalid idempotency key")
        key_digest = sha256(key.encode("ascii")).hexdigest()
        canonical = json.dumps(
            {
                "method": method.upper(),
                "path": path,
                "body": body,
                "preconditions": preconditions,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        request_digest = sha256(canonical.encode("utf-8")).hexdigest()

        with self._writer() as connection:
            existing = connection.exec_driver_sql(
                "SELECT request_digest, operation_id FROM operation_keys "
                "WHERE kind=? AND key_digest=?",
                (kind, key_digest),
            ).first()
            if existing is not None:
                operation_id = str(existing[1])
                if existing[0] != request_digest:
                    raise OperationConflict(422, "IDEMPOTENCY_KEY_REUSED")
                operation = _operation(connection, operation_id)
                if operation is None or operation.status in {"PENDING", "UNKNOWN"}:
                    raise OperationConflict(409, "IDEMPOTENCY_IN_FLIGHT", operation_id)
                if operation.status == "SUCCEEDED" and (
                    operation.result_ref is None or operation.response_status is None
                ):
                    raise OperationConflict(409, "IDEMPOTENCY_IN_FLIGHT", operation_id)
                if operation.status == "FAILED" and (
                    operation.error_category is None or operation.response_status is None
                ):
                    raise OperationConflict(409, "IDEMPOTENCY_IN_FLIGHT", operation_id)
                return ClaimResult(operation, replayed=True)

            operation_id = f"op_{token_urlsafe(18)}"
            created_at = _now()
            connection.exec_driver_sql(
                "INSERT INTO operations (operation_id, kind, status, created_at, updated_at) "
                "VALUES (?, ?, 'PENDING', ?, ?)",
                (operation_id, kind, created_at, created_at),
            )
            connection.exec_driver_sql(
                "INSERT INTO operation_keys (kind, key_digest, request_digest, operation_id) "
                "VALUES (?, ?, ?, ?)",
                (kind, key_digest, request_digest, operation_id),
            )
            operation = _operation(connection, operation_id)
            if operation is None:
                raise RuntimeError("Claim was not persisted")
            return ClaimResult(operation, replayed=False)

    @staticmethod
    def validate_receipt(response_status: int, result_ref: str) -> None:
        """Validate a receipt before any external mutation is attempted."""
        if not 200 <= response_status < 300 or _RESULT_REF.fullmatch(result_ref) is None:
            raise ValueError("Invalid operation receipt")

    def complete(
        self,
        operation_id: str,
        *,
        response_status: int,
        result_ref: str,
        local_write: Callable[[Connection], None] | None = None,
    ) -> OperationRecord:
        """Commit the local revision and immutable result reference together."""
        self.validate_receipt(response_status, result_ref)
        with self._writer() as connection:
            operation = _operation(connection, operation_id)
            if operation is None:
                raise OperationConflict(404, "NOT_FOUND")
            if operation.status == "SUCCEEDED":
                if operation.result_ref is None or operation.response_status is None:
                    raise OperationConflict(409, "IDEMPOTENCY_IN_FLIGHT", operation_id)
                return operation
            if operation.status != "PENDING":
                raise OperationConflict(409, "IDEMPOTENCY_IN_FLIGHT", operation_id)
            if local_write is not None:
                local_write(connection)
            connection.exec_driver_sql(
                "UPDATE operations SET status='SUCCEEDED', result_ref=?, response_status=?, "
                "updated_at=? WHERE operation_id=?",
                (result_ref, response_status, _now(), operation_id),
            )
            completed = _operation(connection, operation_id)
            if completed is None:
                raise RuntimeError("Receipt was not persisted")
            return completed

    def reconcile_source_write(
        self,
        operation_id: str,
        *,
        expected_new_hash: str,
        response_status: int,
        result_ref: str,
        local_write: Callable[[Connection], None],
    ) -> OperationRecord:
        """Finish only an UNKNOWN T022 write backed by durable replacement evidence.

        The caller must first verify the live source through T021. This method also
        verifies T022's journal and the post-callback local state in one transaction.
        It never redispatches a filesystem or network operation.
        """
        self.validate_receipt(response_status, result_ref)
        with self._writer() as connection:
            operation = _operation(connection, operation_id)
            if operation is None:
                raise OperationConflict(404, "NOT_FOUND")
            if operation.status != "UNKNOWN":
                raise OperationConflict(409, "IDEMPOTENCY_IN_FLIGHT", operation_id)
            journal = connection.exec_driver_sql(
                "SELECT source_id,new_hash,intended_projection_revision,state,"
                "response_status,result_ref "
                "FROM source_write_journal WHERE operation_id=?",
                (operation_id,),
            ).first()
            if (
                journal is None
                or journal.state != "SOURCE_REPLACED"
                or journal.new_hash != expected_new_hash
                or journal.response_status != response_status
                or journal.result_ref != result_ref
            ):
                raise OperationConflict(409, "SOURCE_EVIDENCE_MISMATCH", operation_id)
            local_write(connection)
            committed: str = connection.exec_driver_sql(
                "SELECT state FROM source_write_journal WHERE operation_id=?", (operation_id,)
            ).scalar_one()
            source = connection.exec_driver_sql(
                "SELECT content_hash,revision FROM source_files WHERE id=?",
                (journal.source_id,),
            ).first()
            if (
                committed != "COMMITTED"
                or source is None
                or source.content_hash != expected_new_hash
                or source.revision != journal.intended_projection_revision
            ):
                raise OperationConflict(409, "SOURCE_EVIDENCE_MISMATCH", operation_id)
            connection.exec_driver_sql(
                "UPDATE operations SET status='SUCCEEDED', result_ref=?, response_status=?, "
                "error_category=NULL, updated_at=? WHERE operation_id=?",
                (result_ref, response_status, _now(), operation_id),
            )
            completed = _operation(connection, operation_id)
            if completed is None:
                raise RuntimeError("Source receipt was not persisted")
            return completed

    def abort_source_write(self, operation_id: str, *, expected_old_hash: str) -> OperationRecord:
        """Record a proven unreplaced T022 intent and its failure atomically.

        Only startup reconciliation or the failed writer calls this after checking
        the old source through T021 and cleaning its owned staged material.
        """
        with self._writer() as connection:
            operation = _operation(connection, operation_id)
            if operation is None:
                raise OperationConflict(404, "NOT_FOUND")
            journal = connection.exec_driver_sql(
                "SELECT state,old_hash,source_id,intended_projection_revision "
                "FROM source_write_journal WHERE operation_id=?",
                (operation_id,),
            ).first()
            if operation.status not in {"PENDING", "UNKNOWN"} or journal is None:
                raise OperationConflict(409, "SOURCE_EVIDENCE_MISMATCH", operation_id)
            source = connection.exec_driver_sql(
                "SELECT content_hash,revision FROM source_files WHERE id=?", (journal.source_id,)
            ).first()
            if (
                journal.state != "PREPARED"
                or journal.old_hash != expected_old_hash
                or source is None
                or source.content_hash != expected_old_hash
                or source.revision + 1 != journal.intended_projection_revision
            ):
                raise OperationConflict(409, "SOURCE_EVIDENCE_MISMATCH", operation_id)
            connection.exec_driver_sql(
                "UPDATE source_write_journal SET state='ABORTED',updated_at=? WHERE operation_id=?",
                (_now(), operation_id),
            )
            connection.exec_driver_sql(
                "UPDATE operations SET status='FAILED',"
                "error_category='SOURCE_REPLACEMENT_ABORTED', "
                "response_status=409,updated_at=? WHERE operation_id=?",
                (_now(), operation_id),
            )
            result = _operation(connection, operation_id)
            if result is None:
                raise RuntimeError("Source abort was not persisted")
            return result

    def record_failure(
        self,
        operation_id: str,
        *,
        error_category: str,
        response_status: int,
        unknown: bool = False,
    ) -> OperationRecord:
        """Record a definite failure or uncertain external outcome without retrying."""
        if not 400 <= response_status <= 599 or _ERROR_CATEGORY.fullmatch(error_category) is None:
            raise ValueError("Invalid operation failure category")
        with self._writer() as connection:
            operation = _operation(connection, operation_id)
            if operation is None:
                raise OperationConflict(404, "NOT_FOUND")
            if operation.status in {"FAILED", "UNKNOWN"}:
                return operation
            if operation.status != "PENDING":
                raise OperationConflict(409, "IDEMPOTENCY_IN_FLIGHT", operation_id)
            connection.exec_driver_sql(
                "UPDATE operations SET status=?, error_category=?, response_status=?, "
                "updated_at=? WHERE operation_id=?",
                (
                    "UNKNOWN" if unknown else "FAILED",
                    error_category,
                    response_status,
                    _now(),
                    operation_id,
                ),
            )
            recorded = _operation(connection, operation_id)
            if recorded is None:
                raise RuntimeError("Failure was not persisted")
            return recorded

    def get(self, operation_id: str) -> OperationRecord | None:
        with self.engine.connect() as connection:
            return _operation(connection, operation_id)

    def recover_pending(self) -> int:
        """Fail closed after process restart; never re-dispatch an ambiguous intent."""
        with self._writer() as connection:
            result = connection.exec_driver_sql(
                "UPDATE operations SET status='UNKNOWN', error_category='RESTARTED', "
                "updated_at=? WHERE status='PENDING'",
                (_now(),),
            )
            return result.rowcount

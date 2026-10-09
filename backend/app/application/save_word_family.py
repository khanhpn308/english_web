"""Explicit, local save of a validated lookup through the source journal (T024).

No bridge/admission port belongs here. Only the journal acknowledges persistence;
its immutable planned receipt is the replay source, including after recovery.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date
from typing import Any

from backend.app.adapters.source_files import SourceFileError
from backend.app.application.operations import OperationConflict, OperationLedger
from backend.app.application.source_write import (
    FaultInjector,
    JournalBusyError,
    JournalConflictError,
    JournalError,
    SourceWriteCoordinator,
)
from backend.app.markdown_sync.parser import (
    MAX_SOURCE_SIZE_BYTES,
    StructuredFamily,
    normalize_lemma,
    parse_markdown,
    structured_semantics,
)
from backend.app.markdown_sync.serializer import upsert_structured_family
from backend.app.vocabulary.repository import (
    PreviewExpiredError,
    PreviewNotFoundError,
    PreviewOwnerMismatchError,
    VocabularyRepository,
)
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_DATE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")


class SaveConflict(OperationConflict):
    """Privacy-safe failure with optional canonical structured details."""

    def __init__(
        self, status: int, code: str, operation_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(status, code, operation_id)
        self.details = details


class SaveWordFamilyService:
    def __init__(self, ledger: OperationLedger, coordinator: SourceWriteCoordinator) -> None:
        if ledger.engine is not coordinator.engine:
            raise ValueError("Save and journal must share an engine")
        self.ledger = ledger
        self.coordinator = coordinator
        self.repository = VocabularyRepository(ledger.engine)
        self.fault: FaultInjector | None = None

    def save(
        self, *, lookup_id: str, note_date: str, owner_session_id: str,
        idempotency_key: str, source_id: str | None = None,
        source_revision: int | None = None, if_match: str | None = None,
        if_none_match: str | None = None,
    ) -> dict[str, Any]:
        self._validate_intent(
            lookup_id, note_date, source_id, source_revision, if_match, if_none_match,
        )
        # Authorization precedes even the durable intent claim. Expiry and source
        # revisions are checked only for a fresh operation, after receipt replay.
        with self.ledger.engine.connect() as connection:
            owner = connection.exec_driver_sql(
                "SELECT owner_session_id FROM lookup_previews WHERE lookup_id=?", (lookup_id,),
            ).scalar_one_or_none()
        if owner is None:
            raise SaveConflict(404, "NOT_FOUND")
        if owner != owner_session_id:
            raise SaveConflict(403, "ORIGIN_FORBIDDEN")
        body: dict[str, Any] = {"lookupId": lookup_id, "noteDate": note_date}
        if source_id is not None:
            body.update(sourceId=source_id, sourceRevision=source_revision)
        claimed = self.ledger.claim(
            kind="SAVE", key=idempotency_key, method="POST", path="/api/v1/word-forms",
            body=body, preconditions={"If-Match": if_match, "If-None-Match": if_none_match},
        )
        operation = claimed.operation
        if claimed.replayed:
            if operation.status != "SUCCEEDED":
                code = operation.error_category or "IDEMPOTENCY_IN_FLIGHT"
                if code == "SOURCE_REPLACEMENT_ABORTED":
                    code = "SOURCE_NOT_WRITABLE"
                raise SaveConflict(
                    operation.response_status or 409, code, operation.operation_id,
                )
            return self.receipt(operation.operation_id, owner_session_id)
        operation_id = operation.operation_id
        try:
            preview = self.repository.get_preview(lookup_id, requesting_session_id=owner_session_id)
            if preview.status not in {"PREVIEW", "CONSUMED"} or not preview.forms:
                raise SaveConflict(422, "VALIDATION_ERROR")
            lookup_operation = (
                self.ledger.get(preview.operation_id) if preview.operation_id else None
            )
            if lookup_operation is None or (
                lookup_operation.kind != "LOOKUP" or lookup_operation.status != "SUCCEEDED"
                or lookup_operation.result_ref != lookup_id
            ):
                raise SaveConflict(422, "VALIDATION_ERROR")
            payload = {
                "version": 1, "familyRoot": normalize_lemma(preview.term),
                "forms": [form.to_dict() for form in preview.forms],
                "saveOperationId": operation_id,
                "provenance": {
                    "lookupId": lookup_id, "provider": preview.provider,
                    "model": preview.model, "promptVersion": preview.prompt_version,
                },
            }
            normalized = StructuredFamily.model_validate(payload)
            self._validate_preview(normalized)
            payload = normalized.model_dump(mode="json")
            semantics = structured_semantics(payload, note_date)
            context = {
                "lookup_id": lookup_id, "owner": owner_session_id,
                "identities": [
                    [s.family_root, s.normalized_lemma, s.part_of_speech] for s in semantics
                ],
            }
            with self.ledger.engine.connect() as connection:
                ids = list(connection.exec_driver_sql(
                    "SELECT id FROM source_files WHERE note_date=?", (note_date,),
                ).scalars())
            if source_id is None:
                if ids:
                    source = self.repository.get_source_file(str(ids[0]))
                    code = "SOURCE_NOT_WRITABLE" if len(ids) > 1 or (
                        source is not None and source.status != "VALID"
                    ) else "REVISION_CONFLICT"
                    raise SaveConflict(409, code)
                filename = self.coordinator.adapter.creation_path(note_date)
                original = (
                    f"# {filename[:-3]}\n\n## Tra cứu nhanh\n\n"
                    "| Từ/cụm từ | IPA (US) | Nghĩa ngắn | Ví dụ ngắn | Dịch ví dụ |\n"
                    "|---|---|---|---|---|\n\n"
                )
            else:
                source = self.repository.get_source_file(source_id)
                if source is None:
                    raise SaveConflict(404, "SOURCE_MISSING")
                if source.note_date != note_date:
                    raise SaveConflict(422, "CROSS_RESOURCE_MISMATCH")
                if source.status != "VALID" or len(ids) != 1 or ids[0] != source_id:
                    raise SaveConflict(409, "SOURCE_NOT_WRITABLE")
                if source.revision != source_revision or source.etag != if_match:
                    raise SaveConflict(409, "REVISION_CONFLICT", details={
                        "kind": "CONFLICT", "expectedRevision": source_revision,
                        "currentRevision": source.revision, "resourceType": "SOURCE",
                        "resourceId": source.id,
                    })
                self.coordinator.adapter.register_source(source)
                original = self.coordinator.adapter.read_source_content(source.id)
                if hashlib.sha256(original.encode()).hexdigest() != source.content_hash:
                    raise SaveConflict(409, "REVISION_CONFLICT")
                filename = source.relative_path.rsplit("/", 1)[-1]
            parsed = parse_markdown(original, filename=filename)
            if not parsed.is_valid or parsed.document is None:
                raise SaveConflict(409, "SOURCE_NOT_WRITABLE")
            proposed = upsert_structured_family(parsed.document, payload)
            if len(proposed.encode("utf-8")) > MAX_SOURCE_SIZE_BYTES:
                raise SourceFileError("PAYLOAD_TOO_LARGE", "Source size exceeds limit")
            if source_id is None:
                self.coordinator.create(
                    operation_id=operation_id, note_date=note_date, new_content=proposed,
                    operation_ledger=self.ledger, result_ref=operation_id,
                    receipt_context=context, fault=self.fault,
                )
            else:
                if source is None or source.content_hash is None:
                    raise SaveConflict(409, "SOURCE_NOT_WRITABLE")
                self.coordinator.write(
                    operation_id=operation_id, source_id=source_id,
                    expected_old_hash=source.content_hash, new_content=proposed,
                    intended_projection_revision=source.revision + 1,
                    operation_ledger=self.ledger, response_status=201, result_ref=operation_id,
                    receipt_context=context, fault=self.fault,
                )
            return self.receipt(operation_id, owner_session_id)
        except (PreviewOwnerMismatchError, PreviewExpiredError, PreviewNotFoundError) as error:
            code = (
                "ORIGIN_FORBIDDEN" if isinstance(error, PreviewOwnerMismatchError)
                else "VALIDATION_ERROR"
            )
            status = 403 if code == "ORIGIN_FORBIDDEN" else 422
            self._failure(operation_id, status, code)
            raise SaveConflict(status, code, operation_id) from None
        except (ValidationError, ValueError, RecursionError):
            self._failure(operation_id, 422, "VALIDATION_ERROR")
            raise SaveConflict(422, "VALIDATION_ERROR", operation_id) from None
        except SaveConflict as error:
            self._failure(operation_id, error.status_code, error.code)
            raise SaveConflict(error.status_code, error.code, operation_id, error.details) from None
        except SourceFileError as error:
            code = "REVISION_CONFLICT" if error.code == "REVISION_CONFLICT" else (
                "PAYLOAD_TOO_LARGE" if error.code == "PAYLOAD_TOO_LARGE" else
                "SOURCE_NOT_WRITABLE" if error.code in {
                    "SOURCE_NOT_FOUND", "SOURCE_NOT_WRITABLE", "SECURITY_VIOLATION",
                    "ROOT_IDENTITY_CHANGED", "ACCESS_DENIED",
                } else "STORAGE_BUSY"
            )
            status = 413 if code == "PAYLOAD_TOO_LARGE" else 503 if code == "STORAGE_BUSY" else 409
            recorded = self.ledger.get(operation_id)
            if recorded is not None and recorded.status == "FAILED" and (
                recorded.error_category == "SOURCE_REPLACEMENT_ABORTED"
            ):
                # The journal's proven abort is the durable failure outcome.
                # Both the first response and its replay expose its public code.
                status, code = 409, "SOURCE_NOT_WRITABLE"
            self._failure(operation_id, status, code)
            raise SaveConflict(status, code, operation_id) from None
        except JournalBusyError:
            self._failure(operation_id, 409, "IDEMPOTENCY_IN_FLIGHT")
            raise SaveConflict(409, "IDEMPOTENCY_IN_FLIGHT", operation_id) from None
        except JournalConflictError:
            self._failure(operation_id, 409, "REVISION_CONFLICT")
            raise SaveConflict(409, "REVISION_CONFLICT", operation_id) from None
        except (SQLAlchemyError, JournalError):
            self._failure(operation_id, 503, "STORAGE_BUSY")
            raise SaveConflict(503, "STORAGE_BUSY", operation_id) from None

    def _failure(self, operation_id: str, status: int, code: str) -> None:
        operation = self.ledger.get(operation_id)
        if operation is None or operation.status != "PENDING":
            return
        journal = self.coordinator.get(operation_id)
        self.ledger.record_failure(
            operation_id, response_status=status, error_category=code,
            unknown=journal is not None and journal.state not in {"ABORTED", "COMMITTED"},
        )

    def receipt(self, operation_id: str, owner: str) -> dict[str, Any]:
        operation = self.ledger.get(operation_id)
        journal = self.coordinator.get(operation_id)
        if (
            operation is None or operation.status != "SUCCEEDED"
            or journal is None or journal.state != "COMMITTED"
        ):
            raise SaveConflict(409, "IDEMPOTENCY_IN_FLIGHT", operation_id)
        if journal.effect_plan.get("save_context", {}).get("owner") != owner:
            raise SaveConflict(403, "ORIGIN_FORBIDDEN")
        result = journal.effect_plan.get("receipt")
        if (
            not isinstance(result, dict) or operation.result_ref != operation_id
            or operation.response_status != 201
        ):
            raise SaveConflict(503, "STORAGE_BUSY", operation_id)
        return result

    @staticmethod
    def _validate_preview(preview: StructuredFamily) -> None:
        # Source grammar also carries previously valid, larger legacy content.
        # Existing lookup validation's limits apply only to the incoming preview.
        if len(preview.forms) > 100:
            raise SaveConflict(422, "VALIDATION_ERROR")
        for form in preview.forms:
            if (
                len(form.lemma) > 128 or len(form.partOfSpeech) > 32
                or len(form.ipaUs or "") > 128 or len(form.cambridgeUrl or "") > 512
                or not 1 <= len(form.meaningsEn) <= 100
                or not 1 <= len(form.meaningsVi) <= 100
                or not 1 <= len(form.examples) <= 100
                or any(len(m.text) > 4096 for m in [*form.meaningsEn, *form.meaningsVi])
                or any(
                    not e.english.strip() or not e.vietnamese.strip()
                    or len(e.english) > 4096 or len(e.vietnamese) > 4096
                    for e in form.examples
                )
            ):
                raise SaveConflict(422, "VALIDATION_ERROR")

    @staticmethod
    def _validate_intent(
        lookup_id: str, note_date: str, source_id: str | None,
        source_revision: int | None, if_match: str | None, if_none_match: str | None,
    ) -> None:
        if not _ID.fullmatch(lookup_id) or not _DATE.fullmatch(note_date):
            raise SaveConflict(422, "VALIDATION_ERROR")
        try:
            date.fromisoformat(note_date)
        except ValueError:
            raise SaveConflict(422, "VALIDATION_ERROR") from None
        if source_id is None:
            valid = source_revision is None and if_match is None and if_none_match == "*"
        else:
            valid = bool(_ID.fullmatch(source_id)) and type(source_revision) is int and (
                source_revision is not None and source_revision >= 1
            ) and if_none_match is None and bool(if_match) and len(if_match or "") <= 128
        if not valid:
            raise SaveConflict(422, "VALIDATION_ERROR")

"""Revision-safe local edits through the existing durable source writer (T029)."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Annotated, Any, Literal, Self

from backend.app.adapters.source_files import SourceFileError
from backend.app.application.operations import OperationConflict, OperationLedger
from backend.app.application.source_write import (
    FaultInjector,
    JournalBusyError,
    JournalConflictError,
    JournalError,
    SourceWriteCoordinator,
    _form_digest,
)
from backend.app.enrichment.lookup import ProviderResponseError, _cambridge_url
from backend.app.markdown_sync.parser import MAX_SOURCE_SIZE_BYTES, parse_markdown
from backend.app.markdown_sync.serializer import upsert_structured_family
from backend.app.vocabulary.repository import VocabularyRepository
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from sqlalchemy.exc import SQLAlchemyError

Verification = Literal["VERIFIED", "UNVERIFIED", "MISSING"]
_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_EDITABLE = {"meaningsEn", "meaningsVi", "examples", "ipaUs", "cambridgeUrl"}


def _text(value: object) -> str:
    if not isinstance(value, str) or not value.strip() or any(
        0xD800 <= ord(c) <= 0xDFFF for c in value
    ):
        raise ValueError("Invalid editable text")
    return unicodedata.normalize("NFC", value)


class EditMeaning(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    text: str = Field(min_length=1, max_length=4096)
    verificationStatus: Verification

    @field_validator("text", mode="before")
    @classmethod
    def valid_text(cls, value: object) -> str:
        return _text(value)


class EditExample(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    english: str = Field(min_length=1, max_length=4096)
    vietnamese: str = Field(min_length=1, max_length=4096)
    verificationStatus: Verification

    @field_validator("english", "vietnamese", mode="before")
    @classmethod
    def valid_text(cls, value: object) -> str:
        return _text(value)


class EditWordFormIntent(BaseModel):
    """Omitted fields are preserved; explicit null is allowed only for IPA/link."""

    model_config = ConfigDict(extra="forbid", strict=True)
    sourceId: Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")]
    sourceRevision: int = Field(ge=1)
    meaningsEn: list[EditMeaning] | None = Field(default=None, min_length=1, max_length=100)
    meaningsVi: list[EditMeaning] | None = Field(default=None, min_length=1, max_length=100)
    examples: list[EditExample] | None = Field(default=None, min_length=1, max_length=100)
    ipaUs: str | None = Field(default=None, max_length=128)
    cambridgeUrl: str | None = Field(default=None, max_length=512)

    @field_validator("ipaUs", mode="before")
    @classmethod
    def valid_optional_text(cls, value: object) -> str | None:
        return _text(value) if value is not None else None

    @field_validator("cambridgeUrl", mode="before")
    @classmethod
    def valid_dictionary_url(cls, value: object) -> str | None:
        try:
            return _cambridge_url(_text(value) if value is not None else None)
        except ProviderResponseError:
            raise ValueError("Invalid Cambridge dictionary URL") from None

    @model_validator(mode="after")
    def editable_content(self) -> Self:
        supplied = self.model_fields_set & _EDITABLE
        if not supplied or any(
            getattr(self, field) is None
            for field in supplied & {"meaningsEn", "meaningsVi", "examples"}
        ):
            raise ValueError("At least one valid editable field is required")
        return self


class EditConflict(OperationConflict):
    def __init__(
        self, status: int, code: str, operation_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(status, code, operation_id)
        self.details = details


class EditWordFormService:
    def __init__(self, ledger: OperationLedger, coordinator: SourceWriteCoordinator) -> None:
        if ledger.engine is not coordinator.engine:
            raise ValueError("Edit and journal must share an engine")
        self.ledger = ledger
        self.coordinator = coordinator
        self.repository = VocabularyRepository(ledger.engine)
        self.fault: FaultInjector | None = None

    def edit(
        self, *, word_form_id: str, intent: EditWordFormIntent,
        idempotency_key: str, if_match: str,
    ) -> tuple[dict[str, Any], str]:
        if not _ID.fullmatch(word_form_id) or not if_match or len(if_match) > 128:
            raise EditConflict(422, "VALIDATION_ERROR")
        # This is a single-user local resource, protected by SessionGuard. Receipt
        # replay is independent of today's membership and of restart session IDs.
        claim = self.ledger.claim(
            kind="EDIT", key=idempotency_key, method="PATCH",
            path=f"/api/v1/word-forms/{word_form_id}",
            body=intent.model_dump(mode="json", exclude_unset=True),
            preconditions={"If-Match": if_match},
        )
        operation_id = claim.operation.operation_id
        if claim.replayed:
            if claim.operation.status != "SUCCEEDED":
                code = claim.operation.error_category or "IDEMPOTENCY_IN_FLIGHT"
                if code == "SOURCE_REPLACEMENT_ABORTED":
                    code = "REVISION_CONFLICT"
                raise EditConflict(claim.operation.response_status or 409, code, operation_id)
            return self.receipt(operation_id, word_form_id, intent.sourceId)
        try:
            with self.ledger.engine.connect() as connection, connection.begin():
                source = self.repository.get_source_file(intent.sourceId, connection=connection)
                if source is None:
                    raise EditConflict(404, "SOURCE_MISSING")
                form = self.repository.get_word_form(word_form_id, connection=connection)
                if form is None:
                    raise EditConflict(404, "NOT_FOUND")
                if not any(ref.source_id == source.id and ref.note_date == source.note_date
                           for ref in form.source_refs):
                    raise EditConflict(422, "CROSS_RESOURCE_MISMATCH")
                ids = list(connection.exec_driver_sql(
                    "SELECT id FROM source_files WHERE note_date=?", (source.note_date,),
                ).scalars())
                if source.status != "VALID" or ids != [source.id] or source.content_hash is None:
                    raise EditConflict(409, "SOURCE_NOT_WRITABLE")
                if source.revision != intent.sourceRevision or source.etag != if_match:
                    raise EditConflict(409, "REVISION_CONFLICT", details={
                        "kind": "CONFLICT", "expectedRevision": intent.sourceRevision,
                        "currentRevision": source.revision, "resourceType": "SOURCE",
                        "resourceId": source.id,
                    })
                family = self.repository.get_family(form.family_id, connection=connection)
                if family is None:
                    raise EditConflict(409, "SOURCE_NOT_WRITABLE")
            self.coordinator.adapter.register_source(source)
            original = self.coordinator.adapter.read_source_content(source.id)
            if hashlib.sha256(original.encode("utf-8")).hexdigest() != source.content_hash:
                raise EditConflict(409, "REVISION_CONFLICT")
            parsed = parse_markdown(original, filename=source.relative_path.rsplit("/", 1)[-1])
            if not parsed.is_valid or parsed.document is None:
                raise EditConflict(409, "SOURCE_NOT_WRITABLE")
            identity = [family.root_lemma, form.normalized_lemma, form.part_of_speech]
            matches = [semantic for semantic in parsed.document.semantic_forms if [
                semantic.family_root, semantic.normalized_lemma, semantic.part_of_speech,
            ] == identity]
            if len(matches) != 1:
                raise EditConflict(422, "CROSS_RESOURCE_MISMATCH")
            # Start from current canonical content, not a historical source-date
            # snapshot. Partial metadata edits must not revert newer learning text.
            payload_form: dict[str, Any] = {
                "lemma": form.lemma, "partOfSpeech": form.part_of_speech,
                "meaningsEn": [meaning.to_dict() for meaning in form.meanings_en],
                "meaningsVi": [meaning.to_dict() for meaning in form.meanings_vi],
                "examples": [example.to_dict() for example in form.examples],
                "ipaUs": form.ipa_us, "ipaStatus": form.ipa_status,
                "cambridgeUrl": form.cambridge_url, "cambridgeStatus": form.cambridge_status,
            }
            updates = intent.model_dump(mode="json", exclude_unset=True)
            for field in _EDITABLE & intent.model_fields_set:
                value = updates[field]
                if field in {"meaningsEn", "meaningsVi"}:
                    value = [{**item, "language": "en" if field == "meaningsEn" else "vi"}
                             for item in value]
                payload_form[field] = value
                if field in {"ipaUs", "cambridgeUrl"} and value != (
                    form.ipa_us if field == "ipaUs" else form.cambridge_url
                ):
                    payload_form["ipaStatus" if field == "ipaUs" else "cambridgeStatus"] = (
                        "MISSING" if value is None else "UNVERIFIED"
                    )
            proposed = upsert_structured_family(parsed.document, {
                "version": 1, "familyRoot": family.root_lemma, "forms": [payload_form],
                # Persist the edit provenance even for a semantic no-op. Each fresh
                # intent advances the selected source once; replay writes nothing.
                "editOperationId": operation_id,
            })
            if len(proposed.encode("utf-8")) > MAX_SOURCE_SIZE_BYTES:
                raise EditConflict(413, "PAYLOAD_TOO_LARGE")
            self.coordinator.write(
                operation_id=operation_id, source_id=source.id,
                expected_old_hash=source.content_hash, new_content=proposed,
                intended_projection_revision=source.revision + 1,
                operation_ledger=self.ledger, response_status=200, result_ref=operation_id,
                edit_context={
                    "form_id": form.id, "form_revision": form.revision,
                    "form_hash": _form_digest(form), "etag": if_match, "identities": [identity],
                }, fault=self.fault,
            )
            return self.receipt(operation_id, word_form_id, source.id)
        except EditConflict as error:
            self._failure(operation_id, error.status_code, error.code)
            raise EditConflict(error.status_code, error.code, operation_id, error.details) from None
        except (ValidationError, ValueError, RecursionError):
            self._failure(operation_id, 422, "VALIDATION_ERROR")
            raise EditConflict(422, "VALIDATION_ERROR", operation_id) from None
        except (JournalBusyError, JournalConflictError):
            self._failure(operation_id, 409, "REVISION_CONFLICT")
            raise EditConflict(409, "REVISION_CONFLICT", operation_id) from None
        except SourceFileError as error:
            code = "REVISION_CONFLICT" if error.code == "REVISION_CONFLICT" else (
                "PAYLOAD_TOO_LARGE" if error.code == "PAYLOAD_TOO_LARGE" else
                "SOURCE_NOT_WRITABLE" if error.code in {
                    "SOURCE_NOT_FOUND", "SOURCE_NOT_WRITABLE", "SECURITY_VIOLATION",
                    "ROOT_IDENTITY_CHANGED", "ACCESS_DENIED",
                } else "STORAGE_BUSY"
            )
            status = 413 if code == "PAYLOAD_TOO_LARGE" else 503 if code == "STORAGE_BUSY" else 409
            operation = self.ledger.get(operation_id)
            if operation is not None and operation.error_category == "SOURCE_REPLACEMENT_ABORTED":
                status, code = 409, "REVISION_CONFLICT"
            self._failure(operation_id, status, code)
            raise EditConflict(status, code, operation_id) from None
        except (SQLAlchemyError, JournalError):
            self._failure(operation_id, 503, "STORAGE_BUSY")
            raise EditConflict(503, "STORAGE_BUSY", operation_id) from None

    def _failure(self, operation_id: str, status: int, code: str) -> None:
        try:
            operation = self.ledger.get(operation_id)
            if operation is None or operation.status != "PENDING":
                return
            journal = self.coordinator.get(operation_id)
            self.ledger.record_failure(
                operation_id, response_status=status, error_category=code,
                unknown=journal is not None and journal.state not in {"ABORTED", "COMMITTED"},
            )
        except (SQLAlchemyError, OperationConflict):
            # Keep the durable pending claim if storage cannot record the outcome.
            # Startup reconciliation is the authority; never manufacture success.
            return

    def receipt(
        self, operation_id: str, word_form_id: str, source_id: str,
    ) -> tuple[dict[str, Any], str]:
        operation = self.ledger.get(operation_id)
        journal = self.coordinator.get(operation_id)
        if operation is None or operation.status != "SUCCEEDED" or (
            journal is None or journal.state != "COMMITTED"
        ):
            raise EditConflict(409, "IDEMPOTENCY_IN_FLIGHT", operation_id)
        context = journal.effect_plan.get("edit_context", {})
        result = journal.effect_plan.get("receipt")
        etag = journal.effect_plan.get("response_etag")
        frozen_form = result.get("wordForm") if isinstance(result, dict) else None
        if (
            operation.kind != "EDIT" or operation.result_ref != operation_id
            or operation.response_status != 200 or journal.response_status != 200
            or journal.result_ref != operation_id or journal.source_id != source_id
            or context.get("form_id") != word_form_id or not isinstance(result, dict)
            or result.get("operationId") != operation_id
            or result.get("sourceRevision") != journal.intended_projection_revision
            or not isinstance(frozen_form, dict) or frozen_form.get("id") != word_form_id
            or not isinstance(etag, str)
        ):
            raise EditConflict(503, "STORAGE_BUSY", operation_id)
        return result, etag

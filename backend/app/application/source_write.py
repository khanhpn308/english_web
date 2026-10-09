"""Crash-safe orchestration for Markdown source replacements (T022).

The filesystem adapter owns validation, staging, fsync and atomic replacement. This
module only records intent and coordinates short SQLite transactions around it.
Canonical vocabulary, search, card resets, receipt and the terminal marker share
one writer transaction. Recovery reconstructs the effects from persisted identifiers
and verified on-disk Markdown. Edit publication shares the receipt transaction so
reviews cannot invalidate its frozen card snapshot between publication and completion.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import PurePosixPath
from secrets import token_urlsafe
from typing import Any, Literal, Protocol

from backend.app.adapters.source_files import SourceFileAdapter, SourceFileError, StagedTempHandle
from backend.app.application.operations import OperationConflict, OperationLedger
from backend.app.markdown_sync.parser import ParsedDocument, SemanticForm, parse_markdown
from backend.app.review.models import ensure_card, reset_card_state
from backend.app.vocabulary.models import (
    ExampleSentence,
    MeaningEn,
    MeaningVi,
    SourceFile,
    VerificationStatus,
    WordForm,
    compute_verification_summary,
)
from backend.app.vocabulary.repository import VocabularyRepository
from backend.app.vocabulary.search_index import (
    ProjectionVersionMismatchError,
    SearchIndex,
    StaleSourceRevisionError,
)
from sqlalchemy import Connection, Engine

JournalState = Literal["PREPARED", "SOURCE_REPLACED", "COMMITTED", "ABORTED", "DEGRADED"]
FaultPoint = Literal[
    "BEFORE_PREPARED",
    "AFTER_PREPARED",
    "BEFORE_TEMP_HANDLE",
    "AFTER_TEMP_FSYNC",
    "AFTER_ATOMIC_REPLACE",
    "AFTER_SOURCE_REPLACED",
    "BEFORE_PROJECTION",
    "DURING_CANONICAL",
    "AFTER_PROJECTION",
    "AFTER_CARD_RESET",
    "AFTER_RECEIPT",
]


class JournalError(RuntimeError):
    """Base class for source journal refusals."""


class JournalConflictError(JournalError):
    """The operation or source has a different durable intent."""


class JournalBusyError(JournalError):
    """A source already has an active write intent."""


class AmbiguousSourceStateError(JournalError):
    """Observed bytes match neither durable old nor intended new hash."""


class UnknownOperationError(JournalError):
    """An UNKNOWN operation cannot authorize a new destructive action."""


class InjectedCrash(RuntimeError):
    """Deterministic test fault; callers should treat it as process loss."""


class FaultInjector(Protocol):
    def __call__(self, point: FaultPoint) -> None: ...


ProjectionApply = Callable[[Connection, "JournalRecord"], None]
CardReset = Callable[[Connection, "JournalRecord"], None]


@dataclass(frozen=True)
class JournalRecord:
    operation_id: str
    source_id: str
    old_hash: str
    new_hash: str
    temp_path: str | None
    temp_device: int | None
    temp_inode: int | None
    intended_projection_revision: int
    effect_plan: dict[str, Any]
    response_status: int
    result_ref: str
    state: JournalState
    created_at: str
    updated_at: str


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _semantic_key(form: SemanticForm) -> str:
    return _hash(json.dumps([form.family_root, form.normalized_lemma, form.part_of_speech]))


def _learning_values(form: WordForm) -> tuple[object, ...]:
    return (
        [m.text for m in form.meanings_en],
        [m.text for m in form.meanings_vi],
        [(e.english, e.vietnamese) for e in form.examples],
    )


def _form_digest(form: WordForm) -> str:
    return _hash(
        json.dumps(
            [
                form.family_id,
                form.normalized_lemma,
                form.part_of_speech,
                [m.to_dict() for m in form.meanings_en],
                [m.to_dict() for m in form.meanings_vi],
                [e.to_dict() for e in form.examples],
                form.ipa_us,
                form.ipa_status,
                form.cambridge_url,
                form.cambridge_status,
            ],
            ensure_ascii=False,
            sort_keys=True,
        )
    )


def _projection_values(
    semantic: SemanticForm, old: WordForm | None,
) -> tuple[list[MeaningEn], list[MeaningVi], list[ExampleSentence],
           VerificationStatus, VerificationStatus]:
    en = [
        MeaningEn(text, verification_status=semantic.meanings_en_statuses[i])
        if semantic.meanings_en_statuses else
        next((m for m in old.meanings_en if m.text == text), MeaningEn(text)) if old
        else MeaningEn(text)
        for i, text in enumerate(semantic.meanings_en)
    ]
    vi = [
        MeaningVi(text, verification_status=semantic.meanings_vi_statuses[i])
        if semantic.meanings_vi_statuses else
        next((m for m in old.meanings_vi if m.text == text), MeaningVi(text)) if old
        else MeaningVi(text)
        for i, text in enumerate(semantic.meanings_vi)
    ]
    examples = [
        ExampleSentence(*pair, verification_status=semantic.example_statuses[i])
        if semantic.example_statuses else
        next((e for e in old.examples if (e.english, e.vietnamese) == pair),
             ExampleSentence(*pair)) if old else ExampleSentence(*pair)
        for i, pair in enumerate(semantic.examples)
    ]
    ipa_status: VerificationStatus = semantic.ipa_status or (
        old.ipa_status if old and old.ipa_us == semantic.ipa_us else
        "MISSING" if semantic.ipa_us is None else "UNVERIFIED"
    )
    link_status: VerificationStatus = semantic.cambridge_status or (
        old.cambridge_status if old and old.cambridge_url == semantic.cambridge_url else
        "MISSING" if semantic.cambridge_url is None else "UNVERIFIED"
    )
    return en, vi, examples, ipa_status, link_status


def _content_changed(semantic: SemanticForm, old: WordForm | None) -> bool:
    en, vi, examples, ipa_status, link_status = _projection_values(semantic, old)
    return old is None or (
        old.meanings_en, old.meanings_vi, old.examples, old.ipa_us, old.ipa_status,
        old.cambridge_url, old.cambridge_status,
    ) != (en, vi, examples, semantic.ipa_us, ipa_status, semantic.cambridge_url, link_status)


class SourceWriteCoordinator:
    """Coordinate one durable source intent with T021 and T014."""

    def __init__(self, engine: Engine, adapter: SourceFileAdapter) -> None:
        self.engine = engine
        self.adapter = adapter
        self.repository = VocabularyRepository(engine)
        self.search_index = SearchIndex(engine)

    def _document(self, source_id: str, content: str) -> ParsedDocument:
        source = self.adapter.get_source(source_id)
        if source is None:
            raise JournalConflictError("Source registration is missing")
        parsed = parse_markdown(content, filename=PurePosixPath(source.relative_path).name)
        if not parsed.is_valid or parsed.document is None:
            raise JournalConflictError("Source replacement is invalid")
        return parsed.document

    @staticmethod
    def _semantics(document: ParsedDocument) -> dict[str, SemanticForm]:
        result: dict[str, SemanticForm] = {}
        for form in document.semantic_forms:
            key = _semantic_key(form)
            if key in result and result[key] != form:
                raise JournalConflictError("Source has ambiguous canonical content")
            result[key] = form
        return result

    def _plan(
        self, connection: Connection, source_id: str, document: ParsedDocument
    ) -> dict[str, Any]:
        """Persist identifiers and baseline hashes; learning values stay in Markdown."""
        family_ids: dict[str, str] = {}
        effects: list[dict[str, Any]] = []
        linked = self.repository.get_forms_for_source(source_id, connection=connection)
        for key, semantic in sorted(self._semantics(document).items()):
            families = self.repository.get_families_for_root(
                semantic.family_root, connection=connection
            )
            if len(families) > 1:
                raise JournalConflictError("Canonical family identity is ambiguous")
            family_id = family_ids.setdefault(
                semantic.family_root, families[0].id if families else f"family_{token_urlsafe(12)}"
            )
            existing = self.repository.get_word_form_by_identity(
                semantic.lemma, semantic.part_of_speech, family_id, connection=connection
            )
            form_id = existing.id if existing else f"wf_{token_urlsafe(12)}"
            card_id = connection.exec_driver_sql(
                "SELECT card_id FROM review_cards WHERE word_form_id=?", (form_id,)
            ).scalar_one_or_none()
            needs_reset = existing is not None and _learning_values(existing) != (
                semantic.meanings_en,
                semantic.meanings_vi,
                semantic.examples,
            )
            effects.append(
                {
                    "key": key,
                    "family_id": family_id,
                    "form_id": form_id,
                    "base_revision": existing.revision if existing else None,
                    "base_hash": _form_digest(existing) if existing else None,
                    "card_id": str(card_id) if card_id else f"card_{token_urlsafe(12)}",
                    "reset": bool(card_id and needs_reset),
                }
            )
        planned_ids = {effect["form_id"] for effect in effects}
        return {
            "version": 1,
            "forms": effects,
            "links": sorted(form.id for form in linked),
            "removed": sorted(form.id for form in linked if form.id not in planned_ids),
        }

    @contextmanager
    def _writer(self) -> Iterator[Connection]:
        with (
            self.engine.connect().execution_options(sqlite_begin_immediate=True) as connection,
            connection.begin(),
        ):
            yield connection

    def _save_receipt(
        self, connection: Connection, source_id: str, document: ParsedDocument,
        plan: dict[str, Any], operation_id: str, revision: int, context: dict[str, Any],
    ) -> dict[str, Any]:
        """Freeze the exact original result in existing immutable journal evidence.

        Timestamp, memberships and card baselines are checked/applied by completion;
        replay never substitutes today's canonical content for the saved snapshot.
        """
        stamp = _now()
        plan["receipt_time"] = stamp
        semantics = self._semantics(document)
        by_identity = {
            (semantics[e["key"]].family_root, semantics[e["key"]].normalized_lemma,
             semantics[e["key"]].part_of_speech): e for e in plan["forms"]
        }
        created: list[str] = []
        reused: list[str] = []
        forms: list[dict[str, Any]] = []
        for identity in context["identities"]:
            effect = by_identity.get(tuple(identity))
            if effect is None:
                raise JournalConflictError("Preview identity is absent from proposed source")
            semantic = semantics[effect["key"]]
            old = self.repository.get_word_form(effect["form_id"], connection=connection)
            en, vi, examples, ipa_status, link_status = _projection_values(semantic, old)
            card = connection.exec_driver_sql(
                "SELECT box,due_at,queue_revision FROM review_cards WHERE card_id=?",
                (effect["card_id"],),
            ).first()
            effect["card_baseline"] = list(card) if card is not None else None
            effect["refs_baseline"] = json.dumps(
                sorted([sorted(ref.to_dict().items()) for ref in old.source_refs]) if old else [],
                sort_keys=True,
            )
            (reused if card is not None else created).append(effect["card_id"])
            refs = (
                [ref.to_dict() for ref in old.source_refs if ref.source_id != source_id]
                if old else []
            )
            refs.append({"sourceId": source_id, "noteDate": document.note_date, "status": "VALID"})
            changed = _content_changed(semantic, old)
            forms.append({
                "id": effect["form_id"], "familyId": effect["family_id"],
                "lemma": old.lemma if old else semantic.lemma,
                "partOfSpeech": semantic.part_of_speech,
                "meaningsEn": [m.to_dict() for m in en],
                "meaningsVi": [m.to_dict() for m in vi],
                "examples": [e.to_dict() for e in examples],
                "ipaUs": semantic.ipa_us, "cambridgeUrl": semantic.cambridge_url,
                "sourceRefs": sorted(refs, key=lambda ref: (ref["noteDate"], ref["sourceId"])),
                "card": {
                    "id": effect["card_id"],
                    "state": (
                        "NEW" if card is None or effect["reset"] or card[0] == 0 else "LEARNED"
                    ),
                    "dueAt": None if card is None or effect["reset"] else card[1],
                },
                "revision": old.revision + int(changed) if old else 1,
                "verificationSummary": compute_verification_summary(
                    meanings_en=en, meanings_vi=vi, examples=examples,
                    ipa_us=semantic.ipa_us, cambridge_url=semantic.cambridge_url,
                    ipa_status=ipa_status, cambridge_status=link_status,
                ),
                "updatedAt": stamp if changed or old is None else old.updated_at,
            })
        return {
            "operationId": operation_id, "sourceId": source_id,
            "sourceRevision": revision, "sourceEtag": f'"source-{source_id}-r{revision}"',
            "noteDate": document.note_date,
            "savedForms": [{"id": f["id"], "revision": f["revision"]} for f in forms],
            "canonicalForms": forms, "createdCardIds": created, "reusedCardIds": reused,
            "markdownSync": "COMPLETED",
        }

    @staticmethod
    def _fault(fault: FaultInjector | None, point: FaultPoint) -> None:
        if fault is not None:
            fault(point)

    @staticmethod
    def _record(connection: Connection, operation_id: str) -> JournalRecord | None:
        row = (
            connection.exec_driver_sql(
                "SELECT * FROM source_write_journal WHERE operation_id=?",
                (operation_id,),
            )
            .mappings()
            .first()
        )
        if row is None:
            return None
        return JournalRecord(
            operation_id=str(row["operation_id"]),
            source_id=str(row["source_id"]),
            old_hash=str(row["old_hash"]),
            new_hash=str(row["new_hash"]),
            temp_path=str(row["temp_path"]) if row["temp_path"] is not None else None,
            temp_device=int(row["temp_device"]) if row["temp_device"] is not None else None,
            temp_inode=int(row["temp_inode"]) if row["temp_inode"] is not None else None,
            intended_projection_revision=int(row["intended_projection_revision"]),
            effect_plan=json.loads(row["effect_plan"]),
            response_status=int(row["response_status"]),
            result_ref=str(row["result_ref"]),
            state=row["state"],
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    def get(self, operation_id: str) -> JournalRecord | None:
        with self.engine.connect() as connection:
            return self._record(connection, operation_id)

    def _active_for_source(self, connection: Connection, source_id: str) -> JournalRecord | None:
        row = (
            connection.exec_driver_sql(
                "SELECT operation_id FROM source_write_journal "
                "WHERE source_id=? AND state IN ('PREPARED','SOURCE_REPLACED','DEGRADED')",
                (source_id,),
            )
            .scalars()
            .first()
        )
        return self._record(connection, str(row)) if row is not None else None

    def prepare(
        self,
        *,
        operation_id: str,
        source_id: str,
        expected_old_hash: str,
        new_content: str,
        intended_projection_revision: int,
        response_status: int = 200,
        result_ref: str = "source_write",
        fault: FaultInjector | None = None,
        _require_new: bool = False,
        creation: bool = False,
        receipt_context: dict[str, Any] | None = None,
        edit_context: dict[str, Any] | None = None,
    ) -> JournalRecord:
        """Persist PREPARED intent before calling any filesystem replacement."""
        new_hash = _hash(new_content)
        OperationLedger.validate_receipt(response_status, result_ref)
        document = self._document(source_id, new_content)
        if edit_context is not None and (creation or receipt_context is not None):
            raise JournalConflictError("Edit and save contexts cannot be combined")
        context = edit_context if edit_context is not None else receipt_context
        if expected_old_hash == new_hash:
            raise JournalConflictError("Replacement content is unchanged")
        if intended_projection_revision < 1:
            raise ValueError("intended_projection_revision must be positive")
        with self._writer() as connection:
            existing = self._record(connection, operation_id)
            if existing is not None:
                if (
                    existing.source_id,
                    existing.old_hash,
                    existing.new_hash,
                    existing.intended_projection_revision,
                    existing.response_status,
                    existing.result_ref,
                ) != (
                    source_id,
                    expected_old_hash,
                    new_hash,
                    intended_projection_revision,
                    response_status,
                    result_ref,
                ):
                    raise JournalConflictError("Operation has a different source intent")
                if _require_new:
                    raise JournalBusyError("Source operation is already in flight")
                return existing

            active = self._active_for_source(connection, source_id)
            if active is not None:
                if active.state == "DEGRADED":
                    raise JournalBusyError("Source is degraded and requires explicit repair")
                raise JournalBusyError("Source has an in-flight write")

            if creation:
                registered = self.adapter.get_source(source_id)
                if registered is None or (
                    registered.status != "MISSING" or registered.revision != 0
                    or registered.error_code != "CREATION_PENDING"
                    or expected_old_hash != _hash("") or intended_projection_revision != 1
                ):
                    raise JournalConflictError("Creation registration is missing")
                occupied = connection.exec_driver_sql(
                    "SELECT 1 FROM source_files WHERE note_date=? OR relative_path=?",
                    (registered.note_date, registered.relative_path),
                ).first()
                if occupied is not None:
                    raise JournalConflictError("Creation date is occupied")
                self.adapter.assert_creation_absent(registered)
                self.repository.save_source_file(
                    source_id=source_id, relative_path=registered.relative_path,
                    note_date=registered.note_date, status="MISSING", revision=0,
                    etag=registered.etag, content_hash=expected_old_hash,
                    error_code="CREATION_PENDING", connection=connection,
                )

            source = (
                connection.exec_driver_sql(
                    "SELECT status,revision,content_hash,note_date,relative_path "
                    "FROM source_files WHERE id=?",
                    (source_id,),
                )
                .mappings()
                .first()
            )
            if source is None:
                raise JournalConflictError("Source registration is missing")
            registered = self.adapter.get_source(source_id)
            if registered is None or registered.relative_path != source["relative_path"]:
                raise JournalConflictError("Filesystem registration differs from canonical source")
            expected_status = "MISSING" if creation else "VALID"
            if source["status"] != expected_status or source["content_hash"] != expected_old_hash:
                raise JournalConflictError("Source revision or hash is stale")
            if int(source["revision"]) + 1 != intended_projection_revision:
                raise JournalConflictError("Projection revision is stale")
            if document.note_date != source["note_date"]:
                raise JournalConflictError("Source date changed")
            if context is not None:
                date_sources = list(connection.exec_driver_sql(
                    "SELECT id FROM source_files WHERE note_date=?", (source["note_date"],),
                ).scalars())
                if date_sources != [source_id]:
                    raise SourceFileError("SOURCE_NOT_WRITABLE", "Source date is ambiguous")
            operation_status = connection.exec_driver_sql(
                "SELECT status FROM operations WHERE operation_id=?", (operation_id,)
            ).scalar_one_or_none()
            if operation_status != "PENDING":
                raise UnknownOperationError("A new source write requires a pending operation")
            plan = self._plan(connection, source_id, document)
            # Source locks alone do not protect shared canonical forms across dates.
            # Fence overlapping plans whenever either operation is an edit. Existing
            # save-only entries retain their original lifecycle and response shape.
            planned_ids = {effect["form_id"] for effect in plan["forms"]}
            for row in connection.exec_driver_sql(
                "SELECT effect_plan FROM source_write_journal "
                "WHERE state IN ('PREPARED','SOURCE_REPLACED','DEGRADED')",
            ):
                active_plan = json.loads(row[0])
                if (edit_context is not None or "edit_context" in active_plan) and (
                    planned_ids & {effect["form_id"] for effect in active_plan["forms"]}
                ):
                    raise JournalBusyError("A shared form has an active source write")
            if creation:
                plan["mutation"] = "CREATE"
            if context is not None:
                plan["edit_context" if edit_context is not None else "save_context"] = context
                if edit_context is not None:
                    target = next((effect for effect in plan["forms"]
                                   if effect["form_id"] == context["form_id"]), None)
                    operation_kind = connection.exec_driver_sql(
                        "SELECT kind FROM operations WHERE operation_id=?", (operation_id,),
                    ).scalar_one()
                    canonical_source = self.repository.get_source_file(
                        source_id, connection=connection,
                    )
                    if (
                        operation_kind != "EDIT" or response_status != 200
                        or result_ref != operation_id or target is None
                        or target["form_id"] not in plan["links"]
                        or target["base_revision"] != context["form_revision"]
                        or target["base_hash"] != context["form_hash"]
                        or canonical_source is None or canonical_source.etag != context["etag"]
                        or len(context["identities"]) != 1 or plan["removed"]
                        or any(effect["base_revision"] is None for effect in plan["forms"])
                    ):
                        raise JournalConflictError("Edit target or source preconditions changed")
                    target_semantic = self._semantics(document)[target["key"]]
                    if {tuple(identity) for identity in context["identities"]} != {(
                        target_semantic.family_root, target_semantic.normalized_lemma,
                        target_semantic.part_of_speech,
                    )}:
                        raise JournalConflictError("Edit target identity changed")
                if not creation:
                    # A date note can retain an older snapshot of shared forms.
                    # Saving another preview owns only its selected identities;
                    # unchanged historical sections must not roll canonical content
                    # or SRS back. Authenticate this decision before publication.
                    previous_content = self.adapter.read_source_content(source_id)
                    if _hash(previous_content) != expected_old_hash:
                        raise JournalConflictError("Source bytes changed before preparation")
                    previous = self._semantics(self._document(source_id, previous_content))
                    proposed = self._semantics(document)
                    selected = {tuple(identity) for identity in context["identities"]}
                    if edit_context is not None and set(previous) != set(proposed):
                        raise JournalConflictError("Edit changes source identities")
                    for effect in plan["forms"]:
                        semantic = proposed[effect["key"]]
                        identity = (semantic.family_root, semantic.normalized_lemma,
                                    semantic.part_of_speech)
                        if identity in selected or effect["base_revision"] is None:
                            continue
                        prior = previous.get(effect["key"])
                        if prior is None or (
                            prior.ipa_us, prior.cambridge_url, _projection_values(prior, None)
                        ) != (
                            semantic.ipa_us, semantic.cambridge_url,
                            _projection_values(semantic, None),
                        ):
                            raise JournalConflictError("Save changes an unselected source form")
                        effect["preserve_canonical"] = True
                        effect["reset"] = False
                snapshot = self._save_receipt(
                    connection, source_id, document, plan, operation_id,
                    intended_projection_revision, context,
                )
                if edit_context is None:
                    plan["receipt"] = snapshot
                else:
                    plan["receipt"] = {
                        "wordForm": snapshot["canonicalForms"][0],
                        "operationId": operation_id,
                        "sourceRevision": intended_projection_revision,
                    }
                    plan["response_etag"] = snapshot["sourceEtag"]

            now = _now()
            self._fault(fault, "BEFORE_PREPARED")
            connection.exec_driver_sql(
                "INSERT INTO source_write_journal "
                "(operation_id,source_id,old_hash,new_hash,temp_path,"
                "intended_projection_revision,effect_plan,response_status,result_ref,"
                "state,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?, 'PREPARED',?,?)",
                (
                    operation_id,
                    source_id,
                    expected_old_hash,
                    new_hash,
                    None,
                    intended_projection_revision,
                    json.dumps(plan, sort_keys=True),
                    response_status,
                    result_ref,
                    now,
                    now,
                ),
            )
            created = self._record(connection, operation_id)
            if created is None:
                raise RuntimeError("Prepared journal was not persisted")
        self._fault(fault, "AFTER_PREPARED")
        return created

    def _transition(self, operation_id: str, state: JournalState) -> JournalRecord:
        with self._writer() as connection:
            current = self._record(connection, operation_id)
            if current is None:
                raise JournalError("Journal record is missing")
            if current.state == state:
                return current
            now = _now()
            connection.exec_driver_sql(
                "UPDATE source_write_journal SET state=?,updated_at=? WHERE operation_id=?",
                (state, now, operation_id),
            )
            updated = self._record(connection, operation_id)
            if updated is None:
                raise RuntimeError("Journal transition was not persisted")
            return updated

    def _record_stage(self, journal: JournalRecord, handle: StagedTempHandle) -> None:
        with self._writer() as connection:
            connection.exec_driver_sql(
                "UPDATE source_write_journal SET temp_path=?,temp_device=?,temp_inode=?,"
                "updated_at=? "
                "WHERE operation_id=? AND state='PREPARED' AND temp_path IS NULL",
                (
                    handle.relative_path,
                    str(handle.device),
                    str(handle.inode),
                    _now(),
                    journal.operation_id,
                ),
            )
            current = self._record(connection, journal.operation_id)
            if current is None or current.temp_path != handle.relative_path:
                raise JournalBusyError("Staged intent changed")

    def _abort(self, journal: JournalRecord, ledger: OperationLedger | None) -> JournalRecord:
        if journal.temp_path is not None:
            if journal.temp_device is None or journal.temp_inode is None:
                raise JournalError("Staged evidence is incomplete")
            self.adapter.cleanup_abandoned_temp(
                StagedTempHandle(
                    journal.source_id,
                    journal.temp_path,
                    journal.temp_device,
                    journal.temp_inode,
                    journal.new_hash,
                )
            )
        if journal.effect_plan.get("mutation") == "CREATE":
            source = self.adapter.get_source(journal.source_id)
            if source is None:
                raise JournalError("Creation registration is missing")
            self.adapter.assert_creation_absent(source)
        elif self.adapter.get_source_hash(journal.source_id) != journal.old_hash:
            return self._transition(journal.operation_id, "DEGRADED")
        ledger = ledger or OperationLedger(self.engine)
        if ledger.engine is not self.engine:
            raise JournalError("Source and receipt must share the database engine")
        try:
            ledger.abort_source_write(journal.operation_id, expected_old_hash=journal.old_hash)
        except OperationConflict as error:
            if error.code != "SOURCE_EVIDENCE_MISMATCH":
                raise
            return self._transition(journal.operation_id, "DEGRADED")
        if journal.effect_plan.get("mutation") == "CREATE":
            # Retain the reserved identity and journal FK for audit/recovery.
            # MISSING is read-only; a fresh key cannot silently repair this date.
            with self._writer() as connection:
                connection.exec_driver_sql(
                    "UPDATE source_files SET error_code='CREATION_ABORTED' "
                    "WHERE id=? AND revision=0",
                    (journal.source_id,),
                )
        result = self.get(journal.operation_id)
        if result is None:
            raise JournalError("Aborted journal disappeared")
        return result

    def _apply_local(
        self,
        connection: Connection,
        journal: JournalRecord,
        document: ParsedDocument,
        *,
        apply_projection: ProjectionApply | None,
        reset_cards: CardReset | None,
        fault: FaultInjector | None,
    ) -> None:
        current = self._record(connection, journal.operation_id)
        if current is None or current.state != "SOURCE_REPLACED":
            if current is not None and current.state == "COMMITTED":
                return
            raise JournalError("Journal is not ready for completion")
        source = self.repository.get_source_file(journal.source_id, connection=connection)
        creation = journal.effect_plan.get("mutation") == "CREATE"
        if source is None or source.status != ("MISSING" if creation else "VALID"):
            raise AmbiguousSourceStateError("Source registration is unavailable")
        if (
            source.content_hash != journal.old_hash
            or source.revision + 1 != journal.intended_projection_revision
        ):
            raise AmbiguousSourceStateError("Database source revision is ambiguous")
        mutation_context = journal.effect_plan.get("edit_context") or journal.effect_plan.get(
            "save_context"
        )
        if mutation_context is not None:
            ids = list(connection.exec_driver_sql(
                "SELECT id FROM source_files WHERE note_date=?", (source.note_date,),
            ).scalars())
            if ids != [source.id]:
                raise AmbiguousSourceStateError("Source date became ambiguous")
        linked = self.repository.get_forms_for_source(source.id, connection=connection)
        if sorted(form.id for form in linked) != journal.effect_plan["links"]:
            raise AmbiguousSourceStateError("Source projection links changed")
        semantics = self._semantics(document)
        if set(semantics) != {effect["key"] for effect in journal.effect_plan["forms"]}:
            raise AmbiguousSourceStateError("Source effect plan does not match parsed identities")
        self._fault(fault, "BEFORE_PROJECTION")
        affected_ids = set(journal.effect_plan["links"])
        resets: list[str] = []
        for effect in journal.effect_plan["forms"]:
            semantic = semantics[effect["key"]]
            family = self.repository.get_family(effect["family_id"], connection=connection)
            if family is not None and family.root_lemma != semantic.family_root:
                raise AmbiguousSourceStateError("Canonical family identity changed")
            if family is None:
                if self.repository.get_families_for_root(
                    semantic.family_root, connection=connection
                ):
                    raise AmbiguousSourceStateError("Canonical family was concurrently created")
                family = self.repository.get_or_create_family(
                    semantic.family_root, effect["family_id"], connection=connection
                )
            old = self.repository.get_word_form(effect["form_id"], connection=connection)
            if effect["base_revision"] is None:
                if (
                    old is not None
                    or self.repository.get_word_form_by_identity(
                        semantic.lemma, semantic.part_of_speech, family.id, connection=connection
                    )
                    is not None
                ):
                    raise AmbiguousSourceStateError("Canonical form was concurrently created")
            elif (
                old is None
                or old.revision != effect["base_revision"]
                or _form_digest(old) != effect["base_hash"]
            ):
                raise AmbiguousSourceStateError("Canonical form changed since preparation")
            en, vi, examples, ipa_status, link_status = _projection_values(semantic, old)
            if "card_baseline" in effect:
                baseline = connection.exec_driver_sql(
                    "SELECT box,due_at,queue_revision FROM review_cards "
                    "WHERE card_id=? AND word_form_id=?",
                    (effect["card_id"], effect["form_id"]),
                ).first()
                card_values = list(baseline) if baseline is not None else None
                expected_card = effect["card_baseline"]
                if "edit_context" not in journal.effect_plan or expected_card is None:
                    if card_values != expected_card:
                        raise AmbiguousSourceStateError("Card changed since save preparation")
                elif card_values is None or card_values[2] < expected_card[2] or (
                    card_values[2] == expected_card[2] and card_values != expected_card
                ):
                    raise AmbiguousSourceStateError("Edit card identity or revision changed")
                # A published edit can await recovery while another review advances
                # this same card. The canonical form baseline above still authenticates
                # its learning content. Preserve those events and metadata schedules;
                # apply a planned learning reset once to the current card. Its receipt
                # remains the frozen original snapshot, just as after later reviews.
                refs = (
                    sorted([sorted(ref.to_dict().items()) for ref in old.source_refs])
                    if old else []
                )
                if json.dumps(refs, sort_keys=True) != effect["refs_baseline"]:
                    raise AmbiguousSourceStateError("Source membership changed since preparation")
            preserve = effect.get("preserve_canonical", False)
            if preserve and (
                old is None or mutation_context is None
                or [semantic.family_root, semantic.normalized_lemma, semantic.part_of_speech]
                in mutation_context["identities"]
                or effect["reset"]
            ):
                raise AmbiguousSourceStateError("Preserved form intent is inconsistent")
            needs_reset = not preserve and old is not None and _learning_values(old) != (
                semantic.meanings_en,
                semantic.meanings_vi,
                semantic.examples,
            )
            if effect["reset"] and not needs_reset:
                raise AmbiguousSourceStateError("Card reset evidence changed")
            changed = not preserve and _content_changed(semantic, old)
            form = (
                self.repository.save_canonical_word_form(
                    lemma=semantic.lemma,
                    part_of_speech=semantic.part_of_speech,
                    family_id=family.id,
                    meanings_en=en,
                    meanings_vi=vi,
                    examples=examples,
                    ipa_us=semantic.ipa_us,
                    ipa_status=ipa_status,
                    cambridge_url=semantic.cambridge_url,
                    cambridge_status=link_status,
                    word_form_id=effect["form_id"],
                    connection=connection,
                )
                if changed
                else old
            )
            if form is None:
                raise JournalError("Canonical projection was not applied")
            if changed and "receipt_time" in journal.effect_plan:
                connection.exec_driver_sql(
                    "UPDATE word_forms SET updated_at=? WHERE id=?",
                    (journal.effect_plan["receipt_time"], form.id),
                )
            self.repository.link_word_form_to_source(
                form.id, source.id, source.note_date, connection=connection
            )
            card = ensure_card(connection, card_id=effect["card_id"], word_form_id=form.id)
            if card.card_id != effect["card_id"]:
                raise AmbiguousSourceStateError("Card identity changed since preparation")
            if effect["reset"]:
                resets.append(card.card_id)
            affected_ids.add(form.id)
            self._fault(fault, "DURING_CANONICAL")
        for removed_id in journal.effect_plan["removed"]:
            self.repository.unlink_source_from_form(removed_id, source.id, connection=connection)
        projected_source = self.repository.save_source_file(
            source_id=source.id,
            relative_path=source.relative_path,
            note_date=source.note_date,
            status="VALID",
            revision=journal.intended_projection_revision,
            etag=f'"source-{source.id}-r{journal.intended_projection_revision}"',
            content_hash=journal.new_hash,
            last_parsed_at=_now(),
            connection=connection,
        )
        affected = [
            self.repository.get_word_form(form_id, connection=connection)
            for form_id in sorted(affected_ids)
        ]
        self.search_index.update_source(
            projected_source, [form for form in affected if form is not None], connection=connection
        )
        if apply_projection is not None:
            apply_projection(connection, journal)
        self._fault(fault, "AFTER_PROJECTION")
        for card_id in resets:
            reset_card_state(connection, card_id)
        if reset_cards is not None:
            reset_cards(connection, journal)
        self._fault(fault, "AFTER_CARD_RESET")
        context = journal.effect_plan.get("save_context")
        if context is not None:
            preview = connection.exec_driver_sql(
                "SELECT owner_session_id,status FROM lookup_previews WHERE lookup_id=?",
                (context["lookup_id"],),
            ).first()
            if (
                preview is None or preview[0] != context["owner"]
                or preview[1] not in {"PREVIEW", "CONSUMED"}
            ):
                raise AmbiguousSourceStateError("Preview authorization changed since preparation")
            connection.exec_driver_sql(
                "UPDATE lookup_previews SET status='CONSUMED' WHERE lookup_id=?",
                (context["lookup_id"],),
            )
        # Terminal filesystem consistency linearizes after all local effects/hooks.
        # A mismatch raises inside T014's transaction, rolling those effects back
        # before _complete persists DEGRADED in a separate short transaction.
        try:
            if creation:
                self.verify_creation(journal)
            terminal_hash = self.adapter.get_source_hash(journal.source_id)
        except SourceFileError:
            raise AmbiguousSourceStateError("Terminal source evidence is unavailable") from None
        if terminal_hash != journal.new_hash:
            raise AmbiguousSourceStateError("Terminal source hash differs from intended state")
        connection.exec_driver_sql(
            "UPDATE source_write_journal SET state='COMMITTED',updated_at=? WHERE operation_id=?",
            (_now(), journal.operation_id),
        )

    def _complete(
        self,
        journal: JournalRecord,
        *,
        operation_ledger: OperationLedger | None,
        response_status: int | None,
        result_ref: str | None,
        apply_projection: ProjectionApply | None,
        reset_cards: CardReset | None,
        fault: FaultInjector | None,
        publish: ProjectionApply | None = None,
        prepared_document: ParsedDocument | None = None,
    ) -> JournalRecord:
        if (response_status is not None and response_status != journal.response_status) or (
            result_ref is not None and result_ref != journal.result_ref
        ):
            raise JournalConflictError("Operation receipt intent changed")
        try:
            canonical = self.repository.get_source_file(journal.source_id)
            registered = self.adapter.get_source(journal.source_id)
            if (
                canonical is None
                or registered is None
                or canonical.relative_path != registered.relative_path
            ):
                raise JournalConflictError("Filesystem registration differs from canonical source")
            if publish is None:
                content = self.adapter.read_source_content(journal.source_id)
                if _hash(content) != journal.new_hash:
                    raise AmbiguousSourceStateError("Source hash is ambiguous")
                document = self._document(journal.source_id, content)
            else:
                if journal.state != "PREPARED" or prepared_document is None:
                    raise JournalError("Edit publication is not prepared")
                document = prepared_document
        except (SourceFileError, JournalConflictError, AmbiguousSourceStateError):
            self._transition(journal.operation_id, "DEGRADED")
            raise

        def local_write(connection: Connection) -> None:
            if publish is not None:
                publish(connection, journal)
            self._apply_local(
                connection,
                journal,
                document,
                apply_projection=apply_projection,
                reset_cards=reset_cards,
                fault=fault,
            )

        operation_ledger = operation_ledger or OperationLedger(self.engine)
        if operation_ledger.engine is not self.engine:
            raise JournalError("Source and receipt must share the database engine")
        operation = operation_ledger.get(journal.operation_id)
        if operation is None:
            raise JournalError("Operation record is missing")
        try:
            if operation.status == "UNKNOWN":
                operation_ledger.reconcile_source_write(
                    journal.operation_id,
                    expected_new_hash=journal.new_hash,
                    response_status=journal.response_status,
                    result_ref=journal.result_ref,
                    local_write=local_write,
                )
            elif operation.status == "SUCCEEDED":
                committed = self.get(journal.operation_id)
                if committed is None or committed.state != "COMMITTED":
                    raise JournalError("Receipt exists without committed source effects")
            else:
                operation_ledger.complete(
                    journal.operation_id,
                    response_status=journal.response_status,
                    result_ref=journal.result_ref,
                    local_write=local_write,
                )
        except (
            AmbiguousSourceStateError,
            ProjectionVersionMismatchError,
            StaleSourceRevisionError,
        ):
            self._transition(journal.operation_id, "DEGRADED")
            raise
        self._fault(fault, "AFTER_RECEIPT")
        result = self.get(journal.operation_id)
        if result is None or result.state != "COMMITTED":
            raise RuntimeError("Committed journal disappeared")
        source = self.repository.get_source_file(journal.source_id)
        if source is not None:
            self.adapter.register_source(source)
        return result

    def verify_creation(self, journal: JournalRecord) -> None:
        """A matching hash alone cannot identify the winning creator."""
        if journal.temp_path is None or journal.temp_device is None or journal.temp_inode is None:
            raise AmbiguousSourceStateError("Creation publication evidence is incomplete")
        self.adapter.reconcile_creation_temp(StagedTempHandle(
            journal.source_id, journal.temp_path, journal.temp_device, journal.temp_inode,
            journal.new_hash,
        ))

    def create(
        self, *, operation_id: str, note_date: str, new_content: str,
        operation_ledger: OperationLedger | None = None,
        response_status: int = 201, result_ref: str = "source_create",
        receipt_context: dict[str, Any] | None = None, fault: FaultInjector | None = None,
    ) -> JournalRecord:
        """Reserve a backend-generated date source and publish it conditionally."""
        prior = self.get(operation_id)
        if prior is not None:
            if prior.effect_plan.get("mutation") != "CREATE":
                raise JournalConflictError("Operation has a different source intent")
            source = self.repository.get_source_file(prior.source_id)
            if source is None or source.note_date != note_date:
                raise JournalConflictError("Operation has a different creation date")
            self.adapter.register_source(source)
            return self.write(
                operation_id=operation_id, source_id=prior.source_id,
                expected_old_hash=_hash(""), new_content=new_content,
                intended_projection_revision=1, operation_ledger=operation_ledger,
                response_status=response_status, result_ref=result_ref, fault=fault,
                creation=True, receipt_context=receipt_context,
            )
        source_id = f"src_{token_urlsafe(12)}"
        now = _now()
        source = SourceFile(
            source_id, self.adapter.creation_path(note_date), note_date, "MISSING", 0,
            f'"source-{source_id}-r0"', _hash(""), None, "CREATION_PENDING", now, now,
        )
        self.adapter.assert_creation_absent(source)
        self.adapter.register_source(source)
        return self.write(
            operation_id=operation_id, source_id=source_id, expected_old_hash=_hash(""),
            new_content=new_content, intended_projection_revision=1,
            operation_ledger=operation_ledger, response_status=response_status,
            result_ref=result_ref, fault=fault, creation=True, receipt_context=receipt_context,
        )

    def write(
        self,
        *,
        operation_id: str,
        source_id: str,
        expected_old_hash: str,
        new_content: str,
        intended_projection_revision: int,
        operation_ledger: OperationLedger | None = None,
        response_status: int = 200,
        result_ref: str = "source_write",
        apply_projection: ProjectionApply | None = None,
        reset_cards: CardReset | None = None,
        fault: FaultInjector | None = None,
        creation: bool = False,
        receipt_context: dict[str, Any] | None = None,
        edit_context: dict[str, Any] | None = None,
    ) -> JournalRecord:
        """Run PREPARED → safe replacement → projection/card/receipt → COMMITTED."""
        operation_ledger = operation_ledger or OperationLedger(self.engine)
        if operation_ledger.engine is not self.engine:
            raise JournalError("Source and receipt must share the database engine")
        OperationLedger.validate_receipt(response_status, result_ref)
        operation = operation_ledger.get(operation_id)
        if operation is None:
            raise JournalError("Operation record is missing")
        prior = self.get(operation_id)
        if prior is not None and (
            prior.source_id,
            prior.old_hash,
            prior.new_hash,
            prior.intended_projection_revision,
            prior.response_status,
            prior.result_ref,
        ) != (
            source_id,
            expected_old_hash,
            _hash(new_content),
            intended_projection_revision,
            response_status,
            result_ref,
        ):
            raise JournalConflictError("Operation has a different source intent")
        if prior is not None and prior.state == "COMMITTED":
            if operation.status != "SUCCEEDED":
                raise JournalError("Committed source is missing its receipt")
            return prior
        if prior is None and operation.status != "PENDING":
            raise UnknownOperationError("A new source write requires a pending operation")
        if prior is not None and prior.state == "ABORTED":
            raise JournalError("Operation was aborted")
        if prior is not None and prior.state == "DEGRADED":
            raise JournalBusyError("Source is degraded and requires explicit repair")
        if prior is not None:
            try:
                if prior.effect_plan.get("mutation") == "CREATE":
                    source = self.adapter.get_source(source_id)
                    if source is not None and self.adapter.creation_destination_absent(source):
                        raise JournalBusyError("Prepared creation requires startup reconciliation")
                    self.verify_creation(prior)
                actual_hash = self.adapter.get_source_hash(source_id)
            except (SourceFileError, AmbiguousSourceStateError):
                actual_hash = None
            if actual_hash == prior.new_hash:
                journal = (
                    self._transition(operation_id, "SOURCE_REPLACED")
                    if prior.state == "PREPARED"
                    else prior
                )
                return self._complete(
                    journal,
                    operation_ledger=operation_ledger,
                    response_status=response_status,
                    result_ref=result_ref,
                    apply_projection=apply_projection,
                    reset_cards=reset_cards,
                    fault=fault,
                )
            if actual_hash == prior.old_hash and prior.state == "PREPARED":
                raise JournalBusyError("Prepared operation requires startup reconciliation")
            self._transition(operation_id, "DEGRADED")
            raise JournalBusyError("Source state is ambiguous and requires explicit repair")

        journal = self.prepare(
            operation_id=operation_id,
            source_id=source_id,
            expected_old_hash=expected_old_hash,
            new_content=new_content,
            intended_projection_revision=intended_projection_revision,
            response_status=response_status,
            result_ref=result_ref,
            fault=fault,
            _require_new=True,
            creation=creation,
            receipt_context=receipt_context,
            edit_context=edit_context,
        )
        if journal.state == "COMMITTED":
            return journal
        if journal.state == "ABORTED":
            raise JournalError("Operation was aborted")
        staged = None
        crash = False
        try:
            staged = (
                self.adapter.prepare_staged_create(source_id, new_content)
                if creation else
                self.adapter.prepare_staged_write(source_id, new_content, expected_old_hash)
            )
            self._fault(fault, "BEFORE_TEMP_HANDLE")
            self._record_stage(journal, staged.recovery_handle)
            self._fault(fault, "AFTER_TEMP_FSYNC")
            if edit_context is not None:
                # Freeze evidence in PREPARED first, then serialize publication and
                # all completion effects inside T014's existing receipt transaction.
                # A crash rolls SQLite back to PREPARED; recovery already recognizes
                # the intended new hash and completes it without another replacement.
                # This also closes the gap in which an ordinary review could change
                # the frozen card after publication but before receipt completion.
                staged_edit = staged
                publication_context = journal.effect_plan["edit_context"]

                def publish_edit(connection: Connection, record: JournalRecord) -> None:
                    source = self.repository.get_source_file(source_id, connection=connection)
                    ids = list(connection.exec_driver_sql(
                        "SELECT id FROM source_files WHERE note_date=?",
                        (source.note_date if source is not None else "",),
                    ).scalars())
                    if source is None or ids != [source_id] or (
                        source.status != "VALID"
                        or source.revision + 1 != intended_projection_revision
                        or source.content_hash != expected_old_hash
                        or source.etag != publication_context["etag"]
                    ):
                        raise SourceFileError("REVISION_CONFLICT", "Source preconditions changed")
                    for effect in record.effect_plan["forms"]:
                        form = self.repository.get_word_form(
                            effect["form_id"], connection=connection,
                        )
                        if form is None or form.revision != effect["base_revision"] or (
                            _form_digest(form) != effect["base_hash"]
                        ):
                            raise SourceFileError("REVISION_CONFLICT", "Form changed")
                        if "card_baseline" in effect:
                            card = connection.exec_driver_sql(
                                "SELECT box,due_at,queue_revision FROM review_cards "
                                "WHERE card_id=?", (effect["card_id"],),
                            ).first()
                            refs = sorted([
                                sorted(ref.to_dict().items()) for ref in form.source_refs
                            ])
                            if (list(card) if card is not None else None) != (
                                effect["card_baseline"]
                            ) or json.dumps(refs, sort_keys=True) != effect["refs_baseline"]:
                                raise SourceFileError("REVISION_CONFLICT", "Learning state changed")
                    published = staged_edit.commit()
                    self._fault(fault, "AFTER_ATOMIC_REPLACE")
                    if published.new_content_hash != record.new_hash or (
                        self.adapter.get_source_hash(source_id) != record.new_hash
                    ):
                        raise AmbiguousSourceStateError("Replacement hash could not be confirmed")
                    connection.exec_driver_sql(
                        "UPDATE source_write_journal SET state='SOURCE_REPLACED',updated_at=? "
                        "WHERE operation_id=? AND state='PREPARED'",
                        (_now(), operation_id),
                    )
                    self._fault(fault, "AFTER_SOURCE_REPLACED")

                return self._complete(
                    journal, operation_ledger=operation_ledger, response_status=response_status,
                    result_ref=result_ref, apply_projection=apply_projection, reset_cards=reset_cards,
                    fault=fault, publish=publish_edit,
                    prepared_document=self._document(source_id, new_content),
                )
            if receipt_context is not None:
                with self._writer() as connection:
                    source = self.repository.get_source_file(source_id, connection=connection)
                    ids = list(connection.exec_driver_sql(
                        "SELECT id FROM source_files WHERE note_date=?",
                        (source.note_date if source is not None else "",),
                    ).scalars())
                    if source is None or ids != [source_id] or (
                        source.status != ("MISSING" if creation else "VALID")
                        or source.revision + 1 != intended_projection_revision
                        or source.content_hash != expected_old_hash
                    ):
                        raise SourceFileError("SOURCE_NOT_WRITABLE", "Source preconditions changed")
            receipt = staged.commit()
            self._fault(fault, "AFTER_ATOMIC_REPLACE")
            journal = self.get(operation_id) or journal
            if creation:
                self.verify_creation(journal)
            actual_hash = self.adapter.get_source_hash(source_id)
            if receipt.new_content_hash != journal.new_hash or actual_hash != journal.new_hash:
                self._transition(journal.operation_id, "DEGRADED")
                raise AmbiguousSourceStateError("Replacement hash could not be confirmed")
            journal = self._transition(journal.operation_id, "SOURCE_REPLACED")
            self._fault(fault, "AFTER_SOURCE_REPLACED")
            return self._complete(
                journal,
                operation_ledger=operation_ledger,
                response_status=response_status,
                result_ref=result_ref,
                apply_projection=apply_projection,
                reset_cards=reset_cards,
                fault=fault,
            )
        except InjectedCrash:
            crash = True
            raise
        except SourceFileError:
            actual = None
            try:
                if creation:
                    current = self.get(operation_id)
                    if current is not None and current.temp_path is not None:
                        self.verify_creation(current)
                actual = self.adapter.get_source_hash(source_id)
            except SourceFileError:
                actual = None
            if creation and actual is None:
                current = self.get(operation_id)
                source = self.adapter.get_source(source_id)
                if current is not None and source is not None:
                    try:
                        self.adapter.assert_creation_absent(source)
                    except SourceFileError:
                        self._transition(operation_id, "DEGRADED")
                    else:
                        self._abort(current, operation_ledger)
                raise
            if actual == expected_old_hash:
                current = self.get(journal.operation_id)
                if current is None:
                    raise JournalError("Journal disappeared") from None
                if current.state == "PREPARED":
                    self._abort(current, operation_ledger)
                elif current.state != "DEGRADED":
                    self._transition(journal.operation_id, "DEGRADED")
            elif actual == journal.new_hash:
                self._transition(journal.operation_id, "SOURCE_REPLACED")
            else:
                self._transition(journal.operation_id, "DEGRADED")
            raise
        finally:
            if staged is not None and not crash:
                staged.cleanup()

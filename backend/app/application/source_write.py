"""Crash-safe orchestration for Markdown source replacements (T022).

The filesystem adapter owns validation, staging, fsync and atomic replacement. This
module only records intent and coordinates short SQLite transactions around it.
Canonical vocabulary, search, card resets, receipt and the terminal marker share
one writer transaction. Recovery reconstructs the effects from persisted identifiers
and verified on-disk Markdown. Optional callbacks are fault-injection test seams.
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
from backend.app.application.operations import OperationLedger
from backend.app.markdown_sync.parser import ParsedDocument, SemanticForm, parse_markdown
from backend.app.review.models import ensure_card, reset_card_state
from backend.app.vocabulary.models import ExampleSentence, MeaningEn, MeaningVi, WordForm
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
    ) -> JournalRecord:
        """Persist PREPARED intent before calling any filesystem replacement."""
        new_hash = _hash(new_content)
        OperationLedger.validate_receipt(response_status, result_ref)
        document = self._document(source_id, new_content)
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
            if source["status"] != "VALID" or source["content_hash"] != expected_old_hash:
                raise JournalConflictError("Source revision or hash is stale")
            if int(source["revision"]) + 1 != intended_projection_revision:
                raise JournalConflictError("Projection revision is stale")
            if document.note_date != source["note_date"]:
                raise JournalConflictError("Source date changed")
            operation_status = connection.exec_driver_sql(
                "SELECT status FROM operations WHERE operation_id=?", (operation_id,)
            ).scalar_one_or_none()
            if operation_status != "PENDING":
                raise UnknownOperationError("A new source write requires a pending operation")
            plan = self._plan(connection, source_id, document)

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
        if self.adapter.get_source_hash(journal.source_id) != journal.old_hash:
            return self._transition(journal.operation_id, "DEGRADED")
        ledger = ledger or OperationLedger(self.engine)
        if ledger.engine is not self.engine:
            raise JournalError("Source and receipt must share the database engine")
        ledger.abort_source_write(journal.operation_id, expected_old_hash=journal.old_hash)
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
        if source is None or source.status != "VALID":
            raise JournalError("Source registration is unavailable")
        if (
            source.content_hash != journal.old_hash
            or source.revision + 1 != journal.intended_projection_revision
        ):
            raise AmbiguousSourceStateError("Database source revision is ambiguous")
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
            en = [
                next((m for m in old.meanings_en if m.text == text), MeaningEn(text))
                if old
                else MeaningEn(text)
                for text in semantic.meanings_en
            ]
            vi = [
                next((m for m in old.meanings_vi if m.text == text), MeaningVi(text))
                if old
                else MeaningVi(text)
                for text in semantic.meanings_vi
            ]
            examples = [
                next(
                    (e for e in old.examples if (e.english, e.vietnamese) == pair),
                    ExampleSentence(*pair),
                )
                if old
                else ExampleSentence(*pair)
                for pair in semantic.examples
            ]
            ipa_status = (
                old.ipa_status
                if old and old.ipa_us == semantic.ipa_us
                else "MISSING"
                if semantic.ipa_us is None
                else "UNVERIFIED"
            )
            link_status = (
                old.cambridge_status
                if old and old.cambridge_url == semantic.cambridge_url
                else "MISSING"
                if semantic.cambridge_url is None
                else "UNVERIFIED"
            )
            needs_reset = old is not None and _learning_values(old) != (
                semantic.meanings_en,
                semantic.meanings_vi,
                semantic.examples,
            )
            if effect["reset"] and not needs_reset:
                raise AmbiguousSourceStateError("Card reset evidence changed")
            changed = old is None or (
                old.meanings_en,
                old.meanings_vi,
                old.examples,
                old.ipa_us,
                old.cambridge_url,
            ) != (en, vi, examples, semantic.ipa_us, semantic.cambridge_url)
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
        # Terminal filesystem consistency linearizes after all local effects/hooks.
        # A mismatch raises inside T014's transaction, rolling those effects back
        # before _complete persists DEGRADED in a separate short transaction.
        try:
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
            content = self.adapter.read_source_content(journal.source_id)
            if _hash(content) != journal.new_hash:
                raise AmbiguousSourceStateError("Source hash is ambiguous")
            document = self._document(journal.source_id, content)
        except (SourceFileError, JournalConflictError, AmbiguousSourceStateError):
            self._transition(journal.operation_id, "DEGRADED")
            raise

        def local_write(connection: Connection) -> None:
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
        return result

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
                actual_hash = self.adapter.get_source_hash(source_id)
            except SourceFileError:
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
        )
        if journal.state == "COMMITTED":
            return journal
        if journal.state == "ABORTED":
            raise JournalError("Operation was aborted")
        staged = None
        crash = False
        try:
            staged = self.adapter.prepare_staged_write(source_id, new_content, expected_old_hash)
            self._fault(fault, "BEFORE_TEMP_HANDLE")
            self._record_stage(journal, staged.recovery_handle)
            self._fault(fault, "AFTER_TEMP_FSYNC")
            receipt = staged.commit()
            self._fault(fault, "AFTER_ATOMIC_REPLACE")
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
                actual = self.adapter.get_source_hash(source_id)
            except SourceFileError:
                actual = None
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

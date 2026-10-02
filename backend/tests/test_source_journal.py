"""Durable source journal and crash reconciliation tests (T022)."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

import pytest
from alembic import command
from alembic.script import ScriptDirectory
from backend.app.adapters.source_files import SourceFileAdapter, SourceFileError
from backend.app.application.operations import OperationConflict, OperationLedger
from backend.app.application.source_recovery import SourceRecovery
from backend.app.application.source_write import (
    AmbiguousSourceStateError,
    InjectedCrash,
    JournalBusyError,
    JournalConflictError,
    JournalRecord,
    JournalState,
    SourceWriteCoordinator,
)
from backend.app.persistence.database import Database, migration_config
from backend.app.review.models import ensure_card, record_review, reset_card_state
from backend.app.vocabulary.models import ExampleSentence, MeaningVi, SourceFile
from backend.app.vocabulary.repository import VocabularyRepository
from backend.app.vocabulary.search_index import SearchIndex
from sqlalchemy import Connection
from sqlalchemy.exc import IntegrityError

VALID_MD = """# 29-09-2026

## Tra cứu nhanh

| Từ/cụm từ | IPA (US) | Nghĩa ngắn | Ví dụ ngắn | Dịch ví dụ |
|---|---|---|---|---|
| {word} (adj.) | /a/ | meaning | example | ví dụ |
"""


def md(word: str) -> str:
    return VALID_MD.format(word=word)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def source(source_id: str, content_hash: str, revision: int = 1) -> SourceFile:
    return SourceFile(
        id=source_id,
        relative_path="29-09-2026.md",
        note_date="2026-09-29",
        status="VALID",
        revision=revision,
        etag=f'"source-{source_id}-r{revision}"',
        content_hash=content_hash,
        last_parsed_at="2026-10-02T00:00:00Z",
        error_code=None,
        created_at="2026-10-02T00:00:00Z",
        updated_at="2026-10-02T00:00:00Z",
    )


class Fixture:
    def __init__(
        self,
        tmp_path: Path,
        *,
        operation_key: str = "journal-key",
        old_content: str | None = None,
        new_content: str | None = None,
    ) -> None:
        self.root = tmp_path / "sources"
        self.root.mkdir()
        self.old = old_content or md("old")
        self.new = new_content or md("new")
        (self.root / "29-09-2026.md").write_bytes(self.old.encode("utf-8"))
        self.old_hash = digest(self.old)
        self.new_hash = digest(self.new)
        self.source = source("src_journal", self.old_hash)
        self.database = Database(tmp_path / "journal.db")
        self.database.initialize()
        VocabularyRepository(self.database.engine).save_source_file(
            source_id=self.source.id,
            relative_path=self.source.relative_path,
            note_date=self.source.note_date,
            status="VALID",
            revision=1,
            etag=self.source.etag,
            content_hash=self.old_hash,
        )
        self.adapter = SourceFileAdapter(self.root, {self.source.id: self.source})
        self.ledger = OperationLedger(self.database.engine)
        self.claimed = self.ledger.claim(
            kind="SAVE",
            key=operation_key,
            method="POST",
            path="/api/v1/sources",
            body={"sourceId": self.source.id, "content": self.new},
            preconditions={"sourceHash": self.old_hash},
        )
        self.coordinator = SourceWriteCoordinator(self.database.engine, self.adapter)
        self.projection_calls = 0
        self.reset_calls = 0

    @property
    def operation_id(self) -> str:
        return self.claimed.operation.operation_id

    def projection(self, connection: Connection, _journal: object) -> None:
        self.projection_calls += 1
        connection.exec_driver_sql(
            "CREATE TABLE IF NOT EXISTS synthetic_projection "
            "(source_id TEXT PRIMARY KEY, revision INTEGER NOT NULL, "
            "applied_count INTEGER NOT NULL)"
        )
        connection.exec_driver_sql(
            "INSERT INTO synthetic_projection(source_id,revision,applied_count) VALUES (?,?,1) "
            "ON CONFLICT(source_id) DO UPDATE SET revision=excluded.revision, "
            "applied_count=synthetic_projection.applied_count+1",
            (self.source.id, 2),
        )

    def reset(self, connection: Connection, _journal: object) -> None:
        self.reset_calls += 1
        connection.exec_driver_sql(
            "CREATE TABLE IF NOT EXISTS synthetic_card "
            "(card_id TEXT PRIMARY KEY, schedule TEXT NOT NULL, history INTEGER NOT NULL, "
            "applied_count INTEGER NOT NULL)"
        )
        connection.exec_driver_sql(
            "INSERT INTO synthetic_card(card_id,schedule,history,applied_count) "
            "VALUES ('card-1','RESET',1,1) "
            "ON CONFLICT(card_id) DO UPDATE SET schedule='RESET', "
            "applied_count=synthetic_card.applied_count+1"
        )

    def close(self) -> None:
        self.database.close()

    def durable_counts(self) -> tuple[int, int]:
        with self.database.engine.connect() as connection:
            tables = {
                str(row[0])
                for row in connection.exec_driver_sql(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            projection = (
                connection.exec_driver_sql(
                    "SELECT coalesce(applied_count,0) FROM synthetic_projection WHERE source_id=?",
                    (self.source.id,),
                ).scalar_one_or_none()
                if "synthetic_projection" in tables
                else None
            )
            reset = (
                connection.exec_driver_sql(
                    "SELECT coalesce(applied_count,0) FROM synthetic_card WHERE card_id='card-1'"
                ).scalar_one_or_none()
                if "synthetic_card" in tables
                else None
            )
            return int(projection or 0), int(reset or 0)


@pytest.fixture
def fixture(tmp_path: Path) -> Iterator[Fixture]:
    item = Fixture(tmp_path)
    try:
        yield item
    finally:
        item.close()


def run_write(fx: Fixture, **kwargs: object) -> JournalRecord:
    defaults: dict[str, object] = {
        "operation_id": fx.operation_id,
        "source_id": fx.source.id,
        "expected_old_hash": fx.old_hash,
        "new_content": fx.new,
        "intended_projection_revision": 2,
        "operation_ledger": fx.ledger,
        "result_ref": "save_journal_1",
        "apply_projection": fx.projection,
        "reset_cards": fx.reset,
    }
    defaults.update(kwargs)
    return fx.coordinator.write(**cast(Any, defaults))


def test_prepared_replace_projection_receipt_commit_is_durable(fixture: Fixture) -> None:
    result = run_write(fixture)

    assert result.state == "COMMITTED"
    assert (fixture.root / fixture.source.relative_path).read_text() == fixture.new
    operation = fixture.ledger.get(fixture.operation_id)
    assert operation is not None and operation.status == "SUCCEEDED"
    with fixture.database.engine.connect() as connection:
        row = connection.exec_driver_sql(
            "SELECT revision,content_hash FROM source_files WHERE id=?", (fixture.source.id,)
        ).one()
        assert row == (2, fixture.new_hash)
        assert fixture.projection_calls == 1
        assert fixture.reset_calls == 1


def test_failure_before_prepared_commit_leaves_no_journal_or_filesystem_effect(
    fixture: Fixture,
) -> None:
    def fault(point: str) -> None:
        if point == "BEFORE_PREPARED":
            raise InjectedCrash(point)

    with pytest.raises(InjectedCrash):
        run_write(fixture, fault=fault)
    assert fixture.coordinator.get(fixture.operation_id) is None
    operation = fixture.ledger.get(fixture.operation_id)
    assert operation is not None and operation.status == "PENDING"
    assert (fixture.root / fixture.source.relative_path).read_text() == fixture.old


@pytest.mark.parametrize(
    "point,expected_before_recovery,expected_after_recovery",
    [
        ("AFTER_PREPARED", "PREPARED", "ABORTED"),
        ("AFTER_TEMP_FSYNC", "PREPARED", "ABORTED"),
        ("AFTER_ATOMIC_REPLACE", "PREPARED", "COMMITTED"),
        ("AFTER_SOURCE_REPLACED", "SOURCE_REPLACED", "COMMITTED"),
        ("BEFORE_PROJECTION", "SOURCE_REPLACED", "COMMITTED"),
        ("AFTER_PROJECTION", "SOURCE_REPLACED", "COMMITTED"),
        ("AFTER_CARD_RESET", "SOURCE_REPLACED", "COMMITTED"),
    ],
)
def test_fault_boundaries_reconcile_without_duplicate_projection_or_reset(
    fixture: Fixture, point: str, expected_before_recovery: str, expected_after_recovery: str
) -> None:
    def fault(actual: str) -> None:
        if actual == point:
            raise InjectedCrash(point)

    with pytest.raises(InjectedCrash):
        run_write(fixture, fault=fault)
    row = fixture.coordinator.get(fixture.operation_id)
    assert row is not None and row.state == expected_before_recovery

    recovered = SourceRecovery(fixture.coordinator).reconcile(
        operation_ledger=fixture.ledger,
        result_ref="save_journal_1",
        apply_projection=fixture.projection,
        reset_cards=fixture.reset,
    )
    assert recovered and recovered[0].state == expected_after_recovery
    committed = fixture.coordinator.get(fixture.operation_id)
    assert committed is not None and committed.state == expected_after_recovery
    operation = fixture.ledger.get(fixture.operation_id)
    expected_operation = "SUCCEEDED" if expected_after_recovery == "COMMITTED" else "FAILED"
    assert operation is not None and operation.status == expected_operation
    assert fixture.durable_counts() == (
        (1, 1) if expected_after_recovery == "COMMITTED" else (0, 0)
    )


def test_database_failure_after_atomic_replace_reconciles_by_hash(fixture: Fixture) -> None:
    real_transition = fixture.coordinator._transition

    def fail_source_transition(operation_id: str, state: JournalState) -> JournalRecord:
        if state == "SOURCE_REPLACED":
            raise RuntimeError("synthetic database failure")
        return real_transition(operation_id, state)

    with (
        patch.object(fixture.coordinator, "_transition", side_effect=fail_source_transition),
        pytest.raises(RuntimeError, match="synthetic database failure"),
    ):
        run_write(fixture)
    journal = fixture.coordinator.get(fixture.operation_id)
    assert journal is not None and journal.state == "PREPARED"
    assert (fixture.root / fixture.source.relative_path).read_text() == fixture.new

    recovered = SourceRecovery(fixture.coordinator).reconcile(
        operation_ledger=fixture.ledger,
        apply_projection=fixture.projection,
        reset_cards=fixture.reset,
    )
    assert recovered[0].state == "COMMITTED"
    assert fixture.durable_counts() == (1, 1)


def test_committed_replay_is_noop_and_same_key_different_intent_is_rejected(
    fixture: Fixture,
) -> None:
    run_write(fixture)
    replay = fixture.ledger.claim(
        kind="SAVE",
        key="journal-key",
        method="POST",
        path="/api/v1/sources",
        body={"content": fixture.new, "sourceId": fixture.source.id},
        preconditions={"sourceHash": fixture.old_hash},
    )
    assert replay.replayed is True
    assert fixture.projection_calls == 1
    assert fixture.reset_calls == 1
    with pytest.raises(OperationConflict) as changed:
        fixture.ledger.claim(
            kind="SAVE",
            key="journal-key",
            method="POST",
            path="/api/v1/sources",
            body={"content": "different"},
            preconditions={"sourceHash": fixture.old_hash},
        )
    assert changed.value.code == "IDEMPOTENCY_KEY_REUSED"


def test_unknown_operation_never_replays_destructive_work(fixture: Fixture) -> None:
    def fault(point: str) -> None:
        if point == "AFTER_ATOMIC_REPLACE":
            raise InjectedCrash(point)

    with pytest.raises(InjectedCrash):
        run_write(fixture, fault=fault)
    assert fixture.ledger.recover_pending() == 1
    recovered = SourceRecovery(fixture.coordinator).reconcile(
        operation_ledger=fixture.ledger,
        apply_projection=fixture.projection,
        reset_cards=fixture.reset,
    )
    assert recovered[0].state == "COMMITTED"
    operation = fixture.ledger.get(fixture.operation_id)
    assert operation is not None and operation.status == "SUCCEEDED"
    assert fixture.projection_calls == 1
    assert fixture.reset_calls == 1
    assert (fixture.root / fixture.source.relative_path).read_text() == fixture.new


def test_receipt_and_committed_boundaries_are_atomic_and_idempotent(fixture: Fixture) -> None:
    def fault(point: str) -> None:
        if point == "AFTER_RECEIPT":
            raise InjectedCrash(point)

    with pytest.raises(InjectedCrash):
        run_write(fixture, fault=fault)
    journal = fixture.coordinator.get(fixture.operation_id)
    operation = fixture.ledger.get(fixture.operation_id)
    assert journal is not None and journal.state == "COMMITTED"
    assert operation is not None and operation.status == "SUCCEEDED"
    assert fixture.durable_counts() == (1, 1)
    assert SourceRecovery(fixture.coordinator).reconcile() == []
    replay = run_write(fixture)
    assert replay.state == "COMMITTED"
    assert fixture.durable_counts() == (1, 1)


def test_external_hash_is_degraded_and_destructive_writes_are_blocked(fixture: Fixture) -> None:
    fixture.coordinator.prepare(
        operation_id=fixture.operation_id,
        source_id=fixture.source.id,
        expected_old_hash=fixture.old_hash,
        new_content=fixture.new,
        intended_projection_revision=2,
    )
    external = md("external")
    (fixture.root / fixture.source.relative_path).write_bytes(external.encode("utf-8"))

    recovered = SourceRecovery(fixture.coordinator).reconcile()
    assert recovered[0].state == "DEGRADED"
    assert (fixture.root / fixture.source.relative_path).read_text() == external
    assert fixture.projection_calls == 0
    with pytest.raises(JournalBusyError):
        fixture.coordinator.prepare(
            operation_id="op_second",
            source_id=fixture.source.id,
            expected_old_hash=digest(external),
            new_content=fixture.new,
            intended_projection_revision=2,
        )
    with pytest.raises(RuntimeError):
        SourceRecovery(fixture.coordinator).assert_writable(fixture.source.id)


def test_old_state_after_prepared_is_aborted_without_history_mutation(fixture: Fixture) -> None:
    fixture.coordinator.prepare(
        operation_id=fixture.operation_id,
        source_id=fixture.source.id,
        expected_old_hash=fixture.old_hash,
        new_content=fixture.new,
        intended_projection_revision=2,
    )
    recovered = SourceRecovery(fixture.coordinator).reconcile(
        operation_ledger=fixture.ledger,
        apply_projection=fixture.projection,
        reset_cards=fixture.reset,
    )
    assert recovered[0].state == "ABORTED"
    operation = fixture.ledger.get(fixture.operation_id)
    assert operation is not None and operation.status == "FAILED"
    assert fixture.projection_calls == 0
    assert fixture.reset_calls == 0
    assert (fixture.root / fixture.source.relative_path).read_text() == fixture.old


def test_t031_card_reset_is_transactional_append_only_and_replay_safe(fixture: Fixture) -> None:
    repository = VocabularyRepository(fixture.database.engine)
    family = repository.get_or_create_family("robust")
    form = repository.save_canonical_word_form(
        lemma="robust", part_of_speech="ADJECTIVE", family_id=family.id
    )
    repository.link_word_form_to_source(form.id, fixture.source.id, fixture.source.note_date)
    history_operation = fixture.ledger.claim(
        kind="REVIEW",
        key="history-key",
        method="POST",
        path="/api/v1/reviews",
        body={"cardId": "card-history"},
        preconditions={},
    )
    with (
        fixture.database.engine.connect().execution_options(
            sqlite_begin_immediate=True
        ) as connection,
        connection.begin(),
    ):
        card = ensure_card(connection, card_id="card-history", word_form_id=form.id)
        record_review(
            connection,
            card_id=card.card_id,
            event_id="review-history-1",
            operation_id=history_operation.operation.operation_id,
            source="FLASHCARD",
            rating="GOOD",
            reviewed_at=datetime(2026, 10, 2, tzinfo=UTC),
        )

    write_operation = fixture.ledger.claim(
        kind="SAVE",
        key="card-reset-key",
        method="POST",
        path="/api/v1/sources",
        body={"sourceId": fixture.source.id, "content": "new"},
        preconditions={"sourceHash": fixture.old_hash},
    )

    def reset_existing_card(connection: Connection, _journal: object) -> None:
        reset_card_state(connection, "card-history")

    def fault(point: str) -> None:
        if point == "AFTER_CARD_RESET":
            raise InjectedCrash(point)

    with pytest.raises(InjectedCrash):
        fixture.coordinator.write(
            operation_id=write_operation.operation.operation_id,
            source_id=fixture.source.id,
            expected_old_hash=fixture.old_hash,
            new_content=fixture.new,
            intended_projection_revision=2,
            operation_ledger=fixture.ledger,
            result_ref="save_card_reset",
            reset_cards=reset_existing_card,
            fault=fault,
        )
    SourceRecovery(fixture.coordinator).reconcile(
        operation_ledger=fixture.ledger,
        result_ref="save_card_reset",
        reset_cards=reset_existing_card,
    )
    with fixture.database.engine.connect() as connection:
        card_row = connection.exec_driver_sql(
            "SELECT box,due_at,queue_revision FROM review_cards WHERE card_id='card-history'"
        ).one()
        assert card_row[0] == 0 and card_row[1] is None and card_row[2] == 2
        assert (
            connection.exec_driver_sql(
                "SELECT count(*) FROM review_events WHERE card_id='card-history'"
            ).scalar_one()
            == 1
        )


def test_same_source_intents_are_serialized_and_stale_hash_is_refused(fixture: Fixture) -> None:
    fixture.coordinator.prepare(
        operation_id=fixture.operation_id,
        source_id=fixture.source.id,
        expected_old_hash=fixture.old_hash,
        new_content=fixture.new,
        intended_projection_revision=2,
    )
    other = fixture.ledger.claim(
        kind="SAVE",
        key="second-source-key",
        method="POST",
        path="/api/v1/sources",
        body={"sourceId": fixture.source.id, "content": "other"},
        preconditions={"sourceHash": fixture.old_hash},
    )
    with pytest.raises(JournalBusyError):
        fixture.coordinator.prepare(
            operation_id=other.operation.operation_id,
            source_id=fixture.source.id,
            expected_old_hash=fixture.old_hash,
            new_content=md("other"),
            intended_projection_revision=2,
        )


def test_stale_source_hash_is_refused_without_last_write_wins(fixture: Fixture) -> None:
    newer = md("already-new")
    newer_hash = digest(newer)
    (fixture.root / fixture.source.relative_path).write_bytes(newer.encode("utf-8"))
    with fixture.database.engine.begin() as connection:
        connection.exec_driver_sql(
            "UPDATE source_files SET revision=2,content_hash=? WHERE id=?",
            (newer_hash, fixture.source.id),
        )
    with pytest.raises(JournalConflictError):
        fixture.coordinator.prepare(
            operation_id=fixture.operation_id,
            source_id=fixture.source.id,
            expected_old_hash=fixture.old_hash,
            new_content=md("other"),
            intended_projection_revision=2,
        )


def test_temp_write_failure_aborts_receipt_and_preserves_original(fixture: Fixture) -> None:
    def fail_staging(*_args: object, **_kwargs: object) -> object:
        raise SourceFileError("IO_ERROR", "synthetic staging failure", fixture.source.id)

    with (
        patch.object(fixture.adapter, "prepare_staged_write", side_effect=fail_staging),
        pytest.raises(SourceFileError),
    ):
        run_write(fixture)
    journal = fixture.coordinator.get(fixture.operation_id)
    operation = fixture.ledger.get(fixture.operation_id)
    assert journal is not None and journal.state == "ABORTED"
    assert operation is not None and operation.status == "FAILED"
    assert (fixture.root / fixture.source.relative_path).read_text() == fixture.old


def test_journal_constraints_preserve_evidence_and_reject_invalid_transitions(
    fixture: Fixture,
) -> None:
    run_write(fixture)
    with fixture.database.engine.begin() as connection:
        with pytest.raises(IntegrityError):
            connection.exec_driver_sql(
                "UPDATE source_write_journal SET state='PREPARED' WHERE operation_id=?",
                (fixture.operation_id,),
            )
        with pytest.raises(IntegrityError):
            connection.exec_driver_sql(
                "INSERT OR REPLACE INTO source_write_journal "
                "(operation_id,source_id,old_hash,new_hash,intended_projection_revision,state,"
                "created_at,updated_at) "
                "VALUES (?,?,?,?,?,'PREPARED','x','x')",
                (fixture.operation_id, fixture.source.id, fixture.old_hash, fixture.new_hash, 2),
            )
        with pytest.raises(IntegrityError):
            connection.exec_driver_sql(
                "DELETE FROM source_write_journal WHERE operation_id=?", (fixture.operation_id,)
            )


def test_migration_from_review_through_admission_preserves_all_seeded_rows(tmp_path: Path) -> None:
    database = Database(tmp_path / "predecessor.db")
    config = migration_config()
    scripts = ScriptDirectory.from_config(config)
    assert scripts.get_heads() == ["0007_source_journal"]
    admission = scripts.get_revision("0006_ai_admission")
    journal = scripts.get_revision("0007_source_journal")
    assert admission is not None and admission.down_revision == "0005_review"
    assert journal is not None and journal.down_revision == "0006_ai_admission"
    try:
        with database.engine.begin() as conn:
            config.attributes["connection"] = conn
            command.upgrade(config, "0005_review")
        repo = VocabularyRepository(database.engine)
        ledger = OperationLedger(database.engine)
        family = repo.get_or_create_family("seed")
        form = repo.save_canonical_word_form(
            lemma="seed",
            part_of_speech="NOUN",
            family_id=family.id,
            meanings_vi=[MeaningVi("hạt giống")],
            examples=[ExampleSentence("A seed.", "Hạt giống.")],
        )
        src = repo.save_source_file(
            source_id="src_seed",
            relative_path="29-09-2026.md",
            note_date="2026-09-29",
            content_hash=digest(md("seed")),
        )
        repo.link_word_form_to_source(form.id, src.id, src.note_date)
        review = ledger.claim(
            kind="REVIEW",
            key="seed-review",
            method="POST",
            path="/api/v1/reviews",
            body={"cardId": "seed-card"},
            preconditions={},
        )
        ai = ledger.claim(
            kind="LOOKUP",
            key="seed-ai",
            method="POST",
            path="/api/v1/lookup",
            body={"term": "seed"},
            preconditions={},
        )
        consent = ledger.claim(
            kind="CONSENT",
            key="seed-consent",
            method="POST",
            path="/api/v1/consent",
            body={},
            preconditions={},
        )
        with (
            database.engine.connect().execution_options(sqlite_begin_immediate=True) as conn,
            conn.begin(),
        ):
            ensure_card(conn, card_id="seed-card", word_form_id=form.id)
            record_review(
                conn,
                card_id="seed-card",
                event_id="seed-event",
                operation_id=review.operation.operation_id,
                source="QUIZ",
                rating="GOOD",
                attempt_id="seed-attempt",
                question_id="seed-question",
                reviewed_at=datetime(2026, 10, 2, tzinfo=UTC),
            )
            conn.exec_driver_sql(
                "INSERT INTO ai_consent_event "
                "(event_id,revision,action,policy_version,policy_digest,scopes,dispatch_rules,"
                "created_at,operation_id) VALUES ('seed-consent',1,'GRANTED','v1',?,'[]','[]',?,?)",
                ("a" * 64, "2026-10-02T00:00:00Z", consent.operation.operation_id),
            )
        with database.engine.begin() as conn:
            config.attributes["connection"] = conn
            command.upgrade(config, "0006_ai_admission")
            conn.exec_driver_sql(
                "INSERT INTO ai_operation_admission VALUES "
                "(?,1,'v1',?,'LOOKUP','Antigravity/Google','gemini-3.8-flash-high','primary',"
                "'configured-account','ADMITTED','2026-10-02T00:00:00Z')",
                (ai.operation.operation_id, "a" * 64),
            )
        tables = [
            "word_families",
            "word_forms",
            "source_files",
            "word_form_sources",
            "operations",
            "operation_keys",
            "review_cards",
            "review_events",
            "ai_consent_event",
            "ai_consent_state",
            "ai_operation_admission",
        ]
        with database.engine.connect() as conn:
            before = {
                table: conn.exec_driver_sql(f"SELECT * FROM {table} ORDER BY 1").all()
                for table in tables
            }
        config.attributes.pop("connection", None)
        assert database.initialize().schema_revision == "0007_source_journal"
        assert database.initialize().schema_revision == "0007_source_journal"
        with database.engine.connect() as conn:
            for table in tables:
                assert (
                    conn.exec_driver_sql(f"SELECT * FROM {table} ORDER BY 1").all() == before[table]
                )
            assert (
                conn.exec_driver_sql("SELECT count(*) FROM source_write_journal").scalar_one() == 0
            )
            assert conn.exec_driver_sql("PRAGMA foreign_key_check").all() == []
            assert conn.exec_driver_sql("PRAGMA integrity_check").scalar_one() == "ok"
        with (
            pytest.raises(RuntimeError, match="preserve source journal history"),
            database.engine.begin() as conn,
        ):
            config.attributes["connection"] = conn
            command.downgrade(config, "0006_ai_admission")
    finally:
        database.close()


def real_markdown(meaning: str, ipa: str = "/a/") -> str:
    return (
        md("robust")
        + f"""
## Robust

| Từ/cụm từ | Từ loại | IPA (US) | Trọng âm | Nguồn |
|---|---|---|---|---|
| robust | adjective | {ipa} | first | [Cambridge](https://cambridge.org/robust) |

### Ý nghĩa

{meaning}

### Ví dụ

Example.

*Bản dịch:* Ví dụ.
"""
    )


class RealFixture(Fixture):
    def __init__(self, tmp_path: Path) -> None:
        super().__init__(
            tmp_path, old_content=real_markdown("cũ"), new_content=real_markdown("bền vững")
        )
        self.old_hash, self.new_hash = digest(self.old), digest(self.new)
        (self.root / self.source.relative_path).write_bytes(self.old.encode())
        self.source = source(self.source.id, self.old_hash)
        self.adapter.register_source(self.source)
        self.repo = VocabularyRepository(self.database.engine)
        self.repo.save_source_file(
            source_id=self.source.id,
            relative_path=self.source.relative_path,
            note_date=self.source.note_date,
            content_hash=self.old_hash,
        )
        family = self.repo.get_or_create_family("robust")
        self.form = self.repo.save_canonical_word_form(
            lemma="robust",
            part_of_speech="ADJECTIVE",
            family_id=family.id,
            meanings_vi=[MeaningVi("cũ")],
            examples=[ExampleSentence("Example.", "Ví dụ.")],
            ipa_us="/a/",
            cambridge_url="https://cambridge.org/robust",
        )
        self.repo.link_word_form_to_source(self.form.id, self.source.id, self.source.note_date)
        self.index = SearchIndex(self.database.engine)
        self.index.update_source(self.source, self.repo.get_forms_for_source(self.source.id))
        history_op = self.ledger.claim(
            kind="REVIEW",
            key="real-history",
            method="POST",
            path="/api/v1/reviews",
            body={"cardId": "real-card"},
            preconditions={},
        )
        with (
            self.database.engine.connect().execution_options(sqlite_begin_immediate=True) as conn,
            conn.begin(),
        ):
            ensure_card(conn, card_id="real-card", word_form_id=self.form.id)
            record_review(
                conn,
                card_id="real-card",
                event_id="real-event",
                operation_id=history_op.operation.operation_id,
                source="QUIZ",
                rating="GOOD",
                attempt_id="attempt-preserved",
                question_id="question-preserved",
                reviewed_at=datetime(2026, 10, 2, tzinfo=UTC),
            )
        self.ledger.complete(
            history_op.operation.operation_id, response_status=200, result_ref="review_preserved"
        )
        with self.database.engine.connect() as conn:
            self.history = conn.exec_driver_sql("SELECT * FROM review_events").all()
            self.old_card = conn.exec_driver_sql("SELECT * FROM review_cards").all()

    def assert_effects(self, *, committed: bool, reset: bool = True) -> None:
        with self.database.engine.connect() as conn:
            assert conn.exec_driver_sql("SELECT * FROM review_events").all() == self.history
            assert conn.exec_driver_sql("SELECT count(*) FROM review_cards").scalar_one() == 1
            assert conn.exec_driver_sql(
                "SELECT box,queue_revision FROM review_cards WHERE card_id='real-card'"
            ).one() == ((0, 2) if committed and reset else (1, 1))
            assert conn.exec_driver_sql(
                "SELECT revision,content_hash FROM source_files WHERE id=?", (self.source.id,)
            ).one() == ((2, self.new_hash) if committed else (1, self.old_hash))
            assert conn.exec_driver_sql(
                "SELECT revision FROM search_projection_sources WHERE source_id=?",
                (self.source.id,),
            ).scalar_one() == (2 if committed else 1)
        updated = self.repo.get_word_form(self.form.id)
        assert updated is not None
        assert updated.id == self.form.id
        assert updated.revision == (2 if committed else 1)
        assert [m.text for m in updated.meanings_vi] == (
            ["bền vững"] if committed and reset else ["cũ"]
        )
        assert bool(self.index.search("ben vung")) == (committed and reset)
        operation = self.ledger.get(self.operation_id)
        assert operation is not None
        if committed:
            assert operation.status == "SUCCEEDED" and operation.result_ref == "save_journal_1"
        else:
            assert operation.status != "SUCCEEDED" and operation.result_ref is None

    def restart(self, *, mark_unknown: bool = True) -> SourceRecovery:
        self.database.close()
        self.database = Database(self.root.parent / "journal.db")
        self.database.initialize()
        self.ledger = OperationLedger(self.database.engine)
        if mark_unknown:
            self.ledger.recover_pending()
        self.repo = VocabularyRepository(self.database.engine)
        self.index = SearchIndex(self.database.engine)
        self.adapter = SourceFileAdapter(self.root, {self.source.id: self.source})
        self.coordinator = SourceWriteCoordinator(self.database.engine, self.adapter)
        return SourceRecovery(self.coordinator)


@pytest.fixture
def real_fixture(tmp_path: Path) -> Iterator[RealFixture]:
    fx = RealFixture(tmp_path)
    try:
        yield fx
    finally:
        fx.close()


@pytest.mark.parametrize("mark_unknown", [False, True])
@pytest.mark.parametrize(
    "point,state",
    [
        ("BEFORE_PREPARED", None),
        ("AFTER_PREPARED", "PREPARED"),
        ("BEFORE_TEMP_HANDLE", "PREPARED"),
        ("AFTER_TEMP_FSYNC", "PREPARED"),
        ("AFTER_ATOMIC_REPLACE", "PREPARED"),
        ("AFTER_SOURCE_REPLACED", "SOURCE_REPLACED"),
        ("BEFORE_PROJECTION", "SOURCE_REPLACED"),
        ("DURING_CANONICAL", "SOURCE_REPLACED"),
        ("AFTER_PROJECTION", "SOURCE_REPLACED"),
        ("AFTER_CARD_RESET", "SOURCE_REPLACED"),
        ("AFTER_RECEIPT", "COMMITTED"),
    ],
)
def test_real_crash_matrix_reconstructs_effects_after_restart_without_callbacks(
    real_fixture: RealFixture,
    point: str,
    state: str | None,
    mark_unknown: bool,
) -> None:
    fx = real_fixture
    old_disk = point in {
        "BEFORE_PREPARED",
        "AFTER_PREPARED",
        "BEFORE_TEMP_HANDLE",
        "AFTER_TEMP_FSYNC",
    }

    def crash(actual: str) -> None:
        if actual == point:
            raise InjectedCrash(point)

    with pytest.raises(InjectedCrash):
        run_write(fx, apply_projection=None, reset_cards=None, fault=crash)
    journal = fx.coordinator.get(fx.operation_id)
    assert (journal.state if journal else None) == state
    assert (fx.root / fx.source.relative_path).read_text() == (fx.old if old_disk else fx.new)
    fx.assert_effects(committed=state == "COMMITTED")
    recovery = fx.restart(mark_unknown=mark_unknown)
    with patch.object(fx.adapter, "prepare_staged_write", side_effect=AssertionError("no replay")):
        recovered = recovery.reconcile(operation_ledger=fx.ledger)
        assert recovery.reconcile(operation_ledger=fx.ledger) == []
    if state is not None:
        journal = fx.coordinator.get(fx.operation_id)
        assert journal is not None and journal.state == ("ABORTED" if old_disk else "COMMITTED")
        if point == "BEFORE_TEMP_HANDLE":
            residue = list(fx.root.glob(".*.tmp"))
            assert len(residue) == 1 and residue[0].read_text() == fx.new
        else:
            assert not list(fx.root.glob(".*.tmp"))
    else:
        assert recovered == []
    fx.assert_effects(committed=not old_disk)


def test_real_external_h3_preserves_history_and_blocks_writes(real_fixture: RealFixture) -> None:
    fx = real_fixture

    def crash(point: str) -> None:
        if point == "AFTER_ATOMIC_REPLACE":
            raise InjectedCrash(point)

    with pytest.raises(InjectedCrash):
        run_write(fx, apply_projection=None, reset_cards=None, fault=crash)
    external = real_markdown("external H3")
    assert digest(external) not in {fx.old_hash, fx.new_hash}
    (fx.root / fx.source.relative_path).write_bytes(external.encode())
    recovery = fx.restart()
    assert recovery.reconcile(operation_ledger=fx.ledger)[0].state == "DEGRADED"
    assert recovery.reconcile(operation_ledger=fx.ledger) == []
    with pytest.raises(JournalBusyError):
        run_write(fx, apply_projection=None, reset_cards=None)
    with pytest.raises(RuntimeError):
        recovery.assert_writable(fx.source.id)
    assert (fx.root / fx.source.relative_path).read_text() == external
    fx.assert_effects(committed=False)


@pytest.mark.parametrize("restarted_unknown", [False, True], ids=["normal", "UNKNOWN"])
@pytest.mark.parametrize("fault_point", ["AFTER_PROJECTION", "AFTER_CARD_RESET"])
@pytest.mark.parametrize("external_edit", [True, False], ids=["H3", "H2-control"])
def test_terminal_evidence_after_local_effects(
    real_fixture: RealFixture, restarted_unknown: bool, fault_point: str, external_edit: bool
) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    fx = real_fixture
    recovery = SourceRecovery(fx.coordinator)
    if restarted_unknown:

        def crash(boundary: str) -> None:
            if boundary == "AFTER_ATOMIC_REPLACE":
                raise InjectedCrash(boundary)

        with pytest.raises(InjectedCrash):
            run_write(fx, apply_projection=None, reset_cards=None, fault=crash)
        recovery = fx.restart()
        operation = fx.ledger.get(fx.operation_id)
        assert operation is not None and operation.status == "UNKNOWN"

    reached, release = Event(), Event()

    def hold(point: str) -> None:
        if point == fault_point:
            reached.set()
            assert release.wait(5), "External editor did not release completion"

    external = real_markdown("external H3 during completion")
    assert digest(external) not in {fx.old_hash, fx.new_hash}
    target = fx.root / fx.source.relative_path
    tables = (
        "source_files",
        "word_families",
        "word_forms",
        "word_form_sources",
        "search_projection_sources",
        "search_projection_entries",
        "search_projection_ngrams",
        "review_cards",
        "review_events",
    )
    with fx.database.engine.connect() as connection:
        before = {
            table: connection.exec_driver_sql(f"SELECT * FROM {table} ORDER BY 1,2").all()
            for table in tables
        }

    def complete() -> None:
        if restarted_unknown:
            recovery.reconcile(operation_ledger=fx.ledger, fault=hold)
        else:
            run_write(fx, apply_projection=None, reset_cards=None, fault=hold)

    with (
        patch("backend.app.adapters.source_files.os.replace", wraps=os.replace) as replace,
        ThreadPoolExecutor(max_workers=1) as pool,
    ):
        pending = pool.submit(complete)
        try:
            assert reached.wait(5), "Completion did not reach the late boundary"
            assert target.read_bytes() == fx.new.encode()
            if external_edit:
                # The test thread is the external editor; no timing sleeps are needed.
                target.write_bytes(external.encode())
        finally:
            release.set()
        if external_edit and not restarted_unknown:
            with pytest.raises(AmbiguousSourceStateError):
                pending.result(timeout=5)
        else:
            pending.result(timeout=5)

        journal = fx.coordinator.get(fx.operation_id)
        assert journal is not None
        assert journal.state == ("DEGRADED" if external_edit else "COMMITTED")
        fx.assert_effects(committed=not external_edit)
        assert target.read_bytes() == (external if external_edit else fx.new).encode()
        assert replace.call_count == (0 if restarted_unknown else 1)
        if external_edit:
            with fx.database.engine.connect() as connection:
                for table in tables:
                    assert (
                        connection.exec_driver_sql(f"SELECT * FROM {table} ORDER BY 1,2").all()
                        == before[table]
                    )
            operation = fx.ledger.get(fx.operation_id)
            assert operation is not None
            assert operation.status == ("UNKNOWN" if restarted_unknown else "PENDING")
            assert operation.response_status is None and operation.result_ref is None

        # A fresh process cannot reapply rolled-back effects or terminalize DEGRADED.
        recovery = fx.restart()
        assert recovery.reconcile(operation_ledger=fx.ledger) == []
        if external_edit:
            with pytest.raises(RuntimeError, match="degraded"):
                recovery.assert_writable(fx.source.id)
            with pytest.raises(JournalBusyError, match="degraded"):
                run_write(fx, apply_projection=None, reset_cards=None)
            next_intent = fx.ledger.claim(
                kind="SAVE",
                key="after-terminal-H3",
                method="POST",
                path="/api/v1/sources",
                body={"content": fx.new},
                preconditions={"sourceHash": fx.old_hash},
            )
            with pytest.raises(JournalBusyError, match="degraded"):
                run_write(
                    fx,
                    operation_id=next_intent.operation.operation_id,
                    apply_projection=None,
                    reset_cards=None,
                )
            degraded = fx.coordinator.get(fx.operation_id)
            assert degraded is not None and degraded.state == "DEGRADED"
            with fx.database.engine.connect() as connection:
                for table in tables:
                    assert (
                        connection.exec_driver_sql(f"SELECT * FROM {table} ORDER BY 1,2").all()
                        == before[table]
                    )
        else:
            assert run_write(fx, apply_projection=None, reset_cards=None).state == "COMMITTED"
        fx.assert_effects(committed=not external_edit)
        assert target.read_bytes() == (external if external_edit else fx.new).encode()
        assert replace.call_count == (0 if restarted_unknown else 1)


def test_real_replay_and_changed_intent_cannot_duplicate_effects(real_fixture: RealFixture) -> None:
    fx = real_fixture
    with patch.object(
        fx.adapter, "prepare_staged_write", wraps=fx.adapter.prepare_staged_write
    ) as staged:
        run_write(fx, apply_projection=None, reset_cards=None)
        assert run_write(fx, apply_projection=None, reset_cards=None).state == "COMMITTED"
        assert staged.call_count == 1
        with pytest.raises(JournalConflictError):
            run_write(
                fx, new_content=real_markdown("changed"), apply_projection=None, reset_cards=None
            )
    replay = fx.ledger.claim(
        kind="SAVE",
        key="journal-key",
        method="POST",
        path="/api/v1/sources",
        body={"sourceId": fx.source.id, "content": fx.new},
        preconditions={"sourceHash": fx.old_hash},
    )
    assert replay.replayed and replay.operation.operation_id == fx.operation_id
    with pytest.raises(OperationConflict) as conflict:
        fx.ledger.claim(
            kind="SAVE",
            key="journal-key",
            method="POST",
            path="/api/v1/sources",
            body={"sourceId": fx.source.id, "content": real_markdown("changed")},
            preconditions={"sourceHash": fx.old_hash},
        )
    assert conflict.value.code == "IDEMPOTENCY_KEY_REUSED"
    with fx.database.engine.connect() as conn:
        assert (
            conn.exec_driver_sql(
                "SELECT count(*) FROM operation_keys WHERE operation_id=?", (fx.operation_id,)
            ).scalar_one()
            == 1
        )
    fx.assert_effects(committed=True)
    fx.restart().reconcile(operation_ledger=fx.ledger)
    fx.assert_effects(committed=True)


def test_ipa_only_change_preserves_current_schedule(real_fixture: RealFixture) -> None:
    fx = real_fixture
    fx.new = real_markdown("cũ", ipa="/b/")
    fx.new_hash = digest(fx.new)
    run_write(fx, apply_projection=None, reset_cards=None)
    fx.assert_effects(committed=True, reset=False)
    updated = fx.repo.get_word_form(fx.form.id)
    assert updated is not None and updated.ipa_us == "/b/"


def test_real_concurrent_intents_have_one_winner_and_no_writer_lock_over_filesystem(
    real_fixture: RealFixture,
) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    fx = real_fixture
    other = fx.ledger.claim(
        kind="SAVE",
        key="concurrent-source",
        method="POST",
        path="/api/v1/sources",
        body={"content": "other"},
        preconditions={"sourceHash": fx.old_hash},
    )
    prepared, release = Event(), Event()

    def hold(point: str) -> None:
        if point == "AFTER_PREPARED":
            prepared.set()
            assert release.wait(5)

    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(run_write, fx, apply_projection=None, reset_cards=None, fault=hold)
        try:
            assert prepared.wait(5)
            # This independent writer transaction must not wait on filesystem work.
            with fx.database.engine.begin() as conn:
                conn.exec_driver_sql("CREATE TABLE unrelated_writer_probe(value INTEGER)")
            with pytest.raises(JournalBusyError):
                run_write(
                    fx,
                    operation_id=other.operation.operation_id,
                    new_content=real_markdown("other"),
                    apply_projection=None,
                    reset_cards=None,
                )
            with pytest.raises(JournalBusyError):
                run_write(fx, apply_projection=None, reset_cards=None)
        finally:
            release.set()
        assert pending.result(timeout=5).state == "COMMITTED"
    fx.assert_effects(committed=True)
    with pytest.raises(JournalConflictError):
        run_write(
            fx,
            operation_id=other.operation.operation_id,
            new_content=real_markdown("other"),
            apply_projection=None,
            reset_cards=None,
        )


@pytest.mark.parametrize("failure", ["prepared", "canonical", "receipt"])
def test_real_sqlite_failure_never_acknowledges_partial_effects(
    real_fixture: RealFixture,
    failure: str,
) -> None:
    fx = real_fixture
    target = {
        "prepared": "source_write_journal",
        "canonical": "word_forms",
        "receipt": "operations",
    }[failure]
    action = {"prepared": "INSERT", "canonical": "UPDATE", "receipt": "UPDATE OF status"}[failure]
    condition = "WHEN NEW.status='SUCCEEDED'" if failure == "receipt" else ""
    with fx.database.engine.begin() as conn:
        conn.exec_driver_sql(
            f"CREATE TRIGGER disk_full BEFORE {action} ON {target} {condition} "
            "BEGIN SELECT RAISE(ABORT,'database full'); END"
        )
    with pytest.raises(IntegrityError, match="database full"):
        run_write(fx, apply_projection=None, reset_cards=None)
    fx.assert_effects(committed=False)
    assert (fx.root / fx.source.relative_path).read_text() == (
        fx.old if failure == "prepared" else fx.new
    )
    with fx.database.engine.begin() as conn:
        conn.exec_driver_sql("DROP TRIGGER disk_full")
    recovered = fx.restart().reconcile(operation_ledger=fx.ledger)
    assert (recovered[0].state if recovered else None) == (
        "COMMITTED" if failure != "prepared" else None
    )
    fx.assert_effects(committed=failure != "prepared")


@pytest.mark.parametrize("primitive", ["mkstemp", "fsync", "replace"])
def test_real_disk_failure_preserves_old_state(real_fixture: RealFixture, primitive: str) -> None:
    fx = real_fixture
    module = "tempfile" if primitive == "mkstemp" else "os"
    with (
        patch(
            f"backend.app.adapters.source_files.{module}.{primitive}",
            side_effect=OSError(28, "synthetic disk full"),
        ),
        pytest.raises(SourceFileError),
    ):
        run_write(fx, apply_projection=None, reset_cards=None)
    journal = fx.coordinator.get(fx.operation_id)
    assert journal is not None and journal.state == "ABORTED"
    assert (fx.root / fx.source.relative_path).read_text() == fx.old
    assert not list(fx.root.glob(".*.tmp"))
    fx.restart().reconcile(operation_ledger=fx.ledger)
    fx.assert_effects(committed=False)


@pytest.mark.parametrize("change", ["missing", "canonical", "search_revision", "search_version"])
def test_restart_refuses_missing_or_stale_evidence_without_history_loss(
    real_fixture: RealFixture,
    change: str,
) -> None:
    fx = real_fixture

    def crash(point: str) -> None:
        if point == "AFTER_ATOMIC_REPLACE":
            raise InjectedCrash(point)

    with pytest.raises(InjectedCrash):
        run_write(fx, apply_projection=None, reset_cards=None, fault=crash)
    if change == "missing":
        (fx.root / fx.source.relative_path).unlink()
    elif change == "canonical":
        with fx.database.engine.begin() as conn:
            conn.exec_driver_sql(
                "UPDATE word_forms SET revision=revision+1 WHERE id=?", (fx.form.id,)
            )
    elif change == "search_revision":
        with fx.database.engine.begin() as conn:
            conn.exec_driver_sql("UPDATE search_projection_sources SET revision=9")
    else:
        fx.index.set_version("incompatible")
    recovery = fx.restart()
    assert recovery.reconcile(operation_ledger=fx.ledger)[0].state == "DEGRADED"
    with fx.database.engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT * FROM review_events").all() == fx.history
        assert conn.exec_driver_sql("SELECT * FROM review_cards").all() == fx.old_card
        assert conn.exec_driver_sql("SELECT revision,content_hash FROM source_files").one() == (
            1,
            fx.old_hash,
        )
    if change == "missing":
        assert not (fx.root / fx.source.relative_path).exists()
    else:
        assert (fx.root / fx.source.relative_path).read_text() == fx.new
    operation = fx.ledger.get(fx.operation_id)
    assert operation is not None and operation.status == "UNKNOWN"


def test_reset_does_not_touch_an_unrelated_card(real_fixture: RealFixture) -> None:
    fx = real_fixture
    family = fx.repo.get_or_create_family("unrelated")
    form = fx.repo.save_canonical_word_form(
        lemma="unrelated",
        part_of_speech="ADJECTIVE",
        family_id=family.id,
        meanings_vi=[MeaningVi("khác")],
    )
    with (
        fx.database.engine.connect().execution_options(sqlite_begin_immediate=True) as conn,
        conn.begin(),
    ):
        ensure_card(conn, card_id="unrelated-card", word_form_id=form.id)
        conn.exec_driver_sql(
            "UPDATE review_cards SET queue_revision=7 WHERE card_id='unrelated-card'"
        )
    run_write(fx, apply_projection=None, reset_cards=None)
    with fx.database.engine.connect() as conn:
        assert conn.exec_driver_sql(
            "SELECT box,queue_revision FROM review_cards WHERE card_id='unrelated-card'"
        ).one() == (0, 7)
        assert conn.exec_driver_sql("SELECT * FROM review_events").all() == fx.history


def test_unknown_without_journal_never_stages_source(real_fixture: RealFixture) -> None:
    from backend.app.application.source_write import UnknownOperationError

    fx = real_fixture
    fx.ledger.recover_pending()
    with (
        patch.object(fx.adapter, "prepare_staged_write", side_effect=AssertionError("no replay")),
        pytest.raises(UnknownOperationError),
    ):
        run_write(fx, apply_projection=None, reset_cards=None)
    fx.assert_effects(committed=False)


def test_temp_write_disk_full_preserves_original_and_cleans_residue(
    real_fixture: RealFixture,
) -> None:
    import os
    from contextlib import contextmanager
    from unittest.mock import Mock

    fx = real_fixture
    fdopen = os.fdopen

    @contextmanager
    def disk_full(descriptor: int, mode: str) -> Iterator[Any]:
        with fdopen(descriptor, mode) as stream:
            proxy = Mock(wraps=stream)
            proxy.write.side_effect = OSError(28, "synthetic disk full")
            yield proxy

    with (
        patch("backend.app.adapters.source_files.os.fdopen", side_effect=disk_full),
        pytest.raises(SourceFileError),
    ):
        run_write(fx, apply_projection=None, reset_cards=None)
    assert (fx.root / fx.source.relative_path).read_text() == fx.old
    assert not list(fx.root.glob(".*.tmp"))
    journal = fx.coordinator.get(fx.operation_id)
    assert journal is not None and journal.state == "ABORTED"
    fx.assert_effects(committed=False)


@pytest.mark.parametrize("change", ["example", "link"])
def test_reset_policy_distinguishes_examples_from_links(
    real_fixture: RealFixture, change: str
) -> None:
    fx = real_fixture
    fx.new = real_markdown("cũ")
    fx.new = (
        fx.new.replace("Example.", "New example.")
        if change == "example"
        else fx.new.replace("https://cambridge.org/robust", "https://cambridge.org/new-robust")
    )
    fx.new_hash = digest(fx.new)
    run_write(fx, apply_projection=None, reset_cards=None)
    fx.restart().reconcile(operation_ledger=fx.ledger)
    with fx.database.engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT box,queue_revision FROM review_cards").one() == (
            (0, 2) if change == "example" else (1, 1)
        )
        assert conn.exec_driver_sql("SELECT * FROM review_events").all() == fx.history


def test_new_canonical_identity_and_removed_link_recover_without_recreating_history(
    real_fixture: RealFixture,
) -> None:
    fx = real_fixture
    fx.new = real_markdown("mới").replace("robust", "novel").replace("Robust", "Novel")
    fx.new_hash = digest(fx.new)

    def crash(point: str) -> None:
        if point == "AFTER_ATOMIC_REPLACE":
            raise InjectedCrash(point)

    with pytest.raises(InjectedCrash):
        run_write(fx, apply_projection=None, reset_cards=None, fault=crash)
    fx.restart().reconcile(operation_ledger=fx.ledger)
    with fx.database.engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT * FROM review_events").all() == fx.history
        assert (
            conn.exec_driver_sql("SELECT * FROM review_cards WHERE card_id='real-card'").all()
            == fx.old_card
        )
        assert conn.exec_driver_sql("SELECT count(*) FROM word_forms").scalar_one() == 2
        assert conn.exec_driver_sql("SELECT count(*) FROM review_cards").scalar_one() == 2
        assert conn.exec_driver_sql("SELECT count(*) FROM word_form_sources").scalar_one() == 1
    linked = fx.repo.get_forms_for_source(fx.source.id)
    assert len(linked) == 1 and linked[0].lemma == "novel"
    assert fx.index.search("moi") and not fx.index.search("cu")
    assert SourceRecovery(fx.coordinator).reconcile() == []


def test_staged_evidence_and_effect_plan_are_immutable(real_fixture: RealFixture) -> None:
    from dataclasses import replace

    fx = real_fixture
    journal = fx.coordinator.prepare(
        operation_id=fx.operation_id,
        source_id=fx.source.id,
        expected_old_hash=fx.old_hash,
        new_content=fx.new,
        intended_projection_revision=2,
    )
    staged = fx.adapter.prepare_staged_write(fx.source.id, fx.new, fx.old_hash)
    # Windows file identifiers can exceed SQLite's signed 64-bit integer range.
    handle = replace(staged.recovery_handle, inode=2**100)
    fx.coordinator._record_stage(journal, handle)
    current = fx.coordinator.get(fx.operation_id)
    assert current is not None and current.temp_inode == 2**100
    with fx.database.engine.begin() as conn:
        for sql in [
            "UPDATE source_write_journal SET effect_plan='{}'",
            "UPDATE source_write_journal SET temp_path=NULL,temp_device=NULL,temp_inode=NULL",
            "INSERT OR REPLACE INTO source_write_journal SELECT * FROM source_write_journal",
            "UPDATE source_write_journal SET state='COMMITTED'",
        ]:
            with pytest.raises(IntegrityError):
                conn.exec_driver_sql(sql)
    staged.cleanup()


def test_unknown_reconciliation_receipt_mismatch_or_partial_callback_rolls_back(
    real_fixture: RealFixture,
) -> None:
    fx = real_fixture

    def crash(point: str) -> None:
        if point == "AFTER_SOURCE_REPLACED":
            raise InjectedCrash(point)

    with pytest.raises(InjectedCrash):
        run_write(fx, apply_projection=None, reset_cards=None, fault=crash)
    fx.ledger.recover_pending()

    def forbidden(_connection: Connection) -> None:
        raise AssertionError("Mismatched intent cannot apply effects")

    with pytest.raises(OperationConflict):
        fx.ledger.reconcile_source_write(
            fx.operation_id,
            expected_new_hash=fx.new_hash,
            response_status=200,
            result_ref="changed_receipt",
            local_write=forbidden,
        )

    def partial(connection: Connection) -> None:
        connection.exec_driver_sql(
            "UPDATE source_files SET content_hash=?,revision=2 WHERE id=?",
            (fx.new_hash, fx.source.id),
        )

    with pytest.raises(OperationConflict):
        fx.ledger.reconcile_source_write(
            fx.operation_id,
            expected_new_hash=fx.new_hash,
            response_status=200,
            result_ref="save_journal_1",
            local_write=partial,
        )
    fx.assert_effects(committed=False)
    fx.restart().reconcile(operation_ledger=fx.ledger)
    fx.assert_effects(committed=True)


def test_cleanup_failure_degrades_without_deleting_any_source_or_history(
    real_fixture: RealFixture,
) -> None:
    fx = real_fixture

    def crash(point: str) -> None:
        if point == "AFTER_TEMP_FSYNC":
            raise InjectedCrash(point)

    with pytest.raises(InjectedCrash):
        run_write(fx, apply_projection=None, reset_cards=None, fault=crash)
    journal = fx.coordinator.get(fx.operation_id)
    assert journal is not None and journal.temp_path is not None
    temp = fx.root / journal.temp_path
    temp.write_bytes(b"external staged replacement")
    recovery = fx.restart()
    assert recovery.reconcile(operation_ledger=fx.ledger)[0].state == "DEGRADED"
    assert temp.read_bytes() == b"external staged replacement"
    assert (fx.root / fx.source.relative_path).read_text() == fx.old
    fx.assert_effects(committed=False)

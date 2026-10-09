"""Production HTTP/service save regressions with real temporary storage and journal.

Executable verification is deferred by the owner. Only validated synthetic previews
are seeded; filesystem publication, projection, review and ledger are real.
"""

from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import pytest
from backend.app.adapters.source_files import SourceFileError
from backend.app.application.operations import OperationLedger
from backend.app.application.save_word_family import SaveWordFamilyService
from backend.app.application.source_recovery import SourceRecovery
from backend.app.application.source_write import InjectedCrash
from backend.app.enrichment.lookup import parse_provider_response
from backend.app.main import create_app
from backend.app.markdown_sync.parser import parse_markdown
from backend.app.platform.config import AppSettings
from backend.app.review.models import get_card, record_review
from backend.app.vocabulary.repository import VocabularyRepository
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Connection
from sqlalchemy.exc import SQLAlchemyError

BASE = "http://127.0.0.1:8000"
ORIGIN = {"Origin": BASE}
DAY = "2026-09-29"


def provider_forms() -> list[dict[str, Any]]:
    return [{
        "lemma": lemma, "partOfSpeech": pos,
        "meaningsEn": [
            {"text": text, "language": "en"} for text in ["first meaning", "second meaning"]
        ],
        "meaningsVi": [{"text": text, "language": "vi"} for text in ["nghĩa một", "nghĩa hai"]],
        "examples": [
            {"english": "One 🧪 example.", "vietnamese": "Ví dụ một."},
            {"english": "Second example.", "vietnamese": "Ví dụ hai."},
        ], "ipaUs": None, "cambridgeUrl": None,
    } for lemma, pos in [("anchor", "NOUN"), ("anchor", "VERB"), ("anchored", "ADJECTIVE")]]


class Harness:
    def __init__(self, app: FastAPI, client: TestClient, root: Path) -> None:
        self.app, self.client, self.root = app, client, root
        self.service: SaveWordFamilyService = app.state.save_word_family_service
        self.ledger: OperationLedger = app.state.operation_ledger
        self.repository = VocabularyRepository(self.ledger.engine)
        cookie = client.cookies.get("launch_session")
        assert cookie is not None
        self.owner = hashlib.sha256(f"owner:{cookie}".encode()).hexdigest()

    def preview(
        self, name: str = "base", forms: list[dict[str, Any]] | None = None,
        owner: str | None = None, expires_at: float | None = None,
        term: str = "anchor",
    ) -> str:
        lookup_id = f"lookup_{name}"
        drafts = parse_provider_response({
            "forms": forms if forms is not None else provider_forms(),
        })
        claim = self.ledger.claim(
            kind="LOOKUP", key=f"preview-{name}", method="POST", path="/api/v1/lookups",
            body={"term": term}, preconditions={},
        )

        def store(connection: Connection) -> None:
            self.repository.create_preview(
                lookup_id=lookup_id, owner_session_id=owner or self.owner, term=term,
                forms=drafts, operation_id=claim.operation.operation_id,
                expires_at=expires_at, external_connection=connection,
            )

        self.ledger.complete(claim.operation.operation_id, response_status=200,
                             result_ref=lookup_id, local_write=store)
        return lookup_id

    def post(
        self, lookup: str, key: str = "save", day: str = DAY,
        source: dict[str, Any] | None = None,
    ) -> Any:
        body: dict[str, Any] = {"lookupId": lookup, "noteDate": day}
        headers = {**ORIGIN, "Idempotency-Key": key}
        if source is None:
            headers["If-None-Match"] = "*"
        else:
            body.update(sourceId=source["sourceId"], sourceRevision=source["sourceRevision"])
            headers["If-Match"] = source["sourceEtag"]
        return self.client.post("/api/v1/word-forms", json=body, headers=headers)

    def count(self, table: str) -> int:
        assert table in {"source_files", "word_forms", "review_cards", "review_events",
                         "word_form_sources", "source_write_journal", "operation_keys"}
        with self.ledger.engine.connect() as connection:
            return int(connection.exec_driver_sql(f"SELECT count(*) FROM {table}").scalar_one())

    def review(self, card_id: str) -> None:
        claim = self.ledger.claim(kind="REVIEW", key="review", method="POST", path="/review",
                                  body={"cardId": card_id}, preconditions={})

        def apply(connection: Connection) -> None:
            record_review(
                connection, card_id=card_id, event_id="review_synthetic",
                operation_id=claim.operation.operation_id, source="FLASHCARD", rating="GOOD",
                reviewed_at=datetime(2026, 9, 29, 10, 20, 30, tzinfo=UTC),
            )

        self.ledger.complete(claim.operation.operation_id, response_status=200,
                             result_ref="review_synthetic", local_write=apply)

    def card(self, card_id: str) -> Any:
        with self.ledger.engine.connect() as connection:
            return get_card(connection, card_id)

    def history(self) -> list[Any]:
        with self.ledger.engine.connect() as connection:
            return list(connection.exec_driver_sql("SELECT * FROM review_events ORDER BY id"))


@pytest.fixture
def harness(tmp_path: Path) -> Iterator[Harness]:
    root = tmp_path / "notes"
    root.mkdir()
    app = create_app(AppSettings(storage_path=tmp_path / "save.db"), markdown_root=root)
    with TestClient(app, base_url=BASE) as client:
        assert app.state.ready
        # Deterministic tests drive the actual sync boundary explicitly.
        app.state.watcher.stop()
        token = app.state.sessions.issue_bootstrap_token()
        response = client.post("/bootstrap/exchange", json={"token": token}, headers=ORIGIN)
        assert response.status_code == 204
        yield Harness(app, client, root)


def test_preview_alone_persists_no_source_forms_or_cards(harness: Harness) -> None:
    harness.preview()
    assert harness.count("source_files") == 0
    assert harness.count("word_forms") == 0
    assert harness.count("review_cards") == 0
    assert list(harness.root.iterdir()) == []


def test_clean_install_three_forms_full_content_and_consistent_receipt(harness: Harness) -> None:
    response = harness.post(harness.preview())
    assert response.status_code == 201
    result = response.json()
    assert result["sourceRevision"] == 1 and response.headers["etag"] == result["sourceEtag"]
    assert result["markdownSync"] == "COMPLETED"
    assert len(result["savedForms"]) == len(result["createdCardIds"]) == 3
    assert harness.count("word_forms") == harness.count("review_cards") == 3
    content = (harness.root / "29-09-2026.md").read_text(encoding="utf-8")
    parsed = parse_markdown(content, filename="29-09-2026.md")
    assert parsed.is_valid and parsed.document is not None
    assert [f.part_of_speech for f in parsed.document.semantic_forms] == [
        "NOUN", "VERB", "ADJECTIVE",
    ]
    for form in result["canonicalForms"]:
        assert [m["text"] for m in form["meaningsEn"]] == ["first meaning", "second meaning"]
        assert [m["text"] for m in form["meaningsVi"]] == ["nghĩa một", "nghĩa hai"]
        assert len(form["examples"]) == 2
        assert form["examples"][0]["vietnamese"] == "Ví dụ một."
        assert form["meaningsEn"][0]["verificationStatus"] == "UNVERIFIED"
        assert form["verificationSummary"] == "MISSING"
        canonical = harness.repository.get_word_form(form["id"])
        assert canonical is not None and len(canonical.examples) == 2
        assert [ref.source_id for ref in canonical.source_refs] == [result["sourceId"]]
    journal = harness.service.coordinator.get(result["operationId"])
    assert journal is not None and journal.state == "COMMITTED"
    assert journal.effect_plan["receipt"] == result


def test_existing_date_and_cross_date_reuse_progress_and_history(harness: Harness) -> None:
    lookup = harness.preview()
    first = harness.post(lookup).json()
    card_id = first["createdCardIds"][0]
    harness.review(card_id)
    before = harness.card(card_id)
    history = harness.history()
    repeated = harness.post(lookup, key="same-date", source=first)
    assert repeated.status_code == 201
    assert repeated.json()["sourceRevision"] == 2
    assert repeated.json()["createdCardIds"] == []
    other = harness.post(lookup, key="other-date", day="2026-09-30")
    assert other.status_code == 201 and other.json()["sourceRevision"] == 1
    assert set(other.json()["reusedCardIds"]) == set(first["createdCardIds"])
    assert harness.card(card_id) == before
    assert harness.history() == history
    assert harness.count("review_events") == 1
    assert harness.count("word_forms") == harness.count("review_cards") == 3
    assert harness.count("word_form_sources") == 6


@pytest.mark.parametrize("field", ["meaningsEn", "meaningsVi", "examples"])
def test_learning_change_resets_once_and_keeps_history(harness: Harness, field: str) -> None:
    first = harness.post(harness.preview()).json()
    card_id = first["createdCardIds"][0]
    harness.review(card_id)
    history = harness.history()
    forms = provider_forms()
    forms[0][field][0]["english" if field == "examples" else "text"] = "Changed learning content."
    changed_lookup = harness.preview("changed", forms)
    changed = harness.post(changed_lookup, key="changed", source=first)
    assert changed.status_code == 201
    reset = harness.card(card_id)
    assert reset.box == 0 and reset.due_at is None
    assert harness.count("review_events") == 1
    assert harness.history() == history
    echoed = harness.post(changed_lookup, key="echo", source=changed.json())
    assert echoed.status_code == 201
    assert harness.card(card_id) == reset
    sync = harness.app.state.sync_service.sync(reason="MANUAL")
    assert sync.status == "COMPLETED" and harness.card(card_id) == reset


def test_verification_ipa_and_link_changes_do_not_reset(harness: Harness) -> None:
    first = harness.post(harness.preview()).json()
    card_id = first["createdCardIds"][0]
    harness.review(card_id)
    before = harness.card(card_id)
    forms = provider_forms()
    forms[0]["ipaUs"] = "/synthetic/"
    forms[0]["cambridgeUrl"] = "https://dictionary.cambridge.org/dictionary/english/anchor"
    lookup = harness.preview("metadata", forms)
    response = harness.post(lookup, key="metadata", source=first)
    assert response.status_code == 201
    assert harness.card(card_id) == before
    assert harness.count("review_events") == 1


def test_stale_revision_etag_and_unobserved_external_hash_rejected(harness: Harness) -> None:
    lookup = harness.preview()
    first = harness.post(lookup).json()
    second = harness.post(lookup, key="advance", source=first).json()
    stale = harness.post(lookup, key="stale", source=first)
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "REVISION_CONFLICT"
    wrong_etag = {**second, "sourceEtag": '"different"'}
    assert harness.post(lookup, key="etag", source=wrong_etag).status_code == 409
    path = harness.root / "29-09-2026.md"
    external = path.read_text(encoding="utf-8") + "\nExternal context.\n"
    path.write_text(external, encoding="utf-8")
    assert harness.post(lookup, key="hash", source=second).status_code == 409
    assert path.read_text(encoding="utf-8") == external


@pytest.mark.parametrize("status", ["INVALID", "MISSING"])
def test_invalid_or_missing_source_never_authorizes_content(
    harness: Harness, status: Literal["INVALID", "MISSING"],
) -> None:
    lookup = harness.preview()
    first = harness.post(lookup).json()
    harness.repository.update_source_status(first["sourceId"], status=status)
    content = (harness.root / "29-09-2026.md").read_bytes()
    response = harness.post(lookup, key="invalid", source=first)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SOURCE_NOT_WRITABLE"
    assert (harness.root / "29-09-2026.md").read_bytes() == content


def test_foreign_preview_source_date_and_unknown_source_rejected(harness: Harness) -> None:
    foreign = harness.preview("foreign", owner="another-session-fingerprint")
    assert harness.post(foreign).status_code == 403
    assert harness.count("source_files") == harness.count("source_write_journal") == 0
    lookup = harness.preview()
    first = harness.post(lookup).json()
    response = harness.post(lookup, key="wrong-day", day="2026-09-30", source=first)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "CROSS_RESOURCE_MISMATCH"
    missing = {**first, "sourceId": "src_absent"}
    response = harness.post(lookup, key="missing", source=missing)
    assert response.status_code == 404 and response.json()["error"]["code"] == "SOURCE_MISSING"


def test_deleted_source_is_rejected_without_replacement(harness: Harness) -> None:
    lookup = harness.preview()
    first = harness.post(lookup).json()
    (harness.root / "29-09-2026.md").unlink()
    response = harness.post(lookup, key="deleted", source=first)
    assert response.status_code == 409
    assert not (harness.root / "29-09-2026.md").exists()


def test_same_key_replays_original_receipt_after_source_advance(harness: Harness) -> None:
    lookup = harness.preview()
    first = harness.post(lookup)
    original = first.json()
    harness.review(original["createdCardIds"][0])
    assert harness.post(lookup, key="advance", source=original).status_code == 201
    replay = harness.post(lookup)
    assert replay.status_code == 201 and replay.json() == original
    assert harness.count("source_files") == 1
    assert harness.count("source_write_journal") == 2
    changed = harness.post(lookup, day="2026-09-30")
    assert changed.status_code == 422
    assert changed.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"


def test_concurrent_duplicate_has_one_real_publication(harness: Harness) -> None:
    lookup = harness.preview()
    entered, release = threading.Event(), threading.Event()

    def fault(point: str) -> None:
        if point == "AFTER_PREPARED":
            entered.set()
            assert release.wait(5)

    harness.service.fault = fault
    with ThreadPoolExecutor(max_workers=2) as workers:
        first = workers.submit(harness.post, lookup)
        assert entered.wait(5)
        duplicate = workers.submit(harness.post, lookup)
        try:
            response = duplicate.result(timeout=5)
            assert response.status_code == 409
            assert response.json()["error"]["code"] == "IDEMPOTENCY_IN_FLIGHT"
        finally:
            release.set()
        completed = first.result(timeout=5)
    assert completed.status_code == 201
    harness.service.fault = None
    assert harness.post(lookup).json() == completed.json()
    assert harness.count("source_files") == harness.count("source_write_journal") == 1
    assert harness.count("review_cards") == 3


@pytest.mark.parametrize("point", ["AFTER_PREPARED", "AFTER_TEMP_FSYNC", "AFTER_ATOMIC_REPLACE",
                                  "AFTER_SOURCE_REPLACED", "BEFORE_PROJECTION", "AFTER_CARD_RESET",
                                  "AFTER_RECEIPT"])
def test_crash_recovery_and_lost_response_reconcile_journal(harness: Harness, point: str) -> None:
    lookup = harness.preview()

    def crash(at: str) -> None:
        if at == point:
            raise InjectedCrash(at)

    harness.service.fault = crash
    with pytest.raises(InjectedCrash):
        harness.post(lookup)
    harness.service.fault = None
    harness.ledger.recover_pending()
    SourceRecovery(harness.service.coordinator).reconcile(operation_ledger=harness.ledger)
    replay = harness.post(lookup)
    if point in {"AFTER_PREPARED", "AFTER_TEMP_FSYNC"}:
        assert replay.status_code == 409
        assert harness.count("review_cards") == 0
        assert not (harness.root / "29-09-2026.md").exists()
    else:
        assert replay.status_code == 201
        assert harness.count("review_cards") == 3
        assert harness.count("source_write_journal") == 1
        journal = harness.service.coordinator.get(replay.json()["operationId"])
        assert journal is not None and journal.state == "COMMITTED"
    recovered = SourceRecovery(harness.service.coordinator).reconcile(
        operation_ledger=harness.ledger,
    )
    assert recovered == []


def test_filesystem_failure_keeps_no_false_success(
    harness: Harness, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def denied(*_args: Any, **_kwargs: Any) -> Any:
        raise SourceFileError("ACCESS_DENIED", "synthetic denial")

    monkeypatch.setattr(harness.service.coordinator.adapter, "prepare_staged_create", denied)
    response = harness.post(harness.preview())
    assert response.status_code == 409
    assert harness.count("review_cards") == 0
    assert list(harness.root.glob("*.md")) == []
    with harness.ledger.engine.connect() as connection:
        state = connection.exec_driver_sql("SELECT state FROM source_write_journal").scalar_one()
    assert state == "ABORTED"
    replay = harness.post("lookup_base")
    assert replay.status_code == response.status_code
    assert replay.json()["error"]["code"] == response.json()["error"]["code"]


def test_destination_race_preserves_competing_bytes(harness: Harness) -> None:
    def race(point: str) -> None:
        if point == "AFTER_TEMP_FSYNC":
            (harness.root / "29-09-2026.md").write_text("Competing bytes.", encoding="utf-8")

    harness.service.fault = race
    response = harness.post(harness.preview())
    assert response.status_code == 409 and response.json()["error"]["code"] == "REVISION_CONFLICT"
    assert (harness.root / "29-09-2026.md").read_text(encoding="utf-8") == "Competing bytes."
    assert harness.count("word_forms") == harness.count("review_cards") == 0


def test_save_never_dispatches_ai_or_requires_consent(
    harness: Harness, monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("Save dispatched inference")

    monkeypatch.setattr(harness.app.state.lookup_service.admission, "dispatch", forbidden)
    assert harness.post(harness.preview()).status_code == 201


def test_invalid_expired_and_incomplete_preview_rejected(harness: Harness) -> None:
    expired = harness.preview("expired", expires_at=0)
    assert harness.post(expired).status_code == 422
    lookup = harness.preview()
    with harness.ledger.engine.begin() as connection:
        row = connection.exec_driver_sql(
            "SELECT forms_payload FROM lookup_previews WHERE lookup_id=?", (lookup,),
        ).scalar_one()
        forms = json.loads(row)
        forms[0]["meaningsEn"] = []
        connection.exec_driver_sql("UPDATE lookup_previews SET forms_payload=? WHERE lookup_id=?",
                                   (json.dumps(forms), lookup))
    assert harness.post(lookup, key="incomplete").status_code == 422
    assert harness.count("source_files") == 0


@pytest.mark.parametrize("extra,headers", [
    ({"path": "../../outside.md"}, {"If-None-Match": "*"}),
    ({"sourceId": "src_partial"}, {"If-Match": '"etag"'}),
    ({}, {}),
    ({}, {"If-Match": '"etag"', "If-None-Match": "*"}),
    ({"sourceId": None, "sourceRevision": None}, {"If-None-Match": "*"}),
])
def test_invalid_destinations_and_preconditions_fail_before_source_effects(
    harness: Harness, extra: dict[str, Any], headers: dict[str, str],
) -> None:
    lookup = harness.preview()
    response = harness.client.post("/api/v1/word-forms", json={
        "lookupId": lookup, "noteDate": DAY, **extra,
    }, headers={**ORIGIN, "Idempotency-Key": "invalid-input", **headers})
    assert response.status_code == 422
    assert harness.count("source_files") == harness.count("source_write_journal") == 0


def test_reopen_keeps_content_cards_and_journal_receipt(harness: Harness, tmp_path: Path) -> None:
    first = harness.post(harness.preview()).json()
    app = create_app(AppSettings(storage_path=tmp_path / "save.db"), markdown_root=harness.root)
    with TestClient(app, base_url=BASE) as client:
        assert app.state.ready
        app.state.watcher.stop()
        repository = VocabularyRepository(app.state.database.engine)
        forms = repository.get_forms_for_source(first["sourceId"])
        assert len(forms) == 3 and all(len(f.meanings_en) == len(f.examples) == 2 for f in forms)
        coordinator = app.state.save_word_family_service.coordinator
        journal = coordinator.get(first["operationId"])
        assert journal is not None and journal.effect_plan["receipt"] == first
        with app.state.database.engine.connect() as connection:
            assert connection.exec_driver_sql("SELECT count(*) FROM review_cards").scalar_one() == 3


def test_duplicate_date_metadata_fails_closed(harness: Harness) -> None:
    lookup = harness.preview()
    first = harness.post(lookup).json()
    harness.repository.save_source_file(
        source_id="src_duplicate", relative_path="nested/29-09-2026.md",
        note_date=DAY, status="MISSING",
    )
    response = harness.post(lookup, key="ambiguous", source=first)
    assert response.status_code == 409 and response.json()["error"]["code"] == "SOURCE_NOT_WRITABLE"
    assert harness.count("review_cards") == 3


@pytest.mark.parametrize("separator", ["\u0085", "\u2028", "\u2029"])
def test_unicode_lookup_content_cannot_become_markdown_syntax(
    harness: Harness, separator: str,
) -> None:
    forms = provider_forms()
    learning = f"first{separator}## injected heading"
    forms[0]["meaningsEn"][0]["text"] = learning
    response = harness.post(harness.preview(forms=forms))
    assert response.status_code == 201
    assert response.json()["canonicalForms"][0]["meaningsEn"][0]["text"] == learning
    parsed = parse_markdown((harness.root / "29-09-2026.md").read_text(encoding="utf-8"),
                            filename="29-09-2026.md")
    assert parsed.is_valid and parsed.document is not None
    assert parsed.document.semantic_forms[0].meanings_en[0] == learning


def test_duplicate_date_appearing_after_prepare_prevents_publication(harness: Harness) -> None:
    lookup = harness.preview()
    first = harness.post(lookup).json()
    original = (harness.root / "29-09-2026.md").read_bytes()

    def race(point: str) -> None:
        if point == "AFTER_TEMP_FSYNC":
            harness.repository.save_source_file(
                source_id="src_race_date", relative_path="nested/29-09-2026.md",
                note_date=DAY, status="MISSING",
            )

    harness.service.fault = race
    response = harness.post(lookup, key="date-race", source=first)
    assert response.status_code == 409 and response.json()["error"]["code"] == "SOURCE_NOT_WRITABLE"
    assert (harness.root / "29-09-2026.md").read_bytes() == original
    assert harness.count("review_cards") == 3


@pytest.mark.parametrize("phase", ["prepare", "receipt"])
def test_storage_failure_cannot_acknowledge_success_and_is_recoverable(
    harness: Harness, monkeypatch: pytest.MonkeyPatch, phase: str,
) -> None:
    lookup = harness.preview()

    def fail(*_args: Any, **_kwargs: Any) -> Any:
        raise SQLAlchemyError("sensitive synthetic storage failure")

    with monkeypatch.context() as fault:
        if phase == "prepare":
            fault.setattr(harness.service.coordinator, "prepare", fail)
        else:
            fault.setattr(harness.ledger, "complete", fail)
        response = harness.post(lookup)
    assert response.status_code == 503 and response.json()["error"]["code"] == "STORAGE_BUSY"
    assert "sensitive" not in response.text and str(harness.root) not in response.text
    assert harness.count("review_cards") == 0
    SourceRecovery(harness.service.coordinator).reconcile(operation_ledger=harness.ledger)
    if phase == "receipt":
        assert harness.post(lookup).status_code == 201
        assert harness.count("review_cards") == 3
    else:
        assert harness.post(lookup).status_code == 503
        assert list(harness.root.iterdir()) == []


def test_interrupted_content_edit_recovers_one_reset(harness: Harness) -> None:
    first = harness.post(harness.preview()).json()
    card_id = first["createdCardIds"][0]
    harness.review(card_id)
    before = harness.card(card_id)
    forms = provider_forms()
    forms[0]["examples"][0]["english"] = "Edited before interrupted receipt."
    lookup = harness.preview("edit-crash", forms)

    def crash(point: str) -> None:
        if point == "AFTER_CARD_RESET":
            raise InjectedCrash(point)

    harness.service.fault = crash
    with pytest.raises(InjectedCrash):
        harness.post(lookup, key="edit-crash", source=first)
    assert harness.card(card_id) == before
    harness.service.fault = None
    harness.ledger.recover_pending()
    SourceRecovery(harness.service.coordinator).reconcile(operation_ledger=harness.ledger)
    result = harness.post(lookup, key="edit-crash", source=first)
    assert result.status_code == 201
    after = harness.card(card_id)
    assert after.box == 0 and after.due_at is None
    assert after.queue_revision == before.queue_revision + 1
    assert harness.count("review_events") == 1
    assert harness.post(lookup, key="edit-crash", source=first).json() == result.json()
    assert harness.card(card_id) == after


def test_save_route_uses_real_session_and_origin_guards(harness: Harness) -> None:
    lookup = harness.preview()
    body = {"lookupId": lookup, "noteDate": DAY}
    headers = {"Idempotency-Key": "unauthorized", "If-None-Match": "*"}
    origin = harness.client.post("/api/v1/word-forms", json=body,
                                 headers={**headers, "Origin": "http://evil.invalid"})
    assert origin.status_code == 403
    harness.client.cookies.clear()
    missing = harness.client.post("/api/v1/word-forms", json=body, headers={**headers, **ORIGIN})
    assert missing.status_code == 401
    assert harness.count("source_files") == harness.count("source_write_journal") == 0


def test_save_into_imported_legacy_source_preserves_unrelated_families(harness: Harness) -> None:
    original = Path("backend/tests/fixtures/legacy.md").read_bytes()
    (harness.root / "29-09-2026.md").write_bytes(original)
    synced = harness.app.state.sync_service.sync(reason="MANUAL")
    assert synced.status == "COMPLETED"
    with harness.ledger.engine.connect() as connection:
        source_id = connection.exec_driver_sql("SELECT id FROM source_files").scalar_one()
    source = harness.repository.get_source_file(source_id)
    assert source is not None and source.status == "VALID"
    forms_before = harness.repository.get_forms_for_source(source_id)
    unrelated = next(form for form in forms_before if form.lemma == "robust")
    with harness.ledger.engine.connect() as connection:
        card_id = connection.exec_driver_sql(
            "SELECT card_id FROM review_cards WHERE word_form_id=?", (unrelated.id,),
        ).scalar_one()
    harness.review(card_id)
    history, progress = harness.history(), harness.card(card_id)
    response = harness.post(harness.preview(), source={
        "sourceId": source.id, "sourceRevision": source.revision, "sourceEtag": source.etag,
    })
    assert response.status_code == 201
    assert harness.card(card_id) == progress and harness.history() == history
    after = harness.repository.get_forms_for_source(source_id)
    assert {f.id for f in after} == {f.id for f in forms_before}
    assert harness.repository.get_word_form(unrelated.id) == unrelated
    content = (harness.root / "29-09-2026.md").read_text(encoding="utf-8")
    before_doc = parse_markdown(original.decode(), filename="29-09-2026.md").document
    assert before_doc is not None
    for entry in before_doc.entries:
        if entry.normalized_lemma != "anchor":
            assert entry.raw_text in content


def test_verification_only_changes_keep_schedule_and_history(harness: Harness) -> None:
    first = harness.post(harness.preview()).json()
    card_id = first["createdCardIds"][0]
    harness.review(card_id)
    progress, history = harness.card(card_id), harness.history()
    lookup = harness.preview("verified")
    with harness.ledger.engine.begin() as connection:
        payload = json.loads(connection.exec_driver_sql(
            "SELECT forms_payload FROM lookup_previews WHERE lookup_id=?", (lookup,),
        ).scalar_one())
        for field in ["meaningsEn", "meaningsVi", "examples"]:
            for item in payload[0][field]:
                item["verificationStatus"] = "VERIFIED"
        connection.exec_driver_sql(
            "UPDATE lookup_previews SET forms_payload=? WHERE lookup_id=?",
            (json.dumps(payload), lookup),
        )
    response = harness.post(lookup, key="verification", source=first)
    assert response.status_code == 201
    assert response.json()["canonicalForms"][0]["meaningsEn"][0]["verificationStatus"] == "VERIFIED"
    assert harness.card(card_id) == progress and harness.history() == history
    assert harness.post(lookup, key="verified-echo", source=response.json()).status_code == 201
    assert harness.card(card_id) == progress


def test_source_invalidation_after_publication_never_commits_receipt(harness: Harness) -> None:
    lookup = harness.preview()
    first = harness.post(lookup).json()
    card_id = first["createdCardIds"][0]
    harness.review(card_id)
    progress, history = harness.card(card_id), harness.history()

    def invalidate(point: str) -> None:
        if point == "AFTER_ATOMIC_REPLACE":
            harness.repository.update_source_status(first["sourceId"], status="INVALID")

    harness.service.fault = invalidate
    response = harness.post(lookup, key="invalidate", source=first)
    assert response.status_code == 503
    operation_id = response.json()["error"]["details"]["operationId"]
    journal = harness.service.coordinator.get(operation_id)
    operation = harness.ledger.get(operation_id)
    assert journal is not None and journal.state == "DEGRADED"
    assert operation is not None and operation.status == "UNKNOWN"
    assert harness.card(card_id) == progress and harness.history() == history
    harness.service.fault = None
    replay = harness.post(lookup, key="invalidate", source=first)
    assert replay.status_code == 409 and replay.json()["error"]["code"] == "IDEMPOTENCY_IN_FLIGHT"


@pytest.mark.parametrize("destination", ["existing", "new-date"])
def test_content_change_with_other_date_links_stays_active_after_sync(
    harness: Harness, destination: str, tmp_path: Path,
) -> None:
    lookup = harness.preview()
    first = harness.post(lookup).json()
    linked = harness.post(lookup, key="linked", day="2026-09-30")
    assert linked.status_code == 201
    card_id = first["createdCardIds"][0]
    harness.review(card_id)
    progress, history = harness.card(card_id), harness.history()
    forms = provider_forms()
    forms[0]["meaningsEn"][0]["text"] = "Explicitly changed content on another save."
    changed = harness.preview("cross-date-edit", forms)
    response = harness.post(
        changed, key="cross-date-edit", day=DAY if destination == "existing" else "2026-10-01",
        source=first if destination == "existing" else None,
    )
    assert response.status_code == 201
    after = harness.card(card_id)
    assert after.box == 0 and after.due_at is None
    assert after.queue_revision == progress.queue_revision + 1
    assert harness.history() == history
    synced = harness.app.state.sync_service.sync(reason="MANUAL")
    assert synced.status == "COMPLETED" and synced.sources_invalid == 0
    assert harness.card(card_id) == after and harness.history() == history
    with harness.ledger.engine.connect() as connection:
        assert set(connection.exec_driver_sql("SELECT status FROM source_files").scalars()) == {
            "VALID",
        }
    canonical = harness.repository.get_word_form(response.json()["canonicalForms"][0]["id"])
    assert canonical is not None
    assert canonical.meanings_en[0].text == "Explicitly changed content on another save."
    expected_dates = {DAY, "2026-09-30"}
    if destination == "new-date":
        expected_dates.add("2026-10-01")
    assert {ref.note_date for ref in canonical.source_refs} == expected_dates
    assert all(ref.status == "VALID" for ref in canonical.source_refs)
    sources = {ref.source_id: harness.repository.get_source_file(ref.source_id)
               for ref in canonical.source_refs}
    for reason in ("WATCHER", "WATCHER", "STARTUP"):
        assert harness.app.state.sync_service.sync(reason=reason).sources_invalid == 0
        assert harness.repository.get_word_form(canonical.id) == canonical
        assert harness.card(card_id) == after and harness.history() == history
        assert {sid: harness.repository.get_source_file(sid) for sid in sources} == sources
    reopened = create_app(AppSettings(storage_path=tmp_path / "save.db"),
                          markdown_root=harness.root)
    with TestClient(reopened, base_url=BASE):
        reopened.state.watcher.stop()
        assert reopened.state.ready
        repo = VocabularyRepository(reopened.state.database.engine)
        assert repo.get_word_form(canonical.id) == canonical
        assert {sid: repo.get_source_file(sid) for sid in sources} == sources
        with reopened.state.database.engine.connect() as connection:
            assert get_card(connection, card_id) == after
            assert list(connection.exec_driver_sql(
                "SELECT * FROM review_events ORDER BY id",
            )) == history


@pytest.mark.parametrize("evidence", ["external-authority", "external-history", "other-source",
                                     "unknown", "pending", "missing-receipt", "wrong-receipt",
                                     "stale-source-revision"])
def test_cross_date_conflict_requires_current_completed_source_evidence(
    harness: Harness, evidence: str,
) -> None:
    lookup = harness.preview()
    first = harness.post(lookup).json()
    second = harness.post(lookup, key="second-date", day="2026-09-30").json()
    harness.review(first["createdCardIds"][0])
    changed_forms = provider_forms()
    changed_forms[0]["meaningsEn"][0]["text"] = "Application learning edit."
    edited = harness.post(harness.preview("edit", changed_forms), key="edit", source=first)
    assert edited.status_code == 201
    receipt = edited.json()
    card = harness.card(first["createdCardIds"][0])
    history = harness.history()
    canonical = harness.repository.get_word_form(first["canonicalForms"][0]["id"])
    if evidence in {"external-authority", "external-history", "other-source"}:
        path = harness.root / ("29-09-2026.md" if evidence == "external-authority"
                               else "30-09-2026.md")
        text = path.read_text(encoding="utf-8")
        if evidence == "other-source":
            # An unregistered conflicting date cannot borrow another source's journal.
            path = harness.root / "01-10-2026.md"
            text = text.replace("30-09-2026", "01-10-2026")
        text = text.replace("Application learning edit." if evidence == "external-authority"
                            else "first meaning", "External conflicting learning edit.")
        path.write_text(text, encoding="utf-8")
        external_bytes = path.read_bytes()
    else:
        # Deliberately damaged operation/source evidence; never alter immutable journal rows.
        with harness.ledger.engine.begin() as connection:
            if evidence in {"unknown", "pending"}:
                connection.exec_driver_sql("UPDATE operations SET status=? WHERE operation_id=?",
                                           (evidence.upper(), receipt["operationId"]))
            elif evidence == "missing-receipt":
                connection.exec_driver_sql(
                    "UPDATE operations SET response_status=NULL,result_ref=NULL WHERE operation_id=?",
                    (receipt["operationId"],),
                )
            elif evidence == "wrong-receipt":
                connection.exec_driver_sql(
                    "UPDATE operations SET result_ref='unrelated' WHERE operation_id=?",
                    (receipt["operationId"],),
                )
            else:
                connection.exec_driver_sql("UPDATE source_files SET revision=revision+1 WHERE id=?",
                                           (receipt["sourceId"],))
    result = harness.app.state.sync_service.sync(reason="WATCHER")
    assert result.status == "COMPLETED" and result.sources_invalid >= 2
    for source_id in (first["sourceId"], second["sourceId"]):
        source = harness.repository.get_source_file(source_id)
        assert source is not None and source.status == "INVALID"
        assert source.error_code == "AMBIGUOUS_CONTENT"
    assert harness.card(first["createdCardIds"][0]) == card
    assert harness.history() == history
    after = harness.repository.get_word_form(first["canonicalForms"][0]["id"])
    assert after is not None and canonical is not None
    assert after.meanings_en == canonical.meanings_en and after.revision == canonical.revision
    if evidence in {"external-authority", "external-history", "other-source"}:
        assert path.read_bytes() == external_bytes
    assert harness.app.state.sync_service.sync(reason="WATCHER").sources_invalid >= 2
    assert harness.card(first["createdCardIds"][0]) == card and harness.history() == history


@pytest.mark.parametrize("interruption", [False, True])
def test_unrelated_save_preserves_historical_date_canonical_projection(
    harness: Harness, interruption: bool,
) -> None:
    lookup = harness.preview()
    first = harness.post(lookup).json()
    second = harness.post(lookup, key="date-two", day="2026-09-30").json()
    card_id = first["createdCardIds"][0]
    harness.review(card_id)
    forms = provider_forms()
    forms[0]["meaningsEn"][0]["text"] = "Updated canonical meaning on date two."
    edit = harness.post(harness.preview("changed", forms), key="changed", day="2026-09-30",
                        source=second)
    assert edit.status_code == 201
    canonical = harness.repository.get_word_form(first["canonicalForms"][0]["id"])
    card, history = harness.card(card_id), harness.history()
    old_bytes = (harness.root / "29-09-2026.md").read_text(encoding="utf-8")
    unrelated = provider_forms()[:1]
    unrelated[0]["lemma"] = "buoy"
    preview = harness.preview("unrelated", unrelated, term="buoy")

    def crash(point: str) -> None:
        if point == "AFTER_SOURCE_REPLACED":
            raise InjectedCrash(point)

    if interruption:
        harness.service.fault = crash
        with pytest.raises(InjectedCrash):
            harness.post(preview, key="unrelated", source=first)
        harness.service.fault = None
        harness.ledger.recover_pending()
        SourceRecovery(harness.service.coordinator).reconcile(operation_ledger=harness.ledger)
    saved = harness.post(preview, key="unrelated", source=first)
    assert saved.status_code == 201
    assert [f["lemma"] for f in saved.json()["canonicalForms"]] == ["buoy"]
    assert harness.repository.get_word_form(first["canonicalForms"][0]["id"]) == canonical
    assert harness.card(card_id) == card and harness.history() == history
    # The unrelated historical family's complete Markdown block remains unchanged.
    new_bytes = (harness.root / "29-09-2026.md").read_text(encoding="utf-8")
    assert new_bytes.startswith(old_bytes)
    for reason in ("WATCHER", "STARTUP", "WATCHER"):
        assert harness.app.state.sync_service.sync(reason=reason).sources_invalid == 0
        assert harness.repository.get_word_form(first["canonicalForms"][0]["id"]) == canonical
        assert harness.card(card_id) == card and harness.history() == history


def test_save_committed_during_scan_defers_stale_cross_date_classification(
    harness: Harness, monkeypatch: pytest.MonkeyPatch,
) -> None:
    lookup = harness.preview()
    first = harness.post(lookup).json()
    second = harness.post(lookup, key="second", day="2026-09-30").json()
    changed = provider_forms()
    changed[0]["meaningsEn"][0]["text"] = "First committed change."
    latest = harness.post(harness.preview("first-change", changed), key="first-change",
                          source=second, day="2026-09-30").json()
    changed[0]["meaningsEn"][0]["text"] = "Concurrent committed change."
    preview = harness.preview("during-scan", changed)
    service = harness.app.state.sync_service
    original = service._committed_date_variants
    committed: list[dict[str, Any]] = []

    def save_during_classification(*args: Any, **kwargs: Any) -> bool:
        if not committed:
            response = harness.post(preview, key="during-scan", day="2026-09-30", source=latest)
            assert response.status_code == 201
            committed.append(response.json())
        return bool(original(*args, **kwargs))

    monkeypatch.setattr(service, "_committed_date_variants", save_during_classification)
    assert service.sync(reason="WATCHER").sources_invalid == 0
    assert committed
    for source_id in (first["sourceId"], latest["sourceId"]):
        source = harness.repository.get_source_file(source_id)
        assert source is not None and source.status == "VALID"
    card = harness.card(first["createdCardIds"][0])
    canonical = harness.repository.get_word_form(first["canonicalForms"][0]["id"])
    assert canonical is not None and canonical.meanings_en[0].text == "Concurrent committed change."
    assert service.sync(reason="WATCHER").sources_invalid == 0
    assert harness.card(first["createdCardIds"][0]) == card
    assert harness.repository.get_word_form(canonical.id) == canonical


def test_structured_verification_survives_fresh_source_projection(
    harness: Harness, tmp_path: Path,
) -> None:
    lookup = harness.preview()
    with harness.ledger.engine.begin() as connection:
        payload = json.loads(connection.exec_driver_sql(
            "SELECT forms_payload FROM lookup_previews WHERE lookup_id=?", (lookup,),
        ).scalar_one())
        payload[0]["meaningsEn"][0]["verificationStatus"] = "VERIFIED"
        payload[0]["meaningsEn"][1]["verificationStatus"] = "MISSING"
        payload[0]["meaningsVi"][0]["verificationStatus"] = "VERIFIED"
        payload[0]["examples"][0]["verificationStatus"] = "VERIFIED"
        connection.exec_driver_sql(
            "UPDATE lookup_previews SET forms_payload=? WHERE lookup_id=?",
            (json.dumps(payload), lookup),
        )
    saved = harness.post(lookup)
    assert saved.status_code == 201
    parsed = parse_markdown((harness.root / "29-09-2026.md").read_text(encoding="utf-8"),
                            filename="29-09-2026.md")
    assert parsed.document is not None
    assert parsed.document.semantic_forms[0].meanings_en_statuses[0] == "VERIFIED"
    app = create_app(AppSettings(storage_path=tmp_path / "fresh-projection.db"),
                     markdown_root=harness.root)
    with TestClient(app, base_url=BASE):
        assert app.state.ready
        app.state.watcher.stop()
        repository = VocabularyRepository(app.state.database.engine)
        with app.state.database.engine.connect() as connection:
            source_id = connection.exec_driver_sql("SELECT id FROM source_files").scalar_one()
        noun = next(f for f in repository.get_forms_for_source(source_id)
                    if f.lemma == "anchor" and f.part_of_speech == "NOUN")
        assert noun.meanings_en[0].verification_status == "VERIFIED"
        assert noun.meanings_en[1].verification_status == "MISSING"
        assert noun.meanings_vi[0].verification_status == "VERIFIED"
        assert noun.examples[0].verification_status == "VERIFIED"
        assert noun.ipa_status == noun.cambridge_status == "MISSING"
        for reason in ("WATCHER", "MANUAL", "STARTUP"):
            assert app.state.sync_service.sync(reason=reason).sources_invalid == 0
            assert repository.get_word_form(noun.id) == noun

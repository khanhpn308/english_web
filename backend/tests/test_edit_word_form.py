"""T029 production PATCH regressions. Execution is deferred by the owner.

The T024 harness boots the production factory with synthetic notes and SQLite.
Only failure injection uses mocks; publication, journal and projections are real.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from threading import Event
from typing import Any
from unittest.mock import patch

import pytest
from backend.app.adapters.bridge import BridgeAdapter
from backend.app.application.edit_word_form import EditConflict, EditWordFormIntent
from backend.app.application.operations import OperationConflict
from backend.app.application.source_recovery import SourceRecovery
from backend.app.application.source_write import InjectedCrash
from backend.app.main import create_app
from backend.app.platform.config import AppSettings
from backend.app.review.models import record_review
from backend.tests import test_save_word_family as save_tests
from backend.tests.test_save_word_family import BASE, ORIGIN, Harness
from fastapi.testclient import TestClient
from sqlalchemy import Connection
from sqlalchemy.exc import SQLAlchemyError

save_harness = save_tests.harness


@pytest.fixture
def edit_harness(save_harness: Harness) -> Harness:
    return save_harness


def seed(h: Harness) -> dict[str, Any]:
    response = h.post(h.preview())
    assert response.status_code == 201
    result = response.json()
    assert isinstance(result, dict)
    return result


def patch_form(
    h: Harness, saved: dict[str, Any], fields: dict[str, Any], key: str = "edit",
    client: TestClient | None = None,
) -> Any:
    return (client or h.client).patch(
        f"/api/v1/word-forms/{saved['canonicalForms'][0]['id']}",
        json={"sourceId": saved["sourceId"], "sourceRevision": saved["sourceRevision"], **fields},
        headers={**ORIGIN, "Idempotency-Key": key, "If-Match": saved["sourceEtag"]},
    )


def meaning(text: str) -> dict[str, Any]:
    return {"meaningsEn": [{"text": text, "verificationStatus": "UNVERIFIED"}]}


def next_source(saved: dict[str, Any], response: Any) -> dict[str, Any]:
    return {**saved, "sourceRevision": response.json()["sourceRevision"],
            "sourceEtag": response.headers["etag"]}


def test_success_and_frozen_replay_after_later_edit(edit_harness: Harness) -> None:
    h = edit_harness
    saved = seed(h)
    first = patch_form(h, saved, meaning("first edit"))
    assert first.status_code == 200
    result = first.json()
    assert set(result) == {"wordForm", "operationId", "sourceRevision"}
    assert result["sourceRevision"] == 2
    assert result["wordForm"]["id"] == saved["canonicalForms"][0]["id"]
    second = patch_form(h, next_source(saved, first), meaning("second edit"), "edit-b")
    assert second.status_code == 200
    content = (h.root / "29-09-2026.md").read_bytes()
    count = h.count("source_write_journal")
    for _ in range(3):
        replay = patch_form(h, saved, meaning("first edit"))
        assert replay.status_code == 200 and replay.json() == result
        assert replay.headers["etag"] == first.headers["etag"]
    assert h.count("source_write_journal") == count
    assert (h.root / "29-09-2026.md").read_bytes() == content
    canonical = h.repository.get_word_form(result["wordForm"]["id"])
    assert canonical is not None and canonical.meanings_en[0].text == "second edit"


def test_unicode_and_opaque_context_survive_serialization(edit_harness: Harness) -> None:
    h = edit_harness
    saved = seed(h)
    path = h.root / "29-09-2026.md"
    context = "\n## Synthetic unrelated context\n\nKeep this paragraph and its spacing.\n"
    path.write_bytes(path.read_bytes() + context.encode("utf-8"))
    h.app.state.sync_service.sync(reason="MANUAL")
    source = h.repository.get_source_file(saved["sourceId"])
    assert source is not None
    saved = {**saved, "sourceRevision": source.revision, "sourceEtag": source.etag}
    unrelated = [h.repository.get_word_form(form["id"]) for form in saved["canonicalForms"][1:]]
    text = "Unicode 🧪 | `quotes`\n### literal text\n\u2028separated"
    response = patch_form(h, saved, meaning(text))
    assert response.status_code == 200
    assert response.json()["wordForm"]["meaningsEn"][0]["text"] == text
    assert path.read_text(encoding="utf-8").endswith(context)
    assert [h.repository.get_word_form(form["id"])
            for form in saved["canonicalForms"][1:]] == unrelated


@pytest.mark.parametrize("fields,reset", [
    (meaning("changed meaning"), True),
    ({"meaningsVi": [{"text": "nghĩa mới", "verificationStatus": "UNVERIFIED"}]}, True),
    ({"examples": [{"english": "Changed example.", "vietnamese": "Ví dụ mới.",
                    "verificationStatus": "UNVERIFIED"}]}, True),
    ({"ipaUs": "/changed/"}, False),
    ({"cambridgeUrl": "https://dictionary.cambridge.org/dictionary/english/anchor"}, False),
    ({"meaningsEn": [{"text": "first meaning", "verificationStatus": "VERIFIED"},
                     {"text": "second meaning", "verificationStatus": "UNVERIFIED"}]}, False),
    ({"examples": [{"english": "One 🧪 example.", "vietnamese": "Ví dụ một.",
                    "verificationStatus": "VERIFIED"},
                   {"english": "Second example.", "vietnamese": "Ví dụ hai.",
                    "verificationStatus": "UNVERIFIED"}]}, False),
    ({"ipaUs": None}, False),
])
def test_reset_exactly_once_and_retain_history(
    edit_harness: Harness, fields: dict[str, Any], reset: bool,
) -> None:
    h = edit_harness
    saved = seed(h)
    card_id = saved["canonicalForms"][0]["card"]["id"]
    h.review(card_id)
    before, history = h.card(card_id), h.history()
    response = patch_form(h, saved, fields)
    assert response.status_code == 200
    after = h.card(card_id)
    assert after is not None and before is not None
    if reset:
        assert after.box == 0 and after.due_at is None
        assert after.queue_revision == before.queue_revision + 1
    else:
        assert after == before
    assert response.json()["wordForm"]["card"]["id"] == card_id
    assert patch_form(h, saved, fields).json() == response.json()
    h.app.state.sync_service.sync(reason="MANUAL")
    assert h.card(card_id) == after and h.history() == history


def test_stale_revision_and_changed_intent(edit_harness: Harness) -> None:
    h = edit_harness
    saved = seed(h)
    assert patch_form(h, saved, meaning("first")).status_code == 200
    stale = patch_form(h, saved, meaning("second"), "other-client")
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "REVISION_CONFLICT"
    changed = patch_form(h, saved, meaning("second"))
    assert changed.status_code == 422
    assert changed.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"


def test_concurrent_clients_same_etag(edit_harness: Harness) -> None:
    h = edit_harness
    saved = seed(h)
    clients = [TestClient(h.app, base_url=BASE) for _ in range(2)]
    for client in clients:
        client.cookies.update(h.client.cookies)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(patch_form, h, saved, meaning(f"edit {i}"),
                                   f"client-{i}", client) for i, client in enumerate(clients)]
            responses = [future.result(timeout=15) for future in futures]
        assert sorted(response.status_code for response in responses) == [200, 409]
        loser = next(response for response in responses if response.status_code == 409)
        assert loser.json()["error"]["code"] == "REVISION_CONFLICT"
        source = h.repository.get_source_file(saved["sourceId"])
        assert source is not None and source.revision == 2
    finally:
        for client in clients:
            client.close()


@pytest.mark.parametrize("point", ["AFTER_PREPARED", "AFTER_TEMP_FSYNC",
                                  "AFTER_ATOMIC_REPLACE", "AFTER_SOURCE_REPLACED",
                                  "AFTER_RECEIPT"])
def test_crash_unknown_recovery_and_lost_response(edit_harness: Harness, point: str) -> None:
    h = edit_harness
    saved = seed(h)
    service = h.app.state.edit_word_form_service
    old = (h.root / "29-09-2026.md").read_bytes()

    def crash(at: str) -> None:
        if at == point:
            raise InjectedCrash(at)

    service.fault = crash
    with pytest.raises(InjectedCrash):
        patch_form(h, saved, meaning("crash edit"))
    service.fault = None
    h.ledger.recover_pending()
    if point != "AFTER_RECEIPT":
        pending = patch_form(h, saved, meaning("crash edit"))
        assert pending.status_code == 409
        assert pending.json()["error"]["code"] == "IDEMPOTENCY_IN_FLIGHT"
    records = SourceRecovery(service.coordinator).reconcile(operation_ledger=h.ledger)
    committed = point in {"AFTER_ATOMIC_REPLACE", "AFTER_SOURCE_REPLACED", "AFTER_RECEIPT"}
    replay = patch_form(h, saved, meaning("crash edit"))
    if committed:
        assert replay.status_code == 200
        if records:
            assert replay.json() == records[0].effect_plan["receipt"]
    else:
        assert replay.status_code == 409
        assert (h.root / "29-09-2026.md").read_bytes() == old
    assert SourceRecovery(service.coordinator).reconcile(operation_ledger=h.ledger) == []


@pytest.mark.parametrize("before_stage", [True, False])
def test_external_editor_never_overwritten(edit_harness: Harness, before_stage: bool) -> None:
    h = edit_harness
    saved = seed(h)
    path = h.root / "29-09-2026.md"
    external = path.read_bytes() + b"\nExternal synthetic context.\n"
    service = h.app.state.edit_word_form_service
    if before_stage:
        path.write_bytes(external)
    else:
        def edit(at: str) -> None:
            if at == "AFTER_TEMP_FSYNC":
                path.write_bytes(external)
        service.fault = edit
    response = patch_form(h, saved, meaning("must not overwrite"))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "REVISION_CONFLICT"
    assert path.read_bytes() == external
    form = h.repository.get_word_form(saved["canonicalForms"][0]["id"])
    assert form is not None and form.meanings_en[0].text == "first meaning"


@pytest.mark.parametrize("fields", [
    {}, {"lemma": "foreign"}, {"relativePath": "../../private.md"}, {"card": {}},
    {"ipaStatus": "VERIFIED"}, {"meaningsEn": []}, {"examples": None},
    {"meaningsEn": [{"text": " ", "verificationStatus": "VERIFIED"}]},
    {"meaningsEn": [{"text": "x", "language": "vi", "verificationStatus": "VERIFIED"}]},
    {"meaningsEn": [{"text": "x", "verificationStatus": "UNKNOWN"}]},
    {"ipaUs": "x" * 129}, {"ipaUs": "\ud800"},
    {"cambridgeUrl": "javascript:synthetic"},
    {"cambridgeUrl": "https://hostile.test/dictionary/english/anchor"},
])
def test_strict_editable_allowlist(edit_harness: Harness, fields: dict[str, Any]) -> None:
    h = edit_harness
    saved = seed(h)
    original = (h.root / "29-09-2026.md").read_bytes()
    response = patch_form(h, saved, fields)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert (h.root / "29-09-2026.md").read_bytes() == original


def test_storage_failure_rolls_back_and_recovers(edit_harness: Harness) -> None:
    h = edit_harness
    saved = seed(h)
    h.review(saved["canonicalForms"][0]["card"]["id"])
    history = h.history()
    service = h.app.state.edit_word_form_service

    def fail(at: str) -> None:
        if at == "AFTER_CARD_RESET":
            raise SQLAlchemyError("synthetic storage failure")

    service.fault = fail
    response = patch_form(h, saved, meaning("recovered"))
    assert response.status_code == 503
    source = h.repository.get_source_file(saved["sourceId"])
    assert source is not None and source.revision == 1
    assert h.history() == history
    service.fault = None
    records = SourceRecovery(service.coordinator).reconcile(operation_ledger=h.ledger)
    assert records[0].state == "COMMITTED"
    replay = patch_form(h, saved, meaning("recovered"))
    assert replay.status_code == 200 and h.history() == history


@pytest.mark.parametrize("fields,reset", [(meaning("recovered meaning"), True),
                                         ({"ipaUs": "/recovered/"}, False)])
def test_recovery_retains_intervening_review_and_original_receipt(
    edit_harness: Harness, fields: dict[str, Any], reset: bool,
) -> None:
    h = edit_harness
    saved = seed(h)
    card_id = saved["canonicalForms"][0]["card"]["id"]
    service = h.app.state.edit_word_form_service

    def fail(point: str) -> None:
        if point == "AFTER_CARD_RESET":
            raise SQLAlchemyError("synthetic receipt failure")

    service.fault = fail
    failed = patch_form(h, saved, fields)
    assert failed.status_code == 503
    operation_id = failed.json()["error"]["details"]["operationId"]
    journal = service.coordinator.get(operation_id)
    assert journal is not None and journal.state == "PREPARED"
    frozen = journal.effect_plan["receipt"]
    etag = journal.effect_plan["response_etag"]
    # This genuine review commits while the published edit awaits recovery.
    h.review(card_id)
    advanced, history = h.card(card_id), h.history()
    service.fault = None
    recovered = SourceRecovery(service.coordinator).reconcile(operation_ledger=h.ledger)
    assert recovered[0].state == "COMMITTED"
    replay = patch_form(h, saved, fields)
    assert replay.status_code == 200 and replay.json() == frozen
    assert replay.headers["etag"] == etag
    after = h.card(card_id)
    if reset:
        assert after.box == 0 and after.due_at is None
        assert after.queue_revision == advanced.queue_revision + 1
    else:
        assert after == advanced
    assert h.history() == history
    assert SourceRecovery(service.coordinator).reconcile(operation_ledger=h.ledger) == []
    assert patch_form(h, saved, fields).json() == frozen
    assert h.card(card_id) == after


@pytest.mark.parametrize("variant,code,status", [
    ("missing", "SOURCE_MISSING", 404), ("invalid", "SOURCE_NOT_WRITABLE", 409),
    ("deleted", "SOURCE_NOT_WRITABLE", 409), ("foreign", "CROSS_RESOURCE_MISMATCH", 422),
    ("ambiguous", "SOURCE_NOT_WRITABLE", 409),
])
def test_invalid_missing_or_foreign_source(
    edit_harness: Harness, variant: str, code: str, status: int,
) -> None:
    h = edit_harness
    saved = seed(h)
    source = h.repository.get_source_file(saved["sourceId"])
    assert source is not None
    if variant == "missing":
        saved = {**saved, "sourceId": "src_missing"}
    elif variant in {"foreign", "ambiguous"}:
        h.repository.save_source_file(
            source_id="src_foreign", relative_path="foreign.md",
            note_date=source.note_date if variant == "ambiguous" else "2026-09-30",
            content_hash="0" * 64,
        )
        if variant == "foreign":
            saved = {**saved, "sourceId": "src_foreign"}
    else:
        with h.ledger.engine.begin() as connection:
            connection.exec_driver_sql(
                "UPDATE source_files SET status=? WHERE id=?",
                ("INVALID" if variant == "invalid" else "MISSING", source.id),
            )
    original = (h.root / "29-09-2026.md").read_bytes()
    response = patch_form(h, saved, meaning("denied"))
    assert response.status_code == status and response.json()["error"]["code"] == code
    assert response.json()["error"]["requestId"]
    assert "denied" not in response.text and str(h.root) not in response.text
    assert (h.root / "29-09-2026.md").read_bytes() == original


@pytest.mark.parametrize("omitted", ["Idempotency-Key", "If-Match", "sourceId", "sourceRevision"])
def test_required_headers_and_source_pair(edit_harness: Harness, omitted: str) -> None:
    h = edit_harness
    saved = seed(h)
    body = {"sourceId": saved["sourceId"], "sourceRevision": saved["sourceRevision"],
            **meaning("denied")}
    headers = {**ORIGIN, "Idempotency-Key": "edit", "If-Match": saved["sourceEtag"]}
    if omitted in headers:
        del headers[omitted]
    else:
        del body[omitted]
    response = h.client.patch(f"/api/v1/word-forms/{saved['canonicalForms'][0]['id']}",
                              json=body, headers=headers)
    assert response.status_code == 422
    assert h.count("source_write_journal") == 1


@pytest.mark.parametrize("revision", [True, "1", 0, -1, None])
def test_source_revision_is_a_positive_integer(edit_harness: Harness, revision: Any) -> None:
    h = edit_harness
    saved = seed(h)
    response = patch_form(h, {**saved, "sourceRevision": revision}, meaning("denied"))
    assert response.status_code == 422


def test_current_numeric_revision_with_wrong_opaque_etag(edit_harness: Harness) -> None:
    h = edit_harness
    saved = seed(h)
    response = patch_form(h, {**saved, "sourceEtag": '"foreign-etag"'}, meaning("denied"))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "REVISION_CONFLICT"


def test_deleted_file_or_unknown_form_cannot_mutate_storage(edit_harness: Harness) -> None:
    h = edit_harness
    saved = seed(h)
    missing_form = {**saved, "canonicalForms": [{"id": "wf_missing"}]}
    response = patch_form(h, missing_form, meaning("denied"), "missing-form")
    assert response.status_code == 404 and response.json()["error"]["code"] == "NOT_FOUND"
    (h.root / "29-09-2026.md").unlink()
    response = patch_form(h, saved, meaning("denied"), "missing-file")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SOURCE_NOT_WRITABLE"
    assert not (h.root / "29-09-2026.md").exists()
    assert h.count("source_write_journal") == 1


@pytest.mark.parametrize("headers,query", [
    ([("Idempotency-Key", "edit"), ("Idempotency-Key", "duplicate")], ""),
    ([("If-Match", '"duplicate"')], ""),
    ([("If-None-Match", "*")], ""),
    ([], "?relativePath=foreign.md"),
])
def test_ambiguous_headers_or_query_are_rejected(
    edit_harness: Harness, headers: list[tuple[str, str]], query: str,
) -> None:
    h = edit_harness
    saved = seed(h)
    request_headers = [*ORIGIN.items(), ("Idempotency-Key", "edit"),
                       ("If-Match", saved["sourceEtag"]), *headers]
    response = h.client.patch(
        f"/api/v1/word-forms/{saved['canonicalForms'][0]['id']}{query}",
        json={"sourceId": saved["sourceId"], "sourceRevision": 1, **meaning("denied")},
        headers=request_headers,
    )
    assert response.status_code == 422
    assert h.count("source_write_journal") == 1


def test_normalized_content_bounds_and_collection_limit(edit_harness: Harness) -> None:
    h = edit_harness
    saved = seed(h)
    # Bounds apply after NFC, so this otherwise overlong decomposed input fits.
    response = patch_form(h, saved, meaning("e\u0301" * 4096), "at-cap")
    assert response.status_code == 200
    assert response.json()["wordForm"]["meaningsEn"][0]["text"] == "é" * 4096
    current = next_source(saved, response)
    assert patch_form(h, current, meaning("x" * 4097), "too-long").status_code == 422
    too_many = {"meaningsEn": [{"text": "x", "verificationStatus": "UNVERIFIED"}] * 101}
    assert patch_form(h, current, too_many, "too-many").status_code == 422


def test_origin_session_and_post_save_preserved(edit_harness: Harness) -> None:
    h = edit_harness
    saved = seed(h)
    path = f"/api/v1/word-forms/{saved['canonicalForms'][0]['id']}"
    body = {"sourceId": saved["sourceId"], "sourceRevision": 1, **meaning("denied")}
    headers = {"Idempotency-Key": "edit", "If-Match": saved["sourceEtag"]}
    hostile = h.client.patch(
        path, json=body, headers={**headers, "Origin": "http://hostile.test"},
    )
    assert hostile.status_code == 403
    client = TestClient(h.app, base_url=BASE)
    try:
        assert client.patch(path, json=body, headers={**headers, **ORIGIN}).status_code == 401
    finally:
        client.close()
    edit = patch_form(h, saved, {"ipaUs": "/a/"})
    assert edit.status_code == 200
    subsequent_save = h.post(h.preview("after-edit"), key="save-after-edit",
                            source=next_source(saved, edit))
    assert subsequent_save.status_code == 201
    assert subsequent_save.json()["sourceRevision"] == 3
    with h.ledger.engine.connect() as connection:
        assert connection.exec_driver_sql(
            "SELECT status FROM lookup_previews WHERE lookup_id='lookup_after-edit'"
        ).scalar_one() == "CONSUMED"


def test_shared_dates_and_unrelated_form_content_preserved(edit_harness: Harness) -> None:
    h = edit_harness
    saved = seed(h)
    other = h.post("lookup_base", key="other-day", day="2026-09-30").json()
    forms = save_tests.provider_forms()
    forms[1]["meaningsEn"][0]["text"] = "newer unrelated canonical meaning"
    updated = h.post(h.preview("other-update", forms), key="save-other", source=other)
    assert updated.status_code == 201
    unrelated_id = saved["canonicalForms"][1]["id"]
    before = h.repository.get_word_form(unrelated_id)
    card_id = saved["canonicalForms"][0]["card"]["id"]
    h.review(card_id)
    card, history = h.card(card_id), h.history()
    other_bytes = (h.root / "30-09-2026.md").read_bytes()
    edit = patch_form(h, saved, {"ipaUs": "/new/"})
    assert edit.status_code == 200
    assert h.repository.get_word_form(unrelated_id) == before
    assert h.card(card_id) == card and h.history() == history
    assert (h.root / "30-09-2026.md").read_bytes() == other_bytes
    assert len(edit.json()["wordForm"]["sourceRefs"]) == 2
    assert {ref["sourceId"] for ref in edit.json()["wordForm"]["sourceRefs"]} == {
        saved["sourceId"], other["sourceId"],
    }
    assert all(ref["status"] == "VALID" for ref in edit.json()["wordForm"]["sourceRefs"])
    assert h.count("review_cards") == 3


def test_prepare_storage_failure_has_no_visible_effect(edit_harness: Harness) -> None:
    h = edit_harness
    saved = seed(h)
    original = (h.root / "29-09-2026.md").read_bytes()

    def fail(point: str) -> None:
        if point == "BEFORE_PREPARED":
            raise SQLAlchemyError("synthetic prepare failure")

    h.app.state.edit_word_form_service.fault = fail
    response = patch_form(h, saved, meaning("never published"))
    assert response.status_code == 503
    assert h.count("source_write_journal") == 1
    assert (h.root / "29-09-2026.md").read_bytes() == original


def test_edit_never_dispatches_ai(edit_harness: Harness) -> None:
    h = edit_harness
    saved = seed(h)
    with (
        patch.object(BridgeAdapter, "dispatch_chat", side_effect=AssertionError("AI prohibited")),
        patch.object(BridgeAdapter, "preflight", side_effect=AssertionError("AI prohibited")),
    ):
        assert patch_form(h, saved, meaning("local edit")).status_code == 200


def test_frozen_receipt_replays_under_new_restart_session(tmp_path: Path) -> None:
    root = tmp_path / "notes"
    root.mkdir()
    settings = AppSettings(storage_path=tmp_path / "edit.db")
    app = create_app(settings, markdown_root=root)
    with TestClient(app, base_url=BASE) as client:
        app.state.watcher.stop()
        token = app.state.sessions.issue_bootstrap_token()
        bootstrap = client.post("/bootstrap/exchange", json={"token": token}, headers=ORIGIN)
        assert bootstrap.status_code == 204
        h = Harness(app, client, root)
        saved = seed(h)
        first = patch_form(h, saved, meaning("historic edit"))
        assert first.status_code == 200
        later = patch_form(h, next_source(saved, first), meaning("later edit"), "later")
        assert later.status_code == 200
        original = first.json()
        etag = first.headers["etag"]
    restarted = create_app(settings, markdown_root=root)
    with TestClient(restarted, base_url=BASE) as client:
        assert restarted.state.ready
        restarted.state.watcher.stop()
        token = restarted.state.sessions.issue_bootstrap_token()
        bootstrap = client.post("/bootstrap/exchange", json={"token": token}, headers=ORIGIN)
        assert bootstrap.status_code == 204
        h = Harness(restarted, client, root)
        before = (root / "29-09-2026.md").read_bytes()
        replay = patch_form(h, saved, meaning("historic edit"))
        assert replay.status_code == 200 and replay.json() == original
        assert replay.headers["etag"] == etag
        assert (root / "29-09-2026.md").read_bytes() == before


def test_identical_inflight_intent_does_not_write_twice(edit_harness: Harness) -> None:
    h = edit_harness
    saved = seed(h)
    service = h.app.state.edit_word_form_service
    prepared, release = Event(), Event()
    intent = EditWordFormIntent.model_validate({
        "sourceId": saved["sourceId"], "sourceRevision": 1, **meaning("once"),
    })
    form_id = saved["canonicalForms"][0]["id"]

    def pause(point: str) -> None:
        if point == "AFTER_PREPARED":
            prepared.set()
            assert release.wait(timeout=10)

    service.fault = pause
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(service.edit, word_form_id=form_id, intent=intent,
                             idempotency_key="inflight", if_match=saved["sourceEtag"])
        try:
            assert prepared.wait(timeout=10)
            with pytest.raises(OperationConflict) as error:
                service.edit(word_form_id=form_id, intent=intent, idempotency_key="inflight",
                             if_match=saved["sourceEtag"])
            assert error.value.code == "IDEMPOTENCY_IN_FLIGHT"
            assert error.value.operation_id is not None
            with pytest.raises(EditConflict) as incomplete:
                service.receipt(error.value.operation_id, form_id, saved["sourceId"])
            assert incomplete.value.code == "IDEMPOTENCY_IN_FLIGHT"
            source = h.repository.get_source_file(saved["sourceId"])
            assert source is not None and source.revision == 1
        finally:
            release.set()
        result, etag = future.result(timeout=15)
    service.fault = None
    replay, replay_etag = service.edit(word_form_id=form_id, intent=intent,
                                       idempotency_key="inflight", if_match=saved["sourceEtag"])
    assert (replay, replay_etag) == (result, etag)
    assert h.count("source_write_journal") == 2


def test_review_cannot_strand_published_metadata_edit(edit_harness: Harness) -> None:
    h = edit_harness
    saved = seed(h)
    card_id = saved["canonicalForms"][0]["card"]["id"]
    h.review(card_id)
    history = h.history()
    claim = h.ledger.claim(
        kind="REVIEW", key="concurrent-review", method="POST", path="/review",
        body={"cardId": card_id}, preconditions={},
    )
    published, review_started, review_finished = Event(), Event(), Event()

    def pause(point: str) -> None:
        if point == "AFTER_ATOMIC_REPLACE":
            published.set()
            assert review_started.wait(timeout=5)
            # The competing real writer must remain blocked until the edit's
            # projection and receipt transaction commits. The old gap lets this
            # review complete here, making the subsequent edit permanently degrade.
            assert not review_finished.wait(timeout=0.1)

    def review() -> None:
        assert published.wait(timeout=5)
        review_started.set()

        def apply(connection: Connection) -> None:
            record_review(
                connection, card_id=card_id, event_id="review_concurrent",
                operation_id=claim.operation.operation_id, source="FLASHCARD", rating="GOOD",
                reviewed_at=datetime(2026, 9, 29, 11, 20, 30, tzinfo=UTC),
            )

        h.ledger.complete(claim.operation.operation_id, response_status=200,
                          result_ref="review_concurrent", local_write=apply)
        review_finished.set()

    h.app.state.edit_word_form_service.fault = pause
    with ThreadPoolExecutor(max_workers=2) as pool:
        review_future = pool.submit(review)
        edit_future = pool.submit(patch_form, h, saved, {"ipaUs": "/metadata/"})
        response = edit_future.result(timeout=15)
        review_future.result(timeout=15)
    assert response.status_code == 200
    operation_id = response.json()["operationId"]
    journal = h.service.coordinator.get(operation_id)
    assert journal is not None and journal.state == "COMMITTED"
    after_history = h.history()
    assert len(after_history) == len(history) + 1
    assert all(row in after_history for row in history)
    assert h.card(card_id).box > 0

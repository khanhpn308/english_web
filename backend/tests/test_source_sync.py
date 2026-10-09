"""Comprehensive behavioral tests for Markdown source synchronization and source API (T023).

Tests:
1. AC-09: Invalid F excludes X; valid G keeps Y. Y does not use F's invalid content.
2. AC-10: All-sources-deleted suspends card from review queue but retains historical records;
   re-add reuses card.
3. AC-31: External meaning/example edit resets card once; non-learning edit does not reset;
   app-write watcher echo does not double reset or double increment revision.
4. Two valid sources with conflicting definitions do not pick an arbitrary winner.
5. GET /api/v1/sources: query filters, cursor pagination, tamper/expiry protection (409),
   unknown query param rejection (400), session enforcement (401).
6. POST /api/v1/sync-runs: idempotency replay, key reused rejection (422), valid reasons (202).
7. GET /api/v1/sync-runs/{syncRunId}: returns real state (200), missing run (404).
8. Watcher debounce, storm coalescing, and safe shutdown.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import threading
import time
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from pathlib import Path
from secrets import token_urlsafe
from typing import Any

import pytest
from backend.app.adapters.source_files import (
    SourceFileAdapter,
    SourceFileError,
    SourceSecurityError,
)
from backend.app.adapters.watcher import SourceWatcher
from backend.app.application.operations import OperationLedger
from backend.app.application.source_write import SourceWriteCoordinator
from backend.app.application.sync import CursorExpiredError, SyncReason, SyncService
from backend.app.main import create_app
from backend.app.markdown_sync.parser import parse_markdown
from backend.app.markdown_sync.serializer import upsert_structured_family
from backend.app.persistence.database import Database
from backend.app.platform.config import AppSettings
from backend.app.review.models import ensure_card, get_card, record_review
from backend.app.vocabulary.models import MeaningVi
from backend.app.vocabulary.repository import VocabularyRepository
from backend.app.vocabulary.search_index import SearchIndex
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Connection

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


@pytest.fixture
def test_db(db_path: Path) -> Iterator[Database]:
    db = Database(db_path)
    db.initialize()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def markdown_root(tmp_path: Path) -> Path:
    root = tmp_path / "vocabularies"
    root.mkdir(parents=True, exist_ok=True)
    return root


SAMPLE_NOTE_G = """# 29-09-2026

## Tra cứu nhanh

| Từ/cụm từ | IPA (US) | Nghĩa ngắn | Ví dụ ngắn | Dịch ví dụ |
|---|---|---|---|---|
| [robust](#robust) | /roʊ.bʌst/ | Bền vững | The system is robust. | Hệ thống rất bền. |

## Robust

| Từ/cụm từ | Từ loại | IPA (US) | Trọng âm | Nguồn |
|---|---|---|---|---|
| robust | adjective | /roʊ.bʌst/ | Âm tiết 2 | [Cambridge](https://cambridge.org/robust) |

### Ý nghĩa

- **Nghĩa thông dụng**: bền vững, vững chắc

### Trong ngữ cảnh

The system is robust and secure.

### Ví dụ

The system is robust.

*Bản dịch:* Hệ thống rất bền vững.
"""

SAMPLE_NOTE_F = """# 28-09-2026

## Tra cứu nhanh

| Từ/cụm từ | IPA (US) | Nghĩa ngắn | Ví dụ ngắn | Dịch ví dụ |
|---|---|---|---|---|
| [fragile](#fragile) | /frædʒ.ail/ | Dễ vỡ, mỏng manh | The glass is fragile. | Ly rất dễ vỡ. |
| [robust](#robust) | /roʊ.bʌst/ | Bền vững | The system is robust. | Hệ thống rất bền. |

## Fragile

| Từ/cụm từ | Từ loại | IPA (US) | Trọng âm | Nguồn |
|---|---|---|---|---|
| fragile | adjective | /frædʒ.ail/ | Âm tiết 1 | [Cambridge](https://cambridge.org/fragile) |

### Ý nghĩa

- **Nghĩa thông dụng**: dễ vỡ, mỏng manh

### Trong ngữ cảnh

Handle with care because it is fragile.

### Ví dụ

The glass is fragile.

*Bản dịch:* Chiếc ly rất dễ vỡ.

## Robust

| Từ/cụm từ | Từ loại | IPA (US) | Trọng âm | Nguồn |
|---|---|---|---|---|
| robust | adjective | /roʊ.bʌst/ | Âm tiết 2 | [Cambridge](https://cambridge.org/robust) |

### Ý nghĩa

- **Nghĩa thông dụng**: bền vững, vững chắc

### Trong ngữ cảnh

The system is robust.

### Ví dụ

The system is robust.

*Bản dịch:* Hệ thống rất bền vững.
"""


def test_structured_verification_precedence_and_metadata_only_updates(
    test_db: Database, markdown_root: Path,
) -> None:
    """Explicit field states replace stale projection; learning text alone resets SRS."""
    payload: dict[str, Any] = {"version": 1, "familyRoot": "robust", "forms": [
        {
            "lemma": "robust", "partOfSpeech": pos,
            "meaningsEn": [
                {"text": "first English", "language": "en", "verificationStatus": "VERIFIED"},
                {"text": "second English", "language": "en", "verificationStatus": "MISSING"},
            ],
            "meaningsVi": [
                {"text": "nghĩa đầu", "language": "vi", "verificationStatus": "UNVERIFIED"},
                {"text": "nghĩa sau", "language": "vi", "verificationStatus": "VERIFIED"},
            ],
            "examples": [
                {"english": "One example.", "vietnamese": "Ví dụ một.",
                 "verificationStatus": "VERIFIED"},
                {"english": "Two examples.", "vietnamese": "Hai ví dụ.",
                 "verificationStatus": "MISSING"},
            ],
            "ipaUs": "/roʊ.bʌst/", "ipaStatus": "VERIFIED",
            "cambridgeUrl": "https://dictionary.cambridge.org/dictionary/english/robust",
            "cambridgeStatus": "UNVERIFIED",
        }
        for pos in ("ADJECTIVE", "VERB")
    ]}
    # Deliberately distinct grammatical-form verification; association must not collapse.
    payload["forms"][1]["meaningsEn"][0]["verificationStatus"] = "UNVERIFIED"
    path = markdown_root / "29-09-2026.md"

    def write_structured() -> None:
        parsed = parse_markdown(path.read_text(encoding="utf-8") if path.exists()
                                else SAMPLE_NOTE_G, filename=path.name)
        assert parsed.is_valid and parsed.document is not None
        path.write_text(upsert_structured_family(parsed.document, payload), encoding="utf-8")

    write_structured()
    ledger = OperationLedger(test_db.engine)
    service = SyncService(test_db.engine, markdown_root, operation_ledger=ledger)
    repo = VocabularyRepository(test_db.engine)
    assert service.sync(reason="STARTUP").sources_invalid == 0
    forms = {f.part_of_speech: f for f in repo.get_forms_for_date("2026-09-29")}
    assert set(forms) == {"ADJECTIVE", "VERB"}
    adjective = forms["ADJECTIVE"]
    assert [m.verification_status for m in adjective.meanings_en] == ["VERIFIED", "MISSING"]
    assert [m.verification_status for m in adjective.meanings_vi] == ["UNVERIFIED", "VERIFIED"]
    assert [e.verification_status for e in adjective.examples] == ["VERIFIED", "MISSING"]
    assert forms["VERB"].meanings_en[0].verification_status == "UNVERIFIED"
    assert adjective.ipa_status == "VERIFIED" and adjective.cambridge_status == "UNVERIFIED"
    with test_db.engine.connect() as connection:
        card_id = str(connection.exec_driver_sql(
            "SELECT card_id FROM review_cards WHERE word_form_id=?", (adjective.id,),
        ).scalar_one())
    claim = ledger.claim(kind="REVIEW", key="structured-review", method="POST", path="/review",
                         body={"cardId": card_id}, preconditions={})

    def review(connection: Connection) -> None:
        record_review(connection, card_id=card_id, event_id="structured-review-event",
                      operation_id=claim.operation.operation_id, source="FLASHCARD", rating="GOOD",
                      reviewed_at=datetime(2026, 9, 29, 10, tzinfo=UTC))

    ledger.complete(claim.operation.operation_id, response_status=200,
                    result_ref="structured-review-event", local_write=review)
    with test_db.engine.connect() as connection:
        progress = get_card(connection, card_id)
        history = list(connection.exec_driver_sql("SELECT * FROM review_events ORDER BY id"))
    echo_reasons: tuple[SyncReason, ...] = ("WATCHER", "STARTUP")
    for reason in echo_reasons:
        assert service.sync(reason=reason).sources_invalid == 0
        assert repo.get_word_form(adjective.id) == adjective

    payload["forms"][0]["meaningsEn"][0]["verificationStatus"] = "UNVERIFIED"
    payload["forms"][0]["meaningsVi"][0]["verificationStatus"] = "MISSING"
    payload["forms"][0]["examples"][0]["verificationStatus"] = "MISSING"
    payload["forms"][0]["ipaStatus"] = "UNVERIFIED"
    payload["forms"][0]["cambridgeStatus"] = "VERIFIED"
    write_structured()
    assert service.sync(reason="WATCHER").sources_invalid == 0
    updated = repo.get_word_form(adjective.id)
    assert updated is not None and updated.revision == adjective.revision + 1
    assert updated.meanings_en[0].verification_status == "UNVERIFIED"
    assert updated.meanings_vi[0].verification_status == "MISSING"
    assert updated.examples[0].verification_status == "MISSING"
    assert updated.ipa_status == "UNVERIFIED" and updated.cambridge_status == "VERIFIED"
    assert repo.get_word_form(forms["VERB"].id) == forms["VERB"]
    # A status-only edit of IPA/link must also persist when all learning fields are identical.
    payload["forms"][0]["ipaStatus"] = "VERIFIED"
    payload["forms"][0]["cambridgeStatus"] = "UNVERIFIED"
    write_structured()
    assert service.sync(reason="WATCHER").sources_invalid == 0
    metadata = repo.get_word_form(adjective.id)
    assert metadata is not None and metadata.revision == updated.revision + 1
    assert metadata.ipa_status == "VERIFIED" and metadata.cambridge_status == "UNVERIFIED"
    with test_db.engine.connect() as connection:
        assert get_card(connection, card_id) == progress
        assert list(connection.exec_driver_sql("SELECT * FROM review_events ORDER BY id")) == history
    assert service.sync(reason="WATCHER").sources_invalid == 0
    assert repo.get_word_form(adjective.id) == metadata

    payload["forms"][0]["examples"][0]["english"] = "Actual learning content edit."
    write_structured()
    assert service.sync(reason="WATCHER").sources_invalid == 0
    with test_db.engine.connect() as connection:
        reset = get_card(connection, card_id)
        assert reset is not None and progress is not None
        assert reset.box == 0 and reset.due_at is None
        assert reset.queue_revision == progress.queue_revision + 1
        assert list(connection.exec_driver_sql("SELECT * FROM review_events ORDER BY id")) == history
    recreated = SyncService(test_db.engine, markdown_root, operation_ledger=ledger)
    assert recreated.sync(reason="STARTUP").sources_invalid == 0
    assert recreated.sync(reason="WATCHER").sources_invalid == 0
    with test_db.engine.connect() as connection:
        assert get_card(connection, card_id) == reset
        assert list(connection.exec_driver_sql("SELECT * FROM review_events ORDER BY id")) == history


def test_legacy_source_without_structured_verification_uses_unverified_fallback(
    test_db: Database, markdown_root: Path,
) -> None:
    path = markdown_root / "29-09-2026.md"
    path.write_text(SAMPLE_NOTE_G, encoding="utf-8")
    service = SyncService(test_db.engine, markdown_root)
    repo = VocabularyRepository(test_db.engine)
    assert service.sync(reason="STARTUP").sources_invalid == 0
    form = repo.get_forms_for_date("2026-09-29")[0]
    assert all(m.verification_status == "UNVERIFIED" for m in form.meanings_vi)
    assert all(e.verification_status == "UNVERIFIED" for e in form.examples)
    assert form.ipa_status == form.cambridge_status == "UNVERIFIED"
    assert form.verification_summary != "VERIFIED"
    assert service.sync(reason="WATCHER").sources_invalid == 0
    assert repo.get_word_form(form.id) == form


def test_ac09_invalid_source_excludes_x_and_valid_source_keeps_y(
    test_db: Database, markdown_root: Path
) -> None:
    """AC-09: File F contains X, Y; file G valid contains Y; X/Y initially eligible.
    F becomes invalid -> X excluded; Y kept from G; Y does not use F's invalid content.
    """
    file_g = markdown_root / "29-09-2026.md"
    file_f = markdown_root / "28-09-2026.md"
    file_g.write_text(SAMPLE_NOTE_G, encoding="utf-8")
    file_f.write_text(SAMPLE_NOTE_F, encoding="utf-8")

    ledger = OperationLedger(test_db.engine)
    sync_service = SyncService(test_db.engine, markdown_root, operation_ledger=ledger)

    # Initial sync: both F and G valid
    result = sync_service.sync(reason="MANUAL")
    assert result.status == "COMPLETED"
    assert result.sources_scanned == 2
    assert result.sources_invalid == 0

    repo = VocabularyRepository(test_db.engine)
    forms_f = repo.get_forms_for_date("2026-09-28", only_valid_sources=True)
    forms_g = repo.get_forms_for_date("2026-09-29", only_valid_sources=True)
    assert any(wf.lemma == "fragile" for wf in forms_f)
    assert any(wf.lemma == "robust" for wf in forms_g)

    # Corrupt file F (invalid markdown without required sections/table)
    file_f.write_text(
        "MALFORMED CONTENT WITHOUT HEADERS OR METADATA\n\n- invalid", encoding="utf-8"
    )

    # Second sync: F is now invalid
    result2 = sync_service.sync(reason="MANUAL")
    assert result2.status == "COMPLETED"
    assert result2.sources_invalid == 1

    # In 2026-09-28 (F), no valid forms remain
    forms_f_after = repo.get_forms_for_date("2026-09-28", only_valid_sources=True)
    assert not any(wf.lemma == "fragile" for wf in forms_f_after)

    # In 2026-09-29 (G), robust is still valid and present from G!
    forms_g_after = repo.get_forms_for_date("2026-09-29", only_valid_sources=True)
    robust_form = next(wf for wf in forms_g_after if wf.lemma == "robust")
    assert robust_form is not None
    # Meaning is from G
    assert any("Hệ thống rất bền vững" in e.vietnamese for e in robust_form.examples)


def test_ac10_all_sources_deleted_suspends_card_retains_history(
    test_db: Database, markdown_root: Path
) -> None:
    """AC-10: X has review history; deleting X from all files suspends card from review queue
    but retains historical review records; re-adding X reuses the historical card.
    """
    file_f = markdown_root / "28-09-2026.md"
    file_f.write_text(SAMPLE_NOTE_F, encoding="utf-8")

    ledger = OperationLedger(test_db.engine)
    sync_service = SyncService(test_db.engine, markdown_root, operation_ledger=ledger)
    sync_service.sync(reason="MANUAL")

    repo = VocabularyRepository(test_db.engine)
    fragile = next(wf for wf in repo.get_forms_for_date("2026-09-28") if wf.lemma == "fragile")

    # Record a review for fragile
    op_rev_1 = ledger.claim(
        kind="REVIEW",
        key=f"rev-key-{token_urlsafe(8)}",
        method="POST",
        path="/synthetic/review",
        body={"rating": "GOOD"},
        preconditions={},
    ).operation.operation_id
    with (
        test_db.engine.connect().execution_options(sqlite_begin_immediate=True) as conn,
        conn.begin(),
    ):
        card = ensure_card(conn, card_id="card_fragile_1", word_form_id=fragile.id)
        card_id = card.card_id
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        record_review(
            conn,
            card_id=card_id,
            event_id="rev_fragile_1",
            operation_id=op_rev_1,
            source="FLASHCARD",
            rating="GOOD",
            reviewed_at=now,
        )
        card_before = get_card(conn, card_id)
        assert card_before is not None
        assert card_before.box == 1

    # Delete file F completely
    file_f.unlink()

    # Sync detects missing file F
    result = sync_service.sync(reason="MANUAL")
    assert result.status == "COMPLETED"

    # Card is suspended (not eligible because no source is VALID)
    forms_after = repo.get_forms_for_date("2026-09-28", only_valid_sources=True)
    assert not any(wf.lemma == "fragile" for wf in forms_after)

    # History is retained!
    with test_db.engine.connect() as conn:
        card_retained = get_card(conn, card_id)
        assert card_retained is not None
        assert card_retained.box == 1
        event_count: int = conn.exec_driver_sql(
            "SELECT count(*) FROM review_events WHERE card_id=?", (card_id,)
        ).scalar_one()
        assert event_count == 1

    # Re-add file F with fragile
    file_f.write_text(SAMPLE_NOTE_F, encoding="utf-8")
    sync_service.sync(reason="MANUAL")

    # Re-add reuses card and keeps box 1!
    with test_db.engine.connect() as conn:
        card_reused = get_card(conn, card_id)
        assert card_reused is not None
        assert card_reused.box == 1


def test_ac31_external_meaning_edit_resets_card_echo_does_not_double_reset(
    test_db: Database, markdown_root: Path
) -> None:
    """AC-31: External meaning/example edit resets card state once;
    app-write followed by watcher echo doesn't double reset or double advance revision.
    """
    file_g = markdown_root / "29-09-2026.md"
    file_g.write_text(SAMPLE_NOTE_G, encoding="utf-8")

    ledger = OperationLedger(test_db.engine)
    sync_service = SyncService(test_db.engine, markdown_root, operation_ledger=ledger)
    sync_service.sync(reason="MANUAL")

    repo = VocabularyRepository(test_db.engine)
    robust = next(wf for wf in repo.get_forms_for_date("2026-09-29") if wf.lemma == "robust")

    # Learn the card
    op_rev_robust = ledger.claim(
        kind="REVIEW",
        key=f"rev-key-{token_urlsafe(8)}",
        method="POST",
        path="/synthetic/review",
        body={"rating": "GOOD"},
        preconditions={},
    ).operation.operation_id
    with (
        test_db.engine.connect().execution_options(sqlite_begin_immediate=True) as conn,
        conn.begin(),
    ):
        card = ensure_card(conn, card_id="card_robust_1", word_form_id=robust.id)
        card_id = card.card_id
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        record_review(
            conn,
            card_id=card_id,
            event_id="rev_robust_1",
            operation_id=op_rev_robust,
            source="FLASHCARD",
            rating="GOOD",
            reviewed_at=now,
        )
        c = get_card(conn, card_id)
        assert c is not None
        assert c.box == 1
        q_rev_before = c.queue_revision

    # External edit: change meaning
    edited_note = SAMPLE_NOTE_G.replace("bền vững, vững chắc", "cực kỳ kiên cố, bền vững")
    file_g.write_text(edited_note, encoding="utf-8")

    # Sync picks up the external edit
    sync_service.sync(reason="WATCHER")

    # Card was reset once
    with test_db.engine.connect() as conn:
        c_after = get_card(conn, card_id)
        assert c_after is not None
        assert c_after.box == 0
        assert c_after.due_at is None
        assert c_after.queue_revision == q_rev_before + 1
        q_rev_after = c_after.queue_revision

    # Check source revision
    with test_db.engine.connect() as conn:
        source_id = str(
            conn.exec_driver_sql(
                "SELECT id FROM source_files WHERE relative_path = '29-09-2026.md'"
            ).scalar_one()
        )
    source_before_echo = repo.get_source_file(source_id)
    assert source_before_echo is not None
    source_rev_before = source_before_echo.revision

    # Watcher echo with same bytes must be a no-op: no second reset, no revision advance!
    sync_service.sync(reason="WATCHER")

    with test_db.engine.connect() as conn:
        c_echo = get_card(conn, card_id)
        assert c_echo is not None
        assert c_echo.box == 0
        assert c_echo.queue_revision == q_rev_after  # NO second queue revision increment!

    source_after_echo = repo.get_source_file(source_before_echo.id)
    assert source_after_echo is not None
    assert source_after_echo.revision == source_rev_before  # NO revision advance on echo!


def test_non_learning_edit_does_not_reset_card(test_db: Database, markdown_root: Path) -> None:
    """Editing only IPA or Cambridge link does NOT reset card."""
    file_g = markdown_root / "29-09-2026.md"
    file_g.write_text(SAMPLE_NOTE_G, encoding="utf-8")

    ledger = OperationLedger(test_db.engine)
    sync_service = SyncService(test_db.engine, markdown_root, operation_ledger=ledger)
    sync_service.sync(reason="MANUAL")

    repo = VocabularyRepository(test_db.engine)
    robust = next(wf for wf in repo.get_forms_for_date("2026-09-29") if wf.lemma == "robust")

    # Move card to box 2
    op_rob_1 = ledger.claim(
        kind="REVIEW",
        key=f"rev-key-{token_urlsafe(8)}",
        method="POST",
        path="/synthetic/review",
        body={"rating": "GOOD"},
        preconditions={},
    ).operation.operation_id
    op_rob_2 = ledger.claim(
        kind="REVIEW",
        key=f"rev-key-{token_urlsafe(8)}",
        method="POST",
        path="/synthetic/review",
        body={"rating": "GOOD"},
        preconditions={},
    ).operation.operation_id
    with (
        test_db.engine.connect().execution_options(sqlite_begin_immediate=True) as conn,
        conn.begin(),
    ):
        card = ensure_card(conn, card_id="card_robust_2", word_form_id=robust.id)
        card_id = card.card_id
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        record_review(
            conn,
            card_id=card_id,
            event_id="rev_rob_1",
            operation_id=op_rob_1,
            source="FLASHCARD",
            rating="GOOD",
            reviewed_at=now,
        )
        record_review(
            conn,
            card_id=card_id,
            event_id="rev_rob_2",
            operation_id=op_rob_2,
            source="FLASHCARD",
            rating="GOOD",
            reviewed_at=now,
        )
        c = get_card(conn, card_id)
        assert c is not None
        assert c.box == 2
        q_rev = c.queue_revision

    # Edit only link and IPA (non-learning fields)
    edited_note = SAMPLE_NOTE_G.replace(
        "[Cambridge](https://cambridge.org/robust)",
        "[Cambridge](https://cambridge.org/robust?q=test)",
    ).replace("/roʊ.bʌst/", "/roʊ.bʌst.new/")
    file_g.write_text(edited_note, encoding="utf-8")

    sync_service.sync(reason="WATCHER")

    with test_db.engine.connect() as conn:
        wf_row = (
            conn.exec_driver_sql(
                "SELECT ipa_us, cambridge_url FROM word_forms WHERE id=?", (robust.id,)
            )
            .mappings()
            .first()
        )
        assert wf_row is not None
        assert wf_row["cambridge_url"] == "https://cambridge.org/robust?q=test"
        assert wf_row["ipa_us"] == "/roʊ.bʌst.new/"

        c_after = get_card(conn, card_id)
        assert c_after is not None
        assert c_after.box == 2  # NOT RESET!
        assert c_after.queue_revision == q_rev


def test_external_example_edit_resets_card(test_db: Database, markdown_root: Path) -> None:
    """Editing examples in Markdown resets card state and increments queue_revision."""
    file_g = markdown_root / "29-09-2026.md"
    file_g.write_text(SAMPLE_NOTE_G, encoding="utf-8")

    ledger = OperationLedger(test_db.engine)
    sync_service = SyncService(test_db.engine, markdown_root, operation_ledger=ledger)
    sync_service.sync(reason="MANUAL")

    repo = VocabularyRepository(test_db.engine)
    robust = next(wf for wf in repo.get_forms_for_date("2026-09-29") if wf.lemma == "robust")

    # Review to box 1
    op_rev = ledger.claim(
        kind="REVIEW",
        key=f"rev-key-{token_urlsafe(8)}",
        method="POST",
        path="/synthetic/review",
        body={"rating": "GOOD"},
        preconditions={},
    ).operation.operation_id
    with (
        test_db.engine.connect().execution_options(sqlite_begin_immediate=True) as conn,
        conn.begin(),
    ):
        card = ensure_card(conn, card_id="card_robust_ex", word_form_id=robust.id)
        card_id = card.card_id
        from datetime import UTC, datetime

        record_review(
            conn,
            card_id=card_id,
            event_id="rev_rob_ex_1",
            operation_id=op_rev,
            source="FLASHCARD",
            rating="GOOD",
            reviewed_at=datetime.now(UTC),
        )
        c = get_card(conn, card_id)
        assert c is not None
        assert c.box == 1
        q_rev_before = c.queue_revision

    # Edit examples in markdown
    edited_note = SAMPLE_NOTE_G.replace(
        "The system is robust.", "The system is remarkably robust."
    ).replace("Hệ thống rất bền.", "Hệ thống cực kỳ bền vững.")
    file_g.write_text(edited_note, encoding="utf-8")

    sync_service.sync(reason="WATCHER")

    with test_db.engine.connect() as conn:
        c_after = get_card(conn, card_id)
        assert c_after is not None
        assert c_after.box == 0  # RESET!
        assert c_after.queue_revision == q_rev_before + 1


def test_two_valid_sources_with_conflicting_content_no_arbitrary_winner(
    test_db: Database, markdown_root: Path
) -> None:
    """Two valid sources defining conflicting meanings for the same canonical form
    must not pick an arbitrary winner.
    """
    file_1 = markdown_root / "28-09-2026.md"
    file_2 = markdown_root / "29-09-2026.md"

    # Conflicting meaning for 'robust'
    conflicting_note = SAMPLE_NOTE_G.replace("bền vững, vững chắc", "hoàn toàn khác biệt")

    file_1.write_text(SAMPLE_NOTE_F, encoding="utf-8")
    file_2.write_text(conflicting_note, encoding="utf-8")

    ledger = OperationLedger(test_db.engine)
    sync_service = SyncService(test_db.engine, markdown_root, operation_ledger=ledger)
    result = sync_service.sync(reason="MANUAL")

    assert result.sources_invalid == 2
    with test_db.engine.connect() as conn:
        for name in ["28-09-2026.md", "29-09-2026.md"]:
            row = (
                conn.exec_driver_sql(
                    "SELECT status, error_code FROM source_files WHERE relative_path=?", (name,)
                )
                .mappings()
                .first()
            )
            assert row is not None
            assert row["status"] == "INVALID"
            assert row["error_code"] == "AMBIGUOUS_CONTENT"

        # Neither source became a canonical winner for robust
        robust_form = conn.exec_driver_sql(
            "SELECT id FROM word_forms WHERE normalized_lemma='robust'"
        ).first()
        assert robust_form is None


def test_three_source_aba_conflict_detection_all_permutations(
    test_db: Database, markdown_root: Path
) -> None:
    def make_robust_note(date_str: str, suffix: str) -> str:
        return f"""# {date_str}

## Tra cứu nhanh

| Từ/cụm từ | IPA (US) | Nghĩa ngắn | Ví dụ ngắn | Dịch ví dụ |
|---|---|---|---|---|
| [robust](#robust) | /roʊ.bʌst/ | Bền vững {suffix} | The system is robust. | Hệ thống rất bền. |

## Robust

| Từ/cụm từ | Từ loại | IPA (US) | Trọng âm | Nguồn |
|---|---|---|---|---|
| robust | adjective | /roʊ.bʌst/ | Âm tiết 2 | [Cambridge](https://cambridge.org/robust) |

### Ý nghĩa

- **Nghĩa thông dụng**: bền vững {suffix}

### Trong ngữ cảnh

The system is robust.

### Ví dụ

The system is robust.

*Bản dịch:* Hệ thống rất bền vững.
"""

    note_unrelated = """# 30-09-2026

## Tra cứu nhanh

| Từ/cụm từ | IPA (US) | Nghĩa ngắn | Ví dụ ngắn | Dịch ví dụ |
|---|---|---|---|---|
| [flexible](#flexible) | /flek.sə.bəl/ | Linh hoạt | A flexible schedule. | Lịch linh hoạt. |

## Flexible

| Từ/cụm từ | Từ loại | IPA (US) | Trọng âm | Nguồn |
|---|---|---|---|---|
| flexible | adjective | /flek.sə.bəl/ | Âm tiết 1 | [Cambridge](https://cambridge.org/flexible) |

### Ý nghĩa

- **Nghĩa thông dụng**: linh hoạt, mềm dẻo

### Trong ngữ cảnh

A flexible schedule.

### Ví dụ

A flexible schedule.

*Bản dịch:* Một lịch trình linh hoạt.
"""

    # Test permutation A, B, A with empty initial DB
    (markdown_root / "27-09-2026.md").write_text(
        make_robust_note("27-09-2026", "A"), encoding="utf-8"
    )
    (markdown_root / "28-09-2026.md").write_text(
        make_robust_note("28-09-2026", "B"), encoding="utf-8"
    )
    (markdown_root / "29-09-2026.md").write_text(
        make_robust_note("29-09-2026", "A"), encoding="utf-8"
    )
    (markdown_root / "30-09-2026.md").write_text(note_unrelated, encoding="utf-8")

    ledger = OperationLedger(test_db.engine)
    sync_service = SyncService(test_db.engine, markdown_root, operation_ledger=ledger)
    result = sync_service.sync(reason="MANUAL")

    assert result.status == "COMPLETED"
    assert result.sources_invalid == 3

    with test_db.engine.connect() as conn:
        for name in ["27-09-2026.md", "28-09-2026.md", "29-09-2026.md"]:
            row = (
                conn.exec_driver_sql(
                    "SELECT status, error_code FROM source_files WHERE relative_path=?", (name,)
                )
                .mappings()
                .first()
            )
            assert row is not None, f"Source {name} missing"
            assert row["status"] == "INVALID", (
                f"Source {name} should be INVALID, got {row['status']}"
            )
            assert row["error_code"] == "AMBIGUOUS_CONTENT"

        row_unrelated = (
            conn.exec_driver_sql(
                "SELECT status, error_code FROM source_files WHERE relative_path='30-09-2026.md'"
            )
            .mappings()
            .first()
        )
        assert row_unrelated is not None
        assert row_unrelated["status"] == "VALID"

        robust_form = conn.exec_driver_sql(
            "SELECT id FROM word_forms WHERE normalized_lemma='robust'"
        ).first()
        assert robust_form is None, (
            "Conflicting sources must not create an arbitrary canonical winner!"
        )

        flex_form = conn.exec_driver_sql(
            "SELECT id FROM word_forms WHERE normalized_lemma='flexible'"
        ).first()
        assert flex_form is not None

    # Test permutation B, A, A with a clean database
    db_path_2 = markdown_root.parent / "test_perm.db"
    db_2 = Database(db_path_2)
    db_2.initialize()
    root_perm = markdown_root.parent / "root_perm"
    root_perm.mkdir()
    (root_perm / "27-09-2026.md").write_text(make_robust_note("27-09-2026", "B"), encoding="utf-8")
    (root_perm / "28-09-2026.md").write_text(make_robust_note("28-09-2026", "A"), encoding="utf-8")
    (root_perm / "29-09-2026.md").write_text(make_robust_note("29-09-2026", "A"), encoding="utf-8")
    (root_perm / "30-09-2026.md").write_text(note_unrelated, encoding="utf-8")

    ledger_2 = OperationLedger(db_2.engine)
    sync_service_2 = SyncService(db_2.engine, root_perm, operation_ledger=ledger_2)
    res_perm = sync_service_2.sync(reason="MANUAL")
    assert res_perm.status == "COMPLETED"
    assert res_perm.sources_invalid == 3
    with db_2.engine.connect() as conn:
        for name in ["27-09-2026.md", "28-09-2026.md", "29-09-2026.md"]:
            row = (
                conn.exec_driver_sql(
                    "SELECT status, error_code FROM source_files WHERE relative_path=?", (name,)
                )
                .mappings()
                .first()
            )
            assert row is not None
            assert row["status"] == "INVALID"
            assert row["error_code"] == "AMBIGUOUS_CONTENT"
        assert (
            conn.exec_driver_sql(
                "SELECT id FROM word_forms WHERE normalized_lemma='robust'"
            ).first()
            is None
        )
        assert (
            conn.exec_driver_sql(
                "SELECT id FROM word_forms WHERE normalized_lemma='flexible'"
            ).first()
            is not None
        )

    # Test permutation A, A, B with a clean database
    db_path_3 = markdown_root.parent / "test_perm3.db"
    db_3 = Database(db_path_3)
    db_3.initialize()
    root_perm3 = markdown_root.parent / "root_perm3"
    root_perm3.mkdir()
    (root_perm3 / "27-09-2026.md").write_text(make_robust_note("27-09-2026", "A"), encoding="utf-8")
    (root_perm3 / "28-09-2026.md").write_text(make_robust_note("28-09-2026", "A"), encoding="utf-8")
    (root_perm3 / "29-09-2026.md").write_text(make_robust_note("29-09-2026", "B"), encoding="utf-8")
    (root_perm3 / "30-09-2026.md").write_text(note_unrelated, encoding="utf-8")

    ledger_3 = OperationLedger(db_3.engine)
    sync_service_3 = SyncService(db_3.engine, root_perm3, operation_ledger=ledger_3)
    res_perm3 = sync_service_3.sync(reason="MANUAL")
    assert res_perm3.status == "COMPLETED"
    assert res_perm3.sources_invalid == 3
    with db_3.engine.connect() as conn:
        for name in ["27-09-2026.md", "28-09-2026.md", "29-09-2026.md"]:
            row = (
                conn.exec_driver_sql(
                    "SELECT status, error_code FROM source_files WHERE relative_path=?", (name,)
                )
                .mappings()
                .first()
            )
            assert row is not None
            assert row["status"] == "INVALID"
            assert row["error_code"] == "AMBIGUOUS_CONTENT"
        assert (
            conn.exec_driver_sql(
                "SELECT id FROM word_forms WHERE normalized_lemma='robust'"
            ).first()
            is None
        )
        assert (
            conn.exec_driver_sql(
                "SELECT id FROM word_forms WHERE normalized_lemma='flexible'"
            ).first()
            is not None
        )

    # Test already-projected / history-bearing state
    db_path_hist = markdown_root.parent / "test_hist.db"
    db_hist = Database(db_path_hist)
    db_hist.initialize()
    root_hist = markdown_root.parent / "root_hist"
    root_hist.mkdir()
    (root_hist / "27-09-2026.md").write_text(make_robust_note("27-09-2026", "A"), encoding="utf-8")
    (root_hist / "30-09-2026.md").write_text(note_unrelated, encoding="utf-8")

    ledger_hist = OperationLedger(db_hist.engine)
    sync_hist = SyncService(db_hist.engine, root_hist, operation_ledger=ledger_hist)
    res_init = sync_hist.sync(reason="MANUAL")
    assert res_init.status == "COMPLETED"
    assert res_init.sources_invalid == 0

    from datetime import UTC, datetime

    from backend.app.review.models import get_card, record_review

    claim_op = ledger_hist.claim(
        kind="REVIEW_EVENT",
        key="idemp_hist_1",
        method="POST",
        path="/synthetic/review",
        body={"rating": "GOOD"},
        preconditions={},
    ).operation.operation_id

    with (
        db_hist.engine.connect().execution_options(sqlite_begin_immediate=True) as conn,
        conn.begin(),
    ):
        wf = (
            conn.exec_driver_sql(
                "SELECT id, revision FROM word_forms WHERE normalized_lemma='robust'"
            )
            .mappings()
            .first()
        )
        assert wf is not None
        initial_wf_id = wf["id"]
        initial_wf_rev = wf["revision"]
        # Add card review history
        card = (
            conn.exec_driver_sql(
                "SELECT card_id, box, queue_revision FROM review_cards WHERE word_form_id=?",
                (initial_wf_id,),
            )
            .mappings()
            .first()
        )
        assert card is not None
        initial_card_id = card["card_id"]
        record_review(
            conn,
            card_id=initial_card_id,
            event_id="rev_ev_1",
            operation_id=claim_op,
            source="FLASHCARD",
            rating="GOOD",
            reviewed_at=datetime.now(UTC),
        )
        card_before = get_card(conn, initial_card_id)
        assert card_before is not None
        assert card_before.box == 1

    # Now add conflicting sources 28-09-2026 (B) and 29-09-2026 (A2)
    (root_hist / "28-09-2026.md").write_text(make_robust_note("28-09-2026", "B"), encoding="utf-8")
    (root_hist / "29-09-2026.md").write_text(make_robust_note("29-09-2026", "A"), encoding="utf-8")

    res_conflict = sync_hist.sync(reason="MANUAL")
    assert res_conflict.status == "COMPLETED"
    assert res_conflict.sources_invalid == 3

    with db_hist.engine.connect() as conn:
        for name in ["27-09-2026.md", "28-09-2026.md", "29-09-2026.md"]:
            row = (
                conn.exec_driver_sql(
                    "SELECT status, error_code FROM source_files WHERE relative_path=?", (name,)
                )
                .mappings()
                .first()
            )
            assert row is not None
            assert row["status"] == "INVALID"
            assert row["error_code"] == "AMBIGUOUS_CONTENT"

        # Assert no arbitrary overwrite or reset occurred; existing history remains
        wf_post = (
            conn.exec_driver_sql("SELECT id, revision FROM word_forms WHERE id=?", (initial_wf_id,))
            .mappings()
            .first()
        )
        assert wf_post is not None
        assert wf_post["revision"] == initial_wf_rev

        card_post = (
            conn.exec_driver_sql(
                "SELECT card_id, box FROM review_cards WHERE card_id=?", (initial_card_id,)
            )
            .mappings()
            .first()
        )
        assert card_post is not None
        assert card_post["box"] == 1  # history preserved, not reset!


# HTTP Client Fixtures and Tests


@pytest.fixture
async def authed_client(
    db_path: Path, test_db: Database, markdown_root: Path
) -> AsyncIterator[tuple[AsyncClient, FastAPI, str]]:
    _ = test_db
    app = create_app(
        AppSettings(storage_path=db_path),
        markdown_root=markdown_root,
    )
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://127.0.0.1:8000") as client,
    ):
        # Generate bootstrap token
        token = app.state.sessions.issue_bootstrap_token()
        exchange_resp = await client.post(
            "/bootstrap/exchange",
            json={"token": token},
            headers={"Origin": "http://127.0.0.1:8000"},
        )
        assert exchange_resp.status_code == 204
        session_cookie = exchange_resp.cookies.get("launch_session")
        assert session_cookie is not None
        client.cookies.set("launch_session", session_cookie)
        yield client, app, session_cookie


async def test_get_sources_pagination_filters_and_cursor(
    authed_client: tuple[AsyncClient, FastAPI, str], markdown_root: Path
) -> None:
    client, _app, _ = authed_client

    # Write multiple files
    for day in range(1, 15):
        fn_str = f"{day:02d}-09-2026"
        (markdown_root / f"{fn_str}.md").write_text(
            f"# {fn_str}\n\n"
            f"## Tra cứu nhanh\n\n"
            f"| Từ/cụm từ | IPA (US) | Nghĩa ngắn | Ví dụ ngắn | Dịch ví dụ |\n"
            f"|---|---|---|---|---|\n"
            f"| [t{day}](#t{day}) | /test/ | test {day} | T{day}. | Thử {day}. |\n\n"
            f"## T{day}\n\n"
            f"| Từ/cụm từ | Từ loại | IPA (US) | Trọng âm | Nguồn |\n"
            f"|---|---|---|---|---|\n"
            f"| t{day} | noun | /test/ | 1 | [Cambridge](https://dictionary.cambridge.org) |\n\n"
            f"### Ý nghĩa\n\n"
            f"- **Nghĩa thông dụng**: thử {day}\n\n"
            f"### Ví dụ\n\n"
            f"T{day}.\n\n"
            f"*Bản dịch:* Thử {day}.\n",
            encoding="utf-8",
        )

    # Initial manual sync
    sync_resp = await client.post(
        "/api/v1/sync-runs",
        json={"reason": "MANUAL"},
        headers={
            "Idempotency-Key": f"sync-key-{token_urlsafe(8)}",
            "Origin": "http://127.0.0.1:8000",
        },
    )
    assert sync_resp.status_code == 202

    # GET /sources with default pagination
    resp = await client.get("/api/v1/sources?pageSize=5")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["data"]) == 5
    assert data["pagination"]["hasMore"] is True
    cursor = data["pagination"]["nextCursor"]
    assert cursor is not None

    # Fetch second page with cursor
    resp2 = await client.get(f"/api/v1/sources?pageSize=5&cursor={cursor}")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert len(data2["data"]) == 5

    # Filter by noteDate
    resp_date = await client.get("/api/v1/sources?noteDate=2026-09-01")
    assert resp_date.status_code == 200
    data_date = resp_date.json()
    assert len(data_date["data"]) == 1
    assert data_date["data"][0]["noteDate"] == "2026-09-01"

    # Filter by status
    resp_status = await client.get("/api/v1/sources?status=VALID")
    assert resp_status.status_code == 200

    # Tampered cursor returns 409 CURSOR_EXPIRED
    resp_tamper = await client.get("/api/v1/sources?pageSize=5&cursor=tampered_invalid_cursor")
    assert resp_tamper.status_code == 409
    assert resp_tamper.json()["error"]["code"] == "CURSOR_EXPIRED"

    # Invalid query parameter returns 400 INVALID_QUERY
    resp_invalid_query = await client.get("/api/v1/sources?unknownParam=123")
    assert resp_invalid_query.status_code == 400
    assert resp_invalid_query.json()["error"]["code"] == "INVALID_QUERY"


async def test_sync_runs_idempotency_and_replays(
    authed_client: tuple[AsyncClient, FastAPI, str], markdown_root: Path
) -> None:
    client, _, _ = authed_client
    (markdown_root / "29-09-2026.md").write_text(SAMPLE_NOTE_G, encoding="utf-8")

    key = f"key-sync-{token_urlsafe(12)}"

    # First request
    resp1 = await client.post(
        "/api/v1/sync-runs",
        json={"reason": "MANUAL"},
        headers={"Idempotency-Key": key, "Origin": "http://127.0.0.1:8000"},
    )
    assert resp1.status_code == 202
    data1 = resp1.json()
    assert data1["status"] == "COMPLETED"
    assert data1["reason"] == "MANUAL"
    sync_id = data1["id"]

    # Replay with same key and same body returns identical receipt
    resp2 = await client.post(
        "/api/v1/sync-runs",
        json={"reason": "MANUAL"},
        headers={"Idempotency-Key": key, "Origin": "http://127.0.0.1:8000"},
    )
    assert resp2.status_code == 202
    data2 = resp2.json()
    assert data2["id"] == sync_id
    assert data2["operationId"] == data1["operationId"]

    # Same key with different body fails 422 IDEMPOTENCY_KEY_REUSED
    resp_reused = await client.post(
        "/api/v1/sync-runs",
        json={"reason": "STARTUP"},
        headers={"Idempotency-Key": key, "Origin": "http://127.0.0.1:8000"},
    )
    assert resp_reused.status_code == 422
    assert resp_reused.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"

    # GET /sync-runs/{syncRunId}
    get_resp = await client.get(f"/api/v1/sync-runs/{sync_id}")
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert get_data["id"] == sync_id
    assert get_data["status"] == "COMPLETED"

    # GET non-existent sync run returns 404
    get_missing = await client.get("/api/v1/sync-runs/sync_nonexistent_999")
    assert get_missing.status_code == 404
    assert get_missing.json()["error"]["code"] == "NOT_FOUND"


async def test_unauthenticated_request_rejected(
    authed_client: tuple[AsyncClient, FastAPI, str],
) -> None:
    _, app, _ = authed_client
    # Unauthenticated client (no session cookie)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://127.0.0.1:8000"
    ) as client:
        resp = await client.get("/api/v1/sources")
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "SESSION_REQUIRED"


def test_watcher_debounce_and_storm_coalescing(markdown_root: Path) -> None:
    """Watcher debounces rapid multiple file writes into coalesced batch."""
    events: list[list[str]] = []
    watcher = SourceWatcher(
        markdown_root,
        on_change=lambda batch: events.append(batch),
        debounce_seconds=0.1,
        poll_interval=0.02,
    )
    watcher.start()
    try:
        # Rapid storm of 5 writes
        for i in range(5):
            (markdown_root / f"file_{i}.md").write_text(f"# File {i}", encoding="utf-8")

        time.sleep(0.3)
        # Should have coalesced into 1 or at most 2 batches
        assert 1 <= len(events) <= 2
        all_changed = {p for batch in events for p in batch}
        assert all_changed == {f"file_{i}.md" for i in range(5)}
    finally:
        watcher.stop()


async def test_startup_recovery_registers_sources_and_persistent_degradation(
    db_path: Path, markdown_root: Path
) -> None:
    db = Database(db_path)
    db.initialize()
    source_id = "src_recov_test"
    file_path = markdown_root / "29-09-2026.md"
    file_path.write_text(SAMPLE_NOTE_G, encoding="utf-8")
    import hashlib

    content_hash = hashlib.sha256(SAMPLE_NOTE_G.encode("utf-8")).hexdigest()

    with (
        db.engine.connect().execution_options(sqlite_begin_immediate=True) as conn,
        conn.begin(),
    ):
        conn.exec_driver_sql(
            "INSERT INTO source_files (id, relative_path, note_date, status, revision, etag, "
            "content_hash, last_parsed_at, error_code, created_at, updated_at) "
            "VALUES (?, '29-09-2026.md', '2026-09-29', 'VALID', 1, 'etag1', ?, "
            "'2026-09-29T00:00:00Z', NULL, '2026-09-29T00:00:00Z', '2026-09-29T00:00:00Z')",
            (source_id, content_hash),
        )
        op_id = "op_recov_test"
        conn.exec_driver_sql(
            "INSERT INTO operations (operation_id, kind, status, created_at, updated_at) "
            "VALUES (?, 'SOURCE_WRITE', 'PENDING', '2026-09-29T00:00:00Z', '2026-09-29T00:00:00Z')",
            (op_id,),
        )
        dummy_new_hash = hashlib.sha256(b"dummy_new_content").hexdigest()
        conn.exec_driver_sql(
            "INSERT INTO source_write_journal (operation_id, source_id, old_hash, new_hash, "
            "intended_projection_revision, effect_plan, response_status, result_ref, state, "
            "created_at, updated_at) "
            'VALUES (?, ?, ?, ?, 2, \'{"version":1,"forms":[],"links":[],"removed":[]}\', '
            "200, 'ref1', 'PREPARED', '2026-09-29T00:00:00Z', '2026-09-29T00:00:00Z')",
            (op_id, source_id, content_hash, dummy_new_hash),
        )
    db.close()

    app = create_app(AppSettings(storage_path=db_path), markdown_root=markdown_root)
    async with app.router.lifespan_context(app):
        assert app.state.ready is True
        assert app.state.storage_error is None
        with app.state.database.engine.connect() as conn:
            j_state = conn.exec_driver_sql(
                "SELECT state FROM source_write_journal WHERE operation_id=?", (op_id,)
            ).scalar_one()
            assert j_state == "ABORTED"

    db = Database(db_path)
    db.initialize()
    with (
        db.engine.connect().execution_options(sqlite_begin_immediate=True) as conn,
        conn.begin(),
    ):
        conn.exec_driver_sql(
            "INSERT INTO operations (operation_id, kind, status, created_at, updated_at) "
            "VALUES ('op_deg_1', 'SOURCE_WRITE', 'FAILED', "
            "'2026-09-29T00:00:00Z', '2026-09-29T00:00:00Z')"
        )
        conn.exec_driver_sql(
            "INSERT INTO source_write_journal (operation_id, source_id, old_hash, new_hash, "
            "intended_projection_revision, effect_plan, response_status, result_ref, state, "
            "created_at, updated_at) "
            "VALUES ('op_deg_1', ?, ?, ?, 2, "
            '\'{"version":1,"forms":[],"links":[],"removed":[]}\', '
            "200, 'ref1', 'PREPARED', '2026-09-29T00:00:00Z', '2026-09-29T00:00:00Z')",
            (source_id, content_hash, dummy_new_hash),
        )
        conn.exec_driver_sql(
            "UPDATE source_write_journal SET state='DEGRADED' WHERE operation_id='op_deg_1'"
        )
    db.close()

    app2 = create_app(AppSettings(storage_path=db_path), markdown_root=markdown_root)
    async with app2.router.lifespan_context(app2):
        assert app2.state.ready is False
        assert app2.state.storage_error == "DEGRADED"


async def test_configured_service_boundary_absent_or_degraded(
    db_path: Path, test_db: Database
) -> None:
    _ = test_db
    app = create_app(AppSettings(storage_path=db_path), markdown_root=None)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://127.0.0.1:8000") as client,
    ):
        token = app.state.sessions.issue_bootstrap_token()
        exch = await client.post(
            "/bootstrap/exchange",
            json={"token": token},
            headers={"Origin": "http://127.0.0.1:8000"},
        )
        cookie = exch.cookies.get("launch_session")
        assert cookie is not None
        client.cookies.set("launch_session", cookie)

        resp_get = await client.get("/api/v1/sources")
        assert resp_get.status_code == 503
        assert resp_get.json()["error"]["code"] == "CONFIGURATION_REQUIRED"
        assert getattr(app.state, "sync_service", None) is None

        resp_post = await client.post(
            "/api/v1/sync-runs",
            json={"reason": "MANUAL"},
            headers={"Idempotency-Key": "test-key-cfg", "Origin": "http://127.0.0.1:8000"},
        )
        assert resp_post.status_code == 503
        assert resp_post.json()["error"]["code"] == "CONFIGURATION_REQUIRED"
        assert getattr(app.state, "sync_service", None) is None


def test_t021_adapter_validation_refusals(test_db: Database, markdown_root: Path) -> None:
    file_orig = markdown_root / "29-09-2026.md"
    file_orig.write_text(SAMPLE_NOTE_G, encoding="utf-8")

    file_hl = markdown_root / "28-09-2026.md"
    os.link(file_orig, file_hl)

    ledger = OperationLedger(test_db.engine)
    sync_service = SyncService(test_db.engine, markdown_root, operation_ledger=ledger)
    result = sync_service.sync(reason="MANUAL")

    assert result.status == "COMPLETED"
    assert result.sources_invalid >= 1

    with test_db.engine.connect() as conn:
        hl_row = (
            conn.exec_driver_sql(
                "SELECT status, error_code FROM source_files WHERE relative_path='28-09-2026.md'"
            )
            .mappings()
            .first()
        )
        assert hl_row is not None
        assert hl_row["status"] == "INVALID"
        assert hl_row["error_code"] == "SECURITY_VIOLATION"

    file_hl.unlink()
    file_ro = markdown_root / "28-09-2026.md"
    file_ro.write_text(SAMPLE_NOTE_F, encoding="utf-8")
    file_ro.chmod(stat.S_IREAD)
    try:
        result_ro = sync_service.sync(reason="MANUAL")
        assert result_ro.status == "COMPLETED"
        with test_db.engine.connect() as conn:
            ro_row = (
                conn.exec_driver_sql(
                    "SELECT status, error_code FROM source_files "
                    "WHERE relative_path='28-09-2026.md'"
                )
                .mappings()
                .first()
            )
            assert ro_row is not None
            assert ro_row["status"] == "INVALID"
            assert ro_row["error_code"] == "ACCESS_DENIED"
    finally:
        file_ro.chmod(stat.S_IREAD | stat.S_IWRITE)


def test_t021_adapter_hardlink_refusal_deterministic(
    test_db: Database, markdown_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    file_orig = markdown_root / "29-09-2026.md"
    file_orig.write_text(SAMPLE_NOTE_G, encoding="utf-8")

    orig_stat = os.stat

    def fake_stat(path: Any, *args: Any, **kwargs: Any) -> os.stat_result:
        res = orig_stat(path, *args, **kwargs)
        if Path(path).name == "29-09-2026.md":
            return os.stat_result(
                (
                    res.st_mode,
                    res.st_ino,
                    res.st_dev,
                    2,  # st_nlink > 1 triggers hardlink rejection
                    res.st_uid,
                    res.st_gid,
                    res.st_size,
                    res.st_atime,
                    res.st_mtime,
                    res.st_ctime,
                )
            )
        return res

    monkeypatch.setattr(os, "stat", fake_stat)

    ledger = OperationLedger(test_db.engine)
    sync_service = SyncService(test_db.engine, markdown_root, operation_ledger=ledger)
    result = sync_service.sync(reason="MANUAL")

    assert result.status == "COMPLETED"
    assert result.sources_invalid >= 1

    with test_db.engine.connect() as conn:
        row = (
            conn.exec_driver_sql(
                "SELECT status, error_code FROM source_files WHERE relative_path='29-09-2026.md'"
            )
            .mappings()
            .first()
        )
        assert row is not None
        assert row["status"] == "INVALID"
        assert row["error_code"] == "SECURITY_VIOLATION"


def test_fence_t022_writes_coordinator_interleaving(test_db: Database, markdown_root: Path) -> None:
    file_g = markdown_root / "29-09-2026.md"
    file_g.write_text(SAMPLE_NOTE_G, encoding="utf-8")

    ledger = OperationLedger(test_db.engine)
    sync_service = SyncService(test_db.engine, markdown_root, operation_ledger=ledger)
    sync_service.sync(reason="MANUAL")

    repo = VocabularyRepository(test_db.engine)
    robust = next(wf for wf in repo.get_forms_for_date("2026-09-29") if wf.lemma == "robust")

    op_rev = ledger.claim(
        kind="REVIEW",
        key=f"rev-key-{token_urlsafe(8)}",
        method="POST",
        path="/synthetic/review",
        body={"rating": "GOOD"},
        preconditions={},
    ).operation.operation_id
    with (
        test_db.engine.connect().execution_options(sqlite_begin_immediate=True) as conn,
        conn.begin(),
    ):
        card = ensure_card(conn, card_id="card_robust_fence", word_form_id=robust.id)
        card_id = card.card_id
        from datetime import UTC, datetime

        record_review(
            conn,
            card_id=card_id,
            event_id="rev_rob_fence_1",
            operation_id=op_rev,
            source="FLASHCARD",
            rating="GOOD",
            reviewed_at=datetime.now(UTC),
        )
        c = get_card(conn, card_id)
        assert c is not None
        assert c.box == 1

    with test_db.engine.connect() as conn:
        src_row = (
            conn.exec_driver_sql(
                "SELECT id, content_hash FROM source_files WHERE relative_path='29-09-2026.md'"
            )
            .mappings()
            .first()
        )
        assert src_row is not None
        src_id = str(src_row["id"])
        old_hash = str(src_row["content_hash"])

    adapter = SourceFileAdapter(markdown_root)
    src_obj = repo.get_source_file(src_id)
    assert src_obj is not None
    adapter.register_source(src_obj)
    coordinator = SourceWriteCoordinator(test_db.engine, adapter)

    new_content = SAMPLE_NOTE_G.replace("bền vững, vững chắc", "cực kỳ bền vững và kiên cố")
    op_write = ledger.claim(
        kind="SOURCE_WRITE",
        key=f"write-key-{token_urlsafe(8)}",
        method="PUT",
        path="/api/v1/sources",
        body={"source_id": src_id},
        preconditions={},
    ).operation.operation_id

    sync_executed_during_pause = threading.Event()

    def fault_injector(point: str) -> None:
        if point == "AFTER_SOURCE_REPLACED":
            sync_service.sync(reason="WATCHER")
            sync_executed_during_pause.set()

    coordinator.write(
        operation_id=op_write,
        source_id=src_id,
        expected_old_hash=old_hash,
        new_content=new_content,
        intended_projection_revision=2,
        operation_ledger=ledger,
        fault=fault_injector,
    )

    assert sync_executed_during_pause.is_set()

    with test_db.engine.connect() as conn:
        j_rec = coordinator.get(op_write)
        assert j_rec is not None
        assert j_rec.state == "COMMITTED"

        src_after: int = conn.exec_driver_sql(
            "SELECT revision FROM source_files WHERE id=?", (src_id,)
        ).scalar_one()
        assert src_after == 2

        c_after = get_card(conn, card_id)
        assert c_after is not None
        assert c_after.box == 0
        q_rev_after = c_after.queue_revision

    sync_service.sync(reason="WATCHER")

    with test_db.engine.connect() as conn:
        src_echo: int = conn.exec_driver_sql(
            "SELECT revision FROM source_files WHERE id=?", (src_id,)
        ).scalar_one()
        assert src_echo == 2

        c_echo = get_card(conn, card_id)
        assert c_echo is not None
        assert c_echo.box == 0
        assert c_echo.queue_revision == q_rev_after


def test_truthful_receipts_and_watcher_failures(test_db: Database, markdown_root: Path) -> None:
    file_g = markdown_root / "29-09-2026.md"
    file_g.write_text(SAMPLE_NOTE_G, encoding="utf-8")

    class FailingLedger(OperationLedger):
        def complete(
            self,
            operation_id: str,
            *,
            response_status: int,
            result_ref: str,
            local_write: Any = None,
        ) -> Any:
            _ = (operation_id, response_status, result_ref, local_write)
            raise RuntimeError("Injected ledger complete failure")

    ledger = FailingLedger(test_db.engine)
    sync_service = SyncService(test_db.engine, markdown_root, operation_ledger=ledger)

    with pytest.raises(RuntimeError, match="Injected ledger complete failure"):
        sync_service.sync(reason="MANUAL")

    with test_db.engine.connect() as conn:
        op_row = (
            conn.exec_driver_sql("SELECT status FROM operations WHERE kind='SYNC_RUN'")
            .mappings()
            .first()
        )
        assert op_row is not None
        assert op_row["status"] != "SUCCEEDED"

    with (
        test_db.engine.connect().execution_options(sqlite_begin_immediate=True) as conn,
        conn.begin(),
    ):
        conn.exec_driver_sql(
            "INSERT INTO operations "
            "(operation_id, kind, status, result_ref, created_at, updated_at) "
            "VALUES ('op_unknown_sync', 'SYNC_RUN', 'UNKNOWN', 'sync_unk.MANUAL.1.0.1', "
            "'2026-09-29T00:00:00Z', '2026-09-29T00:00:00Z')"
        )

    run_res = sync_service.get_sync_run("sync_unk")
    assert run_res is not None
    assert run_res.status != "COMPLETED"


def test_cursor_snapshot_stale_detection_and_source_revision(
    test_db: Database, markdown_root: Path
) -> None:
    note_a = (
        SAMPLE_NOTE_G.replace("robust", "apple")
        .replace("Robust", "Apple")
        .replace("bền vững, vững chắc", "quả táo")
    )
    note_b = (
        SAMPLE_NOTE_G.replace("robust", "banana")
        .replace("Robust", "Banana")
        .replace("bền vững, vững chắc", "quả chuối")
    )
    (markdown_root / "28-09-2026.md").write_text(note_a, encoding="utf-8")
    (markdown_root / "29-09-2026.md").write_text(note_b, encoding="utf-8")

    ledger = OperationLedger(test_db.engine)
    sync_service = SyncService(test_db.engine, markdown_root, operation_ledger=ledger)
    sync_res = sync_service.sync(reason="MANUAL")
    assert sync_res.status == "COMPLETED"
    assert isinstance(sync_res.source_revision, int)

    with (
        test_db.engine.connect().execution_options(sqlite_begin_immediate=True) as conn,
        conn.begin(),
    ):
        conn.exec_driver_sql(
            "UPDATE source_files SET revision=10 WHERE relative_path='28-09-2026.md'"
        )

    _sources, cursor, _has_more = sync_service.list_sources(page_size=1)
    assert cursor is not None

    # Update source B from rev 1 -> 2
    edited_b = note_b.replace("quả chuối", "trái chuối vàng")
    (markdown_root / "29-09-2026.md").write_text(edited_b, encoding="utf-8")
    sync_service.sync(reason="WATCHER")

    # MAX revision in DB is STILL 10!
    # But cursor was taken before source B changed, so it MUST raise CursorExpiredError
    with pytest.raises(CursorExpiredError):
        sync_service.list_sources(page_size=1, cursor=cursor)

    empty_root = markdown_root.parent / "empty_vocab"
    empty_root.mkdir()
    empty_service = SyncService(test_db.engine, empty_root, operation_ledger=ledger)
    empty_res = empty_service.sync(reason="MANUAL")
    assert empty_res.status == "COMPLETED"
    assert isinstance(empty_res.source_revision, int)
    assert empty_res.source_revision >= 0


def test_list_sources_single_snapshot_concurrent_mutation_issuance_and_validation(
    test_db: Database, markdown_root: Path
) -> None:
    for i in range(1, 4):
        p = markdown_root / f"2026-09-0{i}.md"
        p.write_text(
            f"""# 2026-09-0{i}

## Tra cứu nhanh

| Từ/cụm từ | IPA (US) | Nghĩa ngắn | Ví dụ ngắn | Dịch ví dụ |
|---|---|---|---|---|
| [word{i}](#word{i}) | /w{i}/ | Nghĩa {i} | Ex {i} | Dịch {i} |

## Word{i}

| Từ/cụm từ | Từ loại | IPA (US) | Trọng âm | Nguồn |
|---|---|---|---|---|
| word{i} | noun | /w{i}/ | Âm tiết 1 | [Cambridge](https://cambridge.org/w{i}) |

### Ý nghĩa

- **Nghĩa thông dụng**: nghĩa {i}

### Trong ngữ cảnh

Context {i}

### Ví dụ

Ex {i}

*Bản dịch:* Dịch {i}
""",
            encoding="utf-8",
        )

    ledger = OperationLedger(test_db.engine)
    sync_service = SyncService(test_db.engine, markdown_root, operation_ledger=ledger)
    sync_service.sync(reason="MANUAL")

    def concurrent_mutation_hook() -> None:
        with (
            test_db.engine.connect().execution_options(sqlite_begin_immediate=True) as conn,
            conn.begin(),
        ):
            conn.exec_driver_sql(
                "UPDATE source_files SET note_date='2026-09-99' WHERE relative_path='2026-09-03.md'"
            )

    page1, cursor1, has_more = sync_service.list_sources(
        page_size=1, _test_after_rows_hook=concurrent_mutation_hook
    )
    assert len(page1) == 1
    assert has_more
    assert cursor1 is not None

    with pytest.raises(CursorExpiredError):
        sync_service.list_sources(page_size=1, cursor=cursor1)


async def test_date_normalization_legacy_filename_and_impossible_date(
    authed_client: tuple[AsyncClient, FastAPI, str],
    test_db: Database,
    markdown_root: Path,
) -> None:
    client, app, _ = authed_client

    bad_file = markdown_root / "29-09-2026.md"
    bad_file.write_text("NOT VALID MARKDOWN\nNO SECTIONS", encoding="utf-8")

    sync_service = app.state.sync_service
    assert sync_service is not None
    sync_service.sync(reason="MANUAL")

    with test_db.engine.connect() as conn:
        row = (
            conn.exec_driver_sql(
                "SELECT note_date, status FROM source_files WHERE relative_path='29-09-2026.md'"
            )
            .mappings()
            .first()
        )
        assert row is not None
        assert row["status"] == "INVALID"
        assert row["note_date"] == "2026-09-29"

    resp_valid_date = await client.get("/api/v1/sources?noteDate=2026-09-29")
    assert resp_valid_date.status_code == 200
    assert len(resp_valid_date.json()["data"]) == 1

    resp_imp = await client.get("/api/v1/sources?noteDate=2026-02-30")
    assert resp_imp.status_code == 422
    assert resp_imp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert resp_imp.json()["error"]["details"]["fields"][0]["field"] == "noteDate"

    resp_leap = await client.get("/api/v1/sources?noteDate=2024-02-29")
    assert resp_leap.status_code == 200


async def test_exact_sync_run_id_no_like_wildcard(
    authed_client: tuple[AsyncClient, FastAPI, str],
    markdown_root: Path,
) -> None:
    client, _app, _ = authed_client
    (markdown_root / "29-09-2026.md").write_text(SAMPLE_NOTE_G, encoding="utf-8")

    resp = await client.post(
        "/api/v1/sync-runs",
        json={"reason": "MANUAL"},
        headers={
            "Idempotency-Key": f"exact-id-key-{token_urlsafe(8)}",
            "Origin": "http://127.0.0.1:8000",
        },
    )
    assert resp.status_code == 202
    run_id = resp.json()["id"]

    resp_exact = await client.get(f"/api/v1/sync-runs/{run_id}")
    assert resp_exact.status_code == 200

    resp_pct = await client.get("/api/v1/sync-runs/%25")
    assert resp_pct.status_code == 404

    resp_underscore = await client.get("/api/v1/sync-runs/_")
    assert resp_underscore.status_code == 404


async def test_typed_retry_409_response_schema(
    authed_client: tuple[AsyncClient, FastAPI, str],
) -> None:
    client, app, _ = authed_client
    key = f"in-flight-key-{token_urlsafe(8)}"

    ledger: OperationLedger = app.state.operation_ledger
    ledger.claim(
        kind="SYNC_RUN",
        key=key,
        method="POST",
        path="/api/v1/sync-runs",
        body={"reason": "MANUAL"},
        preconditions={},
    )

    resp_conflict = await client.post(
        "/api/v1/sync-runs",
        json={"reason": "MANUAL"},
        headers={"Idempotency-Key": key, "Origin": "http://127.0.0.1:8000"},
    )
    assert resp_conflict.status_code == 409
    body = resp_conflict.json()
    assert body["error"]["code"] == "IDEMPOTENCY_IN_FLIGHT"
    assert "details" in body["error"]
    assert body["error"]["details"]["kind"] == "RETRY"
    assert "operationId" in body["error"]["details"]


def test_sync_preserves_field_verification_provenance_and_recomputes_summary(
    test_db: Database,
    markdown_root: Path,
) -> None:
    note = markdown_root / "01-09-2026.md"
    note.write_text(
        """# 01-09-2026

## Tra cứu nhanh

| Từ/cụm từ | IPA (US) | Nghĩa ngắn | Ví dụ ngắn | Dịch ví dụ |
|---|---|---|---|---|
| [paradigm](#paradigm) | /pærədaim/ | mô hình | A new paradigm. | Một mô hình mới. |

## Paradigm

| Từ/cụm từ | Từ loại | IPA (US) | Trọng âm | Nguồn |
|---|---|---|---|---|
| paradigm | noun | /pærədaim/ | Âm tiết 1 | [Cambridge](https://cambridge.org/paradigm) |

### Ý nghĩa

- **Nghĩa thông dụng**: mô hình mẫu

### Trong ngữ cảnh

Trong nghiên cứu khoa học.

### Ví dụ

A new paradigm emerged.

*Bản dịch:* Một mô hình mới xuất hiện.
""",
        encoding="utf-8",
    )

    ledger = OperationLedger(test_db.engine)
    sync_service = SyncService(test_db.engine, markdown_root, operation_ledger=ledger)
    repo = VocabularyRepository(test_db.engine)

    # 1. Initial sync
    res1 = sync_service.sync(reason="MANUAL")
    assert res1.status == "COMPLETED"

    forms1 = repo.get_forms_for_source(
        test_db.engine.connect()
        .exec_driver_sql("SELECT id FROM source_files WHERE relative_path='01-09-2026.md'")
        .scalar_one()
    )
    assert len(forms1) == 1
    form1 = forms1[0]
    # In initial import from markdown, verification status should not be blindly VERIFIED
    assert form1.verification_summary != "VERIFIED"
    assert form1.meanings_vi[0].verification_status == "UNVERIFIED"
    initial_rev = form1.revision
    assert initial_rev > 0

    # 2. Simulate user/AI verification of meaning and IPA
    with (
        test_db.engine.connect().execution_options(sqlite_begin_immediate=True) as conn,
        conn.begin(),
    ):
        verified_vi = [MeaningVi(form1.meanings_vi[0].text, verification_status="VERIFIED")]
        form_verified = repo.save_canonical_word_form(
            lemma=form1.lemma,
            part_of_speech=form1.part_of_speech,
            family_id=form1.family_id,
            meanings_en=form1.meanings_en,
            meanings_vi=verified_vi,
            examples=form1.examples,
            ipa_us=form1.ipa_us,
            ipa_status="VERIFIED",
            cambridge_url=form1.cambridge_url,
            cambridge_status="VERIFIED",
            word_form_id=form1.id,
            connection=conn,
        )
    assert form_verified.meanings_vi[0].verification_status == "VERIFIED"
    rev_after_verify = form_verified.revision

    # 3. Re-sync without changes: provenance preserved, no rev bump
    res2 = sync_service.sync(reason="MANUAL")
    assert res2.status == "COMPLETED"

    form2 = repo.get_word_form(form1.id)
    assert form2 is not None
    assert form2.revision == rev_after_verify
    assert form2.meanings_vi[0].verification_status == "VERIFIED"
    assert form2.ipa_status == "VERIFIED"
    assert form2.cambridge_status == "VERIFIED"

    # 4. Advance review card state
    op_rev = ledger.claim(
        kind="REVIEW",
        key=f"rev-key-{token_urlsafe(8)}",
        method="POST",
        path="/synthetic/review",
        body={"rating": "GOOD"},
        preconditions={},
    ).operation.operation_id

    from datetime import UTC, datetime

    with (
        test_db.engine.connect().execution_options(sqlite_begin_immediate=True) as conn,
        conn.begin(),
    ):
        card_id: str = str(
            conn.exec_driver_sql(
                "SELECT card_id FROM review_cards WHERE word_form_id=?", (form1.id,)
            ).scalar_one()
        )
        record_review(
            conn,
            card_id=str(card_id),
            event_id=f"rev_ev_{token_urlsafe(8)}",
            operation_id=op_rev,
            source="FLASHCARD",
            rating="GOOD",
            reviewed_at=datetime.now(UTC),
        )
        card_advanced = get_card(conn, str(card_id))
        assert card_advanced is not None
        assert card_advanced.box == 1

    # 5. Non-learning edit: change Cambridge URL only
    note.write_text(
        """# 01-09-2026

## Tra cứu nhanh

| Từ/cụm từ | IPA (US) | Nghĩa ngắn | Ví dụ ngắn | Dịch ví dụ |
|---|---|---|---|---|
| [paradigm](#paradigm) | /pærədaim/ | mô hình | A new paradigm. | Một mô hình mới. |

## Paradigm

| Từ/cụm từ | Từ loại | IPA (US) | Trọng âm | Nguồn |
|---|---|---|---|---|
| paradigm | noun | /pærədaim/ | Âm tiết 1 | [Cambridge](https://cambridge.org/paradigm-new) |

### Ý nghĩa

- **Nghĩa thông dụng**: mô hình mẫu

### Trong ngữ cảnh

Trong nghiên cứu khoa học.

### Ví dụ

A new paradigm emerged.

*Bản dịch:* Một mô hình mới xuất hiện.
""",
        encoding="utf-8",
    )
    res3 = sync_service.sync(reason="MANUAL")
    assert res3.status == "COMPLETED"

    with test_db.engine.connect() as conn:
        card_after_non_learning = get_card(conn, str(card_id))
        assert card_after_non_learning is not None
        # Must NOT reset card state
        assert card_after_non_learning.box == 1

    form3 = repo.get_word_form(form1.id)
    assert form3 is not None
    assert form3.cambridge_url == "https://cambridge.org/paradigm-new"
    assert form3.cambridge_status == "UNVERIFIED"  # changed URL resets link status to UNVERIFIED
    assert form3.meanings_vi[0].verification_status == "VERIFIED"  # preserved!

    # 6. Learning edit: change meaning
    note.write_text(
        """# 01-09-2026

## Tra cứu nhanh

| Từ/cụm từ | IPA (US) | Nghĩa ngắn | Ví dụ ngắn | Dịch ví dụ |
|---|---|---|---|---|
| [paradigm](#paradigm) | /pærədaim/ | mô hình mới | A new paradigm. | Một mô hình mới. |

## Paradigm

| Từ/cụm từ | Từ loại | IPA (US) | Trọng âm | Nguồn |
|---|---|---|---|---|
| paradigm | noun | /pærədaim/ | Âm tiết 1 | [Cambridge](https://cambridge.org/paradigm-new) |

### Ý nghĩa

- **Nghĩa thông dụng**: mô hình hoàn toàn mới

### Trong ngữ cảnh

Trong nghiên cứu khoa học.

### Ví dụ

A new paradigm emerged.

*Bản dịch:* Một mô hình mới xuất hiện.
""",
        encoding="utf-8",
    )
    res4 = sync_service.sync(reason="MANUAL")
    assert res4.status == "COMPLETED"

    with test_db.engine.connect() as conn:
        card_after_learning = get_card(conn, str(card_id))
        assert card_after_learning is not None
        # MUST reset card state
        assert card_after_learning.box == 0

    form4 = repo.get_word_form(form1.id)
    assert form4 is not None
    assert form4.meanings_vi[0].text == "- **Nghĩa thông dụng**: mô hình hoàn toàn mới"
    assert form4.meanings_vi[0].verification_status == "UNVERIFIED"


def test_truthful_receipts_failure_injection_and_replay_safety(
    test_db: Database,
    markdown_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ledger = OperationLedger(test_db.engine)
    sync_service = SyncService(test_db.engine, markdown_root, operation_ledger=ledger)

    # 1. Non-terminal sync run representation
    with (
        test_db.engine.connect().execution_options(sqlite_begin_immediate=True) as conn,
        conn.begin(),
    ):
        conn.exec_driver_sql(
            "INSERT INTO operations (operation_id, kind, status, result_ref, "
            "created_at, updated_at) "
            "VALUES ('op_pending_1', 'SYNC_RUN', 'PENDING', "
            "'sync_pending_1.MANUAL.0.0.0', '2026-09-01T00:00:00Z', '2026-09-01T00:00:00Z')"
        )
    pending_run = sync_service.get_sync_run("sync_pending_1")
    assert pending_run is not None
    assert pending_run.status == "RUNNING"
    assert pending_run.finished_at is None

    # Ensure not cached: update status to SUCCEEDED and verify get_sync_run
    with (
        test_db.engine.connect().execution_options(sqlite_begin_immediate=True) as conn,
        conn.begin(),
    ):
        conn.exec_driver_sql(
            "UPDATE operations SET status='SUCCEEDED', updated_at='2026-09-01T00:01:00Z' "
            "WHERE operation_id='op_pending_1'"
        )
    completed_run = sync_service.get_sync_run("sync_pending_1")
    assert completed_run is not None
    assert completed_run.status == "COMPLETED"
    assert completed_run.finished_at == "2026-09-01T00:01:00Z"

    # 2. Failure before effects: status becomes FAILED with finished_at
    note = markdown_root / "01-09-2026.md"
    note.write_text("# 01-09-2026\n", encoding="utf-8")

    op_fail_1 = ledger.claim(
        kind="SYNC_RUN",
        key=f"fail-key-{token_urlsafe(8)}",
        method="POST",
        path="/api/v1/sync-runs",
        body={"reason": "MANUAL"},
        preconditions={},
    ).operation.operation_id

    # Monkeypatch to inject failure before any effects are committed
    def fail_scan(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("Disk scan failed")

    monkeypatch.setattr(os, "walk", fail_scan)
    with pytest.raises(RuntimeError, match="Disk scan failed"):
        sync_service.sync(reason="MANUAL", operation_id=op_fail_1)

    op_record_1 = ledger.get(op_fail_1)
    assert op_record_1 is not None
    assert op_record_1.status == "FAILED"
    assert op_record_1.error_category == "INTERNAL_ERROR"

    # Undo scan failure
    monkeypatch.undo()

    # 3. Failure after local effects committed: status becomes UNKNOWN to prevent unsafe redispatch
    op_fail_2 = ledger.claim(
        kind="SYNC_RUN",
        key=f"fail-key-{token_urlsafe(8)}",
        method="POST",
        path="/api/v1/sync-runs",
        body={"reason": "MANUAL"},
        preconditions={},
    ).operation.operation_id

    def fail_before_complete(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("Crash before complete receipt")

    monkeypatch.setattr(ledger, "complete", fail_before_complete)
    with pytest.raises(RuntimeError, match="Crash before complete receipt"):
        sync_service.sync(reason="MANUAL", operation_id=op_fail_2)

    op_record_2 = ledger.get(op_fail_2)
    assert op_record_2 is not None
    assert op_record_2.status == "UNKNOWN"
    assert op_record_2.error_category == "INTERNAL_ERROR"


def test_journal_fencing_active_intent_and_stale_baselines(
    test_db: Database,
    markdown_root: Path,
) -> None:
    note = markdown_root / "01-09-2026.md"
    note.write_text(
        """# 01-09-2026

## Tra cứu nhanh

| Từ/cụm từ | IPA (US) | Nghĩa ngắn | Ví dụ ngắn | Dịch ví dụ |
|---|---|---|---|---|
| [paradigm](#paradigm) | /pærədaim/ | mô hình | A new paradigm. | Một mô hình mới. |

## Paradigm

| Từ/cụm từ | Từ loại | IPA (US) | Trọng âm | Nguồn |
|---|---|---|---|---|
| paradigm | noun | /pærədaim/ | Âm tiết 1 | [Cambridge](https://cambridge.org/paradigm) |

### Ý nghĩa

- **Nghĩa thông dụng**: mô hình mẫu

### Trong ngữ cảnh

Trong nghiên cứu khoa học.

### Ví dụ

A new paradigm emerged.

*Bản dịch:* Một mô hình mới xuất hiện.
""",
        encoding="utf-8",
    )

    ledger = OperationLedger(test_db.engine)
    sync_service = SyncService(test_db.engine, markdown_root, operation_ledger=ledger)
    repo = VocabularyRepository(test_db.engine)

    # Initial sync
    res1 = sync_service.sync(reason="MANUAL")
    assert res1.status == "COMPLETED"

    src_row = (
        test_db.engine.connect()
        .exec_driver_sql(
            "SELECT id, revision, content_hash FROM source_files "
            "WHERE relative_path='01-09-2026.md'"
        )
        .mappings()
        .one()
    )
    src_id = str(src_row["id"])
    assert src_row["revision"] == 1
    orig_hash = str(src_row["content_hash"])

    forms = repo.get_forms_for_source(src_id)
    assert len(forms) == 1
    form_id = forms[0].id

    # 1. Simulate an active writer journal intent for this source
    op_w1 = f"op_w1_{token_urlsafe(8)}"
    dummy_hash = hashlib.sha256(b"new content from writer").hexdigest()
    with (
        test_db.engine.connect().execution_options(sqlite_begin_immediate=True) as conn,
        conn.begin(),
    ):
        conn.exec_driver_sql(
            "INSERT INTO operations (operation_id, kind, status, created_at, updated_at) "
            "VALUES (?, 'SOURCE_WRITE', 'PENDING', '2026-09-01T00:00:00Z', '2026-09-01T00:00:00Z')",
            (op_w1,),
        )
        plan_json = json.dumps(
            {"version": 1, "forms": [{"form_id": form_id}], "links": [], "removed": []}
        )
        conn.exec_driver_sql(
            "INSERT INTO source_write_journal (operation_id, source_id, old_hash, new_hash, "
            "intended_projection_revision, effect_plan, response_status, result_ref, state, "
            "created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 2, ?, 200, 'ref_w1', 'PREPARED', "
            "'2026-09-01T00:00:00Z', '2026-09-01T00:00:00Z')",
            (op_w1, src_id, orig_hash, dummy_hash, plan_json),
        )

    # Edit the markdown file externally while the journal is PREPARED
    note.write_text(
        note.read_text(encoding="utf-8") + "\n<!-- external change -->\n",
        encoding="utf-8",
    )

    # Sync runs: MUST fence the active journal (defer/skip modifying src_id and form_id)
    res2 = sync_service.sync(reason="MANUAL")
    assert res2.status == "COMPLETED"

    # Verify source_files was NOT overwritten by sync
    src_after = (
        test_db.engine.connect()
        .exec_driver_sql("SELECT revision, content_hash FROM source_files WHERE id=?", (src_id,))
        .mappings()
        .one()
    )
    assert src_after["revision"] == 1
    assert src_after["content_hash"] == orig_hash


# ---------------------------------------------------------------------------
# F1-F7 Remediation Regression Tests
# ---------------------------------------------------------------------------


def test_f1_whole_source_deferral_under_journal_fencing(
    test_db: Database,
    markdown_root: Path,
) -> None:
    older_note = markdown_root / "01-09-2026.md"
    older_note.write_text(
        """# 01-09-2026

## Tra cứu nhanh

| Từ/cụm từ | IPA (US) | Nghĩa ngắn | Ví dụ ngắn | Dịch ví dụ |
|---|---|---|---|---|
| [paradigm](#paradigm) | /pær.ə.daim/ | mô hình | A new paradigm. | Một mô hình mới. |

## Paradigm

| Từ/cụm từ | Từ loại | IPA (US) | Trọng âm | Nguồn |
|---|---|---|---|---|
| paradigm | noun | /pær.ə.daim/ | Âm tiết 1 | [Cambridge](https://cambridge.org/paradigm) |

### Ý nghĩa

- **Nghĩa thông dụng**: mô hình mẫu

### Trong ngữ cảnh

Trong nghiên cứu khoa học.

### Ví dụ

A new paradigm emerged.

*Bản dịch:* Một mô hình mới xuất hiện.
""",
        encoding="utf-8",
    )

    ledger = OperationLedger(test_db.engine)
    sync_service = SyncService(test_db.engine, markdown_root, operation_ledger=ledger)
    repo = VocabularyRepository(test_db.engine)
    search_index = SearchIndex(test_db.engine)

    # Step 1: Project older source and seed card history
    res1 = sync_service.sync(reason="MANUAL")
    assert res1.status == "COMPLETED"

    op_rev = ledger.claim(
        kind="REVIEW",
        key=f"rev-key-{token_urlsafe(8)}",
        method="POST",
        path="/synthetic/review",
        body={"rating": "GOOD"},
        preconditions={},
    ).operation.operation_id

    with (
        test_db.engine.connect().execution_options(sqlite_begin_immediate=True) as conn,
        conn.begin(),
    ):
        older_row = (
            conn.exec_driver_sql(
                "SELECT id, revision, content_hash FROM source_files "
                "WHERE relative_path='01-09-2026.md'"
            )
            .mappings()
            .one()
        )
        older_id = str(older_row["id"])
        wf = repo.get_forms_for_source(older_id, connection=conn)[0]
        card_id = str(
            conn.exec_driver_sql(
                "SELECT card_id FROM review_cards WHERE word_form_id=?", (wf.id,)
            ).scalar_one()
        )
        card = get_card(conn, card_id)
        assert card is not None

        # Seed review history: advance to box 1
        from datetime import UTC, datetime

        record_review(
            conn,
            card_id=card_id,
            event_id=f"rev_ev_{token_urlsafe(8)}",
            operation_id=op_rev,
            source="FLASHCARD",
            rating="GOOD",
            reviewed_at=datetime.now(UTC),
        )
        card_seeded = get_card(conn, card_id)
        assert card_seeded is not None
        assert card_seeded.box == 1

    # Step 2: Create an active journal fencing form wf.id
    op_fence = f"op_fence_{token_urlsafe(8)}"
    with (
        test_db.engine.connect().execution_options(sqlite_begin_immediate=True) as conn,
        conn.begin(),
    ):
        conn.exec_driver_sql(
            "INSERT INTO operations (operation_id, kind, status, created_at, updated_at) "
            "VALUES (?, 'SOURCE_WRITE', 'PENDING', '2026-09-01T00:00:00Z', '2026-09-01T00:00:00Z')",
            (op_fence,),
        )
        plan_json = json.dumps(
            {"version": 1, "forms": [{"form_id": wf.id}], "links": [], "removed": []}
        )
        conn.exec_driver_sql(
            "INSERT INTO source_write_journal (operation_id, source_id, old_hash, new_hash, "
            "intended_projection_revision, effect_plan, response_status, result_ref, state, "
            "created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 2, ?, 200, 'ref_fence', 'PREPARED', "
            "'2026-09-01T00:00:00Z', '2026-09-01T00:00:00Z')",
            (op_fence, older_id, "a" * 64, "b" * 64, plan_json),
        )

    # Step 3: Add another valid source containing the same form
    newer_note = markdown_root / "02-09-2026.md"
    newer_note.write_text(
        older_note.read_text(encoding="utf-8").replace("01-09-2026", "02-09-2026"),
        encoding="utf-8",
    )

    # Step 4: Sync during fencing -> whole source 02-09-2026.md MUST BE DEFERRED!
    res_fenced = sync_service.sync(reason="MANUAL")
    assert res_fenced.status == "COMPLETED"

    with test_db.engine.connect() as conn:
        newer_row = (
            conn.exec_driver_sql(
                "SELECT id, status FROM source_files WHERE relative_path='02-09-2026.md'"
            )
            .mappings()
            .first()
        )
        # Whole source deferred: not saved as VALID with unlinked form
        assert newer_row is None

    # Step 5: Clear / resolve the fence
    with (
        test_db.engine.connect().execution_options(sqlite_begin_immediate=True) as conn,
        conn.begin(),
    ):
        conn.exec_driver_sql(
            "UPDATE source_write_journal SET state='ABORTED', updated_at='2026-09-01T00:01:00Z' "
            "WHERE operation_id=?",
            (op_fence,),
        )
        conn.exec_driver_sql(
            "UPDATE operations SET status='FAILED', updated_at='2026-09-01T00:01:00Z' "
            "WHERE operation_id=?",
            (op_fence,),
        )

    # Step 6: Sync the unchanged new source after service recreation
    recreated_service = SyncService(test_db.engine, markdown_root, operation_ledger=ledger)
    res_cleared = recreated_service.sync(reason="MANUAL")
    assert res_cleared.status == "COMPLETED"

    with test_db.engine.connect() as conn:
        newer_row_after = (
            conn.exec_driver_sql(
                "SELECT id, status, revision FROM source_files WHERE relative_path='02-09-2026.md'"
            )
            .mappings()
            .one()
        )
        assert newer_row_after["status"] == "VALID"
        newer_id = str(newer_row_after["id"])
        forms_newer = repo.get_forms_for_source(newer_id, connection=conn)
        assert any(f.id == wf.id for f in forms_newer)

    # Step 7: Remove older synthetic source and sync
    older_note.unlink()
    res_remove_older = recreated_service.sync(reason="MANUAL")
    assert res_remove_older.status == "COMPLETED"

    # Step 8: Assert remaining VALID source has form link, search/review eligibility,
    # and retained history
    with test_db.engine.connect() as conn:
        older_status = conn.exec_driver_sql(
            "SELECT status FROM source_files WHERE id=?", (older_id,)
        ).scalar()
        assert older_status == "MISSING"

        newer_status = conn.exec_driver_sql(
            "SELECT status FROM source_files WHERE id=?", (newer_id,)
        ).scalar()
        assert newer_status == "VALID"

        # Form remains linked to newer source
        remaining_forms = repo.get_forms_for_source(newer_id, connection=conn)
        assert any(f.id == wf.id for f in remaining_forms)

        # Card retains history and identity
        card_retained = get_card(conn, card_id)
        assert card_retained is not None
        assert card_retained.card_id == card_id
        assert card_retained.box == 1

        # Search eligibility
        search_results = search_index.search("mô hình")
        assert len(search_results) > 0
        assert any(r.word_form_id == wf.id for r in search_results)

    # Step 9: Existing source deferred edit under active journal fencing
    op_fence2 = f"op_fence2_{token_urlsafe(8)}"
    with (
        test_db.engine.connect().execution_options(sqlite_begin_immediate=True) as conn,
        conn.begin(),
    ):
        conn.exec_driver_sql(
            "INSERT INTO operations (operation_id, kind, status, created_at, updated_at) "
            "VALUES (?, 'SOURCE_WRITE', 'PENDING', '2026-09-02T00:00:00Z', '2026-09-02T00:00:00Z')",
            (op_fence2,),
        )
        plan_json2 = json.dumps(
            {"version": 1, "forms": [{"form_id": wf.id}], "links": [], "removed": []}
        )
        conn.exec_driver_sql(
            "INSERT INTO source_write_journal (operation_id, source_id, old_hash, new_hash, "
            "intended_projection_revision, effect_plan, response_status, result_ref, state, "
            "created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 3, ?, 200, 'ref_fence2', 'PREPARED', "
            "'2026-09-02T00:00:00Z', '2026-09-02T00:00:00Z')",
            (op_fence2, newer_id, "c" * 64, "d" * 64, plan_json2),
        )

    # Edit newer_note externally while fenced
    with test_db.engine.connect() as conn:
        rev_before = (
            conn.exec_driver_sql(
                "SELECT revision, content_hash FROM source_files WHERE id=?", (newer_id,)
            )
            .mappings()
            .one()
        )

    newer_note.write_text(
        newer_note.read_text(encoding="utf-8") + "\n<!-- external edit during fence -->\n",
        encoding="utf-8",
    )

    # Sync while fenced -> newer_note must be deferred (revision/hash unchanged)
    res_fenced_edit = recreated_service.sync(reason="MANUAL")
    assert res_fenced_edit.status == "COMPLETED"

    with test_db.engine.connect() as conn:
        rev_fenced = (
            conn.exec_driver_sql(
                "SELECT revision, content_hash FROM source_files WHERE id=?", (newer_id,)
            )
            .mappings()
            .one()
        )
        assert rev_fenced["revision"] == rev_before["revision"]
        assert rev_fenced["content_hash"] == rev_before["content_hash"]

    # Clear fence 2
    with (
        test_db.engine.connect().execution_options(sqlite_begin_immediate=True) as conn,
        conn.begin(),
    ):
        conn.exec_driver_sql(
            "UPDATE source_write_journal SET state='ABORTED' WHERE operation_id=?",
            (op_fence2,),
        )
        conn.exec_driver_sql(
            "UPDATE operations SET status='FAILED' WHERE operation_id=?",
            (op_fence2,),
        )

    # Sync with unchanged disk bytes after clearing fence -> advances revision
    res_unfenced_edit = recreated_service.sync(reason="MANUAL")
    assert res_unfenced_edit.status == "COMPLETED"

    with test_db.engine.connect() as conn:
        rev_unfenced = (
            conn.exec_driver_sql(
                "SELECT revision, content_hash FROM source_files WHERE id=?", (newer_id,)
            )
            .mappings()
            .one()
        )
        assert rev_unfenced["revision"] > rev_before["revision"]
        assert rev_unfenced["content_hash"] != rev_before["content_hash"]


async def test_f2_typed_redacted_internal_error_on_unexpected_http_failure(
    authed_client: tuple[AsyncClient, FastAPI, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, app, _ = authed_client
    sentinel = "SENTINEL_EXCEPTION_PATH_/home/user/vocab/secret_note.md"

    def _failing_sync(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError(sentinel)

    assert app.state.sync_service is not None
    monkeypatch.setattr(app.state.sync_service, "sync", _failing_sync)

    resp = await client.post(
        "/api/v1/sync-runs",
        json={"reason": "MANUAL"},
        headers={
            "Idempotency-Key": f"fail-key-{token_urlsafe(8)}",
            "Origin": "http://127.0.0.1:8000",
        },
    )
    assert resp.status_code == 500
    body = resp.json()
    assert "error" in body
    err = body["error"]
    assert err["code"] == "INTERNAL_ERROR"
    assert err["message"] == "Internal server error"
    assert err["requestId"].startswith("req_")
    # Redaction: No sentinel, paths, or learning content
    raw_text = resp.text
    assert "SENTINEL" not in raw_text
    assert "/home/user" not in raw_text
    assert "Traceback" not in raw_text
    assert "secret_note" not in raw_text


async def test_f3_replay_terminal_failure_receipts_truthfully(
    db_path: Path,
    markdown_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 1. Start app and trigger genuine failure
    app = create_app(AppSettings(storage_path=db_path), markdown_root=markdown_root)
    idem_key = f"terminal-fail-key-{token_urlsafe(8)}"

    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://127.0.0.1:8000") as client,
    ):
        token = app.state.sessions.issue_bootstrap_token()
        exch = await client.post(
            "/bootstrap/exchange",
            json={"token": token},
            headers={"Origin": "http://127.0.0.1:8000"},
        )
        client.cookies.set("launch_session", exch.cookies["launch_session"])

        call_count = 0

        def _fail_once(*_args: Any, **_kwargs: Any) -> Any:
            nonlocal call_count
            call_count += 1
            raise RuntimeError("Database connection lost during sync")

        assert app.state.sync_service is not None
        monkeypatch.setattr(app.state.sync_service.search_index, "update_source", _fail_once)

        # Write a file so update_source is invoked
        (markdown_root / "test_note.md").write_text(SAMPLE_NOTE_G, encoding="utf-8")

        # Initial request fails
        resp1 = await client.post(
            "/api/v1/sync-runs",
            json={"reason": "MANUAL"},
            headers={"Idempotency-Key": idem_key, "Origin": "http://127.0.0.1:8000"},
        )
        assert resp1.status_code == 500
        assert resp1.json()["error"]["code"] == "INTERNAL_ERROR"
        assert call_count == 1

        # Replay before recreation
        resp_replay1 = await client.post(
            "/api/v1/sync-runs",
            json={"reason": "MANUAL"},
            headers={"Idempotency-Key": idem_key, "Origin": "http://127.0.0.1:8000"},
        )
        assert resp_replay1.status_code == 500  # NOT 202!
        assert resp_replay1.json()["error"]["code"] == "INTERNAL_ERROR"
        assert call_count == 1  # No extra dispatch!

    # 2. Recreate service/ledger over the same synthetic database
    app2 = create_app(AppSettings(storage_path=db_path), markdown_root=markdown_root)
    async with (
        app2.router.lifespan_context(app2),
        AsyncClient(transport=ASGITransport(app=app2), base_url="http://127.0.0.1:8000") as client2,
    ):
        token2 = app2.state.sessions.issue_bootstrap_token()
        exch2 = await client2.post(
            "/bootstrap/exchange",
            json={"token": token2},
            headers={"Origin": "http://127.0.0.1:8000"},
        )
        client2.cookies.set("launch_session", exch2.cookies["launch_session"])

        # Replay after service recreation
        resp_replay2 = await client2.post(
            "/api/v1/sync-runs",
            json={"reason": "MANUAL"},
            headers={"Idempotency-Key": idem_key, "Origin": "http://127.0.0.1:8000"},
        )
        assert resp_replay2.status_code == 500  # NOT 202!
        assert resp_replay2.json()["error"]["code"] == "INTERNAL_ERROR"

        # Changed payload returns 422 IDEMPOTENCY_KEY_REUSED
        resp_diff = await client2.post(
            "/api/v1/sync-runs",
            json={"reason": "STARTUP"},
            headers={"Idempotency-Key": idem_key, "Origin": "http://127.0.0.1:8000"},
        )
        assert resp_diff.status_code == 422
        assert resp_diff.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"


def test_f4_durable_failed_run_metrics_and_timestamps(
    test_db: Database,
    markdown_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Prepare 1 valid file and 1 invalid file
    (markdown_root / "valid.md").write_text(SAMPLE_NOTE_G, encoding="utf-8")
    (markdown_root / "invalid.md").write_text("CORRUPTED", encoding="utf-8")

    ledger = OperationLedger(test_db.engine)
    sync_service = SyncService(test_db.engine, markdown_root, operation_ledger=ledger)

    # Initial run to establish non-zero baseline revision
    init_res = sync_service.sync(reason="MANUAL")
    assert init_res.status == "COMPLETED"

    # Now make valid.md have a new change
    (markdown_root / "valid.md").write_text(SAMPLE_NOTE_G + "\n<!-- edit -->\n", encoding="utf-8")

    # Inject failure AFTER sources have been scanned and parsed
    orig_search_update = sync_service.search_index.update_source
    fail_after_scan = True

    def _failing_update(*args: Any, **kwargs: Any) -> Any:
        if fail_after_scan:
            raise RuntimeError("Synthetic failure during search index update")
        return orig_search_update(*args, **kwargs)

    monkeypatch.setattr(sync_service.search_index, "update_source", _failing_update)

    with pytest.raises(RuntimeError, match="Synthetic failure"):
        sync_service.sync(reason="MANUAL")

    # Get failed run from cache
    cached_runs = list(sync_service._sync_cache.values())
    failed_cached = next(r for r in cached_runs if r.status == "FAILED")
    assert failed_cached.sources_scanned >= 2
    assert failed_cached.sources_invalid >= 1
    assert failed_cached.finished_at is not None

    # Now RECREATE the SyncService over the same DB (clearing in-memory cache)
    recreated = SyncService(test_db.engine, markdown_root, operation_ledger=ledger)
    durable_run = recreated.get_sync_run(failed_cached.id)
    assert durable_run is not None
    assert durable_run.id == failed_cached.id
    assert durable_run.status == "FAILED"
    assert durable_run.operation_id == failed_cached.operation_id
    assert durable_run.sources_scanned == failed_cached.sources_scanned
    assert durable_run.sources_invalid == failed_cached.sources_invalid
    assert durable_run.source_revision == failed_cached.source_revision
    assert durable_run.started_at == failed_cached.started_at
    assert durable_run.finished_at == failed_cached.finished_at


def test_f5_durable_aggregate_source_revision_and_cursor_invalidation(
    test_db: Database,
    markdown_root: Path,
) -> None:
    note_a = (
        SAMPLE_NOTE_G.replace("29-09-2026", "01-09-2026")
        .replace("robust", "apple")
        .replace("Robust", "Apple")
        .replace("bền vững, vững chắc", "quả táo")
        .replace("The system is robust.", "An apple a day.")
        .replace("Hệ thống rất bền.", "Ăn táo mỗi ngày.")
        .replace("Hệ thống rất bền vững.", "Ăn táo rất tốt.")
        .replace("The system is robust and secure.", "An apple is fresh.")
    )
    file_a = markdown_root / "01-09-2026.md"
    file_a.write_text(note_a, encoding="utf-8")
    hash_a = hashlib.sha256(note_a.encode("utf-8")).hexdigest()

    # 1. Seed Source A with revision 10
    with (
        test_db.engine.connect().execution_options(sqlite_begin_immediate=True) as conn,
        conn.begin(),
    ):
        conn.exec_driver_sql(
            "INSERT INTO source_files (id, relative_path, note_date, status, revision, etag, "
            "content_hash, created_at, updated_at) "
            "VALUES ('src_a', '01-09-2026.md', '2026-09-01', 'VALID', 10, '\"src-r10-src_a\"', "
            "?, '2026-09-01T00:00:00Z', '2026-09-01T00:00:00Z')",
            (hash_a,),
        )

    # Add source B on disk (revision 1)
    file_b = markdown_root / "29-09-2026.md"
    file_b.write_text(SAMPLE_NOTE_G, encoding="utf-8")

    ledger = OperationLedger(test_db.engine)
    sync_service = SyncService(test_db.engine, markdown_root, operation_ledger=ledger)

    res1 = sync_service.sync(reason="MANUAL")
    assert res1.status == "COMPLETED"
    # Aggregate revision = 10 (A) + 1 (B) = 11
    assert res1.source_revision == 11

    # Per-source revisions preserved:
    with test_db.engine.connect() as conn:
        rev_a = conn.exec_driver_sql("SELECT revision FROM source_files WHERE id='src_a'").scalar()
        rev_b = conn.exec_driver_sql(
            "SELECT revision FROM source_files WHERE relative_path='29-09-2026.md'"
        ).scalar()
        assert rev_a == 10
        assert rev_b == 1

    # Issue a cursor from list_sources
    _sources, cursor, _has_more = sync_service.list_sources(page_size=1)
    assert cursor is not None

    # 2. Advance B from revision 1 to 2
    file_b.write_text(SAMPLE_NOTE_G + "\n<!-- edit B -->\n", encoding="utf-8")
    res2 = sync_service.sync(reason="MANUAL")
    assert res2.status == "COMPLETED"
    # Aggregate revision advances 11 -> 12!
    assert res2.source_revision == 12

    with test_db.engine.connect() as conn:
        rev_a = conn.exec_driver_sql("SELECT revision FROM source_files WHERE id='src_a'").scalar()
        rev_b = conn.exec_driver_sql(
            "SELECT revision FROM source_files WHERE relative_path='29-09-2026.md'"
        ).scalar()
        assert rev_a == 10
        assert rev_b == 2

    # Old cursor must now be expired!
    with pytest.raises(CursorExpiredError):
        sync_service.list_sources(page_size=1, cursor=cursor)

    # 3. Add another revision-1 source C
    note_c = (
        SAMPLE_NOTE_G.replace("29-09-2026", "28-09-2026")
        .replace("robust", "banana")
        .replace("Robust", "Banana")
        .replace("bền vững, vững chắc", "quả chuối")
        .replace("The system is robust.", "A yellow banana.")
        .replace("Hệ thống rất bền.", "Chuối vàng rất ngon.")
        .replace("Hệ thống rất bền vững.", "Chuối rất ngon.")
        .replace("The system is robust and secure.", "A banana is sweet.")
    )
    file_c = markdown_root / "28-09-2026.md"
    file_c.write_text(note_c, encoding="utf-8")
    res3 = sync_service.sync(reason="MANUAL")
    assert res3.status == "COMPLETED"
    # Aggregate revision advances 12 -> 13!
    assert res3.source_revision == 13

    with test_db.engine.connect() as conn:
        rev_c = conn.exec_driver_sql(
            "SELECT revision FROM source_files WHERE relative_path='28-09-2026.md'"
        ).scalar()
        assert rev_c == 1

    # 4. Validity/missing transitions
    # Make C INVALID
    file_c.write_text("# 28-09-2026\nINVALID CONTENT\n", encoding="utf-8")
    res4 = sync_service.sync(reason="MANUAL")
    # C revision 1 -> 2; aggregate 13 -> 14!
    assert res4.source_revision == 14

    # Delete C -> transitions to MISSING
    file_c.unlink()
    res5 = sync_service.sync(reason="MANUAL")
    # C revision 2 -> 3; aggregate 14 -> 15!
    assert res5.source_revision == 15

    # 5. Service recreation
    recreated = SyncService(test_db.engine, markdown_root, operation_ledger=ledger)
    assert recreated._get_aggregate_source_revision() == 15

    # 6. Unchanged-byte run / echo
    res_echo = recreated.sync(reason="MANUAL")
    assert res_echo.source_revision == 15


async def test_f6_startup_watcher_handshake_deterministic_barrier(
    db_path: Path,
    markdown_root: Path,
) -> None:
    # 1. Seed initial source and card
    note_path = markdown_root / "29-09-2026.md"
    note_path.write_text(SAMPLE_NOTE_G, encoding="utf-8")

    db = Database(db_path)
    db.initialize()
    ledger = OperationLedger(db.engine)
    init_sync = SyncService(db.engine, markdown_root, operation_ledger=ledger)
    init_sync.sync(reason="STARTUP")

    op_rev = ledger.claim(
        kind="REVIEW",
        key=f"rev-key-{token_urlsafe(8)}",
        method="POST",
        path="/synthetic/review",
        body={"rating": "GOOD"},
        preconditions={},
    ).operation.operation_id
    from datetime import UTC, datetime

    with (
        db.engine.connect().execution_options(sqlite_begin_immediate=True) as conn,
        conn.begin(),
    ):
        row = conn.exec_driver_sql("SELECT card_id FROM review_cards").first()
        assert row is not None
        card_id = row[0]
        # Seed history
        record_review(
            conn,
            card_id=card_id,
            event_id=f"rev_ev_{token_urlsafe(8)}",
            operation_id=op_rev,
            source="FLASHCARD",
            rating="GOOD",
            reviewed_at=datetime.now(UTC),
        )
        card_before = get_card(conn, card_id)
        assert card_before is not None
        assert card_before.box == 1

    db.close()

    # 2. Race condition test around startup handoff using a deterministic barrier
    race_done = threading.Event()
    app = create_app(AppSettings(storage_path=db_path), markdown_root=markdown_root)

    orig_sync = SyncService.sync

    def _hooked_sync(self: SyncService, *args: Any, **kwargs: Any) -> Any:
        res = orig_sync(self, *args, **kwargs)
        is_startup = kwargs.get("reason") == "STARTUP" or (args and args[0] == "STARTUP")
        if is_startup and not race_done.is_set():
            # Edit file externally at handoff boundary before watcher starts observing!
            edited = SAMPLE_NOTE_G.replace(
                "The system is robust.", "The system is extraordinarily robust."
            ).replace("bền vững, vững chắc", "cực kỳ bền vững")
            note_path.write_text(edited, encoding="utf-8")
            race_done.set()
        return res

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(SyncService, "sync", _hooked_sync)
        async with app.router.lifespan_context(app):
            assert app.state.ready is True
            watcher: SourceWatcher | None = app.state.watcher
            assert watcher is not None
            # Allow watcher to poll / process
            watcher.poll_now()
            time.sleep(0.6)

            # Check that external edit was projected and searchable
            search_idx = SearchIndex(app.state.database.engine)
            results = search_idx.search("cực kỳ bền vững")
            assert len(results) > 0

            with app.state.database.engine.connect() as conn:
                card_after = get_card(conn, card_id)
                assert card_after is not None
                # Card was reset exactly ONCE
                assert card_after.box == 0
                q_rev1 = card_after.queue_revision

            # Repeated poll / echo does not advance revision or reset again
            watcher.poll_now()
            time.sleep(0.6)
            with app.state.database.engine.connect() as conn:
                card_after2 = get_card(conn, card_id)
                assert card_after2 is not None
                assert card_after2.box == 0
                assert card_after2.queue_revision == q_rev1  # Did not reset again!


async def test_f7_safe_startup_degradation_source_boundary_failures(
    tmp_path: Path,
    db_path: Path,
    test_db: Database,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A. Missing configured root directory: must not crash lifespan, health is NOT_READY
    nonexistent_root = tmp_path / "nonexistent_markdown_root"
    app_missing = create_app(AppSettings(storage_path=db_path), markdown_root=nonexistent_root)

    transport_missing = ASGITransport(app=app_missing)
    async with (
        app_missing.router.lifespan_context(app_missing),
        AsyncClient(transport=transport_missing, base_url="http://127.0.0.1:8000") as client,
    ):
        assert app_missing.state.ready is False
        assert app_missing.state.storage_error == "SOURCE_UNAVAILABLE"

        h_resp = await client.get("/api/v1/health")
        assert h_resp.status_code == 200
        h_data = h_resp.json()
        assert h_data["status"] == "NOT_READY"
        assert h_data["storageStatus"] == "NOT_READY"
        assert h_data["readiness"] is False

        token = app_missing.state.sessions.issue_bootstrap_token()
        exch = await client.post(
            "/bootstrap/exchange",
            json={"token": token},
            headers={"Origin": "http://127.0.0.1:8000"},
        )
        client.cookies.set("launch_session", exch.cookies["launch_session"])

        # Sources endpoint is guarded and returns 503
        s_resp = await client.get("/api/v1/sources")
        assert s_resp.status_code == 503

    # B. Injected access refusal (SourceSecurityError)
    valid_root = tmp_path / "vocab"
    valid_root.mkdir()
    app_sec = create_app(AppSettings(storage_path=db_path), markdown_root=valid_root)

    def _failing_adapter(*_args: Any, **_kwargs: Any) -> Any:
        raise SourceSecurityError("SECURITY_VIOLATION", "Access denied to configured root")

    monkeypatch.setattr("backend.app.main.SourceFileAdapter", _failing_adapter)

    transport_sec = ASGITransport(app=app_sec)
    async with (
        app_sec.router.lifespan_context(app_sec),
        AsyncClient(transport=transport_sec, base_url="http://127.0.0.1:8000") as client,
    ):
        assert app_sec.state.ready is False
        assert app_sec.state.storage_error == "SOURCE_UNAVAILABLE"

        h_resp = await client.get("/api/v1/health")
        assert h_resp.status_code == 200
        assert h_resp.json()["status"] == "NOT_READY"

        token_sec = app_sec.state.sessions.issue_bootstrap_token()
        exch_sec = await client.post(
            "/bootstrap/exchange",
            json={"token": token_sec},
            headers={"Origin": "http://127.0.0.1:8000"},
        )
        client.cookies.set("launch_session", exch_sec.cookies["launch_session"])
        s_resp_sec = await client.get("/api/v1/sources")
        assert s_resp_sec.status_code == 503

    # C. Inaccessible root must NOT mark known database sources as MISSING
    (valid_root / "29-09-2026.md").write_text(SAMPLE_NOTE_G, encoding="utf-8")
    monkeypatch.undo()
    sync_service = SyncService(test_db.engine, valid_root)
    sync_service.sync(reason="MANUAL")

    with test_db.engine.connect() as conn:
        status_before = conn.exec_driver_sql(
            "SELECT status FROM source_files WHERE relative_path='29-09-2026.md'"
        ).scalar()
        assert status_before == "VALID"

    # Now attempt sync with nonexistent root
    bad_service = SyncService(test_db.engine, nonexistent_root)
    with pytest.raises(SourceFileError):
        bad_service.sync(reason="MANUAL")

    with test_db.engine.connect() as conn:
        status_after = conn.exec_driver_sql(
            "SELECT status FROM source_files WHERE relative_path='29-09-2026.md'"
        ).scalar()
        assert status_after == "VALID"  # RETAINED! Not marked MISSING!


def _sync_learning_snapshot(database: Database) -> dict[str, list[tuple[Any, ...]]]:
    """Capture durable learning and projection state, excluding operation receipts."""
    tables = (
        "source_files",
        "word_forms",
        "word_form_sources",
        "review_cards",
        "review_events",
        "search_projection_sources",
        "search_projection_entries",
        "search_projection_ngrams",
    )
    with database.engine.connect() as conn:
        return {
            table: [tuple(row) for row in conn.exec_driver_sql(f"SELECT * FROM {table} ORDER BY rowid")]
            for table in tables
        }


def _seed_sync_review(database: Database, ledger: OperationLedger) -> None:
    from datetime import UTC, datetime

    operation_id = ledger.claim(
        kind="REVIEW",
        key=f"scan-review-{token_urlsafe(8)}",
        method="POST",
        path="/synthetic/review",
        body={"rating": "GOOD"},
        preconditions={},
    ).operation.operation_id
    with (
        database.engine.connect().execution_options(sqlite_begin_immediate=True) as conn,
        conn.begin(),
    ):
        card_id = conn.exec_driver_sql(
            "SELECT c.card_id FROM review_cards c JOIN word_forms w ON w.id=c.word_form_id "
            "WHERE w.lemma='robust'"
        ).scalar_one()
        record_review(
            conn,
            card_id=card_id,
            event_id=f"scan_event_{token_urlsafe(8)}",
            operation_id=operation_id,
            source="FLASHCARD",
            rating="GOOD",
            reviewed_at=datetime.now(UTC),
        )


def test_nested_traversal_failure_preserves_sources_and_learning_state(
    test_db: Database,
    markdown_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    nested = markdown_root / "private"
    nested.mkdir()
    (nested / "28-09-2026.md").write_text(SAMPLE_NOTE_F, encoding="utf-8")
    visible_note = markdown_root / "29-09-2026.md"
    visible_note.write_text(SAMPLE_NOTE_G, encoding="utf-8")
    ledger = OperationLedger(test_db.engine)
    service = SyncService(test_db.engine, markdown_root, operation_ledger=ledger)
    service.sync(reason="MANUAL")
    _seed_sync_review(test_db, ledger)
    before = _sync_learning_snapshot(test_db)
    assert before["review_events"]
    visible_note.write_text(SAMPLE_NOTE_G + "\n<!-- external edit -->\n", encoding="utf-8")

    # Emulate os.walk yielding a readable parent before scandir fails in its child.
    def inaccessible_walk(
        _root: Any, *, followlinks: bool = False, onerror: Any = None
    ) -> Iterator[tuple[str, list[str], list[str]]]:
        yield str(markdown_root), ["private"], ["29-09-2026.md"]
        if onerror is not None:
            onerror(PermissionError(13, "Synthetic directory access refusal", str(nested)))

    monkeypatch.setattr("backend.app.application.sync.os.walk", inaccessible_walk)
    operation_id = ledger.claim(
        kind="SYNC_RUN",
        key=f"scan-failure-{token_urlsafe(8)}",
        method="POST",
        path="/api/v1/sync-runs",
        body={"reason": "MANUAL"},
        preconditions={},
    ).operation.operation_id

    with pytest.raises(SourceFileError) as caught:
        service.sync(reason="MANUAL", operation_id=operation_id)
    assert caught.value.code == "ACCESS_DENIED"
    assert str(nested) not in str(caught.value)
    assert _sync_learning_snapshot(test_db) == before
    operation = ledger.get(operation_id)
    assert operation is not None
    assert operation.status == "FAILED"
    assert operation.response_status == 500
    assert operation.result_ref is not None
    run = service.get_sync_run(operation.result_ref.split(".")[0])
    assert run is not None
    assert run.status == "FAILED"
    assert run.sources_scanned == 0
    assert run.finished_at is not None


@pytest.mark.parametrize(
    "malformed_form",
    [None, {}, {"form_id": None}, {"form_id": 7}, {"form_id": ""}],
)
@pytest.mark.parametrize(
    "arrival",
    [
        "BEFORE_SCAN",
        "BEFORE_MISSING_TRANSACTION",
        "DURING_VALID_PARSE",
        "DURING_INVALID_PARSE",
        "DURING_UNCHANGED_PARSE",
        "BEFORE_RECEIPT",
    ],
)
def test_malformed_active_journal_blocks_sync_without_unsafe_writes(
    test_db: Database,
    markdown_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    malformed_form: Any,
    arrival: str,
) -> None:
    from backend.app.application.source_write import JournalConflictError
    from backend.app.markdown_sync.parser import parse_markdown
    from sqlalchemy import event

    fenced_note = markdown_root / "30-09-2026.md"
    fenced_note.write_text(SAMPLE_NOTE_F.replace("28-09-2026", "30-09-2026"), encoding="utf-8")
    editable_note = markdown_root / "29-09-2026.md"
    editable_note.write_text(SAMPLE_NOTE_G, encoding="utf-8")
    ledger = OperationLedger(test_db.engine)
    service = SyncService(test_db.engine, markdown_root, operation_ledger=ledger)
    service.sync(reason="MANUAL")
    _seed_sync_review(test_db, ledger)
    before = _sync_learning_snapshot(test_db)
    assert before["review_events"]
    with test_db.engine.connect() as conn:
        source_id, old_hash = conn.exec_driver_sql(
            "SELECT id, content_hash FROM source_files WHERE relative_path='30-09-2026.md'"
        ).one()
        form_id = conn.exec_driver_sql("SELECT id FROM word_forms WHERE lemma='fragile'").scalar_one()
    writer_id = f"op_malformed_{token_urlsafe(8)}"
    valid_plan = {"version": 1, "forms": [], "links": [], "removed": []}
    # A readable entry protects fragile; the malformed entry cannot safely protect robust.
    malformed_plan = {**valid_plan, "forms": [{"form_id": form_id}, malformed_form]}

    def insert_journal(plan: dict[str, Any]) -> None:
        with (
            test_db.engine.connect().execution_options(sqlite_begin_immediate=True) as conn,
            conn.begin(),
        ):
            conn.exec_driver_sql(
                "INSERT INTO operations (operation_id, kind, status, created_at, updated_at) "
                "VALUES (?, 'SOURCE_WRITE', 'PENDING', '2026-09-29T00:00:00Z', "
                "'2026-09-29T00:00:00Z')",
                (writer_id,),
            )
            # Top-level JSON meets the journal CHECK; a form's shape is unsafe to interpret.
            conn.exec_driver_sql(
                "INSERT INTO source_write_journal (operation_id, source_id, old_hash, new_hash, "
                "intended_projection_revision, effect_plan, response_status, result_ref, state, "
                "created_at, updated_at) VALUES (?, ?, ?, ?, 2, ?, 200, 'ref_malformed', "
                "'PREPARED', '2026-09-29T00:00:00Z', '2026-09-29T00:00:00Z')",
                (writer_id, source_id, old_hash, "b" * 64, json.dumps(plan)),
            )

    if arrival == "BEFORE_SCAN":
        insert_journal(malformed_plan)
        # Also prove preflight blocks missing-source mutations unrelated to the fenced source.
        editable_note.unlink()
    elif arrival == "BEFORE_MISSING_TRANSACTION":
        editable_note.unlink()

        def journal_after_source_snapshot(
            _conn: Any,
            _cursor: Any,
            statement: str,
            _parameters: Any,
            _context: Any,
            _executemany: bool,
        ) -> None:
            if statement.startswith("SELECT id, relative_path, note_date, status, revision, etag,"):
                insert_journal(malformed_plan)

        event.listen(test_db.engine, "after_cursor_execute", journal_after_source_snapshot)
    elif arrival == "BEFORE_RECEIPT":
        original_complete = ledger.complete

        def complete_with_new_journal(*args: Any, **kwargs: Any) -> Any:
            insert_journal(malformed_plan)
            return original_complete(*args, **kwargs)

        monkeypatch.setattr(ledger, "complete", complete_with_new_journal)
    else:
        # A new writer appears after preflight; delegate to the real parser before injecting it.
        if arrival == "DURING_VALID_PARSE":
            fenced_note.write_text("INVALID SOURCE", encoding="utf-8")
            editable_note.write_text(
                SAMPLE_NOTE_G.replace("bền vững, vững chắc", "cực kỳ kiên cố"), encoding="utf-8"
            )
        elif arrival == "DURING_INVALID_PARSE":
            editable_note.write_text("INVALID SOURCE", encoding="utf-8")

        def parse_with_new_journal(content: str, *, filename: str) -> Any:
            result = parse_markdown(content, filename=filename)
            if filename == "29-09-2026.md":
                insert_journal(malformed_plan)
            return result

        monkeypatch.setattr("backend.app.application.sync.parse_markdown", parse_with_new_journal)

    operation_id = ledger.claim(
        kind="SYNC_RUN",
        key=f"journal-failure-{token_urlsafe(8)}",
        method="POST",
        path="/api/v1/sync-runs",
        body={"reason": "MANUAL"},
        preconditions={},
    ).operation.operation_id
    try:
        with pytest.raises(JournalConflictError, match="Active source journal effect plan is invalid"):
            service.sync(reason="MANUAL", operation_id=operation_id)
    finally:
        if arrival == "BEFORE_MISSING_TRANSACTION":
            event.remove(test_db.engine, "after_cursor_execute", journal_after_source_snapshot)

    assert _sync_learning_snapshot(test_db) == before
    operation = ledger.get(operation_id)
    assert operation is not None
    assert operation.status == "FAILED"
    assert operation.response_status == 500
    assert operation.result_ref is not None
    run = service.get_sync_run(operation.result_ref.split(".")[0])
    assert run is not None
    assert run.status == "FAILED"
    assert run.finished_at is not None
    writer = ledger.get(writer_id)
    assert writer is not None
    assert writer.status == "PENDING"
    with test_db.engine.connect() as conn:
        journal = conn.exec_driver_sql(
            "SELECT state, effect_plan FROM source_write_journal WHERE operation_id=?", (writer_id,)
        ).one()
        assert journal[0] == "PREPARED"
        assert json.loads(journal[1]) == malformed_plan

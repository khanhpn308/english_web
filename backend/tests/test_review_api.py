"""T032 production-route regressions using synthetic, durable SQLite state.

Execution is deferred to the integration host. No event, schedule or receipt
transaction is replaced by a mock in these tests.
"""

import asyncio
import base64
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from alembic import command
from alembic.script import ScriptDirectory
from backend.app.application.operations import OperationConflict, OperationLedger
from backend.app.assessment.questions import ClozeSnapshot, QuestionSet
from backend.app.assessment.repository import create_attempt
from backend.app.http.review import ReviewErrorResponse
from backend.app.main import create_app
from backend.app.persistence.database import Database, migration_config
from backend.app.platform.config import AppSettings
from backend.app.review.models import ensure_card, record_review, reset_card_state
from backend.app.review.queue import ReviewService
from backend.app.review.srs import transition
from backend.app.vocabulary.models import MeaningEn, MeaningVi
from backend.app.vocabulary.repository import VocabularyRepository
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Connection
from sqlalchemy import event as sqlalchemy_event
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

BASE = "http://127.0.0.1:8000"
NOW = datetime(2026, 9, 29, 10, 20, 30, tzinfo=UTC)
QUEUE = "/api/v1/review-queue"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def seed_card(
    app: FastAPI,
    name: str,
    *,
    note_date: str = "2026-09-29",
    box: int = 0,
    due_at: datetime | None = None,
    lemma: str | None = None,
) -> str:
    repository = VocabularyRepository(app.state.database.engine)
    family = repository.get_or_create_family(name, family_id=f"family_{name}")
    form = repository.save_canonical_word_form(
        lemma=lemma or name,
        part_of_speech="NOUN",
        family_id=family.id,
        meanings_en=[MeaningEn("synthetic definition", verification_status="VERIFIED")],
        meanings_vi=[MeaningVi("nghĩa thử nghiệm", verification_status="VERIFIED")],
        word_form_id=f"wf_{name}",
    )
    source = repository.save_source_file(
        source_id=f"src_{name}",
        relative_path=f"{name}.md",
        note_date=note_date,
        status="VALID",
    )
    repository.link_word_form_to_source(form.id, source.id, note_date)
    card_id = f"card_{name}"
    with (
        app.state.database.engine.connect().execution_options(sqlite_begin_immediate=True) as conn,
        conn.begin(),
    ):
        ensure_card(conn, card_id=card_id, word_form_id=form.id)
        if box:
            assert due_at is not None
            conn.exec_driver_sql(
                "UPDATE review_cards SET box=?,due_at=? WHERE card_id=?",
                (box, due_at.isoformat(timespec="microseconds").replace("+00:00", "Z"), card_id),
            )
    return card_id


@pytest.fixture
async def app(tmp_path: Path) -> AsyncIterator[FastAPI]:
    application = create_app(AppSettings(storage_path=tmp_path / "review.db"))
    async with application.router.lifespan_context(application):
        application.state.review_service.clock = lambda: NOW
        yield application


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url=BASE, headers={"Origin": BASE}
    ) as http:
        token = app.state.sessions.issue_bootstrap_token()
        response = await http.post("/bootstrap/exchange", json={"token": token})
        assert response.status_code == 204
        http.headers["Cookie"] = response.headers["set-cookie"].split(";", 1)[0]
        yield http


@pytest.mark.anyio
async def test_new_due_future_and_date_selection(client: AsyncClient, app: FastAPI) -> None:
    seed_card(app, "new")
    seed_card(app, "due", box=2, due_at=NOW)
    seed_card(app, "future", box=1, due_at=NOW + timedelta(days=1))
    seed_card(app, "other", note_date="2026-09-30", box=1, due_at=NOW)
    response = await client.get(QUEUE)
    assert response.status_code == 200
    body = response.json()
    assert body["pagination"] == {"nextCursor": None, "pageSize": 50, "hasMore": False}
    assert [item["cardId"] for item in body["data"]] == ["card_new", "card_due", "card_other"]
    assert body["data"][0]["state"] == "NEW"
    assert body["data"][1]["state"] == "LEARNED"
    all_cards = await client.get(QUEUE, params={"dueOnly": "false"})
    assert len(all_cards.json()["data"]) == 4
    for due_only in ["true", "false"]:
        selected = await client.get(
            QUEUE, params={"noteDate": "2026-09-29", "dueOnly": due_only}
        )
        assert [item["cardId"] for item in selected.json()["data"]] == ["card_new", "card_due"]


@pytest.mark.anyio
async def test_empty_and_future_only_queue(client: AsyncClient, app: FastAPI) -> None:
    assert (await client.get(QUEUE)).json()["data"] == []
    seed_card(app, "future", box=1, due_at=NOW + timedelta(days=1))
    assert (await client.get(QUEUE)).json()["data"] == []
    assert (await client.get(QUEUE, params={"dueOnly": "false"})).json()["data"]


@pytest.mark.anyio
@pytest.mark.parametrize("sort_by", ["dueAt", "lemma"])
@pytest.mark.parametrize("direction", ["ASC", "DESC"])
async def test_stable_pagination_with_unique_ties(
    client: AsyncClient, app: FastAPI, sort_by: str, direction: str
) -> None:
    for name in ["z", "a", "m"]:
        seed_card(app, name, lemma="tie", box=1, due_at=NOW)
    params = {"sortBy": sort_by, "sortOrder": direction, "pageSize": "1"}
    seen: list[str] = []
    for has_more in [True, True, False]:
        response = await client.get(QUEUE, params=params)
        assert response.status_code == 200
        body = response.json()
        seen.extend(item["cardId"] for item in body["data"])
        assert body["pagination"]["hasMore"] is has_more
        if has_more:
            params["cursor"] = body["pagination"]["nextCursor"]
    assert seen == ["card_a", "card_m", "card_z"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "query",
    [
        {"pageSize": "0"}, {"pageSize": "101"}, {"cardState": "SUSPENDED"},
        {"sortBy": "createdAt;DROP TABLE review_cards"}, {"dueOnly": "yes"},
        {"unknown": "private-value"},
    ],
)
async def test_invalid_filter_is_typed(client: AsyncClient, query: dict[str, str]) -> None:
    response = await client.get(QUEUE, params=query)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "private-value" not in response.text
    ReviewErrorResponse.model_validate(response.json())


@pytest.mark.anyio
@pytest.mark.parametrize("value", ["2026-02-30", "20260929", "２０２６-０９-２９"])
async def test_invalid_date(client: AsyncClient, value: str) -> None:
    response = await client.get(QUEUE, params={"noteDate": value})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_QUERY"


@pytest.mark.anyio
@pytest.mark.parametrize("cursor", ["", "not-a-cursor", "e30.A", "....", "é", "=" * 9000])
async def test_invalid_cursor(client: AsyncClient, cursor: str) -> None:
    response = await client.get(QUEUE, params={"cursor": cursor})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CURSOR_EXPIRED"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "change", [{"dueOnly": "false"}, {"noteDate": "2026-09-29"},
               {"cardState": "NEW"}, {"sortBy": "lemma"}, {"sortOrder": "DESC"}],
)
async def test_query_bound_cursor(
    client: AsyncClient, app: FastAPI, change: dict[str, str]
) -> None:
    seed_card(app, "a")
    seed_card(app, "b")
    first = await client.get(QUEUE, params={"pageSize": 1})
    cursor = first.json()["pagination"]["nextCursor"]
    response = await client.get(QUEUE, params={"cursor": cursor} | change)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CURSOR_EXPIRED"


@pytest.mark.anyio
async def test_bangkok_due_boundary_expires_cursor(client: AsyncClient, app: FastAPI) -> None:
    midnight = datetime(2026, 9, 29, 17, tzinfo=UTC)
    app.state.review_service.clock = lambda: midnight - timedelta(microseconds=1)
    seed_card(app, "a")
    seed_card(app, "b")
    seed_card(app, "c", box=1, due_at=midnight)
    first = await client.get(QUEUE, params={"pageSize": 1})
    cursor = first.json()["pagination"]["nextCursor"]
    assert [item["cardId"] for item in (await client.get(QUEUE)).json()["data"]] == [
        "card_a", "card_b"
    ]
    app.state.review_service.clock = lambda: midnight
    stale = await client.get(QUEUE, params={"cursor": cursor})
    assert stale.status_code == 409
    assert {item["cardId"] for item in (await client.get(QUEUE)).json()["data"]} == {
        "card_a", "card_b", "card_c"
    }


@pytest.mark.anyio
@pytest.mark.parametrize("change", ["status", "unlink", "revision"])
async def test_source_changes_expire_cursor_and_exclude_content(
    client: AsyncClient, app: FastAPI, change: str
) -> None:
    seed_card(app, "a")
    seed_card(app, "b")
    repository = VocabularyRepository(app.state.database.engine)
    cursor = (await client.get(QUEUE, params={"pageSize": 1})).json()["pagination"]["nextCursor"]
    if change == "status":
        repository.update_source_status("src_b", "INVALID", "PARSE_FAILED")
    elif change == "unlink":
        repository.unlink_source_from_form("wf_b", "src_b")
    else:
        repository.save_source_file(
            source_id="src_b", relative_path="b.md", note_date="2026-09-29",
            status="VALID", revision=2,
        )
    stale = await client.get(QUEUE, params={"cursor": cursor})
    assert stale.status_code == 409
    rows = (await client.get(QUEUE)).json()["data"]
    assert len(rows) == (2 if change == "revision" else 1)


def review_path(card_id: str) -> str:
    return f"/api/v1/cards/{card_id}/reviews"


def headers(key: str = "review-intent", revision: int = 0) -> dict[str, str]:
    return {"Idempotency-Key": key, "If-Match": str(revision)}


def stored_state(app: FastAPI, card_id: str) -> tuple[int, str | None, int, int]:
    with app.state.database.engine.connect() as conn:
        row = conn.exec_driver_sql(
            "SELECT box,due_at,queue_revision FROM review_cards WHERE card_id=?", (card_id,)
        ).one()
        events = conn.exec_driver_sql(
            "SELECT count(*) FROM review_events WHERE card_id=?", (card_id,)
        ).scalar_one()
        return int(row[0]), row[1], int(row[2]), int(events)


@pytest.mark.anyio
@pytest.mark.parametrize("box", range(6))
@pytest.mark.parametrize("rating", ["AGAIN", "HARD", "GOOD", "EASY"])
async def test_rating_event_schedule_and_receipt_are_durable(
    client: AsyncClient, app: FastAPI, box: int, rating: str
) -> None:
    card_id = seed_card(app, "rated", box=box, due_at=NOW if box else None)
    response = await client.post(
        review_path(card_id), headers=headers(), json={"rating": rating, "source": "FLASHCARD"}
    )
    assert response.status_code == 201
    event = response.json()
    expected = transition(box, rating, NOW)
    assert expected.due_at is not None
    assert datetime.fromisoformat(event["reviewedAt"]) == NOW
    assert datetime.fromisoformat(event["nextDueAt"]) == expected.due_at
    assert event["cardId"] == card_id and event["rating"] == rating
    state = stored_state(app, card_id)
    assert state == (expected.box, event["nextDueAt"], 1, 1)
    operation = (await client.get(f"/api/v1/operations/{event['operationId']}")).json()
    assert operation["status"] == "SUCCEEDED"
    assert operation["resultRef"] == event["id"]
    with app.state.database.engine.connect() as conn:
        assert conn.exec_driver_sql(
            "SELECT response_status FROM operations WHERE operation_id=?", (event["operationId"],)
        ).scalar_one() == 201
        stored = conn.exec_driver_sql("SELECT * FROM review_events").mappings().one()
        assert stored["id"] == event["id"]
        assert stored["next_box"] == expected.box
        assert stored["operation_id"] == event["operationId"]


@pytest.mark.anyio
async def test_replay_precedes_advanced_card_and_invalid_source_checks(
    client: AsyncClient, app: FastAPI
) -> None:
    card_id = seed_card(app, "replay")
    payload = {"rating": "GOOD", "source": "FLASHCARD"}
    first = await client.post(review_path(card_id), headers=headers(), json=payload)
    assert first.status_code == 201
    later = await client.post(
        review_path(card_id),
        headers=headers("later", 1),
        json={"rating": "EASY", "source": "FLASHCARD"},
    )
    assert later.status_code == 201
    repository = VocabularyRepository(app.state.database.engine)
    repository.update_source_status("src_replay", "MISSING")
    before = stored_state(app, card_id)
    replay = await client.post(review_path(card_id), headers=headers(), json=payload)
    assert replay.status_code == 201
    assert replay.json() == first.json()
    assert stored_state(app, card_id) == before
    assert before[2:] == (2, 2)


@pytest.mark.anyio
@pytest.mark.parametrize("changed", ["rating", "card", "revision", "timestamp"])
async def test_same_key_changed_intent(client: AsyncClient, app: FastAPI, changed: str) -> None:
    card_id = seed_card(app, "intent")
    other_id = seed_card(app, "other-intent")
    payload: dict[str, object] = {"rating": "GOOD", "source": "FLASHCARD"}
    first = await client.post(review_path(card_id), headers=headers(), json=payload)
    assert first.status_code == 201
    path = review_path(other_id if changed == "card" else card_id)
    if changed == "rating":
        payload["rating"] = "EASY"
    if changed == "timestamp":
        payload["clientOccurredAt"] = NOW.isoformat()
    response = await client.post(
        path, headers=headers(revision=1 if changed == "revision" else 0), json=payload
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert stored_state(app, card_id)[2:] == (1, 1)
    assert stored_state(app, other_id)[2:] == (0, 0)


@pytest.mark.anyio
async def test_stale_revision_is_durable_failure(client: AsyncClient, app: FastAPI) -> None:
    card_id = seed_card(app, "stale")
    payload = {"rating": "GOOD", "source": "FLASHCARD"}
    first = await client.post(review_path(card_id), headers=headers(), json=payload)
    assert first.status_code == 201
    response = await client.post(review_path(card_id), headers=headers("stale"), json=payload)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "REVISION_CONFLICT"
    ReviewErrorResponse.model_validate(response.json())
    replay = await client.post(review_path(card_id), headers=headers("stale"), json=payload)
    assert replay.status_code == 409
    assert replay.json()["error"]["code"] == "REVISION_CONFLICT"
    assert stored_state(app, card_id)[2:] == (1, 1)
    operation_id = response.json()["error"]["details"]["operationId"]
    operation = (await client.get(f"/api/v1/operations/{operation_id}")).json()
    assert operation["status"] == "FAILED"
    assert operation["errorCategory"] == "REVISION_CONFLICT"


@pytest.mark.anyio
@pytest.mark.parametrize("status", ["INVALID", "MISSING"])
async def test_invalid_deleted_source_retains_history_and_reactivation(
    client: AsyncClient, app: FastAPI, status: str
) -> None:
    card_id = seed_card(app, "history")
    payload = {"rating": "GOOD", "source": "FLASHCARD"}
    first = await client.post(review_path(card_id), headers=headers(), json=payload)
    assert first.status_code == 201
    before = stored_state(app, card_id)
    repository = VocabularyRepository(app.state.database.engine)
    repository.update_source_status("src_history", status)
    assert (await client.get(QUEUE, params={"dueOnly": "false"})).json()["data"] == []
    inactive = await client.post(review_path(card_id), headers=headers("inactive", 1), json=payload)
    assert inactive.status_code == 404
    assert inactive.json()["error"]["code"] == "NOT_FOUND"
    assert stored_state(app, card_id) == before
    repository.update_source_status("src_history", "VALID")
    assert (await client.get(QUEUE)).json()["data"] == []
    restored = (await client.get(QUEUE, params={"dueOnly": "false"})).json()["data"]
    assert [item["cardId"] for item in restored] == [card_id]
    assert restored[0]["queueRevision"] == 1
    assert stored_state(app, card_id) == before


@pytest.mark.anyio
async def test_offline_review_never_dispatches_ai(client: AsyncClient, app: FastAPI) -> None:
    card_id = seed_card(app, "offline")
    with patch("socket.socket.connect", side_effect=AssertionError("Network forbidden")):
        queue = await client.get(QUEUE)
        response = await client.post(
            review_path(card_id), headers=headers(), json={"rating": "GOOD", "source": "FLASHCARD"}
        )
    assert queue.status_code == 200 and response.status_code == 201
    assert app.state.active_ai_policy is None
    assert stored_state(app, card_id)[2:] == (1, 1)


@pytest.mark.anyio
@pytest.mark.parametrize("diagnostic", [False, True])
@pytest.mark.parametrize("same_key", [True, False])
async def test_concurrent_same_card_requests(
    client: AsyncClient, app: FastAPI, same_key: bool, diagnostic: bool
) -> None:
    card_id = seed_card(app, "race")
    payload = {"rating": "GOOD", "source": "FLASHCARD"}
    if diagnostic:
        payload["clientOccurredAt"] = "2026-09-29T17:20:30+07:00"
    responses = await asyncio.gather(
        *[
            client.post(
                review_path(card_id),
                headers=headers("race" if same_key else f"race-{i}"),
                json=payload,
            )
            for i in range(4)
        ]
    )
    assert any(response.status_code == 201 for response in responses)
    assert all(response.status_code in {201, 409} for response in responses)
    assert stored_state(app, card_id)[2:] == (1, 1)
    successes = [response.json() for response in responses if response.status_code == 201]
    assert all(body == successes[0] for body in successes)
    assert diagnostics(app) == (
        [(successes[0]["id"], "2026-09-29T10:20:30.000000Z")] if diagnostic else []
    )
    for response in responses:
        if response.status_code == 409:
            assert response.json()["error"]["code"] == (
                "IDEMPOTENCY_IN_FLIGHT" if same_key else "REVISION_CONFLICT"
            )


@pytest.mark.anyio
@pytest.mark.parametrize("diagnostic", [False, True])
async def test_restart_restores_committed_event_and_expires_cursor(
    client: AsyncClient, app: FastAPI, diagnostic: bool
) -> None:
    card_id = seed_card(app, "restart")
    seed_card(app, "extra")
    payload = {"rating": "GOOD", "source": "FLASHCARD"}
    if diagnostic:
        payload["clientOccurredAt"] = "2026-09-29T17:20:30+07:00"
    first = await client.post(review_path(card_id), headers=headers(), json=payload)
    assert first.status_code == 201
    cursor = (await client.get(QUEUE, params={"pageSize": 1, "dueOnly": "false"})).json()[
        "pagination"
    ]["nextCursor"]
    restarted = create_app(app.state.settings)
    async with (
        restarted.router.lifespan_context(restarted),
        AsyncClient(
            transport=ASGITransport(app=restarted), base_url=BASE, headers={"Origin": BASE}
        ) as http,
    ):
        restarted.state.review_service.clock = lambda: NOW + timedelta(days=2)
        token = restarted.state.sessions.issue_bootstrap_token()
        exchanged = await http.post("/bootstrap/exchange", json={"token": token})
        assert exchanged.status_code == 204
        http.headers["Cookie"] = exchanged.headers["set-cookie"].split(";", 1)[0]
        replay = await http.post(review_path(card_id), headers=headers(), json=payload)
        assert replay.status_code == 201 and replay.json() == first.json()
        assert stored_state(restarted, card_id)[2:] == (1, 1)
        assert diagnostics(restarted) == (
            [(first.json()["id"], "2026-09-29T10:20:30.000000Z")] if diagnostic else []
        )
        stale = await http.get(QUEUE, params={"cursor": cursor, "dueOnly": "false"})
        assert stale.status_code == 409
        assert stale.json()["error"]["code"] == "CURSOR_EXPIRED"


@pytest.mark.anyio
@pytest.mark.parametrize("diagnostic", [False, True])
async def test_lost_response_after_commit_is_replayable(
    client: AsyncClient, app: FastAPI, diagnostic: bool
) -> None:
    card_id = seed_card(app, "lost")
    payload = {"rating": "GOOD", "source": "FLASHCARD"}
    if diagnostic:
        payload["clientOccurredAt"] = "2026-09-29T10:20:30Z"
    completed = app.state.review_service.ledger.complete

    def lose_response(
        operation_id: str, *, response_status: int, result_ref: str,
        local_write: Callable[[Connection], None] | None = None,
    ) -> None:
        result = completed(
            operation_id, response_status=response_status, result_ref=result_ref,
            local_write=local_write,
        )
        assert result.status == "SUCCEEDED"
        raise SQLAlchemyError("private lost-response sentinel")

    with patch.object(app.state.review_service.ledger, "complete", side_effect=lose_response):
        lost = await client.post(review_path(card_id), headers=headers(), json=payload)
    assert lost.status_code == 503
    assert "private lost-response sentinel" not in lost.text
    operation_id = lost.json()["error"]["details"]["operationId"]
    operation = (await client.get(f"/api/v1/operations/{operation_id}")).json()
    assert operation["status"] == "SUCCEEDED"
    replay = await client.post(review_path(card_id), headers=headers(), json=payload)
    assert replay.status_code == 201 and replay.json()["operationId"] == operation_id
    assert stored_state(app, card_id)[2:] == (1, 1)
    assert diagnostics(app) == (
        [(replay.json()["id"], "2026-09-29T10:20:30.000000Z")] if diagnostic else []
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("stage", "diagnostic"),
    [
        (stage, diagnostic)
        for stage in ["event", "schedule", "receipt"]
        for diagnostic in [False, True]
    ] + [("diagnostic", True)],
)
async def test_storage_failure_rolls_back_the_entire_effect(
    client: AsyncClient, app: FastAPI, stage: str, diagnostic: bool
) -> None:
    card_id = seed_card(app, "rollback")
    payload = {"rating": "GOOD", "source": "FLASHCARD"}
    if diagnostic:
        payload["clientOccurredAt"] = "2026-09-29T10:20:30Z"
    engine = app.state.database.engine
    target = {
        "event": "INSERT INTO review_events",
        "schedule": "UPDATE review_cards SET box=",
        "diagnostic": "INSERT INTO review_event_diagnostics",
        "receipt": "UPDATE operations SET status='SUCCEEDED'",
    }[stage]

    def fail(
        _conn: object, _cursor: object, statement: str,
        _parameters: object, _context: object, _executemany: object,
    ) -> None:
        if statement.startswith(target):
            raise SQLAlchemyError("private storage sentinel")

    sqlalchemy_event.listen(engine, "before_cursor_execute", fail)
    try:
        response = await client.post(
            review_path(card_id), headers=headers(), json=payload
        )
    finally:
        sqlalchemy_event.remove(engine, "before_cursor_execute", fail)
    assert response.status_code == 503
    assert "private storage sentinel" not in response.text
    assert stored_state(app, card_id) == (0, None, 0, 0)
    assert diagnostics(app) == []
    operation_id = response.json()["error"]["details"]["operationId"]
    operation = (await client.get(f"/api/v1/operations/{operation_id}")).json()
    assert operation["status"] == "UNKNOWN"
    with engine.connect() as conn:
        assert conn.exec_driver_sql(
            "SELECT result_ref,response_status FROM operations WHERE operation_id=?",
            (operation_id,),
        ).one() == (None, 503)
    retry = await client.post(
        review_path(card_id), headers=headers(), json=payload
    )
    assert retry.status_code == 409
    assert retry.json()["error"]["code"] == "IDEMPOTENCY_IN_FLIGHT"
    assert stored_state(app, card_id) == (0, None, 0, 0)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "timestamp",
    [
        "not-a-timestamp", "2026-09-29T10:20:30", "2026-02-30T10:20:30Z",
        "2026-09-29T10:20:31Z", "2026-09-29T02:20:29Z", 0, True,
        "2026-09-29T02:20:29.999999Z", "2026-09-29T10:20:30.000001Z",
        "2026-09-29T09:20:30.1234567Z", "2026-09-29T10:20:30+24:00",
        "0001-01-01T00:00:00+07:00", "2026-09-29T10:20:30+0700",
        "2026-09-29T11:20:30+00:60",
    ],
)
async def test_invalid_diagnostic_time_never_changes_schedule(
    client: AsyncClient, app: FastAPI, timestamp: object
) -> None:
    card_id = seed_card(app, "time")
    response = await client.post(
        review_path(card_id), headers=headers(),
        json={"rating": "GOOD", "source": "FLASHCARD", "clientOccurredAt": timestamp},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert stored_state(app, card_id) == (0, None, 0, 0)
    assert diagnostics(app) == []
    if isinstance(timestamp, str):
        assert timestamp not in response.text
    ReviewErrorResponse.model_validate(response.json())
    with app.state.database.engine.connect() as conn:
        assert conn.exec_driver_sql(
            "SELECT count(*) FROM operations WHERE status='SUCCEEDED'"
        ).scalar_one() == 0


@pytest.mark.anyio
@pytest.mark.parametrize(
    "payload",
    [
        {"rating": "good", "source": "FLASHCARD"},
        {"rating": 1, "source": "FLASHCARD"},
        {"rating": "GOOD", "source": "AI"},
        {"rating": "GOOD", "source": "QUIZ"},
        {"rating": "GOOD", "source": "FLASHCARD", "attemptId": "foreign"},
        {"rating": "GOOD", "source": "FLASHCARD", "answer": "private sentinel"},
    ],
)
async def test_invalid_payload_is_safe_before_claim(
    client: AsyncClient, app: FastAPI, payload: dict[str, object]
) -> None:
    card_id = seed_card(app, "payload")
    response = await client.post(review_path(card_id), headers=headers(), json=payload)
    assert response.status_code == 422
    assert "private sentinel" not in response.text
    assert stored_state(app, card_id) == (0, None, 0, 0)
    with app.state.database.engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT count(*) FROM operation_keys").scalar_one() == 0


@pytest.mark.anyio
@pytest.mark.parametrize("revision", [None, "*", "-1", "1.0", 'W/"0"', "9223372036854775808"])
async def test_revision_precondition_is_required_and_numeric(
    client: AsyncClient, app: FastAPI, revision: str | None
) -> None:
    card_id = seed_card(app, "precondition")
    request_headers = {"Idempotency-Key": "review"}
    if revision is not None:
        request_headers["If-Match"] = revision
    response = await client.post(
        review_path(card_id), headers=request_headers, json={"rating": "GOOD", "source": "FLASHCARD"}
    )
    assert response.status_code == 422
    assert stored_state(app, card_id) == (0, None, 0, 0)


@pytest.mark.anyio
async def test_quiz_cross_resource_refusal(client: AsyncClient, app: FastAPI) -> None:
    card_id = seed_card(app, "quiz-mismatch")
    response = await client.post(
        review_path(card_id), headers=headers(),
        json={"rating": "GOOD", "source": "QUIZ", "attemptId": "absent", "questionId": "absent"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "CROSS_RESOURCE_MISMATCH"
    assert stored_state(app, card_id) == (0, None, 0, 0)


@pytest.mark.anyio
async def test_malformed_body_and_session_origin_guards(app: FastAPI) -> None:
    card_id = seed_card(app, "guards")
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as http:
        anonymous = await http.get(QUEUE)
        assert anonymous.status_code == 401
        denied = await http.post(
            review_path(card_id), headers=headers() | {"Origin": BASE},
            json={"rating": "GOOD", "source": "FLASHCARD"},
        )
        assert denied.status_code == 401
        token = app.state.sessions.issue_bootstrap_token()
        exchanged = await http.post(
            "/bootstrap/exchange", headers={"Origin": BASE}, json={"token": token}
        )
        cookie = exchanged.headers["set-cookie"].split(";", 1)[0]
        hostile = await http.post(
            review_path(card_id),
            headers=headers() | {"Cookie": cookie, "Origin": "http://hostile.invalid"},
            json={"rating": "GOOD", "source": "FLASHCARD"},
        )
        assert hostile.status_code == 403
        malformed = await http.post(
            review_path(card_id), content='{"rating":',
            headers=headers() | {
                "Cookie": cookie, "Origin": BASE, "Content-Type": "application/json"
            },
        )
        assert malformed.status_code == 400
        assert malformed.json()["error"]["code"] == "MALFORMED_JSON"
    assert stored_state(app, card_id) == (0, None, 0, 0)


@pytest.mark.anyio
async def test_cursor_rejects_search_and_noncanonical_signature(
    client: AsyncClient, app: FastAPI
) -> None:
    seed_card(app, "a")
    seed_card(app, "b")
    first = await client.get(QUEUE, params={"pageSize": 1})
    cursor = first.json()["pagination"]["nextCursor"]
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    changed = cursor[:-1] + alphabet[alphabet.index(cursor[-1]) ^ 1]
    assert base64.urlsafe_b64decode(changed.split(".")[1] + "=") == base64.urlsafe_b64decode(
        cursor.split(".")[1] + "="
    )
    assert (await client.get(QUEUE, params={"cursor": changed})).status_code == 409
    search = await client.get("/api/v1/word-forms", params={"pageSize": 1})
    search_cursor = search.json()["pagination"]["nextCursor"]
    assert search_cursor
    assert (await client.get(QUEUE, params={"cursor": search_cursor})).status_code == 409
    app.state.review_service = ReviewService(
        app.state.database.engine, signing_key=b"r" * 32,
        ledger=app.state.operation_ledger, conflict_type=OperationConflict,
    )
    assert (await client.get(QUEUE, params={"cursor": cursor})).status_code == 409


@pytest.mark.anyio
async def test_valid_alternate_source_does_not_activate_invalid_date(
    client: AsyncClient, app: FastAPI
) -> None:
    seed_card(app, "shared")
    seed_card(app, "alternate", note_date="2026-09-30")
    repository = VocabularyRepository(app.state.database.engine)
    repository.link_word_form_to_source("wf_shared", "src_alternate", "2026-09-30")
    repository.update_source_status("src_shared", "INVALID", "PARSE_FAILED")
    selected = (await client.get(QUEUE, params={"noteDate": "2026-09-29"})).json()["data"]
    assert selected == []
    shared = [
        item for item in (await client.get(QUEUE)).json()["data"]
        if item["cardId"] == "card_shared"
    ]
    assert len(shared) == 1
    assert shared[0]["noteDates"] == ["2026-09-30"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("reviewed_at", "expected_due"),
    [("2026-09-29T16:59:59Z", "2026-10-01T17:00:00Z"),
     ("2026-09-29T17:00:00Z", "2026-10-02T17:00:00Z")],
)
async def test_review_server_calendar_boundary(
    client: AsyncClient, app: FastAPI, reviewed_at: str, expected_due: str
) -> None:
    card_id = seed_card(app, "midnight", box=1, due_at=NOW)
    app.state.review_service.clock = lambda: datetime.fromisoformat(reviewed_at)
    response = await client.post(
        review_path(card_id), headers=headers(), json={"rating": "GOOD", "source": "FLASHCARD"}
    )
    assert response.status_code == 201
    assert datetime.fromisoformat(response.json()["nextDueAt"]) == datetime.fromisoformat(expected_due)
    assert stored_state(app, card_id) == (2, response.json()["nextDueAt"], 1, 1)


@pytest.mark.anyio
async def test_pending_restart_is_unknown_without_a_review(client: AsyncClient, app: FastAPI) -> None:
    card_id = seed_card(app, "pending")
    payload = {"rating": "GOOD", "source": "FLASHCARD"}
    claim = app.state.operation_ledger.claim(
        kind="REVIEW", key="pending", method="POST", path=review_path(card_id),
        body=payload | {"clientOccurredAt": None, "attemptId": None, "questionId": None},
        preconditions={"queueRevision": 0},
    )
    # This is the exact recovery primitive called by the production lifespan.
    assert app.state.operation_ledger.recover_pending() == 1
    operation = (await client.get(f"/api/v1/operations/{claim.operation.operation_id}")).json()
    assert operation["status"] == "UNKNOWN"
    response = await client.post(review_path(card_id), headers=headers("pending"), json=payload)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "IDEMPOTENCY_IN_FLIGHT"
    assert stored_state(app, card_id) == (0, None, 0, 0)


@pytest.mark.anyio
async def test_succeeded_receipt_without_event_is_not_success(
    client: AsyncClient, app: FastAPI
) -> None:
    card_id = seed_card(app, "missing-event")
    payload = {"rating": "GOOD", "source": "FLASHCARD"}
    claim = app.state.operation_ledger.claim(
        kind="REVIEW", key="receipt", method="POST", path=review_path(card_id),
        body=payload | {"clientOccurredAt": None, "attemptId": None, "questionId": None},
        preconditions={"queueRevision": 0},
    )
    app.state.operation_ledger.complete(
        claim.operation.operation_id, response_status=201, result_ref="review_absent",
    )
    response = await client.post(review_path(card_id), headers=headers("receipt"), json=payload)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "IDEMPOTENCY_IN_FLIGHT"
    assert stored_state(app, card_id) == (0, None, 0, 0)


@pytest.mark.anyio
async def test_storage_read_and_claim_failures_are_safe(client: AsyncClient, app: FastAPI) -> None:
    card_id = seed_card(app, "storage")
    with patch.object(app.state.review_service, "queue", side_effect=SQLAlchemyError("private sql")):
        response = await client.get(QUEUE)
    assert response.status_code == 503
    ReviewErrorResponse.model_validate(response.json())
    assert "private sql" not in response.text
    with patch.object(
        app.state.review_service.ledger, "claim", side_effect=SQLAlchemyError("private sql")
    ):
        response = await client.post(
            review_path(card_id), headers=headers(), json={"rating": "GOOD", "source": "FLASHCARD"}
        )
    assert response.status_code == 503
    assert "private sql" not in response.text
    assert stored_state(app, card_id) == (0, None, 0, 0)


@pytest.mark.anyio
@pytest.mark.parametrize("state", ["NEW", "LEARNED"])
async def test_card_state_filter(client: AsyncClient, app: FastAPI, state: str) -> None:
    seed_card(app, "new")
    seed_card(app, "learned", box=1, due_at=NOW)
    response = await client.get(QUEUE, params={"cardState": state})
    assert response.status_code == 200
    assert [item["state"] for item in response.json()["data"]] == [state]


@pytest.mark.anyio
async def test_duplicate_query_and_mutation_headers_are_rejected(
    client: AsyncClient, app: FastAPI
) -> None:
    card_id = seed_card(app, "duplicates")
    response = await client.get(QUEUE + "?dueOnly=true&dueOnly=false")
    assert response.status_code == 400
    response = await client.post(
        review_path(card_id),
        headers=[("Idempotency-Key", "one"), ("Idempotency-Key", "two"), ("If-Match", "0")],
        json={"rating": "GOOD", "source": "FLASHCARD"},
    )
    assert response.status_code == 422
    assert stored_state(app, card_id) == (0, None, 0, 0)


@pytest.mark.anyio
@pytest.mark.parametrize("diagnostic", [False, True])
async def test_quiz_provenance_is_bound_to_attempt_question_and_card(
    client: AsyncClient, app: FastAPI, diagnostic: bool
) -> None:
    for i in range(5):
        seed_card(app, f"quiz_{i}")
    questions = QuestionSet(questions=tuple(
        ClozeSnapshot(
            id=f"question_{i}", type="CLOZE", word_form_id=f"wf_quiz_{i}",
            prompt_en="A synthetic ___ example.", answer_policy_version="cloze-answer-v1",
            accepted_answers=("synthetic",), explanation_vi="Giải thích thử nghiệm",
        ) for i in range(5)
    ))
    with (
        app.state.database.engine.connect().execution_options(sqlite_begin_immediate=True) as conn,
        conn.begin(),
    ):
        create_attempt(
            conn, attempt_id="attempt_fixture", note_date="2026-09-29",
            questions=questions, created_at=NOW,
        )
    payload = {
        "source": "QUIZ", "rating": "GOOD", "attemptId": "attempt_fixture",
        "questionId": "question_0",
    }
    if diagnostic:
        payload["clientOccurredAt"] = "2026-09-29T10:20:30Z"
    wrong = await client.post(review_path("card_quiz_1"), headers=headers("wrong-card"), json=payload)
    assert wrong.status_code == 422
    assert wrong.json()["error"]["code"] == "CROSS_RESOURCE_MISMATCH"
    assert stored_state(app, "card_quiz_1") == (0, None, 0, 0)
    assert diagnostics(app) == []
    response = await client.post(review_path("card_quiz_0"), headers=headers(), json=payload)
    assert response.status_code == 201
    assert response.json()["attemptId"] == "attempt_fixture"
    assert response.json()["questionId"] == "question_0"
    assert stored_state(app, "card_quiz_0")[2:] == (1, 1)
    replay = await client.post(review_path("card_quiz_0"), headers=headers(), json=payload)
    assert replay.status_code == 201 and replay.json() == response.json()
    assert diagnostics(app) == (
        [(response.json()["id"], "2026-09-29T10:20:30.000000Z")] if diagnostic else []
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("timestamp", "normalized"),
    [
        ("2026-09-29T10:20:30Z", "2026-09-29T10:20:30.000000Z"),
        ("2026-09-29T02:20:30Z", "2026-09-29T02:20:30.000000Z"),
        ("2026-09-29T17:20:30+07:00", "2026-09-29T10:20:30.000000Z"),
        ("2026-09-29t10:20:30.0000000z", "2026-09-29T10:20:30.000000Z"),
        ("2026-09-29T09:20:30.123456Z", "2026-09-29T09:20:30.123456Z"),
        ("2026-09-29T00:20:30-02:00", "2026-09-29T02:20:30.000000Z"),
    ],
)
async def test_accepted_diagnostic_is_linked_normalized_and_server_scheduled(
    client: AsyncClient, app: FastAPI, timestamp: str, normalized: str
) -> None:
    card_id = seed_card(app, "retention")
    response = await client.post(
        review_path(card_id), headers=headers(),
        json={"rating": "GOOD", "source": "FLASHCARD", "clientOccurredAt": timestamp},
    )
    assert response.status_code == 201
    result = response.json()
    assert diagnostics(app) == [(result["id"], normalized)]
    assert datetime.fromisoformat(result["reviewedAt"]) == NOW
    expected = transition(0, "GOOD", NOW)
    assert datetime.fromisoformat(result["nextDueAt"]) == expected.due_at
    assert stored_state(app, card_id) == (expected.box, result["nextDueAt"], 1, 1)
    with app.state.database.engine.connect() as conn:
        linked = conn.exec_driver_sql(
            "SELECT e.id,e.card_id,e.operation_id,d.client_occurred_at,o.status,o.result_ref "
            "FROM review_event_diagnostics d JOIN review_events e ON e.id=d.event_id "
            "JOIN operations o ON o.operation_id=e.operation_id"
        ).one()
        assert linked == (
            result["id"], card_id, result["operationId"], normalized, "SUCCEEDED", result["id"],
        )


def diagnostics(app: FastAPI) -> list[tuple[str, str]]:
    with app.state.database.engine.connect() as conn:
        rows = conn.exec_driver_sql(
            "SELECT event_id,client_occurred_at FROM review_event_diagnostics ORDER BY event_id"
        ).all()
        return [(row[0], row[1]) for row in rows]


@pytest.mark.anyio
@pytest.mark.parametrize("explicit_null", [False, True])
async def test_missing_or_null_diagnostic_preserves_review_without_extra_row(
    client: AsyncClient, app: FastAPI, explicit_null: bool
) -> None:
    card_id = seed_card(app, "no_diagnostic")
    payload: dict[str, object] = {"rating": "GOOD", "source": "FLASHCARD"}
    if explicit_null:
        payload["clientOccurredAt"] = None
    response = await client.post(review_path(card_id), headers=headers(), json=payload)
    assert response.status_code == 201
    assert stored_state(app, card_id)[2:] == (1, 1)
    assert diagnostics(app) == []
    replay = await client.post(review_path(card_id), headers=headers(), json=payload)
    assert replay.status_code == 201 and replay.json() == response.json()
    assert stored_state(app, card_id)[2:] == (1, 1)
    assert diagnostics(app) == []


@pytest.mark.anyio
async def test_historical_diagnostic_replay_precedes_mutable_preconditions(
    client: AsyncClient, app: FastAPI
) -> None:
    card_id = seed_card(app, "historical_diagnostic")
    payload = {
        "rating": "GOOD", "source": "FLASHCARD", "clientOccurredAt": "2026-09-29T17:20:30+07:00",
    }
    first = await client.post(review_path(card_id), headers=headers(), json=payload)
    assert first.status_code == 201
    replay = await client.post(review_path(card_id), headers=headers(), json=payload)
    assert replay.status_code == 201 and replay.json() == first.json()
    later = await client.post(
        review_path(card_id), headers=headers("later", 1),
        json={"rating": "EASY", "source": "FLASHCARD"},
    )
    assert later.status_code == 201
    retained_state = stored_state(app, card_id)
    with app.state.database.engine.begin() as conn:
        conn.exec_driver_sql("UPDATE source_files SET status='MISSING'")
    app.state.review_service.clock = lambda: NOW + timedelta(days=2)
    historical = await client.post(review_path(card_id), headers=headers(), json=payload)
    assert historical.status_code == 201 and historical.json() == first.json()
    assert stored_state(app, card_id) == retained_state
    assert diagnostics(app) == [(first.json()["id"], "2026-09-29T10:20:30.000000Z")]
    assert (await client.get(QUEUE, params={"dueOnly": "false"})).json()["data"] == []
    fresh = await client.post(review_path(card_id), headers=headers("fresh", 2), json=payload)
    assert fresh.status_code == 422
    assert fresh.json()["error"]["code"] == "VALIDATION_ERROR"
    changed = await client.post(
        review_path(card_id), headers=headers(),
        json={**payload, "clientOccurredAt": "2026-09-29T10:20:30Z"},
    )
    assert changed.status_code == 422
    assert changed.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert stored_state(app, card_id) == retained_state
    assert diagnostics(app) == [(first.json()["id"], "2026-09-29T10:20:30.000000Z")]


@pytest.mark.anyio
async def test_diagnostic_review_remains_local_and_uses_server_learning_day(
    client: AsyncClient, app: FastAPI
) -> None:
    card_id = seed_card(app, "local_diagnostic")
    server_now = datetime(2026, 9, 29, 17, 0, tzinfo=UTC)
    app.state.review_service.clock = lambda: server_now
    with patch("socket.socket.connect", side_effect=AssertionError("Network forbidden")):
        response = await client.post(
            review_path(card_id), headers=headers(),
            json={
                "rating": "GOOD", "source": "FLASHCARD",
                "clientOccurredAt": "2026-09-29T16:59:59Z",
            },
        )
    assert response.status_code == 201
    result = response.json()
    assert result["reviewedAt"] == "2026-09-29T17:00:00.000000Z"
    assert result["nextDueAt"] == "2026-09-30T17:00:00.000000Z"
    assert stored_state(app, card_id) == (1, result["nextDueAt"], 1, 1)
    assert diagnostics(app) == [(result["id"], "2026-09-29T16:59:59.000000Z")]
    assert app.state.active_ai_policy is None


@pytest.mark.anyio
@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE review_event_diagnostics SET client_occurred_at='2026-09-29T09:00:00.000000Z'",
        "DELETE FROM review_event_diagnostics",
        "INSERT OR REPLACE INTO review_event_diagnostics SELECT * FROM review_event_diagnostics",
        "INSERT INTO review_event_diagnostics SELECT * FROM review_event_diagnostics "
        "WHERE 1 ON CONFLICT(event_id) DO UPDATE SET client_occurred_at=excluded.client_occurred_at",
    ],
)
async def test_diagnostics_are_append_only_even_without_recursive_triggers(
    client: AsyncClient, app: FastAPI, statement: str
) -> None:
    card_id = seed_card(app, "immutable_diagnostic")
    response = await client.post(
        review_path(card_id), headers=headers(),
        json={"rating": "GOOD", "source": "FLASHCARD", "clientOccurredAt": "2026-09-29T10:20:30Z"},
    )
    assert response.status_code == 201
    before = stored_state(app, card_id)
    retained = diagnostics(app)
    with (
        pytest.raises(IntegrityError, match="Append-only review diagnostics"),
        app.state.database.engine.begin() as conn,
    ):
        conn.exec_driver_sql("PRAGMA recursive_triggers=OFF")
        conn.exec_driver_sql(statement)
    assert diagnostics(app) == retained
    assert stored_state(app, card_id) == before
    replay = await client.post(
        review_path(card_id), headers=headers(),
        json={"rating": "GOOD", "source": "FLASHCARD", "clientOccurredAt": "2026-09-29T10:20:30Z"},
    )
    assert replay.status_code == 201 and replay.json() == response.json()


@pytest.mark.anyio
async def test_diagnostic_foreign_key_and_utc_constraints_preserve_history(
    client: AsyncClient, app: FastAPI
) -> None:
    card_id = seed_card(app, "constraints")
    response = await client.post(
        review_path(card_id), headers=headers(), json={"rating": "GOOD", "source": "FLASHCARD"},
    )
    assert response.status_code == 201
    before = stored_state(app, card_id)
    for event_id, timestamp in [
        ("nonexistent_event", "2026-09-29T10:20:30.000000Z"),
        (response.json()["id"], "2026-09-29T17:20:30+07:00"),
        (response.json()["id"], "not-a-timestamp"),
    ]:
        with pytest.raises(IntegrityError), app.state.database.engine.begin() as conn:
            conn.exec_driver_sql(
                "INSERT INTO review_event_diagnostics(event_id,client_occurred_at) VALUES (?,?)",
                (event_id, timestamp),
            )
    assert diagnostics(app) == []
    assert stored_state(app, card_id) == before
    with app.state.database.engine.connect() as conn:
        assert conn.exec_driver_sql("PRAGMA foreign_key_check").all() == []


@pytest.mark.anyio
async def test_database_diagnostic_rejection_rolls_back_review_and_receipt(
    client: AsyncClient, app: FastAPI
) -> None:
    card_id = seed_card(app, "database_failure")
    with app.state.database.engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TRIGGER synthetic_diagnostic_failure BEFORE INSERT "
            "ON review_event_diagnostics "
            "BEGIN SELECT RAISE(ABORT, 'private diagnostic failure'); END"
        )
    payload = {
        "rating": "GOOD", "source": "FLASHCARD", "clientOccurredAt": "2026-09-29T10:20:30Z",
    }
    response = await client.post(review_path(card_id), headers=headers(), json=payload)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "STORAGE_BUSY"
    assert "private diagnostic failure" not in response.text
    assert payload["clientOccurredAt"] not in response.text
    ReviewErrorResponse.model_validate(response.json())
    assert stored_state(app, card_id) == (0, None, 0, 0)
    assert diagnostics(app) == []
    with app.state.database.engine.begin() as conn:
        assert conn.exec_driver_sql(
            "SELECT status,result_ref,response_status FROM operations"
        ).one() == ("UNKNOWN", None, 503)
        conn.exec_driver_sql("DROP TRIGGER synthetic_diagnostic_failure")
    retry = await client.post(review_path(card_id), headers=headers(), json=payload)
    assert retry.status_code == 409
    assert retry.json()["error"]["code"] == "IDEMPOTENCY_IN_FLIGHT"
    assert stored_state(app, card_id) == (0, None, 0, 0)
    assert diagnostics(app) == []


@pytest.mark.anyio
async def test_terminal_receipt_without_required_diagnostic_is_not_success_evidence(
    client: AsyncClient, app: FastAPI
) -> None:
    card_id = seed_card(app, "missing_evidence")
    ledger = app.state.review_service.ledger
    payload = {
        "rating": "GOOD", "source": "FLASHCARD", "clientOccurredAt": "2026-09-29T10:20:30Z",
    }
    intent = ledger.claim(
        kind="REVIEW", key="missing-evidence", method="POST", path=review_path(card_id),
        body={**payload, "attemptId": None, "questionId": None},
        preconditions={"queueRevision": 0},
    )

    def incomplete_write(conn: Connection) -> None:
        record_review(
            conn, card_id=card_id, event_id="event_missing_evidence",
            operation_id=intent.operation.operation_id,
            rating="GOOD", source="FLASHCARD", reviewed_at=NOW,
        )

    ledger.complete(
        intent.operation.operation_id, response_status=201, result_ref="event_missing_evidence",
        local_write=incomplete_write,
    )
    before = stored_state(app, card_id)
    response = await client.post(
        review_path(card_id), headers=headers("missing-evidence"), json=payload,
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "IDEMPOTENCY_IN_FLIGHT"
    assert stored_state(app, card_id) == before
    assert diagnostics(app) == []


@pytest.mark.anyio
async def test_0009_upgrade_preserves_historical_reviews_and_refuses_destructive_downgrade(
    tmp_path: Path,
) -> None:
    config = migration_config()
    scripts = ScriptDirectory.from_config(config)
    assert scripts.get_heads() == ["0009_review_diagnostics"]
    revision = scripts.get_revision("0009_review_diagnostics")
    assert revision is not None and revision.down_revision == "0008_quiz"
    database = Database(tmp_path / "prior_review.db")

    def prior_schema(conn: Connection) -> None:
        config.attributes["connection"] = conn
        command.upgrade(config, "0008_quiz")

    try:
        database.initialize(migrate=prior_schema)
        # The ordinary synthetic fixture uses the actual vocabulary and card primitives.
        old_app = FastAPI()
        old_app.state.database = database
        card_id = seed_card(old_app, "prior")
        ledger = OperationLedger(database.engine)
        intent = ledger.claim(
            kind="REVIEW", key="prior-history", method="POST", path=review_path(card_id),
            body={
                "rating": "GOOD", "source": "FLASHCARD", "clientOccurredAt": None,
                "attemptId": None, "questionId": None,
            },
            preconditions={"queueRevision": 0},
        )

        def old_review(conn: Connection) -> None:
            record_review(
                conn, card_id=card_id, event_id="prior_event",
                operation_id=intent.operation.operation_id,
                rating="GOOD", source="FLASHCARD", reviewed_at=NOW,
            )

        ledger.complete(
            intent.operation.operation_id, response_status=201, result_ref="prior_event",
            local_write=old_review,
        )
        tables = ("review_cards", "review_events", "operations", "operation_keys")
        with database.engine.connect() as conn:
            assert conn.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one() == (
                "0008_quiz"
            )
            before = {
                table: conn.exec_driver_sql(f"SELECT * FROM {table}").all() for table in tables
            }
        database.close()
        # Startup performs the migration against a real installation with history.
        restarted = create_app(AppSettings(storage_path=tmp_path / "prior_review.db"))
        async with restarted.router.lifespan_context(restarted):
            assert diagnostics(restarted) == []  # No fabricated backfill.
            assert stored_state(restarted, card_id)[2:] == (1, 1)
            async with AsyncClient(
                transport=ASGITransport(app=restarted), base_url=BASE, headers={"Origin": BASE},
            ) as http:
                token = restarted.state.sessions.issue_bootstrap_token()
                exchanged = await http.post("/bootstrap/exchange", json={"token": token})
                assert exchanged.status_code == 204
                http.headers["Cookie"] = exchanged.headers["set-cookie"].split(";", 1)[0]
                historical = await http.post(
                    review_path(card_id), headers=headers("prior-history"),
                    json={"rating": "GOOD", "source": "FLASHCARD"},
                )
                assert historical.status_code == 201
                assert historical.json()["id"] == "prior_event"
                assert historical.json()["operationId"] == intent.operation.operation_id
                assert diagnostics(restarted) == []
            engine = restarted.state.database.engine
            with engine.connect() as conn:
                for table in tables:
                    assert conn.exec_driver_sql(f"SELECT * FROM {table}").all() == before[table]
                assert conn.exec_driver_sql("PRAGMA foreign_key_check").all() == []
            assert restarted.state.database.initialize().schema_revision == "0009_review_diagnostics"
            with engine.begin() as conn:
                conn.exec_driver_sql(
                    "INSERT INTO review_event_diagnostics(event_id,client_occurred_at) VALUES (?,?)",
                    ("prior_event", "2026-09-29T10:20:30.000000Z"),
                )
            with (
                pytest.raises(RuntimeError, match="preserve review diagnostic history"),
                engine.begin() as conn,
            ):
                config.attributes["connection"] = conn
                command.downgrade(config, "0008_quiz")
            assert diagnostics(restarted) == [("prior_event", "2026-09-29T10:20:30.000000Z")]
            with engine.connect() as conn:
                assert conn.exec_driver_sql(
                    "SELECT version_num FROM alembic_version"
                ).scalar_one() == "0009_review_diagnostics"
                for table in tables:
                    assert conn.exec_driver_sql(f"SELECT * FROM {table}").all() == before[table]
    finally:
        database.close()


@pytest.mark.anyio
async def test_submicrosecond_future_diagnostic_is_rejected(
    client: AsyncClient, app: FastAPI
) -> None:
    card_id = seed_card(app, "fraction")
    response = await client.post(
        review_path(card_id), headers=headers(),
        json={
            "rating": "GOOD", "source": "FLASHCARD",
            "clientOccurredAt": "2026-09-29T10:20:30.0000001Z",
        },
    )
    assert response.status_code == 422
    assert stored_state(app, card_id) == (0, None, 0, 0)


@pytest.mark.anyio
async def test_reset_invalidates_cursor_and_stale_card_without_deleting_history(
    client: AsyncClient, app: FastAPI
) -> None:
    card_id = seed_card(app, "reset")
    seed_card(app, "extra")
    payload = {"rating": "GOOD", "source": "FLASHCARD"}
    first = await client.post(review_path(card_id), headers=headers(), json=payload)
    assert first.status_code == 201
    cursor = (await client.get(QUEUE, params={"pageSize": 1, "dueOnly": "false"})).json()[
        "pagination"
    ]["nextCursor"]
    with (
        app.state.database.engine.connect().execution_options(sqlite_begin_immediate=True) as conn,
        conn.begin(),
    ):
        reset_card_state(conn, card_id)
    assert stored_state(app, card_id) == (0, None, 2, 1)
    stale = await client.get(QUEUE, params={"cursor": cursor, "dueOnly": "false"})
    assert stale.status_code == 409
    stale_rating = await client.post(
        review_path(card_id), headers=headers("stale-reset", 1), json=payload
    )
    assert stale_rating.status_code == 409
    assert stale_rating.json()["error"]["code"] == "REVISION_CONFLICT"
    assert stored_state(app, card_id) == (0, None, 2, 1)
    VocabularyRepository(app.state.database.engine).unlink_source_from_form("wf_reset", "src_reset")
    rows = (await client.get(QUEUE, params={"dueOnly": "false"})).json()["data"]
    assert [row["cardId"] for row in rows] == ["card_extra"]
    assert stored_state(app, card_id) == (0, None, 2, 1)


@pytest.mark.anyio
@pytest.mark.parametrize("key", [None, "", "x" * 129, "invalid\tkey"])
async def test_idempotency_header_shape_precedes_mutation(
    client: AsyncClient, app: FastAPI, key: str | None
) -> None:
    card_id = seed_card(app, "key")
    request_headers = {"If-Match": "0"}
    if key is not None:
        request_headers["Idempotency-Key"] = key
    response = await client.post(
        review_path(card_id), headers=request_headers, json={"rating": "GOOD", "source": "FLASHCARD"}
    )
    assert response.status_code == 422
    assert stored_state(app, card_id) == (0, None, 0, 0)


@pytest.mark.anyio
async def test_page_size_max_and_quoted_revision(client: AsyncClient, app: FastAPI) -> None:
    card_id = seed_card(app, "quoted")
    response = await client.get(QUEUE, params={"pageSize": 100})
    assert response.status_code == 200 and response.json()["pagination"]["pageSize"] == 100
    response = await client.post(
        review_path(card_id), headers={"Idempotency-Key": "quoted", "If-Match": '"0"'},
        json={"rating": "GOOD", "source": "FLASHCARD"},
    )
    assert response.status_code == 201
    assert stored_state(app, card_id)[2:] == (1, 1)

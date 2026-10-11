"""T049 synthetic provider and production-factory regression tests."""

import asyncio
import json
import socket
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.script import ScriptDirectory
from backend.app.application.feedback import parse_feedback
from backend.app.assessment.repository import save_answer, store_submission
from backend.app.main import create_app
from backend.app.persistence.database import Database, migration_config
from backend.app.platform.bridge_port import (
    BridgeAuthError,
    BridgeInvalidResponseError,
    BridgeUnavailableError,
)
from backend.app.platform.config import AppSettings
from backend.app.review.models import record_review
from backend.tests.test_quiz_answers import WRITING
from backend.tests.test_quiz_creation import FakeBridge, bootstrap, policy_fixture
from backend.tests.test_quiz_snapshot import NOW, create, operation, seed_sources, terminal_result
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.exc import OperationalError

BASE = "http://127.0.0.1:8000"
PATH = f"/api/v1/quiz-questions/{WRITING}/feedback"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def app_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[Any]:
    def forbidden(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("Feedback tests require fake transport")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    app = create_app(AppSettings(storage_path=tmp_path / "feedback.db"))
    policy = policy_fixture()
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client,
    ):
        seed_sources(app.state.database)
        create(app.state.database)
        app.state.active_ai_policy = policy
        snapshot = app.state.consent_service.read_consent(policy)
        app.state.consent_service.grant("grant", snapshot.etag, policy["version"], policy)
        bridge = FakeBridge()
        bridge.output = output()
        app.state.quiz_service.admission.bridge = bridge
        await bootstrap(app, client)
        attempt = (await client.get("/api/v1/quiz-attempts/attempt_a")).json()
        condition = next(p for p in attempt["answerPreconditions"] if p["questionId"] == WRITING)
        saved = await client.put(
            f"/api/v1/quiz-attempts/attempt_a/answers/{WRITING}",
            json={
                "answer": "The robust result was replicated.",
                "draftRevision": 0,
                "selfScore": 3,
            },
            headers={"If-Match": condition["etag"], "Idempotency-Key": "answer"},
        )
        assert saved.status_code == 200
        yield app, client, bridge


async def post(client: AsyncClient, key: str = "feedback", **fields: Any) -> Any:
    return await client.post(
        PATH,
        json={"rubricVersion": "writing-rubric-v1", "answerRevision": 1, **fields},
        headers={"Idempotency-Key": key},
    )


@pytest.mark.anyio
async def test_valid_feedback_and_durable_history(app_client: Any) -> None:
    app, client, bridge = app_client
    before = (await client.get("/api/v1/quiz-attempts/attempt_a")).json()
    result = await post(client)
    assert result.status_code == 201, result.text
    body = result.json()
    assert body["status"] == "VALIDATED" and body["answerRevision"] == 1
    assert body["summaryVi"] == output()["summaryVi"]
    assert body["criteria"] == output()["criteria"]
    assert (await client.get(PATH)).json()["data"] == [body]
    assert (await post(client)).json() == body
    assert bridge.dispatches == 1
    assert (await client.get("/api/v1/quiz-attempts/attempt_a")).json() == before
    with app.state.database.engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT count(*) FROM review_events").scalar_one() == 0
    payload = json.loads(bridge.payloads[0]["messages"][1]["content"])
    assert payload["answer"] == before["answers"][0]["answer"]
    assert "selfScore" not in payload


def test_migration_preserves_existing_learning_rows(tmp_path: Path) -> None:
    db = Database(tmp_path / "legacy.db")

    def predecessor(connection: Any) -> None:
        config = migration_config()
        config.attributes["connection"] = connection
        command.upgrade(config, "0010_quiz_answer_receipts")

    try:
        db.initialize(migrate=predecessor)
        seed_sources(db)
        create(db)
        with (
            db.engine.connect().execution_options(sqlite_begin_immediate=True) as conn,
            conn.begin(),
        ):
            operation(conn, "legacy-answer")
            save_answer(
                conn,
                attempt_id="attempt_a",
                question_id=WRITING,
                answer="A robust legacy result.",
                self_score=3,
                expected_draft_revision=0,
                operation_id="legacy-answer",
                saved_at=NOW,
            )
            operation(conn, "legacy-submit")
            operation(conn, "legacy-review")
            record_review(
                conn,
                card_id="card_0",
                rating="GOOD",
                source="FLASHCARD",
                reviewed_at=NOW,
                operation_id="legacy-review",
                event_id="legacy-review-event",
            )
            store_submission(conn, result=terminal_result(conn), operation_id="legacy-submit")
        tables = (
            "quiz_attempts",
            "quiz_questions",
            "quiz_answers",
            "quiz_answer_receipts",
            "review_cards",
            "review_events",
            "operations",
        )
        with db.engine.connect() as conn:
            before = {
                table: conn.exec_driver_sql(f"SELECT * FROM {table}").all() for table in tables
            }
        assert db.initialize().schema_revision == "0011_feedback"
        assert db.initialize().schema_revision == "0011_feedback"
        with db.engine.connect() as conn:
            assert {
                table: conn.exec_driver_sql(f"SELECT * FROM {table}").all() for table in tables
            } == before
            assert conn.exec_driver_sql("PRAGMA integrity_check").all() == [("ok",)]
            assert conn.exec_driver_sql("PRAGMA foreign_key_check").all() == []
        scripts = ScriptDirectory.from_config(migration_config())
        assert scripts.get_heads() == ["0011_feedback"]
        revision = scripts.get_revision("0011_feedback")
        assert revision is not None and revision.down_revision == "0010_quiz_answer_receipts"
    finally:
        db.close()


def output() -> dict[str, Any]:
    return {
        "summaryVi": "Câu rõ nghĩa.",
        "criteria": [
            {"criterion": criterion, "commentVi": "Nhận xét tổng hợp."}
            for criterion in ("TARGET_WORD_USAGE", "GRAMMAR", "CLARITY")
        ],
    }


def response(data: Any) -> dict[str, Any]:
    return {
        "model": "gemini-3.8-flash-high",
        "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(data)}}],
    }


def test_schema_accepts_only_advisory_comments() -> None:
    assert parse_feedback(response(output())).model_dump(by_alias=True) == output()


@pytest.mark.parametrize(
    "change",
    [
        {"summaryVi": ""},
        {"summaryVi": "x" * 4097},
        {"summaryVi": 3},
        {"summaryVi": "<script>bad</script>"},
        {"summaryVi": "\ud800"},
        {"score": 4},
        {"criteria": []},
        {"criteria": output()["criteria"][:2]},
        {"criteria": [output()["criteria"][0]] * 3},
        {"criteria": [{"criterion": "UNKNOWN", "commentVi": "comment"}] * 3},
        {"criteria": [{**item, "score": 4} for item in output()["criteria"]]},
    ],
)
def test_schema_rejects_untrusted_content(change: dict[str, Any]) -> None:
    with pytest.raises(BridgeInvalidResponseError):
        parse_feedback(response({**output(), **change}))


@pytest.mark.parametrize(
    "content",
    ["not json", "{}", '{"summaryVi":"a","summaryVi":"b"}', '{"summaryVi":NaN,"criteria":[]}'],
)
def test_schema_rejects_malformed_or_incomplete_json(content: str) -> None:
    data = response(output())
    data["choices"][0]["message"]["content"] = content
    with pytest.raises(BridgeInvalidResponseError):
        parse_feedback(data)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "failure,expected,status",
    [
        (BridgeAuthError("private-provider-body"), "BRIDGE_AUTH_ERROR", "FAILED"),
        (BridgeUnavailableError("Unexpected status: 429"), "BRIDGE_UNAVAILABLE", "UNKNOWN"),
        (BridgeUnavailableError("private-timeout-body"), "BRIDGE_UNAVAILABLE", "UNKNOWN"),
        (BridgeInvalidResponseError("private-response-body"), "BRIDGE_INVALID_RESPONSE", "FAILED"),
    ],
)
async def test_failures_persist_before_response_and_do_not_replay(
    app_client: Any,
    failure: Exception,
    expected: str,
    status: str,
    caplog: Any,
) -> None:
    _, client, bridge = app_client
    before = (await client.get("/api/v1/quiz-attempts/attempt_a")).json()
    bridge.failure = failure
    result = await post(client)
    assert result.status_code in {502, 503}
    assert result.json()["error"]["code"] == expected
    history = (await client.get(PATH)).json()["data"]
    assert len(history) == 1 and history[0]["status"] == "FAILED"
    assert history[0]["errorCategory"] == expected
    identity = history[0]["operationId"]
    assert (await client.get(f"/api/v1/operations/{identity}")).json()["status"] == status
    replay = await post(client)
    assert replay.status_code == (409 if status == "UNKNOWN" else result.status_code)
    assert bridge.dispatches == 1
    assert (await client.get("/api/v1/quiz-attempts/attempt_a")).json() == before
    assert "private-" not in caplog.text + result.text
    assert "The robust result" not in caplog.text


@pytest.mark.anyio
async def test_confirmed_failure_fresh_retry_and_query_bound_pagination(app_client: Any) -> None:
    _, client, bridge = app_client
    bridge.failure = BridgeAuthError("synthetic")
    assert (await post(client)).status_code == 502
    old = (await client.get(PATH)).json()["data"][0]
    bridge.failure = None
    retry = await post(client, "retry", retryOfOperationId=old["operationId"])
    assert retry.status_code == 201
    assert retry.json()["retryOfOperationId"] == old["operationId"]
    assert bridge.dispatches == 2
    assert (
        await post(client, "retry", retryOfOperationId=old["operationId"])
    ).json() == retry.json()
    assert (
        await post(client, "second-child", retryOfOperationId=old["operationId"])
    ).status_code == 409
    page = await client.get(
        PATH, params={"attemptId": "attempt_a", "questionId": WRITING, "pageSize": 1}
    )
    first = page.json()
    assert first["data"] == [old] and first["pagination"]["hasMore"]
    cursor = first["pagination"]["nextCursor"]
    second = (
        await client.get(
            PATH,
            params={
                "attemptId": "attempt_a",
                "questionId": WRITING,
                "pageSize": 1,
                "cursor": cursor,
            },
        )
    ).json()
    assert second["data"] == [retry.json()] and second["pagination"]["nextCursor"] is None
    assert (await client.get(PATH, params={"pageSize": 1, "cursor": cursor})).status_code == 409
    assert (await client.get(PATH, params={"cursor": "tampered"})).status_code == 409
    assert (await client.get(PATH, params={"attemptId": "foreign"})).status_code == 422
    assert (await client.get(PATH, params={"questionId": "foreign"})).status_code == 422


@pytest.mark.anyio
@pytest.mark.parametrize(
    "fields,code",
    [
        ({"answerRevision": 2}, "REVISION_CONFLICT"),
        ({"rubricVersion": "writing-rubric-v2"}, "VALIDATION_ERROR"),
        ({"answer": "arbitrary-client-answer"}, "VALIDATION_ERROR"),
        ({"retryOfOperationId": "foreign"}, "CROSS_RESOURCE_MISMATCH"),
        ({"answerRevision": True}, "VALIDATION_ERROR"),
    ],
)
async def test_invalid_requests_do_not_dispatch(app_client: Any, fields: Any, code: str) -> None:
    _, client, bridge = app_client
    result = await post(client, **fields)
    assert result.json()["error"]["code"] == code
    assert bridge.dispatches == bridge.preflights == 0


@pytest.mark.anyio
async def test_changed_intent_and_success_cannot_be_retried(app_client: Any) -> None:
    _, client, bridge = app_client
    succeeded = await post(client)
    assert succeeded.status_code == 201
    assert (await post(client, answerRevision=2)).json()["error"][
        "code"
    ] == "IDEMPOTENCY_KEY_REUSED"
    assert (
        await post(client, "retry", retryOfOperationId=succeeded.json()["operationId"])
    ).status_code == 409
    assert bridge.dispatches == 1


@pytest.mark.anyio
async def test_revocation_at_preflight_and_replay_after_revoke(app_client: Any) -> None:
    app, client, bridge = app_client
    first = await post(client)
    bridge.after_preflight = lambda: app.state.consent_service.revoke("revoke")
    refused = await post(client, "revoked")
    assert refused.status_code == 403
    assert refused.json()["error"]["details"]["kind"] == "AI_CONSENT"
    assert bridge.dispatches == 1
    assert (await post(client)).json() == first.json()
    assert (await client.get(PATH)).json()["data"][-1]["status"] == "FAILED"


@pytest.mark.anyio
async def test_policy_changed_before_retry_denies_dispatch(app_client: Any) -> None:
    app, client, bridge = app_client
    bridge.failure = BridgeAuthError("synthetic")
    await post(client)
    old = (await client.get(PATH)).json()["data"][0]
    app.state.active_ai_policy = {**policy_fixture(), "version": "new-policy"}
    bridge.failure = None
    result = await post(client, "retry", retryOfOperationId=old["operationId"])
    assert result.status_code == 403
    assert bridge.dispatches == 1


@pytest.mark.anyio
async def test_concurrent_same_key_and_same_retry_have_one_dispatch(app_client: Any) -> None:
    _, client, bridge = app_client
    bridge.entered, bridge.release = asyncio.Event(), asyncio.Event()
    owner = asyncio.create_task(post(client))
    await asyncio.wait_for(bridge.entered.wait(), 5)
    duplicate = await post(client)
    assert duplicate.status_code == 409
    assert (await post(client, "other-fresh-key")).status_code == 409
    bridge.release.set()
    assert (await owner).status_code == 201
    assert bridge.dispatches == 1


@pytest.mark.anyio
@pytest.mark.parametrize("late", [False, True])
async def test_deadline_boundary_has_no_late_success(app_client: Any, late: bool) -> None:
    app, client, bridge = app_client
    elapsed = [100.0]
    app.state.feedback_service.clock = lambda: elapsed[0]
    app.state.feedback_service.admission.clock = lambda: elapsed[0]
    bridge.after_dispatch = lambda: elapsed.__setitem__(0, 130.0 if late else 129.999)
    result = await post(client)
    assert result.status_code == (503 if late else 201)
    assert len(set(bridge.deadlines)) == 1 and bridge.deadlines[0] == 130.0
    history = (await client.get(PATH)).json()["data"][0]
    assert history["status"] == ("FAILED" if late else "VALIDATED")
    assert bridge.dispatches == 1


@pytest.mark.anyio
async def test_answer_changed_during_preflight_blocks_transport(app_client: Any) -> None:
    app, client, bridge = app_client

    def edit() -> None:
        from backend.app.application.save_answer import AnswerDraftRequest
        from backend.app.assessment.questions import answer_etag

        app.state.answer_service.save(
            attempt_id="attempt_a",
            question_id=WRITING,
            intent=AnswerDraftRequest(answer="Changed robust answer.", draft_revision=1),
            if_match=answer_etag("attempt_a", WRITING, 1),
            idempotency_key="changed-answer",
        )

    bridge.after_preflight = edit
    result = await post(client)
    assert result.status_code == 409
    assert bridge.dispatches == 0


@pytest.mark.anyio
async def test_storage_failure_never_acknowledges_success(app_client: Any) -> None:
    app, client, bridge = app_client

    def fail(_conn: Any, _cursor: Any, statement: str, *_args: Any) -> None:
        if statement.startswith("UPDATE writing_feedback SET status='VALIDATED'"):
            raise OperationalError("synthetic", None, RuntimeError("private-storage-sentinel"))

    event.listen(app.state.database.engine, "before_cursor_execute", fail)
    try:
        result = await post(client)
    finally:
        event.remove(app.state.database.engine, "before_cursor_execute", fail)
    assert result.status_code == 503 and "private-storage" not in result.text
    history = (await client.get(PATH)).json()["data"][0]
    assert history["status"] == "FAILED"
    assert bridge.dispatches == 1


@pytest.mark.anyio
async def test_security_and_nonwriting_boundary(app_client: Any) -> None:
    _, client, bridge = app_client
    assert (
        await client.post(PATH, json={"rubricVersion": "writing-rubric-v1", "answerRevision": 1})
    ).status_code == 422
    assert (
        await client.post(PATH, json={}, headers={"Origin": "https://foreign.invalid"})
    ).status_code == 403
    assert (
        await client.post(
            PATH.replace(WRITING, "q_MCQ_0"),
            json={"rubricVersion": "writing-rubric-v1", "answerRevision": 1},
            headers={"Idempotency-Key": "objective"},
        )
    ).status_code == 422
    assert (await client.get(PATH.replace(WRITING, "missing"))).status_code == 404
    assert bridge.dispatches == 0


@pytest.mark.anyio
@pytest.mark.parametrize("bad", ["not json", {}, {"summaryVi": "missing criteria"}])
async def test_malformed_provider_persists_only_redacted_failure(app_client: Any, bad: Any) -> None:
    _, client, bridge = app_client
    bridge.output = bad
    result = await post(client)
    assert result.status_code == 502
    history = (await client.get(PATH)).json()["data"][0]
    assert history["status"] == "FAILED"
    assert history["errorCategory"] == "BRIDGE_INVALID_RESPONSE"
    assert "summaryVi" not in history and "criteria" not in history


@pytest.mark.anyio
async def test_unknown_outcome_cannot_be_retried(app_client: Any) -> None:
    _, client, bridge = app_client
    bridge.failure = BridgeUnavailableError("synthetic disconnect")
    await post(client)
    old = (await client.get(PATH)).json()["data"][0]
    bridge.failure = None
    assert (
        await post(client, "unsafe-retry", retryOfOperationId=old["operationId"])
    ).status_code == 409
    assert (await post(client, "fresh-key-without-retry")).status_code == 409
    assert bridge.dispatches == 1


@pytest.mark.anyio
async def test_lost_response_reconciles_committed_success(
    app_client: Any, monkeypatch: Any
) -> None:
    app, client, bridge = app_client
    original = app.state.feedback_service.get

    def unavailable(_identity: str) -> Any:
        raise OperationalError("synthetic", None, RuntimeError("private-read-error"))

    monkeypatch.setattr(app.state.feedback_service, "get", unavailable)
    result = await post(client)
    assert result.status_code == 503
    monkeypatch.setattr(app.state.feedback_service, "get", original)
    history = (await client.get(PATH)).json()["data"][0]
    assert history["status"] == "VALIDATED"
    assert (await post(client)).json() == history
    assert (await client.get(f"/api/v1/operations/{history['operationId']}")).json()[
        "status"
    ] == "SUCCEEDED"
    assert bridge.dispatches == 1


@pytest.mark.anyio
async def test_restart_reads_success_and_recovers_requested_without_inference(
    app_client: Any,
) -> None:
    from backend.app.application.feedback import FeedbackRequest

    app, client, bridge = app_client
    first = (await post(client)).json()
    claim = app.state.operation_ledger.claim(
        kind="WRITING_FEEDBACK",
        key="interrupted",
        method="POST",
        path=PATH,
        body={"rubricVersion": "writing-rubric-v1", "answerRevision": 1},
        preconditions={},
    )
    app.state.feedback_service._requested(
        WRITING,
        FeedbackRequest.model_validate({"rubricVersion": "writing-rubric-v1", "answerRevision": 1}),
        claim.operation.operation_id,
    )
    restarted = create_app(app.state.settings)
    async with (
        restarted.router.lifespan_context(restarted),
        AsyncClient(transport=ASGITransport(app=restarted), base_url=BASE) as fresh,
    ):
        await bootstrap(restarted, fresh)
        history = (await fresh.get(PATH)).json()["data"]
        assert history[0] == first
        assert history[1]["status"] == "FAILED" and history[1]["errorCategory"] == "RESTARTED"
        assert (await fresh.get(f"/api/v1/operations/{claim.operation.operation_id}")).json()[
            "status"
        ] == "UNKNOWN"
        assert (await post(fresh)).json() == first
    assert bridge.dispatches == 1


@pytest.mark.anyio
async def test_cancellation_records_unknown_and_keeps_answer(app_client: Any) -> None:
    app, client, bridge = app_client
    bridge.entered, bridge.release = asyncio.Event(), asyncio.Event()
    task = asyncio.create_task(post(client))
    await asyncio.wait_for(bridge.entered.wait(), 5)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    await app.state.feedback_service.drain()
    history = (await client.get(PATH)).json()["data"][0]
    assert history["status"] == "FAILED" and history["errorCategory"] == "TIMEOUT"
    assert (await client.get(f"/api/v1/operations/{history['operationId']}")).json()[
        "status"
    ] == "UNKNOWN"
    assert bridge.dispatches == 1


@pytest.mark.anyio
async def test_submitted_result_and_review_history_are_unchanged(app_client: Any) -> None:
    app, client, _ = app_client
    with (
        app.state.database.engine.connect().execution_options(sqlite_begin_immediate=True) as conn,
        conn.begin(),
    ):
        operation(conn, "review-fixture")
        record_review(
            conn,
            card_id="card_0",
            rating="GOOD",
            source="FLASHCARD",
            reviewed_at=NOW,
            operation_id="review-fixture",
            event_id="review_fixture",
        )
        operation(conn, "submission-fixture")
        store_submission(conn, result=terminal_result(conn), operation_id="submission-fixture")
        before_cards = conn.exec_driver_sql("SELECT * FROM review_cards").all()
        before_events = conn.exec_driver_sql("SELECT * FROM review_events").all()
    before = (await client.get("/api/v1/quiz-attempts/attempt_a")).json()
    assert before["status"] == "SUBMITTED"
    assert (await post(client)).status_code == 201
    assert (await client.get("/api/v1/quiz-attempts/attempt_a")).json() == before
    with app.state.database.engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT * FROM review_cards").all() == before_cards
        assert conn.exec_driver_sql("SELECT * FROM review_events").all() == before_events


def test_production_openapi_feedback_contract() -> None:
    schema = create_app().openapi()
    path = schema["paths"]["/api/v1/quiz-questions/{questionId}/feedback"]
    assert "post" in path and "get" in path
    models = schema["components"]["schemas"]
    assert models["FeedbackRequest"]["additionalProperties"] is False
    assert models["Criterion"]["additionalProperties"] is False
    assert set(models["Criterion"]["required"]) == {"criterion", "commentVi"}


@pytest.mark.anyio
async def test_confirmed_failure_requires_retry_identity_even_with_fresh_key(
    app_client: Any,
) -> None:
    _, client, bridge = app_client
    bridge.failure = BridgeAuthError("synthetic")
    await post(client)
    bridge.failure = None
    assert (await post(client, "fresh-key-no-reference")).status_code == 422
    assert bridge.dispatches == 1


@pytest.mark.anyio
async def test_parallel_authorized_retries_dispatch_only_one(app_client: Any) -> None:
    _, client, bridge = app_client
    bridge.failure = BridgeAuthError("synthetic")
    await post(client)
    prior = (await client.get(PATH)).json()["data"][0]
    bridge.failure = None
    bridge.entered, bridge.release = asyncio.Event(), asyncio.Event()
    owner = asyncio.create_task(
        post(client, "retry-owner", retryOfOperationId=prior["operationId"])
    )
    await asyncio.wait_for(bridge.entered.wait(), 5)
    duplicate = await post(client, "retry-duplicate", retryOfOperationId=prior["operationId"])
    assert duplicate.status_code == 409
    bridge.release.set()
    assert (await owner).status_code == 201
    assert bridge.dispatches == 2


@pytest.mark.anyio
async def test_revoked_consent_has_zero_preflight(
    app_client: Any,
) -> None:
    app, client, bridge = app_client
    app.state.consent_service.revoke("revoke-before-request")
    result = await post(client)
    assert result.status_code == 403
    assert bridge.preflights == bridge.dispatches == 0
    assert (await client.get(PATH)).status_code == 200
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as unauthenticated:
        assert (await unauthenticated.get(PATH)).status_code == 401


@pytest.mark.anyio
async def test_shutdown_always_closes_database_after_feedback_drain_error(tmp_path: Path) -> None:
    app = create_app(AppSettings(storage_path=tmp_path / "shutdown.db"))
    with pytest.raises(RuntimeError, match="Feedback durable cleanup failed"):
        async with app.router.lifespan_context(app):
            app.state.feedback_service._errors.append(RuntimeError("synthetic"))
    assert app.state.database is None and not app.state.ready


@pytest.mark.anyio
async def test_changed_answer_blocks_retry_of_old_revision(app_client: Any) -> None:
    from backend.app.application.save_answer import AnswerDraftRequest
    from backend.app.assessment.questions import answer_etag

    app, client, bridge = app_client
    bridge.failure = BridgeAuthError("synthetic")
    assert (await post(client)).status_code == 502
    prior = (await client.get(PATH)).json()["data"][0]
    bridge.failure = None
    app.state.answer_service.save(
        attempt_id="attempt_a",
        question_id=WRITING,
        intent=AnswerDraftRequest(answer="Changed robust answer.", draft_revision=1),
        if_match=answer_etag("attempt_a", WRITING, 1),
        idempotency_key="changed-answer",
    )
    result = await post(client, "stale-retry", retryOfOperationId=prior["operationId"])
    assert result.status_code == 409
    assert result.json()["error"]["code"] == "REVISION_CONFLICT"
    assert bridge.dispatches == 1
    wrong_identity = await post(
        client,
        "changed-revision-retry",
        answerRevision=2,
        retryOfOperationId=prior["operationId"],
    )
    assert wrong_identity.status_code == 422
    assert bridge.dispatches == 1

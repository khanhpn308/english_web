"""Synthetic production-factory regressions for local atomic quiz submission."""

import json
import socket
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Event
from typing import Any

import pytest
from backend.app.assessment.questions import QuestionSet
from backend.app.assessment.repository import create_attempt
from backend.app.main import create_app
from backend.app.platform.config import AppSettings
from backend.app.vocabulary.repository import VocabularyRepository
from backend.tests.test_quiz_answers import BASE, MCQ, ROOT, WRITING, bootstrap, precondition, put
from backend.tests.test_quiz_snapshot import DATE, NOW, create, question, seed_sources
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.exc import OperationalError


@pytest.fixture
def app_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    def forbidden(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("Local submission must not invoke AI or a network")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    app = create_app(AppSettings(storage_path=tmp_path / "submissions.db"))
    with TestClient(app, base_url=BASE) as client:
        bridge = type(app.state.quiz_service.admission.bridge)
        monkeypatch.setattr(bridge, "preflight", forbidden)
        monkeypatch.setattr(bridge, "dispatch_chat", forbidden)
        seed_sources(app.state.database)
        create(app.state.database)
        app.state.submission_service.now = lambda: NOW
        bootstrap(app, client)
        yield app, client


def save(client: TestClient, question: str, answer: str, **fields: Any) -> None:
    condition = precondition(client, question)
    response = put(
        client, f"save-{question}-{condition['draftRevision']}", condition, answer, **fields
    )
    assert response.status_code == 200


def submit(client: TestClient, key: str = "submit", revision: int | None = None) -> Any:
    if revision is None:
        revision = client.get(ROOT).json()["submissionRevision"]
    return client.post(
        f"{ROOT}/submissions",
        json={"submissionRevision": revision},
        headers={"Origin": BASE, "Idempotency-Key": key},
    )


def test_atomic_grouped_submission_and_replay(app_client: Any) -> None:
    app, client = app_client
    save(client, MCQ, "o_a")
    save(client, "q_CLOZE_0", "robuts")
    save(client, WRITING, "A robust synthetic sentence.", selfScore=4)
    response = submit(client)
    assert response.status_code == 201
    result = response.json()
    assert result["status"] == "SUBMITTED"
    handoffs = {h["wordFormId"]: h for h in result["reviewHandoffs"]}
    assert handoffs["wf_0"]["rating"] == "AGAIN"
    assert len(handoffs) == 2 and all(h["status"] == "APPLIED" for h in handoffs.values())
    assert submit(client, revision=3).json() == result
    assert client.get(ROOT).json()["result"] == result
    with app.state.database.engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT count(*) FROM review_events").scalar_one() == 2
        row = connection.exec_driver_sql(
            "SELECT o.status,o.response_status,o.result_ref,a.submission_operation_id "
            "FROM operations o JOIN quiz_attempts a ON a.submission_operation_id=o.operation_id"
        ).one()
        assert tuple(row[:3]) == ("SUCCEEDED", 201, "attempt_a")
    assert response.headers["cache-control"] == "no-store"


def ready(client: TestClient) -> None:
    save(client, WRITING, "A robust synthetic sentence.", selfScore=4)


def durable_state(app: Any) -> tuple[Any, ...]:
    with app.state.database.engine.connect() as connection:
        return (
            tuple(
                connection.exec_driver_sql(
                    "SELECT status,submission_revision,result_payload,submission_operation_id "
                    "FROM quiz_attempts ORDER BY id"
                ).all()
            ),
            tuple(connection.exec_driver_sql("SELECT * FROM review_cards ORDER BY card_id").all()),
            tuple(connection.exec_driver_sql("SELECT * FROM review_events ORDER BY id").all()),
        )


@pytest.mark.parametrize(
    ("answer", "outcome"),
    [("o_a", "CORRECT"), ("o_b", "INCORRECT"), ("", "BLANK"), (None, "BLANK")],
)
def test_mcq_scoring(app_client: Any, answer: str | None, outcome: str) -> None:
    _, client = app_client
    ready(client)
    if answer is not None:
        save(client, MCQ, answer)
    response = submit(client)
    assert response.status_code == 201
    item = next(q for q in response.json()["questionResults"] if q["questionId"] == MCQ)
    assert item["outcome"] == outcome
    assert item["isCorrect"] == (outcome == "CORRECT")
    assert item["rating"] == ("GOOD" if outcome == "CORRECT" else "AGAIN")
    assert item["correctOptionId"] == "o_a" and item["explanationVi"]
    assert response.json()["objectiveScores"]["mcq"] == {
        "total": 2,
        "attempted": int(bool(answer)),
        "correct": int(outcome == "CORRECT"),
        "accuracy": float(outcome == "CORRECT") if answer else None,
    }


@pytest.mark.parametrize(
    ("answer", "outcome"),
    [
        ("robust", "CORRECT"),
        ("ROBUST", "CORRECT"),
        (" robust ", "CORRECT"),
        ("robuts", "INCORRECT"),
        ("", "BLANK"),
        (" \t ", "BLANK"),
    ],
)
def test_cloze_scoring(app_client: Any, answer: str, outcome: str) -> None:
    _, client = app_client
    ready(client)
    save(client, "q_CLOZE_0", answer)
    response = submit(client)
    assert response.status_code == 201
    item = next(q for q in response.json()["questionResults"] if q["type"] == "CLOZE")
    assert item["outcome"] == outcome and item["acceptedAnswers"] == ["robust"]


@pytest.mark.parametrize(
    ("score", "rating"), [(0, "AGAIN"), (1, "AGAIN"), (2, "HARD"), (3, "GOOD"), (4, "EASY")]
)
def test_writing_explicit_score_and_weakest_group(
    app_client: Any,
    score: int,
    rating: str,
) -> None:
    _, client = app_client
    save(client, MCQ, "o_a")
    save(client, "q_CLOZE_0", "robust")
    save(client, WRITING, "A robust synthetic sentence.", selfScore=score)
    response = submit(client)
    assert response.status_code == 201
    assert response.json()["writingSelfScores"] == [
        {
            "questionId": WRITING,
            "selfScore": score,
            "rating": rating,
        }
    ]
    group = next(h for h in response.json()["reviewHandoffs"] if h["wordFormId"] == "wf_0")
    assert group["rating"] == ("GOOD" if score == 4 else rating)


@pytest.mark.parametrize("draft", [None, {}, {"selfScore": None}])
def test_missing_or_null_writing_score_blocks_without_mutation(app_client: Any, draft: Any) -> None:
    app, client = app_client
    if draft is not None:
        save(client, WRITING, "A robust synthetic sentence.", **draft)
    before = durable_state(app)
    response = submit(client)
    assert response.status_code == 422 and response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert durable_state(app) == before
    assert client.get(ROOT).json()["result"] is None
    assert submit(client).json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize("score", [0, 4])
def test_blank_writing_requires_explicit_zero(app_client: Any, score: int) -> None:
    app, client = app_client
    save(client, WRITING, " \t ", selfScore=score)
    before = durable_state(app)
    response = submit(client)
    assert response.status_code == (201 if score == 0 else 422)
    if score:
        assert durable_state(app) == before


@pytest.mark.parametrize("status", ["INVALID", "MISSING"])
def test_inactive_source_skips_schedule_and_preserves_result(app_client: Any, status: str) -> None:
    app, client = app_client
    ready(client)
    with app.state.database.engine.begin() as connection:
        connection.exec_driver_sql("UPDATE source_files SET status=?", (status,))
    before = durable_state(app)
    response = submit(client)
    assert response.status_code == 201
    assert {h["status"] for h in response.json()["reviewHandoffs"]} == {"SKIPPED_INACTIVE"}
    assert all(h["reviewEventId"] is None for h in response.json()["reviewHandoffs"])
    assert durable_state(app)[1:] == before[1:]
    assert client.get(ROOT).json()["result"] == response.json()
    assert submit(client, revision=1).json() == response.json()


def test_revisions_key_reuse_and_fresh_second_submit(app_client: Any) -> None:
    app, client = app_client
    ready(client)
    before = durable_state(app)
    stale = submit(client, "stale", 0)
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "REVISION_CONFLICT"
    assert durable_state(app) == before
    result = submit(client)
    assert result.status_code == 201
    after = durable_state(app)
    changed = submit(client, revision=0)
    assert changed.status_code == 422
    assert changed.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    second = submit(client, "new-key", 0)
    assert second.status_code == 409 and second.json()["error"]["code"] == "ALREADY_SUBMITTED"
    assert durable_state(app) == after
    edited = put(client, "after-submit", precondition(client, WRITING), "Changed", selfScore=0)
    assert edited.status_code == 409 and edited.json()["error"]["code"] == "ALREADY_SUBMITTED"


@pytest.mark.parametrize("same_key", [False, True])
def test_concurrent_requests_cannot_duplicate_events(app_client: Any, same_key: bool) -> None:
    app, client = app_client
    ready(client)
    barrier = Barrier(2)

    def request(index: int) -> Any:
        worker = TestClient(app, base_url=BASE, cookies=dict(client.cookies))
        try:
            barrier.wait(timeout=5)
            return submit(worker, "parallel" if same_key else f"parallel-{index}", 1)
        finally:
            worker.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(request, (0, 1)))
    assert any(r.status_code == 201 for r in responses)
    if same_key:
        assert all(r.status_code in {201, 409} for r in responses)
        assert all(
            r.json()["error"]["code"] == "IDEMPOTENCY_IN_FLIGHT"
            for r in responses
            if r.status_code == 409
        )
        assert all(
            r.json() == client.get(ROOT).json()["result"] for r in responses if r.status_code == 201
        )
    else:
        assert sorted(r.status_code for r in responses) == [201, 409]
        assert (
            next(r for r in responses if r.status_code == 409).json()["error"]["code"]
            == "ALREADY_SUBMITTED"
        )
    assert len(durable_state(app)[2]) == 2


def test_duplicate_while_claimed_returns_in_flight(
    app_client: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, client = app_client
    ready(client)
    claimed, release = Event(), Event()
    ledger = app.state.operation_ledger
    complete = ledger.complete

    def blocked(*args: Any, **kwargs: Any) -> Any:
        claimed.set()
        assert release.wait(timeout=10)
        return complete(*args, **kwargs)

    monkeypatch.setattr(ledger, "complete", blocked)
    with ThreadPoolExecutor(max_workers=1) as pool:
        winner = pool.submit(submit, client, "in-flight", 1)
        try:
            assert claimed.wait(timeout=5)
            duplicate = submit(client, "in-flight", 1)
            assert duplicate.status_code == 409
            assert duplicate.json()["error"]["code"] == "IDEMPOTENCY_IN_FLIGHT"
            assert len(durable_state(app)[2]) == 0
        finally:
            release.set()
        assert winner.result(timeout=10).status_code == 201
    assert len(durable_state(app)[2]) == 2


@pytest.mark.parametrize(
    "statement_prefix",
    [
        "INSERT INTO review_events",
        "UPDATE review_cards",
        "UPDATE quiz_attempts SET status='SUBMITTED'",
        "UPDATE operations SET status='SUCCEEDED'",
    ],
)
def test_storage_failure_rolls_back_entire_handoff(app_client: Any, statement_prefix: str) -> None:
    app, client = app_client
    ready(client)
    before = durable_state(app)

    def fail(_conn: Any, _cursor: Any, statement: str, _params: Any, _ctx: Any, _many: Any) -> None:
        if statement.startswith(statement_prefix):
            raise OperationalError("synthetic-storage", None, RuntimeError("private-failure"))

    event.listen(app.state.database.engine, "before_cursor_execute", fail)
    try:
        response = submit(client)
    finally:
        event.remove(app.state.database.engine, "before_cursor_execute", fail)
    assert response.status_code == 503 and response.json()["error"]["code"] == "STORAGE_BUSY"
    assert "private-failure" not in response.text
    assert durable_state(app) == before
    identity = response.json()["error"]["details"]["operationId"]
    assert client.get(f"/api/v1/operations/{identity}").json()["status"] == "FAILED"
    assert submit(client).status_code == 503
    assert submit(client, "fresh-after-rollback").status_code == 201


def test_commit_exception_reconciles_durable_success(
    app_client: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, client = app_client
    ready(client)
    complete = app.state.operation_ledger.complete

    def ambiguous(*args: Any, **kwargs: Any) -> Any:
        complete(*args, **kwargs)
        raise OperationalError("synthetic-commit", None, RuntimeError("private-commit"))

    monkeypatch.setattr(app.state.operation_ledger, "complete", ambiguous)
    response = submit(client)
    assert response.status_code == 201
    assert submit(client, revision=1).json() == response.json()
    assert len(durable_state(app)[2]) == 2


def test_receipt_read_failure_keeps_success_for_later_replay(app_client: Any) -> None:
    app, client = app_client
    ready(client)

    def fail(_conn: Any, _cursor: Any, statement: str, _params: Any, _ctx: Any, _many: Any) -> None:
        if statement.startswith("SELECT submission_operation_id"):
            raise OperationalError("synthetic-read", None, RuntimeError("private-read"))

    event.listen(app.state.database.engine, "before_cursor_execute", fail)
    try:
        response = submit(client)
    finally:
        event.remove(app.state.database.engine, "before_cursor_execute", fail)
    assert response.status_code == 503 and "private-read" not in response.text
    identity = response.json()["error"]["details"]["operationId"]
    assert client.get(f"/api/v1/operations/{identity}").json()["status"] == "SUCCEEDED"
    assert submit(client, revision=1).json() == client.get(ROOT).json()["result"]
    assert len(durable_state(app)[2]) == 2


def test_no_answer_keys_before_terminal_commit(app_client: Any) -> None:
    _, client = app_client
    ready(client)
    before = client.get(ROOT)
    for private in ("correctOptionId", "acceptedAnswers", "explanationVi"):
        assert private not in before.text
    response = submit(client)
    assert response.status_code == 201
    for private in ("correctOptionId", "acceptedAnswers", "explanationVi"):
        assert private in response.text


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"submissionRevision": None},
        {"submissionRevision": True},
        {"submissionRevision": -1},
        {"submissionRevision": 1.0},
        {"submissionRevision": "1"},
        {"submissionRevision": 0, "answer": "private-input"},
    ],
)
def test_invalid_submission_shape_is_typed_and_does_not_claim(app_client: Any, body: Any) -> None:
    app, client = app_client
    response = client.post(
        f"{ROOT}/submissions", json=body, headers={"Origin": BASE, "Idempotency-Key": "bad-body"}
    )
    assert response.status_code == 422 and response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "private-input" not in response.text
    with app.state.database.engine.connect() as connection:
        assert (
            connection.exec_driver_sql(
                "SELECT count(*) FROM operations WHERE kind='QUIZ_SUBMISSION'"
            ).scalar_one()
            == 0
        )


def test_production_session_origin_and_header_guards(app_client: Any) -> None:
    app, client = app_client
    before = durable_state(app)
    anon = TestClient(app, base_url=BASE)
    try:
        assert submit(anon, revision=0).status_code == 401
    finally:
        anon.close()
    for headers, query, status in [
        ({"Origin": "http://hostile.invalid", "Idempotency-Key": "bad"}, "", 403),
        ({"Origin": BASE}, "", 422),
        ({"Origin": BASE, "Idempotency-Key": ""}, "", 422),
        ({"Origin": BASE, "Idempotency-Key": "bad"}, "?extra=1", 422),
        ([("Origin", BASE), ("Idempotency-Key", "a"), ("Idempotency-Key", "b")], "", 422),
    ]:
        response = client.post(
            f"{ROOT}/submissions{query}", json={"submissionRevision": 0}, headers=headers
        )
        assert response.status_code == status
    assert durable_state(app) == before


def test_lost_http_response_restart_and_durable_replay(app_client: Any) -> None:
    app, client = app_client
    ready(client)

    async def lost(scope: Any, receive: Any, send: Any) -> None:
        async def interrupted(message: Any) -> None:
            if message["type"] == "http.response.body":
                raise OSError("Synthetic lost response")
            await send(message)

        await app(scope, receive, interrupted)

    interrupted_client = TestClient(lost, base_url=BASE, cookies=dict(client.cookies))
    try:
        with pytest.raises(OSError, match="Synthetic lost response"):
            submit(interrupted_client, "lost-response", 1)
    finally:
        interrupted_client.close()
    original = client.get(ROOT).json()["result"]
    assert original is not None
    after = durable_state(app)
    restarted = create_app(app.state.settings)
    with TestClient(restarted, base_url=BASE) as reloaded:
        bootstrap(restarted, reloaded)
        assert reloaded.get(ROOT).json()["result"] == original
        assert submit(reloaded, "lost-response", 1).json() == original
        assert durable_state(restarted) == after
        with restarted.state.database.engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA integrity_check").all() == [("ok",)]
            assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []


def test_absent_card_is_skipped_without_creating_a_schedule(app_client: Any) -> None:
    app, client = app_client
    repo = VocabularyRepository(app.state.database.engine)
    repo.save_canonical_word_form(
        lemma="synthetic absent card",
        part_of_speech="ADJ",
        family_id="family_quiz",
        word_form_id="wf_absent",
    )
    repo.link_word_form_to_source("wf_absent", "src_quiz", DATE)
    questions = [question(index) for index in range(5)]
    for item in questions:
        item["id"] = f"absent_{item['id']}"
    questions[0]["wordFormId"] = "wf_absent"
    with (
        app.state.database.engine.connect().execution_options(
            sqlite_begin_immediate=True
        ) as connection,
        connection.begin(),
    ):
        create_attempt(
            connection,
            attempt_id="attempt_absent",
            note_date=DATE,
            questions=QuestionSet.model_validate_json(json.dumps({"questions": questions})),
            created_at=NOW,
        )
    response = client.post(
        "/api/v1/quiz-attempts/attempt_absent/submissions",
        json={"submissionRevision": 0},
        headers={"Origin": BASE, "Idempotency-Key": "absent"},
    )
    assert response.status_code == 201
    handoff = next(h for h in response.json()["reviewHandoffs"] if h["wordFormId"] == "wf_absent")
    assert handoff == {
        "wordFormId": "wf_absent",
        "cardId": None,
        "rating": "AGAIN",
        "reviewEventId": None,
        "status": "SKIPPED_INACTIVE",
    }
    with app.state.database.engine.connect() as connection:
        assert (
            connection.exec_driver_sql(
                "SELECT count(*) FROM review_cards WHERE word_form_id='wf_absent'"
            ).scalar_one()
            == 0
        )


def test_one_valid_source_keeps_card_active_and_later_source_loss_preserves_receipt(
    app_client: Any,
) -> None:
    app, client = app_client
    ready(client)
    repo = VocabularyRepository(app.state.database.engine)
    repo.save_source_file(
        source_id="src_other",
        relative_path="09-10-2026.md",
        note_date="2026-10-09",
        status="VALID",
        revision=1,
        etag='"r1"',
        content_hash="b" * 64,
    )
    repo.link_word_form_to_source("wf_0", "src_other", "2026-10-09")
    with app.state.database.engine.begin() as connection:
        connection.exec_driver_sql("UPDATE source_files SET status='MISSING' WHERE id='src_quiz'")
        connection.exec_driver_sql(
            "UPDATE review_cards SET box=2,due_at='2026-10-20T17:00:00.000000Z' "
            "WHERE card_id='card_0'"
        )
    response = submit(client)
    assert response.status_code == 201
    handoffs = {h["wordFormId"]: h for h in response.json()["reviewHandoffs"]}
    assert handoffs["wf_0"]["status"] == "APPLIED"
    assert handoffs["wf_1"]["status"] == "SKIPPED_INACTIVE"
    with app.state.database.engine.begin() as connection:
        assert connection.exec_driver_sql(
            "SELECT box,due_at FROM review_cards WHERE card_id='card_0'"
        ).one() == (1, "2026-10-08T17:00:00.000000Z")
        connection.exec_driver_sql("UPDATE source_files SET status='MISSING'")
    before = durable_state(app)
    assert submit(client, revision=1).json() == response.json()
    assert client.get(ROOT).json()["result"] == response.json()
    assert durable_state(app) == before


def test_openapi_uses_production_typed_submission_contract(app_client: Any) -> None:
    app, _ = app_client
    schema = app.openapi()
    route = schema["paths"]["/api/v1/quiz-attempts/{attemptId}/submissions"]["post"]
    assert route["responses"]["201"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/QuizResult"
    }
    assert set(route["responses"]) >= {"201", "401", "403", "409", "422", "503"}
    assert route["requestBody"]["required"]
    request_schema = schema["components"]["schemas"]["SubmissionRequest"]
    assert request_schema["required"] == ["submissionRevision"]
    assert request_schema["additionalProperties"] is False


def test_unavailable_service_readiness_unknown_attempt_and_corrupt_snapshot(
    app_client: Any,
) -> None:
    app, client = app_client
    service = app.state.submission_service
    app.state.submission_service = None
    assert submit(client, revision=0).json()["error"]["code"] == "CONFIGURATION_REQUIRED"
    app.state.submission_service = service
    app.state.ready = False
    assert submit(client, revision=0).json()["error"]["code"] == "STORAGE_BUSY"
    app.state.ready = True
    missing = client.post(
        "/api/v1/quiz-attempts/unknown/submissions",
        json={"submissionRevision": 0},
        headers={"Origin": BASE, "Idempotency-Key": "missing"},
    )
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "NOT_FOUND"
    with app.state.database.engine.begin() as connection:
        # Simulate corrupt storage only in this disposable synthetic database.
        connection.exec_driver_sql("DROP TRIGGER quiz_attempt_immutable")
        connection.exec_driver_sql(
            "UPDATE quiz_attempts SET snapshot_digest=? WHERE id='attempt_a'", ("0" * 64,)
        )
    response = submit(client, revision=0)
    assert response.status_code == 409
    assert response.json()["error"]["details"] == {
        "kind": "RESTORE",
        "attemptId": "attempt_a",
        "guidanceCode": "QUIZ_RESTORE_REQUIRED",
    }


@pytest.mark.parametrize("after_commit", [False, True])
def test_transient_attempt_read_failure_is_storage_error_with_operation_reference(
    app_client: Any,
    after_commit: bool,
) -> None:
    app, client = app_client
    ready(client)
    before = durable_state(app)
    completed = False

    def fail(_conn: Any, _cursor: Any, statement: str, _params: Any, _ctx: Any, _many: Any) -> None:
        nonlocal completed
        if statement.startswith("UPDATE operations SET status='SUCCEEDED'"):
            completed = True
        if statement.startswith("SELECT * FROM quiz_attempts") and completed == after_commit:
            raise OperationalError("synthetic-read", None, RuntimeError("private-read"))

    event.listen(app.state.database.engine, "before_cursor_execute", fail)
    try:
        response = submit(client, revision=1)
    finally:
        event.remove(app.state.database.engine, "before_cursor_execute", fail)
    assert response.status_code == 503 and response.json()["error"]["code"] == "STORAGE_BUSY"
    identity = response.json()["error"]["details"]["operationId"]
    assert client.get(f"/api/v1/operations/{identity}").json()["status"] == (
        "SUCCEEDED" if after_commit else "FAILED"
    )
    if after_commit:
        assert submit(client, revision=1).json() == client.get(ROOT).json()["result"]
        assert len(durable_state(app)[2]) == 2
    else:
        assert durable_state(app) == before

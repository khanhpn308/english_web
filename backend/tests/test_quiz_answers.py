"""T047 production-factory regressions; executable verification belongs to the Host."""

import json
import socket
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from typing import Any

import pytest
from alembic import command
from alembic.script import ScriptDirectory
from backend.app.assessment.questions import QuestionSet, storage_payload
from backend.app.assessment.repository import (
    create_attempt,
    get_attempt,
    save_answer,
    store_submission,
)
from backend.app.main import create_app
from backend.app.persistence.database import Database, migration_config
from backend.app.platform.config import AppSettings
from backend.tests.test_quiz_snapshot import (
    NOW,
    create,
    operation,
    question_set,
    seed_sources,
    terminal_result,
)
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError, OperationalError

BASE = "http://127.0.0.1:8000"
ROOT = "/api/v1/quiz-attempts/attempt_a"
MCQ = "q_MCQ_0"
WRITING = "q_WRITING_0"


def bootstrap(app: Any, client: TestClient) -> None:
    response = client.post(
        "/bootstrap/exchange",
        json={"token": app.state.sessions.issue_bootstrap_token()},
        headers={"Origin": BASE},
    )
    assert response.status_code == 204


@pytest.fixture
def app_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    # No real transport is needed even for fixture creation.
    def forbidden(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("Autosave must not contact a bridge or provider")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    app = create_app(AppSettings(storage_path=tmp_path / "answers.db"))
    with TestClient(app, base_url=BASE) as client:
        monkeypatch.setattr(type(app.state.quiz_service.admission.bridge), "preflight", forbidden)
        monkeypatch.setattr(type(app.state.quiz_service.admission.bridge), "dispatch_chat", forbidden)
        seed_sources(app.state.database)
        create(app.state.database)
        app.state.answer_service.now = lambda: NOW
        bootstrap(app, client)
        yield app, client


def precondition(client: TestClient, question: str = MCQ) -> dict[str, Any]:
    response = client.get(ROOT)
    assert response.status_code == 200
    return next(p for p in response.json()["answerPreconditions"] if p["questionId"] == question)


def put(
    client: TestClient,
    key: str,
    condition: dict[str, Any],
    answer: str = "o_a",
    **fields: Any,
) -> Any:
    return client.put(
        f"{ROOT}/answers/{condition['questionId']}",
        json={"answer": answer, "draftRevision": condition["draftRevision"], **fields},
        headers={"Origin": BASE, "If-Match": condition["etag"], "Idempotency-Key": key},
    )


def counts(app: Any) -> tuple[int, int, int]:
    with app.state.database.engine.connect() as connection:
        return (
            connection.exec_driver_sql("SELECT count(*) FROM quiz_answers").scalar_one(),
            connection.exec_driver_sql("SELECT count(*) FROM quiz_answer_receipts").scalar_one(),
            connection.exec_driver_sql(
                "SELECT count(*) FROM operations WHERE kind='QUIZ_ANSWER_DRAFT' "
                "AND status='SUCCEEDED'"
            ).scalar_one(),
        )


def test_initial_tokens_and_exact_old_receipt_replay(app_client: Any) -> None:
    app, client = app_client
    with app.state.database.engine.connect() as connection:
        snapshot = connection.exec_driver_sql("SELECT * FROM quiz_questions ORDER BY id").all()
    attempt = client.get(ROOT).json()
    assert len(attempt["answerPreconditions"]) == len(attempt["questions"]) == 5
    assert {p["draftRevision"] for p in attempt["answerPreconditions"]} == {0}
    assert len({p["etag"] for p in attempt["answerPreconditions"]}) == 5
    initial = precondition(client)
    first = put(client, "first", initial)
    assert first.status_code == 200
    assert first.json()["draftRevision"] == 1
    assert first.headers["etag"] == precondition(client)["etag"] != initial["etag"]
    second = put(client, "second", precondition(client), "o_b")
    assert second.status_code == 200 and second.json()["draftRevision"] == 2
    replay = put(client, "first", initial)
    assert replay.status_code == 200 and replay.json() == first.json()
    assert replay.headers["etag"] == first.headers["etag"]
    latest = client.get(ROOT).json()
    assert latest["answers"] == [second.json()]
    assert latest["submissionRevision"] == 2
    assert counts(app) == (1, 2, 2)
    reused = put(client, "first", initial, "o_b")
    assert reused.status_code == 422
    assert reused.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert put(client, "stale", initial).status_code == 409
    with app.state.database.engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT count(*) FROM review_events").scalar_one() == 0
        assert connection.exec_driver_sql("SELECT * FROM quiz_questions ORDER BY id").all() == snapshot
    public = first.text + second.text + client.get(ROOT).text
    for private in ("correctOptionId", "acceptedAnswers", "explanationVi"):
        assert private not in public


def test_parallel_distinct_intents_have_one_winner(app_client: Any) -> None:
    app, client = app_client
    initial = precondition(client)
    cookie = dict(client.cookies)
    barrier = Barrier(2)

    def write(index: int) -> Any:
        with_client = TestClient(app, base_url=BASE, cookies=cookie)
        try:
            barrier.wait(timeout=5)
            return put(with_client, f"parallel-{index}", initial, ("o_a", "o_b")[index])
        finally:
            with_client.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(write, (0, 1)))
    assert sorted(response.status_code for response in responses) == [200, 409]
    loser = next(response for response in responses if response.status_code == 409)
    assert loser.json()["error"]["code"] == "REVISION_CONFLICT"
    assert counts(app) == (1, 1, 1)
    assert client.get(ROOT).json()["submissionRevision"] == 1


@pytest.mark.parametrize("token", [None, "*", 'W/"qa-v1-' + "a" * 64 + '"', '"bad"', ""])
def test_missing_or_malformed_precondition_is_422(app_client: Any, token: str | None) -> None:
    app, client = app_client
    headers = {"Origin": BASE, "Idempotency-Key": "bad-header"}
    if token is not None:
        headers["If-Match"] = token
    response = client.put(
        f"{ROOT}/answers/{MCQ}", json={"answer": "o_a", "draftRevision": 0}, headers=headers
    )
    assert response.status_code == 422
    assert counts(app) == (0, 0, 0)


def test_wrong_resource_and_mixed_revision_conflict(app_client: Any) -> None:
    app, client = app_client
    initial = precondition(client)
    foreign = {**initial, "etag": precondition(client, WRITING)["etag"]}
    assert put(client, "foreign-token", foreign).status_code == 409
    mixed = {**initial, "draftRevision": 1}
    assert put(client, "mixed", mixed).status_code == 409
    assert counts(app) == (0, 0, 0)


@pytest.mark.parametrize("score", [None, 0, 4])
def test_writing_scores_and_omission(app_client: Any, score: int | None) -> None:
    _app, client = app_client
    response = put(
        client, "writing", precondition(client, WRITING), "Synthetic sentence.", selfScore=score
    )
    assert response.status_code == 200 and response.json()["selfScore"] == score
    preserved = put(client, "preserve-score", precondition(client, WRITING), "Revised sentence.")
    assert preserved.status_code == 200 and preserved.json()["selfScore"] == score
    cleared = put(client, "clear-score", precondition(client, WRITING), "", selfScore=None)
    assert cleared.json()["state"] == "BLANK" and cleared.json()["selfScore"] is None


@pytest.mark.parametrize("score", [-1, 5, True, 1.0, "0"])
def test_invalid_score_has_no_effect(app_client: Any, score: Any) -> None:
    app, client = app_client
    response = put(
        client, "invalid-score", precondition(client, WRITING), "answer-sentinel", selfScore=score
    )
    assert response.status_code == 422 and "answer-sentinel" not in response.text
    assert counts(app) == (0, 0, 0)


def test_blank_objective_is_not_scored_wrong(app_client: Any) -> None:
    _app, client = app_client
    blank = put(client, "blank", precondition(client), "")
    assert blank.json()["state"] == "BLANK"
    wrong = put(client, "wrong", precondition(client), "o_b")
    assert wrong.json()["state"] == "DRAFT" and "isCorrect" not in wrong.json()
    invalid = put(client, "outside-option", precondition(client), "outside-option-sentinel")
    assert invalid.status_code == 422 and "outside-option-sentinel" not in invalid.text
    assert put(client, "objective-score", precondition(client), selfScore=0).status_code == 422


def test_terminal_replay_and_fresh_write_refusal(app_client: Any) -> None:
    app, client = app_client
    initial = precondition(client)
    first = put(client, "first", initial)
    put(client, "writing-zero", precondition(client, WRITING), "", selfScore=0)
    with (
        app.state.database.engine.connect().execution_options(
            sqlite_begin_immediate=True
        ) as connection,
        connection.begin(),
    ):
        operation(connection, "submit-fixture")
        store_submission(
            connection, result=terminal_result(connection), operation_id="submit-fixture"
        )
    before = counts(app)
    assert put(client, "first", initial).json() == first.json()
    fresh = put(client, "after-submit", precondition(client), "o_b")
    assert fresh.status_code == 409 and fresh.json()["error"]["code"] == "ALREADY_SUBMITTED"
    assert counts(app) == before
    assert client.get(ROOT).json()["status"] == "SUBMITTED"


def test_receipt_failure_rolls_back_projection_and_completion(app_client: Any) -> None:
    app, client = app_client
    initial = precondition(client)

    def fail(
        _conn: Any, _cursor: Any, statement: str, _parameters: Any, _context: Any, _many: Any
    ) -> None:
        if statement.startswith("INSERT INTO quiz_answer_receipts"):
            raise OperationalError("synthetic", None, RuntimeError("private-storage-sentinel"))

    event.listen(app.state.database.engine, "before_cursor_execute", fail)
    try:
        response = put(client, "storage-failure", initial)
    finally:
        event.remove(app.state.database.engine, "before_cursor_execute", fail)
    assert response.status_code == 503 and "private-storage-sentinel" not in response.text
    assert counts(app) == (0, 0, 0)
    assert precondition(client) == initial
    with app.state.database.engine.connect() as connection:
        assert get_attempt(connection, "attempt_a").submission_revision == 0


def test_restart_new_session_restores_latest_and_old_receipt(app_client: Any) -> None:
    app, client = app_client
    initial = precondition(client)
    first = put(client, "restart-first", initial)
    second = put(client, "restart-second", precondition(client), "o_b")
    latest_condition = precondition(client)
    reopened = create_app(app.state.settings)
    with TestClient(reopened, base_url=BASE) as restored:
        restored.cookies.update(client.cookies)
        assert restored.get(ROOT).status_code == 401
        restored.cookies.clear()
        bootstrap(reopened, restored)
        assert restored.get(ROOT).json()["answers"] == [second.json()]
        assert precondition(restored) == latest_condition
        replay = put(restored, "restart-first", initial)
        assert replay.status_code == 200 and replay.json() == first.json()
        assert counts(reopened) == (1, 2, 2)


def test_response_lost_after_commit_replays_without_mutation(
    app_client: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.http import quiz_answers

    app, client = app_client
    initial = precondition(client)
    original = quiz_answers.JSONResponse

    def lost_response(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("Synthetic disconnect after durable service completion")

    monkeypatch.setattr(quiz_answers, "JSONResponse", lost_response)
    with pytest.raises(RuntimeError, match="Synthetic disconnect"):
        put(client, "lost-response", initial)
    monkeypatch.setattr(quiz_answers, "JSONResponse", original)
    assert counts(app) == (1, 1, 1)
    acknowledged = client.get(ROOT).json()["answers"][0]
    replay = put(client, "lost-response", initial)
    assert replay.status_code == 200 and replay.json() == acknowledged
    assert counts(app) == (1, 1, 1)
    status = client.get(f"/api/v1/operations/{acknowledged['operationId']}")
    assert status.json()["status"] == "SUCCEEDED"
    assert "answer" not in status.json() and "selfScore" not in status.json()


def test_missing_and_foreign_membership_and_session_guards(app_client: Any) -> None:
    app, client = app_client
    initial = precondition(client)
    headers = {"Origin": BASE, "If-Match": initial["etag"], "Idempotency-Key": "membership"}
    body = {"answer": "o_a", "draftRevision": 0}
    assert client.put(f"{ROOT}/answers/missing", json=body, headers=headers).status_code == 404
    assert client.put(
        "/api/v1/quiz-attempts/missing/answers/missing", json=body, headers=headers
    ).status_code == 404
    data = question_set().model_dump(mode="json", by_alias=True)
    # Storage serialization preserves private objective keys; ordinary dumps omit them.
    data["questions"] = [json.loads(storage_payload(q)) for q in question_set().questions]
    for question in data["questions"]:
        question["id"] = "foreign_" + question["id"]
    questions = QuestionSet.model_validate_json(json.dumps(data))
    with (
        app.state.database.engine.connect().execution_options(
            sqlite_begin_immediate=True
        ) as connection,
        connection.begin(),
    ):
        create_attempt(
            connection, attempt_id="other", note_date="2026-10-08", questions=questions,
            created_at=NOW,
        )
    response = client.put(f"{ROOT}/answers/foreign_{MCQ}", json=body, headers=headers)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "CROSS_RESOURCE_MISMATCH"
    anonymous = TestClient(app, base_url=BASE)
    try:
        assert anonymous.put(f"{ROOT}/answers/{MCQ}", json=body, headers=headers).status_code == 401
    finally:
        anonymous.close()
    assert client.put(
        f"{ROOT}/answers/{MCQ}", json=body, headers={**headers, "Origin": "http://hostile.invalid"}
    ).status_code == 403
    assert counts(app) == (0, 0, 0)


def test_database_receipts_are_immutable_and_require_matching_evidence(app_client: Any) -> None:
    app, client = app_client
    saved = put(client, "immutable", precondition(client)).json()
    engine = app.state.database.engine
    for statement in (
        "UPDATE quiz_answer_receipts SET answer='changed'",
        "DELETE FROM quiz_answer_receipts",
        "INSERT OR REPLACE INTO quiz_answer_receipts SELECT * FROM quiz_answer_receipts",
        "INSERT INTO quiz_answer_receipts SELECT attempt_id,question_id,draft_revision+1,"
        "answer,self_score,saved_at,state,operation_id FROM quiz_answer_receipts",
    ):
        with (
            engine.connect().execution_options(sqlite_begin_immediate=True) as connection,
            connection.begin(),
        ):
            with pytest.raises(IntegrityError):
                connection.exec_driver_sql(statement)
    with engine.connect() as connection:
        receipt = connection.exec_driver_sql(
            "SELECT answer,draft_revision FROM quiz_answer_receipts"
        ).one()
        assert tuple(receipt) == (saved["answer"], 1)
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []


def test_upgrade_preserves_existing_latest_draft_without_fabricating_history(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "legacy.db")

    def predecessor(connection: Any) -> None:
        config = migration_config()
        config.attributes["connection"] = connection
        command.upgrade(config, "0009_review_diagnostics")

    try:
        database.initialize(migrate=predecessor)
        seed_sources(database)
        create(database)
        with (
            database.engine.connect().execution_options(sqlite_begin_immediate=True) as connection,
            connection.begin(),
        ):
            operation(connection, "legacy-draft")
            saved = save_answer(
                connection, attempt_id="attempt_a", question_id=MCQ, answer="o_a",
                self_score=None, expected_draft_revision=0, operation_id="legacy-draft",
                saved_at=NOW,
            )
            before = get_attempt(connection, "attempt_a")
        assert database.initialize().schema_revision == "0010_quiz_answer_receipts"
        with database.engine.connect() as connection:
            assert get_attempt(connection, "attempt_a") == before
            assert get_attempt(connection, "attempt_a").answers == (saved,)
            assert connection.exec_driver_sql(
                "SELECT count(*) FROM quiz_answer_receipts"
            ).scalar_one() == 0
            assert connection.exec_driver_sql("PRAGMA integrity_check").all() == [("ok",)]
            assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
        scripts = ScriptDirectory.from_config(migration_config())
        head = scripts.get_revision("0010_quiz_answer_receipts")
        assert head is not None and head.down_revision == "0009_review_diagnostics"
    finally:
        database.close()


def test_commit_exception_uses_durable_success_instead_of_reapplying(
    app_client: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, client = app_client
    initial = precondition(client)
    ledger = app.state.answer_service.ledger
    complete = ledger.complete

    def ambiguous(*args: Any, **kwargs: Any) -> Any:
        complete(*args, **kwargs)
        raise OperationalError("synthetic-commit", None, RuntimeError("interrupted-commit"))

    monkeypatch.setattr(ledger, "complete", ambiguous)
    response = put(client, "ambiguous-commit", initial)
    assert response.status_code == 200
    assert counts(app) == (1, 1, 1)
    assert put(client, "ambiguous-commit", initial).json() == response.json()
    assert counts(app) == (1, 1, 1)


def test_receipt_read_unavailable_after_commit_preserves_success_and_reference(
    app_client: Any,
) -> None:
    app, client = app_client
    initial = precondition(client)

    def fail_read(
        _conn: Any, _cursor: Any, statement: str, _parameters: Any, _context: Any, _many: Any
    ) -> None:
        if statement.startswith("SELECT * FROM quiz_answer_receipts"):
            raise OperationalError("synthetic-read", None, RuntimeError("private-read-sentinel"))

    event.listen(app.state.database.engine, "before_cursor_execute", fail_read)
    try:
        response = put(client, "receipt-read-failure", initial)
    finally:
        event.remove(app.state.database.engine, "before_cursor_execute", fail_read)
    assert response.status_code == 503 and "private-read-sentinel" not in response.text
    identity = response.json()["error"]["details"]["operationId"]
    assert client.get(f"/api/v1/operations/{identity}").json()["status"] == "SUCCEEDED"
    assert counts(app) == (1, 1, 1)
    replay = put(client, "receipt-read-failure", initial)
    assert replay.status_code == 200 and replay.json()["operationId"] == identity
    assert counts(app) == (1, 1, 1)


def test_pending_identical_intent_is_not_reexecuted_and_null_changes_fingerprint(
    app_client: Any,
) -> None:
    app, client = app_client
    initial = precondition(client)
    claim = app.state.operation_ledger.claim(
        kind="QUIZ_ANSWER_DRAFT", key="pending", method="PUT",
        path=f"{ROOT}/answers/{MCQ}", body={"answer": "o_a", "draftRevision": 0},
        preconditions={"If-Match": initial["etag"]},
    )
    response = put(client, "pending", initial)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "IDEMPOTENCY_IN_FLIGHT"
    assert response.json()["error"]["details"]["operationId"] == claim.operation.operation_id
    changed = put(client, "pending", initial, selfScore=None)
    assert changed.status_code == 422
    assert changed.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert counts(app) == (0, 0, 0)

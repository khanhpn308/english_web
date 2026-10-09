"""T035 synthetic-provider regressions. Execution is deferred to the owner."""

import asyncio
import copy
import json
import socket
import threading
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

import pytest
from backend.app.application.ai_admission import AiAdmissionCoordinator
from backend.app.application.consent import ConsentApplied, ConsentSnapshot
from backend.app.application.create_quiz import CreateQuizRequest, CreateQuizService
from backend.app.application.operations import OperationConflict
from backend.app.main import create_app
from backend.app.platform.bridge_port import (
    BridgeAuthError,
    BridgeConfigError,
    BridgeInvalidResponseError,
    BridgeProfile,
    BridgeUnavailableError,
)
from backend.app.platform.config import AppSettings
from backend.app.vocabulary.models import ExampleSentence, MeaningEn, MeaningVi
from backend.app.vocabulary.repository import VocabularyRepository
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event

BASE = "http://127.0.0.1:8000"
PATH = "/api/v1/quiz-attempts"
DATE = "2026-10-08"
MODEL = "gemini-3.8-flash-high"
COUNTS = {"mcq": 2, "cloze": 2, "writing": 1}
DESCRIPTORS = (
    "Không có câu có nghĩa, thiếu từ mục tiêu hoặc không thể đánh giá cách dùng nghĩa.",
    "Có thử dùng từ nhưng sai nghĩa/dạng hoặc lỗi ngữ pháp lớn cản trở nghĩa định diễn đạt.",
    "Nhận ra nghĩa định dùng nhưng dạng từ hoặc ngữ pháp cần sửa đáng kể.",
    "Đúng nghĩa/dạng và ngữ pháp dễ hiểu; lỗi nhỏ không cản trở nghĩa.",
    "Đúng nghĩa/dạng, đúng ngữ pháp, rõ ràng, tự nhiên và chính xác trong văn học thuật.",
)


def policy_fixture() -> dict[str, Any]:
    scopes = ["LOOKUP", "QUIZ_GENERATION", "WRITING_FEEDBACK"]
    return {
        "version": "quiz-policy-v1",
        "reviewStatus": "READY",
        "disclosureText": "Synthetic quiz policy.",
        "dataCategories": ["TERM", "WORD_FORMS", "WRITING_ANSWER"],
        "recipients": ["Antigravity/Google"],
        "retentionStatement": "Configured provider terms apply.",
        "regionStatement": "Configured provider region applies.",
        "costQuotaStatement": "Configured account; no automatic fallback.",
        "withdrawalStatement": "Withdrawal cannot recall admitted data.",
        "scopes": scopes,
        "dispatchRules": [
            {"scope": scope, "providerLabel": "Antigravity/Google", "modelId": MODEL,
             "route": "primary", "billingMode": "configured-account"}
            for scope in scopes
        ],
        "blockedReasons": [],
    }


def provider_questions(counts: dict[str, int] | None = None) -> dict[str, Any]:
    questions = []
    for kind, count in (counts or COUNTS).items():
        for index in range(count):
            item: dict[str, Any] = {
                "id": f"provider_{kind}_{index}", "type": kind.upper(),
                "wordFormId": f"wf_{index}", "promptEn": "Synthetic question.",
            }
            if kind == "mcq":
                item.update(options=[{"id": "a", "textEn": "synthetic"},
                                     {"id": "b", "textEn": "fragile"}],
                            correctOptionId="a", explanationVi="private-explanation-sentinel")
            elif kind == "cloze":
                item.update(answerPolicyVersion="cloze-answer-v1",
                            acceptedAnswers=["private-cloze-sentinel"],
                            explanationVi="private-explanation-sentinel")
            else:
                item.update(targetLemma=f"synthetic {index}", rubricVersion="writing-rubric-v1",
                            rubric={"descriptors": [{"score": score, "textVi": text}
                                                    for score, text in enumerate(DESCRIPTORS)]})
            questions.append(item)
    return {"questions": questions}


class FakeBridge:
    def __init__(self) -> None:
        self.output: Any = provider_questions()
        self.preflights = 0
        self.dispatches = 0
        self.payloads: list[dict[str, Any]] = []
        self.deadlines: list[float] = []
        self.profile = BridgeProfile(models=[{"id": MODEL, "owned_by": "google"}])
        self.preflight_failure: Exception | None = None
        self.failure: Exception | None = None
        self.after_preflight: Callable[[], None] | None = None
        self.after_dispatch: Callable[[], None] | None = None
        self.entered: asyncio.Event | None = None
        self.release: asyncio.Event | None = None

    async def preflight(self, deadline: float) -> BridgeProfile:
        self.preflights += 1
        self.deadlines.append(deadline)
        if self.after_preflight:
            self.after_preflight()
        if self.preflight_failure:
            raise self.preflight_failure
        return self.profile

    async def dispatch_chat(self, payload: dict[str, Any], deadline: float) -> dict[str, Any]:
        self.dispatches += 1
        self.deadlines.append(deadline)
        self.payloads.append(copy.deepcopy(payload))
        if self.entered:
            self.entered.set()
        if self.release:
            await asyncio.wait_for(self.release.wait(), 5)
        if self.after_dispatch:
            self.after_dispatch()
        if self.failure:
            raise self.failure
        content = self.output if isinstance(self.output, str) else json.dumps(self.output)
        return {"model": MODEL, "choices": [{"message": {"content": content}}]}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def deny_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("Quiz tests must never perform inference or network I/O")
    monkeypatch.setattr(socket.socket, "connect", forbidden)


def seed_sources(app: Any, count: int = 20) -> None:
    repo = VocabularyRepository(app.state.database.engine)
    family = repo.get_or_create_family("synthetic", family_id="family_quiz")
    repo.save_source_file(source_id="src_quiz", relative_path="08-10-2026.md",
                          note_date=DATE, status="VALID", revision=1, etag='"quiz-r1"',
                          content_hash="a" * 64)
    for index in range(count):
        form = repo.save_canonical_word_form(
            lemma=f"synthetic {index}", part_of_speech="ADJ", family_id=family.id,
            word_form_id=f"wf_{index}", meanings_en=[MeaningEn("Synthetic meaning.")],
            meanings_vi=[MeaningVi("Nghĩa tổng hợp.")],
            examples=[ExampleSentence("Synthetic example.", "Ví dụ tổng hợp.")],
        )
        repo.link_word_form_to_source(form.id, "src_quiz", DATE)


async def bootstrap(app: Any, client: AsyncClient) -> None:
    response = await client.post("/bootstrap/exchange",
                                 json={"token": app.state.sessions.issue_bootstrap_token()},
                                 headers={"Origin": BASE})
    assert response.status_code == 204
    client.headers.update({"Origin": BASE,
                           "Cookie": response.headers["set-cookie"].split(";", 1)[0]})


@pytest.fixture
async def app_client(tmp_path: Path) -> AsyncIterator[tuple[Any, AsyncClient, FakeBridge]]:
    app = create_app(AppSettings(storage_path=tmp_path / "quiz.db"))
    policy = policy_fixture()
    async with (app.router.lifespan_context(app),
                AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client):
        seed_sources(app)
        snapshot = app.state.consent_service.read_consent(policy)
        assert isinstance(snapshot, ConsentSnapshot)
        granted = app.state.consent_service.grant("grant-quiz", snapshot.etag,
                                                  policy["version"], policy)
        assert isinstance(granted, ConsentApplied)
        bridge = FakeBridge()
        app.state.active_ai_policy = policy
        # Keep the production service, ledger and repository. Replace transport only.
        app.state.quiz_service.admission.bridge = bridge
        await bootstrap(app, client)
        yield app, client, bridge


async def post(client: AsyncClient, key: str = "quiz-intent",
               counts: dict[str, Any] | None = None, note_date: str = DATE) -> Any:
    return await client.post(PATH, json={"noteDate": note_date, "counts": counts or COUNTS},
                             headers={"Idempotency-Key": key})


def operation(app: Any) -> Any:
    with app.state.database.engine.connect() as connection:
        return connection.exec_driver_sql(
            "SELECT operation_id,status,error_category,result_ref FROM operations "
            "WHERE kind='QUIZ_GENERATION'"
        ).mappings().one()


def assert_no_snapshot(app: Any) -> None:
    with app.state.database.engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT count(*) FROM quiz_attempts").scalar_one() == 0
        assert connection.exec_driver_sql("SELECT count(*) FROM quiz_questions").scalar_one() == 0


@pytest.mark.anyio
async def test_creation_public_snapshot_and_identical_replay(app_client: Any) -> None:
    app, client, bridge = app_client
    response = await post(client)
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "IN_PROGRESS"
    assert body["result"] is None and body["answers"] == []
    assert body["snapshotRevision"] == 1 and body["submissionRevision"] == 0
    assert body["savedAnswerCount"] == 0
    assert [q["type"] for q in body["questions"]] == ["MCQ", "MCQ", "CLOZE", "CLOZE", "WRITING"]
    for concealed in ("correctOptionId", "acceptedAnswers", "explanationVi",
                       "private-explanation-sentinel", "private-cloze-sentinel"):
        assert concealed not in response.text
    assert response.headers["Cache-Control"] == "no-store"
    assert (await post(client)).json() == body
    assert bridge.dispatches == bridge.preflights == 1
    assert operation(app)["status"] == "SUCCEEDED"
    assert operation(app)["result_ref"] == body["id"]
    get = await client.get(f"{PATH}/{body['id']}")
    assert get.status_code == 200 and get.json() == body
    assert get.headers["Cache-Control"] == "no-store"


@pytest.mark.anyio
@pytest.mark.parametrize("counts,valid", [
    ({"mcq": 0, "cloze": 0, "writing": 0}, False),
    ({"mcq": 1, "cloze": 1, "writing": 1}, False),
    ({"mcq": 5, "cloze": 0, "writing": 0}, True),
    ({"mcq": 10, "cloze": 10, "writing": 10}, True),
    ({"mcq": 11, "cloze": 10, "writing": 10}, False),
    ({"mcq": 21, "cloze": 4, "writing": 0}, False),
    ({"mcq": True, "cloze": 3, "writing": 1}, False),
    ({"mcq": 2.0, "cloze": 2, "writing": 1}, False),
])
async def test_count_boundaries_before_dispatch(app_client: Any, counts: Any, valid: bool) -> None:
    app, client, bridge = app_client
    bridge.output = provider_questions(counts) if valid else provider_questions()
    response = await post(client, counts=counts)
    assert response.status_code == (201 if valid else 422)
    assert bridge.dispatches == bridge.preflights == int(valid)
    if valid:
        assert len(response.json()["questions"]) == sum(counts.values())
    else:
        assert_no_snapshot(app)


@pytest.mark.anyio
@pytest.mark.parametrize("state", ["INVALID", "MISSING", "DELETE", "INSUFFICIENT", "FOREIGN_DATE"])
async def test_valid_selected_date_and_distinct_forms_required(app_client: Any, state: str) -> None:
    app, client, bridge = app_client
    repo = VocabularyRepository(app.state.database.engine)
    if state == "DELETE":
        repo.delete_source_file("src_quiz")
    elif state == "INSUFFICIENT":
        for index in range(1, 20):
            repo.unlink_source_from_form(f"wf_{index}", "src_quiz")
    elif state == "FOREIGN_DATE":
        with app.state.database.engine.begin() as connection:
            connection.exec_driver_sql("UPDATE source_files SET note_date=? WHERE id=?",
                                       ("2026-10-09", "src_quiz"))
    else:
        repo.update_source_status("src_quiz", state)
    response = await post(client)
    assert response.status_code == 422
    assert bridge.dispatches == bridge.preflights == 0
    assert_no_snapshot(app)


@pytest.mark.anyio
@pytest.mark.parametrize("mutation", [
    "wrong_count", "wrong_type_counts", "duplicate_id", "duplicate_pair", "foreign_form",
    "extra", "missing_key", "wrong_key", "oversized", "script", "surrogate", "control",
    "rubric", "target", "alternatives", "too_many_options", "malformed", "duplicate_json",
])
async def test_hostile_or_inexact_output_never_persists(app_client: Any, mutation: str) -> None:
    app, client, bridge = app_client
    data = provider_questions()
    first = data["questions"][0]
    if mutation == "wrong_count":
        data["questions"].pop()
    elif mutation == "wrong_type_counts":
        data = provider_questions({"mcq": 5, "cloze": 0, "writing": 0})
    elif mutation == "duplicate_id":
        data["questions"][1]["id"] = first["id"]
    elif mutation == "duplicate_pair":
        data["questions"][1]["wordFormId"] = first["wordFormId"]
    elif mutation == "foreign_form":
        first["wordFormId"] = "wf_foreign"
    elif mutation == "extra":
        first["tool"] = "run a shell"
    elif mutation == "missing_key":
        del first["correctOptionId"]
    elif mutation == "wrong_key":
        first["correctOptionId"] = "absent-option"
    elif mutation == "oversized":
        first["promptEn"] = "x" * 4097
    elif mutation == "script":
        first["promptEn"] = "<script>hostile()</script>"
    elif mutation == "surrogate":
        first["promptEn"] = "\ud800"
    elif mutation == "control":
        first["promptEn"] = "bad\u0000content"
    elif mutation == "rubric":
        data["questions"][-1]["rubric"]["descriptors"][0]["textVi"] = "Changed rubric."
    elif mutation == "target":
        data["questions"][-1]["targetLemma"] = "another form"
    elif mutation == "alternatives":
        data["questions"][2]["acceptedAnswers"] = ["robust", "ROBUST"]
    elif mutation == "too_many_options":
        first["options"] = [{"id": f"option_{i}", "textEn": "choice"} for i in range(101)]
        first["correctOptionId"] = "option_0"
    bridge.output = data
    if mutation == "malformed":
        bridge.output = "{broken"
    elif mutation == "duplicate_json":
        bridge.output = '{"questions":[],"questions":' + json.dumps(data["questions"]) + "}"
    response = await post(client)
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "BRIDGE_INVALID_RESPONSE"
    assert bridge.dispatches == 1
    assert_no_snapshot(app)
    assert operation(app)["status"] == "FAILED"
    assert (await post(client)).status_code == 502
    assert bridge.dispatches == 1


@pytest.mark.anyio
@pytest.mark.parametrize("state", ["REVOKED", "STALE", "MISSING_POLICY", "MODEL_DRIFT", "FALLBACK"])
async def test_consent_and_policy_default_deny(app_client: Any, state: str) -> None:
    app, client, bridge = app_client
    expected_status = 403
    if state == "REVOKED":
        app.state.consent_service.revoke("revoke-quiz")
    elif state == "STALE":
        policy = copy.deepcopy(app.state.active_ai_policy)
        policy["version"] = "quiz-policy-v2"
        app.state.active_ai_policy = policy
    elif state == "MISSING_POLICY":
        app.state.active_ai_policy = None
        expected_status = 503
    elif state == "MODEL_DRIFT":
        bridge.profile.models[0]["id"] = "unapproved-model"
        expected_status = 503
    else:
        bridge.profile.models[0]["fallback"] = ["paid-route"]
        expected_status = 503
    response = await post(client)
    assert response.status_code == expected_status
    assert bridge.dispatches == 0
    assert bridge.preflights == int(state in {"MODEL_DRIFT", "FALLBACK"})
    assert operation(app)["status"] == "FAILED"
    assert_no_snapshot(app)


@pytest.mark.anyio
async def test_revoke_at_preflight_fence_and_replay_is_denied(app_client: Any) -> None:
    app, client, bridge = app_client
    bridge.after_preflight = lambda: app.state.consent_service.revoke("revoke-at-fence")
    response = await post(client)
    assert response.status_code == 403
    assert bridge.preflights == 1 and bridge.dispatches == 0
    assert_no_snapshot(app)
    assert (await post(client)).status_code == 403
    assert bridge.preflights == 1


@pytest.mark.anyio
@pytest.mark.parametrize("failure,status,code", [
    (BridgeConfigError("synthetic"), 503, "CONFIGURATION_REQUIRED"),
    (BridgeAuthError("synthetic"), 502, "BRIDGE_AUTH_ERROR"),
    (BridgeInvalidResponseError("synthetic"), 502, "BRIDGE_INVALID_RESPONSE"),
    (BridgeUnavailableError("synthetic"), 503, "BRIDGE_UNAVAILABLE"),
])
@pytest.mark.parametrize("stage", ["preflight", "transport"])
async def test_bridge_failures_no_retry_or_fallback(app_client: Any, failure: Exception,
                                                  status: int, code: str, stage: str) -> None:
    app, client, bridge = app_client
    if stage == "preflight":
        bridge.preflight_failure = failure
    else:
        bridge.failure = failure
    response = await post(client)
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    uncertain = stage == "transport" and isinstance(failure, BridgeUnavailableError)
    assert operation(app)["status"] == ("UNKNOWN" if uncertain else "FAILED")
    assert_no_snapshot(app)
    replay = await post(client)
    assert replay.status_code == (409 if uncertain else status)
    assert bridge.preflights == 1
    assert bridge.dispatches == int(stage == "transport")


@pytest.mark.anyio
async def test_changed_key_intent_and_concurrent_duplicates(app_client: Any) -> None:
    app, client, bridge = app_client
    bridge.entered, bridge.release = asyncio.Event(), asyncio.Event()
    owner = asyncio.create_task(post(client))
    await asyncio.wait_for(bridge.entered.wait(), 5)
    duplicate = await post(client)
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "IDEMPOTENCY_IN_FLIGHT"
    changed = await post(client, counts={"mcq": 3, "cloze": 1, "writing": 1})
    assert changed.status_code == 422
    assert changed.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    bridge.release.set()
    response = await asyncio.wait_for(owner, 5)
    assert response.status_code == 201
    assert bridge.dispatches == 1
    assert operation(app)["status"] == "SUCCEEDED"
    assert (await post(client)).json() == response.json()


@pytest.mark.anyio
async def test_offline_read_and_replay_survive_source_edit_delete_and_restart(
    app_client: Any,
) -> None:
    app, client, bridge = app_client
    response = await post(client)
    assert response.status_code == 201
    original = response.json()
    repo = VocabularyRepository(app.state.database.engine)
    with app.state.database.engine.begin() as connection:
        connection.exec_driver_sql("UPDATE word_forms SET meanings_en=? WHERE id=?",
                                   ('[{"text":"changed source"}]', "wf_0"))
    repo.delete_source_file("src_quiz")
    with app.state.database.engine.begin() as connection:
        connection.exec_driver_sql("DELETE FROM word_forms WHERE id=?", ("wf_0",))
    app.state.active_ai_policy = None
    bridge.failure = BridgeUnavailableError("offline")
    assert (await client.get(f"{PATH}/{original['id']}")).json() == original
    assert (await post(client)).json() == original
    assert bridge.dispatches == 1

    restarted = create_app(app.state.settings)
    async with (restarted.router.lifespan_context(restarted),
                AsyncClient(transport=ASGITransport(app=restarted), base_url=BASE) as reader):
        await bootstrap(restarted, reader)
        restored = await reader.get(f"{PATH}/{original['id']}")
        assert restored.status_code == 200 and restored.json() == original
        replay = await post(reader)
        assert replay.status_code == 201 and replay.json() == original
        assert operation(restarted)["status"] == "SUCCEEDED"


@pytest.mark.anyio
@pytest.mark.parametrize("elapsed", [59.999, 60.0, 60.001])
async def test_full_sixty_second_transport_boundary(app_client: Any, elapsed: float) -> None:
    app, client, bridge = app_client
    now = [0.0]
    app.state.quiz_service.clock = lambda: now[0]
    app.state.quiz_service.admission.clock = lambda: now[0]
    bridge.after_dispatch = lambda: now.__setitem__(0, elapsed)
    response = await post(client)
    await app.state.quiz_service.drain()
    assert bridge.deadlines == [60.0, 60.0]
    if elapsed < 60:
        assert response.status_code == 201
    else:
        assert response.status_code == 503
        assert operation(app)["status"] == "UNKNOWN"
        assert operation(app)["error_category"] == "TIMEOUT"
        assert_no_snapshot(app)


@pytest.mark.anyio
async def test_expired_preflight_budget_never_admits_transport(app_client: Any) -> None:
    app, client, bridge = app_client
    now = [0.0]
    app.state.quiz_service.clock = lambda: now[0]
    app.state.quiz_service.admission.clock = lambda: now[0]
    bridge.after_preflight = lambda: now.__setitem__(0, 60.0)
    response = await post(client)
    await app.state.quiz_service.drain()
    assert response.status_code == 503
    assert bridge.preflights == 1 and bridge.dispatches == 0
    assert operation(app)["status"] == "FAILED"
    assert operation(app)["error_category"] == "TIMEOUT"
    assert_no_snapshot(app)


@pytest.mark.anyio
async def test_cancelled_transport_is_unknown_and_never_redispatches(app_client: Any) -> None:
    app, client, bridge = app_client
    bridge.entered, bridge.release = asyncio.Event(), asyncio.Event()
    request = asyncio.create_task(post(client))
    await asyncio.wait_for(bridge.entered.wait(), 5)
    request.cancel()
    with pytest.raises(asyncio.CancelledError):
        await request
    await app.state.quiz_service.drain()
    receipt = operation(app)
    assert receipt["status"] == "UNKNOWN" and receipt["error_category"] == "TIMEOUT"
    assert_no_snapshot(app)
    read = await client.get(f"/api/v1/operations/{receipt['operation_id']}")
    assert read.status_code == 200 and read.json()["status"] == "UNKNOWN"
    assert (await post(client)).status_code == 409
    assert bridge.dispatches == 1


@pytest.mark.anyio
@pytest.mark.parametrize("boundary", ["INSERT INTO quiz_questions", "UPDATE operations", "commit"])
async def test_storage_failure_rolls_back_entire_snapshot_and_receipt(app_client: Any,
                                                                   boundary: str) -> None:
    app, client, bridge = app_client
    engine = app.state.database.engine
    failed = [False]
    def fail_sql(_conn: Any, _cursor: Any, statement: str, _parameters: Any,
                 _context: Any, _many: bool) -> None:
        if boundary in statement and not failed[0]:
            failed[0] = True
            raise OSError("synthetic disk failure")
    def fail_commit(connection: Any) -> None:
        if connection.exec_driver_sql("SELECT count(*) FROM quiz_attempts").scalar_one():
            raise OSError("synthetic commit failure")
    listener = fail_commit if boundary == "commit" else fail_sql
    name = "commit" if boundary == "commit" else "before_cursor_execute"
    event.listen(engine, name, listener)
    try:
        response = await post(client)
    finally:
        event.remove(engine, name, listener)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "STORAGE_BUSY"
    assert_no_snapshot(app)
    assert operation(app)["status"] == "FAILED"
    assert bridge.dispatches == 1


@pytest.mark.anyio
async def test_local_question_ids_do_not_collide_between_distinct_intents(app_client: Any) -> None:
    _app, client, bridge = app_client
    first, second = await post(client, key="first"), await post(client, key="second")
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
    assert {q["id"] for q in first.json()["questions"]}.isdisjoint(
        q["id"] for q in second.json()["questions"])
    assert bridge.dispatches == 2


@pytest.mark.anyio
async def test_missing_and_corrupt_snapshot_reads_are_typed(app_client: Any) -> None:
    app, client, _bridge = app_client
    assert (await client.get(f"{PATH}/missing_attempt")).status_code == 404
    response = await post(client)
    attempt_id = response.json()["id"]
    # Corruption fixture only; production never removes snapshot rows.
    with app.state.database.engine.begin() as connection:
        connection.exec_driver_sql("DROP TRIGGER quiz_question_no_delete")
        connection.exec_driver_sql("DELETE FROM quiz_questions WHERE attempt_id=?", (attempt_id,))
    restored = await client.get(f"{PATH}/{attempt_id}")
    assert restored.status_code == 409
    assert restored.json()["error"]["code"] == "QUIZ_RESTORE_REQUIRED"
    assert restored.headers["Cache-Control"] == "no-store"
    replay = await post(client)
    assert replay.status_code == 409
    assert replay.json()["error"]["details"]["attemptId"] == attempt_id


@pytest.mark.anyio
@pytest.mark.parametrize("note_date", ["2026-02-30", "20261008", "08-10-2026", "2026-10-07"])
async def test_invalid_or_absent_note_date_before_preflight(
    app_client: Any, note_date: str,
) -> None:
    app, client, bridge = app_client
    response = await post(client, note_date=note_date)
    assert response.status_code == 422
    assert bridge.dispatches == bridge.preflights == 0
    assert_no_snapshot(app)


@pytest.mark.anyio
@pytest.mark.parametrize("boundary", ["claim", "admission", "completion"])
async def test_expired_worker_cannot_start_business_transaction(
    app_client: Any, monkeypatch: pytest.MonkeyPatch, boundary: str,
) -> None:
    app, client, bridge = app_client
    service = app.state.quiz_service
    now = [0.0]
    service.clock = service.admission.clock = lambda: now[0]
    engine = app.state.database.engine
    active = threading.local()
    statements: list[str] = []

    def observe(_conn: Any, _cursor: Any, statement: str, _params: Any,
                _context: Any, _many: bool) -> None:
        if getattr(active, "expired_worker", False):
            statements.append(statement)

    target, name = (
        (service.admission, "_admit") if boundary == "admission"
        else (service.ledger, "claim" if boundary == "claim" else "complete")
    )
    original = getattr(target, name)

    def delayed_worker(*args: Any, **kwargs: Any) -> Any:
        # Simulate scheduling or connection acquisition consuming the last budget.
        # Observe the real ledger/consent writer, including its BEGIN IMMEDIATE.
        now[0] = 60.0
        active.expired_worker = True
        try:
            return original(*args, **kwargs)
        finally:
            active.expired_worker = False

    monkeypatch.setattr(target, name, delayed_worker)
    event.listen(engine, "before_cursor_execute", observe)
    try:
        response = await post(client)
        await service.drain()
    finally:
        event.remove(engine, "before_cursor_execute", observe)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "BRIDGE_UNAVAILABLE"
    assert statements == []
    assert_no_snapshot(app)
    assert bridge.dispatches == (1 if boundary == "completion" else 0)
    if boundary == "claim":
        with engine.connect() as connection:
            assert connection.exec_driver_sql(
                "SELECT count(*) FROM operations WHERE kind='QUIZ_GENERATION'"
            ).scalar_one() == 0
    else:
        receipt = operation(app)
        assert receipt["status"] == "FAILED"
        assert receipt["error_category"] == "TIMEOUT"
        read = await client.get(f"/api/v1/operations/{receipt['operation_id']}")
        assert read.json()["status"] == receipt["status"]
        assert bridge.dispatches == (1 if boundary == "completion" else 0)


@pytest.mark.anyio
@pytest.mark.parametrize("completion_time", [59.95, 60.1])
async def test_nonpreemptible_commit_still_refuses_late_http_success(
    app_client: Any, monkeypatch: pytest.MonkeyPatch, completion_time: float,
) -> None:
    """An admitted commit settles atomically; only timely HTTP may acknowledge it."""
    app, client, bridge = app_client
    now = [0.0]
    service = app.state.quiz_service
    service.clock = lambda: now[0]
    service.admission.clock = lambda: now[0]
    dialect = app.state.database.engine.dialect
    commit = dialect.do_commit
    bridge.after_dispatch = lambda: now.__setitem__(0, 59.9)
    entered, release = threading.Event(), threading.Event()
    admission_times: list[float] = []

    def delayed_commit(connection: Any) -> None:
        if not admission_times and connection.execute(
            "SELECT count(*) FROM quiz_attempts"
        ).fetchone()[0]:
            # This dialect boundary follows the production commit-admission guard.
            # Hold the actual SQLite transaction until the test releases it.
            admission_times.append(now[0])
            entered.set()
            if not release.wait(5):
                raise AssertionError("Physical commit barrier was not released")
            commit(connection)
            now[0] = completion_time
            return
        commit(connection)

    monkeypatch.setattr(dialect, "do_commit", delayed_commit)
    request = asyncio.create_task(post(client))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        assert admission_times == [59.9]
        release.set()
        response = await request
        await service.drain()
    finally:
        release.set()
        request.cancel()
        await asyncio.gather(request, return_exceptions=True)
        await service.drain()
    assert response.status_code == (201 if completion_time < 60 else 503)
    receipt = operation(app)
    assert receipt["status"] == "SUCCEEDED"
    if completion_time >= 60:
        assert response.json()["error"]["code"] == "BRIDGE_UNAVAILABLE"
        assert response.json()["error"]["details"]["operationId"] == receipt["operation_id"]
    else:
        assert response.json()["id"] == receipt["result_ref"]
    with app.state.database.engine.connect() as connection:
        fingerprint = connection.exec_driver_sql(
            "SELECT key_digest,request_digest,operation_id FROM operation_keys "
            "WHERE kind='QUIZ_GENERATION'"
        ).one()
    reconciled = await client.get(f"/api/v1/operations/{receipt['operation_id']}")
    assert reconciled.status_code == 200 and reconciled.json()["status"] == "SUCCEEDED"
    assert reconciled.json()["resultRef"] == receipt["result_ref"]
    restored = await client.get(f"{PATH}/{receipt['result_ref']}")
    replay = await post(client)
    assert restored.status_code == 200 and replay.status_code == 201
    assert restored.json() == replay.json()
    assert "private-explanation-sentinel" not in replay.text
    assert "private-cloze-sentinel" not in replay.text
    assert bridge.dispatches == bridge.preflights == 1
    with app.state.database.engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT count(*) FROM quiz_attempts").scalar_one() == 1
        assert connection.exec_driver_sql("SELECT count(*) FROM quiz_questions").scalar_one() == 5
        assert connection.exec_driver_sql(
            "SELECT count(*) FROM operations WHERE kind='QUIZ_GENERATION'"
        ).scalar_one() == 1
        assert connection.exec_driver_sql(
            "SELECT key_digest,request_digest,operation_id FROM operation_keys "
            "WHERE kind='QUIZ_GENERATION'"
        ).one() == fingerprint


@pytest.mark.anyio
async def test_cancelled_request_during_admitted_commit_preserves_durable_success(
    app_client: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, client, bridge = app_client
    service = app.state.quiz_service
    now = [0.0]
    service.clock = service.admission.clock = lambda: now[0]
    bridge.after_dispatch = lambda: now.__setitem__(0, 59.9)
    entered, release = threading.Event(), threading.Event()
    dialect = service.ledger.engine.dialect
    commit = dialect.do_commit
    admission_times: list[float] = []

    def held_commit(connection: Any) -> None:
        if not admission_times and connection.execute(
            "SELECT count(*) FROM quiz_attempts"
        ).fetchone()[0]:
            admission_times.append(now[0])
            entered.set()
            if not release.wait(5):
                raise AssertionError("Admitted commit barrier was not released")
        commit(connection)

    monkeypatch.setattr(dialect, "do_commit", held_commit)
    request = asyncio.create_task(post(client))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        assert admission_times == [59.9]
        request.cancel()
        with pytest.raises(asyncio.CancelledError):
            await request
        now[0] = 60.1
    finally:
        release.set()
        request.cancel()
        await asyncio.gather(request, return_exceptions=True)
        await service.drain()
    receipt = operation(app)
    assert receipt["status"] == "SUCCEEDED" and receipt["error_category"] is None
    read = await client.get(f"/api/v1/operations/{receipt['operation_id']}")
    assert read.status_code == 200 and read.json()["status"] == "SUCCEEDED"
    restored = await client.get(f"{PATH}/{receipt['result_ref']}")
    replay = await post(client)
    assert restored.status_code == 200 and replay.status_code == 201
    assert restored.json() == replay.json()
    assert bridge.dispatches == bridge.preflights == 1
    with service.ledger.engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT count(*) FROM quiz_attempts").scalar_one() == 1
        assert connection.exec_driver_sql("SELECT count(*) FROM quiz_questions").scalar_one() == 5


@pytest.mark.anyio
async def test_lost_physical_commit_ack_preserves_proven_success(
    app_client: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, client, bridge = app_client
    service = app.state.quiz_service
    now = [0.0]
    service.clock = service.admission.clock = lambda: now[0]
    bridge.after_dispatch = lambda: now.__setitem__(0, 59.9)
    dialect = service.ledger.engine.dialect
    commit = dialect.do_commit
    admission_times: list[float] = []

    def lose_commit_ack(connection: Any) -> None:
        quiz = connection.execute("SELECT count(*) FROM quiz_attempts").fetchone()[0]
        commit(connection)
        if quiz and not admission_times:
            admission_times.append(now[0])
            now[0] = 60.1
            raise OSError("Synthetic acknowledgement loss after physical commit")

    monkeypatch.setattr(dialect, "do_commit", lose_commit_ack)
    response = await post(client)
    await service.drain()
    assert admission_times == [59.9]
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "BRIDGE_UNAVAILABLE"
    receipt = operation(app)
    assert receipt["status"] == "SUCCEEDED" and receipt["error_category"] is None
    assert response.json()["error"]["details"]["operationId"] == receipt["operation_id"]
    restored = await client.get(f"{PATH}/{receipt['result_ref']}")
    replay = await post(client)
    assert restored.status_code == 200 and replay.status_code == 201
    assert restored.json() == replay.json()
    assert bridge.dispatches == bridge.preflights == 1
    with service.ledger.engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT count(*) FROM quiz_attempts").scalar_one() == 1
        assert connection.exec_driver_sql("SELECT count(*) FROM quiz_questions").scalar_one() == 5


@pytest.mark.anyio
@pytest.mark.parametrize("failure_time", [59.95, 60.1])
async def test_failed_physical_commit_never_acknowledges_snapshot_success(
    app_client: Any, monkeypatch: pytest.MonkeyPatch, failure_time: float,
) -> None:
    app, client, bridge = app_client
    service = app.state.quiz_service
    now = [0.0]
    service.clock = service.admission.clock = lambda: now[0]
    dialect = service.ledger.engine.dialect
    commit = dialect.do_commit
    failed = [False]
    admission_times: list[float] = []
    bridge.after_dispatch = lambda: now.__setitem__(0, 59.9)

    def failed_commit(connection: Any) -> None:
        if not failed[0] and connection.execute(
            "SELECT count(*) FROM quiz_attempts"
        ).fetchone()[0]:
            failed[0] = True
            admission_times.append(now[0])
            now[0] = failure_time
            raise OSError("synthetic physical commit failure")
        commit(connection)

    monkeypatch.setattr(dialect, "do_commit", failed_commit)
    response = await post(client)
    await service.drain()
    assert response.status_code == 503
    assert failed[0]
    assert admission_times == [59.9]
    assert_no_snapshot(app)
    receipt = operation(app)
    assert receipt["status"] == "FAILED"
    assert receipt["result_ref"] is None
    assert receipt["error_category"] == ("TIMEOUT" if failure_time >= 60 else "STORAGE_BUSY")
    assert response.json()["error"]["details"]["operationId"] == receipt["operation_id"]
    assert (await post(client)).status_code == 503
    assert bridge.dispatches == bridge.preflights == 1


@pytest.mark.anyio
@pytest.mark.parametrize("failure, expected_status", [
    (BridgeAuthError("synthetic rejection"), "FAILED"),
    (BridgeInvalidResponseError("synthetic malformed response"), "FAILED"),
    (BridgeConfigError("synthetic configuration failure"), "FAILED"),
    (BridgeUnavailableError("synthetic uncertain transport"), "UNKNOWN"),
])
async def test_timeout_preserves_known_or_uncertain_transport_outcome(
    app_client: Any, failure: Exception, expected_status: str,
) -> None:
    app, client, bridge = app_client
    service = app.state.quiz_service
    now = [0.0]
    service.clock = service.admission.clock = lambda: now[0]
    bridge.failure = failure
    bridge.after_dispatch = lambda: now.__setitem__(0, 60.0)
    response = await post(client)
    await service.drain()
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "BRIDGE_UNAVAILABLE"
    receipt = operation(app)
    assert receipt["status"] == expected_status
    assert receipt["error_category"] == "TIMEOUT"
    assert_no_snapshot(app)
    assert (await post(client)).status_code == (409 if expected_status == "UNKNOWN" else 503)
    assert bridge.dispatches == bridge.preflights == 1


@pytest.mark.anyio
async def test_ac14_all_three_forms_are_sent_without_due_filter_or_history(app_client: Any) -> None:
    app, client, bridge = app_client
    repo = VocabularyRepository(app.state.database.engine)
    for index in range(3, 20):
        repo.unlink_source_from_form(f"wf_{index}", "src_quiz")
    bridge.output["questions"][3]["wordFormId"] = "wf_2"
    bridge.output["questions"][4]["wordFormId"] = "wf_1"
    bridge.output["questions"][4]["targetLemma"] = "synthetic 1"
    response = await post(client)
    assert response.status_code == 201
    assert [(q["type"], q["wordFormId"]) for q in response.json()["questions"]] == [
        ("MCQ", "wf_0"), ("MCQ", "wf_1"), ("CLOZE", "wf_0"),
        ("CLOZE", "wf_2"), ("WRITING", "wf_1"),
    ]
    payload = bridge.payloads[0]
    assert set(payload) == {"messages", "model"}
    assert payload["model"] == MODEL
    source = json.loads(payload["messages"][1]["content"])
    assert {form["wordFormId"] for form in source["forms"]} == {"wf_0", "wf_1", "wf_2"}
    assert set(source) == {"noteDate", "counts", "forms", "writingRubric"}
    for form in source["forms"]:
        assert set(form) == {
            "wordFormId", "lemma", "partOfSpeech", "meaningsEn", "meaningsVi", "examples",
        }
    serialized = json.dumps(payload)
    for excluded in ("wf_19", "quiz-intent", "launch_session", "dueAt", "source_refs", "api_key"):
        assert excluded not in serialized


@pytest.mark.anyio
async def test_source_invalidated_while_generating_cannot_be_acknowledged(app_client: Any) -> None:
    app, client, bridge = app_client
    repo = VocabularyRepository(app.state.database.engine)
    bridge.after_dispatch = lambda: repo.update_source_status("src_quiz", "INVALID")
    response = await post(client)
    assert response.status_code == 422
    assert_no_snapshot(app)
    assert operation(app)["status"] == "FAILED"
    assert bridge.dispatches == 1


@pytest.mark.anyio
@pytest.mark.parametrize("boundary", ["parse", "snapshot", "receipt", "commit", "finalize"])
async def test_deadline_covers_processing_and_atomic_completion(app_client: Any,
                                                              monkeypatch: pytest.MonkeyPatch,
                                                              boundary: str) -> None:
    from backend.app.application import create_quiz as module
    app, client, _bridge = app_client
    now = [0.0]
    service = app.state.quiz_service
    service.clock = lambda: now[0]
    service.admission.clock = lambda: now[0]
    engine = app.state.database.engine
    physical_snapshot_commits: list[float] = []
    commit = engine.dialect.do_commit

    def observe_physical_commit(connection: Any) -> None:
        if connection.execute("SELECT count(*) FROM quiz_attempts").fetchone()[0]:
            physical_snapshot_commits.append(now[0])
        commit(connection)

    monkeypatch.setattr(engine.dialect, "do_commit", observe_physical_commit)

    def expire_sql(_conn: Any, _cursor: Any, statement: str, _params: Any,
                   _context: Any, _many: bool) -> None:
        if (boundary == "snapshot" and "INSERT INTO quiz_questions" in statement
            or boundary == "receipt" and "UPDATE operations" in statement):
            now[0] = 60.0

    def expire_commit(connection: Any) -> None:
        if boundary == "commit" and connection.connection.dbapi_connection.execute(
            "SELECT count(*) FROM quiz_attempts"
        ).fetchone()[0]:
            now[0] = 60.0

    def install_expiry(connection: Any) -> None:
        # Engine commit listeners run after connection-local guards. Inject at
        # the front of this connection's listeners to test expiry BEFORE admission.
        event.listen(connection, "commit", expire_commit, insert=True)

    parse = module.parse_questions
    def expired_parse(*args: Any) -> Any:
        result = parse(*args)
        now[0] = 60.0
        return result
    if boundary == "parse":
        monkeypatch.setattr(module, "parse_questions", expired_parse)
    event.listen(engine, "before_cursor_execute", expire_sql)
    event.listen(engine, "engine_connect", install_expiry)
    try:
        if boundary == "finalize":
            def finalize(_attempt: Any) -> Any:
                now[0] = 60.0
                return "late-public-response"
            with pytest.raises(OperationConflict) as error:
                await service.create(
                    intent=CreateQuizRequest.model_validate({"noteDate": DATE, "counts": COUNTS}),
                    idempotency_key="quiz-intent", finalize=finalize,
                )
            assert error.value.code == "BRIDGE_UNAVAILABLE"
        else:
            assert (await post(client)).status_code == 503
        await service.drain()
    finally:
        event.remove(engine, "before_cursor_execute", expire_sql)
        event.remove(engine, "engine_connect", install_expiry)
    assert_no_snapshot(app)
    # In particular, expiry exactly at 60s before commit admission must never
    # reach physical COMMIT with a tentative quiz/receipt pair.
    assert physical_snapshot_commits == []
    # The provider response arrived; rollback is a definite local failure.
    assert operation(app)["status"] == "FAILED"
    assert operation(app)["error_category"] == "TIMEOUT"


@pytest.mark.anyio
async def test_http_success_first_sent_at_deadline_becomes_reconcilable_timeout(
    app_client: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.http import quiz as module
    from starlette.responses import JSONResponse

    app, client, bridge = app_client
    service = app.state.quiz_service
    now = [0.0]
    service.clock = service.admission.clock = lambda: now[0]
    public = module._public

    class DelayedResponse(JSONResponse):
        async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
            now[0] = 60.0
            await super().__call__(scope, receive, send)

    def delayed_public(attempt: Any, status: int = 200) -> JSONResponse:
        response = public(attempt, status)
        return DelayedResponse(json.loads(response.body), status_code=status,
                               headers=dict(response.headers))

    monkeypatch.setattr(module, "_public", delayed_public)
    response = await post(client)
    await service.drain()
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "BRIDGE_UNAVAILABLE"
    receipt = operation(app)
    assert receipt["status"] == "SUCCEEDED"
    assert response.json()["error"]["details"]["operationId"] == receipt["operation_id"]
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    read = await client.get(f"/api/v1/operations/{receipt['operation_id']}")
    assert read.json()["resultRef"] == receipt["result_ref"]
    monkeypatch.setattr(module, "_public", public)
    restored = await client.get(f"{PATH}/{receipt['result_ref']}")
    replay = await post(client)
    assert restored.status_code == 200 and replay.status_code == 201
    assert restored.json() == replay.json()
    assert "private-explanation-sentinel" not in replay.text
    assert "private-cloze-sentinel" not in replay.text
    assert bridge.dispatches == bridge.preflights == 1


@pytest.mark.anyio
async def test_deadline_guards_are_isolated_between_concurrent_intents(app_client: Any) -> None:
    app, _client, bridge = app_client
    service = app.state.quiz_service
    now = [0.0]
    service.clock = service.admission.clock = lambda: now[0]
    bridge.entered, bridge.release = asyncio.Event(), asyncio.Event()
    intent = CreateQuizRequest.model_validate({"noteDate": DATE, "counts": COUNTS})
    first = asyncio.create_task(service.create(intent=intent, idempotency_key="earlier",
                                             request_start_time=-30.0))
    second: asyncio.Task[Any] | None = None
    try:
        await asyncio.wait_for(bridge.entered.wait(), 5)
        second = asyncio.create_task(service.create(intent=intent, idempotency_key="later",
                                                  request_start_time=0.0))
        async with asyncio.timeout(5):
            while bridge.dispatches < 2:
                await asyncio.sleep(0)
        now[0] = 30.0
        bridge.release.set()
        results = await asyncio.gather(first, second, return_exceptions=True)
        assert isinstance(results[0], OperationConflict)
        assert results[0].code == "BRIDGE_UNAVAILABLE"
        assert not isinstance(results[1], BaseException)
        await service.drain()
        with service.ledger.engine.connect() as connection:
            assert connection.exec_driver_sql(
                "SELECT status FROM operations WHERE kind='QUIZ_GENERATION' ORDER BY status"
            ).scalars().all() == ["SUCCEEDED", "UNKNOWN"]
            assert connection.exec_driver_sql("SELECT count(*) FROM quiz_attempts").scalar_one() == 1
        assert bridge.dispatches == 2
        assert service.admission.consent.storage_reliable
    finally:
        bridge.release.set()
        first.cancel()
        if second is not None:
            second.cancel()
        await asyncio.gather(first, *([second] if second is not None else []),
                             return_exceptions=True)
        await service.drain()


@pytest.mark.anyio
async def test_committed_result_is_replayable_after_completion_wait_expires(
    app_client: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, client, bridge = app_client
    now = [0.0]
    service = app.state.quiz_service
    service.clock = lambda: now[0]
    service.admission.clock = lambda: now[0]
    complete = service.ledger.complete
    def lose_ack(*args: Any, **kwargs: Any) -> Any:
        result = complete(*args, **kwargs)
        now[0] = 60.0
        return result
    monkeypatch.setattr(service.ledger, "complete", lose_ack)
    assert (await post(client)).status_code == 503
    await service.drain()
    assert operation(app)["status"] == "SUCCEEDED"
    assert (await post(client)).status_code == 201
    assert bridge.dispatches == 1


@pytest.mark.anyio
async def test_lost_http_response_after_commit_reconciles_same_identity(app_client: Any) -> None:
    app, client, bridge = app_client
    observed_ids: list[str] = []
    forwarded: list[Any] = []

    async def lossy_app(scope: Any, receive: Any, send: Any) -> None:
        async def lose_success(message: Any) -> None:
            if message["type"] == "http.response.start" and 200 <= message["status"] < 300:
                observed_ids.append(scope["state"]["quiz_operation_id"])
                raise ConnectionResetError("Synthetic response loss after durable commit")
            forwarded.append(message)
            await send(message)
        await app(scope, receive, lose_success)

    # Keep production middleware/session, storage and routing. Drop the response
    # at the final ASGI transport boundary after the server has committed it.
    async with AsyncClient(transport=ASGITransport(app=lossy_app), base_url=BASE,
                           headers=dict(client.headers)) as disconnected_client:
        with pytest.raises(ConnectionResetError):
            await post(disconnected_client)
    await app.state.quiz_service.drain()
    assert forwarded == []
    receipt = operation(app)
    assert observed_ids == [receipt["operation_id"]]
    assert receipt["status"] == "SUCCEEDED"
    read = await client.get(f"/api/v1/operations/{receipt['operation_id']}")
    assert read.status_code == 200
    assert read.json()["operationId"] == receipt["operation_id"]
    assert read.json()["resultRef"] == receipt["result_ref"]
    restored = await client.get(f"{PATH}/{receipt['result_ref']}")
    replay = await post(client)
    assert restored.status_code == 200 and replay.status_code == 201
    assert restored.json() == replay.json()
    for concealed in ("correctOptionId", "acceptedAnswers", "explanationVi"):
        assert concealed not in replay.text
    assert operation(app)["operation_id"] == receipt["operation_id"]
    assert bridge.dispatches == bridge.preflights == 1
    with app.state.database.engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT count(*) FROM quiz_attempts").scalar_one() == 1
        assert connection.exec_driver_sql("SELECT count(*) FROM quiz_questions").scalar_one() == 5
        assert connection.exec_driver_sql(
            "SELECT count(*) FROM operation_keys WHERE kind='QUIZ_GENERATION'"
        ).scalar_one() == 1


@pytest.mark.anyio
async def test_cancelled_source_worker_stays_owned_and_never_dispatches(
    app_client: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, client, bridge = app_client
    entered, release = threading.Event(), threading.Event()
    service = app.state.quiz_service
    source = service._source
    def blocked_source(intent: Any) -> Any:
        entered.set()
        assert release.wait(5)
        return source(intent)
    monkeypatch.setattr(service, "_source", blocked_source)
    request = asyncio.create_task(post(client))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        request.cancel()
        with pytest.raises(asyncio.CancelledError):
            await request
    finally:
        release.set()
    await service.drain()
    assert operation(app)["status"] == "FAILED"
    assert_no_snapshot(app)
    assert bridge.dispatches == bridge.preflights == 0


@pytest.mark.anyio
async def test_consent_details_deadline_settles_claim(app_client: Any,
                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    app, client, bridge = app_client
    now = [0.0]
    service = app.state.quiz_service
    service.clock = lambda: now[0]
    service.admission.clock = lambda: now[0]
    app.state.consent_service.revoke("revoke-quiz")
    read = service.admission.consent.get_snapshot
    reads = [0]
    def exhausted_read(*args: Any, **kwargs: Any) -> Any:
        snapshot = read(*args, **kwargs)
        reads[0] += 1
        if reads[0] == 2:
            now[0] = 60.0
        return snapshot
    monkeypatch.setattr(service.admission.consent, "get_snapshot", exhausted_read)
    assert (await post(client)).status_code == 503
    await service.drain()
    assert operation(app)["status"] == "FAILED"
    assert operation(app)["error_category"] == "TIMEOUT"
    assert service.admission.consent.storage_reliable
    assert bridge.dispatches == bridge.preflights == 0


@pytest.mark.anyio
async def test_http_disconnect_cancels_generation_and_records_unknown(app_client: Any) -> None:
    app, client, bridge = app_client
    bridge.entered, bridge.release = asyncio.Event(), asyncio.Event()
    body = json.dumps({"noteDate": DATE, "counts": COUNTS}).encode()
    delivered = False
    sent: list[dict[str, Any]] = []
    async def receive() -> dict[str, Any]:
        nonlocal delivered
        if not delivered:
            delivered = True
            return {"type": "http.request", "body": body, "more_body": False}
        await bridge.entered.wait()
        return {"type": "http.disconnect"}
    async def send(message: Any) -> None:
        sent.append(message)
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
             "method": "POST", "scheme": "http", "path": PATH, "raw_path": PATH.encode(),
             "query_string": b"", "server": ("127.0.0.1", 8000), "client": ("127.0.0.1", 99),
             "headers": [(b"host", b"127.0.0.1:8000"), (b"origin", BASE.encode()),
                         (b"content-type", b"application/json"),
                         (b"cookie", client.headers["Cookie"].encode()),
                         (b"idempotency-key", b"disconnect-intent")]}
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(app(scope, receive, send), 5)
    await app.state.quiz_service.drain()
    assert operation(app)["status"] == "UNKNOWN"
    assert_no_snapshot(app)
    assert bridge.dispatches == 1
    assert not any(message.get("status") == 201 for message in sent)


@pytest.mark.anyio
async def test_production_wiring_keeps_shared_admission_and_existing_routes(
    app_client: Any,
) -> None:
    app, client, _bridge = app_client
    assert isinstance(app.state.quiz_service, CreateQuizService)
    assert isinstance(app.state.quiz_service.admission, AiAdmissionCoordinator)
    assert app.state.quiz_service.admission is app.state.lookup_service.admission
    assert app.state.quiz_service.ledger is app.state.operation_ledger
    assert (await client.get("/api/v1/health")).status_code == 200
    assert (await client.get("/api/v1/sources")).status_code == 200
    paths = {route.path for route in app.routes if hasattr(route, "path")}
    assert {"/api/v1/lookups", "/api/v1/operations/{operation_id}",
            "/api/v1/ai-consent", PATH, PATH + "/{attemptId}"} <= paths


@pytest.mark.anyio
@pytest.mark.parametrize("blocked_body", [False, True])
async def test_body_validation_shares_deadline_and_security_headers(app_client: Any,
                                                                 monkeypatch: pytest.MonkeyPatch,
                                                                 blocked_body: bool) -> None:
    from backend.app.application import create_quiz as module
    app, client, bridge = app_client
    now = [0.0]
    if blocked_body:
        monkeypatch.setattr(module, "QUIZ_DEADLINE_SECONDS", 0.05)
    else:
        app.state.quiz_service.clock = lambda: now[0]
        app.state.quiz_service.admission.clock = lambda: now[0]
    received = False
    messages: list[dict[str, Any]] = []
    async def receive() -> dict[str, Any]:
        nonlocal received
        if received:
            await asyncio.Event().wait()
        received = True
        if blocked_body:
            return {"type": "http.request", "body": b"{", "more_body": True}
        now[0] = 60.0
        return {"type": "http.request", "body": b'{"counts":{}}', "more_body": False}
    async def send(message: Any) -> None:
        messages.append(message)
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
             "method": "POST", "scheme": "http", "path": PATH, "raw_path": PATH.encode(),
             "query_string": b"", "server": ("127.0.0.1", 8000), "client": ("127.0.0.1", 99),
             "headers": [(b"host", b"127.0.0.1:8000"), (b"origin", BASE.encode()),
                         (b"content-type", b"application/json"),
                         (b"cookie", client.headers["Cookie"].encode()),
                         (b"idempotency-key", b"body-intent")]}
    await asyncio.wait_for(app(scope, receive, send), 5)
    start = next(message for message in messages if message["type"] == "http.response.start")
    assert start["status"] == 503
    headers = dict(start["headers"])
    assert headers[b"cache-control"] == b"no-store"
    assert headers[b"x-content-type-options"] == b"nosniff"
    assert headers[b"x-frame-options"] == b"DENY"
    assert headers[b"referrer-policy"] == b"no-referrer"
    assert b"content-security-policy" in headers and b"permissions-policy" in headers
    assert bridge.dispatches == bridge.preflights == 0
    assert_no_snapshot(app)


@pytest.mark.anyio
async def test_not_granted_consent_denies_preflight(tmp_path: Path) -> None:
    app = create_app(AppSettings(storage_path=tmp_path / "not-granted.db"))
    async with (app.router.lifespan_context(app),
                AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client):
        seed_sources(app)
        app.state.active_ai_policy = policy_fixture()
        bridge = FakeBridge()
        app.state.quiz_service.admission.bridge = bridge
        await bootstrap(app, client)
        response = await post(client)
        assert response.status_code == 403
        assert response.json()["error"]["details"]["consentState"] == "NOT_GRANTED"
        assert bridge.preflights == bridge.dispatches == 0
        assert operation(app)["status"] == "FAILED"
        assert_no_snapshot(app)


@pytest.mark.anyio
async def test_restart_pending_operation_is_unknown_without_provider_replay(
    app_client: Any,
) -> None:
    app, client, bridge = app_client
    intent = CreateQuizRequest.model_validate({"noteDate": DATE, "counts": COUNTS})
    claimed = app.state.operation_ledger.claim(
        kind="QUIZ_GENERATION", key="quiz-intent", method="POST", path=PATH,
        body=intent.model_dump(by_alias=True), preconditions={},
    )
    app.state.operation_ledger.recover_pending()
    response = await post(client)
    assert response.status_code == 409
    assert response.json()["error"]["details"]["operationId"] == claimed.operation.operation_id
    assert operation(app)["status"] == "UNKNOWN"
    assert bridge.dispatches == bridge.preflights == 0
    assert_no_snapshot(app)


@pytest.mark.anyio
async def test_quiz_http_guards_and_provider_override_rejection(app_client: Any) -> None:
    _app, client, bridge = app_client
    invalid = await client.post(PATH, json={"noteDate": DATE, "counts": COUNTS})
    assert invalid.status_code == 422
    for field in ("model", "fallback", "provider", "sourceId"):
        response = await client.post(
            PATH, json={"noteDate": DATE, "counts": COUNTS, field: "hostile"},
            headers={"Idempotency-Key": field},
        )
        assert response.status_code == 422
    forbidden = await client.post(
        PATH, json={"noteDate": DATE, "counts": COUNTS},
        headers={"Idempotency-Key": "wrong-origin", "Origin": "http://hostile.test"},
    )
    assert forbidden.status_code == 403
    client.headers.pop("Cookie")
    client.cookies.clear()
    assert (await post(client)).status_code == 401
    assert bridge.dispatches == bridge.preflights == 0

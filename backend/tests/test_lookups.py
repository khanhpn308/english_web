"""T008 lookup API tests using fake admission transport and real app wiring."""

import asyncio
import hashlib
import json
import threading
import time
from collections.abc import AsyncIterator, Callable, Coroutine
from pathlib import Path
from typing import Any

import anyio
import pytest
import sqlalchemy as sa
from backend.app.application.ai_admission import AiAdmissionCoordinator
from backend.app.application.consent import ConsentApplied, ConsentService, ConsentSnapshot
from backend.app.application.operations import OperationLedger
from backend.app.enrichment.lookup import LookupService
from backend.app.main import create_app
from backend.app.platform.bridge_port import (
    BridgeAuthError,
    BridgeConfigError,
    BridgeInvalidResponseError,
    BridgeProfile,
    BridgeUnavailableError,
)
from backend.app.platform.config import AppSettings
from backend.app.vocabulary.repository import VocabularyRepository
from httpx import ASGITransport, AsyncClient

BASE = "http://127.0.0.1:8000"
ORIGIN = {"Origin": BASE}
MODEL = "gemini-3.8-flash-high"


def policy_fixture() -> dict[str, Any]:
    scopes = ["LOOKUP", "QUIZ_GENERATION", "WRITING_FEEDBACK"]
    return {
        "version": "policy-v1",
        "reviewStatus": "READY",
        "disclosureText": "Synthetic disclosure.",
        "dataCategories": ["TERM", "WORD_FORMS", "WRITING_ANSWER"],
        "recipients": ["Antigravity/Google"],
        "retentionStatement": "Configured provider terms apply.",
        "regionStatement": "Configured provider region applies.",
        "costQuotaStatement": "Configured account; no automatic fallback.",
        "withdrawalStatement": "Withdrawal cannot recall admitted data.",
        "scopes": scopes,
        "dispatchRules": [
            {
                "scope": scope,
                "providerLabel": "Antigravity/Google",
                "modelId": MODEL,
                "route": "primary",
                "billingMode": "configured-account",
            }
            for scope in scopes
        ],
        "blockedReasons": [],
    }


def provider_content(*, missing_optional: bool = False, hostile_url: str | None = None) -> str:
    form: dict[str, Any] = {
        "lemma": "robust",
        "partOfSpeech": "ADJECTIVE",
        "meaningsEn": [{"text": "able to work effectively", "verificationStatus": "VERIFIED"}],
        "meaningsVi": [{"text": "vững chắc", "verificationStatus": "VERIFIED"}],
        "examples": [
            {
                "english": "The design is robust.",
                "vietnamese": "Thiết kế rất vững chắc.",
                "verificationStatus": "VERIFIED",
            }
        ],
        "ipaUs": None if missing_optional else "/rə\u02c8bʌst/",
        "cambridgeUrl": hostile_url
        if hostile_url is not None
        else (
            None
            if missing_optional
            else "https://dictionary.cambridge.org/dictionary/english/robust"
        ),
    }
    return json.dumps({"forms": [form]})


class FakeBridge:
    test_cambridge_url: str | None = None

    def __init__(self, content: str | None = None) -> None:
        self.content = content or provider_content()
        self.preflights = 0
        self.dispatches = 0
        self.payloads: list[dict[str, Any]] = []
        self.failure: Exception | None = None
        self.profile = BridgeProfile(models=[{"id": MODEL, "owned_by": "google"}])
        self.delay: float = 0.0
        self.entered_dispatch: asyncio.Event | None = None
        self.release_dispatch: asyncio.Event | None = None
        self.dispatch_override: (
            Callable[[dict[str, Any], float], Coroutine[Any, Any, dict[str, Any]]] | None
        ) = None
        self.preflight_override: Callable[[float], Coroutine[Any, Any, BridgeProfile]] | None = None

    async def preflight(self, deadline: float) -> BridgeProfile:
        self.preflights += 1
        if self.preflight_override is not None:
            return await self.preflight_override(deadline)
        return self.profile

    async def dispatch_chat(self, payload: dict[str, Any], deadline: float) -> dict[str, Any]:
        if self.dispatch_override is not None:
            return await self.dispatch_override(payload, deadline)
        from backend.app.platform.bridge_port import BridgeInvalidResponseError

        self.dispatches += 1
        self.payloads.append(payload)
        if self.entered_dispatch is not None:
            self.entered_dispatch.set()
        if self.release_dispatch is not None:
            await self.release_dispatch.wait()
        if self.failure is not None:
            raise self.failure
        import json

        try:
            c = json.loads(self.content)
        except json.JSONDecodeError as e:
            raise BridgeInvalidResponseError("Malformed JSON response") from e
        if getattr(self, "test_cambridge_url", None) is not None:
            c["forms"][0]["cambridgeUrl"] = self.test_cambridge_url
        return {"choices": [{"message": {"content": json.dumps(c)}}]}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def app_client(tmp_path: Path) -> AsyncIterator[tuple[Any, AsyncClient, FakeBridge]]:
    policy = policy_fixture()
    app = create_app(AppSettings(storage_path=tmp_path / "lookup.db"))
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client,
    ):
        service: ConsentService = app.state.consent_service
        snapshot = service.read_consent(policy)
        assert isinstance(snapshot, ConsentSnapshot)
        granted = service.grant("consent-test-key", snapshot.etag, policy["version"], policy)
        assert isinstance(granted, ConsentApplied)
        bridge = FakeBridge()
        coordinator = AiAdmissionCoordinator(service, bridge, lambda: policy)
        app.state.lookup_service = LookupService(
            OperationLedger(app.state.database.engine),
            coordinator,
            VocabularyRepository(app.state.database.engine),
        )
        token = app.state.sessions.issue_bootstrap_token()
        exchanged = await client.post("/bootstrap/exchange", json={"token": token}, headers=ORIGIN)
        assert exchanged.status_code == 204
        client.headers.update(
            {**ORIGIN, "Cookie": exchanged.headers["set-cookie"].split(";", 1)[0]}
        )
        yield app, client, bridge


@pytest.mark.anyio
async def test_valid_lookup_persists_preview_and_replays_without_dispatch(
    app_client: tuple[Any, AsyncClient, FakeBridge],
) -> None:
    app, client, bridge = app_client
    headers = {"Idempotency-Key": "lookup-test-key-001"}
    first = await client.post("/api/v1/lookups", json={"term": "robust"}, headers=headers)
    assert first.status_code == 200
    body = first.json()
    assert body["status"] == "PREVIEW"
    assert body["operationId"].startswith("op_")
    assert body["lookupId"].startswith("lookup_")
    assert body["forms"][0]["meaningsEn"]
    assert body["forms"][0]["examples"]
    assert bridge.preflights == bridge.dispatches == 1
    payload_text = json.dumps(bridge.payloads[0], ensure_ascii=False)
    assert "lookup-test-key-001" not in payload_text
    assert "learning history" not in payload_text

    replay = await client.post("/api/v1/lookups", json={"term": "robust"}, headers=headers)
    assert replay.status_code == 200
    assert replay.json() == body
    assert bridge.dispatches == 1

    changed = await client.post("/api/v1/lookups", json={"term": "fragile"}, headers=headers)
    assert changed.status_code == 422
    assert changed.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert bridge.dispatches == 1

    with app.state.database.engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT count(*) FROM lookup_previews").scalar_one() == 1
        assert connection.exec_driver_sql("SELECT count(*) FROM word_forms").scalar_one() == 0
        assert connection.exec_driver_sql("SELECT count(*) FROM source_files").scalar_one() == 0
        assert (
            connection.exec_driver_sql(
                "SELECT status FROM operations WHERE kind='LOOKUP'"
            ).scalar_one()
            == "SUCCEEDED"
        )


@pytest.mark.anyio
async def test_missing_ipa_and_cambridge_are_missing_and_claimed_verification_is_unverified(
    app_client: tuple[Any, AsyncClient, FakeBridge],
) -> None:
    _app, client, bridge = app_client
    bridge.content = provider_content(missing_optional=True)
    response = await client.post(
        "/api/v1/lookups",
        json={"term": "robust"},
        headers={"Idempotency-Key": "lookup-missing-key-001"},
    )
    assert response.status_code == 200
    form = response.json()["forms"][0]
    assert form["ipaUs"] is None
    assert form["cambridgeUrl"] is None
    assert form["verificationSummary"] == "MISSING"
    assert form["meaningsEn"][0]["verificationStatus"] == "UNVERIFIED"
    assert form["meaningsVi"][0]["verificationStatus"] == "UNVERIFIED"
    assert form["examples"][0]["verificationStatus"] == "UNVERIFIED"
    assert bridge.dispatches == 1


@pytest.mark.anyio
async def test_malformed_provider_response_is_terminal_failure_without_preview(
    app_client: tuple[Any, AsyncClient, FakeBridge],
) -> None:
    app, client, bridge = app_client
    bridge.content = "not-json"
    response = await client.post(
        "/api/v1/lookups",
        json={"term": "robust"},
        headers={"Idempotency-Key": "lookup-malformed-key-001"},
    )
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "BRIDGE_INVALID_RESPONSE"
    with app.state.database.engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT count(*) FROM lookup_previews").scalar_one() == 0
        assert (
            connection.exec_driver_sql(
                "SELECT status FROM operations WHERE kind='LOOKUP'"
            ).scalar_one()
            == "FAILED"
        )


@pytest.mark.anyio
async def test_unknown_provider_fields_and_missing_required_fields_are_rejected(
    app_client: tuple[Any, AsyncClient, FakeBridge],
) -> None:
    _app, client, bridge = app_client
    bridge.content = json.dumps(
        {"forms": [{"lemma": "robust", "partOfSpeech": "ADJECTIVE", "meaningsEn": []}]}
    )
    missing = await client.post(
        "/api/v1/lookups",
        json={"term": "robust"},
        headers={"Idempotency-Key": "lookup-missing-schema-001"},
    )
    assert missing.status_code == 502
    assert missing.json()["error"]["code"] == "BRIDGE_INVALID_RESPONSE"

    bridge.content = json.dumps(
        {
            "forms": [
                {
                    "lemma": "robust",
                    "partOfSpeech": "ADJECTIVE",
                    "meaningsEn": [{"text": "effective", "unexpected": "hostile"}],
                    "meaningsVi": [{"text": "vững chắc"}],
                    "examples": [{"english": "x", "vietnamese": "y"}],
                }
            ]
        }
    )
    extra = await client.post(
        "/api/v1/lookups",
        json={"term": "robust"},
        headers={"Idempotency-Key": "lookup-extra-schema-001"},
    )
    assert extra.status_code == 502
    assert extra.json()["error"]["code"] == "BRIDGE_INVALID_RESPONSE"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("body", "key", "expected_status"),
    [
        ({"term": ""}, "lookup-validation-001", 422),
        ({"term": "   "}, "lookup-validation-002", 422),
        ({"term": "a"}, "lookup-validation-003", 200),
        ({"term": "a" * 80}, "lookup-validation-004", 200),
        ({"term": "a" * 81}, "lookup-validation-005", 422),
        ({"term": "   " + "a" * 80 + "   "}, "lookup-validation-006", 200),
        ({"term": "term\x00with-nul"}, "lookup-validation-007", 422),
        ({"term": "term\x07with-bel"}, "lookup-validation-008", 422),
        ({"term": "term\x7fwith-del"}, "lookup-validation-009", 422),
        ({"term": "term\x80with-c1"}, "lookup-validation-010", 422),
        ({"term": "词"}, "lookup-validation-011", 200),
        ({"term": "robust", "hostile": "ignore"}, "lookup-validation-012", 422),
    ],
)
async def test_lookup_input_validation(
    app_client: tuple[Any, AsyncClient, FakeBridge],
    body: dict[str, Any],
    key: str,
    expected_status: int,
) -> None:
    _app, client, bridge = app_client
    response = await client.post("/api/v1/lookups", json=body, headers={"Idempotency-Key": key})
    assert response.status_code == expected_status
    if expected_status != 200:
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"
        assert bridge.dispatches == 0


@pytest.mark.anyio
async def test_unicode_normalization_idempotency(
    app_client: tuple[Any, AsyncClient, FakeBridge],
) -> None:
    _app, client, bridge = app_client
    decomposed = "re\u0301sume\u0301"
    precomposed = "r\u00e9sum\u00e9"
    key = "idem-unicode-norm-1"

    # First request with decomposed Unicode
    res1 = await client.post(
        "/api/v1/lookups", json={"term": decomposed}, headers={"Idempotency-Key": key}
    )
    assert res1.status_code == 200
    assert res1.json()["term"] == precomposed
    assert bridge.dispatches == 1

    # Second request with precomposed Unicode and same idempotency key:
    # replays without second dispatch!
    res2 = await client.post(
        "/api/v1/lookups", json={"term": precomposed}, headers={"Idempotency-Key": key}
    )
    assert res2.status_code == 200
    assert res2.json()["term"] == precomposed
    assert res2.json()["lookupId"] == res1.json()["lookupId"]
    assert bridge.dispatches == 1


@pytest.mark.anyio
async def test_invalid_idempotency_key_is_rejected_before_dispatch(
    app_client: tuple[Any, AsyncClient, FakeBridge],
) -> None:
    _app, client, bridge = app_client
    response = await client.post(
        "/api/v1/lookups",
        json={"term": "robust"},
        headers={"Idempotency-Key": "bad\nkey"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert bridge.dispatches == 0


@pytest.mark.anyio
async def test_malformed_json_and_query_parameters_are_rejected_before_dispatch(
    app_client: tuple[Any, AsyncClient, FakeBridge],
) -> None:
    _app, client, bridge = app_client
    malformed = await client.post(
        "/api/v1/lookups",
        content="{",
        headers={"Content-Type": "application/json", "Idempotency-Key": "lookup-json-001"},
    )
    assert malformed.status_code == 400
    assert malformed.json()["error"]["code"] == "MALFORMED_JSON"

    query = await client.post(
        "/api/v1/lookups?unexpected=1",
        json={"term": "robust"},
        headers={"Idempotency-Key": "lookup-query-001"},
    )
    assert query.status_code == 422
    assert query.json()["error"]["code"] == "VALIDATION_ERROR"
    assert bridge.dispatches == 0


@pytest.mark.anyio
async def test_consent_denial_zero_dispatch(
    tmp_path: Path,
) -> None:
    app = create_app(AppSettings(storage_path=tmp_path / "denied.db"))
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client,
    ):
        policy = policy_fixture()
        service: ConsentService = app.state.consent_service
        bridge = FakeBridge()
        app.state.lookup_service = LookupService(
            OperationLedger(app.state.database.engine),
            AiAdmissionCoordinator(service, bridge, lambda: policy),
            VocabularyRepository(app.state.database.engine),
        )
        token = app.state.sessions.issue_bootstrap_token()
        exchanged = await client.post("/bootstrap/exchange", json={"token": token}, headers=ORIGIN)
        cookie = exchanged.headers["set-cookie"].split(";", 1)[0]

        # 1. NOT_GRANTED state
        response = await client.post(
            "/api/v1/lookups",
            json={"term": "robust"},
            headers={**ORIGIN, "Cookie": cookie, "Idempotency-Key": "lookup-denied-001"},
        )
        assert response.status_code == 403
        data = response.json()
        assert data["error"]["code"] == "AI_CONSENT_REQUIRED"
        assert data["error"]["details"]["kind"] == "AI_CONSENT"
        assert data["error"]["details"]["consentState"] == "NOT_GRANTED"
        assert data["error"]["details"]["currentPolicyVersion"] == "policy-v1"
        assert "operationId" not in data["error"]["details"]
        assert bridge.preflights == bridge.dispatches == 0

        # 2. REVOKED state
        snapshot = service.read_consent(policy)
        assert isinstance(snapshot, ConsentSnapshot)
        service.grant("grant-key-1", snapshot.etag, policy["version"], policy)
        service.revoke("revoke-key-1")

        revoked_response = await client.post(
            "/api/v1/lookups",
            json={"term": "robust"},
            headers={**ORIGIN, "Cookie": cookie, "Idempotency-Key": "lookup-denied-002"},
        )
        assert revoked_response.status_code == 403
        revoked_data = revoked_response.json()
        assert revoked_data["error"]["code"] == "AI_CONSENT_REQUIRED"
        assert revoked_data["error"]["details"]["kind"] == "AI_CONSENT"
        assert revoked_data["error"]["details"]["consentState"] == "REVOKED"
        assert revoked_data["error"]["details"]["currentPolicyVersion"] == "policy-v1"

        with app.state.database.engine.connect() as connection:
            statuses = (
                connection.exec_driver_sql(
                    "SELECT status FROM operations WHERE kind='LOOKUP' ORDER BY created_at"
                )
                .scalars()
                .all()
            )
            assert all(s == "FAILED" for s in statuses)


@pytest.mark.anyio
async def test_timeout_is_unknown_and_same_key_never_dispatches_again(
    app_client: tuple[Any, AsyncClient, FakeBridge],
) -> None:
    _app, client, bridge = app_client
    bridge.failure = BridgeUnavailableError("synthetic timeout")
    headers = {"Idempotency-Key": "lookup-timeout-key-001"}
    first = await client.post("/api/v1/lookups", json={"term": "robust"}, headers=headers)
    assert first.status_code == 503
    assert first.json()["error"]["code"] == "BRIDGE_UNAVAILABLE"
    assert bridge.dispatches == 1
    replay = await client.post("/api/v1/lookups", json={"term": "robust"}, headers=headers)
    assert replay.status_code == 409
    assert replay.json()["error"]["code"] == "IDEMPOTENCY_IN_FLIGHT"
    assert bridge.dispatches == 1


@pytest.mark.anyio
async def test_session_idempotency_key_not_in_payload(
    app_client: tuple[Any, AsyncClient, FakeBridge],
) -> None:
    _app, client, bridge = app_client
    response = await client.post(
        "/api/v1/lookups",
        json={"term": "robust"},
        headers={"Idempotency-Key": "test-payload-key"},
    )
    assert response.status_code == 200
    payload = bridge.payloads[0]
    payload_str = json.dumps(payload)
    assert "test-payload-key" not in payload_str
    assert "robust" in payload_str


@pytest.mark.anyio
async def test_session_missing_returns_401(tmp_path: Path) -> None:
    app = create_app(AppSettings(storage_path=tmp_path / "401.db"))
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client,
    ):
        response = await client.post(
            "/api/v1/lookups",
            json={"term": "robust"},
            headers={**ORIGIN, "Idempotency-Key": "no-session"},
        )
        assert response.status_code == 401


@pytest.mark.anyio
async def test_concurrent_inflight_duplicate(
    app_client: tuple[Any, AsyncClient, FakeBridge],
) -> None:
    app, client, bridge = app_client
    import sqlalchemy as sa

    bridge.entered_dispatch = asyncio.Event()
    bridge.release_dispatch = asyncio.Event()

    t1 = asyncio.create_task(
        client.post(
            "/api/v1/lookups", json={"term": "robust"}, headers={"Idempotency-Key": "inflight-1"}
        )
    )
    try:
        async with asyncio.timeout(5.0):
            await bridge.entered_dispatch.wait()
        assert not t1.done()

        res2 = await client.post(
            "/api/v1/lookups", json={"term": "robust"}, headers={"Idempotency-Key": "inflight-1"}
        )
        assert res2.status_code == 409
        body2 = res2.json()
        assert body2["error"]["code"] == "IDEMPOTENCY_IN_FLIGHT"
        assert bridge.dispatches == 1
    finally:
        bridge.release_dispatch.set()

    res1 = await t1
    assert res1.status_code == 200
    assert bridge.dispatches == 1

    with app.state.database.engine.connect() as conn:
        previews = conn.execute(sa.text("SELECT count(*) FROM lookup_previews")).scalar()
        succeeded = conn.execute(
            sa.text(
                "SELECT count(*) FROM operations WHERE status = 'SUCCEEDED' AND kind = 'LOOKUP'"
            )
        ).scalar()
        assert previews == 1
        assert succeeded == 1


@pytest.mark.anyio
async def test_privacy_safe_failure_diagnostics(
    app_client: tuple[Any, AsyncClient, FakeBridge],
    capsys: pytest.CaptureFixture[str],
) -> None:
    app, client, bridge = app_client
    import sqlalchemy as sa

    bearer_sentinel = "sentinel-bearer-secret-token-xyz-987"
    learning_sentinel = "sentinel-learning-content-secret-123-abc"
    provider_sentinel = "sentinel-provider-secret-key-456-def"

    bridge.failure = RuntimeError(
        f"Fatal error with {bearer_sentinel} {learning_sentinel} {provider_sentinel}"
    )

    capsys.readouterr()
    res = await client.post(
        "/api/v1/lookups", json={"term": "robust"}, headers={"Idempotency-Key": "priv-fail-1"}
    )
    assert res.status_code == 503
    assert res.json()["error"]["code"] == "STORAGE_BUSY"

    captured = capsys.readouterr()
    for sentinel in [bearer_sentinel, learning_sentinel, provider_sentinel]:
        assert sentinel not in captured.out
        assert sentinel not in captured.err
        assert sentinel not in res.text

    with app.state.database.engine.connect() as conn:
        row = (
            conn.execute(
                sa.text(
                    "SELECT operation_id, kind, status, error_category, response_status "
                    "FROM operations WHERE kind = 'LOOKUP' ORDER BY created_at DESC LIMIT 1"
                )
            )
            .mappings()
            .one()
        )
        for val in row.values():
            if val is not None:
                for sentinel in [bearer_sentinel, learning_sentinel, provider_sentinel]:
                    assert sentinel not in str(val)


@pytest.mark.anyio
async def test_storage_busy_and_bridge_error_variants(
    app_client: tuple[Any, AsyncClient, FakeBridge],
) -> None:
    _app, client, bridge = app_client

    bridge.failure = BridgeInvalidResponseError("invalid")
    res = await client.post(
        "/api/v1/lookups", json={"term": "robust"}, headers={"Idempotency-Key": "b1"}
    )
    assert res.status_code == 502

    bridge.failure = BridgeAuthError("auth")
    res = await client.post(
        "/api/v1/lookups", json={"term": "robust"}, headers={"Idempotency-Key": "b2"}
    )
    assert res.status_code == 502

    bridge.failure = BridgeConfigError("config")
    res = await client.post(
        "/api/v1/lookups", json={"term": "robust"}, headers={"Idempotency-Key": "b3"}
    )
    assert res.status_code == 503


@pytest.mark.anyio
async def test_unrelated_history_sentinels_zero_effects(
    app_client: tuple[Any, AsyncClient, FakeBridge],
) -> None:
    app, client, _bridge = app_client
    with app.state.database.engine.connect() as conn:
        conn.exec_driver_sql(
            "INSERT INTO source_files (id, relative_path, note_date, status, revision, etag, "
            "content_hash, last_parsed_at, error_code, created_at, updated_at) "
            "VALUES ('s1', 'path', '2025-01-01', 'VALID', 1, 'etag', 'hash', 0.0, NULL, 0.0, 0.0)"
        )
        conn.commit()

    res = await client.post(
        "/api/v1/lookups", json={"term": "robust"}, headers={"Idempotency-Key": "zero-effect"}
    )
    assert res.status_code == 200, res.json()

    with app.state.database.engine.connect() as conn:
        sources = conn.exec_driver_sql("SELECT COUNT(*) FROM source_files").scalar()
        assert sources == 1
        cards = conn.exec_driver_sql("SELECT COUNT(*) FROM review_cards").scalar()
        assert cards == 0


@pytest.mark.anyio
async def test_bearer_cookie_is_fingerprinted_not_persisted_in_raw_form(
    tmp_path: Path,
) -> None:
    app = create_app(AppSettings(storage_path=tmp_path / "bearer.db"))
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client,
    ):
        policy = policy_fixture()
        service: ConsentService = app.state.consent_service
        bridge = FakeBridge()
        app.state.lookup_service = LookupService(
            OperationLedger(app.state.database.engine),
            AiAdmissionCoordinator(service, bridge, lambda: policy),
            VocabularyRepository(app.state.database.engine),
        )

        token = app.state.sessions.issue_bootstrap_token()
        exchanged = await client.post("/bootstrap/exchange", json={"token": token}, headers=ORIGIN)
        cookie_full = exchanged.headers["set-cookie"]
        cookie = cookie_full.split(";", 1)[0]
        cookie_val = cookie.split("=")[1]

        snapshot = service.read_consent(policy)
        assert isinstance(snapshot, ConsentSnapshot)
        assert isinstance(snapshot, ConsentSnapshot)
        service.grant("consent-test-key", snapshot.etag, policy["version"], policy)

        response = await client.post(
            "/api/v1/lookups",
            json={"term": "robust"},
            headers={**ORIGIN, "Cookie": cookie, "Idempotency-Key": "bearer-1"},
        )
        assert response.status_code == 200

        # Verify raw cookie is not in payload
        payload_str = json.dumps(bridge.payloads[0])
        assert cookie_val not in payload_str

        # Verify raw cookie is not in DB
        with app.state.database.engine.connect() as conn:
            previews = conn.exec_driver_sql(
                "SELECT owner_session_id FROM lookup_previews"
            ).fetchall()
            owner_id = previews[0][0]
            assert owner_id != cookie_val
            assert cookie_val not in owner_id

            # check fingerprint logic
            expected = hashlib.sha256(f"owner:{cookie_val}".encode()).hexdigest()
            assert owner_id == expected


@pytest.mark.anyio
async def test_deadline_exhaustion_at_claim(
    app_client: tuple[Any, AsyncClient, FakeBridge],
) -> None:
    app, client, bridge = app_client
    service = app.state.lookup_service

    class MockClock:
        def __init__(self) -> None:
            self.calls = 0
            self.base = time.monotonic()

        def __call__(self) -> float:
            self.calls += 1
            if self.calls == 1:
                return self.base
            else:
                return self.base + 121

    service.clock = MockClock()

    res = await client.post(
        "/api/v1/lookups", json={"term": "robust"}, headers={"Idempotency-Key": "dl-1"}
    )
    assert res.status_code == 503, res.json()
    body = res.json()
    assert body["error"]["code"] == "BRIDGE_UNAVAILABLE"
    assert body["error"]["details"]["kind"] == "RETRY"
    assert bridge.dispatches == 0

    op_id = body["error"]["details"]["operationId"]
    with app.state.database.engine.connect() as conn:
        op = (
            conn.execute(
                sa.text(
                    "SELECT status, error_category, response_status "
                    "FROM operations WHERE operation_id = :op_id"
                ),
                {"op_id": op_id},
            )
            .mappings()
            .one()
        )
        assert op["status"] == "FAILED"
        assert op["error_category"] == "TIMEOUT"
        assert op["response_status"] == 503
        previews = conn.execute(
            sa.text("SELECT count(*) FROM lookup_previews WHERE operation_id = :op_id"),
            {"op_id": op_id},
        ).scalar()
        assert previews == 0


@pytest.mark.anyio
async def test_deadline_exhaustion_at_parse(
    app_client: tuple[Any, AsyncClient, FakeBridge],
) -> None:
    app, client, bridge = app_client
    service = app.state.lookup_service

    class MockClock:
        def __init__(self) -> None:
            self.calls = 0
            self.base = time.monotonic()

        def __call__(self) -> float:
            self.calls += 1
            if self.calls <= 3:  # up to dispatch
                return self.base
            else:
                return self.base + 121

    service.clock = MockClock()

    res = await client.post(
        "/api/v1/lookups", json={"term": "robust"}, headers={"Idempotency-Key": "dl-2"}
    )
    assert res.status_code == 503, res.json()
    body = res.json()
    assert body["error"]["code"] == "BRIDGE_UNAVAILABLE"
    assert body["error"]["details"]["kind"] == "RETRY"
    assert bridge.dispatches == 1

    op_id = body["error"]["details"]["operationId"]
    with app.state.database.engine.connect() as conn:
        op = (
            conn.execute(
                sa.text(
                    "SELECT status, error_category, response_status "
                    "FROM operations WHERE operation_id = :op_id"
                ),
                {"op_id": op_id},
            )
            .mappings()
            .one()
        )
        assert op["status"] == "UNKNOWN"
        assert op["error_category"] == "TIMEOUT"
        assert op["response_status"] == 503
        previews = conn.execute(
            sa.text("SELECT count(*) FROM lookup_previews WHERE operation_id = :op_id"),
            {"op_id": op_id},
        ).scalar()
        assert previews == 0


@pytest.mark.anyio
async def test_deadline_exhaustion_at_persistence(
    app_client: tuple[Any, AsyncClient, FakeBridge],
) -> None:
    app, client, _bridge = app_client
    service = app.state.lookup_service

    class MockClock:
        def __init__(self) -> None:
            self.calls = 0
            self.base = time.monotonic()

        def __call__(self) -> float:
            self.calls += 1
            return self.base + 121 if self.calls >= 4 else self.base

    service.clock = MockClock()

    res = await client.post(
        "/api/v1/lookups", json={"term": "robust"}, headers={"Idempotency-Key": "dl-3"}
    )
    assert res.status_code == 503, res.json()
    body = res.json()
    assert body["error"]["code"] == "BRIDGE_UNAVAILABLE"
    assert body["error"]["details"]["kind"] == "RETRY"

    op_id = body["error"]["details"]["operationId"]
    with app.state.database.engine.connect() as conn:
        op = (
            conn.execute(
                sa.text(
                    "SELECT status, error_category, response_status "
                    "FROM operations WHERE operation_id = :op_id"
                ),
                {"op_id": op_id},
            )
            .mappings()
            .one()
        )
        assert op["status"] == "UNKNOWN"
        assert op["error_category"] == "TIMEOUT"
        assert op["response_status"] == 503
        previews = conn.execute(
            sa.text("SELECT count(*) FROM lookup_previews WHERE operation_id = :op_id"),
            {"op_id": op_id},
        ).scalar()
        assert previews == 0


@pytest.mark.anyio
async def test_deadline_preview_sql_boundary(
    app_client: tuple[Any, AsyncClient, FakeBridge],
) -> None:
    app, client, _bridge = app_client
    service = app.state.lookup_service

    current_time = [time.monotonic()]
    service.clock = lambda: current_time[0]

    def _expire_deadline() -> None:
        current_time[0] += 130.0

    service.on_preview_written = _expire_deadline

    res = await client.post(
        "/api/v1/lookups",
        json={"term": "robust"},
        headers={"Idempotency-Key": "dl-preview-boundary"},
    )
    assert res.status_code == 503, res.json()
    body = res.json()
    assert body["error"]["code"] == "BRIDGE_UNAVAILABLE"
    assert body["error"]["details"]["kind"] == "RETRY"
    op_id = body["error"]["details"]["operationId"]

    with app.state.database.engine.connect() as conn:
        op = (
            conn.execute(
                sa.text(
                    "SELECT status, error_category, response_status "
                    "FROM operations WHERE operation_id = :op_id"
                ),
                {"op_id": op_id},
            )
            .mappings()
            .one()
        )
        assert op["status"] == "UNKNOWN"
        assert op["error_category"] == "TIMEOUT"
        assert op["response_status"] == 503

        previews = conn.execute(
            sa.text("SELECT count(*) FROM lookup_previews WHERE operation_id = :op_id"),
            {"op_id": op_id},
        ).scalar()
        assert previews == 0


@pytest.mark.anyio
async def test_deadline_receipt_update_boundary(
    app_client: tuple[Any, AsyncClient, FakeBridge],
) -> None:
    app, client, _bridge = app_client
    service = app.state.lookup_service

    current_time = [time.monotonic()]
    service.clock = lambda: current_time[0]

    def _expire_before_receipt() -> None:
        current_time[0] += 130.0

    service.on_before_receipt_update = _expire_before_receipt

    res = await client.post(
        "/api/v1/lookups",
        json={"term": "robust"},
        headers={"Idempotency-Key": "dl-receipt-boundary"},
    )
    assert res.status_code == 503, res.json()
    body = res.json()
    assert body["error"]["code"] == "BRIDGE_UNAVAILABLE"
    assert body["error"]["details"]["kind"] == "RETRY"
    op_id = body["error"]["details"]["operationId"]

    with app.state.database.engine.connect() as conn:
        op = (
            conn.execute(
                sa.text(
                    "SELECT status, error_category, response_status "
                    "FROM operations WHERE operation_id = :op_id"
                ),
                {"op_id": op_id},
            )
            .mappings()
            .one()
        )
        assert op["status"] == "UNKNOWN"
        assert op["error_category"] == "TIMEOUT"
        assert op["response_status"] == 503

        previews = conn.execute(
            sa.text("SELECT count(*) FROM lookup_previews WHERE operation_id = :op_id"),
            {"op_id": op_id},
        ).scalar()
        assert previews == 0


@pytest.mark.anyio
async def test_cancellation_while_completion_active(
    app_client: tuple[Any, AsyncClient, FakeBridge],
) -> None:
    app, client, _bridge = app_client
    service = app.state.lookup_service

    worker_entered = threading.Event()
    worker_release = threading.Event()

    def _pause_in_worker() -> None:
        worker_entered.set()
        worker_release.wait(timeout=5.0)

    service.on_before_receipt_update = _pause_in_worker
    service.release_commit_boundary = worker_release.set

    task = asyncio.create_task(
        client.post(
            "/api/v1/lookups",
            json={"term": "robust"},
            headers={"Idempotency-Key": "dl-cancellation-1"},
        )
    )

    try:
        await anyio.to_thread.run_sync(lambda: worker_entered.wait(timeout=5.0))
        assert worker_entered.is_set()

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        worker_release.set()

    with app.state.database.engine.connect() as conn:
        previews = conn.execute(
            sa.text("SELECT count(*) FROM lookup_previews WHERE term = 'robust'")
        ).scalar()
        assert previews == 0

        op = (
            conn.execute(
                sa.text(
                    "SELECT status, error_category, response_status FROM operations "
                    "WHERE kind = 'LOOKUP' ORDER BY created_at DESC LIMIT 1"
                )
            )
            .mappings()
            .one()
        )
        assert op["status"] == "UNKNOWN"
        assert op["error_category"] == "TIMEOUT"
        assert op["response_status"] == 503


@pytest.mark.anyio
async def test_deadline_immediately_before_db_commit(
    app_client: tuple[Any, AsyncClient, FakeBridge],
) -> None:
    app, client, _bridge = app_client
    service = app.state.lookup_service

    current_time = [time.monotonic()]
    service.clock = lambda: current_time[0]

    def _expire_at_commit() -> None:
        current_time[0] += 130.0

    service.on_before_commit = _expire_at_commit

    res = await client.post(
        "/api/v1/lookups",
        json={"term": "robust"},
        headers={"Idempotency-Key": "dl-commit-boundary-1"},
    )
    assert res.status_code == 503, res.json()
    body = res.json()
    assert body["error"]["code"] == "BRIDGE_UNAVAILABLE"
    assert body["error"]["details"]["kind"] == "RETRY"
    op_id = body["error"]["details"]["operationId"]

    with app.state.database.engine.connect() as conn:
        op = (
            conn.execute(
                sa.text(
                    "SELECT status, error_category, response_status "
                    "FROM operations WHERE operation_id = :op_id"
                ),
                {"op_id": op_id},
            )
            .mappings()
            .one()
        )
        assert op["status"] == "UNKNOWN"
        assert op["error_category"] == "TIMEOUT"
        assert op["response_status"] == 503

        previews = conn.execute(
            sa.text("SELECT count(*) FROM lookup_previews WHERE operation_id = :op_id"),
            {"op_id": op_id},
        ).scalar()
        assert previews == 0


@pytest.mark.anyio
async def test_cancellation_immediately_before_db_commit(
    app_client: tuple[Any, AsyncClient, FakeBridge],
) -> None:
    app, client, _bridge = app_client
    service = app.state.lookup_service

    commit_entered = threading.Event()
    commit_release = threading.Event()

    def _pause_in_commit() -> None:
        commit_entered.set()
        commit_release.wait(timeout=5.0)

    service.on_before_commit = _pause_in_commit
    service.release_commit_boundary = commit_release.set

    task = asyncio.create_task(
        client.post(
            "/api/v1/lookups",
            json={"term": "robust"},
            headers={"Idempotency-Key": "dl-cancellation-commit-1"},
        )
    )

    try:
        await anyio.to_thread.run_sync(lambda: commit_entered.wait(timeout=5.0))
        assert commit_entered.is_set()

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        commit_release.set()

    with app.state.database.engine.connect() as conn:
        previews = conn.execute(
            sa.text("SELECT count(*) FROM lookup_previews WHERE term = 'robust'")
        ).scalar()
        assert previews == 0

        op = (
            conn.execute(
                sa.text(
                    "SELECT status, error_category, response_status FROM operations "
                    "WHERE kind = 'LOOKUP' ORDER BY created_at DESC LIMIT 1"
                )
            )
            .mappings()
            .one()
        )
        assert op["status"] == "UNKNOWN"
        assert op["error_category"] == "TIMEOUT"
        assert op["response_status"] == 503


@pytest.mark.anyio
async def test_provider_held_beyond_hard_overall_deadline(
    app_client: tuple[Any, AsyncClient, FakeBridge],
) -> None:
    app, client, bridge = app_client
    service = app.state.lookup_service

    hang_event = asyncio.Event()

    async def _hanging_dispatch(_payload: dict[str, Any], _deadline: float) -> dict[str, Any]:
        bridge.dispatches += 1
        await hang_event.wait()
        return {}

    bridge.dispatch_override = _hanging_dispatch

    service.clock = time.monotonic
    import backend.app.enrichment.lookup as lookup_mod

    original_deadline = lookup_mod.LOOKUP_DEADLINE_SECONDS
    lookup_mod.LOOKUP_DEADLINE_SECONDS = 0.2

    try:
        res = await client.post(
            "/api/v1/lookups",
            json={"term": "robust"},
            headers={"Idempotency-Key": "dl-hang-transport-1"},
        )
        assert res.status_code == 503
        body = res.json()
        assert body["error"]["code"] == "BRIDGE_UNAVAILABLE"
        assert body["error"]["details"]["kind"] == "RETRY"
        op_id = body["error"]["details"]["operationId"]

        with app.state.database.engine.connect() as conn:
            op = (
                conn.execute(
                    sa.text(
                        "SELECT status, error_category, response_status "
                        "FROM operations WHERE operation_id = :op_id"
                    ),
                    {"op_id": op_id},
                )
                .mappings()
                .one()
            )
            assert op["status"] == "UNKNOWN"
            assert op["error_category"] == "TIMEOUT"
            assert op["response_status"] == 503

            previews = conn.execute(
                sa.text("SELECT count(*) FROM lookup_previews WHERE operation_id = :op_id"),
                {"op_id": op_id},
            ).scalar()
            assert previews == 0
    finally:
        lookup_mod.LOOKUP_DEADLINE_SECONDS = original_deadline
        hang_event.set()


@pytest.mark.anyio
async def test_provider_cancellation_durable_state(
    app_client: tuple[Any, AsyncClient, FakeBridge],
) -> None:
    app, client, bridge = app_client

    dispatch_started = asyncio.Event()
    dispatch_release = asyncio.Event()

    async def _pausing_dispatch(_payload: dict[str, Any], _deadline: float) -> dict[str, Any]:
        bridge.dispatches += 1
        dispatch_started.set()
        await dispatch_release.wait()
        return {}

    bridge.dispatch_override = _pausing_dispatch

    task = asyncio.create_task(
        client.post(
            "/api/v1/lookups",
            json={"term": "robust"},
            headers={"Idempotency-Key": "dl-cancel-provider-1"},
        )
    )

    try:
        async with asyncio.timeout(5.0):
            await dispatch_started.wait()

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        dispatch_release.set()

    with app.state.database.engine.connect() as conn:
        op = (
            conn.execute(
                sa.text(
                    "SELECT status, error_category, response_status FROM operations "
                    "WHERE kind = 'LOOKUP' ORDER BY created_at DESC LIMIT 1"
                )
            )
            .mappings()
            .one()
        )
        assert op["status"] == "UNKNOWN"
        assert op["error_category"] == "TIMEOUT"
        assert op["response_status"] == 503

        previews = conn.execute(
            sa.text("SELECT count(*) FROM lookup_previews WHERE term = 'robust'")
        ).scalar()
        assert previews == 0


@pytest.mark.anyio
async def test_request_body_time_exhausted_before_dispatch(
    app_client: tuple[Any, AsyncClient, FakeBridge],
) -> None:
    app, client, bridge = app_client

    # Simulate arrival time was recorded, but before dispatch clock advanced past 120s budget
    t0 = 1000.0
    times = [t0]

    def advance_clock() -> float:
        if times:
            return times.pop(0)
        return t0 + 125.0

    app.state.lookup_service.clock = advance_clock

    test_idempotency = "dl-body-exhausted-1"
    res = await client.post(
        "/api/v1/lookups",
        json={"term": "robust"},
        headers={"Idempotency-Key": test_idempotency},
    )
    assert res.status_code == 503
    body = res.json()
    assert body["error"]["code"] == "BRIDGE_UNAVAILABLE"
    assert bridge.dispatches == 0  # Zero provider dispatch!

    op_id = body["error"]["details"]["operationId"]
    with app.state.database.engine.connect() as conn:
        op = (
            conn.execute(
                sa.text(
                    "SELECT status, error_category, response_status "
                    "FROM operations WHERE operation_id = :op_id"
                ),
                {"op_id": op_id},
            )
            .mappings()
            .one()
        )
        assert op["status"] == "FAILED"
        assert op["error_category"] == "TIMEOUT"
        assert op["response_status"] == 503

        previews = conn.execute(
            sa.text("SELECT count(*) FROM lookup_previews WHERE operation_id = :op_id"),
            {"op_id": op_id},
        ).scalar()
        assert previews == 0


@pytest.mark.anyio
async def test_admission_payload_mutation_race(
    app_client: tuple[Any, AsyncClient, FakeBridge],
) -> None:
    app, _client, bridge = app_client
    service = app.state.lookup_service
    coordinator = service.admission

    # Create an operation record
    claimed = service.ledger.claim(
        kind="LOOKUP",
        key="race-key-1",
        method="POST",
        path="/api/v1/lookups",
        body={"term": "robust"},
        preconditions={},
    )
    op_id = claimed.operation.operation_id

    # Hook preflight to mutate the caller dictionary while preflight is in flight
    caller_payload: dict[str, Any] = {
        "messages": [{"role": "user", "content": "lookup prompt"}],
    }

    preflight_entered = asyncio.Event()
    preflight_release = asyncio.Event()

    async def _hooked_preflight(_deadline: float) -> BridgeProfile:
        preflight_entered.set()
        await preflight_release.wait()
        return bridge.profile

    bridge.preflight_override = _hooked_preflight

    dispatch_task = asyncio.create_task(
        coordinator.dispatch(
            operation_id=op_id,
            scope="LOOKUP",
            payload=caller_payload,
            deadline=time.monotonic() + 10.0,
        )
    )

    try:
        async with asyncio.timeout(5.0):
            await preflight_entered.wait()

        # Mutate the original dictionary during preflight!
        caller_payload["route"] = "injected-evil-route"
        caller_payload["provider"] = "injected-evil-provider"
        caller_payload["fallbackModel"] = "injected-evil-fallback"
        caller_payload["model"] = "injected-evil-model"
    finally:
        preflight_release.set()

    result = await dispatch_task
    assert result is not None

    # Assert that the dispatched payload contains ONLY the frozen validated fields
    dispatched = bridge.payloads[0]
    assert "route" not in dispatched
    assert "provider" not in dispatched
    assert "fallbackModel" not in dispatched
    assert dispatched["model"] == MODEL  # frozen model from rule, not injected


@pytest.mark.anyio
async def test_cambridge_url_validation(app_client: tuple[Any, AsyncClient, FakeBridge]) -> None:
    app, client, bridge = app_client
    # Add consent
    policy = app.state.lookup_service.admission.policy_source()
    snapshot = app.state.consent_service.read_consent(policy)
    app.state.consent_service.grant("consent-test-key", snapshot.etag, policy["version"], policy)

    token = app.state.sessions.issue_bootstrap_token()
    exchanged = await client.post(
        "/bootstrap/exchange", json={"token": token}, headers={"Origin": "http://127.0.0.1:8000"}
    )
    cookie = exchanged.headers["set-cookie"].split(";", 1)[0]

    # Test valid Cambridge entry
    bridge.payloads.clear()
    bridge.test_cambridge_url = "https://dictionary.cambridge.org/dictionary/english/robust"
    res = await client.post(
        "/api/v1/lookups",
        json={"term": "robust"},
        headers={
            "Origin": "http://127.0.0.1:8000",
            "Cookie": cookie,
            "Idempotency-Key": "cam-valid-1",
        },
    )
    assert res.status_code == 200, res.json()
    assert (
        res.json()["forms"][0]["cambridgeUrl"]
        == "https://dictionary.cambridge.org/dictionary/english/robust"
    )
    assert res.json()["forms"][0]["cambridgeStatus"] == "UNVERIFIED"
    assert res.json()["forms"][0]["verificationSummary"] == "UNVERIFIED"

    # Test truly absent URL
    bridge.payloads.clear()
    bridge.content = provider_content(missing_optional=True)
    bridge.test_cambridge_url = None
    res_absent = await client.post(
        "/api/v1/lookups",
        json={"term": "robust"},
        headers={
            "Origin": "http://127.0.0.1:8000",
            "Cookie": cookie,
            "Idempotency-Key": "cam-absent-1",
        },
    )
    assert res_absent.status_code == 200, res_absent.json()
    assert res_absent.json()["forms"][0]["cambridgeUrl"] is None
    assert res_absent.json()["forms"][0]["cambridgeStatus"] == "MISSING"
    assert res_absent.json()["forms"][0]["verificationSummary"] == "MISSING"

    # Test hostile supplied URLs
    hostile_urls = [
        "http://dictionary.cambridge.org/dictionary/english/robust",  # wrong scheme
        "https://evil.cambridge.org/dictionary/english/robust",  # wrong host
        "https://dictionary.cambridge.org/dictionary/english",  # empty entry
        "https://dictionary.cambridge.org/dictionary/english/",  # empty entry trailing slash
        "https://dictionary.cambridge.org/dictionary/english/../../../etc/passwd",  # traversal
        "https://dictionary.cambridge.org/dictionary/english/%2e%2e/evil",  # percent-encoded
        "https://dictionary.cambridge.org/dictionary/english/%2E%2E%2Fevil",  # uppercase
        "https://dictionary.cambridge.org/dictionary/english/%252e%252e/evil",  # double
        "https://user:pass@dictionary.cambridge.org/dictionary/english/robust",  # creds
        "https://dictionary.cambridge.org:80/dictionary/english/robust",  # port
        "https://dictionary.cambridge.org/dictionary/english/ro\nbust",  # newline
        "https://dictionary.cambridge.org/dictionary/english/ro\x7fbust",  # DEL
        "https://dictionary.cambridge.org/dictionary/english/\\\\robust",  # backslash
        "https://dictionary.cambridge.org/dictionary/english/robust%",  # incomplete percent
        "https://dictionary.cambridge.org/dictionary/english/robust%GG",  # non-hex percent
        "https://dictionary.cambridge.org/dictionary/english/robust%2",  # incomplete percent
        "https://dictionary.cambridge.org/dictionary/english/%ff",  # invalid UTF-8 byte
        "https://dictionary.cambridge.org/dictionary/english/%c3%28",  # invalid UTF-8 seq
        "https://dictionary.cambridge.org/dictionary/english/robust%25%32%66etc",  # encoded percent
        "https://dictionary.cambridge.org/dictionary/english/%25255c",  # deep backslash
        "https://dictionary.cambridge.org/dictionary/english/%25252e%25252e/x",  # deep traversal
        "https://dictionary.cambridge.org/dictionary/english/robust%2fetc",  # encoded slash
        "https://dictionary.cambridge.org/dictionary/english/robust%5cetc",  # encoded backslash
        "https://dictionary.cambridge.org/dictionary/english/robust?query=1",  # query
        "https://dictionary.cambridge.org/dictionary/english/robust#frag",  # fragment
        "https://dictionary.cambridge.org/dictionary/english/ro\x00bust",  # NUL
        "https://dictionary.cambridge.org/dictionary/english/ro\x07bust",  # BEL
        "https://dictionary.cambridge.org/dictionary/english/ro\x80bust",  # C1
    ]

    for i, url in enumerate(hostile_urls):
        bridge.content = provider_content()
        bridge.test_cambridge_url = url
        key = f"cam-hostile-{i}"
        res = await client.post(
            "/api/v1/lookups",
            json={"term": "robust"},
            headers={
                "Origin": "http://127.0.0.1:8000",
                "Cookie": cookie,
                "Idempotency-Key": key,
            },
        )
        assert res.status_code == 502, f"Failed for url {url}: {res.json()}"
        body = res.json()
        assert body["error"]["code"] == "BRIDGE_INVALID_RESPONSE"

        # Verify no preview created and operation is FAILED
        key_digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        with app.state.database.engine.connect() as conn:
            op_row = (
                conn.execute(
                    sa.text(
                        "SELECT o.operation_id, o.status, o.error_category "
                        "FROM operations o "
                        "JOIN operation_keys k ON o.operation_id = k.operation_id "
                        "WHERE k.kind = 'LOOKUP' AND k.key_digest = :digest"
                    ),
                    {"digest": key_digest},
                )
                .mappings()
                .one()
            )
            assert op_row["status"] == "FAILED"
            assert op_row["error_category"] == "BRIDGE_INVALID_RESPONSE"

            preview_count = conn.execute(
                sa.text("SELECT count(*) FROM lookup_previews WHERE operation_id = :op_id"),
                {"op_id": op_row["operation_id"]},
            ).scalar()
            assert preview_count == 0

"""T015 contract, durable SQLite races and rollback using the production app."""

import copy
import json
import re
import socket
from collections.abc import AsyncIterator, Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from threading import Barrier, Event
from typing import Any

import pytest
from alembic import command
from alembic.script import ScriptDirectory
from backend.app.application.consent import (
    ConsentApplied,
    ConsentRejected,
    ConsentService,
    ConsentSnapshot,
    resolve_policy,
)
from backend.app.application.operations import OperationLedger
from backend.app.main import create_app
from backend.app.persistence.database import Database, StorageError, migration_config
from backend.app.platform.config import AppSettings
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import Connection, event
from sqlalchemy.exc import DBAPIError

PATH = "/api/v1/ai-consent"
SCOPES = ["LOOKUP", "QUIZ_GENERATION", "WRITING_FEEDBACK"]


@pytest.fixture
def synthetic_policy() -> dict[str, Any]:
    return {
        "version": "policy-v1",
        "digest": "caller-digest-is-not-authority",
        "reviewStatus": "READY",
        "disclosureText": "Synthetic disclosure for three explicit AI actions.",
        "dataCategories": ["TERM", "WORD_FORMS", "WRITING_ANSWER"],
        "recipients": ["Antigravity/Google"],
        "retentionStatement": "Configured provider terms apply; app offers no retention guarantee.",
        "regionStatement": "Configured provider region applies; app offers no regional guarantee.",
        "costQuotaStatement": "Configured account quota; no automatic fallback or retry.",
        "withdrawalStatement": "Withdrawal blocks new actions; in-flight data cannot be recalled.",
        "scopes": SCOPES.copy(),
        "dispatchRules": [
            {
                "scope": scope,
                "providerLabel": "Antigravity/Google",
                "modelId": "gemini-3.8-flash-high",
                "route": "primary",
                "billingMode": "configured-account",
            }
            for scope in SCOPES
        ],
        "blockedReasons": [],
    }


@pytest.fixture
def database(tmp_path: Path) -> Iterator[Database]:
    db = Database(tmp_path / "consent.db")
    db.initialize()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
async def app(tmp_path: Path) -> AsyncIterator[FastAPI]:
    application = create_app(AppSettings(storage_path=tmp_path / "consent.db"))
    async with application.router.lifespan_context(application):
        yield application


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://127.0.0.1:8000",
        headers={"Origin": "http://127.0.0.1:8000"},
    ) as http:
        token = app.state.sessions.issue_bootstrap_token()
        exchanged = await http.post("/bootstrap/exchange", json={"token": token})
        assert exchanged.status_code == 204
        http.headers["Cookie"] = exchanged.headers["set-cookie"].split(";", 1)[0]
        yield http


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def deny_network(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    attempts: list[str] = []

    def denied(*_args: object, **_kwargs: object) -> None:
        attempts.append("network")
        raise AssertionError("Consent must not contact any network/provider")

    monkeypatch.setattr(socket.socket, "connect", denied)
    yield attempts
    assert attempts == []


def rows(app: FastAPI, table: str) -> list[dict[str, Any]]:
    assert table in {"ai_consent_state", "ai_consent_event", "operations", "operation_keys"}
    with app.state.database.engine.connect() as connection:
        return [
            dict(row) for row in connection.exec_driver_sql(f"SELECT * FROM {table}").mappings()
        ]


async def grant(
    client: AsyncClient, key: str = "grant-1", etag: str | None = None, version: str = "policy-v1"
) -> Response:
    if etag is None:
        etag = (await client.get(PATH)).headers["etag"]
    return await client.put(
        PATH, json={"policyVersion": version}, headers={"If-Match": etag, "Idempotency-Key": key}
    )


def error(response: Response, status: int, code: str) -> None:
    assert response.status_code == status, response.text
    assert response.json()["error"]["code"] == code
    assert response.json()["error"]["requestId"].startswith("req_")


@pytest.mark.anyio
async def test_get_initial_consent(client: AsyncClient) -> None:
    response = await client.get(PATH)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert re.fullmatch(r'"[A-Za-z0-9._-]+"', response.headers["etag"])
    assert response.json() == {
        "state": "NOT_GRANTED",
        "revision": 0,
        "acceptedPolicyVersion": None,
        "acceptedPolicyDigest": None,
        "lastChoiceAt": None,
        "policy": None,
        "canRequestAi": False,
    }


def test_application_consent_boundary_owns_read_grant_and_revoke(
    database: Database, synthetic_policy: dict[str, Any]
) -> None:
    service = ConsentService(OperationLedger(database.engine))
    initial = service.read_consent(synthetic_policy)
    assert isinstance(initial, ConsentSnapshot)
    assert initial.state.state == "NOT_GRANTED"
    applied = service.grant("boundary-grant", initial.etag, "policy-v1", synthetic_policy)
    assert isinstance(applied, ConsentApplied)
    assert applied.applied_revision == 1
    current = service.read_consent(synthetic_policy)
    assert isinstance(current, ConsentSnapshot)
    assert current.can_request_ai is True
    revoked = service.revoke("boundary-revoke")
    assert isinstance(revoked, ConsentApplied)
    assert revoked.applied_revision == 2
    withdrawn = service.read_consent(None)
    assert isinstance(withdrawn, ConsentSnapshot)
    assert withdrawn.state.state == "REVOKED"
    assert withdrawn.can_request_ai is False


@pytest.mark.parametrize("action", ["read", "grant", "revoke"])
@pytest.mark.parametrize("failure", ["sql", "storage"])
def test_application_boundary_redacts_storage_failures(
    database: Database, monkeypatch: pytest.MonkeyPatch, action: str, failure: str
) -> None:
    from sqlalchemy.exc import OperationalError

    service = ConsentService(OperationLedger(database.engine))

    def cannot_connect() -> None:
        if failure == "storage":
            raise StorageError("synthetic private database path")
        raise OperationalError("synthetic private SQL", {}, RuntimeError("private driver message"))

    result: ConsentSnapshot | ConsentApplied | ConsentRejected
    with monkeypatch.context() as patch:
        patch.setattr(database.engine, "connect", cannot_connect)
        if action == "read":
            result = service.read_consent(None)
        elif action == "grant":
            result = service.grant("failed-boundary", '"etag"', "policy-v1", None)
        else:
            result = service.revoke("failed-boundary")
    assert result == ConsentRejected((503, "STORAGE_BUSY"))
    assert service.storage_reliable is False
    assert "private" not in repr(result)
    with database.engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT revision FROM ai_consent_state").scalar() == 0
        assert connection.exec_driver_sql("SELECT count(*) FROM operations").scalar() == 0
        assert connection.exec_driver_sql("SELECT count(*) FROM ai_consent_event").scalar() == 0


@pytest.mark.anyio
@pytest.mark.parametrize("method", ["GET", "PUT", "DELETE"])
async def test_http_maps_application_rejection_without_database_access(
    client: AsyncClient, app: FastAPI, monkeypatch: pytest.MonkeyPatch, method: str
) -> None:
    def unavailable(*_args: object, **_kwargs: object) -> ConsentRejected:
        return ConsentRejected((503, "STORAGE_BUSY"))

    def forbidden_connection() -> None:
        raise AssertionError("HTTP must use the application outcome without opening storage")

    service = app.state.consent_service
    operation = {"GET": "read_consent", "PUT": "grant", "DELETE": "revoke"}[method]
    monkeypatch.setattr(service, operation, unavailable)
    monkeypatch.setattr(app.state.database.engine, "connect", forbidden_connection)
    response = await client.request(
        method,
        PATH,
        json={"policyVersion": "policy-v1"} if method == "PUT" else None,
        headers={"If-Match": '"etag"', "Idempotency-Key": "application-refusal"}
        if method == "PUT"
        else {"Idempotency-Key": "application-refusal"},
    )
    error(response, 503, "STORAGE_BUSY")
    assert "private" not in response.text


@pytest.mark.anyio
@pytest.mark.parametrize("method", ["GET", "PUT", "DELETE"])
async def test_missing_application_service_preserves_configuration_response(
    client: AsyncClient, app: FastAPI, method: str
) -> None:
    app.state.consent_service = None
    response = await client.request(
        method,
        PATH,
        json={"policyVersion": "policy-v1"} if method == "PUT" else None,
        headers={"If-Match": '"etag"', "Idempotency-Key": "missing-service"}
        if method == "PUT"
        else {"Idempotency-Key": "missing-service"},
    )
    error(response, 503, "CONFIGURATION_REQUIRED")
    assert rows(app, "ai_consent_event") == []
    assert rows(app, "operations") == []


@pytest.mark.anyio
async def test_ready_grant_structured_disclosure_and_rfc3339(
    client: AsyncClient, app: FastAPI, synthetic_policy: dict[str, Any]
) -> None:
    app.state.active_ai_policy = synthetic_policy
    initial = await client.get(PATH)
    disclosure = initial.json()["policy"]
    for field in (
        "reviewStatus",
        "disclosureText",
        "dataCategories",
        "recipients",
        "retentionStatement",
        "regionStatement",
        "costQuotaStatement",
        "withdrawalStatement",
        "scopes",
        "dispatchRules",
        "blockedReasons",
    ):
        assert disclosure[field] == synthetic_policy[field]
    definition = {key: value for key, value in synthetic_policy.items() if key != "digest"}
    canonical = json.dumps(
        definition, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )
    assert disclosure["digest"] == sha256(canonical.encode()).hexdigest()
    assert disclosure["digest"] != synthetic_policy["digest"]
    result = await grant(client, etag=initial.headers["etag"])
    assert result.status_code == 200
    assert result.json()["appliedRevision"] == 1
    current = await client.get(PATH)
    assert current.json()["state"] == "GRANTED"
    assert current.json()["canRequestAi"] is True
    assert current.json()["acceptedPolicyDigest"] == disclosure["digest"]
    timestamp = current.json()["lastChoiceAt"]
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", timestamp)
    assert datetime.fromisoformat(timestamp).tzinfo == UTC
    assert current.headers["etag"] != initial.headers["etag"]
    assert result.headers["cache-control"] == "no-store"


@pytest.mark.anyio
async def test_server_digest_is_repeatable_and_ignores_supplied_digest(
    client: AsyncClient, app: FastAPI, synthetic_policy: dict[str, Any]
) -> None:
    app.state.active_ai_policy = synthetic_policy
    first = await client.get(PATH)
    synthetic_policy["digest"] = "different-arbitrary-input"
    app.state.active_ai_policy = dict(reversed(list(synthetic_policy.items())))
    second = await client.get(PATH)
    assert first.json() == second.json()
    assert first.headers["etag"] == second.headers["etag"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "field",
    [
        "disclosureText",
        "dataCategories",
        "recipients",
        "retentionStatement",
        "regionStatement",
        "costQuotaStatement",
        "withdrawalStatement",
        "scopes",
        "dispatchRules",
        "blockedReasons",
        "reviewStatus",
    ],
)
async def test_incomplete_policy_cannot_grant(
    client: AsyncClient, app: FastAPI, synthetic_policy: dict[str, Any], field: str
) -> None:
    synthetic_policy.pop(field)
    app.state.active_ai_policy = synthetic_policy
    read = await client.get(PATH)
    assert read.status_code == 200
    assert read.json()["canRequestAi"] is False
    assert read.json()["policy"] is None or read.json()["policy"]["reviewStatus"] == "BLOCKED"
    error(await grant(client, etag=read.headers["etag"]), 503, "CONFIGURATION_REQUIRED")
    assert rows(app, "ai_consent_event") == []
    assert (await client.get(PATH)).json()["revision"] == 0


@pytest.mark.anyio
@pytest.mark.parametrize(
    "mutation",
    [
        "empty",
        "scope_missing",
        "scope_duplicate",
        "scope_extra",
        "rule_missing",
        "rule_duplicate",
        "model",
        "provider",
        "route",
        "billing",
        "blocked",
        "data_extra",
        "reasons",
        "freeform",
        "malformed",
        "missing",
    ],
)
async def test_blocked_missing_or_invalid_policy_fails_closed(
    client: AsyncClient, app: FastAPI, synthetic_policy: dict[str, Any], mutation: str
) -> None:
    policy = copy.deepcopy(synthetic_policy)
    if mutation == "empty":
        policy["retentionStatement"] = "   "
    elif mutation == "scope_missing":
        policy["scopes"].pop()
    elif mutation == "scope_duplicate":
        policy["scopes"][2] = "LOOKUP"
    elif mutation == "scope_extra":
        policy["scopes"].append("AUDIO")
    elif mutation == "rule_missing":
        policy["dispatchRules"].pop()
    elif mutation == "rule_duplicate":
        policy["dispatchRules"][2] = policy["dispatchRules"][0]
    elif mutation in {"model", "provider", "route", "billing"}:
        field = {
            "model": "modelId",
            "provider": "providerLabel",
            "route": "route",
            "billing": "billingMode",
        }[mutation]
        policy["dispatchRules"][0][field] = "unapproved"
    elif mutation == "blocked":
        policy["reviewStatus"] = "BLOCKED"
    elif mutation == "data_extra":
        policy["dataCategories"].append("HISTORY")
    elif mutation == "reasons":
        policy["blockedReasons"] = ["CLOUD_DATA_POLICY"]
    elif mutation == "freeform":
        policy = {"version": "policy-v1", "digest": "untrusted", "content": "Free-form prose"}
    app.state.active_ai_policy = (
        None if mutation == "missing" else ("malformed" if mutation == "malformed" else policy)
    )
    read = await client.get(PATH)
    assert read.status_code == 200
    assert read.json()["canRequestAi"] is False
    error(await grant(client, etag=read.headers["etag"]), 503, "CONFIGURATION_REQUIRED")
    assert rows(app, "ai_consent_event") == []


@pytest.mark.anyio
async def test_same_version_mutation_is_durable_and_requires_new_version(
    client: AsyncClient, app: FastAPI, synthetic_policy: dict[str, Any], tmp_path: Path
) -> None:
    app.state.active_ai_policy = synthetic_policy
    first = await client.get(PATH)
    assert (await grant(client, etag=first.headers["etag"])).status_code == 200
    original_history = rows(app, "ai_consent_state")[0]["policy_history"]
    synthetic_policy["disclosureText"] += " Changed scope disclosure."
    changed = await client.get(PATH)
    assert changed.json()["state"] == "STALE"
    assert changed.json()["canRequestAi"] is False
    assert changed.json()["policy"] is None or changed.json()["policy"]["reviewStatus"] == "BLOCKED"
    assert changed.headers["etag"] != first.headers["etag"]
    error(
        await grant(client, key="mutated", etag=first.headers["etag"]),
        503,
        "CONFIGURATION_REQUIRED",
    )
    assert rows(app, "ai_consent_state")[0]["policy_history"] == original_history
    synthetic_policy["disclosureText"] = first.json()["policy"]["disclosureText"]
    assert (await client.get(PATH)).json()["canRequestAi"] is False
    # Independent service/engine proves integrity rejection survives app/service restart.
    second_db = Database(tmp_path / "consent.db")
    try:
        second_db.initialize()
        service = ConsentService(OperationLedger(second_db.engine))
        with second_db.engine.connect() as connection:
            refused = service.grant_consent(
                connection, "after-restart", changed.headers["etag"], "policy-v1", synthetic_policy
            )
        assert isinstance(refused, ConsentRejected)
        assert refused.error == (503, "CONFIGURATION_REQUIRED")
    finally:
        second_db.close()
    synthetic_policy["version"] = "policy-v2"
    assert (await grant(client, key="new-version", version="policy-v2")).status_code == 200
    assert (await client.get(PATH)).json()["canRequestAi"] is True


@pytest.mark.anyio
async def test_etag_covers_effective_policy_status_and_fingerprint(
    client: AsyncClient, app: FastAPI, synthetic_policy: dict[str, Any]
) -> None:
    missing = await client.get(PATH)
    assert (await client.get(PATH)).headers["etag"] == missing.headers["etag"]
    app.state.active_ai_policy = synthetic_policy
    ready = await client.get(PATH)
    assert ready.headers["etag"] != missing.headers["etag"]
    assert "ac-r" not in ready.headers["etag"]
    assert "policy-v1" not in ready.headers["etag"]
    synthetic_policy["version"] = "policy-v2"
    version_changed = await client.get(PATH)
    assert version_changed.headers["etag"] != ready.headers["etag"]
    synthetic_policy["reviewStatus"] = "BLOCKED"
    blocked = await client.get(PATH)
    assert blocked.headers["etag"] != version_changed.headers["etag"]
    synthetic_policy["disclosureText"] += " Additional information."
    mutated = await client.get(PATH)
    assert mutated.headers["etag"] != blocked.headers["etag"]
    app.state.active_ai_policy = None
    assert (await client.get(PATH)).headers["etag"] != mutated.headers["etag"]


@pytest.mark.anyio
async def test_grant_revision_conflict_after_another_tab_revokes(
    client: AsyncClient, app: FastAPI, synthetic_policy: dict[str, Any]
) -> None:
    app.state.active_ai_policy = synthetic_policy
    tab_a = await client.get(PATH)
    revoked = await client.delete(PATH, headers={"Idempotency-Key": "tab-b-revoke"})
    assert revoked.json()["appliedRevision"] == 1
    error(await grant(client, etag=tab_a.headers["etag"]), 409, "REVISION_CONFLICT")
    assert (await client.get(PATH)).json()["state"] == "REVOKED"
    assert len(rows(app, "ai_consent_event")) == 1


@pytest.mark.anyio
async def test_grant_stale_policy_and_error_precedence(
    client: AsyncClient, app: FastAPI, synthetic_policy: dict[str, Any]
) -> None:
    app.state.active_ai_policy = synthetic_policy
    old = await client.get(PATH)
    synthetic_policy["version"] = "policy-v2"
    error(await grant(client, etag=old.headers["etag"]), 409, "AI_POLICY_CHANGED")
    error(
        await grant(
            client, key="current-version-stale-etag", version="policy-v2", etag=old.headers["etag"]
        ),
        409,
        "REVISION_CONFLICT",
    )
    app.state.active_ai_policy = None
    error(
        await grant(client, key="missing-plus-stale", etag=old.headers["etag"]),
        503,
        "CONFIGURATION_REQUIRED",
    )


@pytest.mark.anyio
@pytest.mark.parametrize("changed", ["body", "etag"])
async def test_grant_idempotency_conflict_preserves_422(
    client: AsyncClient, app: FastAPI, synthetic_policy: dict[str, Any], changed: str
) -> None:
    app.state.active_ai_policy = synthetic_policy
    initial = await client.get(PATH)
    assert (await grant(client, etag=initial.headers["etag"])).status_code == 200
    before = rows(app, "ai_consent_event")
    error(
        await grant(
            client,
            version="policy-v2" if changed == "body" else "policy-v1",
            etag='"another-etag"' if changed == "etag" else initial.headers["etag"],
        ),
        422,
        "IDEMPOTENCY_KEY_REUSED",
    )
    assert rows(app, "ai_consent_event") == before
    assert (await client.get(PATH)).json()["revision"] == 1


@pytest.mark.anyio
async def test_historical_grant_replay_after_revoke_never_restores_consent(
    client: AsyncClient, app: FastAPI, synthetic_policy: dict[str, Any]
) -> None:
    app.state.active_ai_policy = synthetic_policy
    initial = await client.get(PATH)
    granted = await grant(client, etag=initial.headers["etag"])
    assert granted.json()["appliedRevision"] == 1
    assert (await grant(client, etag=initial.headers["etag"])).json() == granted.json()
    assert len(rows(app, "ai_consent_event")) == 1
    revoked = await client.delete(PATH, headers={"Idempotency-Key": "revoke-1"})
    assert revoked.json()["appliedRevision"] == 2
    app.state.active_ai_policy = None
    replay = await grant(client, etag=initial.headers["etag"])
    assert replay.status_code == 200
    assert replay.json() == granted.json()
    replay_revoke = await client.delete(PATH, headers={"Idempotency-Key": "revoke-1"})
    assert replay_revoke.json() == revoked.json()
    assert len(rows(app, "ai_consent_event")) == 2
    current = (await client.get(PATH)).json()
    assert current["state"] == "REVOKED"
    assert current["revision"] == 2
    assert current["canRequestAi"] is False
    assert current["acceptedPolicyVersion"] is None
    assert current["acceptedPolicyDigest"] is None


@pytest.mark.anyio
async def test_in_flight_includes_operation_reference(client: AsyncClient, app: FastAPI) -> None:
    etag = (await client.get(PATH)).headers["etag"]
    ledger: OperationLedger = app.state.operation_ledger
    claimed = ledger.claim(
        kind="CONSENT_GRANT",
        key="pending",
        method="PUT",
        path=PATH,
        body={"policyVersion": "policy-v1"},
        preconditions={"If-Match": etag},
    )
    response = await grant(client, key="pending", etag=etag)
    error(response, 409, "IDEMPOTENCY_IN_FLIGHT")
    assert response.json()["error"]["details"] == {
        "kind": "RETRY",
        "operationId": claimed.operation.operation_id,
    }
    assert rows(app, "ai_consent_event") == []


@pytest.mark.anyio
@pytest.mark.parametrize("blocked", [False, True])
async def test_redundant_revoke_bumps_revision_without_policy(
    client: AsyncClient, app: FastAPI, synthetic_policy: dict[str, Any], blocked: bool
) -> None:
    if blocked:
        synthetic_policy["reviewStatus"] = "BLOCKED"
        app.state.active_ai_policy = synthetic_policy
    for number in (1, 2):
        response = await client.delete(PATH, headers={"Idempotency-Key": f"revoke-{number}"})
        assert response.status_code == 200
        assert response.json()["appliedRevision"] == number
    assert len(rows(app, "ai_consent_event")) == 2


SHAPE_CASES: list[tuple[str, dict[str, Any]]] = [
    ("GET", {"params": {"unexpected": "synthetic-raw-input"}}),
    ("PUT", {}),
    ("PUT", {"content": "{synthetic-raw-input"}),
    ("PUT", {"json": {"policyVersion": "policy-v1", "unknown": "synthetic-raw-input"}}),
    ("PUT", {"json": {"policyVersion": "INVALID/raw"}}),
    ("PUT", {"json": {"policyVersion": "a" * 81}}),
    ("PUT", {"json": {"policyVersion": "policy-v1"}, "omit": "If-Match"}),
    ("PUT", {"json": {"policyVersion": "policy-v1"}, "If-Match": "not-quoted"}),
    ("PUT", {"json": {"policyVersion": "policy-v1"}, "If-Match": "*"}),
    ("PUT", {"json": {"policyVersion": "policy-v1"}, "If-Match": 'W/"weak"'}),
    ("PUT", {"json": {"policyVersion": "policy-v1"}, "omit": "Idempotency-Key"}),
    ("PUT", {"json": {"policyVersion": "policy-v1"}, "Idempotency-Key": ""}),
    ("PUT", {"json": {"policyVersion": "policy-v1"}, "Idempotency-Key": "x" * 129}),
    ("PUT", {"json": {"policyVersion": "policy-v1"}, "Idempotency-Key": "bad\tkey"}),
    ("PUT", {"json": {"policyVersion": "policy-v1"}, "params": {"unknown": "raw"}}),
    ("DELETE", {"params": {"unknown": "raw"}}),
    ("DELETE", {"content": "synthetic-raw-input"}),
    ("DELETE", {"If-Match": '"etag"'}),
    ("DELETE", {"omit": "Idempotency-Key"}),
    ("DELETE", {"Idempotency-Key": ""}),
    ("DELETE", {"Idempotency-Key": "x" * 129}),
    ("DELETE", {"Idempotency-Key": "bad\tkey"}),
]


@pytest.mark.anyio
@pytest.mark.parametrize(("method", "options"), SHAPE_CASES)
async def test_request_shape_rejected_without_any_consent_or_policy_side_effect(
    client: AsyncClient,
    app: FastAPI,
    synthetic_policy: dict[str, Any],
    method: str,
    options: dict[str, Any],
) -> None:
    app.state.active_ai_policy = synthetic_policy
    before = rows(app, "ai_consent_state")
    options = options.copy()
    headers = (
        {"If-Match": '"valid-syntax"', "Idempotency-Key": "shape-key"}
        if method == "PUT"
        else ({"Idempotency-Key": "shape-key"} if method == "DELETE" else {})
    )
    for header in ("If-Match", "Idempotency-Key"):
        if header in options:
            headers[header] = options.pop(header)
    headers.pop(options.pop("omit", ""), None)
    response = await client.request(method, PATH, headers=headers, **options)
    error(response, 422, "VALIDATION_ERROR")
    assert "synthetic-raw-input" not in response.text
    assert rows(app, "ai_consent_state") == before
    assert rows(app, "ai_consent_event") == []
    assert rows(app, "operations") == []


@pytest.mark.anyio
async def test_session_and_origin_checks_remain_production_strength(
    client: AsyncClient, app: FastAPI
) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://127.0.0.1:8000"
    ) as other:
        error(await other.get(PATH), 401, "SESSION_REQUIRED")
    error(
        await client.delete(
            PATH, headers={"Origin": "http://hostile.invalid", "Idempotency-Key": "hostile"}
        ),
        403,
        "ORIGIN_FORBIDDEN",
    )
    assert rows(app, "ai_consent_event") == []


@pytest.mark.anyio
@pytest.mark.parametrize("action", ["grant", "revoke"])
async def test_storage_failure_rolls_back_state_event_and_receipt(
    client: AsyncClient, app: FastAPI, synthetic_policy: dict[str, Any], action: str
) -> None:
    app.state.active_ai_policy = synthetic_policy
    await client.get(PATH)
    if action == "revoke":
        assert (await grant(client)).status_code == 200
    before_state = rows(app, "ai_consent_state")
    before_events = rows(app, "ai_consent_event")
    with app.state.database.engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TRIGGER injected_failure BEFORE INSERT ON ai_consent_event "
            "BEGIN SELECT RAISE(ABORT, 'synthetic SQL/path/private-content failure'); END"
        )
    response = (
        await grant(client, key="failed-grant")
        if action == "grant"
        else await client.delete(PATH, headers={"Idempotency-Key": "failed-revoke"})
    )
    error(response, 503, "STORAGE_BUSY")
    assert "synthetic" not in response.text
    assert rows(app, "ai_consent_state") == before_state
    assert rows(app, "ai_consent_event") == before_events
    failed = [op for op in rows(app, "operations") if op["status"] != "SUCCEEDED"]
    assert len(failed) == 1
    assert failed[0]["status"] == "FAILED"
    assert failed[0]["result_ref"] is None
    assert (await client.get(PATH)).json()["canRequestAi"] is False


@pytest.mark.anyio
async def test_event_snapshots_append_only_and_receipts_redacted(
    client: AsyncClient, app: FastAPI, synthetic_policy: dict[str, Any]
) -> None:
    app.state.active_ai_policy = synthetic_policy
    granted = await grant(client)
    assert granted.status_code == 200
    event = rows(app, "ai_consent_event")[0]
    assert event["action"] == "GRANTED"
    assert event["revision"] == 1
    assert event["policy_version"] == "policy-v1"
    assert event["policy_digest"] == (await client.get(PATH)).json()["acceptedPolicyDigest"]
    assert json.loads(event["scopes"]) == SCOPES
    assert json.loads(event["dispatch_rules"]) == synthetic_policy["dispatchRules"]
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", event["created_at"])
    assert event["created_at"] == (await client.get(PATH)).json()["lastChoiceAt"]
    assert event["operation_id"] == granted.json()["operationId"]
    assert (
        await client.delete(PATH, headers={"Idempotency-Key": "revoke-snapshot"})
    ).status_code == 200
    events = rows(app, "ai_consent_event")
    assert events[0] == event
    revoke = events[1]
    assert revoke["action"] == "REVOKED"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", revoke["created_at"])
    for field in ("policy_version", "policy_digest", "scopes", "dispatch_rules"):
        assert revoke[field] is None
    for statement in (
        "UPDATE ai_consent_event SET revision=revision+20",
        "DELETE FROM ai_consent_event",
    ):
        with pytest.raises(DBAPIError), app.state.database.engine.begin() as connection:
            connection.exec_driver_sql(statement)
    for op in rows(app, "operations"):
        assert re.fullmatch(r"consent_event_ev_[a-f0-9]+", op["result_ref"])
        assert synthetic_policy["disclosureText"] not in op["result_ref"]
        assert "LOOKUP" not in op["result_ref"]
    stored_keys = json.dumps(rows(app, "operation_keys"))
    assert "revoke-snapshot" not in stored_keys


def test_fresh_0002_to_0003_migration_repeat_and_history(tmp_path: Path) -> None:
    db = Database(tmp_path / "migration.db")
    config = migration_config()
    scripts = ScriptDirectory.from_config(config)
    heads = scripts.get_heads()
    assert len(heads) == 1
    current_head = heads[0]
    consent_revision = scripts.get_revision("0003_consent")
    assert consent_revision is not None
    assert consent_revision.down_revision == "0002_operations"
    try:
        with db.engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "0002_operations")
            connection.exec_driver_sql("CREATE TABLE synthetic_history (value TEXT)")
            connection.exec_driver_sql("INSERT INTO synthetic_history VALUES ('preserved')")
            command.upgrade(config, "0003_consent")
            assert connection.exec_driver_sql("SELECT version_num FROM alembic_version").all() == [
                ("0003_consent",)
            ]
        # Exercise consent's own downgrade refusal before later migrations can refuse first.
        with (
            pytest.raises(RuntimeError, match="Downgrade is disabled"),
            db.engine.begin() as connection,
        ):
            config.attributes["connection"] = connection
            command.downgrade(config, "0002_operations")
        assert db.initialize().schema_revision == current_head
        assert db.initialize().schema_revision == current_head
        with db.engine.connect() as connection:
            state = connection.exec_driver_sql("SELECT * FROM ai_consent_state").mappings().one()
            assert state["state"] == "NOT_GRANTED"
            assert state["revision"] == 0
            assert json.loads(state["policy_history"]) == {}
            assert json.loads(state["policy_conflicts"]) == {}
            assert (
                connection.exec_driver_sql("SELECT value FROM synthetic_history").scalar_one()
                == "preserved"
            )
            columns = {
                row[1] for row in connection.exec_driver_sql("PRAGMA table_info(ai_consent_event)")
            }
            assert {"scopes", "dispatch_rules", "operation_id"} <= columns
        assert ScriptDirectory.from_config(config).get_heads() == [current_head]
    finally:
        db.close()


def service_grant(
    service: ConsentService, policy: dict[str, Any], etag: str, key: str
) -> ConsentApplied | ConsentRejected:
    with service.operations.engine.connect() as connection:
        return service.grant_consent(connection, key, etag, "policy-v1", policy)


@pytest.mark.anyio
async def test_two_independent_connections_grant_cas(
    client: AsyncClient,
    app: FastAPI,
    synthetic_policy: dict[str, Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app.state.active_ai_policy = synthetic_policy
    etag = (await client.get(PATH)).headers["etag"]
    other = Database(tmp_path / "consent.db")
    services = [
        ConsentService(OperationLedger(app.state.database.engine)),
        ConsentService(OperationLedger(other.engine)),
    ]
    original = OperationLedger.complete
    barrier = Barrier(2)

    def synchronized(self: OperationLedger, *args: Any, **kwargs: Any) -> Any:
        barrier.wait(timeout=5)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(OperationLedger, "complete", synchronized)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(service_grant, service, synthetic_policy, etag, f"race-{index}")
                for index, service in enumerate(services)
            ]
            results = [future.result(timeout=10) for future in futures]
        assert sum(isinstance(result, ConsentApplied) for result in results) == 1
        rejected = [result for result in results if isinstance(result, ConsentRejected)]
        assert rejected[0].error == (409, "REVISION_CONFLICT")
        assert (await client.get(PATH)).json()["revision"] == 1
        assert len(rows(app, "ai_consent_event")) == 1
    finally:
        other.close()


@pytest.mark.anyio
async def test_revoke_committed_between_claim_and_complete_fences_grant(
    client: AsyncClient,
    app: FastAPI,
    synthetic_policy: dict[str, Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app.state.active_ai_policy = synthetic_policy
    etag = (await client.get(PATH)).headers["etag"]
    other = Database(tmp_path / "consent.db")
    revoke_service = ConsentService(OperationLedger(other.engine))
    original = OperationLedger.complete

    def revoke_first(self: OperationLedger, operation_id: str, **kwargs: Any) -> Any:
        operation = self.get(operation_id)
        assert operation is not None
        if operation.kind == "CONSENT_GRANT":
            with other.engine.connect() as connection:
                revoked = revoke_service.revoke_consent(connection, "interleaved-revoke")
            assert isinstance(revoked, ConsentApplied)
        return original(self, operation_id, **kwargs)

    monkeypatch.setattr(OperationLedger, "complete", revoke_first)
    try:
        error(await grant(client, etag=etag), 409, "REVISION_CONFLICT")
        current = (await client.get(PATH)).json()
        assert current["state"] == "REVOKED"
        assert current["revision"] == 1
        assert current["canRequestAi"] is False
        assert len(rows(app, "ai_consent_event")) == 1
    finally:
        other.close()


@pytest.mark.anyio
async def test_malformed_same_version_fingerprint_remains_durably_blocked(
    client: AsyncClient, app: FastAPI, synthetic_policy: dict[str, Any]
) -> None:
    app.state.active_ai_policy = synthetic_policy
    assert (await grant(client)).status_code == 200
    original = copy.deepcopy(synthetic_policy)
    before = await client.get(PATH)
    synthetic_policy["dispatchRules"][0]["modelId"] = "unapproved"
    malformed = await client.get(PATH)
    assert malformed.json()["state"] == "STALE"
    assert malformed.headers["etag"] != before.headers["etag"]
    synthetic_policy["dispatchRules"][0]["modelId"] = "another-unapproved"
    assert (await client.get(PATH)).headers["etag"] != malformed.headers["etag"]
    app.state.active_ai_policy = original
    assert (await client.get(PATH)).json()["canRequestAi"] is False
    error(await grant(client, key="restored-invalid-version"), 503, "CONFIGURATION_REQUIRED")


@pytest.mark.anyio
async def test_policy_change_after_claim_is_checked_inside_completion(
    client: AsyncClient,
    app: FastAPI,
    synthetic_policy: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app.state.active_ai_policy = synthetic_policy
    initial = await client.get(PATH)
    original = OperationLedger.complete

    def change_first(self: OperationLedger, operation_id: str, **kwargs: Any) -> Any:
        app.state.active_ai_policy = {**synthetic_policy, "version": "policy-v2"}
        return original(self, operation_id, **kwargs)

    monkeypatch.setattr(OperationLedger, "complete", change_first)
    error(await grant(client, etag=initial.headers["etag"]), 409, "AI_POLICY_CHANGED")
    assert rows(app, "ai_consent_event") == []
    assert rows(app, "ai_consent_state")[0]["revision"] == 0


@pytest.mark.anyio
async def test_receipt_failure_after_event_write_rolls_back_all_local_effects(
    client: AsyncClient, app: FastAPI, synthetic_policy: dict[str, Any]
) -> None:
    app.state.active_ai_policy = synthetic_policy
    before = await client.get(PATH)
    original_state = rows(app, "ai_consent_state")
    with app.state.database.engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TRIGGER injected_receipt_failure BEFORE UPDATE ON operations "
            "WHEN NEW.status='SUCCEEDED' "
            "BEGIN SELECT RAISE(ABORT, 'synthetic receipt failure'); END"
        )
    response = await grant(client, etag=before.headers["etag"])
    error(response, 503, "STORAGE_BUSY")
    assert rows(app, "ai_consent_state") == original_state
    assert rows(app, "ai_consent_event") == []
    assert rows(app, "operations")[0]["status"] == "FAILED"
    assert rows(app, "operations")[0]["result_ref"] is None


@pytest.mark.anyio
async def test_policy_history_cannot_be_removed_or_modified(
    client: AsyncClient, app: FastAPI, synthetic_policy: dict[str, Any]
) -> None:
    app.state.active_ai_policy = synthetic_policy
    await client.get(PATH)
    before = rows(app, "ai_consent_state")
    for column in ("policy_history", "policy_conflicts"):
        if column == "policy_conflicts":
            synthetic_policy["disclosureText"] += " changed"
            await client.get(PATH)
            before = rows(app, "ai_consent_state")
        with pytest.raises(DBAPIError), app.state.database.engine.begin() as connection:
            connection.exec_driver_sql(f"UPDATE ai_consent_state SET {column}='{{}}'")
        assert rows(app, "ai_consent_state") == before


@pytest.mark.anyio
@pytest.mark.parametrize(
    "corruption", ["event", "history", "definition", "history_missing", "singleton", "receipt"]
)
async def test_missing_or_corrupt_grant_evidence_cannot_authorize(
    client: AsyncClient, app: FastAPI, synthetic_policy: dict[str, Any], corruption: str
) -> None:
    app.state.active_ai_policy = synthetic_policy
    assert (await grant(client)).status_code == 200
    with app.state.database.engine.begin() as connection:
        if corruption == "event":
            connection.exec_driver_sql("DROP TRIGGER append_only_consent_delete")
            connection.exec_driver_sql("DELETE FROM ai_consent_event")
        elif corruption == "singleton":
            connection.exec_driver_sql("DROP TRIGGER preserve_consent_singleton")
            connection.exec_driver_sql("DELETE FROM ai_consent_state")
        elif corruption == "receipt":
            connection.exec_driver_sql("UPDATE operations SET response_status=NULL")
        elif corruption == "history_missing":
            connection.exec_driver_sql("DROP TRIGGER immutable_policy_history")
            connection.exec_driver_sql("UPDATE ai_consent_state SET policy_history='{}'")
        else:
            connection.exec_driver_sql("DROP TRIGGER immutable_policy_history")
            history = json.loads(rows(app, "ai_consent_state")[0]["policy_history"])
            if corruption == "definition":
                history["policy-v1"]["definition"]["disclosureText"] += " corrupted"
            else:
                history["policy-v1"]["digest"] = "corrupt-digest"
            connection.exec_driver_sql(
                "UPDATE ai_consent_state SET policy_history=?", (json.dumps(history),)
            )
    current = await client.get(PATH)
    assert current.status_code in (200, 503)
    if current.status_code == 200:
        assert current.json()["canRequestAi"] is False
        assert current.json()["state"] in {"STALE", "NOT_GRANTED"}
    else:
        error(current, 503, "STORAGE_BUSY")


@pytest.mark.anyio
async def test_get_body_rejected(client: AsyncClient, app: FastAPI) -> None:
    before = rows(app, "ai_consent_state")
    error(await client.request("GET", PATH, content="synthetic-raw-input"), 422, "VALIDATION_ERROR")
    assert rows(app, "ai_consent_state") == before


@pytest.mark.anyio
async def test_rejected_mutation_records_the_observed_policy_even_if_configuration_reverts(
    client: AsyncClient,
    app: FastAPI,
    synthetic_policy: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app.state.active_ai_policy = synthetic_policy
    initial = await client.get(PATH)
    original_policy = copy.deepcopy(synthetic_policy)
    synthetic_policy["withdrawalStatement"] += " Changed policy."
    original_snapshot = ConsentService.get_snapshot

    def revert_first(self: ConsentService, source: object) -> Any:
        app.state.active_ai_policy = original_policy
        return original_snapshot(self, source)

    monkeypatch.setattr(ConsentService, "get_snapshot", revert_first)
    error(await grant(client, etag=initial.headers["etag"]), 503, "CONFIGURATION_REQUIRED")
    error(await grant(client, key="must-change-version"), 503, "CONFIGURATION_REQUIRED")
    assert rows(app, "ai_consent_event") == []
    assert "policy-v1" in json.loads(rows(app, "ai_consent_state")[0]["policy_conflicts"])


@pytest.mark.anyio
@pytest.mark.parametrize("method", ["PUT", "DELETE"])
async def test_connection_open_failure_is_redacted_and_fail_closed(
    client: AsyncClient, app: FastAPI, monkeypatch: pytest.MonkeyPatch, method: str
) -> None:
    from sqlalchemy.exc import OperationalError

    def cannot_connect() -> None:
        raise OperationalError("synthetic SQL/private path", {}, RuntimeError("private-content"))

    monkeypatch.setattr(app.state.database.engine, "connect", cannot_connect)
    response = await client.request(
        method,
        PATH,
        json={"policyVersion": "policy-v1"} if method == "PUT" else None,
        headers={"If-Match": '"syntactic-etag"', "Idempotency-Key": "failed-open"}
        if method == "PUT"
        else {"Idempotency-Key": "failed-open"},
    )
    error(response, 503, "STORAGE_BUSY")
    assert "synthetic" not in response.text
    assert "private" not in response.text
    assert app.state.consent_service.storage_reliable is False


@pytest.mark.anyio
async def test_ambiguous_failure_after_commit_preserves_receipt_and_blocks_ai(
    client: AsyncClient,
    app: FastAPI,
    synthetic_policy: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sqlalchemy.exc import OperationalError

    app.state.active_ai_policy = synthetic_policy
    initial = await client.get(PATH)
    original = OperationLedger.complete

    def lose_response(self: OperationLedger, *args: Any, **kwargs: Any) -> None:
        original(self, *args, **kwargs)
        raise OperationalError("synthetic commit acknowledgement", {}, RuntimeError("private"))

    monkeypatch.setattr(OperationLedger, "complete", lose_response)
    refused = await grant(client, etag=initial.headers["etag"])
    error(refused, 503, "STORAGE_BUSY")
    committed = rows(app, "operations")[0]
    assert committed["status"] == "SUCCEEDED"
    replay = await grant(client, etag=initial.headers["etag"])
    assert replay.json() == {"operationId": committed["operation_id"], "appliedRevision": 1}
    assert len(rows(app, "ai_consent_event")) == 1
    assert (await client.get(PATH)).json()["canRequestAi"] is False


@pytest.mark.anyio
async def test_first_seen_malformed_version_requires_new_version_when_corrected(
    client: AsyncClient, app: FastAPI, synthetic_policy: dict[str, Any]
) -> None:
    valid = copy.deepcopy(synthetic_policy)
    synthetic_policy.pop("dispatchRules")
    app.state.active_ai_policy = synthetic_policy
    first = await client.get(PATH)
    assert first.json()["canRequestAi"] is False
    app.state.active_ai_policy = valid
    error(await grant(client, key="corrected-same-version"), 503, "CONFIGURATION_REQUIRED")
    valid["version"] = "policy-v2"
    assert (
        await grant(client, key="corrected-new-version", version="policy-v2")
    ).status_code == 200


@pytest.mark.anyio
async def test_every_exposed_policy_digest_matches_its_complete_definition(
    client: AsyncClient, app: FastAPI, synthetic_policy: dict[str, Any]
) -> None:
    app.state.active_ai_policy = synthetic_policy
    synthetic_policy["retentionStatement"] = ""
    exposed = (await client.get(PATH)).json()["policy"]
    if exposed is not None:
        digest = exposed.pop("digest")
        canonical = json.dumps(
            exposed, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        )
        assert digest == sha256(canonical.encode()).hexdigest()
        assert exposed["reviewStatus"] == "BLOCKED"


@pytest.mark.anyio
async def test_replace_cannot_bypass_immutable_history(
    client: AsyncClient, app: FastAPI, synthetic_policy: dict[str, Any]
) -> None:
    app.state.active_ai_policy = synthetic_policy
    assert (await grant(client)).status_code == 200
    before_state = rows(app, "ai_consent_state")
    before_events = rows(app, "ai_consent_event")
    statements = [
        "INSERT OR REPLACE INTO ai_consent_state SELECT * FROM ai_consent_state",
        "INSERT OR REPLACE INTO ai_consent_event SELECT * FROM ai_consent_event",
    ]
    for statement in statements:
        with pytest.raises(DBAPIError), app.state.database.engine.begin() as connection:
            connection.exec_driver_sql(statement)
    assert rows(app, "ai_consent_state") == before_state
    assert rows(app, "ai_consent_event") == before_events


@pytest.mark.anyio
async def test_unrecordable_storage_failure_stays_pending_and_never_succeeds(
    client: AsyncClient, app: FastAPI, synthetic_policy: dict[str, Any]
) -> None:
    app.state.active_ai_policy = synthetic_policy
    before = await client.get(PATH)
    with app.state.database.engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TRIGGER injected_any_receipt_failure BEFORE UPDATE ON operations "
            "BEGIN SELECT RAISE(ABORT, 'synthetic disk failure'); END"
        )
    response = await grant(client, etag=before.headers["etag"])
    error(response, 503, "STORAGE_BUSY")
    assert rows(app, "ai_consent_event") == []
    assert rows(app, "ai_consent_state")[0]["revision"] == 0
    assert rows(app, "operations")[0]["status"] == "PENDING"
    error(await grant(client, etag=before.headers["etag"]), 409, "IDEMPOTENCY_IN_FLIGHT")
    assert (await client.get(PATH)).json()["canRequestAi"] is False


@pytest.mark.anyio
@pytest.mark.parametrize("etag", ['"opaque:/!~"', '""'])
async def test_syntactically_valid_opaque_etag_is_a_revision_conflict(
    client: AsyncClient, app: FastAPI, synthetic_policy: dict[str, Any], etag: str
) -> None:
    app.state.active_ai_policy = synthetic_policy
    error(await grant(client, etag=etag), 409, "REVISION_CONFLICT")
    assert rows(app, "ai_consent_state")[0]["revision"] == 0
    assert rows(app, "ai_consent_event") == []


def test_native_retry_schema_requires_discriminator() -> None:
    schema = create_app().openapi()["components"]["schemas"]["ConsentRetryDetails"]
    assert "kind" in schema["required"]


def test_consent_get_declares_validation_errors_in_openapi() -> None:
    responses = create_app().openapi()["paths"][PATH]["get"]["responses"]
    assert "422" in responses


@pytest.mark.anyio
async def test_startup_storage_failure_has_storage_taxonomy_with_production_guards(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken_storage(_self: Database) -> None:
        raise StorageError("UNAVAILABLE")

    monkeypatch.setattr(Database, "initialize", broken_storage)
    application = create_app(AppSettings(storage_path=tmp_path / "failed-start.db"))
    async with (
        application.router.lifespan_context(application),
        AsyncClient(
            transport=ASGITransport(app=application),
            base_url="http://127.0.0.1:8000",
            headers={"Origin": "http://127.0.0.1:8000"},
        ) as http,
    ):
        error(await http.get(PATH), 401, "SESSION_REQUIRED")
        token = application.state.sessions.issue_bootstrap_token()
        exchanged = await http.post("/bootstrap/exchange", json={"token": token})
        assert exchanged.status_code == 204
        http.headers["Cookie"] = exchanged.headers["set-cookie"].split(";", 1)[0]
        error(await http.get(PATH), 503, "STORAGE_BUSY")
        error(
            await http.put(
                PATH,
                json={"policyVersion": "policy-v1"},
                headers={"If-Match": '"valid-syntax"', "Idempotency-Key": "failed-start-grant"},
            ),
            503,
            "STORAGE_BUSY",
        )
        error(
            await http.delete(PATH, headers={"Idempotency-Key": "failed-start-revoke"}),
            503,
            "STORAGE_BUSY",
        )
        assert application.state.consent_service is None
        assert application.state.ready is False


@pytest.mark.anyio
@pytest.mark.parametrize("policy_change", ["missing", "blocked", "new_version"])
async def test_valid_grant_becomes_stale_when_active_policy_is_no_longer_accepted(
    client: AsyncClient, app: FastAPI, synthetic_policy: dict[str, Any], policy_change: str
) -> None:
    app.state.active_ai_policy = synthetic_policy
    initial = await client.get(PATH)
    assert (await grant(client, etag=initial.headers["etag"])).status_code == 200
    if policy_change == "missing":
        app.state.active_ai_policy = None
    else:
        synthetic_policy["version"] = "policy-v2"
        if policy_change == "blocked":
            synthetic_policy["reviewStatus"] = "BLOCKED"
            synthetic_policy["blockedReasons"] = ["CLOUD_DATA_POLICY"]
    current = await client.get(PATH)
    assert (current.json()["state"], current.json()["canRequestAi"]) == ("STALE", False)
    assert current.json()["acceptedPolicyDigest"] == initial.json()["policy"]["digest"]
    if policy_change == "new_version":
        error(
            await grant(client, key="stale-policy", etag=initial.headers["etag"]),
            409,
            "AI_POLICY_CHANGED",
        )
    else:
        error(
            await grant(client, key="stale-policy", etag=current.headers["etag"]),
            503,
            "CONFIGURATION_REQUIRED",
        )
    assert (await client.delete(PATH, headers={"Idempotency-Key": "withdraw-stale"})).json()[
        "appliedRevision"
    ] == 2


def duplicate_policy_registry(history: str, changed: dict[str, Any]) -> str:
    prior = json.loads(history)["policy-v1"]
    policy, _, _, digest = resolve_policy(changed)
    assert policy is not None
    replacement = {"digest": digest, "definition": policy.model_dump(exclude={"digest"})}
    entries = [
        json.dumps(entry, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        for entry in (prior, replacement)
    ]
    return '{"policy-v1":' + entries[0] + ',"policy-v1":' + entries[1] + "}"


@pytest.mark.anyio
@pytest.mark.parametrize("bypass_trigger", [False, True])
async def test_duplicate_registry_version_cannot_rebind_an_observed_policy(
    client: AsyncClient, app: FastAPI, synthetic_policy: dict[str, Any], bypass_trigger: bool
) -> None:
    app.state.active_ai_policy = synthetic_policy
    initial = await client.get(PATH)
    history = rows(app, "ai_consent_state")[0]["policy_history"]
    synthetic_policy["disclosureText"] += " Mutated before first grant."
    duplicate = duplicate_policy_registry(history, synthetic_policy)
    if bypass_trigger:
        with app.state.database.engine.begin() as connection:
            connection.exec_driver_sql("DROP TRIGGER immutable_policy_history")
            connection.exec_driver_sql("UPDATE ai_consent_state SET policy_history=?", (duplicate,))
        current = await client.get(PATH)
        refused = await grant(client, etag=current.headers.get("etag", initial.headers["etag"]))
        error(current, 503, "STORAGE_BUSY")
        error(refused, 503, "STORAGE_BUSY")
        assert rows(app, "ai_consent_event") == []
        assert rows(app, "ai_consent_state")[0]["revision"] == 0
    else:
        with pytest.raises(DBAPIError), app.state.database.engine.begin() as connection:
            connection.exec_driver_sql("UPDATE ai_consent_state SET policy_history=?", (duplicate,))
        assert rows(app, "ai_consent_state")[0]["policy_history"] == history


@pytest.mark.anyio
async def test_blob_event_identity_is_a_typed_storage_failure(
    client: AsyncClient, app: FastAPI, synthetic_policy: dict[str, Any]
) -> None:
    app.state.active_ai_policy = synthetic_policy
    assert (await grant(client)).status_code == 200
    with app.state.database.engine.begin() as connection:
        connection.exec_driver_sql("DROP TRIGGER append_only_consent_update")
        connection.exec_driver_sql("UPDATE ai_consent_event SET event_id=?", (b"invalid",))
    error(await client.get(PATH), 503, "STORAGE_BUSY")
    assert app.state.consent_service.storage_reliable is False


@pytest.mark.anyio
async def test_key_reuse_422_matches_the_generated_error_schema(
    client: AsyncClient, app: FastAPI, synthetic_policy: dict[str, Any]
) -> None:
    app.state.active_ai_policy = synthetic_policy
    initial = await client.get(PATH)
    assert (await grant(client, etag=initial.headers["etag"])).status_code == 200
    reused = await grant(client, etag='"different"')
    error(reused, 422, "IDEMPOTENCY_KEY_REUSED")
    # The existing T017 generic 422 schema permits FIELD_ERRORS, while 409/503
    # have consent's native RETRY schema. Key reuse needs no reconciliation detail.
    assert "details" not in reused.json()["error"]


@pytest.mark.anyio
@pytest.mark.parametrize("method", ["GET", "PUT", "DELETE"])
async def test_production_guards_precede_every_consent_route(
    client: AsyncClient, app: FastAPI, synthetic_policy: dict[str, Any], method: str
) -> None:
    app.state.active_ai_policy = synthetic_policy
    before = rows(app, "ai_consent_state")
    headers = {"Idempotency-Key": "denied-session"}
    options: dict[str, Any] = {}
    if method == "PUT":
        headers["If-Match"] = '"valid-syntax"'
        options["json"] = {"policyVersion": "policy-v1"}
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://127.0.0.1:8000"
    ) as no_session:
        error(
            await no_session.request(
                method, PATH, headers={**headers, "Origin": "http://127.0.0.1:8000"}, **options
            ),
            401,
            "SESSION_REQUIRED",
        )
    error(
        await client.request(
            method, PATH, headers={**headers, "Origin": "http://hostile.invalid"}, **options
        ),
        403,
        "ORIGIN_FORBIDDEN",
    )
    assert rows(app, "ai_consent_state") == before
    assert rows(app, "ai_consent_event") == []
    assert rows(app, "operations") == []


@pytest.mark.anyio
@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE ai_consent_state SET state='STALE'",
        "UPDATE ai_consent_state SET revision=-1",
        "UPDATE ai_consent_state SET last_choice_at=123.0",
        "UPDATE ai_consent_state SET state='REVOKED'",
    ],
)
async def test_migration_rejects_invalid_durable_state_shapes(app: FastAPI, statement: str) -> None:
    before = rows(app, "ai_consent_state")
    with pytest.raises(DBAPIError), app.state.database.engine.begin() as connection:
        connection.exec_driver_sql(statement)
    assert rows(app, "ai_consent_state") == before


@pytest.mark.anyio
@pytest.mark.parametrize("field", ["last_choice_at", "created_at"])
async def test_invalid_calendar_time_in_storage_is_redacted(
    client: AsyncClient, app: FastAPI, synthetic_policy: dict[str, Any], field: str
) -> None:
    app.state.active_ai_policy = synthetic_policy
    assert (await grant(client)).status_code == 200
    with app.state.database.engine.begin() as connection:
        table = "ai_consent_state" if field == "last_choice_at" else "ai_consent_event"
        if field == "created_at":
            connection.exec_driver_sql("DROP TRIGGER append_only_consent_update")
        connection.exec_driver_sql(f"UPDATE {table} SET {field}='2026-13-99T00:00:00Z'")
    error(await client.get(PATH), 503, "STORAGE_BUSY")
    assert app.state.consent_service.storage_reliable is False


@pytest.mark.anyio
@pytest.mark.parametrize("field", ["dataCategories", "recipients", "scopes", "dispatchRules"])
async def test_policy_collection_order_cannot_change_digest_or_invalidate_grant(
    client: AsyncClient, app: FastAPI, synthetic_policy: dict[str, Any], field: str
) -> None:
    synthetic_policy["recipients"] = ["Antigravity/Google", "Configured provider"]
    app.state.active_ai_policy = synthetic_policy
    initial = await client.get(PATH)
    assert (await grant(client, etag=initial.headers["etag"])).status_code == 200
    granted = await client.get(PATH)
    synthetic_policy[field].reverse()
    reordered = await client.get(PATH)
    assert reordered.json()["state"] == "GRANTED"
    assert reordered.json()["canRequestAi"] is True
    assert reordered.json()["acceptedPolicyDigest"] == initial.json()["policy"]["digest"]
    assert reordered.headers["etag"] == granted.headers["etag"]


@pytest.mark.parametrize(
    "field",
    [
        "version",
        "reviewStatus",
        "disclosureText",
        "dataCategories",
        "recipients",
        "retentionStatement",
        "regionStatement",
        "costQuotaStatement",
        "withdrawalStatement",
        "scopes",
        "dispatchRules",
        "blockedReasons",
    ],
)
def test_every_material_policy_field_changes_the_canonical_digest(
    synthetic_policy: dict[str, Any], field: str
) -> None:
    original = resolve_policy(synthetic_policy)[3]
    if field == "version":
        synthetic_policy[field] = "policy-v2"
    elif field == "reviewStatus":
        synthetic_policy[field] = "BLOCKED"
    elif field == "blockedReasons":
        synthetic_policy[field] = ["CLOUD_DATA_POLICY"]
    elif isinstance(synthetic_policy[field], list):
        synthetic_policy[field].pop()
    else:
        synthetic_policy[field] += " Material change."
    assert resolve_policy(synthetic_policy)[3] != original


@pytest.mark.anyio
async def test_storage_failure_latch_cannot_be_cleared_by_a_later_grant(
    client: AsyncClient, app: FastAPI, synthetic_policy: dict[str, Any]
) -> None:
    app.state.active_ai_policy = synthetic_policy
    initial = await client.get(PATH)
    app.state.consent_service.storage_reliable = False
    error(await grant(client, etag=initial.headers["etag"]), 503, "STORAGE_BUSY")
    assert rows(app, "ai_consent_state")[0]["revision"] == 0
    assert rows(app, "ai_consent_event") == []


@pytest.mark.anyio
@pytest.mark.parametrize("method", ["GET", "PUT", "DELETE"])
async def test_all_consent_routes_have_zero_bridge_provider_and_external_transport_calls(
    client: AsyncClient,
    app: FastAPI,
    synthetic_policy: dict[str, Any],
    method: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.adapters.bridge import BridgeAdapter
    from httpx import AsyncHTTPTransport, HTTPTransport

    calls: list[str] = []

    def forbidden(*_args: Any, **_kwargs: Any) -> None:
        calls.append("forbidden transport")
        raise AssertionError("Consent crossed an external/bridge boundary")

    for name in ("preflight", "dispatch_chat"):
        monkeypatch.setattr(BridgeAdapter, name, forbidden)
    monkeypatch.setattr(HTTPTransport, "handle_request", forbidden)
    monkeypatch.setattr(AsyncHTTPTransport, "handle_async_request", forbidden)
    app.state.active_ai_policy = synthetic_policy
    if method == "PUT":
        response = await grant(client)
    elif method == "DELETE":
        response = await client.delete(PATH, headers={"Idempotency-Key": "zero-provider"})
    else:
        response = await client.get(PATH)
    assert response.status_code == 200
    assert calls == []


@pytest.mark.anyio
@pytest.mark.parametrize("corruption", ["singleton", "event", "receipt", "identity", "time"])
async def test_corrupt_storage_cannot_be_repaired_by_a_new_grant(
    client: AsyncClient, app: FastAPI, synthetic_policy: dict[str, Any], corruption: str
) -> None:
    app.state.active_ai_policy = synthetic_policy
    assert (await grant(client)).status_code == 200
    before = await client.get(PATH)
    with app.state.database.engine.begin() as connection:
        if corruption == "singleton":
            connection.exec_driver_sql("DROP TRIGGER preserve_consent_singleton")
            connection.exec_driver_sql("DELETE FROM ai_consent_state")
        elif corruption == "event":
            connection.exec_driver_sql("DROP TRIGGER append_only_consent_delete")
            connection.exec_driver_sql("DELETE FROM ai_consent_event")
        elif corruption == "receipt":
            connection.exec_driver_sql("UPDATE operations SET response_status=NULL")
        elif corruption == "identity":
            connection.exec_driver_sql(
                "UPDATE ai_consent_state SET accepted_policy_digest=?", ("0" * 64,)
            )
        else:
            connection.exec_driver_sql(
                "UPDATE ai_consent_state SET last_choice_at='2000-01-01T00:00:00Z'"
            )
    corrupted_state = rows(app, "ai_consent_state")
    corrupted_events = rows(app, "ai_consent_event")
    error(await client.get(PATH), 503, "STORAGE_BUSY")
    error(
        await grant(client, key="repair-must-fail", etag=before.headers["etag"]),
        503,
        "STORAGE_BUSY",
    )
    error(
        await client.delete(PATH, headers={"Idempotency-Key": "corrupt-revoke"}),
        503,
        "STORAGE_BUSY",
    )
    assert rows(app, "ai_consent_state") == corrupted_state
    assert rows(app, "ai_consent_event") == corrupted_events
    assert all(op["status"] != "SUCCEEDED" for op in rows(app, "operations")[1:])


@pytest.mark.anyio
async def test_successful_receipt_without_its_event_is_a_storage_failure(
    client: AsyncClient, app: FastAPI, synthetic_policy: dict[str, Any]
) -> None:
    app.state.active_ai_policy = synthetic_policy
    initial = await client.get(PATH)
    assert (await grant(client, etag=initial.headers["etag"])).status_code == 200
    with app.state.database.engine.begin() as connection:
        connection.exec_driver_sql("DROP TRIGGER append_only_consent_delete")
        connection.exec_driver_sql("DELETE FROM ai_consent_event")
    error(await grant(client, etag=initial.headers["etag"]), 503, "STORAGE_BUSY")
    assert app.state.consent_service.storage_reliable is False
    assert rows(app, "ai_consent_state")[0]["revision"] == 1


@pytest.mark.anyio
async def test_zero_row_cas_cannot_write_event_or_success_receipt(
    client: AsyncClient, app: FastAPI, synthetic_policy: dict[str, Any]
) -> None:
    app.state.active_ai_policy = synthetic_policy
    initial = await client.get(PATH)
    with app.state.database.engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TRIGGER ignore_cas BEFORE UPDATE OF revision ON ai_consent_state "
            "BEGIN SELECT RAISE(IGNORE); END"
        )
    error(await grant(client, etag=initial.headers["etag"]), 409, "REVISION_CONFLICT")
    assert rows(app, "ai_consent_state")[0]["revision"] == 0
    assert rows(app, "ai_consent_event") == []
    assert rows(app, "operations")[0]["status"] == "FAILED"
    assert rows(app, "operations")[0]["result_ref"] is None


@pytest.mark.anyio
async def test_overlapping_sqlite_writer_transactions_order_revoke_before_stale_grant(
    client: AsyncClient,
    app: FastAPI,
    synthetic_policy: dict[str, Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app.state.active_ai_policy = synthetic_policy
    etag = (await client.get(PATH)).headers["etag"]
    other = Database(tmp_path / "consent.db", busy_timeout_ms=5000)
    grant_service = ConsentService(OperationLedger(other.engine))
    revoke_service: ConsentService = app.state.consent_service
    claimed, revoke_written, grant_begin, grant_callback = Event(), Event(), Event(), Event()
    connections: list[object] = []
    original = OperationLedger.complete

    def on_begin(
        conn: Connection,
        _cursor: Any,
        statement: str,
        _parameters: Any,
        _context: Any,
        _executemany: bool,
    ) -> None:
        if claimed.is_set() and statement == "BEGIN IMMEDIATE":
            connections.append(conn.connection.dbapi_connection)
            grant_begin.set()

    event.listen(other.engine, "before_cursor_execute", on_begin)

    def ordered(self: OperationLedger, operation_id: str, **kwargs: Any) -> Any:
        write = kwargs["local_write"]
        if self is grant_service.operations:
            claimed.set()
            assert revoke_written.wait(timeout=5)

            def grant_write(conn: Connection) -> None:
                grant_callback.set()
                write(conn)

            kwargs["local_write"] = grant_write
        else:
            assert claimed.wait(timeout=5)

            def revoke_write(conn: Connection) -> None:
                connections.append(conn.connection.dbapi_connection)
                write(conn)
                revoke_written.set()
                assert grant_begin.wait(timeout=5)
                assert not grant_callback.is_set()

            kwargs["local_write"] = revoke_write
        return original(self, operation_id, **kwargs)

    monkeypatch.setattr(OperationLedger, "complete", ordered)

    def revoke() -> ConsentApplied | ConsentRejected:
        with revoke_service.operations.engine.connect() as conn:
            return revoke_service.revoke_consent(conn, "overlapping-revoke")

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            stale = pool.submit(service_grant, grant_service, synthetic_policy, etag, "overlap")
            withdrawn = pool.submit(revoke)
            assert isinstance(withdrawn.result(timeout=10), ConsentApplied)
            rejected = stale.result(timeout=10)
        assert isinstance(rejected, ConsentRejected)
        assert rejected.error == (409, "REVISION_CONFLICT")
        assert connections[0] is not connections[1]
        assert grant_callback.is_set()
        current = (await client.get(PATH)).json()
        assert (current["state"], current["revision"], current["canRequestAi"]) == (
            "REVOKED",
            1,
            False,
        )
        assert [entry["action"] for entry in rows(app, "ai_consent_event")] == ["REVOKED"]
        assert sum(op["status"] == "SUCCEEDED" for op in rows(app, "operations")) == 1
    finally:
        event.remove(other.engine, "before_cursor_execute", on_begin)
        other.close()

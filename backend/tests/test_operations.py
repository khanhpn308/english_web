"""T014 durable operation ledger tests use temporary synthetic SQLite databases."""

import sqlite3
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from typing import TypedDict
from unittest.mock import patch

import pytest
from alembic import command
from alembic.script import ScriptDirectory
from backend.app.application.operations import ClaimResult, OperationConflict, OperationLedger
from backend.app.main import create_app
from backend.app.persistence.database import Database, migration_config
from backend.app.platform.config import AppSettings
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Connection
from sqlalchemy.exc import OperationalError


class Intent(TypedDict):
    kind: str
    key: str
    method: str
    path: str
    body: dict[str, object]
    preconditions: dict[str, object]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def test_operations_migration_is_the_single_head_and_creates_permanent_keys(tmp_path: Path) -> None:
    database = Database(tmp_path / "operations.db")
    try:
        heads = ScriptDirectory.from_config(migration_config()).get_heads()
        assert len(heads) == 1
        current_head = heads[0]
        info = database.initialize()
        assert info.schema_revision == current_head
        with database.engine.connect() as connection:
            assert (
                connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one()
                == current_head
            )
            tables = {
                row[0]
                for row in connection.exec_driver_sql(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            assert {"alembic_version", "operations", "operation_keys"}.issubset(tables)
            key_columns = connection.exec_driver_sql("PRAGMA table_info(operation_keys)").all()
            assert [(column[1], column[5]) for column in key_columns if column[5]] == [
                ("kind", 1),
                ("key_digest", 2),
            ]
    finally:
        database.close()


def test_existing_0001_database_upgrades_without_losing_history(tmp_path: Path) -> None:
    path = tmp_path / "existing.db"
    config = migration_config()
    config.set_main_option("sqlalchemy.url", "sqlite:///" + str(path))
    command.upgrade(config, "0001_storage")
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE synthetic_history (value TEXT)")
        connection.execute("INSERT INTO synthetic_history VALUES ('preserved')")
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "0001_storage",
        )

    database = Database(path)
    try:
        current_head = ScriptDirectory.from_config(migration_config()).get_heads()[0]
        assert database.initialize().schema_revision == current_head
        with database.engine.connect() as connection:
            result_val = connection.exec_driver_sql("SELECT value FROM synthetic_history")
            value: str = result_val.scalar_one()
            assert value == "preserved"
            result_cnt = connection.exec_driver_sql("SELECT count(*) FROM operation_keys")
            count: int = result_cnt.scalar_one()
            assert count == 0
    finally:
        database.close()


@pytest.fixture
def database(tmp_path: Path) -> Iterator[Database]:
    instance = Database(tmp_path / "ledger.db")
    instance.initialize()
    try:
        yield instance
    finally:
        instance.close()


def test_claim_replay_and_changed_body_have_one_atomic_effect(database: Database) -> None:
    ledger = OperationLedger(database.engine)
    with database.engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE synthetic_revision (revision INTEGER NOT NULL)")
        connection.exec_driver_sql("INSERT INTO synthetic_revision VALUES (1)")

    first = ledger.claim(
        kind="LOOKUP",
        key="synthetic-key-001",
        method="POST",
        path="/api/v1/lookups",
        body={"term": "synthetic-private-answer", "count": 1},
        preconditions={"policyDigest": "policy-synthetic"},
    )
    assert first.replayed is False
    assert first.operation.status == "PENDING"
    assert first.operation.operation_id.startswith("op_")

    with pytest.raises(OperationConflict) as in_flight:
        ledger.claim(
            kind="LOOKUP",
            key="synthetic-key-001",
            method="POST",
            path="/api/v1/lookups",
            body={"count": 1, "term": "synthetic-private-answer"},
            preconditions={"policyDigest": "policy-synthetic"},
        )
    assert in_flight.value.status_code == 409
    assert in_flight.value.code == "IDEMPOTENCY_IN_FLIGHT"
    assert in_flight.value.operation_id == first.operation.operation_id

    with pytest.raises(OperationConflict) as reused:
        ledger.claim(
            kind="LOOKUP",
            key="synthetic-key-001",
            method="POST",
            path="/api/v1/lookups",
            body={"term": "different"},
            preconditions={"policyDigest": "policy-synthetic"},
        )
    assert reused.value.status_code == 422
    assert reused.value.code == "IDEMPOTENCY_KEY_REUSED"
    with pytest.raises(OperationConflict) as changed_precondition:
        ledger.claim(
            kind="LOOKUP",
            key="synthetic-key-001",
            method="POST",
            path="/api/v1/lookups",
            body={"term": "synthetic-private-answer", "count": 1},
            preconditions={"policyDigest": "changed-policy"},
        )
    assert changed_precondition.value.code == "IDEMPOTENCY_KEY_REUSED"

    def advance_revision(connection: Connection) -> None:
        connection.exec_driver_sql("UPDATE synthetic_revision SET revision=revision+1")

    completed = ledger.complete(
        first.operation.operation_id,
        response_status=200,
        result_ref="lookup_synthetic_1",
        local_write=advance_revision,
    )
    assert completed.status == "SUCCEEDED"
    assert completed.result_ref == "lookup_synthetic_1"
    assert completed.response_status == 200

    replay = ledger.claim(
        kind="LOOKUP",
        key="synthetic-key-001",
        method="POST",
        path="/api/v1/lookups",
        body={"count": 1, "term": "synthetic-private-answer"},
        preconditions={"policyDigest": "policy-synthetic"},
    )
    assert replay.replayed is True
    assert replay.operation == completed
    with database.engine.connect() as connection:
        assert (
            connection.exec_driver_sql("SELECT revision FROM synthetic_revision").scalar_one() == 2
        )
        assert connection.exec_driver_sql("SELECT count(*) FROM operation_keys").scalar_one() == 1
        stored = "\n".join(
            row[0] for row in connection.exec_driver_sql("SELECT sql FROM sqlite_master") if row[0]
        )
        stored += str(connection.exec_driver_sql("SELECT * FROM operation_keys").all())
        assert "synthetic-private-answer" not in stored
        assert "synthetic-key-001" not in stored


def test_lost_response_after_commit_replays_same_receipt_after_reopen(tmp_path: Path) -> None:
    path = tmp_path / "lost-response.db"
    original = Database(path)
    original.initialize()
    try:
        ledger = OperationLedger(original.engine)
        claimed = ledger.claim(
            kind="SAVE",
            key="stable-retry-key",
            method="POST",
            path="/api/v1/word-forms",
            body={"lookupId": "synthetic"},
            preconditions={"If-None-Match": "*"},
        )
        completed = ledger.complete(
            claimed.operation.operation_id,
            response_status=201,
            result_ref="save_synthetic_1",
        )
    finally:
        original.close()

    reopened = Database(path)
    try:
        reopened.initialize()
        replay = OperationLedger(reopened.engine).claim(
            kind="SAVE",
            key="stable-retry-key",
            method="POST",
            path="/api/v1/word-forms",
            body={"lookupId": "synthetic"},
            preconditions={"If-None-Match": "*"},
        )
        assert replay.replayed is True
        assert replay.operation == completed
        with reopened.engine.connect() as connection:
            assert connection.exec_driver_sql("SELECT count(*) FROM operations").scalar_one() == 1
    finally:
        reopened.close()


@pytest.mark.parametrize("key", ["", "bad\nkey", "k" * 129])
def test_invalid_key_never_creates_an_intent(database: Database, key: str) -> None:
    with pytest.raises(ValueError, match="Invalid idempotency key"):
        OperationLedger(database.engine).claim(
            kind="LOOKUP",
            key=key,
            method="POST",
            path="/api/v1/lookups",
            body={"term": "synthetic"},
            preconditions={},
        )
    with database.engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT count(*) FROM operation_keys").scalar_one() == 0


def test_two_database_connections_race_to_claim_one_key(tmp_path: Path) -> None:
    path = tmp_path / "race.db"
    first_db = Database(path, busy_timeout_ms=5000)
    second_db = Database(path, busy_timeout_ms=5000)
    first_db.initialize()
    barrier = Barrier(2)

    def attempt(database: Database) -> ClaimResult | OperationConflict:
        barrier.wait()
        try:
            return OperationLedger(database.engine).claim(
                kind="LOOKUP",
                key="race-key",
                method="POST",
                path="/api/v1/lookups",
                body={"term": "synthetic"},
                preconditions={},
            )
        except OperationConflict as conflict:
            return conflict

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            left = pool.submit(attempt, first_db)
            right = pool.submit(attempt, second_db)
            results = [left.result(), right.result()]
        claims = [result for result in results if isinstance(result, ClaimResult)]
        conflicts = [result for result in results if isinstance(result, OperationConflict)]
        assert len(claims) == 1 and claims[0].replayed is False
        assert len(conflicts) == 1 and conflicts[0].code == "IDEMPOTENCY_IN_FLIGHT"
        assert conflicts[0].operation_id == claims[0].operation.operation_id
        with first_db.engine.connect() as connection:
            assert connection.exec_driver_sql("SELECT count(*) FROM operations").scalar_one() == 1
            assert (
                connection.exec_driver_sql("SELECT count(*) FROM operation_keys").scalar_one() == 1
            )
    finally:
        first_db.close()
        second_db.close()


def test_restart_marks_pending_unknown_and_never_reclaims_it(tmp_path: Path) -> None:
    path = tmp_path / "restart.db"
    first_db = Database(path)
    first_db.initialize()
    try:
        original = OperationLedger(first_db.engine).claim(
            kind="LOOKUP",
            key="lost-response-key",
            method="POST",
            path="/api/v1/lookups",
            body={"term": "synthetic"},
            preconditions={},
        )
    finally:
        first_db.close()

    restarted = Database(path)
    try:
        restarted.initialize()
        ledger = OperationLedger(restarted.engine)
        assert ledger.recover_pending() == 1
        assert ledger.recover_pending() == 0
        recovered = ledger.get(original.operation.operation_id)
        assert recovered is not None and recovered.status == "UNKNOWN"
        with pytest.raises(OperationConflict) as blocked:
            ledger.claim(
                kind="LOOKUP",
                key="lost-response-key",
                method="POST",
                path="/api/v1/lookups",
                body={"term": "synthetic"},
                preconditions={},
            )
        assert blocked.value.status_code == 409
        assert blocked.value.operation_id == original.operation.operation_id
        with restarted.engine.connect() as connection:
            assert connection.exec_driver_sql("SELECT count(*) FROM operations").scalar_one() == 1
    finally:
        restarted.close()


def test_failed_local_write_rolls_back_revision_and_receipt(database: Database) -> None:
    ledger = OperationLedger(database.engine)
    with database.engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE synthetic_revision (revision INTEGER NOT NULL)")
        connection.exec_driver_sql("INSERT INTO synthetic_revision VALUES (1)")
    claimed = ledger.claim(
        kind="SAVE",
        key="disk-full-synthetic",
        method="POST",
        path="/api/v1/word-forms",
        body={"lookupId": "synthetic"},
        preconditions={},
    )

    def fail_after_revision(connection: Connection) -> None:
        connection.exec_driver_sql("UPDATE synthetic_revision SET revision=revision+1")
        raise sqlite3.OperationalError("database or disk is full")

    with pytest.raises(sqlite3.OperationalError, match="database or disk is full"):
        ledger.complete(
            claimed.operation.operation_id,
            response_status=201,
            result_ref="save_synthetic_1",
            local_write=fail_after_revision,
        )
    pending = ledger.get(claimed.operation.operation_id)
    assert pending is not None and pending.status == "PENDING" and pending.result_ref is None
    with database.engine.connect() as connection:
        assert (
            connection.exec_driver_sql("SELECT revision FROM synthetic_revision").scalar_one() == 1
        )
        assert connection.exec_driver_sql("SELECT count(*) FROM operation_keys").scalar_one() == 1


def test_permanent_key_survives_missing_receipt_fault_injection(database: Database) -> None:
    ledger = OperationLedger(database.engine)
    intent: Intent = {
        "kind": "LOOKUP",
        "key": "never-reuse-key",
        "method": "POST",
        "path": "/api/v1/lookups",
        "body": {"term": "synthetic"},
        "preconditions": {},
    }
    first = ledger.claim(**intent)
    ledger.complete(
        first.operation.operation_id, response_status=200, result_ref="lookup_synthetic_1"
    )
    # v1 has no receipt expiry. This corrupt-copy probe removes only the receipt fields.
    with database.engine.begin() as connection:
        connection.exec_driver_sql(
            "UPDATE operations SET result_ref=NULL, response_status=NULL WHERE operation_id=?",
            (first.operation.operation_id,),
        )
    with pytest.raises(OperationConflict) as blocked:
        ledger.claim(**intent)
    assert blocked.value.status_code == 409
    assert blocked.value.operation_id == first.operation.operation_id
    with pytest.raises(OperationConflict) as no_second_completion:
        ledger.complete(
            first.operation.operation_id,
            response_status=200,
            result_ref="lookup_synthetic_2",
        )
    assert no_second_completion.value.status_code == 409
    with database.engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT count(*) FROM operation_keys").scalar_one() == 1
        assert connection.exec_driver_sql("SELECT count(*) FROM operations").scalar_one() == 1


def test_known_failure_replays_and_unknown_outcome_blocks_retry(database: Database) -> None:
    ledger = OperationLedger(database.engine)
    first_intent: Intent = {
        "kind": "LOOKUP",
        "key": "failed-key",
        "method": "POST",
        "path": "/api/v1/lookups",
        "body": {"term": "synthetic"},
        "preconditions": {},
    }
    first = ledger.claim(**first_intent)
    failed = ledger.record_failure(
        first.operation.operation_id, error_category="BRIDGE_UNAVAILABLE", response_status=503
    )
    assert failed.status == "FAILED"
    assert failed.error_category == "BRIDGE_UNAVAILABLE"
    replay = ledger.claim(**first_intent)
    assert replay.replayed is True and replay.operation == failed

    unknown_intent = first_intent.copy()
    unknown_intent["key"] = "unknown-key"
    second = ledger.claim(**unknown_intent)
    unknown = ledger.record_failure(
        second.operation.operation_id,
        error_category="TIMEOUT",
        response_status=503,
        unknown=True,
    )
    assert unknown.status == "UNKNOWN"
    with pytest.raises(OperationConflict) as blocked:
        ledger.claim(**unknown_intent)
    assert blocked.value.status_code == 409
    assert blocked.value.operation_id == second.operation.operation_id


@pytest.mark.anyio
async def test_get_operation_is_session_protected_redacted_and_missing_is_typed_404(
    tmp_path: Path,
) -> None:
    app = create_app(AppSettings(storage_path=tmp_path / "api.db"))
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://127.0.0.1:8000") as client,
    ):
        claimed = app.state.operation_ledger.claim(
            kind="LOOKUP",
            key="synthetic-private-idempotency-key",
            method="POST",
            path="/api/v1/lookups",
            body={"term": "synthetic-private-answer"},
            preconditions={},
        )
        operation_id = claimed.operation.operation_id
        unauthenticated = await client.get(f"/api/v1/operations/{operation_id}")
        assert unauthenticated.status_code == 401
        assert unauthenticated.json()["error"]["code"] == "SESSION_REQUIRED"

        token = app.state.sessions.issue_bootstrap_token()
        exchanged = await client.post(
            "/bootstrap/exchange",
            json={"token": token},
            headers={"Origin": "http://127.0.0.1:8000"},
        )
        cookie = exchanged.headers["set-cookie"].split(";", 1)[0]
        response = await client.get(
            f"/api/v1/operations/{operation_id}", headers={"Cookie": cookie}
        )
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert response.json() == {
            "operationId": operation_id,
            "kind": "LOOKUP",
            "status": "PENDING",
            "createdAt": claimed.operation.created_at,
            "updatedAt": claimed.operation.updated_at,
        }
        assert "synthetic-private-answer" not in response.text
        assert "synthetic-private-idempotency-key" not in response.text
        assert token not in response.text

        unexpected_query = await client.get(
            f"/api/v1/operations/{operation_id}?extra=synthetic", headers={"Cookie": cookie}
        )
        assert unexpected_query.status_code == 400
        assert unexpected_query.json()["error"]["code"] == "INVALID_QUERY"

        missing = await client.get("/api/v1/operations/op_missing", headers={"Cookie": cookie})
        assert missing.status_code == 404
        assert missing.json()["error"]["code"] == "NOT_FOUND"
        assert missing.json()["error"]["requestId"].startswith("req_")

        database_error = OperationalError(
            "SELECT synthetic-private-sql", {}, sqlite3.OperationalError("database is locked")
        )
        with patch.object(app.state.operation_ledger, "get", side_effect=database_error):
            unavailable = await client.get(
                f"/api/v1/operations/{operation_id}", headers={"Cookie": cookie}
            )
        assert unavailable.status_code == 503
        assert unavailable.json()["error"]["code"] == "STORAGE_BUSY"
        assert "synthetic-private-sql" not in unavailable.text


@pytest.mark.anyio
async def test_app_restart_exposes_unknown_without_reclaim(tmp_path: Path) -> None:
    path = tmp_path / "restart-api.db"
    database = Database(path)
    database.initialize()
    try:
        claimed = OperationLedger(database.engine).claim(
            kind="LOOKUP",
            key="pending-after-crash",
            method="POST",
            path="/api/v1/lookups",
            body={"term": "synthetic"},
            preconditions={},
        )
    finally:
        database.close()

    app = create_app(AppSettings(storage_path=path))
    async with app.router.lifespan_context(app):
        recovered = app.state.operation_ledger.get(claimed.operation.operation_id)
        assert recovered is not None and recovered.status == "UNKNOWN"
        with pytest.raises(OperationConflict) as blocked:
            app.state.operation_ledger.claim(
                kind="LOOKUP",
                key="pending-after-crash",
                method="POST",
                path="/api/v1/lookups",
                body={"term": "synthetic"},
                preconditions={},
            )
        assert blocked.value.status_code == 409

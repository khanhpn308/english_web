"""T016 uses real SQLite, synthetic policies, and transport barriers only."""

import asyncio
import copy
import multiprocessing
import socket
from collections.abc import Callable, Iterator
from datetime import datetime
from multiprocessing.connection import Connection as PipeConnection
from multiprocessing.synchronize import Event as ProcessEvent
from pathlib import Path
from time import monotonic
from typing import Any

import pytest
from alembic import command
from alembic.script import ScriptDirectory
from backend.app.application.ai_admission import AiAdmissionCoordinator
from backend.app.application.consent import ConsentApplied, ConsentService, ConsentSnapshot
from backend.app.application.operations import OperationConflict, OperationLedger
from backend.app.persistence.database import Database, migration_config
from backend.app.platform.bridge_port import BridgeProfile, BridgeUnavailableError
from sqlalchemy import Connection, event
from sqlalchemy.exc import DBAPIError, OperationalError

SCOPES = ["LOOKUP", "QUIZ_GENERATION", "WRITING_FEEDBACK"]
MODEL = "gemini-3.8-flash-high"
TABLE = "ai_operation_admission"
PAYLOAD = {"messages": [{"role": "user", "content": "synthetic-private-content"}]}


def policy_fixture() -> dict[str, Any]:
    return {
        "version": "policy-v1",
        "reviewStatus": "READY",
        "disclosureText": "Synthetic disclosure for the three AI scopes.",
        "dataCategories": ["TERM", "WORD_FORMS", "WRITING_ANSWER"],
        "recipients": ["Antigravity/Google"],
        "retentionStatement": "Configured provider terms apply.",
        "regionStatement": "Configured provider region applies.",
        "costQuotaStatement": "Configured account; no automatic fallback.",
        "withdrawalStatement": "Withdrawal cannot recall admitted data.",
        "scopes": SCOPES.copy(),
        "dispatchRules": [
            {
                "scope": scope,
                "providerLabel": "Antigravity/Google",
                "modelId": MODEL,
                "route": "primary",
                "billingMode": "configured-account",
            }
            for scope in SCOPES
        ],
        "blockedReasons": [],
    }


class FakeBridge:
    def __init__(self) -> None:
        self.profile = BridgeProfile(models=[{"id": MODEL, "owned_by": "google"}])
        self.preflights = 0
        self.dispatches = 0
        self.deadlines: list[float] = []
        self.payloads: list[dict[str, Any]] = []
        self.after_preflight: Callable[[], None] | None = None
        self.at_dispatch: Callable[[], None] | None = None
        self.failure: Exception | None = None

    async def preflight(self, deadline: float) -> BridgeProfile:
        self.preflights += 1
        self.deadlines.append(deadline)
        if self.after_preflight:
            self.after_preflight()
        return self.profile

    async def dispatch_chat(self, payload: dict[str, Any], deadline: float) -> dict[str, Any]:
        self.dispatches += 1
        self.deadlines.append(deadline)
        self.payloads.append(payload)
        if self.at_dispatch:
            self.at_dispatch()
        if self.failure:
            raise self.failure
        return {"model": MODEL, "synthetic": "completed"}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def deny_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("T016 must use fake bridge transport")

    monkeypatch.setattr(socket.socket, "connect", forbidden)


@pytest.fixture
def database(tmp_path: Path) -> Iterator[Database]:
    db = Database(tmp_path / "admission.db")
    db.initialize()
    try:
        yield db
    finally:
        db.close()


def grant(service: ConsentService, policy: dict[str, Any], key: str = "grant") -> None:
    snapshot = service.read_consent(policy)
    assert isinstance(snapshot, ConsentSnapshot)
    result = service.grant(key, snapshot.etag, policy["version"], policy)
    assert isinstance(result, ConsentApplied)


def claim(ledger: OperationLedger, scope: str = "LOOKUP", key: str = "intent") -> str:
    return ledger.claim(
        kind=scope, key=key, method="POST", path="/synthetic-ai", body=PAYLOAD, preconditions={}
    ).operation.operation_id


def admissions(db: Database) -> list[dict[str, Any]]:
    with db.engine.connect() as conn:
        return [dict(row) for row in conn.exec_driver_sql(f"SELECT * FROM {TABLE}").mappings()]


async def dispatch(
    coordinator: AiAdmissionCoordinator,
    operation_id: str,
    scope: str = "LOOKUP",
    deadline: float | None = None,
) -> dict[str, Any]:
    return await coordinator.dispatch(
        operation_id=operation_id,
        scope=scope,
        payload=PAYLOAD,
        deadline=deadline if deadline is not None else monotonic() + 30,
    )


@pytest.mark.anyio
@pytest.mark.parametrize("scope", SCOPES)
async def test_valid_scope_records_exact_identity_and_one_dispatch(
    database: Database, scope: str
) -> None:
    ledger = OperationLedger(database.engine)
    service = ConsentService(ledger)
    policy = policy_fixture()
    grant(service, policy)
    snapshot = service.get_snapshot(policy)
    operation_id = claim(ledger, scope)
    bridge = FakeBridge()
    coordinator = AiAdmissionCoordinator(service, bridge, lambda: policy)
    deadline = monotonic() + 30
    original = copy.deepcopy(PAYLOAD)
    result = await dispatch(coordinator, operation_id, scope, deadline)
    assert result["synthetic"] == "completed"
    assert bridge.preflights == bridge.dispatches == 1
    assert bridge.deadlines == [deadline, deadline]
    assert bridge.payloads[0]["model"] == MODEL
    assert original == PAYLOAD
    row = admissions(database)[0]
    assert {key: row[key] for key in row if key != "admitted_at"} == {
        "operation_id": operation_id,
        "consent_revision": 1,
        "policy_version": "policy-v1",
        "policy_digest": snapshot.state.accepted_policy_digest,
        "scope": scope,
        "provider_label": "Antigravity/Google",
        "model_id": MODEL,
        "route": "primary",
        "billing_mode": "configured-account",
        "admission_state": "ADMITTED",
    }
    assert datetime.fromisoformat(row["admitted_at"]).utcoffset() is not None
    assert "synthetic-private-content" not in str(row)
    operation = ledger.get(operation_id)
    assert operation is not None and operation.status == "PENDING"


@pytest.mark.anyio
@pytest.mark.parametrize("state", ["NOT_GRANTED", "REVOKED", "STALE"])
async def test_consent_denied_before_preflight(database: Database, state: str) -> None:
    ledger = OperationLedger(database.engine)
    service = ConsentService(ledger)
    policy = policy_fixture()
    if state != "NOT_GRANTED":
        grant(service, policy)
    if state == "REVOKED":
        assert isinstance(service.revoke("revoke"), ConsentApplied)
    elif state == "STALE":
        policy["version"] = "policy-v2"
    bridge = FakeBridge()
    with pytest.raises(OperationConflict) as denied:
        await dispatch(AiAdmissionCoordinator(service, bridge, lambda: policy), claim(ledger))
    assert denied.value.code == "AI_CONSENT_REQUIRED"
    assert bridge.preflights == bridge.dispatches == 0
    assert admissions(database) == []


@pytest.mark.anyio
@pytest.mark.parametrize(
    "mutation", ["missing", "blocked", "invalid", "incomplete", "same_version"]
)
async def test_policy_denial_before_preflight(database: Database, mutation: str) -> None:
    ledger = OperationLedger(database.engine)
    service = ConsentService(ledger)
    policy = policy_fixture()
    grant(service, policy)
    if mutation == "blocked":
        policy["version"] = "blocked-v2"
        policy["reviewStatus"] = "BLOCKED"
    elif mutation == "invalid":
        policy["dispatchRules"][0]["modelId"] = "unapproved"
    elif mutation == "incomplete":
        policy.pop("dispatchRules")
    elif mutation == "same_version":
        policy["disclosureText"] += " Changed."
    source = None if mutation == "missing" else policy
    bridge = FakeBridge()
    with pytest.raises(OperationConflict) as denied:
        await dispatch(AiAdmissionCoordinator(service, bridge, source), claim(ledger))
    assert denied.value.code == "CONFIGURATION_REQUIRED"
    assert bridge.preflights == bridge.dispatches == 0
    assert admissions(database) == []


@pytest.mark.anyio
async def test_unauthorized_scope(database: Database) -> None:
    ledger = OperationLedger(database.engine)
    service = ConsentService(ledger)
    policy = policy_fixture()
    grant(service, policy)
    bridge = FakeBridge()
    with pytest.raises(OperationConflict, match="AI_CONSENT_REQUIRED"):
        await dispatch(AiAdmissionCoordinator(service, bridge, policy), claim(ledger), "AUDIO")
    assert bridge.preflights == bridge.dispatches == 0


@pytest.mark.anyio
@pytest.mark.parametrize(
    "drift",
    [
        "model",
        "extra_model",
        "missing",
        "provider",
        "route",
        "billing",
        "fallback",
        "fallback_account",
    ],
)
async def test_profile_drift_denied(database: Database, drift: str) -> None:
    ledger = OperationLedger(database.engine)
    service = ConsentService(ledger)
    policy = policy_fixture()
    grant(service, policy)
    bridge = FakeBridge()
    if drift == "model":
        bridge.profile.models[0]["id"] = "another-model"
    elif drift == "extra_model":
        bridge.profile.models.append({"id": "another-model", "owned_by": "google"})
    elif drift == "missing":
        bridge.profile.models.clear()
    elif drift == "provider":
        bridge.profile.models[0]["owned_by"] = "another-provider"
    else:
        field = {
            "route": "route",
            "billing": "billingMode",
            "fallback": "fallbackModel",
            "fallback_account": "fallbackAccount",
        }[drift]
        bridge.profile.raw_response = {field: "unapproved"}
    with pytest.raises(OperationConflict) as denied:
        await dispatch(AiAdmissionCoordinator(service, bridge, policy), claim(ledger))
    assert denied.value.code == "CONFIGURATION_REQUIRED"
    assert bridge.preflights == 1 and bridge.dispatches == 0
    assert admissions(database) == []


@pytest.mark.anyio
@pytest.mark.parametrize("field", ["model", "providerLabel", "route", "billingMode"])
async def test_caller_cannot_override_policy(database: Database, field: str) -> None:
    ledger = OperationLedger(database.engine)
    service = ConsentService(ledger)
    policy = policy_fixture()
    grant(service, policy)
    bridge = FakeBridge()
    with pytest.raises(OperationConflict, match="VALIDATION_ERROR"):
        await AiAdmissionCoordinator(service, bridge, policy).dispatch(
            operation_id=claim(ledger),
            scope="LOOKUP",
            payload={**PAYLOAD, field: "unapproved"},
            deadline=monotonic() + 30,
        )
    assert bridge.preflights == bridge.dispatches == 0


@pytest.mark.anyio
@pytest.mark.parametrize("regrant", [False, True])
async def test_revoke_or_aba_during_preflight_denies(database: Database, regrant: bool) -> None:
    ledger = OperationLedger(database.engine)
    service = ConsentService(ledger)
    policy = policy_fixture()
    grant(service, policy)
    bridge = FakeBridge()

    def withdraw() -> None:
        assert isinstance(service.revoke("revoke"), ConsentApplied)
        if regrant:
            grant(service, policy, "regrant")

    bridge.after_preflight = withdraw
    with pytest.raises(OperationConflict, match="AI_CONSENT_REQUIRED"):
        await dispatch(AiAdmissionCoordinator(service, bridge, policy), claim(ledger))
    assert bridge.preflights == 1 and bridge.dispatches == 0
    assert admissions(database) == []
    assert service.get_snapshot(policy).state.revision == (3 if regrant else 2)


@pytest.mark.anyio
async def test_duplicate_operation_never_dispatches_twice(database: Database) -> None:
    ledger = OperationLedger(database.engine)
    service = ConsentService(ledger)
    policy = policy_fixture()
    grant(service, policy)
    operation_id = claim(ledger)
    bridge = FakeBridge()
    coordinator = AiAdmissionCoordinator(service, bridge, policy)
    await dispatch(coordinator, operation_id)
    with pytest.raises(OperationConflict, match="IDEMPOTENCY_IN_FLIGHT"):
        await dispatch(coordinator, operation_id)
    assert bridge.dispatches == 1
    assert len(admissions(database)) == 1


@pytest.mark.anyio
@pytest.mark.parametrize("stage", ["precheck", "preflight", "commit"])
async def test_absolute_deadline_exhaustion(database: Database, stage: str) -> None:
    ledger = OperationLedger(database.engine)
    service = ConsentService(ledger)
    policy = policy_fixture()
    grant(service, policy)
    operation_id = claim(ledger)
    bridge = FakeBridge()
    now = [5.0 if stage == "precheck" else 0.0]
    if stage == "preflight":
        bridge.after_preflight = lambda: now.__setitem__(0, 5.0)
    elif stage == "commit":

        def expire_at_commit(conn: Connection) -> None:
            if conn.info.get("admission_inserted"):
                now[0] = 5.0

        def inserted(
            conn: Connection,
            _cursor: Any,
            statement: str,
            _parameters: Any,
            _context: Any,
            _many: bool,
        ) -> None:
            if statement.startswith("INSERT INTO ai_operation_admission"):
                conn.info["admission_inserted"] = True

        event.listen(database.engine, "after_cursor_execute", inserted)
        event.listen(database.engine, "commit", expire_at_commit)
    with pytest.raises(BridgeUnavailableError):
        await dispatch(
            AiAdmissionCoordinator(service, bridge, policy, clock=lambda: now[0]),
            operation_id,
            deadline=5.0,
        )
    assert bridge.dispatches == 0
    assert bridge.preflights == (0 if stage == "precheck" else 1)
    assert len(admissions(database)) == (1 if stage == "commit" else 0)


@pytest.mark.anyio
@pytest.mark.parametrize("stage", ["read", "insert", "commit"])
async def test_storage_failure_fails_closed(
    database: Database, stage: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger = OperationLedger(database.engine)
    service = ConsentService(ledger)
    policy = policy_fixture()
    grant(service, policy)
    operation_id = claim(ledger)
    bridge = FakeBridge()

    def fail(*_args: Any, **_kwargs: Any) -> None:
        raise OperationalError("private SQL", {}, RuntimeError("private-content"))

    if stage == "read":
        monkeypatch.setattr(service, "get_state", fail)
    elif stage == "insert":
        with database.engine.begin() as conn:
            conn.exec_driver_sql(
                "CREATE TRIGGER injected_failure BEFORE INSERT ON ai_operation_admission "
                "BEGIN SELECT RAISE(ABORT, 'private-content'); END"
            )
    else:

        def fail_commit(_conn: Connection) -> None:
            if bridge.preflights:
                fail()

        event.listen(database.engine, "commit", fail_commit)
    with pytest.raises(OperationConflict) as denied:
        await dispatch(AiAdmissionCoordinator(service, bridge, policy), operation_id)
    assert denied.value.code == "STORAGE_BUSY"
    assert "private" not in str(denied.value)
    assert service.storage_reliable is False
    assert bridge.dispatches == 0
    assert admissions(database) == []


@pytest.mark.anyio
async def test_unknown_restart_never_redispatches(database: Database, tmp_path: Path) -> None:
    ledger = OperationLedger(database.engine)
    service = ConsentService(ledger)
    policy = policy_fixture()
    grant(service, policy)
    operation_id = claim(ledger)
    bridge = FakeBridge()
    bridge.failure = BridgeUnavailableError("Uncertain external outcome")
    with pytest.raises(BridgeUnavailableError):
        await dispatch(AiAdmissionCoordinator(service, bridge, policy), operation_id)
    assert len(admissions(database)) == bridge.dispatches == 1
    restarted = Database(tmp_path / "admission.db")
    try:
        recovered = OperationLedger(restarted.engine)
        assert recovered.recover_pending() == 1
        operation = recovered.get(operation_id)
        assert operation is not None and operation.status == "UNKNOWN"
        with pytest.raises(OperationConflict, match="IDEMPOTENCY_IN_FLIGHT"):
            claim(recovered)
        with pytest.raises(OperationConflict, match="IDEMPOTENCY_IN_FLIGHT"):
            await dispatch(
                AiAdmissionCoordinator(ConsentService(recovered), bridge, policy), operation_id
            )
        assert len(admissions(restarted)) == bridge.dispatches == 1
    finally:
        restarted.close()


def race_worker(
    path: str,
    operation_id: str,
    ordering: str,
    ready: ProcessEvent,
    release: ProcessEvent,
    output: PipeConnection,
) -> None:
    db = Database(Path(path))
    bridge = FakeBridge()

    def before_begin(
        _conn: Connection,
        _cursor: Any,
        statement: str,
        _parameters: Any,
        _context: Any,
        _many: bool,
    ) -> None:
        if (
            ordering != "admission_first"
            and bridge.preflights == 1
            and statement == "BEGIN IMMEDIATE"
        ):
            ready.set()
            assert release.wait(timeout=15)

    def blocked_transport() -> None:
        assert len(admissions(db)) == 1
        ready.set()
        assert release.wait(timeout=15)

    event.listen(db.engine, "before_cursor_execute", before_begin)
    if ordering == "admission_first":
        bridge.at_dispatch = blocked_transport
    try:
        coordinator = AiAdmissionCoordinator(
            ConsentService(OperationLedger(db.engine)), bridge, policy_fixture()
        )
        try:
            asyncio.run(dispatch(coordinator, operation_id, deadline=monotonic() + 60))
            outcome = "completed"
        except OperationConflict as failure:
            outcome = failure.code
        output.send((outcome, bridge.dispatches, len(admissions(db))))
    finally:
        output.close()
        db.close()


@pytest.mark.parametrize("ordering", ["revoke_first", "aba", "admission_first"])
def test_two_process_ordering_and_transaction_closed(
    database: Database, ordering: str, tmp_path: Path
) -> None:
    ledger = OperationLedger(database.engine)
    service = ConsentService(ledger)
    policy = policy_fixture()
    grant(service, policy)
    operation_id = claim(ledger)
    context = multiprocessing.get_context("spawn")
    ready, release = context.Event(), context.Event()
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(
        target=race_worker,
        args=(str(tmp_path / "admission.db"), operation_id, ordering, ready, release, sender),
    )
    process.start()
    sender.close()
    try:
        assert ready.wait(timeout=15)
        # This durable commit happens while the child is still blocked, with no sleep.
        assert isinstance(service.revoke("revoke"), ConsentApplied)
        if ordering == "aba":
            grant(service, policy, "regrant")
        assert process.is_alive() and not receiver.poll()
        assert len(admissions(database)) == (1 if ordering == "admission_first" else 0)
        release.set()
        assert receiver.poll(timeout=15)
        outcome, dispatches, count = receiver.recv()
        assert (outcome, dispatches, count) == (
            ("completed", 1, 1) if ordering == "admission_first" else ("AI_CONSENT_REQUIRED", 0, 0)
        )
        process.join(timeout=15)
        assert process.exitcode == 0
        if ordering == "admission_first":
            bridge = FakeBridge()
            with pytest.raises(OperationConflict, match="AI_CONSENT_REQUIRED"):
                asyncio.run(
                    dispatch(
                        AiAdmissionCoordinator(service, bridge, policy), claim(ledger, key="later")
                    )
                )
            assert bridge.preflights == bridge.dispatches == 0
            assert len(admissions(database)) == 1
    finally:
        release.set()
        process.join(timeout=15)
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)
        receiver.close()


def test_upgrade_from_0005_preserves_data_and_one_head(tmp_path: Path) -> None:
    db = Database(tmp_path / "upgrade.db")
    config = migration_config()
    scripts = ScriptDirectory.from_config(config)
    assert scripts.get_heads() == ["0006_ai_admission"]
    revision = scripts.get_revision("0006_ai_admission")
    assert revision is not None and revision.down_revision == "0005_review"
    try:
        with db.engine.begin() as conn:
            config.attributes["connection"] = conn
            command.upgrade(config, "0005_review")
            conn.exec_driver_sql(
                "INSERT INTO word_families VALUES ('synthetic', 'synthetic', 'time', 'time')"
            )
        ledger = OperationLedger(db.engine)
        operation_id = claim(ledger)
        assert db.initialize().schema_revision == "0006_ai_admission"
        assert db.initialize().schema_revision == "0006_ai_admission"
        assert ledger.get(operation_id) is not None
        with db.engine.connect() as conn:
            assert (
                conn.exec_driver_sql("SELECT root_lemma FROM word_families").scalar_one()
                == "synthetic"
            )
            assert conn.exec_driver_sql("PRAGMA foreign_key_check").all() == []
            assert {row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({TABLE})")} == {
                "operation_id",
                "consent_revision",
                "policy_version",
                "policy_digest",
                "scope",
                "provider_label",
                "model_id",
                "route",
                "billing_mode",
                "admission_state",
                "admitted_at",
            }
        with pytest.raises(RuntimeError, match="Downgrade is disabled"), db.engine.begin() as conn:
            config.attributes["connection"] = conn
            command.downgrade(config, "0005_review")
    finally:
        db.close()


@pytest.mark.anyio
async def test_admission_cannot_be_replaced_updated_deleted_or_duplicated(
    database: Database,
) -> None:
    ledger = OperationLedger(database.engine)
    service = ConsentService(ledger)
    policy = policy_fixture()
    grant(service, policy)
    await dispatch(AiAdmissionCoordinator(service, FakeBridge(), policy), claim(ledger))
    original = admissions(database)
    for statement in [
        f"INSERT INTO {TABLE} SELECT * FROM {TABLE}",
        f"INSERT OR REPLACE INTO {TABLE} SELECT * FROM {TABLE}",
        f"UPDATE {TABLE} SET consent_revision=2",
        f"DELETE FROM {TABLE}",
    ]:
        with pytest.raises(DBAPIError), database.engine.begin() as conn:
            conn.exec_driver_sql(statement)
        assert admissions(database) == original


@pytest.mark.anyio
@pytest.mark.parametrize("change", ["new_version", "same_version", "storage_latch", "recovery"])
async def test_changes_during_preflight_fail_closed(database: Database, change: str) -> None:
    ledger = OperationLedger(database.engine)
    service = ConsentService(ledger)
    policy = policy_fixture()
    original = copy.deepcopy(policy)
    grant(service, policy)
    bridge = FakeBridge()

    def change_state() -> None:
        if change == "new_version":
            policy["version"] = "policy-v2"
        elif change == "same_version":
            policy["withdrawalStatement"] += " Changed."
        elif change == "storage_latch":
            service.storage_reliable = False
        else:
            assert ledger.recover_pending() == 1

    bridge.after_preflight = change_state
    expected = {
        "new_version": "AI_POLICY_CHANGED",
        "same_version": "CONFIGURATION_REQUIRED",
        "storage_latch": "STORAGE_BUSY",
        "recovery": "IDEMPOTENCY_IN_FLIGHT",
    }[change]
    with pytest.raises(OperationConflict, match=expected):
        await dispatch(AiAdmissionCoordinator(service, bridge, lambda: policy), claim(ledger))
    assert bridge.dispatches == 0 and admissions(database) == []
    if change == "same_version":
        # A rejected final fence must still durably remember a mutable-version conflict.
        assert service.get_snapshot(original).policy is None


@pytest.mark.anyio
@pytest.mark.parametrize(
    "corruption", ["missing_consent", "missing_policy_history", "corrupt_time"]
)
async def test_missing_or_corrupt_durable_authorization(
    database: Database, corruption: str
) -> None:
    ledger = OperationLedger(database.engine)
    service = ConsentService(ledger)
    policy = policy_fixture()
    grant(service, policy)
    operation_id = claim(ledger)
    with database.engine.begin() as conn:
        if corruption == "missing_consent":
            conn.exec_driver_sql("DROP TRIGGER preserve_consent_singleton")
            conn.exec_driver_sql("DELETE FROM ai_consent_state")
        elif corruption == "missing_policy_history":
            conn.exec_driver_sql("DROP TRIGGER immutable_policy_history")
            conn.exec_driver_sql("UPDATE ai_consent_state SET policy_history='{}'")
        else:
            conn.exec_driver_sql(
                "UPDATE ai_consent_state SET last_choice_at='2026-99-99T00:00:00Z'"
            )
    bridge = FakeBridge()
    with pytest.raises(OperationConflict, match="STORAGE_BUSY"):
        await dispatch(AiAdmissionCoordinator(service, bridge, policy), operation_id)
    assert bridge.preflights == bridge.dispatches == 0
    assert admissions(database) == []


@pytest.mark.anyio
async def test_concurrent_final_admission_of_same_operation(database: Database) -> None:
    ledger = OperationLedger(database.engine)
    service = ConsentService(ledger)
    policy = policy_fixture()
    grant(service, policy)
    operation_id = claim(ledger)
    preflights_done = asyncio.Event()

    class SimultaneousBridge(FakeBridge):
        async def preflight(self, deadline: float) -> BridgeProfile:
            profile = await super().preflight(deadline)
            if self.preflights == 2:
                preflights_done.set()
            await asyncio.wait_for(preflights_done.wait(), timeout=5)
            return profile

    bridge = SimultaneousBridge()
    coordinator = AiAdmissionCoordinator(service, bridge, policy)
    results = await asyncio.gather(
        dispatch(coordinator, operation_id),
        dispatch(coordinator, operation_id),
        return_exceptions=True,
    )
    assert sum(isinstance(result, dict) for result in results) == 1
    failures = [result for result in results if isinstance(result, OperationConflict)]
    assert len(failures) == 1 and failures[0].code == "IDEMPOTENCY_IN_FLIGHT"
    assert bridge.preflights == 2 and bridge.dispatches == 1
    assert len(admissions(database)) == 1


@pytest.mark.anyio
async def test_zero_row_admission_is_not_acknowledged(database: Database) -> None:
    ledger = OperationLedger(database.engine)
    service = ConsentService(ledger)
    policy = policy_fixture()
    grant(service, policy)
    with database.engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TRIGGER ignored_admission BEFORE INSERT ON ai_operation_admission "
            "BEGIN SELECT RAISE(IGNORE); END"
        )
    bridge = FakeBridge()
    with pytest.raises(OperationConflict, match="STORAGE_BUSY"):
        await dispatch(AiAdmissionCoordinator(service, bridge, policy), claim(ledger))
    assert bridge.dispatches == 0 and admissions(database) == []


@pytest.mark.anyio
@pytest.mark.parametrize("scope", ["LOOKUP", "QUIZ_GENERATION"])
async def test_missing_or_wrong_kind_operation(database: Database, scope: str) -> None:
    ledger = OperationLedger(database.engine)
    service = ConsentService(ledger)
    policy = policy_fixture()
    grant(service, policy)
    bridge = FakeBridge()
    operation_id = "op_missing" if scope == "LOOKUP" else claim(ledger)
    with pytest.raises(OperationConflict, match=r"NOT_FOUND|VALIDATION_ERROR"):
        await dispatch(AiAdmissionCoordinator(service, bridge, policy), operation_id, scope)
    assert bridge.preflights == bridge.dispatches == 0


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("operation_id", "op_missing"),
        ("consent_revision", 999),
        ("scope", "AUDIO"),
        ("policy_digest", "invalid"),
        ("admission_state", "UNKNOWN"),
        ("model_id", "unapproved"),
    ],
)
def test_admission_foreign_keys_and_checks(database: Database, field: str, invalid: object) -> None:
    ledger = OperationLedger(database.engine)
    service = ConsentService(ledger)
    policy = policy_fixture()
    grant(service, policy)
    snapshot = service.get_snapshot(policy)
    row: dict[str, object] = {
        "operation_id": claim(ledger),
        "consent_revision": 1,
        "policy_version": "policy-v1",
        "policy_digest": snapshot.state.accepted_policy_digest,
        "scope": "LOOKUP",
        "provider_label": "Antigravity/Google",
        "model_id": MODEL,
        "route": "primary",
        "billing_mode": "configured-account",
        "admission_state": "ADMITTED",
        "admitted_at": "2026-10-01T00:00:00Z",
    }
    row[field] = invalid
    with pytest.raises(DBAPIError), database.engine.begin() as conn:
        conn.exec_driver_sql(
            "INSERT INTO ai_operation_admission (operation_id, consent_revision, policy_version, "
            "policy_digest, scope, provider_label, model_id, route, billing_mode, "
            "admission_state, admitted_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            tuple(row.values()),
        )
    assert admissions(database) == []


@pytest.mark.anyio
async def test_expired_transport_result_cannot_be_returned_as_success(database: Database) -> None:
    ledger = OperationLedger(database.engine)
    service = ConsentService(ledger)
    policy = policy_fixture()
    grant(service, policy)
    now = [0.0]
    bridge = FakeBridge()
    bridge.at_dispatch = lambda: now.__setitem__(0, 5.0)
    with pytest.raises(BridgeUnavailableError):
        await dispatch(
            AiAdmissionCoordinator(service, bridge, policy, clock=lambda: now[0]),
            claim(ledger),
            deadline=5.0,
        )
    assert len(admissions(database)) == bridge.dispatches == 1


@pytest.mark.anyio
@pytest.mark.parametrize("deadline", [float("nan"), float("inf"), float("-inf")])
async def test_nonfinite_deadline_is_denied(database: Database, deadline: float) -> None:
    ledger = OperationLedger(database.engine)
    bridge = FakeBridge()
    with pytest.raises(BridgeUnavailableError):
        await dispatch(
            AiAdmissionCoordinator(ConsentService(ledger), bridge, policy_fixture()),
            claim(ledger),
            deadline=deadline,
        )
    assert bridge.preflights == bridge.dispatches == 0

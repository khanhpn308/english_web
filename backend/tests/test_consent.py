import pytest
from pathlib import Path
from backend.app.persistence.database import Database
from backend.app.main import create_app
from backend.app.platform.config import AppSettings
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def database(tmp_path: Path) -> Database:
    db = Database(tmp_path / "consent.db")
    db.initialize()
    return db


@pytest.fixture
def app_settings(tmp_path: Path) -> AppSettings:
    return AppSettings(host="127.0.0.1", port=8000, storage_path=tmp_path / "consent.db")


@pytest.fixture
async def client(app_settings: AppSettings):
    app = create_app(app_settings)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://127.0.0.1:8000",
            headers={"Origin": "http://127.0.0.1:8000"},
        ) as client,
    ):
        token = app.state.sessions.issue_bootstrap_token()
        exchanged = await client.post(
            "/bootstrap/exchange",
            json={"token": token},
            headers={"Origin": "http://127.0.0.1:8000"},
        )
        cookie = exchanged.headers["set-cookie"].split(";", 1)[0]
        client.headers["Cookie"] = cookie
        yield client


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_get_initial_consent(client: AsyncClient):
    response = await client.get("/api/v1/ai-consent")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert "etag" in response.headers

    data = response.json()
    assert data["state"] == "NOT_GRANTED"
    assert data["revision"] == 0
    assert data["acceptedPolicyVersion"] is None
    assert data["acceptedPolicyDigest"] is None
    assert data["lastChoiceAt"] is None
    assert data["canRequestAi"] is False
    assert data["policy"] is None


@pytest.fixture
def synthetic_policy():
    return {"version": "policy-v1", "digest": "d_12345", "content": "You agree to everything."}


@pytest.mark.anyio
async def test_ready_grant(client: AsyncClient, synthetic_policy: dict):
    # Setup policy
    client._transport.app.state.active_ai_policy = synthetic_policy

    # 1. GET initial state
    res1 = await client.get("/api/v1/ai-consent")
    assert res1.status_code == 200
    etag = res1.headers["ETag"]
    assert etag == '"ac-r0-none"'

    # 2. PUT grant
    res2 = await client.put(
        "/api/v1/ai-consent",
        json={"policyVersion": "policy-v1"},
        headers={"If-Match": etag, "Idempotency-Key": "key-grant-1"},
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert "operationId" in data2
    assert data2["appliedRevision"] == 1

    # 3. GET after grant
    res3 = await client.get("/api/v1/ai-consent")
    assert res3.status_code == 200
    assert res3.json()["state"] == "GRANTED"
    assert res3.json()["canRequestAi"] is True
    assert res3.json()["revision"] == 1
    assert res3.headers["ETag"] == '"ac-r1-d_12345"'


@pytest.mark.anyio
async def test_grant_idempotency_replay(client: AsyncClient, synthetic_policy: dict):
    client._transport.app.state.active_ai_policy = synthetic_policy

    # First grant
    res1 = await client.put(
        "/api/v1/ai-consent",
        json={"policyVersion": "policy-v1"},
        headers={"If-Match": '"ac-r0-none"', "Idempotency-Key": "key-grant-2"},
    )
    assert res1.status_code == 200
    op_id = res1.json()["operationId"]

    # Replay exactly
    res2 = await client.put(
        "/api/v1/ai-consent",
        json={"policyVersion": "policy-v1"},
        headers={"If-Match": '"ac-r0-none"', "Idempotency-Key": "key-grant-2"},
    )
    assert res2.status_code == 200
    assert res2.json()["operationId"] == op_id
    assert res2.json()["appliedRevision"] == 1

    # GET shows revision is still 1
    res3 = await client.get("/api/v1/ai-consent")
    assert res3.json()["revision"] == 1


@pytest.mark.anyio
async def test_revoke(client: AsyncClient, synthetic_policy: dict):
    client._transport.app.state.active_ai_policy = synthetic_policy
    await client.put(
        "/api/v1/ai-consent",
        json={"policyVersion": "policy-v1"},
        headers={"If-Match": '"ac-r0-none"', "Idempotency-Key": "key-grant-3"},
    )

    res = await client.delete("/api/v1/ai-consent", headers={"Idempotency-Key": "key-revoke-1"})
    assert res.status_code == 200
    assert res.json()["appliedRevision"] == 2

    get_res = await client.get("/api/v1/ai-consent")
    assert get_res.json()["state"] == "REVOKED"
    assert get_res.json()["canRequestAi"] is False
    assert get_res.json()["acceptedPolicyDigest"] is None
    assert get_res.headers["ETag"] == '"ac-r2-none"'


@pytest.mark.anyio
async def test_redundant_revoke_bumps_revision(client: AsyncClient):
    # Even without policy, revoke works
    res1 = await client.delete(
        "/api/v1/ai-consent", headers={"Idempotency-Key": "key-revoke-first"}
    )
    assert res1.status_code == 200
    assert res1.json()["appliedRevision"] == 1

    res2 = await client.delete(
        "/api/v1/ai-consent",
        headers={"Idempotency-Key": "key-revoke-second"},  # Different key
    )
    assert res2.status_code == 200
    assert res2.json()["appliedRevision"] == 2


@pytest.mark.anyio
async def test_grant_revision_conflict(client: AsyncClient, synthetic_policy: dict):
    client._transport.app.state.active_ai_policy = synthetic_policy
    # Wrong If-Match
    res = await client.put(
        "/api/v1/ai-consent",
        json={"policyVersion": "policy-v1"},
        headers={"If-Match": '"ac-r999-none"', "Idempotency-Key": "key-conflict"},
    )
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "REVISION_CONFLICT"


@pytest.mark.anyio
async def test_grant_missing_policy_returns_503(client: AsyncClient):
    # No policy configured
    res = await client.put(
        "/api/v1/ai-consent",
        json={"policyVersion": "policy-v1"},
        headers={"If-Match": '"ac-r0-none"', "Idempotency-Key": "key-missing-config"},
    )
    assert res.status_code == 503
    assert res.json()["error"]["code"] == "CONFIGURATION_REQUIRED"


@pytest.mark.anyio
async def test_grant_stale_policy_409(client: AsyncClient, synthetic_policy: dict):
    # Setup policy v1
    client._transport.app.state.active_ai_policy = synthetic_policy

    # 1. GET initial state
    res1 = await client.get("/api/v1/ai-consent")
    etag = res1.headers["ETag"]

    # 2. PUT grant but with wrong policyVersion (e.g. policy-v2)
    res2 = await client.put(
        "/api/v1/ai-consent",
        json={"policyVersion": "policy-v2"},
        headers={"If-Match": etag, "Idempotency-Key": "key-stale-grant"},
    )
    assert res2.status_code == 409
    assert res2.json()["error"]["code"] == "AI_POLICY_CHANGED"


@pytest.mark.anyio
async def test_get_stale_state(client: AsyncClient, synthetic_policy: dict):
    # Setup policy v1
    client._transport.app.state.active_ai_policy = synthetic_policy

    res1 = await client.get("/api/v1/ai-consent")
    etag = res1.headers["ETag"]

    # Grant v1
    await client.put(
        "/api/v1/ai-consent",
        json={"policyVersion": "policy-v1"},
        headers={"If-Match": etag, "Idempotency-Key": "key-grant-v1"},
    )

    # Server active policy changes to v2
    client._transport.app.state.active_ai_policy = {
        "version": "policy-v2",
        "digest": "d_67890",
        "content": "You agree to more.",
    }

    # GET should now return STALE
    res_get = await client.get("/api/v1/ai-consent")
    assert res_get.status_code == 200
    data = res_get.json()
    assert data["state"] == "STALE"
    assert data["canRequestAi"] is False
    # ETag must still be based on the persisted digest (d_12345)
    assert res_get.headers["ETag"] == '"ac-r1-d_12345"'


@pytest.mark.anyio
async def test_grant_idempotency_conflict(client: AsyncClient, synthetic_policy: dict):
    client._transport.app.state.active_ai_policy = synthetic_policy

    res = await client.put(
        "/api/v1/ai-consent",
        json={"policyVersion": "policy-v1"},
        headers={"If-Match": '"ac-r0-none"', "Idempotency-Key": "key-shared"},
    )
    assert res.status_code == 200

    # Now try to grant with the SAME key but different intent (e.g., wrong If-Match precondition)
    res_conflict = await client.put(
        "/api/v1/ai-consent",
        json={"policyVersion": "policy-v1"},
        headers={"If-Match": '"ac-r999-none"', "Idempotency-Key": "key-shared"},
    )
    assert res_conflict.status_code == 409
    assert res_conflict.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"

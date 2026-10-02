"""Production-app contract tests for T027 search and detail APIs."""

import base64
from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import patch

import pytest
from backend.app.main import create_app
from backend.app.platform.config import AppSettings
from backend.app.vocabulary.models import MeaningEn, MeaningVi
from backend.app.vocabulary.repository import VocabularyRepository
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

BASE = "http://127.0.0.1:8000"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def app(tmp_path: Path) -> AsyncIterator[FastAPI]:
    application = create_app(AppSettings(storage_path=tmp_path / "search.db"))
    async with application.router.lifespan_context(application):
        repository = VocabularyRepository(application.state.database.engine)
        family = repository.get_or_create_family("robust", family_id="family_01")
        form = repository.save_canonical_word_form(
            lemma="robust",
            part_of_speech="ADJECTIVE",
            family_id=family.id,
            meanings_en=[MeaningEn("reliable", verification_status="VERIFIED")],
            meanings_vi=[MeaningVi("vững chắc", verification_status="VERIFIED")],
            word_form_id="wf_01",
        )
        source = repository.save_source_file(
            source_id="src_01",
            relative_path="29-09-2026.md",
            note_date="2026-09-29",
            status="VALID",
        )
        repository.link_word_form_to_source(form.id, source.id, source.note_date)
        yield application


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url=BASE,
        headers={"Origin": BASE},
    ) as http:
        token = app.state.sessions.issue_bootstrap_token()
        exchanged = await http.post("/bootstrap/exchange", json={"token": token})
        assert exchanged.status_code == 204
        http.headers["Cookie"] = exchanged.headers["set-cookie"].split(";", 1)[0]
        yield http


@pytest.mark.anyio
async def test_collection_defaults_and_detail(client: AsyncClient) -> None:
    collection = await client.get("/api/v1/word-forms")
    assert collection.status_code == 200
    body = collection.json()
    assert body["pagination"] == {"nextCursor": None, "pageSize": 50, "hasMore": False}
    assert body["data"][0]["id"] == "wf_01"

    detail = await client.get("/api/v1/word-forms/wf_01")
    assert detail.status_code == 200
    assert detail.json()["id"] == "wf_01"
    assert detail.json()["partOfSpeech"] == "ADJECTIVE"


@pytest.mark.anyio
async def test_invalid_cursor_is_typed_conflict(client: AsyncClient) -> None:
    response = await client.get("/api/v1/word-forms?cursor=not-a-cursor")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CURSOR_EXPIRED"


def add_form(app: FastAPI, *, form_id: str, lemma: str, meaning: str, pos: str = "NOUN") -> None:
    repository = VocabularyRepository(app.state.database.engine)
    family = repository.get_or_create_family(lemma, family_id=f"family_{form_id}")
    form = repository.save_canonical_word_form(
        lemma=lemma,
        part_of_speech=pos,
        family_id=family.id,
        meanings_en=[MeaningEn("synthetic", verification_status="VERIFIED")],
        meanings_vi=[MeaningVi(meaning, verification_status="VERIFIED")],
        word_form_id=form_id,
    )
    source = repository.save_source_file(
        source_id=f"src_{form_id}",
        relative_path=f"{form_id}.md",
        note_date="2026-09-30",
        status="VALID",
    )
    repository.link_word_form_to_source(form.id, source.id, source.note_date)


@pytest.mark.anyio
async def test_filters_and_cursor_are_query_bound(client: AsyncClient, app: FastAPI) -> None:
    add_form(app, form_id="wf_02", lemma="steady", meaning="bền vững")
    add_form(app, form_id="wf_03", lemma="valid", meaning="hợp lệ")

    first = await client.get("/api/v1/word-forms?pageSize=1&sortBy=lemma&sortOrder=asc")
    assert first.status_code == 200
    first_body = first.json()
    assert first_body["pagination"]["hasMore"] is True
    cursor = first_body["pagination"]["nextCursor"]
    assert isinstance(cursor, str)

    second = await client.get(f"/api/v1/word-forms?pageSize=1&sortBy=lemma&cursor={cursor}")
    assert second.status_code == 200
    assert second.json()["data"][0]["id"] != first_body["data"][0]["id"]

    mismatch = await client.get(f"/api/v1/word-forms?meaningVi=ben&pageSize=1&cursor={cursor}")
    assert mismatch.status_code == 409
    assert mismatch.json()["error"]["code"] == "CURSOR_EXPIRED"

    payload, signature = cursor.split(".")
    signature_bytes = bytearray(base64.urlsafe_b64decode(signature + "="))
    signature_bytes[0] ^= 1
    changed_signature = (
        payload + "." + base64.urlsafe_b64encode(signature_bytes).rstrip(b"=").decode()
    )
    tampered = await client.get(
        f"/api/v1/word-forms?pageSize=1&sortBy=lemma&cursor={changed_signature}"
    )
    assert tampered.status_code == 409
    assert tampered.json()["error"]["code"] == "CURSOR_EXPIRED"

    repository = VocabularyRepository(app.state.database.engine)
    repository.save_source_file(
        source_id="src_wf_02",
        relative_path="wf_02.md",
        note_date="2026-09-30",
        status="VALID",
        revision=2,
    )
    stale = await client.get(f"/api/v1/word-forms?pageSize=1&sortBy=lemma&cursor={cursor}")
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "CURSOR_EXPIRED"

    filtered = await client.get("/api/v1/word-forms?meaningVi=BEN&partOfSpeech=NOUN")
    assert filtered.status_code == 200
    assert [item["id"] for item in filtered.json()["data"]] == ["wf_02"]


@pytest.mark.anyio
async def test_validation_source_health_and_safe_not_found(
    client: AsyncClient, app: FastAPI
) -> None:
    invalid_repo = VocabularyRepository(app.state.database.engine)
    invalid_repo.update_source_status("src_01", "INVALID", "PARSE_FAILED")
    excluded = await client.get("/api/v1/word-forms")
    assert excluded.status_code == 200
    assert excluded.json()["data"] == []
    detail = await client.get("/api/v1/word-forms/wf_01")
    assert detail.status_code == 200
    assert detail.json()["sourceRefs"][0]["status"] == "INVALID"
    assert detail.json()["meaningsVi"] == []

    unknown_filter = await client.get("/api/v1/word-forms?unknownFilter=x")
    assert unknown_filter.status_code == 422
    assert unknown_filter.json()["error"]["code"] == "VALIDATION_ERROR"

    malformed = await client.get("/api/v1/word-forms?noteDate=not-a-date")
    assert malformed.status_code == 400
    assert malformed.json()["error"]["code"] == "INVALID_QUERY"

    bad_sort = await client.get("/api/v1/word-forms?sortBy=updatedAt;DROP TABLE word_forms")
    assert bad_sort.status_code == 422
    assert bad_sort.json()["error"]["code"] == "VALIDATION_ERROR"

    hostile = await client.get("/api/v1/word-forms?lemma=%27%20OR%201%3D1%20--")
    assert hostile.status_code == 200
    with app.state.database.engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT count(*) FROM word_forms").scalar() == 1

    missing = await client.get("/api/v1/word-forms/does-not-exist")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.anyio
async def test_page_size_bounds_and_session_guard(app: FastAPI) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as http:
        too_large = await http.get("/api/v1/word-forms?pageSize=101")
        assert too_large.status_code == 401
        token = app.state.sessions.issue_bootstrap_token()
        exchanged = await http.post(
            "/bootstrap/exchange", json={"token": token}, headers={"Origin": BASE}
        )
        cookie = exchanged.headers["set-cookie"].split(";", 1)[0]
        response = await http.get(
            "/api/v1/word-forms?pageSize=101", headers={"Cookie": cookie, "Origin": BASE}
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.anyio
@pytest.mark.parametrize("meaning", [None, "vung"])
async def test_relationship_changes_invalidate_content_and_cursor(
    client: AsyncClient, app: FastAPI, meaning: str | None
) -> None:
    query = {} if meaning is None else {"meaningVi": meaning}
    add_form(app, form_id="wf_02", lemma="alpha", meaning="vững chắc")
    repo = VocabularyRepository(app.state.database.engine)
    repo.unlink_source_from_form("wf_01", "src_01")
    cached = await client.get("/api/v1/word-forms", params=query)
    assert [item["id"] for item in cached.json()["data"]] == ["wf_02"]
    repo.link_word_form_to_source("wf_01", "src_01", "2026-09-29")
    activated = await client.get("/api/v1/word-forms", params=query)
    assert {item["id"] for item in activated.json()["data"]} == {"wf_01", "wf_02"}
    assert (await client.get("/api/v1/word-forms/wf_01")).json()["meaningsVi"]
    first = await client.get("/api/v1/word-forms", params=query | {"pageSize": 1})
    cursor = first.json()["pagination"]["nextCursor"]
    repo.unlink_source_from_form("wf_01", "src_01")
    stale = await client.get("/api/v1/word-forms", params=query | {"pageSize": 1, "cursor": cursor})
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "CURSOR_EXPIRED"
    assert [
        item["id"] for item in (await client.get("/api/v1/word-forms", params=query)).json()["data"]
    ] == ["wf_02"]
    assert (await client.get("/api/v1/word-forms/wf_01")).json()["meaningsVi"] == []
    # Another VALID source keeps current content active until that last link disappears.
    repo.link_word_form_to_source("wf_01", "src_wf_02", "2026-09-30")
    repo.update_source_status("src_01", "INVALID", "PARSE_FAILED")
    assert {
        item["id"] for item in (await client.get("/api/v1/word-forms", params=query)).json()["data"]
    } == {
        "wf_01",
        "wf_02",
    }
    repo.update_source_status("src_wf_02", "MISSING")
    assert (await client.get("/api/v1/word-forms", params=query)).json()["data"] == []
    assert (await client.get("/api/v1/word-forms/wf_01")).json()["meaningsVi"] == []


@pytest.mark.anyio
@pytest.mark.parametrize("meaning", [None, "vung"])
async def test_projection_version_change_expires_cursor(
    client: AsyncClient, app: FastAPI, meaning: str | None
) -> None:
    add_form(app, form_id="wf_02", lemma="alpha", meaning="vững chắc")
    params = {"pageSize": "1"}
    if meaning is not None:
        params["meaningVi"] = meaning
    first = await client.get("/api/v1/word-forms", params=params)
    cursor = first.json()["pagination"]["nextCursor"]
    assert cursor
    app.state.search_service.index.set_version("incompatible")
    response = await client.get("/api/v1/word-forms", params=params | {"cursor": cursor})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CURSOR_EXPIRED"


@pytest.mark.anyio
async def test_noncanonical_signature_is_rejected(client: AsyncClient, app: FastAPI) -> None:
    add_form(app, form_id="wf_02", lemma="alpha", meaning="vững chắc")
    first = await client.get("/api/v1/word-forms", params={"pageSize": 1})
    cursor = first.json()["pagination"]["nextCursor"]
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    changed = cursor[:-1] + alphabet[alphabet.index(cursor[-1]) ^ 1]
    assert changed != cursor
    assert base64.urlsafe_b64decode(changed.split(".")[1] + "=") == base64.urlsafe_b64decode(
        cursor.split(".")[1] + "="
    )
    response = await client.get("/api/v1/word-forms", params={"pageSize": 1, "cursor": changed})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CURSOR_EXPIRED"


@pytest.mark.anyio
@pytest.mark.parametrize("field", ["meaningVi", "lemma"])
async def test_content_filter_code_point_boundary(client: AsyncClient, field: str) -> None:
    accepted = await client.get("/api/v1/word-forms", params={field: "é" * 4096})
    assert accepted.status_code == 200
    rejected = await client.get("/api/v1/word-forms", params={field: "é" * 4097})
    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "value", ["2026-02-30", "2026-13-01", "\uff12\uff10\uff12\uff16-\uff10\uff11-\uff10\uff11"]
)
async def test_invalid_calendar_or_non_ascii_date(client: AsyncClient, value: str) -> None:
    response = await client.get("/api/v1/word-forms", params={"noteDate": value})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_QUERY"


@pytest.mark.anyio
@pytest.mark.parametrize("value", ["2024-02-29", "2026-09-30"])
async def test_real_calendar_dates_are_accepted(client: AsyncClient, value: str) -> None:
    assert (await client.get("/api/v1/word-forms", params={"noteDate": value})).status_code == 200


@pytest.mark.anyio
async def test_search_reaches_matches_beyond_page_retention(
    client: AsyncClient, app: FastAPI
) -> None:
    for number, lemma in enumerate(["alpha", "beta", "gamma"]):
        add_form(app, form_id=f"wf_extra_{number}", lemma=lemma, meaning="đẹp")
    # Scale the audited legacy cap without creating 100k fixtures. Once removed,
    # this attribute has no effect; pageSize+1 still retains only two candidates.
    with patch("backend.app.vocabulary.search_service.MAX_SEARCH_CANDIDATES", 2, create=True):
        filtered = await client.get(
            "/api/v1/word-forms", params={"meaningVi": "dep", "lemma": "gamma", "pageSize": 1}
        )
        assert [item["lemma"] for item in filtered.json()["data"]] == ["gamma"]
        params = {"meaningVi": "dep", "pageSize": "1", "sortBy": "lemma"}
        seen: list[str] = []
        for expected_more in [True, True, False]:
            response = await client.get("/api/v1/word-forms", params=params)
            body = response.json()
            seen.extend(item["lemma"] for item in body["data"])
            assert body["pagination"]["hasMore"] is expected_more
            params["cursor"] = body["pagination"]["nextCursor"]
        assert seen == ["alpha", "beta", "gamma"]


@pytest.mark.anyio
@pytest.mark.parametrize("sort_by", ["lemma", "updatedAt", "relevance"])
@pytest.mark.parametrize("direction", ["ASC", "DESC"])
async def test_streaming_pages_preserve_order_and_ties(
    client: AsyncClient, app: FastAPI, sort_by: str, direction: str
) -> None:
    for number, pos in enumerate(["NOUN", "VERB", "ADVERB"]):
        add_form(app, form_id=f"wf_tie_{number}", lemma="tie", meaning="bền", pos=pos)
    add_form(app, form_id="wf_tail", lemma="zeta", meaning="một bền lâu")
    with app.state.database.engine.begin() as connection:
        connection.exec_driver_sql(
            "UPDATE word_forms SET updated_at = ?", ("2026-09-30T00:00:00Z",)
        )
    params = {"meaningVi": "ben", "sortBy": sort_by, "sortOrder": direction}
    complete = (await client.get("/api/v1/word-forms", params=params | {"pageSize": "100"})).json()[
        "data"
    ]
    seen: list[str] = []
    params["pageSize"] = "1"
    while True:
        response = await client.get("/api/v1/word-forms", params=params)
        assert response.status_code == 200
        body = response.json()
        seen.extend(item["id"] for item in body["data"])
        if not body["pagination"]["hasMore"]:
            break
        params["cursor"] = body["pagination"]["nextCursor"]
        assert len(seen) <= 4
    assert seen == [item["id"] for item in complete]
    assert len(seen) == len(set(seen)) == 4
    if sort_by == "relevance":
        expected = (
            ["wf_tail", "wf_tie_0", "wf_tie_1", "wf_tie_2"]
            if direction == "ASC"
            else ["wf_tie_0", "wf_tie_1", "wf_tie_2", "wf_tail"]
        )
    elif sort_by == "updatedAt" or direction == "DESC":
        expected = ["wf_tail", "wf_tie_0", "wf_tie_1", "wf_tie_2"]
    else:
        expected = ["wf_tie_0", "wf_tie_1", "wf_tie_2", "wf_tail"]
    assert seen == expected
    assert [item for item in seen if item.startswith("wf_tie_")] == [
        "wf_tie_0",
        "wf_tie_1",
        "wf_tie_2",
    ]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "changed",
    [
        {"meaningVi": "vung"},
        {"lemma": "alpha"},
        {"partOfSpeech": "NOUN"},
        {"verificationStatus": "MISSING"},
        {"noteDate": "2026-09-30"},
        {"sourceStatus": "INVALID"},
        {"sortBy": "lemma"},
        {"sortOrder": "DESC"},
    ],
)
async def test_cursor_binds_every_filter_and_sort(
    client: AsyncClient, app: FastAPI, changed: dict[str, str]
) -> None:
    add_form(app, form_id="wf_02", lemma="alpha", meaning="vững chắc")
    first = await client.get("/api/v1/word-forms", params={"pageSize": 1})
    cursor = first.json()["pagination"]["nextCursor"]
    response = await client.get(
        "/api/v1/word-forms", params={"pageSize": 1, "cursor": cursor} | changed
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CURSOR_EXPIRED"


@pytest.mark.anyio
@pytest.mark.parametrize("cursor", ["a.b", "é", "....", "e30.A", "", "=" * 20])
async def test_malformed_cursors_never_escape_as_500(client: AsyncClient, cursor: str) -> None:
    response = await client.get("/api/v1/word-forms", params={"cursor": cursor})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CURSOR_EXPIRED"


@pytest.mark.anyio
async def test_process_key_change_rejects_prior_cursor(client: AsyncClient, app: FastAPI) -> None:
    from secrets import token_bytes

    from backend.app.vocabulary.search_service import SearchService

    add_form(app, form_id="wf_02", lemma="alpha", meaning="vững chắc")
    first = await client.get("/api/v1/word-forms", params={"pageSize": 1})
    cursor = first.json()["pagination"]["nextCursor"]
    app.state.search_service = SearchService(app.state.database.engine, signing_key=token_bytes(32))
    response = await client.get("/api/v1/word-forms", params={"pageSize": 1, "cursor": cursor})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CURSOR_EXPIRED"


@pytest.mark.anyio
async def test_read_endpoints_work_without_network_or_ai(client: AsyncClient, app: FastAPI) -> None:
    with patch("socket.socket.connect", side_effect=AssertionError("Network forbidden")):
        collection = await client.get("/api/v1/word-forms", params={"meaningVi": "vung"})
        detail = await client.get("/api/v1/word-forms/wf_01")
    assert collection.status_code == detail.status_code == 200
    assert app.state.active_ai_policy is None
    assert collection.json()["data"][0]["id"] == detail.json()["id"]
    assert not {"relativePath", "normalized_lemma", "etag", "content_hash"} & detail.json().keys()


@pytest.mark.anyio
@pytest.mark.parametrize("change", ["link", "unlink", "status", "revision"])
async def test_relationship_and_source_state_expire_outstanding_cursor(
    client: AsyncClient, app: FastAPI, change: str
) -> None:
    add_form(app, form_id="wf_02", lemma="alpha", meaning="vững chắc")
    add_form(app, form_id="wf_03", lemma="beta", meaning="vững chắc")
    repo = VocabularyRepository(app.state.database.engine)
    if change == "link":
        repo.unlink_source_from_form("wf_01", "src_01")
    params = {"meaningVi": "vung", "pageSize": "1"}
    first = await client.get("/api/v1/word-forms", params=params)
    cursor = first.json()["pagination"]["nextCursor"]
    assert cursor
    if change == "link":
        repo.link_word_form_to_source("wf_01", "src_01", "2026-09-29")
    elif change == "unlink":
        repo.unlink_source_from_form("wf_01", "src_01")
    elif change == "status":
        repo.update_source_status("src_01", "MISSING")
    else:
        repo.save_source_file(
            source_id="src_01",
            relative_path="29-09-2026.md",
            note_date="2026-09-29",
            status="VALID",
            revision=2,
        )
    response = await client.get("/api/v1/word-forms", params=params | {"cursor": cursor})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CURSOR_EXPIRED"


@pytest.mark.anyio
@pytest.mark.parametrize("meaning", [None, "vung"])
async def test_first_page_incompatible_projection_is_typed_configuration_failure(
    client: AsyncClient, app: FastAPI, meaning: str | None
) -> None:
    app.state.search_service.index.set_version("incompatible")
    params = {} if meaning is None else {"meaningVi": meaning}
    response = await client.get("/api/v1/word-forms", params=params)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "CONFIGURATION_REQUIRED"
    assert "incompatible" not in response.text
    assert app.state.search_service.index.get_version() == "incompatible"


@pytest.mark.anyio
async def test_incompatible_projection_survives_app_restart_as_typed_failure(app: FastAPI) -> None:
    app.state.search_service.index.set_version("incompatible")
    restarted = create_app(app.state.settings)
    async with (
        restarted.router.lifespan_context(restarted),
        AsyncClient(
            transport=ASGITransport(app=restarted), base_url=BASE, headers={"Origin": BASE}
        ) as http,
    ):
        token = restarted.state.sessions.issue_bootstrap_token()
        exchanged = await http.post("/bootstrap/exchange", json={"token": token})
        assert exchanged.status_code == 204
        http.headers["Cookie"] = exchanged.headers["set-cookie"].split(";", 1)[0]
        response = await http.get("/api/v1/word-forms", params={"meaningVi": "vung"})
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "CONFIGURATION_REQUIRED"
        assert (await http.get("/api/v1/word-forms/wf_01")).status_code == 200


@pytest.mark.anyio
@pytest.mark.parametrize("with_cursor", [False, True])
async def test_projection_mismatch_during_candidate_iteration_is_typed(
    client: AsyncClient, app: FastAPI, with_cursor: bool
) -> None:
    from backend.app.vocabulary.search_index import ProjectionVersionMismatchError

    add_form(app, form_id="wf_02", lemma="alpha", meaning="vững chắc")
    params = {"meaningVi": "vung", "pageSize": "1"}
    first = await client.get("/api/v1/word-forms", params=params)
    if with_cursor:
        params["cursor"] = first.json()["pagination"]["nextCursor"]
    with patch.object(
        app.state.search_service.index,
        "iter_search_candidates",
        side_effect=ProjectionVersionMismatchError("private projection details"),
    ):
        response = await client.get("/api/v1/word-forms", params=params)
    assert response.status_code == (409 if with_cursor else 503)
    assert response.json()["error"]["code"] == (
        "CURSOR_EXPIRED" if with_cursor else "CONFIGURATION_REQUIRED"
    )
    assert "private projection details" not in response.text

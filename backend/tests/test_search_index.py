"""Tests for Vietnamese search projection index, normalization, and infix search (T026)."""

import unicodedata
from pathlib import Path

import pytest
from backend.app.vocabulary.models import (
    ExampleSentence,
    MeaningEn,
    MeaningVi,
    SourceFile,
    SourceReference,
    SourceStatus,
    WordForm,
)
from backend.app.vocabulary.normalization import (
    escape_like_meta,
    generate_ngrams,
    normalize_accent_fold,
    normalize_exact,
)
from backend.app.vocabulary.search_index import (
    PROJECTION_VERSION,
    ProjectionVersionMismatchError,
    SearchIndex,
    StaleSourceRevisionError,
)
from sqlalchemy import create_engine


# Helper fixture creating synthetic canonical word form
def make_word_form(
    *,
    form_id: str,
    lemma: str,
    pos: str,
    meanings_vi: list[str],
    meanings_en: list[str] | None = None,
    examples: list[tuple[str, str]] | None = None,
    source_refs: list[SourceReference] | None = None,
    revision: int = 1,
) -> WordForm:
    vi_objects = [MeaningVi(text=m, verification_status="VERIFIED") for m in meanings_vi]
    en_objects = [MeaningEn(text=m, verification_status="VERIFIED") for m in (meanings_en or [])]
    ex_objects = [
        ExampleSentence(english=ex[0], vietnamese=ex[1], verification_status="VERIFIED")
        for ex in (examples or [])
    ]
    return WordForm(
        id=form_id,
        family_id="fam_01",
        lemma=lemma,
        normalized_lemma=lemma.lower(),
        part_of_speech=pos,
        meanings_en=en_objects,
        meanings_vi=vi_objects,
        examples=ex_objects,
        ipa_us="/r\u0259\u02c8b\u028cst/",
        ipa_status="VERIFIED",
        cambridge_url="https://dictionary.cambridge.org/dictionary/english/robust",
        cambridge_status="VERIFIED",
        verification_summary="VERIFIED",
        revision=revision,
        created_at="2026-09-29T10:00:00Z",
        updated_at="2026-09-29T10:00:00Z",
        source_refs=source_refs or [],
    )


def make_source_file(
    source_id: str,
    note_date: str = "2026-09-29",
    status: SourceStatus = "VALID",
    revision: int = 1,
) -> SourceFile:
    return SourceFile(
        id=source_id,
        relative_path=f"{note_date}.md",
        note_date=note_date,
        status=status,
        revision=revision,
        etag=f"etag_{source_id}_r{revision}",
        content_hash=f"hash_{source_id}",
        last_parsed_at="2026-09-29T10:00:00Z",
        error_code=None,
        created_at="2026-09-29T10:00:00Z",
        updated_at="2026-09-29T10:00:00Z",
    )


# =============================================================================
# A. NORMALIZATION TESTS
# =============================================================================


def test_normalization_nfc_equivalence() -> None:
    """Precomposed and combining-mark equivalent forms normalize to identical NFC strings."""
    precomposed = "bền vững"
    # Create decomposed form using NFD
    decomposed = unicodedata.normalize("NFD", precomposed)
    assert precomposed != decomposed  # byte/character sequences differ in NFD

    exact_pre = normalize_exact(precomposed)
    exact_dec = normalize_exact(decomposed)
    assert exact_pre == exact_dec
    assert exact_pre == "bền vững"


def test_normalization_casefold_behavior() -> None:
    """Casefolding handles upper/lower distinctions across Vietnamese letters."""
    upper = "ĐẠI HỌC VÀ NGHIÊN CỨU"
    lower = "đại học và nghiên cứu"
    assert normalize_exact(upper) == normalize_exact(lower)
    assert normalize_accent_fold(upper) == normalize_accent_fold(lower)


def test_normalization_d_stroke_folding() -> None:
    """Vietnamese đ and Đ map strictly to d in folded projection."""
    assert normalize_accent_fold("đáng tin cậy") == "dang tin cay"
    assert normalize_accent_fold("ĐIỀU KIỆN") == "dieu kien"
    assert normalize_accent_fold("đ") == "d"
    assert normalize_accent_fold("Đ") == "d"

    # Exact normalization retains đ
    assert "đ" in normalize_exact("đáng tin cậy")
    assert "d" not in normalize_exact("đ")


def test_normalization_exact_vs_folded_distinct() -> None:
    """Exact representation remains strictly distinct from folded representation."""
    exact = normalize_exact("bền vững")
    folded = normalize_accent_fold("bền vững")
    assert exact == "bền vững"
    assert folded == "ben vung"
    assert exact != folded


def test_normalization_all_vietnamese_vowels_and_tones() -> None:
    """All standard Vietnamese vowel modifications and tone marks fold cleanly to ASCII."""
    # a, ă, â
    assert normalize_accent_fold("cá cặc cần") == "ca cac can"
    # e, ê
    assert normalize_accent_fold("bé bên") == "be ben"
    # o, ô, ơ
    assert normalize_accent_fold("cò cô cơ") == "co co co"
    # u, ư
    assert normalize_accent_fold("cù cử") == "cu cu"
    # y
    assert normalize_accent_fold("kỳ mỹ") == "ky my"


def test_generate_ngrams_bounds() -> None:
    """N-gram generation produces bounded character n-grams from min_n to max_n."""
    ngrams = generate_ngrams("bền", min_n=1, max_n=3)
    # Length 3: 1-grams (3), 2-grams (2), 3-grams (1) -> total 6
    assert ngrams == {"b", "ề", "n", "bề", "ền", "bền"}

    # Empty or invalid range returns empty set
    assert generate_ngrams("") == set()
    assert generate_ngrams("test", min_n=3, max_n=2) == set()


def test_escape_like_meta() -> None:
    """LIKE metacharacters are properly escaped."""
    assert escape_like_meta("100%_success\\done") == "100\\%\\_success\\\\done"


# =============================================================================
# B. VIETNAMESE INFIX SEARCH TESTS
# =============================================================================


def test_vietnamese_infix_search_accented_and_folded() -> None:
    """Search matches accented substring and accent-folded substring."""
    src = make_source_file("src_01", status="VALID")
    form = make_word_form(
        form_id="wf_01",
        lemma="robust",
        pos="ADJECTIVE",
        meanings_vi=["vững chắc; đáng tin cậy"],
        source_refs=[SourceReference(source_id="src_01", note_date="2026-09-29", status="VALID")],
    )

    index = SearchIndex()
    index.build_from_forms([form], [src])

    # 1. Exact accented substring
    res1 = index.search("vững chắc")
    assert len(res1) == 1
    assert res1[0].word_form_id == "wf_01"

    # 2. Folded unaccented substring
    res2 = index.search("vung chac")
    assert len(res2) == 1
    assert res2[0].word_form_id == "wf_01"

    # 3. Middle infix
    res3 = index.search("ng ti")  # middle of 'đáng tin cậy'
    assert len(res3) == 1
    assert res3[0].word_form_id == "wf_01"

    # 4. End infix
    res4 = index.search("tin cậy")
    assert len(res4) == 1
    assert res4[0].word_form_id == "wf_01"

    # 5. One-character query
    res5 = index.search("đ")
    assert len(res5) == 1
    assert res5[0].word_form_id == "wf_01"

    res6 = index.search("d")  # folded đ -> d
    assert len(res6) == 1
    assert res6[0].word_form_id == "wf_01"

    res7 = index.search("ơ")
    assert len(res7) == 0  # not present in meaning


def test_vietnamese_infix_no_semantic_guessing() -> None:
    """Search does NOT perform semantic-equivalence or synonym guessing."""
    src = make_source_file("src_01", status="VALID")
    form = make_word_form(
        form_id="wf_01",
        lemma="robust",
        pos="ADJECTIVE",
        meanings_vi=["vững chắc"],
        source_refs=[SourceReference(source_id="src_01", note_date="2026-09-29", status="VALID")],
    )

    index = SearchIndex()
    index.build_from_forms([form], [src])

    # Synonym 'kiên cố' or 'bền bỉ' should not match when not in stored text
    assert len(index.search("kiên cố")) == 0
    assert len(index.search("bền bỉ")) == 0


# =============================================================================
# C. SEARCH CONTENT BOUNDARY TESTS
# =============================================================================


def test_search_content_boundary_meanings_vi_only() -> None:
    """Projection indexes meanings_vi only; examples and english meanings are excluded."""
    src = make_source_file("src_01", status="VALID")
    form = make_word_form(
        form_id="wf_01",
        lemma="robust",
        pos="ADJECTIVE",
        meanings_vi=["vững chắc"],
        meanings_en=["able to withstand difficult conditions"],
        examples=[
            ("The experiment uses a robust setup.", "Thí nghiệm sử dụng một thiết kế vững chắc.")
        ],
        source_refs=[SourceReference(source_id="src_01", note_date="2026-09-29", status="VALID")],
    )

    index = SearchIndex()
    index.build_from_forms([form], [src])

    # Vietnamese example translation has 'thí nghiệm' and 'thiết kế', but meanings_vi does not
    assert len(index.search("thí nghiệm")) == 0
    assert len(index.search("thiết kế")) == 0

    # English meaning has 'withstand', meanings_vi does not
    assert len(index.search("withstand")) == 0

    # meaning_vi matches
    assert len(index.search("vững chắc")) == 1


# =============================================================================
# D. DISTINCT POS TESTS
# =============================================================================


def test_distinct_pos_preserved_as_separate_results() -> None:
    """Forms with same lemma and family but different POS remain distinct search results."""
    src = make_source_file("src_01", status="VALID")
    form_noun = make_word_form(
        form_id="wf_noun",
        lemma="measure",
        pos="NOUN",
        meanings_vi=["biện pháp; phương pháp"],
        source_refs=[SourceReference(source_id="src_01", note_date="2026-09-29", status="VALID")],
    )
    form_verb = make_word_form(
        form_id="wf_verb",
        lemma="measure",
        pos="VERB",
        meanings_vi=["đo lường; đánh giá"],
        source_refs=[SourceReference(source_id="src_01", note_date="2026-09-29", status="VALID")],
    )

    index = SearchIndex()
    index.build_from_forms([form_noun, form_verb], [src])

    # Search for common substring 'pháp' -> matches only noun
    res_noun = index.search("pháp")
    assert len(res_noun) == 1
    assert res_noun[0].word_form_id == "wf_noun"
    assert res_noun[0].part_of_speech == "NOUN"

    # Search for 'đo lường' -> matches only verb
    res_verb = index.search("đo lường")
    assert len(res_verb) == 1
    assert res_verb[0].word_form_id == "wf_verb"
    assert res_verb[0].part_of_speech == "VERB"


def test_no_duplicate_results_for_multiple_date_links() -> None:
    """A word form linked to multiple sources/dates is returned exactly once."""
    src1 = make_source_file("src_01", note_date="2026-09-29", status="VALID")
    src2 = make_source_file("src_02", note_date="2026-09-30", status="VALID")
    form = make_word_form(
        form_id="wf_multi_date",
        lemma="robust",
        pos="ADJECTIVE",
        meanings_vi=["vững chắc"],
        source_refs=[
            SourceReference(source_id="src_01", note_date="2026-09-29", status="VALID"),
            SourceReference(source_id="src_02", note_date="2026-09-30", status="VALID"),
        ],
    )

    index = SearchIndex()
    index.build_from_forms([form], [src1, src2])

    results = index.search("vững chắc")
    assert len(results) == 1
    assert results[0].word_form_id == "wf_multi_date"
    assert set(results[0].note_dates) == {"2026-09-29", "2026-09-30"}


# =============================================================================
# E. SOURCE VALIDITY TESTS
# =============================================================================


def test_source_validity_lifecycle() -> None:
    """Forms are searchable only with at least one VALID source; invalidating removes visibility."""
    src1 = make_source_file("src_01", note_date="2026-09-29", status="VALID")
    src2 = make_source_file("src_02", note_date="2026-09-30", status="INVALID")
    src3 = make_source_file("src_03", note_date="2026-10-01", status="MISSING")

    # Form A: valid source only -> searchable
    form_a = make_word_form(
        form_id="wf_a",
        lemma="valid_only",
        pos="ADJECTIVE",
        meanings_vi=["nguồn hợp lệ"],
        source_refs=[SourceReference(source_id="src_01", note_date="2026-09-29", status="VALID")],
    )

    # Form B: invalid source only -> NOT searchable
    form_b = make_word_form(
        form_id="wf_b",
        lemma="invalid_only",
        pos="ADJECTIVE",
        meanings_vi=["nguồn lỗi"],
        source_refs=[SourceReference(source_id="src_02", note_date="2026-09-30", status="INVALID")],
    )

    # Form C: missing source only -> NOT searchable
    form_c = make_word_form(
        form_id="wf_c",
        lemma="missing_only",
        pos="ADJECTIVE",
        meanings_vi=["nguồn thiếu"],
        source_refs=[SourceReference(source_id="src_03", note_date="2026-10-01", status="MISSING")],
    )

    # Form D: linked to VALID + INVALID -> searchable through VALID
    form_d = make_word_form(
        form_id="wf_d",
        lemma="mixed_sources",
        pos="ADJECTIVE",
        meanings_vi=["nguồn hỗn hợp"],
        source_refs=[
            SourceReference(source_id="src_01", note_date="2026-09-29", status="VALID"),
            SourceReference(source_id="src_02", note_date="2026-09-30", status="INVALID"),
        ],
    )

    index = SearchIndex()
    index.build_from_forms([form_a, form_b, form_c, form_d], [src1, src2, src3])

    # A and D searchable; B and C not searchable
    assert len(index.search("hợp lệ")) == 1
    assert len(index.search("nguồn lỗi")) == 0
    assert len(index.search("nguồn thiếu")) == 0
    assert len(index.search("hỗn hợp")) == 1

    # Invalidate src_01: Form A loses all valid sources; Form D loses its only valid source
    index.invalidate_source("src_01", source_revision=2, affected_forms=[form_a, form_d])

    # Now Form A and Form D are no longer active in projection
    assert len(index.search("hợp lệ")) == 0
    assert len(index.search("hỗn hợp")) == 0

    # Restore src_01 with VALID status
    src1_restored = make_source_file("src_01", note_date="2026-09-29", status="VALID", revision=3)
    index.update_source(src1_restored, [form_a, form_d])

    # Both become searchable again
    assert len(index.search("hợp lệ")) == 1
    assert len(index.search("hỗn hợp")) == 1


# =============================================================================
# F. UPDATE TESTS
# =============================================================================


def test_meaning_update_replaces_stale_terms() -> None:
    """When a meaning changes, old terms cease matching and new terms match."""
    src = make_source_file("src_01", status="VALID")
    form = make_word_form(
        form_id="wf_01",
        lemma="robust",
        pos="ADJECTIVE",
        meanings_vi=["vững chắc"],
        source_refs=[SourceReference(source_id="src_01", note_date="2026-09-29", status="VALID")],
    )

    index = SearchIndex()
    index.build_from_forms([form], [src])

    assert len(index.search("vững chắc")) == 1
    assert len(index.search("kiên cố")) == 0

    # Update meaning to 'kiên cố'
    updated_form = make_word_form(
        form_id="wf_01",
        lemma="robust",
        pos="ADJECTIVE",
        meanings_vi=["kiên cố"],
        source_refs=[SourceReference(source_id="src_01", note_date="2026-09-29", status="VALID")],
        revision=2,
    )
    index.update_word_form(updated_form)

    # Old term stops matching
    assert len(index.search("vững chắc")) == 0
    # New term matches
    res = index.search("kiên cố")
    assert len(res) == 1
    assert res[0].word_form_id == "wf_01"
    assert res[0].meaning_vi_match == "kiên cố"
    assert res[0].revision == 2


# =============================================================================
# G. REBUILD AND REPEATABILITY TESTS
# =============================================================================


def test_rebuild_repeatable_and_non_destructive(tmp_path: Path) -> None:
    """Rebuild is idempotent and does not delete unrelated tables."""
    db_path = tmp_path / "temp_vocab.db"
    engine = create_engine(f"sqlite:///{db_path}")

    # Create a synthetic durable history table to prove rebuild does NOT delete it
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE durable_sentinel (key TEXT PRIMARY KEY, val TEXT)")
        conn.exec_driver_sql("INSERT INTO durable_sentinel VALUES ('history_1', 'preserved_state')")

    src = make_source_file("src_01", status="VALID")
    form = make_word_form(
        form_id="wf_01",
        lemma="robust",
        pos="ADJECTIVE",
        meanings_vi=["vững chắc"],
        source_refs=[SourceReference(source_id="src_01", note_date="2026-09-29", status="VALID")],
    )

    index = SearchIndex(engine=engine)
    index.build_from_forms([form], [src])

    assert len(index.search("vững chắc")) == 1

    # Rebuild on the same engine
    index.rebuild([form], [src])

    # Search works identically
    assert len(index.search("vững chắc")) == 1

    # Verify durable sentinel table is completely intact
    with engine.connect() as conn:
        row = conn.exec_driver_sql(
            "SELECT val FROM durable_sentinel WHERE key = 'history_1'"
        ).first()
        assert row is not None
        assert row[0] == "preserved_state"


# =============================================================================
# H. VERSION MISMATCH TESTS (NEGATIVE PROBE)
# =============================================================================


def test_version_mismatch_raises_explicit_error() -> None:
    """Version mismatch raises ProjectionVersionMismatchError, distinguishable from empty search."""
    src = make_source_file("src_01", status="VALID")
    form = make_word_form(
        form_id="wf_01",
        lemma="robust",
        pos="ADJECTIVE",
        meanings_vi=["vững chắc"],
        source_refs=[SourceReference(source_id="src_01", note_date="2026-09-29", status="VALID")],
    )

    index = SearchIndex()
    index.build_from_forms([form], [src])

    # 1. Negative probe: version mismatch must raise ProjectionVersionMismatchError
    with pytest.raises(ProjectionVersionMismatchError) as exc_info:
        index.search("vững", expected_version="v2-incompatible-version")
    assert "Projection version mismatch" in str(exc_info.value)

    # 2. Distinguishable positive case: valid version with no matching forms returns []
    empty_res = index.search("từ không có trong từ điển", expected_version=PROJECTION_VERSION)
    assert empty_res == []


# =============================================================================
# I. SOURCE REVISION CONSISTENCY TESTS (NEGATIVE PROBE)
# =============================================================================


def test_stale_source_revision_fails_explicitly() -> None:
    """Stale source revision update is rejected and leaves existing projection intact."""
    src_v5 = make_source_file("src_01", status="VALID", revision=5)
    form = make_word_form(
        form_id="wf_01",
        lemma="robust",
        pos="ADJECTIVE",
        meanings_vi=["vững chắc"],
        source_refs=[SourceReference(source_id="src_01", note_date="2026-09-29", status="VALID")],
    )

    index = SearchIndex()
    index.build_from_forms([form], [src_v5])

    # Attempt to apply a stale source revision (revision 4 < current 5)
    stale_src = make_source_file("src_01", status="VALID", revision=4)
    with pytest.raises(StaleSourceRevisionError) as exc_info:
        index.update_source(stale_src, [form])
    assert "Stale source revision 4" in str(exc_info.value)

    # Invalidate with stale revision must also fail
    with pytest.raises(StaleSourceRevisionError) as exc_info_inv:
        index.invalidate_source("src_01", source_revision=3, affected_forms=[form])
    assert "Stale source revision 3" in str(exc_info_inv.value)

    # Existing projection remains intact and searchable
    assert len(index.search("vững chắc")) == 1


# =============================================================================
# J. QUERY SAFETY AND PARAMETERIZATION TESTS
# =============================================================================


def test_query_safety_sql_metacharacters() -> None:
    """Queries with SQL metacharacters, quotes, and wildcards are treated as literal data."""
    src = make_source_file("src_01", status="VALID")
    form_normal = make_word_form(
        form_id="wf_normal",
        lemma="normal",
        pos="NOUN",
        meanings_vi=["bình thường"],
        source_refs=[SourceReference(source_id="src_01", note_date="2026-09-29", status="VALID")],
    )
    form_special = make_word_form(
        form_id="wf_special",
        lemma="rate",
        pos="NOUN",
        meanings_vi=["tỉ lệ 50% [ước tính]; giá trị_chuẩn (theo 'tiêu chuẩn')"],
        source_refs=[SourceReference(source_id="src_01", note_date="2026-09-29", status="VALID")],
    )

    index = SearchIndex()
    index.build_from_forms([form_normal, form_special], [src])

    # 1. SQL Injection strings
    injection_queries = [
        "'; DROP TABLE search_projection_entries; --",
        "' OR 1=1 --",
        '" OR "a"="a"',
        "admin'--",
    ]
    for q in injection_queries:
        res = index.search(q)
        assert res == []  # does not crash, does not return all records

    # 2. Metacharacters matched literally
    res_pct = index.search("50%")
    assert len(res_pct) == 1
    assert res_pct[0].word_form_id == "wf_special"

    res_quote = index.search("'tiêu chuẩn'")
    assert len(res_quote) == 1
    assert res_quote[0].word_form_id == "wf_special"

    res_brackets = index.search("[ước tính]")
    assert len(res_brackets) == 1
    assert res_brackets[0].word_form_id == "wf_special"

    res_under = index.search("giá trị_chuẩn")
    assert len(res_under) == 1
    assert res_under[0].word_form_id == "wf_special"

    # Literal % or _ does not act as wildcards to match form_normal
    res_wildcard_pct = index.search("%")
    assert all(r.word_form_id != "wf_normal" for r in res_wildcard_pct)


# =============================================================================
# K. FTS OPTIONALITY TEST
# =============================================================================


def test_fts5_not_required_for_correctness() -> None:
    """Search projection operates correctly and deterministically without FTS5 tables."""
    index = SearchIndex()
    # Verify no FTS5 tables are created in the database
    with index.engine.connect() as conn:
        tables = [
            row[0]
            for row in conn.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        ]
        assert not any("fts" in t.lower() for t in tables)

    # Search correctness is proven independently of FTS5
    src = make_source_file("src_01", status="VALID")
    form = make_word_form(
        form_id="wf_01",
        lemma="robust",
        pos="ADJECTIVE",
        meanings_vi=["vững chắc"],
        source_refs=[SourceReference(source_id="src_01", note_date="2026-09-29", status="VALID")],
    )
    index.build_from_forms([form], [src])
    assert len(index.search("vững chắc")) == 1
    assert len(index.search("vung chac")) == 1


# =============================================================================
# L. BRANCH COVERAGE AND EDGE CASE TESTS
# =============================================================================


def test_normalization_empty_and_whitespace() -> None:
    """Empty or whitespace text normalizes to empty string."""
    assert normalize_exact("") == ""
    assert normalize_exact("   ") == ""
    assert normalize_accent_fold("") == ""
    assert normalize_accent_fold("   ") == ""


def test_search_empty_and_whitespace_queries() -> None:
    """Empty or whitespace search query returns empty list without error."""
    index = SearchIndex()
    assert index.search("") == []
    assert index.search("   ") == []
    assert index.search("\t\n") == []


def test_search_version_mutations() -> None:
    """Projection version can be inspected and updated for simulation."""
    index = SearchIndex()
    assert index.get_version() == PROJECTION_VERSION
    index.set_version("v2-test")
    assert index.get_version() == "v2-test"
    with pytest.raises(ProjectionVersionMismatchError):
        index.search("test", expected_version=PROJECTION_VERSION)


def test_search_result_item_to_dict() -> None:
    """SearchResultItem converts to dictionary conforming to WordFormSummary contract."""
    src = make_source_file("src_01", note_date="2026-09-29", status="VALID")
    form = make_word_form(
        form_id="wf_01",
        lemma="robust",
        pos="ADJECTIVE",
        meanings_vi=["vững chắc"],
        source_refs=[SourceReference(source_id="src_01", note_date="2026-09-29", status="VALID")],
    )
    index = SearchIndex()
    index.build_from_forms([form], [src])
    results = index.search("vững chắc")
    assert len(results) == 1
    item = results[0]
    d = item.to_dict()
    assert d["id"] == "wf_01"
    assert d["lemma"] == "robust"
    assert d["partOfSpeech"] == "ADJECTIVE"
    assert d["meaningViMatch"] == "vững chắc"
    assert d["verificationSummary"] == "VERIFIED"
    assert d["noteDates"] == ["2026-09-29"]
    assert d["revision"] == 1
    assert "updatedAt" in d


def test_search_pagination_offset_limit() -> None:
    """Search results respect limit and offset bounds."""
    src = make_source_file("src_01", status="VALID")
    forms = [
        make_word_form(
            form_id=f"wf_{i:02d}",
            lemma=f"word_{i}",
            pos="NOUN",
            meanings_vi=[f"nghĩa tiếng Việt thứ {i}"],
            source_refs=[
                SourceReference(source_id="src_01", note_date="2026-09-29", status="VALID")
            ],
        )
        for i in range(10)
    ]
    index = SearchIndex()
    index.build_from_forms(forms, [src])

    # Query matching all 10 forms
    all_res = index.search("tiếng Việt", limit=100)
    assert len(all_res) == 10

    # Limit 3
    res_p1 = index.search("tiếng Việt", limit=3, offset=0)
    assert len(res_p1) == 3

    # Offset 3, limit 3
    res_p2 = index.search("tiếng Việt", limit=3, offset=3)
    assert len(res_p2) == 3
    assert res_p1[0].word_form_id != res_p2[0].word_form_id


def test_update_source_brand_new_source() -> None:
    """update_source can add a brand-new source and index its forms."""
    index = SearchIndex()
    src = make_source_file("src_brand_new", status="VALID", revision=1)
    form = make_word_form(
        form_id="wf_new",
        lemma="novel",
        pos="ADJECTIVE",
        meanings_vi=["mới lạ"],
        source_refs=[
            SourceReference(source_id="src_brand_new", note_date="2026-09-29", status="VALID")
        ],
    )
    # Updating a source that wasn't in index yet
    index.update_source(src, [form])
    res = index.search("mới lạ")
    assert len(res) == 1
    assert res[0].word_form_id == "wf_new"


def test_caller_owned_search_update_is_atomic_and_preserves_guards(tmp_path: Path) -> None:
    index = SearchIndex(create_engine("sqlite:///" + str(tmp_path / "borrow.db")))
    src = make_source_file("borrowed")
    form = make_word_form(
        form_id="borrowed-form",
        lemma="robust",
        pos="ADJECTIVE",
        meanings_vi=["bền vững"],
        source_refs=[SourceReference(src.id, src.note_date, src.status)],
    )
    with pytest.raises(RuntimeError, match="rollback"), index.engine.begin() as conn:
        index.update_source(src, [form], connection=conn)
        assert (
            conn.exec_driver_sql("SELECT count(*) FROM search_projection_entries").scalar_one() == 1
        )
        raise RuntimeError("rollback")
    assert index.search("ben vung") == []
    index.update_source(src, [form])
    newer = make_source_file("borrowed", revision=2)
    with index.engine.begin() as conn:
        index.update_source(newer, [form], connection=conn)
    with index.engine.begin() as conn, pytest.raises(StaleSourceRevisionError):
        index.update_source(src, [form], connection=conn)
    index.set_version("different")
    with index.engine.begin() as conn, pytest.raises(ProjectionVersionMismatchError):
        index.update_source(newer, [form], connection=conn)
    with index.engine.connect() as conn, pytest.raises(ValueError, match="active transaction"):
        index.update_source(newer, [form], connection=conn)
    index.engine.dispose()

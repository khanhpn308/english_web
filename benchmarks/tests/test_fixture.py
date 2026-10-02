"""Deterministic T042 fixture and independent ground-truth tests."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unicodedata
from pathlib import Path

import pytest
from backend.app.vocabulary.models import MeaningVi, SourceFile, SourceReference, WordForm
from backend.app.vocabulary.search_index import SearchIndex
from benchmarks.generate_fixture import (
    DEFAULT_FORM_COUNT,
    DEFAULT_SEED,
    FixtureValidationError,
    build_query_specs,
    generate_fixture,
    independent_match_ids,
    iter_fixture_rows,
    validate_fixture_file,
    validate_report,
)

ROOT = Path(__file__).resolve().parents[2]


def test_small_generation_is_byte_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    generate_fixture(64, DEFAULT_SEED, first)
    generate_fixture(64, DEFAULT_SEED, second)
    for name in ("fixtures/100k_forms.jsonl", "artifacts/search-report.json"):
        assert (first / name).read_bytes() == (second / name).read_bytes()


def test_alternate_seed_changes_fixture_and_report(tmp_path: Path) -> None:
    first = tmp_path / "seed29"
    second = tmp_path / "seed30"
    generate_fixture(64, 29, first)
    generate_fixture(64, 30, second)
    assert (first / "fixtures/100k_forms.jsonl").read_bytes() != (
        second / "fixtures/100k_forms.jsonl"
    ).read_bytes()
    assert (first / "artifacts/search-report.json").read_bytes() != (
        second / "artifacts/search-report.json"
    ).read_bytes()


def test_query_set_has_exactly_100_fixed_specs() -> None:
    specs = build_query_specs()
    assert len(specs) == 100
    assert len({spec["id"] for spec in specs}) == 100
    assert any(spec["category"] == "one-character" for spec in specs)
    assert any(spec["category"] == "combining-mark" for spec in specs)


def test_small_fixture_schema_count_and_unique_ids(tmp_path: Path) -> None:
    generate_fixture(128, DEFAULT_SEED, tmp_path)
    summary = validate_fixture_file(tmp_path / "fixtures/100k_forms.jsonl", 128)
    assert summary.form_count == 128
    assert summary.unique_ids == 128
    rows = list(iter_fixture_rows(tmp_path / "fixtures/100k_forms.jsonl"))
    assert all(row["meaningsVi"] for row in rows)
    assert all(row["sourceRefs"][0]["status"] == "VALID" for row in rows)


def test_independent_oracle_covers_zero_single_and_many(tmp_path: Path) -> None:
    generate_fixture(256, DEFAULT_SEED, tmp_path)
    rows = list(iter_fixture_rows(tmp_path / "fixtures/100k_forms.jsonl"))
    counts = {
        query: len(independent_match_ids(rows, query))
        for query in ("kiên cố", "bền vững", "học", "không tồn tại")
    }
    assert counts["kiên cố"] == 0
    assert counts["bền vững"] == 1
    assert counts["học"] > 1
    assert counts["không tồn tại"] == 0


def test_reference_oracle_nfc_combining_and_folded_cases(tmp_path: Path) -> None:
    generate_fixture(64, DEFAULT_SEED, tmp_path)
    rows = list(iter_fixture_rows(tmp_path / "fixtures/100k_forms.jsonl"))
    precomposed = independent_match_ids(rows, "cà phê")
    combining = independent_match_ids(rows, unicodedata.normalize("NFD", "cà phê"))
    folded = independent_match_ids(rows, "ca phe")
    assert precomposed == combining == folded
    assert independent_match_ids(rows, "dieu kien")
    assert independent_match_ids(rows, "50%")
    assert independent_match_ids(rows, "giá trị_chuẩn")


def test_bounded_sample_matches_t026(tmp_path: Path) -> None:
    generate_fixture(96, DEFAULT_SEED, tmp_path)
    rows = list(iter_fixture_rows(tmp_path / "fixtures/100k_forms.jsonl"))
    sources = [_source(row["sourceRefs"][0]["sourceId"]) for row in rows]
    forms = [_word_form(row) for row in rows]
    index = SearchIndex()
    index.build_from_forms(forms, sources)
    for query in ("bền vững", "ben vung", "đ", "dieu kien", "50%", "kiên cố"):
        actual = [item.word_form_id for item in index.search(query, limit=1000)]
        expected = independent_match_ids(rows, query)
        assert set(actual) == set(expected)


def test_duplicate_and_malformed_rows_are_rejected(tmp_path: Path) -> None:
    generate_fixture(8, DEFAULT_SEED, tmp_path)
    path = tmp_path / "fixtures/100k_forms.jsonl"
    rows = list(iter_fixture_rows(path))
    rows[1]["id"] = rows[0]["id"]
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
    )
    with pytest.raises(FixtureValidationError, match="duplicate form id"):
        validate_fixture_file(path, 8)
    rows[1]["id"] = "t042-29-000001"
    rows[1].pop("meaningsVi")
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
    )
    with pytest.raises(FixtureValidationError, match="meaningsVi"):
        validate_fixture_file(path, 8)


def test_incomplete_fixture_is_rejected(tmp_path: Path) -> None:
    generate_fixture(8, DEFAULT_SEED, tmp_path)
    path = tmp_path / "fixtures/100k_forms.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    path.write_text("".join(lines[:-1]), encoding="utf-8")
    with pytest.raises(FixtureValidationError, match="expected 8 records"):
        validate_fixture_file(path, 8)


def test_report_checksums_and_fixture_binding_are_validated(tmp_path: Path) -> None:
    generate_fixture(32, DEFAULT_SEED, tmp_path)
    fixture = tmp_path / "fixtures/100k_forms.jsonl"
    report_path = tmp_path / "artifacts/search-report.json"
    report = validate_report(report_path, fixture, 32, DEFAULT_SEED)
    assert report["fixtureSha256"] == hashlib.sha256(fixture.read_bytes()).hexdigest()
    report["fixtureSha256"] = "0" * 64
    report_path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(FixtureValidationError, match="fixture checksum mismatch"):
        validate_report(report_path, fixture, 32, DEFAULT_SEED)


def test_cli_rejects_invalid_count(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "benchmarks/generate_fixture.py"),
            "--forms",
            "0",
            "--output-dir",
            str(tmp_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "forms must be between" in result.stderr


def test_cli_rejects_malformed_seed(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "benchmarks/generate_fixture.py"),
            "--forms",
            "1",
            "--seed",
            "not-an-integer",
            "--output-dir",
            str(tmp_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "seed must be an integer" in result.stderr


def test_full_count_constant_documents_required_command() -> None:
    assert DEFAULT_FORM_COUNT == 100_000


def _source(source_id: str) -> SourceFile:
    return SourceFile(
        id=source_id,
        relative_path=f"{source_id}.md",
        note_date="2026-01-01",
        status="VALID",
        revision=1,
        etag=f"etag-{source_id}",
        content_hash=f"hash-{source_id}",
        last_parsed_at="2026-01-01T00:00:00Z",
        error_code=None,
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )


def _word_form(row: dict[str, object]) -> WordForm:
    meanings = [str(value) for value in row["meaningsVi"]]
    refs = [
        SourceReference(
            source_id=str(ref["sourceId"]),
            note_date=str(ref["noteDate"]),
            status=str(ref["status"]),
        )
        for ref in row["sourceRefs"]
    ]
    return WordForm(
        id=str(row["id"]),
        family_id=str(row["familyId"]),
        lemma=str(row["lemma"]),
        normalized_lemma=str(row["normalizedLemma"]),
        part_of_speech=str(row["partOfSpeech"]),
        meanings_en=[],
        meanings_vi=[
            MeaningVi(text=meaning, verification_status="VERIFIED") for meaning in meanings
        ],
        examples=[],
        ipa_us="/synthetic/",
        ipa_status="VERIFIED",
        cambridge_url="https://example.invalid/t042",
        cambridge_status="VERIFIED",
        verification_summary="VERIFIED",
        revision=int(row["revision"]),
        created_at=str(row["createdAt"]),
        updated_at=str(row["updatedAt"]),
        source_refs=refs,
    )

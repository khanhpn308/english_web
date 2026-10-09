"""Focused unit tests for T065 deterministic search benchmark harness.

Tests parsing, fixture integrity validation, percentiles, correctness comparison,
timing boundary validation, and verdict decisions across all 15 required cases.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from benchmarks.generate_fixture import (
    DEFAULT_SEED,
    FixtureValidationError,
    build_query_specs,
    generate_fixture,
    validate_fixture_file,
    validate_report,
)
from benchmarks.search_benchmark import (
    AC07_QUERY_ID,
    QueryTiming,
    calculate_percentiles,
    evaluate_correctness,
    evaluate_scenario,
)


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def _make_timing(
    query_id: str = "q001-exact-unique",
    duration_ms: float = 100.0,
    matched_expected: bool = True,
    actual_ids: list[str] | None = None,
    expected_ids: list[str] | None = None,
) -> QueryTiming:
    ids = ["id_01"] if actual_ids is None else actual_ids
    exp = ["id_01"] if expected_ids is None else expected_ids
    return QueryTiming(
        query_id=query_id,
        query="bền vững",
        category="exact-unique",
        duration_ms=duration_ms,
        status="PASS" if matched_expected else "FAIL",
        returned_count=len(ids),
        matched_expected=matched_expected,
        actual_ids=ids,
        expected_ids=exp,
    )


# 1. Valid report parsing
def test_case_01_valid_report_parsing(tmp_path: Path) -> None:
    generate_fixture(16, DEFAULT_SEED, tmp_path)
    report_path = tmp_path / "artifacts/search-report.json"
    fixture_path = tmp_path / "fixtures/100k_forms.jsonl"
    report = validate_report(report_path, fixture_path, 16, DEFAULT_SEED)
    assert report["seed"] == DEFAULT_SEED
    assert report["actualFormCount"] == 16
    assert report["queryCount"] == 100
    assert len(report["queries"]) == 100


# 2. Missing/malformed fixture metadata
def test_case_02_missing_malformed_fixture_metadata(tmp_path: Path) -> None:
    fixture_path = tmp_path / "corrupt_forms.jsonl"
    corrupt_row = {
        "schemaVersion": "t042-fixture-v1",
        "id": "t042-29-000000",
        # missing meaningsVi, lemma, partOfSpeech, etc.
    }
    fixture_path.write_text(json.dumps(corrupt_row) + "\n", encoding="utf-8")
    with pytest.raises(FixtureValidationError, match="missing fields"):
        validate_fixture_file(fixture_path, 1)


# 3. Incorrect fixture checksum
def test_case_03_incorrect_fixture_checksum(tmp_path: Path) -> None:
    generate_fixture(16, DEFAULT_SEED, tmp_path)
    report_path = tmp_path / "artifacts/search-report.json"
    fixture_path = tmp_path / "fixtures/100k_forms.jsonl"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["fixtureSha256"] = "a" * 64
    report_path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(FixtureValidationError, match="fixture checksum mismatch"):
        validate_report(report_path, fixture_path, 16, DEFAULT_SEED)


# 4. Wrong query count
def test_case_04_wrong_query_count(tmp_path: Path) -> None:
    generate_fixture(16, DEFAULT_SEED, tmp_path)
    report_path = tmp_path / "artifacts/search-report.json"
    fixture_path = tmp_path / "fixtures/100k_forms.jsonl"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["queryCount"] = 99
    report["queries"] = report["queries"][:99]
    report_path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(FixtureValidationError, match="count mismatch"):
        validate_report(report_path, fixture_path, 16, DEFAULT_SEED)


# 5. Result-ID mismatch
def test_case_05_result_id_mismatch() -> None:
    actual = ["t042-29-000001", "t042-29-000002"]
    expected = ["t042-29-000001", "t042-29-000099"]
    assert evaluate_correctness(actual, expected) is False


# 6. Duplicate or missing results
def test_case_06_duplicate_or_missing_results() -> None:
    # Duplicate actual ID
    assert evaluate_correctness(["t042-01", "t042-01"], ["t042-01"]) is False
    # Missing expected result
    assert evaluate_correctness(["t042-01"], ["t042-01", "t042-02"]) is False
    # Extra unexpected result
    assert evaluate_correctness(["t042-01", "t042-02"], ["t042-01"]) is False


# 7. Zero-match correctness
def test_case_07_zero_match_correctness() -> None:
    # Empty actual with empty expected passes
    assert evaluate_correctness([], []) is True
    # Non-empty actual when expected is zero fails
    assert evaluate_correctness(["unexpected_match"], []) is False


# 8. Request-to-render timing boundary validation
def test_case_08_timing_boundary_validation() -> None:
    with pytest.raises(ValueError, match="empty sample set"):
        calculate_percentiles([])
    with pytest.raises(ValueError, match="non-negative"):
        calculate_percentiles([-0.5, 100.0])
    stats = calculate_percentiles([0.0])
    assert stats["p50"] == 0.0
    assert stats["min"] == 0.0
    assert stats["max"] == 0.0


# 9. p50/p95/p99 calculation
def test_case_09_p50_p95_p99_calculation() -> None:
    # 101 linear values from 0.0 to 100.0 ms
    samples = [float(i) for i in range(101)]
    stats = calculate_percentiles(samples)
    assert stats["p50"] == 50.0
    assert stats["p95"] == 95.0
    assert stats["p99"] == 99.0
    assert stats["min"] == 0.0
    assert stats["max"] == 100.0


# 10. Exactly 1000 ms threshold boundary
def test_case_10_exactly_1000ms_threshold_boundary() -> None:
    specs = build_query_specs()
    # All queries at exactly 1000.0 ms
    timings = [_make_timing(spec["id"], duration_ms=1000.0) for spec in specs]
    summary = evaluate_scenario("warm", timings, is_windows=True)
    assert summary.p95_ms == 1000.0
    assert summary.verdict == "PASS"

    # Just above threshold: 1000.01 ms
    timings_over = [_make_timing(spec["id"], duration_ms=1000.01) for spec in specs]
    summary_over = evaluate_scenario("warm", timings_over, is_windows=True)
    assert summary_over.verdict == "FAIL"
    assert any("exceeded threshold" in r for r in summary_over.verdict_reasons)


# 11. Slow response fails
def test_case_11_slow_response_fails() -> None:
    specs = build_query_specs()
    timings = [_make_timing(spec["id"], duration_ms=1500.0) for spec in specs]
    summary = evaluate_scenario("warm", timings, is_windows=True)
    assert summary.verdict == "FAIL"
    assert any("p95 latency" in r for r in summary.verdict_reasons)


# 12. Incorrect results fail even with fast timings
def test_case_12_incorrect_results_fail_even_with_fast_timings() -> None:
    specs = build_query_specs()
    timings = [_make_timing(spec["id"], duration_ms=10.0) for spec in specs]
    # Invalidate one query's correctness
    timings[5] = _make_timing(
        specs[5]["id"],
        duration_ms=10.0,
        matched_expected=False,
        actual_ids=["wrong"],
        expected_ids=["expected"],
    )
    summary = evaluate_scenario("warm", timings, is_windows=True)
    assert summary.p95_ms == 10.0
    assert summary.verdict == "FAIL"
    assert any("correctness failed" in r for r in summary.verdict_reasons)


# 13. Missing Windows evidence remains PENDING
def test_case_13_missing_windows_evidence_remains_pending() -> None:
    specs = build_query_specs()
    # Fast timings and correct results on Linux host
    timings = [_make_timing(spec["id"], duration_ms=50.0) for spec in specs]
    summary = evaluate_scenario("warm", timings, is_windows=False)
    assert summary.verdict == "PENDING"
    assert any("Windows 11" in r for r in summary.verdict_reasons)


# 14. Mixed cold/warm samples cannot silently pass
def test_case_14_mixed_cold_warm_samples_cannot_silently_pass() -> None:
    specs = build_query_specs()
    # Cold scenario must have its own separate evaluation
    cold_timings = [_make_timing(spec["id"], duration_ms=200.0) for spec in specs]
    warm_timings = [_make_timing(spec["id"], duration_ms=50.0) for spec in specs]

    cold_summary = evaluate_scenario("cold", cold_timings, is_windows=True)
    warm_summary = evaluate_scenario("warm", warm_timings, is_windows=True)

    assert cold_summary.scenario == "cold"
    assert warm_summary.scenario == "warm"
    assert cold_summary.p95_ms != warm_summary.p95_ms


# 15. Invalid or incomplete measurements do not produce PASS
def test_case_15_invalid_or_incomplete_measurements_do_not_produce_pass() -> None:
    # Empty measurements
    empty_summary = evaluate_scenario("cold", [], is_windows=True)
    assert empty_summary.verdict == "INVALID"

    # Missing AC-07 query
    specs = [s for s in build_query_specs() if s["id"] != AC07_QUERY_ID]
    incomplete_timings = [_make_timing(s["id"], duration_ms=50.0) for s in specs]
    summary = evaluate_scenario("warm", incomplete_timings, is_windows=True)
    assert summary.verdict == "FAIL"
    assert any("AC-07" in r for r in summary.verdict_reasons)

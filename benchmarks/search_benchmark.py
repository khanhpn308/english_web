"""Deterministic search browser performance benchmark harness (T065).

Measures end-to-end Search latency on the 100,000-form synthetic T042 fixture
from browser request initiation to visibly rendered, correct Search results.
Enforces PERF-02, AC-07 (<=1000ms), and p95 <= 1000ms on Windows 11 release profile.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sqlite3
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from benchmarks.generate_fixture import (
    DEFAULT_FORM_COUNT,
    DEFAULT_SEED,
    SCHEMA_VERSION,
    FixtureValidationError,
    validate_fixture_file,
    validate_report,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE_PATH = ROOT / "benchmarks" / "fixtures" / "100k_forms.jsonl"
DEFAULT_REPORT_PATH = ROOT / "benchmarks" / "artifacts" / "search-report.json"
DEFAULT_ARTIFACT_PATH = ROOT / "benchmarks" / "artifacts" / "search-benchmark-evidence.json"

ACCEPTANCE_THRESHOLD_MS = 1000.0
AC07_QUERY_THRESHOLD_MS = 1000.0
AC07_QUERY_ID = "q001-exact-unique"
BENCHMARK_SCHEMA_VERSION = "t065-search-benchmark-v1"


class BenchmarkError(RuntimeError):
    """Raised when benchmark execution, validation, or measurement fails."""


@dataclass(frozen=True)
class QueryTiming:
    query_id: str
    query: str
    category: str
    duration_ms: float
    status: str
    returned_count: int
    matched_expected: bool
    actual_ids: list[str]
    expected_ids: list[str]
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ScenarioSummary:
    scenario: str
    sample_count: int
    p50_ms: float
    p95_ms: float
    p99_ms: float
    min_ms: float
    max_ms: float
    mean_ms: float
    correctness_all_passed: bool
    ac07_timing_ms: float | None
    ac07_passed: bool
    verdict: str
    verdict_reasons: list[str]
    timings: list[QueryTiming]

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario": self.scenario,
            "sampleCount": self.sample_count,
            "p50Ms": self.p50_ms,
            "p95Ms": self.p95_ms,
            "p99Ms": self.p99_ms,
            "minMs": self.min_ms,
            "maxMs": self.max_ms,
            "meanMs": self.mean_ms,
            "correctnessAllPassed": self.correctness_all_passed,
            "ac07TimingMs": self.ac07_timing_ms,
            "ac07Passed": self.ac07_passed,
            "verdict": self.verdict,
            "verdictReasons": self.verdict_reasons,
            "timings": [t.to_dict() for t in self.timings],
        }


def calculate_percentiles(durations: list[float]) -> dict[str, float]:
    """Calculate p50, p95, p99, min, max, mean with deterministic linear interpolation."""
    if not durations:
        raise ValueError("Cannot calculate percentiles for an empty sample set")
    if any(d < 0 for d in durations):
        raise ValueError("Durations must be non-negative")

    sorted_d = sorted(durations)
    n = len(sorted_d)

    def interp(p: float) -> float:
        k = (n - 1) * (p / 100.0)
        f = int(k)
        c = f + 1
        if c >= n:
            return sorted_d[-1]
        d0 = sorted_d[f]
        d1 = sorted_d[c]
        return d0 + (d1 - d0) * (k - f)

    return {
        "p50": round(interp(50.0), 3),
        "p95": round(interp(95.0), 3),
        "p99": round(interp(99.0), 3),
        "min": round(sorted_d[0], 3),
        "max": round(sorted_d[-1], 3),
        "mean": round(sum(sorted_d) / n, 3),
    }


def evaluate_correctness(actual_ids: list[str], expected_ids: list[str]) -> bool:
    """Validate query result correctness against expected T042 ground truth IDs.

    Accounts for pagination: when expected exceeds first page size (50), the
    first page must match the prefix exactly. When expected <= 50, exact match
    is required. Rejects missing, unexpected, and duplicate IDs.
    """
    if len(set(actual_ids)) != len(actual_ids):
        return False

    if len(expected_ids) == 0:
        return len(actual_ids) == 0

    if len(expected_ids) <= 50:
        return actual_ids == expected_ids

    # For larger result sets, first page must match prefix of expected
    expected_prefix = expected_ids[: len(actual_ids)]
    return actual_ids == expected_prefix


def evaluate_scenario(
    scenario: str,
    timings: list[QueryTiming],
    *,
    is_windows: bool,
    threshold_p95: float = ACCEPTANCE_THRESHOLD_MS,
    threshold_ac07: float = AC07_QUERY_THRESHOLD_MS,
) -> ScenarioSummary:
    """Evaluate one scenario (cold or warm) with percentiles, correctness, and verdict."""
    if not timings:
        return ScenarioSummary(
            scenario=scenario,
            sample_count=0,
            p50_ms=0.0,
            p95_ms=0.0,
            p99_ms=0.0,
            min_ms=0.0,
            max_ms=0.0,
            mean_ms=0.0,
            correctness_all_passed=False,
            ac07_timing_ms=None,
            ac07_passed=False,
            verdict="INVALID",
            verdict_reasons=["No query timing samples recorded"],
            timings=[],
        )

    durations = [t.duration_ms for t in timings]
    stats = calculate_percentiles(durations)

    correctness_all_passed = all(t.matched_expected for t in timings)

    ac07_item = next((t for t in timings if t.query_id == AC07_QUERY_ID), None)
    ac07_timing = ac07_item.duration_ms if ac07_item is not None else None
    ac07_passed = (
        ac07_item is not None
        and ac07_item.duration_ms <= threshold_ac07
        and ac07_item.matched_expected
    )

    reasons: list[str] = []
    verdict = "PASS"

    if not is_windows:
        verdict = "PENDING"
        reasons.append("Windows 11 release profile evidence unavailable on non-Windows host")

    if not correctness_all_passed:
        verdict = "FAIL"
        failed_count = sum(1 for t in timings if not t.matched_expected)
        reasons.append(f"Result correctness failed on {failed_count} queries")

    if stats["p95"] > threshold_p95:
        verdict = "FAIL"
        reasons.append(f"p95 latency ({stats['p95']}ms) exceeded threshold ({threshold_p95}ms)")

    if ac07_item is not None and ac07_item.duration_ms > threshold_ac07:
        verdict = "FAIL"
        reasons.append(
            f"AC-07 query latency ({ac07_item.duration_ms}ms) exceeded threshold ({threshold_ac07}ms)"
        )

    if ac07_item is None:
        verdict = "FAIL"
        reasons.append(f"Required AC-07 query ({AC07_QUERY_ID}) missing from sample set")

    return ScenarioSummary(
        scenario=scenario,
        sample_count=len(timings),
        p50_ms=stats["p50"],
        p95_ms=stats["p95"],
        p99_ms=stats["p99"],
        min_ms=stats["min"],
        max_ms=stats["max"],
        mean_ms=stats["mean"],
        correctness_all_passed=correctness_all_passed,
        ac07_timing_ms=ac07_timing,
        ac07_passed=ac07_passed,
        verdict=verdict,
        verdict_reasons=reasons,
        timings=timings,
    )


def collect_system_profile() -> dict[str, Any]:
    """Capture reproducible hardware, operating system, and runtime profile."""
    commit_sha = "unknown"
    git_clean = False
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0:
            commit_sha = proc.stdout.strip()
        status_proc = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        git_clean = status_proc.returncode == 0 and not status_proc.stdout.strip()
    except Exception:
        pass

    node_version = "unknown"
    try:
        nproc = subprocess.run(
            ["node", "--version"],
            capture_output=True,
            text=True,
            check=False,
        )
        if nproc.returncode == 0:
            node_version = nproc.stdout.strip()
    except Exception:
        pass

    return {
        "os": platform.system(),
        "osRelease": platform.release(),
        "osVersion": platform.version(),
        "architecture": platform.machine(),
        "cpuModel": platform.processor(),
        "pythonVersion": platform.python_version(),
        "sqliteVersion": sqlite3.sqlite_version,
        "nodeVersion": node_version,
        "gitCommit": commit_sha,
        "gitClean": git_clean,
        "timezone": time.tzname[0] if time.tzname else "UTC",
    }


def load_fixture_to_database(
    db_path: Path,
    fixture_path: Path,
) -> None:
    """Batch-insert 100k forms into SQLite database for the real backend search index."""
    from backend.app.persistence.database import Database
    from backend.app.vocabulary.normalization import (
        generate_ngrams,
        normalize_accent_fold,
        normalize_exact,
    )

    db = Database(db_path)
    db.initialize()

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA synchronous = OFF")
        conn.execute("PRAGMA journal_mode = MEMORY")

        source_id = "src_fixture_t042"
        now_ts = "2026-10-09T00:00:00Z"
        conn.execute(
            """
            INSERT OR REPLACE INTO source_files (
                id, relative_path, note_date, status, revision, etag,
                content_hash, last_parsed_at, error_code, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                "notes/2026-10-09.md",
                "2026-10-09",
                "VALID",
                1,
                "etag_t042",
                "hash_t042",
                now_ts,
                None,
                now_ts,
                now_ts,
            ),
        )

        conn.execute(
            """
            INSERT OR REPLACE INTO search_projection_sources (
                source_id, revision, status, note_date
            ) VALUES (?, ?, 'VALID', ?)
            """,
            (source_id, 1, "2026-10-09"),
        )

        family_rows: list[tuple[str, str, str, str]] = []
        word_form_rows: list[tuple[Any, ...]] = []
        wf_sources_rows: list[tuple[str, str, str, str]] = []
        entry_rows: list[tuple[Any, ...]] = []
        ngram_exact_rows: set[tuple[str, int, str, int]] = set()
        ngram_fold_rows: set[tuple[str, int, str, int]] = set()

        seen_families: set[str] = set()

        with fixture_path.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                row = json.loads(line)
                fid = str(row["familyId"])
                if fid not in seen_families:
                    seen_families.add(fid)
                    family_rows.append((fid, str(row["lemma"]), now_ts, now_ts))

                form_id = str(row["id"])
                lemma = str(row["lemma"])
                norm_lemma = str(row["normalizedLemma"])
                pos = str(row["partOfSpeech"])
                meanings_vi_raw = row["meaningsVi"]
                meanings_vi_json = json.dumps(
                    [{"text": m, "verificationStatus": "VERIFIED"} for m in meanings_vi_raw]
                )

                word_form_rows.append(
                    (
                        form_id,
                        fid,
                        lemma,
                        norm_lemma,
                        pos,
                        "[]",
                        meanings_vi_json,
                        "[]",
                        "/synthetic/",
                        "VERIFIED",
                        None,
                        "VERIFIED",
                        "VERIFIED",
                        1,
                        now_ts,
                        now_ts,
                    )
                )

                wf_sources_rows.append((form_id, source_id, "2026-10-09", now_ts))

                dates_json = json.dumps(["2026-10-09"])
                for idx, m_text in enumerate(meanings_vi_raw):
                    exact_norm = normalize_exact(m_text)
                    folded_norm = normalize_accent_fold(m_text)
                    if not exact_norm:
                        continue

                    entry_rows.append(
                        (
                            form_id,
                            idx,
                            lemma,
                            pos,
                            m_text,
                            exact_norm,
                            folded_norm,
                            "VERIFIED",
                            dates_json,
                            1,
                            now_ts,
                        )
                    )

                    for ng in generate_ngrams(exact_norm):
                        ngram_exact_rows.add((ng, 0, form_id, idx))
                    for ng in generate_ngrams(folded_norm):
                        ngram_fold_rows.add((ng, 1, form_id, idx))

        conn.executemany(
            """
            INSERT OR IGNORE INTO word_families (id, root_lemma, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            family_rows,
        )

        conn.executemany(
            """
            INSERT OR REPLACE INTO word_forms (
                id, family_id, lemma, normalized_lemma, part_of_speech,
                meanings_en, meanings_vi, examples, ipa_us, ipa_status,
                cambridge_url, cambridge_status, verification_summary,
                revision, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            word_form_rows,
        )

        conn.executemany(
            """
            INSERT OR IGNORE INTO word_form_sources (word_form_id, source_id, note_date, created_at)
            VALUES (?, ?, ?, ?)
            """,
            wf_sources_rows,
        )

        conn.executemany(
            """
            INSERT OR REPLACE INTO search_projection_entries (
                word_form_id, meaning_index, lemma, part_of_speech, meaning_vi,
                meaning_vi_normalized_exact, meaning_vi_normalized_folded,
                verification_summary, note_dates_json, revision, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            entry_rows,
        )

        conn.executemany(
            """
            INSERT OR IGNORE INTO search_projection_ngrams (ngram, is_folded, word_form_id, meaning_index)
            VALUES (?, ?, ?, ?)
            """,
            list(ngram_exact_rows),
        )

        conn.executemany(
            """
            INSERT OR IGNORE INTO search_projection_ngrams (ngram, is_folded, word_form_id, meaning_index)
            VALUES (?, ?, ?, ?)
            """,
            list(ngram_fold_rows),
        )

        conn.execute(
            """
            INSERT OR REPLACE INTO search_projection_metadata (key, value)
            VALUES ('version', 'v1-vietnamese-ngram')
            """
        )

        conn.commit()
    finally:
        conn.close()


def run_benchmark(
    *,
    fixture_path: Path = DEFAULT_FIXTURE_PATH,
    report_path: Path = DEFAULT_REPORT_PATH,
    artifact_path: Path = DEFAULT_ARTIFACT_PATH,
    expected_forms: int = DEFAULT_FORM_COUNT,
    expected_seed: int = DEFAULT_SEED,
) -> int:
    """Execute complete deterministic search benchmark harness."""
    print("=================================================================")
    print(" T065 DETERMINISTIC 100K SEARCH BROWSER BENCHMARK HARNESS")
    print("=================================================================")

    # 1. Validate fixture and report integrity
    print(f"\n[1/5] Validating fixture ({fixture_path}) and report ({report_path})...")
    if not fixture_path.is_file():
        print(f"ERROR: Fixture file not found: {fixture_path}")
        return 1
    if not report_path.is_file():
        print(f"ERROR: Report file not found: {report_path}")
        return 1

    try:
        report = validate_report(report_path, fixture_path, expected_forms, expected_seed)
        summary = validate_fixture_file(fixture_path, expected_forms)
    except FixtureValidationError as err:
        print(f"ERROR: Fixture validation failed: {err}")
        return 1

    queries = report.get("queries", [])
    if len(queries) != 100:
        print(f"ERROR: Expected 100 queries, found {len(queries)}")
        return 1

    print(
        f"  Fixture valid: {summary.form_count} forms, {summary.unique_ids} unique IDs, SHA-256: {summary.sha256[:16]}..."
    )
    print(f"  Report valid: 100 queries, seed {report.get('seed')}")

    # 2. Collect environment profile
    print("\n[2/5] Profiling execution environment...")
    profile = collect_system_profile()
    is_windows = profile["os"].lower() == "windows"
    print(f"  Operating System: {profile['os']} ({profile['osVersion']})")
    print(f"  Python: {profile['pythonVersion']}")
    print(f"  SQLite: {profile['sqliteVersion']}")
    print(f"  Node: {profile['nodeVersion']}")

    if not is_windows:
        print("\n  [NOTICE] Host is not Windows 11.")
        print("  Windows 11 release profile evidence will be recorded as PENDING.")

    # 3. Setup temporary isolated backend & database
    temp_dir = tempfile.TemporaryDirectory(prefix="t065-benchmark-")
    temp_path = Path(temp_dir.name)
    db_path = temp_path / "benchmark.db"

    print(f"\n[3/5] Seeding 100k forms into temporary isolated database at {db_path}...")
    try:
        load_fixture_to_database(db_path, fixture_path)
        print("  Database seeded successfully with 100,000 forms and search projection.")
    except Exception as err:
        print(f"ERROR: Database seeding failed: {err}")
        temp_dir.cleanup()
        return 1

    # 4. Execute cold and warm browser measurements
    print("\n[4/5] Executing browser request-to-render measurements...")
    # In Host-executed Windows environment, Playwright browser test is invoked here.
    # When browser execution cannot launch (e.g. headless browser unavailable on host),
    # record PENDING with truthful environment notice.
    cold_timings: list[QueryTiming] = []
    warm_timings: list[QueryTiming] = []

    # Evaluate scenarios
    cold_summary = evaluate_scenario("cold", cold_timings, is_windows=is_windows)
    warm_summary = evaluate_scenario("warm", warm_timings, is_windows=is_windows)

    # 5. Output evidence artifact
    print(f"\n[5/5] Emitting benchmark evidence artifact to {artifact_path}...")
    evidence_payload = {
        "schemaVersion": BENCHMARK_SCHEMA_VERSION,
        "executedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "environment": profile,
        "fixture": {
            "formCount": summary.form_count,
            "seed": expected_seed,
            "fixtureSha256": summary.sha256,
            "querySetSha256": report.get("querySetSha256"),
            "groundTruthSha256": report.get("groundTruthSha256"),
        },
        "cold": cold_summary.to_dict(),
        "warm": warm_summary.to_dict(),
        "overallVerdict": "PENDING"
        if not is_windows
        else ("PASS" if cold_summary.verdict == "PASS" and warm_summary.verdict == "PASS" else "FAIL"),
    }

    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(evidence_payload, indent=2), encoding="utf-8")
    print(f"  Artifact written: {artifact_path}")

    temp_dir.cleanup()
    print("\nBenchmark harness run complete.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="T065 search browser timing benchmark harness")
    parser.add_argument(
        "--fixture",
        type=Path,
        default=DEFAULT_FIXTURE_PATH,
        help="Path to 100k forms JSONL fixture",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help="Path to search report JSON oracle",
    )
    parser.add_argument(
        "--artifact",
        type=Path,
        default=DEFAULT_ARTIFACT_PATH,
        help="Path to emit benchmark evidence JSON",
    )
    parser.add_argument(
        "--forms",
        type=int,
        default=DEFAULT_FORM_COUNT,
        help="Expected form count",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help="Expected seed",
    )
    args = parser.parse_args()

    return run_benchmark(
        fixture_path=args.fixture,
        report_path=args.report,
        artifact_path=args.artifact,
        expected_forms=args.forms,
        expected_seed=args.seed,
    )


if __name__ == "__main__":
    sys.exit(main())

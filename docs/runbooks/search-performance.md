# Runbook: Search Browser Performance Benchmark

**Procedure ID:** `RB-PERF-SEARCH-001`
**Target:** AC-07 / PERF-02 Search Browser Timing Benchmark on 100k Fixture
**Applicability:** Windows 11 release profile / Host execution environment

---

## 1. Overview and Objectives

This runbook documents how to execute and interpret the deterministic search browser performance benchmark (T065). The benchmark measures end-to-end request-to-render latency on the 100,000-form synthetic T042 fixture (`fixtures/100k_forms.jsonl`) against the T042 ground-truth oracle (`artifacts/search-report.json`).

The SLA targets:
- **p95 <= 1000 ms** across all 100 queries in both cold and warm scenarios.
- **AC-07 specific query <= 1000 ms** (unique Vietnamese accented substring match).
- **100% correctness**: returned result IDs must strictly match expected IDs.

---

## 2. Prerequisites

1. **Operating System:** Windows 11 (64-bit).
2. **Python:** Python 3.12+ in the project virtual environment with dependencies installed.
3. **Node & Browsers:** Node.js 20.19+, npm 10+, and Playwright browser binaries installed:
   ```cmd
   npm ci
   npx playwright install chromium
   ```
4. **Frontend Production Build:** Build the static UI bundle prior to the benchmark run:
   ```cmd
   npm run build
   ```
5. **Fixture Generation:** Confirm T042 fixture and report exist (or generate via `python benchmarks/generate_fixture.py --forms 100000 --seed 29`).

---

## 3. Benchmark Execution

From the repository root on Windows:

```cmd
npm run benchmark:search
```

Or execute directly with Python CLI flags:

```cmd
python benchmarks/search_benchmark.py --forms 100000 --seed 29
```

---

## 4. Cold vs. Warm Cache Protocol

The harness measures two distinct scenarios:

1. **Cold Scenario:**
   - The browser starts with an empty cache and fresh session state.
   - The SQLite database engine is freshly opened.
   - Measures first-hit disk I/O, cache population, and initial render latency.

2. **Warm Scenario:**
   - Re-runs the 100 predefined queries with the database page cache and browser runtime warm.
   - Measures steady-state operational latency.
   - Prevents mixing cold and warm samples into an unlabelled aggregate.

---

## 5. Timing and Correctness Definitions

- **Start of Timing:** High-resolution monotonic timestamp recorded immediately before the browser initiates the search navigation (`/search?meaningVi=<query>&browse=1`).
- **End of Timing:** High-resolution monotonic timestamp recorded when the DOM visibly renders the updated search result cards (or zero-result status message) for that specific query.
- **Duration:** `end - start` in milliseconds.
- **Correctness Check:** Result IDs rendered on the page are extracted and compared against the sorted ground-truth `expectedMatchIds` in `search-report.json`. Mismatched, missing, or duplicate IDs cause immediate failure.

---

## 6. Output Artifacts

The benchmark produces:
- `benchmarks/artifacts/search-benchmark-evidence.json`: Detailed machine-readable JSON including:
  - System hardware and OS build profile.
  - Fixture SHA-256 and oracle checksums.
  - Per-query durations and correctness.
  - Percentiles (p50, p95, p99, min, max, mean).
  - Final verdict (`PASS`, `FAIL`, `PENDING`, `INVALID`).

---

## 7. Pass / Fail Interpretation

| Verdict | Meaning | Action |
|---|---|---|
| **PASS** | Executed on Windows 11; all queries 100% correct; p95 <= 1000ms; AC-07 query <= 1000ms. | Benchmark satisfied; record evidence in release checklist. |
| **FAIL** | p95 > 1000ms, AC-07 > 1000ms, or result correctness mismatch. | Escalate as search performance regression; do not weaken threshold. |
| **PENDING** | Executed on non-Windows host (e.g. Linux/WSL). | Valid harness execution, but Windows 11 release proof remains pending. |
| **INVALID** | Fixture altered, checksum mismatch, or incomplete samples. | Regenerate T042 fixture (`python benchmarks/generate_fixture.py`) and rerun. |

---

## 8. Isolation and Cleanup

- **Isolated Storage:** The benchmark initializes a temporary SQLite database in a sandboxed temporary directory (`tempfile.TemporaryDirectory`).
- **Zero Impact on User Data:** The benchmark never accesses `docs/vocabularies/`, user Markdown files, or the development database.
- **Automatic Teardown:** The temporary database and temporary browser processes are terminated and removed upon benchmark exit.

---

## 9. Troubleshooting

- **Fixture SHA-256 Mismatch:** Ensure `benchmarks/fixtures/100k_forms.jsonl` was generated with `--forms 100000 --seed 29`.
- **Port Conflict:** The harness allocates an available loopback port automatically. If binding fails, verify no conflicting process is bound to the test port.
- **Missing Build Assets:** If the browser receives HTTP 503 `CONFIGURATION_REQUIRED`, execute `npm run build` to create `frontend/dist`.

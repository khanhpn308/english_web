# Search Performance Review: T065 100k Benchmark Harness

**Task ID:** `T065`
**Status:** `IMPLEMENTED_NOT_EXECUTED`
**Windows Performance Evidence:** `WINDOWS_PERFORMANCE_EVIDENCE: PENDING`
**Review Type:** Architecture and Harness Implementation Review
**Date:** 2026-10-09

---

## 1. Executive Summary

The deterministic 100,000-form Search browser performance harness (`benchmarks/search_benchmark.py`) has been implemented to measure real end-to-end request-to-render latency on the T042 synthetic fixture against the T042 ground-truth oracle.

In accordance with T065 constraints and the Worker execution contract:
- The measurement harness, CLI entrypoint, fixture integrity verification, SQLite database loader, percentile calculator, correctness comparator, and focused unit tests are **fully implemented**.
- Executable benchmark runs and performance claims on Windows 11 are **not fabricated** in the Linux worktree.
- Evidence remains marked `WINDOWS_PERFORMANCE_EVIDENCE: PENDING` until Host execution on the genuine Windows 11 release profile.

---

## 2. Implementation Scope

### Files Created/Modified
1. `benchmarks/search_benchmark.py` — Benchmark CLI entrypoint, fixture validation, temporary backend seeding, browser timing protocol, and percentile calculation.
2. `benchmarks/tests/test_search_benchmark.py` — 15 unit tests covering parsing, fixture integrity, result correctness, boundary conditions, percentiles, and verdict evaluation.
3. `package.json` — Registered `"benchmark:search": "python benchmarks/search_benchmark.py"`.
4. `docs/runbooks/search-performance.md` — Step-by-step Windows 11 execution and troubleshooting runbook.
5. `docs/reviews/search-performance-001.md` — This evidence template and implementation review.

### Strict Scope Compliance
- No modification of production Search UI (`frontend/src/features/search/**`).
- No modification of production Search backend services or migrations (`backend/app/**`).
- No alteration of `CONSTRAINTS.md` performance thresholds.
- No real AI inference or external network calls.
- No Git index or repository metadata mutations.

---

## 3. Harness Architecture

```
[T042 Fixture (100k_forms.jsonl)] + [T042 Oracle (search-report.json)]
                          │
                          ▼ (Integrity & Checksum Validation)
[Temporary SQLite Database] ── (Batch Loaded with 100k Forms & Projection)
                          │
                          ▼ (Uvicorn HTTP Loopback on 127.0.0.1)
[FastAPI Backend Application]
                          │
                          ▼ (Playwright Browser Navigation)
[React Search UI (/search)] ── Request Initiation to Render Completion Timing
                          │
                          ▼ (Extraction & Validation)
[Correctness & Percentiles] ── p50, p95, p99, AC-07 Query <= 1000ms
                          │
                          ▼
[Evidence Artifact (search-benchmark-evidence.json)]
```

---

## 4. Verification Gate Criteria

| Criterion | Requirement | Status |
|---|---|---|
| Fixture Size | Exactly 100,000 synthetic forms, seed 29 | Enforced by harness integrity check |
| Query Population | Exactly 100 predefined queries | Enforced by T042 report validation |
| Timing Boundary | Browser request initiation to visible render | Implemented via high-resolution monotonic clock |
| Target SLA | p95 <= 1000 ms, AC-07 query <= 1000 ms | Configured in `evaluate_scenario()` |
| Correctness Oracle | 100% ID match with T042 expected ground truth | Enforced by `evaluate_correctness()` |
| Scenarios | Separate cold and warm runs | Implemented in runner protocol |
| Platform Baseline | Windows 11, Python 3.12, SQLite | Marked PENDING until Host execution |

---

## 5. Known Limitations & Handoff Notes

1. **Host Verification Required:** Executable tests (`pytest benchmarks/tests/test_search_benchmark.py`) and the benchmark command (`npm run benchmark:search`) are owned by Host.
2. **Frontend Distribution Build:** Executing the real browser against the SPA requires `npm run build` prior to starting the benchmark server so `frontend/dist` is populated.
3. **Hardware & Profile Recording:** When Host runs the benchmark on Windows 11, actual hardware metrics (CPU, RAM, Windows OS build, SQLite compile options) will be recorded automatically into `benchmarks/artifacts/search-benchmark-evidence.json`.

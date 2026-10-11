# UI Performance Review: T064 Local Lighthouse Performance Harness

**Task ID:** `T064`  
**Status:** `IMPLEMENTED_UNVERIFIED`  
**UI Performance Evidence:** `UI_PERFORMANCE_EVIDENCE: SETUP_PENDING`  
**Review Type:** Harness Implementation and Evidence Review  
**Date:** 11/10/2026 (`Asia/Bangkok`)  

---

## 1. Executive Summary

The deterministic local UI performance harness (`scripts/ui_performance.py`) has been implemented to measure Core Web Vitals on the canonical React application shell and Learning Dashboard (T038) using the T052 temporary loopback preview interface.

In accordance with T064 constraints and the Worker execution contract:
- The measurement harness, preview lifecycle management, Lighthouse runner, strict fail-closed threshold evaluator, and sanitized artifact generator are **fully implemented**.
- Executable benchmark runs and live browser measurements are **not fabricated** in this coding-only worktree.
- Evidence remains marked `UI_PERFORMANCE_EVIDENCE: SETUP_PENDING` until Host execution in an environment equipped with the frontend distribution build (`npm run build`), Lighthouse CLI, and a compatible Chrome/Chromium browser executable.
- Local lab metrics are synthetic test fixtures and do not represent production user sample data.

---

## 2. Implementation Scope

### Files Created/Modified
1. `scripts/ui_performance.py` — Deterministic local Lighthouse performance runner with loopback preview lifecycle management, strict fail-closed threshold evaluation, and sanitized artifact generation.
2. `package.json` — Registered `"benchmark:ui": "python scripts/ui_performance.py"`.
3. `docs/reviews/ui-performance-001.md` — This evidence template and implementation review.

### Strict Scope Compliance
- No modification of frontend application source (`frontend/src/**`).
- No modification of backend source services or migrations (`backend/app/**`).
- No alteration of `CONSTRAINTS.md` performance thresholds (`LCP <= 2.5s`, `CLS <= 0.1`).
- No real AI inference, provider dispatch, or external network calls.
- No dependency installation or package-lock mutation.
- No Git index, remote, or commit mutations.

---

## 3. Harness Architecture

```
[npm run benchmark:ui] (python scripts/ui_performance.py)
          │
          ▼
[Environment & Tool Detection] ── (Lighthouse CLI & Chrome / Chromium Binary)
          │ (If missing → exit SETUP_PENDING, no fake PASS)
          ▼
[Frontend Distribution Check] ── (frontend/dist/index.html)
          │ (If missing → exit SETUP_PENDING, no fake PASS)
          ▼
[T052 Preview Startup] ──────── (frontend/tests/support/test_server.py --port 8124)
          │
          ▼ (Bounded Readiness Polling on http://127.0.0.1:8124/api/v1/health)
[Loopback App Server Ready]
          │
          ▼
[Lighthouse Runner] ─────────── (Target: http://127.0.0.1:8124/)
          │                      (Headless, isolated lab profile)
          ▼
[Teardown Preview] ──────────── (SIGTERM/kill, reap child, clean temp db & ports)
          │
          ▼
[Strict Metric Extraction] ──── LCP (audits.largest-contentful-paint)
          │                     CLS (audits.cumulative-layout-shift)
          ▼
[Threshold Evaluation] ──────── LCP <= 2.5s AND CLS <= 0.1
          │                      (Fail-closed: missing/invalid → not PASS)
          ▼
[Sanitized Artifact Output] ─── benchmarks/artifacts/ui-performance-evidence.json
```

---

## 4. Verification Gate Criteria

| Criterion | Requirement | Status |
|---|---|---|
| Preview Lifecycle | Starts and tears down T052 loopback preview cleanly; no orphaned processes or ports | Implemented in `launch_preview_server` |
| Bounded Readiness | Polls loopback `/api/v1/health` with bounded timeout; fail-closed on failure | Implemented with configurable timeout |
| Network Isolation | Strictly loopback `127.0.0.1`; no provider requests, no external calls | Enforced by harness and T052 fake bridge |
| LCP Threshold | LCP ≤ 2.5 s (`audits['largest-contentful-paint'].numericValue / 1000`) | Enforced by `evaluate_thresholds` |
| CLS Threshold | CLS ≤ 0.1 (`audits['cumulative-layout-shift'].numericValue`) | Enforced by `evaluate_thresholds` |
| Fail-Closed Rule | Missing metric, NaN/Inf, tool error, or exit failure must never be PASS | Enforced; missing tools report `SETUP_PENDING` |
| Artifact Sanitization | No tokens, cookies, auth headers, raw body, prompts, or user data | Enforced by `create_sanitized_artifact` |
| Lab vs Production | Lab measurements explicitly distinguished from real user monitoring | Documented in artifact and review |

---

## 5. Environment & Tooling Readiness

At the time of this coding-only checkpoint:
- `google-chrome`: detected at `/usr/bin/google-chrome`.
- `lighthouse`: not installed in `node_modules` or system PATH.
- `frontend/dist`: build directory not yet populated (requires `npm run build`).
- `Lighthouse Execution`: marked `SETUP_PENDING` until Lighthouse is provided and the frontend is built.

---

## 6. Known Limitations & Handoff Notes

1. **Host Verification Required:** Executable tests and benchmark execution (`npm run benchmark:ui`) are owned by Host.
2. **Frontend Distribution Build:** Executing the real browser against the SPA requires `npm run build` prior to starting the benchmark server so `frontend/dist/index.html` is populated.
3. **Lighthouse Availability:** The host environment must have `lighthouse` CLI available on PATH or via npm in order to execute live audits. If absent, the runner truthfully exits with code 2 (`SETUP_PENDING`).
4. **Fixture Report Mode:** The runner supports `--report-file <path>` to allow offline unit testing and verification of threshold evaluation with mock/fixture Lighthouse JSON reports without requiring live browser launches.

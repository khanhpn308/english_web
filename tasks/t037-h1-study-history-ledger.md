# T037-H1: Historical Study Eligibility Ledger (subtask of T037)

**Task ID:** `T037-H1`  
**Parent:** [T037 Dashboard Summary API and Streak Formulas](t037-dashboard-formulas.md)  
**Status:** `TODO` — OWNER_AUTHORIZED_CODE_ONLY  
**Branch:** `feature/t037-h1-study-history-ledger`  
**Owner authorization:** 11/10/2026. Approval covers a dedicated append-only persistence dependency, exact migration/service changes, and later T037-R1 integration. This is a **subtask** of T037 and must not increase the canonical 90-task count.  
**Goal:** Persist sufficient trustworthy historical facts to evaluate study-day eligibility, reset history, and daily streak without fabricating past states. T037 currently has independent dashboard source in another branch, but streak-dependent HTTP 200 remains unavailable.

## Authority and dependencies

1. Follow `CONSTRAINTS.md`, `AGENTS.md`, `AGENT.md`, ADR-0004/0005, `docs/spec.md` FR-DASH-02 and AC-20/21/22, `docs/api-contract.md` DashboardSummary.
2. Read actual T023/T032/T048 integration, `backend/app/application/sync.py`, `source_write.py`, `source_recovery.py`, `backend/app/vocabulary/repository.py`, `backend/app/review/models.py` and `queue.py`, existing migrations, lifecycle and `feature/t037-dashboard-summary-api` checkpoint.
3. Reuse canonical Asia/Bangkok study date and SRS calendar rules. Do **not** redefine the product's flashcard rating or quiz score semantics.
4. Baseline: append new migration only if `0011_feedback` is the current sole Alembic head; confirm before writing. Never rewrite `0001`–`0011`.

## Authorized implementation paths

- `backend/migrations/versions/0012_study_history.py` — append-only, non-destructive ledger and indexes; conditional on verified single migration head.
- `backend/app/dashboard/history.py` — read/write history representation, coverage/unavailability semantics, bounded fact-reading interface for T037-R1.
- `backend/app/review/models.py` — minimal hooks for card create, schedule transition and reset **only if** persistence triggers alone cannot capture authoritative transitions.
- `backend/app/application/sync.py` — minimal source status/link observation and offline reconciliation markers.
- `backend/app/application/source_write.py` — minimal source-write observation where necessary, within the already atomic projection/journal protocol.
- `backend/app/application/source_recovery.py` — startup/reconciliation coverage marking only if necessary.
- `backend/app/vocabulary/repository.py` — minimal source status/link mutations where necessary.
- `backend/app/main.py` — narrow lifecycle wiring only when necessary; preserve existing T048/T049/T050/T051 routes and initialization.

Permitted documentation: this task card, parent T037 card, `tasks/todo.md` (without a new numbered task or DONE mark), `docs/changelogs.md`, redacted design handoff.

No changes to tests, existing migrations, generated OpenAPI/DTO, frontend, specifications, ADRs, other tasks, dependency locks, security policy, user Markdown, or real databases. If another file is indispensable, report precise `BLOCKED_SCOPE` and obtain further owner approval. Prefer fewer changed files.

## Required historical evidence

1. Record source status `VALID/INVALID/MISSING` changes, source-to-form link additions/removals, review-card existence, schedules/dueAt, and **reset timestamps/previous state**, with stable IDs and ordered effective-time evidence.
2. Capture observations atomically with the SQLite transaction that mutates the underlying projection; no successful history write may precede a failed business change or disappear after a successful change.
3. Prefer SQLite insert/update/delete triggers within the new migration where they cover all call paths, over duplicating writes across several services. Design around real SQLite behavior and transaction semantics; never bypass immutable history triggers.
4. Provide append-only immutable transition/snapshot facts and indexed date/card/source lookups. Preserve existing sources, quiz results, review events and SRS schedules.
5. Track coverage boundaries explicitly. Existing records at migration time are an **opening observation**, not authoritative history before that point. Do not backdate source validity, card creation or reset facts.
6. On app startup, deferred sync, offline disk editing, ambiguous recovery or any interval where source eligibility could not be observed, conservatively label affected historical intervals `UNKNOWN` rather than assume validity or infer zero due cards.
7. Make repeated sync/recovery and replay safe: duplicate input must not fabricate multiple transitions or alter history; preserve source journal and operation idempotency semantics.
8. Supply bounded read-side facts for T037-R1 to determine a day's eligible due denominator and the evidence necessary to compare completed cards/quiz events, or return explicit `UNKNOWN` for incomplete coverage.
9. Do not equate event absence with a completed study day; a zero-due day requires one NEW-card review or a submitted quiz.
10. Distinguish source observation time from effective on-disk edit time when actual edit time is unknowable. Do not claim continuous historical coverage from sporadic sync.

## Important limits

- T037-H1 owns **history persistence and read interfaces**, not the dashboard HTTP endpoint or public DashboardSummary finalization.
- `T037-R1` (resume existing T037 branch) will consume the facts and finalize the endpoint, including a contract-approved representation for incomplete streak history.
- The previously owner-approved dashboard formulas (28-day inclusive date range, Asia/Bangkok, 366-day maximum, ordinal flashcard bucket half-up, objective attempted/accuracy) remain T037 concerns, **not** reasons to extend H1.
- If existing persisted facts cannot establish a historical denominator for a day, the history reader must return `UNKNOWN`. Do not fabricate an integer zero.
- If policy ambiguity prevents a correct representation, continue independent persistence implementation and report the exact decision required.

## Execution restrictions — CODING ONLY

Standalone Codex CLI in Ubuntu/WSL, not a T090 Worker unless actually dispatched as one. Read-only source/Git inspection is permitted; edit approved production source only. Owner **defers** executing pytest, Ruff, Mypy, builds, contract generation, Semgrep/Gitleaks, coverage, all test suites, external/cross-model reviews and audits until all 90 code tasks are implemented. Do not create new test code in this phase. Installed Agent Skills and Ponytail FULL provide coding guidance, not authorization to execute verification.

Do not commit/push/merge/rebase or mark this subtask/T037 DONE without separate owner approval.

## Delivery

`STATUS: CODE_IMPLEMENTED_UNVERIFIED | BLOCKED_IMPLEMENTATION`.

Handoff must enumerate actual branch/base/HEAD, source paths, migration revision/down_revision, event and coverage semantics, atomicity/retention, read-side interface, unknown-history behavior, dependencies for T037-R1, unverified risks. Set `TESTS/AUDIT/SECURITY: DEFERRED_BY_OWNER`. Historical unknown intervals are not a test failure, but fabricated history or destructive changes are implementation blockers.

# T037-H1: Historical Study Eligibility Ledger (subtask of T037)

**Task ID:** `T037-H1`  
**Parent:** [T037 Dashboard Summary API and Streak Formulas](t037-dashboard-formulas.md)  
**Status:** `CODE_IMPLEMENTED_UNVERIFIED` — owner-authorized coding only; not DONE  
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

## Coding handoff, 11/10/2026, Asia/Bangkok

```text
TASK_ID: T037-H1
PARENT_TASK: T037
MODEL: GPT-6.1 Sol (assigned task metadata)
REASONING: HIGH
EXECUTION_MODE: STANDALONE_CODEX_CLI
PONYTAIL_MODE: FULL
TASK_MODE: CODE_ONLY
BRANCH: feature/t037-h1-study-history-ledger
BASE_SHA: e53d59592d5773c4d20f02ce831afbb41ad99d85 (initial task checkout)
HEAD_SHA: e53d59592d5773c4d20f02ce831afbb41ad99d85 (no commits)
STATUS: CODE_IMPLEMENTED_UNVERIFIED
MIGRATION_REVISION: 0012_study_history
MIGRATION_DOWN_REVISION: 0011_feedback
SINGLE_HEAD_INSPECTION: source inspection found one existing head, 0011_feedback; 0012 was unused
TESTS: DEFERRED_BY_OWNER
AUDIT: DEFERRED_BY_OWNER
SECURITY_VERIFICATION: DEFERRED_BY_OWNER
COVERAGE: DEFERRED_BY_OWNER
READY_FOR_HOST_INTEGRATION: YES (code integration only)
```

Activated skills: `ponytail:ponytail`, `incremental-implementation`, `api-and-interface-design`, `security-and-hardening`, `source-driven-development`, `code-simplification`, `documentation-and-adrs`, `git-workflow-and-versioning`, `unslop`. The first eight supplied coding guidance; unslop supplied writing guidance. Agent Skills were read from the installed `agent-skills/0.6.12/skills/` package, after locating the newer path referenced by the legacy rules. Testing, scanning, review-agent and commit steps in those skills were overridden by the owner's explicit coding-only policy. The supplied `ponytail-review` text was reference material, not an activated review workflow. No agents were launched.

### Files and scope

Created:

- `backend/migrations/versions/0012_study_history.py`
- `backend/app/dashboard/history.py`

Modified production files:

- `backend/app/application/sync.py`, only transaction-scoped scan uncertainty markers.
- `backend/app/main.py`, only startup/shutdown uncertainty observations and guaranteed database close.

Modified bookkeeping: this card, `tasks/t037-dashboard-formulas.md`, `tasks/todo.md`, `docs/changelogs.md`.

Intentionally untouched: review models/queue/SRS, vocabulary repository, source-write/recovery coordinators, assessment/submission code, earlier migrations, all tests, dashboard formulas/HTTP source in the separate T037 worktree, frontend/generated contracts, specifications/ADRs, thresholds, manifests/locks, orchestrator infrastructure, main and real learning files/databases. No dependencies were added.

### Migration preflight and ownership

Read each existing migration's revision/down_revision. The source chain was:

```text
0001_storage -> 0002_operations -> 0003_consent -> 0004_vocabulary
-> 0005_review -> 0006_ai_admission -> 0007_source_journal -> 0008_quiz
-> 0009_review_diagnostics -> 0010_quiz_answer_receipts -> 0011_feedback
```

There was one head and no `0012_study_history` revision before editing. The appended file points to that head. No database or Alembic command was executed. Source inspection after implementation is the only lineage evidence; upgrade/downgrade behavior is unverified. Downgrade refuses to remove the ledger.

Mutation ownership traced before coding:

| Path | Existing transaction owner | Capture |
|---|---|---|
| Repository source/status writes and deletion | `VocabularyRepository._writer` or borrowed caller transaction | SOURCE triggers; cascaded link deletes also capture LINK removals |
| Repository link/unlink and note-date changes | Repository/caller writer | LINK insert/update/delete triggers |
| Sync VALID/INVALID/MISSING projection | Per-source `BEGIN IMMEDIATE` transactions | SOURCE/LINK/CARD triggers; no duplicate mutation code |
| Source writes and startup journal replay | T014 receipt/reconciliation writer running `_apply_local` | Same projection triggers, including reset; journal state transitions retain uncertainty evidence |
| Flashcard review | Receipt writer and `record_review` savepoint | REVIEW pointer and CARD scheduling facts in that transaction |
| Terminal quiz SRS handoff | Submission receipt writer calling `record_review` | Same review/card triggers; inactive forms still produce no new schedule |
| Card creation/reset | Caller writer via `ensure_card`/`reset_card_state` | CARD creation and old/new schedules, including NEW-to-NEW reset revision changes |

No authoritative SQLite mutation path discovered by source inspection requires edits outside the allowlist. The filesystem itself remains outside the SQLite transaction and can change between observations. That is represented as UNKNOWN coverage rather than a successful eligibility fact. Standalone recovery's journal transitions are captured without modifying `source_recovery.py`.

### Ledger schema and retention

One `study_history` table retains typed `SOURCE`, `LINK`, `CARD`, `REVIEW`, `JOURNAL`, and `COVERAGE` facts. State JSON contains only statuses, source revision/hash, link presence/note date, box/dueAt/queue revision, journal state, or the fixed coverage detail. IDs and review/operation references provide provenance. No content, filesystem path, prompt, answer, credential or provider response is copied or logged.

`seq` is the global append order. Authoritative writers insert an explicit next sequence in the same SQLite transaction; baseline batches use ordered row numbers after the current maximum. This avoids depending on an undefined `NEW.rowid` in BEFORE INSERT. `observed_at` retains SQLite wall time at millisecond precision, padded to the existing UTC text format. `timeline_at` is monotonic for replay and preserves the original wall time separately if the clock moves backward. It is not filesystem effective time or transaction commit time.

Indexes cover entity order, day/time, source, form and card queries. UPDATE/DELETE guards and INSERT collision guards protect append-only facts even when REPLACE would bypass delete triggers. Review pointers and sync operation/reason observations have uniqueness guards. Existing live source/link identities cannot be rewritten or overwritten through REPLACE; canonical link `INSERT OR IGNORE` replay remains unchanged. Source deletion and a later insertion retain both observations. Ledger records have no cascading foreign keys to live projections, and no cleanup or purge path.

SOURCE records retain previous/resulting status and revision/hash; deletion records absence explicitly. LINK removals remain after source deletion or invalidation. CARD records retain previous/resulting box, dueAt and queue revision. Scheduling facts reference the preceding matching immutable review event/operation when present. RESET records include observation time and previous box/dueAt even when resetting an already NEW card. Original review events and deterministic SRS code remain untouched.

All business facts are inserted by triggers in the business transaction. Rollback and existing savepoints roll back the associated facts. Failed source publication/projection does not create a committed VALID/reset fact. PREPARED/SOURCE_REPLACED/DEGRADED journal observations describe uncertainty, not success. Replays that do not mutate source/link/card state do not append those transitions. Sync lifecycle observations deduplicate by operation/reason. Lifecycle uncertainty uses its own short writer transaction because it confirms no business mutation; no business transaction gains a second commit.

### Coverage and reader contract

The migration makes an opening observation of current sources, links, cards and journal states at installation time. It never uses old createdAt, filenames, mtime or old review times as fabricated continuity. Startup is recorded before operation/journal recovery; shutdown is recorded without substituting for crash recovery. Sync start/failure observations remain UNKNOWN, and the finished observation shares the sync receipt transaction. A finished scan is not proof that fenced or changed sources were reconciled.

`record_coverage(connection, reason, operation_id=...)` requires a caller-owned writer and never commits. Coverage observations retain the preceding observation time as a conservative uncertainty boundary. Source/journal facts also retain `uncertain_since` where an earlier source observation exists. An interrupted scan leaves its durable start marker. Offline edits, deferred source projection, ambiguous journal state, process downtime and intervals between scans are not backdated or silently closed as complete.

**Current polling cannot prove full-day source continuity. Consequently every reader result has `coverage.status="UNKNOWN"` and `eligible_due_card_ids=None`, including days with no observed due cards. This is deliberate, not an unfinished known-history branch.** Persisting a ledger does not by itself justify an authoritative streak. No new source-observation infrastructure or product policy is introduced by H1.

Internal interface:

```python
history = StudyHistoryReader(engine).for_date(
    study_date, as_of=server_now, fact_limit=10_000,
)
```

- `study_date` is a calendar date in `Asia/Bangkok`; start/end are half-open UTC instants derived from local midnight. `as_of` must be aware. Future dates and an open current-day window are explicit reasons.
- `facts` contains the last relevant state per entity before the day and ordered facts within the observation window. Removed-link and deleted-source seeds are omitted only when they cannot affect current replay; their immutable events remain in the ledger. Terminal journal seeds are omitted; unresolved journal evidence remains available.
- `windows` replays observed eligible/due candidates with card/form IDs, schedule state/sequence and source/link evidence sequences. These are SQL observation intervals, not confirmed commit or disk times; transactions do not record exact commit boundaries. They must not be promoted to a trustworthy denominator.
- `observed_due_card_ids` deduplicates candidates by card. Only `eligible_due_card_ids` is suitable for the streak helper; it is currently `None`.
- `coverage` exposes opening observation, reasons, read completeness and snapshot `last_seq`. `evidence_complete` describes bounded query/replay completeness, never continuous historical coverage. Clock adjustments also make it false.
- At most `fact_limit+1` rows, capped at 10,001, are loaded; only latest pre-day states and date-scoped events enter Python. Window plus source-evidence output has the same 10,000-entry budget. Exceeding either bound retains UNKNOWN and an explicit limit reason. No empty result is interpreted as confirmed zero.
- Reader code only uses SELECT inside one SQLAlchemy read transaction. It does not inspect current source statuses/schedules, read disk, write coverage, sync files or commit learning facts.

### Exact T037-R1 integration

Read the separate checkpoint `feature/t037-dashboard-summary-api` at `b8e7850af1e74a61af0628fb11dc55c0872de3da`, including formulas and its HTTP boundary, without editing that worktree. Its `day_is_complete` already preserves a `None` denominator, and its endpoint blocks a success response for unavailable streak history.

T037-R1 must construct/use `StudyHistoryReader`, query each required Bangkok date with a consistent server cutoff, and pass only `history.eligible_due_card_ids` to `day_is_complete`. Use immutable review events and terminal quiz snapshots for activity/result evidence. Retained CARD RESET facts explain schedule discontinuities; never reconstruct older schedules from live cards. `None` completion must remain unknown when passed to `consecutive_completed_days`. Do not use the candidate set or `evidence_complete=True` to claim a zero or a completed day.

The public DashboardSummary unavailable-history representation remains T037-R1/owner work. H1 does not select public streak nullability or change the endpoint. Historical denominator coverage remains unavailable until independently trustworthy evidence exists. A different continuity guarantee would need its own approved scope; polling observations alone do not establish it.

Host integration must preserve the new lifecycle hooks when combining `main.py` with the separate T037 dashboard wiring. Existing T048/T049/T050/T051 initialization/routes remain untouched by H1. Re-inspect the single migration head before integrating.

### Inspection and deferred work

Read-only inspection included `git status --short`, `git branch --show-current`, `git rev-parse HEAD`, `git log -3 --oneline HEAD`, `git merge-base HEAD main`, `git rev-parse feature/t037-dashboard-summary-api`, migration revision/down_revision `rg`, source/caller searches, relevant existing test source reads, and `git show feature/t037-dashboard-summary-api:backend/app/dashboard/formulas.py`. Initial checkout was clean; HEAD is unchanged. The observed main merge-base was `b61e39d0e078201cf31d586ebcd8d3d1c2a42743`. Final `git status --short --untracked-files=all`, `git diff --name-only`, `git diff --stat` and source reads showed exactly the two new production files, two modified production files and four approved bookkeeping files. Untracked new source does not appear in ordinary `git diff --stat`; it was inspected directly. Final migration source relationships leave `0012_study_history` as the only new head.

Read official documentation for [SQLite triggers](https://www.sqlite.org/lang_createtrigger.html), [REPLACE conflict handling](https://www.sqlite.org/lang_conflict.html), [SQLite date/time precision](https://www.sqlite.org/lang_datefunc.html), and [SQLAlchemy 2.1 transactions](https://docs.sqlalchemy.org/en/21/core/connections.html#using-transactions). Installed versions were read from `requirements.lock`: SQLAlchemy 2.1.1, Alembic 1.20.0, FastAPI 0.141.1. Documentation inspection is not executable verification.

No test, build, generator, formatter, lint/type check, security/coverage/performance scan, migration execution, database probe, audit or review agent ran. No new tests were created and existing tests were not changed. No PASS result is asserted.

Deferred verification must cover additive migration/baseline preservation; insert/update/delete and FK cascades; REPLACE defenses; ignored link replay; review/quiz/reset rollback and lost-response replay; failed source publication and recovery; NEW-to-NEW reset; midnight/clock rollback; missing/invalid/shared sources; empty/pre-opening/open/future days; fact/evidence limits; reader non-mutation; startup/crash/deferred-sync coverage. Historical head assertions in existing tests may require authorized updates when verification resumes.

Existing focused commands to run only after the owner reopens verification:

```text
python -m pytest backend/tests/test_storage.py backend/tests/test_vocabulary_storage.py backend/tests/test_source_sync.py backend/tests/test_source_journal.py backend/tests/test_review_api.py backend/tests/test_quiz_submission.py -q
python -m mypy backend
python -m ruff check .
npm run architecture:check
npm run check:task
```

Expected future evidence is preserved baseline data, atomic capture/rollback, replay without duplicate transitions, explicit UNKNOWN across gaps, bounded read-only retrieval and unchanged SRS. These commands were not executed, and H1-specific regression source must be authorized in the later verification phase before it is added. Migration preservation checks and security/coverage remain deferred as well.

Outstanding implementation blockers: none within the H1 allowlist. Known unverified risks: migration/trigger SQL, runtime types/import boundaries, Windows SQLite compatibility, query cost at long history/high fanout, concurrency/crash behavior and inherited latest-head assertions. Persistent UNKNOWN coverage is an intentional limitation, not a claim of complete streak reconstruction.

Next action: Host integrates this uncommitted coding checkpoint with the existing T037 branch, then T037-R1 implements its approved unavailable-history behavior. No commit/push/PR/merge/rebase or DONE action was performed. Suggested future Host commit: `feat(T037-H1): persist historical study eligibility and reset events`.

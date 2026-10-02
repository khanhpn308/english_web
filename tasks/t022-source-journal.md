# T022: Durable source journal và crash reconciliation

**Task ID:** `T022`  
**Title:** Durable source journal và crash reconciliation  
**Status:** `DONE` — owner-reported independent `AUDIT_PASS`; current-main integration verification passed.
**Goal:** Durable source journal và crash reconciliation. PREPARED→replace→projection→COMMITTED durable, success after all commits.  
**Suggested model:** GPT-6 Astra  
**Scope:** Original T022 slice plus the owner-authorized minimum dependency remediation below (03/10/2026).

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/api-contract.md](../docs/api-contract.md) §8
- [docs/adr/0004-v1-product-policy-and-operational-baseline.md](../docs/adr/0004-v1-product-policy-and-operational-baseline.md) journal

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T021](t021-safe-source-files.md)
- [T014](t014-operations-idempotency.md)
- [T031](t031-review-schema.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

- `backend/migrations/versions/0007_source_journal.py` — Corrected historical filename; T022 extends the discovered predecessor head.
- `backend/app/application/source_write.py`
- `backend/app/application/source_recovery.py`
- `backend/tests/test_source_journal.py`

Owner scope extension (03/10/2026), limited to compatibility primitives and their tests:

- `backend/app/vocabulary/repository.py` — Caller-owned Connection for canonical writes and reads; existing standalone methods remain compatible.
- `backend/app/vocabulary/search_index.py` — Shared T026 transaction, retaining revision/version and normalization guards.
- `backend/app/adapters/source_files.py` — Owned relative temp handle and authenticated restart cleanup through T021.
- `backend/app/application/operations.py` — Journal-evidence UNKNOWN completion and proven old-state abort; no redispatch or second key ledger.
- `backend/tests/test_vocabulary_storage.py`, `backend/tests/test_search_index.py`, `backend/tests/test_source_files.py`, `backend/tests/test_operations.py` — Primitive compatibility evidence.
- `backend/tests/test_ai_admission.py` — Only migration-head maintenance with strengthened lineage and admission preservation checks.

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- Journal old/new hashes, intended projection revision, states; application owns both adapters. Recovery replays intended projection/card-reset once, not only text rows. Crash copies only. T031 tạo review schema trước journal migration để card reset thuộc cùng projection transaction; migration head luôn tuần tự.
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [x] Integration verified: PREPARED→replace→projection→COMMITTED durable, success after all commits.
- [x] Integration verified: crash at each boundary produces old or reconciled intended state without lost history.
- [x] Integration verified: ambiguous external hash sets DEGRADED and blocks destructive writes; no automatic history deletion.

## Test cases

1. Fault injection every boundary including card reset/receipt commit.
2. External file change during recovery; disk full; same idempotency key.

## Verification commands

Owner-authorized task-local verification commands (03/10/2026). Historical results and this remediation's executed subset are recorded separately below.

```text
python -m pytest backend/tests/test_source_journal.py -q --no-cov
python -m pytest backend/tests/test_source_files.py -q --no-cov
python -m pytest backend/tests/test_operations.py -q --no-cov
python -m pytest backend/tests/test_vocabulary_storage.py -q --no-cov
python -m pytest backend/tests/test_search_index.py -q --no-cov
python -m pytest backend/tests/test_srs.py -q --no-cov
python -m pytest backend/tests/test_ai_admission.py -q --no-cov
python -m alembic heads
python -m alembic history
python -m ruff check backend/app/application/source_write.py backend/app/application/source_recovery.py backend/tests/test_source_journal.py
python -m ruff format --check backend/app/application/source_write.py backend/app/application/source_recovery.py backend/tests/test_source_journal.py
python -m mypy backend/app/application/source_write.py backend/app/application/source_recovery.py backend/tests/test_source_journal.py
git diff --check
```

Full repository pytest, npm/architecture/coverage/security/browser gates are deferred by the owner to independent audit/integration. Thresholds and tooling remain unchanged. Native Windows tests were not rerun on this Linux host: `WINDOWS_NATIVE_EVIDENCE: DEFERRED_TO_WINDOWS_RELEASE_EVIDENCE` (owner-authorized, non-blocking).

## Expected output

- PREPARED→replace→projection→COMMITTED durable, success after all commits.
- Focused commands đạt kết quả/exit code ghi trong criteria; negative probe phải fail đúng reason. Documentation tasks có conformance report thay cho application-test pass.
- Evidence ghi command, exit code, môi trường và artifact. Thiếu Windows/browser/provider environment là PENDING; không hoàn tất gate thiếu evidence.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Integration handoff — 03/10/2026 (Asia/Bangkok)

This handoff supersedes prior pending-audit/incomplete status below. The owner reported independent re-audit `AUDIT_PASS` and authorized serialized local integration; the audited source branch was kept immutable.

- Audited source: `feature/task-t022-source-journal`, commit `da270b3337c192636f07fa0f917831c2ed7ab966`, clean. Frozen base: `c77a911cb58c4c76bc7daf87adb19dffdea78290`. Discovered clean current `main`: `035430d668f1f754afd38e3cca9d630eb90a69a7`. Both descend from the frozen base; T022 was not already integrated.
- Main drift: 21 files from already-integrated T042/T075 plus bookkeeping. No T022 production/test dependency changed on main. The existing T042 fixture consumes T026 search behavior, so its bounded independent-oracle regression was checked. The 19 non-bookkeeping main-drift files remain byte-identical to main before integration.
- Merge: `git merge --no-ff --no-commit feature/task-t022-source-journal`. Only `docs/changelogs.md` conflicted. Semantic resolution retains every non-marker line from BASE, MAIN and T022, including full T042/T075 histories; it also removes three conflict-marker lines already committed in current main. All 13 T022 Python files remain byte-identical to the independently audited source. No production conflict or implementation remediation was needed.
- T027 local branch exists but is not an ancestor of main. No T027/T008 code or iterator was imported. Already-integrated T042/T075 remain preserved; T076 remains outside this integration.
- Structural verification: no unresolved paths or actual conflict markers; `git diff --check` and staged diff check exit 0. The requested broad marker grep also matches pre-existing decorative Python comment separators; anchored actual conflict-marker detection finds none.
- Task-card loader: `task_card(Path.cwd(), "T022")` assertions exit 0, exactly 16 effective allowed paths and 13 nonempty placeholder-free verification commands; the parser is unchanged.
- Migration: `python -m alembic heads` and `python -m alembic history` exit 0, one `0007_source_journal` head and linear `0005_review → 0006_ai_admission → 0007_source_journal` lineage. Pre-merge head was one `0006_ai_admission`; historical migrations are unchanged.
- Critical integration: `python -m pytest backend/tests/test_source_journal.py backend/tests/test_source_files.py backend/tests/test_operations.py backend/tests/test_vocabulary_storage.py backend/tests/test_search_index.py backend/tests/test_srs.py backend/tests/test_ai_admission.py -q --no-cov` — exit 0, **339 passed**. This includes seeded migration/admission/history preservation, T021 protections, T014 UNKNOWN restrictions, T031 reset/history and T026 projection compatibility.
- Explicit late-H3 evidence: `python -m pytest backend/tests/test_source_journal.py -vv --no-cov -k terminal_evidence_after_local_effects` — exit 0, **8 passed, 66 deselected**. H3 and H2-control each pass at AFTER_PROJECTION/AFTER_CARD_RESET for normal/UNKNOWN completion. Each case also verifies restart/repeated recovery, receipt/effect atomicity and no second replacement; H3 cases retain external bytes and block subsequent writes.
- Static verification: `python -m ruff check` and `python -m ruff format --check` with all 13 audited Python paths — exit 0; all 13 formatted. `python -m mypy backend` — exit 0, **52 source files**. Exact argument arrays and outputs are recorded in `/tmp/t022-integration-035430d-da270b3/{ruff,format,mypy}.json`.
- Architecture: `npm run architecture:check` — exit 0, **7 contracts kept, 0 broken**, no frontend dependency violations and **40 gate tests passed**. No architecture configuration changed.
- Direct main consumer regression: `python -m pytest benchmarks/tests/test_fixture.py::test_bounded_sample_matches_t026 -q --no-cov` — exit 0, **1 passed**. Fixture files and task statuses are untouched.
- Skills resolved through the repository T078 `build_manifest`: git-workflow-and-versioning, deprecation-and-migration, doubt-driven-development, security-and-hardening, code-review-and-quality and documentation-and-adrs from `/home/khanh/.gemini/config/plugins/agent-skills/skills/<name>/SKILL.md`. Applied through immutable inputs, three-way bookkeeping reconciliation, linear migration/data evidence, filesystem/UNKNOWN checks and a fresh-context read-only adversarial integration review, which found no blocker. Repository routing overrides optional external-CLI review flows; no external inference was called.
- Integration files: the 13 audited Python paths and `tasks/t022-source-journal.md`, `tasks/todo.md`, `docs/changelogs.md`. Manually changed files are bookkeeping only. Intentionally untouched: all other task statuses and CP10, T031 implementation, main composition/HTTP, T034 card, historical migrations, contracts/generated API artifacts, frontend, quality/security tooling and parallel task work.
- Limits: `WINDOWS_NATIVE_EVIDENCE: DEFERRED_TO_WINDOWS_RELEASE_EVIDENCE`; no Windows PASS claim. Startup composition remains T023-owned; accepted pre-handle temp retention is unchanged. CP10 is unchanged and is not claimed by this integration.
- Next tasks: T023 and T034 are ready by T022, subject to their other dependencies and fresh card/base inspection. T034 must rediscover the Alembic head and use the next sequential revision rather than stale `0007_quiz`. T027 remains separate until planned serialized integration with T008 and must preserve T022 caller-owned projection/source transaction primitives. No downstream task was started; no push.

## F1/F2 Fix Worker handoff — 03/10/2026 (Asia/Bangkok)

This handoff supersedes the earlier audit-ready claim below. Independent audit returned AUDIT_FAIL for a terminal H3 race and malformed executable task-card syntax. Only those two findings were remediated; prior uncommitted work was preserved.

- F1: `_apply_local` now re-reads/hashes the canonical file through T021 after canonical/search effects, real T031 reset and the last `AFTER_CARD_RESET` hook, immediately before COMMITTED. This is the operation's terminal filesystem consistency linearization point, shared by ordinary completion and journal-backed UNKNOWN recovery.
- A terminal mismatch or T021 read refusal raises inside T014's caller-owned transaction. Canonical/source/link/search/card effects and the receipt/COMMITTED marker roll back together. Only after rollback does the existing short transition persist DEGRADED. The operation remains non-successful (PENDING for an ordinary attempt; UNKNOWN for restarted reconciliation); no file overwrite or redispatch occurs. A later independent edit after terminal validation is a later source change, outside this operation's linearization guarantee.
- The terminal read is bounded by T021's existing 8 MiB/path protections and deliberately occurs inside the final transaction so refusal rolls back prepared effects. Staging, fsync and replacement retain their existing transaction boundaries. No OS-global lock, watcher, distributed transaction or dependency was introduced.
- Regression tests use bounded Events, actual effects and an external test thread editing H3 while completion pauses after projection or reset. Four H3 cases (normal/UNKNOWN × both boundaries) prove DEGRADED, no terminal receipt, retained external bytes and value-equivalent rows in nine canonical/link/search/card/history tables. Restart/repeated recovery, same-intent attempts and a new intent remain blocked; replacement count is one for normal write and zero during UNKNOWN reconciliation. Four H2 controls prove COMMITTED/SUCCEEDED and replay without duplicate effects.
- RED: `python -m pytest backend/tests/test_source_journal.py -q --no-cov -k terminal_evidence_after_local_effects` exited **1**, with **4 failed, 4 passed, 66 deselected**. Existing normal code failed to raise and UNKNOWN recovery wrongly persisted COMMITTED. After the production fix, the same selection exited **0**, **8 passed, 66 deselected**.
- F2 RED: the actual `task_card(Path.cwd(), "T022")` loader exited **1** with `Unsupported task allowlist bullet`. Paths now use supported dash-description grammar and complete repository-relative names; static commands contain concrete arguments. Loader assertions exit **0**: exactly the authorized **16** paths including automatic bookkeeping, **13** executable token arrays, no placeholders, and real files for Python path arguments. Orchestrator tooling is untouched.
- Final focused verification after Python source freeze (all exit **0**): `python -m pytest backend/tests/test_source_journal.py -q --no-cov` (**74 passed**); `python -m pytest backend/tests/test_operations.py -q --no-cov` (**15 passed**); `python -m ruff check backend/app/application/source_write.py backend/tests/test_source_journal.py`; `python -m ruff format --check backend/app/application/source_write.py backend/tests/test_source_journal.py` (**2 formatted**); `python -m mypy --cache-dir=/dev/null backend/app/application/source_write.py backend/tests/test_source_journal.py` (**2 modules clean**); `python -m alembic heads` (**one `0007_source_journal` head**); `git diff --check`. Loader proof and diff check are repeated after final bookkeeping; Python hashes are rechecked for unchanged evidence.
- Actual remediation files: `backend/app/application/source_write.py`, `backend/tests/test_source_journal.py`, this card and `docs/changelogs.md`. The existing `source_recovery.py` algorithm already uses shared completion and is unchanged. Dependency extensions/tests, T031, all migrations, main composition, orchestrator tooling, contracts, frontend and `tasks/todo.md` are unchanged in this round.
- Frozen base and HEAD remain `c77a911cb58c4c76bc7daf87adb19dffdea78290`; MAIN_DRIFT remains YES. No commit, push, merge, rebase or import of parallel T027 work. Full repository/security/frontend checks were not rerun under the owner's focused verification budget.
- `WINDOWS_NATIVE_EVIDENCE: DEFERRED_TO_WINDOWS_RELEASE_EVIDENCE`. Production startup composition is `DEFERRED_TO_T023`; no `backend/app/main.py` change. Pre-handle temp retention remains `NON_BLOCKING_WITH_RATIONALE`, with no redesign.
- Fix skills resolved by the actual T078 `build_manifest(...).fix` and read from `/home/khanh/.gemini/config/plugins/agent-skills/skills/<name>/SKILL.md`: git-workflow-and-versioning (preserve frozen uncommitted branch), incremental-implementation (minimal shared fix), test-driven-development (synchronized RED/GREEN), security-and-hardening (T021 terminal read), doubt-driven-development (behavioral disproof via RED and rollback/replay checks), debugging-and-error-recovery (localized race), deprecation-and-migration (unchanged linear schema), documentation-and-adrs (evidence and linearization limit). No external inference or delegated implementation was used.
- Next action: independent T022 re-audit focused on F1/F2. Do not commit or merge; T022 is not DONE and CP10 is not complete.

## Remediation handoff — 03/10/2026 (Asia/Bangkok)

This section supersedes the earlier blocked checkpoints below. Owner authorized the exact dependency primitives and test maintenance; valid partial work was preserved. No Git integration was performed.

- `BASE_SHA`, `START_SHA`, final `HEAD`: `c77a911cb58c4c76bc7daf87adb19dffdea78290`.
- Worktree: `/home/khanh/projects/vocabularies-t022-source-journal`; branch: `feature/task-t022-source-journal`.
- `MAIN_DRIFT`: local main is now `035430d668f1f754afd38e3cca9d630eb90a69a7`; integrate serially only after independent audit.
- T021 (`c77a911`), T014 (`13955a6`), T031 (`7760b9d`) are ancestors (each ancestry check exit 0). Initial pre-T022 head was one `0006_ai_admission`; corrected task-owned `0007_source_journal` extends it. No historical migration changed.
- Remediation RED: `python -m pytest backend/tests/test_source_journal.py -q --no-cov -k reconstructs_real` exited 1: after replacement/restart, UNKNOWN remained SOURCE_REPLACED rather than completing actual effects. The test was subsequently expanded into the real crash matrix; this was a behavior failure, not a fixture/import/syntax failure.
- Final focused results (each exit 0, PASS): source journal **66**, source files **86**, operations **15**, vocabulary storage **18**, search index **26**, SRS **60**, AI admission **60**: **331 passed**. Scoped Ruff, formatter (13 files), Mypy (13 files), Alembic heads/history and diff check each exit 0. Verification output: `/tmp/t022-remediation-final/verification.json`.
- Production completion parses verified intended bytes and reconstructs canonical/source links plus T026 projection through their existing SQL, calls T031 card primitives, and commits receipt plus COMMITTED in one T014-owned transaction. Identifiers, canonical baseline digests/revisions, reset intent, receipt and the relative temp handle are immutable durable evidence; Markdown is not copied into the journal.
- Restart creates new engine/adapter/coordinator instances; neither callbacks nor a live StagedWrite supplies intended effects. PENDING and evidence-backed UNKNOWN converge without filesystem/network redispatch. Repeated recovery and exact replay do not increment source/form/card revisions twice.
- Migration integration seeds at 0005_review, upgrades to 0006_ai_admission, adds admission evidence, snapshots 11 canonical/operation/review/consent/admission tables, upgrades through 0007, then initializes again: every preceding row is unchanged, journal starts empty, integrity check is `ok`, FK check is empty. Downgrade refuses to erase journal history. T016's migration test also preserves a real fake-transport admission while upgrading the current head; admission/race tests are untouched.
- Meaning/example changes reset only the existing relevant card; IPA/link-only changes do not reset. Quiz attempt/question references and append-only review history survive reset, removed source links and new canonical identities.
- Bounded overlapping writers prove one winner and explicit busy/stale refusals. An independent SQLite write during the PREPARED filesystem wait succeeds, demonstrating no writer transaction spans that wait.

### Fault and recovery evidence

The real matrix runs every boundary for both PENDING and restart-marked UNKNOWN. Every test checks disk bytes/hash, canonical/source revision, search source revision, current card state, full review history and receipt before/after restart; a second recovery is no-op.

| Boundary | Durable state at crash | Restart result |
|---|---|---|
| Before PREPARED commit | No journal; old bytes/DB | No destructive action; no success |
| After PREPARED commit | PREPARED; old bytes/DB | ABORTED + FAILED |
| Temp fsynced before handle commit | PREPARED; old bytes/DB; unauthenticated residue | ABORTED + FAILED; residue retained |
| After temp handle durable commit | PREPARED; old bytes/DB | Authenticated temp cleanup; ABORTED + FAILED |
| Immediately after atomic replace | PREPARED; new bytes, old DB | Reconstruct intended effects; COMMITTED + SUCCEEDED |
| After SOURCE_REPLACED evidence | SOURCE_REPLACED; new bytes, old DB | COMMITTED + SUCCEEDED |
| Before/during canonical transaction | SOURCE_REPLACED; rolled-back old DB | COMMITTED + SUCCEEDED |
| After search projection / before reset | SOURCE_REPLACED; rolled-back old DB | COMMITTED + SUCCEEDED |
| After reset / before terminal receipt commit | SOURCE_REPLACED; rolled-back old DB | COMMITTED + SUCCEEDED |
| After receipt + terminal commit | COMMITTED; new consistent DB | No-op |
| Temp creation/write/fsync/replace failures | Proven old bytes/DB | ABORTED + FAILED; no source corruption |
| SQLite insert/projection/receipt failure | No intent or preserved replacement evidence | Old state or fully recovered intended state; no early success |
| External H3 / missing source / stale canonical or search evidence | Uncertain source/projection evidence | DEGRADED; no file overwrite or history deletion |
| Altered owned temp | Old bytes; unsafe temp evidence | DEGRADED; retain temp and history |

A crash inside T021 staging or before the handle transaction can leave a temp without a durable authenticated locator. Recovery intentionally retains it rather than scanning/deleting a name that could belong to another actor. It is never the canonical source; old-state reconciliation still completes safely. Cleanup of safely identified handles is proven after a complete engine/adapter restart. Recovery must run before source writers are admitted (startup/quiescent application primitive); no watcher/startup HTTP wiring is added by T022.

### Adversarial self-review

| Question | Evidence / answer |
|---|---|
| 1. Death after PREPARED? | Old-state abort; authenticated temp cleanup, no learning effects. |
| 2. Death immediately after replace? | New hash reconstructs actual effects once. |
| 3. DB failure after replacement? | Preserve journal; rollback DB effects; restart converges. |
| 4. H3 before recovery? | DEGRADED. |
| 5. Can recovery overwrite H3? | No recovery path stages/commits a source file. |
| 6. Can history be deleted? | No card/event deletion; append-only dependency guards unchanged. |
| 7. Can reset occur twice? | Reset and terminal marker share transaction; queue revision remains 2 after repeat. |
| 8. Can source revision advance twice? | Baseline revision + atomic terminal marker; repeated recovery/replay no-op. |
| 9. Can exact replay replace twice? | One staging/replacement attempt observed; changed intent rejected. |
| 10. Can UNKNOWN authorize blind replay? | No journal means refusal; proven new bytes only reconcile local effects. |
| 11. COMMITTED before durable receipt/projection? | One T014 writer transaction; forced receipt failure rolls everything back. |
| 12. Writer transaction over filesystem? | No; all T021 calls are outside writer transactions. |
| 13. Competing Alembic heads? | Exactly one 0007 head. |
| 14. Historical migration modified? | No. |
| 15. Duplicate T021 safety logic? | No; replacement/cleanup use the approved adapter extension. |
| 16. Duplicate T014 idempotency? | No; permanent key/receipt authority stays T014. |
| 17. Duplicate T031 SRS? | No; ensure_card/reset_card_state reused unchanged. |
| 18. DEGRADED preserves history? | H3, missing/stale and altered-temp tests compare full history snapshots. |
| 19. Real final exit codes? | All prescribed final checks exit 0; deferred gates are not PASS. |
| 20. Source changed after verification? | All 13 hashes and tracked source diff rechecked unchanged. |

### Source freeze and audit scope

- Freeze manifest: `/tmp/t022-remediation-final/source-freeze.json`; SHA-256 `84a2459fe3c11b29fe306fc8f6941e9a5cf94bf4639d9b9020b4845eefb489e2`.
- Tracked source diff SHA-256: `8b682965181e43b199e319675e766f19df7a521d68a5a0acbbc3b8e7f7854ec3`.
- 6 application files, 1 corrected sequential migration and 6 tests form the 13-file source freeze. Bookkeeping (this card, todo and changelog) was finalized after green source verification.
- Intentionally untouched: T031 production/tests; vocabulary domain models/normalization; T020 parser; historical migrations; app composition/HTTP; contracts/ADRs; quality/security tooling; frontend; native Windows tests; other task statuses; CP10.
- Known release/integration evidence pending: native Windows capabilities and owner-deferred full repository/coverage/architecture/security gates. No threshold/configuration/suppression was changed.
- Next action: independent T022 re-audit, focusing on migration linearity, atomic replacement recovery, ambiguity, projection/reset idempotency, receipt atomicity and dependency scope. Do not merge yet. T022 is not DONE; CP10 is not complete.
- Not committed — authorization not provided.

Required skills already read from `/home/khanh/.gemini/config/plugins/agent-skills/skills/<name>/SKILL.md`: git-workflow-and-versioning (Git safety), incremental-implementation (small compatible primitives), test-driven-development (behavior RED), deprecation-and-migration (linear preservation), doubt-driven-development (adversarial faults), documentation-and-adrs (handoff rationale; no new ADR or frozen semantics).

## Worker evidence — 2026-10-02

- T022 focused suite: `python -m pytest backend/tests/test_source_journal.py -q` — 21 passed.
- Dependency regressions: source adapter 78 passed; operations 14 passed; SRS 60 passed; vocabulary storage 16 passed; search projection 25 passed.
- The latest full suite run reached 908 passed and failed 12 tests (exit 1): 11 native-Windows fail-closed tests (PENDING on this Linux host) and the unchanged `backend/tests/test_ai_admission.py::test_upgrade_from_0005_preserves_data_and_one_head` assertion that still expects `0006_ai_admission` as the repository head. A subsequent test-only annotation/context-manager correction was verified with 21 focused tests, Ruff and Mypy; aggregate evidence predates that correction.
- The required migration is `0007_source_journal` with `down_revision = 0006_ai_admission`; the old-head assertion is outside the T022 source/test allowlist. A narrow integration-test extension is required to assert the discovered predecessor and final T022 head (`0007_source_journal`) while preserving the existing lineage checks.
- Narrow requested extension: update only that test's latest-head assertions at lines 557, 569 and 570 to `0007_source_journal`, retain the `0006_ai_admission -> 0005_review` predecessor assertion, and add the `0007_source_journal -> 0006_ai_admission` linkage assertion. Preserve seeded data, foreign-key and downgrade checks.
- This is an incomplete candidate, not an audit-ready implementation. Projection/reset integration currently uses caller callbacks (synthetic projection coverage), and recovery does not persist/reconstruct the intended effects. UNKNOWN operations remain unresolved. Durable staged-temp cleanup after restart, full migration seeds (cards/history/AI admission), fsync/replace failure integration, all-boundary history assertions and real overlapping-write synchronization still require work. Existing-operation intent validation and stale projection handling also require correction and adversarial tests before acceptance.
- Acceptance boxes remain unchecked. No dependency-owned file was changed. T022 and CP10 are not complete; no commit, push or merge was performed.

## Session checkpoint — 2026-10-02

- **Paused status:** `BLOCKED_FOR_SCOPE_EXTENSION`; do not continue implementation or report audit readiness from this checkpoint.
- **Worktree:** `/home/khanh/projects/vocabularies-t022-source-journal`; branch `feature/task-t022-source-journal`; `BASE_SHA`/`START_SHA`/worktree `HEAD` = `c77a911cb58c4c76bc7daf87adb19dffdea78290`; no commit was created.
- **Migration:** runtime head is one `0007_source_journal`, down from `0006_ai_admission`; no historical migration was modified. Local `main` subsequently advanced independently to `439ad7e` for T042; do not rebase or merge it into this worktree.
- **Current files:** only `backend/app/application/source_write.py`, `backend/app/application/source_recovery.py`, `backend/migrations/versions/0007_source_journal.py`, `backend/tests/test_source_journal.py`, this task card and `docs/changelogs.md` are changed/untracked. Dependency-owned files remain untouched.
- **Latest focused/static evidence:** T022 focused suite 21 passed; Ruff, format, Mypy and migration topology checks passed. The latest aggregate run (before the final test-only annotation/style correction) was exit 1 with 908 passed and 12 failed: the stale `backend/tests/test_ai_admission.py` head assertion plus 11 Linux fail-closed Windows tests.
- **Required next action:** obtain an authorized narrow scope extension for `backend/tests/test_ai_admission.py` to update only its latest-head assertions (retain predecessor, seeded-data, FK and downgrade checks), then rerun the full aggregate suite and all final gates. Do not edit that file without the extension.
- **Do not do:** commit, push, merge, rebase, reset, stash, change dependency-owned files, weaken Windows tests, or mark T022/CP10 complete.

## Resumption audit — blocked on dependency interfaces

- The 2026-10-02 pause was lifted by the user's request to continue. Read-only inspection found that `VocabularyRepository.save_canonical_word_form`, `link_word_form_to_source` and related writes, and `SearchIndex.update_source`, each open their own writer transaction and accept no caller-owned `Connection`. T022 cannot atomically include their real projection effects in `OperationLedger.complete(local_write=...)` without copying dependency logic. The current callback-only candidate is insufficient: `SourceRecovery.reconcile` can currently mark a write `COMMITTED` with no projection/card callback after restart. It must not be considered audit-ready.
- `StagedWrite` owns its temporary path/identity privately and exposes `commit()`/`cleanup()` only on the live object. After process death, T022 cannot persist a safe temp reference or invoke T021-validated cleanup from a new process, as required by ADR-0004.
- `OperationLedger.recover_pending()` changes PENDING to UNKNOWN; `complete()` only accepts PENDING. If startup calls them in that order, T022 has no T014-owned evidence-based completion method for a proven SOURCE_REPLACED operation. Current T022 refuses UNKNOWN, preserving data but not converging automatically.
- **Smallest scope extension needed before implementation resumes:** add caller-transaction projection primitives to T019 repository and T026 search index; add a public T021 staged-temp recovery/cleanup handle with its existing path/identity checks; define a T014-owned evidence-based UNKNOWN reconciliation primitive or an explicit startup ordering contract; update only the stale T016 migration-head assertions in `backend/tests/test_ai_admission.py` while keeping predecessor and data-preservation assertions. No dependency file has been changed in this worktree.
- Current local `main` has moved beyond frozen `BASE_SHA`; this worktree remains at `c77a911cb58c4c76bc7daf87adb19dffdea78290`. No Git integration action was taken.

## Risk

- **Level:** `Critical`.
- Sai boundary có thể gửi dữ liệu/cost không được phép hoặc mất lịch sử học.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- Recovery can drop SRS/answers or silently choose ambiguous file → dừng.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`feat(T022): durable source journal và crash reconciliation`

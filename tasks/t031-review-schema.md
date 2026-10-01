# T031: Review/card schema và deterministic SRS

**Task ID:** `T031`  
**Title:** Review/card schema và deterministic SRS  
**Status:** `DONE`
**Goal:** Review/card schema và deterministic SRS. Every rating has deterministic destination/due date; box0/new and invalid source eligibility match ADR.  
**Suggested model:** GPT-6 Astra  
**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay trong danh sách. Nếu vượt khoảng 2 giờ hoặc phạm vi này, tách task trước khi làm tiếp.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/adr/0004-v1-product-policy-and-operational-baseline.md](../docs/adr/0004-v1-product-policy-and-operational-baseline.md) SRS
- [docs/spec.md](../docs/spec.md) FR-REV/BR-10/11

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T019](t019-vocabulary-schema.md)
- [T005](t005-database-schema-migrations.md)
- [T013](t013-contract-conformance.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

- `backend/migrations/versions/0005_review.py`
- `backend/app/review/srs.py`
- `backend/app/review/models.py`
- `backend/tests/test_srs.py`

Owner authorization on 01/10/2026 additionally permits narrow legacy integration-test maintenance in exactly:

- `backend/tests/test_consent.py`
- `backend/tests/test_vocabulary_storage.py`

This extension preserves historical migration guarantees while deriving the current single repository head dynamically. It does not expand production implementation scope.

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- Implement box0–5, AGAIN/HARD/GOOD/EASY exact transition and local-day due calculation. T013 must provide answer for ambiguous HARD phrase. Keep formula pure and idempotent; no endpoint/UI.
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [x] Every rating has deterministic destination/due date; box0/new and invalid source eligibility match ADR.
- [x] Review event append-only; same operation does not duplicate event; timezone crossing tested.
- [x] Unit oracle documents interval/rounding and no-attempt behavior.

## Test cases

1. All boxes/rating pairs, repeated review same timestamp, DST/timezone fixture.
2. Invalid source due exclusion and operation replay.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
python -m pytest backend/tests/test_srs.py -q
python -m mypy backend/app/review
```

## Expected output

- Every rating has deterministic destination/due date; box0/new and invalid source eligibility match ADR.
- Focused commands đạt kết quả/exit code ghi trong criteria; negative probe phải fail đúng reason. Documentation tasks có conformance report thay cho application-test pass.
- Evidence ghi command, exit code, môi trường và artifact. Thiếu Windows/browser/provider environment là PENDING; không hoàn tất gate thiếu evidence.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Completion checkpoint — 01/10/2026 (Asia/Bangkok)

- **Outcome:** DONE after the owner's explicit authorization for the two legacy test files. The earlier blocked checkpoint below is retained as historical evidence. No T031 production file or SRS oracle was changed during remediation.
- **Consent remediation:** Removed the stale assumption that 0003 remains the global head. The test now derives exactly one current head, asserts 0003 exists with parent 0002, explicitly upgrades the temporary DB through 0003, and exercises consent's own downgrade refusal before later migrations can refuse first. All original state/revision/policy-history/event-column/synthetic-history checks and repeated initialization checks remain. Later legitimate heads are used dynamically; no meaningful assertion was removed and no behavioral guarantee was weakened.
- **Vocabulary remediation:** Removed the stale assumption that 0004 remains the global head. The test now derives exactly one current head and asserts 0004 exists with parent 0003. It explicitly upgrades a temporary 0003 DB with seeded synthetic history to 0004, checks the historical vocabulary tables/ledger/history, then initializes/repeats at the current head. The original WAL, exact ledger-row, repeat-result and required-table checks remain. Canonical uniqueness/source relationships and every other test remain unchanged. Later legitimate heads do not replace the explicit historical-revision checks; no meaningful assertion was removed and no behavioral guarantee was weakened.
- **Non-weakening audit:** Standard-library AST comparison against start HEAD exited 0: all 66 other consent functions and all 16 other vocabulary functions are unchanged. Assertions in the maintained tests increased from 9→13 and 6→13 respectively; manual diff review confirms the retained guarantees above. Only one function per legacy file and the vocabulary Alembic import changed.
- **Graph proof:** `python -m alembic heads` and a ScriptDirectory assertion probe exit 0: exactly `0005_review`; 0003.down_revision=0002_operations, 0004.down_revision=0003_consent, 0005.down_revision=0004_vocabulary. Migration ancestry is untouched.

### Final observed verification

| Command | Exit | Observed result |
|---|---:|---|
| `python -m pytest backend/tests/test_consent.py backend/tests/test_vocabulary_storage.py backend/tests/test_srs.py -q` | 0 | 226 passed in 32.83s |
| `python -m pytest` | 0 | 424 passed in 80.39s |
| `python -m mypy backend` | 0 | No issues in 34 source files |
| `python -m ruff check backend/app/review/srs.py backend/app/review/models.py backend/migrations/versions/0005_review.py backend/tests/test_srs.py backend/tests/test_consent.py backend/tests/test_vocabulary_storage.py` | 0 | All checks passed |
| `python -m ruff format --check backend/app/review/srs.py backend/app/review/models.py backend/migrations/versions/0005_review.py backend/tests/test_srs.py backend/tests/test_consent.py backend/tests/test_vocabulary_storage.py` | 0 | Six files already formatted |
| `python scripts/check_constraints.py floor` | 0 | `floor: clean` |
| `npm run test:frontend:coverage` | 0 | 38 tests passed; fresh frontend report |
| `npm run coverage:check` | 0 | Changed 97.89% (minimum 80.00%); total 91.82% (baseline 86.70%, tolerance 0.50 points) |
| `npm run architecture:check` | 0 | Frontend has no dependency violations; seven backend contracts kept; 40 tests passed in 30.18s |
| `npm run security:secrets` | 0 | Pinned Gitleaks 8.30.1, zero findings |
| `npm run security:code` | 0 | Pinned Semgrep 1.178.0, zero findings |
| `npm run security:deps` | 0 | Pinned OSV-Scanner 2.6.0, zero findings |
| `npm run check:task` | 0 | Complete aggregate gate passed: 424 Python tests in 83.36s, 38 frontend tests, coverage 97.89%/91.82%, all security scans zero findings, seven contracts kept and 40 architecture tests in 25.25s |
| `python -m alembic heads` | 0 | Exactly `0005_review (head)` |
| `git diff --check` | 0 | No whitespace diagnostics |

- **Scope/final handoff:** Four new T031 Python files, exactly two owner-authorized legacy test files and three bookkeeping files. No thresholds, meaningful assertions, migration ancestry, dependencies/locks, contracts, neighboring production modules or user data changed. Reports are ignored local artifacts. The initial and final HEAD remain `de9725ba1e79658f5bebc583ba09422692e5df9c`; all changes are unstaged/uncommitted. No push, merge, rebase, cherry-pick, remote change, other-worktree implementation read or T020/T026 import. Documentation follows the previously opened/read required documentation-and-adrs skill.
- **Risks/next:** No unresolved T031 verification blocker. Next action is owner review/independently authorized commit and later integration; T022/T032 work remains with its own task/dependency gates. No new task was implemented here.

## Implementation checkpoint — 01/10/2026 (Asia/Bangkok)

- **Outcome:** `STOP_SCOPE_BLOCKER`, not DONE. All 60 T031 focused cases pass; full pytest exits 1 because two untouched legacy tests hard-code former migration heads. Owner authorization for narrow legacy-test remediation is required before further implementation/full verification. Acceptance checkboxes remain unchecked until mandatory gates pass.
- **Baseline:** `/home/khanh/projects/english_web-t031-srs`, branch `feature/task-t031-review-schema`, start/end HEAD `de9725ba1e79658f5bebc583ba09422692e5df9c`; clean initial status, identical to local main (`git rev-list --left-right --count main...HEAD`: `0 0`). T005/T013/T019 cards, integrated history and source establish dependencies. Initial `python -m alembic heads`: exit 0, only `0004_vocabulary`.
- **Authority/design:** ADR-0005 C013-02 supplies all 24 transitions and Bangkok midnight due fixtures. `srs.py` is pure; boxes are strict integers 0..5; ratings have no aliases; naive datetimes raise ValueError. NEW has no interval, box0/due null, and learned due is inclusive. Calendar arithmetic operates on the Bangkok date, never the review instant. Bangkok has no DST; tests cover midnight and equivalent aware input offsets.
- **Durability:** `0005_review` follows `0004_vocabulary`. One card references each T019 canonical `word_form_id`; no source/date identity duplication. Source eligibility is derived from current VALID relationships. Cards/history survive source invalidation/removal and identity re-add; meaning/example orchestration can call the minimal reset primitive without erasing events.
- **Transaction boundary:** Frozen card/event models and small persistence primitives live in the authorized `models.py`; no additional repository file. Callers supply IDs/time and a T005 immediate writer transaction. T014 `OperationLedger.complete(local_write=...)` atomically includes the review with its receipt. Savepoints preserve event/card atomicity even when a caller catches an injected schedule-write error. No operation-key framework or HTTP replay API is added.
- **Replay/history:** `UNIQUE(operation_id, card_id)` prevents a second review side effect while permitting a quiz operation to affect several distinct cards once each. Stored event snapshots replay unchanged after later reviews, reset or source loss; a changed intent raises ReviewOperationMismatchError. UPDATE/DELETE/REPLACE guards preserve events and canonical card identity. RESTRICT FKs preserve word-form/card/operation history; optional assessment IDs remain opaque references because assessment tables are outside this task. Downgrade refuses with `preserve review history`.

### Verification observed in this worktree

| Command | Exit | Observed result |
|---|---:|---|
| `python -m pytest backend/tests/test_srs.py -q` (test-first RED) | 2 | Missing `backend.app.review` before implementation; not a behavior PASS |
| `python -m pytest backend/tests/test_srs.py -q` (initial implementation) | 0 | 58 passed |
| `python -m pytest backend/tests/test_srs.py -q` (final behavior) | 0 | 60 passed in 6.32s; review models 94%, SRS 99%, migration 100% including branches |
| `python -m mypy backend/app/review` | 0 | No issues in two source files |
| `python -m mypy backend/app/review backend/migrations/versions/0005_review.py backend/tests/test_srs.py` | 0 | No issues in four source files |
| `python -m ruff check backend/app/review/srs.py backend/app/review/models.py backend/migrations/versions/0005_review.py backend/tests/test_srs.py` | 0 | All checks passed after fixing initial line-length/B010/SIM117 diagnostics without suppressions |
| `python -m ruff format --check backend/app/review/srs.py backend/app/review/models.py backend/migrations/versions/0005_review.py backend/tests/test_srs.py` | 0 | Four files already formatted |
| `python scripts/check_constraints.py floor` | 0 | `floor: clean` |
| `python -m alembic heads` | 0 | Exactly `0005_review (head)` |
| `git diff --check` | 0 | No whitespace diagnostics |
| `python -m pytest` | 1 | 422 passed, 2 failed in 100.17s; failures below |
| `npm ci --ignore-scripts` | 0 | Installed locked packages; Vitest/depcruise executables subsequently ready; no manifest/lock change |

- **Migration probes:** Temporary fresh/current and seeded 0004→0005 upgrades, repeat upgrade, preservation of every row in word_families/word_forms/source_files/word_form_sources, one-head/down_revision checks, unique constraints, named range/enum/time constraints, source deletion preservation, canonical-form FK restriction after occurrence removal, and refused downgrade all pass within the 60-case suite. No live DB was accessed.
- **Negative probes (expected = actual):** invalid box→ValueError `Invalid box`; unknown rating→ValueError `Invalid rating`; same accepted operation→original event/one advancement (including two physical concurrent connections); direct duplicate-operation REPLACE→IntegrityError `Review operation already applied`; inactive→InactiveCardError `No valid source`; DB box/rating/source/range/time probes→their named CHECK constraints. Injected schedule failure rolls back the event/card/receipt for the intended synthetic error. No-attempt returns None with zero history/schedule change.
- **Exact full-suite blockers:** `backend/tests/test_consent.py:739`, `test_fresh_0002_to_0003_migration_repeat_and_history`, expects `["0003_consent"]`, observes `["0005_review"]`. This failure predates T031: the same focused legacy test was run before implementation and exited 1 with actual `["0004_vocabulary"]`. Its additional assertions at lines 746–747 also hard-code 0003. `backend/tests/test_vocabulary_storage.py:525`, `test_migration_0004_fresh_and_repeat_reaches_head`, expects schema_revision `0004_vocabulary`, observes `0005_review`; lines 534/555 likewise pin the old head. The authorized 0005 migration and T031 prior-head preservation test prove why this new failure occurs. Neither legacy test was edited, skipped or suppressed.
- **PENDING / not executed after stop:** `npm run test:frontend:coverage`, `npm run coverage:check`, `npm run architecture:check`, `npm run security:secrets`, `npm run security:code`, `npm run security:deps`, `npm run check:task`. Scanner version preflight is not a security scan PASS. The failing full run emitted coverage.xml, but the mandatory aggregate coverage gate has not run.
- **Toolchain:** Python 3.12.3; pytest 9.1.1; Node v22.23.2; npm 12.0.2. Pinned executable preflight: Gitleaks 8.30.1, Semgrep 1.178.0, OSV-Scanner 2.6.0, all available at the owner-provided locations. Shell export/version probes ran; no dependencies were added or changed.
- **Scope/handoff:** Four new authorized Python files and only this card/todo/changelog bookkeeping changed. Prior migrations, vocabulary/parser/search, HTTP/application/assessment/dashboard, frontend, generated contract, spec/API/ADRs/CONSTRAINTS, real vocabulary and credentials are untouched. T020/T026 were not merged, cherry-picked, rebased, read from other worktrees or imported. No staging, commit, push, remote change or history rewrite. Documentation-and-adrs SKILL.md was opened/read at the required path and applied to this rationale/evidence record.
- **Next action:** Owner-approved remediation limited to the two legacy migration tests (retain prior-revision probes and all assertions, resolve the current head as T005 already does), then rerun full pytest and every remaining gate before marking T031 DONE. T032/T022 work is not started here.

## Risk

- **Level:** `High`.
- Sai contract/concurrency/persistence có thể làm mất dữ liệu, ghi sai tiến độ hoặc tạo kết luận kiểm chứng sai.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- T013 has no accepted exact HARD/due oracle → dừng.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`feat(T031): review/card schema và deterministic srs`

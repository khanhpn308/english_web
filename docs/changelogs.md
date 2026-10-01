## 01/10/2026 - Local integration verification for T020, T026 and T031

- **Status/merges:** DONE on local `main`. Existing T020 merge `f2a5270` retained; completed the already-started T026 merge as `50967cf`, then merged T031 as `3b36d15`. No abort, restart, history rewrite, push, PR, task-branch deletion or worktree deletion.
- **Resolution semantics:** Preserve dynamic single-head initialization in consent and vocabulary tests, exact 0003→0002 / 0004→0003 historical ancestry, historical upgrade/ledger/history checks and consent's own downgrade refusal. T031 migration retains 0005→0004. Changelog keeps T031, T026, T020 and all prior history; task index checks all three and preserves unrelated states. Task implementation/tests match their reviewed branch versions byte-for-byte.
- **Focused checkpoints:** `python -m pytest backend/tests/test_search_index.py backend/tests/test_markdown_roundtrip.py backend/tests/test_consent.py -q`: exit 0, 199 passed in 23.76s before T031. `python -m pytest backend/tests/test_srs.py backend/tests/test_search_index.py backend/tests/test_markdown_roundtrip.py backend/tests/test_consent.py backend/tests/test_vocabulary_storage.py -q`: exit 0, 275 passed in 33.39s after T031.
- **Final verification:** `python -m pytest`: exit 0, 473 passed in 71.83s. `npm run test:frontend:coverage`: exit 0, 38 passed. `npm run coverage:check`: exit 0, changed lines 96.01% (minimum 80.00%), total lines 92.49% (baseline 86.70%, tolerance 0.50 points). `npm run architecture:check`: exit 0, no frontend violations, seven backend contracts kept, 40 tests passed in 23.82s. `npm run security:secrets`, `npm run security:code`, `npm run security:deps`: each exit 0, zero findings. `npm run check:task`: exit 0, repeating format/lint/types/floor, 38 frontend tests, 473 Python tests in 71.07s, coverage, all three security scans and architecture (40 tests in 23.33s). Coverage and aggregate gate used `QUALITY_BASE_REF=de9725ba1e79658f5bebc583ba09422692e5df9c`, the pre-wave main commit, to verify the entire integration delta.
- **Additional checks:** Full backend Mypy: exit 0, 40 source files. Focused Ruff across the three tasks and two migration tests: exit 0. Alembic heads: exit 0, exactly `0005_review`; explicit ScriptDirectory probe confirms 0001_storage→0002_operations→0003_consent→0004_vocabulary→0005_review. Conflict-marker scans return no matches; no unmerged paths; staged and working-tree whitespace checks pass.
- **Files changed/untouched:** Merge resolutions and integration evidence touch only `backend/tests/test_consent.py`, `docs/changelogs.md` and `tasks/todo.md` beyond task contributions; vocabulary's historical migration-test maintenance comes from T031. Final handoff adds only this changelog entry. Thresholds, dependencies/locks, generated contracts, frontend, earlier migrations, user vocabulary, live databases and task worktrees remain untouched. Reports are ignored local artifacts. Documentation follows the required documentation-and-adrs skill.
- **Risks/next:** No unresolved integration blocker; lint retains its two existing frontend fast-refresh warnings (zero errors). Windows/browser/100k-form release evidence remains governed by its own task cards; this integration does not claim it. Next planned dependency work is T021 (source-file adapter), with T022/T023 and T032 remaining separate tasks.

## 01/10/2026 - T031 authorized legacy-test remediation and completion

- **Local integration checkpoint:** Integrated with T020/T026 on main, retaining dynamic current-head checks and exact historical 0003→0002 / 0004→0003 upgrade, ledger, history and downgrade checks. Preserved all task history and checked only T031 beyond the prior main state. Five-suite focused pytest: exit 0, 275 passed in 33.39s; exact migration-chain probe and Alembic heads: exit 0, one `0005_review` head. Full backend Mypy: exit 0, 40 source files; focused Ruff and pre-commit secret scan: exit 0. No unmerged paths, conflict markers or staged whitespace errors.
- **Scope:** Owner-authorized changes only to the migration test in `backend/tests/test_consent.py`, the migration test/Alembic import in `backend/tests/test_vocabulary_storage.py`, T031 card, todo and this changelog. The four T031 implementation files remain unchanged during remediation; the earlier blocked checkpoint is preserved below. Documentation follows the required documentation-and-adrs skill already opened/read.
- **Semantic preservation:** Derive one current repository head rather than pinning historical global heads. Keep explicit 0003→0002 and 0004→0003 lineage, historical revision ledger checks, consent state/history/event columns and consent's own downgrade refusal, vocabulary tables/WAL/ledger/repeat safety. Add a pre-0004 seeded-history preservation probe. No meaningful assertions removed or behavioral guarantees weakened; AST audit confirms 66/16 other functions unchanged and assertion counts grow 9→13 / 6→13.
- **Verification:** Targeted consent/vocabulary/SRS pytest exits 0 (226 passed, 32.83s); full pytest exits 0 (424 passed, 80.39s). Full backend Mypy, six-file Ruff/format, floor and whitespace checks exit 0. Fresh frontend coverage has 38 passing tests; coverage gate passes changed 97.89%/total 91.82% with unchanged thresholds. Architecture passes seven contracts and 40 tests; pinned Gitleaks/Semgrep/OSV scans each report zero findings. Complete `npm run check:task` exits 0, repeating 424 Python/38 frontend tests and all coverage/security/architecture gates. One head remains `0005_review`; migration ancestry is unchanged.
- **Handoff:** T031 marked DONE with all acceptance boxes checked. Exactly six authorized implementation/test files and three bookkeeping files; no T020/T026 import, neighboring production edits, live DB access, commit/staging, push or Git history operation. Branch/HEAD remain `feature/task-t031-review-schema` / `de9725b`. Next: owner review and separately authorized commit/integration.

## 01/10/2026 - T031 review schema/SRS checkpoint (BLOCKED)

- **Files:** `backend/migrations/versions/0005_review.py`, `backend/app/review/srs.py`, `backend/app/review/models.py`, `backend/tests/test_srs.py`, T031 card, `tasks/todo.md` and this changelog. Documentation follows the required documentation-and-adrs skill, opened/read before editing.
- **Behavior/rationale:** Implement ADR-0005's exact box0–5/rating matrix and Bangkok local-calendar midnight scheduling. One canonical T019 word form owns one persistent card; VALID-source eligibility is derived on use. Frozen events, append-only/REPLACE guards, RESTRICT FKs and per-operation/card uniqueness preserve history, prevent repeated advancement and allow multi-card quiz operations. Caller-owned T005 writer transactions integrate with T014 receipts; reset changes only current schedule. No endpoints, quiz scoring, provider calls or parallel T020/T026 implementation.
- **Evidence:** Focused pytest 60 passed, Mypy (all four new Python files), focused Ruff/format, floor, whitespace and single Alembic head checks exit 0. Temporary 0004→0005/fresh/repeated migration probes preserve T019 data; concurrency, replay, source loss/re-add, reset, constraint rejection and atomic rollback pass. No live DB touched or destructive downgrade allowed.
- **Blocker:** Full pytest exits 1: 422 passed, 2 failed. Untouched `test_consent.py:739` pins 0003 (already failing against the pre-T031 0004 baseline); `test_vocabulary_storage.py:525` pins 0004 while the authorized head is now 0005. The owner requires STOP_SCOPE_BLOCKER before narrow legacy-test remediation. T031 remains BLOCKED/unchecked; frontend coverage, coverage/architecture/security gates and check:task were not executed after the stop and remain PENDING.
- **Handoff:** Baseline/end HEAD `de9725b`, branch `feature/task-t031-review-schema`, clean initial worktree. Locked `npm ci --ignore-scripts` restored missing task executables without dependency edits; all three pinned scanner binaries are available, but version probes do not establish scan success. Prior migrations, neighboring domains, frontend/contracts/authority and user files remain untouched. No staging, commit, merge, rebase, cherry-pick or push. Next: owner-authorized legacy-test remediation, then all mandatory gates.

## 01/10/2026 - T026 Vietnamese normalized n-gram projection

- **Local integration checkpoint:** Resolved the in-progress T026 merge on main by preserving T020 and T026 history, checking both tasks and leaving T031 pending. Consent retains dynamic single-head initialization plus the exact 0003→0002 ancestry assertion. Focused search/roundtrip/consent tests: exit 0, 199 passed in 23.76s. `python -m alembic heads`: exit 0, exactly `0004_vocabulary (head)`. No unmerged paths or conflict markers; staged whitespace check clean.
- **Files:** `backend/app/vocabulary/normalization.py`, `backend/app/vocabulary/search_index.py`, `backend/tests/test_search_index.py`, `backend/tests/test_consent.py` (narrow legacy head remediation authorized by owner), `tasks/t026-search-projection.md`, `tasks/todo.md`, `docs/changelogs.md`.
- **Mục đích:** Xây dựng Vietnamese normalized n-gram projection cho canonical vocabulary theo FR-VOC-01, ADR-0004, api-contract §7:
  - Chuẩn hóa Unicode NFC, Unicode casefold, và accent-folded Vietnamese projection với đ/Đ -> d mapping xác định.
  - Infix / substring matching cho cả truy vấn có dấu và không dấu, hỗ trợ truy vấn ngắn (1 ký tự).
  - Tách bạch rõ rệt giữa biểu diễn chính xác (exact) và biểu diễn gập dấu (accent-folded).
  - Giới hạn n-gram sinh ra ở mức $n \in \{1, 2, 3\}$, chặn bùng nổ tổ hợp, đảm bảo độ phức tạp $O(L)$ tuyến tính.
  - Tôn trọng ranh giới nguồn: chỉ các dạng từ có ít nhất một nguồn `VALID` mới hiển thị trong projection tìm kiếm; nguồn `INVALID`/`MISSING` không hiển thị nhưng không xóa dữ liệu canonical hay lịch sử học tập.
  - Bảo toàn định danh riêng biệt của từng từ loại (distinct POS): cùng lemma/family khác POS vẫn giữ nguyên các `word_form_id` độc lập.
  - Không suy đoán ngữ nghĩa (no semantic/synonym guessing), không embedding/AI, không phụ thuộc vào FTS5, an toàn tuyệt đối trước SQL injection và metacharacters (`%`, `_`, `'`, `"`).
  - Quản lý phiên bản projection và tính nhất quán của source revision: phát hiện và từ chối cập nhật source có revision cũ (`StaleSourceRevisionError`), kiểm tra phiên bản projection (`ProjectionVersionMismatchError`), không trả về kết quả rỗng giả mạo khi sai version.
  - Rebuild an toàn, có thể lặp lại (idempotent), không đụng chạm tới các bảng canonical hay bảng lịch sử.
- **Evidence:**
  - Focused tests: `python -m pytest backend/tests/test_search_index.py -q`: 25 passed in 1.22s (100% coverage on `normalization.py`, 95% on `search_index.py`).
  - Full tests: `python -m pytest`: 389 passed in 75.53s.
  - `npm run test:frontend:coverage`: 4 files, 38 passed.
  - `npm run coverage:check`: changed 97.66% (min 80.00%), total 91.85% (baseline 86.70%).
  - `npm run architecture:check`: 7 kept, 0 broken, 40 passed.
  - `npm run security:secrets`: 0 findings (Gitleaks 8.30.1).
  - `npm run security:code`: 0 findings (Semgrep 1.178.0).
  - `npm run security:deps`: 0 findings (OSV-Scanner 2.6.0).
  - `npm run check:task`: exit code 0.
  - Ruff check & format: zero diagnostics, all formatted.
  - Mypy: zero issues in 4 source files.
  - Floor check: clean, zero violations.
- **Untouched:** `backend/migrations/*`, `backend/app/vocabulary/models.py`, `backend/app/vocabulary/repository.py`, `backend/app/markdown_sync/*`, `backend/app/review/*`, `backend/app/http/*`, `frontend/*`, `contracts/*`, `docs/vocabularies/*`.

## 01/10/2026 - T020 Lossless Markdown parser and serializer

- **Files:** `backend/app/markdown_sync/parser.py`, `backend/app/markdown_sync/serializer.py`, `backend/tests/fixtures/legacy.md`, `backend/tests/test_markdown_roundtrip.py`, `backend/tests/test_consent.py`, `tasks/t020-markdown-parser.md`, `tasks/todo.md`, `docs/changelogs.md`.
- **Purpose/change:** Implement pure deterministic Markdown parser and serializer boundary for daily vocabulary notes (`DD-MM-YYYY.md`) per ADR-0004, ADR-0005, and spec DATA-01–06; perform owner-authorized narrow remediation on `backend/tests/test_consent.py` to replace hard-coded `0003_consent` migration head with dynamic derivation from Alembic `ScriptDirectory` metadata while strictly preserving T015 migration guarantees and history assertions.
- **Invariants & behavior:**
  1. Lossless round-trip: `serialize(parse(original)) == original` preserved byte-for-byte on synthetic and read-only real legacy fixtures (`28-09-2026.md`), including exact spacing, blank lines, table pipes, markdown links, and prose formatting.
  2. Multi-POS splitting: Comma-separated `Từ loại` tokens in primary entries and related forms produce distinct POS-specific semantic forms with independent identities under the same family root.
  3. Related forms: Family members created only with explicit lemma and deterministically interpretable POS; rows with ambiguous or missing POS remain opaque context and never create cards.
  4. Opaque content preservation: Unknown sections (e.g. `### Ghi chú bổ sung`, `## Ghi chú tài liệu`) and opaque contextual rows survive parse/serialize roundtrip untouched without generating semantic cards or forms.
  5. Deterministic validation & diagnostics: Fail-closed structured diagnostics for malformed filename, invalid calendar dates (e.g. `31-02-2026`), filename/H1 date mismatch, missing/malformed H1, truncated or malformed tables, and ambiguous POS.
  6. Source size boundary: Enforced 8 MiB (8,388,608 bytes) limit with `PAYLOAD_TOO_LARGE` diagnostic; no silent truncation.
  7. Unicode fidelity: NFD/combining-mark inputs preserve raw byte representation in serialization, while semantic normalized lemmas consistently resolve to NFC.
  8. Inert data: Untrusted instruction-like text, HTML/scripts, unusual links, and SQL strings remain completely inert text data.
  9. Absolute purity: Zero filesystem writes, zero disk reads in parser/serializer functions, zero SQLite database access, zero network/AI calls, zero global mutable state.
  10. Stale migration head remediation: `test_fresh_0002_to_0003_migration_repeat_and_history` dynamically checks `len(heads) == 1`, verifies `0003_consent` down-revision is `0002_operations`, and asserts `db.initialize().schema_revision == current_head` twice to verify repeat stability while keeping all T015 schema, table existence, event column, and history preservation assertions intact.
- **Evidence:**
  - Focused roundtrip pytest: `python -m pytest backend/tests/test_markdown_roundtrip.py -q` Exit 0, 24 passed in 0.51s (parser 91%, serializer 89%, total 91% coverage).
  - Remediated consent + roundtrip suite: `python -m pytest backend/tests/test_consent.py backend/tests/test_markdown_roundtrip.py -q` Exit 0, 174 passed in 31.57s.
  - Full pytest test suite: `python -m pytest` Exit 0, 388 passed in 75.85s (total coverage 90%).
  - Full task gate (`npm run check:task`): Exit 0, coverage changed lines 94.24% (minimum 80.00%), total lines 91.75% (baseline 86.70%), architecture gate 7 kept / 0 broken (40 passed), security scans all 0 findings.
  - Fast active check (`npm run check:fast:active`): Exit 0 (ESLint 0 errors, TS 0 errors, floor clean, ruff format 144 files formatted).
  - Focused Ruff check & format: Exit 0, 0 diagnostics across all modified files.
  - Full backend Mypy (`python -m mypy backend`): Exit 0, 33 source files checked, 0 errors.
  - Quality floor guard (`python scripts/check_constraints.py floor`): Exit 0, `floor: clean`.
  - Security scans (`npm run security:secrets`, `security:code`, `security:deps`): Exit 0, zero findings across all three scanners (Gitleaks 8.30.1, Semgrep 1.178.0, OSV-Scanner 2.6.0).
- **Files untouched:** `docs/vocabularies/28-09-2026.md` (read-only real sample preserved), frontend code, database models/migrations, HTTP routes, application services, and parallel worktrees (T026, T031).

## 01/10/2026 - T053 generated-source coverage classification remediation

- **Files:** `scripts/check_constraints.py`, `scripts/tests/test_constraints.py`, `tasks/t053-quality-security-gates.md` and this changelog; documentation follows the required documentation-and-adrs skill.
- **Reason/fix:** The changed-coverage checker incorrectly treated T017's generated DTO as handwritten source. Added `is_generated_source()` with the sole exact path `frontend/src/shared/api/generated.ts`, applied only to changed-line classification. Similarly named handwritten paths and unmeasured backend source still fail. Reports, total ratchet, diff-cover setup and quality/security protections remain enforced; no broad exemption.
- **TDD/evidence:** Corrected RED: 12 failed / 41 passed before implementation; GREEN: 53 passed. Full pytest 208 passed; frontend coverage tests 38 passed. Focused Ruff/format/Mypy, typecheck, lint, build, floor, coverage and fast gate pass. Changed coverage 100.00%, total 88.97%. Full Ruff exits 1 with 19 findings proven identical to the base in untouched files; no full-Ruff PASS claimed. Exact command outcomes and initial test/harness corrections are recorded in the task card.
- **T015 read-only replay:** Temporary clone of candidate `2386f3d12730cda8e886acb593b0fadcd473778d` with its actual reports: original checker exits 1 for unmeasured generated DTO; fixed checker exits 0 with changed 94.79% / total 89.89%. All T015 tracked files/reports remain byte-identical, candidate HEAD/status unchanged.
- **Thresholds/scope:** Minimum 80.0%, baseline 86.70%, tolerance 0.5 points unchanged. CONSTRAINTS, dependencies/locks, generated artifacts, frontend tests, T015, T062, security tooling and todo untouched. Pinned checksum-verified Gitleaks 8.30.1 reports zero findings; scanner binaries remain outside Git. Local remediation commit only; no push/main promotion/T015 edits. Next: cherry-pick into the T015 integration branch and rerun complete-candidate `check:task`.

## 01/10/2026 - T015 application-boundary architecture compatibility

- **Files:** `backend/app/application/consent.py`, `backend/app/http/consent.py`, `backend/tests/test_consent.py`; this changelog, T015 card and task-index evidence. Existing integration commits `cb81d69` / `20e4e3c` are preserved.
- **Reason/change:** T062 rejected HTTP's direct persistence import. The existing composed ConsentService now owns read/grant/revoke connections and translates storage failures into existing typed application outcomes. HTTP only renders those outcomes; SQLAlchemy, StorageError and engine access leave the route. Original policy/CAS/ledger/replay methods, main composition, migration and public schema remain unchanged.
- **Evidence:** new boundary tests RED exit 1 (10 failed / 3 already passed), then consent 150 and operations 14 pass. An initial test-union annotation error was corrected; Mypy and focused Ruff/format exit 0. Architecture exits 0 with seven kept contracts, zero forbidden direct graph paths and 40 tests; full Python exits 0 with 332 tests. Two canonical exports preserve both generated files byte for byte. Typecheck, lint (two inherited warnings), build, floor, check:fast and all three pinned security scans exit 0; scanners report zero findings.
- **Promotion blockers:** full Ruff exits 1 only for unchanged T014/T017 findings (test_operations.py E501 and test_contract.py RUF100). Complete-candidate check:task against authorized main `bc0ff937` exits 1 after all 332 tests pass because unchanged T053 tooling demands executable coverage for generated.ts. Remediation-only coverage against `20e4e3c` exits 0: changed 100.00%, total 89.89%, unchanged thresholds. This separate measurement does not clear the aggregate failure.
- **Handoff:** architecture compatibility is fixed; main promotion remains blocked by the required check:task gate. Main, T007, T062 rules, T014/T017 tooling, migration and source worktree remain untouched. T016 and CP06 remain pending; no dispatch admission/provider/network behavior change or push. Documentation follows the repository-required documentation-and-adrs skill.

## 01/10/2026 - T015 prerequisite-aware integration candidate

- **Files/scope:** transplant only the consent application, HTTP adapter and consent tests from `865740e`; apply the ten-file semantic delta from `7f4b320` on authorized local main `bc0ff937`. Historical qualityfix ancestry and T014/T017 tooling edits are excluded; T007 bridge formatting remains unchanged.
- **Evidence:** prerequisite files match their source byte for byte; Mypy, focused Ruff/format, 10 prerequisite tests, whitespace and zero-finding secret scan pass. Reviewed semantic source files match `7f4b320`; canonical contract generation is byte-identical across two runs.
- **Integration:** resolve changelog/task-index conflicts by retaining CP05 history and T052/T062/T007 completion plus T015 semantic completion. Candidate verification and main promotion remain gated; T016 and CP06 are pending. Earlier entries below describe their historical source snapshots, including former tooling blockers.

## 30/09/2026 - T015 resumed semantic remediation and verification

- **Files:** additional changes only in `backend/app/application/consent.py`, `backend/app/http/consent.py`, `backend/migrations/versions/0003_consent.py`, `backend/tests/test_consent.py`; canonically regenerated OpenAPI/DTO; T015 card and todo. Inherited implementation/quality fixes and the previous session's history are preserved; inherited `main.py` is untouched.
- **Change/purpose:** normalize complete structured policy definitions before hashing; reject duplicate registry keys and corrupt singleton/event/receipt evidence; require exactly-one-row CAS over revision/state/identity/time. Preserve committed historical receipts after ambiguous completion while denying AI capability. Store calendar-valid RFC3339 UTC event/choice times, enforce migration shape/registry checks, and correct startup storage error taxonomy plus GET's generated 422/503 schema.
- **Verification:** missing/corrupt evidence, canonical ordering, ambiguous completion, duplicate JSON/BLOB identities and startup storage taxonomy received RED-to-GREEN regressions. Added 47 cases to the inherited 90: consent 137, operations 14, full Python 279, frontend 38 and contract five all exit 0. Mypy, focused format, Ruff, TypeScript, build, floor and three security scans exit 0. Independent physical SQLite connections overlap deterministic writer transactions; stale grants lose. All consent paths have zero bridge/provider/socket/transport attempts. Two exports are byte-identical. Changed executable coverage 94.30%; measured combined 89.81%, unchanged thresholds.
- **Inherited failures:** check:fast/check:task exit 1 on the same untouched T007 format failures; coverage:check exit 1 because unchanged T053 tooling requires coverage for generated.ts. No aggregate PASS or tool/threshold modification. T062 architecture command is absent. Isolated fresh/0002-to-0003 migration verification has one head; no real database rebuild and no 0004 consent migration.
- **Handoff:** T015 acceptance DONE; workspace IMPLEMENTATION_DONE_BASELINE_BLOCKED. Detailed ownership, invariant matrix and exact source-frozen outcomes are in the T015 card. T016 and CP06 remain pending; no dispatch admission or bridge/provider calls were introduced. Not staged or committed; authorization not provided.

## 30/09/2026 - T015 final semantic remediation

- **Files:** the five T015 handwritten files (`backend/app/application/consent.py`, `backend/app/http/consent.py`, `backend/app/main.py`, `backend/migrations/versions/0003_consent.py`, `backend/tests/test_consent.py`); generated OpenAPI/DTO; T015 card and todo. Quality-fix base preserved; no other worktree or owner source edited.
- **Change/purpose:** enforce complete typed v1 READY policy, server canonical digest, durable immutable first-seen policy identities/conflicts, policy-sensitive opaque ETag and RFC3339 choice time. Grant/revoke calculate revisions inside T014's completion writer transaction; state/event/successful receipt commit atomically. Replay remains historical after withdrawal, key reuse preserves 422, revoke stays offline, validation rejects malformed requests without permission/history side effects. Missing/corrupt evidence and actual storage failures fail closed; event snapshots/history resist UPDATE/DELETE/REPLACE.
- **Verification:** RED tests reproduced semantic defects and reviewer findings before fixes. Final consent 90 PASS, operations 14 PASS, full Python 232 PASS, frontend 38 PASS, contract 5 PASS, two exports byte-identical; Mypy, Ruff lint/focused format, TypeScript, build, floor, whitespace and pinned secret/code/dependency scans PASS. Changed executable coverage 93.99%; combined measured coverage 89.56% exceeds the unchanged baseline. Exact commands/outcomes and SQLite two-engine/trigger evidence are recorded in the T015 card.
- **Remaining blockers:** repository formatter still fails only on byte-for-byte inherited T007 bridge files (`BASELINE_T007_FORMAT_BLOCKER`). Existing T053 coverage checker wrongly requests executable coverage for generated.ts; its FAIL is preserved, source/thresholds untouched. T015 semantic acceptance is DONE; whole workspace is IMPLEMENTATION_DONE_BASELINE_BLOCKED / NOT_READY_TO_COMMIT. Unreleased/current 0003 was completed in place with one head; no claim of upgrade compatibility for an old deployed 0003 database.
- **Handoff:** T016 is dependency-ready assuming T007 DONE; it remains TODO and no dispatch/provider work was added. No real credential/provider call, merge/rebase/pull, commit or push. Documentation follows the repository-required documentation-and-adrs skill.
## 01/10/2026 - T019 Schema vocabulary, source links và preview

- **Files:** `backend/migrations/versions/0004_vocabulary.py`, `backend/app/vocabulary/models.py`, `backend/app/vocabulary/repository.py`, `backend/tests/test_vocabulary_storage.py`, `tasks/t019-vocabulary-schema.md`, `tasks/todo.md`, `docs/changelogs.md`.
- **Mục đích:** Xây dựng schema bền vững và repository cho canonical vocabulary identity, liên kết nguồn Markdown nhiều ngày và quản lý lookup preview theo ADR-0004/DATA-01–06 và T013 contract.
- **Invariants:**
  1. Canonical identity: `(normalized_lemma, part_of_speech, family_id)` là duy nhất; nhiều ngày/nguồn dùng chung một canonical form.
  2. Distinct POS: Cùng lemma và family nhưng khác từ loại tạo ra các bản ghi canonical form riêng biệt.
  3. Ambiguous family: Reject fail-closed, không tự ý suy đoán hoặc gộp word family.
  4. Per-field verification: Giá trị thiếu (IPA, Cambridge URL) được lưu đúng `NULL`, không bịa đặt dữ liệu; giữ nguyên `verification_status` và `verificationSummary`.
  5. Source state isolation: Nguồn lỗi (`INVALID`/`MISSING`) hoặc bị xóa chỉ gỡ link, không cascade-delete canonical form hay lịch sử học tập.
  6. Preview ownership & expiration: Bắt buộc khớp session owner và kiểm tra expiration theo T013; dữ liệu lưu bền vững không chứa credentials/auth tokens.
- **Evidence:**
  - `python -m pytest backend/tests/test_vocabulary_storage.py -q`: 16 passed (coverage: models 94%, repository 95%, migration 95%, total 85%).
  - `python -m alembic heads`: `0004_vocabulary (head)`.
  - `lint-imports --config pyproject.toml --no-cache`: 7 kept, 0 broken.
  - `python scripts/check_constraints.py floor`: `floor: clean`.
  - Ruff check & format: zero errors, 4 files clean.
  - Mypy: zero issues in 4 source files.
  - Pending external tools: Gitleaks/Semgrep/Lighthouse ghi nhận `SETUP_PENDING`/`SETUP_FAILED` do môi trường chưa cài đặt nhị phân.
- **Untouched:** Toàn bộ frontend, bridge adapter, consent API, operation ledger, parser, search projection và SRS logic bên ngoài T019 được bảo toàn nguyên vẹn.

## 30/09/2026 - T052 Browser Harness

- **Files:** `frontend/tests/e2e/harness.spec.ts`, `frontend/tests/support/test_server.py`, `frontend/tests/support/fake_bridge.py`, `playwright.config.ts`, `package.json`, `package-lock.json`, `tasks/t052-browser-test-harness.md`.
- **Mục đích:** Cung cấp môi trường kiểm thử E2E và Accessibility UI an toàn, cô lập hoàn toàn khỏi hệ thống dữ liệu thực và Google inference, sẵn sàng cho các nhiệm vụ phát triển React components phía trên.
## 30/09/2026 - T062 resumed architecture-gate verification

- **Files:** Preserved interrupted `.dependency-cruiser.cjs`, `pyproject.toml`, `package.json`, generated npm/dev Python locks and `scripts/tests/test_architecture_gate.py` without implementation edits; updated T062 card, todo and this changelog using the repository-required documentation-and-adrs skill.
- **Reconstruction:** Branch `task/t062`, HEAD/base `b49a722`. Historical `test_real_frontend` failure did not recur. Initial exact pytest command used the original workspace virtualenv and failed 20 Python probes because import-linter/Grimp were absent; this worktree's existing virtualenv resolves the setup error.
- **Evidence:** Final focused pytest 40 passed; architecture gate exit 0: dependency-cruiser 13 modules / 14 dependencies / zero violations, import-linter 7 kept / 0 broken. Typecheck, focused Ruff/Mypy/format, config ESLint, floor and diff checks exit 0. Synthetic forbidden imports, cycles, exact generated DTO/sibling, valid type-only port and namespace-package probes all behave as required. After missing-tool/sandbox setup failures, the checksum-verified OSV-Scanner 2.6.0 network-enabled dependency scan exits 0 with zero findings; pip dependency consistency also passes. Scanner binary stays in `/tmp`.
- **Baseline blocker:** `npm run check:task` exits 1 at formatting in the two T007 bridge files. Both are byte-identical to `b49a722`; base-file formatting checks also exit 1. Application source, thresholds, contracts and unrelated tasks remain untouched. Whole branch not ready to commit; no commit, push or Git integration performed. Exact handoff and T052 package reconciliation are recorded in the task card.

## 30/09/2026 - T053 assertion-replacement floor remediation

- **Files:** `scripts/check_constraints.py`, `scripts/tests/test_constraints.py`, `tasks/t053-quality-security-gates.md` and this changelog; existing uncommitted changes preserved.
- **Reason/change:** T015's legitimate migration-head assertion replacements must not count as assertion deletions. Compare assertions per modified test file; tokenize Python with complete before/after context to exclude comment/string matches. Keep real deletion/net loss, test deletion, skip/suppression, unfinished work, threshold, coverage, no-HEAD and redaction protections. No path/migration exemption or threshold change.
- **Evidence:** Added regression cases first: RED exit 1, 4 failed / 30 passed; GREEN exit 0, 37 passed. Focused Ruff and Mypy exit 0. Isolated replay of the three actual T015 test diffs: original checker exit 1, eight `assertion-removed` findings; repaired checker exit 0, `floor: clean`.
- **Shared gate failures:** `npm run floor:check` exits 1 for existing suppression in `scripts/tests/test_contract.py:34`. `npm run check:fast` exits 1 at formatting in `backend/app/adapters/bridge.py` and `backend/tests/test_bridge.py`; later stages do not run. These files remain untouched. Remediation done; shared workspace not ready to commit. No commit authorized or created.

## 30/09/2026 - T007 final deadline remediation

- **Files:** `backend/app/adapters/bridge.py`, `backend/app/platform/bridge_port.py`, `backend/tests/test_bridge.py`, `tasks/t007-bridge-policy-consent-adapter.md` and this changelog.
- **Deadline:** Removed the redundant client-level timeout calculation. Every no-key models, keyed models and chat request independently receives `deadline - monotonic()` immediately before sending; nonpositive budget raises `BridgeUnavailableError` without another request. The same absolute deadline covers preflight and dispatch. This supersedes the earlier incomplete deadline evidence; operation deadline enforcement is no longer downstream evidence.
- **Tests:** Capture all HTTPX timeout phases: preflight 5.0 → 1.0 after four seconds; exact expiry sends only the no-key request; initially expired preflight sends none; dispatch after four seconds receives 1.0; independent operation deadline 15.1 receives 8.0 / 6.0 / 4.0 on the same adapter.
- **Verification:** Focused pytest 14 passed, Mypy adapters/platform and focused Ruff exit 0; `git diff --check` exit 0. Full pytest 152 passed outside sandbox (exit 0, coverage-file warnings); sandbox attempt stalled and was interrupted (exit 130). Full Mypy exit 1 with 33 errors in three parallel consent files; full Ruff exit 1 with 19 errors in parallel consent files, `test_operations.py` and `scripts/tests/test_contract.py`. Exact locations are recorded in the task card. Remediation DONE; whole working tree NOT_READY_TO_COMMIT until those unrelated checks pass.
- **Scope:** Fixture JSON, shared todo, parallel T015/T017/other source and tooling untouched. Independent concurrent changes to `scripts/check_constraints.py`, `scripts/tests/test_constraints.py` and `tasks/t053-quality-security-gates.md` were observed by hash comparison. No staging, commit, push, real key or inference.
- **Downstream:** Installed Windows/Antigravity profile, LAN isolation, T040 key provisioning, T016 consent/policy admission only. Documentation follows the repository-required documentation-and-adrs skill; no architecture or public API change.

## 30/09/2026 - T007 pre-commit cleanup and evidence audit

- **Files:** `backend/app/adapters/bridge.py`, `backend/tests/test_bridge.py`, `tasks/t007-bridge-policy-consent-adapter.md` and this changelog.
- **Correction:** Initial focused Ruff returned exit 1 with 12 diagnostics; this was FAIL. Removed unused imports, sorted imports, combined equivalent async contexts and renamed unused callback arguments without rule suppression. Replaced the existing test type suppression with `AsyncIterator[bytes]`.
- **Evidence:** Strengthened existing tests to capture the actual dispatch HTTPX timeout and unsafe-profile request path/Authorization absence. Focused pytest: 9 passed, exit 0; Mypy adapters/platform: exit 0; exact focused Ruff: exit 0; `git diff --check`: exit 0. Linux Python 3.12.3; synthetic mock transport only.
- **Deadline:** Operation 1 deadline 5.0, preflight starts 0.0, two requests consume 4.0, dispatch starts 4.0 and receives 1.0 seconds. After expiry at 5.1, no request is sent. Operation 2 deadline 15.1, dispatch at 7.1 receives 8.0 seconds. HTTPX phase timeouts do not alone prove the caller's end-to-end cancellation/hard-deadline admission gate; downstream T016 owns that integration.
- **Boundaries:** 4,194,303 and 4,194,304 bytes pass the size gate and fail synthetic JSON parsing; 4,194,305 bytes fail specifically on size. Unsafe no-key models 200 sends exactly one request, no Authorization and no chat. Approved sequence is no-key models 401, keyed models 200, then caller dispatch.
- **Untouched:** `bridge_port.py`, fixture JSON, shared `tasks/todo.md`, all pre-existing parallel consent/migration/tests and contract/client changes. No staging, commit, push or real inference.
- **Downstream PENDING:** Installed Windows/Antigravity profile, LAN isolation, protected real-key provisioning/rotation (T040), final consent/policy and operation admission (T016). A fully mimicking local listener remains the accepted ADR-0002 impersonation risk.

## 30/09/2026 - T066 Trusted browser bootstrap page

- **Khu vực:** `frontend/bootstrap.html`, `frontend/src/bootstrap.ts`, `vite.config.ts`
- **Thay đổi:** 
  1. Thêm Vite multi-page build cho phép sinh ra HTML và JS cô lập hoàn toàn cho `bootstrap.html`.
  2. Implement `bootstrap.ts` đọc `#token=...`, xóa URL fragment ngay lập tức qua `history.replaceState`.
  3. Gửi `POST /bootstrap/exchange`, bắt thành công HTTP 204 rồi chuyển hướng `location.replace("/")`.
  4. Unit test sử dụng mock dependencies (`BootstrapDependencies`) để đảm bảo không rò rỉ token, chứng minh trình tự gửi (clearing happens before fetching) và handle các mã lỗi 401, 403, 500, network error an toàn mà không in log token.
- **Mục đích:** Khởi tạo session an toàn trước khi vào app chính. Tránh token bị leak vào React application state, log hay analytics.
- **Pending Downstream:** T052, T057. (Chưa có real browser E2E, thuộc phạm vi T052).

## 30/09/2026 - T066 Trusted browser bootstrap page

- **Khu vực:** `frontend/bootstrap.html`, `frontend/src/bootstrap.ts`, `vite.config.ts`
- **Thay đổi:** 
  1. Thêm Vite multi-page build cho phép sinh ra HTML và JS cô lập hoàn toàn cho `bootstrap.html`.
  2. Implement `bootstrap.ts` đọc `#token=...`, xóa URL fragment ngay lập tức qua `history.replaceState`.
  3. Gửi `POST /bootstrap/exchange`, bắt thành công HTTP 204 rồi chuyển hướng `location.replace("/")`.
  4. Unit test sử dụng mock dependencies (`BootstrapDependencies`) để đảm bảo không rò rỉ token, chứng minh trình tự gửi (clearing happens before fetching) và handle các mã lỗi 401, 403, 500, network error an toàn mà không in log token.
- **Mục đích:** Khởi tạo session an toàn trước khi vào app chính. Tránh token bị leak vào React application state, log hay analytics.
- **Pending Downstream:** T052, T057. (Chưa có real browser E2E, thuộc phạm vi T052).

## 30/09/2026 - T017 Remediation

- **Khu vực:** `frontend/src/shared/api`, `scripts/export_contract.py`, `scripts/tests/test_contract.py`
- **Thay đổi:** 
  1. Loại bỏ các schema ErrorDetails ảo (chưa được backend hỗ trợ) ra khỏi generator, chỉ export `FIELD_ERRORS`.
  2. Bổ sung context (URL, method, Idempotency-Key, operationId) cho MutationUnknownError để phục vụ reconciliation.
  3. Cập nhật `test_contract.py` so sánh full-schema byte-for-byte với file checked-in.
  4. Sửa false positive ETag validation `null` guard.
- **Mục đích:** Sửa các bẫy lỗi và ranh giới hợp đồng API, đảm bảo generation không chèn dữ liệu unsupported và test chống trượt cấu trúc.

## 30/09/2026

- **Khu vực:** `frontend/src/shared/api`, `scripts/export_contract.py`, `contracts/openapi.json`
- **Thay đổi:** Hoàn thành T017. Thêm client API có hỗ trợ AbortController, tự động parse typed error. Thêm script generate openapi JSON deterministic.
- **Mục đích:** Xây dựng cầu nối type-safe, tự động lấy DTO từ backend OpenAPI.

## 30/09/2026

- **Khu vực:** `backend/app/application/operations.py`, `backend/app/http/operations.py`, `backend/app/main.py`, `backend/tests/test_operations.py`, `backend/migrations/versions/0002_operations.py`, `tasks/t014-operations-idempotency.md`, `tasks/todo.md`
- **Thay đổi:** Hoàn thành T014: triển khai durable operation ledger. Bổ sung `OperationLedger` với cơ chế idempotency dùng `BEGIN IMMEDIATE`, kiểm tra digest chống trùng lặp; cập nhật endpoint `GET /operations/{id}` redacted, và exception handler cho `SQLAlchemyError`. Pass toàn bộ test kiểm chứng concurrency, lost response, và fault injection.
- **Mục đích:** Đảm bảo tính idempotency và atomic cho các tác vụ AI và save, ngăn chặn duplicate dispatch, tuân thủ đúng API contract về error responses và data redaction.

# Changelog

## Quy định cập nhật

1. Mọi thay đổi do agent thực hiện trong workspace đều phải được ghi vào file này.
2. Ngày sử dụng định dạng **dd/mm/yyyy** và múi giờ `Asia/Bangkok`.
3. Mỗi mục phải nêu ngắn gọn:
   - Ngày thay đổi.
   - Khu vực/file bị thay đổi.
   - Nội dung thay đổi.
   - Lý do hoặc mục đích nếu cần.
4. Ghi mục mới ở đầu danh sách thay đổi, bên dưới phần quy định.
5. Không xóa hoặc sửa lịch sử cũ, trừ khi cần sửa lỗi ghi chép rõ ràng.
6. Agent phải cập nhật changelog trước khi kết thúc một tác vụ có thay đổi file.

## 30/09/2026

- **Khu vực:** `backend/app/http/session.py`, `errors.py`, `bootstrap.py`, `backend/app/main.py`, `backend/tests/test_session.py`, `tasks/t006-api-core-contract-foundation.md`, `tasks/todo.md`.
- **Thay đổi:** Hoàn thành T006 với token bootstrap một lần, session cookie trong bộ nhớ theo vòng đời backend, Host/Origin/Referer/JSON/1 MiB guards, typed redacted errors và same-origin static shell refresh. Health vẫn public; OpenAPI/API/shell cần session. Test RED→GREEN cho replay, expiry, restart, hai tab, hostile headers, max/max+1 và không phản chiếu token.
- **Verification:** 11 focused session tests, 89 full Python tests, 21 frontend tests, Mypy/Ruff/format/typecheck/build PASS; changed coverage 93,27%, total 88,50%; Gitleaks/Semgrep/OSV 0 findings. ESLint 0 errors, 2 warning Fast Refresh cũ. `npm run check:task:active` PASS; T062 architecture aggregate vẫn chưa có command.
- **Mục đích:** Khóa HTTP trust boundary của app local theo API contract và ADR-0005 trước T014/T017/T066. Documentation-and-adrs ghi rationale/handoff trong thẻ task; không tạo ADR mới vì strategy đã được chốt. Browser page/referrer thực và launcher tiếp tục ở task owner.

- **Khu vực:** `tasks/todo.md`, `docs/changelogs.md` và bộ tài liệu T013.
- **Thay đổi:** Tích hợp commit atomic T013 `d7196f3` vào nhánh T063, giữ nguyên evidence của cả T063 và T013, hợp nhất hai xung đột bookkeeping, chuẩn hóa code fence Python trong conformance report theo Ruff và đánh dấu CP03 hoàn tất.
- **Verification:** 11 document probes và 2 negative mutation probes PASS; staged scope/link/authority probe PASS; aggregate gate PASS với format/lint/typecheck, 21 frontend tests, 78 Python tests, changed coverage 100%, combined total 87,42% và ba security scanners đều 0 findings. ESLint còn 2 warning Fast Refresh đã tồn tại, 0 error.
- **Mục đích:** Đồng bộ task checklist và contract-conformance artifacts vào checkout đang được sử dụng mà không thay đổi semantics của API contract.

- **Khu vực:** T013 — `docs/api-contract.md`, `docs/reviews/contract-conformance-002.md`, thẻ T013.
- **Thay đổi:** Sau khi T063 cung cấp Gitleaks 8.30.1, thêm RED→GREEN security recheck cho snapshot contract: thay ba synthetic `Idempotency-Key` values bằng symbolic placeholder, bỏ raw API baseline digest khỏi prose và viết lại một bridge sentence bị rule generic-key bắt nhầm. Không đổi endpoint, schema, precondition hoặc semantics. Directory, staged diff và current-HEAD history (8 commits) đều 0 findings; không dùng allowlist/suppression.
- **Mục đích:** Giữ commit T013 atomic và tương thích security gate hiện hành mà không thay đổi quyết định contract hay quality bar.

- **Khu vực:** `scripts/security_checks.py`, `scripts/tests/test_security_checks.py`, `package.json`, generated `requirements-dev.lock`, `docs/toolchain.md`, `tasks/t063-security-scan-tooling.md`, `tasks/todo.md`; hai wording fixture/prose trong untracked planning `docs/api-contract.md` được sửa nhưng không stage do T013 sở hữu.
- **Thay đổi:** Hoàn thành T063 với wrapper exact-version cho Gitleaks 8.30.1, Semgrep CE 1.178.0 và OSV-Scanner 2.6.0; report chỉ chứa metadata đã redacted, high/critical/unknown fail closed, scanner/network/report lỗi trả setup failure, no-HEAD/untracked + staged + current-HEAD history được quét. Bổ sung 20 focused tests (78 full Python), changed coverage 88,98%, combined total 87,42% và real negative probes; nối npm security scripts/aggregate gates. Remediation được owner phê duyệt không dùng suppression: rewrite hai false-positive examples và regenerate dev lock bằng `--allow-unsafe`, chỉ thêm pin `pip==26.2.1`/`setuptools==84.0.0`. Ba security gates đều 0 findings.
- **Mục đích:** Biến ba security dimensions trong `CONSTRAINTS.md` thành executable gates mà không che finding bằng suppression/allowlist hoặc tự force-upgrade. Skill documentation-and-adrs được dùng để ghi pin/source/license/install boundary, privacy/exit contract, remediation trade-off và cross-branch T013 risk; không tạo ADR vì đây là tooling dễ đảo ngược, không đổi architecture/API.

## 29/09/2026

- **Khu vực:** `scripts/check_constraints.py`, `scripts/tests/test_constraints.py`, `package.json`, `pyproject.toml`, generated lockfiles, `docs/toolchain.md`, `tasks/t053-quality-security-gates.md`, `tasks/todo.md`.
- **Thay đổi:** Hoàn thành T053 bằng CLI diff-scoped cho changed coverage tối thiểu 80%, combined coverage baseline 86,70% với ratchet 0,5 điểm và quality-floor guard. Bổ sung 17 test cases âm/dương cho report thiếu, 79,9/80, ratchet, unmeasured source, suppression/skip/xóa test hoặc assertion/hạ threshold, redaction, coverage/floor trên untracked no-HEAD và trạng thái pending; nối Vitest V8 LCOV, pytest Cobertura, format/floor/coverage scripts và các aggregate command không false-green khi T062/T063 chưa sẵn sàng.
- **Mục đích:** Biến quality bar trong `CONSTRAINTS.md` thành gate có exit code và artifact thực, giữ scanner/architecture ownership tách biệt. Skill documentation-and-adrs được dùng để ghi nguồn chính thức, dependency/license, baseline, trade-off và trạng thái `SETUP_PENDING`; không cần ADR vì thay đổi chỉ là tooling dễ đảo ngược, không đổi architecture/API.

- **Khu vực:** T013 — `docs/spec.md`, `docs/api-contract.md`, `docs/ui-architecture.md`, `docs/adr/0005-contract-clarifications.md`, `docs/reviews/contract-conformance-002.md`, thẻ T013 và `tasks/todo.md`.
- **Thay đổi:** Chốt 11 nhóm conformance bằng ADR-0005: quiz 5–30 với ví dụ2/2/1 và reject1/1/1; HARD giữ box và due calendar midnight Bangkok; writing-rubric-v1/blank/null; conditional new-date save/backend source ID/revision/ETag; hash/watcher vs stale API409; keys/explanations chỉ trong terminal result, GET attempt/replay/SRS atomic; caps1/8/4MiB, session60s/8h, deadline120/60/30s và database-lifetime idempotency retention. Đồng bộ AC/DTO/UI và các positive fixtures.
- **Verification:** 11 document probes RED→GREEN; hai negative mutation probes reject đúng reason; manual crosswalk/walkthrough trong report. Staged whitespace/scope/link/provenance checks PASS sau khi chuẩn hóa metadata hard-break spaces trong scoped files; supplemental redacted credential-pattern scan zero candidates. Không có application code hoặc inference; generated/runtime/Windows/browser/provider/security tooling vẫn do task owner xác minh. Gitleaks chưa có (exit127), giữ PENDING.
- **Mục đích:** Cung cấp oracle xác định trước khi business contracts được freeze. Skill documentation-and-adrs giữ authority, alternatives/consequences và evidence ownership rõ ràng. Worktree riêng bảo toàn concurrent T053; chỉ stage allowlist/bookkeeping T013, gồm full snapshots của planning inputs trước đó untracked.

- **Khu vực:** `frontend/index.html`, `frontend/src/main.tsx`, `frontend/src/app/AppShell.tsx`, `frontend/src/app/shell.css`, `frontend/src/app/AppShell.test.tsx`, `vite.config.ts`, `tsconfig.json`, `tasks/t004-frontend-shell-routes.md`, `tasks/todo.md`.
- **Thay đổi:** Hoàn thành task T004 (React shell, route map và landmarks):
  - Triển khai `AppShell` với đầy đủ cấu trúc landmarks ngữ nghĩa (`<header>`, `<nav aria-label="Điều hướng chính">`, `<main id="main-content">`), skip link chuyển hướng đến nội dung chính và live region thông báo chuyển trang.
  - Thiết lập danh mục 9 route chuẩn hóa theo `docs/ui-architecture.md` §1 (`/`, `/lookup`, `/search`, `/word-forms/:wordFormId`, `/review`, `/quiz/new`, `/quiz/:attemptId`, `/quiz/:attemptId/result`, `/status`), bộ bóc tách dynamic route parameters và màn hình 404 cho route không hợp lệ.
  - Hiển thị trạng thái chưa khả dụng trung thực, không giả lập dữ liệu cho các route v1 chưa có logic nghiệp vụ.
  - Đảm bảo trạng thái `aria-current="page"` tại nav link đang active và bổ sung link truy cập quyền AI `/status#ai-consent` trong header shell.
  - Tích hợp `ErrorBoundary` bảo vệ ứng dụng khi một màn hình gặp sự cố và cung cấp liên kết chuyển sang kiểm tra trạng thái tại `/status`.
  - Cung cấp `shell.css` hỗ trợ responsive (320px - 1440px), tương phản cao, focus ring 3:1 và zoom 200% không che khuất control theo chuẩn WCAG 2.2 AA.
  - Đóng gói static build thành công vào `frontend/dist/` không chứa credentials hay bridge tokens.
  - Bổ sung 17 component/route test cases trong `AppShell.test.tsx`, đạt 21/21 tests frontend PASS cùng kiểm tra typecheck và lint hoàn hảo.
- **Mục đích:** Cung cấp khung giao diện React shell vững chắc, accessible và route map chuẩn mực cho các task giao diện tiếp theo.

## 29/09/2026

- **Khu vực:** `backend/app/main.py`, `backend/app/http/health.py`, `backend/tests/test_health.py`, shared `backend/app/persistence/database.py`/`backend/tests/test_storage.py`, thẻ T005, `tasks/todo.md`.
- **Thay đổi:** Hoàn tất phần T005-B theo scope được owner xác nhận: startup kiểm tra/migrate SQLite trước khi bật readiness; lỗi storage giữ `NOT_READY`; shutdown dispose engine và xóa readiness. Thay fixture file rỗng bằng SQLite thật, thêm 5 health/lifecycle cases và 2 schema edge cases từ review (reserved-prefix filter và view-only database). Final focused storage 24 PASS; full suite 41 PASS; Ruff/format/Mypy PASS; một Alembic head. Cập nhật T005 `DONE` với handoff và các gate downstream còn PENDING.
- **Mục đích:** Health phản ánh kết quả storage startup và bảo toàn dữ liệu trong failure paths. Skill documentation-and-adrs giúp ghi rõ default timeout, scope split, nguồn framework, evidence và giới hạn Linux/Windows/security tooling mà không thay spec/API contract.

## 29/09/2026

- **Khu vực:** `backend/app/persistence/database.py`, `backend/migrations/env.py`, `backend/migrations/versions/0001_storage.py`, `backend/tests/test_storage.py`, generated `alembic.ini`, task T005.
- **Thay đổi:** Hoàn tất phần T005-A theo scope split được owner xác nhận: migration ledger, FK trên mỗi connection, bounded busy timeout, phát hiện WAL, integrity/schema checks trước mutation, migration trong transaction và fail-safe readonly/corrupt DB. Thêm 22 storage cases; full suite 34 PASS, Ruff/format/Mypy PASS, một Alembic head.
- **Mục đích:** Có checkpoint storage kiểm chứng được trước khi nối health/lifecycle ở T005-B; domain schema và dữ liệu học thật được giữ ngoài scope.

## 29/09/2026

- **Khu vực:** `tasks/t005-database-schema-migrations.md`, `docs/changelogs.md`.
- **Thay đổi:** Ghi audit khi tiếp tục T005: baseline health T003 đạt 8 tests; phát hiện health readiness và fixtures cần sửa ở hai file ngoài allowlist, khiến task cần scope clarification/chia nhỏ trước implementation.
- **Mục đích:** Ghi rõ điểm chặn và evidence để tiếp tục đúng phạm vi; chưa thay application code, allowlist, spec/API contract hoặc đánh dấu T005 hoàn tất.

## 29/09/2026

- **Khu vực:** `tasks/t005-database-schema-migrations.md`, `docs/changelogs.md`.
- **Thay đổi:** Ghi checkpoint tạm dừng T005 sau khi đọc dependency/contract và kiểm tra trạng thái repository; chưa viết test/implementation, chưa chạy verification hay commit T005. Giữ task `TODO` để phiên sau bắt đầu từ bước test RED.
- **Mục đích:** Bảo toàn ngữ cảnh và ranh giới scope cho phiên làm việc tiếp theo theo yêu cầu người dùng.

## 29/09/2026

- **Khu vực:** backend/app/main.py, backend/app/http/health.py, backend/app/platform/config.py, backend/__init__.py, backend/tests/test_health.py, tasks/t003-backend-skeleton.md, tasks/todo.md.
- **Thay đổi:** Hoàn thành task T003: Triển khai FastAPI app factory (`create_app`) và endpoint `GET /api/v1/health` theo đúng normative schema `HealthSummary` (`status`, `version`, `storageStatus`, `bridgeStatus`, `readiness`) và header `Cache-Control: no-store`; cấu hình `AppSettings` với ràng buộc chỉ bind loopback interfaces (127.0.0.1, localhost, ::1) theo threat T-01; kiểm tra storage status trung thực (`OK` khi storage tồn tại, `NOT_READY` khi missing); độc lập hoàn toàn với AI bridge (0 inference call, 0 credential read); quản lý vòng đời ASGI startup/shutdown qua lifespan context; bổ sung 8 tests với 100% độ phủ mã nguồn cho backend app; vượt qua toàn bộ Mypy strict, Ruff và Pytest quality gates.
- **Mục đích:** Cung cấp skeleton backend vững chắc và health probe cho các task tiếp theo (T004 frontend shell, T005 SQLite migration zero).

## 29/09/2026

- **Khu vực:** pyproject.toml, backend/tests/conftest.py, backend/tests/test_toolchain.py, docs/toolchain.md, tasks/t058-python-quality-gates.md, tasks/todo.md.
- **Thay đổi:** Hoàn thành task T058: Cấu hình Python quality gates gồm Ruff linter với quy tắc chuẩn (E, W, F, I, B, C4, UP, ARG, SIM, RUF), MyPy static type checker ở chế độ strict (strict = true, files = ["backend"]), Pytest và Pytest-cov tự động xuất báo cáo Cobertura XML (`coverage.xml`) sau mỗi lần chạy suite; tạo `backend/tests/conftest.py` với fixtures `project_root` và `python_version_info`; tạo `backend/tests/test_toolchain.py` kiểm tra phiên bản Python >=3.12, importable dependencies từ lockfiles, nạp fixtures và cấu hình pyproject; thực hiện negative probes xác nhận phát hiện lỗi assertion, collection, lint và type mismatches; hoàn tất checkpoint CP01.
- **Mục đích:** Cung cấp hạ tầng quality gates, runner và coverage cho backend theo CONSTRAINTS.md, sẵn sàng cho việc triển khai FastAPI app factory tại T003.

## 29/09/2026

- **Khu vực:** package.json, package-lock.json, tsconfig.json, eslint.config.js, vite.config.ts, frontend/tests/toolchain.test.ts, tasks/t002-quality-gates-test-runner-build.md, tasks/todo.md.
- **Thay đổi:** Hoàn thành task T002: Cấu hình frontend quality gates gồm ESLint flat config (eslint.config.js với typescript-eslint và react plugins), TypeScript strict configuration (tsconfig.json), Vite 8 và Vitest runner (vite.config.ts với passWithNoTests=false); bổ sung scripts `lint`, `typecheck`, `test:frontend`, `build` vào package.json; tạo bộ test frontend ban đầu frontend/tests/toolchain.test.ts kiểm tra runtime Node >=20.19.0, assertions và báo cáo BUILD_PENDING_SHELL; xác minh probes bắt lỗi âm/dương cho assertion, type, lint và build thiếu entry point.
- **Mục đích:** Cung cấp hạ tầng quality gates và test runner hoàn chỉnh cho frontend theo CONSTRAINTS.md và UI architecture §10, sẵn sàng cho T004.

## 29/09/2026

- **Khu vực:** package.json, package-lock.json, requirements.lock, requirements-dev.lock, README.md, docs/toolchain.md, tasks/t001-toolchain-repository-skeleton.md, tasks/todo.md.
- **Thay đổi:** Hoàn thành task T001: Khóa phiên bản toolchain frontend (React 19, TypeScript 5.8, Vite 8) qua package.json và package-lock.json; khóa phiên bản toolchain backend (FastAPI 0.141, Pydantic 2.13, SQLAlchemy 2.1, Alembic 1.20, Uvicorn 0.54, HTTPX 0.28, Ruff 0.16, MyPy 2.3, Pytest 9.1, Pytest-cov 7.1, Pip-tools 7.6) qua pyproject.toml và requirements.lock / requirements-dev.lock; tạo README.md và docs/toolchain.md hướng dẫn cài đặt và công bố trạng thái readiness của lệnh; xác minh clean install tái lập độc lập và cấu hình .gitignore.
- **Mục đích:** Thiết lập nền tảng toolchain có thể tái lập cho toàn bộ các task downstream bắt đầu từ T002 và T058, tuân thủ CONSTRAINTS.md và AGENTS.md.

## 29/09/2026

- **Khu vực:** CONSTRAINTS.md, AGENTS.md, tasks/_template.md, tasks/t001–t066, tasks/todo.md, docs/task-plan.md, docs/project-context.md.
- **Thay đổi:** Hoàn thiện bản planning thành 66 task nhỏ và 22 checkpoints; tách quiz generation/draft/submission/feedback, các UI flow, tool runners, benchmark và Windows/recovery evidence. Sửa nội dung ghép sai ở 9 task card, commit proposals, scope allowlists, route wiring, dependency order và references. Bổ sung command owner/readiness registry, planned numeric configuration và ranh giới canonical learning storage/diagnostic redaction, giữ các quality thresholds.
- **Mục đích:** Có kế hoạch bắt đầu được từ T001, với T013 conformance là prerequisite cho business contract; không đánh dấu application tests/release evidence đã PASS. Kiểm tra planning có 66 unique cards, 225 dependency edges không chu kỳ, 22 checkpoints và link/current-vs-planned outputs đúng; lưu evidence ở docs/reviews/planning-validation-001.md. Mọi implementation task vẫn TODO; không application code, real provider request, commit, remote hay PR được tạo trong session này.

## 29/09/2026

- **Khu vực:** `CONSTRAINTS.md`, `AGENTS.md`, `tasks/`, `docs/task-plan.md`, `docs/project-context.md`.
- **Thay đổi:** Tạo quality bar bảo thủ với floor, type/lint/test/coverage/security/accessibility/performance gates; tạo persistent agent context; chia implementation thành 46 task cards nhỏ với dependencies, checkpoints, verification, stop conditions và commit proposals; thêm todo/plan pointers và cập nhật project map.
- **Mục đích:** Chuyển design baseline `READY_FOR_PLANNING` thành kế hoạch implementation có thể kiểm chứng, không viết application code, không tạo remote/commit hoặc gọi provider.

## 29/09/2026

- **Khu vực:** `docs/spec.md`, `docs/api-contract.md`, `docs/ui-architecture.md`, `docs/security-review.md`, `docs/observability-plan.md`, `docs/adr/0001-architecture.md`, `docs/project-context.md`, `docs/reviews/spec-architecture-review-001.md`.
- **Thay đổi:** Loại bỏ các câu hiện hành còn tham chiếu OQ/policy chưa chốt; chuẩn hóa model `gemini-3.8-flash-high`, revision conflict, local SpeechSynthesis, hard timeout/cancellation budgets, runbook first-run, ADR-0004 authority và đánh dấu phần review cũ là historical. Sửa các acceptance/UI/API mâu thuẫn (LWW, missing IPA/link, offline audio, FTS5 boundary) và thêm final doubt-driven recheck với không còn Critical/Major design blocker. Giữ các runtime/profile/benchmark/`CONSTRAINTS.md` items là evidence gates.
- **Mục đích:** Kết thúc design-blocked state một cách nhất quán, không tuyên bố application code hoặc runtime/security tests đã pass.

## 29/09/2026

- **Khu vực:** status headers, project context, ADR-0002/0003, review disposition, security/API audio wording.
- **Thay đổi:** Hoàn tất đồng bộ sau closure pass; ghi `READY_FOR_PLANNING` cho spec/architecture/review, đánh dấu historical blocker sections, chuyển audio sang SpeechSynthesis local và loại bỏ các câu còn tuyên bố OQ/paid-fallback/LWW chưa chốt.
- **Mục đích:** Kết thúc design-blocked state đúng theo ADR-0004; giữ `CONSTRAINTS.md` và runtime tests làm planning/implementation gates.

## 29/09/2026

- **Khu vực:** `docs/spec.md`, `docs/api-contract.md`, `docs/ui-architecture.md`, `docs/security-review.md`, `docs/observability-plan.md`, `docs/reviews/spec-architecture-review-001.md`.
- **Thay đổi:** Đồng bộ các contract theo ADR-0004: revision conflict thay LWW, five-box SRS/quiz snapshot/limits, local SpeechSynthesis, WCAG 2.2 AA target, benchmark/timeout gates, journal recovery, dashboard formulas và OQ overlay. Đánh dấu các R2 section cũ là historical và dùng closure table làm disposition hiện hành.
- **Mục đích:** Giữ tài liệu nhất quán sau khi owner ủy quyền chốt mọi blocker; vẫn phân biệt decision closure với runtime verification.

## 29/09/2026

- **Khu vực:** `docs/adr/0004-v1-product-policy-and-operational-baseline.md`, spec/API/UI/security/observability/ADR-0001/project context/review.
- **Thay đổi:** Chốt toàn bộ OQ-01–OQ-14 bằng các mặc định v1 bảo thủ: provider/model/cost policy, five-box SRS, quiz snapshot/rubric, identity/conflict/journal, Windows launcher/autosave, local SpeechSynthesis, WCAG 2.2 AA, benchmark/timeouts, dashboard formulas, secret/recovery boundary và legacy Markdown. Chuyển architecture/spec/review sang `READY_FOR_PLANNING`; giữ runtime/CONSTRAINTS gates cho planning/implementation.
- **Mục đích:** Kết thúc trạng thái block theo ủy quyền của owner mà không tuyên bố code/runtime/security tests đã pass.

## 29/09/2026

- **Khu vực:** `docs/spec.md`, `docs/security-review.md`, `docs/adr/0002-antigravity-loopback-trust-boundary.md`, `docs/reviews/spec-architecture-review-001.md`.
- **Thay đổi:** Ghi nhận owner không cấm paid fallback về nguyên tắc; làm rõ fallback trả phí chỉ được dùng khi READY policy khai báo route/provider/model/billing, disclosure/consent và quyền hạn/quota tương ứng.
- **Mục đích:** Tách “không cấm” khỏi việc tự cấp phép hoặc tự bật fallback; giữ các quyết định provider, route, entitlement, quota, retention và region ở R2-002.

## 29/09/2026

- **Khu vực:** `docs/api-contract.md`, `docs/spec.md`, `docs/ui-architecture.md`, `docs/security-review.md`, `docs/adr/0001-architecture.md`, `docs/adr/0003-ai-consent-and-revocation.md`.
- **Thay đổi:** Bổ sung immutable policy digest/structured disclosure fields, exact scope and dispatch-rule authorization, cross-process consent fencing, append-only consent events và redacted Operation provenance; sửa retry feedback bằng key mới; đánh dấu audio disabled tới OQ-06; khôi phục câu chữ ADR-0001 ở dạng historical với supersession notice; cập nhật AC-27/AC-34 và test cases.
- **Mục đích:** Xử lý các finding fresh review mà không tự chọn provider/quota/billing/retention/region hoặc hạ tiêu chuẩn bảo mật.

## 29/09/2026

- **Khu vực:** API/spec/UI/security/observability/ADR-0001/ADR-0003 và review `spec-architecture-review-001.md`.
- **Thay đổi:** Reconcile fresh adversarial review: ràng buộc policy theo digest + scope/provider/model/route/billing, fence consent cross-process, event audit/provenance, retry feedback bằng key mới, AC-27/AC-34 chính xác hơn, audio disabled khi OQ-06 chưa sẵn sàng và disclosure schema có trường bắt buộc. Ghi nhận R3-001–R3-013 cùng các release/runtime gates.
- **Mục đích:** Không để consent boolean, smoke test hoặc CLI wording vượt qua policy cloud, auth/profile, audio và retry boundaries; giữ R2-002 cùng các blocker khác ở trạng thái chưa sẵn sàng.

## 29/09/2026

- **Khu vực:** `docs/adr/0003-ai-consent-and-revocation.md`; spec/API/UI/security/observability, project context và review ledger.
- **Thay đổi:** Áp dụng phê duyệt của owner cho consent AI local default-deny: disclosure trước lần gửi đầu tiên, lưu policy version/choice, revoke offline chặn dispatch mới và giữ học cục bộ. Thêm API singleton/ETag/idempotency/dispatch gate, UI `/status#ai-consent`, AC-37–40, CONSENT-01–10, threat T-22 và telemetry redaction.
- **Mục đích:** Xử lý phần consent của R2-002 mà không giả định provider/model/quota/billing/retention/region đã được duyệt; giữ R2-002 blocked và không viết application code, gọi cloud hoặc lưu credential.

## 29/09/2026

- **Khu vực:** `docs/adr/0002-antigravity-loopback-trust-boundary.md`; supersession notice ở ADR-0001; spec/API/security/observability, bridge runbook, project context và review ledger.
- **Thay đổi:** Áp dụng phê duyệt của owner cho HTTP loopback + proxy API key với Antigravity v4.8.4 và rủi ro giả mạo process cục bộ được chấp nhận. Bỏ yêu cầu bridge IPC/per-launch/process authentication chưa có cơ sở; thêm profile/preflight/error contract, AC-36/BR-AUTH-01–08 và làm rõ ranh giới trace tại app→proxy. Giữ nguyên thân ADR-0001, không sửa `CONSTRAINTS.md` hay browser session.
- **Mục đích:** Xử lý R2-001 ở cấp thiết kế mà không giả định đã pass runtime/security tests. R2-002 và các blocker khác vẫn mở; không đổi `REVIEW_STATUS`, viết application code, gọi inference hoặc thay cấu hình/credential thực tế.

## 29/09/2026

- **Khu vực:** `docs/spec.md`, `docs/api-contract.md`, `docs/security-review.md`, `docs/project-context.md`, `docs/reviews/spec-architecture-review-001.md`
- **Thay đổi:** Ghi nhận owner xác nhận Antigravity Tools v4.8.4 và đối chiếu tag tới commit nguồn đã kiểm tra. Chuyển điểm cần làm rõ của R2-001 từ phiên bản sang quyết định ranh giới tin cậy; ghi phương án loopback/API-key cùng trade-off nhưng chưa áp dụng.
- **Mục đích:** Không hỏi lại phiên bản đã biết và không coi xác nhận phiên bản là phê duyệt thay đổi xác thực. Chưa sửa cấu hình, dùng credential, viết application code hoặc đổi review status.

## 29/09/2026

- **Khu vực:** `docs/spec.md`, `docs/api-contract.md`, `docs/security-review.md`, `docs/project-context.md`, `docs/reviews/spec-architecture-review-001.md`
- **Thay đổi:** Ghi nhận bridge do owner xác nhận là Antigravity Tools / Antigravity-Manager; phân biệt proxy API key với token/session Google; sửa cách gọi CLI trong luồng hiện hành. Bổ sung bằng chứng upstream theo commit về auth `auto/off`, bearer-key và giới hạn xác thực process; ghi rõ phiên bản cài đặt chưa biết.
- **Mục đích:** Thu hẹp R2-001 bằng nguồn chính thức của dự án mà không tự chấp thuận auth/model/billing, không thay đổi cấu hình, không đọc credential và không đóng blocker khi chưa đủ bằng chứng. Giữ `REVIEW_STATUS: BLOCKED`.

## 29/09/2026

- **Khu vực:** post-apply review, API/UI contracts, security/observability and project context
- **Thay đổi:** Chạy final doubt-driven recheck; sửa lookup idempotency/operation, feedback failure history, quiz answer examples, autosave/PATCH reconciliation, bootstrap wording, legacy date example và runbook retry semantics. Ghi nhận residual R2 owner gates và giữ `REVIEW_STATUS: BLOCKED`.
- **Mục đích:** Không tuyên bố readiness khi bridge auth/consent, source conflict/recovery, quiz/SRS rules, legacy mapping, benchmark, launcher lifecycle, audio/accessibility và recovery policy vẫn chưa được owner chốt.

## 29/09/2026

- **Khu vực:** `docs/reviews/spec-architecture-review-001.md`, `docs/api-contract.md`, `docs/observability-plan.md`, `docs/ui-architecture.md`
- **Thay đổi:** Chạy post-apply doubt-driven review; bổ sung residual blocker ledger R2-001–R2-020, feedback history/failure retrieval, status metrics/lifecycle, autosave/PATCH operation reconciliation, quiz answer restoration và error recovery DTO.
- **Mục đích:** Giữ `REVIEW_STATUS: BLOCKED` khi còn decision gates thay vì tự hạ chuẩn hoặc chuyển thủ công sang planning.

## 29/09/2026

- **Khu vực:** `docs/spec.md`, `docs/api-contract.md`, `docs/ui-architecture.md`, `docs/reviews/spec-architecture-review-001.md`
- **Thay đổi:** Bổ sung implementation gates trong spec, source/projection write protocol trong API, provisional conflict/startup behavior trong UI, và resolution ledger cho toàn bộ Critical/Major findings.
- **Mục đích:** Phân biệt rõ finding đã xử lý bằng contract với finding còn cần owner quyết định, không hạ chuẩn hoặc đổi `REVIEW_STATUS` thủ công.

## 29/09/2026

- **Khu vực:** architecture contracts, security/observability docs, ADR, spec clarifications, review reconciliation và `docs/runbooks/`
- **Thay đổi:** Áp dụng các finding đã được chấp thuận từ `spec-architecture-review-001`: hoàn thiện DTO/error/operation/revision contracts; làm rõ Vietnamese meaning search, Markdown round-trip/source revisions, quiz restore/SRS handoff, startup/offline/session states, authenticated loopback bridge, safe-path residuals, local-only telemetry defaults và runbooks.
- **Mục đích:** Giảm mâu thuẫn và các điểm không thể kiểm chứng mà không tự đóng các product OQ về provider, SRS/rubric, quiz snapshot, audio, conflict, backup, accessibility hoặc performance.

## 29/09/2026

- **Khu vực:** `docs/reviews/spec-architecture-review-001.md` và `docs/changelogs.md`
- **Thay đổi:** Thực hiện adversarial review độc lập cho spec và bộ tài liệu architecture; ghi nhận các finding về OQ chưa chốt, mâu thuẫn Markdown/SQLite và LWW/ETag, FTS5/search, quiz/SRS/autosave, bootstrap/bridge security, API schema, offline/runtime, observability và acceptance criteria.
- **Mục đích:** Chặn việc lập kế hoạch triển khai khi thiết kế còn rủi ro hoặc không thể kiểm chứng; yêu cầu owner review và chỉ áp dụng các finding được chấp thuận.

## 29/09/2026

- **Khu vực:** `docs/api-contract.md`, `docs/ui-architecture.md`, `docs/security-review.md`, `docs/observability-plan.md`, `docs/adr/0001-architecture.md`
- **Thay đổi:** Tạo contract REST/OpenAPI v1, kiến trúc UI/routes/flows, threat model bảo mật, kế hoạch structured logs/metrics/traces/alerts và ADR chọn React + TypeScript + Vite, FastAPI/Python, SQLite + SQLAlchemy/Alembic trên runtime Windows loopback.
- **Mục đích:** Chuyển spec sản phẩm thành architecture có thể triển khai mà không viết application code; giữ các `OQ-*` chưa chốt ở trạng thái review, ghi nguồn tài liệu chính thức và nêu rõ temporary constraints snapshot vì `CONSTRAINTS.md` chưa tồn tại.

## 29/09/2026

- **Khu vực:** `docs/spec.md` và `docs/changelogs.md`
- **Thay đổi:** Chốt hướng runtime local + inference cloud qua local OpenAI-compatible bridge; ghi nhận smoke test thật với `GET /health`, `GET /v1/models` và `POST /v1/chat/completions`. Bổ sung yêu cầu prompt template có version/placeholders, JSON response validation, lưu feedback theo attempt/question/model/prompt version và bảo vệ API key ở backend.
- **Mục đích:** Xác định contract tích hợp AI để chấm/nhận xét, trả feedback cho frontend và truy xuất lịch sử mà không đưa secret vào frontend hoặc database.

- **Khu vực:** `docs/spec.md` và `docs/changelogs.md`
- **Thay đổi:** Tạo spec chính thức từ biên bản product discovery, gồm problem statement, goals, users, journeys, capability map, requirements, business rules, dữ liệu, auth/authorization, UI states, accessibility, security, performance, scope/non-goals, acceptance criteria, open questions và assumptions; ghi trạng thái `SPEC_STATUS: DRAFT_REVIEW_PENDING`.
- **Mục đích:** Tạo bản review với capability gắn nhu cầu, 35 acceptance criteria có điều kiện/kết quả kiểm chứng, và đánh giá những điểm còn chặn việc chốt API, UI hoặc task triển khai; giữ các quyết định chưa rõ trong open questions và không tự chọn framework.

- **Khu vực:** `docs/interviews/product-discovery-001.md` và `docs/changelogs.md`
- **Thay đổi:** Tạo biên bản product discovery sau khi người dùng xác nhận `FINALIZE INTERVIEW`; ghi mục tiêu, người dùng, journeys, phạm vi/non-goals, dữ liệu và quyền truy cập, business rules, edge cases, yêu cầu phi chức năng, acceptance criteria sơ bộ, quyết định đã chốt, giả định và câu hỏi còn mở.
- **Mục đích:** Làm đầu vào viết spec dựa trên interview, phân biệt các quyết định mới với tài liệu tham chiếu và tránh coi những điểm chưa chốt là yêu cầu đã thống nhất.

- **Khu vực:** Git repository và `docs/project-context.md`
- **Thay đổi:** Xác nhận project root, khởi tạo Git với branch mặc định cục bộ `main`, và cập nhật context về trạng thái repository chưa có commit/remote.
- **Mục đích:** Chuẩn bị nền tảng version control cho giai đoạn thiết kế.


- **Khu vực:** `docs/project-context.md`
- **Thay đổi:** Ghi lại repository map, trạng thái Git, runtime/toolchain, frontend/backend hiện có, giới hạn, giả định và câu hỏi cho session tiếp theo.
- **Mục đích:** Tạo context bền vững cho giai đoạn thiết kế mà không thêm application code hoặc sửa spec.


- **Khu vực:** `AGENT.md`
- **Thay đổi:** Quy định agent phải sử dụng skill `agent-skills:documentation-and-adrs` khi tạo hoặc cập nhật tài liệu kỹ thuật, spec, ADR, API documentation, README hoặc changelog.
- **Mục đích:** Đảm bảo tài liệu ghi lại bối cảnh, lý do, đánh đổi và hệ quả của các quyết định quan trọng.

## 28/09/2026

- **Khu vực:** `AGENT.md`
- **Thay đổi:** Thêm quy định bắt buộc agent cập nhật `docs/changelogs.md` cho mọi thay đổi trong workspace.
- **Mục đích:** Đảm bảo mọi thay đổi đều có lịch sử theo dõi thống nhất.

## 28/09/2026

- **Khu vực:** `docs/`
- **Thay đổi:** Thêm quy định changelog và tạo cấu trúc tài liệu `development/spec`, `development/tasks`, `deployment/guide`.
- **Mục đích:** Theo dõi mọi thay đổi do agent thực hiện theo ngày.

# T049: Writing feedback API và history retry

**Task ID:** `T049`  
**Title:** Writing feedback API và history retry  
**Status:** `TODO`  
**Goal:** Request/store/read schema-validated feedback, preserving user answer and score through failure.  
**Suggested model:** GPT-6 Astra  
**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay trong danh sách. Nếu vượt khoảng 2 giờ hoặc phạm vi này, tách task trước khi làm tiếp.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/spec.md](../docs/spec.md) FR-ASM-11–15; AC-17/35
- [docs/api-contract.md](../docs/api-contract.md) Feedback/CONSENT
- [docs/security-review.md](../docs/security-review.md) T-20/24

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T047](t047-quiz-autosave-api.md)
- [T016](t016-dispatch-fence.md)
- [T034](t034-quiz-schema.md)
- [T014](t014-operations-idempotency.md)
- [T017](t017-typed-api-client.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

- `backend/migrations/versions/0011_feedback.py`
- `backend/app/application/feedback.py`
- `backend/app/http/feedback.py`
- `backend/tests/test_feedback.py`
- `backend/app/main.py`

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- Read canonical answerRevision, allowlisted rubric; timeout30s, user action/consent/admission. REQUESTED/VALIDATED/FAILED persisted; failed retry fresh idempotency key + retryOfOperationId, same answer. Safe error categories, redacted operation provenance, no answer payload in logs. Đăng ký đúng route/service vào app factory; TestClient và OpenAPI export dùng app factory production, không app test riêng bỏ security guards.
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [ ] Valid feedback linked answer/attempt/question/provider/model/prompt, independently paginated.
- [ ] Failures persist FAILED before safe response; old key replays failure, fresh authorized retry one dispatch.
- [ ] User selfScore unaffected; changed answer or policy blocks stale request; no secret/raw provider in logs.

## Test cases

1. AC-17/35, malformed JSON/auth/quota/timeout; history reload.
2. Wrong membership/rubric/revision, revoke barrier and fresh retry key.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
python -m pytest backend/tests/test_feedback.py -q
npm run test:contract
```

## Expected output

- Valid feedback linked answer/attempt/question/provider/model/prompt, independently paginated.
- Focused commands đạt kết quả/exit code ghi trong criteria; negative probe phải fail đúng reason. Documentation tasks có conformance report thay cho application-test pass.
- Evidence ghi command, exit code, môi trường và artifact. Thiếu Windows/browser/provider environment là PENDING; không hoàn tất gate thiếu evidence.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Implementation handoff, 11/10/2026 (supersedes preflight status)

Owner approved the minimum inline `writing-feedback-v1` prompt and strict provider
schema. Source is implemented within the five approved implementation files. T049
stays TODO pending Host verification and integration approval; no commit or push.

The service reads canonical SQLite answers, validates resource/revision/rubric/retry
identity, and shares T016 admission/consent and T014 operation receipts. The dispatch
boundary rechecks answer revision after bridge preflight. Identical replay returns
its durable receipt without inference. Confirmed failures require a fresh key and
explicit same-answer retry identity; concurrent owners and UNKNOWN outcomes block
new inference. No background retry, fallback provider or new credential path exists.

The approved schema permits only `summaryVi` and exactly one comment for each
`TARGET_WORD_USAGE`, `GRAMMAR`, `CLARITY`. It rejects extra fields, scores, duplicate
JSON keys, missing fields, malformed JSON, nonblank/size violations and unsafe text.
Validated feedback and success receipts commit together. Failures retain redacted
categories; startup reconciles unfinished REQUESTED records with recovered UNKNOWN
operations. Timeout/cancellation retain cleanup tasks through app shutdown.

Learning answer content, selfScore, QuizResult and SRS are read-only. Tests use the
production factory/security boundaries, temporary SQLite and fake bridge transport.
No real inference or sensitive-content diagnostic logging is introduced.

Migration: verified original single head `0010_quiz_answer_receipts`; created
`0011_feedback.py` with that predecessor. Existing migrations are byte-unchanged.
Upgrade tests retain populated quiz answers/results, SRS cards/events and operations,
check integrity/foreign keys and repeat upgrade safely. New sole head: `0011_feedback`.
Downgrade deliberately refuses destructive history removal.

### Verification classification

The preflight table below remains historical evidence. Current repository Ruff has
66 inherited findings; current formatter has 37 inherited files; current Mypy has
28 inherited errors in 14 files (89 sources, formerly 85). No suppression or
unrelated formatting was added. New files pass scoped Ruff/format and scoped Mypy.
`main.py` formatter differences are only the two pre-existing expressions; its
pre-existing E501 remains. These inherited failures block acceptance.

Generated OpenAPI/DTO files are intentionally untouched. Production OpenAPI route
and feedback-schema assertions are covered locally; Host must generate/reconcile
artifacts and verify complete contract compatibility. The old T016/T047 migration
head assertions also require Host-owned reconciliation, without altering history.

Architecture is PENDING: `depcruise` absent (exit 127). Coverage gate is PENDING:
missing `htmlcov/frontend/lcov.info` (exit 2). Task gate stops at inherited formatter
failures (exit 1). Security secrets reports two untriaged findings in untouched
SavePreview.tsx (exit 1); Semgrep version and OSV execution are unavailable (exit 2).
No missing skill/tool was installed or upgraded.

### Current verification table

| Command | Exit | Outcome |
|---|---:|---|
| `python -m pytest backend/tests/test_feedback.py -q` | 0 | 51 passed in 47.07s; fake providers only. |
| `python -m ruff check .` | 1 | 66 inherited findings; no T049-file findings. |
| `python -m ruff format --check .` | 1 | Same 37 inherited files. |
| `python -m mypy backend` | 1 | Same 28 inherited errors in 14 files. |
| `python -m mypy backend/app/application/feedback.py backend/app/http/feedback.py backend/migrations/versions/0011_feedback.py backend/tests/test_feedback.py --follow-imports=silent` | 0 | Four scoped files pass; full-repository failures remain. |
| `python -m ruff check` / `python -m ruff format --check` on four new files | 0 | All scoped checks pass. |
| `python -m pytest backend/tests/test_quiz_answers.py backend/tests/test_ai_admission.py backend/tests/test_operations.py backend/tests/test_quiz_snapshot.py backend/tests/test_bridge.py backend/tests/test_quiz_creation.py -q --no-cov` | 1 | 329 passed, 7 failed; five historical head assertions and two quiz-creation checks (classification below). |
| `npm run test:contract` | 1 | 62 failed, 16 passed; baseline was 61/17. Introduced route/schema drift awaits Host-generated artifacts; inherited AJV unavailable. |
| `npm run architecture:check` | 127 | Missing depcruise; PENDING. |
| `npm run check:task` | 1 | Stops at inherited formatting failure. |
| `npm run coverage:check` | 2 | Missing frontend report; PENDING. Focused service line coverage 93.97%, HTTP 81.33%, migration 92.86%; not full-suite acceptance. |
| `npm run security:secrets` | 1 | Same two untouched frontend findings; untriaged. |
| `npm run security:code` / `npm run security:deps` | 2 | Semgrep version / OSV execution unavailable; PENDING. |
| `python -m alembic heads` / `python -m alembic history` | 0 | Single head 0011, predecessor 0010; focused migration test passes. |
| Baseline HEAD: targeted quiz-creation commit-deadline and production-wiring tests (`python -m pytest ... -q --no-cov`) | 1 | Both identical failures reproduced; inherited. |
| Invert criteria guard, run positive schema test, restore | 1 expected | Test fails under mutation; restored positive test passes (exit 0). |
| `git diff --check` | 0 | No whitespace defects. |

Initial parser RED exited 2 (absent module); initial HTTP RED exited 1 (405).
Exploratory fixture mistakes were corrected; final 51 cases pass. Buffered terminal
runs that produced no output were interrupted (exit 130) and rerun with a PTY;
no passing result is inferred from those interrupted executions.

Four head assertions became stale through the approved new migration (T047 one, T034
three); T016 already expected obsolete 0007 before T049. Those out-of-scope tests
remain untouched. The two remaining quiz-creation failures were reproduced against an untouched HEAD
export in `/tmp/t049-baseline`: commit-deadline and sources-route expectations both
fail identically (2 failed, exit 1). They are inherited, not changed here.

### Review and residual risk

Applied all requested installed skills, documentation-and-adrs and unslop. RED tests
first rejected absent parser/route, followed by GREEN implementation and refactor.
Final code-review-and-quality and Ponytail review found no remaining confirmed
in-scope critical defect. Host acceptance remains blocked by the recorded gates.
The review traced canonical answer, admission,
receipt persistence, cancellation and shutdown under the one-user local-app model.
Read-only independent review identified shutdown drain cleanup; fixed in scope with
regression coverage. Cross-model external review was offered but not performed.

The bridge port conflates HTTP 429 with uncertain unavailable transport. Feedback
conservatively preserves UNKNOWN, preventing unsafe quota retries. A distinct
confirmed quota retry requires future bridge-port authorization; no exception-text
parsing was introduced. Real provider behavior, Windows runtime, complete coverage,
security scans and generated-contract acceptance remain unverified.

```text
TASK_ID: T049
MODEL: GPT-6.1 Sol (owner-requested label)
REASONING: MEDIUM (owner-requested)
EXECUTION_MODE: STANDALONE_CODEX_CLI
PONYTAIL_MODE: FULL
BRANCH: feature/t049-writing-feedback-api
BASE_SHA: 70105f4de49b84f84cfb0b408c69a7e5823d1792
HEAD_SHA: 70105f4de49b84f84cfb0b408c69a7e5823d1792
STATUS: IMPLEMENTED
SKILLS_INVOKED: ponytail FULL, incremental-implementation, test-driven-development,
  api-and-interface-design, security-and-hardening, doubt-driven-development,
  deprecation-and-migration, source-driven-development, code-review-and-quality,
  git-workflow-and-versioning, ponytail-review; documentation-and-adrs, unslop
SKILLS_APPLIED: inspection, RED/GREEN/refactor, boundary validation, safe migration,
  existing service reuse, failure/retry tests, final review and evidence bookkeeping
MIGRATION_HEAD_FOUND: 0010_quiz_answer_receipts before edits; 0011_feedback afterward
MIGRATION_PATH_DECISION: approved 0011_feedback.py; down_revision 0010_quiz_answer_receipts
FILES_CREATED: backend/app/application/feedback.py, backend/app/http/feedback.py,
  backend/migrations/versions/0011_feedback.py, backend/tests/test_feedback.py
FILES_MODIFIED: backend/app/main.py, tasks/t049-writing-feedback-api.md,
  tasks/todo.md, docs/changelogs.md
FILES_INTENTIONALLY_UNTOUCHED: prior migrations, T048, frontend, generated artifacts,
  admission/consent/ledger/bridge implementations, manifests, locks, thresholds, other tasks
AI_ADMISSION_AND_CONSENT: shared T016; default-deny and dispatch-boundary revocation retained
IDEMPOTENCY_AND_RETRY: shared T014; replay, explicit fresh-key confirmed-failure retry,
  same-answer identity, concurrent and UNKNOWN duplicate blocking
ANSWER_AND_SCORE_PRESERVATION: no answer/selfScore/QuizResult/SRS writes; tested populated history
FEEDBACK_SCHEMA_VALIDATION: strict versioned comments-only schema; positive/negative tests
TESTS_ADDED: 51 collected cases covering requested boundaries; exact outcomes below
TEST_COMMANDS_AND_EXIT_CODES: see current verification table
CONTRACT_STATUS: local production OpenAPI assertions; Host regeneration/full validation pending
REVIEW_FINDINGS: shutdown cleanup corrected; inherited gates and head assertions remain blockers
KNOWN_RISKS: quota ambiguity conservatively UNKNOWN; full gates/provider/Windows unverified
NEXT_ACTION: Host verification, contract generation and authorized inherited-gate reconciliation;
  await integration approval; keep task TODO
```

Suggested future commit: `feat(T049): persist validated writing feedback with safe retries`.

## Standalone preflight handoff, 11/10/2026

T049 remains TODO. Session status is BLOCKED_SCOPE; application implementation has
not started. No commit, push, merge, dependency installation or real inference occurred.

- Repository/worktree: `khanhpn308/english_web`, `/home/khanh/projects/vocabularies-t049-sol`.
- Branch: `feature/t049-writing-feedback-api`.
- Base and unchanged HEAD: `70105f4de49b84f84cfb0b408c69a7e5823d1792`.
- Initial working tree was clean. Local main is `a7d1e3125975f411153525874fa622361f48ac00`;
  `git rev-list --left-right --count main...HEAD` returned `15 0`. No merge/rebase was attempted.
- `python -m alembic heads` and `python -m alembic history` both exited 0.
  Single head is `0010_quiz_answer_receipts`, following `0009_review_diagnostics`,
  which follows `0008_quiz`. The owner's conditional correction is satisfied;
  the allowlist above now names `0011_feedback.py`. That migration is not yet created.

### Scope and verification blockers

1. No approved `writing-feedback-v1` prompt or provider schema exists in this checkout.
   The name occurs in the response example in `docs/api-contract.md`; the executable
   prompt directory contains only lookup and quiz templates. The response example
   does not define the full strict provider schema. Owner clarification is pending
   on supplying the approved definition or authorizing it inside `application/feedback.py`.
2. Adding 0011 would fail `backend/tests/test_quiz_answers.py:393`, which expects
   `database.initialize()` to return latest revision `0010_quiz_answer_receipts`.
   Host reconciliation or a narrow test-allowlist extension is needed. Preserve its
   historical predecessor check and existing-data assertions; do not rewrite migrations.
3. Existing quality/security gates fail before any application edits. Fixing them
   reaches prohibited paths. Their results below are baseline failures, not acceptance
   evidence for T049. Host must reconcile them under separate authorization.

The bridge uses `BridgeUnavailableError` for both HTTP 429 and uncertain transport
failures. Conservative UNKNOWN handling can prevent duplicate inference without
adapter changes. A distinct retryable quota outcome is not currently exposed by the
port; do not parse exception text or HTTPX internals in the feedback service.

### Actual commands and outcomes

Linux/WSL, Python 3.12.3. Existing fakes and temporary SQLite only. No test was modified.

| Command | Exit | Outcome |
|---|---:|---|
| `python -m pytest backend/tests/test_feedback.py -q` | 4 | File absent; no tests ran. T049 tests are PENDING. |
| `python -m pytest backend/tests/test_quiz_answers.py backend/tests/test_ai_admission.py backend/tests/test_operations.py backend/tests/test_quiz_snapshot.py backend/tests/test_bridge.py -q` | 1 | 240 passed, 1 failed. T016 migration test expects obsolete head `0007_source_journal`. |
| `python -m ruff check .` | 1 | 66 baseline findings. |
| `python -m ruff format --check .` | 1 | 37 baseline files would be reformatted. |
| `python -m mypy backend` | 1 | 28 errors in 14 baseline files. |
| `npm run architecture:check` | 127 | `depcruise` absent; PENDING. |
| `npm run check:task` | 1 | Stops at existing formatter failure; downstream coverage/security stages not reached. |
| `npm run security:secrets` | 1 | Two scanner findings in untouched `frontend/src/features/lookup/SavePreview.tsx`; not triaged, no values copied. |
| `npm run security:code` | 2 | Semgrep version check failed; PENDING. |
| `npm run security:deps` | 2 | OSV execution failed; PENDING. |
| `npm run test:contract` | 1 | 61 failed, 17 passed; baseline contract verification is not green. AJV dependency is absent. |
| `node -e "require('@redocly/ajv/dist/2020')"` | 1 | `MODULE_NOT_FOUND`; confirms unavailable schema-validator dependency. |
| `git diff --check` | 0 | Bookkeeping diff has no whitespace errors. |

Coverage from focused baseline tests is not a full-suite coverage acceptance result.
Feedback migration upgrade, HTTP behavior, deadlines, retry history, restart recovery,
privacy tests and all twenty requested T049 cases remain PENDING.

### Skills and review

Loaded the installed Ponytail FULL and Ponytail review skills; agent-skills 0.6.12
incremental-implementation, test-driven-development, api-and-interface-design,
security-and-hardening, doubt-driven-development, deprecation-and-migration,
source-driven-development, code-review-and-quality, git-workflow-and-versioning
and documentation-and-adrs; also unslop. Version 0.6.12 resolves AGENT.md's stale
documentation skill location. Applied these to scope/contract inspection, migration
lineage, existing verification commands, privacy, bookkeeping and read-only review.
No implementation RED/GREEN cycle or framework implementation is claimed.

A fresh-context read-only reviewer confirmed blockers 1 and 2, and corrected an
overstatement that quota handling necessarily required bridge scope expansion.
Cross-model review was offered; no external CLI was invoked. Final code-quality and
Ponytail review are limited to the bookkeeping diff and connected preflight evidence.

### Handoff fields

```text
TASK_ID: T049
MODEL: GPT-6.1 Sol (owner-requested label; runtime model not independently verified)
REASONING: MEDIUM (owner-requested)
EXECUTION_MODE: STANDALONE_CODEX_CLI
PONYTAIL_MODE: FULL
BRANCH: feature/t049-writing-feedback-api
BASE_SHA: 70105f4de49b84f84cfb0b408c69a7e5823d1792
HEAD_SHA: 70105f4de49b84f84cfb0b408c69a7e5823d1792
STATUS: BLOCKED_SCOPE
SKILLS_INVOKED: all requested identifiers resolved/read locally; documentation-and-adrs, unslop
SKILLS_APPLIED: preflight, scope/contract/privacy review and bookkeeping only; see Skills and review
MIGRATION_HEAD_FOUND: 0010_quiz_answer_receipts
MIGRATION_PATH_DECISION: approved correction to 0011_feedback.py; creation blocked pending clarification
FILES_CREATED: none
FILES_MODIFIED: tasks/t049-writing-feedback-api.md, tasks/todo.md, docs/changelogs.md
FILES_INTENTIONALLY_UNTOUCHED: all application code, tests, migrations, frontend,
  generated contracts/DTOs, consent/admission/ledger/bridge, manifests and quality thresholds
AI_ADMISSION_AND_CONSENT: existing T016 inspected, unchanged; no dispatch
IDEMPOTENCY_AND_RETRY: existing T014 inspected, unchanged; T049 not implemented
ANSWER_AND_SCORE_PRESERVATION: no learning-data writes or application edits
FEEDBACK_SCHEMA_VALIDATION: blocked on approved definition
TESTS_ADDED: none
TEST_COMMANDS_AND_EXIT_CODES: exact table above
CONTRACT_STATUS: T049 generation/compatibility PENDING; Host owns generated artifacts
REVIEW_FINDINGS: missing approved definition, migration test scope conflict,
  inherited failing gates; no confirmed defect in bookkeeping change
KNOWN_RISKS: T049 remains unavailable; baseline gates and secret findings unresolved
NEXT_ACTION: Host/owner supplies or approves prompt/schema, reconciles historical-head
  tests and baseline gates, then resume T049 within the approved implementation scope
```

## Risk

- **Level:** `Critical`.
- Sai boundary có thể gửi dữ liệu/cost không được phép hoặc mất lịch sử học.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- Feedback auto-scores or retries without admission, or persist failures can swallow user score → dừng.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`feat(T049): writing feedback api và history retry`

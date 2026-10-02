# T059: Pure quiz scoring và weakest-rating oracle

**Task ID:** `T059`  
**Title:** Pure quiz scoring và weakest-rating oracle  
**Status:** `DONE`
**Goal:** Chấm objective/self-score và map grouped result sang SRS rating deterministic.  
**Suggested model:** GPT-6 Astra  
**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay trong danh sách. Nếu vượt khoảng 2 giờ hoặc phạm vi này, tách task trước khi làm tiếp.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/spec.md](../docs/spec.md) FR-ASM-05–08; AC-16/19/30
- [docs/adr/0004-v1-product-policy-and-operational-baseline.md](../docs/adr/0004-v1-product-policy-and-operational-baseline.md) quiz
- [docs/adr/0005-contract-clarifications.md](../docs/adr/0005-contract-clarifications.md) planned — planned output của dependency; phải tồn tại trước khi dùng

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T031](t031-review-schema.md)
- [T013](t013-contract-conformance.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

- `backend/app/assessment/scoring.py`
- `backend/tests/test_quiz_scoring.py`

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- Pure functions no persistence/UI/AI; NFC/trim/collapse whitespace/casefold; strict punctuation/spelling; only snapshot explicit alternatives. Blank/pending selfscore behavior exact T013. Weakest ordinal AGAIN<HARD<GOOD<EASY; no adaptive algorithm.
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [x] MCQ/cloze fixtures exact and repeated score idempotent; no language model calls.
- [x] Writing0–4 mapping defined, score owner preserved; blank not fabricated0.
- [x] Multiple question results for form yield one weakest rating under contract.

## Test cases

1. robust/ROBUST/spaces/robuts punctuation and NFC variants.
2. Writing0..4/null, mixed correct+wrong/selfscore, invalid schema.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
python -m pytest backend/tests/test_quiz_scoring.py -q
```

## Completion checkpoint — 02/10/2026 (Asia/Bangkok)

- **Outcome:** DONE. Pure domain quiz scoring and weakest-rating oracle fully implemented and verified under ADR-0005 C013-03, including remediation of audited P1 answer-ownership defect.
- **TDD History:**
  - Initial implementation: RED state recorded on missing module (`ModuleNotFoundError: No module named 'backend.app.assessment'`, pytest exit 2); GREEN state with 38 focused unit tests passing in 0.38s and 100% line & branch coverage on `backend/app/assessment/scoring.py`.
  - P1 defect remediation:
    - Defect: Single-question scorers (`score_mcq`, `score_cloze`, `score_writing`) and aggregate `score_quiz` ignored `AnswerInput.question_id`, allowing mismatched or swapped payloads across question keys without validation.
    - RED run: `python -m pytest backend/tests/test_quiz_scoring.py -q` exited with code 1 (6 failed, 39 passed in 0.58s), failing on foreign IDs and swapped/reused writing payloads.
    - Fix: In `score_mcq`, `score_cloze`, and `score_writing`, enforced `answer.question_id == question.id` before evaluating answer/self_score (including blank/pending cases), raising `QuizScoringError` with identity-specific diagnostic. In `score_quiz`, validated all mapping keys against `ans.question_id`.
    - GREEN run: `python -m pytest backend/tests/test_quiz_scoring.py -q` exited with code 0 (45 passed in 0.23s), retaining 100% line & branch coverage on `scoring.py` (242 statements, 80 branches).
- **Scoring Oracles:**
  - MCQ compares option ID exactly against immutable snapshot correct option ID; literal empty string/None yields outcome BLANK, isCorrect=false, rating AGAIN; option outside snapshot options raises `QuizScoringError`; objective selfScore rejected; foreign AnswerInput question_id rejected with `QuizScoringError`.
  - Cloze normalizes using NFC, strict ASCII whitespace trimming/collapsing, and Unicode casefold (`normalize_cloze_text`), preserving strict punctuation, spelling, accents, and non-ASCII whitespace; empty/ASCII-whitespace yields outcome BLANK, isCorrect=false, rating AGAIN; foreign AnswerInput question_id rejected with `QuizScoringError`.
  - Writing strictly maps integer selfScore 0..4 (0/1->AGAIN, 2->HARD, 3->GOOD, 4->EASY); outcome SELF_SCORED; pending null raises `PendingSelfScoreError` preventing terminal scoring; blank text allowed only with explicit score 0; blank text with positive score rejected; foreign AnswerInput question_id rejected with `QuizScoringError`.
  - Aggregate validation: Mapping keys must strictly match `AnswerInput.question_id`. Swapped or reused inputs across keys fail immediately with `QuizScoringError`. Sequence and mapping inputs produce identical objective scores and weakest ratings.
  - Weakest rating oracle deterministic: `AGAIN < HARD < GOOD < EASY`, grouping question results by `wordFormId` invariant of question order.
  - Objective scores: calculates `mcq` and `cloze` total, attempted, correct, and accuracy (null if attempted is 0).
  - Purity & idempotency: inputs are not mutated and repeated calls return identical results; zero language model calls or external network dependencies.

### Observed verification results

| Command | Exit | Observed result |
|---|---:|---|
| `python -m pytest backend/tests/test_quiz_scoring.py -q` | 0 | 45 passed in 0.23s; 100% coverage on `scoring.py` (242 stmts, 80 branches) |
| `python -m pytest backend/tests/test_srs.py -q` | 0 | 60 passed in 4.22s (dependency verification) |
| `python -m mypy backend/app/review` | 0 | Success: no issues found in 2 source files |
| `python -m mypy backend` | 0 | Success: no issues found in 45 source files |
| `python -m ruff check .` | 0 | All checks passed |
| `python -m ruff format --check .` | 0 | 177 files already formatted |
| `npm run architecture:check` | 0 | 7 backend contracts kept, 40 tests passed in 21.63s |
| `npm run security:secrets` | 0 | Pinned Gitleaks 8.30.1: 0 findings; report: htmlcov/security/gitleaks.json |
| `npm run security:code` | 0 | Pinned Semgrep 1.178.0: 0 findings; report: htmlcov/security/semgrep.json |
| `npm run security:deps` | 0 | Pinned OSV-Scanner 2.6.0: 0 findings; report: htmlcov/security/osv-scanner.json |
| `npm run check:task` | 0 | Complete gate passed: 749 Python tests in 223.82s, 38 frontend vitest tests, 40 architecture tests, changed coverage 100.00%, total 92.74%, 0 findings on secrets/code/deps |
| `git diff --check` | 0 | Clean diff without whitespace issues |
| `rg -n "HARD|AC-14|sourceId|session|explanationVi|rubric|SUBMITTED" docs/spec.md docs/api-contract.md docs/adr/0005-contract-clarifications.md` | 0 | All contract anchors confirmed present across spec, contract, and ADR-0005 |

- **Scope & handoff:** Exactly two implementation/test files updated (`backend/app/assessment/scoring.py`, `backend/tests/test_quiz_scoring.py`) and three bookkeeping files updated. Intentionally untouched: persistence models, database migrations, HTTP endpoints, frontend code, and real vocabulary data. No threshold changes or test weakening. Downstream tasks: T034 (quiz snapshot schema) and T035 (quiz creation API).

## Expected output

- MCQ/cloze fixtures exact and repeated score idempotent; no language model calls.
- Focused commands đạt kết quả/exit code ghi trong criteria; negative probe phải fail đúng reason. Documentation tasks có conformance report thay cho application-test pass.
- Evidence ghi command, exit code, môi trường và artifact. Thiếu Windows/browser/provider environment là PENDING; không hoàn tất gate thiếu evidence.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Risk

- **Level:** `High`.
- Sai contract/concurrency/persistence có thể làm mất dữ liệu, ghi sai tiến độ hoặc tạo kết luận kiểm chứng sai.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- Rubric/blank/terminal policy missing from T013 → dừng.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`test(T059): pure quiz scoring và weakest-rating oracle`

## Independent re-audit and integration verification — 02/10/2026 (Asia/Bangkok)

- **Verdict:** PASS after the owner requested direct re-audit and merge. Historical
  run `202610020538470149160000-77174ceb` remains FAILED with every artifact and
  its uncommitted worktree unchanged; no Worker or provider inference was rerun.
  New structured audit evidence lives separately at
  `.agent-runs/T059/manual-audit-20261002-b47d599/` in the primary repository.
- **Candidate:** `integration/t059-manual-audit`, worktree
  `../vocabularies-integrate-t059-audit`, frozen local main base
  `b47d599bc295230f22822de07064e875780c65e8`. The two source/test files are
  byte-identical to the verified original Worker snapshot. Shared todo/changelog
  preserve cumulative T076 and T059 entries. Product checkpoints remain unchanged.
- **Independent review:** All three original criteria pass; findings,
  scope_violations and required_fixes are empty. Supplied Worker claims were
  checked against source, contract, fresh executable evidence and original
  artifact digests. No unresolved task-specific defect or test weakening found.

| Invariant | Contract evidence | Independent check | Mechanism / result |
|---|---|---|---|
| Objective normalization/scoring and repeated-call purity | ADR-0005 C013-03; criterion1 | 45 scoring tests, 45 additional mixed-answer/score combinations and input-copy assertions | Exact MCQ ID, NFC/ASCII/casefold cloze, explicit alternatives, no I/O; PASS |
| Score owner and blank/pending policy | C013-03; criterion2 | Foreign/swapped/reused inputs, null, bool/float/range and blank negatives | Validate question ownership first; preserve explicit score; pending never becomes zero; PASS |
| One weakest rating per form | ADR-0004/0005; criterion3 | Golden five-question fixture; 270 additional question permutations | Validated ordinal minimum grouped by form; PASS |
| Safe integration / no stale evidence | CONSTRAINTS; repository Git rules | Original artifact hashes/source snapshot and frozen candidate checked | Exactly five task files; implementation unchanged during checks; PASS |

| Fresh command | Exit | Result |
|---|---:|---|
| `python -m pytest backend/tests/test_quiz_scoring.py backend/tests/test_srs.py -q --no-cov` on original worktree | 0 | 105 passed, 10.99s |
| Same focused command on integration candidate | 0 | 105 passed, 3.86s |
| `python -m ruff check .` | 0 | All checks passed |
| `python -m ruff format --check .` | 0 | 178 files formatted |
| `python -m mypy backend tools/orchestrator` | 0 | No issues in 49 source files |
| `python -m alembic heads` | 0 | One head: 0006_ai_admission |
| `npm ci` | 0 | Existing lock installed; manifest/lock unchanged |
| `npm run check:task` after SOURCE FREEZE | 0 | 763 Python tests in 408.89s, 38 frontend tests, 40 architecture tests in 46.78s; seven import contracts kept |
| Coverage/security inside aggregate gate | 0 | Scoring 100% line/branch; changed 100%, total 92.78%; Gitleaks/Semgrep/OSV zero findings |
| `git diff --check` | 0 | Clean |

Only task bookkeeping records final evidence after the aggregate gate; code/tests
remain frozen. Existing two AppShell fast-refresh warnings are not errors.
Intentionally unchanged: all other application/tests, migrations, HTTP/API and
frontend/generated artifacts, orchestrator/config, manifests/locks, thresholds,
user data/credentials and historical run files. No real inference or network AI.
Promotion is authorized only under the repository integration lock with a clean,
unchanged main and ff-only to the verified candidate; no push. T059 is complete;
T035/T048 still need their other dependencies, and CP14 is not marked complete.

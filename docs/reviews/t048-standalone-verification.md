# T048 standalone implementation evidence

Date: 11/10/2026, Asia/Bangkok. Execution: standalone Codex CLI on Ubuntu/WSL.
Requested configuration: GPT-6.1 Sol, HIGH reasoning, Ponytail FULL.

## Scope and checkpoint

- Branch: `feature/t048-quiz-submit-api`.
- Base and HEAD: `70105f4de49b84f84cfb0b408c69a7e5823d1792`.
- Initial worktree was clean. Local `main` was 15 commits ahead, with no commits unique to this branch. No merge, rebase, commit, push or PR occurred.
- Code is implemented. Final acceptance is **BLOCKED_VERIFICATION**. T048 and CP16 remain unchecked; no DONE status is authorized.
- Created `backend/app/application/submit_quiz.py`, `backend/app/http/quiz_submissions.py` and `backend/tests/test_quiz_submission.py`. Modified `backend/app/main.py` only to register and manage the service/router lifecycle.
- Owner explicitly extended scope to `contracts/openapi.json` and `frontend/src/shared/api/generated.ts`. Both were produced by `npm run export:contract`, without manual edits. OpenAPI adds only the submission route and `SubmissionRequest`; removing those additions produces the exact HEAD artifact. TypeScript adds the matching path, request and operation. T049 contract reconciliation belongs to integration.
- Bookkeeping: task card, unchecked todo entry, changelog and this redacted report.

## Implemented behavior

`POST /api/v1/quiz-attempts/{attemptId}/submissions` accepts the aggregate
`submissionRevision` and required `Idempotency-Key`, returning `201 QuizResult`.
The production app retains its existing session, Origin, request-size and telemetry
guards. The route rejects query parameters and duplicate idempotency headers.

The service reuses T059's scorer and question adapter. MCQ/cloze score locally;
writing requires the saved explicit integer 0–4. Missing/null writing scores and
positive scores for blank writing fail validation. The scorer supplies one weakest
rating per form. Existing review persistence advances each eligible card once;
absent cards and forms with no valid source receive `SKIPPED_INACTIVE`.

T014 durably claims the intent first. Its `complete(local_write=...)` callback
holds SQLite's `BEGIN IMMEDIATE` writer lock while validating terminal state and
revision, scoring, storing grouped review events/schedules and terminal quiz data.
The operation success receipt commits in that same outer transaction. No result
is acknowledged before commit. Reads after commit establish durable success.
Read failures never relabel an already committed operation as FAILED.

The original result is the immutable receipt, identified by the attempt and its
submission operation owner. Same-key replay precedes revision/terminal checks;
changed intent returns `IDEMPOTENCY_KEY_REUSED`, pending intent returns
`IDEMPOTENCY_IN_FLIGHT`, and a fresh terminal intent returns `ALREADY_SUBMITTED`.
Concurrent fresh intents serialize under SQLite's writer lock.

## Test-first and review evidence

- Initial RED: focused test failed with 405, since the submission route was absent. Exit 1, one failure, 19.31 seconds.
- First GREEN: one complete grouped-submission/replay test passed. Exit 0, 4.95 seconds.
- Expanded checkpoint: 43 tests passed. Exit 0, 31.59 seconds.
- Independent review identified transient DBAPI read failures being redacted by the repository into `QUIZ_RESTORE_REQUIRED`. Two additional RED regressions reproduced misleading 409 responses before/after commit. Exit 1, two failures, 3.29 seconds.
- Corrected only the application service's error mapping. It examines the exception type retained in `__context__`, without exposing SQL or stored content, to return `503 STORAGE_BUSY` and an operation reference. Genuine damaged snapshots still return typed restoration guidance.
- Two new fixture errors were corrected: globally unique question IDs for a second attempt and deliberate corruption of a disposable database using the existing corruption-test pattern. No production guard or existing assertion was removed.
- Final focused run: **49 passed**, exit 0, 57.57 seconds. It includes MCQ correct/incorrect/saved and unsaved blank; cloze spelling/case/whitespace/blank; writing 0–4/null/missing/blank; weakest grouping; one event per form; inactive/absent cards and alternate valid sources; revision/key conflicts; concurrent same/different keys; controlled in-flight duplication; failures during event, schedule, terminal and receipt writes; ambiguous commit; receipt read failures; lost HTTP response and restart/rebootstrap; private answer keys; production security guards; typed OpenAPI and corruption recovery.
- Focused coverage: service 88 statements, 7 missed, 90% combined line/branch coverage; HTTP adapter 43 statements, 4 missed, 91% combined coverage. Each exceeds the 80% changed-code floor. This focused run is not evidence for the repository total-coverage ratchet.
- Mutation probe on a temporary copy inverted the aggregate revision check. The revision/key regression failed on the stale request, exit 1, one failure, 3.89 seconds. Workspace code was never mutated by this probe.
- A fresh-context reviewer inspected transaction design, connected persistence/ledger/review code and the completed error-handling fix. No remaining concrete T048 finding. The owner chose to skip cross-model review.

## Commands and outcomes

Commands ran with Python 3.12.3 from the existing shared project venv. Ruff 0.16.9,
Mypy 2.3.1, SQLAlchemy 2.1.1, FastAPI 0.141.1 and Pydantic 2.13.5 match the lock.
Node was v22.23.2 and npm 12.0.2. No lockfile, dependency or global Codex setting
was changed. `npm ci --ignore-scripts` installed the existing frontend lock.

| Command | Exit | Actual result |
|---|---:|---|
| `npm ci --ignore-scripts` | 0 | 329 packages installed; native audit reported zero vulnerabilities |
| `python -m pytest backend/tests/test_quiz_submission.py -q` | 0 | 49 passed, 57.57s |
| `python -m pytest backend/tests/test_quiz_answers.py backend/tests/test_quiz_scoring.py backend/tests/test_review_api.py backend/tests/test_srs.py backend/tests/test_operations.py backend/tests/test_quiz_snapshot.py -q --no-cov` | 1 | 414 passed; one inherited migration-head assertion failed, 101.37s |
| `npm run export:contract` | 0 | Generated the two approved files; additions only |
| `npm run test:contract` before regeneration | 1 | 73 passed, five failures, including expected generated drift |
| `npm run test:contract` after regeneration | 1 | 74 passed; four inherited contract-test failures, 152.11s |
| `python -m ruff check .` | 1 | 66 inherited diagnostics; clean HEAD snapshot also reports 66 |
| `python -m ruff format --check .` | 1 | 37 inherited files require formatting; clean HEAD also reports 37 |
| Ruff lint/format on the three new T048 files | 0 | All checks passed; all three formatted |
| `python -m mypy backend` | 1 | 28 inherited errors in 14 files; clean HEAD has the same 28 |
| `npm run architecture:check` | 4 | Frontend stops on four missing testing-library imports |
| `npm run architecture:backend` | 1 | Six contracts kept; inherited application/enrichment cycle breaks the seventh, also reproduced at HEAD |
| `python -m pytest scripts/tests/test_architecture_gate.py -q --no-cov` | 1 | 38 passed; real frontend/backend probes fail on those inherited issues |
| `npm run check:task` with pinned scanner paths | 1 | Stops at the inherited formatter gate; later steps are not counted as passed |
| `npm run security:secrets` with pinned Gitleaks | 1 | Inherited generic-api-key finding in `SavePreview.tsx`, in history and working tree; HEAD directory scan reproduces it at line 28 |
| `npm run security:code` with pinned Semgrep | 0 | Zero findings after normal escalation for its settings-directory access |
| `npm run security:deps` with pinned OSV scanner | 0 | Zero findings after normal network escalation |
| `git diff --check` | 0 | Clean |
| `python -m pytest -q -n 4` | 1 | 2,207 passed, 30 failed, 571.77s; all 49 T048 tests passed; failure classification below |
| Unchanged-HEAD probes for ten remaining full-suite failures, `python -m pytest <exact node IDs> -q --no-cov` | 1 | Nine failures reproduced; lookup deadline test passed; exact node IDs below |
| `python -m pytest backend/tests/test_lookups.py::test_provider_held_beyond_hard_overall_deadline -q --no-cov` | 0 | Also passes in the T048 worktree in isolation, 1.42s; full-run deadline failure remains unresolved |
| `npm run floor:check` | 0 | Clean |
| `npm run test:frontend:coverage` | 1 | Six suites failed/seven passed; four tests failed/295 passed/four inherited skips; unchanged frontend assertions, missing testing-library packages and sandboxed Chromium startup failures; no LCOV report produced |
| `npm run coverage:check` | 2 | SETUP_PENDING because `htmlcov/frontend/lcov.info` is missing; aggregate coverage acceptance remains PENDING |

Sandboxed TestClient startup hung in AnyIO's asyncio portal. The diagnostic run
timed out with exit 124; two earlier hanging runs were interrupted with exit 130.
They are not test results. The regression runs above completed through the normal
approved escalation mechanism. Semgrep and OSV first returned SETUP_FAILED, exit
2, inside the sandbox; only their completed escalated runs support scan results.

Baseline evidence was collected from a clean `git archive HEAD` under `/tmp`.
The four contract failures were reproduced with the same installed Node modules
via `NODE_PATH`, exit 1, four failed/nine passed. An earlier baseline contract
probe lacked Node modules and had 13 setup failures; it is not conformance evidence.
The inherited review-head assertion was reproduced separately at HEAD, exit 1.
Raw local command logs are under `/tmp/t048-verification`; this report keeps only
outcomes, file/rule names and synthetic test diagnostics.

## Full-suite failure classification

Sixteen of the thirty failures reproduce on unchanged HEAD: four contract tests,
two architecture probes, the review migration-head assertion and these nine tests:

```text
backend/tests/test_edit_word_form.py::test_shared_dates_and_unrelated_form_content_preserved
backend/tests/test_edit_word_form.py::test_strict_editable_allowlist[fields11]
backend/tests/test_ai_admission.py::test_upgrade_from_0005_preserves_data_and_one_head
backend/tests/test_quiz_creation.py::test_deadline_covers_processing_and_atomic_completion[commit]
backend/tests/test_quiz_creation.py::test_production_wiring_keeps_shared_admission_and_existing_routes
backend/tests/test_source_journal.py::test_migration_from_review_through_admission_preserves_all_seeded_rows
backend/tests/test_telemetry.py::test_production_concurrent_requests_and_exception_cleanup
backend/tests/test_telemetry.py::test_failing_sink_preserves_route_exception_and_success
backend/tests/test_telemetry.py::test_factory_preserves_routers_and_has_no_duplicate_telemetry
```

The unchanged-HEAD probe command listed those nine nodes plus
`backend/tests/test_lookups.py::test_provider_held_beyond_hard_overall_deadline`,
followed by `-q --no-cov`; it returned nine failures and one pass in 5.58 seconds.
Thirteen other full-suite failures are explicit native-Windows acceptance checks
in `backend/tests/windows/test_source_paths.py`, which fail closed on Linux.
The remaining lookup deadline test passed in isolation both at HEAD and in this
worktree, but failed under the full parallel run: its operation was FAILED rather
than the expected UNKNOWN. This timing-sensitive failure remains unresolved; it
is not classified as a proven inherited failure or a proven T048 regression.
No T048 test failed. Full Python line coverage is 90.57% (88% combined line/branch),
which does not substitute for the blocked aggregate/frontend coverage gate.

## Final change review

What this change does: it submits a locally scored quiz and advances each eligible
word form once. SQLite commits the result, state, schedules/events and success
receipt together, and subsequent reads/replays recover that committed result.

Ponytail review and code-review-and-quality checked the connected scorer,
repository, ledger, review primitive, production route wiring, security guards,
generated diff and synthetic failure/concurrency regressions. Expected load is
one local user with overlapping requests. The transient-storage classification
finding was corrected and retested; no remaining concrete T048 finding was found.
Source review passes. Repository acceptance remains BLOCKED_VERIFICATION.
The final source hashes match the verified implementation; no unrelated source,
threshold, policy or test was edited to address the inherited findings.

## Skills and handoff

Applied the installed Ponytail FULL and Ponytail review skills, unslop, and
`agent-skills` 0.6.12 instructions for incremental implementation, test-driven
development, API/interface design, security/hardening, doubt-driven development,
code review/quality, Git workflow/versioning and documentation/ADRs. The AGENT.md
documentation skill's stale 0.6.11 path was resolved to the installed 0.6.12 file.
No skills were installed. The user prohibition on commits overrides skill commit
preferences. Existing ADR-0005 already defines the implementation; no new ADR is
needed or authorized.

Intentionally untouched: existing scorer, autosave, operation ledger, review
primitives, persistence models/migrations, other application/tests, frontend
handwritten code, manifests/locks, specifications/ADRs, security policies,
quality thresholds, global Codex/T078, credentials and real vocabulary files.

Residual risks and next action: repository-wide conformance/security findings
require separate authorized work before acceptance. The full-run lookup deadline
failure also needs investigation. Windows filesystem and real
browser release evidence remain PENDING. Integration must reconcile main's newer
changes and T049's generated artifacts, then rerun the unchanged gates. No commit,
merge, push, PR or DONE action is authorized. Proposed future commit message:
`feat: submit quizzes and SRS updates in one durable transaction`.

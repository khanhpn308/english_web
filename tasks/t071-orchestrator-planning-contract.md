# T071: Preserve planning constraints and safely retry pre-worker failures

**Task ID:** `T071`
**Title:** Preserve planning constraints and safely retry pre-worker failures
**Status:** `IMPLEMENTATION_DONE_BASELINE_BLOCKED`
**Goal:** Supply an exact contract template, actionable diagnostics and an explicit retry command for proven pre-worker failures, preserving previous runs and worktrees.

## Context cần đọc

- `AGENTS.md`, `AGENT.md`, `CONSTRAINTS.md`
- `docs/orchestrator.md`, `docs/adr/0006-local-agent-orchestration.md`
- `tools/orchestrator/core.py`, `tools/orchestrator/workflow.py`, related tests
- T021 run `202610011453018489410000-4aa2c186`: task and plan artifacts (read-only)

## Dependencies

- T067
- T068

## Files được phép sửa

- `tools/orchestrator/core.py`
- `tools/orchestrator/workflow.py`
- `tools/orchestrator/__main__.py`
- `tests/orchestrator/test_workflow.py`

Common bookkeeping: this card, tasks/todo.md, docs/changelogs.md. Infrastructure documentation: docs/orchestrator.md. No other handwritten implementation files. The latest user request to rerun failed tasks authorizes the narrowly scoped CLI/retry extension, recorded before editing; earlier planning verification remains historical after this extension.

## Files không được sửa

- Product source/tests/cards, migrations, generated API/client, dependencies/locks, credentials and real vocabulary data.
- Existing run artifacts/state, task acceptance/verification constraints, security/privacy policy and quality thresholds.

## Acceptance criteria

- [x] Planning receives a literal contract template constructed from the frozen task/base/fix budget, with exact-copy and exact-path instructions.
- [x] Drift reports field names without leaking model text; altered constraints, glob paths and real human gates still block Worker/integration.
- [x] Synthetic provider tests prove template consumption, rejected drift, retained human gates and no real inference.
- [x] Explicit retry creates a fresh run/worktree from current local base, preserving old state/artifacts/worktrees; only verified unchanged pre-worker BLOCKED runs qualify.
- [x] Retry refuses human gates, source/history/artifact changes, active/implemented/integration runs and unmanaged worktrees; duplicate run attempts do not create misleading empty runs.

## Verification commands

```text
python -m pytest tests/orchestrator -q --no-cov
python -m ruff check tools/orchestrator tests/orchestrator
python -m mypy tools/orchestrator tests/orchestrator
npm run check:task
```

## Expected output

Record exact exit codes, baseline, RED/GREEN, source freeze and scope. Contract errors become actionable; this is not evidence that T021 satisfies Windows/privacy gates.

## Risk

- **Level:** High; immutable contract authority must not be normalized away.

## Stop conditions

- Preserve genuine human gates; do not rewrite saved plans/state to make an old BLOCKED run pass.
- Do not change product requirements, permit prohibited data access, weaken verification or call paid providers in tests.
- No remote Git, destructive reset or modification of active task worktrees.

## Commit message đề xuất

`fix(orchestrator): preserve task constraints and safely restart pre-worker runs`

## Planning-only evidence (historical snapshot, 01/10/2026, Asia/Bangkok)

Base: local main `b9530b97118131ffa4c266d47979a46550ef015d`.
Branch/worktree: `feature/task-t071-planning-contract`,
`/home/khanh/projects/vocabularies-t071-planning-contract`.

T021's real Plan rewrote objective/forbidden_scope/stop_conditions and supplied
glob forbidden paths. Original task/Plan/state artifacts remain unchanged. No
Worker ran in that failed run. The new prompt supplies literal constraints; validation
still rejects changed authority rather than silently normalizing model output.

| Invariant | RED / baseline | Mechanism | Focused result |
|---|---|---|---|
| Planner can copy exact original strings, including Unicode | Template missing; provider assertion failed | Host template shared with validator; exact-copy instructions | PASS |
| Drift is actionable without private text leakage | Generic error omitted three field names | Names-only comparison diagnostics | PASS |
| Unsafe forbidden paths remain rejected | Rejected, but generic error omitted field/index | Exact-path policy plus names/index-only diagnostic | PASS |
| Real human gates prevent Worker and integration | Existing behavior already passed | Gate check preserved, no silent normalization | PASS |

Baseline: `python -m pytest tests/orchestrator -q --no-cov`, exit 0, 57 passed in
43.87s. RED selection: exit 1, three failed and one passed in 3.46s. GREEN selection:
exit 0, four passed in 4.71s. Source frozen after canonical formatting.

Final focused command:
`python -m pytest tests/orchestrator -q --cov-reset --cov=tools/orchestrator --cov-report=term --cov-report=xml:htmlcov/orchestrator-coverage.xml`
returned 0, 61 passed in 52.88s. Ruff and focused Mypy returned 0. All providers and
data in these tests are synthetic; no paid model invocation or real vocabulary read.

Additional final checks: `npm ci`, `npm run check:fast` with the Gitleaks override,
`npm run security:code` with the Semgrep override, `python -m ruff check .`,
`python -m mypy backend tools/orchestrator tests/orchestrator` and `git diff --check`
all exit 0. Two inherited frontend fast-refresh warnings remain, no lint errors.
Gitleaks/Semgrep each report zero findings. A focused diff/XML coverage probe gives
18/18 changed executable infrastructure lines covered (100%). Its first invocation
failed on a relative XML source path; resolving that path corrected the probe, with
no source/test change. No repository-wide total coverage verdict is claimed.

`npm run architecture:check` exits 0: frontend has zero violations, all seven
backend contracts are kept, and 40 gate tests pass in 20.75s. Scope audit permits
exactly the three owned code/test files and authorized documentation/bookkeeping.
Main remains clean at the original base. Not committed or merged: required aggregate
verification is blocked by the inherited policy conflict below. Final verdict:
NOT_READY_TO_COMMIT; implementation evidence is available for review.

Read-only replay of the actual saved T021 Plan reports precisely
`objective, forbidden_scope, stop_conditions`; its recorded artifact digest is
unchanged. Test/metadata diagnostics do not expose model content. No automatic
contract normalization, regeneration of an old run or discarded human gate.

Aggregate `npm run check:task` is NOT RUN for this remediation: it includes
`backend/tests/test_markdown_roundtrip.py::test_real_vocabulary_sample_read_only_roundtrip`,
which reads `docs/vocabularies/28-09-2026.md`, conflicting with the current user rule
against real user data in automated tests. This is an inherited policy conflict,
not a PASS. Minimal separate scope required: that T020-owned test and any explicitly
approved synthetic fixture, preserving its lossless/read-only assertions. No deselection,
skip, assertion weakening or product test change was made in T071.

T021 additionally requires native Windows ownership/ACL/reparse evidence; this
remediation does not provide it. No T021 DONE/READY-to-merge claim, run recovery,
automatic replay or task worktree cleanup is part of T071. Existing T021/T059 runs
and unrelated worktrees are intentionally untouched.

## Retry extension and final verification (01/10/2026, Asia/Bangkok)

The latest user request authorizes a narrowly scoped explicit retry command. Scope
was recorded before editing `__main__.py`; no product files or existing run state
were added to the allowlist. Final code/test ownership is the four listed files.
The planning-only results above are historical after this source extension.

`run` now refuses a duplicate task worktree before creating a misleading empty run.
`retry` checks every retained registered task worktree against its managed run,
holds task/run locks, verifies unchanged source/history/task and all recorded artifact
digests, and refuses accepted contracts, Worker/integration stages or genuine human
gates. It creates a new uniquely named branch/worktree/run from current local main,
records `retry_of`/`retry_origin`, and reruns dependencies/baseline/planning. No old
state transition is reopened, no worktree is removed and no previous evidence is
overwritten. Legacy known pre-worker failures are accepted only with the same proofs.

| Invariant | RED evidence | Mechanism | Final result |
|---|---|---|---|
| Safe rerun preserves failed run while refreshing base | Retry method/CLI missing; 11 selected tests failed, exit 1 | Fresh isolated run plus immutable origin; original JSON bytes retained | PASS |
| Duplicate attempts do not hide the actual owner | Original start created another BLOCKED record | Check registered worktrees before run directory creation | PASS |
| All historical evidence stays authoritative | Tampering an older digest was accepted; separate RED test failed, exit 1 | Validate every recorded digest, not only latest artifact pointers | PASS |
| No retry over human decisions or live/mutated work | Negative tests preserve state/history and user modifications | Locks, phase/artifact checks, exact worktree identity and Plan gates | PASS |
| Baseline is rerun after repair, including legacy state | Synthetic missing test exits nonzero before any provider | New run executes normal baseline with current configuration | PASS |

Retry RED selection: 11 failed in 13.61s, exit 1. First GREEN attempt exposed a
typed-artifact mismatch (three failed/eight passed, exit 1); the origin is now a
validated `RetryOrigin`, created inside the guarded pipeline. Historical-evidence
RED: one failed in 2.39s, exit 1. Expanded GREEN: 15 passed in 17.87s, exit 0.
The first Ruff run found two unused mock lambda parameters; naming them as unused
fixed lint without a suppression. All relevant final evidence was rerun afterward.

SOURCE FREEZE after canonical formatting and final lint correction. Final focused
command is the same coverage-enabled command listed above: exit 0, **76 passed in
67.65s**, with **90/94 changed executable infrastructure lines covered (95.74%)**
from that run's XML and exact HEAD diff. This focused probe is not the aggregate
coverage/ratchet verdict. Full Ruff, scoped formatter and Mypy over backend plus
orchestrator/tests (49 files) exit 0. `npm run check:fast` exits 0: floor/type/format/
lint pass, Gitleaks zero findings; two inherited frontend fast-refresh warnings
remain. No real provider call or real vocabulary read occurs in these tests.
`npm run security:code` exits 0 with the pinned Semgrep override and zero findings.
`npm run architecture:check` exits 0: zero frontend violations, seven kept backend
contracts, 40 architecture tests passed in 21.48s. `git diff --check` exits 0.
Scope audit confirms exactly four owned source/test files plus the four authorized
documentation/bookkeeping files, including this new card. No dependency/package,
application, migration, generated contract, security configuration or runtime JSON
changes. No commit, merge, push or real provider execution.

Read-only eligibility checks on actual retained runs identify T059
`202610011513380625930000-e4b16bb7` as a proven pre-worker retry source and reject
T021's unresolved human gates. All existing run JSON digests remain unchanged;
no retry/Worker execution or task cleanup was performed on those real runs.

Required aggregate verification remains NOT RUN because of the inherited real-data
test policy conflict documented above. Status stays IMPLEMENTATION_DONE_BASELINE_BLOCKED,
not DONE; main stays clean at `b9530b9`. This code is not yet committed or merged,
and `retry` is not yet available on main. Final verdict: NOT_READY_TO_COMMIT.

## Owner-authorized promotion (01/10/2026, Asia/Bangkok)

After the unavailable aggregate verdict and proposed separate T020 test scope were
disclosed, the owner explicitly requested "commit và merge vào main". This authorizes
committing and promoting the focused T071 repair. It does not authorize altering
T020 tests, reading real user data in automated tests, waiving thresholds or claiming
aggregate PASS. T071 stays IMPLEMENTATION_DONE_BASELINE_BLOCKED and unchecked in todo.

Promotion must be local ff-only from unchanged clean main `b9530b9`, serialized
under the repository integration lock. Stage exactly the eight authorized files;
inspect the staged diff and run a secret scan. Preserve all existing task worktrees,
runtime JSON and unrelated application files. Run focused checks on promoted main
and record resulting SHAs/outcomes here. No remote operations or push.

## Local main integration evidence (01/10/2026, Asia/Bangkok)

Focused code commit: `c4924cd33014d6c55bac5a035e7e71e930a34034`,
`fix(orchestrator): preserve task constraints and safely restart pre-worker runs`.
Committed exactly the eight authorized files after staged-scope/source-hash checks,
`git diff --cached --check` (exit 0) and a fresh Gitleaks scan (exit 0, zero findings).
Main advanced ff-only from `b9530b97118131ffa4c266d47979a46550ef015d` to that SHA
under `.agent-runs/.locks/integration.lock`, with both checkouts clean and identities
confirmed. No unrelated branch was merged, reset or removed.

| Verification | Exit | Outcome |
|---|---|---|
| `npm run check:fast` on the task branch, pinned Gitleaks override | 0 | Format/lint/types/floor/secrets passed; two inherited frontend warnings |
| `python -m tools.orchestrator --help` on promoted main | 0 | `run,status,resume,retry` exposed |
| `python -m pytest tests/orchestrator -q --no-cov` on promoted main | 0 | 76 passed in 71.32s, synthetic repositories/providers only |
| `python -m ruff format --check tools/orchestrator tests/orchestrator` on main | 0 | Six files formatted |
| `python -m ruff check .` on main | 0 | No lint errors |
| `python -m mypy backend tools/orchestrator tests/orchestrator` on main | 0 | No issues in 49 files |
| `npm run check:task` | NOT RUN | Inherited real-data policy conflict remains unresolved |

The follow-up evidence commit changes only this card, todo and changelog; implementation
and tests remain byte-identical to the verified code commit. Main now provides `retry`.
Task status remains IMPLEMENTATION_DONE_BASELINE_BLOCKED, todo/checkpoints stay unchecked,
and no aggregate PASS or T021/T059 completion is claimed. Application source/tests,
migrations, generated files, dependency/lock files, credentials, real vocabulary data,
all existing task worktrees and runtime JSON are intentionally unchanged. No paid
model execution, automatic task retry, remote operation or push was performed.

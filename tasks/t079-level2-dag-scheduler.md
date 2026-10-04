# T079 — Generic Level 2 DAG Scheduler

**Status:** `DONE`
**Title:** Generic DAG scheduler for all unfinished repository tasks
**Goal:** Extend the existing Level 1 orchestrator with repository-wide task discovery, dependency DAG resolution and concurrent dispatch of all READY unfinished tasks without task-ID-specific logic.
**Level:** `High`

## Dependencies

- T068
- T072
- T073
- T077
- T078

## Files được phép sửa

- `tools/orchestrator/scheduler.py`
- `tools/orchestrator/__main__.py`
- `tests/orchestrator/test_scheduler.py`
- `docs/orchestrator.md`

## Acceptance criteria

- [x] Scheduler discovers repository task cards generically from `tasks/t*.md`; no product task ID such as T034/T018/T023 is hard-coded.
- [x] Scheduler builds a validated dependency DAG for unfinished tasks and detects missing dependencies, duplicate task IDs, self-dependencies and cycles fail-closed.
- [x] DONE tasks are treated as satisfied dependencies; unfinished tasks whose dependencies are satisfied become READY; other unfinished tasks remain BLOCKED with explicit dependency reasons.
- [x] DAG discovery does not require blocked tasks to pass `task_card()` dependency enforcement; the authoritative `task_card()` validation still runs before actual dispatch.
- [x] Scheduler dispatches multiple independent READY tasks concurrently through the existing `Pipeline`; existing per-task worktree, contract, audit, remediation and integration semantics are reused rather than reimplemented.
- [x] Existing repository admission slots and serialized integration lock remain authoritative.
- [x] A BLOCKED/FAILED task does not terminate unrelated READY tasks; only its downstream dependents remain blocked.
- [x] After an integrated task becomes DONE on canonical main, scheduler recomputes the graph and may dispatch newly READY downstream tasks.
- [x] The same task cannot be dispatched twice concurrently.
- [x] Dry-run performs no worktree creation and no model invocation and reports DONE, READY and BLOCKED task sets plus blocking dependencies.
- [x] CLI supports a repository-wide scheduler command without requiring a specific Txxx argument.
- [x] Scheduler never pushes, never weakens task allowlists/verification, never bypasses the existing Pipeline state machine and never invents dependency completion.
- [x] Existing single-task `run`, `resume`, `retry` and `status` behavior remains backward compatible.

## Verification commands

```bash
python -m pytest tests/orchestrator/test_scheduler.py -q --no-cov
python -m pytest tests/orchestrator -q --no-cov
python -m ruff check tools/orchestrator tests/orchestrator
python -m ruff format --check tools/orchestrator tests/orchestrator
python -m mypy tools/orchestrator
git diff --check
```

## Stop conditions

Stop instead of widening scope if implementing the DAG scheduler requires changing product task semantics, product source files, public application contracts, existing task acceptance criteria, or weakening the existing Pipeline safety/integration guarantees.

Resource-aware CPU/RAM/FAST/FULL gate scheduling is explicitly deferred to the next infrastructure task.

## Expected output and verification evidence — 04/10/2026

Implementation complete on `feature/task-t079-dag-scheduler`, Linux/WSL,
Python 3.12.3. No commit, merge or push; canonical main remains unchanged.

| Exact command | Outcome |
|---|---|
| `python -m pytest tests/orchestrator/test_scheduler.py -q --no-cov` | exit0; 47 passed in 13.65s |
| `python -m pytest tests/orchestrator -q --no-cov` | exit0; 279 passed in 211.58s; all 232 existing cases retained and passing |
| `python -m ruff check tools/orchestrator tests/orchestrator` | exit0; all checks passed |
| `python -m ruff format --check tools/orchestrator tests/orchestrator` | exit0; 10 files already formatted |
| `python -m mypy tools/orchestrator` | exit0; no issues in 6 source files |
| `git diff --check` | exit0; no whitespace errors |
| `python -m tools.orchestrator schedule --dry-run` | exit2; `Duplicate task IDs: T075, T076`; no dispatch |

Additional evidence:

- `python -m pytest tests/orchestrator/test_scheduler.py -q --cov-reset --cov=tools.orchestrator.scheduler --cov-branch --cov-report=term-missing --cov-report=xml:/tmp/t079-scheduler-coverage.xml`: exit0; 47 passed; 164/170 lines (96.47%), 63/66 branches (95.45%), combined coverage rounded96%.
- `python -m mypy tools/orchestrator tests/orchestrator/test_scheduler.py`: exit0, 7 files.
- `npm run security:secrets`: exit0, zero findings.
- `SEMGREP_BIN=/home/khanh/.local/tools/semgrep-1.178.0/bin/semgrep npm run security:code`: exit0, zero findings. Initial sandbox runs returned SETUP_FAILED because Semgrep could not update its read-only home settings; the authorized elevated rerun passed without scanner/rule changes.
- Baseline before implementation: 232 existing orchestrator tests passed. No existing tests were changed or weakened.
- Synthetic tests cover linear/fan-out/fan-in graphs, multiple roots, DONE/blocked dependencies, missing/self/cyclic edges, duplicate DONE IDs, stable ordering, malformed/symlink metadata, branch failure isolation, duplicate prevention, busy-root fairness, live capacity refill, canonical recomputation, no false DONE unlock and dry-run isolation. Actual spawned fake providers exercise Pipeline contracts/skills/audit, external OS admission contention and real temporary Git integration. No model CLI is invoked by these tests.

## Canonical repository dry-run

Canonical main `a823d2d4fe354b8074de26de475545ff5feacd90` contains 80 task
cards: 38 DONE and 42 unfinished (40 TODO, two implementation/baseline BLOCKED).
T075 and T076 each identify two separate cards. The requested dry-run correctly
rejects the entire graph before admitting any READY task. Valid READY/BLOCKED DAG
counts are **not computed** for an invalid graph; zero tasks are dispatched and
all 42 unfinished cards remain undispatched. An independent before/after probe
confirmed unchanged canonical refs, Git status, worktree registrations and lock
files. The local T079 card is not yet on canonical main.

Resolving duplicate repository IDs needs a separately authorized task; T079 does
not choose which product/infrastructure card wins or change unrelated metadata.
This existing input defect does not prevent synthetic scheduler acceptance or
justify weakening the duplicate-ID safety check.

## Architecture and handoff

- `scheduler.py` reads lightweight metadata from a pinned canonical revision,
  validates the entire DAG and resolves DONE/READY/BLOCKED with reasons. It calls
  authoritative `task_card()` immediately before `Pipeline.start()`; Pipeline's
  frozen-worktree checks and dependency verification remain authoritative.
- A repository-global scheduler OS lock and three-process spawn pool dispatch
  independent READY nodes in ascending ID order. Pipeline owns all admission,
  per-task/run/worktree/integration locks, provider handoffs, bounded recovery,
  verification/snapshot/scope fences and promotion. Live futures/outcomes prevent
  repeat dispatch; OS contention is deferred, not treated as a task failure.
- After completion, re-read canonical SHA and recompute outcomes/edges. Cache
  metadata only for identical SHA. A FAILED/BLOCKED/AUDIT_PASS result cannot
  unlock dependents; reported DONE also needs canonical DONE. Audited pending
  integration retains Level 1 resume semantics; scheduler does not invent new
  recovery or resolve overlapping bookkeeping/merge conflicts.
- Changed: `tools/orchestrator/scheduler.py`, `tools/orchestrator/__main__.py`,
  `tests/orchestrator/test_scheduler.py`, `docs/orchestrator.md`, this card,
  `tasks/todo.md`, `docs/changelogs.md`.
- Intentionally untouched: core/runtime/workflow/skills, orchestrator.yaml,
  existing orchestrator tests, every unrelated task card/checkpoint, product
  source/tests/contracts/migrations, dependency manifests and quality thresholds.
- Remaining limits: real canonical graph has duplicate IDs; live product-task
  execution was intentionally not performed. Pipeline's existing baseline,
  integration overlap and native Windows limitations remain unchanged.
- Next infrastructure work: CPU/RAM budgeting and FAST/FULL gate arbitration in
  a separate resource-aware scheduling task. No task ID or product behavior is
  selected here. Duplicate-ID repair needs its own authorized scope.

Commit proposal only: `feat(T079): admit repository DAG tasks through verified pipelines`.

## FULL floor remediation — 04/10/2026

Owner-requested remediation reproduced nine `[unfinished-work]` findings in
`tests/orchestrator/test_scheduler.py` at lines 65, 119, 182, 189, 232, 241,
252, 586 and 601. Eight synthetic `TODO` status occurrences now use `PENDING`
consistently; the `tasks/todo.md` fixture now uses `tasks/task-index.md` alongside
`tasks/_template.md`. Both filesystem and canonical Git discovery still ignore
the synthetic index/template. All 30 test functions and 89 assertions remain.

| Exact command | Remediation outcome |
|---|---|
| `python -m pytest tests/orchestrator/test_scheduler.py -q --no-cov` | exit0; 47 passed in 10.35s |
| `python -m pytest tests/orchestrator -q --no-cov` | exit0; 279 passed in 196.02s; includes all 232 existing cases |
| `python scripts/check_constraints.py floor` | exit0; `floor: clean`, zero findings |
| `python -m ruff check tools/orchestrator tests/orchestrator` | exit0; all checks passed |
| `python -m ruff format --check tools/orchestrator tests/orchestrator` | exit0; 10 files already formatted |
| `python -m mypy tools/orchestrator` | exit0; no issues in 6 source files |
| `git diff --check` | exit0; no whitespace errors |

Remediation changed only the scheduler test and permitted bookkeeping in this
card and `docs/changelogs.md`. Scheduler/CLI/runtime/lock/provider/integration
behavior, quality tooling/floor rules, verification, allowlists, architecture
constraints, product files and unrelated cards remain untouched by this round.
Status: `REMEDIATION_READY`. FULL itself was not rerun; these are the requested
floor-remediation checks.
No commit, merge, rebase or push.

## Current-state follow-up — T082, 04/10/2026

The duplicate-ID remediation is ready in the separate T082 worktree: T075/T076
retain orchestrator ownership; the UI foundation/migration cards now use T080/T081.
The unchanged scheduler's filesystem discovery finds 82 cards with 82 unique IDs.
Its next graph-validation failure is `Self dependency: T018`, from prose in that
card's Dependencies section. The renamed T081 card also retains its pre-existing
self-reference in Dependencies prose; neither defect is repaired by T082.

The actual `python -m tools.orchestrator schedule --dry-run` still returns exit2,
`ERROR OrchestratorError: Duplicate task IDs: T075, T076`, because it reads the
unchanged committed canonical main, not this uncommitted worktree. No dispatch,
commit or integration occurred. The earlier command results, pinned-revision
inventory and handoff above remain historical evidence. See
[T082](t082-task-id-remediation.md) for the current remediation verification.

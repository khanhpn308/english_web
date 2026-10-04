# T079 — Generic Level 2 DAG Scheduler

**Status:** `TODO`
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

- [ ] Scheduler discovers repository task cards generically from `tasks/t*.md`; no product task ID such as T034/T018/T023 is hard-coded.
- [ ] Scheduler builds a validated dependency DAG for unfinished tasks and detects missing dependencies, duplicate task IDs, self-dependencies and cycles fail-closed.
- [ ] DONE tasks are treated as satisfied dependencies; unfinished tasks whose dependencies are satisfied become READY; other unfinished tasks remain BLOCKED with explicit dependency reasons.
- [ ] DAG discovery does not require blocked tasks to pass `task_card()` dependency enforcement; the authoritative `task_card()` validation still runs before actual dispatch.
- [ ] Scheduler dispatches multiple independent READY tasks concurrently through the existing `Pipeline`; existing per-task worktree, contract, audit, remediation and integration semantics are reused rather than reimplemented.
- [ ] Existing repository admission slots and serialized integration lock remain authoritative.
- [ ] A BLOCKED/FAILED task does not terminate unrelated READY tasks; only its downstream dependents remain blocked.
- [ ] After an integrated task becomes DONE on canonical main, scheduler recomputes the graph and may dispatch newly READY downstream tasks.
- [ ] The same task cannot be dispatched twice concurrently.
- [ ] Dry-run performs no worktree creation and no model invocation and reports DONE, READY and BLOCKED task sets plus blocking dependencies.
- [ ] CLI supports a repository-wide scheduler command without requiring a specific Txxx argument.
- [ ] Scheduler never pushes, never weakens task allowlists/verification, never bypasses the existing Pipeline state machine and never invents dependency completion.
- [ ] Existing single-task `run`, `resume`, `retry` and `status` behavior remains backward compatible.

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

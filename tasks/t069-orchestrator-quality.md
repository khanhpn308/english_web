# T069: Include infrastructure in repository verification

**Task ID:** `T069`
**Title:** Include infrastructure in repository verification
**Status:** `DONE`
**Goal:** Implement the user-authorized Level 1 local development orchestrator slice.
**Estimated scope:** At most five handwritten implementation/config/test files; no product code.

## Context cần đọc

- `CONSTRAINTS.md`, `AGENTS.md`, `AGENT.md`
- `docs/orchestrator.md` (output of this task family)
- Existing Python/tooling configuration and installed Codex/Gemini CLI help

## Dependencies

- T068

## Files được phép sửa

- `pyproject.toml`

Common bookkeeping: this card, tasks/todo.md, docs/changelogs.md; user-authorized infrastructure documentation: docs/orchestrator.md and docs/task-plan.md infrastructure appendix.

## Files không được sửa

- backend/, frontend/, product contracts, migrations, real vocabulary and credentials.
- Existing quality thresholds and unrelated test assertions.

## Acceptance criteria

- [x] This slice implements its title with deterministic validated behavior.
- [x] Focused tests prove negative behavior, interrupted execution and isolation.
- [x] Source freeze, checks, scope and independent review evidence recorded.

## Test cases

1. Valid flow and malformed contract/state/provider failures.
2. Real temporary Git worktrees; concurrent process locks and crash recovery.
3. No real inference, no database and no destructive Git commands.

## Verification commands

```text
python -m pytest tests/orchestrator -q
python -m ruff check tools/orchestrator tests/orchestrator
python -m mypy tools/orchestrator tests/orchestrator
npm run check:task
```

## Expected output

Exit 0 with exact outcomes recorded. Inherited or environment failures are never PASS.

## Risk

- **Level:** High; orchestrator manages Git/state/agent subprocesses.

## Stop conditions

- Destructive Git, secret requirements, unknown merge semantics or weakening quality.

## Commit message đề xuất

`feat(orchestrator): replace manual agent handoffs with verified local runs`

## Completion evidence (01/10/2026, Asia/Bangkok)

Implemented and verified on `feature/task-t067-level1-orchestrator` from local main
`8dba8726c49585effc3c72ae790bf0b766eeea44`. Final source freeze has 57 focused tests,
590 full Python tests, 38 frontend tests and 40 architecture gate tests; full
`check:task`, Ruff/format/Mypy/build/contract pass, security zero findings, changed
coverage 89.34% and total 91.98% with unchanged thresholds. T070's AST is identical.
Exact commands, RED/GREEN, invariant matrix, scope, known platform/agent limitations
and files intentionally untouched: [final report](../docs/reviews/orchestrator-verification-001.md).
User-authorized focused commit follows staged review; no main merge or push.
Product checkpoints and unrelated worktrees remain unchanged.

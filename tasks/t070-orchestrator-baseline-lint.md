# T070: Remove inherited lint blocker for orchestrator baseline

**Task ID:** `T070`
**Title:** Remove inherited lint blocker for orchestrator baseline
**Status:** `DONE`
**Goal:** Remove the single inherited unused suppression that blocks the orchestrator's mandatory full Ruff baseline, preserving test semantics.
**Estimated scope:** One handwritten test file; mechanical quality-only remediation.

## Context cần đọc

- `CONSTRAINTS.md`, `AGENTS.md`, `AGENT.md`
- `docs/changelogs.md` CP06 inherited RUF100 evidence
- `scripts/tests/test_contract.py`

## Dependencies

- None (user-authorized routine lint remediation for Level 1 infrastructure)

## Files được phép sửa

- `scripts/tests/test_contract.py`

Common bookkeeping: this card, tasks/todo.md, docs/changelogs.md.

## Files không được sửa

- All application source, generated contracts, thresholds and assertions.

## Acceptance criteria

- [x] Remove only the unused E501 suppression on the subprocess closing line.
- [x] Python AST before/after is identical and contract tests pass.
- [x] Full repository Ruff passes without suppressions or threshold changes.

## Verification commands

```text
python -m ruff check .
python -m pytest scripts/tests/test_contract.py -q
```

## Expected output

Exit 0; AST-equivalence evidence and historical failure classification recorded.

## Risk

- **Level:** Low; comment-only change.

## Stop conditions

- Any change to assertions, source semantics or additional files required.

## Commit message đề xuất

`chore(orchestrator): remove inherited baseline lint blocker`

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

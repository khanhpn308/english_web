# T075: Correct agy capability probes and recover undispatched runs

**Task ID:** `T075`
**Title:** Correct agy capability probes and recover undispatched runs
**Status:** `DONE`
**Goal:** Fix the owner's T021 failure caused by agy help on stderr; check only flags actually used by stdin execution and permit a fresh run for the narrowly identified pre-dispatch failure without rewriting old evidence.

## Context cần đọc

- AGENTS.md, AGENT.md, CONSTRAINTS.md
- tasks/t074-agy-worker-permissions.md, tasks/t073-autonomous-agent-recovery.md
- docs/orchestrator.md, docs/adr/0006-local-agent-orchestration.md, docs/adr/0007-owner-verification-authority.md
- tools/orchestrator/runtime.py, workflow.py and their tests
- Installed agy --version/--help (no real inference)

## Dependencies

- T074

## Files được phép sửa

- `tools/orchestrator/runtime.py`
- `tools/orchestrator/workflow.py`
- `tests/orchestrator/test_core.py`
- `tests/orchestrator/test_workflow.py`

Documentation: docs/orchestrator.md. Common bookkeeping: this card, tasks/todo.md, docs/changelogs.md.

## Files không được sửa

Application source/tests, migrations, public API/generated client, dependencies/config,
scanner settings/thresholds, credentials, user vocabulary, retained run artifacts and other worktrees.

## Acceptance criteria

- [x] Valid CLI help on stdout/stderr is accepted; failed/timeout/oversized probes never dispatch an agent.
- [x] agy stdin execution does not require or pass the unused --print flag; every actual required capability stays checked.
- [x] The known agy --print pre-dispatch failure can retry only with intact task/plan/contract, original clean source/history, expected prompt/schema and no Worker execution artifacts.
- [x] Old evidence stays byte-identical; dirty, tampered, incomplete and uncertain Worker runs stay refused.
- [x] Focused regression, static checks and applicable repository gates pass after source freeze.

## Verification commands

```text
python -m pytest tests/orchestrator -q --no-cov
python -m ruff check .
python -m ruff format --check tools/orchestrator tests/orchestrator
python -m mypy backend tools/orchestrator tests/orchestrator
npm run check:task
```

## Risk / stop conditions

High: replay must never hide partial Worker outcomes. No destructive recovery,
old JSON edits, automatic model fallback, real inference test or false PASS.

## Discovery

Base main d7c15239f079db19f8168abbfb820082ca4ce0ff, clean. agy1.2.14
--help exits0 with stdout0bytes/stderr2895characters, advertising --print and the
actual stdin flags. Adapter previously inspected stdout only. T021 run
202610020433577305590000-5d5d376a failed before dispatch, with only Worker
prompt/schema, no execution log/result and a clean worktree at its original base.
No credentials read and no model invoked during discovery.


## Verification and handoff (02/10/2026, Asia/Bangkok)

Worktree: ../vocabularies-t075-agy-capabilities, feature/task-t075-agy-capabilities.
Frozen local main base: d7c15239f079db19f8168abbfb820082ca4ce0ff.

| Invariant | RED/negative evidence | Mechanism and final result |
|---|---|---|
| Valid help on either output stream permits headless execution | Initial RED six failures/seven passes6.74s; stdout/stderr/split and Codex/Gemini stderr fixtures | Join successful help streams, validate exit/timeout/size before capability parsing |
| Unused print flag does not block stdin | RED no-print fixtures; missing actual flags never dispatch | Check actual stdin/schema/mode/model/effort/permission flags; no print argument |
| Invalid probe cannot dispatch | Exit, timeout and output-limit negatives | Central process result checked before command execution |
| Known pre-dispatch failure can start a fresh run | RED retry success case refused; final eighteen recovery scenarios | Exact legacy error and phase, clean original Git, sealed task/plan/contract, canonical prompt/schema, no execution artifacts |
| Changed evidence is not replayed | Additional RED invocation prompt mutation1fail2.65s; dirty/history/tampered/missing/symlink/extra-attempt negatives | Reconstruct canonical role prompt; existing digest, ownership and locking fences retained |

Exact verification:
- Baseline: python -m pytest tests/orchestrator -q --no-cov, exit0,
  144passed115.20s on original main.
- Initial GREEN selection: 21passed8.73s; expanded selection33passed14.70s
  before the final missing-task-card case.
- Final focused: python -m pytest tests/orchestrator -q --no-cov, exit0,
  171passed130.47s.
- After SOURCE FREEZE: npm run check:task, exit0; 704 Python tests229.55s,
  38 frontend tests, 40 architecture tests22.15s; changed coverage97.22%,
  total92.36%, seven import contracts kept, Gitleaks/Semgrep/OSV0findings.
- Whole-repository Ruff, formatter check (six files), Mypy backend/orchestrator/tests
  (49 files), git diff --check: exit0. npm ci: exit0,254packages,
  no manifest/lock change.
- Native agy1.2.14 version/help accepted using real subprocess probes with agent
  execution mocked; no model turn or credentials accessed. CLI help remains public
  metadata; logs preserve only execution metadata/digests.
- Read-only retry_source verifies all registered T021 worktrees and selects
  202610020433577305590000-5d5d376a; all retained artifact bytes unchanged.
  No product task executed or marked DONE.

Evidence: ignored .agent-runs/T075/verification/ in this worktree, including
source-files.json, check-task.json, native-help-verification.json,
t021-recovery.json and retained-t021-files.json. Whole-source snapshot and frozen
implementation/test/guide/config hashes stayed identical throughout final gate.
Only task-local completion bookkeeping changes afterward.

Scope audit PASS: four implementation/test files, guide, this card, todo and
changelog. Intentionally untouched: application/backend/frontend, product task
cards/status/checkpoints, migrations, API/generated client, manifests/locks/config,
scanners/thresholds, credentials/user data and every old run/worktree.

Owner's existing commit/main-integration instruction applies; inspect staged
scope, scan secrets and promote only to clean unchanged main under integration
lock. No push or destructive cleanup. Remaining limits: no live inference smoke
or native Windows validation; arbitrary Worker crashes still require inspection.
Next user command from updated main: python -m tools.orchestrator run T021 --no-integrate.

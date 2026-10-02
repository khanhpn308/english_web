# T077: Make development task timeouts opt-in

**Task ID:** `T077`
**Title:** Make development task timeouts opt-in
**Status:** `DONE`
**Goal:** Run development agents, setup and verification until completion by default. Apply a time deadline only when the owner explicitly configures timeout_seconds.

## Context cần đọc

- AGENTS.md, AGENT.md, CONSTRAINTS.md
- docs/orchestrator.md, docs/adr/0006-local-agent-orchestration.md, docs/adr/0007-owner-verification-authority.md
- tools/orchestrator/core.py, runtime.py, workflow.py and tests/orchestrator
- T074/T075 provider capability and process permission evidence

## Dependencies

- T075
- T076

## Files được phép sửa

- `tools/orchestrator/core.py`
- `tools/orchestrator/runtime.py`
- `tests/orchestrator/test_core.py`
- `tests/orchestrator/test_workflow.py`
- `orchestrator.yaml`

Documentation: docs/orchestrator.md. Common bookkeeping: this card, tasks/todo.md, docs/changelogs.md.

## Files không được sửa

Application code/tests, product cards/checkpoints, migrations, API/generated files,
dependencies/thresholds, credentials, historical runs and other worktrees. No new
recovery mechanism or manual state edits. Preserve unrelated owner changes.

## Acceptance criteria

- [x] Omitted or null timeout_seconds disables task deadlines; explicit positive integer retains the configured deadline and legacy saved configurations validate unchanged.
- [x] No-limit subprocess execution keeps output limits, Ctrl+C cleanup, exit handling and process-tree cleanup; configured timeout still kills timed-out processes.
- [x] Provider interface and workflow pass null unchanged for every role and task verification; no implicit 1800-second task deadline remains.
- [x] Configuration and Vietnamese guide document default, explicit timeout, provider-side limits and historical FAILED/run config behavior.
- [x] Baseline, RED/GREEN, focused/static/aggregate verification and scope evidence are recorded without real model requests.

## Verification commands

```text
python -m pytest tests/orchestrator -q --no-cov
python -m ruff check .
python -m ruff format --check .
python -m mypy backend tools/orchestrator tests/orchestrator
npm run check:task
```

## Risk / stop conditions

No-limit execution deliberately waits for a stalled task until owner interruption.
Retain finite Git/capability-probe housekeeping timeouts; these are not agent/task
execution deadlines. Keep bounded fix cycles and resource locks. No product AI
operation deadlines change. No new dependency, recovery or automatic promotion.

## Discovery

Frozen local main: aca87f26d668416f0407f8e90755403787377aab.
Primary checkout main contains only owner's timeout_seconds=5400 edit; all work
is isolated in ../vocabularies-t077-optional-timeout on feature/task-t077-optional-timeout.
Config.timeout_seconds and execute default are both 1800; provider protocol uses
int. Workflow already forwards timeout to agents, setup and verification.


## Verification and handoff (02/10/2026, Asia/Bangkok)

| Command | Exit | Result |
|---|---|---|
| Baseline: python -m pytest tests/orchestrator -q --no-cov | 0 | 185 passed, 174.01s |
| RED: new opt-in/unlimited cases before source changes | 1 | 11 failed / 9 passed, 3.09s; implicit 1800 deadline, null rejected/None arithmetic, incorrect workflow timeout |
| GREEN: final new cases | 0 | 23 passed, 20.59s; includes PASS and Fix to DONE, all four roles and post-integration checks |
| Ruff check . / format --check . | 0 | No errors; 179 formatted files |
| Mypy backend tools/orchestrator tests/orchestrator | 0 | 51 source files checked |
| npm ci | 0 | Existing lock installed; manifests/lock unchanged |
| SOURCE FREEZE: npm run check:task | 0 | 786 Python tests (208 orchestrator), 38 frontend tests, 40 architecture tests; seven import contracts kept |
| Aggregate coverage/security | 0 | Changed coverage100%, total92.80%; Gitleaks/Semgrep/OSV zero findings |
| git diff --check | 0 | No whitespace errors |

| Invariant | Test/evidence | Mechanism/result |
|---|---|---|
| Default/explicit null waits until completion | Omitted/null config + simulated clock leap + real subprocess | Nullable default; no deadline constructed for None; exit0 |
| Manual finite timeout remains effective | Existing real one-second kill test; finite config and all-role pipeline | Monotonic deadline preserved; exit nonzero/timed_out on expiration |
| No-limit keeps cancellation/output safeguards | Real subprocess interrupt/reap and 5 MB output negatives | Polling every0.1s, process-tree cleanup and original output bound preserved |
| Role/check/state timeout agrees | Three fake CLI providers; six real-Git pipeline cases | None forwarded unchanged; typed persisted config roundtrips; finite integer still supported |
| Historical runs are preserved | No old run/worktree mutation; original config backed up | No recovery/state rewrite; only owner's newly requested timeout setting replaces5400 withnull |

SOURCE FREEZE hashes remained unchanged during the aggregate gate. Final card,
todo and changelog bookkeeping only follow verification. Two existing AppShell
fast-refresh warnings remain warnings, not failed lint checks. Evidence is in
.agent-runs/T077/verification/ (source-freeze.json, verification.json and check-task.log).

Scope audit PASS: exactly five implementation/config/test files plus this card,
todo, changelog and guide. Product source/tests, migrations, generated artifacts,
provider routing/permissions, dependencies/thresholds and prior run evidence
intentionally untouched. No real model call, remote Git or credential read.
Limitations: no time deadline means a hung task waits for interruption; finite
Git/probe housekeeping deadlines remain. Existing FAILED runs are not reopened.
No checkpoint or downstream product task is unlocked by this infrastructure change.

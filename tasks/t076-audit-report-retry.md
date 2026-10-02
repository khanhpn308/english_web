# T076: Clarify audit findings and retry inconsistent reports

**Task ID:** `T076`
**Title:** Clarify audit findings and retry inconsistent reports
**Status:** `DONE`
**Goal:** Keep findings for actionable unresolved problems, place successful verification in criterion evidence, and allow bounded Auditor correction of invalid semantic JSON before ending a run.

## Context cần đọc

- AGENTS.md, AGENT.md, CONSTRAINTS.md
- tasks/t073-autonomous-agent-recovery.md, tasks/t075-agy-capability-probes.md
- docs/orchestrator.md, docs/adr/0006-local-agent-orchestration.md, docs/adr/0007-owner-verification-authority.md
- tools/orchestrator/core.py, workflow.py and tests/orchestrator

## Dependencies

- T073
- T075

## Files được phép sửa

- `tools/orchestrator/core.py`
- `tools/orchestrator/workflow.py`
- `tests/orchestrator/test_core.py`
- `tests/orchestrator/test_workflow.py`

Documentation: docs/orchestrator.md. Common bookkeeping: this card, tasks/todo.md, docs/changelogs.md.

## Files không được sửa

Application code/tests, product cards/checkpoints, migrations, API/generated client,
provider adapters/config, dependencies/quality/security thresholds, credentials,
user data and existing run/worktree source or artifacts.

## Acceptance criteria

- [x] Audit schema descriptions and role-specific prompt explain findings, evidence and strict PASS invariants without changing stored JSON shape.
- [x] Semantic Audit checks occur inside the existing at-most-three-attempt invocation loop; rejected reports are immutable hashed artifacts with useful correction feedback.
- [x] Correction retries use the same source and contract without another Worker or consuming code-fix cycles; true FAIL still enters normal remediation.
- [x] Persistent invalidity, non-zero checks, source/history/state/handoff changes and rejected-report tampering never promote a task.
- [x] Baseline, RED/GREEN, frozen verification and scope audit are recorded; old T059 evidence remains unchanged and no real model call is used for tests.

## Verification commands

```text
python -m pytest tests/orchestrator -q --no-cov
python -m ruff check .
python -m ruff format --check tools/orchestrator tests/orchestrator
python -m mypy backend tools/orchestrator tests/orchestrator
npm run check:task
```

## Risk / stop conditions

High: no heuristic removal of findings, automatic conversion to PASS, stale-check
reuse, unlimited retries, weaker assertions or destructive/uncertain run replay.
Terminal historical FAILED runs remain evidence; this task does not introduce an
audit-only recovery command or alter their state.

## Discovery

Base local main ddffc12e0443197a91f4e862647b526d2696126c, clean.
T059 run202610020538470149160000-77174ceb has four exit0 checks at the current
source digest and a final PASS response with all three criteria PASS, no scope
violations or required fixes, but four informational findings. Audit.check rejects
those correctly; validation formerly happened outside the bounded invoke loop,
so no report correction was attempted. The current T059 worktree matches that
verified digest and is intentionally preserved.

## Verification and handoff (02/10/2026, Asia/Bangkok)

Worktree: ../vocabularies-t076-audit-report-retry.
Branch: feature/task-t076-audit-report-retry.
Frozen local main base: ddffc12e0443197a91f4e862647b526d2696126c.

| Invariant | Evidence / RED test | Mechanism | Final result |
|---|---|---|---|
| Successful notes belong in criterion evidence | Historical T059 PASS with four informational findings; schema and semantic correction tests | Role-specific rules plus JSON Schema descriptions; strict Audit.check preserved | Corrected PASS has empty findings and evidence retained |
| Invalid reports can be corrected without another Worker | Six semantic negative cases; initial RED missing correction | Validate inside the existing three-attempt invoke loop; send rejection reason and original JSON | One Worker, two Auditor calls, fix_cycle=0 |
| Real defects remain actionable | Mixed positive/defect report corrected to FAIL | No Python stripping or status rewriting; valid FAIL follows normal Fix flow | Two Workers, three Auditor calls, one code-fix cycle, DONE |
| False PASS and changed evidence never promote | Non-zero checks, persistent invalidity and source/state/handoff/rejected-report mutation cases | Independent command metadata, bounded attempts and existing snapshot/hash fences | FAILED, target SHA unchanged, no Integrator |
| Rejected reports remain evidence | Persistent-invalidity and tampering cases | Unique atomic rejected JSON with state artifact digest and retry protection | Three immutable rejections at exhaustion; tampering stops correction |

| Command | Exit | Result |
|---|---|---|
| Baseline: python -m pytest tests/orchestrator -q --no-cov on original main | 0 | 171 passed, 132.56s |
| RED: fourteen new cases before implementation | 1 | 11 failed / 3 passed, 20.18s; missing schema guidance/semantic retry, existing mutation fences already effective |
| GREEN: same fourteen cases | 0 | 14 passed, 24.30s |
| Final: python -m pytest tests/orchestrator -q --no-cov | 0 | 185 passed, 171.09s; includes stronger assertions preserving real defects and moved evidence |
| python -m ruff check . | 0 | All checks passed |
| python -m ruff format --check . | 0 | 176 files already formatted |
| python -m mypy backend tools/orchestrator tests/orchestrator | 0 | No issues in 49 source files |
| npm ci | 0 | Existing lockfile installed; no manifest/lock changes |
| npm run check:task, after SOURCE FREEZE | 0 | 718 Python tests in 306.96s, 38 frontend tests, 40 architecture tests in 26.84s; seven import contracts kept |
| Aggregate coverage/security | 0 | Changed coverage 96.30%, total 92.40%; Gitleaks/Semgrep/OSV zero findings |
| git diff --check | 0 | Clean |

The aggregate gate verified an unchanged source snapshot. Implementation, tests
and guide were frozen; only this card, todo and changelog receive final evidence
afterward. The two existing AppShell fast-refresh warnings are not lint errors.
Verification artifacts: .agent-runs/T076/verification in this task worktree
(source-freeze.json, check-task.json, t059-preserved.json).

Scope audit PASS: four authorized implementation/test files and four documentation/
bookkeeping files. Application source/tests, migrations, public API/generated
artifacts, provider/config, dependencies/thresholds and product task/checkpoint
status intentionally unchanged. No real model call or credential read.
All 89 T059 run files plus the verified worktree snapshot remain unchanged.
Historical FAILED recovery remains out of scope. Authorized promotion uses the
repository-level integration lock, a clean unchanged local main and ff-only; no push.

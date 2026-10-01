# T073: Autonomous development-agent recovery

**Task ID:** `T073`
**Title:** Autonomous development-agent recovery
**Status:** `DONE`
**Goal:** Owner requests removal of manual BLOCKED workflow: trust assigned Gemini sessions, retry unchanged failed agent attempts automatically, route role limitations through bounded remediation, and report actual terminal failures honestly.

## Context cần đọc

- AGENTS.md, AGENT.md, CONSTRAINTS.md
- docs/orchestrator.md, tasks/t072-remove-model-human-gates.md
- tools/orchestrator/runtime.py, workflow.py, __main__.py and orchestrator tests
- Installed Gemini 0.59.0 help/source: exit55 is FatalUntrustedWorkspaceError before headless dispatch; --skip-trust is a session-only supported flag.

## Dependencies

- T067
- T068
- T072

## Files được phép sửa

- `tools/orchestrator/runtime.py`
- `tools/orchestrator/workflow.py`
- `tools/orchestrator/__main__.py`
- `tests/orchestrator/test_core.py`
- `tests/orchestrator/test_workflow.py`

Documentation: docs/orchestrator.md. Common bookkeeping: this card, tasks/todo.md, docs/changelogs.md.

## Files không được sửa

- Production application/tests, migrations, API/client, package manifests/locks, credentials, vocabulary, scanner settings, saved run JSON and unrelated worktrees.

## Acceptance criteria

- [x] Gemini session trust is capability checked; no global trust/credentials change or real provider test.
- [x] Agent failures/invalid planning get at most three attempts, only with unchanged source/history/state/handoffs; all attempts preserved.
- [x] Worker/Auditor BLOCKED enters existing bounded fix cycle, never false PASS; terminal errors use FAILED, historical BLOCKED stays readable.
- [x] run can retry proven pre-dispatch failures automatically; known Gemini exit55 recovery preserves existing evidence and refuses unsafe/unknown Worker outcomes.
- [x] Tests, executable gates, scope checks, integration lock and truthful final evidence remain enforced.

## Verification commands

```text
python -m pytest tests/orchestrator -q --no-cov
python -m ruff check .
python -m mypy backend tools/orchestrator tests/orchestrator
npm run check:task
```

## Expected output

Baseline, meaningful RED/GREEN, source freeze and exact exits. Replacement of terminal BLOCKED assertions follows explicit owner change; preserve failure/non-promotion checks.

## Risk

- **Level:** High; agent repeat safety and legacy recovery are narrow and deterministic.

## Stop conditions

Actual test, source-integrity, scope, credential and unsafe Git failures must not be passed or ignored. Finite attempts, no destructive Git, no provider switch/real inference in tests.

## Evidence (02/10/2026, Asia/Bangkok)

Base main: `6bc055a2d3074749ee23110cdb2a2da67ece242c`. Worktree:
../vocabularies-t073-autonomous-recovery; branch feature/task-t073-autonomous-recovery.
Latest owner instructions request autonomous execution and focused commit/main merge.
No push is authorized.

Baseline: 86 passed in76.61s, exit0. RED: seven failures/nine passes in9.43s,
exit1, proving missing Gemini session trust, automatic retry, limitation repair and
known trust-error recovery. GREEN first selection16passed21.67s; intermediate
regression98passed115.28s preceded the final yolo/capability/empty-worker cases.
Final additional selection8passed23.01s, exit0. Test status assertions changed from
BLOCKED to FAILED by the explicit owner requirement; all no-promotion, preservation
and invalid-evidence assertions retained. No test removed/skipped or threshold changed.

| Invariant | Mechanism | Evidence |
|---|---|---|
| New Gemini worktree runs without interactive trust prompt | Probed --skip-trust, session only; Worker yolo, read-only roles plan | Fake CLI rejects missing flag; capability-negative and captured-argv tests |
| Failed agent does not require manual copy/paste | At most3 attempts with source/state/history/handoff fences | Transient third attempt succeeds; persistent error ends FAILED; partial edit prevents repeat |
| Worker/Auditor limitation enters remediation | Audit/fix flow remains bounded; Worker must ultimately IMPLEMENTED | Worker with/without diff and blocked Auditor reach DONE after Fix |
| Planning drift can self-correct | Validate pins before accepting Plan; sealed rejected attempts | First drift then corrected template reaches DONE; persistent drift fails after3 |
| run reuses stable progress or retries known pre-dispatch failure | Managed worktree/run ownership and locks; strict exit55/contract/source checks | Stable audited run integrates without new Worker; safe trust-error retry preserves every old file; invalid/dirty/missing evidence refused |
| Errors never become success | FAILED terminal outcome, independent tests and audit/integration fencing retained | Full regression, false-PASS rejection and no-promotion checks |

Final SOURCE FREEZE verification:
- `npm run check:task` with documented Gitleaks/Semgrep/OSV executable overrides:
  exit0, **634 Python tests in201.31s (101 orchestrator cases)**, frontend coverage
  tests passed, then **40 architecture tests in24.26s**. Changed coverage94.44%
  (minimum80%), total92.23% (baseline86.70%, tolerance0.50points); all three scanners
  zero findings. No timeout/oversized output; whole-source snapshot identical
  before/after. Metadata/digests in ignored .agent-runs/T073/verification/check-task-final.json.
- Earlier aggregate also exit0 but its whole-source marker was false because two
  guide sentences changed while tests ran; implementation/tests stayed unchanged.
  Final aggregate above was rerun after all wording changes, superseding that snapshot.
- Canonical formatter, whole-repo Ruff, Mypy backend/orchestrator/tests (49 files),
  diff check: exit0. npm ci: exit0,254 packages, no audit findings; manifests/lock unchanged.

Read-only real-run eligibility on updated controller proves T059
202610011719061675620000-23f5ef27 and T021202610011719313203820000-cfaaf1ce
can retry. All prior JSON remains identical. No task/provider was launched and no
credentials/global trust state were read or changed. Installed Gemini0.59.0 public
bundle maps FatalUntrustedWorkspaceError to55 before headless dispatch; CLI help
advertises --skip-trust and yolo. Diagnostics used installed source, no remote/web.

Scope: four implementation/test files, guide, this card, todo and changelog.
Production application/tests, migrations, generated contract/client, dependencies,
scanner config, credentials, vocabulary and every prior run/worktree intentionally
untouched. Only documentation/bookkeeping changes after final verification.

Limitations: attempts are bounded (three per invoke, existing configurable fix-cycle
limit). Missing credentials, real failing checks, partial Worker outcomes or unsafe
Git are actual FAILED errors; the system cannot manufacture a successful result.
Historical exit55 logs lacked a stored digest: recovery reads their metadata under
clean-source/contract guards; newly failed attempt logs are sealed. Agents remain
trusted local processes; yolo is not an OS sandbox. No automatic provider fallback,
real LLM smoke test, application AI retry or Level2 scheduler added.

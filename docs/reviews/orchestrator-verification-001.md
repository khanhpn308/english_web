# Level 1 orchestrator — final implementation and verification

## Status

DONE — T067, T068, T069 and T070 acceptance criteria satisfied on the task branch.
At this task-branch handoff, local main was intentionally not promoted. Subsequent
user-authorized integration is recorded in the [main integration report](orchestrator-integration-001.md).
No push, PR or real provider inference.
The [pause checkpoint](orchestrator-checkpoint-001.md) remains historical;
this report records the task-branch handoff. Documentation follows the repository-required
`documentation-and-adrs` skill.

## Base and worktree

- Original local branch/base: `main`, `8dba8726c49585effc3c72ae790bf0b766eeea44`.
- Implementation branch: `feature/task-t067-level1-orchestrator`.
- Checkout: `/home/khanh/projects/vocabularies`.
- Source freeze: final guard for lock failure after integration starts, followed by
  57 focused tests and static checks. Final aggregate used the same source snapshot;
  subsequent edits are documentation/bookkeeping only.
- User-authorized focused commit follows the staged scope/secret review. Resolve its
  SHA from this branch's Git history; no self-referential SHA is embedded in the commit.

## Implementation and architecture

Four namespace modules under `tools/orchestrator/` provide strict Pydantic contracts,
explicit state transitions, atomic JSON state, bounded argv subprocesses, safe local
worktrees, OS locks, capability-probed Codex/Gemini providers, role routing and the CLI.
Agents reason; Python validates results, checks dependencies/scope/evidence, owns
bounded fix cycles, commits and candidate promotion. No database/framework dependency.

The pipeline runs planning -> Worker -> independent audit -> bounded fix -> integrator
review -> host candidate merge/checks -> exact verified-SHA ff-only target promotion.
Integration defaults disabled and requires configuration/CLI authorization. One to
three processes have separate branches, worktrees, run directories and state/artifacts;
one repository-global integration lock serializes target modification. Busy integration
before entry is pending AUDIT_PASS; a lock failure after entry blocks uncertain recovery.

`orchestrator.yaml` is JSON syntax within YAML 1.2, avoiding a new parser dependency.
Role/model configuration is external; null model means CLI configuration, not a
fictional pinned model. Each new task/candidate worktree runs configured `npm ci`;
Python/dev tools come from the invoking environment. Runtime artifacts are ignored.
The application's provider policy, runtime, persistence and public contracts are unchanged.

## Invariant matrix and TDD evidence

| Invariant | Observable test/evidence | Mechanism | Final result |
|---|---|---|---|
| Legal transitions only; durable complete JSON | transition/roundtrip, invalid state, failed atomic replace | strict models, explicit transition map, temp/fsync/replace | PASS |
| Original scope/criteria/risk/stop rules survive planning/resume | malformed contract, risk downgrade, contract/task artifact and prompt tampering, missing artifact | task constraint pinning and saved digests; prompt matches Plan/Fix | PASS |
| Dependency DONE alone is insufficient | missing dependency source/unchecked criteria and owned-path parsing tests | checked criteria + existing exact owned files + nonempty rerun checks | PASS |
| Independent runs never share task state | three spawn processes reach AUDIT_PASS from one base with distinct paths/branches/run IDs | per-run/task locks, unique directories/worktrees, three OS slots | PASS |
| Integration is serialized across processes/configurations | cross-process lock, held integration lock -> pending -> resume, custom run directory | stable repository lock root and OS flock | PASS |
| Hard parent crash does not admit work while direct CLI child remains live | killed POSIX parent/live child retains lock until child exits | held lock FDs inherited by subprocesses | PASS on Linux/WSL |
| Hidden staged changes cannot escape scope | staged weakened test restored only in working tree is rejected | cached diff included in file set and source digest | PASS |
| PASS cannot override executable failure or stale source | lying PASS, edit between checks/audit, edit after audit including no-integrate resume | host checks bound to source digest; immutable audited snapshot | PASS |
| Failure invokes a bounded fix cycle | real temporary Git FAIL -> Fix -> PASS -> DONE and exhausted fix budget -> BLOCKED | deterministic state loop and configured max cycles | PASS |
| Target promotion is the verified candidate SHA | real Git PASS/fix integrations; disjoint main advance preserved | contribution scope vs captured target, post-merge checks, clean/identity rechecks and ff-only exact SHA | PASS |
| Lock failure after integration starts is not pending | `test_lock_failure_after_integration_started_is_not_pending` | propagate LockBusy outside AUDIT_PASS; outer handler records BLOCKED | PASS |
| CLI output/process failures cannot become valid handoffs | fake CLI success/nonzero/malformed/unavailable, timeout/output bound, unsupported Gemini reasoning | local help probes, argv execution, timeout/group kill, strict JSON schema | PASS |

Initial RED in the previous session: orchestrator test collection exit 2 because
modules did not exist. Concurrent-run RED exposed transient worktree lock refusal;
bounded waiting corrected it. In this resumed session the integration-start lock
regression test **exit 1** returned INTEGRATION_RUNNING rather than expected BLOCKED.
The minimal state-sensitive exception guard fixed it; final focused/full runs are GREEN.
No assertion was weakened or required test skipped/deleted.

## Final command evidence

| Command | Exit | Result |
|---|---:|---|
| `python -m pytest tests/orchestrator -q --no-cov` | 0 | 57 passed in 43.52s |
| `python -m ruff format --check .` | 0 | 167 files formatted |
| `python -m ruff check .` | 0 | zero findings |
| `python -m mypy backend tools/orchestrator tests/orchestrator` | 0 | 49 source files, zero errors |
| `npm run build` | 0 | Vite build successful; application source unchanged |
| `npm run test:contract` | 0 | 5 passed; checked-in OpenAPI/client remain unchanged |
| `npm run check:task` with T063 scanner overrides and original base | 0 | all nested gates completed |
| Nested `python -m pytest` | 0 | 590 passed in 122.60s, including all 57 orchestrator cases |
| Nested frontend coverage | 0 | 38 tests passed |
| Nested coverage gate | 0 | changed lines 89.34% >=80%; total 91.98%, baseline 86.70%, tolerance 0.50 points |
| Nested lint/type/floor | 0 | zero errors; two inherited fast-refresh warnings in AppShell.tsx |
| Nested Gitleaks/Semgrep/OSV | 0 each | zero findings for all three scanners |
| Nested architecture | 0 | frontend zero violations; seven backend contracts kept; 40 gate tests passed in 18.72s |
| `python -m alembic heads` | 0 | exactly one head: `0006_ai_admission`; no migration change |
| `git diff --check` | 0 | clean whitespace |
| T070 AST comparison to original base | 0 | Python AST identical; only unused suppression removed |
| T008/T018 dry-run | 0 | no agent call, artifact, worktree or Git mutation |

Exact aggregate invocation:

```bash
GITLEAKS_BIN="$HOME/.local/tools/gitleaks-8.30.1/gitleaks" \
SEMGREP_BIN="$HOME/.local/tools/semgrep-1.178.0/bin/semgrep" \
OSV_SCANNER_BIN="$HOME/.local/tools/osv-scanner-2.6.0/osv-scanner" \
QUALITY_BASE_REF=8dba8726c49585effc3c72ae790bf0b766eeea44 \
npm run check:task
```

An earlier sandboxed aggregate was interrupted with **exit 130** after lack of progress
in consent tests. It is not PASS and supplies no full-gate verdict. The successful
rerun executed outside the restricted sandbox; full access was subsequently restored.
Its source was frozen after the remediation above. Coverage numbers come from this
full run, not focused/historical reports. Gate duration exceeds the planning target;
no tests/gates/thresholds were removed to improve timing.

## Provider integration

Local installed help/version inspection only, no inference:

- Codex 0.159.2 in the initial session, **0.159.3** at final verification. Headless
  `-a never exec --ephemeral --sandbox read-only|workspace-write`, schema and final
  message files, optional model/reasoning, stdin prompt. Required flags reverified.
- Gemini **0.59.0**. Headless prompt/stdin, JSON envelope, plan/auto_edit approval mode,
  optional model. No reasoning-effort flag; configured reasoning must be null.
- Missing binary/capability, nonzero, timeout, oversized or malformed output fails
  clearly. Logs preserve exit/timing/digests without raw provider/test output or env.
- Real model/authentication quality is an operational prerequisite, not a mocked
  test claim. No paid API calls, real learning content or credential-store reads.

## Files and scope audit

Added: four `tools/orchestrator/*.py` modules, two `tests/orchestrator/*.py` modules,
`orchestrator.yaml`, T067–T070 cards, `docs/orchestrator.md`, ADR-0006, checkpoint
and this final report.

Modified: `.gitignore`, `pyproject.toml`, infrastructure appendix in `docs/task-plan.md`,
infrastructure entries in `tasks/todo.md`, `docs/changelogs.md`, and the one authorized
unused suppression in `scripts/tests/test_contract.py`.

Intentionally unchanged: backend/frontend application source, all migrations,
CONSTRAINTS.md, AGENTS.md/AGENT.md, product contract/ADRs, generated OpenAPI/client,
package/requirements locks, credentials, real vocabulary, product task/checkpoint
status, all other worktrees and remote state. Existing dirty T018 worktree is retained.

**Scope audit: PASS.** T067 owns three handwritten files, T068 five, T069 one and
T070 one. Documentation/common bookkeeping is separately authorized. No new package,
database, framework, suppression, weakened assertion or quality threshold.

## Review, limitations and Level 2 readiness

Two independent read-only reviews were completed in the initial session; their
concrete findings were remediated with regression tests. Resumed self-audit found
and fixed the integration-start LockBusy error. Source hashes are checked unchanged
across final evidence and documentation updates before commit.

Linux/WSL is validated. Native Windows automatic integration is ENVIRONMENT_BLOCKED
until process-lock inheritance/recovery is independently proven. Trusted local agents
are required: Gemini approval modes and post-run scope checks do not sandbox malicious
filesystem access. Interrupted active mutations block rather than replaying. Overlapping
target/bookkeeping drift and architectural conflicts require human review. Retained
worktrees need explicit manual cleanup before a same-task new run. These limitations
are documented; they are not silent successful recovery paths.

The configured base must contain the reviewed infrastructure before actual task runs;
this implementation is committed to its feature branch without automatically advancing
main. For first use, integrate it through the repository's authorized workflow, select
real installed role models, then run dry-run/status/resume as documented. No actual
product task was launched by verification.

Level 2 scheduling, distributed workers/locks, dashboard, daemon, database and stronger
OS isolation are deferred. Typed provider/state/Git/role interfaces permit extension
without replacing the Level 1 contracts. No product checkpoint is closed by this work.

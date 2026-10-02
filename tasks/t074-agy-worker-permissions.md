# T074: Antigravity CLI Worker and explicit execution permissions

**Task ID:** `T074`
**Title:** Antigravity CLI Worker and explicit execution permissions
**Status:** `DONE`
**Goal:** Route Gemini development Workers through the owner's installed agy CLI, expose Codex Worker full access and agy process auto-approval, and recover unchanged failed Gemini CLI runs after the explicit provider correction.

## Context cần đọc

- AGENTS.md, AGENT.md, CONSTRAINTS.md
- docs/orchestrator.md, tasks/t073-autonomous-agent-recovery.md
- tools/orchestrator/core.py, runtime.py, workflow.py and orchestrator tests
- Installed agy 1.2.14 --help/--version/models and Codex exec --help

## Dependencies

- T067
- T068
- T073

## Files được phép sửa

- `tools/orchestrator/core.py`
- `tools/orchestrator/runtime.py`
- `tools/orchestrator/workflow.py`
- `tests/orchestrator/test_core.py`
- `tests/orchestrator/test_workflow.py`
- `orchestrator.yaml`

Documentation: docs/orchestrator.md. Common bookkeeping: this card, tasks/todo.md, docs/changelogs.md.

## Files không được sửa

Production application/tests, migrations, API/client, dependency manifests/locks, credentials/global CLI settings, user vocabulary, scanners, retained run JSON and other task worktrees.

## Acceptance criteria

- [x] agy headless adapter checks installed capabilities, supplies stdin/schema and parses validated JSON; no real inference in tests.
- [x] Worker routes explicitly through agy using an actually listed Gemini model; Codex/Gemini adapters remain supported.
- [x] worker_access full-access maps to Codex danger-full-access, allow_process maps to agy session tool auto-approval; read-only roles cannot inherit elevated permissions.
- [x] Failed Gemini CLI to agy routing correction permits fresh run only with failed/no-output logs, intact evidence, clean original base and no implementation/integration; no original artifact changes.
- [x] Negative provider/output/permission/recovery tests, existing flow tests and applicable repository gates pass.

## Verification commands

```text
python -m pytest tests/orchestrator -q --no-cov
python -m ruff check .
python -m mypy backend tools/orchestrator tests/orchestrator
npm run check:task
```

## Risk / stop conditions

High: trusted local agents have explicit process/full access. This is not an OS security boundary. Real source/history drift, malformed output, unknown non-routing crashes and unsafe Git stay failures. No inference solely for tests, automatic provider fallback, production AI policy change or destructive recovery.

## Evidence

Frozen local main: 0d7ece6c7883e92473c16cf469a7725aa09ab99c. Worktree ../vocabularies-t074-agy-worker; branch feature/task-t074-agy-worker. Baseline: 101 passed in92.87s, exit0. agy1.2.14 --help establishes print/schema/mode/effort/skip-permissions flags; agy models lists gemini-3.8-flash-high and gemini-3.1-pro-high. User authorizes Worker permissions and prior commit/main integration; no push.


## Final verification and self-audit (02/10/2026)

SOURCE FREEZE: the three implementation modules, two test files and configuration;
these six hashes remained identical throughout the final gate. Earlier 136-case
focused evidence predates the final direct Worker status/permission/effort cases;
the aggregate below is the final executable evidence.

| Invariant | RED / negative evidence | Mechanism / final result |
|---|---|---|
| agy Worker uses the owner's actual CLI | RED unsupported provider/permission schema; native /help rejects valueless print | Capability probes; stdin auto-headless; valid schema/envelope parsing |
| No privilege spill into read-only roles | RED unknown worker permission fields; six non-Worker config negatives | Config validation; Codex read-only and agy plan never elevated |
| Explicit GPT full access and agy process approval | Captured argv plus missing capability/wrong provider negatives | Codex danger-full-access/never; agy skip-permissions for Worker only |
| JSON/error/timeout failures stay failures | Malformed/schema-invalid/error/denied/status-error/crash/timeout fixtures | Strict model validation and bounded process group timeout |
| Provider correction preserves old work | Six clean/dirty/output/timeout/tampered/same-provider scenarios | Explicit Gemini→agy correction; sealed artifacts and clean Git fences; original evidence unchanged |

Commands/outcomes:
- Baseline focused: 101 passed92.87s, exit0.
- RED selection: 32 failed5.67s, exit1, existing schema lacks agy and permissions.
- Initial GREEN: 32 passed9.74s; corrected stdin/native envelope selection35passed10.51s; final core selection28passed4.18s before last three negative cases.
- Final npm run check:task: exit0, 677 Python tests (144 orchestrator) passed202.20s, 38 frontend tests, 40 architecture tests23.29s. Changed coverage100%, total92.32% against86.70% baseline/tolerance0.50; Gitleaks/Semgrep/OSV0findings; seven import contracts kept.
- Ruff check/format and Mypy backend/tools/orchestrator/tests: exit0, 49 source files checked. git diff --check: exit0.
- npm ci: exit0, 254 packages, no manifest/lock change.
- Configured dry-run: exit0, agy/model/high/allow_process selected, no worktree/LLM created.

Runtime metadata and source hashes: ignored .agent-runs/T074/verification/
check-task.json and source-files.json in the T074 worktree. No raw diagnostic
bodies persisted. Installed agy1.2.14 /help via stdin returned JSON status SUCCESS
without an agent turn (verified local changelog); no live model inference test.
agy models queried available model metadata only. No credentials/global CLI config
read or edited. Codex flags come from installed exec help; no web/remote Git used.

Read-only recovery audit confirms T021 run202610011803489374360000-2dd820bc and
T059 run202610011803113101060000-5530c32f are eligible after provider correction;
all previous state files retained byte-identical. No product task was executed,
committed or marked done. Config, code and tests unchanged after source freeze;
only scoped completion bookkeeping appended after final verification.

Intentionally untouched: application/backend/frontend/tests/migrations/contracts,
generated client, dependency manifests/locks, scanners/quality thresholds, user data,
credentials, previous run artifacts and unrelated worktrees. No shell=True,
destructive Git, database, framework, automatic model fallback or Level2 scheduler.
Remaining limits: trusted local agents; full access/auto-approval is not an OS
boundary; live inference quality/auth entitlement still requires an actual task run.
Native Windows behavior remains inherited. No push or cleanup authorized.

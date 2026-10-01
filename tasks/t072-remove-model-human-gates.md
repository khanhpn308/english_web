# T072: Remove model-declared planning human gates

**Task ID:** `T072`
**Title:** Remove model-declared planning human gates
**Status:** `DONE`
**Goal:** Remove human_gates from new agent contracts and Python planning/retry vetoes, while retaining exact owner constraints, executable checks and immutable old evidence.

## Context cần đọc

- AGENTS.md, AGENT.md, CONSTRAINTS.md
- docs/orchestrator.md, docs/adr/0006-local-agent-orchestration.md
- tools/orchestrator/core.py, tools/orchestrator/workflow.py and both orchestrator test modules
- T071 card and T059 run 202610011631074539710000-7d6c660f, metadata/plan only

## Dependencies

- T067
- T068

## Files được phép sửa

- `tools/orchestrator/core.py`
- `tools/orchestrator/workflow.py`
- `tests/orchestrator/test_core.py`
- `tests/orchestrator/test_workflow.py`

Authorized documentation: docs/orchestrator.md, docs/adr/0007-owner-verification-authority.md.
Common bookkeeping: this card, tasks/todo.md, docs/changelogs.md.

## Files không được sửa

- Application source/tests/task cards, migrations, generated API/client, package/dependency locks, scanner configuration, credentials and vocabulary documents.
- Saved run artifacts/state and unrelated worktrees. No quality threshold change, test skip or suppression.

## Acceptance criteria

- [x] New Plan/Contract schemas and templates omit human_gates; current agent outputs stay strict.
- [x] Planning proceeds with valid contracts and host-confirmed baseline without a model-created human approval step.
- [x] Immutable legacy Plan/Contract files remain readable without rewriting originals; explicit retry accepts clean pre-worker runs previously blocked by the removed mechanism.
- [x] Scope, dependencies, source/artifact integrity, locks, real failure exit codes, audit/fix limit and integration fencing remain enforced.
- [x] Prompts distinguish executing repository-configured verification/scanners from manually accessing user learning data or credentials; new fixtures stay synthetic and no real inference runs in tests.

## Verification commands

```text
python -m pytest tests/orchestrator -q --no-cov
python -m ruff format --check tools/orchestrator tests/orchestrator
python -m ruff check .
python -m mypy backend tools/orchestrator tests/orchestrator
npm run check:task
```

## Expected output

Record baseline, RED/GREEN, source freeze, exact outcomes and scope. Existing human-veto tests must change to assert the explicitly requested new behavior, not be skipped or weakened to hide unrelated failures. All deterministic rejection tests remain.

## Risk

- **Level:** High; contract compatibility and retry authority must remain explicit.

## Stop conditions

- Missing real capability, failed checks, out-of-scope edit, mutated evidence or unsafe Git still stops execution.
- Do not modify product data/tests to fix a planning-only infrastructure issue or let agent claims replace executable evidence.

## Owner decision (01/10/2026, Asia/Bangkok)

Latest instruction: "bỏ luôn human_gates". This supersedes earlier requirements for the model-created planning gate. Repository-configured verification and redacted scanner scopes are treated as owner-selected commands, not new approval decisions invented per task. Agents still must not manually open/copy user vocabulary or credentials into reasoning/artifacts, change data, create real-data fixtures, run provider inference in automated tests or expand implementation scope. No security test/threshold is waived.

Base: e7c1ad57d29e6be006dad1de87841af50e5d7fa0. Isolated worktree: ../vocabularies-t072-remove-human-gates; branch feature/task-t072-remove-human-gates.

## Verification evidence (02/10/2026, Asia/Bangkok)

Baseline: 76 orchestrator tests passed in 59.53s, exit 0. RED selection: seven
failures in 2.23s, exit 1, for missing schema removal, compatibility readers,
legacy gate retry and verification authority. GREEN selection: nine passed in
9.24s, exit 0. Initial focused suite: 82 passed in 72.66s, exit 0; that snapshot
preceded the final prompt line-wrap and four additional compatibility/resume cases.
Those four passed in 1.89s, exit 0. Early Ruff failures were line length only,
fixed without suppression. Their evidence is historical; final checks below were
rerun after canonical formatting and SOURCE FREEZE.

| Invariant | Mechanism | Final evidence |
|---|---|---|
| No model-declared planning veto in new contracts | Field removed from strict schema/template and planning condition | Schema absence/extra-field rejection and full pipeline tests |
| Old contract/Plan stays intact | Narrow validated in-memory reader, raw digest checks retained | Deep value equality, file-byte preservation, malformed legacy input rejection |
| Old blocked gate can retry safely | Known pre-worker legacy failure plus original identity/history/lock guards | Both phase metadata versions create a fresh Plan; old prompt never replayed |
| Stable legacy resume still works | Stored readers for contract and worker prompt comparison | Simulated stable-handoff crash resumes through Worker/Audit; original files unchanged |
| Actual violations still stop | Existing scope/source/artifact/Git/exit/audit/fix-limit checks retained | Full orchestrator regression suite, including independent-process locks |

Final aggregate command with the three documented scanner overrides:
`npm run check:task`, exit 0, **619 Python tests passed in 172.63s** (including
all **86 orchestrator cases**), frontend coverage tests passed, then **40 architecture
tests passed in 21.71s**. Official changed coverage **100.00%** (minimum80%), total
**92.12%** (baseline86.70%, tolerance0.50 points). Gitleaks, Semgrep and OSV each
report zero findings. No test/scanner was skipped, narrowed or changed. New tests
use only synthetic repositories/providers/data; full repository verification runs
existing owner-configured tests with their original scopes as decided in ADR-0007.

Full Ruff and Mypy over backend/orchestrator/tests (49 files), canonical formatter
and `git diff --check` exit 0. `npm ci` exit 0, 254 packages installed, zero dependency
audit findings; manifest/lock unchanged. The aggregate ran for 225.42s without
timeout/oversized output and with whole-source digest unchanged during execution.
Metadata/digests are retained in ignored `.agent-runs/T072/verification/check-task.json`;
raw command output is not logged. Only bookkeeping/docs change afterward; the four
implementation/test hashes are retained for the final scope check.

Read-only inspection of actual T059 runs proves latest run
`202610011631074539710000-7d6c660f` is now retry eligible. All retained run JSON
digests stay identical; no provider invocation, actual retry, old state rewrite,
worktree removal or paid application inference was performed.

Scope: four code/test files and five documentation/bookkeeping files listed above.
Application source/tests, T020/T059 cards, migrations, generated API/client, package/
dependency locks, scanner configuration, credentials and vocabulary data intentionally
untouched. Product checkpoints and other task statuses are unchanged. T071's old
unavailable-verification record remains historical; this task has new full evidence
under the explicit owner decision rather than rewriting that history.

Owner subsequently instructed: "xong thì commit và merge vào main luôn". Commit
only this scope, inspect staged diff and scan secrets, then ff-only clean unchanged
local main under the integration lock and verify promoted code. No push authorized.

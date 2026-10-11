# T083: Repository DAG dependency metadata remediation

**Status:** `DONE`
**Title:** Remove invalid self-dependencies from canonical repository task metadata
**Goal:** Make repository task dependency metadata structurally valid for the Level 2 DAG scheduler without weakening DAG validation or changing product behavior.
**Level:** High

## Dependencies

- T079
- T082

## Files được phép sửa

- `tasks/t018-consent-ui.md`
- `tasks/t081-app-shell-shadcn-migration.md`
- `tasks/t083-dag-metadata-remediation.md`
- `tasks/todo.md`
- `docs/changelogs.md`

## Known inherited blockers

Independent audit after T082 established:

- T018 contains a self-dependency.
- T081 contains a self-dependency inherited from the former UI T076 card.
- These were the only self-dependencies found at the audited T082 candidate.
- No missing dependency IDs were found.

## Required behavior

- Inspect canonical task metadata repository-wide for self-dependencies.
- Remove only invalid self-dependency edges.
- Preserve all legitimate non-self prerequisites.
- T018 must retain all legitimate prerequisites.
- T081 must retain all legitimate prerequisites, including T080.
- Do not weaken DAG validation.
- Do not add task-specific exceptions to scheduler code.
- Do not modify product source code, API contracts, or application behavior.
- Do not rewrite historical evidence unnecessarily.
- Add a newest-first changelog entry for T083.
- Keep task IDs globally unique.
- Do not introduce missing dependency targets.

## Acceptance criteria

- [x] No canonical task card depends on itself.
- [x] Zero self-dependency edges remain in candidate task metadata.
- [x] Repository task IDs remain globally unique.
- [x] No missing dependency target is introduced.
- [x] T018 retains all legitimate non-self prerequisites.
- [x] T081 retains all legitimate non-self prerequisites, including T080.
- [x] Scheduler implementation remains unchanged.
- [x] Pipeline behavior remains unchanged.
- [x] Product source and contracts remain unchanged.
- [x] Candidate-aware DAG validation progresses beyond self-dependency validation.
- [x] Any newly exposed independent DAG defect is reported rather than bypassed.
- [x] Floor, orchestrator tests, Ruff, Mypy, and diff checks pass.

## Verification commands

```bash
npm run floor:check
python -m pytest tests/orchestrator/test_scheduler.py -q --no-cov
python -m pytest tests/orchestrator -q --no-cov
python -m ruff check tools/orchestrator tests/orchestrator
python -m ruff format --check tools/orchestrator tests/orchestrator
python -m mypy tools/orchestrator
git diff --check
```

## Host reconciliation and scoped closure, 11/10/2026 (Asia/Bangkok)

Status: `DONE` for the self-dependency metadata remediation and Host bookkeeping.
The existing correction `9aa1bb0398e2b738baffad0c9a7d0dd9049a56a6` and DONE
transition `a0b23be7846d8781abcdacc689251f2537f71975` are already ancestors of
canonical local `main`; no additional T018/T081 patch or integration is needed.
The unchecked todo entry is now reconciled. The dated evidence below remains
historical and unchanged.

Verified local `main` revision: `e3d34c82b0d9bc9fb3ebc4ff1e4226efeb3be6db`.
The concurrent main update from `b61e39d0e078201cf31d586ebcd8d3d1c2a42743`
did not change orchestrator source/tests/configuration or the T018/T081/T083 cards.
The `origin/main` comparison uses the existing local snapshot
`5153c0cf355289e9bfa4cd241851ca3add977658`; no fetch was performed.

The inventory uses the existing scheduler `metadata()` parser on every matching
task document and reports every parse failure. Worktree, local main and the local
origin/main snapshot each contain 90 valid canonical cards with 90 unique IDs,
zero self-dependency edges and zero missing dependency targets among those cards.
T018 retains `T015`, `T017`, `T052`, `T081`; T081 retains `T004`, `T080`.
T079/T082/T083 remain DONE. One additional matching document fails metadata
validation, so these inventory results do not establish a valid whole-repository DAG.

| Exact command / probe | Current outcome |
|---|---|
| `npm run floor:check` | exit 0; `floor: clean` |
| `python -m pytest tests/orchestrator/test_scheduler.py -q --no-cov` | exit 0; 48 passed in 16.59s |
| `python -m pytest tests/orchestrator -q --no-cov` | exit 0; 561 passed in 370.68s |
| `python -m ruff check tools/orchestrator tests/orchestrator` | exit 0; all checks passed |
| `python -m ruff format --check tools/orchestrator tests/orchestrator` | exit 0; 17 files already formatted |
| `python -m mypy tools/orchestrator` | exit 0; no issues found in 9 source files |
| `git diff --check` | exit 0 after bookkeeping edits |
| `npm run security:secrets` | exit 0; 0 findings across working-tree, staged and history scopes |
| Repository-wide metadata inventory on worktree/main/local origin/main | exit 0; 90 valid canonical cards, 0 self-edges, 0 missing targets; malformed auxiliary document reported separately |
| `python -m tools.orchestrator schedule --dry-run` | exit 2; `ERROR OrchestratorError: Invalid task metadata: tasks/t008-r4-shared-remediation.md`; no dispatch |

The current scheduler blocker is an independent malformed T008 shared-remediation
authorization document, outside T083's allowlist. It is reported under this task's
independent defect rule; it is neither bypassed nor claimed PASS. A separately
scoped metadata fix and subsequent canonical-main dry-run are the next work.
Scheduler validation, Pipeline behavior and product code remain unchanged.

Changed files: this card, `tasks/todo.md`, `docs/changelogs.md`. Intentionally
untouched: T018/T081 cards, the malformed T008 document, scheduler/Pipeline source,
tests, product source/contracts/migrations, constraints and other task states.
No product builds, browser/Windows/release gates or independent audit were run.
No staging, commit, merge, fetch, push or real scheduler dispatch was performed.
Commit proposal: `docs: reconcile T083 closure with integrated metadata evidence`.

## Authorized bookkeeping commit and worktree closure, 11/10/2026 (Asia/Bangkok)

The owner authorized committing these three bookkeeping files and closing the
T083 worktree. `/home/khanh/projects/vocabularies-t083-codex` had no tracked,
untracked or ignored changes, and its tip `5153c0c` is already an ancestor of
`main`. `git worktree remove /home/khanh/projects/vocabularies-t083-codex`
exited 0 without force. The branch `fix/t083-dag-metadata-remediation` is retained.

Fresh commit preflight: `npm run floor:check` exits 0;
`python -m pytest tests/orchestrator/test_scheduler.py -q --no-cov` exits 0,
48 passed in 11.22s; `python -m ruff check tools/orchestrator tests/orchestrator`,
`python -m ruff format --check tools/orchestrator tests/orchestrator` and
`python -m mypy tools/orchestrator` all exit 0. The full orchestrator-suite
results in the earlier reconciliation remain historical, not a new run.
`git diff --check` exits 0. `GITLEAKS_BIN=/home/khanh/.local/tools/gitleaks-8.30.1/gitleaks npm run security:secrets`
exits 0 with zero findings; generated scanner reports remain untracked/ignored.
Product/browser/Windows/release checks remain deferred. T083 stays DONE;
the separate T008 metadata defect remains unresolved and is the next task.

## Expected output and verification evidence — 04/10/2026 (Asia/Bangkok)

Status: `REMEDIATION_READY`. Metadata changes are reviewable in
`fix/t083-dag-metadata-remediation`; this card is not DONE because canonical-main
verification requires separate authorized integration.

| Exact command / probe | Outcome |
|---|---|
| `npm run floor:check` | exit 0; `floor: clean`, zero findings |
| `python -m pytest tests/orchestrator/test_scheduler.py -q --no-cov` | exit 0; 47 passed in 9.10s |
| `python -m pytest tests/orchestrator -q --no-cov` | exit 0; 279 passed in 167.19s |
| `python -m ruff check tools/orchestrator tests/orchestrator` | exit 0; all checks passed |
| `python -m ruff format --check tools/orchestrator tests/orchestrator` | exit 0; 10 files already formatted |
| `python -m mypy tools/orchestrator` | exit 0; no issues found in 6 source files |
| `git diff --check` | exit 0; clean |
| Candidate-aware filesystem discovery and resolution probe (below) | 83 cards, 83 unique IDs, 0 self-dependencies, 0 missing dependencies; graph resolve exits 0; 40 DONE, 6 READY (`T008`, `T018`, `T023`, `T027`, `T034`, `T083`), 37 BLOCKED |
| `python -m tools.orchestrator schedule --dry-run` | exit 2; `ERROR OrchestratorError: Self dependency: T018`. Evaluates canonical main (pinned revision), which retains pre-T083 metadata prior to authorized integration. No dispatch occurs. |

### Candidate-aware isolated diagnostic probe

```python
from pathlib import Path
from tools.orchestrator.scheduler import discover, resolve

tasks = discover(Path.cwd())
assert len(tasks) == 83
assert all(t not in c.dependencies for t, c in tasks.items()), "Zero self-dependencies"
assert all(d in tasks for c in tasks.values() for d in c.dependencies), "Zero missing dependencies"
graph = resolve(tasks)
assert len(graph.topological_order) == 83
assert len(graph.done) == 40
assert len(graph.ready) == 6
assert set(graph.ready) == {"T008", "T018", "T023", "T027", "T034", "T083"}
assert len(graph.blocked) == 37
```

## Canonical-main scheduler note

The Level 2 scheduler discovers task metadata from canonical `main`.

Before T083 is integrated, the command:

```bash
python -m tools.orchestrator schedule --dry-run
```

may still observe the self-dependency present on canonical main.

This must not be treated as a reason to weaken scheduler validation.

Candidate validation must use the existing candidate/filesystem discovery path or an equivalent isolated candidate check.

After T083 is integrated into canonical main, `schedule --dry-run` must progress beyond the T018/T081 self-dependency blocker.

## Stop conditions

Stop instead of widening scope if remediation requires:

- modifying scheduler implementation;
- modifying Pipeline behavior;
- modifying product source code;
- modifying API contracts;
- weakening DAG validation;
- changing unrelated task semantics;
- changing quality, security, or coverage thresholds;
- broadly rewriting historical evidence.

If another independent DAG defect becomes visible after removing the self-dependencies, report it separately instead of expanding T083 scope.

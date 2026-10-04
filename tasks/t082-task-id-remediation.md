# T082: Canonicalize duplicate repository task IDs

**Status:** `REMEDIATION_READY`

**Task ID:** `T082`

**Title:** Resolve duplicate T075/T076 task IDs so the repository DAG is globally valid.

**Goal:** Preserve the older orchestrator ownership of T075/T076 and renumber the later UI task pair to unique canonical IDs without changing product behavior or historical evidence.

## Canonical mapping

- `tasks/t075-agy-capability-probes.md` remains `T075`
- `tasks/t076-audit-report-retry.md` remains `T076`
- shadcn/ui foundation (formerly assigned T075): `tasks/t080-shadcn-ui-foundation.md` / `T080`
- AppShell shadcn migration (formerly assigned T076): `tasks/t081-app-shell-shadcn-migration.md` / `T081`

The mapping is determined by Git creation history: the orchestrator cards predate the UI cards.

## Dependencies

None. This owner-authorized repository metadata remediation has no task prerequisite.

## Required behavior

- Preserve T075/T076 orchestrator semantics unchanged.
- Rename the two UI cards with `git mv`.
- Update their internal Task IDs, titles/references and dependency links.
- T081 must depend on T080 instead of T075.
- Update all live/current repository task dependencies that refer specifically to the shadcn/AppShell UI tasks.
- Update current task planning/index documentation consistently.
- Do not blindly replace every textual T075/T076 occurrence.
- Preserve historical changelog/evidence text unless a current-state statement would become false or ambiguous.
- Add a new changelog entry documenting the canonical-ID remediation.
- Do not alter production source code, application contracts, tests or orchestrator execution semantics.

## Acceptance criteria

- Exactly one task card identifies as T075.
- Exactly one task card identifies as T076.
- Exactly one task card identifies as T080.
- Exactly one task card identifies as T081.
- All live UI dependency links point to T080/T081 where semantically appropriate.
- No orchestrator dependency is accidentally redirected to T080/T081.
- No dangling references to renamed UI filenames remain.
- Repository-wide scheduler discovery no longer fails with duplicate T075/T076.
- `python -m tools.orchestrator schedule --dry-run` gets past duplicate-ID validation.
- Any later DAG failure, if present, is reported separately and is not hidden or weakened.
- Existing constraints and verification remain unchanged.

## Verification

```bash
python -m tools.orchestrator schedule --dry-run
python scripts/check_constraints.py floor
python -m pytest tests/orchestrator -q --no-cov
python -m ruff check tools/orchestrator tests/orchestrator
python -m mypy tools/orchestrator
git diff --check
```

## Expected output and verification evidence — 04/10/2026 (Asia/Bangkok)

Status: `REMEDIATION_READY`. Metadata changes are reviewable in
`fix/t082-task-id-remediation`; this is not a claim of promotion to canonical main
or a valid repository-wide DAG. This card is not DONE because canonical-main
verification requires separate authorized integration.

| Exact command / probe | Outcome |
|---|---|
| `rg -n '^\*\*Task ID:' tasks/t[0-9]*.md` plus Python declaration/heading counts | 81 explicit Task ID declarations, all unique; 82 task headings, all unique. T079 uses its heading without an explicit Task ID field. Exactly one each of T075, T076, T080 and T081, all matching their canonical filenames. |
| `rg -n 't07[56]-(shadcn-ui-foundation\|app-shell-shadcn-migration)\.md' .` (use unescaped alternation in the shell command below) | exit1; no matches anywhere in the searchable repository, including this card and historical changelog filename locators. |
| `python -m tools.orchestrator schedule --dry-run` | exit2; `ERROR OrchestratorError: Duplicate task IDs: T075, T076`. Reads unchanged committed canonical main, not the remediation worktree; no dispatch. |
| Unchanged scheduler `discover(Path.cwd())`, then `resolve(tasks)` (probe below) | discovery succeeds: 82 cards/82 unique IDs. Resolve exits2 with `ERROR OrchestratorError: Self dependency: T018`; no graph readiness counts or dispatch. |
| `python scripts/check_constraints.py floor` | exit0; `floor: clean`, zero findings. |
| `python -m pytest tests/orchestrator -q --no-cov` | exit0; 279 passed in 177.53s. |
| `python -m ruff check tools/orchestrator tests/orchestrator` | exit0; all checks passed. |
| `python -m mypy tools/orchestrator` | exit0; no issues in 6 source files. |
| `git diff --check` | exit0 after removing inherited Markdown trailing spaces on the two modified T081 metadata lines. |

The worktree probe is separate from the CLI dry-run; it does not override Git
revision selection, mutate scheduler semantics or treat any failure as a pass:

```bash
rg -n 't07[56]-(shadcn-ui-foundation|app-shell-shadcn-migration)\.md' .
python - <<'PY'
from pathlib import Path
from tools.orchestrator.core import OrchestratorError
from tools.orchestrator.scheduler import discover, resolve

tasks = discover(Path.cwd())
print(f'Worktree discovery: {len(tasks)} cards, {len(set(tasks))} unique IDs')
print(f'T081 dependencies parsed by unchanged scheduler: {tasks["T081"].dependencies}')
try:
    graph = resolve(tasks)
except OrchestratorError as error:
    print(f'ERROR OrchestratorError: {error}')
    raise SystemExit(2)
print(f'DONE={len(graph.done)}, READY={len(graph.ready)}, BLOCKED={len(graph.blocked)}')
PY
```

## Scope and handoff

- Renamed with `git mv`: the UI foundation card formerly assigned T075 is now
  `tasks/t080-shadcn-ui-foundation.md`; the UI AppShell card formerly assigned
  T076 is now `tasks/t081-app-shell-shadcn-migration.md`.
- Reference classes changed: UI headings/Task IDs, current card prose and proposed
  commit labels, context/dependency links, direct and inherited design-system
  references, readiness labels, planning tables/adjacency/Mermaid/model lists,
  checkpoints and current-state index/handoff notes. T081's explicit prerequisites
  are T004 and T080; no reference to the orchestrator T075 remains in that card.
- Edited documentation: `docs/task-plan.md`, `docs/orchestrator.md`,
  `docs/changelogs.md`, `tasks/todo.md`, this card and
  `tasks/t079-level2-dag-scheduler.md` (append-only current-state follow-up).
- Edited UI cards: `tasks/t080-shadcn-ui-foundation.md`,
  `tasks/t081-app-shell-shadcn-migration.md`,
  `tasks/t009-lookup-ui-vertical-slice.md`,
  `tasks/t010-error-handling-recovery.md`, `tasks/t018-consent-ui.md`,
  `tasks/t025-save-ui-audio.md`, `tasks/t028-search-ui.md`,
  `tasks/t030-edit-ui.md`, `tasks/t033-review-ui.md`, `tasks/t036-quiz-ui.md`,
  `tasks/t038-dashboard-ui.md`, `tasks/t043-accessibility-evidence.md`,
  `tasks/t050-quiz-runner-ui.md`, `tasks/t051-quiz-result-feedback-ui.md`,
  `tasks/t060-status-ui.md`, `tasks/t064-ui-performance-harness.md`.
- Intentionally untouched: orchestrator T075/T076/T077/T078 cards (byte equality
  against HEAD verified), every implementation/test file, public API contracts,
  scheduler/configuration semantics, migrations, dependency manifests, quality
  thresholds and canonical Git refs. Final diff inspected for semantic ownership;
  task-index link labels match their target IDs.
- Historical evidence retained: dated IDs and descriptions in the changelog and
  task handoffs, and the original T079 failure/inventory evidence. Only two
  historical changelog filename locators were updated with explicit historical-ID
  annotations so they remain navigable without dangling old filenames.
- Remaining blocker: `Self dependency: T018`. The existing Dependencies prose
  contains its own task ID, which the unchanged scheduler parses as a dependency.
  T081 also parses a self-edge from the equivalent prose formerly naming T076;
  its parsed prerequisites are `['T004', 'T080', 'T081']`. Both self-references
  were verified present in the pre-remediation cards. Their repair needs a
  separate metadata task; no validator, test or threshold was weakened.
- Next task: separately authorize Dependencies prose/DAG remediation, then rerun
  canonical-main scheduling after authorized integration of metadata changes.
- Git status: two staged renames with unstaged content edits (`RM`), 19 modified
  tracked documentation files (` M`), and the pre-existing untracked T082 card
  (`??`), now containing this handoff. No commit, merge, rebase or push.

Commit proposal only: `fix: preserve orchestrator task ownership with unique UI IDs`.

# T085: Authoritative task dependency parsing normalization

**Task ID:** `T085`
**Title:** Normalize authoritative task dependency parsing across orchestrator layers
**Status:** `TODO`
**Goal:** Make executable task-card parsing and Level 2 DAG discovery interpret task dependencies with the same standalone task-ID semantics, eliminating false dependency edges created by task-like substrings embedded inside prose while preserving fail-closed dependency validation.
**Level:** High

## Dependencies

- T079
- T083

## Files được phép sửa

- `tools/orchestrator/core.py`
- `tools/orchestrator/scheduler.py`
- `tests/orchestrator/test_core.py`
- `tests/orchestrator/test_scheduler.py`
- `docs/orchestrator.md`
- `tasks/t085-task-dependency-parser.md`
- `tasks/todo.md`
- `docs/changelogs.md`

## Context và bằng chứng lỗi

T084 live remediation exposed an independent parser defect outside T084 scope.

`task_card()` currently derives dependencies using logic equivalent to:

`re.findall(TASK_PATTERN, section(text, "Dependencies"))`

where:

`TASK_PATTERN = r"T[0-9]{3}"`

This matches task-like substrings even when they are embedded inside larger prose tokens.

A real task card contains legitimate dependency links such as:

- `T081`
- `T015`
- `T017`
- `T052`

but its dependency section also contains prose including the token:

`BLOCKED_BY_T080_T081`

The executable task-card parser therefore falsely extracts `T080` from that prose.

The Level 2 scheduler already uses standalone-token matching semantics based on word boundaries, so scheduler discovery and executable task-card parsing can disagree about the same task card.

The false `T080` dependency then causes `task_card()` to validate an unrelated dependency card and may expose unrelated legacy metadata defects.

This is a generic parser-consistency defect, not a T018-specific defect.

## Required behavior

### 1. Establish one dependency-ID parsing contract

Dependency IDs must only be recognized when they are standalone task-ID tokens matching the repository task-ID grammar.

Valid examples include:

- `T079`
- `- T079`
- `[T079](t079-level2-dag-scheduler.md)`
- `Depends on T079 and T083`

Embedded task-like substrings must not create dependencies.

Invalid embedded examples include:

- `BLOCKED_BY_T080_T081`
- `PREFIX_T080`
- `T080_SUFFIX`
- `XT080`
- `T080X`

The solution must preserve uppercase canonical task IDs and the existing exact task-ID format.

### 2. Align executable task parsing and DAG metadata parsing

`tools/orchestrator/core.py` and `tools/orchestrator/scheduler.py` must use the same dependency-ID semantics.

Prefer a single small shared parser/helper if that reduces semantic drift without introducing unnecessary coupling.

Do not duplicate two subtly different regex contracts unless equivalence is explicitly proven by tests.

### 3. Preserve fail-closed dependency enforcement

This task must not weaken any existing checks for:

- missing dependency cards;
- dependency `DONE` status;
- checked acceptance criteria;
- dependency implementation files;
- dependency verification commands;
- self-dependencies;
- missing dependency targets;
- DAG cycles;
- canonical-main scheduler discovery.

Only false extraction of embedded task-like substrings is being fixed.

### 4. Add regression coverage

Tests must prove at minimum:

1. A standalone task ID in a dependency section is detected.
2. Markdown dependency links remain detected.
3. Multiple legitimate standalone IDs remain detected.
4. `BLOCKED_BY_T080_T081` does not create `T080` or `T081` dependency edges by itself.
5. Prefix/suffix embeddings such as `XT080`, `T080X`, `PREFIX_T080`, and `T080_SUFFIX` are ignored.
6. `task_card()` does not invent a missing dependency from embedded prose.
7. Scheduler metadata and executable task parsing produce equivalent dependency sets for the same dependency-section fixture.
8. Existing missing-dependency, self-dependency and cycle validation remain fail-closed.

Use synthetic task cards/repositories where appropriate. Do not depend on unrelated legacy metadata defects in T080 or T081 to prove parser behavior.

### 5. Preserve scheduler behavior

Do not change:

- scheduler dispatch concurrency;
- canonical revision discovery;
- READY/BLOCKED resolution semantics;
- Pipeline behavior;
- worktree ownership;
- retry behavior;
- integration behavior;
- lock behavior.

T085 is parser normalization only.

## Acceptance criteria

- [ ] Dependency IDs are recognized only as standalone canonical task-ID tokens.
- [ ] Embedded token `BLOCKED_BY_T080_T081` creates no dependency edge.
- [ ] `XT080`, `T080X`, `PREFIX_T080`, and `T080_SUFFIX` create no dependency edge.
- [ ] Markdown links such as `[T079](...)` continue to produce dependency `T079`.
- [ ] Plain standalone IDs such as `T079` and `T083` continue to work.
- [ ] Executable `task_card()` and scheduler metadata parsing share equivalent dependency semantics.
- [ ] A synthetic T018-style card containing legitimate dependencies plus `BLOCKED_BY_T080_T081` does not invent dependency `T080`.
- [ ] No task-ID-specific exception is added.
- [ ] Missing dependency validation remains fail-closed.
- [ ] Self-dependency validation remains fail-closed.
- [ ] DAG cycle validation remains fail-closed.
- [ ] Scheduler dispatch/integration behavior is unchanged.
- [ ] Product source is unchanged.
- [ ] Existing T084 candidate worktree is untouched.
- [ ] Legacy T008/T018/T027/T034 worktrees are untouched.
- [ ] Focused orchestrator regression tests pass.
- [ ] Full orchestrator test suite passes.
- [ ] Ruff passes.
- [ ] Ruff format check passes.
- [ ] Mypy passes.
- [ ] `git diff --check` passes.

## Verification commands

```bash
python -m pytest tests/orchestrator/test_core.py tests/orchestrator/test_scheduler.py -q --no-cov
python -m pytest tests/orchestrator -q --no-cov
python -m ruff check tools/orchestrator tests/orchestrator
python -m ruff format --check tools/orchestrator tests/orchestrator
python -m mypy tools/orchestrator
git diff --check
```

## Additional diagnostic evidence

The candidate must include a focused diagnostic or regression fixture demonstrating this logical input:

```text
## Dependencies

- [T081](t081-app-shell-shadcn-migration.md)
- [T015](t015-consent-api.md)
- [T017](t017-typed-api-client.md)
- [T052](t052-browser-test-harness.md)

This prose token is not a dependency:
BLOCKED_BY_T080_T081
```

The authoritative dependency result must be exactly:

```text
T015
T017
T052
T081
```

`T080` must not appear.

Do not require the real canonical `task_card(T018)` to complete successfully in the isolated T085 branch because canonical T081 still contains a separate legacy allowlist defect being normalized by the retained T084 candidate.

After T085 is integrated and T084 is reconciled onto the newer main, the combined state must allow the real `task_card(T018)` preflight to progress without the false T080 dependency.

## Files không được sửa

- `backend/*`
- `frontend/*`
- `contracts/*`
- `package.json`
- `orchestrator.yaml`
- `tasks/t018-consent-ui.md`
- `tasks/t080-shadcn-ui-foundation.md`
- `tasks/t081-app-shell-shadcn-migration.md`
- `tasks/t084-scheduler-admission-platform-baseline.md`

Do not modify any retained agent-run evidence or any other task implementation worktree.

## Legacy/candidate protection

T085 must not modify, reset, clean, stash, rebase, delete or adopt:

- `/home/khanh/projects/vocabularies-t084`
- T008 worktrees
- T018 worktrees
- T027 worktrees
- T034 worktrees
- retained T023 run/worktree evidence

T085 works only in its own worktree.

## Stop conditions

DỪNG và report blocker thay vì mở rộng scope nếu remediation yêu cầu:

- sửa task T018/T080/T081;
- sửa T084 candidate;
- sửa product source;
- thay đổi task-ID format;
- làm yếu dependency DONE/acceptance/file/verification enforcement;
- làm yếu missing-dependency/self-dependency/cycle validation;
- thay đổi scheduler dispatch hoặc integration semantics;
- thay đổi Pipeline/retry/worktree behavior;
- sửa unrelated repository metadata;
- destructive Git operations.

## Commit message đề xuất

`fix(T085): normalize task dependency parsing`

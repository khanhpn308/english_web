# Task [TXXX]: [Short title]

**Task ID:** `TXXX`
**Title:** [Short, single-purpose title]
**Status:** `TODO`
**Goal:** [One observable outcome. Do not describe an entire frontend/backend.]

**Estimated scope:** [One focused session, at most five handwritten source/config/test files; split if more than about two hours.]
**Suggested model:** [Gemini or GPT-6 Astra, with task-specific risk rationale.]

## Context cần đọc

- `CONSTRAINTS.md`
- `AGENTS.md`
- [Relevant spec/contract/ADR sections]
- [Relevant existing source/test files, once they exist]

## Dependencies

- [Task IDs, or `None`]

## Files được phép sửa

- [Explicit paths/globs]
- [Generated artifact path and generator owner, if applicable; never hand-edit generated DTO/schema]
- Common bookkeeping: this task card, tasks/todo.md, docs/changelogs.md and sanitized verification artifacts.

## Files không được sửa

- [Explicit paths/globs, especially secrets, unrelated modules and protected docs]

## Implementation notes

- [Boundary and design guidance]
- [Failure/security/observability considerations]
- [Do not invent behavior outside the cited contract]

## Acceptance criteria

- [ ] [Specific, observable condition]
- [ ] [Specific, observable condition]
- [ ] [Contract or security condition]

## Test cases

1. [Happy path]
2. [Validation/error path]
3. [Security/concurrency/offline path as applicable]

## Verification commands

Run from project root in the locked environment. Name the prerequisite task that creates each command. Missing tools or platform produce PENDING, not PASS. Documentation tasks use conformance reports; implementation tasks require real executable tests.

```text
[Exact commands after T001/T002 establish the toolchain]
```

## Expected output

- [Expected command result and artifact]
- [Actual command, exit code, environment, unchanged files, residual risk and next ready task]

## Risk

- **Level:** `Low | Medium | High | Critical`
- [Failure mode and mitigation]

## Stop conditions

- [Missing product decision, secret/access requirement, destructive operation, or failing constraint]

## Commit message đề xuất

`<type>: <why this task exists>`

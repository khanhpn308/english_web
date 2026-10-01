# ADR-0007: Owner-configured verification without model-declared planning gates

## Status

Accepted by explicit owner instruction on 01/10/2026: "bỏ luôn human_gates".
Complements ADR-0006's Python-owned orchestration. Supersedes T071's model-declared
planning/retry veto, not its contract, integrity, Git or verification checks.

## Date

01/10/2026 (`Asia/Bangkok`)

## Context

T059's baseline completed with every recorded exit code zero. Prompt Engineer then
introduced a human gate because a pre-existing T020 test reads a local vocabulary
file and Gitleaks scans the repository. The role prompt's blanket prohibition on
accessing user vocabulary conflicted with executing owner-configured checks. This
made independent tasks repeatedly wait for unrelated scope approval, defeating the
owner's requested autonomous workflow. A schema field let model reasoning directly
veto a routine state transition after executable baseline success.

## Decision summary

- Remove `human_gates` from new Contract/Plan schemas, templates and planning/retry
  conditions. Current model output remains strict; the retired field is not accepted
  as a new agent output or mapped to another model-controlled approval list.
- Repository-configured verification commands and redacted security scanners retain
  their owner-selected scopes. Running those existing read-only checks is authorized;
  a model must not invent per-task approval merely because they read local files.
  No test or scanner is skipped, narrowed or edited by this change. New fixtures
  remain synthetic. Agents must not manually inspect/copy user learning data or
  credentials into prompts, reports or fixtures, modify user data, expose secrets,
  call application AI providers or run real inference in automated tests.
- Read old saved Plan/Contract data through a narrow compatibility reader that
  validates the retired list and removes only that field in memory. Validate all
  other fields normally and check raw artifact hashes before reading; never rewrite
  old evidence. Old controllers may not understand new contracts; use updated code.
- Explicit retry may start a fresh run for unchanged pre-worker failures of the
  removed gate, including legacy phase metadata. Preserve previous runs/worktrees,
  rerun baseline and planning, and never replay their old blocked worker prompt.
- Python still rejects missing dependencies, out-of-scope paths, pinned contract
  drift, artifact/source/history changes, live locks, failed exit codes, false audit
  PASS, unsafe integration and uncertain active-stage recovery. Actual role BLOCKED
  reports remain possible for missing capability or unsafe/out-of-scope work; they
  are not generic planning approval steps.

## Alternatives considered

Retaining a configurable model approval toggle would leave an additional failure
mode and require operators to remember it per task. Ignoring all validation or
changing scanner/test scope would weaken evidence and was not requested. Editing
old artifacts to clear a gate would destroy provenance. These approaches are
rejected in favor of removing the field while preserving deterministic enforcement.

## Consequences

Existing checks can run without unrelated task edits or recurring human approval.
Model concerns belong in implementation reasoning, while executable evidence and
owner constraints remain authoritative. The automatic Worker/Auditor/fix cycle
remains bounded. Removal does not guarantee every task completes: real capability,
scope, test, integrity and Git failures still produce truthful BLOCKED outcomes.
The application consent/security policy and all product checkpoints are unchanged.

# ADR-0006: Deterministic local agent orchestration

## Status

Accepted for the explicitly authorized Level 1 development-infrastructure request,
implemented by T067–T070. This decision does not change the application's v1 AI
policy, provider admission, consent, persistence or public API.

## Date

01/10/2026 (`Asia/Bangkok`)

## Context

Manual copying between planning, implementation, review, remediation and integration
agents loses structured evidence and requires repeated human coordination. The owner
requires a small local Python orchestrator, resumable JSON state, separate Git
worktrees, replaceable Codex/Gemini CLIs and 1–3 independent processes. Integration
must be serialized. Existing Pydantic and Python development tools are available;
no database or heavy agent framework is authorized.

## Decision summary

- Python owns validated state transitions, paths, subprocess bounds, fix limits,
  immutable evidence, Git commits and promotion. Models supply reasoning through
  schema-validated role outputs and never decide routine state transitions.
- Persist each run under ignored `.agent-runs/Txxx/<run-id>/` using fsync and atomic
  replace. Pin original task constraints and artifact/source digests. Reject stale
  evidence and uncertain mutation replay on resume.
- Use outside task worktrees and separate integration candidates. Three local OS
  admission locks permit independent processes; task/run/worktree/integration locks
  protect their shared resources. The lock root stays repository-global regardless
  of artifact-path configuration. Integration lock contention leaves AUDIT_PASS
  pending instead of attempting a concurrent merge.
- Only promote a clean candidate's verified immutable SHA using ff-only target
  promotion. Disjoint target advances can be verified; overlapping drift/conflicts
  retain evidence and block for human adjudication. No destructive Git recovery.
- Reuse Pydantic without adding dependencies. `orchestrator.yaml` uses JSON syntax
  accepted by YAML 1.2 and parsed by stdlib JSON. Setup explicitly runs repository
  `npm ci` in new task/candidate worktrees; Python tools use the invoking environment.
- CLI capability probing uses installed local help. Codex review uses read-only;
  Gemini review uses plan approval mode. Trusted local agents are required: these
  approval settings plus diff checks do not isolate a malicious process from the
  user's filesystem. POSIX lock inheritance protects live CLI children after parent
  crash; Linux/WSL is the validated host, native Windows recovery remains unverified.

## Alternatives considered

A database-backed scheduler or LangGraph/CrewAI-style framework would add lifecycle
and coordination complexity beyond Level 1 and was explicitly excluded. LLM-selected
transitions would make recovery and authority implicit. A single global state file
would defeat independent concurrent task runs. Letting an agent merge directly would
weaken deterministic scope, evidence and promotion checks. These alternatives were
rejected in favor of explicit typed files and conservative Git ownership.

## Consequences

Local execution can replace manual role handoffs, with bounded automatic fix cycles
and serialized integration. It does not schedule a DAG, distribute jobs or resolve
architectural conflicts. Required shared changelog/todo changes can still cause
integration overlap and require human review. Interrupted active mutations block
rather than guessing whether to repeat. Stronger process isolation, native Windows
hard-crash validation, a scheduler/dashboard and distributed coordination are Level 2
work. Operational setup, commands and recovery are documented in
[the orchestrator guide](../orchestrator.md).

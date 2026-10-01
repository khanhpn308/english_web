# Level 1 local development orchestrator

This infrastructure replaces manual agent handoffs with validated files. It is
independent of the FastAPI/React application and adds no database or agent framework.
The implementation uses the existing Python/Pydantic toolchain. T067–T070 describe
its bounded implementation slices; product checkpoints retain their original owners.

## Architecture and decisions

`tools/orchestrator/core.py` owns strict state/contract/output models and atomic JSON
persistence. `runtime.py` owns subprocesses, local locks, Git and the replaceable
`AgentProvider` protocol. `workflow.py` owns deterministic transitions and role
execution. `__main__.py` provides the CLI. Namespace packages intentionally match
the existing repository; execute from the checkout root.

Prompt Engineer returns a `Plan` containing the contract and Worker prompt. Worker
returns `IMPLEMENTED` or `BLOCKED`. Auditor returns `PASS`, `FAIL` or `BLOCKED` with
one evidence entry for every original acceptance criterion. On FAIL, Prompt Engineer
returns a fix prompt and Worker retries in the same worktree, at most three times
by default. Integrator independently returns `READY` or `BLOCKED`; Python performs
commits, candidate merges, verification and target promotion. No model selects a
transition or directly merges into main. All role prompts, schemas and JSON results
are retained without manual message copying.

Python pins task identity, dependencies, base SHA, exact file scope, criteria,
verification commands, risk and stop rules to the original task card. Dependency
cards must be DONE, have completed criteria and existing owned source, and their
verification commands run again on the frozen base. This is direct dependency
validation, not a DAG scheduler. Unsupported card command syntax or directory/glob
allowlists block execution rather than inventing scope. Referenced documents and
source are inspected by the planning/review agents in their worktree.

Host checks run before audit and after integration. Non-zero exit, timeout, excessive
output, contradictory PASS, changed source/index or altered handoff artifacts block
promotion. Source digests include HEAD, staged diff, file contents and modes. Worker
claims are compared with the actual Git diff, including untracked and staged files.
Generated artifacts must use the task-owned generator; no public application API,
DB migration or generated client is changed by this infrastructure.

## Setup and configuration

Use the repository Python environment (Python 3.12+ and its existing dev dependencies),
Git, and separately installed/authenticated Codex and Gemini CLIs. Provider credentials
remain with those CLIs; this tool neither installs CLIs nor reads credential stores.
Provision the repository's npm dependencies and external security scanners before
real runs. Scanner environment overrides documented by T063 are inherited normally.
No real LLM requests are used by tests.

Locally inspected: Codex **0.159.2** before the pause and **0.159.3** on final
verification; Gemini CLI **0.59.0**. The required flags remain available.
These are evidence, not a compatibility guarantee for other versions. Each invocation
probes installed `--version`/`--help` and Codex `exec --help`; missing capabilities fail
clearly. Codex uses `-a never exec --ephemeral --sandbox`, `--output-schema`,
`--output-last-message`, optional `--model` and reasoning configuration; prompt input
is stdin. Gemini uses `--prompt`, `--output-format json`, `--approval-mode plan`
for review or `auto_edit` for implementation, and optional `--model`, with stdin context.
Gemini's JSON envelope and an exactly fenced JSON response are supported. It exposes
no reasoning-effort flag in this version: configure `reasoning: null`.

`orchestrator.yaml` is deliberately **JSON syntax (a YAML 1.2 subset)** parsed with
the standard library. Arbitrary YAML syntax is not accepted. This avoids an additional
runtime dependency. Set each role's `provider`, `executable`, `model` and `reasoning`;
`model: null` inherits the installed CLI's configuration and does not invent a model
name. Select an installed model explicitly for reproducible real runs. Defaults use
Gemini Worker and Codex planning/audit/integration. Providers can be replaced through
the typed protocol without rewriting the state machine.

Configuration also controls `base_branch` (local main), `max_fix_cycles` (0–10),
`timeout_seconds`, mandatory argv-array verification, `setup_commands`, run/worktree roots
and `integrate`. The default setup runs `npm ci` separately in each task worktree
and merged integration candidate; Python/dev tools are inherited from the invoking
environment. Level 1 setup accepts only this repository-native install command.
Dependency/setup failures stop with explicit evidence; no unchecked installer is invoked.
Run directories must be ignored and inside the repository; worktrees must be outside.
Relative paths are resolved against the canonical checkout, not the caller's worktree.
The default worktree root is `../english_web-worktrees`; no machine path is hardcoded.
The default gate includes `check:task`, Ruff and Mypy. Any inherited baseline failure
blocks a real run until remediated in its authorized scope; it is never called PASS.
Integration defaults off so installing infrastructure does not authorize future merges.

## Usage

```bash
python -m tools.orchestrator run T018 --dry-run
python -m tools.orchestrator run T018 --no-integrate
python -m tools.orchestrator status T018
python -m tools.orchestrator resume T018 --run-id <recorded-run-id>
# Explicitly authorize this task's local integration when the target checkout is ready:
python -m tools.orchestrator resume T018 --integrate
```

Use `--config <path>` to select another configuration. Status/resume select the latest
recorded run unless `--run-id` is supplied. Exit 0 means the requested operation
succeeded, including AUDIT_PASS awaiting integration; it does not necessarily mean
DONE. Exit 2 means refusal/BLOCKED/FAILED. Ctrl+C before pipeline ownership returns
130; interruption inside a stage records BLOCKED and returns 2.

Dry run reads task/dependency/config/Git evidence and prints the intended base,
branch, worktree, role routing, checks and flow. It creates no artifacts/worktrees,
invokes no LLM and changes no Git state. The configured local base must contain this
infrastructure commit and its required tooling; another invoking checkout does not
transplant source into new task worktrees. Integrate the reviewed infrastructure
through the repository workflow before starting real tasks against that base.
Actual execution requires a clean canonical
checkout and an ignored runtime root. Existing task worktrees (including manually
created task branches) cause refusal; inspect or resume instead of overwriting them.
Retained completed worktrees must be reviewed and explicitly removed manually before
starting a new run of the same task. The orchestrator has no destructive clean command.

For 1–3 independent tasks, start separate CLI processes. Each receives a unique
`agent/Txxx-<run-id>` branch, outside worktree and run directory. Repository-global
OS locks under `.agent-runs/.locks` admit at most three active processes, one per task,
and one integration at a time. These locks remain shared even with different run
roots. A fourth run or a competing same-task process refuses safely. A busy integration
lock leaves the task at AUDIT_PASS; run `resume --integrate` when it becomes available.
A lock failure after integration has started enters BLOCKED, preserving an uncertain
outcome rather than reporting pending. No background daemon retries it. Independent execution can proceed while another
integration runs, subject to local CPU/memory limits; run heavyweight gates sparingly.

## Artifacts and state

Each `.agent-runs/Txxx/<UTC-time>-<random-id>/` contains `state.json`, immutable
cycle-numbered task/plan/contract/worker/audit/fix reports, Worker prompt,
role prompts/output schemas/responses, JSON process logs, test evidence, integration
review/report and `final_report.md`. Prior cycles and failed evidence are retained.
Every authoritative JSON artifact is bound to its recorded digest; resumed Worker/fix prompts must equal their saved Plan/Fix.
State records original configuration, frozen base, worktree metadata, current agent,
fix count, timestamps, artifact names, source/contract digests and last failure.
State writes use a private temporary file, file fsync, atomic replace and POSIX
directory fsync; JSON parsing is bounded and strict. Per-run locks prevent concurrent
resume and partially shared state. Runtime files are gitignored and never committed.

Normal transitions:

```text
PENDING -> READY -> PLANNING -> PROMPT_READY -> WORKER_RUNNING
-> IMPLEMENTED -> AUDIT_RUNNING -> AUDIT_PASS -> INTEGRATION_RUNNING
-> MERGED -> VERIFYING -> DONE

AUDIT_RUNNING -> AUDIT_FAIL -> FIX_PROMPT_READY -> FIX_RUNNING
-> IMPLEMENTED -> AUDIT_RUNNING
```

`MERGED` refers to the isolated integration candidate, not target promotion.
Only a successfully verified candidate is promoted with an ff-only merge of its
exact SHA. Any unsafe stage enters BLOCKED; invalid transitions are rejected.
DONE, BLOCKED and FAILED are terminal. Contracts cannot weaken criteria or checks,
expand paths, or invent new product choices. Model-reported human gates block.

## Integration and recovery

The task branch remains uncommitted through implementation/audit. With integration
authorized, Python stages exactly audited files, checks staged scope/whitespace,
commits them, creates a dedicated candidate from the current local target, performs
a no-ff merge, verifies the resulting tree and promotes the immutable verified SHA.
The target must be checked out and clean. Disjoint target advances are supported;
overlapping drift, divergent ancestry, conflicts or changed target/candidate stop
and retain all work. No fetch, pull, reset, stash, force push or automatic conflict
resolution exists. Workers preserve the repository-required task-local card/todo/
changelog convention, so concurrent bookkeeping overlap may require human integration
review. No checkpoint is marked complete merely because an individual task passes.

Stable boundaries (READY, PROMPT_READY, IMPLEMENTED, AUDIT_FAIL, FIX_PROMPT_READY,
AUDIT_PASS) can resume after validating original configuration, task snapshot,
worktree identity and frozen evidence. Changing only the integration toggle is allowed.
An interrupted active agent, commit/merge or verification is uncertain: resume marks
BLOCKED instead of replaying a mutation. Inspect final/error and cycle artifacts,
Git index/history, candidate worktree and live CLI processes before human recovery.
BLOCKED cannot be cleared automatically or by editing state to pretend verification.
No previous evidence is silently overwritten.

POSIX locks are inherited by spawned CLI processes: killing the Python parent does
not release an integration/run lock while its direct CLI child remains live. Timeout
and Ctrl+C terminate the subprocess group; output monitoring enforces a 4 MiB bound
per stream, with polling overshoot possible. Native Windows uses byte-range locks and
taskkill for timeout; orphan inheritance after a hard parent crash is not verified.
Linux/WSL is the tested execution environment. Automatic native Windows integration
returns ENVIRONMENT_BLOCKED until its process-tree recovery semantics are independently validated; planning/implementation
may run with the documented native lock limitations.

Process results capture argv, cwd, timing, stdout/stderr, exit/timeout status in memory.
Persisted logs deliberately omit raw bodies/arguments and retain lengths/digests,
provider/model and exit metadata to avoid logging credentials or learning content.
Prompts and validated agent responses are necessary private handoff artifacts: use
synthetic task context, never credentials or real vocabulary payloads. INFO/STATE/
AGENT/GIT/TEST/ERROR messages support local diagnosis; no environment dumps are logged.

CLI approval modes and post-execution scope checks are **not a security boundary
against a malicious local agent**, especially Gemini `auto_edit`. Run trusted local
agents only. They share the user's filesystem/Git permissions; a hostile process
could alter Git metadata or ignore instructions before checks detect it. Stronger
OS isolation and native Windows hard-crash recovery belong to later infrastructure.

## Verification and limitations

```bash
python -m pytest tests/orchestrator -q
python -m ruff format --check tools/orchestrator tests/orchestrator
python -m ruff check tools/orchestrator tests/orchestrator
python -m mypy tools/orchestrator tests/orchestrator
npm run check:task
```

Tests use fake provider binaries and real temporary Git repositories, exercising
PASS, FAIL/fix/PASS, limits, process locks, three simultaneous independent runs,
worktree refusal, stale/contradictory evidence and crash behavior without paid calls.
Real provider authentication/model quality remains operational validation, not test
coverage. No application runtime depends on the orchestration package or CLIs.

Level 1 is local, synchronous per task, JSON-backed, limited to three cooperating
processes and serialized conservative integration. There is no database, dashboard,
distributed lock, scheduler, worker pool, automatic DAG scheduling or background
resume. State/provider/Git interfaces permit Level 2 scheduling and stronger isolation
without replacing role contracts. These features are intentionally deferred.

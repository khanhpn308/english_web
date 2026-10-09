## 09/10/2026 - T090 host-mediated Worker route (unverified implementation candidate)

- Added explicit opt-in host-http-edit Worker backend in tools/orchestrator/core.py and tools/orchestrator/workflow.py; default AGY CLI Worker remains blocked. Host applies constrained text proposals without giving the model shell/MCP/Git/Python tools, and blocks missing credentials before dispatch.
- Extended tools/orchestrator/worker_sandbox.py with loopback-only HTTP text completions (no tools, no redirects, no proxies), strict typed edit protocol, exact allowlisted source preimages and preflighted SHA-256 host edits.
- Extended tests/orchestrator/test_worker_sandbox.py and tests/orchestrator/test_workflow.py with synthetic malicious proposal and complete Pipeline handoff cases. Added operator/limitation documentation in docs/orchestrator.md and T090 task card.
- No live AGY/bridge isolation attestation performed. No default worker enablement, no historical T089 evidence changes, no security threshold weakening, no product source changes, no main merge. This candidate requires host CI on its final SHA.

## 09/10/2026 - T090 phase-2 CI R1 formatting remediation (Asia/Bangkok)

- Historical failed host CI run 37809494529 at candidate 148d94836ced11066225b6b87e107b42baa896d1 retained unchanged: Ruff format check caused check-fast-active FAIL; portable pytest, frontend coverage, all three security gates and architecture PASS; dependent coverage gate not reached.
- Reformatted three multiline calls in tests/orchestrator/test_worker_sandbox.py and one SHA validation conditional in tools/orchestrator/worker_sandbox.py to match pinned Ruff. Functional policy was not changed.
- Updated T090 card with exact failure provenance. A fresh independent CI run is required before making any acceptance claim. AGY/Codex live command-denial proof remains BLOCKED, T089 reopened; WorkerResult fail-closed guard untouched.
- No historical artifacts, product code, security thresholds, or default branch mutated.

## 08/10/2026 - T090 phase-2 historical-scope audit and host-mediated edit primitive (Asia/Bangkok)

- Status: IN_PROGRESS; Worker AGY/Codex dispatch remains BLOCKED; T089 remains REOPENED_PENDING_T090. No live provider isolation PASS and no new merge authorization claimed.
- docs/ci-host-verification.md: attributed eight historical out-of-T089-allowlist PR #5 infrastructure paths to immutable pre-/post-PR blob identities, ownership and explicit owner-approved historical merge. Clarified that prior passing CI verifies repository checks, not Worker tool isolation.
- tools/orchestrator/worker_sandbox.py: introduced a host-only exact-path, SHA-256-bound text edit primitive with checked preimage, content limit, path/symlink rejection and atomic file replacement. Does not grant or invoke AI tool privileges, and is not wired to a provider.
- tests/orchestrator/test_worker_sandbox.py: synthetic success/denial fixtures for host editing. Real AGY/OS command-denial tests remain unperformed and must not be inferred from these tests.
- tasks/t090-host-worker-isolation-scope-adjudication.md: documented the unverified provider boundary and next independent acceptance steps.
- Intentionally untouched: historical T089 artifacts/hashes and Git history, product backend/frontend, policy thresholds, worker permission lock and global CLI settings. Host CI status to be recorded only after a real run.

## 07/10/2026 - T089-R3: verified external candidate import control plane (Asia/Bangkok)

- Status: `IMPLEMENTATION_READY_FOR_HOST_VERIFICATION`. Implemented the host-authoritative verified external candidate import control plane (`import-candidate` CLI command and `Pipeline.import_candidate()`):
  - Architecture & Workflow:
    - Added separate host-owned command `import-candidate` importing an externally salvaged candidate into a fresh orchestrator-owned authoritative run without invoking any AI providers.
    - Historical lineage run remains strictly historical context: requires `FAILED` state (supporting failures originating from `FIX_RUNNING` and retaining `current_agent="worker"` without rewriting), base SHA match, contract validity, task card validity, and configuration compatibility. Fix budget (`fix_cycle` and `max_fix_cycles`) is preserved. Historical directory, state, and sealed artifacts remain byte-identical.
    - External source worktree must be a real Git worktree belonging to the same repository, with HEAD at historical `base_sha` and `Git.snapshot(base_sha)` matching `expected_source_digest`. Symlinks in worktree or ancestry are rejected.
    - Strict JSON decoding implemented (`strict_json_loads`) rejecting duplicate keys, trailing data, NaN, Infinity, -Infinity, and invalid UTF-8.
    - Bounded evidence capture enforces host limits: max 16 artifacts, 256 KiB single artifact limit, 2 MiB combined artifact limit, 256 KiB provenance manifest limit.
    - All 9 supported v1 artifacts (`source-manifest.txt`, `scout-A/B/C.packet.json`, `adjudication-packet[.compact].json`, `heavy-judge.prompt.txt`, `heavy-judge.schema.json`, `heavy-judge.response.json`) are captured, validated, and copied into the new run directory under flat sealed filenames (`00-imported-*`), guaranteeing independence from external `/tmp` evidence.
    - Complete semantic coverage enforced: `actual_changed_paths == source_manifest == union(scout A/B/C reviewed_files)` exact set equality. Any missing or extra path fails closed. Real T089 salvage (6 of 9 paths) correctly rejected.
    - Zero-findings v1 policy enforced: Scout findings empty, Adjudication finding count 0 with empty findings, Heavy Judge decision `PASS` with zero confirmed findings, dismissed findings, or evidence requests.
    - Authoritative reverification: Materializes into managed worktree, executes configured setup commands, and deterministically executes contract and config verification commands via `Pipeline.reverify_candidate`.
    - Atomic publication: Grants `AUDIT_PASS` with `audited_digest` and `verified_digest` atomically bound to the candidate digest only when BOTH mechanical and semantic gates pass.
    - Continuation & Control Plane Guard: `resume --no-integrate` stays at `AUDIT_PASS` with 0 AI calls. `resume --integrate` proceeds through Integrator and merges without re-running ReviewShard or Audit. CLI rejects resume execution from the candidate worktree, enforcing trusted control-plane execution.
  - Invariants Preserved:
    - `recover_candidate` semantics and tests have zero regressions.
    - Exactly 0 AI provider calls during import.
    - Real salvage worktree and historical failed T089 worktree untouched.
  - Verification & Tests:
    - Added full test suite in `tests/orchestrator/test_recovery.py` with synthetic fixture builder covering the entire 12-area test matrix (success, historical lineage, external source, provenance manifest, strict JSON, semantic coverage, zero-findings v1, evidence association, mechanical verification, copied evidence independence, control-plane guard & continuation, CLI).
  - Exact Files Modified:
    - `tools/orchestrator/recovery.py`
    - `tools/orchestrator/workflow.py`
    - `tools/orchestrator/__main__.py`
    - `tests/orchestrator/test_recovery.py`
    - `docs/orchestrator.md`
    - `docs/changelogs.md`

## 07/10/2026 - T089-R3 R5: separate trusted control plane from recovered candidate (Asia/Bangkok)

- Status: `PASS_FOR_FINAL_HOST_REVIEW`. Corrected trust model architecture to enforce execution from trusted host control plane while keeping recovered candidate purely as frozen candidate data:
  - Problem Remedied:
    - Recovery previously generated a handoff that cd'd into the recovered candidate worktree and ran `python -m tools.orchestrator resume ...`.
    - The CLI resume guard previously required `cwd` and loaded `__main__.py` to belong to the candidate worktree.
    - Because the candidate worktree is materialized exactly from historical frozen candidate source (which predates R2/R3 infrastructure remediation), running Python modules from the candidate bypassed trusted R2/R3 control-plane implementation (liveness watchdog, AgentStallError handling, bounded AuditorContextV1, attempt artifact sealing, stall retry, and recovery compatibility).
  - Implementation & Architecture:
    - `tools/orchestrator/recovery.py`: Added canonical helper `control_plane_root()` deriving the absolute resolved control-plane root from the loaded `tools.orchestrator` package.
    - Updated `RecoveryHandoff` model to distinguish `control_plane_cwd` (pointing to control plane) and `candidate_worktree` (pointing to candidate worktree), while retaining `cwd` (pointing to control plane) for backward compatibility.
    - Updated `recovery_handoff()` so `next_step` executes from `control_plane_cwd` (`cd -- <control_plane_cwd> && python -m tools.orchestrator resume ...`).
    - `tools/orchestrator/__main__.py`: Inverted CLI resume guard. Explicitly rejects execution from candidate worktree or using candidate Python modules (`control_plane == candidate_root or Path.cwd().resolve() == candidate_root`). Accepts resume when invoked from the trusted control plane even though `Path.cwd() != state.worktree_path`.
    - Preserved candidate identity: the candidate worktree remains strictly candidate data at the exact historical digest (`Git.snapshot(base_sha) == expected_source_digest`), with zero R2/R3 infrastructure source files injected.
    - The normal Pipeline continues operating on `state.worktree_path` for candidate Git operations, source operations, reviewer `cwd`, and Auditor `cwd`.
  - Invariants Preserved:
    - Frozen candidate identity, recovery source eligibility, `recovery_config_compatible()`, source/recovery config digests, liveness upgrade detection, normal resume config equality, typed `AgentStallError` classification, watchdog implementation, retry budgets, attempt artifact sealing, `AuditorContextV1`, 64 KiB context guard, fix-cycle preservation, historical source immutability.
    - Zero real provider/model/network calls.
    - Historical T089 runs and worktrees unmodified.
  - Regressions Added:
    - Added `test_end_to_end_control_plane_and_candidate_separation_regression` in `tests/orchestrator/test_recovery.py` demonstrating two distinct roots without monkeypatching `__file__`, verifying all 9 invariant points and subprocess-level rejection of candidate worktree invocation.
    - Updated CLI test to verify control-plane execution acceptance and rejection of candidate cwd/module invocation.
  - Exact Files Modified:
    - `tools/orchestrator/__main__.py`
    - `tools/orchestrator/recovery.py`
    - `tests/orchestrator/test_recovery.py`
    - `docs/orchestrator.md`
    - `docs/changelogs.md`

## 07/10/2026 - T089-R3 R3: liveness-only recovery configuration upgrade (Asia/Bangkok)

- Status: `PASS_FOR_HOST_VERIFICATION`. Narrowly scoped infrastructure compatibility remediation enabling recovery-time upgrade for host-owned Role liveness parameters:
  - Problem Remedied:
    - T089-R2 added opt-in watchdog parameters on `Role` (`stall_timeout_seconds`, `stall_confirm_seconds`, `max_stall_retries`) with historical runs defaulting `stall_timeout_seconds = None`.
    - Recovery previously enforced exact configuration identity (excluding only `integrate`), preventing historical runs from recovering with the watchdog enabled.
  - Implementation & Invariants:
    - `tools/orchestrator/recovery.py`: Implemented typed helper `recovery_config_compatible(source_config, recovery_config)` excluding only `integrate` and the three Role liveness fields (`stall_timeout_seconds`, `stall_confirm_seconds`, `max_stall_retries`).
    - Recovery strictly fails-closed against changes to provider, executable, model, reasoning, worker_access, allow_process, base_branch, paths, setup_commands, verification commands, global timeout_seconds, max_fix_cycles, skills_root, or role definitions.
    - Recovered `RunState` persists the new recovery configuration with upgraded watchdog parameters, ensuring subsequent normal `resume()` calls succeed under unmodified configuration equality. Normal `resume()` configuration equality was not weakened.
    - Extended `RecoveryOrigin` with deterministic SHA-256 digests (`source_config_digest`, `recovery_config_digest`) computed over sorted compact JSON and boolean `liveness_config_upgraded` via `is_liveness_config_upgraded()`.
  - Invariants Preserved:
    - All R2 invariants preserved: typed `AgentStallError` classification, liveness observation, stall confirmation, process-tree termination, orthogonal retry budgets, immutable attempt naming, `seal_attempt_artifacts` over `KNOWN_ATTEMPT_ARTIFACT_SUFFIXES`, terminal stall `current_agent = None`, bounded `AuditorContextV1` serialization, and attempt context artifact binding.
    - Historical source run, state, config, worktree, and sealed artifacts remain byte-identical.
    - 0 AI provider calls during recovery.
  - Exact Files Modified:
    - `tools/orchestrator/recovery.py`
    - `tests/orchestrator/test_recovery.py`
    - `docs/orchestrator.md`
    - `docs/changelogs.md`

## 07/10/2026 - T089-R3: unified recovery control plane reconciliation (Asia/Bangkok)

- Status: `IMPLEMENTATION_READY_FOR_HOST_VERIFICATION`. Ported T089-R host-authoritative `recover-candidate` control plane onto approved T089-R2 target baseline while strictly preserving all R2 invariants:
  - Preserved R2 Invariants:
    - Runtime liveness watchdog progress tracking and typed `AgentStallError` classification (no prose matching).
    - Independent stall retry budget (`Role.max_stall_retries`) and validation retry budget.
    - Immutable per-attempt artifact identity (`-a01`, `-a02`, ...) and `seal_attempt_artifacts` over `KNOWN_ATTEMPT_ARTIFACT_SUFFIXES`.
    - Authoritative bounded `AuditorContextV1` serialization, 64 KiB context guard, and attempt context artifact binding.
    - `current_agent = None` cleanup on terminal stall.
  - Recovery Behavior Ported:
    - CLI supports `recover-candidate TNNN --run-id SOURCE_RUN_ID --expected-source-digest SHA256`.
    - Host-authoritative eligibility validation: historical run must be `FAILED` from `AUDIT_RUNNING` with `current_agent is None`, registered worktree, unchanged base SHA, validated sealed artifacts, contract/task/worker handoffs, and matching expected source snapshot. Historical source run, artifacts, index, and worktree remain untouched.
    - Construction creates a fresh managed run and worktree at historical `base_sha`, materializes candidate via extracted 3-layer Git reproducer (`materialize_candidate`), executes clean configured setup commands, and binds immutable `RecoveryOrigin` (schema version 1) with advisory claim comparison digests.
    - Carries only validated pre-audit handoffs (`task_card`, `plan`, `contract`, `worker`, optional `skills`); historical audit, review, probe, and attempt artifacts are excluded.
    - Preserves `fix_cycle`, `max_fix_cycles`, task, contract, and candidate identity.
    - Transitions recovered run to `state = IMPLEMENTED, current_agent = None` invoking zero AI providers.
    - Exposes `recovery_handoff` in CLI output with cwd, branch, identity, and exact command ensuring recovered run is audited in candidate worktree.
  - Exact Files Modified:
    - `tools/orchestrator/__main__.py`
    - `tools/orchestrator/recovery.py`
    - `tools/orchestrator/workflow.py`
    - `tests/orchestrator/test_recovery.py`
    - `docs/orchestrator.md`
    - `docs/changelogs.md`

## 07/10/2026 - T089-R2D: typed stall classification and complete attempt artifact sealing (Asia/Bangkok)

- Remediation of final adversarial review findings for T089-R2:
  - R2C-F01 (Typed Stall Classification):
    - `tools/orchestrator/workflow.py`: Refactored stall classification in `Pipeline.invoke()` to strictly typed `is_stall = isinstance(error, AgentStallError)`. Removed all exception string/prose parsing fallback ("Agent process stalled" substring check). Enforced host-only liveness trust boundary where arbitrary model/error text cannot manufacture mechanical stall evidence or consume stall retries.
    - Added adversarial regressions proving non-AgentStallError containing "Agent process stalled" (both raw `OrchestratorError` and provider/validation error paths) is NOT classified as a stall, consumes 0 stall retries, and validation errors correctly consume validation retries.
  - R2C-F02 (Seal All Existing Attempt Artifacts):
    - `tools/orchestrator/core.py`, `tools/orchestrator/workflow.py`: Defined canonical `KNOWN_ATTEMPT_ARTIFACT_SUFFIXES` (`.prompt.md`, `.auditor-context.json`, `.schema.json`, `.response.json`, `.log.json`, `.rejected.json`).
    - Implemented single host-owned helper `seal_attempt_artifacts` (and `Pipeline._seal_attempt_artifacts`) used uniformly across: (1) terminal confirmed stall, (2) retryable failed attempts, and (3) successful attempts.
    - Inspects only the known fixed suffix set without arbitrary file globbing. For every existing regular non-symlink file, calculates digest, registers in `state.artifact_digests`, and adds to protected tracking. Forbids mutating or overwriting previously sealed artifacts.
    - Added regression coverage verifying that on terminal stall, prompt, auditor context (when applicable), schema (when present), log, and synthetic response (when present) are all sealed into `state.artifact_digests` matching exact bytes, with `state.current_agent = None` persisted to disk.
  - Verification:
    - 15 passed in focused workflow suite (`pytest tests/orchestrator/test_workflow.py -k "stall or attempt or auditor_context"`).
    - 8 passed in `pytest tests/orchestrator/test_runtime.py`.
    - 145 passed in `pytest tests/orchestrator/test_core.py`.
    - 188 passed in `pytest tests/orchestrator/test_workflow.py`.
    - 479 passed in full `pytest tests/orchestrator`.
    - `python scripts/check_constraints.py floor`: clean.
    - Ruff check, Ruff format, Mypy, and `git diff --check` all passed.

## 07/10/2026 - T089-R2B: attempt artifact identity, orthogonal retry budget, and authoritative auditor context binding (Asia/Bangkok)

- Remediation of independent semantic review findings for T089-R2:
  - R2B-001 (Attempt Artifact Identity):
    - `tools/orchestrator/workflow.py`: Every provider invocation attempt receives a unique immutable identity `<invocation_base>-a<attempt_index>` (`<fix-cycle>-<role>-<uuid>-a01`, `-a02`, ...).
    - Dedicated immutable per-attempt artifact paths for prompt (`<attempt_name>.prompt.md`), schema (`<attempt_name>.schema.json`), response (`<attempt_name>.response.json`), log (`<attempt_name>.log.json`), auditor context (`<attempt_name>.auditor-context.json`), and rejected responses (`<attempt_name>.rejected.json`).
    - Sealed prior-attempt artifacts are never overwritten. After each attempt ends, candidate source and protected artifacts are verified unchanged before sealing into `state.artifact_digests` and protected tracking.
    - Terminal confirmed stall reliably sets `state.current_agent = None` and persists `state.json` before raising `AgentStallError`.
  - R2B-002 (Orthogonal Retry Budget):
    - `tools/orchestrator/workflow.py`: Maintained independent counters and state machine logic for validation/execution retries (`validation_retries <= 2`, preserving historical 3 validation attempts) and stall retries (`stall_retries <= role.max_stall_retries`, configurable on `Role` from 0 to 10).
    - Confirmed stall attempts do not consume the historical validation retry allowance.
  - R2B-003 (Authoritative AuditorContext Binding):
    - `tools/orchestrator/workflow.py`: Dispatches final Auditor with a canonical immutable context artifact `<attempt_name>.auditor-context.json` containing exact UTF-8 bytes of `serialize_auditor_context(context)` and registered SHA-256 in `state.artifact_digests` and protected file tracking.
    - Preserved immutable context and distinct prompt artifacts across retries.
  - Tests:
    - `tests/orchestrator/test_core.py`: Added `test_auditor_context_binding_digests_and_persistence` verifying identical context produces identical digest, changed mandatory fields produce changed digest, persisted bytes match `serialize_auditor_context(context)`, and digest matches bytes.
    - `tests/orchestrator/test_workflow.py`: Updated `StallSimulationAgents` to write distinct per-attempt metadata; added regression tests for stall recovery with differing attempt artifacts without aliasing, stall not consuming validation retry allowance, configured `max_stall_retries` matching role contract (0 and 3), and auditor canonical context artifact binding and retry evidence.

## 07/10/2026 - T089-R2: agent liveness watchdog and bounded final-auditor context (Asia/Bangkok)

- Infrastructure remediation on top of frozen T089 candidate:
  - Addressed observed final-Auditor stall/hang incident by introducing an opt-in host-owned silence/stall watchdog and replacing redundant final-Auditor prompt construction with a bounded canonical typed context.
- Objective A: Provider Stall / Liveness Watchdog:
  - `tools/orchestrator/core.py`: Added `stall_timeout_seconds: StrictInt | None = None`, `stall_confirm_seconds: StrictInt = 30`, and `max_stall_retries: StrictInt = 1` to `Role`. Added `AgentStallError` inheriting `OrchestratorError`. Default `None` ensures full backward compatibility for historical configs and runs.
  - `tools/orchestrator/runtime.py`: Added `stalled: bool = False` to `ProcessResult` and exposed in `metadata()`. Implemented progress tracking via `os.fstat(fd).st_size` byte growth on stdout/stderr. Silence beyond `stall_timeout_seconds` triggers confirmation window `stall_confirm_seconds`; output growth cancels suspicion, while confirmed stall terminates entire process tree (`_terminate_process_tree`) across POSIX/Windows without leaving orphan subprocesses. `CliProvider.run` passes role stall settings and raises `AgentStallError` on confirmed stall.
  - `tools/orchestrator/workflow.py`: `Pipeline.invoke()` tracks stall retries separately bounded by `role.max_stall_retries` (default 1 retry). When stall retry budget is exhausted: verifies source and protected artifacts are unchanged, seals `{name}.log.json` into `state.artifact_digests`, sets `current_agent = None`, and raises `AgentStallError` persisting `state = FAILED`, `blocked_from = <active stage>`, `current_agent = None`.
- Objective B: Bounded Final Auditor Context:
  - `tools/orchestrator/core.py`: Added `AuditorCandidateIdentity`, `AuditorContract`, `AuditorWorkerSummary`, and canonical `AuditorContextV1` (aliased as `AuditorContext`). Defined `AUDITOR_CONTEXT_MAX_BYTES = 64 * 1024` (64 KiB operational budget). Added deterministic serialization `serialize_auditor_context()` (sorted keys, compact separators), `auditor_context_digest()`, component size breakdown `auditor_context_component_sizes()`, and `check_auditor_context_size()` which fails closed with `AuditorContextOversizedError` consuming 0 provider attempts.
  - `tools/orchestrator/workflow.py`: Implemented `build_auditor_prompt()`, structuring final Auditor prompt with stable role rules, output schema, required skills, and one serialized `AuditorContextV1`. Explicitly excluded raw Plan, `TaskCard.context_text`, duplicate TaskCard, `WorkerResult.commands_run`, raw verification output, and duplicate ReviewBundle.
- Tests:
  - `tests/orchestrator/test_runtime.py`: Added 8 tests covering `timeout=None` without deadline, watchdog disabled backward compatibility, silent subprocess confirmed stall, progressing output liveness reset, suspected stall recovery during confirmation, process-tree termination with orphan reaper verification, diagnostic metadata distinction, and CliProvider stall exception.
  - `tests/orchestrator/test_core.py`: Added tests for Role stall watchdog configuration defaults and parsing, ProcessResult stalled diagnostic metadata, AuditorContextV1 construction and canonical fields, deterministic serialization and digest, 64 KiB size guard boundary and diagnostics, and Audit JSON Schema validity.
  - `tests/orchestrator/test_workflow.py`: Added tests for stall single retry recovery, terminal stall retry exhaustion (`current_agent=None`, sealed log evidence, candidate unchanged), Auditor bounded prompt construction, and oversized context fail-closed consuming zero provider calls.

## 06/10/2026 - T089: evidence-aware reviewer protocol and safe probe execution (Asia/Bangkok)

- Control plane / host safe probe execution and reviewer protocol:
  - Enforced trust boundary: AI semantic reviewers and auditor are strictly read-only and restricted to candidate-bound evidence. Host owns the `ProbeCatalog` and command execution; arbitrary model-supplied shell/argv/commands are strictly forbidden (`extra="forbid"`, forbidden override keys check, safe path containment).
  - Preserved T087 concurrent verification: initial reviewer fan-out runs concurrently with verification (`verification_status="PENDING"`). Initial reviewers cannot claim unfinished verification as authoritative evidence.
  - Final Auditor receives complete validated `EvidenceBundle.semantic_payload()` alongside `ReviewBundle` and accepted `ProbeEvidence`. Mechanical verification failures cannot be overridden by an Auditor PASS (fails closed).
- `tools/orchestrator/core.py`:
  - Added strict Pydantic models: `ProbeRequest` (`probe_id`, `target_path`, `query`, `candidate_digest`, `params`, optional `rationale`), `ProbeEvidence` (bound to frozen candidate identity, `source_digest`, `status`, `classification`, structured results/summary, byte limit, runtime monotonic duration), `ReviewerContext` (structured context schema for round-1 and resumed round-2 reviewers).
  - Updated `ReviewShard` to carry optional `probe_request: ProbeRequest | None = None`.
  - Added `FORBIDDEN_PROBE_OVERRIDE_KEYS = frozenset({"command", "argv", "cmd", "shell", "executable", ...})` and `probe_request_digest()`.
- `tools/orchestrator/probes.py`:
  - Implemented repository-owned `ProbeCatalog` and `ProbeDefinition` with safe immutable registry.
  - Built default probes: `source_inspection` (pure Python bounded file reading and regex/string search within allowlist) and `git_diff_check` (predefined non-configurable executable probe running `git diff --check`).
  - Implemented `execute_probe`: verifies frozen candidate identity, detects stale candidate changes (fails closed), enforces strict output size limits (`max_output_bytes`), execution timeouts, path containment, and prevents mutation of authoritative task sources.
- `tools/orchestrator/workflow.py`:
  - Wired structured `ReviewerContext` into `_review_phase()`.
  - Added bounded 1-round reviewer probing: reviewers requesting probes are resumed exactly once with structured `ProbeEvidence`. Attempted second probe rounds are rejected.
  - Deterministic fan-in: multiple reviewer probe requests/results fan in canonically (`CORRECTNESS` -> `VERIFICATION` -> `SECURITY`) independent of completion order.
  - Parent remains sole authoritative state/artifact writer (`probe_<perspective>` and `review_bundle` persisted by parent).
  - Wired complete `EvidenceBundle.semantic_payload()` and accepted probe artifacts into final Auditor prompt and context.
  - Enforced mechanical verification failure check: if mechanical verification failed, Auditor PASS is rejected and run fails closed.
- `tests/orchestrator/test_probes.py`:
  - Added 44 comprehensive unit and adversarial security tests covering: schema validation, forbidden override keys (`command`, `argv`, etc.), path traversal, external absolute paths, shell metacharacter payloads, catalog immutability, execution of `source_inspection` and `git_diff_check`, candidate tampering, stale candidate detection, output size limits, timeouts, authoritative source immutability, out-of-order completion canonical ordering, and second-round rejection.
- `tests/orchestrator/test_workflow.py`:
  - Added 5 end-to-end integration tests: `test_reviewer_probe_execution_and_resume_flow`, `test_reviewer_second_probe_round_rejected`, `test_reviewer_probe_stale_candidate_fails_closed`, `test_auditor_cannot_override_mechanical_verification_failure`, and `test_multiple_reviewers_request_probes_canonical_ordering`.
- `docs/orchestrator.md`:
  - Documented evidence-aware reviewer protocol, `ReviewerContext`, `ProbeRequest`, `ProbeEvidence`, `ProbeCatalog`, and fail-closed security invariants.
- Verification:
  - 44 tests in `test_probes.py` pass.
  - 59 tests in focused probe/reviewer/evidence suite pass.
  - 48 tests in concurrent_audit pass.
  - 30 tests in parallel_review pass.
  - 48 tests in scheduler pass.
  - 447 tests in full orchestrator pass.
  - Ruff check, Ruff format, Mypy, and `git diff --check` all pass.
  - Canonical T089 status advanced to DONE.
  - No product source or provider/model defaults changed.

## 06/10/2026 - T088 authoritative host verification closeout

- EvidenceBundle focused regression: 21 passed, 311 deselected.
- Concurrent audit regression: 43 passed, 262 deselected.
- Parallel review regression: 25 passed, 280 deselected.
- Scheduler regression: 48 passed.
- Full orchestrator regression: 398 passed.
- Ruff check: PASS.
- Ruff format check: PASS.
- Mypy: PASS.
- git diff --check: PASS.
- Canonical T088 status advanced to DONE.
- No production source, provider/model defaults, scheduler/runtime semantics or product behavior changed.

## 06/10/2026 - T088 remediation R1: frozen evidence identity, completeness and timing (Asia/Bangkok)

- Independent semantic audit: `NEEDS_REMEDIATION`, with HIGH verification/candidate source binding, HIGH required-command completeness, and MEDIUM diagnostic timing semantics. Earlier T088 notes overstated those properties and are corrected below.
- `tools/orchestrator/core.py`: immutable typed `FrozenEvidenceIdentity` binds task/base/branch/source and ordered canonical argv SHA-256 manifest. Requests validate declarations, collections retain identity, and bundles/artifact references validate association. Strict required execution metadata and exact result-order/completeness checks reject successful prefixes while preserving explicit failed prefixes. Semantic payload excludes all direct diagnostic timing, including command duration.
- `tools/orchestrator/evidence.py`: reject verification/current provenance mismatch, unbound/mismatched references and historical audit_checks source/result substitution. Validate existing artifact source metadata and bind historical declaration association through authoritative typed metadata without changing artifact contents. Preserve path containment, hash/size checks, privacy and schema version 1.
- `tools/orchestrator/workflow.py`: measure execution using `time.monotonic_ns()`, retain frozen request identity through collection, validate before parent persistence, preserve historical audit_checks format, and validate current source digest in the accessor. Reviewer fan-out, private verification workspace, authority and provider boundaries stay unchanged.
- `tests/orchestrator/test_core.py`, `tests/orchestrator/test_evidence.py`, `tests/orchestrator/test_workflow.py`: regressions for frozen A-to-B mismatch using real Git/source fixtures, incomplete successful prefix, explicit failed prefix, declaration substitution after redaction, missing mandatory metadata, timing-only equality, monotonic timing with backward wall-clock metadata, source digest on access/load, result order and historical artifact association.
- `docs/orchestrator.md`, `tasks/t088-deterministic-evidence-bundle.md`, `tasks/todo.md`: record the semantic audit and R1 implementation status. Documentation follows documentation-and-adrs and unslop.
- Agent-local diagnostics: evidence tests 27 passed; manifest-revalidation follow-up 1 passed; selected core/workflow 15 passed, 290 deselected; Ruff check/format, Mypy on 3 source files and diff-check PASS. Exact commands/outcomes are recorded in the task card. Earlier diagnostic fixture/exception expectation, formatting/import and decorated-validator type failures were corrected. No full orchestrator, scheduler, T086 full or T087 full regression was run by the implementation agent.
- Intentionally untouched: runtime/scheduler/CLI/configuration, package/lockfiles, gates, constraints, backend/frontend and T086/T087 task cards. No Git finalization. Candidate remains uncommitted at HEAD `80163a5cc7692ec741166eed12d1fa32a0f7ad41` on `feature/t088-deterministic-evidence-bundle`.
- Status: `R1 IMPLEMENTATION_READY_FOR_HOST_VERIFICATION`. Host verification remains pending; no integration verdict, T023 speedup or Herdr integration is claimed. No unresolved implementation issue; next action is owner/host targeted probes and authoritative deterministic verification.

## 06/10/2026 - T088: deterministic evidence collection and EvidenceBundle (Asia/Bangkok)

- Control plane / host deterministic evidence subsystem:
  - Enforced architectural principle: if correctness can be determined from exit codes, Git/filesystem state, hashes, schema validation, deterministic parsing, or predefined tests, AI must not be in that execution or decision loop.
  - Subsystem executes entirely within host Python logic with 0 AI provider calls, 0 CLI provider calls, and 0 Pipeline.invoke calls. No model decides which commands to run and no arbitrary AI-generated commands are permitted.
- `tools/orchestrator/core.py`:
  - Added strict Pydantic models with `extra="forbid"`:
    - `EvidenceArtifactRef`: captures name, relative path, SHA-256 digest, byte size, classification, and optional summary with `safe_path` enforcement.
    - `CandidateProvenance`: bound to `base_sha`, `branch`, `source_digest` (matching `Git.snapshot(base_sha)`), `head_sha`, and distinguishes all 3 candidate Git layers: staged/index (`staged_paths`, `staged_diff_digest`), unstaged working tree (`unstaged_paths`, `unstaged_diff_digest`), and non-ignored untracked files (`untracked_paths`, `untracked_digest`). Canonical sorting and uniqueness enforced.
    - `ScopeEvidence`: captures `allowed_paths`, `actual_changed_paths`, `unexpected_changed_paths`, and `verdict` (`PASS` | `FAIL`). Fails closed on unexpected changed paths.
    - `VerificationCommandEvidence`: captures declaration order (`command_index`), command identity with withheld arguments, exit code, timeout/oversize status, digests, bytes, duration, and failure classification. Raw unbounded stdout/stderr is strictly forbidden.
    - `VerificationEvidence`: aggregates verification command results, enforcing declaration order, failure classification, and ensuring setup errors or failed commands cannot be misreported as PASS.
    - `TimingEvidence`: captures monotonic duration (`time.monotonic_ns()`) for diagnostics only; timing does not alter PASS/FAIL verdicts.
    - `EvidenceBundle`: versioned (`schema_version: Version = 1`), strictly validated, fail-closed completeness check (`check_completeness`, `is_complete: Literal[True] = True`). Initial `semantic_payload()` excluded top-level timing but retained command durations; the independent audit required R1 correction.
- `tools/orchestrator/evidence.py`:
  - Implemented `collect_candidate_provenance`: deterministically extracts Git metadata and patches across staged index, unstaged working tree, and untracked files.
  - Implemented `collect_scope_evidence`: deterministically validates changes against task allowlist without AI assistance; unexpected paths fail closed.
  - Implemented `collect_verification_evidence`: maps executable verification collection to structured command evidence while preserving declaration order.
  - Implemented `create_artifact_ref` & `validate_artifact_ref`: validates safe relative path, non-symlink, regular file, boundary containment, byte size, and SHA-256 digest. Tampering is behaviorally detected and fails closed.
  - Introduced `build_evidence_bundle` with top-level monotonic timing and canonical ordering; independent semantic audit found source-binding and command-completeness defects, addressed in R1.
  - Implemented `validate_evidence_bundle`: validates schema, candidate bindings (base_sha, branch, source_digest), and all referenced artifacts.
- `tools/orchestrator/workflow.py`:
  - Parent-only authority: in `concurrent_audit` (`_review_phase`), parent persists and registers `evidence_bundle` in `state.artifacts` alongside existing `audit_checks` artifact. Worker threads and reviewer threads have zero artifact registration authority.
  - Added `evidence_bundle(directory, state)` accessor to `Pipeline` verifying artifact integrity, base SHA and branch. Expected source-digest validation was missing until R1.
  - Preserved 100% backward compatibility with `audit_checks`. Reviewer prompts and schemas remain untouched; ProbeRequest and reviewer protocol rewrite deferred to T089.
- `tests/orchestrator/test_core.py`:
  - Added unit tests for schema/version validation, provenance ordering, scope validation, verification integrity, artifact reference rules, and bundle completeness fail-closed checks.
- `tests/orchestrator/test_evidence.py`:
  - Added 11 focused behavioral tests: host-only construction (0 provider/Pipeline calls), candidate provenance binding, staged/unstaged/untracked layer distinction, untracked identity preservation, scope calculation and unexpected path fail-closed, declaration order preservation, failure representation, setup failure fail-closed, artifact reference creation and tamper detection, path escape rejection, bundle validation mismatches, shuffled input canonical ordering, and thread completion order invariance.
- `tests/orchestrator/test_workflow.py`:
  - Added `test_concurrent_audit_evidence_bundle_persistence_and_parent_authority` verifying parent-only bundle registration, accessor validation, artifact referencing, and tamper detection alongside `audit_checks`.
- `docs/orchestrator.md`, `tasks/t088-deterministic-evidence-bundle.md`, `tasks/todo.md`: documented T088 EvidenceBundle architecture, updated status to `IMPLEMENTATION_READY_FOR_HOST_VERIFICATION`.
- Status: `IMPLEMENTATION_READY_FOR_HOST_VERIFICATION`.

## 05/10/2026 - T087 remediation R4: eliminate writable external symlink backlinks (Asia/Bangkok)

- Independent audit findings & verdict:
  - R3 independent audit verdict: `NEEDS_REMEDIATION`.
  - HIGH finding: external regular-file symlink write-through violated private sandbox invariant (`sandbox/node_modules/pkg/link.js -> external host toolchain file` allowed writes through the sandbox symlink to mutate the host file).
  - Explicit statement: Candidate remains pending independent re-audit. Do NOT claim `PASS_FOR_INTEGRATION` or T023 speedup until independent R4 audit actually passes.
- `tools/orchestrator/workflow.py`:
  - Updated `materialize_private_toolchain`:
    - Enforced central security invariant: NO WRITABLE EXTERNAL BACKLINKS. Every path reachable by ordinary toolchain traversal must resolve inside `verification_workspace` or fail closed before lane dispatch.
    - External regular files in `node_modules` (and any non-interpreter external files in `.venv`): FAIL CLOSED before dispatch (`OrchestratorError: Unsafe external file symlink in toolchain: <path> -> <target>`).
    - External directory symlinks: FAIL CLOSED before dispatch (`OrchestratorError: Unsafe external directory symlink in toolchain`).
    - Virtualenv interpreter: materialized as a private executable copy in the sandbox via `shutil.copy2` (preserving `0o755` executable permissions, virtualenv semantics, package resolution, and distinct inode without hardlinks or backlinks).
    - Post-materialization containment validation pass (`verify_dst_containment`): recursively walks `dst_root` and asserts every symlink resolves to an existing target inside `dst_root.resolve()`; escapes and dangling symlinks fail closed.
    - Early dangling symlink detection in `copy_dir`: `not target_canonical.exists()` fails closed immediately.
- `tests/orchestrator/test_workflow.py`:
  - Added `test_concurrent_audit_private_toolchain_external_regular_file_symlink_reproduction`: exact behavioral reproduction of the audit exploit; proves external regular-file symlinks fail closed before dispatch with original external host file contents, inode, and mtime 100% unchanged, and proves pre-dispatch failure produces 0 verification calls, 0 reviewer calls, 0 ReviewBundle creation, and 0 Auditor calls.
  - Added `test_concurrent_audit_private_toolchain_external_directory_symlink_fails_closed`: proves external directory symlinks fail closed before dispatch with 0 lane dispatches.
  - Added `test_concurrent_audit_private_toolchain_nested_symlink_chain_cannot_escape`: proves multi-hop and relative symlink chains escaping the toolchain fail closed.
  - Added `test_concurrent_audit_private_toolchain_symlink_loop_fails_closed`: proves circular symlink loops fail closed.
  - Added `test_concurrent_audit_private_toolchain_dangling_symlink_fails_closed`: proves broken symlinks fail closed.
  - Added `test_concurrent_audit_private_toolchain_venv_non_interpreter_external_symlink_fails_closed`: proves non-interpreter external symlinks in `.venv` fail closed before dispatch.
  - Strengthened `test_concurrent_audit_private_toolchain_real_venv_package_preservation`: asserts sandbox python resolves inside `verify_path/.venv`, does not resolve to worktree or repo, has distinct inode from host python, and executes `import pytest`.
  - Strengthened `test_concurrent_audit_private_toolchain_copy_write_isolation`: asserts modifying existing files in `verify_path/node_modules` and `verify_path/.venv` leaves host files completely untouched.
- `docs/orchestrator.md`, `tasks/t087-concurrent-audit-preparation.md`, `tasks/todo.md`: documented R4 architecture, audit reconciliation, and handoff evidence.
- Status: `R4 IMPLEMENTATION_READY PENDING INDEPENDENT RE-AUDIT`.

## 05/10/2026 - T087 remediation R3: private toolchain materialization (Asia/Bangkok)

- Independent audit findings addressed (six findings):
  1. HIGH 1: Shared writable `node_modules` root is inherently unsafe (`verification_workspace/node_modules/../.pytest_cache/transient` escapes through root symlink into authoritative source; `node_modules -> reviewer_worktree/.pytest_cache` passed previous validation).
  2. HIGH 2: Symlink graph inspection fails open when `os.scandir()` raises `OSError` or `PermissionError`.
  3. MEDIUM 3: Registered worktree discovery corrupted valid paths because `.strip()` stripped trailing spaces, and discovery exceptions were silently ignored.
  4. MEDIUM 4: Shell launcher interpolation of `real_python` permitted command substitution.
  5. MEDIUM 5: Selected `real_python` was not reliably rejected when residing inside an authoritative root.
  6. MEDIUM 6: Resolving a venv interpreter to system Python loses the virtual environment and its installed packages.
  - Explicit statement: R2's claim of complete toolchain isolation was invalidated by independent audit. Candidate remains pending independent re-audit. No claim of `PASS_FOR_INTEGRATION` or T023 speedup.
- `tools/orchestrator/workflow.py`:
  - Complete removal of writable toolchain sharing and launcher shell scripts.
  - Implemented `materialize_private_toolchain(src_root, dst_root, auth_roots, toolchain_name, repo_root, working_root)`: materializes real directories for `node_modules` and `.venv` in the temporary verification workspace. Copies regular files with permissions (no hardlinks). Rewrites internal symlinks to relative links strictly within the private copied tree. Validates external symlinks so they can only be retained if pointing to a system file outside all authoritative roots. External directory symlinks and backlinks to authoritative roots fail closed (`OrchestratorError`). All inspection/copy operations fail closed on `OSError`/`PermissionError`.
  - Updated `authoritative_roots(working)`: queries `git worktree list --porcelain -z` with NUL delimiter parsing without whitespace stripping (`.strip()`), preserving exact trailing spaces, and fails closed on git failures or malformed records.
  - Implemented deterministic argv-based `verification_command_argv(cwd, command)`: executes `/usr/bin/env PATH=... <command...>` prepending `verify_path/.venv/bin` and `verify_path/node_modules/.bin` to `PATH` without mutating `os.environ` globally and without shell string parsing.
  - Updated `collect_verification`: executes commands with private toolchain environment and redacts command metadata to preserve original command identity (`python`, `npm`), avoiding misleading `env` reporting.
- `tests/orchestrator/test_workflow.py`:
  - Updated `concurrent_audit_pipeline` fixture to unwrap private `env` prefix when resolving check names.
  - Updated `_ignore_toolchains` helper to ignore both bare names and directory patterns so git ignores toolchain symlinks.
  - Added test 7A: `test_concurrent_audit_private_toolchain_root_symlink_parent_traversal` proving `verify/node_modules/..` resolves to `verify_path` and parent traversal cannot reach reviewer worktree.
  - Added test 7B: `test_concurrent_audit_private_toolchain_node_modules_root_alias` proving symlinked root alias to non-toolchain paths fails closed before dispatch.
  - Added test 7C: `test_concurrent_audit_private_toolchain_unreadable_directory_fails_closed` proving unreadable toolchain subtrees fail closed before dispatch with 0 lane dispatches.
  - Added test 7D: `test_concurrent_audit_root_discovery_whitespace_sensitive_and_failure` proving exact preservation of trailing spaces in worktree paths, backlink rejection, and discovery failure fail-closed semantics.
  - Added test 7E: `test_concurrent_audit_private_toolchain_no_shell_launcher_or_injection` proving absence of shell launchers and immunity to command injection.
  - Added test 7F: `test_concurrent_audit_private_toolchain_real_venv_package_preservation` executing real subprocess `.venv/bin/python -c "import pytest; print(pytest.__version__)"` inside the private sandbox.
  - Added test 8: `test_concurrent_audit_private_toolchain_copy_write_isolation` proving sandbox toolchain writes do not alter host/reviewer/repo toolchains.
  - Added `test_concurrent_audit_private_toolchain_internal_symlinks_preserved` proving internal symlink rewriting and isolation.
- `tests/orchestrator/test_core.py`:
  - Updated `test_concurrent_audit_collection_detached_inputs_and_failure_semantics` to verify argv-based env execution and private PATH precedence.
- `docs/orchestrator.md`, `tasks/t087-concurrent-audit-preparation.md`, `tasks/todo.md`: documented R3 architecture, audit reconciliation, and handoff evidence.
- Verification: focused private toolchain 7 passed (2.37s); root discovery 1 passed (0.66s); transient boundary 3 passed (1.93s); materialization 2 passed (0.57s); focused T087 36 passed, 255 deselected (16.21s); T086 selection 25 passed, 266 deselected (33.63s); scheduler 48 passed (14.07s); full orchestrator 357 passed (268.26s / 4m28s), exit 0; Ruff check/format (10 files), Mypy (6 source files), and `git diff --check` PASS. Uncommitted candidate, starting/current HEAD `20447177c48a556d63709906cb8c953142f62e4b`, branch `feature/t087-concurrent-audit-preparation`. No commit, merge, push, reset, clean, or rebase. Product source, scheduler, runtime, orchestrator.yaml, package.json untouched.

## 05/10/2026 - T087 remediation R2: close toolchain backlinks and preserve index/worktree state (Asia/Bangkok)

- Independent audit findings addressed:
  1. HIGH: shared writable toolchain symlinks contained nested links back into the authoritative reviewer/task worktree (`node_modules/local-candidate/.pytest_cache/transient` -> `reviewer_cwd/.pytest_cache/transient`), leaking transient verification output into ReviewShard/ReviewBundle/Auditor while snapshot checks passed because output was ignored.
  2. MEDIUM: verification workspace materialization previously collapsed distinct staged and working contents by copying working bytes and running `git add -A`.
- `tools/orchestrator/workflow.py`:
  - Implemented `Pipeline.authoritative_roots` resolving repository root, task worktree root, and any additional git worktrees discovered via `git worktree list --porcelain`.
  - Implemented `validate_toolchain_backlinks(toolchain_root, authoritative_roots)`: recursively traverses symlink graph of shared toolchain with cycle detection (`visited_dirs`) and loop handling (`RuntimeError`/`OSError`). Canonicalizes each symlink and asserts its target does not resolve into any authoritative source root outside `toolchain_canonical`, raising `OrchestratorError` fail-closed before concurrent dispatch.
  - Safe `.venv` protection: host refuses to expose writable `.venv` tree into verification workspace; validates `.venv` backlinks and real Python binary, then generates an isolated launcher proxy script (`.venv/bin/python` / `Scripts/python.exe`) that executes the validated Python directly without write-through backlinks into authoritative roots. Both `.venv` and `node_modules` are excluded via `.git/info/exclude`.
  - Two-layer materialization: clones `--shared --no-checkout` at `base_sha` detached; reproduces Git index via `git apply --binary --index` on staged diff (`git diff --cached --binary base_sha --`); reproduces working-tree state via `git apply --binary` on unstaged diff (`git diff --binary --`); copies non-ignored untracked files (`git ls-files --others --exclude-standard -z`) with byte contents and execution modes (`chmod`) while keeping them untracked (no `git add`).
  - Pre-dispatch snapshot equivalence and post-verification sandbox integrity asserted against frozen candidate source digest.
- `tests/orchestrator/test_workflow.py`:
  - Added `test_concurrent_audit_toolchain_unsafe_backlink_fails_closed`: proves nested `node_modules/local-candidate -> reviewer_cwd` fails closed before dispatch with 0 reviewer cwds, 0 verification cwds, no ReviewBundle, and no Auditor.
  - Added `test_concurrent_audit_toolchain_safe_shared_toolchains_work`: proves safe shared `node_modules` and safe `.venv` launcher proxy pass all lanes and invoke Auditor.
  - Added `test_concurrent_audit_materialization_distinct_staged_and_working_content`: asserts verification workspace faithfully preserves distinct staged index (`value 1`) and working tree (`value 2`) contents on the same tracked file, with snapshot equivalence.
  - Added `test_concurrent_audit_materialization_binary_mode_and_deletion`: proves binary changes, staged deletions, unstaged deletions, file mode changes (`0o755`), non-ignored untracked files, and ignored transient files are correctly handled.
- `tests/orchestrator/test_core.py`:
  - Added `test_concurrent_audit_toolchain_backlink_validation_rules`: verifies `validate_toolchain_backlinks` rules for clean trees, internal symlinks, root escapes, direct backlinks, `../` escapes, external nested links, and circular symlink loops.
- `docs/orchestrator.md`, `tasks/t087-concurrent-audit-preparation.md`, `tasks/todo.md`: documented R2 toolchain backlink validation, safe venv proxy, exact two-layer materialization, and handoff evidence.
- Verification: toolchain tests 3 passed (1.95s); materialization tests 2 passed (0.59s); transient boundary tests 3 passed (1.77s); focused T087 28 passed, 255 deselected (13.20s); T086 selection 25 passed, 250 deselected (31.92s); scheduler 48 passed (11.05s); full orchestrator 349 passed (256.39s), exit 0; Ruff check/format (10 files), Mypy (6 source files), and `git diff --check` PASS. Uncommitted candidate, starting/current HEAD `20447177c48a556d63709906cb8c953142f62e4b`, branch `feature/t087-concurrent-audit-preparation`. No commit, merge, push, reset, clean, or rebase. Product source, scheduler, runtime, orchestrator.yaml, package.json untouched.

## 05/10/2026 - T087 remediation R1: enforce frozen review evidence boundary (Asia/Bangkok)

- Independent audit finding addressed: previously, reviewers and verification ran in the same worktree, allowing ignored transient verification output (`.pytest_cache/transient`) to be observed by reviewers, entering ReviewBundle/Auditor and shifting stable source finding IDs from `:0001` to `:0002` depending on completion order.
- `tools/orchestrator/workflow.py`: implemented `Pipeline.verification_workspace` context manager providing an isolated temporary Git verification workspace checked out at `base_sha` detached, overlaid with candidate changes, deletions, file modes, and non-ignored untracked files. Toolchain paths (`node_modules`, `.venv`) shared via symlinks excluded in `.git/info/exclude`. Pre-dispatch assertion verifies `Git(verification_workspace).snapshot(base_sha) == frozen_source_digest` (failing closed). `Pipeline._review_phase` executes verification with `cwd=verify_path` while reviewers inspect original worktree `state.worktree_path`. Post-join assertion verifies sandbox source integrity (`verify_git.snapshot(base_sha) == snapshot`), failing closed on source/mode mutation while permitting ignored transient files.
- `tools/orchestrator/core.py`: fixed `ReviewBundle.assemble` argument passing (`action=finding.action, evidence=finding.evidence`) to prevent keyword collision when findings are already `IdentifiedFinding` instances.
- `tests/orchestrator/test_workflow.py`: added `test_concurrent_audit_transient_boundary_and_stable_finding_ids` parametrized over both completion orders (`verification_first`, `reviewers_first`), proving verification creates and sees `.pytest_cache/transient`, reviewer does not observe it, ReviewShard and ReviewBundle do not contain transient evidence, final Auditor receives clean static evidence, and finding IDs remain stable at `correctness:0001`. Added counterfactual probe proving regression reproduction when boundary is omitted.
- `tests/orchestrator/test_core.py`: added `test_concurrent_audit_transient_output_isolated_from_request_evidence` verifying verification collector does not leak transient files into results or mutate request.
- `docs/orchestrator.md`, `tasks/t087-concurrent-audit-preparation.md`, `tasks/todo.md`: documented remediation architecture, verification workspace lifecycle, snapshot equivalence, sandbox source integrity, and handoff evidence.
- Verification: transient tests 3 passed (2.36s); focused T087 23 passed, 255 deselected (10.74s); T086 selection 25 passed, 250 deselected (27.99s); scheduler 48 passed (10.87s); full orchestrator 344 passed (231.19s), exit 0. Ruff check/format (10 files), Mypy (6 source files), and `git diff --check` PASS. Uncommitted candidate, starting/current HEAD `20447177c48a556d63709906cb8c953142f62e4b`, branch `feature/t087-concurrent-audit-preparation`. No commit, merge, push, reset, clean, or rebase. Product source, scheduler, runtime, orchestrator.yaml, package.json untouched.

## 05/10/2026 - T087 concurrent audit preparation (Asia/Bangkok)

- `tools/orchestrator/core.py`: frozen detached verification request and collected metadata, with ordinary regression and fatal setup failure distinguished.
- `tools/orchestrator/workflow.py`: overlap one non-authoritative sequential command collector with three read-only reviewer provider calls; share T086 parent freeze/join/integrity protection, persist executable evidence and reviewer diagnostics only after all futures join, and invoke final Auditor sequentially with complete evidence. Static reviewer prompts exclude executable results and reject transient output as authority. Existing mutable verify remains sequential for other phases; T086 disposition/correction semantics remain intact.
- `tests/orchestrator/test_core.py`, `tests/orchestrator/test_workflow.py`: deterministic four-party executable/provider barrier, reverse reviewer completion, both lane-completion orderings and final Auditor barrier, command metadata order/privacy, parent authority guards (`max_invoke_active=1`), failed-command PASS rejection, reviewer/setup failure reaping and source/branch/state/artifact mutation rejection. Existing T086 phase-marker assertion follows the new production phase while every T086 behavioral requirement stays enforced.
- `docs/orchestrator.md`, `tasks/t087-concurrent-audit-preparation.md`, `tasks/todo.md`: record architecture, tradeoffs and task-local handoff. Documentation follows documentation-and-adrs. No new dependency, schema migration, product/runtime/scheduler/config/package/gate/threshold/default change; T084/T085/T086 cards untouched.
- Final verification: exact focused T087 20 passed, 255 deselected (11.69s); T086 selection 25 passed, 250 deselected (33.74s); full orchestrator 341 passed (233.71s), exit 0. Ruff check/format (10 files), Mypy (6 source files) and diff-check PASS. Logs `/tmp/t087-focused-final.log`, `/tmp/t087-t086-final.log`, `/tmp/t087-orchestrator-final.log`. Earlier full run also passed 341 (240.08s); repeated because a raw-OS-error privacy fix landed during it. OS setup errors now keep only type names; sentinel regression verifies redaction. Task acceptance complete; `IMPLEMENTATION_READY`, uncommitted and awaiting independent review. Starting/current HEAD `20447177c48a556d63709906cb8c953142f62e4b`; branch `feature/t087-concurrent-audit-preparation`. No commit, merge, push, reset, clean, rebase or retained/other worktree changes. No unresolved findings; real-task speedup unmeasured.

## 05/10/2026 - T086 owner-approved scheduler fixture compatibility (Asia/Bangkok)

- Owner explicitly extends T086 scope by exactly `tests/orchestrator/test_scheduler.py`; `tasks/t086-parallel-review-fanout.md` records the revised allowlist and resolves the earlier authorization blocker without changing production scope.
- `tests/orchestrator/test_scheduler.py`: adapt only SyntheticProvider to the real ReviewShard schema, deriving the requested perspective from the actual prompt, asserting read-only execution and returning no actionable findings. Existing final Audit PASS validation is unchanged. Added assertions inspect the persisted complete empty review bundle in spawned Pipeline runs; every prior scheduler assertion remains intact.
- Verification: exact four formerly failing scheduler tests 4 passed (9.22s). Ruff check/format (10 files), Mypy (6 source files), and diff-check pass. Exact focused command 25 passed, 230 deselected (33.27s); scheduler suite 48 passed (12.40s). Full orchestrator suite 321 passed (271.43s), exit 0; extended log `/tmp/t086-owner-authorized-regression.log`.
- `tasks/todo.md`: record `IMPLEMENTATION_READY`; task card records completed acceptance, final evidence and resolved scope blocker. No test skipped/deleted/weakened, no task-ID workaround, no fan-out bypass and no scheduler/runtime/config/product/threshold changes. Starting HEAD `da662a3dc5af7dd2b2c8f44dbaff08031b46fe0c`; branch `feature/t086-parallel-review-fanout`; candidate remains uncommitted, with no merge or push. Documentation follows documentation-and-adrs.

## 05/10/2026 - T086 parallel reviewer implementation; scheduler fixture scope blocker (Asia/Bangkok)

- `tools/orchestrator/core.py`: add typed fixed reviewer perspectives, actionable findings/evidence, canonical complete bundles and host-owned finding IDs. Default-empty historical-compatible Audit dispositions enforce exact finding coverage, explicit dismissal evidence, and rejection of confirmed unresolved findings with PASS.
- `tools/orchestrator/workflow.py`: dedicated read-only `ThreadPoolExecutor` provider dispatch, with no concurrent Pipeline.invoke/save/artifact calls. Parent freezes source/branch and executable evidence, constructs all prompts first, protects state/run files/skills, reaps every call, deterministically registers unique reviewer files and atomically persists only a complete bundle before authoritative Auditor. Fan-out failures fail closed without retry; final Audit correction keeps existing three-attempt bound and fix/integration behavior.
- `tests/orchestrator/test_core.py`, `tests/orchestrator/test_workflow.py`: barrier/event-based real overlap and reverse-completion proof (`max_active=3`), complete fan-in, parent-thread authority guards, in-memory/disk state and artifact mutation rejection, source/branch mutation detection, disposition coverage and historical JSON compatibility. Local synthetic CLI failures exercise actual exit 7, timeout, output limit and malformed JSON. Timeout compatibility expectations now include three advisory calls per audit cycle.
- `docs/orchestrator.md`: record concurrency design, deterministic identity/disposition protocol, inherited provider policy, failure behavior and resource/trust boundaries. `tasks/t086-parallel-review-fanout.md` and `tasks/todo.md`: record incomplete task and the exact out-of-scope fixture extension needed.
- Verification: fan-out plus timeout compatibility 31 passed, 224 deselected (54.00s); exact focused command 25 passed, 230 deselected (33.97s); final extended run 317 passed, 4 failed (241.35s), exit 1; all four failures are the out-of-scope scheduler fake provider rejecting ReviewShard (full log `/tmp/t086-orchestrator-regression.log`). Ruff check/format (10 files), Mypy (6 source files) and diff-check pass. First extended run: 310 passed, 10 failed (261.34s); six allowed timeout expectations corrected, four scheduler SyntheticProvider failures require supporting the new ReviewShard output.
- Status: `BLOCKED_FOR_SCOPE_EXTENSION` pending authorization to update only the fake-provider fixture in `tests/orchestrator/test_scheduler.py`. No assertion weakened or test skipped, no production fallback, no scheduler/runtime/config/dependency/product or T023/T084/T085 changes. Starting HEAD `da662a3dc5af7dd2b2c8f44dbaff08031b46fe0c`; no commit, merge, rebase, reset, clean or push. No real inference/network tests, wall-clock speed assertion, or T023 speedup claim. Documentation follows documentation-and-adrs.

## 05/10/2026 - T084 performance gate remediation: parallel portable-task runner & coverage synchronization (Asia/Bangkok)

- `package.json`: updated `check:task:portable` to delegate to generic runner mode `bash .agent/scripts/run-gates.sh portable-task` rather than serializing all eight gates with `&&`. Full gates (`check:task`, `check:task:active`, `check:full`) and `test:python:portable` remain unchanged.
- `.agent/scripts/run-gates.sh`: implemented generic `portable-task` parallel mode under owner authorization. Phase A executes 7 independent concurrent gates (`check:fast:active`, `test:frontend:coverage`, `test:python:portable`, `security:secrets`, `security:code`, `security:deps`, `architecture:check`) in background subshells and reaps all processes. Phase B executes dependent consumer `coverage:check` strictly after both coverage producers finish successfully. Fail-closed propagation ensures non-zero exit if any gate fails and suppresses Phase B.
- `tests/orchestrator/test_core.py`: strengthened real T018 preflight assertion (`card.task_id == "T018"`, `card.dependencies == ["T015", "T017", "T052", "T081"]`, `len(card.dependency_verification) == 11`, and all 4 T081 verification commands present); added behavioral regression tests for `run-gates.sh portable-task` proving success path, coverage synchronization, and fail-closed failure propagation; all 296 orchestrator tests pass.
- `docs/orchestrator.md`: documented the `portable-task` parallel gate runner mode, Phase A concurrent execution graph, Phase B coverage synchronization, and fail-closed child reaping.
- `tasks/t084-scheduler-admission-platform-baseline.md`: updated allowlist to include `.agent/scripts/run-gates.sh` under owner authorization; documented independent audit performance finding (128-141s), root cause, architecture, synchronization rule, failure propagation, and warm performance measurements.
- `tasks/todo.md`: updated T084 entry with performance remediation results and warm timing.
- Measured warm performance:
  - `time npm run check:task:portable`: wall time **1m19.011s** (**79.011s**), well under the ~90s task verification budget in `CONSTRAINTS.md` (reduced from serial ~140.566s).
  - Gate summary: `check-fast-active` PASS (19s), `frontend-coverage` PASS (17s), `portable-pytest` PASS (79s), `security-secrets` PASS (20s), `security-code` PASS (14s), `security-deps` PASS (13s), `architecture` PASS (49s), `coverage-check` PASS (0s).
  - Test counts: Frontend 75 passed (5 suites); Python 1038 passed; Architecture 40 passed (24 modules/31 dependencies cruised, 0 violations, 7 contracts kept/0 broken).
  - Coverage: changed 100.00% (min 80.00%), total 92.69% (baseline 86.70%, tolerance 0.50).
  - Security scans: secrets 0 findings, code 0 findings, deps 0 findings.
  - Orchestrator test suite: 296 passed in 174.26s, exit 0.
  - Windows fail-closed: 11 failures on Linux preserved.
  - Static linters: Ruff check passed, Ruff format passed (10 files), Mypy passed (6 source files), `git diff --check` passed cleanly.
- Preserved all previous T084 protections and behavior: T081 six owned paths and exact verification commands, real T018 preflight and dependencies without T080, T085 shared dependency semantics, Python `-n 10` parallelism without oversubscription, full gates unchanged, native-Windows tests untouched and fail-closed on Linux, product source untouched, legacy worktrees untouched.
- Outcome: `REMEDIATION_READY`.

## 05/10/2026 - T084 reconciliation R2: owner-approved T081 verification metadata and measured portable baseline (Asia/Bangkok)

- `tasks/t081-app-shell-shadcn-migration.md`: split exact executable `Verification commands` (AppShell focused tests, typecheck, frontend architecture, diff integrity) from historical `Snapshot results`. The original fenced snapshot, QUALITY_BASE_REF command, counts/results and Linux/native-Windows inherited failure evidence are preserved byte-for-byte; DONE/dependencies/implementation/acceptance unchanged. Four focused commands are accepted by check_commands/validate_command and pass when run; they add 4 to T018's total 11 dependency checks, avoiding automatic E2E/A11y/full historical reruns. Coverage/security remain in repository baseline.
- `tests/orchestrator/test_core.py`: add executable-metadata regression protection; 10 total T084 cases now pass. T085 helper/core/scheduler and all original tests remain unchanged. `docs/orchestrator.md` explains focused dependency revalidation; `tasks/t084-scheduler-admission-platform-baseline.md` records the approved extension, completed acceptance and exact evidence; `tasks/todo.md` records an uncommitted candidate ready for review.
- Real `task_card(Path.cwd(), "T018")` exit 0, dependencies exactly T015/T017/T052/T081 (no T080); T081 owned_paths returns six exact paths. Historical scope stop below is resolved in this same task under explicit owner authorization.
- `time npm run test:python:portable`: exit 0, 1035 passed (73.97s pytest), wall **74.553s**, 10 workers, coverage retained. `time npm run check:task:portable`: exit 0, wall **140.566s**, 75 frontend/1035 Python/40 architecture tests pass, 7 contracts kept, changed coverage 100.00%, total 92.70%, zero findings from each pinned secrets/code/dependency scanner. Three existing ESLint fast-refresh warnings, zero errors. Full gate timing includes external scanners and architecture; no threshold or check lowered for speed.
- `python -m pytest tests/orchestrator -q --no-cov`: 293 passed in 194.80s, exit 0. Ruff/format (10 files)/Mypy (6 source files)/diff-check exit 0. Direct Windows suite: expected exit 1, 11 native-runtime-unavailable guard failures in 1.41s on Linux, no skip/xfail. This preserves fail-closed verification and does not claim genuine Windows acceptance.
- Scope remains eight T084-allowlisted files. Full gates unchanged; no product/Windows source, parser/Pipeline, T018/T080/T085 card, runner, lock/config/threshold or legacy/retained worktree changes. Retained T084 inspected and unchanged. Starting HEAD/main remains `2f0a7b9001c59bf186088255f362c4994fbf77f7`. No commit, merge, rebase or push. Outcome: `REMEDIATION_READY`; no unresolved T084 blocker. Documentation follows documentation-and-adrs.

## 05/10/2026 - T084 reconciliation R2: portable admission candidate blocked by T081 verification metadata (Asia/Bangkok)

- `tasks/t081-app-shell-shadcn-migration.md`: normalize only the allowlist to six exact paths; retain explanatory prose, DONE/dependencies and all historical evidence.
- `package.json`, `orchestrator.yaml`: add portable Python pytest with `--ignore=backend/tests/windows -n 10` (existing runner authority), retain all eight portable quality gates and separate Ruff/Mypy commands. Full gates unchanged.
- `tests/orchestrator/test_core.py`: add nine T084 regression cases, including real T018 preflight; preserve every T085 case and its shared dependency semantics. `docs/orchestrator.md` records the portable/full gate distinction and xdist rationale.
- `tasks/t084-scheduler-admission-platform-baseline.md`, `tasks/todo.md`: record `BLOCKED_FOR_SCOPE_EXTENSION`. Real T018 preflight exits 1 because T081 lacks exact `Verification commands` heading; a read-only in-memory heading diagnostic then rejects its historical environment-assignment command. No parser or historical-evidence change made. Scope extension for executable T081 verification metadata is needed.
- Verified: T081 six owned paths; real T018 core/scheduler dependencies exactly T015/T017/T052/T081, no T080. Focused T084: 8 passed, 1 failed, 101 deselected (0.28s, exit 1); unchanged T085: 4 passed (0.93s, exit 0). Ruff/format (10 files)/Mypy (6 files)/diff-check exit 0. Timed portable gates and full orchestrator suite not run after scope stop; no baseline/performance PASS claimed.
- Starting clean HEAD equals main `2f0a7b9001c59bf186088255f362c4994fbf77f7`. Retained T084 inspected read-only; product source, Windows tests, core/scheduler/Pipeline, T085 card/tests, T018/T080, runner/lock/pytest config, legacy worktrees and T023 evidence untouched. No commit, merge, rebase or push. Documentation follows documentation-and-adrs.

## 05/10/2026 - T085: Normalize authoritative task dependency parsing across orchestrator layers (Asia/Bangkok)

- Established unified standalone task-ID parsing semantics across executable task card parsing (`tools/orchestrator/core.py`) and Level 2 DAG discovery (`tools/orchestrator/scheduler.py`):
  - `tools/orchestrator/core.py`: Introduced deterministic `dependency_ids(text: str) -> list[str]` helper to extract dependencies from the `## Dependencies` section using word-boundary canonical task ID matching (`\bT[0-9]+\b` matching `TASK_PATTERN`). Replaced substring `re.findall(TASK_PATTERN, section(text, "Dependencies"))` in `task_card()`.
  - `tools/orchestrator/scheduler.py`: Replaced local extraction in `metadata()` with `dependency_ids(text)`, ensuring exact semantic alignment between scheduler admission and execution preflight.
  - Eliminated false dependency edges created by task-like substrings embedded inside prose or status strings such as `BLOCKED_BY_T080_T081`, `PREFIX_T080`, `T080_SUFFIX`, `XT080`, and `T080X`.
  - Maintained strict fail-closed enforcement for missing dependency cards, status completion, self-dependencies, DAG cycles, and malformed dependency IDs (e.g. `T0800`, `T8`).
- Added regression and diagnostic test coverage:
  - `tests/orchestrator/test_core.py`: Added `test_dependency_ids_canonical_and_embedded_tokens`, `test_dependency_ids_t018_synthetic_diagnostic_fixture`, and `test_task_card_ignores_embedded_prose_dependencies` proving that embedded prose tokens like `BLOCKED_BY_T080_T081` do not trigger false dependency extraction and do not cause `task_card()` to attempt loading missing dependency cards (e.g. `T080`).
  - `tests/orchestrator/test_scheduler.py`: Added `test_scheduler_metadata_aligns_with_core_dependency_ids` proving that scheduler `metadata()` and core `dependency_ids()` yield identical dependency sets (`['T015', 'T017', 'T052', 'T081']`) and exclude `'T080'`.
- Documentation & Bookkeeping:
  - `docs/orchestrator.md`: Documented standalone token dependency parsing, elimination of false prose edges, shared helper alignment, and fail-closed validation.
  - `tasks/t085-task-dependency-parser.md`: Marked status `DONE` and checked all 20 acceptance criteria.
  - `tasks/todo.md`: Added T085 entry under local agent infrastructure.
- Verification & Scope Safety:
  - Focused test suite: 149 passed.
  - Full orchestrator test suite: 283 passed.
  - Linters: Ruff check passed, Ruff format check passed (10 files formatted), Mypy passed (6 source files, zero errors).
  - Whitespace: `git diff --check` passed cleanly.
  - Product source, contracts, migrations, task cards `t018`/`t080`/`t081`/`t084`, and external worktrees (`/home/khanh/projects/vocabularies-t084`, legacy worktrees) are 100% untouched. Status: `REMEDIATION_READY`. Uncommitted candidate prepared for independent audit.

## 04/10/2026 - T083: Repository DAG dependency metadata remediation (Asia/Bangkok)

- Remediated repository task dependency metadata by removing invalid self-dependency edges in task cards without altering scheduler validation logic or product behavior:
  - `tasks/t018-consent-ui.md`: removed self-reference `T018` in Dependencies prose ("T018 bị chặn trực tiếp..." -> "Task này bị chặn trực tiếp..."), preserving legitimate dependencies `['T015', 'T017', 'T052', 'T081']`.
  - `tasks/t081-app-shell-shadcn-migration.md`: removed inherited self-reference `T081` in Dependencies prose ("...trước khi triển khai T081." -> "...trước khi triển khai task này."), preserving legitimate dependencies `['T004', 'T080']`.
  - `tasks/t083-dag-metadata-remediation.md`: formatted status as `TODO` with backticks to conform to metadata discovery.
- Candidate-aware DAG validation: filesystem discovery finds 83 regular cards with 83 globally unique task IDs; zero self-dependencies (down from 2 to 0); zero missing dependency targets; topological sort succeeds across all 83 nodes (40 DONE, 6 READY: `T008`, `T018`, `T023`, `T027`, `T034`, `T083`, 37 BLOCKED).
- Preserved scheduler implementation (`tools/orchestrator/*`), tests (`tests/*`), and all product source/contracts/migrations byte-identical. All 279 orchestrator tests passed in 167.19s; floor, Ruff, Mypy and whitespace checks passed.
- Canonical-main dry-run (`python -m tools.orchestrator schedule --dry-run`) exits 2 with `ERROR OrchestratorError: Self dependency: T018` because it reads unintegrated canonical main. Candidate status: `REMEDIATION_READY`. Next inherited DAG blocker: zero blockers in the candidate DAG; independent audit and authorized integration into canonical main remain pending.

## 04/10/2026 - T082: Canonicalize duplicate repository task IDs (Asia/Bangkok)

- Preserved the older orchestrator cards as T075 (agy capability probes) and T076 (audit report retry). Used `git mv` to assign the later shadcn/ui foundation and AppShell migration cards to `tasks/t080-shadcn-ui-foundation.md` / T080 and `tasks/t081-app-shell-shadcn-migration.md` / T081; T081 now depends on T080.
- Updated canonical UI card headings/IDs, dependency links, design-system references, readiness labels, planning tables/graphs/checkpoints/model lists and `tasks/todo.md`. Preserved dated historical IDs and earlier T079 failure evidence; only two historical filename locators now point to the canonical paths, explicitly annotated with their original IDs.
- Updated T082 task-local metadata formatting and verification bookkeeping. Product source, API contracts, scheduler/test semantics, floor/security/coverage thresholds and canonical main are intentionally unchanged. No commit, merge, rebase or push.
- Recorded current-state follow-up in `docs/orchestrator.md`, `tasks/t079-level2-dag-scheduler.md` and the task index without rewriting earlier T079 evidence. Unique-ID proof: 81 explicit declarations/81 unique IDs and 82 headings/82 unique IDs; no old UI filename references remain. All 279 orchestrator tests passed in 177.53s; floor, Ruff, Mypy and whitespace checks passed. Orchestrator T075/T076/T077/T078 cards remain byte-identical.
- Status: `REMEDIATION_READY`. Worktree discovery passes duplicate-ID validation, then unchanged DAG resolution reports `Self dependency: T018`; T081 also retains its pre-existing Dependencies prose self-reference. The required CLI dry-run exits2 with duplicate T075/T076 because it reads unchanged committed canonical main rather than this worktree. No successful canonical-main dry-run, readiness counts or dispatch is claimed; separate DAG remediation and authorized integration remain pending.

## 04/10/2026 - T079: Remediate synthetic scheduler floor findings (Asia/Bangkok)

- Updated `tests/orchestrator/test_scheduler.py` to use `PENDING` consistently for synthetic unfinished task-card states, including the fake worker's DONE transition, malformed-metadata source and dependency/dry-run expectations. Replaced the synthetic `tasks/todo.md` index with `tasks/task-index.md`; retained the `_template.md` fixture and both filesystem/canonical discovery assertions.
- Removed all nine reported unfinished-work findings (eight uppercase status occurrences and one lowercase index path). The same 30 test functions and 89 assertions remain; scheduler behavior, floor rules, verification, allowlists and architecture constraints are unchanged.
- Recorded remediation evidence in `tasks/t079-level2-dag-scheduler.md`. Focused tests: 47 passed in 10.35s; all orchestrator tests: 279 passed in 196.02s, including the 232 existing cases. Floor, Ruff, format, Mypy and diff checks passed. Status: `REMEDIATION_READY`. No commit, merge, rebase or push.

## 04/10/2026 - T079: Generic Level 2 DAG scheduling above Pipeline (Asia/Bangkok)

- Added `tools/orchestrator/scheduler.py`, repository-wide `schedule` CLI in `tools/orchestrator/__main__.py`, and synthetic graph/process coverage in `tests/orchestrator/test_scheduler.py`. Lightweight metadata discovery represents blocked nodes without weakening authoritative `task_card()` or Pipeline checks. Canonical Git revisions, validated edges, deterministic admission, isolated outcomes and recomputation control downstream dispatch.
- Reused synchronous Pipeline in spawned processes, three existing OS admission slots, task/worktree locks and serialized integration. Added a repository-global scheduler OS lock; deferred busy resources without starving unrelated roots. Existing provider, bounded recovery, snapshot/scope/verification fences and no-push policy remain authoritative. No dependency, product code, task-specific scheduling, CPU/RAM budgeting or FAST/FULL gate arbitration was added.
- Updated `docs/orchestrator.md` and task-local bookkeeping with commands, state/exit semantics, limits and handoff evidence. Focused scheduler suite: 47 passed; all orchestrator tests: 279 passed, including every 232 existing case unchanged. Scheduler line coverage 164/170 (96.47%), branch coverage 63/66 (95.45%); Ruff/format/Mypy/diff checks pass and secret/code scans have zero findings. Exact commands and resolved Semgrep sandbox setup evidence are recorded in the T079 card.
- Real `schedule --dry-run` rejects canonical main's duplicate T075/T076 IDs (exit2), before any model/worktree/lock creation. Inventory: 80 cards, 38 DONE, 42 unfinished; valid DAG READY/BLOCKED counts are unavailable because graph validation failed. Unrelated task cards/checkpoints were preserved. No real product-task agents, commit, merge or push.

## 03/10/2026 - T076: Di chuyển AppShell sang canonical shadcn/ui và Tailwind design system (Asia/Bangkok)

- **Mục tiêu & Bối cảnh:** Hoàn thành di chuyển `AppShell` sang nền tảng shadcn/ui và Tailwind CSS v4 semantic tokens theo kiến trúc thiết kế chuẩn của repository; bảo toàn 100% hợp đồng hành vi, accessibility, và khả năng phục hồi của T004.
- **Thực thi giao diện & CSS (`frontend/src/app/AppShell.tsx`, `frontend/src/app/shell.css`):**
  - Bảo toàn 9 routes v1, regular expression pattern matching, trích xuất dynamic route parameters.
  - Tái lập và duy trì các CSS document reset nền tảng (`box-sizing: border-box`, `body { margin: 0; padding: 0; ... }`) cùng typography baseline trong `shell.css` do Tailwind v4 không nạp Preflight theo thiết kế của T075.
  - Sử dụng canonical primitives `Button` và `Card` (`CardHeader`, `CardTitle`, `CardContent`, `CardFooter`; không dùng `CardDescription` do AppShell không dùng tới) từ `@/components/ui`.
  - Bảo toàn ngữ nghĩa tiêu đề cấp 2 trong `ErrorBoundary` bằng cách lồng thẻ `<h2 className="...">` chuẩn semantic bên trong `<CardTitle>`, bảo đảm không làm mất `heading` role trong accessibility tree khi `CardTitle` render thẻ `div`.
  - Thêm cấu hình style responsive `whitespace-normal h-auto py-2` cho `Button` để ngăn chặn tràn ngang (horizontal overflow) trên màn hình hẹp 320px khi nút chứa văn bản tiếng Việt dài.
  - Duy trì liên kết nhanh `/status#ai-consent` trong header: bảo toàn thuộc tính markup `href="/status#ai-consent"` trong khi cơ chế điều hướng client-side chuyển tới màn hình `/status`.
  - Duy trì các class tương thích (`screen-view__title`, `feature-unavailable-note`) để tránh dead CSS và bảo toàn các bài test hồi quy.
- **Kiểm thử đơn vị và E2E đa viewport (`frontend/src/app/AppShell.test.tsx`, `frontend/tests/e2e/shell.spec.ts`):**
  - Giữ vững 25 unit tests ban đầu trong `AppShell.test.tsx` và bổ sung 2 tests tương tác client-side mounted React DOM trong môi trường Vitest/jsdom per-file, mang lại jsdom-based mounted Vitest interaction coverage cho 2 navigation handlers (brand navigation tại line 270 và 404 recovery action tại line 346) thông qua sự kiện DOM thực tế và assertion landing focus `h1`, hoàn toàn không dùng synthetic handler invocation hay React-element traversal.
  - Mở rộng bộ test Playwright E2E `frontend/tests/e2e/shell.spec.ts` gồm 48 tests trên Chromium thực tế (12 tests x 4 viewports chuẩn: 320px mobile, 768px tablet, 1024px desktop, 1440px wide): kiểm thử mounted ErrorBoundary fixture phục hồi thực sự khi người dùng click, kích hoạt brand link và 404 recovery điều hướng về trang chủ và focus `h1`, kiểm thử reflow ở độ phân giải tương đương 200% zoom (viewport 640px) không tràn ngang và các controls khả dụng, cùng kiểm tra chẩn đoán độ phóng đại visual viewport bằng CDP `Emulation.setPageScaleFactor` (2.0) với thuật ngữ chính xác.
- **Kết quả xác minh độc lập:**
  - `npm run test:frontend`: 75/75 tests PASS (gồm 27/27 AppShell tests, 27/27 design system tests).
  - `npm run test:e2e -- frontend/tests/e2e/shell.spec.ts --workers=1`: 48/48 tests PASS (4 viewports x 12 tests).
  - `npm run test:a11y -- --workers=1`: 8/8 tests PASS (0 critical/serious axe-core violations).
  - `npm run typecheck`: exit 0.
  - `npm run lint`: exit 0 (0 errors, 3 fast-refresh warnings).
  - `npm run architecture:frontend`: exit 0 (24 modules, 31 dependencies).
  - `npm run architecture:check`: exit 0 (7 contracts kept, 40 tests passed).
  - `npm run build`: exit 0.
  - `QUALITY_BASE_REF="035430d668f1f754afd38e3cca9d630eb90a69a7" npm run coverage:check`: exit 0 (changed 100.00% >= 80.00%, total 93.40%).
  - `npm run security:secrets`: exit 0 (0 finding).
  - `npm run security:code`: exit 0 (0 finding).
  - `npm run security:deps`: exit 0 (0 finding).
  - `npm run check:fast`: exit 0.
- **Phạm vi bảo toàn & Trạng thái:**
  - Narrow scope extension: Thêm devDependency `jsdom` (test-only) phục vụ chạy môi trường DOM per-file trong `AppShell.test.tsx` cho cổng LCOV của repository; Playwright tiếp tục là oracle E2E trên trình duyệt thật Chromium (không đồng nhất jsdom với Chromium).
  - Mã nguồn production (`AppShell.tsx`, `shell.css`) hoàn toàn không bị thay đổi (byte-identical) trong đợt coverage remediation này.
  - Ghi nhận 11 test Windows-native trong `backend/tests/windows/test_source_paths.py` thất bại có chủ đích fail-closed trên môi trường Linux là `INHERITED_BASELINE_FAILURE` từ T021.
  - Giữ nguyên trạng thái CP06A là `[ ]` (chưa tích hợp).
  - Không commit, không push, không merge theo đúng chỉ thị phân quyền.

## 03/10/2026 - T022: Integrate independently audited durable source journal into current main (Asia/Bangkok)

- Integrated the owner-reported `AUDIT_PASS` candidate `da270b3337c192636f07fa0f917831c2ed7ab966` with current local main `035430d668f1f754afd38e3cca9d630eb90a69a7`, preserving all 13 audited Python files and current-main T042/T075 behavior. Only changelog history conflicted; retained both histories and removed conflict markers previously committed on main.
- Verified PREPARED-before-replace, shared projection/card/receipt transactions, terminal late-H3 rollback then DEGRADED, restricted UNKNOWN reconciliation without redispatch, exactly-once reset/history retention, T021 protections and T026 search behavior. Critical focused suites: **339 passed**; explicit normal/UNKNOWN H3/H2 controls at both late boundaries: **8 passed**; current-main T042 search oracle: **1 passed**.
- Alembic heads/history: one linear `0007_source_journal` after `0006_ai_admission`, with historical migrations untouched. T078 task loader: **16 paths, 13 concrete commands**. Scoped Ruff/format, full backend Mypy (**52 files**), architecture (**7 kept contracts, 40 tests**) and diff checks pass. Exact verification outputs are recorded in `/tmp/t022-integration-035430d-da270b3` and the T022 integration handoff.
- Marked T022 DONE and its todo entry checked after mandatory integration verification; preserved every unrelated task status and CP10. T027/T008 remain separate; no parallel code, frontend, generated API, tooling or downstream task change was introduced. Source branch remains immutable; no push.
- `WINDOWS_NATIVE_EVIDENCE: DEFERRED_TO_WINDOWS_RELEASE_EVIDENCE`. T023/T034 may proceed subject to remaining dependencies; T034 must rediscover the current head rather than reuse stale `0007_quiz`. Future T027 integration must preserve T022 caller-owned transaction/source projection primitives.

## 03/10/2026 - T022: Fix terminal external-edit race and executable task card (Asia/Bangkok)

- `source_write.py` revalidates the canonical hash through T021 after projection/reset and the last local-effect hook, before terminal persistence. Normal and UNKNOWN completion share this linearization point; mismatch rolls back real DB effects/receipt and then persists DEGRADED, retaining external bytes and history.
- `test_source_journal.py` adds eight bounded Event-synchronized H3/control cases at projection/reset boundaries, checks nine persisted tables, non-success receipts, restart idempotency and refusal of new writes after DEGRADED. RED reproduced all four race defects before the fix.
- `tasks/t022-source-journal.md` now conforms to T078's existing allowlist grammar, uses full paths and concrete static commands, and records the remediation evidence. Actual loader assertions prove exactly 16 authorized paths and 13 placeholder-free commands; no tooling was changed.
- Focused final checks: journal 74 and operations 15 passed; scoped Ruff/format/Mypy, one-head Alembic and diff check exit 0. Dependency files/migrations, main/T031, contracts/frontend and todo status were preserved in this round. Full gates and native Windows evidence remain owner-deferred; startup composition belongs to T023 and pre-handle temp retention is unchanged.
- Status: `READY_FOR_T022_RE_AUDIT`, not DONE. MAIN_DRIFT remains; no commit, push, merge or rebase. Independent re-audit must precede owner-authorized integration.

## 03/10/2026 - T022: Real durable effects and restart reconciliation ready for independent audit (Asia/Bangkok)

- Preserved the partial candidate and completed owner-authorized transaction primitives in vocabulary repository/search index, authenticated T021 restart temp cleanup, and dedicated T014 journal-evidence UNKNOWN reconciliation/old-state abort.
- Revised uncommitted `0007_source_journal` in place to persist minimal immutable effect identifiers/baselines, reset intent, receipt and relative staged ownership evidence; no Markdown copy, historical migration edit or competing head.
- T022 now reconstructs real canonical/source/search/card effects after restart and commits them atomically with the operation receipt and journal terminal marker. Ambiguous bytes, missing/stale evidence and unsafe temp cleanup fail closed without overwriting sources or deleting review/quiz references.
- Added actual-effect crash tests for PENDING/UNKNOWN, SQLite/disk failures, bounded concurrent intents, replay, reset policy and seeded 0005→0006→0007 preservation. Maintained only T016 migration-head assertions and strengthened admission preservation; existing admission/race tests remain intact.
- Final task-local verification: 331 passed (journal 66, adapter 86, operations 15, vocabulary 18, search 26, SRS 60, admission 60); scoped Ruff/format/Mypy, single-head Alembic heads/history and diff check all exit 0. Frozen 13 Python files were unchanged after verification.
- State is `READY_FOR_T022_AUDIT`, not DONE; CP10 remains unchecked. Native Windows evidence and full integration/coverage/security gates are deferred per owner instructions. Temps without a durable authenticated handle are retained; startup recovery runs before source writers. MAIN_DRIFT is reported, with no integration or commit performed.

## 02/10/2026 - T022: Incomplete source journal candidate blocked on integration scope (Asia/Bangkok)

- Added the linear `0007_source_journal` migration after the discovered `0006_ai_admission` head, with immutable journal evidence, deterministic state-transition guards and history-preserving downgrade refusal.
- Added candidate `SourceWriteCoordinator` and `SourceRecovery` primitives for durable intent, T021 replacement, T014 receipt callbacks and hash reconciliation. Complete durable projection/reset reconstruction and crash/recovery proofs remain unfinished.
- Added 21 focused fault-injection, idempotency, migration, card-history and ambiguity tests. The focused suite and dependency regressions pass.
- Worker handoff is blocked for a narrow scope extension because the unchanged T016 integration test still hardcodes `0006_ai_admission` as the latest head; updating that non-allowlisted assertion is required to validate the new linear head. Latest aggregate result: exit 1, 908 passed and 12 failed; the later test-only annotation/style correction has focused/static evidence only. Native Windows tests remain PENDING on this Linux host. T022 and CP10 remain incomplete.
- Resumption audit also found missing caller-transaction projection interfaces in T019/T026, no T021 public restart-safe temp cleanup handle, and no T014 UNKNOWN completion path. These require dependency-owned scope extensions or an explicit startup-order contract before T022 can prove durable completion; the callback-only candidate remains incomplete.

## 02/10/2026 - T042: Tạo fixture tìm kiếm tổng hợp 100k xác định (Asia/Bangkok)

- Thêm generator, test và README cho fixture T042; dữ liệu hoàn toàn tổng hợp,
  streaming JSONL, checksum SHA-256 ổn định và ghi artifact theo cơ chế tạm rồi
  replace nguyên tử.
- Sinh chính xác 100.000 forms và 100 query tiếng Việt cố định với seed 29,
  ground truth brute-force độc lập, coverage Unicode/NFC/combining/accent-fold,
  `đ`/`Đ`, infix, POS và các trường hợp zero/single/multi-match.
- Ghi rõ profile Windows 11/Python 3.12/SQLite và ranh giới bằng chứng: T042
  không tuyên bố kết quả hiệu năng; T065 sở hữu timing/p95.

## 02/10/2026 - T021: Tích hợp adapter source Windows sau xác nhận native PASS (Asia/Bangkok)

- T021 được đánh dấu DONE sau xác nhận của chủ repo rằng bộ kiểm thử Windows native trên NTFS đã PASS, gồm junction/reparse, hardlink, read-only, CRLF, ownership/DACL và privacy. Báo cáo gốc không có trong checkout Linux nên được ghi là owner-attested evidence.
- Candidate giữ nguyên source/test từ commit `ef93413`; portable 78 test source + 24 test dependency, Ruff và Mypy đạt. Linux native suite vẫn fail-closed do không có `win32`; không sửa test để che điều kiện môi trường.
- T021 được tích hợp local fast-forward vào main; không push. T022 chỉ tiếp tục từ snapshot đã tích hợp sau verification phù hợp.

## 02/10/2026 - T021: Chuẩn bị tích hợp sau báo cáo PASS của chủ repo (Asia/Bangkok)

- Candidate riêng từ main9135c03 giữ nguyên byte ba file source/test của commit ef93413, bảo toàn task list và changelog cộng dồn. 102 focused tests đạt; Ruff/format đạt.
- Chủ repo thông báo Windows PASS; chưa tìm được file report/log để đối chiếu snapshot. T021 chưa đánh dấu DONE, chưa promote main. Worktree/run lịch sử và cấu hình/threshold không thay đổi.

## 02/10/2026 - T021: Đính chính và hoàn thiện xác thực dọn dẹp file tạm, kiểm tra DACL Win32 và fixture Windows (Asia/Bangkok)

- **Đính chính & Hiệu chỉnh lỗi theo kết quả audit:**
  - **Đính chính về an toàn dọn dẹp file tạm (`StagedWrite.cleanup` & `prepare_staged_write`):**
    - Đính chính tuyên bố trước đây: Tuyên bố trước đây về việc dọn dẹp an toàn tuyệt đối là chưa chính xác. Trước đây `StagedWrite.cleanup()` chỉ xác thực thư mục cha trực tiếp của file tạm (`self._temp_path.parent`). Nếu thư mục tổ tiên cấp cao bị thay thế bằng liên kết tượng trưng (symlink/junction) trong khi thư mục cha trực tiếp và file tạm vẫn giữ nguyên inode, hàm dọn dẹp có thể unlink file bên ngoài allowlist. Đồng thời `prepare_staged_write()` trước đây unlink vô điều kiện `temp_path` khi gặp lỗi staging mà chưa có bằng chứng sở hữu đã xác thực qua descriptor.
    - Khắc phục: Đã thống nhất một đường dẫn xác thực dọn dẹp dùng chung `_safe_cleanup_temp` cho cả `StagedWrite.cleanup()` và dọn dẹp khi hủy `prepare_staged_write()`. Duyệt kiểm tra nghiêm ngặt từ root đến temp: xác thực thư mục root, toàn bộ danh sách thư mục trung gian theo thứ tự, thư mục cha trực tiếp, và file tạm khớp đúng danh tính descriptor ban đầu (`os.fstat`), định dạng regular file, không có reparse/link, đúng 1 hardlink (`st_nlink == 1`). Danh tính descriptor được ghi nhận độc quyền ngay sau `tempfile.mkstemp` thành công, trước khi `os.chmod`, `os.fdopen` hay các thao tác ghi có thể thất bại. Nếu ranh giới hoặc quyền sở hữu bị thay thế, giữ nguyên file tạm và bảo toàn ngoại lệ gốc.
    - Củng cố kiểm thử dọn dẹp: Bổ sung assertion kiểm tra bảo toàn chính liên kết tượng trưng bị thay thế (`assert real_temp.is_symlink()`, `assert real_temp.exists()`) trong `test_cleanup_safe_after_staged_file_substitution` bên cạnh việc kiểm tra bảo toàn file đích ngoài.
  - **Đính chính và mở rộng kiểm tra DACL Win32 (`_inspect_windows_security_info` & `_check_windows_ownership`):**
    - Đính chính tuyên bố trước đây: `_check_windows_ownership` chỉ truy vấn `OWNER_SECURITY_INFORMATION` và không cung cấp bằng chứng DACL.
    - Khắc phục: Đã bổ sung `_inspect_windows_security_info` truy vấn cả `OWNER_SECURITY_INFORMATION` và `DACL_SECURITY_INFORMATION` thông qua `advapi32.GetNamedSecurityInfoW`, kiểm tra tính hợp lệ của DACL qua `advapi32.IsValidAcl`, đối chiếu ownership qua `advapi32.EqualSid`, giải phóng tài nguyên tin cậy (`kernel32.CloseHandle`, `kernel32.LocalFree`) và chỉ ghi nhận bằng chứng dạng boolean/categorical. Bổ sung bộ test deterministic failure paths cho các trường hợp API không khả dụng, lỗi truy vấn token, lỗi truy vấn thông tin bảo mật, ownership mismatch (`EqualSid == 0`), và DACL không hợp lệ, xác nhận hành vi fail-closed và giải phóng tài nguyên tin cậy.
  - **Chuẩn hóa fixture byte-exact và xử lý xuống dòng Windows:**
    - Cấu hình autouse fixture `_disable_newline_translation` trên cả hai file kiểm thử (`test_source_files.py` và `test_source_paths.py`), đảm bảo `Path.write_text` không bị platform newline translation (CRLF trên Windows) làm sai lệch hash.
    - Bổ sung test case synthetic CRLF trên cả hai bộ test chứng minh dữ liệu đĩa CRLF khớp chính xác thành công và hash LF cũ bị từ chối fail-closed với `REVISION_CONFLICT`.
  - **Vệ sinh thông điệp chẩn đoán & bảo mật thông tin (Privacy):**
    - Loại bỏ việc chèn stderr/stdout của tiến trình con vào `pytest.fail`, thay bằng thông điệp chẩn đoán tĩnh đã được vệ sinh.
    - Bổ sung kiểm tra privacy sentinels qua `str`, `repr`, `args` và `caplog.text` trong cả hai bộ test, đảm bảo không làm rò rỉ đường dẫn Windows, nội dung Markdown hay SID trong bất kỳ kênh nào.

- **Phân định bằng chứng lịch sử và hiện tại:**
  - *Bằng chứng lịch sử (chu kỳ 1 & 2):* 70 passed (chu kỳ 1) / 78 passed (chu kỳ 2) portable tests; 9 Windows-native tests fail-closed; một số lỗi về DACL và thay thế tổ tiên chưa được kiểm chứng đầy đủ.
  - *Bằng chứng hiện tại (chu kỳ 3):*
    - `python -m pytest backend/tests/test_markdown_roundtrip.py -q`: 24 passed in 0.53s (T020 dependency verified).
    - `python -m pytest backend/tests/test_source_files.py -q`: 78 passed in 1.19s, line coverage trên `backend/app/adapters/source_files.py` đạt 92%, changed-code coverage đạt 93.63% (vượt sàn 80.00%).
    - `python -m pytest backend/tests/windows/test_source_paths.py -q`: 11 failed (báo lỗi fail-closed trung thực `_require_native_windows()` do thiếu môi trường Windows OS native; không dùng early return/skip/xfail giả pass; PENDING genuine Windows OS environment).
    - `python -m mypy backend`: 0 errors (46 source files).
    - `python -m ruff check .`: 0 errors.
    - `npm run format:check`: exit 0 (178 files already formatted).
    - `npm run check:fast`: exit 0 (format, lint, typecheck, floor, secrets clean).
    - `npm run architecture:check`: exit 0 (7 contracts kept, 40 tests passed in 22.02s).
    - `npm run coverage:check`: exit 0 khi chạy toàn bộ test suite (changed coverage 93.63% >= 80.00%, total coverage 91.75% >= 86.70%).
    - `npm run security:secrets`: exit 0 (0 finding).
    - `npm run security:code`: exit 0 (0 finding).
    - `npm run security:deps`: exit 0 (0 finding).
    - `npm run check:task`: dừng tại `python -m pytest` do 11 test Windows native fail-closed trung thực trên host Linux (782 passed, 11 failed); toàn bộ các kiểm tra hạ nguồn độc lập đều đạt PASS.

- **Trạng thái & Rào cản còn lại (BLOCKED/PENDING):**
  - Task T021 giữ trạng thái `BLOCKED` (tiêu chí Windows acceptance giữ nguyên `[ ]`) cho đến khi có bằng chứng thực thi đầy đủ trên hệ điều hành Windows native (NTFS junction, reparse point, hardlink, DACL). Không mở khóa T022 trên bằng chứng portable đơn thuần.
  - Files đã sửa: `backend/app/adapters/source_files.py`, `backend/tests/test_source_files.py`, `backend/tests/windows/test_source_paths.py`, `docs/changelogs.md`, `tasks/t021-safe-source-files.md`, `tasks/todo.md`.
  - Files chủ ý không sửa: `CONSTRAINTS.md`, `package.json`, `pyproject.toml`, `docs/vocabularies/*`, models/migrations ngoài phạm vi.
  - Rủi ro tồn dư: Same-user filesystem race giữa kiểm tra cuối và `os.replace` là rủi ro tồn dư đã được chấp nhận trong `docs/security-review.md` (T-07) và ADR-0005.

## 02/10/2026 - T021: Hiệu chỉnh xác thực dọn dẹp file tạm, kiểm tra DACL và fixture Windows (Asia/Bangkok) [Lịch sử vòng sửa 2]

- **Đính chính & Hiệu chỉnh lỗi theo kết quả audit:**
  - **Khắc phục lỗi dọn dẹp khi thay thế tổ tiên cấp cao (`StagedWrite.cleanup`):** Trước đây `StagedWrite.cleanup()` chỉ xác thực thư mục cha trực tiếp của file tạm (`self._temp_path.parent`). Nếu thư mục tổ tiên cấp cao bị thay thế bằng liên kết tượng trưng (symlink/junction) trong khi thư mục cha trực tiếp và file tạm vẫn giữ nguyên inode, hàm dọn dẹp có thể unlink file bên ngoài allowlist. Đã thay thế bằng đường dẫn xác thực dọn dẹp dùng chung `_safe_cleanup_temp`, duyệt kiểm tra từ root đến temp: xác thực thư mục root, toàn bộ danh sách thư mục trung gian theo thứ tự, thư mục cha trực tiếp, và file tạm khớp đúng danh tính descriptor ban đầu, định dạng regular file, không có reparse/link, đúng 1 hardlink (`st_nlink == 1`).
  - **Khắc phục dọn dẹp khi chuẩn bị bị hủy (`prepare_staged_write`):** Trước đây khi gặp lỗi trong quá trình ghi staged, hàm đã unlink file tạm mà chưa có bằng chứng sở hữu đã xác thực qua descriptor (do chỉ lưu danh tính sau khi flush/fsync thành công). Đã hiệu chỉnh để ghi nhận danh tính descriptor (`os.fstat`) ngay lập tức sau khi `tempfile.mkstemp` thành công, trước khi `os.chmod`, `os.fdopen` hay các thao tác ghi có thể thất bại; đồng thời gọi `_safe_cleanup_temp` để chỉ xóa file tạm khi ranh giới và danh tính descriptor đã được xác thực an toàn. Nếu ranh giới hoặc quyền sở hữu bị thay thế, giữ nguyên file tạm và bảo toàn ngoại lệ gốc.
  - **Hiệu chỉnh fixture Windows và kiểm tra byte-exact:** Các fixture Windows trước đây ghi file văn bản với cơ chế chuyển đổi xuống dòng mặc định của nền tảng (CRLF trên Windows) nhưng lại hash chuỗi LF ban đầu, dẫn đến `REVISION_CONFLICT` ngoài dự kiến. Đã chuẩn hóa ghi UTF-8 byte tường minh (`write_bytes`), hash chính xác byte trên đĩa và bổ sung test case synthetic CRLF chứng minh byte thực tế khớp thành công và hash LF cũ bị từ chối fail-closed không thay thế.
  - **Bổ sung xác minh DACL Win32:** Hiệu chỉnh `test_windows_ownership_and_dacl_verification` để truy vấn cả `OWNER_SECURITY_INFORMATION` và `DACL_SECURITY_INFORMATION` thông qua `advapi32.GetNamedSecurityInfoW`, kiểm tra tính hợp lệ của DACL qua `advapi32.IsValidAcl`, đối chiếu user SID của process token qua `EqualSid`, giải phóng token handle và security descriptor đúng cách và chỉ ghi nhận bằng chứng dạng boolean/categorical (không làm lộ raw SID hay tài khoản). Đồng thời bổ sung các test kiểm tra fail-closed cho `_check_windows_ownership` trên các đường dẫn lỗi mô phỏng.
  - **Vệ sinh thông điệp lỗi tạo junction:** Thay thế việc chèn trực tiếp `proc.stderr` vào `pytest.fail` bằng thông điệp chẩn đoán tĩnh đã được vệ sinh, loại bỏ hoàn toàn nguy cơ rò rỉ đường dẫn fixture trong lỗi.

- **Kết quả kiểm tra hiện tại:**
  - `python -m pytest backend/tests/test_markdown_roundtrip.py -q`: 24 passed (dependency T020).
  - `python -m pytest backend/tests/test_source_files.py -q`: 78 passed in 1.23s, line coverage trên `backend/app/adapters/source_files.py` đạt 85% (changed coverage đạt 85.83%, vượt ngưỡng 80.00%).
  - `python -m pytest backend/tests/windows/test_source_paths.py -q`: 9 failed (báo lỗi trung thực fail-closed `_require_native_windows()` do chạy trên Linux, PENDING môi trường Windows native).
  - `python -m mypy backend`: 0 errors (46 source files).
  - `python -m ruff check .`: 0 errors.
  - `npm run format:check`: exit 0 (178 files already formatted).
  - `npm run check:fast`: exit 0.
  - `npm run architecture:check`: exit 0 (7 contracts kept, 40 tests passed).
  - `npm run coverage:check`: exit 0 (changed coverage 85.83% >= 80.00%, total coverage 91.75% >= 86.70%).
  - `npm run security:secrets`: exit 0 (0 finding).
  - `npm run security:code`: exit 0 (0 finding).
  - `npm run security:deps`: exit 0 (0 finding).
  - `npm run check:task`: dừng tại `python -m pytest` do 9 test Windows native fail-closed trung thực trên host Linux (782 passed, 9 failed).

- **Trạng thái & Rủi ro tồn dư (BLOCKED/PENDING):**
  - Task T021 giữ trạng thái `BLOCKED` (tiêu chí Windows acceptance giữ nguyên `[ ]`) cho đến khi có bằng chứng thực thi đầy đủ trên hệ điều hành Windows native (NTFS junction, reparse point, hardlink, DACL).
  - Files đã sửa: `backend/app/adapters/source_files.py`, `backend/tests/test_source_files.py`, `backend/tests/windows/test_source_paths.py`, `docs/changelogs.md`, `tasks/t021-safe-source-files.md`, `tasks/todo.md`.
  - Files chủ ý không sửa: `CONSTRAINTS.md`, `package.json`, `pyproject.toml`, `docs/vocabularies/*`, models/migrations ngoài phạm vi.
  - Rủi ro tồn dư: Same-user filesystem race giữa kiểm tra cuối và `os.replace` là rủi ro tồn dư đã được chấp nhận trong `docs/security-review.md` (T-07) và ADR-0005.

## 02/10/2026 - T021: Khắc phục lỗi kiểm tra bảo mật và xác minh theo kết quả audit (Asia/Bangkok) [Lịch sử vòng sửa 1]

- **Bối cảnh & Quyết định sửa đổi (`backend/app/adapters/source_files.py`):**
  - **Tái kiểm tra toàn diện ranh giới đích tại commit:** Bổ sung bước re-verify toàn bộ các thư mục trung gian từ root đến target; đối chiếu danh tính filesystem (`st_dev`, `st_ino`), chặn symlink, junction, reparse point, thay đổi inode thư mục, quyền truy cập (`os.W_OK | os.X_OK`) và quyền sở hữu Windows. Đảm bảo tấn công thay thế thư mục tổ tiên sau `prepare` (kể cả khi giữ nguyên target inode ngoài root) bị từ chối triệt để với `SECURITY_VIOLATION`, không bao giờ gọi thay thế và giữ nguyên file ngoài.
  - **Xác thực file tạm trước khi thay thế:** Ghi nhận danh tính file descriptor (`st_dev`, `st_ino`) của file tạm độc quyền qua open descriptor (`os.fstat`) ngay khi tạo; tại `commit` kiểm tra khớp đúng danh tính inode ban đầu, định dạng regular file, không có reparse/symlink, đúng 1 hardlink (`st_nlink == 1`), kích thước giới hạn và so khớp byte/hash thực tế với bản ghi đã chuẩn bị. Ngăn chặn triệt để sửa đổi nội dung cùng kích thước, hoán đổi inode/file, thêm hardlink hay link giả mạo.
  - **Dọn dẹp file tạm an toàn:** `cleanup()` chỉ xóa file tạm do chính adapter sở hữu khi nằm trong đúng ranh giới thư mục đích hợp lệ và khớp danh tính descriptor; từ chối unlink qua thư mục hoặc file bị thay thế/symlink, không làm lộ hoặc che giấu ngoại lệ gốc. Việc giữ lại file tạm không thể truy cập an toàn được ghi nhận là giới hạn dọn dẹp chủ động thay vì xóa qua đường dẫn không an toàn.
  - **Tái kiểm tra phân quyền source:** Trước khi thay thế, tải lại bản ghi allowlist hiện tại từ adapter, yêu cầu trạng thái `VALID`, so khớp metadata (`relative_path`, `note_date`, `revision`, `etag`, `content_hash`). Mọi thay đổi về đường dẫn, trạng thái (`INVALID`, `MISSING`), metadata hoặc việc xóa source đều fail-closed và bảo tồn cả hai vị trí đích.
  - **Đóng lỗ hổng chẩn đoán và quyền riêng tư:** Đưa `tempfile.mkstemp` vào khối bắt ngoại lệ đã được vệ sinh; chuyển đổi lỗi tạo, ghi, flush, fsync và replace thành các exception có kiểu rõ ràng với thông điệp tĩnh, không để lộ đường dẫn OS hay nội dung thô. Đóng descriptor an toàn và dọn dẹp file tạm khi lỗi xảy ra trước `fdopen`. Bổ sung hàm kiểm tra `_is_valid_source_id` và `_sanitize_source_id`: chỉ cho phép định danh mờ có giới hạn (alphanumeric, `_`, `-`, tối đa 64 ký tự) xuất hiện trong diagnostics; các giá trị không hợp lệ (path-like, newlines, control chars, oversized) bị loại bỏ hoàn toàn (`source_id=None`) trong `SourceFileError`, `str`, `repr`, `args` và traceback. Loại bỏ việc chèn metadata chưa kiểm tra (như `status`) vào thông điệp lỗi.
  - **64-bit ctypes Win32:** Khai báo tường minh `argtypes` và `restype` cho `advapi32` và `kernel32` (`OpenProcessToken`, `GetTokenInformation`, `GetNamedSecurityInfoW`, `EqualSid`, `LocalFree`, `CloseHandle`, `GetCurrentProcess`), đảm bảo an toàn handle trên Windows 64-bit và fail-closed khi API không khả dụng.

- **Kiểm thử (`backend/tests/test_source_files.py` & `backend/tests/windows/test_source_paths.py`):**
  - **TDD RED phase:** Bổ sung 21 regression test mới trong `test_source_files.py`; xác nhận 12 test thất bại đúng các failure mode được audit (thay thế ancestor, đổi danh tính thư mục, sửa nội dung file tạm cùng kích thước, hoán đổi inode, thêm hardlink, hủy source hoặc đổi status/revision/destination tại commit, mkstemp unhandled errors, rò rỉ source_id sentinels).
  - **TDD GREEN phase:** Cập nhật adapter đưa toàn bộ 70 test portable trong `test_source_files.py` đạt kết quả PASS (100%); line coverage trên `backend/app/adapters/source_files.py` đạt 84.53% (vượt ngưỡng 80.00% theo CONSTRAINTS.md).
  - **Bộ kiểm thử Windows truthful failure (`backend/tests/windows/test_source_paths.py`):** Loại bỏ hoàn toàn các lệnh early return giả lập PASS trên Linux; thay bằng kiểm tra bắt buộc `_require_native_windows()`, báo lỗi rõ ràng `Native Windows runtime unavailable: platform is linux (PENDING genuine Windows environment)` (9 FAILED trên Linux). Bổ sung test thay thế ancestor trên Windows và kiểm tra quyền sở hữu/DACL advapi32 trả về bằng chứng dạng boolean/categorical, không lộ SID hay thông tin tài khoản thô.

- **Kết quả xác minh độc lập:**
  - `python -m pytest backend/tests/test_markdown_roundtrip.py -q`: 24 passed (dependency T020 verified).
  - `python -m pytest backend/tests/test_source_files.py -q`: 70 passed in 1.23s, coverage 84.53%.
  - `python -m pytest backend/tests/windows/test_source_paths.py -q`: 9 failed (báo lỗi trung thực do thiếu môi trường Windows native).
  - `python -m mypy backend`: 0 errors (46 source files).
  - `python -m ruff check .`: 0 errors.
  - `npm run check:fast`: exit 0 (format, lint, typecheck, floor, secrets clean).
  - `npm run architecture:check`: exit 0 (7 kept, 40 gate tests passed).
  - `npm run coverage:check`: exit 0 (changed coverage 84.53%, total coverage 91.67%).
  - `npm run security:secrets`: exit 0 (0 finding).
  - `npm run security:code`: exit 0 (0 finding).
  - `npm run security:deps`: exit 0 (0 finding).
  - `npm run check:task`: dừng tại `python -m pytest` do 9 test Windows native fail-closed trung thực trên host Linux (774 passed, 9 failed).

- **Trạng thái & Rủi ro tồn dư (BLOCKED/PENDING):**
  - Task T021 giữ trạng thái `BLOCKED` (hoặc `TODO`) và tiêu chí Windows acceptance được giữ nguyên chưa check (`[ ]`) cho đến khi có bằng chứng thực thi đầy đủ trên hệ điều hành Windows native (NTFS junction, reparse point, hardlink, ACL/DACL và token verification).
  - Rủi ro tồn dư: race condition cùng user trên filesystem giữa lần revalidation cuối và `os.replace` là rủi ro tồn dư đã được chấp nhận và ghi nhận trong `docs/security-review.md` (T-07) và ADR-0005.
  - Files đã sửa: `backend/app/adapters/source_files.py`, `backend/tests/test_source_files.py`, `backend/tests/windows/test_source_paths.py`, `docs/changelogs.md`, `tasks/t021-safe-source-files.md`, `tasks/todo.md`.
  - Files chủ ý không sửa: `CONSTRAINTS.md`, `package.json`, `pyproject.toml`, `docs/vocabularies/*`, các models/migrations ngoài phạm vi.
  - Môi trường xác minh tiếp theo cần thiết: Máy trạm Windows 11 native (NTFS filesystem, Win32 APIs).

## 02/10/2026 - T021: Triển khai allowlisted source file adapter ban đầu (Asia/Bangkok) [Lịch sử - Đã được cập nhật sửa đổi bên trên]

- **Triển khai adapter (`backend/app/adapters/source_files.py`):**
  - Xử lý mutation qua opaque `source_id`, tra cứu metadata allowlisted, từ chối client-supplied path.
  - Kiểm tra tính hợp lệ của path và root directory: chặn path traversal (`..`), absolute/rooted path, Windows drive syntax, alternate data streams (`:`), UNC/device namespace (`//`, `\\`, `\\?\`), reserved device names (`CON`, `PRN`, `AUX`, `NUL`, `COM1-9`, `LPT1-9`), trailing dots và trailing spaces.
  - Kiểm tra và re-verify danh tính thư mục gốc (`st_dev`, `st_ino`), chặn root depth <= 1 (drive root), phát hiện symlink, junction và reparse point.
  - Kiểm tra target file: bắt buộc regular file, chặn hardlinks (`st_nlink > 1`), phát hiện read-only (`FILE_ATTRIBUTE_READONLY`, access denial).
  - Xác thực nội dung: giới hạn tối đa 8 MiB (`MAX_SOURCE_SIZE_BYTES`), giải mã UTF-8 nghiêm ngặt, kiểm tra cú pháp Markdown hiện tại và mới qua `parse_markdown`.
  - Pre-replacement validation và hash precondition: so khớp SHA-256 hash với `expected_content_hash`, phát hiện sửa đổi đồng thời / stale revision và trả về `REVISION_CONFLICT`.
  - Quy trình ghi bền vững: ghi file tạm độc quyền trong cùng thư mục đích (`.{name}.tmp_*.tmp`), phân quyền an toàn (0600 trên POSIX), `flush` và `fsync`, kiểm tra lại toàn bộ danh tính/hash trước khi thay thế nguyên tử qua `os.replace`. Thất bại trước khi thay thế fail-closed, giữ nguyên file gốc và dọn dẹp file tạm.
  - Giao diện hai pha cho T022: cung cấp `prepare_staged_write` (trả về `StagedWrite` với `commit()` và `cleanup()`) cùng phương thức tiện ích `replace_source_content`.
  - Bảo mật chẩn đoán/privacy: ngoại lệ `SourceFileError` và thông điệp chỉ chứa bounded `source_id` và error code, tuyệt đối không lộ path thật, nội dung Markdown, tài khoản hay SID.
  - Ghi nhận accepted residual risk: race condition cùng user trên hệ thống tệp giữa lần kiểm tra cuối và `os.replace` là rủi ro tồn dư đã được chấp nhận trong `docs/security-review.md` (T-07) và ADR-0005.

- **Kiểm thử (`backend/tests/test_source_files.py` & `backend/tests/windows/test_source_paths.py`):**
  - RED phase ban đầu: 36 test thất bại có chủ đích trên các oracle âm.
  - GREEN phase: 49 test portable trong `test_source_files.py` vượt qua toàn bộ; line coverage trên `source_files.py` đạt 84.62%.
  - Hiệu chỉnh ghi nhận kiểm thử Windows native: Các test Windows trước đây sử dụng early return khi chạy trên Linux, không cấu thành bằng chứng Windows hợp lệ. Điều này đã được thay thế bằng kiểm tra fail-closed trung thực (`_require_native_windows()`) trong bản sửa đổi mới.

- **Trạng thái & Rào cản (BLOCKED/PENDING):**
  - Môi trường chạy hiện tại là Linux (Python 3.12.3). Chưa có môi trường Windows native thực tế để sinh Windows-native evidence cho junction/ACL/reparse.
  - Tiêu chí Windows-native được giữ trạng thái `PENDING`. Task T021 giữ trạng thái `TODO`/`BLOCKED` (chưa đánh dấu `DONE`).

## 02/10/2026 - T021: Independent audit remains environment-blocked (Asia/Bangkok)

- Portable source tests rerun in the T021 worktree: 78 passed; T020 dependency tests: 24 passed; Ruff and Mypy passed with zero errors.
- Windows-native suite remains 11 fail-closed failures on the Linux host because genuine `win32`, NTFS reparse/junction and ACL evidence is unavailable. The implementation is committed on its task branch for preservation; it is not merged into `main`, because doing so would make the repository test gate fail.
## 02/10/2026 - T075: Khắc phục hạ tầng kiểm thử Design System & Test Oracle (Remediation Round 3) (Asia/Bangkok)

- **Mục tiêu & Bối cảnh:** Giải quyết 3 blocking findings từ Independent Re-Audit #3 đối với hạ tầng test `frontend/tests/design-system.test.tsx` mà không làm thay đổi bất kỳ code production hay hành vi nào đã được thẩm định PASS.
- **Khắc phục Blocker 1 (Compiled CSS trong Real Browser):**
  - Cấu trúc lại browser test để nạp CSS thực tế được biên dịch từ `frontend/src/index.css` qua Vite và plugin `@tailwindcss/vite`.
  - Fixture chạy trên React components thực tế, Radix Portal thực tế gắn vào DOM `document.body`, và Playwright Chromium thực tế.
  - Xác thực toàn diện các rendered styles và độ tương phản ở cả Light Mode và Dark Mode (`class="dark"` trên root), kiểm tra destructive normal, destructive hover (sau khi transition ổn định), Dialog surface, Dialog title, Dialog description, và Dialog close focus ring.
- **Khắc phục Blocker 2 (Test Oracle & Mô hình Alpha Compositing):**
  - Chuyển oracle kiểm định độ tương phản từ công thức OKLab interpolation toán học trước đây sang trích xuất giá trị màu thực tế từ Chromium và thực hiện alpha-compositing qua Canvas 2D / display sRGB tiêu chuẩn.
  - Tỉ lệ tương phản Destructive hover đo được trên browser thực tế đạt 5.09:1 (Light) và 5.74:1 (Dark), thỏa mãn WCAG AA (>= 4.5:1).
  - Tách bạch rõ ràng giữa STATIC TOKEN CHECK (kiểm tra token tĩnh opaque) và RENDERED STATE CHECK (kiểm tra runtime trên browser).
  - Bổ sung kiểm thử độc lập đối chiếu (independent cross-check) không dùng helper dùng chung cho 5 trạng thái nhạy cảm (light/dark destructive hover, light/dark close focus, dark dialog title).
- **Khắc phục Blocker 3 (Độ ổn định test, Explicit Timeout & Dọn dẹp Fixture):**
  - Di chuyển hoàn toàn file fixture tạm từ `frontend/src` sang thư mục tạm độc lập của hệ thống (`os.tmpdir()` / `mkdtempSync`), liên kết `node_modules` và dọn dẹp bằng khối `try ... finally` trong `beforeAll` / `afterAll`. Tuyệt đối không để lại file rác trong workspace repository.
  - Thiết lập timeout tường minh 30s (`30000ms`) cho các test browser nặng để bảo đảm không bị timeout dưới tải song song hoặc cold-start của Chromium.
- **Bảo toàn & Verification:**
  - Không sửa đổi bất kỳ file production nào trong `frontend/src` (giữ nguyên `main.tsx`, `index.css`, primitives, `AppShell.tsx`, `shell.css`).
  - Toàn bộ checks đạt chuẩn: `npm run typecheck` exit 0, `npm run lint` exit 0 (0 errors, 3 fast-refresh warnings), `npm run architecture:frontend` exit 0 (24 modules, 27 dependencies cruised), `npm run build` exit 0, `npm run check:fast` exit 0.
  - Focused test `npm run test:frontend -- frontend/tests/design-system.test.tsx` pass 27/27 trong ~5.4s–7.1s qua 2 lần chạy độc lập liên tiếp.
  - Full frontend test: 65/65 pass (38 pre-existing + 27 design-system). T004 AppShell test: 17/17 pass.
  - `npm run check:task` exit 0 (810 Python tests, 65 frontend tests, 40 architecture tests, coverage changed 100.00%, total 92.96%, 0 security findings).
  - Giữ nguyên duplicate task ID T075/T076 theo quy định; không commit; để sẵn sàng cho Independent Re-Audit #4.

## 02/10/2026 - T075: shadcn/ui foundation & Tailwind CSS v4 integration (Asia/Bangkok)

- **Mục tiêu & Bối cảnh:** Tích hợp canonical frontend design-system foundation (shadcn/ui + Tailwind CSS v4) vào ứng dụng React 19 / Vite 8 hiện có; thiết lập path alias `@/*`, `components.json`, semantic tokens, tiện ích `cn()`, và minimal primitives (Button, Card, Dialog); bảo toàn 100% code và hành vi của T004 (AppShell, shell.css).
- **Thực thi Source-Driven & Cấu hình (Remediation Round 2):**
  - Tra cứu tài liệu chính thức: `https://ui.shadcn.com/docs/installation/vite`, `https://ui.shadcn.com/docs/components-json`, `https://ui.shadcn.com/docs/theming`, và registry official shadcn (`https://ui.shadcn.com/r/styles/new-york/*.json`).
  - Thêm dependencies cần thiết: `clsx`, `tailwind-merge`, `class-variance-authority`, `@radix-ui/react-slot`, `@radix-ui/react-dialog`, `lucide-react` và devDependencies `@tailwindcss/vite`, `tailwindcss` (v4).
  - Cấu hình path alias `@/*` -> `frontend/src/*` trong `tsconfig.json` (`baseUrl: "."`, `paths: { "@/*": ["frontend/src/*"] }`) và `vite.config.ts` (`resolve.alias: { '@': resolve(process.cwd(), 'frontend/src') }`).
  - Loại bỏ hoàn toàn workaround Vite transform plugin (`inject-theme-css`) trong `vite.config.ts`.
  - Bổ sung `import '@/index.css';` trực tiếp vào `frontend/src/main.tsx` theo scope extension được chủ repository phê duyệt (chỉ thêm duy nhất 1 dòng import này).
  - Cấu hình Tailwind CSS v4 không dùng Preflight để loại bỏ triệt để hồi quy style của T004: sử dụng `@layer theme, base, components, utilities; @import "tailwindcss/theme.css" layer(theme); @import "tailwindcss/utilities.css" layer(utilities);` và `@source "./components";`. Không import `preflight.css` để bảo toàn heading font-weight (700) và paragraph margins của AppShell T004.
  - Tạo `components.json` chuẩn schema shadcn v4 với style `new-york`, `baseColor: "neutral"`, `cssVariables: true`, `"iconLibrary": "lucide"`, và aliases `@/components`, `@/components/ui`, `@/lib/utils`, `@/lib`, `@/hooks`.
- **Design system tokens & Primitives & A11y:**
  - Thiết lập `frontend/src/index.css` sử dụng cú pháp Tailwind CSS v4 layer imports, `@custom-variant dark`, `@theme inline` với các semantic tokens đáp ứng độ tương phản WCAG 2.2 AA.
  - Điều chỉnh `--destructive: oklch(0.52 0.24 27.325)` trong `:root` để bảo đảm destructive hover với 90% alpha trên nền trắng đạt tỉ lệ tương phản 4.82:1 (>= 4.5:1).
  - Thêm `focus:opacity-100 focus-visible:opacity-100` cho `DialogPrimitive.Close` để focus ring đạt 100% opacity và tỉ lệ tương phản 3.64:1 (>= 3.0:1).
  - Thêm class `text-foreground` tường minh cho `DialogContent` và `DialogTitle` để text trong dark Dialog không bị thừa hưởng màu chữ của legacy shell, đạt tỉ lệ tương phản 17.1:1 (>= 4.5:1).
  - Tạo tiện ích `frontend/src/lib/utils.ts` (`cn()`) dựa trên `clsx` và `tailwind-merge`.
  - Thêm minimal primitives chính thức tại `frontend/src/components/ui/`: `Button` (với variants, asChild, disabled a11y), `Card` (với Header, Title, Description, Content, Footer), `Dialog` (với Trigger, Content, Header, Footer, Title, Description, Overlay, Close).
- **Kiểm thử & Bằng chứng thực tế:**
  - Mở rộng `frontend/tests/design-system.test.tsx` lên 32 tests có bằng chứng thực tế:
    1. Kiểm tra Playwright Chromium headless thực tế đối với Dialog interaction (mở dialog, xác thực DOM và a11y labels `role="dialog"`, bấm nút Close, bấm phím Escape, phục hồi focus về trigger element).
    2. Kiểm tra Playwright Chromium thực tế đối với style của T004 AppShell (xác nhận `.screen-view__title` giữ nguyên `font-weight: 700`, và `.feature-unavailable-note` giữ nguyên `margin-top: 14px`).
    3. Kiểm tra build Vite độc lập trong thư mục tạm có cleanup tự động, xác minh bundle `dist/` tạo ra CSS hợp lệ.
    4. Kiểm tra import tường minh của `index.css` trong `main.tsx`.
    5. Kiểm thử toán học 16 điểm tương phản WCAG AA sử dụng mô hình OKLab alpha-blending cho hover states và focus rings.
  - Toàn bộ checks đạt chuẩn: `npm run typecheck` exit 0, `npm run lint` exit 0, `npm run architecture:frontend` exit 0 (24 modules, 27 dependencies cruised), `npm run build` exit 0 (main, bootstrap, compiled theme CSS), `npm run check:fast` exit 0.
  - `npm run check:task` exit 0: 810 Python tests, 70 frontend tests (38 T004 + 32 design system), 40 architecture tests, coverage changed 100.00%, total 92.96%, 0 security findings (secrets/code/deps).
- **Phạm vi bảo toàn:** Không thay đổi `frontend/src/app/AppShell.tsx`, `shell.css`, backend, migrations, hay API contracts. T076 giữ nguyên trạng thái `TODO`. Thay đổi để uncommitted cho re-audit độc lập.

## 02/10/2026 - Remediation kiến trúc UI và kế hoạch task shadcn/ui (Asia/Bangkok)

- **Mục tiêu & Bối cảnh:** Thiết lập shadcn/ui làm canonical UI component foundation cho toàn bộ feature UI tương lai theo chỉ định của chủ repository; bảo toàn 100% hành vi và bằng chứng của T004 (AppShell routing, landmarks, accessibility, ErrorBoundary, 404).
- **Tạo task cards mới:**
  - `tasks/t080-shadcn-ui-foundation.md` (historical ID T075; canonical path updated by T082): Tích hợp shadcn/ui, Tailwind CSS v4, path alias `@/*`, `components.json`, semantic theme tokens, `cn()` utility và minimal primitives vào ứng dụng Vite hiện tại; không cài `add --all` hay registry bên thứ ba.
  - `tasks/t081-app-shell-shadcn-migration.md` (historical ID T076; canonical path updated by T082): Migrate AppShell sang shadcn/ui và semantic tokens; giữ nguyên toàn bộ hành vi routing/landmarks/a11y/keyboard/heading focus/ErrorBoundary và có bộ test chứng minh tương đương hành vi với T004.
- **Cập nhật kiến trúc UI (`docs/ui-architecture.md`):** Thêm mục *Canonical design system (shadcn/ui)* với 12 quy tắc bắt buộc: primitives tại `frontend/src/components/ui/`, feature composition tại `frontend/src/features/...`, sử dụng semantic tokens, accessibility là trách nhiệm ứng dụng, cấm registry bên thứ ba khi chưa được duyệt, tra cứu official docs mới nhất.
- **Cập nhật dependency graph downstream:** Cập nhật 14 task cards (`t018-consent-ui.md`, `t009-lookup-ui-vertical-slice.md`, `t010-error-handling-recovery.md`, `t025-save-ui-audio.md`, `t028-search-ui.md`, `t030-edit-ui.md`, `t033-review-ui.md`, `t036-quiz-ui.md`, `t038-dashboard-ui.md`, `t050-quiz-runner-ui.md`, `t051-quiz-result-feedback-ui.md`, `t060-status-ui.md`, `t043-accessibility-evidence.md`, `t064-ui-performance-harness.md`) theo mô hình `T004 -> T075 -> T076 -> feature UI tasks`.
- **Trạng thái sẵn sàng:** T018 ở trạng thái `BLOCKED_BY_T075_T076`; task sẵn sàng tiếp theo trên nhánh UI là T075.
- **Kế hoạch & Checkpoint:** Cập nhật `docs/task-plan.md` và `tasks/todo.md` với checkpoint `CP06A` (sau T075, T076), cập nhật Mermaid diagram, adjacency list và danh sách Gemini model allocation. Không thay đổi code implementation trong session planning này.

## 02/10/2026 - T078: Skill phù hợp trong prompt Worker/Fix (Asia/Bangkok)

- Theo yêu cầu chủ repository và hướng dẫn addyosmani/agent-skills, `tools/orchestrator/skills.py` chọn workflow theo phạm vi và tính chất task; phát hiện pack native hoặc `skills_root`/`AGENT_SKILLS_ROOT`, không tự cài plugin.
- `core.py`/`workflow.py`: thêm cấu hình root tùy chọn và manifest skill có path/hash/reason theo phase. Planning nhận policy; Python bảo đảm prompt Worker/Fix yêu cầu đọc/áp dụng skill. Auditor đánh giá bằng chứng thực tế, không tin chỉ lời khai.
- `tests/orchestrator/`: kiểm tra pure scoring/API/UI/Windows source/migration/docs/browser/CI/performance/observability, root precedence và nội dung skill thay đổi; fake-agent flow chứng minh cả prompt triển khai lẫn Fix có yêu cầu.
- `docs/orchestrator.md`: bổ sung cách cài native, discovery/override, mapping, precedence task/host và giới hạn evidence. Không đổi provider/model/CLI flags, source sản phẩm hay run lịch sử. Verification ghi trong thẻ T078: check:task exit0, 810 Python/232 orchestrator tests, 38 frontend/40 architecture tests, changed coverage96.27%, tổng92.90%, ba scanner zero findings; Ruff/format/Mypy đạt. Source freeze giữ nguyên; không gọi model thật.

## 02/10/2026 - T059: Audit lại và tích hợp phần scoring đã triển khai (Asia/Bangkok)

## 02/10/2026 - T077: Timeout phát triển chỉ bật khi cấu hình (Asia/Bangkok)

- Theo yêu cầu chủ repository, `orchestrator.yaml` và Config mặc định `timeout_seconds: null`; bỏ trường cũng không áp deadline cho agent, setup và verification. Số nguyên dương vẫn bật timeout thủ công.
- `tools/orchestrator/core.py`, `runtime.py`: provider protocol chấp nhận timeout tùy chọn; subprocess vẫn polling output, xử lý Ctrl+C, thu hồi tiến trình và giữ exit code trung thực. Git/probe quản trị giữ thời hạn riêng; deadline AI sản phẩm, Fix budget và cơ chế phục hồi không đổi.
- `tests/orchestrator/`: kiểm tra cấu hình/roundtrip, chờ không deadline, output limit/Ctrl+C, ba provider giả và pipeline PASS/Fix đến DONE; không gọi model thật. `docs/orchestrator.md` thêm cách tắt/bật timeout ngay đầu hướng dẫn và giải thích snapshot cấu hình/run FAILED.
- Verification: check:task exit0, 786 Python/208 orchestrator/38 frontend/40 architecture tests; changed coverage100%, total92.80%, ba scanner không có finding. Ruff/format/Mypy đạt.
- Triển khai trong worktree T077 riêng; giữ nguyên source/artifacts T021 đang dở và các run lịch sử. Bằng chứng verification được ghi trong thẻ T077.

- **Bối cảnh:** Run 202610020538470149160000-77174ceb dừng vì JSON PASS chứa findings thông tin. Giữ nguyên run/source/artifact cũ; audit độc lập phần scoring đã có, không chạy lại Worker hoặc inference.
- **Tích hợp:** Candidate dựa trên local main b47d599; scoring/test được sao chép nguyên byte. Todo/changelog cộng dồn với T076, không ghi đè trạng thái task khác hoặc đánh dấu checkpoint. Áp dụng documentation-and-adrs. Audit độc lập PASS cả ba tiêu chí; source/test không đổi. 105 focused tests, probe45tổ hợp/270hoán vị và checks tĩnh đạt; check:task exit0 trên snapshot đóng băng:763 Python/38 frontend/40 architecture, scoring line/branch100%, changed100%, total92.78%, ba scanner0finding. Chỉ cập nhật bookkeeping ghi bằng chứng sau gate; promotion dưới khóa tích hợp, main sạch/không đổi và ff-only; không push.

## 02/10/2026 - T076: Làm rõ báo cáo audit và sửa JSON trước khi kết thúc (Asia/Bangkok)

- **Thay đổi:** Schema và prompt Auditor quy định findings chỉ chứa lỗi chưa giải quyết; bằng chứng đạt/kết quả lệnh nằm trong acceptance_criteria[].evidence. Kiểm tra semantic trong vòng gọi agent tối đa ba lượt, lưu/băm JSON bị từ chối và gửi phản hồi để Auditor sửa cùng snapshot, không thêm lượt Worker hay tăng fix_cycle. FAIL thật vẫn vào vòng Fix; không tự xóa finding, đổi verdict hoặc chấp nhận bằng chứng lệnh thất bại.
- **TDD/phạm vi:** Baseline 171 pass (132.56s); RED 11 fail/3 pass (20.18s); GREEN 14 pass (24.30s). Bốn file code/test cùng guide/card/todo/changelog T076; không sửa ứng dụng/config/provider/dependencies/threshold hay gọi inference thật. 89 artifact và snapshot source T059 giữ nguyên; phục hồi run FAILED lịch sử nằm ngoài task. Áp dụng documentation-and-adrs.
- **SOURCE FREEZE/kiểm tra:** 185 test orchestrator pass (171.09s); check:task exit0 trên source bất biến, 718 Python/38 frontend/40 architecture tests, changed coverage96.30%, total92.40%, ba scanner0finding. Ruff/formatter/Mypy49file/diff check đạt; chỉ cập nhật bookkeeping ghi evidence sau gate. Promotion yêu cầu khóa tích hợp, local main sạch/không đổi và ff-only; không push.

## 02/10/2026 - T059: Khắc phục lỗi P1 kiểm tra quyền sở hữu câu trả lời (Asia/Bangkok)

- **Nguyên nhân/mục tiêu:** Khắc phục lỗi bảo mật P1 đã kiểm toán (Answer Ownership Defect). Trước đây, `score_mcq`, `score_cloze`, và `score_writing` không kiểm tra `AnswerInput.question_id` khớp với `question.id`, và `score_quiz` chỉ kiểm tra tập key của `Mapping[str, AnswerInput]` thay vì kiểm tra `ans.question_id == key`. Điều này dẫn đến nguy cơ gán điểm tự đánh giá writing của câu hỏi khác sang word form của câu hỏi đích.
- **Giải pháp xử lý (pure validation):**
  - Trong từng hàm chấm câu đơn (`score_mcq`, `score_cloze`, `score_writing`): khi tham số là `AnswerInput`, bắt buộc `answer.question_id == question.id` trước khi xử lý câu trả lời hoặc điểm tự chấm (kể cả trường hợp rỗng, null hoặc pending). Nếu không khớp, raise `QuizScoringError` với thông báo chẩn đoán định danh cụ thể, tuyệt đối không để lộ nội dung câu trả lời hay dữ liệu bài học. Giữ nguyên hành vi của các dạng input raw (string/tuple/None).
  - Trong `score_quiz`: duyệt và xác thực từng key trong mapping với `AnswerInput.question_id` tương ứng trước khi vào vòng lặp chấm điểm. Bất kỳ sai lệch nào đều raise `QuizScoringError` ngay lập tức, không ghi đè, không re-key hay thay thế câu trả lời rỗng.
- **TDD / Kiểm chứng:**
  - RED: Viết regression tests cho cả 3 hàm chấm đơn và aggregate mapping (foreign ID, swapped values giữa 2 câu writing có word form khác nhau, reused input dưới 2 key khác nhau). Lệnh `python -m pytest backend/tests/test_quiz_scoring.py -q` ghi nhận RED với 6 failures / 39 passed (exit code 1).
  - GREEN: Sau khi sửa, 45 test focused đều PASS trong 0.23s, đạt 100% line & branch coverage trên `backend/app/assessment/scoring.py` (242 stmts, 80 branches).
  - Gate tổng thể: `npm run check:task` exit 0 (749 test Python, 38 test frontend, 40 test architecture; changed coverage 100.00%, total coverage 92.74%; 0 findings từ Gitleaks, Semgrep, OSV-Scanner; 7 architecture contracts kept). `npm run architecture:check` exit 0. `mypy backend` và `ruff check`/`format` đều exit 0.
- **Phạm vi:** Chỉ sửa 2 file implementation/test (`backend/app/assessment/scoring.py`, `backend/tests/test_quiz_scoring.py`) cùng bookkeeping T059 (`tasks/t059-quiz-scoring.md`, `tasks/todo.md`, `docs/changelogs.md`). Giữ nguyên các module database, HTTP, UI và dữ liệu từ vựng; áp dụng documentation-and-adrs theo AGENT.md.

## 02/10/2026 - T059: Pure quiz scoring và weakest-rating oracle (Asia/Bangkok)

- **Nguyên nhân/mục tiêu:** Triển khai module pure domain scoring cho bài kiểm tra (MCQ, cloze, writing) và quy tắc weakest-rating oracle theo ADR-0005 C013-03 / docs/spec.md FR-ASM-05–08; AC-16/19/30.
- **Quy tắc chấm/oracles:**
  - MCQ: so khớp option ID chính xác với snapshot correct_option_id; rỗng/None là BLANK/AGAIN; option ID ngoài snapshot options bị từ chối; selfScore bị cấm.
  - Cloze: chuẩn hóa NFC, trim/collapse ASCII whitespace (`[ \t\r\n\x0c\x0b]+`), Unicode casefold; giữ nghiêm ngặt chính tả, dấu, punctuation và non-ASCII whitespace; rỗng là BLANK/AGAIN.
  - Writing: tự chấm điểm nguyên 0..4 (0/1->AGAIN, 2->HARD, 3->GOOD, 4->EASY); null là pending chặn nộp; text rỗng chỉ hợp lệ với điểm 0; text rỗng có điểm dương bị từ chối.
  - Weakest rating: xác định duy nhất một rating yếu nhất theo wordFormId theo thứ tự `AGAIN < HARD < GOOD < EASY`, độc lập với thứ tự câu hỏi và không tính trung bình.
  - Objective scores: tính toán chính xác tổng câu, số câu đã trả lời (attempted), số câu đúng (correct), và độ chính xác accuracy (null khi attempted bằng 0).
- **TDD / Kiểm chứng:**
  - RED: kiểm tra import khi chưa có module báo lỗi `ModuleNotFoundError: No module named 'backend.app.assessment'` (pytest exit 2).
  - GREEN: 38 test focused đạt trong 0.38s, đạt 100% line và branch coverage trên `backend/app/assessment/scoring.py`.
  - Gate tổng hợp: `npm run check:task` exit 0 (742 test Python/frontend/architecture, changed coverage 100%, total coverage 92.73%, 0 findings từ Gitleaks/Semgrep/OSV-Scanner, 7 architecture contracts kept).
  - Phạm vi: đúng 2 file source/test (`backend/app/assessment/scoring.py`, `backend/tests/test_quiz_scoring.py`) cùng bookkeeping T059 (`tasks/t059-quiz-scoring.md`, `tasks/todo.md`, `docs/changelogs.md`). Giữ nguyên các module database, HTTP, UI và dữ liệu từ vựng; áp dụng documentation-and-adrs theo AGENT.md.

## 02/10/2026 - T075: Sửa kiểm tra capability agy trên stderr (Asia/Bangkok)

- **Nguyên nhân:** agy1.2.14 in --help ra stderr, adapter chỉ đọc stdout nên báo thiếu --print trước Worker. Kiểm tra cả hai kênh, từ chối probe lỗi/timeout/quá giới hạn và bỏ yêu cầu --print không dùng trong lệnh stdin headless; các cờ thực sự dùng vẫn bắt buộc.
- **Phục hồi:** Chỉ lỗi --print pre-dispatch đã xác định được tạo run mới khi source/history, task/plan/contract, prompt/schema còn nguyên và chưa có log/response Worker. Giữ bằng chứng cũ; từ chối source drift, tampering, schema/attempt thiếu, outcome không rõ hoặc provider khác.
- **TDD/phạm vi:** Baseline144pass115.20s; RED6fail/7pass6.74s tái hiện lỗi help và thiếu recovery, thêm RED1fail2.65s phát hiện prompt invocation bị sửa. Chỉ runtime/workflow, hai test, guide và bookkeeping T075; không sửa ứng dụng/config/credentials/scanners hay chạy inference. Áp dụng documentation-and-adrs. SOURCE FREEZE: focused171pass130.47s; check:task exit0,704 Python/38 frontend/40 architecture tests, changed coverage97.22%, total92.36%, ba scanner0finding; Ruff/format/Mypy49file/diff check đạt. Native agy help được chấp nhận với inference giả lập; kiểm tra chỉ đọc xác nhận T021 đủ điều kiện retry, artifact cũ nguyên vẹn.

## 02/10/2026 - Tra cứu nhanh lệnh orchestrator (Asia/Bangkok)

- **Tài liệu:** Thêm bảng trường hợp/lệnh ngay đầu `docs/orchestrator.md`: dry-run, chạy chưa tích hợp/toàn bộ, status theo run ID, resume, retry, cấu hình Worker GPT và chờ khóa tích hợp. Giải thích ngắn worktree, model mặc định agy, điều kiện retry và nạp cấu hình scanner để tra cứu khi chạy task.
- **Kiểm tra/phạm vi:** Đối chiếu CLI/parser và luồng hiện tại; áp dụng documentation-and-adrs. Chỉ sửa tài liệu/changelog, không sửa runtime, config, task status hay evidence cũ; kiểm tra lệnh bằng `--help`, diff và secret scan trước commit.

## 02/10/2026 - T073 đã tích hợp vào main và kiểm tra sau merge (Asia/Bangkok)

- **Git:** Commit `da6349c9cc86870d4e2f83546362bafb15c909bb`, ff-only main sạch từ6bc055a dưới integration lock. Staged diff đúng tám file, Gitleaks trước commit0finding; không push hay sửa worktree/run cũ.
- **Kiểm tra:** Trên main,101 test orchestrator đạt109,07s; formatter/Ruff/Mypy đạt49file. T059/T021 vẫn đủ điều kiện phục hồi bằng kiểm tra chỉ đọc, mọi JSON cũ nguyên vẹn; không gọi provider/task thật. Bằng chứng bổ sung chỉ sửa card/changelog, code/tests giữ nguyên bản đã đạt full gate634test.
- **Sử dụng:** `run T059 --no-integrate` tự tạo lần thử mới đủ bằng chứng; run ổn định được tiếp tục. Lỗi agent có thể sửa được thử lại tối đa ba lần; hết khả năng sửa trả FAILED, không dừng bằng BLOCKED mới hay giả DONE. Áp dụng documentation-and-adrs theo AGENT.md.

## 02/10/2026 - Phân công GPT-6.1 Sol cho task phức tạp (Asia/Bangkok)

- **Tài liệu:** Cập nhật `docs/task-plan.md`: thay đề xuất GPT-6 Astra lịch sử bằng GPT-6.1 Sol, bổ sung bảng nhóm task/rủi ro và yêu cầu Prompt Engineer ghi MODEL/REASONING/WHY. Reasoning chọn theo từng run, không hardcode task ID; ghi rõ Codex model ID cần khớp lựa chọn và model null không pin model.
- **Đối chiếu card:** T027 chuyển sang GPT do signed cursor/query/source-revision boundary; T059 chuyển sang Gemini/agy vì pure scorer không persistence/UI/AI. Giữ scope/dependencies/acceptance/task status/checkpoint và phân biệt baseline planning cũ với hiện trạng Git/filesystem.
- **Giới hạn/phạm vi:** Chỉ sửa task-plan và changelog, áp dụng documentation-and-adrs. Không sửa runtime/config hay tuyên bố auto-routing đã có: Level 1 vẫn dùng roles.worker trong cấu hình run. Kiểm tra cấu trúc, bảng model/danh sách, task links và diff whitespace; không cần chạy lại application tests cho thay đổi tài liệu.

## 02/10/2026 - T074 hoàn tất kiểm tra Worker agy và quyền thực thi (Asia/Bangkok)

- **Gate cuối:** Sau SOURCE FREEZE, check:task exit0: 677 test Python (144 orchestrator), 38 test frontend, 40 test architecture. Coverage thay đổi100%, tổng92,32%; Gitleaks/Semgrep/OSV0findings. Ruff/format/Mypy49file và diff check đạt; npm ci không làm đổi manifest/lock.
- **Kiểm chứng CLI/phục hồi:** agy1.2.14 stdin headless xác nhận qua /help không tiêu quota; JSON SUCCESS được xử lý đúng, lỗi/denied_actions/schema sai vẫn fail. T021/T059 đủ điều kiện retry sau đổi route, state cũ giữ nguyên; không gọi task/model thật. T074 DONE, checkpoint/task sản phẩm nguyên trạng.
- **Phạm vi/Git:** Chỉ ba module orchestrator, hai test, config, guide và bookkeeping T074; giữ code/test/config hash cuối. Owner đã yêu cầu commit/merge main; kiểm tra staged scope/secrets trước ff-only dưới integration lock, không push. Documentation-and-adrs áp dụng cho guide/card/changelog; bằng chứng runtime ignored tại worktree T074.

## 02/10/2026 - T074: Worker qua Antigravity CLI và quyền chạy rõ ràng (Asia/Bangkok)

- **Nguyên nhân/quyết định:** Owner dùng `agy`, nhưng config cũ gọi Gemini CLI độc lập. Thêm provider agy, Worker mặc định gemini-3.8-flash-high đã được `agy models` xác nhận. Giữ Codex/Gemini, không fallback ngầm hoặc thay AI runtime sản phẩm.
- **Quyền:** GPT Worker có worker_access full-access → Codex danger-full-access/approval never; agy Worker allow_process → session skip-permissions/accept-edits. Các vai trò chỉ đọc không được nâng quyền. Không chỉnh cấu hình toàn máy, credentials, scope hay scanner threshold.
- **Khôi phục:** Chuyển route Gemini CLI exit1 sang agy cho phép run mới khi log failed/no-output còn hash, source/history/evidence cũ nguyên vẹn, chưa có implementation/integration. Lưu các run/worktree cũ; không giả định lỗi exit1 đã chứng minh thất bại trước dispatch.
- **Bằng chứng ban đầu:** Baseline101 pass92.87s; RED32fail5.67s do schema chưa hỗ trợ agy/quyền; GREEN32pass9.74s trước điều chỉnh stdin thật. agy1.2.14 help/changelog và lệnh /help cục bộ xác nhận stdin headless; không chạy model trong chẩn đoán. Kiểm tra cuối đang thực hiện, không gọi gate chưa chạy là PASS. Documentation-and-adrs được áp dụng; source/Git policy tham chiếu Codex help tại máy theo yêu cầu không dùng web.

## 02/10/2026 - T073: Tự phục hồi agent, bỏ điểm chờ BLOCKED trong luồng mới (Asia/Bangkok)

- **Nguyên nhân:** Gemini0.59.0 exit55 là FatalUntrustedWorkspaceError trước dispatch, worktree mới chưa trusted. Adapter kiểm tra/truyền --skip-trust cho phiên được giao; Worker dùng yolo theo yêu cầu chạy không duyệt tương tác, không đổi trust/credentials toàn máy.
- **Luồng:** Thử lại agent/planning tối đa ba lần chỉ khi source/state/handoff bất biến; output Worker/Auditor BLOCKED đi vào vòng Fix; lỗi thực tế hết khả năng sửa trả FAILED, không giả PASS/DONE. run tự resume bước ổn định hoặc retry lỗi trước triển khai đủ bằng chứng; ngoại lệ hẹp cho exit55, giữ run/worktree cũ. Scope/test/security/integration fencing vẫn được kiểm tra.
- **TDD/phạm vi:** Baseline86pass; RED7fail/9pass chứng minh thiếu session trust, retry, remediation và recovery. Chỉ hạ tầng orchestrator/tests và tài liệu task T073, không đổi ứng dụng/dữ liệu/credentials hoặc artifact cũ. Dùng documentation-and-adrs theo AGENT.md; SOURCE FREEZE cuối: check:task exit0,634 test Python (101 orchestrator), frontend coverage và40 test architecture; changed coverage94,44%, total92,23%, ba scanner0finding. Ruff/formatter/Mypy đạt49file. Gate đầu bị lệch snapshot do chỉnh lời guide đã được chạy lại nguyên vẹn; gate cuối source bất biến. T059/T021 đủ điều kiện retry chỉ bằng kiểm tra đọc, không gọi model/task thật.

## 02/10/2026 - T072 đã commit và tích hợp vào main (Asia/Bangkok)

- **Git:** Commit `3574e166dc1ad7d4a01de5c75ae98c41917681d2`, ff-only main sạch từ `e7c1ad5` dưới khóa tích hợp. Staged diff đúng chín file, source hash khớp bản đã qua gate tổng, Gitleaks trước commit không có finding. Không push hoặc thay đổi worktree/run cũ.
- **Sau merge:** Trên main, 86 test orchestrator đạt trong 81,18s; formatter/Ruff/Mypy đạt (49 file). Kiểm tra chỉ đọc xác nhận T059 run `202610011631074539710000-7d6c660f` đủ điều kiện retry; JSON cũ nguyên vẹn, không gọi model. Bằng chứng bổ sung chỉ sửa card T072 và changelog, implementation/tests giữ nguyên. Áp dụng documentation-and-adrs theo AGENT.md.

## 02/10/2026 - T072 hoàn tất kiểm tra với quyền verification rõ ràng (Asia/Bangkok)

- **Kiểm tra cuối:** Sau SOURCE FREEZE, nguyên `check:task` đạt: 619 test Python (86 orchestrator), frontend coverage tests và 40 test architecture; coverage thay đổi100%, tổng92,12%; Gitleaks/Semgrep/OSV không có finding. Ruff/Mypy/formatter đạt, manifest/lock không đổi. Giữ nguyên lệnh/phạm vi test/scanner; không skip hoặc giảm threshold. Bốn case bổ sung xác minh input legacy sai vẫn bị từ chối và resume legacy giữ nguyên artifact.
- **Khôi phục/phạm vi:** T059 run `202610011631074539710000-7d6c660f` đã đủ điều kiện retry theo cơ chế mới; đối chiếu chỉ đọc, JSON/run/worktree cũ nguyên vẹn, không gọi model hoặc chạy task thật. T072 DONE; không thay status task/checkpoint sản phẩm hay viết lại bằng chứng lịch sử T071.
- **Tích hợp:** Người dùng yêu cầu hoàn tất rồi commit/merge main. Stage đúng bốn file code/test cùng năm file tài liệu/bookkeeping; scan secrets, ff-only main sạch dưới khóa tích hợp, không push. Chỉ bookkeeping đổi sau test; source hash và metadata kiểm tra được lưu trong runtime ignored. Áp dụng documentation-and-adrs theo AGENT.md.

## 01/10/2026 - T072: Bỏ human_gates theo yêu cầu chủ repository (Asia/Bangkok)

- **Quyết định/phạm vi:** Bỏ trường `human_gates` trong contract/template/schema mới và veto planning/retry trong Python. Ghi ADR-0007, không sửa/xóa ADR cũ. Test/scanner có sẵn giữ lệnh, phạm vi và threshold do repository chọn; agent không tự đưa approval mới vì chúng đọc file cục bộ. Không tự đọc/sao chép dữ liệu học hoặc credentials vào prompt/report, không sửa dữ liệu và vẫn dùng fixture tổng hợp cho test mới.
- **Tương thích:** Đọc Plan/Contract cũ qua lớp chuyển đổi hẹp trong bộ nhớ, chỉ xử lý trường đã bỏ; giữ file/hash/worker prompt gốc. Retry tạo run/Plan mới cho lỗi gate cũ đủ bằng chứng trước Worker; không nới kiểm tra phạm vi, dependency, source/Git/artifact, khóa, exit code, audit hoặc tích hợp.
- **TDD:** Baseline 76 test pass; RED bảy test mới fail đúng schema/compatibility/retry/prompt authority. GREEN selection chín test pass. Test veto cũ được thay bằng hành vi chủ repository vừa yêu cầu và regression schema strict/old gate retry; không skip test hay xóa assertions bảo vệ độc lập. Kiểm tra cuối đang thực hiện; áp dụng documentation-and-adrs theo AGENT.md.

## 01/10/2026 - T071 đã tích hợp vào main theo yêu cầu người dùng (Asia/Bangkok)

- **Git:** Commit tập trung `c4924cd33014d6c55bac5a035e7e71e930a34034`, ff-only main từ `b9530b9` dưới khóa tích hợp. Kiểm tra staged scope tám file, source hash bất biến, staged diff và Gitleaks trước commit đều đạt. Không push hoặc thay đổi các worktree task khác.
- **Sau tích hợp:** CLI main có `retry`; 76 test orchestrator trên main đạt trong 71,32s, Ruff/formatter/Mypy đạt (49 file). Bổ sung bằng chứng vào card T071, cập nhật todo về việc đã promotion; commit bằng chứng chỉ sửa ba file bookkeeping, giữ nguyên implementation/tests đã kiểm tra.
- **Giới hạn:** `check:task` vẫn chưa chạy do test T020 đọc dữ liệu thật; không báo gate tổng PASS, không sửa test ngoài phạm vi, không đánh dấu T071/checkpoint DONE. Không chạy lại T021/T059 thật, gọi model trả phí hay thay đổi run JSON. Áp dụng skill documentation-and-adrs theo AGENT.md.

## 01/10/2026 - Cho phép tích hợp bản sửa T071 đã kiểm tra tập trung (Asia/Bangkok)

- **Quyền thực hiện:** Người dùng yêu cầu commit và merge vào main sau khi giới hạn gate tổng đã được trình bày. Tích hợp bản sửa T071 trong phạm vi hiện có; không suy diễn quyền sửa test T020 hay bỏ ràng buộc dữ liệu thật.
- **Kiểm tra/trạng thái:** Giữ bằng chứng 76 test orchestrator, static/security/architecture đã đạt; kiểm tra lại staged diff và secret scan trước commit, rồi kiểm tra tập trung trên main. `check:task` vẫn chưa chạy do xung đột policy đã ghi; T071 và checkpoint sản phẩm không được đánh dấu DONE.
- **Git/phạm vi:** Chỉ stage tám file T071 cho phép; ff-only main sạch từ `b9530b9` dưới khóa tích hợp repository. Không push, không sửa/xóa worktree hoặc JSON của các run T021/T059. Áp dụng skill documentation-and-adrs theo AGENT.md; kết quả tích hợp được bổ sung vào card T071.

## 01/10/2026 - T071: Contract bất biến và chạy lại an toàn trước Worker (Asia/Bangkok)

- **Nguyên nhân:** Plan của T021 diễn giải lại `objective`, `forbidden_scope`, `stop_conditions` và thêm glob vào danh sách đường dẫn chính xác. Validator chặn đúng nhưng prompt chưa cung cấp template nguyên văn và thông báo thiếu tên trường.
- **Sửa hạ tầng:** Python tạo contract mẫu dùng chung với validator; Prompt Engineer phải giữ nguyên trường bất biến, tách diễn giải sang prompt Worker. Lỗi chỉ ghi tên trường/chỉ số mục, không ghi nội dung riêng tư. Không tự chuẩn hóa contract lệch, bỏ human gate hoặc sửa artifact cũ.
- **Chạy lại:** Theo yêu cầu mới, ghi mở rộng phạm vi trước khi thêm CLI `retry`. Run/worktree mới được tạo từ main cục bộ hiện tại sau khi xác minh lần cũ dừng trước Worker, source/history/task/artifact bất biến và không có human gate; giữ toàn bộ lần cũ. Lỗi trùng worktree bị từ chối trước khi tạo bản ghi rỗng. Run mới có `retry_of`, bằng chứng nguồn và chạy lại baseline; khóa run/task ngăn cạnh tranh với tiến trình sống.
- **Kiểm tra:** Baseline 57 pass; RED planning ba fail/một pass. RED retry 11 fail; RED artifact lịch sử một fail. Sau sửa lỗi và SOURCE FREEZE: 76 test orchestrator pass với provider giả, changed executable lines 90/94 covered (95,74%); Ruff/Mypy/check:fast đạt, Gitleaks/Semgrep không có finding; architecture giữ bảy contract, 40 test gate đạt. Kết quả 61 test/18 dòng trước mở rộng là lịch sử. Chưa chạy `check:task`: test T020 đọc dữ liệu từ vựng thật, xung đột với quy định automated tests hiện tại; không báo gate tổng PASS.
- **Phạm vi/trạng thái:** Bốn file code/test (`core.py`, `workflow.py`, `__main__.py`, `test_workflow.py`) trong worktree T071 cùng guide/card/todo/changelog. Không sửa ứng dụng, task T021/T020, migration, dependency hay JSON các run đang tồn tại. Đối chiếu chỉ đọc xác nhận T059 có run sở hữu worktree đủ điều kiện; T021 vẫn có human gate. Bản sửa chưa commit/merge vào main; `retry` chưa có trên main. Áp dụng skill documentation-and-adrs theo AGENT.md; bằng chứng tại `tasks/t071-orchestrator-planning-contract.md`.

## 01/10/2026 - Tích hợp orchestrator vào main cục bộ (Asia/Bangkok)

- **Git:** Theo yêu cầu người dùng, commit bản dịch `69c4ff5` và merge fast-forward nhánh `feature/task-t067-level1-orchestrator` vào `main`, từ `8dba872` đến `69c4ff5`. Không push, không thay đổi các worktree khác.
- **Bằng chứng:** `npm run check:task` trên bản tích hợp trả về 0: 590 test Python (gồm 57 test orchestrator), 38 test frontend, 40 test gate kiến trúc; coverage thay đổi 89,34%, ba scanner không có finding. Ruff, Mypy, build, Alembic head và dry-run T008 cũng đạt. Chi tiết tại `docs/reviews/orchestrator-integration-001.md`; báo cáo task-branch cũ được liên kết tới bằng chứng tích hợp mới.
- **Phạm vi:** Commit ghi bằng chứng chỉ thay đổi tài liệu; source, cấu hình, migrations, API/client sinh tự động, dữ liệu người dùng và trạng thái checkpoint sản phẩm không thay đổi sau kiểm tra. Áp dụng skill documentation-and-adrs theo AGENT.md.

## 01/10/2026 - Dịch hướng dẫn orchestrator sang tiếng Việt (Asia/Bangkok)

- **Tài liệu:** Dịch toàn bộ `docs/orchestrator.md` sang tiếng Việt, giữ nguyên cấu trúc, lệnh thực thi, đường dẫn, tên cấu hình, trạng thái và ý nghĩa kỹ thuật. Áp dụng skill documentation-and-adrs theo AGENT.md.
- **Phạm vi:** Chỉ thay đổi hướng dẫn và mục changelog này; source, tests, cấu hình, task status và lịch sử changelog được giữ nguyên. Đối chiếu lệnh/trạng thái với bản gốc và kiểm tra `git diff --check`; không chạy lại test ứng dụng cho thay đổi tài liệu.

## 01/10/2026 - Verified Level 1 autonomous agent workflow (Asia/Bangkok)

- **Implemented:** T067–T070 on `feature/task-t067-level1-orchestrator`: deterministic Python state/JSON contracts, capability-probed Codex/Gemini CLI adapters, separate outside worktrees/run artifacts, three independent processes, automatic bounded fix cycle and serialized verified-SHA integration. No database/framework or production runtime dependency.
- **Remediation:** Independent review findings are covered by regression tests. Resumed RED proved LockBusy after integration entry incorrectly remained active/pending; the minimal guard now records BLOCKED. T070 removes only the inherited unused suppression; AST unchanged.
- **Verification:** 57 focused tests and 590 full Python tests pass; 38 frontend tests, 40 architecture tests and all `check:task` gates pass. Ruff/format/Mypy/build/contract pass; changed coverage 89.34%, total 91.98%; Gitleaks/Semgrep/OSV each zero findings. Initial sandbox gate exit 130 is recorded as interrupted, never PASS. Final evidence uses the frozen remediated source.
- **Documentation/bookkeeping:** Added [guide](orchestrator.md), [ADR-0006](adr/0006-local-agent-orchestration.md) and [final handoff](reviews/orchestrator-verification-001.md); completed only infrastructure cards/todo entries. The prior pause checkpoint remains historical. Required documentation-and-adrs skill applied.
- **Safety/limits:** No real inference, credentials, package/lock drift, migration/contract drift, main promotion or push. Existing task worktrees and product checkpoints unchanged. Linux/WSL validated; native Windows integration blocks pending recovery evidence. Trusted local agents, conservative conflict handling and explicit integration opt-in remain required.
- **Git:** User-authorized focused Conventional Commit follows staged scope and secret review; implementation remains on its feature branch.

## 01/10/2026 - Level 1 orchestrator implementation paused with checkpoint (Asia/Bangkok)

- **Status:** PAUSED_BY_USER, not DONE; requested pause preserved all unstaged work on `feature/task-t067-level1-orchestrator`, base/HEAD `8dba8726c49585effc3c72ae790bf0b766eeea44`. No commit, main merge, push or real provider inference.
- **Infrastructure:** Added typed JSON contracts/atomic state, bounded CLI providers, outside Git worktrees, autonomous planning/Worker/audit/fix flow, 1–3 isolated processes and repository-global serialized verified-SHA integration under `tools/orchestrator/`; added tests under `tests/orchestrator/`, config and runtime ignores. T067–T070 split explicit file ownership; existing product task/checkpoint state remains unchanged.
- **Quality/docs:** Extended Python verification ownership without weakening thresholds; T070 removes only the inherited unused E501 suppression in `scripts/tests/test_contract.py` (AST equal). Added orchestrator guide, ADR-0006 and infrastructure planning/todo entries using the required documentation skill.
- **Evidence limits:** Latest focused snapshot passed 56 tests; final annotated multi-file scope parser change followed that run, so final tests/static evidence need rerunning. Current T018/T008 dry runs exit 0 without invoking agents. No current full-suite/aggregate/security/build/coverage verdict exists.
- **Handoff:** [Checkpoint](reviews/orchestrator-checkpoint-001.md) records implementation, independent review remediation, exact checks, limitations and remaining verification/commit steps. Existing dirty T018 and other worktrees remain untouched; no matching test/orchestrator job was running at pause.

## 01/10/2026 - Checkpoint CP06 verification and closure (Asia/Bangkok)

- **Audit/base:** Verified integrated repository state on `main` at `2dd220f368d40588fa9839237d5c4ed38a818474` (`fix(T016): linearize admission migration after review schema`). CP06 covers T015 (consent persistence/API), T007 (bridge transport adapter with fake proxy), and T016 (AI admission fence). All three tasks verified complete with sufficient evidence. Documentation follows the repository-required documentation-and-adrs skill.
- **Task review:**
  - T015: Confirmed initial `NOT_GRANTED` behavior, ready-only grants, stale ETag/digest denial, no implicit grants, offline revocation, atomic policy/event/receipt transactions via OperationLedger, fail-closed storage integrity, durable append-only event history, and no sensitive telemetry or real provider inference.
  - T007: Confirmed no-key models preflight 401 requirement, keyed shape 200 via mock transport, missing key and unsafe URL fail-closed handling, loopback trust boundary preservation (`trust_env=False`, `follow_redirects=False`), absolute shrinking deadline across preflight and dispatch, 4 MiB bounded streaming, no auto-retries, no Google token/admin access, and no real inference. The known bookkeeping discrepancy (`Status: TODO` in card header vs `[x]` in todo.md) was investigated and resolved as a stale card documentation omission; updated T007 card header to `Status: DONE` and marked criteria complete.
  - T016: Confirmed durable admission fence before dispatch, revoke-before-admission and revoke/regrant ABA denial of old intents, preflight denied by missing/revoked consent, admitted-before-revoke completing exactly once with subsequent intents denied, model/route matching captured policy, two-process SQLite race safety without process-local mutex, no open DB transaction across network, duplicate admission / PENDING->UNKNOWN recovery refusal, and linear migration chain `0005_review -> 0006_ai_admission`.
- **Focused tests:** All focused CP06 suites exit 0:
  - `python -m pytest backend/tests/test_consent.py -q`: exit 0 (150 passed in 26.42s).
  - `python -m pytest backend/tests/test_bridge.py -q`: exit 0 (14 passed in 0.46s).
  - `python -m pytest backend/tests/test_ai_admission.py -q`: exit 0 (60 passed in 13.63s).
  - `python -m pytest backend/tests/test_operations.py -q`: exit 0 (14 passed in 3.65s).
  - `python -m pytest backend/tests/test_vocabulary_storage.py -q`: exit 0 (16 passed in 3.41s).
  - `python -m pytest backend/tests/test_srs.py -q`: exit 0 (60 passed in 6.72s).
- **Full regression & gates:** Full test suites and aggregate gates exit 0:
  - `python -m pytest -q`: exit 0 (533 passed in 87.28s).
  - `npm run test:frontend:coverage`: exit 0 (38 passed in 776ms).
  - `npm run check:task`: exit 0 (cleanly executing fast checks, 38 frontend tests, 533 Python tests, coverage check, all 3 security scans, and 40 architecture tests).
- **Static, lint & build:**
  - `python -m mypy backend`: exit 0 (43 source files checked, 0 errors).
  - `npm run typecheck`: exit 0 (zero TypeScript errors).
  - `npm run lint`: exit 0 (0 errors, 2 fast-refresh warnings in AppShell.tsx).
  - `npm run build`: exit 0 (Vite build in 369ms).
  - `npm run format:check`: exit 0 (154 files formatted).
  - Scoped Ruff check / format on 10 CP06 files: exit 0 (clean).
  - `npm run floor:check`: exit 0 (`floor: clean`).
  - `npm run test:contract`: exit 0 (5 passed in 3.13s).
- **Migration & schema:**
  - `python -m alembic heads`: exit 0, exactly one head: `0006_ai_admission (head)`.
  - `python -m alembic history`: exit 0, linear ancestry: `<base> -> 0001_storage -> 0002_operations -> 0003_consent -> 0004_vocabulary -> 0005_review -> 0006_ai_admission`.
- **Coverage & architecture:**
  - `npm run coverage:check`: exit 0, changed lines 100.00% (min 80.00%), total lines 92.72% (baseline 86.70%, tolerance 0.50 points) against clean HEAD; 97.22% when evaluated against T016 integration base `3b4faf52ba63aac30d6ea0443746eff846eb62da`. Thresholds and ratchets intact.
  - `npm run architecture:check`: exit 0, depcruise 0 violations, import-linter 7 kept / 0 broken, 40 gate tests passed in 20.78s.
- **Security & contract determinism:**
  - `npm run security:secrets`: exit 0, 0 findings (Gitleaks 8.30.1).
  - `npm run security:code`: exit 0, 0 findings (Semgrep 1.178.0).
  - `npm run security:deps`: exit 0, 0 findings (OSV-Scanner 2.6.0).
  - `npm run export:contract`: executed twice consecutively with byte-identical output; zero git diff in `contracts/openapi.json` and `frontend/src/shared/api/generated.ts`.
- **Inherited baseline failure:**
  - `python -m ruff check .`: exit 1, exactly 1 finding in untouched `scripts/tests/test_contract.py:34` (`RUF100 [*] Unused noqa directive`). Verified as `INHERITED_BASELINE_FAILURE` from commit `121d006a`, unrelated to CP06/T015/T007/T016, and left unmodified to preserve audit integrity.
- **Bookkeeping & closure:**
  - Updated `tasks/todo.md`: marked CP06 `[x]`, updated stale `Next ready task: T014` to current ready work (`T018, T008, T021`).
  - Updated `tasks/t007-bridge-policy-consent-adapter.md`: aligned status to `DONE` and criteria to `[x]`.
  - CP06 final verdict: PASS.
- **Scope & safety:** Production files, migrations, ADRs, test fixtures, user Markdown vocabulary files, live databases, git history/remote intentionally untouched. No commits staged or pushed, no real provider inference, no real credentials accessed.

## 01/10/2026 - T016 verified linear integration after T020/T026/T031

- **Base/source/audit:** frozen clean local main `3b4faf52ba63aac30d6ea0443746eff846eb62da` includes the preceding integration wave and one `0005_review` head. Source `task/t016` is already committed at `56b8e83254e1fce1d13d888aa2e4beb2952822e1`; source confirmation has 60 passing admission tests. Exact cherry-pick with provenance is `5eafd570fd82e646a4586e90dd263ad1ce90f662` on `integration/t016-after-wave`; separate ancestry/remediation commit preserves the original source. Documentation follows the required documentation-and-adrs skill.
- **Migration/data:** rename only T016's `0005_ai_admission` to `0006_ai_admission` and move its predecessor from `0004_vocabulary` to `0005_review`. All admission columns/constraints/triggers/downgrade bytes otherwise match source. No merge migration; final head is uniquely `0006_ai_admission`. Real seeded 0005->0006 and repeat upgrades preserve all ten existing vocabulary/operation/consent/review tables, including a review card/event, with clean foreign keys. Initial seed-probe transaction misuse was corrected to T031's required writer; production remained untouched.
- **Conflicts/tests:** preserve both task histories/statuses and main's consent/vocabulary seeded-history/native-downgrade checks while retaining T016 repeat checks. INTEGRATION_TEST_REMEDIATION is limited to T031's historical migration test: reproduced stale-head failure, then explicit repeated 0005 upgrade, exact ancestry, all original data/uniqueness checks, native review downgrade refusal, and dynamic single-head initialization. Other SRS test functions are AST-identical to frozen main. T016 upgrade test targets 0005->0006; all its race/restart functions and coordinator/port bytes are preserved.
- **Verification:** admission 60, T020 24, T026 25, T031 60, consent 150, vocabulary-storage 16, operations 14 and bridge 14 pass; full pytest 533 and frontend 38 pass. Full Mypy (43 source files), seven-file scoped Ruff/format, single-head/history, typecheck/lint/build/floor, architecture (seven kept contracts/40 tests), check:fast, complete check:task and all three zero-finding security scans exit 0. Changed coverage 97.22% / total 92.69% uses the frozen latest-main SHA; minimum 80%, thresholds and tooling unchanged. Two contract exports are deterministic and unchanged. Exact command outcomes are in the T016 card.
- **Safety/handoff:** two-process revoke-first/ABA deny with zero dispatch; admission-first finishes once while revoke commits during blocked fake transport. No transaction across network, duplicate admission or UNKNOWN redispatch, real inference, fallback or retry. Preceding production/migration semantics and generated/config/security files are byte-identical to main. Full Ruff retains only the byte-identical RUF100 finding reproduced on this current base: INHERITED_BASELINE_FAILURE, not PASS. T016/preceding tasks DONE; CP06 PENDING. Promotion is local ff-only after unchanged-main and committed-scope checks, followed by required main smoke; no push.

## 01/10/2026 - T016 durable AI admission and historical migration-test remediation

- **Files:** new `backend/app/application/ai_admission.py`, `backend/tests/test_ai_admission.py`, `backend/migrations/versions/0005_ai_admission.py`; additive profile documentation in `backend/app/platform/bridge_port.py`; explicitly authorized migration-test maintenance in `backend/tests/test_consent.py` and `backend/tests/test_vocabulary_storage.py`; T016 card, todo and this changelog. Documentation follows the repository-required documentation-and-adrs skill and existing ADR-0003.
- **Design/reason:** capture exact T015 consent revision/version/digest/scope/dispatch rule before preflight, reject profile drift, then recheck durable authorization and insert immutable admission provenance in one short BEGIN IMMEDIATE writer transaction. Commit precedes the sole dispatch. The new table binds one operation to redacted authorization evidence with primary/FK/CHECK constraints and preservation triggers; no AI content or credentials are stored. The migration follows `0004_vocabulary`, preserves existing data and refuses destructive downgrade. Existing OperationLedger remains the sole intent/recovery authority; PENDING -> UNKNOWN and admission evidence prevent uncertain re-entry from dispatching again.
- **Race evidence:** real shared SQLite with two spawn processes and bounded events/pipes proves revoke-first and revoke/regrant ABA deny with zero admissions/dispatches; admission-first commits one row and permits one dispatch while another process commits revoke during blocked fake transport. Later requests deny. No process-local correctness lock, transaction across transport, automatic retry/fallback or real inference.
- **Non-weakening remediation:** both historical tests now assert one head and their own direct predecessor, explicitly upgrade/repeat at `0003_consent` or `0004_vocabulary`, retain tables/history/revision checks and preserve current-head startup repeat behavior. Pre-edit RED exits 1: consent 149 passed/one failed; vocabulary 15 passed/one failed. No newest-head replacement, skip, fixture change or production/migration edit during remediation.
- **Final verification:** consent 150, vocabulary-storage 16, admission 60, operations 14, bridge 14, full Python 424 and frontend 38 pass. Mypy, six-file scoped Ruff/format, single Alembic head `0005_ai_admission`, architecture (seven kept contracts/40 tests), check:fast, complete check:task and all three zero-finding pinned security scans exit 0. Changed coverage 97.22%, total 91.63% against `de9725ba1e79658f5bebc583ba09422692e5df9c`; minimum 80% and all thresholds/tooling unchanged. Two contract exports preserve OpenAPI/client bytes. Exact commands and exits are in the T016 card.
- **Inherited Ruff/handoff:** `python -m ruff check .` exits 1 solely for RUF100 in untouched `scripts/tests/test_contract.py:34`; exact-base reproduction and SHA-256 equality confirm INHERITED_BASELINE_FAILURE. No full-Ruff PASS claimed or unrelated fix made. T016 DONE; CP06 PENDING. Changes remain unstaged/uncommitted, with no push; next action is separate pre-commit review.

## 01/10/2026 - Local integration verification for T020, T026 and T031

- **Status/merges:** DONE on local `main`. Existing T020 merge `f2a5270` retained; completed the already-started T026 merge as `50967cf`, then merged T031 as `3b36d15`. No abort, restart, history rewrite, push, PR, task-branch deletion or worktree deletion.
- **Resolution semantics:** Preserve dynamic single-head initialization in consent and vocabulary tests, exact 0003→0002 / 0004→0003 historical ancestry, historical upgrade/ledger/history checks and consent's own downgrade refusal. T031 migration retains 0005→0004. Changelog keeps T031, T026, T020 and all prior history; task index checks all three and preserves unrelated states. Task implementation/tests match their reviewed branch versions byte-for-byte.
- **Focused checkpoints:** `python -m pytest backend/tests/test_search_index.py backend/tests/test_markdown_roundtrip.py backend/tests/test_consent.py -q`: exit 0, 199 passed in 23.76s before T031. `python -m pytest backend/tests/test_srs.py backend/tests/test_search_index.py backend/tests/test_markdown_roundtrip.py backend/tests/test_consent.py backend/tests/test_vocabulary_storage.py -q`: exit 0, 275 passed in 33.39s after T031.
- **Final verification:** `python -m pytest`: exit 0, 473 passed in 71.83s. `npm run test:frontend:coverage`: exit 0, 38 passed. `npm run coverage:check`: exit 0, changed lines 96.01% (minimum 80.00%), total lines 92.49% (baseline 86.70%, tolerance 0.50 points). `npm run architecture:check`: exit 0, no frontend violations, seven backend contracts kept, 40 tests passed in 23.82s. `npm run security:secrets`, `npm run security:code`, `npm run security:deps`: each exit 0, zero findings. `npm run check:task`: exit 0, repeating format/lint/types/floor, 38 frontend tests, 473 Python tests in 71.07s, coverage, all three security scans and architecture (40 tests in 23.33s). Coverage and aggregate gate used `QUALITY_BASE_REF=de9725ba1e79658f5bebc583ba09422692e5df9c`, the pre-wave main commit, to verify the entire integration delta.
- **Additional checks:** Full backend Mypy: exit 0, 40 source files. Focused Ruff across the three tasks and two migration tests: exit 0. Alembic heads: exit 0, exactly `0005_review`; explicit ScriptDirectory probe confirms 0001_storage→0002_operations→0003_consent→0004_vocabulary→0005_review. Conflict-marker scans return no matches; no unmerged paths; staged and working-tree whitespace checks pass.
- **Files changed/untouched:** Merge resolutions and integration evidence touch only `backend/tests/test_consent.py`, `docs/changelogs.md` and `tasks/todo.md` beyond task contributions; vocabulary's historical migration-test maintenance comes from T031. Final handoff adds only this changelog entry. Thresholds, dependencies/locks, generated contracts, frontend, earlier migrations, user vocabulary, live databases and task worktrees remain untouched. Reports are ignored local artifacts. Documentation follows the required documentation-and-adrs skill.
- **Risks/next:** No unresolved integration blocker; lint retains its two existing frontend fast-refresh warnings (zero errors). Windows/browser/100k-form release evidence remains governed by its own task cards; this integration does not claim it. Next planned dependency work is T021 (source-file adapter), with T022/T023 and T032 remaining separate tasks.

## 01/10/2026 - T031 authorized legacy-test remediation and completion

- **Local integration checkpoint:** Integrated with T020/T026 on main, retaining dynamic current-head checks and exact historical 0003→0002 / 0004→0003 upgrade, ledger, history and downgrade checks. Preserved all task history and checked only T031 beyond the prior main state. Five-suite focused pytest: exit 0, 275 passed in 33.39s; exact migration-chain probe and Alembic heads: exit 0, one `0005_review` head. Full backend Mypy: exit 0, 40 source files; focused Ruff and pre-commit secret scan: exit 0. No unmerged paths, conflict markers or staged whitespace errors.
- **Scope:** Owner-authorized changes only to the migration test in `backend/tests/test_consent.py`, the migration test/Alembic import in `backend/tests/test_vocabulary_storage.py`, T031 card, todo and this changelog. The four T031 implementation files remain unchanged during remediation; the earlier blocked checkpoint is preserved below. Documentation follows the required documentation-and-adrs skill already opened/read.
- **Semantic preservation:** Derive one current repository head rather than pinning historical global heads. Keep explicit 0003→0002 and 0004→0003 lineage, historical revision ledger checks, consent state/history/event columns and consent's own downgrade refusal, vocabulary tables/WAL/ledger/repeat safety. Add a pre-0004 seeded-history preservation probe. No meaningful assertions removed or behavioral guarantees weakened; AST audit confirms 66/16 other functions unchanged and assertion counts grow 9→13 / 6→13.
- **Verification:** Targeted consent/vocabulary/SRS pytest exits 0 (226 passed, 32.83s); full pytest exits 0 (424 passed, 80.39s). Full backend Mypy, six-file Ruff/format, floor and whitespace checks exit 0. Fresh frontend coverage has 38 passing tests; coverage gate passes changed 97.89%/total 91.82% with unchanged thresholds. Architecture passes seven contracts and 40 tests; pinned Gitleaks/Semgrep/OSV scans each report zero findings. Complete `npm run check:task` exits 0, repeating 424 Python/38 frontend tests and all coverage/security/architecture gates. One head remains `0005_review`; migration ancestry is unchanged.
- **Handoff:** T031 marked DONE with all acceptance boxes checked. Exactly six authorized implementation/test files and three bookkeeping files; no T020/T026 import, neighboring production edits, live DB access, commit/staging, push or Git history operation. Branch/HEAD remain `feature/task-t031-review-schema` / `de9725b`. Next: owner review and separately authorized commit/integration.

## 01/10/2026 - T031 review schema/SRS checkpoint (BLOCKED)

- **Files:** `backend/migrations/versions/0005_review.py`, `backend/app/review/srs.py`, `backend/app/review/models.py`, `backend/tests/test_srs.py`, T031 card, `tasks/todo.md` and this changelog. Documentation follows the required documentation-and-adrs skill, opened/read before editing.
- **Behavior/rationale:** Implement ADR-0005's exact box0–5/rating matrix and Bangkok local-calendar midnight scheduling. One canonical T019 word form owns one persistent card; VALID-source eligibility is derived on use. Frozen events, append-only/REPLACE guards, RESTRICT FKs and per-operation/card uniqueness preserve history, prevent repeated advancement and allow multi-card quiz operations. Caller-owned T005 writer transactions integrate with T014 receipts; reset changes only current schedule. No endpoints, quiz scoring, provider calls or parallel T020/T026 implementation.
- **Evidence:** Focused pytest 60 passed, Mypy (all four new Python files), focused Ruff/format, floor, whitespace and single Alembic head checks exit 0. Temporary 0004→0005/fresh/repeated migration probes preserve T019 data; concurrency, replay, source loss/re-add, reset, constraint rejection and atomic rollback pass. No live DB touched or destructive downgrade allowed.
- **Blocker:** Full pytest exits 1: 422 passed, 2 failed. Untouched `test_consent.py:739` pins 0003 (already failing against the pre-T031 0004 baseline); `test_vocabulary_storage.py:525` pins 0004 while the authorized head is now 0005. The owner requires STOP_SCOPE_BLOCKER before narrow legacy-test remediation. T031 remains BLOCKED/unchecked; frontend coverage, coverage/architecture/security gates and check:task were not executed after the stop and remain PENDING.
- **Handoff:** Baseline/end HEAD `de9725b`, branch `feature/task-t031-review-schema`, clean initial worktree. Locked `npm ci --ignore-scripts` restored missing task executables without dependency edits; all three pinned scanner binaries are available, but version probes do not establish scan success. Prior migrations, neighboring domains, frontend/contracts/authority and user files remain untouched. No staging, commit, merge, rebase, cherry-pick or push. Next: owner-authorized legacy-test remediation, then all mandatory gates.

## 01/10/2026 - T026 Vietnamese normalized n-gram projection

- **Local integration checkpoint:** Resolved the in-progress T026 merge on main by preserving T020 and T026 history, checking both tasks and leaving T031 pending. Consent retains dynamic single-head initialization plus the exact 0003→0002 ancestry assertion. Focused search/roundtrip/consent tests: exit 0, 199 passed in 23.76s. `python -m alembic heads`: exit 0, exactly `0004_vocabulary (head)`. No unmerged paths or conflict markers; staged whitespace check clean.
- **Files:** `backend/app/vocabulary/normalization.py`, `backend/app/vocabulary/search_index.py`, `backend/tests/test_search_index.py`, `backend/tests/test_consent.py` (narrow legacy head remediation authorized by owner), `tasks/t026-search-projection.md`, `tasks/todo.md`, `docs/changelogs.md`.
- **Mục đích:** Xây dựng Vietnamese normalized n-gram projection cho canonical vocabulary theo FR-VOC-01, ADR-0004, api-contract §7:
  - Chuẩn hóa Unicode NFC, Unicode casefold, và accent-folded Vietnamese projection với đ/Đ -> d mapping xác định.
  - Infix / substring matching cho cả truy vấn có dấu và không dấu, hỗ trợ truy vấn ngắn (1 ký tự).
  - Tách bạch rõ rệt giữa biểu diễn chính xác (exact) và biểu diễn gập dấu (accent-folded).
  - Giới hạn n-gram sinh ra ở mức $n \in \{1, 2, 3\}$, chặn bùng nổ tổ hợp, đảm bảo độ phức tạp $O(L)$ tuyến tính.
  - Tôn trọng ranh giới nguồn: chỉ các dạng từ có ít nhất một nguồn `VALID` mới hiển thị trong projection tìm kiếm; nguồn `INVALID`/`MISSING` không hiển thị nhưng không xóa dữ liệu canonical hay lịch sử học tập.
  - Bảo toàn định danh riêng biệt của từng từ loại (distinct POS): cùng lemma/family khác POS vẫn giữ nguyên các `word_form_id` độc lập.
  - Không suy đoán ngữ nghĩa (no semantic/synonym guessing), không embedding/AI, không phụ thuộc vào FTS5, an toàn tuyệt đối trước SQL injection và metacharacters (`%`, `_`, `'`, `"`).
  - Quản lý phiên bản projection và tính nhất quán của source revision: phát hiện và từ chối cập nhật source có revision cũ (`StaleSourceRevisionError`), kiểm tra phiên bản projection (`ProjectionVersionMismatchError`), không trả về kết quả rỗng giả mạo khi sai version.
  - Rebuild an toàn, có thể lặp lại (idempotent), không đụng chạm tới các bảng canonical hay bảng lịch sử.
- **Evidence:**
  - Focused tests: `python -m pytest backend/tests/test_search_index.py -q`: 25 passed in 1.22s (100% coverage on `normalization.py`, 95% on `search_index.py`).
  - Full tests: `python -m pytest`: 389 passed in 75.53s.
  - `npm run test:frontend:coverage`: 4 files, 38 passed.
  - `npm run coverage:check`: changed 97.66% (min 80.00%), total 91.85% (baseline 86.70%).
  - `npm run architecture:check`: 7 kept, 0 broken, 40 passed.
  - `npm run security:secrets`: 0 findings (Gitleaks 8.30.1).
  - `npm run security:code`: 0 findings (Semgrep 1.178.0).
  - `npm run security:deps`: 0 findings (OSV-Scanner 2.6.0).
  - `npm run check:task`: exit code 0.
  - Ruff check & format: zero diagnostics, all formatted.
  - Mypy: zero issues in 4 source files.
  - Floor check: clean, zero violations.
- **Untouched:** `backend/migrations/*`, `backend/app/vocabulary/models.py`, `backend/app/vocabulary/repository.py`, `backend/app/markdown_sync/*`, `backend/app/review/*`, `backend/app/http/*`, `frontend/*`, `contracts/*`, `docs/vocabularies/*`.

## 01/10/2026 - T020 Lossless Markdown parser and serializer

- **Files:** `backend/app/markdown_sync/parser.py`, `backend/app/markdown_sync/serializer.py`, `backend/tests/fixtures/legacy.md`, `backend/tests/test_markdown_roundtrip.py`, `backend/tests/test_consent.py`, `tasks/t020-markdown-parser.md`, `tasks/todo.md`, `docs/changelogs.md`.
- **Purpose/change:** Implement pure deterministic Markdown parser and serializer boundary for daily vocabulary notes (`DD-MM-YYYY.md`) per ADR-0004, ADR-0005, and spec DATA-01–06; perform owner-authorized narrow remediation on `backend/tests/test_consent.py` to replace hard-coded `0003_consent` migration head with dynamic derivation from Alembic `ScriptDirectory` metadata while strictly preserving T015 migration guarantees and history assertions.
- **Invariants & behavior:**
  1. Lossless round-trip: `serialize(parse(original)) == original` preserved byte-for-byte on synthetic and read-only real legacy fixtures (`28-09-2026.md`), including exact spacing, blank lines, table pipes, markdown links, and prose formatting.
  2. Multi-POS splitting: Comma-separated `Từ loại` tokens in primary entries and related forms produce distinct POS-specific semantic forms with independent identities under the same family root.
  3. Related forms: Family members created only with explicit lemma and deterministically interpretable POS; rows with ambiguous or missing POS remain opaque context and never create cards.
  4. Opaque content preservation: Unknown sections (e.g. `### Ghi chú bổ sung`, `## Ghi chú tài liệu`) and opaque contextual rows survive parse/serialize roundtrip untouched without generating semantic cards or forms.
  5. Deterministic validation & diagnostics: Fail-closed structured diagnostics for malformed filename, invalid calendar dates (e.g. `31-02-2026`), filename/H1 date mismatch, missing/malformed H1, truncated or malformed tables, and ambiguous POS.
  6. Source size boundary: Enforced 8 MiB (8,388,608 bytes) limit with `PAYLOAD_TOO_LARGE` diagnostic; no silent truncation.
  7. Unicode fidelity: NFD/combining-mark inputs preserve raw byte representation in serialization, while semantic normalized lemmas consistently resolve to NFC.
  8. Inert data: Untrusted instruction-like text, HTML/scripts, unusual links, and SQL strings remain completely inert text data.
  9. Absolute purity: Zero filesystem writes, zero disk reads in parser/serializer functions, zero SQLite database access, zero network/AI calls, zero global mutable state.
  10. Stale migration head remediation: `test_fresh_0002_to_0003_migration_repeat_and_history` dynamically checks `len(heads) == 1`, verifies `0003_consent` down-revision is `0002_operations`, and asserts `db.initialize().schema_revision == current_head` twice to verify repeat stability while keeping all T015 schema, table existence, event column, and history preservation assertions intact.
- **Evidence:**
  - Focused roundtrip pytest: `python -m pytest backend/tests/test_markdown_roundtrip.py -q` Exit 0, 24 passed in 0.51s (parser 91%, serializer 89%, total 91% coverage).
  - Remediated consent + roundtrip suite: `python -m pytest backend/tests/test_consent.py backend/tests/test_markdown_roundtrip.py -q` Exit 0, 174 passed in 31.57s.
  - Full pytest test suite: `python -m pytest` Exit 0, 388 passed in 75.85s (total coverage 90%).
  - Full task gate (`npm run check:task`): Exit 0, coverage changed lines 94.24% (minimum 80.00%), total lines 91.75% (baseline 86.70%), architecture gate 7 kept / 0 broken (40 passed), security scans all 0 findings.
  - Fast active check (`npm run check:fast:active`): Exit 0 (ESLint 0 errors, TS 0 errors, floor clean, ruff format 144 files formatted).
  - Focused Ruff check & format: Exit 0, 0 diagnostics across all modified files.
  - Full backend Mypy (`python -m mypy backend`): Exit 0, 33 source files checked, 0 errors.
  - Quality floor guard (`python scripts/check_constraints.py floor`): Exit 0, `floor: clean`.
  - Security scans (`npm run security:secrets`, `security:code`, `security:deps`): Exit 0, zero findings across all three scanners (Gitleaks 8.30.1, Semgrep 1.178.0, OSV-Scanner 2.6.0).
- **Files untouched:** `docs/vocabularies/28-09-2026.md` (read-only real sample preserved), frontend code, database models/migrations, HTTP routes, application services, and parallel worktrees (T026, T031).

## 01/10/2026 - T053 generated-source coverage classification remediation

- **Files:** `scripts/check_constraints.py`, `scripts/tests/test_constraints.py`, `tasks/t053-quality-security-gates.md` and this changelog; documentation follows the required documentation-and-adrs skill.
- **Reason/fix:** The changed-coverage checker incorrectly treated T017's generated DTO as handwritten source. Added `is_generated_source()` with the sole exact path `frontend/src/shared/api/generated.ts`, applied only to changed-line classification. Similarly named handwritten paths and unmeasured backend source still fail. Reports, total ratchet, diff-cover setup and quality/security protections remain enforced; no broad exemption.
- **TDD/evidence:** Corrected RED: 12 failed / 41 passed before implementation; GREEN: 53 passed. Full pytest 208 passed; frontend coverage tests 38 passed. Focused Ruff/format/Mypy, typecheck, lint, build, floor, coverage and fast gate pass. Changed coverage 100.00%, total 88.97%. Full Ruff exits 1 with 19 findings proven identical to the base in untouched files; no full-Ruff PASS claimed. Exact command outcomes and initial test/harness corrections are recorded in the task card.
- **T015 read-only replay:** Temporary clone of candidate `2386f3d12730cda8e886acb593b0fadcd473778d` with its actual reports: original checker exits 1 for unmeasured generated DTO; fixed checker exits 0 with changed 94.79% / total 89.89%. All T015 tracked files/reports remain byte-identical, candidate HEAD/status unchanged.
- **Thresholds/scope:** Minimum 80.0%, baseline 86.70%, tolerance 0.5 points unchanged. CONSTRAINTS, dependencies/locks, generated artifacts, frontend tests, T015, T062, security tooling and todo untouched. Pinned checksum-verified Gitleaks 8.30.1 reports zero findings; scanner binaries remain outside Git. Local remediation commit only; no push/main promotion/T015 edits. Next: cherry-pick into the T015 integration branch and rerun complete-candidate `check:task`.

## 01/10/2026 - T015 application-boundary architecture compatibility

- **Files:** `backend/app/application/consent.py`, `backend/app/http/consent.py`, `backend/tests/test_consent.py`; this changelog, T015 card and task-index evidence. Existing integration commits `cb81d69` / `20e4e3c` are preserved.
- **Reason/change:** T062 rejected HTTP's direct persistence import. The existing composed ConsentService now owns read/grant/revoke connections and translates storage failures into existing typed application outcomes. HTTP only renders those outcomes; SQLAlchemy, StorageError and engine access leave the route. Original policy/CAS/ledger/replay methods, main composition, migration and public schema remain unchanged.
- **Evidence:** new boundary tests RED exit 1 (10 failed / 3 already passed), then consent 150 and operations 14 pass. An initial test-union annotation error was corrected; Mypy and focused Ruff/format exit 0. Architecture exits 0 with seven kept contracts, zero forbidden direct graph paths and 40 tests; full Python exits 0 with 332 tests. Two canonical exports preserve both generated files byte for byte. Typecheck, lint (two inherited warnings), build, floor, check:fast and all three pinned security scans exit 0; scanners report zero findings.
- **Promotion blockers:** full Ruff exits 1 only for unchanged T014/T017 findings (test_operations.py E501 and test_contract.py RUF100). Complete-candidate check:task against authorized main `bc0ff937` exits 1 after all 332 tests pass because unchanged T053 tooling demands executable coverage for generated.ts. Remediation-only coverage against `20e4e3c` exits 0: changed 100.00%, total 89.89%, unchanged thresholds. This separate measurement does not clear the aggregate failure.
- **Handoff:** architecture compatibility is fixed; main promotion remains blocked by the required check:task gate. Main, T007, T062 rules, T014/T017 tooling, migration and source worktree remain untouched. T016 and CP06 remain pending; no dispatch admission/provider/network behavior change or push. Documentation follows the repository-required documentation-and-adrs skill.

## 01/10/2026 - T015 prerequisite-aware integration candidate

- **Files/scope:** transplant only the consent application, HTTP adapter and consent tests from `865740e`; apply the ten-file semantic delta from `7f4b320` on authorized local main `bc0ff937`. Historical qualityfix ancestry and T014/T017 tooling edits are excluded; T007 bridge formatting remains unchanged.
- **Evidence:** prerequisite files match their source byte for byte; Mypy, focused Ruff/format, 10 prerequisite tests, whitespace and zero-finding secret scan pass. Reviewed semantic source files match `7f4b320`; canonical contract generation is byte-identical across two runs.
- **Integration:** resolve changelog/task-index conflicts by retaining CP05 history and T052/T062/T007 completion plus T015 semantic completion. Candidate verification and main promotion remain gated; T016 and CP06 are pending. Earlier entries below describe their historical source snapshots, including former tooling blockers.

## 30/09/2026 - T015 resumed semantic remediation and verification

- **Files:** additional changes only in `backend/app/application/consent.py`, `backend/app/http/consent.py`, `backend/migrations/versions/0003_consent.py`, `backend/tests/test_consent.py`; canonically regenerated OpenAPI/DTO; T015 card and todo. Inherited implementation/quality fixes and the previous session's history are preserved; inherited `main.py` is untouched.
- **Change/purpose:** normalize complete structured policy definitions before hashing; reject duplicate registry keys and corrupt singleton/event/receipt evidence; require exactly-one-row CAS over revision/state/identity/time. Preserve committed historical receipts after ambiguous completion while denying AI capability. Store calendar-valid RFC3339 UTC event/choice times, enforce migration shape/registry checks, and correct startup storage error taxonomy plus GET's generated 422/503 schema.
- **Verification:** missing/corrupt evidence, canonical ordering, ambiguous completion, duplicate JSON/BLOB identities and startup storage taxonomy received RED-to-GREEN regressions. Added 47 cases to the inherited 90: consent 137, operations 14, full Python 279, frontend 38 and contract five all exit 0. Mypy, focused format, Ruff, TypeScript, build, floor and three security scans exit 0. Independent physical SQLite connections overlap deterministic writer transactions; stale grants lose. All consent paths have zero bridge/provider/socket/transport attempts. Two exports are byte-identical. Changed executable coverage 94.30%; measured combined 89.81%, unchanged thresholds.
- **Inherited failures:** check:fast/check:task exit 1 on the same untouched T007 format failures; coverage:check exit 1 because unchanged T053 tooling requires coverage for generated.ts. No aggregate PASS or tool/threshold modification. T062 architecture command is absent. Isolated fresh/0002-to-0003 migration verification has one head; no real database rebuild and no 0004 consent migration.
- **Handoff:** T015 acceptance DONE; workspace IMPLEMENTATION_DONE_BASELINE_BLOCKED. Detailed ownership, invariant matrix and exact source-frozen outcomes are in the T015 card. T016 and CP06 remain pending; no dispatch admission or bridge/provider calls were introduced. Not staged or committed; authorization not provided.

## 30/09/2026 - T015 final semantic remediation

- **Files:** the five T015 handwritten files (`backend/app/application/consent.py`, `backend/app/http/consent.py`, `backend/app/main.py`, `backend/migrations/versions/0003_consent.py`, `backend/tests/test_consent.py`); generated OpenAPI/DTO; T015 card and todo. Quality-fix base preserved; no other worktree or owner source edited.
- **Change/purpose:** enforce complete typed v1 READY policy, server canonical digest, durable immutable first-seen policy identities/conflicts, policy-sensitive opaque ETag and RFC3339 choice time. Grant/revoke calculate revisions inside T014's completion writer transaction; state/event/successful receipt commit atomically. Replay remains historical after withdrawal, key reuse preserves 422, revoke stays offline, validation rejects malformed requests without permission/history side effects. Missing/corrupt evidence and actual storage failures fail closed; event snapshots/history resist UPDATE/DELETE/REPLACE.
- **Verification:** RED tests reproduced semantic defects and reviewer findings before fixes. Final consent 90 PASS, operations 14 PASS, full Python 232 PASS, frontend 38 PASS, contract 5 PASS, two exports byte-identical; Mypy, Ruff lint/focused format, TypeScript, build, floor, whitespace and pinned secret/code/dependency scans PASS. Changed executable coverage 93.99%; combined measured coverage 89.56% exceeds the unchanged baseline. Exact commands/outcomes and SQLite two-engine/trigger evidence are recorded in the T015 card.
- **Remaining blockers:** repository formatter still fails only on byte-for-byte inherited T007 bridge files (`BASELINE_T007_FORMAT_BLOCKER`). Existing T053 coverage checker wrongly requests executable coverage for generated.ts; its FAIL is preserved, source/thresholds untouched. T015 semantic acceptance is DONE; whole workspace is IMPLEMENTATION_DONE_BASELINE_BLOCKED / NOT_READY_TO_COMMIT. Unreleased/current 0003 was completed in place with one head; no claim of upgrade compatibility for an old deployed 0003 database.
- **Handoff:** T016 is dependency-ready assuming T007 DONE; it remains TODO and no dispatch/provider work was added. No real credential/provider call, merge/rebase/pull, commit or push. Documentation follows the repository-required documentation-and-adrs skill.
## 01/10/2026 - T019 Schema vocabulary, source links và preview

- **Files:** `backend/migrations/versions/0004_vocabulary.py`, `backend/app/vocabulary/models.py`, `backend/app/vocabulary/repository.py`, `backend/tests/test_vocabulary_storage.py`, `tasks/t019-vocabulary-schema.md`, `tasks/todo.md`, `docs/changelogs.md`.
- **Mục đích:** Xây dựng schema bền vững và repository cho canonical vocabulary identity, liên kết nguồn Markdown nhiều ngày và quản lý lookup preview theo ADR-0004/DATA-01–06 và T013 contract.
- **Invariants:**
  1. Canonical identity: `(normalized_lemma, part_of_speech, family_id)` là duy nhất; nhiều ngày/nguồn dùng chung một canonical form.
  2. Distinct POS: Cùng lemma và family nhưng khác từ loại tạo ra các bản ghi canonical form riêng biệt.
  3. Ambiguous family: Reject fail-closed, không tự ý suy đoán hoặc gộp word family.
  4. Per-field verification: Giá trị thiếu (IPA, Cambridge URL) được lưu đúng `NULL`, không bịa đặt dữ liệu; giữ nguyên `verification_status` và `verificationSummary`.
  5. Source state isolation: Nguồn lỗi (`INVALID`/`MISSING`) hoặc bị xóa chỉ gỡ link, không cascade-delete canonical form hay lịch sử học tập.
  6. Preview ownership & expiration: Bắt buộc khớp session owner và kiểm tra expiration theo T013; dữ liệu lưu bền vững không chứa credentials/auth tokens.
- **Evidence:**
  - `python -m pytest backend/tests/test_vocabulary_storage.py -q`: 16 passed (coverage: models 94%, repository 95%, migration 95%, total 85%).
  - `python -m alembic heads`: `0004_vocabulary (head)`.
  - `lint-imports --config pyproject.toml --no-cache`: 7 kept, 0 broken.
  - `python scripts/check_constraints.py floor`: `floor: clean`.
  - Ruff check & format: zero errors, 4 files clean.
  - Mypy: zero issues in 4 source files.
  - Pending external tools: Gitleaks/Semgrep/Lighthouse ghi nhận `SETUP_PENDING`/`SETUP_FAILED` do môi trường chưa cài đặt nhị phân.
- **Untouched:** Toàn bộ frontend, bridge adapter, consent API, operation ledger, parser, search projection và SRS logic bên ngoài T019 được bảo toàn nguyên vẹn.

## 30/09/2026 - T052 Browser Harness

- **Files:** `frontend/tests/e2e/harness.spec.ts`, `frontend/tests/support/test_server.py`, `frontend/tests/support/fake_bridge.py`, `playwright.config.ts`, `package.json`, `package-lock.json`, `tasks/t052-browser-test-harness.md`.
- **Mục đích:** Cung cấp môi trường kiểm thử E2E và Accessibility UI an toàn, cô lập hoàn toàn khỏi hệ thống dữ liệu thực và Google inference, sẵn sàng cho các nhiệm vụ phát triển React components phía trên.
## 30/09/2026 - T062 resumed architecture-gate verification

- **Files:** Preserved interrupted `.dependency-cruiser.cjs`, `pyproject.toml`, `package.json`, generated npm/dev Python locks and `scripts/tests/test_architecture_gate.py` without implementation edits; updated T062 card, todo and this changelog using the repository-required documentation-and-adrs skill.
- **Reconstruction:** Branch `task/t062`, HEAD/base `b49a722`. Historical `test_real_frontend` failure did not recur. Initial exact pytest command used the original workspace virtualenv and failed 20 Python probes because import-linter/Grimp were absent; this worktree's existing virtualenv resolves the setup error.
- **Evidence:** Final focused pytest 40 passed; architecture gate exit 0: dependency-cruiser 13 modules / 14 dependencies / zero violations, import-linter 7 kept / 0 broken. Typecheck, focused Ruff/Mypy/format, config ESLint, floor and diff checks exit 0. Synthetic forbidden imports, cycles, exact generated DTO/sibling, valid type-only port and namespace-package probes all behave as required. After missing-tool/sandbox setup failures, the checksum-verified OSV-Scanner 2.6.0 network-enabled dependency scan exits 0 with zero findings; pip dependency consistency also passes. Scanner binary stays in `/tmp`.
- **Baseline blocker:** `npm run check:task` exits 1 at formatting in the two T007 bridge files. Both are byte-identical to `b49a722`; base-file formatting checks also exit 1. Application source, thresholds, contracts and unrelated tasks remain untouched. Whole branch not ready to commit; no commit, push or Git integration performed. Exact handoff and T052 package reconciliation are recorded in the task card.

## 30/09/2026 - T053 assertion-replacement floor remediation

- **Files:** `scripts/check_constraints.py`, `scripts/tests/test_constraints.py`, `tasks/t053-quality-security-gates.md` and this changelog; existing uncommitted changes preserved.
- **Reason/change:** T015's legitimate migration-head assertion replacements must not count as assertion deletions. Compare assertions per modified test file; tokenize Python with complete before/after context to exclude comment/string matches. Keep real deletion/net loss, test deletion, skip/suppression, unfinished work, threshold, coverage, no-HEAD and redaction protections. No path/migration exemption or threshold change.
- **Evidence:** Added regression cases first: RED exit 1, 4 failed / 30 passed; GREEN exit 0, 37 passed. Focused Ruff and Mypy exit 0. Isolated replay of the three actual T015 test diffs: original checker exit 1, eight `assertion-removed` findings; repaired checker exit 0, `floor: clean`.
- **Shared gate failures:** `npm run floor:check` exits 1 for existing suppression in `scripts/tests/test_contract.py:34`. `npm run check:fast` exits 1 at formatting in `backend/app/adapters/bridge.py` and `backend/tests/test_bridge.py`; later stages do not run. These files remain untouched. Remediation done; shared workspace not ready to commit. No commit authorized or created.

## 30/09/2026 - T007 final deadline remediation

- **Files:** `backend/app/adapters/bridge.py`, `backend/app/platform/bridge_port.py`, `backend/tests/test_bridge.py`, `tasks/t007-bridge-policy-consent-adapter.md` and this changelog.
- **Deadline:** Removed the redundant client-level timeout calculation. Every no-key models, keyed models and chat request independently receives `deadline - monotonic()` immediately before sending; nonpositive budget raises `BridgeUnavailableError` without another request. The same absolute deadline covers preflight and dispatch. This supersedes the earlier incomplete deadline evidence; operation deadline enforcement is no longer downstream evidence.
- **Tests:** Capture all HTTPX timeout phases: preflight 5.0 → 1.0 after four seconds; exact expiry sends only the no-key request; initially expired preflight sends none; dispatch after four seconds receives 1.0; independent operation deadline 15.1 receives 8.0 / 6.0 / 4.0 on the same adapter.
- **Verification:** Focused pytest 14 passed, Mypy adapters/platform and focused Ruff exit 0; `git diff --check` exit 0. Full pytest 152 passed outside sandbox (exit 0, coverage-file warnings); sandbox attempt stalled and was interrupted (exit 130). Full Mypy exit 1 with 33 errors in three parallel consent files; full Ruff exit 1 with 19 errors in parallel consent files, `test_operations.py` and `scripts/tests/test_contract.py`. Exact locations are recorded in the task card. Remediation DONE; whole working tree NOT_READY_TO_COMMIT until those unrelated checks pass.
- **Scope:** Fixture JSON, shared todo, parallel T015/T017/other source and tooling untouched. Independent concurrent changes to `scripts/check_constraints.py`, `scripts/tests/test_constraints.py` and `tasks/t053-quality-security-gates.md` were observed by hash comparison. No staging, commit, push, real key or inference.
- **Downstream:** Installed Windows/Antigravity profile, LAN isolation, T040 key provisioning, T016 consent/policy admission only. Documentation follows the repository-required documentation-and-adrs skill; no architecture or public API change.

## 30/09/2026 - T007 pre-commit cleanup and evidence audit

- **Files:** `backend/app/adapters/bridge.py`, `backend/tests/test_bridge.py`, `tasks/t007-bridge-policy-consent-adapter.md` and this changelog.
- **Correction:** Initial focused Ruff returned exit 1 with 12 diagnostics; this was FAIL. Removed unused imports, sorted imports, combined equivalent async contexts and renamed unused callback arguments without rule suppression. Replaced the existing test type suppression with `AsyncIterator[bytes]`.
- **Evidence:** Strengthened existing tests to capture the actual dispatch HTTPX timeout and unsafe-profile request path/Authorization absence. Focused pytest: 9 passed, exit 0; Mypy adapters/platform: exit 0; exact focused Ruff: exit 0; `git diff --check`: exit 0. Linux Python 3.12.3; synthetic mock transport only.
- **Deadline:** Operation 1 deadline 5.0, preflight starts 0.0, two requests consume 4.0, dispatch starts 4.0 and receives 1.0 seconds. After expiry at 5.1, no request is sent. Operation 2 deadline 15.1, dispatch at 7.1 receives 8.0 seconds. HTTPX phase timeouts do not alone prove the caller's end-to-end cancellation/hard-deadline admission gate; downstream T016 owns that integration.
- **Boundaries:** 4,194,303 and 4,194,304 bytes pass the size gate and fail synthetic JSON parsing; 4,194,305 bytes fail specifically on size. Unsafe no-key models 200 sends exactly one request, no Authorization and no chat. Approved sequence is no-key models 401, keyed models 200, then caller dispatch.
- **Untouched:** `bridge_port.py`, fixture JSON, shared `tasks/todo.md`, all pre-existing parallel consent/migration/tests and contract/client changes. No staging, commit, push or real inference.
- **Downstream PENDING:** Installed Windows/Antigravity profile, LAN isolation, protected real-key provisioning/rotation (T040), final consent/policy and operation admission (T016). A fully mimicking local listener remains the accepted ADR-0002 impersonation risk.

## 30/09/2026 - T066 Trusted browser bootstrap page

- **Khu vực:** `frontend/bootstrap.html`, `frontend/src/bootstrap.ts`, `vite.config.ts`
- **Thay đổi:** 
  1. Thêm Vite multi-page build cho phép sinh ra HTML và JS cô lập hoàn toàn cho `bootstrap.html`.
  2. Implement `bootstrap.ts` đọc `#token=...`, xóa URL fragment ngay lập tức qua `history.replaceState`.
  3. Gửi `POST /bootstrap/exchange`, bắt thành công HTTP 204 rồi chuyển hướng `location.replace("/")`.
  4. Unit test sử dụng mock dependencies (`BootstrapDependencies`) để đảm bảo không rò rỉ token, chứng minh trình tự gửi (clearing happens before fetching) và handle các mã lỗi 401, 403, 500, network error an toàn mà không in log token.
- **Mục đích:** Khởi tạo session an toàn trước khi vào app chính. Tránh token bị leak vào React application state, log hay analytics.
- **Pending Downstream:** T052, T057. (Chưa có real browser E2E, thuộc phạm vi T052).

## 30/09/2026 - T066 Trusted browser bootstrap page

- **Khu vực:** `frontend/bootstrap.html`, `frontend/src/bootstrap.ts`, `vite.config.ts`
- **Thay đổi:** 
  1. Thêm Vite multi-page build cho phép sinh ra HTML và JS cô lập hoàn toàn cho `bootstrap.html`.
  2. Implement `bootstrap.ts` đọc `#token=...`, xóa URL fragment ngay lập tức qua `history.replaceState`.
  3. Gửi `POST /bootstrap/exchange`, bắt thành công HTTP 204 rồi chuyển hướng `location.replace("/")`.
  4. Unit test sử dụng mock dependencies (`BootstrapDependencies`) để đảm bảo không rò rỉ token, chứng minh trình tự gửi (clearing happens before fetching) và handle các mã lỗi 401, 403, 500, network error an toàn mà không in log token.
- **Mục đích:** Khởi tạo session an toàn trước khi vào app chính. Tránh token bị leak vào React application state, log hay analytics.
- **Pending Downstream:** T052, T057. (Chưa có real browser E2E, thuộc phạm vi T052).

## 30/09/2026 - T017 Remediation

- **Khu vực:** `frontend/src/shared/api`, `scripts/export_contract.py`, `scripts/tests/test_contract.py`
- **Thay đổi:** 
  1. Loại bỏ các schema ErrorDetails ảo (chưa được backend hỗ trợ) ra khỏi generator, chỉ export `FIELD_ERRORS`.
  2. Bổ sung context (URL, method, Idempotency-Key, operationId) cho MutationUnknownError để phục vụ reconciliation.
  3. Cập nhật `test_contract.py` so sánh full-schema byte-for-byte với file checked-in.
  4. Sửa false positive ETag validation `null` guard.
- **Mục đích:** Sửa các bẫy lỗi và ranh giới hợp đồng API, đảm bảo generation không chèn dữ liệu unsupported và test chống trượt cấu trúc.

## 30/09/2026

- **Khu vực:** `frontend/src/shared/api`, `scripts/export_contract.py`, `contracts/openapi.json`
- **Thay đổi:** Hoàn thành T017. Thêm client API có hỗ trợ AbortController, tự động parse typed error. Thêm script generate openapi JSON deterministic.
- **Mục đích:** Xây dựng cầu nối type-safe, tự động lấy DTO từ backend OpenAPI.

## 30/09/2026

- **Khu vực:** `backend/app/application/operations.py`, `backend/app/http/operations.py`, `backend/app/main.py`, `backend/tests/test_operations.py`, `backend/migrations/versions/0002_operations.py`, `tasks/t014-operations-idempotency.md`, `tasks/todo.md`
- **Thay đổi:** Hoàn thành T014: triển khai durable operation ledger. Bổ sung `OperationLedger` với cơ chế idempotency dùng `BEGIN IMMEDIATE`, kiểm tra digest chống trùng lặp; cập nhật endpoint `GET /operations/{id}` redacted, và exception handler cho `SQLAlchemyError`. Pass toàn bộ test kiểm chứng concurrency, lost response, và fault injection.
- **Mục đích:** Đảm bảo tính idempotency và atomic cho các tác vụ AI và save, ngăn chặn duplicate dispatch, tuân thủ đúng API contract về error responses và data redaction.

# Changelog

## Quy định cập nhật

1. Mọi thay đổi do agent thực hiện trong workspace đều phải được ghi vào file này.
2. Ngày sử dụng định dạng **dd/mm/yyyy** và múi giờ `Asia/Bangkok`.
3. Mỗi mục phải nêu ngắn gọn:
   - Ngày thay đổi.
   - Khu vực/file bị thay đổi.
   - Nội dung thay đổi.
   - Lý do hoặc mục đích nếu cần.
4. Ghi mục mới ở đầu danh sách thay đổi, bên dưới phần quy định.
5. Không xóa hoặc sửa lịch sử cũ, trừ khi cần sửa lỗi ghi chép rõ ràng.
6. Agent phải cập nhật changelog trước khi kết thúc một tác vụ có thay đổi file.

## 30/09/2026

- **Khu vực:** `backend/app/http/session.py`, `errors.py`, `bootstrap.py`, `backend/app/main.py`, `backend/tests/test_session.py`, `tasks/t006-api-core-contract-foundation.md`, `tasks/todo.md`.
- **Thay đổi:** Hoàn thành T006 với token bootstrap một lần, session cookie trong bộ nhớ theo vòng đời backend, Host/Origin/Referer/JSON/1 MiB guards, typed redacted errors và same-origin static shell refresh. Health vẫn public; OpenAPI/API/shell cần session. Test RED→GREEN cho replay, expiry, restart, hai tab, hostile headers, max/max+1 và không phản chiếu token.
- **Verification:** 11 focused session tests, 89 full Python tests, 21 frontend tests, Mypy/Ruff/format/typecheck/build PASS; changed coverage 93,27%, total 88,50%; Gitleaks/Semgrep/OSV 0 findings. ESLint 0 errors, 2 warning Fast Refresh cũ. `npm run check:task:active` PASS; T062 architecture aggregate vẫn chưa có command.
- **Mục đích:** Khóa HTTP trust boundary của app local theo API contract và ADR-0005 trước T014/T017/T066. Documentation-and-adrs ghi rationale/handoff trong thẻ task; không tạo ADR mới vì strategy đã được chốt. Browser page/referrer thực và launcher tiếp tục ở task owner.

- **Khu vực:** `tasks/todo.md`, `docs/changelogs.md` và bộ tài liệu T013.
- **Thay đổi:** Tích hợp commit atomic T013 `d7196f3` vào nhánh T063, giữ nguyên evidence của cả T063 và T013, hợp nhất hai xung đột bookkeeping, chuẩn hóa code fence Python trong conformance report theo Ruff và đánh dấu CP03 hoàn tất.
- **Verification:** 11 document probes và 2 negative mutation probes PASS; staged scope/link/authority probe PASS; aggregate gate PASS với format/lint/typecheck, 21 frontend tests, 78 Python tests, changed coverage 100%, combined total 87,42% và ba security scanners đều 0 findings. ESLint còn 2 warning Fast Refresh đã tồn tại, 0 error.
- **Mục đích:** Đồng bộ task checklist và contract-conformance artifacts vào checkout đang được sử dụng mà không thay đổi semantics của API contract.

- **Khu vực:** T013 — `docs/api-contract.md`, `docs/reviews/contract-conformance-002.md`, thẻ T013.
- **Thay đổi:** Sau khi T063 cung cấp Gitleaks 8.30.1, thêm RED→GREEN security recheck cho snapshot contract: thay ba synthetic `Idempotency-Key` values bằng symbolic placeholder, bỏ raw API baseline digest khỏi prose và viết lại một bridge sentence bị rule generic-key bắt nhầm. Không đổi endpoint, schema, precondition hoặc semantics. Directory, staged diff và current-HEAD history (8 commits) đều 0 findings; không dùng allowlist/suppression.
- **Mục đích:** Giữ commit T013 atomic và tương thích security gate hiện hành mà không thay đổi quyết định contract hay quality bar.

- **Khu vực:** `scripts/security_checks.py`, `scripts/tests/test_security_checks.py`, `package.json`, generated `requirements-dev.lock`, `docs/toolchain.md`, `tasks/t063-security-scan-tooling.md`, `tasks/todo.md`; hai wording fixture/prose trong untracked planning `docs/api-contract.md` được sửa nhưng không stage do T013 sở hữu.
- **Thay đổi:** Hoàn thành T063 với wrapper exact-version cho Gitleaks 8.30.1, Semgrep CE 1.178.0 và OSV-Scanner 2.6.0; report chỉ chứa metadata đã redacted, high/critical/unknown fail closed, scanner/network/report lỗi trả setup failure, no-HEAD/untracked + staged + current-HEAD history được quét. Bổ sung 20 focused tests (78 full Python), changed coverage 88,98%, combined total 87,42% và real negative probes; nối npm security scripts/aggregate gates. Remediation được owner phê duyệt không dùng suppression: rewrite hai false-positive examples và regenerate dev lock bằng `--allow-unsafe`, chỉ thêm pin `pip==26.2.1`/`setuptools==84.0.0`. Ba security gates đều 0 findings.
- **Mục đích:** Biến ba security dimensions trong `CONSTRAINTS.md` thành executable gates mà không che finding bằng suppression/allowlist hoặc tự force-upgrade. Skill documentation-and-adrs được dùng để ghi pin/source/license/install boundary, privacy/exit contract, remediation trade-off và cross-branch T013 risk; không tạo ADR vì đây là tooling dễ đảo ngược, không đổi architecture/API.

## 29/09/2026

- **Khu vực:** `scripts/check_constraints.py`, `scripts/tests/test_constraints.py`, `package.json`, `pyproject.toml`, generated lockfiles, `docs/toolchain.md`, `tasks/t053-quality-security-gates.md`, `tasks/todo.md`.
- **Thay đổi:** Hoàn thành T053 bằng CLI diff-scoped cho changed coverage tối thiểu 80%, combined coverage baseline 86,70% với ratchet 0,5 điểm và quality-floor guard. Bổ sung 17 test cases âm/dương cho report thiếu, 79,9/80, ratchet, unmeasured source, suppression/skip/xóa test hoặc assertion/hạ threshold, redaction, coverage/floor trên untracked no-HEAD và trạng thái pending; nối Vitest V8 LCOV, pytest Cobertura, format/floor/coverage scripts và các aggregate command không false-green khi T062/T063 chưa sẵn sàng.
- **Mục đích:** Biến quality bar trong `CONSTRAINTS.md` thành gate có exit code và artifact thực, giữ scanner/architecture ownership tách biệt. Skill documentation-and-adrs được dùng để ghi nguồn chính thức, dependency/license, baseline, trade-off và trạng thái `SETUP_PENDING`; không cần ADR vì thay đổi chỉ là tooling dễ đảo ngược, không đổi architecture/API.

- **Khu vực:** T013 — `docs/spec.md`, `docs/api-contract.md`, `docs/ui-architecture.md`, `docs/adr/0005-contract-clarifications.md`, `docs/reviews/contract-conformance-002.md`, thẻ T013 và `tasks/todo.md`.
- **Thay đổi:** Chốt 11 nhóm conformance bằng ADR-0005: quiz 5–30 với ví dụ2/2/1 và reject1/1/1; HARD giữ box và due calendar midnight Bangkok; writing-rubric-v1/blank/null; conditional new-date save/backend source ID/revision/ETag; hash/watcher vs stale API409; keys/explanations chỉ trong terminal result, GET attempt/replay/SRS atomic; caps1/8/4MiB, session60s/8h, deadline120/60/30s và database-lifetime idempotency retention. Đồng bộ AC/DTO/UI và các positive fixtures.
- **Verification:** 11 document probes RED→GREEN; hai negative mutation probes reject đúng reason; manual crosswalk/walkthrough trong report. Staged whitespace/scope/link/provenance checks PASS sau khi chuẩn hóa metadata hard-break spaces trong scoped files; supplemental redacted credential-pattern scan zero candidates. Không có application code hoặc inference; generated/runtime/Windows/browser/provider/security tooling vẫn do task owner xác minh. Gitleaks chưa có (exit127), giữ PENDING.
- **Mục đích:** Cung cấp oracle xác định trước khi business contracts được freeze. Skill documentation-and-adrs giữ authority, alternatives/consequences và evidence ownership rõ ràng. Worktree riêng bảo toàn concurrent T053; chỉ stage allowlist/bookkeeping T013, gồm full snapshots của planning inputs trước đó untracked.

- **Khu vực:** `frontend/index.html`, `frontend/src/main.tsx`, `frontend/src/app/AppShell.tsx`, `frontend/src/app/shell.css`, `frontend/src/app/AppShell.test.tsx`, `vite.config.ts`, `tsconfig.json`, `tasks/t004-frontend-shell-routes.md`, `tasks/todo.md`.
- **Thay đổi:** Hoàn thành task T004 (React shell, route map và landmarks):
  - Triển khai `AppShell` với đầy đủ cấu trúc landmarks ngữ nghĩa (`<header>`, `<nav aria-label="Điều hướng chính">`, `<main id="main-content">`), skip link chuyển hướng đến nội dung chính và live region thông báo chuyển trang.
  - Thiết lập danh mục 9 route chuẩn hóa theo `docs/ui-architecture.md` §1 (`/`, `/lookup`, `/search`, `/word-forms/:wordFormId`, `/review`, `/quiz/new`, `/quiz/:attemptId`, `/quiz/:attemptId/result`, `/status`), bộ bóc tách dynamic route parameters và màn hình 404 cho route không hợp lệ.
  - Hiển thị trạng thái chưa khả dụng trung thực, không giả lập dữ liệu cho các route v1 chưa có logic nghiệp vụ.
  - Đảm bảo trạng thái `aria-current="page"` tại nav link đang active và bổ sung link truy cập quyền AI `/status#ai-consent` trong header shell.
  - Tích hợp `ErrorBoundary` bảo vệ ứng dụng khi một màn hình gặp sự cố và cung cấp liên kết chuyển sang kiểm tra trạng thái tại `/status`.
  - Cung cấp `shell.css` hỗ trợ responsive (320px - 1440px), tương phản cao, focus ring 3:1 và zoom 200% không che khuất control theo chuẩn WCAG 2.2 AA.
  - Đóng gói static build thành công vào `frontend/dist/` không chứa credentials hay bridge tokens.
  - Bổ sung 17 component/route test cases trong `AppShell.test.tsx`, đạt 21/21 tests frontend PASS cùng kiểm tra typecheck và lint hoàn hảo.
- **Mục đích:** Cung cấp khung giao diện React shell vững chắc, accessible và route map chuẩn mực cho các task giao diện tiếp theo.

## 29/09/2026

- **Khu vực:** `backend/app/main.py`, `backend/app/http/health.py`, `backend/tests/test_health.py`, shared `backend/app/persistence/database.py`/`backend/tests/test_storage.py`, thẻ T005, `tasks/todo.md`.
- **Thay đổi:** Hoàn tất phần T005-B theo scope được owner xác nhận: startup kiểm tra/migrate SQLite trước khi bật readiness; lỗi storage giữ `NOT_READY`; shutdown dispose engine và xóa readiness. Thay fixture file rỗng bằng SQLite thật, thêm 5 health/lifecycle cases và 2 schema edge cases từ review (reserved-prefix filter và view-only database). Final focused storage 24 PASS; full suite 41 PASS; Ruff/format/Mypy PASS; một Alembic head. Cập nhật T005 `DONE` với handoff và các gate downstream còn PENDING.
- **Mục đích:** Health phản ánh kết quả storage startup và bảo toàn dữ liệu trong failure paths. Skill documentation-and-adrs giúp ghi rõ default timeout, scope split, nguồn framework, evidence và giới hạn Linux/Windows/security tooling mà không thay spec/API contract.

## 29/09/2026

- **Khu vực:** `backend/app/persistence/database.py`, `backend/migrations/env.py`, `backend/migrations/versions/0001_storage.py`, `backend/tests/test_storage.py`, generated `alembic.ini`, task T005.
- **Thay đổi:** Hoàn tất phần T005-A theo scope split được owner xác nhận: migration ledger, FK trên mỗi connection, bounded busy timeout, phát hiện WAL, integrity/schema checks trước mutation, migration trong transaction và fail-safe readonly/corrupt DB. Thêm 22 storage cases; full suite 34 PASS, Ruff/format/Mypy PASS, một Alembic head.
- **Mục đích:** Có checkpoint storage kiểm chứng được trước khi nối health/lifecycle ở T005-B; domain schema và dữ liệu học thật được giữ ngoài scope.

## 29/09/2026

- **Khu vực:** `tasks/t005-database-schema-migrations.md`, `docs/changelogs.md`.
- **Thay đổi:** Ghi audit khi tiếp tục T005: baseline health T003 đạt 8 tests; phát hiện health readiness và fixtures cần sửa ở hai file ngoài allowlist, khiến task cần scope clarification/chia nhỏ trước implementation.
- **Mục đích:** Ghi rõ điểm chặn và evidence để tiếp tục đúng phạm vi; chưa thay application code, allowlist, spec/API contract hoặc đánh dấu T005 hoàn tất.

## 29/09/2026

- **Khu vực:** `tasks/t005-database-schema-migrations.md`, `docs/changelogs.md`.
- **Thay đổi:** Ghi checkpoint tạm dừng T005 sau khi đọc dependency/contract và kiểm tra trạng thái repository; chưa viết test/implementation, chưa chạy verification hay commit T005. Giữ task `TODO` để phiên sau bắt đầu từ bước test RED.
- **Mục đích:** Bảo toàn ngữ cảnh và ranh giới scope cho phiên làm việc tiếp theo theo yêu cầu người dùng.

## 29/09/2026

- **Khu vực:** backend/app/main.py, backend/app/http/health.py, backend/app/platform/config.py, backend/__init__.py, backend/tests/test_health.py, tasks/t003-backend-skeleton.md, tasks/todo.md.
- **Thay đổi:** Hoàn thành task T003: Triển khai FastAPI app factory (`create_app`) và endpoint `GET /api/v1/health` theo đúng normative schema `HealthSummary` (`status`, `version`, `storageStatus`, `bridgeStatus`, `readiness`) và header `Cache-Control: no-store`; cấu hình `AppSettings` với ràng buộc chỉ bind loopback interfaces (127.0.0.1, localhost, ::1) theo threat T-01; kiểm tra storage status trung thực (`OK` khi storage tồn tại, `NOT_READY` khi missing); độc lập hoàn toàn với AI bridge (0 inference call, 0 credential read); quản lý vòng đời ASGI startup/shutdown qua lifespan context; bổ sung 8 tests với 100% độ phủ mã nguồn cho backend app; vượt qua toàn bộ Mypy strict, Ruff và Pytest quality gates.
- **Mục đích:** Cung cấp skeleton backend vững chắc và health probe cho các task tiếp theo (T004 frontend shell, T005 SQLite migration zero).

## 29/09/2026

- **Khu vực:** pyproject.toml, backend/tests/conftest.py, backend/tests/test_toolchain.py, docs/toolchain.md, tasks/t058-python-quality-gates.md, tasks/todo.md.
- **Thay đổi:** Hoàn thành task T058: Cấu hình Python quality gates gồm Ruff linter với quy tắc chuẩn (E, W, F, I, B, C4, UP, ARG, SIM, RUF), MyPy static type checker ở chế độ strict (strict = true, files = ["backend"]), Pytest và Pytest-cov tự động xuất báo cáo Cobertura XML (`coverage.xml`) sau mỗi lần chạy suite; tạo `backend/tests/conftest.py` với fixtures `project_root` và `python_version_info`; tạo `backend/tests/test_toolchain.py` kiểm tra phiên bản Python >=3.12, importable dependencies từ lockfiles, nạp fixtures và cấu hình pyproject; thực hiện negative probes xác nhận phát hiện lỗi assertion, collection, lint và type mismatches; hoàn tất checkpoint CP01.
- **Mục đích:** Cung cấp hạ tầng quality gates, runner và coverage cho backend theo CONSTRAINTS.md, sẵn sàng cho việc triển khai FastAPI app factory tại T003.

## 29/09/2026

- **Khu vực:** package.json, package-lock.json, tsconfig.json, eslint.config.js, vite.config.ts, frontend/tests/toolchain.test.ts, tasks/t002-quality-gates-test-runner-build.md, tasks/todo.md.
- **Thay đổi:** Hoàn thành task T002: Cấu hình frontend quality gates gồm ESLint flat config (eslint.config.js với typescript-eslint và react plugins), TypeScript strict configuration (tsconfig.json), Vite 8 và Vitest runner (vite.config.ts với passWithNoTests=false); bổ sung scripts `lint`, `typecheck`, `test:frontend`, `build` vào package.json; tạo bộ test frontend ban đầu frontend/tests/toolchain.test.ts kiểm tra runtime Node >=20.19.0, assertions và báo cáo BUILD_PENDING_SHELL; xác minh probes bắt lỗi âm/dương cho assertion, type, lint và build thiếu entry point.
- **Mục đích:** Cung cấp hạ tầng quality gates và test runner hoàn chỉnh cho frontend theo CONSTRAINTS.md và UI architecture §10, sẵn sàng cho T004.

## 29/09/2026

- **Khu vực:** package.json, package-lock.json, requirements.lock, requirements-dev.lock, README.md, docs/toolchain.md, tasks/t001-toolchain-repository-skeleton.md, tasks/todo.md.
- **Thay đổi:** Hoàn thành task T001: Khóa phiên bản toolchain frontend (React 19, TypeScript 5.8, Vite 8) qua package.json và package-lock.json; khóa phiên bản toolchain backend (FastAPI 0.141, Pydantic 2.13, SQLAlchemy 2.1, Alembic 1.20, Uvicorn 0.54, HTTPX 0.28, Ruff 0.16, MyPy 2.3, Pytest 9.1, Pytest-cov 7.1, Pip-tools 7.6) qua pyproject.toml và requirements.lock / requirements-dev.lock; tạo README.md và docs/toolchain.md hướng dẫn cài đặt và công bố trạng thái readiness của lệnh; xác minh clean install tái lập độc lập và cấu hình .gitignore.
- **Mục đích:** Thiết lập nền tảng toolchain có thể tái lập cho toàn bộ các task downstream bắt đầu từ T002 và T058, tuân thủ CONSTRAINTS.md và AGENTS.md.

## 29/09/2026

- **Khu vực:** CONSTRAINTS.md, AGENTS.md, tasks/_template.md, tasks/t001–t066, tasks/todo.md, docs/task-plan.md, docs/project-context.md.
- **Thay đổi:** Hoàn thiện bản planning thành 66 task nhỏ và 22 checkpoints; tách quiz generation/draft/submission/feedback, các UI flow, tool runners, benchmark và Windows/recovery evidence. Sửa nội dung ghép sai ở 9 task card, commit proposals, scope allowlists, route wiring, dependency order và references. Bổ sung command owner/readiness registry, planned numeric configuration và ranh giới canonical learning storage/diagnostic redaction, giữ các quality thresholds.
- **Mục đích:** Có kế hoạch bắt đầu được từ T001, với T013 conformance là prerequisite cho business contract; không đánh dấu application tests/release evidence đã PASS. Kiểm tra planning có 66 unique cards, 225 dependency edges không chu kỳ, 22 checkpoints và link/current-vs-planned outputs đúng; lưu evidence ở docs/reviews/planning-validation-001.md. Mọi implementation task vẫn TODO; không application code, real provider request, commit, remote hay PR được tạo trong session này.

## 29/09/2026

- **Khu vực:** `CONSTRAINTS.md`, `AGENTS.md`, `tasks/`, `docs/task-plan.md`, `docs/project-context.md`.
- **Thay đổi:** Tạo quality bar bảo thủ với floor, type/lint/test/coverage/security/accessibility/performance gates; tạo persistent agent context; chia implementation thành 46 task cards nhỏ với dependencies, checkpoints, verification, stop conditions và commit proposals; thêm todo/plan pointers và cập nhật project map.
- **Mục đích:** Chuyển design baseline `READY_FOR_PLANNING` thành kế hoạch implementation có thể kiểm chứng, không viết application code, không tạo remote/commit hoặc gọi provider.

## 29/09/2026

- **Khu vực:** `docs/spec.md`, `docs/api-contract.md`, `docs/ui-architecture.md`, `docs/security-review.md`, `docs/observability-plan.md`, `docs/adr/0001-architecture.md`, `docs/project-context.md`, `docs/reviews/spec-architecture-review-001.md`.
- **Thay đổi:** Loại bỏ các câu hiện hành còn tham chiếu OQ/policy chưa chốt; chuẩn hóa model `gemini-3.8-flash-high`, revision conflict, local SpeechSynthesis, hard timeout/cancellation budgets, runbook first-run, ADR-0004 authority và đánh dấu phần review cũ là historical. Sửa các acceptance/UI/API mâu thuẫn (LWW, missing IPA/link, offline audio, FTS5 boundary) và thêm final doubt-driven recheck với không còn Critical/Major design blocker. Giữ các runtime/profile/benchmark/`CONSTRAINTS.md` items là evidence gates.
- **Mục đích:** Kết thúc design-blocked state một cách nhất quán, không tuyên bố application code hoặc runtime/security tests đã pass.

## 29/09/2026

- **Khu vực:** status headers, project context, ADR-0002/0003, review disposition, security/API audio wording.
- **Thay đổi:** Hoàn tất đồng bộ sau closure pass; ghi `READY_FOR_PLANNING` cho spec/architecture/review, đánh dấu historical blocker sections, chuyển audio sang SpeechSynthesis local và loại bỏ các câu còn tuyên bố OQ/paid-fallback/LWW chưa chốt.
- **Mục đích:** Kết thúc design-blocked state đúng theo ADR-0004; giữ `CONSTRAINTS.md` và runtime tests làm planning/implementation gates.

## 29/09/2026

- **Khu vực:** `docs/spec.md`, `docs/api-contract.md`, `docs/ui-architecture.md`, `docs/security-review.md`, `docs/observability-plan.md`, `docs/reviews/spec-architecture-review-001.md`.
- **Thay đổi:** Đồng bộ các contract theo ADR-0004: revision conflict thay LWW, five-box SRS/quiz snapshot/limits, local SpeechSynthesis, WCAG 2.2 AA target, benchmark/timeout gates, journal recovery, dashboard formulas và OQ overlay. Đánh dấu các R2 section cũ là historical và dùng closure table làm disposition hiện hành.
- **Mục đích:** Giữ tài liệu nhất quán sau khi owner ủy quyền chốt mọi blocker; vẫn phân biệt decision closure với runtime verification.

## 29/09/2026

- **Khu vực:** `docs/adr/0004-v1-product-policy-and-operational-baseline.md`, spec/API/UI/security/observability/ADR-0001/project context/review.
- **Thay đổi:** Chốt toàn bộ OQ-01–OQ-14 bằng các mặc định v1 bảo thủ: provider/model/cost policy, five-box SRS, quiz snapshot/rubric, identity/conflict/journal, Windows launcher/autosave, local SpeechSynthesis, WCAG 2.2 AA, benchmark/timeouts, dashboard formulas, secret/recovery boundary và legacy Markdown. Chuyển architecture/spec/review sang `READY_FOR_PLANNING`; giữ runtime/CONSTRAINTS gates cho planning/implementation.
- **Mục đích:** Kết thúc trạng thái block theo ủy quyền của owner mà không tuyên bố code/runtime/security tests đã pass.

## 29/09/2026

- **Khu vực:** `docs/spec.md`, `docs/security-review.md`, `docs/adr/0002-antigravity-loopback-trust-boundary.md`, `docs/reviews/spec-architecture-review-001.md`.
- **Thay đổi:** Ghi nhận owner không cấm paid fallback về nguyên tắc; làm rõ fallback trả phí chỉ được dùng khi READY policy khai báo route/provider/model/billing, disclosure/consent và quyền hạn/quota tương ứng.
- **Mục đích:** Tách “không cấm” khỏi việc tự cấp phép hoặc tự bật fallback; giữ các quyết định provider, route, entitlement, quota, retention và region ở R2-002.

## 29/09/2026

- **Khu vực:** `docs/api-contract.md`, `docs/spec.md`, `docs/ui-architecture.md`, `docs/security-review.md`, `docs/adr/0001-architecture.md`, `docs/adr/0003-ai-consent-and-revocation.md`.
- **Thay đổi:** Bổ sung immutable policy digest/structured disclosure fields, exact scope and dispatch-rule authorization, cross-process consent fencing, append-only consent events và redacted Operation provenance; sửa retry feedback bằng key mới; đánh dấu audio disabled tới OQ-06; khôi phục câu chữ ADR-0001 ở dạng historical với supersession notice; cập nhật AC-27/AC-34 và test cases.
- **Mục đích:** Xử lý các finding fresh review mà không tự chọn provider/quota/billing/retention/region hoặc hạ tiêu chuẩn bảo mật.

## 29/09/2026

- **Khu vực:** API/spec/UI/security/observability/ADR-0001/ADR-0003 và review `spec-architecture-review-001.md`.
- **Thay đổi:** Reconcile fresh adversarial review: ràng buộc policy theo digest + scope/provider/model/route/billing, fence consent cross-process, event audit/provenance, retry feedback bằng key mới, AC-27/AC-34 chính xác hơn, audio disabled khi OQ-06 chưa sẵn sàng và disclosure schema có trường bắt buộc. Ghi nhận R3-001–R3-013 cùng các release/runtime gates.
- **Mục đích:** Không để consent boolean, smoke test hoặc CLI wording vượt qua policy cloud, auth/profile, audio và retry boundaries; giữ R2-002 cùng các blocker khác ở trạng thái chưa sẵn sàng.

## 29/09/2026

- **Khu vực:** `docs/adr/0003-ai-consent-and-revocation.md`; spec/API/UI/security/observability, project context và review ledger.
- **Thay đổi:** Áp dụng phê duyệt của owner cho consent AI local default-deny: disclosure trước lần gửi đầu tiên, lưu policy version/choice, revoke offline chặn dispatch mới và giữ học cục bộ. Thêm API singleton/ETag/idempotency/dispatch gate, UI `/status#ai-consent`, AC-37–40, CONSENT-01–10, threat T-22 và telemetry redaction.
- **Mục đích:** Xử lý phần consent của R2-002 mà không giả định provider/model/quota/billing/retention/region đã được duyệt; giữ R2-002 blocked và không viết application code, gọi cloud hoặc lưu credential.

## 29/09/2026

- **Khu vực:** `docs/adr/0002-antigravity-loopback-trust-boundary.md`; supersession notice ở ADR-0001; spec/API/security/observability, bridge runbook, project context và review ledger.
- **Thay đổi:** Áp dụng phê duyệt của owner cho HTTP loopback + proxy API key với Antigravity v4.8.4 và rủi ro giả mạo process cục bộ được chấp nhận. Bỏ yêu cầu bridge IPC/per-launch/process authentication chưa có cơ sở; thêm profile/preflight/error contract, AC-36/BR-AUTH-01–08 và làm rõ ranh giới trace tại app→proxy. Giữ nguyên thân ADR-0001, không sửa `CONSTRAINTS.md` hay browser session.
- **Mục đích:** Xử lý R2-001 ở cấp thiết kế mà không giả định đã pass runtime/security tests. R2-002 và các blocker khác vẫn mở; không đổi `REVIEW_STATUS`, viết application code, gọi inference hoặc thay cấu hình/credential thực tế.

## 29/09/2026

- **Khu vực:** `docs/spec.md`, `docs/api-contract.md`, `docs/security-review.md`, `docs/project-context.md`, `docs/reviews/spec-architecture-review-001.md`
- **Thay đổi:** Ghi nhận owner xác nhận Antigravity Tools v4.8.4 và đối chiếu tag tới commit nguồn đã kiểm tra. Chuyển điểm cần làm rõ của R2-001 từ phiên bản sang quyết định ranh giới tin cậy; ghi phương án loopback/API-key cùng trade-off nhưng chưa áp dụng.
- **Mục đích:** Không hỏi lại phiên bản đã biết và không coi xác nhận phiên bản là phê duyệt thay đổi xác thực. Chưa sửa cấu hình, dùng credential, viết application code hoặc đổi review status.

## 29/09/2026

- **Khu vực:** `docs/spec.md`, `docs/api-contract.md`, `docs/security-review.md`, `docs/project-context.md`, `docs/reviews/spec-architecture-review-001.md`
- **Thay đổi:** Ghi nhận bridge do owner xác nhận là Antigravity Tools / Antigravity-Manager; phân biệt proxy API key với token/session Google; sửa cách gọi CLI trong luồng hiện hành. Bổ sung bằng chứng upstream theo commit về auth `auto/off`, bearer-key và giới hạn xác thực process; ghi rõ phiên bản cài đặt chưa biết.
- **Mục đích:** Thu hẹp R2-001 bằng nguồn chính thức của dự án mà không tự chấp thuận auth/model/billing, không thay đổi cấu hình, không đọc credential và không đóng blocker khi chưa đủ bằng chứng. Giữ `REVIEW_STATUS: BLOCKED`.

## 29/09/2026

- **Khu vực:** post-apply review, API/UI contracts, security/observability and project context
- **Thay đổi:** Chạy final doubt-driven recheck; sửa lookup idempotency/operation, feedback failure history, quiz answer examples, autosave/PATCH reconciliation, bootstrap wording, legacy date example và runbook retry semantics. Ghi nhận residual R2 owner gates và giữ `REVIEW_STATUS: BLOCKED`.
- **Mục đích:** Không tuyên bố readiness khi bridge auth/consent, source conflict/recovery, quiz/SRS rules, legacy mapping, benchmark, launcher lifecycle, audio/accessibility và recovery policy vẫn chưa được owner chốt.

## 29/09/2026

- **Khu vực:** `docs/reviews/spec-architecture-review-001.md`, `docs/api-contract.md`, `docs/observability-plan.md`, `docs/ui-architecture.md`
- **Thay đổi:** Chạy post-apply doubt-driven review; bổ sung residual blocker ledger R2-001–R2-020, feedback history/failure retrieval, status metrics/lifecycle, autosave/PATCH operation reconciliation, quiz answer restoration và error recovery DTO.
- **Mục đích:** Giữ `REVIEW_STATUS: BLOCKED` khi còn decision gates thay vì tự hạ chuẩn hoặc chuyển thủ công sang planning.

## 29/09/2026

- **Khu vực:** `docs/spec.md`, `docs/api-contract.md`, `docs/ui-architecture.md`, `docs/reviews/spec-architecture-review-001.md`
- **Thay đổi:** Bổ sung implementation gates trong spec, source/projection write protocol trong API, provisional conflict/startup behavior trong UI, và resolution ledger cho toàn bộ Critical/Major findings.
- **Mục đích:** Phân biệt rõ finding đã xử lý bằng contract với finding còn cần owner quyết định, không hạ chuẩn hoặc đổi `REVIEW_STATUS` thủ công.

## 29/09/2026

- **Khu vực:** architecture contracts, security/observability docs, ADR, spec clarifications, review reconciliation và `docs/runbooks/`
- **Thay đổi:** Áp dụng các finding đã được chấp thuận từ `spec-architecture-review-001`: hoàn thiện DTO/error/operation/revision contracts; làm rõ Vietnamese meaning search, Markdown round-trip/source revisions, quiz restore/SRS handoff, startup/offline/session states, authenticated loopback bridge, safe-path residuals, local-only telemetry defaults và runbooks.
- **Mục đích:** Giảm mâu thuẫn và các điểm không thể kiểm chứng mà không tự đóng các product OQ về provider, SRS/rubric, quiz snapshot, audio, conflict, backup, accessibility hoặc performance.

## 29/09/2026

- **Khu vực:** `docs/reviews/spec-architecture-review-001.md` và `docs/changelogs.md`
- **Thay đổi:** Thực hiện adversarial review độc lập cho spec và bộ tài liệu architecture; ghi nhận các finding về OQ chưa chốt, mâu thuẫn Markdown/SQLite và LWW/ETag, FTS5/search, quiz/SRS/autosave, bootstrap/bridge security, API schema, offline/runtime, observability và acceptance criteria.
- **Mục đích:** Chặn việc lập kế hoạch triển khai khi thiết kế còn rủi ro hoặc không thể kiểm chứng; yêu cầu owner review và chỉ áp dụng các finding được chấp thuận.

## 29/09/2026

- **Khu vực:** `docs/api-contract.md`, `docs/ui-architecture.md`, `docs/security-review.md`, `docs/observability-plan.md`, `docs/adr/0001-architecture.md`
- **Thay đổi:** Tạo contract REST/OpenAPI v1, kiến trúc UI/routes/flows, threat model bảo mật, kế hoạch structured logs/metrics/traces/alerts và ADR chọn React + TypeScript + Vite, FastAPI/Python, SQLite + SQLAlchemy/Alembic trên runtime Windows loopback.
- **Mục đích:** Chuyển spec sản phẩm thành architecture có thể triển khai mà không viết application code; giữ các `OQ-*` chưa chốt ở trạng thái review, ghi nguồn tài liệu chính thức và nêu rõ temporary constraints snapshot vì `CONSTRAINTS.md` chưa tồn tại.

## 29/09/2026

- **Khu vực:** `docs/spec.md` và `docs/changelogs.md`
- **Thay đổi:** Chốt hướng runtime local + inference cloud qua local OpenAI-compatible bridge; ghi nhận smoke test thật với `GET /health`, `GET /v1/models` và `POST /v1/chat/completions`. Bổ sung yêu cầu prompt template có version/placeholders, JSON response validation, lưu feedback theo attempt/question/model/prompt version và bảo vệ API key ở backend.
- **Mục đích:** Xác định contract tích hợp AI để chấm/nhận xét, trả feedback cho frontend và truy xuất lịch sử mà không đưa secret vào frontend hoặc database.

- **Khu vực:** `docs/spec.md` và `docs/changelogs.md`
- **Thay đổi:** Tạo spec chính thức từ biên bản product discovery, gồm problem statement, goals, users, journeys, capability map, requirements, business rules, dữ liệu, auth/authorization, UI states, accessibility, security, performance, scope/non-goals, acceptance criteria, open questions và assumptions; ghi trạng thái `SPEC_STATUS: DRAFT_REVIEW_PENDING`.
- **Mục đích:** Tạo bản review với capability gắn nhu cầu, 35 acceptance criteria có điều kiện/kết quả kiểm chứng, và đánh giá những điểm còn chặn việc chốt API, UI hoặc task triển khai; giữ các quyết định chưa rõ trong open questions và không tự chọn framework.

- **Khu vực:** `docs/interviews/product-discovery-001.md` và `docs/changelogs.md`
- **Thay đổi:** Tạo biên bản product discovery sau khi người dùng xác nhận `FINALIZE INTERVIEW`; ghi mục tiêu, người dùng, journeys, phạm vi/non-goals, dữ liệu và quyền truy cập, business rules, edge cases, yêu cầu phi chức năng, acceptance criteria sơ bộ, quyết định đã chốt, giả định và câu hỏi còn mở.
- **Mục đích:** Làm đầu vào viết spec dựa trên interview, phân biệt các quyết định mới với tài liệu tham chiếu và tránh coi những điểm chưa chốt là yêu cầu đã thống nhất.

- **Khu vực:** Git repository và `docs/project-context.md`
- **Thay đổi:** Xác nhận project root, khởi tạo Git với branch mặc định cục bộ `main`, và cập nhật context về trạng thái repository chưa có commit/remote.
- **Mục đích:** Chuẩn bị nền tảng version control cho giai đoạn thiết kế.


- **Khu vực:** `docs/project-context.md`
- **Thay đổi:** Ghi lại repository map, trạng thái Git, runtime/toolchain, frontend/backend hiện có, giới hạn, giả định và câu hỏi cho session tiếp theo.
- **Mục đích:** Tạo context bền vững cho giai đoạn thiết kế mà không thêm application code hoặc sửa spec.


- **Khu vực:** `AGENT.md`
- **Thay đổi:** Quy định agent phải sử dụng skill `agent-skills:documentation-and-adrs` khi tạo hoặc cập nhật tài liệu kỹ thuật, spec, ADR, API documentation, README hoặc changelog.
- **Mục đích:** Đảm bảo tài liệu ghi lại bối cảnh, lý do, đánh đổi và hệ quả của các quyết định quan trọng.

## 28/09/2026

- **Khu vực:** `AGENT.md`
- **Thay đổi:** Thêm quy định bắt buộc agent cập nhật `docs/changelogs.md` cho mọi thay đổi trong workspace.
- **Mục đích:** Đảm bảo mọi thay đổi đều có lịch sử theo dõi thống nhất.

## 28/09/2026

- **Khu vực:** `docs/`
- **Thay đổi:** Thêm quy định changelog và tạo cấu trúc tài liệu `development/spec`, `development/tasks`, `deployment/guide`.
- **Mục đích:** Theo dõi mọi thay đổi do agent thực hiện theo ngày.

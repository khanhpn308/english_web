# T088: Deterministic Evidence Collection and EvidenceBundle

**Task ID:** `T088`  
**Title:** Deterministic host evidence collection and EvidenceBundle  
**Status:** `TODO`  
**Goal:** Tách toàn bộ deterministic/mechanical evidence collection (thu thập bằng chứng xác định/cơ học) khỏi vòng lặp AI; host/control plane (máy chủ/lớp điều khiển) trực tiếp thu thập, kiểm tra, chuẩn hóa và đóng gói Git, scope, verification, integrity, provenance và timing evidence thành một `EvidenceBundle` có cấu trúc, deterministic và fail-closed để các AI reviewer/auditor về sau chỉ làm semantic/adversarial reasoning (suy luận ngữ nghĩa/đối kháng).  
**Level:** High

## Dependencies

- T087

## Files được phép sửa

- `tools/orchestrator/core.py`
- `tools/orchestrator/evidence.py`
- `tools/orchestrator/workflow.py`
- `tests/orchestrator/test_core.py`
- `tests/orchestrator/test_evidence.py`
- `tests/orchestrator/test_workflow.py`
- `docs/orchestrator.md`
- `tasks/t088-deterministic-evidence-bundle.md`
- `tasks/todo.md`
- `docs/changelogs.md`

## Context

T086 và T087 đã thiết lập:

- parallel read-only reviewer fan-out;
- concurrent executable verification;
- parent-only authority;
- deterministic reviewer fan-in;
- private verification toolchain isolation;
- exact Git candidate materialization;
- false-PASS protection.

Observed development workflow shows another dominant latency source: expensive AI models repeatedly decide to execute deterministic commands such as Git inspection, pytest, Ruff, Mypy, scope checks and hashing even though those commands themselves execute directly and deterministically on the host.

The target architecture is therefore:

```text
HOST / DETERMINISTIC CONTROL PLANE
        |
        +-- Git metadata / diff / scope
        +-- candidate provenance / hashes
        +-- executable verification
        +-- static/integrity checks
        +-- predefined deterministic probes
        +-- timing
        |
        v
EvidenceBundle
        |
        v
AI semantic/adversarial reasoning
```

Core principle:

```text
If correctness can be decided from exit codes, Git/filesystem state,
hashes, schema validation, deterministic parsing or predefined tests,
AI MUST NOT be in that execution/decision loop.
```

T088 establishes the host evidence layer and bundle contract.

T089 will later change reviewer input/probe protocol to consume this bundle directly.

## Required behavior

### 1. Host-only deterministic evidence collection

Evidence collection MUST execute entirely in Python/host process logic.

It MUST NOT:

- call an AI provider;
- call `Pipeline.invoke()`;
- ask a model which deterministic command to run;
- rely on model interpretation for PASS/FAIL of deterministic evidence.

Mechanical evidence is authoritative host evidence.

### 2. Introduce a versioned EvidenceBundle

Define a strict structured schema for `EvidenceBundle`.

At minimum it must identify:

```text
schema/version
task_id
base_sha
branch
source_digest
candidate provenance
scope evidence
verification evidence
artifact/log references
timing evidence
integrity metadata
```

The representation must be deterministic and schema validated.

### 3. Candidate provenance evidence

Bundle provenance must deterministically capture enough information to bind evidence to the exact frozen candidate.

At minimum preserve or reference:

```text
base SHA
branch
source digest
tracked/index/working-tree candidate identity
non-ignored untracked candidate identity where applicable
```

Do not weaken T087 three-layer materialization semantics.

### 4. Scope evidence

Host determines:

```text
allowed paths
actual changed paths
unexpected changed paths
scope verdict
```

No AI determines whether a path is inside the task allowlist.

Unexpected paths fail closed according to existing task policy.

Ordering must be deterministic.

### 5. Executable verification evidence

Reuse existing host verification semantics rather than duplicating verification logic.

Evidence must preserve declaration order and include deterministic metadata such as:

```text
command index
command identity
exit status
failure classification
timeout/oversize/setup status
duration
```

Do not make a model infer command success.

Preserve current failure semantics.

### 6. Evidence artifact references

Potentially large evidence such as:

```text
diffs
logs
scanner output
test output
```

must not require embedding arbitrary unbounded raw output inside `EvidenceBundle`.

Bundle may reference host-owned evidence artifacts using deterministic metadata such as:

```text
artifact name/path
SHA-256
byte size
media/type classification
bounded/redacted summary where appropriate
```

Referenced evidence must be integrity-checkable.

### 7. Deterministic serialization

Equivalent evidence inputs must produce semantically identical bundle ordering independent of:

```text
thread completion order
filesystem enumeration order
dictionary insertion accidents
reviewer timing
```

Use canonical ordering for collections where order is not contract-defined.

### 8. Atomic parent authority

Only authoritative parent/control-plane code may persist/register the final `EvidenceBundle`.

Worker threads and AI reviewers receive no artifact-registration authority.

Bundle persistence must use existing atomic artifact semantics.

### 9. Fail-closed completeness

A bundle MUST NOT be marked complete when required deterministic evidence is missing, malformed, mismatched to the frozen source, or fails integrity validation.

Examples:

```text
wrong source digest
wrong branch
missing required verification evidence
artifact hash mismatch
unexpected changed path
invalid bundle schema
```

must not silently degrade into a partial authoritative bundle.

### 10. Evidence integrity

Every referenced evidence artifact required by the bundle must be verifiable against recorded digest/size metadata.

Behavioral tests must prove tampering is detected.

### 11. Timing evidence

Collect monotonic wall-clock durations for deterministic execution where useful.

Timing is diagnostic evidence only.

Timing MUST NOT change PASS/FAIL semantics unless an existing timeout policy already does so.

### 12. Privacy / bounded evidence

Do not widen current privacy exposure.

Do not place secrets, arbitrary raw environment state or unbounded stdout/stderr into model-facing structured evidence.

Preserve existing redaction and output-limit policy.

### 13. Backward compatibility

T088 must not regress:

```text
T086 ReviewBundle semantics
T087 concurrent audit semantics
private verification sandbox
NO WRITABLE EXTERNAL BACKLINKS
Git three-layer materialization
single-writer authority
Auditor dispositions
false-PASS prevention
scheduler behavior
integration behavior
```

Existing `audit_checks` compatibility may remain during T088.

T088 may add `EvidenceBundle` alongside existing artifacts.

Do NOT remove historical artifact compatibility in this task.

### 14. No reviewer protocol rewrite yet

T088 builds the deterministic host evidence layer.

Do NOT yet implement the full future protocol:

```text
EvidenceBundle -> semantic reviewers -> ProbeRequest -> host probe -> reviewer
```

Dynamic targeted `ProbeRequest` belongs to T089.

T088 may define clean extension points but must not implement arbitrary reviewer-requested command execution.

### 15. No arbitrary shell requests from AI

T088 must not introduce an interface where model output directly becomes arbitrary shell/argv execution.

All executed deterministic commands remain repository/contract-owned.

## Acceptance criteria

- [ ] Strict versioned `EvidenceBundle` schema exists.
- [ ] Host can build `EvidenceBundle` without any AI/provider call.
- [ ] `EvidenceBundle` is bound to exact task/candidate provenance.
- [ ] Scope/allowlist verdict is computed deterministically by host.
- [ ] Verification PASS/FAIL metadata comes from executable host results, not AI judgment.
- [ ] Existing verification declaration order is preserved.
- [ ] Large/raw evidence uses integrity-checkable artifact references rather than unbounded embedding.
- [ ] Artifact SHA-256 and size metadata are deterministic and validated.
- [ ] Missing required evidence fails closed.
- [ ] Source/branch/digest mismatch fails closed.
- [ ] Unexpected changed path fails closed under existing policy.
- [ ] Referenced-artifact tampering is behaviorally detected.
- [ ] Bundle serialization/order is deterministic across equivalent runs.
- [ ] Thread completion order cannot change semantic bundle ordering.
- [ ] Parent remains the only authoritative bundle writer/registrar.
- [ ] No AI provider is invoked by evidence collection.
- [ ] `Pipeline.invoke()` is not used by deterministic evidence collection.
- [ ] Existing `audit_checks` compatibility remains intact.
- [ ] T086 focused regression passes.
- [ ] T087 focused regression passes.
- [ ] Scheduler regression passes.
- [ ] Full orchestrator regression passes.
- [ ] Ruff passes.
- [ ] Ruff format passes.
- [ ] Mypy passes.
- [ ] `git diff --check` passes.
- [ ] No product source changes.
- [ ] No provider/model default changes.

## Verification commands

```text
python -m pytest tests/orchestrator/test_core.py tests/orchestrator/test_evidence.py tests/orchestrator/test_workflow.py -q --no-cov -k "evidence_bundle or deterministic_evidence"
python -m pytest tests/orchestrator/test_core.py tests/orchestrator/test_workflow.py -q --no-cov -k concurrent_audit
python -m pytest tests/orchestrator/test_core.py tests/orchestrator/test_workflow.py -q --no-cov -k parallel_review
python -m pytest tests/orchestrator/test_scheduler.py -q --no-cov
python -m ruff check tools/orchestrator tests/orchestrator
python -m ruff format --check tools/orchestrator tests/orchestrator
python -m mypy tools/orchestrator
git diff --check
```

## Additional verification evidence

Run once before implementation handoff:

```text
python -m pytest tests/orchestrator -q --no-cov
```

All tests must use local deterministic fixtures.

No real provider/model/network calls are allowed in automated tests.

## Explicit non-goals

T088 does not:

- implement dynamic `ProbeRequest`;
- let AI execute arbitrary shell commands;
- integrate Herdr;
- change provider/model defaults;
- implement resource-aware scheduling;
- change scheduler `max_workers`;
- change `pytest -n 10`;
- change portable gate policy;
- modify `runtime.py`;
- modify `scheduler.py`;
- modify `orchestrator.yaml`;
- modify package/lockfiles;
- modify product source;
- remove historical `audit_checks`;
- claim T023 speedup.

## Risk

- **Level:** `High`.

Primary risks are duplicating authority, provenance mismatch, partial evidence being treated as complete, unstable serialization, artifact tampering, privacy regression and accidental changes to T086/T087 semantics.

## Stop conditions

STOP rather than expanding scope if implementation requires:

- modifying `tools/orchestrator/runtime.py`;
- modifying `tools/orchestrator/scheduler.py`;
- modifying `orchestrator.yaml`;
- modifying `package.json` or lockfiles;
- changing provider/model defaults;
- changing scheduler concurrency;
- allowing AI-generated arbitrary commands;
- weakening verification or source-integrity checks;
- removing historical artifact compatibility;
- modifying backend/frontend product source.

Request explicit owner scope extension if one of these is genuinely required.

## Proposed commit message

`feat(T088): add deterministic evidence bundle`
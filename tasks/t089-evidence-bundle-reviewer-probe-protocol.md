# T089: EvidenceBundle Reviewer Protocol and Safe ProbeRequest

**Task ID:** `T089`  
**Title:** Evidence-aware semantic reviewer protocol and host-owned safe probe execution  
**Status:** `IMPLEMENTATION_READY`  
**Goal:** Hoàn thiện trust boundary (ranh giới tin cậy) giữa deterministic host/control plane (host/lớp điều khiển xác định bằng máy) và AI semantic reviewers/auditor (AI soát xét/kiểm toán ngữ nghĩa): AI chỉ được đọc candidate-bound evidence (bằng chứng gắn với đúng candidate), đưa ra semantic findings (phát hiện ngữ nghĩa) và tùy chọn `ProbeRequest` có kiểu; host sở hữu `ProbeCatalog`, quyết định probe nào hợp lệ, thực thi probe bằng Python/repository-owned commands, đóng gói `ProbeEvidence`, phát hiện stale candidate (candidate đã thay đổi), và tuyệt đối không thực thi arbitrary shell/argv (shell/đối số tùy ý) do model sinh ra.  
**Level:** High

## Dependencies

- T088

This task MUST preserve T086 parallel reviewer semantics (ngữ nghĩa reviewer song song), T087 concurrent audit preparation (chuẩn bị audit đồng thời) và T088 EvidenceBundle authority (thẩm quyền EvidenceBundle).

## Files được phép sửa

- `tools/orchestrator/core.py`
- `tools/orchestrator/evidence.py`
- `tools/orchestrator/probes.py`
- `tools/orchestrator/workflow.py`
- `tests/orchestrator/test_core.py`
- `tests/orchestrator/test_evidence.py`
- `tests/orchestrator/test_probes.py`
- `tests/orchestrator/test_workflow.py`
- `tests/orchestrator/test_scheduler.py`
- `docs/orchestrator.md`
- `tasks/t089-evidence-bundle-reviewer-probe-protocol.md`
- `tasks/todo.md`
- `docs/changelogs.md`

`tools/orchestrator/probes.py` và `tests/orchestrator/test_probes.py` may be added if absent.

## Context

T086 established:

- three read-only reviewer perspectives (ba góc nhìn reviewer chỉ đọc);
- deterministic reviewer fan-in (gom reviewer theo thứ tự xác định);
- authoritative final Auditor (Auditor cuối có thẩm quyền ngữ nghĩa).

T087 established:

- executable verification lane (luồng xác minh thực thi) chạy đồng thời với reviewer fan-out;
- frozen candidate/source identity (danh tính candidate/source đóng băng);
- private verification workspace (workspace xác minh riêng);
- exact Git three-layer materialization (materialize chính xác tracked/index/working tree);
- parent-only state/artifact authority (chỉ parent có quyền ghi state/artifact);
- false-PASS protection (chống PASS giả).

T088 established:

- versioned `EvidenceBundle`;
- host-only deterministic evidence collection (host tự thu bằng chứng xác định);
- candidate provenance (nguồn gốc candidate), scope, verification, artifact integrity và timing evidence;
- deterministic serialization (tuần tự hóa xác định);
- fail-closed completeness (thiếu/sai bằng chứng thì đóng lỗi);
- `semantic_payload()` để đưa evidence an toàn cho AI mà không để timing chẩn đoán ảnh hưởng semantics.

The remaining architectural gap is the reviewer/probe protocol.

Current reviewers are still based on the pre-T088 prompt protocol. A model may reason about source and findings, but there is not yet a strict typed mechanism for:

1. consuming host evidence consistently;
2. requesting one additional targeted deterministic observation;
3. guaranteeing that model output can never become arbitrary shell/argv execution;
4. binding the requested probe and returned evidence to the exact frozen candidate;
5. preserving T087 concurrent verification/review overlap.

Target architecture:

```text
                   frozen candidate
                         |
              +----------+----------+
              |                     |
              v                     v
     HOST verification        semantic reviewers
              |                     |
              |                findings and/or
              |                 ProbeRequest
              |                     |
              +----------+----------+
                         |
                         v
                  parent deterministic join
                         |
                         v
                   EvidenceBundle
                         |
             validate ProbeRequest(s)
                         |
                         v
                    ProbeCatalog
               (host-owned registry)
                         |
                         v
                  deterministic probe
                         |
                         v
                    ProbeEvidence
                         |
             optional bounded reviewer resume
                         |
                         v
                    ReviewBundle
                         |
                         v
                 authoritative Auditor
                         |
                         v
                   host final gate
```

Core principle:

```text
AI MAY request a typed observation.
AI MUST NOT define how the host executes that observation.
```

## Required behavior

### 1. Strict reviewer evidence protocol

Introduce a strict typed reviewer input contract (hợp đồng input reviewer có kiểu).

The protocol MUST distinguish:

- immutable candidate identity (danh tính candidate bất biến);
- frozen task/contract context (ngữ cảnh task/hợp đồng đóng băng);
- host evidence already authoritative at the moment of dispatch;
- reviewer perspective (góc nhìn reviewer);
- bounded source/diff references;
- optional completed `EvidenceBundle.semantic_payload()` where available.

Reviewer input MUST NOT expose mutable host state objects.

Reviewer code MUST NOT infer deterministic PASS/FAIL from prose when authoritative host evidence exists.

### 2. Preserve T087 concurrency

T089 MUST NOT serialize the normal production audit cycle into:

```text
verification completes
-> reviewers start
```

Initial semantic reviewer fan-out MUST remain able to overlap with executable verification.

Therefore:

- initial reviewers receive only deterministic evidence available before dispatch plus frozen candidate/task context;
- they MUST NOT claim unfinished executable verification PASS/FAIL;
- after concurrent lanes join, parent builds/validates the complete T088 `EvidenceBundle`;
- final Auditor MUST receive the complete candidate-bound `EvidenceBundle`.

If a reviewer requests an additional probe, that bounded probe round occurs only after parent join and after candidate/evidence identity validation.

### 3. Introduce strict ProbeRequest

Define a versioned/strict `ProbeRequest` schema.

At minimum it must contain or bind:

```text
schema_version
probe_id
reviewer perspective / request origin
candidate identity
bounded validated parameters
rationale
```

It MUST NOT contain:

```text
shell
command
argv
executable
script
powershell
bash fragment
environment overrides
working-directory override
```

Unknown fields fail closed.

### 4. Host-owned ProbeCatalog

Introduce a repository-owned `ProbeCatalog` or equivalent registry.

Only host code may map:

```text
probe_id
->
ProbeDefinition
->
executor
```

A `ProbeDefinition` must explicitly define, as applicable:

- parameter schema;
- allowed reviewer roles/perspectives;
- timeout/output bounds;
- filesystem/source scope;
- whether it is pure inspection or executable;
- deterministic executor identity/version;
- evidence serializer;
- cache/key semantics where useful.

Model output MUST NOT register or mutate probe definitions.

### 5. No arbitrary shell/argv from AI

There MUST be no data flow equivalent to:

```text
model output
-> shell=True
-> subprocess
```

or:

```text
model-provided argv
-> execute()
```

AI-provided values may only populate explicitly validated typed parameters of an already repository-owned probe.

Tests MUST behaviorally prove that fields such as `command`, `argv`, shell metacharacters, path traversal and executable overrides cannot escape the ProbeRequest schema or ProbeCatalog policy.

### 6. Minimal safe initial probe catalog

T089 MUST implement a deliberately small initial catalog sufficient to prove the architecture.

At minimum include:

1. one pure deterministic source-inspection probe (for example bounded literal reference/search inspection implemented in Python, not shell); and
2. one repository-owned executable/predefined probe whose command/executor is selected entirely by `probe_id`, with no executable/argv supplied by AI.

Do not attempt to create a universal shell abstraction.

### 7. ProbeEvidence

Define strict structured `ProbeEvidence`.

At minimum preserve:

```text
schema_version
probe_id
request identity
candidate identity
executor identity/version
validated parameters
result classification
bounded structured result
artifact reference(s) where needed
integrity metadata
duration/timeout diagnostic metadata
```

Large output must use host-owned bounded artifact references with SHA-256/size integrity, following T088 principles.

Raw unbounded stdout/stderr MUST NOT be inserted into model-facing payloads.

### 8. Exact candidate binding

Every `ProbeRequest` and `ProbeEvidence` MUST bind to the same frozen candidate identity used by T088.

At minimum validate consistency across:

```text
task_id
base_sha
branch
source_digest
candidate provenance identity
```

If source changes after a reviewer emits a request but before host execution:

```text
STALE_PROBE_REQUEST
```

must fail closed.

Do not silently execute the request against the new source.

### 9. Bounded probe round

Normal T089 behavior allows at most one targeted probe round per reviewer per audit cycle.

A reviewer may:

- return findings with no probe;
- return a valid `ProbeRequest`;
- receive the resulting `ProbeEvidence` once;
- then return its final reviewer result.

No unbounded:

```text
reviewer -> probe -> reviewer -> probe -> ...
```

loop is allowed.

Any future multi-round protocol requires a separate task and explicit owner decision.

### 10. Probe requests are advisory, not authority

A reviewer request does not itself execute anything.

Host may deterministically classify a request as:

```text
ACCEPTED
UNSUPPORTED
INVALID
STALE
DENIED_BY_POLICY
```

Unsupported/invalid requests MUST NOT be converted into improvised shell commands.

Probe failure does not permit the model to override T088 deterministic verification semantics.

### 11. Parent-only authority

Reviewer threads and probe executors MUST NOT:

- transition authoritative `RunState`;
- call `save()`;
- call authoritative `artifact()` registration directly;
- mutate the task worktree;
- mutate candidate source;
- promote/merge anything.

Parent/control-plane code alone validates, persists/registers authoritative `ProbeEvidence`, `ReviewBundle` and downstream artifacts.

### 12. Read-only reviewer semantics

Reviewer and Auditor roles remain inspect-only.

T089 MUST preserve:

```text
Worker/Fix Worker -> source mutation allowed inside task scope
Reviewer -> no source mutation
Auditor -> no source mutation
Host -> verification/state/integration authority
```

A probe executor may use a private verification/probe workspace but must not mutate authoritative source.

### 13. Deterministic ordering and fan-in

Multiple reviewer probe requests/results must be normalized in deterministic declaration order independent of future/thread completion timing.

Ordering keys must be explicit and tested.

Equivalent inputs must yield semantically equivalent reviewer/probe bundles.

### 14. Reviewer resume integrity

If a reviewer receives `ProbeEvidence` in a bounded second call:

- use the same frozen reviewer perspective and candidate identity;
- provide the original reviewer result/request in bounded structured form;
- provide host-validated `ProbeEvidence`;
- do not rely on hidden mutable session history as authority;
- require strict schema validation for the resumed reviewer output.

A fresh deterministic prompt reconstruction is acceptable and preferred over trusting implicit chat state.

### 15. Final Auditor input

Authoritative final Auditor MUST receive, in bounded structured form:

- frozen task/contract context;
- exact candidate/source identity;
- complete T088 `EvidenceBundle.semantic_payload()`;
- deterministic `ReviewBundle`;
- accepted `ProbeEvidence` artifacts/results;
- reviewer request classifications where relevant.

Auditor remains semantic/adversarial authority only.

Auditor MUST NOT be allowed to override failed mechanical evidence.

### 16. Host final gate remains authoritative

T089 MUST NOT introduce a model field equivalent to authoritative `FINAL_PASS`.

Host final eligibility remains a deterministic combination of host evidence and allowed semantic decision state.

At minimum:

```text
mechanical evidence valid
AND candidate binding valid
AND semantic audit state acceptable
```

must be required before later integration logic can treat the candidate as eligible.

### 17. Privacy and bounded context

Do not widen current privacy exposure.

Probe/reviewer payloads MUST NOT include:

- secrets;
- credentials/tokens;
- arbitrary environment dumps;
- unbounded command output;
- unrelated repository/user files;
- raw ignored/transient verification output.

Preserve T087 private workspace isolation and T088 artifact integrity/redaction rules.

### 18. Backward compatibility

T089 MUST NOT regress:

- T086 three-perspective parallel reviewer semantics;
- T087 verification/reviewer overlap;
- T087 private verification toolchain isolation;
- T087 exact Git three-layer materialization;
- T087 false-PASS protection;
- T088 `EvidenceBundle` schema/authority;
- historical `audit_checks` compatibility unless explicitly versioned;
- scheduler behavior;
- integration behavior;
- current provider/model defaults.

### 19. No telemetry/model routing yet

T089 is only the reviewer/evidence/probe protocol.

Do NOT implement:

- telemetry/internal model benchmark;
- model router;
- multi-account broker;
- resource broker;
- Herdr runtime;
- Paperclip bridge;
- risk-aware model policy.

Those are downstream tasks.

## Acceptance criteria

- [ ] Strict reviewer input/context schema exists.
- [ ] Initial reviewer fan-out remains compatible with T087 concurrent verification.
- [ ] Initial reviewers cannot claim unfinished executable verification as authoritative evidence.
- [ ] Final Auditor receives complete validated `EvidenceBundle.semantic_payload()`.
- [ ] Strict versioned `ProbeRequest` schema exists.
- [ ] `ProbeRequest` cannot carry shell/command/argv/executable override fields.
- [ ] Unknown ProbeRequest fields fail closed.
- [ ] Host-owned `ProbeCatalog` exists.
- [ ] Probe definitions are repository-owned and cannot be registered/mutated by model output.
- [ ] At least one pure source-inspection probe is implemented and behaviorally tested.
- [ ] At least one predefined executable probe is implemented and behaviorally tested.
- [ ] AI cannot choose executable/argv for the predefined executable probe.
- [ ] Strict versioned `ProbeEvidence` schema exists.
- [ ] ProbeEvidence is bound to exact frozen candidate identity.
- [ ] Stale candidate between request and execution fails closed.
- [ ] Probe artifact references are integrity-checkable.
- [ ] Large/unbounded probe output is not embedded into model-facing payloads.
- [ ] Probe timeout/output-limit behavior is fail-closed and behaviorally tested.
- [ ] One-probe-round-per-reviewer limit is enforced.
- [ ] Invalid/unsupported/denied probe request never falls back to improvised execution.
- [ ] Parent remains sole authoritative artifact/state writer.
- [ ] Reviewer/Auditor remain source read-only.
- [ ] Probe execution cannot mutate authoritative task source.
- [ ] Multiple probe requests/results fan in deterministically independent of completion order.
- [ ] Reviewer resume uses explicit reconstructed structured context, not hidden session authority.
- [ ] Auditor cannot override mechanical verification failure.
- [ ] No direct arbitrary shell path from model output to subprocess exists.
- [ ] T086 focused regression passes.
- [ ] T087 focused regression passes.
- [ ] T088 EvidenceBundle focused regression passes.
- [ ] Scheduler regression passes.
- [ ] Full orchestrator regression passes.
- [ ] Ruff passes.
- [ ] Ruff format passes.
- [ ] Mypy passes.
- [ ] `git diff --check` passes.
- [ ] No product source changes.
- [ ] No provider/model default changes.

## Required behavioral security tests

Tests MUST include adversarial cases proving rejection/fail-closed behavior for at least:

```text
ProbeRequest with "command"
ProbeRequest with "argv"
ProbeRequest with unknown probe_id
probe parameter path traversal
probe parameter absolute external path
shell metacharacter payload
candidate source mutation after request
artifact tampering after probe
probe timeout
probe oversized result
reviewer attempts second probe round
probe executor attempts authoritative-source mutation
out-of-order concurrent probe completion
```

These tests must use synthetic local fixtures only.

No real provider/model/network call is allowed.

## Verification commands

Owner/host verification commands:

```text
python -m pytest tests/orchestrator/test_probes.py -q --no-cov
python -m pytest tests/orchestrator/test_core.py tests/orchestrator/test_evidence.py tests/orchestrator/test_workflow.py -q --no-cov -k "probe or reviewer_protocol or evidence_bundle"
python -m pytest tests/orchestrator/test_core.py tests/orchestrator/test_workflow.py -q --no-cov -k concurrent_audit
python -m pytest tests/orchestrator/test_core.py tests/orchestrator/test_workflow.py -q --no-cov -k parallel_review
python -m pytest tests/orchestrator/test_scheduler.py -q --no-cov
python -m pytest tests/orchestrator -q --no-cov
python -m ruff check tools/orchestrator tests/orchestrator
python -m ruff format --check tools/orchestrator tests/orchestrator
python -m mypy tools/orchestrator
git diff --check
```

All automated tests MUST use deterministic local fakes/fixtures.

## Explicit non-goals

T089 does not:

- change model/provider defaults;
- implement model selection;
- implement telemetry/internal benchmarking;
- implement multi-account Gemini routing;
- implement global resource-aware scheduling;
- integrate Herdr;
- integrate Paperclip;
- change scheduler `max_workers`;
- change `pytest -n 10`;
- change product source;
- change application API/UI behavior;
- permit arbitrary AI-generated shell/argv;
- permit multi-round open-ended probing;
- allow Reviewer/Auditor source mutation;
- replace T088 EvidenceBundle authority;
- remove T087 concurrency optimization;
- weaken historical verification evidence.

## Risk

- **Level:** `High`.

Primary risks:

- accidentally converting model text into executable commands;
- stale candidate/probe evidence being treated as current;
- reintroducing AI into deterministic decision loops;
- losing T087 verification/reviewer concurrency;
- hidden mutable reviewer session state becoming authority;
- probe workspace mutation leaking into authoritative source;
- unbounded context/output growth;
- nondeterministic fan-in;
- privacy/secret exposure;
- reviewer/advisor decisions overriding mechanical failure.

## Stop conditions

STOP rather than expanding scope if implementation requires:

- modifying `tools/orchestrator/runtime.py`;
- modifying `tools/orchestrator/scheduler.py`;
- modifying `orchestrator.yaml`;
- modifying package/lockfiles;
- changing provider/model defaults;
- changing scheduler concurrency;
- introducing shell/argv supplied by model output;
- weakening T087 source/workspace isolation;
- weakening T088 EvidenceBundle integrity/completeness;
- changing backend/frontend product source;
- implementing telemetry, model routing, Herdr or Paperclip.

Request explicit owner scope extension if one of these is genuinely required.

## Proposed implementation sequence

```text
1. Add ProbeRequest / ProbeEvidence / reviewer protocol schemas.
2. Add host-owned ProbeCatalog with minimal safe probes.
3. Add candidate-binding and stale-request validation.
4. Wire reviewer output -> bounded ProbeRequest collection.
5. Preserve concurrent initial reviewer/verification dispatch.
6. Parent join -> complete EvidenceBundle validation.
7. Execute accepted probe requests in host/private workspace.
8. Reinvoke only requesting reviewer once with ProbeEvidence.
9. Deterministically fan in final ReviewBundle.
10. Pass complete EvidenceBundle + ReviewBundle + ProbeEvidence to final Auditor.
11. Add adversarial/fail-closed tests.
12. Run focused regressions, then full host verification.
```

## Proposed commit message

`feat(T089): add evidence-aware reviewer probe protocol`

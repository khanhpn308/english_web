# T090: Host–Worker execution isolation and T089 infrastructure scope adjudication

**Task ID:** `T090`  
**Title:** Enforced code-only Worker boundary and auditable infrastructure ownership  
**Status:** `TODO`  
**Goal:** Thiết lập ranh giới quyền thực thi có thể kiểm chứng: AI Worker được đọc/sửa đúng mã nguồn đã phê duyệt nhưng không được chạy shell, Git, Python, test, build hay subprocess (tiến trình con). Host độc quyền các thao tác tất định. Đồng thời xét duyệt hợp lệ tám file hạ tầng đã xuất hiện trên T089 PR #5 nhưng nằm ngoài allowlist gốc, **không chỉnh sửa hoặc hợp thức hóa hồi tố task card hay bằng chứng T089**.  
**Level:** High

## Dependencies

- T088

**Ordering clarification:** T088 đã tích hợp. T089 PR #5 hiện là *unmerged candidate* nên không khai báo T089 là prerequisite `DONE` của T090: làm vậy gây deadlock vì PR #5 lại bị chặn bởi T090. Điều kiện thực thi là phải có một integration plan do host xác thực cho cặp candidate T089/T090 trước khi cập nhật `main`.

## Context cần đọc

- `AGENTS.md`, `AGENT.md`, `CONSTRAINTS.md`.
- `docs/orchestrator.md`, `docs/ci-host-verification.md` (trên T089 candidate).
- `tasks/t074-agy-worker-permissions.md`, `tasks/t087-concurrent-audit-preparation.md`, `tasks/t088-deterministic-evidence-bundle.md`, `tasks/t089-evidence-bundle-reviewer-probe-protocol.md`.
- [T089 Draft PR #5](https://github.com/khanhpn308/english_web/pull/5), head `55ad6c20b5f6257761e981729a5df49cb0af16eb`.
- [T089 GitHub Full CI R3](https://github.com/khanhpn308/english_web/actions/runs/37794190587): **8/8 PASS on that exact head**, not proof of Worker process isolation and not a scope waiver.
- `tools/orchestrator/runtime.py`, `tools/orchestrator/workflow.py`, `tools/orchestrator/__main__.py`, `tools/orchestrator/scheduler.py`, `orchestrator.yaml`, associated tests and CI configuration.

## Files được phép sửa

### Explicit T090 infrastructure ownership

- `tools/orchestrator/runtime.py`
- `tools/orchestrator/recovery.py`
- `tools/orchestrator/__main__.py`
- `tools/orchestrator/scheduler.py`
- `tests/orchestrator/test_runtime.py`
- `tests/orchestrator/test_recovery.py`
- `.github/workflows/t089-host-ci.yml`
- `docs/ci-host-verification.md`

### T090-specific isolation integration and regression coverage

- `tools/orchestrator/workflow.py`
- `tests/orchestrator/test_workflow.py`
- `tests/orchestrator/test_core.py`
- `orchestrator.yaml`
- `tools/orchestrator/worker_sandbox.py`
- `tests/orchestrator/test_worker_sandbox.py`
- `docs/orchestrator.md`
- `tasks/t090-host-worker-isolation-scope-adjudication.md`
- `tasks/todo.md`
- `docs/changelogs.md`

The two `worker_sandbox.py` paths may be **added only when an actual restricted execution mechanism needs these modules**. Listing a file does not require changing it. Every touched file needs a T090-specific justification and independent review. Unknown files, directory-level globs, unrelated app source, package locks, other task cards, archived run state, credentials, home-directory CLI settings and security thresholds are forbidden.

## Context và vấn đề

### Blocker A — scope ownership from T089 PR #5

T089's original allowlist did **not** contain these eight paths:

1. `.github/workflows/t089-host-ci.yml` — host-owned GitHub CI and portable verification.
2. `docs/ci-host-verification.md` — CI operating procedure and logs.
3. `tests/orchestrator/test_recovery.py` — compatibility/explicit host verification tests.
4. `tests/orchestrator/test_runtime.py` — provider/process boundary tests.
5. `tools/orchestrator/__main__.py` — dedicated `verify-candidate` CLI entry point.
6. `tools/orchestrator/recovery.py` — provenance-preserving recovery/import.
7. `tools/orchestrator/runtime.py` — provider dispatch and subprocess policy.
8. `tools/orchestrator/scheduler.py` — defer audit and preserve scheduler interfaces.

T090 provides **prospective task ownership and an adjudication workflow**, not an automatic retrospective exemption for the historical T089 contract. Prior to merge, host must record exact head/base SHAs, file-attribution matrix, rationale and a deliberate owner authorization of the combined integration plan. If per-task provenance or scope cannot be reconciled, keep PR #5 Draft/BLOCKED and separate or restage infrastructure changes onto a traceable T090 implementation branch. Never alter frozen T089 artifacts, allowlists or hashes to make an old run appear authorized.

### Blocker B — effective code-only execution boundary

`allow_process=False`, `worker_access!="full-access"`, CLI `--mode accept-edits` and prompt instructions are **preflight settings, not security isolation**. In particular, `accept-edits` must not be assumed to disable shell/process/terminal tools. `is_worker_code_only()` alone cannot establish effective protection.

Required policy:

```text
AI Worker: read/edit exact allowlisted source files only
AI Reviewer/Auditor: semantic/adversarial reasoning on host-provided evidence only
Host control plane: exclusively execute Git, pytest, npm, Ruff, Mypy,
                    predefined probes, hashes, verification, commit/merge
If provider capability cannot be proven non-executable: BLOCK before dispatch
```

The coding model must remain usable (including Gemini/AGY) when run under an actually enforceable restricted tool surface or OS sandbox. Do **not** solve the problem by simply banning all Gemini Workers, changing the default model, allowing `--dangerously-skip-permissions` or silently dropping the code-only requirement.

## Required behavior

1. **Inventory and proof:** inspect supported provider CLI capabilities and the actual tool grants of the deployed AGY/Codex versions. Record what is enforced by the tool broker/OS versus what is merely described in model prompts. Do not infer isolation from a flag name.
2. **Enforced edit-only boundary:** provide a host-enforced restricted execution environment or explicit allowlisted edit-only tool interface denying all shell, process spawning, arbitrary filesystem writes, Git mutation, subprocess bridges and permission escalation originating from Worker turns. Preserve host's separate executable gate lane. Sandbox/permission changes must be compatible with the specific platform and fail closed when unavailable.
3. **Pre-dispatch validation:** policy is evaluated by the host, with immutable configuration/capability identity; unsafe, unknown or stale runtime mode returns `BLOCKED` before model dispatch. Preserve existing lifecycle/fix/recovery behavior where authorized.
4. **Adversarial host tests:** on a disposable synthetic repository, attempt Worker-origin terminal/shell, `python -c`, `git status`, indirect process tools, environment override and write outside allowlist. Each attempt must be denied *before actual command execution*, and a legitimate allowlisted source edit must still succeed. Never run these real-provider probes on user files or with secrets present.
5. **No simulated security proof:** mocks may test rejection logic but cannot attest live vendor permission isolation. Include one independently observed negative live-tool/OS isolation test per supported Worker provider/platform before accepting that provider as code-only. If actual CLI facilities cannot deny commands, stop as `BLOCKED`, report limitation and propose host-mediated editor architecture; do not fake PASS.
6. **Host authority unchanged:** Reviewer/Auditor never execute deterministic gates; `run/resume` Worker handoff stops at `IMPLEMENTED`; a separate, intentional host verification request drives `verify-candidate`. Preserve sealed evidence, probe integrity, concurrent reviewer behavior and fixed scope.
7. **Scope adjudication:** build an eight-file exact-path ownership/provenance matrix against PR #5, including acceptance evidence and whether transplant/restaging is necessary. Owner explicitly signs off on T090/combined rollout scope after evidence. T090 does not mark or rewrite T089 as `DONE`.
8. **No automatic promotion:** changing task/PR state, applying broad permissions, replaying imports, creating new agents or merging into `main` is forbidden without a separate explicit owner action.

## Acceptance criteria

- [ ] All eight out-of-T089-allowlist files have explicit ownership, rationale, immutable before/after provenance and owner scope approval under T090; historical T089 artifacts unchanged.
- [ ] The T089/T090 integration plan is dependency-safe and reconciles per-task allowlists without rewriting historical task contracts.
- [ ] Effective AGY/Gemini and Codex Worker command-denial mechanism documented per provider/platform; configuration flags and prompts are not falsely counted as isolation.
- [ ] Host rejects unsafe/unknown/stale Worker permissions *before dispatch*; no unsafe fallback or shell escape; denial is testable.
- [ ] Synthetic real tool-boundary tests demonstrate command/process/Git/escalation denial and allowlisted edit success, without touching user data; truthful `BLOCKED` if unavailable.
- [ ] Host still performs Git, probes, verification and integration independently; Worker never executes them.
- [ ] Deferred Worker/Fix handoff, explicit `verify-candidate`, frozen evidence, recovery/import, T086/T087/T088/T089 invariants and scheduler backward compatibility preserved.
- [ ] Ruff lint/format, strict Mypy, relevant Python tests, full eight-gate Portable CI all PASS **on final T090 implementation SHA** with unchanged minimum changed-line coverage.
- [ ] Evidence report contains provider and runner versions, test commands/outcomes, source SHA, candidate/contract hashes, permission-denial proof, exact scope matrix and any unverified platform limitations.
- [ ] PR #5 remains Draft and `main` unchanged until independent acceptance and specific owner merge authorization.

## Verification commands

Owner/host-only verification; do not run from AI Worker:

```text
python -m ruff check tools/orchestrator tests/orchestrator
python -m ruff format --check tools/orchestrator tests/orchestrator
python -m mypy tools/orchestrator tests/orchestrator
python -m pytest tests/orchestrator/test_runtime.py tests/orchestrator/test_recovery.py tests/orchestrator/test_workflow.py -q --no-cov
python -m pytest tests/orchestrator -q --no-cov
npm run check:task:portable
git diff --check
```

These commands do not substitute for separate, host-attested **real provider** deny/allow capability probes, which must be documented using isolated synthetic inputs and an explicitly configured capability harness. Do not execute live probes automatically as a side effect of code completion.

## Stop conditions

Stop with evidence and `BLOCKED` when:

- the real provider can still execute shell/process commands or expose an unmediated equivalent while acting as Worker;
- required security boundary cannot be enforced on the deployment OS/runner;
- a file outside the exact T090 allowlist is required without owner approval;
- authorizing infrastructure would require tampering with T089 frozen run artifacts or task card;
- negative tests fail, data privacy is at risk, or toolchain/CI gates need to be weakened;
- integration would require merging unapproved candidate content.

## Handoff and evidence

- Requested 2026-10-08: create an **independent infrastructure task** covering scope ownership and code-only enforcement. This approval authorizes task creation/planning, **not implementation PASS or merge**.
- Task definition branch: `feature/t090-host-worker-isolation-scope` (from `main`).
- T089 reference: Draft PR #5 at tested head `55ad6c20b5f6257761e981729a5df49cb0af16eb`.
- Task state: `TODO`, no implementation, no live isolation test, no T090 CI evidence yet.

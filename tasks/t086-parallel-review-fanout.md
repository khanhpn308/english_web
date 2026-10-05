# T086: Intra-task parallel review fan-out

**Task ID:** `T086`
**Title:** Intra-task parallel read-only review fan-out
**Status:** `DONE`
**Goal:** Giảm wall-clock time và số vòng Worker/Auditor của một task bằng cách chạy nhiều reviewer read-only độc lập song song sau implementation, fan-in toàn bộ findings vào một authoritative Auditor duy nhất, trong khi giữ nguyên single-writer, deterministic state machine, fail-closed verification và Git/worktree safety.
**Level:** High

## Dependencies

- T084
- T085

## Files được phép sửa

- `tools/orchestrator/core.py`
- `tools/orchestrator/workflow.py`
- `tests/orchestrator/test_core.py`
- `tests/orchestrator/test_workflow.py`
- `tests/orchestrator/test_scheduler.py`
- `docs/orchestrator.md`
- `tasks/t086-parallel-review-fanout.md`
- `tasks/todo.md`
- `docs/changelogs.md`

## Context

Level 1 hiện có nhiều role nhưng một task vẫn chạy tuần tự:

Prompt Engineer -> Worker -> verification -> Auditor -> fix -> Worker -> verification -> Auditor.

Level 2 cho phép tối đa ba task pipeline chạy đồng thời nhưng không tạo parallelism giữa các reviewer của cùng một task.

T023 đã cho thấy một task High-risk có thể mất hơn hai giờ qua nhiều vòng Worker/Auditor. T086 là bước đầu tiên để tạo intra-task multi-agent parallelism mà không cho nhiều agent cùng ghi source.

Single-writer invariant phải được giữ:
- Worker/Fix Worker có thể ghi trong worktree theo contract.
- Reviewer shards và authoritative Auditor luôn read-only.
- Python orchestrator vẫn là authority duy nhất cho state transition, artifact registration, Git commit và integration.

## Required behavior

### 1. Parallel read-only reviewer fan-out

Sau khi Worker hoàn tất implementation và executable audit checks đã có evidence, orchestrator phải chạy nhiều reviewer shards read-only song song trên cùng một frozen source snapshot.

Tối thiểu ba perspective generic:

1. correctness / contract / concurrency / data-safety;
2. tests / failure paths / regression / edge cases;
3. security / architecture / scope / privacy.

Các perspective không được phụ thuộc task ID.

Mỗi shard dùng configured `auditor` provider/model nhưng prompt perspective khác nhau.

### 2. Không gọi `Pipeline.invoke()` đồng thời

`Pipeline.invoke()` hiện quản lý mutable orchestration state và không phải primitive concurrency-safe.

Không được đơn giản dùng ThreadPool/ProcessPool để gọi nhiều `invoke()` cùng lúc.

Phải có một parallel read-only invocation path riêng với các invariant:

- source snapshot được freeze trước fan-out;
- authoritative state/artifacts được kiểm tra trước fan-out;
- state mutation của parent không diễn ra từ reviewer threads;
- mỗi reviewer có unique prompt/schema/log/response artifact name;
- reviewer chỉ chạy readonly;
- sau fan-in phải xác nhận source snapshot, branch và protected artifacts không đổi;
- chỉ parent pipeline được đăng ký bundle/artifact/state sau khi tất cả reviewer hoàn tất.

### 3. Deterministic fan-in

Kết quả reviewer phải được tập hợp theo thứ tự perspective deterministic, không theo thứ tự future hoàn thành.

Mỗi finding phải có identity ổn định do host/orchestrator quản lý hoặc cơ chế tương đương để authoritative Auditor có thể disposition từng finding.

Reviewer completion order không được thay đổi semantic result ordering.

### 4. Authoritative Auditor vẫn là final authority

Parallel reviewer shards không được trực tiếp chuyển state sang PASS/FAIL.

Sau fan-in, authoritative Auditor hiện tại phải nhận:

- frozen task/contract context;
- Worker result;
- executable audit evidence;
- toàn bộ parallel review bundle.

Authoritative Auditor là model duy nhất tạo final `Audit`.

Python vẫn validate final Audit trước state transition.

### 5. Reviewer finding disposition

Final Audit không được âm thầm bỏ qua finding từ reviewer shards.

Mỗi actionable reviewer finding phải được final Auditor disposition rõ ràng, tối thiểu theo semantics:

- confirmed; hoặc
- dismissed với rationale/evidence.

Nếu một finding được confirmed và chưa được sửa trong source hiện tại thì final Audit không được PASS.

Schema phải giữ khả năng đọc historical audit artifacts đã được tạo trước T086.

### 6. Fail-closed reviewer execution

Nếu bất kỳ required reviewer shard nào:

- process fail;
- timeout;
- trả malformed output;
- vi phạm schema;
- mutate source;
- đổi branch;
- làm thay đổi protected artifact/state;

thì không được tạo partial PASS.

Không được silently drop failed reviewer.

Bounded retry được phép nhưng không được tạo retry vô hạn.

### 7. Single-writer invariant

Không reviewer nào được:

- sửa source;
- commit;
- merge;
- reset;
- stash;
- switch branch;
- thay đổi state/run artifacts có thẩm quyền.

Worker/Fix Worker vẫn là writer duy nhất.

T086 không triển khai multi-writer collaboration.

### 8. Parallelism proof

Regression test phải chứng minh reviewer execution thực sự overlap.

Không chỉ kiểm tra source có `ThreadPoolExecutor` hoặc chuỗi text.

Dùng deterministic fake provider/barrier/event synchronization hoặc tương đương để chứng minh ít nhất hai reviewer invocation active đồng thời.

Không dựa vào arbitrary sleep timing.

### 9. Failure aggregation proof

Regression tests phải chứng minh:

- một shard fail => whole parallel review phase fail;
- successful shards vẫn được reaped;
- authoritative Auditor không chạy trên incomplete bundle;
- không false PASS;
- source/state vẫn intact.

### 10. Deterministic ordering proof

Cho reviewer futures hoàn thành theo thứ tự khác với perspective declaration.

Bundle cuối vẫn phải có deterministic canonical ordering.

### 11. Final-audit coverage proof

Regression test phải chứng minh:

- authoritative Auditor nhận toàn bộ reviewer findings;
- final Audit phải disposition toàn bộ finding IDs;
- missing disposition bị deterministic validation reject;
- confirmed unresolved finding không thể tạo PASS.

### 12. Preserve existing workflow semantics

Không thay đổi:

- task-card parser/dependency semantics của T085;
- T084 portable gate semantics;
- Worker scope enforcement;
- retry provenance;
- Git/worktree locks;
- integration semantics;
- Level 2 scheduler dispatch semantics;
- max_fix_cycles behavior trong task này.

Không sửa scheduler.

### 13. Resource boundary

T086 chỉ tạo parallelism cho read-only reviewer fan-out.

Không tăng Level 2 task concurrency.

Không thêm CPU/RAM scheduler.

Không cho reviewer spawn nested sub-agents.

Global resource-aware arbitration là task riêng sau T086.

## Acceptance criteria

- [x] Một task có ít nhất ba read-only reviewer perspectives có thể chạy concurrent trong cùng audit phase.
- [x] Reviewer shards dùng cùng frozen source snapshot và contract.
- [x] Không gọi mutable `Pipeline.invoke()` concurrently.
- [x] Reviewer threads/processes không mutate authoritative RunState.
- [x] Single-writer invariant được giữ.
- [x] Reviewer bundle có deterministic ordering độc lập completion order.
- [x] Reviewer finding có deterministic identity.
- [x] Final authoritative Auditor nhận đầy đủ executable evidence và review bundle.
- [x] Final Audit disposition mọi actionable reviewer finding.
- [x] Missing reviewer disposition bị deterministic validation reject.
- [x] Confirmed unresolved finding không thể tạo Audit PASS.
- [x] Reviewer process/schema/timeout failure fail-closed và không chạy final Auditor trên incomplete bundle.
- [x] Read-only reviewer source mutation bị phát hiện và từ chối.
- [x] Regression test chứng minh reviewer invocations overlap thực sự.
- [x] Regression test chứng minh out-of-order completion vẫn fan-in deterministic.
- [x] Historical pre-T086 Audit artifacts vẫn parse được.
- [x] Existing Worker -> fix -> Auditor state transitions vẫn tương thích.
- [x] T085 dependency semantics không regress.
- [x] T084 portable verification semantics không regress.
- [x] Level 2 scheduler semantics không đổi.
- [x] Focused orchestrator tests PASS.
- [x] Full orchestrator regression suite được chạy ít nhất một lần và PASS như extended evidence.
- [x] Ruff PASS.
- [x] Ruff format PASS.
- [x] Mypy PASS.
- [x] `git diff --check` PASS.

## Verification commands

```text
python -m pytest tests/orchestrator/test_core.py tests/orchestrator/test_workflow.py -q --no-cov -k parallel_review
python -m ruff check tools/orchestrator tests/orchestrator
python -m ruff format --check tools/orchestrator tests/orchestrator
python -m mypy tools/orchestrator
git diff --check
```

## Additional verification evidence

Ngoài executable task verification ở trên, implementation phải chạy một lần:

`python -m pytest tests/orchestrator -q --no-cov`

Kết quả full suite được ghi vào task card/changelog làm extended regression evidence nhưng không thêm vào automatic per-cycle verification metadata vì suite hiện vượt task-verification budget 90 giây.

Phải benchmark fake-provider concurrency deterministically; không dùng network/model thật trong automated tests.

## Explicit non-goals

T086 không:

- chạy nhiều Worker cùng sửa source;
- parallelize Prompt Engineer với Worker;
- parallelize final Integrator;
- thay đổi provider/model mặc định;
- đổi Gemini sang GPT;
- tối ưu FAST/FULL verification arbitration;
- thay đổi `max_fix_cycles`;
- thêm convergence classifier;
- thay đổi Level 2 `max_workers`;
- sửa product implementation.

Các phần này thuộc task tiếp theo.

## Risk

- **Level:** `High`.

Concurrency mới trong orchestration có thể tạo race trên state/artifacts hoặc cho PASS thiếu evidence nếu fan-in không fail-closed.

Mitigation:
- reviewer read-only;
- frozen snapshot;
- parent-only state mutation;
- deterministic bundle;
- behavioral concurrency tests;
- final authoritative Audit;
- no scheduler/product changes.

## Stop conditions

DỪNG thay vì mở rộng scope nếu implementation cần:

- cho nhiều Worker ghi cùng worktree;
- sửa product source;
- sửa scheduler semantics;
- bypass artifact digest/state validation;
- bỏ reviewer thất bại khỏi bundle để tiếp tục;
- giảm test/coverage/security threshold;
- sửa T023 để làm test fixture;
- dùng real provider/network trong automated test.

## Commit message đề xuất

`feat(T086): parallelize intra-task review fanout`

## Initial implementation handoff — 05/10/2026 (Asia/Bangkok)

Starting HEAD: `da662a3dc5af7dd2b2c8f44dbaff08031b46fe0c`. No commit, merge,
rebase, reset, clean or push performed. Source implementation is confined to
`core.py` and `workflow.py`; tests, orchestrator documentation and task-local
bookkeeping are the other six allowed files.

Implemented dedicated read-only `ThreadPoolExecutor` dispatch after executable
evidence. Parent owns frozen source/branch/state/artifacts, builds every prompt
before dispatch, joins all futures, validates protections, deterministically
registers evidence, then atomically persists the complete canonical bundle.
Threads call provider.run only and never Pipeline.invoke/save/artifact. Every
reviewer inherits the configured auditor role/model; perspectives and host IDs
are generic and independent of task ID. Final Audit validates complete explicit
dispositions, rejects unresolved confirmed findings with PASS, and keeps old JSON
parseable. Reviewer failures do not retry or invoke final Auditor; existing final
Audit report correction remains bounded to three attempts on the same bundle.

Behavioral evidence uses a three-party barrier and reverse event chain:
all three calls are active before any completes (`max_active=3`), timeline is
three starts followed by three finishes, and completion is security -> verification
-> correctness while bundle order remains correctness -> verification -> security.
This proves three review units overlap in one coordinated logical round; no
internet or wall-clock latency assertion and no real T023 speedup claim.
Local CLI fixtures exercise real exit 7, timeout, oversized output and malformed
JSON. Additional tests reject schema/wrong perspective, source/branch/state/prompt/
contract mutation and out-of-band in-memory authority changes; all calls are
reaped, and final Auditor is absent on incomplete fan-out. Parent-thread assertions
guard invoke/save/artifact. Disposition tests cover successful dismissal,
missing/unknown/duplicate/confirmed findings and historical JSON without dispositions.

Verification snapshot:

- Focused fan-out plus timeout compatibility: 31 passed, 224 deselected (54.00s).
- Exact focused card command: 25 passed, 230 deselected (33.97s), exit 0.
- Extended `python -m pytest tests/orchestrator -q --no-cov`: 317 passed,
  4 failed (241.35s), exit 1. All four are scheduler fake-provider incompatibility;
  the complete core/workflow, parser, portable gate and other regressions pass.
  Full log: `/tmp/t086-orchestrator-regression.log`.
- Ruff check PASS; Ruff format PASS (10 files); Mypy PASS (6 source files);
  `git diff --check` PASS.
- First full regression: 310 passed, 10 failed (261.34s). Six timeout-call-count
  expectations were corrected in the allowed workflow test file to include three
  reviewers per audit cycle; the remaining four failures are described below.

Initial scope blocker (resolved by the owner extension below): the independent `SyntheticProvider` in
`tests/orchestrator/test_scheduler.py` supports Plan/WorkerResult/Audit/
IntegrationReview but raises AssertionError for ReviewShard. Four existing spawned
pipeline tests failed before final Auditor. This file was outside the initial
T086 allowlist and remained unchanged at that checkpoint. The smallest
required extension is imports plus a ReviewShard branch returning the requested
perspective and no findings in that test-only provider, preserving every scheduler
assertion and production behavior. Approval was pending at the initial handoff;
no runtime fallback, skipped/weakened tests or scheduler-specific exception added.

Intentionally untouched: runtime.py, scheduler.py, test_scheduler.py, config,
package/dependencies, CONSTRAINTS.md, all product files, T023/T084/T085, retained
worktrees/evidence and Git history. Next action: authorize/update the scheduler
fake-provider fixture and rerun the full orchestrator suite before marking T086
complete. No next product task dispatched.

## Owner-approved fixture scope extension — 05/10/2026 (Asia/Bangkok)

Owner explicitly authorized adding only `tests/orchestrator/test_scheduler.py`
to the T086 allowlist to adapt its existing SyntheticProvider to ReviewShard.
The initial scope blocker above is resolved by this authorization. Production
scheduler/runtime semantics, DAG/admission/dispatch concurrency and all existing
scheduler assertions must remain unchanged. No other path is added to scope.

The fixture derives the required perspective from the actual reviewer prompt,
asserts read-only invocation and returns schema-valid ReviewShard with no actionable
findings. It writes no source in this branch and leaves final Audit PASS semantics
intact. Existing spawned scheduler tests still execute the actual Pipeline fan-out;
additional assertions inspect the persisted complete empty review bundle. All
owner-required reruns are complete; final evidence is recorded below.

- Previously failing exact selection: all four spawned integration, independent
  dispatch, admission-slot and failure-isolation tests PASS (4 passed, 9.22s).
- Ruff check PASS; Ruff format PASS (10 files); Mypy PASS (6 source files);
  `git diff --check` PASS after the fixture adaptation.

- Exact focused command `python -m pytest tests/orchestrator/test_core.py tests/orchestrator/test_workflow.py -q --no-cov -k parallel_review`: 25 passed, 230 deselected (33.27s), exit 0.
- Scheduler command `python -m pytest tests/orchestrator/test_scheduler.py -q --no-cov`: 48 passed (12.40s), exit 0.

## Final owner-approved handoff — 05/10/2026 (Asia/Bangkok)

Outcome: `IMPLEMENTATION_READY`. Implementation acceptance is complete; candidate
remains uncommitted on `feature/t086-parallel-review-fanout`. Starting/current HEAD
is `da662a3dc5af7dd2b2c8f44dbaff08031b46fe0c`. The nine changed files are exactly
the current allowlist, including the owner-authorized scheduler test fixture.

Final exact verification results:

- The four formerly failing tests, selected explicitly by node ID, all PASS:
  `test_spawned_pipeline_integrates_and_unlocks_downstream`,
  `test_spawned_multiple_ready_pipelines_no_integration`,
  `test_spawned_pipelines_respect_external_admission_slots`,
  `test_spawned_pipeline_failure_does_not_stop_another_branch` (4 passed, 9.22s).
- `python -m pytest tests/orchestrator/test_core.py tests/orchestrator/test_workflow.py -q --no-cov -k parallel_review`: 25 passed, 230 deselected (33.27s), exit 0.
- `python -m pytest tests/orchestrator/test_scheduler.py -q --no-cov`: 48 passed (12.40s), exit 0.
- `python -m pytest tests/orchestrator -q --no-cov`: 321 passed (271.43s), exit 0.
  Extended evidence log: `/tmp/t086-owner-authorized-regression.log`; this full
  suite remains outside automatic per-cycle verification metadata.
- `python -m ruff check tools/orchestrator tests/orchestrator`: PASS.
- `python -m ruff format --check tools/orchestrator tests/orchestrator`: PASS, 10 files.
- `python -m mypy tools/orchestrator`: PASS, 6 source files.
- `git diff --check`: PASS.

Final inspection: `git status --short`, `git diff --name-only`, `git diff --stat`
and diff-check confirm exactly nine authorized changed files and no staged changes.
Production scheduler/runtime bytes match HEAD; no product/config/package/constraints,
T023/T084/T085 or retained worktree/evidence changes. Scheduler fixture diff adds
only imports, ReviewShard handling and persisted-bundle assertions; every existing
scheduler assertion remains intact. No tests skipped, deleted or weakened. Actual
spawned Pipeline fan-out still runs; empty reviewer findings leave Audit validation
and PASS semantics unchanged. No real inference/network calls or T023 speedup claim.

Unresolved findings: none. Prior scope blocker resolved by explicit owner approval.
Next action: independent review of this uncommitted candidate; no further task
was dispatched. No commit, merge, rebase, reset, clean or push performed.

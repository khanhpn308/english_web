# T086: Intra-task parallel review fan-out

**Task ID:** `T086`
**Title:** Intra-task parallel read-only review fan-out
**Status:** `TODO`
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

- [ ] Một task có ít nhất ba read-only reviewer perspectives có thể chạy concurrent trong cùng audit phase.
- [ ] Reviewer shards dùng cùng frozen source snapshot và contract.
- [ ] Không gọi mutable `Pipeline.invoke()` concurrently.
- [ ] Reviewer threads/processes không mutate authoritative RunState.
- [ ] Single-writer invariant được giữ.
- [ ] Reviewer bundle có deterministic ordering độc lập completion order.
- [ ] Reviewer finding có deterministic identity.
- [ ] Final authoritative Auditor nhận đầy đủ executable evidence và review bundle.
- [ ] Final Audit disposition mọi actionable reviewer finding.
- [ ] Missing reviewer disposition bị deterministic validation reject.
- [ ] Confirmed unresolved finding không thể tạo Audit PASS.
- [ ] Reviewer process/schema/timeout failure fail-closed và không chạy final Auditor trên incomplete bundle.
- [ ] Read-only reviewer source mutation bị phát hiện và từ chối.
- [ ] Regression test chứng minh reviewer invocations overlap thực sự.
- [ ] Regression test chứng minh out-of-order completion vẫn fan-in deterministic.
- [ ] Historical pre-T086 Audit artifacts vẫn parse được.
- [ ] Existing Worker -> fix -> Auditor state transitions vẫn tương thích.
- [ ] T085 dependency semantics không regress.
- [ ] T084 portable verification semantics không regress.
- [ ] Level 2 scheduler semantics không đổi.
- [ ] Focused orchestrator tests PASS.
- [ ] Full orchestrator regression suite được chạy ít nhất một lần và PASS như extended evidence.
- [ ] Ruff PASS.
- [ ] Ruff format PASS.
- [ ] Mypy PASS.
- [ ] `git diff --check` PASS.

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

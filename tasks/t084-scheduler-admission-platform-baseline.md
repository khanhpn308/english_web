# T084: Scheduler admission & platform-baseline normalization

**Task ID:** `T084`
**Title:** Normalize scheduler admission metadata and portable baseline verification
**Status:** `TODO`
**Goal:** Làm cho Level 2 scheduler có thể admission task ổn định trên Linux/WSL mà không làm yếu full repository verification hoặc native-Windows acceptance.
**Level:** High

## Dependencies

- T079
- T083

## Files được phép sửa

- `orchestrator.yaml`
- `package.json`
- `tasks/t081-app-shell-shadcn-migration.md`
- `tests/orchestrator/test_core.py`
- `tests/orchestrator/test_workflow.py`
- `tests/orchestrator/test_scheduler.py`
- `docs/orchestrator.md`
- `tasks/t084-scheduler-admission-platform-baseline.md`
- `tasks/todo.md`
- `docs/changelogs.md`

## Bằng chứng hiện có

Live trial đầu tiên của Level 2 scheduler đã phát hiện hai blocker độc lập.

### 1. Admission metadata của T081

`task_card(T018)` thất bại với:

`Unsupported task allowlist bullet`

Probe độc lập xác nhận:

- T018: parse OK
- T015: parse OK
- T017: parse OK
- T052: parse OK
- T081: FAIL `Unsupported task allowlist bullet`

Nguyên nhân là `## Files được phép sửa` của T081 chứa hai bullet dạng prose thay vì path thuần.

T081 hiện có scope thực tế gồm:

- `frontend/src/app/AppShell.tsx`
- `frontend/src/app/shell.css`
- `frontend/src/app/AppShell.test.tsx`
- `frontend/tests/e2e/shell.spec.ts`
- `package.json`
- `package-lock.json`

T084 chỉ được chuẩn hóa metadata. Không thay đổi implementation, dependencies, acceptance evidence hoặc trạng thái DONE của T081.

### 2. Baseline verification trên Linux/WSL

T023 đã được scheduler dispatch vào managed worktree nhưng dừng trước implementation với:

`INHERITED_BASELINE_FAILURE: Verification baseline failed (exit 1)`

Command thất bại:

`npm run check:task`

Kết quả trên Linux/WSL:

- 1021 Python tests PASS.
- 11 tests trong `backend/tests/windows/test_source_paths.py` FAIL.
- Các test này cố ý fail-closed khi `sys.platform != "win32"`.
- Không có implementation T023 nào được dispatch.

`orchestrator.yaml` hiện dùng:

- `npm run check:task`
- `python -m ruff check .`
- `python -m mypy backend tools/orchestrator`

`npm run check:task` và `npm run check:full` vẫn là full repository gates có thẩm quyền và không được làm yếu.

## Required behavior

### 1. Chuẩn hóa allowlist của T081

Trong `tasks/t081-app-shell-shadcn-migration.md`, mọi bullet nằm trong `## Files được phép sửa` phải là path repository chính xác, được đặt trong backticks.

Danh sách phải bao gồm:

- `frontend/src/app/AppShell.tsx`
- `frontend/src/app/shell.css`
- `frontend/src/app/AppShell.test.tsx`
- `frontend/tests/e2e/shell.spec.ts`
- `package.json`
- `package-lock.json`

Prose giải thích về scope extension và bookkeeping phải nằm ngoài danh sách path.

Không thay đổi implementation hoặc evidence lịch sử của T081.

### 2. Thêm Python portable test command

Thêm script vào `package.json`:

`test:python:portable`

Script này phải chạy Python pytest suite nhưng loại duy nhất:

`backend/tests/windows`

Không được:

- thêm skip/xfail vào Windows tests;
- sửa Windows tests;
- cấu hình pytest toàn cục để bỏ qua Windows tests.

### 3. Thêm portable scheduler baseline

Thêm script:

`check:task:portable`

Semantic coverage phải bao gồm:

- `check:fast:active`
- `test:frontend:coverage`
- `test:python:portable`
- `coverage:check`
- `security:secrets`
- `security:code`
- `security:deps`
- `architecture:check`

Không được làm yếu hoặc thay đổi semantics của:

- `check:task`
- `check:task:active`
- `check:full`

### 4. Chuyển orchestrator baseline sang portable gate

Trong `orchestrator.yaml`, đổi baseline đầu tiên từ:

`npm run check:task`

thành:

`npm run check:task:portable`

Giữ nguyên các command Ruff và Mypy riêng hiện có, trừ khi có bằng chứng repository rõ ràng buộc phải thay đổi.

### 5. Giữ native-Windows verification fail-closed

Portable scheduler baseline và full repository verification là hai contract khác nhau.

Portable baseline được phép bỏ native-Windows test suite để generic Linux/WSL tasks có thể admission.

Tuy nhiên:

- Native-Windows tests không được sửa.
- Khi chạy trực tiếp trên Linux, chúng vẫn phải fail-closed.
- Task thực sự yêu cầu Windows vẫn phải có genuine Windows evidence.
- Không được tạo bypass generic cho Windows acceptance.

### 6. Regression protection

Phải có regression coverage chứng minh tối thiểu:

- default orchestrator config dùng portable baseline;
- allowlist T081 machine-parseable;
- `task_card(Path.cwd(), "T018")` thành công trên candidate;
- `check:task`, `check:task:active`, `check:full` không bị làm yếu;
- không có task-ID-specific exception được thêm vào scheduler/runtime.

Không thêm special-case cho:

- T008
- T018
- T021
- T023
- T027
- T034

## Acceptance criteria

- [ ] T081 `## Files được phép sửa` chỉ chứa path bullets hợp lệ.
- [ ] `owned_paths()` parse T081 thành công.
- [ ] `task_card()` load T018 thành công.
- [ ] `package.json` có `test:python:portable`.
- [ ] `test:python:portable` chỉ loại `backend/tests/windows`.
- [ ] `package.json` có `check:task:portable`.
- [ ] `check:task:portable` giữ đầy đủ portable quality, coverage, security và architecture gates.
- [ ] `check:task`, `check:task:active`, `check:full` không bị làm yếu.
- [ ] `orchestrator.yaml` dùng `npm run check:task:portable`.
- [ ] Native-Windows tests không thay đổi.
- [ ] Native-Windows tests vẫn fail-closed khi chạy trực tiếp trên Linux.
- [ ] Không sửa product implementation.
- [ ] Không thêm task-specific scheduler exception.
- [ ] Level 1 và Level 2 scheduler semantics không thay đổi.
- [ ] Orchestrator regression tests PASS.
- [ ] Portable repository baseline PASS trên Linux/WSL hiện tại.
- [ ] Ruff PASS.
- [ ] Ruff format PASS.
- [ ] Mypy PASS.
- [ ] `git diff --check` PASS.

## Verification commands

```bash
npm run check:task:portable
python -m pytest tests/orchestrator -q --no-cov
python -m ruff check tools/orchestrator tests/orchestrator
python -m ruff format --check tools/orchestrator tests/orchestrator
python -m mypy tools/orchestrator
git diff --check
```

## Additional diagnostic evidence

Candidate phải chứng minh command sau thành công:

```python
from pathlib import Path
from tools.orchestrator.core import task_card

card = task_card(Path.cwd(), "T018")
assert card.task_id == "T018"
```

Sau khi T084 được integrate vào canonical main:

`python -m tools.orchestrator schedule --dry-run`

phải tiếp tục validate DAG thành công.

Không yêu cầu `npm run check:task` PASS trên Linux vì native-Windows fail-closed là inherited behavior có chủ đích.

## Legacy worktree protection

T084 tuyệt đối không được modify, reset, clean, rebase, delete hoặc adopt các worktree hiện có của:

- T008
- T018
- T027
- T034

Retained failed run của T023 chỉ là evidence và không được mutate.

Legacy candidate reconciliation sẽ được xử lý riêng sau khi scheduler admission infrastructure khỏe mạnh.

## Stop conditions

DỪNG thay vì mở rộng scope nếu remediation yêu cầu:

- sửa product implementation;
- làm yếu `check:task` hoặc `check:full`;
- sửa Windows tests để PASS/SKIP trên Linux;
- cấu hình pytest toàn cục để bỏ Windows tests;
- thêm task-ID-specific behavior vào scheduler, Pipeline hoặc runtime;
- xóa hoặc sửa legacy worktrees;
- thay đổi coverage/security thresholds;
- refactor rộng ngoài phạm vi task.

Nếu gặp trường hợp trên, report blocker thay vì bypass.

## Commit message đề xuất

`fix(T084): normalize scheduler admission baseline`

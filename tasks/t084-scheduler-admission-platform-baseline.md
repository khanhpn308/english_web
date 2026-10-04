# T084: Scheduler admission & platform-baseline normalization

**Task ID:** `T084`
**Title:** Normalize scheduler admission metadata and portable baseline verification
**Status:** `DONE`
**Goal:** Làm cho Level 2 scheduler có thể admission task ổn định trên Linux/WSL mà không làm yếu full repository verification hoặc native-Windows acceptance.
**Level:** High

## Dependencies

- T079
- T083

## Files được phép sửa

- `orchestrator.yaml`
- `package.json`
- `.agent/scripts/run-gates.sh`
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

### 7. Owner-approved verification metadata extension — 05/10/2026

Owner đã phê duyệt mở scope T084 trong file T081 hiện có, không tạo task mới:
tách exact `## Verification commands` và `## Snapshot results`. Giữ nguyên
historical snapshot (test counts, E2E/A11y/security/architecture/coverage,
original `QUALITY_BASE_REF` command và Linux/native-Windows inherited failure),
implementation, DONE status, dependencies và acceptance evidence của T081.

Executable dependency verification chỉ gồm các command rerunnable/parser-safe:

```text
npm run test:frontend -- frontend/src/app/AppShell.test.tsx
npm run typecheck
npm run architecture:frontend
git diff --check
```

Không có environment assignment, shell operators hoặc inline result comments;
không sửa parser để accommodate legacy metadata. Bốn command này kiểm tra behavior,
TypeScript, frontend boundary và diff integrity; không mechanically promote E2E,
A11y, security hay full historical gates vào mọi dependent-task baseline.
Coverage/security/architecture repository vẫn do `config.verification` portable
baseline kiểm tra; không thêm `coverage:check` riêng vào dependency verification
để tránh lặp lại coverage gate. Historical coverage command giữ nguyên snapshot.

## Acceptance criteria

- [x] T081 `## Files được phép sửa` chỉ chứa path bullets hợp lệ.
- [x] `owned_paths()` parse T081 thành công.
- [x] `task_card()` load T018 thành công.
- [x] T081 có exact `## Verification commands`.
- [x] T081 historical snapshot được tách riêng và bảo toàn.
- [x] T081 executable commands đều pass `check_commands()`/`validate_command()`.
- [x] Không có environment assignment trong executable verification block.
- [x] `task_card(Path.cwd(), "T018")` load thành công với dependencies T015/T017/T052/T081, không có T080.
- [x] Dependency verification không mechanically rerun toàn bộ historical T081 snapshot.
- [x] `package.json` có `test:python:portable`.
- [x] `test:python:portable` chỉ loại `backend/tests/windows`.
- [x] `package.json` có `check:task:portable`.
- [x] `check:task:portable` giữ đầy đủ portable quality, coverage, security và architecture gates.
- [x] `check:task`, `check:task:active`, `check:full` không bị làm yếu.
- [x] `orchestrator.yaml` dùng `npm run check:task:portable`.
- [x] Native-Windows tests không thay đổi.
- [x] Native-Windows tests vẫn fail-closed khi chạy trực tiếp trên Linux.
- [x] Không sửa product implementation.
- [x] Không thêm task-specific scheduler exception.
- [x] Level 1 và Level 2 scheduler semantics không thay đổi.
- [x] Orchestrator regression tests PASS.
- [x] Portable repository baseline PASS trên Linux/WSL hiện tại.
- [x] Ruff PASS.
- [x] Ruff format PASS.
- [x] Mypy PASS.
- [x] `git diff --check` PASS.

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

## Initial R2 scope-stop evidence — 05/10/2026 (Asia/Bangkok)

Status: `BLOCKED_FOR_SCOPE_EXTENSION`; no commit, merge, rebase or push.
Starting HEAD/main: `2f0a7b9001c59bf186088255f362c4994fbf77f7` (clean worktree,
HEAD equals main, main ancestry exit 0, integrated T085).
Retained T084 candidate inspected read-only and unchanged; its obsolete T080
blocker and serial pytest evidence were not copied into this candidate.

Implemented within the allowlist: T081 six exact path bullets with original prose
outside the list; `test:python:portable` =
`python -m pytest --ignore=backend/tests/windows -n 10`; complete eight-gate
`check:task:portable` chain; portable orchestrator baseline with separate Ruff/Mypy
unchanged; documentation and nine T084 regression cases. Worker count follows
both existing portable pytest invocations in `.agent/scripts/run-gates.sh`, which
is untouched. Full repository scripts remain identical to starting HEAD.

The mandatory real `task_card(Path.cwd(), "T018")` diagnostic exits 1:
`Missing task section: Verification commands` in T081 dependency verification.
T081 has `## Verification commands & Snapshot results`; its allowlist now parses
successfully. A heading-only replacement **in memory**, without editing T081,
then raises `Unsupported verification executable` on the historical
`QUALITY_BASE_REF=... npm run coverage:check` line. Historical snapshot commands
also contain inline result comments. This requires executable verification
metadata normalization beyond the authorized T081 allowlist section; no parser,
T018 special-case, verification-heading or historical-evidence change was made.
Next work needs explicit scope extension for T081 verification metadata, keeping
its original snapshot, DONE status, dependencies and acceptance evidence intact.

T085 helper/core/scheduler and all its regression tests are preserved. Both
`dependency_ids` and scheduler metadata for the real T018 return exactly
`['T015', 'T017', 'T052', 'T081']`; the T080 false-positive is absent.

Verification actually performed:

- Focused nine T084 cases (`python -m pytest tests/orchestrator/test_core.py -q
  --no-cov -k 't081_allowlist_is_exact or default_orchestrator_config_uses_portable
  or real_t018_preflight or portable_python_uses_approved or
  portable_task_baseline_retains or authoritative_full_gates_remain or
  no_task_id_specific_scheduler'`): initially 5 failed/4 passed/101 deselected,
  exit 1 (0.37s); final 1 failed/8 passed/101 deselected, exit 1 (0.28s), solely
  the real T018 verification-section blocker.
- Four unchanged T085 cases: `python -m pytest
  tests/orchestrator/test_core.py::test_dependency_ids_canonical_and_embedded_tokens
  tests/orchestrator/test_core.py::test_dependency_ids_t018_synthetic_diagnostic_fixture
  tests/orchestrator/test_core.py::test_task_card_ignores_embedded_prose_dependencies
  tests/orchestrator/test_scheduler.py::test_scheduler_metadata_aligns_with_core_dependency_ids
  -q --no-cov`: 4 passed in 0.93s, exit 0.
- `python -m ruff check tools/orchestrator tests/orchestrator`: exit 0.
- `python -m ruff format --check tools/orchestrator tests/orchestrator`: exit 0,
  10 files already formatted.
- `python -m mypy tools/orchestrator`: exit 0, 6 source files.
- `git diff --check`: exit 0.

Stopped for scope before `time npm run test:python:portable`,
`time npm run check:task:portable`, the full `python -m pytest tests/orchestrator
-q --no-cov`, or direct native-Windows execution. Portable baseline exit, Python
wall time and complete gate wall time are **not measured**; no passing baseline
or performance claim is made. The real preflight regression remains failing;
it is not skipped, weakened or marked expected-failure.

Changed files: `orchestrator.yaml`, `package.json`,
`tasks/t081-app-shell-shadcn-migration.md`, `tests/orchestrator/test_core.py`,
`docs/orchestrator.md`, this card, `tasks/todo.md`, `docs/changelogs.md`.
Intentionally untouched: core/scheduler/Pipeline, T085 tests and card, T018/T080,
product source, Windows tests, pytest config, run-gates.sh, package-lock.json,
all legacy worktrees and retained T023 evidence. Next task: explicitly scoped
T081 executable-verification metadata normalization, then rerun real T018
preflight and all required timed gates before claiming remediation ready.

## Completed R2 verification — 05/10/2026 (Asia/Bangkok)

Current outcome: `REMEDIATION_READY`. Owner-approved scope extension resolves the
initial stop above within T084; no new task was created. DONE records verified
candidate completion, not integration into main. No commit, merge, rebase or push.
Starting HEAD remains `2f0a7b9001c59bf186088255f362c4994fbf77f7`, equal to main;
main ancestry exit 0. Original session started clean; continuation retained only
this session's eight authorized file changes.

T081 has exact `Verification commands` with four commands (in order):

```text
npm run test:frontend -- frontend/src/app/AppShell.test.tsx
npm run typecheck
npm run architecture:frontend
git diff --check
```

`check_commands(text)` and explicit `validate_command` calls accept all four,
without shell assignments/operators or inline result comments. They contribute
4 commands to T018's total 11 `dependency_verification` commands. AppShell's 27
behavior tests, TypeScript, frontend architecture and diff integrity provide
focused dependency revalidation. E2E/A11y/full historical runs are not promoted;
coverage/security remain in the complete portable repository baseline. No extra
coverage command is added to T081. Historical `QUALITY_BASE_REF` coverage command
remains in `Snapshot results`; its original fenced block is byte-preserved.
Dependencies, implementation notes, acceptance criteria, test cases and execution
failure classification also compare byte-identically to starting HEAD.

Required real probe (exit 0): `task_card(Path.cwd(), "T018")` returns task_id
`T018`, dependencies exactly `['T015', 'T017', 'T052', 'T081']`. Core shared helper
and scheduler metadata agree; T080 is absent. `owned_paths(T081)` returns the six
required paths. T085 source and all four regression functions remain unchanged;
all are exercised in the full suites below.

| Exact command/check | Result |
|---|---|
| `time npm run test:python:portable` | Exit 0; 1035 passed in pytest 73.97s; shell wall **74.553s**; 10 xdist workers; coverage XML generated |
| `time npm run check:task:portable` | Exit 0; shell wall **140.566s**; frontend 75 passed/5 suites, Python 1035 passed (81.82s), architecture 40 passed (20.49s), 7 import contracts kept/0 broken |
| `python -m pytest tests/orchestrator -q --no-cov` | Exit 0; **293 passed in 194.80s** |
| `python -m ruff check tools/orchestrator tests/orchestrator` | Exit 0 |
| `python -m ruff format --check tools/orchestrator tests/orchestrator` | Exit 0; 10 files already formatted |
| `python -m mypy tools/orchestrator` | Exit 0; no issues in 6 source files |
| `git diff --check` | Exit 0 |
| Four T081 executable commands run directly | Each exit 0; AppShell 27 passed, frontend architecture 24 modules/31 dependencies/0 violations |
| Focused T084 cases | Exit 0; 10 passed/101 deselected in 0.14s |
| `python -m pytest backend/tests/windows -q --no-cov` | Expected exit 1; **11 failed in 1.41s**, every failure is the native-Windows-unavailable Linux guard; no skip/xfail |

Portable coverage: changed **100.00%** (minimum 80.00%), total **92.70%**
(baseline 86.70%, tolerance 0.50). Secrets/code/dependency scans each return zero
findings. Gate run uses existing pinned binaries via `GITLEAKS_BIN`, `SEMGREP_BIN`
and `OSV_SCANNER_BIN` under `/home/khanh/.local/tools/` (8.30.1/1.178.0/2.6.0).
Existing ESLint fast-refresh warnings: 3; errors: 0. Thresholds are unchanged.
The full portable gate still takes over 90 seconds including external scanners
and architecture; measured timings are reported without hiding work or weakening
checks. The former serial-Python bottleneck is replaced with approved 10-worker
execution, not a new exclusion or retry policy.

Timing/test logs are local `/tmp/t084-r2-python.{log,time}`,
`/tmp/t084-r2-portable-gate.{log,time}`, `/tmp/t084-r2-orchestrator.log` and
`/tmp/t084-r2-windows.log`; they are not committed artifacts.

Changed files: `orchestrator.yaml`, `package.json`,
`tasks/t081-app-shell-shadcn-migration.md`, `tests/orchestrator/test_core.py`,
`docs/orchestrator.md`, this card, `tasks/todo.md`, `docs/changelogs.md`.
All are T084-allowlisted. Intentionally untouched: product/Windows source,
core/scheduler/Pipeline, all pre-existing tests, T085 card, T018/T080,
run-gates.sh, package-lock.json, pytest config and quality thresholds.
Retained T084 status and binary diff match the initial read-only snapshot;
legacy T008/T018/T027/T034 worktrees and retained T023 evidence were not touched.
Full `check:task`, `check:task:active`, `check:full` scripts remain identical to
starting HEAD and retain native-Windows inclusion.

Unresolved T084 blockers: none. Genuine native-Windows acceptance remains an
existing platform requirement; the expected Linux failures do not claim Windows
verification passed. Next step: independent review of this uncommitted candidate;
integration and legacy worktree reconciliation require separate authorization.

## Performance Gate Remediation — 05/10/2026 (Asia/Bangkok)

### 1. Independent audit finding & root cause

Independent audit verdict returned `NEEDS_REMEDIATION` due to a single substantive
performance blocker: `check:task:portable` took ~128–141 seconds (measured ~140.566s in
prior R2 run), materially exceeding the ~90-second task verification budget defined in
`CONSTRAINTS.md`.

Root cause: `package.json`'s `check:task:portable` serialized all eight independent gates
using sequential `&&` chaining. Pytest alone accounted for ~70–75s; running frontend,
architecture, security scanners, and type/lint sequentially pushed total runtime to ~140s.

### 2. Owner-approved scope extension

The owner authorized modifying `.agent/scripts/run-gates.sh` to introduce a generic
parallel task gate mode (`portable-task`), with `.agent/scripts/run-gates.sh` added
to the task allowlist. No unrelated runner refactoring was authorized.

### 3. Architecture & Execution Graph

`check:task:portable` in `package.json` delegates directly to:
`bash .agent/scripts/run-gates.sh portable-task`

Execution DAG:
- **PHASE A (Independent Concurrent Work):**
  - `check-fast-active` (`npm run check:fast:active`)
  - `frontend-coverage` (`npm run test:frontend:coverage`)
  - `portable-pytest` (`npm run test:python:portable`)
  - `security-secrets` (`npm run security:secrets`)
  - `security-code` (`npm run security:code`)
  - `security-deps` (`npm run security:deps`)
  - `architecture` (`npm run architecture:check`)
  All Phase A gates execute concurrently in background subshells.
- **SYNCHRONIZATION & REAPING:**
  `wait_phase` iterates over all launched Phase A PIDs and collects each exit code,
  ensuring no zombie processes or uncollected child processes remain.
- **FAIL-CLOSED PROPAGATION:**
  If ANY Phase A command fails:
  - Runner marks `FAILED=1`;
  - Phase B (`coverage:check`) is NOT launched;
  - All launched processes are reaped;
  - Failure is reported in the gate summary and runner exits with code 1.
- **PHASE B (Dependent Consumer):**
  Only after BOTH coverage producers (`frontend-coverage` and `portable-pytest`) and all
  Phase A gates finish with exit code 0:
  - `coverage-check` (`npm run coverage:check`) runs and validates changed/total coverage against thresholds.

### 4. Behavioral regression tests

Replaced string-locking test with comprehensive behavioral verification in
`tests/orchestrator/test_core.py`:
- `test_portable_task_baseline_retains_all_semantic_gates`: proves all 8 semantic gates are represented in `portable-task`.
- `test_portable_task_runner_success_and_coverage_synchronization`: proves end-to-end success path, all 8 gates PASS, and deterministically validates with timestamps and state markers that `coverage:check` starts strictly after both frontend and Python coverage producers complete.
- `test_portable_task_runner_failure_propagation`: parametrized with `security:code` and `test:python:portable`, proves that Phase A failure stops subsequent phases, suppresses `coverage:check`, reaps processes, and exits with code 1.
- `test_real_t018_preflight_with_normalized_t081`: strengthened to prove exact dependencies `['T015', 'T017', 'T052', 'T081']`, 11 dependency verification commands, and presence of all 4 T081 verification commands.

### 5. Measured warm performance verification

| Check / Metric | Measured Result | Status |
|---|---|---|
| `time npm run check:task:portable` | Exit 0; real **1m19.011s** (**79.011s**), user 9m28.350s, sys 1m24.699s | **PASS** (budget <= 90s) |
| Phase A: `check-fast-active` | PASS (19s) | PASS |
| Phase A: `frontend-coverage` | PASS (17s); 75 passed (5 suites) | PASS |
| Phase A: `portable-pytest` | PASS (79s); 1038 passed in 77.54s (10 xdist workers) | PASS |
| Phase A: `security-secrets` | PASS (20s); 0 findings | PASS |
| Phase A: `security-code` | PASS (14s); 0 findings | PASS |
| Phase A: `security-deps` | PASS (13s); 0 findings | PASS |
| Phase A: `architecture` | PASS (49s); 40 passed (43.91s); 24 modules/31 deps cruised (0 violations); 7 contracts kept/0 broken | PASS |
| Phase B: `coverage-check` | PASS (0s); changed 100.00% (min 80%), total 92.69% (baseline 86.70%) | PASS |
| `python -m pytest tests/orchestrator -q --no-cov` | Exit 0; **296 passed in 174.26s** | PASS |
| `python -m ruff check tools/orchestrator tests/orchestrator` | Exit 0; all checks passed | PASS |
| `python -m ruff format --check tools/orchestrator tests/orchestrator` | Exit 0; 10 files already formatted | PASS |
| `python -m mypy tools/orchestrator` | Exit 0; 6 source files clean | PASS |
| `git diff --check` | Exit 0; clean | PASS |
| `task_card(Path.cwd(), "T018")` | Exit 0; dependencies `['T015', 'T017', 'T052', 'T081']`, 11 verification commands | PASS |
| Native Windows suite on Linux | Expected exit 1; 11 guard failures (fail-closed preserved) | PASS |

Outcome: `REMEDIATION_READY`. Wall time is reduced from 140.566s to 79.011s, fully satisfying
the ~90-second task verification budget in `CONSTRAINTS.md` without weakening or skipping any gates.

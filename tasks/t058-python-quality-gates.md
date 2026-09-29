# T058: Python lint, types, pytest và coverage runner

**Task ID:** `T058`  
**Title:** Python lint, types, pytest và coverage runner  
**Status:** `DONE`  
**Goal:** Thiết lập venv Python checks và test-discovery để backend slices có verification thực.  
**Suggested model:** Gemini  
**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay trong danh sách. Nếu vượt khoảng 2 giờ hoặc phạm vi này, tách task trước khi làm tiếp.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/adr/0001-architecture.md](../docs/adr/0001-architecture.md) backend

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T001](t001-toolchain-repository-skeleton.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

- `pyproject.toml`
- `backend/tests/conftest.py`
- `backend/tests/test_toolchain.py`
- `docs/toolchain.md`

Generated outputs, chỉ tạo bằng generator:

- `requirements.lock`
- `requirements-dev.lock`

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- Ruff/mypy strict project paths, pytest+cov XML config; runner-smoke tests distinct from product correctness. Empty backend/app preT003 may typecheck config/tool tests; document transition strict once app exists. No no-tests pass override. Commands executed from repo root activated locked venv.
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [x] Runner discovers real test and returns nonzero failing assertion/import/unknown collection.
- [x] Ruff/mypy/cov tools pinned via T001 dependency update and pyproject; no suppression.
- [x] Coverage artifact emitted once per suite; typecheck backend/app mandatory once T003 creates it.

## Test cases

1. Temp bad assertion and Python type/lint fixture.
2. Test import/discovery with cwd and locked env clean install.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
python -m pytest backend/tests/test_toolchain.py -q
python -m ruff check backend
python -m mypy backend/tests/test_toolchain.py
```

## Evidence verification (29/09/2026)

1. Negative probes:
   - Failing assertion probe: `python -m pytest` trả về exit code 1 khi có assert fail.
   - Unknown collection probe: `python -m pytest backend/tests/non_existent.py -q` trả về exit code 4.
   - Unsorted imports probe: `python -m ruff check backend` phát hiện vi phạm I001 và trả về exit code 1.
   - Type mismatch probe: `python -m mypy -c "x: int = 'hello'"` phát hiện incompatibile type và trả về exit code 1.

2. Focused commands:
   - `python -m pytest backend/tests/test_toolchain.py -q` -> Exit code 0, 4 passed in 1.48s, sinh ra `coverage.xml` (line-rate 1.0, 31/31 lines).
   - `python -m ruff check backend` -> Exit code 0, All checks passed!
   - `python -m mypy backend/tests/test_toolchain.py` -> Exit code 0, Success: no issues found in 1 source file.
   - `python -m mypy backend` -> Exit code 0, Success: no issues found in 2 source files.
   - `python -m ruff check .` -> Exit code 0, All checks passed!
   - `python -m ruff format --check .` -> Exit code 0, 101 files already formatted.
   - `python -m pytest` -> Exit code 0, 4 passed in 1.30s, coverage.xml written.

3. Zero suppressions: không dùng bất kỳ `# noqa`, `# type: ignore` nào.

## Expected output

- Runner discovers real test and returns nonzero failing assertion/import/unknown collection.
- Focused commands đạt kết quả/exit code ghi trong criteria; negative probe phải fail đúng reason. Documentation tasks có conformance report thay cho application-test pass.
- Evidence ghi command, exit code, môi trường và artifact. Thiếu Windows/browser/provider environment là PENDING; không hoàn tất gate thiếu evidence.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Risk

- **Level:** `Medium`.
- Sai wiring/tooling có thể khiến task sau dùng command hoặc UI state không chính xác.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- Empty suite/tolerance/suppression needed to fake green → dừng.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`chore(T058): python lint, types, pytest và coverage runner`

# T003: FastAPI app factory và health

**Task ID:** `T003`  
**Title:** FastAPI app factory và health  
**Status:** `DONE`  
**Goal:** FastAPI app factory và health. GET /api/v1/health có typed readiness/version no-store; factory có thể test.  
**Suggested model:** Gemini  
**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay trong danh sách. Nếu vượt khoảng 2 giờ hoặc phạm vi này, tách task trước khi làm tiếp.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/api-contract.md](../docs/api-contract.md) §2–4
- [docs/security-review.md](../docs/security-review.md) T-01

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T002](t002-quality-gates-test-runner-build.md)
- [T058](t058-python-quality-gates.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

- `backend/app/main.py`
- `backend/app/http/health.py`
- `backend/app/platform/config.py`
- `backend/tests/test_health.py`

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- Health factory độc lập bridge; bind loopback; runtime chưa có DB phải NOT_READY trung thực. T006 thêm session guard; chưa distribute shell unguarded.
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [x] GET /api/v1/health có typed readiness/version no-store; factory có thể test.
- [x] Loopback-only; health không inference, không đọc credential; missing storage NOT_READY.
- [x] ASGI startup/shutdown chạy; tests và Python typecheck không lỗi.

## Test cases

1. Loopback healthy fixture, invalid bind, missing storage.
2. Count bridge calls = 0.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
python -m pytest backend/tests/test_health.py -q
python -m mypy backend/app
python -m mypy backend
python -m ruff check .
python -m ruff format --check .
python -m pytest
```

## Verification evidence

- `python -m pytest backend/tests/test_health.py -q`: 8 passed in 1.10s, 100% coverage on `backend/app`.
- `python -m mypy backend/app`: Success: no issues found in 3 source files.
- `python -m mypy backend`: Success: no issues found in 7 source files.
- `python -m ruff check .`: All checks passed!
- `python -m ruff format --check .`: 106 files already formatted.
- `python -m pytest`: 12 passed in 1.93s, 100% overall coverage across all backend modules, `coverage.xml` emitted.

## Expected output

- GET /api/v1/health có typed readiness/version no-store; factory có thể test.
- Focused commands đạt kết quả/exit code ghi trong criteria; negative probe phải fail đúng reason. Documentation tasks có conformance report thay cho application-test pass.
- Evidence ghi command, exit code, môi trường và artifact. Thiếu Windows/browser/provider environment là PENDING; không hoàn tất gate thiếu evidence.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Risk

- **Level:** `Medium`.
- Sai wiring/tooling có thể khiến task sau dùng command hoặc UI state không chính xác.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- Muốn LAN hoặc public unauthenticated API → dừng.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`feat(T003): fastapi app factory và health`

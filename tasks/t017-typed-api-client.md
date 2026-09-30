# T017: Generated DTO và typed fetch client

**Task ID:** `T017`  
**Title:** Generated DTO và typed fetch client  
**Status:** `TODO`  
**Goal:** Generated DTO và typed fetch client. Generation reproducible no timestamp churn; contract diff phát hiện breaking shape.  
**Suggested model:** Gemini  
**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay trong danh sách. Nếu vượt khoảng 2 giờ hoặc phạm vi này, tách task trước khi làm tiếp.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/api-contract.md](../docs/api-contract.md) §3/5/9
- [docs/ui-architecture.md](../docs/ui-architecture.md) §4/9

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T006](t006-api-core-contract-foundation.md)
- [T014](t014-operations-idempotency.md)
- [T002](t002-quality-gates-test-runner-build.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

- `frontend/src/shared/api/client.ts`
- `frontend/src/shared/api/client.test.ts`
- `scripts/export_contract.py`
- `scripts/tests/test_contract.py`
- `package.json`

Generated outputs, chỉ tạo bằng generator:

- `contracts/openapi.json`
- `frontend/src/shared/api/generated.ts`
- `package-lock.json`

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- Tạo npm test:contract/export:contract wrappers; generated schema/TS ở contracts/openapi.json và frontend/src/shared/api/generated.ts là deterministic outputs. Abort đọc; mutation giữ intent để reconcile. Subsequent endpoint tasks regenerate artifacts with export:contract; tests pin full schema not fake examples.
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [x] Generation reproducible no timestamp churn; contract diff phát hiện breaking shape.
- [x] Client maps error union, requestId, opaque ETag; browser session credentials same-origin.
- [x] No bridge URL/key/path exposed; network/unknown mutation not converted success.

## Test cases

1. Good JSON vs non-JSON500; malformed error; abort after server commit.
2. Generate twice + compare; required nullable fields remain.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
npm run export:contract
npm run test:contract
npm run test:frontend -- frontend/src/shared/api/client.test.ts
```

## Expected output

- Generation reproducible no timestamp churn; contract diff phát hiện breaking shape.
- Focused commands đạt kết quả/exit code ghi trong criteria; negative probe phải fail đúng reason. Documentation tasks có conformance report thay cho application-test pass.
- Evidence ghi command, exit code, môi trường và artifact. Thiếu Windows/browser/provider environment là PENDING; không hoàn tất gate thiếu evidence.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Risk

- **Level:** `Medium`.
- Sai wiring/tooling có thể khiến task sau dùng command hoặc UI state không chính xác.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- Cần hand-written duplicate DTO hoặc shape chưa T013 freeze → dừng.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`feat(T017): generated dto và typed fetch client`

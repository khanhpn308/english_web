# T010: Typed UI recovery cho common error codes

**Task ID:** `T010`  
**Title:** Typed UI recovery cho common error codes  
**Status:** `TODO`  
**Goal:** Typed UI recovery cho common error codes. Mọi common code có exhaustive mapping và requestId an toàn.  
**Suggested model:** Gemini  
**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay trong danh sách. Nếu vượt khoảng 2 giờ hoặc phạm vi này, tách task trước khi làm tiếp.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/api-contract.md](../docs/api-contract.md) §5/8
- [docs/ui-architecture.md](../docs/ui-architecture.md) §5/9 & Canonical design system (shadcn/ui)

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T009](t009-lookup-ui-vertical-slice.md)
- [T052](t052-browser-test-harness.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

- `frontend/src/shared/api/errors.ts`
- `frontend/src/shared/errors/RecoveryPanel.tsx`
- `frontend/src/shared/errors/RecoveryPanel.test.tsx`
- `frontend/tests/e2e/error-recovery.spec.ts`

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- Backend envelope T006; task chỉ UI mapping và unknown-operation reconciliation. Retry mutation qua same intent/operation theo contract; không arbitrary auto-resubmit.
- UI recovery components (`RecoveryPanel`) kế thừa nền tảng design system từ T076 (qua T009), sử dụng canonical primitives và semantic error tokens đã chuẩn hóa.
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [ ] Mọi common code có exhaustive mapping và requestId an toàn.
- [ ] API stopped/bridge unavailable/consent/session/storage/conflict phân biệt; draft không mất.
- [ ] Unknown outcome không báo success hoặc tự tạo intent mới.

## Test cases

1. Table-driven every error code, all details union branches.
2. Abort-after-commit → GET operation; rebootstrap failure preserves draft.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
npm run test:frontend -- frontend/src/shared/errors/RecoveryPanel.test.tsx
npm run test:e2e -- frontend/tests/e2e/error-recovery.spec.ts
```

## Expected output

- Mọi common code có exhaustive mapping và requestId an toàn.
- Focused commands đạt kết quả/exit code ghi trong criteria; negative probe phải fail đúng reason. Documentation tasks có conformance report thay cho application-test pass.
- Evidence ghi command, exit code, môi trường và artifact. Thiếu Windows/browser/provider environment là PENDING; không hoàn tất gate thiếu evidence.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Risk

- **Level:** `High`.
- Sai contract/concurrency/persistence có thể làm mất dữ liệu, ghi sai tiến độ hoặc tạo kết luận kiểm chứng sai.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- Recovery cần bỏ Origin guard hoặc xóa DB → dừng.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`feat(T010): typed ui recovery cho common error codes`

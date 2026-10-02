# T025: Save lookup preview và local pronunciation

**Task ID:** `T025`  
**Title:** Save lookup preview và local pronunciation  
**Status:** `TODO`  
**Goal:** Save lookup preview và local pronunciation. Save success only after durable receipt; duplicate click/reload reconciles and invalidates local queries.  
**Suggested model:** Gemini  
**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay trong danh sách. Nếu vượt khoảng 2 giờ hoặc phạm vi này, tách task trước khi làm tiếp.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/ui-architecture.md](../docs/ui-architecture.md) J2 & Canonical design system (shadcn/ui)
- [docs/spec.md](../docs/spec.md) AC-04/11/25/33

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T009](t009-lookup-ui-vertical-slice.md)
- [T024](t024-save-api.md)
- [T052](t052-browser-test-harness.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

- `frontend/src/features/lookup/SavePreview.tsx`
- `frontend/src/features/lookup/AudioButton.tsx`
- `frontend/src/features/lookup/LookupPage.tsx`
- `frontend/src/features/lookup/save.test.tsx`
- `frontend/tests/e2e/lookup-save.spec.ts`

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- All forms, explicit date; show operation/sync confirmed status. Audio choose ONLY voice.localService=true and en-US; no generic remote/default voice fallback. Client signal not proof, offline/native voice verification T044.
- Thiết kế component theo design system: `SavePreview` và `AudioButton` sử dụng canonical primitives (`Button`, `Card`, `Badge`...) từ `frontend/src/components/ui/` và semantic tokens kế thừa từ T076 (qua T009).
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [ ] Save success only after durable receipt; duplicate click/reload reconciles and invalidates local queries.
- [ ] New-day save and card reuse/reset notices reflect API; conflict preserves preview.
- [ ] Audio available local-US voice or disabled reason; no app/provider fetch or mic.

## Test cases

1. AC-04/11/33 with real API fake upstream.
2. Local vs remote vs no voice; repeated play bounded/cancelled; keyboard.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
npm run test:frontend -- frontend/src/features/lookup/save.test.tsx
npm run test:e2e -- frontend/tests/e2e/lookup-save.spec.ts
```

## Expected output

- Save success only after durable receipt; duplicate click/reload reconciles and invalidates local queries.
- Focused commands đạt kết quả/exit code ghi trong criteria; negative probe phải fail đúng reason. Documentation tasks có conformance report thay cho application-test pass.
- Evidence ghi command, exit code, môi trường và artifact. Thiếu Windows/browser/provider environment là PENDING; không hoàn tất gate thiếu evidence.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Risk

- **Level:** `Medium`.
- Sai wiring/tooling có thể khiến task sau dùng command hoặc UI state không chính xác.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- Speech voice not positively local → disabled, not network fallback.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`feat(T025): save lookup preview và local pronunciation`

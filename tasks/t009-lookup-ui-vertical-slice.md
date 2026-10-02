# T009: Lookup UI gọi API thật qua client

**Task ID:** `T009`  
**Title:** Lookup UI gọi API thật qua client  
**Status:** `TODO`  
**Goal:** Lookup UI gọi API thật qua client. Grant/decline giữ term, không tự submit; fresh click mới gọi POST.  
**Suggested model:** Gemini  
**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay trong danh sách. Nếu vượt khoảng 2 giờ hoặc phạm vi này, tách task trước khi làm tiếp.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/ui-architecture.md](../docs/ui-architecture.md) J2/J7 & Canonical design system (shadcn/ui)
- [docs/spec.md](../docs/spec.md) AC-02/03/05/32/33

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T076](t076-app-shell-shadcn-migration.md)
- [T008](t008-lookup-api-vertical-slice.md)
- [T017](t017-typed-api-client.md)
- [T018](t018-consent-ui.md)
- [T052](t052-browser-test-harness.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

- `frontend/src/features/lookup/LookupPage.tsx`
- `frontend/src/features/lookup/LookupResult.tsx`
- `frontend/src/features/lookup/LookupPage.test.tsx`
- `frontend/tests/e2e/lookup.spec.ts`
- `frontend/src/app/AppShell.tsx`

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- Tích hợp consent UI từ T018; lookup preview-only, save chưa triển khai phải rõ; audio T025. Fixture/mock dùng generated types. Count network calls, không chỉ snapshot UI. Đăng ký flow vào route thật, không chỉ render isolated component; build và harness dùng cùng router.
- Thiết kế component theo design system: Sử dụng canonical primitives từ `frontend/src/components/ui/` (Button, Card, Input...) và semantic tokens từ T075/T076; không duplicate primitives.
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [ ] Grant/decline giữ term, không tự submit; fresh click mới gọi POST.
- [ ] Loading/empty/error/success đủ, unverified/missing label, safe text links.
- [ ] Keyboard focus và retry terminal dùng key mới khi người dùng yêu cầu.

## Test cases

1. Consent 0 calls until fresh action; validation and hostile HTML.
2. Successful real local API with fake upstream; no card persistence.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
npm run test:frontend -- frontend/src/features/lookup/LookupPage.test.tsx
npm run test:e2e -- frontend/tests/e2e/lookup.spec.ts
npm run build
```

## Expected output

- Grant/decline giữ term, không tự submit; fresh click mới gọi POST.
- Focused commands đạt kết quả/exit code ghi trong criteria; negative probe phải fail đúng reason. Documentation tasks có conformance report thay cho application-test pass.
- Evidence ghi command, exit code, môi trường và artifact. Thiếu Windows/browser/provider environment là PENDING; không hoàn tất gate thiếu evidence.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Risk

- **Level:** `Medium`.
- Sai wiring/tooling có thể khiến task sau dùng command hoặc UI state không chính xác.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- Proxy key/URL được đưa xuống frontend → dừng.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`feat(T009): lookup ui gọi api thật qua client`

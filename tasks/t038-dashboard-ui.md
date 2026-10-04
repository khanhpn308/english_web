# T038: Learning Dashboard UI

**Task ID:** `T038`  
**Title:** Learning Dashboard UI  
**Status:** `TODO`  
**Goal:** Learning Dashboard UI. Due/streak/three learning result groups có label và null-not-zero.  
**Suggested model:** Gemini  
**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay trong danh sách. Nếu vượt khoảng 2 giờ hoặc phạm vi này, tách task trước khi làm tiếp.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/ui-architecture.md](../docs/ui-architecture.md) J1/status/§5 & Canonical design system (shadcn/ui)
- [docs/spec.md](../docs/spec.md) AC-20–23/32

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T081](t081-app-shell-shadcn-migration.md)
- [T037](t037-dashboard-formulas.md)
- [T017](t017-typed-api-client.md)
- [T010](t010-error-handling-recovery.md)
- [T052](t052-browser-test-harness.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

- `frontend/src/features/dashboard/DashboardPage.tsx`
- `frontend/src/features/dashboard/DashboardPage.test.tsx`
- `frontend/tests/e2e/dashboard.spec.ts`
- `frontend/src/app/AppShell.tsx`

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- Chỉ learning dashboard; status panel T060. Panel loading/empty/errors, three groups separate; due/streak invalidation sau review/quiz/sync. SYNCING không false empty/current. Đăng ký flow vào route thật, không chỉ render isolated component; build và harness dùng cùng router.
- Thiết kế component theo design system: `DashboardPage` và các cards/panels sử dụng canonical primitives (`Card`, `Button`, `Badge`...) từ `frontend/src/components/ui/` và semantic tokens từ T081; không duplicate primitives.
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [ ] Due/streak/three learning result groups có label và null-not-zero.
- [ ] Panel errors/retry không xóa dữ liệu panel khác; offline local API reads.
- [ ] Keyboard/long Vietnamese/responsive and invalidation reflected.

## Test cases

1. No-history/0 due; DEGRADED; bridge down but revoke available.
2. Focus after mutation, offline local API healthy, API stopped fallback link.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
npm run test:frontend -- frontend/src/features/dashboard/DashboardPage.test.tsx
npm run test:e2e -- frontend/tests/e2e/dashboard.spec.ts
```

## Expected output

- Due/streak/three learning result groups có label và null-not-zero.
- Focused commands đạt kết quả/exit code ghi trong criteria; negative probe phải fail đúng reason. Documentation tasks có conformance report thay cho application-test pass.
- Evidence ghi command, exit code, môi trường và artifact. Thiếu Windows/browser/provider environment là PENDING; không hoàn tất gate thiếu evidence.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Risk

- **Level:** `Medium`.
- Sai wiring/tooling có thể khiến task sau dùng command hoặc UI state không chính xác.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- Dashboard reads raw DB or claims real cloud quota/security → dừng.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`feat(T038): learning dashboard ui`

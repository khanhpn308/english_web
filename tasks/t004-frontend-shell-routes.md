# T004: React shell, route map và landmarks

**Task ID:** `T004`  
**Title:** React shell, route map và landmarks  
**Status:** `DONE`  
**Goal:** React shell, route map và landmarks. Mọi route v1 có shell/landmarks/skip link và current-nav state.  
**Suggested model:** Gemini  
**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay trong danh sách. Nếu vượt khoảng 2 giờ hoặc phạm vi này, tách task trước khi làm tiếp.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/ui-architecture.md](../docs/ui-architecture.md) §1–2, §6–7

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T003](t003-backend-skeleton.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

- `frontend/index.html`
- `frontend/src/main.tsx`
- `frontend/src/app/AppShell.tsx`
- `frontend/src/app/shell.css`
- `frontend/src/app/AppShell.test.tsx`
- Cấu hình mở rộng được chấp thuận: `vite.config.ts`, `tsconfig.json`

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- Dùng minimal router, chưa business state store. Routes chưa triển khai hiển thị unavailable rõ, không fabricated data. T043/T053 mới full journey/a11y; ở đây keyboard/focus component tests.
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [x] Mọi route v1 có shell/landmarks/skip link và current-nav state.
- [x] Tab/Enter/Space, heading focus, 200% zoom không giấu control.
- [x] Static build chạy; không credential/bridge configuration trong bundle.

## Test cases

1. Deep-link route, back/forward; keyboard nav.
2. Long Vietnamese labels và error boundary fixture.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
npm run test:frontend -- frontend/src/app/AppShell.test.tsx
npm run typecheck
npm run build
```

## Verification results & Evidence

- `npm run test:frontend -- frontend/src/app/AppShell.test.tsx`: Exit code 0 (17/17 tests passed in 337ms).
  - Khẳng định đầy đủ landmarks: `<header>`, `<nav aria-label="Điều hướng chính">`, `<main id="main-content">`, `<a href="#main-content">` (skip link).
  - Khẳng định `aria-current="page"` tại nav link đang active của mọi màn hình v1.
  - Khẳng định link truy cập nhanh quyền chia sẻ AI tại shell: `href="/status#ai-consent"`.
  - Khẳng định 9 routes chuẩn hóa theo docs/ui-architecture.md §1: `/`, `/lookup`, `/search`, `/word-forms/:wordFormId`, `/review`, `/quiz/new`, `/quiz/:attemptId`, `/quiz/:attemptId/result`, `/status`.
  - Khẳng định màn hình 404 cho route không hợp lệ và nút quay lại trang chủ.
  - Khẳng định hiển thị trạng thái chưa khả dụng không giả lập dữ liệu cho routes v1 chưa có logic nghiệp vụ.
  - Khẳng định trích xuất tham số dynamic route (`wordFormId`, `attemptId`).
  - Khẳng định ErrorBoundary phục hồi giao diện khi render lỗi và cung cấp liên kết sang `/status`.
- `npm run test:frontend`: Exit code 0 (21/21 tests passed trong cả 2 test suites `toolchain.test.ts` và `AppShell.test.tsx`).
- `npm run typecheck`: Exit code 0 (TypeScript strict mode, 0 errors trên toàn bộ `frontend/src` và test files).
- `npm run lint`: Exit code 0 (0 ESLint errors).
- `npm run build`: Exit code 0 (`vite build` hoàn thành tĩnh đóng gói vào `frontend/dist/` trong 200ms).
- Kiểm tra bảo mật bundle: Scan regex phát hiện 0 credentials, 0 bridge tokens, 0 proxy key trong `frontend/dist/assets/*.js`.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Risk

- **Level:** `Medium`.
- Sai wiring/tooling có thể khiến task sau dùng command hoặc UI state không chính xác.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- Cần general settings/account hoặc business flow ngoài shell → dừng.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`feat(T004): react shell, route map và landmarks`

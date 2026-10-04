# T081: AppShell shadcn/ui & semantic design-system migration

**Task ID:** `T081`
**Title:** AppShell shadcn/ui & semantic design-system migration  
**Status:** `DONE`
**Goal:** Migrate the visual and component styling of the existing AppShell to the canonical shadcn/Tailwind design system established in T080, while preserving 100% of T004 routing, landmark, accessibility, and navigation behaviors.

**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay (`frontend/src/app/AppShell.tsx`, `frontend/src/app/shell.css`, `frontend/src/app/AppShell.test.tsx`, `frontend/tests/e2e/shell.spec.ts`, và common bookkeeping).  
**Suggested model:** Gemini  

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/ui-architecture.md](../docs/ui-architecture.md) §1–2, §6–7 & Canonical design system
- [tasks/t004-frontend-shell-routes.md](t004-frontend-shell-routes.md)
- [tasks/t080-shadcn-ui-foundation.md](t080-shadcn-ui-foundation.md)
- Source & tests hiện tại: `frontend/src/app/AppShell.tsx`, `frontend/src/app/shell.css`, `frontend/src/app/AppShell.test.tsx`

## Dependencies

- [T004](t004-frontend-shell-routes.md)
- [T080](t080-shadcn-ui-foundation.md)

Cả hai dependencies phải có evidence hoàn tất trước khi triển khai task này.

## Files được phép sửa

- `frontend/src/app/AppShell.tsx`
- `frontend/src/app/shell.css`
- `frontend/src/app/AppShell.test.tsx`
- `frontend/tests/e2e/shell.spec.ts`
- Scope extension ủy quyền riêng cho coverage gate: `package.json`, `package-lock.json` (thêm test-only devDependency `jsdom`).
- Common bookkeeping: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md).

## Files không được sửa

- `frontend/src/shared/api/*` (API client/DTO)
- Feature UI code: `frontend/src/features/*` (không triển khai feature code hay business logic của Consent, Lookup, Search, Review, Quiz, Dashboard, Status)
- Primitives cơ sở: `frontend/src/components/ui/*` (trừ khi cần tinh chỉnh nhỏ đã được xác thực trong T080)
- Backend code: `backend/*`
- Contracts: `contracts/*`
- Router & state libraries (không thêm external router như react-router hay external state store như Redux/Zustand)

## Implementation notes

1. **Bảo toàn bất biến T004 (Invariants to preserve):**
   - Mọi định nghĩa route v1: `/`, `/lookup`, `/search`, `/word-forms/:wordFormId`, `/review`, `/quiz/new`, `/quiz/:attemptId`, `/quiz/:attemptId/result`, `/status`.
   - Cơ chế route matching nội bộ, trích xuất route params (`wordFormId`, `attemptId`).
   - Xử lý deep-link, back/forward qua `popstate` event.
   - Cấu trúc semantic landmarks: `<header role="banner">`, `<nav aria-label="Điều hướng chính" role="navigation">`, `<main id="main-content" role="main">`.
   - Skip link dễ tiếp cận: `<a href="#main-content" className="skip-link ...">Chuyển đến nội dung chính</a>`.
   - Thuộc tính `aria-current="page"` trên nav item đang active.
   - Điều hướng bàn phím (Tab, Enter, Space).
   - Chuyển focus về thẻ `h1` của màn hình sau khi chuyển trang (`requestAnimationFrame(() => heading.focus())`).
   - ErrorBoundary: hiển thị panel lỗi có khả năng phục hồi, bảo toàn `h2` heading semantics bên trong CardTitle, nút "Thử lại màn hình này" và link kiểm tra trạng thái `/status`.
   - Xử lý route 404: tiêu đề, mô tả và nút quay về trang chủ.
   - Trạng thái placeholder không giả lập dữ liệu: thông báo tính năng chưa khả dụng rõ ràng cho các route chưa nạp dữ liệu.
   - Liên kết nhanh `/status#ai-consent` trong header: bảo toàn thuộc tính markup `href="/status#ai-consent"` trong khi cơ chế điều hướng client-side chuyển tới màn hình `/status`.
2. **Những thay đổi đã thực hiện:**
   - Thay thế các visual primitives cũ (nút bấm, card) bằng canonical primitives từ `frontend/src/components/ui/` (`Button`, `Card` từ shadcn gồm `CardHeader`, `CardTitle`, `CardContent`, `CardFooter`; không sử dụng `CardDescription` do AppShell không dùng tới).
   - Chuyển đổi các custom CSS tokens trong `shell.css` sang semantic Tailwind classes và design-system tokens đã thiết lập ở T080.
   - Khôi phục reset document cơ bản (`box-sizing: border-box`, `body { margin: 0; padding: 0; ... }`) trong `shell.css`.
   - Bổ sung `frontend/tests/e2e/shell.spec.ts` kiểm thử toàn diện E2E trên 4 viewports (320, 768, 1024, 1440): kiểm thử mounted ErrorBoundary fixture phục hồi thực sự khi người dùng click, kích hoạt brand link về trang chủ và focus h1, kích hoạt nút quay lại trang chủ ở 404 và focus h1.
   - Kiểm thử reflow ở độ phân giải tương đương 200% zoom (viewport 640px) xác nhận văn bản và nút tiếng Việt co giãn không tràn ngang, các controls điều hướng và phục hồi khả dụng và có thể nhận focus bàn phím; giữ nguyên kiểm thử 320px; kiểm tra chẩn đoán độ phóng đại visual viewport bằng CDP `Emulation.setPageScaleFactor` (2.0) với thuật ngữ chính xác.
   - Tối ưu nút bấm co giãn (`whitespace-normal h-auto py-2`) tránh tràn ngang trên màn hình hẹp 320px.
   - Bổ sung ủy quyền kiểm thử độ phủ (Coverage Scope Extension): Thêm devDependency `jsdom` (test-only) và môi trường Vitest per-file (`// @vitest-environment jsdom`) trong `AppShell.test.tsx`. Bổ sung 2 test mounted React DOM thực tế với `createRoot` và sự kiện click DOM để bao phủ line 270 (brand navigation) và line 346 (404 recovery action), nâng độ phủ code thay đổi lên 100% (3/3 lines). Mã nguồn production (`AppShell.tsx`, `shell.css`) được giữ nguyên byte-identical.
3. **Những điều TUYỆT ĐỐI KHÔNG làm:**
   - Không thêm business logic hoặc mock data nghiệp vụ.
   - Không triển khai flow chia sẻ AI / Consent (thuộc T018).
   - Không triển khai các màn hình nghiệp vụ (Lookup, Search, Review, Quiz, Dashboard, Status).
   - Không thay đổi API contract hoặc backend.
   - Không thay thế router nội bộ bằng thư viện router bên ngoài.
   - Không đưa vào thư viện state management toàn cục.

## Acceptance criteria

- [x] Toàn bộ 27 bài test trong `frontend/src/app/AppShell.test.tsx` PASS, chứng minh sự tương đương hành vi (behavioral equivalence) hoàn toàn với T004 và bao phủ tương tác DOM thực tế cho brand navigation (line 270) và 404 recovery (line 346).
- [x] Giao diện AppShell được migrate sang sử dụng canonical shadcn/Tailwind design system và semantic tokens.
- [x] Không làm suy giảm hoặc phá vỡ các hợp đồng accessibility: skip link hoạt động, `aria-current` đúng vị trí, landmarks đầy đủ, focus landing trên `h1` sau navigation.
- [x] Màn hình 404, ErrorBoundary và trạng thái tính năng chưa khả dụng giữ nguyên thông điệp và không có dữ liệu giả lập.
- [x] Toàn bộ quality gates trong phạm vi task và môi trường đều PASS: `check:fast`, `typecheck`, `lint`, `architecture:frontend`, `build`, `test:frontend` (75 passed across 5 suites), `test:e2e` (48 passed across 4 viewports on shell.spec.ts), `test:a11y` (8 passed), `architecture:check` (40 passed, 7 contracts kept), authoritative coverage gate (`coverage:check` changed 100.00% >= 80.00%, total 93.40%), `security:secrets` (0 findings), `security:code` (0 findings), `security:deps` (0 findings). (11 tests Windows-native trong `check:task` fail-closed trung thực do chạy trên Linux, được ghi nhận là INHERITED_BASELINE_FAILURE từ T021).

## Test cases

1. **Behavioral equivalence & mounted interaction tests:** Chạy toàn bộ test suite `AppShell.test.tsx` (27/27 PASS) bao gồm kiểm tra landmarks, routing, active navigation, 404 view, ErrorBoundary, và 2 mounted DOM interaction tests (chạy trong môi trường jsdom per-file) kích hoạt brand link và 404 recovery action với real DOM events và kiểm tra heading focus, không dùng direct callback invocation.
2. **Design system integration test:** Kiểm tra AppShell import và render chính xác các canonical primitives từ `@/components/ui/` mà không gây circular dependencies (`design-system.test.tsx`: 27/27 PASS).
3. **Accessibility verification:** Kiểm tra skip link, live region thông báo chuyển trang, focus indicator trên các controls chuyển trang, và scan `@a11y` qua axe-core (`test:a11y`: 8/8 PASS, zero critical/serious violations).
4. **E2E & Responsive Reflow:** `frontend/tests/e2e/shell.spec.ts` kiểm thử 48 test cases qua 4 viewports (320, 768, 1024, 1440), kiểm thử mounted ErrorBoundary fixture phục hồi thực tế, và 200% effective layout equivalent reflow ở 640px (48/48 PASS). Playwright vẫn là oracle E2E trên trình duyệt thật Chromium; Vitest/jsdom tồn tại để cung cấp instrumented component coverage cho cổng LCOV của repository.

## Verification commands & Snapshot results

```text
npm run test:frontend -- frontend/src/app/AppShell.test.tsx  # Exit 0, 27 passed
npm run test:frontend -- frontend/tests/design-system.test.tsx # Exit 0, 27 passed
npm run test:frontend                                      # Exit 0, 75 passed (5 suites)
npm run typecheck                                          # Exit 0
npm run lint                                               # Exit 0 (0 errors, 3 fast-refresh warnings)
npm run architecture:frontend                              # Exit 0 (24 modules, 31 dependencies cruised)
npm run architecture:check                                 # Exit 0 (7 contracts kept, 40 tests passed)
npm run build                                              # Exit 0 (built in ~250ms)
QUALITY_BASE_REF="035430d668f1f754afd38e3cca9d630eb90a69a7" npm run coverage:check # Exit 0, changed 100.00%, total 93.40%
npm run test:e2e -- frontend/tests/e2e/shell.spec.ts --workers=1 # Exit 0, 48 passed (4 viewports x 12 tests)
npm run test:a11y -- --workers=1                           # Exit 0, 8 passed
npm run security:secrets                                   # Exit 0 (0 finding)
npm run security:code                                      # Exit 0 (0 finding)
npm run security:deps                                      # Exit 0 (0 finding)
npm run check:fast                                         # Exit 0 (format, lint, typecheck, floor, secrets clean)
git diff --check                                           # Exit 0
```

## Task Execution State & Failure Classification

- **Trạng thái:** `COMPLETED` (Verified Task Snapshot sẵn sàng cho tích hợp / audit; CP06A vẫn giữ nguyên `[ ]`).
- **Phân loại kết quả kiểm thử:**
  - `TASK_REGRESSION`: 0 (không có hồi quy).
  - `INHERITED_BASELINE_FAILURE`: 11 tests Windows-native trong `backend/tests/windows/test_source_paths.py` fail-closed trung thực `_require_native_windows()` do host là Linux (kế thừa từ T021).
  - `ENVIRONMENT_BLOCKED`: Không có (Chromium headless chạy đầy đủ trong môi trường này, E2E và A11y tests đều pass).

## Risk

- **Level:** `Medium`.
- Thay đổi class CSS hoặc thẻ bọc khi tích hợp shadcn primitive có thể làm lệch selector của skip-link, focus indicator, hoặc live-region.
- Mitigation: Bảo toàn cấu trúc HTML semantic của landmarks và test kỹ bằng các assertion kiểm tra role, text content, và focus target.

## Stop conditions

- Bị mất hoặc thay đổi bất kỳ hành vi routing/landmark/accessibility nào đã được kiểm chứng bởi T004 → DỪNG.
- Yêu cầu bổ sung thư viện router hoặc state library ngoài phạm vi → DỪNG.
- Có ý định đưa business logic hoặc mock data vào shell → DỪNG.

## Commit message đề xuất

`refactor(T081): migrate app shell visual styling to shadcn design system`

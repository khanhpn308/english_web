# T076: AppShell shadcn/ui & semantic design-system migration

**Task ID:** `T076`  
**Title:** AppShell shadcn/ui & semantic design-system migration  
**Status:** `TODO`  
**Goal:** Migrate the visual and component styling of the existing AppShell to the canonical shadcn/Tailwind design system established in T075, while preserving 100% of T004 routing, landmark, accessibility, and navigation behaviors.  

**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay (`frontend/src/app/AppShell.tsx`, `frontend/src/app/shell.css`, `frontend/src/app/AppShell.test.tsx`, `frontend/tests/e2e/shell.spec.ts`, và common bookkeeping).  
**Suggested model:** Gemini  

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/ui-architecture.md](../docs/ui-architecture.md) §1–2, §6–7 & Canonical design system
- [tasks/t004-frontend-shell-routes.md](t004-frontend-shell-routes.md)
- [tasks/t075-shadcn-ui-foundation.md](t075-shadcn-ui-foundation.md)
- Source & tests hiện tại: `frontend/src/app/AppShell.tsx`, `frontend/src/app/shell.css`, `frontend/src/app/AppShell.test.tsx`

## Dependencies

- [T004](t004-frontend-shell-routes.md)
- [T075](t075-shadcn-ui-foundation.md)

Cả hai dependencies phải có evidence hoàn tất trước khi triển khai T076.

## Files được phép sửa

- `frontend/src/app/AppShell.tsx`
- `frontend/src/app/shell.css`
- `frontend/src/app/AppShell.test.tsx`
- `frontend/tests/e2e/shell.spec.ts`
- Common bookkeeping: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md).

## Files không được sửa

- `frontend/src/shared/api/*` (API client/DTO)
- Feature UI code: `frontend/src/features/*` (không triển khai feature code hay business logic của Consent, Lookup, Search, Review, Quiz, Dashboard, Status)
- Primitives cơ sở: `frontend/src/components/ui/*` (trừ khi cần tinh chỉnh nhỏ đã được xác thực trong T075)
- Backend code: `backend/*`
- Contracts: `contracts/*`
- Router & state libraries (không thêm external router như react-router hay external state store như Redux/Zustand)

## Implementation notes

1. **Bảo toàn bất biến T004 (Invariants to preserve):**
   - Mọi định nghĩa route v1: `/`, `/lookup`, `/search`, `/word-forms/:wordFormId`, `/review`, `/quiz/new`, `/quiz/:attemptId`, `/quiz/:attemptId/result`, `/status`.
   - Cơ chế route matching nội bộ, trích xuất route params (`wordFormId`, `attemptId`).
   - Xử lý deep-link, back/forward qua `popstate` event.
   - Cấu trúc semantic landmarks: `<header role="banner">`, `<nav aria-label="Điều hướng chính" role="navigation">`, `<main id="main-content" role="main">`.
   - Skip link dễ tiếp cận: `<a href="#main-content" className="skip-link">Chuyển đến nội dung chính</a>`.
   - Thuộc tính `aria-current="page"` trên nav item đang active.
   - Điều hướng bàn phím (Tab, Enter, Space).
   - Chuyển focus về thẻ `h1` của màn hình sau khi chuyển trang (`requestAnimationFrame(() => heading.focus())`).
   - ErrorBoundary: hiển thị panel lỗi có khả năng phục hồi, nút "Thử lại màn hình này" và link kiểm tra trạng thái `/status`.
   - Xử lý route 404: tiêu đề, mô tả và nút quay về trang chủ.
   - Trạng thái placeholder không giả lập dữ liệu: thông báo tính năng chưa khả dụng rõ ràng cho các route chưa nạp dữ liệu.
   - Liên kết nhanh `/status#ai-consent` trong header.
2. **Những thay đổi được phép thực hiện:**
   - Thay thế các visual primitives cũ (nút bấm, card) bằng canonical primitives từ `frontend/src/components/ui/` (ví dụ `Button`, `Card` từ shadcn).
   - Chuyển đổi các custom CSS tokens trong `shell.css` sang semantic Tailwind classes và design-system tokens đã thiết lập ở T075.
   - Đơn giản hóa `shell.css` khi các layout utility đã được Tailwind đảm nhiệm, giữ nguyên hành vi hiển thị và accessibility.
3. **Những điều TUYỆT ĐỐI KHÔNG làm:**
   - Không thêm business logic hoặc mock data nghiệp vụ.
   - Không triển khai flow chia sẻ AI / Consent (thuộc T018).
   - Không triển khai các màn hình nghiệp vụ (Lookup, Search, Review, Quiz, Dashboard, Status).
   - Không thay đổi API contract hoặc backend.
   - Không thay thế router nội bộ bằng thư viện router bên ngoài.
   - Không đưa vào thư viện state management toàn cục.

## Acceptance criteria

- [ ] Toàn bộ 17+ bài test hiện có trong `frontend/src/app/AppShell.test.tsx` tiếp tục PASS, chứng minh sự tương đương hành vi (behavioral equivalence) hoàn toàn với T004.
- [ ] Giao diện AppShell được migrate sang sử dụng canonical shadcn/Tailwind design system và semantic tokens.
- [ ] Không làm suy giảm hoặc phá vỡ các hợp đồng accessibility: skip link hoạt động, `aria-current` đúng vị trí, landmarks đầy đủ, focus landing trên `h1` sau navigation.
- [ ] Màn hình 404, ErrorBoundary và trạng thái tính năng chưa khả dụng giữ nguyên thông điệp và không có dữ liệu giả lập.
- [ ] Toàn bộ quality gates pass: typecheck, lint, frontend tests, architecture check, build và fast checks.

## Test cases

1. **Behavioral equivalence tests:** Chạy toàn bộ test suite `AppShell.test.tsx` hiện tại bao gồm kiểm tra landmarks, routing, active navigation, 404 view, và ErrorBoundary.
2. **Design system integration test:** Kiểm tra AppShell import và render chính xác các canonical primitives từ `@/components/ui/` mà không gây circular dependencies.
3. **Accessibility verification:** Kiểm tra skip link, live region thông báo chuyển trang, và focus indicator trên các controls chuyển trang.

## Verification commands

```text
npm run test:frontend -- frontend/src/app/AppShell.test.tsx
npm run typecheck
npm run lint
npm run architecture:frontend
npm run build
npm run check:fast
```

Sau khi hoàn tất, chạy `npm run check:task` để bảo đảm độ bao phủ (coverage) không suy giảm.

## Expected output

- `npm run test:frontend -- frontend/src/app/AppShell.test.tsx`: exit code 0, 100% tests passed.
- `npm run typecheck`: exit code 0.
- `npm run lint`: exit code 0.
- `npm run architecture:frontend`: exit code 0.
- `npm run build`: exit code 0.
- `npm run check:fast`: exit code 0.

## Risk

- **Level:** `Medium`.
- Thay đổi class CSS hoặc thẻ bọc khi tích hợp shadcn primitive có thể làm lệch selector của skip-link, focus indicator, hoặc live-region.
- Mitigation: Bảo toàn cấu trúc HTML semantic của landmarks và test kỹ bằng các assertion kiểm tra role, text content, và focus target.

## Stop conditions

- Bị mất hoặc thay đổi bất kỳ hành vi routing/landmark/accessibility nào đã được kiểm chứng bởi T004 → DỪNG.
- Yêu cầu bổ sung thư viện router hoặc state library ngoài phạm vi → DỪNG.
- Có ý định đưa business logic hoặc mock data vào shell → DỪNG.

## Commit message đề xuất

`refactor(T076): migrate app shell visual styling to shadcn design system`

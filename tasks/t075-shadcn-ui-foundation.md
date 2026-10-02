# T075: shadcn/ui foundation & Tailwind integration

**Task ID:** `T075`  
**Title:** shadcn/ui foundation & Tailwind integration  
**Status:** `TODO`  
**Goal:** Integrate shadcn/ui into the existing React/Vite application as the canonical frontend design-system foundation without recreating the project or breaking existing routes, build, or test infrastructure.  

**Estimated scope:** Một phiên tập trung; tối đa 5 file cấu hình/source viết tay (`package.json`, `vite.config.ts`, `tsconfig.json`, `components.json`, `frontend/src/app/theme.css` hoặc `frontend/src/index.css`), cộng với utility `frontend/src/lib/utils.ts` và minimal primitive files được thêm có chủ đích vào `frontend/src/components/ui/`.  
**Suggested model:** Gemini  

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/ui-architecture.md](../docs/ui-architecture.md) Canonical design system & §2, §6, §7
- Official shadcn/ui Vite guide: `https://ui.shadcn.com/docs/installation/vite`
- Official shadcn/ui `components.json` reference: `https://ui.shadcn.com/docs/components-json`
- Official Tailwind CSS v4 docs: `https://tailwindcss.com/docs`
- Hiện trạng cấu hình: `package.json`, `vite.config.ts`, `tsconfig.json`, `.dependency-cruiser.cjs`

## Dependencies

- [T004](t004-frontend-shell-routes.md)
- [T002](t002-quality-gates-test-runner-build.md)

Mọi dependency phải có evidence hoàn tất. T004 đã hoàn tất và được bảo toàn nguyên vẹn.

## Files được phép sửa

- `package.json`
- `vite.config.ts`
- `tsconfig.json`
- `components.json`
- `frontend/src/lib/utils.ts`
- `frontend/src/index.css` (hoặc `frontend/src/app/theme.css`)
- `frontend/src/components/ui/*` (chỉ các canonical primitives tối thiểu cho roadmap trước mắt: ví dụ button, card, dialog)
- `frontend/tests/design-system.test.ts` (test kiểm tra tokens, `cn()` utility và render primitive)
- Generated: `package-lock.json`
- Common bookkeeping: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md).

## Files không được sửa

- `frontend/src/app/AppShell.tsx` (AppShell migration thuộc về T076)
- `frontend/src/app/shell.css` (AppShell styling thuộc về T076)
- Feature UI code: `frontend/src/features/*` (không triển khai Consent, Lookup, Search, Review, Quiz, Dashboard, Status)
- Backend code: `backend/*`
- Contracts: `contracts/*`
- Database migrations: `backend/migrations/*`
- Test harness & bootstrap: `frontend/src/bootstrap.ts`, `frontend/tests/e2e/*`

## Implementation notes

1. **Kiểm tra hiện trạng trước khi sửa:**
   - Stack hiện tại: React 19.0.0, Vite 8.3.1, TypeScript 5.8.2.
   - Vite root được cấu hình là `frontend`.
   - Entry points: `frontend/index.html` và `frontend/bootstrap.html`.
2. **Nguyên tắc tích hợp:**
   - Tích hợp trực tiếp vào project Vite hiện hữu; **TUYỆT ĐỐI KHÔNG** tạo lại project Vite (`never recreate the Vite project`).
   - Cài đặt Tailwind CSS v4 (`tailwindcss` và plugin `@tailwindcss/vite`) theo đúng hướng dẫn chính thức từ `https://ui.shadcn.com/docs/installation/vite`.
   - Thiết lập path alias `@/*` ánh xạ tới `frontend/src/*`:
     - Trong `tsconfig.json`: `"baseUrl": "."`, `"paths": { "@/*": ["frontend/src/*"] }`.
     - Trong `vite.config.ts`: `resolve: { alias: { '@': resolve(process.cwd(), 'frontend/src') } }`.
   - Tạo và kiểm tra tính hợp lệ của `components.json` theo schema chuẩn của shadcn/ui (`https://ui.shadcn.com/schema.json`):
     - Aliases: `components: "@/components"`, `ui: "@/components/ui"`, `utils: "@/lib/utils"`, `lib: "@/lib"`, `hooks: "@/hooks"`.
3. **Semantic theme tokens & utilities:**
   - Thiết lập các semantic theme tokens chuẩn (colors, backgrounds, foreground, border, focus, radius) kế thừa bảng màu hiện tại và đảm bảo độ tương phản WCAG 2.2 AA (4.5:1 text thường, 3:1 UI/focus).
   - Tạo hàm utility `cn()` chuẩn dùng `clsx` và `tailwind-merge` tại `frontend/src/lib/utils.ts`.
4. **Phạm vi primitives tối thiểu:**
   - Chỉ thêm các primitives tối thiểu cần thiết cho lộ trình feature kế tiếp (ví dụ: `button`, `card`, `dialog`).
   - **TUYỆT ĐỐI KHÔNG** chạy `shadcn add --all`.
   - **TUYỆT ĐỐI KHÔNG** sử dụng registry của bên thứ ba / community registries (chỉ dùng official shadcn registry).
   - Nếu phạm vi số file và primitives vượt quá giới hạn 5 file viết tay + primitives cơ sở, phải tách task chứ không được âm thầm mở rộng phạm vi.
5. **Bảo toàn kiến trúc:**
   - Giữ nguyên React 19, Vite 8, test runner Vitest, Playwright browser harness, typed API client và kiến trúc bootstrap.
   - Tuân thủ architecture boundaries trong `.dependency-cruiser.cjs` (không import node builtins trong client code, không import backend/sql/credentials).

## Acceptance criteria

- [ ] `components.json` được tạo hợp lệ, đúng cấu trúc và đúng path alias của repository (`@/*` -> `frontend/src/*`).
- [ ] Tailwind CSS v4 và Vite plugin được tích hợp thành công vào Vite hiện tại, `npm run build` xuất ra bundle dist không lỗi.
- [ ] TypeScript typecheck (`npm run typecheck`) và ESLint (`npm run lint`) đạt 0 errors trên toàn bộ source và primitives mới.
- [ ] Hàm tiện ích `cn()` và các semantic tokens được thiết lập, có test kiểm chứng tại `frontend/tests/design-system.test.ts`.
- [ ] Primitives cơ sở tối thiểu (button, card, dialog) được thêm vào `frontend/src/components/ui/` và render được trong môi trường test.
- [ ] Dependency Cruiser (`npm run architecture:frontend`) xác nhận không có vi phạm ranh giới kiến trúc.
- [ ] Không có thay đổi nào đối với code nghiệp vụ backend, public API contracts, hoặc behavior của AppShell hiện hữu.

## Test cases

1. **Path alias & utility test:** Import `@/lib/utils` và kiểm tra hàm `cn()` gộp classes Tailwind chính xác, xử lý conditional classes và conflicts.
2. **Primitive component render test:** Render `Button`, `Card`, `Dialog` từ `@/components/ui/` trong Vitest; kiểm tra render DOM hợp lệ và áp dụng semantic design tokens.
3. **Build & bundle verification:** `npm run build` thành công; không rò rỉ secret hoặc làm hỏng static assets của `frontend/bootstrap.html`.

## Verification commands

```text
npm run typecheck
npm run lint
npm run test:frontend -- frontend/tests/design-system.test.ts
npm run architecture:frontend
npm run build
npm run check:fast
```

Sau khi các lệnh trên pass, chạy đầy đủ `npm run check:task` để bảo đảm coverage và quality floor không bị suy giảm.

## Expected output

- `npm run typecheck`: exit code 0, 0 errors.
- `npm run lint`: exit code 0, 0 errors.
- `npm run test:frontend`: exit code 0, toàn bộ tests hiện có và design system tests pass.
- `npm run architecture:frontend`: exit code 0, 0 dependency violations.
- `npm run build`: exit code 0, Vite build tạo `frontend/dist/` thành công.
- `npm run check:fast`: exit code 0.

## Risk

- **Level:** `Medium`.
- Cấu hình path alias `@/*` không khớp giữa `tsconfig.json`, `vite.config.ts`, và `.dependency-cruiser.cjs` có thể gây lỗi module resolution hoặc vi phạm architecture check.
- Tích hợp Tailwind v4 với Vite plugin có thể ảnh hưởng đến rollupOptions multi-input (`index.html` và `bootstrap.html`).
- Mitigation: Xác minh cấu hình alias đối chiếu với tài liệu chính thức; kiểm tra kỹ bằng cả `tsc`, `vite build`, và `depcruise`.

## Stop conditions

- Cần tạo lại project Vite từ đầu thay vì tích hợp vào project hiện có → DỪNG.
- Phải dùng third-party registries ngoài official shadcn → DỪNG.
- Thay đổi logic nghiệp vụ AppShell hoặc feature UI → DỪNG.
- Typecheck hoặc architecture check phát hiện vi phạm ranh giới → DỪNG.

## Commit message đề xuất

`feat(T075): integrate shadcn/ui foundation and tailwind css v4`

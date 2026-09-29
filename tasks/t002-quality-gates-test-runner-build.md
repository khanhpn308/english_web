# T002: Frontend lint, typecheck và test runner

**Task ID:** `T002`  
**Title:** Frontend lint, typecheck và test runner  
**Status:** `DONE`  
**Goal:** Cung cấp lint/typecheck/Vitest và build command cho frontend; T004 tạo React entry point để build sản phẩm.  
**Suggested model:** Gemini  
**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay trong danh sách. Nếu vượt khoảng 2 giờ hoặc phạm vi này, tách task trước khi làm tiếp.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/toolchain.md](../docs/toolchain.md) — planned output của dependency; phải tồn tại trước khi dùng
- [docs/ui-architecture.md](../docs/ui-architecture.md) §10

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T001](t001-toolchain-repository-skeleton.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

- `package.json`
- `tsconfig.json`
- `eslint.config.js`
- `vite.config.ts`
- `frontend/tests/toolchain.test.ts`

Generated outputs, chỉ tạo bằng generator:

- `package-lock.json`

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- Cấu hình frontend tools; negative fixtures phải fail đúng reason. Vitest discovery có test thực về pipeline; T004 mới build React bundle, trước đó ghi BUILD_PENDING_SHELL. Không dùng passWithNoTests. Python gates chuyển T058. npm install scripts bị review, exact versions theo T001.
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [x] Frontend lint/typecheck/test runner có test thật và exit code đúng; no-tests không thành success.
- [x] Deliberate assertion/lint/type errors đều bị phát hiện, fixture lỗi được gỡ sau probe.
- [x] Build command tồn tại và báo thiếu entry point trước T004; T004 bắt buộc build thành công.

## Test cases

1. Runner discovery và assertions âm/dương.
2. TS invalid type, ESLint violation; toolchain build readiness report.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
npm run lint
npm run typecheck
npm run test:frontend -- frontend/tests/toolchain.test.ts
```

## Verification results & Evidence

- `npm run lint`: Exit code 0 (ESLint flat config quét toàn bộ dự án, 0 errors, 0 warnings).
- `npm run typecheck`: Exit code 0 (TypeScript strict mode, 0 errors).
- `npm run test:frontend -- frontend/tests/toolchain.test.ts`: Exit code 0 (4/4 tests passed in 156ms).
- Positive assertions & pipeline test: Exit code 0 (Node version, Vitest runner, negative assertion throw, and `BUILD_PENDING_SHELL` report).
- No-tests probe: `npm run test:frontend -- non_existent_pattern` $\rightarrow$ Exit code 1 (`No test files found, exiting with code 1`).
- Deliberate assertion error probe: `failing_probe.test.ts` $\rightarrow$ Exit code 1 (`AssertionError: expected 'actual' to be 'expected_failure'`).
- Deliberate type error probe: `const x: number = 'string'` $\rightarrow$ Exit code 2 (`error TS2322`).
- Deliberate ESLint error probe: `debugger;` $\rightarrow$ Exit code 1 (`error Unexpected 'debugger' statement no-debugger`).
- Deliberate probe fixtures removed cleanly after verification.
- Build command probe: `npm run build` $\rightarrow$ Exit code 1 (`[UNRESOLVED_ENTRY] Cannot resolve entry module index.html`, báo thiếu entry point đúng trước T004).

## Risk

- **Level:** `Medium`.
- Sai wiring/tooling có thể khiến task sau dùng command hoặc UI state không chính xác.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- Cần suppression/passWithNoTests để giấu việc chưa có feature, hoặc check đòi credential → dừng.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`chore(T002): frontend lint, typecheck và test runner`

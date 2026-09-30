# T052: Browser harness với local fake API/bridge

**Task ID:** `T052`  
**Title:** Browser harness với local fake API/bridge  
**Status:** `TODO`  
**Goal:** Cung cấp npm test:e2e và test:a11y dùng preview tạm reproducible để UI tasks chạy được.  
**Suggested model:** Gemini  
**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay trong danh sách. Nếu vượt khoảng 2 giờ hoặc phạm vi này, tách task trước khi làm tiếp.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/ui-architecture.md](../docs/ui-architecture.md) §10

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T004](t004-frontend-shell-routes.md)
- [T006](t006-api-core-contract-foundation.md)
- [T017](t017-typed-api-client.md)
- [T066](t066-browser-bootstrap.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

- `playwright.config.ts`
- `frontend/tests/e2e/harness.spec.ts`
- `frontend/tests/support/fake_bridge.py`
- `frontend/tests/support/test_server.py`
- `package.json`

Generated outputs, chỉ tạo bằng generator:

- `package-lock.json`

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- Playwright starts loopback backend/static UI against temporary DB/config and fake bridge; never existing user roots/key. Single harness provides ports/readiness teardown. Không bind hoặc stop proxy thật tại 8045; backend test injects fake bridge port/HTTP transport, và T007 kiểm tra exact-origin bằng synthetic transport. Production config không nhận arbitrary bridge URL từ test overrides. Chromium local; Windows Edge channel jobs explicit pending until platform exists. Package scripts test:e2e/test:a11y defined; user study content synthetic.
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [ ] Smoke harness starts/tears down temporary services and browser; no orphan process/port.
- [ ] All external provider calls denied; fake proxy dummy key only; no prod state copied.
- [ ] Commands stable, viewport profiles and artifacts sanitized; missing browser fail actionable.

## Test cases

1. Harness startup timeout/fake provider unavailable and teardown.
2. Check temporary source/data roots; request count and outbound destination assertions.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
npm run test:e2e -- frontend/tests/e2e/harness.spec.ts
npm run build
```

## Expected output

- Smoke harness starts/tears down temporary services and browser; no orphan process/port.
- Focused commands đạt kết quả/exit code ghi trong criteria; negative probe phải fail đúng reason. Documentation tasks có conformance report thay cho application-test pass.
- Evidence ghi command, exit code, môi trường và artifact. Thiếu Windows/browser/provider environment là PENDING; không hoàn tất gate thiếu evidence.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Risk

- **Level:** `Medium`.
- Sai wiring/tooling có thể khiến task sau dùng command hoặc UI state không chính xác.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- Need real proxy secrets/network login for browser harness → dừng.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`chore(T052): browser harness với local fake api/bridge`

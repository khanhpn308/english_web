# T018: Consent dialog và Status panel

**Task ID:** `T018`  
**Title:** Consent dialog và Status panel  
**Status:** `DONE` (code merged into `main` at `c4fe06c13`; final acceptance `PENDING`)
**Coding completion policy (2026-10-09):** Implementation integrated into `main`; final project acceptance is pending. Historical TODO, environment limitations and unchecked acceptance cases below remain evidence history, not test PASS.
**Goal:** Consent dialog và Status panel. All NOT_GRANTED/GRANTED/REVOKED/STALE/loading/error states visible; structured disclosure fields rendered.  
**Suggested model:** Gemini  
**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay trong danh sách. Nếu vượt khoảng 2 giờ hoặc phạm vi này, tách task trước khi làm tiếp.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/ui-architecture.md](../docs/ui-architecture.md) J7/keyboard & Canonical design system (shadcn/ui)
- [docs/api-contract.md](../docs/api-contract.md) CONSENT-07/10
- [tasks/t081-app-shell-shadcn-migration.md](t081-app-shell-shadcn-migration.md)

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T081](t081-app-shell-shadcn-migration.md)
- [T015](t015-consent-api.md)
- [T017](t017-typed-api-client.md)
- [T052](t052-browser-test-harness.md)

Mọi dependency phải có evidence hoàn tất. Task này bị chặn trực tiếp bởi nền tảng giao diện: `BLOCKED_BY_T080_T081`. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

- `frontend/src/features/consent/AiConsentGate.tsx`
- `frontend/src/features/consent/AiConsentPanel.tsx`
- `frontend/src/features/consent/consent.test.tsx`
- `frontend/tests/e2e/consent.spec.ts`
- `frontend/src/app/AppShell.tsx`

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- No initial grant; focus disclosure heading, Escape decline, focus return; stale/missing policy; GET after receipt. Revoke unknown locally disables AI while reconciling. Đăng ký flow vào route thật, không chỉ render isolated component; build và harness dùng cùng router.
- Thiết kế component theo design system: Sử dụng canonical primitives từ `frontend/src/components/ui/` (Dialog, Button, Card...) và semantic design tokens của T080/T081; không tự viết custom styling rời rạc ngoài hệ thống.
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [ ] All NOT_GRANTED/GRANTED/REVOKED/STALE/loading/error states visible; structured disclosure fields rendered.
- [ ] Consent changes alone zero learning requests; require fresh user action; no localStorage auth.
- [ ] Keyboard, two tabs, bridge-down revoke, lost response tests pass.

## Test cases

1. CONSENT-07/10; null policy; same-version digest changes.
2. Grant/revoke receipt historical vs GET current state.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
npm run test:frontend -- frontend/src/features/consent/consent.test.tsx
npm run test:e2e -- frontend/tests/e2e/consent.spec.ts
```

## Expected output

- All NOT_GRANTED/GRANTED/REVOKED/STALE/loading/error states visible; structured disclosure fields rendered.
- Focused commands đạt kết quả/exit code ghi trong criteria; negative probe phải fail đúng reason. Documentation tasks có conformance report thay cho application-test pass.
- Evidence ghi command, exit code, môi trường và artifact. Thiếu Windows/browser/provider environment là PENDING; không hoàn tất gate thiếu evidence.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Risk

- **Level:** `High`.
- Sai contract/concurrency/persistence có thể làm mất dữ liệu, ghi sai tiến độ hoặc tạo kết luận kiểm chứng sai.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- Panel grants automatically or hides unknown revoke as success → dừng.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`feat(T018): consent dialog và status panel`

# T060: Operational Status screen và consent integration

**Task ID:** `T060`  
**Title:** Operational Status screen và consent integration  
**Status:** `TODO`  
**Goal:** Cho người dùng biết storage/bridge/source readiness, recovery và consent tại Status.  
**Suggested model:** Gemini  
**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay trong danh sách. Nếu vượt khoảng 2 giờ hoặc phạm vi này, tách task trước khi làm tiếp.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/ui-architecture.md](../docs/ui-architecture.md) Status/J7 & Canonical design system (shadcn/ui)
- [docs/observability-plan.md](../docs/observability-plan.md) §6
- [docs/api-contract.md](../docs/api-contract.md) StatusSummary

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T046](t046-metrics-alerts-runbooks.md)
- [T018](t018-consent-ui.md)
- [T010](t010-error-handling-recovery.md)
- [T052](t052-browser-test-harness.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

- `frontend/src/features/status/StatusPage.tsx`
- `frontend/src/features/status/StatusPage.test.tsx`
- `frontend/tests/e2e/status.spec.ts`
- `frontend/src/app/AppShell.tsx`

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- Polling30s while visible, no key/account/path details. Reuse consent panel no new settings secrets form. Link runbooks/status banners; dashboard learning distinct. Source diagnostics safe bounded metadata, errors/revoke independent bridge. Đăng ký flow vào route thật, không chỉ render isolated component; build và harness dùng cùng router.
- Thiết kế component theo design system: `StatusPage` sử dụng canonical primitives (`Card`, `Table`, `Badge`, `Button`...) từ `frontend/src/components/ui/` và semantic tokens kế thừa từ T076 (qua T018).
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [ ] Readiness/offline matrix/metrics/source/bridge fields correct loading/empty/error with accessible labels.
- [ ] Visible polling30s, pause hidden/unmount, explicit invalidation; no unnecessary cloud queries.
- [ ] Consent route#ai-consent reachable every screen, revoke works bridge-down and unknown state not success.

## Test cases

1. Fake clock polling hidden window; storage degraded and API unavailable.
2. Consent grant/revoke refresh, safe fields and keyboard headings.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
npm run test:frontend -- frontend/src/features/status/StatusPage.test.tsx
npm run test:e2e -- frontend/tests/e2e/status.spec.ts
```

## Expected output

- Readiness/offline matrix/metrics/source/bridge fields correct loading/empty/error with accessible labels.
- Focused commands đạt kết quả/exit code ghi trong criteria; negative probe phải fail đúng reason. Documentation tasks có conformance report thay cho application-test pass.
- Evidence ghi command, exit code, môi trường và artifact. Thiếu Windows/browser/provider environment là PENDING; không hoàn tất gate thiếu evidence.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Risk

- **Level:** `Medium`.
- Sai wiring/tooling có thể khiến task sau dùng command hoặc UI state không chính xác.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- Status needs provider credentials/quota emails or realtime remote telemetry → dừng.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`feat(T060): operational status screen và consent integration`

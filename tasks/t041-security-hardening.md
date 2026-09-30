# T041: Browser/API/filesystem hardening evidence

**Task ID:** `T041`  
**Title:** Browser/API/filesystem hardening evidence  
**Status:** `TODO`  
**Goal:** Browser/API/filesystem hardening evidence. Security headers and hostile browser requests pass; LAN/CORS/path/proxy redirect blocked.  
**Suggested model:** GPT-6 Astra  
**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay trong danh sách. Nếu vượt khoảng 2 giờ hoặc phạm vi này, tách task trước khi làm tiếp.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/security-review.md](../docs/security-review.md) all threats
- [docs/api-contract.md](../docs/api-contract.md) §5–6

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T040](t040-first-run-recovery.md)
- [T021](t021-safe-source-files.md)
- [T025](t025-save-ui-audio.md)
- [T049](t049-writing-feedback-api.md)
- [T052](t052-browser-test-harness.md)
- [T063](t063-security-scan-tooling.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

- `backend/tests/test_security.py`
- `frontend/tests/e2e/security.spec.ts`
- `docs/reviews/security-implementation-001.md`

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- Task audit/focused hostile fixtures cho controls implemented từ đầu trong T006/T007/T021. Assertions CSP, Origin/CSRF, SQL/path guards, no credential bundle/log/DB; every security test mapping T-01–24. Failed controls quay task owner/focused fix, không sửa hàng loạt unrelated source. No approved local listener identity guarantee.
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [ ] Security headers and hostile browser requests pass; LAN/CORS/path/proxy redirect blocked.
- [ ] XSS/SSRF/SQL injection/path traversal/prompt injection fixtures fail safely.
- [ ] Dependency/secret scans clean; error responses generic and logs redacted.

## Test cases

1. T-01–T-24 applicable fake bridge/hostile files.
2. No credential in bundle, DB, logs, screenshots; CSP DOM checks.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
python -m pytest backend/tests/test_security.py -q
npm run test:e2e -- frontend/tests/e2e/security.spec.ts
npm run security:secrets
npm run security:code
```

## Expected output

- Security headers and hostile browser requests pass; LAN/CORS/path/proxy redirect blocked.
- Focused commands đạt kết quả/exit code ghi trong criteria; negative probe phải fail đúng reason. Documentation tasks có conformance report thay cho application-test pass.
- Evidence ghi command, exit code, môi trường và artifact. Thiếu Windows/browser/provider environment là PENDING; không hoàn tất gate thiếu evidence.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Risk

- **Level:** `Critical`.
- Sai boundary có thể gửi dữ liệu/cost không được phép hoặc mất lịch sử học.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- Test requires real credentials or cannot distinguish accepted local spoof residual → dừng and document limit.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`test(T041): browser/api/filesystem hardening evidence`

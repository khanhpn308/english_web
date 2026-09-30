# T040: Native first-run configuration và protected key store

**Task ID:** `T040`  
**Title:** Native first-run configuration và protected key store  
**Status:** `TODO`  
**Goal:** Native first-run configuration và protected key store. First-run valid native config persists protected key, browser/log/DB never key.  
**Suggested model:** GPT-6 Astra  
**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay trong danh sách. Nếu vượt khoảng 2 giờ hoặc phạm vi này, tách task trước khi làm tiếp.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/runbooks/first-run-and-restore.md](../docs/runbooks/first-run-and-restore.md)
- [docs/security-review.md](../docs/security-review.md) T-10/16
- [docs/adr/0004-v1-product-policy-and-operational-baseline.md](../docs/adr/0004-v1-product-policy-and-operational-baseline.md) runtime/recovery

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T039](t039-launcher.md)
- [T007](t007-bridge-policy-consent-adapter.md)
- [T020](t020-markdown-parser.md)
- [T005](t005-database-schema-migrations.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

- `launcher/src/first_run.py`
- `launcher/src/protected_key.py`
- `backend/app/platform/config.py`
- `launcher/tests/test_first_run.py`

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- Native/operator only: config.toml, DPAPI current-user key reference, data/Markdown roots. Validate migration/integrity/dry-run roundtrip/auth-profile; absence bridge may mark AI unavailable while local data works theo T013. No Google/admin credential read. Staging restore belongs T054.
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [ ] First-run valid native config persists protected key, browser/log/DB never key.
- [ ] Bad path/ACL/profile gives native remediation; restart no repeated credential entry if valid.
- [ ] Test dummy keys only; Windows DPAPI/ACL verification pending T057 when non-Windows.

## Test cases

1. Native fake-key provisioning, current-user DPAPI roundtrip.
2. Access denied, malformed config, missing key/profile; local vs AI readiness.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
python -m pytest launcher/tests/test_first_run.py -q
python -m mypy launcher
```

## Expected output

- First-run valid native config persists protected key, browser/log/DB never key.
- Focused commands đạt kết quả/exit code ghi trong criteria; negative probe phải fail đúng reason. Documentation tasks có conformance report thay cho application-test pass.
- Evidence ghi command, exit code, môi trường và artifact. Thiếu Windows/browser/provider environment là PENDING; không hoàn tất gate thiếu evidence.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Risk

- **Level:** `Critical`.
- Sai boundary có thể gửi dữ liệu/cost không được phép hoặc mất lịch sử học.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- Requires collecting/storing Google token/session or in-app backup → dừng.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`feat(T040): native first-run configuration và protected key store`

# T014: Durable operation ledger và idempotency

**Task ID:** `T014`  
**Title:** Durable operation ledger và idempotency  
**Status:** `DONE`  
**Goal:** Durable operation ledger và idempotency. Same-key/same-body replay không duplicate; changed body 422; in-flight 409.  
**Suggested model:** GPT-6 Astra  
**Estimated scope:** Một phiên tập trung; tối đa 7 file code/test trong danh sách theo phê duyệt bổ sung của owner ngày 30/09/2026. Nếu vượt khoảng 2 giờ hoặc phạm vi này, tách task trước khi làm tiếp.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/api-contract.md](../docs/api-contract.md) §8; Operation schema

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T005](t005-database-schema-migrations.md)
- [T006](t006-api-core-contract-foundation.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

- `backend/migrations/versions/0002_operations.py`
- `backend/app/application/operations.py`
- `backend/app/http/operations.py`
- `backend/app/main.py` — owner phê duyệt bổ sung để gắn operations router vào app factory (30/09/2026).
- `backend/tests/test_operations.py`
- `backend/tests/test_storage.py`, `backend/tests/test_health.py` — owner phê duyệt cập nhật assertions revision/schema của T005 khi migration `0002_operations` trở thành Alembic head (30/09/2026); giữ nguyên các failure-path tests.

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- Atomically claim fingerprint+key; store opaque result reference/receipt not prompt; UNKNOWN không resubmit. Retention theo CONSTRAINTS, không expire key thành fresh AI intent.
- Owner xác nhận 30/09/2026: “receipt expiry” trong acceptance được kiểm bằng fault injection giả lập receipt không đọc được; v1 vẫn giữ intent/receipt/fingerprint suốt đời database, không có TTL hay cleanup tự động.
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [x] Same-key/same-body replay không duplicate; changed body 422; in-flight 409.
- [x] GET operation redacted; restart UNKNOWN không dispatch; missing ID typed404.
- [x] Receipts/revision commit atomic, permanent minimal key tombstone ngăn reuse sau receipt expiry.

## Test cases

1. Two DB connections race; lost response after commit.
2. Retention boundary và rejected key reuse; disk full rollback.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
python -m pytest backend/tests/test_operations.py -q
```

## Expected output

- Same-key/same-body replay không duplicate; changed body 422; in-flight 409.
- Focused commands đạt kết quả/exit code ghi trong criteria; negative probe phải fail đúng reason. Documentation tasks có conformance report thay cho application-test pass.
- Evidence ghi command, exit code, môi trường và artifact. Thiếu Windows/browser/provider environment là PENDING; không hoàn tất gate thiếu evidence.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Risk

- **Level:** `High`.
- Sai contract/concurrency/persistence có thể làm mất dữ liệu, ghi sai tiến độ hoặc tạo kết luận kiểm chứng sai.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- Cần giữ transaction qua network hoặc log request body → dừng.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`feat(T014): durable operation ledger và idempotency`

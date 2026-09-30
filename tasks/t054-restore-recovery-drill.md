# T054: Staging restore và migration recovery drill

**Task ID:** `T054`  
**Title:** Staging restore và migration recovery drill  
**Status:** `TODO`  
**Goal:** Khôi phục bản copy lúc app dừng với migration/integrity/journal checks và nguyên vẹn learning history.  
**Suggested model:** GPT-6 Astra  
**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay trong danh sách. Nếu vượt khoảng 2 giờ hoặc phạm vi này, tách task trước khi làm tiếp.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/runbooks/first-run-and-restore.md](../docs/runbooks/first-run-and-restore.md)
- [docs/security-review.md](../docs/security-review.md) T-10/16
- [docs/api-contract.md](../docs/api-contract.md) journal

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T040](t040-first-run-recovery.md)
- [T022](t022-source-journal.md)
- [T048](t048-quiz-submit-api.md)
- [T049](t049-writing-feedback-api.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

- `launcher/src/restore.py`
- `launcher/tests/test_restore.py`
- `docs/runbooks/first-run-and-restore.md`
- `docs/reviews/restore-evidence-001.md`

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- Operator recovery workflow only, no in-app backup feature. Preserve original root; restore copy into task-specific staging, validate then configured-root switch, no overwrite sole original. Consent/policy/ops/history in SQLite and all Markdown roots included. Automated fixtures only; real data test requires exact authorized copy.
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [ ] Good staging copy preserves vocabulary/card/SRS/answers/feedback/consent references and hashes.
- [ ] Corrupt/ambiguous/migration failure never replaces original; writes blocked DEGRADED.
- [ ] Runbook exact stop/copy/check/switch/revert procedure tested and artifact redacted.

## Test cases

1. Mid-journal crash, DB migration failure, missing source backup.
2. Compare before/after history counts + hashes and repeat recovery; readonly original.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
python -m pytest launcher/tests/test_restore.py -q
```

## Expected output

- Good staging copy preserves vocabulary/card/SRS/answers/feedback/consent references and hashes.
- Focused commands đạt kết quả/exit code ghi trong criteria; negative probe phải fail đúng reason. Documentation tasks có conformance report thay cho application-test pass.
- Evidence ghi command, exit code, môi trường và artifact. Thiếu Windows/browser/provider environment là PENDING; không hoàn tất gate thiếu evidence.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Risk

- **Level:** `Critical`.
- Sai boundary có thể gửi dữ liệu/cost không được phép hoặc mất lịch sử học.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- Need delete DB, overwritten only copy, or new backup/upload feature → dừng.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`test(T054): staging restore và migration recovery drill`

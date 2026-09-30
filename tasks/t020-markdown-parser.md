# T020: Lossless Markdown parser/serializer

**Task ID:** `T020`  
**Title:** Lossless Markdown parser/serializer  
**Status:** `TODO`  
**Goal:** Lossless Markdown parser/serializer. Roundtrip preserves legacy fields/format; comma POS produces expected forms.  
**Suggested model:** Gemini  
**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay trong danh sách. Nếu vượt khoảng 2 giờ hoặc phạm vi này, tách task trước khi làm tiếp.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/vocabularies/README.md](../docs/vocabularies/README.md)
- [docs/vocabularies/28-09-2026.md](../docs/vocabularies/28-09-2026.md)
- [docs/adr/0004-v1-product-policy-and-operational-baseline.md](../docs/adr/0004-v1-product-policy-and-operational-baseline.md) legacy

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T019](t019-vocabulary-schema.md)
- [T013](t013-contract-conformance.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

- `backend/app/markdown_sync/parser.py`
- `backend/app/markdown_sync/serializer.py`
- `backend/tests/test_markdown_roundtrip.py`
- `backend/tests/fixtures/legacy.md`

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- Read-only original sample; synthetic/sanitized test copy. Preserve unknown/context rows and legacy path/date; POS split deterministic. Pure functions, no filesystem write or DB.
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [ ] Roundtrip preserves legacy fields/format; comma POS produces expected forms.
- [ ] Malformed date/H1/POS gives INVALID structured diagnostic; opaque rows not cards.
- [ ] Parse/serialize size caps enforced and content remains untrusted.

## Test cases

1. Existing-format fixture + unknown rows + multi POS + related members.
2. Invalid date, truncated table, oversized input, Unicode normalization.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
python -m pytest backend/tests/test_markdown_roundtrip.py -q
```

## Expected output

- Roundtrip preserves legacy fields/format; comma POS produces expected forms.
- Focused commands đạt kết quả/exit code ghi trong criteria; negative probe phải fail đúng reason. Documentation tasks có conformance report thay cho application-test pass.
- Evidence ghi command, exit code, môi trường và artifact. Thiếu Windows/browser/provider environment là PENDING; không hoàn tất gate thiếu evidence.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Risk

- **Level:** `Medium`.
- Sai wiring/tooling có thể khiến task sau dùng command hoặc UI state không chính xác.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- Lossless roundtrip impossible for a valid supported legacy file → dừng trước write.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`feat(T020): lossless markdown parser/serializer`

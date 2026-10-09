# T024: Explicit save preview vào Markdown và cards

**Task ID:** `T024`  
**Title:** Explicit save preview vào Markdown và cards  
**Status:** `DONE` (code merged into `main` at `9bb0f45d8`; final acceptance `PENDING`)
**Coding completion policy (2026-10-09):** Implementation integrated into `main`; final project acceptance is pending. Historical TODO, environment limitations and unchecked acceptance cases below remain evidence history, not test PASS.
**Goal:** Explicit save preview vào Markdown và cards. POST save creates date source/content + one card/form only on explicit save.  
**Suggested model:** GPT-6 Astra  
**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay trong danh sách. Nếu vượt khoảng 2 giờ hoặc phạm vi này, tách task trước khi làm tiếp.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/spec.md](../docs/spec.md) AC-04/11/33
- [docs/api-contract.md](../docs/api-contract.md) save/revisions
- [docs/reviews/contract-conformance-002.md](../docs/reviews/contract-conformance-002.md) — planned output của dependency; phải tồn tại trước khi dùng

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T008](t008-lookup-api-vertical-slice.md)
- [T023](t023-source-sync.md)
- [T031](t031-review-schema.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

- `backend/app/application/save_word_family.py`
- `backend/app/http/word_forms.py`
- `backend/tests/test_save_word_family.py`
- `backend/app/main.py`

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- Use source-resolution/new-day behavior frozen T013, server-generated safe path. All returned forms saved; journal handles atomicity. Requires no AI consent to save existing preview. Đăng ký đúng route/service vào app factory; TestClient và OpenAPI export dùng app factory production, không app test riêng bỏ security guards.
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [ ] POST save creates date source/content + one card/form only on explicit save.
- [ ] Same form same content new date reuses card/SRS; changed content reset per contract.
- [ ] Stale source/owner mismatch deny before write; same key replays same receipt.

## Test cases

1. Clean install new day; three forms; duplicate date and new date.
2. AC-11/33, lost response retry, invalid source and hash conflict.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
python -m pytest backend/tests/test_save_word_family.py -q
npm run test:contract
```

## Expected output

- POST save creates date source/content + one card/form only on explicit save.
- Focused commands đạt kết quả/exit code ghi trong criteria; negative probe phải fail đúng reason. Documentation tasks có conformance report thay cho application-test pass.
- Evidence ghi command, exit code, môi trường và artifact. Thiếu Windows/browser/provider environment là PENDING; không hoàn tất gate thiếu evidence.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Risk

- **Level:** `High`.
- Sai contract/concurrency/persistence có thể làm mất dữ liệu, ghi sai tiến độ hoặc tạo kết luận kiểm chứng sai.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- sourceId can't be obtained for new note date → do not invent client path; return to T013.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`feat(T024): explicit save preview vào markdown và cards`

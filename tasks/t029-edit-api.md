# T029: Revision-safe word-form edit API

**Task ID:** `T029`  
**Title:** Revision-safe word-form edit API  
**Status:** `TODO`  
**Goal:** Revision-safe word-form edit API. PATCH with correct source If-Match writes canonical content, revision and operation once.  
**Suggested model:** GPT-6 Astra  
**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay trong danh sách. Nếu vượt khoảng 2 giờ hoặc phạm vi này, tách task trước khi làm tiếp.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/spec.md](../docs/spec.md) AC-08/28/31
- [docs/api-contract.md](../docs/api-contract.md) PATCH, journal

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T024](t024-save-api.md)
- [T027](t027-search-api.md)
- [T017](t017-typed-api-client.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

- `backend/app/application/edit_word_form.py`
- `backend/app/http/word_forms.py`
- `backend/tests/test_edit_word_form.py`
- `backend/app/main.py`

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- Selected source only under T013 multi-source rule. Detect external file hashes before replacement; external editor itself cannot receive HTTP409. Meaning/examples reset; metadata-only no reset. Đăng ký đúng route/service vào app factory; TestClient và OpenAPI export dùng app factory production, không app test riêng bỏ security guards.
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [ ] PATCH with correct source If-Match writes canonical content, revision and operation once.
- [ ] Two API clients same ETag produce one success/one409; external write detected before app commit.
- [ ] Invalid/missing source deny; reset/history behavior correct, no false success on journal failure.

## Test cases

1. AC-08/28 and external editor write, conflict retains both snapshots.
2. IPA-only edit, replay after commit, readonly source.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
python -m pytest backend/tests/test_edit_word_form.py -q
npm run test:contract
```

## Expected output

- PATCH with correct source If-Match writes canonical content, revision and operation once.
- Focused commands đạt kết quả/exit code ghi trong criteria; negative probe phải fail đúng reason. Documentation tasks có conformance report thay cho application-test pass.
- Evidence ghi command, exit code, môi trường và artifact. Thiếu Windows/browser/provider environment là PENDING; không hoàn tất gate thiếu evidence.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Risk

- **Level:** `High`.
- Sai contract/concurrency/persistence có thể làm mất dữ liệu, ghi sai tiến độ hoặc tạo kết luận kiểm chứng sai.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- Conflict can silently overwrite concurrent external changes → dừng.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`feat(T029): revision-safe word-form edit api`

# T030: Edit form và conflict dialog

**Task ID:** `T030`  
**Title:** Edit form và conflict dialog  
**Status:** `TODO`  
**Goal:** Edit form và conflict dialog. Client validation maps backend field errors; draft preserved through retry/session renewal.  
**Suggested model:** Gemini  
**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay trong danh sách. Nếu vượt khoảng 2 giờ hoặc phạm vi này, tách task trước khi làm tiếp.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/ui-architecture.md](../docs/ui-architecture.md) detail/edit; §8–9
- [docs/spec.md](../docs/spec.md) AC-08/28/31

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T029](t029-edit-api.md)
- [T028](t028-search-ui.md)
- [T052](t052-browser-test-harness.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

- `frontend/src/features/search/EditWordForm.tsx`
- `frontend/src/features/search/RevisionConflictDialog.tsx`
- `frontend/src/features/search/edit.test.tsx`
- `frontend/tests/e2e/edit.spec.ts`
- `frontend/src/features/search/WordDetail.tsx`

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- Keep local draft and show current revision on409; fresh explicit submit after reload. INVALID/MISSING read-only; no general file repair GUI.
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [ ] Client validation maps backend field errors; draft preserved through retry/session renewal.
- [ ] Conflict dialog keyboard focus and source revision visible; no force overwrite.
- [ ] Confirmed content edit shows reset, invalidates search/detail/review/dashboard.

## Test cases

1. Same ETag two-tab conflict, external edit, missing source.
2. Meaning change vs IPA-only; failed save not successful toast.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
npm run test:frontend -- frontend/src/features/search/edit.test.tsx
npm run test:e2e -- frontend/tests/e2e/edit.spec.ts
```

## Expected output

- Client validation maps backend field errors; draft preserved through retry/session renewal.
- Focused commands đạt kết quả/exit code ghi trong criteria; negative probe phải fail đúng reason. Documentation tasks có conformance report thay cho application-test pass.
- Evidence ghi command, exit code, môi trường và artifact. Thiếu Windows/browser/provider environment là PENDING; không hoàn tất gate thiếu evidence.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Risk

- **Level:** `Medium`.
- Sai wiring/tooling có thể khiến task sau dùng command hoặc UI state không chính xác.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- Need merge/delete/relink scope not approved → dừng.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`feat(T030): edit form và conflict dialog`

# T050: Quiz runner và revision-aware autosave UI

**Task ID:** `T050`  
**Title:** Quiz runner và revision-aware autosave UI  
**Status:** `TODO`  
**Goal:** Làm bài đã tạo, phục hồi câu trả lời và autosave500ms/flush blur+submit qua local API.  
**Suggested model:** Gemini  
**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay trong danh sách. Nếu vượt khoảng 2 giờ hoặc phạm vi này, tách task trước khi làm tiếp.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/ui-architecture.md](../docs/ui-architecture.md) J5/quiz runner & Canonical design system (shadcn/ui)
- [docs/spec.md](../docs/spec.md) AC-18/23

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T047](t047-quiz-autosave-api.md)
- [T036](t036-quiz-ui.md)
- [T017](t017-typed-api-client.md)
- [T010](t010-error-handling-recovery.md)
- [T052](t052-browser-test-harness.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

- `frontend/src/features/quiz/QuizRunner.tsx`
- `frontend/src/features/quiz/QuestionRenderer.tsx`
- `frontend/src/features/quiz/QuizRunner.test.tsx`
- `frontend/tests/e2e/quiz-runner.spec.ts`
- `frontend/src/app/AppShell.tsx`

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- Only runner input/draft/restore. State draft/save pending/confirmed/error; don't mark saved before durable receipt. Reverse response order/revision conflict cannot overwrite newer input. No service worker/browser canonical DB; source snapshot read-only. Đăng ký flow vào route thật, không chỉ render isolated component; build và harness dùng cùng router.
- Thiết kế component theo design system: `QuizRunner` và `QuestionRenderer` sử dụng canonical primitives (`Card`, `Button`, `Input`, `RadioGroup`...) từ `frontend/src/components/ui/` và semantic tokens kế thừa từ T076 (qua T036/T018).
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [ ] All three question inputs+explicit selfScore render; saved data restored on tab/app reopen.
- [ ] 500ms debounce and blur/submit flush; unknown response reconciles before new mutation.
- [ ] Local API healthy network-down usable; restore error not empty quiz; keyboard focus preserved.

## Test cases

1. Fake timers debounce/blur, rapid edits out-of-order response, lost receipt.
2. Offline reload, stale tab conflict, session rebootstrap while draft remains.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
npm run test:frontend -- frontend/src/features/quiz/QuizRunner.test.tsx
npm run test:e2e -- frontend/tests/e2e/quiz-runner.spec.ts
```

## Expected output

- All three question inputs+explicit selfScore render; saved data restored on tab/app reopen.
- Focused commands đạt kết quả/exit code ghi trong criteria; negative probe phải fail đúng reason. Documentation tasks có conformance report thay cho application-test pass.
- Evidence ghi command, exit code, môi trường và artifact. Thiếu Windows/browser/provider environment là PENDING; không hoàn tất gate thiếu evidence.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Risk

- **Level:** `High`.
- Sai contract/concurrency/persistence có thể làm mất dữ liệu, ghi sai tiến độ hoặc tạo kết luận kiểm chứng sai.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- Browser optimistic state treated durable or submitting unsaved draft → dừng.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`feat(T050): quiz runner và revision-aware autosave ui`

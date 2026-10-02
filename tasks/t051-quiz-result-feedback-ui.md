# T051: Submit/result và writing feedback UI

**Task ID:** `T051`  
**Title:** Submit/result và writing feedback UI  
**Status:** `TODO`  
**Goal:** Nộp đã flush và xem scores, SRS notices, feedback history theo API.  
**Suggested model:** Gemini  
**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay trong danh sách. Nếu vượt khoảng 2 giờ hoặc phạm vi này, tách task trước khi làm tiếp.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/ui-architecture.md](../docs/ui-architecture.md) result/FeedbackHistory & Canonical design system (shadcn/ui)
- [docs/spec.md](../docs/spec.md) AC-17/19/35

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T050](t050-quiz-runner-ui.md)
- [T048](t048-quiz-submit-api.md)
- [T049](t049-writing-feedback-api.md)
- [T018](t018-consent-ui.md)
- [T052](t052-browser-test-harness.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

- `frontend/src/features/quiz/QuizResult.tsx`
- `frontend/src/features/quiz/FeedbackPanel.tsx`
- `frontend/src/features/quiz/QuizResult.test.tsx`
- `frontend/tests/e2e/quiz-result.spec.ts`
- `frontend/src/app/AppShell.tsx`

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- Terminal result route supports refresh; required writer self-score per oracle. Objective explanation separate from immutable question before submit. Feedback optional user action/current consent; preserve all local results when cloud fails. Fresh-key terminal failed feedback retry, same answerRevision. Đăng ký flow vào route thật, không chỉ render isolated component; build và harness dùng cùng router.
- Thiết kế component theo design system: `QuizResult` và `FeedbackPanel` sử dụng canonical primitives (`Card`, `Button`, `Badge`...) từ `frontend/src/components/ui/` và semantic tokens kế thừa từ T076 (qua T018/T050).
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [ ] Submit flushes durable draft then single operation; duplicate click/reload consistent result.
- [ ] Objective accuracy, selfScore and feedback separate; no AI overwrites scoring.
- [ ] REQUESTED/VALIDATED/FAILED history shown, consent grant no auto action and errors preserve result.

## Test cases

1. Submit while debounce pending, lost response, second tab.
2. Feedback timeout/malformed/stale/revoked, retry same old key vs explicit fresh key.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
npm run test:frontend -- frontend/src/features/quiz/QuizResult.test.tsx
npm run test:e2e -- frontend/tests/e2e/quiz-result.spec.ts
```

## Expected output

- Submit flushes durable draft then single operation; duplicate click/reload consistent result.
- Focused commands đạt kết quả/exit code ghi trong criteria; negative probe phải fail đúng reason. Documentation tasks có conformance report thay cho application-test pass.
- Evidence ghi command, exit code, môi trường và artifact. Thiếu Windows/browser/provider environment là PENDING; không hoàn tất gate thiếu evidence.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Risk

- **Level:** `High`.
- Sai contract/concurrency/persistence có thể làm mất dữ liệu, ghi sai tiến độ hoặc tạo kết luận kiểm chứng sai.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- UI needs undisclosed answer keys or silent feedback retry → dừng.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`feat(T051): submit/result và writing feedback ui`

# T049: Writing feedback API và history retry

**Task ID:** `T049`  
**Title:** Writing feedback API và history retry  
**Status:** `TODO`  
**Goal:** Request/store/read schema-validated feedback, preserving user answer and score through failure.  
**Suggested model:** GPT-6 Astra  
**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay trong danh sách. Nếu vượt khoảng 2 giờ hoặc phạm vi này, tách task trước khi làm tiếp.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/spec.md](../docs/spec.md) FR-ASM-11–15; AC-17/35
- [docs/api-contract.md](../docs/api-contract.md) Feedback/CONSENT
- [docs/security-review.md](../docs/security-review.md) T-20/24

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T047](t047-quiz-autosave-api.md)
- [T016](t016-dispatch-fence.md)
- [T034](t034-quiz-schema.md)
- [T014](t014-operations-idempotency.md)
- [T017](t017-typed-api-client.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

- `backend/migrations/versions/0008_feedback.py`
- `backend/app/application/feedback.py`
- `backend/app/http/feedback.py`
- `backend/tests/test_feedback.py`
- `backend/app/main.py`

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- Read canonical answerRevision, allowlisted rubric; timeout30s, user action/consent/admission. REQUESTED/VALIDATED/FAILED persisted; failed retry fresh idempotency key + retryOfOperationId, same answer. Safe error categories, redacted operation provenance, no answer payload in logs. Đăng ký đúng route/service vào app factory; TestClient và OpenAPI export dùng app factory production, không app test riêng bỏ security guards.
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [ ] Valid feedback linked answer/attempt/question/provider/model/prompt, independently paginated.
- [ ] Failures persist FAILED before safe response; old key replays failure, fresh authorized retry one dispatch.
- [ ] User selfScore unaffected; changed answer or policy blocks stale request; no secret/raw provider in logs.

## Test cases

1. AC-17/35, malformed JSON/auth/quota/timeout; history reload.
2. Wrong membership/rubric/revision, revoke barrier and fresh retry key.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
python -m pytest backend/tests/test_feedback.py -q
npm run test:contract
```

## Expected output

- Valid feedback linked answer/attempt/question/provider/model/prompt, independently paginated.
- Focused commands đạt kết quả/exit code ghi trong criteria; negative probe phải fail đúng reason. Documentation tasks có conformance report thay cho application-test pass.
- Evidence ghi command, exit code, môi trường và artifact. Thiếu Windows/browser/provider environment là PENDING; không hoàn tất gate thiếu evidence.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Risk

- **Level:** `Critical`.
- Sai boundary có thể gửi dữ liệu/cost không được phép hoặc mất lịch sử học.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- Feedback auto-scores or retries without admission, or persist failures can swallow user score → dừng.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`feat(T049): writing feedback api và history retry`

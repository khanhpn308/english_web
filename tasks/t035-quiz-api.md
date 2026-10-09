# T035: Quiz creation và snapshot retrieval API

**Task ID:** `T035`  
**Title:** Quiz creation và snapshot retrieval API  
**Status:** `DONE` (code merged into `main` at `877f44813`; final acceptance `PENDING`)
**Coding completion policy (2026-10-09):** Implementation integrated into `main`; final project acceptance is pending. Historical TODO, environment limitations and unchecked acceptance cases below remain evidence history, not test PASS.
**Goal:** Quiz creation và snapshot retrieval API. Create exactly requested counts from valid selected-date source; limit/insufficient/invalid output fail typed.  
**Suggested model:** GPT-6 Astra  
**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay trong danh sách. Nếu vượt khoảng 2 giờ hoặc phạm vi này, tách task trước khi làm tiếp.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/api-contract.md](../docs/api-contract.md) assessments/feedback
- [docs/spec.md](../docs/spec.md) AC-14–19/30/35
- [docs/security-review.md](../docs/security-review.md) T-04/05/20

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T034](t034-quiz-schema.md)
- [T016](t016-dispatch-fence.md)
- [T059](t059-quiz-scoring.md)
- [T023](t023-source-sync.md)
- [T014](t014-operations-idempotency.md)
- [T017](t017-typed-api-client.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

- `backend/app/http/quiz.py`
- `backend/app/application/create_quiz.py`
- `backend/app/enrichment/prompts/quiz.txt`
- `backend/tests/test_quiz_creation.py`
- `backend/app/main.py`

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- Chỉ POST create và GET attempt. Counts5–30 max20/type, selected valid date source kể cả not-due. Consent/admission có trước payload. Store immutable snapshot only after schema/count validation; deadline60s. GET chưa submit không expose answers/explanations. Autosave T047, submit T048, feedback T049. Đăng ký đúng route/service vào app factory; TestClient và OpenAPI export dùng app factory production, không app test riêng bỏ security guards.
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [ ] Create exactly requested counts from valid selected-date source; limit/insufficient/invalid output fail typed.
- [ ] Snapshot reloads immutable/offline; no answer keys/explanation leakage trước submit.
- [ ] Consent/routing/idempotency/60s timeout tests: no hidden fallback/retry, zero dispatch denied.

## Test cases

1. Boundary total0/3/5/30/31, pertype21, deleted source, wrong question counts.
2. Fake provider deny/timeout/hostile output; duplicate operation; offline GET.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
python -m pytest backend/tests/test_quiz_creation.py -q
npm run test:contract
```

## Expected output

- Create exactly requested counts from valid selected-date source; limit/insufficient/invalid output fail typed.
- Focused commands đạt kết quả/exit code ghi trong criteria; negative probe phải fail đúng reason. Documentation tasks có conformance report thay cho application-test pass.
- Evidence ghi command, exit code, môi trường và artifact. Thiếu Windows/browser/provider environment là PENDING; không hoàn tất gate thiếu evidence.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Risk

- **Level:** `Critical`.
- Sai boundary có thể gửi dữ liệu/cost không được phép hoặc mất lịch sử học.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- Question keys leak, quiz min total contradicts contract, or AI feedback can alter score → dừng.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`feat(T035): quiz creation và snapshot retrieval api`

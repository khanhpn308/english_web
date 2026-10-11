# T048: Quiz submission và atomic SRS handoff

**Task ID:** `T048`  
**Title:** Quiz submission và atomic SRS handoff  
**Status:** `TODO`  
**Goal:** Nộp quiz, chấm objective/self score và cập nhật SRS đúng một lần trong transaction.  
**Suggested model:** GPT-6 Astra  
**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay trong danh sách. Nếu vượt khoảng 2 giờ hoặc phạm vi này, tách task trước khi làm tiếp.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/spec.md](../docs/spec.md) FR-ASM-05–08; AC-16/19/30
- [docs/api-contract.md](../docs/api-contract.md) submissions

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T047](t047-quiz-autosave-api.md)
- [T032](t032-review-api.md)
- [T059](t059-quiz-scoring.md)
- [T017](t017-typed-api-client.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

- `backend/app/http/quiz_submissions.py`
- `backend/app/application/submit_quiz.py`
- `backend/tests/test_quiz_submission.py`
- `backend/app/main.py`

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- Use pure scorer T059; terminal submission_revision; weakest rating per form; suppress handoff for inactive source/card per clarified policy. Objective keys/explanations exposed only terminal response/read. No cloud need to score. Đăng ký đúng route/service vào app factory; TestClient và OpenAPI export dùng app factory production, không app test riêng bỏ security guards.
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [ ] Correctness MCQ/cloze/writing mapping exact; weakest rating wins and grouped event once.
- [ ] Quiz result+review handoff+operation commit atomic; retry/second submit not duplicate.
- [ ] Offline submit/terminal result reload work; preserve snapshot/history if source deleted.

## Test cases

1. Correct+incorrect same form; self score0–4/blank according oracle.
2. Failure before/after transaction, duplicate key vs new second key, stale revision.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
python -m pytest backend/tests/test_quiz_submission.py -q
npm run test:contract
```

## Expected output

- Correctness MCQ/cloze/writing mapping exact; weakest rating wins and grouped event once.
- Focused commands đạt kết quả/exit code ghi trong criteria; negative probe phải fail đúng reason. Documentation tasks có conformance report thay cho application-test pass.
- Evidence ghi command, exit code, môi trường và artifact. Thiếu Windows/browser/provider environment là PENDING; không hoàn tất gate thiếu evidence.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Risk

- **Level:** `Critical`.
- Sai boundary có thể gửi dữ liệu/cost không được phép hoặc mất lịch sử học.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- SRS and quiz commit separately causing double-count/data loss → dừng.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`feat(T048): quiz submission và atomic srs handoff`

## Standalone implementation checkpoint, 11/10/2026 (Asia/Bangkok)

- Code implemented on `feature/t048-quiz-submit-api`, base/HEAD `70105f4de49b84f84cfb0b408c69a7e5823d1792`. Final acceptance is `BLOCKED_VERIFICATION`; task status and acceptance checkboxes remain unchanged. No commit, merge, push or PR.
- Added the production submission route/service and 49 synthetic regressions. Reused T059 scoring, T034 terminal persistence, T032 review primitives and T014's atomic completion callback. Success follows durable result/SRS/receipt commit; replay and restart preserve the original result.
- Owner authorized only two additional generated files: `contracts/openapi.json` and `frontend/src/shared/api/generated.ts`. Generated through the existing T017 command; diff adds only the T048 route/request and matching TypeScript. T049 artifact reconciliation belongs to integration.
- Focused suite: 49 passed, exit 0. Dependency suite: 414 passed and one inherited migration-head failure, exit 1. Generated consistency restored; four inherited contract tests still fail. Lint, formatting, Mypy, architecture and secret-scan blockers are recorded separately from T048 diagnostics.
- Full Python suite: 2,207 passed and 30 failed, exit 1; all T048 tests passed. Sixteen failures reproduce at unchanged HEAD, thirteen require native Windows, and one lookup deadline failure passes in isolation but remains unresolved under the full parallel run.
- Full commands, review evidence, unchanged files, risks and remaining verification are in [the redacted standalone report](../docs/reviews/t048-standalone-verification.md). No quality threshold, existing test or security policy was weakened.

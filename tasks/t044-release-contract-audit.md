# T044: Generated contract and cross-doc audit

**Task ID:** `T044`  
**Title:** Generated contract and cross-doc audit  
**Status:** `TODO`  
**Goal:** Generated contract and cross-doc audit. No undocumented endpoint/schema/error/nullable/enum; examples satisfy min/max and response privacy.  
**Suggested model:** GPT-6 Astra  
**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay trong danh sách. Nếu vượt khoảng 2 giờ hoặc phạm vi này, tách task trước khi làm tiếp.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/reviews/spec-architecture-review-001.md](../docs/reviews/spec-architecture-review-001.md)

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T013](t013-contract-conformance.md)
- [T008](t008-lookup-api-vertical-slice.md)
- [T024](t024-save-api.md)
- [T027](t027-search-api.md)
- [T029](t029-edit-api.md)
- [T032](t032-review-api.md)
- [T035](t035-quiz-api.md)
- [T047](t047-quiz-autosave-api.md)
- [T048](t048-quiz-submit-api.md)
- [T049](t049-writing-feedback-api.md)
- [T037](t037-dashboard-formulas.md)
- [T046](t046-metrics-alerts-runbooks.md)
- [T061](t061-alerts-runbooks.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

- `scripts/audit_contract.py`
- `scripts/tests/test_audit_contract.py`
- `docs/reviews/contract-conformance-003.md`

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- Final audit only: compare implemented schema/examples/routes/version/security to docs; report exact discrepancy and responsible task; do not silently rewrite spec or review READY. Generated snapshot expected deterministic. Test audit with missing response/error field.
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [ ] No undocumented endpoint/schema/error/nullable/enum; examples satisfy min/max and response privacy.
- [ ] Every FR/AC critical path maps to task+test; no task writes forbidden files.
- [ ] Audit report records pending runtime evidence and no REVIEW_STATUS manual rewrite.

## Test cases

1. Schema snapshot diff; rg stale placeholders; link checks.
2. Contract test case index coverage.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
python scripts/audit_contract.py
python -m pytest scripts/tests/test_audit_contract.py -q
npm run test:contract
```

## Expected output

- No undocumented endpoint/schema/error/nullable/enum; examples satisfy min/max and response privacy.
- Focused commands đạt kết quả/exit code ghi trong criteria; negative probe phải fail đúng reason. Documentation tasks có conformance report thay cho application-test pass.
- Evidence ghi command, exit code, môi trường và artifact. Thiếu Windows/browser/provider environment là PENDING; không hoàn tất gate thiếu evidence.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Risk

- **Level:** `High`.
- Sai contract/concurrency/persistence có thể làm mất dữ liệu, ghi sai tiến độ hoặc tạo kết luận kiểm chứng sai.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- Contract discrepancy requires product choice not in ADR → stop and ask owner.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`docs(T044): generated contract and cross-doc audit`

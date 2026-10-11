# T044: Generated contract and cross-doc audit

**Task ID:** `T044`  
**Title:** Generated contract and cross-doc audit  
**Status:** `IMPLEMENTED_UNVERIFIED` (coding only; audit and acceptance `PENDING`)  
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

## Coding-only implementation handoff — 12/10/2026 (Asia/Bangkok)

- Implemented `scripts/audit_contract.py` (`t044-static-contract/1`): read-only AST route/model extraction, document/snapshot/DTO comparisons, represented example/bounds/privacy checks, FR/AC/task/test/evidence indices and deterministic redacted reporting. Default stdout; only explicit `--write-report` writes report 003. No app construction, provider access, source repair, dependency or CI change.
- Added [contract-conformance-003.md](../docs/reviews/contract-conformance-003.md) as an implementation checkpoint, not an executed conformance verdict. T037/T046/T061 runtime gaps, full pinned-generator reproduction and source-inspection discrepancy candidates retain exact owners and PENDING evidence. No other `REVIEW_STATUS` changed.
- Used the existing `feature/t044-contract-audit-tooling` worktree at base `2f82ac9e715e944465985169ab3b7a5e9d26c1bc`; no branch/worktree creation, reset, commit, push or unrelated source modification. Initial status was clean.
- Explicit session restriction makes `scripts/tests/test_audit_contract.py` read-only; it is absent at this base and was not created. A later authorized verification worker must add focused positive/negative tests before running the recorded commands. Existing contract/architecture tests are unchanged.
- `TESTS_RUN=NO`, `AUDIT_PERFORMED=NO`, `CONTRACT_AUDIT_EXECUTED=NO`, `BUILD_RUN=NO`, `TYPECHECK_RUN=NO`, `LINT_RUN=NO`, `SECURITY_SCAN_RUN=NO`. No installation or generated-file regeneration. Read-only source/status/diff inspection is the only inspection evidence; no acceptance box is checked.
- Boundaries: static JSON Schema subset and current AST/Markdown patterns; dynamic/custom projections, format validation, complete generator equality, current-head runtime and Windows/browser/provider/performance evidence remain pending. No spec/ADR/default/threshold was adjusted to make a result green.
- Next: host integration of coding-only source, then separately authorized T044 test/audit execution, T017 pinned contract reproduction and T013/feature-owner discrepancy resolution. CP22 and DONE remain unaccepted.

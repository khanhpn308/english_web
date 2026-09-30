# T061: Local symptom alerts và runbook links

**Task ID:** `T061`  
**Title:** Local symptom alerts và runbook links  
**Status:** `TODO`  
**Goal:** Đánh giá symptom windows và hiển thị alert có hướng xử lý đã kiểm chứng.  
**Suggested model:** GPT-6 Astra  
**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay trong danh sách. Nếu vượt khoảng 2 giờ hoặc phạm vi này, tách task trước khi làm tiếp.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/observability-plan.md](../docs/observability-plan.md) §5/7
- docs/runbooks/

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T046](t046-metrics-alerts-runbooks.md)
- [T060](t060-status-ui.md)
- [T063](t063-security-scan-tooling.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

- `backend/app/platform/alerts.py`
- `backend/tests/test_alerts.py`
- `docs/reviews/observability-evidence-001.md`

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- Exact plan thresholds2 health probes; API5xx>1%5min; searchp95>1s5min benchmark; bridge failures>20%10min; storagebusy>1%5min; any new invalid/integrity failure. Sliding-window sample size/empty conditions documented, no divide-zero false alert. Local status sink only, not page/push services.
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [ ] Every alert controlled fixture triggers category/severity/runbook as plan, resolves after recovery.
- [ ] No-data vs no-error distinct; bounded debounce/dedup and no unbounded label history.
- [ ] Redacted events/local status, rotation failure not stop study; runbook links existing/actionable.

## Test cases

1. Synthetic timestamps threshold boundary and window expiration each alert.
2. Zero requests, mixed failures, newly invalid source/integrity failure.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
python -m pytest backend/tests/test_alerts.py -q
npm run test:e2e -- frontend/tests/e2e/status.spec.ts
```

## Expected output

- Every alert controlled fixture triggers category/severity/runbook as plan, resolves after recovery.
- Focused commands đạt kết quả/exit code ghi trong criteria; negative probe phải fail đúng reason. Documentation tasks có conformance report thay cho application-test pass.
- Evidence ghi command, exit code, môi trường và artifact. Thiếu Windows/browser/provider environment là PENDING; không hoàn tất gate thiếu evidence.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Risk

- **Level:** `High`.
- Sai contract/concurrency/persistence có thể làm mất dữ liệu, ghi sai tiến độ hoặc tạo kết luận kiểm chứng sai.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- External pager/export needed or alert threshold to change → dừng.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`test(T061): local symptom alerts và runbook links`

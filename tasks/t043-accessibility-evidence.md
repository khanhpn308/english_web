# T043: WCAG 2.2 AA browser/manual evidence

**Task ID:** `T043`  
**Title:** WCAG 2.2 AA browser/manual evidence  
**Status:** `TODO`  
**Goal:** WCAG 2.2 AA browser/manual evidence. Zero critical/serious axe findings; all changed flows keyboard-complete and visible focus not obscured.  
**Suggested model:** GPT-6 Astra  
**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay trong danh sách. Nếu vượt khoảng 2 giờ hoặc phạm vi này, tách task trước khi làm tiếp.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/adr/0004-v1-product-policy-and-operational-baseline.md](../docs/adr/0004-v1-product-policy-and-operational-baseline.md) accessibility

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T025](t025-save-ui-audio.md)
- [T028](t028-search-ui.md)
- [T030](t030-edit-ui.md)
- [T033](t033-review-ui.md)
- [T036](t036-quiz-ui.md)
- [T050](t050-quiz-runner-ui.md)
- [T051](t051-quiz-result-feedback-ui.md)
- [T038](t038-dashboard-ui.md)
- [T060](t060-status-ui.md)
- [T052](t052-browser-test-harness.md)
- [T064](t064-ui-performance-harness.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

- `frontend/tests/e2e/a11y.spec.ts`
- `frontend/tests/e2e/audio.spec.ts`
- `docs/reviews/accessibility-001.md`
- `docs/runbooks/accessibility.md`

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- Run Chromium/Edge 320/768/1024/1440, 200% zoom, keyboard J1–J7, axe supplementary, manual focus/contrast/screen-reader smoke. Do not claim full SR support. Only positively local en-US voices selected; no default remote voice. Voice unavailable disables playback; Windows offline proof in T057.
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [ ] Zero critical/serious axe findings; all changed flows keyboard-complete and visible focus not obscured.
- [ ] Text labels, non-color statuses, 4.5:1/3:1 checks, responsive long Vietnamese/missing fields.
- [ ] Evidence artifact records browser/OS/date and unresolved moderate findings.

## Test cases

1. AC-24/25/32; consent dialog, quiz, conflict focus.
2. Zoom/viewport and CSS-disabled semantic smoke.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
npm run test:a11y
npm run test:e2e -- frontend/tests/e2e/audio.spec.ts
npm run benchmark:ui
```

## Expected output

- Zero critical/serious axe findings; all changed flows keyboard-complete and visible focus not obscured.
- Focused commands đạt kết quả/exit code ghi trong criteria; negative probe phải fail đúng reason. Documentation tasks có conformance report thay cho application-test pass.
- Evidence ghi command, exit code, môi trường và artifact. Thiếu Windows/browser/provider environment là PENDING; không hoàn tất gate thiếu evidence.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Risk

- **Level:** `High`.
- Sai contract/concurrency/persistence có thể làm mất dữ liệu, ghi sai tiến độ hoặc tạo kết luận kiểm chứng sai.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- No real preview/browser or threshold failure → retain evidence pending; no waiver without owner.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`test(T043): wcag 2.2 aa browser/manual evidence`

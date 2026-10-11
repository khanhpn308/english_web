# T064: Local Lighthouse performance harness

**Task ID:** `T064`  
**Title:** Local Lighthouse performance harness  
**Status:** `DONE (CODING_ONLY)` — `FINAL_VERIFICATION_DEFERRED` (11/10/2026; PR #19 merged into `main`; executable verification pending)
**Goal:** Measure LCP≤2.5s/CLS≤0.1 on a recorded deterministic preview and return a threshold verdict.  
**Suggested model:** Gemini  
**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay trong danh sách. Nếu vượt khoảng 2 giờ hoặc phạm vi này, tách task trước khi làm tiếp.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [CONSTRAINTS.md](../CONSTRAINTS.md) LCP/CLS
- [docs/ui-architecture.md](../docs/ui-architecture.md) responsive & Canonical design system (shadcn/ui)

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T052](t052-browser-test-harness.md)
- [T038](t038-dashboard-ui.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

- `scripts/ui_performance.py`
- `scripts/tests/test_ui_performance.py`
- `package.json`
- `docs/reviews/ui-performance-001.md`

Generated outputs, chỉ tạo bằng generator:

- `package-lock.json`

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- Run Lighthouse against temporary loopback preview started by T052, synthetic data, documented machine/Edge/Chromium/build/cache profile. npm benchmark:ui owns orchestration/threshold parsing. No preview deploy/cloud, no network provider. Do not report lab metrics as actual user sample.
- Đo lường hiệu năng giao diện trên bản dựng sử dụng canonical shadcn/Tailwind design system (qua T038/T081); bảo đảm các bundle primitives không gây hồi quy LCP hay layout shift CLS.
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [ ] Runner starts/stops preview, captures artifact, verifies LCP2.5s/CLS0.1 threshold fail/pass.
- [ ] Unknown/missing metric or tool exit failure not success; test thresholds with fixture reports.
- [ ] Hardware/build/cache fixture and timings recorded, no change to performance bar.

## Test cases

1. Metrics just-under/over threshold, missing values and Lighthouse exit failure.
2. Synthetic preview run, no provider request; sanitized artifact.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
python -m pytest scripts/tests/test_ui_performance.py -q
npm run benchmark:ui
```

## Expected output

- Runner starts/stops preview, captures artifact, verifies LCP2.5s/CLS0.1 threshold fail/pass.
- Focused commands đạt kết quả/exit code ghi trong criteria; negative probe phải fail đúng reason. Documentation tasks có conformance report thay cho application-test pass.
- Evidence ghi command, exit code, môi trường và artifact. Thiếu Windows/browser/provider environment là PENDING; không hoàn tất gate thiếu evidence.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Risk

- **Level:** `Medium`.
- Sai wiring/tooling có thể khiến task sau dùng command hoặc UI state không chính xác.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- Harness not runnable in current browser environment → pending evidence; no threshold relaxation.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`chore(T064): local lighthouse performance harness`

## Standalone coding-only checkpoint, 11/10/2026 (Asia/Bangkok)

- Implemented `scripts/ui_performance.py` as a deterministic local UI performance runner utilizing T052's `frontend/tests/support/test_server.py` loopback preview boundary.
- Enforced strict fail-closed Core Web Vitals thresholds: LCP ≤ 2.5s and CLS ≤ 0.1 (`CONSTRAINTS.md`).
- Implemented bounded lifecycle management (startup health check on `/api/v1/health`, process termination on SIGTERM/SIGKILL, port cleanup).
- Sanitized diagnostic evidence artifact generation excluding credentials, cookies, tokens, learning content, and raw prompts.
- Registered `"benchmark:ui": "python scripts/ui_performance.py"` in `package.json`.
- Documented implementation architecture and pending execution state in `docs/reviews/ui-performance-001.md`.
- Status: `IMPLEMENTED_UNVERIFIED` (coding-only session; tests, builds, lint, typecheck, audits, and Git commits deferred).

## Owner-approved coding-only closure — T064 (11/10/2026)

- Repository owner explicitly authorized merging PR #19 and closing T064 at `DONE (CODING_ONLY)`; the merge commit is `0fb3226ff69b19bbcff97f5e6d59854bb9309d28`.
- Integrated `scripts/ui_performance.py`, `npm run benchmark:ui` wiring in `package.json`, and `docs/reviews/ui-performance-001.md`, with existing T052/T038 functionality preserved.
- The implementation defines fail-closed LCP ≤ 2.5 s / CLS ≤ 0.1 evaluation and setup-pending conditions. **Neither Lighthouse nor a browser benchmark was run**; no measured Core Web Vitals, threshold PASS, or release evidence is claimed.
- `FINAL_VERIFICATION_DEFERRED` by owner: unit tests, build, typecheck, lint, security scans, benchmark and audit remain pending the final system-wide phase. Historical `IMPLEMENTED_UNVERIFIED` handoff above is superseded for coding closure only; acceptance checkboxes remain unchecked pending evidence.

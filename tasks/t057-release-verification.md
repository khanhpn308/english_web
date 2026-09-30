# T057: Windows/offline release evidence matrix

**Task ID:** `T057`  
**Title:** Windows/offline release evidence matrix  
**Status:** `TODO`  
**Goal:** Ghi evidence cuối cho product flows trên Windows/Edge/Chromium, source recovery và offline integrity.  
**Suggested model:** GPT-6 Astra  
**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay trong danh sách. Nếu vượt khoảng 2 giờ hoặc phạm vi này, tách task trước khi làm tiếp.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/spec.md](../docs/spec.md) AC-01–40
- [docs/security-review.md](../docs/security-review.md) all threats
- [docs/observability-plan.md](../docs/observability-plan.md) §7

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T041](t041-security-hardening.md)
- [T043](t043-accessibility-evidence.md)
- [T044](t044-release-contract-audit.md)
- [T054](t054-restore-recovery-drill.md)
- [T056](t056-windows-package.md)
- [T061](t061-alerts-runbooks.md)
- [T055](t055-ai-content-evidence.md)
- [T065](t065-search-performance-evidence.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

- `frontend/tests/e2e/offline.spec.ts`
- `launcher/tests/test_windows_lifecycle.py`
- `docs/reviews/release-evidence-001.md`

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- Full AC matrix includes test IDs/results/OS/browser/build hash; every required row PASS before release. Fake bridge tests automated; real installed profile/LAN/admin separation separate operator evidence without reading credentials. T055 human/provider checks may remain pending blocking RELEASE_READY; never override previous review status.
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [ ] AC matrix covers startup/lookup/save/search/edit/review/quiz/dashboard/consent with offline external network disabled.
- [ ] Windows restart/crash/duplicate launch, safe roots and voice localService/offline manually proved.
- [ ] Security/a11y/benchmark/human/provider evidence linked; missing environment or failure leaves release pending.

## Test cases

1. All journeys with fake bridge and no external network; local API stopped separate scenario.
2. Windows single-instance2 launches, token restart, staged restore, actual Edge local voice.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
npm run test:e2e -- frontend/tests/e2e/offline.spec.ts
python -m pytest launcher/tests/test_windows_lifecycle.py -q
npm run check:full
```

## Expected output

- AC matrix covers startup/lookup/save/search/edit/review/quiz/dashboard/consent with offline external network disabled.
- Focused commands đạt kết quả/exit code ghi trong criteria; negative probe phải fail đúng reason. Documentation tasks có conformance report thay cho application-test pass.
- Evidence ghi command, exit code, môi trường và artifact. Thiếu Windows/browser/provider environment là PENDING; không hoàn tất gate thiếu evidence.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Risk

- **Level:** `High`.
- Sai contract/concurrency/persistence có thể làm mất dữ liệu, ghi sai tiến độ hoặc tạo kết luận kiểm chứng sai.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- Any mandatory row lacks result, native Windows test only WSL, or provider quality lacks human review → no release sign-off.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`test(T057): windows/offline release evidence matrix`

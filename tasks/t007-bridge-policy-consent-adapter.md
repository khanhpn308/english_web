# T007: Antigravity transport adapter với fake proxy

**Task ID:** `T007`  
**Title:** Antigravity transport adapter với fake proxy  
**Status:** `TODO`  
**Goal:** Antigravity transport adapter với fake proxy. No-key models 401, keyed shape 200; auto/off, missing key và unsafe URL fail closed.  
**Suggested model:** GPT-6 Astra  
**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay trong danh sách. Nếu vượt khoảng 2 giờ hoặc phạm vi này, tách task trước khi làm tiếp.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/adr/0002-antigravity-loopback-trust-boundary.md](../docs/adr/0002-antigravity-loopback-trust-boundary.md)
- [docs/api-contract.md](../docs/api-contract.md) BR-AUTH-01–09

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T006](t006-api-core-contract-foundation.md)
- [T013](t013-contract-conformance.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

- `backend/app/adapters/bridge.py`
- `backend/app/platform/bridge_port.py`
- `backend/tests/test_bridge.py`
- `backend/tests/fixtures/bridge_cases.json`

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- Chỉ transport/profile, chưa consent implementation (T015/T016). Fake-key injection qua port; protected real key provisioning belongs T040; tests chỉ dummy key. Exact origin/path, no redirect/ambient proxy, strip auto-injected trace headers. Adapter chưa exposed như AI route.
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [ ] No-key models 401, keyed shape 200; auto/off, missing key và unsafe URL fail closed.
- [ ] Deadline bao gồm preflight/inference; bounded streaming response; no retries.
- [ ] Không đọc Google tokens/admin config; BR-AUTH residual giả mạo được ghi đúng.

## Test cases

1. BR-AUTH-01–08 bằng dummy key; model route mismatch fixture cho T016.
2. Proxy env, 3xx, oversized/malformed response, timeout; outbound sentinel capture.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
python -m pytest backend/tests/test_bridge.py -q
python -m mypy backend/app/adapters
```

## Expected output

- No-key models 401, keyed shape 200; auto/off, missing key và unsafe URL fail closed.
- Focused commands đạt kết quả/exit code ghi trong criteria; negative probe phải fail đúng reason. Documentation tasks có conformance report thay cho application-test pass.
- Evidence ghi command, exit code, môi trường và artifact. Thiếu Windows/browser/provider environment là PENDING; không hoàn tất gate thiếu evidence.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Risk

- **Level:** `Critical`.
- Sai boundary có thể gửi dữ liệu/cost không được phép hoặc mất lịch sử học.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- Cần real inference/credential hoặc tuyên bố xác thực listener từ health/key → dừng.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`feat(T007): antigravity transport adapter với fake proxy`

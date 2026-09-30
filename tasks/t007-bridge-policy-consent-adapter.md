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


## Final pre-commit cleanup audit — 30/09/2026

Cleanup status: **DONE**; focused T007 pre-commit verdict: **READY_TO_COMMIT**. No commit authorization; no staging, commit or push performed. This records the cleanup audit and does not assert release readiness.

Initial exact Ruff command returned **1 (FAIL)** with 12 diagnostics: I001 ×2, UP035 ×2, F401 ×3, SIM117 ×1 and ARG001 ×4. Safe Ruff fixes left four unused callback arguments; these were resolved without suppressions. Existing stream iterator suppression was replaced by its return annotation. Production deadline and size behavior were not changed.

| Command | Exit code | Result |
|---|---|---|
| `python -m pytest backend/tests/test_bridge.py -q` | 0 | PASS: 9 tests |
| `python -m mypy backend/app/adapters backend/app/platform` | 0 | PASS: 3 source files |
| `python -m ruff check backend/app/adapters/bridge.py backend/app/platform/bridge_port.py backend/tests/test_bridge.py` | 0 | PASS |
| `git diff --check` | 0 | PASS |

Environment: Linux, Python 3.12.3; all HTTPX clients use mock transports. No real bridge/key/inference was accessed.

Evidence in the existing tests:

- `test_monotonic_deadline`: absolute operation-1 deadline **5.0**; preflight start **0.0**; two synthetic requests each consume **2.0**, total **4.0**; dispatch start **4.0**; captured HTTPX read timeout **1.0**. Expired dispatch at 5.1 produces no request. Independent operation-2 deadline **15.1**, start **7.1**, captured budget **8.0**. Correction: the previous claim that preflight reused its initial timeout was inaccurate for the inspected source, which already supplied per-request overrides. The final deadline remediation below removes the redundant client timeout and records complete per-stage evidence; deadline enforcement is no longer pending downstream evidence.
- `test_stream_limit`: exact production constant **4_194_304**. Limit-minus-one and exact-limit reach malformed-JSON errors, proving size acceptance; limit-plus-one and oversized declared Content-Length raise `BridgeInvalidResponseError` specifically for size.
- Errors are separate subclasses of `BridgeError`: configuration (missing key or no-key 200), authentication (keyed 401/403), invalid response (malformed JSON/schema or oversize), unavailable (HTTPX timeout/connectivity or expired deadline). Callers can catch classes without parsing messages.
- `test_br_auth_03_unsafe_auto_off`: request capture equals exactly `[('/v1/models', None)]`; explicit chat count zero. `test_br_auth_02_approved_synthetic_profile`: no-key models 401, keyed models valid 200, then caller chat dispatch. The transport port does not own final consent/policy enforcement.

Changed during this audit: `bridge.py` (lint cleanup), `test_bridge.py` (lint/type cleanup and evidence assertions), this card and `docs/changelogs.md`. Intentionally untouched: `bridge_port.py`, `bridge_cases.json`, shared `tasks/todo.md` and all pre-existing parallel files. Scope audit uses initial/final SHA-256 comparison of unrelated working files; untracked T007 files are enumerated separately because `git diff --name-only` omits them.

PENDING downstream evidence: installed Windows/Antigravity v4.8.4 profile verification, LAN isolation from a second machine, protected real-key provisioning/rotation (T040), and final consent/policy admission (T016). ADR-0002 accepts a malicious local listener fully mimicking the profile; transport/key checks cannot authenticate server identity or remove the check/dispatch race. Next task: T016 admission integration. No unrelated task work is absorbed by this audit.

## Final deadline remediation — 30/09/2026

Remediation status: **DONE**. Focused T007 checks pass; complete working-tree verdict: **NOT_READY_TO_COMMIT** because unrelated parallel files fail full Mypy/Ruff. No staging, commit or push performed. The earlier cleanup verdict applies only to that earlier focused audit.

The client no longer computes or stores an initial operation timeout. Immediately before each no-key models, keyed models and chat request, `_get_timeout(deadline)` independently calculates `deadline - clock()`. A nonpositive remainder raises `BridgeUnavailableError` before the outbound request. Each request explicitly receives the new remaining budget, with the same caller-supplied absolute deadline; neither the deadline nor a prior stage's timeout is reused/reset as a fresh full budget. The port documents this obligation.

Deterministic synthetic evidence (all HTTPX connect/read/write/pool timeout values captured):

- Preflight shrinking budget: deadline **5.0**, no-key starts **0.0** with **5.0** seconds, completes **4.0**, keyed request receives **1.0** second.
- Exact deadline inside preflight: no-key completes **5.0** (also tested **5.1**); exactly **one** outbound request, no keyed request, `BridgeUnavailableError("Operation deadline exceeded")`.
- Already-expired preflight starts **5.0** or **5.1** against deadline **5.0**: zero outbound requests, same typed error.
- Dispatch remaining budget: deadline **5.0**, preflight requests receive **5.0 / 3.0**, total elapsed **4.0**; dispatch receives **1.0**. Dispatch at **5.1** sends no request.
- Independent second operation on the same adapter: new deadline **15.1**, start **7.1**, preflight receives **8.0 / 6.0**, ends **11.1**, dispatch receives **4.0**. All three stages are unaffected by the first operation's expired deadline.

| Command | Exit code | Result |
|---|---|---|
| `python -m pytest backend/tests/test_bridge.py -q` | 0 | PASS: 14 tests; adapter coverage 88% |
| `python -m mypy backend/app/adapters backend/app/platform` | 0 | PASS: 3 source files |
| `python -m ruff check backend/app/adapters/bridge.py backend/app/platform/bridge_port.py backend/tests/test_bridge.py` | 0 | PASS after wrapping three new overlong assertion lines |
| `git diff --check` | 0 | PASS |
| `python -m pytest -q` | 0 | PASS: 152 tests, 12.32s, outside sandbox; coverage-file warnings reported |
| `python -m mypy backend` | 1 | FAIL: 33 errors solely in parallel consent files |
| `python -m ruff check .` | 1 | FAIL: 19 errors solely in parallel files |

Full Mypy locations: `backend/app/application/consent.py` lines 48, 57, 58, 149 (unparameterized dicts); `backend/app/http/consent.py` lines 99, 131 (JSONResponse return types); `backend/tests/test_consent.py` lines 22, 49, 66, 71, 73, 102, 103, 130, 131, 150, 167, 168, 180, 192, 194, 211, 213, 226, 243, 244 (missing annotations/type arguments and ASGI transport attributes; some lines have multiple diagnostics).

Full Ruff locations: `backend/app/application/consent.py` lines 1, 8, 26, 120, 127, 183, 194, 201; `backend/app/http/consent.py` lines 1 (two diagnostics), 4, 73, 74, 95, 113, 128; `backend/tests/test_consent.py` line 1; `backend/tests/test_operations.py` line 53; `scripts/tests/test_contract.py` line 34. These files were already unrelated working-tree changes and were not edited. The initial sandbox full pytest stalled after the 14 bridge tests and was interrupted (exit 130); the same command completed outside the sandbox after approval. The successful run emitted coverage warnings about `.coverage` having no `arc` table for seven files; test assertions passed, but that run's whole-project coverage report is not clean coverage evidence.

Changed: `bridge.py`, `bridge_port.py`, `test_bridge.py`, this task card and `docs/changelogs.md`. Intentionally untouched: fixture JSON, shared `tasks/todo.md`, all T015/T017/other implementation and tooling files. SHA-256 comparison captured independent parallel changes to `scripts/check_constraints.py`, `scripts/tests/test_constraints.py` and `tasks/t053-quality-security-gates.md` during this session; no edits to those files were made by this remediation. Checks create their configured ignored coverage/cache artifacts.

Remaining downstream evidence: installed Windows/Antigravity profile, LAN isolation, T040 protected key provisioning and T016 consent/policy admission. Operation deadline enforcement itself is verified here and is not downstream. Next work: parallel owners resolve their type/lint findings; T016 consent/policy admission integration remains separate. No new product decision, migration, adapter redesign or dependency change.

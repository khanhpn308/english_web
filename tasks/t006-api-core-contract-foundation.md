# T006: Bootstrap session và HTTP guards

**Task ID:** `T006`

**Title:** Bootstrap session và HTTP guards

**Status:** `DONE`

**Goal:** Bootstrap session và HTTP guards. Bootstrap exchange 204, reuse/expired token denied; missing/expired session → typed 401.

**Suggested model:** GPT-6 Astra
**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay trong danh sách. Nếu vượt khoảng 2 giờ hoặc phạm vi này, tách task trước khi làm tiếp.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/api-contract.md](../docs/api-contract.md) §4 health/bootstrap, §5–6
- [docs/security-review.md](../docs/security-review.md) T-01/02/18

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T003](t003-backend-skeleton.md)
- [T013](t013-contract-conformance.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

- `backend/app/http/session.py`
- `backend/app/http/errors.py`
- `backend/app/http/bootstrap.py`
- `backend/app/main.py`
- `backend/tests/test_session.py`

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- Chỉ browser session/common errors; durable operations chuyển T014. One-time token 60s, fragment clear before app load, HttpOnly SameSite Strict; local HTTP không giả Secure guarantee. T013 định session expiry/restart rule.
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [x] Bootstrap exchange 204, reuse/expired token denied; missing/expired session → typed 401.
- [x] Host/Origin/JSON and cross-origin denial; no wildcard CORS; protected APIs/OpenAPI không leak data.
- [x] Browser token/cookie bị redacted; same-origin shell refresh works.

## Test cases

1. Token replay, stale cookie restart, two tabs.
2. Hostile Origin/Host; token absent referrer/logs.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
python -m pytest backend/tests/test_session.py -q
python -m mypy backend/app
```

## Verification evidence and handoff — 30/09/2026

- T003/T013 dependencies có commit/evidence hoàn tất. TDD RED: `python -m pytest backend/tests/test_session.py -q --no-cov` exit1 khi session module chưa tồn tại; sau slice đầu 8 PASS. Hai test bổ sung cho bodyless DELETE và shell refresh RED (422/thiếu static root), sau sửa 10 PASS; thêm max/max+1 và error-redaction cases thành 11 PASS.
- Server-side contract: token chỉ cấp bởi `SessionStore.issue_bootstrap_token()` trong backend, không có HTTP issuance route; exchange atomic một lần, 204 + host-only `HttpOnly; SameSite=Strict` cookie. TTL token `now < issued+60s`, cookie `now < issued+28800s`, không sliding; shutdown/restart xóa state. Host/Origin/Referer/JSON/1 MiB guards áp dụng trước route, OpenAPI và shell cần session; health, bootstrap page và built static assets là đường public cần thiết. Common 401/403/413/422 errors có envelope redacted và no-store/security headers. Bodyless DELETE giữ contract consent tương lai.
- Focused `python -m pytest backend/tests/test_session.py -q --no-cov`: 11 PASS; command chính xác `python -m pytest backend/tests/test_session.py -q`: 11 PASS. `python -m mypy backend/app`: PASS; `python -m ruff check` cho năm file source/test: PASS. `npm run build`: PASS (Vite 8.3.1, 16 modules). Final `npm run check:task:active`: 89 Python + 21 frontend PASS, changed coverage 93,27% ≥80%, total 88,50% ≥ ratchet, format/lint/typecheck/floor PASS, Gitleaks/Semgrep/OSV 0 findings; ESLint 0 errors/2 pre-existing Fast Refresh warnings ở AppShell. `git diff --cached --check` PASS sau khi chuẩn hóa hard-break spaces của thẻ mới được stage.
- Các file sửa: ba HTTP modules trong allowlist, `backend/app/main.py`, `backend/tests/test_session.py`, thẻ này, `tasks/todo.md`, `docs/changelogs.md`. Giữ nguyên spec/API/UI/ADR, cấu hình/locks, generated DTO, dữ liệu người dùng và mọi file planning untracked khác. Không thêm dependency, suppression, inference hoặc remote push.
- Browser bootstrap page/fragment clearing và real browser/referrer evidence thuộc T066/T052; Windows launcher token issuance thuộc T039; generated DTO/OpenAPI conformance thuộc T017; architecture command T062 chưa có. Đây là handoff downstream, không được tính là T006 browser runtime PASS. Local HTTP không gắn `Secure` cookie theo threat model; `Referrer-Policy: no-referrer` và CSP giữ boundary. ADR-0005 đã chốt strategy nên không tạo ADR mới.
- Next ready task: T014 durable operation ledger và idempotency; CP04 còn chờ T014/T017.

## Expected output

- Bootstrap exchange 204, reuse/expired token denied; missing/expired session → typed 401.
- Focused commands đạt kết quả/exit code ghi trong criteria; negative probe phải fail đúng reason. Documentation tasks có conformance report thay cho application-test pass.
- Evidence ghi command, exit code, môi trường và artifact. Thiếu Windows/browser/provider environment là PENDING; không hoàn tất gate thiếu evidence.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Risk

- **Level:** `High`.
- Sai contract/concurrency/persistence có thể làm mất dữ liệu, ghi sai tiến độ hoặc tạo kết luận kiểm chứng sai.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- Phải expose session token trong UI state/log để chạy → dừng.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`feat(T006): bootstrap session và http guards`

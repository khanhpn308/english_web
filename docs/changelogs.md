## 30/09/2026 - T066 Trusted browser bootstrap page

- **Khu vực:** `frontend/bootstrap.html`, `frontend/src/bootstrap.ts`, `vite.config.ts`
- **Thay đổi:** 
  1. Thêm Vite multi-page build cho phép sinh ra HTML và JS cô lập hoàn toàn cho `bootstrap.html`.
  2. Implement `bootstrap.ts` đọc `#token=...`, xóa URL fragment ngay lập tức qua `history.replaceState`.
  3. Gửi `POST /bootstrap/exchange`, bắt thành công HTTP 204 rồi chuyển hướng `location.replace("/")`.
  4. Unit test sử dụng mock dependencies (`BootstrapDependencies`) để đảm bảo không rò rỉ token, chứng minh trình tự gửi (clearing happens before fetching) và handle các mã lỗi 401, 403, 500, network error an toàn mà không in log token.
- **Mục đích:** Khởi tạo session an toàn trước khi vào app chính. Tránh token bị leak vào React application state, log hay analytics.
- **Pending Downstream:** T052, T057. (Chưa có real browser E2E, thuộc phạm vi T052).

## 30/09/2026 - T066 Trusted browser bootstrap page

- **Khu vực:** `frontend/bootstrap.html`, `frontend/src/bootstrap.ts`, `vite.config.ts`
- **Thay đổi:** 
  1. Thêm Vite multi-page build cho phép sinh ra HTML và JS cô lập hoàn toàn cho `bootstrap.html`.
  2. Implement `bootstrap.ts` đọc `#token=...`, xóa URL fragment ngay lập tức qua `history.replaceState`.
  3. Gửi `POST /bootstrap/exchange`, bắt thành công HTTP 204 rồi chuyển hướng `location.replace("/")`.
  4. Unit test sử dụng mock dependencies (`BootstrapDependencies`) để đảm bảo không rò rỉ token, chứng minh trình tự gửi (clearing happens before fetching) và handle các mã lỗi 401, 403, 500, network error an toàn mà không in log token.
- **Mục đích:** Khởi tạo session an toàn trước khi vào app chính. Tránh token bị leak vào React application state, log hay analytics.
- **Pending Downstream:** T052, T057. (Chưa có real browser E2E, thuộc phạm vi T052).

## 30/09/2026 - T017 Remediation

- **Khu vực:** `frontend/src/shared/api`, `scripts/export_contract.py`, `scripts/tests/test_contract.py`
- **Thay đổi:** 
  1. Loại bỏ các schema ErrorDetails ảo (chưa được backend hỗ trợ) ra khỏi generator, chỉ export `FIELD_ERRORS`.
  2. Bổ sung context (URL, method, Idempotency-Key, operationId) cho MutationUnknownError để phục vụ reconciliation.
  3. Cập nhật `test_contract.py` so sánh full-schema byte-for-byte với file checked-in.
  4. Sửa false positive ETag validation `null` guard.
- **Mục đích:** Sửa các bẫy lỗi và ranh giới hợp đồng API, đảm bảo generation không chèn dữ liệu unsupported và test chống trượt cấu trúc.

## 30/09/2026

- **Khu vực:** `frontend/src/shared/api`, `scripts/export_contract.py`, `contracts/openapi.json`
- **Thay đổi:** Hoàn thành T017. Thêm client API có hỗ trợ AbortController, tự động parse typed error. Thêm script generate openapi JSON deterministic.
- **Mục đích:** Xây dựng cầu nối type-safe, tự động lấy DTO từ backend OpenAPI.

## 30/09/2026

- **Khu vực:** `backend/app/application/operations.py`, `backend/app/http/operations.py`, `backend/app/main.py`, `backend/tests/test_operations.py`, `backend/migrations/versions/0002_operations.py`, `tasks/t014-operations-idempotency.md`, `tasks/todo.md`
- **Thay đổi:** Hoàn thành T014: triển khai durable operation ledger. Bổ sung `OperationLedger` với cơ chế idempotency dùng `BEGIN IMMEDIATE`, kiểm tra digest chống trùng lặp; cập nhật endpoint `GET /operations/{id}` redacted, và exception handler cho `SQLAlchemyError`. Pass toàn bộ test kiểm chứng concurrency, lost response, và fault injection.
- **Mục đích:** Đảm bảo tính idempotency và atomic cho các tác vụ AI và save, ngăn chặn duplicate dispatch, tuân thủ đúng API contract về error responses và data redaction.

# Changelog

## Quy định cập nhật

1. Mọi thay đổi do agent thực hiện trong workspace đều phải được ghi vào file này.
2. Ngày sử dụng định dạng **dd/mm/yyyy** và múi giờ `Asia/Bangkok`.
3. Mỗi mục phải nêu ngắn gọn:
   - Ngày thay đổi.
   - Khu vực/file bị thay đổi.
   - Nội dung thay đổi.
   - Lý do hoặc mục đích nếu cần.
4. Ghi mục mới ở đầu danh sách thay đổi, bên dưới phần quy định.
5. Không xóa hoặc sửa lịch sử cũ, trừ khi cần sửa lỗi ghi chép rõ ràng.
6. Agent phải cập nhật changelog trước khi kết thúc một tác vụ có thay đổi file.

## 30/09/2026

- **Khu vực:** `backend/app/http/session.py`, `errors.py`, `bootstrap.py`, `backend/app/main.py`, `backend/tests/test_session.py`, `tasks/t006-api-core-contract-foundation.md`, `tasks/todo.md`.
- **Thay đổi:** Hoàn thành T006 với token bootstrap một lần, session cookie trong bộ nhớ theo vòng đời backend, Host/Origin/Referer/JSON/1 MiB guards, typed redacted errors và same-origin static shell refresh. Health vẫn public; OpenAPI/API/shell cần session. Test RED→GREEN cho replay, expiry, restart, hai tab, hostile headers, max/max+1 và không phản chiếu token.
- **Verification:** 11 focused session tests, 89 full Python tests, 21 frontend tests, Mypy/Ruff/format/typecheck/build PASS; changed coverage 93,27%, total 88,50%; Gitleaks/Semgrep/OSV 0 findings. ESLint 0 errors, 2 warning Fast Refresh cũ. `npm run check:task:active` PASS; T062 architecture aggregate vẫn chưa có command.
- **Mục đích:** Khóa HTTP trust boundary của app local theo API contract và ADR-0005 trước T014/T017/T066. Documentation-and-adrs ghi rationale/handoff trong thẻ task; không tạo ADR mới vì strategy đã được chốt. Browser page/referrer thực và launcher tiếp tục ở task owner.

- **Khu vực:** `tasks/todo.md`, `docs/changelogs.md` và bộ tài liệu T013.
- **Thay đổi:** Tích hợp commit atomic T013 `d7196f3` vào nhánh T063, giữ nguyên evidence của cả T063 và T013, hợp nhất hai xung đột bookkeeping, chuẩn hóa code fence Python trong conformance report theo Ruff và đánh dấu CP03 hoàn tất.
- **Verification:** 11 document probes và 2 negative mutation probes PASS; staged scope/link/authority probe PASS; aggregate gate PASS với format/lint/typecheck, 21 frontend tests, 78 Python tests, changed coverage 100%, combined total 87,42% và ba security scanners đều 0 findings. ESLint còn 2 warning Fast Refresh đã tồn tại, 0 error.
- **Mục đích:** Đồng bộ task checklist và contract-conformance artifacts vào checkout đang được sử dụng mà không thay đổi semantics của API contract.

- **Khu vực:** T013 — `docs/api-contract.md`, `docs/reviews/contract-conformance-002.md`, thẻ T013.
- **Thay đổi:** Sau khi T063 cung cấp Gitleaks 8.30.1, thêm RED→GREEN security recheck cho snapshot contract: thay ba synthetic `Idempotency-Key` values bằng symbolic placeholder, bỏ raw API baseline digest khỏi prose và viết lại một bridge sentence bị rule generic-key bắt nhầm. Không đổi endpoint, schema, precondition hoặc semantics. Directory, staged diff và current-HEAD history (8 commits) đều 0 findings; không dùng allowlist/suppression.
- **Mục đích:** Giữ commit T013 atomic và tương thích security gate hiện hành mà không thay đổi quyết định contract hay quality bar.

- **Khu vực:** `scripts/security_checks.py`, `scripts/tests/test_security_checks.py`, `package.json`, generated `requirements-dev.lock`, `docs/toolchain.md`, `tasks/t063-security-scan-tooling.md`, `tasks/todo.md`; hai wording fixture/prose trong untracked planning `docs/api-contract.md` được sửa nhưng không stage do T013 sở hữu.
- **Thay đổi:** Hoàn thành T063 với wrapper exact-version cho Gitleaks 8.30.1, Semgrep CE 1.178.0 và OSV-Scanner 2.6.0; report chỉ chứa metadata đã redacted, high/critical/unknown fail closed, scanner/network/report lỗi trả setup failure, no-HEAD/untracked + staged + current-HEAD history được quét. Bổ sung 20 focused tests (78 full Python), changed coverage 88,98%, combined total 87,42% và real negative probes; nối npm security scripts/aggregate gates. Remediation được owner phê duyệt không dùng suppression: rewrite hai false-positive examples và regenerate dev lock bằng `--allow-unsafe`, chỉ thêm pin `pip==26.2.1`/`setuptools==84.0.0`. Ba security gates đều 0 findings.
- **Mục đích:** Biến ba security dimensions trong `CONSTRAINTS.md` thành executable gates mà không che finding bằng suppression/allowlist hoặc tự force-upgrade. Skill documentation-and-adrs được dùng để ghi pin/source/license/install boundary, privacy/exit contract, remediation trade-off và cross-branch T013 risk; không tạo ADR vì đây là tooling dễ đảo ngược, không đổi architecture/API.

## 29/09/2026

- **Khu vực:** `scripts/check_constraints.py`, `scripts/tests/test_constraints.py`, `package.json`, `pyproject.toml`, generated lockfiles, `docs/toolchain.md`, `tasks/t053-quality-security-gates.md`, `tasks/todo.md`.
- **Thay đổi:** Hoàn thành T053 bằng CLI diff-scoped cho changed coverage tối thiểu 80%, combined coverage baseline 86,70% với ratchet 0,5 điểm và quality-floor guard. Bổ sung 17 test cases âm/dương cho report thiếu, 79,9/80, ratchet, unmeasured source, suppression/skip/xóa test hoặc assertion/hạ threshold, redaction, coverage/floor trên untracked no-HEAD và trạng thái pending; nối Vitest V8 LCOV, pytest Cobertura, format/floor/coverage scripts và các aggregate command không false-green khi T062/T063 chưa sẵn sàng.
- **Mục đích:** Biến quality bar trong `CONSTRAINTS.md` thành gate có exit code và artifact thực, giữ scanner/architecture ownership tách biệt. Skill documentation-and-adrs được dùng để ghi nguồn chính thức, dependency/license, baseline, trade-off và trạng thái `SETUP_PENDING`; không cần ADR vì thay đổi chỉ là tooling dễ đảo ngược, không đổi architecture/API.

- **Khu vực:** T013 — `docs/spec.md`, `docs/api-contract.md`, `docs/ui-architecture.md`, `docs/adr/0005-contract-clarifications.md`, `docs/reviews/contract-conformance-002.md`, thẻ T013 và `tasks/todo.md`.
- **Thay đổi:** Chốt 11 nhóm conformance bằng ADR-0005: quiz 5–30 với ví dụ2/2/1 và reject1/1/1; HARD giữ box và due calendar midnight Bangkok; writing-rubric-v1/blank/null; conditional new-date save/backend source ID/revision/ETag; hash/watcher vs stale API409; keys/explanations chỉ trong terminal result, GET attempt/replay/SRS atomic; caps1/8/4MiB, session60s/8h, deadline120/60/30s và database-lifetime idempotency retention. Đồng bộ AC/DTO/UI và các positive fixtures.
- **Verification:** 11 document probes RED→GREEN; hai negative mutation probes reject đúng reason; manual crosswalk/walkthrough trong report. Staged whitespace/scope/link/provenance checks PASS sau khi chuẩn hóa metadata hard-break spaces trong scoped files; supplemental redacted credential-pattern scan zero candidates. Không có application code hoặc inference; generated/runtime/Windows/browser/provider/security tooling vẫn do task owner xác minh. Gitleaks chưa có (exit127), giữ PENDING.
- **Mục đích:** Cung cấp oracle xác định trước khi business contracts được freeze. Skill documentation-and-adrs giữ authority, alternatives/consequences và evidence ownership rõ ràng. Worktree riêng bảo toàn concurrent T053; chỉ stage allowlist/bookkeeping T013, gồm full snapshots của planning inputs trước đó untracked.

- **Khu vực:** `frontend/index.html`, `frontend/src/main.tsx`, `frontend/src/app/AppShell.tsx`, `frontend/src/app/shell.css`, `frontend/src/app/AppShell.test.tsx`, `vite.config.ts`, `tsconfig.json`, `tasks/t004-frontend-shell-routes.md`, `tasks/todo.md`.
- **Thay đổi:** Hoàn thành task T004 (React shell, route map và landmarks):
  - Triển khai `AppShell` với đầy đủ cấu trúc landmarks ngữ nghĩa (`<header>`, `<nav aria-label="Điều hướng chính">`, `<main id="main-content">`), skip link chuyển hướng đến nội dung chính và live region thông báo chuyển trang.
  - Thiết lập danh mục 9 route chuẩn hóa theo `docs/ui-architecture.md` §1 (`/`, `/lookup`, `/search`, `/word-forms/:wordFormId`, `/review`, `/quiz/new`, `/quiz/:attemptId`, `/quiz/:attemptId/result`, `/status`), bộ bóc tách dynamic route parameters và màn hình 404 cho route không hợp lệ.
  - Hiển thị trạng thái chưa khả dụng trung thực, không giả lập dữ liệu cho các route v1 chưa có logic nghiệp vụ.
  - Đảm bảo trạng thái `aria-current="page"` tại nav link đang active và bổ sung link truy cập quyền AI `/status#ai-consent` trong header shell.
  - Tích hợp `ErrorBoundary` bảo vệ ứng dụng khi một màn hình gặp sự cố và cung cấp liên kết chuyển sang kiểm tra trạng thái tại `/status`.
  - Cung cấp `shell.css` hỗ trợ responsive (320px - 1440px), tương phản cao, focus ring 3:1 và zoom 200% không che khuất control theo chuẩn WCAG 2.2 AA.
  - Đóng gói static build thành công vào `frontend/dist/` không chứa credentials hay bridge tokens.
  - Bổ sung 17 component/route test cases trong `AppShell.test.tsx`, đạt 21/21 tests frontend PASS cùng kiểm tra typecheck và lint hoàn hảo.
- **Mục đích:** Cung cấp khung giao diện React shell vững chắc, accessible và route map chuẩn mực cho các task giao diện tiếp theo.

## 29/09/2026

- **Khu vực:** `backend/app/main.py`, `backend/app/http/health.py`, `backend/tests/test_health.py`, shared `backend/app/persistence/database.py`/`backend/tests/test_storage.py`, thẻ T005, `tasks/todo.md`.
- **Thay đổi:** Hoàn tất phần T005-B theo scope được owner xác nhận: startup kiểm tra/migrate SQLite trước khi bật readiness; lỗi storage giữ `NOT_READY`; shutdown dispose engine và xóa readiness. Thay fixture file rỗng bằng SQLite thật, thêm 5 health/lifecycle cases và 2 schema edge cases từ review (reserved-prefix filter và view-only database). Final focused storage 24 PASS; full suite 41 PASS; Ruff/format/Mypy PASS; một Alembic head. Cập nhật T005 `DONE` với handoff và các gate downstream còn PENDING.
- **Mục đích:** Health phản ánh kết quả storage startup và bảo toàn dữ liệu trong failure paths. Skill documentation-and-adrs giúp ghi rõ default timeout, scope split, nguồn framework, evidence và giới hạn Linux/Windows/security tooling mà không thay spec/API contract.

## 29/09/2026

- **Khu vực:** `backend/app/persistence/database.py`, `backend/migrations/env.py`, `backend/migrations/versions/0001_storage.py`, `backend/tests/test_storage.py`, generated `alembic.ini`, task T005.
- **Thay đổi:** Hoàn tất phần T005-A theo scope split được owner xác nhận: migration ledger, FK trên mỗi connection, bounded busy timeout, phát hiện WAL, integrity/schema checks trước mutation, migration trong transaction và fail-safe readonly/corrupt DB. Thêm 22 storage cases; full suite 34 PASS, Ruff/format/Mypy PASS, một Alembic head.
- **Mục đích:** Có checkpoint storage kiểm chứng được trước khi nối health/lifecycle ở T005-B; domain schema và dữ liệu học thật được giữ ngoài scope.

## 29/09/2026

- **Khu vực:** `tasks/t005-database-schema-migrations.md`, `docs/changelogs.md`.
- **Thay đổi:** Ghi audit khi tiếp tục T005: baseline health T003 đạt 8 tests; phát hiện health readiness và fixtures cần sửa ở hai file ngoài allowlist, khiến task cần scope clarification/chia nhỏ trước implementation.
- **Mục đích:** Ghi rõ điểm chặn và evidence để tiếp tục đúng phạm vi; chưa thay application code, allowlist, spec/API contract hoặc đánh dấu T005 hoàn tất.

## 29/09/2026

- **Khu vực:** `tasks/t005-database-schema-migrations.md`, `docs/changelogs.md`.
- **Thay đổi:** Ghi checkpoint tạm dừng T005 sau khi đọc dependency/contract và kiểm tra trạng thái repository; chưa viết test/implementation, chưa chạy verification hay commit T005. Giữ task `TODO` để phiên sau bắt đầu từ bước test RED.
- **Mục đích:** Bảo toàn ngữ cảnh và ranh giới scope cho phiên làm việc tiếp theo theo yêu cầu người dùng.

## 29/09/2026

- **Khu vực:** backend/app/main.py, backend/app/http/health.py, backend/app/platform/config.py, backend/__init__.py, backend/tests/test_health.py, tasks/t003-backend-skeleton.md, tasks/todo.md.
- **Thay đổi:** Hoàn thành task T003: Triển khai FastAPI app factory (`create_app`) và endpoint `GET /api/v1/health` theo đúng normative schema `HealthSummary` (`status`, `version`, `storageStatus`, `bridgeStatus`, `readiness`) và header `Cache-Control: no-store`; cấu hình `AppSettings` với ràng buộc chỉ bind loopback interfaces (127.0.0.1, localhost, ::1) theo threat T-01; kiểm tra storage status trung thực (`OK` khi storage tồn tại, `NOT_READY` khi missing); độc lập hoàn toàn với AI bridge (0 inference call, 0 credential read); quản lý vòng đời ASGI startup/shutdown qua lifespan context; bổ sung 8 tests với 100% độ phủ mã nguồn cho backend app; vượt qua toàn bộ Mypy strict, Ruff và Pytest quality gates.
- **Mục đích:** Cung cấp skeleton backend vững chắc và health probe cho các task tiếp theo (T004 frontend shell, T005 SQLite migration zero).

## 29/09/2026

- **Khu vực:** pyproject.toml, backend/tests/conftest.py, backend/tests/test_toolchain.py, docs/toolchain.md, tasks/t058-python-quality-gates.md, tasks/todo.md.
- **Thay đổi:** Hoàn thành task T058: Cấu hình Python quality gates gồm Ruff linter với quy tắc chuẩn (E, W, F, I, B, C4, UP, ARG, SIM, RUF), MyPy static type checker ở chế độ strict (strict = true, files = ["backend"]), Pytest và Pytest-cov tự động xuất báo cáo Cobertura XML (`coverage.xml`) sau mỗi lần chạy suite; tạo `backend/tests/conftest.py` với fixtures `project_root` và `python_version_info`; tạo `backend/tests/test_toolchain.py` kiểm tra phiên bản Python >=3.12, importable dependencies từ lockfiles, nạp fixtures và cấu hình pyproject; thực hiện negative probes xác nhận phát hiện lỗi assertion, collection, lint và type mismatches; hoàn tất checkpoint CP01.
- **Mục đích:** Cung cấp hạ tầng quality gates, runner và coverage cho backend theo CONSTRAINTS.md, sẵn sàng cho việc triển khai FastAPI app factory tại T003.

## 29/09/2026

- **Khu vực:** package.json, package-lock.json, tsconfig.json, eslint.config.js, vite.config.ts, frontend/tests/toolchain.test.ts, tasks/t002-quality-gates-test-runner-build.md, tasks/todo.md.
- **Thay đổi:** Hoàn thành task T002: Cấu hình frontend quality gates gồm ESLint flat config (eslint.config.js với typescript-eslint và react plugins), TypeScript strict configuration (tsconfig.json), Vite 8 và Vitest runner (vite.config.ts với passWithNoTests=false); bổ sung scripts `lint`, `typecheck`, `test:frontend`, `build` vào package.json; tạo bộ test frontend ban đầu frontend/tests/toolchain.test.ts kiểm tra runtime Node >=20.19.0, assertions và báo cáo BUILD_PENDING_SHELL; xác minh probes bắt lỗi âm/dương cho assertion, type, lint và build thiếu entry point.
- **Mục đích:** Cung cấp hạ tầng quality gates và test runner hoàn chỉnh cho frontend theo CONSTRAINTS.md và UI architecture §10, sẵn sàng cho T004.

## 29/09/2026

- **Khu vực:** package.json, package-lock.json, requirements.lock, requirements-dev.lock, README.md, docs/toolchain.md, tasks/t001-toolchain-repository-skeleton.md, tasks/todo.md.
- **Thay đổi:** Hoàn thành task T001: Khóa phiên bản toolchain frontend (React 19, TypeScript 5.8, Vite 8) qua package.json và package-lock.json; khóa phiên bản toolchain backend (FastAPI 0.141, Pydantic 2.13, SQLAlchemy 2.1, Alembic 1.20, Uvicorn 0.54, HTTPX 0.28, Ruff 0.16, MyPy 2.3, Pytest 9.1, Pytest-cov 7.1, Pip-tools 7.6) qua pyproject.toml và requirements.lock / requirements-dev.lock; tạo README.md và docs/toolchain.md hướng dẫn cài đặt và công bố trạng thái readiness của lệnh; xác minh clean install tái lập độc lập và cấu hình .gitignore.
- **Mục đích:** Thiết lập nền tảng toolchain có thể tái lập cho toàn bộ các task downstream bắt đầu từ T002 và T058, tuân thủ CONSTRAINTS.md và AGENTS.md.

## 29/09/2026

- **Khu vực:** CONSTRAINTS.md, AGENTS.md, tasks/_template.md, tasks/t001–t066, tasks/todo.md, docs/task-plan.md, docs/project-context.md.
- **Thay đổi:** Hoàn thiện bản planning thành 66 task nhỏ và 22 checkpoints; tách quiz generation/draft/submission/feedback, các UI flow, tool runners, benchmark và Windows/recovery evidence. Sửa nội dung ghép sai ở 9 task card, commit proposals, scope allowlists, route wiring, dependency order và references. Bổ sung command owner/readiness registry, planned numeric configuration và ranh giới canonical learning storage/diagnostic redaction, giữ các quality thresholds.
- **Mục đích:** Có kế hoạch bắt đầu được từ T001, với T013 conformance là prerequisite cho business contract; không đánh dấu application tests/release evidence đã PASS. Kiểm tra planning có 66 unique cards, 225 dependency edges không chu kỳ, 22 checkpoints và link/current-vs-planned outputs đúng; lưu evidence ở docs/reviews/planning-validation-001.md. Mọi implementation task vẫn TODO; không application code, real provider request, commit, remote hay PR được tạo trong session này.

## 29/09/2026

- **Khu vực:** `CONSTRAINTS.md`, `AGENTS.md`, `tasks/`, `docs/task-plan.md`, `docs/project-context.md`.
- **Thay đổi:** Tạo quality bar bảo thủ với floor, type/lint/test/coverage/security/accessibility/performance gates; tạo persistent agent context; chia implementation thành 46 task cards nhỏ với dependencies, checkpoints, verification, stop conditions và commit proposals; thêm todo/plan pointers và cập nhật project map.
- **Mục đích:** Chuyển design baseline `READY_FOR_PLANNING` thành kế hoạch implementation có thể kiểm chứng, không viết application code, không tạo remote/commit hoặc gọi provider.

## 29/09/2026

- **Khu vực:** `docs/spec.md`, `docs/api-contract.md`, `docs/ui-architecture.md`, `docs/security-review.md`, `docs/observability-plan.md`, `docs/adr/0001-architecture.md`, `docs/project-context.md`, `docs/reviews/spec-architecture-review-001.md`.
- **Thay đổi:** Loại bỏ các câu hiện hành còn tham chiếu OQ/policy chưa chốt; chuẩn hóa model `gemini-3.8-flash-high`, revision conflict, local SpeechSynthesis, hard timeout/cancellation budgets, runbook first-run, ADR-0004 authority và đánh dấu phần review cũ là historical. Sửa các acceptance/UI/API mâu thuẫn (LWW, missing IPA/link, offline audio, FTS5 boundary) và thêm final doubt-driven recheck với không còn Critical/Major design blocker. Giữ các runtime/profile/benchmark/`CONSTRAINTS.md` items là evidence gates.
- **Mục đích:** Kết thúc design-blocked state một cách nhất quán, không tuyên bố application code hoặc runtime/security tests đã pass.

## 29/09/2026

- **Khu vực:** status headers, project context, ADR-0002/0003, review disposition, security/API audio wording.
- **Thay đổi:** Hoàn tất đồng bộ sau closure pass; ghi `READY_FOR_PLANNING` cho spec/architecture/review, đánh dấu historical blocker sections, chuyển audio sang SpeechSynthesis local và loại bỏ các câu còn tuyên bố OQ/paid-fallback/LWW chưa chốt.
- **Mục đích:** Kết thúc design-blocked state đúng theo ADR-0004; giữ `CONSTRAINTS.md` và runtime tests làm planning/implementation gates.

## 29/09/2026

- **Khu vực:** `docs/spec.md`, `docs/api-contract.md`, `docs/ui-architecture.md`, `docs/security-review.md`, `docs/observability-plan.md`, `docs/reviews/spec-architecture-review-001.md`.
- **Thay đổi:** Đồng bộ các contract theo ADR-0004: revision conflict thay LWW, five-box SRS/quiz snapshot/limits, local SpeechSynthesis, WCAG 2.2 AA target, benchmark/timeout gates, journal recovery, dashboard formulas và OQ overlay. Đánh dấu các R2 section cũ là historical và dùng closure table làm disposition hiện hành.
- **Mục đích:** Giữ tài liệu nhất quán sau khi owner ủy quyền chốt mọi blocker; vẫn phân biệt decision closure với runtime verification.

## 29/09/2026

- **Khu vực:** `docs/adr/0004-v1-product-policy-and-operational-baseline.md`, spec/API/UI/security/observability/ADR-0001/project context/review.
- **Thay đổi:** Chốt toàn bộ OQ-01–OQ-14 bằng các mặc định v1 bảo thủ: provider/model/cost policy, five-box SRS, quiz snapshot/rubric, identity/conflict/journal, Windows launcher/autosave, local SpeechSynthesis, WCAG 2.2 AA, benchmark/timeouts, dashboard formulas, secret/recovery boundary và legacy Markdown. Chuyển architecture/spec/review sang `READY_FOR_PLANNING`; giữ runtime/CONSTRAINTS gates cho planning/implementation.
- **Mục đích:** Kết thúc trạng thái block theo ủy quyền của owner mà không tuyên bố code/runtime/security tests đã pass.

## 29/09/2026

- **Khu vực:** `docs/spec.md`, `docs/security-review.md`, `docs/adr/0002-antigravity-loopback-trust-boundary.md`, `docs/reviews/spec-architecture-review-001.md`.
- **Thay đổi:** Ghi nhận owner không cấm paid fallback về nguyên tắc; làm rõ fallback trả phí chỉ được dùng khi READY policy khai báo route/provider/model/billing, disclosure/consent và quyền hạn/quota tương ứng.
- **Mục đích:** Tách “không cấm” khỏi việc tự cấp phép hoặc tự bật fallback; giữ các quyết định provider, route, entitlement, quota, retention và region ở R2-002.

## 29/09/2026

- **Khu vực:** `docs/api-contract.md`, `docs/spec.md`, `docs/ui-architecture.md`, `docs/security-review.md`, `docs/adr/0001-architecture.md`, `docs/adr/0003-ai-consent-and-revocation.md`.
- **Thay đổi:** Bổ sung immutable policy digest/structured disclosure fields, exact scope and dispatch-rule authorization, cross-process consent fencing, append-only consent events và redacted Operation provenance; sửa retry feedback bằng key mới; đánh dấu audio disabled tới OQ-06; khôi phục câu chữ ADR-0001 ở dạng historical với supersession notice; cập nhật AC-27/AC-34 và test cases.
- **Mục đích:** Xử lý các finding fresh review mà không tự chọn provider/quota/billing/retention/region hoặc hạ tiêu chuẩn bảo mật.

## 29/09/2026

- **Khu vực:** API/spec/UI/security/observability/ADR-0001/ADR-0003 và review `spec-architecture-review-001.md`.
- **Thay đổi:** Reconcile fresh adversarial review: ràng buộc policy theo digest + scope/provider/model/route/billing, fence consent cross-process, event audit/provenance, retry feedback bằng key mới, AC-27/AC-34 chính xác hơn, audio disabled khi OQ-06 chưa sẵn sàng và disclosure schema có trường bắt buộc. Ghi nhận R3-001–R3-013 cùng các release/runtime gates.
- **Mục đích:** Không để consent boolean, smoke test hoặc CLI wording vượt qua policy cloud, auth/profile, audio và retry boundaries; giữ R2-002 cùng các blocker khác ở trạng thái chưa sẵn sàng.

## 29/09/2026

- **Khu vực:** `docs/adr/0003-ai-consent-and-revocation.md`; spec/API/UI/security/observability, project context và review ledger.
- **Thay đổi:** Áp dụng phê duyệt của owner cho consent AI local default-deny: disclosure trước lần gửi đầu tiên, lưu policy version/choice, revoke offline chặn dispatch mới và giữ học cục bộ. Thêm API singleton/ETag/idempotency/dispatch gate, UI `/status#ai-consent`, AC-37–40, CONSENT-01–10, threat T-22 và telemetry redaction.
- **Mục đích:** Xử lý phần consent của R2-002 mà không giả định provider/model/quota/billing/retention/region đã được duyệt; giữ R2-002 blocked và không viết application code, gọi cloud hoặc lưu credential.

## 29/09/2026

- **Khu vực:** `docs/adr/0002-antigravity-loopback-trust-boundary.md`; supersession notice ở ADR-0001; spec/API/security/observability, bridge runbook, project context và review ledger.
- **Thay đổi:** Áp dụng phê duyệt của owner cho HTTP loopback + proxy API key với Antigravity v4.8.4 và rủi ro giả mạo process cục bộ được chấp nhận. Bỏ yêu cầu bridge IPC/per-launch/process authentication chưa có cơ sở; thêm profile/preflight/error contract, AC-36/BR-AUTH-01–08 và làm rõ ranh giới trace tại app→proxy. Giữ nguyên thân ADR-0001, không sửa `CONSTRAINTS.md` hay browser session.
- **Mục đích:** Xử lý R2-001 ở cấp thiết kế mà không giả định đã pass runtime/security tests. R2-002 và các blocker khác vẫn mở; không đổi `REVIEW_STATUS`, viết application code, gọi inference hoặc thay cấu hình/credential thực tế.

## 29/09/2026

- **Khu vực:** `docs/spec.md`, `docs/api-contract.md`, `docs/security-review.md`, `docs/project-context.md`, `docs/reviews/spec-architecture-review-001.md`
- **Thay đổi:** Ghi nhận owner xác nhận Antigravity Tools v4.8.4 và đối chiếu tag tới commit nguồn đã kiểm tra. Chuyển điểm cần làm rõ của R2-001 từ phiên bản sang quyết định ranh giới tin cậy; ghi phương án loopback/API-key cùng trade-off nhưng chưa áp dụng.
- **Mục đích:** Không hỏi lại phiên bản đã biết và không coi xác nhận phiên bản là phê duyệt thay đổi xác thực. Chưa sửa cấu hình, dùng credential, viết application code hoặc đổi review status.

## 29/09/2026

- **Khu vực:** `docs/spec.md`, `docs/api-contract.md`, `docs/security-review.md`, `docs/project-context.md`, `docs/reviews/spec-architecture-review-001.md`
- **Thay đổi:** Ghi nhận bridge do owner xác nhận là Antigravity Tools / Antigravity-Manager; phân biệt proxy API key với token/session Google; sửa cách gọi CLI trong luồng hiện hành. Bổ sung bằng chứng upstream theo commit về auth `auto/off`, bearer-key và giới hạn xác thực process; ghi rõ phiên bản cài đặt chưa biết.
- **Mục đích:** Thu hẹp R2-001 bằng nguồn chính thức của dự án mà không tự chấp thuận auth/model/billing, không thay đổi cấu hình, không đọc credential và không đóng blocker khi chưa đủ bằng chứng. Giữ `REVIEW_STATUS: BLOCKED`.

## 29/09/2026

- **Khu vực:** post-apply review, API/UI contracts, security/observability and project context
- **Thay đổi:** Chạy final doubt-driven recheck; sửa lookup idempotency/operation, feedback failure history, quiz answer examples, autosave/PATCH reconciliation, bootstrap wording, legacy date example và runbook retry semantics. Ghi nhận residual R2 owner gates và giữ `REVIEW_STATUS: BLOCKED`.
- **Mục đích:** Không tuyên bố readiness khi bridge auth/consent, source conflict/recovery, quiz/SRS rules, legacy mapping, benchmark, launcher lifecycle, audio/accessibility và recovery policy vẫn chưa được owner chốt.

## 29/09/2026

- **Khu vực:** `docs/reviews/spec-architecture-review-001.md`, `docs/api-contract.md`, `docs/observability-plan.md`, `docs/ui-architecture.md`
- **Thay đổi:** Chạy post-apply doubt-driven review; bổ sung residual blocker ledger R2-001–R2-020, feedback history/failure retrieval, status metrics/lifecycle, autosave/PATCH operation reconciliation, quiz answer restoration và error recovery DTO.
- **Mục đích:** Giữ `REVIEW_STATUS: BLOCKED` khi còn decision gates thay vì tự hạ chuẩn hoặc chuyển thủ công sang planning.

## 29/09/2026

- **Khu vực:** `docs/spec.md`, `docs/api-contract.md`, `docs/ui-architecture.md`, `docs/reviews/spec-architecture-review-001.md`
- **Thay đổi:** Bổ sung implementation gates trong spec, source/projection write protocol trong API, provisional conflict/startup behavior trong UI, và resolution ledger cho toàn bộ Critical/Major findings.
- **Mục đích:** Phân biệt rõ finding đã xử lý bằng contract với finding còn cần owner quyết định, không hạ chuẩn hoặc đổi `REVIEW_STATUS` thủ công.

## 29/09/2026

- **Khu vực:** architecture contracts, security/observability docs, ADR, spec clarifications, review reconciliation và `docs/runbooks/`
- **Thay đổi:** Áp dụng các finding đã được chấp thuận từ `spec-architecture-review-001`: hoàn thiện DTO/error/operation/revision contracts; làm rõ Vietnamese meaning search, Markdown round-trip/source revisions, quiz restore/SRS handoff, startup/offline/session states, authenticated loopback bridge, safe-path residuals, local-only telemetry defaults và runbooks.
- **Mục đích:** Giảm mâu thuẫn và các điểm không thể kiểm chứng mà không tự đóng các product OQ về provider, SRS/rubric, quiz snapshot, audio, conflict, backup, accessibility hoặc performance.

## 29/09/2026

- **Khu vực:** `docs/reviews/spec-architecture-review-001.md` và `docs/changelogs.md`
- **Thay đổi:** Thực hiện adversarial review độc lập cho spec và bộ tài liệu architecture; ghi nhận các finding về OQ chưa chốt, mâu thuẫn Markdown/SQLite và LWW/ETag, FTS5/search, quiz/SRS/autosave, bootstrap/bridge security, API schema, offline/runtime, observability và acceptance criteria.
- **Mục đích:** Chặn việc lập kế hoạch triển khai khi thiết kế còn rủi ro hoặc không thể kiểm chứng; yêu cầu owner review và chỉ áp dụng các finding được chấp thuận.

## 29/09/2026

- **Khu vực:** `docs/api-contract.md`, `docs/ui-architecture.md`, `docs/security-review.md`, `docs/observability-plan.md`, `docs/adr/0001-architecture.md`
- **Thay đổi:** Tạo contract REST/OpenAPI v1, kiến trúc UI/routes/flows, threat model bảo mật, kế hoạch structured logs/metrics/traces/alerts và ADR chọn React + TypeScript + Vite, FastAPI/Python, SQLite + SQLAlchemy/Alembic trên runtime Windows loopback.
- **Mục đích:** Chuyển spec sản phẩm thành architecture có thể triển khai mà không viết application code; giữ các `OQ-*` chưa chốt ở trạng thái review, ghi nguồn tài liệu chính thức và nêu rõ temporary constraints snapshot vì `CONSTRAINTS.md` chưa tồn tại.

## 29/09/2026

- **Khu vực:** `docs/spec.md` và `docs/changelogs.md`
- **Thay đổi:** Chốt hướng runtime local + inference cloud qua local OpenAI-compatible bridge; ghi nhận smoke test thật với `GET /health`, `GET /v1/models` và `POST /v1/chat/completions`. Bổ sung yêu cầu prompt template có version/placeholders, JSON response validation, lưu feedback theo attempt/question/model/prompt version và bảo vệ API key ở backend.
- **Mục đích:** Xác định contract tích hợp AI để chấm/nhận xét, trả feedback cho frontend và truy xuất lịch sử mà không đưa secret vào frontend hoặc database.

- **Khu vực:** `docs/spec.md` và `docs/changelogs.md`
- **Thay đổi:** Tạo spec chính thức từ biên bản product discovery, gồm problem statement, goals, users, journeys, capability map, requirements, business rules, dữ liệu, auth/authorization, UI states, accessibility, security, performance, scope/non-goals, acceptance criteria, open questions và assumptions; ghi trạng thái `SPEC_STATUS: DRAFT_REVIEW_PENDING`.
- **Mục đích:** Tạo bản review với capability gắn nhu cầu, 35 acceptance criteria có điều kiện/kết quả kiểm chứng, và đánh giá những điểm còn chặn việc chốt API, UI hoặc task triển khai; giữ các quyết định chưa rõ trong open questions và không tự chọn framework.

- **Khu vực:** `docs/interviews/product-discovery-001.md` và `docs/changelogs.md`
- **Thay đổi:** Tạo biên bản product discovery sau khi người dùng xác nhận `FINALIZE INTERVIEW`; ghi mục tiêu, người dùng, journeys, phạm vi/non-goals, dữ liệu và quyền truy cập, business rules, edge cases, yêu cầu phi chức năng, acceptance criteria sơ bộ, quyết định đã chốt, giả định và câu hỏi còn mở.
- **Mục đích:** Làm đầu vào viết spec dựa trên interview, phân biệt các quyết định mới với tài liệu tham chiếu và tránh coi những điểm chưa chốt là yêu cầu đã thống nhất.

- **Khu vực:** Git repository và `docs/project-context.md`
- **Thay đổi:** Xác nhận project root, khởi tạo Git với branch mặc định cục bộ `main`, và cập nhật context về trạng thái repository chưa có commit/remote.
- **Mục đích:** Chuẩn bị nền tảng version control cho giai đoạn thiết kế.


- **Khu vực:** `docs/project-context.md`
- **Thay đổi:** Ghi lại repository map, trạng thái Git, runtime/toolchain, frontend/backend hiện có, giới hạn, giả định và câu hỏi cho session tiếp theo.
- **Mục đích:** Tạo context bền vững cho giai đoạn thiết kế mà không thêm application code hoặc sửa spec.


- **Khu vực:** `AGENT.md`
- **Thay đổi:** Quy định agent phải sử dụng skill `agent-skills:documentation-and-adrs` khi tạo hoặc cập nhật tài liệu kỹ thuật, spec, ADR, API documentation, README hoặc changelog.
- **Mục đích:** Đảm bảo tài liệu ghi lại bối cảnh, lý do, đánh đổi và hệ quả của các quyết định quan trọng.

## 28/09/2026

- **Khu vực:** `AGENT.md`
- **Thay đổi:** Thêm quy định bắt buộc agent cập nhật `docs/changelogs.md` cho mọi thay đổi trong workspace.
- **Mục đích:** Đảm bảo mọi thay đổi đều có lịch sử theo dõi thống nhất.

## 28/09/2026

- **Khu vực:** `docs/`
- **Thay đổi:** Thêm quy định changelog và tạo cấu trúc tài liệu `development/spec`, `development/tasks`, `deployment/guide`.
- **Mục đích:** Theo dõi mọi thay đổi do agent thực hiện theo ngày.

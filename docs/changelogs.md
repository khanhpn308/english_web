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

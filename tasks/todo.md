# Implementation task checklist

**Planning state:** Kế hoạch đã có thẻ/graph; mọi implementation task dưới đây vẫn `TODO`.  
**Canonical plan:** [docs/task-plan.md](../docs/task-plan.md).  
**Next ready task:** [T001](t001-toolchain-repository-skeleton.md).  
**Handoff rule:** Chỉ check item khi thẻ tương ứng có acceptance/verification evidence và task status `DONE`. PENDING environment không được check thành PASS.

## Ordered task list

- [x] [T001](t001-toolchain-repository-skeleton.md): Pin toolchain và repository skeleton
- [x] [T002](t002-quality-gates-test-runner-build.md): Frontend lint, typecheck và test runner
- [x] [T058](t058-python-quality-gates.md): Python lint, types, pytest và coverage runner
- [ ] [T003](t003-backend-skeleton.md): FastAPI app factory và health
- [ ] [T004](t004-frontend-shell-routes.md): React shell, route map và landmarks
- [ ] [T005](t005-database-schema-migrations.md): SQLite connection và migration zero
- [ ] [T053](t053-quality-security-gates.md): Coverage và quality-floor guard
- [ ] [T063](t063-security-scan-tooling.md): Secret và code/dependency security scan gates
- [ ] [T013](t013-contract-conformance.md): Chuẩn hóa ví dụ và quyết định contract còn mơ hồ
- [ ] [T006](t006-api-core-contract-foundation.md): Bootstrap session và HTTP guards
- [ ] [T014](t014-operations-idempotency.md): Durable operation ledger và idempotency
- [ ] [T017](t017-typed-api-client.md): Generated DTO và typed fetch client
- [ ] [T066](t066-browser-bootstrap.md): Trusted browser bootstrap page
- [ ] [T052](t052-browser-test-harness.md): Browser harness với local fake API/bridge
- [ ] [T062](t062-architecture-gates.md): Architecture import boundary gates
- [ ] [T015](t015-consent-api.md): Persist consent singleton và GET/PUT/DELETE
- [ ] [T007](t007-bridge-policy-consent-adapter.md): Antigravity transport adapter với fake proxy
- [ ] [T016](t016-dispatch-fence.md): Consent admission fence trước AI dispatch
- [ ] [T018](t018-consent-ui.md): Consent dialog và Status panel
- [ ] [T019](t019-vocabulary-schema.md): Schema vocabulary, source links và preview
- [ ] [T008](t008-lookup-api-vertical-slice.md): POST lookup trả preview đã validate
- [ ] [T009](t009-lookup-ui-vertical-slice.md): Lookup UI gọi API thật qua client
- [ ] [T010](t010-error-handling-recovery.md): Typed UI recovery cho common error codes
- [ ] [T011](t011-observability-instrumentation.md): Local JSON logs, correlation và span boundary
- [ ] [T012](t012-ci-pipeline.md): CI lõi cho build và tests
- [ ] [T020](t020-markdown-parser.md): Lossless Markdown parser/serializer
- [ ] [T026](t026-search-projection.md): Vietnamese normalized n-gram projection
- [ ] [T031](t031-review-schema.md): Review/card schema và deterministic SRS
- [ ] [T021](t021-safe-source-files.md): Allowlisted Windows source file adapter
- [ ] [T022](t022-source-journal.md): Durable source journal và crash reconciliation
- [ ] [T023](t023-source-sync.md): Startup/watcher sync và source API
- [ ] [T024](t024-save-api.md): Explicit save preview vào Markdown và cards
- [ ] [T025](t025-save-ui-audio.md): Save lookup preview và local pronunciation
- [ ] [T027](t027-search-api.md): Search/detail API có cursor và filters
- [ ] [T028](t028-search-ui.md): Search/detail read flow
- [ ] [T029](t029-edit-api.md): Revision-safe word-form edit API
- [ ] [T030](t030-edit-ui.md): Edit form và conflict dialog
- [ ] [T032](t032-review-api.md): Review queue và review event API
- [ ] [T033](t033-review-ui.md): Flashcard review flow
- [ ] [T059](t059-quiz-scoring.md): Pure quiz scoring và weakest-rating oracle
- [ ] [T034](t034-quiz-schema.md): Quiz immutable snapshot schema
- [ ] [T035](t035-quiz-api.md): Quiz creation và snapshot retrieval API
- [ ] [T036](t036-quiz-ui.md): Quiz builder UI dùng generation API
- [ ] [T047](t047-quiz-autosave-api.md): Quiz answer draft API với revision
- [ ] [T050](t050-quiz-runner-ui.md): Quiz runner và revision-aware autosave UI
- [ ] [T048](t048-quiz-submit-api.md): Quiz submission và atomic SRS handoff
- [ ] [T049](t049-writing-feedback-api.md): Writing feedback API và history retry
- [ ] [T051](t051-quiz-result-feedback-ui.md): Submit/result và writing feedback UI
- [ ] [T037](t037-dashboard-formulas.md): Dashboard summary API và streak formulas
- [ ] [T046](t046-metrics-alerts-runbooks.md): Local RED metrics và operational Status API
- [ ] [T060](t060-status-ui.md): Operational Status screen và consent integration
- [ ] [T038](t038-dashboard-ui.md): Learning Dashboard UI
- [ ] [T061](t061-alerts-runbooks.md): Local symptom alerts và runbook links
- [ ] [T039](t039-launcher.md): Windows launcher single-instance/bootstrap
- [ ] [T040](t040-first-run-recovery.md): Native first-run configuration và protected key store
- [ ] [T054](t054-restore-recovery-drill.md): Staging restore và migration recovery drill
- [ ] [T041](t041-security-hardening.md): Browser/API/filesystem hardening evidence
- [ ] [T042](t042-performance-fixture.md): Deterministic100k search benchmark fixture
- [ ] [T065](t065-search-performance-evidence.md): Search browser timing trên100k fixture
- [ ] [T064](t064-ui-performance-harness.md): Local Lighthouse performance harness
- [ ] [T043](t043-accessibility-evidence.md): WCAG 2.2 AA browser/manual evidence
- [ ] [T055](t055-ai-content-evidence.md): Human-reviewed semantic fixture và optional AI smoke
- [ ] [T056](t056-windows-package.md): Reproducible Windows package và shortcut
- [ ] [T044](t044-release-contract-audit.md): Generated contract and cross-doc audit
- [ ] [T045](t045-git-release-hygiene.md): Git hooks, branch and commit hygiene
- [ ] [T057](t057-release-verification.md): Windows/offline release evidence matrix

## Checkpoints

- [x] CP01: T001, T002, T058 — review criteria, applicable checks, integration và recorded evidence trước task kế tiếp.
- [ ] CP02: T003, T004, T005 — review criteria, applicable checks, integration và recorded evidence trước task kế tiếp.
- [ ] CP03: T053, T063, T013 — review criteria, applicable checks, integration và recorded evidence trước task kế tiếp.
- [ ] CP04: T006, T014, T017 — review criteria, applicable checks, integration và recorded evidence trước task kế tiếp.
- [ ] CP05: T066, T052, T062 — review criteria, applicable checks, integration và recorded evidence trước task kế tiếp.
- [ ] CP06: T015, T007, T016 — review criteria, applicable checks, integration và recorded evidence trước task kế tiếp.
- [ ] CP07: T018, T019, T008 — review criteria, applicable checks, integration và recorded evidence trước task kế tiếp.
- [ ] CP08: T009, T010, T011 — review criteria, applicable checks, integration và recorded evidence trước task kế tiếp.
- [ ] CP09: T012, T020, T026 — review criteria, applicable checks, integration và recorded evidence trước task kế tiếp.
- [ ] CP10: T031, T021, T022 — review criteria, applicable checks, integration và recorded evidence trước task kế tiếp.
- [ ] CP11: T023, T024, T025 — review criteria, applicable checks, integration và recorded evidence trước task kế tiếp.
- [ ] CP12: T027, T028, T029 — review criteria, applicable checks, integration và recorded evidence trước task kế tiếp.
- [ ] CP13: T030, T032, T033 — review criteria, applicable checks, integration và recorded evidence trước task kế tiếp.
- [ ] CP14: T059, T034, T035 — review criteria, applicable checks, integration và recorded evidence trước task kế tiếp.
- [ ] CP15: T036, T047, T050 — review criteria, applicable checks, integration và recorded evidence trước task kế tiếp.
- [ ] CP16: T048, T049, T051 — review criteria, applicable checks, integration và recorded evidence trước task kế tiếp.
- [ ] CP17: T037, T046, T060 — review criteria, applicable checks, integration và recorded evidence trước task kế tiếp.
- [ ] CP18: T038, T061, T039 — review criteria, applicable checks, integration và recorded evidence trước task kế tiếp.
- [ ] CP19: T040, T054, T041 — review criteria, applicable checks, integration và recorded evidence trước task kế tiếp.
- [ ] CP20: T042, T065, T064 — review criteria, applicable checks, integration và recorded evidence trước task kế tiếp.
- [ ] CP21: T043, T055, T056 — review criteria, applicable checks, integration và recorded evidence trước task kế tiếp.
- [ ] CP22: T044, T045, T057 — review criteria, applicable checks, integration và recorded evidence trước task kế tiếp.

## Execution state

- Current task: T058 đã hoàn thành và kiểm chứng (pytest, ruff, mypy PASS, coverage.xml emitted). Checkpoint CP01 hoàn tất.
- Next task: T003 (FastAPI app factory và health) theo checkpoint CP02.
- T013: mandatory contract-conformance trước behavior phụ thuộc; clarification ghi trong ADR/task output.
- Remote/commit/installed Windows/provider evidence: chưa có; Git/real inference execution theo authority và stop conditions.
- Task ID là identifier ổn định; danh sách trên là dependency order, không sort theo số ID.

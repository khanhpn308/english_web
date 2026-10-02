# Implementation task checklist

**Planning state:** T001/T002/T058/T003/T004/T005/T053/T063/T013/T006 đã có evidence hoàn tất; trạng thái các task còn lại theo checklist dưới đây.
**Canonical plan:** [docs/task-plan.md](../docs/task-plan.md).  
**Next ready work:** see dependency graph/current ready tasks in docs/task-plan.md (e.g. T075, T008, T021; T018 is blocked by T075 and T076).
**Handoff rule:** Chỉ check item khi thẻ tương ứng có acceptance/verification evidence và task status `DONE`. PENDING environment không được check thành PASS.

## Ordered task list

- [x] [T001](t001-toolchain-repository-skeleton.md): Pin toolchain và repository skeleton
- [x] [T002](t002-quality-gates-test-runner-build.md): Frontend lint, typecheck và test runner
- [x] [T058](t058-python-quality-gates.md): Python lint, types, pytest và coverage runner
- [x] [T003](t003-backend-skeleton.md): FastAPI app factory và health
- [x] [T004](t004-frontend-shell-routes.md): React shell, route map và landmarks
- [x] [T005](t005-database-schema-migrations.md): SQLite connection và migration zero
- [x] [T053](t053-quality-security-gates.md): Coverage và quality-floor guard
- [x] [T063](t063-security-scan-tooling.md): Secret và code/dependency security scan gates
- [x] [T013](t013-contract-conformance.md): Chuẩn hóa ví dụ và quyết định contract còn mơ hồ
- [x] [T006](t006-api-core-contract-foundation.md): Bootstrap session và HTTP guards
- [x] [T014](t014-operations-idempotency.md): Durable operation ledger và idempotency
- [x] [T017](t017-typed-api-client.md): Generated DTO và typed fetch client
- [x] [T066](t066-browser-bootstrap.md): Trusted browser bootstrap page
- [x] [T052](t052-browser-test-harness.md): Browser harness với local fake API/bridge
- [x] [T062](t062-architecture-gates.md): Architecture import boundary gates — implementation green (40 tests, both tools, dependency scan).
- [x] [T015](t015-consent-api.md): Persist consent singleton và GET/PUT/DELETE
- [x] [T007](t007-bridge-policy-consent-adapter.md): Antigravity transport adapter với fake proxy
- [x] [T016](t016-dispatch-fence.md): Consent admission fence trước AI dispatch
- [ ] [T075](t075-shadcn-ui-foundation.md): shadcn/ui foundation & Tailwind integration
- [ ] [T076](t076-app-shell-shadcn-migration.md): AppShell shadcn/ui & semantic design-system migration
- [ ] [T018](t018-consent-ui.md): Consent dialog và Status panel (BLOCKED_BY_T075_T076)
- [x] [T019](t019-vocabulary-schema.md): Schema vocabulary, source links và preview
- [ ] [T008](t008-lookup-api-vertical-slice.md): POST lookup trả preview đã validate
- [ ] [T009](t009-lookup-ui-vertical-slice.md): Lookup UI gọi API thật qua client
- [ ] [T010](t010-error-handling-recovery.md): Typed UI recovery cho common error codes
- [ ] [T011](t011-observability-instrumentation.md): Local JSON logs, correlation và span boundary
- [ ] [T012](t012-ci-pipeline.md): CI lõi cho build và tests
- [x] [T020](t020-markdown-parser.md): Lossless Markdown parser/serializer
- [x] [T026](t026-search-projection.md): Vietnamese normalized n-gram projection
- [x] [T031](t031-review-schema.md): Review/card schema và deterministic SRS — DONE: 60 SRS cases, 226 targeted/424 full Python tests; owner-authorized legacy-head maintenance preserves lineage/history; coverage, architecture, security and check:task all exit 0.
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
- [x] [T059](t059-quiz-scoring.md): Pure quiz scoring và weakest-rating oracle — independently re-audited PASS; 45 scoring/60 SRS tests, 100% scoring line/branch coverage; integrated candidate check:task exit0 (763 Python, 38 frontend, 40 architecture tests, changed coverage100%, total92.78%, zero security findings). Historical automated FAILED run preserved.
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
- [x] CP03: T053, T063, T013 — review criteria, applicable checks, integration và recorded evidence trước task kế tiếp.
- [x] CP04: T006, T014, T017 — review criteria, applicable checks, integration và recorded evidence trước task kế tiếp.
- [x] CP05: T066, T052, T062 — review criteria, applicable checks, integration và recorded evidence trước task kế tiếp.
- [x] CP06: T015, T007, T016 — review criteria, applicable checks, integration và recorded evidence trước task kế tiếp.
- [ ] CP06A: T075, T076 — review criteria, design system tokens, AppShell equivalence, build/test trước task kế tiếp.
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

- Frontend architecture & task-plan remediation (02/10/2026): T075 (shadcn/ui foundation & Tailwind integration) và T076 (AppShell shadcn/ui migration) đã được bổ sung vào canonical plan trước T018. T004 giữ nguyên DONE (mọi invariants về routing, landmarks, accessibility, ErrorBoundary được bảo toàn). T018 ở trạng thái BLOCKED_BY_T075_T076. Toàn bộ 13 downstream UI task cards đã được cập nhật phụ thuộc vào T076 và tuân thủ canonical design system shadcn/ui. Ready work kế tiếp trên nhánh UI là T075.

- T016 DONE, verified linear integration after T020/T026/T031 on frozen main `3b4faf52ba63aac30d6ea0443746eff846eb62da`: preserved source `56b8e83`, transplanted as `5eafd57`, and realigned admission to `0006_ai_admission` after `0005_review` without changing table/coordinator semantics. All 60 admission races/restart cases, preceding-task suites (24/25/60), 533 full Python tests, changed coverage 97.22%/total 92.69%, architecture, static, fast/task and zero-finding security gates pass. Generated contracts are unchanged; only review's historical migration test needed INTEGRATION_TEST_REMEDIATION beyond T016 scope. Main promotion must be ff-only after its unchanged-base check; CP06 stays unchecked and no push is authorized. Current integration evidence is in the T016 card; the source-only snapshot below remains historical.

- T016 DONE on authorized base `de9725ba1e79658f5bebc583ba09422692e5df9c`: migration `0005_ai_admission` follows `0004_vocabulary`; immutable per-operation evidence commits atomically with the final consent revision/version/digest/rule fence before transport. All 60 admission tests, 150 consent tests, 16 vocabulary-storage tests and 424 full Python tests pass. Two spawn processes prove revoke-first/ABA denial and admission-first completion while revoke commits during blocked transport; UNKNOWN recovery never redispatches. Historical migration tests now target their own revision/ancestry. Changed coverage 97.22%; complete check:task, scoped static checks, architecture, security and deterministic contract exports pass. Full Ruff retains the sole byte-identical inherited RUF100 finding, explicitly classified in the card. CP06 remains unchecked; all changes unstaged/uncommitted, no push.

- T015 semantic remediation DONE: resumed-session verification has 137 consent tests (47 added to the inherited 90), 14 operation tests and 279 full Python tests. Complete policy canonicalization, corrupt-storage denial, overlapping two-connection CAS, atomic receipts/replay and UTC event timestamps are proven. T016 remains TODO with T007 DONE; CP06 remains unchecked. The historical semantic source snapshot was IMPLEMENTATION_DONE_BASELINE_BLOCKED by T007 formatting and T053 generated-file coverage classification; exact checks and ownership are in the T015 card. The prerequisite-aware integration candidate starts from authorized post-CP05/T007 main `bc0ff937`; post-CP05 architecture compatibility now passes seven contracts/40 gate tests, 150 consent tests and 332 full Python tests. Main is NOT PROMOTED: complete-candidate check:task still fails on T053 generated DTO coverage classification. Remediation-only coverage is 100%; this does not clear that required aggregate gate.

- Current task: T006 hoàn tất server-side bootstrap/session/HTTP guards; focused session tests, full quality/security gate và build có evidence trong thẻ T006. T066/T052 tiếp tục browser bootstrap/integration evidence.
- T005 handoff: cả hai phần SQLite/migrations và health/lifecycle hoàn tất; full backend suite 41 PASS, focused storage 24 PASS, Ruff/format/Mypy PASS, một Alembic head. Pending release/tooling checks ghi trong thẻ T005.
- Next task: T052 (Browser test harness), T062 (Architecture import boundary gates) theo dependency graph.
- T013: contract conformance hoàn tất; generated DTO/runtime verification tiếp tục thuộc T017 và downstream tasks.
- T005-A commit: `8adf972`; T004 commit atomic; T005-B commit theo Git history của branch `feature/task-t005-sqlite-migrations`. Chưa push; Windows/provider evidence còn pending theo owner tasks.
- Task ID là identifier ổn định; danh sách trên là dependency order, không sort theo số ID.

## Local agent infrastructure (explicit owner request, outside product checkpoints)

- [x] [T067](t067-orchestrator-core.md): Typed contracts/state, bounded subprocesses, CLI adapters and safe worktrees.
- [x] [T068](t068-orchestrator-workflow.md): Autonomous role/fix pipeline, isolated concurrent runs and serialized integration.
- [x] [T069](t069-orchestrator-quality.md): Include infrastructure in test/type/coverage gates.
- [x] [T070](t070-orchestrator-baseline-lint.md): Mechanical inherited Ruff baseline remediation.
- [ ] [T071](t071-orchestrator-planning-contract.md): Exact planning constraints, safe diagnostics and explicit pre-worker retry; owner-authorized ff-only promotion `c4924cd` to main, 76 focused tests pass on main; aggregate real-data policy conflict unresolved.
- [x] [T072](t072-remove-model-human-gates.md): Owner-requested removal of model planning gates, legacy artifact compatibility and configured verification authority; full check:task exits 0 (619 Python/86 orchestrator cases, 40 architecture tests; changed coverage100%, total92.12%, zero scanner findings).

Infrastructure verification: [final evidence](../docs/reviews/orchestrator-verification-001.md), [T067–T070 local main integration](../docs/reviews/orchestrator-integration-001.md), [T071 historical promotion evidence](t071-orchestrator-planning-contract.md), [T072 full verification and owner decision](t072-remove-model-human-gates.md). Product checkpoints unchanged; T071's prior unavailable aggregate verdict remains historical, superseded for current verification authority by T072/ADR-0007.

- [x] [T073](t073-autonomous-agent-recovery.md): Autonomous development-agent recovery; session trust, bounded safe agent retries and FAILED terminal errors. Full check:task exit0: 634 Python tests (101 orchestrator), 40 architecture tests, changed coverage94.44%, zero scanner findings.

- [x] [T074](t074-agy-worker-permissions.md): Antigravity CLI Worker, explicit GPT full access and agy process auto-approval; check:task exit0, 677 Python/144 orchestrator tests, 40 architecture tests, changed coverage100%, zero scanner findings.

- [x] [T075](t075-agy-capability-probes.md): Accept valid CLI help on stderr, check only used agy stdin flags and safely retry the known undispatched --print capability failure while preserving old evidence; check:task exit0, 704 Python/171 orchestrator tests, 40 architecture tests, changed coverage97.22%, zero scanner findings.

- [x] [T076](t076-audit-report-retry.md): Actionable audit findings, criterion evidence and bounded semantic JSON correction before terminating a run; check:task exit0, 718 Python/185 orchestrator tests, 40 architecture tests, changed coverage96.30%, zero scanner findings. Historical T059 implementation/evidence remains unchanged.

- [x] [T077](t077-optional-task-timeout.md): Opt-in development task deadlines; default null, manual positive seconds, preserved cancellation/output/fix limits and historical run evidence.

- [x] [T078](t078-task-skill-prompts.md): Task-relevant installed skill references, pinned run policy and required Worker/Fix handoff blocks; no scope/Git expansion or historical prompt rewrite.

# T037: Dashboard summary API và streak formulas

**Task ID:** `T037`  
**Title:** Dashboard summary API và streak formulas  
**Status:** `BLOCKED_IMPLEMENTATION` (11/10/2026; independent source `CODE_IMPLEMENTED_UNVERIFIED`; full summary awaits historical persistence/unavailable-streak policy; not DONE)  
**Goal:** Dashboard summary API và streak formulas. Due/streak/three learning metrics response match contract và fixtures.  
**Suggested model:** GPT-6 Astra  
**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay trong danh sách. Nếu vượt khoảng 2 giờ hoặc phạm vi này, tách task trước khi làm tiếp.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/adr/0004-v1-product-policy-and-operational-baseline.md](../docs/adr/0004-v1-product-policy-and-operational-baseline.md) dashboard
- [docs/spec.md](../docs/spec.md) FR-DASH/AC-20–22
- [docs/api-contract.md](../docs/api-contract.md) dashboard/status

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T023](t023-source-sync.md)
- [T032](t032-review-api.md)
- [T048](t048-quiz-submit-api.md)
- [T011](t011-observability-instrumentation.md)
- [T017](t017-typed-api-client.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

- `backend/app/dashboard/formulas.py`
- `backend/app/http/dashboard.py`
- `backend/tests/test_dashboard.py`
- `backend/app/main.py`

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- Chỉ learning dashboard formulas/GET bounded from/to. null no-attempt, separate MCQ/cloze/self score, invalid/missing sources excluded due, history preserved. Operational status chuyển T046; cross midnight/late review frozen T013. Đăng ký đúng route/service vào app factory; TestClient và OpenAPI export dùng app factory production, không app test riêng bỏ security guards.
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [ ] Due/streak/three learning metrics response match contract và fixtures.
- [ ] No-due/new-card/terminal-quiz/invalid-source/tz cases deterministic, no-attempt null.
- [ ] History deletion/source reset không erase past metrics; scoped bounded date queries.

## Test cases

1. AC-20/21/22; no attempts, four-week boundary, midnight.
2. Sources invalid/missing, replay submission, failed feedback không đổi score.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
python -m pytest backend/tests/test_dashboard.py -q
npm run test:contract
```

## Expected output

- Due/streak/three learning metrics response match contract và fixtures.
- Focused commands đạt kết quả/exit code ghi trong criteria; negative probe phải fail đúng reason. Documentation tasks có conformance report thay cho application-test pass.
- Evidence ghi command, exit code, môi trường và artifact. Thiếu Windows/browser/provider environment là PENDING; không hoàn tất gate thiếu evidence.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Risk

- **Level:** `High`.
- Sai contract/concurrency/persistence có thể làm mất dữ liệu, ghi sai tiến độ hoặc tạo kết luận kiểm chứng sai.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- Formula requires new policy or raw user data in telemetry → dừng.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`feat(T037): dashboard summary api và streak formulas`

## Standalone coding-only checkpoint, 11/10/2026 (Asia/Bangkok)

The owner's session instruction overrides this card's executable verification workflow: no tests, new test source, lint/type/format gates, builds, scans, audits, generated contracts or Git mutations are authorized. Acceptance checkboxes remain unchecked. This checkpoint records a required implementation stop, not coding completion or runtime evidence.

### Provenance and inspected integration

- Task: T037; requested model/configuration: GPT-6.1 Sol, HIGH, STANDALONE_CODEX_CLI, Ponytail FULL, CODE_ONLY.
- Actual branch: `feature/t037-dashboard-summary-api`.
- Supplied base and inspected HEAD: `b61e39d0e078201cf31d586ebcd8d3d1c2a42743`; initial `git status --short` was empty. No main synchronization or Git mutation occurred.
- Read-only inspection covered constraints/rules, the task/dependency plan, FR-DASH-01–05 and AC-20–22, the dashboard API example and validation rules, ADR-0004/0005, source sync/repository/journal storage, review queue/events/SRS/reset storage, durable terminal quiz results/submission, production HTTP/factory/session patterns and telemetry/privacy boundaries. Existing source-sync/review/submission tests were read as references only.
- Installed skills read: `ponytail:ponytail`, `unslop`, and `agent-skills:{incremental-implementation,api-and-interface-design,security-and-hardening,source-driven-development,code-simplification,documentation-and-adrs,git-workflow-and-versioning}`. Agent-skills files resolve under `/mnt/c/Users/khanh/.codex/plugins/cache/agent-skills/agent-skills/0.6.12/skills/`; this is the locally installed match for the stale 0.6.11 documentation-skill path in AGENT.md. No installation or upgrade occurred.
- Applied guidance: scope discipline, contract-first inspection, canonical persistence ownership, preserving history/security boundaries, read-only Git provenance and evidence-based documentation. Source-driven framework implementation and code simplification did not proceed because production implementation is blocked. `ponytail:ponytail-review`, independent reviews, audits and subagents were not invoked.

### Blocking persisted facts

ADR-0004 requires the eligible due-card denominator for each historical Bangkok study day. The retained database cannot reproduce that denominator exactly:

- `backend/app/application/sync.py` overwrites `source_files.status` for MISSING/INVALID transitions. Migration `0004_vocabulary` stores current status and latest update time, not a status timeline. Later repair/sync replaces that evidence again.
- `VocabularyRepository.unlink_source_from_form` deletes `word_form_sources` rows. Removed relationships have no retained validity interval. Current links and source status therefore cannot establish past card eligibility.
- Sync calls `reset_card_state` after meaning/example changes. `backend/app/review/models.py` resets only current box/due/revision. Review events retain the resulting schedule of each review, but neither the intervening reset time nor its previous schedule. `review_cards` also has no card-creation timestamp.
- `source_write_journal` retains application source-replacement plans, not every external watcher/startup source-status/link/reset transition. SYNC_RUN operation receipts retain aggregate counts/revision, not a per-card eligibility or schedule timeline. `0009_review_diagnostics` adds client timestamps only; those are not historical denominators or authoritative scheduling time.

Concrete case: learned cards X and Y were due on day D. X was reviewed; Y was not. If Y's only source was invalid on D, D can be complete. If Y's source was valid on D, D is incomplete. A subsequent invalidation and repair retain only current status, latest timestamps/revision and the same review history; they do not establish which denominator applied on D. A later content reset also makes the current schedule unsuitable as evidence of Y's historical due state. Counting activity days, consulting today's queue, or assigning zero to unknown history would silently change the required streak policy.

This triggers the owner's explicit stop condition: correct historical streak reconstruction is impossible from available persisted facts. Fixing future reconstruction requires a separate approved persistence task covering eligibility/link/schedule changes or durable daily completion evidence. A new ledger cannot recover already absent historical facts; handling that history also needs an explicit policy. T037 cannot modify migrations, review/sync modules or specifications, and DashboardSummary has no approved unknown-streak representation.

### Narrow contract clarifications required

1. Flashcard `averageBucket`: AGAIN/HARD/GOOD/EASY transitions are defined, but neither ordinal averaging nor bucket thresholds/tie rounding are defined. Do not reuse the writing rubric or invent a grade scale. Confirm the empty-history representation as well.
2. Objective summary: DashboardSummary exposes only `{correct,total}` for each type, while the dashboard prose requires nullable `correct/attempted` accuracy. Durable QuizResult explicitly distinguishes total questions, nonblank attempted answers and nullable accuracy. For five questions with one correct answer and four blanks, QuizResult is total 5, attempted 1, correct 1, accuracy 1. The two-field dashboard shape cannot convey both denominators and explicit nullable accuracy. Host must clarify the dashboard field semantics/shape before implementation.
3. Optional `from`/`to`: no dashboard-specific omitted-bound default, one-sided-bound behavior or endpoint inclusivity is published. ADR-0004's four-week success observation is not explicitly a dashboard result-filter default. Host must specify the historical metric window and boundaries without converting current due/streak into period totals.

Clarification requests were submitted in the session; no answer or scope extension has been received at this checkpoint.

### Source handoff

- STATUS: `BLOCKED_IMPLEMENTATION`; READY_FOR_HOST_INTEGRATION: `NO` for production T037.
- Files created: none. Files modified: this card, `tasks/todo.md`, `docs/changelogs.md`.
- Intentionally untouched: both proposed dashboard production paths, `backend/app/main.py`, all tests, migrations, review/SRS/sync/submission/feedback services, frontend/generated contracts, specifications/ADRs, dependencies/security configuration, T046/T038/T051/T090 and user Markdown/databases.
- Endpoint registered: no. Dashboard DTO/formulas: not created. No stub, fabricated streak, replacement factory or new dependency was introduced.
- Unblocked source findings for resumption: current due count can use the review queue's persisted VALID-source EXISTS predicate and `(box=0 OR due_at<=server_now)`, counting each card once. Historical FLASHCARD-only counts and terminal quiz objective/writing data survive source loss and should not join current source eligibility. Terminal `result_payload` supplies objective counts and explicit final writing self-scores, including 0; draft answers, feedback and idempotency replay do not create new results. Read-only SQL aggregation in one existing database snapshot can preserve offline operation and history, once response/range policy is resolved.
- Commands executed: read-only `pwd`, `git status --short`, `git branch --show-current`, `git rev-parse HEAD`, `rg`/`rg --files`, `cat`, `sed` and `wc`; file edits used apply_patch. No application/runtime command was executed and no runtime PASS is claimed.
- TESTS / AUDIT / COVERAGE / SECURITY_VERIFICATION: `DEFERRED_BY_OWNER`.
- GENERATED_CONTRACT: `HOST_INTEGRATION_PENDING`; generation must follow an implemented, clarified endpoint, using T017 tooling.
- Known unverified risks: no runtime verification; historical completion evidence is absent and contract details above remain unresolved. Existing production integrations and learning history were left unchanged.
- Next action: Host resolves the narrow dashboard contract details and opens/authorizes the separate historical-persistence task, including the policy for already missing history; then resume T037 within an approved scope. Do not mark DONE or use the feature commit proposal for this documentation-only checkpoint.

## Owner-approved continuation, 11/10/2026 (Asia/Bangkok)

This checkpoint supersedes the earlier pre-implementation stop for independent metrics. The owner approved the following rules in the session, subject to Host recording canonical API/ADR amendments. The production allowlist and coding-only verification restrictions remain in force.

### Approved rules implemented

- FLASHCARD events alone contribute rating count/mean: AGAIN=1, HARD=2, GOOD=3, EASY=4. Integer arithmetic rounds the ordinal mean half-up; for example HARD plus GOOD yields GOOD. No events returns count 0/bucket null. QUIZ handoffs never contribute to this metric. A production assertion checks persisted rating-aggregate bounds; no assert-based test suite was created or executed.
- Bangkok calendar dates define inclusive `from`/`to`. Neither supplied defaults to today minus 27 days through today; only `to` defaults `from` to `to` minus 27 days; only `from` defaults `to` to today. Strict ASCII YYYY-MM-DD parsing rejects malformed dates; reversed or more than 366 inclusive days returns typed `400 INVALID_QUERY`. Duplicate parameters return 400; unknown parameters return typed `422 VALIDATION_ERROR`, following the existing review boundary convention.
- Inclusive UTC bounds use the first local midnight through the last local day's final microsecond. This matches canonical microsecond review/submission storage and avoids overflowing the calendar when `to=9999-12-31`. Bounds that cannot be represented in UTC or whose default subtraction underflows return INVALID_QUERY rather than a crash. No browser timezone, silent clipping or extra query parameter was added.
- Objective MCQ/CLOZE summaries preserve `correct` and question `total`, adding `attempted` and nullable `accuracy`. Each type aggregates terminal QuizResult counts independently; accuracy divides correct by attempted, never by total. Zero attempts returns null accuracy.
- Writing metrics aggregate final terminal `writingSelfScores` only. COUNT of non-null selfScore and AVG retain explicit 0; no scores returns scored 0/average null. Drafts and AI feedback do not contribute.
- Current `dueCards` is independent of the selected historical window. The SQL matches ReviewService.queue's eligible-card predicate: NEW box 0 or learned due_at <= captured aware server time, with at least one persisted VALID source. EXISTS counts a multiply referenced card once. Historical metrics do not join live sources, so subsequent source loss/reset does not remove them.

### Completed independent source and HTTP wiring

- Created `backend/app/dashboard/formulas.py`: date/window and half-up helpers, read-only `DashboardService.project`, SQL aggregates and an internal `DashboardProjection`. Server time is captured once; all four reads share the existing explicit SQLite read transaction. Only aggregate rows enter application memory: due/rating/writing each return one row and objective scores at most two.
- Created `backend/app/http/dashboard.py`: GET `/api/v1/dashboard`, query validation, the clarified DashboardSummary DTO, typed errors, readiness checks and no-store responses. The DTO retains a required non-null streak object with integer currentDays.
- Modified `backend/app/main.py`: imports/router registration and dashboard service initialization/reset/cleanup using the existing database lifecycle. The synchronous HTTP handler follows FastAPI's existing threadpool route pattern. Production SessionGuard and telemetry middleware remain in place; T048/T049 services, watcher behavior and cleanup ordering are preserved.
- Added pure `day_is_complete` and `consecutive_completed_days` helpers. They consume explicitly supplied daily denominators/completion flags; an unknown denominator or a missing completion day yields None. The consecutive helper counts backwards from an explicit caller-supplied as_of day and never treats missing history as a failed or completed day. It does not choose the public streak's treatment of an unfinished today.
- Source guidance was checked against locked FastAPI 0.141.1, Pydantic 2.13.5 and SQLAlchemy 2.1.1 from requirements.lock. Framework references: [FastAPI response models](https://fastapi.tiangolo.com/tutorial/response-model/), [SQLAlchemy transactions](https://docs.sqlalchemy.org/en/21/core/connections.html#using-transactions), [SQLite JSON table functions](https://www.sqlite.org/json1.html#the_json_each_and_json_tree_table_valued_functions), [Python 3.12 ZoneInfo](https://docs.python.org/3.12/library/zoneinfo.html#using-zoneinfo). No dependency changes were made.

### Dependent portion still blocked

The existing schema cannot supply trustworthy historical daily denominators. `DashboardProjection.current_days` remains internally None. The HTTP handler returns the existing typed `503 CONFIGURATION_REQUIRED` rather than serialize a fabricated zero or introduce unapproved public nullability. Consequently, on the current schema a valid, ready dashboard GET computes the independent projections but cannot return HTTP 200. The independent service projections are implemented, but the API does not expose a partial success shape or a new endpoint.

Exact integration requirement: Host must implement the separately assigned historical persistence/reconstruction dependency and establish unavailable-history semantics. Wire authoritative completion facts into the projection within the same read snapshot, then use the pure helper under the approved current-streak anchor rule. If unavailable history must be exposed in a successful summary, Host must amend the public streak DTO/contract first. Do not simply replace current_days=None with 0, infer it from the mutable queue, or count activity days.

### Host-owned task scope authorized for planning only

Record a separate task, with ID/branch/allowlist/owner assigned by Host, to persist sufficient immutable facts for daily eligible due-card denominators and completion. It must cover source validity/link transitions, card creation/reset and other schedule transitions needed by reconstruction; preserve review events, quiz results, source history and current SRS schedules; use non-destructive append-only evidence wherever feasible; define Bangkok day boundaries, reconstruction and current streak anchor rules, and explicit semantics for history before coverage begins or during coverage gaps. New facts cannot recover old facts that were never stored. The owner authorized planning/scope definition only for this dependency.

This scope is recorded here without creating an unassigned task card, changing docs/task-plan.md, modifying migrations/sync/review internals, or sending messages to external systems.

Host must also record the approved rating/range/objective/field-boundary rules in canonical docs/api-contract.md and the applicable ADR, then reconcile OpenAPI/TypeScript DTO artifacts through T017's generator. Specifications and generated artifacts remain untouched in this session.

### Updated source handoff and deferred evidence

- Overall STATUS: `BLOCKED_IMPLEMENTATION`; independent source portions: `CODE_IMPLEMENTED_UNVERIFIED`; streak persistence/HTTP-200 summary: `BLOCKED_IMPLEMENTATION`. READY_FOR_HOST_INTEGRATION: `NO` for complete T037, with independent code available for Host integration.
- Actual branch/base/HEAD remain `feature/t037-dashboard-summary-api` / `b61e39d0e078201cf31d586ebcd8d3d1c2a42743`; no commits or Git mutations.
- Files created: `backend/app/dashboard/formulas.py`, `backend/app/http/dashboard.py`. Files modified: `backend/app/main.py`, this card, `tasks/todo.md`, `docs/changelogs.md`. No package initializer was needed because the existing backend uses namespace packages.
- Intentionally untouched: all test source, migrations, sync/review/SRS/scoring/submission/feedback modules, frontend/generated files, specs/ADRs, task-plan dependencies, manifests/lockfiles/security controls, T046/T038/T051/T090 and user Markdown/databases.
- Existing skills applied to coding: Ponytail FULL, incremental scope, API/interface and security boundaries, source-driven framework guidance and minimal-code conventions; documentation/unslop applied to handoff; Git skill limited to read-only provenance/diff. No review/audit agents or executable skill verification were invoked.
- Read-only source/diff/status inspection and official-documentation retrieval only. No imports, runtime probes, assertions, tests, audit, lint/type/format gates, builds, generators, coverage or security commands were executed. No runtime PASS is claimed. The later planned checks remain `python -m pytest backend/tests/test_dashboard.py -q` and `npm run test:contract`, followed by Host-owned project verification; the reserved dashboard test source was not created in this phase.
- TESTS / AUDIT / COVERAGE / SECURITY_VERIFICATION: `DEFERRED_BY_OWNER`; GENERATED_CONTRACT: `HOST_INTEGRATION_PENDING`.
- Known unverified limits: HTTP 200 remains unavailable; executable correctness and performance are unverified; existing schema has no global reviewed_at/submitted_at indexes, so range-filtered aggregation can scan stored history even though application memory stays bounded. Adding indexes is outside this allowlist. Host verification should cover empty data, half-up ties, attempted-vs-total, explicit zero writing scores, inclusive 366/max+1 dates, Bangkok midnight, source loss/reset, replay, concurrent snapshot reads and session/no-store boundaries.
- Next action: Host records the canonical amendments, assigns the historical dependency and resolves successful unavailable-streak representation/anchoring, then integrates its read projection and reconciles generated contracts. T037 remains unchecked and must not be marked DONE.

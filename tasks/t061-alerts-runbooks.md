# T061: Local symptom alerts và runbook links

**Task ID:** `T061`  
**Title:** Local symptom alerts và runbook links  
**Status:** `CODE_IMPLEMENTED_UNVERIFIED` (11/10/2026; owner-approved R1/R2 production integration; all verification deferred)  
**Goal:** Đánh giá symptom windows và hiển thị alert có hướng xử lý đã kiểm chứng.  
**Suggested model:** GPT-6 Astra  
**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay trong danh sách. Nếu vượt khoảng 2 giờ hoặc phạm vi này, tách task trước khi làm tiếp.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/observability-plan.md](../docs/observability-plan.md) §5/7
- docs/runbooks/

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T046](t046-metrics-alerts-runbooks.md)
- [T060](t060-status-ui.md)
- [T063](t063-security-scan-tooling.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

Owner authorization for RESUME_FULL_CODE_IMPLEMENTATION supersedes the original
narrow allowlist below for R1/R2. Approved production paths are alerts.py,
main.py, platform metrics.py/telemetry.py, HTTP telemetry.py/status.py, adapters
bridge.py, application sync.py, persistence database.py and frontend StatusPage.tsx.
Approved contract/docs paths additionally include docs/api-contract.md,
docs/runbooks/storage-integrity.md, generated contracts/openapi.json and
frontend/src/shared/api/generated.ts. Existing common bookkeeping and evidence
remain allowed. This coding-only session forbids test changes/execution, runtime
verification, other gates, installs and Git mutation; the test path below is
read-only. T039/T040/packaging and thresholds remain out of scope.

- `backend/app/platform/alerts.py`
- `backend/tests/test_alerts.py`
- `docs/reviews/observability-evidence-001.md`

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- Exact plan thresholds2 health probes; API5xx>1%5min; searchp95>1s5min benchmark; bridge failures>20%10min; storagebusy>1%5min; any new invalid/integrity failure. Sliding-window sample size/empty conditions documented, no divide-zero false alert. Local status sink only, not page/push services.
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [ ] Every alert controlled fixture triggers category/severity/runbook as plan, resolves after recovery.
- [ ] No-data vs no-error distinct; bounded debounce/dedup and no unbounded label history.
- [ ] Redacted events/local status, rotation failure not stop study; runbook links existing/actionable.

## Test cases

1. Synthetic timestamps threshold boundary and window expiration each alert.
2. Zero requests, mixed failures, newly invalid source/integrity failure.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
python -m pytest backend/tests/test_alerts.py -q
npm run test:e2e -- frontend/tests/e2e/status.spec.ts
```

## Expected output

- Every alert controlled fixture triggers category/severity/runbook as plan, resolves after recovery.
- Focused commands đạt kết quả/exit code ghi trong criteria; negative probe phải fail đúng reason. Documentation tasks có conformance report thay cho application-test pass.
- Evidence ghi command, exit code, môi trường và artifact. Thiếu Windows/browser/provider environment là PENDING; không hoàn tất gate thiếu evidence.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Risk

- **Level:** `High`.
- Sai contract/concurrency/persistence có thể làm mất dữ liệu, ghi sai tiến độ hoặc tạo kết luận kiểm chứng sai.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- External pager/export needed or alert threshold to change → dừng.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`test(T061): local symptom alerts và runbook links`

## Coding-only implementation handoff, 11/10/2026 (Asia/Bangkok)

Historical initial narrow-scope handoff, superseded by the R1/R2 resumption below.

- Created `backend/app/platform/alerts.py`: seven fixed category/severity/runbook
  mappings; exact bounded 300/600-second windows, strict thresholds, nearest-rank
  search p95, no-data/incomplete distinctions, duplicate/late/overflow handling,
  health streaks, committed source snapshots, explicit integrity recovery and
  bounded activation/resolution records returned locally. Optional existing
  telemetry failure latches expose bounded diagnostic degradation; no sink or
  exporter was added.
- T046 and T060 implementations are present with final verification deferred.
  T063 records historical scanner evidence; no scanner was run for this change.
  Existing dependency events lack timed windows and exact bridge classifications;
  source counts cannot detect every newly invalid source. No missing contract was
  substituted with an invented metric label or guessed healthy value.
- Overall status is BLOCKED_SCOPE. App/telemetry/HTTP/status, bridge/sync/database,
  public/generated contracts and frontend producer/consumer wiring are outside
  the explicit one-production-file allowlist. The shared storage-integrity
  runbook needs contention-specific recovery content outside this scope.
  Exact paths and reasons are in
  [observability-evidence-001.md](../docs/reviews/observability-evidence-001.md).
- Changed files: alerts.py, the evidence document, this card, tasks/todo.md and
  docs/changelogs.md. Tests, all other production source, contracts, runbooks,
  thresholds, configuration, credentials and real data were intentionally
  untouched. Initial worktree was clean; no pre-existing changes were discarded.
- Workspace: `/home/khanh/projects/vocabularies-t061-sol`, actual branch
  `feature/t061-local-alerts-runbooks`, base/HEAD
  `93a181fc0855aa988a01f9d1330c49fdd80f94dc`. No Git mutation occurred.
- No tests/test creation, builds, lint, typecheck, scans, audits, installation,
  provider calls or subagents. All acceptance checkboxes and CP18 remain pending.
  Planned test files are absent and need separate authorization for creation.
- Next task: owner scopes the exact producer/status/runbook integration and
  authorizes focused failure/privacy tests and project gates. The engine source
  alone does not complete T061 or establish release acceptance.

## R1/R2 coding-only resumption, 11/10/2026 (Asia/Bangkok)

- Preserved all five uncommitted T061 files on entry. Actual branch remains
  `feature/t061-local-alerts-runbooks`; HEAD remains
  `93a181fc0855aa988a01f9d1330c49fdd80f94dc`. No reset, replacement, stash,
  branch/worktree creation, commit, push or merge.
- One alert evaluator is attached to production telemetry at lifespan startup
  and detached after services/storage shut down. Existing HTTP completion,
  bridge, transaction and storage failure producers forward bounded observations
  once, with serialized process-local sequence allocation and nonfatal failure
  latches. Evaluation occurs on observations and Status reads, including expiry;
  no new scheduler, sink, remote service or persistence was added.
- Bridge timeout/auth/HTTP-429 quota/transport-invalid-response classifications
  reach the exact ten-minute window. Startup and post-sync committed source
  snapshots preserve invalid state until authoritative recovery. Startup integrity
  success recovers only after storage checks; observed corruption remains visible.
- Status exposes bounded typed local alert states and completeness; the existing
  UI renders headings, semantic severity/state, unknown/incomplete guidance and
  same-origin runbook links without changing polling or consent architecture.
  Seven fixed IDs serve escaped bundled docs behind the existing session/origin
  guard, including the six mapped alert runbooks and supporting staged restore
  guide. SQLITE_BUSY guidance was added without replacing integrity instructions.
- Approved benchmark fixture timings are not available at the production HTTP
  boundary. Search is deliberately NO_DATA rather than a performance PASS or an
  ordinary-traffic alert. T039 retains two-failed-probe launcher responsibility;
  backend health monitoring was not fabricated. Consumer-specific AI semantic
  validation retains T046's existing boundary outside bridge transport metrics.
- `npm run export:contract` ran with already-installed tools borrowed through
  PATH from the main checkout, npm offline/no-install settings, and Python
  bytecode writes disabled. Both generated artifacts were regenerated, not
  hand-edited. This is source generation only, not executable verification.
- Detailed producer paths, contract/status behavior, tool limitations and pending
  negative/privacy/accessibility/Windows checks are in the observability evidence.
  All acceptance checkboxes and CP18 remain pending; T061 is not DONE.

# T046: Local RED metrics và operational Status API

**Task ID:** `T046`  
**Title:** Local RED metrics và operational Status API  
**Status:** `DONE (CODING_ONLY)` — `FINAL_VERIFICATION_DEFERRED` (11/10/2026; owner-approved PR #18 merged into `main`; not runtime-verified)  
**Goal:** Local RED metrics và operational Status API. Status required fields typed/no-store include current readiness/offline/consent, no fake-ready fields.  
**Suggested model:** GPT-6 Astra  
**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay trong danh sách. Nếu vượt khoảng 2 giờ hoặc phạm vi này, tách task trước khi làm tiếp.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/observability-plan.md](../docs/observability-plan.md) §3/5/6
- [docs/api-contract.md](../docs/api-contract.md) StatusSummary

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T011](t011-observability-instrumentation.md)
- [T037](t037-dashboard-formulas.md)
- [T023](t023-source-sync.md)
- [T016](t016-dispatch-fence.md)
- [T017](t017-typed-api-client.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

### Owner-approved coding-only scope exception, 11/10/2026

The owner approved resuming the existing implementation, finalizing StatusSummary
nullable/enumerated semantics, a five-minute HTTP 5xx-only error rate, read-only
consent observation, and instrumentation at the existing dependency boundaries.
In addition to the original production paths, this session may modify:

- `docs/api-contract.md`
- `backend/app/application/consent.py`
- `backend/app/http/telemetry.py`
- `backend/app/platform/telemetry.py`
- `backend/app/adapters/bridge.py`
- `backend/app/application/sync.py`
- `backend/app/persistence/database.py`

T017's existing generator alone may regenerate `contracts/openapi.json` and
`frontend/src/shared/api/generated.ts`. This explicit exception covers the
original five-file limit. Tests and test creation, builds, lint, typecheck, scans,
audits/review workflows, installation and Git mutations remain forbidden. Do not
mark DONE or assert runtime acceptance. Configuration, migrations, user data and
T037 code remain outside scope. Preserve the previous checkpoint below as history.

- `backend/app/platform/metrics.py`
- `backend/app/http/status.py`
- `backend/tests/test_metrics.py`
- `backend/tests/test_status.py`
- `backend/app/main.py`

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- Only bounded counters/histograms/local retention and GET status aggregation; no cloud exporter. Safe app/schema/version/uptime/source/bridge/offline/consent fields; p50/p95/p99 and no request/term/path labels. Alerts move T061. Đăng ký đúng route/service vào app factory; TestClient và OpenAPI export dùng app factory production, không app test riêng bỏ security guards.
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [ ] Status required fields typed/no-store include current readiness/offline/consent, no fake-ready fields.
- [ ] RED histograms/counters bounded labels, safe local rotation/retention, diagnostic IDs not labels.
- [ ] Storage/bridge/consent failures visible independent of study outcome; no exporter/secret.

## Test cases

1. Synthetic metrics each alert once; histogram percentile fixture.
2. Dashboard no-data vs zero; collector absent stays local/no block.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
python -m pytest backend/tests/test_metrics.py -q
python -m pytest backend/tests/test_status.py -q
```

## Expected output

- Status required fields typed/no-store include current readiness/offline/consent, no fake-ready fields.
- Focused commands đạt kết quả/exit code ghi trong criteria; negative probe phải fail đúng reason. Documentation tasks có conformance report thay cho application-test pass.
- Evidence ghi command, exit code, môi trường và artifact. Thiếu Windows/browser/provider environment là PENDING; không hoàn tất gate thiếu evidence.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Risk

- **Level:** `High`.
- Sai contract/concurrency/persistence có thể làm mất dữ liệu, ghi sai tiến độ hoặc tạo kết luận kiểm chứng sai.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- Need remote pager/export or threshold relaxation → dừng.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`feat(T046): local red metrics và operational status api`

## Earlier coding-only checkpoint, 11/10/2026 (Asia/Bangkok)

The owner restricted this session to three production paths and bookkeeping. Tests,
test source, generators, builds, type/lint checks, audits, scans, installation and
Git mutation are deferred. All acceptance checkboxes remain unchecked.

### Workspace and dependency evidence

- Provided worktree: `/home/khanh/projects/vocabularies-t046-sol`; actual branch
  `feature/t046-operational-status-api`, rather than requested
  `feature/task-t046-status-api`. Base/HEAD was
  `434b1badbcdeffcc42eda10fe34b5c3141ef10a0`. Initial read-only status was clean;
  no branch, worktree, index or commit mutation occurred.
- T011 has production correlation/middleware, a local JSON sink and bounded spans,
  plus existing privacy/rotation/failure tests. Its card says coding merged with
  final acceptance PENDING. Request events contain duration and success/failure,
  not HTTP status class. Failed events include 4xx and 5xx.
- T037 has dashboard service/router and newer H1/R1 history source. Its task card
  still reports PARTIAL_UNVERIFIED/BLOCKED_DEPENDENCY; newer R1 source/changelog
  implements nullable streak behavior without executable verification. No DONE
  or usable operational-status contract is inferred from that source.
- T023 has production sync/source/watcher wiring, source status rows and durable
  SYNC_RUN receipts. Its DONE card records historical verification. T016 has the
  authoritative consent/admission fence and historical race-test evidence. T017
  has the production-factory exporter, typed client and deterministic schema
  comparison tests. None of their checks was rerun here.

### Independent source implemented

- Created `backend/app/platform/metrics.py`: finite metric/label categories,
  registered route templates only, at most 256 series and 1024 exact retained
  durations per histogram. Counters and samples reset together after a maximum
  14-day collection epoch; the epoch start and retained sample count accompany
  internal summaries. Percentiles use nearest-rank retained observations;
  no observations yield None and a measured zero remains zero. Counts describe
  the collection epoch, not an unspecified five-minute alert window.
- Added `MeteredTelemetry`, consuming T011's existing completed-request event and
  measured duration. No second middleware, diagnostic ID label, network, worker,
  exporter or metric disk format was added. Existing log rotation remains owned
  by T011. A failed measurement latches observability unavailable; reads raise a
  content-free category rather than report partial collection as healthy.
- Modified `backend/app/main.py` only to initialize per-app metrics, select the
  telemetry extension and freeze the registered server route templates. Existing
  middleware order, request correlation, security guards, routers, storage and
  learning lifecycle remain unchanged. Initialization failure uses T011's
  existing diagnostic fallback and marks any retained metrics unavailable.

### Blocked contract and scope

No `backend/app/http/status.py` or success DTO was created, and `/api/v1/status`
was not registered. The normative StatusSummary lists field names but does not
define required unknown/null values, storage/search status enums, nested
offlineCapabilities types or unavailable consent representation. No backend or
generated StatusSummary exists. In particular, NOT_GRANTED cannot stand in for
failed consent reads, and zero cannot stand in for unrecorded busy counts.

Host must clarify `docs/api-contract.md` through its contract owner before a
truthful typed status summary can be delivered. Required retained facts currently
absent include app uptime, last integrity-check time and SQLite busy count; bridge
transport is stateless with no retained reachability result. No bridge probe or
durable-state mutation was substituted for missing observations.

Additional exact out-of-scope integration paths:

- `backend/app/http/telemetry.py` and `backend/app/platform/telemetry.py`: carry
  actual status class into the completed event. Current HTTP metrics use the
  existing bounded success/failure result, without inventing 4xx/5xx labels.
- `backend/app/application/consent.py`: provide an authoritative read-only
  effective snapshot. Existing read_consent/get_snapshot invokes _policy inside
  BEGIN IMMEDIATE and may persist policy history/conflicts. Status must not reuse
  that mutating accessor or duplicate the admission rules speculatively.
- `backend/app/adapters/bridge.py`, `backend/app/application/sync.py` and
  `backend/app/persistence/database.py`: instrument the owning dependency
  boundaries and retain safe observation metadata. Generic counters/histograms
  support these categories, but no actual dependency samples are claimed.
- `contracts/openapi.json` and `frontend/src/shared/api/generated.ts`: remain
  T017 generator-owned; no generator ran and no manual DTO edits occurred.

These paths were read only. T060 UI, T061 alerts/runbooks, configuration,
migrations, tests, real data and all unrelated source remain untouched.

### Handoff and deferred evidence

Requested configuration: GPT-6.1 Sol, HIGH, Ponytail FULL. Applied installed
api-and-interface-design, observability-and-instrumentation,
incremental-implementation, security-and-hardening, source-driven-development,
context-engineering and ponytail skills. Unslop and repository-required
documentation-and-adrs also apply. Agent Skills resolve at the installed 0.6.12
path, replacing AGENT.md's stale 0.6.11 location; no installation occurred.

Source-driven references: [FastAPI route classes and router registration](https://fastapi.tiangolo.com/reference/apirouter/)
and [pinned 0.141.1 routing source](https://github.com/fastapi/fastapi/blob/0.141.1/fastapi/routing.py).
The pinned source includes nested routers, so route-label setup uses its
iter_route_contexts iterator and the original route path supplied by T011's
dispatch event. Metrics arithmetic/storage use the Python standard library.
No framework runtime probe was performed; this worktree has no inspected local
site-packages installation at the conventional .venv path.

Files created: metrics.py. Files modified: main.py, this card, tasks/todo.md and
docs/changelogs.md. All pre-existing source was retained. Read-only source/status
and diff inspection only; no execution PASS is claimed. The planned metrics and
status tests do not yet exist, so Host must separately authorize their creation
before the card's pytest commands can provide acceptance evidence. Later checks
remain the task commands, contract generation/comparison and applicable project
gates; all are DEFERRED_BY_OWNER in this session.

Overall status: BLOCKED_CONTRACT, with independent metrics
IMPLEMENTED_UNVERIFIED and dependency instrumentation BLOCKED_SCOPE. Complete
T046 is not ready for Host integration. Next action: Host clarifies the status
unknown/type contract and assigns the narrow dependency instrumentation/read-only
consent scope, then completes status/router wiring and generator-owned contracts.

## Resumed implementation handoff, 11/10/2026 (Asia/Bangkok)

Status: CODE_IMPLEMENTED_UNVERIFIED. The owner-approved exception above resolves
the previous contract/scope blockers. Branch remains
`feature/t046-operational-status-api`, base/HEAD
`434b1badbcdeffcc42eda10fe34b5c3141ef10a0`. The five pre-existing T046 paths
from the earlier session were continued, not discarded; no other changes were
present at resume. No task acceptance checkbox is checked and T046 is not DONE.

### Source and integration delivered

- `platform/metrics.py`: bounded counters/histograms and nearest-rank retained
  percentiles, 1,024 maximum series and observations per histogram. Added an exact
  sliding five-minute HTTP 5xx-only fraction. HTTP 4xx has its own status-class
  series. The response-outcome queue caps at 16,384; an incomplete window returns
  null rate and degraded diagnostics until discarded outcomes expire. Latencies
  use the latest 1,024 actual durations in the same window. No samples or a
  failed collector never imply numeric zero. Invalid/over-limit timing becomes
  unavailable; legacy bounded span timing is preserved.
- `http/telemetry.py`, `platform/telemetry.py`: carry actual HTTP status class and
  method, consume one completion event, retain existing request correlation and
  add bounded dependency observations through the existing local spans/events.
  The outer response boundary also applies status no-store on error responses.
- `adapters/bridge.py`: measure preflight/chat without changing dispatch, budgets,
  auth or outbound trace isolation. Keep only recent success/failure for status;
  no bridge probe occurs when status is read. Malformed transport responses are
  separately counted. No key and expired/no observation remain explicit.
- `application/sync.py`: observe returned/raised failures and measured duration,
  source counts through a consistent read transaction, persisted successful sync
  timestamps, and same-operation process-local timing. Failed sync keeps readiness
  degraded until a later success. Second-resolution receipt ties yield null
  duration because newest operation identity cannot be proven.
- `persistence/database.py`: count actual DBAPI commit/rollback outcomes and busy/
  integrity failures. Normal read cleanup is success; discarded/failed writes are
  failure. Retain real startup integrity time and schema evidence; query current
  revision and main-file size safely. A bounded process busy observer distinguishes
  a measured zero from missing collection. Use the same NullPool engine with a
  request-local SQLite mode=ro for observations, including missing-file failure
  instead of accidental file creation. No schema/data migration was added.
- `application/consent.py`: dedicated observe_consent shares _snapshot/_policy
  eligibility but disables durable policy-history/conflict observation. It reads
  in a normal read transaction and leaves revisions/events/choices untouched.
  Failure retains existing fail-closed behavior. Grant/revoke/admission still use
  their existing writer paths and policy observation.
- New `http/status.py`: production `GET /api/v1/status`, typed StatusSummary,
  required nullable/enumerated fields, no-store, existing session/origin/body-size
  guards, no queries/body accepted, bounded typed 500 on aggregation bugs.
  Storage, source, bridge, consent, search, diagnostics and offline capabilities
  remain independent. main.py wires the service/router once and records actual
  lifespan uptime; no worker/exporter/network capability probe was added.
- `docs/api-contract.md`: records units, exact five-minute rate denominator,
  no-data/overflow behavior, safe metadata scope and offline/unavailable semantics.
  HealthSummary and consent domain enums retain ownership and compatibility.

### Contract artifacts and exact generation outcomes

The worktree has no local venv/node_modules. Reused the existing repository venv
and pinned CLI without installing dependencies, running quality gates or starting
the app lifespan:

```text
PATH=/home/khanh/projects/vocabularies/.venv/bin:/home/khanh/projects/vocabularies/node_modules/.bin:$PATH PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 npm_config_offline=true npm_config_yes=false npm_config_cache=/tmp/t046-contract-npm python scripts/export_contract.py
```

Exit 1: T017's backend generator wrote contracts/openapi.json; npx failed with
ENOTCACHED under explicit offline mode. Then ran the same installed DTO compiler
used by T017, directly rather than resolving a new package:

```text
/home/khanh/projects/vocabularies/node_modules/.bin/openapi-typescript contracts/openapi.json -o frontend/src/shared/api/generated.ts
```

Exit 0: openapi-typescript 7.4.2 wrote generated.ts. Both artifacts now include
StatusSummary. No generated definition was edited by hand. Full-factory export
also captures pre-existing dashboard and feedback endpoints missing from the old
artifacts. Those source contracts were preserved; this artifact drift needs Host
contract comparison in the separately authorized verification phase. Generator
output is not test/build/typecheck/contract-conformance acceptance evidence.

### Dependency state, limits and next work

T011/T016/T017/T023 interfaces remain evidenced as in the earlier checkpoint.
T037's dashboard/history/R1 source exists in this baseline, but its task metadata
still reports incomplete/unverified integration. This endpoint does not aggregate
due cards, streak or historical learning scores, so no absent T037 operational
interface blocks the delivered status contract. Dashboard offline capability means
the existing local service is wired, not a claim that its historical formulas
were verified. T037 ownership and final verification remain independent.

Historical sync duration, uptime and integrity times are not persisted; audio
availability is browser-owned and null here. Search status proves version
compatibility, not freshness/performance. Bridge adapter metrics cannot claim
application-owned provider-output schema validation. Business study/consent gauges
and counters whose owner boundaries are outside this scope are not claimed as
instrumented. No T060 UI or T061 alert/runbook work was added.

Source-driven references: [SQLite connection factory](https://docs.python.org/3.12/library/sqlite3.html#sqlite3.connect),
[SQLAlchemy events](https://docs.sqlalchemy.org/en/21/core/events.html), and the
existing FastAPI references above. Applied all previously loaded implementation
skills, Ponytail FULL, documentation-and-adrs and unslop. Model requested GPT-6.1
Sol, reasoning HIGH; the exact runtime variant is not exposed.

Files created across T046: metrics.py and status.py. Modified: main.py, HTTP and
platform telemetry, bridge, sync, database, consent, docs/api-contract.md, generated
OpenAPI/DTO and the three bookkeeping files. All tests, other dependency source,
configuration, security policy, migrations, UI, credentials and vocabulary data
remain untouched. Read-only source/diff inspection and the two generation commands
above are the only execution evidence. No tests, test creation, build, typecheck,
lint, audit, security scan, benchmark, agent delegation or Git mutation occurred.

Ready for Host code integration: YES, as unverified source only. Next work requires
separate authorization for metrics/status and telemetry/database/consent failure
tests, contract comparison/determinism, and applicable project gates. Merge/release
acceptance is not established by this handoff.

## Owner-approved coding-only closure — T046 (11/10/2026)

- Final status: **`DONE (CODING_ONLY)`**; **`FINAL_VERIFICATION_DEFERRED`** by explicit repository-owner authorization. Earlier `BLOCKED_CONTRACT`, `CODE_IMPLEMENTED_UNVERIFIED` and `not DONE` checkpoints above describe historical stages and are superseded for implementation closure only.
- [PR #18](https://github.com/khanhpn308/english_web/pull/18) merged `feature/t046-operational-status-api` into `main` at merge commit `2c4b18ef9e62fcf7c46d94a1ab69b4a8a0aae177`.
- Integrated production `GET /api/v1/status`, bounded local RED metrics, HTTP status class and five-minute 5xx-only error rate, consent read-only observation, bridge/sync/SQLite dependency instrumentation, typed API contract and regenerated OpenAPI/TypeScript DTOs. The merge reconciled existing T037/T038 changes and retained Dashboard/Feedback/Status API contracts.
- **Verification status:** tests, builds, lint, typecheck, security scanning, runtime/Windows/browser checks and audit were **not executed** for this closure. Existing task acceptance checkboxes and any release/performance evidence remain deferred to the owner-approved system-wide final verification; this status is not `VERIFIED`, `PASSED` or `RELEASE_READY`.

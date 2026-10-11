# T061 local symptom alerts implementation evidence

Date: 11/10/2026, Asia/Bangkok.

## Current R1/R2 coding-only resumption

Current status: **CODE_IMPLEMENTED_UNVERIFIED**. The owner explicitly authorized
the R1/R2 integration paths in the resumption prompt, resolving the original
BLOCKED_SCOPE. All previous T061 work remains in this worktree. The historical
narrow-scope report below is preserved as history, not the current status.
Branch and HEAD remain `feature/t061-local-alerts-runbooks` and
`93a181fc0855aa988a01f9d1330c49fdd80f94dc`. The five uncommitted files present on
entry were retained; no Git mutation occurred.

### Actual producer-to-consumer source connections

- `main.py` attaches one LocalAlerts instance to application state and the
  existing Telemetry instance before storage initialization. Shutdown drains
  services/storage and then detaches both alert references. There is no timer,
  worker, retained application object in a global, or alert persistence lifecycle.
- `http/telemetry.py` remains unchanged. Its existing completion/failure EventFields
  reaches MeteredTelemetry.emit, which retains T046 metrics and invokes
  Telemetry.emit. That base boundary now forwards one HTTP observation to alerts.
  4xx only enters the denominator. The same event's measured duration is passed,
  but no ordinary request is attested as a benchmark fixture.
- `Telemetry._observe_alert` serializes a bounded process-local sequence, a
  monotonic ingestion timestamp, the observation and immediate evaluation. These
  IDs never enter labels or public records. A forwarding failure latches degraded
  diagnostics without replacing the original application result/error. Status
  evaluates again for expiry; idle windows resolve on their next observation/read.
  No background polling or duplicate aggregate-to-counter conversion was added.
- BridgeAdapter classifies typed timeout/deadline, auth, HTTP 429 quota and
  transport-invalid-response errors. Private timeout/quota exceptions preserve
  the existing public BridgeUnavailableError family. Redirect, connection and
  configuration failures are known nonqualifying outcomes; an unclassified
  exception/cancellation is incomplete. DependencyOutcome carries only a private
  boolean qualification, never exception text or provider bodies. Preflight/chat
  each remains one measured transport operation, not an observation per HTTP stage.
- MeteredTelemetry forwards classification through its existing dependency hook;
  no new metric label is needed. SQLite DBAPI commit/rollback and existing driver
  failure hooks reach timestamped transaction/BUSY windows once. Database diagnostic
  loss propagates its existing span-failure latch so missing measurements cannot
  become healthy alert calculations. No lifetime-counter ratio is used.
- Database.initialize publishes recovery only after existing integrity/FK,
  migration and write-access checks complete. Existing startup failure hooks
  activate integrity failures; authoritative driver corruption remains latched
  too. A status read never clears integrity or authorizes destructive writes.
- SyncService reads a committed, path-free source ID/status snapshot at startup
  and after every completed or raised sync attempt, including committed partial
  effects. The query holds at most 1,025 rows to expose the existing 1,024-source
  limit. Unknown/unavailable reads mark source evidence incomplete while retaining
  active state; a later complete snapshot can recover it. IDs stay engine-private.
- StatusSummary.localAlerts is required and nullable. A present LocalAlertSummary
  contains exactly seven typed items and diagnostic completeness; absence/failure
  is null. Fixed summaries, identifiers, counts and UTC timestamps exclude paths,
  content, arbitrary destinations and credential/account data. A latest ACTIVE
  episode can coexist with INCOMPLETE evidence; incomplete never resolves it.
- StatusPage validates the new bounded shape, renders accessible headings and
  textual severity/state/completeness, and links to actual same-origin runbooks.
  Its existing polling, abort/unmount/invalidation and independent consent panel
  remain intact. Alert render/evaluation failures cannot authorize AI.
- HTTP status router now serves fixed trusted runbook IDs only. It escapes all
  document text, bounds reads to 64 KiB, rejects symlink/escaped-path/hardlink files,
  and provides Status plus allowlisted local navigation. Existing SessionGuard
  enforces session/origin/security headers. Six alert runbooks cover seven
  categories; supporting first-run-and-restore is also served for staged recovery.
  No arbitrary path, user Markdown, unauthenticated mount or directory listing.
  Storage-integrity adds contention/draft/idempotency/backoff guidance while
  preserving its original integrity instructions.

### Supported and deliberately unavailable observations

API-unavailable's two-failed-probe rule belongs to T039's external/native launcher.
The backend cannot observe its own stopped process and reports NO_DATA for that
category here. Coordination of external health episodes is deferred to Windows
integration; no fake successful probe or backend monitor was added.

No approved fixture-qualified rendered-search observations exist in the existing
production HTTP/T046 measurement boundary. Production search completions are
forwarded as HTTP events but remain unqualified for search_latency, whose Status
item is NO_DATA. Its exact nearest-rank/300-second/>1-second engine contract and
actionable benchmark link remain intact. Connecting a trusted Windows benchmark
producer would require its own scope; no client flag/header can attest a fixture,
and this implementation does not establish AC-07/PERF-02 or a PASS.

Consumer-specific semantic AI response parsing remains outside T046's existing
bridge transport observation, as already documented by the Operational Status
contract. T061 classifies adapter transport/JSON/schema rejection and does not
infer consumer validation failures from arbitrary API status codes. Local study
does not depend on bridge success. Bundled docs must ship at their existing
repository-relative location; packaging relocation/Windows native integration
remains with its owner and is not runtime-verified here.

### Source generation and pending evidence

Only the approved `npm run export:contract` source generator was executed, using
installed Python and Node tooling from the main checkout through PATH. npm was
offline with install confirmation disabled; Python bytecode writes were disabled.
The command regenerated both OpenAPI and TypeScript from production schemas.
Exact source-generation command, run twice with exit code 0, including final
regeneration after correcting JSON error media types:

```text
PATH=/home/khanh/projects/vocabularies/.venv/bin:/home/khanh/projects/vocabularies/node_modules/.bin:$PATH npm_config_offline=true npm_config_yes=false PYTHONDONTWRITEBYTECODE=1 npm run export:contract
```

The generator's npx resolved the already-installed npm cache copy of
openapi-typescript 7.13.0. The main checkout's installed package and the task's
package.json both specify 7.4.2; PATH alone does not override npx package-tree
resolution. Offline/no-confirmation settings prevented a missing-package install;
no install or dependency-file change was made. Regeneration with the pinned
toolchain remains a final verification limitation. Generated diff is confined to the local
alert DTO and runbook endpoint; unrelated endpoint contracts remain unchanged.

No tests were created/modified/run. No runtime verification, benchmark, build,
lint, typecheck, audit, security/dependency scan, install, real provider request,
subagent, commit, push or merge. No PASS, DONE, security sign-off or Windows
acceptance evidence is claimed. Existing acceptance checkboxes and CP18 stay pending.
Future tests must cover real producer/consumer wiring, concurrency/dedup, strict
boundaries, overflow/no-data, missing classifications, committed source recovery,
integrity latches, telemetry loss, safe DTOs, hostile runbook IDs/files/HTML,
session/origin errors, UI accessibility and consent independence.

Framework references consulted for the new response and bounded DTO patterns:
[FastAPI response-class and OpenAPI documentation](https://fastapi.tiangolo.com/advanced/custom-response/#document-in-openapi-and-override-response)
and [Pydantic field constraints](https://docs.pydantic.dev/latest/concepts/fields/).
The code follows existing per-app telemetry and session conventions; these sources
do not supply executable integration or security evidence.

### Files and deferred ownership

Current changes: alerts.py; main.py; platform metrics.py/telemetry.py;
adapters/bridge.py; application/sync.py; persistence/database.py; http/status.py;
StatusPage.tsx; API contract; storage-integrity runbook; generated OpenAPI/TS;
this evidence, T061 card, unchecked todo and changelog. All are owner-approved.
No new file was added during resumption; alerts.py and this evidence remain the
two untracked files originally created by the initial session.

Intentionally untouched: all tests, HTTP telemetry middleware, health.py, other
frontend features, generator/package/dependency configuration, T039/T040/Windows
packaging, migrations, CONSTRAINTS thresholds, credentials and real user data.
This is ready for host **code** integration with the stated unsupported-signal
boundaries, not for verified runtime/release acceptance.

## Historical initial narrow-scope session

Task status: **BLOCKED_SCOPE** for production integration. The independent
`backend/app/platform/alerts.py` source is **IMPLEMENTED_UNVERIFIED**. This is
source inspection and coding evidence only. No alert-trigger, resolution,
privacy, security, performance or release verification has run.

## Workspace and authority

The provided worktree is `/home/khanh/projects/vocabularies-t061-sol`, branch
`feature/t061-local-alerts-runbooks`, base/HEAD
`93a181fc0855aa988a01f9d1330c49fdd80f94dc`. This differs from the requested
`feature/task-t061-local-alerts`; no branch or Git mutation occurred. Initial
read-only status was clean. Only the one production path and four authorized
documentation/bookkeeping paths were changed.

Ponytail FULL and unslop instructions were applied. The six requested Agent
Skills were found at
`/mnt/c/Users/khanh/.codex/plugins/cache/agent-skills/agent-skills/0.6.12/skills/`
and applied to the final implementation/context/documentation pass:
observability-and-instrumentation, incremental-implementation,
source-driven-development, security-and-hardening, documentation-and-adrs and
context-engineering. AGENT.md's 0.6.11 path is stale; earlier commentary reporting
these skills unavailable was corrected. No skill or dependency was installed.
Requested model is GPT-6.1 Sol with HIGH reasoning; the exact runtime model
variant is not exposed by this session.

The owner's explicit coding-only restriction takes precedence over the skills'
test/verify/commit recommendations. Arithmetic and retention are standard-library
logic; existing inspected T046/T011 types and constants supply the integration
shapes. No new framework-specific API or external documentation fetch is needed.
This reversible internal source addition creates no public API, persistence or
architecture decision requiring a new ADR. The consumer contract remains blocked.

## Dependency source inspected

- T046 contains `LocalMetrics`, `MeteredTelemetry`, closed `EventFields` and
  `DependencyOutcome`, production HTTP completion instrumentation and the typed
  `/api/v1/status` route. HTTP errors distinguish actual 5xx from 4xx and use an
  exact five-minute response window. Other counters cover a collection epoch;
  retained dependency duration samples have no event timestamps. T046 is
  DONE CODING_ONLY with final verification deferred, not verified runtime evidence.
- T060 has the actual StatusPage/AppShell route, typed fields and visible-only
  30-second polling. Its runbook references are text/code filenames rather than
  clickable links, and there is no alert DTO consumer. Its closure also defers
  final verification. No frontend change was made.
- T063's DONE card records real pinned scanner positive/negative evidence dated
  30/09/2026. This is historical evidence, not a scan of the T061 changes. The
  tooling was neither installed nor executed here.

## Engine contract and exact mappings

The returned signals answer three local operational questions: which documented
symptom is active, whether enough trustworthy evidence exists to evaluate it,
and which existing runbook addresses it. They carry no learning content.

`LocalAlerts` returns `AlertEvaluation` with seven fixed `AlertStatus` values and
at most seven transitions per evaluation. Records contain a fixed category,
severity, active/resolved state, process-relative monotonic start/update times,
bounded sample count, fixed threshold identifier and reviewed relative runbook
path. These are internal Python records, not an added public API contract.

| Category | Exact activation | Severity | Runbook |
|---|---|---|---|
| api_unavailable | Two consecutive failed health probes | page-equivalent | [api-unavailable](../runbooks/api-unavailable.md) |
| api_error_rate | HTTP 5xx / completed responses > 0.01 in 300 seconds | ticket | [api-error-rate](../runbooks/api-error-rate.md) |
| search_latency | Nearest-rank p95 of fixture-attested GET /api/v1/word-forms durations > 1 second in 300 seconds | ticket | [search-performance](../runbooks/search-performance.md) |
| bridge_failure | Timeout/auth/quota/invalid-response failures / observed bridge outcomes > 0.20 in 600 seconds | ticket | [bridge-failure](../runbooks/bridge-failure.md) |
| storage_contention | Observed busy failures / completed transactions > 0.01 in 300 seconds | ticket | [storage-integrity](../runbooks/storage-integrity.md) |
| source_parse_failure | A complete committed source snapshot includes a newly observed invalid source | ticket | [source-sync](../runbooks/source-sync.md) |
| integrity_failure | Any observed startup integrity failure | page-equivalent | [storage-integrity](../runbooks/storage-integrity.md) |

All six mapped runbook files were read and exist. They provide recovery guidance.
The shared storage-integrity runbook currently covers integrity recovery but
does not explain contention, bounded backoff or draft preservation. That required
content is outside the write allowlist and remains a runbook scope blocker.

Windows are `(now - window, now]`; observations at the lower boundary expire.
Strict greater-than comparisons leave exactly 1%, 20% and 1 second below the
activation condition. One measured denominator is sufficient, including before
a full window of uptime, following T046's HTTP contract. No minimum traffic or
additional hold period is invented. An empty denominator never divides or fires.
`measured` with zero failures differs from `no_observations` and `incomplete`.
An expired complete window resolves a previous rate/latency episode while still
reporting no observations. Missing/incomplete evidence preserves a previously
active episode rather than reporting recovery.

HTTP input consumes the existing `EventFields`. Search input is accepted only
for the exact registered search route with the caller's named-fixture attestation;
ordinary HTTP latency is excluded. This backend timing never certifies rendered
search latency, the Windows fixture, AC-07 or PERF-02.

Bridge input consumes `DependencyOutcome`. Invalid response is already classified
by T046. Generic failures require the producer's explicit boolean classification
as timeout/auth/quota/invalid response. An unclassified failure makes its window
incomplete, never an invented success or broadened failure category. No exception
message or provider body is accepted. Transaction outcomes and BUSY/startup
INTEGRITY_FAILED categories reuse the existing T046 boundary values.

Committed source snapshots accept only the actual `src_` plus 16-character opaque
ID shape and VALID/INVALID/MISSING statuses. IDs remain internal and never enter
records or labels. Initially observed invalid sources activate the category;
repeated snapshots do not repeat activation. The episode remains active while
any invalid source exists and resolves when a complete snapshot has none.
Replacement of invalid sources with equal aggregate counts cannot be inferred
from StatusSummary, so it requires the owning sync boundary's snapshot.
Integrity recovers only on explicit successful startup validation; elapsed time,
a successful status read or an absent database cannot clear the failure.

## Bounds, ordering and local failure behavior

The trust boundary is the producer input, including potentially malformed provider
classifications and source snapshots. Assets are learning data, credentials and
the study flow's original success/error behavior. Closed input categories, fixed
record fields/links, bounded capacities and content-free validation errors limit
disclosure and memory growth. The engine owns no privileged action, learning
storage, dispatch or sink, so input cannot trigger a destructive operation or an
external call. Runtime privacy/failure evidence remains unverified.

- HTTP, bridge, busy and transaction windows each hold at most T046's 16,384
  observations. Search holds at most 1,024 observations and source snapshots at
  most 1,024 sources. Overflow yields incomplete evidence until lost observations
  expire, or until a newer complete source snapshot arrives; no truncated estimate
  is reported. These are diagnostic capacity limits, not changed alert thresholds.
- IDs are process-local integers in 0..2^63-1, increasing in event-time order
  within each stream. Health IDs are consecutive. Retained duplicate IDs are
  ignored; conflicting duplicates mark the window incomplete. Expired/evicted
  sequence watermarks prevent replays from resurrecting evidence. Replays must
  keep their original timestamps. Late rate observations within the retained
  window are accepted; expired observations are discarded.
- Health/source/integrity snapshots reject older observations. A health sequence
  gap discards an uncertain streak and marks evidence incomplete until a success
  or two known consecutive failures. This avoids guessing past a missed probe.
- Evaluate after each observation or atomic batch and on expiry ticks. Transitions
  describe evaluated episodes; an unevaluated transient between input batches
  has no separately retained history. No timer or scheduler is introduced here.
- Only one latest record and current state per category are retained. Repeated
  evaluations return no duplicate transition. A new episode after resolution gets
  a new start time. There is no unbounded history or generic metric-label registry.
- An optional existing Telemetry instance supplies its sink/span failure latches;
  MeteredTelemetry's failed collector leaves timed conditions incomplete. A failed
  sink only exposes `diagnostics_degraded`; no append or rotation is attempted.
  Records are returned locally. Telemetry.emit's closed schema cannot currently
  persist an alert record. No second sink or diagnostic disk format was created.
- Invalid input raises fixed content-free ValueError categories. Future producers
  must preserve T011's diagnostic isolation so those errors cannot mask application
  failures. No learning writes, destructive recovery, dispatch, retry, bridge
  probe, remote destination, exporter or pager exists in this engine.

## Exact integration blockers and deferred work

The following paths remain untouched. Required work needs a
separate owner-approved scope/contract; the independent engine is not wired.

1. `backend/app/main.py`: instantiate per-app alert state, attach its producer
   boundary and lifecycle/expiry evaluation. T039's external launcher must own
   unavailable-process probes; a stopped backend cannot diagnose itself.
2. `backend/app/platform/metrics.py`, `backend/app/platform/telemetry.py` and
   `backend/app/http/telemetry.py`: forward each real observation with stable
   original time/sequence, including HTTP completion, transaction and busy
   outcomes, and provide an approved redacted alert-event schema if persistence
   is required. Epoch counters or successive aggregate polls cannot reconstruct
   exact dependency windows.
3. `backend/app/adapters/bridge.py`: classify qualifying failures before they are
   collapsed into generic BridgeUnavailableError/result=failure. Current telemetry
   cannot distinguish timeout/quota from redirects, connection and other failures.
4. `backend/app/application/sync.py`: supply committed bounded source snapshots
   or an owner-defined transition boundary. T046 counts and sync completion events
   do not identify each newly invalid source.
5. `backend/app/persistence/database.py`: supply explicit startup integrity
   success/failure and recovery observations. The engine does not replace the
   existing storage write-safety checks.
6. `backend/app/http/status.py`, `docs/api-contract.md`, T017-generated
   `contracts/openapi.json` and `frontend/src/shared/api/generated.ts`: define and
   expose an approved local alert summary. StatusSummary currently forbids extras
   and has no alert field. No public DTO was fabricated or edited.
7. `frontend/src/features/status/StatusPage.tsx`: consume approved alert states
   and render accessible actionable links. Serving local runbook content also
   needs an approved route/static boundary; relative repository filenames alone
   are not browser endpoints.
8. `docs/runbooks/storage-integrity.md`: add the contention-specific recovery
   procedure under separate scope. Other reviewed runbooks remain unchanged.

## Verification deferred by owner

No tests were created, modified or executed. `backend/tests/test_alerts.py`,
T046 metrics/status tests, and T060 status unit/E2E tests do not exist in this
worktree. Planned focused commands cannot currently provide their stated evidence
until test creation is separately authorized:

```text
python -m pytest backend/tests/test_alerts.py -q
npm run test:e2e -- frontend/tests/e2e/status.spec.ts
```

Later verification must cover strict threshold equality, window cutoff, no data,
zero failures, missing classifications, duplicates, late arrivals, overflow,
health sequence gaps, committed source replacement/recovery, integrity recovery,
each activation/resolution, privacy sentinels, failed local sinks and integration.
Applicable CONSTRAINTS checks and CP18 remain pending. No build, lint, typecheck,
audit, scan, benchmark, installation, provider access, Git mutation or subagent
was performed. No PASS, DONE, end-to-end readiness or release claim is made.

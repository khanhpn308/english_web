# Observability plan — Vocabulary learning app

**Status:** Planning baseline — instrumentation verification required  
**Date:** 29/09/2026 (`Asia/Bangkok`)  
**Runtime:** one local FastAPI process, React browser tab, SQLite and an external local bridge that may call cloud inference.

The app is not a 24/7 multi-user service, so the first operational surface is an in-app `/status` screen and rotating local JSON logs. Telemetry remains local-only by default; any export requires explicit user consent, an allowlisted local destination and a documented retention/ACL policy. A stopped backend is diagnosed by the Windows launcher/native fallback, not by an API route that cannot be reached.

OpenTelemetry documents logs, metrics and traces as separate signals and recommends structured logs for correlation: [signals](https://opentelemetry.io/docs/concepts/signals/), [logs](https://opentelemetry.io/docs/concepts/signals/logs/), [metrics](https://opentelemetry.io/docs/concepts/signals/metrics/).

## 1. Operational questions

Every signal below must answer one of these questions:

1. Is the local app available, and can it read/write durable study data?
2. Which user-visible flow is slow or failing: search, sync, review, quiz, bridge or audio?
3. Is a Markdown source invalid or excluded while another valid source still serves the form?
4. Did an AI/provider failure affect feedback only, or did it incorrectly affect a user's answer/score/SRS history?

## 2. Structured logs

Emit one JSON object per event, never interpolated prose. Required fields:

```json
{
  "timestamp":"2026-09-29T10:20:30.123Z",
  "level":"info",
  "event":"bridge_call_completed",
  "service":"vocab-backend",
  "version":"0.1.0",
  "requestId":"req_01J...",
  "traceId":"trace_01J...",
  "spanId":"span_01J...",
  "entryPoint":"browser",
  "route":"POST /api/v1/lookups",
  "status":"success",
  "durationMs":1840,
  "provider":"local-bridge",
  "model":"gemini-3.8-flash-high",
  "promptVersion":"lookup-v1"
}
```

Stable event names:

- `app_started`, `app_shutdown`, `bootstrap_succeeded`, `bootstrap_rejected`;
- `http_request_completed`, `http_request_failed`;
- `markdown_sync_started`, `markdown_source_invalid`, `markdown_sync_completed`;
- `lookup_started`, `lookup_completed`, `lookup_failed`;
- `bridge_call_started`, `bridge_call_completed`, `bridge_call_failed`, `bridge_response_rejected`;
- `review_recorded`, `quiz_created`, `quiz_answer_autosaved`, `quiz_submitted`;
- `feedback_requested`, `feedback_validated`, `feedback_rejected`;
- `storage_busy`, `storage_integrity_failed`, `security_boundary_rejected`.
- `ai_consent_viewed`, `ai_consent_granted`, `ai_consent_revoked`, `ai_consent_rejected`, `ai_consent_stale` (record policy version/revision/status category only; never policy text, answer, term or provider credential).

Log levels:

- `error`: failed invariant, storage integrity failure, or user-visible operation that needs intervention.
- `warn`: handled degradation such as retryable bridge timeout, invalid source, fallback or storage contention.
- `info`: lifecycle and completed business event with bounded metadata.
- `debug`: local diagnostics disabled by default in production mode.

### Correlation ID and entry point

At the HTTP boundary, accept `X-Request-ID` only if it matches a bounded safe format; otherwise generate a UUID. Echo it to the browser and attach it to every app log/span, including the local span representing an outbound call. Propagate W3C context inside the app, but suppress outbound `X-Request-ID`, `traceparent`, `tracestate` and `baggage` before app→Antigravity HTTP calls, including auto-instrumentation injection. ADR-0002 treats the proxy as a third-party boundary whose cloud forwarding the app cannot enforce. Audio is local SpeechSynthesis in v1, so it has no outbound trace. Record `entryPoint` at the origin (`browser`, `launcher`, `watcher`, `manual-sync`) rather than inferring it downstream. This privacy exception deliberately ends the distributed trace at the adapter; it does not remove local correlation.

Request IDs and trace IDs are diagnostic identifiers, not user IDs. They must never be metric labels.

### Data not logged

Never log API keys, bridge secrets, session/bootstrap tokens, cookies, authorization headers, full prompts, full LLM responses, quiz answers, writing text, raw Markdown, full vocabulary meaning/example text, PII, database paths, arbitrary URLs, stack traces in the UI, or provider request bodies. Use opaque IDs, status codes, bounded error categories and hashes only where correlation is essential. Redact exception messages before logging if they may contain an upstream body.

## 3. Metrics

Use RED metrics for every API route and external dependency: rate, errors and duration histograms. Use bounded labels only: `route_template`, `method`, `status_class`, `operation`, `dependency`, `provider`, `model_family`, `source_status`. Never label by request ID, term, answer, raw URL, path, timestamp or user content.

### Service and dependency metrics

| Metric | Type | Key labels | Signal |
|---|---|---|---|
| `http_requests_total` | counter | route, method, status class | API rate/error |
| `http_request_duration_seconds` | histogram | route, method, status class | p50/p95/p99 latency |
| `bridge_requests_total` | counter | operation, provider, result | lookup/quiz/feedback dependency errors |
| `bridge_request_duration_seconds` | histogram | operation, provider | external latency and timeout |
| `bridge_response_validation_failures_total` | counter | operation, failure class | hostile/broken model output |
| `markdown_sync_total` | counter | result, source status | parse and sync health |
| `markdown_sync_duration_seconds` | histogram | result | sync latency |
| `sqlite_transactions_total` | counter | operation, result | writes and rollbacks |
| `sqlite_busy_total` | counter | operation | writer contention |
| `sqlite_integrity_failures_total` | counter | check | corruption signal |
| `review_events_total` | counter | source, rating bucket | study activity (no card ID) |
| `quiz_attempts_total` | counter | type, result | assessment completion |
| `feedback_total` | counter | result | AI feedback success/failure separated from score |
| `local_due_cards` | gauge | none | local product view only; never exported remotely without consent |
| `ai_consent_mutations_total` | counter | action, result, policy_state | Consent operations; no user/content IDs and no policy text |
| `ai_dispatch_blocked_total` | counter | reason (`CONSENT_REQUIRED`, `POLICY_STALE`, `CONFIGURATION_REQUIRED`) | Proves fail-closed behavior without measuring content |

Latency is a histogram; dashboards show p50/p95/p99 and not only averages. The v1 local default is a current-user `%LOCALAPPDATA%/VocabularyApp/logs` directory with restrictive ACLs, five 10 MiB JSON files, and 14-day metric/log retention. These values do not license remote export. Rotation failure emits one bounded `telemetry_rotation_failed` event to stderr/status and must not block study. Do not create a remote copy of learning progress by default.

## 4. Traces

Use OpenTelemetry SDKs for the Python backend when the project adds a collector/exporter. The root span is the HTTP request. Add child spans only for meaningful boundaries:

1. request validation and route handler;
2. SQLite transaction/query group;
3. Markdown parse/atomic write;
4. bridge HTTP call and response validation;
5. quiz scoring and SRS update.

Keep outbound bridge-call spans in the local trace without injecting propagation headers into the HTTP request. Do not claim a correlated cloud trace or proxy-side redaction without separate approval/evidence. Do not attach prompts, answers, file content, keys or raw URLs as span attributes. Safe attributes include operation, model family, prompt version, source status, result class, bounded row count and duration. Sample normal local success at a low rate; retain all errors and validation failures if an exporter is enabled. With no exporter configured, spans stay local and must not block the user flow.

## 5. Alerts and runbooks

The local app presents these as status indicators and optionally writes a local alert record; it does not page a remote operator by default. Thresholds use the named ADR-0004 fixture; every alert links to a local runbook.

| Alert | Severity | Trigger | User-facing action | Runbook requirement |
|---|---|---|---|---|
| API unavailable | page-equivalent | health fails for 2 consecutive probes | launcher/status screen offers restart and preserves DB | [`api-unavailable.md`](runbooks/api-unavailable.md) |
| API error rate | ticket | `5xx > 1%` for 5 minutes | show status warning; inspect request IDs | [`api-error-rate.md`](runbooks/api-error-rate.md) |
| Search latency | ticket | p95 `GET /word-forms` > 1s for 5 minutes on benchmark fixture | suggest retry; do not claim PERF-02 pass | [`search-performance.md`](runbooks/search-performance.md) |
| Bridge failure | ticket | timeout/auth/quota/invalid response >20% for 10 minutes | disable only network-dependent action; local study remains usable | [`bridge-failure.md`](runbooks/bridge-failure.md) |
| Storage contention | ticket | `sqlite_busy_total / transactions >1%` for 5 minutes | retry with bounded backoff; preserve draft | [`storage-integrity.md`](runbooks/storage-integrity.md) |
| Source parse failures | ticket | any source newly invalid | exclude source and show file-specific remediation | [`source-sync.md`](runbooks/source-sync.md) |
| Integrity failure | page-equivalent | any startup `PRAGMA integrity_check` failure | stop destructive writes and show recovery guidance | [`storage-integrity.md`](runbooks/storage-integrity.md) |

Alerts must be symptom-based, actionable and linked to a short runbook. Do not page on CPU/memory alone for this single-user app; show those as diagnostic status only.

## 6. Dashboard signals

The `/status` screen and an optional local telemetry view show (local-only by default, polled every 30 seconds while visible):

- readiness (`NOT_READY`, `SYNCING`, `READY`, `DEGRADED`), app version, uptime, last successful health check and current request error rate;
- p50/p95/p99 API/search/bridge latency;
- bridge reachability, selected model family, last result category and last failure time (never key/quota secret);
- Markdown source count by `VALID`, `INVALID`, `MISSING`, last sync duration and last sync error category;
- SQLite file size, schema revision, last integrity check, busy/rollback count;
- offline capability matrix (local search/review/dashboard/created quiz vs. lookup/new quiz/feedback/audio);
- due-card count and study result counters only in the local product dashboard, not exported telemetry labels.
- AI sharing state (`NOT_GRANTED`, `GRANTED`, `REVOKED`, `STALE`), policy readiness/version fingerprint, last consent mutation category and blocked-dispatch count; never policy text, term, answer, key or provider account. Consent choice is local product state, not a remote telemetry permission.

The dashboard must distinguish “no data yet” from “0% accuracy” and “dependency unavailable”.

## 7. Verification plan

Before release, exercise telemetry itself:

1. Force a fake bridge timeout and locate the request by `requestId`; verify structured fields and redaction.
2. Send benchmark search traffic and confirm histogram p50/p95/p99 and bounded labels.
3. Break a Markdown fixture and confirm source error, excluded-study behavior and status signal.
4. Run concurrent writes to create `sqlite_busy`; verify retries and the contention metric.
5. If a collector/alert backend is enabled, fire each alert once with a controlled threshold and verify its runbook link.
6. Capture real browser/network logs and confirm no token, key, prompt, answer or raw vocabulary content appears.
7. `BR-AUTH-03`/`05`: force an auth-profile failure with a fake proxy and confirm a redacted failure category and local request/span correlation; inspect in-memory sentinel captures to ensure app diagnostic headers never enter the proxy. Do not save unredacted packet captures with real credentials. Proxy-generated logs are outside this app's telemetry guarantees; provider-controlled retention/region are disclosed by ADR-0004 and profile evidence remains a release gate.
8. Exercise `CONSENT-01`–`12`: verify denied/stale/incomplete-policy/route-blocked cases emit bounded reasons, grant/revoke/admission mutations correlate by request ID without content, a lost revoke response does not log success, and no consent event includes policy text, account identity, prompt, answer or credential. Ensure local-only telemetry remains local even when AI consent is granted; record only policy digest/version and redacted admission state.

No application code or telemetry exporter is added by this architecture task. Implementation must add the instrumentation with each vertical slice rather than postponing it to launch.

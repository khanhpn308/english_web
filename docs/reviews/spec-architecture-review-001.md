# Spec/architecture adversarial review 001

**Reviewer mode:** fresh-context, adversarial review  
**Date:** 29/09/2026 (`Asia/Bangkok`)  
**Scope:** `docs/spec.md`, `docs/api-contract.md`, `docs/ui-architecture.md`, `docs/security-review.md`, `docs/observability-plan.md`, `docs/adr/0001-architecture.md`; `CONSTRAINTS.md` was absent.  
**Review rule:** findings only; no design document was modified in this review.

## Verdict (historical first pass)

The design is not ready for implementation planning. Several documents turn unresolved product questions into API/UI behavior, while other contracts are incomplete or contradictory. The findings below must be resolved or explicitly accepted before changing the design status to `READY_FOR_PLANNING`.

This verdict describes the original review context. The current authoritative disposition is the ADR-0004 closure pass near the end of this file; it supersedes historical “owner gate” labels without deleting the audit trail.

Cross-model second opinion was offered in the interactive session and was not run pending owner direction; this document records the single-model adversarial review.

## Findings

### R-001 — Open questions are being frozen as implementation decisions

- **Priority:** Critical
- **Evidence:** `docs/spec.md` §14 says framework, package manager, database schema, API routes and SRS are still open; §17.1 says the spec is not sufficient to finalize API/schema/tasks; `docs/adr/0001-architecture.md` §Decision nevertheless selects React/Vite, FastAPI and SQLite; `docs/api-contract.md` and `docs/ui-architecture.md` present those choices as baselines.
- **Impact:** Implementation can hard-code rejected product or technical choices before the owner resolves `OQ-01`–`OQ-14`. A later answer can require breaking API, data migration or UI rework. Planning now would create false certainty.
- **Đề xuất xử lý:** Keep provisional alternatives visibly provisional, or close the affected OQs in `docs/spec.md` with owner approval and a superseding ADR. Do not mark the design ready until the contract and acceptance gates agree.
- **Tài liệu bị ảnh hưởng:** `docs/spec.md`, `docs/api-contract.md`, `docs/ui-architecture.md`, `docs/security-review.md`, `docs/observability-plan.md`, `docs/adr/0001-architecture.md`, future `CONSTRAINTS.md`.

### R-002 — Cloud-provider consent, cost and data policy are not an enforceable boundary

- **Priority:** Critical
- **Evidence:** `docs/spec.md` FR-CAP-02/SEC-07 and `OQ-01` leave provider, quota, billing, retention and policy open. `docs/ui-architecture.md` only says the UI shows an external-provider disclosure. `docs/security-review.md` calls the issue a release gate, but no consent state, quota cap or fail-closed rule exists in the API.
- **Impact:** A lookup/quiz/feedback request can send user content to an unapproved or billable provider without an auditable user decision. This is a privacy, cost and potentially compliance failure, not merely a configuration detail.
- **Đề xuất xử lý:** Decide provider/model allowlist, billing owner, retention/region policy, consent wording and revocation behavior. Add a persisted/visible consent gate, request limits and a fail-closed error when policy is absent. Never treat a local bridge as proof of privacy or zero cost.
- **Tài liệu bị ảnh hưởng:** `docs/spec.md` `OQ-01`/SEC-01–07, `docs/api-contract.md` auth/config/lookup sections, `docs/ui-architecture.md` API integration, `docs/security-review.md`, `docs/adr/0001-architecture.md`.

### R-003 — Markdown and SQLite have no atomic consistency model

- **Priority:** Major
- **Evidence:** The spec requires Markdown edits and external sync while keeping SRS/quiz history outside Markdown (`docs/spec.md` §8/OQ-08/OQ-13). The ADR calls Markdown the vocabulary source and SQLite the durable history/projection. The API promises atomic Markdown rename/write but no transaction or recovery protocol across file and database.
- **Impact:** A crash between file replacement and SQLite commit can make search, displayed content, cards and history disagree. There is no deterministic recovery or proof that a rebuild preserves user history.
- **Đề xuất xử lý:** Define source-of-truth per field, revision/journal ordering, crash recovery, replay and repair behavior. Add failure-injection acceptance tests for each write ordering, including partial Markdown writes and migration failure.
- **Tài liệu bị ảnh hưởng:** `docs/spec.md` DATA-05–11/OQ-08/OQ-13, `docs/api-contract.md` sync/concurrency, `docs/security-review.md` T-07/T-10, `docs/adr/0001-architecture.md` storage decision.

### R-004 — “Last save wins” contradicts ETag conflict behavior

- **Priority:** Major
- **Evidence:** `docs/spec.md` J3/FR-VOC-06/BR-13 says the last save wins. `docs/api-contract.md` concurrency says an `If-Match` mismatch returns `409 REVISION_CONFLICT` and the client must re-read; `docs/ui-architecture.md` requires a conflict dialog and forbids silently applying the last write.
- **Impact:** Two valid clients receive different product behavior depending on whether the write is through the API or an editor. Users cannot predict whether a later edit overwrites, blocks, or requires manual merge.
- **Đề xuất xử lý:** Choose one policy. For true last-write-wins, make revision ordering authoritative and document the lost-update warning. For explicit conflict resolution, amend the spec and add merge/keep-local/keep-external behavior and acceptance tests.
- **Tài liệu bị ảnh hưởng:** `docs/spec.md` J3/FR-VOC-06/BR-13/OQ-08, `docs/api-contract.md` §8, `docs/ui-architecture.md` J3, `docs/security-review.md` T-09/T-10.

### R-005 — FTS5 does not by itself satisfy Vietnamese arbitrary substring search

- **Priority:** Major
- **Evidence:** `docs/spec.md` PERF-02/AC-07 require a Vietnamese substring match within 1 second on 100,000 forms. `docs/api-contract.md` and the ADR select FTS5 but define no tokenization, accent normalization, infix/trigram strategy, index maintenance or fallback. Default full-text token matching is not equivalent to arbitrary infix substring matching.
- **Impact:** The required query can return false negatives or miss the 1-second target; the core search capability cannot be verified from the current design.
- **Đề xuất xử lý:** Specify exact semantics (accent-insensitive or not, token/substring/typo behavior), normalization, index structure and benchmark fixture. Compare FTS5 prefix/ngram, normalized side index and bounded `LIKE`; choose based on measured Windows results and add update/rebuild tests.
- **Tài liệu bị ảnh hưởng:** `docs/spec.md` FR-VOC-01/PERF-02/AC-07/OQ-11/OQ-14, `docs/api-contract.md` search/filter/sort, `docs/adr/0001-architecture.md`, `docs/security-review.md` T-06.

### R-006 — SRS, ratings and dashboard fields are public placeholders

- **Priority:** Major
- **Evidence:** `docs/spec.md` OQ-02/OQ-03/OQ-07/OQ-12 leave SRS algorithm, rating scale, quiz mapping, streak and dashboard formulas open. `docs/api-contract.md` nevertheless exposes `rating: GOOD`, `nextDueAt`, `averageBucket`, `writingSelfScore` and review queue semantics.
- **Impact:** These fields become a de facto `/v1` contract before the business rules exist. Implementers cannot calculate expected results or write stable contract tests; changing the enum/meaning later is breaking.
- **Đề xuất xử lý:** Resolve the scoring/rating/formula decisions before freezing DTOs. Until then, keep an internal prototype schema out of `/api/v1` or mark it explicitly experimental and remove normative acceptance claims.
- **Tài liệu bị ảnh hưởng:** `docs/spec.md` OQ-02/OQ-03/OQ-07/OQ-12, `docs/api-contract.md` review/dashboard schemas, `docs/ui-architecture.md` review/result screens, `docs/adr/0001-architecture.md` implementation sequence.

### R-007 — Quiz snapshot and submission lifecycle are contradictory and incomplete

- **Priority:** Major
- **Evidence:** `docs/api-contract.md` says quiz questions are snapshotted at creation, then says snapshot/source-change handling is `OQ-04`; the spec explicitly leaves that policy open. The submission endpoint accepts `{}` and has no attempt state, immutable submission revision, already-submitted error or one-time SRS handoff.
- **Impact:** Re-submit, source changes, bridge failures and app restarts can duplicate SRS updates, orphan attempts or change the meaning of a result. The UI cannot distinguish draft, submitted, failed and recoverable states.
- **Đề xuất xử lý:** Define a state machine (`IN_PROGRESS → SUBMITTED` plus explicit `FAILED`/`ABANDONED` policy), immutable snapshot rules, submission idempotency, result revision and exactly-once SRS handoff. Add crash/retry/source-change tests.
- **Tài liệu bị ảnh hưởng:** `docs/spec.md` FR-ASM-08–15/OQ-02/OQ-04/DATA-09, `docs/api-contract.md` assessment endpoints, `docs/ui-architecture.md` quiz runner/result, `docs/adr/0001-architecture.md` Slice 4.

### R-008 — Answer autosave claims idempotency without a revision in the schema

- **Priority:** Major
- **Evidence:** `docs/api-contract.md` says `PUT` answer drafts are idempotent for `(attemptId, questionId, revision)`, but `AnswerDraftRequest` contains only `answer` and `selfScore`; the endpoint has no request/response revision or `If-Match` semantics. `docs/ui-architecture.md` uses debounced autosave and AbortController.
- **Impact:** Concurrent tabs/retries cannot detect stale drafts. A late request can overwrite a newer answer, and the client cannot prove whether an aborted save committed.
- **Đề xuất xử lý:** Add server/client monotonic draft revisions, response revision, stale-write `409`, and read-after-abort reconciliation. Otherwise remove the revision claim and define last-write behavior explicitly.
- **Tài liệu bị ảnh hưởng:** `docs/api-contract.md` answer schema/concurrency, `docs/ui-architecture.md` quiz runner/fetching, `docs/spec.md` FR-ASM-09/OQ-04/OQ-09.

### R-009 — Lookup preview expiry is an unapproved data-loss policy

- **Priority:** Major
- **Evidence:** The lookup example adds a five-minute `expiresAt`, but the spec only requires inspect-then-save and never defines expiry. `POST /word-forms` can save only by the ephemeral `lookupId`; no retrieval endpoint or expired-preview UX exists.
- **Impact:** A valid, expensive lookup can become unsaveable while the user reviews it. A retry may call the provider again or produce different content, violating user intent and cost expectations.
- **Đề xuất xử lý:** Remove expiry, or approve TTL, persistence scope, expiry error, recovery/re-fetch behavior and offline handling in the spec/API/UI. Add an acceptance test for expiry and retry.
- **Tài liệu bị ảnh hưởng:** `docs/spec.md` J2/FR-CAP-06–09/OQ-01, `docs/api-contract.md` lookup/save schemas, `docs/ui-architecture.md` lookup flow/states, `docs/security-review.md` provider cost risk.

### R-010 — API contract is not schema-complete

- **Priority:** Major
- **Evidence:** Endpoint tables reference `LookupResult`, `WordFormSummary`, `ReviewCard`, `Answer`, `QuizResult` and `Feedback`, but only partial examples are provided. Required bounds, nullable fields, enum values, error variants and response headers are missing despite the claim that generated OpenAPI/DTOs are the source of truth.
- **Impact:** OpenAPI generation, frontend type generation and contract tests cannot be implemented consistently. Different agents will invent incompatible schemas.
- **Đề xuất xử lý:** Define every request/response JSON Schema, including all status states, bounds, headers (`ETag`, `Location`, retry information), pagination cursor errors and error-detail discriminated unions. Do not freeze `/v1` until schema review passes.
- **Tài liệu bị ảnh hưởng:** `docs/api-contract.md` §§3–5/10–11, `docs/ui-architecture.md` API integration/test strategy, `docs/spec.md` §17.1.

### R-011 — Audio redirect conflicts with CSP, privacy and observability

- **Priority:** Major
- **Evidence:** `docs/api-contract.md` returns `302` to a provider URL; `docs/security-review.md` only says hosts are allowlisted and the CSP example does not define `media-src`; `docs/spec.md` OQ-06 leaves provider/voice/error policy open. Browser-followed redirects cannot carry the backend trace context promised by `docs/observability-plan.md`.
- **Impact:** Audio may be blocked by the shipped CSP, leak the selected word/referrer to an unapproved provider, or fail without a typed error/content contract. The UI cannot reliably distinguish provider, network and playback errors.
- **Đề xuất xử lý:** Resolve OQ-06. Either proxy audio through the backend with strict host/size/timeouts and `media-src` policy, or explicitly allow client-side provider media and accept its privacy/trace limitations. Define range/content-type/error tests.
- **Tài liệu bị ảnh hưởng:** `docs/spec.md` FR-CAP-10/OQ-06/AC-25, `docs/api-contract.md` audio endpoint, `docs/ui-architecture.md` `AudioButton`, `docs/security-review.md` T-08, `docs/observability-plan.md` traces.

### R-012 — Startup failure recovery screen is unreachable when the API fails

- **Priority:** Major
- **Evidence:** `docs/ui-architecture.md` says the launcher redirects to `/status` on startup failure, but `/status` is a static/UI route backed by the FastAPI process and the API requires a bootstrap session. If FastAPI did not start, neither route nor health API is available.
- **Impact:** The primary recovery path fails precisely during startup/crash incidents. The user receives a blank browser error instead of restart guidance.
- **Đề xuất xử lý:** Define a launcher-native/static fallback (or a separate process/IPC status channel), process discovery/restart behavior, port collision handling and duplicate-instance policy. Add tests for process-not-started, crash and stale tab.
- **Tài liệu bị ảnh hưởng:** `docs/spec.md` FR-RUN-01/OQ-09/OQ-13, `docs/api-contract.md` bootstrap/health, `docs/ui-architecture.md` startup/status, `docs/observability-plan.md` API-unavailable alert, `docs/adr/0001-architecture.md` runtime.

### R-013 — External editor synchronization has no complete invalidation/conflict contract

- **Priority:** Major
- **Evidence:** The spec requires detection of external edits and last-save-wins, while timestamp/version/tie behavior remains OQ-08. The API exposes only `POST/GET sync-runs`; the UI cache uses stale-while-revalidate but no watcher event, source revision propagation or cache invalidation contract.
- **Impact:** Search, detail, queue and dashboard can show stale data after an editor change. Simultaneous writes, partial writes and same-timestamp changes have no deterministic user-visible state.
- **Đề xuất xử lý:** Define watcher/manual-sync lifecycle, debounce, source revision/ETag propagation, tie-break, stale-cache invalidation and sync error states. Add tests for external edit, delete, partial write and concurrent app/editor writes.
- **Tài liệu bị ảnh hưởng:** `docs/spec.md` FR-VOC-05/06/08/09/OQ-08/OQ-14, `docs/api-contract.md` sources/sync/concurrency, `docs/ui-architecture.md` data fetching/detail states, `docs/security-review.md` T-07/T-10.

### R-014 — Idempotency cannot recover from unknown outcomes and omits sync runs

- **Priority:** Major
- **Evidence:** `docs/api-contract.md` requires idempotency keys for several POSTs but omits `POST /sync-runs`; retention TTL remains open. It defines an in-flight `409` but no recovery for a process crash after an external call and before the terminal response. The UI aborts requests on unmount.
- **Impact:** A committed save/review/feedback may look failed to the client and be retried; a stuck key can block work forever; duplicate sync runs can occur. Exactly-once behavior is asserted but not implementable.
- **Đề xuất xử lý:** Define `PENDING/SUCCEEDED/FAILED/UNKNOWN`, durable operation records, reconciliation/read-status endpoint, crash recovery and TTL. Include sync-run idempotency and abort-after-commit tests.
- **Tài liệu bị ảnh hưởng:** `docs/api-contract.md` sync/idempotency/concurrency, `docs/ui-architecture.md` fetching/mutations, `docs/spec.md` FR-CAP-09/FR-ASM-09/OQ-08/OQ-09, `docs/security-review.md` T-09.

### R-015 — Bootstrap token in the URL has a leakage path

- **Priority:** Major
- **Evidence:** `docs/api-contract.md` uses `GET /bootstrap?token=<one-time>` and only says the token is omitted from logs/not returned to JavaScript. `docs/security-review.md` asks for a history/referrer test but defines no mechanism that removes the URL before browser history, screenshots, browser sync or access logs capture it.
- **Impact:** A local process or copied browser profile can replay the token during its TTL. A “one-time” token is not sufficient if the exchange is observed before use.
- **Đề xuất xử lý:** Prefer a named-pipe/launcher IPC or POST/header exchange. If a URL is unavoidable, use a fragment or immediate `replaceState`, redact access logs, set explicit TTL/replay rules and test history/referrer/process listings.
- **Tài liệu bị ảnh hưởng:** `docs/api-contract.md` bootstrap/auth, `docs/security-review.md` T-01/T-18, `docs/ui-architecture.md` J1, `docs/adr/0001-architecture.md` session boundary.

### R-016 — Configurable bridge can violate the local/provider allowlist

- **Priority:** Major
- **Evidence:** The spec calls the bridge configurable but forbids unapproved paid APIs; security T-15 requires a provider/model allowlist. The API has no configuration schema or enforcement, while examples hard-code `gemini-3.8-flash-high` even though OQ-01 leaves production model/provider open.
- **Impact:** A config typo or malicious local config can send prompts to a LAN/remote/paid endpoint, bypass consent and data-minimization assumptions. Examples may become an accidental production contract.
- **Đề xuất xử lý:** Validate configuration at startup; require loopback bridge by default, explicit provider/model allowlist, consent and cost status. Replace hard-coded production model examples with `configuredModel` until OQ-01 is closed.
- **Tài liệu bị ảnh hưởng:** `docs/spec.md` FR-CAP-02/SEC-03/SEC-07/OQ-01/OQ-13, `docs/api-contract.md` lookup/health, `docs/security-review.md` T-03/T-12/T-15, `docs/adr/0001-architecture.md` provider boundary.

### R-017 — Security limits and timeouts are promises without values

- **Priority:** Major
- **Evidence:** `docs/api-contract.md` says lookup/feedback payload caps “must be configured before implementation”; security promises file/array caps, rate limits and bridge/audio timeouts; the 120-second lookup target has no timeout budget or retry policy.
- **Impact:** DoS/quota-burn protection and hung-request behavior cannot be tested. A user can wait indefinitely or a provider call can continue after the UI abandons it.
- **Đề xuất xử lý:** Approve concrete maximum term/array/file sizes, request and bridge timeouts, cancellation, retry/backoff and per-operation rate limits. Add timeout, `413`, `429`/`503` and cancellation acceptance tests.
- **Tài liệu bị ảnh hưởng:** `docs/spec.md` PERF-01/03/OQ-11, `docs/api-contract.md` validation/errors, `docs/security-review.md` T-11, `docs/observability-plan.md` bridge alerts.

### R-018 — Feedback failure history required by the spec is absent from the API model

- **Priority:** Major
- **Evidence:** `docs/spec.md` DATA-11 and FR-ASM-15 require storing feedback status/errors while preserving the answer and user score. `docs/api-contract.md` models only `status: VALIDATED` and returns a transient `502/503` without a persisted failed-feedback record.
- **Impact:** After restart the user cannot see whether feedback was requested, failed due quota, or was never attempted. Retries can duplicate calls and observability cannot reconstruct the attempt.
- **Đề xuất xử lý:** Add `Feedback` states such as `REQUESTED`, `VALIDATED`, `FAILED`, with redacted error category, provider/model, prompt version and timestamps. Define retry/idempotency and UI states for each.
- **Tài liệu bị ảnh hưởng:** `docs/spec.md` DATA-11/FR-ASM-13–15, `docs/api-contract.md` feedback schema/errors, `docs/ui-architecture.md` result/feedback states, `docs/observability-plan.md` feedback metrics.

### R-019 — AI feedback can be requested for text different from the persisted answer

- **Priority:** Major
- **Evidence:** `POST /api/v1/quiz-questions/{questionId}/feedback` accepts a free `answer` string, while the spec requires feedback linked to the stored attempt/question/answer and autosave. No answer revision/hash is required.
- **Impact:** Feedback history can describe text the user never submitted or an older draft; sensitive text can be sent outside the intended saved state.
- **Đề xuất xử lý:** Omit answer from the request and read the canonical saved answer, or require an answer revision/hash that must match the stored draft. Reject stale/mismatched feedback and return the bound revision.
- **Tài liệu bị ảnh hưởng:** `docs/spec.md` FR-ASM-09/11–15/DATA-11, `docs/api-contract.md` feedback endpoint/schema/concurrency, `docs/ui-architecture.md` quiz result flow, `docs/security-review.md` T-04/T-12.

### R-020 — “Save all forms” conflicts with `selectedFormIds[]`

- **Priority:** Major
- **Evidence:** `docs/spec.md` J2/FR-CAP-07 says saving creates a separate card for each word form. `docs/api-contract.md` requires `selectedFormIds[]`, and the UI makes selection part of the save flow; no rule says whether omission is allowed or whether “select all” is default.
- **Impact:** A user can save a partial family contrary to the product goal, or agents can implement different defaults. Card counts and Markdown output become non-deterministic.
- **Đề xuất xử lý:** Add an explicit selection rule and AC (including zero/partial/all selection), or remove selection and always save every returned form. Align request schema, UI copy and persistence tests.
- **Tài liệu bị ảnh hưởng:** `docs/spec.md` J2/FR-CAP-03/07/08/AC-04, `docs/api-contract.md` save request/response, `docs/ui-architecture.md` lookup/save components.

### R-021 — Verification status has two incompatible levels

- **Priority:** Major
- **Evidence:** `docs/api-contract.md` says status is per field, but `WordForm` examples also show field statuses and `LookupResult` adds a top-level `verificationStatus`. `docs/spec.md` OQ-06 leaves field/form/result granularity open; UI expects field badges.
- **Impact:** A result-level `UNVERIFIED` can hide verified/missing fields, while save/reopen/filter logic has no deterministic aggregate rule. AC-33 checks only one ambiguous case.
- **Đề xuất xử lý:** Define immutable per-field provenance plus a read-only aggregate computed from fields, or choose one level. Specify transitions to `VERIFIED`, filter semantics and round-trip tests; remove misleading top-level fields if not defined.
- **Tài liệu bị ảnh hưởng:** `docs/spec.md` FR-CAP-05/OQ-06/AC-33, `docs/api-contract.md` schemas/filtering, `docs/ui-architecture.md` verification badges, `docs/security-review.md` T-05/T-15.

### R-022 — Client-supplied review timestamps can corrupt SRS and streaks

- **Priority:** Major
- **Evidence:** `ReviewRequest` accepts `reviewedAt` from the client. SRS due/streak timezone/order remains open in `docs/spec.md` OQ-02/OQ-07, and API does not define server ordering or clock tolerance.
- **Impact:** Clock skew, stale tabs or a local caller can backdate/future-date reviews, alter due queues and produce incorrect streaks. Offline replay has no event-time policy.
- **Đề xuất xử lý:** Make server receipt time authoritative, record optional bounded client event time separately, define offline replay/timezone rules and reject unreasonable timestamps. Add boundary and replay tests.
- **Tài liệu bị ảnh hưởng:** `docs/spec.md` FR-REV-06/07/OQ-02/OQ-07, `docs/api-contract.md` ReviewRequest/ReviewEvent, `docs/ui-architecture.md` review flow, `docs/observability-plan.md` review metrics.

### R-023 — UI/observability promise a status surface with no matching API contract

- **Priority:** Major
- **Evidence:** `docs/observability-plan.md` `/status` requires latency, error rate, source counts, DB size/schema/integrity/busy counts and offline matrix. `docs/ui-architecture.md` says the route polls health/sync. `docs/api-contract.md` only defines `/api/v1/health` with a small unspecified object.
- **Impact:** The status screen, privacy boundary and polling behavior cannot be implemented or contract-tested. Exposing DB paths/telemetry details also risks data leakage.
- **Đề xuất xử lý:** Add a privacy-safe, `Cache-Control: no-store` status DTO and endpoint with bounded fields, polling interval and failure states, or reduce the observability/UI promise to the existing health contract.
- **Tài liệu bị ảnh hưởng:** `docs/api-contract.md` health/status, `docs/ui-architecture.md` `/status`, `docs/observability-plan.md` dashboard/alerts, `docs/security-review.md` T-13/T-17.

### R-024 — FTS5 availability is assumed on the shipped Windows runtime

- **Priority:** Major
- **Evidence:** The ADR/API require SQLite FTS5, but `docs/project-context.md` has no runtime or bundled SQLite version. Security only says WAL “where supported”; no startup capability check, migration fallback or Windows CI verification exists.
- **Impact:** A Python/Windows SQLite build without the required extension can fail startup or silently miss the search/performance target.
- **Đề xuất xử lý:** Make FTS5 capability a startup prerequisite with a clear `/status` error, verify the exact bundled build in Windows CI, and define a tested fallback/index rebuild path or fail installation before data import.
- **Tài liệu bị ảnh hưởng:** `docs/project-context.md`, `docs/spec.md` PERF-02/OQ-11/OQ-13, `docs/api-contract.md` health/search, `docs/adr/0001-architecture.md`, `docs/security-review.md` T-10/T-11.

### R-025 — Existing Markdown compatibility is not specified enough to prevent data loss

- **Priority:** Major
- **Evidence:** The spec assumes current files remain readable (`A3`, `OQ-14`) and the repository has a Markdown contract with context fields. The API/ADR define normalized word-form fields but no parser version, unknown-field preservation, round-trip policy or migration marker.
- **Impact:** The first sync can drop context or rewrite files in a way the external editor cannot read. This violates the user-visible Markdown requirement and is hard to undo without backup.
- **Đề xuất xử lý:** Freeze a parser/serializer compatibility matrix against the existing fixture, preserve unknown/context fields or explicitly migrate them, add round-trip/diff tests and a dry-run before first write.
- **Tài liệu bị ảnh hưởng:** `docs/spec.md` DATA-02–06/A3/OQ-14, `docs/api-contract.md` sync/source schemas, `docs/security-review.md` T-07/T-10, `docs/adr/0001-architecture.md` storage.

### R-026 — Several acceptance criteria cannot produce a repeatable pass/fail result

- **Priority:** Major
- **Evidence:** `AC-02` requires “all” academic meanings without a completeness rubric; `AC-07` and `AC-27` depend on an undecided hardware/network/provider fixture; `AC-21`/`AC-22` depend on open streak rules; `AC-24` says keyboard-only with no focus-order checklist; `AC-32` covers every task without concrete fixtures.
- **Impact:** Different reviewers can reach opposite results while all claim to follow the spec. Teams may lower quality thresholds to get green tests.
- **Đề xuất xử lý:** Replace qualitative absolutes with fixtures/rubrics, pin machine/network/cache/model conditions, define keyboard and accessibility test matrices, and label exploratory/manual checks separately from automated acceptance.
- **Tài liệu bị ảnh hưởng:** `docs/spec.md` AC-02/07/21/22/24/27/32/OQ-06/OQ-10/OQ-11/OQ-12, `docs/ui-architecture.md` test strategy, `docs/api-contract.md` contract tests.

### R-027 — Required runbooks and alert delivery are missing

- **Priority:** Major
- **Evidence:** `docs/observability-plan.md` references `docs/runbooks/api-unavailable.md` and requires runbooks for all alerts, but no `docs/runbooks/` files exist. The app is local-only, has no collector/exporter by default, and thresholds are explicitly provisional.
- **Impact:** “Page-equivalent” and ticket alerts are not actionable, cannot be fired or routed, and may give false operational confidence. There is no documented recovery for corruption, bridge outage or launcher failure.
- **Đề xuất xử lý:** Choose local diagnostics only or specify a collector/delivery path. Add minimal runbooks with local commands, log locations, recovery/backup boundaries and escalation; remove alert commitments that cannot be delivered in v1.
- **Tài liệu bị ảnh hưởng:** `docs/observability-plan.md`, `docs/security-review.md` verification gate, `docs/adr/0001-architecture.md` operations, future `docs/runbooks/*`.

### R-028 — Offline behavior conflates “no internet” with “backend process unavailable”

- **Priority:** Major
- **Evidence:** The spec says search/review/dashboard/created quizzes work offline, while the UI/API assume a running FastAPI local API and map network failures to `NETWORK_REQUIRED`. There is no distinction between external network loss, bridge loss, crashed backend, locked database and browser reload after process exit.
- **Impact:** Users may see an offline banner but be unable to access local data, or the UI may incorrectly claim a cloud dependency is the cause. AC-06/AC-23 are not reproducible without a defined fault matrix.
- **Đề xuất xử lý:** Define offline modes and recovery: local API healthy + internet down, bridge down, DB locked, backend stopped, and stale tab. Specify launcher auto-restart/status fallback and test each mode.
- **Tài liệu bị ảnh hưởng:** `docs/spec.md` J6/FR-RUN-03/04/AC-06/23/OQ-09, `docs/api-contract.md` errors/health, `docs/ui-architecture.md` offline states, `docs/observability-plan.md` status.

### R-029 — First-run configuration and data-root setup are absent

- **Priority:** Major
- **Evidence:** The API requires a configured Markdown root, SQLite location, bridge base URL/key and provider/model, but there is no settings/first-run route (`docs/ui-architecture.md` explicitly omits settings) or installer contract. `docs/spec.md` leaves these in OQ-09/OQ-13.
- **Impact:** A clean Windows installation has no defined way to locate existing Markdown or configure credentials safely. Agents will invent environment variables, file paths and secret storage, risking data loss or secret exposure.
- **Đề xuất xử lý:** Define installer/launcher configuration source, first-run validation, migration from existing files, secret storage and safe reconfiguration. If configuration is intentionally external, document the exact operator procedure and error UX before planning.
- **Tài liệu bị ảnh hưởng:** `docs/spec.md` OQ-09/OQ-13/OQ-14, `docs/api-contract.md` health/bootstrap, `docs/ui-architecture.md` route map/status, `docs/security-review.md` T-03/T-07/T-16, `docs/adr/0001-architecture.md` runtime.

### R-030 — Observability can leak product progress and lacks lifecycle controls

- **Priority:** Minor
- **Evidence:** `docs/observability-plan.md` permits optional local collector/export and a `due_cards` gauge, suggests 14-day retention, and promises rotating logs without specifying directory, ACL, maximum size or rotation failure behavior. `docs/spec.md` SEC-02 keeps study progress local unless a new decision is made.
- **Impact:** Enabling diagnostics can create extra copies of personal study history; logs can fill disk or be readable by another local account. Retention/deletion cannot be verified.
- **Đề xuất xử lý:** Default-disable product-progress telemetry, require explicit local-only consent for export, define log path/ACL/size/retention/rotation and deletion behavior, and separate operational counters from learning history.
- **Tài liệu bị ảnh hưởng:** `docs/spec.md` SEC-01/02/07/OQ-13, `docs/observability-plan.md`, `docs/security-review.md` T-13/T-16, `docs/adr/0001-architecture.md` observability.

### R-031 — API examples and identifiers are internally inconsistent

- **Priority:** Minor
- **Evidence:** `docs/api-contract.md` says IDs are opaque UUIDs but examples use prefixed ULID-like values (`wf_01J...`). Error `details` is an array in the common schema but an object in the revision conflict example. `SaveResult` is described as returning canonical forms but the shown schema omits them.
- **Impact:** Generated clients and fixtures can encode incompatible types; conflict and save UI implementations will diverge before the first endpoint exists.
- **Đề xuất xử lý:** Choose UUID/ULID format, define a discriminated error-details schema and make every example conform to the normative schema. Add an OpenAPI example validation check.
- **Tài liệu bị ảnh hưởng:** `docs/api-contract.md` §§3, 5, 10–11, `docs/ui-architecture.md` API integration/test strategy.

### R-032 — UI adds unapproved scope and acceptance policy

- **Priority:** Minor
- **Evidence:** `docs/ui-architecture.md` mandates mobile-first 320/768/1024/1440 breakpoints and WCAG contrast targets, while the product targets one Windows browser and `OQ-10` leaves zoom, Sci-Link and contrast acceptance open. It also adds an operational `/status` and optional telemetry view not listed as product capabilities.
- **Impact:** Implementation work expands before the owner chooses the accessibility target; acceptance may be judged against policies the product did not approve.
- **Đề xuất xử lý:** Mark breakpoints/contrast/status/telemetry as provisional implementation guidance, or close OQ-10 and add them to scope with explicit acceptance criteria. Keep mandatory keyboard requirements distinct from optional responsive polish.
- **Tài liệu bị ảnh hưởng:** `docs/spec.md` §3/§10–12/OQ-10, `docs/ui-architecture.md` route/responsive/accessibility sections, `docs/observability-plan.md` dashboard.

### R-033 — Durable-data recovery and deletion boundaries are unresolved

- **Priority:** Major
- **Evidence:** The product excludes in-app backup, but `docs/spec.md` OQ-13 leaves storage/protection/recovery open. The ADR chooses SQLite and `docs/observability-plan.md` says integrity failure requires user-managed recovery, without a migration/backup/export compatibility contract or retention/deletion path.
- **Impact:** A corrupt database, failed migration or accidental Markdown overwrite can permanently lose SRS/quiz history. Local telemetry/feedback may persist indefinitely.
- **Đề xuất xử lý:** Define supported user-managed backup/restore/export, migration rollback/startup failure behavior, retention and deletion for feedback/logs, and integrity recovery tests. If recovery is explicitly out of scope, state the data-loss risk as an accepted decision.
- **Tài liệu bị ảnh hưởng:** `docs/spec.md` FR-RUN-05/DATA-07–11/OQ-13, `docs/adr/0001-architecture.md`, `docs/security-review.md` T-10/T-16, `docs/observability-plan.md` alerts/dashboard.

### R-034 — The local bridge is an unauthenticated key-exfiltration boundary

- **Priority:** Critical
- **Evidence:** `docs/spec.md` FR-CAP-02 sends the provider API key to a configurable `http://127.0.0.1:8045/v1` bridge. `docs/api-contract.md` says the key is backend-only but does not authenticate the bridge or prove process ownership. `docs/security-review.md` treats a compromised bridge as untrusted without a concrete channel control.
- **Impact:** Any local process that binds/proxies the bridge port, or a remotely configured URL, can steal the provider key and incur cost. “Not in the frontend/log/DB” does not make the secret safe at the next hop.
- **Đề xuất xử lý:** Use authenticated named-pipe/IPC or a mutually authenticated loopback channel with Windows ACL/process identity and a per-launch secret. Refuse non-loopback/plain HTTP unless explicitly approved. Add interception/key-exfiltration tests and rotate the previously exposed key.
- **Tài liệu bị ảnh hưởng:** `docs/spec.md` FR-CAP-02/SEC-03/OQ-01/OQ-13, `docs/api-contract.md` bridge/auth/config, `docs/security-review.md` T-03/T-15, `docs/adr/0001-architecture.md` provider boundary.

### R-035 — Quiz answer drafts cannot be restored from the response contract

- **Priority:** Major
- **Evidence:** The UI requires reload/offline resume, but `GET /api/v1/quiz-attempts/{attemptId}` returns only `savedAnswerCount` in the example. There is no answer collection endpoint and `Answer` is undefined; the `PUT` draft contract has no complete response schema.
- **Impact:** The runner cannot reconstruct answers, blank-vs-incorrect state, self-score or draft revisions after reload. The offline requirement is therefore not implementable from the API.
- **Đề xuất xử lý:** Include versioned answer drafts in `QuizAttempt` or add a paginated answers resource with answer status/revision/self-score and offline cache semantics. Add restore-after-reload/crash acceptance tests.
- **Tài liệu bị ảnh hưởng:** `docs/spec.md` FR-ASM-09/10/AC-18/23, `docs/api-contract.md` assessment schemas, `docs/ui-architecture.md` quiz runner/data fetching.

### R-036 — UI error mapping omits errors defined by the API

- **Priority:** Major
- **Evidence:** `docs/api-contract.md` defines `SESSION_INVALID`, `NOT_FOUND`, `IDEMPOTENCY_IN_FLIGHT`, `BRIDGE_INVALID_RESPONSE`, `BRIDGE_AUTH_ERROR` and `IDEMPOTENCY_KEY_REUSED`. `docs/ui-architecture.md` maps only network, validation, revision conflict, storage busy and internal errors.
- **Impact:** Expired sessions, duplicate requests, malformed bridge responses and missing resources fall into generic/unrecoverable UI states, violating the required error/retry/empty behavior.
- **Đề xuất xử lý:** Create a complete code-to-state matrix: rebootstrap for `401`, wait/replay for in-flight idempotency, field/resource handling for `404/422`, safe retry for bridge failures and expired-preview handling. Add a fixture for every API error code.
- **Tài liệu bị ảnh hưởng:** `docs/api-contract.md` errors, `docs/ui-architecture.md` API integration/loading/error states, `docs/security-review.md` T-01/T-17.

### R-037 — Launcher lacks single-instance and database ownership rules

- **Priority:** Major
- **Evidence:** `docs/spec.md` OQ-09 asks how duplicate launches/processes are handled. The ADR starts a FastAPI process and SQLite is single-writer, but no Windows mutex/port ownership, watcher ownership or duplicate-launch handoff is defined.
- **Impact:** Double-clicking can create two servers/watchers writing the same SQLite/Markdown state, duplicate sync/review events and attach the browser to the wrong process.
- **Đề xuất xử lý:** Define single-instance mutex/lock, owner token, duplicate-launch behavior (focus existing tab vs exit), port collision handling and clean shutdown. Test concurrent launcher invocations and crash recovery.
- **Tài liệu bị ảnh hưởng:** `docs/spec.md` OQ-09/OQ-13, `docs/api-contract.md` bootstrap/health, `docs/ui-architecture.md` J1/status, `docs/security-review.md` T-10/T-18, `docs/adr/0001-architecture.md` runtime.

### R-038 — Vietnamese meaning is missing from the canonical search schema

- **Priority:** Major
- **Evidence:** The spec requires search by Vietnamese meaning. `docs/api-contract.md` models `meanings` with `language: "en"` and Vietnamese text only inside `examples[].vietnamese`, while the filter list exposes `meaningVi` without defining its source projection.
- **Impact:** Agents cannot implement or benchmark the required search consistently; a query may search example translations, an absent field or a different hidden projection. AC-07 could pass on the wrong data.
- **Đề xuất xử lý:** Add an explicit Vietnamese meaning/translation resource or define a deterministic projection from Markdown/AI fields. Specify normalization, indexing and DTO/UI labels, then regenerate the 100k fixture around that field.
- **Tài liệu bị ảnh hưởng:** `docs/spec.md` FR-VOC-01/AC-07/DATA-02, `docs/api-contract.md` WordForm/search schemas, `docs/ui-architecture.md` Search, `docs/adr/0001-architecture.md` search decision.

### R-039 — AI content-quality requirements are not testable

- **Priority:** Major
- **Evidence:** `docs/spec.md` FR-CAP-03/04 requires a complete academic word family and all common academic meanings. OQ-06 asks for a completeness/correctness rubric. AC-02 only verifies rendering of a prebuilt fixture and explicitly does not evaluate real AI quality; API validation checks shape, not semantics.
- **Impact:** An implementation can pass all automated tests while omitting forms/meanings or presenting hallucinated “verified” content. The learning set can be wrong at its source.
- **Đề xuất xử lý:** Define an authoritative dictionary/rubric and sample-based semantic acceptance, immutable provenance and human verification transition, or relax the requirement to model suggestions requiring user confirmation before learning.
- **Tài liệu bị ảnh hưởng:** `docs/spec.md` FR-CAP-03–05/OQ-06/AC-02, `docs/api-contract.md` enrichment schemas, `docs/ui-architecture.md` Lookup/verification states, `docs/security-review.md` T-05/T-15.

### R-040 — PATCH behavior for invalid or deleted sources is undefined

- **Priority:** Major
- **Evidence:** `docs/spec.md` FR-VOC-08/09 excludes malformed/deleted sources from active study and says old content must not continue. `docs/api-contract.md` permits generic `PATCH /word-forms/{id}` and atomic writes without a source-status guard; the UI only says to keep a history link.
- **Impact:** Editing a form with no valid source can overwrite a malformed file, write to a missing path, or silently repair/delete data contrary to the source-state rule.
- **Đề xuất xử lý:** Make invalid/deleted source records read-only, or define an explicit repair/relink operation with source selection, confirmation and recovery semantics. Add `SOURCE_NOT_WRITABLE`/`SOURCE_MISSING` errors and tests.
- **Tài liệu bị ảnh hưởng:** `docs/spec.md` FR-VOC-08/09/OQ-04/OQ-08, `docs/api-contract.md` PATCH/sync/errors, `docs/ui-architecture.md` detail/edit states, `docs/security-review.md` T-07/T-10.

### R-041 — Startup sync/readiness ordering is unspecified

- **Priority:** Major
- **Evidence:** J1 expects the dashboard to reflect due/streak immediately; the API offers a `STARTUP` sync run but does not define whether bootstrap waits for it, serves stale data, or shows an empty state. The UI opens Dashboard directly and has no sync-readiness state.
- **Impact:** First launch or an external edit can show an empty/stale queue and incorrect streak before import completes. The same user action can produce different results depending on startup timing.
- **Đề xuất xử lý:** Define startup state machine (`NOT_READY`, `SYNCING`, `READY`, `DEGRADED`), blocking vs asynchronous bootstrap, stale-data disclosure, retry and crash behavior. Add first-launch/external-edit timing tests.
- **Tài liệu bị ảnh hưởng:** `docs/spec.md` J1/FR-VOC-05/OQ-09/OQ-14, `docs/api-contract.md` bootstrap/sync/health, `docs/ui-architecture.md` J1/status/loading states, `docs/observability-plan.md` startup signals.

### R-042 — Cross-resource ownership and provenance checks are absent

- **Priority:** Major
- **Evidence:** `SaveWordFormsRequest` accepts arbitrary `lookupId` and `selectedFormIds[]`; feedback accepts arbitrary `questionId`, `answer` and `rubricVersion`. Boundary validation only checks shape/opaque IDs, not membership in the same preview, attempt, session or revision.
- **Impact:** A malformed local caller can save forms from another lookup, bypass selection/provenance, invoke an unsupported rubric or attach feedback to a different answer. This violates authorization/data-minimization assumptions even in a single-user app.
- **Đề xuất xử lý:** Enforce server-side relationship, term, session, revision and rubric allowlist checks. Return precise `409/422` errors and add cross-ID tampering tests.
- **Tài liệu bị ảnh hưởng:** `docs/api-contract.md` save/feedback/validation/authorization, `docs/security-review.md` T-04/T-05/T-12, `docs/ui-architecture.md` API integration.

### R-043 — Trace propagation can leak metadata to the cloud provider

- **Priority:** Major
- **Evidence:** `docs/observability-plan.md` propagates W3C trace headers through outbound bridge calls. The bridge may forward them to cloud inference, while `docs/spec.md` SEC-01/02 restricts unrelated data leaving the machine and OQ-01 leaves provider policy open.
- **Impact:** Correlation IDs and trace metadata can allow a provider to correlate study activity, even when prompts are minimized. The UI disclosure does not mention telemetry headers.
- **Đề xuất xử lý:** Strip trace context at the bridge-to-cloud boundary unless provider policy and explicit consent allow it; use a local-only correlation ID for bridge logs. Add an outbound-header assertion test.
- **Tài liệu bị ảnh hưởng:** `docs/spec.md` SEC-01/02/07/OQ-01, `docs/observability-plan.md` correlation/traces, `docs/security-review.md` T-12/T-13, `docs/adr/0001-architecture.md` observability.

### R-044 — The 100,000-form benchmark fixture is absent

- **Priority:** Major
- **Evidence:** `docs/spec.md` AC-07/PERF-02 requires a reproducible 100,000-form fixture, query and Windows configuration. `docs/ui-architecture.md` mentions browser journeys but no fixture generator/artifact; the repository currently contains only a small vocabulary sample.
- **Impact:** Performance acceptance cannot be reproduced or audited, and Unicode/content distribution can change the result. The stated 1-second target is an aspiration rather than a test.
- **Đề xuất xử lý:** Version a deterministic fixture generator/artifact, exact query set, normalized data distribution, cold/warm cache policy, SQLite build and browser/machine profile. Link it to AC-07 and OQ-11 before planning performance tasks.
- **Tài liệu bị ảnh hưởng:** `docs/spec.md` PERF-02/03/OQ-11/AC-07, `docs/api-contract.md` search contract tests, `docs/ui-architecture.md` Playwright/performance strategy, `docs/adr/0001-architecture.md` FTS5 decision.

### R-045 — Quiz-to-SRS handoff has no auditable public/data contract

- **Priority:** Major
- **Evidence:** `docs/spec.md` FR-ASM-08 requires quiz results to update SRS and keep history. The review endpoint in `docs/api-contract.md` hard-codes `source: "FLASHCARD"`; no quiz source, attempt/question reference, handoff status or idempotent link exists.
- **Impact:** Quiz-induced schedule changes cannot be distinguished from flashcard self-ratings or safely retried. Repeated submission can double-update the same card while the dashboard loses provenance.
- **Đề xuất xử lý:** Define `ReviewEvent.source=QUIZ`, attempt/question/result references, weakest-result mapping and an atomic/idempotent submission-to-SRS handoff. Expose audit fields and test repeated submission/failure recovery.
- **Tài liệu bị ảnh hưởng:** `docs/spec.md` FR-ASM-08/DATA-07/08/OQ-02, `docs/api-contract.md` review/assessment resources, `docs/ui-architecture.md` quiz result, `docs/observability-plan.md` review metrics.

### R-046 — Quiz question DTO cannot render or score the required question types

- **Priority:** Major
- **Evidence:** The `QuizAttempt` example contains only `id`, `type`, `promptEn` and `explanationVi`. It has no MCQ options/correct-answer metadata, cloze target/accepted answers, writing rubric/target word, source form ID or answer state, while the spec/UI require type-specific rendering, deterministic scoring, self-score and offline results.
- **Impact:** Frontend and backend agents must invent incompatible question/answer schemas; AC-14–19/30 cannot be contract-tested or implemented offline.
- **Đề xuất xử lý:** Define discriminated question DTOs and answer/result DTOs per type, with safe pre-submit fields, source-form linkage, rubric/version, accepted-answer policy and post-submit scoring fields. Keep answer keys out of pre-submit responses where applicable.
- **Tài liệu bị ảnh hưởng:** `docs/spec.md` FR-ASM-01–08/AC-14–19/30, `docs/api-contract.md` assessment schemas, `docs/ui-architecture.md` question renderer/result/test strategy.

### R-047 — Date and filename formats conflict with the existing Markdown fixture

- **Priority:** Major
- **Evidence:** `docs/api-contract.md` uses strict note dates `YYYY-MM-DD` and `SourceFile.relativePath: 2026-09-29.md`, while the repository contract and existing file use `DD-MM-YYYY` (`docs/vocabularies/28-09-2026.md`). `docs/spec.md` OQ-14 leaves legacy format compatibility open.
- **Impact:** Startup sync can miss the existing file or rename/rewrite it, breaking note links and user expectations before any learning data is imported.
- **Đề xuất xử lý:** Define canonical date semantics separately from legacy filename parsing, preserve existing paths on write or perform an explicit migration, and add fixtures for both formats before API freeze.
- **Tài liệu bị ảnh hưởng:** `docs/spec.md` A1/A3/OQ-14/DATA-05, `docs/api-contract.md` date/source schemas, `docs/adr/0001-architecture.md` Markdown storage, repository Markdown README/fixture.

### R-048 — Safe-path write design leaves a Windows TOCTOU/reparse-point gap

- **Priority:** Major
- **Evidence:** The API/security design only says to resolve paths, reject symlink escapes and atomically rename a temp file. It does not define handle-based validation, Windows junction/reparse-point or hardlink behavior; the security review explicitly treats a local malicious process as a residual risk.
- **Impact:** A local process can swap the checked root/target between validation and rename and cause an overwrite outside the allowlisted root, undermining the strongest destructive-file control.
- **Đề xuất xử lý:** Define Windows handle/reparse-point/ACL checks, create temp files only in a validated directory, use an atomic replace tied to validated handles where possible, or explicitly accept the residual race. Add race/hardlink/junction tests.
- **Tài liệu bị ảnh hưởng:** `docs/api-contract.md` sync/path safety, `docs/security-review.md` T-07/T-10/T-16, `docs/spec.md` AUTH-04/OQ-13/OQ-14, `docs/adr/0001-architecture.md` runtime/storage.

### R-049 — Module boundary table contains a cycle and unclear write ownership

- **Priority:** Major
- **Evidence:** `docs/api-contract.md` says `markdown-sync` may call `vocabulary`, while `vocabulary` may call `markdown-sync`; the same document assigns Markdown source ownership and SQLite projection/history ownership without defining an application orchestrator or transaction boundary.
- **Impact:** Direct circular dependencies can become circular imports/transactions. Sync and edit logic may both decide card resets, revisions and source writes, producing deadlocks or divergent behavior.
- **Đề xuất xử lý:** Make module dependencies one-way through ports: parser/sync emits source snapshots, an application service applies canonical changes and calls a serializer port. Assign conflict/reset ownership and transaction boundaries explicitly, then update the module graph and contract tests.
- **Tài liệu bị ảnh hưởng:** `docs/api-contract.md` module boundaries/sync, `docs/adr/0001-architecture.md` module decision/storage, `docs/spec.md` capability dependencies/OQ-08/OQ-13.

### R-050 — `platform` is an orchestration/god module in the boundary table

- **Priority:** Major
- **Evidence:** `docs/api-contract.md` lets `platform` call all modules while most business modules may call `platform`; no dependency-injection or port rule separates configuration, clock, IDs, telemetry and health aggregation from business behavior.
- **Impact:** Domain modules can depend on orchestration and health, creating import cycles, test coupling and hidden side effects. A health check could accidentally execute business code or database writes.
- **Đề xuất xử lý:** Make config/clock/ID/telemetry interfaces leaf dependencies; put health aggregation in an application/HTTP adapter that queries modules. Forbid domain-to-platform business calls and encode the layering rule in architecture tests.
- **Tài liệu bị ảnh hưởng:** `docs/api-contract.md` module boundaries, `docs/adr/0001-architecture.md` module decision, `docs/observability-plan.md` health/status design.

## Cross-cutting implementation blockers

The following task areas cannot be estimated safely until the corresponding findings are resolved:

- launcher/bootstrap/offline runtime: R-012, R-015, R-028, R-029, R-037, R-041;
- Markdown parser/sync and persistence: R-003, R-004, R-013, R-025, R-033, R-040, R-047, R-048;
- search/indexing/performance: R-005, R-024, R-026, R-038, R-044;
- API DTO/OpenAPI and client generation: R-006, R-008, R-010, R-014, R-021, R-022, R-023, R-031, R-036, R-042;
- quiz/SRS/feedback: R-006, R-007, R-008, R-018, R-019, R-035, R-045, R-046;
- provider/AI/security: R-002, R-011, R-016, R-017, R-021, R-034, R-039, R-042, R-043;
- operations/CI/telemetry: R-017, R-023, R-027, R-030, R-033, R-043.

## Post-apply reconciliation

`APPLY FINDINGS` was received. The following classes were applied to the affected design documents:

- API/schema: complete resource DTO placeholders, discriminated error details, Vietnamese meaning projection, cursor expiry, operation status, draft revisions, quiz state/recovery, quiz-to-SRS provenance, cross-resource checks, server review timestamps and status/capabilities endpoints.
- Security/runtime: authenticated loopback bridge, fragment bootstrap exchange, native startup fallback, single-instance/recovery gates, source write/reparse-point controls, local-only trace propagation by default and explicit configuration/consent gates.
- UI: startup readiness states, non-selective save semantics, answer restoration, abort-after-commit reconciliation, complete error mapping, source-invalid read-only behavior and a local-API-versus-external-network fault matrix.
- Storage/search/operations: explicit Vietnamese meaning field, normalized exact/folded/n-gram search proposal, legacy Markdown round-trip requirement, source revision invalidation, local telemetry lifecycle and runbooks.

The following findings were clarified rather than silently “closed”: technical stack remains a proposed baseline pending `OQ-13`; SRS/rating/rubric/quiz snapshot/audio/provider/backup/conflict/accessibility/performance formulas remain owner decisions; “offline” means external network unavailable while the local API is running, not a stopped backend; the API-key exposure finding applies to an unauthenticated or remote bridge hop, not automatically to the provider's own credential.

Full recheck result: the affected documents now cross-reference the same provisional boundaries, but they still cannot be promoted to implementation-ready because the unresolved OQs remain normative release gates and the repository still has no runtime manifests, lockfiles or implementation tests.

### Finding resolution ledger

| Finding | Handling | State |
|---|---|---|
| R-001 | Marked all stack choices as proposed baselines; retained `OQ-13` gate. | Owner gate |
| R-002 | Added provider/consent/configuration boundary and fail-closed behavior. | Owner gate: `OQ-01` |
| R-003 | Added application-owned source/projection journal and startup reconciliation protocol. | Provisional; `OQ-08`/`OQ-13` gate |
| R-004 | Made ETag conflict behavior explicitly provisional and tied it to the last-write policy. | Owner gate: `OQ-08` |
| R-005 | Added explicit Vietnamese field, exact/folded normalization and n-gram projection; FTS5 no longer claims correctness. | Benchmark gate: `OQ-11`/`OQ-14` |
| R-006 | Kept SRS/rating/dashboard DTOs configured placeholders and blocked final freeze. | Owner gate: `OQ-02`/`OQ-07`/`OQ-12` |
| R-007 | Added quiz state, operation recovery and idempotent SRS handoff; snapshot choice remains explicit. | Owner gate: `OQ-04` |
| R-008 | Added draft revision, `If-Match`, answer response revision and operation reconciliation. | Resolved in contract |
| R-009 | Removed unapproved lookup expiry from the contract. | Resolved in contract |
| R-010 | Added normative resource, question, answer, feedback, status and discriminated-error schemas. | Resolved in contract |
| R-011 | Removed arbitrary audio redirect; provider/CSP/voice remain an explicit audio gate. | Owner gate: `OQ-06` |
| R-012 | Added native launcher fallback and in-app readiness/status distinction. | Provisional; `OQ-09` gate |
| R-013 | Added source revisions, sync invalidation and invalid-source behavior. | Provisional; `OQ-08`/`OQ-14` gate |
| R-014 | Added sync idempotency, durable unknown operations and status reconciliation. | Resolved in contract |
| R-015 | Replaced query token with fragment + POST + URL replacement; TTL/restart policy remains. | Owner gate: `OQ-09` |
| R-016 | ADR-0002 resolves bridge auth/trust; exact origin/profile and BR-AUTH cases added. Model/provider policy remains separate. | Auth addressed in design; `OQ-01` model/policy gate remains |
| R-017 | Added capabilities/configuration boundary; numeric limits and timeout budget still need approval. | Owner gate: `OQ-11`/`OQ-13` |
| R-018 | Added persisted `REQUESTED/VALIDATED/FAILED` feedback states and error category. | Resolved in contract |
| R-019 | Feedback now binds to canonical saved answer revision. | Resolved in contract |
| R-020 | Save contract saves all returned forms; removed partial-family selection ambiguity. | Resolved in contract/spec alignment |
| R-021 | Added field provenance plus computed verification summary. | Resolved in contract |
| R-022 | Server now assigns review time; client time is bounded diagnostic metadata. | Resolved in contract |
| R-023 | Added privacy-safe `/status` DTO and no-store semantics. | Provisional; runtime gate |
| R-024 | Added FTS/index startup status and exact-build verification requirement. | Benchmark/runtime gate |
| R-025 | Added lossless legacy round-trip and unknown-field preservation requirement. | Owner gate: `OQ-14` |
| R-026 | Kept qualitative AI/accessibility/performance criteria explicitly gated instead of lowering them. | Owner gate: `OQ-06`/`OQ-10`/`OQ-11`/`OQ-12` |
| R-027 | Added concrete local runbooks and alert links. | Resolved in observability docs |
| R-028 | Distinguished external-network loss, bridge loss, stopped API, storage busy and session expiry. | Resolved in UI contract |
| R-029 | Documented first-run configuration as launcher/operator flow pending storage/runtime policy. | Owner gate: `OQ-09`/`OQ-13`/`OQ-14` |
| R-030 | Made telemetry local-only by default and specified log lifecycle/ACL requirements. | Provisional; privacy gate |
| R-031 | Standardized prefixed opaque IDs and error-detail union; completed SaveResult. | Resolved in contract |
| R-032 | Marked responsive/contrast guidance provisional and preserved the product scope. | Resolved as scope clarification |
| R-033 | Added integrity stop/recovery runbook and preserved no-auto-delete rule. | Owner gate: `OQ-13` |
| R-034 | ADR-0002 records explicit owner acceptance of HTTP loopback/client key and local-impersonation residual; no unsupported server-authentication claim. | Addressed in design; implementation verification pending |
| R-035 | Added answer arrays/revisions to quiz restore contract. | Resolved in contract |
| R-036 | Added complete API-code-to-UI-state mapping. | Resolved in UI contract |
| R-037 | Added single-instance as a required launcher decision/test. | Owner gate: `OQ-09` |
| R-038 | Added canonical `meaningsVi` and indexed `meaningVi` projection. | Resolved in contract/spec |
| R-039 | Preserved semantic-quality requirement and added explicit rubric/provenance gate. | Owner gate: `OQ-06` |
| R-040 | Made invalid/missing sources read-only and repair/relink explicit. | Resolved in contract/UI |
| R-041 | Added startup readiness state machine and stale-data disclosure. | Resolved provisionally; launcher gate |
| R-042 | Added cross-resource membership/revision/rubric checks. | Resolved in contract |
| R-043 | Strip app correlation/trace headers at app→third-party proxy, retain local span IDs; do not promise control of proxy/cloud forwarding. | Addressed in design; BR-AUTH-05 verification pending |
| R-044 | Added benchmark fixture requirements and search-performance runbook. | Owner gate: `OQ-11` |
| R-045 | Added `ReviewEvent.source=QUIZ`, references and idempotent handoff. | Resolved in contract |
| R-046 | Added discriminated MCQ/cloze/writing question DTOs and server-only keys. | Resolved in contract |
| R-047 | Added legacy `DD-MM-YYYY` path preservation/migration gate. | Owner gate: `OQ-14` |
| R-048 | Added Windows reparse/hardlink checks and documented race residual. | Security implementation gate |
| R-049 | Replaced module cycle with one-way ports/application orchestration. | Resolved in architecture |
| R-050 | Split platform ports from application health/orchestration. | Resolved in architecture |

## Second doubt-driven review — residual blockers

The post-apply fresh-context review found these remaining blockers:

### R2-001 — Bridge authentication/ownership is not executable

- **Current disposition:** Addressed in design by the owner's explicit acceptance and ADR-0002; local impersonation remains an accepted residual risk. Implementation/profile tests are pending, not claimed passed. Evidence below retains the pre-approval history; the resolution subsection is current.
- **Priority:** Critical
- **Nguyên nhân/evidence:** `FR-CAP-02`, API §6 and security T-03/T-19 allow “per-launch secret or IPC” but do not select a mechanism, define process identity/ACL/handshake or prove compatibility with the existing `:8045` service.
- **Impact:** A fake listener can steal the bridge credential, or the app can fail closed against the real bridge; provider cost/privacy boundary is not enforceable.
- **Đề xuất xử lý:** Owner must choose named pipe, mTLS, per-launch secret+ACL, or an approved trusted sidecar; document issuance/rotation and negative interception tests.
- **Tài liệu ảnh hưởng:** `docs/spec.md`, `docs/api-contract.md`, `docs/security-review.md`, `docs/adr/0001-architecture.md`.

#### Evidence update — 29/09/2026, trước khi owner xác nhận phiên bản

- **Owner xác nhận:** service là Antigravity Tools / Antigravity-Manager, proxy nội bộ sử dụng token/session tài khoản Google để cấp truy cập model. Chưa cung cấp phiên bản cài đặt; đây không phải chấp thuận thay đổi auth, model allowlist hay billing.
- **Nguồn upstream được kiểm tra:** commit `0269f045f4e35f34b9ee3b3bcd6c0ff1e741378f`, không đại diện cho bản đang chạy trên máy. [README](https://github.com/lbjlaq/Antigravity-Manager/blob/0269f045f4e35f34b9ee3b3bcd6c0ff1e741378f/README_EN.md) mô tả proxy OpenAI-compatible và phân biệt API key với mật khẩu quản trị. [Proxy config](https://github.com/lbjlaq/Antigravity-Manager/blob/0269f045f4e35f34b9ee3b3bcd6c0ff1e741378f/src-tauri/src/proxy/config.rs) cho phép bind loopback qua `allow_lan_access=false` và chọn auth mode; không được suy ra cấu hình thực tế từ default.
- **Bằng chứng xác thực:** [`effective_auth_mode`](https://github.com/lbjlaq/Antigravity-Manager/blob/0269f045f4e35f34b9ee3b3bcd6c0ff1e741378f/src-tauri/src/proxy/security.rs) ánh xạ `auto` + không cho LAN thành `off`. [HTTP auth middleware](https://github.com/lbjlaq/Antigravity-Manager/blob/0269f045f4e35f34b9ee3b3bcd6c0ff1e741378f/src-tauri/src/proxy/middleware/auth.rs) nhận bearer/API key và bỏ kiểm tra bắt buộc ở mode `off`; có ngoại lệ như `OPTIONS` và `/internal/*`. Vì vậy không tuyên bố `strict` bảo vệ mọi route chỉ từ tên mode. API key của proxy không phải token/session Google và không chứng minh danh tính server/process nhận nó.
- **Nguyên nhân được thu hẹp:** tài liệu đã yêu cầu per-launch secret/IPC/process authentication mà chưa xác minh proxy hỗ trợ; đồng thời dùng HTTP loopback nhưng có câu từ chối plain HTTP. Chưa có bằng chứng trong các nguồn đã đọc về cơ chế đáp ứng yêu cầu đó. Không được giải quyết mâu thuẫn bằng cách coi HTTP + bearer key là xác thực hai chiều.
- **Đề xuất tiếp theo:** xác định phiên bản cài đặt trước. Với phiên bản tương ứng, đánh giá cấu hình tắt LAN + bật auth rõ ràng cho inference, quản lý/rotate proxy client key, tách mật khẩu quản trị; sau đó trình owner quyết định ranh giới tin cậy Windows so với yêu cầu xác thực process hiện tại. Đây là đề xuất, chưa thay thế yêu cầu bảo mật. Quyết định thay đổi kiến trúc cần ADR kế tiếp, không viết lại lịch sử ADR-0001.
- **Verification cần lập sau quyết định:** inference thiếu/sai key phải bị từ chối trước khi gọi upstream; key hợp lệ được chấp nhận; không truy cập được qua LAN; frontend/log/DB không có credential; client không đọc token/session Google; fake listener phải có kết quả theo threat model được duyệt. Kiểm tra hành vi cụ thể trên phiên bản đã chọn, không dùng `GET /health=200` làm bằng chứng xác thực. Không chạy các kiểm thử này hoặc gọi proxy thật trong lượt cập nhật tài liệu.
- **Đã thực hiện:** sửa tên/ranh giới tích hợp trong spec và project context; bổ sung cảnh báo compatibility trong API/security; giữ nguyên endpoint/schema, mức bảo mật và review status. Chưa có quyết định mới để tạo ADR thay thế.
- **Điểm dừng ở lượt này (đã được trả lời ở lượt tiếp theo):** cần số phiên bản Antigravity Tools đang chạy; không yêu cầu cung cấp key, token/session, email tài khoản hoặc log/config chứa secret. R2-001 chưa xử lý xong. Nhận diện proxy cũng chưa đóng R2-002: model hỗ trợ không bảo đảm quyền sử dụng, chi phí, route upstream hoặc chính sách dữ liệu.

#### Version follow-up — v4.8.4, lịch sử trước khi chấp thuận

- **Dữ kiện đã chốt:** owner trả lời `v4.8.4`. [Release v4.8.4](https://github.com/lbjlaq/Antigravity-Manager/releases/tag/v4.8.4) và [Git tag ref](https://api.github.com/repos/lbjlaq/Antigravity-Manager/git/ref/tags/v4.8.4) xác nhận tag trỏ commit `0269f045f4e35f34b9ee3b3bcd6c0ff1e741378f`. Vì vậy bằng chứng source ở trên áp dụng cho release này; không còn blocker thiếu số phiên bản. Chưa xác minh binary hoặc config cục bộ và không suy ra chúng từ tag.
- **Nguyên nhân còn lại:** bearer/API-key auth không xác thực server/process nhận request. Spec FR-CAP-02, API §6, security T-03/T-15/T-19 và ADR-0001 còn yêu cầu process authentication/per-launch secret/IPC chưa có cơ chế được chứng minh tương thích với bridge hiện có. Câu từ chối plain HTTP vẫn mâu thuẫn base URL loopback HTTP. Biết số phiên bản chưa giải quyết những điểm này.
- **Phương án đề xuất, CHƯA ÁP DỤNG:** giữ `http://127.0.0.1:8045/v1`, tắt LAN (`allow_lan_access=false`), bật xác thực rõ ràng cho inference (`auth_mode=all_except_health`, không dùng `auto`/`off`). Proxy key mới sau rotation chỉ nằm ở backend; mật khẩu quản trị tách riêng và không cấp cho app; app không đọc token/session Google. Chỉ cho phép endpoint cần thiết, không theo redirect hoặc chuyển sang remote; giữ bảo vệ browser/session và tối thiểu hóa dữ liệu. Health public không được chứa secret và không là bằng chứng xác thực. Đây là hợp đồng ứng dụng được đề xuất, không tuyên bố tất cả route của proxy đều yêu cầu key.
- **Trade-off:** phương án này dùng giao diện HTTP/API-key sẵn có, không thêm sidecar hay quản lý certificate. Đổi lại, tin cậy máy/tài khoản Windows và **không cam kết chống tiến trình độc hại trên máy giả mạo proxy để nhận key/payload**. Nếu cần bảo đảm danh tính server mạnh hơn, phải thiết kế ranh giới IPC hoặc TLS có xác minh danh tính và việc bảo vệ chặng cuối tới proxy; chỉ đặt một sidecar phía trước không tự giải quyết vấn đề. Chưa chọn hay triển khai phương án bổ sung đó.
- **Tài liệu ảnh hưởng khi được duyệt:** spec FR-CAP-02/OQ-13; API §6; security T-03/T-15/T-19; ADR kế tiếp thay phần bridge boundary của ADR-0001; runbook bridge-failure. UI, model allowlist, chi phí và consent không được tự đổi theo quyết định này. Không tạo/sửa `CONSTRAINTS.md` trong lượt này.
- **Đã thực hiện:** cập nhật số phiên bản và phân biệt bằng chứng source với cấu hình thực tế trong spec/API/security/context; ghi changelog. Không đổi các yêu cầu auth hiện hành hoặc tự đánh dấu resolved. Cần kiểm chứng thiếu/sai key không gọi upstream, key hợp lệ, LAN bị chặn, secret redaction và health không lộ dữ liệu theo phiên bản đã xác định; đây là test implementation sau khi thiết kế được duyệt, không yêu cầu viết app code để xác nhận số phiên bản.
- **Điểm dừng ở lượt này (đã được trả lời):** cần owner chấp thuận hoặc từ chối ranh giới tin cậy Windows + HTTP loopback/API key đề xuất ở trên. Lượt tiếp theo owner trả lời “chấp nhận”; resolution dưới đây áp dụng quyết định đó, không tự hạ priority.

#### Resolution — owner chấp thuận, 29/09/2026

- **Nguyên nhân:** draft đòi xác thực process/IPC chưa chứng minh tương thích Antigravity và từ chối plain HTTP trong khi chọn HTTP loopback. API-key auth không thể chứng minh danh tính listener.
- **Phê duyệt:** owner chấp thuận phương án đã trình: HTTP `127.0.0.1:8045`, tắt LAN, key inference bắt buộc chỉ ở backend, tin cậy máy/tài khoản Windows và không cam kết chống tiến trình cục bộ giả mạo proxy. Đây là chấp thuận residual risk có ghi nhận, không bỏ qua finding hay giảm severity.
- **Đã xử lý:** tạo ADR-0002 accepted riêng boundary này; thêm supersession notice cho ADR-0001 nhưng giữ nguyên thân lịch sử. Đồng bộ FR-CAP-02/data rules/OQ/AC-36, API §6/BR-AUTH-01–08, security T-03/T-12/T-15/T-19, observability, runbook và project context. HTTP được phép đúng chặng local này; remote/redirect/ambient proxy bị chặn; không có IPC/per-launch bridge secret hoặc lời hứa fake-listener rejection. Metadata app được loại bỏ trước khi vào proxy thay vì kỳ vọng proxy tự xóa.
- **Tài liệu ảnh hưởng:** `docs/spec.md`, `docs/api-contract.md`, `docs/security-review.md`, `docs/observability-plan.md`, `docs/adr/0001-architecture.md` (notice), `docs/adr/0002-antigravity-loopback-trust-boundary.md`, `docs/runbooks/bridge-failure.md`, `docs/project-context.md`. Không có thay đổi route/component/luồng thao tác UI; UI hiện có tiếp tục nhận lỗi cấu hình/dependency và không nhận secret.
- **Verification:** đã kiểm tra link file tương đối trong 10 tài liệu thay đổi: không có link thiếu đích; `AC-36` và đủ `BR-AUTH-01`–`08` hiện diện; so sánh văn bản trước/sau xác nhận thân ADR-0001 không đổi ngoài supersession notice, và các status marker của spec/review không đổi. Rà các yêu cầu process/IPC/plain-HTTP cũ trong tài liệu hiện hành: chỉ còn câu phủ định hoặc chỉ dẫn supersession, không còn là yêu cầu bridge bắt buộc. Test application/live profile chưa chạy vì đây là lượt documentation-only; kiểm tra văn bản không thay thế full doubt-driven review hay runtime tests. Google credential, proxy config và `CONSTRAINTS.md` không bị sửa.
- **Kết quả:** nguyên nhân khiến R2-001 chặn thiết kế đã được giải quyết bằng quyết định có authority và contract tương ứng. Cần full doubt-driven re-review sau khi xử lý các blocker còn lại; không chuyển trạng thái toàn bộ review hoặc bắt đầu planning ở lượt này.

### R2-002 — Cloud consent/cost policy is not enforced (historical before ADR-0004)

- **Current disposition:** Consent/revocation behavior is addressed in design by owner approval and ADR-0003. The cloud policy itself remains blocked; consent is not treated as provider/quota/billing/retention approval.
- **Priority:** Critical
- **Nguyên nhân/evidence:** `OQ-01` leaves provider/model/quota/billing/retention/region open; UI only discloses cloud use when policy exists; no persisted consent/revocation contract exists.
- **Impact:** User text may be sent to a billable/unapproved provider without auditable acceptance.
- **Đề xuất xử lý:** Owner must choose provider/model allowlist, billing/quota/retention/region policy and consent/revocation behavior. API must fail closed before cloud calls without that state; UI and ACs must test no-consent/quota paths.
- **Tài liệu ảnh hưởng:** `docs/spec.md`, `docs/api-contract.md`, `docs/ui-architecture.md`, `docs/security-review.md`, `docs/adr/0001-architecture.md`.

- **Resolution:** Owner answered “chấp nhận” to the proposal: ask before first AI transfer, persist the choice, allow withdrawal that blocks new AI requests, and keep local learning available. Added ADR-0003; synchronized spec SEC-08/09, DATA-12, AC-37–40, API singleton/dispatch gate/CONSENT-01–10, UI J7 and consent state matrix, security T-22, observability consent events and local runbook/verification guidance. The gate is backend-owned and default-deny; it does not rely on browser localStorage or a disclosure banner.
- **Boundary retained:** Grant requires a current `READY` policy version. A missing/blocked/changed policy prevents grant or AI dispatch. Revoke works without bridge/network and does not erase local study records. Requests admitted to transport before revoke may complete; the app cannot recall transmitted data or promise third-party deletion. Audio and telemetry export are separate permissions. Owner clarified that paid fallback is not prohibited in principle; provider/model allowlist, exact fallback route/billing mode, entitlement/quota, retention/region, proxy routing and policy text remain unresolved and cannot be fabricated to make consent “ready”.
- **Verification (historical):** document checks passed for `AC-37`–`AC-40`, `CONSENT-01`–`10`, relative links and unchanged status markers; no live bridge/cloud request or application test was run. The later owner-authorized ADR-0004 closure supplies the v1 policy fixture; concurrent tabs, policy changes, lost responses, storage failure and admission ordering remain implementation tests.
- **Tài liệu ảnh hưởng:** `docs/spec.md`, `docs/api-contract.md`, `docs/ui-architecture.md`, `docs/security-review.md`, `docs/observability-plan.md`, `docs/adr/0003-ai-consent-and-revocation.md`, `docs/project-context.md`.

### R2-003 — Markdown/SQLite crash consistency is still not deterministic

- **Priority:** Major
- **Nguyên nhân/evidence:** API now describes a journal/reconciliation protocol but leaves exact journal schema, ordering and repair policy in `OQ-08`/`OQ-13`; source replacement can still precede SQLite commit.
- **Impact:** A crash can leave file, search/detail/queue and projection divergent with no deterministic user repair state.
- **Đề xuất xử lý:** Owner must approve durable intent/outbox ordering, recovery/repair endpoint, write blocking and failure-injection ACs before source writes are planned.
- **Tài liệu ảnh hưởng:** `docs/spec.md`, `docs/api-contract.md`, `docs/security-review.md`, `docs/adr/0001-architecture.md`.

### R2-004 — Last-write-wins conflicts with ETag conflict UI

- **Priority:** Major
- **Nguyên nhân/evidence:** Spec J3/BR-13 says last save wins; API/UI use `If-Match` and a conflict dialog; API labels this provisional under `OQ-08`.
- **Impact:** App/editor writes have different outcomes and acceptance tests cannot assert one deterministic policy.
- **Đề xuất xử lý:** Owner must choose LWW with revision/tie/lost-update warning or explicit merge; then align spec/API/UI/security tests.
- **Tài liệu ảnh hưởng:** `docs/spec.md`, `docs/api-contract.md`, `docs/ui-architecture.md`, `docs/security-review.md`.

### R2-005 — Quiz/SRS semantics have no test oracle

- **Priority:** Major
- **Nguyên nhân/evidence:** `OQ-02`/`OQ-03`/`OQ-04`/`OQ-07`/`OQ-12` leave ratings, weakest-result mapping, rubric, snapshot/state/limits, streak and dashboard formulas open; API/UI expose only configured placeholders.
- **Impact:** Due scheduling, quiz-to-SRS, lifecycle and metrics cannot be implemented without inventing breaking policy.
- **Đề xuất xử lý:** Owner must approve the business rules and regenerate enums/formulas/AC fixtures; provisional placeholders cannot be frozen as `/v1`.
- **Tài liệu ảnh hưởng:** `docs/spec.md`, `docs/api-contract.md`, `docs/ui-architecture.md`, `docs/adr/0001-architecture.md`.

### R2-006 — Feedback history retrieval (resolved; prior blocker retracted)

- **Priority:** Major at discovery; resolved in the current contract
- **Nguyên nhân/evidence:** `DATA-11` requires history, but the API previously exposed only POST feedback. The contract now adds `GET /api/v1/quiz-questions/{questionId}/feedback` and UI `FeedbackHistory`.
- **Impact:** Resolved by the applied endpoint/schema/test changes; failed/validated feedback can now be reloaded and retried by answer revision.
- **Đề xuất xử lý:** Keep the GET/list endpoint in the generated OpenAPI and add reload/retry contract tests.
- **Tài liệu ảnh hưởng:** `docs/api-contract.md`, `docs/ui-architecture.md`.

### R2-007 — Legacy Markdown mapping can still misidentify forms/dates

- **Priority:** Major
- **Nguyên nhân/evidence:** Existing `DD-MM-YYYY.md` and H1 conventions differ from API ISO dates; existing entries can contain multiple parts of speech and related-form rows. `OQ-05`/`OQ-14` do not define split/merge/identity mapping.
- **Impact:** First sync can assign a wrong note day, collapse/duplicate word forms/cards or drop context fields.
- **Đề xuất xử lý:** Owner must approve date authority, AST/unknown-field preservation, multi-part-of-speech split/merge identity and parser/serializer fixtures before writes.
- **Tài liệu ảnh hưởng:** `docs/spec.md`, `docs/api-contract.md`, `docs/security-review.md`, `docs/adr/0001-architecture.md`, `docs/vocabularies/README.md`.

### R2-008 — Search performance gate is not executable

- **Priority:** Major
- **Nguyên nhân/evidence (historical before ADR-0004):** API calls n-gram/index strategy unverified; repository had no pinned runtime, 100k fixture or benchmark harness; `OQ-11` was then open. ADR-0004 now fixes the benchmark profile and gate; evidence is still required during implementation.
- **Impact:** Correctness and ≤1s latency cannot be reproduced or audited.
- **Đề xuất xử lý:** Owner must approve/pin fixture generator, normalization/query semantics, index revision, Python/SQLite/browser build and cold/warm protocol; add a release benchmark gate.
- **Tài liệu ảnh hưởng:** `docs/spec.md`, `docs/api-contract.md`, `docs/ui-architecture.md`, `docs/adr/0001-architecture.md`, project context.

### R2-009 — Launcher/bootstrap lifecycle is not implementable

- **Priority:** Major
- **Nguyên nhân/evidence:** `OQ-09` leaves mutex, port ownership, token issuance, readiness wait, duplicate focus, crash/restart and fallback behavior open; API only defines token exchange.
- **Impact:** Startup, stale-tab, duplicate-launch and stopped-backend acceptance tests cannot be implemented.
- **Đề xuất xử lý:** Owner must approve launcher state machine and Windows primitive; then add process/port/token/restart tests and runtime manifest.
- **Tài liệu ảnh hưởng:** `docs/spec.md`, `docs/api-contract.md`, `docs/ui-architecture.md`, `docs/security-review.md`, `docs/adr/0001-architecture.md`.

### R2-010 — Status/telemetry contract needed lifecycle verification

- **Priority:** Major
- **Nguyên nhân/evidence:** Observability promised metrics/status and rotating logs without cadence/lifecycle; API lacked metric fields. The contract now adds bounded local metrics to `StatusSummary`, 30-second polling, local retention/ACL/rotation defaults and runbook links.
- **Impact:** Resolved provisionally by the applied status/observability/runbook changes; retention values remain an `OQ-13` configuration gate.
- **Đề xuất xử lý:** Keep metrics local-only, validate `Cache-Control: no-store`, rotation and deletion tests before implementation.
- **Tài liệu ảnh hưởng:** `docs/api-contract.md`, `docs/ui-architecture.md`, `docs/observability-plan.md`, `docs/security-review.md`.

### R2-011 — Durable-data recovery boundary is unspecified

- **Priority:** Major
- **Nguyên nhân/evidence:** In-app backup is out of scope; `OQ-13` leaves restore/export/migration rollback/retention open; the runbook references an unapproved procedure.
- **Impact:** Corruption or migration failure can permanently lose SRS/quiz/feedback, and operations cannot promise safe recovery.
- **Đề xuất xử lý:** Owner must approve supported user-managed backup/restore/export and migration rollback, or explicitly accept loss and remove recovery claims; add integrity/restore ACs.
- **Tài liệu ảnh hưởng:** `docs/spec.md`, `docs/adr/0001-architecture.md`, `docs/security-review.md`, `docs/observability-plan.md`, runbooks.

### R2-012 — AI content quality remains untestable

- **Priority:** Major
- **Nguyên nhân/evidence:** Complete academic word-family/meaning quality is required, but `OQ-06` has no authority/rubric; AC-02 only renders a fixture and shape validation cannot detect semantic omission/hallucination.
- **Impact:** The app can pass automation while storing incorrect learning content.
- **Đề xuất xử lý:** Owner must approve an authoritative dictionary/rubric and human verification transition, or explicitly relax to suggestions requiring confirmation before save; add semantic acceptance fixtures.
- **Tài liệu ảnh hưởng:** `docs/spec.md`, `docs/api-contract.md`, `docs/ui-architecture.md`, `docs/security-review.md`.

### R2-013 — Error recovery DTO was underspecified

- **Priority:** Major
- **Nguyên nhân/evidence:** UI expected operation IDs/recovery guidance while the prior error union did not carry them consistently. The contract now defines discriminated `FIELD_ERRORS`, `CONFLICT`, `RETRY`, `RESOURCE` and `RESTORE` details and aligns examples.
- **Impact:** Resolved provisionally in the API/UI contract; generated OpenAPI must preserve these variants and tests must cover each code.
- **Đề xuất xử lý:** Add schema-diff and error-fixture contract tests before `/v1` freeze.
- **Tài liệu ảnh hưởng:** `docs/api-contract.md`, `docs/ui-architecture.md`, `docs/security-review.md`.

### R2-014 — Autosave PUT lacked operation reconciliation

- **Priority:** Major
- **Nguyên nhân/evidence:** UI promises abort-after-commit reconciliation, but the previous answer `PUT` contract had no operation ID/idempotency. The API now requires an idempotency key and returns an operation ID tied to `draftRevision`.
- **Impact:** Resolved provisionally; generated OpenAPI and abort/retry tests must preserve the operation record.
- **Đề xuất xử lý:** Add contract tests for abort-after-commit, same-key replay, stale revision and operation status.
- **Tài liệu ảnh hưởng:** `docs/api-contract.md`, `docs/ui-architecture.md`, `docs/spec.md` FR-ASM-09/OQ-09.

### R2-015 — Word-form PATCH lacked unknown-outcome recovery

- **Priority:** Major
- **Nguyên nhân/evidence:** Source/projection PATCH could commit before the response and had no operation record. The API now requires `Idempotency-Key` and returns `WordFormMutationResult` with operation/source revision.
- **Impact:** Resolved provisionally; source journal/revision policy remains coupled to `OQ-08`/`OQ-13`.
- **Đề xuất xử lý:** Add same-key replay, abort-after-commit, source revision and card-reset atomicity tests.
- **Tài liệu ảnh hưởng:** `docs/api-contract.md`, `docs/ui-architecture.md`, `docs/security-review.md`, `docs/spec.md` FR-VOC-03/04/07.

### R2-016 — Quiz restore DTO omitted the answer collection

- **Priority:** Major
- **Nguyên nhân/evidence:** `QuizAttempt` prose promised saved `Answer[]`, but the example omitted it. The response now includes `answers: Answer[]` and the normative `Answer` schema includes revision/state/operation ID.
- **Impact:** Resolved provisionally; reload/offline restore is now contract-testable.
- **Đề xuất xử lý:** Add fixture tests for blank, draft, scored, stale and failed-answer states.
- **Tài liệu ảnh hưởng:** `docs/api-contract.md`, `docs/ui-architecture.md`, `docs/spec.md` FR-ASM-09/10.

### R2-017 — Numeric limits/timeouts remain unapproved

- **Priority:** Major
- **Nguyên nhân/evidence:** Capabilities expose limits but no approved values exist; `OQ-11` asks for lookup/feedback timeout and performance conditions, while security requires bounded calls.
- **Impact:** 413/503/timeout/DoS and 120-second lookup acceptance cannot be reproduced.
- **Đề xuất xử lý:** Owner must approve caps, timeout/cancellation, retry/backoff and rate limits, or explicitly define them as versioned safe defaults in `CONSTRAINTS.md`.
- **Tài liệu ảnh hưởng:** `docs/spec.md` PERF-01/03/OQ-11, `docs/api-contract.md`, `docs/security-review.md` T-11, `docs/observability-plan.md`.

### R2-018 — Audio provider and media security remain undecided

- **Priority:** Major
- **Nguyên nhân/evidence:** API now refuses arbitrary redirects, but provider/voice/media size/CSP/error behavior remains `OQ-06`; spec AC-25 and UI `AudioButton` still require a concrete stream behavior.
- **Impact:** Audio cannot be implemented or security-tested without choosing proxy vs approved client media and its privacy/error policy.
- **Đề xuất xử lý:** Owner must choose the audio boundary and approve host/voice/size/CSP/range/error contract, then add AC-25 fixtures.
- **Tài liệu ảnh hưởng:** `docs/spec.md` FR-CAP-10/OQ-06/AC-25, `docs/api-contract.md`, `docs/ui-architecture.md`, `docs/security-review.md` T-08.

### R2-019 — Accessibility acceptance is still not an executable oracle

- **Priority:** Major
- **Nguyên nhân/evidence:** UI preserves keyboard guidance but spec OQ-10 leaves Sci-Link, zoom, contrast and focus acceptance open; AC-24 has no focus-order/manual matrix.
- **Impact:** Teams can claim or fail accessibility based on undocumented thresholds; UI work may expand or regress without a gate.
- **Đề xuất xử lý:** Owner must approve the target/threshold/manual matrix, then add keyboard focus-order and contrast fixtures. Until then the UI targets are guidance, not readiness evidence.
- **Tài liệu ảnh hưởng:** `docs/spec.md` A11Y-01–05/OQ-10/AC-24, `docs/ui-architecture.md` accessibility/test strategy.

### R2-020 — Failed feedback persistence now has an explicit contract

- **Priority:** Major
- **Nguyên nhân/evidence:** Previous POST semantics did not state whether dependency errors persisted a failed row. The API now requires a durable `FAILED` record before returning timeout/auth/quota/schema errors; UI history reloads it.
- **Impact:** Resolved provisionally; implementation must test transaction ordering, retry idempotency and redacted failure fields.
- **Đề xuất xử lý:** Add fake-bridge failure/reload/retry contract tests and ensure no prompt/answer body is logged.
- **Tài liệu ảnh hưởng:** `docs/api-contract.md`, `docs/ui-architecture.md`, `docs/spec.md` DATA-11/FR-ASM-15, `docs/observability-plan.md`.

## Fresh-context re-review after ADR-0003 — 29/09/2026

The fresh adversarial reviewer examined the current bridge/consent artifacts. The findings below are the reconciliation record; the reviewer did not modify files.

| Finding | Reconciliation and action | State |
|---|---|---|
| R3-001 — bridge residual was called “addressed” too broadly | Kept ADR-0002 owner acceptance as a design decision, but clarified that local impersonation remains a Critical residual/release gate. Profile, key rotation, LAN isolation, redaction and `BR-AUTH-01`–`09` are required before release; no fake-listener protection is claimed. | Addressed in design; runtime gate remains |
| R3-002 — selected provider/model/route could bypass policy | Added structured `dispatchRules`, server-owned provider/model/route/billing matching, selected-route provenance, BR-AUTH-09 and fail-closed dispatch language. ADR-0004 now supplies the v1 allowlist/default route; entitlement/quota evidence remains a runtime gate. | Closed at design level; implementation test pending |
| R3-003 — policy freshness compared only version | Added immutable `digest`, accepted digest, same-version mutation failure, digest-based `STALE`/dispatch checks and CONSENT-11. | Addressed in design; implementation test pending |
| R3-004 — process-local consent fence | Replaced single-coordinator-only wording with durable SQLite compare-and-set/admission fence that orders revoke vs. dispatch across processes; added CONSENT-12. Normal launcher/single-instance remains R2-009/OQ-09. | Addressed in design; implementation test pending |
| R3-005 — consent audit history too weak | Added append-only `AiConsentEvent`, policy/scope/rule snapshot and retention dependency tied to related AI result/feedback; ADR-0004/runbook own the v1 export/deletion/backup boundary. | Closed at design level; retention implementation test pending |
| R3-006 — ADR-0001 could resurrect old bridge auth | Marked the old bridge paragraph as historical and added a direct “MUST use ADR-0002” notice; retained the old implementation sequence as ADR history. Current implementers use ADR-0002/API §6, not the superseded sentence. | Addressed |
| R3-007 — AC-34 overstated auth evidence | Recast AC-34 as compatibility-only; installed v4.8.4 auth/profile proof is separate BR-AUTH evidence. | Addressed |
| R3-008 — one boolean consent ignored scopes | READY requires exactly all three AI scopes and a rule per scope; dispatch checks requested scope. | Addressed in design; schema/test pending |
| R3-009 — failed feedback retry reused idempotency operation | Added fresh key + `retryOfOperationId` with same canonical answer revision; UI retry and API contract no longer reuse a terminal failed key. Consent/policy is checked again. | Addressed |
| R3-010 — AC-27 still used CLI | Replaced with app `POST /api/v1/lookups` through Antigravity v4.8.4; records app/bridge/profile/route state and keeps OQ-11 timing gate. | Addressed |
| R3-011 — audio bypassed a defined consent boundary | ADR-0004 chooses local browser SpeechSynthesis; no provider/network request or audio consent exists in v1. Missing voice disables the button. | Addressed |
| R3-012 — disclosure completeness was free-form | Added required structured categories, recipients, retention, region, cost/quota, withdrawal fields and per-field READY validation; UI/CONSENT tests assert them. ADR-0004 supplies the v1 fixture and provider-controlled retention/region boundary. | Closed at design level; implementation test pending |
| R3-013 — operation lacked consent provenance | Added redacted `aiProvenance` to `Operation` (digest/version/scope/rule/admission state/time) and linked it to event/feedback retry reconciliation; no content or secret fields. | Addressed in design; implementation test pending |

**Fresh review limitations:** This was a documentation review only. No application code, installed proxy profile, real cloud request, multi-process race test, browser journey or storage failure injection ran. These are verification gates, not evidence of passing. Cross-model CLI review was not run; no external CLI was authorized.

## Owner-authorized closure pass — ADR-0004

The owner instructed the agent to choose reasonable defaults for every remaining blocked product decision. ADR-0004 and the synchronized contracts apply those choices:

| Prior blocker | Closure decision | Verification still required |
|---|---|---|
| R2-002 provider/cost/policy | Gemini `gemini-3.8-flash-high`, no automatic fallback by default; paid fallback permitted only by a future explicit policy; provider-controlled retention/region disclosed; fail closed without entitlement/quota/policy. | Installed profile, policy fixture, quota/auth/error and consent tests |
| R2-003 source/SQLite crash consistency | Durable hash journal, atomic replace, startup reconciliation and `DEGRADED` write stop in ADR-0004/API. | Failure injection and Windows filesystem tests |
| R2-004 LWW/ETag | ETag/revision conflict with `409`; no silent last-write-wins. | Concurrent editor/API tests |
| R2-005 quiz/SRS | Five-box SRS, explicit ratings/mapping, fixed limits and immutable quiz snapshot. | Rule fixtures and replay tests |
| R2-007 legacy identity/date | Normalized lemma/POS/family identity, legacy path/date preservation and round-trip rules. | Legacy parser/serializer fixtures |
| R2-008 benchmark | Named Windows 11/Python 3.12/SQLite/100k fixture, p95 search gate and reproducible protocol. | Benchmark run artifact |
| R2-009 launcher | Named mutex, readiness/duplicate-launch/60s bootstrap/autosave defaults. | Windows lifecycle tests |
| R2-011 recovery | No in-app backup; user-managed closed-directory copy plus journal repair/DEGRADED stop. | Integrity/restore/runbook tests |
| R2-012 AI quality | AI output is unverified suggestion; user confirmation plus fixed human-reviewed 100-form fixture. | Content fixture/human review record |
| R2-017 limits | Lookup 120s, quiz 60s, feedback 30s; bounded payloads/cancellation. | Timeout/load tests |
| R2-018 audio | Local browser SpeechSynthesis; no provider/network policy or audio consent in v1. | Browser voice availability/manual audio tests |
| R2-019 accessibility | WCAG 2.2 AA target, 200% zoom, contrast/focus/keyboard/manual matrix and Sci-Link as reference. | Browser/manual accessibility evidence |

All prior Critical/Major design blockers now have an owner-authorized decision and a verification contract. Implementation/runtime evidence and the separate `CONSTRAINTS.md` session remain workflow gates, not unresolved product decisions.

The earlier R2 sections below are preserved as historical evidence of what was previously missing. For current disposition, ADR-0004 and the closure table above are authoritative; a historical “Owner gate” label must not be read as an open decision after this closure pass.

### Second-review conclusion

R2-001 and R2-002 are addressed at design level by owner-approved ADR-0002/0003/0004, with explicit residual risks and implementation gates. R2-003, R2-004, R2-005, R2-007, R2-008, R2-009, R2-011, R2-012, R2-017, R2-018 and R2-019 are closed as design blockers by ADR-0004. No Critical or Major finding remains undecided; runtime tests, generated-contract checks, benchmark evidence, `CONSTRAINTS.md` and task planning are the next workflow phase.

### Final doubt-driven recheck — 29/09/2026

| Check | Result |
|---|---|
| Spec/API/UI consistency | Pass at document level: ADR-0004 values are used for model, fallback, SRS, quiz limits/snapshot, conflict semantics, audio and performance budgets. Historical OQ text is explicitly non-authoritative. |
| Critical/Major design findings | None undecided. R2/R3 historical findings point to the owner-authorized closure table; residual items are verification gates, not missing decisions. |
| Security and data exposure | Pass at design level: loopback/API-key trust boundary, consent/digest/fence, task-only payloads, redaction and provider-controlled retention/region limitation are explicit. |
| Operational readiness | Pass as a planning baseline: launcher, recovery, timeout, dashboard and observability contracts are documented. No runtime pass is claimed. |
| Remaining blockers | No design blocker. A separate planning session must formalize `CONSTRAINTS.md`, pin manifests/lockfiles and create implementation tasks; release still requires the listed runtime/security/accessibility/benchmark evidence. |

This recheck did not run application code, inference, installed-profile checks or browser/Windows tests. Those omissions are intentionally recorded as verification work rather than converted into a false design blocker.

## Required next gate

Create implementation tasks only in the planning session after `CONSTRAINTS.md` is formalized and the implementation verification gates are copied into tasks. The architecture decision set is ready for planning; runtime verification is not being claimed here.

REVIEW_STATUS: READY_FOR_PLANNING

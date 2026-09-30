# ADR-0003: Local AI consent and revocation

## Status

Accepted for the consent behavior approved by the owner: request permission before the first AI data transfer, persist the choice, allow withdrawal that blocks new AI requests, and retain local study functions. The API/UI mechanisms below implement that decision and remain subject to design review.

Complements [ADR-0002](0002-antigravity-loopback-trust-boundary.md); does not supersede its bridge trust boundary or accept the remaining provider/model/quota/billing/retention/region decisions in R2-002. The conversation approval is approval to build this control, **not** a pre-populated grant in the installed app.

## Date

29/09/2026 (`Asia/Bangkok`)

## Context

AI lookup, quiz generation and writing feedback send task-specific data beyond the local app. A disclosure banner alone does not record a user's choice or stop a direct API caller after withdrawal. The local app has no product account; the consent record belongs to the one local installation and is protected by the existing launch session, not a new login system.

## Decision

1. Default to no consent. The backend maintains a durable singleton consent record, immutable policy definition/digest and append-only consent events. A READY policy must structurally name data categories, recipients, retention, region, cost/quota, withdrawal limitation, exactly the three approved AI scopes, and an allowlisted provider/model/route/billing rule for each scope. No key, account identifier, user answer or vocabulary content belongs in this record. A policy is eligible for grant only after its unresolved product decisions are approved; arbitrary disclosure prose cannot make an incomplete policy consent-ready.
2. Offer the disclosure before first lookup, AI quiz generation or writing feedback. The user can decline and continue local study. Grant requires an explicit button; never infer permission from page load, Enter in the lookup field, opening a quiz or the owner's design approval. The same consent covers these three named operations only. Audio and telemetry export are separate boundaries, not implicitly granted.
3. Use the existing `/status` screen for viewing/withdrawing the choice, reachable from the shared shell. A contextual consent dialog does not introduce an account or general settings screen. After grant, ask the user to repeat the original AI action; saving consent never auto-submits their text.
4. Persist the grant's exact policy version **and immutable policy digest**, server timestamp, monotonic revision and latest choice; append the event with scope/provider/model/route/billing-mode snapshot. A policy version may never be edited in place: a digest change under the same version is a configuration-integrity failure and fails closed. Relevant changes to recipients, models/routing, data categories, cost or storage policy require a new version and explicit re-consent. A missing, blocked or mismatched policy fails closed independently of a previous grant. The configured operator policy, not a model name returned by an untrusted proxy, is the source of disclosure; route drift/fallback is rejected at dispatch rather than treated as consent.
5. Backend checks policy and consent before bridge preflight and again at dispatch admission. All three AI use cases share one gate with revoke/grant/policy changes; a READY policy must contain exactly these three scopes, and each dispatch must match its scope plus server-owned provider/model/route/billing rule. A successful revoke is committed durably before its response; any dispatch admitted after that commit is denied until a new valid grant. A request admitted to the HTTP transport earlier is already in flight and may still send/complete. No promise of recalling transmitted data, deleting provider copies or cancelling upstream processing is made. Pending unadmitted work cannot reuse old consent after a revoke/re-grant cycle.
6. Revoke needs no network, provider configuration or current policy version. It must work even if the bridge is down or the policy is missing. Concurrent grant requires a matching consent revision, version and digest; stale-tab grant must not overwrite withdrawal. Durable-write failure must not produce a success message. The UI locally blocks further AI actions while withdrawal outcome is unknown and reconciles from the backend. Admission/revoke ordering is a durable SQLite compare-and-set/fence, not merely an in-memory coordinator; it remains correct if two processes race, even though single-instance launch is separately required for normal operation.
7. Withdrawal does not erase saved words, quizzes, answers, scores or feedback. Already-dispatched results may be validated and persisted under the existing contracts; no new AI dispatch, retry or delayed job is authorized by their completion. Backend restart does not replay pending/unknown AI requests. Consent events and referenced immutable policy digests are retained at least as long as the related local AI result/feedback retention; exact deletion/export/backup behavior remains OQ-13. This is an explicit retention dependency, not a promise of indefinite audit history.

## Alternatives considered

- **Banner-only disclosure:** rejected; cannot enforce withdrawal or associate a saved choice with a specific policy.
- **Browser-only checkbox:** rejected as authority; stale tabs, direct API calls and cleared browser storage can disagree with it.
- **Confirmation before every AI call:** not selected; the approved behavior persists the choice. Each call still has an explicit user action and backend enforcement.
- **Separate consent service/account screen:** unnecessary for one local user. Existing app orchestration, SQLite persistence and `/status` suffice.

## Consequences

- `GET`/`PUT`/`DELETE /api/v1/ai-consent` expose one singleton; mutations use local session/CSRF guards and durable idempotency. `Operation` exposes redacted AI provenance/admission state so unknown outcomes and feedback retries can be reconciled without payloads. Detailed request/response, concurrency and tests are in API §4, §6 and §11.
- The grant/revoke path works independently of study-content operations. Withdrawing cannot be gated on a successful cloud call; granting cannot make an incomplete cloud policy safe.
- The dispatch boundary is an explicit limitation: withdrawal blocks later admissions, not network bytes already handed to the client transport. Durable database fencing orders cross-process revoke/admission; fake transport barriers must verify both race orderings.
- Only documentation is changed. No live request, credential, consent grant, application code or `CONSTRAINTS.md` change is authorized by this ADR.

## Verification gates

Map `AC-37`–`AC-40` to `CONSENT-01`–`CONSENT-12` in the API/UI. Verify default denial, structured disclosure completeness, immutable digest/same-version mutation, exact scope/route/model rules, explicit durable grant, refresh/restart, missing-policy block, wrong policy version, multi-tab/two-process revoke/admission conflicts, lost responses/idempotent replay, fresh-key feedback retry, revocation before/after dispatch, no implicit audio/export permission, redacted operation provenance and preserved local study data. UI must cover loading, no policy/no choice, saving, error, stale policy, success and unknown withdrawal outcome using keyboard controls.

These are design requirements, not executed test results. ADR-0004 supplies the remaining v1 cloud-policy defaults; implementation, profile and policy-fixture tests remain required before release.

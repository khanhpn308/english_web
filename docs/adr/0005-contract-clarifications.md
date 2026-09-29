# ADR-0005: Contract clarifications and deterministic v1 oracles

## Status

Accepted for T013. The owner explicitly confirmed the T013 document allowlist in this chat. This ADR clarifies ADR-0004 under that authority and the defaults already frozen in `CONSTRAINTS.md`. It supersedes only ADR-0004's ambiguous HARD, due-time and “stale editor gets 409” wording. ADR-0004's other policy decisions continue to apply; its historical text is preserved.

## Date

29/09/2026 (`Asia/Bangkok`)

## Context

The [conformance report](../reviews/contract-conformance-002.md) records eleven failing document probes before these changes. Business contracts have not yet been implemented: T005 establishes storage startup only. T013 must provide expected outputs before T006/T007/T014/T017 and the vocabulary/SRS/quiz tasks freeze DTOs or behavior. This decision introduces no application implementation, provider, fallback, network exposure or migration.

## Decision summary

### C013-01 — Quiz limits and sufficient source

- Counts are strict integers, each in `0..20`; total is `5..30`. Unknown types, booleans, fractions and negative counts fail `422 VALIDATION_ERROR` before bridge preflight. There is no separate requirement to include all three types; a 5/0/0 quiz is valid with sufficient sources.
- A `(question type, wordFormId)` pair occurs at most once per attempt. The same form may occur in different types, supporting the weakest-result rule. Each requested type count must be no greater than the number of eligible distinct forms for the selected date. An insufficient source fails `422 VALIDATION_ERROR`; the server does not reduce counts or invent sources.
- The positive AC-14 fixture has three eligible forms A/B/C (even if not due), with counts 2/2/1: MCQ A/B, cloze A/C, writing B. The creation snapshot has exactly five questions. Every eligible form is in the task source payload; unrelated history/context is absent.

| Counts mcq/cloze/writing | Eligible forms | Expected |
|---|---:|---|
| 1/1/1 | 3 | `422 VALIDATION_ERROR`, total 3 < 5; zero bridge calls |
| 2/2/1 | 3 | Valid, exactly five questions |
| 5/0/0 | 5 | Valid, exactly five MCQ questions |
| 0/0/0 or 2/1/1 | 3 | `422 VALIDATION_ERROR`, total below 5 |
| 10/10/10 | 10 | Valid, total 30 |
| 11/10/10 | 11 | `422 VALIDATION_ERROR`, total 31 |
| 21/4/0 | 21 | `422 VALIDATION_ERROR`, per-type maximum exceeded |
| 2/2/1 | 1 | `422 VALIDATION_ERROR`, insufficient distinct source forms |

### C013-02 — SRS transitions and calendar due time

Let `currentBox` be 0 (NEW) through 5. `AGAIN = 1`; `HARD = max(1, currentBox)`; `GOOD = min(5, currentBox + 1)`; `EASY = min(5, currentBox + 2)`. HARD preserves an existing box; NEW moves to 1. These transitions do not add a new card-state enum.

| Current box | AGAIN | HARD | GOOD | EASY |
|---:|---:|---:|---:|---:|
| 0 | 1 | 1 | 1 | 2 |
| 1 | 1 | 1 | 2 | 3 |
| 2 | 1 | 2 | 3 | 4 |
| 3 | 1 | 3 | 4 | 5 |
| 4 | 1 | 4 | 5 | 5 |
| 5 | 1 | 5 | 5 | 5 |

The server owns `reviewedAt` and quiz `submittedAt`. Convert that instant to a date in `Asia/Bangkok`, add the destination box interval as calendar days, take local midnight of the resulting date, and serialize that instant in UTC. Do not add a multiple of 24 hours to the review instant. NEW cards have `dueAt=null` and are immediately eligible; learned cards are due when `now >= dueAt`.

For `reviewedAt=2026-09-29T10:20:30Z` (17:20:30 in Bangkok):

| Destination box | Interval (local days) | Due local date at 00:00 +07:00 | `nextDueAt` UTC |
|---:|---:|---|---|
| 1 | 1 | 2026-09-30 | `2026-09-29T17:00:00Z` |
| 2 | 3 | 2026-10-02 | `2026-10-01T17:00:00Z` |
| 3 | 7 | 2026-10-06 | `2026-10-05T17:00:00Z` |
| 4 | 14 | 2026-10-13 | `2026-10-12T17:00:00Z` |
| 5 | 30 | 2026-10-29 | `2026-10-28T17:00:00Z` |

Boundary fixture: GOOD from box 1 at `2026-09-29T16:59:59Z` is due `2026-10-01T17:00:00Z`; at `2026-09-29T17:00:00Z` it is due `2026-10-02T17:00:00Z`. Quiz uses the same function at terminal submission, once per active form. A meaning/example reset returns box 0/dueAt null and preserves old events.

### C013-03 — Rubric, blank answers and weakest rating

`writing-rubric-v1` is one holistic self-score, not an average of AI criteria. Its integer 0–4 descriptors are visible in the runner and snapshotted at creation. AI comments concern target-word usage, grammar and clarity; no AI score changes the user's value.

| Score | Descriptor | SRS rating |
|---|---|---|
| 0 | No meaningful sentence, target word absent, or no assessable use of its meaning. | AGAIN |
| 1 | Target word is attempted, but wrong meaning/form or major grammar prevents the intended meaning. | AGAIN |
| 2 | Intended meaning is recognizable; word form or grammar needs substantial correction. | HARD |
| 3 | Correct meaning/form and understandable grammar; minor issues do not impede meaning. | GOOD |
| 4 | Correct meaning/form, grammatical and clear sentence, with natural and precise academic use. | EASY |

- MCQ answers store an option ID (or blank `""`); a nonblank ID outside the question's options is invalid. Cloze normalization is NFC, trim/collapse ASCII whitespace (`space`, tab, CR, LF, FF, VT), then Unicode case-fold. Only explicit snapshot alternatives match; spelling/punctuation remain strict. `robust`, `ROBUST`, ` robust ` pass for accepted `robust`; `robuts`, `robust.` and `a robust` fail.
- Before submit, blank objective answers remain BLANK, not a fabricated score. At terminal scoring a blank MCQ/cloze has outcome `BLANK`, `isCorrect=false`, rating AGAIN. A nonblank objective answer is CORRECT→GOOD or INCORRECT→AGAIN. Results preserve that distinction. Per-type `total` counts questions, `attempted` counts nonblank answers, `correct` counts correct answers; `accuracy=correct/attempted`, or null when attempted is zero, as in ADR-0004.
- WRITING may have `selfScore=null` while in progress. Submission with any writing `selfScore=null` fails `422 VALIDATION_ERROR`; result and SRS are unchanged. Blank writing is allowed only with an explicit user score 0 at submission; blank text with a positive score fails validation. An answer with no saved row is blank/null for these checks. Objective selfScore must be null. Floats, booleans or scores outside 0–4 fail validation.
- Weakest order is `AGAIN < HARD < GOOD < EASY`, grouped once per word form. Example: correct MCQ plus incorrect cloze plus writing 4 yields AGAIN, not an average. Missing writing score never becomes 0. An inactive card (no valid source or absent card) has `SKIPPED_INACTIVE` handoff, preserving historical result without scheduling a new review.

### C013-04 — New-date source creation and save receipts

The same POST save has two explicit variants. All preview forms are saved together, within the journal protocol; saving an existing preview needs no AI dispatch/consent.

1. **New date:** body `{lookupId, noteDate}` with `If-None-Match: *` and `Idempotency-Key`. Both source fields are omitted. The backend confirms absence of a source for that date and absence of the destination file, allocates a source ID, and creates `DD-MM-YYYY.md` under the configured root (e.g. `29-09-2026.md`). Initial committed revision is 1. The client never provides a path or constructs a source ID.
2. **Existing date:** body also contains `sourceId` and `sourceRevision`; `If-Match` must be the opaque ETag of that exact source. The ID's noteDate must match, the source must be VALID, and both revision and current file hash must match before replacement. A successful mutation increments source revision by one. The client obtains source identity/revision/ETag through the source read, not by inventing a value.
3. Source reads include `etag` per `SourceFile` because a paginated collection's HTTP ETag cannot stand for every source. Header and numeric revision must describe the same source version. Missing/partial/mixed preconditions fail `422 VALIDATION_ERROR`; foreign ID/date fails `422 CROSS_RESOURCE_MISMATCH`; INVALID/MISSING/ambiguous date sources are read-only (`409 SOURCE_NOT_WRITABLE`, or `404 SOURCE_MISSING` for a missing ID).
4. If a source/file appears between the absence read and a new-date write, return `409 REVISION_CONFLICT`; preserve its bytes and require a source re-read. Never silently switch the request to an append/overwrite. New source creation and an existing source update share crash-safe journal recovery; no source/card success is acknowledged before durable completion.
5. `SaveResult` carries `operationId`, `sourceId`, `sourceRevision`, `sourceEtag`, canonical forms, note date and created/reused card IDs. An identical key/fingerprint replays the same `201` receipt before re-evaluating changed preconditions; same key/different intent is `422 IDEMPOTENCY_KEY_REUSED`. Replay creates no second source/card. The local session must still be valid.

The UI defaults noteDate from current Bangkok date, sends the chosen date explicitly and preserves that selection across midnight. It lists the date source before save and uses the appropriate variant; conflicts retain the preview. Three fresh forms on a clean install create one source at revision 1 and three NEW cards; saving their same content at another date adds a source relation and reuses all three cards/SRS schedules.

### C013-05 — External edits versus stale API writes

An external editor writes ordinary Markdown and receives no API response. Watcher/startup/manual sync detects a changed content hash, validates/parses, advances the source revision and invalidates projections; identical bytes do not advance the revision. A valid meaning/example change resets the corresponding card; invalid content suspends that source while preserving history and other valid sources.

AC-28 fixture: API reads source revision 1/ETag E1/hash H1; external editor writes H2; hash/watcher sync produces revision 2/ETag E2; an API write with revision 1/E1 returns `409 REVISION_CONFLICT` and does not replace H2. After re-reading revision 2/E2 and explicit confirmation, the new write commits revision 3. Even before a watcher finishes, the write path rechecks the actual hash and rejects stale content. This does not claim protection against an actively malicious local filesystem racer beyond the existing Windows trust boundary.

### C013-06 — Disclosure of answer keys and explanations

The backend stores the complete immutable question snapshot, correct option/accepted answers and `explanationVi` at creation. Creation responses and IN_PROGRESS reads return only public question variants, saved answers/revisions and the rubric descriptors needed to self-score. They omit `correctOptionId`, `acceptedAnswers` and `explanationVi` entirely, including nested/cache responses.

After terminal submission commit, the submission response and subsequent attempt read include `QuizResult.questionResults` with objective outcome, correct key/accepted alternatives and Vietnamese explanation. Writing rubric stays visible before submission; requested AI comments are distinct from the concealed objective keys/explanations. No client scoring key or CSS-only hiding implements this boundary.

### C013-07 — Submit revision, terminal read and replay

- `QuizAttempt` is discriminated by `status: IN_PROGRESS | SUBMITTED`, with `result: QuizResult | null`; result is null only while IN_PROGRESS. `GET /api/v1/quiz-attempts/{attemptId}` is the read path for both runner and result route, with `Cache-Control: no-store`. No new result endpoint is necessary. A missing/corrupt snapshot/result yields `409 QUIZ_RESTORE_REQUIRED`, never an empty successful attempt.
- `submissionRevision` is the aggregate draft revision: 0 at creation, incremented once for each successful fresh answer write, atomically with that answer's revision. It differs from immutable `snapshotRevision` and per-question `draftRevision`. Key replays do not increment it. The runner flushes drafts, reads the latest attempt, then submits that revision with one stable key.
- Stale submission revision is `409 REVISION_CONFLICT` before scoring. Valid submission atomically stores terminal result, grouped review events/SRS update, SUBMITTED state and operation receipt. Failure before commit leaves all unchanged; a lost response after commit can be read/replayed locally. No cloud request is needed to score, submit or read a result.
- Identical key/fingerprint replays the original `201 QuizResult`; same key/different payload is `422 IDEMPOTENCY_KEY_REUSED`. A new submit intent for a SUBMITTED attempt returns `409 ALREADY_SUBMITTED` and the UI reads its stored result. New answer writes/score edits after submission also return `409 ALREADY_SUBMITTED`; historical receipts cannot reopen the attempt. Submission is a short synchronous local transaction: success is 201, an in-flight duplicate is `409 IDEMPOTENCY_IN_FLIGHT`, and GET operation returns `200 Operation` for reconciliation without a second submission/handoff. This resolves the former unspecified 202 submission alternative.
- Snapshot changes do not follow later source edits/deletion. Results remain readable offline with a healthy local API; inactive-source handoffs are skipped under C013-03, while historical answers/scores are retained.

### C013-08 — Size limits and exact rejection oracle

These are the existing `CONSTRAINTS.md` defaults, published by capabilities. Byte caps count actual UTF-8 body/file/bridge bytes; request streaming enforces the cap even without Content-Length. Content strings count Unicode code points (not UTF-16 units or graphemes); count after the field's defined normalization. General collections count elements per collection, with tighter quiz/pagination/term limits taking precedence.

| Boundary | Inclusive cap | At cap with otherwise valid input | At cap + 1 |
|---|---:|---|---|
| Request JSON | 1,048,576 bytes (1 MiB) | Eligible for normal validation | `413 PAYLOAD_TOO_LARGE`, no side effect |
| Source Markdown | 8,388,608 bytes (8 MiB) | Eligible for parse/write | `413 PAYLOAD_TOO_LARGE`; no replacement; externally oversized source becomes INVALID |
| Bridge response | 4,194,304 bytes (4 MiB) | Eligible for schema validation | `502 BRIDGE_INVALID_RESPONSE`, no validated result; persist redacted failure |
| Content string | 4,096 code points | Eligible for schema validation | Client: `422 VALIDATION_ERROR`; bridge: `502 BRIDGE_INVALID_RESPONSE` |
| General collection | 100 elements | Eligible for schema validation | Client: `422 VALIDATION_ERROR`; bridge: `502 BRIDGE_INVALID_RESPONSE` |

A UTF-16 surrogate pair representing one astral character is one Unicode code point. Malformed Unicode is invalid; no boundary silently truncates. A provider's smaller actual configured limit is checked by the adapter as required by CONSTRAINTS; it cannot authorize a larger product cap. Missing/invalid limit configuration is `503 CONFIGURATION_REQUIRED`, not an unlimited default.

### C013-09 — Bootstrap, session and durable restart

- A bootstrap token is single-use, valid only while `now < issuedAt + 60 seconds`. At 59.999s a first valid exchange can return 204; at 60s it returns `401 SESSION_INVALID`. Concurrent exchanges have at most one success; replay returns the same typed 401. Clear the fragment before app navigation; never retain it in application state, logs or examples with real credentials.
- A browser session is valid only while its issuing backend process is alive and `now < issuedAt + 28,800 seconds` (8 hours), using a monotonic clock for elapsed checks. It is non-sliding. Refresh/read/mutation does not extend it. A same-origin second tab shares the cookie and original expiry. Expiry, normal shutdown, crash or restart invalidates the old session; no persisted cookie grants a new process access. Missing cookie is `401 SESSION_REQUIRED`; present expired/invalid cookie is `401 SESSION_INVALID`.
- The established loopback HttpOnly/SameSite=Strict cookie/Origin rules apply. The launcher/trusted bootstrap page supplies a fresh token for explicit rebootstrap. This never creates a product login.
- Durable answer drafts, results, source/card history, consent and operations survive restart. Rebootstrap restores them through their read APIs; it does not erase drafts or resubmit AI work. Only acknowledged drafts are guaranteed durable. Revoke remains persisted, so restart plus a fresh session still denies new AI actions. An old grant receipt cannot turn consent back on; GET consent remains authoritative.

### C013-10 — Deadlines, operation outcomes and retention

The monotonic budget starts at server request admission and includes validation, local admission checks, bridge preflight, transport, parsing and completion for that operation: lookup 120s, quiz generation 60s, writing feedback 30s. Browser end-to-end p95 targets remain separately measured from user action through rendering under the named fixture. The server cannot reset the budget per stage or retry.

At `elapsed >= budget`, stop further dispatch/success and return the typed timeout mapping `503 BRIDGE_UNAVAILABLE` with operation reference and redacted TIMEOUT category in the operation. A transport not yet admitted or a known failure is FAILED; an admitted request whose external outcome cannot be established is UNKNOWN. Cancellation follows the same known/unknown distinction and never authorizes redispatch. A definite result committed before the deadline but followed by a lost HTTP response remains success on replay/read. A reply arriving only after timeout cannot turn that timed-out intent into a newly acknowledged success, start another request or duplicate a handoff; retain its UNKNOWN/failed-feedback evidence for explicit reconciliation.

Durable idempotency intents, terminal receipts and minimal used-key fingerprints are retained for the **lifetime of the local database** in v1. No automatic TTL/cleanup makes a used key a fresh billable intent. Consent events and referenced immutable policy snapshots/digests remain with related results/history and are part of user-managed backup. Diagnostic logs retain the separate five 10 MiB files/14-day policy; logs are not operation receipts. A future purge/export needs a separate approved contract.

Boundary fixtures for 120/60/30s use a fake monotonic clock: otherwise valid completion just below the deadline is eligible for success; completion at/after the deadline is a typed timeout, without budget reset or background inference retry. Revocation/restart tests hold a request before admission, persist revoke, and verify zero new bridge calls after release/rebootstrap; an admitted earlier request may finish as disclosed by ADR-0003.

### C013-11 — Positive examples are contract data

Examples use reviewed synthetic vocabulary and symbolic opaque IDs. Positive learning previews contain nonempty meaning/example fields; missing IPA/link is explicit null with MISSING verification. Consent views include acceptedPolicyDigest, and cloze drafts do not carry writing self-scores. These fixes make examples useful as future DTO fixtures; they do not verify semantic completeness of real AI content or constitute provider/profile approval. T017 owns generated schema/DTO comparison once its tooling exists.

## Alternatives considered

- Advancing HARD or scheduling review-instant + 24-hour multiples leaves agents choosing different oracles. Preserve the current box and use local calendar midnight so date queues/streak share the approved timezone.
- Requiring a client source ID for a fresh install has no valid producer; silently resolving an existing source without a precondition risks lost edits. Conditional creation plus explicit existing-source preconditions uses the same save endpoint and journal.
- Sending explanations before submit leaks scoring content. Public question variants plus a terminal result preserve offline study and deterministic server scoring.
- A separate result endpoint is unnecessary while GET attempt already restores the snapshot/state. A required nullable result on that read closes the result route with no new resource.
- Expiring used idempotency keys can convert a delayed retry into a new paid request. Database-lifetime retention follows CONSTRAINTS at the cost of growing local operation storage.

## Consequences and remaining gates

Spec/API/UI share these oracles; [conformance 002](../reviews/contract-conformance-002.md) traces each to ACs, DTOs and implementation owners. No application, migration or generated file changes are made here. T017 must generate and compare schemas; T006/T007/T014 and the source/SRS/quiz cards must implement boundary/failure/replay tests. Windows filesystem/session/browser, real bridge profile/entitlement, semantic content, accessibility and performance evidence remain release gates. Document conformance cannot be reported as runtime success.

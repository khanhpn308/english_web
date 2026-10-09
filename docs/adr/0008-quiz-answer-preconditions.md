# ADR-0008: Quiz answer preconditions and historical receipts

## Status

Accepted under the owner's T047 contract and persistence remediation authorization. This supplements ADR-0004/0005 without replacing their submission, snapshot, privacy or operation decisions.

## Date

10/10/2026 (`Asia/Bangkok`)

## Context

The draft contract requires `If-Match`, but creation and GET previously supplied no per-answer token. The latest-draft table replaces earlier content, so an operation reference alone cannot reproduce a historical Answer after later writes. Exact replay must also work after submission, restart or a lost HTTP response.

## Decision

Every QuizAttempt creation/read includes required `answerPreconditions` in question order. Each entry has question ID, current draft revision and a server-issued opaque strong ETag. Questions without a saved draft use revision 0 and do not acquire an Answer row merely by being read.

The server derives the token from SHA-256 of the compact ASCII-escaped JSON array `["quiz-answer-v1",attemptId,questionId,draftRevision]`, encoded as ASCII UTF-8 without whitespace or a trailing newline. The token is double-quoted `qa-v1-` plus the lowercase hexadecimal digest. The version discriminator permits an explicit future contract revision. Stable IDs and monotonic revisions make tokens resource-specific and stable across process restarts. No stored or rotating secret is required. Clients copy tokens from server responses; tokens confer no authorization.

Missing, duplicate, weak, wildcard, list or malformed validators fail with 422. A well-formed token for the wrong resource/version or stale numeric revision fails with 409. Fresh writes compare token and numeric revision inside the existing SQLite writer transaction. Omitted writing `selfScore` preserves the saved score, explicit null clears it, and strict integer 0–4 sets it; zero remains zero. Canonical intent hashing preserves omitted versus supplied fields.

Migration `0010_quiz_answer_receipts`, following `0009_review_diagnostics`, adds append-only canonical Answer receipts keyed by operation ID and unique per attempt/question/revision. Composite question membership and operation foreign keys protect identity. Database triggers forbid update, delete and conflicting replacement, and require an inserted receipt to match the current draft and a pending answer operation. No past revision is backfilled or invented. `quiz_answers` remains the authoritative latest projection.

T047 reuses T014 claim and transaction-scoped completion. A fresh completion writes the latest draft, historical receipt, aggregate revision and SUCCEEDED operation status together. Success follows durable confirmation. Known same-intent replay reads the original receipt before current revision and terminal checks, after session/input/resource identity checks. It never modifies the latest projection, creates another receipt, increments revisions or reopens submission. A PUT response returns the saved Answer and its ETag; historical replay returns that historical ETag. GET gives the latest revision/token.

Lost HTTP responses are reconciled using the same key/fingerprint or the existing operation/attempt reads. A commit exception is resolved by reading durable operation evidence; inability to read it is a storage error with the operation identity, not proof of failure. No automatic mutation retry or new recovery endpoint is introduced.

## Alternatives considered

- Returning the latest draft on replay would misrepresent the original operation result.
- Embedding answers in the redacted operation reference would violate its bounded opaque contract and privacy boundary.
- Process-local receipts or locks would not preserve restart or cross-connection correctness.
- A rotating secret would invalidate otherwise valid tokens across restarts without adding an authorization guarantee.
- Reconstructing overwritten revisions would invent unavailable learning history.

## Consequences and remaining gates

Receipts grow with acknowledged writes and follow database-lifetime retention and backup rules. Existing drafts remain available, but unavailable historical answers cannot be recovered. Immutable snapshots and concealed objective keys are unchanged; autosave is local and does not submit, score objective questions, update SRS or call the bridge. The Host must run migration, restart, replay, concurrency, rollback and privacy regressions and regenerate OpenAPI/DTO artifacts before integration acceptance.

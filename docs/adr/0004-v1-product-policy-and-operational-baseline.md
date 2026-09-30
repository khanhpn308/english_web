# ADR-0004: v1 product policy and operational baseline

## Status

Accepted for v1 planning. This ADR closes the previously open product/operational questions with conservative defaults selected by the owner-authorized instruction to end the blocked review. It supersedes conflicting provisional OQ wording in `docs/spec.md`, `docs/api-contract.md`, `docs/ui-architecture.md`, `docs/security-review.md` and `docs/observability-plan.md`; it does not erase their historical review evidence.

## Date

29/09/2026 (`Asia/Bangkok`)

## Decision summary

### Cloud/provider and consent policy (`OQ-01`)

- v1 uses Antigravity Tools / Antigravity-Manager v4.8.4 over the ADR-0002 loopback profile.
- Product AI model allowlist is `gemini-3.8-flash-high` for lookup, quiz generation and writing feedback. Claude/other model families are not in v1's product policy even if the proxy advertises them.
- Paid fallback is not prohibited, but **default v1 policy has no automatic fallback**. A future policy version may add a paid fallback only when it names provider, model, route, billing mode, quota/entitlement, retention and region and receives fresh consent. The app never silently creates a billing project or changes route after a quota error.
- Cloud payloads are task-minimized: current term/forms, selected quiz source content or canonical saved writing answer only. No history, SRS, unrelated Markdown, account token/session or proxy admin credential is sent.
- Retention/region statement: the app cannot enforce provider retention or region; v1 discloses that provider defaults apply and that no regional/retention guarantee is made. If the configured policy cannot state the provider's current terms, grant and dispatch fail closed. This is an explicit accepted limitation, not a privacy guarantee.
- The persisted consent/policy/digest/route contracts in ADR-0003 remain mandatory. Quota/auth errors are terminal for the operation; no background retry.

### SRS and assessment (`OQ-02`–`OQ-04`)

- Use a deterministic five-box SRS, deliberately simpler than an adaptive algorithm. Boxes are `0 NEW`, `1`, `2`, `3`, `4`, `5`; base intervals for boxes 1–5 are 1, 3, 7, 14 and 30 local days.
- Flashcard ratings: `AGAIN` moves to box 1; `HARD` keeps or moves one box up (never above 5); `GOOD` moves one box up; `EASY` moves two boxes up. A rating's due date is review time plus the destination box interval. A new card starts at box 0 and is due immediately.
- Quiz mapping: incorrect MCQ/cloze = `AGAIN`; correct MCQ/cloze = `GOOD`; writing self-score 0–1 = `AGAIN`, 2 = `HARD`, 3 = `GOOD`, 4 = `EASY`. For repeated results on one form, the weakest rating wins (`AGAIN < HARD < GOOD < EASY`). SRS updates once at terminal submission; a replay returns the original result.
- Quiz limits: 5–30 total questions, at least one question, at most 20 per type; insufficient source returns a validation error. A quiz stores an immutable question/answer snapshot at creation. Source edits do not mutate an in-progress attempt; deleted forms remain in the snapshot and are marked historical, with no new SRS handoff if the card no longer exists.
- Cloze normalization is Unicode NFC, trim, collapse internal ASCII whitespace and Unicode case-fold; punctuation, spelling and extra content remain strict. Accepted alternatives must be explicit in the snapshot. Writing self-score is user-owned and never overwritten by AI feedback.

### Word identity, Markdown and source consistency (`OQ-05`, `OQ-08`, `OQ-14`)

- Identity key is normalized lemma + part of speech + family identity. Same identity at another note date reuses the card. Meaning/example edits reset that card; IPA/link/verification-only edits do not. Re-adding a form after all sources disappear reuses its historical card but does not restore an active source until a valid file is parsed.
- Use optimistic concurrency, not silent last-write-wins: every source mutation requires the current source revision/ETag. A stale editor gets `409 REVISION_CONFLICT` and must reload; no tie-breaking timestamp is used. This prevents lost updates and supersedes the earlier provisional LWW wording.
- Source/projection writes use a durable SQLite journal with `operationId`, source ID, old/new hash, temp path, intended projection revision and state (`PREPARED`, `SOURCE_REPLACED`, `COMMITTED`, `ABORTED`, `DEGRADED`). Write temp → fsync/atomic replace → short projection transaction → mark committed. Startup reconciliation discards an unused temp, rebuilds projection when the new hash matches, and blocks destructive writes with `DEGRADED` when hashes are ambiguous; it never deletes learning history.
- Preserve legacy `DD-MM-YYYY.md` paths, unknown/context fields and round-trip formatting. Interpret dates in `Asia/Bangkok`; use ISO date in API. Search uses Unicode NFC + case-fold plus an accent-folded Vietnamese projection; no typo-tolerance or semantic-equivalence matching in v1.
- Legacy parser mapping is deterministic: each comma-separated `Từ loại` token creates/merges one POS-specific form; related-form rows create family members only when their lemma and POS are explicit; unknown rows remain opaque context and never create a card. Same normalized lemma+POS+family key merges across files. Invalid filename/date/H1 or ambiguous POS makes the source `INVALID` and read-only. First sync runs dry-run parse/round-trip before enabling writes.

### Audio and content quality (`OQ-06`)

- Audio uses browser `SpeechSynthesis`/system voices, not a third-party audio provider, so no audio cloud consent or remote host is needed. If the browser has no usable voice, the button is disabled with a clear status. No microphone or speech recognition is used.
- Verification is per field. Missing IPA/Cambridge link is stored as `MISSING`/`UNVERIFIED` and does not block saving. AI enrichment is a suggestion; the user confirms a preview before saving. Semantic completeness is evaluated against a fixed 100-form human-reviewed fixture for planning/release, not claimed from JSON shape alone.

### Streak, launcher and runtime (`OQ-07`, `OQ-09`, `OQ-13`)

- Study timezone is `Asia/Bangkok`. A day with due cards is complete only when every eligible due card is completed; invalid/missing sources are excluded from that day's denominator. A day without due cards is complete after one new-card review or a terminal quiz. Streak is consecutive completed local days; dashboard uses calendar days, not UTC timestamps.
- Windows launcher owns a named single-instance mutex `Global\\VocabularyApp-v1`, binds app API to loopback, waits up to 10 seconds for readiness, opens a one-time bootstrap fragment with 60-second TTL, and focuses the existing instance on duplicate launch. Autosave is debounced at 500 ms and flushed on blur/submit; no success label is shown before durable acknowledgement.
- Runtime baseline is React/TypeScript/Vite static assets, Python 3.12+/FastAPI/Pydantic, SQLite/SQLAlchemy/Alembic, with npm and Python lockfiles to be created in the toolchain task. First-run launcher/operator bootstrap uses `%LOCALAPPDATA%\\VocabularyApp\\config.toml`, default data root `%USERPROFILE%\\Documents\\VocabularyApp`, and a current-user protected bridge-key reference under `%LOCALAPPDATA%\\VocabularyApp\\secrets\\bridge-key.dpapi`; it validates paths/profile and shows a native remediation screen before opening the browser. The app never renders or logs the key. No in-app backup/sync is added; the documented recovery input is a user-managed copy of the closed data directory.
- Recovery procedure: stop the app, copy the entire data root and Markdown root to a dated safe location, restore only while stopped, run schema migration/integrity check and journal reconciliation on the copy, then replace the live directory only after checks pass. Keep the original on failure; never delete/rebuild automatically.

### Accessibility, performance and dashboard (`OQ-10`–`OQ-12`)

- Target WCAG 2.2 AA using W3C testable success criteria; preserve Sci-Link's calm, content-first visual language without treating it as a normative dependency. Require keyboard-complete flows, visible focus, 200% zoom without loss, 4.5:1 normal text, 3:1 large text/UI components, focus not obscured, and manual screen-reader smoke checks. This is a target, not a claim until tested.
- Search benchmark: Windows 11, Python 3.12, documented SQLite build, 100,000 forms, 100 fixed Vietnamese queries, cold and warm runs; p95 ≤1 second from request to rendered result. Lookup p95 ≤120 seconds end-to-end; quiz generation ≤60 seconds; feedback ≤30 seconds, all with cancellation and bounded payloads. These are release gates on the named fixture, not universal hardware promises.
- Dashboard formulas: `accuracy = correct / attempted` with null for no attempts; due count excludes invalid/missing sources; streak follows the rule above; 6-days/week success is measured for four consecutive weeks with at least 80% of weeks meeting six completed days. Deletion/source invalidation never erases historical result counts.

## Consequences and remaining gates

This closes the product-policy blockers without adding cloud infrastructure or application code. It intentionally accepts provider retention/region uncertainty, local impersonation risk, user-managed backup and the limits of a simple SRS. Planning still needs a separate `CONSTRAINTS.md` session and implementation verification; those are workflow gates, not unresolved product questions.

## Sources

- [MDN SpeechSynthesis](https://developer.mozilla.org/en-US/docs/Web/API/SpeechSynthesis) and [`speak()`](https://developer.mozilla.org/en-US/docs/Web/API/SpeechSynthesis/speak) support the local browser speech boundary.
- [W3C WCAG 2.2 Recommendation](https://www.w3.org/TR/wcag/) and [WCAG 2.2 conformance reference](https://www.w3.org/WAI/WCAG22/Understanding/refer-to-wcag) support the AA target and testable criteria.

# ADR-0009: SQLite study history and streak reconstruction

## Status

Accepted for T037-R1 coding under the owner-approved policy dated 11/10/2026.
This ADR supplements ADR-0004 and ADR-0005.

## Date

11/10/2026 (`Asia/Bangkok`)

## Context

The H1 ledger stores immutable source, link, card, review, journal, and
coverage facts. Business facts are created by SQLite triggers in the same
writer transaction as their projection. The ledger has no physical commit
timestamp or transaction-group column, but it retains an opening snapshot,
global sequence, stable IDs, operation and review references, and a monotonic
replay timeline.

The dashboard needs an exact daily denominator without turning missing history
into zero. Metrics, eligibility, review events, and terminal quiz evidence
must come from one SQLite snapshot.

## Decision

Use the opening snapshot and ordered committed facts as the historical
authority. Replay source status, form links, card schedules, and resets into
half-open Bangkok-day eligibility windows. A date is `KNOWN` only when the
opening state exists before the date, bounded retrieval is complete, the clock
was not clamped, and no unresolved journal state affects the replay. A zero
card set is a known empty denominator. Missing opening state, pre-opening or
future dates, retrieval limits, clamped clocks, and unresolved journal
evidence remain `UNKNOWN`.

Lifecycle, startup, shutdown, sync polling, and legacy
`NO_CONTINUOUS_SOURCE_OBSERVATION` rows do not alone invalidate committed
SQLite state. Offline Markdown edit time is never inferred; the interval
changes when sync commits the SQLite projection.

`StudyHistoryReader.for_date` accepts a caller-owned SQLAlchemy `Connection`.
With it, the reader performs bounded SELECTs only and does not open, begin, or
commit a transaction. The dashboard captures one aware server cutoff and uses
one explicit read transaction for all metrics and streak evidence.

Each eligible card needs a durable review event inside its applicable window
and after the window's schedule or reset predecessor. A known zero-due day
needs a NEW-card review or a terminal submitted quiz. Drafts, generated
quizzes, feedback, client timestamps, and receipt replay do not count.

Today anchors a streak when complete. A known incomplete today starts counting
from yesterday. An unknown today or historical boundary returns
`currentDays: null`. The endpoint still returns independent metrics with HTTP
200.

## Alternatives considered

- A commit-marker migration was not added. Trigger facts already roll back with
  their writer transaction, while a post-commit marker could not be atomically
  added to the transaction it describes.
- Observed candidate cards are not the denominator because absent evidence
  would become a false zero.
- Unknown streak history does not produce HTTP 503 because the other metrics
  remain locally readable.

## Consequences

Sufficiently evidenced intervals produce exact streaks. Older or ambiguous
intervals stay unknown. T017-generated OpenAPI and TypeScript artifacts remain
Host work. Source, review, SRS, quiz, and migration behavior stays unchanged.

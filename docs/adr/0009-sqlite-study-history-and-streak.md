# ADR-0009: SQLite study history and streak reconstruction

## Status

Accepted for T037-R1 coding under the owner-approved policy dated 11/10/2026.
This ADR supplements ADR-0004 and ADR-0005.

## Date

11/10/2026 (`Asia/Bangkok`)

## Context

H1 facts roll back atomically with their projections. Its opening snapshot,
global sequence, stable IDs, and review references do not identify transaction
groups. Statements can span a day boundary; equal trigger timestamps do not
prove a common commit. Rollback safety alone cannot establish committed
historical projections. Dashboard metrics and history need one read snapshot.

## Decision

Historical authority is recorded, committed SQLite source status, source/form
links, and card schedules. Markdown edits affect history when sync records the
SQLite transition. Unknown earlier filesystem edit times are never inferred.

Add `0013_study_history_commits` after unchanged `0012_study_history`. Preserve
all H1 facts. Record a prospective SQLite state checkpoint, immutable transaction
markers, and metadata-only terminal quiz observations. The checkpoint describes
state at installation; it does not invent old transaction boundaries or activity.
Pre-checkpoint history remains UNKNOWN.

After migrations, install narrow SQLAlchemy engine listeners before lifecycle,
recovery, sync, or study writers run. At BEGIN IMMEDIATE, capture evidence
frontiers. Immediately before root COMMIT, append a marker for surviving new
evidence in that same transaction. Savepoint rollback removes its facts; root
rollback, commit failure, and crash cannot leave a visible successful marker
without the business transaction. Ordinary read transactions never append
markers. Receipt replay creates no study activity.

Recorded effective time is the aware UTC server timestamp sampled by the
pre-commit callback, monotonically bounded by prior marker and H1 timeline
times. It is not exact physical commit time. Replay facts within each marker
in sequence; expose only the group's final source/link/card projection.
Equal timestamps alone never group transactions. The checkpoint uses its
recorded migration observation time under the same convention.

A day is KNOWN only when the prospective checkpoint supplies its opening state,
bounded retrieval covers all applicable committed transitions, and required
group/predecessor/timing evidence is complete. Eligibility requires a stable
card, at least one VALID linked source, and NEW state or a due learned schedule.
Shared references deduplicate by card ID. Known empty is an empty set; missing
evidence is None.

Ungrouped evidence makes the interval since the last marker unknown. A later
instrumented writer records that gap and a new final state without claiming
its intermediate projections. Pre-checkpoint and future dates, missing
predecessors, activity crossing the group's Bangkok date, clock rollback, or
fact/window/activity/work/backward-day limits remain UNKNOWN. Today uses the
recorded prefix through the captured cutoff; its unelapsed remainder is not a gap.

STARTUP, SHUTDOWN, polling, and legacy NO_CONTINUOUS_SOURCE_OBSERVATION rows do
not alone invalidate committed SQLite history. Journal preparation/degradation
alone also does not prove a missing SQLite transition when complete facts exist.

`StudyHistoryReader.for_date` accepts a caller-owned SQLAlchemy Connection.
It performs bounded SELECTs without opening, beginning, or committing another
transaction. Dashboard captures one aware server cutoff and reads metrics,
ledger state, durable reviews, and terminal quizzes in one explicit transaction.

Each applicable obligation needs a durable FLASHCARD review or an APPLIED QUIZ
handoff joined to its REVIEW fact and CARD application predecessor. Schedule,
reset, and reactivation order establish obligations; changing only the valid
reference set does not require another review. Earlier reviews cannot satisfy
later obligations/resets. NEW activity requires historical box=0 immediately
before the applied review, including a transaction leaving no committed due
projection. A proven terminal quiz with stored result and server submitted_at
supplies zero-due activity. Drafts, generated quizzes, AI feedback, client
timestamps, and replay do not count.

Complete today anchors counting today. KNOWN incomplete today anchors yesterday.
UNKNOWN today or a historical boundary before a KNOWN incomplete day yields
currentDays=null. Count exactly until a known incomplete day; limits never
become a lower-bound integer. Streak is independent of the metric range.
asOf remains the cutoff's Bangkok date even with yesterday as the anchor.

Required currentDays is a nullable nonnegative integer. Unknown history alone
returns HTTP 200 with independent metrics and Cache-Control: no-store. Add no
public coverage/reason field. Configuration, storage, input, corrupt-data, and
programming failures retain typed handling.

## Alternatives considered

- H1 timestamps alone expose uncommitted intermediate trigger projections.
- Post-commit markers cannot share the business transaction atomically.
- Observed candidates cannot become a denominator when evidence is missing.
- Unknown streak history does not justify HTTP 503 for usable local metrics.

## Consequences and remaining gates

Exact sufficiently evidenced streaks are available prospectively; older or
ambiguous intervals stay unknown. Source-write, SRS, scoring, and idempotency
behavior are preserved. Host must apply the additive migration, reconcile T017
OpenAPI/TypeScript artifacts, and perform deferred executable verification.
No migration, tests, audit, build, or scan was run in this task.

Framework references: [SQLite isolation](https://www.sqlite.org/isolation.html),
[SQLite triggers](https://www.sqlite.org/lang_createtrigger.html),
[SQLAlchemy transactions](https://docs.sqlalchemy.org/en/21/core/connections.html#using-transactions),
[SQLAlchemy events](https://docs.sqlalchemy.org/en/21/core/events.html), and
[FastAPI response models](https://fastapi.tiangolo.com/tutorial/response-model/).

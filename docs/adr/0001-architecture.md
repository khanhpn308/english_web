# ADR-0001: Local browser UI with FastAPI and SQLite

## Status

Proposed baseline with accepted superseding decisions (`ARCHITECTURE_STATUS: READY_FOR_PLANNING`)

**Partial supersession, 29/09/2026:** [ADR-0002](0002-antigravity-loopback-trust-boundary.md) replaces only this record's bridge process-authentication/per-launch secret/IPC requirement and rejection of plain HTTP on the local bridge hop. [ADR-0004](0004-v1-product-policy-and-operational-baseline.md) supplies the owner-authorized v1 product defaults. The original text below is retained as history; use the superseding ADRs for current boundaries.

## Date

29/09/2026 (`Asia/Bangkok`)

## Context

The product is a single-person vocabulary-learning application on one Windows machine. The product requirements require:

- a browser tab opened from a Windows launcher, with no app account/password and no LAN access;
- local search, Markdown editing/sync, flashcard/SRS, dashboard and already-created quizzes while offline;
- a relational history for forms, note dates, cards, review events, quizzes, answers and validated AI feedback;
- at least a 100,000-word-form search benchmark with a 1-second target under a recorded test setup;
- AI lookup/quiz generation/feedback through a configurable local OpenAI-compatible bridge (`http://127.0.0.1:8045/v1` by default), with cloud inference acknowledged to the user;
- API keys kept out of the frontend, Markdown, database feedback and Git;
- no application code in this design task and no current dependency manifest, lockfile, frontend, backend or test suite.

`docs/spec.md` is now the planning baseline. The former `OQ-01` through `OQ-14` question text is retained for interview history, while [ADR-0004](0004-v1-product-policy-and-operational-baseline.md) is the owner-authorized v1 policy authority. This ADR records the reversible technical baseline; runtime evidence and `CONSTRAINTS.md` remain implementation gates.

### Temporary constraints snapshot

`CONSTRAINTS.md` did not exist when this ADR was written. For this session, the following temporary in-memory constraint set was used:

1. preserve the v1 local/offline/no-account scope;
2. keep AI data minimization and secret isolation mandatory;
3. keep Markdown user-editable and retain history when a source is invalid/deleted;
4. meet the stated 100,000-form search test and ≤1-second target under an agreed fixture;
5. avoid application code and avoid adding unrequested infrastructure;
6. document open questions instead of guessing product policy.

This snapshot is not a project contract. A dedicated session must interview the owner, create `CONSTRAINTS.md`, agree measurable quality/security/accessibility/performance thresholds, and reconcile it with this ADR before implementation begins.

## Decision

Adopt a local modular monolith with the following deployment shape:

```text
Windows launcher
  └─ FastAPI process (127.0.0.1:<app-port>)
       ├─ serves Vite-built React static assets
       ├─ REST/OpenAPI /api/v1 contract
       ├─ SQLite file + normalized Vietnamese meaning/n-gram search projection
       ├─ Markdown source root (allowlisted, user-managed)
       └─ authenticated loopback bridge adapter → 127.0.0.1:8045/v1 → configured cloud provider
```

### Frontend

Use React 19.x with TypeScript and Vite 8.x. Vite builds static assets; the production app does not need a Node server. Use local React state, URL state for filters/pagination, and a small typed `fetch` data layer. Do not add a global business-state library until profiling proves it necessary.

### Backend

Use Python 3.12+ with FastAPI and Pydantic. Organize a modular monolith around `platform`, `markdown-sync`, `vocabulary`, `enrichment`, `review`, `assessment`, `dashboard` and `http`. FastAPI's typed request models are the boundary validation and source of generated OpenAPI/JSON Schema. Use synchronous route functions for blocking SQLite/file work and async functions only where the client is genuinely awaitable, following FastAPI's official guidance.

### Database and source storage

Use SQLite with SQLAlchemy 2.0 and Alembic migrations. SQLite is appropriate for one local user and no service, network or cloud database. Store an explicit Vietnamese meaning projection plus exact/folded normalized text and a versioned n-gram side index; FTS5 may accelerate candidate retrieval but is not the correctness guarantee for arbitrary substring search. Use short transactions, a bounded busy timeout and WAL where the supported SQLite build permits it. SQLite's single-writer behavior is an explicit scale limit, not hidden behind a queue. Verify the exact Windows SQLite build and benchmark fixture before claiming PERF-02.

Markdown remains the user-visible source for vocabulary content. SQLite is the durable source for SRS schedules, review history, quiz snapshots/answers, feedback, sync metadata and search projections that cannot be recreated from Markdown. No “delete database and rebuild” operation is introduced in v1.

### API and session boundary

Use REST at `/api/v1` with one structured error envelope, opaque prefixed IDs, cursor pagination with explicit expiry recovery, allowlisted filtering/sorting, ETags/draft revisions for edits and atomic idempotency/operation records for retriable mutations. The generated FastAPI OpenAPI document is checked against `docs/api-contract.md`.

**Historical wording retained from this proposed baseline; superseded for the bridge by [ADR-0002](0002-antigravity-loopback-trust-boundary.md). Implementers MUST use ADR-0002 and not the bridge sentence below.**

There is no product login. The launcher binds the server to loopback and opens a fragment token that the bootstrap page exchanges once by POST, then clears from browser history before setting a short-lived `HttpOnly; SameSite=Strict` local session cookie. The bridge is loopback/process authenticated and rejects remote/plain HTTP by default. These technical guards are not an account or password; local malicious processes remain a documented residual risk.

### Observability and security

Emit structured JSON logs with request/trace IDs, bounded metrics and OpenTelemetry-compatible spans. Redact secrets, prompts, answers, raw Markdown, full vocabulary text and provider bodies. Validate all external input and all bridge/LLM output before rendering or persistence. Outbound provider payloads contain only fields needed for the current task.

## Official documentation checked

- [React versions and releases](https://react.dev/versions), [React versioning policy](https://react.dev/community/versioning-policy)
- [Vite getting started](https://vite.dev/guide/), [production build and browser targets](https://vite.dev/guide/build)
- [FastAPI request bodies/Pydantic validation](https://fastapi.tiangolo.com/tutorial/body/), [OpenAPI metadata](https://fastapi.tiangolo.com/tutorial/metadata/), [async/sync guidance](https://fastapi.tiangolo.com/async/), [strict JSON content type](https://fastapi.tiangolo.com/advanced/strict-content-type/)
- [Python 3.12 virtual environments](https://docs.python.org/3.12/tutorial/venv.html)
- [SQLAlchemy SQLite dialect](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html), [session transactions](https://docs.sqlalchemy.org/en/20/orm/session_basics.html)
- [Alembic migration environment/tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [SQLite FTS5](https://sqlite.org/fts5.html), [SQLite limits](https://www.sqlite.org/limits.html), [SQLite use/concurrency](https://www.sqlite.org/whentouse.html)
- [OpenTelemetry signals](https://opentelemetry.io/docs/concepts/signals/), [logs](https://opentelemetry.io/docs/concepts/signals/logs/) and [metrics](https://opentelemetry.io/docs/concepts/signals/metrics/)

The documentation confirms current API patterns and relevant limits as of this design date. ADR-0004 supplies the v1 provider/model/route/fallback and disclosure defaults; provider entitlement/quota and provider-controlled retention/region still require implementation/profile evidence and must fail closed when unavailable.

## Alternatives considered

### Electron or Tauri desktop shell

- **Pros:** installer/window lifecycle and tighter OS integration.
- **Cons:** an additional desktop runtime, packaging and security surface; product explicitly wants a browser tab rather than a desktop window.
- **Decision:** reject for v1. A Windows launcher that starts the backend and opens the browser is smaller and reversible.

### Node full-stack (Next.js/NestJS) or a Python template engine

- **Pros:** one language or server-rendered UI.
- **Cons:** does not reduce the required bridge/file/SQLite boundaries; SSR is unnecessary for a private local app; Python aligns with the existing spec direction and file/AI tooling.
- **Decision:** reject. React/Vite static assets plus FastAPI preserves a clear browser/API contract and keeps runtime Node out of the installed app.

### PostgreSQL or another server database

- **Pros:** concurrent writers and a familiar remote scale path.
- **Cons:** service installation, credentials, backup/upgrade burden and cost for one local user; violates the simplest local-first shape.
- **Decision:** reject for v1. Revisit only if multi-user/LAN/cloud sync enters scope; that would require a new ADR and migration plan.

### IndexedDB-only browser storage

- **Pros:** no backend database and easy offline reads.
- **Cons:** poor fit for Markdown file synchronization, durable quiz/history transactions, FTS5-scale search and external bridge credential isolation.
- **Decision:** reject as canonical storage. Browser cache may be added as a read optimization only after correctness is proven.

### GraphQL or unversioned RPC

- **Pros:** flexible client queries or fewer route files.
- **Cons:** more tooling and less obvious caching/error semantics for a single local client; no need for public schema federation.
- **Decision:** reject. Versioned REST + generated OpenAPI is sufficient and inspectable.

### Local-only inference

- **Pros:** no cloud data transfer or provider quota.
- **Cons:** not the product decision; current smoke test and spec require local bridge → cloud inference.
- **Decision:** reject as an unapproved change. Keep the bridge adapter/provider policy configurable and make cloud disclosure explicit.

## Consequences

### Positive

- Zero database service and no production network deployment for v1.
- One same-origin API reduces CORS and deployment complexity.
- SQLite transactions preserve history independently of Markdown source validity.
- A normalized Vietnamese meaning/n-gram projection gives a testable path to the 100,000-form benchmark without a search service; FTS5 remains optional rather than a hidden correctness dependency.
- OpenAPI, generated frontend DTOs, ETags and idempotency make the single client contract testable.
- A provider adapter isolates the cloud bridge and keeps the secret out of the UI.
- The architecture can later replace SQLite/launcher without changing the product-facing module boundaries, but that migration is not assumed free.

### Costs and risks

- SQLite serializes writers and is not a multi-user/LAN database; heavy sync/quiz writes must stay short and observable.
- Two language toolchains exist at development time (Node for build/test, Python for runtime); both need pinned lockfiles and audits.
- The loopback session is not a replacement for OS security or encryption at rest.
- Provider entitlement/quota evidence, provider-controlled retention/region, bridge profile verification and feedback-quality fixtures remain external/runtime release gates; v1 defaults are recorded in ADR-0004.
- Markdown conflict tie-breaking, SRS/rubric formulas, quiz limits, accessibility acceptance and dashboard definitions block final contract freeze.
- Browser-tab launcher/Windows crash recovery need a small platform-specific implementation and test matrix.

## Implementation sequence (contract-first, incremental)

1. **Slice 0 — constraints and contracts:** create `CONSTRAINTS.md`, pin the ADR-0004 baseline, generate API DTOs/OpenAPI shape, verify bridge/session policy and source-root policy.
2. **Slice 1 — local runtime/storage:** single-instance launcher/bootstrap, FastAPI static serving, SQLite/Alembic, Markdown parser/sync, startup readiness, integrity and safe-path tests.
3. **Slice 2 — lookup/save/search:** authenticated bridge adapter with fake provider, schema validation, word-form persistence, normalized Vietnamese/n-gram search, save idempotency and UI lookup/search flows.
4. **Slice 3 — review:** card/read models, ADR-0004 five-box SRS, review events, due/date queue and offline UI.
5. **Slice 4 — quiz:** ADR-0004 state/snapshot/limits/rubric, revisioned autosave/restore, deterministic scoring, feedback validation and idempotent SRS handoff.
6. **Slice 5 — dashboard/operations:** ADR-0004 formulas, status screen, metrics/logs/traces, benchmark fixture and Windows journey tests.

Each slice must have contract tests, a build/type check, security tests for its new boundary and telemetry verification before the next slice. No application code is part of this ADR task.

## Review gates

ADR-0004 supplies the explicit v1 decisions that were previously required before implementation planning. Before implementation begins, create `CONSTRAINTS.md` in a dedicated session, pin exact runtime/lockfile versions, and produce generated-contract, bridge-profile, source-recovery, SRS/quiz, benchmark, accessibility and telemetry/security evidence. If those checks require a different architecture, create a new superseding ADR rather than silently rewriting this record.

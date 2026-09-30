# Project Constraints

Last reviewed: 29/09/2026 (`Asia/Bangkok`)
Owner: product owner + implementation reviewers
Authority: [`docs/spec.md`](docs/spec.md), [`docs/adr/0004-v1-product-policy-and-operational-baseline.md`](docs/adr/0004-v1-product-policy-and-operational-baseline.md)

This file is the implementation quality bar. An agent MUST read it before writing application code. A failing constraint is a stop condition; it must not be made green by weakening a threshold, skipping a test, adding a suppression, or hiding an error. The repository currently has no application runtime, so commands marked “after toolchain” are planning contracts to be wired by the bootstrap tasks.

## Scope and non-negotiables

- v1 is a one-user Windows local-first application: React/TypeScript/Vite browser UI, Python 3.12+/FastAPI/Pydantic backend, SQLite/SQLAlchemy/Alembic.
- Antigravity Tools/Antigravity-Manager v4.8.4 is reached only through `127.0.0.1:8045`; LAN access is disabled and the backend alone handles the proxy client key.
- The v1 AI policy selects `gemini-3.8-flash-high` with no automatic fallback. Paid fallback is not prohibited, but a future route requires a new explicit policy version and fresh consent.
- Local study must remain usable when external network/bridge access is unavailable. Local browser `SpeechSynthesis` must never become a network dependency.
- Markdown remains user-editable. Source edits use revision/ETag conflict handling; silent last-write-wins is forbidden.
- Credentials, proxy keys, Google tokens/sessions and bootstrap/session tokens never belong in browser bundles, vocabulary Markdown, SQLite learning/feedback records, Git or telemetry. Bootstrap/session tokens are handled only in their intended exchange/cookie mechanisms.
- Logs/traces/metrics never contain prompts, answers, raw Markdown, full provider bodies or full learning content. Vocabulary Markdown, SQLite quiz/answer/validated-feedback records and the UI may contain the learning data explicitly required by the spec; source/test fixtures use synthetic or reviewed public examples. This distinguishes canonical learning storage from diagnostic data without changing the secret or telemetry protections.
- No application code is part of this planning session.

## Floor — always enforced

- No new `@ts-ignore`, `@ts-nocheck`, `eslint-disable`, `# type: ignore`, `# noqa`, `nosemgrep`, `gitleaks:allow` or equivalent suppression without a time-bounded exception below.
- No unimplemented stubs such as `TODO` in place of required behavior, `throw new Error("Not implemented")`, empty catches, silent fallbacks, or fake success responses.
- No skipped, deleted or weakened tests without a documented reason, owner and expiry in the same commit.
- No secrets or realistic credentials in source, fixtures, screenshots, tests, logs, task files or commit messages.
- No destructive migration, database rebuild, source deletion or data-loss behavior without an explicit recovery test and approved task scope.
- `CONSTRAINTS.md` itself cannot be weakened to make a change pass. Tightening it is allowed; loosening requires owner review and a new rationale.

## Enforced quality dimensions

| Dimension | Rule | Checked by | Runs at |
|---|---|---|---|
| Type safety | Zero TypeScript errors and zero Python type-check errors | `npm run typecheck`; `python -m mypy backend` | TS: T002; Python: T058; every code task afterwards |
| Lint/format | Zero configured ESLint/Ruff errors; formatter check passes | `npm run lint`; `python -m ruff check .`; `npm run format:check` | T002/T058/T053; fast task verification and CI |
| Tests | Focused tests pass; no unverified task may be marked done | `npm run test:frontend`; `python -m pytest`; contract/e2e commands per task | Every task |
| Changed-code coverage | At least 80% line coverage for changed application code; generated/vendor files excluded | Vitest/pytest coverage from the same test run, then `npm run coverage:check` intersects reports with diff | T053; task end and CI |
| Coverage ratchet | Once a baseline exists, total coverage may not fall by more than 0.5 percentage points | Coverage report compared with recorded baseline | CI |
| Secrets | Zero detected secrets; reports must be redacted | `npm run security:secrets` wraps pinned Gitleaks with redaction; scan working/untracked files and staged diff as well as history when HEAD exists | T063; fast task verification and CI |
| Code security | Zero high/critical findings in changed code | `npm run security:code` wraps pinned Semgrep rules/reports and enforces the severity policy | T063; CI/review tasks |
| Dependency security | Zero high/critical known dependency findings | `npm run security:deps` wraps pinned OSV scanner and enforces severity from its report; missing/unknown severity requires triage | T063; CI and dependency changes |
| API contract | Generated OpenAPI/JSON Schema matches `docs/api-contract.md` and all error envelopes are typed | `npm run export:contract`; `npm run test:contract` | T017; API tasks and CI |
| Architecture boundaries | UI cannot import backend/database/secret modules; domain modules cannot import HTTP/UI adapters | `npm run architecture:check` invokes dependency-cruiser and Python import-linter | T062; every boundary task, CI |
| Accessibility | WCAG 2.2 AA target; zero critical/serious automated violations and manual keyboard evidence for changed flows | `npm run test:a11y` with axe in the Playwright loopback preview; manual matrix | T052 harness/T043 full matrix; UI task end and CI preview |
| Frontend performance | LCP ≤ 2.5 s and CLS ≤ 0.1 on the named local preview fixture; no regression without an exception | `npm run benchmark:ui` uses Lighthouse and the T052 preview; fixture/hardware recorded | T064 command/T043 evidence; UI task end and CI preview |
| Search performance | p95 ≤ 1 s rendered result at 100,000 forms on the named Windows 11/Python 3.12/SQLite fixture; the exact AC-07 query also stays ≤ 1,000 ms | `npm run benchmark:search`; benchmark harness and `docs/runbooks/search-performance.md` | T042 fixture/T065 timing; search task and release gate |
| AI operation budgets | Lookup p95/hard deadline ≤ 120 s; quiz generation ≤ 60 s; feedback ≤ 30 s; all cancellable and no background retry | Timeout/load contract tests | AI tasks and release gate |
| Storage safety | Stale source revision returns `409 REVISION_CONFLICT`; journal recovery never deletes learning history | Failure-injection and Windows filesystem tests | Sync/storage tasks and release gate |
| Local security boundary | Loopback-only app, strict origin/session checks, backend-only bridge key, no LAN exposure | BR-AUTH-01–09, hostile-browser tests, secret scans | Security tasks and CI |
| Observability privacy | Local structured logs/traces contain correlation metadata only; forbidden content list stays absent | Sentinel log/trace tests | Observability task and CI |

## Lifecycle and time budgets

### v1 configuration defaults to freeze in T013

- Request JSON limit: 1 MiB; source Markdown file: 8 MiB; bridge response: 4 MiB. A content string is at most 4,096 Unicode code points and a general collection at most 100 elements; stricter term, quiz, pagination and enum bounds from the API contract take precedence. The bridge adapter also validates the actual configured model/provider limits when available. Oversized content is rejected visibly, never silently truncated.
- Bootstrap token remains one-time with 60-second TTL. Browser session expires on backend restart/shutdown or 8 hours after issue, whichever occurs first; rebootstrap preserves durable drafts and does not add product login.
- Durable idempotency intents, receipts and minimal key fingerprints are retained for the lifetime of the local database in v1; no automatic cleanup may turn a used key into a new billable intent. Consent events and referenced immutable policy digests remain with their related results/history. User-managed backup includes these records. A future purge/export feature needs a separate contract decision.
- Logs/metrics keep the observability plan's five 10 MiB rotating files and 14-day retention. Diagnostic retention is separate from canonical learning and operation storage.

These are bounded local defaults selected under the owner's existing decision authority, not claims about cloud entitlement or installed provider terms. T013 must reflect them consistently in API/capabilities/examples before the dependent task implements them. Boundary/max+1 tests in T006/T007/T014/T015 and T041 verify these defaults.

Tool readiness: all command names are planned until their owner task installs/pins tools and proves negative and positive outcomes. This planning session establishes the written tier of enforcement only. No application coverage, LCP, CLS or search timings have been measured yet. Missing executable, report, vulnerability database or runtime is `SETUP_PENDING`/`PENDING` and must not count as a passing check.

| Baseline metric | Today | Ratchet/authority |
|---|---|---|
| Total frontend/backend coverage | Unmeasured; no application source | First real reports recorded by T053; retain the 0.5-point tolerance above |
| Main bundle size | Unmeasured; no frontend build | Record after T004/T064; investigate growth, no invented byte ceiling |
| Application LCP/CLS/search p95 | Unmeasured | Thresholds above remain mandatory when runtime evidence exists |

Rationale: zero-error type/lint and the floor protect every slice; 80% changed-code coverage is the skill default for a new repository; the 0.5-point ratchet tolerance absorbs measurement drift. Dependency/code high-severity gates and external axe/Lighthouse checks provide evidence beyond the project's own tests. Existing spec/ADR performance, accessibility and operation deadlines retain their approved numbers. All thresholds block the relevant task/release gate once its tool exists; the floor applies immediately.

- Fast checks should complete in **10 seconds** on a warm developer machine; they cover lint, typecheck, floor guard and secret scan for changed files.
- Task verification should complete in **90 seconds** when it does not require a Windows/browser/benchmark environment. Longer external checks move to CI or an explicit verification task.
- Browser accessibility, Windows launcher, real bridge profile and 100k-form performance checks are release evidence, not reasons to fake local green output.
- Every task must leave a runnable, testable checkpoint or explicitly document why it is a non-runtime toolchain checkpoint.

## Exceptions

No exceptions are approved at planning time.

Any future exception must record: ID, exact rule, path, reason, owner, compensating check, and expiry no more than 90 days away. An exception cannot cover secrets, consent bypass, data loss, silent conflict resolution or disabled security tests.

## Change-control rules

- A task may add a dependency only after recording why the standard-library/existing-tool option is insufficient, its version, license/supply-chain check and bundle/runtime impact.
- A database or public API change requires updating the contract/ADR and its contract tests in the same task.
- A threshold change requires a separate documentation change, owner review and a new baseline; it cannot be bundled as a “fix” for a failing implementation.
- Each task ends with an atomic commit proposal using `<type>: <why>` and records files intentionally untouched.

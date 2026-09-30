# T066: Trusted browser bootstrap page

**Task ID:** `T066`  
**Title:** Trusted browser bootstrap page  
**Status:** `DONE`  
**Goal:** Exchange the one-time launcher fragment into the local session before loading the main UI, clearing the token from the address bar immediately.  
**Suggested model:** GPT-6 Astra  
**Estimated scope:** One focused session, four handwritten files.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md), [AGENTS.md](../AGENTS.md).
- [API contract](../docs/api-contract.md): bootstrap page/exchange and session boundary.
- [UI architecture](../docs/ui-architecture.md): J1 and session recovery.
- [Security review](../docs/security-review.md): T-01, T-02, T-18.

## Dependencies

- [T004](t004-frontend-shell-routes.md).
- [T006](t006-api-core-contract-foundation.md).

## Files được phép sửa

- `frontend/bootstrap.html`.
- `frontend/src/bootstrap.ts`.
- `frontend/src/bootstrap.test.ts`.
- `vite.config.ts`.

Common bookkeeping: this task card, tasks/todo.md, docs/changelogs.md; generated frontend build stays ignored. T052 adds browser integration evidence after this page exists.

## Files không được sửa

- Proxy keys/configuration, domain modules, user Markdown, local databases, other UI features.
- Session policy or thresholds outside T013-approved contract; no general login screen or browser secret-entry form.

## Implementation notes

- Vite builds a separate trusted bootstrap entry. It contains only token exchange/recovery UI and loads no application module, analytics or external script before exchange completes.
- Read the fragment into a short-lived local variable, call history.replaceState immediately, POST the token to same-origin bootstrap/exchange once, then navigate to the approved local app route only after the cookie response succeeds.
- Missing/expired/reused token produces visible native/launcher recovery guidance. Do not log the token, persist it in browser storage, place it in query parameters or send it to a remote origin.
- T006 serves this built asset; if static routing is incomplete, record the exact T006 integration adjustment before changing its source scope. Browser tests of the integrated page belong to T052/T057.

## Acceptance criteria

- [ ] A token fixture is removed from URL before any module/navigation/referrer can expose it; only the intended same-origin POST contains it.
- [ ] Successful 204 exchange loads the main UI; missing/expired token and failed exchange show explicit recovery without pretending the app is ready.
- [ ] The main UI never receives the bootstrap token; no localStorage/sessionStorage/log or external request contains it.

## Test cases

1. Mock history/fetch/module loader: assert clear-URL precedes exchange and main-app load; exactly one exchange.
2. Token missing/expired/replayed, origin mismatch, abort/unknown response and network failure.
3. Build two entries and inspect bootstrap HTML for only self-hosted scripts; no app import before exchange.

## Verification commands

```text
npm run test:frontend -- frontend/src/bootstrap.test.ts
npm run typecheck
npm run build
```

## Expected output

- Focused tests pass; build includes bootstrap.html and separate bootstrap script.
- Evidence records token-sentinel absence in bundle/source diagnostics. T052/T057 supply real browser/referrer/session integration proof.
- Handoff includes outputs, files intentionally untouched, residual evidence and next task.

## Risk

- **Level:** `High`.
- Token leakage or app load before exchange can undermine the local session boundary.
- Mitigation: ordering tests, separate entry, no remote script, short-lived token and required browser integration checks.

## Stop conditions

- A fix needs unsafe-inline/external scripts, token logging/browser storage or weakening the session guard.
- Contract ambiguity outside T013-approved behavior; build/runtime required tool missing is pending evidence, never PASS.

## Commit message đề xuất

`feat(T066): exchange the launch token before loading the app`

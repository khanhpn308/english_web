# ADR-0002: Antigravity v4.8.4 loopback API key and trusted Windows host

## Status

Accepted for the bridge transport/authentication boundary only. Owner answered “chấp nhận” after the proposal to use HTTP loopback, mandatory inference API key and a trusted Windows host without a guarantee against a malicious local process impersonating the proxy.

Supersedes only the bridge process-authentication/per-launch secret/IPC requirement and blanket rejection of plain HTTP in [ADR-0001](0001-architecture.md). The app's browser bootstrap/session is unchanged. Overall architecture and planning remain blocked by the other review findings; this is not release/security sign-off.

## Date

29/09/2026 (`Asia/Bangkok`)

## Context

The owner uses Antigravity Tools / Antigravity-Manager **v4.8.4** as an existing local API proxy. Its release tag resolves to commit `0269f045f4e35f34b9ee3b3bcd6c0ff1e741378f`. That identifies the upstream source to review, not proof of the installed binary or its configuration. The vocabulary app must not manage Google account tokens/sessions or introduce product login, LAN sharing, a paid provider or additional infrastructure.

The prior design required process authentication without a compatible mechanism and simultaneously allowed an HTTP loopback base URL while rejecting plain HTTP. The approved choice resolves that contradiction by explicitly accepting the local-machine impersonation risk, not by claiming that an API key authenticates a server.

## Decision

1. Use the existing OpenAI-compatible HTTP interface at `http://127.0.0.1:8045/v1`. This exact origin is the v1 allowlist. The backend never takes a bridge URL/key from browser input, follows redirects, uses an ambient HTTP proxy for this connection, or falls back to another host/port. HTTP is allowed on this specific local hop only; it does not authorize plain HTTP to an external provider.
2. The operator configures `allow_lan_access=false` and `auth_mode=all_except_health` in Antigravity. `auto`/`off` are not an approved profile: v4.8.4 resolves local-only `auto` to `off`. Require a valid proxy key on `/v1/models` and `/v1/chat/completions`. Health availability alone is not authentication evidence; do not claim every proxy route requires authentication.
3. A newly rotated proxy client key is provisioned only to the vocabulary backend's current-user protected local secret configuration. The app does not read Antigravity account stores or its whole configuration. Set a separate nonempty Antigravity administration password; do not provision it to the app. The detailed secret-store packaging remains OQ-13, without weakening backend-only storage, restrictive ACLs or redaction. There is no per-launch bridge key requirement and no automatic key rotation by the app.
4. The backend adapter may call only `GET /health`, `GET /v1/models` and `POST /v1/chat/completions` for this integration. It sends its key only to the allowlisted authenticated routes, never to `/health`, management/internal routes, URLs in responses, logs or the frontend. No Google token/session is requested, stored or sent by the vocabulary app.
5. Before each AI dispatch, require the operator-approved profile and run the auth check in API §6: a no-key models request must be rejected, then a keyed models request must succeed. Failure prevents the inference call; local search/review/created quizzes remain usable. This catches ordinary misconfiguration, not a malicious listener or a race after the check. Numeric time/size budgets remain OQ-11 and must cover preflight within the existing operation deadline, not restart the timer.
6. Keep request/trace correlation inside the app; remove diagnostic propagation headers before the request enters the third-party proxy. Keep mandatory content/schema validation, browser session/CSRF controls, key redaction and no-background-retry semantics. Proxy-generated logs/metadata and upstream routing remain a separate OQ-01 privacy/cost gate.

## Official documentation checked

- [v4.8.4 release](https://github.com/lbjlaq/Antigravity-Manager/releases/tag/v4.8.4) and [tag ref](https://api.github.com/repos/lbjlaq/Antigravity-Manager/git/ref/tags/v4.8.4).
- [Proxy configuration](https://github.com/lbjlaq/Antigravity-Manager/blob/0269f045f4e35f34b9ee3b3bcd6c0ff1e741378f/src-tauri/src/proxy/config.rs): bind and auth settings.
- [Effective auth mode](https://github.com/lbjlaq/Antigravity-Manager/blob/0269f045f4e35f34b9ee3b3bcd6c0ff1e741378f/src-tauri/src/proxy/security.rs): local-only auto disables mandatory authentication.
- [Authentication middleware](https://github.com/lbjlaq/Antigravity-Manager/blob/0269f045f4e35f34b9ee3b3bcd6c0ff1e741378f/src-tauri/src/proxy/middleware/auth.rs): client key checks, health/internal/preflight exceptions and separate administration credential.
- [Routes](https://github.com/lbjlaq/Antigravity-Manager/blob/0269f045f4e35f34b9ee3b3bcd6c0ff1e741378f/src-tauri/src/proxy/server.rs) and [models handler](https://github.com/lbjlaq/Antigravity-Manager/blob/0269f045f4e35f34b9ee3b3bcd6c0ff1e741378f/src-tauri/src/proxy/handlers/openai.rs): integration endpoints. A models response is not proof of quota, actual model execution or billing.

## Alternatives considered

- **HTTP loopback + key, trusted Windows host — accepted:** compatible with the existing proxy, no additional service/certificates. Cannot prove the listener's identity or secure a compromised host.
- **Authenticated IPC or verified TLS boundary — not selected for v1:** could provide a stronger boundary if designed end-to-end, but compatibility and credential/certificate lifecycle have not been established. A sidecar alone would not protect an unauthenticated last hop.
- **Loopback with `auto`/`off` — rejected:** does not enforce the required client key.

## Consequences

- A malicious process on the machine can impersonate the proxy and receive the proxy key and task payload; this residual risk is **explicitly accepted**, not tested away. Its impact is not downgraded. OS trust and protected configuration are prerequisites, not proof of server identity.
- This acceptance does not authorize sending new data categories to cloud, broader model access, proxy administration, LAN exposure, or weakening file/browser security. Paid fallback is not prohibited by this ADR, but it requires an explicit READY cloud policy, disclosure/consent and dispatch rule. ADR-0004 supplies the v1 default and keeps runtime verification gates.
- Suspected host/proxy compromise means stop AI requests, investigate the host and rotate the key before re-enabling; do not retry against the suspicious listener. Upgrading Antigravity requires rechecking its auth/routing behavior against this profile.
- No application code, live proxy configuration or credential is changed by this ADR. `CONSTRAINTS.md` remains for its separately requested session.

## Verification gates

The normative design cases are `AC-36` and `BR-AUTH-01` through `BR-AUTH-09` in the spec/API. Use synthetic credentials and a fake upstream for automated tests; verify the installed proxy profile separately before release without sending study content or collecting real secrets. Cover no-key/wrong-key rejection, successful keyed inference, `auto` misconfiguration, allowed-origin/redirect/proxy-env restrictions, LAN isolation, admin separation, route/model policy enforcement, secret/trace redaction and ordinary dependency failures. Document rather than promise rejection of a fully mimicking malicious local listener.

Passing these implementation tests is required before release; their absence in a documentation-only repository is not itself an unresolved architecture decision. Final readiness still requires the full doubt-driven review after remaining findings are handled.

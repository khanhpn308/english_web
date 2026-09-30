# Runbook: Local bridge failure

**Means:** Lookup, new quiz generation or AI feedback cannot use the approved Antigravity v4.8.4 client-key-authenticated bridge. Local search/review/created quizzes remain available while the API/storage is healthy. Audio is local browser SpeechSynthesis and is independent of this bridge.

**First check:** Inspect `/api/v1/status` for reachability, configured model policy and redacted error category. `502 BRIDGE_AUTH_ERROR` is not a browser-session failure; `503 CONFIGURATION_REQUIRED` can indicate a missing/unsafe bridge profile. Health success alone does not prove auth, quota or process identity. Never print/copy a key, Google token/session, admin password, whole config or raw proxy log.

**Recovery:** Follow [ADR-0002](../adr/0002-antigravity-loopback-trust-boundary.md) and API §6. In Antigravity's own local settings confirm v4.8.4, LAN disabled, `all_except_health`, and a separate admin password. Provision only the rotated client key to protected backend configuration; never switch auth off or enable LAN to get a request through. The adapter checks no-key models rejection and keyed models success without inference; do not use user study content for diagnosis. Do not claim these checks authenticate the listener.

**Retry safety:** Reconcile the existing operation via its status endpoint before retrying. A successful operation returns its saved result; `PENDING`/`UNKNOWN` must not trigger a second inference. Once the cause is corrected and a failed operation is terminal, the user may explicitly create a new intent/key; do not replay a terminal failure as fresh work or queue background retries. Suspected host/proxy impersonation overrides retry: stop AI calls, investigate the host, then rotate the key before re-enabling. Local malicious-process resistance is an accepted residual risk, not a promised IPC/process-owner control.

**Escalate:** Preserve request ID, provider/model category and prompt version only; do not collect prompts, answers or provider bodies.

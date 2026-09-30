# Runbook: Local API error rate

**Means:** The local backend is reachable but user-facing requests are failing at an unusual rate.

**First check:** Group structured logs by route template, status class and request ID; inspect storage, configuration and bridge categories without logging bodies.

**Recovery:** Reproduce with a deterministic fixture, restart only after preserving the database, and roll back the last local change if the error began after an update.

**Escalate:** Attach redacted event names, request IDs and schema revision; never attach prompts, answers, keys or raw Markdown.

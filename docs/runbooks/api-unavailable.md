# Runbook: Local API unavailable

**Means:** The Windows launcher cannot reach the loopback FastAPI process; local study data is not necessarily damaged.

**First check:** Use the launcher/native status surface to verify the owning process and port; do not ask the browser `/status` route to diagnose a stopped process.

**Recovery:** Start or focus the single instance, then verify `/api/v1/health` and readiness before opening Dashboard. Do not start a second process against the same database.

**Escalate:** Preserve the launcher log and request ID, then stop writes if the process repeatedly crashes; follow the storage-integrity runbook.

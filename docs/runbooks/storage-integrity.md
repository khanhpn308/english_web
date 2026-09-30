# Runbook: Storage integrity failure

**Means:** SQLite integrity or migration checks failed; writes may damage durable study history.

**First check:** Stop destructive writes and record the schema revision, integrity category and request ID. Do not delete or rebuild the database automatically.

**Recovery:** Follow [`first-run-and-restore.md`](first-run-and-restore.md): stop the app, preserve the original, restore to a staging copy, run migrations/integrity/journal checks, and reopen only after the staging copy passes. Never delete/rebuild automatically.

**Escalate:** Keep the original database and Markdown sources unchanged for diagnosis; document any data loss explicitly.

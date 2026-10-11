# Runbook: Storage integrity failure

**Means:** SQLite integrity or migration checks failed; writes may damage durable study history.

**First check:** Stop destructive writes and record the schema revision, integrity category and request ID. Do not delete or rebuild the database automatically.

**Recovery:** Follow [`first-run-and-restore.md`](first-run-and-restore.md): stop the app, preserve the original, restore to a staging copy, run migrations/integrity/journal checks, and reopen only after the staging copy passes. Never delete/rebuild automatically.

**Escalate:** Keep the original database and Markdown sources unchanged for diagnosis; document any data loss explicitly.

## SQLite writer contention

**Means:** More than 1% of timestamped SQLite transactions encountered
SQLITE_BUSY/SQLITE_LOCKED in the last five minutes. This is contention evidence,
not proof of corruption. No transactions or incomplete retention cannot establish
a healthy contention rate.

1. Preserve the current draft. Do not delete the database, WAL/SHM files, learning
   history or source files, and do not rebuild from Markdown.
2. Use the launcher to focus the single owning instance. Stop a duplicate app or
   competing database editor safely; allow the current sync/write to finish.
   Keep transactions short. Do not disable locking or increase busy timeout
   beyond the configured maximum of 5 seconds.
3. Reconcile a mutation with its existing operation ID/idempotency key first.
   A lost response is not evidence that the write failed. PENDING/UNKNOWN must
   not create another intent or AI request. For a retriable intent, retry only
   with bounded backoff, preserving the same intent; honor the existing recovery
   response and budget. A terminal failure needs explicit reconciliation and
   user action before a new intent. Never queue automatic inference retries.
4. Inspect Status after successful transactions and after the five-minute window
   clears. INCOMPLETE does not confirm recovery. If contention persists, preserve
   redacted request IDs and the schema revision for diagnosis.
5. If an integrity failure also appears, stop destructive writes and use the
   integrity procedure above. Stop the app, preserve the original, restore a
   backup to a separate staging copy, run migration/integrity/journal checks,
   and reopen only after those checks succeed. The local runbook viewer includes
   `first-run-and-restore` for the full procedure.

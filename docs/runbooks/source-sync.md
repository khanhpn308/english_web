# Runbook: Markdown source sync failure

**Means:** A Markdown file is invalid, missing, or changed during sync; the affected source is excluded from active study while valid sources and history remain available.

**First check:** Inspect the source ID, relative path, parser error category and source revision. Never follow a client-supplied path or repair a malformed file implicitly.

**Recovery:** Correct the file externally or use an explicitly approved repair/relink flow. Reconcile the existing operation first; if a new sync is required, create a new intent/idempotency key rather than replaying a terminal operation, then verify the source revision and search projection.

**Escalate:** Preserve the original file and parser fixture; do not overwrite a source whose status is `INVALID` or `MISSING`.

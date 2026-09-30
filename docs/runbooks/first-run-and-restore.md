# Runbook: First-run bootstrap and restore

## First run

1. The Windows launcher creates the current-user directory `%LOCALAPPDATA%\VocabularyApp`, a default data root `%USERPROFILE%\Documents\VocabularyApp`, and a protected bridge-key reference at `%LOCALAPPDATA%\VocabularyApp\secrets\bridge-key.dpapi`.
2. The operator selects or confirms the Markdown root and enters the rotated Antigravity client key only in the native launcher/operator surface. The key is written through the Windows current-user protected store; it is never put in the browser URL, Markdown, SQLite content, logs or Git.
3. The launcher validates the root is readable/writable, performs a dry-run Markdown parse/round-trip, validates Antigravity v4.8.4 loopback/auth profile without sending study content, and runs SQLite migration/integrity checks.
4. If any check fails, show a remediation screen and keep the browser app closed. `CONFIGURATION_REQUIRED` is not a reason to invent an environment variable, enable LAN, disable auth or proceed with an unverified source root.

## Restore and migration

1. Stop the app and preserve the original data root and Markdown root unchanged.
2. Copy the user-managed backup into a new staging directory; never restore over the only original copy.
3. Run migrations, `PRAGMA integrity_check`, Markdown dry-run parsing and journal reconciliation on the staging copy. Ambiguous source/projection hashes remain `DEGRADED` and block destructive writes.
4. After checks pass, make the staging directory the configured data root and restart through the launcher. Keep the original until the user verifies vocabulary, SRS, quiz and feedback history.
5. On failure, return to the original root and retain the staging diagnostics. The app never deletes a database, rebuilds from Markdown while discarding history, or silently uploads a backup.

This runbook is local-only. It does not promise provider/cloud backup, encryption beyond the Windows current-user protection, or recovery of data already sent to a cloud provider.

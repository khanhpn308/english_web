# Runbook: First-run bootstrap and restore

## First run

1. The Windows launcher creates the current-user directory `%LOCALAPPDATA%\VocabularyApp`, a default data root `%USERPROFILE%\Documents\VocabularyApp`, and a protected bridge-key reference at `%LOCALAPPDATA%\VocabularyApp\secrets\bridge-key.dpapi`.
2. The operator selects or confirms the Markdown root and enters the rotated Antigravity client key only in the native launcher/operator surface. The key is written through the Windows current-user protected store; it is never put in the browser URL, Markdown, SQLite content, logs or Git.
3. The launcher validates the root is readable/writable, performs a dry-run Markdown parse/round-trip, validates Antigravity v4.8.4 loopback/auth profile without sending study content, and runs SQLite migration/integrity checks.
4. If any check fails, show a remediation screen and keep the browser app closed. `CONFIGURATION_REQUIRED` is not a reason to invent an environment variable, enable LAN, disable auth or proceed with an unverified source root.

## Restore and migration — T054 source implementation

**Operator-only and offline. No automatic switch.** A successful staging check
does not prove that the application's Windows launcher or runtime is usable.

1. Stop every Vocabulary launcher/backend process and verify the database is no
   longer in use. Preserve the **original** Data and Markdown roots. Obtain a
   consistent operator-managed, offline backup of **both** complete roots.
   Include SQLite journal/WAL companion files in that backup if present; never
   copy a live database by copying just the main SQLite file.
2. Select an **existing private local parent directory** containing neither
   original data nor backup data. Choose a **new, nonexistent child** for staging.
   Never stage inside the backup, original, Markdown root, or current app config.
3. With Python runtime dependencies already installed, run from the repository
   root (replace the placeholder paths with dedicated backup directories):

   ```powershell
   .\.venv\Scripts\python.exe -m launcher.src.restore `
      --confirm-stopped `
      --backup-data "C:\OfflineBackup\Data" `
      --backup-markdown "C:\OfflineBackup\Markdown" `
      --staging-root "C:\RecoveryPrivate\Trial001"
   ```

4. A result of `STAGING_VALIDATED_SWITCH_NOT_PERFORMED` means only that the
   staging copy passed Python migration/integrity, Markdown round-trip, source
   journal reconciliation, and historical-row preservation assertions. The
   script records a path-free `restore-evidence.json` **inside staging**. It
   does **not** modify `config.toml`, source backups, original roots, DPAPI
   protection, session state, or the browser.
5. If the command refuses the candidate, **do not switch roots or suppress
   DEGRADED**. Preserve the failed staging copy for controlled diagnosis. The
   original and backups remain untouched. In particular, a corrupted database,
   unresolved source journal or a mismatched data/Markdown pair is not
   repairable by discarding learning history.
6. After independent review and **separate authorization**, update native
   configuration by its approved owner-controlled procedure to point to
   `<staging>\Data` and `<staging>\Markdown`; restart from the normal
   Windows Launcher and inspect vocabulary, review/SRS, quiz/answers, writing
   feedback and consent. Do not manually edit encrypted keys or bypass
   configuration ACL enforcement.
7. If validation fails after switch, stop the launcher, revert the **configured
   root selection** to the preserved original paths using the approved native
   configuration workflow, and retain the candidate unchanged.

**Boundaries:** This is recovery validation, not a backup scheduler, an
installer, a data exporter, or a license to change platform security controls.
Same-user concurrent filesystem mutation cannot be ruled out by pure Python
path checks; operator-confirmed quiescence and private staging ACLs are required.
Windows desktop operation, adversarial security probes, and full migration
acceptance remain **PENDING** for project-wide verification.

This runbook is local-only. It does not promise provider/cloud backup, encryption beyond the Windows current-user protection, or recovery of data already sent to a cloud provider.

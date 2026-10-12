"""Operator-only staged restore. Never change the configured roots or the backup."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import stat
from pathlib import Path

from backend.app.adapters.source_files import SourceFileAdapter
from backend.app.application.operations import OperationLedger
from backend.app.application.source_recovery import SourceRecovery
from backend.app.application.source_write import SourceWriteCoordinator
from backend.app.markdown_sync.parser import parse_markdown
from backend.app.markdown_sync.serializer import serialize_document
from backend.app.persistence.database import Database
from backend.app.vocabulary.models import SourceFile

# Immutable learning evidence must survive migration and reconciliation.
PRESERVED_TABLES = (
    "word_families", "word_forms", "review_cards", "review_events",
    "quiz_attempts", "quiz_questions", "quiz_answers", "writing_feedback",
    "ai_consent_state", "ai_consent_event", "study_history",
    "study_history_commits", "study_history_quiz_submissions",
)
MAX_MARKDOWN_BYTES = 8 * 1024 * 1024


class RestoreRefused(RuntimeError):
    """Content-free category suitable for operator display."""


def _check_entry(path: Path) -> os.stat_result:
    info = path.lstat()
    if (
        stat.S_ISLNK(info.st_mode)
        or bool(getattr(info, "st_file_attributes", 0) & 0x400)
        or not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode))
        or (stat.S_ISREG(info.st_mode) and info.st_nlink != 1)
    ):
        raise RestoreRefused("UNSAFE_BACKUP_ENTRY")
    return info


def _safe_root(path: Path) -> Path:
    """Reject symlink/reparse aliases at every existing root component."""
    absolute = path.absolute()
    for entry in (*reversed(absolute.parents), absolute):
        _check_entry(entry)
    return absolute.resolve(strict=True)


def _inventory(root: Path, *, markdown: bool = False) -> dict[str, str]:
    if not stat.S_ISDIR(_check_entry(root).st_mode):
        raise RestoreRefused("INVALID_BACKUP_ROOT")
    inventory: dict[str, str] = {}
    for directory, dirs, files in os.walk(root, followlinks=False):
        parent = Path(directory)
        _check_entry(parent)
        for name in sorted(dirs):
            _check_entry(parent / name)
        for name in sorted(files):
            path = parent / name
            if not stat.S_ISREG(_check_entry(path).st_mode):
                raise RestoreRefused("UNSAFE_BACKUP_ENTRY")
            if name.lower().endswith((".dpapi", ".pem", ".key", ".token", ".secret")):
                raise RestoreRefused("PROTECTED_MATERIAL_IN_BACKUP")
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                if markdown and name.lower().endswith(".md"):
                    raw = stream.read(MAX_MARKDOWN_BYTES + 1)
                    if len(raw) > MAX_MARKDOWN_BYTES:
                        raise RestoreRefused("INVALID_MARKDOWN")
                    try:
                        parsed = parse_markdown(raw.decode("utf-8"), filename=name)
                        if (
                            not parsed.is_valid or parsed.document is None
                            or serialize_document(parsed.document).encode("utf-8") != raw
                        ):
                            raise RestoreRefused("INVALID_MARKDOWN")
                    except (ValueError, UnicodeError):
                        raise RestoreRefused("INVALID_MARKDOWN") from None
                    digest.update(raw)
                else:
                    while block := stream.read(1024 * 1024):
                        digest.update(block)
            inventory[path.relative_to(root).as_posix()] = digest.hexdigest()
    return inventory


def _db_snapshot(db_path: Path) -> dict[str, tuple[int, str]]:
    if not db_path.is_file() or not stat.S_ISREG(_check_entry(db_path).st_mode):
        raise RestoreRefused("MISSING_DATABASE")
    connection = sqlite3.connect(f"{db_path.as_uri()}?mode=ro", uri=True)
    try:
        if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise RestoreRefused("DATABASE_INTEGRITY")
        if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise RestoreRefused("DATABASE_INTEGRITY")
        names = {
            row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        if "alembic_version" not in names:
            raise RestoreRefused("SCHEMA_MISMATCH")
        snapshots: dict[str, tuple[int, str]] = {}
        for table in PRESERVED_TABLES:
            if table not in names:
                continue
            digest = hashlib.sha256()
            count = 0
            # Hash the value of each row rather than SQLite page layout or WAL bytes.
            for row in connection.execute(f'SELECT * FROM "{table}" ORDER BY rowid'):
                count += 1
                digest.update(repr(tuple(row)).encode("utf-8"))
                digest.update(b"\x00")
            snapshots[table] = count, digest.hexdigest()
        return snapshots
    except sqlite3.DatabaseError:
        raise RestoreRefused("DATABASE_INTEGRITY") from None
    finally:
        connection.close()


def _reconcile(db: Database, markdown_root: Path) -> None:
    """Use exactly the canonical startup source-journal recovery on staged data."""
    adapter = SourceFileAdapter(markdown_root)
    with db.engine.connect() as connection:
        sources = connection.exec_driver_sql(
            "SELECT id, relative_path, note_date, status, revision, etag, "
            "content_hash, last_parsed_at, error_code, created_at, updated_at "
            "FROM source_files"
        ).mappings().all()
    for source in sources:
        adapter.register_source(SourceFile(
            id=str(source["id"]), relative_path=str(source["relative_path"]),
            note_date=str(source["note_date"]), status=source["status"],
            revision=int(source["revision"]), etag=str(source["etag"]),
            content_hash=str(source["content_hash"])
            if source["content_hash"] is not None else None,
            last_parsed_at=str(source["last_parsed_at"])
            if source["last_parsed_at"] is not None else None,
            error_code=str(source["error_code"])
            if source["error_code"] is not None else None,
            created_at=str(source["created_at"]), updated_at=str(source["updated_at"]),
        ))
    ledger = OperationLedger(db.engine)
    ledger.recover_pending()
    SourceRecovery(SourceWriteCoordinator(db.engine, adapter)).reconcile(
        operation_ledger=ledger
    )
    with db.engine.connect() as connection:
        unresolved = connection.exec_driver_sql(
            "SELECT count(*) FROM source_write_journal "
            "WHERE state IN ('PREPARED','SOURCE_REPLACED','DEGRADED')"
        ).scalar_one()
    if unresolved:
        raise RestoreRefused("JOURNAL_DEGRADED")


def verify_staging(data_root: Path, markdown_root: Path, db_name: str) -> dict[str, int]:
    """Migrate and reconcile staging only; reject lost or modified history."""
    _inventory(markdown_root, markdown=True)
    db_path = data_root / db_name
    before = _db_snapshot(db_path)
    database = Database(db_path)
    try:
        database.initialize()
        after_migration = _db_snapshot(db_path)
        # Existing tables must preserve rows byte-for-byte across migration.
        if any(after_migration.get(name) != record for name, record in before.items()):
            raise RestoreRefused("LEARNING_HISTORY_CHANGED")
        _reconcile(database, markdown_root)
        after_recovery = _db_snapshot(db_path)
        # A recovered journal may project new vocabulary rows, but must never
        # erase existing quiz, feedback, consent or review history.
        durable = {
            "review_events", "quiz_attempts", "quiz_questions", "quiz_answers",
            "writing_feedback", "ai_consent_state", "ai_consent_event",
        }
        if any(after_recovery.get(name) != record for name, record in before.items()
               if name in durable):
            raise RestoreRefused("LEARNING_HISTORY_CHANGED")
        if any(after_recovery.get(name, (0, ""))[0] < record[0]
               for name, record in before.items()):
            raise RestoreRefused("LEARNING_HISTORY_LOST")
        return {name: count for name, (count, _) in after_recovery.items()}
    finally:
        database.close()


def restore_staging(
    backup_data: Path, backup_markdown: Path, staging_root: Path,
    *, db_name: str = "vocabulary.sqlite3",
) -> dict[str, object]:
    """Create a new, non-destructive staging copy from operator-managed backups."""
    if db_name != "vocabulary.sqlite3":
        raise RestoreRefused("UNSUPPORTED_DATABASE_NAME")
    data = _safe_root(backup_data)
    markdown = _safe_root(backup_markdown)
    stage = staging_root.absolute()
    if stage.exists() or stage.is_symlink():
        raise RestoreRefused("STAGING_ALREADY_EXISTS")
    # Reject nesting in either direction, including data/Markdown backup overlap.
    if (
        data == markdown or data.is_relative_to(markdown) or markdown.is_relative_to(data)
        or stage.is_relative_to(data) or stage.is_relative_to(markdown)
        or data.is_relative_to(stage) or markdown.is_relative_to(stage)
    ):
        raise RestoreRefused("OVERLAPPING_ROOTS")
    _safe_root(stage.parent)
    baseline_data = _inventory(data)
    baseline_md = _inventory(markdown, markdown=True)
    if db_name not in baseline_data:
        raise RestoreRefused("MISSING_DATABASE")
    stage.mkdir(mode=0o700)
    try:
        shutil.copytree(data, stage / "Data", symlinks=False)
        shutil.copytree(markdown, stage / "Markdown", symlinks=False)
        if (
            _inventory(stage / "Data") != baseline_data
            or _inventory(stage / "Markdown", markdown=True) != baseline_md
            or _inventory(data) != baseline_data
            or _inventory(markdown, markdown=True) != baseline_md
        ):
            raise RestoreRefused("COPY_MISMATCH")
        counts = verify_staging(stage / "Data", stage / "Markdown", db_name)
        # This is not authorization to change config.toml. The operator switches
        # roots only after independent review of these checks.
        receipt: dict[str, object] = {
            "state": "STAGING_VALIDATED_SWITCH_NOT_PERFORMED",
            "markdown_files": sum(name.endswith(".md") for name in baseline_md),
            "database_tables": counts,
        }
        (stage / "restore-evidence.json").write_text(
            json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
        return receipt
    except Exception:
        # Preserve failed staging for diagnosis, never delete data or backup.
        raise RestoreRefused("STAGING_REJECTED_OR_DEGRADED") from None


def main() -> int:
    parser = argparse.ArgumentParser(description="Operator-only offline staging restore")
    parser.add_argument("--backup-data", required=True, type=Path)
    parser.add_argument("--backup-markdown", required=True, type=Path)
    parser.add_argument("--staging-root", required=True, type=Path)
    parser.add_argument("--confirm-stopped", action="store_true")
    arguments = parser.parse_args()
    if not arguments.confirm_stopped:
        print("BLOCKED: STOP_APP_FIRST")
        return 2
    try:
        receipt = restore_staging(
            arguments.backup_data, arguments.backup_markdown, arguments.staging_root
        )
    except (RestoreRefused, OSError, ValueError, sqlite3.DatabaseError):
        print("BLOCKED: STAGING_NOT_AUTHORIZED")
        return 1
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

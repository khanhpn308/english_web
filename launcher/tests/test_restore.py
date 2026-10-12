"""T054 non-destructive staging contract probes (no live Windows or credentials)."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from backend.app.persistence.database import Database
from launcher.src.restore import RestoreRefused, _db_snapshot, restore_staging


def _backup(tmp_path: Path) -> tuple[Path, Path]:
    data = tmp_path / "original-data"
    markdown = tmp_path / "original-markdown"
    data.mkdir()
    markdown.mkdir()
    db = Database(data / "vocabulary.sqlite3")
    try:
        db.initialize()
    finally:
        db.close()
    return data, markdown


def test_staging_is_copy_only_and_retains_existing_backup(tmp_path: Path) -> None:
    data, markdown = _backup(tmp_path)
    original_hash = _db_snapshot(data / "vocabulary.sqlite3")
    stage = tmp_path / "candidate"
    receipt = restore_staging(data, markdown, stage)
    assert receipt["state"] == "STAGING_VALIDATED_SWITCH_NOT_PERFORMED"
    assert (stage / "Data" / "vocabulary.sqlite3").is_file()
    assert (stage / "Markdown").is_dir()
    assert json.loads((stage / "restore-evidence.json").read_text()) == receipt
    assert _db_snapshot(data / "vocabulary.sqlite3") == original_hash
    assert (data / "vocabulary.sqlite3").is_file()
    # No implicit swap or overwrite of the operator's only source.
    with pytest.raises(RestoreRefused, match="STAGING_ALREADY_EXISTS"):
        restore_staging(data, markdown, stage)


def test_missing_database_does_not_create_staging(tmp_path: Path) -> None:
    data = tmp_path / "data"
    markdown = tmp_path / "markdown"
    data.mkdir()
    markdown.mkdir()
    stage = tmp_path / "stage"
    with pytest.raises(RestoreRefused, match="MISSING_DATABASE"):
        restore_staging(data, markdown, stage)
    assert not stage.exists()


def test_corrupt_database_preserves_source(tmp_path: Path) -> None:
    data = tmp_path / "data"
    markdown = tmp_path / "markdown"
    data.mkdir()
    markdown.mkdir()
    raw = b"not-a-sqlite-database"
    (data / "vocabulary.sqlite3").write_bytes(raw)
    with pytest.raises(RestoreRefused, match="STAGING_REJECTED_OR_DEGRADED"):
        restore_staging(data, markdown, tmp_path / "stage")
    assert (data / "vocabulary.sqlite3").read_bytes() == raw


def test_overlap_denied_without_copy(tmp_path: Path) -> None:
    data, markdown = _backup(tmp_path)
    with pytest.raises(RestoreRefused, match="OVERLAPPING_ROOTS"):
        restore_staging(data, markdown, data / "nested-staging")
    assert not (data / "nested-staging").exists()


def test_rejects_symlink_inside_backup(tmp_path: Path) -> None:
    data, markdown = _backup(tmp_path)
    (markdown / "outside.md").symlink_to(data / "vocabulary.sqlite3")
    with pytest.raises(RestoreRefused, match="UNSAFE_BACKUP_ENTRY"):
        restore_staging(data, markdown, tmp_path / "staging")
    assert not (tmp_path / "staging").exists()


def test_rejects_protected_material_in_backup(tmp_path: Path) -> None:
    data, markdown = _backup(tmp_path)
    (data / "bridge-key.dpapi").write_bytes(b"synthetic")
    with pytest.raises(RestoreRefused, match="PROTECTED_MATERIAL_IN_BACKUP"):
        restore_staging(data, markdown, tmp_path / "staging")
    assert not (tmp_path / "staging").exists()


def test_existing_staging_never_replaced(tmp_path: Path) -> None:
    data, markdown = _backup(tmp_path)
    stage = tmp_path / "staging"
    stage.mkdir()
    marker = stage / "important.txt"
    marker.write_text("retain me")
    with pytest.raises(RestoreRefused, match="STAGING_ALREADY_EXISTS"):
        restore_staging(data, markdown, stage)
    assert marker.read_text() == "retain me"


def test_history_digest_changes_on_content_mutation(tmp_path: Path) -> None:
    data, _ = _backup(tmp_path)
    path = data / "vocabulary.sqlite3"
    before = _db_snapshot(path)
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "INSERT INTO word_families (id, root_lemma, created_at, updated_at) "
            "VALUES ('fixture', 'synthetic', '2026-01-01', '2026-01-01')"
        )
        connection.commit()
    finally:
        connection.close()
    assert _db_snapshot(path)["word_families"] != before["word_families"]

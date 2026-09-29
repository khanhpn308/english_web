"""SQLite migration and failure probes use only temporary, synthetic databases."""

import shutil
import sqlite3
from pathlib import Path
from time import monotonic
from unittest.mock import patch

import pytest
from alembic import command
from alembic.script import ScriptDirectory
from backend.app.persistence.database import Database, StorageError, migration_config
from sqlalchemy import Connection
from sqlalchemy.exc import IntegrityError, OperationalError


def test_fresh_and_repeat_upgrade_have_one_head_and_only_ledger(tmp_path: Path) -> None:
    db = Database(tmp_path / "fresh.db")
    try:
        first = db.initialize()
        assert first.schema_revision == "0001_storage"
        assert first.wal_supported is True
        assert first.journal_mode == "wal"
        assert db.initialize() == first
        with db.engine.connect() as connection:
            assert connection.exec_driver_sql("SELECT version_num FROM alembic_version").all() == [
                ("0001_storage",)
            ]
            assert connection.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).all() == [("alembic_version",)]
        assert ScriptDirectory.from_config(migration_config()).get_heads() == ["0001_storage"]
    finally:
        db.close()


def test_every_connection_enforces_foreign_keys_and_busy_timeout(tmp_path: Path) -> None:
    db = Database(tmp_path / "fk.db", busy_timeout_ms=80)
    try:
        db.initialize()
        with db.engine.begin() as connection:
            connection.exec_driver_sql("CREATE TABLE parent (id INTEGER PRIMARY KEY)")
            connection.exec_driver_sql(
                "CREATE TABLE child (parent_id INTEGER REFERENCES parent(id))"
            )
        for _ in range(2):
            with db.engine.begin() as connection:
                assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
                assert connection.exec_driver_sql("PRAGMA busy_timeout").scalar() == 80
                with pytest.raises(IntegrityError):
                    connection.exec_driver_sql("INSERT INTO child VALUES (999)")
    finally:
        db.close()


def test_busy_writer_is_bounded_and_history_is_unchanged(tmp_path: Path) -> None:
    path = tmp_path / "busy.db"
    db = Database(path, busy_timeout_ms=80)
    try:
        db.initialize()
        with db.engine.begin() as connection:
            connection.exec_driver_sql("CREATE TABLE history (id INTEGER PRIMARY KEY)")
            connection.exec_driver_sql("INSERT INTO history VALUES (1)")
        with sqlite3.connect(path) as writer:
            writer.execute("BEGIN IMMEDIATE")
            started = monotonic()
            with pytest.raises(StorageError, match="BUSY"):
                db.initialize()
            assert monotonic() - started < 2
            # WAL still permits a separate reader during a write transaction.
            with db.engine.connect() as reader:
                assert reader.exec_driver_sql("SELECT id FROM history").scalar() == 1
            with pytest.raises(OperationalError), db.engine.begin() as connection:
                connection.exec_driver_sql("INSERT INTO history VALUES (2)")
            writer.rollback()
        assert db.initialize().schema_revision == "0001_storage"
    finally:
        db.close()


@pytest.mark.parametrize("kind", ["unknown_revision", "unversioned", "bad_ledger"])
def test_schema_mismatch_preserves_existing_database(tmp_path: Path, kind: str) -> None:
    path = tmp_path / "mismatch.db"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE history (content TEXT)")
        connection.execute("INSERT INTO history VALUES ('synthetic-history')")
        if kind == "unknown_revision":
            connection.execute("CREATE TABLE alembic_version (version_num TEXT PRIMARY KEY)")
            connection.execute("INSERT INTO alembic_version VALUES ('future_revision')")
        elif kind == "bad_ledger":
            connection.execute("CREATE TABLE alembic_version (wrong_column TEXT)")
    before = path.read_bytes()
    db = Database(path)
    try:
        with pytest.raises(StorageError, match="SCHEMA_MISMATCH"):
            db.initialize()
        assert path.read_bytes() == before
    finally:
        db.close()


def test_readonly_database_is_not_ready_and_retains_ledger(tmp_path: Path) -> None:
    path = tmp_path / "readonly.db"
    db = Database(path)
    db.initialize()
    db.close()
    before = path.read_bytes()
    readonly = Database(path, read_only=True)
    try:
        with pytest.raises(StorageError, match="READ_ONLY"):
            readonly.initialize()
        assert path.read_bytes() == before
    finally:
        readonly.close()


def test_corrupt_copy_never_rebuilds_or_touches_original(tmp_path: Path) -> None:
    original = tmp_path / "original.db"
    db = Database(original)
    db.initialize()
    with db.engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE history (content TEXT)")
        connection.exec_driver_sql("INSERT INTO history VALUES ('synthetic-history')")
    db.close()
    original_bytes = original.read_bytes()
    copied = tmp_path / "corrupt-copy.db"
    shutil.copyfile(original, copied)
    with copied.open("r+b") as stream:
        stream.write(b"invalid sqlite header")
    corrupt_bytes = copied.read_bytes()
    corrupt = Database(copied)
    try:
        with pytest.raises(StorageError, match="INTEGRITY_FAILED"):
            corrupt.initialize()
        assert copied.read_bytes() == corrupt_bytes
        assert original.read_bytes() == original_bytes
    finally:
        corrupt.close()


def test_integrity_check_rejects_foreign_key_violations_without_repair(tmp_path: Path) -> None:
    path = tmp_path / "invalid-fk.db"
    db = Database(path)
    db.initialize()
    db.close()
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE parent (id INTEGER PRIMARY KEY)")
        connection.execute("CREATE TABLE child (id INTEGER REFERENCES parent(id))")
        connection.execute("INSERT INTO child VALUES (3)")
    before = path.read_bytes()
    try:
        with pytest.raises(StorageError, match="INTEGRITY_FAILED"):
            db.initialize()
        assert path.read_bytes() == before
    finally:
        db.close()


@pytest.mark.parametrize("timeout", [0, -1, 5001])
def test_timeout_must_be_bounded(tmp_path: Path, timeout: int) -> None:
    with pytest.raises(ValueError):
        Database(tmp_path / "unused.db", busy_timeout_ms=timeout)
    assert not (tmp_path / "unused.db").exists()


def test_missing_parent_is_not_created(tmp_path: Path) -> None:
    path = tmp_path / "missing" / "storage.db"
    db = Database(path)
    try:
        with pytest.raises(StorageError, match="UNAVAILABLE"):
            db.initialize()
        assert not path.parent.exists()
    finally:
        db.close()


def test_alembic_online_upgrade_and_repeat(tmp_path: Path) -> None:
    path = tmp_path / "cli.db"
    config = migration_config()
    config.set_main_option("sqlalchemy.url", "sqlite:///" + str(path))
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchall() == [
            ("0001_storage",)
        ]


def test_failed_migration_rolls_back_ddl_and_preserves_history(tmp_path: Path) -> None:
    db = Database(tmp_path / "rollback.db")
    try:
        db.initialize()
        with db.engine.begin() as connection:
            connection.exec_driver_sql("CREATE TABLE history (id INTEGER PRIMARY KEY)")
            connection.exec_driver_sql("INSERT INTO history VALUES (1)")

        def failing_migration(connection: Connection) -> None:
            connection.exec_driver_sql("CREATE TABLE partial_migration (id INTEGER)")
            connection.exec_driver_sql("INSERT INTO history VALUES (2)")
            raise StorageError("INJECTED_FAILURE")

        with pytest.raises(StorageError, match="INJECTED_FAILURE"):
            db.initialize(migrate=failing_migration)
        with db.engine.connect() as connection:
            assert connection.exec_driver_sql("SELECT id FROM history").all() == [(1,)]
            assert (
                connection.exec_driver_sql(
                    "SELECT name FROM sqlite_master WHERE name='partial_migration'"
                ).all()
                == []
            )
            revision = connection.exec_driver_sql(
                "SELECT version_num FROM alembic_version"
            ).scalar()
            assert revision == "0001_storage"
    finally:
        db.close()


def test_unsupported_wal_is_reported_with_durable_rollback_journal(tmp_path: Path) -> None:
    db = Database(tmp_path / "no-wal.db")
    try:
        with patch(
            "backend.app.persistence.database.select_journal_mode",
            side_effect=lambda connection: connection.execute(
                "PRAGMA journal_mode=DELETE"
            ).fetchone()[0],
        ):
            info = db.initialize()
        assert info.wal_supported is False
        assert info.journal_mode == "delete"
        with db.engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA journal_mode").scalar() == "delete"
    finally:
        db.close()


def test_readonly_file_permissions_fail_safe(tmp_path: Path) -> None:
    path = tmp_path / "permissions.db"
    db = Database(path)
    try:
        db.initialize()
        db.close()
        before = path.read_bytes()
        path.chmod(0o444)
        with pytest.raises(StorageError, match="READ_ONLY"):
            db.initialize()
        assert path.read_bytes() == before
    finally:
        path.chmod(0o600)
        db.close()


def test_downgrade_refuses_to_remove_ledger(tmp_path: Path) -> None:
    path = tmp_path / "downgrade.db"
    config = migration_config()
    config.set_main_option("sqlalchemy.url", "sqlite:///" + str(path))
    command.upgrade(config, "head")
    with pytest.raises(RuntimeError, match="Downgrade is disabled"):
        command.downgrade(config, "base")
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "0001_storage",
        )


@pytest.mark.parametrize("url", ["", "sqlite:///:memory:", "postgresql:///unused"])
def test_cli_rejects_unconfigured_or_nonlocal_storage(url: str) -> None:
    config = migration_config()
    config.set_main_option("sqlalchemy.url", url)
    with pytest.raises(StorageError, match="UNAVAILABLE"):
        command.upgrade(config, "head")


def test_offline_upgrade_requires_integrity_check() -> None:
    with pytest.raises(StorageError, match="integrity checks require an online database"):
        command.upgrade(migration_config(), "head", sql=True)

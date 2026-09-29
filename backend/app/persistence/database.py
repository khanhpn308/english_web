"""SQLite connection, migration ledger and startup safety (T005)."""

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Connection, Engine, create_engine, event
from sqlalchemy.exc import DBAPIError
from sqlalchemy.pool import NullPool

DEFAULT_BUSY_TIMEOUT_MS = 1000
MAX_BUSY_TIMEOUT_MS = 5000


class StorageError(RuntimeError):
    """A content-free category; never expose SQL, paths or database contents."""


@dataclass(frozen=True)
class StorageInfo:
    schema_revision: str
    journal_mode: str
    wal_supported: bool


def migration_config() -> Config:
    """Resolve scripts relative to the installed project, independent of cwd."""
    root = Path(__file__).resolve().parents[3]
    return Config(str(root / "alembic.ini"))


def select_journal_mode(connection: sqlite3.Connection) -> str:
    """Read the mode actually selected; unsupported WAL retains the existing mode."""
    return str(connection.execute("PRAGMA journal_mode=WAL").fetchone()[0])


def _failure(error: sqlite3.Error) -> StorageError:
    code = getattr(error, "sqlite_errorcode", 0) & 0xFF
    if code in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
        category = "BUSY"
    elif code == sqlite3.SQLITE_READONLY:
        category = "READ_ONLY"
    elif code in (sqlite3.SQLITE_CORRUPT, sqlite3.SQLITE_NOTADB):
        category = "INTEGRITY_FAILED"
    else:
        category = "UNAVAILABLE"
    return StorageError(category)


def _validate(connection: sqlite3.Connection, scripts: ScriptDirectory) -> None:
    # SQLite integrity_check omits FK violations: both checks are required.
    # Source: https://www.sqlite.org/pragma.html#pragma_integrity_check
    if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
        raise StorageError("INTEGRITY_FAILED")
    if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise StorageError("INTEGRITY_FAILED")
    tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    if not tables:
        return
    if "alembic_version" not in tables:
        raise StorageError("SCHEMA_MISMATCH")
    columns = connection.execute("PRAGMA table_info(alembic_version)").fetchall()
    if len(columns) != 1 or columns[0][1] != "version_num" or columns[0][5] != 1:
        raise StorageError("SCHEMA_MISMATCH")
    revisions = connection.execute("SELECT version_num FROM alembic_version").fetchall()
    known = {revision.revision for revision in scripts.walk_revisions()}
    if len(revisions) != 1 or revisions[0][0] not in known:
        raise StorageError("SCHEMA_MISMATCH")


class Database:
    """Own a local engine; initialize upgrades safely and requires writable storage."""

    def __init__(
        self,
        path: Path,
        *,
        busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
        read_only: bool = False,
    ) -> None:
        if not 1 <= busy_timeout_ms <= MAX_BUSY_TIMEOUT_MS:
            raise ValueError("busy_timeout_ms must be between 1 and 5000")
        mode = "ro" if read_only else "rwc"
        uri = path.resolve().as_uri() + "?mode=" + mode

        def connect() -> sqlite3.Connection:
            connection = sqlite3.connect(
                uri, uri=True, timeout=busy_timeout_ms / 1000, check_same_thread=False
            )
            # PRAGMAs must precede any transaction. SQLAlchemy emits BEGIN below.
            # Source: https://docs.sqlalchemy.org/en/21/dialects/sqlite.html
            connection.isolation_level = None
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
            if connection.execute("PRAGMA foreign_keys").fetchone() != (1,):
                connection.close()
                raise StorageError("UNAVAILABLE")
            return connection

        self.engine: Engine = create_engine(
            "sqlite+pysqlite://", creator=connect, poolclass=NullPool, hide_parameters=True
        )

        @event.listens_for(self.engine, "begin")
        def begin(connection: Connection) -> None:
            immediate = connection.get_execution_options().get("sqlite_begin_immediate", False)
            connection.exec_driver_sql("BEGIN IMMEDIATE" if immediate else "BEGIN")

    def initialize(self, *, migrate: Callable[[Connection], None] | None = None) -> StorageInfo:
        """Check before mutation; atomically migrate and prove write access, no retries."""
        config = migration_config()
        scripts = ScriptDirectory.from_config(config)
        heads = scripts.get_heads()
        if len(heads) != 1:
            raise StorageError("SCHEMA_MISMATCH")
        try:
            raw = self.engine.raw_connection()
            try:
                dbapi = raw.dbapi_connection
                if not isinstance(dbapi, sqlite3.Connection):
                    raise StorageError("UNAVAILABLE")
                _validate(dbapi, scripts)
                # journal_mode returns the mode actually selected, even without WAL support.
                # Source: https://www.sqlite.org/wal.html
                journal_mode = select_journal_mode(dbapi)
                if journal_mode not in {"wal", "delete", "truncate", "persist"}:
                    raise StorageError("UNAVAILABLE")
            finally:
                raw.close()
            with (
                self.engine.connect().execution_options(sqlite_begin_immediate=True) as connection,
                connection.begin(),
            ):
                dbapi = connection.connection.dbapi_connection
                if not isinstance(dbapi, sqlite3.Connection):
                    raise StorageError("UNAVAILABLE")
                # Recheck under the writer lock before touching the ledger.
                _validate(dbapi, scripts)
                if migrate is None:
                    config.attributes["connection"] = connection
                    command.upgrade(config, "head")
                else:
                    migrate(connection)
                # A repeated upgrade may do no writes, including on a readonly file.
                connection.exec_driver_sql("UPDATE alembic_version SET version_num=version_num")
            return StorageInfo(heads[0], journal_mode, journal_mode == "wal")
        except sqlite3.Error as error:
            raise _failure(error) from None
        except DBAPIError as error:
            if isinstance(error.orig, sqlite3.Error):
                raise _failure(error.orig) from None
            raise StorageError("UNAVAILABLE") from None

    def close(self) -> None:
        """Release connections; never remove files or change revision."""
        self.engine.dispose()

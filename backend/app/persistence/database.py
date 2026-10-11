"""SQLite connection, migration ledger and startup safety (T005)."""

import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import cast

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from backend.app.platform.telemetry import Telemetry
from sqlalchemy import Connection, Engine, create_engine, event
from sqlalchemy.exc import DBAPIError
from sqlalchemy.pool import NullPool

DEFAULT_BUSY_TIMEOUT_MS = 1000
MAX_BUSY_TIMEOUT_MS = 5000
_observing: ContextVar[bool] = ContextVar("readonly_storage_observation", default=False)


@contextmanager
def read_only_observation() -> Iterator[None]:
    """Use the same NullPool engine with mode=ro, including when a file disappears."""
    token = _observing.set(True)
    try:
        yield
    finally:
        _observing.reset(token)


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
    schema_objects = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE substr(lower(name), 1, 7) != 'sqlite_'"
        )
    }
    if not schema_objects:
        return
    if "alembic_version" not in schema_objects:
        raise StorageError("SCHEMA_MISMATCH")
    columns = connection.execute("PRAGMA table_info(alembic_version)").fetchall()
    if len(columns) != 1 or columns[0][1] != "version_num" or columns[0][5] != 1:
        raise StorageError("SCHEMA_MISMATCH")
    revisions = connection.execute("SELECT version_num FROM alembic_version").fetchall()
    known = {revision.revision for revision in scripts.walk_revisions()}
    if len(revisions) != 1 or revisions[0][0] not in known:
        raise StorageError("SCHEMA_MISMATCH")


class _ObservedConnection(sqlite3.Connection):
    """Record outcomes after DBAPI commit/rollback, not SQLAlchemy's pre-commit hook."""

    metric_operation: str | None = None
    metric_failed = False
    transaction_observer: Callable[[str, str], None] | None = None

    def _finished(self, committed: bool) -> None:
        operation = self.metric_operation
        self.metric_operation = None
        if operation is not None and self.transaction_observer is not None:
            result = "failure" if self.metric_failed or (operation == "write" and not committed) else "success"
            self.transaction_observer(operation, result)
        self.metric_failed = False

    def commit(self) -> None:
        committed = False
        try:
            super().commit()
            committed = True
        except BaseException:
            self.metric_failed = True
            raise
        finally:
            self._finished(committed)

    def rollback(self) -> None:
        try:
            super().rollback()
        except BaseException:
            self.metric_failed = True
            raise
        finally:
            self._finished(False)


class Database:
    """Own a local engine; initialize upgrades safely and requires writable storage."""

    def __init__(
        self,
        path: Path,
        *,
        busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
        read_only: bool = False,
        telemetry: Telemetry | None = None,
    ) -> None:
        if not 1 <= busy_timeout_ms <= MAX_BUSY_TIMEOUT_MS:
            raise ValueError("busy_timeout_ms must be between 1 and 5000")
        mode = "ro" if read_only else "rwc"
        self.path = path.resolve()
        self.telemetry = telemetry
        self.last_integrity_check_at: datetime | None = None
        self._schema_revision: str | None = None
        self.storage_failure: str | None = None
        self._status_lock = Lock()
        self._busy_count = 0
        self.diagnostics_failed = False
        base_uri = self.path.as_uri()

        def connect() -> sqlite3.Connection:
            uri = base_uri + "?mode=" + ("ro" if _observing.get() else mode)
            connection = cast(_ObservedConnection, sqlite3.connect(
                uri, uri=True, timeout=busy_timeout_ms / 1000, check_same_thread=False,
                factory=_ObservedConnection,
            ))
            connection.transaction_observer = self._transaction_finished
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
            try:
                dbapi = connection.connection.dbapi_connection
                if isinstance(dbapi, _ObservedConnection):
                    dbapi.metric_operation = "write" if immediate else "read"
                    dbapi.metric_failed = False
            except Exception:
                self._diagnostic_failure()
            connection.exec_driver_sql("BEGIN IMMEDIATE" if immediate else "BEGIN")

        @event.listens_for(self.engine, "before_cursor_execute")
        def writing(connection: Connection, _cursor: object, statement: str,
                    _parameters: object, _context: object, _many: bool) -> None:
            try:
                dbapi = connection.connection.dbapi_connection
                words = statement.lstrip().split(None, 1)
                if isinstance(dbapi, _ObservedConnection) and words and words[0].upper() in {
                    "INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP", "REPLACE",
                }:
                    dbapi.metric_operation = "write"
            except Exception:
                self._diagnostic_failure()

        @event.listens_for(self.engine, "handle_error")
        def failed(context: object) -> None:
            try:
                error = getattr(context, "original_exception", None)
                if isinstance(error, sqlite3.Error):
                    self._observe_failure(str(_failure(error)))
                connection = getattr(context, "connection", None)
                if connection is not None:
                    dbapi = connection.connection.dbapi_connection
                    if isinstance(dbapi, _ObservedConnection):
                        dbapi.metric_failed = True
            except Exception:
                self._diagnostic_failure()

    def _diagnostic_failure(self) -> None:
        self.diagnostics_failed = True
        if self.telemetry is not None:
            self.telemetry.span_retention_failed = True

    def _transaction_finished(self, operation: str, result: str) -> None:
        try:
            if self.telemetry is not None:
                self.telemetry.record_dependency("sqlite", operation, result)
        except Exception:
            self._diagnostic_failure()

    def _observe_failure(self, category: str, *, check: str = "database") -> None:
        try:
            with self._status_lock:
                if category == "BUSY":
                    if self._busy_count == 2**63 - 1:
                        self._diagnostic_failure()
                    else:
                        self._busy_count += 1
                if category in {"READ_ONLY", "INTEGRITY_FAILED", "SCHEMA_MISMATCH"}:
                    self.storage_failure = category
            if self.telemetry is not None:
                self.telemetry.record_storage_failure(category, check=check)
        except Exception:
            self._diagnostic_failure()

    @property
    def busy_count(self) -> int | None:
        with self._status_lock:
            return None if self.diagnostics_failed else self._busy_count

    def status_snapshot(self) -> tuple[str, str | None, int | None, int | None]:
        """Observe schema/read access and file size without integrity scans or writes."""
        try:
            with read_only_observation(), self.engine.connect() as connection, connection.begin():
                revisions = connection.exec_driver_sql("SELECT version_num FROM alembic_version").all()
        except DBAPIError as error:
            if isinstance(error.orig, sqlite3.Error):
                raise _failure(error.orig) from None
            raise StorageError("UNAVAILABLE") from None
        if len(revisions) != 1:
            raise StorageError("SCHEMA_MISMATCH")
        revision = revisions[0][0]
        try:
            size = self.path.stat().st_size
        except OSError:
            size = None
        with self._status_lock:
            status = self.storage_failure or ("OK" if self._schema_revision is not None else "NOT_READY")
            if self._schema_revision is not None and revision != self._schema_revision:
                status = "SCHEMA_MISMATCH"
            busy = None if self.diagnostics_failed else self._busy_count
        return status, revision if revision == self._schema_revision else None, size, busy

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
                self.last_integrity_check_at = datetime.now(UTC)
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
                self.last_integrity_check_at = datetime.now(UTC)
                if migrate is None:
                    config.attributes["connection"] = connection
                    command.upgrade(config, "head")
                else:
                    migrate(connection)
                # A repeated upgrade may do no writes, including on a readonly file.
                connection.exec_driver_sql("UPDATE alembic_version SET version_num=version_num")
            self.storage_failure = None
            self._schema_revision = heads[0]
            if self.telemetry is not None:
                self.telemetry.record_integrity(True)
            return StorageInfo(heads[0], journal_mode, journal_mode == "wal")
        except sqlite3.Error as error:
            self._observe_failure(str(_failure(error)), check="startup")
            raise _failure(error) from None
        except DBAPIError as error:
            if isinstance(error.orig, sqlite3.Error):
                raise _failure(error.orig) from None
            raise StorageError("UNAVAILABLE") from None
        except StorageError as error:
            self._observe_failure(str(error), check="startup")
            raise

    def close(self) -> None:
        """Release connections; never remove files or change revision."""
        self.engine.dispose()

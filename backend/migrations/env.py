"""Alembic uses the same safety checks for app startup and standalone upgrades."""

from pathlib import Path

from alembic import context
from backend.app.persistence.database import Database, StorageError
from sqlalchemy import Connection
from sqlalchemy.engine import make_url


def migrate(connection: Connection) -> None:
    # Source: https://alembic.sqlalchemy.org/en/latest/cookbook.html
    context.configure(connection=connection, target_metadata=None, transactional_ddl=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations() -> None:
    connection = context.config.attributes.get("connection")
    if isinstance(connection, Connection):
        migrate(connection)
        return
    if context.is_offline_mode():
        raise StorageError("UNAVAILABLE: integrity checks require an online database")
    configured_url = context.config.get_main_option("sqlalchemy.url")
    if not configured_url:
        raise StorageError("UNAVAILABLE: configure a local SQLite path")
    url = make_url(configured_url)
    if url.drivername not in {"sqlite", "sqlite+pysqlite"} or not url.database:
        raise StorageError("UNAVAILABLE: configure a local SQLite path")
    if url.host or url.username or url.password or url.query or url.database == ":memory:":
        raise StorageError("UNAVAILABLE: configure a local SQLite path")
    database = Database(Path(url.database))
    try:
        database.initialize(migrate=migrate)
    finally:
        database.close()


run_migrations()

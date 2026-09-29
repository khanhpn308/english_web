"""Establish the migration ledger only; domain migrations belong to later tasks."""

revision: str = "0001_storage"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Alembic itself creates and advances alembic_version for migration zero."""


def downgrade() -> None:
    """Removing the durable ledger requires an explicit recovery workflow."""
    raise RuntimeError("Downgrade is disabled; preserve the database for recovery")

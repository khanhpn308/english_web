"""Keep operation results and used idempotency fingerprints for database lifetime."""

import sqlalchemy as sa
from alembic import op

revision: str = "0002_operations"
down_revision: str | None = "0001_storage"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # Source: https://alembic.sqlalchemy.org/en/latest/ops.html#alembic.operations.Operations.create_table
    op.create_table(
        "operations",
        sa.Column("operation_id", sa.String(64), primary_key=True),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("result_ref", sa.String(128), nullable=True),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("error_category", sa.String(64), nullable=True),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("updated_at", sa.String(32), nullable=False),
        sa.CheckConstraint("status IN ('PENDING','SUCCEEDED','FAILED','UNKNOWN')"),
    )
    op.create_table(
        "operation_keys",
        sa.Column("kind", sa.String(64), primary_key=True),
        sa.Column("key_digest", sa.String(64), primary_key=True),
        sa.Column("request_digest", sa.String(64), nullable=False),
        sa.Column("operation_id", sa.String(64), nullable=False, unique=True),
        sa.ForeignKeyConstraint(["operation_id"], ["operations.operation_id"], ondelete="RESTRICT"),
    )


def downgrade() -> None:
    """The permanent intent ledger must never be dropped by routine downgrade."""
    raise RuntimeError("Downgrade is disabled; preserve operation history")

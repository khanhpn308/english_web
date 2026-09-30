"""Durable consent state and append-only event history."""

import sqlalchemy as sa
from alembic import op

revision: str = "0003_consent"
down_revision: str | None = "0002_operations"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "ai_consent_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("accepted_policy_version", sa.String(64), nullable=True),
        sa.Column("accepted_policy_digest", sa.String(64), nullable=True),
        sa.Column("last_choice_at", sa.Float(), nullable=True),
        sa.CheckConstraint("id = 1", name="ck_singleton_consent_state"),
        sa.CheckConstraint("state IN ('NOT_GRANTED', 'GRANTED', 'REVOKED')", name="ck_valid_state"),
    )

    # Initialize the singleton row safely
    op.execute(
        "INSERT INTO ai_consent_state "
        "(id, revision, state, accepted_policy_version, accepted_policy_digest, last_choice_at) "
        "VALUES (1, 0, 'NOT_GRANTED', NULL, NULL, NULL)"
    )

    op.create_table(
        "ai_consent_event",
        sa.Column("event_id", sa.String(64), primary_key=True),
        sa.Column("revision", sa.Integer(), nullable=False, unique=True),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("policy_version", sa.String(64), nullable=True),
        sa.Column("policy_digest", sa.String(64), nullable=True),
        sa.Column("created_at", sa.Float(), nullable=False),
        sa.Column("operation_id", sa.String(64), nullable=False),
        sa.CheckConstraint("action IN ('GRANT', 'REVOKE')", name="ck_valid_action"),
        sa.ForeignKeyConstraint(["operation_id"], ["operations.operation_id"], ondelete="RESTRICT"),
    )


def downgrade() -> None:
    raise RuntimeError("Downgrade is disabled; preserve consent history")

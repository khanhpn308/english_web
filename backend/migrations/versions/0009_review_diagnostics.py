"""Retain optional review diagnostics without altering canonical review history."""

import sqlalchemy as sa
from alembic import op

revision: str = "0009_review_diagnostics"
down_revision: str | None = "0008_quiz"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # Existing events remain valid without diagnostics; no historical data is backfilled.
    op.create_table(
        "review_event_diagnostics",
        sa.Column("event_id", sa.String(64), primary_key=True, nullable=False),
        sa.Column("client_occurred_at", sa.String(32), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["review_events.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "typeof(client_occurred_at)='text' AND length(client_occurred_at)=27 "
            "AND client_occurred_at GLOB '????-??-??T??:??:??.??????Z' "
            "AND julianday(client_occurred_at) IS NOT NULL",
            name="ck_review_diagnostics_client_occurred_at",
        ),
    )
    for action in ("UPDATE", "DELETE"):
        op.execute(
            f"CREATE TRIGGER append_only_review_diagnostics_{action.lower()} "
            f"BEFORE {action} ON review_event_diagnostics "
            "BEGIN SELECT RAISE(ABORT, 'Append-only review diagnostics'); END"
        )
    # SQLite REPLACE can bypass DELETE guards when recursive_triggers is off.
    # Guard the original event identity before any conflicting INSERT or upsert.
    op.execute(
        "CREATE TRIGGER preserve_review_diagnostic_event BEFORE INSERT "
        "ON review_event_diagnostics "
        "WHEN EXISTS (SELECT 1 FROM review_event_diagnostics WHERE event_id=NEW.event_id) "
        "BEGIN SELECT RAISE(ABORT, 'Append-only review diagnostics'); END"
    )


def downgrade() -> None:
    """Accepted diagnostic evidence has the same lifetime as its review history."""
    raise RuntimeError("Downgrade is disabled; preserve review diagnostic history")

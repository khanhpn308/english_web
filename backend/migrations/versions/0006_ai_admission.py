"""Preserve one immutable authorization admission per AI operation (T016)."""

import sqlalchemy as sa
from alembic import op

revision: str = "0006_ai_admission"
down_revision: str | None = "0005_review"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "ai_operation_admission",
        sa.Column("operation_id", sa.String(64), primary_key=True),
        sa.Column("consent_revision", sa.Integer(), nullable=False),
        sa.Column("policy_version", sa.String(80), nullable=False),
        sa.Column("policy_digest", sa.String(64), nullable=False),
        sa.Column("scope", sa.String(32), nullable=False),
        sa.Column("provider_label", sa.String(64), nullable=False),
        sa.Column("model_id", sa.String(64), nullable=False),
        sa.Column("route", sa.String(32), nullable=False),
        sa.Column("billing_mode", sa.String(32), nullable=False),
        sa.Column("admission_state", sa.String(16), nullable=False),
        sa.Column("admitted_at", sa.String(20), nullable=False),
        sa.ForeignKeyConstraint(["operation_id"], ["operations.operation_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["consent_revision"], ["ai_consent_event.revision"], ondelete="RESTRICT"
        ),
        sa.CheckConstraint("consent_revision >= 1"),
        sa.CheckConstraint(
            "length(policy_version) BETWEEN 1 AND 80 "
            "AND policy_version GLOB '[a-z0-9]*' "
            "AND policy_version NOT GLOB '*[^a-z0-9._-]*'"
        ),
        sa.CheckConstraint("length(policy_digest)=64 AND policy_digest NOT GLOB '*[^a-f0-9]*'"),
        sa.CheckConstraint("scope IN ('LOOKUP','QUIZ_GENERATION','WRITING_FEEDBACK')"),
        sa.CheckConstraint("provider_label='Antigravity/Google'"),
        sa.CheckConstraint("model_id='gemini-3.8-flash-high'"),
        sa.CheckConstraint("route='primary'"),
        sa.CheckConstraint("billing_mode='configured-account'"),
        # UNKNOWN belongs to the existing operation ledger. This row records admission,
        # independently of whether transport completed or was ever known to have sent bytes.
        sa.CheckConstraint("admission_state='ADMITTED'"),
        sa.CheckConstraint(
            "typeof(admitted_at)='text' AND length(admitted_at)=20 "
            "AND admitted_at GLOB '????-??-??T??:??:??Z'"
        ),
    )
    # Prevent REPLACE from erasing the one-admission fence when recursive triggers are off.
    op.execute(
        "CREATE TRIGGER preserve_ai_admission_insert BEFORE INSERT ON ai_operation_admission "
        "WHEN EXISTS (SELECT 1 FROM ai_operation_admission WHERE operation_id=NEW.operation_id) "
        "BEGIN SELECT RAISE(ABORT, 'Preserve AI admission'); END"
    )
    for action in ("UPDATE", "DELETE"):
        op.execute(
            f"CREATE TRIGGER preserve_ai_admission_{action.lower()} BEFORE {action} "
            "ON ai_operation_admission "
            "BEGIN SELECT RAISE(ABORT, 'Preserve AI admission'); END"
        )


def downgrade() -> None:
    raise RuntimeError("Downgrade is disabled; preserve AI admission history")

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
        sa.Column("accepted_policy_version", sa.String(80), nullable=True),
        sa.Column("accepted_policy_digest", sa.String(64), nullable=True),
        sa.Column("last_choice_at", sa.String(20), nullable=True),
        sa.Column("policy_history", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("policy_conflicts", sa.Text(), nullable=False, server_default="{}"),
        sa.CheckConstraint("id = 1", name="ck_singleton_consent_state"),
        sa.CheckConstraint("state IN ('NOT_GRANTED', 'GRANTED', 'REVOKED')", name="ck_valid_state"),
        sa.CheckConstraint("revision >= 0", name="ck_consent_revision"),
        sa.CheckConstraint(
            "(state='NOT_GRANTED' AND revision=0 AND last_choice_at IS NULL) "
            "OR (state IN ('GRANTED','REVOKED') AND revision>0 "
            "AND typeof(last_choice_at)='text' AND length(last_choice_at)=20 "
            "AND last_choice_at GLOB '????-??-??T??:??:??Z')",
            name="ck_consent_choice_time",
        ),
        sa.CheckConstraint("json_valid(policy_history) AND json_type(policy_history)='object'"),
        sa.CheckConstraint("json_valid(policy_conflicts) AND json_type(policy_conflicts)='object'"),
        sa.CheckConstraint(
            "(state='GRANTED' AND accepted_policy_version IS NOT NULL "
            "AND accepted_policy_digest IS NOT NULL AND last_choice_at IS NOT NULL) "
            "OR (state!='GRANTED' AND accepted_policy_version IS NULL "
            "AND accepted_policy_digest IS NULL)",
            name="ck_consent_identity",
        ),
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
        sa.Column("policy_version", sa.String(80), nullable=True),
        sa.Column("policy_digest", sa.String(64), nullable=True),
        sa.Column("scopes", sa.Text(), nullable=True),
        sa.Column("dispatch_rules", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(20), nullable=False),
        sa.Column("operation_id", sa.String(64), nullable=False, unique=True),
        sa.CheckConstraint("action IN ('GRANTED', 'REVOKED')", name="ck_valid_action"),
        sa.CheckConstraint("revision >= 1"),
        sa.CheckConstraint(
            "typeof(created_at)='text' AND length(created_at)=20 "
            "AND created_at GLOB '????-??-??T??:??:??Z'",
            name="ck_event_utc_time",
        ),
        sa.CheckConstraint(
            "(action='GRANTED' AND policy_version IS NOT NULL AND policy_digest IS NOT NULL "
            "AND scopes IS NOT NULL AND json_valid(scopes) "
            "AND dispatch_rules IS NOT NULL AND json_valid(dispatch_rules)) "
            "OR (action='REVOKED' AND policy_version IS NULL AND policy_digest IS NULL "
            "AND scopes IS NULL AND dispatch_rules IS NULL)",
            name="ck_event_snapshot",
        ),
        sa.ForeignKeyConstraint(["operation_id"], ["operations.operation_id"], ondelete="RESTRICT"),
    )

    # Policy configuration/history is separate from telemetry and cannot be overwritten.
    # Keeping the registry on the singleton preserves T014's existing table contract.
    for column in ("policy_history", "policy_conflicts"):
        duplicates = (
            f"(SELECT count(*) FROM json_each(NEW.{column})) != "
            f"(SELECT count(DISTINCT key) FROM json_each(NEW.{column}))"
        )
        op.execute(
            f"CREATE TRIGGER unique_{column}_insert BEFORE INSERT ON ai_consent_state "
            f"WHEN {duplicates} BEGIN SELECT RAISE(ABORT, 'Duplicate policy identity'); END"
        )
        op.execute(
            f"CREATE TRIGGER immutable_{column} BEFORE UPDATE OF {column} ON ai_consent_state "
            f"WHEN {duplicates} OR EXISTS (SELECT 1 FROM json_each(OLD.{column}) old_entry "
            f"WHERE NOT EXISTS (SELECT 1 FROM json_each(NEW.{column}) new_entry "
            "WHERE new_entry.key=old_entry.key AND new_entry.value=old_entry.value)) "
            "BEGIN SELECT RAISE(ABORT, 'Immutable policy history'); END"
        )
    op.execute(
        "CREATE TRIGGER preserve_consent_singleton BEFORE DELETE ON ai_consent_state "
        "BEGIN SELECT RAISE(ABORT, 'Preserve consent history'); END"
    )
    # SQLite REPLACE can bypass delete triggers unless recursive_triggers is enabled.
    op.execute(
        "CREATE TRIGGER preserve_consent_replace BEFORE INSERT ON ai_consent_state "
        "WHEN EXISTS (SELECT 1 FROM ai_consent_state WHERE id=NEW.id) "
        "BEGIN SELECT RAISE(ABORT, 'Preserve consent history'); END"
    )
    op.execute(
        "CREATE TRIGGER append_only_consent_insert BEFORE INSERT ON ai_consent_event "
        "WHEN EXISTS (SELECT 1 FROM ai_consent_event WHERE event_id=NEW.event_id "
        "OR revision=NEW.revision OR operation_id=NEW.operation_id) "
        "BEGIN SELECT RAISE(ABORT, 'Append-only consent events'); END"
    )
    for action in ("UPDATE", "DELETE"):
        op.execute(
            f"CREATE TRIGGER append_only_consent_{action.lower()} BEFORE {action} "
            "ON ai_consent_event BEGIN SELECT RAISE(ABORT, 'Append-only consent events'); END"
        )


def downgrade() -> None:
    raise RuntimeError("Downgrade is disabled; preserve consent history")

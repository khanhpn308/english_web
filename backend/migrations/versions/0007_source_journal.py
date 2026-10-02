"""Durable source replacement journal and recovery evidence (T022)."""

import sqlalchemy as sa
from alembic import op

revision: str = "0007_source_journal"
down_revision: str | None = "0006_ai_admission"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "source_write_journal",
        sa.Column("operation_id", sa.String(64), primary_key=True),
        sa.Column("source_id", sa.String(64), nullable=False),
        sa.Column("old_hash", sa.String(64), nullable=False),
        sa.Column("new_hash", sa.String(64), nullable=False),
        sa.Column("temp_path", sa.String(512), nullable=True),
        sa.Column("temp_device", sa.String(40), nullable=True),
        sa.Column("temp_inode", sa.String(40), nullable=True),
        sa.Column("intended_projection_revision", sa.Integer(), nullable=False),
        sa.Column("effect_plan", sa.Text(), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column("result_ref", sa.String(128), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("updated_at", sa.String(32), nullable=False),
        sa.ForeignKeyConstraint(["operation_id"], ["operations.operation_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_id"], ["source_files.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "length(old_hash)=64 AND old_hash NOT GLOB '*[^0-9a-f]*'",
            name="ck_source_journal_old_hash",
        ),
        sa.CheckConstraint(
            "length(new_hash)=64 AND new_hash NOT GLOB '*[^0-9a-f]*'",
            name="ck_source_journal_new_hash",
        ),
        sa.CheckConstraint("old_hash != new_hash", name="ck_source_journal_hashes_differ"),
        sa.CheckConstraint(
            "(temp_path IS NULL AND temp_device IS NULL AND temp_inode IS NULL) OR "
            "(temp_path IS NOT NULL AND temp_device IS NOT NULL AND temp_inode IS NOT NULL "
            "AND length(temp_device) BETWEEN 1 AND 40 AND temp_device NOT GLOB '*[^0-9]*' "
            "AND length(temp_inode) BETWEEN 1 AND 40 AND temp_inode NOT GLOB '*[^0-9]*' "
            "AND length(temp_path) BETWEEN 1 AND 512 AND substr(temp_path,1,1)!='/' "
            "AND instr(temp_path,':')=0 AND instr(temp_path,char(92))=0)",
            name="ck_source_journal_temp_handle",
        ),
        sa.CheckConstraint(
            "json_valid(effect_plan) AND coalesce(json_extract(effect_plan,'$.version'),0)=1 "
            "AND coalesce(json_type(effect_plan,'$.forms'),'')='array' "
            "AND coalesce(json_type(effect_plan,'$.links'),'')='array' "
            "AND coalesce(json_type(effect_plan,'$.removed'),'')='array'",
            name="ck_source_journal_effect_plan",
        ),
        sa.CheckConstraint("response_status BETWEEN 200 AND 299", name="ck_source_journal_receipt"),
        sa.CheckConstraint(
            "typeof(intended_projection_revision)='integer' AND intended_projection_revision >= 1",
            name="ck_source_journal_revision",
        ),
        sa.CheckConstraint(
            "state IN ('PREPARED','SOURCE_REPLACED','COMMITTED','ABORTED','DEGRADED')",
            name="ck_source_journal_state",
        ),
    )
    op.create_index(
        "ix_source_write_journal_source",
        "source_write_journal",
        ["source_id", "updated_at"],
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_source_write_journal_active_source "
        "ON source_write_journal(source_id) "
        "WHERE state IN ('PREPARED','SOURCE_REPLACED','DEGRADED')"
    )
    # Journal evidence is append-only. A retry must inspect the existing row rather than replace it.
    op.execute(
        "CREATE TRIGGER source_journal_initial_state BEFORE INSERT ON source_write_journal "
        "WHEN NEW.state!='PREPARED' OR NEW.temp_path IS NOT NULL "
        "BEGIN SELECT RAISE(ABORT, 'Journal must start PREPARED without staged material'); END"
    )
    op.execute(
        "CREATE TRIGGER preserve_source_write_journal_insert "
        "BEFORE INSERT ON source_write_journal "
        "WHEN EXISTS (SELECT 1 FROM source_write_journal WHERE operation_id=NEW.operation_id) "
        "BEGIN SELECT RAISE(ABORT, 'Preserve source journal evidence'); END"
    )
    op.execute(
        "CREATE TRIGGER immutable_source_write_journal_evidence "
        "BEFORE UPDATE OF operation_id,source_id,old_hash,new_hash,"
        "intended_projection_revision,effect_plan,response_status,result_ref,created_at "
        "ON source_write_journal "
        "WHEN NEW.operation_id!=OLD.operation_id OR NEW.source_id!=OLD.source_id "
        "OR NEW.old_hash!=OLD.old_hash OR NEW.new_hash!=OLD.new_hash "
        "OR NEW.intended_projection_revision!=OLD.intended_projection_revision "
        "OR NEW.effect_plan!=OLD.effect_plan OR NEW.response_status!=OLD.response_status "
        "OR NEW.result_ref!=OLD.result_ref "
        "OR NEW.created_at!=OLD.created_at "
        "BEGIN SELECT RAISE(ABORT, 'Immutable source journal evidence'); END"
    )
    op.execute(
        "CREATE TRIGGER immutable_source_journal_temp BEFORE UPDATE OF "
        "temp_path,temp_device,temp_inode ON source_write_journal "
        "WHEN OLD.state!='PREPARED' OR OLD.temp_path IS NOT NULL "
        "BEGIN SELECT RAISE(ABORT, 'Immutable staged temp handle'); END"
    )
    op.execute(
        "CREATE TRIGGER source_write_journal_state_transition "
        "BEFORE UPDATE OF state ON source_write_journal "
        "WHEN NOT ((OLD.state='PREPARED' AND "
        "NEW.state IN ('SOURCE_REPLACED','ABORTED','DEGRADED')) "
        "OR (OLD.state='SOURCE_REPLACED' AND NEW.state IN ('COMMITTED','DEGRADED'))) "
        "BEGIN SELECT RAISE(ABORT, 'Invalid source journal transition'); END"
    )
    op.execute(
        "CREATE TRIGGER preserve_source_write_journal_delete "
        "BEFORE DELETE ON source_write_journal "
        "BEGIN SELECT RAISE(ABORT, 'Preserve source journal history'); END"
    )


def downgrade() -> None:
    """Refuse destructive downgrade because recovery evidence is durable history."""
    raise RuntimeError("Downgrade is disabled; preserve source journal history")

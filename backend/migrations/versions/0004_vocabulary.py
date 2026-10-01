"""Vocabulary canonical schema, source links and preview storage (T019)."""

import sqlalchemy as sa
from alembic import op

revision: str = "0004_vocabulary"
down_revision: str | None = "0003_consent"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # 1. Word Families
    op.create_table(
        "word_families",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("root_lemma", sa.String(128), nullable=False),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("updated_at", sa.String(32), nullable=False),
    )

    # 2. Canonical Word Forms
    op.create_table(
        "word_forms",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("family_id", sa.String(64), nullable=False),
        sa.Column("lemma", sa.String(128), nullable=False),
        sa.Column("normalized_lemma", sa.String(128), nullable=False),
        sa.Column("part_of_speech", sa.String(32), nullable=False),
        sa.Column("meanings_en", sa.JSON(), nullable=False),
        sa.Column("meanings_vi", sa.JSON(), nullable=False),
        sa.Column("examples", sa.JSON(), nullable=False),
        sa.Column("ipa_us", sa.String(128), nullable=True),
        sa.Column("ipa_status", sa.String(16), nullable=False),
        sa.Column("cambridge_url", sa.String(512), nullable=True),
        sa.Column("cambridge_status", sa.String(16), nullable=False),
        sa.Column("verification_summary", sa.String(16), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("updated_at", sa.String(32), nullable=False),
        sa.ForeignKeyConstraint(["family_id"], ["word_families.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "family_id",
            "normalized_lemma",
            "part_of_speech",
            name="uq_word_forms_canonical_identity",
        ),
        sa.CheckConstraint(
            "ipa_status IN ('VERIFIED', 'UNVERIFIED', 'MISSING')",
            name="ck_word_forms_ipa_status",
        ),
        sa.CheckConstraint(
            "cambridge_status IN ('VERIFIED', 'UNVERIFIED', 'MISSING')",
            name="ck_word_forms_cambridge_status",
        ),
        sa.CheckConstraint(
            "verification_summary IN ('VERIFIED', 'UNVERIFIED', 'MISSING')",
            name="ck_word_forms_verification_summary",
        ),
    )
    op.create_index("ix_word_forms_normalized_lemma", "word_forms", ["normalized_lemma"])
    op.create_index("ix_word_forms_family_id", "word_forms", ["family_id"])

    # 3. Source Files (Markdown note files)
    op.create_table(
        "source_files",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("relative_path", sa.String(256), nullable=False, unique=True),
        sa.Column("note_date", sa.String(10), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("etag", sa.String(64), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("last_parsed_at", sa.String(32), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("updated_at", sa.String(32), nullable=False),
        sa.CheckConstraint(
            "status IN ('VALID', 'INVALID', 'MISSING')",
            name="ck_source_files_status",
        ),
    )
    op.create_index("ix_source_files_note_date", "source_files", ["note_date"])

    # 4. Word Form Source Occurrences (Many-to-many link)
    op.create_table(
        "word_form_sources",
        sa.Column("word_form_id", sa.String(64), nullable=False),
        sa.Column("source_id", sa.String(64), nullable=False),
        sa.Column("note_date", sa.String(10), nullable=False),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.PrimaryKeyConstraint("word_form_id", "source_id", name="pk_word_form_sources"),
        sa.ForeignKeyConstraint(["word_form_id"], ["word_forms.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_id"], ["source_files.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_word_form_sources_note_date", "word_form_sources", ["note_date"])
    op.create_index("ix_word_form_sources_source_id", "word_form_sources", ["source_id"])
    op.create_index("ix_word_form_sources_word_form_id", "word_form_sources", ["word_form_id"])

    # 5. Lookup Previews
    op.create_table(
        "lookup_previews",
        sa.Column("lookup_id", sa.String(64), primary_key=True),
        sa.Column("operation_id", sa.String(64), nullable=True),
        sa.Column("owner_session_id", sa.String(64), nullable=False),
        sa.Column("term", sa.String(128), nullable=False),
        sa.Column("forms_payload", sa.JSON(), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column("prompt_version", sa.String(64), nullable=False),
        sa.Column("verification_summary", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.Float(), nullable=False),
        sa.Column("expires_at", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["operation_id"], ["operations.operation_id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "status IN ('PREVIEW', 'CONSUMED', 'EXPIRED', 'FAILED')",
            name="ck_lookup_previews_status",
        ),
        sa.CheckConstraint(
            "verification_summary IN ('VERIFIED', 'UNVERIFIED', 'MISSING')",
            name="ck_lookup_previews_verification_summary",
        ),
    )
    op.create_index("ix_lookup_previews_owner", "lookup_previews", ["owner_session_id"])


def downgrade() -> None:
    raise RuntimeError("Downgrade is disabled; preserve vocabulary history")

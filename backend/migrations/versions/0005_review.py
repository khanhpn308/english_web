"""Canonical review cards and append-only operation-linked history (T031)."""

import sqlalchemy as sa
from alembic import op

revision: str = "0005_review"
down_revision: str | None = "0004_vocabulary"
branch_labels: str | None = None
depends_on: str | None = None


def _utc_constraint(column: str, name: str) -> sa.CheckConstraint:
    return sa.CheckConstraint(
        f"typeof({column})='text' AND length({column})=27 "
        f"AND {column} GLOB '????-??-??T??:??:??.??????Z' AND julianday({column}) IS NOT NULL",
        name=name,
    )


def upgrade() -> None:
    op.create_table(
        "review_cards",
        sa.Column("card_id", sa.String(64), primary_key=True),
        sa.Column("word_form_id", sa.String(64), nullable=False),
        sa.Column("box", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("due_at", sa.String(32), nullable=True),
        sa.Column("queue_revision", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("word_form_id", name="uq_review_cards_word_form"),
        sa.ForeignKeyConstraint(["word_form_id"], ["word_forms.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "typeof(box)='integer' AND box BETWEEN 0 AND 5", name="ck_review_cards_box"
        ),
        sa.CheckConstraint(
            "(box=0 AND due_at IS NULL) OR (box>0 AND due_at IS NOT NULL "
            "AND typeof(due_at)='text' AND length(due_at)=27 "
            "AND due_at GLOB '????-??-??T??:??:??.??????Z' AND julianday(due_at) IS NOT NULL)",
            name="ck_review_cards_schedule",
        ),
        sa.CheckConstraint(
            "typeof(queue_revision)='integer' AND queue_revision>=0",
            name="ck_review_cards_revision",
        ),
    )
    op.create_index("ix_review_cards_due_at", "review_cards", ["due_at"])
    op.create_table(
        "review_events",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("card_id", sa.String(64), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("rating", sa.String(16), nullable=False),
        sa.Column("reviewed_at", sa.String(32), nullable=False),
        sa.Column("next_due_at", sa.String(32), nullable=False),
        sa.Column("next_box", sa.Integer(), nullable=False),
        sa.Column("operation_id", sa.String(64), nullable=False),
        # Assessment owns these opaque snapshot references; its tables are not present yet.
        sa.Column("attempt_id", sa.String(64), nullable=True),
        sa.Column("question_id", sa.String(64), nullable=True),
        sa.ForeignKeyConstraint(["card_id"], ["review_cards.card_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["operation_id"], ["operations.operation_id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("operation_id", "card_id", name="uq_review_events_operation_card"),
        sa.CheckConstraint("source IN ('FLASHCARD','QUIZ')", name="ck_review_events_source"),
        sa.CheckConstraint(
            "rating IN ('AGAIN','HARD','GOOD','EASY')", name="ck_review_events_rating"
        ),
        sa.CheckConstraint(
            "typeof(next_box)='integer' AND next_box BETWEEN 1 AND 5", name="ck_review_events_box"
        ),
        _utc_constraint("reviewed_at", "ck_review_events_reviewed_at"),
        _utc_constraint("next_due_at", "ck_review_events_next_due_at"),
    )
    op.create_index("ix_review_events_card_time", "review_events", ["card_id", "reviewed_at"])
    for action in ("UPDATE", "DELETE"):
        op.execute(
            f"CREATE TRIGGER append_only_review_{action.lower()} BEFORE {action} ON review_events "
            "BEGIN SELECT RAISE(ABORT, 'Append-only review events'); END"
        )
    # REPLACE may bypass DELETE triggers with recursive_triggers off: guard INSERT too.
    op.execute(
        "CREATE TRIGGER unique_review_operation BEFORE INSERT ON review_events "
        "WHEN EXISTS (SELECT 1 FROM review_events "
        "WHERE operation_id=NEW.operation_id AND card_id=NEW.card_id) "
        "BEGIN SELECT RAISE(ABORT, 'Review operation already applied'); END"
    )
    op.execute(
        "CREATE TRIGGER preserve_review_event_id BEFORE INSERT ON review_events "
        "WHEN EXISTS (SELECT 1 FROM review_events WHERE id=NEW.id "
        "AND (operation_id!=NEW.operation_id OR card_id!=NEW.card_id)) "
        "BEGIN SELECT RAISE(ABORT, 'Append-only review events'); END"
    )
    op.execute(
        "CREATE TRIGGER preserve_review_card_delete BEFORE DELETE ON review_cards "
        "BEGIN SELECT RAISE(ABORT, 'Preserve review cards'); END"
    )
    op.execute(
        "CREATE TRIGGER preserve_review_card_replace BEFORE INSERT ON review_cards "
        "WHEN EXISTS (SELECT 1 FROM review_cards "
        "WHERE card_id=NEW.card_id OR word_form_id=NEW.word_form_id) "
        "BEGIN SELECT RAISE(ABORT, 'Preserve review cards'); END"
    )
    op.execute(
        "CREATE TRIGGER immutable_review_card_identity BEFORE UPDATE OF card_id,word_form_id "
        "ON review_cards WHEN NEW.card_id!=OLD.card_id OR NEW.word_form_id!=OLD.word_form_id "
        "BEGIN SELECT RAISE(ABORT, 'Immutable review card identity'); END"
    )


def downgrade() -> None:
    raise RuntimeError("Downgrade is disabled; preserve review history")

"""Append-only canonical Answer receipts, without reconstructing lost revisions."""

import sqlalchemy as sa
from alembic import op

revision: str = "0010_quiz_answer_receipts"
down_revision: str | None = "0009_review_diagnostics"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # Keep all existing latest drafts untouched. Past overwritten answers are unavailable.
    op.create_table(
        "quiz_answer_receipts",
        sa.Column("attempt_id", sa.String(64), nullable=False),
        sa.Column("question_id", sa.String(64), nullable=False),
        sa.Column("draft_revision", sa.Integer(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("self_score", sa.Integer(), nullable=True),
        sa.Column("saved_at", sa.String(32), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("operation_id", sa.String(64), primary_key=True, nullable=False),
        sa.ForeignKeyConstraint(
            ["attempt_id", "question_id"], ["quiz_questions.attempt_id", "quiz_questions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["operation_id"], ["operations.operation_id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "attempt_id", "question_id", "draft_revision", name="uq_answer_receipt_revision"
        ),
        sa.CheckConstraint("typeof(draft_revision)='integer' AND draft_revision>=1"),
        sa.CheckConstraint("typeof(answer)='text' AND length(answer)<=4096"),
        sa.CheckConstraint(
            "self_score IS NULL OR (typeof(self_score)='integer' AND self_score BETWEEN 0 AND 4)"
        ),
        sa.CheckConstraint(
            "typeof(saved_at)='text' AND length(saved_at)=27 "
            "AND saved_at GLOB '????-??-??T??:??:??.??????Z' AND julianday(saved_at) IS NOT NULL"
        ),
        sa.CheckConstraint(
            "(self_score IS NULL AND state IN ('BLANK','DRAFT')) OR "
            "(self_score IS NOT NULL AND state='SCORED')"
        ),
    )
    for action in ("UPDATE", "DELETE"):
        op.execute(
            f"CREATE TRIGGER quiz_answer_receipt_no_{action.lower()} BEFORE {action} "
            "ON quiz_answer_receipts BEGIN SELECT RAISE(ABORT, 'Immutable answer receipt'); END"
        )
    # REPLACE can bypass DELETE triggers; reject either conflicting identity at INSERT.
    op.execute(
        "CREATE TRIGGER quiz_answer_receipt_identity BEFORE INSERT ON quiz_answer_receipts "
        "WHEN EXISTS (SELECT 1 FROM quiz_answer_receipts WHERE operation_id=NEW.operation_id "
        "OR (attempt_id=NEW.attempt_id AND question_id=NEW.question_id "
        "AND draft_revision=NEW.draft_revision)) "
        "BEGIN SELECT RAISE(ABORT, 'Immutable answer receipt'); END"
    )
    op.execute(
        "CREATE TRIGGER quiz_answer_receipt_evidence BEFORE INSERT ON quiz_answer_receipts "
        "WHEN NOT EXISTS (SELECT 1 FROM quiz_answers a JOIN quiz_attempts t ON t.id=a.attempt_id "
        "JOIN operations o ON o.operation_id=a.operation_id "
        "WHERE a.attempt_id=NEW.attempt_id AND a.question_id=NEW.question_id "
        "AND a.draft_revision=NEW.draft_revision AND a.answer=NEW.answer "
        "AND a.self_score IS NEW.self_score AND a.saved_at=NEW.saved_at AND a.state=NEW.state "
        "AND a.operation_id=NEW.operation_id AND t.status='IN_PROGRESS' "
        "AND o.kind='QUIZ_ANSWER_DRAFT' AND o.status='PENDING') "
        "BEGIN SELECT RAISE(ABORT, 'Answer receipt evidence mismatch'); END"
    )


def downgrade() -> None:
    """Routine downgrade cannot remove acknowledged history."""
    raise RuntimeError("Downgrade is disabled; preserve quiz history and answer receipts")

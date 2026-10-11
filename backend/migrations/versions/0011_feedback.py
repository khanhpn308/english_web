"""Add advisory feedback history without modifying learning or operation history."""

import sqlalchemy as sa
from alembic import op

revision: str = "0011_feedback"
down_revision: str | None = "0010_quiz_answer_receipts"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # Source: https://alembic.sqlalchemy.org/en/latest/ops.html#alembic.operations.Operations.create_table
    op.create_table(
        "writing_feedback",
        sa.Column("feedback_id", sa.String(64), primary_key=True),
        sa.Column("attempt_id", sa.String(64), nullable=False),
        sa.Column("question_id", sa.String(64), nullable=False),
        sa.Column("answer_revision", sa.Integer(), nullable=False),
        sa.Column("rubric_version", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("summary_vi", sa.Text()),
        sa.Column("criteria", sa.Text()),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column("prompt_version", sa.String(64), nullable=False),
        sa.Column("error_category", sa.String(64)),
        sa.Column("operation_id", sa.String(64), nullable=False, unique=True),
        sa.Column("retry_of_operation_id", sa.String(64), unique=True),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("updated_at", sa.String(32), nullable=False),
        sa.ForeignKeyConstraint(
            ["attempt_id", "question_id"],
            ["quiz_questions.attempt_id", "quiz_questions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["operation_id"], ["operations.operation_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["retry_of_operation_id"],
            ["writing_feedback.operation_id"],
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("typeof(answer_revision)='integer' AND answer_revision>=1"),
        sa.CheckConstraint("rubric_version='writing-rubric-v1'"),
        sa.CheckConstraint("prompt_version='writing-feedback-v1'"),
        sa.CheckConstraint("provider='Antigravity/Google' AND model='gemini-3.8-flash-high'"),
        sa.CheckConstraint(
            "(status='REQUESTED' AND summary_vi IS NULL AND criteria IS NULL "
            "AND error_category IS NULL) OR (status='FAILED' AND summary_vi IS NULL "
            "AND criteria IS NULL AND error_category IS NOT NULL) OR "
            "(status='VALIDATED' AND summary_vi IS NOT NULL AND length(summary_vi) BETWEEN 1 "
            "AND 4096 AND criteria IS NOT NULL AND json_valid(criteria) "
            "AND json_array_length(criteria)=3 AND error_category IS NULL)"
        ),
    )
    op.create_index(
        "ix_feedback_history", "writing_feedback", ["question_id", "created_at", "feedback_id"]
    )
    op.execute(
        "CREATE TRIGGER feedback_admission BEFORE INSERT ON writing_feedback WHEN "
        "NEW.status!='REQUESTED' OR EXISTS (SELECT 1 FROM writing_feedback "
        "WHERE feedback_id=NEW.feedback_id OR operation_id=NEW.operation_id) OR NOT EXISTS "
        "(SELECT 1 FROM quiz_answers a JOIN quiz_questions q ON q.id=a.question_id "
        "JOIN operations o ON o.operation_id=NEW.operation_id WHERE q.type='WRITING' "
        "AND a.attempt_id=NEW.attempt_id AND a.question_id=NEW.question_id "
        "AND a.draft_revision=NEW.answer_revision AND o.kind='WRITING_FEEDBACK' "
        "AND o.status='PENDING') BEGIN SELECT RAISE(ABORT, 'Invalid feedback admission'); END"
    )
    op.execute(
        "CREATE TRIGGER feedback_terminal BEFORE UPDATE ON writing_feedback WHEN "
        "OLD.status!='REQUESTED' OR NEW.status NOT IN ('VALIDATED','FAILED') OR "
        "NEW.feedback_id!=OLD.feedback_id OR NEW.attempt_id!=OLD.attempt_id OR "
        "NEW.question_id!=OLD.question_id OR NEW.answer_revision!=OLD.answer_revision OR "
        "NEW.rubric_version!=OLD.rubric_version OR NEW.operation_id!=OLD.operation_id OR "
        "NEW.retry_of_operation_id IS NOT OLD.retry_of_operation_id OR "
        "NEW.provider!=OLD.provider OR NEW.model!=OLD.model OR "
        "NEW.prompt_version!=OLD.prompt_version OR NEW.created_at!=OLD.created_at OR "
        "NEW.updated_at<OLD.updated_at BEGIN SELECT RAISE(ABORT, 'Immutable feedback'); END"
    )
    op.execute(
        "CREATE TRIGGER feedback_no_delete BEFORE DELETE ON writing_feedback "
        "BEGIN SELECT RAISE(ABORT, 'Preserve feedback history'); END"
    )


def downgrade() -> None:
    raise RuntimeError("Downgrade disabled; preserve feedback and learning history")

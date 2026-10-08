"""Immutable quiz content and durable draft/terminal state (T034)."""

import sqlalchemy as sa
from alembic import op

revision: str = "0008_quiz"
down_revision: str | None = "0007_source_journal"
branch_labels: str | None = None
depends_on: str | None = None


def _revision(column: str, name: str, minimum: int = 0) -> sa.CheckConstraint:
    return sa.CheckConstraint(f"typeof({column})='integer' AND {column}>={minimum}", name=name)


def _time(column: str, name: str) -> sa.CheckConstraint:
    return sa.CheckConstraint(
        f"typeof({column})='text' AND length({column})=27 "
        f"AND {column} GLOB '????-??-??T??:??:??.??????Z' AND julianday({column}) IS NOT NULL",
        name=name,
    )


def _guard(name: str, event: str, table: str, condition: str, message: str) -> None:
    # All arguments are migration-owned literals, never application input.
    op.execute(
        f"CREATE TRIGGER {name} BEFORE {event} ON {table} "
        f"WHEN {condition} BEGIN SELECT RAISE(ABORT, '{message}'); END"
    )


def upgrade() -> None:
    op.create_table(
        "quiz_attempts",
        sa.Column("id", sa.String(64), primary_key=True, nullable=False),
        sa.Column("note_date", sa.String(10), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="IN_PROGRESS"),
        sa.Column("snapshot_revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("question_count", sa.Integer(), nullable=False),
        sa.Column("snapshot_digest", sa.String(64), nullable=False),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("submission_revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("result_payload", sa.Text(), nullable=True),
        sa.Column("result_digest", sa.String(64), nullable=True),
        sa.Column("submitted_at", sa.String(32), nullable=True),
        sa.Column("submission_operation_id", sa.String(64), nullable=True),
        sa.ForeignKeyConstraint(
            ["submission_operation_id"], ["operations.operation_id"], ondelete="RESTRICT"
        ),
        sa.CheckConstraint("length(id) BETWEEN 1 AND 64", name="ck_quiz_attempt_id"),
        sa.CheckConstraint(
            "length(note_date)=10 AND note_date GLOB '????-??-??' "
            "AND date(note_date,'+0 days') IS NOT NULL "
            "AND date(note_date,'+0 days')=note_date",
            name="ck_quiz_note_date",
        ),
        sa.CheckConstraint("status IN ('IN_PROGRESS','SUBMITTED')", name="ck_quiz_status"),
        _revision("snapshot_revision", "ck_quiz_snapshot_revision", 1),
        sa.CheckConstraint(
            "typeof(question_count)='integer' AND question_count BETWEEN 5 AND 30",
            name="ck_quiz_count",
        ),
        sa.CheckConstraint(
            "length(snapshot_digest)=64 AND snapshot_digest NOT GLOB '*[^0-9a-f]*'",
            name="ck_quiz_digest",
        ),
        _revision("submission_revision", "ck_quiz_submission_revision"),
        _time("created_at", "ck_quiz_created_at"),
        sa.CheckConstraint(
            "(status='IN_PROGRESS' AND result_payload IS NULL AND result_digest IS NULL "
            "AND submitted_at IS NULL "
            "AND submission_operation_id IS NULL) OR "
            "(status='SUBMITTED' AND result_payload IS NOT NULL AND json_valid(result_payload) "
            "AND result_digest IS NOT NULL AND length(result_digest)=64 "
            "AND result_digest NOT GLOB '*[^0-9a-f]*' "
            "AND submitted_at IS NOT NULL AND length(submitted_at)=27 "
            "AND submitted_at GLOB '????-??-??T??:??:??.??????Z' "
            "AND julianday(submitted_at) IS NOT NULL AND submission_operation_id IS NOT NULL "
            "AND coalesce(json_extract(result_payload,'$.status'),'')='SUBMITTED' "
            "AND coalesce(json_extract(result_payload,'$.attemptId'),'')=id "
            "AND coalesce(json_extract(result_payload,'$.submissionRevision'),-1)"
            "=submission_revision)",
            name="ck_quiz_terminal_result",
        ),
    )
    op.create_table(
        "quiz_questions",
        sa.Column("id", sa.String(64), primary_key=True, nullable=False),
        sa.Column("attempt_id", sa.String(64), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(16), nullable=False),
        # Opaque historical reference, intentionally no live-form/source FK. Restore
        # must survive deleted sources/forms; T031 checks live eligibility for reviews.
        sa.Column("word_form_id", sa.String(64), nullable=False),
        sa.Column("snapshot_payload", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["attempt_id"], ["quiz_attempts.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("attempt_id", "id", name="uq_quiz_question_membership"),
        sa.UniqueConstraint("attempt_id", "position", name="uq_quiz_question_position"),
        sa.UniqueConstraint("attempt_id", "type", "word_form_id", name="uq_quiz_question_form"),
        sa.CheckConstraint(
            "length(id) BETWEEN 1 AND 64 AND length(word_form_id) BETWEEN 1 AND 64",
            name="ck_quiz_question_ids",
        ),
        sa.CheckConstraint("type IN ('MCQ','CLOZE','WRITING')", name="ck_quiz_question_type"),
        sa.CheckConstraint(
            "typeof(position)='integer' AND position BETWEEN 0 AND 29",
            name="ck_quiz_question_position",
        ),
        sa.CheckConstraint(
            "json_valid(snapshot_payload) "
            "AND coalesce(json_extract(snapshot_payload,'$.id'),'')=id "
            "AND coalesce(json_extract(snapshot_payload,'$.type'),'')=type "
            "AND coalesce(json_extract(snapshot_payload,'$.wordFormId'),'')=word_form_id "
            "AND coalesce(json_type(snapshot_payload,'$.promptEn'),'')='text' "
            "AND length(json_extract(snapshot_payload,'$.promptEn')) BETWEEN 1 AND 4096",
            name="ck_quiz_snapshot_identity",
        ),
        sa.CheckConstraint(
            "(type='MCQ' AND coalesce(json_type(snapshot_payload,'$.options'),'')='array' "
            "AND json_array_length(snapshot_payload,'$.options') BETWEEN 1 AND 100 "
            "AND coalesce(json_type(snapshot_payload,'$.correctOptionId'),'')='text' "
            "AND coalesce(json_type(snapshot_payload,'$.explanationVi'),'')='text') OR "
            "(type='CLOZE' AND coalesce(json_extract(snapshot_payload,'$.answerPolicyVersion'),'')"
            "='cloze-answer-v1' AND coalesce(json_type(snapshot_payload,'$.acceptedAnswers'),'')"
            "='array' AND json_array_length(snapshot_payload,'$.acceptedAnswers') "
            "BETWEEN 1 AND 100 "
            "AND coalesce(json_type(snapshot_payload,'$.explanationVi'),'')='text') OR "
            "(type='WRITING' AND coalesce(json_extract(snapshot_payload,'$.rubricVersion'),'')"
            "='writing-rubric-v1' "
            "AND coalesce(json_type(snapshot_payload,'$.targetLemma'),'')='text' "
            "AND coalesce(json_type(snapshot_payload,'$.rubric.descriptors'),'')='array' "
            "AND json_array_length(snapshot_payload,'$.rubric.descriptors')=5)",
            name="ck_quiz_snapshot_type_data",
        ),
    )
    op.create_table(
        "quiz_answers",
        sa.Column("attempt_id", sa.String(64), nullable=False),
        sa.Column("question_id", sa.String(64), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("self_score", sa.Integer(), nullable=True),
        sa.Column("draft_revision", sa.Integer(), nullable=False),
        sa.Column("saved_at", sa.String(32), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("operation_id", sa.String(64), nullable=False),
        sa.PrimaryKeyConstraint("attempt_id", "question_id", name="pk_quiz_answer"),
        sa.ForeignKeyConstraint(
            ["attempt_id", "question_id"], ["quiz_questions.attempt_id", "quiz_questions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["operation_id"], ["operations.operation_id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("operation_id", name="uq_quiz_answer_operation"),
        sa.CheckConstraint(
            "typeof(answer)='text' AND length(answer)<=4096", name="ck_quiz_answer_content"
        ),
        sa.CheckConstraint(
            "self_score IS NULL OR (typeof(self_score)='integer' AND self_score BETWEEN 0 AND 4)",
            name="ck_quiz_self_score",
        ),
        _revision("draft_revision", "ck_quiz_draft_revision", 1),
        _time("saved_at", "ck_quiz_answer_saved_at"),
        sa.CheckConstraint("state IN ('BLANK','DRAFT','SCORED')", name="ck_quiz_answer_state"),
        sa.CheckConstraint(
            "(self_score IS NULL AND state IN ('BLANK','DRAFT')) OR "
            "(self_score IS NOT NULL AND state='SCORED')",
            name="ck_quiz_answer_score_state",
        ),
    )
    _guard(
        "quiz_initial_state",
        "INSERT",
        "quiz_attempts",
        "NEW.status!='IN_PROGRESS' OR NEW.submission_revision!=0",
        "Quiz must start in progress at revision zero",
    )
    _guard(
        "quiz_attempt_no_replace",
        "INSERT",
        "quiz_attempts",
        "EXISTS (SELECT 1 FROM quiz_attempts WHERE id=NEW.id)",
        "Preserve quiz attempt",
    )
    _guard("quiz_attempt_no_delete", "DELETE", "quiz_attempts", "1", "Preserve quiz history")
    _guard(
        "quiz_attempt_immutable",
        "UPDATE",
        "quiz_attempts",
        "NEW.id!=OLD.id OR NEW.note_date!=OLD.note_date OR "
        "NEW.snapshot_revision!=OLD.snapshot_revision OR NEW.question_count!=OLD.question_count "
        "OR NEW.snapshot_digest!=OLD.snapshot_digest OR NEW.created_at!=OLD.created_at "
        "OR OLD.status='SUBMITTED'",
        "Immutable quiz snapshot or terminal state",
    )
    _guard(
        "quiz_aggregate_revision",
        "UPDATE OF submission_revision",
        "quiz_attempts",
        "NEW.submission_revision!=OLD.submission_revision+1 OR NEW.submission_revision!="
        "(SELECT coalesce(sum(draft_revision),0) FROM quiz_answers WHERE attempt_id=OLD.id)",
        "Invalid aggregate draft revision",
    )
    _guard(
        "quiz_submission_complete",
        "UPDATE OF status",
        "quiz_attempts",
        "NEW.status!='SUBMITTED' OR (SELECT count(*) FROM quiz_questions WHERE attempt_id=OLD.id)"
        "!=OLD.question_count",
        "Invalid quiz terminal transition",
    )
    _guard("quiz_question_no_update", "UPDATE", "quiz_questions", "1", "Immutable quiz question")
    _guard("quiz_question_no_delete", "DELETE", "quiz_questions", "1", "Preserve quiz snapshot")
    _guard(
        "quiz_question_admission",
        "INSERT",
        "quiz_questions",
        "EXISTS (SELECT 1 FROM quiz_questions WHERE id=NEW.id) OR "
        "NOT EXISTS (SELECT 1 FROM quiz_attempts WHERE id=NEW.attempt_id "
        "AND status='IN_PROGRESS' AND submission_revision=0 AND question_count>NEW.position) OR "
        "NEW.position!=(SELECT count(*) FROM quiz_questions WHERE attempt_id=NEW.attempt_id) OR "
        "(SELECT count(*) FROM quiz_questions "
        "WHERE attempt_id=NEW.attempt_id AND type=NEW.type)>=20",
        "Invalid or sealed question ordering",
    )
    _guard(
        "quiz_answer_no_delete", "DELETE", "quiz_answers", "1", "Preserve quiz answer revisions"
    )
    _guard(
        "quiz_answer_initial_revision",
        "INSERT",
        "quiz_answers",
        "NEW.draft_revision!=1 OR EXISTS (SELECT 1 FROM quiz_answers WHERE "
        "(attempt_id=NEW.attempt_id AND question_id=NEW.question_id) "
        "OR operation_id=NEW.operation_id)",
        "Invalid initial answer revision or replacement",
    )
    _guard(
        "quiz_answer_next_revision",
        "UPDATE",
        "quiz_answers",
        "NEW.attempt_id!=OLD.attempt_id OR NEW.question_id!=OLD.question_id "
        "OR NEW.draft_revision!=OLD.draft_revision+1 OR NEW.operation_id=OLD.operation_id "
        "OR NEW.saved_at<OLD.saved_at",
        "Invalid next answer revision",
    )
    for event in ("INSERT", "UPDATE"):
        _guard(
            f"quiz_answer_writable_{event.lower()}",
            event,
            "quiz_answers",
            "NOT EXISTS (SELECT 1 FROM quiz_attempts a JOIN quiz_questions q ON q.attempt_id=a.id "
            "WHERE a.id=NEW.attempt_id AND q.id=NEW.question_id AND a.status='IN_PROGRESS' "
            "AND (SELECT count(*) FROM quiz_questions WHERE attempt_id=a.id)=a.question_count "
            "AND (q.type='WRITING' OR NEW.self_score IS NULL) "
            "AND (q.type!='MCQ' OR NEW.answer='' OR EXISTS "
            "(SELECT 1 FROM json_each(q.snapshot_payload,'$.options') o "
            "WHERE json_extract(o.value,'$.id')=NEW.answer)))",
            "Quiz answer is not writable or mismatched",
        )
        op.execute(
            f"CREATE TRIGGER quiz_answer_aggregate_{event.lower()} AFTER {event} ON quiz_answers "
            "BEGIN UPDATE quiz_attempts SET submission_revision=submission_revision+1 "
            "WHERE id=NEW.attempt_id; END"
        )


def downgrade() -> None:
    """History cannot be removed by a routine downgrade, matching T005/T019/T031."""
    raise RuntimeError("Downgrade is disabled; preserve quiz history")

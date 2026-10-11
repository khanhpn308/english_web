"""Record prospective transaction boundaries without rewriting H1 facts."""

from alembic import op

revision: str = "0013_study_history_commits"
down_revision: str | None = "0012_study_history"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE study_history_commits (
            id INTEGER PRIMARY KEY CHECK(id>0),
            kind TEXT NOT NULL CHECK(kind IN ('OPENING','COMMIT')),
            first_seq INTEGER NOT NULL CHECK(first_seq>0),
            last_seq INTEGER NOT NULL CHECK(last_seq>=first_seq-1),
            first_quiz_seq INTEGER NOT NULL CHECK(first_quiz_seq>0),
            last_quiz_seq INTEGER NOT NULL CHECK(last_quiz_seq>=first_quiz_seq-1),
            observed_at TEXT NOT NULL CHECK(length(observed_at)=27 AND
                observed_at GLOB '????-??-??T??:??:??.??????Z' AND julianday(observed_at) IS NOT NULL),
            effective_at TEXT NOT NULL CHECK(length(effective_at)=27 AND
                effective_at GLOB '????-??-??T??:??:??.??????Z' AND julianday(effective_at) IS NOT NULL
                AND effective_at>=observed_at),
            gap_since TEXT CHECK(gap_since IS NULL OR (length(gap_since)=27 AND
                gap_since GLOB '????-??-??T??:??:??.??????Z' AND julianday(gap_since) IS NOT NULL
                AND gap_since<=effective_at)),
            CHECK((id=1 AND kind='OPENING' AND first_seq=1 AND first_quiz_seq=1
                AND last_quiz_seq=0 AND gap_since IS NULL) OR (id>1 AND kind='COMMIT'))
        )
    """)
    op.execute("CREATE INDEX ix_study_history_commits_time ON study_history_commits(effective_at,id)")
    op.execute("CREATE INDEX ix_study_history_commits_facts ON study_history_commits(last_seq)")
    op.execute("CREATE INDEX ix_study_history_commits_quizzes ON study_history_commits(last_quiz_seq)")
    op.execute("""
        CREATE TABLE study_history_quiz_submissions (
            seq INTEGER PRIMARY KEY CHECK(seq>0),
            attempt_id TEXT NOT NULL UNIQUE,
            operation_id TEXT NOT NULL,
            submitted_at TEXT NOT NULL CHECK(length(submitted_at)=27 AND
                submitted_at GLOB '????-??-??T??:??:??.??????Z' AND julianday(submitted_at) IS NOT NULL)
        )
    """)
    for table in ("study_history_commits", "study_history_quiz_submissions"):
        for action in ("UPDATE", "DELETE"):
            op.execute(f"CREATE TRIGGER {table}_no_{action.lower()} BEFORE {action} ON {table} "
                       "BEGIN SELECT RAISE(ABORT,'Append-only study evidence'); END")
    op.execute("""
        CREATE TRIGGER study_history_quiz_submissions_order BEFORE INSERT
        ON study_history_quiz_submissions
        WHEN NEW.seq!=coalesce((SELECT max(seq) FROM study_history_quiz_submissions),0)+1
            OR EXISTS (SELECT 1 FROM study_history_quiz_submissions WHERE attempt_id=NEW.attempt_id)
        BEGIN SELECT RAISE(ABORT,'Preserve terminal quiz evidence'); END
    """)
    op.execute("""
        CREATE TRIGGER study_history_commits_order BEFORE INSERT ON study_history_commits
        WHEN NEW.id!=coalesce((SELECT max(id) FROM study_history_commits),0)+1
            OR NEW.first_seq!=coalesce((SELECT last_seq FROM study_history_commits
                ORDER BY id DESC LIMIT 1),0)+1
            OR NEW.first_quiz_seq!=coalesce((SELECT last_quiz_seq FROM study_history_commits
                ORDER BY id DESC LIMIT 1),0)+1
            OR NEW.effective_at<coalesce((SELECT effective_at FROM study_history_commits
                ORDER BY id DESC LIMIT 1),'')
            OR NEW.last_seq!=coalesce((SELECT max(seq) FROM study_history),0)
            OR NEW.last_quiz_seq!=coalesce((SELECT max(seq) FROM study_history_quiz_submissions),0)
            OR (NEW.gap_since IS NOT NULL AND NEW.gap_since!=coalesce(
                (SELECT effective_at FROM study_history_commits ORDER BY id DESC LIMIT 1),''))
        BEGIN SELECT RAISE(ABORT,'Preserve transaction evidence order'); END
    """)
    # This is a new checkpoint of retained SQLite state, not a claim about old commits.
    op.execute("""
        INSERT INTO study_history_commits
            (id,kind,first_seq,last_seq,first_quiz_seq,last_quiz_seq,observed_at,effective_at)
        SELECT 1,'OPENING',1,next_seq-1,1,0,observed_at,timeline_at FROM study_history_clock
    """)
    for action, condition in (
        ("INSERT", "NEW.status='SUBMITTED'"),
        ("UPDATE", "NEW.status='SUBMITTED' AND OLD.status!='SUBMITTED'"),
    ):
        op.execute(f"CREATE TRIGGER study_quiz_terminal_{action.lower()} AFTER {action} "
                   f"ON quiz_attempts WHEN {condition} BEGIN "
                   "INSERT INTO study_history_quiz_submissions "
                   "(seq,attempt_id,operation_id,submitted_at) SELECT "
                   "coalesce(max(seq),0)+1,NEW.id,NEW.submission_operation_id,NEW.submitted_at "
                   "FROM study_history_quiz_submissions; END")


def downgrade() -> None:
    raise RuntimeError("Downgrade disabled; preserve committed study evidence")

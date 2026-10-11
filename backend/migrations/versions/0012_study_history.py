"""Append observed eligibility facts without claiming pre-installation continuity."""

from alembic import op

revision: str = "0012_study_history"
down_revision: str | None = "0011_feedback"
branch_labels: str | None = None
depends_on: str | None = None


def _append(
    kind: str, reason: str, entity: str, *, source: str = "NULL", form: str = "NULL",
    card: str = "NULL", operation: str = "NULL", event: str = "NULL",
    previous: str = "NULL", resulting: str = "NULL", since: str = "NULL",
) -> str:
    return (
        "INSERT INTO study_history (seq,kind,reason,entity_key,source_id,word_form_id,card_id,"
        "operation_id,review_event_id,previous_state,resulting_state,uncertain_since,"
        "observed_at,timeline_at) SELECT "
        f"next_seq,'{kind}',{reason},{entity},{source},{form},{card},{operation},{event},"
        f"{previous},{resulting},{since},observed_at,timeline_at FROM study_history_clock;"
    )


def _source(row: str) -> str:
    return f"json_object('status',{row}.status,'revision',{row}.revision,'hash',{row}.content_hash)"


def _link(row: str, present: int) -> str:
    return f"json_object('present',{present},'note_date',{row}.note_date)"


def _card(row: str) -> str:
    return (
        f"json_object('box',{row}.box,'due_at',{row}.due_at,"
        f"'queue_revision',{row}.queue_revision)"
    )


def upgrade() -> None:
    # No foreign keys to live projections: source deletion must retain all evidence.
    op.execute("""
        CREATE TABLE study_history (
            seq INTEGER PRIMARY KEY CHECK(seq>0),
            kind TEXT NOT NULL CHECK(kind IN ('SOURCE','LINK','CARD','REVIEW','JOURNAL','COVERAGE')),
            reason TEXT NOT NULL CHECK(reason IN
                ('OPENING','INSERT','UPDATE','DELETE','RESET','SCHEDULE','REVIEW',
                 'JOURNAL','STARTUP','SHUTDOWN','SYNC_STARTED','SYNC_FINISHED','SYNC_FAILED')),
            entity_key TEXT NOT NULL CHECK(json_valid(entity_key) AND json_type(entity_key)='array'),
            source_id TEXT,
            word_form_id TEXT,
            card_id TEXT,
            operation_id TEXT,
            review_event_id TEXT,
            previous_state TEXT CHECK(previous_state IS NULL OR
                (json_valid(previous_state) AND json_type(previous_state)='object')),
            resulting_state TEXT CHECK(resulting_state IS NULL OR
                (json_valid(resulting_state) AND json_type(resulting_state)='object')),
            uncertain_since TEXT,
            observed_at TEXT NOT NULL CHECK(length(observed_at)=27 AND
                observed_at GLOB '????-??-??T??:??:??.??????Z' AND julianday(observed_at) IS NOT NULL),
            timeline_at TEXT NOT NULL CHECK(length(timeline_at)=27 AND
                timeline_at GLOB '????-??-??T??:??:??.??????Z' AND julianday(timeline_at) IS NOT NULL
                AND timeline_at>=observed_at),
            CHECK(uncertain_since IS NULL OR (length(uncertain_since)=27 AND
                uncertain_since GLOB '????-??-??T??:??:??.??????Z' AND
                julianday(uncertain_since) IS NOT NULL AND uncertain_since<=timeline_at)),
            CHECK(coalesce((kind='SOURCE' AND source_id IS NOT NULL) OR
                (kind='LINK' AND source_id IS NOT NULL AND word_form_id IS NOT NULL) OR
                (kind='CARD' AND card_id IS NOT NULL AND word_form_id IS NOT NULL) OR
                (kind='REVIEW' AND card_id IS NOT NULL AND review_event_id IS NOT NULL
                    AND operation_id IS NOT NULL) OR
                (kind='JOURNAL' AND source_id IS NOT NULL AND operation_id IS NOT NULL) OR
                (kind='COVERAGE' AND json_extract(resulting_state,'$.status')='UNKNOWN'),0)),
            CHECK(kind NOT IN ('LINK','CARD','JOURNAL','COVERAGE') OR resulting_state IS NOT NULL),
            CHECK(kind!='SOURCE' OR resulting_state IS NOT NULL OR reason='DELETE'),
            CHECK(kind!='REVIEW' OR (previous_state IS NULL AND resulting_state IS NULL)),
            CHECK(kind!='LINK' OR coalesce(json_extract(resulting_state,'$.present') IN (0,1),0)),
            CHECK(kind!='JOURNAL' OR coalesce(json_extract(resulting_state,'$.state') IN
                ('PREPARED','SOURCE_REPLACED','COMMITTED','ABORTED','DEGRADED'),0))
        )
    """)
    op.execute("CREATE INDEX ix_study_history_entity ON study_history(kind,entity_key,seq)")
    op.execute("CREATE INDEX ix_study_history_time ON study_history(timeline_at,seq)")
    op.execute("CREATE INDEX ix_study_history_source ON study_history(source_id,timeline_at,seq)")
    op.execute("CREATE INDEX ix_study_history_card ON study_history(card_id,timeline_at,seq)")
    op.execute("CREATE INDEX ix_study_history_form ON study_history(word_form_id,timeline_at,seq)")
    op.execute("CREATE INDEX ix_study_history_review_card ON study_history(card_id,seq) WHERE kind='REVIEW'")
    op.execute("CREATE UNIQUE INDEX uq_study_history_review ON study_history(review_event_id) "
               "WHERE kind='REVIEW'")
    op.execute("CREATE UNIQUE INDEX uq_study_history_sync_observation "
               "ON study_history(operation_id,reason) WHERE kind='COVERAGE' AND operation_id IS NOT NULL")
    # Keep raw wall time as evidence; a clock rollback cannot reorder the replay timeline.
    op.execute("""
        CREATE VIEW study_history_clock AS SELECT
            (SELECT coalesce(max(seq),0)+1 FROM study_history) AS next_seq,
            strftime('%Y-%m-%dT%H:%M:%f','now') || '000Z' AS observed_at,
            max(strftime('%Y-%m-%dT%H:%M:%f','now') || '000Z',
                coalesce((SELECT timeline_at FROM study_history ORDER BY seq DESC LIMIT 1),''))
                AS timeline_at
    """)
    for action in ("UPDATE", "DELETE"):
        op.execute(f"CREATE TRIGGER study_history_no_{action.lower()} BEFORE {action} "
                   "ON study_history BEGIN SELECT RAISE(ABORT,'Append-only study history'); END")
    # Writers supply next_seq: BEFORE INSERT must not depend on SQLite's undefined NEW.rowid.
    # Source: https://www.sqlite.org/lang_createtrigger.html#cautions_on_the_use_of_before_triggers
    op.execute("""
        CREATE TRIGGER study_history_order BEFORE INSERT ON study_history
        WHEN NEW.seq<=coalesce((SELECT max(seq) FROM study_history),0)
            OR NEW.timeline_at<coalesce((SELECT timeline_at FROM study_history
                ORDER BY seq DESC LIMIT 1),'')
            OR (NEW.kind='REVIEW' AND EXISTS (SELECT 1 FROM study_history
                WHERE kind='REVIEW' AND review_event_id=NEW.review_event_id))
            OR (NEW.kind='COVERAGE' AND NEW.operation_id IS NOT NULL AND EXISTS
                (SELECT 1 FROM study_history WHERE kind='COVERAGE'
                    AND operation_id=NEW.operation_id AND reason=NEW.reason))
        BEGIN SELECT RAISE(ABORT,'Preserve study history order'); END
    """)

    op.execute(_append(
        "COVERAGE", "'OPENING'", "json_array('coverage')",
        resulting="json_object('status','UNKNOWN','detail','NO_CONTINUOUS_SOURCE_OBSERVATION')",
    ))
    for table, kind, entity, ids, state in (
        ("source_files", "SOURCE", "json_array(s.id)", "s.id,NULL,NULL", _source("s")),
        ("word_form_sources", "LINK", "json_array(s.word_form_id,s.source_id)",
         "s.source_id,s.word_form_id,NULL", _link("s", 1)),
        ("review_cards", "CARD", "json_array(s.card_id)", "NULL,s.word_form_id,s.card_id",
         _card("s")),
        ("source_write_journal", "JOURNAL", "json_array(s.operation_id)",
         "s.source_id,NULL,NULL", "json_object('state',s.state)"),
    ):
        # One migration observation time, never original created_at / reviewed_at / filename time.
        batch_base: int = op.get_bind().exec_driver_sql(
            "SELECT coalesce(max(seq),0) FROM study_history"
        ).scalar_one()
        op.execute(
            "INSERT INTO study_history (seq,kind,reason,entity_key,source_id,word_form_id,card_id,"
            "operation_id,resulting_state,observed_at,timeline_at) "
            f"SELECT {batch_base}+row_number() OVER (ORDER BY {entity}),'{kind}','OPENING',{entity},{ids},"
            f"{'s.operation_id' if kind == 'JOURNAL' else 'NULL'},{state},h.observed_at,h.timeline_at "
            f"FROM {table} s CROSS JOIN study_history h WHERE h.kind='COVERAGE' AND h.reason='OPENING' "
            f"ORDER BY {entity}"
        )

    for action, row, previous, resulting in (
        ("INSERT", "NEW", "NULL", _source("NEW")),
        ("UPDATE", "NEW", _source("OLD"), _source("NEW")),
        ("DELETE", "OLD", _source("OLD"), "NULL"),
    ):
        condition = (
            "WHEN NEW.status IS NOT OLD.status OR NEW.revision IS NOT OLD.revision "
            "OR NEW.content_hash IS NOT OLD.content_hash" if action == "UPDATE" else ""
        )
        since = ("(SELECT timeline_at FROM study_history WHERE kind='SOURCE' "
                 f"AND entity_key=json_array({row}.id) ORDER BY seq DESC LIMIT 1)")
        op.execute(f"CREATE TRIGGER study_source_{action.lower()} AFTER {action} ON source_files "
                   f"{condition} BEGIN " + _append(
                       "SOURCE", f"'{action}'", f"json_array({row}.id)", source=f"{row}.id",
                       previous=previous, resulting=resulting, since=since,
                   ) + " END")
    op.execute("CREATE TRIGGER study_source_identity BEFORE UPDATE OF id ON source_files "
               "WHEN NEW.id!=OLD.id BEGIN SELECT RAISE(ABORT,'Stable source identity'); END")
    op.execute("CREATE TRIGGER study_source_no_replace BEFORE INSERT ON source_files "
               "WHEN EXISTS (SELECT 1 FROM source_files WHERE id=NEW.id OR relative_path=NEW.relative_path) "
               "BEGIN SELECT RAISE(ABORT,'Preserve source identity'); END")
    op.execute("CREATE TRIGGER study_source_path_no_replace BEFORE UPDATE OF relative_path ON source_files "
               "WHEN EXISTS (SELECT 1 FROM source_files WHERE relative_path=NEW.relative_path AND id!=OLD.id) "
               "BEGIN SELECT RAISE(ABORT,'Preserve source identity'); END")

    for action, row, previous, resulting in (
        ("INSERT", "NEW", "(SELECT resulting_state FROM study_history WHERE kind='LINK' "
         "AND entity_key=json_array(NEW.word_form_id,NEW.source_id) ORDER BY seq DESC LIMIT 1)",
         _link("NEW", 1)),
        ("UPDATE", "NEW", _link("OLD", 1), _link("NEW", 1)),
        ("DELETE", "OLD", _link("OLD", 1), _link("OLD", 0)),
    ):
        condition = "WHEN NEW.note_date IS NOT OLD.note_date" if action == "UPDATE" else ""
        if action == "INSERT":
            condition = (
                "WHEN coalesce((SELECT resulting_state FROM study_history WHERE kind='LINK' "
                "AND entity_key=json_array(NEW.word_form_id,NEW.source_id) "
                "ORDER BY seq DESC LIMIT 1),'') != " + _link("NEW", 1)
            )
        op.execute(f"CREATE TRIGGER study_link_{action.lower()} AFTER {action} ON word_form_sources "
                   f"{condition} BEGIN " + _append(
                       "LINK", f"'{action}'", f"json_array({row}.word_form_id,{row}.source_id)",
                       source=f"{row}.source_id", form=f"{row}.word_form_id",
                       previous=previous, resulting=resulting,
                   ) + " END")
    op.execute("CREATE TRIGGER study_link_identity BEFORE UPDATE OF word_form_id,source_id "
               "ON word_form_sources WHEN NEW.word_form_id!=OLD.word_form_id OR NEW.source_id!=OLD.source_id "
               "BEGIN SELECT RAISE(ABORT,'Stable source link identity'); END")

    op.execute("CREATE TRIGGER study_card_insert AFTER INSERT ON review_cards BEGIN " + _append(
        "CARD", "'INSERT'", "json_array(NEW.card_id)", form="NEW.word_form_id", card="NEW.card_id",
        resulting=_card("NEW"),
    ) + " END")
    review = (
        "(SELECT h.review_event_id FROM study_history h JOIN review_events e ON e.id=h.review_event_id "
        "WHERE h.kind='REVIEW' AND h.card_id=NEW.card_id AND e.next_box=NEW.box "
        "AND e.next_due_at=NEW.due_at AND h.seq>coalesce((SELECT seq FROM study_history "
        "WHERE kind='CARD' AND entity_key=json_array(NEW.card_id) ORDER BY seq DESC LIMIT 1),0) "
        "ORDER BY h.seq DESC LIMIT 1)"
    )
    op.execute("CREATE TRIGGER study_card_update AFTER UPDATE ON review_cards "
               "WHEN NEW.box IS NOT OLD.box OR NEW.due_at IS NOT OLD.due_at "
               "OR NEW.queue_revision IS NOT OLD.queue_revision BEGIN " + _append(
                   "CARD", "CASE WHEN NEW.box=0 AND NEW.due_at IS NULL THEN 'RESET' ELSE 'SCHEDULE' END",
                   "json_array(NEW.card_id)", form="NEW.word_form_id", card="NEW.card_id",
                   previous=_card("OLD"), resulting=_card("NEW"),
                   event=review,
                   operation=f"(SELECT operation_id FROM review_events WHERE id={review})",
               ) + " END")
    op.execute("CREATE TRIGGER study_review_insert AFTER INSERT ON review_events BEGIN " + _append(
        "REVIEW", "'REVIEW'", "json_array(NEW.id)", card="NEW.card_id",
        form="(SELECT word_form_id FROM review_cards WHERE card_id=NEW.card_id)",
        operation="NEW.operation_id", event="NEW.id",
    ) + " END")
    for action, previous in (("INSERT", "NULL"), ("UPDATE", "json_object('state',OLD.state)")):
        condition = "WHEN NEW.state IS NOT OLD.state" if action == "UPDATE" else ""
        op.execute(f"CREATE TRIGGER study_journal_{action.lower()} AFTER {action} ON source_write_journal "
                   f"{condition} BEGIN " + _append(
                       "JOURNAL", "'JOURNAL'", "json_array(NEW.operation_id)", source="NEW.source_id",
                       operation="NEW.operation_id", previous=previous,
                       resulting="json_object('state',NEW.state)",
                       since="(SELECT timeline_at FROM study_history WHERE kind='SOURCE' "
                       "AND entity_key=json_array(NEW.source_id) ORDER BY seq DESC LIMIT 1)",
                   ) + " END")


def downgrade() -> None:
    raise RuntimeError("Downgrade disabled; preserve historical study eligibility")

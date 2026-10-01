"""Storage, migration, and domain invariant tests for vocabulary schema (T019)."""

from pathlib import Path
from time import time

import pytest
from alembic.script import ScriptDirectory
from backend.app.persistence.database import Database, migration_config
from backend.app.vocabulary.models import (
    ExampleSentence,
    MeaningEn,
    MeaningVi,
    WordFormDraft,
    compute_verification_summary,
)
from backend.app.vocabulary.repository import (
    AmbiguousFamilyError,
    PreviewExpiredError,
    PreviewNotFoundError,
    PreviewOwnerMismatchError,
    SourceNotFoundError,
    VocabularyRepository,
)


@pytest.fixture
def repo(tmp_path: Path) -> VocabularyRepository:
    """Create a temporary initialized database and return the repository."""
    db = Database(tmp_path / "test_vocab.db")
    db.initialize()
    return VocabularyRepository(db.engine)


# =============================================================================
# 1. Canonical Identity and Multi-Source / Multi-Date Sharing
# =============================================================================


def test_same_identity_on_multiple_dates_reuses_canonical_form(repo: VocabularyRepository) -> None:
    """Same normalized lemma + POS + family identity must identify the same canonical form.

    Multiple dates/sources must not create duplicate canonical vocabulary forms.
    """
    family = repo.get_or_create_family(root_lemma="robust")

    # Date 1: 2026-09-29
    src1 = repo.save_source_file(
        source_id="src_20260929",
        relative_path="29-09-2026.md",
        note_date="2026-09-29",
    )
    form1 = repo.save_canonical_word_form(
        lemma="Robust",
        part_of_speech="adjective",
        family_id=family.id,
        meanings_en=[MeaningEn(text="strong and healthy")],
        meanings_vi=[MeaningVi(text="vững chắc")],
        ipa_us="/r\u0259\u02c8b\u028cst/",
        cambridge_url="https://dictionary.cambridge.org/dictionary/english/robust",
    )
    repo.link_word_form_to_source(form1.id, src1.id, "2026-09-29")

    # Date 2: 2026-09-30, same identity with different casing ("robust")
    src2 = repo.save_source_file(
        source_id="src_20260930",
        relative_path="30-09-2026.md",
        note_date="2026-09-30",
    )
    form2 = repo.save_canonical_word_form(
        lemma="robust",
        part_of_speech="ADJECTIVE",
        family_id=family.id,
    )
    repo.link_word_form_to_source(form2.id, src2.id, "2026-09-30")

    # Invariant: identical canonical ID reused
    assert form1.id == form2.id

    # Check database row count in word_forms
    with repo.engine.connect() as conn:
        count = conn.exec_driver_sql("SELECT COUNT(*) FROM word_forms").scalar()
        assert count == 1

        # Check word_form_sources has 2 links
        link_count = conn.exec_driver_sql("SELECT COUNT(*) FROM word_form_sources").scalar()
        assert link_count == 2

    # Fetch canonical form and verify it has both source references
    fetched = repo.get_word_form(form1.id)
    assert fetched is not None
    assert len(fetched.source_refs) == 2
    dates = {ref.note_date for ref in fetched.source_refs}
    assert dates == {"2026-09-29", "2026-09-30"}


def test_duplicate_source_link_is_idempotent(repo: VocabularyRepository) -> None:
    """Linking the same canonical form to the same source and date twice is idempotent."""
    family = repo.get_or_create_family(root_lemma="rely")
    src = repo.save_source_file(
        source_id="src_rely_01",
        relative_path="01-10-2026.md",
        note_date="2026-10-01",
    )
    form = repo.save_canonical_word_form(
        lemma="reliable",
        part_of_speech="ADJECTIVE",
        family_id=family.id,
    )

    repo.link_word_form_to_source(form.id, src.id, "2026-10-01")
    # Duplicate link
    repo.link_word_form_to_source(form.id, src.id, "2026-10-01")

    with repo.engine.connect() as conn:
        count = conn.exec_driver_sql(
            "SELECT COUNT(*) FROM word_form_sources WHERE word_form_id = ? AND source_id = ?",
            (form.id, src.id),
        ).scalar()
        assert count == 1


# =============================================================================
# 2. Distinct POS
# =============================================================================


def test_distinct_pos_remain_distinct_identities(repo: VocabularyRepository) -> None:
    """Distinct POS values remain distinct canonical identities even with same lemma and family."""
    family = repo.get_or_create_family(root_lemma="estimate")

    verb_form = repo.save_canonical_word_form(
        lemma="estimate",
        part_of_speech="VERB",
        family_id=family.id,
        meanings_vi=[MeaningVi(text="ước tính")],
    )
    noun_form = repo.save_canonical_word_form(
        lemma="estimate",
        part_of_speech="NOUN",
        family_id=family.id,
        meanings_vi=[MeaningVi(text="sự ước tính")],
    )

    assert verb_form.id != noun_form.id
    assert verb_form.part_of_speech == "VERB"
    assert noun_form.part_of_speech == "NOUN"

    with repo.engine.connect() as conn:
        count = conn.exec_driver_sql("SELECT COUNT(*) FROM word_forms").scalar()
        assert count == 2


# =============================================================================
# 3. Ambiguous Family Identity (Negative Probes)
# =============================================================================


def test_ambiguous_family_identity_is_rejected_fail_closed(repo: VocabularyRepository) -> None:
    """Ambiguous or missing family identity must not be silently guessed or merged."""
    # Empty string
    with pytest.raises(AmbiguousFamilyError, match="Family identity is required"):
        repo.save_canonical_word_form(
            lemma="ambiguous",
            part_of_speech="ADJECTIVE",
            family_id="",
        )

    # Non-existent family ID
    with pytest.raises(AmbiguousFamilyError, match="does not exist"):
        repo.save_canonical_word_form(
            lemma="ambiguous",
            part_of_speech="ADJECTIVE",
            family_id="family_nonexistent_xyz",
        )

    # In get_or_create_family, empty root_lemma is rejected
    with pytest.raises(AmbiguousFamilyError, match="Root lemma cannot be empty"):
        repo.get_or_create_family(root_lemma="   ")


# =============================================================================
# 4. Invalid, Missing, and Deleted Source State
# =============================================================================


def test_invalid_source_state_preserves_canonical_form_and_filters_queue(
    repo: VocabularyRepository,
) -> None:
    """Invalid source state must NOT cascade-delete or corrupt canonical forms or history."""
    family = repo.get_or_create_family(root_lemma="factor")
    src = repo.save_source_file(
        source_id="src_factor",
        relative_path="05-10-2026.md",
        note_date="2026-10-05",
        status="VALID",
    )
    form = repo.save_canonical_word_form(
        lemma="factor",
        part_of_speech="NOUN",
        family_id=family.id,
    )
    repo.link_word_form_to_source(form.id, src.id, "2026-10-05")

    # Mark source as INVALID due to parsing or syntax error
    repo.update_source_status(src.id, status="INVALID", error_code="PARSE_SYNTAX_ERROR")

    # Canonical form still exists in database
    fetched = repo.get_word_form(form.id)
    assert fetched is not None
    assert fetched.lemma == "factor"

    # Active study query for that date excludes invalid sources
    valid_forms = repo.get_forms_for_date("2026-10-05", only_valid_sources=True)
    assert len(valid_forms) == 0

    # General history/inspection query can still retrieve it
    all_forms = repo.get_forms_for_date("2026-10-05", only_valid_sources=False)
    assert len(all_forms) == 1


def test_deleted_source_does_not_cascade_delete_word_form(repo: VocabularyRepository) -> None:
    """Deleting a Markdown source file record unlinks it but never deletes canonical WordForm."""
    family = repo.get_or_create_family(root_lemma="isolate")
    src = repo.save_source_file(
        source_id="src_isolate",
        relative_path="06-10-2026.md",
        note_date="2026-10-06",
    )
    form = repo.save_canonical_word_form(
        lemma="isolation",
        part_of_speech="NOUN",
        family_id=family.id,
    )
    repo.link_word_form_to_source(form.id, src.id, "2026-10-06")

    # Delete the source
    repo.delete_source_file(src.id)

    # Source is deleted
    assert repo.get_source_file(src.id) is None

    # Canonical form is completely preserved!
    fetched = repo.get_word_form(form.id)
    assert fetched is not None
    assert fetched.id == form.id
    assert fetched.source_refs == []


# =============================================================================
# 5. Per-Field Verification and Missing Nullable Preservation
# =============================================================================


def test_per_field_missing_nullable_preserved_without_fabrication(
    repo: VocabularyRepository,
) -> None:
    """Missing or unverified values must remain distinguishable without fabricating values."""
    family = repo.get_or_create_family(root_lemma="derive")

    # Save with no IPA and no Cambridge URL
    form = repo.save_canonical_word_form(
        lemma="derivation",
        part_of_speech="NOUN",
        family_id=family.id,
        meanings_en=[MeaningEn(text="the origin of something", verification_status="VERIFIED")],
        meanings_vi=[MeaningVi(text="sự bắt nguồn", verification_status="UNVERIFIED")],
        examples=[
            ExampleSentence(
                english="The word has a French derivation.",
                vietnamese="Từ này có nguồn gốc tiếng Pháp.",
                verification_status="UNVERIFIED",
            )
        ],
        ipa_us=None,
        cambridge_url=None,
    )

    # Must preserve None, not fabricated empty strings
    assert form.ipa_us is None
    assert form.cambridge_url is None
    assert form.ipa_status == "MISSING"
    assert form.cambridge_status == "MISSING"
    assert form.verification_summary == "MISSING"

    # Re-read directly from database
    with repo.engine.connect() as conn:
        row = (
            conn.exec_driver_sql(
                "SELECT ipa_us, cambridge_url, ipa_status, cambridge_status, "
                "verification_summary FROM word_forms WHERE id = ?",
                (form.id,),
            )
            .mappings()
            .first()
        )
        assert row is not None
        assert row["ipa_us"] is None
        assert row["cambridge_url"] is None
        assert row["ipa_status"] == "MISSING"
        assert row["cambridge_status"] == "MISSING"
        assert row["verification_summary"] == "MISSING"


def test_verification_summary_logic() -> None:
    """Verification summary is VERIFIED only when all fields are verified."""
    en_unverified = [MeaningEn(text="...", verification_status="UNVERIFIED")]
    en_verified = [MeaningEn(text="...", verification_status="VERIFIED")]
    vi_verified = [MeaningVi(text="...", verification_status="VERIFIED")]
    ex_verified = [ExampleSentence(english="a", vietnamese="b", verification_status="VERIFIED")]

    # Missing IPA -> MISSING
    s1 = compute_verification_summary(
        meanings_en=en_verified,
        meanings_vi=vi_verified,
        examples=ex_verified,
        ipa_us=None,
        cambridge_url="https://cambridge.org",
        ipa_status="MISSING",
        cambridge_status="VERIFIED",
    )
    assert s1 == "MISSING"

    # Present but unverified meaning -> UNVERIFIED
    s2 = compute_verification_summary(
        meanings_en=en_unverified,
        meanings_vi=vi_verified,
        examples=ex_verified,
        ipa_us="/ipa/",
        cambridge_url="https://cambridge.org",
        ipa_status="VERIFIED",
        cambridge_status="VERIFIED",
    )
    assert s2 == "UNVERIFIED"

    # All verified -> VERIFIED
    s3 = compute_verification_summary(
        meanings_en=en_verified,
        meanings_vi=vi_verified,
        examples=ex_verified,
        ipa_us="/ipa/",
        cambridge_url="https://cambridge.org",
        ipa_status="VERIFIED",
        cambridge_status="VERIFIED",
    )
    assert s3 == "VERIFIED"


# =============================================================================
# 6. Preview Ownership and Expiration
# =============================================================================


def test_preview_owner_mismatch_fails_due_to_ownership_check(repo: VocabularyRepository) -> None:
    """Preview owned by one session cannot be accessed or saved by another session."""
    drafts = [
        WordFormDraft(
            form_id="draft_01",
            lemma="consistent",
            part_of_speech="ADJECTIVE",
            meanings_en=[MeaningEn(text="always behaving in a similar way")],
            meanings_vi=[MeaningVi(text="nhất quán")],
            examples=[
                ExampleSentence(
                    english="consistent results",
                    vietnamese="kết quả nhất quán",
                )
            ],
        )
    ]
    preview = repo.create_preview(
        lookup_id="lookup_owner_test",
        owner_session_id="session_user_alice",
        term="consistent",
        forms=drafts,
    )

    # Same owner succeeds
    fetched = repo.get_preview(preview.lookup_id, requesting_session_id="session_user_alice")
    assert fetched.lookup_id == "lookup_owner_test"

    # Different owner fails strictly on ownership check
    with pytest.raises(PreviewOwnerMismatchError, match="is not owner"):
        repo.get_preview(preview.lookup_id, requesting_session_id="session_user_mallory")

    # Saving preview with wrong owner fails and creates no forms
    with pytest.raises(PreviewOwnerMismatchError):
        repo.save_preview_to_vocabulary(
            lookup_id=preview.lookup_id,
            requesting_session_id="session_user_mallory",
            note_date="2026-09-29",
        )

    # Word forms were NOT created
    with repo.engine.connect() as conn:
        count = conn.exec_driver_sql("SELECT COUNT(*) FROM word_forms").scalar()
        assert count == 0


def test_preview_expiration_enforced(repo: VocabularyRepository) -> None:
    """Expired preview cannot be accessed or converted into vocabulary."""
    t_now = time()
    drafts = [
        WordFormDraft(
            form_id="draft_exp",
            lemma="transient",
            part_of_speech="ADJECTIVE",
            meanings_en=[],
            meanings_vi=[],
            examples=[],
        )
    ]
    preview = repo.create_preview(
        lookup_id="lookup_exp_test",
        owner_session_id="session_valid",
        term="transient",
        forms=drafts,
        created_at=t_now,
        expires_at=t_now + 100.0,
    )

    # Valid before expiration
    assert (
        repo.get_preview(
            preview.lookup_id,
            requesting_session_id="session_valid",
            now=t_now + 50.0,
        ).lookup_id
        == "lookup_exp_test"
    )

    # Fails after expiration
    with pytest.raises(PreviewExpiredError, match="has expired"):
        repo.get_preview(
            preview.lookup_id,
            requesting_session_id="session_valid",
            now=t_now + 150.0,
        )


def test_save_preview_to_vocabulary_success_and_durable_no_secrets(
    repo: VocabularyRepository,
) -> None:
    """Successful save_preview_to_vocabulary stores durable canonical data without secrets."""
    drafts = [
        WordFormDraft(
            form_id="draft_valid",
            lemma="empirical",
            part_of_speech="ADJECTIVE",
            meanings_en=[MeaningEn(text="based on observation", verification_status="VERIFIED")],
            meanings_vi=[MeaningVi(text="thực nghiệm", verification_status="VERIFIED")],
            examples=[
                ExampleSentence(
                    english="empirical evidence",
                    vietnamese="bằng chứng thực nghiệm",
                    verification_status="VERIFIED",
                )
            ],
            ipa_us="/\u026am\u02c8p\u026ar.\u026a.k\u0259l/",
            cambridge_url="https://dictionary.cambridge.org/dictionary/english/empirical",
            ipa_status="VERIFIED",
            cambridge_status="VERIFIED",
            verification_summary="VERIFIED",
        )
    ]
    preview = repo.create_preview(
        lookup_id="lookup_save_test",
        owner_session_id="session_alice",
        term="empirical",
        forms=drafts,
    )

    forms = repo.save_preview_to_vocabulary(
        lookup_id=preview.lookup_id,
        requesting_session_id="session_alice",
        note_date="2026-10-01",
    )
    assert len(forms) == 1
    saved = forms[0]
    assert saved.lemma == "empirical"
    assert saved.normalized_lemma == "empirical"
    assert saved.part_of_speech == "ADJECTIVE"
    assert saved.verification_summary == "VERIFIED"
    assert len(saved.source_refs) == 1
    assert saved.source_refs[0].note_date == "2026-10-01"

    # Preview status is now CONSUMED
    p = repo.get_preview(preview.lookup_id, requesting_session_id="session_alice")
    assert p.status == "CONSUMED"

    # Verify no session/credential data in word_forms or word_families
    with repo.engine.connect() as conn:
        wf_cols = {c[1] for c in conn.exec_driver_sql("PRAGMA table_info(word_forms)").fetchall()}
        assert "owner_session_id" not in wf_cols
        assert "password" not in wf_cols
        assert "token" not in wf_cols


# =============================================================================
# 7. Empty Source Inventory
# =============================================================================


def test_empty_source_inventory_handled_deterministically(repo: VocabularyRepository) -> None:
    """Querying forms for an unknown date or nonexistent source returns empty list without error."""
    forms_for_missing_date = repo.get_forms_for_date("1999-01-01")
    assert forms_for_missing_date == []

    forms_for_missing_src = repo.get_forms_for_source("src_nonexistent")
    assert forms_for_missing_src == []

    nonexistent_file = repo.get_source_file("src_none")
    assert nonexistent_file is None


# =============================================================================
# 8. Migration Repeated and Current-State Verification
# =============================================================================


def test_migration_0004_fresh_and_repeat_reaches_head(tmp_path: Path) -> None:
    """Migration reaches 0004_vocabulary head and repeated upgrade is idempotent."""
    db = Database(tmp_path / "fresh_migration.db")
    try:
        first = db.initialize()
        assert first.schema_revision == "0004_vocabulary"
        assert first.journal_mode == "wal"

        # Repeated initialize is a no-op that retains head
        repeat = db.initialize()
        assert repeat == first

        with db.engine.connect() as connection:
            assert connection.exec_driver_sql("SELECT version_num FROM alembic_version").all() == [
                ("0004_vocabulary",)
            ]
            tables = {
                row[0]
                for row in connection.exec_driver_sql(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).all()
            }
            assert {
                "alembic_version",
                "operations",
                "operation_keys",
                "ai_consent_state",
                "ai_consent_event",
                "word_families",
                "word_forms",
                "source_files",
                "word_form_sources",
                "lookup_previews",
            }.issubset(tables)

        assert ScriptDirectory.from_config(migration_config()).get_heads() == ["0004_vocabulary"]
    finally:
        db.close()


# =============================================================================
# 9. Additional Negative Path Probes
# =============================================================================


def test_negative_probes_raise_intended_errors(repo: VocabularyRepository) -> None:
    """Failure paths must fail for the intended domain reason, not unintended DB crashes."""
    # Preview not found
    with pytest.raises(PreviewNotFoundError, match="not found"):
        repo.get_preview("lookup_ghost")

    # Link non-existent word form
    src = repo.save_source_file(
        source_id="src_dummy",
        relative_path="dummy.md",
        note_date="2026-10-01",
    )
    with pytest.raises(ValueError, match="does not exist"):
        repo.link_word_form_to_source("wf_ghost", src.id, "2026-10-01")

    # Link non-existent source
    fam = repo.get_or_create_family(root_lemma="test")
    wf = repo.save_canonical_word_form(lemma="test", part_of_speech="NOUN", family_id=fam.id)
    with pytest.raises(SourceNotFoundError, match="does not exist"):
        repo.link_word_form_to_source(wf.id, "src_ghost", "2026-10-01")

    # Update non-existent source
    with pytest.raises(SourceNotFoundError):
        repo.update_source_status("src_ghost", "INVALID")

    # Empty lemma
    with pytest.raises(ValueError, match="Lemma cannot be empty"):
        repo.save_canonical_word_form(lemma="", part_of_speech="NOUN", family_id=fam.id)

    # Empty part of speech
    with pytest.raises(ValueError, match="Part of speech cannot be empty"):
        repo.save_canonical_word_form(lemma="valid", part_of_speech="", family_id=fam.id)

    # Missing word form by ID
    assert repo.get_word_form("wf_nonexistent") is None

    # Missing word form by identity
    assert repo.get_word_form_by_identity("ghost", "NOUN", fam.id) is None

    # Missing family
    assert repo.get_family("family_ghost") is None


def test_repository_updates_and_queries(repo: VocabularyRepository) -> None:
    """Verify repository update operations, identity lookups, and unlinking."""
    fam1 = repo.get_or_create_family(root_lemma="concept")
    # Calling get_or_create_family with same family_id
    fam1_again = repo.get_or_create_family(root_lemma="concept", family_id=fam1.id)
    assert fam1_again.id == fam1.id

    # Save and update source file
    src = repo.save_source_file(
        source_id="src_concept",
        relative_path="concept.md",
        note_date="2026-10-02",
        revision=1,
    )
    assert src.revision == 1

    # Update same source
    src_up = repo.save_source_file(
        source_id="src_concept",
        relative_path="concept.md",
        note_date="2026-10-02",
        revision=2,
    )
    assert src_up.revision == 2

    # Save canonical form
    wf = repo.save_canonical_word_form(
        lemma="concept",
        part_of_speech="NOUN",
        family_id=fam1.id,
    )
    repo.link_word_form_to_source(wf.id, src.id, "2026-10-02")

    # Lookup by identity
    by_identity = repo.get_word_form_by_identity("concept", "NOUN", fam1.id)
    assert by_identity is not None
    assert by_identity.id == wf.id

    # Lookup forms for source
    forms_for_src = repo.get_forms_for_source(src.id)
    assert len(forms_for_src) == 1
    assert forms_for_src[0].id == wf.id

    # Unlink source from form
    repo.unlink_source_from_form(wf.id, src.id)
    assert repo.get_forms_for_source(src.id) == []
    # Form itself still exists!
    assert repo.get_word_form(wf.id) is not None


def test_save_preview_with_explicit_or_invalid_family(repo: VocabularyRepository) -> None:
    """save_preview_to_vocabulary with explicit family and with invalid family."""
    fam = repo.get_or_create_family(root_lemma="explicit_fam")
    draft = WordFormDraft(
        form_id="d_01",
        lemma="explicit_fam",
        part_of_speech="NOUN",
        meanings_en=[],
        meanings_vi=[],
        examples=[],
    )
    preview = repo.create_preview(
        lookup_id="lookup_fam_test",
        owner_session_id="session_fam",
        term="explicit_fam",
        forms=[draft],
    )

    # Non-existent family ID raises AmbiguousFamilyError
    with pytest.raises(AmbiguousFamilyError, match="not found"):
        repo.save_preview_to_vocabulary(
            lookup_id=preview.lookup_id,
            requesting_session_id="session_fam",
            note_date="2026-10-02",
            family_id="family_missing_999",
        )

    # Valid explicit family succeeds
    saved = repo.save_preview_to_vocabulary(
        lookup_id=preview.lookup_id,
        requesting_session_id="session_fam",
        note_date="2026-10-02",
        family_id=fam.id,
    )
    assert len(saved) == 1
    assert saved[0].family_id == fam.id

"""Repository for canonical vocabulary, word forms, source links, and previews (T019)."""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from secrets import token_urlsafe
from typing import Any

from backend.app.vocabulary.models import (
    ExampleSentence,
    LookupPreview,
    MeaningEn,
    MeaningVi,
    SourceFile,
    SourceReference,
    SourceStatus,
    VerificationStatus,
    WordFamily,
    WordForm,
    WordFormDraft,
    compute_verification_summary,
    normalize_lemma,
)
from sqlalchemy import Connection, Engine


class VocabularyStorageError(RuntimeError):
    """Base error for vocabulary storage operations."""


class AmbiguousFamilyError(VocabularyStorageError, ValueError):
    """Raised when word family identity is missing, ambiguous, or cannot be resolved."""


class PreviewOwnerMismatchError(VocabularyStorageError, PermissionError):
    """Raised when accessing a lookup preview with a session ID other than the owner's."""


class PreviewExpiredError(VocabularyStorageError, ValueError):
    """Raised when attempting to use or inspect an expired lookup preview."""


class PreviewNotFoundError(VocabularyStorageError, KeyError):
    """Raised when a requested lookup preview does not exist."""


class SourceNotFoundError(VocabularyStorageError, KeyError):
    """Raised when a requested source file does not exist."""


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


class VocabularyRepository:
    """Synchronous SQLite repository for vocabulary domain entities and source links."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    @contextmanager
    def _borrow(self, connection: Connection) -> Iterator[Connection]:
        if connection.engine is not self.engine or not connection.in_transaction():
            raise ValueError("Caller must own an active transaction on this database engine")
        yield connection

    @contextmanager
    def _writer(self) -> Iterator[Connection]:
        with (
            self.engine.connect().execution_options(sqlite_begin_immediate=True) as connection,
            connection.begin(),
        ):
            yield connection

    @contextmanager
    def _reader(self) -> Iterator[Connection]:
        with self.engine.connect() as connection:
            yield connection

    # -------------------------------------------------------------------------
    # Word Family
    # -------------------------------------------------------------------------

    def get_or_create_family(
        self,
        root_lemma: str,
        family_id: str | None = None,
        *,
        connection: Connection | None = None,
    ) -> WordFamily:
        """Get an existing word family by root lemma or create a new deterministic one."""
        norm_root = normalize_lemma(root_lemma)
        if not norm_root:
            raise AmbiguousFamilyError("Root lemma cannot be empty for word family")

        with self._writer() if connection is None else self._borrow(connection) as conn:
            if family_id:
                row = (
                    conn.exec_driver_sql(
                        "SELECT id, root_lemma, created_at, updated_at "
                        "FROM word_families WHERE id = ?",
                        (family_id,),
                    )
                    .mappings()
                    .first()
                )
                if row:
                    return WordFamily(
                        id=row["id"],
                        root_lemma=row["root_lemma"],
                        created_at=row["created_at"],
                        updated_at=row["updated_at"],
                    )

            row = (
                conn.exec_driver_sql(
                    "SELECT id, root_lemma, created_at, updated_at "
                    "FROM word_families WHERE root_lemma = ?",
                    (norm_root,),
                )
                .mappings()
                .first()
            )
            if row:
                return WordFamily(
                    id=row["id"],
                    root_lemma=row["root_lemma"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )

            fam_id = family_id or f"family_{token_urlsafe(12)}"
            now = _now_iso()
            conn.exec_driver_sql(
                "INSERT INTO word_families (id, root_lemma, created_at, updated_at) "
                "VALUES (?, ?, ?, ?)",
                (fam_id, norm_root, now, now),
            )
            return WordFamily(
                id=fam_id,
                root_lemma=norm_root,
                created_at=now,
                updated_at=now,
            )

    def get_family(
        self, family_id: str, *, connection: Connection | None = None
    ) -> WordFamily | None:
        """Fetch word family by ID."""
        with self._reader() if connection is None else self._borrow(connection) as conn:
            row = (
                conn.exec_driver_sql(
                    "SELECT id, root_lemma, created_at, updated_at FROM word_families WHERE id = ?",
                    (family_id,),
                )
                .mappings()
                .first()
            )
            if not row:
                return None
            return WordFamily(
                id=row["id"],
                root_lemma=row["root_lemma"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

    def get_families_for_root(
        self, root_lemma: str, *, connection: Connection | None = None
    ) -> list[WordFamily]:
        """Read all matches so a caller can refuse ambiguous family identity."""
        with self._reader() if connection is None else self._borrow(connection) as conn:
            rows = (
                conn.exec_driver_sql(
                    "SELECT id,root_lemma,created_at,updated_at "
                    "FROM word_families WHERE root_lemma=?",
                    (normalize_lemma(root_lemma),),
                )
                .mappings()
                .all()
            )
            return [WordFamily(**row) for row in rows]

    # -------------------------------------------------------------------------
    # Canonical Word Forms
    # -------------------------------------------------------------------------

    def save_canonical_word_form(
        self,
        *,
        lemma: str,
        part_of_speech: str,
        family_id: str,
        meanings_en: list[MeaningEn] | None = None,
        meanings_vi: list[MeaningVi] | None = None,
        examples: list[ExampleSentence] | None = None,
        ipa_us: str | None = None,
        ipa_status: VerificationStatus | None = None,
        cambridge_url: str | None = None,
        cambridge_status: VerificationStatus | None = None,
        word_form_id: str | None = None,
        connection: Connection | None = None,
    ) -> WordForm:
        """Save a canonical word form, reusing existing row if (norm_lemma, POS, family) matches.

        Invariants enforced:
        - Canonical identity is: normalized lemma + POS + family identity.
        - Multiple dates/sources must not create duplicate canonical forms.
        - Distinct POS values remain distinct identities.
        - Ambiguous family identity must not be silently guessed or merged.
        - Nullable missing fields (ipa_us, cambridge_url) are preserved as NULL.
        """
        if not family_id or not str(family_id).strip():
            raise AmbiguousFamilyError("Family identity is required and must not be ambiguous")

        norm_lemma = normalize_lemma(lemma)
        if not norm_lemma:
            raise ValueError("Lemma cannot be empty")

        pos = part_of_speech.strip().upper()
        if not pos:
            raise ValueError("Part of speech cannot be empty")

        fam = self.get_family(family_id, connection=connection)
        if fam is None:
            raise AmbiguousFamilyError(f"Word family '{family_id}' does not exist")

        en_list = meanings_en or []
        vi_list = meanings_vi or []
        ex_list = examples or []

        if ipa_status is not None:
            eff_ipa_status = ipa_status
        else:
            eff_ipa_status = "MISSING" if ipa_us is None else "UNVERIFIED"

        if cambridge_status is not None:
            eff_cambridge_status = cambridge_status
        else:
            eff_cambridge_status = "MISSING" if cambridge_url is None else "UNVERIFIED"

        summary = compute_verification_summary(
            meanings_en=en_list,
            meanings_vi=vi_list,
            examples=ex_list,
            ipa_us=ipa_us,
            cambridge_url=cambridge_url,
            ipa_status=eff_ipa_status,
            cambridge_status=eff_cambridge_status,
        )

        with self._writer() if connection is None else self._borrow(connection) as conn:
            existing = (
                conn.exec_driver_sql(
                    "SELECT id, family_id, lemma, normalized_lemma, part_of_speech, meanings_en, "
                    "meanings_vi, examples, ipa_us, ipa_status, cambridge_url, cambridge_status, "
                    "verification_summary, revision, created_at, updated_at "
                    "FROM word_forms "
                    "WHERE family_id = ? AND normalized_lemma = ? AND part_of_speech = ?",
                    (family_id, norm_lemma, pos),
                )
                .mappings()
                .first()
            )

            if existing:
                form_id = existing["id"]
                now = _now_iso()
                new_rev = existing["revision"] + 1
                conn.exec_driver_sql(
                    "UPDATE word_forms SET meanings_en = ?, meanings_vi = ?, examples = ?, "
                    "ipa_us = ?, ipa_status = ?, cambridge_url = ?, cambridge_status = ?, "
                    "verification_summary = ?, revision = ?, updated_at = ? "
                    "WHERE id = ?",
                    (
                        json.dumps([m.to_dict() for m in en_list]),
                        json.dumps([m.to_dict() for m in vi_list]),
                        json.dumps([e.to_dict() for e in ex_list]),
                        ipa_us,
                        eff_ipa_status,
                        cambridge_url,
                        eff_cambridge_status,
                        summary,
                        new_rev,
                        now,
                        form_id,
                    ),
                )
                source_refs = self._get_source_refs(conn, form_id)
                return WordForm(
                    id=form_id,
                    family_id=family_id,
                    lemma=lemma,
                    normalized_lemma=norm_lemma,
                    part_of_speech=pos,
                    meanings_en=en_list,
                    meanings_vi=vi_list,
                    examples=ex_list,
                    ipa_us=ipa_us,
                    ipa_status=eff_ipa_status,
                    cambridge_url=cambridge_url,
                    cambridge_status=eff_cambridge_status,
                    verification_summary=summary,
                    revision=new_rev,
                    created_at=existing["created_at"],
                    updated_at=now,
                    source_refs=source_refs,
                )

            wf_id = word_form_id or f"wf_{token_urlsafe(12)}"
            now = _now_iso()
            conn.exec_driver_sql(
                "INSERT INTO word_forms (id, family_id, lemma, normalized_lemma, part_of_speech, "
                "meanings_en, meanings_vi, examples, ipa_us, ipa_status, cambridge_url, "
                "cambridge_status, verification_summary, revision, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)",
                (
                    wf_id,
                    family_id,
                    lemma,
                    norm_lemma,
                    pos,
                    json.dumps([m.to_dict() for m in en_list]),
                    json.dumps([m.to_dict() for m in vi_list]),
                    json.dumps([e.to_dict() for e in ex_list]),
                    ipa_us,
                    eff_ipa_status,
                    cambridge_url,
                    eff_cambridge_status,
                    summary,
                    now,
                    now,
                ),
            )
            return WordForm(
                id=wf_id,
                family_id=family_id,
                lemma=lemma,
                normalized_lemma=norm_lemma,
                part_of_speech=pos,
                meanings_en=en_list,
                meanings_vi=vi_list,
                examples=ex_list,
                ipa_us=ipa_us,
                ipa_status=eff_ipa_status,
                cambridge_url=cambridge_url,
                cambridge_status=eff_cambridge_status,
                verification_summary=summary,
                revision=1,
                created_at=now,
                updated_at=now,
                source_refs=[],
            )

    def get_word_form_by_identity(
        self,
        lemma: str,
        part_of_speech: str,
        family_id: str,
        *,
        connection: Connection | None = None,
    ) -> WordForm | None:
        """Fetch canonical word form by exact (norm_lemma, POS, family) identity."""
        norm_lemma = normalize_lemma(lemma)
        pos = part_of_speech.strip().upper()
        with self._reader() if connection is None else self._borrow(connection) as conn:
            row = (
                conn.exec_driver_sql(
                    "SELECT id, family_id, lemma, normalized_lemma, part_of_speech, "
                    "meanings_en, meanings_vi, examples, ipa_us, ipa_status, cambridge_url, "
                    "cambridge_status, verification_summary, revision, created_at, updated_at "
                    "FROM word_forms "
                    "WHERE family_id = ? AND normalized_lemma = ? AND part_of_speech = ?",
                    (family_id, norm_lemma, pos),
                )
                .mappings()
                .first()
            )
            if not row:
                return None
            source_refs = self._get_source_refs(conn, row["id"])
            return self._row_to_word_form(row, source_refs)

    def get_word_form(
        self, word_form_id: str, *, connection: Connection | None = None
    ) -> WordForm | None:
        """Fetch canonical word form by ID."""
        with self._reader() if connection is None else self._borrow(connection) as conn:
            row = (
                conn.exec_driver_sql(
                    "SELECT id, family_id, lemma, normalized_lemma, part_of_speech, "
                    "meanings_en, meanings_vi, examples, ipa_us, ipa_status, cambridge_url, "
                    "cambridge_status, verification_summary, revision, created_at, updated_at "
                    "FROM word_forms WHERE id = ?",
                    (word_form_id,),
                )
                .mappings()
                .first()
            )
            if not row:
                return None
            source_refs = self._get_source_refs(conn, word_form_id)
            return self._row_to_word_form(row, source_refs)

    # -------------------------------------------------------------------------
    # Sources and Date Links
    # -------------------------------------------------------------------------

    def save_source_file(
        self,
        *,
        source_id: str,
        relative_path: str,
        note_date: str,
        status: SourceStatus = "VALID",
        revision: int = 1,
        etag: str = "",
        content_hash: str | None = None,
        last_parsed_at: str | None = None,
        error_code: str | None = None,
        connection: Connection | None = None,
    ) -> SourceFile:
        """Save or update a Markdown source file entry."""
        now = _now_iso()
        actual_etag = etag or f'"src-r{revision}-{source_id}"'
        with self._writer() if connection is None else self._borrow(connection) as conn:
            existing = (
                conn.exec_driver_sql(
                    "SELECT id, created_at FROM source_files WHERE id = ?",
                    (source_id,),
                )
                .mappings()
                .first()
            )

            if existing:
                conn.exec_driver_sql(
                    "UPDATE source_files SET relative_path = ?, note_date = ?, status = ?, "
                    "revision = ?, etag = ?, content_hash = ?, last_parsed_at = ?, "
                    "error_code = ?, updated_at = ? WHERE id = ?",
                    (
                        relative_path,
                        note_date,
                        status,
                        revision,
                        actual_etag,
                        content_hash,
                        last_parsed_at,
                        error_code,
                        now,
                        source_id,
                    ),
                )
                created_at = existing["created_at"]
            else:
                conn.exec_driver_sql(
                    "INSERT INTO source_files (id, relative_path, note_date, status, revision, "
                    "etag, content_hash, last_parsed_at, error_code, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        source_id,
                        relative_path,
                        note_date,
                        status,
                        revision,
                        actual_etag,
                        content_hash,
                        last_parsed_at,
                        error_code,
                        now,
                        now,
                    ),
                )
                created_at = now

            return SourceFile(
                id=source_id,
                relative_path=relative_path,
                note_date=note_date,
                status=status,
                revision=revision,
                etag=actual_etag,
                content_hash=content_hash,
                last_parsed_at=last_parsed_at,
                error_code=error_code,
                created_at=created_at,
                updated_at=now,
            )

    def get_source_file(
        self, source_id: str, *, connection: Connection | None = None
    ) -> SourceFile | None:
        """Fetch source file by ID."""
        with self._reader() if connection is None else self._borrow(connection) as conn:
            row = (
                conn.exec_driver_sql(
                    "SELECT id, relative_path, note_date, status, revision, etag, content_hash, "
                    "last_parsed_at, error_code, created_at, updated_at "
                    "FROM source_files WHERE id = ?",
                    (source_id,),
                )
                .mappings()
                .first()
            )
            if not row:
                return None
            return self._row_to_source_file(row)

    def update_source_status(
        self,
        source_id: str,
        status: SourceStatus,
        error_code: str | None = None,
    ) -> SourceFile:
        """Update source file status (VALID, INVALID, MISSING) and optional error code."""
        with self._writer() as conn:
            row = (
                conn.exec_driver_sql(
                    "SELECT id FROM source_files WHERE id = ?",
                    (source_id,),
                )
                .mappings()
                .first()
            )
            if not row:
                raise SourceNotFoundError(f"Source '{source_id}' not found")
            now = _now_iso()
            conn.exec_driver_sql(
                "UPDATE source_files SET status = ?, error_code = ?, updated_at = ? WHERE id = ?",
                (status, error_code, now, source_id),
            )
            updated = (
                conn.exec_driver_sql(
                    "SELECT id, relative_path, note_date, status, revision, etag, content_hash, "
                    "last_parsed_at, error_code, created_at, updated_at "
                    "FROM source_files WHERE id = ?",
                    (source_id,),
                )
                .mappings()
                .first()
            )
            if not updated:
                raise SourceNotFoundError(f"Source '{source_id}' not found")
            return self._row_to_source_file(updated)

    def delete_source_file(self, source_id: str) -> None:
        """Delete source file record.

        Invariants enforced:
        - Deleting a source unlinks it in word_form_sources via FK CASCADE.
        - Deleting a source must NOT cascade-delete canonical word forms or learning history.
        """
        with self._writer() as conn:
            conn.exec_driver_sql("DELETE FROM source_files WHERE id = ?", (source_id,))

    def link_word_form_to_source(
        self,
        word_form_id: str,
        source_id: str,
        note_date: str,
        *,
        connection: Connection | None = None,
    ) -> None:
        """Idempotently link a canonical word form to a source file and note date."""
        with self._writer() if connection is None else self._borrow(connection) as conn:
            wf = conn.exec_driver_sql(
                "SELECT id FROM word_forms WHERE id = ?", (word_form_id,)
            ).first()
            if not wf:
                raise ValueError(f"Word form '{word_form_id}' does not exist")
            src = conn.exec_driver_sql(
                "SELECT id FROM source_files WHERE id = ?", (source_id,)
            ).first()
            if not src:
                raise SourceNotFoundError(f"Source file '{source_id}' does not exist")

            now = _now_iso()
            conn.exec_driver_sql(
                "INSERT OR IGNORE INTO word_form_sources "
                "(word_form_id, source_id, note_date, created_at) "
                "VALUES (?, ?, ?, ?)",
                (word_form_id, source_id, note_date, now),
            )

    def unlink_source_from_form(
        self, word_form_id: str, source_id: str, *, connection: Connection | None = None
    ) -> None:
        """Unlink a source from a word form without deleting the word form itself."""
        with self._writer() if connection is None else self._borrow(connection) as conn:
            conn.exec_driver_sql(
                "DELETE FROM word_form_sources WHERE word_form_id = ? AND source_id = ?",
                (word_form_id, source_id),
            )

    def get_forms_for_source(
        self, source_id: str, *, connection: Connection | None = None
    ) -> list[WordForm]:
        """Fetch all canonical word forms linked to a specific source file."""
        with self._reader() if connection is None else self._borrow(connection) as conn:
            rows = (
                conn.exec_driver_sql(
                    "SELECT wf.id, wf.family_id, wf.lemma, wf.normalized_lemma, "
                    "wf.part_of_speech, wf.meanings_en, wf.meanings_vi, wf.examples, wf.ipa_us, "
                    "wf.ipa_status, wf.cambridge_url, wf.cambridge_status, "
                    "wf.verification_summary, wf.revision, wf.created_at, wf.updated_at "
                    "FROM word_forms wf "
                    "JOIN word_form_sources wfs ON wf.id = wfs.word_form_id "
                    "WHERE wfs.source_id = ? "
                    "ORDER BY wf.lemma ASC",
                    (source_id,),
                )
                .mappings()
                .all()
            )

            results: list[WordForm] = []
            for row in rows:
                source_refs = self._get_source_refs(conn, row["id"])
                results.append(self._row_to_word_form(row, source_refs))
            return results

    def get_forms_for_date(
        self,
        note_date: str,
        *,
        only_valid_sources: bool = False,
    ) -> list[WordForm]:
        """Fetch all canonical word forms linked to a note date.

        If only_valid_sources=True, exclude forms whose sources are INVALID or MISSING.
        If empty source inventory exists, returns empty list deterministically.
        """
        with self._reader() as conn:
            if only_valid_sources:
                sql = (
                    "SELECT DISTINCT wf.id, wf.family_id, wf.lemma, wf.normalized_lemma, "
                    "wf.part_of_speech, wf.meanings_en, wf.meanings_vi, wf.examples, wf.ipa_us, "
                    "wf.ipa_status, wf.cambridge_url, wf.cambridge_status, "
                    "wf.verification_summary, wf.revision, wf.created_at, wf.updated_at "
                    "FROM word_forms wf "
                    "JOIN word_form_sources wfs ON wf.id = wfs.word_form_id "
                    "JOIN source_files sf ON wfs.source_id = sf.id "
                    "WHERE wfs.note_date = ? AND sf.status = 'VALID' "
                    "ORDER BY wf.lemma ASC"
                )
            else:
                sql = (
                    "SELECT DISTINCT wf.id, wf.family_id, wf.lemma, wf.normalized_lemma, "
                    "wf.part_of_speech, wf.meanings_en, wf.meanings_vi, wf.examples, wf.ipa_us, "
                    "wf.ipa_status, wf.cambridge_url, wf.cambridge_status, "
                    "wf.verification_summary, wf.revision, wf.created_at, wf.updated_at "
                    "FROM word_forms wf "
                    "JOIN word_form_sources wfs ON wf.id = wfs.word_form_id "
                    "WHERE wfs.note_date = ? "
                    "ORDER BY wf.lemma ASC"
                )

            rows = conn.exec_driver_sql(sql, (note_date,)).mappings().all()
            results: list[WordForm] = []
            for row in rows:
                source_refs = self._get_source_refs(conn, row["id"])
                results.append(self._row_to_word_form(row, source_refs))
            return results

    # -------------------------------------------------------------------------
    # Previews and Lookup Results
    # -------------------------------------------------------------------------

    def create_preview(
        self,
        *,
        lookup_id: str,
        owner_session_id: str,
        term: str,
        forms: list[WordFormDraft],
        provider: str = "Antigravity/Google",
        model: str = "gemini-3.8-flash-high",
        prompt_version: str = "lookup-v1",
        operation_id: str | None = None,
        created_at: float | None = None,
        expires_at: float | None = None,
    ) -> LookupPreview:
        """Store a lookup preview bound to an owner session."""
        now_ts = created_at if created_at is not None else datetime.now(UTC).timestamp()
        forms_data = [f.to_dict() for f in forms]

        if any(f.verification_summary == "MISSING" for f in forms):
            summary: VerificationStatus = "MISSING"
        elif bool(forms) and all(f.verification_summary == "VERIFIED" for f in forms):
            summary = "VERIFIED"
        else:
            summary = "UNVERIFIED"

        with self._writer() as conn:
            conn.exec_driver_sql(
                "INSERT INTO lookup_previews (lookup_id, operation_id, owner_session_id, term, "
                "forms_payload, provider, model, prompt_version, verification_summary, status, "
                "created_at, expires_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'PREVIEW', ?, ?)",
                (
                    lookup_id,
                    operation_id,
                    owner_session_id,
                    term,
                    json.dumps(forms_data),
                    provider,
                    model,
                    prompt_version,
                    summary,
                    now_ts,
                    expires_at,
                ),
            )

        return LookupPreview(
            lookup_id=lookup_id,
            operation_id=operation_id,
            owner_session_id=owner_session_id,
            term=term,
            forms=forms,
            provider=provider,
            model=model,
            prompt_version=prompt_version,
            verification_summary=summary,
            status="PREVIEW",
            created_at=now_ts,
            expires_at=expires_at,
        )

    def get_preview(
        self,
        lookup_id: str,
        *,
        requesting_session_id: str | None = None,
        now: float | None = None,
    ) -> LookupPreview:
        """Fetch lookup preview, enforcing owner matching and expiration."""
        with self._reader() as conn:
            row = (
                conn.exec_driver_sql(
                    "SELECT lookup_id, operation_id, owner_session_id, term, forms_payload, "
                    "provider, model, prompt_version, verification_summary, status, "
                    "created_at, expires_at "
                    "FROM lookup_previews WHERE lookup_id = ?",
                    (lookup_id,),
                )
                .mappings()
                .first()
            )

            if not row:
                raise PreviewNotFoundError(f"Preview '{lookup_id}' not found")

            if (
                requesting_session_id is not None
                and requesting_session_id != row["owner_session_id"]
            ):
                raise PreviewOwnerMismatchError(
                    f"Preview owner mismatch: session '{requesting_session_id}' "
                    f"is not owner of preview '{lookup_id}'"
                )

            current_time = now if now is not None else datetime.now(UTC).timestamp()
            if row["expires_at"] is not None and current_time >= row["expires_at"]:
                raise PreviewExpiredError(f"Preview '{lookup_id}' has expired")

            forms_raw = json.loads(row["forms_payload"])
            forms = [WordFormDraft.from_dict(item) for item in forms_raw]
            return LookupPreview(
                lookup_id=row["lookup_id"],
                operation_id=row["operation_id"],
                owner_session_id=row["owner_session_id"],
                term=row["term"],
                forms=forms,
                provider=row["provider"],
                model=row["model"],
                prompt_version=row["prompt_version"],
                verification_summary=row["verification_summary"],
                status=row["status"],
                created_at=row["created_at"],
                expires_at=row["expires_at"],
            )

    def save_preview_to_vocabulary(
        self,
        *,
        lookup_id: str,
        requesting_session_id: str,
        note_date: str,
        source_id: str | None = None,
        relative_path: str | None = None,
        family_id: str | None = None,
        now: float | None = None,
    ) -> list[WordForm]:
        """Save forms from a validated preview into durable canonical forms linked to note_date.

        Invariants enforced:
        - Validates owner matching; raises PreviewOwnerMismatchError on mismatch.
        - Validates expiration; raises PreviewExpiredError if expired.
        - Reuses canonical forms matching (norm_lemma, POS, family).
        - Links all canonical forms to the source file.
        - Saved durable vocabulary contains NO credentials or secrets.
        - Updates preview status to CONSUMED.
        """
        preview = self.get_preview(
            lookup_id,
            requesting_session_id=requesting_session_id,
            now=now,
        )

        if family_id:
            fam = self.get_family(family_id)
            if fam is None:
                raise AmbiguousFamilyError(f"Word family '{family_id}' not found")
        else:
            fam = self.get_or_create_family(preview.term)

        src_id = source_id or f"src_{token_urlsafe(12)}"
        rel_path = relative_path or f"{note_date}.md"
        src = self.get_source_file(src_id)
        if src is None:
            src = self.save_source_file(
                source_id=src_id,
                relative_path=rel_path,
                note_date=note_date,
                status="VALID",
            )

        saved_forms: list[WordForm] = []
        for draft in preview.forms:
            form = self.save_canonical_word_form(
                lemma=draft.lemma,
                part_of_speech=draft.part_of_speech,
                family_id=fam.id,
                meanings_en=draft.meanings_en,
                meanings_vi=draft.meanings_vi,
                examples=draft.examples,
                ipa_us=draft.ipa_us,
                ipa_status=draft.ipa_status,
                cambridge_url=draft.cambridge_url,
                cambridge_status=draft.cambridge_status,
            )
            self.link_word_form_to_source(form.id, src.id, note_date)
            re_read = self.get_word_form(form.id)
            saved_forms.append(re_read or form)

        with self._writer() as conn:
            conn.exec_driver_sql(
                "UPDATE lookup_previews SET status = 'CONSUMED' WHERE lookup_id = ?",
                (lookup_id,),
            )

        return saved_forms

    # -------------------------------------------------------------------------
    # Internal Helpers
    # -------------------------------------------------------------------------

    def _get_source_refs(self, conn: Connection, word_form_id: str) -> list[SourceReference]:
        rows = (
            conn.exec_driver_sql(
                "SELECT sf.id, sf.note_date, sf.status "
                "FROM word_form_sources wfs "
                "JOIN source_files sf ON wfs.source_id = sf.id "
                "WHERE wfs.word_form_id = ? "
                "ORDER BY sf.note_date ASC",
                (word_form_id,),
            )
            .mappings()
            .all()
        )
        return [
            SourceReference(
                source_id=r["id"],
                note_date=r["note_date"],
                status=r["status"],
            )
            for r in rows
        ]

    def _row_to_word_form(
        self,
        row: Any,
        source_refs: list[SourceReference],
    ) -> WordForm:
        if isinstance(row["meanings_en"], str):
            raw_en = json.loads(row["meanings_en"])
        else:
            raw_en = row["meanings_en"]

        if isinstance(row["meanings_vi"], str):
            raw_vi = json.loads(row["meanings_vi"])
        else:
            raw_vi = row["meanings_vi"]

        if isinstance(row["examples"], str):
            raw_ex = json.loads(row["examples"])
        else:
            raw_ex = row["examples"]

        return WordForm(
            id=row["id"],
            family_id=row["family_id"],
            lemma=row["lemma"],
            normalized_lemma=row["normalized_lemma"],
            part_of_speech=row["part_of_speech"],
            meanings_en=[MeaningEn.from_dict(m) for m in raw_en],
            meanings_vi=[MeaningVi.from_dict(m) for m in raw_vi],
            examples=[ExampleSentence.from_dict(e) for e in raw_ex],
            ipa_us=row["ipa_us"],
            ipa_status=row["ipa_status"],
            cambridge_url=row["cambridge_url"],
            cambridge_status=row["cambridge_status"],
            verification_summary=row["verification_summary"],
            revision=row["revision"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            source_refs=source_refs,
        )

    def _row_to_source_file(self, row: Any) -> SourceFile:
        return SourceFile(
            id=row["id"],
            relative_path=row["relative_path"],
            note_date=row["note_date"],
            status=row["status"],
            revision=row["revision"],
            etag=row["etag"],
            content_hash=row["content_hash"],
            last_parsed_at=row["last_parsed_at"],
            error_code=row["error_code"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

"""Vietnamese normalized n-gram search projection index (T026).

Implements deterministic search projection for canonical vocabulary forms:
- Substring / infix matching over canonical meanings_vi
- Unicode NFC exact normalized projection
- Accent-folded Vietnamese projection (with đ/Đ -> d mapping)
- Bounded n-gram extraction (lengths 1 to 3)
- Parameterized SQL and literal metacharacter safety
- Source validity filtering (VALID keeps active; INVALID/MISSING excluded)
- Distinct POS form preservation
- Safe, non-destructive projection rebuild
- Deterministic projection versioning and source revision consistency
"""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from backend.app.vocabulary.models import SourceFile, WordForm
from backend.app.vocabulary.normalization import (
    escape_like_meta,
    generate_ngrams,
    normalize_accent_fold,
    normalize_exact,
)
from sqlalchemy import Connection, Engine, create_engine
from sqlalchemy.pool import StaticPool

PROJECTION_VERSION: str = "v1-vietnamese-ngram"


class SearchProjectionError(RuntimeError):
    """Base exception for search projection operations."""


class ProjectionVersionMismatchError(SearchProjectionError, ValueError):
    """Raised when expected projection version does not match stored projection version."""


class StaleSourceRevisionError(SearchProjectionError, ValueError):
    """Raised when a projection update receives a stale source revision."""


@dataclass(frozen=True)
class SearchResultItem:
    """Projection search result representing a matched canonical word form."""

    word_form_id: str
    lemma: str
    part_of_speech: str
    meaning_vi_match: str
    verification_summary: str
    note_dates: tuple[str, ...]
    revision: int
    updated_at: str
    score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict representation matching WordFormSummary fields."""
        return {
            "id": self.word_form_id,
            "lemma": self.lemma,
            "partOfSpeech": self.part_of_speech,
            "meaningViMatch": self.meaning_vi_match,
            "verificationSummary": self.verification_summary,
            "noteDates": list(self.note_dates),
            "revision": self.revision,
            "updatedAt": self.updated_at,
        }


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


class SearchIndex:
    """Deterministic search projection index for Vietnamese vocabulary meanings."""

    def __init__(
        self,
        engine: Engine | None = None,
        *,
        version: str = PROJECTION_VERSION,
    ) -> None:
        self.version = version
        if engine is None:
            # Dedicated in-memory SQLite database with StaticPool for rebuildable projection
            self.engine = create_engine(
                "sqlite:///:memory:",
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )
        else:
            self.engine = engine
        self._init_schema()

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

    def _init_schema(self) -> None:
        """Initialize projection tables. Only touches projection-specific tables."""
        with self._writer() as conn:
            conn.exec_driver_sql(
                """
                CREATE TABLE IF NOT EXISTS search_projection_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            conn.exec_driver_sql(
                """
                CREATE TABLE IF NOT EXISTS search_projection_sources (
                    source_id TEXT PRIMARY KEY,
                    revision INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    note_date TEXT NOT NULL
                )
                """
            )
            conn.exec_driver_sql(
                """
                CREATE TABLE IF NOT EXISTS search_projection_entries (
                    word_form_id TEXT NOT NULL,
                    meaning_index INTEGER NOT NULL,
                    lemma TEXT NOT NULL,
                    part_of_speech TEXT NOT NULL,
                    meaning_vi TEXT NOT NULL,
                    meaning_vi_normalized_exact TEXT NOT NULL,
                    meaning_vi_normalized_folded TEXT NOT NULL,
                    verification_summary TEXT NOT NULL,
                    note_dates_json TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (word_form_id, meaning_index)
                )
                """
            )
            conn.exec_driver_sql(
                """
                CREATE TABLE IF NOT EXISTS search_projection_ngrams (
                    ngram TEXT NOT NULL,
                    is_folded INTEGER NOT NULL,
                    word_form_id TEXT NOT NULL,
                    meaning_index INTEGER NOT NULL,
                    PRIMARY KEY (ngram, is_folded, word_form_id, meaning_index)
                )
                """
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_sp_ngrams "
                "ON search_projection_ngrams (ngram, is_folded)"
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_sp_entries_exact "
                "ON search_projection_entries (meaning_vi_normalized_exact)"
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_sp_entries_folded "
                "ON search_projection_entries (meaning_vi_normalized_folded)"
            )

            # Store version if not already recorded
            row = (
                conn.exec_driver_sql(
                    "SELECT value FROM search_projection_metadata WHERE key = 'version'"
                )
                .mappings()
                .first()
            )
            if not row:
                conn.exec_driver_sql(
                    "INSERT INTO search_projection_metadata (key, value) VALUES ('version', ?)",
                    (self.version,),
                )

    def get_version(self) -> str:
        """Get the stored projection version."""
        with self._reader() as conn:
            row = (
                conn.exec_driver_sql(
                    "SELECT value FROM search_projection_metadata WHERE key = 'version'"
                )
                .mappings()
                .first()
            )
            if row:
                return str(row["value"])
            return ""

    def set_version(self, version: str) -> None:
        """Set stored projection version (used for version mismatch testing/simulation)."""
        with self._writer() as conn:
            conn.exec_driver_sql(
                "INSERT INTO search_projection_metadata (key, value) VALUES ('version', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (version,),
            )

    def build_from_forms(
        self,
        word_forms: list[WordForm],
        source_files: list[SourceFile],
    ) -> None:
        """Populate the projection from given canonical word forms and sources."""
        sources_map = {s.id: str(s.status) for s in source_files}
        with self._writer() as conn:
            # 1. Update source status inventory
            for s in source_files:
                conn.exec_driver_sql(
                    "INSERT INTO search_projection_sources "
                    "(source_id, revision, status, note_date) "
                    "VALUES (?, ?, ?, ?) "
                    "ON CONFLICT(source_id) DO UPDATE SET revision = excluded.revision, "
                    "status = excluded.status, note_date = excluded.note_date",
                    (s.id, s.revision, s.status, s.note_date),
                )

            # 2. Index each word form
            for wf in word_forms:
                self._index_single_form(conn, wf, sources_map)

    def rebuild(
        self,
        word_forms: list[WordForm],
        source_files: list[SourceFile],
    ) -> None:
        """Rebuild the projection completely and non-destructively.

        Clears ONLY search_projection_* tables; never modifies canonical tables
        (word_forms, word_families, source_files, operations, etc.).
        """
        with self._writer() as conn:
            conn.exec_driver_sql("DELETE FROM search_projection_ngrams")
            conn.exec_driver_sql("DELETE FROM search_projection_entries")
            conn.exec_driver_sql("DELETE FROM search_projection_sources")
            conn.exec_driver_sql(
                "INSERT INTO search_projection_metadata (key, value) VALUES ('version', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (self.version,),
            )
            conn.exec_driver_sql(
                "INSERT INTO search_projection_metadata (key, value) VALUES ('rebuilt_at', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (_now_iso(),),
            )

        self.build_from_forms(word_forms, source_files)

    def update_source(
        self,
        source_file: SourceFile,
        linked_forms: list[WordForm],
        *,
        connection: Connection | None = None,
    ) -> None:
        """Refresh a source in a standalone or caller-owned writer transaction."""
        with self._writer() if connection is None else self._borrow(connection) as conn:
            if connection is not None:
                stored_version = conn.exec_driver_sql(
                    "SELECT value FROM search_projection_metadata WHERE key='version'"
                ).scalar_one_or_none()
                if stored_version != self.version:
                    raise ProjectionVersionMismatchError("Projection version mismatch")
            row = (
                conn.exec_driver_sql(
                    "SELECT revision, status FROM search_projection_sources WHERE source_id = ?",
                    (source_file.id,),
                )
                .mappings()
                .first()
            )
            if row:
                current_rev = int(row["revision"])
                if source_file.revision < current_rev:
                    raise StaleSourceRevisionError(
                        f"Stale source revision {source_file.revision} for source {source_file.id} "
                        f"(current: {current_rev})"
                    )

            conn.exec_driver_sql(
                "INSERT INTO search_projection_sources (source_id, revision, status, note_date) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(source_id) DO UPDATE SET revision = excluded.revision, "
                "status = excluded.status, note_date = excluded.note_date",
                (source_file.id, source_file.revision, source_file.status, source_file.note_date),
            )

            # Refresh sources map from current projection state
            sources_map = self._load_sources_map(conn)
            for wf in linked_forms:
                self._index_single_form(conn, wf, sources_map)

    def invalidate_source(
        self,
        source_id: str,
        source_revision: int,
        affected_forms: list[WordForm],
    ) -> None:
        """Mark a source as INVALID and remove forms that have no remaining valid source."""
        with self._writer() as conn:
            row = (
                conn.exec_driver_sql(
                    "SELECT revision, status, note_date FROM search_projection_sources "
                    "WHERE source_id = ?",
                    (source_id,),
                )
                .mappings()
                .first()
            )
            if row:
                current_rev = int(row["revision"])
                if source_revision < current_rev:
                    raise StaleSourceRevisionError(
                        f"Stale source revision {source_revision} for source {source_id} "
                        f"(current: {current_rev})"
                    )
                note_date = str(row["note_date"])
            else:
                note_date = ""

            conn.exec_driver_sql(
                "INSERT INTO search_projection_sources (source_id, revision, status, note_date) "
                "VALUES (?, ?, 'INVALID', ?) "
                "ON CONFLICT(source_id) DO UPDATE SET revision = excluded.revision, "
                "status = 'INVALID'",
                (source_id, source_revision, note_date),
            )

            sources_map = self._load_sources_map(conn)
            for wf in affected_forms:
                self._index_single_form(conn, wf, sources_map)

    def update_word_form(
        self,
        word_form: WordForm,
    ) -> None:
        """Update projection when a word form's meanings or attributes change."""
        with self._writer() as conn:
            sources_map = self._load_sources_map(conn)
            self._index_single_form(conn, word_form, sources_map)

    def _load_sources_map(self, conn: Connection) -> dict[str, str]:
        rows = (
            conn.exec_driver_sql("SELECT source_id, status FROM search_projection_sources")
            .mappings()
            .all()
        )
        sources_map: dict[str, str] = {}
        for r in rows:
            sources_map[str(r["source_id"])] = str(r["status"])
        return sources_map

    def _index_single_form(
        self,
        conn: Connection,
        wf: WordForm,
        sources_map: dict[str, str],
    ) -> None:
        """Index or remove a single form based on active source validity."""
        # 1. Clean existing projection entries for this word form
        conn.exec_driver_sql(
            "DELETE FROM search_projection_ngrams WHERE word_form_id = ?",
            (wf.id,),
        )
        conn.exec_driver_sql(
            "DELETE FROM search_projection_entries WHERE word_form_id = ?",
            (wf.id,),
        )

        # 2. Determine valid source note dates
        # A form is active only if at least one linked source has status VALID
        valid_dates: set[str] = set()
        for ref in wf.source_refs:
            src_status = sources_map.get(ref.source_id, ref.status)
            if src_status == "VALID":
                valid_dates.add(ref.note_date)

        if not valid_dates:
            # No valid source: form is not actively searchable
            return

        sorted_dates = sorted(valid_dates)
        dates_json = json.dumps(sorted_dates)

        # 3. Index each Vietnamese meaning (FR-VOC-01: canonical meanings_vi only)
        for idx, m in enumerate(wf.meanings_vi):
            text = m.text
            exact_norm = normalize_exact(text)
            folded_norm = normalize_accent_fold(text)
            if not exact_norm:
                continue

            conn.exec_driver_sql(
                """
                INSERT INTO search_projection_entries (
                    word_form_id, meaning_index, lemma, part_of_speech, meaning_vi,
                    meaning_vi_normalized_exact, meaning_vi_normalized_folded,
                    verification_summary, note_dates_json, revision, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    wf.id,
                    idx,
                    wf.lemma,
                    wf.part_of_speech,
                    text,
                    exact_norm,
                    folded_norm,
                    wf.verification_summary,
                    dates_json,
                    wf.revision,
                    wf.updated_at,
                ),
            )

            # Generate n-grams for exact and folded normalized text
            exact_ngrams = generate_ngrams(exact_norm)
            folded_ngrams = generate_ngrams(folded_norm)

            for ng in exact_ngrams:
                conn.exec_driver_sql(
                    """
                    INSERT OR IGNORE INTO search_projection_ngrams (
                        ngram, is_folded, word_form_id, meaning_index
                    ) VALUES (?, 0, ?, ?)
                    """,
                    (ng, wf.id, idx),
                )
            for ng in folded_ngrams:
                conn.exec_driver_sql(
                    """
                    INSERT OR IGNORE INTO search_projection_ngrams (
                        ngram, is_folded, word_form_id, meaning_index
                    ) VALUES (?, 1, ?, ?)
                    """,
                    (ng, wf.id, idx),
                )

    def iter_search_candidates(
        self,
        query: str,
        *,
        expected_version: str | None = None,
    ) -> Iterator[SearchResultItem]:
        """Stream the complete matching population, retaining only one form's best match.

        Supports:
        - Accented exact matching
        - Accent-folded matching (e.g. đ -> d, vung -> vững)
        - Infix matches (beginning, middle, end)
        - Short queries (including 1-character queries)
        - Parameterized query safety with literal metacharacter handling
        """
        # Version verification: mismatch raises explicit error, never silent empty
        exp_ver = expected_version or self.version
        stored_ver = self.get_version()
        if stored_ver != exp_ver:
            raise ProjectionVersionMismatchError(
                f"Projection version mismatch: expected '{exp_ver}', got '{stored_ver}'"
            )

        if not query or not query.strip():
            return

        q_exact = normalize_exact(query)
        q_folded = normalize_accent_fold(query)
        if not q_exact:
            return

        # Parameterized LIKE search with deterministic escaping of LIKE metacharacters
        pattern_exact = f"%{escape_like_meta(q_exact)}%"
        pattern_folded = f"%{escape_like_meta(q_folded)}%"

        sql = """
            SELECT word_form_id, meaning_index, lemma, part_of_speech, meaning_vi,
                   meaning_vi_normalized_exact, meaning_vi_normalized_folded,
                   verification_summary, note_dates_json, revision, updated_at
            FROM search_projection_entries
            WHERE meaning_vi_normalized_exact LIKE ? ESCAPE '\\'
               OR meaning_vi_normalized_folded LIKE ? ESCAPE '\\'
            ORDER BY word_form_id ASC, meaning_index ASC
        """

        # Group adjacent rows by form. No population-sized list/dictionary is built.
        best: SearchResultItem | None = None
        with self._reader() as conn:
            rows = conn.exec_driver_sql(sql, (pattern_exact, pattern_folded)).mappings()
            for row in rows:
                wf_id = str(row["word_form_id"])
                if best is not None and best.word_form_id != wf_id:
                    yield best
                    best = None
                exact_text = str(row["meaning_vi_normalized_exact"])
                folded_text = str(row["meaning_vi_normalized_folded"])
                raw_meaning = str(row["meaning_vi"])

                is_exact = q_exact in exact_text
                is_folded = q_folded in folded_text
                if not is_exact and not is_folded:
                    # Discard any false-positive from LIKE patterns
                    continue

                # Deterministic scoring:
                # - Exact diacritic match scores higher than accent-folded
                # - Prefix match scores higher than middle/suffix match
                # - Complete exact match gives highest bonus
                score = 0.0
                if is_exact:
                    score += 2.0
                    if exact_text == q_exact:
                        score += 3.0
                    elif exact_text.startswith(q_exact):
                        score += 1.0
                elif is_folded:
                    score += 1.0
                    if folded_text == q_folded:
                        score += 2.0
                    elif folded_text.startswith(q_folded):
                        score += 0.5

                if best is None or score > best.score:
                    note_dates = tuple(json.loads(str(row["note_dates_json"])))
                    best = SearchResultItem(
                        word_form_id=wf_id,
                        lemma=str(row["lemma"]),
                        part_of_speech=str(row["part_of_speech"]),
                        meaning_vi_match=raw_meaning,
                        verification_summary=str(row["verification_summary"]),
                        note_dates=note_dates,
                        revision=int(row["revision"]),
                        updated_at=str(row["updated_at"]),
                        score=score,
                    )

        if best is not None:
            yield best

    def search(
        self,
        query: str,
        *,
        expected_version: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SearchResultItem]:
        """Preserve the legacy globally sorted, materialized search interface."""
        sorted_results = sorted(
            self.iter_search_candidates(query, expected_version=expected_version),
            key=lambda item: (-item.score, item.lemma, item.part_of_speech, item.word_form_id),
        )
        return sorted_results[offset : offset + limit]

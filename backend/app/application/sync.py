"""Startup, manual, and watcher Markdown source synchronization (T023).

Coordinates scanning, parsing, canonical vocabulary persistence, search index projection,
and SRS card reset/reuse across Markdown note files and SQLite.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import hmac
import json
import os
import re
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from secrets import token_hex, token_urlsafe
from typing import Any, Literal, cast

from backend.app.adapters.source_files import (
    SourceFileAdapter,
    SourceFileError,
    validate_relative_path,
)
from backend.app.application.operations import OperationLedger
from backend.app.application.source_write import (
    JournalConflictError,
    _content_changed,
    _form_digest,
    _learning_values,
    _projection_values,
    _semantic_key,
)
from backend.app.markdown_sync.parser import ParsedDocument, parse_markdown
from backend.app.review.models import ensure_card, reset_card_state
from backend.app.vocabulary.models import SourceFile, WordForm
from backend.app.vocabulary.repository import VocabularyRepository
from backend.app.vocabulary.search_index import SearchIndex
from sqlalchemy import Connection, Engine

SyncReason = Literal["STARTUP", "MANUAL", "WATCHER"]
SyncStatus = Literal["QUEUED", "RUNNING", "COMPLETED", "FAILED"]

_CURSOR_SECRET = token_hex(32)


class CursorExpiredError(RuntimeError):
    """Raised when an opaque cursor cannot be safely decrypted or validated."""


@dataclass(frozen=True)
class SyncResult:
    id: str
    operation_id: str
    status: SyncStatus
    reason: SyncReason
    sources_scanned: int
    sources_invalid: int
    started_at: str
    source_revision: int | None = None
    finished_at: str | None = None
    error_message: str | None = None


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _normalize_inferred_date(filename: str) -> str:
    """Normalize legacy DD-MM-YYYY or ISO YYYY-MM-DD filename date to valid ISO format."""
    m_iso = re.search(r"(\d{4})-(\d{2})-(\d{2})", filename)
    if m_iso:
        y, m, d = int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3))
        try:
            return date(y, m, d).isoformat()
        except ValueError:
            pass
    m_leg = re.search(r"(\d{2})-(\d{2})-(\d{4})", filename)
    if m_leg:
        d, m, y = int(m_leg.group(1)), int(m_leg.group(2)), int(m_leg.group(3))
        try:
            return date(y, m, d).isoformat()
        except ValueError:
            pass
    return "1970-01-01"


def _protected_journal_forms(effect_plan: str) -> set[str]:
    """Reject an uninterpretable active plan instead of dropping form protections."""
    message = "Active source journal effect plan is invalid"
    try:
        plan = json.loads(effect_plan)
    except (ValueError, TypeError):
        raise JournalConflictError(message) from None
    if (
        not isinstance(plan, dict)
        or plan.get("version") != 1
        or not isinstance(plan.get("forms"), list)
    ):
        raise JournalConflictError(message)
    protected: set[str] = set()
    for effect in plan["forms"]:
        if not isinstance(effect, dict):
            raise JournalConflictError(message)
        form_id = effect.get("form_id")
        if not isinstance(form_id, str) or not form_id.strip():
            raise JournalConflictError(message)
        protected.add(form_id)
    return protected


class SyncService:
    """Coordinates Markdown file scanning, parsing, canonical vocabulary, and search updates."""

    def __init__(
        self,
        engine: Engine,
        root_path: Path | str,
        *,
        operation_ledger: OperationLedger | None = None,
        search_index: SearchIndex | None = None,
    ) -> None:
        self.engine = engine
        self.root_path = Path(root_path).resolve()
        self.operation_ledger = operation_ledger or OperationLedger(engine)
        self.repository = VocabularyRepository(engine)
        self.search_index = search_index or SearchIndex(engine)
        self._sync_lock = threading.Lock()
        self._sync_cache: dict[str, SyncResult] = {}

    def _committed_date_variants(
        self, connection: Connection, adapter: SourceFileAdapter,
        identity: tuple[str, str, str], paths: set[str],
        documents: dict[str, tuple[str, ParsedDocument | None, str | None]],
        sources: dict[str, dict[str, Any]],
    ) -> bool:
        """Authenticate historical date variants; never select a file by recency.

        Every participant must still be a valid, unchanged, linked source. One
        exact committed write plus its successful durable receipt must explain
        the current canonical projection. A subsequent external edit, new path,
        stale revision or incomplete operation therefore cannot borrow that proof.
        """
        families = self.repository.get_families_for_root(identity[0], connection=connection)
        if len(families) != 1:
            return False
        canonical = self.repository.get_word_form_by_identity(
            identity[1], identity[2], families[0].id, connection=connection,
        )
        if canonical is None:
            return False
        refs = {ref.source_id: ref for ref in canonical.source_refs}
        participants: list[tuple[SourceFile, ParsedDocument]] = []
        for path in sorted(paths):
            snapshot = sources.get(path)
            content_hash, document, error = documents[path]
            if snapshot is None or document is None or error is not None:
                return False
            source = self.repository.get_source_file(str(snapshot["id"]), connection=connection)
            if (
                source is None or source.status != "VALID" or source.relative_path != path
                or source.revision != snapshot["revision"] or source.content_hash != content_hash
                or snapshot["status"] != "VALID" or snapshot["content_hash"] != content_hash
                or source.note_date != document.note_date
                or source.id not in refs or refs[source.id].status != "VALID"
                or refs[source.id].note_date != source.note_date
            ):
                return False
            adapter.register_source(source)
            try:
                if adapter.get_source_hash(source.id) != content_hash:
                    return False
            except SourceFileError:
                return False
            participants.append((source, document))

        for source, document in participants:
            semantics = [sf for sf in document.semantic_forms if (
                sf.family_root, sf.normalized_lemma, sf.part_of_speech
            ) == identity]
            if len(semantics) != 1 or _content_changed(semantics[0], canonical):
                continue
            semantic = semantics[0]
            rows = connection.exec_driver_sql(
                "SELECT j.operation_id,j.effect_plan,j.response_status,j.result_ref "
                "FROM source_write_journal j JOIN operations o ON o.operation_id=j.operation_id "
                "WHERE j.state='COMMITTED' AND j.source_id=? AND j.new_hash=? "
                "AND j.intended_projection_revision=? AND o.kind='SAVE' AND o.status='SUCCEEDED' "
                "AND o.response_status=j.response_status AND o.result_ref=j.result_ref",
                (source.id, source.content_hash, source.revision),
            ).mappings().all()
            for row in rows:
                try:
                    plan = json.loads(row["effect_plan"])
                except (ValueError, TypeError, RecursionError):
                    continue
                if not isinstance(plan, dict) or plan.get("version") != 1:
                    continue
                receipt = plan.get("receipt")
                effects = plan.get("forms")
                if (
                    not isinstance(receipt, dict) or not isinstance(effects, list)
                    or row["response_status"] != 201 or row["result_ref"] != row["operation_id"]
                    or receipt.get("operationId") != row["operation_id"]
                    or receipt.get("sourceId") != source.id
                    or receipt.get("sourceRevision") != source.revision
                    or receipt.get("sourceEtag") != source.etag
                    or receipt.get("noteDate") != source.note_date
                    or receipt.get("markdownSync") != "COMPLETED"
                ):
                    continue
                matching = [e for e in effects if isinstance(e, dict)
                            and e.get("key") == _semantic_key(semantic)
                            and e.get("form_id") == canonical.id
                            and e.get("family_id") == canonical.family_id]
                if len(matching) != 1:
                    continue
                effect = matching[0]
                base_revision = effect.get("base_revision")
                if base_revision is None:
                    if canonical.revision != 1:
                        continue
                elif (
                    type(base_revision) is not int
                    or canonical.revision not in (base_revision, base_revision + 1)
                    or (canonical.revision == base_revision
                        and _form_digest(canonical) != effect.get("base_hash"))
                ):
                    continue
                card_id = connection.exec_driver_sql(
                    "SELECT card_id FROM review_cards WHERE word_form_id=?", (canonical.id,),
                ).scalar_one_or_none()
                if card_id is None or card_id != effect.get("card_id"):
                    continue
                frozen_forms = receipt.get("canonicalForms")
                if not isinstance(frozen_forms, list):
                    continue
                frozen = [f for f in frozen_forms if isinstance(f, dict)
                          and f.get("id") == canonical.id]
                if not frozen and (
                    effect.get("preserve_canonical") is not True
                    or canonical.revision != base_revision
                    or _form_digest(canonical) != effect.get("base_hash")
                ):
                    continue
                if frozen and (len(frozen) != 1 or any(
                    frozen[0].get(key) != value for key, value in {
                        "familyId": canonical.family_id, "revision": canonical.revision,
                        "partOfSpeech": canonical.part_of_speech,
                        "meaningsEn": [m.to_dict() for m in canonical.meanings_en],
                        "meaningsVi": [m.to_dict() for m in canonical.meanings_vi],
                        "examples": [e.to_dict() for e in canonical.examples],
                        "ipaUs": canonical.ipa_us, "cambridgeUrl": canonical.cambridge_url,
                    }.items()
                )):
                    continue
                return True
        return False

    def _conflict_snapshot_changed(
        self, connection: Connection, paths: set[str], sources: dict[str, dict[str, Any]],
    ) -> bool:
        """Defer a stale corpus comparison instead of invalidating a concurrent save."""
        by_id = {str(source["id"]): source for source in sources.values()}
        related = set(paths)
        for path in paths:
            snapshot = sources.get(path)
            if snapshot is None:
                continue
            for form in self.repository.get_forms_for_source(str(snapshot["id"]),
                                                            connection=connection):
                for ref in form.source_refs:
                    if ref.status == "VALID":
                        known = by_id.get(ref.source_id)
                        if known is None:
                            return True
                        related.add(str(known["relative_path"]))
        for path in related:
            current = connection.exec_driver_sql(
                "SELECT id,status,revision,content_hash FROM source_files WHERE relative_path=?",
                (path,),
            ).mappings().first()
            snapshot = sources.get(path)
            if snapshot is None:
                if current is not None:
                    return True
            elif current is None or any(
                current[key] != snapshot[key] for key in ("id", "status", "revision", "content_hash")
            ):
                return True
        return False

    def _get_aggregate_source_revision(self, *, connection: Connection | None = None) -> int:
        """Compute durable aggregate revision from retained source files.

        Advances on every committed source change (addition, edit, validity, or missing transition)
        and survives service recreation.
        """
        sql = "SELECT COALESCE(SUM(revision), 0) FROM source_files"
        if connection is not None:
            val = connection.exec_driver_sql(sql).scalar()
        else:
            with self.engine.connect() as conn:
                val = conn.exec_driver_sql(sql).scalar()
        return int(val) if val is not None else 0

    def _get_max_source_revision(self) -> int:
        return self._get_aggregate_source_revision()

    def _get_sources_snapshot_token(self, *, connection: Connection | None = None) -> str:
        agg_rev = self._get_aggregate_source_revision(connection=connection)
        sql = (
            "SELECT id, relative_path, note_date, status, revision, content_hash, "
            "error_code, updated_at FROM source_files ORDER BY id ASC"
        )
        if connection is not None:
            rows = connection.exec_driver_sql(sql).all()
        else:
            with self.engine.connect() as conn:
                rows = conn.exec_driver_sql(sql).all()
        h = hashlib.sha256()
        h.update(f"agg:{agg_rev}|".encode())
        for r in rows:
            h.update(f"{r[0]}:{r[1]}:{r[2]}:{r[3]}:{r[4]}:{r[5]}:{r[6]}:{r[7]}|".encode())
        return h.hexdigest()

    def _encode_cursor(self, payload: dict[str, Any]) -> str:
        data_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        sig = hmac.new(_CURSOR_SECRET.encode("utf-8"), data_bytes, hashlib.sha256).digest()
        token = base64.urlsafe_b64encode(sig[:16] + data_bytes).decode("ascii")
        return token

    def _decode_cursor(
        self,
        token: str,
        expected_filters: dict[str, Any],
        expected_snapshot: str | None = None,
        *,
        connection: Connection | None = None,
    ) -> dict[str, Any]:
        try:
            raw = base64.urlsafe_b64decode(token.encode("ascii"))
            sig = raw[:16]
            data_bytes = raw[16:]
            expected_sig = hmac.new(
                _CURSOR_SECRET.encode("utf-8"), data_bytes, hashlib.sha256
            ).digest()[:16]
            if not hmac.compare_digest(sig, expected_sig):
                raise CursorExpiredError("Cursor signature mismatch")
            payload = json.loads(data_bytes.decode("utf-8"))
        except Exception as e:
            if isinstance(e, CursorExpiredError):
                raise
            raise CursorExpiredError("Malformed cursor") from e

        # Validate query filters and sort consistency
        for key in ["status", "note_date", "sort_by", "direction"]:
            if payload.get(key) != expected_filters.get(key):
                raise CursorExpiredError("Cursor query mismatch")

        # Validate source snapshot has not drifted past cursor issuance
        current_snapshot = (
            expected_snapshot
            if expected_snapshot is not None
            else self._get_sources_snapshot_token(connection=connection)
        )
        if payload.get("snapshot_token") != current_snapshot:
            raise CursorExpiredError("Cursor expired due to source updates")

        return cast(dict[str, Any], payload)

    def list_sources(
        self,
        *,
        status: str | None = None,
        note_date: str | None = None,
        page_size: int = 50,
        cursor: str | None = None,
        sort_by: str = "updatedAt",
        direction: str = "DESC",
        _test_after_rows_hook: Callable[[], None] | None = None,
    ) -> tuple[list[SourceFile], str | None, bool]:
        """Query sources with cursor pagination, deterministic tie-breaking, and filter guards."""
        sort_column_map = {
            "updatedAt": "updated_at",
            "noteDate": "note_date",
            "status": "status",
            "revision": "revision",
        }
        db_col = sort_column_map.get(sort_by, "updated_at")
        db_dir = "ASC" if direction.upper() == "ASC" else "DESC"
        opp_cmp = ">" if db_dir == "ASC" else "<"

        expected_filters = {
            "status": status,
            "note_date": note_date,
            "sort_by": sort_by,
            "direction": db_dir,
        }

        conditions: list[str] = []
        params: list[Any] = []

        if status is not None:
            conditions.append("status = ?")
            params.append(status)
        if note_date is not None:
            conditions.append("note_date = ?")
            params.append(note_date)

        with self.engine.connect() as conn, conn.begin():
            snapshot_token = self._get_sources_snapshot_token(connection=conn)

            last_val = None
            last_id = None
            if cursor is not None:
                decoded = self._decode_cursor(
                    cursor, expected_filters, expected_snapshot=snapshot_token, connection=conn
                )
                last_val = decoded.get("last_val")
                last_id = decoded.get("last_id")

            if last_val is not None and last_id is not None:
                conditions.append(f"({db_col} {opp_cmp} ? OR ({db_col} = ? AND id > ?))")
                params.extend([last_val, last_val, last_id])

            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            query = (
                f"SELECT id, relative_path, note_date, status, revision, etag, content_hash, "
                f"last_parsed_at, error_code, created_at, updated_at "
                f"FROM source_files {where_clause} "
                f"ORDER BY {db_col} {db_dir}, id ASC LIMIT ?"
            )
            params.append(page_size + 1)

            rows = conn.exec_driver_sql(query, tuple(params)).mappings().all()

        if _test_after_rows_hook is not None:
            _test_after_rows_hook()

        has_more = len(rows) > page_size
        results_rows = rows[:page_size]

        source_files = [
            SourceFile(
                id=str(r["id"]),
                relative_path=str(r["relative_path"]),
                note_date=str(r["note_date"]),
                status=r["status"],
                revision=int(r["revision"]),
                etag=str(r["etag"]),
                content_hash=str(r["content_hash"]) if r["content_hash"] is not None else None,
                last_parsed_at=str(r["last_parsed_at"])
                if r["last_parsed_at"] is not None
                else None,
                error_code=str(r["error_code"]) if r["error_code"] is not None else None,
                created_at=str(r["created_at"]),
                updated_at=str(r["updated_at"]),
            )
            for r in results_rows
        ]

        next_cursor = None
        if has_more and results_rows:
            last_row = results_rows[-1]
            cursor_payload = {
                "status": status,
                "note_date": note_date,
                "sort_by": sort_by,
                "direction": db_dir,
                "snapshot_token": snapshot_token,
                "last_val": last_row[db_col],
                "last_id": str(last_row["id"]),
            }
            next_cursor = self._encode_cursor(cursor_payload)

        return source_files, next_cursor, has_more

    def get_sync_run(self, sync_run_id: str) -> SyncResult | None:
        """Fetch a sync run by ID from in-memory cache or durable operations ledger."""
        if sync_run_id in self._sync_cache:
            return self._sync_cache[sync_run_id]

        with self.engine.connect() as conn:
            row = (
                conn.exec_driver_sql(
                    "SELECT operation_id, status, result_ref, created_at, updated_at "
                    "FROM operations WHERE kind='SYNC_RUN' "
                    "AND result_ref IS NOT NULL "
                    "AND (result_ref = ? OR (instr(result_ref, '.') > 0 "
                    "AND substr(result_ref, 1, instr(result_ref, '.') - 1) = ?))",
                    (sync_run_id, sync_run_id),
                )
                .mappings()
                .first()
            )
        if row is None:
            return None

        result_ref = str(row["result_ref"])
        parts = result_ref.split(".")
        run_id = parts[0]
        reason_str = parts[1] if len(parts) > 1 else ""
        reason: SyncReason = (
            cast(SyncReason, reason_str)
            if reason_str in ("STARTUP", "MANUAL", "WATCHER")
            else "MANUAL"
        )
        scanned = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
        invalid = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0
        rev = int(parts[4]) if len(parts) > 4 and parts[4].isdigit() else 0
        raw_status = str(row["status"])
        status: SyncStatus
        if raw_status == "SUCCEEDED":
            status = "COMPLETED"
        elif raw_status == "QUEUED":
            status = "QUEUED"
        elif raw_status in ("PENDING", "RUNNING"):
            status = "RUNNING"
        else:
            status = "FAILED"

        finished_at = str(row["updated_at"]) if status in ("COMPLETED", "FAILED") else None
        result = SyncResult(
            id=run_id,
            operation_id=str(row["operation_id"]),
            status=status,
            reason=reason,
            sources_scanned=scanned,
            sources_invalid=invalid,
            started_at=str(row["created_at"]),
            source_revision=rev,
            finished_at=finished_at,
        )
        if status in ("COMPLETED", "FAILED"):
            self._sync_cache[run_id] = result
        return result

    def sync(
        self,
        reason: SyncReason = "MANUAL",
        *,
        operation_id: str | None = None,
    ) -> SyncResult:
        """Perform atomic synchronization between Markdown directory and SQLite store."""
        with self._sync_lock:
            started_at = _now()
            sync_id = f"sync_{token_urlsafe(12)}"
            op_id = operation_id or f"op_{token_urlsafe(18)}"
            initial_result_ref = f"{sync_id}.{reason}.0.0.0"

            # If not already claimed by caller via ledger, insert into operations table
            with (
                self.engine.connect().execution_options(sqlite_begin_immediate=True) as conn,
                conn.begin(),
            ):
                existing_op = conn.exec_driver_sql(
                    "SELECT operation_id FROM operations WHERE operation_id=?", (op_id,)
                ).first()
                if existing_op is None:
                    conn.exec_driver_sql(
                        "INSERT INTO operations "
                        "(operation_id, kind, status, result_ref, created_at, updated_at) "
                        "VALUES (?, 'SYNC_RUN', 'PENDING', ?, ?, ?)",
                        (op_id, initial_result_ref, started_at, started_at),
                    )
                else:
                    conn.exec_driver_sql(
                        "UPDATE operations SET result_ref=?, updated_at=? WHERE operation_id=?",
                        (initial_result_ref, started_at, op_id),
                    )

            sources_scanned = 0
            sources_invalid = 0
            max_rev_seen: int | None = None
            committed_effects = False
            try:
                # Query active journal records for write fencing (T022)
                with self.engine.connect() as conn:
                    active_journal_rows = conn.exec_driver_sql(
                        "SELECT source_id, effect_plan FROM source_write_journal "
                        "WHERE state IN ('PREPARED', 'SOURCE_REPLACED', 'DEGRADED')"
                    ).all()
                for row in active_journal_rows:
                    _protected_journal_forms(row[1])
                fenced_source_ids = {str(r[0]) for r in active_journal_rows}

                # 1. Collect all non-hidden .md files from root_path safely
                found_files: list[Path] = []
                adapter: SourceFileAdapter | None = None
                if not self.root_path.exists() or not self.root_path.is_dir():
                    raise SourceFileError(
                        "ROOT_NOT_FOUND",
                        "Configured root directory does not exist or is not a directory",
                    )
                adapter = SourceFileAdapter(self.root_path)

                def refuse_traversal_error(error: OSError) -> None:
                    code = "ACCESS_DENIED" if isinstance(error, PermissionError) else "IO_ERROR"
                    raise SourceFileError(code, "Source directory traversal failed") from None

                for root, dirs, files in os.walk(
                    self.root_path, followlinks=False, onerror=refuse_traversal_error
                ):
                    dirs[:] = [
                        d
                        for d in dirs
                        if not d.startswith(".") and not os.path.islink(os.path.join(root, d))
                    ]
                    for f in files:
                        if not f.startswith(".") and f.endswith(".md"):
                            full_path = Path(root) / f
                            if not os.path.islink(full_path):
                                found_files.append(full_path)

                found_files.sort()
                disk_rel_paths = {p.relative_to(self.root_path).as_posix() for p in found_files}

                # 2. Get existing sources from DB
                with self.engine.connect() as conn:
                    db_rows = (
                        conn.exec_driver_sql(
                            "SELECT id, relative_path, note_date, status, revision, etag, "
                            "content_hash, last_parsed_at, error_code, created_at, updated_at "
                            "FROM source_files"
                        )
                        .mappings()
                        .all()
                    )
                db_sources = {str(r["relative_path"]): dict(r) for r in db_rows}

                # 3. Mark missing sources (known in DB, absent on disk, not fenced)
                for rel_path, db_src in db_sources.items():
                    if str(db_src["id"]) in fenced_source_ids:
                        continue
                    if rel_path not in disk_rel_paths and db_src["status"] != "MISSING":
                        with (
                            self.engine.connect().execution_options(
                                sqlite_begin_immediate=True
                            ) as conn,
                            conn.begin(),
                        ):
                            active_journals = conn.exec_driver_sql(
                                "SELECT source_id, effect_plan FROM source_write_journal "
                                "WHERE state IN ('PREPARED', 'SOURCE_REPLACED', 'DEGRADED')"
                            ).all()
                            for row in active_journals:
                                _protected_journal_forms(row[1])
                            if str(db_src["id"]) in {str(row[0]) for row in active_journals}:
                                continue
                            current_row = (
                                conn.exec_driver_sql(
                                    "SELECT revision, status FROM source_files WHERE id = ?",
                                    (str(db_src["id"]),),
                                )
                                .mappings()
                                .first()
                            )
                            if (
                                current_row is None
                                or current_row["revision"] != db_src["revision"]
                                or current_row["status"] == "MISSING"
                            ):
                                continue

                            new_rev = int(db_src["revision"]) + 1
                            new_etag = f'"src-r{new_rev}-{db_src["id"]}"'
                            now_ts = _now()
                            conn.exec_driver_sql(
                                "UPDATE source_files SET status='MISSING', revision=?, "
                                "etag=?, updated_at=? WHERE id=?",
                                (new_rev, new_etag, now_ts, db_src["id"]),
                            )
                            src_model = SourceFile(
                                id=str(db_src["id"]),
                                relative_path=rel_path,
                                note_date=str(db_src["note_date"]),
                                status="MISSING",
                                revision=new_rev,
                                etag=new_etag,
                                content_hash=None,
                                last_parsed_at=str(db_src["last_parsed_at"])
                                if db_src.get("last_parsed_at") is not None
                                else None,
                                error_code=str(db_src["error_code"])
                                if db_src.get("error_code") is not None
                                else None,
                                created_at=str(db_src["created_at"])
                                if db_src.get("created_at") is not None
                                else now_ts,
                                updated_at=now_ts,
                            )
                            affected_forms = self.repository.get_forms_for_source(
                                str(db_src["id"]), connection=conn
                            )
                            self.search_index.update_source(
                                src_model, affected_forms, connection=conn
                            )
                            if max_rev_seen is None or new_rev > max_rev_seen:
                                max_rev_seen = new_rev
                            committed_effects = True

                # 4. Read, validate, and parse each disk file via T021 adapter
                parsed_docs: dict[
                    str, tuple[str, ParsedDocument | None, str | None]
                ] = {}  # rel -> (hash, doc_or_none, error_or_none)
                for file_path in found_files:
                    rel_path = file_path.relative_to(self.root_path).as_posix()
                    existing_src = db_sources.get(rel_path)

                    # Skip active write targets fenced by T022
                    if existing_src is not None and str(existing_src["id"]) in fenced_source_ids:
                        continue

                    sources_scanned += 1
                    try:
                        validate_relative_path(rel_path)
                    except SourceFileError as sfe:
                        sources_invalid += 1
                        parsed_docs[rel_path] = ("", None, sfe.code)
                        continue

                    candidate_id = (
                        str(existing_src["id"]) if existing_src else f"cand_{token_urlsafe(12)}"
                    )
                    candidate_date = (
                        str(existing_src["note_date"])
                        if existing_src
                        else _normalize_inferred_date(file_path.name)
                    )
                    candidate_src = SourceFile(
                        id=candidate_id,
                        relative_path=rel_path,
                        note_date=candidate_date,
                        status="VALID",
                        revision=int(existing_src["revision"]) if existing_src else 1,
                        etag=str(existing_src["etag"]) if existing_src else '"candidate"',
                        content_hash=str(existing_src["content_hash"])
                        if existing_src and existing_src.get("content_hash")
                        else None,
                        last_parsed_at=str(existing_src["last_parsed_at"])
                        if existing_src and existing_src.get("last_parsed_at")
                        else None,
                        error_code=None,
                        created_at=str(existing_src["created_at"])
                        if existing_src and existing_src.get("created_at")
                        else started_at,
                        updated_at=str(existing_src["updated_at"])
                        if existing_src and existing_src.get("updated_at")
                        else started_at,
                    )
                    if adapter is not None:
                        adapter.register_source(candidate_src)
                        try:
                            content_str = adapter.read_source_content(candidate_id)
                        except SourceFileError as sfe:
                            sources_invalid += 1
                            parsed_docs[rel_path] = ("", None, sfe.code)
                            continue
                    else:
                        try:
                            raw_bytes = file_path.read_bytes()
                            content_str = raw_bytes.decode("utf-8")
                        except Exception:
                            sources_invalid += 1
                            parsed_docs[rel_path] = ("", None, "IO_ERROR")
                            continue

                    content_hash = _hash_bytes(content_str.encode("utf-8"))
                    parse_res = parse_markdown(content_str, filename=file_path.name)
                    if not parse_res.is_valid or parse_res.document is None:
                        sources_invalid += 1
                        err_code = (
                            parse_res.diagnostics[0].code
                            if parse_res.diagnostics
                            else "PARSE_ERROR"
                        )
                        parsed_docs[rel_path] = (content_hash, None, err_code)
                        continue

                    parsed_docs[rel_path] = (content_hash, parse_res.document, None)

                # 5. Check cross-file multi-source semantic ambiguities
                # Track all participating sources for each canonical identity:
                # (family_root, normalized_lemma, part_of_speech) -> dict[form_val, set[rel_paths]]
                forms_by_identity: dict[
                    tuple[str, str, str],
                    dict[
                        tuple[tuple[str, ...], tuple[str, ...], tuple[tuple[str, str], ...]],
                        set[str],
                    ],
                ] = {}

                for rel_path, (_chash, doc, _err) in parsed_docs.items():
                    if doc is None:
                        continue
                    for sf in doc.semantic_forms:
                        form_key = (sf.family_root, sf.normalized_lemma, sf.part_of_speech)
                        form_val = (
                            tuple(sf.meanings_en),
                            tuple(sf.meanings_vi),
                            tuple(sf.examples),
                        )
                        variants = forms_by_identity.setdefault(form_key, {})
                        variants.setdefault(form_val, set()).add(rel_path)

                # Keep the original parsed evidence for transaction-time rechecks.
                conflict_documents = parsed_docs.copy()
                conflict_sources = db_sources.copy()
                conflicts_by_path: dict[str, list[tuple[tuple[str, str, str], set[str]]]] = {}
                with self.engine.connect() as conn, conn.begin():
                    for form_key, variants in forms_by_identity.items():
                        if len(variants) <= 1:
                            continue
                        paths: set[str] = set().union(*variants.values())
                        if self._committed_date_variants(
                            conn, adapter, form_key, paths, conflict_documents, db_sources,
                        ):
                            # Historical Markdown stays intact. Its already committed
                            # source links must not project old learning content again.
                            continue
                        for path in paths:
                            conflicts_by_path.setdefault(path, []).append((form_key, paths))

                for rel_path in sorted(conflicts_by_path):
                    chash, _doc, _ = parsed_docs[rel_path]
                    parsed_docs[rel_path] = (chash, None, "AMBIGUOUS_CONTENT")
                    sources_invalid += 1

                # 6. Apply database changes for each file
                for file_path in found_files:
                    rel_path = file_path.relative_to(self.root_path).as_posix()
                    if rel_path not in parsed_docs:
                        continue
                    content_hash, doc, doc_err_code = parsed_docs[rel_path]
                    existing_src = db_sources.get(rel_path)

                    # Case A: File is INVALID
                    if doc is None or doc_err_code is not None:
                        with (
                            self.engine.connect().execution_options(
                                sqlite_begin_immediate=True
                            ) as conn,
                            conn.begin(),
                        ):
                            if existing_src is not None:
                                src_id = str(existing_src["id"])
                            else:
                                src_id = f"src_{token_urlsafe(12)}"

                            # Re-check active journal for this source
                            active_journals = conn.exec_driver_sql(
                                "SELECT source_id, effect_plan FROM source_write_journal "
                                "WHERE state IN ('PREPARED', 'SOURCE_REPLACED', 'DEGRADED')"
                            ).all()
                            invalid_protected_forms: set[str] = set()
                            for row in active_journals:
                                invalid_protected_forms.update(_protected_journal_forms(row[1]))
                            if src_id in {str(row[0]) for row in active_journals}:
                                continue
                            if any(form.id in invalid_protected_forms for form in
                                   self.repository.get_forms_for_source(src_id, connection=conn)):
                                continue
                            if doc_err_code == "AMBIGUOUS_CONTENT" and any(
                                self._conflict_snapshot_changed(conn, paths, conflict_sources)
                                for _key, paths in conflicts_by_path[rel_path]
                            ):
                                # The scan predates a committed source/link change.
                                # Defer all remaining participants to a fresh scan.
                                sources_invalid -= 1
                                continue
                            if doc_err_code == "AMBIGUOUS_CONTENT" and all(
                                self._committed_date_variants(
                                    conn, adapter, key, paths, conflict_documents, db_sources,
                                ) for key, paths in conflicts_by_path[rel_path]
                            ):
                                sources_invalid -= 1
                                continue

                            if existing_src is not None:
                                current_row = (
                                    conn.exec_driver_sql(
                                        "SELECT revision, content_hash FROM source_files "
                                        "WHERE id = ?",
                                        (src_id,),
                                    )
                                    .mappings()
                                    .first()
                                )
                                if (
                                    current_row is None
                                    or current_row["revision"] != existing_src["revision"]
                                    or current_row["content_hash"] != existing_src["content_hash"]
                                ):
                                    continue
                            else:
                                existing_by_path = conn.exec_driver_sql(
                                    "SELECT id FROM source_files WHERE relative_path = ?",
                                    (rel_path,),
                                ).first()
                                if existing_by_path is not None:
                                    continue

                            now_ts = _now()
                            inferred_date = _normalize_inferred_date(file_path.name)
                            if existing_src is not None:
                                # If content unchanged and already INVALID, avoid duplicate rev bump
                                if (
                                    existing_src["status"] == "INVALID"
                                    and existing_src["content_hash"] == content_hash
                                    and existing_src["error_code"] == doc_err_code
                                ):
                                    continue
                                new_rev = int(existing_src["revision"]) + 1
                                new_etag = f'"src-r{new_rev}-{src_id}"'
                                conn.exec_driver_sql(
                                    "UPDATE source_files SET status='INVALID', revision=?, "
                                    "etag=?, content_hash=?, last_parsed_at=?, error_code=?, "
                                    "updated_at=? WHERE id=?",
                                    (
                                        new_rev,
                                        new_etag,
                                        content_hash,
                                        now_ts,
                                        doc_err_code,
                                        now_ts,
                                        src_id,
                                    ),
                                )
                            else:
                                new_rev = 1
                                new_etag = f'"src-r1-{src_id}"'
                                conn.exec_driver_sql(
                                    "INSERT INTO source_files (id, relative_path, note_date, "
                                    "status, revision, etag, content_hash, last_parsed_at, "
                                    "error_code, created_at, updated_at) "
                                    "VALUES (?, ?, ?, 'INVALID', 1, ?, ?, ?, ?, ?, ?)",
                                    (
                                        src_id,
                                        rel_path,
                                        inferred_date,
                                        new_etag,
                                        content_hash,
                                        now_ts,
                                        doc_err_code,
                                        now_ts,
                                        now_ts,
                                    ),
                                )

                            src_model = SourceFile(
                                id=src_id,
                                relative_path=rel_path,
                                note_date=str(existing_src["note_date"])
                                if existing_src
                                else inferred_date,
                                status="INVALID",
                                revision=new_rev,
                                etag=new_etag,
                                content_hash=content_hash,
                                last_parsed_at=now_ts,
                                error_code=doc_err_code,
                                created_at=now_ts,
                                updated_at=now_ts,
                            )
                            affected_forms = self.repository.get_forms_for_source(
                                src_id, connection=conn
                            )
                            self.search_index.update_source(
                                src_model, affected_forms, connection=conn
                            )
                            if doc_err_code == "AMBIGUOUS_CONTENT":
                                # Our own invalidations are expected by the next
                                # participant's CAS; concurrent mutations are not.
                                conflict_sources[rel_path] = {
                                    "id": src_id, "relative_path": rel_path,
                                    "status": "INVALID", "revision": new_rev,
                                    "content_hash": content_hash,
                                }
                            if max_rev_seen is None or new_rev > max_rev_seen:
                                max_rev_seen = new_rev
                            committed_effects = True
                        continue

                    # Case B: File is VALID
                    # Check for byte identity / echo suppression
                    if (
                        existing_src is not None
                        and existing_src["status"] == "VALID"
                        and existing_src["content_hash"] == content_hash
                    ):
                        # Identical bytes: no revision advance, no card reset
                        continue

                    with (
                        self.engine.connect().execution_options(
                            sqlite_begin_immediate=True
                        ) as conn,
                        conn.begin(),
                    ):
                        if existing_src is not None:
                            src_id = str(existing_src["id"])
                        else:
                            src_id = f"src_{token_urlsafe(12)}"

                        # Re-query active journal records
                        active_journals = conn.exec_driver_sql(
                            "SELECT source_id, effect_plan FROM source_write_journal "
                            "WHERE state IN ('PREPARED', 'SOURCE_REPLACED', 'DEGRADED')"
                        ).all()
                        active_protected_forms: set[str] = set()
                        for row in active_journals:
                            active_protected_forms.update(_protected_journal_forms(row[1]))
                        active_source_ids = {str(r[0]) for r in active_journals}
                        if src_id in active_source_ids or (
                            existing_src is not None
                            and str(existing_src["id"]) in active_source_ids
                        ):
                            continue

                        # F1: Whole-source deferral when active journal fencing protects a form.
                        current_linked = {
                            f.id: f
                            for f in self.repository.get_forms_for_source(src_id, connection=conn)
                        }
                        if any(wid in active_protected_forms for wid in current_linked):
                            continue

                        has_protected_form = False
                        for s_form in doc.semantic_forms:
                            fam_row = conn.exec_driver_sql(
                                "SELECT id FROM word_families WHERE root_lemma = ?",
                                (s_form.family_root,),
                            ).first()
                            if fam_row is not None:
                                norm_lemma = s_form.lemma.strip().lower()
                                form_row = conn.exec_driver_sql(
                                    "SELECT id FROM word_forms WHERE normalized_lemma = ? "
                                    "AND part_of_speech = ? AND family_id = ?",
                                    (norm_lemma, s_form.part_of_speech, fam_row[0]),
                                ).first()
                                if (
                                    form_row is not None
                                    and str(form_row[0]) in active_protected_forms
                                ):
                                    has_protected_form = True
                                    break
                        if has_protected_form:
                            continue

                        if existing_src is not None:
                            current_row = (
                                conn.exec_driver_sql(
                                    "SELECT revision, content_hash FROM source_files WHERE id = ?",
                                    (src_id,),
                                )
                                .mappings()
                                .first()
                            )
                            if (
                                current_row is None
                                or current_row["revision"] != existing_src["revision"]
                                or current_row["content_hash"] != existing_src["content_hash"]
                            ):
                                continue
                            new_rev = int(existing_src["revision"]) + 1
                        else:
                            existing_by_path = conn.exec_driver_sql(
                                "SELECT id FROM source_files WHERE relative_path = ?",
                                (rel_path,),
                            ).first()
                            if existing_by_path is not None:
                                continue
                            new_rev = 1

                        now_ts = _now()
                        new_etag = f'"src-r{new_rev}-{src_id}"'

                        source_file = self.repository.save_source_file(
                            source_id=src_id,
                            relative_path=rel_path,
                            note_date=doc.note_date,
                            status="VALID",
                            revision=new_rev,
                            etag=new_etag,
                            content_hash=content_hash,
                            last_parsed_at=now_ts,
                            error_code=None,
                            connection=conn,
                        )

                        if max_rev_seen is None or new_rev > max_rev_seen:
                            max_rev_seen = new_rev

                        active_form_ids: set[str] = set()

                        for s_form in doc.semantic_forms:
                            family = self.repository.get_or_create_family(
                                s_form.family_root, connection=conn
                            )
                            old = self.repository.get_word_form_by_identity(
                                s_form.lemma, s_form.part_of_speech, family.id, connection=conn
                            )

                            en, vi, examples, ipa_status, link_status = _projection_values(s_form, old)
                            needs_reset = old is not None and _learning_values(old) != (
                                s_form.meanings_en,
                                s_form.meanings_vi,
                                s_form.examples,
                            )
                            changed = _content_changed(s_form, old)

                            saved_form: WordForm | None = (
                                self.repository.save_canonical_word_form(
                                    lemma=s_form.lemma,
                                    part_of_speech=s_form.part_of_speech,
                                    family_id=family.id,
                                    meanings_en=en,
                                    meanings_vi=vi,
                                    examples=examples,
                                    ipa_us=s_form.ipa_us,
                                    ipa_status=ipa_status,
                                    cambridge_url=s_form.cambridge_url,
                                    cambridge_status=link_status,
                                    word_form_id=old.id if old else None,
                                    connection=conn,
                                )
                                if changed
                                else old
                            )
                            if saved_form is None:
                                raise RuntimeError(
                                    f"Canonical form projection failed for {s_form.lemma}"
                                )

                            wf_id = saved_form.id
                            active_form_ids.add(wf_id)

                            card_id = conn.exec_driver_sql(
                                "SELECT card_id FROM review_cards WHERE word_form_id=?", (wf_id,)
                            ).scalar_one_or_none()
                            if card_id is not None:
                                if needs_reset:
                                    reset_card_state(conn, str(card_id))
                            else:
                                ensure_card(
                                    conn, card_id=f"card_{token_urlsafe(12)}", word_form_id=wf_id
                                )

                            self.repository.link_word_form_to_source(
                                wf_id, src_id, doc.note_date, connection=conn
                            )

                        # Unlink removed forms from this source
                        for old_wid in current_linked:
                            if old_wid not in active_form_ids:
                                self.repository.unlink_source_from_form(
                                    old_wid, src_id, connection=conn
                                )

                        all_affected_ids = active_form_ids | set(current_linked.keys())
                        affected_wfs = [
                            wf
                            for wf in [
                                self.repository.get_word_form(wid, connection=conn)
                                for wid in all_affected_ids
                            ]
                            if wf is not None
                        ]
                        self.search_index.update_source(source_file, affected_wfs, connection=conn)
                        committed_effects = True

                # 7. Complete the operation in OperationLedger
                def validate_receipt_journals(connection: Connection) -> None:
                    # Validate under the receipt's writer lock, including unchanged-byte runs.
                    active_journals = connection.exec_driver_sql(
                        "SELECT effect_plan FROM source_write_journal "
                        "WHERE state IN ('PREPARED', 'SOURCE_REPLACED', 'DEGRADED')"
                    ).all()
                    for row in active_journals:
                        _protected_journal_forms(row[0])

                finished_at = _now()
                current_agg_rev = self._get_aggregate_source_revision()
                rev_str = str(current_agg_rev)
                result_ref = f"{sync_id}.{reason}.{sources_scanned}.{sources_invalid}.{rev_str}"

                self.operation_ledger.complete(
                    op_id,
                    response_status=202,
                    result_ref=result_ref,
                    local_write=validate_receipt_journals,
                )

                sync_res = SyncResult(
                    id=sync_id,
                    operation_id=op_id,
                    status="COMPLETED",
                    reason=reason,
                    sources_scanned=sources_scanned,
                    sources_invalid=sources_invalid,
                    started_at=started_at,
                    source_revision=current_agg_rev,
                    finished_at=finished_at,
                )
                self._sync_cache[sync_id] = sync_res
                return sync_res
            except Exception as exc:
                finished_at = _now()
                current_agg_rev = self._get_aggregate_source_revision()
                failed_result_ref = (
                    f"{sync_id}.{reason}.{sources_scanned}.{sources_invalid}.{current_agg_rev}"
                )
                failed_res = SyncResult(
                    id=sync_id,
                    operation_id=op_id,
                    status="FAILED",
                    reason=reason,
                    sources_scanned=sources_scanned,
                    sources_invalid=sources_invalid,
                    started_at=started_at,
                    source_revision=current_agg_rev,
                    finished_at=finished_at,
                    error_message=str(exc),
                )
                self._sync_cache[sync_id] = failed_res
                with contextlib.suppress(Exception):
                    with (
                        self.engine.connect().execution_options(
                            sqlite_begin_immediate=True
                        ) as conn,
                        conn.begin(),
                    ):
                        conn.exec_driver_sql(
                            "UPDATE operations SET result_ref=?, updated_at=? WHERE operation_id=?",
                            (failed_result_ref, finished_at, op_id),
                        )
                    self.operation_ledger.record_failure(
                        op_id,
                        error_category="INTERNAL_ERROR",
                        response_status=500,
                        unknown=committed_effects,
                    )
                raise

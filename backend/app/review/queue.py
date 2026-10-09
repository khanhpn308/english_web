"""Local review queues and atomic event orchestration, independent of AI.

Pagination uses the signed-query pattern from T027, with separate review
state evidence. One SQLite read snapshot covers membership and page selection.
Source and schedule changes invalidate continuation rather than mixing pages.
"""

import base64
import hashlib
import hmac
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe
from typing import Any, Literal, Protocol
from zoneinfo import ZoneInfo

from backend.app.review.models import get_card, record_review, source_references
from backend.app.review.srs import PRODUCT_TIMEZONE, require_aware
from sqlalchemy import Connection, Engine
from sqlalchemy.exc import SQLAlchemyError

QueueSort = Literal["dueAt", "lemma"]
QueueDirection = Literal["ASC", "DESC"]
CardState = Literal["NEW", "LEARNED"]


class QueueCursorExpired(ValueError):
    """Malformed, foreign or stale review continuation."""


class ReviewRejected(RuntimeError):
    """Safe local review refusal, optionally linked to its durable operation."""

    def __init__(self, status_code: int, code: str, operation_id: str | None = None) -> None:
        super().__init__(code)
        self.status_code = status_code
        self.code = code
        self.operation_id = operation_id


class ReviewReceipt(Protocol):
    """Read-only T014 receipt fields consumed by review orchestration."""

    @property
    def operation_id(self) -> str: ...

    @property
    def status(self) -> str: ...

    @property
    def result_ref(self) -> str | None: ...

    @property
    def response_status(self) -> int | None: ...

    @property
    def error_category(self) -> str | None: ...


class ReviewClaim(Protocol):
    @property
    def operation(self) -> ReviewReceipt: ...

    @property
    def replayed(self) -> bool: ...


class ReviewLedger(Protocol):
    """Structural T014 boundary; composition supplies the existing real ledger.

    Source sync already imports review models. Importing application.operations
    here would create a package cycle. This port preserves that ownership rule
    without implementing another ledger or changing T014.
    """

    def claim(
        self, *, kind: str, key: str, method: str, path: str,
        body: Mapping[str, object], preconditions: Mapping[str, object],
    ) -> ReviewClaim: ...

    def complete(
        self, operation_id: str, *, response_status: int, result_ref: str,
        local_write: Callable[[Connection], None] | None = None,
    ) -> ReviewReceipt: ...

    def record_failure(
        self, operation_id: str, *, error_category: str, response_status: int,
        unknown: bool = False,
    ) -> ReviewReceipt: ...


@dataclass(frozen=True)
class QueuePage:
    data: list[dict[str, Any]]
    next_cursor: str | None
    page_size: int
    has_more: bool
    sort_by: QueueSort
    sort_order: QueueDirection


def utc_text(instant: datetime) -> str:
    require_aware(instant)
    return instant.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    if not value or any(
        char not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
        for char in value
    ):
        raise ValueError("Invalid cursor encoding")
    decoded = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
    if _b64(decoded) != value:
        raise ValueError("Noncanonical cursor encoding")
    return decoded


class ReviewService:
    """Serve active cards using server time and durable source relationships."""

    def __init__(
        self,
        engine: Engine,
        *,
        signing_key: bytes,
        ledger: ReviewLedger,
        conflict_type: type[Exception],
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if len(signing_key) < 32:
            raise ValueError("Review cursor key requires at least 256 bits")
        self.engine = engine
        self._signing_key = signing_key
        self.clock = clock or (lambda: datetime.now(UTC))
        self.ledger = ledger
        self._conflict_type = conflict_type

    @staticmethod
    def _revision(conn: Connection, now: datetime) -> str:
        """Bound both retained identities and live eligibility, with bounded memory.

        Include due membership so elapsed server time also expires a cursor.
        A Bangkok day change invalidates it even when no card becomes due.
        """
        digest = hashlib.sha256()
        statements = (
            (
                "SELECT c.card_id,c.word_form_id,c.box,c.due_at,c.queue_revision,"
                "f.lemma,f.revision FROM review_cards c JOIN word_forms f "
                "ON f.id=c.word_form_id ORDER BY c.card_id",
                (),
            ),
            ("SELECT id,note_date,status,revision,etag FROM source_files ORDER BY id", ()),
            (
                "SELECT word_form_id,source_id,note_date FROM word_form_sources "
                "ORDER BY word_form_id,source_id",
                (),
            ),
            (
                "SELECT card_id FROM review_cards WHERE box=0 OR due_at<=? ORDER BY card_id",
                (utc_text(now),),
            ),
        )
        digest.update(now.astimezone(ZoneInfo(PRODUCT_TIMEZONE)).date().isoformat().encode())
        for sql, params in statements:
            digest.update(b"\x00")
            for row in conn.exec_driver_sql(sql, params):
                value = json.dumps(list(row), ensure_ascii=True, separators=(",", ":")).encode()
                digest.update(len(value).to_bytes(8, "big"))
                digest.update(value)
        return digest.hexdigest()

    def _encode(self, query: dict[str, object], revision: str, position: list[str]) -> str:
        payload = {"v": 1, "kind": "review", "q": query, "r": revision, "p": position}
        encoded = _b64(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
        signature = hmac.new(self._signing_key, encoded.encode(), hashlib.sha256).digest()
        return encoded + "." + _b64(signature)

    def _decode(self, cursor: str, query: dict[str, object], revision: str) -> tuple[str, str]:
        try:
            # Server-created cursors contain only bounded filters and IDs. Reject
            # oversized opaque input before base64/JSON allocation.
            if len(cursor) > 8192:
                raise ValueError("Oversized cursor")
            encoded, signature = cursor.split(".", 1)
            expected = hmac.new(self._signing_key, encoded.encode("ascii"), hashlib.sha256).digest()
            if not hmac.compare_digest(expected, _unb64(signature)):
                raise ValueError("Invalid signature")
            payload = json.loads(_unb64(encoded))
            if (
                not isinstance(payload, dict)
                or payload.get("v") != 1
                or payload.get("kind") != "review"
                or payload.get("q") != query
                or payload.get("r") != revision
            ):
                raise ValueError("Cursor state mismatch")
            position = payload.get("p")
            if (
                not isinstance(position, list)
                or len(position) != 2
                or not all(isinstance(value, str) for value in position)
            ):
                raise ValueError("Invalid position")
            return str(position[0]), str(position[1])
        except (ValueError, TypeError, UnicodeError, KeyError) as error:
            raise QueueCursorExpired from error

    def queue(
        self,
        *,
        note_date: str | None = None,
        due_only: bool = True,
        card_state: CardState | None = None,
        page_size: int = 50,
        sort_by: QueueSort = "dueAt",
        sort_order: QueueDirection = "ASC",
        cursor: str | None = None,
    ) -> QueuePage:
        now = self.clock()
        query: dict[str, object] = {
            "noteDate": note_date, "dueOnly": due_only, "cardState": card_state,
            "sortBy": sort_by, "sortOrder": sort_order,
        }
        # All interpolated SQL identifiers/operators are internal allowlisted literals.
        primary = "COALESCE(c.due_at,'')" if sort_by == "dueAt" else "f.lemma"
        direction = "DESC" if sort_order == "DESC" else "ASC"
        comparison = "<" if direction == "DESC" else ">"
        with self.engine.connect() as conn, conn.begin():
            revision = self._revision(conn, now)
            conditions = [
                "EXISTS (SELECT 1 FROM word_form_sources w JOIN source_files s "
                "ON s.id=w.source_id WHERE w.word_form_id=c.word_form_id AND s.status='VALID')"
            ]
            params: list[object] = []
            if note_date is not None:
                conditions.append(
                    "EXISTS (SELECT 1 FROM word_form_sources w JOIN source_files s "
                    "ON s.id=w.source_id WHERE w.word_form_id=c.word_form_id "
                    "AND s.status='VALID' AND w.note_date=?)"
                )
                params.append(note_date)
            # FR-REV-05: selecting a note day always restricts study to new/due.
            if due_only or note_date is not None:
                conditions.append("(c.box=0 OR c.due_at<=?)")
                params.append(utc_text(now))
            if card_state is not None:
                conditions.append("c.box=0" if card_state == "NEW" else "c.box>0")
            if cursor is not None:
                value, card_id = self._decode(cursor, query, revision)
                conditions.append(
                    f"({primary} {comparison} ? OR ({primary}=? AND c.card_id>?))"
                )
                params.extend([value, value, card_id])
            rows = conn.exec_driver_sql(
                "SELECT c.card_id,c.word_form_id,c.box,c.due_at,c.queue_revision,f.lemma,"
                f"{primary} AS sort_value FROM review_cards c JOIN word_forms f "
                "ON f.id=c.word_form_id WHERE " + " AND ".join(conditions)
                + f" ORDER BY {primary} {direction},c.card_id ASC LIMIT ?",
                tuple([*params, page_size + 1]),
            ).mappings().all()
            has_more = len(rows) > page_size
            selected = rows[:page_size]
            data: list[dict[str, Any]] = []
            for row in selected:
                dates = conn.exec_driver_sql(
                    "SELECT DISTINCT w.note_date FROM word_form_sources w JOIN source_files s "
                    "ON s.id=w.source_id WHERE w.word_form_id=? AND s.status='VALID' "
                    "ORDER BY w.note_date", (row["word_form_id"],),
                ).scalars().all()
                data.append({
                    "cardId": row["card_id"], "wordFormId": row["word_form_id"],
                    "lemma": row["lemma"], "noteDates": list(dates),
                    "state": "NEW" if row["box"] == 0 else "LEARNED",
                    "dueAt": row["due_at"], "queueRevision": row["queue_revision"],
                })
            next_cursor = None
            if has_more:
                last = selected[-1]
                next_cursor = self._encode(query, revision, [last["sort_value"], last["card_id"]])
        # Recheck after releasing the read snapshot, as in T027. A source invalidated
        # during selection must not return cached study text or a mixed-state cursor.
        with self.engine.connect() as conn:
            if self._revision(conn, self.clock()) != revision:
                raise QueueCursorExpired
        return QueuePage(data, next_cursor, page_size, has_more, sort_by, sort_order)

    def _restore_event(
        self, operation: ReviewReceipt, card_id: str, diagnostic: str | None = None,
    ) -> dict[str, object]:
        if operation.status == "FAILED":
            raise ReviewRejected(
                operation.response_status or 409,
                operation.error_category or "IDEMPOTENCY_IN_FLIGHT",
                operation.operation_id,
            )
        if operation.status != "SUCCEEDED" or operation.response_status != 201:
            raise ReviewRejected(409, "IDEMPOTENCY_IN_FLIGHT", operation.operation_id)
        with self.engine.connect() as conn:
            row = conn.exec_driver_sql(
                "SELECT id,card_id,source,rating,reviewed_at,next_due_at,operation_id,"
                "attempt_id,question_id FROM review_events "
                "WHERE id=? AND operation_id=? AND card_id=?",
                (operation.result_ref, operation.operation_id, card_id),
            ).mappings().first()
            if diagnostic is not None:
                available = conn.exec_driver_sql(
                    "SELECT 1 FROM sqlite_master WHERE type='table' "
                    "AND name='review_event_diagnostics'"
                ).scalar_one_or_none()
                retained = None
                if available is not None:
                    retained = conn.exec_driver_sql(
                        "SELECT client_occurred_at FROM review_event_diagnostics WHERE event_id=?",
                        (operation.result_ref,),
                    ).scalar_one_or_none()
                if retained != diagnostic:
                    raise ReviewRejected(409, "IDEMPOTENCY_IN_FLIGHT", operation.operation_id)
        # A terminal flag without its immutable event is not evidence of success.
        if row is None:
            raise ReviewRejected(409, "IDEMPOTENCY_IN_FLIGHT", operation.operation_id)
        result: dict[str, object] = {
            "id": row["id"], "cardId": row["card_id"], "source": row["source"],
            "rating": row["rating"], "reviewedAt": row["reviewed_at"],
            "nextDueAt": row["next_due_at"], "operationId": row["operation_id"],
        }
        for api_name, column in (("attemptId", "attempt_id"), ("questionId", "question_id")):
            if row[column] is not None:
                result[api_name] = row[column]
        return result

    def _storage_failure(self, operation_id: str) -> None:
        """Retain ambiguity if commit evidence cannot be read. Never redispatch."""
        try:
            self.ledger.record_failure(
                operation_id, error_category="STORAGE_BUSY", response_status=503, unknown=True,
            )
        except (SQLAlchemyError, self._conflict_type):
            # The original durable claim remains available to startup recovery.
            # A SUCCEEDED receipt is immutable even if reading its response failed.
            return

    def review(
        self,
        *,
        card_id: str,
        key: str,
        expected_revision: int,
        body: dict[str, object],
        rating: str,
        source: Literal["FLASHCARD", "QUIZ"],
        client_occurred_at: datetime | None = None,
        attempt_id: str | None = None,
        question_id: str | None = None,
    ) -> dict[str, object]:
        claim = self.ledger.claim(
            kind="REVIEW", key=key, method="POST", path=f"/api/v1/cards/{card_id}/reviews",
            body=body, preconditions={"queueRevision": expected_revision},
        )
        operation_id = claim.operation.operation_id
        try:
            diagnostic = utc_text(client_occurred_at) if client_occurred_at is not None else None
            if claim.replayed:
                # Immutable intent was validated when committed. Replay must not
                # re-evaluate its diagnostic age, source validity or card revision.
                return self._restore_event(claim.operation, card_id, diagnostic)
            event_id = f"review_{token_urlsafe(18)}"

            def write(conn: Connection) -> None:
                # Sample scheduling time only after obtaining the writer lock.
                now = self.clock()
                require_aware(now)
                if client_occurred_at is not None:
                    require_aware(client_occurred_at)
                    if not (now - timedelta(hours=8) <= client_occurred_at <= now):
                        raise ReviewRejected(422, "VALIDATION_ERROR", operation_id)
                card = get_card(conn, card_id)
                if card is None or not any(
                    ref.status == "VALID" for ref in source_references(conn, card.word_form_id)
                ):
                    raise ReviewRejected(404, "NOT_FOUND", operation_id)
                if card.queue_revision != expected_revision:
                    raise ReviewRejected(409, "REVISION_CONFLICT", operation_id)
                if source == "QUIZ":
                    # Local session ownership alone does not establish object membership.
                    membership = conn.exec_driver_sql(
                        "SELECT q.word_form_id FROM quiz_questions q JOIN quiz_attempts a "
                        "ON a.id=q.attempt_id WHERE q.id=? AND a.id=?",
                        (question_id, attempt_id),
                    ).scalar_one_or_none()
                    if membership != card.word_form_id:
                        raise ReviewRejected(422, "CROSS_RESOURCE_MISMATCH", operation_id)
                event = record_review(
                    conn, card_id=card_id, event_id=event_id, operation_id=operation_id,
                    source=source, rating=rating, reviewed_at=now,
                    attempt_id=attempt_id, question_id=question_id,
                )
                if event is None:
                    raise RuntimeError("A validated rating must produce a review event")
                if diagnostic is not None:
                    # The callback shares the event/SRS/receipt writer transaction.
                    # A failed INSERT rolls back all effects before any success receipt.
                    conn.exec_driver_sql(
                        "INSERT INTO review_event_diagnostics (event_id,client_occurred_at) "
                        "VALUES (?,?)", (event.id, diagnostic),
                    )

            operation = self.ledger.complete(
                operation_id, response_status=201, result_ref=event_id, local_write=write,
            )
            return self._restore_event(operation, card_id, diagnostic)
        except ReviewRejected as error:
            if not claim.replayed and error.code != "IDEMPOTENCY_IN_FLIGHT":
                try:
                    self.ledger.record_failure(
                        operation_id, error_category=error.code, response_status=error.status_code,
                    )
                except SQLAlchemyError:
                    self._storage_failure(operation_id)
                    raise ReviewRejected(503, "STORAGE_BUSY", operation_id) from None
            raise
        except SQLAlchemyError:
            self._storage_failure(operation_id)
            raise ReviewRejected(503, "STORAGE_BUSY", operation_id) from None
        except self._conflict_type:
            raise
        except (ValueError, RuntimeError, OverflowError, TypeError):
            try:
                self.ledger.record_failure(
                    operation_id, error_category="INTERNAL_ERROR", response_status=500, unknown=True,
                )
            except (SQLAlchemyError, self._conflict_type):
                self._storage_failure(operation_id)
            raise ReviewRejected(500, "INTERNAL_ERROR", operation_id) from None

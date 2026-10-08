"""Application service for the local word-form search and detail reads."""

import base64
import hashlib
import hmac
import json
from collections.abc import Iterator
from dataclasses import dataclass
from functools import cmp_to_key
from heapq import nsmallest
from threading import RLock
from typing import Any, Literal

from backend.app.vocabulary.models import SourceFile, WordForm
from backend.app.vocabulary.repository import VocabularyRepository
from backend.app.vocabulary.search_index import (
    PROJECTION_VERSION,
    ProjectionVersionMismatchError,
    SearchIndex,
    SearchResultItem,
)
from sqlalchemy import Engine

CursorSort = Literal["relevance", "updatedAt", "lemma"]
CursorDirection = Literal["ASC", "DESC"]
CURSOR_VERSION = 1
READ_BATCH_SIZE = 64


class CursorExpiredError(ValueError):
    """The cursor is malformed, tampered with, stale, or bound to another query."""


class SearchQueryError(ValueError):
    """The requested search state is not supported by the endpoint contract."""


@dataclass(frozen=True)
class SearchPage:
    data: list[dict[str, Any]]
    next_cursor: str | None
    page_size: int
    has_more: bool
    sort_by: CursorSort
    sort_order: CursorDirection


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    if not value or any(
        char not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
        for char in value
    ):
        raise ValueError("invalid base64")
    decoded = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
    if _b64(decoded) != value:
        raise ValueError("noncanonical base64")
    return decoded


class SearchService:
    """Synchronously project canonical storage and serve bounded, cursor-based reads."""

    def __init__(self, engine: Engine, *, signing_key: bytes) -> None:
        if len(signing_key) < 32:
            raise ValueError("cursor signing key must contain at least 256 bits")
        self.engine = engine
        self.repository = VocabularyRepository(engine)
        self.index = SearchIndex(engine)
        self._signing_key = signing_key
        self._state_token: str | None = None
        self._lock = RLock()

    def _iter_ids(self, *, sources: bool) -> Iterator[str]:
        # Identifiers are internal literals, never browser-controlled SQL fragments.
        sql = (
            "SELECT id FROM source_files WHERE id > ? ORDER BY id LIMIT ?"
            if sources
            else "SELECT id FROM word_forms WHERE id > ? ORDER BY id LIMIT ?"
        )
        after = ""
        while True:
            with self.engine.connect() as connection:
                rows = connection.exec_driver_sql(sql, (after, READ_BATCH_SIZE)).all()
            if not rows:
                return
            for row in rows:
                yield str(row[0])
            after = str(rows[-1][0])

    def _iter_sources(self) -> Iterator[SourceFile]:
        for source_id in self._iter_ids(sources=True):
            source = self.repository.get_source_file(source_id)
            if source is not None:
                yield source

    def _iter_forms(self) -> Iterator[WordForm]:
        for form_id in self._iter_ids(sources=False):
            form = self.repository.get_word_form(form_id)
            if form is not None:
                yield form

    def _revision(self) -> str:
        """Hash deterministic current state including effective relationship membership.

        Repository reads expose joined source references; link/unlink does not need
        a source/form revision bump to change this evidence. Hash incrementally so
        the fingerprint never requires a population-sized metadata list.
        """
        digest = hashlib.sha256()

        def include(value: object) -> None:
            encoded = json.dumps(
                value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
            ).encode("utf-8")
            digest.update(len(encoded).to_bytes(8, "big"))
            digest.update(encoded)

        include({"projection": self.index.get_version()})
        for source in self._iter_sources():
            include(
                {
                    "source": source.id,
                    "revision": source.revision,
                    "status": source.status,
                    "etag": source.etag,
                    "noteDate": source.note_date,
                }
            )
        for form in self._iter_forms():
            include(
                {
                    "form": form.id,
                    "revision": form.revision,
                    "updatedAt": form.updated_at,
                    "refs": [
                        ref.to_dict()
                        for ref in sorted(form.source_refs, key=lambda ref: ref.source_id)
                    ],
                }
            )
        return digest.hexdigest()

    def refresh(self, revision: str | None = None) -> None:
        """Refresh the disposable projection without retaining canonical populations."""
        if self.index.get_version() != PROJECTION_VERSION:
            raise ProjectionVersionMismatchError("Incompatible search projection")
        state_token = revision if revision is not None else self._revision()
        if state_token == self._state_token:
            return
        self.index.rebuild([], [])
        for source in self._iter_sources():
            self.index.build_from_forms([], [source])
        for form in self._iter_forms():
            # Fresh repository references carry current source status/note dates.
            self.index.build_from_forms([form], [])
        self._state_token = state_token

    @staticmethod
    def _fingerprint(filters: dict[str, str | None]) -> str:
        raw = json.dumps(filters, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode(
            "utf-8"
        )
        return hashlib.sha256(raw).hexdigest()

    def _encode_cursor(
        self,
        *,
        fingerprint: str,
        sort_by: CursorSort,
        sort_order: CursorDirection,
        position: tuple[float | str, str],
        revision: str,
    ) -> str:
        payload = {
            "v": CURSOR_VERSION,
            "f": fingerprint,
            "s": sort_by,
            "d": sort_order,
            "p": [position[0], position[1]],
            "r": revision,
        }
        encoded = _b64(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
        signature = _b64(
            hmac.new(self._signing_key, encoded.encode("ascii"), hashlib.sha256).digest()
        )
        return f"{encoded}.{signature}"

    def _decode_cursor(
        self,
        cursor: str,
        *,
        fingerprint: str,
        sort_by: CursorSort,
        sort_order: CursorDirection,
        revision: str,
    ) -> tuple[float | str, str]:
        try:
            encoded, signature = cursor.split(".", 1)
            expected = hmac.new(self._signing_key, encoded.encode("ascii"), hashlib.sha256).digest()
            if not hmac.compare_digest(expected, _unb64(signature)):
                raise CursorExpiredError
            payload = json.loads(_unb64(encoded).decode("utf-8"))
            if (
                payload.get("v") != CURSOR_VERSION
                or payload.get("f") != fingerprint
                or payload.get("s") != sort_by
                or payload.get("d") != sort_order
                or payload.get("r") != revision
                or not isinstance(payload.get("p"), list)
                or len(payload["p"]) != 2
                or not isinstance(payload["p"][1], str)
            ):
                raise CursorExpiredError
            primary = payload["p"][0]
            if sort_by == "relevance":
                if not isinstance(primary, (int, float)) or isinstance(primary, bool):
                    raise CursorExpiredError
                primary = float(primary)
            elif not isinstance(primary, str):
                raise CursorExpiredError
            return primary, payload["p"][1]
        except CursorExpiredError:
            raise
        except (
            ValueError,
            TypeError,
            KeyError,
            IndexError,
            json.JSONDecodeError,
            UnicodeError,
        ) as exc:
            raise CursorExpiredError from exc

    @staticmethod
    def _active(form: WordForm) -> bool:
        return any(reference.status == "VALID" for reference in form.source_refs)

    @staticmethod
    def _summary(item: SearchResultItem) -> dict[str, Any]:
        return item.to_dict()

    def _items_for_query(self, meaning_vi: str | None) -> Iterator[SearchResultItem]:
        if meaning_vi is not None:
            yield from self.index.iter_search_candidates(meaning_vi)
            return
        for form in self._iter_forms():
            if self._active(form):
                yield SearchResultItem(
                    word_form_id=form.id,
                    lemma=form.lemma,
                    part_of_speech=form.part_of_speech,
                    meaning_vi_match=form.meanings_vi[0].text if form.meanings_vi else "",
                    verification_summary=form.verification_summary,
                    note_dates=tuple(
                        sorted({ref.note_date for ref in form.source_refs if ref.status == "VALID"})
                    ),
                    revision=form.revision,
                    updated_at=form.updated_at,
                )

    @staticmethod
    def _matches(
        item: SearchResultItem,
        form: WordForm,
        *,
        lemma: str | None,
        part_of_speech: str | None,
        verification_status: str | None,
        note_date: str | None,
        source_status: str | None,
    ) -> bool:
        if lemma is not None and lemma.casefold() not in form.lemma.casefold():
            return False
        if part_of_speech is not None and form.part_of_speech != part_of_speech:
            return False
        if verification_status is not None and form.verification_summary != verification_status:
            return False
        if note_date is not None and not any(
            reference.status == "VALID" and reference.note_date == note_date
            for reference in form.source_refs
        ):
            return False
        if source_status is not None and not any(
            reference.status == source_status for reference in form.source_refs
        ):
            return False
        return item.word_form_id == form.id

    @staticmethod
    def _primary(item: SearchResultItem, sort_by: CursorSort) -> float | str:
        if sort_by == "relevance":
            return item.score
        if sort_by == "updatedAt":
            return item.updated_at
        return item.lemma.casefold()

    def search(
        self,
        *,
        meaning_vi: str | None,
        lemma: str | None,
        part_of_speech: str | None,
        verification_status: str | None,
        note_date: str | None,
        source_status: str | None,
        page_size: int,
        sort_by: CursorSort,
        sort_order: CursorDirection,
        cursor: str | None,
    ) -> SearchPage:
        with self._lock:
            revision = self._revision()
            fingerprint = self._fingerprint(
                {
                    "meaningVi": meaning_vi,
                    "lemma": lemma,
                    "partOfSpeech": part_of_speech,
                    "verificationStatus": verification_status,
                    "noteDate": note_date,
                    "sourceStatus": source_status,
                }
                | {"sortBy": sort_by, "sortOrder": sort_order}
            )
            position = None
            if cursor is not None:
                position = self._decode_cursor(
                    cursor,
                    fingerprint=fingerprint,
                    sort_by=sort_by,
                    sort_order=sort_order,
                    revision=revision,
                )
            self.refresh(revision)

            def compare_positions(
                left: tuple[float | str, str], right: tuple[float | str, str]
            ) -> int:
                if left[0] != right[0]:
                    before = (
                        float(left[0]) < float(right[0])
                        if sort_by == "relevance"
                        else str(left[0]) < str(right[0])
                    )
                    result = -1 if before else 1
                    return -result if sort_order == "DESC" else result
                return (left[1] > right[1]) - (left[1] < right[1])

            def eligible() -> Iterator[SearchResultItem]:
                for item in self._items_for_query(meaning_vi):
                    item_position = (self._primary(item, sort_by), item.word_form_id)
                    if position is not None and compare_positions(item_position, position) <= 0:
                        continue
                    form = self.repository.get_word_form(item.word_form_id)
                    if (
                        form is not None
                        and self._active(form)
                        and self._matches(
                            item,
                            form,
                            lemma=lemma,
                            part_of_speech=part_of_speech,
                            verification_status=verification_status,
                            note_date=note_date,
                            source_status=source_status,
                        )
                    ):
                        yield item

            def compare_items(left: SearchResultItem, right: SearchResultItem) -> int:
                return compare_positions(
                    (self._primary(left, sort_by), left.word_form_id),
                    (self._primary(right, sort_by), right.word_form_id),
                )

            # nsmallest consumes the complete stream with a heap of at most pageSize+1.
            selected = nsmallest(page_size + 1, eligible(), key=cmp_to_key(compare_items))
            has_more = len(selected) > page_size
            page = selected[:page_size]
            # A source change while scanning must not issue a cursor for mixed revisions.
            if self._revision() != revision:
                raise CursorExpiredError
            next_cursor = None
            if has_more and page:
                last = page[-1]
                next_cursor = self._encode_cursor(
                    fingerprint=fingerprint,
                    sort_by=sort_by,
                    sort_order=sort_order,
                    position=(self._primary(last, sort_by), last.word_form_id),
                    revision=revision,
                )
            return SearchPage(
                data=[self._summary(item) for item in page],
                next_cursor=next_cursor,
                page_size=page_size,
                has_more=has_more,
                sort_by=sort_by,
                sort_order=sort_order,
            )

    def detail(self, word_form_id: str) -> dict[str, Any] | None:
        form = self.repository.get_word_form(word_form_id)
        if form is None:
            return None
        active = self._active(form)
        with self.engine.connect() as connection:
            card = (
                connection.exec_driver_sql(
                    "SELECT card_id, box, due_at FROM review_cards WHERE word_form_id = ?",
                    (word_form_id,),
                )
                .mappings()
                .first()
            )
        return {
            "id": form.id,
            "familyId": form.family_id,
            "lemma": form.lemma,
            "partOfSpeech": form.part_of_speech,
            "meaningsEn": [meaning.to_dict() for meaning in form.meanings_en] if active else [],
            "meaningsVi": [meaning.to_dict() for meaning in form.meanings_vi] if active else [],
            "examples": [example.to_dict() for example in form.examples] if active else [],
            "ipaUs": form.ipa_us if active else None,
            "cambridgeUrl": form.cambridge_url if active else None,
            "sourceRefs": [reference.to_dict() for reference in form.source_refs],
            "card": (
                {
                    "id": card["card_id"],
                    "state": "NEW" if card["box"] == 0 else "LEARNED",
                    "dueAt": str(card["due_at"]).replace("+00:00", "Z") if card["due_at"] else None,
                }
                if card is not None
                else None
            ),
            "revision": form.revision,
            "verificationSummary": form.verification_summary if active else "MISSING",
            "updatedAt": form.updated_at,
        }

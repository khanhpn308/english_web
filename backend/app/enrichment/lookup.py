"""Lookup enrichment orchestration and strict provider-response validation (T008)."""

import asyncio
import contextlib
import json
import threading
import unicodedata
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from secrets import token_urlsafe
from time import monotonic
from typing import Any, cast
from urllib.parse import urlsplit

from backend.app.application.ai_admission import AiAdmissionCoordinator
from backend.app.application.operations import OperationConflict, OperationLedger
from backend.app.platform.bridge_port import (
    BridgeAuthError,
    BridgeConfigError,
    BridgeInvalidResponseError,
    BridgeUnavailableError,
)
from backend.app.vocabulary.models import (
    ExampleSentence,
    LookupPreview,
    MeaningEn,
    MeaningVi,
    VerificationStatus,
    WordFormDraft,
)
from backend.app.vocabulary.repository import VocabularyRepository
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy import Connection, event
from starlette.concurrency import run_in_threadpool

LOOKUP_SCOPE = "LOOKUP"
LOOKUP_METHOD = "POST"
LOOKUP_PATH = "/api/v1/lookups"
LOOKUP_DEADLINE_SECONDS = 120.0
PROVIDER = "Antigravity/Google"
MODEL = "gemini-3.8-flash-high"
PROMPT_VERSION = "lookup-v1"
_PROMPT_PATH = Path(__file__).with_name("prompts") / "lookup.txt"


class ProviderResponseError(ValueError):
    """Provider output failed the versioned lookup schema or safety checks."""


class _ProviderMeaning(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    text: str = Field(min_length=1, max_length=4096)
    language: str = Field(default="en", min_length=2, max_length=8)
    verificationStatus: VerificationStatus = "UNVERIFIED"

    @field_validator("text", mode="after")
    @classmethod
    def _check_not_whitespace(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("String cannot be whitespace only")
        return v


class _ProviderExample(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    english: str = Field(min_length=1, max_length=4096)
    vietnamese: str = Field(min_length=1, max_length=4096)
    verificationStatus: VerificationStatus = "UNVERIFIED"

    @field_validator("english", "vietnamese", mode="after")
    @classmethod
    def _check_not_whitespace(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("String cannot be whitespace only")
        return v


class _ProviderForm(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    lemma: str = Field(min_length=1, max_length=128)
    partOfSpeech: str = Field(min_length=1, max_length=32)
    meaningsEn: list[_ProviderMeaning] = Field(min_length=1, max_length=100)
    meaningsVi: list[_ProviderMeaning] = Field(min_length=1, max_length=100)
    examples: list[_ProviderExample] = Field(min_length=1, max_length=100)
    ipaUs: str | None = Field(default=None, max_length=128)
    cambridgeUrl: str | None = Field(default=None, max_length=512)

    @field_validator("lemma", "partOfSpeech", "ipaUs", "cambridgeUrl", mode="after")
    @classmethod
    def _check_not_whitespace(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("String cannot be whitespace only")
        return v


class _ProviderEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    forms: list[_ProviderForm] = Field(min_length=1, max_length=100)


def normalize_term(term: str) -> str:
    """Apply the frozen boundary normalization before hashing or dispatch (R3-B05)."""
    if not isinstance(term, str):
        raise ValueError("term must be a string")
    # 1. Unicode NFC normalization
    nfc = unicodedata.normalize("NFC", term)
    # 2. Reject forbidden controls: check for C0/C1 and Cc controls (excluding standard whitespace)
    for ch in nfc:
        if unicodedata.category(ch) == "Cc" and ch not in " \t\n\r\x0b\x0c":
            raise ValueError("term contains forbidden control characters")
        if 0x80 <= ord(ch) <= 0x9F:
            raise ValueError("term contains forbidden C1 control characters")
    # 3. Collapse whitespace and strip
    collapsed = " ".join(nfc.strip().split())
    # 4. Length bounds: 1-80 Unicode code points
    code_points = len(collapsed)
    if code_points < 1 or code_points > 80:
        raise ValueError("term must contain 1-80 Unicode code points")
    return collapsed


def _duplicate_free_object_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ProviderResponseError("Duplicate provider response field")
        result[key] = value
    return result


def _extract_content(response: dict[str, Any]) -> str:
    if "forms" in response:
        return json.dumps(response, ensure_ascii=False, separators=(",", ":"))
    choices = response.get("choices")
    if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
        raise ProviderResponseError("Provider response schema invalid")
    message = choices[0].get("message")
    if not isinstance(message, dict) or not isinstance(message.get("content"), str):
        raise ProviderResponseError("Provider response schema invalid")
    return cast(str, message["content"])


def _cambridge_url(value: str | None) -> str | None:
    """Canonical fail-closed validation for Cambridge dictionary URLs (R3-B04)."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ProviderResponseError("Invalid Cambridge dictionary URL: not a string")
    if not value or not value.strip():
        raise ProviderResponseError("Invalid Cambridge dictionary URL: empty value")
    if any(ord(c) <= 32 or ord(c) == 127 or 0x80 <= ord(c) <= 0x9F for c in value):
        raise ProviderResponseError(
            "Invalid Cambridge dictionary URL: control characters or whitespace forbidden"
        )
    if "\\" in value or "@" in value:
        raise ProviderResponseError(
            "Invalid Cambridge dictionary URL: backslash or userinfo forbidden"
        )
    try:
        parsed = urlsplit(value)
    except ValueError as exc:
        raise ProviderResponseError("Invalid Cambridge dictionary URL: unparseable URL") from exc
    if parsed.scheme != "https":
        raise ProviderResponseError("Invalid Cambridge dictionary URL: scheme must be https")
    if parsed.hostname != "dictionary.cambridge.org" or parsed.netloc != "dictionary.cambridge.org":
        raise ProviderResponseError(
            "Invalid Cambridge dictionary URL: host must be dictionary.cambridge.org"
        )
    if parsed.port is not None or parsed.username or parsed.password or ":" in parsed.netloc:
        raise ProviderResponseError("Invalid Cambridge dictionary URL: port and userinfo forbidden")
    if parsed.query or parsed.fragment or "?" in value or "#" in value:
        raise ProviderResponseError("Invalid Cambridge dictionary URL: query or fragment forbidden")
    if not parsed.path.startswith("/dictionary/english/"):
        raise ProviderResponseError(
            "Invalid Cambridge dictionary URL: path outside allowed namespace"
        )
    entry = parsed.path[len("/dictionary/english/") :].strip("/")
    if not entry:
        raise ProviderResponseError("Invalid Cambridge dictionary URL: empty entry path")
    if ".." in parsed.path:
        raise ProviderResponseError("Invalid Cambridge dictionary URL: path traversal forbidden")
    if "%25" in parsed.path.lower():
        raise ProviderResponseError("Invalid Cambridge dictionary URL: encoded percent forbidden")

    path = parsed.path
    raw_bytes = bytearray()
    i = 0
    while i < len(path):
        if path[i] == "%":
            if i + 2 >= len(path):
                raise ProviderResponseError(
                    "Invalid Cambridge dictionary URL: incomplete percent escape"
                )
            hex_part = path[i + 1 : i + 3]
            if not all(c in "0123456789abcdefABCDEF" for c in hex_part):
                raise ProviderResponseError(
                    "Invalid Cambridge dictionary URL: non-hex percent escape"
                )
            raw_bytes.append(int(hex_part, 16))
            i += 3
        else:
            raw_bytes.extend(path[i].encode("utf-8"))
            i += 1
    try:
        decoded = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ProviderResponseError(
            "Invalid Cambridge dictionary URL: invalid UTF-8 in percent escape"
        ) from exc

    if any(ord(c) <= 32 or ord(c) == 127 or 0x80 <= ord(c) <= 0x9F for c in decoded):
        raise ProviderResponseError(
            "Invalid Cambridge dictionary URL: decoded control characters forbidden"
        )
    if "\\" in decoded:
        raise ProviderResponseError("Invalid Cambridge dictionary URL: decoded backslash forbidden")
    if ".." in decoded or any(seg in {".", ".."} for seg in decoded.split("/")):
        raise ProviderResponseError(
            "Invalid Cambridge dictionary URL: decoded path traversal forbidden"
        )
    decoded_entry = decoded[len("/dictionary/english/") :].strip("/")
    if "/" in decoded_entry:
        raise ProviderResponseError("Invalid Cambridge dictionary URL: encoded slash forbidden")
    if "%" in decoded:
        raise ProviderResponseError(
            "Invalid Cambridge dictionary URL: residual ambiguous encoding forbidden"
        )

    return value


def parse_provider_response(response: dict[str, Any]) -> list[WordFormDraft]:
    """Parse untrusted provider text and force unverifiable content to UNVERIFIED."""
    try:
        content = _extract_content(response)
        parsed = json.loads(
            content,
            object_pairs_hook=_duplicate_free_object_pairs,
        )
        envelope = _ProviderEnvelope.model_validate(parsed)
    except (ProviderResponseError, TypeError, ValueError, json.JSONDecodeError, ValidationError):
        raise ProviderResponseError("Provider response schema invalid") from None

    drafts: list[WordFormDraft] = []
    for form in envelope.forms:
        ipa = form.ipaUs.strip() if form.ipaUs is not None else None
        ipa = ipa or None
        cambridge = _cambridge_url(form.cambridgeUrl)
        meanings_en = [
            MeaningEn(text=item.text, language="en", verification_status="UNVERIFIED")
            for item in form.meaningsEn
        ]
        meanings_vi = [
            MeaningVi(text=item.text, language="vi", verification_status="UNVERIFIED")
            for item in form.meaningsVi
        ]
        examples = [
            ExampleSentence(
                english=item.english,
                vietnamese=item.vietnamese,
                verification_status="UNVERIFIED",
            )
            for item in form.examples
        ]
        drafts.append(
            WordFormDraft(
                form_id=f"draft_{token_urlsafe(9)}",
                lemma=form.lemma.strip(),
                part_of_speech=form.partOfSpeech.strip().upper(),
                meanings_en=meanings_en,
                meanings_vi=meanings_vi,
                examples=examples,
                ipa_us=ipa,
                cambridge_url=cambridge,
                ipa_status="UNVERIFIED" if ipa is not None else "MISSING",
                cambridge_status="UNVERIFIED" if cambridge is not None else "MISSING",
                verification_summary=_form_summary(
                    meanings_en, meanings_vi, examples, ipa, cambridge
                ),
            )
        )
    return drafts


def _form_summary(
    meanings_en: list[MeaningEn],
    meanings_vi: list[MeaningVi],
    examples: list[ExampleSentence],
    ipa: str | None,
    cambridge: str | None,
) -> VerificationStatus:
    if ipa is None or cambridge is None:
        return "MISSING"
    if meanings_en and meanings_vi and examples:
        return "UNVERIFIED"
    return "UNVERIFIED"


def _render_prompt(term: str) -> str:
    template = _PROMPT_PATH.read_text(encoding="utf-8")
    return template.replace("{{term_json}}", json.dumps(term, ensure_ascii=False))


class LookupService:
    """Claim, admit, validate, persist and replay one lookup operation (T008)."""

    def __init__(
        self,
        ledger: OperationLedger,
        admission: AiAdmissionCoordinator,
        vocabulary: VocabularyRepository,
        *,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self.ledger = ledger
        self.admission = admission
        self.vocabulary = vocabulary
        self.clock = clock
        self.on_preview_written: Callable[[], None] | None = None
        self.on_before_receipt_update: Callable[[], None] | None = None
        self.on_before_commit: Callable[[], None] | None = None
        self.release_commit_boundary: Callable[[], None] | None = None

    async def lookup(
        self,
        *,
        term: str,
        idempotency_key: str,
        owner_session_id: str,
        request_start_time: float | None = None,
    ) -> LookupPreview:
        start_time = request_start_time if request_start_time is not None else self.clock()
        deadline = start_time + LOOKUP_DEADLINE_SECONDS
        normalized = normalize_term(term)
        claimed = await run_in_threadpool(
            self.ledger.claim,
            kind=LOOKUP_SCOPE,
            key=idempotency_key,
            method=LOOKUP_METHOD,
            path=LOOKUP_PATH,
            body={"term": normalized},
            preconditions={},
        )
        operation = claimed.operation
        if claimed.replayed:
            if operation.status == "SUCCEEDED" and operation.result_ref is not None:
                return await run_in_threadpool(
                    self.vocabulary.get_preview,
                    operation.result_ref,
                    requesting_session_id=owner_session_id,
                )
            raise OperationConflict(
                operation.response_status or 409,
                operation.error_category or "IDEMPOTENCY_IN_FLIGHT",
                operation.operation_id,
            )

        operation_id = operation.operation_id
        payload = {"messages": [{"role": "user", "content": _render_prompt(normalized)}]}

        cancellation_event = threading.Event()
        thread_done = threading.Event()
        active_connection: list[Connection | None] = [None]
        cursor_listener: list[Any] = [None]
        commit_listener: list[Any] = [None]

        try:
            # 1. Hard enforcement: check if deadline already expired before dispatch
            remaining = deadline - self.clock()
            if remaining <= 0.0:
                raise TimeoutError("Deadline already expired before dispatch")

            # 2. Hard enforcement: provider dispatch bounded by cancellation-aware timeout scope
            try:
                async with asyncio.timeout(remaining):
                    provider_response = await self.admission.dispatch(
                        operation_id=operation_id,
                        scope=LOOKUP_SCOPE,
                        payload=payload,
                        deadline=deadline,
                    )
            except TimeoutError:
                unknown = await self._admitted(operation_id)
                await self._record_failure(operation_id, "TIMEOUT", 503, unknown=unknown)
                raise OperationConflict(503, "BRIDGE_UNAVAILABLE", operation_id) from None

            if self.clock() >= deadline:
                raise TimeoutError("Deadline expired after dispatch")

            forms = parse_provider_response(provider_response)

            if self.clock() >= deadline:
                raise TimeoutError("Deadline expired after parse")

            lookup_id = f"lookup_{token_urlsafe(12)}"
            created_at = datetime.now(UTC).timestamp()

            def _check_eligibility(stmt: str = "") -> None:
                if cancellation_event.is_set():
                    raise TimeoutError(f"Operation cancelled before commit: {stmt}")
                if self.clock() >= deadline:
                    raise TimeoutError(f"Deadline expired before commit: {stmt}")

            def _local_write(connection: Connection) -> None:
                active_connection[0] = connection

                _check_eligibility("before_preview_insert")

                def _before_cursor(
                    _conn: Connection,
                    _cursor: Any,
                    statement: str,
                    _parameters: Any,
                    _context: Any,
                    _executemany: bool,
                ) -> None:
                    if (
                        self.on_before_receipt_update is not None
                        and "UPDATE operations" in statement
                    ):
                        self.on_before_receipt_update()
                    _check_eligibility(statement)

                def _on_commit(_conn: Connection) -> None:
                    if self.on_before_commit is not None:
                        self.on_before_commit()
                    _check_eligibility("commit")

                cursor_listener[0] = _before_cursor
                commit_listener[0] = _on_commit
                event.listen(connection, "before_cursor_execute", _before_cursor)
                event.listen(connection, "commit", _on_commit)

                self.vocabulary.create_preview(
                    lookup_id=lookup_id,
                    owner_session_id=owner_session_id,
                    term=normalized,
                    forms=forms,
                    provider=PROVIDER,
                    model=MODEL,
                    prompt_version=PROMPT_VERSION,
                    operation_id=operation_id,
                    created_at=created_at,
                    external_connection=connection,
                )

                if self.on_preview_written is not None:
                    self.on_preview_written()

                _check_eligibility("after_preview_insert")

            def _do_complete() -> None:
                try:
                    self.ledger.complete(
                        operation_id,
                        response_status=200,
                        result_ref=lookup_id,
                        local_write=_local_write,
                    )
                finally:
                    thread_done.set()
                    conn = active_connection[0]
                    if conn is not None:
                        with contextlib.suppress(Exception):
                            if cursor_listener[0] is not None:
                                event.remove(conn, "before_cursor_execute", cursor_listener[0])
                            if commit_listener[0] is not None:
                                event.remove(conn, "commit", commit_listener[0])

            try:
                await run_in_threadpool(_do_complete)
            except (asyncio.CancelledError, GeneratorExit):
                cancellation_event.set()
                if self.release_commit_boundary is not None:
                    self.release_commit_boundary()
                # Wait bounded for worker thread to rollback and finish
                await run_in_threadpool(lambda: thread_done.wait(timeout=5.0))
                # Durably record cancellation failure state
                admitted = await self._admitted(operation_id)
                await self._record_failure(operation_id, "TIMEOUT", 503, unknown=admitted)
                raise

            return await run_in_threadpool(
                self.vocabulary.get_preview, lookup_id, requesting_session_id=owner_session_id
            )
        except (asyncio.CancelledError, GeneratorExit):
            # Outer cancellation catch: ensures operation is NEVER silently left in PENDING
            cancellation_event.set()
            if self.release_commit_boundary is not None:
                self.release_commit_boundary()
            with contextlib.suppress(Exception):
                admitted = await self._admitted(operation_id)
                await self._record_failure(operation_id, "TIMEOUT", 503, unknown=admitted)
            raise
        except OperationConflict as error:
            if error.code not in {"IDEMPOTENCY_IN_FLIGHT", "IDEMPOTENCY_KEY_REUSED"}:
                await self._record_failure(operation_id, error.code, error.status_code)
            raise
        except ProviderResponseError:
            await self._record_failure(operation_id, "BRIDGE_INVALID_RESPONSE", 502)
            raise OperationConflict(502, "BRIDGE_INVALID_RESPONSE", operation_id) from None
        except BridgeInvalidResponseError:
            await self._record_failure(operation_id, "BRIDGE_INVALID_RESPONSE", 502)
            raise OperationConflict(502, "BRIDGE_INVALID_RESPONSE", operation_id) from None
        except BridgeAuthError:
            await self._record_failure(operation_id, "BRIDGE_AUTH_ERROR", 502)
            raise OperationConflict(502, "BRIDGE_AUTH_ERROR", operation_id) from None
        except BridgeConfigError:
            await self._record_failure(operation_id, "CONFIGURATION_REQUIRED", 503)
            raise OperationConflict(503, "CONFIGURATION_REQUIRED", operation_id) from None
        except BridgeUnavailableError:
            unknown = await self._admitted(operation_id)
            if self.clock() >= deadline:
                await self._record_failure(operation_id, "TIMEOUT", 503, unknown=unknown)
                raise OperationConflict(503, "BRIDGE_UNAVAILABLE", operation_id) from None
            await self._record_failure(operation_id, "BRIDGE_UNAVAILABLE", 503, unknown=unknown)
            raise OperationConflict(503, "BRIDGE_UNAVAILABLE", operation_id) from None
        except TimeoutError:
            unknown = await self._admitted(operation_id)
            await self._record_failure(operation_id, "TIMEOUT", 503, unknown=unknown)
            raise OperationConflict(503, "BRIDGE_UNAVAILABLE", operation_id) from None
        except OSError:
            await self._record_failure(operation_id, "STORAGE_BUSY", 503)
            raise OperationConflict(503, "STORAGE_BUSY", operation_id) from None
        except Exception:
            await self._record_failure(operation_id, "STORAGE_BUSY", 503)
            raise OperationConflict(503, "STORAGE_BUSY", operation_id) from None

    def _is_admitted_sync(self, operation_id: str) -> bool:
        try:
            with self.ledger.engine.connect() as connection:
                return (
                    connection.exec_driver_sql(
                        "SELECT 1 FROM ai_operation_admission WHERE operation_id=?",
                        (operation_id,),
                    ).first()
                    is not None
                )
        except Exception:
            return True

    async def _admitted(self, operation_id: str) -> bool:
        return await run_in_threadpool(self._is_admitted_sync, operation_id)

    async def _record_failure(
        self, operation_id: str, code: str, status: int, *, unknown: bool = False
    ) -> None:
        def _record() -> None:
            with contextlib.suppress(Exception):
                self.ledger.record_failure(
                    operation_id,
                    error_category=code,
                    response_status=status,
                    unknown=unknown,
                )

        await run_in_threadpool(_record)

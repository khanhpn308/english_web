"""T035 quiz generation using T016 admission and T034 immutable storage.

Only durable cleanup survives a cancelled waiter. It never retries transport.
Snapshot and receipt share the ledger's writer transaction; HTTP serialization
also finishes before that transaction may acknowledge success.
"""

import asyncio
import json
import re
import threading
from collections import Counter
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from secrets import token_urlsafe
from time import monotonic
from typing import Any, Never

from backend.app.application.ai_admission import AiAdmissionCoordinator
from backend.app.application.operations import OperationConflict, OperationLedger
from backend.app.assessment.questions import (
    NoteDate,
    QuestionSet,
    QuizAttempt,
    QuizCounts,
    StrictModel,
    WritingQuestion,
    WritingRubric,
)
from backend.app.assessment.repository import QuizPersistenceError, create_attempt, get_attempt
from backend.app.platform.bridge_port import (
    BridgeAuthError,
    BridgeConfigError,
    BridgeInvalidResponseError,
    BridgeUnavailableError,
)
from backend.app.vocabulary.models import WordForm
from backend.app.vocabulary.repository import VocabularyRepository
from pydantic import ConfigDict
from sqlalchemy import Connection, event
from starlette.concurrency import run_in_threadpool

QUIZ_PATH = "/api/v1/quiz-attempts"
QUIZ_SCOPE = "QUIZ_GENERATION"
QUIZ_DEADLINE_SECONDS = 60.0
_PROMPT = Path(__file__).resolve().parents[1] / "enrichment" / "prompts" / "quiz.txt"
_HTML_TAG = re.compile(r"<\s*(?:!|/?\s*[a-zA-Z][^>]*>)")
_DESCRIPTORS = (
    "Không có câu có nghĩa, thiếu từ mục tiêu hoặc không thể đánh giá cách dùng nghĩa.",
    "Có thử dùng từ nhưng sai nghĩa/dạng hoặc lỗi ngữ pháp lớn cản trở nghĩa định diễn đạt.",
    "Nhận ra nghĩa định dùng nhưng dạng từ hoặc ngữ pháp cần sửa đáng kể.",
    "Đúng nghĩa/dạng và ngữ pháp dễ hiểu; lỗi nhỏ không cản trở nghĩa.",
    "Đúng nghĩa/dạng, đúng ngữ pháp, rõ ràng, tự nhiên và chính xác trong văn học thuật.",
)
WRITING_RUBRIC = WritingRubric.model_validate(
    {
        "descriptors": [
            {"score": score, "textVi": text} for score, text in enumerate(_DESCRIPTORS)
        ]
    }
)


class CreateQuizRequest(StrictModel):
    model_config = ConfigDict(populate_by_name=False)
    note_date: NoteDate
    counts: QuizCounts


class QuizConsentRequired(OperationConflict):
    def __init__(self, operation_id: str | None, details: dict[str, Any]) -> None:
        super().__init__(403, "AI_CONSENT_REQUIRED", operation_id)
        self.details = details


class QuizRestoreRequired(OperationConflict):
    def __init__(self, attempt_id: str, operation_id: str) -> None:
        super().__init__(409, "QUIZ_RESTORE_REQUIRED", operation_id)
        self.attempt_id = attempt_id


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field")
        result[key] = value
    return result


def _text_tree(value: Any, *, provider: bool) -> None:
    if isinstance(value, str):
        if (
            len(value) > 4096
            or any(
                0xD800 <= ord(c) <= 0xDFFF
                or 0x7F <= ord(c) <= 0x9F
                or (ord(c) < 32 and c not in "\t\n\r\f\v")
                for c in value
            )
            or (provider and _HTML_TAG.search(value))
        ):
            raise ValueError("Invalid learning content")
    elif isinstance(value, dict):
        for key, item in value.items():
            _text_tree(key, provider=provider)
            _text_tree(item, provider=provider)
    elif isinstance(value, (list, tuple)):
        if len(value) > 100:
            raise ValueError("Collection limit exceeded")
        for item in value:
            _text_tree(item, provider=provider)


def parse_questions(
    response: dict[str, Any], counts: QuizCounts, forms: list[WordForm]
) -> QuestionSet:
    """Reject untrusted structure, counts and membership before any snapshot write."""
    try:
        if "model" in response and response["model"] != "gemini-3.8-flash-high":
            raise ValueError("Unexpected response model")
        choices = response.get("choices")
        if not isinstance(choices, list) or len(choices) != 1:
            raise ValueError("Expected one completion")
        choice = choices[0]
        if not isinstance(choice, dict) or choice.get("finish_reason") not in {None, "stop"}:
            raise ValueError("Incomplete completion")
        message = choice.get("message")
        if (
            not isinstance(message, dict)
            or message.get("tool_calls")
            or message.get("function_call")
        ):
            raise ValueError("Expected text only")
        content = message.get("content")
        if not isinstance(content, str) or len(content.encode("utf-8")) > 4_194_304:
            raise ValueError("Invalid completion content")
        data = json.loads(content, object_pairs_hook=_pairs)
        _text_tree(data, provider=True)
        questions = QuestionSet.model_validate(data)
        if Counter(q.type for q in questions.questions) != Counter(
            {kind.upper(): count for kind, count in counts.model_dump().items() if count}
        ):
            raise ValueError("Generated counts differ from requested counts")
        eligible = {form.id: form for form in forms}
        for question in questions.questions:
            if question.word_form_id not in eligible:
                raise ValueError("Generated form is outside the selected source")
            if isinstance(question, WritingQuestion) and (
                question.target_lemma != eligible[question.word_form_id].lemma
                or question.rubric != WRITING_RUBRIC
            ):
                raise ValueError("Writing target or rubric differs from canonical source")
        # Provider-local IDs may repeat across different completions. T034 owns
        # global identity; allocate it only after duplicate identities are rejected.
        return QuestionSet(
            questions=tuple(
                q.model_copy(update={"id": f"question_{token_urlsafe(18)}"})
                for q in questions.questions
            )
        )
    except (ValueError, TypeError, KeyError, RecursionError):
        raise BridgeInvalidResponseError("Quiz response validation failed") from None


@dataclass
class _Lifecycle:
    abort: threading.Event = field(default_factory=threading.Event)
    dispatched: threading.Event = field(default_factory=threading.Event)
    response_received: bool = False
    operation_id: str | None = None


async def _settle[T](task: asyncio.Task[T]) -> T:
    while True:
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            if task.done():
                return task.result()


async def _local[T](function: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    worker = asyncio.create_task(run_in_threadpool(function, *args, **kwargs))
    try:
        return await asyncio.shield(worker)
    except asyncio.CancelledError:
        await _settle(worker)
        raise


class CreateQuizService:
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
        self._owners: set[asyncio.Task[Any]] = set()
        self._cleanup_errors: list[BaseException] = []
        self._transaction_check: ContextVar[Callable[[], None] | None] = ContextVar(
            "quiz_transaction_check", default=None
        )
        event.listen(self.ledger.engine, "engine_connect", self._guard_connection)

    def _guard_connection(self, connection: Connection) -> None:
        # AnyIO propagates the owner's context to its workers, including the
        # shared admission coordinator's workers. Other services have no check.
        check = self._transaction_check.get()
        if check is None:
            return

        def boundary(_connection: Connection) -> None:
            check()

        def before_sql(
            _conn: Connection,
            _cursor: Any,
            _statement: str,
            _parameters: Any,
            _context: Any,
            _executemany: bool,
        ) -> None:
            check()

        # Attach before caller begin, including T005's BEGIN IMMEDIATE listener.
        # Do not raise in engine_connect, after raw connection acquisition, or
        # fence rollback. Closed connections discard these request-local guards.
        event.listen(connection, "begin", boundary)
        event.listen(connection, "before_cursor_execute", before_sql)
        event.listen(connection, "commit", boundary)

    def _done(self, task: asyncio.Task[Any]) -> None:
        self._owners.discard(task)
        if not task.cancelled():
            error = task.exception()
            if error is not None and not isinstance(error, OperationConflict):
                self.admission.consent.storage_reliable = False
                self._cleanup_errors.append(error)

    async def drain(self) -> None:
        """Retain all durable workers until the shared lifespan can close SQLite."""
        while self._owners:
            await _settle(
                asyncio.ensure_future(asyncio.gather(*self._owners, return_exceptions=True))
            )
        if self._cleanup_errors:
            raise RuntimeError("Quiz durable cleanup failed") from None

    def get(self, attempt_id: str) -> QuizAttempt:
        with self.ledger.engine.connect() as connection, connection.begin():
            return get_attempt(connection, attempt_id)

    async def create[T](
        self,
        *,
        intent: CreateQuizRequest,
        idempotency_key: str,
        request_start_time: float | None = None,
        finalize: Callable[[QuizAttempt], T] | None = None,
        on_operation: Callable[[str], None] | None = None,
    ) -> QuizAttempt | T:
        start = self.clock() if request_start_time is None else request_start_time
        deadline = start + QUIZ_DEADLINE_SECONDS
        state = _Lifecycle()
        owner = asyncio.create_task(
            self._execute(intent, idempotency_key, deadline, state, finalize, on_operation)
        )
        self._owners.add(owner)
        owner.add_done_callback(self._done)

        def abort() -> None:
            if not state.abort.is_set():
                state.abort.set()
                owner.cancel()

        try:
            done, _ = await asyncio.wait({owner}, timeout=max(0.0, deadline - self.clock()))
            if not done or self.clock() >= deadline:
                abort()
                raise OperationConflict(503, "BRIDGE_UNAVAILABLE", state.operation_id)
            return owner.result()
        except asyncio.CancelledError:
            abort()
            raise

    def _source(self, intent: CreateQuizRequest) -> list[WordForm]:
        forms = [
            form
            for form in self.vocabulary.get_forms_for_date(
                intent.note_date, only_valid_sources=True
            )
            if any(
                ref.note_date == intent.note_date and ref.status == "VALID"
                for ref in form.source_refs
            )
        ]
        if (
            not forms
            or len(forms) > 100
            or max(intent.counts.model_dump().values()) > len({f.id for f in forms})
        ):
            raise OperationConflict(422, "VALIDATION_ERROR")
        return forms

    @staticmethod
    def _payload(intent: CreateQuizRequest, forms: list[WordForm]) -> dict[str, Any]:
        data = {
            "noteDate": intent.note_date,
            "counts": intent.counts.model_dump(),
            "forms": [
                {
                    "wordFormId": form.id,
                    "lemma": form.lemma,
                    "partOfSpeech": form.part_of_speech,
                    "meaningsEn": [m.text for m in form.meanings_en],
                    "meaningsVi": [m.text for m in form.meanings_vi],
                    "examples": [
                        {"english": e.english, "vietnamese": e.vietnamese}
                        for e in form.examples
                    ],
                }
                for form in forms
            ],
            "writingRubric": WRITING_RUBRIC.model_dump(by_alias=True),
        }
        try:
            _text_tree(data, provider=False)
            source_json = json.dumps(data, ensure_ascii=False, allow_nan=False)
            if len(source_json.encode("utf-8")) > 1_048_576:
                raise ValueError("Quiz source payload limit exceeded")
        except ValueError:
            raise OperationConflict(422, "VALIDATION_ERROR") from None
        return {
            "messages": [
                {"role": "system", "content": _PROMPT.read_text(encoding="utf-8")},
                {"role": "user", "content": source_json},
            ]
        }

    async def _failure(self, identity: str, code: str, status: int, *, unknown: bool) -> None:
        def record() -> None:
            try:
                self.ledger.record_failure(
                    identity, error_category=code, response_status=status, unknown=unknown
                )
            except OperationConflict:
                receipt = self.ledger.get(identity)
                if receipt is None or receipt.status != "SUCCEEDED":
                    raise

        # Terminal failure/reconciliation is mandatory cleanup, not permission
        # for new generation or snapshot persistence after cancellation/expiry.
        token = self._transaction_check.set(None)
        try:
            try:
                await _local(record)
            except Exception as error:
                self.admission.consent.storage_reliable = False
                self._cleanup_errors.append(error)
                raise OperationConflict(503, "STORAGE_BUSY", identity) from None
        finally:
            self._transaction_check.reset(token)

    async def _execute[T](
        self,
        intent: CreateQuizRequest,
        key: str,
        deadline: float,
        state: _Lifecycle,
        finalize: Callable[[QuizAttempt], T] | None,
        on_operation: Callable[[str], None] | None,
    ) -> QuizAttempt | T:
        identity: str | None = None

        def check() -> None:
            if state.abort.is_set() or self.clock() >= deadline:
                raise TimeoutError("Quiz deadline exhausted")

        async def reject(
            code: str, status: int, *, unknown: bool = False, outcome_known: bool = False
        ) -> Never:
            if state.abort.is_set() or self.clock() >= deadline or code == "TIMEOUT":
                code, status, unknown = (
                    "TIMEOUT", 503,
                    state.dispatched.is_set() and not state.response_received and not outcome_known,
                )
            if identity is not None:
                await self._failure(identity, code, status, unknown=unknown)
            raise OperationConflict(
                status, "BRIDGE_UNAVAILABLE" if code == "TIMEOUT" else code, state.operation_id
            ) from None

        token = self._transaction_check.set(check)
        try:
            check()
            worker = asyncio.create_task(
                run_in_threadpool(
                    self.ledger.claim,
                    kind=QUIZ_SCOPE,
                    key=key,
                    method="POST",
                    path=QUIZ_PATH,
                    body=intent.model_dump(by_alias=True),
                    preconditions={},
                )
            )
            try:
                claimed = await asyncio.shield(worker)
            except asyncio.CancelledError:
                claimed = await _settle(worker)
            operation = claimed.operation
            state.operation_id = operation.operation_id
            if not claimed.replayed:
                identity = operation.operation_id
            if on_operation is not None:
                on_operation(operation.operation_id)
            if claimed.replayed:
                check()
                if operation.status != "SUCCEEDED" or operation.result_ref is None:
                    code = operation.error_category or "IDEMPOTENCY_IN_FLIGHT"
                    raise OperationConflict(
                        operation.response_status or 409,
                        "BRIDGE_UNAVAILABLE" if code == "TIMEOUT" else code,
                        operation.operation_id,
                    )
                try:
                    attempt = await _local(self.get, operation.result_ref)
                except QuizPersistenceError:
                    raise QuizRestoreRequired(
                        operation.result_ref, operation.operation_id
                    ) from None
                check()
                result = await _local(finalize, attempt) if finalize else attempt
                check()
                return result
            check()
            forms = await _local(self._source, intent)
            check()
            payload = await _local(self._payload, intent, forms)
            check()

            def dispatching() -> None:
                check()
                state.dispatched.set()

            response = await self.admission.dispatch(
                operation_id=identity,
                scope=QUIZ_SCOPE,
                payload=payload,
                deadline=deadline,
                on_dispatch=dispatching,
            )
            state.response_received = True
            check()
            questions = await _local(parse_questions, response, intent.counts, forms)
            check()
            attempt_id = f"attempt_{token_urlsafe(18)}"
            completed: list[QuizAttempt | T] = []

            def complete() -> None:
                def write(connection: Connection) -> None:
                    check()
                    attempt = create_attempt(
                        connection,
                        attempt_id=attempt_id,
                        note_date=intent.note_date,
                        questions=questions,
                        created_at=datetime.now(UTC),
                    )
                    completed.append(finalize(attempt) if finalize else attempt)
                    check()

                check()
                # Connection guards fence BEGIN, SQL and commit admission.
                # ADR-0005 C013-10 permits an admitted physical SQLite commit
                # to settle after expiry. Preserve its atomic snapshot/receipt;
                # the owner and HTTP guards still refuse a late acknowledgement.
                self.ledger.complete(
                    identity, response_status=201, result_ref=attempt_id, local_write=write
                )

            await _local(complete)
            check()
            return completed[0]
        except (asyncio.CancelledError, TimeoutError):
            await reject("TIMEOUT", 503)
        except OperationConflict as error:
            if error.code == "AI_CONSENT_REQUIRED":
                try:
                    snapshot = await _local(
                        self.admission.consent.get_snapshot, self.admission.policy_source
                    )
                    check()
                    details = {
                        "kind": "AI_CONSENT",
                        "consentState": snapshot.state.state,
                        "currentPolicyVersion": (
                            snapshot.policy.version if snapshot.policy else None
                        ),
                    }
                except (asyncio.CancelledError, TimeoutError):
                    await reject("TIMEOUT", 503)
                except Exception:
                    await reject("STORAGE_BUSY", 503)
                if identity is not None:
                    await self._failure(identity, error.code, error.status_code, unknown=False)
                raise QuizConsentRequired(state.operation_id, details) from None
            if identity is not None:
                await reject(error.code, error.status_code)
            raise
        except QuizPersistenceError as error:
            if error.code == "VALIDATION_ERROR":
                await reject("VALIDATION_ERROR", 422)
            # Restore failure inside a new creation is storage failure and rolls
            # back with the receipt. Replay carries its existing attempt ID above.
            await reject("STORAGE_BUSY", 503)
        except BridgeInvalidResponseError:
            await reject("BRIDGE_INVALID_RESPONSE", 502, outcome_known=True)
        except BridgeAuthError:
            await reject("BRIDGE_AUTH_ERROR", 502, outcome_known=True)
        except BridgeConfigError:
            await reject("CONFIGURATION_REQUIRED", 503, outcome_known=True)
        except BridgeUnavailableError:
            await reject("BRIDGE_UNAVAILABLE", 503, unknown=state.dispatched.is_set())
        except Exception:
            await reject(
                "STORAGE_BUSY", 503,
                unknown=state.dispatched.is_set() and not state.response_received,
            )
        finally:
            self._transaction_check.reset(token)

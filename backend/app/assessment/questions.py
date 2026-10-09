"""Validated immutable quiz content and public projections (ADR-0005 C013-01/06/07).

Private snapshots deliberately exclude keys from normal and nested serialization.
Only storage_payload opts into persistence of concealed objective fields. T059 owns
scoring; the adapter below only translates validated content into its existing types.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import date, datetime
from typing import Annotated, Any, Literal, Self

from backend.app.assessment import scoring
from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    TypeAdapter,
    model_validator,
)
from pydantic.alias_generators import to_camel


def _nonblank(value: str) -> str:
    if not value.strip():
        raise ValueError("Required content cannot be blank")
    return value


def _tuple(value: Any) -> tuple[Any, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError("Expected an array")
    return tuple(value)


def _array_bounds_schema(schema: dict[str, Any]) -> None:
    # Field constraints after BeforeValidator retain runtime order but Pydantic
    # emits string keywords for these tuple fields. Correct only their schema.
    for string_keyword, array_keyword in (("minLength", "minItems"), ("maxLength", "maxItems")):
        if string_keyword in schema:
            schema[array_keyword] = schema.pop(string_keyword)


def _note_date(value: str) -> str:
    if date.fromisoformat(value).isoformat() != value:
        raise ValueError("Expected YYYY-MM-DD")
    return value


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timestamp must have a timezone")
    return value


Identifier = Annotated[str, Field(min_length=1, max_length=64), AfterValidator(_nonblank)]
Content = Annotated[str, Field(min_length=1, max_length=4096), AfterValidator(_nonblank)]
AnswerText = Annotated[str, Field(max_length=4096)]
Revision = Annotated[int, Field(ge=0)]
SelfScore = Annotated[int, Field(ge=0, le=4)]
NoteDate = Annotated[str, AfterValidator(_note_date)]
AwareTime = Annotated[datetime, AfterValidator(_aware)]
Rating = Literal["AGAIN", "HARD", "GOOD", "EASY"]


class StrictModel(BaseModel):
    model_config = ConfigDict(
        strict=True,
        extra="forbid",
        frozen=True,
        revalidate_instances="always",
        populate_by_name=True,
        alias_generator=to_camel,
        hide_input_in_errors=True,
    )


class MCQOption(StrictModel):
    id: Identifier
    text_en: Content


class RubricDescriptor(StrictModel):
    score: SelfScore
    text_vi: Content


class WritingRubric(StrictModel):
    descriptors: Annotated[
        tuple[RubricDescriptor, ...],
        BeforeValidator(_tuple),
        Field(min_length=5, max_length=5, json_schema_extra=_array_bounds_schema),
    ]

    @model_validator(mode="after")
    def complete_scale(self) -> Self:
        if tuple(item.score for item in self.descriptors) != (0, 1, 2, 3, 4):
            raise ValueError("Rubric must contain ordered descriptors 0..4")
        return self


class Question(StrictModel):
    id: Identifier
    type: Literal["MCQ", "CLOZE", "WRITING"]
    word_form_id: Identifier
    prompt_en: Content


class MCQQuestion(Question):
    type: Literal["MCQ"]
    options: Annotated[
        tuple[MCQOption, ...],
        BeforeValidator(_tuple),
        Field(min_length=1, max_length=100, json_schema_extra=_array_bounds_schema),
    ]

    @model_validator(mode="after")
    def distinct_options(self) -> Self:
        if len({option.id for option in self.options}) != len(self.options):
            raise ValueError("Duplicate option identity")
        return self


class ClozeQuestion(Question):
    type: Literal["CLOZE"]
    answer_policy_version: Literal["cloze-answer-v1"]


class WritingQuestion(Question):
    type: Literal["WRITING"]
    target_lemma: Content
    rubric_version: Literal["writing-rubric-v1"]
    rubric: WritingRubric


PublicQuestion = Annotated[
    MCQQuestion | ClozeQuestion | WritingQuestion, Field(discriminator="type")
]
PUBLIC_QUESTION_ADAPTER: TypeAdapter[PublicQuestion] = TypeAdapter(PublicQuestion)


class MCQSnapshot(MCQQuestion):
    correct_option_id: Identifier = Field(exclude=True, repr=False)
    explanation_vi: Content = Field(exclude=True, repr=False)

    @model_validator(mode="after")
    def key_membership(self) -> Self:
        if self.correct_option_id not in {option.id for option in self.options}:
            raise ValueError("Correct option must belong to the snapshot")
        return self


class ClozeSnapshot(ClozeQuestion):
    accepted_answers: Annotated[
        tuple[Content, ...], BeforeValidator(_tuple), Field(min_length=1, max_length=100)
    ] = Field(exclude=True, repr=False)
    explanation_vi: Content = Field(exclude=True, repr=False)

    @model_validator(mode="after")
    def distinct_alternatives(self) -> Self:
        normalized = {scoring.normalize_cloze_text(answer) for answer in self.accepted_answers}
        if len(normalized) != len(self.accepted_answers):
            raise ValueError("Duplicate accepted alternative")
        return self


QuestionSnapshot = Annotated[
    MCQSnapshot | ClozeSnapshot | WritingQuestion, Field(discriminator="type")
]
SNAPSHOT_ADAPTER: TypeAdapter[QuestionSnapshot] = TypeAdapter(QuestionSnapshot)


class QuizCounts(StrictModel):
    mcq: Annotated[int, Field(ge=0, le=20)]
    cloze: Annotated[int, Field(ge=0, le=20)]
    writing: Annotated[int, Field(ge=0, le=20)]

    @property
    def total(self) -> int:
        return self.mcq + self.cloze + self.writing

    @model_validator(mode="after")
    def total_bounds(self) -> Self:
        if not 5 <= self.total <= 30:
            raise ValueError("Quiz total must be between 5 and 30")
        return self


def validate_question_collection(questions: tuple[Question, ...]) -> None:
    if not 5 <= len(questions) <= 30:
        raise ValueError("Quiz total must be between 5 and 30")
    if len({q.id for q in questions}) != len(questions):
        raise ValueError("Duplicate question identity")
    pairs = {(q.type, q.word_form_id) for q in questions}
    if len(pairs) != len(questions):
        raise ValueError("Duplicate question type/form pair")
    if any(count > 20 for count in Counter(q.type for q in questions).values()):
        raise ValueError("At most 20 questions per type")


class QuestionSet(StrictModel):
    questions: Annotated[
        tuple[QuestionSnapshot, ...], BeforeValidator(_tuple), Field(min_length=5, max_length=30)
    ]

    @model_validator(mode="after")
    def bounds_and_identity(self) -> Self:
        validate_question_collection(self.questions)
        return self


def storage_payload(question: QuestionSnapshot) -> str:
    """Backend-only canonical JSON. Never use this in an HTTP response or diagnostics."""
    validated = SNAPSHOT_ADAPTER.validate_python(question)
    payload = validated.model_dump(mode="json", by_alias=True)
    if isinstance(validated, MCQSnapshot):
        payload.update(
            correctOptionId=validated.correct_option_id, explanationVi=validated.explanation_vi
        )
    elif isinstance(validated, ClozeSnapshot):
        payload.update(
            acceptedAnswers=list(validated.accepted_answers), explanationVi=validated.explanation_vi
        )
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def to_scoring_snapshot(question: QuestionSnapshot) -> scoring.QuestionSnapshot:
    """Translate to T059's established types, without performing any scoring."""
    question = SNAPSHOT_ADAPTER.validate_python(question)
    if isinstance(question, MCQSnapshot):
        return scoring.MCQSnapshot(
            id=question.id,
            word_form_id=question.word_form_id,
            prompt_en=question.prompt_en,
            options=tuple(scoring.MCQOption(o.id, o.text_en) for o in question.options),
            correct_option_id=question.correct_option_id,
            explanation_vi=question.explanation_vi,
        )
    if isinstance(question, ClozeSnapshot):
        return scoring.ClozeSnapshot(
            id=question.id,
            word_form_id=question.word_form_id,
            prompt_en=question.prompt_en,
            accepted_answers=question.accepted_answers,
            explanation_vi=question.explanation_vi,
        )
    return scoring.WritingSnapshot(
        id=question.id,
        word_form_id=question.word_form_id,
        prompt_en=question.prompt_en,
        target_lemma=question.target_lemma,
        rubric_version=question.rubric_version,
    )


class Answer(StrictModel):
    attempt_id: Identifier
    question_id: Identifier
    answer: AnswerText
    self_score: SelfScore | None
    draft_revision: Annotated[int, Field(ge=1)]
    saved_at: AwareTime
    state: Literal["BLANK", "DRAFT", "SCORED"]
    operation_id: Identifier


def answer_etag(attempt_id: str, question_id: str, draft_revision: int) -> str:
    """Server-issued strong validator, stable across restart. See ADR-0008."""
    canonical = json.dumps(
        ["quiz-answer-v1", attempt_id, question_id, draft_revision],
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return '"qa-v1-' + hashlib.sha256(canonical.encode("ascii")).hexdigest() + '"'


class AnswerPrecondition(StrictModel):
    question_id: Identifier
    draft_revision: Revision
    etag: Annotated[str, Field(pattern=r'^"qa-v1-[0-9a-f]{64}"$')]


class ObjectiveScore(StrictModel):
    total: Annotated[int, Field(ge=0, le=20)]
    attempted: Annotated[int, Field(ge=0, le=20)]
    correct: Annotated[int, Field(ge=0, le=20)]
    accuracy: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)] | None

    @model_validator(mode="after")
    def consistent_metrics(self) -> Self:
        if not self.correct <= self.attempted <= self.total:
            raise ValueError("Inconsistent objective counts")
        expected = self.correct / self.attempted if self.attempted else None
        if self.accuracy != expected:
            raise ValueError("Inconsistent objective accuracy")
        return self


class ObjectiveScores(StrictModel):
    mcq: ObjectiveScore
    cloze: ObjectiveScore


class MCQQuestionResult(StrictModel):
    question_id: Identifier
    type: Literal["MCQ"]
    outcome: Literal["CORRECT", "INCORRECT", "BLANK"]
    is_correct: bool
    rating: Rating
    correct_option_id: Identifier
    explanation_vi: Content


class ClozeQuestionResult(StrictModel):
    question_id: Identifier
    type: Literal["CLOZE"]
    outcome: Literal["CORRECT", "INCORRECT", "BLANK"]
    is_correct: bool
    rating: Rating
    accepted_answers: Annotated[
        tuple[Content, ...],
        BeforeValidator(_tuple),
        Field(min_length=1, max_length=100, json_schema_extra=_array_bounds_schema),
    ]
    explanation_vi: Content


class WritingQuestionResult(StrictModel):
    question_id: Identifier
    type: Literal["WRITING"]
    outcome: Literal["SELF_SCORED"]
    self_score: SelfScore
    rating: Rating


QuestionResult = Annotated[
    MCQQuestionResult | ClozeQuestionResult | WritingQuestionResult, Field(discriminator="type")
]


class WritingSelfScore(StrictModel):
    question_id: Identifier
    self_score: SelfScore
    rating: Rating


class ReviewHandoff(StrictModel):
    word_form_id: Identifier
    card_id: Identifier | None
    rating: Rating
    review_event_id: Identifier | None
    status: Literal["APPLIED", "SKIPPED_INACTIVE"]

    @model_validator(mode="after")
    def event_presence(self) -> Self:
        if self.status == "APPLIED" and (self.card_id is None or self.review_event_id is None):
            raise ValueError("Applied handoff requires a card and review event")
        if self.status == "SKIPPED_INACTIVE" and self.review_event_id is not None:
            raise ValueError("Inactive handoff cannot create a review event")
        return self


class QuizResult(StrictModel):
    attempt_id: Identifier
    status: Literal["SUBMITTED"]
    submission_revision: Revision
    objective_scores: ObjectiveScores
    writing_self_scores: Annotated[
        tuple[WritingSelfScore, ...],
        BeforeValidator(_tuple),
        Field(max_length=20, json_schema_extra=_array_bounds_schema),
    ]
    question_results: Annotated[
        tuple[QuestionResult, ...],
        BeforeValidator(_tuple),
        Field(min_length=5, max_length=30, json_schema_extra=_array_bounds_schema),
    ]
    review_handoffs: Annotated[
        tuple[ReviewHandoff, ...],
        BeforeValidator(_tuple),
        Field(min_length=1, max_length=30, json_schema_extra=_array_bounds_schema),
    ]
    submitted_at: AwareTime

    @model_validator(mode="after")
    def distinct_members(self) -> Self:
        for identities in (
            [q.question_id for q in self.question_results],
            [q.question_id for q in self.writing_self_scores],
            [q.word_form_id for q in self.review_handoffs],
        ):
            if len(identities) != len(set(identities)):
                raise ValueError("Duplicate result membership")
        writing = {
            q.question_id: (q.self_score, q.rating)
            for q in self.question_results
            if isinstance(q, WritingQuestionResult)
        }
        if writing != {q.question_id: (q.self_score, q.rating) for q in self.writing_self_scores}:
            raise ValueError("Writing score membership differs from results")
        return self


def _quiz_attempt_schema(schema: dict[str, Any]) -> None:
    # Reuse Pydantic's generated reference so FastAPI can remap it correctly.
    result_schema = next(
        branch
        for branch in schema["properties"]["result"]["anyOf"]
        if branch.get("type") != "null"
    )
    # Only the outer object is closed. Closing these partial branches would
    # reject shared attempt properties. oneOf intersects with the generated core.
    schema["oneOf"] = [
        {
            "type": "object",
            "properties": {
                "status": {"type": "string", "const": "IN_PROGRESS"},
                "result": {"type": "null"},
            },
            "required": ["status", "result"],
        },
        {
            "type": "object",
            "properties": {
                "status": {"type": "string", "const": "SUBMITTED"},
                "result": result_schema,
            },
            "required": ["status", "result"],
        },
    ]


class QuizAttempt(StrictModel):
    model_config = ConfigDict(json_schema_extra=_quiz_attempt_schema)

    id: Identifier
    note_date: NoteDate
    status: Literal["IN_PROGRESS", "SUBMITTED"]
    questions: Annotated[
        tuple[PublicQuestion, ...],
        BeforeValidator(_tuple),
        Field(min_length=5, max_length=30, json_schema_extra=_array_bounds_schema),
    ]
    answers: Annotated[
        tuple[Answer, ...],
        BeforeValidator(_tuple),
        Field(max_length=30, json_schema_extra=_array_bounds_schema),
    ]
    saved_answer_count: Annotated[int, Field(ge=0, le=30)]
    snapshot_revision: Annotated[int, Field(ge=1)]
    submission_revision: Revision
    result: QuizResult | None
    answer_preconditions: Annotated[
        tuple[AnswerPrecondition, ...],
        BeforeValidator(_tuple),
        Field(min_length=5, max_length=30, json_schema_extra=_array_bounds_schema),
    ]

    @model_validator(mode="after")
    def state_and_membership(self) -> Self:
        validate_question_collection(self.questions)
        question_ids = {question.id for question in self.questions}
        answer_ids = {answer.question_id for answer in self.answers}
        if len(answer_ids) != len(self.answers) or not answer_ids <= question_ids:
            raise ValueError("Invalid answer membership")
        if any(answer.attempt_id != self.id for answer in self.answers):
            raise ValueError("Foreign attempt answer")
        if self.saved_answer_count != len(self.answers):
            raise ValueError("Saved answer count mismatch")
        if self.submission_revision != sum(answer.draft_revision for answer in self.answers):
            raise ValueError("Aggregate draft revision mismatch")
        revisions = {answer.question_id: answer.draft_revision for answer in self.answers}
        expected = tuple(
            AnswerPrecondition(
                question_id=question.id,
                draft_revision=revisions.get(question.id, 0),
                etag=answer_etag(self.id, question.id, revisions.get(question.id, 0)),
            )
            for question in self.questions
        )
        if self.answer_preconditions != expected:
            raise ValueError("Answer preconditions differ from saved revisions")
        if (self.status == "SUBMITTED") != (self.result is not None):
            raise ValueError("Terminal result/state mismatch")
        if self.result is not None:
            if (self.result.attempt_id, self.result.submission_revision) != (
                self.id,
                self.submission_revision,
            ):
                raise ValueError("Terminal result identity/revision mismatch")
            if {q.question_id for q in self.result.question_results} != question_ids:
                raise ValueError("Terminal result question membership mismatch")
        return self

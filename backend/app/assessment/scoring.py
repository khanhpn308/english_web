"""Pure quiz scoring and weakest-rating oracle (T059 / ADR-0005 C013-03).

Implements deterministic, side-effect-free scoring for MCQ, cloze, and writing questions.
Calculates objective metrics and maps aggregated question results per word form into
a single weakest SRS rating according to AGAIN < HARD < GOOD < EASY.
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from backend.app.review.srs import Rating, validate_rating

_ASCII_WHITESPACE_CHARS = " \t\r\n\x0c\x0b"
_ASCII_WHITESPACE_RE = re.compile(r"[ \t\r\n\x0c\x0b]+")

RATING_ORDINAL: dict[Rating, int] = {
    "AGAIN": 0,
    "HARD": 1,
    "GOOD": 2,
    "EASY": 3,
}

QuestionType = Literal["MCQ", "CLOZE", "WRITING"]
ObjectiveOutcome = Literal["CORRECT", "INCORRECT", "BLANK"]
WritingOutcome = Literal["SELF_SCORED"]


class QuizScoringError(ValueError):
    """Base domain error for quiz validation and scoring failures."""


class PendingSelfScoreError(QuizScoringError):
    """Raised when a writing question has a pending null self-score at terminal scoring."""


# ---------------------------------------------------------------------------
# Snapshots and Answers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MCQOption:
    id: str
    text_en: str


@dataclass(frozen=True)
class MCQSnapshot:
    id: str
    word_form_id: str
    prompt_en: str
    options: tuple[MCQOption, ...]
    correct_option_id: str
    explanation_vi: str
    type: Literal["MCQ"] = "MCQ"

    def __post_init__(self) -> None:
        object.__setattr__(self, "options", tuple(self.options))
        if not self.options:
            raise QuizScoringError("MCQ question options cannot be empty")
        option_ids = {opt.id for opt in self.options}
        if len(option_ids) != len(self.options):
            raise QuizScoringError("MCQ options contain duplicate IDs")
        if self.correct_option_id not in option_ids:
            raise QuizScoringError("MCQ correct_option_id is not present in options")


@dataclass(frozen=True)
class ClozeSnapshot:
    id: str
    word_form_id: str
    prompt_en: str
    accepted_answers: tuple[str, ...]
    explanation_vi: str
    type: Literal["CLOZE"] = "CLOZE"
    answer_policy_version: str = "cloze-answer-v1"

    def __post_init__(self) -> None:
        object.__setattr__(self, "accepted_answers", tuple(self.accepted_answers))
        if not self.accepted_answers:
            raise QuizScoringError("Cloze question must have at least one accepted answer")
        for ans in self.accepted_answers:
            if not ans.strip(_ASCII_WHITESPACE_CHARS):
                raise QuizScoringError("Cloze accepted answer cannot be empty or whitespace only")


@dataclass(frozen=True)
class WritingSnapshot:
    id: str
    word_form_id: str
    prompt_en: str
    target_lemma: str = ""
    type: Literal["WRITING"] = "WRITING"
    rubric_version: str = "writing-rubric-v1"


QuestionSnapshot = MCQSnapshot | ClozeSnapshot | WritingSnapshot


@dataclass(frozen=True)
class AnswerInput:
    question_id: str
    answer: str | None = None
    self_score: int | None = None


# ---------------------------------------------------------------------------
# Question Results
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MCQQuestionResult:
    question_id: str
    outcome: ObjectiveOutcome
    is_correct: bool
    rating: Rating
    correct_option_id: str
    explanation_vi: str
    type: Literal["MCQ"] = "MCQ"


@dataclass(frozen=True)
class ClozeQuestionResult:
    question_id: str
    outcome: ObjectiveOutcome
    is_correct: bool
    rating: Rating
    accepted_answers: tuple[str, ...]
    explanation_vi: str
    type: Literal["CLOZE"] = "CLOZE"


@dataclass(frozen=True)
class WritingQuestionResult:
    question_id: str
    self_score: int
    rating: Rating
    outcome: WritingOutcome = "SELF_SCORED"
    type: Literal["WRITING"] = "WRITING"


QuestionResult = MCQQuestionResult | ClozeQuestionResult | WritingQuestionResult


@dataclass(frozen=True)
class TypeObjectiveScore:
    total: int
    attempted: int
    correct: int
    accuracy: float | None


@dataclass(frozen=True)
class ObjectiveScores:
    mcq: TypeObjectiveScore
    cloze: TypeObjectiveScore


@dataclass(frozen=True)
class WritingSelfScore:
    question_id: str
    self_score: int
    rating: Rating


@dataclass(frozen=True)
class QuizScoringResult:
    objective_scores: ObjectiveScores
    writing_self_scores: tuple[WritingSelfScore, ...]
    question_results: tuple[QuestionResult, ...]
    weakest_ratings: dict[str, Rating]


# ---------------------------------------------------------------------------
# Normalization and Single-Question Oracles
# ---------------------------------------------------------------------------


def normalize_cloze_text(text: str) -> str:
    """NFC normalization, ASCII whitespace trimming/collapsing, and Unicode casefold.

    Preserves strict punctuation, spelling, accents, and non-ASCII whitespace.
    """
    nfc = unicodedata.normalize("NFC", text)
    trimmed = nfc.strip(_ASCII_WHITESPACE_CHARS)
    collapsed = _ASCII_WHITESPACE_RE.sub(" ", trimmed)
    return collapsed.casefold()


def writing_score_to_rating(score: int) -> Rating:
    """Map integer self-score 0..4 to SRS Rating (ADR-0005 C013-03)."""
    if type(score) is not int:
        raise QuizScoringError("Writing score must be a strict integer")
    match score:
        case 0 | 1:
            return "AGAIN"
        case 2:
            return "HARD"
        case 3:
            return "GOOD"
        case 4:
            return "EASY"
        case _:
            raise QuizScoringError("Writing score must be in range 0..4")


def score_mcq(question: MCQSnapshot, answer: AnswerInput | str | None) -> MCQQuestionResult:
    """Score an MCQ question against the immutable snapshot."""
    if isinstance(answer, AnswerInput):
        if answer.question_id != question.id:
            raise QuizScoringError(
                f"Answer question ID '{answer.question_id}' does not match "
                f"question ID '{question.id}'"
            )
        if answer.self_score is not None:
            raise QuizScoringError("Objective questions cannot have a selfScore")
        ans_text = answer.answer
    else:
        ans_text = answer

    if ans_text is None or ans_text == "":
        return MCQQuestionResult(
            question_id=question.id,
            outcome="BLANK",
            is_correct=False,
            rating="AGAIN",
            correct_option_id=question.correct_option_id,
            explanation_vi=question.explanation_vi,
        )

    valid_option_ids = {opt.id for opt in question.options}
    if ans_text not in valid_option_ids:
        raise QuizScoringError("Option ID outside snapshot options")

    is_correct = ans_text == question.correct_option_id
    outcome: ObjectiveOutcome = "CORRECT" if is_correct else "INCORRECT"
    rating: Rating = "GOOD" if is_correct else "AGAIN"

    return MCQQuestionResult(
        question_id=question.id,
        outcome=outcome,
        is_correct=is_correct,
        rating=rating,
        correct_option_id=question.correct_option_id,
        explanation_vi=question.explanation_vi,
    )


def score_cloze(question: ClozeSnapshot, answer: AnswerInput | str | None) -> ClozeQuestionResult:
    """Score a cloze question using NFC, ASCII trim/collapse, and casefold normalization."""
    if isinstance(answer, AnswerInput):
        if answer.question_id != question.id:
            raise QuizScoringError(
                f"Answer question ID '{answer.question_id}' does not match "
                f"question ID '{question.id}'"
            )
        if answer.self_score is not None:
            raise QuizScoringError("Objective questions cannot have a selfScore")
        ans_text = answer.answer
    else:
        ans_text = answer

    if ans_text is None or not ans_text.strip(_ASCII_WHITESPACE_CHARS):
        return ClozeQuestionResult(
            question_id=question.id,
            outcome="BLANK",
            is_correct=False,
            rating="AGAIN",
            accepted_answers=question.accepted_answers,
            explanation_vi=question.explanation_vi,
        )

    norm_user = normalize_cloze_text(ans_text)
    norm_accepted = {normalize_cloze_text(alt) for alt in question.accepted_answers}

    is_correct = norm_user in norm_accepted
    outcome: ObjectiveOutcome = "CORRECT" if is_correct else "INCORRECT"
    rating: Rating = "GOOD" if is_correct else "AGAIN"

    return ClozeQuestionResult(
        question_id=question.id,
        outcome=outcome,
        is_correct=is_correct,
        rating=rating,
        accepted_answers=question.accepted_answers,
        explanation_vi=question.explanation_vi,
    )


def score_writing(
    question: WritingSnapshot, answer: AnswerInput | tuple[str | None, int | None]
) -> WritingQuestionResult:
    """Score a writing question, validating strict 0..4 score and blank-text rules."""
    if isinstance(answer, AnswerInput):
        if answer.question_id != question.id:
            raise QuizScoringError(
                f"Answer question ID '{answer.question_id}' does not match "
                f"question ID '{question.id}'"
            )
        ans_text = answer.answer
        score = answer.self_score
    else:
        ans_text, score = answer

    if score is None:
        raise PendingSelfScoreError(
            "Writing question requires an explicit self-score at terminal submission"
        )

    if type(score) is not int or score < 0 or score > 4:
        raise QuizScoringError("Writing self-score must be an integer between 0 and 4")

    is_blank_text = ans_text is None or ans_text.strip() == ""
    if is_blank_text and score > 0:
        raise QuizScoringError("Blank writing answer cannot have a positive self-score")

    rating = writing_score_to_rating(score)
    return WritingQuestionResult(
        question_id=question.id,
        self_score=score,
        rating=rating,
    )


def weakest_rating(ratings: Iterable[Rating]) -> Rating:
    """Deterministic weakest rating oracle: AGAIN < HARD < GOOD < EASY."""
    rating_list = list(ratings)
    if not rating_list:
        raise ValueError("Cannot determine weakest rating from an empty collection")
    for r in rating_list:
        validate_rating(r)
    return min(rating_list, key=lambda r: RATING_ORDINAL[r])


# ---------------------------------------------------------------------------
# Aggregate Quiz Scorer
# ---------------------------------------------------------------------------


def score_quiz(
    questions: Sequence[QuestionSnapshot],
    answers: Sequence[AnswerInput] | Mapping[str, AnswerInput],
) -> QuizScoringResult:
    """Score an entire quiz snapshot against draft/submitted answers.

    Preconditions:
    - Questions must have unique IDs.
    - Any present answer must match a question ID in the snapshot.
    - Missing objective answers are treated as blank.
    - Missing writing answers or null writing self-scores raise PendingSelfScoreError.
    - Computes objective totals, attempted counts, and accuracy (null if attempted == 0).
    - Groups question results by wordFormId and determines the single weakest rating per form.
    """
    question_ids = set()
    for q in questions:
        if q.id in question_ids:
            raise QuizScoringError("Duplicate question ID in snapshot")
        question_ids.add(q.id)

    if isinstance(answers, Mapping):
        for key, ans in answers.items():
            if not isinstance(ans, AnswerInput) or ans.question_id != key:
                raise QuizScoringError(
                    f"Answer mapping key '{key}' does not match AnswerInput question_id "
                    f"'{getattr(ans, 'question_id', None)}'"
                )
        answers_map = dict(answers)
    else:
        answers_map = {}
        for ans in answers:
            if ans.question_id in answers_map:
                raise QuizScoringError("Duplicate answer for question ID in payload")
            answers_map[ans.question_id] = ans

    for ans_q_id in answers_map:
        if ans_q_id not in question_ids:
            raise QuizScoringError("Unmatched question ID in answers payload")

    question_results: list[QuestionResult] = []
    writing_self_scores: list[WritingSelfScore] = []
    form_ratings: dict[str, list[Rating]] = defaultdict(list)

    for q in questions:
        ans_input = answers_map.get(q.id)

        if isinstance(q, MCQSnapshot):
            effective_ans = (
                ans_input if ans_input is not None else AnswerInput(question_id=q.id, answer="")
            )
            mcq_res = score_mcq(q, effective_ans)
            question_results.append(mcq_res)
            form_ratings[q.word_form_id].append(mcq_res.rating)

        elif isinstance(q, ClozeSnapshot):
            effective_ans = (
                ans_input if ans_input is not None else AnswerInput(question_id=q.id, answer="")
            )
            cloze_res = score_cloze(q, effective_ans)
            question_results.append(cloze_res)
            form_ratings[q.word_form_id].append(cloze_res.rating)

        elif isinstance(q, WritingSnapshot):
            effective_ans = (
                ans_input
                if ans_input is not None
                else AnswerInput(question_id=q.id, answer="", self_score=None)
            )
            writing_res = score_writing(q, effective_ans)
            question_results.append(writing_res)
            writing_self_scores.append(
                WritingSelfScore(
                    question_id=q.id,
                    self_score=writing_res.self_score,
                    rating=writing_res.rating,
                )
            )
            form_ratings[q.word_form_id].append(writing_res.rating)

        else:
            raise QuizScoringError("Unsupported question snapshot type")

    # Calculate objective metrics
    mcq_total = sum(1 for q in questions if q.type == "MCQ")
    mcq_attempted = sum(1 for r in question_results if r.type == "MCQ" and r.outcome != "BLANK")
    mcq_correct = sum(1 for r in question_results if r.type == "MCQ" and r.outcome == "CORRECT")
    mcq_accuracy = (mcq_correct / mcq_attempted) if mcq_attempted > 0 else None

    cloze_total = sum(1 for q in questions if q.type == "CLOZE")
    cloze_attempted = sum(1 for r in question_results if r.type == "CLOZE" and r.outcome != "BLANK")
    cloze_correct = sum(1 for r in question_results if r.type == "CLOZE" and r.outcome == "CORRECT")
    cloze_accuracy = (cloze_correct / cloze_attempted) if cloze_attempted > 0 else None

    objective_scores = ObjectiveScores(
        mcq=TypeObjectiveScore(
            total=mcq_total,
            attempted=mcq_attempted,
            correct=mcq_correct,
            accuracy=mcq_accuracy,
        ),
        cloze=TypeObjectiveScore(
            total=cloze_total,
            attempted=cloze_attempted,
            correct=cloze_correct,
            accuracy=cloze_accuracy,
        ),
    )

    weakest_per_form: dict[str, Rating] = {
        w_id: weakest_rating(ratings) for w_id, ratings in form_ratings.items()
    }

    return QuizScoringResult(
        objective_scores=objective_scores,
        writing_self_scores=tuple(writing_self_scores),
        question_results=tuple(question_results),
        weakest_ratings=weakest_per_form,
    )

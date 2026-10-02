"""Tests for pure quiz scoring, cloze normalization, and weakest-rating oracle (T059).

Covers:
- Strict ASCII whitespace trimming/collapsing, NFC normalization, and Unicode casefold.
- MCQ option validation, exact ID comparison, blank handling, and key disclosure invariants.
- Writing 0-4 self-score mapping, blank text rules, pending null rejection, and type safety.
- Aggregate quiz scoring, per-type objective metrics (total, attempted, correct, accuracy),
  and deterministic weakest SRS rating grouping per word form (AGAIN < HARD < GOOD < EASY).
- Repeated call purity and idempotency without mutating inputs or calling language models.
"""

from dataclasses import FrozenInstanceError, dataclass
from typing import cast

import pytest
from backend.app.assessment.scoring import (
    AnswerInput,
    ClozeQuestionResult,
    ClozeSnapshot,
    MCQOption,
    MCQQuestionResult,
    MCQSnapshot,
    PendingSelfScoreError,
    QuizScoringError,
    TypeObjectiveScore,
    WritingQuestionResult,
    WritingSelfScore,
    WritingSnapshot,
    normalize_cloze_text,
    score_cloze,
    score_mcq,
    score_quiz,
    score_writing,
    weakest_rating,
    writing_score_to_rating,
)
from backend.app.review.srs import Rating

# ---------------------------------------------------------------------------
# 1. Cloze Normalization Tests
# ---------------------------------------------------------------------------


def test_normalize_cloze_text_casefold_and_ascii_spaces() -> None:
    """Exact ASCII trimming, internal whitespace collapsing, and Unicode casefold."""
    assert normalize_cloze_text("robust") == "robust"
    assert normalize_cloze_text("ROBUST") == "robust"
    assert normalize_cloze_text("  robust  ") == "robust"
    assert normalize_cloze_text("\trobust\r\n") == "robust"
    assert normalize_cloze_text("\v\f robust \f\v") == "robust"
    assert normalize_cloze_text("robust\t\tsystem") == "robust system"
    assert normalize_cloze_text("  robust   adaptive   system  ") == "robust adaptive system"


def test_normalize_cloze_text_strict_punctuation_and_spelling() -> None:
    """Accents, punctuation, spelling, and extra tokens must remain strict."""
    norm_robust = normalize_cloze_text("robust")
    assert normalize_cloze_text("robuts") != norm_robust
    assert normalize_cloze_text("robust.") != norm_robust
    assert normalize_cloze_text("robust!") != norm_robust
    assert normalize_cloze_text("robust,") != norm_robust
    assert normalize_cloze_text("a robust") != norm_robust
    assert normalize_cloze_text("the robust") != norm_robust


def test_normalize_cloze_text_non_ascii_whitespace_strict() -> None:
    """Non-ASCII whitespace (NBSP, ideographic space) must NOT be collapsed or stripped."""
    nbsp = "\u00a0"
    ideographic = "\u3000"
    norm_robust = normalize_cloze_text("robust")
    # Non-ASCII whitespace is preserved and therefore does not match plain 'robust'
    assert normalize_cloze_text(f"{nbsp}robust{nbsp}") != norm_robust
    assert normalize_cloze_text(f"{ideographic}robust{ideographic}") != norm_robust
    assert nbsp in normalize_cloze_text(f"{nbsp}robust")


def test_normalize_cloze_text_nfc_and_casefold_equivalence() -> None:
    """Composed and decomposed Unicode normalize to identical NFC casefolded form."""
    composed = "café"
    decomposed = "cafe\u0301"  # 'e' + combining acute accent
    assert normalize_cloze_text(composed) == normalize_cloze_text(decomposed)
    assert normalize_cloze_text("CAFÉ") == normalize_cloze_text(decomposed)
    # Unicode casefold: German eszett
    assert normalize_cloze_text("STRAßE") == "strasse"
    assert normalize_cloze_text("straße") == "strasse"


def test_normalize_cloze_text_blank_inputs() -> None:
    """Empty or ASCII-whitespace-only strings normalize to empty string."""
    assert normalize_cloze_text("") == ""
    assert normalize_cloze_text("   ") == ""
    assert normalize_cloze_text("\t\r\n\x0c\x0b") == ""


# ---------------------------------------------------------------------------
# 2. MCQ Scoring Tests
# ---------------------------------------------------------------------------


@pytest.fixture
def mcq_question() -> MCQSnapshot:
    return MCQSnapshot(
        id="q_mcq_1",
        word_form_id="wf_1",
        prompt_en="Synthetic prompt for testing",
        options=(
            MCQOption(id="opt_a", text_en="Option Alpha"),
            MCQOption(id="opt_b", text_en="Option Beta"),
            MCQOption(id="opt_c", text_en="Option Gamma"),
        ),
        correct_option_id="opt_a",
        explanation_vi="Giải thích mẫu bằng tiếng Việt.",
    )


def test_score_mcq_correct(mcq_question: MCQSnapshot) -> None:
    """Exact option match yields CORRECT, is_correct=True, and GOOD rating."""
    result = score_mcq(mcq_question, AnswerInput(question_id="q_mcq_1", answer="opt_a"))
    assert isinstance(result, MCQQuestionResult)
    assert result.question_id == "q_mcq_1"
    assert result.type == "MCQ"
    assert result.outcome == "CORRECT"
    assert result.is_correct is True
    assert result.rating == "GOOD"
    assert result.correct_option_id == "opt_a"
    assert result.explanation_vi == "Giải thích mẫu bằng tiếng Việt."


def test_score_mcq_incorrect(mcq_question: MCQSnapshot) -> None:
    """Mismatched valid option yields INCORRECT, is_correct=False, and AGAIN rating."""
    result = score_mcq(mcq_question, AnswerInput(question_id="q_mcq_1", answer="opt_b"))
    assert result.outcome == "INCORRECT"
    assert result.is_correct is False
    assert result.rating == "AGAIN"
    assert result.correct_option_id == "opt_a"


def test_score_mcq_blank(mcq_question: MCQSnapshot) -> None:
    """Empty string or None answer yields BLANK, is_correct=False, and AGAIN rating."""
    result_empty = score_mcq(mcq_question, AnswerInput(question_id="q_mcq_1", answer=""))
    assert result_empty.outcome == "BLANK"
    assert result_empty.is_correct is False
    assert result_empty.rating == "AGAIN"

    result_none = score_mcq(mcq_question, AnswerInput(question_id="q_mcq_1", answer=None))
    assert result_none.outcome == "BLANK"
    assert result_none.is_correct is False
    assert result_none.rating == "AGAIN"


def test_score_mcq_invalid_option_id(mcq_question: MCQSnapshot) -> None:
    """Non-blank option ID outside snapshot options fails validation."""
    with pytest.raises(QuizScoringError) as exc_info:
        score_mcq(mcq_question, AnswerInput(question_id="q_mcq_1", answer="opt_unknown"))
    assert "outside" in str(exc_info.value).lower() or "option" in str(exc_info.value).lower()


def test_score_mcq_rejects_objective_self_score(mcq_question: MCQSnapshot) -> None:
    """MCQ answer with self_score fails validation."""
    with pytest.raises(QuizScoringError):
        score_mcq(
            mcq_question,
            AnswerInput(question_id="q_mcq_1", answer="opt_a", self_score=3),
        )


def test_score_mcq_no_whitespace_normalization_on_options(mcq_question: MCQSnapshot) -> None:
    """Option IDs are compared exactly; no whitespace stripping or casefold."""
    with pytest.raises(QuizScoringError):
        score_mcq(mcq_question, AnswerInput(question_id="q_mcq_1", answer="opt_a "))
    with pytest.raises(QuizScoringError):
        score_mcq(mcq_question, AnswerInput(question_id="q_mcq_1", answer="OPT_A"))


def test_mcq_snapshot_validation() -> None:
    """Snapshot consistency: correct_option_id must exist in options."""
    with pytest.raises(QuizScoringError):
        MCQSnapshot(
            id="q_bad",
            word_form_id="wf_1",
            prompt_en="Prompt",
            options=(MCQOption("opt_1", "One"),),
            correct_option_id="opt_nonexistent",
            explanation_vi="Explanation",
        )
    # Empty options rejected
    with pytest.raises(QuizScoringError):
        MCQSnapshot(
            id="q_bad2",
            word_form_id="wf_1",
            prompt_en="Prompt",
            options=(),
            correct_option_id="opt_1",
            explanation_vi="Explanation",
        )


# ---------------------------------------------------------------------------
# 3. Cloze Scoring Tests
# ---------------------------------------------------------------------------


@pytest.fixture
def cloze_question() -> ClozeSnapshot:
    return ClozeSnapshot(
        id="q_cloze_1",
        word_form_id="wf_2",
        prompt_en="Synthetic sentence with [...] for testing.",
        accepted_answers=("robust", "sturdy"),
        explanation_vi="Giải thích điền từ tiếng Việt.",
        answer_policy_version="cloze-answer-v1",
    )


def test_score_cloze_exact_and_normalized_matches(cloze_question: ClozeSnapshot) -> None:
    """NFC, ASCII trimming/collapsing, and casefold matches accepted alternatives."""
    for valid_variant in ("robust", "ROBUST", " robust ", "\trobust\n", "STURDY", " sturdy "):
        ans = AnswerInput(question_id="q_cloze_1", answer=valid_variant)
        result = score_cloze(cloze_question, ans)
        assert isinstance(result, ClozeQuestionResult)
        assert result.outcome == "CORRECT"
        assert result.is_correct is True
        assert result.rating == "GOOD"
        assert result.accepted_answers == ("robust", "sturdy")
        assert result.explanation_vi == "Giải thích điền từ tiếng Việt."


def test_score_cloze_mismatches(cloze_question: ClozeSnapshot) -> None:
    """Typo, strict punctuation, and non-ASCII whitespace yield INCORRECT / AGAIN."""
    for wrong_answer in ("robuts", "robust.", "robust!", "a robust", "\u00a0robust"):
        ans = AnswerInput(question_id="q_cloze_1", answer=wrong_answer)
        result = score_cloze(cloze_question, ans)
        assert result.outcome == "INCORRECT"
        assert result.is_correct is False
        assert result.rating == "AGAIN"


def test_score_cloze_blank(cloze_question: ClozeSnapshot) -> None:
    """Empty string, whitespace-only, or None yields BLANK / AGAIN."""
    for blank_val in ("", "   ", "\t\r\n", None):
        result = score_cloze(cloze_question, AnswerInput(question_id="q_cloze_1", answer=blank_val))
        assert result.outcome == "BLANK"
        assert result.is_correct is False
        assert result.rating == "AGAIN"


def test_score_cloze_rejects_objective_self_score(cloze_question: ClozeSnapshot) -> None:
    """Cloze answer with self_score fails validation."""
    with pytest.raises(QuizScoringError):
        score_cloze(
            cloze_question,
            AnswerInput(question_id="q_cloze_1", answer="robust", self_score=0),
        )


def test_cloze_snapshot_validation() -> None:
    """Cloze snapshot requires at least one non-empty accepted alternative."""
    with pytest.raises(QuizScoringError):
        ClozeSnapshot(
            id="q_bad",
            word_form_id="wf_1",
            prompt_en="Prompt",
            accepted_answers=(),
            explanation_vi="Explanation",
        )
    with pytest.raises(QuizScoringError):
        ClozeSnapshot(
            id="q_bad2",
            word_form_id="wf_1",
            prompt_en="Prompt",
            accepted_answers=("  ",),
            explanation_vi="Explanation",
        )


# ---------------------------------------------------------------------------
# 4. Writing Scoring & Rubric Tests
# ---------------------------------------------------------------------------


@pytest.fixture
def writing_question() -> WritingSnapshot:
    return WritingSnapshot(
        id="q_writing_1",
        word_form_id="wf_3",
        prompt_en="Write a synthetic academic sentence using the target lemma.",
        target_lemma="synthesize",
        rubric_version="writing-rubric-v1",
    )


def test_writing_score_to_rating_mapping() -> None:
    """Contract rubric mapping: 0,1 -> AGAIN; 2 -> HARD; 3 -> GOOD; 4 -> EASY."""
    assert writing_score_to_rating(0) == "AGAIN"
    assert writing_score_to_rating(1) == "AGAIN"
    assert writing_score_to_rating(2) == "HARD"
    assert writing_score_to_rating(3) == "GOOD"
    assert writing_score_to_rating(4) == "EASY"


def test_score_writing_valid_scores(writing_question: WritingSnapshot) -> None:
    """Scores 0-4 preserve user score and produce correct rating."""
    expected_ratings = {
        0: "AGAIN",
        1: "AGAIN",
        2: "HARD",
        3: "GOOD",
        4: "EASY",
    }
    for score, expected_rating in expected_ratings.items():
        result = score_writing(
            writing_question,
            AnswerInput(
                question_id="q_writing_1",
                answer="A synthetic non-empty sentence.",
                self_score=score,
            ),
        )
        assert isinstance(result, WritingQuestionResult)
        assert result.outcome == "SELF_SCORED"
        assert result.self_score == score
        assert result.rating == expected_rating


def test_score_writing_blank_text_rules(writing_question: WritingSnapshot) -> None:
    """Blank writing is valid ONLY with explicit zero; positive score fails."""
    # Blank text with score 0 is valid -> AGAIN
    for blank_text in ("", "   ", "\t\n", None):
        result = score_writing(
            writing_question,
            AnswerInput(question_id="q_writing_1", answer=blank_text, self_score=0),
        )
        assert result.outcome == "SELF_SCORED"
        assert result.self_score == 0
        assert result.rating == "AGAIN"

    # Blank text with positive score (1..4) must fail validation
    for score in (1, 2, 3, 4):
        with pytest.raises(QuizScoringError) as exc_info:
            score_writing(
                writing_question,
                AnswerInput(question_id="q_writing_1", answer="", self_score=score),
            )
        assert "blank" in str(exc_info.value).lower()


def test_score_writing_pending_null_rejection(writing_question: WritingSnapshot) -> None:
    """Null self-score is pending and must reject terminal scoring without substituting 0."""
    with pytest.raises(PendingSelfScoreError) as exc_info:
        score_writing(
            writing_question,
            AnswerInput(
                question_id="q_writing_1",
                answer="A sentence written by user.",
                self_score=None,
            ),
        )
    assert "pending" in str(exc_info.value).lower() or "score" in str(exc_info.value).lower()


def test_score_writing_type_and_range_validation(writing_question: WritingSnapshot) -> None:
    """Booleans, floats, strings, and out-of-range values fail validation."""
    invalid_scores = (True, False, 3.0, 2.5, "3", "0", -1, 5, 10)
    for bad_score in invalid_scores:
        with pytest.raises(QuizScoringError):
            score_writing(
                writing_question,
                AnswerInput(
                    question_id="q_writing_1",
                    answer="Synthetic sentence.",
                    self_score=cast(int, bad_score),
                ),
            )


# ---------------------------------------------------------------------------
# 5. Weakest Rating Oracle Tests
# ---------------------------------------------------------------------------


def test_weakest_rating_ordering() -> None:
    """Ordinal rule: AGAIN < HARD < GOOD < EASY."""
    assert weakest_rating(["AGAIN"]) == "AGAIN"
    assert weakest_rating(["HARD"]) == "HARD"
    assert weakest_rating(["GOOD"]) == "GOOD"
    assert weakest_rating(["EASY"]) == "EASY"

    # Pairwise comparisons
    assert weakest_rating(["AGAIN", "HARD"]) == "AGAIN"
    assert weakest_rating(["AGAIN", "GOOD"]) == "AGAIN"
    assert weakest_rating(["AGAIN", "EASY"]) == "AGAIN"
    assert weakest_rating(["HARD", "GOOD"]) == "HARD"
    assert weakest_rating(["HARD", "EASY"]) == "HARD"
    assert weakest_rating(["GOOD", "EASY"]) == "GOOD"


def test_weakest_rating_permutation_invariance() -> None:
    """Weakest rating must be completely independent of input order."""
    ratings: list[Rating] = ["GOOD", "AGAIN", "EASY", "HARD"]
    from itertools import permutations

    for p in permutations(ratings):
        assert weakest_rating(p) == "AGAIN"

    easy_good_hard: tuple[Rating, ...] = ("EASY", "GOOD", "HARD")
    for p in permutations(easy_good_hard):
        assert weakest_rating(p) == "HARD"

    easy_good: tuple[Rating, ...] = ("EASY", "GOOD")
    for p in permutations(easy_good):
        assert weakest_rating(p) == "GOOD"


def test_weakest_rating_empty_raises() -> None:
    """Empty iterable has no weakest rating."""
    with pytest.raises(ValueError):
        weakest_rating([])


# ---------------------------------------------------------------------------
# 6. Aggregate Quiz Scoring & Five-Question Fixture (AC-14 / C013-01 / C013-03)
# ---------------------------------------------------------------------------


@pytest.fixture
def five_question_snapshot() -> list[MCQSnapshot | ClozeSnapshot | WritingSnapshot]:
    """Synthetic 5-question fixture with 3 word forms (A, B, C):

    - Form A: MCQ A, Cloze A
    - Form B: MCQ B, Writing B
    - Form C: Cloze C
    """
    return [
        MCQSnapshot(
            id="q_a",
            word_form_id="wf_a",
            prompt_en="Prompt MCQ A",
            options=(MCQOption("opt_1", "Option 1"), MCQOption("opt_2", "Option 2")),
            correct_option_id="opt_1",
            explanation_vi="Giải thích A.",
        ),
        MCQSnapshot(
            id="q_b",
            word_form_id="wf_b",
            prompt_en="Prompt MCQ B",
            options=(MCQOption("opt_1", "Option 1"), MCQOption("opt_2", "Option 2")),
            correct_option_id="opt_1",
            explanation_vi="Giải thích B.",
        ),
        ClozeSnapshot(
            id="q_c",
            word_form_id="wf_a",
            prompt_en="Prompt Cloze A [...]",
            accepted_answers=("target_word_a",),
            explanation_vi="Giải thích C.",
        ),
        ClozeSnapshot(
            id="q_d",
            word_form_id="wf_c",
            prompt_en="Prompt Cloze C [...]",
            accepted_answers=("target_word_c",),
            explanation_vi="Giải thích D.",
        ),
        WritingSnapshot(
            id="q_e",
            word_form_id="wf_b",
            prompt_en="Prompt Writing B",
            target_lemma="lemma_b",
        ),
    ]


def test_score_quiz_five_question_fixture(
    five_question_snapshot: list[MCQSnapshot | ClozeSnapshot | WritingSnapshot],
) -> None:
    """Mixed responses:

    - q_a (MCQ Form A): opt_1 -> CORRECT (GOOD)
    - q_b (MCQ Form B): opt_2 -> INCORRECT (AGAIN)
    - q_c (Cloze Form A): wrong_word -> INCORRECT (AGAIN)
    - q_d (Cloze Form C): target_word_c -> CORRECT (GOOD)
    - q_e (Writing Form B): score 3 -> SELF_SCORED (GOOD)

    Form groupings:
    - Form A (q_a GOOD, q_c AGAIN) -> weakest AGAIN
    - Form B (q_b AGAIN, q_e GOOD) -> weakest AGAIN
    - Form C (q_d GOOD) -> weakest GOOD

    Objective scores:
    - MCQ: total=2, attempted=2, correct=1, accuracy=0.5
    - Cloze: total=2, attempted=2, correct=1, accuracy=0.5
    """
    answers = [
        AnswerInput(question_id="q_a", answer="opt_1"),
        AnswerInput(question_id="q_b", answer="opt_2"),
        AnswerInput(question_id="q_c", answer="wrong_word"),
        AnswerInput(question_id="q_d", answer="target_word_c"),
        AnswerInput(question_id="q_e", answer="My sentence.", self_score=3),
    ]

    result = score_quiz(five_question_snapshot, answers)

    # 1. Objective scores
    assert result.objective_scores.mcq == TypeObjectiveScore(
        total=2, attempted=2, correct=1, accuracy=0.5
    )
    assert result.objective_scores.cloze == TypeObjectiveScore(
        total=2, attempted=2, correct=1, accuracy=0.5
    )

    # 2. Writing self-scores
    assert result.writing_self_scores == (
        WritingSelfScore(question_id="q_e", self_score=3, rating="GOOD"),
    )

    # 3. Question results
    assert len(result.question_results) == 5
    assert result.question_results[0].outcome == "CORRECT"
    assert result.question_results[0].rating == "GOOD"
    assert result.question_results[1].outcome == "INCORRECT"
    assert result.question_results[1].rating == "AGAIN"
    assert result.question_results[2].outcome == "INCORRECT"
    assert result.question_results[2].rating == "AGAIN"
    assert result.question_results[3].outcome == "CORRECT"
    assert result.question_results[3].rating == "GOOD"
    assert result.question_results[4].outcome == "SELF_SCORED"
    assert result.question_results[4].rating == "GOOD"

    # 4. Grouped weakest ratings
    assert result.weakest_ratings == {
        "wf_a": "AGAIN",
        "wf_b": "AGAIN",
        "wf_c": "GOOD",
    }


def test_score_quiz_with_blank_objective_answers(
    five_question_snapshot: list[MCQSnapshot | ClozeSnapshot | WritingSnapshot],
) -> None:
    """Blank answers count towards total but not attempted; accuracy is correct/attempted."""
    answers = [
        AnswerInput(question_id="q_a", answer="opt_1"),  # Correct
        AnswerInput(question_id="q_b", answer=""),  # Blank
        AnswerInput(question_id="q_c", answer=None),  # Blank
        AnswerInput(question_id="q_d", answer=None),  # Blank
        AnswerInput(question_id="q_e", answer="Sentence", self_score=4),  # EASY
    ]

    result = score_quiz(five_question_snapshot, answers)

    # MCQ: 1 attempted, 1 correct -> accuracy = 1.0
    assert result.objective_scores.mcq.total == 2
    assert result.objective_scores.mcq.attempted == 1
    assert result.objective_scores.mcq.correct == 1
    assert result.objective_scores.mcq.accuracy == 1.0

    # Cloze: 0 attempted -> accuracy = None
    assert result.objective_scores.cloze.total == 2
    assert result.objective_scores.cloze.attempted == 0
    assert result.objective_scores.cloze.correct == 0
    assert result.objective_scores.cloze.accuracy is None

    # Form A had q_a (GOOD) and q_c (BLANK -> AGAIN) -> weakest AGAIN
    assert result.weakest_ratings["wf_a"] == "AGAIN"
    # Form B had q_b (BLANK -> AGAIN) and q_e (EASY) -> weakest AGAIN
    assert result.weakest_ratings["wf_b"] == "AGAIN"
    # Form C had q_d (BLANK -> AGAIN) -> weakest AGAIN
    assert result.weakest_ratings["wf_c"] == "AGAIN"


def test_score_quiz_missing_answers_in_payload(
    five_question_snapshot: list[MCQSnapshot | ClozeSnapshot | WritingSnapshot],
) -> None:
    """Missing objective answer is treated as blank. Missing writing is pending and fails."""
    # Only supply answer for q_a; q_e (writing) is missing
    partial_answers = [AnswerInput(question_id="q_a", answer="opt_1")]
    with pytest.raises(PendingSelfScoreError):
        score_quiz(five_question_snapshot, partial_answers)

    # When writing has explicit score 0 for blank text, missing objective answers are blank
    answers_with_writing = [
        AnswerInput(question_id="q_a", answer="opt_1"),
        AnswerInput(question_id="q_e", answer="", self_score=0),
    ]
    result = score_quiz(five_question_snapshot, answers_with_writing)
    assert result.objective_scores.mcq.total == 2
    assert result.objective_scores.mcq.attempted == 1
    assert result.objective_scores.cloze.total == 2
    assert result.objective_scores.cloze.attempted == 0


def test_score_quiz_unmatched_answer_raises(
    five_question_snapshot: list[MCQSnapshot | ClozeSnapshot | WritingSnapshot],
) -> None:
    """Answers for questions not in snapshot must fail validation."""
    answers = [
        AnswerInput(question_id="q_a", answer="opt_1"),
        AnswerInput(question_id="q_b", answer="opt_1"),
        AnswerInput(question_id="q_c", answer="target_word_a"),
        AnswerInput(question_id="q_d", answer="target_word_c"),
        AnswerInput(question_id="q_e", answer="S", self_score=2),
        AnswerInput(question_id="q_unknown_rogue", answer="val"),
    ]
    with pytest.raises(QuizScoringError) as exc_info:
        score_quiz(five_question_snapshot, answers)
    assert "unknown" in str(exc_info.value).lower() or "unmatched" in str(exc_info.value).lower()


def test_score_quiz_duplicate_question_in_snapshot_raises() -> None:
    """Duplicate question ID in snapshot fails validation."""
    dup_snapshot = [
        MCQSnapshot("q_1", "wf_1", "P", (MCQOption("opt_1", "O"),), "opt_1", "E"),
        MCQSnapshot("q_1", "wf_2", "P2", (MCQOption("opt_1", "O"),), "opt_1", "E2"),
    ]
    with pytest.raises(QuizScoringError):
        score_quiz(dup_snapshot, [AnswerInput("q_1", "opt_1")])


def test_score_quiz_idempotency_and_no_mutation(
    five_question_snapshot: list[MCQSnapshot | ClozeSnapshot | WritingSnapshot],
) -> None:
    """Repeated calls return equal results and never mutate question/answer structures."""
    answers = [
        AnswerInput(question_id="q_a", answer="opt_1"),
        AnswerInput(question_id="q_b", answer="opt_2"),
        AnswerInput(question_id="q_c", answer="wrong_word"),
        AnswerInput(question_id="q_d", answer="target_word_c"),
        AnswerInput(question_id="q_e", answer="My sentence.", self_score=3),
    ]

    res1 = score_quiz(five_question_snapshot, answers)
    res2 = score_quiz(five_question_snapshot, answers)

    assert res1 == res2
    assert res1.objective_scores == res2.objective_scores
    assert res1.weakest_ratings == res2.weakest_ratings

    # Ensure snapshots were not mutated
    cloze_snapshot = five_question_snapshot[2]
    assert isinstance(cloze_snapshot, ClozeSnapshot)
    assert cloze_snapshot.accepted_answers == ("target_word_a",)


def test_frozen_dataclass_invariants(
    mcq_question: MCQSnapshot,
    cloze_question: ClozeSnapshot,
    writing_question: WritingSnapshot,
) -> None:
    """Snapshot and result structures are frozen value objects."""
    with pytest.raises(FrozenInstanceError):
        field_prompt = "prompt_en"
        setattr(mcq_question, field_prompt, "Mutated")

    with pytest.raises(FrozenInstanceError):
        field_answers = "accepted_answers"
        setattr(cloze_question, field_answers, ("mutated",))

    with pytest.raises(FrozenInstanceError):
        field_lemma = "target_lemma"
        setattr(writing_question, field_lemma, "mutated")


def test_mcq_snapshot_duplicate_option_ids() -> None:
    """MCQSnapshot rejects duplicate option IDs."""
    with pytest.raises(QuizScoringError) as exc_info:
        MCQSnapshot(
            id="q_dup",
            word_form_id="wf_1",
            prompt_en="P",
            options=(MCQOption("opt_1", "O1"), MCQOption("opt_1", "O2")),
            correct_option_id="opt_1",
            explanation_vi="E",
        )
    assert "duplicate" in str(exc_info.value).lower()


def test_writing_score_to_rating_invalid_inputs() -> None:
    """writing_score_to_rating rejects non-int and out-of-range values."""
    with pytest.raises(QuizScoringError):
        writing_score_to_rating(cast(int, "3"))
    with pytest.raises(QuizScoringError):
        writing_score_to_rating(cast(int, True))
    with pytest.raises(QuizScoringError):
        writing_score_to_rating(-1)
    with pytest.raises(QuizScoringError):
        writing_score_to_rating(5)


def test_single_question_direct_raw_inputs(
    mcq_question: MCQSnapshot,
    cloze_question: ClozeSnapshot,
    writing_question: WritingSnapshot,
) -> None:
    """Single-question scorers accept raw string or tuple inputs."""
    res_mcq = score_mcq(mcq_question, "opt_a")
    assert res_mcq.outcome == "CORRECT"

    res_cloze = score_cloze(cloze_question, "robust")
    assert res_cloze.outcome == "CORRECT"

    res_writing = score_writing(writing_question, ("Valid sentence.", 3))
    assert res_writing.outcome == "SELF_SCORED"
    assert res_writing.self_score == 3
    assert res_writing.rating == "GOOD"


def test_score_quiz_with_mapping_answers(
    five_question_snapshot: list[MCQSnapshot | ClozeSnapshot | WritingSnapshot],
) -> None:
    """score_quiz accepts answers as a Mapping[str, AnswerInput]."""
    answers_map = {
        "q_a": AnswerInput("q_a", "opt_1"),
        "q_b": AnswerInput("q_b", "opt_2"),
        "q_c": AnswerInput("q_c", "target_word_a"),
        "q_d": AnswerInput("q_d", "target_word_c"),
        "q_e": AnswerInput("q_e", "Sentence", 4),
    }
    result = score_quiz(five_question_snapshot, answers_map)
    assert result.objective_scores.mcq.total == 2
    assert result.objective_scores.cloze.total == 2
    assert result.weakest_ratings["wf_b"] == "AGAIN"


def test_score_quiz_duplicate_answer_in_payload_raises(
    five_question_snapshot: list[MCQSnapshot | ClozeSnapshot | WritingSnapshot],
) -> None:
    """score_quiz rejects duplicate answers for the same question ID."""
    answers = [
        AnswerInput("q_a", "opt_1"),
        AnswerInput("q_a", "opt_2"),
        AnswerInput("q_e", "Sentence", 3),
    ]
    with pytest.raises(QuizScoringError) as exc_info:
        score_quiz(five_question_snapshot, answers)
    assert "duplicate" in str(exc_info.value).lower()


def test_score_quiz_unsupported_question_type_raises() -> None:
    """score_quiz rejects unsupported question snapshot objects."""

    @dataclass(frozen=True)
    class FakeQuestion:
        id: str = "q_fake"
        word_form_id: str = "wf_fake"
        type: str = "UNKNOWN"

    with pytest.raises(QuizScoringError) as exc_info:
        score_quiz(cast(list[MCQSnapshot], [FakeQuestion()]), [AnswerInput("q_fake", "ans")])
    assert "unsupported" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# 7. Answer Ownership and Question ID Validation Tests (P1 Remediation)
# ---------------------------------------------------------------------------


def test_score_mcq_rejects_foreign_question_id(mcq_question: MCQSnapshot) -> None:
    """MCQ scorer requires answer.question_id == question.id for AnswerInput."""
    # Valid answer text with foreign question_id
    with pytest.raises(QuizScoringError) as exc_info:
        score_mcq(mcq_question, AnswerInput(question_id="q_other", answer="opt_a"))
    assert (
        "question_id" in str(exc_info.value).lower() or "question id" in str(exc_info.value).lower()
    )
    assert "q_other" in str(exc_info.value)

    # Blank answer text with foreign question_id
    with pytest.raises(QuizScoringError) as exc_info:
        score_mcq(mcq_question, AnswerInput(question_id="q_other", answer=""))
    assert (
        "question_id" in str(exc_info.value).lower() or "question id" in str(exc_info.value).lower()
    )

    # None answer text with foreign question_id
    with pytest.raises(QuizScoringError) as exc_info:
        score_mcq(mcq_question, AnswerInput(question_id="q_other", answer=None))
    assert (
        "question_id" in str(exc_info.value).lower() or "question id" in str(exc_info.value).lower()
    )


def test_score_cloze_rejects_foreign_question_id(cloze_question: ClozeSnapshot) -> None:
    """Cloze scorer requires answer.question_id == question.id for AnswerInput."""
    # Valid answer text with foreign question_id
    with pytest.raises(QuizScoringError) as exc_info:
        score_cloze(cloze_question, AnswerInput(question_id="q_other", answer="robust"))
    assert (
        "question_id" in str(exc_info.value).lower() or "question id" in str(exc_info.value).lower()
    )
    assert "q_other" in str(exc_info.value)

    # Blank answer text with foreign question_id
    with pytest.raises(QuizScoringError) as exc_info:
        score_cloze(cloze_question, AnswerInput(question_id="q_other", answer=""))
    assert (
        "question_id" in str(exc_info.value).lower() or "question id" in str(exc_info.value).lower()
    )

    # Whitespace answer text with foreign question_id
    with pytest.raises(QuizScoringError) as exc_info:
        score_cloze(cloze_question, AnswerInput(question_id="q_other", answer="   "))
    assert (
        "question_id" in str(exc_info.value).lower() or "question id" in str(exc_info.value).lower()
    )

    # None answer text with foreign question_id
    with pytest.raises(QuizScoringError) as exc_info:
        score_cloze(cloze_question, AnswerInput(question_id="q_other", answer=None))
    assert (
        "question_id" in str(exc_info.value).lower() or "question id" in str(exc_info.value).lower()
    )


def test_score_writing_rejects_foreign_question_id(writing_question: WritingSnapshot) -> None:
    """Writing scorer requires answer.question_id == question.id for AnswerInput."""
    # Valid text and valid score with foreign question_id
    with pytest.raises(QuizScoringError) as exc_info:
        score_writing(
            writing_question,
            AnswerInput(question_id="q_other", answer="Valid sentence.", self_score=4),
        )
    assert (
        "question_id" in str(exc_info.value).lower() or "question id" in str(exc_info.value).lower()
    )
    assert "q_other" in str(exc_info.value)

    # Blank text with explicit score 0 and foreign question_id
    with pytest.raises(QuizScoringError) as exc_info:
        score_writing(
            writing_question,
            AnswerInput(question_id="q_other", answer="", self_score=0),
        )
    assert (
        "question_id" in str(exc_info.value).lower() or "question id" in str(exc_info.value).lower()
    )

    # None text with explicit score 0 and foreign question_id
    with pytest.raises(QuizScoringError) as exc_info:
        score_writing(
            writing_question,
            AnswerInput(question_id="q_other", answer=None, self_score=0),
        )
    assert (
        "question_id" in str(exc_info.value).lower() or "question id" in str(exc_info.value).lower()
    )

    # Pending null self_score with foreign question_id must raise identity QuizScoringError
    with pytest.raises(QuizScoringError) as exc_info:
        score_writing(
            writing_question,
            AnswerInput(question_id="q_other", answer="Sentence.", self_score=None),
        )
    assert (
        "question_id" in str(exc_info.value).lower() or "question id" in str(exc_info.value).lower()
    )
    assert "q_other" in str(exc_info.value)


@pytest.fixture
def two_writing_questions_snapshot() -> list[WritingSnapshot]:
    """Two writing questions on distinct synthetic word forms."""
    return [
        WritingSnapshot(
            id="q_w1",
            word_form_id="wf_alpha",
            prompt_en="Write about alpha.",
            target_lemma="alpha",
        ),
        WritingSnapshot(
            id="q_w2",
            word_form_id="wf_beta",
            prompt_en="Write about beta.",
            target_lemma="beta",
        ),
    ]


def test_score_quiz_rejects_foreign_embedded_id_under_known_key(
    two_writing_questions_snapshot: list[WritingSnapshot],
) -> None:
    """Mapping with valid snapshot key but foreign AnswerInput.question_id must fail."""
    mapping = {
        "q_w1": AnswerInput(question_id="q_foreign", answer="Sentence 1", self_score=1),
        "q_w2": AnswerInput(question_id="q_w2", answer="Sentence 2", self_score=4),
    }
    with pytest.raises(QuizScoringError) as exc_info:
        score_quiz(two_writing_questions_snapshot, mapping)
    msg = str(exc_info.value).lower()
    assert "question_id" in msg or "question id" in msg or "key" in msg
    assert "q_w1" in str(exc_info.value)


def test_score_quiz_rejects_swapped_answers_in_mapping(
    two_writing_questions_snapshot: list[WritingSnapshot],
) -> None:
    """Mapping with swapped AnswerInputs between valid questions must be rejected.

    Prevents assigning q_w2's EASY (score 4) to q_w1's word form (wf_alpha)
    and q_w1's AGAIN (score 1) to q_w2's word form (wf_beta).
    """
    ans_w1 = AnswerInput(question_id="q_w1", answer="Sentence alpha", self_score=1)
    ans_w2 = AnswerInput(question_id="q_w2", answer="Sentence beta", self_score=4)

    # Swapped: q_w1 key maps to ans_w2, q_w2 key maps to ans_w1
    swapped_mapping = {
        "q_w1": ans_w2,
        "q_w2": ans_w1,
    }
    with pytest.raises(QuizScoringError) as exc_info:
        score_quiz(two_writing_questions_snapshot, swapped_mapping)
    msg = str(exc_info.value).lower()
    assert "question_id" in msg or "question id" in msg or "key" in msg


def test_score_quiz_rejects_reused_answer_under_multiple_keys(
    two_writing_questions_snapshot: list[WritingSnapshot],
) -> None:
    """One AnswerInput reused under two different valid keys must fail ownership check."""
    ans_w2 = AnswerInput(question_id="q_w2", answer="Sentence beta", self_score=4)
    reused_mapping = {
        "q_w1": ans_w2,  # Discrepancy: key q_w1 != question_id q_w2
        "q_w2": ans_w2,
    }
    with pytest.raises(QuizScoringError) as exc_info:
        score_quiz(two_writing_questions_snapshot, reused_mapping)
    msg = str(exc_info.value).lower()
    assert "question_id" in msg or "question id" in msg or "key" in msg
    assert "q_w1" in str(exc_info.value)


def test_score_quiz_mapping_versus_sequence_equivalence(
    five_question_snapshot: list[MCQSnapshot | ClozeSnapshot | WritingSnapshot],
) -> None:
    """Correctly associated inputs preserve each question's self-score and yield
    identical results.
    """
    answers_seq = [
        AnswerInput(question_id="q_a", answer="opt_1"),
        AnswerInput(question_id="q_b", answer="opt_2"),
        AnswerInput(question_id="q_c", answer="wrong_word"),
        AnswerInput(question_id="q_d", answer="target_word_c"),
        AnswerInput(question_id="q_e", answer="My sentence.", self_score=3),
    ]
    answers_map = {ans.question_id: ans for ans in answers_seq}

    res_seq = score_quiz(five_question_snapshot, answers_seq)
    res_map = score_quiz(five_question_snapshot, answers_map)

    assert res_map == res_seq
    assert res_map.objective_scores == res_seq.objective_scores
    assert res_map.question_results == res_seq.question_results
    assert res_map.writing_self_scores == res_seq.writing_self_scores
    assert res_map.weakest_ratings == res_seq.weakest_ratings
    # Ensure self_score is preserved
    assert res_map.writing_self_scores[0].self_score == 3
    assert res_map.writing_self_scores[0].question_id == "q_e"

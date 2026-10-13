# UXR-01 R1 evidence delta — Direction B v1.2

**TASK_ID:** UXR-01  
**Evidence reviewed:** UXR-00-R1 Phase B, `CURRENT_APP_RENDER_WITH_SYNTHETIC_FIXTURE`  
**Decision:** retain all original B v1.2 images unchanged; no UXR-01 visual correction required

## Baseline and provenance

The original [UXR-01 evidence ledger](UXR-01-EVIDENCE-LEDGER.md) had 21 canonical UXR-00 captures. G7 had no rendered current-app result or feedback; G9 had first-run, but no populated or mixed-data current-app capture. UXR-01 produced 27 full-resolution synthetic design mockups for each of A and B, with IDs in the [visual gallery](UXR-01-VISUAL-GALLERY.md) and hashes in `assets/image-manifest.json`. The original galleries, comparison and source copies remain historical evidence.

The read-only R1 source paths are `C:\Users\khanh\projects\vocabularies-smoke\artifacts\uxr00\r1\UXR-00-R1-REPORT.md`, `C:\Users\khanh\projects\vocabularies-smoke\artifacts\uxr00\r1\R1-COVERAGE-DELTA.md` and `C:\Users\khanh\projects\vocabularies-smoke\artifacts\uxr00\r1\R1-SCREENSHOT-INVENTORY.md` in the sibling worktree. These are local workspace references, not repository-contained or GitHub-hosted evidence. The three R1 captures used intercepted synthetic GET fixtures in the current React UI. They prove the pictured rendering, not real learner history, a backend write, dashboard aggregation, submission persistence or provider output. UXR-00 remains `PARTIAL_WITH_EXPLICIT_BLOCKERS`.

## G7 — submitted result and validated feedback

| R1 current-app image | B v1.2 image IDs | Finding | Classification |
|---|---|---|---|
| `C:\Users\khanh\projects\vocabularies-smoke\artifacts\uxr00\r1\screenshots\R1-G7-01-submitted-quiz-result.png` | [B21 desktop](assets/b/results-writing-feedback-source-backed-1440x900.png), [B24 mobile](assets/b/results-writing-feedback-mobile-390x844.png) | Both display `SUBMITTED`, separate MCQ/Cloze objective results, a learner Writing self-score and a Review/SRS handoff. B's sample has MCQ 1/2 attempted at 50%, Cloze 1/1 attempted at 100% with one blank of two total, and Writing 3/4. R1 uses the same score pattern, showing CORRECT, INCORRECT and BLANK in individual items. B puts item detail behind a disclosure and states that blank differs from wrong; the exact expanded visual treatment remains for UXR-07. | `MATCHES_DESIGN` for result semantics and action hierarchy; `VISUAL_DIFFERENCE_ACCEPTABLE` for the denser ledger/disclosure |
| `C:\Users\khanh\projects\vocabularies-smoke\artifacts\uxr00\r1\screenshots\R1-G7-02-validated-writing-feedback.png` | B21, B24 | R1 shows historical `VALIDATED` feedback with a summary and three criteria, bound in the synthetic fixture to answerRevision 2. B21/B24 deliberately depict the **not-requested** optional-AI state and a collapsed history affordance. They do not claim the validated state is absent or replace the 3/4 self-score with an AI grade. A later UXR-07 frame must show the actual validated/history content and revision context. | `VISUAL_DIFFERENCE_ACCEPTABLE` for different scenario; `SOURCE_BEHAVIOR_NOT_VERIFIED` for provider generation and persistence |

R1's result is terminal. It does not capture an `IN_PROGRESS` result transition, unknown submission recovery, keyboard operation, or the expanded B disclosure. The B concept states the terminal distinction; the current transition remains `BLOCKED_MISSING_EVIDENCE`. R1 shows SRS handoff after submission, but its GET interception did not prove an atomic backend update. No G7 image replacement is justified by this delta.

## G9 — populated Dashboard

| R1 current-app image | B v1.2 image IDs | Finding | Classification |
|---|---|---|---|
| `C:\Users\khanh\projects\vocabularies-smoke\artifacts\uxr00\r1\screenshots\R1-G9-01-populated-dashboard.png` | [B03 desktop](assets/b/dashboard-populated-desktop-1440x900.png), [B04 mobile](assets/b/dashboard-populated-mobile-390x844.png), [B13 fold](assets/b/dashboard-populated-fold-1366x768.png), [B17 dark](assets/b/dashboard-populated-dark-desktop-1440x900.png) | R1 renders 12 due, 7-day streak, 24 GOOD ratings, MCQ 75%, Cloze 67% rounded from 66.67%, and Writing 3.3/4 displayed from 3.25. B uses deliberately different synthetic example values (12 due, 6-day streak, 38 GOOD ratings, MCQ 80%, Cloze 75%, Writing 3/4); they are not a transcription of R1. B keeps flashcard rating ordinal, MCQ/Cloze accuracy separate, Writing learner self-score separate, and a single due Review primary action. | `MATCHES_DESIGN` for metric categories and action semantics; `VISUAL_DIFFERENCE_ACCEPTABLE` for illustrative values/layout |

R1 and B use aggregate source fields from `DashboardSummary`: `dueCards`, `streak.currentDays`, `flashcardSelfRating`, `objectiveAccuracy.mcq/cloze`, and `writingSelfScore`. Neither B's populated image nor R1 proves backend aggregation from durable source records. B's first-run [B01](assets/b/dashboard-first-run-desktop-1440x900.png)/[B02](assets/b/dashboard-first-run-mobile-390x844.png) separately show real due zero, unknown streak and no-attempt null; R1 does not exercise mixed zero/null states. The source contract retains null for no attempted objective questions or unknown streak, while measured zero is a real numeric outcome. Mixed/null rendering remains `BLOCKED_MISSING_EVIDENCE` for current-app coverage. No daily activity, trend, future due schedule, heatmap, goal percentage or proficiency series is supplied by the current aggregate API.

## Correction decision and remaining limits

No material conflict with authoritative behavior was found in the six affected B image IDs **B03, B04, B13, B17, B21 and B24**. `DESIGN_CORRECTION_REQUIRED`: **none**. The original 27 B v1.2 and 27 A v1.2 images are retained without regeneration or replacement. B's validated-feedback and expanded answer-detail visual states are future UXR-07 work, not silent assumptions that those states are fully designed. R1 does not close original UXR-00 gaps around keyboard/a11y, Save/conflict, UNKNOWN reconciliation, real AI/provider output, backend writes, mixed/null Dashboard, or full nine-group verification.

The owner-selected B direction can be retained unchanged for UXR-02 preparation. D1/D2/D3/D4/D6/D8/D9 are now explicitly approved in [the final decision sheet](UXR-01-DESIGN-DECISION.md); D5 remains deferred to UXR-06 and D7 remains future/unapproved. This approval is not implementation or detailed component/runtime validation. Publication remains blocked by the mandatory pinned secret scan.

# UXR-07 — Quiz Results & Writing Feedback Design

**Track:** English Web final major UI/UX redesign; **design-only** research task, not canonical app T001–T090.  
**Group/routes:** G7 — `/quiz/:attemptId/result`; result history/FeedbackPanel within the existing submitted-attempt route.  
**Status:** `PREPARED / NOT STARTED / BLOCKED_BY_UXR_02A_OWNER_VISUAL_SIGNOFF`.  
**Owner authorization (2026-10-12):** prepare this task Markdown and update the roadmap/Draft PR #26 only. **Not** authorization to execute redesign, render gallery, invoke local designer workers, change app code, install shadcn, run test/audit, mark DONE or merge.  
**Hard chain for real execution:** verified UXR-00 final evidence → UXR-01 owner-selected actual image direction → UXR-02 owner-approved AppShell images → UXR-02A owner-approved density images → separately approved UXR-07 image design execution → distinct owner approval of G7 rendered version → UXR-10 → UXR-11 final cross-product sign-off.  
**Parallelism:** UXR-03–09 feature designs can execute in separate owned directories only after real UXR-02A approval, subject to their own authorizations. UXR-06 owns Builder/Runner/draft/submit; UXR-07 owns **terminal result and optional feedback display**; UXR-08 owns policy/consent dialog states.  
**GitHub:** `khanhpn308/english_web`, `design/ui-ux-research-20261012`, [Draft PR #26](https://github.com/khanhpn308/english_web/pull/26) remains OPEN/DRAFT/UNMERGED.  
**Binding protocol:** [Owner-visible image approval, already-installed Impeccable and official shadcn/ui](../docs/design/uxr-visual-approval-impeccable-protocol-2026-10-12.md).  
**Stop after preparation:** get **explicit owner permission** before creating task UXR-08 — Status, Consent & Error States Design.

## 1. Goal and strictly delimited scope

Create a compact, educational, evidence-accurate and **owner-visually-approved** result-reading journey covering:

1. **Entry and terminality:** distinguish attempt loading, local API error, `QUIZ_RESTORE_REQUIRED`, `IN_PROGRESS/result=null` (“continue runner”) and authoritative `SUBMITTED/result`. Never display a fabricated failed/zero-score result before terminal commit.
2. **Separate result summaries:** MCQ and Cloze objective `total / attempted / correct / accuracy` with exact `null` handling; Writing `selfScore` 0–4 clearly **learner-assigned**, not equivalent to objective percentage nor AI score.
3. **Detailed answer review:** MCQ chosen vs correct option, Cloze saved answer vs accepted alternatives, BLANK distinct from INCORRECT, Vietnamese explanations unlocked **only after submission**, long bilingual content and keyboard access.
4. **SRS outcome:** display server-confirmed grouped per-word review handoffs (`APPLIED` vs `SKIPPED_INACTIVE`) and rating semantics without pretending a skipped/inactive source was rescheduled or applying a second review event.
5. **Optional AI Writing Feedback:** per-submitted Writing answer and exact answer revision; explicit AI consent, provider route/timeout states, REQUESTED/VALIDATED/FAILED, unknown outcome reconciliation, retry-of-failed-operation vs replay-same-unknown-intent, source-linked criterion comments and readable paginated feedback history.
6. **Truthful cross-product boundaries:** results work via local API without external AI; **requesting new comments** is a separate optional bridge/data-sharing operation. The user can read local result and self-score without granting AI consent.

Success is a complete **full-resolution UI image gallery** the owner inspects and explicitly signs off, after approved shell/density phases. Good Markdown/wireframes alone cannot satisfy G7 design approval. No new frontend functionality or generated API behavior is authorized by this specification.

## 2. Actual repository evidence and unresolved visual baseline

| Source | Source-confirmed G7 behavior and design constraint |
|---|---|
| `frontend/src/features/quiz/QuizResult.tsx` | Reads `GET /api/v1/quiz-attempts/{attemptId}` with `cache=no-store`, validates attempt ID, handles loading and failed read, `QUIZ_RESTORE_REQUIRED`, `IN_PROGRESS` (shows savedAnswerCount + Continue Runner), and `SUBMITTED` with stored `QuizResult`. Missing result on submitted attempt is **error/recovery**, not 0%. |
| `QuizResult.tsx` | Objective MCQ/Cloze score cards use `total,attempted,correct,accuracy`. Current UI shows dash for `accuracy=null`, but its progressbar uses 0 as aria-valuenow fallback; require a proposed **not-assessed** design state, not fabricated accuracy=0. This is a **source-based semantic design review**, not an observed runtime accessibility defect. |
| `QuizResult.tsx` | Per-question `CORRECT/INCORRECT/BLANK` result; MCQ shows choice + correct option; Cloze shows submitted answer, accepted alternatives, and Vietnamese explanation; Writing shows saved sentence, learner `selfScore/4`, rubric descriptor and mapped system SRS rating. FeedbackPanel shown for a saved Writing answer with valid revision and non-null score. |
| `QuizResult.tsx` | `reviewHandoffs` list displays per-word ratings and `APPLIED` vs inactive/skipped status; raw `wordFormId` visible in current source. Source changes after snapshot/submit should not change stored historical question/result. Backend owns handoff and due schedule. |
| `frontend/src/features/quiz/FeedbackPanel.tsx` | Feedback records `feedbackId,attemptId,questionId,answerRevision,status REQUESTED/VALIDATED/FAILED,summaryVi,criteria,provider,model,promptVersion,errorCategory,operationId,retryOfOperationId,createdAt`. Shows latest and cursor-paginated history (pageSize 10) from `/api/v1/quiz-questions/{questionId}/feedback`. |
| `FeedbackPanel.tsx` | Request body carries `rubricVersion + answerRevision` (optional `retryOfOperationId`) and `Idempotency-Key`; uses shared `AiConsentGate`, 30-second request deadline and lock. Existing UI keeps `unknownIntent = {key,body}` in **component memory**, offers history re-read and replay of **same original key/body**. **Do not claim it persists after browser tab closure/restart** or that history-only re-read can prove mutation identity. |
| `FeedbackPanel.tsx` | `VALIDATED`: summary + criterion comments for `TARGET_WORD_USAGE / GRAMMAR / CLARITY`; `REQUESTED`: still processing; `FAILED`: categorized failure plus explicit new retry linked to prior operation. AI comment is optional and never changes selfScore/SRS. Blank saved answer disables new feedback request. |
| `docs/adr/0005-contract-clarifications.md` §C013-03/06/07 | `accuracy=correct/attempted`, **null when attempted=0**; objective blank `BLANK` vs incorrect, score 0–4 mapping to SRS, weakest-result grouping by word form, inactive handoff skip. Objective answer key/accepted Cloze answers/explanationVi appear only after valid terminal submission. Submit/replay creates no second scoring or SRS update. |
| `docs/ui-architecture.md` §J5/J7 | Objective scores, Writing self-assessment, optional AI criteria, history and SRS must be **distinct**; AI request is separately opt-in and consent-gated; consent grant **never auto-sends** the Writing answer. Result read and submit are local; AI provider loss cannot erase result. |
| `docs/design/ui-visual-audit-2026-10-12-batch2.md` | **G7 has NO DIRECT owner screenshot** of result/feedback/history/failed-retry. All current G7 layout observations are **SOURCE_CONFIRMED / NOT_VISUALLY_VERIFIED** until UXR-00/owner actually supplies captures. Never manufacture “current app before” screenshots. |

**API-vs-component caveat:** existing source shows controls and intent handling, not proof of live runtime outcomes, persisted current provider state or a complete end-to-end error-free path. The future design must preserve actual backend contracts and mark UI differences as proposals; source code alone does not certify a verified bug or fix.

## 3. Execution readiness gate, evidence confidence and decisions

The following are **requirements for later separately authorized local design execution**, not performed by this documentation commit:
- Link UXR-00 final baseline screenshots/evidence confidence, the actual owner-approved UXR-01 selected image direction, UXR-02 AppShell responsive/theme version, and UXR-02A compact layout/density decision.
- Obtain **separate owner approval to execute UXR-07** and designate an integration lead and independent Result vs Feedback designers with non-overlapping assets. Approval to prepare this file does not grant any design/code runtime actions.
- Coordinator and each local design worker **actually discover, load and run** their installed Impeccable skill as detailed in §8, log version and image effects. Do not claim a Windows skill was invoked through GitHub connector.
- Establish UXR-06 **presentation seam**: only authentic `SUBMITTED + result` enters scored result UI; `IN_PROGRESS` returns to Runner, with no preterminal key disclosure. UXR-07 may be designed in parallel but cannot override UXR-06 mutation/terminal semantics.
- Align feedback request consent layout with shared UXR-08 contract, even if UXR-08 feature images are not yet prepared. Policy changes, server-authoritative consent and pending/revoke reconciliation remain UXR-08 owned.
- Record proposed A/B composition decisions and a visible source ledger `claim | source | verified capture? | mockup/fixture label | user risk` before asking owner to approve any result design version.

## 4. Result-entry states and score hierarchy (future design work)

Produce a state matrix `route | attempt.status | result | available source fields | primary/secondary action | focus/aria | warning or caveat | screenshot ID`:

1. **Loading** attempt read: no fake answer cards or default 0%, provide valid skeleton and responsive header; distinguish delayed local API from AI outage.
2. **Error** `QUIZ_RESTORE_REQUIRED`, `SESSION_*`, local service unreachable, mismatched/corrupt attempt: actionable re-read/launcher help, preserve historical data claims, never claim no attempt exists simply because GET failed.
3. **IN_PROGRESS, result=null**: explicit “Bài chưa nộp”, saved draft count (`savedAnswerCount` server field), **Tiếp tục làm bài** route and no objective answer key/accuracy/terminal explanation in DOM, image or tooltip.
4. **SUBMITTED with missing/inconsistent result**: recovery/restore warning and retry read, **not** an empty successful scorecard or “0 điểm.”
5. **SUBMITTED with valid result**: date/time and revision from backend, one compact high-priority result summary, next useful CTA (e.g. review weak questions), return to Dashboard/new quiz optional and subordinate. Do not invent “final grade” across disparate assessment types.

**Objective metrics:** For each MCQ/Cloze independently show `total` (assigned questions), `attempted` (answered nonblank), `correct` and `accuracy = correct/attempted`. When `attempted=0`, show **“Chưa có lượt trả lời để tính độ chính xác”** / dash, never 0%; 0 correct among >0 attempted is genuinely 0%. An optional official Progress component is used only if an actual, non-null denominator and accessible label are present. Separately distinguish completion (`attempted/total`) from correctness (`correct/attempted`).

**Writing metrics:** Show saved user sentence, learner's explicitly selected `0..4` self-score, Vietnamese rubric meaning, and mapped SRS rating. This is not AI grade, no Writing “accuracy percentage,” and cannot be silently averaged with objective MCQ/Cloze values. If authoritative result contradicts the expected submitted constraint (`selfScore=null`), label as validation/recovery issue instead of inventing a zero.

**Design split/hierarchy:** Compact header with answer status first, then differentiated MCQ and Cloze metrics, then a navigable weak/blank question review and Writing panel; SRS handoff is secondary with operator identifiers behind accessible disclosure. Avoid one enormous flat stack of equivalent Card borders, duplicate summary badges, or long error metadata above the learner's useful interpretation.

## 5. Objective answer review: teaching value and key secrecy

- Group per-question detail by type or show one scannable chronological list, comparing actual question `promptEn`, **user's recorded answer**, correct option/accepted alternatives and explanations. Owner can choose an A/B disclosure/accordion composition; do not alter question order or use unsupported predicted topic groupings.
- MCQ `CORRECT`: mark chosen correct answer with text + icon/color; `INCORRECT`: show chosen distractor and actual correct option separately; `BLANK`: mark **Chưa trả lời**, with correct option available **only after SUBMITTED**. Do not call BLANK an answered wrong question in completion statistics.
- Cloze: show exact user-saved input (or “Để trống”), accepted answer alternatives and Vietnamese explanation. Preserve normalized server determination; UI must not rescore client-side, invent extra acceptable spellings, or alter historical result if source word changes.
- Objective explanation `explanationVi` and hidden `correctOptionId/acceptedAnswers` must not be visible **in any IN_PROGRESS design variant**, including synthetic example captions/interaction mockups marked as pre-submit. A CSS-hidden answer key is not a security boundary; use terminal source results only.
- Blank/incorrect/correct status must use non-color-only labels, proper language tags/ARIA, robust line wrap and no cramped three-column answer layout on 320px. Show long English prompts, long Vietnamese explanations, long Cloze alternatives and zero-attempt case.
- The result is **read-only**. An “Edit submitted answer” or post-submit selfScore change is out of contract; next action is new attempt, review, or non-mutating result navigation.

## 6. SRS handoff and accurate outcomes

- Show `reviewHandoffs` from the stored terminal `QuizResult`, not an asynchronously invented progress animation. `APPLIED` means review state was actually updated by the backend; `SKIPPED_INACTIVE` means absent/invalid source/card blocked rescheduling, while **past attempt result and learning history remain readable**.
- SRS derived rating is grouped once per active word form under weakest-result order `AGAIN < HARD < GOOD < EASY`; MCQ correct → GOOD, incorrect/blank → AGAIN; Writing rubric `0/1→AGAIN, 2→HARD, 3→GOOD, 4→EASY`. Never render a mean rating that would conceal a weaker result.
- Make skip reason visible and accessible, without suggesting the user can manually force reapply from the result page. Present raw wordFormId/operation detail only when needed for support; **no new implicit review action**.
- Calendar next due dates are server-owned (Asia/Bangkok midnight calculation) and are not assumed merely from a displayed rating. No additional SRS event may be triggered by visiting or refreshing this result route, feedback history, or changing a visual tab.
- Zero handoffs: clarify “Không có cập nhật SRS áp dụng được từ bài này” only if the backend list is empty; do not misrepresent a known skipped handoff as no attempted learning.

## 7. Optional Writing AI Feedback, versioning, failure and history

### A. Separate AI permission and submission intent

- Feedback shown **only for submitted Writing with an actually saved Answer and meaningful `answerRevision`** under the existing component boundary. The canonical submitted sentence and `selfScore/4` remain **visible and immutable**. Blank sentence → feedback request disabled with clear reason; a valid blank Writing with explicit zero is still a completed result, not eligible for meaningful AI critique.
- **Feedback is optional**; initial state `Không yêu cầu nhận xét` must not look like missing terminal score. Initiation uses an explicit button and the current server-authoritative AI consent gate; any grant/policy-change dialog is UXR-08-owned. **Granting consent does not trigger feedback automatically.** Only a subsequent explicit request with current permission can dispatch.
- `FeedbackRequest` keeps `rubricVersion`, exact saved **`answerRevision`** and stable `Idempotency-Key`; optional `retryOfOperationId` marks **new request after confirmed FAILED**. Never run AI request against unsaved local text, stale answer revision, or silently substitute the learner's self-score with an AI score.
- Access to local result and historical validated feedback is conceptually separate from **starting a new external request**; treat availability/errors of local API and remote AI bridge distinctly. No provider token, raw sensitive payload or speculative cloud availability in mockups.

### B. Status presentation, unknown reconciliation and history

| Actual status / circumstance | Visible learner-first behavior | Request safety |
|---|---|---|
| Not requested, nonempty saved answer | Optional “Yêu cầu AI nhận xét”, short disclosure that comments do not alter selfScore | Requires current explicit consent and click |
| `REQUESTED` | “Đang xử lý”, submission time, no fake finished comments | Do not offer duplicate new request |
| `VALIDATED` | Separate summaryVi, `TARGET_WORD_USAGE`, `GRAMMAR`, `CLARITY` Vietnamese criteria, version/provider disclosure | Treat as commentary, not score change |
| `FAILED` with known operation ID | Categorized failure, safe **explicit new retry** referencing `retryOfOperationId` | New request is permitted only after proven failure + current consent |
| Timeout, lost response, `IDEMPOTENCY_IN_FLIGHT`, `MutationUnknownError` | “Chưa xác định”, preserved known original key/body (to extent source actually provides), “Kiểm tra kết quả”, optional explicit same-key continuation | No new key/altered payload until original settled; history GET alone **cannot prove** exact lost-operation identity |
| Bridge/network unavailable or consent withdrawn | Show bridge/permission unavailability; keep displayed local objective/Writing/SRS result fully accessible | Never require AI grant to display local results |
| History pagination/read failure | Keep acknowledged page, `Tải thêm lịch sử` only if backend hasMore, distinguish missing from loading/error | No invented total; no hidden background resubmission |

- History is linked to **questionId + attemptId**, retrieved in pages of 10 with `nextCursor/hasMore`; show timestamp, feedback status and associated **answerRevision** where available. A single first-page count is **not** all-time history; preserve existing records if next-page GET fails. An accessible Collapsible/Accordion is preferable to ten duplicated full-length commentary cards.
- New feedback attempt after known `FAILED` must be visually distinguished from continuing an **uncertain original** with the same key and same body. Distinguish `REQUESTED` from unknown transport (can be committed but response lost).
- **Important evidence limit:** current `FeedbackPanel.tsx` retains `unknownIntent` in component state, not established durable storage; **do not promise same-key recovery after tab closure**. Mark cross-refresh continuity as an unresolved **implementation/contract risk** requiring separate authorization, not an excuse to add persistence now.
- AI comments do not overwrite submitted Writing text, user's 0–4 score, objective keys, SRS rating or existing historical attempt. No autogeneration on visiting result route, opening history or withdrawing consent.

## 8. Owner-visible image gallery and explicit visual gate (VG4)

**Required during future, separately authorized UXR-07 design execution:** create **at least 28 original, full-resolution, viewable PNG/WebP proposed UI images** — **14 named scenarios each at 1366×768 desktop and 390×844 mobile**. These represent complete visually composed screens, not just cropped illustrations, ASCII boxes, JSX or tiny contact sheet fragments. They use clearly marked `DESIGN_MOCKUP / SYNTHETIC` answer fixtures; **G7 has NO DIRECT CURRENT OWNER SCREENSHOT**.

| Frame IDs | Paired scenario | Owner must be able to see |
|---|---|---|
| RS01–RS02 | Result route `LOADING` | Compact status, not fictitious result data |
| RS03–RS04 | `IN_PROGRESS` attempt (result null) | No grade, resume Runner, savedAnswerCount |
| RS05–RS06 | `SUBMITTED` comprehensive result | Final header, separate MCQ/Cloze/learner Writing summary |
| RS07–RS08 | Objective `accuracy=null` (zero attempted) | “Chưa tính được độ chính xác” vs actual 0% distinction |
| RS09–RS10 | MCQ detailed INCORRECT/CORRECT | User choice, correct choice and Vietnamese explanation **post-submit** |
| RS11–RS12 | Cloze BLANK/INCORRECT detail | Stored answer vs accepted alternatives and statuses |
| RS13–RS14 | Writing self-score and rubric | Submitted text, explicit 0–4 learner self-score, mapped SRS rating |
| RS15–RS16 | SRS `APPLIED` vs `SKIPPED_INACTIVE` | Correctly separated real update and skipped source |
| FB01–FB02 | Feedback not requested + consent-needed entry | Optional only, no auto-request on grant |
| FB03–FB04 | Feedback `REQUESTED` / still processing | No fabricated completed AI answer |
| FB05–FB06 | Feedback `VALIDATED` | Vietnamese summary + three criteria, separate score |
| FB07–FB08 | Feedback `FAILED`, retry intent | Error category and explicit new retry linked to failed operation |
| FB09–FB10 | Feedback `UNKNOWN` / reconciliation | Original key/body lock, same-intent continuation, history alone inconclusive |
| FB11–FB12 | History with several versions/pagination | Versioned feedback records, status/date, history expansion/load more |

**Beyond the 28:** provide `320×568` stress screenshots for long Vietnamese objective explanation and long AI feedback criterion lists, `768×1024` tablet, `1024×768` intermediate and `1440×900` full approved AppShell; a same-state **light/dark** comparison of complete screens; and **two materially different layout compositions** of objective-detail disclosure/Feedback history (at least 1 desktop + 1 mobile alternative) within the **already owner-selected UXR-01 brand direction**. Document 200%-zoom design reflow, touch targets, keyboard focus and reduced-motion. Include at least one explicit local API/QUIZ_RESTORE_REQUIRED error storyboard beyond primary 28 frames.

**Before/proposed rule:** no owner-provided G7 screenshot is presently verified. Present only future proposed imagery marked `SOURCE_ONLY / NOT_VERIFIED CURRENT APP`. Do not invent a “before” or claim to have captured current G7 application. If UXR-00 later supplies genuine screenshot bytes, add authentic provenance and before/proposed comparison then.

**Gallery deliverable:** a readable contact sheet **plus individual full-resolution original image links**, persistent under `docs/design/uxr-07/assets/` (or owner-approved storage). Asset metadata `task | screen | case/state | frame ID | exact CSS viewport | theme | A/B | DESIGN_MOCKUP/CURRENT_APP_CAPTURE | SYNTHETIC flag | version/date | path/link`. Technical report sans images **blocks owner approval**.

**Owner decision:** `version | image URLs | candidate selected | approved summary/detail/feedback states | feedback | APPROVE/REQUEST_CHANGES/REJECT/PENDING | owner response/date`. **Only explicit owner viewing and saying APPROVE** marks this feature's image gate met. Revised images require new version and renewed approval. UXR-11 still requires nine-group final gallery sign-off.

## 9. Mandatory use of already-installed Impeccable — real per-worker proof

Owner reports [Impeccable](https://github.com/pbakaus/impeccable) is **already installed locally on Windows**. Do **not** install, reinstall, update, vendor or copy it for this project.

During **later local, owner-authorized UXR-07 design execution**:
1. **Coordinator AND each distinct Result, Objective-detail, Feedback, accessibility/critique image worker** independently locate their installed skill directory in their actual Codex/agent harness, read the installed `SKILL.md` and relevant command references. Upstream GitHub README and forwarded coordinator summary do not count.
2. Run `<skill-base>/scripts/impeccable context` **once per agent session from English Web project cwd** (Windows launcher `<skill-base>\scripts\impeccable.cmd context` if applicable); record actual path, version if available, timestamp and **result**. Never invent invocation success or repeatedly run context for every frame.
3. Use installed guidance as appropriate: `shape`/ `layout`/ `distill` for separating result metrics; `clarify` for accuracy null/blank wording, `harden` for feedback UNKNOWN and consent, `adapt` for 320px/long Vietnamese explanations, independent `critique` for hierarchy/accessibility. Follow real installed verb references and correct limitations, not a mandatory shotgun call to every verb.
4. Per-worker audit row in `UXR-07-IMPECCABLE-EVIDENCE.md`: `role+agent/session | real installed skill path/version | context call time/result | command/reference | observed design issue | changed mockup decision | exact image ID`. Coordinator logs its own call and reconciles independent worker feedback.
5. If skill unavailable or invocation fails, report `IMPECCABLE_NOT_ACCESSIBLE` with actual error/path and block final G7 sign-off until resolved by owner. No reinstall, no silent skipping, no claims of successful local use from GitHub edits.
6. Skill may influence image composition only; it cannot override consent, scoring, visibility of objective keys, source truth, offline API, owner-approved design foundation or official component policy.

**This Markdown preparation has NOT invoked the owner's locally installed Impeccable skill.** Its actual use is a future execution requirement, not a claim about this task.

## 10. Official shadcn/ui-only component candidates and ownership

**Only default source of missing reusable UI primitives:** https://ui.shadcn.com/docs/components. Refer to [existing project strategy](../docs/design/shadcn-ui-component-strategy-2026-10-12.md), `components.json` and currently adopted `frontend/src/components/ui/{button,card,dialog}.tsx`; preserve Radix/new-york/Tailwind 4 style and no-Preflight assumptions.

Later deliver `surface/state | exact official component name and URL | ALREADY_PRESENT/OFFICIAL_PROPOSED/COMPOSITION/DEFERRED | keyboard/aria | owning designer`:

| G7 area | Official shadcn/ui candidates | Contract and safety checks |
|---|---|---|
| Terminal summary | existing **Card/Button**, official **Badge, Separator, Progress** | `accuracy=null` must be **indeterminate/not assessed** and must not use aria-valuenow=0 |
| Objective question details | **Accordion, Collapsible, Badge, Tabs** (only if useful), existing **Card** | Accessible key visibility only after SUBMITTED; no blank/incorrect conflation |
| Writing self-score | **Card, Badge, Separator, Tooltip** only for secondary rubric guidance | Learner selfScore not AI rating or inferred grade |
| Feedback statuses | **Alert, Badge, Skeleton, Collapsible**; existing **Dialog** only if real consent interaction supplied by UXR-08 | Distinguish REQUESTED/VALIDATED/FAILED/UNKNOWN and local vs AI availability |
| Feedback history | **Accordion, Collapsible, Pagination, Button, Separator** as data warrants | Cursor/hasMore truth, answer revision, keyboard focus, no fabricated total |
| SRS handoff | **Badge, Accordion, Table** only if genuine density supports | APPLIED vs SKIPPED_INACTIVE, no new review event |
| Error/restore | **Alert, Skeleton, Button**, optional **Alert Dialog** for real destructive decisions | Restore/retry labels, no invented local data loss or success |

App-level **future presentational compositions** may be `QuizTerminalSummary`, `ObjectiveMetricTile`, `QuestionResultDisclosure`, `WritingSelfAssessment`, `SrsHandoffSummary`, `FeedbackRequestStatus`, `FeedbackHistoryList`; these are *not* components installed now. No community shadcn registries, copying templates, `shadcn init --force`, `add --all`, `--overwrite`, npm install, package lock modification or changing existing Radix primitives in design prep. Later separately authorized implementation must review specific official docs/source/CLI diffs and one shared primitive owner.

## 11. Future deliverables, acceptance criteria and Definition of Done

**Design artifact root (later execution only):** `docs/design/uxr-07/`.

| Future artifact | Required content |
|---|---|
| `UXR-07-EVIDENCE-STATE-MATRIX.md` | G7 baseline confidence, attempt states, source-specific term/result/feedback status truth |
| `UXR-07-RESULT-SUMMARY-SPEC.md` | total/attempted/correct/nullable accuracy, separated Writing and completion, summary hierarchy |
| `UXR-07-QUESTION-DETAIL-SPEC.md` | MCQ/Cloze correct/incorrect/blank, hidden-key terminal boundary, Vietnamese explanations |
| `UXR-07-WRITING-SRS-SPEC.md` | learner selfScore, rubric and weakest grouped rating, APPLIED/skipped historical handoff |
| `UXR-07-FEEDBACK-CONTRACT.md` | optional AI consent, REQUESTED/VALIDATED/FAILED/UNKNOWN, retry versus replay and answerRevision |
| `UXR-07-HISTORY-RESPONSIVE-A11Y.md` | cursor history, responsive/keyboard/200%-zoom and disclosure errors |
| `UXR-07-SHADCN-MAPPING.md` | official URL, installed vs proposed, Radix compatibility and owner |
| `UXR-07-VISUAL-GALLERY.md` plus `assets/*.{png,webp}` | **≥28** primary actual composed full-resolution image files + extras, contact sheets and links |
| `UXR-07-IMPECCABLE-EVIDENCE.md` | actual coordinator + each worker installed skill context invocation/impact or genuine blocker |
| `UXR-07-OWNER-DECISION.md` | exact image/version A/B choice and owner's explicit decision |
| `UXR-07-HANDOFF.md` | frozen visual approval, UXR-06/08/09/10 interfaces, risk register and remaining runtime checks |

**Definition of Done — ALL 20 acceptance criteria mandatory:**

1. **AC01** — UXR-00 final evidence, actual owner-reviewed UXR-01/02/02A image approvals and separately authorized UXR-07 execution all linked.
2. **AC02** — ≥**28 genuine full-resolution** 14-pair desktop/mobile render images in §8, plus narrow/tablet/mid/wide/theme/alternatives, directly viewable to owner.
3. **AC03** — Owner explicitly approves named, linked G7 result/detail/feedback image version and layout options; silence/agent recommendations do not count.
4. **AC04** — `IN_PROGRESS/result=null` resumes Runner and shows no result score/key; `SUBMITTED/result` alone enables terminal detail, else honest error/restore.
5. **AC05** — MCQ and Cloze `total/attempted/correct/accuracy` represented accurately, `attempted=0 → accuracy=null`, not false 0% or improper ARIA progress.
6. **AC06** — BLANK, INCORRECT, CORRECT distinct in per-question objective detail and completion denominators; no client rescoring or invented accepted alternatives.
7. **AC07** — MCQ correct option, Cloze accepted alternatives and Vietnamese explanations **only when terminal snapshot** authorizes their exposure.
8. **AC08** — Writing learner selfScore `0..4` and rubric explanation separate from objective percentages, provider AI comments and SRS rating; no invented composite mark.
9. **AC09** — Accurate weakest-result grouped SRS rating and per-word `APPLIED/SKIPPED_INACTIVE`; no second event, guessed dueAt or hidden historical result.
10. **AC10** — Empty or mixed handoffs, inactive source/card and chronological history preserve actual backend status and truthful actions.
11. **AC11** — Feedback request is optional, bound to submitted canonical nonblank Writing and exact answerRevision/rubricVersion; no implicit AI request from opening results.
12. **AC12** — Current consent fail-closed; granting permission does not auto-dispatch; local results remain readable without AI network/consent when local API is available.
13. **AC13** — `REQUESTED/VALIDATED/FAILED/UNKNOWN` statuses and criteria comments are visually distinct, provider/model information disclosed secondarily, no AI score overwrite.
14. **AC14** — Feedback `UNKNOWN` reuses same immutable key/body, history read does not prove original intent; new retry of confirmed FAILED references original operation, no double send.
15. **AC15** — No unverified claim that component-memory unknownIntent survives refresh; gaps declared for separate authorized implementation.
16. **AC16** — Feedback history date/status/answerRevision and cursor pagination accurate; page count not global; error/recovery does not erase history.
17. **AC17** — Full-width/a11y 320px and 200%-zoom design, long EN/VI explanations, screen reader states, keyboard focus and reduced motion; no premature WCAG PASS.
18. **AC18** — Existing official-compatible Button/Card/Dialog reused; missing primitives selected only via official shadcn docs, no install/config/package/source change.
19. **AC19** — Coordinator and every participating local design worker log **actual** installed Impeccable context invocation plus changed screenshot; inaccessible skill blocks Done.
20. **AC20** — No app code, route/backend/SQLite/quiz scoring/SRS/AI consent mutation, DTO regeneration, `tasks/todo.md`, test/production pass, UXR-00 closure or PR merge; clear UXR-06/08/09/10 handoffs.

**Lifecycle:** `PREPARED → READY_FOR_EXECUTION → IN_PROGRESS → OWNER_VISUAL_APPROVAL_PENDING → DONE`. The last step **requires actual accessible images + installed Impeccable evidence + explicit owner approval**, not merely checking this task file into GitHub.

## 12. File ownership, non-goals and UXR-08 stopping rule

**Later separately authorized workers:** a single **UXR-07 integration lead** owns consolidated image-index/decision/handoff and commits. **Result summary/answer review worker** exclusively owns `docs/design/uxr-07/assets/result-*`; **feedback/recovery designer** owns `assets/feedback-*` and `assets/history-*`; optional SRS/a11y critic returns notes via named scratch files with no shared overwrites. All participants must independently use installed Impeccable and contribute real invocation evidence.

**Shared/read-only:** UXR-01/02/02A frozen design assets; UXR-00 evidence; UXR-06 Runner and submission contract; UXR-08 consent/policy interface; UXR-09 Dashboard result linkage; existing official shadcn strategy. **Research coordinator alone** updates `docs/design/english-web-ui-ux-redesign-plan-2026-10-12.md` and Draft PR #26. `frontend/**`, `backend/**`, `components.json`, dependency locks, generated API and canonical `tasks/todo.md` strictly read only.

**Design-only boundaries:** no new quiz route, account/cloud storage, invented whole-app score, AI-grading Writing, provider retry automation, autonomous post-submit edits, new Markdown files or changes to source eligibility. No local browser screenshot or mockup files generated **by this documentation preparation**; those belong to future owner-authorized design execution.

**Handoff:** UXR-06 provides the terminal-only entry and active Runner return; UXR-08 provides reusable consent/error/recovery presentation; UXR-09 consumes only confirmed history/results; UXR-10 checks all nine-group visual inconsistencies. UXR-11 still requires final owner sign-off.

**After this UXR-07 task specification + roadmap/PR update: STOP. Do not prepare or execute UXR-08 until owner explicitly approves UXR-08 preparation.**

# UXR-06 — Quiz Builder & Runner Design

## CURRENT OWNER AUTHORIZATION — 2026-10-14 — DESIGN + FRONTEND IMPLEMENTATION

> **Binding amendment.** The owner changed UXR-06 from design-only research to **Design + Frontend Implementation** on 2026-10-14. [Shared implementation policy](../docs/design/uxr-03-09-design-frontend-implementation-policy-2026-10-14.md) is binding. The original task's source/evidence, feature semantics, all visual frame/viewport quotas, Impeccable, official shadcn, accessibility, and explicit owner visual approval requirements remain mandatory. Historical `design-only`, `no frontend edits`, `no code`, `no tests`, and `no implementation` clauses are **SUPERSEDED for the explicitly owned frontend scope only**. This section prevails over contradictory legacy clauses below. Application backend/API/DB/contracts still remain protected.

**CURRENT STATUS:** `READY_FOR_DESIGN_PLUS_FRONTEND_IMPLEMENTATION / NOT_STARTED` (UXR-02A owner-approved and published; launching Codex work still requires the owner's instruction).  
**CURRENT ACTION:** Design the complete UXR-06 feature experience **and implement it in the actual existing React/TypeScript/Tailwind frontend**, keeping the approved UXR-01/02/02A foundation unchanged.  
**OUTPUT STATE:** `OWNER_VISUAL_AND_IMPLEMENTATION_APPROVAL_PENDING`, not `DONE`, until owner review.  
**BASE:** `57159675fc59e984db1d64dcd899aedabf6622ff`; existing `design/uxr-06` worktree must safely fast-forward to the updated specification before execution.

### New authorized deliverables for UXR-06

1. Preserve **every original scenario, minimum full-resolution screenshot count, comparative evidence, and state/viewport gate specified later in this task**; additionally show the actual running application frontend implementing the design, not solely isolated mockups.
2. Implement the feature-owned frontend surfaces, preserving current app routes and supported API contracts. **Candidate ownership allowlist:** `frontend/src/features/quiz/** ONLY relevant Builder/Runner components after inspecting tree; feature-local tests/styles`. Inspect the actual repo to resolve paths; if an expected file moved, document the precise verified path. No arbitrary changes outside the feature boundary.
3. **Primary implementation targets:** quiz builder, question runner, autosave indicator, submission UI. The approved design direction is UXR-01 Compact Study Console v1.2 + UXR-02 AppShell R2/HM-FIX + UXR-02A Variant B/R1B. Do not redesign shared foundation.
4. **Read-only/cross-task seam:** UXR-07 results/feedback UI, scoring/backend snapshot. If a necessary change touches a shared/cross-feature file, record a proposed integration patch or ask for an explicit single-writer owner/coordinator decision; do not modify in two parallel worktrees.
5. No invented data or backend capabilities: preserve null/zero/UNKNOWN/error boundaries, existing operation contracts, idempotency, revision/reconciliation, user consent, and status truthfulness as applicable. Mark screenshots as `RUNNING_FRONTEND`, `ISOLATED_MOCKUP` or `SYNTHETIC_FIXTURE` accurately.
6. New implementation acceptance: actual TSX/styles changed; actual app can mount the affected route; representative functional interactions can be exercised against existing contracts or explicitly labeled fixtures; required full-resolution UI frames captured from the running frontend; feature-local build/type/browser check results documented. Full-system tests/audit remain for a later wave; do not fabricate PASS.
7. Every frontend-design Worker explicitly invokes installed `$frontend-ui-engineering`, plus relevant addyosmani skills and installed Impeccable in its own context; Astra acts as coordinator/auditor/integrator, delegates GPT-6.1 Sol Worker packages with single-writer file ownership.
8. Request `speed: fast`, `permission: full-access` via actual supported runtime controls, but still obey the file allowlist. On the exact model-capacity error, retry dispatch with a real 3s delay up to 30 times, then replace the blocked, non-running worker (max 3 replacement workers per package) without changing model or duplicating writes. Disclose unverified actual-model/speed/permission metadata.
9. No new dependencies or shadcn installation without separate approval; reuse current canonical primitives. No unapproved edits to `backend/**`, SQLite, API/DTO/OpenAPI, generated contracts, SRS/quiz/consent business semantics, main, UXR-02A frozen artifacts, `tasks/todo.md`, or shared app shell. No automatic commit/push/merge; stop for owner visual + implementation review.
10. Acceptance item previously reading `no app/frontend code changes` is now `no unauthorized code changes outside owned frontend`; any other old item only contradicted by this explicit amendment is `SUPERSEDED_BY_OWNER_2026-10-14`, **not PASS**. Add an `IMPLEMENTATION_GATE` alongside all original design AC. No existing critical visual or safety criterion is waived.

---


**Track:** English Web — major final UI/UX redesign. **Design-only task specification**, separate from canonical T001–T090 application tasks and AI orchestration.  
**Priority:** P0 — group **G6 Quiz Builder & Runner**.  
**Status:** `PREPARED / NOT STARTED / BLOCKED_BY_UXR_02A_OWNER_VISUAL_SIGNOFF`.  
**Owner authorization (2026-10-12):** prepare this task card, update design roadmap and Draft PR #26 **only**. No redesign execution, mockup production/sign-off, frontend/backend modifications, local tool installations, tests, or merge.  
**Routes:** `/quiz/new` and `/quiz/:attemptId`; handoff to `/quiz/:attemptId/result` is UXR-07-owned.  
**Dependency DAG:** UXR-00 final verified evidence → UXR-01 owner-approved A/B visual direction → UXR-02 owner-approved shell/foundation images → UXR-02A owner-approved information density/images → UXR-06 **separately authorized design execution** and owner visual approval → UXR-10 → UXR-11. Task **preparation** can occur before upstream design approval; actual execution cannot.  
**Parallel peer tasks:** UXR-03–05 and UXR-07–09 design execution may run in non-overlapping areas once UXR-02A visual gate has genuinely passed.  
**Repo/PR:** `khanhpn308/english_web`, branch `design/ui-ux-research-20261012`, [Draft PR #26](https://github.com/khanhpn308/english_web/pull/26), keep OPEN/DRAFT/unmerged.  
**Binding policy:** [Mandatory owner-visible UI screenshots, installed Impeccable and official shadcn/ui](../docs/design/uxr-visual-approval-impeccable-protocol-2026-10-12.md).  
**Next gate:** stop after this documentation update; the owner must separately approve **preparing UXR-07 — Quiz Results & Writing Feedback Design**.

## 1. Objective, product boundaries, success definition

Design a **cohesive and compact, but academically readable** two-part quiz workflow that the owner can assess by viewing real high-fidelity **rendered UI images** before design approval:

1. **Builder:** choose the saved-vocabulary source note date and question counts for MCQ / Cloze / Writing, understand total/limits and AI creation dependency, explicitly pass consent and create a valid attempt, and safely interpret validation, generation, permission, unknown and recovery outcomes.
2. **Runner:** work through immutable public question snapshot, answer MCQ/Cloze, write free text and **explicitly self-score Writing 0–4** against available rubric; observe **per-question** draft acknowledgment (pending/saving/saved/error/conflict/unknown), reconcile or compare competing revisions without losing local text, verify all drafts before submit, and distinguish IN_PROGRESS from **server-confirmed SUBMITTED**.
3. **Cross-route journey:** `/quiz/new` → `/quiz/:attemptId` → `/quiz/:attemptId/result` only after backend terminal commit. UXR-07 owns the **result and AI feedback displays**; UXR-06 owns pre-submit and safe handoff/read-only runner. UXR-05 owns Flashcard's subjective four-rating interface; Writing rubric self-score is **not** that rating widget.

**No application behavior change from this task**: no new endpoints, answer key leakage, snapshot mutation, SRS formula changes, bridge/consent bypass, AI judging Writing automatically, or implementation before UXR-11 owner design sign-off. Existing multi-question Runner vs proposed one-at-a-time layout is an **open owner decision**, not permission to change save/submit semantics.

## 2. Source-backed baseline and genuine evidence limitations

| Repository source | Verified source behavior / proposed design implication |
|---|---|
| `frontend/src/features/quiz/QuizBuilder.tsx` | Phases `idle/validation/authorizing/loading/recoverable/terminal/unknown/reconciling`. Three count inputs default 2 MCQ / 2 Cloze / 1 Writing, date input; validates 0–20/type and total 5–30, gets explicit `AiConsentGate` permission before bridge-backed generation, preserves form state for retry/recovery. Shows Stop Waiting notice and same-operation check for `UNKNOWN`. Request uses stable Idempotency-Key + X-Request-ID. |
| `QuizBuilder.tsx` | Existing `max-w-2xl mx-auto` Card under differently aligned page heading, no displayed aggregate count; verified **desktop screenshot** VIS-009 captures this Builder state. Source uses `parseInt` for counts; authoritative contract demands strict integers: propose explicit correct validation copy/state but do **not** claim runtime acceptance tests or silently change parser in a design-only task. Date initialization uses UTC ISO; do not assume a Bangkok-local date without separate contract/code review. |
| `frontend/src/features/quiz/QuizRunner.tsx` | Runner reads `GET /api/v1/quiz-attempts/:attemptId` `no-store`, restores public questions + answers + `answerPreconditions` ETags; separate per-question `serverRevision/serverEtag/serverAnswer/serverSelfScore` and local draft; sync states `idle/pending/saving/saved/error/conflict/unknown/reconciling`. Debounces 500 ms and flushes on blur. |
| `QuizRunner.tsx` | Per-answer PUT uses `{answer,selfScore,draftRevision}`, exact `If-Match` ETag and stable `Idempotency-Key`. A missing/bad acknowledgment becomes `UNKNOWN`; read/compare server state before replaying *identical* intent. `REVISION_CONFLICT` reveals explicit current-vs-local choice; no silent overwrite. `SUBMITTED` runner becomes read-only. |
| `QuizRunner.tsx` | `submitDraft()` flushes per-question edits and blocks submission if any dirty/in-flight/unknown/conflict/error remains before calling supplied `onSubmit`. The actual submitted-attempt handler/receipt integration must be source-traced before rendering a “confirmed SUBMITTED” state; a stale line of T051 integration copy is not proof the button is presently unavailable or available at runtime. |
| `frontend/src/features/quiz/QuestionRenderer.tsx` | MCQ native radio group; Cloze text field; Writing textarea with `Chưa tự đánh giá` (`selfScore=null`) plus `rubric.descriptors` numeric 0–4. Distinct question drafts and labels; no objective answer keys exposed in question renderer. |
| `docs/adr/0005-contract-clarifications.md` §C013-01/03/06/07 | Strict per-type counts 0–20, total 5–30; available distinct source count; 2/2/1 example yields 5 questions when 3 source forms sufficient. Objective BLANK ≠ INCORRECT; Writing `null` blocks submit, blank Writing allowed only with **explicit score 0**, nonblank self-score 0–4. IN_PROGRESS responses must not reveal correct MCQ choice/accepted Cloze alternatives or Vietnamese explanation. |
| `docs/ui-architecture.md` §J5, related ADRs | Creation uses optional external AI + explicit consent; consent grant **does not auto-dispatch**. In-progress answer edit/autosave/reload/submit/result retrieval are **local API** after attempt exists. Submit uses aggregate `submissionRevision` after flush/latest read, idempotency and guarded terminal result. Results/AI writing feedback remain separate UXR-07 responsibilities. |
| `docs/design/ui-visual-audit-2026-10-12-batch2.md` | **G6 PARTIAL.** One direct **desktop Quiz Builder screenshot**, VIS-009. There is **NO direct verified screenshot of MCQ/Cloze/Writing Runner**, autosave, revision conflicts, submit guard, unknown or mobile states. Source-driven observations must be marked `SOURCE_CONFIRMED / NOT_VISUALLY_VERIFIED`, never fabricated “current app screenshots”. |

**Critical guardrails derived from ADR C013-07:** an attempt has `status: IN_PROGRESS|SUBMITTED` and `result=null` only in progress; `submissionRevision` (aggregate) differs from `snapshotRevision` and per-answer `draftRevision`. A terminal result is backend-authoritative. A lost submit response can be checked using existing attempt/operation state or same request identity; never create a second submit/SRS update just because a spinner ended. A restored/corrupt snapshot may return `QUIZ_RESTORE_REQUIRED`, not an empty quiz.

**Evidence categories:** `CURRENT_APP_CAPTURE` (authentic screenshots only), `SOURCE_CONFIRMED` (code/ADR semantics), `DESIGN_MOCKUP / SYNTHETIC` (future proposal), `NOT_VERIFIED` (no evidence). Exactly record source screenshot file/viewport if available; image pixels are not automatically CSS pixels. UXR-00 final inventory remains required.

## 3. Start gate and required owner authorizations

Before **actual** UXR-06 visual work:
1. Verify **UXR-00** source+journey final evidence and unresolved capture gaps; cite baseline revision and genuine Builder capture.
2. Read **UXR-01** exact A/B-selected visual direction signed by owner, **UXR-02** approved AppShell/route/typography/theme snapshots, **UXR-02A** approved Dashboard/Review/Status compact density snapshots and CTA/disclosure contract. None of these is proven complete merely by prepared task cards.
3. Obtain **separate explicit owner authorization** for UXR-06 *design execution*, not only permission to create this task.
4. Assign one **UXR-06 integration lead**, Quiz Builder visuals specialist and Quiz Runner/answer-state specialist; optional independent accessibility/critical recovery reviewer, with strictly non-overlapping asset prefixes.
5. All active local designer agents, **coordinator plus every worker**, must discover/read and actually invoke the **owner's already-installed** Impeccable skill once per session. Absence/error must be reported without reinstall or fabricated success.
6. Treat UXR-07 result/AI feedback, UXR-08 consent UI and UXR-05 SRS rating design as **separate** task owners. Establish presentation-only seams; do not mutate source or shared primitives.

## 4. Builder G6 — form, validation and AI creation states

Prepare a source-to-design matrix `state | preconditions | action | URL/operation identity | server-authoritative outcome | user-facing status | focus | allowed next step | screenshot ID`.

- Compact heading consistent with UXR-02 AppShell content edge; date picker/native date, **three clearly labelled integer counts** (`MCQ`, `Cloze`, `Writing`) and live total `n/30`. Explicit bounds **0..20 each, 5..30 aggregate**, and backend rejects insufficient eligible distinct source word forms. `2+2+1=5` is a valid config **only with enough eligible source forms**; `1+1+1=3`, negative/fractional/boolean and >20 per type are invalid. An all-zero category can be valid if total within range; do not invent a rule that each type must be >0.
- Differentiate **form validity** from **source sufficiency**; do not promise sufficient sources before authoritative API check. Display selected noteDate and local saved-source dependency (can include valid saved forms even if not due). No active Book/Library selection or misleading due-card restriction.
- **One dominant Create action**, contextual summary above fold, tightly grouped fields with low empty whitespace, as motivated by VIS-009. Validation error message associated with precise inputs and title/focus; don't turn invalid configuration into a bridge dispatch.
- Before generation, **AI consent fail-closed**, preserve chosen counts/date when denied, revoked or policy stale; after grant, do **not** auto-send; next explicit Create action only. Consent modal visual implementation remains shared **UXR-08**.
- `authorizing`, `loading` with honest long-generation wait, Cancel Waiting informational note (`abort` is **not** recall/delete of already sent content), recoverable network/auth/provider failure, terminal failure and `UNKNOWN` operation. An unresolved `operationId` is checked/replayed under the **same immutable request key**, never via unannounced second creation.
- On proven successful creation, route to `/quiz/:attemptId`, not result screen. Do not treat mockup success text as a verified bridge/backend response. Preserve form intent in UI while error/permission is pending; any stronger durability after reload requires source proof rather than assumption.
- **Date subtlety:** source Builder currently derives initial date from `new Date().toISOString().split('T')[0]`, while note dates elsewhere use Bangkok calendar. The design should clearly show selected `YYYY-MM-DD` and flag timezone/default behavior as a **contract clarification candidate**, not implement a change silently or falsely claim locale bugs.

## 5. Runner G6 — three question types, navigation and honest progress

**Existing baseline:** Runner renders the attempted quiz's **full question list** via `questions.map` and each `QuestionRenderer`; there is no approved single-question navigation contract yet. Owner decision **D5** on all-at-once vs one-by-one is OPEN.

- Propose **two UI variants** within approved UXR-01 direction: A) all questions in one accessible scrollable document, with anchored question index/progress and per-question status; B) one-question-at-a-time with an accessible question navigator, preserved per-question draft/scroll/focus and a deliberate response to pending/unknown autosave. **Do not decide the product flow or silently implement the second option.** Owner must see images and select a named variant. Both variants must preserve same underlying immutable snapshot and update/submit rules.
- MCQ: accessible radio group and option labels, selected state, pending vs confirmed saving indicator. Do not show correct answer or “pass/fail” on the runner.
- Cloze: one appropriately labeled text field, normalization/trimming rules remain server-defined; blank answer not same as wrong, and user text is preserved until acknowledged.
- Writing: multiline English text editor, **rubric descriptor 0/1/2/3/4 with meaningful Vietnamese explanations**, explicitly distinct `Chưa tự đánh giá` (`selfScore=null`); show blank Writing + score 0 as separately chosen permitted terminal case, but do not silently default blank to 0. Blank text + positive score is a validation error. Writing self-score is learner-origin data, not AI evaluation.
- Display per-question `CHƯA LƯU / ĐANG LƯU / ĐÃ LƯU / LỖI / XUNG ĐỘT / CHƯA XÁC ĐỊNH` with text (not color only), retained draft, focused recovery action; optional aggregate “X/Y questions with confirmed draft” can be computed only from actual authoritative/current local acknowledged counts, not mistaken for a final score.
- Questions, correct-answer references, translations/accepted options and scoring must remain hidden pre-submit; rubric descriptors are deliberately public. Do not expose objective solutions or Vietnamese explanation through source text, image mockup of an IN_PROGRESS state, tooltip, hidden CSS, accessibility tree or inspectable props.
- A no-network/external-bridge state **after attempt creation** must permit local answer saving/submission/result retrieval if the **local API is healthy**. Distinguish local session expiry and corrupted/undecryptable snapshot from AI outage.
- Accessible route/current question heading, 320px wrap for long prompts, visible keyboard focus, `aria-live` for save states, predictable placekeeping after collapse/next question. Proposed progress bar is **question completion**, not learned mastery/accuracy; use it only with honest denominator `attempt.questions.length`.

## 6. Autosave, conflict resolution, safe submit and terminal handoff

### 6.1 Per-question Save state machine

Write an explicit matrix for `idle → pending → saving → saved`, including `error/conflict/unknown/reconciling`.

1. Runner initializes `serverRevision`, `serverEtag`, server answer/selfScore and local editable draft from authoritative attempt GET.
2. Editing triggers local `pending`, 500 ms debounce or onBlur `flush`; PUT carries `draftRevision`, precise `If-Match` ETag and one immutable `Idempotency-Key` for that mutation. While in-flight, do not re-enable controls that would discard a concurrent edit.
3. Only matching validated server receipt/ETag sets `saved`. A response missing matching draft revision or ETag is **UNKNOWN**, not saved.
4. Re-read attempt before resolving **UNKNOWN**; if server already acknowledges identical request, settle; if still old revision/ETag, an explicitly safe replay of **same identity and body** may be allowed by existing state machine. Never submit a new different PUT as “retry” while old intent remains unknown.
5. On `REVISION_CONFLICT`, show **server version vs local typed version** side-by-side only after server read actually yielded content. User chooses `Dùng bản máy chủ` or **explicitly** `Lưu bản đang nhập` using fresh source precondition; no silent last-write-wins and no fake server diff.
6. If user edits while an old mutation is resolving, protect **newest local draft**; no old response should overwrite latest user input. Mockup must reflect pending status rather than false completion.
7. Text about durability is precise: local unsent draft in memory is **not** guaranteed after tab closure or process crash. Server-acknowledged Answer[] survives refresh/rebootstrap where backend state is valid; don't promise offline device storage that has not been implemented.

### 6.2 Submission gate and results handoff

- Show a **pre-submit checklist/summary** of confirmed saved answers, unanswered objective prompts, Writing selfScore selections and any per-question pending/error/unknown/conflict. Submission disabled/blocked while **ANY draft is unconfirmed**, including a pending 500 ms debounce/blur flush.
- For Writing, `null` is explicitly **incomplete**; require deliberate self-score 0–4 even if text is empty (blank valid only with **0**). A blank objective answer is allowed as blank, not silently replaced with “wrong” before scoring.
- Submit is **not** a button that assumes immediate result. The integrated submit handler must flush, re-read the current **aggregate submissionRevision**, send a single stable-key submit, and handle `REVISION_CONFLICT`, `IDEMPOTENCY_IN_FLIGHT`, result-read recovery, `ALREADY_SUBMITTED`, session expiry and `QUIZ_RESTORE_REQUIRED`. The runner's observed source exposes an `onSubmit` integration hook; confirm actual handler/receipt in application routes before asserting it is wired, not just code comment.
- Once backend proves `SUBMITTED` and result is stored, show **read-only runner / “Xem kết quả”** transition to `/quiz/:attemptId/result`; **UXR-07** designs actual detailed scores, correct answers, writing feedback and result history. IN_PROGRESS `result=null` must always return to Runner, not a “0% result”.
- Never reveal `correctOptionId/acceptedAnswers/explanationVi` in an IN_PROGRESS screenshot. Never automatically resubmit or double-apply SRS effects when a response is lost. Reconciliation prefers authoritative attempt/operation read and valid original submission key.
- Visual alternatives for submit handling: compact persistent bottom action after last question vs summary bar, each justified for keyboard, error discovery and mobile sticky overlap; owner selection required if navigation structure changes.

## 7. Mandatory owner-visible full-resolution UI images (VG4)

**At later authorized design execution, not now:** **at least 30 original full-resolution PNG/WebP UI screenshots**, each a complete representative screen, arranged as **15 paired cases × `1366×768` desktop plus `390×844` mobile**, with visually realistic **SYNTHETIC / DESIGN_MOCKUP** study data and clearly honest status labels. No ASCII wireframes, bare Markdown, component catalogs, low-resolution contact-sheet-only delivery, or fictional `CURRENT_APP_CAPTURE` can satisfy this approval.

| Pair | Screen/state | Mandatory visible design content |
|---|---|---|
| QB01–02 | Builder initial/default `2/2/1` | Compact aligned form, selected date, 5-question summary, one Create CTA |
| QB03–04 | Builder validation/insufficient eligible source | Fractional/out-of-range or total <5 rejection, field-level help, no AI dispatch; insufficiency separate from bad input |
| QB05–06 | Builder AI permission needed | Preserved counts/date, consent gate; no automatic create after grant |
| QB07–08 | Builder generating/loading | Honest wait, stop-wait meaning and retained request context |
| QB09–10 | Builder `UNKNOWN` / recoverable | Same-operation `Kiểm tra kết quả`, no duplicate creation |
| QR01–02 | Runner multi-question overview + MCQ | Public prompt/options, navigation/progress based on actual snapshot count, no answer key |
| QR03–04 | Runner Cloze | Entered word/text, clear per-question Save state, bilingual task instructions as appropriate |
| QR05–06 | Runner Writing / `selfScore=null` | Textarea + 0–4 rubric descriptors and visible “Chưa tự đánh giá” |
| QR07–08 | Runner Writing valid explicit score 0 or >0 | User-selected score, saved-state status, no AI grading or auto-score |
| QR09–10 | Per-question autosave pending/saving/saved | Distinct legible statuses, answer not treated as durable before receipt |
| QR11–12 | Per-question `REVISION_CONFLICT` | Side-by-side server vs local after real read; explicit resolution buttons |
| QR13–14 | Per-question `UNKNOWN` | Safe reconcile current attempt, preserve unsent local draft |
| QR15–16 | Pre-submit blocked/checklist | Pending/unconfirmed fields, Writing null vs zero, no premature submission |
| QR17–18 | Submitting or uncertain terminal result | Intent/operation recovery, avoid duplicate submit/SRS, no objective key pre-commit |
| QR19–20 | `SUBMITTED` runner/read-only transition | Verified terminal state, direct result navigation, no editing |
| QR21–30 | **Five additional paired states (not part of 30 minimum)** | Additional coverage across `SESSION_EXPIRED`, `QUIZ_RESTORE_REQUIRED`, AI/network create failure, MCQ/Cloze blank state, **alternate full-list vs one-at-a-time navigation**. Publish exact IDs/captions; every pair is a distinct complete screen, not duplicative collage |

**Counting rule:** QB01–QB10 = 10, QR01–QR20 = 20, **total 30 required original full screens**. QR21–30 line above is an additional **recommended extension**, **not counted toward 30** and must not be misreported as part of the minimum. Any omitted essential scenario must be covered in extra frames. An individual scenario pair cannot count as two when only one responsive screenshot is generated.

**Additional required images/evidence beyond 30:** 
1. **`320×568` narrow stress**: long MCQ options, multiline Cloze prompt and Writing rubric/textarea without horizontal overflow; **`768×1024` tablet**, **`1024×768` intermediate** and **`1440×900`** whole AppShell.
2. At least one same-state **light/dark** pair with errors, successful saved/unknown badges and contrast discussion (can overlap a primary pair if same state genuinely appears in both themes).
3. **A/B screenshot variants for Runner navigation** (all questions vs one-by-one, desktop **and** mobile), including a state where a Writing draft is pending, with source preservation tradeoffs. Owner approval of exact Runner variant **must be recorded** before Done; don't silently choose.
4. Authentic before/proposed comparison for **Builder** only if UXR-00/owner capture is actually retrievable. **Runner has NO DIRECT CURRENT SCREENSHOT** in present evidence: show `SOURCE_ONLY/NOT_VERIFIED`, not a fake before image.
5. Interactive storyboard/review of **invalid → correction → grant AI (no dispatch) → explicit create → Runner**, and **typing → pending → saved/conflict/unknown → submit guard → confirmed result**, keeping synthetic backend states labeled.
6. Contact sheet sufficiently readable **plus direct clickable original full-resolution links** for each frame under `docs/design/uxr-06/assets/` or owner-approved durable location. Image descriptions record `UXR-06 | route | state | frame ID | variant | exact CSS viewport | theme | DESIGN_MOCKUP/CURRENT_APP_CAPTURE | SYNTHETIC if needed | version/date | link`.

**Owner review outcome:** record `APPROVE / REQUEST_CHANGES / REJECT / PENDING`, exact image/version IDs, selected A/B Runner navigation and feedback. **Only an explicit owner response to the images counts as APPROVE.** If missing images, source claim, Impeccable invocation or owner sign-off: `OWNER_VISUAL_APPROVAL_PENDING`, not DONE. Revised screenshots require reapproval; UXR-11 still requires final integrated nine-group approval.

## 8. Mandatory already-installed Impeccable skill use

The owner reports [pbakaus/impeccable](https://github.com/pbakaus/impeccable) is **already installed locally**. **Do not install, reinstall, update, vendor, or relocate it.** During **later owner-authorized local design sessions**:

1. **Astra/Codex coordinator and EVERY independent Builder, Runner, Writing, recovery/critique design worker** separately discover their installed skill path/version and read **their own installed `SKILL.md`** plus relevant references; forwarded coordinator summaries do not satisfy proof.
2. From project root execute installed `<skill-base>/scripts/impeccable context` **once per session**, using `<skill-base>\scripts\impeccable.cmd context` on Windows when applicable. Do not guess a path or claim command success without actual result.
3. Select installed-version `shape` (journeys/form), `layout`/`distill` (builder and question density), `clarify` (Vietnamese validation/draft language), `harden` (UNKNOWN/consent/recovery), `adapt` (mobile/200% zoom) and independent `critique` (focus, action hierarchy) as relevant; **not all verbs blindly**. The skill cannot authorize edits to production UI files during the no-code phase.
4. Each worker independently logs `agent/role | harness | installed skill path/version | session/context invocation timestamp/result | relevant reference/verb | finding | concrete mockup revision/image ID`. Coordinator records its **own** invocation and aggregates independent evidence in `UXR-06-IMPECCABLE-EVIDENCE.md`.
5. If installation not exposed to agent or launcher fails, report exact `IMPECCABLE_NOT_ACCESSIBLE` with real error; do **not** reinstall, silently skip or declare skill PASS. Owner resolution is required for final design acceptance.
6. Preserve upstream approved UXR-01/02/02A identity, consent fail-closed, local-data durability, accessibility and official shadcn constraint even if a skill suggests a different visual pattern.

**GitHub-only document drafting now does not invoke the owner's Windows-installed skill and must never claim so.**

## 9. Official shadcn/ui-only component mapping and reuse

**Sole default source for missing reusable components:** https://ui.shadcn.com/docs/components; see [project official-component strategy](../docs/design/shadcn-ui-component-strategy-2026-10-12.md). Existing `components.json` uses New York style, React 19, Vite 8, Tailwind 4 with existing non-Preflight CSS foundation and **Radix-based** local `Button/Card/Dialog`. Keep those primitives canonical; official candidate list does not imply installed.

**Future artifact:** `component surface | exact official shadcn component name/docs URL | ALREADY_PRESENT / OFFICIAL_PROPOSED / COMPOSITION / DEFERRED | keyboard/ARIA risks | eventual owner`.

| G6 surface | Official candidates (select only as justified) | Constraints |
|---|---|---|
| Builder counts and note date | **Field, Input, Button (existing), Card (existing), Alert, Badge, Separator**, optional **Date Picker** | Strict integer/date validation, correctly labelled total; optional Date Picker only after locale/keyboard review |
| AI permission/loading | Existing **Dialog** via shared UXR-08, **Alert, Skeleton, Badge, Progress** only if determinate | No invented percent of AI generation, no consent auto-send |
| MCQ | **Radio Group, Field, Card, Button** | Native semantic grouping and visible focus, preserve options and no key leak |
| Cloze | **Input, Field, Card** | Draft text retained, no hint that leaks accepted alternatives |
| Writing/rubric | **Textarea, Radio Group, Field, Separator, Accordion** for optional rubric details | Show complete 0–4 descriptors, null vs explicit 0 |
| Question navigation/true completion | **Tabs** or **Pagination** only if chosen via owner A/B, **Progress, Badge** when denominator is actual snapshot questions | Keyboard and pending-draft preservation, no quiz score prediction |
| Save/submit/restore/uncertainty | **Alert, Badge, Skeleton, Collapsible, Dialog or Alert Dialog** if truly necessary | Distinct pending/saved/unknown/conflict; no destructive auto-submit |

Propose app-level compositions `QuizConfigForm, QuestionTypeCount, QuizDraftStatus, QuestionIndex, QuestionHeader, RubricSelfScore, DraftConflictCompare, SubmitReadiness, SubmitRecovery` built **from official and existing primitives**. Do not copy third-party registries, replace Radix with unapproved base mix, run shadcn `init`, `add`, `--all` or `--overwrite`, install npm packages, or change `components.json`, lockfile/CSS in task preparation or design. Later approved implementation requires specific official docs verification, pinned CLI diff and shared primitive-owner review.

## 10. Execution deliverables (future; NOT files produced by this task preparation)

Everything under **`docs/design/uxr-06/`**, with one integration lead:

| Planned file | Later required content |
|---|---|
| `UXR-06-EVIDENCE-STATE-MATRIX.md` | source/ADR/observed-vs-source-only state transitions for Builder, Runner and submitted handoff |
| `UXR-06-BUILDER-DESIGN.md` | compact form/total, integer/date validation, source eligibility, AI permission/generation/recovery |
| `UXR-06-RUNNER-DESIGN.md` | MCQ/Cloze/Writing visible content, A/B navigation options, progress/answer focus |
| `UXR-06-WRITING-RUBRIC.md` | selfScore null vs 0–4, rubric descriptors and blocking rules |
| `UXR-06-AUTOSAVE-CONFLICT.md` | per-answer revisions/ETags/idempotency, concurrent local drafts, error/UNKNOWN/explicit conflict compare |
| `UXR-06-SUBMIT-HANDOFF.md` | flush/read/submissionRevision/terminal vs pending states and UXR-07 ownership boundary |
| `UXR-06-RESPONSIVE-A11Y.md` | 320px/200%-zoom/mobile/tablet/desktop, keyboard, label, status and focus requirements |
| `UXR-06-SHADCN-MAPPING.md` | official component docs URLs, existing/proposed/deferred and Radix compatibility |
| `UXR-06-VISUAL-GALLERY.md` and `assets/*.png`/`*.webp` | **≥30** full-resolution frames + extras/alternatives, contact sheets and owner-clickable links |
| `UXR-06-IMPECCABLE-EVIDENCE.md` | coordinator **and every worker** actual locally installed skill invocation or genuine blocker |
| `UXR-06-OWNER-DECISION.md` | owner A/B Runner selection, image/version approval/revision log |
| `UXR-06-HANDOFF.md` | frozen G6 visual contract, runtime unverified risks, UXR-07/08/10 interface and worktree ownership |

The above are **execution deliverables only**. This GitHub task file does not create these galleries, install components, validate runtime or secure owner image sign-off.

## 11. Measurable Definition of Done — 22 acceptance criteria

Actual **UXR-06 DONE** requires all conditions:

1. **AC01** UXR-00 final evidence and **owner-approved image/version** references for UXR-01, UXR-02 and UXR-02A; separate owner authorization to execute UXR-06.
2. **AC02** ≥30 original full-resolution Desktop/Mobile complete-screen proposed images per §7, plus narrow/tablet/intermediate/wide, A/B nav variant and theme, all links accessible to owner.
3. **AC03** Owner **explicitly approves** exact Builder, MCQ/Cloze/Writing, autosave/recovery/submit versions **AND** selects full-list vs one-question Runner based on **actual screenshots**; agent recommendation not approval.
4. **AC04** Builder aligned with frozen UXR-02/02A shell/density and compact aggregate count; no giant empty configuration Card or conflicting primary CTAs.
5. **AC05** Strict 0–20/type, total 5–30, integer/date and sufficient distinct-source eligibility; 2/2/1 positive / 1/1/1 invalid fixtures represented honestly.
6. **AC06** AI consent fail-closed, no automatic creation after grant, no generation on validation error or incomplete authorization, preserve count/date intent.
7. **AC07** Generator `UNKNOWN`/cancel waiting preserved request identity and visible safe `Kiểm tra kết quả`; no silent second AI dispatch.
8. **AC08** Runner only shows immutable **public** IN_PROGRESS snapshot; never objective answer keys/accepted Cloze alternatives/terminal explanations before committed submission.
9. **AC09** MCQ radio semantics, Cloze typed-answer, Writing multiline with rubric descriptors, blank/nonblank objective distinction and correct bilingual copy.
10. **AC10** Writing `selfScore=null` clearly incomplete and blocks submit; explicit score 0 differs from unanswered, positive score on blank text correctly invalid.
11. **AC11** Per-question `idle/pending/saving/saved/error/conflict/unknown/reconciling` states and backend-ack-only “Đã lưu” clearly illustrated.
12. **AC12** Exact `draftRevision/If-Match ETag/Idempotency-Key` guard and 500ms/blur flush preserved; old receipt cannot erase newer local typing.
13. **AC13** `REVISION_CONFLICT` has actually-read server-vs-local values and explicit choices, no overwrite from stale revision.
14. **AC14** Per-answer `UNKNOWN` reads authoritative attempt before replaying **same request identity**; no altered duplicate request.
15. **AC15** Submission blocks any unconfirmed draft, distinguishes quiz **aggregate submissionRevision** from question draftRevision and snapshotRevision, then validates backend submit status.
16. **AC16** Terminal UI uses `IN_PROGRESS/result=null` vs real `SUBMITTED/result`; no “0%” result before commit, no double SRS events on retry/ALREADY_SUBMITTED.
17. **AC17** External AI bridge outage affects creation/feedback only, not local API answer editing, submit/result of an existing attempt; error/rebootstrap/restore states are truthful.
18. **AC18** 320px/200%-zoom and mobile/tablet responsive, labels, focus restore, screen reader announcements, reduced motion and touch target design — no unverified WCAG AA PASS.
19. **AC19** Only existing/official shadcn primitives with exact docs URLs and compatible Radix base; no component install/dependency/config changes.
20. **AC20** Coordinator and **every active visual designer** actually invoke already-installed Impeccable in own session, log impact; `IMPECCABLE_NOT_ACCESSIBLE` blocks sign-off.
21. **AC21** Real Builder capture provenance, missing Runner baseline, synthetic mockups and undecided Runner navigation all documented, with signed A/B selection and source-driven risks distinguished from observed bugs.
22. **AC22** UXR-07 results/feedback, UXR-08 consent, UXR-05 SRS, UXR-09 dashboard are clearly handed off; **no source code**, API, SQLite, dependency, generated DTO, test, `tasks/todo.md`, UXR-00 completion, PR merge or false runtime claims.

**Lifecycle:** `PREPARED → READY_FOR_EXECUTION (upstream visual approvals + separate execution authorization) → IN_PROGRESS → OWNER_VISUAL_APPROVAL_PENDING → DONE` only after all ACs, owner images and actual local skill log are satisfied. Fail any gate → not DONE.

## 12. Out of scope, collaboration and next-owner stop

**Out of scope:**
- No production `frontend/**` React/TypeScript/CSS, `backend/**` API/SQLite, `components.json`, `package-lock.json`, `tasks/todo.md`, tests, dependencies, Windows launcher, provider calls, snapshots or real quiz grading/submit actions in task preparation.
- No alteration to strict integer limits, source eligibility, bridge consent, answer drafts/ETag semantics, unknown operation reconciliation, quiz result scoring or backend SRS. No new question types, books/exercises/IELTS/TOEIC collections or Book/Library routes.
- No fake Quiz Runner *before* screenshot, no claim of local Impeccable invocation or installed shadcn components, no unsupported WCAG/CI/security PASS and no unilateral choice of one-question workflow.
- No taking over UXR-07 result design or writing AI feedback, UXR-08 policy/consent dialogs, UXR-09 Dashboard learning metrics. No UXR-00 closure, UXR-11 final sign-off or unapproved future UXR-12.

**Artifact ownership and parallelism:** later authorized UXR-06 integration lead is **single writer** for `docs/design/uxr-06/*-DESIGN.md`, combined state/decision/gallery/handoff and `UXR-06-IMPECCABLE-EVIDENCE.md`; Builder worker exclusively owns `docs/design/uxr-06/assets/builder-*`; Runner worker owns `assets/runner-*`; Writing/Conflict reviewer, if separately dispatched, owns `assets/writing-*` and `assets/recovery-*`. All independently invoke installed Impeccable. Roadmap/PR are updated **only by design coordinator**. UXR-00/01/02/02A reference assets and all other task-specific design folders are read only. If a shared token/navigation decision must change, escalate to owner for reapproval, never independently overwrite.

**Handoff to UXR-07:** convey post-submit route boundary, confirmed SUBMITTED vs IN_PROGRESS states, non-leaked objective keys, all-writing-score completeness and draft/submit recovery; UXR-07 exclusively designs terminal result metrics/feedback. **UXR-10** consumes G6 owner-approved image/version, component and responsive matrices and real Impeccable log. **UXR-11** independently requires final nine-group owner visual approval.

**Stop condition for this turn:** commit UXR-06 **task Markdown**, update roadmap and Draft PR #26, verify no code/lock/checklist changes, and **STOP** until the owner explicitly authorizes **preparing UXR-07**. This is task preparation only; no redesign executed.

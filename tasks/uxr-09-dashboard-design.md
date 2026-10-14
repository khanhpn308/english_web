# UXR-09 — Dashboard Design

## CURRENT OWNER AUTHORIZATION — 2026-10-14 — DESIGN + FRONTEND IMPLEMENTATION

> **Binding amendment.** The owner changed UXR-09 from design-only research to **Design + Frontend Implementation** on 2026-10-14. [Shared implementation policy](../docs/design/uxr-03-09-design-frontend-implementation-policy-2026-10-14.md) is binding. The original task's source/evidence, feature semantics, all visual frame/viewport quotas, Impeccable, official shadcn, accessibility, and explicit owner visual approval requirements remain mandatory. Historical `design-only`, `no frontend edits`, `no code`, `no tests`, and `no implementation` clauses are **SUPERSEDED for the explicitly owned frontend scope only**. This section prevails over contradictory legacy clauses below. Application backend/API/DB/contracts still remain protected.

**CURRENT STATUS:** `READY_FOR_DESIGN_PLUS_FRONTEND_IMPLEMENTATION / NOT_STARTED` (UXR-02A owner-approved and published; launching Codex work still requires the owner's instruction).  
**CURRENT ACTION:** Design the complete UXR-09 feature experience **and implement it in the actual existing React/TypeScript/Tailwind frontend**, keeping the approved UXR-01/02/02A foundation unchanged.  
**OUTPUT STATE:** `OWNER_VISUAL_AND_IMPLEMENTATION_APPROVAL_PENDING`, not `DONE`, until owner review.  
**BASE:** `57159675fc59e984db1d64dcd899aedabf6622ff`; existing `design/uxr-09` worktree must safely fast-forward to the updated specification before execution.

### New authorized deliverables for UXR-09

1. Preserve **every original scenario, minimum full-resolution screenshot count, comparative evidence, and state/viewport gate specified later in this task**; additionally show the actual running application frontend implementing the design, not solely isolated mockups.
2. Implement the feature-owned frontend surfaces, preserving current app routes and supported API contracts. **Candidate ownership allowlist:** `frontend/src/features/dashboard/**; feature-local tests/styles`. Inspect the actual repo to resolve paths; if an expected file moved, document the precise verified path. No arbitrary changes outside the feature boundary.
3. **Primary implementation targets:** DashboardPage.tsx, KPI/charts, five-book carousel, square 105-day heatmap. The approved design direction is UXR-01 Compact Study Console v1.2 + UXR-02 AppShell R2/HM-FIX + UXR-02A Variant B/R1B. Do not redesign shared foundation.
4. **Read-only/cross-task seam:** UXR-03/04/05/06/07 feature logic, global AppShell, backend metric fields. If a necessary change touches a shared/cross-feature file, record a proposed integration patch or ask for an explicit single-writer owner/coordinator decision; do not modify in two parallel worktrees.
5. No invented data or backend capabilities: preserve null/zero/UNKNOWN/error boundaries, existing operation contracts, idempotency, revision/reconciliation, user consent, and status truthfulness as applicable. Mark screenshots as `RUNNING_FRONTEND`, `ISOLATED_MOCKUP` or `SYNTHETIC_FIXTURE` accurately.
6. New implementation acceptance: actual TSX/styles changed; actual app can mount the affected route; representative functional interactions can be exercised against existing contracts or explicitly labeled fixtures; required full-resolution UI frames captured from the running frontend; feature-local build/type/browser check results documented. Full-system tests/audit remain for a later wave; do not fabricate PASS.
7. Every frontend-design Worker explicitly invokes installed `$frontend-ui-engineering`, plus relevant addyosmani skills and installed Impeccable in its own context; Astra acts as coordinator/auditor/integrator, delegates GPT-6.1 Sol Worker packages with single-writer file ownership.
8. Request `speed: fast`, `permission: full-access` via actual supported runtime controls, but still obey the file allowlist. On the exact model-capacity error, retry dispatch with a real 3s delay up to 30 times, then replace the blocked, non-running worker (max 3 replacement workers per package) without changing model or duplicating writes. Disclose unverified actual-model/speed/permission metadata.
9. No new dependencies or shadcn installation without separate approval; reuse current canonical primitives. No unapproved edits to `backend/**`, SQLite, API/DTO/OpenAPI, generated contracts, SRS/quiz/consent business semantics, main, UXR-02A frozen artifacts, `tasks/todo.md`, or shared app shell. No automatic commit/push/merge; stop for owner visual + implementation review.
10. Acceptance item previously reading `no app/frontend code changes` is now `no unauthorized code changes outside owned frontend`; any other old item only contradicted by this explicit amendment is `SUPERSEDED_BY_OWNER_2026-10-14`, **not PASS**. Add an `IMPLEMENTATION_GATE` alongside all original design AC. No existing critical visual or safety criterion is waived.

---


**Track:** English Web major final UI/UX redesign; **research/design-only task specification**, not canonical application T001–T090 or AI-orchestration development.  
**Group/route:** **G9 Dashboard**, `/`.  
**Status:** `PREPARED / NOT STARTED / BLOCKED_BY_UXR_02A_OWNER_VISUAL_SIGNOFF`.  
**Authorization (2026-10-12):** owner approved preparation of **this Markdown specification, roadmap update and Draft PR #26 description only**. Does not approve G9 image rendering, feature redesign execution, coding, local Impeccable invocation, component installs, tests/audits, final signoff or merge.  
**Hard dependency for real feature design:** UXR-00 verified final evidence → UXR-01 visual direction **owner-approved by viewing images** → UXR-02 shell/tokens **owner-approved images** → UXR-02A compact-layout/density **owner-approved images** → **separate owner approval to execute UXR-09** → G9 owner decision on actual images → UXR-10 integration and UXR-11 independent final nine-group signoff.  
**Parallel features:** UXR-03–09 may run separately authorized, isolated design execution **in parallel only after UXR-02A owner visual signoff**; preparing specs beforehand is allowed.  
**Repo:** `khanhpn308/english_web` on `design/ui-ux-research-20261012`, [Draft PR #26](https://github.com/khanhpn308/english_web/pull/26) stays OPEN/DRAFT/unmerged.  
**Global requirements:** [Full-resolution visual approval, installed Impeccable, official shadcn/ui](../docs/design/uxr-visual-approval-impeccable-protocol-2026-10-12.md).  
**Next checkpoint:** **STOP** after this prep, and seek owner approval before **preparing UXR-10 — Cross-Screen Design QA**. Do not prepare UXR-10 now.

## 1. Purpose, screen ownership and outcome

Design a compact, visually legible, **study-first daily Dashboard** that answers three questions immediately:
1. **What can I study next?** Present actionable **server-confirmed due cards** and one primary context-appropriate learning CTA, otherwise a truthful reason/alternative.
2. **How is the learning streak going?** Display server `streak.currentDays` with Bangkok-calendar `streak.asOf`; null is **unknown**, not zero or a broken streak.
3. **How have distinct exercise types gone?** Summarize flashcard self-ratings, MCQ correctness, Cloze correctness and Writing learner self-score as **different measures**, not an invented aggregate grade, AI score, book progress or streak-as-accuracy.

The design must inherit UXR-02A's **owner-chosen compact G9 composition and density contract** instead of silently re-opening it. UXR-02A produces two Dashboard variants for owner selection of the cross-screen compact precedent; UXR-09 refines and requires **a separate approval of full G9 states and actions**. Missing upstream signed visual images mean G9 execution is blocked.

In scope: `DashboardPage.tsx` information hierarchy, first-run/populated/mixed/error/refresh states; next-action/navigation to existing `/review`, `/lookup`, `/quiz/new`; truthful progress/count/empty copy; mobile focus/fit; official component proposals; server-event-driven refresh semantics and design-only affordances.

Out of scope: creating API metrics, artificial AI recommendations/personalization, learned-grade averages, date filters without backend, graphs without historic series, manipulating review schedules, computing due/streak client-side, changing SRS/quiz results, inventing streak rewards, adding future Library/Book routes or actual application React/CSS code.

## 2. Verified source contracts and authentic visual baseline

| Evidence | Source-grounded fact or limitation |
|---|---|
| `frontend/src/features/dashboard/DashboardPage.tsx` | `DashboardSummary` has exactly `dueCards: number`, `streak:{currentDays:number|null, asOf:string}`, `flashcardSelfRating:{count,averageBucket:Rating|null}`, `objectiveAccuracy:{mcq,cloze}` with each `{correct,total,attempted,accuracy:number|null}`, and `writingSelfScore:{scored,average:number|null}`. Do not invent a response field `weeklyTrend`, `progressPercentage`, `dailyGoal`, total saved vocabulary, nextDueAt, historical series or per-book completion. |
| `DashboardPage.tsx` | `GET /api/v1/dashboard`, `cache=no-store`; validates summary, guards stale competing requests, fetches on mount, `window.focus` and `vocabulary:invalidate`, and on manual `Làm mới`. There is **no source-proven 30-second Dashboard polling**. |
| `DashboardPage.tsx` | Initial loading skeleton when `data=null`; `STORAGE_BUSY` labeled syncing; other errors through real `frontend/src/shared/errors/RecoveryPanel.tsx`. Previously accepted data is **kept** when refresh errors; do not present it as freshly confirmed current state or delete the old display without an explicit design state. |
| `DashboardPage.tsx` | Due-card count from backend drives `Ôn tập ngay` when >0, otherwise `Xem hàng đợi ôn tập`. Due=0 is **no currently due cards**, not proof all saved vocabulary has been mastered nor that all time/date queues are empty. |
| `DashboardPage.tsx` | `streak.currentDays=null` shows “Chưa xác định”, not 0. Server `streak.asOf` displayed as a Bangkok-local learning calendar date; UI must not infer a current-day streak or reset after the viewer's midnight. |
| `DashboardPage.tsx` | `flashcardSelfRating.count` is **number of ratings**, `averageBucket` one of `AGAIN/HARD/GOOD/EASY` or null. UI currently calls it ordinal SRS mean; it is **not quiz correctness, cumulative mastery, a numeric percentage or a forecast of next due date**. |
| `DashboardPage.tsx` | MCQ and Cloze metrics distinct; `attempted=0` / `accuracy=null` displays no accuracy rather than 0%; objective attempted may be lower than total, correct uses server data. True 0% requires a real nonzero attempted denominator and 0 correct. |
| `DashboardPage.tsx` | Writing `scored` and nullable `average` are **learner self-assessment /4**, not AI feedback grade. Zero-scored Writing with `average=null` is unmeasured, not a computed score 0. |
| `DashboardPage.tsx` | Source `isEntirelyEmpty` checks `dueCards=0`, flashcard rating count=0, both objective attempted counts=0, Writing scored=0, **but does not include streak.currentDays**; this predicate is a screen-copy precondition, not authoritative proof no saved words, no historical learning or no unsubmitted quiz exists. Design must qualify global empty/onboarding claim and record this potential discrepancy **as source-observed logic, not runtime-verified bug**. |
| `docs/design/english-web-ui-ux-redesign-plan-2026-10-12.md` §3C and `docs/design/ui-visual-audit-2026-10-12-batch2.md` | **Two actual owner-supplied Dashboard desktop captures** dated 2026-10-12 (`20261012-064645`, `20261012-064657`) show oversized cards, long scrolling, repeated zero/unknown copy and competing CTA groups. Images exist in the **owner conversation**, not committed GitHub assets; don't invent an actual CSS viewport from image pixels. |
| `tasks/uxr-02a-layout-simplification-information-density.md` | UXR-02A already requires first-run/populated/mixed compact Dashboard full-screen images, 2 candidate layouts, 320px stress and explicit owner-approved density precedent. UXR-09 extends **G9-specific** state coverage, content composition and handoff; it does not replace or silently approve UXR-02A. |
| `docs/design/future-learning-content-architecture-2026-10-12.md` | Future Library/book/exercise progress and typed skill/exam metadata are **future extensibility only**. Leave layout growth capacity, but no active Book/Library tags, percentages, exercises, IELTS bands or routes in current G9 image claims. |

**Evidence type rule:** `CURRENT_APP_CAPTURE` only for actual retrieved owner images with source/date/viewport provenance; `SOURCE_CONFIRMED` for code/ADR semantics; `DESIGN_MOCKUP + SYNTHETIC` for proposed example statistics; `NOT_VERIFIED` for missing populated Dashboard/mobile/refresh-error screenshots. A real user screenshot of first-run does not prove how a real populated page currently appears.

## 3. Execution readiness and owner approvals (not satisfied by task creation)

Before later G9 visualization:
1. Link UXR-00 final nine-group evidence ledger and identify genuine G9 owner screenshot files/availability. UXR-00 remains **IN_PROGRESS** unless separately verified otherwise; UXR-09 does not close it.
2. Confirm exact UXR-01 owner-selected A/B brand/version images; UXR-02 approved desktop/tablet/mobile AppShell; **UXR-02A approved compact Dashboard alternatives and chosen version**. Use them as **read-only foundations**.
3. Obtain a new, explicit owner instruction to **execute UXR-09**, separate from permission to write this spec.
4. Assign a **single G9 integration lead**, independently owned overview/CTA and metric/error/mobility image workers with unique output filenames; workers cannot edit shared AppShell/tokens or other UXR feature folders.
5. Verify coordinator **and each local design worker** can read and actually use the owner's **already installed Impeccable** skill, log genuine invocation and effect on images; if inaccessible, block DONE without reinstall.
6. Inventory official shadcn primitives and approved UXR-02A density components, track existing vs proposed, without issuing install/CLI commands in this prep.
7. Define source evidence for every displayed count/denominator/streak as-of and attach a `source | approved data shape | proposed label | empty/unknown treatment | action | frame ID` matrix.

## 4. Information hierarchy and one primary action per Dashboard state

**Layer 1 / first viewport:** page title/context (do not duplicate the UXR-02 AppShell heading), one **primary safe learning CTA** if appropriate, `dueCards` and `streak` quick glance. On a true `1366×768` CSS viewport, show heading/CTA/due/streak without forced fixed-height hacks; annotate content fold from actual proposed images.

**Due>0:** primary CTA `Ôn tập ngay` → existing `/review`. A positive count is currently due cards according to server, not a global learning progress percentage. The source click handler navigates to Review; no invented direct-card ID, unimplemented smart schedule or “next due hour.”

**Due=0, other results present:** no all-history-empty onboarding; show “Hôm nay chưa có thẻ đến hạn” (Bangkok-calendar semantics as confirmed), emphasize appropriate existing secondary action `/quiz/new` or `/lookup` only if eligibility known, else a safe **review queue** link. Do not claim all study is complete just because dueCards=0.

**First-run/no measured activity:** `isEntirelyEmpty` source predicate signals zero measured activity categories, but cannot prove no vocabulary history. Show one concise invitation with **one visually primary CTA** (proposal: `Tra cứu từ mới` → `/lookup`, with honest AI dependency/consent label) and visually subordinate `Review`/`Quiz` links if meaningful; avoid separate repeated empty paragraphs or duplicated giant onboarding card.

**Streak null:** “Chưa xác định” with backend `asOf`, not an auto-reset-to-zero. **Streak=0:** genuinely zero consecutive days as computed; **streak>0:** real positive consecutive-day count. Do not invent gamified badges, achievement rewards, study goals, motivational claims or unreported “longest streak.”

**Action hierarchy:** One dominant CTA per **current Dashboard state**, not a ban on essential secondary links. Avoid repeating `Tạo bài kiểm tra` in MCQ, Cloze, Writing and global footer at identical prominence. Contextual inline links can remain accessible; no invisible or disabled link to future Library.

**Compact density:** reuse UXR-02A approved `MetricTile` / `StatSummary` contract, fewer container layers, content-driven height and readable progressive explanation. Two owner-approved layout variants from UXR-02A are **frozen**; G9 may show a scoped component-level alternative only within selected direction and with separate owner approval, not relaunch global identity decision.

## 5. Metric-by-metric data accuracy and accessible language

| Domain | Exact existing backend/source fields | Correct visible distinction |
|---|---|---|
| SRS due | `dueCards` | True `0` vs `>0`; does not equal total cards, words mastered or today-completed events |
| Learning streak | `streak.currentDays`, `streak.asOf` | `null`=unknown; 0=known zero; >0=known consecutive days; Bangkok date from backend, not browser midnight guess |
| Flashcard self-rating | `flashcardSelfRating.count`, `averageBucket` | `count=0` or bucket null = no meaningful mean; ordinal `AGAIN/HARD/GOOD/EASY` bucket is a subjective review-summary, never success rate |
| Objective MCQ | `objectiveAccuracy.mcq.{total,attempted,correct,accuracy}` | `attempted=0` / `accuracy=null` = “Chưa làm câu trắc nghiệm nào”; `correct=0, attempted>0` = actual 0% |
| Objective CLOZE | `objectiveAccuracy.cloze.{total,attempted,correct,accuracy}` | Same semantics, separately labelled; never combine with MCQ into arbitrary “average accuracy” without backend-defined metric |
| Writing | `writingSelfScore.{scored,average}` | `scored=0` or null mean = not assessed; nonnull 0–4 = learner self-score mean; not AI evaluation |

**No invented statistic:** current DashboardSummary has no longitudinal series, streak goal, card mastery percentage, note-date filter, weekly retention trend, category-weighted grade, quiz-writing AI grade, future due-day histogram, per-book completion or badge unlock. A **chart** is not automatically appropriate; omit shadcn Chart/Recharts when no actual time-series/data bins exist. A visual composition with sample data must be conspicuously **SYNTHETIC** and obey the actual DTO shapes.

**Percent and a11y:** Render MCQ/Cloze accuracy only if numeric and `attempted>0`. `accuracy=0` with attempted>0 gets a valid real `0%` and determinate progressbar; `accuracy=null` has no `aria-valuenow=0` masquerading as measured accuracy. Associate attempted/correct/total labels with the appropriate metric, not another exercise domain.

**Ordinal bucket:** `averageBucket` is a server-returned qualitative rating; do not convert AGAIN/HARD/GOOD/EASY into 25/50/75/100% numeric chart or learned mastery. If there are no ratings, show an actual no-rating state, not a fabricated AGAIN.

**Writing average:** source `toFixed(1)` display is a presentational decimal rounding of backend number, not evidence of grading precision or AI scoring. Do not imply all Writing submissions were AI reviewed.

**Empty/global semantics:** two real captured dashboard frames motivated reducing repeated `Chưa có đánh giá` text in each tile plus one global empty card. Keep independent category status without repeating a paragraph four times; global empty copy cannot claim “no vocabulary exists” unless verified by additional authoritative source, which DashboardSummary does not provide.

## 6. States, data refresh, network and UI affordances

Prepare a state matrix `GET/state | server data trustworthy? | last-known value? | primary CTA | error/recovery | focus/live announcement | screenshot ID`.

- **Initial loading**: source has no data yet, use stable official Skeleton/semantic loading status, no zero-value placeholders. Reflow avoids large blank skeletons differing radically from final compact layout.
- **Loaded first-run**: due=0, flashcard rating count=0, objective attempted=0, Writing scored=0, streak nullable and backend asOf; accessible one-global-onboarding; no invented missing saved-vocabulary claim.
- **Loaded populated**: due>0, known positive streak, separate rating/MCQ/Cloze/Writing values; one primary Review CTA, other links subordinate.
- **Loaded mixed**: due=0 but quiz and/or Writing histories nonempty; category gaps remain truthfully visible and **no global first-run treatment**.
- **Streak unknown with valid metrics**: retain measurable due, MCQ, rating etc while clearly marking streak unknown, not marking all Dashboard data unknown.
- **Objective never attempted**: MCQ or Cloze attempted=0, accuracy=null; the other objective category may have valid 0% or positive percentage; show side-by-side distinction.
- **Flashcard no rating vs saved vocabulary exists**: cannot assert number of saved words from this DTO; no global “vocabulary empty” claim.
- **API `STORAGE_BUSY` / syncing**: explicit waiting/retry, previous data marked **last known/stale** if retained, not erased or displayed as freshly validated.
- **Other API/session/validation/restore errors**: use shared `RecoveryPanel` source, with retry/read/rebootstrap appropriate to state and available handler; no unsupported automatic send, source mutation or AI permission.
- **Manual refresh, focus, `vocabulary:invalidate`**: Dashboard fetches authoritative summary; design distinguishes pending refresh, confirmed latest read and read failure. Do not promise push-live real-time updates or a 30-second polling interval.
- **After confirmed Review/Quiz mutation**: share source-confirmed event refresh semantics with UXR-05/06/07; **never** display increased streak/accuracy/changed due count solely from frontend click before backend acknowledgment.
- **Partial data and malformed response**: validation failure is read error, not false 0. The current API is one summary object; don't imply independent tile refresh/independent freshness if not actually supported.

All DIL/prototype or screenshot states must use **non-mutating synthetic fixtures**; no real demo SRS/quiz writes. UI image text “Cập nhật gần nhất” needs real source timestamp or clearly labeled proposed display from last successful read; `DashboardSummary` has `streak.asOf` but not a global API `lastUpdatedAt` field. Distinguish the two, never repurpose streak date as server-health freshness.

## 7. Mandatory owner-visible full-resolution gallery — ≥26 primary UI frames

**During later separately authorized actual UXR-09 visual execution only** produce **at least 26 original readable full-screen PNG/WebP `DESIGN_MOCKUP` images**: **13 distinct Dashboard states × desktop `1366×768` CSS viewport and mobile `390×844` CSS viewport**, with a realistic application shell and bilingual content where appropriate. Every example with illustrative counts is conspicuously `SYNTHETIC` and uses the current documented schema, not an invented API field.

| Pair | Frame state | Specific visual contract |
|---|---|---|
| DA01–02 | First-run / zero measured history | One concise onboarding/primary CTA, no four long repeated empties, null streak distinguishable |
| DA03–04 | Populated learning day | Due>0, real-valued example streak and ratings, separate exercise summaries, one dominant Review CTA |
| DA05–06 | No due cards but history exists | True zero due, nonempty quiz/writing/review stats, no “no history” message |
| DA07–08 | Streak `null` with valid other metrics | Date asOf visible, unknown not rendered as 0, legitimate known stats retained |
| DA09–10 | Streak `0` with otherwise known stats | Known zero distinct from unknown and known positive |
| DA11–12 | Flashcard rating count=0 / mean=null | No qualitative numeric chart, category-specific honest no-rating copy |
| DA13–14 | MCQ `attempted=0, accuracy=null` | No progress percentage or false 0%; Cloze can remain measured |
| DA15–16 | CLOZE measured true 0% | attempted>0, correct=0, percentage 0 is real, separate from absent MCQ |
| DA17–18 | Writing score mixed/learner mean | scored>0, backend average/4, no AI grading implied |
| DA19–20 | Initial Dashboard loading | Skeleton size mirrors compact layout, no prefilled zeros |
| DA21–22 | `STORAGE_BUSY` / sync warning | Distinct temporary block, server freshness wording, safe retry |
| DA23–24 | API read/session error after no valid data | RecoveryPanel with proper action, not an empty dashboard |
| DA25–26 | Refresh failure with retained last-good summary | Clear stale/last-known label, usable non-mutating navigation and retry |

**Beyond the 26 primary images, required additional evidence:**
1. `320×568` stress screenshot for long Vietnamese results and safe CTA, `768×1024` tablet, `1024×768` intermediary and `1440×900` full approved AppShell; cover effective 200%-zoom reflow, no horizontal clipping or focus trap.
2. A **same-state light/dark pair** of complete Dashboard screens with differentiated zero/unknown/error statuses, non-color-only distinctions and focus target visibility.
3. **At least two materially different compact G9 metric-detail / next-action micro-layout concepts** **within the already approved UXR-02A chosen visual direction**, shown as one desktop and one mobile extra frame **per alternative**. This is not permission to change globally approved shell or reselect UXR-02A cross-screen precedent.
4. Authentic before/proposed side-by-side for **the two existing owner Dashboard screenshots** only **if their real bytes/provenance are accessible**; otherwise cite screenshot names and mark `CURRENT BASELINE BY WRITTEN EVIDENCE ONLY`, never synthesize a current-app shot.
5. A legible **fold annotation** at `1366×768` showing title/due/streak/context-appropriate primary action above fold, with no unverified measured user-study or benchmark metrics.
6. Readable contact sheet **plus separate direct owner-clickable original full-resolution image links** to each state under `docs/design/uxr-09/assets/*.png|*.webp` or another owner-authorized durable destination. No tiny collage-only or scratch-only delivery.

**Metadata for every asset:** `UXR-09 | route / | screenshot ID | scenario | exact CSS viewport | theme | alternative/version | DESIGN_MOCKUP or genuine CURRENT_APP_CAPTURE | SYNTHETIC flag | timestamp | link`. A real baseline screenshot never becomes a synthetic proposed mockup through relabeling.

**Owner decision:** `gallery version/IDs/links | selected G9 detail layout | unchanged upstream direction/density | concerns | APPROVE/REQUEST_CHANGES/REJECT/PENDING | owner response/date`. Only direct owner review of actual **viewable** images constitutes approval. Revision after requests requires fresh image version and reapproval. Without full gallery, confirmed installed-skill use and explicit visual approval, UXR-09 stays `OWNER_VISUAL_APPROVAL_PENDING` (not DONE).

## 8. Impeccable — local already-installed skill, all actual workers

The owner reports [pbakaus/impeccable](https://github.com/pbakaus/impeccable) **already installed on Windows**. **Never reinstall, update, download, vendor or duplicate it** to prepare this task.

At the start of **each later authorized local UXR-09 design session**:
1. Coordinator **and each active overview/metric/responsive/a11y image worker** independently resolve **their own** local installed Impeccable directory in their harness, read the installed `SKILL.md` plus relevant command references. A README link or coordinator summary does not prove each worker has used the skill.
2. From English Web project root, execute the **installed** `<skill-base-dir>/scripts/impeccable context` **once per session**, using its available Windows `<skill-base-dir>\scripts\impeccable.cmd context` launcher if applicable. Record actual path, command, timestamp/version, response and failure; do not invent paths or repeatedly spam context calls.
3. Read installed-version guidance and selectively apply `shape/layout/distill` (daily journey, fold and duplicate tile/CTA), `clarify` (0 vs null language), `adapt` (320px/200%-zoom), `harden` (stale/read error), `critique` (independent visual hierarchy). Commands are examples subject to the installed references, **not proof of invocation**.
4. Save `role/agent ID/session | installed path/version | real context invocation/output | reference/command used | visual issue | changed design screenshot ID` for coordinator and **every** active worker in future `UXR-09-IMPECCABLE-EVIDENCE.md`. Coordinator aggregates authentic independent evidence and runs its own context.
5. If a worker cannot use installed skill, report `IMPECCABLE_NOT_ACCESSIBLE` with actual error, **do not reinstall or mark skill PASS**. G9 cannot be DONE until resolved/owner decides.
6. Skill suggestions never override backend semantics, official component restriction, UXR-01/02/02A signed visual decisions or the no-app-code scope.

**Preparing this Markdown file via GitHub does not invoke the owner's Windows-local skill.**

## 9. Official shadcn/ui-only reusable component plan (no install)

**Sole source of any missing reusable UI primitive:** https://ui.shadcn.com/docs/components. Use existing [shadcn component strategy](../docs/design/shadcn-ui-component-strategy-2026-10-12.md). Existing app has Radix-compatible **Button/Card/Dialog**, New York style, React 19/Vite 8/Tailwind 4 **without generic Preflight reset**. Reuse, do not overwrite.

Later required matrix: `G9 surface/state | exact official component name/docs URL | ALREADY_PRESENT / OFFICIAL_PROPOSED / COMPOSITION / DEFERRED | keyboard/ARIA risk | one owner`.

| Area | Official candidates (only as warranted) | Safety and truth |
|---|---|---|
| Dashboard next step and due/streak | Existing **Card/Button**, official **Badge/Separator** | One primary CTA; due=0 vs null streak independent |
| Four separated learning summaries | Existing **Card**, official **Tabs/Collapsible/Accordion** optional | No loss of objective vs subjective score distinction |
| Accuracy display | Official **Progress** only with real attempted denominator, correct ARIA `aria-valuenow` | Null ≠ 0%; never invented global progress |
| Initial load/empty | Official **Skeleton/Empty/Alert** or lightweight accessible composition | One meaningful onboarding, not repeated zero/unknown paragraphs |
| Read errors/sync | Official **Alert/Skeleton/Badge**, shared **RecoveryPanel** visual contract | Last-known label, safe retry, no inferred freshness |
| Future trends | Official **Chart**: **DEFERRED unless genuine historic series is separately specified and approved** | Current Dashboard DTO has no time series or per-book progress |

Future app-level compositions may be `DashboardActionSummary`, `DueStatTile`, `StreakTile`, `ExerciseResultSummary`, `DashboardFirstRun`, `LastKnownDataBanner`, assembled from existing/official primitives. They are *design-only suggestions*, not created React files. No third-party registry, `shadcn init --force`, `add --all`, `--overwrite`, npm installation, `components.json` edits, dependency/lockfile or Tailwind CSS changes now. A future implementation phase must be separately owner-authorized and review exact official docs/CLI diff with a single canonical primitive owner.

## 10. Future execution artifacts (NONE created in task preparation)

**Design artifact root:** `docs/design/uxr-09/`.

| Future artifact | Later required proof |
|---|---|
| `UXR-09-EVIDENCE-DATA-MATRIX.md` | DashboardSummary field, source-vs-current-screenshot coverage, metrics/status/unknown truths |
| `UXR-09-JOURNEY-ACTIONS.md` | first-run/populated/mixed next-action hierarchy, existing route handoff, correct empty copy |
| `UXR-09-METRICS-SEMANTICS.md` | due/streak ordinal flashcard/MCQ/Cloze/Writing, null vs 0 and no invented denominator |
| `UXR-09-DENSITY-RESPONSIVE.md` | UXR-02A approved precedent, viewport fold, mobile/320px/200%-zoom/a11y |
| `UXR-09-LOADING-STALE-RECOVERY.md` | GET/initial/refresh/focus/invalidation, syncing/stale/Error recovery, last-known semantics |
| `UXR-09-SHADCN-MAPPING.md` | exact official component URLs, reuse/proposed/deferred and Radix compatibility |
| `UXR-09-VISUAL-GALLERY.md` + `assets/*.png|*.webp` | ≥26 owner-viewable original full-resolution frames, variants, contact sheets and comparison |
| `UXR-09-IMPECCABLE-EVIDENCE.md` | coordinator and each actual design worker installed `context` call/impact or genuine blocker |
| `UXR-09-OWNER-DECISION.md` | actual named image/version approval and selected G9 detail layout |
| `UXR-09-HANDOFF.md` | frozen G9 visual decisions, exact UXR-02A density reference, UXR-05/06/07/08/10 integration seams |

These are **not produced now**. This task-card/roadmap/PR preparation has no real mockups, no browser preview, no local skill use, no runtime assertions and no code implementation.

## 11. Definition of Done — 22 acceptance criteria (all mandatory)

1. **AC01** — UXR-00 final evidence and actual owner-approved image versions for UXR-01/02/02A are linked; separate owner execution authorization for UXR-09 exists.
2. **AC02** — ≥26 genuine full-resolution G9 Dashboard PNG/WebP images (13 desktop/mobile pairs) plus 320px/tablet/intermediate/wide/light-dark/variant evidence and readable direct links.
3. **AC03** — Owner explicitly views and approves named G9 first-run/populated/mixed/error/next-action image version; no text-only implicit acceptance or silent UXR-02A direction changes.
4. **AC04** — Heading, contextual single main next action, due and streak above fold at actual 1366×768, without fake fixed-height hacks.
5. **AC05** — Real `dueCards=0` does not assert all words mastered; due>0 action navigates the actual `/review` route.
6. **AC06** — `streak.currentDays=null` genuinely unknown, 0 known zero, >0 known positive; actual `asOf` preserves Bangkok calendar and is not used as API freshness.
7. **AC07** — Flashcard `count/averageBucket` qualitative ordinal meaning preserved; no false correctness/percentage/forecast.
8. **AC08** — MCQ and Cloze separate `correct/attempted/total/accuracy`; `attempted=0` / accuracy=null not 0%, while true 0% with attempts shown accurately.
9. **AC09** — Writing `scored/average` shown as learner self-score /4, not AI feedback score or objective accuracy.
10. **AC10** — No combined grade or invented trends, time series, streak goal, mastered-card percentage, per-book completion or AI learning recommendation without source fields.
11. **AC11** — First-run shows one nonduplicated honest onboarding/CTA; `isEntirelyEmpty` source predicate's limited meaning does not imply no stored words or historical attempts.
12. **AC12** — Mixed-state Dashboard (due=0 but learning results present) not mislabeled as all-history-empty; category-specific no-measure states remain legible.
13. **AC13** — Compact UXR-02A approved composition remains consistent; no duplicate large Cards and competing repeated primary CTA routes.
14. **AC14** — Initial loading, storage busy, API failure, and last-good stale summary look/behave distinctly and never default to fabricated zero.
15. **AC15** — Source-confirmed refresh on mount/focus/`vocabulary:invalidate` and manual request; no fake WebSocket/30-second Dashboard polling or optimistic SRS change.
16. **AC16** — Shared error/RecoveryPanel action uses real `shared/errors` path, safe retry/local session and source-state clarity.
17. **AC17** — Mobile 390px and stress 320px, effective 200%-zoom, tablet/intermediate/wide, light/dark, keyboard and visible focus/a11y design; mockups do **not** claim WCAG runtime PASS.
18. **AC18** — Authentic prior Dashboard owner captures cited by filename; real before/new only if bytes accessible; populated/mobile baselines unverified, proposed synthetic screenshots clearly labeled.
19. **AC19** — Official-only shadcn mapping with reused Radix Button/Card/Dialog, no unnecessary Chart or new UI package/lock/component edits.
20. **AC20** — Coordinator and **every active designer** independently invoke already-installed Impeccable `context` in own local session with recorded actual impact; `IMPECCABLE_NOT_ACCESSIBLE` blocks final Done.
21. **AC21** — G9 owner approval, asset/version/handoff ledger and UXR-05 Review/06 Quiz/07 Result/08 Status interfaces documented for UXR-10 QA.
22. **AC22** — No app source, API/SQLite/DTO/SRS/consent, dependency, `components.json`, `tasks/todo.md`, tests, UXR-00 closure or PR #26 merge, and no UXR-10 preparation without a new owner instruction.

**Lifecycle:** `PREPARED → READY_FOR_EXECUTION → IN_PROGRESS → OWNER_VISUAL_APPROVAL_PENDING → DONE` **only** after upstream evidence/approval, actual ≥26 image gallery, local installed-skill per-agent proof and explicit owner review. Missing any = not DONE.

## 12. Design worker file ownership, prohibited work and stop before UXR-10

One future G9 integration lead owns consolidated state/visual gallery/Impeccable evidence/owner decision and writes `docs/design/uxr-09/*.md` (except independently numbered worker assets). A first-fold/daily-CTA designer exclusively owns `docs/design/uxr-09/assets/overview-*`; a learning-metrics worker owns `assets/metrics-*`; and an error/mobile designer owns `assets/recovery-*` and `assets/responsive-*`. Coordinator and each independently commissioned worker run installed Impeccable in **their own session**. Roadmap/Draft PR metadata have **one research coordinator owner**, not concurrent feature workers.

Read-only: UXR-00 screenshots, UXR-01 brand, UXR-02 shell, UXR-02A signed density, UXR-03–08 design folders, UXR-10 downstream (not created yet). All `frontend/**`, `backend/**`, `components.json`, package locks, generated API DTO, SQLite, launcher, tests and `tasks/todo.md` **must remain unchanged** throughout documentation and design-only research.

Explicitly forbidden: original-app UI modifications, running external AI calls or real SRS events, browser UI captures misrepresented as existing app, fabricating learner history, installing shadcn/Impeccable, premature WCAG/CI/security pass claims, altering UXR-00 status, merging PR, creating new app routes, implementing future Library/book tags or *preparing UXR-10 without owner authorization*.

**Stop condition:** after this task Markdown exists, the roadmap references it and Draft PR #26 is updated/verified, **STOP for owner's separate approval to prepare UXR-10 — Cross-Screen Design QA**. No redesign execution or screenshot production has occurred.

# UXR-10 — Cross-Screen Design QA

**Track:** English Web — major final UI/UX redesign; **design-only cross-screen quality assurance**, not canonical application T001–T090 or AI orchestrator tasks.  
**Official ID/title:** `UXR-10 — Cross-Screen Design QA`.  
**Status:** `PREPARED / NOT STARTED / BLOCKED_BY_UXR_03_TO_09_OWNER_VISUAL_SIGNOFFS`.  
**Owner authorization (2026-10-12):** Prepare this Markdown task specification, link it in the UI/UX roadmap and update [Draft PR #26](https://github.com/khanhpn308/english_web/pull/26). **No UXR-10 QA execution, visual regeneration, new runtime test, code redesign, automatic owner approval or merge is authorized by preparing this file.**  
**Repository/branch:** `khanhpn308/english_web` / `design/ui-ux-research-20261012`; PR #26 must remain OPEN / DRAFT / UNMERGED.  
**Binding protocol:** [Actual owner-viewable images, installed Impeccable, official shadcn/ui](../docs/design/uxr-visual-approval-impeccable-protocol-2026-10-12.md).  
**Downstream:** UXR-11 — Owner Sign-off & Implementation Handoff, **separate authorization**; UXR-12 remains PROPOSED, not approved.

## 1. Objective and scope

Consolidate and independently assess the **already owner-reviewed, full-resolution proposed UI designs** for all **nine existing screen groups**, verifying that the final multi-screen experience is consistent, usable and semantically safe **before final owner sign-off (UXR-11)**. This is an integrated **design review** and proposed-UI QA, **not** runtime audit of production React or proof of WCAG 2.2 AA implementation.

Scope covers: AppShell navigation/identity, responsive breakpoints, density/spacing, typography and visual tokens, official shadcn primitive mapping, shared status and empty/error/UNKNOWN patterns, consent, safe action hierarchy, data provenance, focus/keyboard/contrast **design specifications**, route-to-route continuity and future extensibility without new features.

Deliver a cross-screen coverage matrix, the actual linked images and comparison boards, independently checked violation register, precise remediation ownership, recorded reapproval/version discipline and a **GATE_READY / BLOCKED / REWORK_REQUIRED** handoff decision. Do not silently “pass” a feature because a task card exists.

## 2. Authoritative upstream evidence and formal start gate

```text
UXR-00 verified final capture/source ledger
   → UXR-01 owner-selected A/B/hybrid design images
   → UXR-02 owner-approved AppShell/foundation images
   → UXR-02A owner-approved density images
      → [UXR-03, 04, 05, 06, 07, 08, 09: feature galleries + actual owner sign-offs]
         → UXR-10 cross-screen design QA
            → UXR-11 final owner sign-off + implementation handoff
               → UXR-12 (PROPOSED ONLY; requires separate adoption)
```

Before **executing** UXR-10, check **all**:
1. UXR-00 report, baseline SHA, inventory of **actual** current-app captures, 9-group state coverage and `NOT_VERIFIED` findings; do not infer missing coverage or close UXR-00 from old task documents. Owner previously reported UXR-00 complete locally, but confirm the **actual final artifact** and provenance rather than treating repo's old `BLOCKED` copy as current proof.
2. Owner decisions for UXR-01 visual direction, UXR-02 shell and UXR-02A compact density with **selected variant/version, actual full-resolution images, decision record, date**.
3. **Each** UXR-03–UXR-09 has a completed versioned image gallery, exact individual links, task acceptance matrix, coordinator/worker Impeccable proof, source/evidence ledger, component mapping and **explicit owner feature-visual approval**. Seven prepared Markdown task files are **not** sufficient.
4. A coordinator has received **separate owner approval to run UXR-10 design QA**; today's approval covers only preparation. Missing predecessor or owner approval → `BLOCKED_BY_DEPENDENCY`, produce a **readiness gap report** but never claim cross-screen QA COMPLETE.
5. Freeze image versions by **SHA/path/version** at the start; collect all upstream approved images read-only. A replacement of any image/token/navigation pattern after approval triggers impact analysis and possible reapproval of affected G1–G9 features.
6. Assign one UXR-10 integration lead, independent visual/interaction/accessibility reviewers and a non-overlapping artifact ownership map; do **not** run two agents editing a shared results/owner-decision file.
7. For actual local QA design workers, use the **already installed Impeccable** correctly and verify official shadcn rules (§8–9); neither README links nor upstream task claims substitute for worker evidence.

**Preparation may be complete now. UXR-10 execution is intentionally blocked** while actual feature design/image approvals have not been independently verified.

## 3. Nine-group coverage matrix and version lock

One row per **route × state × viewport × theme × design version**, additionally mapped to exact `IMAGE_ID | PNG/WebP link | OWNER_APPROVAL_REF | genuine capture / DESIGN_MOCKUP | source code/ADR reference | pass/fail/not verified | issue ID`. Every row must be traceable to **a visible image**, not a non-rendered JSX file.

| Group / source of approved design | Required checkpoints for integrated consistency |
|---|---|
| **G1 AppShell** — UXR-02 | Desktop expanded/collapsed navigation, mobile Sheet open/closed, `header/nav/main` focus/skip/route semantics, all existing links, `/status#ai-consent`, current page and local-vs-AI indicator |
| **G2 Lookup/AI Preview** — UXR-03 | Compact search input, AI consent before sending, preview `NOT SAVED`, VERIFIED/UNVERIFIED/MISSING meanings/IPA, UNKNOWN original-request reconciliation |
| **G3 Search/Word Detail** — UXR-03 | Meaning/lemma filters and chips, URL/date/sort/cursor, deep link/back-return, valid/invalid/missing source, Edit entry only for VALID |
| **G4 Save/Edit Vocabulary** — UXR-04 | Date/new-vs-existing source, `If-None-Match/If-Match` UX, saved receipt, UNKNOWN non-duplication, revision-conflict draft comparison, no silent overwrite |
| **G5 Review Flashcards** — UXR-05 | Empty queue/date filter, NEW/LEARNED front, revealed bilingual back, AGAIN/HARD/GOOD/EASY only after flip, server receipt and UNKNOWN recovery |
| **G6 Quiz Builder/Runner** — UXR-06 | Consent/validation, MCQ/Cloze/Writing rubric 0–4 and null-vs-0, per-answer autosave/ETag/conflict/UNKNOWN, chosen A/B Runner navigation, submit guard |
| **G7 Results/Writing Feedback** — UXR-07 | IN_PROGRESS ≠ SUBMITTED, MCQ/Cloze nullable accuracy and BLANK, learner Writing self-score vs optional AI commentary, SRS APPLIED/SKIPPED, Feedback REQUESTED/VALIDATED/FAILED/UNKNOWN |
| **G8 Status/Consent/Errors** — UXR-08 | ACTIVE vs potential severity and UNKNOWN/no-data, bridge vs local health, grant/revoke/policy fail-closed, same-intent consent recovery, correct `RecoveryPanel` action |
| **G9 Dashboard** — UXR-09 | First-run/populated/mixed, one context-valid CTA, dueCards 0 vs history, streak null vs 0, objective accuracy null vs true 0%, Writing learner mean, stale-error vs fresh data |

**Coverage arithmetic:** The nine groups are not the same as nine pages: G2/G3 share Lookup/Search/Detail handoffs, G6 covers Builder and Runner, G8 consent dialog plus Status. Record **sub-surface** and **critical state** rows separately so a single Dashboard screenshot cannot mark the whole group “covered.”

**Approval ledger:** For each group record `task done? | selected image version | reviewer/owner response | SHA | unresolved blocking defects | upstream approved design`; if one is missing, the status is `MISSING_EVIDENCE`/BLOCKED, **not** PASS. Actual owner decision must be traceable, never extrapolated from “prepared” task status.

## 4. Cross-screen consistency review matrix (design evidence)

Evaluate the following **measurable checks** on every applicable approved group/state, with `PASS / FAIL / NOT_APPLICABLE(reason) / NOT_VERIFIED(reason)` and image anchor:

1. **Navigation/IA:** existing nine route surfaces and semantic return/deep links remain reachable; consistent labels, selected nav, sidebar/drawer, breadcrumb, mobile close/restore and AI consent anchor; future Library/Books/IELTS/TOEIC/CEFR remain future-only architecture, not clickable v1 routes.
2. **Design tokens:** identical approved brand palette, light/dark semantic roles, typography levels, spacing/rounding/shadow and canonical state colors across all feature compositions; no independent feature-by-feature palette drift. Specify pixel/token comparisons from artifact metadata rather than invented global source change.
3. **Density:** G1–G9 follow frozen UXR-02A information hierarchy; first viewport carries task/context/primary action where meaningful, no oversized blank Cards, unnecessary equal-height wrappers or wide unfilled canvases; legitimate long readings retain comfortable line length.
4. **CTA discipline:** **at most one visually dominant primary action per visible state**; essential separate consent/recovery/re-read/cancel/Save may be accessible as appropriately scoped secondary/danger actions; reject duplicate `Tra cứu`, `Lưu`, `Tạo bài` of equal weight for one transaction.
5. **Empty messages:** one explanatory empty surface for each **actual** empty scope; no duplicated queue-empty/onboarding paragraphs; preserve live region announcements and do not equate `EMPTY` with `LOADING`, `UNKNOWN` or storage fault.
6. **State vocabulary:** shared status UI expresses `IDLE/LOADING/PENDING/CONFIRMED/FAILED/UNKNOWN/DEGRADED` with human-readable Vietnamese, consistent visual severity, non-color-only labels, and correct platform request semantics, while preserving feature-specific vocabulary.
7. **Semantic values:** every measured `0` distinct from `null/unknown/not assessed`; BLANK distinct from INCORRECT; due count distinct from mastered total; ordinal ratings distinct from objective quiz percentages and learner Writing/AI feedback.
8. **Source provenance and safety:** lookup preview vs stored Markdown, VALID vs INVALID/MISSING sources, ETag/conflict, quiz draft vs terminal result, receipt-acknowledged SRS changes, consent and local/offline states cannot be presented as interchangeable UI outcomes.
9. **Progress/Charts:** show an actual percentage/progressbar **only when authoritative numerator and denominator exist** (e.g. attempted MCQ), not fictitious queue total, streak target, generation %, historical trend, book completion or AI score.
10. **Technical disclosure:** warning/permission information stays reachable at point of risk; raw ETag, requestId, provider/model and metrics progressively disclosed (not removed or exposed as primary learner copy), with keyboard-accessible `details`/Accordion.
11. **Language and microcopy:** precise Vietnamese role/label/error/empty/CTAs, equivalent wording for same action across routes; distinguish `Thử lại` safe reads, `Kiểm tra kết quả` UNKNOWN mutations, `Đọc lại` authoritative refresh and `Khởi chạy lại phiên` bootstrap.
12. **Components:** `ALREADY_PRESENT/OFFICIAL_PROPOSED/APP_COMPOSITION/DEFERRED` match existing Radix/new-york/Tailwind-4 component strategy, with direct official shadcn docs links, one future shared component owner and no unapproved primitive forks.

Avoid declaring a check PASS where there is only a source-only prediction and **no approved image**. UI visual consistency can be assessed from images, while tab order/ARIA/contrast performance require interactive/rendered test evidence later; label those as **DESIGN_SPEC_CHECKED / RUNTIME_NOT_TESTED**.

## 5. Cross-feature continuity / risk transition checks

Create a traceable **continuity table** `journey | source state | action | target screen | required preserved identity/URL/draft | visual handoff | confirmed vs pending | before/after image links | issue` for **at least 12 journeys**:

1. Dashboard due>0 → Review due card; confirmed rating → fresh Dashboard data, not optimistic due/streak.
2. Dashboard first-run → Lookup; AI consent gate → explicit separate Lookup request, no grant-auto-send.
3. Lookup PREVIEW → SavePreview; no false “đã lưu” before Markdown/source receipt.
4. SavePreview source invalid/missing or `UNKNOWN` → safe read/reconcile, never new duplicate Save.
5. Search query/filter/cursor → Word Detail → `returnTo` with original Search URL intact.
6. Word Detail `VALID` source → Edit → revision conflict → preserved draft/re-read, no silent overwrite.
7. Review front → reveal → four subjective SRS ratings → pending/UNKNOWN/confirmed next-card state.
8. Quiz Builder permission/validation → creation UNKNOWN → same-original-operation result → Runner.
9. Quiz Runner MCQ/Cloze/Writing draft → pending/ETag conflict/UNKNOWN → submit guard, no unsaved submission.
10. Quiz Runner `SUBMITTED` → Results; `IN_PROGRESS` returns Runner with no answer-key leak.
11. Result Writing selfScore → optional AI Feedback consent → REQUESTED/FAILED/VALIDATED; no AI grade substitution and no automatic request after grant.
12. Status policy STALE / revoke UNKNOWN → blocked AI action, yet local saved Search/Review remains available if local API healthy.
13. Shared RecoveryPanel error action types `RETRY/RECONCILE/REBOOTSTRAP/RELOAD/UPDATE_CONSENT` across G2/G4/G5/G6/G7/G8 have consistent **safe** visible outcome and accessible focus.
14. Mobile AppShell Drawer → nested route → browser back / status consent anchor; focus and breadcrumb consistency.

There are **14 specified journeys; inspect all 14**, not merely a sample. Missing source or target image is an explicit blocker/missing-coverage item. Do not simulate a mutation to “test” a static design.

## 6. Responsive, focus, visual-accessibility and theme audit

**Required coverage by actual approved/derived image metadata:**
- **Desktop:** `1440×900`, `1366×768`, **intermediate** `1024×768`, **tablet** `768×1024`, **mobile** `390×844`, **narrow** `320×568` CSS px. If an upstream task lacks a particular size, record **`NO_FRAME` / request targeted remediation**; a 1917px owner PNG width does *not* automatically mean 1917 CSS px.
- **Light and dark:** verify selected tokens, warnings, borders, chart/progress roles only where valid, inactive vs unknown and visible focus on **both themes**; mark unsupplied combinations `NOT_VERIFIED`, not invented PASS.
- **200% zoom/reflow plan:** at effective narrow content widths inspect long Vietnamese technical/policy text, word examples/IPA, multiline Writing, Search filters, four SRS rating buttons, scroll and sticky bars, dialog viewport fit and no ordinary horizontal overflow. Static screenshots can prove pictured composition, **not actual browser zoom behavior**.
- **Keyboard/focus contract:** route `main/h1`/skip link, `aria-current`, Search/Review date label, lookup input error associations, card flip-to-rating focus, Runner MCQ radio/rubric/unknown drafts, consent Dialog trap/Escape/return, dynamic recovery `role=status/alert` and image vs interactive evidence. No keyboard runtime test → `SPEC_ONLY`, not PASS.
- **A11y non-color semantics:** VERIFIED/MISSING, MCQ status, source INVALID, active alarms, error/unknown, SRS and consent can't rely solely on red/green. Text labels and distinguishable shapes/focus targets are visible in screenshots.
- **Quantitative design QA:** record actual checked `viewport | frame | visible primary CTAs count | ordinary horizontal overflow visible? | first-fold action visible? | critical warning hidden? | duplicate empty blocks count | label contrast design-risk`. No invented measured contrast ratios, Core Web Vitals, latency, WCAG 2.2 AA compliance or motion test PASS.
- **Privacy/security:** remove secrets, cookies, personal data, provider tokens and real learner records from proposed image packets; synthetic fixtures must be labeled. A screenshot is not a security test.

Output a **per-group six-viewport × two-theme coverage grid**, with states/screenshot IDs and honest `NOT_REQUIRED` only with a documented source reason. Full pixel-perfect images for each state/viewport pair are **not** automatically required if existing approved responsive variants genuinely demonstrate the same pattern, but **all missing critical states** must get a targeted remediation request and relevant new images before pass.

## 7. Owner-visible UXR-10 QA gallery and problem evidence

UXR-10 may **reuse existing owner-approved G1–G9 image originals** (read-only) to avoid duplicating generation and violating prior signed variants. Nonetheless UXR-10's own deliverable must be a **directly viewable comparative image package**, not merely a spreadsheet/text assessment:

1. **18 cross-screen comparison boards:** one **desktop (1366×768)** and one **mobile (390×844)** board for **each G1–G9**. Boards link original full-resolution feature images and highlight equivalent header/nav/actions/states. A board can place two or more existing source images side by side with annotations; label resulting **QA_COMPOSITE** and link all original approved images. Do not call a composite a new current-app capture.
2. **At least 6 cross-feature continuity comparison boards**, grouped around (i) Dashboard→Review, (ii) Lookup→Save/Edit, (iii) Search→Detail→Edit, (iv) Quiz Builder→Runner→Result, (v) Result→AI Feedback/Consent, (vi) Status/Consent→feature recovery. Each board shows before/after state image IDs, relevant warning/CTA/focus consistency and precise mismatch annotations.
3. A **nine-group full-screen contact sheet** including all selected variants and **individual original full-resolution PNG/WebP links**; openable owner-visible file references under `docs/design/uxr-10/assets/` (QA boards) and approved upstream galleries (originals).
4. Genuine `CURRENT_APP_CAPTURE` from UXR-00 may be referenced only if file/provenance exists; all derived QA boards have explicit `QA_COMPOSITE`; any synthetic cases remain `DESIGN_MOCKUP/SYNTHETIC`. Every image includes `group | route/state | viewport | theme | upstream task/version | approval ref | board issue IDs | asset URL`.
5. If a required image or signed variant is missing, **do not manufacture it**, mark `BLOCKED_MISSING_IMAGE` and send the owning feature worker to render/version it with owner reapproval. A board without original sources cannot be counted.
6. Generate visual **before → correction proposal** overlays for material conflicts only on isolated QA copies; never overwrite feature-approved images. The owner must see and approve any substantive change before the corrected version replaces a frozen design.
7. Each QA report/board must be actionable: ID, source and target screenshot, observed design mismatch, source-state safety impact, severity, suggested remedy, target owner and acceptance proof. No generic “improve consistency”.

**QA is not UXR-11 owner sign-off:** UXR-10 may recommend `READY_FOR_UXR11` but must not invent an owner approval or mark the final nine-group design approved by itself.

## 8. Real use of the already-installed Impeccable skill — per agent

The owner states [Impeccable](https://github.com/pbakaus/impeccable) is **installed on Windows**. **Do not reinstall, upgrade, copy/vendor or download it.** In any later **owner-authorized local UXR-10 design QA session**:

- Coordinator and **every active independent cross-screen reviewer/designer** independently locate installed skill in **their own harness**, read local `SKILL.md`/references and run the installed `<skill-base>/scripts/impeccable context` **once per session** from the repository root (Windows `scripts/impeccable.cmd context` when present). Record real path/version/time/result; do not assert that GitHub README reading equals invocation.
- Select installed-version guidance appropriate to `critique` (cross-screen visual comparisons), `layout`/`distill` (density/repeated CTAs), `adapt` (mobile/zoom), `clarify` (shared Vietnamese microcopy), `harden` (unknown/consent/error) and `shape` (journey continuity). Use independent critique only when supported, and **do not spam every verb**.
- Log `agent ID/role | harness | installed SKILL path/version | context command/time/outcome | reference/command | inspected gallery version | finding/issue ID | changed QA board/screenshot ID` in `UXR-10-IMPECCABLE-EVIDENCE.md`. The coordinator logs its own real call, not a substitution for worker evidence.
- If unavailable, report `IMPECCABLE_NOT_ACCESSIBLE` with real error/needed user action; do not reinstall or claim a skill-based QA PASS. The mandatory acceptance gate remains blocked until resolved.
- Skill suggestions cannot override existing owner-approved global theme/shell, backend semantics, missing-data honesty, consent privacy, offline behavior or official-only components. Scope is **read-only source and design artifacts**, write only UXR-10 QA outputs.

**This GitHub task-preparation commit does not access or run the owner's local skill.**

## 9. Official shadcn/ui component compliance and ownership

Only propose missing reusable primitives from **https://ui.shadcn.com/docs/components**, consulting [current strategy](../docs/design/shadcn-ui-component-strategy-2026-10-12.md). Existing `Button/Card/Dialog` on Radix, New York style, React/Vite/Tailwind 4 and no-Preflight CSS baseline remain canonical. Do **not** infer a component is already installed because the official catalog lists it.

Produce an integrated matrix `component name | official component docs URL | tier 1 primitive / tier 2 app composition / tier 3 feature composition | existing/proposed/deferred | used by G# and screenshot ID | keyboard/focus constraints | single future code owner`.

Flag: competing implementations of Badge/Alert/Field/Input, duplicate status components under different features, inconsistent Dialog trap/return, mismatched Sidebar/Sheet breakpoints, unsupported Chart without history, mistaken numbered Pagination when API offers only a cursor, or a Progress bar when denominator is null. Distinguish **design suggestions** from later separately approved installation plans. Reject copied dashboards/community registries, unapproved Base UI mix, shadcn `init/add/--overwrite`, dependency/lock/CSS/config changes in the design-only phase.

Any necessary shared design-token/primitive change requires UXR-02/UXR-02A design-owner mediation and reapproval impact record; **UXR-10 must not edit prior approved component or image sources**. Future Library/Books/Chapters/Lessons/IELTS/TOEIC/CEFR concepts are architectural seams, not live UI or new navigation routes.

## 10. Future execution deliverables and artifact ownership

**Owned root:** `docs/design/uxr-10/` for later design QA execution. All named files are **future deliverables**; the task-card preparation creates none of them.

| Artifact | Measurable expected content | Exclusive writer |
|---|---|---|
| `UXR-10-READINESS-AND-VERSIONS.md` | UXR-00/01/02/02A gates, seven feature approvals/actual gallery links, frozen SHA, blocked prerequisites | integration lead |
| `UXR-10-NINE-GROUP-MATRIX.md` | 9 groups and subsurfaces × state/route × 6 viewport × 2 theme coverage and source evidence ID/status | integration lead |
| `UXR-10-CROSS-SCREEN-CHECKLIST.md` | checks §4 with PASS/FAIL/NOT_APPLICABLE/NOT_VERIFIED, screenshot proof and consequences | interaction/visual critic draft; lead consolidates |
| `UXR-10-JOURNEY-CONTINUITY.md` | **14** specified feature transitions, preserved URL/draft/identity and status safety across routes | interaction reviewer |
| `UXR-10-RESPONSIVE-A11Y-RISK.md` | reflow/320px/200%, light/dark, keyboard/focus/ARIA design-only evidence and deferred browser tests | accessibility reviewer |
| `UXR-10-SHADCN-OWNERSHIP.md` | all components used/proposed, official URLs and shared future code owners, no CLI calls | component specialist |
| `UXR-10-VISUAL-QA-GALLERY.md` and `assets/qa-*.png|webp` | **18 group boards + ≥6 continuity boards** with original image links, issue IDs and provenance | gallery lead |
| `UXR-10-ISSUE-REGISTER.md` | severity, reproduce-from-image, implicated groups/screens, owner, approved remediation evidence/status | integration lead |
| `UXR-10-IMPECCABLE-EVIDENCE.md` | coordinator+each worker actual installed skill invocation/results and issue/image impacts | integration lead |
| `UXR-10-QA-DECISION.md` | `BLOCKED/REWORK_REQUIRED/READY_FOR_UXR11` recommendation, evidence metrics, no owner-signoff substitution | integration lead |
| `UXR-10-HANDOFF-TO-UXR11.md` | selected visual versions, approved change exceptions, unresolved risks, UXR-11 explicit owner decisions | integration lead |

**File ownership:** QA workers write only isolated drafts/scratch and disjoint `assets/qa-g1-*` to `qa-g9-*` or `assets/qa-flow-*` prefixes; **one integration lead** writes consolidated QA decision/issue register/handoff. UXR-03–09 approved galleries, UXR-01/02/02A foundation, UXR-00 screenshots and the cross-task policy are **strictly read-only**. Shared roadmap and PR metadata have a **single research coordinator**, not QA workers. Avoid repeated source-file reads where a reliable upstream evidence matrix exists.

## 11. Acceptance criteria / Definition of Done (24 auditable checks)

UXR-10 design QA can be marked DONE **only if all are satisfied**; a missing prerequisite is **BLOCKED**, an unresolved material design defect is **REWORK_REQUIRED**, not an implied PASS:

1. **AC01:** UXR-00 final evidence/provenance verified; owner-selected UXR-01, 02, 02A visual decisions linked with version and original full-size images.
2. **AC02:** All **seven** UXR-03–09 tasks have actual owner-approved, versioned design image sets, matrix/handoff and authenticated approval references, not merely prepared Markdown.
3. **AC03:** UXR-10 execution has its own separate owner permission, QA baseline image SHA/version freeze and a single accountable integration owner.
4. **AC04:** G1–G9 and all main sub-surfaces/routes have a grounded state/viewport/theme mapping to actual image IDs and provenance.
5. **AC05:** §4 design consistency checks are evaluated for each applicable group with `PASS/FAIL/NOT_VERIFIED/N/A` and actual image evidence; no default “PASS”.
6. **AC06:** 6 breakpoints × 2 themes matrix exists per group; absent frame and 200%-zoom/browser testing boundaries are explicitly noted, not hidden.
7. **AC07:** **18 owner-viewable cross-screen G1–G9 desktop/mobile comparison boards** with direct original approved image links, version and context.
8. **AC08:** **≥6 continuity boards** cover six §7 flows; all **14 §5** feature transitions documented with before/after images or explicit blocker.
9. **AC09:** Genuine screenshot vs mockup vs QA composite vs source-only states remain correctly labeled; no fake current-app baseline or real data.
10. **AC10:** G1 shared typography, palette, themes, spacing, navigation and 320px/mobile drawer continuity match frozen UXR-01/02/02A.
11. **AC11:** All applicable screens have **≤1 visually dominant primary CTA** per state and no duplicated visible global empty/unknown/error messages while retaining essential warnings/accessibility.
12. **AC12:** `0/null/UNKNOWN/PENDING/FAILED/CONFIRMED` and `BLANK/INCORRECT` semantics are consistent without invented denominators, queue percentages or master grades.
13. **AC13:** G2 preview≠saved, G4 conditional source/ETag and non-destructive conflict, G3 deep links/source validity and G5 rating acknowledgment agree across handoffs.
14. **AC14:** G6 per-answer/submit guards and G7 terminal-only keys/feedback/self-score/SRS effects remain consistent; no wrong-score leakage in preterminal mockup.
15. **AC15:** G8 consent fail-closed, `#ai-consent`, permission vs bridge, same-intent UNKNOWN recovery, and local API vs AI outage semantics consistent with G2/06/07.
16. **AC16:** Severe ACTIVE warnings, source-invalid and operation-unknown recovery visibly prioritized; raw metadata progressively disclosed, not removed; safe actionType/handler interface documented.
17. **AC17:** 320px/390px/mobile/tablet/intermediate/wide legibility, long EN/VI content, label reachability and responsive layout are assessed with exact screen IDs and meaningful gaps.
18. **AC18:** Keyboard/focus, semantic landmarks, dialogs, live regions, aria/contrast/reduced-motion risks reviewed as **design evidence only**; **no WCAG or runtime PASS claimed** without real interactive tests.
19. **AC19:** Every missing reusable primitive maps to an exact official shadcn URL, Radix-compatible classification and designated future code owner, with no installation.
20. **AC20:** Coordinator and every active QA design reviewer record real installed Impeccable SKILL/context invocation and used critique findings; unavailable blocks skill acceptance.
21. **AC21:** Every material mismatch has an issue ID, severity, offending asset link, accountable owner, precise fix and validation/reapproval path.
22. **AC22:** No unresolved material `P0/P1` design issue is silently waived; any material change to an owner-approved feature version is re-rendered and **reapproved by owner** before QA success.
23. **AC23:** Cross-group owner packet, selected latest images, decision/outstanding risks, handoff and `READY_FOR_UXR11` recommendation delivered; **UXR-11 itself still requires distinct final owner signoff**.
24. **AC24:** No `frontend/**`, `backend/**`, API/SQLite/DTO, dependencies, CSS, `components.json`, `tasks/todo.md`, tests, UXR-00 retroactive closure, app redesign or Draft PR #26 merge.

**Lifecycle:** `PREPARED → READY_FOR_EXECUTION (all images+owner gates+new authorization) → IN_PROGRESS → QA_REWORK_REQUIRED or QA_EVIDENCE_BLOCKED or READY_FOR_UXR11 → DONE` after all ACs and evidence. A `READY_FOR_UXR11` QA recommendation **is not final product design approval**; UXR-11 and any later coding remain separately gated.

## 12. Explicit exclusions, conflict escalation and stop before UXR-11

- **Do not execute QA now**: no worker dispatch, no local browser/Playwright, no A/B image generation, no accessibility/contrast automated test, no live API mutation and no claim that approved UXR-03–09 galleries currently exist just because their task files exist.
- **No redesign implementation:** no changes to React/CSS/components, backend, consent, SRS, quiz scoring, Markdown provenance, runtime policy, local storage, packages/lockfiles or future features; no shadcn CLI installation; no Impeccable reinstallation.
- **No arbitrary retroactive approvals:** even if the owner reports UXR-00 DONE locally, verify actual UXR-00 artifact; if a feature has no owner-signed gallery, document `BLOCKED` and return responsibility to that feature.
- **No PR merge:** keep research Draft PR #26 OPEN/DRAFT, do not merge `main` and do not modify canonical `tasks/todo.md`.
- **Issue resolution:** route G1 tokens/navigation to UXR-02; density to UXR-02A; G2/G3 to UXR-03; G4 to UXR-04; G5 to UXR-05; G6 to UXR-06; G7 to UXR-07; G8 to UXR-08; G9 to UXR-09. A cross-owner dispute goes to research coordinator and owner for an image-version decision; QA never overwrites feature work.
- **Handoff to UXR-11:** provide nine-group linked full-resolution QA gallery, owner-approved upstream design versions, issues/risks/waivers and official-component ownership. UXR-11 must explicitly ask owner for **final nine-group image sign-off** before implementation planning/handoff can be approved.
- **UXR-12:** Proposed planning task only, cannot begin from this document without a later explicit owner decision.

**Current preparation ends after this file is committed, the roadmap references it, Draft PR #26 describes it and the changes are verified. STOP and ask owner permission to prepare UXR-11.**

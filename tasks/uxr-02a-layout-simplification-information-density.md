# UXR-02A â€” Layout Simplification & Information Density

**Track:** English Web UI/UX research/redesign; distinct from application T001â€“T090 and AI orchestration.
**Priority:** P0 mandatory cross-screen density and layout design gate.
**Status:** DONE / OWNER_APPROVED / PUBLISHED.
**UXR02A_STATUS:** DONE / OWNER_APPROVED / PUBLISHED.
**UXR02A_REVIEW_STATE:** OWNER_VISUAL_APPROVAL_APPROVED — Variant B / UXR-02A-R1B / A12 square geometry.
**Approval scope:** The 2026-10-14 owner instruction authorizes UXR-02A design execution and isolated preview production. It does not authorize application code modification, production implementation, final design approval, commit, push or merge.
**Hard dependency:** UXR-00 verified evidence handoff â†’ UXR-01 owner-approved visual direction â†’ UXR-02 owner-approved AppShell + foundation visuals â†’ **UXR-02A**.
**Unlocks:** UXR-03â€“UXR-09 **design execution**, in parallel and in independently owned areas, **only after the owner explicitly approves UXR-02A visual outputs and handoff**. Preparing the later task descriptions is allowed independently of execution gates.
**Branch/PR:** `design/ui-ux-research-20261012`; [Draft PR #26](https://github.com/khanhpn308/english_web/pull/26); no merge.
**Binding cross-task policy:** [Mandatory visual-approval / installed Impeccable / official shadcn protocol](../docs/design/uxr-visual-approval-impeccable-protocol-2026-10-12.md).

## 1. Objective and scope

Turn approved AppShell/tokens into a concrete, **owner-visible, screenshot-backed cross-screen compact-layout specification**. Remove redundant empty messages, decorative/oversized Cards, repeated competing primary CTAs and visible operator diagnostics that overwhelm learning tasks **without deleting data, controls, accessibility affordances, safety notices or product functionality**.

**Principal design prototypes (not application implementation):**
- **G9 Dashboard:** first-run/zero-history, active learning/populated, mixed/no-attempts and unknown/stale/degraded states. Give the learner one clear next action and concise due/streak/result summary, preserve all existing metric meanings.
- **G5 Review:** compact date-filter toolbar, one visible empty-queue message in the empty state; full queue/reveal/rating later remains UXR-05 ownership. Retain live-region announcements and honest pending/unknown outcomes.
- **G8 Status + Consent:** readable local-study/AI summary first, prominent consent entry and active alarms, diagnostics behind explicit accessible disclosure without hiding real errors; complete consent details and interaction implementation remain UXR-08 ownership.
- **G2 Lookup idle** and **G6 Quiz Builder:** set **reusable design examples** for compact input/composer and aligned one-primary-CTA form, without taking over UXR-03/UXR-06 feature flows.
- **G1 Shell, G3 Search/Detail, G4 Save/Edit, G7 Results/Feedback:** publish layout/density/CTA/progressive-disclosure contracts for later feature designers; do not assert unobserved visual defects. The UXR-02 approved shell/navigation design is **not** re-opened here.

**Outcomes must be evidenced by actual composed UI images** so the owner can understand how Dashboard, Review and Status/Consent will look before approving. Pure prose, Markdown, ASCII diagrams or component lists **never** satisfy the visual gate.

## 2. Current state and evidence provenance

- **UXR-00 status:** reconciled from `artifacts/uxr00/final/UXR-00-REPORT.md` as `PARTIAL_WITH_EXPLICIT_BLOCKERS`; the handoff is available and its evidence gaps remain carried forward. Do not modify/restart/mark DONE in this task.
- **UXR-01 status:** reconciled as `DONE / OWNER_APPROVED / PUBLISHED` from `docs/design/uxr-01/UXR-01-DESIGN-DECISION.md`.
- **UXR-02 status:** reconciled as `DONE / OWNER_APPROVED / PUBLISHED` with approved foundation `UXR-02-R2 + HM-FIX` from `docs/design/uxr-02/UXR-02-APPROVAL.md` and `UXR-02-HANDOFF-TO-02A.md`. Earlier wording in this task that said the UXR-02 visual sign-off was missing is stale historical preparation text; it is preserved below only as historical evidence.
- **UXR-02A execution:** owner authorization is now present in the current instruction. UXR-02A is `IN_PROGRESS`; owner visual approval of the resulting packet remains a later gate.
- Actual owner desktop screenshots: Dashboard previously reviewed (oversized metric Cards, multiple repeated actions and global empty-state footer); batch-2 captures Review empty, Status with AI consent far down the page, Lookup idle and Quiz Builder. These are **partial current-UI evidence**, not approval or evidence of full nine-screen visual coverage.
- **VIS-001â€“005** establish Status alarm/readiness/diagnostics/consent hierarchy concerns, **VIS-006â€“007** Review duplicate empty and date locale observation, **VIS-008** Lookup idle large-card issue, **VIS-009** Quiz Builder width/alignment, **VIS-010â€“011** shell/large-card consistency. Do not describe them as observed backend failures or independently proven accessibility defects.
- The source in `DashboardPage.tsx` exposes `dueCards`, nullable `streak.currentDays`, flashcard self-rating summary and separate `objectiveAccuracy.mcq`, `objectiveAccuracy.cloze` and writing summary. Source evidence supports preserving these distinct metrics; it does **not** establish that all unknown values equal zero.
- `ReviewPage.tsx` has URL `noteDate` filtering and rating phases `loading/ready/empty/error/submitting/unknown`, durable operation reconciliation; `StatusPage.tsx` holds alerts, storage/source/AI bridge/offline/metrics/runbook and consent surfaces. These contracts constrain the proposed layout.

Use `CURRENT_APP_CAPTURE | SOURCE_CONFIRMED | SYNTHETIC_RENDERED/DESIGN_MOCKUP | NOT_VERIFIED` labels. UXR-00 findings arriving later must be traceably reconciled before *execution*, without rewriting observed issues as fabricated results.

## 3. Preconditions / dependencies / start checklist

Formal execution begins **only** if:
1. UXR-00 final evidence matrix and honest gaps/blockers (with screenshot provenance) are available.
2. UXR-01 owner has selected the direction via comparable full-resolution A/B images; approval reference and version exist.
3. UXR-02 completed its owner-visible **AppShell desktop/tablet/mobile screenshots** and obtained explicit owner approval of its foundation version: sidebar/nav, tokens, typography and responsive rules. UXR-02's acceptance and handoff file are readable.
4. The owner has separately authorized UXR-02A **execution**, beyond the current approval to write this brief.
5. Single owner for cross-screen density contract and screenshots has been assigned; workers agree on frozen UXR-02 tokens/navigation. No agent can independently overwrite shared foundation work.
6. The **installed local Impeccable** skill is discoverable for the coordinator and each design worker. They read the installed `SKILL.md` and invoke its real `context` launcher in their own session (see Â§6). Failure to access is logged `IMPECCABLE_NOT_ACCESSIBLE` and prevents a false DONE claim; do **not** reinstall/update.

## 4. Detailed work packages

### 4.1 Baseline, user tasks and a common evidence matrix

Build a ledger with columns:

`group | route/state | current screenshot path OR SOURCE_ONLY | viewport and theme | baseline finding ID | screen's primary job | existing primary/secondary CTA count | repeated empty/technical content | proposed change | invariant | approval status`.

- Identify **one intended primary learning/user action for each screen and state**, not a hard-coded global action. When a state forbids an action (unknown mutation, revoked consent, missing valid data), provide an honest status and safe recovery rather than a fake enabled CTA.
- Create a nine-group **first viewport / second-level detail / critical exception** density map. Show what stays visible, what enters a labeled disclosure and what must never be hidden.
- For existing screenshots, compare against those exact states; source-only groups are design hypotheses until UXR-00 adds rendered evidence.
- Any measurements (number of prominent CTAs, vertically repeated empties, visible regions, screenshots' viewport dimensions, vertical scroll extent) must be based on **explicit annotated screenshots or proposed image frames**; don't invent live DOM size/performance or user-study timings.

### 4.2 Dashboard (G9) â€” representative compact design and semantics

Design at least **two candidate compact compositions inside the already approved UXR-01 visual identity**, for explicit owner selection **without re-opening the identity decision**. Each must show:

1. **First-view priority:** one page purpose/title, one next learning action only where data permits, due-card count and streak glance metrics; optional lightweight local readiness statement. On a `1366Ã—768` CSS-pixel concept, heading, next action (or reason none is safe), and due/streak summary must appear without initial scroll; no fixed-height hack and record design viewport.
2. **Compact metrics:** one reusable app-level `MetricTile` or `StatSummary` composition, content-sized cells, minimal padding, readable label/value/support copy; no uniform tall empty cards just to balance a grid, no Card-inside-Card.
3. **Exact retained groups:** flashcard self-ratings, MCQ objective correctness, Cloze objective correctness and writing self-score/learning result, with group labels intact. Display details in compact aligned rows, Tabs/Collapsible/Accordion as appropriate **without concealing data necessary for decisions**.
4. **First-run** when all history is truly empty: **one** visible global onboarding/empty explanation and **one** primary CTA; do not repeat 'chÆ°a cÃ³ dá»¯ liá»‡u' prose in every metric. Show `0` only for actual authoritative zero; `â€” / chÆ°a cÃ³ lÆ°á»£t` or `UNKNOWN` for nullable/no-evidence values. The source's existing first-run predicate must be checked before using `no history`.
5. **Populated**: dueCount >0, known streak and at least two different learning result types. Avoid repeated `Ã”n táº­p ngay`/`Táº¡o bÃ i kiá»ƒm tra` buttons across tiles and footer; secondary destination links may remain as visually subordinate contextual links.
6. **Mixed partial data**: dueCards=0 with quiz results present, streak=null, one objective category `attempted=0`; this is **not** an all-history-empty state. Contextual empty labels are allowed and independent valid stats remain visible.
7. **Error/loading/stale:** skeleton or loading before authoritative data, `NOT_READY`/`DEGRADED`/invalid API response/unknown without converting it to zero; visible retry/status path, truthful uncertainty, no personalized or fabricated trends.
8. **Focus/reading:** screen hierarchy `h1/h2`, keyboard-reachable disclosures/actions, long Vietnamese metric labels, 200% zoom and screen reader names. Design must not assume numerical streak when `currentDays=null`.

**Candidate comparison criterion:** A/B compact composition scored for information hierarchy, clarity, number of prominent CTA duplicates, correct empty/unknown semantics, viewport fold, readable mixed-content and mobile reflow. The owner's chosen compact layout becomes a reusable **cross-screen density precedent**, not automatic approval of UXR-09's final dashboard feature specification.

### 4.3 Review (G5) â€” compact empty queue and safety

- Place note-date filter, `Táº¥t cáº£ ngÃ y` reset and relevant queue summary in a single **slim, accessible toolbar**; preserve URL `noteDate` semantics/back/forward, labels, validation and date locale ambiguity.
- When queue is truly empty, show **exactly one visible empty explanation**/useful next action. The status/ARIA live region stays present and accessible but does not reproduce duplicate visible prose. Do not hide storage/session errors in an empty state.
- Separate `EMPTY`, `LOADING`, `ERROR`, `UNKNOWN` and `PENDING REVIEW`; during an unknown review operation disable any misleading second rating, show `Kiá»ƒm tra káº¿t quáº£` when valid, keep underlying intent and preserve the same-event idempotency/reconciliation contract.
- Use design previews of **empty** (primary gate), and **pending/unknown** (critical exception). For a populated flashcard, specify the layout envelope and rating button target-size/focus rule, leaving actual flip/back/rating content and full SRS design to **UXR-05**.
- Native date input remains an accepted option; switching to official shadcn Date Picker is **a proposal requiring keyboard/locale/ISO-contract rationale**, not a visual bug fix already proven.

### 4.4 Status and AI permissions (G8) â€” progressive disclosure without concealment

- First visible region: **Local learning readiness** and **optional AI readiness** separately, with explicit `ACTIVE/INACTIVE/UNKNOWN` alert activity, `READY/DEGRADED/NOT_READY/UNKNOWN` overall condition, and a prominent **AI permission / policy** link to `/status#ai-consent`. Don't imply failed AI bridge blocks local review/search.
- **Active critical alarms** and critical privacy/consent information must stay visible and understandable in default view; severity of a *hypothetical* alert must not look like an actual triggered outage.
- Put verbose storage/source counts, offline matrix, bridge implementation detail, local p50/p95/p99 metrics, runbooks and technical revisions in **labeled Accordion/Collapsible sections**; ensure the full facts and exact status codes remain discoverable by keyboard and assistive technology.
- Show illustrative `REVOKED`, `NOT_GRANTED`, `STALE/UNKNOWN`, and `DEGRADED` appearances without granting/revoking anything. Consent state is server-authoritative; fail-closed language, true policy disclosure, ongoing in-flight request warning and revoked-but-in-flight semantics are never truncated into a deceptive badge.
- The deep link `#ai-consent` must locate the right content and have a design-level focus/scroll behavior plan, including collapsed sections, mobile drawer and no obscured focused controls. Detailed dialog interactions remain UXR-08 ownership.

### 4.5 Cross-screen density rules for G1â€“G9

Publish a matrix defining, for each group, `primary action | essential above fold | secondary/advanced | critical always-visible state | official component candidate | owner/next task`:

| Group | Standardized design concern | Feature-design owner |
|---|---|---|
| G1 AppShell | Use **UXR-02-approved** header/sidebar/title; do not repeat another large title within screen content | UXR-02; UXR-02A consumes |
| G2 Lookup/Preview | Compact idle term Input+CTA, short AI disclosure; no empty result Card until result exists, no pretending preview is saved | UXR-03 |
| G3 Search/Detail | Basic search visible, advanced filters accessible and active filters indicated; provenance never silently hidden | UXR-03 |
| G4 Save/Edit | Draft/save confirmation primary; technical IDs progressive; unsaved/conflict statuses visible and recoverable | UXR-04 |
| G5 Review | Slim date filter, one empty queue view, focused study envelope, pending/unknown explicit | UXR-05 |
| G6 Quiz Builder/Runner | Compact builder alignment and verified count summary; runner long questions/writing never crushed by density targets | UXR-06 |
| G7 Results/Feedback | Summary first; objective/self/AI advisory scores visibly separate; historical/unknown retained | UXR-07 |
| G8 Status/Consent/Errors | Plain-language local+AI readiness upfront; visible critical alarms/consent; diagnostics reachable | UXR-08 |
| G9 Dashboard | Action+due/streak first, compact distinct metrics, one global first-run empty, no inferred data | UXR-09 |

Define compact composition contracts (future proposed only): `MetricTile`, `StatSummary`, `StatusSummary`, `CompactFormSection`, `FilterToolbar`, `EmptyState`, `DisclosureGroup`. Each contract specifies data slots, allowed empty/unknown wording, semantic region/heading/focus, variable-length content and permitted density variants. **Do not create these React files now.**

**Important:** `one primary CTA` means **one dominant next action per screen/state**, not deletion of required save, submit, cancel, revoke, retry, keyboard, consent or secondary navigation controls. Critical safety/privacy actions remain sufficiently prominent regardless of compactness.

### 4.6 Realistic content/extremes and device adaptation

Use source-derived/mock **synthetic** examples (clearly labeled) to exercise:
- First-use empty and populated with due cards, streak and both objective/self-score results.
- No due cards but prior history; mixed null streak + valid performance; late-loading/stale local data.
- Very long Vietnamese labels, long word meanings/examples, 100-character lemma and overflow-prone metadata.
- Long quiz prompts, multiline writing answers, a consent policy paragraph and actual-reason error recovery.
- `0/100` future books and many skill tags **as architectural annotation only**; book progress is not a live Dashboard widget and no clickable new Library link is added.
- Windows desktop pointer/keyboard; mobile touch; **320px reflow and effective 200% zoom**; no ordinary horizontal overflow, focus obscuration or decorative compression of critical controls.
- The 200% zoom and accessibility conditions are **design targets** until later real browser and WCAG verification. A static image cannot prove a screen reader or keyboard trap works.

## 5. Mandatory owner-visible UI image packet (VG3)

During authorized UXR-02A execution, create **real full-resolution PNG/WebP composed UI previews** (browser-rendered static mockups or clearly labeled image designs). Provide inline viewable comparison/contact sheets **and links to every full-resolution image**. Record `task | group | variant | content state | CSS viewport | theme | DESIGN_MOCKUP | version/date | link | data provenance`.

**Minimum review gallery â€” 12 labeled full-screen frames**, count each actual state+viewport separately:

| Frame IDs | Screen/state | Exact CSS viewports | Min. images |
|---|---|---|---|
| D1â€“D4 | Dashboard **first-run** and **populated** in selected compact direction | `1366Ã—768` desktop **and** `390Ã—844` mobile for each state | 4 |
| R1â€“R2 | Review **empty queue**/date toolbar; no duplicate visible prose | `1366Ã—768` and `390Ã—844` | 2 |
| S1â€“S2 | Status/Consent **readiness summary**, permission location, diagnostics disclosure entry | `1366Ã—768` and `390Ã—844` | 2 |
| D5 | Dashboard **mixed history / null streak / no attempts** | `1366Ã—768` | 1 |
| D6 | Dashboard **first-run** stress reflow/long label | `320Ã—568` | 1 |
| R3 | Review **UNKNOWN or pending rating** safe recovery | `390Ã—844` | 1 |
| S3 | Status **DEGRADED/UNKNOWN or ACTIVE alarm + revoked/stale consent** | `1366Ã—768` | 1 |

**Additional mandatory comparisons (not included in the 12 count):**
- **At least two alternative Dashboard layout compositions** in the *selected* UXR-01 visual identity; the second composition needs at least `1366Ã—768` first-run and `390Ã—844` populated examples (**2 more screenshots**). The owner chooses the actual compact composition; don't call A/B re-approval of color/brand.
- Representative `768Ã—1024` tablet and `1024Ã—768` intermediate responsive annotated screen (screenshots or mockup screenshots where layouts meaningfully change); record deviations and still test the concept for 200% zoom reflow.
- A **light/dark** pair of the same approved-layout Dashboard state (could reuse one of the 12 only if matching theme pair exists; otherwise add a frame).
- Before/proposed side-by-side comparisons for Dashboard, Review empty and Status using **genuine** UXR-00/owner baseline when image bytes are available; if not accessible, mark baseline `WRITTEN_EVIDENCE_ONLY` and show proposed image without fabricating an original screenshot.
- A compact **G1â€“G9 density board** showing each screen's action hierarchy and advanced disclosure regions; can be an annotated gallery, not a claim that all nine feature designs are finished.
- Separate `SCROLL/FOLD` annotation for `1366Ã—768` Dashboard: heading, safe next action and due/streak summary visible above fold; no forced heights used solely to satisfy the metric.

A collage with tiny illegible thumbnails, source JSX, ASCII wireframes or a GitHub Markdown table **alone** does not pass. Images must be directly accessible to the owner (committed under `docs/design/uxr-02a/assets/` or another approved durable path; scratch/local-only paths are insufficient).

**Owner review action:** provide a specific selection sheet `variant and version | gallery links | compare evidence | changed principles | outstanding warnings | APPROVE/REQUEST_CHANGES/REJECT/PENDING | explicit owner response/date`. The task remains `OWNER_VISUAL_APPROVAL_PENDING` until **explicit approval of the actual frames and density contract**. New layout version after a requested change â†’ new images and reapproval, not reused prior approval.

## 6. Mandatory Impeccable skill usage â€” actual coordinator AND worker invocations

Impeccable is reported **already installed on owner's Windows machine**; **never reinstall, update or vendor it** as part of this research task.

- At the start of **each actual local Codex coordinator/worker execution session**, resolve the installed skill base directory in that agent's own harness and read its installed `SKILL.md` and references. From English Web repository cwd, invoke `<skill-base-dir>/scripts/impeccable context` **once per session** (Windows `.cmd` launcher when required); no wasteful repeated init/context calls.
- Use the installed version's relevant design workflow: `layout` for grouping/density/rhythm and viewport checks, `distill` for duplicate CTAs/empty prose, `adapt` for device changes, `critique` for independent visual hierarchy appraisal; `harden/clarify/onboard` when justified by source state and owner scope. Read the command-specific reference; **do not indiscriminately run every command**.
- When critique requires parallel isolated agents and native subagents are available/authorized, honor the installed skill's procedure, but **only one coordinator** edits consolidated design/gallery/approval records. Non-overlapping tasks can run in parallel.
- **Proof artifact for every active design worker:** `agent ID and role | skill path/version | session | context command and actual result | references/commands applied | target | finding | design change | screenshot/result link`. Coordinator also logs its own invocation.
- If skill cannot be accessed, report `IMPECCABLE_NOT_ACCESSIBLE` with path/error and owner remedy needed, not a fabricated pass. The mandatory skill gate remains **BLOCKED**; the coordinator can record incomplete design research without claiming final UXR-02A DONE.
- This GitHub-only authoring session **has not accessed or run the Windows-installed skill**; researching the official upstream skill in a previous task is not execution proof. Skill recommendations do not override UXR-01 approved identity, UXR-02 tokens, privacy safety, meaningful density or official shadcn sourcing.

## 7. Official shadcn/ui component contract â€” no install in design phase

Source of missing reusable UI primitives: **official only** https://ui.shadcn.com/docs/components, with matching **Radix-compatible** implementation. Use the repo's [component strategy](../docs/design/shadcn-ui-component-strategy-2026-10-12.md), existing `components.json`, `index.css` and local `Button/Card/Dialog` as baseline.

Document precise component name, official docs URL, reuse/propose status, role and risk. Candidates per need:
- Dashboard: official `Card`, `Badge`, `Progress` (only if denominator exists), `Skeleton`, `Tabs` or `Collapsible`, `Separator`, `Button`. `Chart` only when actual source data makes it meaningful.
- Review: `Card`, `Button`, `Badge`, `Progress`; date filter `Input`/native date first; official `Date Picker` only if evidence justifies replacing the native date.
- Status: `Alert`, `Badge`, `Accordion`, `Collapsible`, `Separator`, `Dialog`, `Table`, `Skeleton` as justified.
- Reusable composition: `MetricTile/StatSummary`, `FilterToolbar`, `StatusSummary`, `CompactFormSection`, `EmptyState` **combine existing/official primitives** in a future app-level layer; they are not a request to install a third-party composition registry.

**Never** run `shadcn init --force`, `add --all`, `add --overwrite`, install any component, edit dependency/lockfiles or reinitialize the Tailwind Preflight baseline during preparation or design-only mockup creation. Installation/upgrades belong to **separately authorized implementation work**, after pinned CLI/diff/security/compatibility review. Skills can critique style, not substitute unauthorized components.

## 8. Deliverables and artifact names for later authorized execution

| Required path under `docs/design/uxr-02a/` | Contents |
|---|---|
| `UXR-02A-EVIDENCE-MATRIX.md` | screen/state/baseline screenshot/viewport/source reference/quality flag and explicitly unverified states |
| `UXR-02A-DENSITY-CONTRACT.md` | G1â€“G9 hierarchy/CTA/disclosure/empty/state rules and role-based compact composition specification |
| `UXR-02A-DASHBOARD-VARIANTS.md` | two genuinely different compact compositions, precise first-run/populated/mixed/unknown state mappings, annotated fold |
| `UXR-02A-REVIEW-STATUS-SPEC.md` | compact Review empty/pending, Status/Consent summary+diagnostic patterns, privacy/focus safeguards |
| `UXR-02A-SHADCN-MAPPING.md` | official docs links and local/existing/proposed/deferred statuses; no CLI installation |
| `UXR-02A-VISUAL-GALLERY.md` | full screenshot inventory (minimum 12 + 2 alternative images), contact sheets, image provenance and full-resolution links |
| `UXR-02A-IMPECCABLE-EVIDENCE.md` | each worker and coordinator installed-skill invocation plus actual design effects, or explicit blocker |
| `UXR-02A-OWNER-DECISION.md` | explicit owner review of screenshots/layout variant, feedback, version, date/reference |
| `UXR-02A-HANDOFF-TO-UXR03-09.md` | frozen density constraints, owners, permitted exceptions and specific downstream AC expectations |
| `assets/*.png` or `assets/*.webp` | viewable full-resolution design mockups and representative side-by-side comparisons |

All paths here are **future deliverables**, not files whose existence is claimed by this task-card preparation. Using isolated design/mockup artifacts outside app source is permitted **only when UXR-02A execution is authorized**.

## 9. Acceptance criteria / Definition of Done (all mandatory)

- **AC01 Dependency gate:** verified UXR-00 evidence and UXR-01/UXR-02 owner visual sign-offs linked with version; UXR-02A execution separately authorized.
- **AC02 Image gate:** owner-accessible **at least 12 primary full-resolution screen images plus 2 alternative Dashboard composition images**, with the exact frame/state/viewport coverage in Â§5, source-vs-mockup labels and no fake current UI evidence. Include tablet/intermediate comparison and same-state light/dark evidence.
- **AC03 Owner choice:** owner is shown **two compact Dashboard compositions** and an evidence-based recommendation; explicit choice/approval of named version and screenshots is recorded; no implicit sign-off from a model score.
- **AC04 Fold:** annotated `1366Ã—768` Dashboard shows heading, next valid action (or honest unavailable reason), due and streak glance without initial scroll; spacing is content-driven, not artificially squeezed.
- **AC05 CTA count:** **at most one visually dominant primary action per screen/state** in proposed first-run Dashboard, Review empty and Status primary view. Secondary and critical privacy/recovery controls are still clearly reachable.
- **AC06 Empty handling:** first-run Dashboard has exactly **one** visible global 'no learning history' explanatory surface; Review empty has exactly **one** visible queue-empty explanation; mixed Dashboard preserves local context and previously valid metrics. Live-region accessible announcements are not discarded to game visible-duplication count.
- **AC07 Semantic data truth:** demonstrate side-by-side `dueCards=0`, `streak.currentDays=null`, objective `attempted=0 / accuracy=null`, actual known values, `DEGRADED` and `UNKNOWN` with **different labels and no invented denominator, zero streak, confidence or fake AI success**.
- **AC08 Status safety:** active alarms and high-importance consent/privacy remain visible; status summary differentiates local study vs AI bridge; technical sections remain reachable and the `/status#ai-consent` deep-link/focus plan is explicit.
- **AC09 Review mutation:** empty/unknown/pending states are not merged; no second rating/success claim during unresolved operations, and noteDate URL behavior is retained.
- **AC10 Nine-group matrix:** all G1â€“G9 have explicit primary task/action, top-level info, advanced content, critical state, component candidate and designated feature owner. Missing screenshots stay marked `SOURCE-ONLY/NOT_VERIFIED`.
- **AC11 Responsive design:** proposals cover `1366Ã—768`, `390Ã—844`, `320Ã—568`, `768Ã—1024` and `1024Ã—768`; document `1440Ã—900` foundation inheritance, long-string and 200% zoom reflow/focus constraints. No unmeasured a11y PASS claim.
- **AC12 Component compliance:** all missing reusable primitives map to official shadcn docs/compatible Radix; local components reused; no component/dependency installation.
- **AC13 Impeccable proof:** coordinator plus **each actual design worker** has a real installed-skill context invocation and command/reference evidence, with changes tied to screenshots. No silent skip or reinstall.
- **AC14 Cross-boundary safety:** no modification to route registry, React/CSS, API/DTO, backend, SQLite, consent/SRS/quiz/Markdown or official app primitives. Future Library/IELTS/TOEIC/CEFR remain annotation-only.
- **AC15 Full handoff:** explicitly approved compact design version, image links, frozen contracts, variation allowances, unresolved exceptions and per-feature UXR-03â€“09 ownership are recorded.
- **AC16 Visual owner approval:** owner explicitly views and approves image packet + density rules. Until then, task is **`OWNER_VISUAL_APPROVAL_PENDING`**, not `DONE`. No UXR-03â€“09 design execution before this gate.

**Lifecycle:** `PREPARED` â†’ `READY_FOR_EXECUTION` (upstream gates + new owner permission) â†’ `IN_PROGRESS` â†’ `OWNER_VISUAL_APPROVAL_PENDING` â†’ `DONE` only on completed images, evidence, and explicit owner approval. Genuine blockers remain `BLOCKED`.

## 10. Out of scope / safety boundaries

- No implementation of redesigned UI; no React, CSS, TS, test fixture, frontend/backend, API/schema, lockfile, database or launcher edits.
- No installation or update of locally installed Impeccable; no new shadcn primitives/dependencies in repository during design.
- No fake populated application, synthetic metrics presented as real observations, fabricated 9/9 audit coverage or inferred WCAG/accessibility PASS.
- No change to SRS due/rating schedule, quiz snapshot/autosave/results, writing self-score/AI separation, consent grant/revoke, unknown-operation reconciliation, source revision/ETag or Markdown persistence.
- No new Library/Books/Chapter/Lesson/Exercise/Progress routes, book dashboard widget or examination scoring rules.
- No authorization for UXR-03â€“09 execution, UXR-11 sign-off, UXR-12 adoption or merge of Draft PR #26 as part of **task preparation**.

## 11. Parallel execution and file ownership

**Dependency DAG:**

```text
UXR-00 evidence â†’ UXR-01 visual direction/owner decision
               â†’ UXR-02 AppShell visual foundation/owner decision
               â†’ UXR-02A compact layout/density/owner decision
               â”œâ”€â”€ UXR-03 G2/G3 vocabulary Lookup/Search/Detail
               â”œâ”€â”€ UXR-04 G4 Save/Edit
               â”œâ”€â”€ UXR-05 G5 Review
               â”œâ”€â”€ UXR-06 G6 Quiz Builder/Runner
               â”œâ”€â”€ UXR-07 G7 Results/Feedback
               â”œâ”€â”€ UXR-08 G8 Status/Consent/Errors
               â””â”€â”€ UXR-09 G9 Dashboard
                   (all seven complete â†’ UXR-10 â†’ UXR-11)
```

Within an authorized UXR-02A session, parallel read-only design specialists may own `dashboard`, `review`, `status` evidence/variant scratch artifacts. **Coordinator/lead only** integrates final density spec, shadcn mapping, approval packet, roadmap and PR text. Every specialist using design reasoning loads and invokes Impeccable **itself**. No shared browser session or concurrent writes to common approval files without explicit isolation.

| Artifact/source | Ownership |
|---|---|
| `tasks/uxr-02a-layout-simplification-information-density.md` | Research task-spec coordinator; preparation only now |
| `docs/design/uxr-02a/UXR-02A-DENSITY-CONTRACT.md`, `UXR-02A-OWNER-DECISION.md`, `UXR-02A-HANDOFF-TO-UXR03-09.md` | **One UXR-02A integration lead** |
| `docs/design/uxr-02a/assets/dashboard-*` | One designated Dashboard visual worker |
| `docs/design/uxr-02a/assets/review-*` | One designated Review visual worker |
| `docs/design/uxr-02a/assets/status-*` | One designated Status/Consent visual worker |
| `docs/design/uxr-02a/UXR-02A-IMPECCABLE-EVIDENCE.md`, `UXR-02A-VISUAL-GALLERY.md` | Lead aggregates worker logs and asset links |
| `docs/design/uxr-01/**`, `docs/design/uxr-02/**` | **Read only**; approved foundation not overwritten |
| `artifacts/uxr00/**` and UXR-00 reports | **Read only**; preserved audit provenance |
| `docs/design/english-web-ui-ux-redesign-plan-2026-10-12.md` and PR #26 | Roadmap/PR coordinator single writer |
| `frontend/**`, `backend/**`, `components.json`, package locks, `tasks/todo.md` | **Read only** in design phase |

Downstream UXR-05/08/09 own complete feature interactions and their final implementation-oriented visual specs. They must **inherit** UXR-02A's approved density contract but may propose precisely documented, owner-approved accessibility/behavior exceptions. They must not directly edit UXR-02A's frozen files. During current GitHub work only this UXR-02A Markdown brief, roadmap and PR description may be created/edited.

## 12. Explicit handoff / approval barrier for UXR-03â€“09

Before sending the next feature design task to Codex/Astra, provide:
1. A direct owner decision/version/date for the **actual UXR-02A UI screenshots**, including selected compact Dashboard layout and frozen first-view hierarchy.
2. Exact official shadcn component inventory and app-level composition contracts (UI-only), with owners and permitted variations.
3. Nine-group density/action hierarchy table, states and recorded exceptions.
4. Full-resolution screenshot gallery and genuine baseline provenance; unresolved `NOT_VERIFIED` evidence, including downstream groups without current screenshots.
5. Responsive/keyboard/contrast **design requirements** (not declared implementation PASS), source contract guardrails and local/AI/consent/quiz protections.
6. Coordinator + worker Impeccable actual-run evidence.
7. UXR-03â€¦09 dependency readiness: **all seven may begin design in parallel only after UXR-02A is signed off**; each preserves its own scope and cannot edit UXR-02A shared artifacts.
8. In the absence of any required owner visual approval, keep UXR-03â€¦09 **BLOCKED_FOR_EXECUTION**. This does **not** prevent creating their future Markdown task descriptions now.

This document deliberately describes future work; no screenshots, mockups or local skill execution have been produced during its task-card preparation.


### Current closure status (2026-10-14)

The owner approved Variant B — Compact Refinement, release UXR-02A-R1B, including A12 square heatmap geometry. AC03, AC15 and AC16 are closed by explicit owner approval and completed handoff. The status is DESIGN_PUBLISHED_PENDING_GIT_CONFIRMATION until the authorized commit and remote publication are verified; historical preparation statements below remain historical records and are superseded for current state.\n

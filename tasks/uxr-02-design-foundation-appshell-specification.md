# UXR-02 — Design Foundation & AppShell Specification

**Track:** English Web UI/UX redesign (separate from application T001–T090)  
**Priority:** P0 / shared design foundation  
**Status:** `PREPARED / NOT STARTED / BLOCKED_BY_UXR_01_OWNER_SIGNOFF`  
**Task-file preparation:** APPROVED 2026-10-12; **task execution, final UI direction, installation and code implementation are NOT approved**.  
**Dependency:** UXR-00 final handoff → UXR-01 image-based owner selection/approval → **UXR-02** → UXR-02A.  
**Owner-visible approval:** MANDATORY **visual screenshots**, not merely a markdown specification.  
**Branch:** `design/ui-ux-research-20261012` / [Draft PR #26](https://github.com/khanhpn308/english_web/pull/26). Do not merge.  
**Shared mandatory protocol:** [Visual Owner Approval + Impeccable + Official shadcn/ui](../docs/design/uxr-visual-approval-impeccable-protocol-2026-10-12.md).

## 1. Objective and scope

Define one consistent, evidence-driven **visual design foundation and shared application shell** that supports all nine existing routes (G1–G9), compact content-first learning screens, keyboard navigation, locally honest status, light/dark theming and future navigation growth **without enabling future features**.

Produce an actual **owner-reviewable rendered visual proposal** of the new AppShell and its states. Owner visually approves the specific UXR-02 foundation version before this task is called DONE and before UXR-02A execution. Approved UXR-01 direction is binding; do **not** independently choose Direction A, B or a hybrid in this task.

UXR-02 owns: shared information architecture, layout regions, sidebar/header/nav behavior, foundational tokens, semantic state patterns, responsive shell rules, typography and primitive/component adoption plan. **UXR-02A**, not UXR-02, owns cross-screen KPI/card density, primary CTA/empty-state deduplication, detailed Dashboard first-run + populated layout and the compact-layout owner gate.

## 2. Current status, evidence and blockers

- Research branch contains source-based design notes; UXR-00 was last documented `IN_PROGRESS`. No proven UXR-00 DONE artifact or UXR-01 owner-signed design direction is available in this task preparation context.
- Existing source: `frontend/src/app/AppShell.tsx` declares nine same-origin routes, horizontal navigation to six main destinations, an AI-consent deep link, skip link, route focus and live status/ErrorBoundary. Current behavior is a **baseline contract**, not proof that a redesigned Sidebar or mobile drawer works.
- `frontend/src/index.css`: existing semantic light/dark CSS variables; `frontend/src/app/shell.css`: current body and shell baseline, no blanket Tailwind Preflight.
- `components.json`: existing `new-york`, Tailwind CSS variables, `lucide` icons and `@/components/ui` aliases. Installed local primitives include `Button`, `Card`, `Dialog` with Radix Dialog. No installation/reinitialization is required for **task preparation**.
- The 2026-10-12 existing visual audit has **partial G1/G2/G5/G6/G8/G9** desktop visual coverage; G3/G4/G7 lack direct screenshots. Treat unsupported visual claims as `NOT_VERIFIED` until UXR-00 hands off.
- The owner has stated Impeccable is already installed **on their Windows machine**. GitHub research cannot invoke or validate that installation. Actual Codex coordinator/worker usage must be proven in the later execution log.

**Current gate:** `BLOCKED_BY_UXR_01_OWNER_SIGNOFF`. This Markdown file can be committed now; designing UI, running Impeccable on the user's local machine, finalizing tokens and producing approved design images require later execution authorization.

## 3. Hard dependencies and execution start conditions

Do **not** start execution until all are verified:

1. UXR-00 final report/coverage matrix is handed off, with `NOT_VERIFIED` conditions and environmental blockers retained honestly.
2. UXR-01 has **actual A/B image mockups** and an explicit owner-signed selection (`direction/version/date/evidence link`) of A, B or a specified hybrid; D1/D2/D3/D4/D6/D8/D9 status and any deferred choices are recorded.
3. The current design roadmap, [UXR-01](uxr-01-design-direction-owner-approval.md), official shadcn strategy, future content architecture and new mandatory visual protocol have been read.
4. Owner has authorized execution of UXR-02 and single-writer responsibility is assigned for shared artifacts; owner approval for task-file **preparation alone** is not authorization to execute.
5. The active local Codex harness resolves the already-installed Impeccable skill; local coordinator and design workers can actually load its instructions. If not, report `IMPECCABLE_NOT_ACCESSIBLE` and do not claim execution of the mandatory skill.

No need to wait for future Library/product scope decisions; these are non-blocking conceptual extension seams, not implemented routes.

## 4. Required concrete work (when later authorized)

### 4.1 Baseline inventory and invariants

Create a source-to-design mapping with `file/symbol | current responsibility | proposed presentation-only change | invariant | owner | visual evidence`. Inspect the exact existing V1 route definitions, navigation click handling, history/back/forward, URLSearchParams, focus transfer, deep links, fallback/404 and retry behavior. Protect:

- Existing routes: `/`, `/lookup`, `/search`, `/word-forms/:id`, `/review`, `/quiz/new`, `/quiz/:attemptId`, `/quiz/:attemptId/result`, `/status`.
- `/status#ai-consent` and a visible way to reach it from every screen. An in-app hash anchor is not a new route and must work across navigation.
- Current same-origin/local bootstrap semantics; skip-to-main, `nav`/`main` landmarks, live announcement and focus on the screen `h1` after navigation; correct `aria-current` for active parent links on detail/quiz descendant routes.
- Honest visual distinction: local API unavailable, external AI bridge unavailable, consent not granted/revoked/stale, `NOT_READY`/`READY`/`DEGRADED`/`UNKNOWN`; green/healthy appearance never proves missing data is verified.
- Browser keyboard/history behavior, in-progress quiz draft safety, source/ETag/revision conflict handling, SRS due/rating and writing self-rating are **preserved contracts**. A shell redesign cannot alter them.

### 4.2 Navigation and information-architecture design

Specify a scalable navigation register **concept**, with fields such as `featureId | section | label | route | enabled | capabilities | ordering | active descendant rule`, plus:

- **Current live items:** Dashboard, Lookup, Search, Review, Quiz Builder, Status.
- **Groups:** Learning, Vocabulary, Practice, System (exact labels/localization approved by owner).
- Detail/edit and quiz runner/result routes use contextual breadcrumb/back path and parent active state, not additional global sidebar items.
- AI consent is a visible deep link under Status, not generic Settings and not an alternative to explicit consent disclosure.
- **Future conceptual entries only:** Library/Books/Chapters/Lessons, Exercises by Book, Vocabulary-to-Book Links, Book Progress, IELTS/TOEIC/CEFR classifications and Reading/Listening/Writing/Speaking. Mockup-only diagram labels `FUTURE — HIDDEN UNTIL SHIPPED`; NO clickable v1 placeholder, dead nav, route registration or fake existing metric.
- Route/feature registry is a small static future implementation proposal, **not** a plugin loader, microfrontend platform or permission system.
- Describe navigation fallback at unknown route, stale session and direct deep-link entry.

### 4.3 Layout regions and responsive behavior

Specify AppShell regions with semantic hierarchy:
1. Skip link and accessible landmarks.
2. Wide-screen sidebar (proposed width *range*, expanded/collapsed state and affordances).
3. Compact top header with page title or breadcrumb, local readiness/consent entry, avoiding redundant screen headings.
4. Main content with density-agnostic width modes: standard workspace, **focus study/quiz**, and **resource reader/future**.
5. Global alert/notice placement and accessible focus/announcement behavior.
6. Mobile trigger/drawer and overlay semantics; keyboard and touch behavior.
7. Responsive spacing, safe areas, long Vietnamese labels and scroll containment; no sticky controls obscuring important fields or keyboard focus.

Required **design frame matrix** (CSS-pixel sizes):
- `1440×900`: sidebar expanded, sidebar collapsed, route detail.
- `1366×768`: Dashboard representative initial fold (heading/primary CTA/due-streak summary visible in concept without faking fixed heights).
- `1024×768`: intermediate layout with conditional navigation and content width.
- `768×1024`: tablet drawer/collapsed pattern, displayed action hierarchy.
- `390×844`: mobile menu closed/open with focus trail and representative content.
- `320×568`: stress example showing long labels, no ordinary horizontal overflow, visible critical action and focus path.
- `200% zoom`: design reflow/focus plan, including effective reduced CSS width; actual claims require later browser verification.

No arbitrary sidebar width or mobile pattern can be treated as an approved choice before the owner sees rendered variants. Show content and chrome as a **composed UI**, not isolated rectangles with only labels.

### 4.4 Foundations: tokens, typography, state semantics

Create a proposed token decision table, `role | current source | light candidate | dark candidate | use/contrast concern | approval status`:
- `background`, `foreground`, `card`, `muted`, `border`, `primary`, `accent`, `ring`, `destructive`; plus named **success/warning/unknown/status** roles if justified.
- Type system for page headings, section headings, body, forms, metadata and bilingual word/IPA/examples; use reliable **offline-available** fonts or explicitly approved bundled licensed assets, not an uncontrolled runtime CDN. Impeccable typography preferences must not override local/offline product requirements.
- Spacing/padding/radius scale: **content-driven**, not large equal-height decorative cards. Record component role, label and focus states.
- Light/dark screenshots of the **same actual composed UI** and status/consent examples; do not assert passing WCAG 2.2 AA without measured contrast/focus evidence.
- Motion/reduced-motion, disabled/loading/selected/active/unknown focus styles; don't signal state by color alone.

This is a proposed **design spec**, not modification of `index.css`, `shell.css` or installed components.

### 4.5 Official shadcn/ui component adoption plan — mandatory

Read the [official component catalog](https://ui.shadcn.com/docs/components) and repo [strategy](../docs/design/shadcn-ui-component-strategy-2026-10-12.md). Create an inventory table:

`component | official Radix docs URL | existing file? | ALREADY_PRESENT / OFFICIAL_PROPOSED / CUSTOM_COMPOSITION / DEFERRED | chosen AppShell role | dependency/upgrade risk | single owner`.

At minimum evaluate `Sidebar`, `Breadcrumb`, `Sheet` (only if necessary), `Collapsible`, `Separator`, `Button`, `Card`, `Dialog`, `Badge`, `Alert`, `Input`, `Field`, `Textarea`, `Skeleton`, `Tooltip` and `Dropdown Menu`. Explain why Sidebar mobile behavior does or does not require separate Sheet; prevent double overlays and duplicate key handlers.

**Hard component acquisition rule:** missing components must be sourced **only from the official shadcn/ui components documentation/registry** after future implementation approval. Reuse existing `Button/Card/Dialog`; use the **Radix-compatible** official source and inspect scoped pinned-version CLI diff during implementation. Do not use third-party registries, copy community dashboard templates, issue `shadcn init --force`, `add --all`, `--overwrite`, edit `package-lock.json`, install libraries or run any CLI that mutates app files during this design-only task.

### 4.6 Impeccable execution is mandatory and auditable

Use [visual/skill protocol](../docs/design/uxr-visual-approval-impeccable-protocol-2026-10-12.md) §3.

- Coordinator and **each independent design worker**: discover locally installed skill in own active Codex context; read installed `SKILL.md` and selected references.
- Run **actual installed launcher `<skill-base-dir>/scripts/impeccable context` once per session** from project cwd (`.cmd` on Windows when appropriate). Do not reinstall, update, or rerun context unnecessarily.
- Apply appropriate installed-skill design procedures to **shape** the shell, **critique** alternate nav/layout structures, **adapt** responsive patterns and review **layout** hierarchy; use command/reference only when supported by installed version and task scope. A command needing source code edits must operate on isolated mockup materials only during this design-only phase.
- Submit `agent | role | skill actual path/version | successful context invocation or exact blocker | reference/command | target | finding → design change | evidence location`. A worker not invoking the skill is **not compliant** merely because Astra read the upstream GitHub README.
- If local skill is unavailable, report `IMPECCABLE_NOT_ACCESSIBLE`, no install workaround and **no false pass or owner approval**. Reading upstream in GitHub now is reference research, not local skill execution.

### 4.7 Produce actual screenshot proposals and request owner approval

**Mandatory visual packet, using rendered/composed UI not merely text:**
- At least **two distinctly composed AppShell alternatives** within the chosen UXR-01 visual direction for sidebar/top bar placement or density (do not restart a competing A/B brand identity decision).
- Full-resolution PNG or WebP screenshots for each required §4.3 frame/state, with desktop expanded/collapsed, mobile menu open/closed, deep detail context, status alert + consent shortcut, focus-mode study/quiz and **light/dark** examples.
- At least one shell screenshot populated with **Dashboard**, another with Lookup/Search or Quiz so the shared shell is proven as a composition, not a standalone sidebar template. Meaningful Vietnamese example copy, true empty/unknown semantic labels and realistic long strings.
- A side-by-side `CURRENT_APP_CAPTURE` versus `DESIGN_MOCKUP` where an authentic baseline exists, plus a before/after annotation explaining the visual change and any information retained. For no direct screenshot, label `SOURCE-ONLY BASELINE`.
- Inline readable contact sheet **AND direct links to full-resolution images**. Image captions include variant, state, viewport, theme, version and mockup disclaimer; PNG assets must be stored in a persistent owner-accessible location on the research branch.
- Produce an owner decision ledger for sidebar default, mobile pattern, nav labels/grouping, header placement, typography, light/dark palette, focus-mode shell and component shortlist. Mark each `PENDING` until explicitly approved. Visual approval cannot be inferred from automatic checks or internal agent scoring.

**Do not fake browser testing:** a browser-rendered static mockup is `DESIGN_MOCKUP`, not proof that React/AppShell, a real local server, API, keyboard or screen reader works.

## 5. Files and authoritative references

**Read-only source:**
- `frontend/src/app/AppShell.tsx`, `frontend/src/app/shell.css`, `frontend/src/index.css`.
- `components.json`, `frontend/src/components/ui/button.tsx`, `card.tsx`, `dialog.tsx`, `frontend/src/lib/utils.ts`.
- `frontend/src/features/dashboard/DashboardPage.tsx`, `features/lookup/LookupPage.tsx`, `features/status/StatusPage.tsx`, `features/consent/AiConsentGate.tsx` (only necessary scope).
- `docs/ui-architecture.md`, `docs/adr/0004-v1-product-policy-and-operational-baseline.md`, `docs/adr/0005-contract-clarifications.md`.
- [UXR-01](uxr-01-design-direction-owner-approval.md) and [UXR-00](uxr-00-autonomous-visual-audit.md) final evidence package **when available**.
- [UI/UX roadmap](../docs/design/english-web-ui-ux-redesign-plan-2026-10-12.md), [screenshot audit batch 2](../docs/design/ui-visual-audit-2026-10-12-batch2.md), [shadcn strategy](../docs/design/shadcn-ui-component-strategy-2026-10-12.md), [future learning architecture](../docs/design/future-learning-content-architecture-2026-10-12.md).
- [Owner visual approval and Impeccable protocol](../docs/design/uxr-visual-approval-impeccable-protocol-2026-10-12.md); official catalog https://ui.shadcn.com/docs/components; installed Impeccable skill as resolved **locally** by actual agents.

## 6. Required deliverables for later execution

Owned under **`docs/design/uxr-02/`**, during an authorized UXR-02 session:

| File/artifact | Required content |
|---|---|
| `UXR-02-FOUNDATION-SPEC.md` | layout regions, token/typography/responsive contracts, theme and focus rules |
| `UXR-02-NAVIGATION-IA.md` | all nine v1 routes, current six global links, future hidden IA extension, breadcrumb/active/consent rules |
| `UXR-02-SHADCN-ADOPTION-MATRIX.md` | official component URL, local existing/adopt/defer class, primitive/CLI risk, owner |
| `UXR-02-VISUAL-REVIEW.md` | versioned visual board, all required viewports/states, authentic before/proposed pairs, image index and owner decisions |
| `UXR-02-IMPECCABLE-EVIDENCE.md` | coordinator + worker actual installed-skill invocation, references and effects, or exact blocker |
| `UXR-02-APPROVAL.md` | named owner decision for actual screenshots; approved vs pending vs revision requested |
| `UXR-02-HANDOFF-TO-02A.md` | frozen nav/tokens/compositions, allowed density adaptations and unresolved issues |
| `assets/*` | full-resolution composited UI PNG/WebP screenshots plus any isolated, non-production mockup source |

Use descriptive image filenames such as `uxr02-v1-shell-1440-expanded-light.png`, `uxr02-v1-shell-390-drawer-open.png`. All images must be viewable to the owner; a local temp path alone is not an owner-accessible deliverable. Avoid committing fake real-data screenshots.

## 7. Acceptance Criteria and Definition of Done

**Only mark UXR-02 `DONE` if all pass:**

- **AC01 — Dependency proof:** UXR-00 traceable final handoff and UXR-01 owner-signed selected direction/version are referenced; owner has authorized UXR-02 execution.
- **AC02 — All routes:** exact nine v1 routes, active descendant rules, URL/back/deep-link semantics and `/status#ai-consent` are mapped. No invented live Library/Settings route.
- **AC03 — Visual evidence:** proposed **full-screen rendered mockup images** cover §4.3 sizes and the key shell states; includes desktop expanded/collapsed, mobile drawer closed/open, focus route, 1366×768 Dashboard fold, at least one light/dark complete-screen pair, truthful error/unknown treatment and full-resolution links.
- **AC04 — Meaningful UI:** images show real structure and realistic content including long Vietnamese labels, not placeholder boxes. Images are labeled `DESIGN_MOCKUP`; authentic existing screenshots remain correctly `CURRENT_APP_CAPTURE`.
- **AC05 — Structure:** shell specification has one clear heading/task context, no duplicate page title/header, defined sidebar/header/landmark hierarchy, focus and alert placements.
- **AC06 — Responsive/accessibility:** explicit keyboard tab/focus order, drawer focus trap and return, skip link, 320px/200% reflow plan, non-obscured focus, touch target sizing, reduced motion and non-color-only states; unmeasured WCAG claims remain pending verification.
- **AC07 — Honest state:** local/API/AI/consent statuses, `READY`/`DEGRADED`/`UNKNOWN`, and empty/zero are differentiated; neither consent nor quiz state is visually mislabeled as confirmed.
- **AC08 — Component contract:** official-only component shortlist uses verified docs URLs, `ALREADY_PRESENT / OFFICIAL_PROPOSED / CUSTOM_COMPOSITION / DEFERRED` classes and Radix compatibility; source/lockfiles unchanged.
- **AC09 — Skill proof:** **every active design worker and coordinator actually invoked installed Impeccable context** and applied selected guidance; evidence contains exact paths/outcomes, not an unsupported claim. Any `IMPECCABLE_NOT_ACCESSIBLE` blocks completion.
- **AC10 — Token proposal:** light/dark theme-role matrix, typography, spacing and focus/state system documented as **PROPOSED** until visual approval.
- **AC11 — Scope separation:** Dashboard metric density, cross-screen CTA and empty-history specifics are expressly delegated to UXR-02A; that task's sign-off is not claimed here.
- **AC12 — Owner VISUAL sign-off:** owner has viewed accessible proposed UI screenshots and explicitly approved the named `UXR-02 version` and its navigation/layout/theme decisions. Otherwise status `OWNER_VISUAL_APPROVAL_PENDING`, never `DONE`.
- **AC13 — No implementation:** `frontend/`, `backend/`, API, data, package/lockfiles and `tasks/todo.md` untouched; no component installs, CI assertions or merge of PR #26.
- **AC14 — Handoff:** all approved foundation assumptions are linked, and each unresolved decision is listed for UXR-02A rather than silently resolved by a worker.

**Status flow:** `PREPARED` → `READY_FOR_EXECUTION` (UXR-01 owner sign-off + UXR-02 execution approval) → `IN_PROGRESS` → `OWNER_VISUAL_APPROVAL_PENDING` → `DONE` (owner explicitly approves full-resolution visual packet and handoff).

## 8. Out of scope

- Editing or integrating React, TypeScript, CSS, Tailwind, dependencies, installed shadcn/ui, backend, SQLite, API, consent persistence, quiz persistence or production routes.
- Creating accounts, mobile-native app, synchronization, chat, backup, live Library/Book pages or speculative scoring/exam content.
- Running an unapproved shadcn CLI `add/init/overwrite`, reinstalling the already-installed Impeccable skill or introducing fonts/CDNs.
- Comprehensive UXR-00 audit acceptance, system regression, final WCAG PASS, coding release gates, Draft PR merge and UXR-11 final sign-off.
- Final per-screen metric tiles, CTA and zero-history deduplication: **UXR-02A** owns that decision gate.

## 9. Parallelism and coordination

- UXR-02 execution is **sequential** after UXR-01 sign-off; do not dispatch UXR-02/02A as parallel approval work.
- Inside a **later authorized** UXR-02 run, independent read-only subagents may examine (a) existing AppShell routes/focus, (b) official shadcn component inventory/Radix, (c) Impeccable visual/UX critique, and (d) future IA/long-label adaptation. Assign a **single integration lead** to bind all findings to one coherent visual system and owner packet.
- Workers may each read the shared protocol, but must independently invoke their local installed Impeccable skill when performing design tasks.
- **Only one owner** writes the final foundation spec, shared tokens decision table, navigation/IA and `UXR-02-APPROVAL.md`; no parallel uncoordinated edits to shared files.
- The owner must review screenshots before UXR-02A can execute. Preparing UXR-02A's task description separately does not violate the execution gate.

## 10. Artifact ownership

| Path | Access/ownership |
|---|---|
| `tasks/uxr-02-design-foundation-appshell-specification.md` | Coordinator-only task specification |
| `docs/design/uxr-02/**` | UXR-02 design lead **single writer** for merged deliverables; subagents use preassigned non-overlapping scratch paths |
| `docs/design/uxr-02/assets/**` | Named image/mockup owners per variant; lead consolidates and prevents conflicting image versions |
| `docs/design/uxr-visual-approval-impeccable-protocol-2026-10-12.md` | Coordinator-owned shared policy; read only to UXR workers |
| `docs/design/english-web-ui-ux-redesign-plan-2026-10-12.md` | Roadmap coordinator only, updated to approved decisions with owner link |
| `docs/design/uxr-01/**`, `artifacts/uxr00/**` | Read-only upstream evidence; never overwrite |
| `frontend/**`, `backend/**`, `components.json`, `package-lock.json`, `tasks/todo.md` | Read-only during all UXR-02 design work |
| PR #26 | Coordinator only; Draft, design-only, never merge in this phase |

## 11. Handoff to UXR-02A — Layout Simplification & Information Density

Deliver an owner-approved **visually illustrated** foundation version: navigation grouping and labels, sidebar/mobile drawer behavior, token/theme tables, layouts/margins/focus rules, official component inventory, all screenshots and skill proof. Explicitly provide UXR-02A with:

- Frozen structural shell regions and **where Dashboard/Review/Status may adjust content density without editing shell decisions**.
- Shell constraints for a representative **compact Dashboard first-run + populated desktop/mobile** visual mockup, one primary CTA, compact due/streak summary, correct null/zero representation, and no duplicated history-wide empty states.
- Review empty queue and Status/Consent diagnostic disclosure layouts to compare using same token foundation.
- Consistent desktop `1366×768` initial-view target and `320px`/200%-zoom responsive/focus constraints.
- Owner sign-off proof and `UNRESOLVED` list; if owner's approval is absent, leave UXR-02A **BLOCKED**.

UXR-02A must itself present **actual UI preview images to the owner** and obtain separate approval before seven parallel feature-design tasks begin. Nothing in UXR-02 authorizes redesign implementation, production code changes or UXR-12.

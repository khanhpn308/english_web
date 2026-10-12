# UXR-01 — Design Direction & Owner Approval

**Track:** English Web UI/UX research and redesign (independent of application T001–T090 and AI orchestration tasks)  
**Status:** `PREPARED / NOT STARTED / BLOCKED_BY_UXR_00`  
**Execution approval:** NOT GRANTED. Preparation of this task card does not authorize execution.  
**Priority:** P0 design decision gate  
**Depends on:** UXR-00 — Autonomous UI/UX Visual Audit  
**Unblocks:** UXR-02 — Design Foundation & AppShell Specification, **only after the owner approves and records the selected direction**.  
**Repository/branch:** `khanhpn308/english_web` / `design/ui-ux-research-20261012`  
**PR:** https://github.com/khanhpn308/english_web/pull/26 (Draft; do not merge)

## 1. Objective and scope

Produce an evidence-traceable comparison of **two genuinely distinct visual directions** and obtain explicit owner approval of the preferred direction **before** the shared UI foundation, AppShell and feature-level wireframes are finalized.

- **Direction A — Calm Academic Workspace:** study-first hierarchy; quiet surfaces; restrained accent; compact content-driven summaries; appropriately expanded navigation on wide screens; reduced visual noise.
- **Direction B — Compact Study Console:** higher information density; concise action/tool rows; compact navigation and multi-column overview; technical/advanced content readily reachable without turning it into primary study content.
- A proposed **hybrid** is permitted only if the owner explicitly chooses which elements come from A and B and the resulting direction is documented as a new approved variant. Do not mark the recommended A as automatically approved.
- Decide *visual direction, hierarchy, high-level navigation behavior, density policy and concept-level aesthetics*, not final design tokens, pixel-perfect responsive grids, React implementation or quiz state-machine changes.
- Cover **all nine UI groups** (G1–G9) at the level needed to demonstrate the direction remains coherent across study, vocabulary, quiz, status/consent and dashboard flows.

## 2. Current status and evidence boundary

- `UXR-00` has an approved task card and was last reported **IN_PROGRESS**, with no independently verified DONE package. Do not restart, mutate, or close it in UXR-01.
- The owner-supplied 2026-10-12 screenshots currently provide **partial visual evidence for G1/G2/G5/G6/G8/G9**, and **no direct screenshot for G3/G4/G7**. The Dashboard empty-data screenshots and batch-2 findings are evidence; source-derived opportunities for the missing groups are **not** confirmed visual defects.
- Existing design document proposes A/B, candidate palette, sidebar and density; these remain **PROPOSAL** until recorded owner approval.
- The official shadcn/ui component source is an **approved design-system policy** but does not confer approval of a specific Sidebar behavior, palette or component installation.
- **Preparation gate vs execution gate:** authoring this Markdown file now is allowed. Launch UXR-01 only after UXR-00 has delivered the required final report, traceable nine-group evidence matrix and UXR-01 readiness synthesis (including explicit `NOT_VERIFIED/BLOCKED` cases). UXR-00 does *not* need fabricated all-green coverage; owner must be shown any material evidence limitations.

## 3. Dependencies and start conditions

**Hard dependency:** `UXR-00 → UXR-01 → UXR-02 → UXR-02A → UXR-03…09 → UXR-10 → UXR-11`.

The worker/orchestrator must verify before starting:
1. UXR-00 coordinator has issued the report and `UXR_00_STATUS`, `UXR_01_READINESS`, screenshot inventory, coverage matrix, group/blocker register, source anchors and baseline SHA. The report may be local under `artifacts/uxr00/final/`; do not assert its existence on GitHub without verifying it.
2. All `NOT_VERIFIED` groups/states are listed; any blocker with material impact on visual-direction selection is escalated to the owner instead of hidden.
3. The current research branch/roadmap and PR are inspected; any newer UXR-00 findings override provisional evidence claims here *only with source links*.
4. Owner has authorized **execution of UXR-01** separately from the authorization to draft this task; execution does not grant authorization to implement the redesign.
5. No competing agent owns the same UXR-01 artifacts during production of the deliverables.

**Conflict resolution note:** an older paragraph of the roadmap allows *early ideation* while UXR-00 is ongoing. Under the current owner handoff, early task-file preparation is fine, but **formal UXR-01 execution and approval remain gated on UXR-00 handoff**.

## 4. Concrete work to perform when authorized

### 4.1 Establish a traceable baseline
- Read the final UXR-00 synthesis and update an evidence ledger: `group | route/state | viewport | REAL_RENDERED/SYNTHETIC_RENDERED/NOT_VERIFIED | screenshot or NONE | observed issue | source path/symbol | design implication | confidence`.
- Map the existing nine same-origin routes: `/`, `/lookup`, `/search`, `/word-forms/:id`, `/review`, `/quiz/new`, `/quiz/:attemptId`, `/quiz/:attemptId/result`, `/status`. Preserve the `/status#ai-consent` entry point and deep links. No future Library route is a live destination.
- Distinguish local operation, optional AI, permission/consent, failure and unknown states. A source observation does not become screenshot evidence by assertion.

### 4.2 Produce equivalent A/B direction boards
For **each** option present equivalent, labeled visuals for:
1. Desktop learning workspace / Dashboard first-run and compact metrics.
2. Mobile navigation and Dashboard/review view at a **320px CSS viewport**.
3. Vocabulary Lookup/Search/Detail treatment including readable forms, IPA/source labels and accessible advanced filters.
4. Focus mode for Review and Quiz Runner versus standard shell content.
5. Status and AI consent treatment with alerts visible and diagnostics progressively disclosed.

Minimum comparable variants: **wide 1440×900**, **mid-width 768px**, **narrow 320×568** in CSS pixels, plus a representative **1366×768** Dashboard fold check. Record actual frame dimensions, intended zoom and any synthetic content. Provide both options under the **same task scenarios**, not a polished A versus an intentionally weaker B.

Provide annotated low-/mid-fidelity wireframes and a concise comparison board. Do not claim a static Figma/Markdown diagram is a rendered application or an accessibility test. Include light/dark intent and distinguish final palette selection from color *candidate*. No need to create an unsanctioned external Figma account or send confidential data to cloud design tools.

### 4.3 Make the two directions measurably different and inspectable

For each board annotate:
- **G1:** header height strategy, navigation grouping (Learning/Vocabulary/Practice/System), sidebar expanded/collapsed intent, active/current page, breadcrumb and permission shortcut; mobile drawer trigger and focus restoration.
- **G2–G4:** first meaningful content position, common-action prominence, word-source provenance, advanced filter/disclosure placement, Save Preview `→` durable Save and Edit conflict signals.
- **G5–G7:** focus-safe primary action, reveal/rating hierarchy, quiz autosave/saved-unknown differentiation, objective score vs writing self-rating vs optional advisory AI feedback.
- **G8:** local learning status vs optional AI bridge status, explicit consent choice, user-facing action versus technical diagnostics and visible warning/degraded/unknown cases.
- **G9:** exact single first-run CTA location, compact due/streak/quiz summary, semantic `0` versus unknown/no attempts, no repeated whole-page empty-state prose.
- **Future seams:** expandable Library/Books/Chapters/Lessons/Exercises/Progress taxonomy; IELTS/TOEIC/CEFR and reading/listening/writing/speaking labels as **future navigation/schema concepts only**. Show future items on a separate annotated IA diagram as `FUTURE / HIDDEN UNTIL IMPLEMENTED`; **not** as clickable v1 mockup destinations.

### 4.4 Evaluate with one comparison rubric

Create a **side-by-side scoring matrix** using the same 0–3 scale for each criterion (0 = unsupported/violates contract; 1 = major ambiguity; 2 = meets baseline with stated trade-off; 3 = clearly demonstrated by labeled evidence):
- Next-action discoverability across Dashboard, Lookup and Review.
- Information density and duplicated CTA/empty-state control.
- Desktop route discoverability and scalable navigation groups.
- Small viewport reflow, non-obscured content, long Vietnamese labels.
- Keyboard, focus, semantic landmark and contrast *design provisions* (not claimed conformance).
- Readability for dictionary data, long quiz questions and writing answers.
- Honest consent, AI/local status and error/unknown visibility.
- Consistency with official shadcn/ui/Radix and existing tokens/primitives.
- Future Library/Book/proficiency extensibility with no premature feature promise.
- Preservation of existing local-first, SRS, quiz answer/persistence and revision/consent contracts.

For each score, cite a concrete panel/annotation plus baseline/evidence ID; give rationale and trade-off. Scores are **design judgment**, not objective measured usability or performance. Do not manipulate weights to force A. Include a recommended direction only after the comparison.

### 4.5 Make the owner decision explicit, not inferred

Present a one-page decision sheet covering:
- **D1** Direction A / Direction B / explicitly defined hybrid.
- **D2** Desktop sidebar expanded/collapsed default; mobile drawer behavior (subject to UXR-02 details).
- **D3** Restrained indigo versus teal or another named palette *direction*; ensure dark-mode concept exists.
- **D4** Comfortable-study baseline versus compact default, and optional compact mode.
- **D6** Owner visual references to retain/exclude if supplied.
- **D8** Confirmation that official shadcn/ui is the component source **without** blanket permission to install/overwrite.
- **D9** Principle approval for one primary CTA, non-duplicated empty state, compact metrics and progressive disclosure; **UXR-02A still owns layout sign-off**.
- **D5** Quiz Runner one-at-a-time versus all-at-once is intentionally **deferred** to the feature-specific task after a persistence/focus analysis; do not silently choose it in UXR-01.
- **D7** Future book import/content policy does not block UXR-01; keep it `FUTURE / UNAPPROVED`.

For each item record `decision | alternatives | recommendation | owner response | decision date | evidence/link | unresolved consequences`. Leave `owner response = PENDING` until explicit owner instruction. No agent impersonates or infers approval.

## 5. Authoritative source and reference files (read-only inputs)

- [UXR-00 task contract](uxr-00-autonomous-visual-audit.md); its verified final report, screenshot inventory and coverage matrix when available.
- [Redesign roadmap](../docs/design/english-web-ui-ux-redesign-plan-2026-10-12.md), especially sections 3, 3C, 3D, 4–7 and D1–D9.
- [Batch-2 visual evidence](../docs/design/ui-visual-audit-2026-10-12-batch2.md), VIS-001–011.
- [Official component strategy](../docs/design/shadcn-ui-component-strategy-2026-10-12.md) and https://ui.shadcn.com/docs/components.
- [Future learning content architecture](../docs/design/future-learning-content-architecture-2026-10-12.md).
- `docs/ui-architecture.md`; `docs/adr/0004-v1-product-policy-and-operational-baseline.md`; `docs/adr/0005-contract-clarifications.md`.
- `frontend/src/app/AppShell.tsx`, `frontend/src/app/shell.css`, `frontend/src/index.css`, `components.json`, `frontend/src/components/ui/button.tsx`, `card.tsx`, `dialog.tsx`.
- Read feature source **only as needed to verify an interaction contract**; do not edit any source file.

## 6. Deliverables (only during subsequent authorized execution)

The sole UXR-01 worker owns new files under:
`docs/design/uxr-01/`

Required deliverables:
1. `UXR-01-EVIDENCE-LEDGER.md` — versioned UXR-00 handoff citations, group/state/viewport, confidence and unresolved blockers.
2. `UXR-01-DIRECTION-COMPARISON.md` — A/B boards, annotated desktop/tablet/mobile concepts, identical scenarios and scored rubric.
3. `UXR-01-DESIGN-DECISION.md` — D1/D2/D3/D4/D6/D8/D9 sign-off matrix, D5/D7 deferrals, owner decision recorded or `PENDING`.
4. `UXR-01-HANDOFF.md` — selected direction constraints and deferred issues for UXR-02, including semantic tokens and IA questions (not final tokens).
5. Optional wireframe assets at `docs/design/uxr-01/assets/` using descriptive filenames, with labels for conceptual/mock data and source of visuals. Do not commit personal desktop screenshots, credentials, cookies or temporary test records.

This task file is a **brief**; its existence does not mean any of the above deliverables or owner approvals exist.

## 7. Acceptance criteria and Definition of Done

**Task may be marked `DONE` only when all are true:**
- **AC01:** UXR-00 handoff source and readiness are identified with actual artifact links/paths and explicit remaining `NOT_VERIFIED` cases; no false nine-group completeness claim.
- **AC02:** A/B boards cover all five comparable scenarios in §4.2, nine-group implications in §4.3, and wide/mid/narrow viewport concepts with exact labeled dimensions. Any unrenderable state is visibly called out.
- **AC03:** Side-by-side rubric has all 10 criteria, a documented 0–3 scoring legend, cited rationale and trade-offs for **both** directions.
- **AC04:** Each direction shows **one** dominant primary CTA on the proposed Dashboard and a documented empty-history treatment without duplicate full-page empties; critical warnings/consent disclosures remain visible.
- **AC05:** The concept retains all nine current routes, a deep link to AI consent, separate offline/AI statuses, SRS rating semantics, quiz autosave uncertainty, writing self-score/AI separation and source-revision conflicts. Any unresolved choice is explicit, not redesigned away.
- **AC06:** At 320px concepts show a reachable drawer/keyboard sequence, no assumed fixed sidebar, long-label handling and planned reflow; 1366×768 Dashboard highlights heading/primary CTA/due-streak glance above proposed fold without fake forced heights.
- **AC07:** shadcn/ui components are named at concept level (Sidebar, Sheet, Breadcrumb, Button, Card, Alert, Accordion, Badge etc.) with **reuse/propose only** labels; no CLI add/install and no generic component rewrite.
- **AC08:** The owner has **explicitly selected** A, B or defined hybrid and approved the D1–D4/D6/D8/D9 decision sheet with timestamp/reference. Ambiguous or missing feedback keeps `OWNER_APPROVAL_PENDING`, not `DONE`.
- **AC09:** UXR-01 HANDOFF enumerates concrete nonnegotiables, open issues and design decisions needed in UXR-02. UXR-02 is **not** authorized automatically by UXR-01 completion.
- **AC10:** Only design documents/assets changed; no application source, API/DB/DTO, canonical `tasks/todo.md`, PR merge or release/test claims.

**Status transitions:** `PREPARED` → `READY_FOR_EXECUTION` (UXR-00 handoff + owner execution authorization) → `IN_PROGRESS` → `OWNER_APPROVAL_PENDING` → `DONE` (owner sign-off with proof). If UXR-00 cannot supply material evidence: `BLOCKED` with documented question and suggested safe next step.

## 8. Explicitly out of scope

- No coding redesign; no edits to `frontend/`, `backend/`, API contracts, migrations or data.
- No new Library, Book, Chapter, Lesson, Exercise, Progress, IELTS/TOEIC/CEFR or skill feature implementation, routes or persisted tags.
- No shadcn/ui install/upgrade, CSS reset, dependency changes, CLI initialization or blanket overwrite.
- No global testing, CI acceptance, a11y PASS declaration, quiz/scoring policy changes or UXR-00 completion assertion.
- No owner approval by proxy; do not merge Draft PR #26.

## 9. Parallel execution and coordination

- **Planning/document authoring** may overlap UXR-00; **UXR-01 execution** must wait for the explicit UXR-00 handoff.
- One lead designer/agent can delegate **read-only** evidence extraction or option-boarding to independent subagents, provided the A/B comparison is consistent and the final owner-decision record has a **single writer**.
- UXR-02 (shared foundation) **cannot** start formally until D1 direction sign-off and UXR-01 handoff are complete. UXR-02A, UXR-03–09 and implementation remain blocked by their own gates.
- Do not dispatch parallel agents to write `UXR-01-DESIGN-DECISION.md`. The coordinator consolidates owner feedback only from direct recorded owner instruction; not agent consensus.

## 10. Artifact ownership and conflict prevention

| Path / artifact | UXR-01 access | Owner |
|---|---|---|
| `tasks/uxr-01-design-direction-owner-approval.md` | Task specification, edited only with owner-requested scope change | Research documentation maintainer |
| `docs/design/uxr-01/*` | Exclusive write during authorized UXR-01 execution | UXR-01 lead |
| `docs/design/english-web-ui-ux-redesign-plan-2026-10-12.md` | Read; final decision cross-link update only by coordinator | Roadmap coordinator |
| `artifacts/uxr00/**`, UXR-00 final reports | Read only; never overwrite or impersonate audit evidence | UXR-00 coordinator |
| `frontend/**`, `backend/**`, `components.json`, `tasks/todo.md` | Read only / no write | Existing application task owners |
| PR #26 description | Summary update only by research documentation coordinator | Research documentation coordinator |

Use isolated branch/worktree for any future concurrent authoring; coordinate ownership before shared roadmap or PR updates. No UXR worker owns shared primitives or app source during this design phase.

## 11. Handoff conditions to UXR-02

Share:
- Owner-signed direction ID/version/date/link, explicit density/nav/palette policy, any hybrid constraints.
- A/B comparison board and scored rationale; nine-group evidence/gaps and UXR-00 traceability.
- Approved vs *still undecided* design principles; mobile/desktop requirements; future-only navigation seams.
- A boundary checklist protecting routes, browser history, consent, local/offline readiness, SRS, quiz unknown/autosave, word-source revision and writing feedback semantics.
- Specific inputs for UXR-02: canonical tokens inventory, AppShell component inventory, official shadcn reuse candidates, 320/768/1024/1440 responsive concept, focus/landmark policy and gated UXR-02A density work.

If approval is missing, hand off **no finalized direction**; leave UXR-02 blocked. UXR-11 later owns final cross-screen design sign-off and implementation handoff; this preliminary choice is not coding authorization.

## 12. Future task proposal boundary (not adopted)

UXR-12 — *Proposed Redesign Implementation Planning* is **NOT IN APPROVED ROADMAP**. It may be proposed after UXR-11 to translate signed-off designs into discrete coding tasks, implementation dependency DAG, worktree/file ownership, integration gates and sequencing. UXR-11 remains responsible for **approved design handoff**; UXR-12 would be responsible for **post-sign-off coding execution planning**, if separately authorized. This UXR-01 file neither approves nor creates UXR-12.

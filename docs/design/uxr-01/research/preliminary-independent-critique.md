# UXR-01 independent visual and accessibility critique

**Task:** UXR-01 — Design Direction & Owner Approval  
**Worker role:** independent evidence synthesis and visual/accessibility critique  
**Status:** `PRELIMINARY_IMAGE_REVIEW_PENDING`  
**Evidence cutoff:** 2026-10-12 (Asia/Bangkok)  
**Scope:** read-only research; no frontend/backend or integrated UXR-01 document changes

## Evidence boundary

The verified handoff is available under [`artifacts/uxr00/final/`](uxr00/final/):

- [`UXR-00-REPORT.md`](uxr00/final/UXR-00-REPORT.md) reports `PARTIAL_WITH_EXPLICIT_BLOCKERS`, 21 canonical local Playwright captures, and `UXR_01_READINESS: READY_WITH_EVIDENCE_GAPS`.
- [`COVERAGE-MATRIX.md`](uxr00/final/COVERAGE-MATRIX.md) records partial rendered coverage for G1–G6, G8 and G9; G7 is `PARTIAL / NOT_VERIFIED`.
- [`SCREENSHOT-INVENTORY.md`](uxr00/final/SCREENSHOT-INVENTORY.md) identifies the 21 canonical PNGs and the 1440×900 / 320×568 CSS viewports.
- [`CHECKPOINT.md`](uxr00/final/CHECKPOINT.md) records baseline SHA `c2417ba6ff1db131fd3259faf67100fda6c3928b`, local harness `127.0.0.1:8124`, temporary SQLite isolation and no provider calls.
- [`IMPECCABLE-NOTES.md`](uxr00/final/IMPECCABLE-NOTES.md) reports a supplementary detector pass, not a WCAG or product acceptance pass.

At the time of this first pass, neither `artifacts/uxr01/` design images nor `docs/design/uxr-01/assets/` existed. Consequently, this file does **not** claim to have inspected Direction A/B pixels, image dimensions, contact sheets, color contrast or rendered interaction. It is a baseline critique and an inspection rubric to apply after the two independent image sets arrive. Synthetic fixtures remain synthetic; source findings remain source-only.

## Impeccable proof of use

- **Installed skill:** `.agents/skills/impeccable/SKILL.md` (metadata version `4.5.2`).
- **Command invoked once from project root:** `.agents/skills/impeccable/scripts/impeccable.cmd context`.
- **Invocation result:** `NO_PRODUCT_MD` and `PRODUCT_INIT_REQUIRED`; resolved project root `C:\Users\khanh\projects\vocabularies-smoke`; no `PRODUCT.md`, `DESIGN.md` or surface brief; `IMAGE_TOOLS: no image converter found`.
- **References read:** `reference/shape.md`, `reference/layout.md`, `reference/distill.md`, `reference/adapt.md`, and `reference/critique.md`.
- **Design impact:** use a content-first Operate/Read lens; verify one primary task path, proximity/grouping/rhythm, progressive disclosure, structural rather than pixel-scaling adaptation, and Nielsen heuristic/cognitive-load checks. The launcher did not authorize editing production code and none was changed.
- **Affected image IDs:** none yet. This is intentional and is recorded as an evidence limitation until the workers deliver full-resolution A/B assets.

## Verified UXR-00 synthesis by UI group

| Group | Verified evidence | Confidence | Independent design implication | Carry-forward gap |
|---|---|---:|---|---|
| G1 AppShell/navigation | `BR-001`, `G1-shell-desktop-REAL_RENDERED-1440x900.png`, `G1-shell-narrow-REAL_RENDERED-320x568.png` | High for shown states | Replace six-item horizontal nav with grouped Learning/Vocabulary/Practice/System IA; preserve active route, skip link, deep links and focus. | Mobile drawer focus restoration, back/deep-link behavior, keyboard and 200% zoom are unverified. |
| G2 Lookup/AI preview | `BR-002`, `BR-010`, `BR-011`; idle, invalid, synthetic preview/missing optional | High for shown states | Make Input + Button composer primary; keep preview-versus-durable-save boundary and explicit `MISSING`/`UNVERIFIED` provenance. | Bridge unavailable, cancellation and save transition are unverified; no real AI result claim. |
| G3 Search/detail | `BR-003`; synthetic populated list/detail desktop | Medium | Separate the word meaning/source identity from advanced filters and raw provenance; use progressive disclosure. | No narrow/filter URL recovery capture; source-only risks must not be written as visual defects. |
| G4 Save/edit | `BR-004`; synthetic edit desktop | Medium | Group fields with concise human-facing receipt; expose revision conflict through an explicit recovery surface and preserve draft. | Confirmed save, conflict and narrow form screenshots absent. |
| G5 Review | `BR-005`; synthetic populated front/back/rating at desktop/narrow | High for shown state | Focus-safe flashcard, one empty surface, clear due/operation status; four ratings must remain text-labelled and backend-authoritative. | Empty queue and pending/unknown operation are unverified. |
| G6 Quiz builder/runner | `BR-006`; real builder + synthetic heterogeneous runner | High for shown states | Add selected-total/progress summary; keep question-first reading order, autosave truth and writing self-score distinct from optional AI. | Resume conflict and terminal submit are unverified. |
| G7 Results/writing feedback | `BR-007`; no rendered capture | Low / blocked | Plan score summary + answer review with objective, self-score and AI advisory visibly separated. | Browser fixture for submitted result/writing feedback is blocked; never fabricate this screen. |
| G8 Status/consent/errors | `BR-008`, `BR-012`; real status; synthetic consent dialog | High for shown states | Put current local readiness and consent action before diagnostics; use explicit `ACTIVE/INACTIVE/UNKNOWN` language and progressive details. Preserve `#ai-consent`, revoke limitations and local study. | Consent section reachability, RecoveryPanel, active-vs-unknown transition and keyboard dialog matrix unverified. |
| G9 Dashboard | `BR-009`; real zero-data desktop/narrow | High for shown state | One first-run CTA and content-driven metrics; distinguish due `0`, unknown and completed; remove repeated whole-page empties. | Populated/mixed learning dashboard remains `NOT_VERIFIED`. |

## A/B critique framework

The two directions are required to differ in composition, navigation emphasis, density and visual character. The following checks are intentionally equivalent so neither direction receives an easier bar.

### Direction A — Calm Academic Workspace

**Expected thesis:** a reading-led main column, quiet surfaces and restrained emphasis. The next study action should win the squint test; status and advanced controls should recede behind clear disclosure. On desktop, an expanded grouped sidebar may remain visible when it supports orientation. On mobile, the shell should become a labelled drawer/Sheet with focus restoration. Comfortable spacing must survive long Vietnamese labels and long quiz prompts.

**Strengths to confirm in images:** readable dictionary data and writing answers; one obvious Dashboard CTA; one Review card and one empty-state surface; fewer competing borders; clear heading hierarchy; consent/error copy that is calm but unmistakable.

**Risks to test:** overly generous vertical spacing can push due metrics or actions below a 1366×768 fold; hidden diagnostics can reduce recoverability if disclosure labels are vague; an always-expanded sidebar can consume a 768px tablet; quiet colors may under-signal errors or focus if semantic tokens are weak.

### Direction B — Compact Study Console

**Expected thesis:** a compact grouped shell, denser dashboard metrics and tool/action rows for fast scanning. Navigation should make learning, vocabulary, practice and system groups explicit while keeping technical diagnostics secondary to the current task. Desktop may use a compact rail or denser sidebar; mobile must collapse into a touch-safe drawer and never rely on hover.

**Strengths to confirm in images:** fast overview of due/streak/quiz metrics; scalable group navigation; efficient search/list/detail treatment; visible progress/autosave status in quiz and review; technical detail available without leaving context.

**Risks to test:** compact controls can become icon-heavy or visually flat; dense cards may make a long Vietnamese label wrap into an unreadable strip; duplicate CTAs and status badges can compete; a split-pane or tool rail can reorder DOM/focus unexpectedly on narrow screens; contrast and 44×44 targets are easy to erode.

### Nine-group A/B inspection checklist

| Group | Direction A inspection | Direction B inspection | Failure signal (either direction) |
|---|---|---|---|
| G1 | Sidebar grouping and current-page marker remain quiet but visible; main reading column starts predictably. | Compact rail/sidebar still labels groups and exposes frequently used routes; no icon-only ambiguity. | More than one competing current-page cue, hidden route context, drawer without focus return, or future routes shown as live destinations. |
| G2 | Composer first, preview reading measure second, source/provenance in a compact disclosure. | Composer + result/tool row can be denser, but preview/save boundary and missing fields remain prominent. | AI dependency or consent buried; synthetic data presented as live; missing values rendered as successful values. |
| G3 | Search is the first task; detail reads like a dictionary entry; advanced filters collapse. | List/detail and filter controls can be denser with URL state visible. | Raw source/revision labels outrank lemma/meaning, or 320px forces horizontal scrolling. |
| G4 | Relaxed field groups and clear Save as the sole primary action; conflict details are secondary. | Compact field grid/sticky action row is acceptable if labels, errors and draft persistence remain clear. | Technical ETag/revision details replace human recovery copy, or duplicate save actions appear. |
| G5 | Single focus card, generous flip/reveal and rating rhythm; queue context is secondary. | Compact session/progress strip may sit above card; rating remains a safe, labelled action row. | Rating appears before reveal, operation is reported as saved without confirmation, or empty state repeats. |
| G6 | Question-first runner with one main answer path; autosave and submit are visibly separate. | Progress and question-type controls can be compact/always available. | Progress claims completion before terminal commit, writing self-score conflated with AI, or dense controls steal answer focus. |
| G7 | Narrative result hierarchy: score → answer review → writing self-score → optional AI advisory. | Metric strip + accordions are acceptable if each score has a plain label and source. | G7 rendered state is absent or fabricated; objective, self and AI feedback look like one grade. |
| G8 | Readiness and consent sit above technical details; accordion copy remains recoverable. | Health/consent summaries can be compact with quick status chips and expandable diagnostics. | `UNKNOWN` severity is read as an active outage, revoke action appears redundant, or local learning looks blocked by bridge status. |
| G9 | Single first-run action and compact due/streak/quiz glance above fold; no duplicated empty prose. | Denser metrics and quick actions can be above fold; cards must be semantically distinct. | Due `0` is labelled as completion without evidence, or five-plus equal-weight CTAs appear. |

## Preliminary rubric scores (hypotheses, not owner decision)

These are independent design hypotheses before image review. They are not measured usability scores and must be replaced or confirmed by the coordinator after inspecting equivalent A/B images. Scale: `0` unsupported/violates contract; `1` major ambiguity; `2` baseline with trade-off; `3` clearly demonstrated by labeled evidence.

| Criterion | A hypothesis | B hypothesis | Why this must be checked against images |
|---|---:|---:|---|
| Next-action discoverability | 3 | 2 | A should make one CTA dominant; B may expose compact action rows that compete. |
| Density and duplicate CTA/empty-state control | 3 | 2 | A naturally suppresses repetition; B must prove density is intentional rather than crowded. |
| Desktop route discoverability/scalability | 2 | 3 | B's grouped console may scale better; A needs a real future-seam/sidebar proof. |
| Small viewport reflow and long Vietnamese labels | 3 | 2 | A has more breathing room; B must prove no clipping, overflow or tiny controls at 320px. |
| Keyboard/focus/landmark/contrast provisions | 3 | 2 | Both need semantic landmarks and focus; compact/icon-heavy B carries higher risk. |
| Dictionary, quiz and writing readability | 3 | 2 | A's reading measure suits long content; B needs deliberate max widths and disclosure. |
| Consent, AI/local status and error honesty | 3 | 3 | This is a contract requirement, not an aesthetic advantage; verify both preserve unknown/blocked states. |
| Official shadcn/Radix compatibility | 3 | 3 | Both can compose existing Button/Card/Dialog and official candidates; no install is implied. |
| Future Library/Book/proficiency extensibility | 2 | 3 | B's feature groups may scale faster; A can still pass with hidden-until-enabled seams. |
| Local-first/SRS/quiz/save/revision contract preservation | 3 | 3 | Neither direction may alter behavior; inspect labels and state copy for implied changes. |

**Provisional read:** A has a slight information-reading and accessibility margin if its images keep primary actions above fold. B has a navigation/density margin if it demonstrates touch-safe, labelled controls. This is a review hypothesis only; owner approval remains pending and no hybrid is inferred.

## Responsive and accessibility review matrix

Apply this matrix to every delivered A/B image and record image IDs, observed facts and unresolved questions. A static image can demonstrate visual intent but cannot prove keyboard or WCAG conformance.

| Check | 1440×900 / 1366×768 | 1024×768 / 768×1024 | 390×844 / 320×568 |
|---|---|---|---|
| Reading order | Dashboard heading → one CTA → due/streak/quiz context; dictionary prose constrained to readable measure. | Sidebar/rail collapse does not move main heading below technical panels. | One column; heading, CTA and critical status precede secondary details; no fixed sidebar. |
| Reflow/overflow | No forced full-width prose; stable max width and fold check. | Split panes collapse at content breakpoints; quiz controls remain usable. | No horizontal scroll; long Vietnamese labels wrap or disclose; forms stack and actions remain reachable. |
| Touch/focus | Visible focus ring, target spacing, hover not required. | Drawer/Sheet and nested accordions keep focus in DOM order. | Minimum 44×44 target area; thumb-reachable primary action; drawer trigger and close return focus. |
| Semantics | One `h1`, landmarks `header/nav/main`, active route announced by text/`aria-current`. | Breadcrumb or equivalent current-location cue remains visible. | Dialog has title/description; consent choices are explicit; status changes use live region intent. |
| Contrast/state | Error/warning/unknown use text/icon + color; muted text remains legible. | Dark concept retains focus/alert contrast; badges do not carry meaning alone. | Critical warning and consent action remain visible without relying on color or hover. |
| Content extremes | Long examples, multiple meanings and form fields do not flatten hierarchy. | 200% zoom concept should avoid modal clipping and sticky action occlusion. | Long Vietnamese labels, missing IPA, blank writing and unknown status preserve explanatory text. |
| Motion | No motion is needed to understand state; honor reduced motion. | No animated collapse should steal focus. | Loading/skeleton state has textual status; no timed action without extension. |

Record the following as **design provisions**, not PASS claims: focus-visible treatment, heading/landmark order, semantic labels, color-independent status, local-first disclosure, and progressive disclosure. Automated axe, NVDA/VoiceOver, touch testing and 200% zoom remain future verification work.

## Official shadcn/UI classification

This classification follows the official-only strategy and does not authorize CLI installation or source changes.

| Candidate | Classification | Use in critique |
|---|---|---|
| Button, Card, Dialog | `ALREADY_PRESENT` | Reuse canonical local Radix/new-york primitives. |
| Sidebar, Sheet, Breadcrumb, Separator, Alert, Badge, Input, Field, Textarea, Skeleton, Accordion, Collapsible, Tabs, Progress, Radio Group, Alert Dialog, Tooltip | `OFFICIAL_PROPOSED` | Map to the exact official catalog and preserve semantic landmarks/focus behavior. |
| AppSidebar, PageHeader, ResourceHeader, StatusSummary, MetricTile, EmptyState, FilterBar, QuestionSurface, ConsentSummary | `APP_LEVEL_COMPOSITION` | Compose existing/official primitives; no database/HTTP knowledge. |
| Data Table, Chart, Calendar/Date Picker, Command palette, virtualized views | `DEFERRED` | Add only when a real current or future interaction warrants it; no speculative route or dependency. |

## Explicit unverified / blocked states

1. Direction A/B UXR-01 image assets, contact sheets and full-resolution links were absent at this pass. No pixel-level scoring, theme comparison or image-ID claim is made here.
2. G7 submitted results/writing feedback remain blocked in UXR-00; a source/test fixture is not rendered evidence.
3. Populated/mixed Dashboard, save confirmation/conflict, Review empty/pending, Quiz resume/terminal submit, Status consent deep-link/recovery and several narrow G3/G4 states remain unverified.
4. No current-app capture should be relabeled as a design mockup, and no design mockup should be relabeled as a current-app capture.
5. Impeccable context found no PRODUCT.md/DESIGN.md; this is a recorded launcher result, not a failure to use the installed skill. The required context invocation completed. No image converter was available, so PNG output is the safe expected format.

## Update protocol when image assets arrive

When `docs/design/uxr-01/assets/` or a worker-owned image directory appears:

1. Enumerate every original PNG/WebP and verify exact dimensions with a local image metadata tool.
2. Open representative desktop, tablet and mobile images for both directions; inspect light/dark and error/consent examples.
3. Replace `PRELIMINARY_IMAGE_REVIEW_PENDING` with `IMAGE_REVIEWED`, add affected image IDs and observed visual facts, and record any failures against the matrix above.
4. Send the coordinator a concise delta with image paths, responsive/accessibility observations, score changes and unresolved limitations. Do not write the integrated comparison or decision matrix from this worker.

## Coordinator handoff

Use this file as independent critique input. UXR-01 now records owner approval of Direction B and D1/D2/D3/D4/D6/D8/D9; the UXR-00 baseline remains partial, not all-green. UXR-02 and implementation remain separately gated. The critique is historical evidence and was not independently re-executed during finalization.

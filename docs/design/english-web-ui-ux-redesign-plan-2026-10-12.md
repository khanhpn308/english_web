# English Web — UI/UX source assessment and redesign proposal

**Date:** 2026-10-12 (Asia/Ho_Chi_Minh)
**Repository:** khanhpn308/english_web
**Source baseline:** `67659eea35202706e0f18e4db9c722b02921cbd0` on `main`
**Status:** `RESEARCH / DESIGN PROPOSAL ONLY — OWNER DESIGN APPROVAL PENDING`
**Scope:** Nine requested UI groups; no source code, API, schema, route, dependency, token, test or release changes authorized.
**Release policy:** Packaging source T056 already merged coding-only; defer the actual Windows build until redesign implementation and final integrated verification.

## 1. Evidence standard and limitations

The observations marked **SOURCE-CONFIRMED** follow directly from the checked-in React/CSS and repo architecture. **PROPOSAL** identifies an unapproved design choice. **PENDING VISUAL VERIFICATION** identifies claims that cannot be proved by a source read.

This study did **not** launch a browser, render screens, obtain screenshots, run Playwright, measure contrast, complete usability sessions, execute tests, connect an AI provider or observe Windows runtime. Do not infer visual quality, accessibility conformance or runtime correctness from code structure.

Authoritative product UI constraints:
- `docs/ui-architecture.md` — routes, J1–J7 journeys, consent, typed DTOs, keyboard/focus and state retention.
- `docs/adr/0004-v1-product-policy-and-operational-baseline.md` — offline study, SRS, quiz, consent, 320px/reflow/WCAG 2.2 AA and performance targets.
- `frontend/src/index.css` — existing light/dark semantic tokens. `frontend/src/app/shell.css` — document baseline.
- `frontend/src/components/ui/button.tsx`, `card.tsx` and `dialog.tsx` — current local shadcn/ui-like canonical primitives.
- Official component reference (research only): https://ui.shadcn.com/docs/components/radix/sidebar ; accessibility standard https://www.w3.org/TR/wcag/

## 2. Baseline source observations

| ID | SOURCE-CONFIRMED observation | Evidence | Design implication (PROPOSAL) |
|---|---|---|---|
| B01 | AppShell defines nine routes; six primary links are in a responsive horizontal header navigation, not a persistent sidebar. It provides skip link, route focus, a live region and ErrorBoundary. | `frontend/src/app/AppShell.tsx` | Redesign IA with desktop sidebar and mobile drawer; retain routes, focus, browser history and bootstrap semantics. |
| B02 | Core semantic light/dark colors in `index.css` are predominantly achromatic; Card and Button primitives exist, while many feature inputs use bespoke class strings. | `frontend/src/index.css`, `frontend/src/components/ui/*`, `SearchPage.tsx` | Propose a restrained branded accent and harmonize input/state primitives. Do not discard canonical shadcn foundation or install unapproved registry components. |
| B03 | Lookup has distinct input, preview, audio and save states; AI request and unknown-operation reconciliation are explicitly guarded. | `frontend/src/features/lookup/LookupPage.tsx`, `LookupResult.tsx`, `SavePreview.tsx` | Introduce stronger term/result/save hierarchy without merging preview and durable save into one misleading action. |
| B04 | Search has Vietnamese meaning, lemma, POS, verification, date, source, sort, order and page-size controls in one form. Results and filters are URL-driven. | `frontend/src/features/search/SearchPage.tsx` | Primary search row + collapsible advanced filters, visible active chips and explicit clear/reset semantics. Preserve query URL/cursor behavior. |
| B05 | Detail presents source status, revision, card state, meanings, examples, IPA and Cambridge; Edit offers repeating bilingual fields and conflict/recovery. | `frontend/src/features/search/WordDetail.tsx`, `EditWordForm.tsx` | Reader-friendly dictionary detail and grouped editor; keep source provenance, ETag conflicts, draft preservation and safe Cambridge-link policy. |
| B06 | Review exposes date-filtered queue, reveal action and four `AGAIN/HARD/GOOD/EASY` ratings. | `frontend/src/features/review/ReviewPage.tsx`, `Flashcard.tsx` | Focus-oriented study mode with visible progress and clear localized rating labels. No false flip/rating acknowledgments. |
| B07 | Quiz builder has date and three numeric type counts; runner displays question cards, autosave, pending/unknown/conflict and submit states. | `frontend/src/features/quiz/QuizBuilder.tsx`, `QuizRunner.tsx`, `QuestionRenderer.tsx` | Improve configuration preview, sticky-but-safe progress and question navigation. Do not lose any in-progress answers or alter rubric behavior. |
| B08 | Quiz Result has objective scores, question-by-question review, writing self-score, optional AI feedback and SRS notice. | `frontend/src/features/quiz/QuizResult.tsx` | Summary-first results, grouped answer analysis, separately labeled optional feedback and SRS evidence. Keep objective/self/AI scores distinct. |
| B09 | Dashboard presents due count, streak, flashcard self-rating, MCQ, Cloze and writing self-score in multiple Cards. | `frontend/src/features/dashboard/DashboardPage.tsx` | Show the next meaningful learning action above detailed statistics; never infer missing streak/accuracy as zero. |
| B10 | Status contains alerts, readiness, storage/SQLite, search, AI bridge, offline capabilities, local metrics, runbooks and separate AI-consent controls. | `frontend/src/features/status/StatusPage.tsx`, `AiConsentPanel.tsx` | Separate plain-language readiness/consent from expandable diagnostics; never hide failures or make grant look like generic settings. |
| B11 | Shared recovery handles typed errors; AI consent is a deliberate Radix/shadcn dialog with server-policy read and explicit accept/decline/revoke. | `frontend/src/shared/errors/RecoveryPanel.tsx`, `AiConsentGate.tsx` | Consistent status surfaces, recovery hierarchy and focus behavior without changing consent semantics. |

Potential maintenance concern, not a measured usability defect: some components co-locate a large volume of state and presentation (e.g. DashboardPage and StatusPage), increasing the risk of unscoped visual rewrites. Preserve state machines by isolating presentational components rather than replacing business logic during redesign.

## 3. Candidate product direction — not approved

**Direction A (recommended): Calm Academic Workspace.** A desktop learning workspace with an opt-in collapsible left sidebar, quiet neutral surfaces, one restrained accent, strong typography and dedicated study/quiz focus states. This fits the local-first single-user app and its content-heavy learning surfaces.

**Direction B (comparison alternative): Compact Study Console.** More information per screen, compact cards, persistent small navigation and advanced data prominence. Better for expert/operators, less suitable as the default learning interface.

### Design tokens for mockup exploration — proposed, not present implementation

- Palette candidate: background `#F8FAFC`, surface `#FFFFFF`, body text `#0F172A`, primary `#315BE8`; success teal, amber warning and red danger in explicitly named status roles. Confirm color and contrast in both light/dark before acceptance.
- Type: keep available OS/system fonts by default for Windows offline reliability; hierarchy proposal display 28–32px, section title 20–24px, body 16px, metadata 13–14px. Avoid tiny labels as sole critical meaning.
- Spacing scale `4 / 8 / 12 / 16 / 24 / 32 / 48` px; interactive targets design toward 44px, while WCAG 2.2 AA requirements remain authoritative.
- Content widths: main workspace up to ~1180px; focused learning text ~720–800px; sidebar candidate ~240–264px on wide screens. No fixed sidebar on narrow screens.
- Responsive study: wide screen sidebar + content; tablet collapsible sidebar; narrow 320px reflow with off-canvas drawer. No lateral scrolling for regular text, including at 200% zoom.
- Preserve semantic shadcn CSS variables, local composition and the repo's no-Preflight Tailwind baseline. Do not paste external UI blocks without dependency/license/security review.

### Proposed information architecture

`Learning` group: Dashboard (`/`), Lookup (`/lookup`), Search (`/search`), Review (`/review`), Quiz (`/quiz/new`).
`System` group: Status and explicit AI data-sharing permissions (`/status#ai-consent`).

Nested word-form detail/edit and quiz attempt/result remain same-origin routes with clear breadcrumbs/back links, not new sidebar destinations. Do not add Accounts, generic Settings, cloud sync, backup or credentials pages outside the approved v1 routes. Header can show current page, local readiness summary and a link to consent; labels must not claim a bridge outage disables local features.

## 3B. Owner component-source decision: official shadcn/ui

**New owner choice, 2026-10-12:** Use existing, official shadcn/ui components from
https://ui.shadcn.com/docs/components and install/upgrade via the established
Vite project's documented workflow at https://ui.shadcn.com/docs/installation.
This is a preferred **implementation/component policy**, not approval to
install, upgrade or replace app code in this design phase.

Technical baseline is **SOURCE-CONFIRMED**: root `components.json` has
`new-york` style, `lucide` icons, semantic CSS variables and aliases to
`frontend/src/components/ui`; React/Vite/Tailwind 4, Button/Card/Dialog
and Radix Dialog are already installed. Reuse and extend, **do not
reinitialize Vite/shadcn, blanket-replace CSS or overwrite existing components**.

Use the [official component mapping and upgrade-safe adoption policy](shadcn-ui-component-strategy-2026-10-12.md)
as a hard design handoff reference for UXR-02–11. It maps official Sidebar,
Breadcrumb, Accordion, Data Table, Date Picker, Alert, Progress, Chart etc.
to the nine screens and future Library/Book modules; requires Radix-consistent
choices, source-controlled canonical primitives, scoped CLI review/diffs
and human design sign-off. Component source changes are NOT auto-updated
by shadcn releases.

This narrows implementation choices but does **not** predetermine color
palette, component density, book feature scope, or the visual mockup to approve.

## 3A. Approved future-growth requirement: books, exercises, tags and per-book progress

**New owner requirement, 2026-10-12:** the application must eventually support
a learning Library with books, exercises inside books, vocabulary occurrences
linked to book/unit, per-book reading/completion progress, and multiple skill
tags plus typed proficiency/exam targets (e.g. Writing, Speaking, IELTS target
band, CEFR level). This is a **future extensibility requirement**, not an
authorization to add v1 Library routes or to rewrite the current backend.

Detailed, source-grounded proposal:
[Future learning content architecture](future-learning-content-architecture-2026-10-12.md).

**Consequences for this redesign:**

- **Shell / UXR-G1 and UXR-02:** do not design a fixed six-item layout that
  cannot grow. Define scalable navigation groupings: Learning, Vocabulary,
  Practice, future Library/Progress, and System. Future entries are omitted
  until actually implemented; do not ship placeholder routes.
- **Word Detail and Save / UXR-G3–G4:** keep vocabulary canonical and allow
  later contextual backlinks from a word to a book, chapter/unit and exercise.
  Do not store a duplicate word per book.
- **Review / UXR-G5:** independent SRS learning remains canonical. Later review
  filters may select linked book vocabulary without creating a separate SRS
  schedule per book.
- **Quiz / UXR-G6–G7:** reserve a presentation concept of exercise origin and
  separately versioned book exercises; do not change current `note_date`
  generated-quiz contracts or immutable snapshots as part of UI work.
- **Dashboard / UXR-G9:** leave room for additional book-progress widgets but
  do not fold book completion into due-card/streak/quiz metrics.
- **Metadata components:** use controlled multi-skill taxonomy; typed,
  scale-aware IELTS bands and CEFR levels; many-to-many tags with filter chips.
  Book-target proficiency is not measured learner proficiency.
- **No early platform rewrite:** remain single-user, local-first FastAPI +
  SQLite + React modular monolith. Future schema requires additive migrations,
  record preservation and a separately approved ADR.
- **UXR-10 review scenarios:** 0/100 books, long titles, many tags, mixed
  skills, 30-unit table of contents, word shared among three books, changed
  book edition, offline content and incomplete progress.

The illustrative navigation model below represents **future capacity**, not
approved current release pages:

```text
Học tập:      Tổng quan | Thư viện (future) | Tiến độ sách (future)
Từ vựng:      Tra cứu | Kho từ | Ôn tập
Luyện tập:    Kiểm tra | Bài tập theo sách (future)
Hệ thống:     Trạng thái | Quyền AI (trong Trạng thái)
```

## 3C. Required redesign scope: UI layout simplification & information density

**Owner evidence, 2026-10-12:** two screenshots of the currently rendered Dashboard
from local browser `127.0.0.1` at desktop width show a long sequence of large
cards and a full scroll needed to reveal the empty-state call-to-action footer.
The screenshot review is **VISUAL EVIDENCE**, distinct from earlier static-code
observations. Captures are present in the owner conversation; not copied into
GitHub (avoid bundling personal desktop captures into the repository).

**Observed in these screenshots:**
- Oversized metric cards relative to data shown, especially when learning
  history is empty; vertical whitespace creates excessive scrolling.
- A repeated zero-data/unknown message occurs in individual metric cards
  *and* the lower-page global empty state. Do not conflate genuine zero
  due cards with unknown streak or unavailable accuracy.
- Multiple repeated routes/actions such as Review and Create Quiz compete
  across cards and the footer.
- Important 'what should I learn next' action is not the dominant visual
  focal point; fine-print diagnostic explanations are highly visible.
- Top navigation and content header consume space without creating a strong
  information hierarchy. These observations apply to the supplied Dashboard,
  **not** to all nine screens without equivalent evidence.

### [UXR-02A — Layout Simplification & Information Density](../../tasks/uxr-02a-layout-simplification-information-density.md) (P0 design gate; task specification PREPARED, execution NOT STARTED)

**Scope:** a mandatory cross-screen IA/layout specification between UXR-02
(shared shell/tokens) and UXR-03–09 (individual screen redesigns). The owner
must **view actual full-resolution Dashboard desktop/mobile UI mockup images and approve the selected composition/version**, not merely a text wireframe, before feature design work proceeds. See the [UXR-02A task contract](../../tasks/uxr-02a-layout-simplification-information-density.md) and the [visual approval / Impeccable protocol](uxr-visual-approval-impeccable-protocol-2026-10-12.md).

1. **One primary action per screen.** Secondary actions live in a contextual
   menu or clear secondary placement; navigation shortcuts can exist but should
   not be repeated as equally prominent primary CTAs inside every metric.
2. **Two-level information hierarchy.** First view shows the screen purpose,
   next action and key metrics; explanatory/technical content is in named
   expandable sections, tooltips or detailed views. Keep all information
   accessible, and never hide safety/privacy-critical warnings.
3. **Content-driven card sizing.** No oversized metric cards or artificial
   equal heights when content is tiny. Use a dense `MetricTile` or
   `StatSummary` composition with restrained padding instead of default
   full-height cards for every value; retain accessible labels.
4. **Deduplicated empty state.** When the *entire learning history* is empty,
   show one main onboarding/empty-state CTA with a compact summary of the
   available zero/unknown metrics. For mixed-data situations, use **local
   contextual empties** (and do not erase valid data from unrelated cards).
5. **Semantic correctness.** Keep `0`, `— / no attempts`,
   `UNKNOWN`, and `DEGRADED` distinguishable. A minimized layout never
   implies that unknown streak is zero, optional AI feedback is final,
   unacknowledged save completed, or offline bridge down disables local study.
6. **Progressive disclosure.** Main Search shows common search fields;
   advanced filters remain reachable and visible when active. The Status
   screen shows user-facing readiness before diagnostics. Save/Edit shows
   a human-oriented success before optional receipt IDs.
7. **Responsive density.** Wide desktop: grouped KPIs, scan-friendly content;
   narrow screens: single column, keyboard focus remains visible, control
   hit targets and text remain accessible at 320px / effective 200% zoom.
8. **Reusable composition, not copy-paste.** Use official shadcn/ui
   Card, Badge, Accordion, Tabs, Separator, Skeleton, Progress, Button,
   Alert and Sidebar where appropriate; create one app-level metric
   composition, no nine unrelated card styles.
9. **Design-level targets (proposals, not audited facts):**
   - On a typical 1366×768 CSS-pixel desktop viewport at 100% zoom,
     the Dashboard's page heading, primary action and top-level due/streak
     summary should be visible without scrolling, subject to browser
     viewport chrome; don't force fixed pixel heights to game the target.
   - User can identify the next learning action within **one visual scan**
     (measured in owner walk-through, not asserted from a mockup).
   - Duplicate 'no history' paragraphs should not appear throughout
     the same initial dashboard state.
   - At 320px and 200% zoom, required actions remain reachable and no
     ordinary content overflows horizontally.
10. **Do not optimize only for density.** Readability, long Vietnamese strings,
    quiz question text, writing answer input areas, verification labels,
    consent disclosures and error recovery have higher priority than
    shrinking cards.

### Proposed Dashboard composition (design mockup only)

```text
[App Sidebar] | Tổng quan                 [Local status] [...]
              | Hôm nay nên học gì?      [Ôn tập ngay]
              | [Thẻ đến hạn 0] [Streak —] [Quiz hôm nay —]
              |
              | Hoạt động học tập
              | [ Flashcard | MCQ | Cloze | Writing ] (summary rows/tabs)
              |
              | First run only: một empty/onboarding section,
              | không lặp nội dung 'chưa có dữ liệu' trong mọi card.
```

When no cards are due, the single primary CTA may switch to Lookup or
Create Quiz according to **authoritative local data and user goal**, not
inferred personalized recommendations. All existing dashboard metrics must
remain reachable with documented meaning.

**Workflow dependencies:** UXR-00 captures the screenshots/state matrix;
UXR-01 selects direction; **UXR-02 → UXR-02A** fixes shell, density
and component contracts; UXR-03–09 then design their feature screens;
UXR-10 checks against a 9-screen content-density matrix. Do not
treat redesign as a mandate for unsafe algorithm/API/data mutations.

## 3D. UXR-00 screenshot evidence update — batch #2 (2026-10-12)

**Evidence received:** eight desktop screenshots uploaded by the owner in this conversation:
five Status/Consent segments, one Lookup idle screen, one Review empty
queue and one Quiz Builder form. Source anchors, finding IDs VIS-001–011,
design severity and proposed shadcn compositions are documented in
[UXR-00 visual audit — 8-screen capture batch](ui-visual-audit-2026-10-12-batch2.md).

Earlier Dashboard screenshots remain part of UXR-02A evidence. Distinguish
**number of screenshots** from **number of requested feature groups**:
6/9 groups now have at least one desktop visual reference when counting
shared AppShell/header (G1) and earlier Dashboard (G9). The three groups
with no direct screenshot are G3 Search/Word Detail, G4 Save/Edit,
and G7 Quiz Results/Writing Feedback. Other combined groups are only
partially captured: Lookup without AI Preview, Review without a
revealed flashcard, Quiz Builder without Runner and Status without
consent dialog/error recovery. Every captured group remains partial for unshown interaction
states and responsive viewports.

Top visual findings: Status places alarms/technical diagnostics ahead of
quick permission and local-readiness access; Review repeats the empty
queue message in two Cards; Lookup's idle composer uses a disproportionately
large container; Quiz Builder has inconsistent form/header alignment and
does not summarize selected counts. **These are layout/redesign
observations, not verified functional failures.**

UXR-00 remains `IN_PROGRESS`, not `DONE`. Wireframe work for
UXR-01/02/02A can proceed now using the observed screens; do not report
full 9-group audit or release tests as completed.

## 4. Nine screen-level design briefs

### UXR-G1 — AppShell / Sidebar / Navigation [P0, platform-wide]
**Keep:** route table and active semantics, history, skip link, focus announcer, ErrorBoundary and consent deep link.
**Propose:** expandable sidebar with clear active item, group labels, icon+text, keyboard-accessible collapse; top content header with breadcrumb and concise local status; off-canvas mobile navigation with focus management; default content padding responsive.
**Acceptance mockups:** 320/768/1024/1440 widths; collapsed, expanded, selected, deep route, 404, keyboard-only and long Vietnamese label. Focus cannot disappear behind drawer/sticky UI.
**Risk boundary:** no change to bootstrap, routes, active quiz attempt ID, or session and link navigation semantics.

### UXR-G2 — Lookup & AI Preview [P1]
**Keep:** term validation; AI policy/consent gate; noncommittal preview, field-verification provenance; native local audio; operation reconciliation.
**Propose:** prominent search input and CTA, phase-specific progress with copy that distinguishes local readiness versus provider availability; result as dictionary-style word family with bilingual tabs/sections (not hidden important fields); single clear 'Lưu vào ôn tập' transition; compact source/provider meta in expandable details.
**Design variants:** idle/empty, checking policy, awaiting consent, AI unavailable, loading/canceled-wait, result with missing fields, success, UNKNOWN reconciliation.

### UXR-G3 — Search & Word Detail [P1]
**Keep:** all supported filters, URL query/cursor, verification and source labels, safe external link and independent detail route.
**Propose:** main Vietnamese/lemma search row; expandable filters grid and removable active filter chips; results as scannable lemma / meaning / source / verification rows; detail heading with IPA/audio status, bilingual meanings and examples, provenance/reading mode.
**State coverage:** browse/no query, zero results, slow local API, expired cursor, stale source, detail missing, return-to-search preservation.

### UXR-G4 — Save & Edit Vocabulary [P1]
**Keep:** all-preview forms, note-date choice, existing-source preconditions, revision/ETag conflict, unknown mutation reconciliation, draft inputs.
**Propose:** 2-step preview→save treatment; save summary with human-readable action result and collapsible technical receipt; add/remove meaning/example editor with stable labels, field grouping and visible unsaved indicators.
**State coverage:** dirty draft, validation failure, missing source, revision conflict, unknown result, acknowledged success, keyboard deletion.
**Never:** silent overwrite, repeat a mutation solely to clear a spinner, truncate or drop unknown Markdown fields.

### UXR-G5 — Review Flashcards [P1]
**Keep:** due/date logic, four SRS ratings, source restrictions and durable acknowledgment before moving to the next card.
**Propose:** focused centered card, conspicuous reveal interaction, progress position and remaining count when the server can authoritatively provide it; translated rating controls with optional Again/Hard/Good/Easy annotation; shortcut hints only if accessible and separately approved.
**States:** hidden/revealed, pending rating, empty queue, source-invalid card, uncertain operation, successful next-card transition.

### UXR-G6 — Quiz Builder & Runner [P1]
**Keep:** quiz date, MCQ/Cloze/Writing counts, immutable snapshot, writing rubric/self-score, 500ms autosave semantics, per-question conflict/reconcile, protected submit.
**Propose:** builder as one brief setup card with counts summary and source sufficiency guidance; runner with attempt heading, progress/question navigator, per-question saved indicator, clear submit prerequisites, sticky actions only when they never obscure focus.
**States:** insufficient material, provider failure, created attempt, in-progress/dirty/saving/acknowledged, UNKNOWN, REVISION_CONFLICT, submission reconciliation.
**Never:** present an unacknowledged draft as saved; reveal hidden answer keys pre-submit; override self-score from AI feedback.

### UXR-G7 — Quiz Results & Writing Feedback [P2]
**Keep:** objective MCQ/Cloze accuracy, writing self-score, answer explanations, terminal submission identity, SRS handoff and optional consent-gated AI feedback/history.
**Propose:** result summary top; grouped collapsible per-question explanation; separate panel 'Phản hồi AI (tùy chọn)' with request history; explicit distinction objective grading vs learner self-rating vs advisory AI commentary.
**States:** never submitted, loading, submitted no result, valid result, optional feedback disabled/failed/ready, historical source deleted.

### UXR-G8 — Status / Consent / Error States [P1]
**Keep:** honest readiness and alerts, no-secret telemetry, consent view/grant/revoke, stale/unknown and fail-closed states, runbook link, error recovery actions.
**Propose:** two levels on same `/status` route: user-facing 'Học cục bộ / AI tùy chọn / cần xử lý' summary first, technical diagnostics under explicit disclosure; consent remains a dedicated high-visibility section and dialog; reusable callouts for loading/empty/warning/failure/unknown.
**Never:** let green UI imply missing evidence is PASS, infer provider approval, hide DEGRADED or automatically re-grant/retry AI.

### UXR-G9 — Dashboard [P1]
**Keep:** authoritative due count, streak definition, separate flashcard/MCQ/Cloze/writing stats, null/unknown distinctions, refresh triggers.
**Propose:** hero 'Hôm nay nên học gì?' deriving one primary CTA only from valid local data, compact due-card/streak glance metrics with truthful 0/unknown distinctions, progressive-disclosure detailed result breakdown, and exactly one top-level onboarding empty state when every learning-history metric is empty. Do not force equal card heights or duplicate empty-state explanations and CTAs.
**States:** first-run zero data, ready, storage busy, stale/invalid response, null streak, incomplete results; no invented performance trends or analytics.

## 5. Design-only work plan and task boundaries

These are **proposed UXR IDs**, NOT canonical application T IDs. **The owner has authorized autonomous research execution for UXR-00 only** (2026-10-12); the actionable task contract is [UXR-00 — Astra-led autonomous visual audit](../../tasks/uxr-00-autonomous-visual-audit.md). Other design phases, code changes and owner design-direction sign-off remain separate approvals. Do not add UXR IDs to the canonical `tasks/todo.md`.

| Work package | Depends on | Output | Relevant owner files to read (no edits yet) |
|---|---|---|---|
| UXR-00 Evidence capture and journey inventory | None | Browser screenshot/state matrix and source-to-journey trace; status 'unverified' where Windows startup blocked | app shell, existing E2E fixtures, ui-architecture |
| [UXR-01 Design direction approval](../../tasks/uxr-01-design-direction-owner-approval.md) — **task specification PREPARED; execution NOT STARTED** | **UXR-00 final handoff** | Two comparable design directions, scored comparison and explicit owner decision | CSS tokens, shell, design docs |
| [UXR-02 Foundation and AppShell spec](../../tasks/uxr-02-design-foundation-appshell-specification.md) — **task PREPARED, execution NOT STARTED** | **UXR-01 owner visual direction sign-off** | **Full-resolution image mockups of AppShell desktop/tablet/mobile + owner visual approval**, navigation IA, official shadcn adoption matrix, token proposal, accessible shell rules and actual Impeccable use evidence | AppShell.tsx, shell.css, index.css, components/ui; future-learning-content-architecture; shadcn-ui-component-strategy; visual-approval-impeccable-protocol |
| [UXR-02A Layout simplification and density](../../tasks/uxr-02a-layout-simplification-information-density.md) — **task PREPARED, execution BLOCKED until UXR-02 visual sign-off** | **UXR-02 owner-approved foundation images** | G1–G9 compact hierarchy, CTA/empty-state deduplication, truthful 0/null/UNKNOWN, **Dashboard first-run/populated + Review empty + Status/Consent desktop/mobile full-resolution images and separate owner visual approval**, Impeccable proof and official shadcn mapping | DashboardPage.tsx, ReviewPage.tsx, StatusPage.tsx; UXR-02 frozen shell; visual-approval-impeccable-protocol |
| [UXR-03 Lookup, Search & Word Detail Design](../../tasks/uxr-03-lookup-search-word-detail-design.md) — **task PREPARED, execution NOT STARTED** | **UXR-02A owner visual-density sign-off** | **≥18 actual full-resolution UI mockup frames + owner visual approval** for G2/G3 Lookup/AI Preview, Search filters/pagination and Word Detail/source validity; consent/UNKNOWN safeguards, preserved URL cursor/deep-link state, Impeccable per-worker evidence and official-only shadcn mapping | LookupPage.tsx, LookupResult.tsx, AudioButton.tsx, SearchPage.tsx, WordDetail.tsx; UXR-02/02A approved layout; shared visual/Impeccable protocol |
| [UXR-04 Save & Edit Vocabulary Design](../../tasks/uxr-04-save-edit-vocabulary-design.md) — **task PREPARED, execution NOT STARTED** | **UXR-02A owner-approved visual-density images** | **≥20 full-resolution desktop/mobile Save/Edit/Conflict UI mockups + independent owner visual approval**, new vs existing source/date/ETag preconditions, preserved draft and UNKNOWN operation, validated Markdown/card receipt, source conflict comparison, Impeccable per-worker evidence and official-only shadcn mapping | SavePreview.tsx, EditWordForm.tsx, RevisionConflictDialog.tsx, WordDetail.tsx; ADR-0005 C013-04/05; shared visual policy |
| UXR-05 Review spec | UXR-02A | Reveal/rating/progress wireframes for G5 | ReviewPage.tsx, Flashcard.tsx |
| UXR-06 Quiz Builder/Runner spec | UXR-02A | Setup/progress/autosave/failure wireframes for G6 | QuizBuilder.tsx, QuizRunner.tsx, QuestionRenderer.tsx |
| UXR-07 Results/Feedback spec | UXR-02A | Scoring/splitting/feedback history wireframes for G7 | QuizResult.tsx, FeedbackPanel.tsx |
| UXR-08 Status/Consent/Errors spec | UXR-02A | State taxonomy and diagnostics disclosure for G8 | StatusPage.tsx, AiConsentGate.tsx, RecoveryPanel.tsx |
| UXR-09 Dashboard spec | UXR-02A | Daily-workflow and statistics wireframes for G9 | DashboardPage.tsx |
| UXR-10 Cross-screen design QA | UXR-03–09 | Component-state and information-density matrix, responsive/keyboard/accessibility review, action/empty-state deduplication and UX consistency report | all nine groups; UXR-02A criteria |
| UXR-11 Owner sign-off and implementation handoff | UXR-10 | Approved screens, mapping to scoped coding tasks, file ownership and merge order | design artifacts only |

### Mandatory owner-visible design previews, installed Impeccable and official shadcn/ui

**Binding owner requirement (2026-10-12):** This is a major, final redesign and cannot be signed off by written plans alone. Read and apply the [visual-approval / Impeccable / official-components protocol](uxr-visual-approval-impeccable-protocol-2026-10-12.md) across **UXR-01, UXR-02, UXR-02A, UXR-03–11**.

- **UXR-01 visual direction gate:** A/B options include high-fidelity **actual owner-viewable image screenshots** of the proposed Dashboard, vocabulary, Review/Quiz and Status/Consent screens; owner explicitly selects A/B/hybrid based on images. No screenshots = no approved direction.
- **UXR-02 shell gate:** full-resolution **visual mockups** show desktop expanded/collapsed Sidebar, tablet, mobile menu open/closed, a real composed Dashboard/feature page, light/dark, long labels, local-versus-AI status and 320px adaptation. Owner must view and approve the AppShell design version **before UXR-02 is DONE**.
- **UXR-02A density gate:** mandatory **rendered screenshots** for first-run + populated compact Dashboard, compact Review empty state and Status/Consent information hierarchy on desktop/mobile; owner approval required before UXR-03–09 begin. The [UXR-02A task specification](../../tasks/uxr-02a-layout-simplification-information-density.md) fixes a **minimum 12 primary full-resolution frames plus 2 alternative Dashboard frames**, semantic case matrix, 320px stress treatment, authentic baseline provenance and signed variant/version decision. These are **future execution deliverables**, not screenshots created by this documentation commit.
- **UXR-03–09 per-feature gate:** each worker produces screen/state screenshots, including meaningful populated content and empty/error/unknown states where relevant. Owner must approve each feature's visible design, even if seven worker design tasks can run in parallel. **UXR-04 specifically** requires [its Save/Edit task contract](../../tasks/uxr-04-save-edit-vocabulary-design.md): **≥20** desktop/mobile full-resolution images, including source ABSENT/VALID/blocked, source revision conflict and UNKNOWN save reconciliation; all forms saved atomically via authoritative receipt and no unapproved overwrite. Original G4 owner capture is **NOT_VERIFIED** until UXR-00 shows actual screenshots. **UXR-03 specifically** requires [its screen-state/visual task contract](../../tasks/uxr-03-lookup-search-word-detail-design.md): at least 18 desktop/mobile Lookup, Search and Word Detail images (plus responsive/variant comparisons); AI preview never counts as saved, Search preserves URL/cursor state, invalid-source detail cannot offer Edit, and missing current G3 screenshots remain explicitly NOT_VERIFIED.
- **UXR-10 / UXR-11:** nine-group contact-sheet and linked full-resolution gallery, responsive/semantic UI comparisons and recorded owner decisions. UXR-11 requires the **final explicit owner sign-off of all nine screen groups** before any code implementation handoff is treated as approved.
- **Impeccable required, not optional:** the owner reports [Impeccable](https://github.com/pbakaus/impeccable) is **already installed locally**. Do not install/update it. The actual Codex coordinator **and every worker** must discover their installed skill, read its SKILL.md, execute its `context` launcher once per session and apply relevant `shape/critique/layout/distill/adapt` guidance per the installed references, recording **evidence of actual invocation and its effect on the UI proposal**. GitHub-only authoring of the task docs is **not** a claim to have invoked the owner's Windows skill. If it is not accessible to a worker, disclose `IMPECCABLE_NOT_ACCESSIBLE` and block false approval.
- **Official-only shadcn policy:** all missing reusable UI components are proposed from https://ui.shadcn.com/docs/components, compatible with existing Radix/new-york/Tailwind 4 setup. Reuse canonical installed primitives; no registry substitutions or component-install commands during design preparation. Approved implementation later reviews specific official CLI diffs without overwriting existing components.
- **Screenshot provenance:** distinguish current-app capture, rendered/synthetic mockup and not-verified. PNG/WebP previews and full-resolution links are required; ASCII/Markdown wireframes, diagrams or code alone do **not** satisfy an image-based approval checkpoint.
- **Scope:** visuals are **isolated design assets/prototypes only** until owner authorizes implementation; no code, API, database, packaging, main merge or acceptance-PASS claims from a visual mockup.

### UXR task-card preparation — 2026-10-12

- **[UXR-04 prepared task card](../../tasks/uxr-04-save-edit-vocabulary-design.md):** `PREPARED / NOT STARTED / BLOCKED_BY_UXR_02A_OWNER_VISUAL_SIGNOFF`. Owner approved task-file preparation and roadmap/PR metadata only. Execution requires independently confirmed UXR-00/01/02/02A evidence and owner design permissions; actual G4 Save/Edit screenshots need separate owner approval. It preserves conditional source/ETag/idempotency, save operation reconciliation, drafted bilingual edits and safe conflict resolution. G4 currently has no direct owner screenshot; do not claim any local Impeccable invocation, shadcn install, visual mockup or code/test from this preparation commit.


- **[UXR-03 prepared task card](../../tasks/uxr-03-lookup-search-word-detail-design.md):** `PREPARED / NOT STARTED / BLOCKED_BY_UXR_02A_OWNER_VISUAL_SIGNOFF`. Owner authorized task Markdown preparation, roadmap and Draft PR updates only. Later design execution requires the UXR-00→01→02→02A owner-verified gates and separate execution authorization. Its G2/G3 full-resolution UI designs demand an additional owner visual sign-off. `SavePreview` and `EditWordForm` interaction/conflict design remain **UXR-04**, not UXR-03. No mockup images, installed Impeccable invocation or official shadcn component acquisition is claimed from this documentation commit.


- **[UXR-02A prepared task card](../../tasks/uxr-02a-layout-simplification-information-density.md):** `PREPARED / NOT STARTED / BLOCKED_BY_UXR_02_VISUAL_SIGNOFF`. Owner approved drafting the task file; UXR-02A execution/owner visual approval/UXR-03–09 dispatch remain separately gated. This documentation change does not generate mockup screenshots, execute the locally installed Impeccable skill or add shadcn components.

- **[UXR-01 task specification](../../tasks/uxr-01-design-direction-owner-approval.md):** `PREPARED / NOT STARTED / BLOCKED_BY_UXR_00`. Drafting the task is authorized; **running UXR-01 requires the verified UXR-00 report/readiness handoff plus separate owner execution authorization**. This is the stricter dependency in the current project handoff. Older wording in §3D about sketching while UXR-00 runs means preliminary ideation only, **not** permission to execute, sign off, or mark either task DONE.
- UXR-01 output requires a side-by-side A/B comparison and explicit owner selection; UXR-02 and UXR-02A remain separate, later approval gates. The existing nine-group evidence limitations, including G3/G4/G7 without direct screenshot, remain in force until updated by UXR-00 evidence.
- **UXR-12 — Proposed Redesign Implementation Planning:** assessed as a potentially useful **post-UXR-11** implementation-planning phase for scoped coding work packages, worktree ownership, dependency waves, integrations and release gates. **Not approved, not in the established UXR-00–11 roadmap and not authorized for execution or new features.** UXR-11 signs off the design; a future UXR-12 would only structure the subsequent implementation program after separate owner approval.

The independent feature briefs UXR-03 through UXR-09 can proceed in parallel **after** UXR-02 and UXR-02A fix the shared component, navigation and density contracts. Source implementation should later be assigned to independent worker worktrees by non-overlapping files; one integration owner controls AppShell, design tokens and shared primitives. No agent changes generated DTOs, API schemas, SQLite, consent rules or release tooling solely for a visual task.

## 6. Required visual evidence before claiming an actual UI problem

For each screen collect viewport/zoom screenshots at 320 / 768 / 1024 / 1440 CSS px, light/dark where supported, plus empty/loading/success/error/unknown state.

**Evidence ledger:** User-supplied desktop screenshots from 2026-10-12 cover Dashboard (earlier batch) and partial Status, Lookup, Review and Quiz Builder states (batch #2). See [audit report](ui-visual-audit-2026-10-12-batch2.md). Further screenshots/screens are still needed; the image widths are file pixels, not verified CSS viewport widths. Use synthetic learning data and fake bridge; do not enter real credentials or import personal study records.

Use an evidence register: `screen + state + viewport + screenshot link + observed issue + user impact + severity + source anchor + proposal + owner decision`. A visual defect remains `PENDING_VISUAL_VERIFICATION` until actually observed. Source-driven issues can still be accepted as redesign opportunities without being misreported as observed bugs.

### Design acceptance contract (pre-code)

1. Owner chooses design direction, nav/sidebar behavior, palette, density, and approves representative desktop/mobile wireframes before coding.
2. Every requested screen has loading, empty, content, recoverable, terminal and uncertainty treatments appropriate to its APIs; controls have explicit label/primary action.
3. The nine-route map, URL query persistence, source verification badges, SRS semantics, quiz terminal/result rules and consent fail-closed behavior are preserved.
4. Design specifies keyboard tab order, focus for overlay/route, visible focus, contrast checks and reflow through 320px/200% zoom.
5. Navigation and core learning tasks require no invented product surfaces (account, backup, settings, paid provider). Technical metadata stays available to operators without crowding primary learning content.
6. Design handoff maps each new component to presentational-only ownership and explicit acceptance scenarios. **No source implementation begins before owner sign-off.**
7. Every screen includes a content-density and action-hierarchy review against UXR-02A; the provided real Dashboard screenshots anchor the first visual comparison. Explicitly avoid duplicated full-page empty states and oversized no-data cards.

### Release gates deferred until after approved UI implementation

WCAG 2.2 AA evidence (contrast 4.5:1 normal text, 3:1 large text/non-text UI as applicable, 1.4.10 reflow and 2.4.11 focus visibility), keyboard journeys, visual screenshots, Playwright/Vitest, backend regression, Windows launcher smoke, packaging and dependency remediation remain separate executable checks. No security/a11y/performance PASS is claimed here.

## 7. Decisions awaiting owner

- **D1:** Adopt Direction A (Calm Academic Workspace), or Direction B (Compact Study Console)?
- **D2:** Desktop sidebar expanded by default or collapsed by default? Recommended expanded when width allows; mobile drawer.
- **D3:** Accent exploration: restrained indigo (recommended) or teal; light default with supported dark theme.
- **D4:** Content density: comfortable study default (recommended) versus compact list mode optional.
- **D5:** Quiz Runner: all questions on one page (existing flow) versus one-at-a-time navigation; do not decide without mapping autosave/focus/accessibility and owner approval.
- **D6:** Confirm desired visual reference examples/screenshots from the owner. Current repository source does not include an approved screenshot target in this research record.
- **D7:** For the future Library, define first import format and reading needs (manual metadata, PDF/EPUB assets or external references), book exercise type support and completion criteria. These are architecture decisions, NOT v1 redesign blockers; see the linked future-learning-content document.
- **D8:** The official shadcn component library is selected as the design-system source. Confirm individual additions (especially Sidebar and large interaction primitives) via representative wireframes and a scoped CLI diff before implementation; no automatic overwrite.
- **D9:** Approve cross-screen UXR-02A simplification: compact KPI composition, one primary CTA, deduplicated empty state, contextual advanced details. Exact dashboard layout still requires owner sign-off.

**Current outcome:** Source audit and design direction proposals prepared; static code observations supported, runtime visual assessment pending. No app code changed, no acceptance gates executed, no tasks added to the canonical checklist.
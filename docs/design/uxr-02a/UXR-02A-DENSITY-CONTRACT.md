# UXR-02A Density Contract

**Version:** `UXR-02A-DENSITY-1.0-DRAFT`
**State:** owner visual approval pending
**Foundation lock:** UXR-02-R2 + HM-FIX; Dashboard row topology is frozen.

**Owner A12 requirement:** Study-history date cells must have equal rendered width/height with consistent gaps. Center a square or near-square heatmap block in its existing panel across desktop, tablet, mobile and both themes. Preserve all 105 date/count associations, five levels, zero/UNKNOWN distinction and hover/focus/tap/keyboard behavior. Non-data padding slots must remain distinct from dates. See [A12 measured evidence](UXR-02A-R1-A12-SQUARE-REPORT.md).

## Cross-screen rules

1. **One contextual primary.** Each screen/state has at most one visually dominant action. Save, submit, cancel, revoke/grant, retry, reconciliation and navigation remain available when their contract requires them. A blocked or unknown operation presents a truthful reason and safe recovery action.
2. **First viewport answers three questions.** The user sees purpose, safe next action (or why it is unavailable), and the critical state summary before secondary diagnostics.
3. **Group by meaning.** Use proximity and one shallow surface hierarchy. Avoid nested cards; use separators and compact metric groups for related facts.
4. **Density follows task frequency.** Dashboard and Status use console density; Review and Quiz use a focused 680â€“800px measure; long Vietnamese explanations use a 720â€“840px reading measure; forms stack when labels or errors wrap.
5. **Progressive disclosure is explicit.** Technical details, source revisions, bridge diagnostics, performance metrics and runbooks enter labeled `DisclosureGroup`/Accordion sections. Active critical alerts and privacy disclosures never enter a hidden section.
6. **Empty is not zero.** `UNKNOWN`, `NOT_READY`, missing, null and confirmed zero use different labels and visual treatments. Empty explanatory prose appears once per screen surface.
7. **Content extremes are first-class.** Vietnamese strings wrap within the content column; no ellipsis is used for a warning, source/evidence badge or consent state. Long examples can expand without fixed-height clipping.
8. **Responsive structure is real reflow.** Desktop two/three-column relationships collapse to one column at â‰¤767px; tablet uses two readable columns; 200% zoom is treated as narrow reflow. DOM/focus order follows visual order.
9. **Touch and keyboard remain usable.** Interactive targets have a 44px intent area; focus ring is visible and not clipped; skip link, one `h1`, live-region announcements and deep-link focus remain required implementation work.
10. **No invented product surfaces.** Future Library, Books, IELTS, TOEIC and CEFR are annotations only.

## G1â€“G9 action and information matrix

| Group | Route/state | Primary task | Dominant action | Essential first viewport | Secondary information | Critical always-visible state | Allowed disclosure | Official component candidate | Future task owner |
|---|---|---|---|---|---|---|---|---|---|
| G1 AppShell | all routes / mobile drawer | orient and navigate | current route navigation | brand, active group, page title, local/AI state | breadcrumbs, account placeholder, collapsed labels | status + consent access | drawer details, future groups | Sidebar, Sheet, Breadcrumb, Separator | AppShell / implementation task |
| G2 Lookup | `/lookup` idle/preview | find a word | Tra tá»« | labeled input, one search/lookup CTA, result readiness | pronunciation, source, examples | validation/error and source status | provenance and optional fields | Input, Button, Badge, Alert, Collapsible | UXR-03 |
| G3 Search / Detail | `/search`, `/word-forms/:id` | compare and verify a meaning | Open detail / Search | query, result count/state, selected word, source badge | examples, related forms, history | source/evidence limit and revision | advanced filters, related data | Input, Table, Badge, Accordion | UXR-03 |
| G4 Save / Edit | save/edit/conflict | preserve a draft and commit | Save changes | editable fields, source context, save state | revision/ETag, audio, provenance | unsaved/conflict/error status | technical revision and receipts | Textarea, Input, Button, Alert, Dialog | UXR-04 |
| G5 Review | `/review` empty/loading/unknown | act on the dated queue | Start review when queue exists; Tra tá»« má»›i when empty | noteDate filter, reset, queue summary, one state explanation | keyboard/live status, route history | EMPTY/LOADING/ERROR/SUBMITTING/UNKNOWN | reconciliation details | Input/Date Picker, Button, Badge, Alert | UXR-05 |
| G6 Quiz Builder / Runner | `/quiz/new`, `/quiz/:attemptId` | compose or answer a quiz | Start quiz / Submit | selected total or question progress, answer controls, autosave state | question metadata, draft history | snapshot/autosave/UNKNOWN semantics | help, technical receipt | Card, Button, Progress, Radio Group, Alert | UXR-06 |
| G7 Results / Writing Feedback | result/feedback | understand performance | Review feedback | objective score and writing self-score separately | answer review, optional advisory, history | submitted/partial/error/provider status | diagnostics and detailed feedback | Card, Badge, Tabs, Accordion, Alert | UXR-07 |
| G8 Status / Consent | `/status`, `/status#ai-consent` | know readiness and permissions | Open AI consent / safe recovery | local readiness, AI readiness, active alerts, consent entry | storage/source, offline matrix, metrics, runbooks | privacy alert, consent state, UNKNOWN/DEGRADED | all diagnostics behind named disclosure | Alert, Badge, Collapsible, Accordion, Separator, Dialog | UXR-08 |
| G9 Dashboard | `/` first-run/populated/mixed/degraded | choose the next learning step | contextual learning CTA | purpose, CTA/reason, due and streak glance | four rows of charts/history/activity | nullable/unknown semantics and local state | chart detail, long history | Card, Button, Badge, Progress, Skeleton, Tooltip | UXR-09 |

### Compact composition examples

**G2 Lookup idle:** one labeled input and one `Tra tá»«` button share a compact composer row at desktop; on mobile they stack. Provenance and optional fields use a labeled disclosure. Invalid input keeps the field error adjacent and does not add a second global empty card.

**G6 Quiz Builder:** title, selected-total `StatSummary`, question list and one `Báº¯t Ä‘áº§u quiz` CTA. Secondary reset/cancel stay text-level. Runner uses progress plus autosave state above the answer surface; result/UNKNOWN recovery is never presented as a successful submit.

## Reusable app-level contracts (future, no React files in UXR-02A)

| Composition | Required slots | Density behavior | Unknown/empty rule |
|---|---|---|---|
| `MetricTile` | label, value, unit, state, note | 4-up desktop, 2-up mobile when labels fit | show `â€”`, `ChÆ°a cÃ³ dá»¯ liá»‡u` or `UNKNOWN`, never invented zero |
| `StatSummary` | heading, value, qualifier, source | inline group for related metrics | qualifier names the source/meaning |
| `FilterToolbar` | labeled date/query, reset, queue/result summary | wrap at tablet/mobile | preserve URL contract; reset is secondary |
| `CompactFormSection` | label, control, help, error, save state | one or two columns by content measure | warning/error remains adjacent to field |
| `EmptyState` | icon, explanation, contextual CTA, live status | one visible explanatory surface | visible prose once; live announcement may remain separate |
| `DisclosureGroup` | named summary, content, focus target | collapsed by default for diagnostics | critical alert/privacy copy stays outside |
| `StatusSummary` | local state, AI state, alerts, consent link, recovery | two cells desktop, stacked mobile | local READY is independent from AI UNKNOWN/DEGRADED |

## Responsive and accessibility requirements

- `1366Ã—768`: D1 proves heading, next action/reason, due and streak in the first viewport without fixed-height compression.
- `1024Ã—768`: keep the R2 rail and reduce content columns only where labels remain readable.
- `768Ã—1024`: use two readable columns for Dashboard, single focused column for Review/Quiz.
- `390Ã—844` and `320Ã—568`: drawer trigger replaces rail, one-column route content, stacked controls, no ordinary horizontal scroll.
- `200%` browser zoom: effective narrow width; collapse columns, preserve action order, focus visibility and long-string wrapping.
- These are design requirements; no runtime WCAG or screen-reader PASS is claimed by mockups.

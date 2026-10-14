# English Web — UXR-00 visual evidence review #2 (8 desktop screenshots)

**Date:** 2026-10-12 (Asia/Ho_Chi_Minh)  
**State:** `PARTIAL VISUAL AUDIT — OWNER-SUPPLIED SCREENSHOTS`  
**Design-only:** no React/TypeScript/CSS/API/backend changes, tests, live-browser observation or acceptance claims.  
**Source baseline:** `main` at `67659eea35202706e0f18e4db9c722b02921cbd0`; findings cross-checked with source components.  
**Parent:** [9-group redesign plan](english-web-ui-ux-redesign-plan-2026-10-12.md); [shadcn/ui strategy](shadcn-ui-component-strategy-2026-10-12.md).

## 1. Evidence provenance

User provided 8 images through the ChatGPT conversation. They are **not checked into GitHub**; filenames below allow the owner to match them to the original attachments. They are desktop screenshots circa 1915–1917 pixels wide (image pixels, not validated browser CSS viewport), Windows Chrome and Vietnamese UI.

| Capture | Visible surface | What can be evaluated |
|---|---|---|
| `image(20261012-071302-1).png` | Status lower screen: Runbooks and AI data-sharing controls | Info density, ordering, consent copy |
| `image(20261012-071307).png` | Status: local metrics / Runbooks / part of Consent | Card density, repeated explanatory text |
| `image(20261012-071310).png` | Status: offline feature capability matrix and metrics | Table density, labels and scanability |
| `image(20261012-071316).png` | Status: Markdown/search index and AI Bridge readiness | Diagnostic prominence and terminology |
| `image(20261012-071336).png` | Lookup: initial input state | Empty layout, CTA hierarchy, help/status text |
| `image(20261012-071349).png` | Review: filtered empty queue | Duplicate empty messages, date control |
| `image(20261012-071424).png` | Status: top-level alerts including 'API không phản hồi' | Alarm hierarchy, warning severity versus unknown activation |
| `image(20261012-071448).png` | Quiz Builder: date and type-count form | Width, alignment, count context |

Earlier owner-provided Dashboard screenshots dated `20261012-064645` and `20261012-064657` support a **separate** finding for overlarge/duplicated cards in Dashboard and are summarized in the parent UXR-02A plan. They are **not** silently counted as part of the eight new captures.

Important: Captures do not prove backend faults, AI connectivity, focus handling, React responsiveness, form submission, contrast pass or mobile accessibility. The capture sequence covers **four feature surfaces** (Status/Consent, Lookup, Review, Quiz Builder), not eight different feature groups. Shared AppShell/header is visible across multiple captures and separately supplies G1 layout evidence. The earlier Dashboard supplies G9.

## 2. Prioritized findings with source anchors

Priority refers to **redesign urgency**; not a measured incident, security failure or production defect.

| ID / priority | Visible evidence | Source cross-reference | Design response | Mandatory safeguard |
|---|---|---|---|---|
| VIS-001 / P0 | Status top displays long standalone alert cards; 'API không phản hồi' lists **severity if activated** yet actual observation is 'chưa xác định'. On first glance, this reads like an active outage, though screenshot does not confirm one. | `frontend/src/features/status/StatusPage.tsx` — `localAlerts.items`, alert severity/state/observation | Compact **current** health summary with explicitly distinct `ACTIVE / INACTIVE / UNKNOWN` and expandable conditions/runbooks; severity only describes conditional impact, not actual alarm state | Never convert insufficient observations into PASS/FAIL; never hide an active critical alarm |
| VIS-002 / P0 | Status requires extensive scrolling through separate cards for alerts, storage, source, bridge, offline, metrics, runbooks before reaching AI consent in the captured lower portion. | `StatusPage.tsx` and `AiConsentPanel.tsx` | Two-layer layout: above-the-fold local learning and AI permission summary + anchor to `#ai-consent`; collapse diagnostics by category `Health / Storage / AI Bridge / Offline / Metrics / Runbooks` | Keep `/status#ai-consent` deep link, manual refresh, complete diagnostics and policy access |
| VIS-003 / P1 | Status repeats raw technical words/revisions/statuses (`NOT_READY`, `REVOKED`, `Revision 1`, `p50/p95/p99`) in primary reading hierarchy and includes English incident instructions inside Vietnamese UI. | `StatusPage.tsx`, `AiConsentPanel.tsx` | Plain-language labels and meaningful short summaries; raw codes/IDs and runbook technical instructions under labelled expandable details | Preserve exact statuses for troubleshooting; translations must not claim service is available |
| VIS-004 / P1 | Consent screenshot shows `REVOKED` and a prominent red 'Rút lại quyền...' action simultaneously, which might look redundant; policy is incomplete. | `frontend/src/features/consent/AiConsentPanel.tsx` | Consent status badge and action hierarchy based on **server-authoritative** status; potential disabled/secondary already-revoked action only after reviewing backend idempotency and transition rules | Don't alter grant/revoke semantics, fail-closed policy, unresolved operation recovery, or pretend a revocation deletes already-sent content |
| VIS-005 / P1 | Offline matrix has eight long rows, repeated 'Khả dụng ngoại tuyến (Có)' and 'Cần mạng/Không hỗ trợ (Không)' text and a full explanation column. | `StatusPage.tsx`, `offlineCapabilitiesList` | Summary groups 'Học không cần mạng' / 'Cần AI Bridge'; expandable comparative capability table for technical details | Never imply local functions require bridge/network; browser speech support remains browser dependent |
| VIS-006 / P0 | Review empty state is duplicated: status paragraph inside 'Bộ lọc ôn tập' and a second standalone card repeating no due/unlearned cards. | `frontend/src/features/review/ReviewPage.tsx` — `view.message` and `phase === 'empty'` | Compact date filter toolbar + **one** prominent empty card/feedback surface; place technical queue count in accessible details | Preserve ARIA live announcements, queue evidence, eligibility and backend-authoritative due state; don't suppress critical status/focus |
| VIS-007 / P2 | Review date input displays `mm/dd/yyyy` in screenshots despite Vietnamese interface. This may result from the user's OS/browser locale; source uses native `<input type="date">`. | `ReviewPage.tsx` — `review-note-date` | Evaluate official shadcn Date Picker/localized rendering **only if** it improves accessibility, locale clarity and keyboard operation; keep native date alternative in scope | Do not assert a date parsing bug from a screenshot; preserve ISO `YYYY-MM-DD` URL/state |
| VIS-008 / P1 | Lookup initial state has a full-width tall Card for one text input, one button and two explanatory/status paragraphs; large surrounding empty canvas. | `frontend/src/features/lookup/LookupPage.tsx` `lookup-term`, `lookup-help`, `lookup-status` | Compact hero/search composer with shadcn Input + Button, single concise helper at idle, preview content in a separate results region when available | Keep validation, AI consent, cancellation, operation UNKNOWN/reconciliation, and preview-not-saved meaning |
| VIS-009 / P1 | Quiz Builder card (~half content width) centered below a page heading aligned to a different grid edge; considerable empty whitespace. Three numeric inputs are visible, but total selected questions is not summarized. | `frontend/src/features/quiz/QuizBuilder.tsx` — `max-w-2xl mx-auto`, 3 `input type=number` | Consistent column alignment with AppShell; summarize `MCQ + Cloze + Writing` total and permissible range; compact form with prominent creation CTA | Current v1 quiz bounds: total 5–30, <=20/type; no invented books/exercise source switch or unconfirmed provider availability |
| VIS-010 / P1 | Horizontal main navigation repeats unchanged across screenshots; will not scale elegantly to future Library/Book/Progress feature groups. | `frontend/src/app/AppShell.tsx` `PRIMARY_NAV_ITEMS`, `header<nav>` | Official shadcn Sidebar with feature groups, Breadcrumb and accessible mobile navigation; show future items **only when feature exists** | Preserve 9 current routes, client navigation, back/forward, focus and consent link |
| VIS-011 / P2 | Widespread large bordered Card treatment and high-level headings flatten hierarchy across Status/Lookup/Review; several secondary explanations visually compete with main tasks. | `frontend/src/components/ui/card.tsx` and feature-specific compositions | Define `MetricTile`, `StatusSummary`, `CompactFormSection`, `EmptyState` app-level compositions with tokens; establish max-widths and density variants | Do not shrink essential consent text, answers, error reasons or accessibility targets to save space |

### Positive patterns to retain

- Consistent visual controls and semantic Card foundation; React currently has official-compatible local Button/Card/Dialog and Tailwind tokens.
- Status includes meaningful offline vs online distinction, local telemetry and source condition; preserve it even if condensed.
- Consent clearly states that existing data may already have been sent, and local study can continue with consent revoked. Retain this disclosure.
- Quiz Builder has understandable separated MCQ/Cloze/Writing counts and a single primary CTA; preserve flow rather than redesign its domain logic.
- Native labelled date fields and visible review empty state; improve density without discarding labels or accessible status events.

## 3. Nine-group visual-evidence coverage (status after this batch)

| Requested group | Coverage classification | Shown now / remaining evidence |
|---|---|---|
| G1 AppShell, Sidebar & Navigation | **PARTIAL** | Desktop top nav visible across captures. Need mobile width, active/deep routes, keyboard/focus and responsive drawer design |
| G2 Lookup & AI Preview | **PARTIAL** | Empty/idle Lookup captured; need actual preview/result, missing verification, AI unavailable, save transition |
| G3 Search & Word Detail | **NO DIRECT SCREENSHOT** | Need results, filters, detail and return/navigation states |
| G4 Save & Edit Vocabulary | **NO DIRECT SCREENSHOT** | Need save preview and edit form, successful receipt / revision conflict |
| G5 Review Flashcards | **PARTIAL** | Empty review queue captured; need front/back of real flashcard, rating, pending/unknown |
| G6 Quiz Builder & Runner | **PARTIAL** | Builder form captured; need quiz runner MCQ/Cloze/Writing and save/conflict/submit states |
| G7 Quiz Results & Writing Feedback | **NO DIRECT SCREENSHOT** | Need results, per-question explanations, optional feedback and historical status |
| G8 Status, Consent & Error States | **PARTIAL (rich Status coverage)** | 5 Status captures, lower Consent Card; need consent dialog and actual RecoveryPanel/error state, responsive |
| G9 Dashboard | **PARTIAL (earlier captures)** | Earlier empty-data Dashboard and repeated cards; need populated learning state, responsive widths |

Totals: **6/9 groups have at least one visual reference** when the shared AppShell visible across screenshots is counted separately (G1, G2, G5, G6, G8, G9); **3/9 groups have no direct screenshot** (G3 Search/Detail, G4 Save/Edit, G7 Results/Feedback). Of the six referenced groups, G1 is a shared header/navigation view rather than its own dedicated screenshot, and G2/G5/G6/G8/G9 are partial states. No claim of complete visual audit for any group. Multiple screenshots of one group do not count as different groups.

## 4. UXR-02A refinement: screen-specific information density contract

- G8 Status is the highest-leverage density refactor: one top summary, quickly reachable AI data permissions, well-labeled expandable diagnostics, active alarms unmistakable, preserve technical evidence and anchors.
- G5 Review: one empty-state surface for an empty queue, date filter in a slim toolbar; focus-safe announcement separate from visible duplicated prose.
- G2 Lookup: input/CTA dominate idle state, don't show empty or decorative result cards before preview exists; a visible short disclosure of AI dependency still exists.
- G6 Quiz Builder: consistent form alignment and width, total-count summary, clear disabled/error reasons; don't insert invented progress/rating semantics into builder.
- G1 Shell: more compact top bar and future-proof official shadcn Sidebar; not necessarily always expanded.
- G9 Dashboard: previous screenshots motivate compact metrics, one primary CTA and de-duplicated entire-history empty state.
- G3/G4/G7: source assessment only until actual screenshot/interaction coverage; don't invent specific visual defects.

## 5. Recommended design/worker sequence and review gate

1. **Complete UXR-00 evidence inventory** using missing screenshots or a real browser preview; if local backend prevents fixture flow, use deterministic simulated data for design mockups while labelling simulations as such.
2. **UXR-01 / UXR-02:** owner chooses visual direction (Calm Academic Workspace proposed); validate official shadcn Sidebar/Badge/Alert/Accordion/Field/Progress use.
3. **UXR-02A:** approve compact dashboard, compact review empty state, and two-level Status/Consent wireframes. These become authoritative design patterns.
4. **UXR-03–09:** assign feature work in parallel *after* design tokens, IA and density contract are approved.
5. **UXR-10–11:** review states/responsive/a11y design and obtain explicit approval before React/CSS coding.

The existing `UXR-00` is **in progress, not DONE**. The new screenshots are a strong source of direct visual evidence for four feature surfaces, and support early sketch/wireframing without declaring all flows audited.

**No application implementation was changed or tested as part of this report.**

# UXR-03 — Lookup, Search & Word Detail Design

## CURRENT OWNER AUTHORIZATION — 2026-10-14 — DESIGN + FRONTEND IMPLEMENTATION

> **Binding amendment.** The owner changed UXR-03 from design-only research to **Design + Frontend Implementation** on 2026-10-14. [Shared implementation policy](../docs/design/uxr-03-09-design-frontend-implementation-policy-2026-10-14.md) is binding. The original task's source/evidence, feature semantics, all visual frame/viewport quotas, Impeccable, official shadcn, accessibility, and explicit owner visual approval requirements remain mandatory. Historical `design-only`, `no frontend edits`, `no code`, `no tests`, and `no implementation` clauses are **SUPERSEDED for the explicitly owned frontend scope only**. This section prevails over contradictory legacy clauses below. Application backend/API/DB/contracts still remain protected.

**CURRENT STATUS:** `READY_FOR_DESIGN_PLUS_FRONTEND_IMPLEMENTATION / NOT_STARTED` (UXR-02A owner-approved and published; launching Codex work still requires the owner's instruction).  
**CURRENT ACTION:** Design the complete UXR-03 feature experience **and implement it in the actual existing React/TypeScript/Tailwind frontend**, keeping the approved UXR-01/02/02A foundation unchanged.  
**OUTPUT STATE:** `OWNER_VISUAL_AND_IMPLEMENTATION_APPROVAL_PENDING`, not `DONE`, until owner review.  
**BASE:** `57159675fc59e984db1d64dcd899aedabf6622ff`; existing `design/uxr-03` worktree must safely fast-forward to the updated specification before execution.

### New authorized deliverables for UXR-03

1. Preserve **every original scenario, minimum full-resolution screenshot count, comparative evidence, and state/viewport gate specified later in this task**; additionally show the actual running application frontend implementing the design, not solely isolated mockups.
2. Implement the feature-owned frontend surfaces, preserving current app routes and supported API contracts. **Candidate ownership allowlist:** `frontend/src/features/lookup/**; frontend/src/features/search/**`. Inspect the actual repo to resolve paths; if an expected file moved, document the precise verified path. No arbitrary changes outside the feature boundary.
3. **Primary implementation targets:** LookupPage.tsx; LookupResult.tsx; WordDetail.tsx; SearchPage.tsx. The approved design direction is UXR-01 Compact Study Console v1.2 + UXR-02 AppShell R2/HM-FIX + UXR-02A Variant B/R1B. Do not redesign shared foundation.
4. **Read-only/cross-task seam:** UXR-04 SavePreview and UXR-08 consent data/authorization. If a necessary change touches a shared/cross-feature file, record a proposed integration patch or ask for an explicit single-writer owner/coordinator decision; do not modify in two parallel worktrees.
5. No invented data or backend capabilities: preserve null/zero/UNKNOWN/error boundaries, existing operation contracts, idempotency, revision/reconciliation, user consent, and status truthfulness as applicable. Mark screenshots as `RUNNING_FRONTEND`, `ISOLATED_MOCKUP` or `SYNTHETIC_FIXTURE` accurately.
6. New implementation acceptance: actual TSX/styles changed; actual app can mount the affected route; representative functional interactions can be exercised against existing contracts or explicitly labeled fixtures; required full-resolution UI frames captured from the running frontend; feature-local build/type/browser check results documented. Full-system tests/audit remain for a later wave; do not fabricate PASS.
7. Every frontend-design Worker explicitly invokes installed `$frontend-ui-engineering`, plus relevant addyosmani skills and installed Impeccable in its own context; Astra acts as coordinator/auditor/integrator, delegates GPT-6.1 Sol Worker packages with single-writer file ownership.
8. Request `speed: fast`, `permission: full-access` via actual supported runtime controls, but still obey the file allowlist. On the exact model-capacity error, retry dispatch with a real 3s delay up to 30 times, then replace the blocked, non-running worker (max 3 replacement workers per package) without changing model or duplicating writes. Disclose unverified actual-model/speed/permission metadata.
9. No new dependencies or shadcn installation without separate approval; reuse current canonical primitives. No unapproved edits to `backend/**`, SQLite, API/DTO/OpenAPI, generated contracts, SRS/quiz/consent business semantics, main, UXR-02A frozen artifacts, `tasks/todo.md`, or shared app shell. No automatic commit/push/merge; stop for owner visual + implementation review.
10. Acceptance item previously reading `no app/frontend code changes` is now `no unauthorized code changes outside owned frontend`; any other old item only contradicted by this explicit amendment is `SUPERSEDED_BY_OWNER_2026-10-14`, **not PASS**. Add an `IMPLEMENTATION_GATE` alongside all original design AC. No existing critical visual or safety criterion is waived.

---


**Track:** English Web final UI/UX redesign; design specification only, separate from T001–T090.  
**Status:** `PREPARED / NOT STARTED / BLOCKED_BY_UXR_02A_OWNER_VISUAL_SIGNOFF`.  
**Owner authorization:** prepare this task card and update roadmap/Draft PR #26 only; no design execution or app changes.  
**Dependency:** UXR-00 final evidence → UXR-01 owner-approved visual direction → UXR-02 owner-approved AppShell → UXR-02A owner-approved density and visual mockups → UXR-03.  
**Groups:** G2 Lookup/AI Preview; G3 Search/Word Detail.  
**Next task-card gate:** ask owner whether to prepare UXR-04 after documenting this card.  
**Mandatory shared policy:** [visual screenshots, local Impeccable and official shadcn/ui](../docs/design/uxr-visual-approval-impeccable-protocol-2026-10-12.md).  
**Branch/PR:** `design/ui-ux-research-20261012`, [Draft PR #26](https://github.com/khanhpn308/english_web/pull/26), no merge.

## 1. Objective and scope

Specify and visually illustrate three existing workflows without changing their behavior:
- `/lookup`: enter an English term, request optional AI enrichment after explicit consent, inspect all preview forms and verification evidence, hear locally available pronunciation and pass the preview to the separate Save action.
- `/search`: search/browse saved local vocabulary, choose URL-persisted filters, inspect pages, handle empty/error/stale cursor and return to saved search state.
- `/word-forms/:wordFormId`: see canonical word form, bilingual meanings/examples, IPA, source-health and verification, safe dictionary link and source-specific Edit entry where permitted.

Create compact, readable desktop/mobile layouts, with one dominant next action per screen/state, clear uncertainty, full keyboard reachability and substantial user-visible full-resolution image proposals. **UXR-04** owns SavePreview and EditWordForm interaction design, including source conflicts; UXR-03 owns only handoff layout and Edit entry. No redesign coding.

## 2. Present state and grounded evidence

**Source references:**
- `frontend/src/features/lookup/LookupPage.tsx`: phases `idle, validation, authorizing, loading, success, empty, recoverable, terminal, unknown, reconciling`; NFC/whitespace term normalization, **1–80 Unicode characters**; consent before external request, preserved operation identity and explicit reconciliation.
- `frontend/src/features/lookup/LookupResult.tsx`: each form/POS; Vietnamese and English meanings, translated examples, US IPA, Cambridge source, field-level `VERIFIED/UNVERIFIED/MISSING`, origin details. Preview does not imply Save.
- `frontend/src/features/lookup/AudioButton.tsx`: only browser `SpeechSynthesis` with confirmed local `en-US` service; unavailable otherwise, no cloud TTS.
- `frontend/src/features/lookup/SavePreview.tsx`: selected date, source checks, ETag/revision, idempotency and saved receipt are separate UXR-04 concerns.
- `frontend/src/features/search/SearchPage.tsx`: URL keys `meaningVi,lemma,partOfSpeech,verificationStatus,noteDate,sourceStatus,pageSize,sortBy,sortOrder,cursor`; UI markers `browse,notice`; `CURSOR_EXPIRED` restarts from first page retaining filters. Search is local API, not AI-dependent.
- `frontend/src/features/search/WordDetail.tsx`: decoded ID, safe `returnTo` only to `/search`, detail load/retry, `VALID/INVALID/MISSING` source health, source-gated Edit, translated examples and verification.
- `docs/ui-architecture.md`, `docs/adr/0004-v1-product-policy-and-operational-baseline.md`, `docs/adr/0005-contract-clarifications.md`: authoritative local/optional AI, consent, vocabulary and source contracts.

**Visual baseline:** 2026-10-12 owner screenshot confirms only G2 **Lookup idle** has an oversized surrounding Card (VIS-008); no direct owner screenshot is established for G3 Search/Detail, G2 populated preview, AI permission dialog or error states. Read [batch-2 report](../docs/design/ui-visual-audit-2026-10-12-batch2.md) and future UXR-00 handoff. Keep `CURRENT_APP_CAPTURE`, `SOURCE_CONFIRMED`, `DESIGN_MOCKUP`, `NOT_VERIFIED` distinct. Do not invent baseline images.

## 3. Hard dependencies and start conditions

Before an actual worker begins UXR-03 design:
1. Verify UXR-00 report, screenshot provenance, missing-state matrix and source baseline SHA.
2. Obtain and link owner-signed **image approvals** for UXR-01 direction, UXR-02 shell/theme and UXR-02A compact density. These currently have no proven approved execution deliverables.
3. Obtain separate owner **UXR-03 execution** permission; authorization to write this Markdown file is not that permission.
4. Freeze UXR-02/02A shared tokens/nav/density contract; allocate one UXR-03 integration lead and non-overlapping G2 and G3 image owners.
5. Discover the owner's **already installed** Impeccable skill in each active local agent context; read it and invoke it as specified in §6. Never reinstall.
6. Read relevant source, official shadcn strategy and the binding visual protocol. UXR-04–09 may execute in parallel only after the actual UXR-02A design gate, not before.

## 4. Concrete design work

### A. Lookup composer and AI Preview — G2

Propose a compact term Input/label, concise helper, one prominent `Tra cứu` action; reduce the oversized idle Card without hiding consent disclosure. Design states:
- Empty/invalid term, normalized maximum length, Enter/button; keep entered term after errors.
- Permission unknown/stale/not granted/revoked; explicit grant dialog, decline/Escape return without submitting. **Grant does not auto-send**; only a fresh deliberate action may dispatch.
- Authorizing/loading with cancel-wait warning; aborted waiting does not recall previously shared data. AI bridge missing while local Search remains available.
- Preview with zero, one and multiple forms; form/POS headings, field-level `VERIFIED/UNVERIFIED/MISSING`, VN/EN meaning pairs, translated examples, US IPA, local voice and Cambridge reference. Source/provider/model IDs through named disclosure; missing verification is not concealed.
- Error/recoverable/terminal/`UNKNOWN` operation: preserve the original request identity and one `Kiểm tra kết quả` route, never a misleading duplicate generation.
- Preview-not-saved vs back-end-confirmed saved receipt. Show handoff to `SavePreview` without defining its date/source/precondition/commit/conflict interactions (UXR-04).

### B. Search and browse — G3

First visual level: meaning-Vietnamese query, lemma query, one contextual primary action, active-filter summary and result list/count. Advanced disclosure preserves accessible controls for POS, verification, note date, source status, sort key/order and page size. Show `browse=1` mode, no filters, active filters, no matches, loading, recovery, local API unavailable. Use compact content-driven result rows: lemma, POS, matching meaning, verification, note dates and update time.

Document every API URL key listed in §2 and `browse/notice`, refresh/deep link/back-forward behavior. On changing non-cursor filters clear stale cursor; preserve other choices and reflect active filters even with disclosure collapsed. Show cursor-based `Trang đầu/Trang tiếp` correctly; don't invent total pages or total results when API only provides page length and `hasMore`. For cursor expiry show notice and first-page restart retaining filters. Search must not require AI permission or optional bridge.

### C. Word Detail and safe editing entry — G3

Design word header with lemma/POS, IPA, safe Cambridge link, verification; source/date status and optional existing card/due state; VN/EN meanings and bilingual examples. Preserve all meaning text, not just shortened previews. Show mixed valid/invalid/missing, no-valid-source, absent refs, loading, NOT_FOUND, invalid ID and API/session recovery.

Back link must preserve validated `returnTo=/search?... ` and default safely to `/search` for bad targets. Visual Edit entry appears only for `VALID` source with clear source/date target; it must never be enabled in an invalid-source-only mockup. Preserve UXR-04's ownership of drafts, conflicts, revisions, date/source Save and edit forms.

### D. Cross-screen density and responsive/accessibility rules

Inherit UXR-02 approved AppShell and UXR-02A one-primary-action/progressive-disclosure contract. Reuse no more than necessary Cards; group by meaning, not arbitrary equal heights. For viewports `1440×900`, `1366×768`, `1024×768`, `768×1024`, `390×844`, `320×568` CSS px, define layout, focus/tab order, error/consent dialog focus return, readable bilingual text, long lemma/IPA/translation wrapping, 200% zoom reflow, touch targets, screen-reader names and visible focus. Avoid claiming measured WCAG AA or verified app behavior from design images. No hypothetical Future Book link goes live.

## 5. Mandatory full-resolution proposed UI screenshots and owner decisions

**A later authorized UXR-03 execution must create at least 18 original full-screen owner-viewable PNG/WebP frames**, not text-only or ASCII wireframes. The following **nine screen/states** each have **1366×768 desktop + 390×844 mobile** images:

| Frames | Screen/state |
|---|---|
| L01–02 | Lookup idle, compact composer |
| L03–04 | Lookup multi-form preview, meanings/examples/verification, visibly NOT SAVED |
| L05–06 | Lookup consent pending, input preserved, explicit no-auto-send |
| L07–08 | Lookup UNKNOWN/recoverable operation and safe reconciliation |
| S01–02 | Search populated results/list and result count |
| S03–04 | Search advanced filters, active indicators/sort/date/source |
| S05–06 | Search empty/no matches, useful recovery |
| W01–02 | Word Detail with VALID source and safe Edit entry |
| W03–04 | Word Detail invalid/missing-only source and unavailable Edit |

**Extra mandatory images:** `320×568` stress layout, `768×1024` tablet and `1024×768` intermediate composition, representative `1440×900` full AppShell, same-state light/dark screenshots, and at least one alternate G2/G3 composition for owner comparison. Clearly mark all synthetic study and AI data `SYNTHETIC / DESIGN_MOCKUP`. Compare Lookup idle with genuine existing capture when available. For G3 current state, explicitly label `SOURCE-ONLY BASELINE / NO DIRECT SCREENSHOT` until UXR-00 supplies an authentic one.

Publish readable contact sheet **plus direct full-resolution image links**, labeled `task|route|state|viewport|theme|variant|version|provenance|date`. Keep assets accessible to owner under `docs/design/uxr-03/assets/` or another approved durable location. Owner reviews actual pictures and signs `APPROVE / REQUEST_CHANGES / REJECT / PENDING` for exact version. **No visual owner sign-off = UXR-03 not DONE**. A revised layout must have revised screenshots and reapproval.

## 6. Mandatory Impeccable skill use by coordinator and workers

Owner states [Impeccable](https://github.com/pbakaus/impeccable) is **already installed locally**. Do not install, update or vendor it.

For every authorized local UXR-03 **design execution session**, coordinator **and each independent design worker**:
1. Resolve their own installed skill base directory; read its `SKILL.md` and relevant references.
2. Run `<skill-base>/scripts/impeccable context` **once per session** from English Web project cwd, or the appropriate installed Windows `impeccable.cmd context` launcher. Record actual result; reading upstream GitHub docs is not invocation.
3. Apply installed-version guidance selectively: `shape` (task/flow), `layout`/`distill` (compact composer/results), `adapt` (mobile/zoom), `critique` (independent visual assessment), `clarify` (UI wording) and `harden` (uncertain states). No blanket verb spam; mockups/specs only, not production React.
4. Log `agent|role|skill actual path/version|session|context invocation result|reference/verb|target|finding → design change|image ID`.
5. If unavailable, report `IMPECCABLE_NOT_ACCESSIBLE`, real path/error and owner resolution; **do not silently skip or claim PASS**. Mandatory skill gate blocks final sign-off.

This task-card GitHub preparation has **not** run the owner's local Windows skill.

## 7. Official shadcn/ui-only component contract

**Only authorized source for missing reusable primitives:** https://ui.shadcn.com/docs/components. First reuse existing `frontend/src/components/ui/{button,card,dialog}.tsx`, `components.json` New York style, Radix Dialog foundation and Tailwind 4 non-Preflight CSS. For any proposed component, record `official docs URL|role|ALREADY_PRESENT/OFFICIAL_PROPOSED/CUSTOM_COMPOSITION/DEFERRED|accessibility risk|owner`.

- Lookup: official **Input, Field, Alert, Skeleton, Badge, Accordion, Tabs** as justified, with existing **Button/Card**.
- Search: **Input, Input Group, Select, Collapsible, Badge, Separator, Pagination** (only if suited to cursor), **Empty**; **Combobox** only with a real need.
- Detail: existing **Card/Button**, official **Badge, Alert, Accordion, Separator**, with source status semantics intact.
- App-level conceptual composition names: `LookupComposer, WordPreview, VerificationStatus, SearchFilterBar, WordResultItem, WordDetailHeader, SourceHealth`; they combine official primitives, do not duplicate them.

Do **not** run shadcn `init/add/overwrite`, install dependencies, change package locks, mix incompatible base libraries or copy unofficial registries/templates during design preparation/execution. Later code implementation requires separate authorization, official pinned CLI/diff review and a single primitive owner.

## 8. Future execution deliverables

All future outputs under `docs/design/uxr-03/` (none is claimed created now):

| Artifact | Required contents |
|---|---|
| `UXR-03-EVIDENCE-STATE-MATRIX.md` | current source/screenshot proof and states/transitions |
| `UXR-03-LOOKUP-DESIGN.md` | input/consent/preview/audio/UNKNOWN and preview-save boundary |
| `UXR-03-SEARCH-DESIGN.md` | query/filter, cursor, results/empty/error and URL invariants |
| `UXR-03-WORD-DETAIL-DESIGN.md` | word/sources/status/back/Edit entry; UXR-04 separation |
| `UXR-03-RESPONSIVE-A11Y.md` | 320px, 200% zoom, keyboard, screen reader, long content design targets |
| `UXR-03-SHADCN-MATRIX.md` | official component/source mapping and adoption classification |
| `UXR-03-VISUAL-GALLERY.md` + `assets/*.png` or `*.webp` | 18+ full-resolution labeled mockups, alternatives, contact sheets and links |
| `UXR-03-IMPECCABLE-EVIDENCE.md` | real per-agent local installed skill invocations and outcomes |
| `UXR-03-OWNER-APPROVAL.md` | owner decision on **actual images**, version and outstanding feedback |
| `UXR-03-HANDOFF.md` | frozen G2/G3 visual boundaries, UXR-04 and UXR-10 inputs |

## 9. Measurable acceptance and Definition of Done

UXR-03 is **DONE only if all criteria pass**:
1. **AC01** Verified UXR-00 final handoff and UXR-01/UXR-02/UXR-02A owner image approvals, plus separate execution permission.
2. **AC02** At least **18** accessible full-resolution screen images for L01–W04; additional widths, light/dark and alternate composition; clear version/source labels and working owner links.
3. **AC03** Explicit owner visual approval of exact Lookup, Search and Word Detail images; agent scoring never substitutes.
4. **AC04** Lookup term validation, consent fail-closed/no auto-submit, cancel-wait clarification, preview-not-saved and UNKNOWN recovery visibly specified.
5. **AC05** Multiple forms/POS, full meanings/examples, IPA, Cambridge and per-field VERIFIED/UNVERIFIED/MISSING displayed honestly.
6. **AC06** Speech only if local en-US voice available; disabled/unavailable treatment explicit.
7. **AC07** All Search URL query/filter/sort/date/pageSize/cursor/browse/notice semantics mapped, including reset, back/forward and cursor-expiry preservation.
8. **AC08** Search is visibly local/offline-bridge-independent; no invented result totals or page counts, one appropriate empty state.
9. **AC09** Detail shows VALID/INVALID/MISSING source, full bilingual content, safe returnTo, valid-source Edit only, error/retry.
10. **AC10** All critical loading/empty/populated/recoverable/terminal/unknown/permission states included in matrix and selected images; no fake backend or screenshot evidence.
11. **AC11** Shared shell/density and one primary context-valid CTA, advanced disclosure with active filters and essential warnings visible.
12. **AC12** 320px/mobile/tablet, 200%-zoom reflow plan, focus/dialog/tab/ARIA and bilingual accessibility stated; no unsupported WCAG PASS.
13. **AC13** Every missing primitive mapped to **official shadcn docs** and existing Radix compatibility; nothing installed.
14. **AC14** Coordinator **and every active UI designer** logged actual already-installed Impeccable invocation and concrete design changes; failure remains blocker.
15. **AC15** UXR-04 owns Save/Edit flows and conflict handling; UXR-03 only designs safe transitions.
16. **AC16** Source-only G3 current baseline is honestly labeled, with no invented existing screenshots.
17. **AC17** Approved assets, resolved/unresolved issues and component/state contracts handed to UXR-04/UXR-10.
18. **AC18** No frontend/backend/config/dependency/SQLite/DTO/`tasks/todo.md` edits, tests, implementation claims or PR merge.

Lifecycle: `PREPARED → READY_FOR_EXECUTION → IN_PROGRESS → OWNER_VISUAL_APPROVAL_PENDING → DONE`; blocked evidence, missing skill usage or unsigned image gallery prevent DONE.

## 10. Out of scope

No application UI coding or running Playwright, local backend/AI requests, tests, installs or screenshots in this preparation turn. No changes to consent grant/revoke mechanics (UXR-08), SavePreview/source revisions/ETag/idempotency or EditWordForm conflict workflows (UXR-04), SRS, quiz, Markdown, backend or API. No new Library/books/exercises/progress/IELTS/CEFR routes; future book-word provenance is conceptual only. No false a11y/benchmark PASS, UXR-00 closure, main merge or adoption of proposed UXR-12.

## 11. Parallelization, coordination and artifact ownership

After **actual UXR-02A owner visual sign-off** UXR-03–UXR-09 may execute in parallel on disjoint feature artifacts. Inside UXR-03, designate one **integration lead**, one G2 Lookup screenshot worker and one G3 Search/Detail worker, each owning distinct scratch/assets; every design worker invokes Impeccable in its own session.

| Ownership | Paths |
|---|---|
| UXR-03 integration lead, **single writer** | `docs/design/uxr-03/*-MATRIX.md`, consolidated specs, gallery, owner approval and handoff |
| G2 specialist | `docs/design/uxr-03/assets/lookup-*` |
| G3 specialist | `docs/design/uxr-03/assets/search-*`, `assets/detail-*` |
| Coordinator only | `tasks/uxr-03-lookup-search-word-detail-design.md`, roadmap, Draft PR #26 |
| Read only | `docs/design/uxr-01/**`, `uxr-02/**`, `uxr-02a/**`, audit evidence, shared visual protocol |
| UXR-04 exclusively | future `docs/design/uxr-04/**` including Save/Edit wireframes and approvals |
| No edits during design | `frontend/**`, `backend/**`, `components.json`, `package-lock.json`, generated code, `tasks/todo.md` |

UXR-03 and UXR-04 share a **visual seam** at Lookup → Save and Detail → Edit, not artifact ownership. A single coordinator resolves any proposed change to shared tokens, primitives or AppShell and requests owner reapproval if material.

## 12. Handoff and next owner gate (UXR-04)

Later, hand UXR-04 the **actually owner-approved** G2/G3 full-resolution preview/detail images, states, official components and exact safe entry contracts. UXR-04 independently designs save-date/source-read, source revision/ETag, idempotent save receipt, unknown/conflict recovery, edits/409/re-read and draft preservation; its deliverables require **separate visual owner approval**. Give UXR-10 a traceable nine-group integration input: screenshots/version/decisions, source invariants, semantic verification/consent, URL state and Impeccable evidence.

**Current action only:** commit this Markdown task card, update roadmap and Draft PR #26, verify the changes are documentation-only and **stop for owner authorization to prepare UXR-04**. No execution of UXR-03 or UXR-04, no visual approval claimed and no code changes.

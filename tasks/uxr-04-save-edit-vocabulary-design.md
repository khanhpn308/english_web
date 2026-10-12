# UXR-04 — Save & Edit Vocabulary Design

**Track:** English Web — major final UI/UX redesign; research and visual design task, separate from canonical application T001–T090.  
**Priority:** P0 — G4 Save/Edit Vocabulary, shared seam with G2 Lookup Preview and G3 Word Detail.  
**Status:** `PREPARED / NOT STARTED / BLOCKED_BY_UXR_02A_OWNER_VISUAL_SIGNOFF`.  
**Authorization:** Owner approved **preparing this Markdown task card** and updating the research roadmap / Draft PR #26 on 2026-10-12. This is **NOT** approval to execute UXR-04 design, produce approved mockups, install components, run agents locally, edit app code or merge the PR.  
**Hard chain:** UXR-00 final evidence → UXR-01 owner-approved image-based direction → UXR-02 owner-approved AppShell → UXR-02A owner-approved compact/density gallery → **UXR-04 execution and its separate owner image approval** → UXR-10 → UXR-11.  
**Parallel peers:** UXR-03 and UXR-05–09 may execute feature design in parallel only **after the real UXR-02A owner gate**, with non-overlapping artifacts.  
**Branch:** `design/ui-ux-research-20261012`; [Draft PR #26](https://github.com/khanhpn308/english_web/pull/26) stays Open/Draft/unmerged.  
**Binding cross-track protocol:** [Owner-visible screenshots, installed Impeccable and official shadcn/UI](../docs/design/uxr-visual-approval-impeccable-protocol-2026-10-12.md).

## 1. Goal and scope

Deliver a visually coherent, compact and **owner-approved image-based** design for two existing, independent **local data mutation** journeys, without changing backend or client behavior:

1. **Save Preview (G4 at `/lookup`)**: show a valid AI-enriched preview as *not yet stored*; choose note date; check same-date source; differentiate new-date creation, valid existing-date update, blocked invalid/missing/ambiguous source and failed read; save **all** forms in the preview as one durable operation; represent in-progress, conflict, UNKNOWN and confirmed Markdown/flashcard receipt correctly.
2. **Edit Word Form (G4 from `/word-forms/:wordFormId`)**: enter edit only for a `VALID` source; edit bilingual meanings, bilingual examples, US IPA and Cambridge URL; preserve draft and source identity, display field validation; handle revision/ETag conflict with explicit comparison and safe choices; convey confirmed change, source revision and flashcard/SRS reset implications.

The final proposals must use the approved UXR-01 visual identity, UXR-02 AppShell tokens/layout and UXR-02A compact density hierarchy, while retaining **independent state machines**, keyboard access, semantic uncertainty and a non-destructive default. One dominant primary action per current state does **not** remove required cancel, re-read, reconcile, consent/privacy or conflict controls.

**Explicitly excluded from UXR-04:** designing the Lookup AI request/Preview content itself (UXR-03), Search/Detail browse and provenance layout (UXR-03), Review rating/SRS algorithm (UXR-05), Status/AI consent transitions (UXR-08), or implementing any of these screens.

## 2. Current behavior and evidence boundary

**Repository-confirmed files and contracts:**

| Source | Actual responsibilities and preservation rule |
|---|---|
| `frontend/src/features/lookup/SavePreview.tsx` | `Phase = ready/saving/success/failed/unknown/reconciling`; source `kind = unread/loading/absent/existing/blocked/error`; date defaults to current `Asia/Bangkok` date and is retained across midnight; reads source list before enabling Save; `preview.status === PREVIEW` and `forms.length > 0` required; stores pending intent in sessionStorage or blocks unsafe new Save |
| `SavePreview.tsx` | `absent` → `If-None-Match: *`, no fabricated source ID; one exact `existing VALID` source → `sourceId/sourceRevision` and `If-Match` with per-source opaque ETag; multiple, INVALID or MISSING sources are not writable; saves all preview forms together; new requests have stable `Idempotency-Key` |
| `SavePreview.tsx` | `UNKNOWN` holds original intent, locks new save, queries operation/receipt, and may replay **same intent**, not create another; backend-confirmed `SaveResult` requires `markdownSync=COMPLETED`, source ID/revision/ETag, canonical forms, created/reused card IDs; user-facing success cannot precede receipt validation |
| `frontend/src/features/search/WordDetail.tsx` | Only a `VALID` sourceRef exposes Edit; passes selected `sourceId` and `noteDate`; after success returns to detail and refreshes. Detail needs valid safe return-to-Search behavior from UXR-03 |
| `frontend/src/features/search/EditWordForm.tsx` | Loads selected date/source, guards `VALID`; edits arrays `meaningsEn/meaningsVi/examples` and optional `ipaUs/cambridgeUrl`; sends `PATCH` with selected source ID/revision, `If-Match=source.etag` and a client idempotency key; exposes FIELD_ERRORS; keeps entered fields in component state on ordinary save errors |
| `frontend/src/features/search/RevisionConflictDialog.tsx` | Existing Radix/shadcn Dialog presents a server revision and choices to discard draft or reload source version. Wording around “lưu đè” deserves a **design-level non-destructive comparison/confirmation review**, not an unsupported assertion that a backend overwrite already occurred |
| `docs/adr/0005-contract-clarifications.md` §C013-04/05 | New/existing source conditional save, 409 conflict and no last-write-wins, external Markdown watcher/hashes, revision/ETag invariant; meaning/example edits can reset SRS card box to NEW while historical review events remain |
| `docs/ui-architecture.md` §J2/J3 | Preview never equals stored data; all returned forms saved, not cherry-picked; successful Markdown/source/card receipt is authoritative; visible source mismatch/conflict recovery must preserve user work |

**Evidence status:** The owner-provided batch-2 screenshots show Lookup **idle** only. There are **NO DIRECT owner captures of Save Preview active, Save receipt/conflict, Edit form or conflict dialog** recorded in current audit coverage G4. UXR-00 may later add them. Mark `SOURCE_CONFIRMED` and `NOT_VERIFIED` honestly until an authentic current-app screenshot exists; do **not** fabricate a “before” image or assert runtime defects from code inspection alone.

**Potential UX risk to investigate:** A design reading of `RevisionConflictDialog` suggests “refresh version to overwrite” may be hard to interpret; the proposed new copy and flow must distinguish re-read, compare and **explicit fresh save authorization**. Do not modify backend precondition logic, claim verified data loss, silently replace draft, or assume a re-read automatically approves overwrite.

## 3. Preconditions and formal execution gate

UXR-04 can be **prepared** now but can only be **executed** after:
1. UXR-00 final report with precise screenshot confidence labels, source baseline SHA and unresolved G4 visual gaps is available.
2. UXR-01 actual **owner-selected** visual direction/version and full-resolution A/B gallery, UXR-02 owner-approved shell/theme screenshots, UXR-02A owner-approved compact density Dashboard/Review/Status frames plus frozen shared token, navigation and action contracts are linked.
3. Owner separately authorizes **UXR-04 execution**, not merely this task file.
4. One UXR-04 integration lead and distinct Save/Edit/conflict mockup asset owners are assigned, with **no overlap** in `docs/design/uxr-03/**`, shared `uxr-02/**`, `uxr-02a/**` or production source.
5. Astra/coordinator **and each active design worker** have independently located their own actual locally installed Impeccable skill, read installed `SKILL.md` and invoked its `context` launcher; precise unavailable results are reported, no reinstall.
6. The current official shadcn strategy/component inventory and the binding owner-image protocol have been read. The actual G2/G3 proposal (UXR-03) can develop in parallel; its **shared visual seam is a contract to reconcile**, not a hard execution dependency if both consume the approved UXR-02/02A foundation.

## 4. Concrete design work packages (design-only, future authorized run)

### A. Save Preview journey and state machine

Create a state/event matrix with `route | source phase/kind | precondition | action | source/API identity | allowed primary/secondary controls | visible status | draft retention | focus target | screenshot ID`.

Design the **full, all-forms** save decision:
- `PREVIEW` clearly labeled **Chưa lưu**; save only with non-empty validated result and explicit selected study date. Do not imply imported meanings are already authoritative.
- Date defaults from `Asia/Bangkok`, not browser locale; user can choose another day; selected day is retained across midnight/refresh as existing logic permits. A date change invalidates previously read source status; the safe next action becomes **Đọc nguồn**, not immediate Save.
- Display source check results: **UNREAD**, **LOADING**, **ABSENT/new date**, **EXISTING/one VALID source**, **BLOCKED/INVALID**, **BLOCKED/MISSING**, **BLOCKED/ambiguous multiple sources**, **ERROR**, with precise enabled/disabled actions, plain-language reasons and non-color-only cues. Do not convert source absence into `MISSING` source corruption.
- **New date:** convey “Tạo nguồn cho ngày đã chọn” using authoritative absence; Save sends `{lookupId,noteDate}` and `If-None-Match: *`. **Existing one VALID:** convey “Cập nhật nguồn ngày đã chọn” using exact sourceId/sourceRevision and its own ETag `If-Match`. Never invent a source ID/path or silently combine conflicting source variants.
- Display “Đang lưu — chưa xác nhận” while pending. If response lost/timeout/storage intent failure, distinguish `UNKNOWN` (may have committed) from confirmed `FAILED`, **lock new Save**, preserve pending intent and show **Kiểm tra kết quả lưu** using same operation. Never recommend retry-as-new-operation while unresolved.
- On `REVISION_CONFLICT`, show changed-source warning, preserved preview and next deliberate **Đọc lại nguồn** action; no background merge or blind append. On source invalid/missing/multiple, do not present an enabled Save.
- On validated `SaveResult` show **“Đã lưu”** only after `markdownSync=COMPLETED`, include note date, count of new/reused flashcards and what happened to schedules. Technical `operationId/sourceId/revision/ETag` remain available via labeled disclosure, not the main success message. Reused cards retain identity; changed learning content can cause backend-reset according to authoritative receipt, never silently promise schedule preserved or reset without evidence.
- Explicitly show `preview` versus `canonical saved forms` and provider verification provenance, retaining all returned forms; no selective save per POS in v1.

### B. Edit Word Form journey and safe draft handling

- Scope is a **selected VALID source/date** reached from Word Detail. Show word lemma/POS and currently edited source/date in an always-readable context; place revision/ETag in expandable technical metadata. INVALID/MISSING source states block Edit with a useful recovery explanation; no source/date mismatch.
- Forms for **English meanings**, **Vietnamese meanings**, bilingual **example pairs**, **US IPA**, **Cambridge link**. Use add/remove controls with clear per-row labels, correct list insertion/deletion focus, and accessible error association. Make bilingual long examples readable, not narrow inline micro-inputs. Keep existing field verification provenance; new edits are not magically `VERIFIED`.
- User can choose **Lưu thay đổi** or **Hủy**; define visible unsaved-draft policy and focus/return targets, including navigating away, editing repeated rows, validation failures, source-read failures and save failure. Do not claim persistent drafts survive reboot unless a separately approved implementation provides it; existing in-memory form state is limited.
- Show `SAVING` vs confirmed success vs FIELD_ERRORS with paths/reasons; preserve typed content after field errors/recoverable error. Current `PATCH` uses `sourceId/sourceRevision` plus that exact source's opaque `If-Match` and request's stable idempotency key; do not display `WordForm.revision` as the write precondition or treat it as sourceRevision.
- **409 REVISION_CONFLICT**: a dedicated, clearly understood **existing/current-source vs unsaved draft** UI concept with old/new revision references, changed fields when actually available, no claim that the server sends a full diff if it doesn't. Default to **Keep draft / Cancel comparison** and **Re-read current source**. Any overwrite based on the new revision requires a **separate explicit user decision** after comparing content; no automatic repeated POST/PATCH, no silent last-write-wins.
- **Important API caveat:** source-only revision re-read is not the same as fetching authoritative changed meanings/examples. If comparison requires a new Word Detail read, document that requirement in the design; **do not invent a diff endpoint or a currently implemented compare feature**. Present only available fields until actual data is fetched; a missing comparison is a blocker to an unsafe overwrite action.
- After server-confirmed success, show source revision, meaning/example update and **possible SRS card reset** (only when backend confirms applicable semantics) while preserving old event history. Returning to refreshed detail must not show stale saved text as confirmed.

### C. Shared cross-feature safety and visual composition

- Connect UXR-03 **Lookup Preview → SavePreview** and **Word Detail → EditWordForm** using stable shared confirmation/verification patterns without double-owned forms. Keep verified/missing badges honest and optional AI sharing separate from local save/edit, which need no new bridge dispatch.
- Apply UXR-02A density rule: one context-correct dominant action (e.g. `Đọc nguồn` *then* `Lưu để ôn`, or `Kiểm tra kết quả` when UNKNOWN), secondary Cancel/Back, compact form sections, no tall duplicate status cards or extra “success” copy repeated four times.
- Define `SaveSummary`, `SourcePreconditionStatus`, `BilingualEditSection`, `SourceConflictReview`, `ConfirmedReceipt`, `PendingOperationNotice` and `FormErrorSummary` as **future presentational compositions**, not new repository components now.
- Critical warnings/unsaved changes/confirmation remain obvious. Operational IDs, raw ETags and revision information stay reachable for diagnosis, but aren't the main reading order. Avoid implying offline/local save is blocked by missing optional AI consent.

### D. Accessibility, responsive and difficult data

- Design for desktop `1366×768` and `1440×900`, intermediate `1024×768`, tablet `768×1024`, mobile `390×844` and narrow `320×568` CSS pixels. Include 200%-zoom **design reflow** behavior, long Vietnamese lines, multiline meanings/examples, long source/operation IDs, browser-native date input ambiguities and safe scrolling/focus.
- Explain keyboard order and dialog focus trap/return; each repeatable field, add/remove and confirmation action has a programmatically distinct label; field validation has a linked error message; `role=alert/status` announcements don't disappear because duplicate visible prose is consolidated.
- Browser locale formatting may show `mm/dd/yyyy` on native `date` despite ISO values. Do not falsely claim a date bug based only on screenshot; if proposing official Date Picker, evaluate keyboard access, Vietnamese labeling and preservation of `YYYY-MM-DD` wire format.
- Contrast, reduced motion and accessible targets are **design requirements**, not measured WCAG 2.2 AA PASS. No actual local API/sync/ETag behavior is proven by static screenshots.

## 5. Owner-visible UI screenshots and mandatory approval gate (VG4)

**During authorized UXR-04 execution:** produce **at least 20 original full-resolution PNG/WebP composed UI mockup screenshots** — ten named scenarios, each at `1366×768` desktop and `390×844` mobile. These are *not* optional wireframes. Use one approved shell/theme foundation; all simulated source IDs, words, revisions, Markdown receipts and conflict states must be **clearly labeled SYNTHETIC/DESIGN_MOCKUP**, not claimed as actual backend results.

| Frame pair | Required scenario | What must be visible |
|---|---|---|
| SV01–02 | Valid preview awaiting Save | Word/forms, explicit NOT SAVED, selected date and source-check gate |
| SV03–04 | New-date source `ABSENT` | Read completed, safe create-source Save action, no fabricated source ID |
| SV05–06 | Existing one `VALID` date source | Existing-source update semantics and accurate date/source context |
| SV07–08 | `BLOCKED` source: INVALID/MISSING/multiple | Clear reason, disabled Save and contextual safe next step |
| SV09–10 | `UNKNOWN` save outcome | Original operation held, check-same-operation action, no second Save |
| SV11–12 | Validated successful receipt | Markdown confirmed, created/reused cards, accessible technical metadata |
| ED01–02 | Edit populated bilingual form | Repeatable meanings/examples, IPA/Cambridge, selected VALID source/date |
| ED03–04 | Edit draft with field errors | Input retained, field-path feedback, one primary corrective route |
| ED05–06 | `409 REVISION_CONFLICT` comparison/dialog | Current vs local draft, explicit no-auto-overwrite and safe options |
| ED07–08 | Confirmed edit success / SRS implication | Server acknowledgement, source revision, guarded schedule-reset meaning |

**Mandatory additions beyond the 20:**
- `320×568` compact form with multiline Vietnamese + English examples and a conflict alert, no ordinary horizontal overflow; `768×1024` tablet and `1024×768` intermediate layout; `1440×900` representative full shell.
- Same-state **light/dark** full-screen comparison; show semantic error/warning/success distinction.
- At least **two materially different layout compositions** of the Edit form or Save decision hierarchy inside already approved UXR-01 visual identity, with a side-by-side choice board and rationale (does not reopen color/branding approval).
- Additional annotated cases `SOURCE_READ_ERROR`, `SOURCE_AMBIGUOUS`, `SESSION_EXPIRED`, `EDIT_SOURCE_MISSING` and **source changed outside app**. They may share a consolidated storyboard **only if each distinct transition is legible and explicitly annotated**; otherwise separate frames. Don't falsely count a single collage as several 20 primary screenshots.
- **Before/proposed pairs only with genuine current captures.** G4 currently lacks owner screenshots; label `SOURCE_CONFIRMED / NO DIRECT BASELINE CAPTURE` until UXR-00 provides actual visual evidence, not fabricated before screenshots.
- Readable contact sheet plus individual owner-accessible **full-resolution image links** under `docs/design/uxr-04/assets/` or approved persistent storage, with `task|scenario|state|viewport|theme|version|synthetic provenance|date|path`. A local temp directory or source JSX is insufficient.

**Owner decision record:** `version | selected candidate | full image links | confirmed user-visible safeguards | concerns | APPPROVE/REQUEST_CHANGES/REJECT/PENDING | owner response/date`. Treat `APPROVE` (correct spelling) as the only acceptable positive status. Until owner actually views images and explicitly approves the specific version, UXR-04 stays `OWNER_VISUAL_APPROVAL_PENDING`, not DONE. Changed image set requires reapproval. Later UXR-11 still requires integrated nine-group final sign-off.

## 6. Mandatory use of the already-installed Impeccable skill

The owner states [Impeccable](https://github.com/pbakaus/impeccable) is **installed on the Windows machine**. **Do not install/reinstall/update/vendor** it for this workflow.

**For each later authorized local coordinator/worker design session:**
1. Independently discover installed skill base in **the actual worker harness**, read its `SKILL.md` plus relevant command reference. Astra reading an upstream link does **not** prove the worker loaded the installed skill.
2. Invoke `<skill-base-dir>/scripts/impeccable context` **once per session from the English Web project cwd**; when appropriate on Windows use the installed `scripts/impeccable.cmd context`. Record actual result/version/path. Do not guess global install location or repeatedly call context after each UI variant.
3. Apply the installed version's relevant `shape`, `layout`, `distill`, `clarify`, `harden`, `adapt` and `critique` procedures as the problem requires. **Use verbs selectively**, and limit refinement to isolated mockup/spec assets, never production code. Follow any subagent independence rules in the installed critique reference.
4. Keep an auditable per-agent row: `agent role | skill path/version | session/time | context invocation and actual exit/result | reference/command | examined scenario | identified issue | resulting mockup change + image ID`. Coordinator separately records its own use and reconciles worker findings.
5. Missing or broken skill invocation must report `IMPECCABLE_NOT_ACCESSIBLE` with exact error and user-required action; **do not reinstall or mark compliant by citing README**. It blocks the skill acceptance gate until owner resolves it.
6. No skill aesthetic suggestion overrides owner-approved foundation, local/offline rules, non-destructive source edits, field verification or official-only shadcn sourcing.

**This GitHub task preparation has not invoked the locally installed Impeccable skill.** The requirement applies to future authorized local execution.

## 7. Official shadcn/ui-only components and safety rules

**Official source for missing primitives only:** https://ui.shadcn.com/docs/components. Read `components.json`, `frontend/src/index.css` and the [repo's component strategy](../docs/design/shadcn-ui-component-strategy-2026-10-12.md). Existing `Button`, `Card`, Radix-based `Dialog` remain authoritative; use the compatible `new-york`/Tailwind 4 **Radix** flavor.

Propose a documented mapping `surface | official exact component URL | ALREADY_PRESENT/OFFICIAL_PROPOSED/CUSTOM_COMPOSITION/DEFERRED | semantic role | aria/keyboard risk | future owner`:

- Save form and date: existing **Button/Card**, official **Field**, **Input**, **Alert**, **Badge**, **Skeleton**; native `input[type=date]` acceptable; **Date Picker** only when locale/keyboard benefit is justified.
- Source check/read/blocked: **Alert**, **Badge**, **Accordion/Collapsible**, **Separator**, **Tooltip** only where clear additional value.
- Edit bilingual arrays: official **Field**, **Input**, **Textarea** for genuinely multi-line sentences, existing **Button/Card**, **Separator**, **Accordion** for long secondary sections; source/field verification stays labeled.
- Conflict actions: existing **Dialog** or official **Alert Dialog** only with correct destructive semantics, focus control and **no pre-confirmed overwrite**; provide explicit keep-draft/re-read/compare choices. Source re-read is not assumed to fetch changed Word Form body.
- Confirmation/receipt: **Alert**, **Badge**, **Collapsible**, **Table** only if multiple records justify it; avoid gigantic technical receipt Card.

All feature compositions would later live under appropriate `frontend/src/components/app/` or feature directories and **combine approved official primitives**. Do **not** introduce community registries, copied templates, unreviewed Base UI mix, reinstall shadcn, run `shadcn init --force`/`add --all`/`--overwrite`, add packages or alter lockfiles during research/design. Later authorized coding uses scoped pinned CLI diff review and a single shared component owner.

## 8. Required deliverables (only after separate UXR-04 execution approval)

**Exclusive design output root:** `docs/design/uxr-04/`

| Artifact | Required content |
|---|---|
| `UXR-04-SOURCE-STATE-MATRIX.md` | authoritative source states/requests, error/reconciliation/concurrency cases, observed vs source-only evidence |
| `UXR-04-SAVE-PREVIEW-SPEC.md` | date, source-read, ABSENT vs VALID/blocked, save-all, UNKNOWN and durable receipt UI, preview vs stored semantics |
| `UXR-04-EDIT-WORD-FORM-SPEC.md` | bilingual repeatable field layouts, draft preservation, validation, source identity and successful edit feedback |
| `UXR-04-CONFLICT-DECISION-CONTRACT.md` | actual available conflict info, re-read/full-detail comparison needs, no silent overwrite, user choices/focus |
| `UXR-04-RESPONSIVE-A11Y.md` | 320px and zoom, long content, date/field labels, dialog keyboard/focus requirements; no runtime PASS claims |
| `UXR-04-SHADCN-MAPPING.md` | official-only component URLs/statuses, existing Radix compatibility, owner |
| `UXR-04-VISUAL-GALLERY.md` | **20+ primary full-resolution UI frames**, variants, mobile/desktop/light-dark, contact sheets and individual durable links |
| `UXR-04-IMPECCABLE-EVIDENCE.md` | coordinator/each designer actual installed-skill invocation, command/reference and visual impacts |
| `UXR-04-OWNER-DECISION.md` | owner explicit visual version/variant approval or requested revisions; no inferred approval |
| `UXR-04-HANDOFF.md` | frozen Save/Edit visual contracts, UXR-03 seam, UXR-10 consistency and unresolved review risks |
| `assets/*.png` / `assets/*.webp` | owner-visible original composed mockups and genuine before/proposed pairs where available |

These are **future execution deliverables**, not files presently produced by drafting this task.

## 9. Measurable acceptance criteria and Definition of Done

**UXR-04 may be marked DONE only when every criterion is met:**

1. **AC01 Upstream:** links to verified UXR-00 evidence plus explicit UXR-01/02/02A **owner image approvals** and separate UXR-04 execution permission.
2. **AC02 Real visual proposal:** at least **20 primary** full-resolution linked desktop/mobile screen images as §5; plus 320px/tablet/intermediate/wide, theme and variant comparisons; user can inspect without running app.
3. **AC03 Owner signature:** actual owner approves named Save/Edit visual version and specific images, with feedback/decision record. Text-only plans and agent scores cannot pass.
4. **AC04 Preview distinction:** Preview clearly **not yet saved**, all preview forms saved together only after explicit date/source check, no selective POS-only save.
5. **AC05 Source variants:** date `unread/loading/absent/existing VALID/blocked ERROR` accurately mapped; ambiguous, INVALID or MISSING source forbids enabled Save; Bangkok date/selected date and re-read requirements retained.
6. **AC06 Conditional identity:** new source `If-None-Match:*`, existing source `sourceId + sourceRevision + own If-Match ETag`, stable per-intent idempotency specified and not visually bypassed; no client-generated paths/source IDs.
7. **AC07 UNKNOWN safety:** original pending intent and operation identity preserved; no fresh Save during unknown; explicit check/reconcile and no success before verified receipt.
8. **AC08 Receipt truth:** `markdownSync=COMPLETED` confirmation required, source revision/ETag and created/reused cards available in detail, status for schedule effects accurate.
9. **AC09 Edit scope:** source VALID gate, EN/VI meanings, bilingual examples, IPA/Cambridge, focus-safe add/remove and readable long input layouts represented.
10. **AC10 Edit save contract:** exact source precondition `If-Match`, version/ETag, server-defined field errors and retained draft; no use of WordForm revision as write guard.
11. **AC11 Conflict safety:** 409 screen shows known conflict revision, safe compare/re-read/keep-draft decisions; no automatic re-key/retry/overwrite and no invented server diff. Source re-read vs refreshed full detail distinguished.
12. **AC12 SRS semantics:** successful change may reset affected card state per authoritative logic; historical reviews retained and effect is explained without fabricated receipt values.
13. **AC13 Hierarchy:** one dominant context-correct CTA, compact content-based sections and no duplicated all-page status paragraphs; required secondary/critical controls visible.
14. **AC14 Responsive/accessibility:** all target widths and 200%-zoom reflow rules, labeled fields, focus order, dialog return, screen-reader status and error associations documented; no unmeasured WCAG PASS.
15. **AC15 Source evidence:** G4 no-direct-owner-screenshot recorded `NOT_VERIFIED/SOURCE_CONFIRMED`; no fake baseline, committed personal screenshot or real save/test claim.
16. **AC16 shadcn:** official-only component inventory with direct docs URLs, existing Radix primitives reused and no install, dependency or config mutation.
17. **AC17 Impeccable:** coordinator **and every active worker** prove real installed-skill `context` invocation plus chosen guidance and resulting mockup decision; inaccessible skill blocks DONE.
18. **AC18 Ownership:** G2/G3 only visual entry seam, UXR-04 owns Save/Edit content; UXR-08 consent and UXR-05 review algorithms remain untouched.
19. **AC19 Handoff:** approved screenshots/versions, full state matrices, risk log, component mapping and UXR-10/UXR-03 seam links delivered.
20. **AC20 Repo unchanged:** no edits to `frontend/**`, `backend/**`, `components.json`, package locks, SQLite/API/DTO, `tasks/todo.md`; no installation, CI PASS, UXR-00 status change or PR merge.

**State progression:** `PREPARED → READY_FOR_EXECUTION (upstream visual gates + separate owner authorization) → IN_PROGRESS → OWNER_VISUAL_APPROVAL_PENDING → DONE`. Missing actual screenshots, local skill proof or owner sign-off blocks completion.

## 10. Out of scope and non-negotiable constraints

- No coding or implementing Save/Edit, no browser/API mutation, no local agent run during **this task-file preparation**, no dependency/tool installation, and no automation to send AI requests.
- No changing Markdown schema, source files, backend journal, ETag and idempotency contract, recovery semantics, quiz, reviews, SRS scheduling, AI consent or current routes.
- No false claims of existing screenshot coverage (G4 currently not directly captured), tested data corruption, successful UI interactions, WCAG 2.2 AA compliance or completed visual approval.
- No silently implemented comparison endpoint, cross-tab autosave, account/cloud sync, import, Book/Library/chapters/IELTS/TOEIC routes or hypothetical future functionality.
- No unsanctioned rework of UXR-01/02/02A foundations, no UXR-11 final sign-off, no adoption of proposed UXR-12 and no merging PR #26.
- A prettier dialog that hides actual source changes or encourages unreviewed overwrites is **not** acceptable simplification.

## 11. Parallel work, coordinator responsibilities and file ownership

**Dependency topology:** UXR-00 → 01 → 02 → 02A → {03, **04**, 05, 06, 07, 08, 09} → 10 → 11. Parallel **design execution** is permissible only after UXR-02A was actually owner-approved. Task specification preparation remains sequential with owner permission after each file.

Within an authorized UXR-04 session, independent local agents may analyze Save state, Edit/Conflict state and shadcn/a11y/risk, and render their own image sets. **One integration lead** merges coherent tokens/wording/state semantics and presents one owner packet. Every worker invoking design guidance must load/run Impeccable independently. No duplicated reading loops or conflicting edits to one approval log.

| Path or area | Owner and access |
|---|---|
| `tasks/uxr-04-save-edit-vocabulary-design.md` | task-spec coordinator only |
| `docs/design/uxr-04/UXR-04-*-SPEC.md`, state matrix, conflict contract, gallery, approval, handoff | UXR-04 integration lead **single writer** for consolidated outputs |
| `docs/design/uxr-04/assets/save-*` | designated SavePreview visual worker |
| `docs/design/uxr-04/assets/edit-*`, `assets/conflict-*` | designated Edit/Conflict visual worker |
| `docs/design/uxr-04/UXR-04-IMPECCABLE-EVIDENCE.md` | lead consolidates each actual worker invocation, without fabricating |
| `docs/design/uxr-03/**`, `uxr-02/**`, `uxr-02a/**`, UXR-00 artifacts | **read only**, shared design/seam through handoff |
| `docs/design/english-web-ui-ux-redesign-plan-2026-10-12.md` and Draft PR #26 | **one research coordinator**, workers read only |
| `frontend/**`, `backend/**`, `components.json`, package locks, `tasks/todo.md` | **read only**, no installation/implementation |
| `docs/design/uxr-visual-approval-impeccable-protocol-2026-10-12.md` | shared coordinator policy, read only to workers |

Feature-specific proposals must not independently rewrite common Sidebar/tokens, official primitives or UXR-02A density rules. If a conflict requires a shared design change, obtain coordinator mediation and explicit owner approval for the affected frozen image version.

## 12. Handoff to UXR-05 and later UXR-10

**Preparation handoff:** after committing this UXR-04 task, the next task-card eligible for owner permission is **UXR-05 — Review Flashcards Design**. Do **not** draft UXR-05 without owner approval. UXR-04 **execution** can still proceed independently of UXR-05 once the shared UXR-02A gate and UXR-04-specific permission are fulfilled.

**Future design handoff:** once actual UXR-04 images have been owner-approved, send UXR-03 (seam) and UXR-10 (cross-screen QA):
- Versioned full-resolution Save/Edit/Conflict screenshots and owner decision ledger.
- State/action table for source absent/VALID/INVALID/MISSING/ambiguous, date selection, pending/UNKNOWN and successful receipt.
- Editing-field error, preserved draft, new/current source comparison and explicit non-destructive 409 resolution contract.
- Official-only shadcn inventory and each worker's actual Impeccable evidence.
- 320px/mobile/zoom/focus requirements, pending runtime verification, accurate semantic messages and unchanged local-API/SRS rules.

UXR-10 checks these against Lookup Preview, Word Detail, Review, Dashboard and shared Status/Consent semantics. UXR-11 still requires final nine-group owner image approval. This document is a **prepared task specification only**; no mockups, code implementation, local skill invocation, audit completion or final sign-off is claimed.

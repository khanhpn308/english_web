# UXR-08 — Status, Consent & Error States Design

## CURRENT OWNER AUTHORIZATION — 2026-10-14 — DESIGN + FRONTEND IMPLEMENTATION

> **Binding amendment.** The owner changed UXR-08 from design-only research to **Design + Frontend Implementation** on 2026-10-14. [Shared implementation policy](../docs/design/uxr-03-09-design-frontend-implementation-policy-2026-10-14.md) is binding. The original task's source/evidence, feature semantics, all visual frame/viewport quotas, Impeccable, official shadcn, accessibility, and explicit owner visual approval requirements remain mandatory. Historical `design-only`, `no frontend edits`, `no code`, `no tests`, and `no implementation` clauses are **SUPERSEDED for the explicitly owned frontend scope only**. This section prevails over contradictory legacy clauses below. Application backend/API/DB/contracts still remain protected.

**CURRENT STATUS:** `READY_FOR_DESIGN_PLUS_FRONTEND_IMPLEMENTATION / NOT_STARTED` (UXR-02A owner-approved and published; launching Codex work still requires the owner's instruction).  
**CURRENT ACTION:** Design the complete UXR-08 feature experience **and implement it in the actual existing React/TypeScript/Tailwind frontend**, keeping the approved UXR-01/02/02A foundation unchanged.  
**OUTPUT STATE:** `OWNER_VISUAL_AND_IMPLEMENTATION_APPROVAL_PENDING`, not `DONE`, until owner review.  
**BASE:** `57159675fc59e984db1d64dcd899aedabf6622ff`; existing `design/uxr-08` worktree must safely fast-forward to the updated specification before execution.

### New authorized deliverables for UXR-08

1. Preserve **every original scenario, minimum full-resolution screenshot count, comparative evidence, and state/viewport gate specified later in this task**; additionally show the actual running application frontend implementing the design, not solely isolated mockups.
2. Implement the feature-owned frontend surfaces, preserving current app routes and supported API contracts. **Candidate ownership allowlist:** `frontend/src/features/status/** and truly owned error presentation components only; feature-local tests/styles`. Inspect the actual repo to resolve paths; if an expected file moved, document the precise verified path. No arbitrary changes outside the feature boundary.
3. **Primary implementation targets:** StatusPage.tsx, consent visualization and safe error/status components. The approved design direction is UXR-01 Compact Study Console v1.2 + UXR-02 AppShell R2/HM-FIX + UXR-02A Variant B/R1B. Do not redesign shared foundation.
4. **Read-only/cross-task seam:** backend consent/AI state, shared error response contracts, global AppShell. If a necessary change touches a shared/cross-feature file, record a proposed integration patch or ask for an explicit single-writer owner/coordinator decision; do not modify in two parallel worktrees.
5. No invented data or backend capabilities: preserve null/zero/UNKNOWN/error boundaries, existing operation contracts, idempotency, revision/reconciliation, user consent, and status truthfulness as applicable. Mark screenshots as `RUNNING_FRONTEND`, `ISOLATED_MOCKUP` or `SYNTHETIC_FIXTURE` accurately.
6. New implementation acceptance: actual TSX/styles changed; actual app can mount the affected route; representative functional interactions can be exercised against existing contracts or explicitly labeled fixtures; required full-resolution UI frames captured from the running frontend; feature-local build/type/browser check results documented. Full-system tests/audit remain for a later wave; do not fabricate PASS.
7. Every frontend-design Worker explicitly invokes installed `$frontend-ui-engineering`, plus relevant addyosmani skills and installed Impeccable in its own context; Astra acts as coordinator/auditor/integrator, delegates GPT-6.1 Sol Worker packages with single-writer file ownership.
8. Request `speed: fast`, `permission: full-access` via actual supported runtime controls, but still obey the file allowlist. On the exact model-capacity error, retry dispatch with a real 3s delay up to 30 times, then replace the blocked, non-running worker (max 3 replacement workers per package) without changing model or duplicating writes. Disclose unverified actual-model/speed/permission metadata.
9. No new dependencies or shadcn installation without separate approval; reuse current canonical primitives. No unapproved edits to `backend/**`, SQLite, API/DTO/OpenAPI, generated contracts, SRS/quiz/consent business semantics, main, UXR-02A frozen artifacts, `tasks/todo.md`, or shared app shell. No automatic commit/push/merge; stop for owner visual + implementation review.
10. Acceptance item previously reading `no app/frontend code changes` is now `no unauthorized code changes outside owned frontend`; any other old item only contradicted by this explicit amendment is `SUPERSEDED_BY_OWNER_2026-10-14`, **not PASS**. Add an `IMPLEMENTATION_GATE` alongside all original design AC. No existing critical visual or safety criterion is waived.

---


**Track:** English Web final UI/UX redesign — design research only, separate from canonical application tasks T001–T090.
**Group:** G8 Status, Consent & Error States. Routes: `/status`, `/status#ai-consent` and existing shared consent/recovery surfaces.
**Status:** `PREPARED / NOT STARTED / BLOCKED_BY_UXR_02A_OWNER_VISUAL_SIGNOFF`.
**Authorization:** On 2026-10-12 the owner approved **preparing this task specification and updating the design roadmap and Draft PR #26**. There is **no approval** to execute visual design, modify app code, install or run UI tooling, render and approve mockups, test, audit, mark task DONE or merge.
**Prerequisite to actual design execution:** UXR-00 final verified evidence → UXR-01 image-selected owner-approved visual direction → UXR-02 owner-approved AppShell images → UXR-02A owner-approved density/gallery → separate owner authorization for UXR-08 execution. Another explicit owner visual decision is required to close UXR-08, and UXR-11 separately signs off the final integration.
**Parallel peers:** UXR-03–09 independently assigned feature design can run in parallel **only after actual UXR-02A sign-off** and corresponding feature execution authorization. Task-file preparation is not execution.
**Branch:** `design/ui-ux-research-20261012`; [Draft PR #26](https://github.com/khanhpn308/english_web/pull/26) stays OPEN/DRAFT/unmerged.
**Binding cross-task contract:** [Owner-visible images / installed Impeccable / official shadcn/ui](../docs/design/uxr-visual-approval-impeccable-protocol-2026-10-12.md).

## 1. Objective and owned surface

Prepare a precise, compact, **image-reviewable** design for a learner-first Status page, separate AI-data consent panel/dialog and safe error recovery presentations. Above the fold the learner should know: whether local learning is usable, whether any **active** critical incident exists, whether AI data sharing is currently permitted, and when the evidence was last fetched. All detailed technical evidence remains available by accessible disclosure rather than dominating the page.

UXR-08 owns **visual contracts**, not production code or system policy. In scope: `StatusPage`, `AiConsentPanel`, `AiConsentGate` policy dialog (visual semantics), shared `RecoveryPanel`, offline capability grouping, alert/state labels, responsive/a11y patterns and links between features. Out of scope: UXR-02 AppShell, UXR-02A approved density layout, UXR-03/04/05/06/07 feature mutation/replay logic, UXR-09 Dashboard learning analytics, local API implementation, SQLite, policy changes and Windows launcher coding.

The owner must **see full-resolution composed UI pictures before selecting a final design**, not just read specs, component lists, ASCII or JSX.

## 2. Verified repository sources and confidence labels

| Source | Confirmed rule that future visuals must honor |
|---|---|
| `frontend/src/features/status/StatusPage.tsx` | `GET /api/v1/status`, `cache=no-store`, validates status DTO; server readiness `NOT_READY/SYNCING/READY/DEGRADED/UNKNOWN`, bridge `NOT_CHECKED/OK/NOT_READY`, storage, index, source counts, offline capabilities, metrics, local alerts. |
| `StatusPage.tsx` | Manual Refresh and automatic 30-second poll while visible, refetch on focus/visibility/invalidation. A failed later poll can coexist with previously loaded `data`; its age matters. This is **not** push/continuous live status. |
| `StatusPage.tsx` | Seven LocalAlert categories. **State** `ACTIVE/RESOLVED/INACTIVE/UNKNOWN`, **observation** `MEASURED/NO_DATA/INCOMPLETE`, **severity** `ticket/page-equivalent` have distinct meanings. Potential high severity does not prove an ACTIVE incident; no samples do not prove health. |
| `StatusPage.tsx` | Existing lengthy sections: alerts, readiness, SQLite/storage, Markdown/source sync, AI bridge/model, offline capabilities, RED metrics, runbooks and AI consent panel at bottom. Compact grouping may reorganize, not discard, evidence or hide active alarms. |
| `frontend/src/features/consent/AiConsentPanel.tsx` | Actual `#ai-consent` anchor; current server consent state, revision, last choice, blocked policy, disclosure, read/review/revoke and same-intent retry. Explicit warning: already-sent AI requests might finish; revoke does not erase previously sent data or local learning data. |
| `frontend/src/features/consent/AiConsentGate.tsx` | Dialog and provider; state `NOT_GRANTED/GRANTED/REVOKED/STALE`, with unavailable/UNKNOWN read state separately. Current server policy/version/digest/ETag, policy completeness, current permission and no unresolved mutation gate all AI dispatches. |
| `AiConsentGate.tsx` | Policy includes categories, recipients, scopes `LOOKUP/QUIZ_GENERATION/WRITING_FEEDBACK`, provider/model/routing/billing, retention, region, cost/quota and withdrawal; ready policy required, incomplete/digest-mismatched policy **fails closed**. Consent never comes from browser-local permission guess. |
| `AiConsentGate.tsx` | Grant PUT uses displayed policy and matching `If-Match` ETag + stable Idempotency-Key; revoke DELETE uses local session and idempotency key **without AI bridge or policy ETag dependency**. Pending/unknown intent requires same-intent server reconciliation. Granting permission **does not automatically re-dispatch** original AI request. |
| `AiConsentGate.tsx` | Dialog focus trap/title and return focus; Escape/close/`Chưa đồng ý` is not consent; policy invalidated on focus/visibility/cross-tab notifications, fresh GET before AI. Shared panel must remain reachable independent of bridge health. |
| `frontend/src/shared/errors/RecoveryPanel.tsx` | **Actual path**, not `frontend/src/components/app/RecoveryPanel.tsx`. Uses `mapErrorToUIState`: `RETRY/RECONCILE/REBOOTSTRAP/RELOAD/UPDATE_CONSENT`; callbacks are optional; source displays English generic button labels. Correct Vietnamese contextual copy is a future design proposal, not implemented code. |
| `docs/design/ui-visual-audit-2026-10-12-batch2.md` | **G8 PARTIAL**, five desktop Status captures including lower Consent Card. VIS-001–005 record confusing potential-severity emphasis, excessive scroll, raw code hierarchy, prominent revoke under REVOKED and duplicated offline wording. **No verified owner capture** of Dialog open, RecoveryPanel actual error or mobile states. |
| `docs/ui-architecture.md` §J6/J7 | Local learning when healthy local API but external network/bridge down; in-app `/status` is **not** a substitute for a native/static launcher fallback if backend cannot start. Permission is fail-closed, requires current policy; no credential-entry or cloud account form. |

**Provenance:** `CURRENT_APP_CAPTURE` only with genuine screenshot bytes and metadata; `SOURCE_CONFIRMED` for repository-inspected logic; `DESIGN_MOCKUP/SYNTHETIC` for future art; `NOT_VERIFIED` where runtime/real screenshot absent. No claims of verified API outage, working consent, WCAG PASS or captured mobile UI based on code inspection.

## 3. Execution start conditions

This task card can be prepared now; **actual UXR-08 execution cannot start** until UXR-00 evidence and **owner image sign-offs for UXR-01, UXR-02, UXR-02A** plus separate permission for UXR-08 execution are linked. Assign one integration lead and distinct Status/Consent/Recovery image-worker owners. Follow approved identity, shell, density, source data and route/focus contracts. UXR-08 feature designers cannot overwrite shared UXR-02/02A tokens or other feature worktrees.

Coordinator **and every active worker** must independently load/run the already-installed local Impeccable skill, preserve real context evidence and use official-only shadcn primitives. GitHub-only preparation is not proof of skill invocation or screenshot completion.

## 4. Status overview and two-layer information architecture

**First fold — learner decisions:** current read status and freshness; server readiness `READY/SYNCING/DEGRADED/NOT_READY/UNKNOWN`, real ACTIVE incidents prioritized by observed alert state; local learning eligibility (local API/storage/source), independently read AI consent, bridge status as separate evidence, a clear link to `/status#ai-consent` and a single readable Refresh action. A status poll success timestamp isn't an unconditional “healthy now” guarantee. A failed refresh with previous data becomes explicitly **stale / last known**, not fresh green.

**Alert correctness:** `severity=page-equivalent` is *potential impact when ACTIVE*, not live emergency. Do not display red critical alarm based on severity if `state=UNKNOWN/INACTIVE/RESOLVED`. Likewise `NO_DATA/INCOMPLETE` ≠ PASS; true ACTIVE critical alerts cannot be hidden behind collapsed diagnostics. Show state and observation with text/icon, not only color.

**Second layer — grouped disclosures:** Health & 7 alerts, SQLite/storage/integrity, Markdown/source sync and search index, AI bridge/config, offline capability groups, local request/error/latency metrics, and genuine existing runbook links. Preserve read-only/source-invalid effects, dates, sample counts, severity/observations, last polled time, technical request IDs and runbook destinations; move operator detail behind accessible Accordions/Collapsibles, **not discard** the data or hide operational warnings.

**Offline capabilities:** local Search/Review/Dashboard/Created Quiz can function without external AI internet **only if local API healthy**; new Lookup/Quiz generation/Writing Feedback need AI bridge plus appropriate current permission; browser SpeechSynthesis depends on installed/browser voice. False/true/null represent different capabilities; an unresponsive local API must not be described as fully offline-operational.

**Native fallback:** propose only a clearly **DESIGN_MOCKUP** launcher/static fallback contract for backend unavailable; do not claim that React `/status` can run without its local API, and do not implement launcher UI.

## 5. Explicit AI disclosure and permission contract

**State hierarchy:** `NOT_GRANTED` (review policy first), `GRANTED` (current permission only when policy/version/digest/ETag and server `canRequestAi` match), `REVOKED` (new AI calls stopped; policy review to regrant), `STALE` (re-read changed policy), and `UNKNOWN`/policy missing (fail closed). Bridge `OK` is **not** proof of consent. Consent GRANTED is **not** proof provider is online.

**Before granting:** full readable server-sourced scope/provider/model/data recipients/retention/region/cost/quota/withdrawal statements, version and digest accessible; no prechecked agreement, hidden disclosures or shortened misleading summary. `Chưa đồng ý`, Escape, close do **not** grant or send data. Maintain Dialog focus trap, title focus on open and return-to-invoker focus on close.

**Grant:** explicit action uses backend policy version/digest and GET ETag `If-Match` with a stable idempotency key. Stale/digest mismatch prevents action, requires new disclosure. After the server confirms grant, **return to initiator without automatically sending a Lookup, Quiz generation or Writing Feedback request**; the user must click that action anew.

**Revoke:** local DELETE only, no bridge/policy ETag prerequisite; pending immediately blocks new AI requests, but success copy requires validated receipt/current server state. Unknown/timeout is “chưa xác nhận rút quyền”; keep original PUT/DELETE intent and same-key recovery (not an unannounced new mutation). Preserve warning: **“Yêu cầu đã gửi có thể vẫn hoàn tất; thao tác này không xóa dữ liệu đã gửi hoặc dữ liệu học trên máy.”** In screenshot REVOKED, redesign primary hierarchy so redundant red revoke is not dominant, but do not silently change backend idempotency/retry semantics.

**Cross-tab/incomplete state:** focus, visibility and BroadcastChannel invalidation keep displays fresh; browser cache does not grant permission. A previously acknowledged grant cannot authorize an AI action if server policy is now STALE. Existing client intent in mounted provider does not prove recovery across process restart; document that limitation honestly.

## 6. Shared error and recovery presentation, not business-logic ownership

Source: `frontend/src/shared/errors/RecoveryPanel.tsx` and `frontend/src/shared/api/errors.ts`. Produce a table `error/source|certainty|preserved user data|actionType|available callback|primary CTA|secondary action|focus announcement|image ID`.

| Existing action | Proposed Vietnamese UX label | Mandatory safety semantics |
|---|---|---|
| `RETRY` | Thử lại | Only when server outcome is proven rejected or operation is a harmless read; not a fresh mutation in UNKNOWN |
| `RECONCILE` | Kiểm tra kết quả thao tác | Use original idempotency key/operation when available; do not send new request with changed intent |
| `REBOOTSTRAP` | Khởi chạy lại phiên từ launcher | Native/local session recovery, not a new cloud login or background AI dispatch |
| `RELOAD` | Đọc lại dữ liệu | Refetch authoritative current state; do not overwrite unsaved user draft |
| `UPDATE_CONSENT` | Kiểm tra quyền AI | Refetch server permission/policy; granting still needs explicit user action, no auto-send |
| No valid handler / dismiss | Đóng / xem Trạng thái | Never show inert primary button when its callback is absent; request ID disclosed secondarily |

Make genuinely different error screens for local API stopped, SQLite busy, Markdown invalid, source conflict, session expiration, optional AI bridge unavailable, consent stale, mutation `UNKNOWN`, incomplete telemetry. User intent and card/quiz/draft recovery stay with UXR-03–07; this task owns **shared visual language and action/callback contract**, not generic mutation reconciliation logic. No color-only error, no infinite fake spinner, no assumption unknown is failure. Shared RecoveryPanel source currently uses English labels — proposal can localize without claiming deployed translation.

## 7. Mandatory owner-visible image gallery and explicit sign-off

During later separately authorized UXR-08 design work require **at least 30 original, full-resolution, readable PNG/WebP UI compositions**, representing **15 scenarios × two complete-screen CSS viewports**: `1366×768` desktop and `390×844` mobile. Images use approved UXR-01 identity, UXR-02 AppShell, UXR-02A density. Synthetic health/incident/policy fixtures must be visibly labeled **DESIGN_MOCKUP / SYNTHETIC**.

| Pair IDs | Screen/state | What the owner should visibly understand |
|---|---|---|
| ST01–02 | READY learner-first Status | Compact local health/consent summary, timestamp, refresh, anchor |
| ST03–04 | UNKNOWN or stale Status | No false healthy or current availability conclusion |
| ST05–06 | ACTIVE critical alert | True active state, potential severity, relevant runbook |
| ST07–08 | INACTIVE/RESOLVED with high potential severity | High severity does not imply active incident |
| ST09–10 | Storage BUSY / read-only source | Correctly limited local writes and safe status |
| ST11–12 | Expandable storage, Markdown, index and metrics | Complete diagnostic detail, NO_DATA not zero |
| ST13–14 | Offline matrix; bridge NOT_CHECKED | Local API versus bridge, browser audio conditional |
| ST15–16 | Status read/error + shared RecoveryPanel | Retry/reload/rebootstrap based on real failure |
| CN01–02 | NOT_GRANTED consent entry | Policy review path, no automatic permission |
| CN03–04 | Full policy dialog before grant | Data scopes/recipients/provider/retention/region/cost/withdrawal and decline |
| CN05–06 | GRANTED but AI bridge not ready | Independent consent and provider status |
| CN07–08 | REVOKED | No dominant redundant revoke, truthful already-sent warning |
| CN09–10 | STALE/incomplete policy | Fail closed, new review, no AI dispatch |
| CN11–12 | PENDING/UNKNOWN grant or revoke | Separate PUT/DELETE identity and same-intent check |
| ER01–02 | Contextual recovery after session/unknown | Correct RECONCILE/REBOOTSTRAP/UPDATE_CONSENT action |

**30 primary images are 15 genuine desktop/mobile pairs**, not one collage counted 30 times. Additional required evidence:
- `320×568` narrow Policy/ACTIVE alert/Recovery stress, `768×1024` tablet, `1024×768` intermediate and `1440×900` wide shell; document 200%-zoom reflow and long Vietnamese policy/ID wrap.
- Same-state full-screen light/dark comparison and **two materially different first-fold Status/Consent layout compositions** shown on desktop **and mobile**, without reopening already approved brand/tokens.
- More detailed storyboards for explicit Consent grant then **no automatic AI dispatch**, revocation before confirmation, session rebootstrap, Native fallback proposal, and unresolved original operation vs retry. Any uncaptured current state must be marked **SOURCE_CONFIRMED / NOT_VERIFIED CURRENT CAPTURE**.
- Genuine old-vs-new comparisons only with actual owner Status capture files; missing current Consent Dialog/Recovery/mobile screenshots are **never fabricated**.
- Owner-accessible **readable contact sheet and individual original full-resolution links** under `docs/design/uxr-08/assets/` or explicitly approved persistent destination. Each asset metadata: `task|screen|state|ID|CSS viewport|theme|A/B|provenance|SYNTHETIC|version/date|link`.

**Owner approval record:** `named version|chosen layout|actual image links|feedback|APPROVE/REQUEST_CHANGES/REJECT/PENDING|owner date`. Agent opinions, Markdown specs or unrendered prototypes cannot replace explicit user image approval. When images change materially, require reapproval. UXR-11 separately requires final nine-group signoff.

## 8. Mandatory Impeccable — already-installed skill, real per-session calls

The user reports [pbakaus/impeccable](https://github.com/pbakaus/impeccable) is **already installed on Windows**. **Do not reinstall, update, vendor or download** the skill. For each later authorized local design session:
1. Coordinator **and every independent Status, Consent, Error, mobile or visual-critique worker** separately discover their installed skill in **their own agent harness**, read installed `SKILL.md` and applicable references. Coordinator summary / public README does not establish a worker used the skill.
2. Run `<skill-base>/scripts/impeccable context` **once per session from the project root** (installed Windows `scripts/impeccable.cmd context` if provided). Record actual path/version, session, command output and result; don't assume location or claim execution from GitHub-only edits.
3. Select real installed-version guidance: `shape/layout/distill` for learner-first Status; `clarify` for alert and consent vocabulary; `harden` for UNKNOWN/policy/rebootstrap; `adapt` for 320px long policy; `critique` for hierarchy and a11y. Apply selectively, preserving actual backend semantics.
4. Record one row per agent: `role/session|installed skill path/version|context invocation/result|reference|issue|changed UI/image ID` in future `UXR-08-IMPECCABLE-EVIDENCE.md`. Coordinator logs its own genuine call and collects worker-specific evidence.
5. Unavailable skill must report `IMPECCABLE_NOT_ACCESSIBLE` with real error. No automatic reinstall, no false PASS or final DONE while required skill evidence is absent.
6. Skill suggestions cannot override approved UXR-01/02/02A images, AI policy/consent safety, local-first scope or official components.

**This GitHub task preparation has NOT invoked the owner's local Impeccable installation.** It is a future design-execution gate.

## 9. Official shadcn/ui-only component mapping

Single authorized origin for **missing reusable UI components**: https://ui.shadcn.com/docs/components. Consult [project strategy](../docs/design/shadcn-ui-component-strategy-2026-10-12.md) and existing `components.json`; reuse current Radix/new-york/Tailwind-4-compatible `Button/Card/Dialog`, respecting no-Preflight CSS baseline.

Later `UXR-08-SHADCN-MAPPING.md` must list `surface|exact official docs URL|ALREADY_PRESENT/OFFICIAL_PROPOSED/COMPOSITION/DEFERRED|keyboard/ARIA|owner`.

| Area | Official component candidates | Guard |
|---|---|---|
| Status overview | Existing Card/Button; official Badge, Alert, Separator, Skeleton | ACTIVE vs UNKNOWN text, freshness, correct priority |
| Diagnostics and offline groups | Official Accordion, Collapsible, Table, Tabs only if warranted | Retain alerts, sample counts and runbook links |
| Consent panel and disclosure | Existing Dialog, official Alert, Scroll Area, Badge, Separator | Unabridged disclosure, focus/deny, no automatic grant |
| Uncertain grant/revoke | Existing Button/Dialog, official Alert, Collapsible, Skeleton | Differentiate pending/unknown/confirmed and idempotency |
| Recovery and local health | Existing Button/Card, official Alert, Badge | ActionType callback correctness, no inert primary CTA |
| Metrics/runbooks | Official Accordion/Table only if real data supports | No invented metrics or extra remote actions |

Future app compositions could be `LocalHealthSummary`, `ActiveIncidentList`, `ConsentStatusSummary`, `PolicyDisclosureView`, `ContextualRecovery`, built **from the existing and official primitives**, not installed today. No community registry, Base UI/Radix mix, shadcn `init --force`, `add --all`, `--overwrite`, npm install, lockfile/CSS/component changes during task preparation/design. A later coded implementation needs separate owner authorization and pinned official source/CLI diff review by a shared primitive owner.

## 10. Planned execution deliverables — none generated now

**Output root:** `docs/design/uxr-08/`.

| Future file | Required proof |
|---|---|
| `UXR-08-SOURCE-STATE-MATRIX.md` | Actual readiness, alerts, bridge, consent, errors, observation vs severity and baseline evidence |
| `UXR-08-STATUS-OVERVIEW-SPEC.md` | Two-layer layout, active warning, freshness, local vs remote health |
| `UXR-08-CONSENT-POLICY-SPEC.md` | Disclosure and fail-closed grant/revoke, current ETag/digest, no auto-dispatch, pending/unknown |
| `UXR-08-ERROR-RECOVERY-CONTRACT.md` | Per-actionType callback map, certainty and no-new-mutation handling |
| `UXR-08-OFFLINE-RESPONSIVE-A11Y.md` | Backend vs bridge offline, 320px, 200%-zoom, keyboard and dialog focus |
| `UXR-08-SHADCN-MAPPING.md` | Official catalog URLs, reused/proposed status and Radix compatibility |
| `UXR-08-VISUAL-GALLERY.md` + `assets/*.png`/`*.webp` | ≥30 full-resolution image originals, alternatives, responsive, readable contact sheets/links |
| `UXR-08-IMPECCABLE-EVIDENCE.md` | Genuine installed-skill context/impact rows per worker/coordinator or blocker |
| `UXR-08-OWNER-DECISION.md` | Explicit owner-visible image version/choice, feedback and signoff |
| `UXR-08-HANDOFF.md` | Frozen G8 visual/policy safety contract and UXR-03–07/09/10 interfaces |

These **do not exist as outputs of preparing this task card**. Creating a spec does not generate screenshots, test services or invoke a local skill.

## 11. Definition of Done — 22 measurable acceptance criteria

1. **AC01** — UXR-00 verified final evidence; UXR-01, UXR-02 and UXR-02A actual **owner-image approvals**, plus separate permission to execute UXR-08.
2. **AC02** — ≥30 primary full-resolution UI image frames (15 desktop/mobile pairs) plus additional responsive/theme/A-B states with persistent owner-visible links.
3. **AC03** — Owner explicitly sees and approves named G8 Status, Consent Dialog and Recovery image version; text-only/agent approval never sufficient.
4. **AC04** — First fold displays local readiness, separately sourced consent, actual active alerts, freshness and manual Refresh in approved density.
5. **AC05** — Readiness `READY/SYNCING/DEGRADED/NOT_READY/UNKNOWN` truthful; stale server data not promoted to current healthy.
6. **AC06** — Alert `ACTIVE/RESOLVED/INACTIVE/UNKNOWN` distinguished from severity and `MEASURED/NO_DATA/INCOMPLETE`; critical ACTIVE not hidden.
7. **AC07** — Null/unknown bridge, metrics, source/index and conditional SpeechSynthesis remain unknown, not false 0/PASS.
8. **AC08** — SQLite/Markdown/bridge/offline/metrics/runbooks remain accessible in meaningful categories with real runbook links.
9. **AC09** — Healthy local API vs remote AI bridge dependency clear; existing study not blocked by optional remote AI failure.
10. **AC10** — `/status#ai-consent` reachable and keyboard-focusable; Status consent independent of bridge readiness.
11. **AC11** — NOT_GRANTED/GRANTED/REVOKED/STALE/UNKNOWN and policy-not-ready all have distinct safe consent UI choices.
12. **AC12** — Complete policy scopes, recipients, categories, provider/retention/region/cost/withdrawal exposed; no preselected consent or false agreement on close/Escape.
13. **AC13** — Grant uses current version/digest/server ETag and stable idempotency; no automatic Lookup/Quiz/Feedback dispatch after approval.
14. **AC14** — Revoke works without provider/bridge readiness; pending disables new actions; outcome UNKNOWN vs confirmed and already-sent disclosure accurate.
15. **AC15** — Cross-tab permission refresh, backend authoritative gating and stale/digest mismatch re-review; no cached-grant bypass.
16. **AC16** — Unresolved PUT/DELETE safe same-intent reconciliation and no invented persistence across reboot.
17. **AC17** — Recovery path `shared/errors/RecoveryPanel.tsx`, correct `RETRY/RECONCILE/REBOOTSTRAP/RELOAD/UPDATE_CONSENT` mapping and no inert primary button.
18. **AC18** — API down/session expiry/SQLite busy/source invalid/AI bridge unavailable/UNKNOWN are not collapsed into generic failure and unsafe retry.
19. **AC19** — 320px and effective 200%-zoom, light/dark, focus trap/restore, semantic live regions and keyboard accessibility design documented; no unmeasured WCAG PASS claim.
20. **AC20** — Official shadcn docs only for missing components, reused Radix-compatible existing primitives, no installs/source/lock/config modifications.
21. **AC21** — Coordinator and each real design worker independently invoked installed Impeccable and logged actionable image change; `IMPECCABLE_NOT_ACCESSIBLE` prevents completion.
22. **AC22** — Versioned images/owner decision/handoffs to UXR-03–07, UXR-09/10; no app code/API/SQLite/consent/SRS modification, `tasks/todo.md`, test PASS, UXR-00 closure or PR merge.

**Actual lifecycle:** `PREPARED → READY_FOR_EXECUTION (upstream approved visuals + new execution permission) → IN_PROGRESS → OWNER_VISUAL_APPROVAL_PENDING → DONE`. Owner must explicitly approve the generated image set before any real DONE.

## 12. Worktree ownership, exclusions and owner stop

Later separately authorized work: UXR-08 integration lead single-writes consolidated specs, screenshot inventory, owner decision and Impeccable report; Status worker exclusively owns `docs/design/uxr-08/assets/status-*`; Consent worker `assets/consent-*`; Recovery worker `assets/recovery-*`. Independent per-agent skill calls mandatory. Research coordinator alone edits roadmap and PR metadata. UXR-00 captures, UXR-01/02/02A approved foundations, and every other UXR feature directory remain read-only to G8 workers.

All `frontend/**`, `backend/**`, `components.json`, package locks, SQLite, generated DTOs, `tasks/todo.md`, provider configuration/secrets and launcher source **remain untouched** in task preparation and design. No local app/browser/mockup/skill execution claimed. Do not alter consent policy, create account/login pages, add health probes or new product features, declare CI/WCAG PASS, merge Draft PR #26, close UXR-00 or authorize future UXR-12.

**STOP after UXR-08 file creation, roadmap + Draft PR #26 metadata and verification. UXR-09 — Dashboard Design preparation requires explicit separate owner approval.**

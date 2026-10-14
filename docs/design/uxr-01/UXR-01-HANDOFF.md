# UXR-01 handoff — owner visual review packet

**TASK_ID: UXR-01**  
**STATUS: DONE / DESIGN_DECISIONS_APPROVED / DOCUMENTATION_VALIDATED / PUBLISHED**  
**DESIGN_DECISIONS_APPROVED:** D1/D2/D3/D4/D6/D8/D9 on 13/10/2026; D5 deferred to UXR-06; D7 future/unapproved  
**DOCUMENTATION_VALIDATED:** YES (local asset, manifest, JSON and Markdown checks recorded below)  
**SECRET_SCAN_PASSED:** YES — pinned Gitleaks 8.30.1 returned exit 0 with zero findings after approved exact historical exceptions and current prose corrections  
**GIT_PUBLISHED:** YES; **RESEARCH_BRANCH_INTEGRATED:** YES; **TASK_DONE:** YES  
**UXR00_EVIDENCE: PARTIAL (actual handoff and all 21 canonical assets verified accessible)**  
**BASE_SHA: c2417ba6ff1db131fd3259faf67100fda6c3928b** (audit)  
**WORKTREE_BASE_SHA: aaf1629f5680da89c6117e42880565450439a6cc**  
**WORKING_BRANCH: work/uxr01-design**  
**WORKTREE: C:/Users/khanh/projects/english-web-uxr01**  
**VISUAL_VERSION: v1.2**  
**DIRECTION_A_IMAGE_COUNT: 27**  
**DIRECTION_B_IMAGE_COUNT: 27**  
**RECOMMENDED_DIRECTION: superseded by owner selection — B v1.2 — Compact Study Console**  
**SELECTED_DIRECTION: B**  
**SELECTED_VERSION: v1.2**  
**OWNER_DECISION: APPROVE_DIRECTION_B**  
**DECISION_ID: UXR01-D1**

Review the [A gallery](UXR-01-VISUAL-GALLERY.md#direction-a-v12), [B gallery](UXR-01-VISUAL-GALLERY.md#direction-b-v12), [comparison matrix](UXR-01-DIRECTION-COMPARISON.md), [owner decision sheet](UXR-01-DESIGN-DECISION.md), and [R1 evidence delta](UXR-01-R1-EVIDENCE-DELTA.md). The earlier recommendation for A and equal 26/30 scores are historical comparison evidence; the owner selected B. Every original full-resolution image remains individually linked. Synthetic frames are not current-app captures.

## Evidence and version boundaries

The UXR-00 originals remain unchanged in the original checkout. The task folder includes byte-identical copies of final handoff reports, source/design/browser reports, and the 21 canonical existing-app captures for accessible review. The legacy duplicate and owner desktop attachments were excluded. [Evidence ledger](UXR-01-EVIDENCE-LEDGER.md) lists every gap. R1 now supplies three synthetic current-app renders for G7 submitted/validated states and G9 populated state; these are additive evidence, not production-data captures. G7 transitions, persistence, provider behavior and G9 mixed/null current-app coverage remain unverified. The new comparison and classifications are recorded in [R1 evidence delta](UXR-01-R1-EVIDENCE-DELTA.md).

The installed Impeccable coordinator and worker outcomes, including capacity and Windows command-length failures, are recorded in [Impeccable evidence](UXR-01-IMPECCABLE-EVIDENCE.md). Coordinator context was invoked once before worktree separation; no reinstall or second initialization. Workers' predecessor observations do not count as independent final v1.2 review. Both final directions and the integrated comparison are coordinator-owned.

Design artifacts remain under `docs/design/uxr-01/`; root changelog bookkeeping is the only shared-document edit. The initial worker drafts/temporary renderer files were created in the original checkout before the dedicated worktree was established. They were inspected and final artifacts migrated; they are not staged or claimed as isolated production work. Pre-existing original worktree changes, including its own `docs/changelogs.md`, `.agents/`, `.codex/`, `.playwright-mcp/`, UXR-00 artifacts and the owner's screenshot, are preserved. The approved package is published on the research branch.

The user expressly restricts design artifact writes to this folder. A task-local [CHANGELOG](CHANGELOG.md) and the repository-required root `docs/changelogs.md` record this finalization. No task card, canonical todo, shared roadmap, source contract, ADR, or application file was edited.

## Nine existing routes and consent entry point

| Existing route | Proposed navigation/context |
|---|---|
| `/` | Learning → Tổng quan |
| `/lookup` | Vocabulary → Tra cứu AI; policy/permission checks retained |
| `/search` | Vocabulary → Kho từ; URL query/filter/sort/cursor state |
| `/word-forms/:id` | From Search/word links; contextual breadcrumb and source-valid Edit |
| `/review` | Learning/vocabulary study → Ôn tập; backend queue semantics |
| `/quiz/new` | Practice → Tạo bài kiểm tra; source date and total count |
| `/quiz/:attemptId` | Existing attempt/start/resume link; multiple questions preserved |
| `/quiz/:attemptId/result` | Submitted attempt/result context; terminal immutable view |
| `/status` | System → Trạng thái |
| `/status#ai-consent` | Persistent consent shortcut and independent local revocation access |

Desktop concepts display six top-level destinations; detail, attempt and result remain contextual routes. They are not new top-level navigation items. Final separation of Quiz into a Practice group and Review placement is an open UXR-02 IA detail. FUTURE Library/Books/Exercises/Progress/IELTS/TOEIC/CEFR exist only in a separate annotated diagram; no new product route was added or promised by a clickable mockup destination.

## Nonnegotiables to carry to later approved design tasks

- Preserve canonical Button/Card/Dialog and Radix/new-york/Tailwind 4. Missing primitives must come from official shadcn/ui, with an individual scope/adoption diff later; no CSS-reset or primitive overwrite.
- Semantic token intent: `background/surface/foreground/muted/border/primary/on-primary`, plus text-labelled warning/error/unknown states. A's paper/indigo and Cambria/Segoe UI, B's cool console/teal and Segoe UI are candidates, not final tokens or fonts. Offline system font fallback and contrast measurements need deliberate UXR-02 work.
- A uses comfortable reading, B a compact console; compact metrics do not justify shrinking consent, validation, answers, source verification, or touch controls. UXR-02A owns final density/layout contracts.
- One first-run Lookup CTA; due Review only when authoritative due>0. Never infer completion from due 0, streak 0 from unknown, accuracy 0 from no attempts, or AI grade from optional advice.
- AI default-deny until policy/consent/dispatch checks pass. Incomplete policy exposes no grant; consent grant is not dispatch. No automatic AI retry, paid fallback, credentials in UI, or invented provider result. Local study availability assumes a healthy local API; new Lookup/quiz generation/feedback still need AI dependencies.
- Preview is not saved. Read date/source first, preserve all forms and verification labels, use conditional source revision/ETag and idempotent intent. Conflict retains drafts and requires explicit source reread; UNKNOWN reconciles the same operation before a new mutation.
- Review rating meanings/SRS remain backend-defined. Session remaining queue is not a fixed global progress denominator. No invented intervals, mastery/learning percentage, or keyboard shortcuts.
- Quiz counts remain total 5–30/max20 per type, with sufficient distinct forms. Keep snapshot, per-answer draft revision, aggregate submission revision, unknown autosave and terminal immutability. Writing null is not zero; explicit 0–4 rubric is preserved. No in-progress answer keys or explanations. D5 is deferred.
- Separate objective MCQ/Cloze, learner self-rating/self-score, and optional advisory AI in every result/dashboard composition. Historical/source-invalid data must not silently vanish.
- Retain route focus, skip link, keyboard controls, persistent critical errors and live-region design. Menu/Site/Sheet focus trap, Escape-to-close/decline and focus return are later implementation requirements, not verified behavior here.

## Owner-selected direction and downstream requirements

- **D1–D4, D6, D8 and D9 are approved:** B — Compact Study Console v1.2, expanded/collapsible desktop sidebar with mobile drawer, teal/cool console direction with light/dark support, compact default density with reading comfort, the separate Dashboard Overview reference, official shadcn/ui source policy, and one dominant contextual CTA hierarchy. The owner explicitly approved these choices in the 13/10/2026 project conversation. The compact/navigation/color explanations elsewhere are DESIGN_TEAM_RATIONALE unless explicitly marked as owner decisions.
- **Official shadcn/ui is mandatory for UXR-02 design and later implementation planning.** Use the official catalog and source strategy. Evaluate existing canonical Button, Card and Dialog for reuse; missing primitives must originate from official shadcn/ui. Map Sidebar, Sheet, Breadcrumb, Tabs, Badge, Alert and other components to real use cases, preserve Radix/new-york/Tailwind v4 compatibility, do not duplicate primitives, and include component provenance in future previews. No `shadcn init/add`, dependency install, production-component edit or claim that the v1.2 mockups already implement official components was made here.
- **UXR-09 Dashboard reference:** the [owner-approved Dashboard Overview](owner-approved-dashboard-overview/README.md) is authoritative for Dashboard composition and supersedes the older UXR-01 Dashboard layout proposal. It fixes the four-row desktop hierarchy: today's task and recent-book carousel; four KPI cards; seven-day due bar chart, activity heatmap and result donut; fourteen-day progress line chart, skills-to-strengthen panel and recent activity. The daily task is dominant, book resume contextual. The carousel shows one complete book at a time, with subtle arrows, pagination, conceptual five-second autoplay, pause on interaction/focus and reduced-motion consideration. The [original image](owner-approved-dashboard-overview/UXR-09-OWNER-APPROVED-DASHBOARD.png) is 1672×941 physical pixels, distinct from future 1440×900 CSS rendering. Current DashboardSummary supplies aggregates only; the book history/progress, forecast, heatmap, time series, recent activity and filtered historical results are SYNTHETIC_DESIGN_FIXTURE or FUTURE_DATA_CONTRACT_REQUIRED. UXR-09 verifies sources and designs the remaining states. No production implementation is authorized.
- R1 adds no image replacement. B03/B04/B13/B17 retain their illustrative aggregate values, and B21/B24 retain the not-requested optional-feedback state. Historical validated feedback and expanded terminal answer detail are future UXR-07 states.

## Historical render checks and current finalization limits

Rendering/contact-sheet/DOM commands below describe the original v1.2 production session. They were not rerun for this documentation-only finalization. Current finalization rechecked image bytes, hashes, dimensions, JSON and recursive Markdown links, and ran the pinned security gate.

| Check | Exact command / method | Outcome |
|---|---|---|
| Task render | `node docs/design/uxr-01/assets/source/render.mjs` with existing module path in `UXR_PLAYWRIGHT_PATH` | 27 exact viewport PNGs per direction; Chrome headless, deviceScaleFactor 1, local file HTML |
| Contact sheets | `node docs/design/uxr-01/assets/source/contact-sheet.mjs` | A/B sheets and equivalent six-scenario board produced |
| Mockup DOM check | `node docs/design/uxr-01/assets/source/confirm.mjs` | 50 light-state renders; zero page-level horizontal overflow, zero script errors, zero visible buttons >90px; report saved |
| Images/links/source copies | Task package validation and PNG headers/hash inventory | See [verification record](research/PACKAGE-VERIFICATION.md); every listed file must exist before final report |
| Scope | `git status --short --branch`, `git diff --name-only` on prohibited paths; no staging | Existing untracked owner inputs/artifacts are preserved; UXR-01 documentation and required changelog bookkeeping are the only edits. Prohibited application paths are unchanged. |
| Source fidelity | `git diff c2417ba6… HEAD -- frontend backend components.json package-lock.json` | Empty at task start; copied source-backed audit assumptions still apply to this checkout |
| Remote baseline/PR | `git ls-remote origin refs/heads/design/ui-ux-research-20261012 refs/pull/26/head`; browser read of PR #26 | Research/PR head advanced to a1ae72d5…; PR inspected as Draft; no merge or metadata update |
| Application tests/build/CI/WCAG | Not run by UXR-01 | Design-only task; no full PASS claimed |

R1 finalization checks: 54/54 original A/B PNG files match the existing manifest SHA-256 and byte sizes; all three R1 screenshot SHA-256 values match the R1 inventory. The B gallery/contact sheet and individual affected frames were visually inspected for the evidence delta and obvious personal/sensitive content. No production path appears in the current diff. The pinned Gitleaks 8.30.1 gate returned exit 0 with zero findings after the approved current prose corrections and exact historical false-positive fingerprints. Report: htmlcov/security/gitleaks.json. No scanner or security policy was changed.

Git handoff completed: source commit **77c0e1813f3d5873ca4ccc3a24218018ddea226f** was integrated by merge commit **1c11b6f3238057c0953c7fe272e9351e666df619**. The research branch retains pre-existing local untracked research/tool inputs, which were not overwritten; the UXR-01 package is available from the target branch. The owner-authorized documentation-only publication and scoped integration completed after the security gate passed. The [finalization verification](UXR-01-FINALIZATION-VERIFICATION.md) records the gate and artifact evidence.

## Outstanding decisions / next task

All owner direction decisions required by AC08 are recorded as approved. Technical and evidence limits remain explicit: incomplete current G7/G9 behavior and persistence evidence, full keyboard/zoom/screen-reader/contrast testing, exact Practice-group placement, source/filter detail patterns, and consent disclosure completeness. These are not hidden or treated as verified. UXR-01 is DONE; those downstream evidence limits remain explicit for later authorized work.

After UXR-01 is DONE, the next allowed action is preparing the UXR-02 prompt. UXR-02 execution still needs a separate instruction. Its inputs include the selected B v1.2 direction, final IA, semantic token roles, responsive/focus contract, official shadcn provenance map and canonical primitive inventory. UXR-02A is a separate compact-layout image approval gate. No downstream design task, production implementation, research integration or main merge was performed during this finalization.

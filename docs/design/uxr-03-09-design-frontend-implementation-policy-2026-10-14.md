# UXR-03–09 — Design + Frontend Implementation Execution Policy

**Decision date:** 2026-10-14  
**Owner directive:** UXR-03 through UXR-09 now combine visual design **and real application frontend implementation**. Previous design-only clauses are superseded **only to the extent explicitly authorized here**.  
**Status:** POLICY APPROVED / TASK EXECUTION NOT STARTED.  
**Frozen baseline:** UXR-01 Direction B, UXR-02 AppShell R2 + HM-FIX, UXR-02A Variant B / R1B with A12 square heatmap.  
**Source baseline commit:** `57159675fc59e984db1d64dcd899aedabf6622ff`.  
**Design PR #26:** preserve OPEN/DRAFT/NOT_MERGED and do not integrate production code into `main` without separate approval.

## 1. Binding scope and precedence

This decision is binding for UXR-03, UXR-04, UXR-05, UXR-06, UXR-07, UXR-08 and UXR-09. It supersedes the earlier task cards' blanket bans on `frontend/**` changes, React/TypeScript/Tailwind editing, writing application tests, browser integration, or real implementation claims **for each task's expressly owned frontend surface only**. It does **not** remove screenshot-count requirements, source-evidence requirements, task-specific business invariants, separate visual owner approval, the frozen design foundation, safety gates, or the owner's explicit approval before publication/merge.

The historical sections of the 2026-10-12 task cards remain provenance, not current execution authority wherever inconsistent with this policy. The task-specific amendment at the top of each card controls, followed by this common policy, then unchanged feature-specific requirements.

Design-only isolated mockups are **insufficient** for the new implementation deliverable. Workers must modify the application frontend and demonstrate screenshots from the actual frontend running with real supported data flows or clearly identified controlled fixtures.

## 2. Permitted and prohibited operations

**Allowed after task execution begins:** owned `frontend/src/features/**` files, narrowly owned related components, styles, existing shared UI components through a single designated integrator when explicitly necessary, focused frontend tests, preview/browser harness assets, and `docs/design/uxr-0X/**` evidence. Existing package dependencies/components are preferred.

**Still prohibited without a separate owner authorization:** editing `backend/**`, migrations/SQLite, API/DTO/OpenAPI/generated contracts, consent/SRS/quiz business rules, infrastructure, `tasks/todo.md`, `main`, shared frozen UXR-01/02/02A design artifacts, `components.json`, lockfiles/dependency installs, and silently creating routes or APIs not present in source. No fake success screens. A frontend requirement that genuinely needs missing backend data must use honest UNKNOWN/UNAVAILABLE/NOT_IMPLEMENTED semantics and record the integration blocker; do not fabricate a persistent capability.

Existing user-facing actions must retain authoritative API/operation semantics including ETag/If-Match, idempotency, reconciliation, local-vs-optional-AI/consent, objective-vs-self-score distinctions, safe navigation and the approved data provenance model.

## 3. Seven-way ownership / integration

- UXR-03 — Lookup, AI Preview, Search, Word Detail presentation and related feature-local components; **read-only** UXR-04 Save flow and UXR-08 Consent logic.
- UXR-04 — SavePreview, EditWordForm, revision conflict UI and owned Save/Edit feature-local components; **read-only** UXR-03 Lookup result presentation.
- UXR-05 — Review flashcard page and feature-local UI; retain SRS/rating and durable reconciliation.
- UXR-06 — Quiz Builder/Runner feature UI; retain snapshot, autosave, submit and answer secrecy.
- UXR-07 — Results/Writing Feedback feature UI; retain authoritative grade, self-score, consent-gated feedback.
- UXR-08 — Status/Consent/Error presentation; preserve fail-closed consent and critical alerts.
- UXR-09 — Dashboard feature UI; preserve locked four-row composition and A12 square heatmap.

Cross-cutting app shell, global routes, tokens, canonical `frontend/src/shared/**` components, styles, generated types and contract files are **shared integration surfaces**. Do not permit independent worktrees to modify the same shared surface without a separately designated coordinator, an explicit ownership lock, and conflict-aware sequencing. A blocking shared change must be written to the task's integration handoff, not hidden in a branch.

Each task uses its existing `design/uxr-0X` branch and worktree; no automatic merge between task branches, no force push, and no unattended merge to `main`. A shared design research branch may publish these amended **task specifications**, but production feature commits remain isolated on their own branches pending owner review and integration.

## 4. Required implementation evidence and acceptance

Retain **all original task-specific full-resolution image counts and state/viewport matrices** as minimums. The owner reviews actual UI appearance. For each task additionally provide:

1. Implemented React/TSX/Tailwind file inventory and exact ownership boundaries.
2. Screenshots captured from the **running frontend** (not exclusively isolated HTML mockups); describe mock/test fixtures and whether backend data are real.
3. Clear difference between `DESIGN_APPROVED`, `IMPLEMENTED_UNVERIFIED`, `FRONTEND_BROWSER_VERIFIED` and `BACKEND_INTEGRATION_NOT_VERIFIED`.
4. Responsive states including 1366 desktop, 390 mobile, 320 reflow, relevant dark mode, and representative keyboard focus; state-specific viewports inherit each task's visual contract.
5. Minimal focused checks for edited frontend behavior and build/type correctness **where permitted by the task run**; do not claim global/full-system audit until that later acceptance wave. Failures must be accurately reported.
6. Accessibility/integration risk ledger, source/API behavior changes **none** unless separately authorized, and reviewer-ready visual packet.
7. Owner approval of both **visual design** and **frontend implementation scope** before marking `DONE` or merging. A worker/coordinator cannot self-approve.

Original design AC remain in force, except a prior `no app code` criterion becomes `no unauthorized production changes outside task-owned frontend`. Add an explicit `IMPLEMENTATION_GATE` requiring actual authored application changes and running-frontend evidence. Historical design-only acceptance items may be marked `SUPERSEDED_BY_OWNER_2026-10-14` where directly inconsistent, never quietly marked PASS.

## 5. Orchestration and skills

For each task: one Astra High coordinator/integrator/auditor and multiple GPT-6.1 Sol workers (Medium or High based on complexity), dispatched early for independent work packages, with single-writer file ownership. Request `speed: fast` and `permission: full-access` only through supported CLI/runtime configuration; no assertion that they applied without runtime evidence.

Every actual frontend worker must invoke installed `$frontend-ui-engineering` in its own context, alongside relevant installed addyosmani skills (`$source-driven-development`, `$api-and-interface-design`, `$browser-testing-with-devtools`, `$code-review-and-quality`, etc.). Impeccable's actual installed design workflow remains mandatory. Use official shadcn/ui components and existing primitives; no reinstall by default.

On exact `Selected model is at capacity. Please try a different model.` dispatch errors: real 3-second delay, up to 30 retries on the failed dispatch, then replace a conclusively non-running worker up to 3 times per work package using the same configured Sol model/reasoning/speed/permission. Do not duplicate active writes or substitute root/model silently. Distinguish capacity from quota/auth errors. If runtime lacks true timed retry, report it; prompt text is not a scheduler.

## 6. Execution and publication gates

This policy changes the **authorized kind of task**; it does not itself start seven local Codex sessions or approve their results. Task prompt issuance/launch remains owner controlled. The source research branch's newly amended task cards must be safely synchronized into the seven existing local worktrees before execution; they were originally created from the older approved base commit. Check local dirty worktrees and remote divergence before any fast-forward; never reset or overwrite existing changes.

During execution, Astra may perform focused browser verification and code implementation. Stop after generating owner-review artifacts at `OWNER_VISUAL_AND_IMPLEMENTATION_APPROVAL_PENDING`, without commit/push unless a separate publication authorization is supplied. Integrate seven production branches only in an explicitly coordinated later wave.

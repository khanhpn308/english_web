# UXR-00 — Autonomous English Web Visual Audit (Astra Orchestrator)

**Track:** UI/UX redesign research, separate from canonical implementation T00x tasks  
**Execution approval:** APPROVED FOR RESEARCH/AUDIT PREPARATION (owner, 2026-10-12)  
**Autonomous execution status:** NOT YET VERIFIED; earlier screenshot-based UXR-00 research is PARTIAL / IN_PROGRESS. Mark `DONE` only after the evidence/coverage acceptance below.  
**Target workspace:** an isolated local `vocabularies-smoke` checkout of English Web; record the actual checkout commit SHA  
**Owner requirement:** Fastest reliable completion. **No token budget, tool-call cap, or monetary/quota optimization.** Resource discipline is intended **only** to reduce wall-clock latency, duplicated work and stalled loops.

> This is a task card for execution by a Codex **GPT-6 Astra coordinator** using native subagents when available. The GitHub task card itself does not spawn agents. No production React/CSS/backend edits, task migration, release work, or automatic PR merge is authorized.

## 1. Mission and authoritative source documents

Complete a **real rendered, evidence-based visual audit** for all nine English Web UI groups, including states currently difficult to reach without a live AI provider. Use existing local-first test infrastructure and synthetic test data; do **not** wait for real AI integration.

Read **only the relevant sections** of:

1. [UI/UX redesign plan](../docs/design/english-web-ui-ux-redesign-plan-2026-10-12.md) — UXR-00, UXR-02A density, nine groups, design acceptance criteria.
2. [Existing screenshot audit](../docs/design/ui-visual-audit-2026-10-12-batch2.md) — VIS-001–011, previously supplied owner images, unresolved states.
3. [shadcn/ui component policy](../docs/design/shadcn-ui-component-strategy-2026-10-12.md) — official component preference, existing Radix/Tailwind foundation.
4. [Future content extensibility](../docs/design/future-learning-content-architecture-2026-10-12.md) — scalable Library/Books/Exercises/Progress navigation without implementing future features.
5. Existing `frontend/tests/support/test_server.py`, `frontend/tests/e2e/harness.spec.ts`, `frontend/tests/e2e/lookup.spec.ts`, `playwright.config.ts` as needed.

The documents are **research references**, not evidence that UI implementation or application acceptance has already passed. Earlier screenshot images exist in the owner's conversation; if unavailable locally, rely on the written evidence and do not claim to have opened image bytes you did not access.

## 2. Done criteria / coverage

Capture and assess these nine groups:

| Group | Required scenarios / minimum evidence |
|---|---|
| G1 AppShell, Sidebar & Navigation | Desktop route hierarchy, active state, back/deep link, narrow viewport; scalability to future Library |
| G2 Lookup & AI Preview | Idle/invalid, actual rendered fixture preview, missing or unverified values, consent/AI unavailable |
| G3 Search & Word Detail | Search list/filter and real or synthetic stored word detail, empty and populated states |
| G4 Save & Edit Vocabulary | Valid save/edit draft, form density, confirmation/errors, revision conflict if supported |
| G5 Review Flashcards | Empty queue and populated front/back/rating; due count semantics |
| G6 Quiz Builder & Runner | Builder plus rendered MCQ, Cloze and Writing question types, progress/resume states where supported |
| G7 Quiz Results & Writing Feedback | Submitted results, scoring distinctions, writing self-assessment and optional synthetic feedback where supported |
| G8 Status, Consent & Error States | Readiness, offline/AI bridge states, privacy consent, alerts, diagnostic disclosure, error/recovery states |
| G9 Learning Dashboard | First-run/zero-data and populated learning data; CTA priority and information density |

Attempt desktop `1440 × 900` and narrow `320 × 568` CSS-pixel viewports for representative flows; document actual viewport. Capture state-specific screenshots; avoid redundant shots of indistinguishable UI.

**Evidence statuses:** `REAL_RENDERED` (real local application and local state), `SYNTHETIC_RENDERED` (real app UI with explicitly mocked/harness-supplied data), and `NOT_VERIFIED` / `BLOCKED`. A static code review **never** counts as a rendered-state screenshot. Synthetic UI coverage **never** means real AI passed.

UXR-00 is `DONE` only when: (a) a traceable 9-group evidence matrix is produced, (b) each reachable priority state has rendered evidence with screenshot path, environment and viewport, (c) unavailable states are explicitly labeled with blocker and next safe action, (d) findings have source anchors, design priority and UX proposal, and (e) the coordinator issues a synthesis with UXR-01 readiness. **An honestly blocked group may remain `NOT_VERIFIED`; never mark 9/9 PASS to satisfy a numeric target.**

## 3. Execution model — one terminal, native Codex subagents

**Coordinator:** GPT-6 Astra, acting as scheduler, independent evidence reconciler and author of final report. The coordinator should **not** repeat full browser/source inspections already delegated.

**Before dispatch:** verify that Codex exposes native collaboration/spawn tools in the running session. If absent, report `MULTI_AGENT_BLOCKED` with the actual capability evidence. Do not emulate subagents with role-play, unattended nested `codex` processes or extra PowerShell windows. Where supported, assign GPT-6.1 Sol Medium/High per complexity; model selection is subordinate to actual runtime capability.

**Parallel execution waves**

| Worker | Ownership | Starts | Deliverable |
|---|---|---|---|
| A0 — Environment | Windows Python/Node prerequisites; one isolated 127.0.0.1:8124 harness; ephemeral SQLite; fixture and bootstrap readiness | Immediately | `A0-environment/STATUS.md`: base URL, verified health, actual process, test DB isolation, known fixture limitations |
| A1 — Source Auditor | G2–G7 targeted React source, state/API contracts, reusable shadcn compositions | Immediately | `A1-source/REPORT.md` with concrete file and relevant symbol/line locations |
| A2 — IA & Design Auditor | G1, G8, G9; UXR-02A information density and extension seams | Immediately | `A2-design/REPORT.md`, focused design recommendations |
| A3 — Browser Auditor | **Sole owner** of Playwright MCP browser; rendered exploration and screenshots G1–G9 | Once A0 posts a verified ready URL/session | `A3-browser/REPORT.md`, screenshot inventory and 9-group rendered coverage |

A1 and A2 should finish their independent analysis without waiting for A0. A3 may begin planning while A0 is starting but must not attempt application mutations or claim rendered evidence before session readiness. Coordinator starts final reconciliation as soon as the relevant reports arrive, not after any unnecessary idle delay. Native concurrency limits and available tools take precedence over assumptions about agent count.

**Browser/session safety:** Playwright MCP is configured with Chrome and `--isolated`. One browser-owning worker avoids uncontrolled shared-profile interactions; isolated browser state **does not alone guarantee** backend/SQLite data separation. For parallel synthetic sessions, verify independent harness cookies and temporary database paths; if not demonstrable, serialize only the conflicting state mutations, without serializing unrelated source analysis.

## 4. Safe harness and synthetic state protocol

- Use `frontend/tests/support/test_server.py --port 8124` with host `127.0.0.1`, matching `playwright.config.ts`. Use the appropriate Windows Python executable and verify dependencies before starting; do not assume WSL `./.venv/bin/python` works on Windows.
- `test_server.py` uses `TemporaryDirectory(prefix="vocabulary-e2e-")` and a temporary SQLite `test.db`; verify effective `/_harness/db_path` remains outside production storage. Check process state and port ownership first so no second server competes for 8124.
- Build `frontend/dist` using the existing build task **only if required** for page rendering. Generated build output is allowed for this research; no source-code changes or dependency/lockfile upgrades.
- Perform legitimate harness bootstrap: `POST /_harness/token` with the exact loopback Origin, then open `/bootstrap#token=<one-time-value>`; let the app exchange it. Never write, print or upload bootstrap tokens/cookies into screenshots/reports. Use `/_harness/lookup-session` for scoped fake Lookup where appropriate; follow its strict Origin, cookie and fixture schema.
- Prefer **existing** deterministic fixtures and sanctioned test APIs for saved words, review events, quiz attempts and AI responses. The fake Lookup Bridge supports specific cases; **do not assume Writing Feedback, Book Exercises or all other AI flows are implemented in it**.
- If existing fixtures cannot reach a state, mark it `BLOCKED`, explain the precise gap and propose a **future separate fixture/task**. Do not edit production code, backend schema, authentication, consent or bundled test harness just to manufacture screenshots.
- The app has no meaningful academic data according to its owner, but still protect existing user files, audit history and app settings. Only mutate **temporary** harness data; never real local learning databases.
- Deny external AI/provider/network requests during test flows unless explicitly needed for fetching public official documentation; all app AI payloads must remain synthetic and local. Do not bypass AI consent or silently convert failed AI into "success".
- Do not run a full regression or security suite; only lightweight readiness checks and interaction exploration needed to produce visual evidence.

## 5. Speed-first tool and context discipline — NOT a budget

There is **no fixed token ceiling, request quota, tool-call limit, or time-cost cap**. Spend tools and tokens as needed to complete the audit fastest and accurately.

The following are **latency/quality controls**, not spending restrictions:

- Inspect file symbols/paths first; read the smallest sufficient ranges rather than repeatedly dumping entire files.
- Prefer existing fixture helpers; cache only stable findings in checkpoint documents, not massive copy-pasted source code.
- Avoid full DOM trees, long terminal logs or all screenshots embedded in agent-to-coordinator messages; refer to on-disk artifacts.
- Do not retry the identical failed action with unchanged parameters or assumptions. Diagnose cause, change the plan once and continue or record `BLOCKED`.
- Never postpone important work solely to stay below a usage number. If deeper investigation is required to answer an important unknown, do it.
- Continuously exploit **real dependency-free parallelism**. Keep browser ownership single until session isolation proves multi-browser operation safe. No recursive subagents or duplicate source auditors.
- Give the owner brief, **meaningful** progress updates (phase readiness/coverage/blocker), not time-filling status narration. Record a checkpoint after each completed phase or material blocker.
- Log observable usage/tool metrics **only if helpful** for diagnosing repeated work or bottlenecks. Do not optimize for payment, cache-hit totals or cost.

**What counts as waste:** repeated reads of unchanged files that produce no new evidence, duplicated source analysis across workers, replaying an already-complete browser path, unbounded retries without new hypotheses, or copying huge logs into the coordinator context. A *high* token count alone does **not** prove waste.

## 6. Deliverables, artifact ownership and checkpointing

Use local directory `artifacts/uxr00/` (do not commit automatically):

```text
artifacts/uxr00/
  A0-environment/STATUS.md
  A1-source/REPORT.md
  A2-design/REPORT.md
  A3-browser/REPORT.md
  A3-browser/screenshots/*.png
  final/UXR-00-REPORT.md
  final/SCREENSHOT-INVENTORY.md
  final/COVERAGE-MATRIX.md
  final/CHECKPOINT.md
```

Worker file ownership is exclusive to its directory. The coordinator alone writes `final/` to avoid races. Store enough information for another session to resume from checkpoint without rereading the entire codebase. If the directory is not excluded by existing Git ignore rules, keep it untracked and explicitly report that fact; do not change project ignore rules as part of the audit.

**Every finding:** `ID | group | screenshot path or NONE | state type | viewport | observed behavior | source path+symbol | P0/P1/P2 redesign priority | proposed shadcn component / layout improvement | risk / pending verification`.

**Priority meanings:** P0 = blocking coherent design foundation or unsafe/confusing user-critical state; P1 = significant UX/density/flow inefficiency; P2 = polish or localized usability improvement. Distinguish visual-design P0 from production incident severity.

Final report must include `UXR_00_STATUS`, `AGENT_EXECUTION_EVIDENCE`, `VISUAL_GROUP_COVERAGE`, `SCREENSHOT_COUNT`, `SYNTHETIC_STATES`, `FINDINGS_BY_PRIORITY`, `BLOCKERS`, `GITHUB_BASELINE_SHA`, `UXR_01_READINESS`, with `UNKNOWN` when unavailable. Separate visually observed facts from source-based deductions and mocked-only behavior.

## 7. Hard exclusions and handoff

- No edits to production React, CSS, TypeScript, API, FastAPI, SQLite schema or existing records.
- No real AI provider calls, stored credentials, consent circumvention, source import or licensed publisher content creation.
- No Git commit, PR push/merge, task checklist status change, Windows installer, full acceptance/a11y/security PASS claim.
- No use of an unrestricted system profile or changing operating-system permissions merely to speed up exploration.
- Do not block UXR-01 ideation if some currently unreachable states are honestly labeled and the evidence needed to proceed is sufficient; do not mark UXR-00 globally DONE until its report and blockers meet this contract.

**Next track:** UXR-01 visual-direction selection, then UXR-02 AppShell foundation and UXR-02A layout simplification; only later UXR-03–09 and coding following owner design sign-off.

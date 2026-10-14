# UXR-11 — Owner Sign-off & Implementation Handoff

**Track:** English Web final UI/UX redesign research and design sign-off; **not** application T001–T090 and not AI-orchestration task management.
**Task ID:** `UXR-11`. **Formal title:** Owner Sign-off & Implementation Handoff.
**Status:** `PREPARED / NOT STARTED / BLOCKED_BY_UXR_10_QA_GATE`.
**Owner authorization — 2026-10-12:** prepare this Markdown task file on `design/ui-ux-research-20261012`, link it in the UI/UX roadmap and update Draft PR #26 **only**. This approval does **not** authorize UXR-11 execution, an actual final sign-off, UI implementation, screenshot generation, Impeccable runs, release testing, merging or adding UXR-12 to the approved roadmap.
**Repository:** `khanhpn308/english_web`; [Draft PR #26](https://github.com/khanhpn308/english_web/pull/26) remains OPEN/DRAFT/unmerged.
**Dependency:** verified UXR-00 → owner-selected UXR-01 → signed UXR-02 → signed UXR-02A → owner-approved **all** UXR-03–09 → completed UXR-10 with `READY_FOR_UXR11` and no material unresolved P0/P1 design defect → separately approved UXR-11 execution → explicit owner final integrated visual sign-off.
**Downstream:** possible UXR-12 — **PROPOSED Redesign Implementation Planning only**, subject to separate owner assessment and approval; no automatic implementation.
**Binding policy:** [Owner-viewable images, installed Impeccable, official shadcn](../docs/design/uxr-visual-approval-impeccable-protocol-2026-10-12.md).

## 1. Outcome, scope and distinction between approvals

Provide a **single final decision packet** enabling the owner to examine what the entire English Web application would look like in its proposed redesign, **side by side and screen by screen**, then explicitly `APPROVE`, `REQUEST_CHANGES`, or `REJECT` a named, immutable nine-group design version. After an actual `APPROVE`, prepare a **design implementation handoff**: canonical visual references, source behavior boundaries, component ownership, dependency waves, implementation/test gates and unresolved risks. No coding or component installation is allowed by this task's preparation or design sign-off.

Three authorizations are distinct:
- **Feature approval:** UXR-01/02/02A and UXR-03–09 contain previous explicit owner image/version decisions. They are required but **do not replace final UXR-11 integrated approval**.
- **Final UI DESIGN sign-off:** the owner must view the combined nine-group desktop/mobile gallery, review material issues/risks and explicitly approve the exact aggregate version with attributable decision evidence. Agent score, green QA or silence is **not approval**.
- **Implementation authorization:** separate later owner permission to plan/execute scoped coding, worktrees, installs, tests, deployments or merge. Even `UXR-11 DONE` **does not authorize implementation** or automatically approve proposed UXR-12.

Deliver documents only. Maintain a hard boundary between `DESIGN_SIGNED_OFF` and `IMPLEMENTATION_AUTHORIZED`.

## 2. Actual upstream evidence and start gate

Before launching UXR-11 **execution**, require verified accessible evidence:
1. **UXR-00** final audit source SHA, genuine current-app screenshot inventory, nine-group capture/NOT_VERIFIED flags and handoff. Owner reported UXR-00 complete locally, but do not claim the GitHub branch contains or verifies local untracked artifacts until inspected.
2. **UXR-01** owner-selected A/B/hybrid concept, exact image/version, D1/D2/D3/D4/D6/D8/D9 decision ledger; open D5 belongs to UXR-06 and D7 remains future-only.
3. **UXR-02 and UXR-02A** owner-approved AppShell/foundation/density variants, semantic tokens, current route map, correct responsive behavior plans, and genuine Impeccable logs.
4. **UXR-03 through UXR-09** each have: full-resolution owner-viewable gallery; valid screenshot provenance; screen/state matrix; separate owner approval with version/asset IDs; locally installed Impeccable coordinator+worker invocation logs; official shadcn component plan; handoff/risks. Prepared Markdown task cards **do not** count as completed feature designs.
5. **UXR-10** genuinely executed design QA: frozen approved source-image versions, nine-group × state × six CSS viewports × two themes matrix, 14 journey reports, **18 desktop/mobile group comparison boards + ≥6 continuity boards**, issue register and `READY_FOR_UXR11` recommendation; no unresolved **P0/P1** consistency/safety issues or unapproved material changes.
6. **Separate owner approval** to execute UXR-11; today's permission covers **task preparation only**. If any blocker exists, report precise missing path/approval/version and remain `BLOCKED_BY_DEPENDENCY`, rather than assembling fiction or auto-marking DONE.
7. Freeze a **manifest** of every accepted upstream image with `file URL/path | Git blob SHA or content hash | resolution/viewport | theme | group | feature owner approval ref | QA issue status`. The signed design may only reference those exact bytes/versions.

Once UXR-10 is `READY_FOR_UXR11`, there is no need to rerun UXR-00 nor design/QA all nine screens again. Any targeted new mockup is a versioned feature-owner correction and requires applicable owner reapproval, **not** a silent change by UXR-11.

## 3. Final nine-group gallery — visual sign-off interface

The owner must be able to view **genuine full-resolution, linked PNG/WebP images**, not just tables or thumbnail contact sheets. Reuse UXR-10's **18** G1–G9 desktop/mobile boards and **≥6** cross-journey continuity boards, with direct links back to individual immutable approved originals. UXR-11 builds a consolidated decision presentation, not 24 newly invented source captures.

| Group | Final must show in visible imagery, with approved component/state versions |
|---|---|
| **G1 AppShell** | Desktop Sidebar expanded/collapsed; mobile navigation Sheet open/closed; active route/focus/consent entry; theme and information density |
| **G2 Lookup** | Initial term, AI preview vs saved distinction, consent request and unknown-result safe recovery |
| **G3 Search / Word Detail** | Search URL/filter/cursor and detail, VALID vs invalid source, safe Edit entry |
| **G4 Save & Edit** | SavePreview receipt vs unsaved preview, bilingual editor, revision conflict/draft preservation, UNKNOWN |
| **G5 Review** | NEW/LEARNED front, revealed back, four AGAIN/HARD/GOOD/EASY ratings and confirmed/pending/UNKNOWN queue outcomes |
| **G6 Quiz Builder / Runner** | MCQ/Cloze/Writing, null vs explicit Writing selfScore 0, per-answer autosave, submission gate, chosen owner-approved Runner A/B navigation |
| **G7 Results / Writing Feedback** | SUBMITTED vs IN_PROGRESS, MCQ/Cloze nullable accuracy and BLANK, Writing learner self-score, SRS handoff, optional consent-gated AI feedback states |
| **G8 Status / Consent / Recovery** | Real ACTIVE vs UNKNOWN and severity, local API vs AI bridge, full policy, grant/revoke, safe operation/rebootstrap recovery |
| **G9 Dashboard** | Populated/first-run/mixed learning, due/streak, distinct objective/self metrics, real zero vs null, stable next-action CTA |

**Required decision presentation:** one nine-group index/contact sheet showing each desktop/mobile pair; a per-group brief with at least one desktop and one mobile full-resolution link, plus links to critical error/empty/consent/writing states; six linked continuity boards; light/dark and responsive variation index; issue/exception badges as **plain text** rather than fabricated “PASS”. If state images are missing, label `MISSING_IMAGE` and block sign-off. Synthetically populated images are `DESIGN_MOCKUP/SYNTHETIC`, QA boards `QA_COMPOSITE`, genuine old UI `CURRENT_APP_CAPTURE` only with provenance.

The owner must be able to answer, using images alone, “What will the Dashboard, Lookup, Search/Detail, Save/Edit, Review, Quiz, Result/Feedback, Status/Consent, sidebar and mobile layout look like?” Show alternative concept selections **already decided upstream**, not unapproved hybrid composites.

## 4. Final decision protocol and change control

Use a **decision ledger**:
`decision ID | G1..G9 / integrated | image URLs and exact hash/viewport/version | specific proposed choice | owner response | timestamp/reference | conditions | final status`.

- Prepare **D1–D9** summary preserving explicit UXR-01/02/02A/06 outcomes; **D5** is the selected Quiz Runner navigation; **D7** future Library/Books scope stays `FUTURE_UNAPPROVED` and **must not block** final v1 visual review unless the owner explicitly elevates it.
- Present a final integrated **G1–G9 approval table** with rows requiring *owner-reviewed* images; solicit exact `APPROVE / REQUEST_CHANGES / REJECT`. Only the owner's explicit instruction grants final design sign-off. Do not interpret “task prepared”, approved roadmap, PR open, up-to-date GitHub SHA or QA pass as sign-off.
- `REQUEST_CHANGES`: create change ID; source image IDs, affected themes/viewports/groups, severity, requested correction and owner; send to corresponding UXR-02/02A or UXR-03–09 design owner, regenerate only affected mockup, rerun relevant UXR-10 checks, **reapprove changed images**. Keep prior approved manifest archived; never silently overwrite signed originals.
- If no written owner choice, record `OWNER_FINAL_APPROVAL_PENDING`. No green completion, no implementation handoff published as **approved**.
- `REJECT`: mark rejected version and a proposed rework path, not DONE.
- On actual `APPROVE`, freeze the precise nine-group aggregate manifest, approved design tokens/component catalog/navigation and open *nonblocking* follow-up risks; publish decision ref, date and linked image index. Approval is **design-only**, not a release or product-code test.
- Any later change in shared tokens, navigation, source-visible semantics or major interaction states invalidates affected approval until owner reviews a new named version.

## 5. Design-to-implementation traceability and deliverable granularity

**Handoff is a planning specification, not a coding command.** Produce a matrix:
`design requirement / issue ID → upstream owner-approved image/version → existing source modules → proposed presentation component → contract invariant → eventual coding task candidate → independent acceptance scenario → implementation owner → dependency → release gate`.

**Scoping rules:**
- Current v1 only. Maintain nine current same-origin routes `/`, `/lookup`, `/search`, `/word-forms/:id`, `/review`, `/quiz/new`, `/quiz/:attemptId`, `/quiz/:attemptId/result`, `/status` and consent deep link `/status#ai-consent`. Distinguish a group from a single route.
- Keep persisted Markdown/SQLite division, source revision/ETag/idempotency, review SRS, quiz answer `draftRevision` and `submissionRevision`, Writing selfScore vs optional AI comments, consent policy and local/offline behavior untouched by design.
- **Tier 1:** existing/official shadcn Radix/new-york primitives and tokens under `frontend/src/components/ui/` / shared CSS; only one future component owner. **Tier 2:** future shared AppShell/compositions `Sidebar/Nav/PageHeader/FilterToolbar/StateAlert/EmptyState`; **Tier 3:** feature-specific presentational compositions owned by G2–G9. This is a proposed folder/responsibility map, not file creation.
- Phase-order candidates: shared design tokens/Sidebar + accessibility foundations → shared density/CTA/status patterns → independent feature presentations G2/G3, G4, G5, G6, G7, G8, G9 with actual source dependencies → cross-screen integration → accessible keyboard/zoom/error-state verification → Windows/offline packaging and final release evaluation. **Do not claim all these waves are already authorized or runnable in parallel**; later UXR-12 (if approved) owns precise issue/task decomposition, runnable dependency DAG and scheduling.
- Every proposed new shadcn primitive includes its exact official documentation URL, `EXISTING/PROPOSED/COMPOSITION/DEFERRED`, Radix compatibility, version pin/diff review requirement and owner. No unreviewed community registry or global CLI overwrite.
- For every coding candidate, document **non-modifiable behavior** and a **test/verification plan for later**, not a test claimed to have been run.
- Existing T001–T090 tasks and AI coordinator tasks remain distinct; do not allocate or mark DONE any canonical T ID from UXR design handoff. `tasks/todo.md` remains untouched.

## 6. Acceptance and verification gates for a future implementation phase

Provide a **proposed** later verification strategy, divided into explicit stages and clearly labelled `NOT_RUN`:
- Visual parity: screen/state snapshots compared to signed image IDs, source route/state mapping, light/dark, mobile/tablet/desktop and design-deviation register.
- Functional integrity: Lookup preview-vs-save, Markdown invalid/ETag conflicts, safe SRS rating and UNKNOWN replay, quiz autosave/submit/results idempotency, optional AI feedback, consent grant/revoke and local-only behavior. Use backend receipts; a picture cannot prove correctness.
- Accessibility: WCAG 2.2 AA **target**, real keyboard/focus, Dialog trapped/returned focus, 320px/200%-zoom reflow, contrast measurements on rendered UI, semantic status/aria live regions, language tags and reduced motion. UXR-10 image-only review is NOT WCAG PASS.
- Platform readiness: offline first local server launch, provider/bridge disconnected vs local API up, storage BUSY/READ_ONLY, degraded Status, restoration/rebootstrap and Windows packaging. Scope actual release/installer build separately after code phase.
- CI, safety and test authority: existing test suites, API contracts, TypeScript/build/Playwright as appropriate; do **not** run tests or claim success from this design-only preparation or sign-off.
- Cross-screen regression: owner-approved versions and all material G1–G9 scenario states; no unapproved library/books functionality.

A future software implementation acceptance or shipping decision **cannot be inferred** from visual owner approval; it requires separately authorized code and runtime verification with fresh evidence.

## 7. Issue triage, waivers, unresolved decisions and risk posture

Required incoming UXR-10 issue register: `issue ID | group | impact severity | source screenshots | missing visual/runtime evidence | accountable owner | recommended fix | approval/re-review requirement | status`. Carry forward **all** unresolved design and downstream runtime risks.

Rules:
- **P0/P1 material visual/contract inconsistency unresolved:** **BLOCK** final integrated sign-off. Do not reclassify solely to pass the gate.
- **Missing owner-signed upstream variant, missing original image or broken link:** **BLOCK**; obtain and verify assets before owner approval.
- **Missing Impeccable coordinator/worker actual usage evidence:** `IMPECCABLE_NOT_ACCESSIBLE` and block relevant acceptance, never pretend it ran locally.
- **P2/P3 cosmetic or explicitly nonblocking runtime-untested risks:** propose deferral with rationale, owner visibility and future code/review owner. A waiver **requires explicit owner decision**, cannot compromise consent, preserved drafts, SRS/quiz idempotency, privacy, accessibility critical navigation or essential error states.
- **Cross-screen conflict:** route token/sidebar to UXR-02, density to UXR-02A, G2/G3 to UXR-03, G4 to UXR-04, G5 to UXR-05, G6 to UXR-06, G7 to UXR-07, G8 to UXR-08, G9 to UXR-09; material new imagery returns to UXR-10 for targeted recheck and the owner for explicit reapproval.
- **Future learning content:** Library/Books/Chapters/Lessons/Exercises/Vocabulary linkage/Progress and IELTS/TOEIC/CEFR, Reading/Listening/Writing/Speaking remain architecture-only, disabled/hidden until separately approved. Do not include them in promised working v1 UI.
- Document data privacy: no personal screenshots, secrets/tokens, cookie contents, real stored learner text or AI prompts inadvertently embedded in public final gallery.

## 8. Installed Impeccable — evidence required of coordinator and every design worker

The owner has **already installed** [pbakaus/impeccable](https://github.com/pbakaus/impeccable) on Windows. **Do not reinstall, update, vendor or copy it**. On **later separately authorized local UXR-11 execution**:
1. Coordinator and **every actual independently assigned visual sign-off/consistency/handoff reviewer** discover the installed skill in **their own harness**, read the installed `SKILL.md` plus relevant reference guidance and call the installed `<skill-root>/scripts/impeccable context` **once per session** from project root (actual Windows `impeccable.cmd context` launcher where supplied). Log real command/location/version/time/outcome.
2. Apply `critique` to integrated image boards, `layout/distill` to density/CTA conflicts, `adapt` to mobile and 200%-zoom risks, `clarify/harden` to terminology and consent/UNKNOWN, and `shape` only if a journey issue needs it — follow the locally installed version, do not blindly call all verbs.
3. In `UXR-11-IMPECCABLE-EVIDENCE.md` log per individual: `agent/session/role | installed SKILL path/version | context command/result | reference/command | exact inspected gallery version | discovered issue | concrete design/QA change or documented no-change rationale | image/issue ID`. Coordinator independently logs its own invocation; forwarding another agent's result is insufficient.
4. If inaccessible, record `IMPECCABLE_NOT_ACCESSIBLE`, actual discovery/execution failure and what user action is needed; block false skill completion. **GitHub-only authorship of this task does not invoke Windows skill**.
5. Impeccable does not override approved user design decisions, source business rules, local-first consent, shadcn official-only policy or privacy/a11y obligations.

No installation or local skill work takes place in this task preparation.

## 9. Official shadcn/ui and canonical component handoff

**Only source for missing primitives:** https://ui.shadcn.com/docs/components. Consult [official component strategy](../docs/design/shadcn-ui-component-strategy-2026-10-12.md).

Mandatory handoff table:
`approved screen and ID | canonical primitive/composition | official component docs URL | installed vs proposed | Radix/new-york/Tailwind-4 compatibility | CSS/reset constraints | one future shared component code owner | required keyboard/ARIA verification | implementation authorization status`.

- Reuse `Button/Card/Dialog` locally owned primitives (installed baseline); Sidebar/Sheet/Breadcrumb/Badge/Alert/Field/Input/Accordion/Collapsible/Progress etc. are **official candidates**, not asserted as currently installed.
- Preserve the root `components.json` setup and existing **non-Preflight Tailwind** baseline; no duplicate generic primitives per feature, Base UI/Radix foundation swap or pasted third-party “full dashboard template”.
- Any future component source acquisition must have a **separately authorized** implementation scope, pinned official CLI/source and diff, reviewed dependency/security/license implications, and one owner of shared primitives.
- Avoid introducing shadcn Chart or Progress where no genuine timeline/denominator exists; avoid replacing native date without locale/keyboard/ISO-state rationale.
- Mapping is **documentation only**; do not invoke shadcn `init/add`, edit `components.json` or package-lock, install or regenerate code here.

## 10. Later execution deliverables — not created by this task preparation

**Exclusive root:** `docs/design/uxr-11/` when UXR-11 is separately authorized for design sign-off execution.

| Future artifact | Required content |
|---|---|
| `UXR-11-READINESS-AND-SOURCE-VERSIONS.md` | audited dependency approvals, UXR-10 READY proof, baseline SHA, all frozen gallery hashes/links |
| `UXR-11-FINAL-VISUAL-GALLERY.md` + `assets/qa-signoff-*.(png|webp)` | owner-openable nine-group index, **18 reused G1–G9 desktop/mobile boards and ≥6 continuity boards**, individual originals, themes/responsive/error links; QA compositions labeled |
| `UXR-11-FINAL-DECISION-MATRIX.md` | G1–G9 owner view/response, D1–D9 resolved or future-only, version/hash and comments |
| `UXR-11-OWNER-SIGNOFF.md` | explicit owner integrated design decision, timestamp/reference, accepted exceptions, **DESIGN_ONLY** flag |
| `UXR-11-ISSUES-EXCEPTIONS.md` | P0/P1 closures, P2/P3 documented waiver/deferral, affected screenshot versions and reapproval chain |
| `UXR-11-SHADCN-COMPONENT-OWNERSHIP.md` | official URLs, canonical Radix/tiers/shared implementation owner, no source acquisition |
| `UXR-11-IMPLEMENTATION-TRACEABILITY.md` | feature/asset → current code surface → proposed component → invariant → future coding candidate → verification gate |
| `UXR-11-IMPLEMENTATION-HANDOFF.md` | phased candidate work packages and bounded file ownership, dependency risks, unchanged business contracts, proposed validation/release gates; **not a coding authorization** |
| `UXR-11-IMPECCABLE-EVIDENCE.md` | local coordinator+each actual worker installed context proof with issues and gallery effects |
| `UXR-11-UXR12-ASSESSMENT.md` | explicit **PROPOSED ONLY** assessment: whether dedicated implementation planning is needed; prerequisites, value, alternatives, no automatic roadmap promotion |

**Artifact ownership:** the UXR-11 sign-off coordinator alone authors consolidated `READINESS`, `FINAL-DECISION`, `OWNER-SIGNOFF`, `ISSUES` and `HANDOFF`; a gallery assembler writes only `assets/qa-signoff-*` and image inventory drafts; component/traceability reviewer writes separate scoped draft; QA reviewer reads UXR-10 outputs and contributes specific issues. Every actual local participant uses installed Impeccable independently. Roadmap and PR metadata remain **single-writer** research coordinator resources. All upstream UXR-00–10 assets and decisions are **read-only**; no worker writes frontend/backend or canonical T tasks.

**This preparation creates only `tasks/uxr-11-owner-signoff-implementation-handoff.md` and metadata changes to roadmap/PR**, not the future outputs in the table.

## 11. Acceptance criteria / Definition of Done — 24 hard checks

UXR-11 is DONE **only** when all applicable criteria have actual evidence, including **the owner's final approval**. Absence of approval means `OWNER_FINAL_APPROVAL_PENDING` regardless of how complete the agent's handoff is.

1. **AC01:** UXR-00 final audit SHA/provenance and genuine screenshot coverage verified; missing current captures explicitly `NOT_VERIFIED`.
2. **AC02:** UXR-01 selected direction and UXR-02 / UXR-02A signed shell/density version and owner approval refs linked.
3. **AC03:** **Every UXR-03–09** feature has verified owner-approved original full-resolution images, accepted version, complete source/state map and skill/official-component evidence.
4. **AC04:** UXR-10 executed, issue register complete, genuinely `READY_FOR_UXR11`, its **18 G1–G9 + ≥6 journey boards** linked, all material P0/P1 closed/reapproved.
5. **AC05:** Separate permission to execute UXR-11 confirmed; today's permission to prepare this file is not reinterpreted as execution or sign-off.
6. **AC06:** Immutable final gallery manifest tracks each original image path/hash/version/viewport/theme/owner reference and exact nine-group scope.
7. **AC07:** Direct full-resolution owner-visible desktop/mobile screens cover **all G1–G9 and key sub-surfaces**, with no missing Group/result/consent/recovery proof hidden in a contact sheet.
8. **AC08:** Consolidated visual gallery uses **18** grouped desktop/mobile comparisons and **≥6** continuity boards; links to approved original images are valid and original-vs-QA-composite provenance precise.
9. **AC09:** Six relevant responsive CSS viewports, light/dark and narrow 320px/200%-zoom **design evidence/gaps** documented accurately; a mockup does not claim tested browser zoom.
10. **AC10:** All **14 UXR-10 cross-feature journeys** have preserved route/URL/focus/identity/intent semantics and image issue links.
11. **AC11:** AppShell navigation, fonts, tokens, CTA hierarchy, compact Card/empty/error handling consistent with frozen UXR-01/02/02A design, not silently changed.
12. **AC12:** Readability and a11y designs include keyboard/focus/dialog, long bilingual text, live regions, contrast/reduced-motion plans without false WCAG runtime PASS claims.
13. **AC13:** Review/SRS receipt, Lookup preview≠saved, source revision/ETag, Quiz draft/submit/idempotency and UNKNOWN reconciliation boundaries documented unchanged.
14. **AC14:** Objective BLANK/INCORRECT/null accuracy, Writing learner selfScore vs optional AI review, consent fail-closed, local-vs-external bridge distinctions correct in selected images.
15. **AC15:** Active incident vs potential severity, no-data UNKNOWN, due vs mastery, progress numerator/denominator and postsubmit feedback truth preserved.
16. **AC16:** Source/visual evidence provenance correct; real personal data, API keys and cookies absent from publicly viewable images.
17. **AC17:** P0/P1 design issues closed with exact approved remediated image versions; P2/P3 deferrals explicitly known to owner with a responsible future owner.
18. **AC18:** D1–D9 design decisions summarized without fabricated user choices; deferred future D7 does not become live Book/Library/IELTS feature or block valid current v1 sign-off.
19. **AC19:** Official shadcn/ui component matrix with exact URLs, existing/proposed classifications, Radix compatibility and single shared future component ownership; no source installs.
20. **AC20:** Coordinator and **each actual UXR-11 local reviewer/worker** log genuine already-installed Impeccable SKILL/context invocation and concrete effect; inaccessible skill disclosed and blocks compliance.
21. **AC21:** Owner **actually inspects final linked nine-group images** and gives explicit `APPROVE` for the named aggregate version, or task remains pending/rework.
22. **AC22:** `UXR-11-OWNER-SIGNOFF.md` records the authentic owner decision/date/reference, exact hash manifest and any exceptions; no impersonated or inferred approval.
23. **AC23:** Traceable **design-only** implementation handoff maps approved screens to proposed coding packages/owners/dependencies/test gates, keeps existing T tasks independent, states `IMPLEMENTATION_NOT_AUTHORIZED`, and assesses UXR-12 as **PROPOSED pending owner decision**.
24. **AC24:** No `frontend/**`, `backend/**`, API, SQLite, generated DTOs, shared CSS/components, `components.json`, dependencies/locks, `tasks/todo.md`, live app, tests/CI/packaging, UXR-00 retroactive modification, PR #26 merge or unauthorized coding/UXR-12 launch.

**Status progression:** `PREPARED → READY_FOR_EXECUTION (all gates and explicit UXR-11 execution permission) → IN_PROGRESS → OWNER_FINAL_APPROVAL_PENDING → DESIGN_SIGNED_OFF / DONE`. Any `REQUEST_CHANGES` leads back to affected design owner and targeted UXR-10 recheck; `REJECT` or missing sources is BLOCKED. No UXR-11 DONE without explicit final owner image approval.

## 12. Prohibited changes, coordination and stop for UXR-12 decision

Only `tasks/uxr-11-owner-signoff-implementation-handoff.md`, the research roadmap and Draft PR #26 metadata may be written **during this preparation**. Do not edit `tasks/todo.md`, application code, API, database, test fixtures, source snapshots, product routes, dependency/CSS/component configuration or any UXR-00–10 already authored design assets. Do not create real images, launch Playwright, install Impeccable/shadcn, run tests or label their results PASS. No merge of PR #26.

If the owner approves the **final image packet later**, that approves a **frozen design** only. Subsequent implementation planning or code execution needs an **additional explicit decision**; UXR-12 remains a **candidate planning task**, not part of the approved UXR-00–11 sequence. The final UXR-11 artifact can recommend a UXR-12 scope, compare planning within regular app T tasks versus a dedicated work package and present dependency waves, but **cannot adopt, execute or approve UXR-12**.

**STOP after this task specification, roadmap link, Draft PR #26 update and verification. Ask owner separately before preparing UXR-12.**

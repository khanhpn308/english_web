# English Web — Mandatory Visual Approval, Impeccable & Official shadcn/ui Protocol

**Date:** 2026-10-12  
**Status:** OWNER-REQUIRED WORKFLOW CONTRACT / DOCUMENTATION ONLY  
**Scope:** UXR-01, UXR-02, UXR-02A, UXR-03–UXR-11, and any later approved implementation-planning phase.  
**Authority:** Owner's requirement for a final, substantial UI/UX redesign that is **shown visually and approved before it becomes a finalized design**.  
**Explicit exclusion:** Does NOT authorize UI coding, application source changes, real provider calls, full acceptance testing, UXR-00 closure or PR #26 merge.

## 1. Non-negotiable: owner must SEE the UI

A written proposal, ASCII wireframe, component list or Mermaid diagram is **never sufficient** for a UI decision. Agents must provide **actual viewable UI images** (PNG preferred; WebP acceptable) of their proposed interfaces, not just descriptions of them. HTML/SVG/interactive prototypes are useful **in addition**, but **not as substitutes** for screenshots. Produce screenshots from a visually composed mockup/prototype rendered in a browser or a clearly marked image composition. Distinguish:

- `CURRENT_APP_CAPTURE`: screenshot of existing app (audit baseline; state/viewport/provenance).
- `DESIGN_MOCKUP`: proposed UI composition; not the implemented app.
- `INTERACTIVE_PROTOTYPE`: separately hosted/read-only preview with demonstrated interaction, not production code.
- `NOT_RENDERED`: unable to produce viewable evidence; blocks the affected owner-approval gate.

Each screenshot must have `task ID | group/screen | variant | state | exact CSS viewport | theme | evidence type | version | date | path/link`. Synthetic personal/study data must be labeled **SYNTHETIC**; do not imply a live backend, functional consent, accuracy result or successful API interaction from a visual mockup. Do not commit owner desktop captures or secrets.

**Image review formats:**
1. An inline preview/contact sheet showing complete screens **at readable resolution**, with a link to each individual full-resolution screenshot. Do not hand off a single tiny collage as the only evidence.
2. Desktop reference: `1440×900` and representative `1366×768` CSS pixels. Tablet: `768×1024`; mobile: `390×844` and stress layout at `320×568`. Screens requiring 1024px intermediate state also show `1024×768`. Record deviations.
3. Light and dark appearances for a representative complete screen and the semantic error/warning/consent palette (or document why a particular variant does not support a theme).
4. **Before vs proposed** capture for states with current visual evidence; **proposed + SOURCE-ONLY / NOT_VERIFIED** marker otherwise. Do not fake a missing baseline.
5. Screens must show meaningful product content, not empty aesthetic shells: realistic Vietnamese text, long word/example, partial learning history, actual-looking form fields and truthful semantic empty/unknown/error labels.

Every owner decision records `version | visual previews | alternatives | scope | feedback | decision (APPROVE / REQUEST_CHANGES / REJECT / PENDING) | date/reference`. **Only an explicit owner response is APPROVE.** Silence, agent recommendation and a green automated score never count as approval. Revised mockups require a new version and renewed approval of changed visuals.

## 2. Mandatory visual gates and stage ownership

| Gate | Task | Owner-visible proposal required | Approval effect |
|---|---|---|---|
| VG1 | UXR-01 | **A and B** as comparable image-based design boards; Dashboard, vocabulary, focused study/quiz, Status/Consent; desktop/mobile | Owner selects direction; no design-system foundation without decision |
| VG2 | UXR-02 | AppShell complete UI screenshots: expanded/collapsed desktop navigation, tablet/mid-width, mobile drawer open/closed, representative populated page, light/dark, long labels and state alert | Owner accepts **foundation/AppShell visual design** before UXR-02 is DONE |
| VG3 | UXR-02A | **Compact Dashboard** first-run + populated desktop/mobile screenshots; compact Review empty-state; two-level Status/Consent; compared against existing captures where available | Owner accepts compact/density/layout gate **before** UXR-03–09 execution |
| VG4 | UXR-03–09 | Per-feature high-fidelity screen images for relevant G2–G9 in populated, empty, loading, recoverable, uncertain and terminal/permission states, **as applicable**; desktop/mobile and important overlays | Each feature retains independent `OWNER_REVIEW_PENDING` until user approves its version; parallel design preparation does not imply approvals |
| VG5 | UXR-10 | Nine-group contact sheet + links to full-resolution versions; consistent responsive and state examples, visual change register, accessibility/risk trace | Owner can inspect integrated consistency; QA report does not replace owner sign-off |
| VG6 | UXR-11 | Final **visual design review gallery** covering G1–G9, desktop/mobile, key state paths and design version hashes; approval ledger plus unresolved/declined changes | **Owner's final explicit sign-off** is required before calling redesign design-complete or starting implementation |

Any approval gate remains `OWNER_VISUAL_APPROVAL_PENDING` until required images are accessible. Initial UXR-00 investigation is a separate **baseline evidence** task; it is NOT design approval. App source must not be changed to fabricate screenshots. Visual mockup sources can be isolated in `docs/design/uxr-XX/assets/` or an approved non-production preview folder, with links to browser-rendered exports. No unapproved code under `frontend/` or `backend/`.

**Design-only handoff (UXR-02/02A):** Produce browser-rendered screenshots using static representative content and isolated preview artifacts, not production feature implementation. If a rendering tool is unavailable, report the blocker rather than substituting a text-only approval packet.

## 3. Installed Impeccable skill: REQUIRED for coordinator AND design workers

**Upstream:** https://github.com/pbakaus/impeccable  
**Canonical skill instructions:** https://github.com/pbakaus/impeccable/blob/main/.agents/skills/impeccable/SKILL.md  
**State:** OWNER REPORTS SKILL ALREADY INSTALLED LOCALLY. **Do not install, update, vendor, pin a new version or modify its installation as part of UXR documentation/preparation.**

For each actual local UXR-01–11 design **execution** session:

1. **Coordinator preflight:** Locate the currently installed `impeccable` skill in the active Codex harness; read its installed `SKILL.md` and applicable reference. Use its **actual installed version**, not a presumed version or guessed path. Record provider/harness, resolved skill-base directory, version if available and whether execution is possible.
2. **Invoke, do not merely mention:** Follow the installed skill Setup. Run `<skill-base-dir>/scripts/impeccable context` **once per session from the English Web project cwd** (on PowerShell/Windows use `<skill-base-dir>\scripts\impeccable.cmd context` when applicable). Preserve loaded PRODUCT/DESIGN/surface truth. The slash-command or equivalent native harness skill can route the relevant design verbs. **Do not rerun context per screen or agent message.**
3. **Every independent design worker** must load the skill in their own agent context, invoke context once per actual independent session, and read the command reference for the job. Sharing only the coordinator's summary is insufficient proof of worker use.
4. Recommended **use by stage** (select references/verbs according to installed skill version; not every verb must run): UXR-01 `shape` and design concept review; UXR-02 `shape` / `critique` / `adapt` as appropriate; UXR-02A `layout` + `distill` + `adapt`; UXR-03–09 `critique` / `clarify` / `harden` where applicable; UXR-10 `critique` plus `audit` for supported design evidence; UXR-11 `polish` as **design review** only. Use `live` or `generate` only when their prerequisites, safe browser isolation and output mode are actually available. In the no-code phase, **do not obey a refining verb by editing production application files**: use it to critique or revise isolated mockups/specifications.
5. **Proof-of-use log** in each task artifact: `agent role | actual skill path/version | context invoked (timestamp/result or failure) | chosen command/reference | target | concrete finding/changed design decision | evidence artifact`. Coordinator synthesizes worker proof and resolves duplication; do not invent successful tool invocation or claim that reading GitHub upstream means the locally installed skill ran.
6. If skill is unavailable to the actual agent, set `IMPECCABLE_NOT_ACCESSIBLE`, give the precise discovery/invocation error and notify the owner. **Do not silently skip, claim compliance, or reinstall.** The affected design approval remains blocked pending owner resolution. If the skill's Setup says to continue after launcher failure, continue **analysis only with explicitly degraded provenance**, without declaring the mandatory invocation gate met.
7. Skill guidance is an expert input, **not an override** of owner decisions, contracts, accessibility, Windows/offline safety or the approved shadcn source policy. Use its heuristics to improve information architecture, visual rhythm, clarity, states and responsive design, not to make arbitrary brand/color or data changes.

**Practical separation:** This GitHub documentation session can read the *upstream* Impeccable instructions and write the **future worker contract**, but cannot assert it invoked the **already installed Windows skill**. Real local skill invocation belongs to future authorized local Codex worker sessions. Do not make a false `SKILL_EXECUTED` claim now.

## 4. Missing component policy: official shadcn/ui ONLY

**Sole default source for missing reusable components:** https://ui.shadcn.com/docs/components

- First audit the existing local canonical `frontend/src/components/ui/` primitives, `components.json`, `frontend/src/index.css`, and current Radix base.
- Identify missing pieces by exact official component name and URL: e.g. Sidebar, Breadcrumb, Sheet, Separator, Badge, Alert, Field, Skeleton, Accordion, Collapsible, Progress, Input, Select/Combobox, Tooltip, Alert Dialog.
- Proposed app compositions under future `frontend/src/components/app/` may combine **existing + official shadcn primitives**. Distinguish `ALREADY_PRESENT`, `OFFICIAL_PROPOSED`, `CUSTOM_COMPOSITION`, and `DEFERRED`. Do not use a community registry, copied dashboard template or unapproved component library as a substitute.
- Respect **Radix flavor**, existing `new-york` style, Tailwind 4 and **non-Preflight** CSS. Do not reinitialize Vite or shadcn, overwrite existing Button/Card/Dialog, run `add --all` or apply unreviewed CSS resets.
- During UXR research **component acquisition = documentation, inventory and component references only**, **not** CLI install/add or dependency/lockfile edits. Later approved implementation uses reviewed pinned-version CLI, exact component diff and single owner for shared primitive changes.
- A missing official primitive may be covered by a **documented composition of official primitives** or a scoped native semantic control if needed for accessibility; document its rationale. Third-party registry adoption requires separate explicit owner approval.
- A skill's visual suggestion cannot quietly replace the official shadcn source rule.

## 5. Handoff and conflict rules

- Shared AppShell, tokens, typography, spacing and primitive inventory are **UXR-02 coordinator-owned**. UXR-02A owns cross-screen density and Dashboard representative simplification gate. Feature designers own their own mockup/gallery directories. The roadmap and Draft PR are single-writer coordinator resources.
- UXR-03–09 can design **in parallel only after UXR-02A is approved**, using the same approved shared design version and app-level patterns. Feature sign-offs are independent; UXR-10 requires completed design artifacts and owner-review states from all seven tasks.
- Failures to render a preview, missing skill invocation, conflicting navigation/token decisions, or missing owner approval are blockers, **not** reasons to invent passing evidence.
- No task can declare `DESIGN_DONE` without the applicable owner visual sign-off and traceable screenshots. Only UXR-11 records final integrated approval.
- UXR-12 remains **PROPOSED** and cannot authorize coding. Current Draft PR #26 remains a design-only, unmerged research branch.

**Acceptance test for this protocol:** the final UXR-11 packet must allow an owner to answer, with the **actual images**, “What will Dashboard, Lookup/Search, Review, Quiz, Result/Feedback, Status/Consent and mobile navigation look like?” without running the application or reading a component list.

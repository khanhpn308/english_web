# UXR-01 installed Impeccable evidence

Task: UXR-01. Images: v1.2. Direction B and D1/D2/D3/D4/D6/D8/D9 owner-approved 13/10/2026; evidence remains historical/documentary and was not independently re-executed during finalization. No skill reinstall, update, download, vendoring, pinning, hooks repair, or shadcn installation occurred.

## Installed skill and coordinator invocation

Actual installed skill: `C:/Users/khanh/projects/vocabularies-smoke/.agents/skills/impeccable/SKILL.md`. Metadata version **4.5.2**. Installed launcher: `scripts/impeccable.cmd`; bundled engine/version **0.1.14**, independently reported in [worker evidence](research/worker-evidence-recovery.md). Skill and engine versions are separate.

An initial attempted read at `C:/Users/khanh/.codex/skills/.system/impeccable/SKILL.md` returned a path-not-found error. The correct repository-local installed skill was then read. This was discovery, not an install attempt. The installed launcher subsequently ran successfully; `IMPECCABLE_NOT_ACCESSIBLE` does not describe the resolved state.

Coordinator command, executed **once** for this session:

```text
.agents/skills/impeccable/scripts/impeccable.cmd context
cwd: C:/Users/khanh/projects/vocabularies-smoke
exit: 0
```

Actual directives: `NO_PRODUCT_MD`, `PRODUCT_INIT_REQUIRED`, `RESOLVED_CONTEXT` with the original project/repository root, null product/design/surface brief, `hasVisualImplementation: false`, `platform: null`; `AUTONOMY_DIRECTIVE_CHECK`; `SUBAGENT_AUTHORIZATION`; and `IMAGE_TOOLS` reporting no converter. The complete equivalent context output from the independently invoked worker is retained in [worker evidence](research/worker-evidence-recovery.md); the coordinator's stdout was observed directly in the tool result during this session. That worker output is not presented as a second coordinator invocation.

The launcher ran before the dedicated worktree was created. Final artifact worktree: `C:/Users/khanh/projects/english-web-uxr01`, `work/uxr01-design`. The installed skill stayed in its original location and was not copied into the worktree. Context was not rerun after worktree creation or continuation prompts. The earlier zero-target launcher finding does not establish that the application has no visual implementation.

Read guidance included `shape`, `layout`, `distill`, `adapt`, `critique`, and `craft-floor`. The explicit owner brief settles audience, outcomes, scope, two alternative worlds and the final owner gate. It also restricts writes to `docs/design/uxr-01/`, so no root `PRODUCT.md`/`DESIGN.md` was created and no separate skill interview/shape-stop superseded the authorized visual-production request. This record claims **installed context invocation and selective playbook application**, not full standalone command completion or an Impeccable/WCAG PASS.

## Independently dispatched workers

| Worker | Installed context requirement / actual result | Contribution and affected images | Limit |
|---|---|---|---|
| Direction A assets | Same installed skill 4.5.2; context ran once at original project root, exit 0; recovered actual output in [worker A record](research/worker-a-impeccable.md) | Authored initial standalone A composition, predecessor vA.1.0. Coordinator rendered/corrected final A01–A27 | Worker hit model capacity; final v1.2 is coordinator-owned. Worker records reference-read output truncation and its original cwd. No claimed final independent critique |
| Direction B assets | Same installed skill 4.5.2; context once at original root, exit 0, reported `NO_PRODUCT_MD`, `PRODUCT_INIT_REQUIRED`, resolved original root, no converter | Read shape/layout/distill/adapt/critique/new-work/Operate/craft-floor; reported a drafted console thesis | Worker generation failed before process start with Windows error 206 (command length); **zero B files/images**. Coordinator authored and rendered B01–B27. Invocation evidence is the worker's tool-backed handoff message, not a separately saved stdout file |
| Independent critique | Same installed skill; invocation and findings recorded in [preliminary critique](research/preliminary-independent-critique.md) | Baseline synthesis, nine-group safeguards and preliminary scoring hypotheses | Report preceded final images; hypotheses are not final image-based scores. Worker later hit capacity |
| Worker evidence recovery | Same installed skill 4.5.2; context once, exit 0; engine-probe 0.1.14; exact stdout in [record](research/worker-evidence-recovery.md) | Opened eleven predecessor A PNGs and identified arrow sizing, invalid first-run review CTA, unsupported metrics/goals, mobile quiz hierarchy, dark CTA contrast, drawer evidence gap | Record contains hashes of predecessor bytes. Those findings are historical after coordinator repairs; worker did not independently inspect final B or v1.2. Later capacity failure recorded |

No worker action is inferred from assignment alone. Failed worker output was not described as completed A/B production. After the bounded worker failures, the coordinator completed both options and the integrated judgment.

## Applied findings and image effects

| Guidance | Applied finding / resulting design | Image IDs |
|---|---|---|
| Shape | Explicit job: one-user Windows local-first academic study. Alternatives remain genuine named proposals; no final selected world before owner image review | A01–A27 / B01–B27 |
| Layout | A reading measure + centered Review; B console rail + connected metric/ledger composition + side ratings; tablet returns main width via menu header | A03/A13/A07/A14 vs B03/B13/B07/B14; G1 across all frames |
| Distill | Removed unsupported weekly minutes/trends, B2 focus/progress goals, repeated next-review action and repeated whole-history empties. Replaced invalid first-run Review with Lookup; retained semantic 0/null and necessary safety controls | A01–A04/B01–B04, A13/B13 |
| Adapt | Bounded oversized SVG arrows, wrapped long Vietnamese labels, 44px primary/menu targets, full-width study at tablet, mobile warning moved ahead of permission panel; A shortcuts vs B drawer-only compared | A02/A06/A08/A12/A15/A18/A22 and equivalent B; A14/B14 |
| Critique | Independent predecessor findings used as repair input. Final scores derive from final rendered images and coordinator review; no invented measured usability | Comparison criteria 1–10, linked final image IDs |
| Craft floor | Removed invented dashboard goals/proficiency, used meaningful synthetic content, preserved product truth, no CDN fonts/imagery or new runtime dependency | Dashboard and all source-backed state concepts |

## Verification scope

Standalone HTML was rendered using existing Playwright and installed Google Chrome. Playwright's bundled headless shell was missing on the first attempt; installed Chrome provided the renderer. No browser/package download was performed. The worktree has no node_modules; `UXR_PLAYWRIGHT_PATH` points at the already installed module in the original checkout.

[Static render checks](research/static-render-checks.json) cover 50 route/state/viewport renders of the standalone light mockups: no recorded script errors, no page-level horizontal overflow, no visible button taller than 90px. Screenshots are device scale 1 at their exact labelled viewport. Dark and contact-sheet images were rendered and visually reviewed separately. This proves only the stated mockup observations; it is not production browser testing, full keyboard/a11y validation, a detector-based quality verdict, or full CI.

Further refinements belong to the owner response and later separately authorized task. This packet does not start UXR-02.

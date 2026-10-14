# UXR-02A-R1B Technical Delta

## Source and fixture changes

- R1B is a new isolated copy under `assets/r1b/source/`, derived from the approved A12 square preview. Original R1/A12 source remains untouched.
- A04 uses the existing active-state `counts` object. `total`, percentages, CSS donut segments, legend and accessible text are all derived from it. No state-specific total is hardcoded into markup.
- A02 uses in-place state updates in the R1B copy. The heatmap keeps 105 chronological dates and A12â€™s 11Ã—11 square geometry. The first cell is the single roving focus entry; arrows move focus, Escape dismisses, pointer/tap update the tooltip, and no heatmap interaction navigates the document.
- A08 removes repeated first-run explanatory paragraphs while preserving every Dashboard row and panel. The hero owns the dominant onboarding explanation and CTA; panel empties are compact and state-specific.

## Verification

`check.mjs` passed:

- POPULATED donut: total 110, legend 78/24/8 with 71/22/7%.
- MIXED donut: total 6, legend 5/1/0 with 83/17/0%.
- FIRST_RUN: no donut or heatmap date cells; one dominant hero explanation; no repeated `ChÆ°a cÃ³ dá»¯ liá»‡u` copy.
- Heatmap: 105 cells; exactly one initial `tabindex="0"`; hover switches three dates; pointer exit dismisses; arrows move focus; Escape dismisses; touch tap/close works; no URL changes.
- A12: square grid remains approximately 242Ã—242px; cell geometry remains equal; no horizontal overflow.

## Provenance and limitations

- All R1B frames are browser-rendered `DESIGN_MOCKUP` / `SYNTHETIC_DESIGN_FIXTURE` evidence.
- `Button`, `Card` and the heatmap are conceptual isolated preview compositions; no production React, backend, package, route, API, shadcn or database file changed.
- Production accessibility, real screen-reader semantics, real-device touch and backend result sources remain unverified.

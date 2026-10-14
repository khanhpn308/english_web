# UXR-02A-R1B Final Targeted Correction Report

**Task:** UXR-02A-R1B
**Parent:** UXR-02A
**State:** `OWNER_VISUAL_APPROVAL_PENDING`
**Independent review:** exact 2026-10-14 report was absent; the supplied A04/A02/A08 contract was used.

## Finding status

| Finding | Root cause | Correction | Evidence | Status |
|---|---|---|---|---|
| A04 mixed donut | CSS pseudo-element kept the populated `110` center while the mixed fixture was 5/1/0 | Added `data-total` from the active `counts` object; CSS uses `content: attr(data-total)`; one data object drives counts, total, percentages, legend and segments | [mixed](assets/r1b/frames/R1B-mixed-1366x768.png), [populated](assets/r1b/frames/R1B-populated-1366x768.png) | `PASS` |
| A02 keyboard/tooltip | Prior reload-oriented interaction could prevent reliable in-place focus/tooltip updates | Preserved A12 square grid and replaced R1B interaction copy with in-place tooltip state, roving `tabindex`, arrows, Escape, hover switch, pointer exit, touch tap and close | [keyboard](assets/r1b/frames/R1B-heatmap-keyboard-1366x768.png), [tooltip](assets/r1b/frames/R1B-heatmap-tooltip-1366x768.png), [mobile tap](assets/r1b/frames/R1B-heatmap-mobile-tap-390x844.png) | `PASS` |
| A08 first-run duplication | Empty panels repeated onboarding/history prose | Kept all four Dashboard rows and compacted panel empties; the hero is the only dominant first-run explanation/CTA. Book, due, history, result and progress surfaces use short state labels/placeholders | [A first-run](assets/r1b/frames/R1B-A-first-run-1366x768.png), [B first-run](assets/r1b/frames/R1B-B-first-run-1366x768.png) | `PASS` |
| A12 preservation | Previously approved square geometry must survive A02 changes | R1B starts from the A12 source; square cell/block geometry, 105 dates, 16 non-data slots, themes and semantics remain measured | [A12-preserved default](assets/r1b/frames/R1B-heatmap-default-1366x768.png), [dark](assets/r1b/frames/R1B-heatmap-dark-1366x768.png) | `PASS` |

## Targeted results

- A04 populated remains `78/24/8 = 110`; mixed is `5/1/0 = 6`, with `83/17/0%`.
- A02 has exactly one initial `tabindex="0"` cell and 104 `tabindex="-1"` cells. No heatmap hover/focus/tap changes the document URL.
- A08 first-run keeps the four Dashboard rows and contains zero repeated `ChÆ°a cÃ³ dá»¯ liá»‡u` copies in the measured Dashboard text; panel-specific labels remain truthful.
- A12 verification remains PASS: equal cells, square block, no overflow, five levels, zero/UNKNOWN distinction.

## Limitations

These are isolated Chromium `DESIGN_MOCKUP` / `SYNTHETIC_DESIGN_FIXTURE` checks. They do not establish production React behavior, backend data contracts, screen-reader output or physical-device touch behavior.

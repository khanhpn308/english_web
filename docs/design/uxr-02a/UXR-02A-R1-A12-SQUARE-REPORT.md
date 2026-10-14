# UXR-02A-R1 A12 â€” Square Heatmap Geometry

**Finding:** `A12_HEATMAP_SQUARE_GEOMETRY`
**Priority:** P1
**Status:** `PASS`
**Scope:** R1 isolated preview only; original R1 and UXR-02 source remain unchanged.

## Correction

- The 105 chronological cells are laid out as an 11Ã—11 square grid: 105 dates plus sixteen layout-only padding cells.
- Every cell wrapper and button uses `aspect-ratio: 1`, equal width/height, consistent 3px gaps and no border.
- The grid is centered in its card with a capped width of 242px, so the visible composition reads as a square on desktop, tablet and mobile.
- The legend stays below the square block; tooltip positioning is clamped to the grid bounds.
- Light/dark cell levels, zero, UNKNOWN, keyboard focus, hover, tap, Escape and dismissal semantics are preserved.
- Dates run chronologically across each row. The sixteen blank slots are noninteractive, hidden from assistive technology and never counted as zero/unknown dates.
- First-run retains a square empty envelope with no fabricated history cells. The original week-column arrangement is superseded only in this owner-authorized square-geometry preview.

## Evidence

- [Desktop default square heatmap](assets/r1/a12/frames/A12-desktop-default.png)
- [Desktop tooltip square heatmap](assets/r1/a12/frames/A12-desktop-tooltip.png)
- [Mobile 390px square heatmap](assets/r1/a12/frames/A12-mobile-390-default.png)
- [Mobile 390px tap tooltip](assets/r1/a12/frames/A12-mobile-390-tooltip.png)
- [Mobile 320px square heatmap](assets/r1/a12/frames/A12-mobile-320-default.png)
- [Dark theme square heatmap](assets/r1/a12/frames/A12-desktop-dark.png)
- [A12 verification JSON](assets/r1/a12/verification.json)
- [Readable contact sheet](assets/r1/a12/contact-sheet.png)
- [Tablet default](assets/r1/a12/frames/A12-tablet-default.png)
- [Mobile 320px dark](assets/r1/a12/frames/A12-mobile-320-dark.png)
- [Updated Dashboard A desktop](assets/r1/a12/frames/A12-dashboard-A-desktop.png)
- [Updated Dashboard B desktop](assets/r1/a12/frames/A12-dashboard-B-desktop.png)
- [Updated 390px full page](assets/r1/a12/frames/A12-dashboard-390-full.png)
- [Updated 320px full page](assets/r1/a12/frames/A12-dashboard-320-full.png)

The packet contains 12 screenshots plus one contact sheet. Card detail images are native-resolution browser crops; their recorded CSS viewport and pixel dimensions are in `verification.json`. Full Dashboard frames retain the locked row/panel order and naturally scroll after the square heatmap increases Row 3 height.

## Geometry validation

The targeted Chromium check measured 20 combinations: 1366Ã—768, 1024Ã—768, 768Ã—1024, 390Ã—844 and 320Ã—568 across light/dark themes and Variants A/B.

- 105 cells in every case.
- 105 unique consecutive dates: 2026-09-28 through 2027-01-10.
- Maximum measured cell width/height difference: `0px` (check tolerance `0.05px`).
- The grid measures approximately `242Ã—242px`, or `239Ã—239px` when its tablet card is narrower. Width/height ratio is `0.9996â€“1.0000`; subpixel rounding is below `0.1px`.
- Grid centered error is below `0.01px` (check tolerance `1px`).
- No horizontal overflow; cell borders computed as `0px`.
- Interaction checks passed for hover, pointer exit, keyboard focus, ArrowRight movement, 2px focus outline, Escape, emulated touch tap and close.

These are isolated Chromium design-preview checks. They do not establish production accessibility, real-device touch behavior or runtime data correctness.

## Reproduction and preservation

Run `node docs/design/uxr-02a/assets/r1/a12/prepare.mjs`, then `node docs/design/uxr-02a/assets/r1/a12/verify-render.mjs`. The latter starts and stops a dedicated loopback preview server and records geometry, interaction checks and screenshot dimensions.

R1's original URL-reload tooltip handler was replaced in the A12 copy by in-place preview state, so focus and arrow navigation remain on the relevant cell. No new product operation or provider call is introduced. All previous preview sources/images remain intact. Production files and frozen UXR-02 files are untouched; no commit, push or merge occurred. Owner approval remains `PENDING`.

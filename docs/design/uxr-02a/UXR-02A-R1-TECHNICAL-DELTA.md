# UXR-02A-R1 Technical Delta

## Changed-file inventory

### Original packet preserved

- `assets/source/preview.html`
- `assets/source/preview.js`
- `assets/source/render.mjs`
- `assets/frames/*.png`
- `assets/contact-sheets/*.png` and `.html`
- All original UXR-02A Markdown documents

### R1 additions

- `assets/r1/source/preview.html` â€” copied isolated preview with R1-only CSS overrides.
- `assets/r1/source/preview.js` â€” corrected synthetic fixture, chart, carousel, HM-FIX grid and state semantics.
- `assets/r1/source/render.mjs` â€” Chrome renderer for viewport/full-page R1 frames.
- `assets/r1/frames/*.png` â€” 17 corrected frames.
- `assets/r1/contact-sheets/ab.html` and `r1-ab-comparison.png`.
- `UXR-02A-R1-CORRECTION-REPORT.md`, `UXR-02A-R1-OWNER-REVIEW.md`, `UXR-02A-R1-TECHNICAL-DELTA.md`.

## Fixture consistency

- Populated result fixture: Correct 78, Incorrect 24, Blank 8, Total 110; percentages 71%, 22%, 7%.
- Populated Writing self-score: 3.6 / 4.
- Future due anchor: 14/10/2026; buckets 15/10â€“21/10.
- HM-FIX: 105 unique cells, 28/09/2026â€“10/01/2027, levels 0â€“4, one separate UNKNOWN cell.
- Mixed: dueCards=0, currentDays=null, existing quiz history retained, Cloze attempted=0/accuracy=null.
- First-run: no book collection, no historical chart points, no result denominator.

## Preview provenance

The R1 preview is an isolated HTML/JavaScript design mockup. It does not import production React components and does not claim that the book dataset, charts or heatmap API exist. The HM-FIX count matrix/range and interaction vocabulary were adapted from the read-only approved UXR-02 source; UXR-02 files remain unchanged. Official shadcn provenance remains source-only; no component installation occurred.

## Interaction and responsive limitations

- Chromium checks exercise cell count, date set, swatches, tooltip rendering, carousel affordances, Review height and overflow.
- Hover/focus/tap proof is isolated preview behavior; production focus management, screen-reader announcements and real touch behavior remain unverified.
- Full-page screenshots cover 390px populated and 320px first-run. Tablet/intermediate/dark corrected frames are also rendered.
- The 200% requirement is represented by effective narrow-width reflow checks; this is not a WCAG or browser zoom conformance claim.

## A12 square geometry delta

- Added versioned `assets/r1/a12/` preview/source, 12 evidence images, one contact sheet and verification JSON.
- Changed the isolated heatmap grid to an 11Ã—11 square composition: 105 chronological date cells plus sixteen non-data padding cells, centered within the card. First-run uses a square empty envelope.
- Replaced URL-reload tooltip handling in the A12 copy with in-place preview state and arrow navigation; executed hover, focus, Escape, dismissal and emulated touch checks.
- Preserved the approved HM-FIX count matrix, date range, five levels, zero/UNKNOWN treatment, no borders and keyboard/hover/tap semantics.
- Measured geometry across 20 desktop/tablet/mobile/theme/variant combinations; see `verification.json` and [A12 report](UXR-02A-R1-A12-SQUARE-REPORT.md).


## R1B follow-up

R1B is an additional isolated copy for A04/A02/A08. It derives the donut total from the active fixture, uses in-place heatmap state and compact first-run panel empties, while preserving the A12 square source and previous R1 artifacts. See [UXR-02A-R1B-TECHNICAL-DELTA.md](UXR-02A-R1B-TECHNICAL-DELTA.md).

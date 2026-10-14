# UXR-02A Visual Gallery

**All proposed images:** `DESIGN_MOCKUP` Â· isolated static HTML/CSS preview Â· synthetic metrics disclosed.
**Full-resolution contact sheets:** [gallery.png](assets/contact-sheets/gallery.png) Â· [before-proposed.png](assets/contact-sheets/before-proposed.png).
**Preview source:** [preview.html](assets/source/preview.html) Â· [preview.js](assets/source/preview.js) Â· [render.mjs](assets/source/render.mjs).

## Full-resolution inventory

| Frame | State | CSS viewport | Theme | Link |
|---|---|---:|---|---|
| D1 | Dashboard first-run | 1366Ã—768 | light | [PNG](assets/frames/D1-dashboard-first-run-1366x768-light.png) |
| D2 | Dashboard first-run | 390Ã—844 | light | [PNG](assets/frames/D2-dashboard-first-run-390x844-light.png) |
| D3 | Dashboard populated | 1366Ã—768 | light | [PNG](assets/frames/D3-dashboard-populated-1366x768-light.png) |
| D4 | Dashboard populated | 390Ã—844 | light | [PNG](assets/frames/D4-dashboard-populated-390x844-light.png) |
| D5 | Dashboard mixed/null/zero | 1366Ã—768 | light | [PNG](assets/frames/D5-dashboard-mixed-1366x768-light.png) |
| D6 | Dashboard first-run | 320Ã—568 | light | [PNG](assets/frames/D6-dashboard-first-run-320x568-light.png) |
| R1 | Review empty | 1366Ã—768 | light | [PNG](assets/frames/R1-review-empty-1366x768-light.png) |
| R2 | Review empty | 390Ã—844 | light | [PNG](assets/frames/R2-review-empty-390x844-light.png) |
| R3 | Review UNKNOWN/pending | 390Ã—844 | light | [PNG](assets/frames/R3-review-unknown-pending-390x844-light.png) |
| S1 | Status/Consent summary | 1366Ã—768 | light | [PNG](assets/frames/S1-status-consent-summary-1366x768-light.png) |
| S2 | Status/Consent summary | 390Ã—844 | light | [PNG](assets/frames/S2-status-consent-summary-390x844-light.png) |
| S3 | Status degraded + unknown consent | 1366Ã—768 | light | [PNG](assets/frames/S3-status-degraded-1366x768-light.png) |
| VB-D1 | Dashboard Variant B first-run | 1366Ã—768 | light | [PNG](assets/frames/VB-dashboard-first-run-1366x768-light.png) |
| VB-D4 | Dashboard Variant B populated | 390Ã—844 | light | [PNG](assets/frames/VB-dashboard-populated-390x844-light.png) |
| Theme | Dashboard populated | 1366Ã—768 | dark | [PNG](assets/frames/D3-dashboard-populated-1366x768-dark.png) |
| T1 | Dashboard populated tablet | 768Ã—1024 | light | [PNG](assets/frames/tablet-dashboard-populated-768x1024-light.png) |
| T2 | Dashboard populated intermediate | 1024Ã—768 | light | [PNG](assets/frames/intermediate-dashboard-populated-1024x768-light.png) |
| Board | G1â€“G9 contract board | 1366Ã—768 | light | [PNG](assets/frames/board-g1-g9-1366x768-light.png) |

## Coverage notes

- The first-viewport annotation is [D1 annotated](assets/frames/D1-dashboard-first-run-1366x768-annotated.png).
- Same-state light/dark evidence is D3 light plus [D3 dark](assets/frames/D3-dashboard-populated-1366x768-dark.png).
- Responsive evidence includes 320, 390, 768, 1024 and 1366 CSS pixel viewports. The 1440Ã—900 R2 foundation is inherited; UXR-02A does not redraw the frozen foundation.
- Long Vietnamese copy is present in hero, Review, Status and disclosure examples. At 200% zoom, the contract treats the surface as a narrow reflow and requires no horizontal scroll or clipped focus.
- No runtime production accessibility PASS is claimed. Browser-rendered static mockups prove composition only.

## R1 correction addendum

The initial gallery is preserved as historical UXR-02A evidence. A targeted R1 package corrects the independent A-01â€“A-11 regressions without replacing the approved foundation. Use the [R1 owner review](UXR-02A-R1-OWNER-REVIEW.md) and [R1 A/B contact sheet](assets/r1/contact-sheets/r1-ab-comparison.png) for current conformance review. The R1 package adds full-page mobile frames, restored charts, exact HM-FIX heatmap evidence, corrected fixture semantics and a content-sized Review empty card.

The A12 addendum adds [square heatmap evidence](UXR-02A-R1-A12-SQUARE-REPORT.md): desktop default/tooltip, 390px mobile, 320px mobile, tablet and dark-theme frames with measured equal cell geometry.

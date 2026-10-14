# UXR-02A-R1 Correction Report

**Task:** UXR-02A-R1
**Parent:** UXR-02A
**State:** `OWNER_VISUAL_APPROVAL_PENDING`
**Foundation preserved:** UXR-02-R2 + HM-FIX
**Independent review file:** `UXR-02A-INDEPENDENT-REVIEW-2026-10-14.md` was absent at the repository root; this report uses the supplied A-01â€“A-11 contract.

## Finding resolution

| Finding | Original root cause | Exact correction | R1 evidence | Status | Remaining limitation |
|---|---|---|---|---|---|
| A-01 Progress chart | Row 4 used two text statistics instead of the approved chart | Added content-sized SVG line chart with 14 points, dates, scale, guide lines and first-run empty chart state | [A populated](assets/r1/frames/R1-A-populated-1366x768-light.png), [mobile full page](assets/r1/frames/R1-populated-390x844-full.png) | `PASS` | Static SVG; production data/tooltips remain future work |
| A-02 HM-FIX heatmap | 70 decorative cells and text-only legend | Reused the approved HM-FIX count matrix/range logic in isolated R1 source; rendered 105 cells, five swatches, zero/UNKNOWN, date-specific tooltip states | [detail](assets/r1/frames/R1-heatmap-detail-1366x768-light.png), [tooltip](assets/r1/frames/R1-heatmap-tooltip-1366x768-light.png), [zero](assets/r1/frames/R1-heatmap-zero-390x844-light.png) | `PASS` | Chromium interaction evidence only; no production/real-device PASS |
| A-03 Writing score | Populated fixture displayed `4.2 / 5` | Changed populated fixture to `3.6 / 4`; kept objective quiz accuracy separate | [A populated](assets/r1/frames/R1-A-populated-1366x768-light.png) | `PASS` | Synthetic score |
| A-04 Results donut | Inconsistent percentage/count summary | Restored ÄÃºng/Sai/Bá» trá»‘ng with 78/24/8 = 110 and 71/22/7 percentages; no-attempt state has no fabricated percent | [A populated](assets/r1/frames/R1-A-populated-1366x768-light.png), [mixed](assets/r1/frames/R1-mixed-null-zero-1366x768-light.png) | `PASS` | Synthetic result fixture |
| A-05 Future due workload | Widget represented the previous seven days | Restored `Tháº» Ä‘áº¿n háº¡n 7 ngÃ y tá»›i`, seven future buckets 15/10â€“21/10 and fixture anchor 14/10/2026 | [A populated](assets/r1/frames/R1-A-populated-1366x768-light.png) | `PASS` | Future API remains unimplemented |
| A-06 Book carousel/truthfulness | Populated affordances were incomplete; first-run showed a named book with no history | Populated has one visible book, previous/next, five dots and 1/5; first-run has an empty panel with no book name or position | [populated](assets/r1/frames/R1-A-populated-1366x768-light.png), [first-run](assets/r1/frames/R1-A-first-run-1366x768-light.png) | `PASS` | Five-book dataset is synthetic; no Library route/API claim |
| A-07 Skill categories | Skills were replaced by unrelated labels | Restored Cloze, Tráº¯c nghiá»‡m and Writing with separate indicators/actions | [A populated](assets/r1/frames/R1-A-populated-1366x768-light.png) | `PASS` | Synthetic indicators |
| A-08 First-run/mixed semantics | First-run repeated generic empty explanations; mixed state contradicted itself | First-run uses empty book/history/chart/result surfaces; mixed retains quiz results, dueCards=0, `currentDays=null`, and objective attempted=0/accuracy=null | [first-run](assets/r1/frames/R1-A-first-run-1366x768-light.png), [mixed](assets/r1/frames/R1-mixed-null-zero-1366x768-light.png) | `PASS` | Source predicate is represented as a fixture, not production runtime |
| A-09 Review height | `.review-empty` retained a 300px minimum | R1 override sets `min-height:0` and content-driven padding; toolbar/empty/live-region semantics remain | [desktop](assets/r1/frames/R1-review-empty-1366x768-light.png), [mobile](assets/r1/frames/R1-review-empty-390x844-light.png) | `PASS` | Static preview only |
| A-10 Full-page mobile/reflow | Prior mobile evidence stopped at the viewport | Added full-page 390px populated and 320px first-run captures; all four rows are present and no horizontal overflow was observed | [390 full](assets/r1/frames/R1-populated-390x844-full.png), [320 full](assets/r1/frames/R1-first-run-320x568-full.png) | `PASS` for effective-width reflow | Browser zoom and screen reader semantics remain implementation gates |
| A-11 Documentation accuracy | Original matrix treated AC01â€“AC15 as complete despite regressions | Added R1 acceptance addendum, correction report, owner review and technical delta; owner approval remains pending | [R1 owner review](UXR-02A-R1-OWNER-REVIEW.md), [technical delta](UXR-02A-R1-TECHNICAL-DELTA.md) | `PASS` for artifact correction; approval pending | AC16 cannot close without owner response |

## Scope safety

- Original UXR-02A frames and source remain under `assets/frames/`, `assets/contact-sheets/` and `assets/source/`.
- R1 source and images are isolated under `assets/r1/`.
- No AppShell, route, API, frontend, backend, contract, package or approved UXR-02 file was modified.
- Status/Consent and Review UNKNOWN/PENDING content was retained except for the direct A-09 height correction.

## A12 addendum

`A12_HEATMAP_SQUARE_GEOMETRY` is `PASS`. The new square-geometry preview and measured evidence are documented in [UXR-02A-R1-A12-SQUARE-REPORT.md](UXR-02A-R1-A12-SQUARE-REPORT.md). A12 is an additional owner requirement and does not reopen the UXR-02 foundation or Dashboard variant selection.


## R1B supersession note

R1B is the authoritative targeted correction for remaining A04, A02 and A08 defects. See [UXR-02A-R1B-FINAL-CORRECTION-REPORT.md](UXR-02A-R1B-FINAL-CORRECTION-REPORT.md). R1 evidence remains preserved.

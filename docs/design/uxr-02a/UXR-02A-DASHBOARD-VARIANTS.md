# UXR-02A Dashboard Variants

**Comparison scope:** density treatment only inside the owner-locked UXR-02 Dashboard composition.
**Owner decision:** `APPROVED â€” Variant B / Compact Refinement / UXR-02A-R1B` (`2026-10-14`).
**Recommendation:** Variant B is the owner-approved frozen design; Variant A remains the preserved comparison reference.

## Invariants shared by both candidates

- R2 expanded 210px dark-teal rail, 54px header, same navigation and teal/cool tokens.
- Four locked Dashboard rows remain in the same order:
  1. Today's learning task + one-book carousel.
  2. Due cards, streak, quiz accuracy, writing self-score.
  3. Seven-day due workload, history heatmap, result donut.
  4. Fourteen-day progress, skills to strengthen, recent activity.
- No duplicate book-progress panel, new metric or composite learning score.
- HM-FIX five-level heatmap and UNKNOWN distinction remain intact.
- Every state has at most one dominant contextual CTA.

## Variant A â€” Reference-faithful baseline

**Frames:** [first-run desktop](assets/frames/D1-dashboard-first-run-1366x768-light.png), [populated desktop](assets/frames/D3-dashboard-populated-1366x768-light.png), [first-run mobile](assets/frames/D2-dashboard-first-run-390x844-light.png), [populated mobile](assets/frames/D4-dashboard-populated-390x844-light.png).

- Uses the approved R2 panel padding and comfortable compact baseline.
- Keeps supporting notes in KPI tiles so meaning is explicit in the first viewport.
- Keeps the book card's progress bar visible even when it is zero/unknown.
- Best for owner comparison against the published UXR-02 reference and for content-rich reading comfort.

## Variant B â€” Compact-density refinement

**Frames:** [first-run desktop](assets/frames/VB-dashboard-first-run-1366x768-light.png), [populated mobile](assets/frames/VB-dashboard-populated-390x844-light.png).

- Same row structure, panel locations, shell, navigation and visual identity.
- Reduces internal card padding and row gaps by one spacing step.
- Keeps labels and values, but makes secondary notes quieter and moves supporting explanation into the panel's existing lower line.
- Uses the existing book panel for progress and one concise contextual sentence; no additional card or action.
- At mobile, the same vertical order remains; only internal rhythm and note density change.

## Recommendation and trade-off

Variant B is recommended because it exposes more of Rows 3â€“4 at 1366Ã—768 while preserving the approved hierarchy and gives the mobile first viewport a shorter scan. Variant A is the safer reference-faithful baseline and may be preferred if owner review prioritizes breathing room over visible lower-row context. This is a design recommendation, not owner approval.

## Historical owner comparison record (superseded by final selection)

| Version | First-run desktop | Populated mobile | Recommendation | Owner response |
|---|---|---|---|---|
| A Â· `UXR-02A-DENSITY-1.0-A` | [D1](assets/frames/D1-dashboard-first-run-1366x768-light.png) | [D4](assets/frames/D4-dashboard-populated-390x844-light.png) | reference-faithful | `PENDING` |
| B Â· `UXR-02A-DENSITY-1.0-B` | [VB-D1](assets/frames/VB-dashboard-first-run-1366x768-light.png) | [VB-D4](assets/frames/VB-dashboard-populated-390x844-light.png) | **recommended** | `PENDING` |

The owner must choose a named version after viewing the full-resolution frames. No model score or internal recommendation closes this gate.

## R1 correction status

Both variants use the same corrected synthetic fixture and required widgets: 14-day line chart, future due workload, 105-cell HM-FIX heatmap, 78/24/8 donut, 3.6/4 Writing score, Cloze/Trắc nghiệm/Writing skills and truthful book states. Variant B changes internal spacing only. See the [R1 correction report](UXR-02A-R1-CORRECTION-REPORT.md) and the R1B correction report. The pending wording in this historical paragraph is superseded by the final owner selection below.
## Final owner selection (2026-10-14)

- Variant B â€” Compact Refinement, release UXR-02A-R1B: OWNER_APPROVED / FROZEN.
- Variant A â€” Reference-faithful baseline: ALTERNATIVE / NOT_SELECTED / HISTORICAL_REFERENCE.
- The owner selected B because its compact internal spacing exposes more useful content without changing the four-row structure, fixtures, metric semantics, shell, palette or feature behavior contract.
- The R1B corrected frames use the same fixture and HM-FIX/A12 contract for equivalent states. Approval is design-only; production implementation remains downstream.

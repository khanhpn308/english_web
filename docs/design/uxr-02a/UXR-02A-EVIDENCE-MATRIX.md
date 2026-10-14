# UXR-02A Evidence Matrix

**Task:** UXR-02A Â· Layout Simplification & Information Density
**Status:** DONE / OWNER_APPROVED / DESIGN_PUBLISHED_PENDING_GIT_CONFIRMATION
**Branch:** `design/ui-ux-research-20261012`
**Foundation:** `UXR-02-R2 + HM-FIX` (owner approved 2026-10-14)
**Evidence rule:** proposed frames are `DESIGN_MOCKUP` with synthetic fixtures. Baseline captures retain their original `REAL_RENDERED` or `SYNTHETIC_RENDERED` provenance.

## Dependency reconciliation

| Dependency | Current evidence | Result |
|---|---|---|
| UXR-00 | [`artifacts/uxr00/final/UXR-00-REPORT.md`](../../../artifacts/uxr00/final/UXR-00-REPORT.md) reports `PARTIAL_WITH_EXPLICIT_BLOCKERS`, 21 canonical screenshots, G7 and populated Dashboard gaps | `VERIFIED_WITH_EXPLICIT_GAPS` |
| UXR-01 | [`UXR-01-DESIGN-DECISION.md`](../uxr-01/UXR-01-DESIGN-DECISION.md) is `DONE / OWNER_APPROVED / PUBLISHED`, Direction B v1.2 | `VERIFIED` |
| UXR-02 | [`UXR-02-APPROVAL.md`](../uxr-02/UXR-02-APPROVAL.md) records `OWNER_VISUAL_APPROVAL: APPROVED`, `UXR-02-R2 + HM-FIX` | `VERIFIED` |
| UXR-02A authorization | Current owner instruction explicitly grants execution; final visual approval is not granted | `VERIFIED / IN_PROGRESS` |

## State and viewport ledger

| ID | Group/state | Viewport/theme | Proposed evidence | Data provenance | Approval flag |
|---|---|---|---|---|---|
| D1 | G9 first-run | 1366Ã—768 light | [D1](assets/frames/D1-dashboard-first-run-1366x768-light.png) Â· [annotated](assets/frames/D1-dashboard-first-run-1366x768-annotated.png) | `SYNTHETIC_RENDERED/DESIGN_MOCKUP` | pending |
| D2 | G9 first-run | 390Ã—844 light | [D2](assets/frames/D2-dashboard-first-run-390x844-light.png) | `SYNTHETIC_RENDERED/DESIGN_MOCKUP` | pending |
| D3 | G9 populated | 1366Ã—768 light | [D3](assets/frames/D3-dashboard-populated-1366x768-light.png) | synthetic due/streak/quiz/writing/history | pending |
| D4 | G9 populated | 390Ã—844 light | [D4](assets/frames/D4-dashboard-populated-390x844-light.png) | synthetic | pending |
| D5 | G9 mixed/null/zero | 1366Ã—768 light | [D5](assets/frames/D5-dashboard-mixed-1366x768-light.png) | `dueCards=0`, `currentDays=null`, `attempted=0`, `accuracy=null` | pending |
| D6 | G9 first-run stress | 320Ã—568 light | [D6](assets/frames/D6-dashboard-first-run-320x568-light.png) | synthetic | pending |
| R1 | G5 empty queue | 1366Ã—768 light | [R1](assets/frames/R1-review-empty-1366x768-light.png) | source-confirmed URL contract + synthetic empty queue | pending |
| R2 | G5 empty queue | 390Ã—844 light | [R2](assets/frames/R2-review-empty-390x844-light.png) | synthetic | pending |
| R3 | G5 UNKNOWN/pending | 390Ã—844 light | [R3](assets/frames/R3-review-unknown-pending-390x844-light.png) | source-confirmed phase contract | pending |
| S1 | G8 summary | 1366Ã—768 light | [S1](assets/frames/S1-status-consent-summary-1366x768-light.png) | source-confirmed local/AI separation; synthetic statuses | pending |
| S2 | G8 summary | 390Ã—844 light | [S2](assets/frames/S2-status-consent-summary-390x844-light.png) | synthetic | pending |
| S3 | G8 degraded + unknown consent | 1366Ã—768 light | [S3](assets/frames/S3-status-degraded-1366x768-light.png) | source-confirmed state vocabulary; synthetic alert | pending |
| VB-D1 | G9 Variant B first-run | 1366Ã—768 light | [Variant B first-run](assets/frames/VB-dashboard-first-run-1366x768-light.png) | synthetic | pending |
| VB-D4 | G9 Variant B populated | 390Ã—844 light | [Variant B populated](assets/frames/VB-dashboard-populated-390x844-light.png) | synthetic | pending |
| T1 | G9 tablet | 768Ã—1024 light | [tablet](assets/frames/tablet-dashboard-populated-768x1024-light.png) | synthetic | pending |
| T2 | G9 intermediate | 1024Ã—768 light | [intermediate](assets/frames/intermediate-dashboard-populated-1024x768-light.png) | synthetic | pending |
| Theme | G9 populated | 1366Ã—768 dark | [D3 dark](assets/frames/D3-dashboard-populated-1366x768-dark.png) | same fixture as D3 | pending |
| Board | G1â€“G9 contract board | 1366Ã—768 light | [density board](assets/frames/board-g1-g9-1366x768-light.png) | design contract | pending |

## Existing baseline evidence

The before/proposed sheet uses genuine existing bytes where available: [before-proposed.png](assets/contact-sheets/before-proposed.png). Baselines are not treated as approved target designs.

| Screen | Genuine baseline | Evidence limitation |
|---|---|---|
| Dashboard | `artifacts/uxr00/A3-browser/screenshots/G9-dashboard-first-run-REAL_RENDERED-1440x900.png` | first-run only; populated Dashboard remains not verified |
| Review | `artifacts/uxr00/A3-browser/screenshots/G5-review-populated-SYNTHETIC_RENDERED-1440x900.png` | populated state, not the empty state proposed here |
| Status | `artifacts/uxr00/A3-browser/screenshots/G8-status-REAL_RENDERED-1440x900.png` | current diagnostics hierarchy; consent reachability remains a design requirement |
| G3/G4/G7 | `SOURCE_ONLY / NOT_VERIFIED` for this task | no new screenshots invented |

## Acceptance trace

| Criterion | Evidence in this packet | Result at handoff |
|---|---|---|
| AC01 | dependency table and approval links above | met with UXR-00 gaps carried forward |
| AC02 | 12 primary + 2 Variant B frames, responsive/theme pair, contact sheets | met |
| AC03 | [`UXR-02A-DASHBOARD-VARIANTS.md`](UXR-02A-DASHBOARD-VARIANTS.md) + owner decision sheet | pending owner choice |
| AC04 | annotated D1 | met as design evidence |
| AC05 | one dominant CTA policy in density contract | met |
| AC06 | D1 hero is the sole visible first-run/no-history explanation; R1 has one visible queue-empty surface | met |
| AC07 | D3/D5/S3/R3 semantic state labels | met as mockup evidence |
| AC08 | S1â€“S3 and deep-link plan | met as design evidence |
| AC09 | R1â€“R3 distinct mutation states | met as design evidence |
| AC10 | nine-group matrix in density contract | met |
| AC11 | 1366/390/320/768/1024, 200% notes | met as design requirements |
| AC12 | official mapping with local/proposed provenance | met |
| AC13 | coordinator context invocation in Impeccable evidence | met; no workers dispatched |
| AC14 | no production files changed | met |
| AC15 | draft handoff with owners and unresolved exceptions | met, draft |
| AC16 | owner decision remains `PENDING` | intentionally open |

## Verification notes

- PNG dimensions were checked from the requested CSS viewport sizes by the browser renderer; full-page scrolling is not used to fake first-viewport compliance.
- Synthetic data is never described as current production data.
- Mockups do not establish runtime accessibility, keyboard behavior, contrast conformance or API correctness.

## R1 acceptance addendum

The initial acceptance rows above describe the original packet and are retained for history. The authoritative correction status is now:

| Acceptance area | R1 status | Evidence |
|---|---|---|
| AC01 dependencies | `PASS` | frozen UXR-02-R2 + HM-FIX links and owner authorization |
| AC02 image packet | `PASS` | [R1 owner review](UXR-02A-R1-OWNER-REVIEW.md), 17 corrected frames + A/B sheet |
| AC03 variant choice | `OWNER_APPROVAL_PENDING` | corrected A/B comparison; no self-selection |
| AC04 first viewport | `PASS` | corrected A first-run desktop |
| AC05 CTA hierarchy | `PASS` | corrected first-run/populated states |
| AC06 empty handling | `PASS` | first-run book/history/chart/result states are distinct; Review has one empty surface |
| AC07 semantic truth | `PASS` | mixed/null/zero and corrected fixture report |
| AC08 Status safety | `PASS` | Status frames unchanged and retained |
| AC09 Review mutation | `PASS` | R1 empty/UNKNOWN frames; no operation semantics changed |
| AC10 nine-group matrix | `PASS` | original density contract retained |
| AC11 responsive evidence | `PASS` for design/reflow evidence | full-page 390px/320px plus tablet/intermediate/dark frames |
| AC12 shadcn provenance | `PASS` | source-only mapping; no installation |
| AC13 Impeccable proof | `PASS` | prior coordinator evidence retained; R1 used same loaded context |
| AC14 boundaries | `PASS` | production tree and UXR-02 files untouched |
| AC15 handoff | `PARTIAL` | R1 corrections documented; owner approval still open |
| AC16 owner visual approval | `OWNER_APPROVAL_PENDING` | [R1 owner decision fields](UXR-02A-R1-OWNER-REVIEW.md) |

See the complete [R1 correction report](UXR-02A-R1-CORRECTION-REPORT.md) and [technical delta](UXR-02A-R1-TECHNICAL-DELTA.md). No previous review history was erased.

### A12 owner requirement

`A12_HEATMAP_SQUARE_GEOMETRY: PASS` â€” corrected square-cell/square-block evidence is in [UXR-02A-R1-A12-SQUARE-REPORT.md](UXR-02A-R1-A12-SQUARE-REPORT.md). This addendum preserves the 105-date HM-FIX contract and remains subject to owner visual approval.


## R1B final targeted addendum

The authoritative remaining-defect statuses are recorded in [UXR-02A-R1B-FINAL-CORRECTION-REPORT.md](UXR-02A-R1B-FINAL-CORRECTION-REPORT.md). A04, A02 keyboard/tooltip behavior and A08 first-run duplication are PASS in the isolated preview; A12 remains PASS. AC03 and AC16 remain owner-pending.

### Final closure addendum (2026-10-14)

| Criterion | Final outcome | Evidence |
|---|---|---|
| AC01 | PASS with UXR-00 explicit gaps carried forward | dependency reconciliation above and approved UXR-01/02 records |
| AC02 | PASS | original 12+2 gallery plus R1/A12/R1B correction packet |
| AC03 | PASS | owner selected Variant B / Compact Refinement, release UXR-02A-R1B |
| AC04 | PASS | first-viewport/fold annotation and approved Dashboard frames |
| AC05 | PASS | one dominant contextual CTA contract |
| AC06 | PASS | first-run global explanation and Review single empty surface |
| AC07 | PASS | populated/mixed/unknown semantic fixtures and R1B checks |
| AC08 | PASS | Status/Consent summary and fail-closed disclosure contract |
| AC09 | PASS | Review empty/UNKNOWN/PENDING evidence and URL noteDate contract |
| AC10 | PASS | complete G1–G9 matrix in the density contract |
| AC11 | PASS for design/reflow evidence; runtime accessibility NOT_VERIFIED | responsive frames and 200% design requirements |
| AC12 | PASS | official shadcn source-only mapping |
| AC13 | PASS / NOT_APPLICABLE — NONE_DISPATCHED | prior coordinator Impeccable invocation; no workers dispatched |
| AC14 | PASS | production and approved UXR-01/UXR-02 trees untouched |
| AC15 | PASS | completed UXR-03–09 handoff |
| AC16 | PASS | explicit owner approval of R1B image packet and density rules on 2026-10-14 |

The final closure report records publication metadata after Git confirmation. Isolated-preview checks are not production implementation or runtime accessibility claims.

# UXR-02-R1 Technical Delta

> Historical R1 snapshot. Its pending decisions are superseded by the [2026-10-14 approval of R2 + HM-FIX](UXR-02-APPROVAL.md). R1 evidence remains archived.

## What changed

- Added isolated R1 sources: `preview-r1.tsx`, `preview-r1.css`, `vite-r1.config.mjs`, `index-r1.html`, `render-r1.mjs`, and contact-sheet renderer.
- Added six corrected PNGs and an R1 comparison contact sheet under `docs/design/uxr-02/assets/r1/`.
- Corrected the Dashboard topology to the locked reference: side-by-side hero/book Row 1, four KPI Row 2, and the exact three-panel Rows 3–4.
- Added collapsed rail reopen control and retained Status/AI consent entry in expanded, collapsed and mobile states.
- Replaced branding and malformed labels; removed false weekday/date precision.
- Changed dark primary CTA tokens to a light mint surface with dark teal text.
- Stacked mobile book actions to prevent clipped labels.

## What stayed locked

- Direction B — Compact Study Console v1.2.
- Existing routes and consent deep link.
- R0 artifacts and documentation; no prior PNG or source was deleted or overwritten.
- Official shadcn policy and existing canonical Button/Card/Dialog sources.
- No production frontend, backend, database, package or route changes.

## Component provenance

The R1 preview imports the real local canonical `Button` and `Card` modules. The rail, mobile drawer, chart panels, KPI compositions, status/consent shortcuts and book carousel are app-level composition previews. Sidebar, Sheet, Badge, Alert and chart components are mapped in the existing adoption matrix but are not claimed as implemented. No shadcn CLI or dependency install was run.

## Impeccable evidence

The installed local skill at `.agents/skills/impeccable/SKILL.md` (4.5.2) was read. The coordinator ran `.agents/skills/impeccable/scripts/impeccable.cmd context` successfully from the repository root during R1. The selected `layout`, `adapt`, `critique` and `craft-floor` guidance was applied to the reference alignment, row rhythm, responsive stacking, collapsed affordance and labeling. `impeccable detect --json docs/design/uxr-02/assets/source/preview-r1.tsx` returned `[]`.

## Remaining partial verification

- Contrast is visually improved in dark mode but exact WCAG ratios are not asserted without runtime contrast tooling.
- Browser screenshots do not prove focus trapping, Escape behavior, active route semantics, history, screen-reader announcements or production component behavior.
- The preview uses synthetic chart/book data and CSS equivalents; it does not assert future Dashboard APIs.
- Owner visual approval remains pending.

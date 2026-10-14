# UXR-02-R2 Technical Delta

## Preview-only changes from R1

- Added isolated `preview-r2.tsx` and `preview-r2.css`; R1 sources remain intact.
- Added R2 Vite entry, renderer, checker and contact-sheet source.
- Adjusted desktop Row 1 to a reference-like `.92fr / 1.08fr` hero/book balance.
- Reworked KPI internals into icon-left + label/value/subtext/trend composition.
- Added y-axis/gridline/date annotation to the due chart, month controls and denser 15-column heatmap, three-state donut legend, and a jagged multi-point SVG 14-day series with y-axis/tooltip.
- Added explicit collapsed-rail links to `/status` and `/status#ai-consent` with visible labels and accessible titles.
- Added `1 / 5 · 5 sách gần nhất` carousel semantics, full-page mobile/desktop captures and disclosure-footer watermark.
- Corrected stale `Luyện tập` / `Quyền gửi dữ liệu AI` labels and clarified that the UXR-02 handoff is proposed, not frozen.

## Final heatmap-only refinement

- Added versioned `preview-final.tsx`/`preview-final.css` on top of the unchanged R2 shell source.
- Replaced the two-extreme heatmap legend with exactly five levels (0–4) and provisional count thresholds `0`, `1–2`, `3–5`, `6–9`, `10+`.
- Added date/count/description tooltips for pointer hover and keyboard focus, a confirmed-zero state, an explicit striped unverified state, roving grid keyboard movement, Escape dismissal and mobile tap selection.
- Added final PNGs and isolated render/check scripts under `assets/final/` and `assets/source/`.

## Provenance honesty

The preview imports real local canonical `Button` and `Card` implementations and the local `index.css` for the isolated render. The sidebar, mobile drawer, KPI/chart compositions, carousel, badge, status shortcuts and SVG charts are app-level preview compositions. Official Sidebar, Breadcrumb, Sheet, Collapsible, Separator, Badge, Alert, Field, Skeleton, Tooltip and Dropdown Menu remain mapped proposals in the existing adoption matrix; none is claimed as production implemented. No shadcn CLI, registry install, dependency change or canonical component overwrite occurred.

## Verification

- `.agents/skills/impeccable/scripts/impeccable.cmd context` ran successfully for this correction session.
- Selected local guidance: `layout.md`, `adapt.md`, `critique.md`, `craft-floor.md`.
- `impeccable detect --json docs/design/uxr-02/assets/source/preview-r2.tsx` and the edit hook returned `[]`.
- Isolated Vite preview rendered with installed Chrome at exact CSS sizes; `render-r2.mjs` produced 8 PNGs.
- `check-r2.mjs` covered six representative viewport/state cases and returned `issues: []` for overflow, disclosure, lower-section presence and malformed-label scan.
- PNG header inspection confirms requested viewport dimensions for fixed captures; full-page captures intentionally exceed viewport height to prove lower content.

## Partial / unverified items

| Item | Status |
|---|---|
| Visual reference fidelity | `OWNER_APPROVED_DESIGN`; exact pixel equivalence is not claimed. |
| Dark-mode contrast | `PREVIEW_MEASURED`: tooltip text/card 15.93:1, muted legend/card 8.62:1, level-4 swatch/card 9.34:1. Production token and runtime validation remain pending. |
| Keyboard, focus return/trap, history/deep links, screen reader | `UNVERIFIED`; screenshots cannot prove runtime behavior. |
| 200% zoom and real device gestures | `UNVERIFIED`; design proposal only. |
| Synthetic charts/book/activity values | `HONEST_SYNTHETIC_FIXTURE`; no API or production-data claim. |
| Owner approval / foundation freeze | `OWNER_APPROVED_DESIGN`; UXR-02A execution remains unauthorized. |
| Final heatmap visual approval | `OWNER_APPROVED_DESIGN`; publication gates determine full task closure. |

# UXR-02 — Final Heatmap Refinement

**Task:** UXR-02
**Baseline:** UXR-02-R2 + HM-FIX, owner approved 2026-10-14
**Status:** `OWNER_APPROVED / LOCKED`
**Scope:** heatmap widget only; AppShell, dashboard hierarchy and all other R2 visuals remain locked.

## Locked reference and boundary

The final preview continues to use [`dashboard-overview.png`](assets/references/dashboard-overview-owner-root.png) as the composition contract. The correction is limited to `Lịch sử học`. It does not change sidebar geometry, header/breadcrumbs, branding, row order, hero, carousel, KPIs, other charts, theme direction or CTA hierarchy.

The independent R2 review chain remains preserved. The detailed Dashboard behavior and real historical-data integration remain future UXR-09/production implementation scope.

## Five-level activity contract

Exactly five levels are shown, including zero:

| Level | Provisional fixture threshold | Light token | Dark token | Meaning |
|---:|---|---|---|---|
| 0 | `0` activities | `#E7EFEF` | `#1B3438` | Confirmed zero recorded activity |
| 1 | `1–2` | `#C8E8E0` | `#27544F` | Lowest nonzero activity |
| 2 | `3–5` | `#91D2C2` | `#337E70` | Low-to-moderate activity |
| 3 | `6–9` | `#48AD98` | `#42AD96` | High activity |
| 4 | `10+` | `#087D76` | `#7CDEC0` | Highest activity |

The thresholds are approved deterministic design proposals, not backend contracts. The fixture uses nonnegative integer counts. `null`/unavailable history is not coerced to level 0: the preview renders a striped, dashed cell with an explicit unverified label. This is a separate data-availability treatment, not a sixth intensity level.

## Legend

The panel footer uses the compact reference placement:

`Ít  [level 0] [level 1] [level 2] [level 3] [level 4]  Nhiều`

All five swatches are equal size and ordered from neutral/light to dark/saturated teal. The legend has an accessible label naming each level and does not add controls.

## Tooltip and interaction schema

Each day is a focusable calendar-grid cell. Its accessible name and tooltip contain:

1. Full Vietnamese weekday/date, generated from the fixture date in UTC.
2. Daily count and short description, for example `12 hoạt động học tập`.
3. For zero: `Không có hoạt động được ghi nhận`.
4. For unavailable history: `Dữ liệu lịch sử chưa có sẵn hoặc chưa được xác minh` and an explicit note that it is not level 0.

Desktop pointer hover and keyboard focus show the anchored compact tooltip. A focused cell has a visible outline and subtle scale emphasis. `Escape` dismisses the tooltip; moving between cells updates it. The isolated grid uses roving `tabIndex`, Arrow keys, Home/End, and Enter/click without creating a page-level keyboard trap.

On touch, tapping a cell selects it and keeps the popover visible within the panel; tapping another cell updates it and `Đóng` dismisses it. The preview honors `prefers-reduced-motion: reduce` by removing the cell transition.

## Evidence

- [Final dashboard light, 1440×900](assets/final/uxr02-final-dashboard-1440-light.png)
- [Heatmap default](assets/final/uxr02-final-heatmap-default.png)
- [Desktop hover](assets/final/uxr02-final-heatmap-hover.png)
- [Confirmed zero tooltip](assets/final/uxr02-final-heatmap-zero-activity.png)
- [Dark-theme tooltip](assets/final/uxr02-final-heatmap-dark.png)
- [Mobile tap popover](assets/final/uxr02-final-heatmap-mobile-tap.png)

The targeted HM-FIX packet corrects the final preview’s date labels, cell-relative tooltip placement and cell-border cascade without changing the approved composition: [HM-FIX report](UXR-02-HM-FIX-REPORT.md), [HM-FIX dashboard](assets/final/hm-fix/uxr02-hm-fix-dashboard-1440-light.png), [HM-FIX default](assets/final/hm-fix/uxr02-hm-fix-heatmap-default.png), [left hover](assets/final/hm-fix/uxr02-hm-fix-hover-left.png), [center hover](assets/final/hm-fix/uxr02-hm-fix-hover-center.png), [right/bottom hover](assets/final/hm-fix/uxr02-hm-fix-hover-right-bottom.png), [zero tooltip](assets/final/hm-fix/uxr02-hm-fix-zero-activity.png), [dark](assets/final/hm-fix/uxr02-hm-fix-dark.png), and [mobile tap](assets/final/hm-fix/uxr02-hm-fix-mobile-tap.png).

All images are browser-rendered `DESIGN_MOCKUP` evidence using synthetic fixtures. The isolated sources are [`preview-final.tsx`](assets/source/preview-final.tsx), [`preview-final.css`](assets/source/preview-final.css), [`render-final.mjs`](assets/source/render-final.mjs), [`render-final-mobile.mjs`](assets/source/render-final-mobile.mjs), and [`check-final.mjs`](assets/source/check-final.mjs).

## Component provenance and remaining gates

The preview reuses the existing local `Button`/`Card` imports through the R2 source. The calendar grid and tooltip are app-level isolated composition code. Official shadcn/ui `Tooltip` or `Popover` is the proposed production mapping, but neither is claimed as installed or imported by this preview; no dependency or canonical component was changed.

## Impeccable evidence

The installed local skill `.agents/skills/impeccable/SKILL.md` version 4.5.2 was read again for this refinement. `.agents/skills/impeccable/scripts/impeccable.cmd context` completed successfully from the repository root. The `layout`, `adapt`, `critique` and `craft-floor` guidance was applied to compact legend rhythm, anchored tooltip placement, reduced-motion behavior and keyboard/touch affordances. `impeccable detect --json` on `preview-final.tsx` and `preview-final.css` returned `[]`.

Browser checks confirmed five swatches, deterministic level counts, date/count tooltip content, keyboard dismissal path, mobile selection, dark rendering and no overflow at the tested 1440px/390px states. These checks do not prove production routing, screen-reader output, WCAG ratios, real touch behavior or backend data semantics. Owner approval of R2 + HM-FIX was explicitly granted on 2026-10-14; publication gates are tracked separately in the [closure report](UXR-02-FINAL-CLOSURE-REPORT.md).

For this isolated preview, calculated WCAG relative luminance ratios are: dark tooltip text `#F2FFFB` on `#0B2328` **15.93:1**; dark muted legend text `#B5C8C9` on card `#122A30` **8.62:1**; level-4 swatch `#7CDEC0` on card `#122A30` **9.34:1**. These are preview-token measurements only, not production conformance evidence.

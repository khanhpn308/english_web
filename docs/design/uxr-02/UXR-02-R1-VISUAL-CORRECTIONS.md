# UXR-02-R1 Visual Corrections

> Historical R1 snapshot. Its pending decisions are superseded by the [2026-10-14 approval of R2 + HM-FIX](UXR-02-APPROVAL.md). R1 evidence remains archived.

**Task:** UXR-02-R1
**Parent:** UXR-02
**Status:** `OWNER_VISUAL_APPROVAL_PENDING`
**Correction version:** `UXR-02-R1 v1.0`
**Design direction:** Direction B — Compact Study Console v1.2
**Reference:** [`dashboard-overview.png`](assets/references/dashboard-overview-owner-root.png) — locked primary visual contract.

## Scope

This is a targeted correction pass. R0 images, source files and documentation remain preserved. R1 creates a separate preview source and versioned assets; it does not reopen the A/B direction decision, redesign the approved Dashboard concept, or authorize production implementation.

## Locked reference alignment

The corrected desktop frame follows the root reference structure:

- **Row 1:** side-by-side `Việc cần làm hôm nay` hero and one-book `Sách học gần đây` carousel.
- **Row 2:** exactly four compact KPI cards: `Thẻ đến hạn`, `Chuỗi học`, `Độ chính xác trắc nghiệm`, `Writing tự chấm`.
- **Row 3:** `Thẻ đến hạn 7 ngày tới`, `Lịch sử học`, `Kết quả làm bài`.
- **Row 4:** `Tiến độ 14 ngày`, `Kỹ năng cần củng cố`, `Hoạt động gần đây`.

No duplicate book-progress panel, extra carousel book or new dashboard metric is introduced. Values remain `SYNTHETIC_DESIGN_FIXTURE`; no new API claim is made.

## F01–F10 correction mapping

| Finding | Concrete R1 correction | Evidence |
|---|---|---|
| F01 composition drift | Rebuilt the isolated R1 Dashboard topology to match the locked four-row reference, including side-by-side Row 1. | [R1 expanded light](assets/r1/uxr02-r1-dashboard-1440-expanded-light.png) |
| F02 collapsed reopen | Added a visible `PanelLeftOpen` control at the top of the collapsed rail with accessible label `Mở rộng thanh điều hướng`. | [R1 collapsed](assets/r1/uxr02-r1-dashboard-1440-collapsed-light.png) |
| F03 status/AI access | Expanded rail keeps `Trạng thái & quyền AI` and `Quyền AI / AI consent`; collapsed rail retains status and consent icon controls; mobile drawer keeps the full status and consent link. | [R1 collapsed](assets/r1/uxr02-r1-dashboard-1440-collapsed-light.png), [R1 mobile drawer](assets/r1/uxr02-r1-dashboard-390-open-light.png) |
| F04 dark CTA contrast | Dark mode uses a light mint primary surface with dark teal text for the dominant CTA and preserved readable secondary buttons. | [R1 dark](assets/r1/uxr02-r1-dashboard-1440-expanded-dark.png) |
| F05 Vietnamese labels | Corrected labels use `English Web`, `NHẬT KÝ HỌC TẬP`, `Học tập`, `Từ vựng`, `Hệ thống`, `Trạng thái & quyền AI` and the reference Dashboard copy. | All R1 assets |
| F06 date/weekday | Removed false specific weekday/date from the toolbar. The frame now uses the route context `Không gian học / Tổng quan`; chart labels are synthetic period labels. | [R1 expanded light](assets/r1/uxr02-r1-dashboard-1440-expanded-light.png) |
| F07 branding drift | Replaced the R0 `Học từ vựng / Academic Console` mark with the approved `English Web / Nhật ký học tập` tone. | All R1 assets |
| F08 provenance | R1 source imports real local `Button` and `Card`; Sidebar, drawer, Badge, Alert and charts remain explicitly composition previews. | [Technical delta](UXR-02-R1-TECHNICAL-DELTA.md) |
| F09 mobile truthfulness | Mobile stacks only where the viewport requires it; same hero, book, four KPI and analytics hierarchy remains visible. Book CTAs stack to avoid clipping. | [R1 mobile closed](assets/r1/uxr02-r1-dashboard-390-closed-light.png), [R1 narrow](assets/r1/uxr02-r1-dashboard-320-stress-light.png) |
| F10 image labeling | Every R1 screenshot carries a visible `DESIGN_MOCKUP · UXR-02-R1` stamp and synthetic-data disclaimer. | All R1 assets |

## R1 image inventory

| Asset | Viewport/state | Label |
|---|---|---|
| [uxr02-r1-dashboard-1440-expanded-light.png](assets/r1/uxr02-r1-dashboard-1440-expanded-light.png) | 1440×900, expanded, light, primary review | `DESIGN_MOCKUP` |
| [uxr02-r1-dashboard-1440-collapsed-light.png](assets/r1/uxr02-r1-dashboard-1440-collapsed-light.png) | 1440×900, collapsed, light, reopen control | `DESIGN_MOCKUP` |
| [uxr02-r1-dashboard-1440-expanded-dark.png](assets/r1/uxr02-r1-dashboard-1440-expanded-dark.png) | 1440×900, expanded, dark, contrast correction | `DESIGN_MOCKUP` |
| [uxr02-r1-dashboard-390-closed-light.png](assets/r1/uxr02-r1-dashboard-390-closed-light.png) | 390×844, drawer closed | `DESIGN_MOCKUP` |
| [uxr02-r1-dashboard-390-open-light.png](assets/r1/uxr02-r1-dashboard-390-open-light.png) | 390×844, drawer open | `DESIGN_MOCKUP` |
| [uxr02-r1-dashboard-320-stress-light.png](assets/r1/uxr02-r1-dashboard-320-stress-light.png) | 320×568, narrow stress | `DESIGN_MOCKUP` |
| [uxr02-r1-contact-sheet.png](assets/r1/uxr02-r1-contact-sheet.png) | Reference/R0/R1 comparison board | `DESIGN_MOCKUP` board |

## Verification

- Browser-rendered through isolated Vite preview and installed Google Chrome at `C:\Program Files\Google\Chrome\Application\chrome.exe`.
- Six R1 PNGs rendered at exact CSS dimensions, device scale 1.
- R1 source scan: Impeccable detector returned `[]`.
- Responsive browser sweep covered the six R1 states at 1440×900, 390×844 and 320×568; no ordinary horizontal overflow was observed.
- This remains visual design evidence, not production React, router, keyboard, screen-reader or WCAG conformance evidence.

## Known remaining limitations

- The root reference includes richer chart detail and a book-cover image; R1 uses CSS-rendered synthetic equivalents to keep the preview self-contained and offline.
- Exact contrast ratios and focus visibility require runtime implementation validation.
- Collapsed and drawer interactions are visual states; persistence, focus trap and focus return remain unverified runtime behavior.
- Owner approval is still pending. UXR-02A remains unauthorized.

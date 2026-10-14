# UXR-02-R2 — Final Reference Fidelity Correction

**Status:** `OWNER_APPROVED / LOCKED`
**Parent:** UXR-02
**Direction:** Direction B — Compact Study Console v1.2
**Locked reference:** [`dashboard-overview.png`](assets/references/dashboard-overview-owner-root.png) (1672×941; SHA-256 `f60e487b2ad43acf0a8b3d0470b18ccfc69ce3528aaa2417bca1aaf394724511)
**Controlling review:** [`UXR-02-R1-INDEPENDENT-REVIEW-2026-10-13.md`](assets/references/UXR-02-R1-INDEPENDENT-REVIEW-2026-10-13.md)

## Scope

R2 is a narrow fidelity correction. R0 and R1 assets remain unchanged. The four-row Dashboard architecture, Direction B identity, six live navigation destinations, synthetic-data boundary and owner approval gate remain locked. No production source, route, dependency or component registry file changed.

The independent review’s original F01–F10 meanings remain authoritative. R2 uses the review’s P0/P1 labels for the targeted remainder and does not relabel R1’s historical F-codes; the stale R0 label fixes are documentation-only corrections.

## Correction ledger

| Review issue | R2 evidence and status |
|---|---|
| **P0-1 Row 1 proportional fidelity** | **FIXED_VISUALLY.** Desktop Row 1 is approximately reference-like: hero is the supporting 47% region and recent-book is the 53% region; hero actions span the card; book cover, progress and two actions receive comparable weight. Exact pixel matching remains owner judgment. |
| **P0-2 KPI internal layout** | **FIXED_VISUALLY.** Each KPI uses a left icon visual area, label/chevron, dominant metric, supporting denominator and trend line in a consistent side-by-side composition. |
| **P0-3 Chart fidelity** | **FIXED_VISUALLY_FOR_PREVIEW.** Due chart now includes y-axis, horizontal/vertical guides and two-line date labels; heatmap has month navigation and 15-column history; donut retains three-state legend; 14-day chart has jagged multi-point SVG series, y-axis, x-axis labels and tooltip; skills/activity retain structured rows. Values are synthetic. |
| **P0-4 Collapsed sidebar access** | **FIXED_VISUALLY.** Collapsed rail shows separate labeled `Trạng thái` link to `/status` and `Quyền AI` link to `/status#ai-consent`, plus the reopen control. Runtime navigation/tooltips are unverified. |
| **P1-1 Carousel semantic fidelity** | **FIXED_VISUALLY.** One book is visible; header reads `1 / 5 · 5 sách gần nhất`; five dots and previous/next controls communicate the five-book set. |
| **P1-2 Mobile evidence completeness** | **FIXED_WITH_EVIDENCE.** Full-page 390px and 320px captures show Rows 1–4 and the synthetic disclosure; drawer-open evidence remains a separate 390px state. |
| **P1-3 Watermark placement** | **FIXED_VISUALLY.** `DESIGN_MOCKUP · UXR-02-R2` is in the non-interactive disclosure footer rather than fixed over controls. |
| **P1-4 Documentation consistency** | **FIXED_IN_R2_PACKET.** R2 retains original issue meanings, removes stale mojibake in navigation/approval/handoff docs, and does not claim owner approval or blanket pass. |
| **P1-5 Evidence completeness** | **FIXED_FOR_REVIEW.** R2 includes TSX/CSS/index/Vite/render/check/contact-sheet sources in `assets/source/`; provenance remains explicit. |

## Locked structure check

- Row 1: `Việc cần làm hôm nay` + `Sách học gần đây` side-by-side.
- Row 2: exactly `Thẻ đến hạn`, `Chuỗi học`, `Độ chính xác trắc nghiệm`, `Writing tự chấm`.
- Row 3: `Thẻ đến hạn 7 ngày tới`, `Lịch sử học`, `Kết quả làm bài`.
- Row 4: `Tiến độ 14 ngày`, `Kỹ năng cần củng cố`, `Hoạt động gần đây`.
- No duplicate progress-by-book panel and no second visible carousel book.

## Evidence inventory

See the [R2 contact sheet](assets/r2/uxr02-r2-contact-sheet.png) and [contact-sheet source](assets/r2/contact-sheet.html). Direct full-resolution images:

- [Desktop expanded light](assets/r2/uxr02-r2-dashboard-1440-expanded-light.png)
- [Desktop collapsed light](assets/r2/uxr02-r2-dashboard-1440-collapsed-light.png)
- [Desktop expanded dark](assets/r2/uxr02-r2-dashboard-1440-expanded-dark.png)
- [Mobile closed top](assets/r2/uxr02-r2-dashboard-390-closed-light-top.png)
- [Mobile closed full page](assets/r2/uxr02-r2-dashboard-390-closed-light-full.png)
- [Mobile drawer open](assets/r2/uxr02-r2-dashboard-390-open-light.png)
- [320px stress full page](assets/r2/uxr02-r2-dashboard-320-stress-light-full.png)
- [Desktop full page](assets/r2/uxr02-r2-dashboard-1440-expanded-light-full.png)

Every image is a browser-rendered `DESIGN_MOCKUP`; values are synthetic fixtures and do not assert current learner data or future APIs.

## Remaining limitations

Exact contrast ratios, keyboard/focus trap behavior, route history, tooltip announcement, screen-reader output, real component runtime behavior and 200% zoom remain unverified implementation gates. R2 + HM-FIX is owner approved and frozen for design handoff; UXR-02A execution remains separately unauthorized.

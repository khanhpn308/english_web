# UXR-02 Approved Handoff to UXR-02A

**Frozen version:** UXR-02-R2 + HM-FIX
**Owner approval:** 2026-10-14; [conversation approval record](UXR-02-APPROVAL.md)
**UXR-02A state:** `PREPARED / READY_FOR_OWNER_EXECUTION_AUTHORIZATION`
**Next allowed action:** UXR-02A preparation only. Its execution requires a separate owner instruction.

## Frozen foundation

1. Direction B — Compact Study Console v1.2; English Web / Nhật ký học tập branding.
2. R2 desktop expanded 210px dark teal rail by default; user-collapse to 76px rail; visible reopen control; independent Status and AI consent access.
3. Header 54px with contextual breadcrumb; mobile 58px header/menu trigger; drawer at narrow widths. Long labels wrap; focus trap/Escape/return and safe areas remain implementation requirements.
4. Three displayed R2 groups: Học tập (overview/review/quiz), Từ vựng (lookup/search), Hệ thống (status/consent). Future logical Practice/Library seams stay hidden until shipped.
5. Nine route invariants: `/`, `/lookup`, `/search`, `/word-forms/:id`, `/review`, `/quiz/new`, `/quiz/:attemptId`, `/quiz/:attemptId/result`, `/status`. Preserve `/status#ai-consent`, active parents, URL filters/cursors, history/deep links, draft and ETag semantics.
6. [Approved R2 tokens and typography](UXR-02-FOUNDATION-SPEC.md); Segoe UI/Arial offline stack, teal light/dark identity and text/icon state distinctions.
7. Console/full workspace; reading 720–840px; focused study 680–800px; responsive forms. Skip link, one h1 and focus/live-announcement contracts remain.
8. Official shadcn/ui source only; reuse canonical Button/Card/Dialog. R2 rail/drawer/calendar/chart code is isolated composition; no installed Sidebar/Sheet/Tooltip/Popover claim. See [adoption matrix](UXR-02-SHADCN-ADOPTION-MATRIX.md).

## Locked Dashboard contract

- Row 1: today's task + one-book recent-books carousel, side-by-side on desktop; one of five books per frame.
- Row 2: four KPIs, in order: due cards, streak, quiz accuracy, writing self-score.
- Row 3: seven-day due workload, study history heatmap, result donut.
- Row 4: fourteen-day progress, skills to strengthen, recent activity.
- No duplicate book-progress panel. UXR-09 owns detailed Dashboard design and actual API/source verification.

## Final HM-FIX heatmap contract

Five total levels: 0 confirmed activities; 1–2; 3–5; 6–9; 10+. Legend `Ít [0] [1] [2] [3] [4] Nhiều`. UNKNOWN/unavailable is separate from zero. Approved synthetic range is 105 consecutive UTC calendar dates from 28/09/2026 through 10/01/2027. Preserve cell-anchored hover/focus/tap information, date/count/description, dismissal, visible focus and no unintended borders in both themes. Thresholds are an approved design proposal, not an established backend contract.

## Approved evidence

[R2 desktop](assets/r2/uxr02-r2-dashboard-1440-expanded-light.png) · [collapsed](assets/r2/uxr02-r2-dashboard-1440-collapsed-light.png) · [dark](assets/r2/uxr02-r2-dashboard-1440-expanded-dark.png) · [mobile drawer](assets/r2/uxr02-r2-dashboard-390-open-light.png) · [mobile full page](assets/r2/uxr02-r2-dashboard-390-closed-light-full.png) · [final HM-FIX Dashboard](assets/final/hm-fix/uxr02-hm-fix-dashboard-1440-light.png) · [heatmap correction report/gallery](UXR-02-HM-FIX-REPORT.md).

## UXR-02A owns

Layout Simplification & Information Density: redundant information/card reduction, contextual primary CTA, consistent learning-screen density, Dashboard first-run/populated adaptations, Review empty-state hierarchy, Status/Consent diagnostic layouts, responsive content-density adjustments and 200% reflow evidence. These screens are not redesigned during closure. UXR-02A must obtain its own image approval before UXR-03–09 execution.

## Remaining implementation requirements

Runtime focus trap/restoration, route/history/consent behavior, screen-reader announcements, all text/state contrast pairs, real touch collision behavior and actual historical/book APIs remain unverified. Synthetic fixture screenshots and limited isolated Chromium tests are not production acceptance. No production code, backend, schema, route or dependency changes are included.

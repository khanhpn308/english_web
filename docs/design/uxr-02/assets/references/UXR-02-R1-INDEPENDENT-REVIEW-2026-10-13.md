# UXR-02-R1 — Independent visual and artifact review

**Material reviewed:** `UXR-02-R1-OWNER-REVIEW.zip` (12 files: six corrected screenshots, one contact sheet, one owner reference PNG, three Markdown files, one HTML file). **Verdict:** `NEEDS_TARGETED_R2`; not `DONE`, not owner approved. No production behavior was assessed.

## Reference verification

`dashboard-overview.png`: 1672×941, SHA-256 `f60e487b2ad43acf0a8b3d0470b18ccfc69ce3528aaa2417bca1aaf394724511`. This **matches** the R1 report's reference, so R1 used the requested project-root reference. The older UXR-01 approved Dashboard file has a different SHA; there is no reason to silently substitute it.

## Direct visual findings

| Ref | Verdict | Evidence and correction |
|---|---|---|
| F01 — original Dashboard drift | **PARTIAL** | Correct four-row topology and side-by-side desktop hero/book, but still divergent internal layouts. Reference Row 1 is approximately 47% hero / 53% book; R1 is ~55% hero / 45% book. R1 hero has excessive unused vertical space, book-cover asset is schematic/small, KPI icon/text arrangement is vertically stacked rather than reference side-by-side. Restore visual proportions, type hierarchy and spacing as closely as possible for 1440 CSS px without altering ordering. Preserve 5-book carousel, one displayed at a time; label should not obscure five-item meaning. |
| F02 — restore collapsed sidebar | **PASS as visible mockup** | Reopen control is visible near upper rail; interaction not tested. |
| F03 — consent shortcut | **PARTIAL / VISUAL GAP** | Mobile drawer includes explicit `Quyền AI / AI consent` at bottom. Expanded rail says `Trạng thái & quyền AI`. In collapsed screenshot, only one system/heartbeat icon is clearly identifiable; cannot distinguish independent `/status#ai-consent` action. Render a separate recognizable consent action and label/tooltip state with intended target. This is not proof that a link fails at runtime; source preview is absent. |
| F04 — dark CTA contrast | **IMPROVED, MEASUREMENT PENDING** | Primary dark CTA now has mint surface and dark text. The ZIP contains no preview CSS/TSX to verify exact component, focus and hover tokens; do not assert WCAG conformance. |
| F05 — malformed Vietnamese in original docs | **PARTIAL** | R1 images and R1-only docs appear corrected, but unchanged R0 `UXR-02-NAVIGATION-IA.md` and `UXR-02-APPROVAL.md` still include `LuyÔn tập` and `Quyền gứi dữ liệu AI` (verified in prior R0 ZIP). Correct only those stale terms in original docs, preserving approval state. |
| F06 — weekday/date | **PASS** | Removed the falsely precise top-bar weekday/date. |
| F07 — branding | **PASS** | English Web / Nhật ký học tập restored. |
| F08 — original mobile analytics hidden | **NOT VERIFIED** | 390×844 and 320×568 viewport screenshots end before most analytics. The visible hierarchy begins correctly, but they cannot prove lower panels remain available below the fold or are not `display:none`. Provide full-page mobile capture or source/media-rule evidence. |
| F09 — original donut legend | **PASS visually** | R1 donut legend now separates correct/incorrect/blank, not MCQ/Cloze/Writing. |
| F10 — premature design freeze | **PARTIAL** | R1 approval remains PENDING, correctly. But the old `UXR-02-HANDOFF-TO-02A.md` still says `Frozen for the next task after owner approval`; clarify it is `PROPOSED_NOT_FROZEN` until explicit owner sign-off. |

## Additional reference-fidelity gaps

1. Heatmap header in the reference uses a calendar/month display and previous/next controls; R1 substitutes a static `7 ngày gần đây` label. Visual contract is not identical.
2. The bar-chart panel in R1 omits reference-style axis/gridline structure; the 14-day line chart is a simplified largely monotonic area chart instead of the reference's multi-point jagged series. This is acceptable as synthetic data only if the owner permits reduced fidelity, not under a **strict** visual reproduction instruction.
3. KPI icons and typography are much smaller and vertically reorganized in R1; row details are difficult to read at natural screenshot size.
4. In the 390×844 and 320×568 images, the fixed `DESIGN_MOCKUP` label overlaps lower content / action areas. Keep the disclosure but reposition it outside interactive content. Mobile breadcrumb at 320 is densely wrapped; simplify contextual chrome without losing current title.
5. Screenshots capture a fixed-height viewport and cut through Row 4 (desktop). That alone does **not** prove scrolling/clipping; request one full-page desktop capture and full-page mobile capture to demonstrate that all lower content exists and is scroll-accessible.
6. Standalone ZIP is not self-contained from the Markdown perspective: it stores image files at `r1/...`, whereas Markdown assumes `assets/r1/...` relative to repository `docs/design/uxr-02/`; the root reference relative link is likewise outside ZIP layout. These links may resolve correctly in the original repository, but not when extracting this ZIP on its own. The ZIP also excludes the R1 TSX/CSS/renderer sources referenced by its technical report, so component imports, responsive CSS and a11y cannot be independently checked from this attachment.

## Finding-ID integrity

The R1 correction document repurposes original review IDs: original F08 = mobile charts hidden; R1 F08 = component provenance. Original F09 = donut legend; R1 F09 = mobile hierarchy. Original F10 = premature freeze; R1 F10 = watermark labeling. Future correction reports must retain the original F01–F10 IDs and classify the three extras separately; `10/10 corrected` is not independently supportable until this mapping is reconciled.

## Recommended narrow R2

Do not redesign. Tighten primary desktop reference fidelity (proportions, KPI internal placement, row 3/4 chart anatomy), expose distinct consent shortcut in the collapsed rail, prevent watermark/action overlap, provide full-page mobile and desktop evidence, reconcile original F08–F10 and stale Markdown labels, and include preview TSX/CSS within the review package. Preserve R0/R1 images, original structure, locked data/permissions limits, official shadcn provenance and UXR-02 status `OWNER_VISUAL_APPROVAL_PENDING`. Do not change production files or commit/push before owner approval.

**Scope of conclusion:** Visual inspection and static Markdown/ZIP analysis only. Local browser scans, real routes, keyboard behavior, Gitleaks and WCAG were not independently rerun.

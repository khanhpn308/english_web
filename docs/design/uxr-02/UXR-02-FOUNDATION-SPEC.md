# UXR-02 Foundation Specification

**Status:** `OWNER APPROVED / DESIGN LOCKED / PUBLICATION PENDING`
**Version:** `UXR-02-R2 + HM-FIX`
**Direction:** **B - Compact Study Console v1.2**
**Scope:** design-only proposal; no production implementation authorization.

## Readiness and boundaries

UXR-01 is verified as `DONE / DESIGN_DECISIONS_APPROVED / PUBLISHED`. Direction B, the expanded/collapsible desktop sidebar, mobile drawer, cool teal palette, compact density, separate Dashboard Overview reference, official shadcn source policy and one-primary-action hierarchy are owner-approved. D5 is deferred to UXR-06; D7 remains future/unapproved. UXR-00 remains partial with explicit blockers; its final handoff and targeted G7/G9 evidence are preserved in the UXR-01 package.

The owner approved UXR-02-R2 + HM-FIX on 2026-10-14 in the current conversation. See [approval](UXR-02-APPROVAL.md). UXR-02A execution and production changes remain unauthorized.

## Shared shell composition

1. **Skip link** - first tab stop, jumps to `#main-content`.
2. **Sidebar** - dark teal, grouped v1 destinations, expanded by default on wide screens; user-toggleable to icon rail. The rail never becomes the only way to discover a label: tooltips/accessible names are required in implementation.
3. **Compact header** - local readiness pill, route title, local avatar placeholder; mobile menu trigger replaces the rail.
4. **Breadcrumb** - one concise contextual path within the compact R2 header. Detail, quiz runner and result routes retain parent active state.
5. **Main content** - one `h1`, route content and one dominant contextual action.
6. **Global status** - persistent text-labelled local/AI state; `UNKNOWN` is not rendered as healthy.
7. **Mobile drawer** -> Sheet/Sidebar composition with focus trap, Escape close and focus restoration to the menu trigger.
8. **Loading/error/unknown placement** - per-panel skeletons; blocking errors in an alert region near the affected action; consent remains reachable from Status and the shell shortcut.

### Archived alternatives shown before R2 refinement

| Variant | Composition | Evidence | Trade-off |
|---|---|---|---|
| **A -> Header-context rail** | 272px rail; taller 86px header; title and date carry more context; breadcrumb remains below. | [A Dashboard 1440](assets/uxr02-v1-alt-a-dashboard-1440-expanded-light.png), [A collapsed](assets/uxr02-v1-alt-a-dashboard-1440-collapsed-light.png) | More orientation context, less vertical room for the first content fold. |
| **B -> Compact command rail** | 256px rail; 76px header; date/section eyebrow and title stay compact; breadcrumb carries route context. | [B Dashboard 1440](assets/uxr02-v1-alt-b-dashboard-1440-expanded-light.png), [B detail](assets/uxr02-v1-alt-b-detail-1440-light.png) | More content in the initial fold and clearer continuity across Dashboard, detail and focus mode. Historical recommendation; superseded by approved R2. |

These archived variants are not the final approved version. The selected R2 shell has a 210px expanded rail, 76px collapsed rail, 54px desktop header and contextual breadcrumb within that header. Below 801px the rail is replaced by a mobile drawer with 58px header. R2 widths and typography are taken from the actual preview; later density adaptations remain UXR-02A decisions.

## Dashboard composition boundary

The Dashboard frame in the preview is only a shell demonstration of the separately approved reference. Its hierarchy is preserved exactly: **Row 1** today's learning action plus a single-book recent-books carousel; **Row 2** four compact KPI cards; **Row 3** seven-day due workload, learning heatmap and result donut; **Row 4** fourteen-day progress, skills to strengthen and recent activity. The book, historical charts and activity values are `SYNTHETIC_DESIGN_FIXTURE` / `FUTURE_DATA_CONTRACT_REQUIRED` as classified by UXR-01. UXR-02 does not authorize new metrics or APIs.

The final heatmap refinement is documented separately in [`UXR-02-FINAL-HEATMAP-REFINEMENT.md`](UXR-02-FINAL-HEATMAP-REFINEMENT.md). It preserves the panel position and proposes five contribution levels including zero, deterministic synthetic thresholds, anchored tooltips and keyboard/touch behavior. Real historical-data integration remains future UXR-09/production scope.

## Responsive contract proposal

| Width | Shell proposal |
|---|---|
| `>=1200px` | Expanded rail by default; content max measure 1380px; optional collapse persists per session. |
| `1024-1199px` | Rail remains available; content cards reduce columns and wrap long Vietnamese labels. |
| `768-1023px` | Header menu trigger may replace persistent rail; content remains one or two readable columns. Focus mode becomes single-column. |
| `<=767px` | Drawer closed by default, menu trigger in header, one-column content. Drawer width <=84vw and safe-area padding. |
| `320px` | No ordinary horizontal scroll; stacked actions, 2-column KPI only when labels fit, otherwise one column. |
| `200% zoom` | Treat as effective narrow CSS width: reflow to one column, keep focus visible, avoid fixed-height cards, preserve action order. Browser verification remains pending. |

Scroll belongs to the workspace/main region; the sidebar is independently stable on desktop. On mobile, the drawer backdrop locks background interaction while open. Long labels wrap inside the content column, never into an unbounded horizontal strip.

## Approved R2 visual tokens (design contract; no production CSS change)

| Role | Light | Dark | Boundary |
|---|---|---|---|
| background | `#EFF5F6` | `#09191F` | R2 workspace |
| foreground | `#182D52` | `#EDF7F4` | R2 text |
| surface/card | `#FFFFFF` | `#122A30` | Panels |
| surface secondary | `#F7FBFB` | `#10242A` | Subordinate surfaces |
| muted | `#7180A0` | `#B5C8C9` | Metadata; production contrast gate remains |
| border | `#D8E3EC` | `#29474C` | Separators |
| primary / text | `#087D76` / `#FFFFFF` | `#A8F0D8` / `#073B39` | Primary CTA |
| primary hover | `#06645F` | `#89DBC0` | Preview hover |
| accent | `#A6E1D5` | `#24695F` | Supporting emphasis |
| focus ring | `#076E68` | `#B6F7E0` | 2px outline + offset |
| sidebar/status rail | `#0D3036` | `#0D3036` | Active rail `#1B4B53` |
| destructive data | `#FF5D68` | `#FF5D68` | Text/icon required |
| success data | `#46BA98` | `#46BA98` | Never infer UNKNOWN as READY |
| warning data | `#FF9C40` | `#FF9C40` | Label and icon |
| unknown/status | striped/unverified label | striped/unverified label | Not intensity level zero; see heatmap contract |

Offline font stack: Segoe UI, Arial, sans-serif. Actual R2 sizing: hero heading 30px, panel heading 15px, button 12–14px, metadata 9–11px; mobile hero 25px. R2 cards use 8px radius, buttons 5px; semantic focus/read/form widths and reduced-motion requirements remain as below. These are approved visual foundation values, not a replacement for future screen-level density/accessibility validation.

HM-FIX heatmap tokens, date interval, thresholds and interaction design are locked in [final heatmap contract](UXR-02-FINAL-HEATMAP-REFINEMENT.md). No production implementation is implied.

### State rules

- Selected/active: rail + text + icon shape; never color alone.
- Focus: visible ring around the actual focus target; never clipped by card overflow.
- Disabled: lower contrast plus disabled semantics and explanatory text where consequential.
- Loading: skeleton preserves content geometry and `aria-busy`; no full-screen spinner after shell render.
- `READY`, `DEGRADED`, `UNKNOWN`, `NOT_READY`, empty and zero are text-labelled and icon-paired.
- Reduced motion: disable drawer easing, carousel autoplay and decorative transitions under `prefers-reduced-motion: reduce`.

## Baseline inventory and preserved invariants

| Source file/symbol | Current responsibility | Proposed visual change | Preserved invariant | Evidence |
|---|---|---|---|---|
| `frontend/src/app/AppShell.tsx` `PRIMARY_NAV_ITEMS` | Six horizontal links and active matching | Group in Learning/Vocabulary/Practice/System sidebar; parent active matching for detail/quiz descendants | Same nine routes and same-origin history | [Current capture](assets/current-app-capture/G1-shell-desktop-CURRENT_APP_CAPTURE-1440x900.png) -> [mockup](assets/uxr02-v1-alt-b-dashboard-1440-expanded-light.png) |
| `AppShell` `handleLinkClick` / `navigateSearch` | Push/replace history, focus `h1` | Keep browser semantics; shell only changes presentation | URL state, deep links, back/forward and route focus | Source-only baseline; browser behavior unverified in mockup |
| `AppShell` skip link/live region | Accessible entry and announcements | Keep first stop and visible focus treatment | `#main-content`, `h1` focus, polite status | `SOURCE_ONLY_BASELINE`; implementation gate remains |
| `frontend/src/app/shell.css` | Body reset and title/placeholder spacing | No production edit; map reset into future scoped shell tokens | No Tailwind Preflight replacement | Read-only inspection |
| `frontend/src/index.css` | Semantic CSS variables and Tailwind layers | Candidate token mapping only | Existing no-Preflight contract | Read-only inspection |
| `Button`, `Card`, `Dialog` | Canonical shadcn/Radix primitives | Reuse in preview/implementation plan | No overwrite or duplicate primitive | Isolated preview imports `Button` and `Card`; `Dialog` is conceptual in status frame |
| Dashboard route | Current summary and existing route | Demonstrate owner-approved four-row composition with synthetic fixtures | No claim of future book/history APIs | [Dashboard mockup](assets/uxr02-v1-alt-b-dashboard-1440-expanded-light.png) |

## Content-width modes

- **Console mode:** Dashboard and Status use the full shell workspace up to the max width so compact panels stay scanable.
- **Reading mode:** word detail, examples and long Vietnamese explanatory copy use a narrower 720-840px measure inside the workspace.
- **Focus mode:** Review/Quiz centers one study surface at 680-800px; navigation remains available but visually recedes.
- **Form mode:** Lookup/Search/Edit use a 2-column desktop split only where labels and error copy remain readable; at tablet/mobile they stack.

## Accessibility design considerations and gaps

The design includes skip link, landmarks, one `h1`, text/icon state labels, focus target proposal, drawer close affordance, 44px touch intent and 200% reflow plan. The render sweep proves only that the static mockup has no horizontal overflow in 48 viewport/state combinations. It does **not** prove WCAG conformance, screen-reader semantics, focus trapping, keyboard history behavior, contrast ratios or production React behavior. Those remain implementation and browser/a11y gates.

## Scope handoff

UXR-02A owns screen-level density, Dashboard first-run/populated compactness, duplicate empty-state removal, Review/Status density tuning and final 200% zoom evidence. UXR-09 owns detailed Dashboard chart responsiveness and data-dependency classification. UXR-06 owns quiz runner presentation. No future Library/Book/Progress route is enabled by this packet.

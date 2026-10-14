# UXR-02 Official shadcn/ui Adoption Matrix

**Source policy:** official shadcn/ui catalog and Radix-compatible source only. No CLI, install, overwrite or production component edit occurred in UXR-02.

| Component | Official docs URL | Current source path | Classification | AppShell purpose | Constraint / risk | Owner |
|---|---|---|---|---|---|---|
| Sidebar | https://ui.shadcn.com/docs/components/sidebar | none | `OFFICIAL_PROPOSED` | Desktop groups, collapse, mobile composition | Choose Radix flavor to match existing Dialog; review CLI diff in isolated worktree later | Future implementation owner (separate authorization) |
| Breadcrumb | https://ui.shadcn.com/docs/components/breadcrumb | none | `OFFICIAL_PROPOSED` | Detail/quiz context | Keep one concise path; do not duplicate h1 | AppShell owner |
| Sheet | https://ui.shadcn.com/docs/components/sheet | none | `OFFICIAL_PROPOSED` | Mobile drawer if Sidebar mobile mode is not sufficient | Avoid double overlay/focus handlers; use one owner | AppShell owner |
| Collapsible | https://ui.shadcn.com/docs/components/collapsible | none | `OFFICIAL_PROPOSED` | Optional grouped nav/rail disclosure | Preserve active descendants when collapsed | Navigation owner |
| Separator | https://ui.shadcn.com/docs/components/separator | none | `OFFICIAL_PROPOSED` | Rail/header section boundaries | Decorative separators need no redundant announcement | AppShell owner |
| Button | https://ui.shadcn.com/docs/components/button | `frontend/src/components/ui/button.tsx` | `ALREADY_PRESENT` | CTA, menu, collapse, status actions | Reuse current cva/Radix Slot; no overwrite | UI foundation owner |
| Card | https://ui.shadcn.com/docs/components/card | `frontend/src/components/ui/card.tsx` | `ALREADY_PRESENT` | Dashboard panels, status callouts | Preserve existing radius/no-Preflight behavior | UI foundation owner |
| Dialog | https://ui.shadcn.com/docs/components/dialog | `frontend/src/components/ui/dialog.tsx` | `ALREADY_PRESENT` | Consent disclosure and conflict details | Existing Radix Dialog; focus restoration must remain | Consent owner |
| Badge | https://ui.shadcn.com/docs/components/badge | none | `OFFICIAL_PROPOSED` | Readiness, verification and source labels | Text/icon pair; no color-only semantic | Feature owners |
| Alert | https://ui.shadcn.com/docs/components/alert | none | `OFFICIAL_PROPOSED` | Global status, conflict and blocking errors | Persistent visible copy; `role=alert` only for blocking state | Status owner |
| Input | https://ui.shadcn.com/docs/components/input | none | `OFFICIAL_PROPOSED` | Lookup/search fields | Visible labels, validation and Vietnamese wrapping | Form owner |
| Field | https://ui.shadcn.com/docs/components/field | none | `OFFICIAL_PROPOSED` | Label/help/error grouping | Reconcile with existing form contracts before adding | Form owner |
| Textarea | https://ui.shadcn.com/docs/components/textarea | none | `OFFICIAL_PROPOSED` | Meaning/example/writing fields | Preserve drafts and conflict semantics | Form owner |
| Skeleton | https://ui.shadcn.com/docs/components/skeleton | none | `OFFICIAL_PROPOSED` | Per-panel loading geometry | `aria-busy`; never imply loaded data | Feature owners |
| Tooltip | https://ui.shadcn.com/docs/components/tooltip | none | `OFFICIAL_PROPOSED` | Collapsed rail labels/icon-only controls | Supplement, never replace, accessible name | Navigation owner |
| Dropdown Menu | https://ui.shadcn.com/docs/components/dropdown-menu | none | `DEFERRED` | Possible future theme/utility menu | Not needed for v1 shell; avoid hiding consent/status actions | AppShell owner |

### Preview provenance

The isolated React preview imports the actual local `Button` and `Card` modules. The shell rail, breadcrumb, alert and mobile drawer are **composition previews**; Sidebar, Sheet, Badge and Alert are not claimed as implemented production components. The status consent action is an honest conceptual placement, not a working dialog. `Dialog` remains available from the canonical local source for a later implementation task.

### Acquisition constraints

Future implementation must inspect `components.json`, use the current Radix/new-york/Tailwind v4 setup, add one reviewed component group at a time, record CLI/source diffs and avoid package-lock churn. No third-party registry, `shadcn init --force`, `add --all`, overwrite or dependency installation is authorized by this design packet.

## Approved heatmap mapping

Official [Tooltip](https://ui.shadcn.com/docs/components/tooltip) / [Popover](https://ui.shadcn.com/docs/components/popover) remain OFFICIAL_PROPOSED. HM-FIX uses app-level isolated preview positioning and grid controls; neither primitive is claimed imported. Dashboard feature/data integration stays UXR-09 plus separately authorized production work.

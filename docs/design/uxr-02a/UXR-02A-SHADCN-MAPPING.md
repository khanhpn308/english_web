# UXR-02A shadcn/ui Mapping

**Policy:** official shadcn/ui catalog, Radix-compatible/new-york/Tailwind v4 approach. No CLI, install, overwrite or package-lock change occurred.

| Need | Official source | Local status | UXR-02A use | Provenance/owner |
|---|---|---|---|---|
| Card panels | [Card](https://ui.shadcn.com/docs/components/card) | `ALREADY_PRESENT` at `frontend/src/components/ui/card.tsx` | Dashboard/Review/Status surfaces | local canonical component; UI foundation |
| Primary/secondary actions | [Button](https://ui.shadcn.com/docs/components/button) | `ALREADY_PRESENT` at `frontend/src/components/ui/button.tsx` | one dominant CTA and safe recovery | local canonical component; UI foundation |
| Readiness/state label | [Badge](https://ui.shadcn.com/docs/components/badge) | `OFFICIAL_PROPOSED` | READY, UNKNOWN, LOCAL, synthetic labels | official source; feature owners |
| Progress bar | [Progress](https://ui.shadcn.com/docs/components/progress) | `OFFICIAL_PROPOSED` | book/quiz progress where a denominator exists | official source; Dashboard/Quiz |
| Per-panel loading | [Skeleton](https://ui.shadcn.com/docs/components/skeleton) | `OFFICIAL_PROPOSED` | preserve geometry during loading | official source; feature owners |
| Tabbed result detail | [Tabs](https://ui.shadcn.com/docs/components/tabs) | `OFFICIAL_PROPOSED` | objective vs writing result detail | official source; UXR-07 |
| Diagnostics | [Collapsible](https://ui.shadcn.com/docs/components/collapsible) / [Accordion](https://ui.shadcn.com/docs/components/accordion) | `OFFICIAL_PROPOSED` | Status technical detail, advanced filters | official source; UXR-08 / feature owners |
| Active alert | [Alert](https://ui.shadcn.com/docs/components/alert) | `OFFICIAL_PROPOSED` | blocking error, consent warning, degraded state | official source; feature owners |
| Section boundary | [Separator](https://ui.shadcn.com/docs/components/separator) | `OFFICIAL_PROPOSED` | low-noise grouping | official source; AppShell |
| Consent/reconciliation | [Dialog](https://ui.shadcn.com/docs/components/dialog) | `ALREADY_PRESENT` at `frontend/src/components/ui/dialog.tsx` | future consent/conflict detail | local canonical component; UXR-08/UXR-04 |
| Lookup/search fields | [Input](https://ui.shadcn.com/docs/components/input) | `OFFICIAL_PROPOSED` | labeled compact composer | official source; UXR-03 |
| Date filter | [Date Picker](https://ui.shadcn.com/docs/components/date-picker) | `OFFICIAL_PROPOSED` | Review noteDate filter | official source; UXR-05 |
| Tabular search results | [Table](https://ui.shadcn.com/docs/components/table) | `OFFICIAL_PROPOSED` | Search result density | official source; UXR-03 |
| AppShell navigation | [Sidebar](https://ui.shadcn.com/docs/components/sidebar), [Breadcrumb](https://ui.shadcn.com/docs/components/breadcrumb), [Sheet](https://ui.shadcn.com/docs/components/sheet) | `OFFICIAL_PROPOSED` | R2 rail/drawer contract | no production claim; AppShell implementation task |

## App-level compositions

`MetricTile`, `StatSummary`, `FilterToolbar`, `CompactFormSection`, `EmptyState`, `DisclosureGroup` and `StatusSummary` are future compositions that combine the official primitives above. They are not installed registry components and no React files are created in UXR-02A.

## Provenance rules

- The isolated preview is HTML/CSS and does not import production React components; the frames are conceptual `DESIGN_MOCKUP` evidence.
- `Button` and `Card` are mapped to actual local canonical files for future implementation, but a static preview must not be represented as an installed component execution.
- No third-party registry, `shadcn init`, `add --all`, `add --overwrite`, dependency install or Tailwind preflight change was performed.

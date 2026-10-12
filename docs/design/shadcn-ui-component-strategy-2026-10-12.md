# English Web — Official shadcn/ui component strategy (DESIGN / SOURCE REVIEW ONLY)

**Date:** 2026-10-12
**Owner preference:** Use and compose existing components from the **official** https://ui.shadcn.com/docs/components and install according to https://ui.shadcn.com/docs/installation, to minimize custom UI primitives and lower future upgrade costs.
**Research status:** source-based and official-doc-grounded proposal, **not** authorization to install dependencies, regenerate components, modify app code, or claim accessibility/upgrade PASS.
**Related:** [UI redesign](english-web-ui-ux-redesign-plan-2026-10-12.md), [future content platform](future-learning-content-architecture-2026-10-12.md).

## 1. Source-confirmed baseline, no reinstall needed

Read from actual repository (main baseline `67659eea35202706e0f18e4db9c722b02921cbd0`):

- `components.json` exists at repository **root** with `style: "new-york"`, `rsc: false`, `tsx: true`, Tailwind CSS entry `frontend/src/index.css`, `baseColor: "neutral"`, `cssVariables: true`, `iconLibrary: "lucide"`, and aliases including `@/components/ui`.
- Root `package.json` holds React 19, Vite 8, TypeScript, Tailwind CSS 4, `@tailwindcss/vite`, `@radix-ui/react-dialog`, `@radix-ui/react-slot`, `class-variance-authority`, `clsx`, `tailwind-merge` and `lucide-react`.
- Root `vite.config.ts` sets Vite `root: "frontend"` and `@` alias to `frontend/src`; root `tsconfig.json` has matching TS alias. Use repository root as CLI cwd unless a future reviewed configuration explicitly changes it.
- Existing adopted UI primitives: `frontend/src/components/ui/button.tsx`, `card.tsx`, `dialog.tsx`. Dialog is implemented with **Radix UI**, so select the matching **Radix UI component implementation** for new components. Do not mix a second primitive base (Base UI/React Aria) indiscriminately with the existing Radix components.
- `frontend/src/index.css` deliberately imports Tailwind theme/utilities with `@layer` but not Tailwind Preflight; the repository has specific reset/layout tests. **Do not replace wholesale with `@import "tailwindcss";` from a generic Vite tutorial without a scoped regression review.**
- Current T080/T081 already handled foundation/AppShell styling; installing shadcn/ui afresh, recreating Vite, changing package manager or introducing a new frontend workspace would produce unnecessary risk.

## 2. Grounded official guidance and component acquisition

Authoritative documentation:
- Catalog: https://ui.shadcn.com/docs/components
- Framework setup / **Existing Project**: https://ui.shadcn.com/docs/installation and https://ui.shadcn.com/docs/installation/vite
- CLI `add` and maintenance flags: https://ui.shadcn.com/docs/cli
- `components.json` semantics, aliases and registry: https://ui.shadcn.com/docs/components-json
- Token theming: https://ui.shadcn.com/docs/theming
- Radix Sidebar example: https://ui.shadcn.com/docs/components/radix/sidebar

Official shadcn CLI **adds component source files into the app**. These are locally owned, reviewable components; they are **not automatically updated whenever upstream changes**. Upgrades mean reviewing upstream changes, component diffs, dependency changes and local behavior. Prefer a pinned reviewed CLI version for any repeatable task; the official examples use `@latest` interactively, but automated workers should not float dependency/codegen versions without approval.

**Example commands for a future authorized implementation from repo root, NOT executed in this research:**

```sh
# Review official CLI and registry metadata before writing
npx shadcn@<approved-version> add sidebar --dry-run
npx shadcn@<approved-version> add sidebar --diff

# After owner-scoped implementation approval and dependency review:
npx shadcn@<approved-version> add sidebar
```

Note: `--diff [path]` is a documented CLI option; confirm actual output/behavior for the pinned CLI and chosen component in the worktree. Do not install a package with a fake literal `<approved-version>`; substitute a tested explicit version. `-o/--overwrite` replaces local files and is **prohibited by default**; `-a/--all` is unnecessary. Do not run a blanket `init` or copy the tutorial's CSS/tsconfig scaffold into the established project. Preserve and review `package-lock.json` changes after each addition.

Use the **official shadcn/ui registry by default**. External blocks, community registry items, entire dashboard template projects or unsupported custom packages need distinct owner approval and security/license review.

## 3. Three-tier component architecture

- **Tier 1 — canonical primitives**: `frontend/src/components/ui/` is the sole authoritative copy of installed/approved official shadcn component sources, theme tokens and primitive utilities. Changes require component-owner review because all nine current screens and future book screens may share them.
- **Tier 2 — app-level compositions**: `frontend/src/components/app/` (prospective folder, not currently implemented) may contain reusable `AppSidebar`, `PageHeader`, `ResourceHeader`, `StatusCallout`, `FilterBar`, `FormSection` and `EmptyState` compositions; they import Tier 1, contain no HTTP or SQLite knowledge, and use design tokens.
- **Tier 3 — feature compositions**: `frontend/src/features/<domain>/` composes Tier 1/2 with typed API state and business decisions. Domain-specific interactions remain owned by the existing React containers/hooks and backend; a new shadcn `Input` or `Dialog` must not alter request IDs, quiz snapshots, consent, revision/ETag or idempotency.
- **Future book domain**: Book list/detail, chapter explorer, contextual vocabulary and per-book progress reuse the same tiers. Never copy Button/Input/Card/Sidebar source into each new feature folder.

## 4. Component-to-screen mapping

**Use official component names only as design candidates**. Exact React API/availability is verified against official docs at implementation time. A screen is not required to install every candidate.

| Screen / future module | Preferred official shadcn/ui components | Composition/interaction boundary |
|---|---|---|
| G1 AppShell / IA | **Sidebar**, **Breadcrumb**, **Sheet**, **Collapsible**, **Separator**, **Tooltip**, **Dropdown Menu** | Sidebar groups allow future Book/Library entries; mobile drawer; retain route history, focus and `aria-current` |
| G2 Lookup / AI preview | **Input**, **Button**, **Card**, **Tabs**, **Badge**, **Alert**, **Skeleton**, **Accordion** | Preview is not durable Save; statuses and verified/missing provenance remain explicit |
| G3 Search / Word detail | **Input**, **Input Group**, **Combobox**, **Select**, **Badge**, **Pagination**, **Accordion**, **Scroll Area**, **Empty** | Main search / advanced filters / chips, URL query and cursor restore; use Data Table only if appropriate to result semantics |
| G4 Save / Edit | **Field**, **Input**, **Textarea**, **Button**, **Date Picker**, **Dialog**, **Alert Dialog**, **Alert**, **Accordion** | Date validation; repeatable meaning/example rows; revision-conflict decision and no accidental delete/overwrite |
| G5 Flashcards | **Card**, **Button**, **Progress**, **Badge**, **Tooltip**, **Skeleton** | Reveal, four honest SRS ratings and confirmed mutation state; do not confuse activity progress with mastery |
| G6 Quiz Builder / Runner | **Card**, **Field**, **Input**, **Radio Group**, **Textarea**, **Progress**, **Alert Dialog**, **Badge**, **Skeleton** | Immutable quiz attempt, autosave status, rubric self-score, resume/reconcile and explicit terminal submit |
| G7 Quiz Results / Writing | **Card**, **Progress**, **Badge**, **Accordion**, **Tabs**, **Alert**, **Separator** | Objective accuracy, learner self-score and optional AI advisory feedback must remain distinct |
| G8 Status / Consent / Errors | **Alert**, **Dialog**, **Alert Dialog**, **Accordion**, **Badge**, **Table**, **Skeleton** | Honest DEGRADED/UNKNOWN; consent disclosed and fail closed, accessible diagnostic expansion |
| G9 Dashboard | **Card**, **Progress**, **Chart** (only if data justifies it), **Skeleton**, **Empty**, **Badge** | Default to today’s learning actions rather than decoration or invented trends |
| Future Library / Books | **Card**, **Item**, **Badge**, **Combobox**, **Select**, **Tabs**, **Pagination**, **Data Table** (when warranted), **Accordion** | Skill multi-select, typed IELTS/CEFR filters, catalog browse and book metadata |
| Future Book Contents | **Accordion**, **Sidebar**, **Breadcrumb**, **Scroll Area**, **Tabs**, **Progress** | Chapter/unit hierarchy, edition identity, reading position separate from completion |
| Future Book Exercises | **Radio Group**, **Checkbox**, **Textarea**, **Field**, **Progress**, **Alert Dialog**, **Tabs** | Exercise attempts/versioned source, answer keys, status and evaluation policies |
| Future Book Progress | **Progress**, **Card**, **Chart** (when derived metrics available), **Badge**, **Table** | Known denominator, explicit completion events, no fabricated grade/proficiency |

### Prioritized adoption set for current redesign

**Foundation / P0:** Sidebar, Breadcrumb, Sheet (mobile if not already handled by official Sidebar), Separator, Badge, Alert, Input, Field, Textarea, Skeleton. Existing Button/Card/Dialog remain; check compatibility before adopting updates.

**Feature / P1:** Accordion, Collapsible, Tabs, Select/Combobox, Date Picker, Progress, Radio Group, Tooltip, Alert Dialog. Add only per approved screen where a real interaction needs it.

**Future / on demand:** Data Table, Chart, Calendar, command palettes, large virtualized views and resource-specific UIs. Do not install them solely to prepare for future books.

## 5. Interaction and styling rules for worker agents

1. **Check the official docs for the actual component and primitive flavor** (Radix for this repo) before editing. Favor the existing local component source if it meets screen needs.
2. **Do not independently copy component implementations** from articles or inline web screenshots; use the audited official component registry/CLI or scoped review of source.
3. **Never run `shadcn add --all`, `shadcn add --overwrite`, or `shadcn init --force` in unattended worker jobs.** An overwrite of a specific component may be allowed only as a separately reviewed upgrade with preserved local diffs.
4. Use `components.json` + CSS semantic variables as the source of truth; avoid feature-specific hard-coded color palettes or multiple CSS resets. Light/dark and offline browser font behavior must be deliberately supported.
5. Use shadcn components for widgets, not as a license to replace semantic landmarks (`main`, `nav`, `header`), native focus handling or accessible labels. WCAG 2.2 AA target still needs measured tests and manual keyboard/screen-reader review.
6. Prefer shadcn `Field` and consistent Form feedback patterns over nine bespoke raw `<input>` style strings. Preserve typed DTO validation and user-entered drafts.
7. Icons: use existing `lucide-react`; icon-only buttons require accessible names. Avoid animation that obscures focus or ignores `prefers-reduced-motion`.
8. Use immutable URLs/asset references, no third-party runtime CDN for essential UI and no added cloud dependency: Windows local app and offline study remain first class.
9. Avoid big-bang primitive replacement; one reviewed, non-overlapping worktree per feature; a single integration owner is responsible for shared primitives and theme. No backend, SQLite, OpenAPI or learning-content behavior change without separately scoped authorization.

## 6. Safe future upgrade process

- Keep a registry of each installed component: name, official docs/source reference, primitive flavor, reviewed CLI version, date introduced, local modifications, owner and affected screens.
- Before adding/upgrading: read `components.json`, source in `frontend/src/components/ui`, official docs/change log and compare CLI dry run/diff in an **isolated worktree**. Confirm destination paths and transitive dependencies.
- Upgrade **one compatible group at a time**. Treat migration between Radix/Base UI foundations or Tailwind major resets as separate architectural work, not a routine re-copy.
- Update source and package-lock only after reviewing changed files. No forced overwrite, no blind `@latest` commits, and no unscoped refactor of AppShell or CSS.
- Verify appropriate TypeScript, Vite, component interactions, unit/browser/a11y regressions when execution is authorized. Owner code-first workflow currently defers the broad final audit, but does not authorize asserting a component upgrade is safe without evidence.
- Upstream component source updates are **explicitly managed**, not automatic. The main maintainability benefit is common recognizable API patterns, centralized primitives, source control and scoped upgrade diff review.

## 7. Redesign task dependencies and approval gates

- UXR-01 owner visual direction still pending (Calm Academic Workspace vs Compact Study Console). shadcn/ui is a **component-source choice**, not a mandate for any one aesthetic.
- UXR-02 must now specify an **official shadcn component inventory and adoption list**, existing primitive compatibility, proposed new base tokens, Radix consistent selections, Sidebar IA and future Library nav slots.
- UXR-03–09 must map UI states to an approved shadcn component; any custom widget must justify which official primitive cannot meet the requirement.
- UXR-10 reviews repetition, keyboard/focus/reflow, overflow 320px, auto-save and AI consent status semantics; screenshot-based judgments remain `PENDING VISUAL VERIFICATION` until rendered.
- UXR-11 approves wireframes plus component adoption matrix; then scoped coding worktrees may be planned and dispatched.

**Explicit status:** only source review and documentation updated. No CLI executed; no components downloaded or installed; no code/test/build/audit/Windows actions.
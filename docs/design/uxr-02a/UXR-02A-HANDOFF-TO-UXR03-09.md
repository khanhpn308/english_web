# Draft Handoff from UXR-02A to UXR-03â€“09

**State:** COMPLETE / DESIGN_HANDOFF_READY
**Shared foundation:** `UXR-02-R2 + HM-FIX`
**Density packet:** UXR-02A-R1B / Variant B — Compact Refinement
**Owner decision:** APPROVED 2026-10-14 — see UXR-02A-OWNER-DECISION.md

## Frozen handoff rules

1. Preserve the R2 shell: branding, 210px expanded/76px collapsed desktop rail, 54px header, mobile 58px drawer header, route groups and `/status#ai-consent` access.
2. Preserve Dashboard rows exactly. UXR-09 may refine chart internals and data classification, but may not reorder rows, add a duplicate book-progress panel or invent metrics.
3. Keep one dominant contextual CTA per task context, while retaining save/submit/cancel/consent/retry/reconciliation controls.
4. Keep EMPTY, LOADING, ERROR, SUBMITTING, UNKNOWN, READY, DEGRADED and NOT_READY distinct. Null and unavailable values are not numeric zero.
5. Keep source/evidence limits, conditional revision/ETag conflicts, SRS rating semantics, quiz answer snapshot/autosave/UNKNOWN recovery, objective accuracy vs Writing self-score and AI consent fail-closed behavior.
6. Treat all UXR-02A PNGs as design mockups with synthetic fixtures. They are not production screenshots or implementation acceptance.

## Per-feature ownership

| Future task | Inherit | Owns next |
|---|---|---|
| UXR-03 | G2/G3 compact composer, source/evidence limit, disclosure rule | full Lookup/Search/Word Detail interaction and source fixtures |
| UXR-04 | G4 compact form, one Save CTA, conflict visibility | Save/Edit forms, audio and revision conflict flows |
| UXR-05 | G5 toolbar, one empty surface, UNKNOWN reconciliation rule | complete Flashcards/reveal/rating design |
| UXR-06 | G6 compact composer, progress/autosave hierarchy | full Quiz Builder/Runner behavior and accessibility |
| UXR-07 | G7 objective/Writing separation and disclosure | result/feedback content and provider advisory states |
| UXR-08 | G8 readiness-first summary, consent deep-link and fail-closed copy | detailed consent, errors, alerts and diagnostics interaction |
| UXR-09 | G9 locked rows, semantic metrics, responsive density | detailed Dashboard chart behavior and data dependency classification |

## Release gate for this handoff

Before dispatching any downstream design task, the owner must explicitly approve a named Dashboard variant and the density contract in [`UXR-02A-OWNER-DECISION.md`](UXR-02A-OWNER-DECISION.md). A requested change creates a new packet version and new screenshots; prior approval is not reused. No production implementation, PR merge or UXR-03â€“09 execution is authorized by this draft.

## Completed handoff closure (2026-10-14)

### Approved design reference

- Approved release: UXR-02A-R1B.
- Selected design: Variant B — Compact Refinement.
- Approval authority/date: Project owner, 2026-10-14.
- Inherited foundation: UXR-02-R2 + HM-FIX.
- Heatmap requirement: A12 square cells and centered square composition, preserving 105 dates, five levels, zero versus UNKNOWN and approved focus/hover/tap semantics.
- Decision record: [UXR-02A-OWNER-DECISION.md](UXR-02A-OWNER-DECISION.md).
- Gallery and correction evidence: [UXR-02A-VISUAL-GALLERY.md](UXR-02A-VISUAL-GALLERY.md), [R1B owner review](UXR-02A-R1B-OWNER-REVIEW.md), [R1B correction report](UXR-02A-R1B-FINAL-CORRECTION-REPORT.md).

### Frozen G1–G9 density and safety contracts

The complete matrix remains in [UXR-02A-DENSITY-CONTRACT.md](UXR-02A-DENSITY-CONTRACT.md). It defines each group's primary task, one context-valid dominant action, essential first view, secondary information, always-visible critical state, allowed disclosure, official component candidate and future owner. It also preserves compact G2 Lookup and G6 Quiz examples and the future app-level MetricTile, StatSummary, FilterToolbar, CompactFormSection, EmptyState, DisclosureGroup and StatusSummary contracts.

Frozen cross-screen rules:
- Preserve the R2 AppShell, route groups, /status#ai-consent, Dashboard four-row order, one-book carousel and Variant B internal spacing.
- Keep one dominant contextual CTA while retaining Save, Submit, Cancel, consent grant/revoke, retry and reconciliation controls.
- Distinguish EMPTY, LOADING, ERROR, SUBMITTING, UNKNOWN, READY, DEGRADED and NOT_READY; null and unavailable values are not zero.
- Preserve local learning when optional AI is unavailable, fail-closed consent, Review noteDate filtering and pending/UNKNOWN mutation reconciliation.
- Preserve objective quiz accuracy versus Writing self-score, durable save and source revision/ETag conflicts, source provenance and honest synthetic-data labels.
- Keep active alarms and essential privacy disclosures visible; diagnostics use named progressive disclosure.
- Require readable long Vietnamese content, focus visibility, contrast, mobile reflow and effective 200% zoom without ordinary horizontal overflow. These remain design requirements until production verification.

### Exact downstream ownership

- UXR-03: Lookup, AI Preview, Search and Word Detail design.
- UXR-04: Save and Edit Vocabulary design.
- UXR-05: Review Flashcards design.
- UXR-06: Quiz Builder and Runner design.
- UXR-07: Quiz Results and Writing Feedback design.
- UXR-08: Status, Consent and Error States design.
- UXR-09: Dashboard feature-level design.

UXR-03–09 inherit this approved density packet and frozen foundation. Feature-specific exceptions require documented rationale and owner approval where required. No downstream task is executed or production implementation authorized in this session.

### Evidence limitations

UXR-00 remains PARTIAL_WITH_EXPLICIT_BLOCKERS; its evidence gaps are carried forward. This handoff differentiates DESIGN_APPROVED, SOURCE_CONFIRMED, ISOLATED_PREVIEW_VERIFIED and NOT_VERIFIED_IN_PRODUCTION. The R1B packet is browser-rendered design evidence with synthetic fixtures. It does not claim production React, backend, screen-reader, real-device mobile or runtime accessibility verification.

### Handoff readiness

| Field | Status |
|---|---|
| UXR02A_HANDOFF | COMPLETE |
| UXR03_09_DESIGN_DEPENDENCY | SATISFIED |
| UXR03_09_PRODUCTION_IMPLEMENTATION | NOT_AUTHORIZED |

UXR-03 through UXR-09 may now proceed with their separate DESIGN tasks after their own execution authorizations. Do not execute them from this closure session.

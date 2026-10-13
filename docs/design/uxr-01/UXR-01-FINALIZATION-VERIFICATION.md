# UXR-01 finalization verification — 13/10/2026

**Final status:** APPROVED_DESIGN / SECURITY_PASS / GIT_INTEGRATION_PENDING  
**Selected direction:** B — Compact Study Console v1.2  
**Owner decision provenance:** Explicit approval in the English Web ChatGPT project conversation, 13/10/2026. No public URL, exact time or literal quotation is asserted.

## Owner decisions

D1, D2, D3, D4, D6, D8 and D9 are approved. D5 is DEFERRED_TO_UXR06. D7 is FUTURE_UNAPPROVED. The complete alternatives, references, downstream owners and rationale boundary are in [UXR-01-DESIGN-DECISION.md](UXR-01-DESIGN-DECISION.md).

## Acceptance criteria

| AC | Result | Evidence and boundary |
|---|---|---|
| AC01 | PASS | UXR-00 is recorded as PARTIAL_WITH_EXPLICIT_BLOCKERS; UXR-00-R1 is scoped to three synthetic captures and remaining NOT_VERIFIED states. |
| AC02 | PASS | A/B gallery preserves 27 original PNGs per direction, matched scenarios and exact viewport labels; 54/54 local hashes and byte sizes match the manifest. |
| AC03 | PASS | Ten-criterion 0–3 comparison, trade-offs and the historical A recommendation/equal 26/30 tie are preserved; B is now the current selection. |
| AC04 | PASS | One dominant task-context CTA, truthful empty states and visible warning/consent constraints are documented in both directions and the handoff. |
| AC05 | PASS | Routes, consent deep link, local/AI separation, SRS semantics, autosave UNKNOWN, writing self-score/AI separation and revision conflicts remain explicit. |
| AC06 | PASS (documented) | 320px drawer, 1366×768 fold assumptions, reflow and keyboard assumptions are documented. No independent runtime/WCAG certification is claimed. |
| AC07 | PASS (provenance) | Existing Button/Card/Dialog are identified as canonical; Sidebar, Sheet, Breadcrumb, Badge, Alert, Skeleton and others are OFFICIAL_PROPOSED; compositions are APP_LEVEL_COMPOSITION. No install or component claim is made. |
| AC08 | PASS (owner record) | D1/D2/D3/D4/D6/D8/D9 approval is explicit and dated 13/10/2026; D5/D7 remain deferred/future as required. |
| AC09 | PASS | Handoff enumerates non-negotiables, downstream details, open evidence limits and UXR-02 ownership; it does not authorize UXR-02 automatically. |

## Validation results

- **Dashboard reference:** copied exact source bytes to owner-approved-dashboard-overview/; SHA-256 10998522acffa8b1ff6a21f66659666946c3c0fe5905d7501295ccb863833227; dimensions 1672 × 941.
- **Manifest/static JSON:** parsed successfully; 54 original images, 21 baseline copies and 3 contact sheets are present. Current status metadata records owner approval and publication blocking.
- **Markdown links:** recursive check found 227 local targets: 226 resolve from their current location (including one directory target). Six ../uxr00/final/ links in research/preliminary-independent-critique.md were repaired. The one unresolved link is a source-relative path inside byte-preserved research/uxr00/A2-design/REPORT.md to the adjacent repository document docs/design/future-learning-content-architecture-2026-10-12.md, which exists at that location. This archival copy was not rewritten as fresh evidence. Forty external or anchor links were classified separately, not claimed HTTP-verified.
- **Image validation:** existing package/header/hash checks and the recorded static render checks remain valid; no PNG was regenerated.
- **Scope:** only UXR-01 documentation/reference files and required changelog bookkeeping were changed. No production code, API, database, task todo, UXR-00/R1 originals or components were changed.
- **Pinned secret scan:** Gitleaks 8.30.1 was verified from the Winget manifest for the official GitHub release and reports gitleaks version 8.30.1. python scripts/security_checks.py --repo . secrets with GITLEAKS_BIN set returned exit 1. Findings are four redacted generic-api-key records in existing UXR-06 line 73 and UXR-07 line 58, in working-tree and history. The direct working-tree matches are ordinary task prose about answer keys and an API error state; they remain unresolved detector findings and were not suppressed. Report: htmlcov/security/gitleaks.json.
- **Git:** because the mandatory scan did not pass, no UXR-01 commit, push, research-branch integration or PR metadata update was attempted. Draft PR #26 was not merged.

The results above describe the earlier finalization checkpoint. On 13/10/2026 the owner authorized the two exact historical fingerprint exceptions and the already-published wording corrections. Those corrections are now present, existing exceptions are preserved, and `npm run security:secrets` passed with Gitleaks 8.30.1: exit 0, zero findings, report verdict PASS. The gate required filesystem escalation because sandbox permissions prevented temporary report writes. No scanner or rule was modified. Git integration and publication remain pending at this checkpoint.

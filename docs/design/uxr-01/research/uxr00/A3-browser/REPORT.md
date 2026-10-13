# UXR-00 A3 — Playwright rendered audit

Date: 12/10/2026 (Asia/Bangkok). Checkout: `design/ui-ux-research-20261012`, SHA `c2417ba6ff1db131fd3259faf67100fda6c3928b`.

The browser session used Playwright MCP with the isolated local harness at `http://127.0.0.1:8124`. The harness used temporary SQLite storage and synthetic route fixtures; external requests were denied. The first requested `gpt-6.1-sol/high` worker was rejected by runtime capacity. The successful browser worker used fallback `gpt-6-sol/high`; model fallback is recorded rather than inferred as the requested model. No production, harness or dependency files were edited.

## Canonical screenshot inventory

The canonical captures below are in `screenshots/`. The earlier `G1-shell-desktop.png` is retained as a duplicate predecessor and is excluded from the count.

| Group | Capture | State | Viewport |
|---|---|---|---|
| G1 | `G1-shell-desktop-REAL_RENDERED-1440x900.png` | REAL_RENDERED; active Dashboard shell | 1440x900 |
| G1 | `G1-shell-narrow-REAL_RENDERED-320x568.png` | REAL_RENDERED; narrow shell | 320x568 |
| G2 | `G2-lookup-idle-REAL_RENDERED-1440x900.png` | REAL_RENDERED; idle/consent-gated input | 1440x900 |
| G2 | `G2-lookup-preview-SYNTHETIC_RENDERED-1440x900.png` | SYNTHETIC_RENDERED; fake bridge preview | 1440x900 |
| G2 | `G2-lookup-preview-SYNTHETIC_RENDERED-320x568.png` | SYNTHETIC_RENDERED; fake bridge preview | 320x568 |
| G2 | `G2-lookup-invalid-REAL_RENDERED-1440x900.png` | REAL_RENDERED; invalid input validation | 1440x900 |
| G2 | `G2-missing-optional-SYNTHETIC_RENDERED-1440x900.png` | SYNTHETIC_RENDERED; missing optional values | 1440x900 |
| G3 | `G3-search-populated-SYNTHETIC_RENDERED-1440x900.png` | SYNTHETIC_RENDERED; list/filter | 1440x900 |
| G3 | `G3-word-detail-SYNTHETIC_RENDERED-1440x900.png` | SYNTHETIC_RENDERED; stored detail | 1440x900 |
| G4 | `G4-edit-form-SYNTHETIC_RENDERED-1440x900.png` | SYNTHETIC_RENDERED; edit draft | 1440x900 |
| G5 | `G5-review-populated-SYNTHETIC_RENDERED-1440x900.png` | SYNTHETIC_RENDERED; front/reveal/rating fixture | 1440x900 |
| G5 | `G5-review-populated-SYNTHETIC_RENDERED-320x568.png` | SYNTHETIC_RENDERED; narrow review | 320x568 |
| G6 | `G6-quiz-builder-REAL_RENDERED-1440x900.png` | REAL_RENDERED; local builder | 1440x900 |
| G6 | `G6-quiz-runner-SYNTHETIC_RENDERED-1440x900.png` | SYNTHETIC_RENDERED; in-progress MCQ/Cloze/Writing attempt | 1440x900 |
| G8 | `G8-status-REAL_RENDERED-1440x900.png` | REAL_RENDERED; readiness/diagnostics | 1440x900 |
| G8 | `G8-status-consent-REAL_RENDERED-320x568.png` | REAL_RENDERED; Status top narrow (filename is legacy; consent section not visible) | 320x568 |
| G8 | `G8-status-consent-SYNTHETIC_RENDERED-320x568.png` | SYNTHETIC_RENDERED; Status top narrow (filename is legacy; consent section not visible) | 320x568 |
| G8 | `G8-consent-dialog-SYNTHETIC_RENDERED-1440x900.png` | SYNTHETIC_RENDERED; privacy consent dialog | 1440x900 |
| G8 | `G8-consent-dialog-SYNTHETIC_RENDERED-320x568.png` | SYNTHETIC_RENDERED; privacy consent dialog narrow | 320x568 |
| G9 | `G9-dashboard-first-run-REAL_RENDERED-1440x900.png` | REAL_RENDERED; zero-data dashboard | 1440x900 |
| G9 | `G9-dashboard-first-run-REAL_RENDERED-320x568.png` | REAL_RENDERED; zero-data narrow dashboard | 320x568 |

Canonical screenshot count: **21**. There are 22 physical PNGs because the legacy `G1-shell-desktop.png` duplicates the canonical shell capture. Routes were rendered through the local app; synthetic labels identify only the fixture data, not a real provider or production acceptance.

## Findings

| ID | Group | Screenshot | State | Viewport | Observed behavior | Source anchor | Priority | Proposed shadcn/layout response | Pending/risk |
|---|---|---|---|---|---|---|---|---|---|
| BR-001 | G1 | G1-shell-desktop..., G1-shell-narrow... | REAL_RENDERED | 1440x900; 320x568 | Six destinations remain a horizontal header. At narrow width the navigation wraps/competes with the brand and AI link; no grouped drawer/sidebar is visible. | `frontend/src/app/AppShell.tsx`, `PRIMARY_NAV_ITEMS`, header nav | P0 design gate | Sidebar + Sheet mobile drawer, Breadcrumb for nested detail/attempt, grouped Learning/Vocabulary/Practice/System. | Keyboard drawer, deep-link active state and 200% zoom need a separate manual/a11y pass. |
| BR-002 | G2 | G2 lookup idle/preview captures | REAL_RENDERED + SYNTHETIC_RENDERED | 1440x900; 320x568 | Idle form spends a large card on one input. Preview exposes useful verification/provenance but makes the preview region tall and dense. | `LookupPage.tsx`, `LookupResult.tsx`, `SavePreview.tsx` | P1 | Input + Button composer; Card/Badge/Alert with compact provenance; Accordion optional examples; preserve preview-versus-save boundary. | Unavailable and cancellation scenarios remain unverified; no real AI claim. |
| BR-010 | G2 | G2-lookup-invalid... | REAL_RENDERED | 1440x900 | Invalid term/input state is rendered with immediate validation feedback while the composer remains available. | `LookupPage.tsx`, typed lookup error/recovery handling | P1 | Field-level Alert/Field error with preserved input; avoid replacing the whole composer. | Provider-unavailable and cancellation states remain unverified. |
| BR-011 | G2 | G2-missing-optional... | SYNTHETIC_RENDERED | 1440x900 | Preview with missing optional values keeps the result visible while distinguishing absent fields from verified content. | `LookupResult.tsx`, `VerificationLabel` | P1 | Badge/Accordion provenance and explicit MISSING/UNVERIFIED labels; never render missing as success. | Save transition and unavailable bridge state remain unverified. |
| BR-003 | G3 | G3 search/detail captures | SYNTHETIC_RENDERED | 1440x900 | Search controls and result detail are readable at desktop but information-rich; source/provenance competes with primary word meaning. | `SearchPage.tsx`, `WordDetail.tsx` | P1 | Primary search Input Group, advanced Accordion and active Badge chips; dictionary ResourceHeader and details disclosure. | No narrow G3 capture; URL back/cursor behavior remains unverified. |
| BR-004 | G4 | G4-edit-form... | SYNTHETIC_RENDERED | 1440x900 | Editor is a long card with repeated bilingual/example fields. Draft structure is understandable, but conflict and confirmed save receipts were not captured. | `EditWordForm.tsx`, `RevisionConflictDialog.tsx`, `SavePreview.tsx` | P1 | Field/Input/Textarea grouping, compact sections, Alert Dialog for revision conflict, one concise success receipt. | Save success, revision conflict and source reread remain NOT_VERIFIED. |
| BR-005 | G5 | G5 review captures | SYNTHETIC_RENDERED | 1440x900; 320x568 | Review fixture shows front/back and four ratings. Narrow layout remains readable; empty queue duplication and receipt-pending states need separate evidence. | `ReviewPage.tsx`, `Flashcard.tsx` | P0 design gate | One Empty surface plus slim date toolbar; Card/Progress/Badge for session state; preserve disabled rating until safe confirmation. | Global due count and operation reconciliation are not visual-proven. |
| BR-006 | G6 | G6 builder/runner captures | REAL_RENDERED + SYNTHETIC_RENDERED | 1440x900 | Builder presents three counts in a centered form. Runner renders heterogeneous question cards and state messaging; selected total/progress hierarchy could be stronger. | `QuizBuilder.tsx`, `QuizRunner.tsx`, `QuestionRenderer.tsx` | P1 | Shared grid, total-count summary, Progress, Radio Group/Field for writing rubric, explicit autosave/submit status. | Resume conflict and terminal submit are not claimed; synthetic attempt is not generated-AI evidence. |
| BR-007 | G7 | NONE | NOT_VERIFIED/BLOCKED | N/A | No sanctioned submitted-result plus writing-feedback fixture was available to the browser worker. Existing client test fixture is MCQ-only. | `QuizResult.tsx`, `FeedbackPanel.tsx`; fixture gap noted in A1 | P2 presentation, semantic safeguard | Use score summary Cards, Accordion answer review, separate objective/self/AI advisory labels when a fixture exists. | Requires separate approved result/feedback fixture task; do not manufacture or call AI. |
| BR-008 | G8 | G8 status/consent captures | REAL_RENDERED + SYNTHETIC_RENDERED | 1440x900; 320x568 | Status exposes many diagnostics before consent; the two narrow captures show the Status top, not the consent section. API alarm state is visibly UNKNOWN while conditional severity is shown, so current state and impact are distinguishable but dense. | `StatusPage.tsx`, `AiConsentPanel.tsx`, `RecoveryPanel.tsx` | P0 safety/readiness gate; P1 screen | Alert/Badge current readiness first; Accordion diagnostics; Dialog for policy; preserve `#ai-consent`, revoke semantics and local study availability. | Consent section, RecoveryPanel/error route, active-vs-unknown transitions and keyboard dialog matrix remain unverified. |
| BR-012 | G8 | G8-consent-dialog... | SYNTHETIC_RENDERED | 1440x900; 320x568 | Consent dialog is rendered at both viewports with disclosure and explicit decision actions. | `AiConsentGate.tsx`, `AiConsentPanel.tsx` | P1 | Radix/shadcn Dialog with concise disclosure hierarchy, clear grant/decline/revoke actions and focus return. | Synthetic policy only; no consent mutation or provider dispatch was performed. |
| BR-009 | G9 | G9 dashboard captures | REAL_RENDERED | 1440x900; 320x568 | Zero-data dashboard renders four result cards plus a global onboarding card. At desktop the primary next action is diluted by repeated empty explanations; narrow view requires substantial scroll. Due `0` is paired with “ÄÃ£ hoÃ n thÃ nh” while streak correctly says “ChÆ°a xÃ¡c Ä‘á»‹nh”. | `DashboardPage.tsx`, `isEntirelyEmpty`, result cards and due badge | P0 UXR-02A density gate; P1 screen | Content-driven MetricTile/Empty composition, one primary CTA, compact summaries and correct zero/unknown/completed wording. | Populated and mixed-data dashboard states remain NOT_VERIFIED. |

## Browser safety and limitations

- Browser used loopback only; no external provider or port `8045` was called. Harness bridge count remained zero for base readiness; fake lookup transport was in-process.
- Bootstrap/session credentials were kept in the browser closure and excluded from screenshots, reports and logs.
- Evidence is rendered local UI. Synthetic state does not establish AI provider correctness, backend acceptance, persistence or accessibility conformance.
- G7 is explicitly blocked; G2 unavailable/cancellation, G4 save/conflict, G5 empty/operation, G6 submit/conflict, G8 recovery/active alert and G9 populated/mixed states are not verified.


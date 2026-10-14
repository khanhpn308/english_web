# Owner-approved Dashboard Overview reference

**TASK_ID:** UXR-01  
**CONCEPT_STATUS:** Owner-approved concept reference for Dashboard Overview / UXR-09; no production implementation authorization.  
**OWNER_APPROVAL:** Explicit approval in the English Web ChatGPT project conversation, 13/10/2026.  
**DIRECTION:** B — Compact Study Console.

## Preserved source bytes

- Image: UXR-09-OWNER-APPROVED-DASHBOARD.png
- SHA-256: 10998522acffa8b1ff6a21f66659666946c3c0fe5905d7501295ccb863833227
- Physical dimensions: **1672 × 941 pixels**
- Source prompts copied byte-for-byte: [UXR-09-MASTER-PROMPT.txt](UXR-09-MASTER-PROMPT.txt) and [UXR-09-STRICT-VISUAL-CONTRACT.txt](UXR-09-STRICT-VISUAL-CONTRACT.txt)

The physical image dimensions are distinct from the future 1440 × 900 CSS-pixel browser-rendering requirement.

## Locked concept

The reference establishes the Dashboard composition: a dominant “VIỆC CẦN LÀM HÔM NAY” action, a single-book “SÁCH HỌC GẦN ĐÂY” carousel state, four compact KPI cards, three analytics panels, and the Row 4 “Kỹ năng cần củng cố” panel. The carousel concept uses one complete book per stable state, subtle controls, pagination and conceptual autoplay with interaction/reduced-motion considerations.

## Data-truthfulness boundary

Current DashboardSummary supports aggregate metrics such as dueCards, streak, flashcard self-rating, objective MCQ/Cloze accuracy and writing self-score. Recent book history, seven-day forecasts, calendar activity, fourteen-day series, recent activity and historical quiz breakdowns require source verification or future data contracts. Screenshot values and book/chart content are SYNTHETIC_DESIGN_FIXTURE, not observed learner data. Widgets must be classified as SOURCE_BACKED_CURRENT, DERIVED_FROM_CURRENT_CONTRACT, SYNTHETIC_DESIGN_FIXTURE or FUTURE_DATA_CONTRACT_REQUIRED during UXR-09.

| Reference region | Contract classification | Boundary |
|---|---|---|
| Today's due-review count and CTA | SOURCE_BACKED_CURRENT / DERIVED_FROM_CURRENT_CONTRACT | Use dueCards only when known and positive; choose a truthful alternative when zero. |
| Four KPI cards | SOURCE_BACKED_CURRENT for due, streak, MCQ accuracy and Writing self-score aggregates | Comparison arrows, denominators outside the current contract and illustrative values are SYNTHETIC_DESIGN_FIXTURE. Writing is learner self-score, not AI grade. |
| Recent-book carousel | FUTURE_DATA_CONTRACT_REQUIRED | Book identities, recent-study order, progress and resume location are not in DashboardSummary. The pictured book is SYNTHETIC_DESIGN_FIXTURE. |
| Seven-day due bar chart and activity heatmap | FUTURE_DATA_CONTRACT_REQUIRED | A current total does not support a future forecast or dated history. |
| Result donut, fourteen-day progress and recent activity | FUTURE_DATA_CONTRACT_REQUIRED | Historical grouping, time series and feed are not supplied by the current aggregate DTO. |
| Skills to strengthen | DERIVED_FROM_CURRENT_CONTRACT only for honest independent MCQ/Cloze/Writing aggregate summaries | A ranked recommendation or per-skill trend needs source verification; screenshot examples are SYNTHETIC_DESIGN_FIXTURE. |

## Locked versus downstream-owned

Locked here: the concept, composition, hierarchy, single-book carousel rule and skills-panel replacement. UXR-09 owns its design artifacts, responsive states, data-source verification and owner review. UXR-02/02A own the shared foundation, semantic tokens, detailed density and responsive implementation mapping. No endpoint, migration, book entity, chart computation or frontend component is authorized by this reference.

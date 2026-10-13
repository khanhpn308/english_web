# UXR-00 nine-group coverage matrix

| Group | Rendered coverage | Evidence | Missing / blocked |
|---|---|---|---|
| G1 AppShell/navigation | PARTIAL | REAL desktop + narrow shell | Drawer, deep-link/back and keyboard matrix |
| G2 Lookup/AI preview | PARTIAL | REAL idle + invalid; SYNTHETIC preview + missing optional desktop/narrow | Unavailable, cancellation and save transition |
| G3 Search/detail | PARTIAL | SYNTHETIC populated list + detail desktop | Narrow/filter URL recovery |
| G4 Save/edit | PARTIAL | SYNTHETIC edit desktop | Confirmed save/conflict screenshots, narrow form |
| G5 Review | PARTIAL | SYNTHETIC populated front/back/rating desktop+narrow | Empty queue, pending/unknown operation |
| G6 Quiz builder/runner | PARTIAL | REAL builder; SYNTHETIC MCQ/Cloze/Writing runner | Resume conflict, terminal submit |
| G7 Results/writing feedback | PARTIAL / NOT_VERIFIED | Existing typed MCQ result fixture is source-confirmed; no rendered result screenshot | Writing self-score/feedback rendered state and browser result capture; no AI call made |
| G8 Status/consent/errors | PARTIAL | REAL status desktop; REAL/SYNTHETIC Status top narrow; SYNTHETIC consent dialog desktop+narrow | RecoveryPanel, active-vs-unknown transitions, keyboard dialog |
| G9 Dashboard | PARTIAL | REAL zero-data desktop+narrow | Populated and mixed-data states |

Overall: **8/9 groups have rendered evidence; 1/9 is blocked; no group is claimed fully verified.**




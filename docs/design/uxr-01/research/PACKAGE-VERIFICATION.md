# UXR-01 package verification

Task UXR-01, visual version v1.2. Direction B owner-approved 13/10/2026. Documentation status: validated locally; publication blocked by the mandatory secret scan.

- Required packet documents present: 6, plus the finalization verification and owner-approved Dashboard reference bundle.
- Original task PNGs: A 27 + B 27. Baseline capture copies: 21. Derived contact sheets: 3.
- The existing manifest contains 54 original entries with preserved IDs, paths, dimensions, byte sizes and SHA-256 values. A local header/hash pass verified all 54 files against the manifest; no image was regenerated or replaced.
- The approved Dashboard reference was copied byte-for-byte with its two prompt files. The image is 1672 × 941 pixels and has SHA-256 10998522acffa8b1ff6a21f66659666946c3c0fe5905d7501295ccb863833227.
- The existing standalone render record contains 50 light-state renders with no recorded script errors, no page-level horizontal overflow and no visible button taller than 90px. This is mockup evidence, not production browser, keyboard, WCAG or runtime acceptance.
- A recursive Markdown link check on the UXR-01 tree resolved 226 of 227 local targets after the six preliminary-critique links were corrected. The one remaining source-relative link is in the byte-preserved archived UXR-00 A2 report and points to an adjacent repository document; its archival copy is intentionally unchanged. External citations and local-only provenance paths are reported separately in finalization verification.
- JSON parsing passed for assets/image-manifest.json and research/static-render-checks.json. The current manifest status records owner approval and publication blocking; historical image records remain unchanged.
- No frontend/backend/generated DTO/components.json/lockfile/task-todo/constraints/schema/ADR or UXR-00/R1 original evidence was modified.
- Pinned Gitleaks 8.30.1 was obtained from the verified Winget manifest for the official GitHub v8.30.1 release. The actual secrets gate returned exit 1 with four redacted generic-api-key findings in existing UXR-06/UXR-07 task files across working-tree and history. Report: htmlcov/security/gitleaks.json. This is a real violation result, not setup success.
- No commit, push or research-branch integration was attempted after the blocking scan. No force push, suppression flag or policy change was used.

No full test/CI/WCAG PASS is claimed. Static checks do not establish production focus, screen reader, browser zoom, API behavior, source safety, persistence or AI policy correctness.

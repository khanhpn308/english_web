# Runbook: Search performance regression

**Means:** The indexed Vietnamese meaning search exceeded the approved benchmark target on the pinned Windows fixture.

**First check:** Verify fixture version, SQLite build, normalization/index revision, query shape and cold/warm cache state before comparing timings.

**Recovery:** Rebuild only the derived search projection after preserving canonical Markdown/SQLite data; do not change the acceptance threshold silently.

**Escalate:** Record p50/p95/p99, row counts and index revision, not user terms or vocabulary content.

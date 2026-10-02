# T042 deterministic search fixture

This directory contains synthetic data for the T026 Vietnamese search projection.
The generator is local-only and uses no user vocabulary, network, provider, AI
generation, browser history, credentials, or machine-specific values.

## Generate

From the repository root, run:

```text
python benchmarks/generate_fixture.py --forms 100000 --seed 29
```

The command atomically writes:

- `fixtures/100k_forms.jsonl`: one canonical JSON object per form, exactly one
  hundred thousand lines for the required command;
- `artifacts/search-report.json`: the fixed 100-query set and expected IDs.

The `--forms` value is bounded to 1 through 1,000,000 for development probes.
The release fixture uses 100,000. `--seed` is an integer from 0 through
4,294,967,295. A seeded arithmetic mapping selects synthetic phrases; IDs also
include the seed. No Python process-randomized `hash()` is used.

Generation streams JSONL records to a temporary file, flushes and fsyncs it,
then replaces the final path. The report is written with the same temporary-file
and replace pattern. A failed run cannot publish a shorter fixture or a report
claiming a complete run.

## Form schema

Each JSONL record uses `schemaVersion: "t042-fixture-v1"` and these fields:

| Field | Meaning |
| --- | --- |
| `id` | Unique deterministic form identity (`t042-<seed>-<zero-padded-index>`). |
| `familyId` | Deterministic synthetic family grouping. |
| `lemma`, `normalizedLemma` | Synthetic lemma strings. |
| `partOfSpeech` | One of `ADJECTIVE`, `NOUN`, `VERB`, `ADVERB`. |
| `meaningsVi` | Non-empty list of explicit Vietnamese meaning strings. This is the T026 search source. |
| `sourceRefs` | At least one source reference with `sourceId`, `noteDate`, and `status`; generated rows are `VALID`. |
| `verificationSummary` | `VERIFIED` synthetic fixture state. |
| `revision`, `createdAt`, `updatedAt` | Fixed deterministic metadata required to construct T026-compatible forms. |

The fixture deliberately includes duplicate-looking text with distinct IDs and
POS values, punctuation (`%`, `_`, brackets), NFC/decomposed equivalents,
accented and accent-folded Vietnamese, and `đ`/`Đ` cases. It contains no
English meanings or examples because T026 indexes `meaningsVi` only.

## Report and checksums

`search-report.json` uses `schemaVersion: "t042-fixture-v1"` and contains the
generator version, seed, requested/actual form counts, query count, 100 query
objects, and sorted expected form IDs for every query. Query objects carry a
stable ID, the raw query string, and a coverage category.

Checksums are SHA-256 values over UTF-8 bytes:

- `fixtureSha256`: canonical final JSONL bytes, including each newline;
- `querySetSha256`: canonical compact JSON of query objects containing only
  `id`, `query`, and `category`, in report order;
- `groundTruthSha256`: canonical compact JSON of objects containing `id` and
  `expectedMatchIds`, in report order.

Canonical JSON uses UTF-8, `ensure_ascii=false`, sorted object keys, compact
separators, and no trailing whitespace. The report itself ends with one newline.
Repeated runs from the same source revision with `--forms 100000 --seed 29`
produce byte-identical artifacts. An alternate seed changes fixture IDs/content
and the ground-truth report while the fixed query set remains seed-independent.

## Ground truth and coverage

The oracle is a direct brute-force scan implemented in
`generate_fixture.py`. It independently applies NFC/casefold/space collapsing
and an accent-fold projection using `unicodedata`, then checks substring
membership in each stored `meaningsVi` string and requires a `VALID` source. It
does not call `SearchIndex`, SQL, n-grams, or the T026 implementation. The
focused tests compare this oracle with a bounded T026 `SearchIndex` sample.

The fixed queries include exact and infix matches; one-, two-, and three-character
queries; NFC and combining-mark equivalents; accent folding; `đ`/`Đ`; casefolding;
punctuation boundaries; multiple POS identities; and zero, one, several, and
many-match cases. Semantic or synonym guessing is represented by an explicitly
zero-match query.

## Downstream benchmark profile

T042 establishes fixture determinism and correctness only. It does not claim
`PERF-02`, p95 <= 1 second, a browser render bound, or any other timing result.
T065 owns timing evidence on the named release profile:

- Windows 11, with the OS build recorded;
- Python 3.12, with the exact version recorded;
- SQLite, with `sqlite3.sqlite_version` and relevant compile/options recorded;
- exactly 100,000 forms, exactly these 100 fixed queries, seed 29;
- T026 projection version and source-validity assumptions recorded;
- separate cold and warm runs with a documented cache protocol (database/page
  cache state, process restart policy, and browser cache state);
- CPU model, RAM, storage type, and other hardware recorded by the runner.

Do not run on WSL and label that result as Windows release evidence. Missing
Windows/browser/hardware evidence is pending for T065; it is never a T042
performance pass.

## Verification

```text
python -m pytest benchmarks/tests/test_fixture.py -q
python benchmarks/generate_fixture.py --forms 100000 --seed 29
```

The tests cover determinism, exact counts, Unicode behavior, independent
ground truth, duplicate/malformed/incomplete data rejection, atomic generation,
and invalid CLI input. Generated artifacts are never hand-edited; change the
generator and regenerate them instead.

# T008 — Round 4 Shared Remediation Authorization

**Parent task:** T008 — Lookup API Vertical Slice
**Card type:** Scoped shared-remediation authorization
**Status:** AUTHORIZED_FOR_REMEDIATION
**Audit trigger:** Independent Re-Audit Round 4
**Audited candidate:** `9ed91b9762f7fd859e81ba9e743fb18a91030509`
**Audited base:** `c77a911cb58c4c76bc7daf87adb19dffdea78290`

---

## 1. PURPOSE

This card authorizes the minimum shared-file scope required to remediate findings from **T008 Independent Re-Audit Round 4**.

It exists specifically to satisfy the repository rule that implementation work outside the original T008 file scope must be authorized by a **separate card before further shared implementation editing**.

This card:

- does not declare T008 DONE;
- does not authorize integration;
- does not authorize modification of T027;
- does not retroactively claim that candidate `9ed91b9` was scope-compliant;
- authorizes the controlled continuation, correction and re-verification of the shared changes required for a new T008 remediation candidate.

The Round-4 candidate remains historical audit evidence and must not be rewritten or amended.

---

# 2. ROUND-4 FINDINGS COVERED

This authorization is limited to remediation of:

```text
R4-B01 — Cancellation can leave durable PENDING operations
R4-B02 — Hard deadline does not cover the complete request lifecycle
R4-B03 — Consent schema violates required-nullable semantics
R4-B04 — Malformed client Unicode returns an internal error
R4-B05 — Invalid UTF-8 bridge output is mislabeled as storage failure

R3-B07 — Shared-scope authorization remains open
R3-B08 — Deterministic concurrency evidence remains incomplete
```

No unrelated feature work is authorized by this card.

---

# 3. EXISTING T008-OWNED SCOPE

The original T008-owned implementation scope remains governed by the parent T008 card.

The following existing T008 files may continue to be modified as necessary for Round-4 remediation:

```text
backend/app/enrichment/lookup.py
backend/app/enrichment/prompts/lookup.txt
backend/app/http/lookups.py
backend/app/main.py
backend/tests/test_lookups.py
```

Changes in these files must still be directly traceable to T008 acceptance criteria or the Round-4 findings listed above.

---

# 4. AUTHORIZED SHARED HANDWRITTEN SCOPE

The following shared handwritten files are explicitly authorized for T008 Round-4 remediation.

## 4.1 Existing shared changes inherited from candidate 9ed91b9

The remediation branch may carry forward, review and where necessary correct the existing T008-related changes in:

```text
backend/app/application/ai_admission.py
backend/app/vocabulary/repository.py
backend/app/http/errors.py
scripts/export_contract.py
scripts/tests/test_contract.py
```

Authorization is narrowly scoped as follows.

### `backend/app/application/ai_admission.py`

Authorized only for behavior required by T008/T016 interaction, including:

- immutable admission payload handling;
- lifecycle/cancellation interaction directly exercised by T008;
- preservation of default-deny admission semantics.

Do not redesign T016 policy or provider-routing behavior.

---

### `backend/app/vocabulary/repository.py`

Authorized only for:

- transaction participation required for atomic lookup-preview persistence;
- preservation of T019 preview semantics;
- correction of defects directly required by T008 atomicity.

Do not alter unrelated vocabulary persistence behavior.

---

### `backend/app/http/errors.py`

Authorized only for:

- error serialization required by T008;
- preservation/correction of public error classification required by the API contract;
- redaction behavior directly relevant to T008.

Do not perform unrelated error-framework refactoring.

---

### `scripts/export_contract.py`

Authorized only for:

- correcting `AI_CONSENT` error-detail schema semantics;
- preserving other existing generated API contracts;
- producing canonical OpenAPI through the repository generator.

The Round-4 requirement is that:

```text
currentPolicyVersion
```

is:

```text
required
AND
string | null
```

under the repository's OpenAPI 3.1 contract.

Do not manually edit generated API artifacts as the primary fix.

---

### `scripts/tests/test_contract.py`

Authorized only for executable contract proof related to the T008/T017 error union, particularly:

```text
AI_CONSENT.currentPolicyVersion
```

Required regression semantics:

```text
missing field -> invalid
null          -> valid
string        -> valid
```

Tests must exercise the actual generated schema semantics rather than merely checking for property presence or a legacy `nullable` flag.

---

# 5. NEW ROUND-4 SHARED SCOPE

The following additional shared files are authorized because Round-4 defects cannot be correctly resolved within the original T008 allowlist alone.

## 5.1 Request lifecycle / deadline boundary

```text
backend/app/http/session.py
```

This file is authorized **only if required to close R4-B02**.

Permitted changes:

- enforce the existing request deadline across request/body lifecycle stages;
- propagate/use the already-authoritative monotonic deadline;
- ensure blocked request receive/body processing cannot outlive the required hard deadline indefinitely.

Not authorized:

- unrelated session behavior changes;
- authentication redesign;
- cookie/session format changes;
- broad middleware refactoring.

If R4-B02 can be correctly solved without changing this file, leave it unchanged.

---

## 5.2 Bridge response classification

```text
backend/app/adapters/bridge.py
```

This file is authorized specifically to close **R4-B05**.

Permitted changes:

- classify malformed bridge response encoding as a typed bridge-invalid-response failure;
- correctly handle invalid UTF-8 or equivalent response-decoding failure;
- preserve existing timeout, authentication, transport, size-limit and no-retry semantics.

Required externally visible result for malformed successful bridge responses:

```text
HTTP 502
BRIDGE_INVALID_RESPONSE
operation != SUCCEEDED
0 successful previews
```

Do not:

- add retries;
- broaden supported bridge endpoints;
- change provider selection;
- change authentication policy;
- weaken response-size limits;
- expose raw malformed bytes or internal exceptions.

---

# 6. AUTHORIZED SHARED TEST SCOPE

To close the remaining deterministic-concurrency evidence gap, the following existing shared test file is authorized for **test-only bounded synchronization changes**:

```text
backend/tests/test_operations.py
```

Permitted modifications are limited to:

- replacing unbounded Barrier/Future/Event/task waits with deterministic bounded waits;
- ensuring regressions fail within a bounded interval rather than hanging;
- preserving the production mechanism being exercised.

Not authorized:

- weakening assertions;
- skipping tests;
- replacing real database behavior with mocks;
- changing T014 production semantics;
- using `time.sleep()` or `asyncio.sleep()` as correctness synchronization.

T008-specific concurrency regression tests should remain in:

```text
backend/tests/test_lookups.py
```

where practical.

---

# 7. GENERATED ARTIFACTS

The following generated files may change only as outputs of their canonical generators:

```text
contracts/openapi.json
frontend/src/shared/api/generated.ts
```

Rules:

1. Never manually repair these files.
2. Modify the canonical source/generator first.
3. Regenerate using the repository-defined process.
4. Verify deterministic regeneration.
5. Any unrelated generated diff is a blocker.

Expected Round-4 contract correction includes the required-nullable semantics for:

```text
AI_CONSENT.currentPolicyVersion
```

---

# 8. BLOCKER-TO-FILE AUTHORIZATION MATRIX

| Finding | Primary authorized files | Required proof |
|---|---|---|
| R4-B01 cancellation durability | `backend/app/enrichment/lookup.py`, `backend/tests/test_lookups.py` | Cancellation during claim and repeated cancellation cannot leave illegal PENDING state |
| R4-B02 complete hard deadline | `lookup.py`, `main.py`, conditionally `http/session.py`, `test_lookups.py` | Every contract-required lifecycle stage remains bounded and cannot produce late success |
| R4-B03 consent schema | `scripts/export_contract.py`, `scripts/tests/test_contract.py`, canonical generated artifacts | Missing invalid; null/string valid; TS property required |
| R4-B04 malformed client Unicode | `lookup.py`, `test_lookups.py` | Isolated surrogates -> 422, zero provider/preview effects |
| R4-B05 malformed bridge bytes | `adapters/bridge.py`, `test_lookups.py` | Invalid UTF-8 bridge body -> 502 BRIDGE_INVALID_RESPONSE |
| R3-B07 scope governance | this separate authorization card | Every shared edit maps to an explicitly authorized purpose |
| R3-B08 bounded concurrency evidence | `test_lookups.py`, limited `test_operations.py` | Explicit synchronization + bounded waits; no sleeps/unbounded waits |

Any required file outside this matrix requires another explicit scope authorization before editing.

---

# 9. R4-B01 — REQUIRED LIFECYCLE INVARIANTS

Remediation must guarantee the complete durable operation lifecycle.

For every claimed operation:

```text
CLAIMED
→ ADMISSION / PROVIDER / COMPLETION
→ DURABLE TERMINAL STATE
```

Cancellation must not leave an operation permanently PENDING when the contract requires a terminal result.

Required adversarial cases include:

### Cancellation during claim

If cancellation occurs while the real durable claim is in progress:

- claim completion and parent cancellation must have defined semantics;
- no operation may be left in an illegal durable PENDING state;
- same-key replay must follow T014 semantics;
- no duplicate provider dispatch may occur.

### Cancellation after admission / dispatch

Where external work may already have occurred:

```text
UNKNOWN
```

must be used when the contract requires uncertainty rather than falsely claiming definite failure.

### Repeated cancellation during cleanup

A second cancellation must not prevent required durable terminal-state recording.

Required cleanup must be designed so that cancellation of the request coroutine cannot silently abandon mandatory durable classification.

Do not fake correctness with process-local state.

---

# 10. R4-B02 — REQUIRED DEADLINE INVARIANTS

The authoritative monotonic deadline must cover the complete contract-required lifecycle.

Audit and regression proof must include blocking independently at relevant stages such as:

```text
request/body receive
claim
admission/preflight
provider await
response parsing
preview/final completion
durable cleanup where contract-bounded
```

A recorded timestamp alone is not hard deadline enforcement.

The implementation must prevent:

```text
stage blocks indefinitely
→ deadline expires
→ request remains indefinitely pending
```

Finalization occurring after deadline must never create late success.

Worker-thread continuation after parent timeout must be explicitly considered.

Deadline remediation must preserve atomic preview/SUCCEEDED transaction semantics already proven in Round 4.

---

# 11. R4-B03 — REQUIRED CONSENT CONTRACT

Canonical public contract:

```text
details.kind == "AI_CONSENT"
```

and:

```text
currentPolicyVersion
```

must be:

```text
REQUIRED
value = string | null
```

Required executable proof:

```text
missing currentPolicyVersion -> schema invalid
currentPolicyVersion: null   -> schema valid
currentPolicyVersion: "..."  -> schema valid
```

Generated TypeScript must expose the property as required, not optional.

Runtime NOT_GRANTED/REVOKED behavior must remain:

```text
403 AI_CONSENT_REQUIRED
0 provider preflight
0 provider dispatch
0 preview
```

unless an authoritative dependency contract explicitly specifies otherwise.

---

# 12. R4-B04 — REQUIRED UNICODE VALIDATION

Malformed Unicode must be rejected at the normalized client-input boundary before:

- operation fingerprinting;
- provider preflight;
- provider dispatch;
- preview persistence.

At minimum test:

```text
isolated high surrogate
isolated low surrogate
valid surrogate-equivalent astral Unicode
NFC decomposed/precomposed equivalence
1 / 80 / 81 normalized length boundaries
control characters
```

Required behavior for malformed surrogate input:

```text
HTTP 422
0 provider dispatch
0 preview
```

Do not broadly reject valid non-BMP Unicode merely to fix isolated surrogate handling.

---

# 13. R4-B05 — REQUIRED BRIDGE ERROR SEMANTICS

A bridge HTTP success response containing bytes that cannot be decoded/parsed according to the bridge contract is an invalid bridge response, not a storage failure.

Required classification:

```text
BRIDGE_INVALID_RESPONSE
HTTP 502
```

Required proof must exercise the actual adapter boundary using deterministic local transport such as:

```text
httpx.MockTransport
```

No external network or real provider inference.

Regression should cover at least:

```text
invalid UTF-8 models response, if contract-relevant
invalid UTF-8 chat response
malformed JSON
valid JSON positive control
```

The adapter must emit a typed error that the lookup layer handles through the normal bridge-error path.

Do not special-case malformed bytes in lookup if the bridge adapter owns response decoding.

---

# 14. R3-B08 — TEST SYNCHRONIZATION REQUIREMENTS

Concurrency tests must use explicit deterministic synchronization.

Allowed mechanisms include:

```text
asyncio.Event
bounded Barrier
bounded Future/task completion
explicit transaction hook
known dispatch point
known commit boundary
asyncio.timeout(...)
```

Correctness must not depend on:

```text
time.sleep(...)
asyncio.sleep(...)
unbounded wait
scheduler luck
```

Test hooks may expose timing points.

They must not supply the production correctness mechanism.

---

# 15. HARD PROHIBITIONS

This card does NOT authorize modification of:

- T027 implementation or worktree;
- unrelated tasks;
- unrelated migrations;
- package dependencies unless separately authorized;
- lock files unless an explicitly authorized dependency change requires them;
- frontend UI behavior unrelated to regenerated API types;
- unrelated provider/routing behavior;
- authentication/session semantics unrelated to R4-B02;
- vocabulary persistence unrelated to T008 preview atomicity;
- unrelated error mappings;
- unrelated API schemas.

Do not use this card as general permission to clean up adjacent code.

---

# 16. NO MIGRATION AUTHORIZATION

This remediation card does not authorize a new database migration.

If remediation concludes that schema migration is required for correctness:

```text
STOP
```

and report:

```text
BLOCKED_FOR_SCOPE_EXTENSION
```

with:

- required schema change;
- required migration ownership;
- why existing schema cannot satisfy the invariant.

Do not consume another task's migration ownership.

---

# 17. NO NEW DEPENDENCY AUTHORIZATION

Do not add Python, Node or system dependencies to solve Round-4 findings unless separately authorized.

Use existing project/runtime capabilities.

Environment problems with Windows tests, OSV data or scanner installation must not be "fixed" by changing application dependencies.

---

# 18. VERIFICATION REQUIREMENTS

The remediation worker must use RED → GREEN evidence for every corrected semantic defect.

At minimum, before another independent audit, obtain passing evidence for:

```text
focused T008 regression tests
contract tests
Python type checking
Python lint
TypeScript typecheck
architecture gate
fast quality gate
full relevant regression
security/code gates
dependency-security gate where required
genuine Windows-only regression evidence where required
```

A required non-zero gate is not PASS.

Linux/WSL failures caused solely by genuine native-Windows guards must not be hidden by skip markers or weakened tests.

Windows evidence must be obtained from an appropriate Windows execution environment.

Dependency-security evidence must use the repository-approved scanner/database mechanism.

Do not alter application code merely to make an environment/setup failure disappear.

---

# 19. REQUIRED ROUND-4 REGRESSION MATRIX

Before another audit, the remediation report must include:

```text
Finding
| RED test/probe
| Expected failure reason
| Observed RED reason
| Implementation mechanism
| GREEN result
| Final gate evidence
```

Required findings:

```text
R4-B01
R4-B02
R4-B03
R4-B04
R4-B05
R3-B08
```

R3-B07 is satisfied only if the final changed-file set remains inside this card plus the original T008-owned scope.

---

# 20. SOURCE FREEZE

After remediation is complete:

1. freeze the resulting candidate;
2. record the exact candidate SHA;
3. run final verification against that exact snapshot;
4. do not change source after final evidence;
5. if source changes, invalidate affected evidence and rerun it.

The next audit must inspect the exact frozen candidate SHA.

---

# 21. BOOKKEEPING

This card may be referenced from the parent T008 task card as:

```text
Round-4 shared remediation authorization:
tasks/t008-r4-shared-remediation.md
```

Do not mark T008 DONE from this card.

Do not mark T027 complete.

Do not mark an integration/checkpoint complete.

T008 may advance only after a new independent re-audit returns:

```text
PASS_FOR_INTEGRATION
```

---

# 22. COMMIT / INTEGRATION BOUNDARY

Creating this authorization card does not itself authorize:

```text
merge
integration
push
force-push
```

Implementation/remediation commits remain subject to the normal repository workflow and explicit authorization.

T008 integration into main is a separate step after successful independent re-audit.

---

# 23. CLOSURE CONDITIONS

This remediation authorization is considered successfully consumed only when:

1. all code changes remain inside the parent T008 scope plus this card;
2. R4-B01 through R4-B05 have executable regression proof;
3. R3-B08 uses bounded deterministic synchronization;
4. generated artifacts reproduce canonically;
5. no unexplained shared-file drift remains;
6. required quality/security/environment gates have valid evidence;
7. a new candidate SHA is frozen;
8. an independent re-audit is performed.

Until then:

```text
T008 STATUS = REMEDIATION_IN_PROGRESS
INTEGRATION = NOT AUTHORIZED
T027 = UNCHANGED
```

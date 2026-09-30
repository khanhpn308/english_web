# T015: Persist consent singleton và GET/PUT/DELETE

**Task ID:** `T015`  
**Title:** Persist consent singleton và GET/PUT/DELETE  
**Status:** `DONE`
**Goal:** Persist consent singleton và GET/PUT/DELETE. NOT_GRANTED initial; ready-only grant, stale ETag/digest denial; no implicit grant.  
**Suggested model:** GPT-6 Astra  
**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay trong danh sách. Nếu vượt khoảng 2 giờ hoặc phạm vi này, tách task trước khi làm tiếp.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/adr/0003-ai-consent-and-revocation.md](../docs/adr/0003-ai-consent-and-revocation.md)
- [docs/api-contract.md](../docs/api-contract.md) CONSENT-01–04/08/09/11

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T014](t014-operations-idempotency.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

- `backend/migrations/versions/0003_consent.py`
- `backend/app/application/consent.py`
- `backend/app/http/consent.py`
- `backend/tests/test_consent.py`
- `backend/app/main.py`

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- Policy/version/digest/events append-only, exact scopes, structured statements; no provider calls. Grant/revoke dùng shared operation receipt; UI permission GET authoritative. Missing policy never invented ready. Đăng ký đúng route/service vào app factory; TestClient và OpenAPI export dùng app factory production, không app test riêng bỏ security guards.
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [x] NOT_GRANTED initial; ready-only grant, stale ETag/digest denial; no implicit grant.
- [x] Revoke works offline/missing policy; old successful receipt cannot restore grant.
- [x] Policy/event/receipt atomic; storage failure reports no success, fail closed.

## Test cases

1. CONSENT-01–04/08/09/11 fake storage and two tabs.
2. No-key/unknown fields/DELETE If-Match rejects; no network call.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
python -m pytest backend/tests/test_consent.py -q
npm run test:contract
```

## Expected output

- NOT_GRANTED initial; ready-only grant, stale ETag/digest denial; no implicit grant.
- Focused commands đạt kết quả/exit code ghi trong criteria; negative probe phải fail đúng reason. Documentation tasks có conformance report thay cho application-test pass.
- Evidence ghi command, exit code, môi trường và artifact. Thiếu Windows/browser/provider environment là PENDING; không hoàn tất gate thiếu evidence.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Risk

- **Level:** `Critical`.
- Sai boundary có thể gửi dữ liệu/cost không được phép hoặc mất lịch sử học.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- Bỏ digest/fence/history hoặc lưu policy content như telemetry → dừng.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`feat(T015): persist consent singleton và get/put/delete`


## Semantic remediation handoff — 30/09/2026 (`Asia/Bangkok`)

- **Task status:** DONE. All T015 semantic acceptance criteria and focused gates pass. Overall workspace status is `IMPLEMENTATION_DONE_BASELINE_BLOCKED`; no commit or push was authorized.
- **Worktree/base:** `/home/khanh/projects/vocabularies-t015-semantic`, branch `fix/t015-semantic`, initially clean at quality-fix commit `865740e` (`fix: clean T015 T017 quality diagnostics`). Its quality fixes remain intact. No merge/rebase/pull, other-worktree access, real credential or provider request.
- **Review:** Two read-only reviewers checked the consent contract and SQLite transaction semantics. No Critical authoritative-source contradiction; actionable corruption, configuration-reversion and connection-open findings received regression tests and fixes. No optional external/cross-model review.
- **Migration gate:** T015 is the current unfinished/unreleased owner of `0003_consent`; no released-migration rule requiring a new revision was found. Complete it in place, maintaining `0002_operations → 0003_consent`, one head. This does not upgrade a previously deployed database already stamped with the old 0003 schema. No user database was touched; T019's future 0004 remains untouched.

### Policy and persistence

- Pydantic models expose all AiDisclosurePolicy fields and narrow scope/category/review/routing enums. READY requires complete nonblank disclosure/statements/recipients/categories, exactly LOOKUP/QUIZ_GENERATION/WRITING_FEEDBACK once each, exactly one valid rule per scope, and no blocked reasons. Rules require Antigravity/Google, gemini-3.8-flash-high, primary, configured-account. There is no fallback or network-derived policy.
- Internal canonicalization follows existing T014 practice: UTF-8 JSON, sorted keys, compact separators, `ensure_ascii=False`, `allow_nan=False`; SHA-256 excludes the digest field. Caller-supplied digest is ignored. Every exposed policy digest matches its complete definition; invalid effective policies return null rather than rewritten READY/BLOCKED definitions with inconsistent digests.
- Existing singleton gains append-only `policy_history` and `policy_conflicts` JSON registries. Valid definitions retain their complete canonical configuration and digest; malformed definitions reserve only their digest, without storing unvalidated text. Same-version changes are durably rejected even if configuration reverts or a service/engine restarts; correction requires a new version. SQLite triggers prohibit replacing/removing registry entries and replacing/deleting the singleton. Missing/corrupt accepted history never reconstructs permission.
- Append-only events use GRANTED/REVOKED actions, unique revision and operation reference. Grant stores version/digest/scopes/rules/server time; revoke stores no active-policy dependency. Triggers reject UPDATE, DELETE and INSERT OR REPLACE. Operation result_ref contains only an opaque event reference, never policy text, scopes, keys or user content.
- GET requires coherent matching policy, singleton, grant event and successful CONSENT_GRANT receipt (including status 200). Otherwise GRANTED becomes STALE and canRequestAi is false. Storage failures latch the running service fail-closed. Provider/network/quota readiness is separate. Public lastChoiceAt is a server-generated UTC RFC3339 date-time.
- ETag is a SHA-256 opaque fingerprint of revision/effective state, accepted identity, policy availability/status/version/canonical fingerprint/integrity and storage reliability. Stable reads are stable; revision, missing/READY/BLOCKED state, version and same-version definition changes alter it. No policy text or credentials are exposed in it.

### Mutation ordering and precedence

1. Existing SessionGuard and HTTP shape validation run first; queries, unknown fields, bad version/header syntax, missing body/key and DELETE body/If-Match are rejected. Consent malformed JSON uses its specific 422 VALIDATION_ERROR contract; other endpoints retain their existing behavior.
2. T014 atomically claims the canonical intent/preconditions. Exact terminal replay returns the historical receipt before current policy/ETag validation. Changed fingerprint preserves 422 IDEMPOTENCY_KEY_REUSED; running/unknown intent preserves 409 IDEMPOTENCY_IN_FLIGHT and its operation reference in typed RETRY details.
3. Fresh grant enters complete(local_write)'s BEGIN IMMEDIATE, reads the actual revision, captures current local policy, validates readiness/immutable identity/version/effective ETag, and performs UPDATE WHERE revision=current. Revision+1 is calculated there. State, event, policy identity and successful operation receipt commit together.
4. Fresh revoke enters the same writer transaction, reads revision there, clears accepted identity and appends its event; it requires no policy or If-Match. Every new revoke advances revision; exact replay does not.
5. Callback/receipt failures roll everything back. Only after rollback may a definite FAILED receipt be recorded; if that write also fails, PENDING remains and cannot be replayed as success. Captured configuration observations survive semantic rejection in a separate configuration-only transaction, without granting permission or appending an event.

The sources explicitly order validation → claim/replay → current policy/preconditions. They do not define every overlapping version/ETag failure. The documented interpretation is configuration/integrity → supplied version → ETag: 503 CONFIGURATION_REQUIRED; then 409 AI_POLICY_CHANGED; then 409 REVISION_CONFLICT. This preserves CONSENT-11's explicit configuration failure despite its changed ETag. Tests cover each mapping and overlap; no precedence is represented as a new product decision.

### RED → GREEN evidence

| Tests / invariant | RED cause | Final mechanism/result |
|---|---|---|
| Structured READY, independent disclosure fields, RFC3339 | Old GET accessed free-form content and exposed float time | Typed model/server time; PASS |
| Incomplete/BLOCKED/missing/free-form and invalid rules/scopes | Old grant had no structural readiness validation | Strict parse and exact v1 readiness; PASS |
| Server digest/repeatability/immutability | Caller digest trusted; no durable first-seen identity | Canonical hash + protected registries; PASS |
| Same-version valid/malformed changes and first-seen malformed correction | Definition changes could be accepted/restored | Durable conflict record/new-version requirement; PASS |
| Stable/policy-sensitive ETag | Persisted revision/digest alone defined ETag | Effective fingerprint; PASS |
| Stale tab/two independent engines/interleaved revoke | Precondition and new revision computed before complete | Writer-local CAS and revision; PASS |
| Changed intent 422/in-flight/replay after revoke | Hardcoded 409; current-state assumptions in old tests | Preserve T014 status/ref; historical event receipt only; PASS |
| Shape/session/origin negatives | Query/body/header syntax gaps | Production app/guard, 422 shape errors, no side effects; PASS |
| State/event failure and receipt failure after event | SQL error escaped; fail-closed latch absent | Actual trigger rollback, FAILED/PENDING never success; PASS |
| Missing history/event/singleton, corrupt definition/digest/receipt | History could be recreated or incomplete receipt authorize | Integrity/evidence checks, false permission; PASS |
| Configuration reversion after rejection/open-connection failure | Second getter lost observed conflict; error escaped HTTP mapping | Capture exact observation, redacted storage mapping; PASS |
| Event snapshots and replace/append-only invariants | No snapshots/triggers; REPLACE bypass | Snapshot columns and INSERT/UPDATE/DELETE protections; PASS |

Initial complete semantic RED: exit 1, 55 failed/14 passed. Intermediate review REDs: 2 failed/75 passed, 5 failed/77 passed, then 8 failed/77 passed. REPLACE probe: 1 failed/1 passed. Final HTTP-schema RED: 3 failures proved valid opaque/empty ETag rejection and optional RETRY discriminator; corrected grammar/schema now pass. Final focused suite: 90 passed, no skipped/deleted failure-path tests. Fixture-only corrections: bootstrap exchange is 204; Alembic downgrade needs a live test connection.

### Exact verification outcomes

| Command | Exit | Outcome |
|---|---:|---|
| python -m pytest backend/tests/test_consent.py -q | 0 | 90 passed, 14.42s |
| python -m pytest backend/tests/test_operations.py -q | 0 | 14 passed; T014 unchanged |
| npm run export:contract (twice) | 0 | OpenAPI/DTO outputs byte-identical |
| npm run test:contract | 0 | 5 passed; includes native structured consent/error schemas |
| python -m mypy backend | 0 | 26 files, no errors |
| python -m ruff check <five T015 handwritten paths> | 0 | Clean |
| python -m ruff format --check <five T015 handwritten paths> | 0 | All five formatted |
| python -m pytest -q | 0 | 232 passed, 24.48s; full report retained separately from focused reports |
| python -m ruff check . | 0 | Clean |
| npm run lint | 0 | No errors; two inherited AppShell fast-refresh warnings |
| npm run typecheck | 0 | Clean |
| npm run build | 0 | Production build successful; output ignored |
| npm run floor:check | 0 | Clean |
| git diff --check | 0 | Clean |
| python -m alembic heads | 0 | Exactly 0003_consent |
| npm run test:frontend:coverage | 0 | 38 tests passed |
| GITLEAKS_BIN=/tmp/t015-security-tools/gitleaks npm run security:secrets | 0 | Zero findings |
| SEMGREP_BIN=/tmp/t015-security-venv/bin/semgrep npm run security:code | 0 | Zero findings |
| OSV_SCANNER_BIN=/tmp/t015-security-tools/osv-scanner npm run security:deps | 0 | Zero findings |
| diff-cover coverage.xml --compare-branch=865740ebd86f17570da138f9820727bdaecd7273 --fail-under=80 --total-percent-float | 0 | 93.99% changed executable lines (316 measured, 19 missing); combined measured total 89.56% vs 86.70% baseline |
| QUALITY_BASE_REF=865740ebd86f17570da138f9820727bdaecd7273 npm run coverage:check | 1 | Existing T053 checker incorrectly requires coverage for generated.ts; generated code is excluded by CONSTRAINTS |
| python -m ruff format --check . | 1 | BASELINE_T007_FORMAT_BLOCKER: only bridge.py/test_bridge.py; byte-identical to HEAD |

Initial baseline: consent 10 passed; operations 14 passed on sequential rerun; mypy/Ruff lint/contract PASS. First concurrent pytest attempt collided on the shared ignored coverage database and was discarded. First typecheck lacked tsc; npm ci --ignore-scripts restored locked dependencies (zero vulnerabilities), then typecheck passed without manifest changes. Scanner commands initially SETUP_FAILED due to missing executables; pinned tools were installed only under /tmp, Gitleaks/OSV artifacts verified against documented hashes, then all three actual scans passed. No aggregate gate or repository-wide formatter PASS is claimed. T062 architecture gate was not required or run.

### Scope, privacy and next task

- Handwritten: only the five T015 allowlisted files. Generated: contracts/openapi.json and frontend/src/shared/api/generated.ts, produced by unchanged T017 tooling; no manual edits. Bookkeeping: this card, tasks/todo.md and docs/changelogs.md.
- Intentionally untouched: OperationLedger/errors.py, T007, T016, T017 generator/tests/client, frontend components, manifests/locks, CONSTRAINTS/spec/API/ADR documents, T019 migration ownership, T052/T062 and their worktrees, real vocabulary and credentials.
- Every consent test blocks/counts real socket connects and asserts zero attempts. Production app/session/database/ledger are used. No policy/consent logging was introduced; raw idempotency keys, browser tokens, prompts, provider responses and learning content are absent from consent state/events and operation receipts. SQL/error contents are redacted.
- Unresolved integration blockers: inherited T007 formatting and T053 generated-file coverage classification. Actual handwritten coverage exceeds the unchanged threshold; checker source/thresholds were not altered. In-place 0003 completion is only for the current unreleased task, not a deployed stamped DB.
- T015 makes T016 dependency-ready assuming T007 is DONE (the current checklist records it DONE). T016 remains TODO; dispatch admission, bridge preflight and provider transport are not implemented here.
- Final verdict for the whole workspace: NOT_READY_TO_COMMIT until the owner-scoped baseline/tooling blockers are resolved. Not committed — authorization not provided.

## Follow-up semantic verification — 30/09/2026 (`Asia/Bangkok`)

This section records the resumed session's changes separately from the preceding session's inherited implementation and evidence. The worktree remains `fix/t015-semantic` at `865740ebd86f17570da138f9820727bdaecd7273`. When another writer was detected, this session stopped without editing; the user confirmed that writer had stopped before work resumed. The settled inherited baseline had 90 passing consent tests. Checks spanning concurrent writes are STALE and are not verification evidence. No inherited T014/T017 quality fixes were redone.

### Additional corrections and ownership

- `backend/app/application/consent.py`: normalize set-like policy collections before hashing every material field; preserve duplicates for readiness validation. Validate immutable definitions/digests and registry identities. Reject duplicate JSON keys at every depth. Require coherent singleton, event and successful receipt evidence before reading or mutating consent. Missing/corrupt storage returns redacted `503 STORAGE_BUSY`, never a fabricated fresh row or a repair-by-grant. Legitimate active-policy changes still derive STALE. CAS predicates include revision/state/accepted identity/time and require exactly one updated row. Ambiguous completion preserves an already committed receipt for historical replay while latching AI permission off. Calendar-valid UTC choice/event timestamps replace epoch storage.
- `backend/app/http/consent.py`: map connection/startup storage failures to the existing storage taxonomy and declare GET's actual 422/503 response schemas. Production `create_app`, SessionGuard, routes and lifecycle remain in use. Existing validation/idempotency behavior is preserved.
- `backend/migrations/versions/0003_consent.py`: finish the unreleased T015 migration in place with text UTC timestamps, state/time checks and duplicate-key protection for the immutable registry. Fresh isolated databases and `0002_operations → 0003_consent` upgrades are tested; no real database was rebuilt and no 0004 migration was created. An already stamped older 0003 database is outside this development-migration compatibility claim.
- `backend/tests/test_consent.py`: add 47 parameterized semantic cases, bringing the suite from 90 to 137. Add a deterministic overlapping writer test with two physical SQLite connections, zero-row CAS, corrupt evidence, ambiguous commit/replay, canonical list ordering, every material digest field, startup failure taxonomy, UTC timestamp checks and all-route guards/provider/transport sentinels.
- `backend/app/main.py` remains byte-identical to the inherited handoff. T014 implementation/tests and T017 handwritten generator/tests remain byte-identical to HEAD. Generated artifacts came only from `npm run export:contract`; the additional generated delta documents GET 422 and typed 503.

The preceding handoff's raw event-time representation and corruption behavior are superseded by these corrections. Historical evidence above belongs to the prior session and is not claimed as this session's output.

### Invariant matrix

| Invariant | Authoritative source | Test proving it | Implementation mechanism | Current evidence |
|---|---|---|---|---|
| A Initial NOT_GRANTED/r0/null identity/time | API singleton; ADR-0003 | get_initial_consent; fresh migration | Seeded singleton; no implicit grant | PASS |
| B Structured policy/null | API AiDisclosurePolicy | ready_grant_structured_disclosure_and_rfc3339 | Explicit typed policy model | PASS |
| C Version pattern | API version validation | request_shape_rejected parameter cases | Strict constrained version | PASS |
| D Complete READY/exact scopes/rules/no reasons | API READY; CONSENT-02/03/11 | incomplete_policy; blocked_missing_or_invalid_policy | One authoritative readiness validator; literal v1 rules | PASS |
| E Complete deterministic canonical digest | API immutable hash | collection_order; every_material_policy_field; server_digest | Sorted UTF-8 JSON and normalized collections; server SHA-256 | PASS |
| F Immutable version/digest | ADR-0003; CONSENT-11 | same_version_mutation; duplicate_registry_version; history protections | Durable definitions/conflicts; triggers and duplicate-safe parser | PASS |
| G Current grant or derived STALE | API state; CONSENT-03/11 | valid_grant_becomes_stale; same_version_mutation | Full policy/status/identity/evidence validation | PASS |
| H Opaque effective-policy ETag | API ETag | etag_covers_effective_policy_status_and_fingerprint | Hash revision and effective fingerprint/status | PASS |
| I Durable grant preconditions | API concurrency | policy_change_after_claim; stale_policy; stale tab | Checks inside T014 writer callback | PASS |
| J Real CAS and rowcount | API concurrency; ADR-0003 | zero_row_cas | Conditional UPDATE and exactly-one-row check | PASS |
| K Independent connection ordering | ADR-0003; T015 | two_independent_connections_grant_cas; overlapping_sqlite_writer_transactions | BEGIN IMMEDIATE with barriers/events and separate engines/connections | PASS |
| L Offline revoke/new intent/replay | API DELETE; CONSENT-04 | redundant_revoke_bumps_revision_without_policy | Policy-independent writer; receipt replay | PASS |
| M DELETE If-Match rejection | API DELETE | request_shape_rejected parameter cases | Validation before claim | PASS, 422 |
| N T014 idempotency taxonomy | API replay; T014 | grant_idempotency_conflict; in_flight | Preserve OperationConflict status/code | PASS, 422/409 |
| O Historical grant replay after revoke | API replay; CONSENT-04 | historical_grant_replay_after_revoke_never_restores_consent | Receipt/event reads only | PASS: G r1, R r2, replay G r1; GET REVOKED r2 |
| P Atomic state/event/success receipt | API atomicity; CONSENT-08 | storage_failure_rolls_back; receipt_failure_after_event_write | Existing T014 complete(local_write) transaction | PASS |
| Q No false success on write failure | CONSENT-08 | unrecordable_storage_failure; ambiguous_failure_after_commit | Rollback or preserve committed receipt; fail-closed latch | PASS |
| R Missing/corrupt singleton/evidence | API storage taxonomy; CONSENT-08 | corrupt_storage_cannot_be_repaired; missing event; BLOB identity | Strict evidence checks; redacted STORAGE_BUSY | PASS, 503 |
| S Immutable event snapshots/action names | ADR-0003; API event | event_snapshots_append_only; replace protections | GRANTED/REVOKED with immutable policy/scopes/rules and triggers | PASS |
| T RFC3339 UTC choice/event time | API timestamps | structured_disclosure_and_rfc3339; event_snapshots; invalid_calendar_time | UTC text storage; strict parse; aware public datetime | PASS |
| U Body/query/header negatives | API validation; CONSENT-09 | request_shape_rejected; get_body_rejected; native schema | Strict HTTP input validation before claim | PASS, 422 |
| V Production security | CONSENT-09; BR-AUTH-09 | production_guards_precede_every_consent_route | create_app/lifespan/SessionGuard | PASS: 401/403, zero side effects |
| W Zero bridge/provider/network | T015; CONSENT-02 | all_consent_routes_have_zero_bridge_provider_and_external_transport_calls | Bridge/httpx sentinels plus autouse socket-connect counter | PASS: zero attempts |
| X T016 boundary | T016 card | Scope/code audit | No admission coordinator/preflight/transport barrier | PASS: T016 remains downstream |

### Test-first and adversarial evidence

- Corrupt evidence/lost-event replay RED: exit 1, six failures; zero-row CAS and the independent writer ordering test already passed and were not labeled RED. Policy ordering/UTC corrected RED: exit 1, six failures; three earlier sentinel fixture errors were corrected and are not semantic evidence.
- Ambiguous completion RED: exit 1, one failure. Final read-only reviewers found duplicate registry keys, BLOB event identities and missing GET 422 schema; their regressions failed (exit 1, four failures) before fixes. Startup storage taxonomy RED: exit 1, one failure; legitimate missing/BLOCKED/new-policy STALE cases already passed. Final GREEN: 137 consent tests, no skipped/deleted negative cases.
- Adversarial review resolved every material T015 question: old receipts cannot write; stale tabs lose; incomplete or mutated policies deny; zero-row UPDATE cannot create events/success; state/event/success receipt commit together; two writers cannot both win; revoke does not need policy; DELETE If-Match is rejected; reuse stays 422; missing/corrupt storage fails closed; timestamps are UTC; security is production; transport counters remain zero. T016 admission was not implemented.

### Final source-frozen checks

Checks ran sequentially where they share coverage reports. The two canonical exports were byte-identical; hashes of all consumed source/generated files stayed unchanged throughout verification. Long checks were awaited without overlapping writes. No command with a nonzero exit is a PASS.

| Command | Exit | Outcome |
|---|---:|---|
| python -m pytest backend/tests/test_consent.py -q | 0 | 137 passed, 21.38s |
| python -m pytest backend/tests/test_operations.py -q | 0 | 14 passed |
| python -m mypy backend | 0 | 26 files, no errors |
| python -m ruff check backend/app/application/consent.py backend/app/http/consent.py backend/tests/test_consent.py | 0 | Clean |
| python -m ruff format --check backend/app/application/consent.py backend/app/http/consent.py backend/tests/test_consent.py | 0 | Three formatted; separate five-path check also exit 0 |
| npm run export:contract | 0 | Canonical generation, repeated byte-identically |
| npm run test:contract | 0 | Five passed |
| python -m alembic heads | 0 | Exactly 0003_consent; no 0004_consent |
| git diff --check | 0 | Clean |
| npm run check:fast | 1 | INHERITED_BASELINE_FAILURE: T007 bridge.py/test_bridge.py formatting |
| npm run check:task | 1 | INHERITED_BASELINE_FAILURE: same first-stage formatting blocker |
| python -m ruff check . | 0 | Clean |
| npm run typecheck | 0 | Clean |
| npm run lint | 0 | Zero errors; two inherited AppShell fast-refresh warnings |
| npm run floor:check | 0 | Clean |
| python -m pytest -q | 0 | 279 passed, 32.95s |
| npm run test:frontend:coverage | 0 | 38 passed |
| QUALITY_BASE_REF=865740ebd86f17570da138f9820727bdaecd7273 npm run coverage:check | 1 | INHERITED_BASELINE_FAILURE: existing T053 checker requires coverage for generated.ts |
| diff-cover coverage.xml --compare-branch=865740ebd86f17570da138f9820727bdaecd7273 --fail-under=80 --total-percent-float | 0 | 364/386 changed executable lines covered, 94.30% |
| npm run build | 0 | Production build successful |
| GITLEAKS_BIN=/tmp/t015-security-tools/gitleaks npm run security:secrets | 0 | Zero findings |
| SEMGREP_BIN=/tmp/t015-security-venv/bin/semgrep npm run security:code | 0 | Zero findings |
| OSV_SCANNER_BIN=/tmp/t015-security-tools/osv-scanner npm run security:deps | 0 | Zero findings |

Measured combined coverage, using the unchanged T053 report parser: 1878/2091 lines = 89.81%, against unchanged 86.70% baseline and 0.5-point tolerance. This separate measurement does not turn the failing coverage command green. `architecture:check` is absent; no command/result was invented and no T062 tooling was copied. Aggregate gates remain blocked by inherited formatting. T007 files and T053 tooling/thresholds were not edited.

**Final status:** T015 DONE; whole workspace `IMPLEMENTATION_DONE_BASELINE_BLOCKED`. Four additional T015 handwritten paths, two canonically regenerated artifacts and three bookkeeping paths; inherited main.py untouched. T016 and CP06 remain pending. Next consent integration owner: T016. No staging, commit, push or external messaging. Not committed — authorization not provided.


## Post-CP05 architecture compatibility — 01/10/2026

Integration candidate: `integration/t015-after-cp05`, starting HEAD `20e4e3ce0aff6040485a4272aa31e54afee4cadc`, with authorized main baseline `bc0ff937b85a62fa395213d93ac4d6a5021cddcc`. The prerequisite transplant and semantic cherry-pick are retained; this is a separate narrow remediation.

T062's **HTTP uses application and platform contracts** failed because `http.consent` imported `persistence.database.StorageError`. The existing service composed in main now exposes `read_consent`, `grant` and `revoke` application methods, owns receipt-read connections and translates known storage/SQLAlchemy/validation failures into existing redacted `ConsentRejected` outcomes. HTTP receives only application snapshots/results and owns HTTP validation/rendering. No concrete import aliases, dynamic imports, broad catches or architecture exceptions were added.

All original ConsentService methods are AST-identical to the starting candidate, including policy validation/canonicalization, durable CAS, immutable evidence, replay and T014 atomic writes. Main, migration, SessionGuard, T007 files, T062 configuration/tests and excluded T014/T017 qualityfix files are unchanged. DELETE's synchronous service call remains in the threadpool. Public schema and both generated artifacts remain byte-identical after two canonical exports.

New regression cases cover configured application read/grant/offline revoke, typed redacted SQL/storage failures with no state/event/operation side effects, HTTP rendering of application refusals without opening storage, and missing-service configuration taxonomy. Existing production guard, zero-network, concurrency, corruption, replay and atomicity regressions remain present.

| Check | Exit | Evidence |
|---|---:|---|
| New boundary tests before implementation | 1 | RED: 10 failed, 3 already passed |
| npm run architecture:check, before remediation | 1 | Exact HTTP -> persistence import; six contracts kept, one broken |
| npm run architecture:check, after remediation | 0 | Seven kept contracts, zero violations; 40 tests |
| Actual Grimp direct-import graph audit | 0 | HTTP -> persistence/adapters and application -> HTTP/main absent |
| python -m pytest backend/tests/test_consent.py -q | 0 | 150 passed, including existing security/network/race cases |
| python -m pytest backend/tests/test_operations.py -q | 0 | 14 passed |
| python -m mypy backend | 0 | 26 files clean; initial new-test union annotation diagnostics corrected |
| Focused Ruff lint/format over application/http/main/consent tests | 0 | Clean; no suppressions |
| npm run test:contract | 0 | Five passed |
| npm run export:contract, twice | 0 | No generated drift, byte-identical |
| python -m alembic heads | 0 | One head: 0003_consent |
| python -m pytest -q | 0 | 332 passed; real architecture test now passes |
| python -m ruff check . | 1 | INHERITED_BASELINE_FAILURE: unchanged test_operations.py E501 / test_contract.py RUF100 |
| npm run typecheck / lint / build / floor:check / check:fast | 0 each | Clean; lint retains two inherited warnings |
| QUALITY_BASE_REF=bc0ff937 npm run check:task | 1 | All 332 tests pass; existing generated.ts coverage classification blocks the complete candidate |
| QUALITY_BASE_REF=20e4e3c npm run coverage:check | 0 | Remediation only: changed 100.00%, total 89.89%; unchanged thresholds |
| Pinned security:secrets / security:code / security:deps | 0 each | Zero findings |
| git diff --check | 0 | Clean |

**Handoff:** architecture compatibility fixed and T015 semantics remain DONE in the candidate; **NOT PROMOTED** because the required complete-candidate check:task gate still fails on T053's generated-file classification. That tooling is outside this remediation's authorized scope and was not changed. Remediation-only coverage does not convert the aggregate failure into PASS. Main remains at `bc0ff937`; T016/CP06 are pending and no push is authorized.

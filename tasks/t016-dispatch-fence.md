# T016: Consent admission fence trước AI dispatch

**Task ID:** `T016`  
**Title:** Consent admission fence trước AI dispatch  
**Status:** `DONE`

**Goal:** Consent admission fence trước AI dispatch. Revoke-before-admission and revoke/regrant deny old intent; preflight denied by missing consent.  
**Suggested model:** GPT-6 Astra  
**Authorized scope:** Four T016 implementation/test/migration files plus two explicitly authorized historical migration-test remediations; common bookkeeping below.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/api-contract.md](../docs/api-contract.md) §6, CONSENT-05/06/12, BR-AUTH-09

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Verification below uses the current T015/T007 implementation and authorized base `de9725ba1e79658f5bebc583ba09422692e5df9c`.

## Dependencies

- [T015](t015-consent-api.md)
- [T007](t007-bridge-policy-consent-adapter.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

- `backend/app/application/ai_admission.py`
- `backend/app/platform/bridge_port.py`
- `backend/tests/test_ai_admission.py`
- `backend/migrations/versions/0005_ai_admission.py` — explicitly authorized additive admission schema after `0004_vocabulary`.
- `backend/tests/test_consent.py` — explicitly authorized historical migration-test maintenance only.
- `backend/tests/test_vocabulary_storage.py` — explicitly authorized historical migration-test maintenance only.

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- One coordinator service shared lookup/quiz/feedback; durable CAS captures revision/digest/scope/selected route before transport admission. No DB transaction while awaiting cloud. Revocation does not recall admitted bytes.
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [x] Revoke-before-admission and revoke/regrant deny old intent; preflight denied by missing consent.
- [x] Admitted-before-revoke may finish exactly once, no follow-up; selected model/route matches policy.
- [x] Two-process SQLite race tests prove fence, not merely process mutex.

## Test cases

1. Barriers both orderings; restart after admission UNKNOWN no replay.
2. Same-version mutation, unexpected model, route drift, storage failure.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
python -m pytest backend/tests/test_ai_admission.py -q
```

## Expected output

- Revoke-before-admission and revoke/regrant deny old intent; preflight denied by missing consent.
- Focused commands đạt kết quả/exit code ghi trong criteria; negative probe phải fail đúng reason. Documentation tasks có conformance report thay cho application-test pass.
- Evidence ghi command, exit code, môi trường và artifact. Thiếu Windows/browser/provider environment là PENDING; không hoàn tất gate thiếu evidence.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Completion evidence — 01/10/2026

Documentation follows the repository-required documentation-and-adrs skill. This implements the existing ADR-0003 admission/revocation decision; no HTTP endpoint or public contract is added.

### Durable design and operation ownership

- `AiAdmissionCoordinator` shares the same flow for LOOKUP, QUIZ_GENERATION and WRITING_FEEDBACK. Local precheck captures the exact consent revision, policy version/digest and existing T015 `AiDispatchRule` (`scope`, `providerLabel`, `modelId`, `route`, `billingMode`) before bridge preflight. Missing/revoked/stale/corrupt consent or invalid policy denies before any bridge call. Profile drift denies inference; the caller cannot substitute the selected rule.
- Final admission uses the established `sqlite_begin_immediate=True` writer transaction. It re-reads durable consent and requires GRANTED plus the captured revision/version/digest, revalidates policy/rule identity, and inserts the admission evidence in the same transaction. Commit and connection closure precede `dispatch_chat`; no process-local lock or network call participates in the transaction.
- Migration `0005_ai_admission` has `down_revision="0004_vocabulary"` and creates `ai_operation_admission`. Its eleven columns contain only operation ID, consent revision, policy version/digest, scope, provider/model/route/billing, ADMITTED state and UTC admission time. The operation ID is the primary key and references `operations.operation_id`; the consent revision references `ai_consent_event.revision`. CHECK constraints restrict authorization identity/state, and triggers forbid duplicate/REPLACE/update/delete of evidence. No raw payload, response, token or credential is stored. Downgrade refuses history deletion.
- The coordinator uses the existing OperationLedger's claimed PENDING operation. The caller retains completion/reconciliation ownership; restart recovery remains PENDING -> UNKNOWN. Existing admission evidence rejects duplicate/re-entry even before recovery, including uncertain outcomes and deadline exhaustion after admission commit. This deliberately favors no second billable dispatch; no automatic retry is introduced.
- The same absolute monotonic deadline is checked before preflight, admission and dispatch and after transport. No timeout reset or fallback occurs.

### Deterministic race and migration results

| Scenario | Durable evidence | Dispatch count |
|---|---|---:|
| Revoke commits before final admission | Denied; no admission row | 0 |
| Revoke rev2 + regrant rev3 after capturing rev1 | Denied by revision mismatch; no admission row | 0 |
| Admission commits before revoke | Admission row retained; original completes; later request denied | 1 |
| Two-process revoke first | Denied; no admission row | 0 |
| Two-process admission first | One admission/dispatch; later request denied | 1 |

The spawn-process tests share one temporary SQLite file, use bounded Event/Pipe waits and pause at final BEGIN or fake transport without sleeps. In the admission-first case, the parent commits revoke while the child remains blocked in fake dispatch and the admission row is already visible. This proves the writer transaction is closed across transport. All inference interactions use fakes.

The upgrade test explicitly prepares a `0004_vocabulary` database with existing vocabulary and operation data, upgrades to `0005_ai_admission`, repeats initialization, checks retained data, exact admission columns, foreign keys and disabled downgrade. The final repository has exactly one head: `0005_ai_admission`.

Historical tests now require exactly one head and assert their own direct predecessor: `0003_consent -> 0002_operations`, `0004_vocabulary -> 0003_consent`. They explicitly upgrade to their historical revision twice and check the stored revision/tables/history there, then preserve startup/repeat checks against the discovered current head. No latest-revision literal replaces historical assertions, and no tests are skipped or weakened. Direct Alembic metadata verification also confirms `0005_ai_admission -> 0004_vocabulary`.

### RED/GREEN and exact command outcomes

- Original T016 test-first RED: `python -m pytest backend/tests/test_ai_admission.py -q` exited 2 because the coordinator module did not yet exist. Final GREEN: 60 passed.
- Remediation RED before either historical test edit: consent suite exited 1 (149 passed, one failure at `get_heads()==["0003_consent"]`); vocabulary suite exited 1 (15 passed, one failure at initialization revision `0004_vocabulary` versus actual `0005_ai_admission`).
- Linux/Python 3.12.3; fake bridge and temporary SQLite only. Focused gates below passed after test remediation. The complete task gate independently reran all 424 Python tests, frontend coverage, security and architecture.

| Command | Exit | Result |
|---|---:|---|
| `python -m pytest backend/tests/test_consent.py -q` | 0 | 150 passed |
| `python -m pytest backend/tests/test_vocabulary_storage.py -q` | 0 | 16 passed |
| `python -m pytest backend/tests/test_ai_admission.py -q` | 0 | 60 passed; all critical races and UNKNOWN recovery re-proven |
| `python -m pytest backend/tests/test_operations.py -q` | 0 | 14 passed |
| `python -m pytest backend/tests/test_bridge.py -q` | 0 | 14 passed |
| `python -m mypy backend` | 0 | 33 source files |
| `python -m ruff check backend/tests/test_consent.py backend/tests/test_vocabulary_storage.py backend/app/application/ai_admission.py backend/app/platform/bridge_port.py backend/tests/test_ai_admission.py backend/migrations/versions/0005_ai_admission.py` | 0 | All scoped checks pass |
| `python -m ruff format --check backend/tests/test_consent.py backend/tests/test_vocabulary_storage.py backend/app/application/ai_admission.py backend/app/platform/bridge_port.py backend/tests/test_ai_admission.py backend/migrations/versions/0005_ai_admission.py` | 0 | Six files formatted |
| `python -m alembic heads` | 0 | Exactly `0005_ai_admission` |
| `python -m pytest -q` | 0 | 424 passed |
| `npm run test:frontend:coverage` | 0 | 38 passed |
| `QUALITY_BASE_REF=de9725ba1e79658f5bebc583ba09422692e5df9c npm run coverage:check` | 0 | Changed 97.22%; total 91.63% |
| `QUALITY_BASE_REF=de9725ba1e79658f5bebc583ba09422692e5df9c npm run check:task` | 0 | Full task gate passes |
| `npm run architecture:check` | 0 | Seven contracts kept, zero broken; 40 tests passed |
| `npm run check:fast` | 0 | Pass; two existing frontend lint warnings |
| `npm run security:secrets` | 0 | Zero findings |
| `npm run security:code` | 0 | Zero findings |
| `npm run security:deps` | 0 | Zero findings |
| `npm run export:contract` (twice) | 0 / 0 | Both generated files remain byte-identical to base |
| `python -m ruff check .` | 1 | INHERITED_BASELINE_FAILURE: RUF100 at `scripts/tests/test_contract.py:34` |
| `git diff --check` | 0 | Clean |

Coverage minimum remains 80%, total baseline 86.70% and tolerance 0.50 points; no threshold, exclusion or tooling changes. Full Ruff is not reported as PASS: an archive of exact base `de9725ba1e79658f5bebc583ba09422692e5df9c` produces the same sole finding. Its untouched file is byte-identical to base (SHA-256 `1aca8c740aef432726f848017a4f7c361308fa974f6ab4458dd407846de8430c`). This inherited finding is explicitly accepted for this remediation by the user.

### Handoff

T016 DONE; CP06 remains PENDING for its separate integration/checkpoint review. Existing consent/operations/bridge implementation, historical migrations, HTTP/main/persistence, generated contracts and quality/security configuration remain untouched. There was no real inference, staging, commit or push. Next action: separately authorized pre-commit review; downstream AI features must claim/reconcile/complete operations through the existing ledger when integrating this coordinator.

## Risk

- **Level:** `Critical`.
- Sai boundary có thể gửi dữ liệu/cost không được phép hoặc mất lịch sử học.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- Không có coherent commit/transport admission ordering → dừng; không đóng bằng fake test.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`feat(T016): consent admission fence trước ai dispatch`

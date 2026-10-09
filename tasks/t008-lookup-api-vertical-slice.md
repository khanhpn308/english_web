# T008: POST lookup trả preview đã validate

**Task ID:** `T008`
**Title:** POST lookup trả preview đã validate
**Status:** `DONE` (code merged into `main` at `b46ab6538`; final acceptance `PENDING`)
**Coding completion policy (2026-10-09):** Implementation integrated into `main`; final project acceptance is pending. Historical TODO, environment limitations and unchecked acceptance cases below remain evidence history, not test PASS.
**Goal:** POST lookup trả preview đã validate. Valid preview có meaning/example fields; missing IPA/link có nhãn, không hallucinated verified.
**Suggested model:** GPT-6 Astra
**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay trong danh sách. Nếu vượt khoảng 2 giờ hoặc phạm vi này, tách task trước khi làm tiếp.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/spec.md](../docs/spec.md) FR-CAP; AC-02/03/05/26/33
- [docs/api-contract.md](../docs/api-contract.md) lookup

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T007](t007-bridge-policy-consent-adapter.md)
- [T014](t014-operations-idempotency.md)
- [T016](t016-dispatch-fence.md)
- [T019](t019-vocabulary-schema.md)
- [T017](t017-typed-api-client.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

- `backend/app/enrichment/lookup.py`
- `backend/app/http/lookups.py`
- `backend/app/enrichment/prompts/lookup.txt`
- `backend/tests/test_lookups.py`
- `backend/app/main.py`

### R3-B07 Scope Authorization Record

| File | Owner Task | Classification | Rationale & Minimum Necessary Change |
|---|---|---|---|
| `backend/app/application/ai_admission.py` | T016 | `REQUIRED_SHARED_REMEDIATION` | Deepcopy caller payload immediately before validation/await in `dispatch()` to eliminate race where caller mutates dict and injects unapproved fields. |
| `backend/app/vocabulary/repository.py` | T019 | `REQUIRED_SHARED_REMEDIATION` | Accept external `connection` parameter in `create_preview()` so preview + operation SUCCEEDED receipt commit atomically in the ledger transaction. |
| `backend/app/http/errors.py` | T003/T014 | `REQUIRED_SHARED_REMEDIATION` | Pass structured `details` dictionary directly to `JSONResponse` error envelope. |
| `scripts/export_contract.py` | T017 | `REQUIRED_SHARED_REMEDIATION` | Add `AI_CONSENT` schema variant to `ErrorDetails` discriminated union to conform to OpenAPI spec. |
| `scripts/tests/test_contract.py` | T017 | `REQUIRED_SHARED_REMEDIATION` | Add contract test asserting `AI_CONSENT` variant in exported schema. |

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- Dùng port fake provider và admission đã kiểm chứng. Preview có operation/owner session, prompt version, per-field provenance; không ghi card/source. Operation receipt lưu lookup reference để reload, không prompt trong operation metadata. Đăng ký đúng route/service vào app factory; TestClient và OpenAPI export dùng app factory production, không app test riêng bỏ security guards.
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [x] Valid preview có meaning/example fields; missing IPA/link có nhãn, không hallucinated verified.
- [x] Consent denied zero preflight; malformed output/timeout không success hoặc queued retry.
- [x] Idempotent same intent một dispatch; no explicit save = zero card/source.

## Test cases

1. Valid/partial/hostile response fixtures; Unicode 1–80 term bounds.
2. Lost response/replay; payload sentinel unrelated history.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
python -m pytest backend/tests/test_lookups.py -q
npm run test:contract
```

## Expected output

- Valid preview có meaning/example fields; missing IPA/link có nhãn, không hallucinated verified.
- Focused commands đạt kết quả/exit code ghi trong criteria; negative probe phải fail đúng reason. Documentation tasks có conformance report thay cho application-test pass.
- Evidence ghi command, exit code, môi trường và artifact. Thiếu Windows/browser/provider environment là PENDING; không hoàn tất gate thiếu evidence.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Risk

- **Level:** `High`.
- Sai contract/concurrency/persistence có thể làm mất dữ liệu, ghi sai tiến độ hoặc tạo kết luận kiểm chứng sai.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- Cần hidden fallback hoặc format chưa được T013 freeze → dừng.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`feat(T008): post lookup trả preview đã validate`


## Round-4 remediation handoff — 03/10/2026 (Asia/Bangkok)

Round-4 shared remediation authorization: [t008-r4-shared-remediation.md](t008-r4-shared-remediation.md).
This authorization is prospective for the new remediation diff; it does not change the old audit
or retroactively authorize candidate `9ed91b9`. T008 is not DONE and integration is not authorized.

Base/HEAD: `9ed91b9762f7fd859e81ba9e743fb18a91030509`; worktree
`/home/khanh/projects/vocabularies-t008-r4-remediation`; branch `fix/t008-r4-remediation`.
No commit or push is authorized. The frozen deliverable is an uncommitted diff plus a SHA-256
file manifest in `/tmp/t008-r4-freeze-manifest.json`; HEAD alone does not identify its contents.

Lifecycle ownership follows ADR-0005 C013-10 and T016 caller ownership: the service retains
claim, snapshot/admission, parse, completion, preview-load and HTTP serialization workers.
The request returns at its absolute deadline and signals abort once. Its cancellation cannot
recancel terminalization. Lifespan drains owners before closing storage. Mandatory local cleanup
may settle after the response; it never retries inference. Before a claim outcome is known,
there is no truthful operation reference to return; optional RETRY.operationId is supplied when
known. A cancellation before transport is FAILED; uncertainty after transport is UNKNOWN.
The existing ledger-owned preview/SUCCEEDED transaction and eligibility listeners are retained.
A result committed before expiry remains replayable when later response rendering times out.

Durable storage failure is surfaced as redacted STORAGE_BUSY, retained for a sanitized drain
failure, and denies further AI admission. Actual unavailable storage cannot promise a terminal
write; existing restart recovery remains the fallback. No error/prompt/response bytes are logged.

| Invariant | Contract | RED proof | Production mechanism / GREEN proof |
|---|---|---|---|
| Claim cancellation / replay | C013-10; API §8 | real claim commit held, cancellation leaves PENDING | retained claim outcome, FAILED; same key replays without dispatch |
| Pre-dispatch cancellation | C013-10; T016 | claim RED plus admission/transport controls | settle admission worker; guard transport entry; FAILED |
| Post-dispatch / repeated cancellation | C013-10 | cleanup gate cancelled twice leaves PENDING | owned terminalization, UNKNOWN; repeated request cancellation cannot reach owner |
| Body deadline | API bounded budgets | blocked ASGI receive misses safety bound | same deadline around receive; typed503, security headers retained |
| Claim/admission/provider deadline | C013-10 | held claim misses deadline; existing hung-provider oracle | bounded request await; retained local workers; no new dispatch after abort |
| Parsing/completion/load/HTTP rendering | C013-10 | held stages / real render yield late200 or exceed bound | retained workers and final deadline check; predeadline receipts remain immutable |
| Late worker error | C013-10 | late parser/admission errors overwrite TIMEOUT category | timeout precedence through reject; FAILED/UNKNOWN TIMEOUT503 |
| Required-nullable consent / required TS | API ErrorDetails | actual Draft2020 validation gives missing-valid/null-invalid; optional TS | canonical anyOf string/null + required; semantic validation and required TS assertion |
| High/low/embedded surrogate | C013-08 | escaped JSON reaches fingerprint and returns500 | normalized input rejects surrogates;422/zero claims/provider/previews |
| Astral/NFC/1/80/81 | C013-08 | positive controls / preserved NFC oracle | valid scalar Unicode accepted; NFC replay and normalized bounds preserved |
| Invalid UTF-8 models/chat | API BR-AUTH / T007 | actual MockTransport gives503 storage classification | typed adapter error ->502; no retry/preview; malformed JSON and valid controls |
| Bounded concurrency evidence | remediation card §6/14 | AST finds Barrier/Future waits without bounds | barrier/future bounds, event/task bounds, shielded drain wait; real DB mechanisms retained |

Pre-freeze executable evidence: baseline lookup 41 and contract 7 pass after pinned npm install;
new boundary RED 9 failures, consent RED 2 failures, lifecycle stage RED 4 failures, adversarial
snapshot/details RED 2 failures, rendering RED 2 failures, late parser/admission RED 1 each.
Focused final implementation rehearsal: lookup 82 pass; combined lookup/operations/bridge/admission
167 pass before the final null/drain/admission-error additions; mypy 51 files, full Ruff,
format 191 files and TS typecheck pass. Contract 9 pass; generated diff only consent semantics.
Secrets, Semgrep and OSV each report zero findings; architecture 7 kept/0 broken plus 40 tests.
An early full rehearsal failed 13 (964 passed): two test-local 0.1s rendezvous failures corrected
with 0.5s local budgets, and eleven genuine Windows guards. That rehearsal is not final evidence.
Production timeout remains 120s. Final gates run after freeze; exact commands, exits and durations
are recorded in `/tmp/t008-r4-final-results.json` and the final remediation report.

Windows verification: genuine Windows PowerShell responds (Windows NT10.0.26200), but Python
resolves only to an uninstalled WindowsApps alias; no native Python/py launcher was found.
`ENVIRONMENT_BLOCKED_WINDOWS_VERIFICATION`; eleven native filesystem/ACL tests remain mandatory.
OSV2.6.0 canonical normal-network metadata scan is available and clean; no dependency changes.

Files intentionally untouched: lookup prompt; vocabulary repository; HTTP errors; operation ledger;
all migrations; dependencies/lockfiles; frontend UI; security/CI tooling; old audit records; T027;
main and the frozen lookup worktree. Conditional session edit only classifies lookup receive timeout
through existing security headers. Shared operation-test changes are only bounded waits.
Next action: obtain genuine Windows evidence and perform a separately assigned independent re-audit
of this exact uncommitted snapshot (or a later explicitly authorized commit). No integration verdict
is issued by this implementation worker.

Verification resumed on 04/10/2026 after the development environment restarted. Prior /tmp
evidence and running processes were no longer present; final verification is rerun from a new
freeze manifest. The unrelated historical changelog line changed accidentally during spacing
cleanup was restored byte-for-byte from the audited base before this new freeze. Earlier
interrupted final results are not claimed as current executable evidence.

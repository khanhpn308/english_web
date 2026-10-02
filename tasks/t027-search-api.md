# T027: Search/detail API có cursor và filters

**Task ID:** `T027`  
**Title:** Search/detail API có cursor và filters  
**Status:** `TODO`  
**Goal:** Search/detail API có cursor và filters. GET collection/default50/max100 and GET detail match schemas.  
**Suggested model:** Gemini  
**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay trong danh sách. Nếu vượt khoảng 2 giờ hoặc phạm vi này, tách task trước khi làm tiếp.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/api-contract.md](../docs/api-contract.md) word-forms, §7
- [docs/spec.md](../docs/spec.md) AC-07/13

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T026](t026-search-projection.md)
- [T006](t006-api-core-contract-foundation.md)
- [T017](t017-typed-api-client.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

- `backend/app/http/search.py`
- `backend/app/vocabulary/search_service.py`
- `backend/tests/test_search_api.py`
- `backend/app/main.py`

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- Allowlist sorts/filters, signed cursor bound query+source revision; stable ID tie-break. Detail includes source health and field verification. Đăng ký đúng route/service vào app factory; TestClient và OpenAPI export dùng app factory production, không app test riêng bỏ security guards.
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [ ] GET collection/default50/max100 and GET detail match schemas.
- [ ] Expired/modified/query-mismatched cursor →409; unknown filter/sort→422; safe404.
- [ ] Only active valid sources supply current study text; history remains distinct.

## Test cases

1. Pagination ties no duplicates/omissions; filters noteDate/POS/verification/source.
2. External edit invalidates cursor; SQL payload doesn't alter query.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
python -m pytest backend/tests/test_search_api.py -q
npm run test:contract
```

## Expected output

- GET collection/default50/max100 and GET detail match schemas.
- Focused commands đạt kết quả/exit code ghi trong criteria; negative probe phải fail đúng reason. Documentation tasks có conformance report thay cho application-test pass.
- Evidence ghi command, exit code, môi trường và artifact. Thiếu Windows/browser/provider environment là PENDING; không hoàn tất gate thiếu evidence.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Risk

- **Level:** `Medium`.
- Sai wiring/tooling có thể khiến task sau dùng command hoặc UI state không chính xác.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- Raw SQL sort/path from browser or unbounded result list → dừng.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`feat(T027): search/detail api có cursor và filters`

## Worker verification evidence — 02/10/2026

- Owner-authorized scope extension added only `INVALID_QUERY` and `CURSOR_EXPIRED` mappings in `backend/app/http/errors.py`.
- Production `create_app()` wires `/api/v1/word-forms` collection/detail routes and a process-local HMAC cursor key; no session/config files changed.
- `python -m pytest backend/tests/test_search_api.py -q`: 5 passed.
- `python -m pytest backend/tests/test_search_index.py -q`: 25 passed.
- `python -m pytest backend/tests/test_session.py -q`: 11 passed.
- `npm run export:contract` twice produced byte-identical OpenAPI/TypeScript artifacts; `npm run test:contract`: 5 passed.
- `python -m pytest backend/tests -q`: T027 tests pass; inherited Windows-native tests fail closed on Linux and remain pending native Windows evidence.
- Status remains `TODO` pending independent audit; changes are intentionally uncommitted.


## Fix Worker remediation — 03/10/2026

- Scope: owner additionally authorized `backend/app/vocabulary/search_index.py` and `backend/tests/test_search_index.py` solely for a shared bounded candidate iterator. Repository, normalization, models, session, migrations and contract tooling remain untouched.
- T078 Fix skills read: `git-workflow-and-versioning`, `incremental-implementation`, `test-driven-development`, `api-and-interface-design`, `security-and-hardening`, `documentation-and-adrs`, `debugging-and-error-recovery`; resolved at `/home/khanh/.gemini/config/plugins/agent-skills/skills/<name>/SKILL.md`. Applied to isolated Git/scope, RED/GREEN increments, API/error boundaries, cursor/input hardening, root-cause diagnosis and this handoff.
- RED: `python -m pytest backend/tests/test_search_api.py backend/tests/test_search_index.py -q --no-cov` exited 1: 18 failed / 37 passed. Failures reproduced relationship staleness, missing detail POS, stored-version cursor behavior, noncanonical signature acceptance, string/date bounds and omitted candidates; new iterator tests failed because that primitive was absent.
- T026 now shares matching/scoring through `iter_search_candidates()`, streams rows ordered by form ID/meaning index and retains one best result per form. Legacy `search()` keeps its materialized score/lemma/POS/ID ordering and limit/offset interface.
- F1: removed full-form/source caches; incremental fingerprint includes joined relationship membership/status/note date plus source revisions/ETags and form revisions. Existing repository reads provide this information; no repository extension was needed.
- F2/F5: detail includes required `partOfSpeech`; content filters cap at 4,096 code points; noteDate requires ASCII shape and an actual calendar date. Malformed dates retain `400 INVALID_QUERY`.
- F3: fingerprint uses actual stored projection version and validates cursors before candidate iteration. Owner clarified first-page incompatibility as `503 CONFIGURATION_REQUIRED`; cursor incompatibility remains `409 CURSOR_EXPIRED`. Refresh is lazy so an incompatible stored projection survives app startup as a typed API failure rather than a startup crash. No incompatible projection is silently rebuilt.
- Additional F3 RED: first-page incompatibility (2 failures) and app restart with incompatible projection (1 failure); corresponding focused GREEN runs passed.
- F4: canonical URL-safe no-padding base64 enforced by strict decode/re-encode equality; deterministic signature-byte tampering and unused-padding-bit probes replace the random last-character test.
- F6: arbitrary candidate cap removed. T027 consumes the complete iterator and uses a heap retaining at most pageSize+1 candidates; canonical IDs read in bounded batches of 64. No full canonical population/result cache remains. Search requests serialize projection refresh/iteration; revision evidence is rechecked before returning results.
- Generated artifacts were regenerated exclusively through T017 `npm run export:contract`. Combined regeneration is still required after serialized T008/T027 integration.
- Final task-local verification completed; evidence follows. Status remains TODO and uncommitted pending independent F1–F6 re-audit.


### Final verification and source freeze

| Command | Exit | Result |
|---|---:|---|
| `python -m pytest backend/tests/test_search_index.py -q --no-cov` | 0 | 32 passed |
| `python -m pytest backend/tests/test_search_api.py -q --no-cov` | 0 | 49 passed |
| `python -m pytest backend/tests/test_session.py -q --no-cov` | 0 | 11 passed |
| `python -m ruff check backend/app/vocabulary/search_index.py backend/app/http/errors.py backend/app/http/search.py backend/app/vocabulary/search_service.py backend/app/main.py backend/tests/test_search_index.py backend/tests/test_search_api.py` | 0 | PASS |
| `python -m ruff format --check backend/app/vocabulary/search_index.py backend/app/http/errors.py backend/app/http/search.py backend/app/vocabulary/search_service.py backend/app/main.py backend/tests/test_search_index.py backend/tests/test_search_api.py` | 0 | 7 files formatted |
| `python -m mypy backend` | 0 | 51 source files; no issues |
| `npm run export:contract` | 0 | OpenAPI/DTO regenerated through T017 |
| `npm run test:contract` | 0 | 5 passed; schema/DTO equality and determinism |
| `git diff --check` | 0 | PASS |

- Initial scoped lint found formatting/import issues, then a nested-with style issue; corrected within the allowlist. Final scoped checks above passed. RED failures remain recorded separately, not reported as PASS.
- Seven scoped Python files and both generated artifacts retained identical SHA256 hashes during final verification. A style-only correction changed test_search_api.py after the first freeze; the freeze was renewed and affected API/static checks rerun. Unchanged T026/session/contract evidence remains valid.
- Final source/generated hashes:

| File | SHA256 |
|---|---|
| `backend/app/http/errors.py` | `c9e266d9d0fd08646b11c1db89e111b5aa1fe7821875b54b40cb3b965d3e417b` |
| `backend/app/http/search.py` | `33bc5c3869483e64afbdc169d6601cc41b17e794b1112dedbfea8a534e0e4b23` |
| `backend/app/main.py` | `69087920468f100866b8ea8fe3c58f4f4ea91105acb31da667d5f6d04a2e6a37` |
| `backend/app/vocabulary/search_index.py` | `9f156c88bd720b9d942c0c2a9432748847fd60e0d38f6d1b02f0a5cee74c8833` |
| `backend/app/vocabulary/search_service.py` | `4d918bb13b2615d76130c46e43233ceacdd53650d579301f28eca3ac3547fc99` |
| `backend/tests/test_search_api.py` | `b55b14db39beebbaef4d2fabf3ea3c368df0a374d1cb6d8bf6d3c3a89d8bc1b7` |
| `backend/tests/test_search_index.py` | `98eef6d64f4923ca76e259a66b57d3f3d471e96ee1b6cb7c832cad241d18fa29` |
| `contracts/openapi.json` | `6d19c5383215471476236a4b2ee77e20738284a4a084049085d741601b547c66` |
| `frontend/src/shared/api/generated.ts` | `bfbb59cc28135bdaf9b65246329fc45a490101372ec500005c043ac9aa5deba2` |

- F1–F6: PASS. Scope audit: 11 authorized changed/untracked files; errors.py extension remains only two approved mappings; no other dependency-owned files changed. main.py is unchanged from the earlier T027 Worker output. No T008 output imported; generated paths added are exclusively the two word-form read endpoints.
- Frozen base/HEAD: `c77a911cb58c4c76bc7daf87adb19dffdea78290`; main drift observed at `035430d668f1f754afd38e3cca9d630eb90a69a7`. No merge/rebase or Git mutation.
- Windows-native evidence: DEFERRED_TO_WINDOWS_RELEASE_EVIDENCE. No full pytest/check:task/frontend coverage/security suite was run in this focused remediation.
- Full-population scans trade latency for complete bounded-memory selection; Windows 100k performance/release evidence remains a separate gate, not claimed here. Legacy SearchIndex.search() remains materialized by design.
- Handoff: READY_FOR_T027_RE_AUDIT. Card status remains TODO pending independent audit; no commit/push/merge. Integration must remain serialized with T008 and regenerate the combined contract.

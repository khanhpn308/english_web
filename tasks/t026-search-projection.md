# T026: Vietnamese normalized n-gram projection

**Task ID:** `T026`  
**Title:** Vietnamese normalized n-gram projection  
**Status:** `DONE`
**Goal:** Vietnamese normalized n-gram projection. Vietnamese infix match incl short query exact/folded; distinct POS links preserved.  
**Suggested model:** GPT-6 Astra  
**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay trong danh sách. Nếu vượt khoảng 2 giờ hoặc phạm vi này, tách task trước khi làm tiếp.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/spec.md](../docs/spec.md) FR-VOC-01
- [docs/api-contract.md](../docs/api-contract.md) §7

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T019](t019-vocabulary-schema.md)
- [T013](t013-contract-conformance.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

- `backend/app/vocabulary/search_index.py`
- `backend/app/vocabulary/normalization.py`
- `backend/tests/test_search_index.py`

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- NFC/casefold/exact+accent folded projection of meaningsVi; FTS5 optional, no correctness dependency. Version index, bounded batch updates, source revision consistency. Triển khai pure projection/update port trước live sync; integration sync T023 gọi port này.
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [x] Vietnamese infix match incl short query exact/folded; distinct POS links preserved.
- [x] Index changes with source updates/invalidation; rebuilding projection never removes durable history.
- [x] Queries parameterized; index version mismatch not silent empty.

## Test cases

1. Combining marks/đ-accent cases, one-character query, SQL metacharacters.
2. Missing/invalid source, index rebuild on temp DB.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
python -m pytest backend/tests/test_search_index.py -q
```

## Verification evidence (01/10/2026)

- `python -m pytest backend/tests/test_consent.py backend/tests/test_search_index.py -q`: Exit 0, 175 passed in 31.04s. `test_consent.py` uses dynamic Alembic head discovery (`ScriptDirectory.get_heads()`, `current_head = heads[0]`) and preserves explicit T015 lineage (`get_revision("0003_consent")` down to `"0002_operations"`).
- `python -m pytest backend/tests/test_search_index.py -q`: Exit 0, 25 passed in 1.22s. Line coverage: `normalization.py` 100%, `search_index.py` 95%.
- `python -m ruff check backend/app/vocabulary/search_index.py backend/app/vocabulary/normalization.py backend/tests/test_search_index.py backend/tests/test_consent.py`: Exit 0, zero diagnostics.
- `python -m ruff format --check backend/app/vocabulary/search_index.py backend/app/vocabulary/normalization.py backend/tests/test_search_index.py backend/tests/test_consent.py`: Exit 0, all files formatted.
- `python -m mypy backend/app/vocabulary`: Exit 0, zero issues found in 4 source files.
- `python scripts/check_constraints.py floor`: Exit 0, `floor: clean`.
- `git diff --check`: Exit 0.
- `python -m pytest`: Exit 0, 389 passed in 78.43s.
- `npm run test:frontend:coverage`: Exit 0, 4 test files, 38 tests passed.
- `npm run coverage:check`: Exit 0, changed 97.66% (min 80.00%), total 91.85% (baseline 86.70%).
- `npm run architecture:check`: Exit 0, 7 kept, 0 broken, 40 passed.
- `npm run security:secrets`: Exit 0, 0 findings (Gitleaks 8.30.1).
- `npm run security:code`: Exit 0, 0 findings (Semgrep 1.178.0).
- `npm run security:deps`: Exit 0, 0 findings (OSV-Scanner 2.6.0).
- `npm run check:task`: Exit 0.
- Negative probes:
  - Projection version mismatch raises `ProjectionVersionMismatchError`, distinguishable from empty search result `[]`.
  - Stale source revision raises `StaleSourceRevisionError`, keeping existing projection intact.
  - SQL injection input (`'; DROP TABLE ... --`, `' OR 1=1 --`) treated strictly as literal data without injection or syntax errors.
  - LIKE wildcard metacharacters (`%`, `_`) escaped and treated as literal characters.
  - Forms with only INVALID or MISSING sources excluded from active search results.
  - Semantic synonyms / guesses not in text return zero results (no semantic guessing).
  - Examples translations alone do not match Vietnamese meaning search (meanings_vi boundary preserved).

## Expected output

- Vietnamese infix match incl short query exact/folded; distinct POS links preserved.
- Focused commands đạt kết quả/exit code ghi trong criteria; negative probe phải fail đúng reason. Documentation tasks có conformance report thay cho application-test pass.
- Evidence ghi command, exit code, môi trường và artifact. Thiếu Windows/browser/provider environment là PENDING; không hoàn tất gate thiếu evidence.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Risk

- **Level:** `High`.
- Sai contract/concurrency/persistence có thể làm mất dữ liệu, ghi sai tiến độ hoặc tạo kết luận kiểm chứng sai.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- 100k performance needs removing correctness checks → stop, measure T052.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`feat(T026): vietnamese normalized n-gram projection`

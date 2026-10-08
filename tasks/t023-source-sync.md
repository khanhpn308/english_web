# T023: Startup/watcher sync và source API

**Task ID:** `T023`  
**Title:** Startup/watcher sync và source API  
**Status:** `DONE`
**Goal:** Startup/watcher sync và source API. GET sources, POST/GET sync-runs conform, safe diagnostic and cursor filters.  
**Suggested model:** GPT-6 Astra  
**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay trong danh sách. Nếu vượt khoảng 2 giờ hoặc phạm vi này, tách task trước khi làm tiếp.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/spec.md](../docs/spec.md) FR-VOC-05/08/09; AC-09/10/31
- [docs/api-contract.md](../docs/api-contract.md) sources/sync-runs

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T022](t022-source-journal.md)
- [T026](t026-search-projection.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

- `backend/app/application/sync.py`
- `backend/app/adapters/watcher.py`
- `backend/app/http/sources.py`
- `backend/tests/test_source_sync.py`
- `backend/app/main.py`

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- Idempotent STARTUP/MANUAL/WATCHER runs, readiness SYNCING then READY/DEGRADED. Watcher debounce/coalesce; source revision invalidates projections. Review scheduler already T031; don't modify quiz snapshots. Index cập nhật dùng T026 trong cùng projection commit. Đăng ký đúng route/service vào app factory; TestClient và OpenAPI export dùng app factory production, không app test riêng bỏ security guards.
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [x] GET sources, POST/GET sync-runs conform, safe diagnostic and cursor filters.
- [x] Invalid F excludes X; valid G keeps Y; all-sources-deleted suspends card but retains history.
- [x] External meaning/example edit resets once; app-write watcher echo doesn't double reset.

## Test cases

1. AC-09/10/31, partial file then valid, watcher storm.
2. Startup no false-empty dashboard, sourceRevision increments.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
python -m pytest backend/tests/test_source_sync.py -q
npm run test:contract
```

## Expected output

- GET sources, POST/GET sync-runs conform, safe diagnostic and cursor filters.
- Focused commands đạt kết quả/exit code ghi trong criteria; negative probe phải fail đúng reason. Documentation tasks có conformance report thay cho application-test pass.
- Evidence ghi command, exit code, môi trường và artifact. Thiếu Windows/browser/provider environment là PENDING; không hoàn tất gate thiếu evidence.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Risk

- **Level:** `High`.
- Sai contract/concurrency/persistence có thể làm mất dữ liệu, ghi sai tiến độ hoặc tạo kết luận kiểm chứng sai.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- Sync must delete history or guess multi-source conflict winner → dừng.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`feat(T023): startup/watcher sync và source api`

## Verification Evidence

- `python -m pytest backend/tests/test_source_sync.py -q`: 25 passed in 9.52s (Exit 0)
- `npm run test:contract`: 5 passed in 3.94s (Exit 0)
- `python scripts/check_constraints.py floor`: floor: clean (Exit 0)
- `python -m ruff check backend/app/adapters/watcher.py backend/app/application/sync.py backend/app/http/sources.py backend/app/main.py backend/tests/test_source_sync.py`: All checks passed! (Exit 0)
- `python -m ruff format --check backend/app/adapters/watcher.py backend/app/application/sync.py backend/app/http/sources.py backend/app/main.py backend/tests/test_source_sync.py`: 5 files already formatted (Exit 0)
- `python -m mypy backend/app/adapters/watcher.py backend/app/application/sync.py backend/app/http/sources.py backend/app/main.py backend/tests/test_source_sync.py`: Success: no issues found in 5 source files (Exit 0)
- Dependency regression suite (`test_source_journal.py`, `test_source_files.py`, `test_operations.py`, `test_vocabulary_storage.py`, `test_search_index.py`, `test_srs.py`, `test_ai_admission.py`): 339 passed in 33.27s (Exit 0)
- `npm run check:task:portable`: RESULT: PASS across all 8 gates (check-fast-active, frontend-coverage, portable-pytest, security-secrets, security-code, security-deps, architecture, coverage-check) (Exit 0)
- `python -m alembic heads`: 0007_source_journal (head) (Exit 0)
- `git diff --check`: Clean, no whitespace or merge markers (Exit 0)

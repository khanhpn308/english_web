# T005: SQLite connection và migration zero

**Task ID:** `T005`
**Title:** SQLite connection và migration zero
**Status:** `TODO`
**Goal:** SQLite connection và migration zero. FK enabled, bounded busy timeout, WAL support detected; readonly/corrupt DB fail safe.
**Suggested model:** GPT-6 Astra
**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay trong danh sách. Nếu vượt khoảng 2 giờ hoặc phạm vi này, tách task trước khi làm tiếp.

## Session checkpoint — 29/09/2026

- Tạm dừng theo yêu cầu người dùng trước bước viết test; task vẫn `TODO`, chưa có implementation, verification hoặc commit T005.
- Đã đọc `AGENTS.md`, `AGENT.md`, `CONSTRAINTS.md`, task T005, phần storage/health của spec/API contract, ADR-0001/0004, security review T-10, task plan và code/tests T003 hiện tại.
- Dependency T003 có evidence `DONE`; branch hiện tại là `feature/task-t005-sqlite-migrations`, HEAD `d82c224` (`feat(T003): fastapi app factory và health`). Branch được tạo trong phiên này từ `main`.
- Code hiện tại: `backend/app/http/health.py` chỉ dựa vào sự tồn tại của `storage_path`; chưa có `backend/tests/test_storage.py`, `backend/app/persistence/database.py`, `alembic.ini` hoặc migrations. Python mặc định không có trên PATH; dùng `.venv/bin/python` (3.12.3), Alembic 1.20.0.
- Nhiều file tài liệu/task đã untracked trước phiên này; giữ nguyên, không stage hàng loạt. Không có application file nào được sửa trong phiên này.
- Tiếp tục bằng test RED trong `backend/tests/test_storage.py` cho fresh/repeat upgrade, schema mismatch, FK/busy/WAL, readonly/corrupt DB và bảo toàn history. Sau đó làm implementation tối thiểu trong allowlist, chạy focused/full gates, ghi evidence rồi mới chuyển `DONE` và commit atomic.

### Resume audit — scope clarification required

- Khi tiếp tục từ checkpoint, đã chạy `.venv/bin/python -m pytest backend/tests/test_health.py -q`: exit 0, 8 passed (Python 3.12.3/Linux). Đây là baseline T003, chưa là verification T005.
- `backend/app/http/health.py` tính readiness trực tiếp bằng `storage_path.exists()` và không đọc `app.state.ready`. Test T003 dùng file rỗng và HTTPX ASGITransport không chạy lifespan. Vì vậy nối SQLite/integrity vào `main.py` chưa đủ để health phản ánh storage thực.
- Cần làm rõ scope cho `backend/app/http/health.py` và `backend/tests/test_health.py`, cùng việc chia phần SQLite/migrations và phần health/lifecycle để tuân giới hạn tối đa 5 file implementation. Hai file này chưa được sửa; allowlist, spec/API contract và acceptance criteria giữ nguyên trong lúc chờ chỉ dẫn.
- T005 vẫn `TODO`; chưa viết test mới/implementation hoặc tạo commit. Bước tiếp theo là chốt scope trước test RED.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/adr/0001-architecture.md](../docs/adr/0001-architecture.md) database
- [docs/security-review.md](../docs/security-review.md) T-10

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T003](t003-backend-skeleton.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

Owner đã xác nhận scope clarification trong chat (`ok`): bổ sung health adapter/tests và chia T005 thành hai phần tuần tự, mỗi phần tối đa 5 file implementation. T005 chỉ `DONE` khi cả hai phần có evidence.

### T005-A — SQLite/migrations

- `backend/migrations/env.py`
- `backend/app/persistence/database.py`
- `backend/migrations/versions/0001_storage.py`
- `backend/tests/test_storage.py`

### T005-B — Health/lifecycle (sau T005-A)

- `backend/app/main.py`
- `backend/app/http/health.py`
- `backend/tests/test_health.py`

Generated outputs, tạo bằng Alembic init/config generator version đã khóa:

- `alembic.ini`

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- Chỉ migration ledger/connection health, chưa toàn bộ domain schema. Nối database health/integrity/lifecycle vào app factory để readiness phản ánh storage thực; dùng Alembic init để tạo config và giữ script_location đúng migrations root. T014 operations, T015 consent, T019 vocabulary, T032 review, T035 quiz, T043 feedback sở hữu migrations riêng. Test trên DB tạm; không downgrade live.
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [ ] FK enabled, bounded busy timeout, WAL support detected; readonly/corrupt DB fail safe.
- [ ] Alembic fresh upgrade + repeat giữ cùng revision; một migration head.
- [ ] Integrity failure không drop/rebuild bất kỳ history.

## Test cases

1. Fresh DB, repeated upgrade, schema mismatch.
2. Busy lock và injected corrupt-copy DB.

## Verification evidence — T005-A

- Environment: Linux, `.venv/bin/python` 3.12.3, SQLite 3.45.1, locked SQLAlchemy 2.1.1/Alembic 1.20.0; no dependency/lockfile edits.
- RED: `.venv/bin/python -m pytest backend/tests/test_storage.py -q` exited 2 because the persistence module did not exist. Additional unsupported-WAL probe failed before the journal-mode seam was added.
- GREEN: 22 storage cases pass within the full `.venv/bin/python -m pytest -q` run: 34 passed; database coverage 89% including branches, migrations 100%; `coverage.xml` emitted (ignored artifact).
- `.venv/bin/python -m alembic heads`: exit 0, exactly `0001_storage (head)`.
- `.venv/bin/python -m mypy backend`: exit 0, 11 files; Ruff check and formatter check: exit 0.
- Verified fresh/repeated upgrade, FK on separate connections, 80 ms lock timeout, WAL reader during writer lock, unsupported WAL via injected mode selection, readonly URI/file permissions, unknown/unversioned/malformed ledger, corrupt copy, FK integrity failure, transactional DDL rollback and refused downgrade. No live database touched.
- `alembic.ini` generated with locked Alembic `init` in a temporary directory; generated config normalized to `%(here)s/backend/migrations`, no default database/credentials. Online standalone migration shares the same safety path; offline upgrade refuses without integrity checks.
- T005-B health/lifecycle is still pending; overall task stays `TODO`. Future quality/security aggregate commands are PENDING until T053/T062/T063; Windows ACL/build/recovery evidence belongs to downstream tasks.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
python -m pytest backend/tests/test_storage.py -q
python -m alembic heads
```

## Expected output

- FK enabled, bounded busy timeout, WAL support detected; readonly/corrupt DB fail safe.
- Focused commands đạt kết quả/exit code ghi trong criteria; negative probe phải fail đúng reason. Documentation tasks có conformance report thay cho application-test pass.
- Evidence ghi command, exit code, môi trường và artifact. Thiếu Windows/browser/provider environment là PENDING; không hoàn tất gate thiếu evidence.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Risk

- **Level:** `High`.
- Sai contract/concurrency/persistence có thể làm mất dữ liệu, ghi sai tiến độ hoặc tạo kết luận kiểm chứng sai.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- Migration chỉ chạy được bằng xóa live DB → dừng.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`chore(T005): sqlite connection và migration zero`

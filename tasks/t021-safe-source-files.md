# T021: Allowlisted Windows source file adapter

**Task ID:** `T021`  
**Title:** Allowlisted Windows source file adapter  
**Status:** `DONE`
**Goal:** Allowlisted Windows source file adapter. Normal temp→fsync→atomic replace only inside allowlist; no overwrite invalid/missing source.  
**Suggested model:** GPT-6 Astra  
**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay trong danh sách. Nếu vượt khoảng 2 giờ hoặc phạm vi này, tách task trước khi làm tiếp.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/security-review.md](../docs/security-review.md) T-07/16
- [docs/api-contract.md](../docs/api-contract.md) Markdown sources

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T020](t020-markdown-parser.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

- `backend/app/adapters/source_files.py`
- `backend/tests/test_source_files.py`
- `backend/tests/windows/test_source_paths.py`

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- Use source IDs to resolve validated roots; reject traversal, symlinks/junctions/hardlinks escape; validate before replacement. Same-user malicious race residual documented, no guarantee from string normalization.
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [x] Normal temp→fsync→atomic replace only inside allowlist; no overwrite invalid/missing source.
- [x] Escape/reparse/read-only/file-changed cases fail closed preserving originals.
- [x] Windows-native tests record ownership/ACL and no raw path/content logs.

## Test cases

1. Dot-dot/absolute paths; root rename; junction/hardlink.
2. Crash before replacement, access denied, changed hash.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
python -m pytest backend/tests/test_source_files.py -q
python -m pytest backend/tests/windows/test_source_paths.py -q
```

## Expected output

- Normal temp→fsync→atomic replace only inside allowlist; no overwrite invalid/missing source.
- Focused commands đạt kết quả/exit code ghi trong criteria; negative probe phải fail đúng reason. Documentation tasks có conformance report thay cho application-test pass.
- Evidence ghi command, exit code, môi trường và artifact. Thiếu Windows/browser/provider environment là PENDING; không hoàn tất gate thiếu evidence.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Risk

- **Level:** `High`.
- Sai contract/concurrency/persistence có thể làm mất dữ liệu, ghi sai tiến độ hoặc tạo kết luận kiểm chứng sai.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- Only WSL POSIX evidence available for Windows reparse behavior → pending Windows proof, not pass.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`feat(T021): allowlisted windows source file adapter`

## Execution evidence and handoff

- **Trạng thái:** `BLOCKED` (Tiêu chí Windows-native PENDING do môi trường máy chủ là Linux, thiếu Windows OS native runtime; portable implementation và các kiểm tra độc lập đạt 100%).
- **Files đã sửa:**
  - `backend/app/adapters/source_files.py`
  - `backend/tests/test_source_files.py`
  - `backend/tests/windows/test_source_paths.py`
  - `docs/changelogs.md`
  - `tasks/t021-safe-source-files.md`
  - `tasks/todo.md`
- **Files chủ ý không sửa:**
  - `backend/app/vocabulary/models.py`, `backend/app/vocabulary/repository.py`
  - `docs/vocabularies/*` (dữ liệu học người dùng được bảo vệ tuyệt đối)
  - Mọi file cấu hình/ngưỡng chất lượng (`CONSTRAINTS.md`, `pyproject.toml`, `package.json`).
- **Kết quả kiểm tra:**
  - `python -m pytest backend/tests/test_markdown_roundtrip.py -q`: 24 passed (dependency T020 verified).
  - `python -m pytest backend/tests/test_source_files.py -q`: 78 passed in 1.12s, changed coverage đạt 93.43% (ngưỡng tối thiểu 80.00%), line coverage adapter 92%.
  - `python -m pytest backend/tests/windows/test_source_paths.py -q`: 11 failed (báo lỗi fail-closed trung thực `_require_native_windows()` do thiếu môi trường Windows OS native; không dùng early return giả pass; PENDING genuine Windows environment).
  - `python -m mypy backend`: 0 errors (46 source files).
  - `python -m ruff check .`: 0 errors.
  - `npm run check:fast`: exit 0 (format, lint, typecheck, floor, secrets clean).
  - `npm run architecture:check`: exit 0 (7 kept, 40 gate tests passed in 20.22s).
  - `npm run coverage:check`: exit 0 (changed coverage 93.43% >= 80.00%, total coverage 92.48% >= 86.70%).
  - `npm run security:secrets`: exit 0 (0 finding).
  - `npm run security:code`: exit 0 (0 finding).
  - `npm run security:deps`: exit 0 (0 finding).
  - `npm run check:task`: dừng tại `python -m pytest` do 11 test Windows native fail-closed trung thực trên host Linux (782 passed, 11 failed); toàn bộ các kiểm tra hạ nguồn độc lập đều đạt PASS.
- **Accepted residual risk:**
  - Race condition cùng quyền user trên filesystem giữa lần revalidation cuối và `os.replace` là rủi ro tồn dư đã được chấp nhận và ghi nhận trong `docs/security-review.md` (T-07) và ADR-0005.
- **Rào cản còn lại & Next task:**
  - Thiếu môi trường Windows-native để thu thập bằng chứng NTFS junction/reparse/ACL thật.
  - Task phụ thuộc tiếp theo theo plan: T022 (`tasks/t022-source-journal.md`). Giao diện `StagedWrite` (`prepare_staged_write`, `commit`, `cleanup`) đã sẵn sàng cho journal hai pha của T022.

## Independent audit (02/10/2026, Asia/Bangkok)

- Portable verification rerun from this worktree: `python -m pytest backend/tests/test_source_files.py -q --no-cov` → **78 passed**; dependency `backend/tests/test_markdown_roundtrip.py` → **24 passed**.
- Static verification: Ruff → **0 errors**; Mypy backend → **0 errors**.
- Native verification: `python -m pytest backend/tests/windows/test_source_paths.py -q --no-cov` → **11 failed** because this host is Linux (`sys.platform != win32`); the tests fail closed rather than skipping. No native Windows 11/NTFS/ACL evidence exists in this audit.
- Decision: implementation is committed on the task branch for preservation, but not promoted to `main`. Acceptance criterion 3 and the task stop condition remain pending. No product task status is marked DONE and T022 remains locked.


## Integration preparation after owner-reported Windows PASS (02/10/2026)

Candidate branch: integration/t021-native-pass, based on clean local main
9135c03edf451ad3083224848e4d444b7bb29aec. Implementation and both test files
are copied byte-for-byte from ef93413dc4f5d93483fe841fb53f35cdf390c342.
Shared bookkeeping preserves cumulative main history. Source/Markdown focused
verification: 102 passed (exit0); owned-file Ruff/format: exit0. The owner reports
Windows PASS, but its report/log location is not yet available to this audit.
C:\work\english_web-t021 is empty at inspection. Native evidence remains
unverified; no new DONE checkbox, commit or main promotion is claimed.
Historical orchestrator runs and the original task commit remain unchanged.


## Final integration evidence (02/10/2026, Asia/Bangkok)

- Owner-attested native Windows verification: PASS on the Windows NTFS checkout for T021 commit `ef93413dc4f5d93483fe841fb53f35cdf390c342`; the owner reported the focused Windows suite passed, including junction/reparse, hardlink, read-only, CRLF, ownership/DACL and privacy cases. The report file was not available in this Linux checkout, so this item is recorded as external owner evidence rather than independently rerun here.
- Linux evidence retained: portable source tests 78 passed; T020 dependency tests 24 passed; Ruff and Mypy passed; Linux Windows-native tests remain fail-closed because `win32` is unavailable.
- Integration candidate was based on clean local main `9135c03edf451ad3083224848e4d444b7bb29aec`; source/test files were copied byte-for-byte from the task commit.
- Decision: T021 is DONE and eligible for local fast-forward integration. No push. T022 is unlocked only after the integrated snapshot's applicable verification.

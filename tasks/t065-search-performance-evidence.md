# T065: Search browser timing trên100k fixture

**Task ID:** `T065`  
**Title:** Search browser timing trên100k fixture  
**Status:** `DONE` (coding merged; Windows acceptance `PENDING`)
**Goal:** Chứng minh p95≤1s request→render và AC-07 query≤1000ms bằng benchmark Windows profile.  
**Suggested model:** GPT-6 Astra  
**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay trong danh sách. Nếu vượt khoảng 2 giờ hoặc phạm vi này, tách task trước khi làm tiếp.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/spec.md](../docs/spec.md) PERF/AC-07
- [CONSTRAINTS.md](../CONSTRAINTS.md) search row

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T042](t042-performance-fixture.md)
- [T028](t028-search-ui.md)
- [T052](t052-browser-test-harness.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

- `benchmarks/search_benchmark.py`
- `benchmarks/tests/test_search_benchmark.py`
- `package.json`
- `docs/reviews/search-performance-001.md`
- `docs/runbooks/search-performance.md`

Generated outputs, chỉ tạo bằng generator:

- `package-lock.json`

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- npm benchmark:search starts temp backend/browser fixture harness, warm/cold100 fixed queries with monotonic clocks; report p50/p95/p99 and correctness. Compare result IDs before accepting timings. no UI optimization guessing; failures task owner fix + rerun named fixture. Write build/hardware/cache/SQLite profile in artifact.
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [ ] Request→render measurement and exact result correctness on100k fixture, not DB-only timing.
- [ ] p95≤1s all named benchmark runs; specific AC-07 query≤1000ms; misses fail verdict.
- [ ] Windows11/Python3.12/SQLite/version/query/seed artifact reproducible; missing Windows evidence pending.

## Test cases

1. Timing parser fixture, slow-response fake and incorrect results flagged.
2. Cold/warm100-query Windows runs; exact normalization/expected IDs.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
python -m pytest benchmarks/tests/test_search_benchmark.py -q
npm run benchmark:search
```

## Expected output

- Request→render measurement and exact result correctness on100k fixture, not DB-only timing.
- Focused commands đạt kết quả/exit code ghi trong criteria; negative probe phải fail đúng reason. Documentation tasks có conformance report thay cho application-test pass.
- Evidence ghi command, exit code, môi trường và artifact. Thiếu Windows/browser/provider environment là PENDING; không hoàn tất gate thiếu evidence.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Risk

- **Level:** `High`.
- Sai contract/concurrency/persistence có thể làm mất dữ liệu, ghi sai tiến độ hoặc tạo kết luận kiểm chứng sai.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- Bench misses bar or required Windows profile unavailable → no performance claim; fix/record pending.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`test(T065): search browser timing trên100k fixture`

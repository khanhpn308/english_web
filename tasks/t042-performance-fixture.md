# T042: Deterministic100k search benchmark fixture

**Task ID:** `T042`  
**Title:** Deterministic100k search benchmark fixture  
**Status:** `DONE`
**Goal:** Tạo100k synthetic forms/100 exact Vietnamese queries để benchmark có expected matches và checksum.  
**Suggested model:** GPT-6 Astra  
**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay trong danh sách. Nếu vượt khoảng 2 giờ hoặc phạm vi này, tách task trước khi làm tiếp.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/adr/0004-v1-product-policy-and-operational-baseline.md](../docs/adr/0004-v1-product-policy-and-operational-baseline.md) performance

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T026](t026-search-projection.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

- `benchmarks/generate_fixture.py`
- `benchmarks/tests/test_fixture.py`
- `benchmarks/README.md`

Generated outputs, chỉ tạo bằng generator:

- `benchmarks/artifacts/search-report.json`
- `benchmarks/fixtures/100k_forms.jsonl`

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- Seed29, explicit meaningsVi index source, exact/folded normalization including short/combining mark queries. Fixture JSONL and queries generated to benchmark artifacts; do not commit actual user data. Environment protocol Windows11/Python3.12/SQLite build cold/warm fixed. Browser timing T065.
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [x] Exactly100k forms/100 query set deterministic checksum and ground-truth match IDs.
- [x] Unicode/short/infix/accent-folded fixtures prove correctness; generation không OOM.
- [x] README documents hardware/cache/SQLite profile and seed, no perf pass claimed until T065.

## Test cases

1. Generate twice same checksums; expected query results compare brute force synthetic sample.
2. Malformed fixture/duplicate identity detection and index definition.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
python -m pytest benchmarks/tests/test_fixture.py -q
python benchmarks/generate_fixture.py --forms 100000 --seed 29
```

## Expected output

- Exactly100k forms/100 query set deterministic checksum and ground-truth match IDs.
- Focused commands đạt kết quả/exit code ghi trong criteria; negative probe phải fail đúng reason. Documentation tasks có conformance report thay cho application-test pass.
- Evidence ghi command, exit code, môi trường và artifact. Thiếu Windows/browser/provider environment là PENDING; không hoàn tất gate thiếu evidence.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Risk

- **Level:** `High`.
- Sai contract/concurrency/persistence có thể làm mất dữ liệu, ghi sai tiến độ hoặc tạo kết luận kiểm chứng sai.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- Cannot run Windows fixture or result misses threshold → evidence pending, no optimization guess.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`test(T042): deterministic100k search benchmark fixture`

## Verification evidence (02/10/2026)

- `python -m pytest benchmarks/tests/test_fixture.py -q`: Exit 0, 13 passed.
- `python benchmarks/generate_fixture.py --forms 100000 --seed 29`: Exit 0;
  exactly 100,000 forms and 100 queries generated. Repeated invocation produced
  byte-identical JSONL and report artifacts.
- Fixture validation: 100,000 lines, 100,000 unique IDs, fixture SHA-256
  `9a008769530d811b017ff17078d57f13760198cb1164ac7304b01b90740167bb`;
  report query SHA-256 and ground-truth SHA-256 revalidated from canonical bytes.
- `python -m pytest backend/tests/test_search_index.py -q`: Exit 0, 25 passed.
- `python -m ruff check .` and `python -m ruff format --check .`: Exit 0.
- `python -m mypy backend`: Exit 0, no issues in 48 source files.
- `npm run security:secrets`, `npm run security:code`,
  `npm run security:deps`: Exit 0, zero findings.
- `python scripts/check_constraints.py floor`: Exit 0, `floor: clean`.
- Full `python -m pytest -q`: Exit 1 with 30 inherited environment failures
  (native Windows tests and frontend architecture tests unavailable on this Linux
  checkout); 869 tests passed. This is not a T042 failure and is not reported as
  a pass.
- `npm run check:fast` and `npm run architecture:check`: Exit 127 because the
  checkout lacks installed Node executables (`eslint`, `depcruise`); classified
  SETUP_PENDING rather than pass.

Generated artifacts were produced only by the generator; no manual generated
edits were made. T042 does not claim search timing or p95 acceptance; T065 owns
Windows/browser performance evidence.

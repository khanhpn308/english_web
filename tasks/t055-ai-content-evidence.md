# T055: Human-reviewed semantic fixture và optional AI smoke

**Task ID:** `T055`  
**Title:** Human-reviewed semantic fixture và optional AI smoke  
**Status:** `TODO`  
**Goal:** Tạo bộ100-form human-reviewed oracle và thủ tục đo provider content/latency đã được consent.  
**Suggested model:** GPT-6 Astra  
**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay trong danh sách. Nếu vượt khoảng 2 giờ hoặc phạm vi này, tách task trước khi làm tiếp.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/spec.md](../docs/spec.md) AC-02/26/27/34/35
- [docs/adr/0004-v1-product-policy-and-operational-baseline.md](../docs/adr/0004-v1-product-policy-and-operational-baseline.md) content quality
- [docs/api-contract.md](../docs/api-contract.md) BR-AUTH

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T008](t008-lookup-api-vertical-slice.md)
- [T035](t035-quiz-api.md)
- [T049](t049-writing-feedback-api.md)
- [T040](t040-first-run-recovery.md)
- [T041](t041-security-hardening.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

- `backend/tests/fixtures/semantic_quality.json`
- `backend/tests/test_semantic_fixture.py`
- `scripts/provider_smoke.py`
- `docs/reviews/ai-quality-001.md`

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- Fixture academic POS/family/common meanings/examples/translations needs named human review and authority source links; automated schema can't certify semantics. No bulk scraping/credential copy. Provider smoke is disabled by default; only exact approved configured-account model and explicit user-run opt-in, current consent/profile. Distinguish fixture tests vs real130? hard deadline120 lookup/60 quiz/30 feedback; no paid fallback.
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [ ] Fixture100 forms has IDs/expected semantic rubric/source provenance and validation checks; human review pending recorded until provided.
- [ ] Smoke records redacted version/model/route/auth/quota/network/timings with no study-history payload.
- [ ] Report separates compatibility, profile/auth, semantic quality and timing; no false conclusion from fake provider.

## Test cases

1. Fixture missing source/POS/meaning regression is detected.
2. Default smoke invokes zero real inference; explicit opt-in path validates consent/profile before dummy approved content.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
python -m pytest backend/tests/test_semantic_fixture.py -q
python scripts/provider_smoke.py --dry-run
```

## Expected output

- Fixture100 forms has IDs/expected semantic rubric/source provenance and validation checks; human review pending recorded until provided.
- Focused commands đạt kết quả/exit code ghi trong criteria; negative probe phải fail đúng reason. Documentation tasks có conformance report thay cho application-test pass.
- Evidence ghi command, exit code, môi trường và artifact. Thiếu Windows/browser/provider environment là PENDING; không hoàn tất gate thiếu evidence.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Risk

- **Level:** `High`.
- Sai contract/concurrency/persistence có thể làm mất dữ liệu, ghi sai tiến độ hoặc tạo kết luận kiểm chứng sai.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- Real inference requires current owner opt-in, valid profile/consent/cost conditions; human oracle missing → pending evidence, no invented reviewer.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`test(T055): human-reviewed semantic fixture và optional ai smoke`

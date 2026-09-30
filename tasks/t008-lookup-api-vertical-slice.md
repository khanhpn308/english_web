# T008: POST lookup trả preview đã validate

**Task ID:** `T008`  
**Title:** POST lookup trả preview đã validate  
**Status:** `TODO`  
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

- [ ] Valid preview có meaning/example fields; missing IPA/link có nhãn, không hallucinated verified.
- [ ] Consent denied zero preflight; malformed output/timeout không success hoặc queued retry.
- [ ] Idempotent same intent một dispatch; no explicit save = zero card/source.

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

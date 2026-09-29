# T013: Chuẩn hóa ví dụ và quyết định contract còn mơ hồ

**Task ID:** `T013`

**Title:** Chuẩn hóa ví dụ và quyết định contract còn mơ hồ

**Status:** `DONE`

**Goal:** Chốt conformance matrix và cập nhật ví dụ thành các oracle xác định trước khi lập trình business contracts.

**Suggested model:** GPT-6 Astra

**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay trong danh sách. Nếu vượt khoảng 2 giờ hoặc phạm vi này, tách task trước khi làm tiếp.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/reviews/spec-architecture-review-001.md](../docs/reviews/spec-architecture-review-001.md) closure
- [docs/adr/0004-v1-product-policy-and-operational-baseline.md](../docs/adr/0004-v1-product-policy-and-operational-baseline.md)

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T005](t005-database-schema-migrations.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Execution context — 29/09/2026

- Owner xác nhận trong chat cho phép sửa spec/API đúng allowlist T013, thay chỉ dẫn template cấm hai file này cho task này.
- T005 `DONE`, evidence tại thẻ dependency và commits `8adf972`/`bebcc12`; current baseline `bebcc12` cũng chứa T004 `dc52e0e`. `main` mới ở T003 nên không reset/merge bỏ dependency.
- Branch `feature/task-t013-contract-conformance`, managed worktree `/home/khanh/.codex/worktrees/task-t013-contract-conformance/vocabularies`. Checkout chung đang do T053 sử dụng; chỉ copy planning inputs để đọc/sửa trong worktree riêng, không đổi branch/index/files của worker đó.
- Spec/API/UI/card đã untracked trước phiên này; commit chỉ stage đúng năm allowlisted documents + card/todo/changelog, ghi full snapshots khi chúng lần đầu được track. Baseline provenance trong [conformance report](../docs/reviews/contract-conformance-002.md) giữ nguồn đầu vào; raw API digest được bỏ khỏi prose khi T063 chứng minh Gitleaks misclassify nó như generic key.

## Files được phép sửa

- `docs/spec.md`
- `docs/api-contract.md`
- `docs/ui-architecture.md`
- `docs/adr/0005-contract-clarifications.md`
- `docs/reviews/contract-conformance-002.md`

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- Task docs-only từ ủy quyền trước của owner chọn quyết định hợp lý để đóng blockers. ADR-0004 có precedence: 1/1/1 quiz invalid vì total3<5; chuẩn hóa example5+; HARD giữ box hiện tại (NEW→1), GOOD+1/EASY+2 capped5, local-calendar due rule phải ghi exact fixture; source mới được backend cấp ID theo noteDate; HTTP409 chỉ áp API stale write, external editor được phát hiện qua hash/watcher. Định rubric 0–4 descriptors, correct answer/explanation chỉ trả sau submission, terminal result read, body/file/response caps và session lifecycle theo CONSTRAINTS. Record mọi clarification và impact trong ADR-0005; giữ scope hiện tại. Nếu phát hiện quyết định material không nằm trong ủy quyền thì mới dừng.
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [x] Mọi ambiguity có evidence và quyết định deterministic trong ADR-0005; không chỉ sửa status.
- [x] Spec/API/UI/examples dùng đúng min5, clean-install save, source revision và submit-result lifecycle.
- [x] Oracle SRS/rubric/deadline/size/session đủ để tests định expected output, không cần agent tự chọn.

## Test cases

1. Manual crosswalk từng issue tới AC/schema/ADR; check 1/1/1 quiz bị reject.
2. Walkthrough clean install save ngày mới, external edit, terminal quiz và revoke/restart.

## Verification evidence and handoff — 29/09/2026

- Đây là docs-only checkpoint, không có application code/config/migration thay đổi. Dùng incremental implementation, TDD document probes, git workflow, API/UI design và documentation-and-adrs; không gọi bridge/inference.
- RED: viết 11 nhóm C013-01–11 trong report trước implementation tài liệu; command standard-library Python exit1, cả 11 FAIL. Một lỗi delimiter của command được sửa trước valid RED run.
- GREEN: cùng probe (bổ sung kiểm tra full SRS transition/date table, strict JSON fixture parsing, snapshot/result IDs/counts và weakest grouping) exit0, 11 PASS. Hai mutation probes chỉ thay dữ liệu trong memory: positive counts thành1/1/1 và thêm explanationVi trước submit; checker từ chối đúng C013-01/C013-06, wrapper exit0.
- Manual crosswalk/walkthrough của card đạt document conformance: quiz5+/negative3, HARD giữ box/due midnight Bangkok, rubric0–4/null/blank, backend new-date source ID + preconditions/receipts, hash/watcher và stale API409, hidden keys/explanations và terminal GET/replay, max/max+1 caps, session60s/8h/restart, deadline120/60/30s và lifetime idempotency retention. Authority/alternatives/impact ở ADR-0005.
- Focused `git diff --check` và task-card `rg` exit0. Spec/API/UI trước đó untracked nên staged whitespace check ban đầu phát hiện Markdown hard-break spaces ở metadata; đổi thành blank-line paragraphs trong chính scoped files, rồi `git diff --cached --check` exit0. `git diff --no-index --check` trả1 khi có delta, không có whitespace diagnostic, không coi exit1 là PASS command.
- Final staged conformance script exit0: đúng tám task files được stage; application/config diff rỗng; 96 local links resolve trong worktree hoặc original planning context; CONSTRAINTS và ADR-0004 SHA-256 giữ nguyên. Supplemental credential-pattern scan in-memory cho staged diff và local Git history đều 0 candidate, không in candidate contents. Gitleaks vẫn PENDING.
- `gitleaks detect --redact --no-banner`: exit127 (tool unavailable), PENDING T063; supplemental redacted pattern scan không được gọi là Gitleaks PASS. T053/T017/T062/T063 commands chưa có tại baseline của branch; check:task/generated-contract/security/architecture là SETUP_PENDING. Không cần frontend/backend lint/type/test/build/coverage cho thay đổi chỉ tài liệu; không tuyên bố runtime PASS.
- Post-T063 recheck ngày 30/09/2026: Gitleaks 8.30.1 ban đầu RED với năm false positives (một SHA-256 provenance, ba synthetic idempotency values, một bridge prose fragment). Sau các wording/placeholder edits không đổi contract, `dir`, staged diff và current-HEAD history (8 commits) đều 0 findings. Commit được amend để history reachable không giữ fixture cũ; không thêm allowlist/suppression.
- Môi trường: Linux, existing T001/T058 interpreter `/home/khanh/projects/vocabularies/.venv/bin/python` 3.12.3; script chỉ dùng stdlib. Exact executable probe/negative/staged commands ở report; không tạo dependency hoặc runtime mới.
- Files sửa: `docs/spec.md`, `docs/api-contract.md`, `docs/ui-architecture.md`, `docs/adr/0005-contract-clarifications.md`, `docs/reviews/contract-conformance-002.md`, card này, `tasks/todo.md`, `docs/changelogs.md`.
- Files chủ ý không sửa: application/config/locks; CONSTRAINTS; ADR-0001–0004; historical review, security/observability/runbooks; real vocabulary/credentials và concurrent T053 changes. Read-only planning context copies còn untracked, không stage hàng loạt.
- Risk/evidence còn mở: generated DTO/schema T017; source/session/SRS/quiz runtime boundaries và failure/replay tests do T006/T007/T014–16/T021–24/T029/T031/T035/T047/T048/T059 sở hữu; Windows/browser/profile/entitlement/semantic/accessibility/performance vẫn release gates. Không có product decision T013 còn mở.
- Next: T006 dependency-ready sau T013; hoàn thành quality wave T053/T063 theo ordered plan trước integration checkpoints. Commit atomic đã được user yêu cầu; không push/merge main.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
git diff --check
rg -n 'HARD|AC-14|sourceId|session|explanationVi|rubric|SUBMITTED' docs/spec.md docs/api-contract.md docs/adr/0005-contract-clarifications.md
```

## Expected output

- Mọi ambiguity có evidence và quyết định deterministic trong ADR-0005; không chỉ sửa status.
- Focused commands đạt kết quả/exit code ghi trong criteria; negative probe phải fail đúng reason. Documentation tasks có conformance report thay cho application-test pass.
- Evidence ghi command, exit code, môi trường và artifact. Thiếu Windows/browser/provider environment là PENDING; không hoàn tất gate thiếu evidence.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Risk

- **Level:** `High`.
- Sai contract/concurrency/persistence có thể làm mất dữ liệu, ghi sai tiến độ hoặc tạo kết luận kiểm chứng sai.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- Decision mở rộng multi-user/LAN/cloud, new provider/cost hoặc mất dữ liệu không thuộc authorization → dừng; routine clarification dùng baseline đơn giản đã ủy quyền.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`docs(T013): chuẩn hóa ví dụ và quyết định contract còn mơ hồ`

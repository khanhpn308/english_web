# T063: Secret và code/dependency security scan gates

**Task ID:** `T063`
**Title:** Secret và code/dependency security scan gates
**Status:** `DONE`
**Goal:** Pinned Gitleaks/Semgrep/OSV scans tạo reproducible severity verdict và redacted reports.
**Suggested model:** GPT-6 Astra
**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay trong danh sách. Nếu vượt khoảng 2 giờ hoặc phạm vi này, tách task trước khi làm tiếp.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [CONSTRAINTS.md](../CONSTRAINTS.md) secret/code/dependency rules
- [docs/security-review.md](../docs/security-review.md) T-14

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T001](t001-toolchain-repository-skeleton.md)
- [T053](t053-quality-security-gates.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

- `scripts/security_checks.py`
- `scripts/tests/test_security_checks.py`
- `package.json`
- `docs/toolchain.md`

Generated outputs, chỉ tạo bằng generator:

- `package-lock.json`
- `requirements-dev.lock` (owner phê duyệt remediation ngày 30/09/2026; chỉ regenerate bằng `pip-compile --allow-unsafe`)

Owner cũng phê duyệt sửa đúng hai false-positive wording lines trong planning `docs/api-contract.md`; file này vẫn do T013 sở hữu và không được stage vào commit T063.

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- Verify pinned CLI docs/flags, license rules and install recipes. Working tree (incl untracked/no-HEAD), staged and history when exists; no realistic key in fixtures. Severity high/critical blocking; unknown severity explicit triage; scans unavailable/vuln db unavailable SETUP_FAILED not pass. Scanner report parser only redacted metadata. Baseline screenshot key risk remains manual pre-commit review; do not commit assets wholesale.
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [x] security:secrets/code/deps run de facto tools and failures propagate as exit nonzero.
- [x] Dummy sentinel value absent transcript/reports, only rule/path printed; scan all in-scope untracked files.
- [x] Report high/critical/unknown severity fixtures enforce written policy, no force dependency upgrade.

## Test cases

1. Synthetic secret temp fixture, report redaction, no-HEAD/untracked detection.
2. High/critical/deps unknown severity reports; scanner exit/network failure.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
python -m pytest scripts/tests/test_security_checks.py -q
npm run security:secrets
npm run security:code
npm run security:deps
```

## Verification evidence (30/09/2026)

- TDD RED: focused suite ban đầu lỗi import vì `scripts/security_checks.py` chưa tồn tại; remediation regression sau đó fail đúng ở missing current-HEAD scope và missing setuptools pin. GREEN: 20 focused tests pass. Full Python suite đạt 78 tests; frontend 21 tests; changed coverage 88,98%, combined total 87,42%.
- Pinned tools được kiểm tra bằng binary thật ngoài repository: Gitleaks `8.30.1`, Semgrep CE `1.178.0`, OSV-Scanner `2.6.0`; checksum/install evidence và nguồn chính thức ghi tại `docs/toolchain.md` §8.
- Real negative probes: synthetic no-HEAD/untracked secret trả exit `1` và không xuất sentinel trong transcript/report; Semgrep fixture `eval(input())` trả critical, stable rule ID và exit `1`.
- Owner-approved remediation: history scan dùng `--log-opts=HEAD` để quét history reachable hiện tại, không quét nhánh/worktree không liên quan; hai Markdown false positives được đổi sang placeholder/prose tương đương; generated `requirements-dev.lock` dùng `--allow-unsafe` và chỉ thêm pin thật `pip==26.2.1`, `setuptools==84.0.0`.
- `npm ci --ignore-scripts` sạch (0 vulnerabilities); clean Python venv install + `pip check` sạch. Ruff, format, Mypy, frontend typecheck/build, floor, coverage, `check:fast` và `check:task:active` đều pass; ESLint có 0 errors và hai warning Fast Refresh có sẵn trong file không sửa.
- `npm run security:secrets`, `npm run security:code`, `npm run security:deps`: exit `0`, mỗi report 0 findings. `check:task`/`check:full` còn terminal `SETUP_PENDING` riêng của T062 theo dependency graph.

## Handoff

- Files thay đổi thuộc commit T063: scanner/test, `package.json`, generated `requirements-dev.lock`, `docs/toolchain.md` và bookkeeping. `docs/api-contract.md` trong planning workspace được sửa đúng hai false-positive dòng theo owner approval nhưng không stage vào T063 vì file thuộc worktree/owner T013 và chưa tracked trên branch này.
- Files chủ ý không sửa: spec/UI/ADR, application frontend/backend, vocabulary data, credentials, proxy/provider configuration và thresholds trong `CONSTRAINTS.md`.
- Risk còn lại: nhánh T013 đang chứa commit cũ với fixture false positive; trước khi merge T013 vào dòng chính, owner T013 phải mang hai wording fixes tương đương vào lịch sử reachable mới, nếu không current-HEAD history scan sẽ chặn đúng thiết kế.
- Next task: T013 theo dependency order; không push, remote change hay provider inference được thực hiện.

## Expected output

- security:secrets/code/deps run de facto tools and failures propagate as exit nonzero.
- Focused commands đạt kết quả/exit code ghi trong criteria; negative probe phải fail đúng reason. Documentation tasks có conformance report thay cho application-test pass.
- Evidence ghi command, exit code, môi trường và artifact. Thiếu Windows/browser/provider environment là PENDING; không hoàn tất gate thiếu evidence.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Risk

- **Level:** `High`.
- Sai contract/concurrency/persistence có thể làm mất dữ liệu, ghi sai tiến độ hoặc tạo kết luận kiểm chứng sai.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- Need disable scanner/new allowlist or expose secret to get green → dừng.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`chore(T063): secret và code/dependency security scan gates`

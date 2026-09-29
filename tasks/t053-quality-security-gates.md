# T053: Coverage và quality-floor guard

**Task ID:** `T053`
**Title:** Coverage và quality-floor guard
**Status:** `DONE`
**Goal:** Enforce changed-code coverage80%, baseline ratchet và chống suppression/skipped tests.
**Suggested model:** GPT-6 Astra
**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay trong danh sách. Nếu vượt khoảng 2 giờ hoặc phạm vi này, tách task trước khi làm tiếp.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- constraint-driven-development references/floor-guard.md

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T002](t002-quality-gates-test-runner-build.md)
- [T058](t058-python-quality-gates.md)
- [T003](t003-backend-skeleton.md)
- [T004](t004-frontend-shell-routes.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

- `scripts/check_constraints.py`
- `scripts/tests/test_constraints.py`
- `package.json`
- `docs/toolchain.md`
- `pyproject.toml`

Generated outputs, chỉ tạo bằng generator:

- `package-lock.json`
- `requirements.lock`
- `requirements-dev.lock`

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- Adapt constraint skill floor-guard reference, diff scopes including untracked/no-HEAD baseline. Reuse lcov/XML generated same test run; do not duplicate suite. Coverage config phải thu backend/app và các script/launcher/benchmark code đã tồn tại; từng focused test đo đúng production/tooling files vừa thay đổi, không chỉ coverage của tests. Scripts check:fast/check:task aggregate applicable gates whose owners T062/T063; before owner tool exists report SETUP_PENDING explicitly. Install required diff coverage dependency/version from official docs. This task owns format:check, coverage:check and floor:check; architectural/scanner tools separate.
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [x] Changed lines80% and baseline ratchet0.5-point are enforced using actual reports; missing report fail.
- [x] New suppressions, skips/deleted/assertion-stripped tests or threshold changes flagged against task baseline.
- [x] Check scripts no false-green/no-test pathways, sensitive matches redacted and no-HEAD untracked code covered.

## Test cases

1. Coverage79.9/80, missing XML/lcov, baseline regression beyond0.5 point.
2. Floor suppression/testskip/assertiondelete and untracked-file cases.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
python -m pytest scripts/tests/test_constraints.py -q
npm run coverage:check
npm run floor:check
```

## Verification evidence (29/09/2026)

- Environment: Ubuntu/WSL, Python 3.12.3, temporary verified Node.js Linux 22.23.2 runtime; task diff base `bebcc12` via `QUALITY_BASE_REF` because the completed T004/T005 work was stacked ahead of local `main`.
- TDD RED: focused suite initially returned 15 failures because `scripts/check_constraints.py` did not exist.
- `python -m pytest scripts/tests/test_constraints.py -q`: exit 0, 17 passed; checker code đạt 84% line coverage. Negative fixtures cover 79.9/80, missing XML/LCOV, baseline regression beyond 0.5 point, unmeasured changed source, suppression/skip/test deletion/assertion deletion/threshold weakening, redacted finding, coverage/floor trên untracked no-HEAD và explicit pending exit 2.
- `npm run test:frontend:coverage`: exit 0, 21 passed; LCOV emitted in the same Vitest run, frontend line coverage 50.00% (38/76).
- `python -m pytest`: exit 0, 58 passed; Cobertura XML emitted in the same Python run, report summary 88% across backend/migrations/checker.
- `npm run coverage:check`: exit 0; changed lines 87.99% (minimum 80.00%), combined total 86.88% against recorded baseline 86.70% with 0.50-point tolerance.
- `npm run floor:check`: exit 0, `floor: clean`.
- `npm run format:check`, `python -m ruff check .`, `python -m mypy backend`, `npm run typecheck`, `npm run build`: exit 0. `npm run lint` returned exit 0 with 0 errors and two pre-existing Fast Refresh warnings in `AppShell.tsx`; that file was intentionally untouched.
- Lock generation/install: `npm install --package-lock-only --ignore-scripts`, both `pip-compile` commands and Linux `npm ci --ignore-scripts` exited 0. Windows npm over the WSL UNC path first returned `ENOTEMPTY`/`ENOENT`; no source or lockfile failure remained after using the verified Linux runtime. `npm audit` reported 0 vulnerabilities, but T063's Gitleaks/Semgrep/OSV gates remain `SETUP_PENDING` and are not claimed as security PASS.
- `check:fast`, `check:task`, `check:full` retain an explicit exit-2 `SETUP_PENDING` terminal for T062/T063. Active T053 components are separately runnable; the aggregate commands must not be reported green until those owners replace the pending terminal.

## Handoff

- Files changed: `scripts/check_constraints.py`, `scripts/tests/test_constraints.py`, `package.json`, `pyproject.toml`, generated lockfiles, `docs/toolchain.md` and permitted bookkeeping files.
- Intentionally untouched: `CONSTRAINTS.md`, spec/API/UI/security/observability/ADR documents, frontend/backend product source, vocabulary data, credentials and provider configuration.
- Remaining risks: local `main` still trails the stacked T004/T005 commits, so current task verification names `bebcc12` explicitly; downstream CI must use its actual merge target. Architecture and security aggregates remain owned by T062/T063.
- Next task: T063 security scan tooling (or the next dependency-ready task chosen by the owner); no remote push or provider inference was performed.

## Expected output

- Changed lines80% and baseline ratchet0.5-point are enforced using actual reports; missing report fail.
- Focused commands đạt kết quả/exit code ghi trong criteria; negative probe phải fail đúng reason. Documentation tasks có conformance report thay cho application-test pass.
- Evidence ghi command, exit code, môi trường và artifact. Thiếu Windows/browser/provider environment là PENDING; không hoàn tất gate thiếu evidence.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Risk

- **Level:** `High`.
- Sai contract/concurrency/persistence có thể làm mất dữ liệu, ghi sai tiến độ hoặc tạo kết luận kiểm chứng sai.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- Scanner lacks severity gating or coverage report unavailable → dừng, không remove gate.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`chore(T053): coverage và quality-floor guard`

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

### Narrow generated-source coverage classification remediation (01/10/2026)

- Scope/status: remediation `DONE`, local commit authorized on `fix/t053-generated-coverage` in `/home/khanh/projects/vocabularies-t053-generated`, based on `bc0ff937b85a62fa395213d93ac4d6a5021cddcc`. This is T053 quality infrastructure only. No T015 implementation or integration, main promotion or push is authorized in this session.
- Root cause: source suffix, test exclusion and coverage prefixes admitted `frontend/src/shared/api/generated.ts` as handwritten changed application code. T017 explicitly owns that generated artifact, and CONSTRAINTS excludes generated/vendor files from changed-code coverage.
- Fix: `is_generated_source()` uses an immutable exact-path set containing only `frontend/src/shared/api/generated.ts`. Apply it only to changed-line coverage classification. Unknown paths still require measurement; no filename/directory heuristic, broad exemption or threshold exception. Git diff collection, total report measurements, diff-cover validation, floor, architecture, contracts and security behavior remain unchanged.
- Thresholds unchanged: changed minimum **80.0%**, total baseline **86.70%**, tolerance **0.5 percentage points**. No dependency/config/generated artifact changes.
- TDD RED: tests added before implementation. Initial focused run exited 1 with 14 failed / 39 passed; two failures were mistaken expected error wording, corrected before checker changes. Corrected RED (`python -m pytest scripts/tests/test_constraints.py -q --tb=short`) exited 1 with **12 failed / 41 passed**. Tracked/untracked/no-HEAD generated cases reported `no coverage measurements for changed source frontend/src/shared/api/generated.ts`; mixed cases failed before calculating handwritten coverage. Initial focused lint/format identified two new overlong test lines, subsequently corrected.
- GREEN/adversarial: **53 passed** (37 existing, 16 new). Generated-only diffs without DTO measurements yield changed 100%; generated plus measured backend yields exactly 80% pass / 70% fail. Unmeasured `generated-helper.ts`, `not-generated.ts`, `client.ts` and `backend/app/unmeasured.py` each fail with exit 1. Missing XML/LCOV, empty LCOV and absent/invalid diff-cover retain setup exit 2. The total ratchet still fails on uncovered generated measurements present in a report. Generated-path suppression and threshold weakening still fail the floor. No fake LCOV records or frontend DTO execution tests added.
- Actual T015 replay: isolated temporary shared Git clone checked out candidate `2386f3d12730cda8e886acb593b0fadcd473778d`, compared to the exact base above; copied its existing real XML/LCOV reports unchanged. Original checker exited **1** with the exact DTO missing-measurement failure. Fixed checker exited **0**, changed **94.79%**, total **89.89%**. The real LCOV has an SF entry for the DTO but zero measured lines; an initial replay-harness assertion incorrectly expected no SF entry and was corrected before running the comparison. SHA-256 snapshots of every T015 tracked file and both reports were identical before/after, HEAD unchanged, status clean. No writes to `/home/khanh/projects/vocabularies-integrate-t015`.
- Environment: Ubuntu/WSL, Python 3.12.3 using the existing locked main virtualenv, Node.js 22.23.2 / npm 12.0.2. `npm ci --ignore-scripts` exited 0 with no dependency/lock edits. Task commands use `QUALITY_BASE_REF=bc0ff937b85a62fa395213d93ac4d6a5021cddcc`.

| Command | Exit | Outcome |
|---|---:|---|
| `python -m pytest scripts/tests/test_constraints.py -q` | 0 | 53 passed; checker measured directly |
| `python -m ruff check scripts/check_constraints.py scripts/tests/test_constraints.py` | 0 | All checks passed |
| `python -m ruff format --check scripts/check_constraints.py scripts/tests/test_constraints.py` | 0 | Both files formatted |
| `python -m mypy scripts/check_constraints.py` | 0 | No issues |
| `python -m pytest -q` | 0 | 208 passed; real Cobertura report generated |
| `python -m ruff check .` | 1 | 19 pre-existing findings, zero new findings; verified against exact base |
| `npm run test:frontend:coverage` | 0 | 38 passed; real LCOV generated |
| `npm run typecheck` | 0 | No errors |
| `npm run lint` | 0 | Zero errors; two existing AppShell Fast Refresh warnings |
| `npm run build` | 0 | Vite build passes; output remains ignored |
| `npm run floor:check` | 0 | Clean |
| `npm run coverage:check` | 0 | Changed 100.00%, total 88.97%; ratchet enforced |
| `npm run check:fast` | 0 | Format/lint/type/floor/secrets pass |
| `npm run security:secrets` | 0 | Pinned Gitleaks 8.30.1; zero working/staged/history findings |
| `git diff --check` | 0 | No whitespace errors |

- Full Ruff limitation: 19 findings in `backend/app/application/consent.py`, `backend/app/http/consent.py`, `backend/tests/test_consent.py`, `backend/tests/test_operations.py` and `scripts/tests/test_contract.py`. Each file is byte-identical to the base. Running Ruff on base contents gives the same paths/rules/locations/messages. This is a baseline failure, not a remediation regression; full repository Ruff is not claimed green and no unrelated fix/suppression is included.
- Secret scanner provenance: `/tmp/t015-gitleaks.tar.gz` SHA-256 matches the pinned toolchain value `551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb`; `/tmp/t015-security-tools/gitleaks` matches the binary extracted from that archive. Wrapper checks exact 8.30.1 and redacts reports. Binary stays outside Git.
- Changed files: checker, checker tests, this card and `docs/changelogs.md`. Intentionally untouched: `tasks/todo.md`, CONSTRAINTS, thresholds/baseline/tolerance, package/lockfiles, generated DTO/OpenAPI, frontend coverage tests, T015 source/worktree, T062 files, security tooling and all unrelated source. Documentation uses the required documentation-and-adrs skill; no ADR/API change is needed.
- Remaining work: cherry-pick the remediation commit into `integration/t015-after-cp05`, then rerun complete-candidate `check:task` with the proper base. This remediation branch does not change the DTO; replay/focused evidence proves classification, but does not claim a complete integrated-candidate gate. Main remains untouched; commit is local only, not pushed.

### Narrow assertion-replacement remediation (30/09/2026)

- Status: remediation `DONE`; shared workspace `NOT_READY_TO_COMMIT` because unrelated gates still fail. No commit authorized or created.
- Context: T015 advances Alembic head, so legitimate assertion edits appear as removed/added Git lines. The original checker reported every removed assertion independently. The session started with an uncommitted per-file counting implementation and 29 passing tests; those existing changes were preserved.
- Decision: compare assertion counts within each modified test file, across diff hunks. For Python, reconstruct the previous source from the collected diff and tokenize both versions so comments, assertion messages and multiline strings cannot count as replacements. Count multiple assertions on one line separately. Other languages retain the existing `assert`/`expect`/`should` markers with per-file replacement counting. Unreadable or untokenizable modified Python tests return redacted setup failure (exit 2), never a clean verdict. No semantic-strength inference, path/migration exemption, dependency, threshold or gate change.
- TDD: eight additional cases cover exact sole-assertion deletion, message-word false positives, comments/strings falsely credited as replacements, multiline-string context, unchanged assertions enclosed in a string, separate-hunk replacement and redacted tokenization failure. RED before checker changes: exit 1, 4 failed / 30 passed. GREEN: exit 0, 37 passed. Existing revision replacement, wrap/unwrap, net loss/addition, same-line statements, cross-file isolation, framework replacement, test deletion, suppression/skip, threshold, coverage/ratchet and no-HEAD regressions remain green.
- T015 reproduction: copied the actual baseline/current contents of `backend/tests/test_storage.py`, `backend/tests/test_health.py` and `backend/tests/test_operations.py` into a temporary Git repository. Original HEAD checker: exit 1 with eight `assertion-removed` findings. Repaired checker: exit 0, `floor: clean`. The source files were read only.

| Command | Exit | Outcome |
|---|---|---|
| `python -m pytest scripts/tests/test_constraints.py -q` | 0 | 37 passed |
| `python -m ruff check scripts/check_constraints.py scripts/tests/test_constraints.py` | 0 | All checks passed |
| `python -m mypy scripts/check_constraints.py` | 0 | No issues in one source file |
| `npm run floor:check` | 1 | Only remaining finding: `silenced-checker` in `scripts/tests/test_contract.py:34` |
| `npm run check:fast` | 1 | Stops at formatter: `backend/app/adapters/bridge.py` and `backend/tests/test_bridge.py`; later stages not run |

- Files changed this session: the checker, its tests, this task card and `docs/changelogs.md`. Intentionally untouched: T015 and all backend/product tests, contract/client changes, `CONSTRAINTS.md`, thresholds, package/locks and other task bookkeeping. Existing unrelated working-tree changes remain intact. No staging, branching, commit, push or inference.
- Remaining risks: structural counts cannot establish semantic strength; other-language marker matching remains heuristic. The working-tree floor/fast failures above require their own owners. Next work: resolve the contract-test suppression and bridge formatting in their authorized tasks, then rerun the shared gates.

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

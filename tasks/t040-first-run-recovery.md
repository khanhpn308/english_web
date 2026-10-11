# T040: Native first-run configuration và protected key store

**Task ID:** `T040`  
**Title:** Native first-run configuration và protected key store  
**Status:** `DONE (CODING_ONLY)` — `FINAL_VERIFICATION_DEFERRED` (12/10/2026; owner-approved PR #23 merged; Windows/runtime/security acceptance pending)  
**Goal:** Native first-run configuration và protected key store. First-run valid native config persists protected key, browser/log/DB never key.  
**Suggested model:** GPT-6 Astra  
**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay trong danh sách. Nếu vượt khoảng 2 giờ hoặc phạm vi này, tách task trước khi làm tiếp.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/runbooks/first-run-and-restore.md](../docs/runbooks/first-run-and-restore.md)
- [docs/security-review.md](../docs/security-review.md) T-10/16
- [docs/adr/0004-v1-product-policy-and-operational-baseline.md](../docs/adr/0004-v1-product-policy-and-operational-baseline.md) runtime/recovery

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T039](t039-launcher.md)
- [T007](t007-bridge-policy-consent-adapter.md)
- [T020](t020-markdown-parser.md)
- [T005](t005-database-schema-migrations.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

- `launcher/src/first_run.py`
- `launcher/src/protected_key.py`
- `backend/app/platform/config.py`
- `launcher/tests/test_first_run.py`

Owner-approved R2 scope expansion permits `launcher/src/main.py` and `backend/app/main.py` only, alongside the R1 production files and this task handoff. R2 is coding-only: tests are read-only, all execution checks are deferred, and R1 changes in `tasks/todo.md` and `docs/changelogs.md` must remain unchanged for host reconciliation.

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- Native/operator only: config.toml, DPAPI current-user key reference, data/Markdown roots. Validate migration/integrity/dry-run roundtrip/auth-profile; absence bridge may mark AI unavailable while local data works theo T013. No Google/admin credential read. Staging restore belongs T054.
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [ ] First-run valid native config persists protected key, browser/log/DB never key.
- [ ] Bad path/ACL/profile gives native remediation; restart no repeated credential entry if valid.
- [ ] Test dummy keys only; Windows DPAPI/ACL verification pending T057 when non-Windows.

## Test cases

1. Native fake-key provisioning, current-user DPAPI roundtrip.
2. Access denied, malformed config, missing key/profile; local vs AI readiness.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
python -m pytest launcher/tests/test_first_run.py -q
python -m mypy launcher
```

## Expected output

- First-run valid native config persists protected key, browser/log/DB never key.
- Focused commands đạt kết quả/exit code ghi trong criteria; negative probe phải fail đúng reason. Documentation tasks có conformance report thay cho application-test pass.
- Evidence ghi command, exit code, môi trường và artifact. Thiếu Windows/browser/provider environment là PENDING; không hoàn tất gate thiếu evidence.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Risk

- **Level:** `Critical`.
- Sai boundary có thể gửi dữ liệu/cost không được phép hoặc mất lịch sử học.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- Requires collecting/storing Google token/session or in-app backup → dừng.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`feat(T040): native first-run configuration và protected key store`

## Coding-only implementation handoff — 12/10/2026 (Asia/Bangkok)

- Preserved the provided clean worktree `/home/khanh/projects/vocabularies-t040-sol` on `feature/t040-first-run-protected-key`, base `2f82ac9e715e944465985169ab3b7a5e9d26c1bc`. The requested branch name differs; no branch/worktree creation or Git mutation occurred.
- Created `launcher/src/first_run.py` and `launcher/src/protected_key.py`; modified only `backend/app/platform/config.py` plus this card, `tasks/todo.md` and `docs/changelogs.md`. No tests, dependencies, contracts, schemas, real source data or credentials were changed.
- Native configuration uses T039's exact four TOML fields and existing path reader. New validation checks user-profile data containment, local directories, storage containment, source safety and restrictive current-user/SYSTEM ACLs. Configuration and protected key creation are exclusive and flushed; existing or incomplete files require explicit repair rather than overwrite, cleanup or silent replacement. The approved default data-directory creation is a separate native operation; selected Markdown roots must already exist.
- Current-user DPAPI uses `CRYPTPROTECT_UI_FORBIDDEN`, no machine-wide protection or prompts. Protected reads are bounded and reject missing/inaccessible/invalid material, unsafe ACLs, reparse points and hardlinks. Config/key operations retain ancestor handles and inspect opened handles. Protection and file interfaces permit explicit fake injection, with no non-Windows protection fallback. Resolved keys use `SecretStr`, stay outside `AppSettings`, and are unwrapped only at the bridge adapter constructor. Python immutable plaintext copies are not guaranteed erasable or resistant to debugger/crash-dump inspection.
- Dry-run validation reads Markdown with an 8 MiB cap, checks T020 parse/serialize equality and performs no database initialization or bridge probe. Explicit non-dry validation calls existing `Database.initialize()` migration/integrity checks and content-free bridge preflight after native profile confirmation. Missing/invalid key/profile or unavailable bridge leaves successful local storage checks intact. These helper results do not replace backend journal reconciliation, authoritative HTTP health, policy or consent admission.
- Dependency source/evidence inspected: T039 `DONE (CODING_ONLY)` with Windows/final evidence deferred; T007, T020 and T005 recorded `DONE` with historical focused evidence. Reused their actual launcher path reader/Win32 ownership primitives, bridge preflight, parser/serializer and database initializer. No dependency verification was rerun.
- **Scope blockers:** `launcher/src/main.py` must invoke provisioning/validation within the primary instance and present native inputs/guidance before browser opening. `backend/app/main.py` currently constructs `BridgeAdapter(api_key=None)` and must resolve the protected key for that runtime adapter, retaining an AI-unavailable adapter when resolution/profile fails. Both files are explicitly forbidden in this session and remain unchanged. No monkeypatch, import-time provisioning or implicit key loading was added. Operator confirmation is transient and supplies no new TOML fields or provider administration access.
- Source was inspected through `cat`, `sed`, `rg` and read-only `git status`/`git diff`; this is not an audit or executable verification. `launcher/tests/test_first_run.py` and the launcher test directory do not exist at this base; neither was created. No tests, build, lint, typecheck, audit, security scan, installation, migration execution, provider call or Windows run was performed. Task commands, CP19 and Windows DPAPI/ACL evidence remain `PENDING`; acceptance boxes remain unchecked.
- Applied the six requested agent-skills from the available 0.6.12 Windows plugin cache, Ponytail full and Unslop. The recorded 0.6.11 documentation-skill path is stale. Official Microsoft DPAPI/CreateFile/GetSecurityInfo documentation and Pydantic SecretStr documentation informed source decisions; fetching documentation is not runtime evidence.
- Intentionally untouched: launcher main/mutex, backend composition/bridge/HTTP/session, frontend, tests/fixtures, API/DTO/ADR/spec/CONSTRAINTS, migrations, CI, dependency locks, Google/browser/admin stores and real learning data. No commit, push, reset, merge, rebase or subagent. Next work is an explicitly scoped host-integration task for the two blocked composition paths, followed by authorized test authoring and independent verification; staging restore remains T054.

## R2 runtime integration handoff — 12/10/2026 (Asia/Bangkok)

- **Status:** `CODE_IMPLEMENTED_UNVERIFIED`, not `DONE`. Owner approval expanded the write scope to `launcher/src/main.py` and `backend/app/main.py`; R1's two composition blockers above are historical and addressed in this phase. Branch remains `feature/t040-first-run-protected-key`, original base `2f82ac9e715e944465985169ab3b7a5e9d26c1bc`.
- Preserved all R1 uncommitted and untracked files. R2 created no files. Modified the two approved composition files, this task card, and only concrete R1 integration gaps: missing-key classification in `backend/app/platform/config.py`/`launcher/src/protected_key.py`, checked native-file absence detection, and the obsolete wiring docstring in `launcher/src/first_run.py`. Shared `tasks/todo.md` and `docs/changelogs.md` retain their R1 contents; owner instructions defer their reconciliation to the host.
- The production `main()` now supplies primary-only configuration and backend factories to `run_launcher()`. Mutex acquisition and role validation precede configuration/provisioning/key work. Duplicate invocation only signals the existing instance and exits; it does not inspect configuration or protected keys, bind a socket, create a backend or issue/open another bootstrap.
- `WindowsDesktop.native_setup` implements operator interaction using Python's installed Tk dialog support: explicit default-data-directory confirmation or selection of an existing directory, existing Markdown-directory selection, configuration creation confirmation, and optional masked client-key entry. R1 performs path/access/ACL/ownership checks, bounded Markdown parse/round-trip and exclusive native config/key writes. Provisioned configuration is read through R1's wrapper around the exact T039 four-field version-1 TOML reader. Existing malformed, unsafe or inaccessible configuration never enters automatic replacement. A missing database under existing configuration requires explicit native confirmation for an intentionally new installation; refusal directs the operator to staging recovery and prevents automatic empty storage creation.
- Native dialog failure has a concrete `BLOCKED_CONTRACT` boundary, `WindowsDesktop.native_setup` requiring installed Tcl/Tk and an interactive Windows desktop. No success is manufactured if input is unavailable or cancelled. Optional key setup can be declined or unavailable without preventing valid local storage startup. Tk user profile scripts and default callback traceback reporting are disabled for this operator surface; debug tracing is refused. Native guidance uses fixed messages and never interpolates keys, source contents, bootstrap tokens or raw exceptions.
- The launcher passes its current-user `ProtectedKeyStore` reference and transient, explicit approved-profile confirmation to the same `create_app()` instance. A factory lifespan closure holds only the protected reference; plaintext and the reference are excluded from Pydantic settings and additional application-state fields. Backend composition runs the R1 typed resolver in the existing thread pool after local migration/integrity initialization, unwraps the resulting `SecretStr` only for the supported `BridgeAdapter` constructor, and drops that wrapper. Fixed internal statuses distinguish `MISSING`, `PROFILE_UNCONFIRMED`, `INVALID` and `RESOLVED`; resolved credentials do not claim bridge/AI readiness. A confirmed absent native key propagates as `BridgeKeyMissingError`; access, ownership, ACL, malformed or DPAPI failures remain configuration failures with native repair guidance and an unconfigured AI adapter.
- No bridge network preflight is added to startup. The existing AI admission coordinator retains consent/policy/provider/route/quota/deadline checks and request-owned preflight. Local database/search/review/quiz storage initialization, Markdown sync/journal reconciliation, authoritative health readiness, the reserved 127.0.0.1 socket, 10-second serving-readiness boundary, same-instance SessionStore, one-time browser bootstrap, focus event and bounded shutdown remain on the existing T039 paths. No endpoint, browser secret UI, second backend/bootstrap mechanism, TOML secret/profile field, environment-key fallback, Google/browser/admin store read, schema or policy change was introduced.
- **Limitations:** source inspection is not runtime correctness evidence. Installed Tcl/Tk availability and native keyboard/cancel behavior remain unverified. Windows DPAPI/ACL/reparse/hardlink/ownership behavior and restart recovery remain `PENDING`. Profile confirmation is transient and repeats when using an existing key, while successful protected-key restart reads require no plaintext re-entry. The existing adapter necessarily retains a Python plaintext string in private memory during its service lifetime; immutable Python/Tcl copies, debugger/state introspection and crash dumps have no zeroization guarantee. Restrictive R1 ACLs may require explicit operator repair; source/path check-use races within the accepted same-user host trust boundary remain. The existing separate AI policy-loading prerequisite is unchanged and may still deny AI dispatch.
- **Deferred verification:** no tests were created, modified or run; the T040 launcher test file is still absent. No application execution, migration execution, provider calls, builds, lint, typecheck, audit, security scan, benchmark, installation or Git mutation. Windows DPAPI/ACL evidence remains `PENDING`; acceptance boxes remain unchecked. Host must authorize test work and verify duplicate-launch ordering, all native cancellation/failure paths, missing/corrupt keys, local readiness without AI, database protection, restart key recovery and unchanged bootstrap/shutdown behavior before accepting T040.
- **Intentionally untouched in R2:** shared bookkeeping, `launcher/src/windows_mutex.py`, bridge adapter/bridge port, HTTP/session/API/DTO/frontend, tests/fixtures, contracts/ADRs/CONSTRAINTS, packaging, migrations, dependencies/locks, CI, real learning data and credential stores. No commit, push, pull, merge, rebase, reset, clean, stash or subagents. Ready for host code integration as unverified source; no acceptance or release claim.

## T040 owner-approved coding-only closure — 12/10/2026 (Asia/Bangkok)

- Owner explicitly approved PR #23 merge into `main`, merge commit `a5623be42baa421539975ff57d619aeb1789a256`. Implementation status is **`DONE (CODING_ONLY)` — `FINAL_VERIFICATION_DEFERRED`**. Earlier `BLOCKED_SCOPE` and `CODE_IMPLEMENTED_UNVERIFIED` notes describe historical R1/R2 work stages only.
- Code integrated: Windows primary-launcher native first-run provisioning, four-field `config.toml`, DPAPI current-user protected bridge-key store, source/path/ACL checks, launcher-to-FastAPI protected-key context and the existing `BridgeAdapter` construction boundary. Existing T039 single-instance, local storage readiness, AI consent/policy admission and one-time browser bootstrap remain design requirements, not independently verified runtime results.
- No tests, test creation, Windows launch, DPAPI/ACL runtime verification, Tcl/Tk packaging check, lint, typecheck, build, security scan, audit, profile/preflight probe or release checks were run. T056 must package Tcl/Tk for interactive Windows setup; missing native UI is a documented blocker, not a passing result.
- The three acceptance checkboxes and CP19 remain **unchecked** until project-wide verification. T054 may now begin independent code-only implementation against merged `main`; this closure does not claim successful restore, Windows installation or production deployment.

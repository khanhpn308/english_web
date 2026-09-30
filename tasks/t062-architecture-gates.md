# T062: Architecture import boundary gates

**Task ID:** `T062`  
**Title:** Architecture import boundary gates  
**Status:** `IMPLEMENTATION_DONE_BASELINE_BLOCKED`
**Goal:** Máy kiểm tra forbidden imports theo module ownership trước feature integration.  
**Suggested model:** GPT-6 Astra  
**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay trong danh sách. Nếu vượt khoảng 2 giờ hoặc phạm vi này, tách task trước khi làm tiếp.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [CONSTRAINTS.md](../CONSTRAINTS.md) architecture row
- [docs/api-contract.md](../docs/api-contract.md) module boundaries

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T053](t053-quality-security-gates.md)
- [T003](t003-backend-skeleton.md)
- [T004](t004-frontend-shell-routes.md)
- [T017](t017-typed-api-client.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

- `.dependency-cruiser.cjs`
- `pyproject.toml`
- `package.json`
- `scripts/tests/test_architecture_gate.py`

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

- Use dependency-cruiser+Python import-linter. UI never backend/secret/SQL; domain never HTTP or adapter concrete implementations. Handle namespace packages and false-positive type-only imports from port contracts by actual rules, no broad exemption. Synthetic bad module in temp fixture only.
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [x] npm architecture:check fails forbidden UI/domain import and allows typed domain ports.
- [x] Rules mapped to actual folder structure, no blanket ignore of future modules.
- [x] Rule config versioned, reproducible and no application behavior changed.

## Test cases

1. Inject temporary bad cross-module import and good port implementation fixture.
2. Cycle rule and generated DTO exempt only exact artifact path.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
python -m pytest scripts/tests/test_architecture_gate.py -q
npm run architecture:check
```

## Expected output

- npm architecture:check fails forbidden UI/domain import and allows typed domain ports.
- Focused commands đạt kết quả/exit code ghi trong criteria; negative probe phải fail đúng reason. Documentation tasks có conformance report thay cho application-test pass.
- Evidence ghi command, exit code, môi trường và artifact. Thiếu Windows/browser/provider environment là PENDING; không hoàn tất gate thiếu evidence.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Risk

- **Level:** `Medium`.
- Sai wiring/tooling có thể khiến task sau dùng command hoặc UI state không chính xác.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- Rules cannot enforce existing intended boundary without broad suppressions → dừng fix owner task.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`chore(T062): architecture import boundary gates`

## Resumed implementation handoff — 30/09/2026

Worktree `/home/khanh/projects/vocabularies-t062`, branch `task/t062`, HEAD/base
`b49a7227ecb26293920fad331cecba973a03d74a`. Preserved all six interrupted implementation
files without rewriting them. No application source, schema, public API, threshold,
runtime lockfile or unrelated task implementation changed. Optional cross-model review
remains skipped as previously instructed; validation uses the real tools.

### Reconstruction and ownership mapping

| File | Existing purpose / preserved implementation | Verification |
|---|---|---|
| `.dependency-cruiser.cjs` | Seven frontend rules; includes type-only edges, checks source presence, rejects unresolved imports; no shared/generated directory exclusion | Real frontend and synthetic fixtures pass |
| `pyproject.toml` | Pins import-linter 2.15; seven contracts rooted at the actual `backend.app` namespace | Seven kept, zero broken; graph includes every application Python source |
| `package.json` | Three architecture scripts; replaces T062 placeholder in task/full gates | Aggregate wiring test and standalone architecture gate pass |
| `package-lock.json` | Generated dependency-cruiser 17.4.3 lock additions | Only root dev dependency metadata plus 41 added package entries; no existing package changed/removed |
| `requirements-dev.lock` | Generated import-linter/Grimp/Rich dependency additions | Local virtualenv has import-linter 2.15 and Grimp 3.17 |
| `scripts/tests/test_architecture_gate.py` | 40 real-tool positive/negative/discovery/failure-path cases in isolated temporary fixtures | 40 passed |

Frontend ownership covers every source under `frontend/src`, including tests and type-only
edges. Backend/server, SQL/persistence, credentials and server builtins are forbidden;
cycles and unresolved imports fail. Library imports such as `react-dom/server` used by
existing tests are distinct from first-party backend/server paths.

Backend mapping: `platform` owns leaf interfaces/configuration; `application` orchestrates
ports/adapters and cannot depend directly or indirectly on `http`/`main`; `http` uses
application/platform and cannot directly import concrete adapters/persistence. Concrete
implementations cannot orchestrate, and each `adapters.*` implementation is independent
of its siblings and `persistence`. `main` composes the application. The backend cannot
import frontend, and sibling cycles are checked through depth 10. The namespace root
avoids omitting descendants without adding application `__init__.py` files.

The generated DTO rule matches only `^frontend/src/shared/api/generated\\.ts$` and permits
type-only incoming imports. It does not exempt the artifact's own imports from server/SQL/
credential/cycle rules. `not-generated.ts` accepts normal runtime imports but still fails
on a forbidden server dependency. No broad exemption is present.

Dependency rationale: existing lint/type tools do not enforce resolved ownership graphs,
indirect Python boundaries and import cycles. dependency-cruiser 17.4.3 (MIT) and
import-linter 2.15 (BSD-2-Clause) are development-only; neither enters the browser bundle
or application runtime dependencies. npm locks registry URLs/integrity hashes; Python
locks exact versions. License/version metadata was checked locally. OSV-Scanner 2.6.0
verified all three dependency locks with zero findings. Its downloaded release binary's
SHA-256 matches the pinned value in `docs/toolchain.md`; the binary remains outside the
repository in `/tmp/t062-osv-scanner-release`.

### Reproduced results and verification

First exact command, before edits:
`python -m pytest scripts/tests/test_architecture_gate.py -q --tb=short`
exited 1 with 20 failed / 20 passed. The shell selected the original
workspace virtualenv at `/home/khanh/projects/vocabularies/.venv`, lacking import-linter
and Grimp. `test_real_frontend` passed: historical frontend failure is not reproducible
from the current files. Classification: environment/tool selection, not an application
violation, incorrect rule, test assumption or generated DTO exception. No implementation
change was needed.

All subsequent commands prepend this worktree's `.venv/bin` to `PATH`; Python 3.12.3,
Node 22.23.2. Implementation files were frozen for final verification.

| Command | Exit | Result |
|---|---|---|
| `python -m pytest scripts/tests/test_architecture_gate.py -q` | 0 | 40 passed; subprocess-only tests collect no in-process application coverage, so pytest emits its existing no-data warning |
| `npm run architecture:check` | 0 | Frontend: 13 modules, 14 dependencies, zero violations; backend: 42 graph files, 81 dependencies, 7 kept / 0 broken; 40 focused tests passed |
| `npm run typecheck` | 0 | Zero TypeScript errors |
| `python -m ruff check scripts/tests/test_architecture_gate.py` | 0 | All checks passed |
| `python -m mypy scripts/tests/test_architecture_gate.py` | 0 | No issues in one source file |
| `python -m ruff format --check scripts/tests/test_architecture_gate.py` | 0 | Already formatted |
| `node_modules/.bin/eslint .dependency-cruiser.cjs` | 0 | No diagnostics |
| `npm run floor:check` | 0 | Floor clean |
| `npm run security:deps` | 0 | OSV-Scanner 2.6.0, zero findings across all three locks; initial missing-tool/sandbox setup failures exited 2, then a network-enabled retry passed |
| `git diff --check` | 0 | Clean |
| `npm run check:task` | 1 | Stops at existing T007 formatting failures; later aggregate stages do not run |

Negative probes: frontend forbidden first-party/server/credential/SQL and package imports
fail their named rules; Python application-to-HTTP, indirect application-to-HTTP, leaf-port,
concrete ownership and adapter independence imports fail their named contracts. Runtime
and type-only TS cycles and Python cycles fail. Exact generated runtime import fails;
generated sibling server import fails; valid React/shared API/type-only port imports and
namespace-package fixtures pass. Both discovery tests cover every real source file.
Missing/malformed configuration, empty/unanalyzable sources and missing Python contract
targets fail closed. Dependency scan uses `OSV_SCANNER_BIN=/tmp/t062-osv-scanner-release`;
no scanner/tool dependency was added to application runtime. `python -m pip check` also
exits 0 with no broken requirements.

Aggregate inherited failures only: `backend/app/adapters/bridge.py:113` and
`backend/tests/test_bridge.py:224`, `:244`, `:267` need Ruff formatting. Each current file
is byte-identical to `git show b49a722:<path>`; running Ruff format check on each base
file through stdin also exits 1. They were intentionally untouched. No claim is made
about downstream aggregate stages that were not reached.

### Scope, reconciliation and next work

Implementation files remain exactly as reconstructed. Bookkeeping changes only this
card, `tasks/todo.md` and `docs/changelogs.md`. `requirements.lock`, frontend/backend
application source/tests, contract exports, `CONSTRAINTS.md`, API/spec/ADRs and T052
files remain untouched. No reset, checkout, stash, cleanup, restore, integration,
staging, commit or push was performed.

T052 reconciliation must preserve `dependency-cruiser: "17.4.3"` in devDependencies,
the three architecture scripts, and task/full wiring to `npm run architecture:check`.
The npm lock adds root dependency metadata and 41 new package entries (527 inserted
lines); existing locked package entries are unchanged. Combine T052's package additions
and regenerate the lock from the combined manifest rather than replacing either side.

Next: resolve the inherited T007 formatting in its owner task and rerun the aggregate
gate. T052 integration remains separate.
Architecture acceptance is green; whole branch is not ready to commit. No commit authorized.

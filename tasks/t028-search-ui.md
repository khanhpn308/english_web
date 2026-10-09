# T028: Search/detail read flow

**Task ID:** `T028`  
**Title:** Search/detail read flow  
**Status:** `DONE` (code merged into `main` at `58dc087a9`; final acceptance `PENDING`)
**Coding completion policy (2026-10-09):** Implementation integrated into `main`; final project acceptance is pending. Historical TODO, environment limitations and unchecked acceptance cases below remain evidence history, not test PASS.
**Goal:** Search/detail read flow. Query/back-forward/reload persists intent; results/loading/empty/error accurate.  
**Suggested model:** Gemini  
**Estimated scope:** Một phiên tập trung; tối đa 5 file viết tay trong danh sách. Nếu vượt khoảng 2 giờ hoặc phạm vi này, tách task trước khi làm tiếp.

Owner-approved extension on 09/10/2026 permits the seven source/test paths listed below for T028 completion. Common bookkeeping remains separate from that implementation allowlist.

## Context cần đọc

- [CONSTRAINTS.md](../CONSTRAINTS.md)
- [AGENTS.md](../AGENTS.md)
- [docs/ui-architecture.md](../docs/ui-architecture.md) J3 & Canonical design system (shadcn/ui)
- [docs/spec.md](../docs/spec.md) AC-07/32

Đọc handoff của dependencies và source/tests hiện có trong phạm vi sửa. Các path source/config là vị trí dự kiến; repository hiện chỉ có tài liệu.

## Dependencies

- [T081](t081-app-shell-shadcn-migration.md)
- [T027](t027-search-api.md)
- [T017](t017-typed-api-client.md)
- [T010](t010-error-handling-recovery.md)
- [T052](t052-browser-test-harness.md)

Mọi dependency phải có evidence hoàn tất. Task ID không biểu thị thứ tự chạy; dùng [task-plan.md](../docs/task-plan.md).

## Files được phép sửa

- `frontend/src/features/search/SearchPage.tsx`
- `frontend/src/features/search/WordDetail.tsx`
- `frontend/src/features/search/search.test.tsx`
- `frontend/tests/e2e/search.spec.ts`
- `frontend/src/app/AppShell.tsx`
- `frontend/src/app/AppShell.test.tsx` (owner-approved T028 test scope extension, 09/10/2026)
- `frontend/tests/e2e/shell.spec.ts` (owner-approved T028 test scope extension, 09/10/2026)

Khi thêm endpoint, regenerate OpenAPI/DTO do T017 quản lý; không sửa generated file bằng tay. Common bookkeeping được phép: thẻ task này, [todo.md](todo.md), [changelog](../docs/changelogs.md), artifact verification đã loại dữ liệu nhạy cảm.

## Files không được sửa

- Source/config/feature ngoài danh sách; không đổi threshold trong `CONSTRAINTS.md`.
- Dữ liệu từ vựng thực `docs/vocabularies/`, credentials, screenshot, Google token/session store hoặc proxy admin configuration.
- Spec/API/UI/ADR ngoài danh sách. Contract discrepancy cần T013 hoặc task clarification riêng ghi rõ trước khi tiếp tục.

## Implementation notes

- URL query/filter/cursor; abort obsolete read, stable list identity; explicit browse vs empty. Editing supplied T030, not fake-save. Đăng ký flow vào route thật, không chỉ render isolated component; build và harness dùng cùng router.
- Thiết kế component theo design system: `SearchPage` và `WordDetail` sử dụng canonical primitives (`Input`, `Button`, `Card`, `Badge`...) từ `frontend/src/components/ui/` và semantic tokens từ T081; không duplicate primitives.
- Test behavior/error paths trước hoặc cùng implementation; source validity, privacy, correlation và operation receipts được kiểm tra ở boundary có liên quan.
- Không chạy inference thật trong automated tests. Lệnh thiếu tool/runtime phải ghi `PENDING`, không báo PASS.

## Acceptance criteria

- [ ] Query/back-forward/reload persists intent; results/loading/empty/error accurate.
- [ ] Expired cursor restarts first page with notice; stale response cannot overwrite latest.
- [ ] Detail shows source validity/verification; keyboard works offline local API.

## Test cases

1. Rapid typing reverse response order; URL restore; empty match.
2. Offline API healthy vs API stopped; long Vietnamese labels.

## Verification commands

Chạy tại project root, Python trong venv đã cài lock T001/T058. Sau focused commands, chạy applicable checks trong CONSTRAINTS và `npm run check:task` khi các owner T053/T062/T063 đã hoàn tất.

```text
npm run test:frontend -- frontend/src/features/search/search.test.tsx
npm run test:e2e -- frontend/tests/e2e/search.spec.ts
```

## Expected output

- Query/back-forward/reload persists intent; results/loading/empty/error accurate.
- Focused commands đạt kết quả/exit code ghi trong criteria; negative probe phải fail đúng reason. Documentation tasks có conformance report thay cho application-test pass.
- Evidence ghi command, exit code, môi trường và artifact. Thiếu Windows/browser/provider environment là PENDING; không hoàn tất gate thiếu evidence.
- Handoff ghi files sửa, files chủ ý không sửa, kết quả, risk còn lại và next task. Chỉ cập nhật `DONE`/checklist sau verification; commit khi đã được ủy quyền.

## Risk

- **Level:** `Medium`.
- Sai wiring/tooling có thể khiến task sau dùng command hoặc UI state không chính xác.
- Mitigation: tests âm/dương, phạm vi thẻ, evidence thực và stop conditions. Không giảm quality bar để xử lý failure.

## Stop conditions

- Needs browser persistence as canonical data → dừng.
- Floor/quality gate thất bại, material requirement chưa có precedence, credential/action ngoài phạm vi, hoặc destructive change chưa được task cho phép.
- Không tự tạo remote, push, publish, bật paid fallback hay gọi real inference từ automated test.

## Commit message đề xuất

`feat(T028): search/detail read flow`

## Source completion handoff, 09/10/2026 (Asia/Bangkok)

- Task status remains `TODO`; implementation status is `SOURCE_COMPLETE_UNVERIFIED`. Acceptance boxes remain unchecked until Host verification.
- Worktree: `/home/khanh/projects/vocabularies-t028-codex`; branch: `feature/t028-codex`; BASE_SHA / inspected HEAD: `aeaaa322ef8f3b94a6ab9f2330dd2ef90b3dcd97`.
- Owner approved extending the original five implementation/test paths with `frontend/src/app/AppShell.test.tsx` and `frontend/tests/e2e/shell.spec.ts`. This is one Search/detail flow, not a second subsystem.
- Original in-flight implementation was preserved. Existing T028 modifications in `AppShell.tsx` were inspected and left unchanged this session. No synchronization with main or manual T033 import occurred.

### Requirement review and authored evidence

| Requirement | Source evidence and regression coverage |
|---|---|
| Typed Search API | Uses T017 generated query keys, WordFormCollection and WordFormDetail with the shared same-origin API client. Validates consumed response shapes before rendering. No generated files or endpoints changed. |
| URL state/navigation | URL owns query/filter/sort/page size/cursor. Mounted AppShell tests cover initial query and popstate restoration; real-shell Playwright cases cover Search/detail navigation, return URL, reload and browser back/forward. |
| Cursor/races | AbortController, generation guard and keyed state reject obsolete reads, including A → B → A. Existing reverse-order/unmount/page/reset/expiry tests retained. Expiry removes only cursor, keeps filters and replaces history with a first-page notice. |
| Word Detail/source validity | Real source dates, source health, aggregate and per-meaning/example verification, revision and card information render. Invalid/missing/absent sources hide current study content; mixed valid/invalid sources keep current data available. Tests retain stale content to prove withholding. Editing remains T030. |
| Error recovery | Empty results differ from local network, storage, session, invalid-query and missing-form errors. Malformed success JSON and malformed error codes use safe recovery instead of perpetual loading/render errors. User-triggered retries keep URL intent; raw messages and unsafe request IDs are withheld. |
| Accessibility | Labelled native controls, semantic result lists/links, route focus and live regions reviewed. Shell announcement locator now selects its own status region. Keyboard Enter/Tab, heading focus, Search/Detail axe assertions and long Vietnamese/reflow checks authored. Browser/contrast/zoom/performance evidence is pending. |
| Regression/scope | Corrected only obsolete Search/detail placeholder assertions. Preserved placeholder Card/parameter coverage on the unimplemented quiz route and all unrelated shell assertions. Fixture mocking is at the HTTP boundary; real AppShell/Search/Detail remain mounted. |

### Checks and integration limits

`TESTS: NOT_RUN`. `AUDIT: SOURCE_REVIEW_ONLY`. `GIT_MUTATIONS: NOT_PERFORMED`.

Read-only inspection used `git status --short`, `git diff --stat`, path-specific `git diff`, `git rev-parse HEAD`, `git branch --show-current`, `rg`, `cat`, `sed` and `tail`. No tests, builds, lint, typecheck, executable audits, dependency installation or browser execution were performed. No passing result, measured coverage, performance or accessibility conformance is claimed.

Host verification commands, recorded but not executed:

```text
npm run test:frontend -- frontend/src/features/search/search.test.tsx frontend/src/app/AppShell.test.tsx
npm run test:e2e -- frontend/tests/e2e/search.spec.ts frontend/tests/e2e/shell.spec.ts
npm run test:a11y
npm run build
npm run check:task
```

Expected outcomes: zero task/type/lint/security failures; Search and detail retain URL state through reload/history; newest read wins; cursor expiry restarts safely; invalid sources and malformed responses do not expose current/stale content or private errors; keyboard and serious/critical accessibility checks pass. These are pending outcomes, not observed results. Changed-code coverage and other CONSTRAINTS gates remain mandatory.

- Shared AppShell risk: Host reports main advanced to `e8ebfe8` after T033 changed `AppShell.tsx`. Host must reconcile T028 imports, pathname-plus-query state, popstate focus, push/replace search navigation and real Search/Detail rendering with T033's shell. Existing unrelated-route tests retain this base's behavior and need comparison with T033 tests during integration.
- Known blockers: Host AppShell reconciliation and executable verification. Local task metadata still lists T010/T027 as TODO despite their existing source; Host owns authoritative dependency/integration status.
- Scope exceptions: exactly the two owner-approved test files. No additional implementation path, dependency, generated-artifact, schema or quality-bar exception. Native input/select controls match existing Lookup practice; the installed UI directory has Button/Card/Dialog and no Input/Select primitive.
- Intentionally untouched: existing `AppShell.tsx` delta this session, backend, generated DTO/OpenAPI, shared API/errors, Lookup/consent, design-system primitives/config, spec/ADRs, user vocabulary data and all T033 work.
- Next action: Host reconciliation and verification of T028; T030 remains the separate editing task. Source handoff is ready, but integration/release gates and task DONE are not approved by source review.

### Skills read and applied at actual installed paths

The legacy AGENT.md references 0.6.11; installed engineering skills were found at 0.6.12. Owner instructions override runtime/commit steps and the cross-model CLI audit flow. Skill application here is source review and authored tests only where execution is prohibited.

| Actual SKILL.md path | Application |
|---|---|
| `/mnt/c/Users/khanh/.codex/plugins/cache/agent-skills/agent-skills/0.6.12/skills/frontend-ui-engineering/SKILL.md` | Canonical Button/Card primitives, native labelled controls, semantic tokens, focus and reflow source review. |
| `/mnt/c/Users/khanh/.codex/plugins/cache/agent-skills/agent-skills/0.6.12/skills/incremental-implementation/SKILL.md` | Preserved the in-flight implementation; completed shell tests and recovery fixes as separate scoped edits. |
| `/mnt/c/Users/khanh/.codex/plugins/cache/agent-skills/agent-skills/0.6.12/skills/test-driven-development/SKILL.md` | Authored malformed-response regressions before the corresponding fixes; RED/GREEN execution deferred by owner instruction. |
| `/mnt/c/Users/khanh/.codex/plugins/cache/agent-skills/agent-skills/0.6.12/skills/api-and-interface-design/SKILL.md` | Checked generated query/collection/detail DTOs and existing typed API/error boundary; no contract changes. |
| `/mnt/c/Users/khanh/.codex/plugins/cache/agent-skills/agent-skills/0.6.12/skills/debugging-and-error-recovery/SKILL.md` | Traced obsolete assertions and malformed-response failures to their source; added explicit retry regressions. |
| `/mnt/c/Users/khanh/.codex/plugins/cache/agent-skills/agent-skills/0.6.12/skills/doubt-driven-development/SKILL.md` | Three bounded fresh-context, read-only adversarial reviews. Actionable malformed success/error findings corrected; final correction reviewed locally. No external CLI audit. |
| `/mnt/c/Users/khanh/.codex/plugins/cache/agent-skills/agent-skills/0.6.12/skills/security-and-hardening/SKILL.md` | Reviewed response shape, escaped content, same-origin reads, bounded correlation IDs, local return targets and dictionary URL allowlist. |
| `/mnt/c/Users/khanh/.codex/plugins/cache/agent-skills/agent-skills/0.6.12/skills/browser-testing-with-devtools/SKILL.md` | Applied keyboard/landmark/network/accessibility verification guidance to authored Playwright cases; no browser execution or observed browser evidence. |
| `/mnt/c/Users/khanh/.codex/plugins/cache/agent-skills/agent-skills/0.6.12/skills/git-workflow-and-versioning/SKILL.md` | Inspected branch/base/diff using read-only Git; preserved uncommitted work and identified shared AppShell reconciliation risk. |
| `/mnt/c/Users/khanh/.codex/plugins/cache/agent-skills/agent-skills/0.6.12/skills/documentation-and-adrs/SKILL.md` | Recorded the authorized extension, source evidence, deferred gates and handoff; no new architectural decision or ADR. |
| `/home/khanh/.agents/skills/unslop/SKILL.md` | Plain-language updates, changelog and handoff with no invented verification claims. |

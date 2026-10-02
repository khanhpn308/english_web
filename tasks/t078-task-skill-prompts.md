# T078: Require relevant agent skills in implementation and fix prompts

**Task ID:** `T078`
**Title:** Require relevant agent skills in implementation and fix prompts
**Status:** `DONE`
**Goal:** Select task-relevant installed addyosmani/agent-skills workflows, explicitly require them in planning/Worker/Fix prompts, and record reproducible skill references without expanding task authority.

## Context cần đọc

- AGENTS.md, AGENT.md, CONSTRAINTS.md
- docs/orchestrator.md; ADR-0006 and ADR-0007
- T075/T076/T077 evidence; tools/orchestrator core/workflow and tests
- Upstream agent-skills README and docs/antigravity-setup.md, codex-setup.md, gemini-cli-setup.md

## Dependencies

- T076
- T077

## Files được phép sửa

- `tools/orchestrator/core.py`
- `tools/orchestrator/workflow.py`
- `tools/orchestrator/skills.py`
- `tests/orchestrator/test_workflow.py`
- `tests/orchestrator/test_skills.py`

Documentation: docs/orchestrator.md. Common bookkeeping: this card, tasks/todo.md, docs/changelogs.md.

## Files không được sửa

Product source/tests/task status/checkpoints, migrations, public API/generated
files, provider CLI flags/model routing, dependency manifests/locks, scanner and
quality thresholds, credentials, global CLI settings or historical run artifacts.
No plugin download/upgrade, autonomous model routing, new recovery or framework.

## Acceptance criteria

- [x] Select actual installed skills from owned implementation paths/title/objective/acceptance; do not activate all skills or classify from boilerplate/dependency references.
- [x] Resolve paths portably through explicit skills_root/environment override or supported native locations; missing/unreadable/changed required skills are truthful setup failures.
- [x] Planning receives a pinned skill policy; Python guarantees explicit read/apply requirements in saved Worker/Fix handoffs and actual invocations; Auditor checks application evidence without silently fixing source.
- [x] Immutable skill manifest pins names, reasons, paths and hashes; task/user/repository authority and host Git/privacy/verification rules override skill suggestions. No full meta-router or whole pack is preloaded.
- [x] Older runs/config schemas remain readable and handoffs are not rewritten; baseline/RED/GREEN/aggregate verification and setup/usage docs recorded with fake agents only.

## Verification commands

```text
python -m pytest tests/orchestrator -q --no-cov
python -m ruff check .
python -m ruff format --check .
python -m mypy backend tools/orchestrator tests/orchestrator
npm run check:task
```

## Risk / stop conditions

Skills guide reasoning, never task scope, Git permissions, state transitions or
new product requirements. Do not treat a skill mention as proof it was followed.
No native plugin auto-install, new global approvals, all-skill context injection,
forced cross-model reviews, Worker commits or unbounded Fix cycles.

## Discovery

Clean local main f4adf1276a40c834459ba25c24225b1d63fd963e.
Current prompts depend on model-written skill mentions; Plan/Fix only require
nonempty strings. Existing agy plugin under ~/.gemini/config/plugins/agent-skills
is version0.6.11; core native skills are already installed. Worker agy intentionally
disables slash-command expansion, so instructions must identify readable SKILL.md
paths and must not depend on wrapper/slash activation.


## Verification and handoff (02/10/2026, Asia/Bangkok)

Worktree: vocabularies-t078-task-skills; branch: feature/task-t078-task-skills.
Frozen local main: f4adf1276a40c834459ba25c24225b1d63fd963e.
T076/T077 DONE verified from local cards, implementation/tests and main ancestry.
No dependency/product checkpoint status changed by this task.

| Command / phase | Exit | Result |
|---|---|---|
| Baseline: pytest tests/orchestrator -q --no-cov | 0 | 208 passed, 173.04s, before editing |
| RED: required prompt/missing-pack workflow cases | 1 | 3 failed; old prompts omit mandatory skills and missing pack incorrectly reaches DONE |
| RED: new skill unit module before implementation | 2 | ModuleNotFoundError for missing tools.orchestrator.skills |
| GREEN: final skill + legacy cases | 0 | 24 passed, 110 deselected, 13.37s; real temporary Git and fake agents |
| Ruff check . / format --check . | 0 | No lint errors; 182 files formatted |
| Mypy backend tools/orchestrator tests/orchestrator | 0 | 53 source files checked |
| npm ci | 0 | Existing lock installed; no manifest/lock changes |
| SOURCE FREEZE: npm run check:task | 0 | 810 Python tests, including 232 orchestrator tests; 38 frontend and 40 architecture tests; seven import contracts kept |
| Aggregate coverage/security | 0 | Changed coverage96.27%, total92.90%; Gitleaks/Semgrep/OSV zero findings |
| git diff --check | 0 | No whitespace errors |

| Invariant | RED / executable evidence | Mechanism | Final result |
|---|---|---|---|
| Relevant workflows follow actual task nature | Scoring/API/UI/Windows/migration/docs/browser/CI/performance/observability cases | Owned paths + title/goal/acceptance only, no boilerplate/Task ID activation | PASS |
| Both Worker and Fix explicitly read/apply skills | Initial missing-block RED; PASS and full remediation flow tests | Python prepends pinned section to saved model handoffs; canonical invocation checks remain | PASS |
| Skill setup/evidence cannot be invented or change mid-run | Missing/invalid/oversized/changed files; Planner/Worker mutation negative flows | Bounded UTF-8 reads, name validation and immutable manifest/hash checks before/after agents | PASS; no promotion |
| Skill suggestions cannot grant scope or Git authority | Actual planner/Worker/Fix/Auditor prompt assertions | Host precedence, existing schema/allowlist/Git/evidence fences preserved | PASS |
| Old run/config/handoff compatibility | Synthetic no-manifest safe-barrier resume; two historical states read-only | Optional default root; no historical handoff rewrite, state compatibility in memory | PASS |

Read-only native discovery resolves actual T021/T059/T018/T008 cards against the
already installed agy agent-skills0.6.11 pack. T021 adds security/doubt; T059 stays
pure logic/core workflow; T018 adds frontend/browser/consent; T008 adds API/security
without classifying its generated DTO as UI implementation. Evidence is saved in
.agent-runs/T078/verification/installed-skill-manifests.json.

SOURCE FREEZE hashes stayed unchanged throughout the final aggregate gate. Only
this card, task list and changelog bookkeeping changed afterwards. Two inherited
AppShell fast-refresh warnings remain warnings (zero lint errors). No real model
call or paid inference was used. Upstream installation commands in the guide are
documented setup examples, not a claim that plugins were installed this session.

Scope audit PASS: exactly five implementation/test files plus guide/card/task list/
changelog. Product source/tests/status, migrations, contracts/generated artifacts,
provider permissions/routing/CLI flags, dependency manifests/locks, quality/security
thresholds, user vocabulary, credentials, global plugin settings and historical run
artifacts are intentionally unchanged. No database, scheduler or Level 2 features.

Known limits: pinned hashes cover SKILL.md entrypoints, not every supporting file.
The system guarantees explicit skill instructions and verifies referenced files,
but cannot prove an LLM read/applied a workflow from its declaration alone; Auditor
must assess concrete source/test/evidence. Skills guide reasoning, not transitions.
New runs use the policy; already planned runs keep their historical handoffs.

Bookkeeping: this card DONE, T078 task-list checkbox checked; no product task or
checkpoint newly unlocked. Next work follows the owner's selected product task.
Git: focused commit and ff-only local-main promotion authorized by the existing
owner instruction, subject to clean-main/staged-scope/secret checks; no push.

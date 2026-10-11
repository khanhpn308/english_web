# Contract conformance 003 — T044 implementation checkpoint

**Tool:** `t044-static-contract/1` — `scripts/audit_contract.py`  
**Implementation status:** `IMPLEMENTED_UNVERIFIED`  
**Contract/release evidence:** `PENDING`  
**Session:** `CODE_IMPLEMENTATION_ONLY`, 12/10/2026, Asia/Bangkok  
**Branch:** `feature/t044-contract-audit-tooling` (existing provided worktree)  
**Base SHA:** `2f82ac9e715e944465985169ab3b7a5e9d26c1bc`

This checkpoint is written from source inspection. The checker has not been executed. No generated finding, source fingerprint, test result, contract PASS or release approval is claimed. It may be replaced by the tool's report only in an authorized audit session. Other review artifacts and their `REVIEW_STATUS` are untouched.

## Authority and extraction

Product behavior comes from `CONSTRAINTS.md`, `docs/api-contract.md`, `docs/spec.md` and approved ADRs. ADR-0005 clarifies ADR-0004; ADR-0008 supplies answer preconditions/receipt rules; ADR-0009 supplies prospective SQLite study-history and nullable streak rules. Historical review findings are evidence of past decisions, not current endpoint registrations or executable instructions.

Production route registrations originate in `backend/app/main.py` and its included HTTP routers. Request/response fields, requiredness, explicit bounds and enum annotations originate in the corresponding Pydantic models and imported model definitions. Public errors originate in `backend/app/http/errors.py`, route-local catalogs/models and the production middleware. Validator-only semantics remain an explicit runtime verification responsibility.

`scripts/export_contract.py` calls `create_app().openapi()`, normalizes the operation path/model names, projects error detail variants, adds error responses and recursively sorts dictionaries. It writes `contracts/openapi.json`, then invokes `openapi-typescript` for `frontend/src/shared/api/generated.ts`. Those snapshots are comparison inputs, not independent product authority. Exporter-injected envelopes do not prove that raw production `/openapi.json` has the same declarations. Application construction can initialize a local telemetry sink; the new checker uses AST and does not import or instantiate the application.

## Deterministic input scope

The implementation reads repository-relative source files only:

- Rules, constraints, API/spec, task-plan and applicable `docs/adr/*.md` files.
- Production composition root, included HTTP routers, error catalogs and statically resolved model/import definitions.
- Checked OpenAPI/TypeScript snapshots, exporter, existing contract and architecture test source, and package metadata.
- Task-card FR/AC, implementation, focused-test and evidence references. Referenced test definitions are inspected without execution.
- Historical conformance/design reports and referenced review evidence. Report 003 is excluded as an input to avoid self-referential output.

Paths and schema references are normalized; records and findings use stable ordering. The generated output includes one input-scope fingerprint without timestamps or host absolute paths. Markdown fences, task prose, example values and review snippets are parsed as data; nothing in them is executed. No credentials, user vocabulary, provider access or dependency installation is required.

Default execution writes Markdown to stdout; `--json` emits structured indices. Only explicit `--write-report` writes this fixed report path. The checker does not write application source, schemas, DTOs or specifications. No package/CI command was added outside the allowlist.

## Implemented checks — execution pending

| Area | Implemented source behavior | Evidence status |
|---|---|---|
| API surfaces | AST router inclusion/decorators versus current endpoint tables and snapshots; missing methods/paths, duplicates, schema-excluded shell routes and historical/deprecated classification | PENDING |
| Responses/errors | Success/status/schema references, required typed error fields, literal shared/local code catalogs and ErrorDetails discriminator variants; raw declaration gaps kept separate from exporter projections | PENDING |
| Source/snapshot drift | Explicit Pydantic fields, inherited camelCase/serialization aliases, requiredness, nullability, enums and Field bounds; custom schema projection is unresolved evidence rather than assumed annotation equality | PENDING |
| Documented schemas | Named declarations/fixtures, resource aliases, missing/extra fields, explicit enum drift and nullable semantics; unclear prose bindings remain pending | PENDING |
| Generated DTO drift | OpenAPI/TypeScript path/schema inventories and simple object field/optionality/nullability comparison; full pinned-generator equality remains T017 responsibility | PENDING |
| Examples/bounds | Named JSON fixtures and HTTP bodies/query examples; required/unknown fields, types, unions, enums, represented bounds, quiz total/per-type counts, byte caps and redacted credential headers | PENDING |
| Privacy | Sensitive field/category detection with diagnostic and pre-submission question boundaries; nested diagnostic schema references; credentials, PII, filesystem/DB paths, arbitrary URLs and traces withheld from output | PENDING |
| FR/AC evidence | Explicit requirement references mapped to task IDs, existing source paths, route/schema associations, focused test definitions, evidence references and verification owners; missing/stale references reported | PENDING |
| Reporting | Stable severity/status/location/owner records, structured and Markdown output, fail-closed exit status and preserved findings when later extraction fails | PENDING |

No PASS or FAIL result was produced in this session. Future result meanings are:

| Result | Meaning |
|---|---|
| PASS | Actual available evidence for the named static check only; test presence is never test success |
| FAIL | Deterministic contract violation found by the executed check |
| PENDING | Missing extraction, runtime, tool, platform or current-source evidence |
| OWNER_DECISION_REQUIRED | Conflicting approved product semantics; stop the affected check and identify its owner/files/fields |
| BLOCKED_SCOPE | Required write/integration outside the allowlist, or an unsafe/unavailable report destination; never apply a workaround |

Exit 1 identifies deterministic violations/owner blockers; exit 2 identifies incomplete evidence. Runtime release evidence remains pending even if the supported static checks have evidence. The tool never inserts example defaults or repairs a document to make a check pass.

## Dependency implementation and pending acceptance

These paths were inspected as source context. Existing tests are references only; none ran here. Earlier task numbers and coding-only DONE statuses do not certify acceptance.

| Owner | Existing implementation evidence | Focused test/evidence owner | Pending evidence |
|---|---|---|---|
| T013 | `docs/reviews/contract-conformance-002.md`, ADR-0004/0005 | T013 document crosswalk C013-01–11 | Historical documentation evidence does not prove this runtime |
| T008 | `backend/app/http/lookups.py`, enrichment lookup service | `backend/tests/test_lookups.py` | Current-head contract, consent, deadline and privacy acceptance |
| T024 | `backend/app/http/word_forms.py`, `backend/app/application/save_word_family.py` | `backend/tests/test_save_word_family.py` | Journal/source conflicts, replay and Windows file behavior |
| T027 | `backend/app/http/search.py`, vocabulary search/index services | `backend/tests/test_search_api.py` | Cursor/source-version acceptance and named 100k Windows performance |
| T029 | PATCH adapter and `backend/app/application/edit_word_form.py` | `backend/tests/test_edit_word_form.py` | Source revision/hash and preserved-history failure paths |
| T032 | `backend/app/http/review.py`, review/SRS modules | `backend/tests/test_review_api.py` | Due/new queue, provenance and once-only event acceptance |
| T035 | `backend/app/http/quiz.py`, `backend/app/application/create_quiz.py` | `backend/tests/test_quiz_creation.py` | Public snapshot privacy, eligibility, consent and deadline boundaries |
| T047 | `backend/app/http/quiz_answers.py`, `backend/app/application/save_answer.py` | `backend/tests/test_quiz_answers.py`, ADR-0008 | Historical receipts, revision conflicts and restart acceptance |
| T048 | `backend/app/http/quiz_submissions.py`, `backend/app/application/submit_quiz.py` | `backend/tests/test_quiz_submission.py` | Atomic result/SRS/idempotency and terminal restoration; final verification deferred |
| T049 | `backend/app/http/feedback.py`, `backend/app/application/feedback.py` | `backend/tests/test_feedback.py` | Comments-only validation, failure history, consent/retry and deadline acceptance; final verification deferred |
| T037 | `backend/app/http/dashboard.py`, `backend/app/dashboard/formulas.py`, `backend/app/dashboard/history.py`, ADR-0009 | T037; referenced `backend/tests/test_dashboard.py` absent in this worktree | Prospective coverage/nullable streak, independent metrics and bounded history performance; final verification deferred |
| T046 | `backend/app/http/status.py`, `backend/app/platform/metrics.py`, production instrumentation | T046; referenced metrics/status tests absent in this worktree | RED overflow/no-data, read-only status/consent, privacy and consumer semantic-validation observations; final verification deferred |
| T061 | `backend/app/platform/alerts.py`, Status/runbook routes and integration | `docs/reviews/observability-evidence-001.md`; focused alert tests absent in this worktree | Qualified search producer absent (`NO_DATA`); two failed health probes owned by T039 launcher; pinned DTO regeneration/runtime acceptance pending |

T061 records cached generator 7.13.0 against declared 7.4.2. T017 must establish reproducible generated artifacts with the pinned tool. No regeneration was attempted here.

## Source-inspection candidates — no audit verdict

The following are handoff locations for the first authorized execution. They are not generated FAIL results and are not silently repaired.

| Priority | Exact fields/locations to reconcile | Responsible owner | Evidence status |
|---|---|---|---|
| High | Documented `/api/v1/capabilities` versus production router registrations and snapshot path inventory | T006/T013/T017 | PENDING |
| High | API `ErrorDetails.kind` union includes RESOURCE; exporter projection lacks that variant | T013/T017 | PENDING |
| High | API `Operation.aiProvenance` versus OperationView/exported Operation fields; internal stored provenance does not establish public DTO coverage | T013/T014/T017 | PENDING |
| High | WordForm/SaveResult examples' `sourceRefs[].status`; lookup examples' `ipaStatus`, `cambridgeStatus`, `meaningsEn/Vi[].language` versus required source/generated fields | T013/T008/T024/T027 | PENDING |
| High | Dashboard common fixture `objectiveAccuracy.mcq/cloze.attempted` and `.accuracy` versus generated DashboardObjectiveScore; ADR-0009 governs unknown streak independently | T013/T037 | PENDING |
| High | Feedback compact declaration/example `operationId`, accepted criterion list, and endpoint `201/202` versus implemented response model/status | T013/T049 | PENDING |
| Medium | Source sorting prose versus source route's `noteDate/status/revision` allowlist; field-specific nullable/enum prose versus compact declarations | T013/T023/T027 | PENDING |
| Medium | Raw factory OpenAPI error declarations versus exporter-added schemas/responses and the API's machine-source statement | T013/T017 | PENDING |

No new product choice has been resolved by this implementation. The tool records explicit limit-authority conflicts as OWNER_DECISION_REQUIRED and stops affected example/bounds checks. Missing local prose bindings are pending owner verification, not automatic requests to change settled ADR policy. Product/spec/ADR repairs belong to T013 or a separately authorized owner card.

## Limitations and deferred verification

AST handles the current literal router/model patterns without executing code. Dynamic registration, inherited/custom schema callbacks, validators, full JSON Schema formats/dialect semantics and exact generator output equality require existing verification owners. Compact Markdown declarations are not a complete schema language: unbound prose and aliases remain explicit pending evidence. Privacy checks report bounded field/category metadata and do not replace the existing T063 redacted scanner or sentinel tests.

FR/AC-to-task references and task-to-route/schema/test associations are deterministic indices. They do not establish that every assertion in a test corresponds to its referenced requirement, or that historical evidence belongs to the current head. Runtime, manual UI/accessibility, Windows, bridge profile and performance acceptance remain with their recorded owners/CP22.

`scripts/tests/test_audit_contract.py` does not exist at the inspected base and is read-only under this session's explicit restrictions. No test was created. A verification worker needs authorization to add focused positive/negative cases, including missing response/error fields, stale snapshots, named aliases, valid negative fixtures, redaction, pending inputs and deterministic repeat output.

Commands reserved for that later authorized session, all **NOT RUN** here:

```text
python scripts/audit_contract.py
python -m pytest scripts/tests/test_audit_contract.py -q
npm run test:contract
```

Applicable quality/security/platform gates also remain pending. Tool/report implementation is ready for coding-only host integration; task acceptance and release cleanliness are not complete.

## Files intentionally untouched

Backend/frontend application source, all tests, exporter, OpenAPI/DTO snapshots, API/spec, ADRs, CONSTRAINTS, dependency cards/versions, package/CI configuration, historical review status, user data and credentials. No Git mutation, provider call, dependency install, generator, test, audit, build, lint, typecheck or security scan occurred. The existing worktree was clean before these T044 additions; no unrelated change was replaced.

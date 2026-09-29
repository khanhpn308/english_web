# API contract — Vocabulary learning app

**Status:** Planning baseline — implementation freeze follows generated-contract verification

**Date:** 29/09/2026 (`Asia/Bangkok`)

**Scope:** v1 local Windows application, one local user, React browser UI and FastAPI backend on loopback.

This document is the contract-first boundary for the implementation. ADR-0004 is the owner-authorized v1 policy authority for the former `OQ-01`–`OQ-14`; [ADR-0005](adr/0005-contract-clarifications.md) supplies the exact T013 oracles and resolves conflicting examples. The question text in the spec is historical. Generated-schema checks and security/performance evidence remain implementation gates.

## 1. Technology baseline verified against official documentation

The table records the original planning baselines. T001/T002/T058 now own the installed versions and lockfiles in [toolchain.md](toolchain.md); the version descriptions below do not override those locks.

| Area | Choice | Baseline / limit to pin at bootstrap | Why |
|---|---|---|---|
| Browser UI | React + TypeScript | React 19.x (official docs report 19.3 as latest on 29/09/2026); TypeScript exact version to pin in the frontend lockfile | Component model and browser-native semantics fit the tab UI; no server rendering is needed. React's stable channel follows semver. |
| Frontend build | Vite | Vite 8.x; Node.js `20.19+` or `22.12+` as required by the current Vite guide | Produces static assets that FastAPI can serve; no Node process is required at runtime. |
| Backend | Python + FastAPI + Pydantic | Python 3.12+; FastAPI 0.14x line and Pydantic version selected together and frozen in the Python lockfile | FastAPI generates OpenAPI/JSON Schema from typed request models and supports synchronous file/SQLite operations or async I/O where a client supports it. |
| Database | SQLite + SQLAlchemy ORM + Alembic | SQLite with FTS5 enabled where the target build supports it; SQLAlchemy 2.0.x; Alembic 1.20.x line | Embedded, no service account or network; relational history and transactions fit one-user local use. The normalized Vietnamese/n-gram projection is the correctness boundary; FTS5 is an optional accelerator subject to the benchmark. |
| Runtime | Windows process bound to `127.0.0.1`; browser tab | App port chosen at launch; bridge defaults to loopback and must pass the bridge allowlist/authentication checks below | Satisfies the local-first launcher requirement and avoids LAN exposure. |

Official references checked:

- [React versions](https://react.dev/versions) and [React versioning policy](https://react.dev/community/versioning-policy)
- [Vite getting started](https://vite.dev/guide/) and [Vite production build](https://vite.dev/guide/build)
- [FastAPI request bodies and Pydantic validation](https://fastapi.tiangolo.com/tutorial/body/), [OpenAPI metadata](https://fastapi.tiangolo.com/tutorial/metadata/), and [async/sync guidance](https://fastapi.tiangolo.com/async/)
- [Python 3.12 virtual environments](https://docs.python.org/3.12/tutorial/venv.html)
- [SQLAlchemy SQLite dialect](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html) and [session/transaction semantics](https://docs.sqlalchemy.org/en/20/orm/session_basics.html)
- [Alembic migration tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [SQLite FTS5](https://sqlite.org/fts5.html), [SQLite limits](https://www.sqlite.org/limits.html), and [appropriate uses/concurrency](https://www.sqlite.org/whentouse.html)

The official pages support the chosen interfaces and constraints; product policy defaults are fixed by ADR-0004. The n-gram side-index design remains **UNVERIFIED** until measured on the target Windows SQLite build and benchmark fixture.

## 2. Module boundaries

The backend is a modular monolith. Modules communicate through typed service interfaces; only the HTTP adapter is public.

| Module | Owns | May call | Must not own |
|---|---|---|---|
| `platform-ports` | clock, ID, configuration, telemetry and storage interfaces | leaf dependency only | orchestration or business rules |
| `application` | use-case orchestration, transaction boundaries, health aggregation, operation recovery and the shared AI consent/dispatch gate | domain ports and adapters | parsing or UI concerns |
| `markdown-sync` | allowlisted root, parser/serializer, source snapshots and source status | `platform-ports` | card/SRS mutation or AI calls |
| `vocabulary` | word families/forms, bilingual meanings, examples, verification flags, note-day links and search projection | `platform-ports` | filesystem writes, quiz scoring or provider credentials |
| `enrichment` | versioned prompt rendering, local bridge adapter and strict response parsing | `platform-ports`, `vocabulary` ports | direct frontend access to bridge/key |
| `review` | cards, SRS schedule, review events and due queue | `platform-ports`, vocabulary ports | Markdown serialization |
| `assessment` | quiz state, questions, answers, autosave, deterministic scoring and feedback records | `platform-ports`, vocabulary/review ports, enrichment ports | final writing score decisions |
| `dashboard` | read-only due/streak/result projections | vocabulary/review/assessment read ports | mutation of source or history |
| `http` | route mapping, boundary validation, auth/session, error mapping, ETag/idempotency middleware | `application` ports | business rules |

Database tables are an implementation detail behind repositories. Markdown is the user-visible source for vocabulary content; SQLite is the durable source for SRS history, quiz attempts, feedback, sync metadata and indexed projections that cannot be reconstructed from Markdown alone. Only `application` may coordinate a source write and projection update; adapters do not call each other directly.

## 3. API conventions

- Base URL: `http://127.0.0.1:<app-port>`.
- Version prefix: `/api/v1`.
- JSON request/response bodies use UTF-8 and `Content-Type: application/json`.
- Time instants are RFC 3339 UTC strings (`2026-09-29T10:20:30Z`). Note days are `YYYY-MM-DD` in `Asia/Bangkok`.
- IDs are opaque, prefixed ULIDs in transport examples (`wf_01J...`, `attempt_01J...`). Clients must not infer database keys or timestamp semantics from the prefix.
- Response fields use `camelCase`; enum values use `UPPER_SNAKE_CASE`.
- FastAPI's generated OpenAPI document at `/openapi.json` is the machine-readable source. The checked-in contract must be compared with the generated document in CI.

### Common schemas

JSON blocks keyed by a schema name are named fixture maps: the HTTP body is the enclosed object, not the schema-name wrapper. They allow contract tests to select a resource fixture by name. HTTP blocks show actual headers/body; IDs are symbolic aliases. T017 will bind these fixtures to generated DTO validation.

```json
{
  "WordForm": {
    "id": "wf_01J...",
    "familyId": "family_01J...",
    "lemma": "robust",
    "partOfSpeech": "ADJECTIVE",
    "meaningsEn": [{
      "text": "able to work effectively in difficult conditions",
      "language": "en",
      "verificationStatus": "VERIFIED"
    }],
    "meaningsVi": [{
      "text": "vững chắc; đáng tin cậy",
      "language": "vi",
      "verificationStatus": "UNVERIFIED"
    }],
    "examples": [{
      "english": "The study uses a robust design.",
      "vietnamese": "Nghiên cứu sử dụng một thiết kế vững chắc.",
      "verificationStatus": "UNVERIFIED"
    }],
    "ipaUs": "/rəˈbʌst/",
    "cambridgeUrl": "https://dictionary.cambridge.org/dictionary/english/robust",
    "sourceRefs": [{"sourceId": "src_01J...", "noteDate": "2026-09-29"}],
    "card": {"id": "card_01J...", "state": "NEW", "dueAt": null},
    "revision": 4,
    "verificationSummary": "UNVERIFIED",
    "updatedAt": "2026-09-29T10:20:30Z"
  }
}
```

Verification status is per field in the domain model. A separate read-only `verificationSummary` is `VERIFIED` only when all learning/display fields are verified, `MISSING` when one is missing (including nullable IPA/link), and `UNVERIFIED` otherwise. Missing IPA/link still permits save under ADR-0004. The aggregate never replaces field-level provenance.

Request/response DTOs used by the endpoint tables:

```json
{
  "LookupRequest": {"term": "robust"},
  "SaveWordFormsRequest": {"lookupId": "lookup_01J...", "noteDate": "2026-09-29"},
  "SaveExistingSourceRequest": {"lookupId": "lookup_01J...", "noteDate": "2026-09-29", "sourceId": "src_01J...", "sourceRevision": 7},
  "PatchWordFormRequest": {
    "sourceId": "src_01J...",
    "sourceRevision": 7,
    "meaningsEn": [{"text": "...", "verificationStatus": "UNVERIFIED"}],
    "meaningsVi": [{"text": "...", "verificationStatus": "UNVERIFIED"}],
    "examples": [{"english": "...", "vietnamese": "...", "verificationStatus": "UNVERIFIED"}],
    "ipaUs": "/.../",
    "cambridgeUrl": "https://dictionary.cambridge.org/dictionary/english/robust"
  },
  "ReviewRequest": {"rating": "GOOD", "clientOccurredAt": null, "source": "FLASHCARD"},
  "CreateQuizRequest": {
    "noteDate": "2026-09-29",
    "counts": {"mcq": 2, "cloze": 2, "writing": 1}
  },
  "AnswerDraftRequest": {"answer": "robust", "selfScore": null, "draftRevision": 4},
  "WritingAnswerDraftRequest": {"answer": "The study uses a robust design.", "selfScore": 3, "draftRevision": 4},
  "FeedbackRequest": {"rubricVersion": "writing-rubric-v1", "answerRevision": 4}
}
```

```json
{
  "SaveResult": {
    "operationId": "op_01J...",
    "sourceId": "src_01J...",
    "sourceEtag": "\"source-fixture-r1\"",
    "savedForms": [{"id": "wf_01J...", "revision": 1}],
    "noteDate": "2026-09-29",
    "reusedCardIds": [],
    "createdCardIds": ["card_01J..."],
    "canonicalForms": [{
      "id": "wf_01J...", "familyId": "family_01J...", "lemma": "robust", "partOfSpeech": "ADJECTIVE",
      "meaningsEn": [{"text": "able to work effectively in difficult conditions", "language": "en", "verificationStatus": "UNVERIFIED"}],
      "meaningsVi": [{"text": "vững chắc; đáng tin cậy", "language": "vi", "verificationStatus": "UNVERIFIED"}],
      "examples": [{"english": "The study uses a robust design.", "vietnamese": "Nghiên cứu sử dụng một thiết kế vững chắc.", "verificationStatus": "UNVERIFIED"}],
      "ipaUs": null, "cambridgeUrl": null,
      "sourceRefs": [{"sourceId": "src_01J...", "noteDate": "2026-09-29"}],
      "card": {"id": "card_01J...", "state": "NEW", "dueAt": null},
      "revision": 1, "verificationSummary": "MISSING", "updatedAt": "2026-09-29T10:20:30Z"
    }],
    "markdownSync": "COMPLETED",
    "sourceRevision": 1
  },
  "SourceFile": {
    "id": "src_01J...",
    "relativePath": "29-09-2026.md",
    "noteDate": "2026-09-29",
    "status": "VALID",
    "revision": 7,
    "etag": "\"source-fixture-r7\"",
    "lastParsedAt": "2026-09-29T10:20:30Z",
    "errorCode": null
  },
  "SyncRun": {
    "id": "sync_01J...",
    "operationId": "op_01J...",
    "status": "COMPLETED",
    "reason": "MANUAL",
    "startedAt": "2026-09-29T10:20:30Z",
    "finishedAt": "2026-09-29T10:20:31Z",
    "sourcesScanned": 3,
    "sourcesInvalid": 0
  },
  "ReviewEvent": {
    "id": "review_01J...",
    "cardId": "card_01J...",
    "operationId": "op_review_01J...",
    "source": "FLASHCARD",
    "rating": "GOOD",
    "reviewedAt": "2026-09-29T10:20:30Z",
    "nextDueAt": "2026-09-29T17:00:00Z"
  },
  "QuizAttempt": {
    "id": "attempt_01J...",
    "noteDate": "2026-09-29",
    "status": "IN_PROGRESS",
    "questions": [
      {"id": "question_a", "type": "MCQ", "wordFormId": "wf_a", "promptEn": "Which adjective means reliable under difficult conditions?", "options": [{"id": "option_a", "textEn": "robust"}, {"id": "option_b", "textEn": "fragile"}, {"id": "option_c", "textEn": "temporary"}, {"id": "option_d", "textEn": "vague"}]},
      {"id": "question_b", "type": "MCQ", "wordFormId": "wf_b", "promptEn": "Which noun names a predicted explanation to be tested?", "options": [{"id": "option_a", "textEn": "hypothesis"}, {"id": "option_b", "textEn": "sample"}, {"id": "option_c", "textEn": "table"}, {"id": "option_d", "textEn": "margin"}]},
      {"id": "question_c", "type": "CLOZE", "wordFormId": "wf_a", "promptEn": "The design remains ___ under changing conditions.", "answerPolicyVersion": "cloze-answer-v1"},
      {"id": "question_d", "type": "CLOZE", "wordFormId": "wf_c", "promptEn": "The researchers ___ the effect with repeated measurements.", "answerPolicyVersion": "cloze-answer-v1"},
      {"id": "question_e", "type": "WRITING", "wordFormId": "wf_b", "promptEn": "Write one academic sentence using hypothesis.", "targetLemma": "hypothesis", "rubricVersion": "writing-rubric-v1", "rubric": {"descriptors": [{"score": 0, "textVi": "Không có câu có nghĩa hoặc không dùng từ mục tiêu."}, {"score": 1, "textVi": "Có thử dùng từ nhưng sai nghĩa/dạng hoặc lỗi lớn làm khó hiểu."}, {"score": 2, "textVi": "Nhận ra nghĩa định dùng nhưng cần sửa đáng kể dạng từ/ngữ pháp."}, {"score": 3, "textVi": "Đúng nghĩa/dạng, câu rõ; lỗi nhỏ không cản nghĩa."}, {"score": 4, "textVi": "Đúng nghĩa/dạng, đúng ngữ pháp, rõ và tự nhiên trong câu học thuật."}]}}
    ],
    "answers": [],
    "savedAnswerCount": 0,
    "snapshotRevision": 11,
    "submissionRevision": 0,
    "result": null
  },
  "DashboardSummary": {
    "dueCards": 3,
    "streak": {"currentDays": 2, "asOf": "2026-09-29"},
    "flashcardSelfRating": {"count": 5, "averageBucket": "GOOD"},
    "objectiveAccuracy": {"mcq": {"correct": 4, "total": 5}, "cloze": {"correct": 3, "total": 4}},
    "writingSelfScore": {"scored": 2, "average": 3.5}
  }
}
```

`QuizAttempt`, `ReviewEvent.nextDueAt`, rating buckets and writing score scales follow ADR-0004/0005. The review example starts at box 0; GOOD moves to box 1 and the next local midnight. A response must use `null`/`MISSING` for unavailable data, never silently convert “not attempted” to zero accuracy. IDs in examples are symbolic opaque resource references, not values clients construct.

Capabilities are local configuration data; no bridge request is required to read them. Required v1 values:

```json
{
  "Capabilities": {
    "limits": {"requestJsonBytes": 1048576, "sourceMarkdownBytes": 8388608, "bridgeResponseBytes": 4194304, "contentCodePoints": 4096, "collectionItems": 100, "quizTotalMin": 5, "quizTotalMax": 30, "quizPerTypeMax": 20, "pageSizeMax": 100, "termCodePoints": 80},
    "session": {"bootstrapTokenTtlSeconds": 60, "browserSessionTtlSeconds": 28800, "expiresOnBackendRestart": true, "slidingExpiration": false},
    "operationDeadlinesSeconds": {"lookup": 120, "quizGeneration": 60, "writingFeedback": 30},
    "idempotencyRetention": "DATABASE_LIFETIME"
  }
}
```

### Normative resource schemas

The following schemas are the minimum transport shape. ADR-0004/0005 own the v1 bounds/enums and precise field semantics; clients must not invent alternatives. The common examples above illustrate independent resource snapshots, not one transaction.

```text
HealthSummary { status: OK | DEGRADED | NOT_READY, version, storageStatus, bridgeStatus, readiness }
LookupResult {
  lookupId, operationId, term, forms: WordFormDraft[], provider, model, promptVersion,
  verificationSummary, status: PREVIEW | FAILED, createdAt
}
WordFormDraft { formId, lemma, partOfSpeech, meaningsEn[], meaningsVi[], examples[], ipaUs?, cambridgeUrl?, verificationSummary }
WordFormSummary { id, lemma, partOfSpeech, meaningViMatch, verificationSummary, noteDates[], revision, updatedAt }
SaveWordFormsRequest { lookupId, noteDate, sourceId?, sourceRevision? }
SaveResult { operationId, sourceId, sourceEtag, savedForms: {id, revision}[], canonicalForms: WordForm[],
             reusedCardIds[], createdCardIds[], noteDate, markdownSync, sourceRevision }
SourceFile { id, relativePath, noteDate, status: VALID | INVALID | MISSING, revision, etag, lastParsedAt?, errorCode? }
SyncRun { id, operationId, status: QUEUED | RUNNING | COMPLETED | FAILED, reason, sourceRevision?, sourcesScanned, sourcesInvalid, startedAt, finishedAt? }
ReviewCard { cardId, wordFormId, lemma, noteDates[], state, dueAt, queueRevision }
ReviewEvent { id, cardId, source: FLASHCARD | QUIZ, attemptId?, questionId?, rating: AGAIN | HARD | GOOD | EASY, reviewedAt, nextDueAt?, operationId }
Answer { attemptId, questionId, answer, selfScore: integer 0..4 | null, draftRevision, savedAt, state: BLANK | DRAFT | SCORED, operationId }
WordFormMutationResult { wordForm, operationId, sourceRevision }
QuizAttempt { id, noteDate, status: IN_PROGRESS | SUBMITTED, questions: PublicQuestion[], answers: Answer[],
              savedAnswerCount, snapshotRevision, submissionRevision, result: QuizResult | null }
QuizResult { attemptId, status: SUBMITTED, submissionRevision, objectiveScores: ObjectiveScores,
             writingSelfScores: {questionId, selfScore: integer 0..4, rating}[],
             questionResults: QuestionResult[], reviewHandoffs: ReviewHandoff[], submittedAt }
ObjectiveScores { mcq: {total, attempted, correct, accuracy: number | null},
                  cloze: {total, attempted, correct, accuracy: number | null} }
ReviewHandoff { wordFormId, cardId: string | null, rating, reviewEventId: string | null,
                status: APPLIED | SKIPPED_INACTIVE }
Feedback { feedbackId, attemptId, questionId, answerRevision, status: REQUESTED | VALIDATED | FAILED,
           summaryVi?, criteria?, provider, model, promptVersion, errorCategory?, createdAt, updatedAt }
FeedbackPage { data: Feedback[], pagination }
StatusSummary { readiness, appVersion, uptimeSeconds, storageStatus, schemaRevision, sourceCounts,
                bridgeStatus, selectedModelFamily, searchIndexStatus, lastSyncAt, lastSyncDurationMs,
                lastIntegrityCheckAt, sqliteFileSizeBytes, sqliteBusyCount, offlineCapabilities,
                consentState, policyVersion?, localMetrics: { requestErrorRate, p50Ms, p95Ms, p99Ms, sampledAt }, requestId }
Operation { operationId, kind, status: PENDING | SUCCEEDED | FAILED | UNKNOWN,
            resultRef?, errorCategory?, createdAt, updatedAt,
            aiProvenance?: { consentRevision, policyVersion, policyDigest,
              scope, providerLabel, modelId, route, billingMode,
              admissionState: NOT_ADMITTED | ADMITTED | UNKNOWN, admittedAt? } }
```

Quiz questions are discriminated by `type` and include enough public data to render/restore without the client inventing fields. Scoring keys remain backend-only until submission:

```text
MCQQuestion { id, type: MCQ, wordFormId, promptEn, options: {id, textEn}[] }
ClozeQuestion { id, type: CLOZE, wordFormId, promptEn, answerPolicyVersion: cloze-answer-v1 }
WritingQuestion { id, type: WRITING, wordFormId, promptEn, targetLemma,
                  rubricVersion: writing-rubric-v1, rubric: {descriptors: {score: integer 0..4, textVi}[]} }
MCQQuestionResult { questionId, type: MCQ, outcome: CORRECT | INCORRECT | BLANK, isCorrect,
                    rating, correctOptionId, explanationVi }
ClozeQuestionResult { questionId, type: CLOZE, outcome: CORRECT | INCORRECT | BLANK, isCorrect,
                      rating, acceptedAnswers: string[], explanationVi }
WritingQuestionResult { questionId, type: WRITING, outcome: SELF_SCORED, selfScore: integer 0..4, rating }
QuestionResult = MCQQuestionResult | ClozeQuestionResult | WritingQuestionResult
PublicQuestion = MCQQuestion | ClozeQuestion | WritingQuestion
```

Correct answers, scoring keys and `explanationVi` are server-only until terminal submission commit; they are absent from public questions, not merely hidden by UI. `GET /quiz-attempts/{attemptId}` returns the public snapshot, saved `Answer[]`, per-answer draft revisions and aggregate `submissionRevision`, plus `result=null` while IN_PROGRESS or the stored `QuizResult` when SUBMITTED. Creation and reads use the same privacy boundary. Missing snapshot/terminal result returns `409 QUIZ_RESTORE_REQUIRED`, not an empty successful attempt. Both runner/result reads are `Cache-Control: no-store`.

### Bounded operation budgets

The server enforces cancellation-aware hard deadlines, not only client-side timers: lookup 120 seconds, quiz generation 60 seconds, writing feedback 30 seconds, measured monotonically from server request admission through validation, preflight, transport, parsing and completion. At `elapsed >= budget`, no new dispatch/success is admitted; timeout maps to `503 BRIDGE_UNAVAILABLE` with operation reference and redacted TIMEOUT category. Not-admitted/definitely failed work is `FAILED`; an admitted transport with uncertain external outcome is `UNKNOWN`. Cancellation uses the same distinction. A result committed before the deadline but followed by a lost HTTP response remains readable/replayable as success; a reply first arriving after timeout cannot newly acknowledge the timed-out intent as success or cause another dispatch/handoff. No stage resets the budget or starts a background retry. Search's 1-second target and browser end-to-end p95 measurements remain the separate named-fixture performance gates. ADR-0005 C013-10 supplies just-below/exact/above-deadline fixtures.

`ErrorResponse.error.details` is a discriminated union, never both an array and an object:

```text
details: { kind: FIELD_ERRORS, fields: [{field, reason}] }
       | { kind: CONFLICT, expectedRevision, currentRevision, resourceType?, resourceId? }
       | { kind: RETRY, retryAfterSeconds?, operationId?, operationKind? }
       | { kind: RESOURCE, resourceType, resourceId?, recovery: READ | REBOOTSTRAP | RELINK | RESTORE }
       | { kind: RESTORE, attemptId, snapshotRevision?, answerRevision?, guidanceCode }
       | { kind: AI_CONSENT, consentState: NOT_GRANTED | GRANTED | REVOKED | STALE, currentPolicyVersion: string | null }
```

```json
{
  "Page<T>": {
    "data": [],
    "pagination": {
      "nextCursor": null,
      "pageSize": 50,
      "hasMore": false
    },
    "sort": {"by": "updatedAt", "direction": "DESC"}
  }
}
```

```json
{
  "ErrorResponse": {
    "error": {
      "code": "VALIDATION_ERROR",
      "message": "Request validation failed",
      "details": {"kind": "FIELD_ERRORS", "fields": [{"field": "term", "reason": "required"}]},
      "requestId": "req_01J..."
    }
  }
}
```

## 4. Resources and endpoints

### Health and bootstrap

| Resource | Method | Endpoint | Request | Response |
|---|---|---|---|---|
| bootstrap page | `GET` | `/bootstrap#token=<one-time>` | fragment token is never sent in HTTP headers or referrers | static bootstrap page; page immediately clears the URL with `replaceState` |
| bootstrap exchange | `POST` | `/bootstrap/exchange` | `{token}` in body; one-time, valid for less than 60s | `204` plus `HttpOnly; SameSite=Strict` launch-session cookie; replay/expiry → `401 SESSION_INVALID` |
| health | `GET` | `/api/v1/health` | none | `200 HealthSummary`, `Cache-Control: no-store` |
| status summary | `GET` | `/api/v1/status` | none | `200 StatusSummary`, `Cache-Control: no-store`; UI polls every 30s while visible and after mutations |
| capabilities | `GET` | `/api/v1/capabilities` | none | `200 Capabilities` with the required defaults above, or `503 CONFIGURATION_REQUIRED` |
| operation status | `GET` | `/api/v1/operations/{operationId}` | path ID | `200 Operation` |

The bootstrap token is a technical local-session credential, not an app account or password. It is single-use, valid while `now < issuedAt + 60s`, omitted from logs, read only by the trusted bootstrap page, cleared from the URL before the main app loads, and never exposed to application components. The browser session is non-sliding, valid for less than 28,800s (8 hours) and only in the issuing backend process. Refresh/second tabs share its original expiry; shutdown/crash/restart invalidate it. Missing cookie → `401 SESSION_REQUIRED`; expired/invalid cookie → `401 SESSION_INVALID`. Fresh rebootstrap restores acknowledged durable drafts/history/consent through reads, without replaying AI operations. ADR-0005 C013-09 defines exact expiry and replay fixtures.

### AI consent singleton — ADR-0003

These are local-only operations: they must work without internet/bridge, independently of `/capabilities` being unavailable. The same local session and mutation Origin/CSRF checks apply. There is one record for this installation, not a client-supplied user/resource ID. No pagination, filtering or sorting applies; query parameters/unknown body fields are rejected with `422`. Versioning follows `/api/v1`.

| Resource | Method | Endpoint | Request | Response |
|---|---|---|---|---|
| Current choice + disclosure | `GET` | `/api/v1/ai-consent` | No body/query | `200 AiConsentView`, `Cache-Control: no-store`, opaque `ETag` |
| Explicit grant | `PUT` | `/api/v1/ai-consent` | `GrantAiConsent {policyVersion: string}`, required `If-Match` from GET and `Idempotency-Key` | `200 AiConsentMutationResult` after durable commit; does not dispatch AI |
| Withdraw permission | `DELETE` | `/api/v1/ai-consent` | No body/query; required `Idempotency-Key`; no `If-Match` or policy prerequisite | `200 AiConsentMutationResult` after durable revoke, including when policy/bridge unavailable |

```text
AiConsentView {
  state: NOT_GRANTED | GRANTED | REVOKED | STALE,
  revision: integer >= 0,
  acceptedPolicyVersion: string | null,
  acceptedPolicyDigest: string | null,
  lastChoiceAt: RFC3339 UTC | null,
  policy: AiDisclosurePolicy | null,
  canRequestAi: boolean
}
AiDisclosurePolicy {
  version: string,
  digest: string,
  reviewStatus: BLOCKED | READY,
  disclosureText: string,
  dataCategories: [TERM | WORD_FORMS | WRITING_ANSWER],
  recipients: string[],
  retentionStatement: string,
  regionStatement: string,
  costQuotaStatement: string,
  withdrawalStatement: string,
  scopes: [LOOKUP, QUIZ_GENERATION, WRITING_FEEDBACK],
  dispatchRules: [{scope, providerLabel, modelId, route, billingMode}],
  blockedReasons: (MODEL_POLICY | QUOTA_BILLING | PROXY_DATA_POLICY | CLOUD_DATA_POLICY)[]
}
AiConsentEvent { id: opaque, revision, action: GRANTED | REVOKED, policyVersion?, policyDigest?, scopes?, dispatchRules?, occurredAt }
GrantAiConsent { policyVersion: string }
AiConsentMutationResult { operationId: opaque Operation ID, appliedRevision: integer >= 1 }
```

All fields above are required; null is explicit. Policy version is a server-owned opaque identifier matching `[a-z0-9][a-z0-9._-]{0,79}`; `digest` is a server-computed immutable hash of the complete canonical policy, including structured disclosure fields, scopes and dispatch rules. The client can only echo the displayed current version. Policy text/labels are curated local configuration (plain text, not HTML or external response content), never a place for credentials/account emails. A policy may be `null` or `BLOCKED` when operator configuration is missing or invalid; GET still returns `200`, no fabricated approved policy. `READY` requires non-empty/approved `dataCategories`, `recipients`, retention/region/cost-quota/withdrawal statements, all three scopes **exactly once**, a non-empty dispatch rule for each scope, approved provider/model/route/billing values, no blocked reasons and a digest that matches immutable storage; no cloud contact occurs to render a disclosure. A UI fixture must assert each structured field separately; arbitrary free-form disclosure text cannot make an incomplete policy READY.

The v1 READY policy fixture is `policy-v1-antigravity-gemini-flash`: provider label `Antigravity/Google`, model `gemini-3.8-flash-high`, route `primary`, billing mode `configured-account`, and no automatic fallback. It names the three scopes and states that provider retention/region follow the configured provider with no app guarantee. Any paid fallback requires a new policy version/digest and fresh consent; it is not enabled by the v1 fixture.

Initially the durable/virtual record is `NOT_GRANTED`, revision `0`, with null accepted version/digest and last-choice time. Grant stores the current policy version/digest and server time. Revoke clears the active accepted version/digest, stores server time, and increments revision. State `STALE` is derived when a previously granted version or digest no longer equals the current ready policy (including missing/blocked policy); same-version digest mutation is an integrity failure, not a valid in-place update. `canRequestAi` is true only for a current grant + ready policy with all required scopes/rules; it is **not** a guarantee of network, quota or bridge readiness. The ETag covers consent revision and effective policy fingerprint/status; clients treat it as opaque, not as a sequence to construct.

**Validation/concurrency:** grant requires the exact current ETag, version and digest-backed READY policy; missing/malformed headers/body → `422 VALIDATION_ERROR`, outdated ETag → `409 REVISION_CONFLICT`, outdated/unknown version or digest → `409 AI_POLICY_CHANGED`, unavailable or same-version-mutated policy → `503 CONFIGURATION_REQUIRED`. Evaluate these with the update inside a durable database compare-and-set transaction. Each AI dispatch admission atomically records the consent revision/policy digest and selected dispatch rule before releasing the transaction; revoke atomically advances the revision/fence. Whichever transaction commits first defines ordering: an admission committed before revoke may be in flight, while an admission after the revoke fence is denied. This works across processes; the normal launcher still must enforce single-instance/port ownership. DELETE intentionally has no stale-version prerequisite: a new revoke intent fences pending grants even if already revoked and increments revision; retry of that same idempotency key does not increment again. Refuse supplied `If-Match` on DELETE as `422` rather than silently implying conditional revocation.

**Idempotency and lost responses:** after session/Origin/input validation, atomically claim the key with method/path/canonical body and grant precondition fingerprint. Replay a known identical intent before checking today's ETag/policy; it returns its original mutation receipt, never re-applies an old grant. Different fingerprint with same key → `422 IDEMPOTENCY_KEY_REUSED`; running intent → existing `409 IDEMPOTENCY_IN_FLIGHT`. The receipt is historical and deliberately contains no current `GRANTED` flag. Always GET current state after any mutation/replay; receipts and operation status cannot authorize AI. Persist consent update, revision, immutable policy digest/event and successful operation receipt together; write failure → no success. Consent event records are append-only and reference the immutable policy snapshot/digest plus the selected dispatch rules; retain them with related results/history as required by CONSTRAINTS and ADR-0005, including user-managed backup. After an ambiguous response, retry only the same key/fingerprint and/or GET current state, never silently create a new grant intent. Durable intents, receipts and minimal used-key fingerprints remain for the lifetime of the local database in v1; no automatic cleanup turns an old key into a new intent.

Consent examples (synthetic `policy-fixture-1`, not a production provider approval):

```http
GET /api/v1/ai-consent

HTTP/1.1 200 OK
Cache-Control: no-store
ETag: "ac-r0-none"

{"state":"NOT_GRANTED","revision":0,"acceptedPolicyVersion":null,"acceptedPolicyDigest":null,"lastChoiceAt":null,"policy":null,"canRequestAi":false}
```

After a separate approved-policy fixture is loaded and GET returns its ETag:

```http
PUT /api/v1/ai-consent
Content-Type: application/json
If-Match: "ac-r0-policy-fixture-1-ready"
Idempotency-Key: consent-grant-fixture-001

{"policyVersion":"policy-fixture-1"}

HTTP/1.1 200 OK
Cache-Control: no-store

{"operationId":"op_01J...","appliedRevision":1}
```

```http
DELETE /api/v1/ai-consent
Idempotency-Key: <opaque-key>

HTTP/1.1 200 OK
Cache-Control: no-store

{"operationId":"op_01K...","appliedRevision":2}
```

Both mutations use the established session cookie (not reproduced here). GET after withdrawal returns `state: REVOKED`, `revision: 2`, null accepted version, server `lastChoiceAt`, the current policy (or null), and `canRequestAi: false`. A denied AI action uses the common error shape:

```json
{"error":{"code":"AI_CONSENT_REQUIRED","message":"Review AI data sharing before continuing","details":{"kind":"AI_CONSENT","consentState":"REVOKED","currentPolicyVersion":"policy-fixture-1"},"requestId":"req_01J..."}}
```

### Lookup and vocabulary

| Resource | Method | Endpoint | Request schema | Response |
|---|---|---|---|---|
| lookup preview | `POST` | `/api/v1/lookups` | `{term: string}` plus required `Idempotency-Key` | `200 LookupResult` and `Operation` reference |
| word-form collection | `GET` | `/api/v1/word-forms` | query filters below | `200 Page<WordFormSummary>` |
| word form | `GET` | `/api/v1/word-forms/{wordFormId}` | path ID | `200 WordForm` |
| saved word family | `POST` | `/api/v1/word-forms` | New date: `{lookupId, noteDate}` + `If-None-Match: *`; existing date: add `sourceId, sourceRevision` + source `If-Match`; required idempotency key for both | `201 SaveResult` with source identity/revision/ETag and operation receipt |
| word form edit | `PATCH` | `/api/v1/word-forms/{wordFormId}` | allowed editable fields only, `sourceId`, current source revision/`If-Match` and required `Idempotency-Key` | `200 WordFormMutationResult` |
| audio | client-only | `SpeechSynthesis` for the selected lemma | none | No backend/provider request; disabled if no local voice is available |

`POST /lookups` is not queued for later execution, but the bridge call has a durable operation/idempotency record so an unknown timeout cannot silently trigger a second billable request. A failed lookup operation is terminal and has no background retry; the user must explicitly start a new operation.

Lookup request and response:

```http
POST /api/v1/lookups
Content-Type: application/json
Idempotency-Key: lookup-fixture-001

{"term":"robust"}
```

```json
{"LookupResult": {
  "lookupId":"lookup_01J...",
  "operationId":"op_01J...",
  "term":"robust",
  "forms":[{"formId":"draft_01J...","lemma":"robust","partOfSpeech":"ADJECTIVE","meaningsVi":[{"text":"vững chắc; đáng tin cậy","verificationStatus":"UNVERIFIED"}],"meaningsEn":[{"text":"able to work effectively in difficult conditions","verificationStatus":"UNVERIFIED"}],"examples":[{"english":"The study uses a robust design.","vietnamese":"Nghiên cứu sử dụng một thiết kế vững chắc.","verificationStatus":"UNVERIFIED"}],"ipaUs":null,"cambridgeUrl":null,"verificationSummary":"MISSING"}],
  "provider":"Antigravity/Google",
  "model":"gemini-3.8-flash-high",
  "promptVersion":"lookup-v1",
  "verificationSummary":"MISSING",
  "status":"PREVIEW",
  "createdAt":"2026-09-29T10:20:30Z"
}}
```

Save on a clean install/new date (no date source/file exists):

```http
POST /api/v1/word-forms
Idempotency-Key: save-lookup_01J...-2026-09-29
If-None-Match: *
Content-Type: application/json

{"lookupId":"lookup_01J...","noteDate":"2026-09-29"}
```

The backend allocates `sourceId`, creates `29-09-2026.md` under the configured root and commits source revision 1. The client supplies no filesystem path. A source/file appearing before commit yields `409 REVISION_CONFLICT`, preserving its bytes; a source already INVALID/MISSING/ambiguous is not silently repaired or overwritten.

For an existing date, GET `/api/v1/sources?noteDate=2026-09-29` returns the source ID, revision and per-source `etag`. Use all three for the next write:

```http
POST /api/v1/word-forms
Idempotency-Key: <opaque-key>
If-Match: "source-fixture-r7"
Content-Type: application/json

{"lookupId":"lookup_01J...","noteDate":"2026-09-29","sourceId":"src_01J...","sourceRevision":7}
```

Source fields are an all-or-none pair; exactly one of the two precondition variants is required. Mixed/missing preconditions → `422 VALIDATION_ERROR`; ID/date mismatch → `422 CROSS_RESOURCE_MISMATCH`. A stale numeric revision, ETag or actual file hash → `409 REVISION_CONFLICT` before replacement. Existing VALID-source save advances revision 7→8. Source ETags are opaque; shown values are fixture tokens, not a client construction rule.

`SaveResult` returns `operationId`, `sourceId`, `sourceRevision`, `sourceEtag`, all canonical forms, note-day links and reused/created card IDs. An identical key/fingerprint (body plus source preconditions) replays the same `201` receipt before today's precondition check, with no second card/source. Same key/different fingerprint → `422 IDEMPOTENCY_KEY_REUSED`. Preview/form ownership and the current local session are validated. No AI consent is needed to save an existing preview.

### Markdown sources and synchronization

| Resource | Method | Endpoint | Request | Response |
|---|---|---|---|---|
| source files | `GET` | `/api/v1/sources` | `status`, `noteDate`, cursor pagination | `200 Page<SourceFile>` |
| sync run | `POST` | `/api/v1/sync-runs` | `{reason: "STARTUP"|"MANUAL"|"WATCHER"}` plus required `Idempotency-Key` | `202 SyncRun` and `Operation` reference |
| sync run | `GET` | `/api/v1/sync-runs/{syncRunId}` | path ID | `200 SyncRun` |

Existing-source mutations send a source ID, never a filesystem path; only conditional new-date save omits the ID and lets the backend allocate it (ADR-0005 C013-04). The backend resolves paths only under the configured Markdown root, rejects symlinks/junctions/hardlinks that escape it, validates Windows ownership/reparse-point state immediately before replacement, writes a temporary file in the validated directory and atomically replaces the original. A source with `INVALID` or `MISSING` status is read-only until an explicit repair/relink operation is approved. The current design treats a local malicious process racing the filesystem as a residual risk unless handle-based Windows APIs are selected in implementation. An external editor receives no HTTP response: hash/watcher/startup sync advances revisions for changed bytes, and a stale API write receives 409 even if the watcher has not yet refreshed the projection.

### Review/SRS

| Resource | Method | Endpoint | Request | Response |
|---|---|---|---|---|
| review queue | `GET` | `/api/v1/review-queue` | `noteDate`, `dueOnly`, cursor, sort | `200 Page<ReviewCard>` |
| review event | `POST` | `/api/v1/cards/{cardId}/reviews` | `{rating, clientOccurredAt?, source: "FLASHCARD"|"QUIZ", attemptId?, questionId?}` | `201 ReviewEvent` |

The queue includes only due or `NEW` cards when `dueOnly=true`; date filtering follows the spec. The server assigns `reviewedAt`; an optional client timestamp is retained only for bounded offline diagnostics. AGAIN→1; HARD→max(1,current box); GOOD→min(5,current+1); EASY→min(5,current+2). Destination intervals are 1/3/7/14/30 local days. `nextDueAt` is midnight in Bangkok on `localDate(reviewedAt)+interval`, serialized in UTC, not review time plus 24-hour multiples. ADR-0005 C013-02 provides the full transition/boundary oracle.

### Assessments

| Resource | Method | Endpoint | Request | Response |
|---|---|---|---|---|
| quiz attempt | `POST` | `/api/v1/quiz-attempts` | `{noteDate, counts: {mcq, cloze, writing}}`, total 5–30, each 0–20, required `Idempotency-Key` | `201 QuizAttempt` with public questions and null result, or typed validation/dependency error |
| quiz attempt | `GET` | `/api/v1/quiz-attempts/{attemptId}` | path ID | `200 QuizAttempt`; immutable public snapshot plus null IN_PROGRESS result or stored SUBMITTED result; `Cache-Control: no-store` |
| answer draft | `PUT` | `/api/v1/quiz-attempts/{attemptId}/answers/{questionId}` | `{answer, selfScore?, draftRevision}` plus `If-Match` and required `Idempotency-Key` | `200 Answer` with next revision and operation ID |
| submission | `POST` | `/api/v1/quiz-attempts/{attemptId}/submissions` | Current aggregate `{submissionRevision}` plus `Idempotency-Key` | `201 QuizResult`; same intent replays it; fresh terminal intent → `409 ALREADY_SUBMITTED`; in-flight duplicate → `409 IDEMPOTENCY_IN_FLIGHT` |
| AI writing feedback | `POST` | `/api/v1/quiz-questions/{questionId}/feedback` | `{rubricVersion, answerRevision, retryOfOperationId?}` plus a fresh `Idempotency-Key`; answer is read from canonical draft | `201/202 Feedback` or dependency error |
| feedback history | `GET` | `/api/v1/quiz-questions/{questionId}/feedback` | attempt/question filters, cursor pagination | `200 FeedbackPage` |

The attempt state is `IN_PROGRESS → SUBMITTED`, with `FAILED`/`UNKNOWN` operation records for recoverable errors. Question content is an immutable creation snapshot; source revisions do not mutate an in-progress attempt. The user's writing score is stored separately and is never overwritten by AI feedback. Rubric `writing-rubric-v1` has the five descriptors in ADR-0005 C013-03; score 0/1→AGAIN, 2→HARD, 3→GOOD, 4→EASY. Null writing score prevents submission (`422 VALIDATION_ERROR`), never fabricates zero. Blank objective answers retain BLANK outcome and map to AGAIN at terminal scoring; objective selfScore must be null. Blank writing can submit only with an explicit user score 0.

`submissionRevision` starts at 0 and increases atomically once for each fresh answer write alongside its per-question `draftRevision`. The submit request must equal the current aggregate revision; stale → `409 REVISION_CONFLICT` before mutation. Submission is a short local transaction that commits result, SUBMITTED state, grouped SRS handoffs and receipt together. For each form use the weakest rating once (AGAIN < HARD < GOOD < EASY); inactive cards/sources yield `SKIPPED_INACTIVE` with no review event. Answers/score edits after SUBMITTED return `409 ALREADY_SUBMITTED`. GET attempt restores the terminal result after reload/rebootstrap without bridge access. A lost response is reconciled by operation/attempt read or replay of the same key, never a second handoff. Identical receipt replay precedes current revision/terminal checks; changed fingerprint still fails `422 IDEMPOTENCY_KEY_REUSED`.

Negative count fixture (with a valid session and otherwise eligible sources):

```http
POST /api/v1/quiz-attempts
Content-Type: application/json
Idempotency-Key: <opaque-key>

{"noteDate":"2026-09-29","counts":{"mcq":1,"cloze":1,"writing":1}}

HTTP/1.1 422 Unprocessable Entity

{"error":{"code":"VALIDATION_ERROR","message":"Quiz total must be between 5 and 30","details":{"kind":"FIELD_ERRORS","fields":[{"field":"counts","reason":"total_below_minimum"}]},"requestId":"req_01J..."}}
```

Terminal result for the five-question snapshot shown above, after five draft writes (`submissionRevision=5`):

```json
{"QuizResult": {
  "attemptId":"attempt_01J...", "status":"SUBMITTED", "submissionRevision":5,
  "objectiveScores":{"mcq":{"total":2,"attempted":2,"correct":1,"accuracy":0.5},"cloze":{"total":2,"attempted":2,"correct":1,"accuracy":0.5}},
  "writingSelfScores":[{"questionId":"question_e","selfScore":3,"rating":"GOOD"}],
  "questionResults":[
    {"questionId":"question_a","type":"MCQ","outcome":"CORRECT","isCorrect":true,"rating":"GOOD","correctOptionId":"option_a","explanationVi":"Robust diễn tả khả năng hoạt động đáng tin cậy trong điều kiện khó khăn."},
    {"questionId":"question_b","type":"MCQ","outcome":"INCORRECT","isCorrect":false,"rating":"AGAIN","correctOptionId":"option_a","explanationVi":"Hypothesis là giả thuyết cần được kiểm chứng."},
    {"questionId":"question_c","type":"CLOZE","outcome":"INCORRECT","isCorrect":false,"rating":"AGAIN","acceptedAnswers":["robust"],"explanationVi":"Robust phù hợp với thiết kế chịu được điều kiện thay đổi."},
    {"questionId":"question_d","type":"CLOZE","outcome":"CORRECT","isCorrect":true,"rating":"GOOD","acceptedAnswers":["assess"],"explanationVi":"Assess nghĩa là đánh giá tác động bằng phép đo."},
    {"questionId":"question_e","type":"WRITING","outcome":"SELF_SCORED","selfScore":3,"rating":"GOOD"}
  ],
  "reviewHandoffs":[
    {"wordFormId":"wf_a","cardId":"card_a","rating":"AGAIN","reviewEventId":"review_a","status":"APPLIED"},
    {"wordFormId":"wf_b","cardId":"card_b","rating":"AGAIN","reviewEventId":"review_b","status":"APPLIED"},
    {"wordFormId":"wf_c","cardId":"card_c","rating":"GOOD","reviewEventId":"review_c","status":"APPLIED"}
  ],
  "submittedAt":"2026-09-29T10:20:30Z"
}}
```

For this fixture the saved objective answers are `option_a`, `option_b`, `robuts`, `assess`; writing is `The hypothesis was tested with repeated measurements.` with self-score 3. Each QuestionResult matches its public snapshot question. On terminal GET, `QuizAttempt.result` contains this stored result; the public question collection stays unchanged. MCQ/cloze `accuracy=correct/attempted` (null if none attempted), while `total` includes blank questions. AI feedback/history is fetched separately and cannot alter these scores or SRS events.

Feedback response is accepted only after schema validation:

```json
{
  "feedbackId":"feedback_01J...",
  "attemptId":"attempt_01J...",
  "questionId":"question_01J...",
  "status":"VALIDATED",
  "summaryVi":"Câu rõ nghĩa; nên dùng mạo từ chính xác hơn.",
  "criteria":[{"criterion":"GRAMMAR","commentVi":"..."}],
  "provider":"Antigravity/Google",
  "model":"gemini-3.8-flash-high",
  "promptVersion":"writing-feedback-v1",
  "answerRevision":4,
  "createdAt":"2026-09-29T10:20:30Z",
  "updatedAt":"2026-09-29T10:20:30Z"
}
```

If bridge timeout/auth/quota/schema validation fails, the application first persists a `Feedback` record with `status: FAILED`, redacted `errorCategory`, provider/model, prompt version, answer revision and timestamps, then returns the dependency error with the feedback/operation reference. This keeps failure history reloadable and retries auditable.

### Dashboard

| Resource | Method | Endpoint | Request | Response |
|---|---|---|---|---|
| dashboard summary | `GET` | `/api/v1/dashboard` | `from`, `to` optional | `200 DashboardSummary` |

The response keeps flashcard self-rating, objective MCQ/cloze accuracy, writing self-score, due count and streak as separate fields. Formula details and four-week observation window follow ADR-0004; no-attempt accuracy is `null`.

## 5. Validation and error semantics

Validation is enforced at the HTTP boundary with Pydantic models and again for every external bridge response. Internal module calls use typed interfaces and do not duplicate validation.

- `term`: Unicode-normalized, trimmed, 1–80 characters, no control characters.
- `noteDate`: strict `YYYY-MM-DD`, interpreted in `Asia/Bangkok`; source filenames may use the legacy `DD-MM-YYYY.md` form and retain their original relative path.
- Existing-source mutations require `sourceId`, numeric `sourceRevision` and that source's opaque `If-Match`; conditional new-date save instead requires `If-None-Match: *` and omits both source fields. Stale revision/ETag/hash returns `409 REVISION_CONFLICT` before any Markdown replacement. The source journal and new-source absence checks follow ADR-0004/0005.
- Quiz counts are strict integers 0–20 per type with total 5–30. Each requested type count is at most the eligible distinct-form count; `(type, wordFormId)` cannot repeat, while a form may appear across types. Invalid/insufficient counts fail `422 VALIDATION_ERROR` before bridge preflight. `selfScore` is a strict integer 0–4 or null for WRITING until scoring; objective answers permit only null. Missing writing scores prevent terminal submission.
- `pageSize`: integer 1–100. Cursors encode a signed query, sort and source revision; a stale/invalid cursor returns `409 CURSOR_EXPIRED` and the UI restarts from the first page.
- `sortBy`, `filter`, `rating`, source status, quiz type and IDs are allowlisted enums/opaque IDs; unknown values fail with `422`.
- Required v1 caps exposed by `/api/v1/capabilities`: JSON 1 MiB (1,048,576 bytes), Markdown 8 MiB (8,388,608 bytes), bridge response 4 MiB (4,194,304 bytes), content strings 4,096 Unicode code points and general collections 100 items. Tighter term/quiz/page/enum bounds take precedence. Byte caps are actual UTF-8 bytes, including streamed bodies without Content-Length; string bounds use code points after defined field normalization. At the cap an otherwise valid input proceeds; max+1 request/file → `413 PAYLOAD_TOO_LARGE`, client string/array → `422 VALIDATION_ERROR`, bridge byte/string/array → `502 BRIDGE_INVALID_RESPONSE`. No silent truncation; missing/invalid limit configuration → `503 CONFIGURATION_REQUIRED`. ADR-0005 C013-08 records boundary oracles.
- Bridge responses must be valid JSON matching the versioned schema, with bounded string/array lengths. Invalid JSON/schema returns `502 BRIDGE_INVALID_RESPONSE`; it is never rendered as success or stored as feedback.
- Cambridge URLs are stored as data only after scheme/host validation; no arbitrary server-side fetch is permitted. Audio is client-only `SpeechSynthesis`; no audio provider, redirect or server-side media fetch exists in v1.

All failures use the single `ErrorResponse` shape:

| Status | Codes | Meaning |
|---:|---|---|
| 400 | `MALFORMED_JSON`, `INVALID_QUERY` | Syntax or query shape invalid |
| 401 | `SESSION_REQUIRED`, `SESSION_INVALID` | No valid local launch session |
| 403 | `ORIGIN_FORBIDDEN`, `PATH_FORBIDDEN`, `AI_CONSENT_REQUIRED` | Request is outside local permissions or AI sharing has no current grant |
| 404 | `NOT_FOUND`, `SOURCE_MISSING` | Opaque resource ID or configured source does not exist |
| 409 | `REVISION_CONFLICT`, `IDEMPOTENCY_IN_FLIGHT`, `ALREADY_SUBMITTED`, `CURSOR_EXPIRED`, `QUIZ_RESTORE_REQUIRED`, `SOURCE_NOT_WRITABLE`, `AI_POLICY_CHANGED` | Safe retry must wait/re-read or source/attempt/policy state blocks mutation |
| 413 | `PAYLOAD_TOO_LARGE` | Request/file exceeds configured cap |
| 422 | `VALIDATION_ERROR`, `IDEMPOTENCY_KEY_REUSED`, `CROSS_RESOURCE_MISMATCH` | Semantically invalid input |
| 502 | `BRIDGE_INVALID_RESPONSE`, `BRIDGE_AUTH_ERROR` | External bridge failed or returned invalid data |
| 503 | `NETWORK_REQUIRED`, `BRIDGE_UNAVAILABLE`, `STORAGE_BUSY`, `CONFIGURATION_REQUIRED` | Temporary dependency/offline or missing approved configuration |
| 500 | `INTERNAL_ERROR` | Unexpected failure; no stack trace or secrets in body |

## 6. Authentication and authorization

There is no product account, password, role model, or LAN API. The launcher starts the process on loopback and opens a fragment token (`/bootstrap#token=...`); the bootstrap page immediately exchanges it by POST, clears the URL with `history.replaceState`, and receives an ephemeral `HttpOnly`, `SameSite=Strict` cookie. The backend rejects non-loopback binds, cross-origin browser requests, and requests without that cookie. The cookie is an implementation guard, not user authentication. The 60-second single-use bootstrap and non-sliding 8-hour/process-lifetime session rules are in ADR-0005 C013-09; restart/expiry requires fresh rebootstrap and preserves acknowledged durable drafts.

The local session is authorized for the one local user's resources. The owner approved [ADR-0002](adr/0002-antigravity-loopback-trust-boundary.md): Antigravity v4.8.4 with HTTP loopback + required proxy client key, using the Windows host/account as the trust boundary. This replaces the draft per-launch bridge secret/IPC/process-authentication requirement. It does not change browser authentication, authorize LAN/remote access or prove the listener's identity. Provider/model/consent/billing defaults are in ADR-0003/0004; the installed security profile is still an implementation verification gate.

### Bridge adapter contract

The consent/data-policy gate below precedes this preflight for every content-sending use case. Denied consent never triggers its models/health calls as a side effect of the denied action. Independent operator diagnostics contain no study content and never grant consent.

- Exact allowed origin: `http://127.0.0.1:8045`; base path `/v1`. Parse and compare scheme, host and port. Use only this configured loopback origin: reject every alternate host or port and every browser-supplied URL, never follow redirects, and ignore ambient proxy environment settings. HTTP is permitted only on this loopback hop, not to an external plaintext destination.
- Allowed calls: `GET /health` without key, `GET /v1/models`, `POST /v1/chat/completions`. No management, account or `/internal/*` calls. On the two authenticated routes set `Authorization: Bearer <proxy-client-key>` from protected backend configuration, never from inbound browser headers. Do not forward browser cookies/session tokens or application `X-Request-ID`/W3C trace/baggage headers.
- Operator profile: `allow_lan_access=false`, `auth_mode=all_except_health`, rotated nonempty proxy key, distinct nonempty admin password not given to the app. The app never reads Google account stores or the full Antigravity config. The operator records profile verification without recording secrets; the app does not require administration access to verify the profile. `auto`/`off` are unsupported. Other proxy routes have auth exceptions; they are not part of this adapter.
- Before each AI dispatch, with the approved local profile configured, send `GET /v1/models` **without a key** and require `401`. A `200` means mandatory auth is not enforced; stop with `503 CONFIGURATION_REQUIRED` and do not send a key or inference body. Redirects/other unexpected responses also stop, without following a new URL. Then request models with the configured key and require `200` plus a valid models-list shape. A keyed `401`/`403` becomes `502 BRIDGE_AUTH_ERROR` (not an app-session error); unavailable/timeout becomes `503 BRIDGE_UNAVAILABLE`; malformed models output becomes `502 BRIDGE_INVALID_RESPONSE`. Only then may an independently consent/policy-approved AI request proceed. Budgets cover preflight plus inference within the operation deadline; no automatic retry or timeout-budget reset.
- Health `200` is reachability only. Preflight detects ordinary misconfiguration, not a forged listener, malicious reconfiguration or a change between check and dispatch. The accepted local impersonation risk must not be described as prevented. Scope-keying/idempotency for the user operation does not imply exactly-once inference inside Antigravity or an upstream provider.
- Missing key/profile or rejected origin disables AI actions with `503 CONFIGURATION_REQUIRED`, not local study. Use the existing structured error envelope and redacted categories; never expose raw proxy bodies, account identities or secrets. Do not add a browser settings page for secret entry as part of this decision.

### Consent enforcement and withdrawal — ADR-0003

Every new lookup, AI quiz generation and writing-feedback dispatch passes the same application-owned gate, including direct API access and future retry paths. Stored data reads, save of an existing preview, autosave, scoring and local study do not require AI consent. Granting these scopes does not authorize audio or telemetry export, which keep their own policy gates.

1. After normal session/resource/body validation and known idempotent-result reconciliation, require a ready operator-approved policy. Missing/blocked policy → `503 CONFIGURATION_REQUIRED`; otherwise missing/revoked/stale grant → `403 AI_CONSENT_REQUIRED` with `AI_CONSENT` details, before bridge preflight. A known prior response may be replayed locally after revoke, but must not call any provider again. Consent denial before dispatch must not be recorded as successful enrichment or feedback. A terminal `FAILED` feedback retry requires a new idempotency key and `retryOfOperationId` for the same question/answer revision; it is a new consent/policy-checked dispatch, never a replay of the old key.
2. Capture consent revision, policy version/digest and the requested scope. After bridge preflight, use a durable database compare-and-set/fence (not only a process-local coordinator) to recheck current consent/policy and atomically record dispatch admission plus the server-owned selected provider/model/route/billing rule. A READY policy must contain all three scopes and an allowlisted rule for each; selected model/provider/route/fallback must match exactly. Changed consent → deny without sending; changed policy/digest or unapproved route/model → `409 AI_POLICY_CHANGED`/`503 CONFIGURATION_REQUIRED`; a new grant does not revive an older unadmitted operation. Store internal operation provenance (`aiConsentRevision`, `aiPolicyVersion`, `aiPolicyDigest`, `aiScope`, `provider`, `model`, `route`, `billingMode`, `dispatchAdmittedAt`) without learning payloads; it is not permission for restart/retry.
3. A revoke commits the singleton/revision/receipt under this same admission gate before returning success. Keep the gate only for bounded local commit/check/transport admission, never for awaiting the cloud response; do not hold a SQLite transaction across network I/O. Any dispatch admitted after the revoke commit is denied until a valid new grant. A transport request admitted earlier is already in flight: packets may still leave/complete after revoke, and app cannot recall provider copies. Never present withdrawal as deletion or guaranteed upstream cancellation.
4. Backend restart reconstructs the gate from durable state and reconciles operations without resending pending/unknown AI work. Revocation remains local and available when the provider/bridge/policy is unavailable. A storage failure cannot acknowledge revoke; fail closed for AI in the running process when consent cannot be read/written reliably, preserve the last durable state for explicit reconciliation, and show the user that withdrawal was not confirmed.
5. The current consent row is not a complete history, so every grant/revoke appends an immutable `AiConsentEvent` containing revision, action, policy version/digest and the approved scope/dispatch-rule snapshot. Existing operation metadata ties an admitted request to that event/policy digest; referenced immutable definitions/events remain with related results/history. CONSTRAINTS/ADR-0005 retain idempotency intents/receipts/fingerprints for database lifetime and include these records in user-managed backup; no automatic purge is authorized. Startup must not invent a grant when the record/event/policy is missing or corrupt. In-flight output may follow existing schema-validation/persistence rules after withdrawal, without changing scores or launching another AI request.

## 7. Pagination, filtering and sorting

All potentially large lists use opaque cursor pagination. Default `pageSize=50`, maximum `100`. Stable tie-breaking is always by `id` after the requested sort field.

Supported filters:

- word forms: `meaningVi` (indexed from explicit `meaningsVi`), `lemma`, `partOfSpeech`, `verificationStatus`, `noteDate`, `sourceStatus`;
- sources: `noteDate`, `status`;
- review queue: `noteDate`, `dueOnly`, `cardState`;
- dashboard: bounded `from`/`to` date range.

Supported sort fields are endpoint-specific allowlists (`updatedAt`, `lemma`, `dueAt`, `createdAt`, `relevance`). Raw SQL fragments, arbitrary URLs and user IDs are never accepted as sort/filter values. Search uses a normalized exact/folded Vietnamese meaning projection and a versioned n-gram side index for infix matching; FTS5 is an optional candidate accelerator, not the correctness guarantee. The 100,000-form benchmark must verify the selected index on the target Windows SQLite build.

## 8. Idempotency and concurrency

### Source/projection write protocol

The `application` layer owns the only write protocol crossing Markdown and SQLite: read/hash the source; record a `PREPARED` journal row with old/new hash, temp path and operation; write/fsync temp; atomically replace source; commit projection/source revision; mark `COMMITTED`. Startup reconciliation discards unused temp files, rebuilds projection when the new hash matches, marks an ambiguous state `DEGRADED`, blocks destructive writes until repair and never deletes SRS/quiz history. The journal states and repair rule are normative in ADR-0004.

- State-changing or externally billable `POST` endpoints (`lookups`, `word-forms`, reviews, sync runs, quiz attempts, submissions, feedback) require `Idempotency-Key` (1–128 printable ASCII characters). The server atomically claims `(operation, key)`, stores a request hash and terminal response, and rejects the same key with a different body.
- A duplicate while the first request is running returns `409 IDEMPOTENCY_IN_FLIGHT` with an operation ID; it never runs the side effect twice. Unknown outcomes are persisted as `UNKNOWN` and reconciled through `/operations/{operationId}` before retry. Durable intents, terminal receipts and minimal used-key fingerprints remain for the lifetime of the local database in v1, including backup; no automatic TTL/cleanup permits a new side effect under a used key.
- `PUT` answer drafts use `draftRevision` plus `If-Match`; stale writes return `409 REVISION_CONFLICT`, and the response returns the authoritative next revision.
- `PUT` answer drafts and `PATCH` word-form edits also create a durable operation record keyed by `(resource, idempotency key, request hash)`; the response includes `operationId`, so an aborted response can be reconciled without applying the mutation twice.
- Quiz submission and SRS handoff are one synchronous idempotent application operation. Identical key/fingerprint → original 201 result; new intent for a terminal attempt → `409 ALREADY_SUBMITTED`; in-flight duplicate → `409 IDEMPOTENCY_IN_FLIGHT`. None creates a second event. Result/receipt and SRS commit atomically; GET attempt is the terminal read path.
- `PATCH` word-form edits require the selected source's `sourceId`, `sourceRevision` and opaque `If-Match` from its read (not the word form's own revision). A mismatch returns `409 REVISION_CONFLICT`; the client re-reads the source and shows the conflict. Hash is checked before replacement even if a watcher has not run.
- SQLite writes run in short transactions. WAL may improve reader/writer overlap, but SQLite still serializes writers; `STORAGE_BUSY` is retriable with bounded backoff.
- Markdown uses a source revision and atomic replacement; stale `If-Match` always returns `409 REVISION_CONFLICT`. There is no silent last-write-wins or timestamp tie-breaker.

## 9. Versioning

The URL major version is `/api/v1`. Within v1, add fields only, keep enum additions backward-compatible for tolerant readers, and never change the meaning/type of an existing field. A breaking change requires `/api/v2` and a new ADR; deprecation must name the removal release and migration path. The generated OpenAPI document is versioned with the application release.

## 10. Contract examples

Successful search:

```http
GET /api/v1/word-forms?meaningVi=b%E1%BB%81n%20v%E1%BB%AFng&pageSize=20&sortBy=relevance&sortOrder=asc
```

```json
{
  "data": [{"id":"wf_01J...","lemma":"robust","partOfSpeech":"ADJECTIVE","meaningViMatch":"vững chắc; đáng tin cậy","verificationSummary":"UNVERIFIED","noteDates":["2026-09-29"],"revision":4,"updatedAt":"2026-09-29T10:20:30Z"}],
  "pagination":{"nextCursor":null,"pageSize":20,"hasMore":false},
  "sort":{"by":"relevance","direction":"ASC"}
}
```

Revision conflict:

```json
{
  "error": {
    "code": "REVISION_CONFLICT",
    "message": "Source changed since it was read",
    "details": {"kind":"CONFLICT","expectedRevision":1,"currentRevision":2,"resourceType":"SOURCE","resourceId":"src_01J..."},
    "requestId":"req_01J..."
  }
}
```

Offline-dependent operation:

```json
{
  "error": {
    "code":"NETWORK_REQUIRED",
    "message":"This operation needs the configured AI bridge or an available local capability",
    "details":{"kind":"RETRY","operationKind":"LOOKUP","retryAfterSeconds":5},
    "requestId":"req_01J..."
  }
}
```

## 11. Contract test cases

Contract tests must run against the generated OpenAPI schema and a fake bridge; no test may send a real secret. Minimum cases:

1. `AC-03`: lookup success without save creates no card or note-day link.
2. `AC-04`, `AC-11`: save creates one card per form, links multiple dates, and replays an identical idempotency key.
3. `AC-05`, `AC-34`: bridge success/failure and health/models/chat compatibility; failed lookup is not queued.
4. `AC-07`, `AC-31`: Vietnamese substring search, Unicode normalization and external Markdown edit reset the relevant card.
5. `AC-08`, `AC-09`, `AC-10`, `AC-28`: edit serialization, invalid source exclusion, source deletion history retention and stale-revision conflict behavior.
6. `AC-12`, `AC-13`, `AC-21`, `AC-22`: due queue/date filter, review event persistence and streak inputs.
7. `AC-14`–`AC-19`, `AC-30`, `AC-35`: quiz creation, answer autosave, deterministic MCQ/cloze scoring, separate writing score, feedback schema rejection, and SRS handoff.
8. `AC-23`, `AC-29`: local data works without external network; LAN and missing-session requests are rejected.
9. `AC-26`, `AC-33`: outbound payload allowlist and preservation of `UNVERIFIED` labels.
10. Every endpoint: malformed JSON, unknown enum, too-large payload, 404, structured error shape, request ID echo, `Cache-Control: no-store` for status, and no stack/secret leakage.
11. Concurrency: two PATCH requests with the same ETag produce one success and one `409`; two identical POSTs produce one side effect and one replay; an aborted request reconciles through its operation ID.
12. Schema compatibility: generated OpenAPI contains `/api/v1`, every resource schema including discriminated question/answer/feedback/status variants, status codes and examples; a diff flags breaking changes.
13. Search: explicit Vietnamese meaning field, exact/folded normalization, n-gram index, cursor expiry/restart and deterministic 100,000-form benchmark.
14. Security: fragment bootstrap token is removed before navigation, adapter blocks disallowed destinations, supported proxy inference routes reject missing/invalid keys, cross-resource IDs are rejected, and app diagnostic headers are removed before the third-party proxy boundary. Do not assert malicious local listener rejection; see ADR-0002.

### Bridge authentication cases — AC-36

| ID | Fixture/action | Expected result |
|---|---|---|
| BR-AUTH-01 | Synthetic no-key models request; wrong synthetic key on models/chat with fake upstream | No-key returns `401`; wrong key returns `401`/`403`; inference upstream call count remains zero. Test backend mapping of proxy auth errors separately from app-session `401`. |
| BR-AUTH-02 | Approved profile, no-key models `401`, keyed models valid `200`, then valid chat JSON; independent cloud-policy/consent gate satisfied in fixture | One chat dispatch, backend parses schema; key only on authenticated loopback routes. No live provider/credential in automated tests. Installed-profile evidence is separate from the compatibility-only AC-34 smoke fixture. |
| BR-AUTH-03 | No-key models `200` (local-only `auto`/`off` fixture), absent key/profile or malformed configured origin | `503 CONFIGURATION_REQUIRED`; no inference. An unsafe-origin rejection performs no network request at all. Local study remains available. |
| BR-AUTH-04 | LAN/remote/alternate-port URL, URL userinfo, response `3xx`, ambient proxy set | Configuration rejected or dependency error; no redirect, external request or credential sent to another destination. Actual proxy must also be unreachable from a second machine on LAN before release. |
| BR-AUTH-05 | Capture browser, app logs/DB and fake-proxy headers with sentinel values | Key appears only in intended backend→proxy auth header; no Google/admin credential, browser cookie, bootstrap token, `X-Request-ID`, `traceparent`, `tracestate` or `baggage` sent to proxy; local logs/spans retain correlation without payloads. |
| BR-AUTH-06 | Proxy admin password distinct from client key; examine public health with synthetic setup | Client key cannot authorize a protected admin read; public health has no secrets/account data. The app never calls admin/internal routes. Verify proxy profile separately, not via privileged app probes. |
| BR-AUTH-07 | Key revoked, bridge unavailable/timeout or schema-invalid reply; abort/retry/reload | Correct redacted dependency error; preserve local answer/history, use existing operation reconciliation, no background inference replay or credential refresh from Google stores. |
| BR-AUTH-08 | Fully mimicking local listener accepts synthetic key and returns valid JSON | Document that transport checks cannot distinguish it; no test or UI assertion claims authenticated server identity. This demonstrates ADR-0002's accepted residual risk using dummy data only. |
| BR-AUTH-09 | Models list contains an unapproved model/provider, selected route differs from policy, or proxy advertises fallback to another account/model | `503 CONFIGURATION_REQUIRED` or `409 AI_POLICY_CHANGED`; no task payload/inference dispatch. Persist only redacted selected/blocked route category and policy digest. |

### Consent cases — AC-37 through AC-40

| ID | Fixture/action | Expected result |
|---|---|---|
| CONSENT-01 | Ready policy, no grant/revoked/stale grant; call each of lookup, AI quiz generation, writing feedback directly | `403 AI_CONSENT_REQUIRED`, no bridge preflight or inference; no false result/feedback success; local reads/scoring/autosave remain usable. |
| CONSENT-02 | GET ready disclosure → explicit PUT with current ETag/version → reload/restart → explicit AI action | Choice/version/time persist; mutation alone makes zero bridge calls; later action passes both consent and independent bridge/policy gates. |
| CONSENT-03 | Missing/BLOCKED policy, or changed version after rendering | GET still works; no ready policy means grant/AI `503`; stale PUT returns `409`; DELETE still works locally. Existing grant does not approve new policy. |
| CONSENT-04 | Tab A keeps grant form/ETag; tab B revokes; submit A or replay an old successful grant key | New stale grant rejected; old-key replay returns historical receipt without state mutation; GET reports latest revoked state. No inferred grant from receipt. |
| CONSENT-05 | Hold AI after preflight but before admission; commit revoke, then release request | Final gate denies, no inference. Regrant before releasing the old request still fails captured-revision check. |
| CONSENT-06 | Admit request at fake transport barrier, then commit revoke; let in-flight request complete | Result may validate/persist; response/withdrawal copy does not promise recall/cancellation. Every new admission is denied, no follow-up AI; stored words/answers/score/history unchanged. |
| CONSENT-07 | Decline/close dialog, blank checkbox/default form, audio or telemetry action | No implicit grant or delayed AI submit; consent scopes do not authorize audio/export. Local study remains navigable. |
| CONSENT-08 | Crash/write failure/lost response during grant or revoke; replay same key; restart with corrupt/missing consent | No false success, duplicate state change or fresh AI replay; GET/operation reconciliation shows durable result. Running process blocks AI on unreliable consent storage; no record means no permission. |
| CONSENT-09 | Missing session/cross-origin mutation, unknown fields/query, invalid policy ID/precondition, same key changed fingerprint | Session/Origin/schema/idempotency errors with no consent mutation, no raw payload/secret leak. |
| CONSENT-10 | Keyboard-only dialog/status use, loading/blocked/empty/error/stale/unknown mutation fixtures | Focus and visible labels preserved; grant/revoke not optimistic; lost revoke response keeps AI disabled locally until GET/reconciliation; fresh server consent checked before any AI action in another tab. |
| CONSENT-11 | Same policy version is edited in place so its canonical digest changes | Existing grant becomes `STALE`/configuration-invalid; no AI dispatch or silent re-consent. Loader rejects mutable version and requires a new policy version/digest. |
| CONSENT-12 | Two backend processes race revoke vs. AI admission using a shared SQLite fixture | Durable compare-and-set/fence orders commits; dispatch after revoke fence is denied, and only admission committed first may be in flight. No process-local lock alone is accepted as proof. |

## 12. Open decisions before implementation

Consent behavior and v1 policy defaults are accepted in ADR-0003/0004; a consent checkbox cannot override the explicit provider/route/quota/retention constraints.

ADR-0005 and [contract conformance 002](reviews/contract-conformance-002.md) provide the T013 decision/fixture crosswalk. Remaining gates are T017 generated OpenAPI/schema comparison, implementation tests, benchmark evidence and installed bridge profile verification. CONSTRAINTS is established; its thresholds are unchanged. No document probe is application/runtime evidence.

# UI architecture — Vocabulary learning app

**Status:** Planning baseline — implementation freeze follows component/journey verification

**Date:** 29/09/2026 (`Asia/Bangkok`)

**Frontend baseline:** React 19.x + TypeScript + Vite 8.x, static build served by the local FastAPI process.

The UI is a responsive browser tab opened by the Windows launcher. There is no account flow, mobile-native app, or separate desktop window in v1.

[ADR-0005](adr/0005-contract-clarifications.md) and [conformance 002](reviews/contract-conformance-002.md) provide the exact T013 save/source, SRS/rubric, submit/result, size/deadline and session oracles. UI validation and fixtures use those values; the backend remains authoritative.

## 1. Route map

All routes are same-origin and protected by the local launch session established by the launcher. Route state that affects a search or queue is URL state so refresh and back/forward preserve the user's place.

| Route | Screen | Primary job | Network requirement |
|---|---|---|---|
| `/` | Dashboard | See due cards, streak and separated results | Local API only |
| `/lookup` | Lookup/capture | Enter a word, inspect enrichment, save all preview forms | Bridge/network for lookup; local API for save |
| `/search` | Vocabulary search | Search by Vietnamese meaning/lemma and filter source/date | Local API only |
| `/word-forms/:wordFormId` | Word-form detail/edit | Inspect sources, dates, verification labels and edit content | Local API + Markdown sync |
| `/review` | Review queue | Filter by date/due state and study flashcards | Local API only |
| `/quiz/new` | Quiz builder | Select note date and count per question type | Local API; AI generation may need bridge |
| `/quiz/:attemptId` | Quiz runner | Answer, autosave, continue offline | Local API only after quiz exists; AI feedback optional |
| `/quiz/:attemptId/result` | Quiz result | Read terminal QuizAttempt.result and show objective/self scores separately | Local API; feedback may be unavailable offline |
| `/status` | Local status + AI sharing choice | Show health and review/withdraw AI consent | Local API; no bridge needed to read/revoke consent; diagnostics never expose secrets |

If the backend cannot start, the launcher must show a native/static fallback status surface; `/status` is only the in-app status route after the local API is available. Settings, account, backup and LAN routes remain absent. ADR-0003 adds a consent section at `/status#ai-consent`, not a general settings screen or secret-entry form. First-run operator configuration follows ADR-0004 and [the first-run/restore runbook](runbooks/first-run-and-restore.md); the UI never accepts bridge secrets.

## 2. Screen map and component boundaries

### Shared shell

- `AppShell`: landmark structure (`header`, `nav`, `main`), route outlet, skip link and global offline/bridge banner.
- `PrimaryNav`: keyboard-operable links to Dashboard, Lookup, Search, Review and Quiz.
- `StatusBanner`: text + icon + `role="status"`/`role="alert"` for offline, source-error and success messages; never color-only.
- `FocusAnnouncer`: one live region for route and mutation outcomes; does not duplicate visible error text.
- `ErrorBoundary`: prevents one screen failure from blanking the whole app and offers a retry/status link.
- `AiConsentGate`: shared container loading server consent before AI actions; it never treats browser storage as permission. `AiConsentDialog` renders plain-text policy with explicit **Đồng ý**/**Chưa đồng ý**; `AiConsentPanel` on Status displays the latest choice and **Rút lại quyền gửi dữ liệu AI**. A shell link **Quyền gửi dữ liệu AI** makes that panel reachable from every screen.

### Screen composition

| Screen | Container responsibilities | Presentational components |
|---|---|---|
| Dashboard | Fetch summary and recent due queue; refresh after review/quiz mutations | `DueCard`, `StreakSummary`, `LearningResultPanel`, `DashboardSkeleton`, `DashboardEmpty` |
| Lookup | Own term input, request cancellation, lookup error/retry and save mutation | `LookupForm`, `LookupResult`, `WordFamilyGroup`, `VerificationBadge`, `SaveToReviewButton`, `AudioButton` |
| Search | Own URL query, pagination and sort; fetch page | `SearchForm`, `SearchFilters`, `WordFormResultList`, `SearchEmpty`, `SearchError` |
| Detail/edit | Fetch one form, edit draft, ETag conflict handling, sync result | `WordFormHeader`, `MeaningEditor`, `ExampleEditor`, `SourceDateList`, `RevisionConflictDialog` |
| Review | Fetch queue and date filter; own current-card index and rating mutation | `ReviewFilters`, `Flashcard`, `FlashcardBack`, `RatingControl`, `QueueEmpty` |
| Quiz builder | Validate counts/date, create attempt, map dependency errors | `QuizConfigForm`, `QuestionTypeCount`, `QuizCreateError` |
| Quiz runner | Fetch snapshot, autosave answers, restore draft, submit | `QuizProgress`, `QuestionRenderer`, `AnswerField`, `AutosaveStatus`, `SubmitDialog` |
| Quiz result | Fetch result and feedback history, display separated metrics, request writing feedback | `ObjectiveScore`, `WritingSelfScore`, `FeedbackPanel`, `FeedbackHistory`, `SrsUpdateNotice` |
| Status | Poll health/status; independently GET consent and perform grant/revoke with reconciliation | `HealthCheckList`, `SourceHealthTable`, `BridgeStatus`, `StorageStatus`, `ReadinessState`, `AiConsentPanel` |

Components receive typed props and callbacks; they do not call `fetch` directly. Container hooks call the API client and map DTOs to view models. Keep each component focused and prefer composition over configuration.

### Canonical design system (shadcn/ui)

`shadcn/ui is the canonical UI component foundation for the application.`

1. Prefer existing shadcn/ui primitives before building custom interactive controls.
2. Reusable primitives live under:
   `frontend/src/components/ui/`
3. Feature composition belongs in feature modules, e.g.:
   `frontend/src/features/...`
4. Feature modules must not duplicate design-system primitives.
5. Use semantic design tokens for:
   - colors
   - backgrounds
   - borders
   - focus states
   - radius
   - spacing where applicable
6. Do not hard-code arbitrary visual values when a canonical token exists.
7. Prefer composition over modifying a shared primitive for one feature.
8. Accessibility remains an application requirement; do not assume the component library alone satisfies it.
9. Existing keyboard, focus, landmark, live-region, and WCAG requirements remain authoritative.
10. Third-party shadcn registries require explicit owner authorization.
11. When component API or installation behavior may have changed, agents must verify current official documentation rather than relying on memory.
12. Business/API architecture remains independent from the chosen visual component system.

## 3. User flows

### J1 — Open and plan work

1. Launcher starts one FastAPI instance on loopback and opens `/bootstrap#token=...`.
2. The bootstrap page exchanges the fragment token by POST, clears the URL, and focuses the page heading.
3. The app exposes `NOT_READY → SYNCING → READY|DEGRADED`; Dashboard does not present stale/empty data as current while startup sync is unresolved.
4. Dashboard renders local data, due count, streak and three result groups.
5. User navigates to Review or selects a note date for Review/Quiz.

Bootstrap is one-time and expires at 60 seconds. Browser session expires after 8 giờ from issue (non-sliding), or on backend shutdown/crash/restart, whichever occurs first. Same-origin tabs share the cookie and its original expiry; refresh does not extend it. On expiry/restart offer fresh launcher/bootstrap exchange, retain visible input and restore acknowledged durable quiz drafts by read. Rebootstrap does not issue queued AI requests or turn revoked consent back on (ADR-0005 C013-09).

Startup failure has a dedicated status screen; it must not show an empty dashboard as if there were no data.

### J2 — Lookup and save

1. `LookupForm` validates a non-empty English term; Enter or submit invokes `AiConsentGate` before an AI request. If consent is needed, preserve input and show disclosure, never auto-submit the term after granting.
2. `LookupResult` renders each part of speech separately, all meanings/examples, IPA, Cambridge link and field-level `UNVERIFIED`/`MISSING` labels according to ADR-0004.
3. Audio uses local browser `SpeechSynthesis` when a voice is available; otherwise `AudioButton` is disabled with a clear status and no network request.
4. Save remains disabled until a valid preview exists and noteDate is chosen explicitly (default: current Bangkok date; preserve selection across midnight). All returned forms are saved; partial-family selection is not a v1 behavior. Read the chosen date's sources: for an absent source use `{lookupId,noteDate}` with `If-None-Match: *`; for an existing VALID source use its `sourceId`, `sourceRevision` and per-source `etag` as `If-Match`. INVALID/MISSING/ambiguous sources remain read-only.
5. Save mutation uses a stable idempotency key; success receipt supplies backend-allocated sourceId/revision/ETag, date, reused/created cards and completed Markdown sync state. A source appearing after the absence read or any stale precondition opens conflict/re-read while retaining the preview. Identical key replay shows the original receipt, followed by resource refresh; it creates no second card/source. No client path/ID generation is needed for a clean install.
6. Lookup failure offers **Thử lại**, never a background queue.

### J3 — Search and edit

1. Search text and filters live in URL search parameters.
2. Results render loading skeleton → empty state → paginated list without layout jump.
3. Detail screen shows source health and verification state before edit.
4. Save sends the selected sourceId/sourceRevision and that source's `If-Match` (not WordForm.revision); `409` opens a conflict dialog with current and local values. External editor changes arrive through hash/watcher sync and cache invalidation; the editor receives no HTTP error. A stale API draft is preserved for explicit comparison/re-read. No silent last-write-wins.
5. On successful meaning/example edit, UI announces card reset and source revision.

### J4 — Flashcard review

1. Review screen fetches `dueOnly=true` and optional `noteDate`.
2. Front displays English form; **Lật thẻ** reveals Vietnamese meaning/examples.
3. Rating controls are native buttons with labels; no answer text input is required.
4. After rating, the current card is removed/advanced and the mutation is acknowledged.
5. Queue and Dashboard invalidate after the server confirms the event.

Rating labels follow ADR-0005 C013-02: HARD giữ box hiện tại (NEW→1), GOOD+1, EASY+2 capped5, AGAIN→1. The confirmed event's due time uses Bangkok calendar midnight. The client renders the authoritative schedule instead of independently choosing intervals.

### J5 — Quiz

1. Builder validates note date and strict integer counts (each0–20, total5–30, enough distinct source forms per requested type). Positive fixture2/2/1 produces five questions; 1/1/1 is invalid, with no generation dispatch. `AiConsentGate` runs only after valid configuration; granting consent does not automatically create the quiz. Server errors preserve config and focus the invalid fields.
2. Creation shows that selected-date source content may be used even when cards are not due.
3. Runner restores public questions, versioned Answer[] and aggregate/per-question revisions from `GET /api/v1/quiz-attempts/{attemptId}` after reload/rebootstrap. IN_PROGRESS has result=null and contains no correct keys/explanationVi. Rubric `writing-rubric-v1` descriptors0–4 are visible for the explicit writing self-score control.
4. Flush pending 500ms-debounced/blur drafts, wait for durable acknowledgements, GET the current submissionRevision, then POST submission with that revision and one stable key. Writing null blocks submit and is never turned into0; blank writing can submit only with explicit0. Blank objective stays distinct from wrong, and both map AGAIN at terminal scoring. Submit/scoring/result read are local and require no bridge. A stale revision re-reads and preserves the local draft; no automatic overwrite.
5. AI feedback is opt-in per writing answer and also requires current AI consent; clicking feedback invokes `AiConsentGate`. It reads the canonical saved answer revision and cannot modify the self-score. Consent approval does not automatically send the answer.
6. Result route GETs the same attempt and reads its stored SUBMITTED result, including objective keys/Vietnamese explanations only after terminal commit. It separates MCQ/cloze accuracy, flashcard self-rating, writing self-score and AI feedback. If result=null, offer continue-in-runner rather than an empty/0% result. A SUBMITTED runner becomes read-only/result navigation; it cannot edit answers/self-score. Same-key submit replay and fresh-key ALREADY_SUBMITTED both lead to reading the stored result without another SRS event. QUIZ_RESTORE_REQUIRED shows recovery guidance rather than empty data.

### J6 — Offline and source errors

- `OfflineBanner` distinguishes external network/bridge loss from local API stopped, storage busy, and session expiry.
- Existing search, review, dashboard and created quizzes remain usable when the local API is running and the external network is unavailable; the launcher/native fallback handles a stopped backend.
- Lookup, new quiz generation and AI feedback show `NETWORK_REQUIRED` when their approved dependency is unavailable; local SpeechSynthesis shows unavailable only when no browser voice exists and makes no external request. The UI never retries indefinitely.
- Invalid Markdown sources are listed with an error and excluded from review/quiz eligibility; valid sources for the same form remain usable.

## 4. State management and data fetching

### J7 — Consent, change of policy and withdrawal

1. Before an AI action, GET `/api/v1/ai-consent` with no cache. Null/blocked policy shows **Chưa hoàn tất chính sách AI** and no grant control; the user can return to local study. Do not fetch the policy from a cloud URL or infer it from the bridge's model list.
2. When state is NOT_GRANTED/REVOKED/STALE and policy is ready, show its structured `dataCategories`, `recipients`, provider/model/route rules, retention, region, cost/quota, three scopes and withdrawal limitation; free-form text alone is insufficient. No preselected acceptance; closing, Escape or **Chưa đồng ý** sends neither grant nor learning data. Opening a dialog is not consent.
3. Explicit grant PUT uses the shown policy version and GET's ETag plus a stable idempotency key. Disable duplicate submission while pending. After receipt, GET current state; announce saved only when confirmed. Return focus to the initiating action and require a fresh click to send AI content. Keep draft input, not a queued submission.
4. Status always offers the consent panel independently of bridge health or missing policy. Revoke DELETE requires only the local session and idempotency key, not the policy ETag or an online check. Immediately disable further AI actions in that tab while pending, but do not claim withdrawal succeeded until confirmed. On error/unknown response show **Chưa xác nhận rút quyền**, preserve local study and reconcile with GET/the same intent; do not silently issue a new grant.
5. Successful revoke announces **Đã chặn các yêu cầu AI mới** with **Yêu cầu đã gửi có thể vẫn hoàn tất; thao tác này không xóa dữ liệu đã gửi hoặc dữ liệu học trên máy**. Existing in-flight results may arrive; their arrival must not turn consent back on or trigger another AI call.
6. Refetch on window focus, panel entry and before every explicit AI action. Cross-tab cached state is only display state; backend gating decides permission even if another tab has not refreshed. A stale grant/policy conflict closes no drafts: reload disclosure, announce the change and require explicit consent again. Historical idempotency receipts cannot enable AI.

This flow is consent UI, not a new product account or provider admin console; the v1 disclosure fields and route rules come from ADR-0004.

Use the smallest state mechanism that fits the ownership:

| State | Owner | Mechanism |
|---|---|---|
| input text, open card, dialog, pending submit | leaf/container component | React local state and form actions |
| search filters, page cursor, note date | route | `URLSearchParams`; back/forward is meaningful |
| API resources and cache | feature hook | one typed `apiClient` using `fetch`, AbortController, cache timestamps and explicit invalidation |
| current quiz draft | `QuizRunner` + backend | debounced `PUT` answer drafts with `draftRevision`, `If-Match`, flush-on-blur/submit and an operation ID; backend is durable source, local state is optimistic only after a confirmed write |
| global cross-cutting status | `AppShell` | small read-only context for offline/session/announcer; no global business store |
| AI sharing choice/policy | backend; `AiConsentGate`/Status hook for display | no-store GET plus revision/ETag; explicit invalidation after mutations and refetch before AI; no localStorage authorization or optimistic grant |

No Redux/Zustand store is needed in v1. If later profiling shows cache coordination is a bottleneck, adopt a server-state library in a separate ADR rather than adding it pre-emptively.

### Fetching rules

- Read requests have an AbortController tied to route/component lifetime. Mutations are not abandoned without an operation ID; if the response is canceled after commit, the client reconciles through `/api/v1/operations/{operationId}` on remount.
- Read requests use a stable key (`resource + normalized query`) and stale-while-revalidate behavior only for local data.
- Mutations invalidate only affected keys: saving a form invalidates word-form/detail/search/queue/dashboard; a review invalidates card/queue/dashboard; a quiz answer invalidates the attempt only.
- A completed sync run invalidates all source-dependent keys and carries a `sourceRevision`; an in-progress/invalid sync is visible and never silently replaces valid cached content.
- Loading state is per panel, not a full-screen spinner after the first shell render.
- The API error code is preserved in a typed error object; UI copy is localized/mapped, while `requestId` and operation ID are available in a support details disclosure.

## 5. Loading, empty, error and success states

| Area | Loading | Empty | Error | Success |
|---|---|---|---|---|
| Lookup | Skeleton result + `aria-busy` | Prompt asks for an English word | Inline reason + retry; no queued job | Result list with verification labels and enabled save |
| Search | List skeleton preserving column shape | “Không tìm thấy…” with clear-filter action | Retry + request ID | Results, count/page cursor and active filters |
| Detail/edit | Field skeleton | No valid active source → explain, keep history link; edit is read-only until repair/relink is approved | Field-level validation, revision conflict, source missing/invalid | Saved content, revision and reset notice |
| Review | Card skeleton | No due/new cards under filter | Retry; rating remains disabled | Rating recorded and next-card announcement |
| Quiz builder | Disable submit and show progress | Date has no eligible forms | Validation/dependency/configuration message, preserve config | Attempt ID and start link |
| Quiz runner | Restore question/answer state and revision | Unanswered is a valid state, not 0% | Local save error blocks false “saved” label; session expiry offers rebootstrap; cloud feedback error does not block quiz | “Đã lưu” timestamp/operation state and completion result |
| Dashboard | Panel skeletons | No history; due count `0` is valid | Per-panel error, retry | Due/streak/results shown separately |
| Offline | Persistent but dismissible banner with fault category | No local data explains how to create it | Network-required, API-stopped, storage-busy and session-expired states have distinct recovery actions | Local flows remain available when the backend is healthy |
| AI consent | Busy label while reading/saving; local study stays available | No choice → explicit disclosure; no policy → explain unavailable, no grant | Stale policy/revision, write failure or unknown revoke outcome; preserve input and reconcile, no implicit retry of AI | Show confirmed current choice; revoke success explains in-flight/data-recall limitation |

Visible success is shown only after the backend confirms the mutation. Toasts are supplemental; important state is also present in the page.

## 6. Responsive behavior

Responsive guidance (not a new product acceptance gate) for the Windows browser tab:

- `320px`: one column, no horizontal scrolling, stacked form actions, card content full width.
- `768px`: two-column search/detail where content remains readable; quiz controls may move below the question.
- `1024px`: persistent primary navigation and two-pane review/detail layouts.
- `1440px`: constrain reading measure; do not stretch prose across the full viewport.

Use a shared spacing scale and semantic color tokens. Do not rely on gradients, color-only states, oversized card grids or arbitrary pixel values. Test long Vietnamese text, missing IPA, multiple meanings and error copy at representative Windows widths. Zoom/contrast acceptance follows WCAG 2.2 AA and ADR-0004.

## 7. Keyboard navigation and accessibility

The target is keyboard-complete, semantic UI aligned with the spec. Full screen-reader support is not claimed in v1, but the implementation must avoid known barriers.

- Native `button`, `a`, `input`, `select`, `textarea` and `dialog` elements before ARIA roles.
- Skip link to `main`; one `h1` per screen; headings are not skipped.
- Every input has a visible `<label>` and stable `id`; errors use `aria-invalid` and `aria-describedby`.
- Route changes move focus to the screen `h1`; dialogs focus the first actionable control and restore focus on close.
- Flashcard flip is a button activated by Enter/Space; rating buttons expose text and state, not only icons.
- Async changes use a polite live region for success and assertive alerts for blocking errors.
- Focus indicators are always visible; target WCAG 2.2 AA, 4.5:1 normal text, 3:1 large text/UI/focus and no obscured focus at 200% zoom.
- Verification, source validity and offline state use text/icon plus color; removing color must not remove meaning.
- Audio buttons include the target lemma in their accessible name and state when no local voice is available.
- Tables and lists have headers/roles that remain understandable when CSS is disabled.
- Consent dialog has an accessible title/description, trapped keyboard focus and Escape-as-decline; opening focus lands on the disclosure heading, not **Đồng ý**. Tab reaches both choices and visible focus is preserved; return focus to the initiating control on close. On narrow widths, disclosure scrolls without hiding actions. Revoke is a labelled native button reachable from the shell/Status, not an icon or hover-only action.

Sci-Link is a visual reference; WCAG 2.2 AA is the test target, not a conformance claim before manual verification.

## 8. Form validation

Frontend validation improves feedback but is never the security boundary. The backend contract is authoritative.

- Lookup: trimmed Unicode term, required, max length, no control characters.
- Save: valid preview/date; conditional absence for a new date or source ID/revision/ETag for an existing VALID source; all preview forms are saved together.
- Search: empty query is allowed only for the explicit browse state; filters are allowlisted.
- Edit: field lengths and URL syntax; preserve `UNVERIFIED`/`MISSING` status rather than silently upgrading.
- Quiz builder: date required; strict integer counts0–20/type, total5–30 and sufficient distinct source forms/type. 1/1/1 is invalid. Server returns field errors for invalid config without inference.
- Quiz answers: preserve blank vs. incorrect; writing self-score is explicit0–4 using `writing-rubric-v1` descriptors, with null pending blocking submit. AI never overwrites it; terminal answers/scores are read-only.
- Learning content strings ≤4096 Unicode code points, general collections≤100; stricter term/quiz bounds take precedence. Read capabilities' 1/8/4 MiB and 120/60/30s operation defaults; preserve input on rejection, never truncate it silently or reset a request budget.

Validation errors render next to the field and in a summary at submit time. The first invalid field receives focus; values are preserved after error.

## 9. API integration and offline boundary

The UI imports generated TypeScript DTOs from the FastAPI OpenAPI document. It must not know the bridge URL, provider key, filesystem path or SQL schema.

`apiClient` maps every `ErrorResponse.code` to a deterministic UI state:

- `NETWORK_REQUIRED`, `BRIDGE_UNAVAILABLE`, `BRIDGE_AUTH_ERROR`, `BRIDGE_INVALID_RESPONSE`: dependency banner, bounded retry and preserved local answer/score.
- `SESSION_REQUIRED`, `SESSION_INVALID`: attempt local rebootstrap; if it fails, show launcher/status recovery without losing local draft.
- `MALFORMED_JSON`, `INVALID_QUERY`, `VALIDATION_ERROR`, `PAYLOAD_TOO_LARGE`: field/form summary and preserved input; `CROSS_RESOURCE_MISMATCH` identifies stale/mismatched preview/attempt resources.
- `ORIGIN_FORBIDDEN`, `PATH_FORBIDDEN`: blocking security/status state; no retry loop.
- `AI_CONSENT_REQUIRED`: preserve input and read current consent/policy; offer explicit disclosure only if policy is ready, never automatic retry.
- `AI_POLICY_CHANGED`: refetch disclosure and ETag; require explicit re-consent before a new AI action.
- `REVISION_CONFLICT`, `IDEMPOTENCY_IN_FLIGHT`, `IDEMPOTENCY_KEY_REUSED`, `ALREADY_SUBMITTED`: conflict/wait/reconcile dialog using operation ID and current resource.
- `CURSOR_EXPIRED`: restart pagination at the first page with a non-blocking notice.
- `QUIZ_RESTORE_REQUIRED`: preserve the attempt ID and show recovery guidance; never render an empty quiz.
- `NOT_FOUND`, `SOURCE_NOT_WRITABLE`, `SOURCE_MISSING`: resource/source state with history/relink guidance.
- `STORAGE_BUSY`: retry with bounded client backoff and visible “đang bận”.
- `INTERNAL_ERROR`, `CONFIGURATION_REQUIRED`: generic message plus request ID; detailed stack remains server-only.

AI disclosure and persistent choice follow ADR-0003/J7 above. GET/PUT/DELETE `/api/v1/ai-consent` use existing local session guards. Consent receipts carry `operationId`/`appliedRevision`, not current permission; GET is authoritative for display and the server checks again at dispatch. `canRequestAi` excludes provider/network availability. Grant cannot be offered for incomplete cloud policy; do not tell the user consent overrides quota/billing/data-policy blockers. History, SRS and unrelated vocabulary remain local; trace headers stop at app→proxy.

## 10. Component and journey test strategy

Official references: [Vitest](https://vitest.dev/guide/index.html), [React Testing Library](https://testing-library.com/docs/react-testing-library/intro/), and [Playwright browser/test docs](https://playwright.dev/docs/browsers).

### Component tests (Vitest + React Testing Library)

- Render each component by user-visible role/label, not implementation details.
- Cover loading/empty/error/success for each table above.
- Verify keyboard activation, focus movement, live-region announcements and color-independent labels.
- Verify form boundaries, `aria-invalid`, error summary focus and preserving entered values.
- Verify verification badges, missing fields, source-error treatment, and no false success.
- Mock `apiClient` at the module boundary with contract-shaped fixtures; never mock React internals.
- Cover `AiConsentDialog`/`AiConsentPanel` NOT_GRANTED/GRANTED/REVOKED/STALE and null/BLOCKED policy; no initial grant, no automatic original-action submission, keyboard decline/accept/revoke, focus restoration and visible in-flight limitation.

### Integration tests

- Use a fake FastAPI HTTP server or contract mock generated from OpenAPI.
- Assert query invalidation and optimistic rollback on failed review/save/autosave; test abort-after-commit reconciliation and session rebootstrap.
- Assert ETag conflict dialog and idempotent replay behavior.
- Assert conditional new-date save without a client sourceId/path, existing-source preconditions, hash-before-watcher conflict and retained preview. Assert min5/max30/per-type/source counts with 2/2/1 and rejected1/1/1.
- Assert public questions omit keys/explanationVi before submit, rubric is visible, null writing score blocks submit, aggregate revision follows acknowledged autosave, terminal GET/replay restores result and inactive-source handoff is skipped. A second fresh submit or answer edit cannot create another event or alter terminal scores.
- Assert one-time bootstrap59.999s/60s, non-sliding session just-before/exact8h, shared second-tab expiry and restart invalidation. Fresh rebootstrap restores acknowledged drafts and revoked consent without inference replay.
- Assert feedback history reloads `REQUESTED`, `VALIDATED` and `FAILED` records. A terminal failed retry uses a fresh idempotency key plus `retryOfOperationId`, preserves the same canonical answer revision, and is rechecked against current consent/policy; reusing the failed key replays the failure and does not dispatch.
- Assert fault matrix: local API healthy + external network down, bridge down, API stopped, storage busy, and expired session. Existing local data works only in healthy-local-API cases; bridge/new quiz/feedback report network/dependency required, while local SpeechSynthesis remains available or clearly unavailable without a network request.
- Run CONSENT-01–12: two-tab stale grant, same-version digest mutation, policy switch/structured-field omission, two-process fence, lost mutation response, bridge-down withdrawal and late in-flight response. Count API/bridge calls to prove dialog dismiss/grant alone sends no learning data; simulate revoke errors and require no false success.

### Browser journeys (Playwright)

Run on Chromium and Microsoft Edge at 320, 768, 1024 and 1440 widths. Minimum journeys map to `AC-01` through `AC-40`: startup, lookup/save, search/edit, invalid source, duplicate date, review, quiz autosave/resume, offline use, keyboard-only navigation, configured/disabled audio state, feedback schema/retry failure and consent/revocation. Use deterministic fixtures and a fake bridge; run a separate opt-in smoke test for the real local bridge. No live provider is needed for consent tests.

Before implementation, pin Playwright/browser versions and document the Windows browser channel. Do not use automated accessibility checks as a substitute for keyboard/manual review; add axe-style checks only as a supplementary gate after the final UI is available.

## 11. Review gates

UI contracts use ADR-0004/0005 for SRS/rubric, counts/snapshot/terminal disclosure/read, conditional save, local audio, streak, launcher/autosave/session, WCAG2.2AA target and dashboard formulas. CONSTRAINTS is established. Remaining work is component/journey/runtime verification and T017 generated DTO checks; T013 document conformance is not a browser/accessibility pass.

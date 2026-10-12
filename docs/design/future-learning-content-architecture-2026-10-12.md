# English Web — future-ready learning content architecture (DESIGN ONLY)

**Recorded:** 2026-10-12
**Origin:** Owner requirement to expand beyond vocabulary into books, in-book exercises, per-book vocabulary, study progress, skills (Writing, Speaking, Listening, Reading), IELTS band and learner proficiency.
**State:** Proposed future architecture; not approved for code execution or the v1 release.
**Baseline:** Existing local-first FastAPI modular monolith, SQLite/Alembic, React/Vite, authenticated loopback API, Markdown canonical vocabulary with durable SQLite review/quiz history.

## 1. Product direction

English Web should become a **local-first modular learning platform** rather than a single-purpose vocabulary application. A first-class learning resource may be a BOOK, COURSE, ARTICLE, WORKSHEET, PERSONAL_NOTE or future format. The first requested expansion is BOOK; no need to implement every content type initially.

Target journey:
Library → Book → Chapters → Units/Lessons → Exercises → Attempts/Feedback → Progress.
A user can link previously saved vocabulary to a book, unit, exercise or passage, then review the canonical vocabulary via existing Flashcard/SRS without duplicating it.

**Do not conflate:** source material, vocabulary identity, source provenance, learning activity, recorded progress, and exam difficulty.
Book is a content resource; Review/Quiz is learning activity; streak and progress are derived observations, not content fields.

## 2. Existing source contract and migration constraints

Source-confirmed:
- `backend/migrations/versions/0004_vocabulary.py` defines `word_families`, `word_forms`, `source_files`, `word_form_sources` and `lookup_previews`. `word_form_sources` links a canonical form to date-stamped Markdown files; no book/unit identity in this schema.
- `backend/migrations/versions/0008_quiz.py` `quiz_attempts` currently requires `note_date` and stores immutable questions and results tied to source vocabulary. `quiz_questions.word_form_id` is a historical reference. This is not a generic publisher-book exercise schema.
- `backend/app/application/create_quiz.py` `CreateQuizRequest` accepts `note_date` and question-type counts; hardwiring book exercises into this request would be a breaking change.
- `docs/adr/0001-architecture.md` states that Markdown is canonical for vocabulary content and SQLite is the durable source for review, quiz, answers and feedback. Preserve this distinction.
- `docs/ui-architecture.md` describes the approved v1 routes. No Book/Library route is approved or implemented in the current v1.

Therefore extend **additively** by new domains and FK/join tables. Do not rewrite, repurpose or delete legacy Markdown, existing source_file IDs, historical quiz snapshots, review events or consent evidence. Do not silently transform book exercises into AI-generated vocabulary quizzes.

## 3. Recommended bounded modules — modular monolith, not microservices

| Module | Owns | Explicitly does not own |
|---|---|---|
| `catalog` | Resource identity, title, author/publisher metadata, book editions, classifications | Card scheduling, learning events, generated AI content |
| `content` | Book hierarchy, chapters/units/lessons, localized text/media references, provenance and content version | Student completion |
| `exercises` | Exercise definitions, type-specific payload/validation, authorized answer keys, fixed version on attempt | Existing T034 generated-quiz mutation semantics |
| `vocabulary` (existing) | Canonical word identity, Markdown sync, verification/source references | Book progress percentage |
| `resource-links` | Many-to-many vocabulary ↔ book/unit/exercise occurrence and exact location | Cloning canonical word form records |
| `learning-progress` | Enrollment/book state, activity/completion facts, projections by version | Material text, answer key |
| `review / assessment` (existing) | SRS/card events, existing quiz immutable attempts and feedback | Generic book-definition storage |
| `platform` (existing) | Local file safety, app settings, sessions, telemetry, migrations and allowed AI bridge | Product-specific taxonomy rendering |

Namespaces are proposed boundaries, not directories to create now.

### Versioned content model — conceptual only

- `learning_resources(id, kind, title, language, created_at, updated_at)` — stable resource identity and discriminated type.
- `book_editions(id, resource_id, edition_label, isbn_optional, author, publisher, content_revision, availability_status)` — never use title as identity; separate revisions/editions so re-import does not invalidate progress.
- `content_units(id, edition_id, parent_unit_id?, unit_kind, ordinal, title, content_revision)` — hierarchical chapter/lesson/section; avoid one database column for every possible hierarchy level.
- `learning_assets(id, unit_id?, asset_kind, validated_local_reference, digest, rights_metadata)` — user-managed private path/reference; media data does not belong in API JSON, telemetry, or Markdown.
- `exercise_definitions(id, unit_id, exercise_kind, definition_revision, payload, evaluation_policy)` — versioned source exercise; type-specific schema, never one opaque unvalidated JSON bucket.
- `exercise_attempts(id, definition_id, definition_revision, attempt_snapshot, status, started_at, finished_at, result?)` — durable attempt and replay/idempotency; do not mutate old exercise content when book changes.
- `resource_word_occurrences(resource_id, edition_id?, unit_id?, exercise_id?, word_form_id, location_ref?, context?, occurrence_key)` — linked occurrence with FK/referential rules. Multiple books/units may point to the same canonical `word_forms.id`. Location may encode page/paragraph/item but must be versioned and validated.
- `learning_enrollments(id, resource_id, edition_id?, started_at, state)` — current single-user enrollment; do not invent logins or multiplayer.
- `progress_events(id, enrollment_id, unit_id?, exercise_attempt_id?, event_kind, occurred_at, content_revision, idempotency_key)` — append-only completion/read/attempt/correction facts with provenance.
- `progress_summary` — derived/materialized status keyed by enrollment + content revision; rebuildable from history, never the only source of truth.

This is a model proposal, **not a final migration/schema**. Actual constraints (FK, unique occurrence identity, optionality, cascade restrictions, retention, indexes, version compatibility) require a separate ADR and tested migration when development is authorized.

### Separation of tags, exam framework and measured proficiency

Do not store every attribute as an undifferentiated free-form string array and do not store `IELTS Band 6.5` as the same type as `B2`.

- `skills`: controlled multi-select vocabulary `READING, LISTENING, WRITING, SPEAKING`, extensible by a versioned taxonomy.
- `assessment_framework`: `IELTS`, `TOEIC`, `CEFR`, `GENERAL_ENGLISH`, etc. Qualifiers need a clear framework and scale.
- `target_proficiency`: typed scale/value or range, e.g. `{ framework:"IELTS", bandMin:6.0, bandMax:7.0 }` or `{ framework:"CEFR", levels:["B1","B2"] }`, as different, independently validated classifications.
- `tags`: optional free-form topics, publishers, series, user collections; normalized catalog terms with dedicated resource↔tag many-to-many join.
- A book may have *many* skills, multiple target levels/framework associations and multiple topic tags. A single type should not imply a skill or a numeric level.
- Tag filtering should support intersection/union policy defined by UX (e.g., `skill=Writing AND framework=IELTS AND targetBand includes 6.5`); be explicit about book-target band vs actual user-achieved score.
- Progress in a book does **not** automatically certify an IELTS band or CEFR level.

Example metadata — illustrative only:

```json
{
  "resourceId": "book_sample",
  "kind": "BOOK",
  "title": "IELTS Writing Practice — sample",
  "edition": "2026",
  "skills": ["WRITING", "READING"],
  "targets": [
    { "framework": "IELTS", "minBand": 6.0, "maxBand": 7.0 },
    { "framework": "CEFR", "levels": ["B2"] }
  ],
  "tags": ["Academic", "Practice"],
  "progress": { "status": "IN_PROGRESS", "requiredUnitsCompleted": 8, "requiredUnits": 20 }
}
```

No automatic CEFR↔IELTS band conversion is implied by those independent illustrative labels.

## 4. Progress semantics — avoid fake completion

- `NOT_STARTED` / `IN_PROGRESS` / `COMPLETED` (and optional `PAUSED`/`ARCHIVED` when defined) are explicit states.
- Viewing a page, opening a PDF or entering a lesson must not automatically count as learned/mastered.
- Treat **reading position** (last-opened unit, page/anchor) separately from **unit completion** (manual check or authorized exercise criteria).
- Book completion = defined required-unit completion under a versioned completion policy; calculate percentage only when the denominator is known. Example: 8/20 = 40%, not an estimated learning mastery score.
- Exercise completion and performance are separate: a submitted attempt is not necessarily a passed attempt; self-rating vs objective grading vs optional advisory AI must remain distinct.
- Retain historical progress and exercise snapshots when a book edition changes or source material disappears. An updated edition may need an explicit `NEEDS_REVIEW` state rather than silently treating progress as current.
- Do not merge existing vocabulary streak/SRS/due-card metrics into book completion counts. Dashboard may display separate widgets based on independent measures.

## 5. Frontend shell and UI extension seams — design now, implement later

Build the design foundation around **feature-group navigation**, not a hardcoded assumption that there will always be exactly six destinations.

Recommended future navigation:

```text
HỌC TẬP
  Tổng quan
  Thư viện (future; hidden until enabled)
    Sách của tôi
    Bộ sưu tập / giáo trình
  Từ vựng
    Tra cứu
    Kho từ
    Ôn tập
  Luyện tập
    Tạo bài kiểm tra
    Bài tập theo sách (future; hidden until enabled)
  Tiến độ
    Tổng quan học tập
    Tiến độ sách (future; hidden until enabled)
HỆ THỐNG
  Trạng thái
  Quyền gửi dữ liệu AI (within Status)
```

The current v1 routes must keep working, including `/`, `/lookup`, `/search`, `/word-forms/:id`, `/review`, `/quiz/new` and `/status`. Reserve prospective `/library`, `/library/books/:bookId`, `/library/books/:bookId/units/:unitId`, `/exercises/:exerciseId` and `/progress/books` **only as future design examples**: do not add blank route screens, navigate to 404s, or create unsanctioned features now.

Use a typed static navigation registry / feature descriptor when implementation is approved: `featureId`, `section`, `label`, `route`, `capabilities`, `enabled` and display order. This is a small explicit routing seam, **not** a dynamic plugin loader or remote microfrontend infrastructure.

Reusable screen design patterns:
- `ResourceHeader`: title, subtitle, skill chips, framework/proficiency labels, edition and source license status where appropriate.
- `ResourceExplorer`: hierarchical contents, search/filter/sort and accessible keyboard navigation.
- `ContentReader`: content and chapter outline, reading position (future only; do not assume PDF renderer).
- `ExerciseSurface`: type-specific renderer, progress, recoverable autosave and immutable result.
- `ProgressSummary`: numerator/denominator and explicit source of completion, separate from grade.
- `VocabularyLinks`: contextual occurrence links to canonical word detail and existing SRS actions.

Do not rewrite existing AppShell or interfaces in this research PR. Avoid forcing all future screens into a fixed dashboard card pattern; resource reader and focus quiz need distinct content layouts under shared tokens/shell.

## 6. Suggested incremental implementation phases (not authorized)

| Phase | Scope | Preconditions/why |
|---|---|---|
| F0: Current redesign | Shell information architecture and reusable primitives tolerate feature groups and future library; keep routes unchanged | Owner sign-off on visual direction |
| F1: Library metadata | Add book catalog/edition, cover metadata, typed skill/level tags, manually entered book; list/detail navigation | Schema/ADR, privacy/license and migration acceptance |
| F2: Contents and in-book exercises | Book units, edition-specific exercises, secure type-specific attempt snapshots and scoring; input/import contract | Define supported formats, owner-owned content and answer rights |
| F3: Contextual vocabulary and progress | Link word_form IDs to book/unit/exercise, capture occurrences, user enrollment, append-only progress, per-book dashboard | Preserve Markdown source and legacy SRS/quiz evidence |
| F4: Advanced content | Additional resource kinds, local search across materials, richer practice analytics, optional AI assistance with explicit consent | Real usage evidence and cost/performance/security budget |

Avoid building F1–F4 speculatively now. F0 is largely an **information architecture/design decision**. The eventual F1–F4 implementation should be vertical slices with additive Alembic migrations, typed endpoints, migrations on copies and release verification.

## 7. Risks and non-negotiable boundaries

1. **Content rights**: Store or display full publisher books/exercises only when the user has rights or another legally permitted basis; metadata/links and user-authored notes may be separate. Do not embed third-party copyrighted exercise corpora in app releases.
2. **File safety**: A future PDF/EPUB or cover asset import needs explicit allowlisted local file roots, size limits, MIME/content validation, path traversal/reparse guards, atomic operations and no secret-bearing metadata. Never reuse the Markdown source-directory safety checks without reviewing format-specific threats.
3. **No surprise cloud use**: AI treatment of book excerpts, screenshots or exercise answers is a **new scope** needing disclosure, minimization, policy version and consent; existing vocabulary consent is not blanket authorization for entire-book uploads.
4. **Data safety**: Do not delete or rebuild existing SQLite history, existing canonical word forms, review schedules, consent audit history or quiz snapshots in an attempt to model books.
5. **Search/performance**: Catalog search and book-content indexing are separate from the current word-form 100k search target. Bound result pagination, bulk import and on-disk storage without loading a large book into one React component or API response.
6. **Single-user/offline**: No need for account login, microservices, remote vector database or a full plugin marketplace now.
7. **Explicit progress evidence**: No auto-graduation, guessed band score, fake completed unit, or infinite recomputation of previously acknowledged attempts.

## 8. Design plan amendments and owner decisions

Update the existing UI redesign program to require:
- `UXR-02` Shell exploration includes a future extensible navigation grouping and a disabled/hidden-until-shipped Library slot, not a permanent six-item hardcode; preserve current deep routes.
- `UXR-09` Dashboard components permit future Library/Book progress modules but keep existing due/streak/quiz measures honest.
- `UXR-03/04` Word-detail and save designs have an optional **source occurrence/provenance extension point** for future book/unit links; no schema changes now.
- `UXR-06/07` Quiz UI can display an eventual `origin` label (Daily Vocabulary vs Book Exercise) while respecting distinct persistence/assessment definitions.
- `UXR-10` Design review adds scalability scenarios: 0 books; 100 books; 10+ tags; one book with 30 units and mixed skills; one word in 3 books; no local assets; missing version; lost source; offline; keyboard and mobile.
- Book/library designs require a separate scoped ADR and explicit owner sign-off before task IDs/worktrees or code.

Owner decisions required before F1: first input type (manual metadata only or existing PDF/EPUB/Markdown?), whether in-app ebook reading is needed or only tracking, exact book exercise formats and marking rules, whether publishers' answers are user-provided, how per-book completion is defined, IELTS/CEFR scales and collection tags, import/export rights and backup strategy.

**Current decision recorded:** Future library/books/exercises/progress extensibility is a product requirement; the specific schema, routes and UI mockups remain design proposals. No coding authorization.
# UXR-05 — Review Flashcards Design

**Track:** English Web final UI/UX redesign; design-only research task, not canonical application T001–T090 or AI-orchestration work.  
**Priority:** P0 — group **G5 Review Flashcards**, route `/review`.  
**Status:** `PREPARED / NOT STARTED / BLOCKED_BY_UXR_02A_OWNER_VISUAL_SIGNOFF`.  
**Authorization (2026-10-12):** owner approved **preparing this Markdown task card, linking it in the roadmap and updating Draft PR #26**. The owner has not approved execution of UXR-05, produced-image decisions, app implementation, component installation or PR merge.  
**Dependencies:** verified UXR-00 final evidence → UXR-01 owner-approved visual direction → UXR-02 owner-approved AppShell → UXR-02A owner-approved compact density/gallery → UXR-05 design execution and its **independent G5 visual owner approval** → UXR-10 → UXR-11.  
**Parallel sibling tasks:** UXR-03/04 and UXR-06–09 may perform separately authorized design **in parallel** only after UXR-02A owner sign-off.  
**Repo:** `khanhpn308/english_web`, branch `design/ui-ux-research-20261012`, [Draft PR #26](https://github.com/khanhpn308/english_web/pull/26) OPEN/DRAFT/unmerged.  
**Mandatory protocol:** [Full-resolution owner-visible UI, installed Impeccable, official shadcn only](../docs/design/uxr-visual-approval-impeccable-protocol-2026-10-12.md).  
**Next preparation gate:** stop for the owner to approve **UXR-06 — Quiz Builder & Runner Design**; do not prepare it autonomously now.

## 1. Outcome, scope and separation

Design an accessible, **compact, study-first flashcard reviewing experience** from date filtering to showing a due/NEW word, revealing its meanings/examples, self-rating it through the four backend-defined SRS ratings, awaiting durable acknowledgment, then moving safely to the next server-authoritative card. Show honest empty/error/UNKNOWN states, keyboard focus and progress semantics. Provide full-resolution **desktop and mobile UI images** the owner can directly inspect and explicitly approve **before UXR-05 is DONE**.

Screen surfaces:
- **Filter and queue banner:** current `noteDate` URL filter, `Tất cả ngày`, `dueOnly=true`, clear source eligibility/known page queue context.
- **Flashcard front:** English lemma, `NEW/LEARNED` status, backend due date only when present, optional note dates; prominent `Lật thẻ`.
- **Flashcard back:** Vietnamese and English meanings, bilingual examples, IPA US, verification, safe external Cambridge link; one clear four-button self-assessment after reveal, without falsely scoring an objective answer.
- **Transaction/recovery:** SRS rating pending, confirmed next schedule, stale queue/revision, no valid source, storage/session failures and ambiguous mutation outcomes that **must not be treated as success or failure without evidence**.
- **Empty and partial data:** one meaningful empty state with accessible live announcement, narrow date filter, precise local queue context, no invented future due count.

UXR-02A **already owns the cross-screen compact empty state / density precedent** and should be inherited. UXR-05 owns the **complete G5 flip/rating/review screen designs and approved state images**, not dashboard metrics (UXR-09), saving/editing vocabulary (UXR-04), quiz review-derived events (UXR-06/07) or SRS algorithm changes.

## 2. Source-confirmed behavior, screenshots and provenance

| Source | Source-confirmed rule that the design must preserve |
|---|---|
| `frontend/src/features/review/ReviewPage.tsx` | `Phase = idle/loading/ready/empty/error/submitting/unknown`. Queue GET uses `dueOnly=true`, optional validated `noteDate` from URL, `cache=no-store`; loads current card's Word Detail and requires **at least one VALID source**, existing card and NEW/LEARNED state before study is ready |
| `ReviewPage.tsx` | Queue response has `data` for **this page**, `pagination.hasMore` and `nextCursor`; UI currently uses first returned card and re-reads **page one** after confirmed review. A count of returned items **is not an authoritative lifetime total**, and `hasMore` forbids calling the first page the whole queue |
| `ReviewPage.tsx` | `noteDate` input is native `type=date`; URL changes with `pushState`, restores on `popstate`. Pending mutation temporarily locks date/rating; `All dates` clears filter. Date text in screenshot `mm/dd/yyyy` may reflect OS/browser locale, not a proven source parsing bug |
| `frontend/src/features/review/Flashcard.tsx` | Front: lemma/state/dueAt/noteDates, `Lật thẻ`; **only after `revealed`**: POS, verification, IPA, Vietnamese/English meanings, examples, safe Cambridge link, fieldset with `AGAIN/HARD/GOOD/EASY` buttons; focus moves to first rating after flip; a fresh keyed card resets reveal |
| `ReviewPage.tsx` | Each rating POST body `{rating,source:'FLASHCARD'}` carries **`If-Match` queueRevision** and stable **`Idempotency-Key`**. It stores the immutable intent fingerprint `cardId/queueRevision/rating/noteDate/key` in sessionStorage before sending; can't rate another card while pending |
| `ReviewPage.tsx` | Validated server `ReviewEvent` receipt confirms rating and `nextDueAt`; emits `vocabulary:invalidate` then fetches fresh queue, not a front-end invented due date. `UNKNOWN` preserves intent and checks same operation/receipt; `PENDING/UNKNOWN` must not be called failed, replay with changed intent prohibited |
| `docs/adr/0005-contract-clarifications.md` §C013-02 | SRS boxes `NEW=0`, `AGAIN→1`, `HARD→max(1, currentBox)`, `GOOD→min(5,box+1)`, `EASY→min(5,box+2)`. Backend selects Bangkok-calendar due midnight and timestamps; front end **never calculates or promises future schedule from design-only score labels** |
| `docs/ui-architecture.md` §J4 | Flip then self-rate; server-confirmed rating updates queue and Dashboard; no typed answer, no objective grading, local study is independent of optional AI bridge |
| `docs/design/ui-visual-audit-2026-10-12-batch2.md` | Owner screenshot of **G5 empty Review** only: VIS-006 observed duplicate empty explanation inside filter and another Card; VIS-007 date input locale ambiguity. **No direct owner capture** of live front/back, rating, loading, mutation receipt/UNKNOWN or responsive review yet |

**Evidence qualification:** owner screenshot is `CURRENT_APP_CAPTURE` only for **empty Review on desktop**. G5 is `PARTIAL`, not fully audited. Source-driven UI concerns for unpictured states are `SOURCE_CONFIRMED/NOT_VERIFIED`, **not observed visual bugs**. UXR-00 may later yield verified additional captures. Proposed assets are `DESIGN_MOCKUP` with `SYNTHETIC` data, never confused with the running app.

## 3. Readiness and execution authorization

During later execution, coordinator must link:
1. UXR-00 verified final journey/evidence matrix (including real `/review` screenshot provenance, actual CSS viewport if known, and unknown states explicitly remaining unverified).
2. UXR-01 selected and **owner signed** image direction; UXR-02 signed AppShell/theme/responsive images; UXR-02A signed Dashboard/Review-empty/Status density visuals and frozen density/CTA contract. Textual UXR task-card preparation does **not** satisfy these gates.
3. **Separate owner permission to execute UXR-05**, beyond authorization to prepare this document.
4. Named **one integration lead** and non-overlapping design-worker ownership for `docs/design/uxr-05/**`. No worker edits AppShell/tokens, UXR-02A approved density, PR or canonical task list.
5. Evidence that the **already installed local Impeccable skill is accessible separately to coordinator AND each active design worker**; actual `context` invocation and effect log per §6. Unavailability is reported and blocks DONE rather than triggering reinstall.
6. Official shadcn component strategy and approved Radix/new-york Tailwind 4 foundation have been consulted.

**Task preparation may be performed while UXR-00–02A are still pending.** Feature design execution may not.

## 4. Detailed user states and design packages

### A. Compact Review filter and empty-state integration

- One slim accessible date-filter toolbar with label, native date candidate and `Tất cả ngày` reset. The user's `noteDate` remains in `/review?noteDate=YYYY-MM-DD` on refresh/back/forward; focus and enabled controls agree with state; no date changes while a rating is unresolved.
- `dueOnly=true`: empty means **no eligible due/NEW cards in the selected queue scope**. It does not prove “you own no words,” “all words are mastered” or “there are no cards on any date.” If a filtered date is empty, show filter context plus clear-filter route; if unfiltered, show one concise empty and optional local Lookup/Search navigation.
- Remove the **duplicated visible** empty explanation seen in VIS-006; use **one** main empty surface while retaining `role=status/alert` and focus-safe live announcements (which need not duplicate an entire second visible paragraph). Empty queue, loading, read error, unknown previous mutation and storage/session blocked **must not** collapse into the same UI.
- Show known `page.data.length` as **“Thẻ trên trang dữ liệu hiện tại”** or an equivalent truthful term; where `hasMore=true`, never render a fabricated global `1 / 28` completion/progress bar or percentage. Make any proposed per-session progress explicit as an **implementation proposal dependent on new authoritative data**, not v1 present fact.
- Note `mm/dd/yyyy` screenshot is browser-locale dependent; only propose official shadcn Date Picker after keyboard/locale/ISO state preservation review, not as an already proven bug fix.

### B. Flashcard front (NEW and LEARNED) / reveal mechanics

- First action is `Lật thẻ` (or clearly localized Reveal), not an arbitrary “Check answer” grader. Present a large readable English lemma, concise status `Chưa học` vs `Đã học`, server-provided `dueAt` only if non-null, note dates as succinct secondary context.
- **NEW with `dueAt=null`** is eligible for immediate study, not “no schedule means error.” **LEARNED** card may be due based on authoritative backend queue; do not calculate or expose assumed next date before rating.
- Include screen-reader/keyboard `h1/h2` hierarchy, `lang=en` lemma, control accessible name, `aria-controls/expanded` semantics and a documented focus transition from Reveal to post-reveal rating control; avoid automatic reveal when card loads.
- Next card identity/revision change resets back to front. Do not keep the previous card's revealed meaning on the next card, and do not accidentally rate a new card with a stale button event.
- Card need not animate a 3D flip; if animation proposed, supply reduced-motion equivalent, stable DOM, focus preservation and no motion-induced distraction. No decorative auto-flip.

### C. Flashcard back, bilingual learning content and verification

- Upon explicit reveal show **all** Vietnamese and English meanings and paired example translations, part of speech, US IPA if present, and `VERIFIED/UNVERIFIED/MISSING` as human-readable status where available. Long examples, unknown IPA, missing examples/meanings and source verification uncertainty must remain honest and accessible.
- Cambridge external URL must be safe (approved hostname/protocol, `noopener noreferrer` and `no-referrer`) and a secondary clearly labeled action; no arbitrary provider text as a link. Do not invent local audio on Review unless separately approved and implemented; Lookup audio is G2-owned.
- Arrange answer and rating controls so the latter are easy to find after scrolling through long examples. Consider compact sticky review footer only as a design **proposal requiring keyboard, 320px, virtual keyboard and text accessibility rationale**, never a hidden/overlapping toolbar.
- **Only revealed and eligible card permits rating**. While `loading/submitting/unknown/storageBlocked`, rating cannot be activated. Do not show inferred “correct/incorrect” or user accuracy; this is subjective review, not quiz objective scoring.

### D. Four SRS ratings, intent persistence and receipt

**Backend-contract mapping to preserve exactly:**

| Rating | Authoritative next box transition | UI meaning (nonjudgmental proposal) |
|---|---|---|
| `AGAIN` | `1` | “Chưa nhớ” / “Học lại” |
| `HARD` | `max(1, currentBox)` | “Khó nhớ” / “Gặp khó” |
| `GOOD` | `min(5, currentBox+1)` | “Nhớ được” |
| `EASY` | `min(5, currentBox+2)` | “Rất dễ nhớ” |

- UI can display Vietnamese helpful labels with original `AGAIN/HARD/GOOD/EASY` secondary codes, but must **not** create numeric seconds/days or scheduled due date based on button selection. All due times and resulting boxes, where present, come from a validated server event. A familiar SRS app's fixed interval is **not** this app's contract.
- A single rating click persists its **exact** intent (`key/cardId/queueRevision/rating/noteDate`), sends the version guard and disables subsequent ratings until settled. Show pending state, unambiguous chosen rating and why another click would be unsafe.
- Confirmed `ReviewEvent`: only then display acknowledgment and `nextDueAt`; emit/inherit Dashboard/queue refresh, then present front of **fresh server-returned** next card (or empty if authoritative queue is empty). Clear intent only when safely acknowledged.
- A progress/animation/checkmark is allowed only for a **confirmed** event; no confetti on pending or `UNKNOWN`, no instant local assumption that a card has moved out of the queue.

### E. Errors, UNKNOWN and recovery without duplicate SRS events

Explicitly design at least:
- `LOADING` queue/detail skeleton; `EMPTY`; `READY` front; `REVEALED` back; `SUBMITTING`; `CONFIRMED` receipt/next read; `ERROR`; `UNKNOWN` with immutable intent; `SESSION_EXPIRED`; `STORAGE_BLOCKED`.
- `REVISION_CONFLICT`: a stale queue/card must **re-read** before new rating; preserve history and avoid falsely showing its due date as current.
- `NOT_FOUND` / source invalid: no eligible current card, preserve historical review events; user can re-read queue. Error is **not** equivalent to empty or quiz attempt failure.
- `STORAGE_BUSY`, local API disconnected, session rebootstrap (open Windows launcher), unreadable sessionStorage/invalid saved intent: if mutation fingerprint cannot be preserved, **block fresh ratings** rather than risking duplicates.
- Lost response / timeout / `IDEMPOTENCY_IN_FLIGHT` / `UNKNOWN`: **not confirmed failure**; show `Kiểm tra kết quả` for the **same saved intent**, with operation `PENDING/SUCCEEDED/FAILED/UNKNOWN` and valid receipt gating. Never offer “Rate again” until settlement/re-read permits a genuinely new event.
- A clearly rejected request, when proven, uses retry/re-read semantics appropriate to actual rejection; do not automatically replay changed rating or different card under same idempotency key. Technical request/operation IDs appear in accessible details, not as primary learner content.
- If `AI_CONSENT_REQUIRED` unexpectedly appears in local-review recovery, follow code's safe informational status path; **do not invent a requirement to grant AI consent to use offline/local flashcards**.

### F. Design-level layout/a11y/responsive contract

- Inherit approved UXR-02 shell/focus and UXR-02A compact filter/empty precedence. Place the word and its study action above distracting diagnostics; keep essential due/source/study status readable.
- `1366×768`, `1440×900`, `1024×768`, `768×1024`, `390×844`, `320×568` CSS-pixel mockups/analysis; study answer text and all four rating options reflow without clipping at 320px and effective 200% zoom, including long Vietnamese translation.
- Keyboard: Reveal → first rating focus (as source currently does), buttons as real buttons/fieldset, focus return/new card restoration, no hidden tab-stop traps during UNKNOWN; dated filter and dialogs/alerts reachable with screen reader.
- Mobile: comfortable rating tap targets, four choices may wrap to 2×2 or vertical stack; distinguish each using text and focus, not only colors/icons. A sticky footer is optional and must not cover content or focus.
- `prefers-reduced-motion`, visible focus and text contrast must be specified; static mockups do **not** prove WCAG 2.2 AA, browser focus, session durability or network outcomes. Put any future interaction verification explicitly in downstream implementation/audit.

## 5. Required owner-visible UI images: 22 primary full-screen frames + extras

**Non-negotiable during later authorized design execution:** create **at least 22 original full-resolution PNG/WebP UI screenshot mockups**, representing **11 scenarios × 2 actual CSS viewports** (`1366×768` desktop **and** `390×844` mobile). The images must use realistic bilingual text and clearly labeled **SYNTHETIC** fixtures; image art cannot be misrepresented as running-app behavior.

| Image pair | State/screen | Image must show |
|---|---|---|
| RV01–RV02 | Review `EMPTY` (filter/date) | Compact toolbar and **one** visible empty explanation, no guessed study total |
| RV03–RV04 | `READY` front — `NEW` | English lemma, new status, dueAt null semantics, Reveal |
| RV05–RV06 | `READY` front — `LEARNED` | Known due time from fixture, filtered date, no auto-reveal |
| RV07–RV08 | `REVEALED` back with realistic content | Vietnamese/English meanings, bilingual long examples, field verification and IPA |
| RV09–RV10 | `REVEALED` rating choice hierarchy | All four AGAIN/HARD/GOOD/EASY self-ratings, accessible labels and tap targets |
| RV11–RV12 | `SUBMITTING` pending rating | Chosen rating shown, all rating controls locked, no successful outcome claimed |
| RV13–RV14 | **Confirmed** rating receipt and fresh next-card/queue state | Backend-acknowledged nextDueAt, next card front/confirmed refresh, no made-up progress |
| RV15–RV16 | `UNKNOWN` persisted rating | Same-intent “Kiểm tra kết quả”, original action remains blocked, non-failure copy |
| RV17–RV18 | `REVISION_CONFLICT` or definitively rejected operation | Distinct error/re-read, no automatic duplicate rate |
| RV19–RV20 | `STORAGE_BLOCKED` / session recovery | Clearly locked rating, guidance and accessible diagnostics |
| RV21–RV22 | `SOURCE_INVALID / NOT_FOUND` detail/queue read | Not an empty queue; source eligibility warning and safe reload |

**Additional evidence outside the 22 count:**
1. A `320×568` stress screenshot of the long bilingual **revealed back and all four rating controls**; viewport `768×1024` tablet + `1024×768` intermediate + `1440×900` full approved shell with G5 content. Document effective 200% zoom reflow and focus concerns.
2. At least one same-state **light/dark full-screen pair** (may reuse a primary frame if both themes are represented in same state); check semantic error/confirmation and rating button hierarchy.
3. Two **materially different** study-card/reveal or rating-layout concepts inside the **already approved UXR-01** design language; provide at least one alternative desktop screenshot and one mobile screenshot, compare readable content, focus, 4-option rating visibility, density, and one-action priority. Owner chooses specific layout/version; this does not re-open the global color/brand choice.
4. Genuine current `EMPTY` capture vs proposed empty state side-by-side **only if the actual old screenshot bytes and provenance are accessible**. For front/back/rating with no baseline screenshots, label `SOURCE-ONLY / NO VERIFIED CURRENT CAPTURE`, not invented before art.
5. Annotated state storyboards for `pending → confirmed` and `pending → unknown → reconcile`; precise source-state labels, no invented SRS backend results. Include a filtered-empty example and an unfiltered-empty wording comparison, without claiming absence of all saved vocabulary.
6. Contact sheets **readable** at normal viewing size **plus separate direct full-resolution owner links** for all images; store persistent `docs/design/uxr-05/assets/*.png|webp` or owner-approved durable path. No local temp-only links or textual diagrams in place of screenshots.

**Caption required for each asset:** `UXR-05 | /review | scenario | FRONT/BACK/state | A/B variant | exact CSS viewport | light/dark | DESIGN_MOCKUP | SYNTHETIC fixture | version/date | path/link`. Real baseline screenshots use `CURRENT_APP_CAPTURE` and provenance separately. **Explicit owner response** `APPROVE / REQUEST_CHANGES / REJECT / PENDING` is recorded for the actual reviewed image/version; revised images require another review. If images or owner approval are missing, task remains `OWNER_VISUAL_APPROVAL_PENDING` and is **not DONE**.

## 6. Impeccable: installed skill must actually run for every designer

[Impeccable upstream](https://github.com/pbakaus/impeccable) is reported **already installed on the owner's Windows workstation**. **Do not install, reinstall, update, vendor or modify it** to prepare this task.

During **each later authorized local design session**, Astra/coordinator **and every individual independent G5 image/design worker** must:
1. Resolve their installed skill base in their **own harness/session**, read its `SKILL.md` and relevant commands/references. An upstream README, coordinator summary or copied tool-output does not prove skill usage.
2. Run installed `<skill-base-dir>/scripts/impeccable context` **once per session from project root**; on Windows use `<skill-base-dir>\scripts\impeccable.cmd context` if the installation provides it. Record actual executable/path/version, invocation timestamp and result; do not guess.
3. Select installed-version guidance for `shape` (learner journey), `layout`/`distill` (flashcard information density), `clarify` (Vietnamese SRS labels and empty copy), `harden` (UNKNOWN/recovery), `adapt` (320px/zoom), `critique` (peer visual hierarchy); follow command references, not indiscriminate repeated invocations.
4. Log `agent ID/role | local installed skill path/version | actual context result | command/reference | issue found | proposed design change | screenshot ID | owner review consequence` in `UXR-05-IMPECCABLE-EVIDENCE.md`. Coordinator records **its own** call and synthesizes independent worker evidence without inventing passes.
5. If unavailable, explicitly report **`IMPECCABLE_NOT_ACCESSIBLE`**, path and error. Do not silently skip, reinstall or mark the skill gate passed; task remains blocked from final sign-off until owner resolves it.
6. The skill cannot override SRS source truth, existing consent/privacy rules, official components or approved visual direction.

**This documentation-only GitHub task preparation is NOT a local skill run.** No skill invocation is claimed now.

## 7. Official shadcn/ui component mapping — design candidates only

**Single default source for missing reusable components:** https://ui.shadcn.com/docs/components. Read [official-component strategy](../docs/design/shadcn-ui-component-strategy-2026-10-12.md) and existing `components.json`: `new-york`, React 19/Vite 8/TypeScript, Tailwind 4 **without generic Preflight reset**, Radix-based existing `Button/Card/Dialog`. Reuse canonical primitives rather than installing or duplicating components.

Produce later a matrix `screen/state | exact official name and URL | EXISTING / OFFICIAL_PROPOSED / COMPOSITION / DEFERRED | focus/aria/keyboard impact | owner`.

| Review area | Official shadcn candidates | Hard interaction boundary |
|---|---|---|
| Queue/date toolbar | Existing **Button/Card**, official **Field**, **Input**, **Separator**, optional **Date Picker** | URL noteDate ISO unchanged; native date acceptable; keep labels |
| Card front/back | Existing **Card**, **Button**, official **Badge**, **Separator**, **Collapsible/Accordion** for optional metadata only | Answer remains discoverable; no hidden rated action or forced animation |
| Four ratings | Existing **Button**, official **Tooltip** only for supplemental explanation, **Badge** for status | Native semantic fieldset, all four correct labels and same-key rating guard |
| Loading/empty | Official **Skeleton**, **Empty** or app-level composition using existing Card | One visible empty message, real live region, no fabricated progress |
| Pending/unknown/error | Official **Alert**, **Badge**, **Collapsible**, existing **Dialog** only if an interaction truly requires it | Protect unresolved mutation identity, status text, explicit check-result/reload |
| Genuine known progress | Official **Progress** only **if denominator is grounded** | The current queue page count/hasMore is **not** total study progress; otherwise omit |

Propose future app-level `ReviewFilterBar`, `FlashcardFace`, `ReviewRatingControl`, `ReviewReceiptStatus`, `QueueEmpty`, `PendingReviewNotice` compositions **from official/local primitives**, not unverified third-party registries. Do not run shadcn `init`, `add`, `--all`, `--overwrite`, npm installation or lock/config/CSS changes during prep/design. Any later implementation needs separate authorization and pinned CLI/diff review by one shared primitive owner.

## 8. Future design-execution deliverables (none created now)

**Exclusive directory:** `docs/design/uxr-05/`.

| Required artifact | Contents |
|---|---|
| `UXR-05-EVIDENCE-STATE-MATRIX.md` | source phases, errors, screenshot grades, new/learned, reveal/rate/receipt/unknown, precise request guards |
| `UXR-05-REVIEW-JOURNEY.md` | filter and queue, card front/back, focus and complete study decision flow |
| `UXR-05-RATING-SRS-CONTRACT.md` | four rating labels vs backend box transitions, first-rate guard, known vs inferred nextDueAt |
| `UXR-05-UNKNOWN-RECOVERY.md` | persisted intent, revision/storage/session issues, same-operation read/receipt and forbidden duplicate ratings |
| `UXR-05-RESPONSIVE-A11Y.md` | desktop/tablet/mobile/320px/200%-zoom, keyboard/ARIA, long bilingual content and non-color focus rules |
| `UXR-05-SHADCN-MAPPING.md` | official component docs links and reuse/proposal classification |
| `UXR-05-VISUAL-GALLERY.md` + `assets/*.png|*.webp` | **22+** primary images, variants, light/dark, responsive stress, before/proposed when genuine |
| `UXR-05-IMPECCABLE-EVIDENCE.md` | actual installed skill invocations for coordinator and every worker, or genuine `IMPECCABLE_NOT_ACCESSIBLE` blocker |
| `UXR-05-OWNER-DECISION.md` | owner selection, screenshots/version/date and explicit `APPROVE` or requests |
| `UXR-05-HANDOFF.md` | frozen approved G5 design + UXR-02A density, Dashboard/Quiz seams, remaining risks, UXR-10 inputs |

Do not create these artifacts solely by preparing the task card; the later authorized design execution must render and label their images honestly.

## 9. Acceptance criteria and Definition of Done (20 mandatory checks)

**AC01** — verified UXR-00 evidence and actual UXR-01, UXR-02, UXR-02A **image-based owner approvals** plus separate permission to execute UXR-05.

**AC02** — at least **22 actual readable full-resolution PNG/WebP UI mockup frames** for 11 desktop/mobile pairs in §5, plus extra widths/theme/alternative design, all directly visible to owner.

**AC03** — owner explicitly selects and approves named **G5 front/back/rating/empty/recovery design version and asset links**; no text-only or inferred pass.

**AC04** — compact date filter, `/review?noteDate=YYYY-MM-DD`, back/forward, `Tất cả ngày` and `dueOnly=true` invariants recorded.

**AC05** — first-run/filtered-empty page has **one visible empty explanation** while preserving live region/focus, different from loading, storage error, unknown mutation and absent source; no claim all vocabulary is missing.

**AC06** — front `NEW` and `LEARNED`, lemma/note dates/authoritative nullable dueAt shown honestly; study begins on front with explicit `Lật thẻ`.

**AC07** — back reveals all VN/EN meanings/examples, POS/IPA, field verification and safe Cambridge link without pretending user answered a scored quiz.

**AC08** — exactly four review ratings `AGAIN/HARD/GOOD/EASY` available **only after reveal and readiness**, with accessible labels and readable Vietnamese help.

**AC09** — mapping of four ratings to ADR-0005 box transitions correct; no inferred numeric next due date or fabricated streak/accuracy.

**AC10** — review submission guarded by immutable `Idempotency-Key`, `If-Match` queueRevision, cardId/rating/date; status pending clearly disables further ratings.

**AC11** — only validated backend `ReviewEvent` confirms success/`nextDueAt` and triggers queue/Dashboard update; next card comes from fresh server queue and starts on front.

**AC12** — `UNKNOWN` holds original intent; `PENDING/UNKNOWN` operation cannot mean failed or success; safe same-operation reconciliation is visually primary, no duplicate new rating.

**AC13** — stale revision, source loss, source invalid and API/session error have distinct non-destructive re-read/rebootstrap paths; no false empty or mastery status.

**AC14** — storageBlocked and unpersistable intent prevent fresh ratings; diagnostics available via accessible disclosure without exposing secrets.

**AC15** — no invented whole-queue denominator, “cards mastered” percentage, total pages or universal finished assertion from `page.data.length` or `hasMore`.

**AC16** — responsive desktop/tablet/390px/320px and effective 200%-zoom design, all four rating options reachable, focus and long text not obscured.

**AC17** — accessible keyboard/tab/flip-to-rating focus, live/status/error announcement, fieldset/button semantics, meaningful EN/VI language and reduced-motion requirements described; **not** a runtime WCAG PASS claim.

**AC18** — every missing component mapped to official shadcn docs, existing Radix Button/Card/Dialog reused, no package installs/lockfile changes.

**AC19** — coordinator **and each actual local UI design worker** have real installed Impeccable `context` invocation and documented guidance applied; failure declared `IMPECCABLE_NOT_ACCESSIBLE` and blocks DONE.

**AC20** — G5 signed visual gallery, source evidence ledger, shadcn matrix, runtime-unverified risks and UXR-06/07/09/10 design seams handed off; no application files, API/SQLite/SRS/consent/quiz logic, canonical task list, full-system audit or Draft PR merge changed.

**Task lifecycle:** `PREPARED → READY_FOR_EXECUTION → IN_PROGRESS → OWNER_VISUAL_APPROVAL_PENDING → DONE` **only** after all ACs, screenshots, installed-skill evidence and owner response. Missing required proof = not DONE.

## 10. Explicit exclusions and safety invariants

- No implementation/source refactor in this design or task-preparation stage: `frontend/**`, `backend/**`, `components.json`, `package-lock.json`, SQLite, OpenAPI/generated DTOs, Windows launcher and `tasks/todo.md` remain unchanged.
- No local app start, Playwright, UI screenshot capture or skill invocation is implied by creating this task document. No passing accessibility/verification/security benchmark is claimed.
- No changed SRS boxes, Bangkok calendar formula, queue eligibility, `source='FLASHCARD'`, card lifecycle or backend receipt/idempotency rule; no replacing local review with an AI call.
- No invention of lifetime queue total, review accuracy, user streak, flashcard answer grading or new spaced repetition intervals. Future Library/book/TOEIC/IELTS source tags are **not** implemented in this task.
- No redesign of UXR-01/02 shared shell/tokens, UXR-02A density contract, UXR-04 Save/Edit, UXR-06 Quiz workflow, UXR-07 result/feedback or UXR-08 consent statuses.
- No UXR-00 closure, UXR-11 final visual sign-off, UXR-12 adoption or PR #26 merge. Owner permission to draft UXR-05 is **not** a permission to run UXR-06 or deploy redesign.

## 11. Parallel execution, conflict avoidance and ownership

**DAG:** `UXR-00 → UXR-01 → UXR-02 → UXR-02A → {UXR-03, UXR-04, UXR-05, UXR-06, UXR-07, UXR-08, UXR-09} → UXR-10 → UXR-11`.

During any later separately approved G5 design run:
- One **UXR-05 integration lead** owns the consolidated state matrix, screenshot inventory, design approval record and handoff.
- Distinct **G5 card-front/back** and **G5 ratings/recovery** workers may independently study the same source and deliver uniquely named image assets in isolated scratch areas. Each uses installed Impeccable in its **own** session. Only lead writes shared summary and PR metadata.
- UXR-02/02A frozen foundations are **read only**; request coordinator/owner versioned exception rather than silently rewriting shared tokens.
- UXR-03/04/06–09 work trees/artifacts are disjoint; shared visual status/receipt semantics go through a versioned handoff, not competing edits.

| Area | Single writer/access |
|---|---|
| `tasks/uxr-05-review-flashcards-design.md` | task-spec/roadmap coordinator |
| `docs/design/uxr-05/UXR-05-*-*.md` and final approval/handoff | designated G5 integration lead |
| `docs/design/uxr-05/assets/front-*`, `assets/back-*` | card visual worker |
| `docs/design/uxr-05/assets/rating-*`, `assets/recovery-*`, `assets/empty-*` | rating/recovery visual worker |
| `docs/design/uxr-05/UXR-05-IMPECCABLE-EVIDENCE.md` | lead synthesizes logged coordinator and worker calls |
| `docs/design/uxr-01/**`, `uxr-02/**`, `uxr-02a/**`, shared protocol, UXR-00 captures | read-only references |
| `docs/design/uxr-06/**`, `uxr-07/**`, `uxr-09/**` (future) | those task owners exclusively |
| `docs/design/english-web-ui-ux-redesign-plan-2026-10-12.md`, Draft PR #26 | **one** roadmap coordinator |
| `frontend/**`, `backend/**`, dependencies, `tasks/todo.md` | strictly read-only |

## 12. Handoff and next owner checkpoint (UXR-06)

On later **actual** UXR-05 image approval, hand the signed version and full-resolution G5 gallery to UXR-10 for nine-group design QA; share only G5 cross-feature interface rules with:
- **UXR-06:** quiz-derived review events use the same authoritative SRS contract, but quiz question answering and scoring are **not flashcard ratings** and are owned by Quiz Builder/Runner.
- **UXR-07:** objective quiz results, learner writing self-score and optional AI feedback remain distinct from G5 subjective self-assessment.
- **UXR-09:** Dashboard updates due/learning summary **only after acknowledged review event**, not when learner merely clicks a rating.
- **UXR-02A:** compact Review empty and date filter layout precedent already approved; UXR-05 final interaction states inherit it.

Deliver versioned decision ledger, screenshot links, a source-to-state matrix, Impeccable actual invocation evidence, official component choices, responsive/accessibility design risks and untouched business logic.

**Current preparation ends here:** commit only `tasks/uxr-05-review-flashcards-design.md`, update roadmap and Draft PR #26, verify documentation-only changes and **stop for explicit owner permission before preparing UXR-06**. No redesign code or actual owner-reviewed images have been created by this task preparation.

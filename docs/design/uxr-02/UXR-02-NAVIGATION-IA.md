# UXR-02 Navigation and Information Architecture

**Direction:** B - Compact Study Console v1.2
**State:** Approved design contract, UXR-02-R2 + HM-FIX, 2026-10-14.

## v1 navigation register

| featureId | group | label | route | enabled | active descendant rule |
|---|---|---|---|---|---|
| `dashboard` | Learning / Học tập | Tổng quan | `/` | yes | Exact `/`; root only. |
| `lookup` | Vocabulary / Từ vựng | Tra cứu AI | `/lookup` | yes | Exact route; AI consent gate remains default-deny. |
| `search` | Vocabulary / Từ vựng | Kho từ | `/search` | yes | Exact `/search`; detail route keeps Kho từ active. |
| `review` | Learning / Học tập | Ôn tập | `/review` | yes | Exact route; focus study context keeps Ôn tập active. |
| `quiz` | Learning / Học tập | Tạo bài kiểm tra | `/quiz/new` | yes | Prefix `/quiz`; runner and result remain contextual. |
| `status` | System / Hệ thống | Trạng thái | `/status` | yes | `/status` and `/status#ai-consent`. |

R2 visually groups Tổng quan, Ôn tập and Tạo bài kiểm tra under Học tập; Tra cứu AI and Kho từ under Từ vựng; Trạng thái & quyền AI under Hệ thống. Luyện tập remains a future logical extension seam, not a fourth displayed R2 heading. The functional destinations remain exactly the six current global links. Detail/edit and quiz runner/result are contextual routes, not duplicate sidebar entries.

## Route semantics

- `/word-forms/:id`: breadcrumb `Tổng quan -> Kho từ -> [lemma]`; Search remains `aria-current="page"` in the global rail. Query, filter, sort and cursor state remain URL state.
- `/quiz/:attemptId`: breadcrumb `Tổng quan -> Ôn tập -> Phiên hiện tại` or the explicit originating quiz path; Quiz/Practice parent remains active. The draft and attempt ID remain untouched.
- `/quiz/:attemptId/result`: same contextual parent, terminal result copy; no new global link.
- `/status#ai-consent`: deep link scrolls/focuses the consent section without inventing Settings. The shell shortcut is visible from every screen.
- Unknown route: preserve the shell, show a focused `Không tìm thấy trang` heading, and offer a single return-to-dashboard action.
- Back/forward and direct deep links: keep current same-origin `pushState`/`replaceState` semantics and move focus to the new screen heading after route change. This is a source invariant, not a claim that the mockup tested the browser router.

## Future extension seam (hidden until shipped)

The groups are intentionally extensible without adding live placeholders:

```text
HOC TAP
  Tổng quan
  Thư viện -> FUTURE -> HIDDEN UNTIL SHIPPED
TU VUNG
  Tra cứu AI
  Kho từ
  Ôn tập
LUYEN TAP
  Tạo bài kiểm tra
  Bài tập theo sách -> FUTURE -> HIDDEN UNTIL SHIPPED
HE THONG
  Trạng thái
  Quyền gửi dữ liệu AI -> within Status, not a route
```

Library, Books, Chapters, Lessons, book exercises, vocabulary linked to lessons, learning progress, IELTS, TOEIC, CEFR and Reading/Listening/Writing/Speaking are future concepts only. The shell reserves group seams for these concepts without creating links or route claims. No clickable placeholder or backend claim appears in the mockup.

## Interaction and focus proposal

Desktop tab order: skip link -> brand/home -> collapse control -> grouped links -> consent shortcut -> menu/status actions -> breadcrumb -> route content. Mobile: skip link -> menu trigger -> header actions -> breadcrumb -> content; when drawer opens, focus moves to its close button, is trapped in the drawer, closes on Escape/backdrop, then returns to the trigger. Active navigation exposes `aria-current="page"` independently of visual styling. Long Vietnamese labels wrap, and icon-only collapsed controls require accessible names/tooltips.

## Approved owner decision ledger

| Decision | Proposed value | Owner state |
|---|---|---|
| Desktop default | Expanded dark teal rail, user collapsible | `APPROVED_DESIGN` |
| Mobile pattern | shadcn Sidebar/Sheet-style drawer, closed by default | `APPROVED_DESIGN` |
| Group labels | Học tập, Từ vựng, Luyện tập, Hệ thống | `APPROVED_DESIGN` |
| Header placement | R2 compact 54px header; mobile 58px | `APPROVED_DESIGN` |
| Breadcrumb | Within R2 header, route-contextual | `APPROVED_DESIGN` |
| Theme | Cool teal light/dark semantic tokens | `APPROVED_DESIGN` |
| Focus mode | Same shell, content width narrows and chrome recedes | `APPROVED_DESIGN` |
| AI consent | Status-owned deep link, persistent shell access | `APPROVED_DESIGN` |

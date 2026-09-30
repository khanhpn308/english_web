# Project Context

## Phạm vi kiểm kê

Kiểm kê được thực hiện ngày 29/09/2026 theo múi giờ `Asia/Bangkok`. Thư mục làm việc là `/home/khanh/projects/vocabularies`.

Spec hiện hành là [docs/spec.md](spec.md) cùng quyết định v1 trong ADR-0004. [Đặc tả legacy](development/spec/vocabulary-platform-spec.md) chỉ là nguồn lịch sử; không dùng để tự mở rộng scope. `docs/spec-draft.md` không tồn tại.

## Repository map

```text
.
├── AGENT.md
├── AGENTS.md
├── CONSTRAINTS.md
├── tasks/
│   ├── _template.md
│   ├── todo.md
│   └── t001–t066 task cards        # ID giữ ổn định; task-plan ghi execution order
├── docs/
│   ├── changelogs.md
│   ├── adr/
│   │   ├── 0001-architecture.md
│   │   ├── 0002-antigravity-loopback-trust-boundary.md
│   │   ├── 0003-ai-consent-and-revocation.md
│   │   └── 0004-v1-product-policy-and-operational-baseline.md
│   ├── development/
│   │   └── spec/
│   │       └── vocabulary-platform-spec.md
│   ├── reviews/
│   │   └── spec-architecture-review-001.md
│   ├── runbooks/
│   │   ├── api-unavailable.md
│   │   ├── bridge-failure.md
│   │   ├── source-sync.md
│   │   └── storage-integrity.md
│   ├── api-contract.md
│   ├── ui-architecture.md
│   ├── security-review.md
│   ├── observability-plan.md
│   ├── project-context.md          # file này
│   ├── task-plan.md
│   └── vocabularies/
│       ├── README.md
│       └── 28-09-2026.md
└── paper-vocabulary.zip            # archive chứa paper-vocabulary/SKILL.md
```

Các thư mục `docs/deployment/guide` và `docs/development/tasks` hiện tồn tại nhưng chưa có file được phát hiện. Không có thư mục `frontend/`, `backend/`, `src/`, `app/` hoặc test suite.

## Trạng thái Git và branch

- `/home/khanh/projects/vocabularies` được xác nhận là project root trong session này.
- Git repository đã được khởi tạo tại root bằng branch mặc định cục bộ `main`.
- Repository chưa có commit nào; toàn bộ file hiện có đang ở trạng thái untracked.
- Chưa cấu hình remote vì chưa có URL remote được cung cấp.
- Branch nên dùng cho giai đoạn thiết kế sau khi repository có remote: `feature/design-foundation`. Đây là đề xuất theo convention feature branch; chưa được tạo.

## Runtime, package manager và toolchain

### Đã xác nhận

- Có shell `bash` trong môi trường thực thi.
- Có `python3` trong môi trường thực thi; đây là công cụ môi trường, chưa phải runtime được khai báo cho dự án.
- Archive `paper-vocabulary.zip` là ZIP hợp lệ và chứa một file `paper-vocabulary/SKILL.md`.

### Chưa có trong repository

- Không có `package.json`, `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `bun.lock*`.
- Không có `pyproject.toml`, `requirements*.txt`, `Pipfile`, `go.mod`, `Cargo.toml` hoặc manifest tương đương.
- Không có `.nvmrc`, `.node-version`, Dockerfile, compose file, `tsconfig`, Vite/Next/Astro/Webpack config hay `.env.example`.
- Không thể xác định package manager, phiên bản Node/Python của ứng dụng, lệnh build, lệnh test hoặc lệnh lint từ repository.

ADR-0004 chốt Python 3.12+/FastAPI, React/TypeScript/Vite và SQLite/SQLAlchemy/Alembic cho v1. T001 phải xác minh exact releases và tạo lockfiles; đây chưa phải toolchain đã cài trên máy.

## Frontend và backend hiện có

- **Frontend:** chưa có mã nguồn, manifest, build config, route, component hoặc test.
- **Backend:** chưa có mã nguồn, manifest, API route, schema, database migration hoặc runtime config.
- **Dữ liệu/tài liệu hiện có:** nhật ký từ vựng Markdown ngày `28-09-2026`, README quy ước định dạng, đặc tả nền tảng và skill được đóng gói trong ZIP.
- **Hạ tầng chạy ứng dụng:** chưa có cấu hình bind host/port, database file, watcher, CI/CD, container hoặc deployment.

### Trạng thái thiết kế sau adversarial review

- `docs/spec.md`: `SPEC_STATUS: READY_FOR_PLANNING` after ADR-0004 decision closure; runtime verification remains implementation work.
- `docs/adr/0001-architecture.md`: proposed baseline with superseding ADRs, `ARCHITECTURE_STATUS: READY_FOR_PLANNING`.
- `docs/adr/0004-v1-product-policy-and-operational-baseline.md`: accepted v1 product/operational defaults; closes OQ-01–OQ-14 for planning without claiming implementation tests passed.
- `docs/adr/0002-antigravity-loopback-trust-boundary.md`: accepted chỉ cho bridge HTTP loopback/API-key và rủi ro process giả mạo cục bộ; supersedes một phần ADR-0001, không phê duyệt toàn bộ architecture.
- `docs/adr/0003-ai-consent-and-revocation.md`: accepted cho consent AI local default-deny, lưu policy version, revoke offline và chặn dispatch mới; provider/route disclosure defaults are completed by ADR-0004.
- `docs/reviews/spec-architecture-review-001.md`: 50 findings đã được owner yêu cầu áp dụng; ADR-0002/0003/0004 close design blockers and set `REVIEW_STATUS: READY_FOR_PLANNING`; implementation/runtime/CONSTRAINTS gates remain for the planning session.
- `docs/api-contract.md`, `docs/ui-architecture.md`, `docs/security-review.md`, `docs/observability-plan.md`: planning baseline; implementation/runtime verification still required.
- `CONSTRAINTS.md`: project quality bar created in this planning session; thresholds and command ownership must not be weakened.
- `AGENTS.md`: persistent implementation/session context; `AGENT.md` remains the changelog/documentation rule file.
- [docs/task-plan.md](task-plan.md): `PLAN_STATUS: READY_FOR_IMPLEMENTATION`, 66 task cards và 22 checkpoints; graph/table/checklist đồng bộ theo dependencies. Tất cả implementation task vẫn TODO.
- [tasks/t013-contract-conformance.md](../tasks/t013-contract-conformance.md): chuẩn hóa các ví dụ/chi tiết contract còn mơ hồ trước khi code phụ thuộc. Không sửa review status để né gate; apply ADR-0004 precedence và authority đã được owner ủy quyền.
- [planning-validation-001](reviews/planning-validation-001.md): kiểm tra planning đạt exit 0 với 66 task cards, 225 dependency edges không chu kỳ, 22 checkpoints và linked current/planned outputs hợp lệ. Application build/tests chưa chạy.

### Bridge được owner xác nhận ngày 29/09/2026

- Local API proxy là [Antigravity Tools / Antigravity-Manager](https://github.com/lbjlaq/Antigravity-Manager), không phải yêu cầu xây tích hợp CLI. Token/session tài khoản Google do proxy quản lý; app từ vựng chỉ dùng credential client của proxy ở backend.
- Owner xác nhận phiên bản đang dùng là **v4.8.4**. Tag upstream `v4.8.4` trỏ commit `0269f045f4e35f34b9ee3b3bcd6c0ff1e741378f`, trùng nguồn đã đối chiếu. Đây là xác nhận của owner và kiểm tra source upstream, không phải kiểm tra binary/cấu hình trên máy.
- Owner đã chấp thuận HTTP loopback + proxy client key, tắt LAN và tin cậy máy/tài khoản Windows, không cam kết chống tiến trình cục bộ giả mạo proxy. ADR-0002 thay yêu cầu per-launch bridge secret/IPC/process identity cũ. API §6 và `BR-AUTH-01`–`09` định nghĩa profile, preflight/error behavior, route/model policy check và verification. Browser session không đổi. R2-001 được xử lý ở cấp thiết kế; profile thật/key rotation và implementation tests vẫn phải kiểm chứng trước release.
- Owner đã chấp thuận consent trước lần gửi AI đầu tiên, lưu lựa chọn và revoke để chặn AI mới; ADR-0003, API consent singleton, UI `/status#ai-consent`, threats T-22–T-24 và CONSENT-01–12 đã ghi contract. ADR-0004 bổ sung policy v1 (Antigravity/Google, Gemini `gemini-3.8-flash-high`, route primary, configured-account billing, không automatic fallback) và nêu rõ retention/region do provider kiểm soát. Dữ liệu đã vào transport không thể thu hồi; local study không bị xóa. R2-002 được xử lý ở cấp thiết kế; policy fixture, entitlement/quota và implementation tests vẫn là release gates. Không có thay đổi cấu hình proxy, gọi inference, đọc credential hay application code trong lượt áp dụng này. Chi tiết resolution nằm ở [review](reviews/spec-architecture-review-001.md).

## Các file quan trọng

| File | Vai trò | Tình trạng |
|---|---|---|
| `AGENT.md` | Quy định cho agent, gồm changelog bắt buộc và yêu cầu dùng documentation skill khi tạo tài liệu kỹ thuật | Đang áp dụng |
| `AGENTS.md` | Context implementation, boundaries, commands and Git/session rules | Đang áp dụng |
| `CONSTRAINTS.md` | Project quality/security/accessibility/performance floor and command gates | Đang áp dụng |
| `tasks/` | T001–T066 task cards, template, todo checklist and plan pointer | Plan ready; all tasks TODO |
| `docs/development/spec/vocabulary-platform-spec.md` | Đặc tả thiết kế chốt v1, gồm phạm vi, kiến trúc đề xuất, hợp đồng Markdown và mô hình SQLite | Chỉ đọc trong session này |
| `docs/vocabularies/README.md` | Hợp đồng định dạng nhật ký từ vựng hàng ngày | Đang áp dụng cho dữ liệu Markdown |
| `docs/vocabularies/28-09-2026.md` | Dữ liệu mẫu/thực tế với hai mục từ | Đang có |
| `docs/changelogs.md` | Lịch sử thay đổi do agent | Phải cập nhật khi sửa workspace |
| `paper-vocabulary.zip` | Archive của skill xử lý từ vựng; không phải source application | Chưa giải nén |
| `docs/project-context.md` | Bản đồ context cho các session sau | Tạo trong session này |

## Giới hạn hiện tại

- Repository mới khởi tạo chưa có commit, remote, branch protection hoặc cơ chế review.
- Runtime/package manager/toolchain baseline đã được ghi trong ADR-0004 và CONSTRAINTS.md; exact versions/lockfiles vẫn do T001 pin.
- Chưa có frontend/backend để chạy, build, test hoặc kiểm tra type.
- Chưa có manifest/lockfile triển khai; không được suy ra rằng architecture baseline đã được triển khai.
- `paper-vocabulary.zip` chưa được giải nén thành một skill file trong workspace; nội dung archive chỉ được xem như tài liệu đầu vào.
- Không có `docs/spec-draft.md`; nếu một draft khác tồn tại ngoài workspace này, session này chưa thể xác minh.
- Hiện tại mọi file đều là thay đổi chưa commit của repository mới; T045 ghi quy trình Git nhưng session này không commit.

## Context và giới hạn cho session tiếp theo

- `/home/khanh/projects/vocabularies` là project root intended.
- `docs/spec.md` + ADR-0004 là authority hiện hành; legacy spec/interview giữ lịch sử.
- Kiến trúc Python/FastAPI và React/TypeScript/Vite trong ADR-0004 là v1 baseline; T001 pin exact releases.
- SQLite và Markdown vẫn là nguồn dữ liệu/read model được chọn cho v1; migration behavior thuộc T005/T019/T022.
- `paper-vocabulary.zip` sẽ được giữ nguyên hoặc được giải nén theo một quy trình được thống nhất sau này.
- `feature/design-foundation` là đề xuất Git lịch sử; implementation theo AGENTS dùng `feature/task-<id>-<slug>` khi branching được cho phép.

## Câu hỏi cần làm rõ ở session tiếp theo

1. URL remote chính thức là gì, và remote đó dùng tên `origin` hay tên khác?
2. Branch thiết kế có dùng tên `feature/design-foundation` hay convention khác của nhóm?
3. T001 cần xác minh exact Node/Python/package versions against official release/runtime availability.
4. Có cần giải nén/cài đặt `paper-vocabulary` thành skill hoặc chỉ giữ archive làm tài liệu?
5. Có repository hoặc tài liệu README bên ngoài workspace cần liên kết vào context không?
6. Remote Git chính thức và branch protection vẫn chưa được cung cấp.
7. Nếu owner thay đổi một decision trong ADR-0004, phải tạo ADR superseding và cập nhật task dependencies; không sửa task status để né gate.

## Phiên tiếp theo nên bắt đầu từ đâu

Bắt đầu bằng [T001](../tasks/t001-toolchain-repository-skeleton.md); sau đó T002/T058, backend T003, frontend T004, storage T005 và các checkpoint trong [task-plan](task-plan.md). Lệnh/tool chưa tồn tại phải PENDING. Session planning chưa viết application code, chạy inference, commit hoặc tạo remote.

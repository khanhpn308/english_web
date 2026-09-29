# Vocabulary Learning Application (v1)

Ứng dụng học từ vựng học thuật cá nhân, local-first trên Windows, tích hợp AI qua loopback proxy bridge Antigravity Tools và hỗ trợ ôn tập bằng SRS, bài kiểm tra (trắc nghiệm, điền từ, viết câu) và nhật ký Markdown.

## Yêu cầu môi trường (Prerequisites)

- **Node.js**: `>=20.19.0` (khuyến nghị Node 22 LTS, ví dụ `v22.23.2`) và **npm** `>=10.0.0`
- **Python**: `3.12+` (ví dụ Python `3.12.3`)
- **Hệ điều hành**: Windows 11 (mục tiêu chạy ứng dụng chính thức) / Linux (môi trường dev hiện tại)

## Cài đặt công cụ và dependencies (Install Recipe)

### 1. Frontend dependencies

```bash
npm ci
```

Lệnh `npm ci` cài đặt chính xác các package đã khóa tại `package-lock.json` (React 19, Vite 8, TypeScript).

### 2. Backend dependencies

Khởi tạo và kích hoạt virtual environment Python 3.12:

```bash
# Trên Linux / macOS:
python3 -m venv .venv
source .venv/bin/activate

# Trên Windows (PowerShell):
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Cài đặt các gói đã khóa phiên bản qua pip-tools lockfile:

```bash
# Cài đặt môi trường phát triển (bao gồm testing, linting, typing tooling):
python -m pip install -r requirements-dev.lock

# Hoặc cài đặt runtime tối thiểu cho backend:
python -m pip install -r requirements.lock
```

## Trạng thái lệnh phát triển (Command Readiness)

Tại mốc `T001`, repository mới chỉ hoàn thành khóa phiên bản toolchain (`package.json`, `package-lock.json`, `pyproject.toml`, `requirements.lock`, `requirements-dev.lock`) và cấu hình `.gitignore`. Chưa có mã nguồn ứng dụng hay test runner nào được coi là đã pass:

| Lệnh | Trạng thái hiện tại | Task phụ trách thiết lập |
|---|---|---|
| `npm ci` | **SẴN SÀNG** | T001 (xác minh thành công) |
| `pip install -r requirements-dev.lock` | **SẴN SÀNG** | T001 (xác minh thành công) |
| `npm run lint` | *CHƯA CÓ* | T002 |
| `npm run typecheck` | *CHƯA CÓ* | T002 |
| `npm run test:frontend` | *CHƯA CÓ* | T002 |
| `npm run build` | *CHƯA CÓ* | T002 / T004 |
| `python -m ruff check .` | *CHƯA CẤU HÌNH GATE* | T058 |
| `python -m mypy backend` | *CHƯA CÓ BACKEND CODE* | T058 / T003 |
| `python -m pytest` | *CHƯA CÓ TESTS* | T058 / T003 |

## Cấu trúc thư mục dự kiến

- `frontend/`: Ứng dụng giao diện React 19 + TypeScript + Vite (thiết lập tại T002/T004).
- `backend/`: Mã nguồn FastAPI, domain models, SQLite và SQLite migration (thiết lập tại T003/T005).
- `docs/`: Đặc tả kiến trúc (`spec.md`, `api-contract.md`, `ui-architecture.md`), ADRs, và kế hoạch kiểm thử.
- `tasks/`: Danh sách các task card (`T001` - `T066`) và checklist (`todo.md`).

Chi tiết thêm về quản lý phiên bản và cập nhật lockfiles xem tại [`docs/toolchain.md`](docs/toolchain.md).

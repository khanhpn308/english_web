# Toolchain và Repository Skeleton (T001)

Tài liệu này ghi lại đặc tả phiên bản công cụ (toolchain), công thức cài đặt (install recipe), cách tạo và cập nhật lockfiles, cùng với quy trình kiểm thử tái lập (reproducible clean install) cho dự án theo [CONSTRAINTS.md](../CONSTRAINTS.md) và [ADR-0004](adr/0004-v1-product-policy-and-operational-baseline.md).

## 1. Môi trường baseline đã xác minh

Dự án yêu cầu hai toolchain độc lập ở cấp độ phát triển (development time):

| Môi trường | Phiên bản yêu cầu | Phiên bản xác minh cục bộ | Vai trò |
|---|---|---|---|
| **Python** | `>=3.12` | `3.12.3` | Backend runtime (FastAPI, SQLite, Alembic) |
| **pip** | `>=22.2` | `26.2.1` | Trình cài đặt package Python |
| **pip-tools** | `>=7.4.0` | `7.6.1` | Trình biên dịch lockfiles Python (`pip-compile`) |
| **Node.js** | `>=20.19.0` (LTS) | `v22.23.2` | Trình chạy build/lint/test frontend |
| **npm** | `>=10.0.0` | `12.0.2` | Quản lý package frontend |
| **Hệ điều hành** | Windows 11 (target), Linux (dev) | Linux (Ubuntu/Debian) | Môi trường thực thi |

## 2. Phân chia ranh giới quản lý dependencies

Dự án áp dụng ranh giới phân tách rõ ràng giữa hai stack:

1. **Frontend**:
   - Khai báo tại `package.json` ở project root.
   - Lockfile chuẩn: `package-lock.json` (chỉ tạo và cập nhật bằng `npm install`).
   - Cài đặt sạch (clean install) bắt buộc dùng: `npm ci`.
   - Core libraries:
     - `react`: `^19.0.0` (đã resolve `19.3.0`)
     - `react-dom`: `^19.0.0` (đã resolve `19.3.0`)
     - `vite`: `^8.3.1`
     - `@vitejs/plugin-react`: `^6.1.1`
     - `typescript`: `^5.8.2`
     - `@types/react`, `@types/react-dom`: `^19.0.0`

2. **Backend**:
   - Khai báo tại `pyproject.toml` ở project root theo chuẩn PEP 621.
   - Lockfiles chuẩn được sinh bởi `pip-tools`:
     - `requirements.lock`: Runtime dependencies tối thiểu cho backend (FastAPI, Pydantic, SQLAlchemy, Alembic, Uvicorn, HTTPX).
     - `requirements-dev.lock`: Đầy đủ dependencies cho phát triển và kiểm thử (bổ sung Ruff, Mypy, Pytest, Pytest-cov, Pip-tools).
   - Cài đặt vào virtual environment (`.venv/`):
     - Dev: `python -m pip install -r requirements-dev.lock`
     - Runtime: `python -m pip install -r requirements.lock`

## 3. Công thức cài đặt và tái lập (Install Recipe)

### Bước 1: Chuẩn bị môi trường Python

```bash
# Khởi tạo virtual environment
python3 -m venv .venv

# Kích hoạt venv (Linux/Bash)
source .venv/bin/activate

# Kích hoạt venv (Windows PowerShell)
.venv\Scripts\Activate.ps1
```

### Bước 2: Cài đặt Backend dependencies

```bash
python -m pip install -r requirements-dev.lock
```

### Bước 3: Cài đặt Frontend dependencies

```bash
npm ci
```

## 4. Quy trình tái sinh Lockfiles (Lockfile Regeneration)

Khi có yêu cầu cập nhật dependency đã được phê duyệt (tuân thủ quy định change-control trong `CONSTRAINTS.md`):

1. **Frontend (`package-lock.json`)**:
   ```bash
   npm install
   ```
   *Không chỉnh sửa `package-lock.json` bằng tay.*

2. **Backend (`requirements.lock` & `requirements-dev.lock`)**:
   ```bash
   # Cập nhật runtime lockfile
   pip-compile --output-file=requirements.lock pyproject.toml

   # Cập nhật dev lockfile
   pip-compile --extra=dev --output-file=requirements-dev.lock pyproject.toml
   ```
   *Không chỉnh sửa các file `.lock` bằng tay.*

## 5. Cấu hình loại trừ (.gitignore)

`.gitignore` đã được cấu hình toàn diện để ngăn chặn vô tình commit:
- Virtual environments: `.venv/`, `venv/`, `env/`
- Node dependencies: `node_modules/`
- Build outputs: `dist/`, `build/`, `frontend/dist/`
- Caches: `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`, `.coverage*`
- Databases & SQLite journals: `*.db`, `*.sqlite`, `*.sqlite3`, `*.db-journal`, `*.db-wal`
- Secrets & credentials: `.env`, `.env.*` (ngoại trừ `!.env.example`), `*.pem`, `*.key`, `*.dpapi`, `*.secret`, `*.token`, `secrets/`
- Ảnh chụp màn hình có nguy cơ chứa API key: `screenshots/`, `sceenshots/`, `*.screenshot.*`

## 6. Python Quality Gates và Test Runner (T058)

Dự án thiết lập hệ thống kiểm tra chất lượng mã nguồn Python nghiêm ngặt tại `pyproject.toml`, tuân thủ [CONSTRAINTS.md](../CONSTRAINTS.md):

### 6.1. Ruff (Linter & Formatter)
- Cấu hình tại `[tool.ruff]` và `[tool.ruff.lint]`.
- Bộ quy tắc kích hoạt: `E`, `W`, `F`, `I` (isort), `B` (bugbear), `C4` (comprehensions), `UP` (pyupgrade), `ARG` (unused arguments), `SIM` (simplify), `RUF` (ruff specific).
- Không sử dụng bất kỳ suppression nào (`# noqa`).
- Lệnh kiểm tra:
  ```bash
  python -m ruff check backend
  python -m ruff check .
  python -m ruff format --check .
  ```

### 6.2. Mypy (Static Type Checker)
- Cấu hình tại `[tool.mypy]`.
- Chế độ: `strict = true`, `python_version = "3.12"`, `warn_return_any = true`, `warn_unused_configs = true`.
- Mục tiêu quét mặc định: `files = ["backend"]`.
- Không sử dụng bất kỳ suppression nào (`# type: ignore`).
- Lệnh kiểm tra:
  ```bash
  python -m mypy backend/tests/test_toolchain.py
  python -m mypy backend
  ```

### 6.3. Pytest & Pytest-cov (Test Runner & Coverage)
- Cấu hình tại `[tool.pytest.ini_options]`, `[tool.coverage.run]`, `[tool.coverage.report]`, `[tool.coverage.xml]`.
- Tự động đo coverage cho `backend` và xuất báo cáo `coverage.xml` (chuẩn Cobertura XML) sau mỗi lần chạy suite.
- Tuyệt đối không cho phép ghi đè exit code khi không có test (`no no-tests pass override`).
- Lệnh kiểm tra:
  ```bash
  python -m pytest backend/tests/test_toolchain.py -q
  python -m pytest
  ```

### 6.4. Kế hoạch chuyển tiếp (Transition Plan)
- Hiện tại (pre-T003), thư mục `backend/` chứa `backend/tests/` với các smoke test kiểm chứng môi trường, phiên bản Python (>=3.12), khả năng import các package bị khóa trong lockfiles và cơ chế nạp fixtures `conftest.py`.
- Khi T003 tạo `backend/app/`, mã nguồn ứng dụng sẽ tự động được đưa vào phạm vi kiểm tra kiểu của Mypy (`python -m mypy backend`) và theo dõi độ phủ của Pytest Coverage (`--cov=backend`).

## 7. Trạng thái kiểm chứng các nhiệm vụ Toolchain

- **T001 (Hoàn thành)**: Thiết lập lockfiles (`requirements.lock`, `requirements-dev.lock`, `package-lock.json`), quy tắc `.gitignore`, `README.md` và `docs/toolchain.md`.
- **T058 (Hoàn thành)**: Thiết lập Python quality gates (Ruff, Mypy strict, Pytest runner và Cobertura XML coverage artifact). Runner phát hiện test thật, negative probes xác nhận báo lỗi đúng exit code khi assertion/import/collection/type/lint thất bại.
- **T002 (Kế tiếp)**: Cấu hình frontend runner, linting (ESLint), typechecking (TypeScript config), Vitest và build readiness.


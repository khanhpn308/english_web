# Toolchain và Repository Skeleton (T001)

Tài liệu này ghi lại đặc tả phiên bản công cụ (toolchain), công thức cài đặt (install recipe), cách tạo và cập nhật lockfiles, cùng với quy trình kiểm thử tái lập (reproducible clean install) cho dự án theo [CONSTRAINTS.md](../CONSTRAINTS.md) và [ADR-0004](adr/0004-v1-product-policy-and-operational-baseline.md).

## 1. Môi trường baseline đã xác minh

Dự án yêu cầu hai toolchain độc lập ở cấp độ phát triển (development time):

| Môi trường | Phiên bản yêu cầu | Phiên bản xác minh cục bộ | Vai trò |
|---|---|---|---|
| **Python** | `>=3.12` | `3.12.3` | Backend runtime (FastAPI, SQLite, Alembic) |
| **pip** | `>=22.2` | `26.2.1` | Trình cài đặt package Python |
| **pip-tools** | `>=7.4.0` | `7.6.1` | Trình biên dịch lockfiles Python (`pip-compile`) |
| **diff-cover** | `>=10.4.1` | `10.6.0` | Đối chiếu report coverage với Git diff |
| **Node.js** | `>=20.19.0` (LTS) | `v22.23.2` | Trình chạy build/lint/test frontend |
| **npm** | `>=10.0.0` | `12.0.2` | Quản lý package frontend |
| **@vitest/coverage-v8** | `^5.0.2` | `5.0.2` | Sinh LCOV trong cùng lần chạy Vitest |
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
     - `@vitest/coverage-v8`: `^5.0.2` (dev-only, MIT; không vào production bundle)

2. **Backend**:
   - Khai báo tại `pyproject.toml` ở project root theo chuẩn PEP 621.
   - Lockfiles chuẩn được sinh bởi `pip-tools`:
     - `requirements.lock`: Runtime dependencies tối thiểu cho backend (FastAPI, Pydantic, SQLAlchemy, Alembic, Uvicorn, HTTPX).
     - `requirements-dev.lock`: Đầy đủ dependencies cho phát triển và kiểm thử (bổ sung Ruff, Mypy, Pytest, Pytest-cov, Pip-tools và diff-cover 10.6.0 Apache-2.0).
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
   pip-compile --allow-unsafe --extra=dev --output-file=requirements-dev.lock pyproject.toml
   ```
   *Không chỉnh sửa các file `.lock` bằng tay.*

`--allow-unsafe` ở dev lock là fail-closed supply-chain evidence, không phải cho phép package nguy hiểm: nó buộc `pip` và `setuptools` mà `pip-tools` cần phải xuất hiện với version pin thực thay vì comment mơ hồ. Điều này ngăn dependency scanner diễn giải sai comment unsafe thành một package/version giả và bảo đảm hai bootstrap tool cũng được audit.

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
- Mục tiêu quét mặc định: `files = ["backend", "scripts/check_constraints.py"]`.
- Không sử dụng bất kỳ suppression nào (`# type: ignore`).
- Lệnh kiểm tra:
  ```bash
  python -m mypy backend/tests/test_toolchain.py
  python -m mypy backend
  ```

### 6.3. Pytest & Pytest-cov (Test Runner & Coverage)
- Cấu hình tại `[tool.pytest.ini_options]`, `[tool.coverage.run]`, `[tool.coverage.report]`, `[tool.coverage.xml]`.
- Tự động đo coverage cho Python application/tooling dưới project root, loại trừ test code, và xuất báo cáo `coverage.xml` (chuẩn Cobertura XML) sau mỗi lần chạy suite.
- Tuyệt đối không cho phép ghi đè exit code khi không có test (`no no-tests pass override`).
- Lệnh kiểm tra:
  ```bash
  python -m pytest backend/tests/test_toolchain.py -q
  python -m pytest
  ```

### 6.4. Trạng thái sau T003/T053

- `backend/app`, migrations và `scripts/check_constraints.py` nằm trong report Python; `backend/tests` và `scripts/tests` bị loại để số đo phản ánh application/tooling code.
- Focused suite T053 đo trực tiếp `scripts/check_constraints.py`; không dùng coverage của test files làm bằng chứng.

## 7. Changed coverage và quality floor (T053)

### 7.1. Report và dependency

- `npm run test:frontend:coverage` chạy Vitest đúng một lần với V8 provider và sinh `htmlcov/frontend/lcov.info`; cấu hình này theo [Vitest coverage guide](https://vitest.dev/guide/coverage) và [coverage reporter reference](https://vitest.dev/config/coverage#coverage-reporter).
- `python -m pytest` chạy pytest-cov đúng một lần và sinh `coverage.xml`.
- `npm run coverage:check` đọc lại hai artifact trên; report thiếu, rỗng, không parse được hoặc source thay đổi không có measurement đều trả nonzero. Checker dùng diff-cover theo [upstream diff/fail-under contract](https://github.com/Bachmann1234/diff_cover#readme), đồng thời tự kiểm tra combined LCOV/XML để tránh đường false-green khi report không có dòng liên quan.
- Hai dependency đều dev-only: `@vitest/coverage-v8` 5.0.2 (MIT) và `diff-cover` 10.6.0 (Apache-2.0). Chúng không làm tăng runtime hoặc frontend production bundle.

### 7.2. Threshold và task baseline

- Changed executable lines phải đạt tối thiểu `80.0%`.
- Baseline tổng đầu tiên đo ngày 29/09/2026 là `86.70%`, kết hợp line entries từ cùng report run: frontend V8 báo `50.00%` lines và Python suite báo `88%` tổng quan. Ratchet cho phép giảm tối đa `0.5` điểm phần trăm.
- Base ref mặc định là local `main`. Khi làm trên stacked branch/worktree chưa merge, đặt `QUALITY_BASE_REF=<task-start-commit>` để so với đúng task baseline; thiếu merge base là exit code 2, không phải PASS.

### 7.3. Floor guard và exit code

- `npm run floor:check` kiểm tra tracked/staged/unstaged/untracked diff; repository chưa có HEAD được coi là baseline rỗng để vẫn quét code mới.
- Guard chặn suppression, stub, skip/todo test, xóa test/assertion, exception mới và threshold bị hạ. Findings chỉ in rule + path + line, không in nội dung dòng khớp.
- Exit `0`: clean; exit `1`: vi phạm; exit `2`: không thể tạo verdict đáng tin (`SETUP_PENDING`/configuration error).
- `check:fast` nối secret scan của T063 sau các check nhanh; `check:task:active` nối cả ba security scan sau coverage. `check:task` và `check:full` vẫn cố ý kết thúc exit 2 với `SETUP_PENDING` cho T062 sau khi các gate đang hoạt động chạy xong. Finding thật hoặc tool/database không dùng được luôn giữ exit nonzero, không được báo là PASS.

### 7.4. Commands

```bash
npm run format:check
npm run floor:check
npm run test:frontend:coverage
python -m pytest
npm run coverage:check
```

## 8. Security scan gates (T063)

### 8.1. Phiên bản, nguồn và install boundary

| Tool | Pin | Nguồn/giấy phép | Vai trò và impact |
|---|---:|---|---|
| Gitleaks | `8.30.1` | [GitHub Release chính thức](https://github.com/gitleaks/gitleaks/releases/tag/v8.30.1), MIT | CLI ngoài app; quét working tree, staged và history. Linux x64 archive SHA-256 `551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb`. |
| Semgrep CE | `1.178.0` | [GitHub Release chính thức](https://github.com/semgrep/semgrep/releases/tag/v1.178.0), LGPL-2.1-or-later | CLI development-only cài trong venv riêng; không thêm package/runtime frontend/backend. Ruleset `vocabulary.*` nằm bất biến trong `scripts/security_checks.py`; không gọi registry mutable và `--metrics off`. |
| OSV-Scanner | `2.6.0` | [GitHub Release chính thức](https://github.com/google/osv-scanner/releases/tag/v2.6.0), Apache-2.0 | Binary ngoài app; chỉ đọc ba lockfile chuẩn và truy vấn OSV database, không sửa dependency. Linux amd64 SHA-256 `ca69b3d3cd08f889a49dc0a383122f71cc528b83803671df5fd874d97485b108`. |

Gitleaks dùng các mode `dir`, `git --staged` và `git --log-opts=HEAD` theo [CLI upstream](https://github.com/gitleaks/gitleaks#usage); mode `dir` luôn chạy nên repository chưa có HEAD và file untracked vẫn được quét, còn history verdict chỉ phụ thuộc lịch sử reachable từ HEAD hiện tại chứ không phụ thuộc nhánh/worktree khác trên máy. Semgrep dùng JSON output, `--strict`, `--oss-only`, `--no-rewrite-rule-ids` và tắt metrics theo [CLI reference](https://docs.semgrep.dev/cli-reference). OSV dùng `scan source --format=json` với lockfile chỉ định rõ theo [source-scan guide](https://google.github.io/osv-scanner/usage/scan-source) và phân biệt result/setup error theo [return-code contract](https://google.github.io/osv-scanner/output/#return-codes).

Công thức cài đặt phải giữ tool ngoài dependency/runtime của ứng dụng. Tải Gitleaks/OSV từ release asset đúng phiên bản, kiểm tra SHA-256 trước khi giải nén/chạy; cài `semgrep==1.178.0` vào virtual environment dành riêng cho scanner. Có thể trỏ binary bằng `GITLEAKS_BIN`, `SEMGREP_BIN`, `OSV_SCANNER_BIN`. Wrapper kiểm tra exact version trước mỗi scan và trả `SETUP_FAILED` nếu thiếu/sai phiên bản; không tự tải tool, không chạy install script và không tự nâng dependency.

### 8.2. Verdict, privacy và report

- `npm run security:secrets`: Gitleaks `--redact=100`; leak exit được tách thành code `3` để code `1` còn biểu thị scanner error. Report tạm bị xóa sau parse; artifact `htmlcov/security/gitleaks.json` chỉ giữ tool/version/verdict và `rule`, `path`, `severity`, `scope`.
- `npm run security:code`: Semgrep chạy ruleset local versioned cho dynamic execution và `subprocess(..., shell=True)`. `ERROR` không có metadata được map thành high; impact high/critical chặn, severity lạ map `unknown` và chặn để cần triage.
- `npm run security:deps`: OSV quét `package-lock.json`, `requirements.lock`, `requirements-dev.lock`; CVSS v3 được phân loại critical `>=9.0`, high `>=7.0`, medium `>=4.0`, còn advisory không có severity parse được là `unknown` và chặn. Wrapper không có remediation/force-upgrade path.
- Exit `0` là verdict clean theo policy; exit `1` là finding chặn; exit `2` là tool/version/config/network/database/report không tạo được verdict đáng tin. Stdout/stderr thô từ scanner không được chuyển tiếp để tránh làm lộ secret hoặc source line.

### 8.3. Verification Linux ngày 30/09/2026

- Focused suite: 20 tests pass, bao gồm report redaction, no-HEAD/untracked, staged/current-HEAD history scopes, high/critical/unknown, CVSS v3, scanner crash, OSV network failure, missing tool, CLI dispatch, exact-version mismatch và explicit fixed setuptools pin. Full Python suite đạt 78 tests; changed coverage 88,98% và combined total 87,42% vượt ratchet.
- Negative probes với binary thật: secret sentinel tổng hợp trong repo tạm no-HEAD trả exit `1`, report/transcript không chứa sentinel; `eval(input())` trả Semgrep critical với rule ID ổn định và exit `1`.
- Owner phê duyệt remediation scope: hai false-positive Markdown fixture/prose được đổi sang placeholder/câu tương đương không đổi contract; dev lock được regenerate bằng `pip-compile --allow-unsafe`, chỉ thêm `pip==26.2.1` và `setuptools==84.0.0`, không force-upgrade hay đổi package version khác. Clean venv install đạt `pip check` và setuptools 84.0.0.
- `npm run security:secrets`, `security:code`, `security:deps`, `check:fast` và `check:task:active` đều exit `0`; ba report có 0 findings. `check:task`/`check:full` vẫn kết thúc `SETUP_PENDING` sau các active gates vì T062 chưa hoàn tất, không phải failure của T063.

## 9. Trạng thái kiểm chứng các nhiệm vụ Toolchain

- **T001 (Hoàn thành)**: Thiết lập lockfiles (`requirements.lock`, `requirements-dev.lock`, `package-lock.json`), quy tắc `.gitignore`, `README.md` và `docs/toolchain.md`.
- **T058 (Hoàn thành)**: Thiết lập Python quality gates (Ruff, Mypy strict, Pytest runner và Cobertura XML coverage artifact). Runner phát hiện test thật, negative probes xác nhận báo lỗi đúng exit code khi assertion/import/collection/type/lint thất bại.
- **T002/T003/T004/T005 (Hoàn thành)**: Frontend runner/build, backend skeleton, React shell và storage migration có evidence trong task cards tương ứng.
- **T053 (Hoàn thành)**: Changed coverage, total ratchet và floor guard được kiểm chứng.
- **T063 (Hoàn thành)**: Pinned scanner wrappers, redacted reports, severity gates, negative probes, no-HEAD/staged/current-history scopes và dependency lock audit đều có executable evidence; ba security commands clean.
- **T062 (Chưa chạy)**: Architecture gate vẫn `SETUP_PENDING` đúng owner/dependencies.

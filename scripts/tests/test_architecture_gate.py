"""Exercise the actual architecture tools against isolated source fixtures."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
FRONTEND = [
    str(REPO / "node_modules/.bin/depcruise"),
    "--config",
    ".dependency-cruiser.cjs",
    "--output-type",
    "err",
    "frontend/src",
]
BACKEND = [
    str(Path(sys.executable).with_name("lint-imports.exe" if os.name == "nt" else "lint-imports")),
    "--config",
    "pyproject.toml",
    "--no-cache",
]


def run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    environment = {**os.environ, "PYTHONPATH": str(cwd), "NO_COLOR": "1"}
    return subprocess.run(
        command, cwd=cwd, env=environment, capture_output=True, text=True, timeout=60, check=False
    )


def write(root: Path, name: str, source: str) -> None:
    target = root / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source, encoding="utf-8")


def assert_clean(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, result.stdout + result.stderr


def assert_broken(result: subprocess.CompletedProcess[str], rule: str) -> None:
    assert result.returncode != 0, result.stdout + result.stderr
    assert rule in result.stdout + result.stderr


@pytest.fixture
def frontend(tmp_path: Path) -> Path:
    shutil.copyfile(REPO / ".dependency-cruiser.cjs", tmp_path / ".dependency-cruiser.cjs")
    shutil.copyfile(REPO / "tsconfig.json", tmp_path / "tsconfig.json")
    (tmp_path / "node_modules").symlink_to(REPO / "node_modules", target_is_directory=True)
    write(tmp_path, "frontend/src/shared/api/generated.ts", "export interface DTO { id: string }\n")
    write(tmp_path, "frontend/src/shared/api/port.ts", "export interface Port { read(): string }\n")
    write(
        tmp_path,
        "frontend/src/app/view.ts",
        'import type { DTO } from "../shared/api/generated";\n'
        'import type { Port } from "../shared/api/port";\n'
        'import type { ReactNode } from "react";\n'
        "export type View = { dto: DTO; port: Port; child: ReactNode };\n",
    )
    return tmp_path


@pytest.fixture
def backend(tmp_path: Path) -> Path:
    shutil.copyfile(REPO / "pyproject.toml", tmp_path / "pyproject.toml")
    write(tmp_path, "backend/__init__.py", "")
    for layer in ("platform", "application", "http", "adapters", "persistence"):
        write(tmp_path, f"backend/app/{layer}/module.py", "VALUE = 1\n")
    write(tmp_path, "backend/app/main.py", "VALUE = 1\n")
    write(
        tmp_path,
        "backend/app/application/module.py",
        "from backend.app.platform.module import VALUE\n",
    )
    return tmp_path


def test_real_frontend() -> None:
    assert_clean(run(FRONTEND, REPO))


def test_real_backend() -> None:
    result = run(BACKEND, REPO)
    assert_clean(result)
    assert "0 broken" in result.stdout


def test_backend_graph_covers_every_application_source() -> None:
    # Grimp is import-linter's analyzer. Check discovery, not import relationships.
    result = run(
        [
            sys.executable,
            "-c",
            "import grimp, json; "
            "print(json.dumps(sorted(grimp.build_graph('backend.app', cache_dir=None).modules)))",
        ],
        REPO,
    )
    assert_clean(result)
    expected = {
        ".".join(path.relative_to(REPO).with_suffix("").parts).removesuffix(".__init__")
        for path in (REPO / "backend/app").rglob("*.py")
    }
    assert expected, "Missing backend architecture source"
    assert expected <= set(json.loads(result.stdout)), "Backend source omitted from import graph"


def test_frontend_graph_covers_every_typescript_source() -> None:
    command = list(FRONTEND)
    command[command.index("--output-type") + 1] = "json"
    result = run(command, REPO)
    assert_clean(result)
    analyzed = {module["source"] for module in json.loads(result.stdout)["modules"]}
    expected = {
        path.relative_to(REPO).as_posix()
        for path in (REPO / "frontend/src").rglob("*")
        if path.is_file() and path.suffix in {".ts", ".tsx"}
    }
    assert expected, "Missing frontend architecture source"
    assert expected <= analyzed, "Frontend source omitted from dependency graph"


@pytest.mark.parametrize(
    ("target", "rule"),
    [
        ("backend/app/secret.ts", "frontend-no-server"),
        ("server/config.ts", "frontend-no-server"),
        ("frontend/src/shared/server.ts", "frontend-no-server"),
        ("frontend/src/shared/secret.ts", "frontend-no-credentials"),
        ("frontend/src/shared/proxy-key.ts", "frontend-no-credentials"),
        ("frontend/src/persistence/database.ts", "frontend-no-sql"),
    ],
)
def test_frontend_forbidden_import(frontend: Path, target: str, rule: str) -> None:
    write(frontend, target, "export interface Private { value: string }\n")
    relative = os.path.relpath(frontend / target, frontend / "frontend/src/app").replace("\\", "/")
    write(
        frontend,
        "frontend/src/app/view.ts",
        f'import type {{ Private }} from "{relative.removesuffix(".ts")}";\n'
        "export type View = Private;\n",
    )
    assert_broken(run(FRONTEND, frontend), rule)


def test_allowed_react_shared_api_and_type_only_port(frontend: Path) -> None:
    assert_clean(run(FRONTEND, frontend))


@pytest.mark.parametrize(
    ("specifier", "rule"),
    [("node:fs", "frontend-no-server-builtins"), ("better-sqlite3", "frontend-no-sql")],
)
def test_forbidden_server_or_sql_package(frontend: Path, specifier: str, rule: str) -> None:
    write(frontend, "frontend/src/app/view.ts", f'import "{specifier}";\n')
    assert_broken(run(FRONTEND, frontend), rule)


def test_typescript_cycle(frontend: Path) -> None:
    write(frontend, "frontend/src/app/a.ts", 'import "./b";\nexport const a = 1;\n')
    write(frontend, "frontend/src/app/b.ts", 'import "./a";\nexport const b = 1;\n')
    assert_broken(run(FRONTEND, frontend), "frontend-no-cycles")


def test_type_only_cycle_is_still_checked(frontend: Path) -> None:
    write(
        frontend,
        "frontend/src/app/a.ts",
        'import type { B } from "./b";\nexport interface A { other: B }\n',
    )
    write(
        frontend,
        "frontend/src/app/b.ts",
        'import type { A } from "./a";\nexport interface B { other: A }\n',
    )
    assert_broken(run(FRONTEND, frontend), "frontend-no-cycles")


def test_generated_dto_is_type_only_and_exact(frontend: Path) -> None:
    assert_clean(run(FRONTEND, frontend))
    write(frontend, "frontend/src/app/view.ts", 'import "../shared/api/generated";\n')
    assert_broken(run(FRONTEND, frontend), "generated-dto-types-only")
    write(frontend, "frontend/src/shared/api/not-generated.ts", "export const value = 1;\n")
    write(frontend, "frontend/src/app/view.ts", 'import "../shared/api/not-generated";\n')
    assert_clean(run(FRONTEND, frontend))
    write(frontend, "server/private.ts", "export const value = 1;\n")
    write(
        frontend,
        "frontend/src/shared/api/not-generated.ts",
        'import "../../../../server/private";\n',
    )
    assert_broken(run(FRONTEND, frontend), "frontend-no-server")
    # Even the exact artifact cannot smuggle a backend dependency into the graph.
    write(
        frontend, "frontend/src/shared/api/generated.ts", 'import "../../../../server/private";\n'
    )
    assert_broken(run(FRONTEND, frontend), "frontend-no-server")


@pytest.mark.parametrize(
    ("source", "target", "rule"),
    [
        ("application", "http", "Application cannot depend on HTTP or composition"),
        ("platform", "http", "Platform remains a leaf abstraction"),
        ("platform", "application", "Platform remains a leaf abstraction"),
        ("platform", "adapters", "Platform remains a leaf abstraction"),
        ("platform", "persistence", "Platform remains a leaf abstraction"),
        ("adapters", "persistence", "Concrete adapters are independent"),
        ("persistence", "adapters", "Concrete adapters are independent"),
        ("http", "adapters", "HTTP uses application and platform contracts"),
    ],
)
def test_python_forbidden_import(backend: Path, source: str, target: str, rule: str) -> None:
    write(
        backend,
        f"backend/app/{source}/module.py",
        f"from backend.app.{target}.module import VALUE\n",
    )
    assert_broken(run(BACKEND, backend), rule)


def test_good_port_direction_and_namespace_descendants(backend: Path) -> None:
    assert not (backend / "backend/app/__init__.py").exists()
    assert not (backend / "backend/app/platform/__init__.py").exists()
    assert_clean(run(BACKEND, backend))


def test_sibling_concrete_adapters_cannot_coordinate(backend: Path) -> None:
    write(backend, "backend/app/adapters/other.py", "VALUE = 1\n")
    write(
        backend, "backend/app/adapters/module.py", "from backend.app.adapters.other import VALUE\n"
    )
    assert_broken(run(BACKEND, backend), "Concrete adapters are independent")


def test_application_may_coordinate_adapter_through_http(backend: Path) -> None:
    write(
        backend,
        "backend/app/application/module.py",
        "from backend.app.adapters.module import VALUE\n",
    )
    write(
        backend, "backend/app/http/module.py", "from backend.app.application.module import VALUE\n"
    )
    assert_clean(run(BACKEND, backend))


def test_indirect_application_to_http_is_forbidden(backend: Path) -> None:
    write(
        backend,
        "backend/app/application/module.py",
        "from backend.app.platform.module import VALUE\n",
    )
    write(backend, "backend/app/platform/module.py", "from backend.app.http.module import VALUE\n")
    assert_broken(run(BACKEND, backend), "Application cannot depend on HTTP or composition")


def test_python_cycle(backend: Path) -> None:
    write(backend, "backend/app/application/a.py", "from backend.app.application import b\n")
    write(backend, "backend/app/application/b.py", "from backend.app.application import a\n")
    assert_broken(run(BACKEND, backend), "Backend ownership is acyclic")


def test_backend_cannot_import_frontend(backend: Path) -> None:
    write(backend, "backend/app/application/module.py", "import frontend\n")
    assert_broken(run(BACKEND, backend), "Backend cannot import frontend")


@pytest.mark.parametrize("tool", ["frontend", "backend"])
def test_missing_configuration_fails(frontend: Path, backend: Path, tool: str) -> None:
    command = list(FRONTEND if tool == "frontend" else BACKEND)
    command[command.index("--config") + 1] = "missing-config"
    result = run(command, frontend if tool == "frontend" else backend)
    assert result.returncode != 0, result.stdout + result.stderr


@pytest.mark.parametrize("tool", ["frontend", "backend"])
def test_malformed_configuration_fails(frontend: Path, backend: Path, tool: str) -> None:
    root = frontend if tool == "frontend" else backend
    config = ".dependency-cruiser.cjs" if tool == "frontend" else "pyproject.toml"
    write(root, config, "invalid configuration [\n")
    result = run(FRONTEND if tool == "frontend" else BACKEND, root)
    assert result.returncode != 0, result.stdout + result.stderr


@pytest.mark.parametrize("tool", ["frontend", "backend"])
def test_unanalyzable_source_fails(frontend: Path, backend: Path, tool: str) -> None:
    if tool == "frontend":
        write(frontend, "frontend/src/app/view.ts", 'import "./missing-contract";\n')
        assert_broken(run(FRONTEND, frontend), "frontend-no-unresolved")
    else:
        write(backend, "backend/app/application/module.py", "this is invalid Python !!!\n")
        result = run(BACKEND, backend)
        assert result.returncode != 0, result.stdout + result.stderr


def test_empty_frontend_cannot_pass(tmp_path: Path) -> None:
    shutil.copyfile(REPO / ".dependency-cruiser.cjs", tmp_path / ".dependency-cruiser.cjs")
    (tmp_path / "frontend/src").mkdir(parents=True)
    assert_broken(run(FRONTEND, tmp_path), "architecture source")


def test_directory_named_like_typescript_is_not_source(tmp_path: Path) -> None:
    shutil.copyfile(REPO / ".dependency-cruiser.cjs", tmp_path / ".dependency-cruiser.cjs")
    shutil.copyfile(REPO / "tsconfig.json", tmp_path / "tsconfig.json")
    (tmp_path / "node_modules").symlink_to(REPO / "node_modules", target_is_directory=True)
    (tmp_path / "frontend/src/fake.ts").mkdir(parents=True)
    assert_broken(run(FRONTEND, tmp_path), "architecture source")


def test_missing_backend_target_fails(backend: Path) -> None:
    (backend / "backend/app/application/module.py").unlink()
    assert run(BACKEND, backend).returncode != 0


def test_aggregate_scripts_use_real_gate() -> None:
    scripts = json.loads((REPO / "package.json").read_text(encoding="utf-8"))["scripts"]
    for aggregate in ("check:task", "check:full"):
        assert "npm run architecture:check" in scripts[aggregate]
        assert "pending T062" not in scripts[aggregate]
    assert "architecture:frontend" in scripts["architecture:check"]
    assert "architecture:backend" in scripts["architecture:check"]

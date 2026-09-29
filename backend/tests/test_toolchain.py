"""Toolchain verification and test runner smoke tests."""

import importlib
import sys
from pathlib import Path


def test_python_version() -> None:
    """Verify runtime Python meets or exceeds the required 3.12 specification."""
    assert sys.version_info >= (3, 12), f"Python 3.12+ required, got: {sys.version_info}"


def test_conftest_fixtures(project_root: Path, python_version_info: tuple[int, int]) -> None:
    """Verify pytest conftest discovery loads fixtures correctly."""
    assert project_root.is_dir()
    assert (project_root / "pyproject.toml").is_file()
    assert python_version_info >= (3, 12)


def test_locked_dependencies_importable() -> None:
    """Verify core dependencies pinned in lockfiles can be imported successfully."""
    core_modules = [
        "fastapi",
        "pydantic",
        "sqlalchemy",
        "alembic",
        "uvicorn",
        "httpx",
        "pytest",
        "pytest_cov",
        "mypy",
        "ruff",
    ]
    for module_name in core_modules:
        mod = importlib.import_module(module_name)
        assert mod is not None, f"Module {module_name} could not be imported"


def test_pyproject_configuration_exists(project_root: Path) -> None:
    """Verify pyproject.toml contains required quality tool configurations."""
    pyproject_path = project_root / "pyproject.toml"
    assert pyproject_path.is_file()
    content = pyproject_path.read_text(encoding="utf-8")
    assert "[tool.pytest.ini_options]" in content
    assert "[tool.ruff]" in content
    assert "[tool.mypy]" in content
    assert "[tool.coverage.run]" in content

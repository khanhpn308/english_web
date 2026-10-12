"""T056: deterministic inventory and opt-in Windows one-directory package builder.

Build is Windows-only and requires an independently pinned PyInstaller tool.
Verify is file-only and never executes an installed application or real AI provider.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DIST = REPO / "packaging" / "dist" / "VocabularyApp"
MANIFEST_NAME = "package-manifest.json"
PYINSTALLER_VERSION = "6.16.0"
APP_VERSION = "0.1.0"
BANNED_COMPONENTS = frozenset({
    ".env", ".git", ".venv", "__pycache__", "node_modules", "tests", "pytest",
    "mypy", "ruff", "pip", "pip_tools", "setuptools", "semgrep", "gitleaks",
    "screenshots", "secrets", "user_data", "site-packages",
})
BANNED_SUFFIXES = (".db", ".sqlite", ".sqlite3", ".db-wal", ".db-shm",
                   ".dpapi", ".pem", ".key", ".token", ".secret")
REQUIRED = (
    "VocabularyApp.exe", "frontend/dist/index.html", "frontend/dist/bootstrap.html",
    "alembic.ini", "backend/migrations/env.py",
)


class PackageRefused(RuntimeError):
    """Non-sensitive failure category; never emit local file content."""


def _safe_path(file: Path, root: Path) -> str:
    relative = file.relative_to(root).as_posix()
    components = [part.casefold() for part in file.relative_to(root).parts]
    if (
        any(part in BANNED_COMPONENTS for part in components)
        or any(part.endswith(BANNED_SUFFIXES) for part in components)
        or any(part.startswith(".env") for part in components)
        or "\\" in relative or ":" in relative
    ):
        raise PackageRefused("UNEXPECTED_OR_SECRET_ARTIFACT")
    info = file.lstat()
    if (
        not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
        or getattr(info, "st_file_attributes", 0) & 0x400
    ):
        raise PackageRefused("UNSAFE_PACKAGE_ENTRY")
    return relative


def inventory(root: Path) -> dict[str, str]:
    if not root.is_dir() or root.is_symlink():
        raise PackageRefused("MISSING_PACKAGE")
    records: dict[str, str] = {}
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in dirs:
            path = Path(directory) / name
            info = path.lstat()
            if (
                not stat.S_ISDIR(info.st_mode) or path.is_symlink()
                or getattr(info, "st_file_attributes", 0) & 0x400
            ):
                raise PackageRefused("UNSAFE_PACKAGE_ENTRY")
            if name.casefold() in BANNED_COMPONENTS:
                raise PackageRefused("UNEXPECTED_OR_SECRET_ARTIFACT")
        for name in files:
            item = Path(directory) / name
            if item.name == MANIFEST_NAME and item.parent == root:
                continue
            relative = _safe_path(item, root)
            checksum = hashlib.sha256()
            with item.open("rb") as stream:
                while block := stream.read(1024 * 1024):
                    checksum.update(block)
            records[relative] = checksum.hexdigest()
    if not all(name in records for name in REQUIRED):
        raise PackageRefused("INCOMPLETE_PACKAGE")
    # tzdata/zoneinfo cannot rely on a system-wide IANA database on Windows.
    if not any("tzdata/zoneinfo/" in name.replace("\\", "/").casefold()
               for name in records):
        raise PackageRefused("TIMEZONE_DATA_MISSING")
    return dict(sorted(records.items()))


def write_manifest(root: Path, *, source_revision: str) -> dict[str, object]:
    if not re.fullmatch(r"[a-f0-9]{40}", source_revision):
        raise PackageRefused("INVALID_SOURCE_REVISION")
    document: dict[str, object] = {
        "format": 1, "app_version": APP_VERSION,
        "pyinstaller_version": PYINSTALLER_VERSION,
        "git_source_revision": source_revision, "sha256": inventory(root),
    }
    target = root / MANIFEST_NAME
    if target.exists():
        raise PackageRefused("MANIFEST_ALREADY_EXISTS")
    with target.open("x", encoding="utf-8") as stream:
        json.dump(document, stream, indent=2, sort_keys=True)
        stream.write("\n")
    return document


def verify(root: Path = DIST) -> dict[str, object]:
    try:
        manifest = json.loads((root / MANIFEST_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise PackageRefused("MANIFEST_UNAVAILABLE") from None
    if (
        not isinstance(manifest, dict)
        or set(manifest) != {
            "format", "app_version", "pyinstaller_version", "git_source_revision", "sha256"
        }
        or manifest["format"] != 1
        or manifest["app_version"] != APP_VERSION
        or manifest["pyinstaller_version"] != PYINSTALLER_VERSION
        or not isinstance(manifest["git_source_revision"], str)
        or not re.fullmatch(r"[a-f0-9]{40}", manifest["git_source_revision"])
        or not isinstance(manifest["sha256"], dict)
        or manifest["sha256"] != inventory(root)
    ):
        raise PackageRefused("PACKAGE_MANIFEST_MISMATCH")
    return {
        "status": "PACKAGE_INVENTORY_VERIFIED_RUNTIME_UNTESTED",
        "app_version": APP_VERSION, "files": len(manifest["sha256"]),
        "git_source_revision": manifest["git_source_revision"],
    }


def _version_guard() -> None:
    if os.name != "nt" or sys.platform != "win32":
        raise PackageRefused("WINDOWS_BUILD_REQUIRED")
    if sys.version_info[:2] != (3, 12):
        raise PackageRefused("PYTHON_VERSION_NOT_PINNED")
    try:
        if importlib.metadata.version("pyinstaller") != PYINSTALLER_VERSION:
            raise PackageRefused("PYINSTALLER_VERSION_MISMATCH")
        if importlib.metadata.version("tzdata") == "":
            raise PackageRefused("TIMEZONE_DATA_MISSING")
        import tkinter
        tkinter.Tcl()
    except (ImportError, importlib.metadata.PackageNotFoundError):
        raise PackageRefused("MISSING_BUILD_DEPENDENCY") from None


def build() -> dict[str, object]:
    _version_guard()
    if DIST.exists() or DIST.is_symlink():
        raise PackageRefused("DIST_ALREADY_EXISTS")
    static = REPO / "frontend" / "dist"
    for required in ("index.html", "bootstrap.html"):
        if not (static / required).is_file():
            raise PackageRefused("FRONTEND_BUILD_MISSING")
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO, check=True,
        capture_output=True, text=True, timeout=10,
    ).stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise PackageRefused("INVALID_SOURCE_REVISION")
    cmd = [
        sys.executable, "-m", "PyInstaller", "--onedir", "--windowed",
        "--contents-directory", ".", "--name", "VocabularyApp",
        "--distpath", str(REPO / "packaging" / "dist"),
        "--workpath", str(REPO / "packaging" / "build"),
        "--specpath", str(REPO / "packaging" / "build"),
        "--exclude-module", "uvloop",
        "--exclude-module", "pytest", "--exclude-module", "ruff",
        "--exclude-module", "mypy",
        "--hidden-import", "_tkinter", "--collect-submodules", "tkinter",
        "--collect-submodules", "backend.migrations.versions",
        "--collect-data", "tzdata",
        "--add-data", f"{static}:frontend/dist",
        "--add-data", f"{REPO / 'backend' / 'migrations'}:backend/migrations",
        "--add-data", f"{REPO / 'alembic.ini'}:.",
        str(REPO / "launcher" / "src" / "main.py"),
    ]
    subprocess.run(cmd, cwd=REPO, check=True, timeout=900)
    write_manifest(DIST, source_revision=revision)
    return verify(DIST)


def main() -> int:
    parser = argparse.ArgumentParser(description="T056 Windows package builder")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--build", action="store_true")
    group.add_argument("--verify", action="store_true")
    options = parser.parse_args()
    try:
        result = build() if options.build else verify()
    except (PackageRefused, OSError, subprocess.SubprocessError):
        print("BLOCKED: PACKAGE_UNVERIFIED")
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

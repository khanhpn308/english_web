"""T056 deterministic packaging contract tests; synthetic inventory, no Windows run."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from packaging.build_windows import (
    PackageRefused,
    inventory,
    verify,
    write_manifest,
)


def _fixture(tmp_path: Path) -> Path:
    root = tmp_path / "bundle"
    for part in (
        "VocabularyApp.exe", "frontend/dist/index.html",
        "frontend/dist/bootstrap.html", "alembic.ini",
        "backend/migrations/env.py", "tzdata/zoneinfo/Asia/Bangkok",
    ):
        file = root / part
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(b"synthetic-build-artifact")
    return root


def test_manifest_is_deterministic_and_detects_tamper(tmp_path: Path) -> None:
    root = _fixture(tmp_path)
    expected = inventory(root)
    assert expected == inventory(root)
    source = "a" * 40
    manifest = write_manifest(root, source_revision=source)
    assert manifest["git_source_revision"] == source
    assert verify(root)["status"] == "PACKAGE_INVENTORY_VERIFIED_RUNTIME_UNTESTED"
    assert json.loads((root / "package-manifest.json").read_text()) == manifest
    (root / "frontend/dist/index.html").write_text("changed")
    with pytest.raises(PackageRefused, match="PACKAGE_MANIFEST_MISMATCH"):
        verify(root)


def test_secret_db_and_dev_dependencies_rejected(tmp_path: Path) -> None:
    root = _fixture(tmp_path)
    (root / "vocabulary.sqlite3").write_text("synthetic")
    with pytest.raises(PackageRefused, match="UNEXPECTED_OR_SECRET_ARTIFACT"):
        inventory(root)
    (root / "vocabulary.sqlite3").unlink()
    tests = root / "pytest"
    tests.mkdir()
    (tests / "test.py").write_text("fixture")
    with pytest.raises(PackageRefused, match="UNEXPECTED_OR_SECRET_ARTIFACT"):
        inventory(root)


def test_broken_manifest_and_missing_timezone_rejected(tmp_path: Path) -> None:
    root = _fixture(tmp_path)
    with pytest.raises(PackageRefused, match="MANIFEST_UNAVAILABLE"):
        verify(root)
    (root / "tzdata/zoneinfo/Asia/Bangkok").unlink()
    with pytest.raises(PackageRefused, match="TIMEZONE_DATA_MISSING"):
        inventory(root)


def test_missing_runtime_asset_is_not_a_valid_package(tmp_path: Path) -> None:
    root = _fixture(tmp_path)
    (root / "alembic.ini").unlink()
    with pytest.raises(PackageRefused, match="INCOMPLETE_PACKAGE"):
        inventory(root)


def test_manifest_cannot_be_rewritten_or_faked(tmp_path: Path) -> None:
    root = _fixture(tmp_path)
    with pytest.raises(PackageRefused, match="INVALID_SOURCE_REVISION"):
        write_manifest(root, source_revision="../invalid")
    write_manifest(root, source_revision="b" * 40)
    with pytest.raises(PackageRefused, match="MANIFEST_ALREADY_EXISTS"):
        write_manifest(root, source_revision="b" * 40)
    raw = json.loads((root / "package-manifest.json").read_text())
    raw["sha256"].pop("VocabularyApp.exe")
    (root / "package-manifest.json").write_text(json.dumps(raw))
    with pytest.raises(PackageRefused, match="PACKAGE_MANIFEST_MISMATCH"):
        verify(root)


def test_symlink_is_rejected(tmp_path: Path) -> None:
    root = _fixture(tmp_path)
    (root / "frontend/dist/index.html").unlink()
    (root / "frontend/dist/index.html").symlink_to(root / "VocabularyApp.exe")
    with pytest.raises(PackageRefused, match="UNSAFE_PACKAGE_ENTRY"):
        inventory(root)

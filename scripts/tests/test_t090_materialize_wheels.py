"""Executable coverage and adversarial regressions for exact T090 wheel materialization."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from scripts import t090_materialize_wheels as candidate


def wheel(directory: Path, name: str, version: str, *, tag: str = "py3-none-any") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}-{version}-{tag}.whl"
    path.write_bytes(f"synthetic:{name}:{version}:{tag}".encode())
    return path


def test_read_pins_requires_exact_unique_versions_and_supports_extras(tmp_path: Path) -> None:
    lock = tmp_path / "requirements.lock"
    lock.write_text("# frozen\ncoverage[toml]==7.16.2\ndemo_name==1.0.0  # version reason\n")
    assert candidate.read_pins(lock) == {"coverage": "7.16.2", "demo-name": "1.0.0"}
    for raw, message in (
        ("", "Empty"),
        ("demo>=1.0\n", "Unpinned"),
        ("demo==1.0\ndemo==1.0\n", "Duplicate"),
        ("--index-url=https://example.invalid\n", "Unpinned"),
    ):
        lock.write_text(raw)
        with pytest.raises(ValueError, match=message):
            candidate.read_pins(lock)


def test_wheel_lock_records_exact_bytes_and_denies_unexpected_artifacts(tmp_path: Path) -> None:
    directory = tmp_path / "wheels"
    output = tmp_path / "results" / "requirements-hashed.lock"
    record = wheel(directory, "demo_name", "1.0.0")
    expected = {"demo-name": "1.0.0"}
    assert candidate.materialize_wheel_lock(directory, output, expected) == expected
    lock_text = output.read_text()
    assert "NOT production approved" in lock_text
    assert hashlib.sha256(record.read_bytes()).hexdigest() in lock_text
    report = json.loads(output.with_suffix(".wheels.json").read_text())
    assert report["approved"] is False
    assert report["wheels"][0]["filename"] == record.name
    with pytest.raises(ValueError, match="versions"):
        candidate.materialize_wheel_lock(directory, output, {"demo-name": "2.0.0"})
    with pytest.raises(ValueError, match="missing"):
        candidate.materialize_wheel_lock(directory, output, {"other": "1.0.0"})
    with pytest.raises(ValueError, match="extra"):
        candidate.materialize_wheel_lock(directory, output, {})
    wheel(directory, "demo_name", "1.0.0", tag="py2.py3-none-any")
    with pytest.raises(ValueError, match="Duplicate"):
        candidate.materialize_wheel_lock(directory, output, None)
    for item in directory.glob("*.whl"):
        item.unlink()
    with pytest.raises(ValueError, match="empty"):
        candidate.materialize_wheel_lock(directory, output, None)


def test_wheel_downloader_forbids_sdists_and_uses_fixed_pip_arguments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commands: list[list[str]] = []

    def fake_run(argv: list[str], *, check: bool, timeout: int) -> None:
        assert check is True
        assert timeout == 900
        commands.append(argv)

    monkeypatch.setattr(candidate.subprocess, "run", fake_run)
    directory = tmp_path / "wheelhouse"
    candidate.download_wheels(directory, ["demo==1.0.0"])
    assert directory.is_dir()
    assert len(commands) == 1
    argv = commands[0]
    assert argv[:4] == [sys.executable, "-m", "pip", "download"]
    assert "--only-binary=:all:" in argv
    assert argv[-1] == "demo==1.0.0"
    assert "--no-index" not in argv


def test_wheel_cli_writes_separate_dev_and_semgrep_locks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "requirements-dev.lock").write_text("demo==1.0.0\n")
    out = tmp_path / "out"

    def fake_download(directory: Path, requirements: list[str]) -> None:
        if requirements == ["semgrep==1.178.0"]:
            wheel(directory, "semgrep", "1.178.0")
        else:
            assert requirements[:2] == ["--no-deps", "-r"]
            wheel(directory, "demo", "1.0.0")

    monkeypatch.setattr(candidate, "download_wheels", fake_download)
    monkeypatch.setattr(
        sys, "argv", ["wheel-materializer", "--root", str(root), "--output", str(out)]
    )
    assert candidate.main() == 0
    assert (out / "dev" / "requirements-hashed.lock").exists()
    assert "semgrep==1.178.0" in (out / "semgrep" / "requirements-hashed.lock").read_text()
    assert "PASS_NOT_APPROVED" in capsys.readouterr().out


def test_wheel_cli_fails_closed_on_missing_semgrep_and_wheel_download_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "requirements-dev.lock").write_text("demo==1.0.0\n")
    out = tmp_path / "out"
    monkeypatch.setattr(
        sys, "argv", ["wheel-materializer", "--root", str(root), "--output", str(out)]
    )

    def absent_semgrep(directory: Path, requirements: list[str]) -> None:
        if requirements == ["semgrep==1.178.0"]:
            wheel(directory, "wrong_package", "1.0.0")
        else:
            wheel(directory, "demo", "1.0.0")

    monkeypatch.setattr(candidate, "download_wheels", absent_semgrep)
    with pytest.raises(ValueError, match="Semgrep wheel not pinned"):
        candidate.main()
    assert "Semgrep wheel not pinned" in (out / "semgrep" / "BLOCKED.txt").read_text()

    def download_error(directory: Path, requirements: list[str]) -> None:
        if requirements == ["semgrep==1.178.0"]:
            raise subprocess.CalledProcessError(1, ["pip", "download"])
        wheel(directory, "demo", "1.0.0")

    monkeypatch.setattr(candidate, "download_wheels", download_error)
    with pytest.raises(subprocess.CalledProcessError):
        candidate.main()
    assert "Cannot admit binary-only" in (out / "semgrep" / "BLOCKED.txt").read_text()


def test_wheel_cli_denies_other_platforms(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        sys, "argv", ["wheel-materializer", "--root", str(tmp_path), "--output", str(tmp_path)]
    )
    monkeypatch.setattr(candidate.sys, "platform", "win32")
    with pytest.raises(SystemExit, match="Python 3.12 on Linux"):
        candidate.main()

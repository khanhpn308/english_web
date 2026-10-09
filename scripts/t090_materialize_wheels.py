"""Materialize exact Linux/Python wheel byte hashes for T090 candidate admission.

Candidate-only; running pip with a live package index does not establish
publisher identity or independent production trust.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

from packaging.utils import canonicalize_name, parse_wheel_filename

_PIN = re.compile(r"^([A-Za-z0-9_.-]+)(?:\\[[A-Za-z0-9_,.-]+\\])?==([A-Za-z0-9][A-Za-z0-9.!+_-]*)$")


def read_pins(path: Path) -> dict[str, str]:
    pins: dict[str, str] = {}
    for source in path.read_text(encoding="utf-8").splitlines():
        line = source.split("#", 1)[0].strip()
        if not line:
            continue
        match = _PIN.fullmatch(line)
        if match is None:
            raise ValueError(f"Unpinned or unsupported requirement: {line[:80]}")
        name = canonicalize_name(match.group(1))
        if name in pins:
            raise ValueError(f"Duplicate requirement: {name}")
        pins[name] = match.group(2)
    if not pins:
        raise ValueError("Empty requirements")
    return pins


def materialize_wheel_lock(
    wheel_dir: Path, output: Path, expected: dict[str, str] | None
) -> dict[str, str]:
    pins: dict[str, str] = {}
    records: list[dict[str, str]] = []
    for wheel in sorted(wheel_dir.glob("*.whl")):
        parsed_name, parsed_version, _, _ = parse_wheel_filename(wheel.name)
        name, version = canonicalize_name(parsed_name), str(parsed_version)
        if name in pins:
            raise ValueError(f"Duplicate wheel distributions: {name}")
        pins[name] = version
        records.append(
            {
                "name": name,
                "version": version,
                "filename": wheel.name,
                "sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
            }
        )
    if not records:
        raise ValueError("Wheelhouse is empty")
    if expected is not None and expected != pins:
        missing = sorted(set(expected) - set(pins))
        extra = sorted(set(pins) - set(expected))
        wrong = sorted(k for k in pins.keys() & expected.keys() if pins[k] != expected[k])
        raise ValueError(f"Wheel set mismatch: missing={missing}, extra={extra}, versions={wrong}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "# T090 candidate Linux/amd64 Python 3.12 wheel bytes, NOT production approved\\n"
        + "".join(f"{r['name']}=={r['version']} --hash=sha256:{r['sha256']}\\n" for r in records),
        encoding="utf-8",
    )
    output.with_suffix(".wheels.json").write_text(
        json.dumps({"schema_version": 1, "approved": False, "wheels": records}, indent=2) + "\n",
        encoding="utf-8",
    )
    return pins


def download_wheels(wheel_dir: Path, requirements: list[str]) -> None:
    wheel_dir.mkdir(parents=True, exist_ok=True)
    argv = [
        sys.executable,
        "-m",
        "pip",
        "download",
        "--disable-pip-version-check",
        "--only-binary=:all:",
        "--dest",
        str(wheel_dir),
        *requirements,
    ]
    # Do not use a shell, source builds or a fallback to unpinned artifacts.
    subprocess.run(argv, check=True, timeout=900)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root, output = args.root.resolve(), args.output.resolve()
    if sys.version_info[:2] != (3, 12) or sys.platform != "linux":
        raise SystemExit("T090: wheel materialization requires Python 3.12 on Linux")
    expected = read_pins(root / "requirements-dev.lock")
    dev = output / "dev"
    download_wheels(dev / "wheels", ["--no-deps", "-r", str(root / "requirements-dev.lock")])
    materialize_wheel_lock(dev / "wheels", dev / "requirements-hashed.lock", expected)
    # Separate Semgrep environment: don't silently overlay dev dependencies.
    semgrep = output / "semgrep"
    try:
        download_wheels(semgrep / "wheels", ["semgrep==1.178.0"])
        versions = materialize_wheel_lock(
            semgrep / "wheels", semgrep / "requirements-hashed.lock", None
        )
        if versions.get("semgrep") != "1.178.0":
            raise ValueError("Semgrep wheel not pinned")
    except (ValueError, subprocess.CalledProcessError) as error:
        (semgrep / "BLOCKED.txt").parent.mkdir(parents=True, exist_ok=True)
        (semgrep / "BLOCKED.txt").write_text(
            f"Cannot admit binary-only Semgrep wheel closure: {error}\\n",
            encoding="utf-8",
        )
        raise
    print("T090_CANDIDATE_WHEEL_MATERIALIZATION_PASS_NOT_APPROVED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

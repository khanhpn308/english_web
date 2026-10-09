#!/usr/bin/env python3
"""Pinned, fail-closed security scanner gates for T063."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any

EXIT_CLEAN = 0
EXIT_VIOLATION = 1
EXIT_SETUP = 2

GITLEAKS_VERSION = "8.30.1"
SEMGREP_VERSION = "1.178.0"
OSV_SCANNER_VERSION = "2.6.0"

BLOCKING_SEVERITIES = {"critical", "high", "unknown"}
Runner = Callable[[Sequence[str], Path], subprocess.CompletedProcess[str]]

SEMGREP_RULESET = """\
rules:
  - id: vocabulary.python.dynamic-code-execution
    message: Dynamic Python execution is forbidden at trust boundaries.
    severity: ERROR
    metadata:
      impact: CRITICAL
    languages: [python]
    pattern-either:
      - pattern: eval(...)
      - pattern: exec(...)
  - id: vocabulary.python.subprocess-shell
    message: subprocess shell execution can turn untrusted text into commands.
    severity: ERROR
    metadata:
      impact: HIGH
    languages: [python]
    patterns:
      - pattern: subprocess.$FUNC(..., shell=True, ...)
      - metavariable-regex:
          metavariable: $FUNC
          regex: ^(run|Popen|call|check_call|check_output)$
  - id: vocabulary.javascript.dynamic-code-execution
    message: Dynamic JavaScript execution is forbidden.
    severity: ERROR
    metadata:
      impact: CRITICAL
    languages: [javascript, typescript]
    pattern: eval(...)
"""


@dataclass(frozen=True)
class Finding:
    rule: str
    path: str
    severity: str
    scope: str


@dataclass(frozen=True)
class GateResult:
    exit_code: int
    report_path: Path
    findings: tuple[Finding, ...]


class SetupFailure(RuntimeError):
    """The scanner could not produce a trustworthy verdict."""


def run_command(command: Sequence[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            list(command),
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as error:
        raise SetupFailure(f"{Path(command[0]).name} is unavailable") from error


def _clean_rule(value: object) -> str:
    candidate = str(value)[:160]
    cleaned = re.sub(r"[^A-Za-z0-9._:/@+-]", "_", candidate)
    return cleaned or "unknown-rule"


def _clean_path(value: object, repo: Path) -> str:
    raw = str(value).replace("\\", "/").replace("\r", "_").replace("\n", "_")
    root = repo.resolve().as_posix().rstrip("/")
    if raw.startswith(root + "/"):
        raw = raw[len(root) + 1 :]
    elif Path(raw).is_absolute():
        raw = PurePosixPath(raw).name
    while raw.startswith("./"):
        raw = raw[2:]
    cleaned = re.sub(r"[^A-Za-z0-9._/@+() -]", "_", raw[:240])
    return cleaned or "unknown-path"


def _as_mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def parse_gitleaks_report(payload: object, repo: Path, scope: str) -> list[Finding]:
    if not isinstance(payload, list):
        raise SetupFailure("gitleaks returned an invalid JSON report")
    return [
        Finding(
            rule=_clean_rule(item.get("RuleID", "unknown-rule")),
            path=_clean_path(item.get("File", "unknown-path"), repo),
            severity="critical",
            scope=scope,
        )
        for raw_item in payload
        if (item := _as_mapping(raw_item))
    ]


def _semgrep_severity(extra: Mapping[str, Any]) -> str:
    metadata = _as_mapping(extra.get("metadata"))
    if "impact" in metadata:
        impact = str(metadata["impact"]).lower()
        return impact if impact in {"critical", "high", "medium", "low"} else "unknown"
    fallback = {"error": "high", "warning": "medium", "info": "low"}
    return fallback.get(str(extra.get("severity", "")).lower(), "unknown")


def parse_semgrep_report(payload: object, repo: Path) -> list[Finding]:
    report = _as_mapping(payload)
    if not report or not isinstance(report.get("results", []), list):
        raise SetupFailure("semgrep returned an invalid JSON report")
    if _as_list(report.get("errors")):
        raise SetupFailure("semgrep reported scan errors")
    findings: list[Finding] = []
    for raw_result in _as_list(report.get("results")):
        result = _as_mapping(raw_result)
        extra = _as_mapping(result.get("extra"))
        findings.append(
            Finding(
                rule=_clean_rule(result.get("check_id", "unknown-rule")),
                path=_clean_path(result.get("path", "unknown-path"), repo),
                severity=_semgrep_severity(extra),
                scope="code",
            )
        )
    return findings


def _round_up_one_decimal(value: float) -> float:
    return math.ceil((value - 1e-10) * 10.0) / 10.0


def _cvss_v3_score(vector: str) -> float | None:
    if not vector.startswith(("CVSS:3.0/", "CVSS:3.1/")):
        return None
    metrics = dict(part.split(":", 1) for part in vector.split("/")[1:] if ":" in part)
    try:
        scope = metrics["S"]
        attack_vector = {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.2}[metrics["AV"]]
        attack_complexity = {"L": 0.77, "H": 0.44}[metrics["AC"]]
        privileges = (
            {"N": 0.85, "L": 0.62, "H": 0.27} if scope == "U" else {"N": 0.85, "L": 0.68, "H": 0.5}
        )[metrics["PR"]]
        interaction = {"N": 0.85, "R": 0.62}[metrics["UI"]]
        impact_values = {"H": 0.56, "L": 0.22, "N": 0.0}
        impact_base = 1.0
        for metric in ("C", "I", "A"):
            impact_base *= 1.0 - impact_values[metrics[metric]]
        impact_base = 1.0 - impact_base
    except (KeyError, ValueError):
        return None
    impact = (
        6.42 * impact_base
        if scope == "U"
        else 7.52 * (impact_base - 0.029) - 3.25 * (impact_base - 0.02) ** 15
    )
    if impact <= 0:
        return 0.0
    exploitability = 8.22 * attack_vector * attack_complexity * privileges * interaction
    base = min(impact + exploitability, 10.0)
    if scope == "C":
        base = min(1.08 * (impact + exploitability), 10.0)
    return _round_up_one_decimal(base)


def _score_severity(score: float) -> str:
    if score >= 9.0:
        return "critical"
    if score >= 7.0:
        return "high"
    if score >= 4.0:
        return "medium"
    return "low"


def _osv_severity(vulnerability: Mapping[str, Any]) -> str:
    database_specific = _as_mapping(vulnerability.get("database_specific"))
    named = str(database_specific.get("severity", "")).lower()
    if named in {"critical", "high", "medium", "low"}:
        return named
    scores: list[float] = []
    for raw_severity in _as_list(vulnerability.get("severity")):
        severity = _as_mapping(raw_severity)
        score_value = str(severity.get("score", ""))
        if score_value:
            try:
                scores.append(float(score_value))
            except ValueError:
                parsed = _cvss_v3_score(score_value)
                if parsed is not None:
                    scores.append(parsed)
    return _score_severity(max(scores)) if scores else "unknown"


def parse_osv_report(payload: object, repo: Path) -> list[Finding]:
    report = _as_mapping(payload)
    if not report or not isinstance(report.get("results", []), list):
        raise SetupFailure("osv-scanner returned an invalid JSON report")
    findings: list[Finding] = []
    for raw_result in _as_list(report.get("results")):
        result = _as_mapping(raw_result)
        source = _as_mapping(result.get("source"))
        path = _clean_path(source.get("path", "unknown-path"), repo)
        for raw_package in _as_list(result.get("packages")):
            package = _as_mapping(raw_package)
            for raw_vulnerability in _as_list(package.get("vulnerabilities")):
                vulnerability = _as_mapping(raw_vulnerability)
                findings.append(
                    Finding(
                        rule=_clean_rule(vulnerability.get("id", "unknown-vulnerability")),
                        path=path,
                        severity=_osv_severity(vulnerability),
                        scope="dependencies",
                    )
                )
    return findings


def blocks_release(findings: Sequence[Finding]) -> bool:
    return any(finding.severity in BLOCKING_SEVERITIES for finding in findings)


def render_report(tool: str, version: str, findings: Sequence[Finding]) -> dict[str, object]:
    return {
        "tool": tool,
        "version": version,
        "verdict": "BLOCK" if blocks_release(findings) else "PASS",
        "findings": [asdict(finding) for finding in findings],
    }


def _write_report(
    report_dir: Path, tool: str, version: str, findings: Sequence[Finding]
) -> GateResult:
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{tool}.json"
    report_path.write_text(
        json.dumps(render_report(tool, version, findings), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    exit_code = EXIT_VIOLATION if blocks_release(findings) else EXIT_CLEAN
    return GateResult(exit_code, report_path, tuple(findings))


def _load_json(path: Path, tool: str) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SetupFailure(f"{tool} returned an invalid JSON report") from error


def _tool_binary(environment_name: str, default: str) -> str:
    return os.environ.get(environment_name, default)


def _verify_version(
    tool: str,
    binary: str,
    expected: str,
    repo: Path,
    runner: Runner,
) -> None:
    result = runner([binary, "--version"], repo)
    if result.returncode != 0:
        raise SetupFailure(f"{tool} version check failed")
    version_text = result.stdout + result.stderr
    if re.search(rf"(?<!\d){re.escape(expected)}(?!\d)", version_text) is None:
        raise SetupFailure(f"{tool} version mismatch; expected {expected}")


def _git_has_head(repo: Path) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD"],
        cwd=repo,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def run_secrets(repo: Path, report_dir: Path, *, runner: Runner = run_command) -> GateResult:
    binary = _tool_binary("GITLEAKS_BIN", "gitleaks")
    _verify_version("gitleaks", binary, GITLEAKS_VERSION, repo, runner)
    scopes: list[tuple[str, list[str]]] = [("working-tree", ["dir", str(repo)])]
    if _git_has_head(repo):
        scopes.extend(
            [
                ("staged", ["git", "--staged", str(repo)]),
                ("history", ["git", "--log-opts=HEAD", str(repo)]),
            ]
        )
    findings: list[Finding] = []
    with tempfile.TemporaryDirectory(prefix="vocabulary-gitleaks-") as temp_dir:
        for index, (scope, arguments) in enumerate(scopes):
            raw_report = Path(temp_dir) / f"{index}.json"
            command = [
                binary,
                *arguments,
                "--no-banner",
                "--no-color",
                "--redact=100",
                "--exit-code",
                "3",
                "--report-format",
                "json",
                "--report-path",
                str(raw_report),
            ]
            result = runner(command, repo)
            if result.returncode not in {0, 3}:
                raise SetupFailure("gitleaks execution failed")
            scope_findings = parse_gitleaks_report(_load_json(raw_report, "gitleaks"), repo, scope)
            if result.returncode == 3 and not scope_findings:
                raise SetupFailure("gitleaks failed without a parseable finding")
            findings.extend(scope_findings)
    unique = sorted(set(findings), key=lambda item: (item.path, item.rule, item.scope))
    return _write_report(report_dir, "gitleaks", GITLEAKS_VERSION, unique)


def run_code(repo: Path, report_dir: Path, *, runner: Runner = run_command) -> GateResult:
    binary = _tool_binary("SEMGREP_BIN", "semgrep")
    _verify_version("semgrep", binary, SEMGREP_VERSION, repo, runner)
    with tempfile.TemporaryDirectory(prefix="vocabulary-semgrep-") as temp_dir:
        rules_path = Path(temp_dir) / "rules.yml"
        raw_report = Path(temp_dir) / "report.json"
        rules_path.write_text(SEMGREP_RULESET, encoding="utf-8")
        command = [
            binary,
            "scan",
            "--config",
            str(rules_path),
            "--json-output",
            str(raw_report),
            "--metrics",
            "off",
            "--strict",
            "--oss-only",
            "--no-rewrite-rule-ids",
            "--no-autofix",
            "--exclude",
            "node_modules",
            "--exclude",
            "frontend/dist",
            str(repo),
        ]
        result = runner(command, repo)
        if result.returncode != 0:
            raise SetupFailure("semgrep execution failed")
        findings = parse_semgrep_report(_load_json(raw_report, "semgrep"), repo)
    return _write_report(report_dir, "semgrep", SEMGREP_VERSION, findings)


def run_dependencies(repo: Path, report_dir: Path, *, runner: Runner = run_command) -> GateResult:
    binary = _tool_binary("OSV_SCANNER_BIN", "osv-scanner")
    _verify_version("osv-scanner", binary, OSV_SCANNER_VERSION, repo, runner)
    lockfiles = [
        ("package-lock.json", str(repo / "package-lock.json")),
        ("requirements.txt", str(repo / "requirements.lock")),
        ("requirements.txt", str(repo / "requirements-dev.lock")),
    ]
    missing = [path for _kind, path in lockfiles if not Path(path).is_file()]
    if missing:
        raise SetupFailure("required dependency lockfile is missing")
    arguments = [
        f"--lockfile=:{path}" if kind == "package-lock.json" else f"--lockfile={kind}:{path}"
        for kind, path in lockfiles
    ]
    command = [binary, "scan", "source", "--format=json", *arguments]
    if os.environ.get("T090_OSV_OFFLINE") == "1":
        command.insert(1, "--offline")
    result = runner(command, repo)
    if result.returncode not in {0, 1}:
        raise SetupFailure("osv-scanner execution failed")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise SetupFailure("osv-scanner returned an invalid JSON report") from error
    findings = parse_osv_report(payload, repo)
    if result.returncode == 1 and not findings:
        raise SetupFailure("osv-scanner failed without a parseable finding")
    return _write_report(report_dir, "osv-scanner", OSV_SCANNER_VERSION, findings)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--report-dir", type=Path)
    parser.add_argument("gate", choices=("secrets", "code", "deps"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo = args.repo.resolve()
    report_dir = args.report_dir or repo / "htmlcov" / "security"
    try:
        if args.gate == "secrets":
            result = run_secrets(repo, report_dir)
        elif args.gate == "code":
            result = run_code(repo, report_dir)
        else:
            result = run_dependencies(repo, report_dir)
    except SetupFailure as error:
        print(f"SETUP_FAILED: {error}", file=sys.stderr)
        return EXIT_SETUP

    print(f"{args.gate}: {len(result.findings)} finding(s)")
    for finding in result.findings:
        print(f"[{finding.severity}] {finding.rule} {finding.path}")
    print(f"report: {result.report_path.relative_to(repo)}")
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())

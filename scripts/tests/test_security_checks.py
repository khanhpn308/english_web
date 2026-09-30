from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest
from scripts import security_checks


def completed(
    command: Sequence[str],
    returncode: int = 0,
    *,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(list(command), returncode, stdout, stderr)


def test_gitleaks_report_exposes_only_rule_and_path_metadata(tmp_path: Path) -> None:
    sentinel = "synthetic-secret-value-that-must-not-escape"
    payload = [
        {
            "RuleID": "generic-api-key",
            "File": str(tmp_path / "untracked.txt"),
            "Secret": sentinel,
            "Match": f"api_key={sentinel}",
            "Line": f"api_key={sentinel}",
            "Commit": "deadbeef",
            "Author": "fixture",
        }
    ]

    findings = security_checks.parse_gitleaks_report(payload, tmp_path, "working-tree")
    report = security_checks.render_report("gitleaks", "8.30.1", findings)
    serialized = json.dumps(report, sort_keys=True)

    assert findings == [
        security_checks.Finding(
            rule="generic-api-key",
            path="untracked.txt",
            severity="critical",
            scope="working-tree",
        )
    ]
    assert sentinel not in serialized
    assert "Secret" not in serialized
    assert "Match" not in serialized


def test_secret_gate_scans_untracked_files_without_head_and_redacts_transcript(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    sentinel = "synthetic-secret-value-that-must-not-escape"
    (repo / "untracked.txt").write_text(f"api_key={sentinel}\n", encoding="utf-8")
    calls: list[list[str]] = []

    def runner(command: Sequence[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        calls.append(list(command))
        if "--version" in command:
            return completed(command, stdout="8.30.1\n")
        report_path = Path(command[command.index("--report-path") + 1])
        report_path.write_text(
            json.dumps(
                [
                    {
                        "RuleID": "generic-api-key",
                        "File": str(cwd / "untracked.txt"),
                        "Secret": sentinel,
                        "Match": sentinel,
                        "Line": sentinel,
                    }
                ]
            ),
            encoding="utf-8",
        )
        return completed(command, 3, stdout=sentinel, stderr=sentinel)

    result = security_checks.run_secrets(repo, tmp_path / "reports", runner=runner)
    captured = capsys.readouterr()
    report_text = result.report_path.read_text(encoding="utf-8")

    assert result.exit_code == security_checks.EXIT_VIOLATION
    assert [call[1] for call in calls if "--report-path" in call] == ["dir"]
    assert "--redact=100" in calls[1]
    assert calls[1][calls[1].index("--exit-code") + 1] == "3"
    assert sentinel not in captured.out
    assert sentinel not in captured.err
    assert sentinel not in report_text
    assert "generic-api-key" in report_text
    assert "untracked.txt" in report_text


def test_secret_gate_scans_worktree_staged_and_history_when_head_exists(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "fixture@example.invalid"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Fixture"], cwd=repo, check=True)
    (repo / "tracked.txt").write_text("clean\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=repo, check=True)
    calls: list[list[str]] = []

    def runner(command: Sequence[str], _cwd: Path) -> subprocess.CompletedProcess[str]:
        calls.append(list(command))
        if "--version" in command:
            return completed(command, stdout="gitleaks version 8.30.1\n")
        report_path = Path(command[command.index("--report-path") + 1])
        report_path.write_text("[]", encoding="utf-8")
        return completed(command)

    result = security_checks.run_secrets(repo, tmp_path / "reports", runner=runner)
    scan_calls = [call for call in calls if "--report-path" in call]

    assert result.exit_code == security_checks.EXIT_CLEAN
    assert [call[1] for call in scan_calls] == ["dir", "git", "git"]
    assert "--staged" in scan_calls[1]
    assert "--staged" not in scan_calls[2]
    assert "--log-opts=HEAD" in scan_calls[2]


@pytest.mark.parametrize("severity", ["HIGH", "CRITICAL", "UNRECOGNIZED"])
def test_semgrep_high_critical_and_unknown_severity_block(severity: str) -> None:
    payload = {
        "results": [
            {
                "check_id": "vocabulary.security.rule",
                "path": "backend/app/example.py",
                "extra": {
                    "severity": "ERROR" if severity != "UNRECOGNIZED" else severity,
                    "metadata": {"impact": severity},
                    "lines": "sensitive source text must not enter the report",
                },
            }
        ],
        "errors": [],
    }

    findings = security_checks.parse_semgrep_report(payload, Path.cwd())

    assert len(findings) == 1
    assert findings[0].severity == severity.lower().replace("unrecognized", "unknown")
    assert security_checks.blocks_release(findings)


@pytest.mark.parametrize("severity", ["HIGH", "CRITICAL", None])
def test_osv_high_critical_and_unknown_severity_block(severity: str | None) -> None:
    vulnerability: dict[str, object] = {"id": "OSV-FIXTURE-1"}
    if severity is not None:
        vulnerability["database_specific"] = {"severity": severity}
    payload = {
        "results": [
            {
                "source": {"path": "package-lock.json", "type": "lockfile"},
                "packages": [
                    {
                        "package": {"name": "fixture", "version": "1.0.0"},
                        "vulnerabilities": [vulnerability],
                    }
                ],
            }
        ]
    }

    findings = security_checks.parse_osv_report(payload, Path.cwd())

    assert findings == [
        security_checks.Finding(
            rule="OSV-FIXTURE-1",
            path="package-lock.json",
            severity=(severity or "unknown").lower(),
            scope="dependencies",
        )
    ]
    assert security_checks.blocks_release(findings)


def test_osv_cvss_v3_score_enforces_high_threshold() -> None:
    payload = {
        "results": [
            {
                "source": {"path": "requirements.lock"},
                "packages": [
                    {
                        "vulnerabilities": [
                            {
                                "id": "OSV-CVSS-HIGH",
                                "severity": [
                                    {
                                        "type": "CVSS_V3",
                                        "score": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
                                    }
                                ],
                            }
                        ]
                    }
                ],
            }
        ]
    }

    findings = security_checks.parse_osv_report(payload, Path.cwd())

    assert findings[0].severity == "critical"
    assert security_checks.blocks_release(findings)


def test_scanner_execution_failure_is_setup_failure(tmp_path: Path) -> None:
    def runner(command: Sequence[str], _cwd: Path) -> subprocess.CompletedProcess[str]:
        if "--version" in command:
            return completed(command, stdout="1.178.0\n")
        return completed(command, 2, stderr="scanner crashed with sensitive source")

    with pytest.raises(security_checks.SetupFailure, match="semgrep execution failed"):
        security_checks.run_code(tmp_path, tmp_path / "reports", runner=runner)


def test_dependency_network_failure_is_setup_failure(tmp_path: Path) -> None:
    (tmp_path / "package-lock.json").write_text("{}", encoding="utf-8")
    (tmp_path / "requirements.lock").write_text("fixture==1.0\n", encoding="utf-8")
    (tmp_path / "requirements-dev.lock").write_text("fixture==1.0\n", encoding="utf-8")

    def runner(command: Sequence[str], _cwd: Path) -> subprocess.CompletedProcess[str]:
        if "--version" in command:
            return completed(command, stdout="osv-scanner version: 2.6.0\n")
        return completed(command, 127, stderr="database unavailable")

    with pytest.raises(security_checks.SetupFailure, match="osv-scanner execution failed"):
        security_checks.run_dependencies(tmp_path, tmp_path / "reports", runner=runner)


def test_version_mismatch_fails_closed(tmp_path: Path) -> None:
    def runner(command: Sequence[str], _cwd: Path) -> subprocess.CompletedProcess[str]:
        return completed(command, stdout="gitleaks version 8.29.1\n")

    with pytest.raises(security_checks.SetupFailure, match=r"expected 8\.30\.1"):
        security_checks.run_secrets(tmp_path, tmp_path / "reports", runner=runner)


def test_code_gate_uses_pinned_local_rules_and_disables_metrics(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def runner(command: Sequence[str], _cwd: Path) -> subprocess.CompletedProcess[str]:
        calls.append(list(command))
        if "--version" in command:
            return completed(command, stdout="1.178.0\n")
        output_path = Path(command[command.index("--json-output") + 1])
        output_path.write_text('{"results": [], "errors": []}', encoding="utf-8")
        return completed(command)

    result = security_checks.run_code(tmp_path, tmp_path / "reports", runner=runner)
    scan_command = calls[1]

    assert result.exit_code == security_checks.EXIT_CLEAN
    assert scan_command[1] == "scan"
    assert scan_command[scan_command.index("--metrics") + 1] == "off"
    assert "--strict" in scan_command
    assert "--oss-only" in scan_command
    assert "--no-rewrite-rule-ids" in scan_command


def test_dependency_gate_scans_all_lockfiles_and_allows_medium_findings(tmp_path: Path) -> None:
    (tmp_path / "package-lock.json").write_text("{}", encoding="utf-8")
    (tmp_path / "requirements.lock").write_text("fixture==1.0\n", encoding="utf-8")
    (tmp_path / "requirements-dev.lock").write_text("fixture==1.0\n", encoding="utf-8")
    calls: list[list[str]] = []

    def runner(command: Sequence[str], _cwd: Path) -> subprocess.CompletedProcess[str]:
        calls.append(list(command))
        if "--version" in command:
            return completed(command, stdout="osv-scanner version: 2.6.0\n")
        payload = {
            "results": [
                {
                    "source": {"path": str(tmp_path / "requirements.lock")},
                    "packages": [
                        {
                            "package": {"name": "must-not-enter-redacted-report"},
                            "vulnerabilities": [
                                {
                                    "id": "OSV-MEDIUM",
                                    "database_specific": {"severity": "MEDIUM"},
                                }
                            ],
                        }
                    ],
                }
            ]
        }
        return completed(command, 1, stdout=json.dumps(payload))

    result = security_checks.run_dependencies(tmp_path, tmp_path / "reports", runner=runner)
    report_text = result.report_path.read_text(encoding="utf-8")
    scan_command = calls[1]

    assert result.exit_code == security_checks.EXIT_CLEAN
    assert sum(argument.startswith("--lockfile=") for argument in scan_command) == 3
    assert f"--lockfile=:{tmp_path / 'package-lock.json'}" in scan_command
    assert "OSV-MEDIUM" in report_text
    assert "must-not-enter-redacted-report" not in report_text


def test_main_reports_setup_failure_without_scanner_transcript(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    def fail_gate(_repo: Path, _report_dir: Path) -> security_checks.GateResult:
        raise security_checks.SetupFailure("gitleaks is unavailable")

    monkeypatch.setattr(security_checks, "run_secrets", fail_gate)

    exit_code = security_checks.main(
        ["--repo", str(tmp_path), "--report-dir", str(tmp_path / "reports"), "secrets"]
    )
    captured = capsys.readouterr()

    assert exit_code == security_checks.EXIT_SETUP
    assert captured.out == ""
    assert captured.err.strip() == "SETUP_FAILED: gitleaks is unavailable"


@pytest.mark.parametrize(
    ("gate", "function_name", "exit_code"),
    [
        ("code", "run_code", security_checks.EXIT_CLEAN),
        ("deps", "run_dependencies", security_checks.EXIT_VIOLATION),
    ],
)
def test_main_dispatches_gate_and_returns_verdict(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    gate: str,
    function_name: str,
    exit_code: int,
) -> None:
    report_path = tmp_path / "reports" / f"{gate}.json"
    finding = security_checks.Finding("fixture-rule", "fixture.py", "high", gate)

    def gate_result(_repo: Path, _report_dir: Path) -> security_checks.GateResult:
        findings = () if exit_code == security_checks.EXIT_CLEAN else (finding,)
        return security_checks.GateResult(exit_code, report_path, findings)

    monkeypatch.setattr(security_checks, function_name, gate_result)

    actual = security_checks.main(
        ["--repo", str(tmp_path), "--report-dir", str(tmp_path / "reports"), gate]
    )
    captured = capsys.readouterr()

    assert actual == exit_code
    assert captured.err == ""
    assert f"{gate}:" in captured.out
    assert "report: reports/" in captured.out


def test_missing_executable_is_setup_failure(tmp_path: Path) -> None:
    with pytest.raises(security_checks.SetupFailure, match="is unavailable"):
        security_checks.run_command([str(tmp_path / "missing-scanner"), "--version"], tmp_path)


def test_dependency_lock_explicitly_pins_fixed_setuptools() -> None:
    repo = Path(__file__).resolve().parents[2]
    lock_text = (repo / "requirements-dev.lock").read_text(encoding="utf-8")
    match = re.search(r"^setuptools==(\d+)\.(\d+)\.(\d+)$", lock_text, re.MULTILINE)

    assert match is not None
    assert tuple(int(part) for part in match.groups()) >= (83, 0, 0)

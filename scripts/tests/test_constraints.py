from __future__ import annotations

import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

import pytest
from scripts import check_constraints

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CHECKER = PROJECT_ROOT / "scripts" / "check_constraints.py"


def run_command(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*args],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )


def run_checker(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        return_code = check_constraints.main(["--repo", str(repo), *args])
    return subprocess.CompletedProcess(
        [sys.executable, str(CHECKER), "--repo", str(repo), *args],
        return_code,
        stdout.getvalue(),
        stderr.getvalue(),
    )


def initialise_repository(repo: Path, files: dict[str, str] | None = None) -> None:
    result = run_command("git", "init", "-b", "main", cwd=repo)
    assert result.returncode == 0, result.stderr
    assert (
        run_command("git", "config", "user.email", "quality@example.invalid", cwd=repo).returncode
        == 0
    )
    assert run_command("git", "config", "user.name", "Quality Test", cwd=repo).returncode == 0
    for relative_path, content in (files or {"README.md": "baseline\n"}).items():
        write_file(repo, relative_path, content)
    assert run_command("git", "add", ".", cwd=repo).returncode == 0
    commit = run_command("git", "commit", "-m", "test: baseline", cwd=repo)
    assert commit.returncode == 0, commit.stderr


def write_file(repo: Path, relative_path: str, content: str) -> None:
    path = repo / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_quality_config(
    repo: Path,
    *,
    changed_minimum: float = 80.0,
    baseline: float = 0.0,
    tolerance: float = 0.5,
) -> None:
    write_file(
        repo,
        "pyproject.toml",
        "\n".join(
            [
                "[tool.vocabulary_quality]",
                f"changed_coverage_min = {changed_minimum}",
                f"total_coverage_baseline = {baseline}",
                f"total_coverage_tolerance = {tolerance}",
                'coverage_reports = ["coverage.xml", "coverage/frontend/lcov.info"]',
                'coverage_source_prefixes = ["backend/", "frontend/src/", "scripts/"]',
                "",
            ]
        ),
    )


def source_lines(count: int, *, first_value: int = 1) -> str:
    return "".join(
        f"value_{line_number} = {first_value if line_number == 1 else line_number}\n"
        for line_number in range(1, count + 1)
    )


def write_cobertura_report(
    repo: Path,
    relative_path: str,
    *,
    total_lines: int,
    covered_lines: int,
) -> None:
    line_elements = "".join(
        f'<line number="{line_number}" hits="{1 if line_number <= covered_lines else 0}"/>'
        for line_number in range(1, total_lines + 1)
    )
    write_file(
        repo,
        "coverage.xml",
        (
            '<?xml version="1.0" ?>'
            f'<coverage lines-valid="{total_lines}" lines-covered="{covered_lines}" line-rate="0">'
            "<packages><package><classes>"
            f'<class filename="{relative_path}"><lines>{line_elements}</lines></class>'
            "</classes></package></packages></coverage>"
        ),
    )


def write_lcov_report(
    repo: Path,
    relative_path: str = "frontend/src/existing.ts",
    *,
    hits: int = 1,
) -> None:
    write_file(
        repo,
        "coverage/frontend/lcov.info",
        f"TN:\nSF:{relative_path}\nDA:1,{hits}\nLF:1\nLH:{1 if hits else 0}\nend_of_record\n",
    )


@pytest.mark.parametrize(
    ("covered_lines", "expected_code", "expected_fragment"),
    [
        (799, 1, "79.90%"),
        (800, 0, "80.00%"),
    ],
)
def test_coverage_enforces_changed_line_threshold(
    tmp_path: Path,
    covered_lines: int,
    expected_code: int,
    expected_fragment: str,
) -> None:
    initialise_repository(
        tmp_path,
        {"frontend/src/existing.ts": "export const existing = true;\n"},
    )
    write_quality_config(tmp_path)
    write_file(tmp_path, "backend/app/new_module.py", source_lines(1000))
    write_cobertura_report(
        tmp_path,
        "backend/app/new_module.py",
        total_lines=1000,
        covered_lines=covered_lines,
    )
    write_lcov_report(tmp_path)

    result = run_checker(tmp_path, "coverage", "--base", "main")

    assert result.returncode == expected_code, result.stdout + result.stderr
    assert expected_fragment in result.stdout + result.stderr


def test_coverage_fails_when_any_configured_report_is_missing(tmp_path: Path) -> None:
    initialise_repository(tmp_path)
    write_quality_config(tmp_path)
    write_file(tmp_path, "backend/app/new_module.py", "answer = 42\n")
    write_cobertura_report(
        tmp_path,
        "backend/app/new_module.py",
        total_lines=1,
        covered_lines=1,
    )

    result = run_checker(tmp_path, "coverage", "--base", "main")

    assert result.returncode == 2
    assert "coverage/frontend/lcov.info" in result.stderr
    assert "missing" in result.stderr.lower()


@pytest.mark.parametrize(
    ("covered_lines", "expected_code"),
    [
        (894, 1),
        (895, 0),
    ],
)
def test_coverage_enforces_total_baseline_ratchet_with_half_point_tolerance(
    tmp_path: Path,
    covered_lines: int,
    expected_code: int,
) -> None:
    initialise_repository(
        tmp_path,
        {
            "backend/app/existing.py": source_lines(1000),
            "frontend/src/existing.ts": "export const existing = true;\n",
        },
    )
    write_quality_config(tmp_path, baseline=90.0)
    write_file(tmp_path, "backend/app/existing.py", source_lines(1000, first_value=2))
    write_cobertura_report(
        tmp_path,
        "backend/app/existing.py",
        total_lines=1000,
        covered_lines=covered_lines,
    )
    write_lcov_report(tmp_path)

    result = run_checker(tmp_path, "coverage", "--base", "main")

    assert result.returncode == expected_code, result.stdout + result.stderr
    assert "baseline 90.00%" in result.stdout + result.stderr


def test_coverage_fails_when_changed_source_has_no_measurements(tmp_path: Path) -> None:
    initialise_repository(
        tmp_path,
        {"frontend/src/existing.ts": "export const existing = true;\n"},
    )
    write_quality_config(tmp_path)
    write_file(tmp_path, "backend/app/unmeasured.py", "answer = 42\n")
    write_cobertura_report(
        tmp_path,
        "backend/app/other.py",
        total_lines=1,
        covered_lines=1,
    )
    write_lcov_report(tmp_path)

    result = run_checker(tmp_path, "coverage", "--base", "main")

    assert result.returncode == 1
    assert "backend/app/unmeasured.py" in result.stderr
    assert "no coverage measurements" in result.stderr.lower()


def test_coverage_checks_untracked_source_in_repository_without_head(tmp_path: Path) -> None:
    assert run_command("git", "init", "-b", "main", cwd=tmp_path).returncode == 0
    write_quality_config(tmp_path)
    write_file(tmp_path, "backend/app/new_module.py", "answer = 42\n")
    write_file(tmp_path, "frontend/src/existing.ts", "export const existing = true;\n")
    write_cobertura_report(
        tmp_path,
        "backend/app/new_module.py",
        total_lines=1,
        covered_lines=1,
    )
    write_lcov_report(tmp_path)

    result = run_checker(tmp_path, "coverage", "--base", "main")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "changed 100.00%" in result.stdout
    assert "no merge base" not in result.stderr.lower()


@pytest.mark.parametrize("diff_kind", ["tracked", "untracked", "no-head"])
def test_coverage_excludes_only_generated_lines_without_measurements(
    tmp_path: Path, diff_kind: str
) -> None:
    generated = "frontend/src/shared/api/generated.ts"
    if diff_kind == "no-head":
        assert run_command("git", "init", "-b", "main", cwd=tmp_path).returncode == 0
    else:
        files = {generated: "export type DTO = string;\n"} if diff_kind == "tracked" else None
        initialise_repository(tmp_path, files)
    write_quality_config(tmp_path)
    write_file(tmp_path, generated, "export type DTO = number;\n" * 100)
    write_cobertura_report(tmp_path, "backend/app/existing.py", total_lines=1, covered_lines=1)
    write_lcov_report(tmp_path)

    result = run_checker(tmp_path, "coverage", "--base", "main")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "changed 100.00%" in result.stdout
    assert "total 100.00%" in result.stdout
    assert generated not in result.stderr


@pytest.mark.parametrize(
    "handwritten",
    [
        "frontend/src/shared/api/generated-helper.ts",
        "frontend/src/shared/api/not-generated.ts",
        "frontend/src/shared/api/client.ts",
        "backend/app/unmeasured.py",
    ],
)
def test_coverage_requires_measurements_for_handwritten_generated_siblings(
    tmp_path: Path, handwritten: str
) -> None:
    initialise_repository(tmp_path)
    write_quality_config(tmp_path)
    write_file(tmp_path, "frontend/src/shared/api/generated.ts", "export type DTO = number;\n")
    write_file(tmp_path, handwritten, "value = 42\n")
    write_cobertura_report(tmp_path, "backend/app/existing.py", total_lines=1, covered_lines=1)
    write_lcov_report(tmp_path)

    result = run_checker(tmp_path, "coverage", "--base", "main")

    assert result.returncode == 1
    assert f"no coverage measurements for changed source {handwritten}" in result.stderr
    assert (
        "no coverage measurements for changed source frontend/src/shared/api/generated.ts"
        not in result.stderr
    )


@pytest.mark.parametrize(("covered_lines", "expected_code"), [(8, 0), (7, 1)])
def test_coverage_mixed_diff_counts_only_handwritten_lines(
    tmp_path: Path, covered_lines: int, expected_code: int
) -> None:
    initialise_repository(tmp_path)
    write_quality_config(tmp_path)
    write_file(
        tmp_path, "frontend/src/shared/api/generated.ts", "export type DTO = number;\n" * 100
    )
    write_file(tmp_path, "backend/app/example.py", source_lines(10))
    write_cobertura_report(
        tmp_path, "backend/app/example.py", total_lines=10, covered_lines=covered_lines
    )
    write_lcov_report(tmp_path)

    result = run_checker(tmp_path, "coverage", "--base", "main")

    assert result.returncode == expected_code, result.stdout + result.stderr
    assert f"changed {covered_lines * 10:.2f}% (minimum 80.00%)" in result.stdout
    assert "no coverage measurements" not in result.stderr
    if expected_code:
        assert "changed-line threshold failed" in result.stderr


@pytest.mark.parametrize(
    ("failure", "expected_code", "expected_fragment"),
    [
        ("missing-xml", 2, "coverage report missing: coverage.xml"),
        ("missing-lcov", 2, "coverage report missing: coverage/frontend/lcov.info"),
        ("empty-lcov", 2, "coverage report has no measured lines"),
        ("ratchet", 1, "total baseline ratchet failed"),
        ("diff-cover-missing", 2, "diff-cover is not installed"),
        ("diff-cover-invalid", 2, "diff-cover could not evaluate"),
    ],
)
def test_generated_only_diff_preserves_report_ratchet_and_setup_checks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
    expected_code: int,
    expected_fragment: str,
) -> None:
    initialise_repository(tmp_path)
    write_quality_config(tmp_path, baseline=90.0)
    write_file(tmp_path, "frontend/src/shared/api/generated.ts", "export type DTO = number;\n")
    write_cobertura_report(tmp_path, "backend/app/existing.py", total_lines=1, covered_lines=1)
    write_lcov_report(tmp_path)
    if failure == "missing-xml":
        (tmp_path / "coverage.xml").unlink()
    elif failure == "missing-lcov":
        (tmp_path / "coverage/frontend/lcov.info").unlink()
    elif failure == "empty-lcov":
        write_file(tmp_path, "coverage/frontend/lcov.info", "")
    elif failure == "ratchet":
        # Even measurements of generated code remain in the total report ratchet.
        write_lcov_report(tmp_path, "frontend/src/shared/api/generated.ts", hits=0)
    elif failure == "diff-cover-missing":
        monkeypatch.setattr(check_constraints, "find_diff_cover", lambda: None)
    elif failure == "diff-cover-invalid":
        monkeypatch.setattr(check_constraints, "find_diff_cover", lambda: Path(sys.executable))

    result = run_checker(tmp_path, "coverage", "--base", "main")

    assert result.returncode == expected_code, result.stdout + result.stderr
    assert expected_fragment in result.stderr
    if failure == "ratchet":
        assert "changed 100.00%" in result.stdout
        assert "total 50.00%" in result.stdout


def test_generated_coverage_exclusion_does_not_exempt_floor_rules(tmp_path: Path) -> None:
    initialise_repository(tmp_path)
    write_quality_config(tmp_path)
    assert run_command("git", "add", "pyproject.toml", cwd=tmp_path).returncode == 0
    assert run_command("git", "commit", "-m", "test: quality config", cwd=tmp_path).returncode == 0
    write_quality_config(tmp_path, changed_minimum=79.0)
    write_file(
        tmp_path,
        "frontend/src/shared/api/generated.ts",
        "// @ts" + "-ignore\nexport type DTO = number;\n",
    )

    result = run_checker(tmp_path, "floor", "--base", "main")

    assert result.returncode == 1
    assert "[silenced-checker] frontend/src/shared/api/generated.ts:1" in result.stderr
    assert "[threshold-loosened] pyproject.toml" in result.stderr


def test_floor_flags_untracked_suppression_without_leaking_line_content(tmp_path: Path) -> None:
    initialise_repository(tmp_path)
    suppression = "# type:" + " ignore"
    write_file(
        tmp_path,
        "backend/app/unsafe.py",
        f'api_key = "do-not-print-this"  {suppression}\n',
    )

    result = run_checker(tmp_path, "floor", "--base", "main")

    assert result.returncode == 1
    assert "[silenced-checker] backend/app/unsafe.py:1" in result.stderr
    assert "do-not-print-this" not in result.stdout + result.stderr


def test_floor_flags_new_skipped_test(tmp_path: Path) -> None:
    initialise_repository(tmp_path)
    marker = "@pytest.mark." + "skip(reason='later')"
    write_file(
        tmp_path, "tests/test_pending.py", f"{marker}\ndef test_pending():\n    assert True\n"
    )

    result = run_checker(tmp_path, "floor", "--base", "main")

    assert result.returncode == 1
    assert "[test-made-easier] tests/test_pending.py:1" in result.stderr


def test_floor_flags_assertion_removed_from_existing_test(tmp_path: Path) -> None:
    initialise_repository(
        tmp_path,
        {"tests/test_value.py": "def test_value():\n    assert 1 + 1 == 2\n"},
    )
    write_file(tmp_path, "tests/test_value.py", "def test_value():\n    value = 1 + 1\n")

    result = run_checker(tmp_path, "floor", "--base", "main")

    assert result.returncode == 1
    assert "[assertion-removed] tests/test_value.py:2" in result.stderr


def test_floor_flags_deleted_test_file(tmp_path: Path) -> None:
    initialise_repository(
        tmp_path,
        {"tests/test_value.py": "def test_value():\n    assert 1 + 1 == 2\n"},
    )
    (tmp_path / "tests" / "test_value.py").unlink()

    result = run_checker(tmp_path, "floor", "--base", "main")

    assert result.returncode == 1
    assert "[test-deleted] tests/test_value.py" in result.stderr


@pytest.mark.parametrize(
    ("before", "after", "expected_code"),
    [
        pytest.param(
            "    assert value == 2\n",
            "    value = 2\n",
            1,
            id="only-assertion-deleted",
        ),
        pytest.param(
            '    assert revision == "0002_operations"\n',
            '    assert revision == "0003_consent"\n',
            0,
            id="revision-replacement",
        ),
        pytest.param(
            '    assert read_revision(connection) == "0002_operations"\n',
            '    assert (\n        read_revision(connection) == "0003_consent"\n    )\n',
            0,
            id="replacement-wraps-to-multiline",
        ),
        pytest.param(
            '    assert (\n        read_revision(connection) == "0002_operations"\n    )\n',
            '    assert read_revision(connection) == "0003_consent"\n',
            0,
            id="replacement-unwraps-multiline",
        ),
        pytest.param(
            "    assert value == 2\n    assert other == 3\n",
            "    assert value == 4\n",
            1,
            id="two-removed-one-added",
        ),
        pytest.param(
            "    assert value == 2\n",
            "    assert value == 4\n    assert other == 3\n",
            0,
            id="one-removed-two-added",
        ),
        pytest.param(
            "    assert value == 2; assert other == 3\n",
            "    assert value == 4\n",
            1,
            id="two-statements-on-one-line-net-loss",
        ),
        pytest.param(
            "    assert value == 2; assert other == 3\n",
            "    assert value == 4\n    assert other == 5\n",
            0,
            id="same-line-statements-rewrapped",
        ),
        pytest.param(
            '    assert value == 2, "assert old revision"\n',
            '    assert value == 3, "new revision"\n',
            0,
            id="assertion-message-is-not-an-assertion",
        ),
        pytest.param(
            "    assert value == 2\n",
            "    value = 2  # assert value == 2\n",
            1,
            id="comment-cannot-replace-assertion",
        ),
        pytest.param(
            "    assert value == 2\n",
            '    value = "assert value == 2"\n',
            1,
            id="string-cannot-replace-assertion",
        ),
        pytest.param(
            '    message = """example\n    assert value == 2\n    """\n',
            '    message = """example\n    value = 2\n    """\n',
            0,
            id="multiline-string-is-not-an-assertion",
        ),
        pytest.param(
            "    value = 2\n    assert value == 2\n    value = 3\n",
            '    message = """\n    assert value == 2\n    """\n',
            1,
            id="unchanged-assertion-enclosed-in-string",
        ),
    ],
)
def test_floor_compares_assertion_counts_per_file(
    tmp_path: Path, before: str, after: str, expected_code: int
) -> None:
    path = "tests/test_schema.py"
    initialise_repository(tmp_path, {path: "def test_schema():\n" + before})
    write_file(tmp_path, path, "def test_schema():\n" + after)

    result = run_checker(tmp_path, "floor", "--base", "main")

    assert result.returncode == expected_code, result.stdout + result.stderr
    if expected_code == 1:
        assert f"[assertion-removed] {path}:" in result.stderr
    else:
        assert result.stdout == "floor: clean\n"
        assert result.stderr == ""


@pytest.mark.parametrize("assertion", ["expect(value).toBe", "value.should.equal"])
def test_floor_allows_other_assertion_framework_replacements(
    tmp_path: Path, assertion: str
) -> None:
    path = "frontend/src/value.test.ts"
    initialise_repository(tmp_path, {path: f"{assertion}(2);\n"})
    write_file(tmp_path, path, f"{assertion}(3);\n")

    result = run_checker(tmp_path, "floor", "--base", "main")

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stderr == ""


def test_floor_does_not_credit_assertions_added_in_another_file(tmp_path: Path) -> None:
    initialise_repository(
        tmp_path,
        {
            "tests/test_value.py": "def test_value():\n    assert value == 2\n",
            "tests/test_other.py": "def test_other():\n    assert other == 3\n",
        },
    )
    write_file(tmp_path, "tests/test_value.py", "def test_value():\n    value = 2\n")
    write_file(
        tmp_path,
        "tests/test_other.py",
        "def test_other():\n    assert other == 3\n    assert extra == 4\n",
    )

    result = run_checker(tmp_path, "floor", "--base", "main")

    assert result.returncode == 1
    assert result.stderr == "floor: 1 violation(s)\n[assertion-removed] tests/test_value.py:2\n"


def test_floor_allows_replacement_across_separate_diff_hunks(tmp_path: Path) -> None:
    path = "tests/test_value.py"
    middle = "    value += 1\n" * 10
    initialise_repository(tmp_path, {path: "def test_value():\n    assert value == 2\n" + middle})
    write_file(tmp_path, path, "def test_value():\n" + middle + "    assert value == 12\n")

    result = run_checker(tmp_path, "floor", "--base", "main")

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == "floor: clean\n"


def test_floor_assertion_counting_failure_is_redacted_and_never_green(tmp_path: Path) -> None:
    path = "tests/test_value.py"
    initialise_repository(tmp_path, {path: "def test_value():\n    assert value == 2\n"})
    write_file(tmp_path, path, 'def test_value():\n    assert ("do-not-print-this"\n')

    result = run_checker(tmp_path, "floor", "--base", "main")

    assert result.returncode == 2
    assert result.stderr == f"floor: SETUP_PENDING: cannot count assertions: {path}\n"
    assert "do-not-print-this" not in result.stdout + result.stderr


@pytest.mark.parametrize(
    ("marker", "rule"),
    [
        ("@pytest.mark." + "skip(reason='later')", "test-made-easier"),
        ("# type:" + " ignore", "silenced-checker"),
    ],
)
def test_floor_replacement_does_not_bypass_skip_or_suppression(
    tmp_path: Path, marker: str, rule: str
) -> None:
    path = "tests/test_value.py"
    initialise_repository(tmp_path, {path: "def test_value():\n    assert value == 2\n"})
    write_file(tmp_path, path, f"{marker}\ndef test_value():\n    assert value == 3\n")

    result = run_checker(tmp_path, "floor", "--base", "main")

    assert result.returncode == 1
    assert f"[{rule}] {path}:1" in result.stderr
    assert "[assertion-removed]" not in result.stderr


def test_floor_flags_loosened_constraint_threshold(tmp_path: Path) -> None:
    initialise_repository(
        tmp_path,
        {"CONSTRAINTS.md": "- Changed coverage: at least 80%\n"},
    )
    write_file(tmp_path, "CONSTRAINTS.md", "- Changed coverage: at least 79%\n")

    result = run_checker(tmp_path, "floor", "--base", "main")

    assert result.returncode == 1
    assert "[threshold-loosened] CONSTRAINTS.md:1" in result.stderr


def test_floor_checks_untracked_code_in_repository_without_head(tmp_path: Path) -> None:
    assert run_command("git", "init", "-b", "main", cwd=tmp_path).returncode == 0
    suppression = "@ts" + "-ignore"
    write_file(tmp_path, "frontend/src/new.ts", f"// {suppression}\nexport const value = 1;\n")

    result = run_checker(tmp_path, "floor", "--base", "main")

    assert result.returncode == 1
    assert "[silenced-checker] frontend/src/new.ts:1" in result.stderr
    assert "no merge base" not in result.stderr.lower()


def test_floor_ignores_planning_language_in_markdown(tmp_path: Path) -> None:
    initialise_repository(tmp_path)
    planning_text = "Status: TO" + "DO\nDo not add eslint" + "-disable to code.\n"
    write_file(tmp_path, "tasks/task.md", planning_text)

    result = run_checker(tmp_path, "floor", "--base", "main")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "floor: clean" in result.stdout


def test_floor_returns_setup_error_outside_git_repository(tmp_path: Path) -> None:
    result = run_checker(tmp_path, "floor", "--base", "main")

    assert result.returncode == 2
    assert "not a git repository" in result.stderr.lower()


def test_pending_gate_is_explicit_and_never_green(tmp_path: Path) -> None:
    result = run_checker(tmp_path, "pending", "T063", "security scanners")

    assert result.returncode == 2
    assert "SETUP_PENDING" in result.stderr
    assert "T063" in result.stderr


def test_diff_cover_is_found_next_to_active_python_when_not_on_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable_directory = tmp_path / "bin"
    executable_directory.mkdir()
    python_executable = executable_directory / "python"
    diff_cover_executable = executable_directory / "diff-cover"
    python_executable.write_text("", encoding="utf-8")
    diff_cover_executable.write_text("", encoding="utf-8")
    monkeypatch.setattr(check_constraints.shutil, "which", lambda _command: None)
    monkeypatch.setattr(check_constraints.sys, "executable", str(python_executable))

    assert check_constraints.find_diff_cover() == diff_cover_executable

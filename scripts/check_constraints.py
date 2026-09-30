#!/usr/bin/env python3
"""Diff-scoped coverage and quality-floor checks for T053."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tokenize
import tomllib
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from io import StringIO
from pathlib import Path, PurePosixPath
from typing import Any, cast

EXIT_CLEAN = 0
EXIT_VIOLATION = 1
EXIT_SETUP = 2
SOURCE_SUFFIXES = {
    ".c",
    ".cjs",
    ".cpp",
    ".cs",
    ".go",
    ".h",
    ".hpp",
    ".java",
    ".js",
    ".jsx",
    ".kt",
    ".mjs",
    ".ps1",
    ".py",
    ".pyi",
    ".rs",
    ".sh",
    ".ts",
    ".tsx",
}


@dataclass(frozen=True)
class DiffLine:
    path: str
    line_number: int
    text: str


@dataclass
class DiffData:
    added: list[DiffLine]
    removed: list[DiffLine]
    deleted: set[str]
    unified_diff: str


@dataclass(frozen=True)
class Finding:
    rule: str
    path: str
    line_number: int | None = None


class SetupFailure(RuntimeError):
    """The checker cannot produce a trustworthy verdict."""


def run_git(repo: Path, *args: str, allow_difference: bool = False) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0 or (allow_difference and result.returncode == 1):
        return result.stdout
    message = result.stderr.strip() or "git command failed"
    raise SetupFailure(message)


def normalize_path(value: str, repo: Path | None = None) -> str:
    normalized = value.replace("\\", "/")
    if repo is not None:
        repo_prefix = repo.resolve().as_posix().rstrip("/") + "/"
        if normalized.startswith(repo_prefix):
            normalized = normalized[len(repo_prefix) :]
    while normalized.startswith("./"):
        normalized = normalized[2:]
    if normalized.startswith("a/") or normalized.startswith("b/"):
        normalized = normalized[2:]
    return PurePosixPath(normalized).as_posix()


def is_git_repository(repo: Path) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def has_head(repo: Path) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD"],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def untracked_paths(repo: Path, *, include_cached: bool = False) -> list[str]:
    args = ["ls-files"]
    if include_cached:
        args.append("--cached")
    args.extend(["--others", "--exclude-standard", "-z"])
    output = run_git(repo, *args)
    return sorted({normalize_path(path) for path in output.split("\0") if path})


def synthetic_new_file_diff(path: str, content: str) -> str:
    lines = content.splitlines()
    header = ["diff --git a/{0} b/{0}", "new file mode 100644", "--- /dev/null", "+++ b/{0}"]
    rendered = [part.format(path) for part in header]
    if lines:
        rendered.append(f"@@ -0,0 +1,{len(lines)} @@")
        rendered.extend(f"+{line}" for line in lines)
    return "\n".join(rendered) + "\n"


def parse_unified_diff(diff: str) -> DiffData:
    added: list[DiffLine] = []
    removed: list[DiffLine] = []
    deleted: set[str] = set()
    old_path = ""
    path = ""
    old_line = 0
    new_line = 0
    in_hunk = False
    hunk_pattern = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")

    for raw_line in diff.splitlines():
        if raw_line.startswith("--- "):
            old_path = normalize_path(raw_line[4:].split("\t", 1)[0])
            in_hunk = False
            continue
        if raw_line.startswith("+++ "):
            new_path = normalize_path(raw_line[4:].split("\t", 1)[0])
            path = old_path if new_path == "/dev/null" else new_path
            if new_path == "/dev/null" and old_path:
                deleted.add(old_path)
            in_hunk = False
            continue
        hunk_match = hunk_pattern.match(raw_line)
        if hunk_match:
            old_line = int(hunk_match.group(1))
            new_line = int(hunk_match.group(2))
            in_hunk = True
            continue
        if not in_hunk or raw_line.startswith("\\ No newline"):
            continue
        if raw_line.startswith("+"):
            added.append(DiffLine(path, new_line, raw_line[1:]))
            new_line += 1
        elif raw_line.startswith("-"):
            removed.append(DiffLine(path, old_line, raw_line[1:]))
            old_line += 1
        else:
            old_line += 1
            new_line += 1

    return DiffData(added=added, removed=removed, deleted=deleted, unified_diff=diff)


def collect_diff(repo: Path, base: str) -> DiffData:
    if not is_git_repository(repo):
        raise SetupFailure("not a git repository")

    if has_head(repo):
        merge_base = run_git(repo, "merge-base", base, "HEAD").strip()
        if not merge_base:
            raise SetupFailure(f"no merge base against {base}")
        tracked_diff = run_git(repo, "diff", "--unified=0", merge_base, "--")
        paths = untracked_paths(repo)
    else:
        tracked_diff = ""
        paths = untracked_paths(repo, include_cached=True)

    untracked_diffs: list[str] = []
    for relative_path in paths:
        absolute_path = repo / relative_path
        if not absolute_path.is_file():
            continue
        try:
            content = absolute_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        untracked_diffs.append(synthetic_new_file_diff(relative_path, content))

    combined = tracked_diff + "\n" + "\n".join(untracked_diffs)
    return parse_unified_diff(combined)


def is_source(path: str) -> bool:
    return PurePosixPath(path).suffix.lower() in SOURCE_SUFFIXES


def is_test(path: str) -> bool:
    name = PurePosixPath(path).name.lower()
    return (
        name.startswith("test_")
        or "_test." in name
        or ".test." in name
        or ".spec." in name
        or "/tests/" in f"/{path.lower()}"
    )


def compile_floor_patterns() -> tuple[re.Pattern[str], re.Pattern[str], re.Pattern[str]]:
    suppression_tokens = [
        r"@ts" + r"-ignore",
        r"@ts" + r"-nocheck",
        r"eslint" + r"-disable",
        r"biome" + r"-ignore",
        r"#\s*no" + r"qa",
        r"#\s*type:\s*" + r"ignore",
        r"istanbul\s+" + r"ignore",
        r"nosem" + r"grep",
        r"gitleaks:" + r"allow",
        r"Stryker\s+" + r"disable",
        r"pragma:\s*no\s*" + r"cover",
    ]
    stub_tokens = [
        r"throw\s+new\s+(?:Error|NotImplemented).*not\s+implemented",
        r"raise\s+NotImplemented" + r"Error",
        r"catch\s*(?:\([^)]*\))?\s*\{\s*\}",
        r"\bTO" + r"DO\b",
        r"\bpass\s*#\s*stub",
    ]
    skip_tokens = [
        r"\.(?:skip|" + r"to" + r"do)\b",
        r"\bx(?:it|describe)\s*\(",
        r"@pytest\.mark\." + r"skip",
        r"\bt\.Skip\s*\(",
    ]
    return (
        re.compile("|".join(suppression_tokens), re.IGNORECASE),
        re.compile("|".join(stub_tokens), re.IGNORECASE),
        re.compile("|".join(skip_tokens)),
    )


def constraint_rule_key(text: str) -> str | None:
    stripped = text.strip()
    if stripped.startswith("|"):
        cells = [cell.strip() for cell in stripped.split("|") if cell.strip()]
        return cells[0] if cells else None
    if stripped.startswith(("- ", "* ")):
        return stripped[2:].split(":", 1)[0].strip()
    return None


def directional_numbers(text: str) -> list[tuple[float, str | None]]:
    minimum_before = re.compile(
        r"(?:>=|>|≥|at least|minimum|no less than|not fall|not drop)\s*$", re.I
    )
    maximum_before = re.compile(
        r"(?:<=|<|≤|at most|maximum|no more than|under|below|not grow|not exceed)\s*$", re.I
    )
    numbers: list[tuple[float, str | None]] = []
    for match in re.finditer(r"\d+(?:\.\d+)?", text):
        before = text[max(0, match.start() - 30) : match.start()]
        after = text[match.end() : match.end() + 45].lower()
        direction: str | None = None
        if minimum_before.search(before) or re.match(
            r"\s*%?\s*(?:or more|or higher|must not fall|must not drop)", after
        ):
            direction = "min"
        elif maximum_before.search(before) or re.match(
            r"\s*%?\s*(?:or less|or lower|must not grow|must not exceed)", after
        ):
            direction = "max"
        numbers.append((float(match.group()), direction))
    return numbers


def threshold_findings(diff: DiffData) -> list[Finding]:
    findings: list[Finding] = []
    removed_rules = [
        line
        for line in diff.removed
        if line.path.endswith("CONSTRAINTS.md") and constraint_rule_key(line.text)
    ]
    added_rules = [
        line
        for line in diff.added
        if line.path.endswith("CONSTRAINTS.md") and constraint_rule_key(line.text)
    ]

    for old in removed_rules:
        key = constraint_rule_key(old.text)
        replacement = next(
            (line for line in added_rules if constraint_rule_key(line.text) == key), None
        )
        if replacement is None:
            if not re.match(r"^\|\s*[WE]\d+\s*\|", old.text.strip()):
                findings.append(Finding("rule-removed", old.path, old.line_number))
            continue
        before = directional_numbers(old.text)
        after = directional_numbers(replacement.text)
        for index, (old_value, direction) in enumerate(before):
            if index >= len(after):
                findings.append(
                    Finding("threshold-removed", replacement.path, replacement.line_number)
                )
                break
            new_value, new_direction = after[index]
            loosened = (
                direction != new_direction
                or (direction == "min" and new_value < old_value)
                or (direction == "max" and new_value > old_value)
                or (direction is None and new_value != old_value)
            )
            if loosened:
                findings.append(
                    Finding("threshold-loosened", replacement.path, replacement.line_number)
                )
                break

    protected_thresholds = {
        "changed_coverage_min": "min",
        "total_coverage_baseline": "min",
        "total_coverage_tolerance": "max",
    }
    assignments = re.compile(r"^\s*([a-z_]+)\s*=\s*(\d+(?:\.\d+)?)\s*$")
    removed_config: dict[str, tuple[float, DiffLine]] = {}
    added_config: dict[str, tuple[float, DiffLine]] = {}
    for line in diff.removed:
        if line.path == "pyproject.toml" and (match := assignments.match(line.text)):
            removed_config[match.group(1)] = (float(match.group(2)), line)
    for line in diff.added:
        if line.path == "pyproject.toml" and (match := assignments.match(line.text)):
            added_config[match.group(1)] = (float(match.group(2)), line)
    for key, direction in protected_thresholds.items():
        if key not in removed_config:
            continue
        if key not in added_config:
            old_line = removed_config[key][1]
            findings.append(Finding("threshold-removed", old_line.path, old_line.line_number))
            continue
        old_value = removed_config[key][0]
        new_value, new_line = added_config[key]
        if (direction == "min" and new_value < old_value) or (
            direction == "max" and new_value > old_value
        ):
            findings.append(Finding("threshold-loosened", new_line.path, new_line.line_number))
    return findings


def assertion_removal_findings(repo: Path, diff: DiffData) -> list[Finding]:
    assertion_pattern = re.compile(r"\b(?:assert|expect|should)\b")
    added_by_path: dict[str, list[DiffLine]] = {}
    removed_by_path: dict[str, list[DiffLine]] = {}
    for line in diff.added:
        if is_test(line.path):
            added_by_path.setdefault(line.path, []).append(line)
    for line in diff.removed:
        if is_test(line.path) and line.path not in diff.deleted:
            removed_by_path.setdefault(line.path, []).append(line)

    findings: list[Finding] = []
    for path, removed in removed_by_path.items():
        added = added_by_path.get(path, [])
        if PurePosixPath(path).suffix.lower() in {".py", ".pyi"}:
            # Reconstruct the old file from the same diff used by every floor rule.
            # Full-file tokenization distinguishes code from multiline strings.
            try:
                new_lines = (repo / path).read_text(encoding="utf-8").splitlines()
                added_numbers = {line.line_number for line in added}
                old_lines = [
                    text for number, text in enumerate(new_lines, 1) if number not in added_numbers
                ]
                for line in sorted(removed, key=lambda line: line.line_number):
                    old_lines.insert(line.line_number - 1, line.text)

                def assertion_tokens(lines: list[str], test_path: str) -> list[DiffLine]:
                    return [
                        DiffLine(test_path, token.start[0], "")
                        for token in tokenize.generate_tokens(
                            StringIO("\n".join(lines) + "\n").readline
                        )
                        if token.type == tokenize.NAME and assertion_pattern.fullmatch(token.string)
                    ]

                old_assertions = assertion_tokens(old_lines, path)
                new_assertions = assertion_tokens(new_lines, path)
            except (OSError, UnicodeError, tokenize.TokenError, SyntaxError) as error:
                raise SetupFailure(f"cannot count assertions: {path}") from error
            loss = len(old_assertions) - len(new_assertions)
            removed_numbers = {line.line_number for line in removed}
            candidates = sorted(
                old_assertions,
                key=lambda line: (line.line_number not in removed_numbers, line.line_number),
            )
        else:
            # Other test languages retain the existing structural markers.
            candidates = [
                line for line in removed for _match in assertion_pattern.finditer(line.text)
            ]
            replacements = sum(len(assertion_pattern.findall(line.text)) for line in added)
            loss = len(candidates) - replacements
        for line in candidates[: max(0, loss)]:
            findings.append(Finding("assertion-removed", path, line.line_number))
    return findings


def check_floor(repo: Path, base: str) -> int:
    diff = collect_diff(repo, base)
    suppression_pattern, stub_pattern, skip_pattern = compile_floor_patterns()
    findings: list[Finding] = []

    for line in diff.added:
        if is_source(line.path) and suppression_pattern.search(line.text):
            findings.append(Finding("silenced-checker", line.path, line.line_number))
        if is_source(line.path) and stub_pattern.search(line.text):
            findings.append(Finding("unfinished-work", line.path, line.line_number))
        if is_test(line.path) and skip_pattern.search(line.text):
            findings.append(Finding("test-made-easier", line.path, line.line_number))
        if line.path.endswith("CONSTRAINTS.md") and re.match(
            r"^\|\s*[WE]\d+\s*\|", line.text.strip()
        ):
            findings.append(Finding("new-exception", line.path, line.line_number))

    for path in sorted(diff.deleted):
        if is_test(path):
            findings.append(Finding("test-deleted", path))
    findings.extend(assertion_removal_findings(repo, diff))
    findings.extend(threshold_findings(diff))
    unique_findings = sorted(
        set(findings),
        key=lambda finding: (finding.path, finding.line_number or 0, finding.rule),
    )
    if not unique_findings:
        print("floor: clean")
        return EXIT_CLEAN

    print(f"floor: {len(unique_findings)} violation(s)", file=sys.stderr)
    for finding in unique_findings:
        location = finding.path
        if finding.line_number is not None:
            location += f":{finding.line_number}"
        print(f"[{finding.rule}] {location}", file=sys.stderr)
    return EXIT_VIOLATION


def load_quality_config(repo: Path) -> dict[str, Any]:
    config_path = repo / "pyproject.toml"
    if not config_path.is_file():
        raise SetupFailure("pyproject.toml is missing")
    try:
        parsed = tomllib.loads(config_path.read_text(encoding="utf-8"))
        config = cast(dict[str, Any], parsed["tool"]["vocabulary_quality"])
    except (KeyError, tomllib.TOMLDecodeError) as error:
        raise SetupFailure("[tool.vocabulary_quality] is missing or invalid") from error
    required = {
        "changed_coverage_min",
        "total_coverage_baseline",
        "total_coverage_tolerance",
        "coverage_reports",
        "coverage_source_prefixes",
    }
    missing = sorted(required - config.keys())
    if missing:
        raise SetupFailure("quality config missing: " + ", ".join(missing))
    return config


def parse_cobertura(path: Path, repo: Path) -> dict[tuple[str, int], int]:
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as error:
        raise SetupFailure(f"invalid coverage report: {path.relative_to(repo)}") from error
    measurements: dict[tuple[str, int], int] = {}
    for class_element in root.findall(".//class"):
        filename = class_element.get("filename")
        if not filename:
            continue
        normalized = normalize_path(filename, repo)
        for line_element in class_element.findall("./lines/line"):
            number = line_element.get("number")
            hits = line_element.get("hits")
            if number is None or hits is None:
                continue
            measurements[(normalized, int(number))] = int(float(hits))
    if not measurements:
        raise SetupFailure(f"coverage report has no measured lines: {path.relative_to(repo)}")
    return measurements


def parse_lcov(path: Path, repo: Path) -> dict[tuple[str, int], int]:
    measurements: dict[tuple[str, int], int] = {}
    current_file: str | None = None
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise SetupFailure(f"invalid coverage report: {path.relative_to(repo)}") from error
    for line in lines:
        if line.startswith("SF:"):
            current_file = normalize_path(line[3:], repo)
        elif line.startswith("DA:") and current_file:
            fields = line[3:].split(",")
            if len(fields) >= 2:
                measurements[(current_file, int(fields[0]))] = int(float(fields[1]))
    if not measurements:
        raise SetupFailure(f"coverage report has no measured lines: {path.relative_to(repo)}")
    return measurements


def parse_coverage_reports(
    repo: Path, report_names: list[str]
) -> tuple[list[Path], dict[tuple[str, int], int]]:
    reports: list[Path] = []
    combined: dict[tuple[str, int], int] = {}
    for report_name in report_names:
        report = repo / report_name
        if not report.is_file():
            raise SetupFailure(f"coverage report missing: {report_name}")
        reports.append(report)
        if report.suffix.lower() == ".xml":
            measurements = parse_cobertura(report, repo)
        elif report.name.endswith("lcov.info") or report.suffix.lower() == ".lcov":
            measurements = parse_lcov(report, repo)
        else:
            raise SetupFailure(f"unsupported coverage report: {report_name}")
        for key, hits in measurements.items():
            combined[key] = max(combined.get(key, 0), hits)
    return reports, combined


def coverage_path_candidates(path: str, prefixes: list[str]) -> list[str]:
    candidates = [normalize_path(path)]
    for prefix in prefixes:
        normalized_prefix = normalize_path(prefix).rstrip("/") + "/"
        if path.startswith(normalized_prefix):
            candidates.append(path[len(normalized_prefix) :])
    return candidates


def map_measurements_to_diff_paths(
    measurements: dict[tuple[str, int], int],
    changed_paths: set[str],
    prefixes: list[str],
) -> dict[tuple[str, int], int]:
    remapped: dict[tuple[str, int], int] = {}
    for (report_path, line_number), hits in measurements.items():
        matches = [
            changed_path
            for changed_path in changed_paths
            if report_path in coverage_path_candidates(changed_path, prefixes)
            or changed_path.endswith("/" + report_path)
        ]
        target = matches[0] if len(matches) == 1 else report_path
        remapped[(target, line_number)] = max(remapped.get((target, line_number), 0), hits)
    return remapped


def find_diff_cover() -> Path | None:
    discovered = shutil.which("diff-cover")
    if discovered:
        return Path(discovered)
    executable_dir = Path(sys.executable).parent
    for name in ("diff-cover", "diff-cover.exe"):
        candidate = executable_dir / name
        if candidate.is_file():
            return candidate
    return None


def run_external_diff_cover(
    repo: Path,
    reports: list[Path],
    unified_diff: str,
) -> None:
    executable = find_diff_cover()
    if executable is None:
        raise SetupFailure("diff-cover is not installed")
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".diff") as diff_file:
        diff_file.write(unified_diff)
        diff_file.flush()
        for report in reports:
            result = subprocess.run(
                [
                    str(executable),
                    str(report),
                    f"--diff-file={diff_file.name}",
                    "--fail-under=0",
                    "--total-percent-float",
                    "--quiet",
                ],
                cwd=repo,
                check=False,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                raise SetupFailure(f"diff-cover could not evaluate {report.relative_to(repo)}")


def check_coverage(repo: Path, base: str) -> int:
    config = load_quality_config(repo)
    report_names = [str(value) for value in config["coverage_reports"]]
    prefixes = [str(value) for value in config["coverage_source_prefixes"]]
    changed_minimum = float(config["changed_coverage_min"])
    baseline = float(config["total_coverage_baseline"])
    tolerance = float(config["total_coverage_tolerance"])
    reports, measurements = parse_coverage_reports(repo, report_names)
    diff = collect_diff(repo, base)

    changed_source_lines = [
        line
        for line in diff.added
        if is_source(line.path)
        and not is_test(line.path)
        and any(
            line.path.startswith(normalize_path(prefix).rstrip("/") + "/") for prefix in prefixes
        )
    ]
    changed_paths = {line.path for line in changed_source_lines}
    remapped = map_measurements_to_diff_paths(measurements, changed_paths, prefixes)
    report_paths = {path for path, _line_number in remapped}
    unmeasured_files = sorted(path for path in changed_paths if path not in report_paths)
    if unmeasured_files:
        for path in unmeasured_files:
            print(f"coverage: no coverage measurements for changed source {path}", file=sys.stderr)
        return EXIT_VIOLATION

    measured_changed = [
        remapped[(line.path, line.line_number)]
        for line in changed_source_lines
        if (line.path, line.line_number) in remapped
    ]
    if changed_source_lines and not measured_changed:
        print("coverage: changed source has no executable lines in the reports", file=sys.stderr)
        return EXIT_VIOLATION
    changed_percentage = (
        100.0 * sum(1 for hits in measured_changed if hits > 0) / len(measured_changed)
        if measured_changed
        else 100.0
    )
    total_percentage = (
        100.0 * sum(1 for hits in measurements.values() if hits > 0) / len(measurements)
    )

    run_external_diff_cover(repo, reports, diff.unified_diff)
    print(
        f"coverage: changed {changed_percentage:.2f}% (minimum {changed_minimum:.2f}%); "
        f"total {total_percentage:.2f}% "
        f"(baseline {baseline:.2f}%, tolerance {tolerance:.2f} points)"
    )
    failed = False
    if changed_percentage + 1e-9 < changed_minimum:
        print("coverage: changed-line threshold failed", file=sys.stderr)
        failed = True
    if total_percentage + tolerance + 1e-9 < baseline:
        print("coverage: total baseline ratchet failed", file=sys.stderr)
        failed = True
    return EXIT_VIOLATION if failed else EXIT_CLEAN


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    subparsers = parser.add_subparsers(dest="command", required=True)
    default_base = os.environ.get("QUALITY_BASE_REF", "main")
    floor_parser = subparsers.add_parser("floor")
    floor_parser.add_argument("--base", default=default_base)
    coverage_parser = subparsers.add_parser("coverage")
    coverage_parser.add_argument("--base", default=default_base)
    pending_parser = subparsers.add_parser("pending")
    pending_parser.add_argument("owner")
    pending_parser.add_argument("gate", nargs="+")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.command == "floor":
            return check_floor(repo, args.base)
        if args.command == "coverage":
            return check_coverage(repo, args.base)
        gate = " ".join(args.gate)
        print(f"SETUP_PENDING: {gate} is owned by {args.owner}", file=sys.stderr)
        return EXIT_SETUP
    except SetupFailure as error:
        print(f"{args.command}: SETUP_PENDING: {error}", file=sys.stderr)
        return EXIT_SETUP


if __name__ == "__main__":
    raise SystemExit(main())

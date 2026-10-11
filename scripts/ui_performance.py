#!/usr/bin/env python3
"""Deterministic local Lighthouse performance harness for T064.

Measures Core Web Vitals (LCP <= 2.5s, CLS <= 0.1) on the canonical React
application shell and Learning Dashboard (T038) using the T052 temporary loopback
preview interface. Enforces fail-closed threshold evaluation and sanitized artifact
generation without external network or provider dependencies.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any, Generator
import urllib.parse
import urllib.request

EXIT_SUCCESS = 0
EXIT_VIOLATION = 1
EXIT_SETUP = 2

TASK_ID = "T064"
RUNNER_VERSION = "t064-ui-performance-v1"
THRESHOLD_LCP_SECONDS = 2.5
THRESHOLD_CLS = 0.1
DEFAULT_PORT = 8124
DEFAULT_STARTUP_TIMEOUT_SECONDS = 15.0

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_ARTIFACT_PATH = ROOT_DIR / "benchmarks" / "artifacts" / "ui-performance-evidence.json"
TEST_SERVER_SCRIPT = ROOT_DIR / "frontend" / "tests" / "support" / "test_server.py"


@dataclass(frozen=True)
class PerformanceMetrics:
    lcp_seconds: float | None
    cls_score: float | None
    lcp_source: str
    cls_source: str
    raw_lcp_ms: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "lcpSeconds": self.lcp_seconds,
            "clsScore": self.cls_score,
            "lcpSource": self.lcp_source,
            "clsSource": self.cls_source,
            "rawLcpMs": self.raw_lcp_ms,
        }


@dataclass(frozen=True)
class ThresholdVerdict:
    verdict: str  # "PASS", "FAIL", "METRIC_MISSING", "SETUP_PENDING", "TOOL_FAILED"
    reasons: list[str]
    lcp_passed: bool
    cls_passed: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "reasons": self.reasons,
            "lcpPassed": self.lcp_passed,
            "clsPassed": self.cls_passed,
        }


def sanitize_loopback_url(raw_url: str) -> str:
    """Sanitize URL to strictly allow loopback origin, stripping credentials and queries."""
    parsed = urllib.parse.urlparse(raw_url)
    if parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise ValueError(
            f"Target URL must be on loopback (127.0.0.1 or localhost), got: {parsed.hostname}"
        )
    port_part = f":{parsed.port}" if parsed.port else ""
    path = parsed.path if parsed.path else "/"
    return f"{parsed.scheme or 'http'}://{parsed.hostname}{port_part}{path}"


def parse_metrics_from_lhr(report_data: dict[str, Any]) -> PerformanceMetrics:
    """Extract LCP and CLS from a Lighthouse JSON report safely and fail-closed."""
    audits = report_data.get("audits")
    if not isinstance(audits, dict):
        return PerformanceMetrics(
            lcp_seconds=None,
            cls_score=None,
            lcp_source="missing-audits",
            cls_source="missing-audits",
        )

    # LCP extraction
    lcp_audit = audits.get("largest-contentful-paint")
    raw_lcp_ms: float | None = None
    lcp_sec: float | None = None
    lcp_src = "audits.largest-contentful-paint"

    if isinstance(lcp_audit, dict):
        num_val = lcp_audit.get("numericValue")
        if isinstance(num_val, (int, float)) and math.isfinite(num_val):
            raw_lcp_ms = float(num_val)
            lcp_sec = round(raw_lcp_ms / 1000.0, 4)
            lcp_src = "audits.largest-contentful-paint.numericValue"

    # CLS extraction
    cls_audit = audits.get("cumulative-layout-shift")
    cls_val: float | None = None
    cls_src = "audits.cumulative-layout-shift"

    if isinstance(cls_audit, dict):
        num_val = cls_audit.get("numericValue")
        if isinstance(num_val, (int, float)) and math.isfinite(num_val):
            cls_val = round(float(num_val), 4)
            cls_src = "audits.cumulative-layout-shift.numericValue"

    return PerformanceMetrics(
        lcp_seconds=lcp_sec,
        cls_score=cls_val,
        lcp_source=lcp_src,
        cls_source=cls_src,
        raw_lcp_ms=raw_lcp_ms,
    )


def evaluate_thresholds(
    metrics: PerformanceMetrics,
    threshold_lcp: float = THRESHOLD_LCP_SECONDS,
    threshold_cls: float = THRESHOLD_CLS,
) -> ThresholdVerdict:
    """Evaluate Core Web Vitals against fixed thresholds fail-closed.

    Both metrics must be present, finite, and within thresholds to PASS.
    Any missing, malformed, non-finite, or exceeded metric fails.
    """
    reasons: list[str] = []
    lcp_ok = False
    cls_ok = False

    # 1. LCP validation
    if metrics.lcp_seconds is None or not math.isfinite(metrics.lcp_seconds):
        reasons.append("LCP metric missing or non-finite")
    elif metrics.lcp_seconds > threshold_lcp:
        reasons.append(
            f"LCP ({metrics.lcp_seconds:.3f}s) exceeded threshold ({threshold_lcp:.1f}s)"
        )
    else:
        lcp_ok = True

    # 2. CLS validation
    if metrics.cls_score is None or not math.isfinite(metrics.cls_score):
        reasons.append("CLS metric missing or non-finite")
    elif metrics.cls_score > threshold_cls:
        reasons.append(
            f"CLS ({metrics.cls_score:.4f}) exceeded threshold ({threshold_cls:.2f})"
        )
    else:
        cls_ok = True

    if lcp_ok and cls_ok:
        verdict = "PASS"
        reasons.append(
            f"LCP ({metrics.lcp_seconds:.3f}s <= {threshold_lcp:.1f}s) and "
            f"CLS ({metrics.cls_score:.4f} <= {threshold_cls:.2f}) within thresholds"
        )
    elif metrics.lcp_seconds is None or metrics.cls_score is None:
        verdict = "METRIC_MISSING"
    else:
        verdict = "FAIL"

    return ThresholdVerdict(
        verdict=verdict,
        reasons=reasons,
        lcp_passed=lcp_ok,
        cls_passed=cls_ok,
    )


def collect_system_profile() -> dict[str, Any]:
    """Capture hardware, OS, and toolchain versions without private info."""
    node_version = "unknown"
    try:
        proc = subprocess.run(
            ["node", "--version"],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0:
            node_version = proc.stdout.strip()
    except Exception:
        pass

    lighthouse_version = "unknown"
    lh_cmd = find_lighthouse_command()
    if lh_cmd:
        try:
            proc = subprocess.run(
                [*lh_cmd, "--version"],
                capture_output=True,
                text=True,
                check=False,
            )
            if proc.returncode == 0:
                lighthouse_version = proc.stdout.strip()
        except Exception:
            pass

    return {
        "os": platform.system(),
        "osRelease": platform.release(),
        "osVersion": platform.version(),
        "architecture": platform.machine(),
        "pythonVersion": platform.python_version(),
        "nodeVersion": node_version,
        "lighthouseVersion": lighthouse_version,
    }


def find_chrome_executable() -> str | None:
    """Locate Chrome / Chromium executable on host."""
    env_path = os.environ.get("CHROME_PATH")
    if env_path and Path(env_path).is_file():
        return env_path

    candidates = [
        "google-chrome",
        "google-chrome-stable",
        "chromium",
        "chromium-browser",
        "chrome",
        "msedge",
    ]
    for name in candidates:
        found = shutil.which(name)
        if found:
            return found
    return None


def find_lighthouse_command() -> list[str] | None:
    """Locate Lighthouse CLI binary or local package."""
    binary = shutil.which("lighthouse")
    if binary:
        return [binary]

    local_lh = ROOT_DIR / "node_modules" / ".bin" / "lighthouse"
    if local_lh.is_file():
        return [str(local_lh)]

    return None


@contextmanager
def launch_preview_server(
    port: int = DEFAULT_PORT,
    timeout_seconds: float = DEFAULT_STARTUP_TIMEOUT_SECONDS,
) -> Generator[str, None, None]:
    """Launch T052 temporary loopback preview server and ensure clean teardown."""
    if not TEST_SERVER_SCRIPT.is_file():
        raise FileNotFoundError(f"T052 test server script not found at {TEST_SERVER_SCRIPT}")

    dist_index = ROOT_DIR / "frontend" / "dist" / "index.html"
    if not dist_index.is_file():
        raise RuntimeError(
            f"Frontend distribution build missing ({dist_index}). "
            "Run 'npm run build' before executing performance harness."
        )

    env = {**os.environ, "PYTHONPATH": str(ROOT_DIR)}
    cmd = [sys.executable, str(TEST_SERVER_SCRIPT), "--port", str(port)]

    proc = subprocess.Popen(
        cmd,
        cwd=ROOT_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    health_url = f"http://127.0.0.1:{port}/api/v1/health"
    preview_url = f"http://127.0.0.1:{port}/"
    ready = False
    start_time = time.monotonic()

    try:
        while time.monotonic() - start_time < timeout_seconds:
            if proc.poll() is not None:
                _, stderr = proc.communicate(timeout=1.0)
                raise RuntimeError(
                    f"Preview server exited prematurely with code {proc.returncode}: {stderr}"
                )
            try:
                with urllib.request.urlopen(health_url, timeout=1.0) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        if data.get("status") == "OK":
                            ready = True
                            break
            except Exception:
                time.sleep(0.2)

        if not ready:
            raise TimeoutError(
                f"Preview server failed to become ready at {health_url} within {timeout_seconds}s"
            )

        yield preview_url

    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=2.0)


def create_sanitized_artifact(
    *,
    preview_url: str,
    metrics: PerformanceMetrics,
    verdict: ThresholdVerdict,
    profile: dict[str, Any],
    tool_exit_code: int | None,
    error_category: str | None,
    browser_channel: str,
    artifact_path: Path,
    threshold_lcp: float = THRESHOLD_LCP_SECONDS,
    threshold_cls: float = THRESHOLD_CLS,
) -> dict[str, Any]:
    """Assemble sanitized diagnostic artifact payload with no credentials or user content."""
    return {
        "taskId": TASK_ID,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "runnerVersion": RUNNER_VERSION,
        "previewUrl": sanitize_loopback_url(preview_url),
        "browserChannel": browser_channel,
        "environment": profile,
        "buildMode": "production-preview",
        "cacheProfile": "deterministic-fresh",
        "viewportProfile": "desktop-1440x900",
        "metrics": metrics.to_dict(),
        "thresholds": {
            "lcpSeconds": threshold_lcp,
            "clsScore": threshold_cls,
        },
        "verdict": verdict.verdict,
        "verdictReasons": verdict.reasons,
        "toolExitCode": tool_exit_code,
        "errorCategory": error_category,
        "artifactPath": str(artifact_path),
        "labMeasurementNotice": (
            "Local lab metrics measured in synthetic preview environment; "
            "does not represent production user sample data."
        ),
    }


def write_artifact(artifact: dict[str, Any], path: Path) -> None:
    """Save artifact file safely."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")


def run_ui_performance(
    *,
    report_file: Path | None = None,
    port: int = DEFAULT_PORT,
    preview_url: str | None = None,
    artifact_path: Path = DEFAULT_ARTIFACT_PATH,
    threshold_lcp: float = THRESHOLD_LCP_SECONDS,
    threshold_cls: float = THRESHOLD_CLS,
    skip_preview: bool = False,
) -> int:
    """Execute UI performance measurement harness fail-closed."""
    print("=================================================================")
    print(" T064 LOCAL LIGHTHOUSE UI PERFORMANCE HARNESS")
    print("=================================================================")

    profile = collect_system_profile()
    browser_executable = find_chrome_executable()
    browser_name = Path(browser_executable).name if browser_executable else "unknown"

    # Case A: Offline / Fixture report evaluation
    if report_file is not None:
        print(f"\n[Fixture Mode] Evaluating provided Lighthouse report: {report_file}")
        if not report_file.is_file():
            print(f"ERROR: Specified report file does not exist: {report_file}")
            return EXIT_SETUP

        try:
            report_data = json.loads(report_file.read_text(encoding="utf-8"))
        except Exception as err:
            print(f"ERROR: Failed to parse Lighthouse report JSON: {err}")
            return EXIT_SETUP

        metrics = parse_metrics_from_lhr(report_data)
        verdict = evaluate_thresholds(metrics, threshold_lcp, threshold_cls)
        target_url = preview_url or f"http://127.0.0.1:{port}/"

        artifact = create_sanitized_artifact(
            preview_url=target_url,
            metrics=metrics,
            verdict=verdict,
            profile=profile,
            tool_exit_code=0,
            error_category=None if verdict.verdict == "PASS" else verdict.verdict,
            browser_channel=browser_name,
            artifact_path=artifact_path,
            threshold_lcp=threshold_lcp,
            threshold_cls=threshold_cls,
        )
        write_artifact(artifact, artifact_path)
        print(f"  Artifact written: {artifact_path}")
        print(f"  Verdict: {verdict.verdict}")
        for r in verdict.reasons:
            print(f"    - {r}")

        return EXIT_SUCCESS if verdict.verdict == "PASS" else EXIT_VIOLATION

    # Case B: Live run against preview server
    print("\n[1/4] Checking environment and required tools...")
    print(f"  Operating System: {profile['os']} ({profile['osVersion']})")
    print(f"  Python: {profile['pythonVersion']}")
    print(f"  Node: {profile['nodeVersion']}")
    print(f"  Browser: {browser_name} ({browser_executable or 'not found'})")

    lh_cmd = find_lighthouse_command()
    if lh_cmd is None:
        print("\n  [SETUP_PENDING] Lighthouse CLI is not installed or available on PATH.")
        print("  In accordance with CONSTRAINTS.md, missing tooling is reported as SETUP_PENDING.")
        empty_metrics = PerformanceMetrics(
            lcp_seconds=None, cls_score=None, lcp_source="none", cls_source="none"
        )
        verdict = ThresholdVerdict(
            verdict="SETUP_PENDING",
            reasons=["Lighthouse CLI is not installed or available in this environment"],
            lcp_passed=False,
            cls_passed=False,
        )
        artifact = create_sanitized_artifact(
            preview_url=preview_url or f"http://127.0.0.1:{port}/",
            metrics=empty_metrics,
            verdict=verdict,
            profile=profile,
            tool_exit_code=None,
            error_category="MISSING_LIGHTHOUSE",
            browser_channel=browser_name,
            artifact_path=artifact_path,
            threshold_lcp=threshold_lcp,
            threshold_cls=threshold_cls,
        )
        write_artifact(artifact, artifact_path)
        return EXIT_SETUP

    if browser_executable is None:
        print("\n  [SETUP_PENDING] Chrome or Chromium browser executable not found.")
        print("  In accordance with CONSTRAINTS.md, missing browser is reported as SETUP_PENDING.")
        empty_metrics = PerformanceMetrics(
            lcp_seconds=None, cls_score=None, lcp_source="none", cls_source="none"
        )
        verdict = ThresholdVerdict(
            verdict="SETUP_PENDING",
            reasons=["Chrome/Chromium browser executable not found on host"],
            lcp_passed=False,
            cls_passed=False,
        )
        artifact = create_sanitized_artifact(
            preview_url=preview_url or f"http://127.0.0.1:{port}/",
            metrics=empty_metrics,
            verdict=verdict,
            profile=profile,
            tool_exit_code=None,
            error_category="MISSING_BROWSER",
            browser_channel=browser_name,
            artifact_path=artifact_path,
            threshold_lcp=threshold_lcp,
            threshold_cls=threshold_cls,
        )
        write_artifact(artifact, artifact_path)
        return EXIT_SETUP

    dist_index = ROOT_DIR / "frontend" / "dist" / "index.html"
    if not dist_index.is_file():
        print(f"\n  [SETUP_PENDING] Frontend build missing at {dist_index}.")
        print("  Execute 'npm run build' before running UI performance benchmark.")
        empty_metrics = PerformanceMetrics(
            lcp_seconds=None, cls_score=None, lcp_source="none", cls_source="none"
        )
        verdict = ThresholdVerdict(
            verdict="SETUP_PENDING",
            reasons=[f"Frontend distribution build missing ({dist_index})"],
            lcp_passed=False,
            cls_passed=False,
        )
        artifact = create_sanitized_artifact(
            preview_url=preview_url or f"http://127.0.0.1:{port}/",
            metrics=empty_metrics,
            verdict=verdict,
            profile=profile,
            tool_exit_code=None,
            error_category="MISSING_DIST_BUILD",
            browser_channel=browser_name,
            artifact_path=artifact_path,
            threshold_lcp=threshold_lcp,
            threshold_cls=threshold_cls,
        )
        write_artifact(artifact, artifact_path)
        return EXIT_SETUP

    # Step 2: Lifecycle context - startup preview server
    print("\n[2/4] Initializing temporary loopback preview server...")
    with tempfile.TemporaryDirectory(prefix="t064-lh-") as lh_tmp_dir:
        report_output_path = Path(lh_tmp_dir) / "report.json"

        try:
            if skip_preview and preview_url:
                target_url = preview_url
                print(f"  Using existing preview at {target_url}")
                execute_lighthouse(lh_cmd, target_url, report_output_path, browser_executable)
            else:
                with launch_preview_server(port=port) as active_url:
                    print(f"  Preview server ready at {active_url}")
                    print("\n[3/4] Executing Lighthouse audit against local preview...")
                    execute_lighthouse(lh_cmd, active_url, report_output_path, browser_executable)
                    target_url = active_url

        except Exception as err:
            print(f"ERROR: Preview lifecycle or Lighthouse invocation failed: {err}")
            empty_metrics = PerformanceMetrics(
                lcp_seconds=None, cls_score=None, lcp_source="none", cls_source="none"
            )
            verdict = ThresholdVerdict(
                verdict="TOOL_FAILED",
                reasons=[str(err)],
                lcp_passed=False,
                cls_passed=False,
            )
            artifact = create_sanitized_artifact(
                preview_url=f"http://127.0.0.1:{port}/",
                metrics=empty_metrics,
                verdict=verdict,
                profile=profile,
                tool_exit_code=1,
                error_category="PREVIEW_OR_TOOL_FAILURE",
                browser_channel=browser_name,
                artifact_path=artifact_path,
                threshold_lcp=threshold_lcp,
                threshold_cls=threshold_cls,
            )
            write_artifact(artifact, artifact_path)
            return EXIT_SETUP

        # Step 4: Metric extraction & verdict
        print("\n[4/4] Parsing metrics and evaluating thresholds...")
        if not report_output_path.is_file():
            print("ERROR: Lighthouse failed to generate output report file.")
            return EXIT_SETUP

        try:
            report_data = json.loads(report_output_path.read_text(encoding="utf-8"))
        except Exception as err:
            print(f"ERROR: Failed to read Lighthouse output JSON: {err}")
            return EXIT_SETUP

        metrics = parse_metrics_from_lhr(report_data)
        verdict = evaluate_thresholds(metrics, threshold_lcp, threshold_cls)

        artifact = create_sanitized_artifact(
            preview_url=target_url,
            metrics=metrics,
            verdict=verdict,
            profile=profile,
            tool_exit_code=0,
            error_category=None if verdict.verdict == "PASS" else verdict.verdict,
            browser_channel=browser_name,
            artifact_path=artifact_path,
            threshold_lcp=threshold_lcp,
            threshold_cls=threshold_cls,
        )
        write_artifact(artifact, artifact_path)
        print(f"  Artifact written: {artifact_path}")
        print(f"  Verdict: {verdict.verdict}")
        for r in verdict.reasons:
            print(f"    - {r}")

        return EXIT_SUCCESS if verdict.verdict == "PASS" else EXIT_VIOLATION


def execute_lighthouse(
    lh_cmd: list[str],
    target_url: str,
    output_path: Path,
    chrome_path: str | None,
) -> None:
    """Invoke Lighthouse CLI subprocess with strict lab flags and timeout."""
    cmd = [
        *lh_cmd,
        target_url,
        "--output=json",
        f"--output-path={output_path}",
        "--chrome-flags=--headless=new --no-sandbox --disable-gpu --disable-dev-shm-usage",
        "--only-categories=performance",
        "--throttling-method=provided",
        "--quiet",
    ]
    env = os.environ.copy()
    if chrome_path:
        env["CHROME_PATH"] = chrome_path

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        timeout=120.0,
        env=env,
    )

    if proc.returncode != 0:
        raise RuntimeError(
            f"Lighthouse exited with code {proc.returncode}: {proc.stderr.strip() or proc.stdout.strip()}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="T064 local Lighthouse UI performance harness")
    parser.add_argument(
        "--report-file",
        type=Path,
        default=None,
        help="Path to pre-captured Lighthouse JSON report for offline/fixture threshold verification",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Loopback preview port (default {DEFAULT_PORT})",
    )
    parser.add_argument(
        "--preview-url",
        type=str,
        default=None,
        help="Override preview target URL (must target loopback 127.0.0.1 or localhost)",
    )
    parser.add_argument(
        "--artifact-path",
        type=Path,
        default=DEFAULT_ARTIFACT_PATH,
        help=f"Path to emit evidence JSON artifact (default {DEFAULT_ARTIFACT_PATH})",
    )
    parser.add_argument(
        "--threshold-lcp",
        type=float,
        default=THRESHOLD_LCP_SECONDS,
        help=f"LCP threshold in seconds (default {THRESHOLD_LCP_SECONDS})",
    )
    parser.add_argument(
        "--threshold-cls",
        type=float,
        default=THRESHOLD_CLS,
        help=f"CLS threshold (default {THRESHOLD_CLS})",
    )
    parser.add_argument(
        "--skip-preview",
        action="store_true",
        help="Skip starting local preview server (targets existing running preview)",
    )

    args = parser.parse_args()

    return run_ui_performance(
        report_file=args.report_file,
        port=args.port,
        preview_url=args.preview_url,
        artifact_path=args.artifact_path,
        threshold_lcp=args.threshold_lcp,
        threshold_cls=args.threshold_cls,
        skip_preview=args.skip_preview,
    )


if __name__ == "__main__":
    sys.exit(main())

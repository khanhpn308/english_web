"""T090 candidate supply-chain verification; caller MUST own independent trust pins.

This module never approves an image. Signed registry attestations must be
verified before any independent Host operator chooses to sign an approval.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import stat
import subprocess
from pathlib import Path

_SHA = re.compile(r"[0-9a-f]{64}\Z")
_IMAGE = re.compile(r"ghcr\.io/[a-z0-9._/-]+@sha256:([0-9a-f]{64})\Z")
_PREDICATES = (
    "https://slsa.dev/provenance/v1",
    "https://spdx.dev/Document/v2.3",
)


class SupplyChainBlocked(RuntimeError):
    """A missing or inconsistent fact can never become implicit approval."""


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _trusted_file(path: Path, *, max_bytes: int = 16_000_000) -> bytes:
    if not path.is_absolute() or path.is_symlink():
        raise SupplyChainBlocked("T090 SUPPLY_CHAIN_BLOCKED: non-independent file path")
    try:
        st = path.stat()
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_size > max_bytes:
            raise SupplyChainBlocked("T090 SUPPLY_CHAIN_BLOCKED: invalid evidence file")
        return path.read_bytes()
    except OSError as error:
        raise SupplyChainBlocked("T090 SUPPLY_CHAIN_BLOCKED: evidence unavailable") from error


def verify_file_digest(path: Path, expected_sha256: str) -> bytes:
    if not _SHA.fullmatch(expected_sha256):
        raise SupplyChainBlocked("T090 SUPPLY_CHAIN_BLOCKED: missing SHA-256 trust pin")
    content = _trusted_file(path, max_bytes=1_000_000_000)
    if not hmac.compare_digest(_sha(content), expected_sha256):
        raise SupplyChainBlocked("T090 SUPPLY_CHAIN_BLOCKED: artifact digest mismatch")
    return content


def python_lock_is_hash_complete(path: Path) -> bool:
    """Conservative check: every pinned requirement must have a pip SHA-256 hash.

    Keep this independent of pip-compile: version-only locks do NOT satisfy it.
    """
    lines = _trusted_file(path).decode("utf-8").splitlines()
    requirements: list[str] = []
    current = ""
    for source in lines:
        line = source.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith(("-r", "--", "-e", ".", "git+", "http:", "https:")):
            return False
        current += " " + line.rstrip("\\").strip()
        if source.rstrip().endswith("\\"):
            continue
        requirements.append(current.strip())
        current = ""
    if current or not requirements:
        return False
    return all(
        re.match(r"^[a-zA-Z0-9_.-]+(?:\[[a-zA-Z0-9_,.-]+\])?==[a-zA-Z0-9_.!+ -]+", req)
        and re.search(r"--hash=sha256:[0-9a-f]{64}(?:\s|$)", req)
        for req in requirements
    )


def npm_lock_has_integrities(path: Path) -> bool:
    try:
        lock = json.loads(_trusted_file(path))
        packages = lock["packages"]
        return (
            isinstance(packages, dict)
            and bool(packages)
            and all(
                name == ""
                or (
                    isinstance(item, dict)
                    and (
                        isinstance(item.get("integrity"), str)
                        and item["integrity"].startswith("sha512-")
                        or item.get("link") is True
                    )
                )
                for name, item in packages.items()
            )
        )
    except (KeyError, TypeError, ValueError, UnicodeError):
        return False


def verify_spdx_file(path: Path, expected_sha256: str) -> dict[str, object]:
    try:
        payload = json.loads(verify_file_digest(path, expected_sha256))
    except (UnicodeError, ValueError) as error:
        raise SupplyChainBlocked("T090 SUPPLY_CHAIN_BLOCKED: invalid SBOM JSON") from error
    if (
        not isinstance(payload, dict)
        or payload.get("spdxVersion") != "SPDX-2.3"
        or payload.get("dataLicense") != "CC0-1.0"
        or not isinstance(payload.get("packages"), list)
        or len(payload["packages"]) == 0
        or not isinstance(payload.get("documentNamespace"), str)
        or not isinstance(payload.get("creationInfo"), dict)
    ):
        raise SupplyChainBlocked("T090 SUPPLY_CHAIN_BLOCKED: incomplete SBOM")
    if not all(
        isinstance(package, dict)
        and isinstance(package.get("name"), str)
        and package.get("name")
        and isinstance(package.get("SPDXID"), str)
        for package in payload["packages"]
    ):
        raise SupplyChainBlocked("T090 SUPPLY_CHAIN_BLOCKED: invalid SBOM package entries")
    return payload


def verify_registry_attestations(
    *,
    image_reference: str,
    repository: str,
    signer_workflow: str,
    source_sha: str,
    source_ref: str,
    gh_executable: Path,
    expected_gh_sha256: str,
) -> tuple[dict[str, object], dict[str, object]]:
    """Verify real Sigstore bundles with an independently pinned gh executable.

    No JSON document supplied by the Worker is accepted as attestation proof.
    All values in this call MUST originate from independently approved Host
    configuration, not repository/Worker arguments.
    """
    match = _IMAGE.fullmatch(image_reference)
    if (
        match is None
        or not re.fullmatch(r"[0-9a-f]{40}", source_sha)
        or not re.fullmatch(r"[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+", repository)
        or not signer_workflow.startswith(repository + "/.github/workflows/")
        or not source_ref.startswith("refs/")
    ):
        raise SupplyChainBlocked("T090 SUPPLY_CHAIN_BLOCKED: invalid trust identity")
    verify_file_digest(gh_executable, expected_gh_sha256)
    statements: list[dict[str, object]] = []
    for predicate in _PREDICATES:
        argv = [
            str(gh_executable),
            "attestation",
            "verify",
            "oci://" + image_reference,
            "--repo",
            repository,
            "--signer-workflow",
            signer_workflow,
            "--source-digest",
            source_sha,
            "--source-ref",
            source_ref,
            "--predicate-type",
            predicate,
            "--format",
            "json",
        ]
        try:
            proc = subprocess.run(
                argv,
                shell=False,
                capture_output=True,
                text=True,
                timeout=90,
                check=False,
                env={"PATH": "/usr/bin:/bin", "HOME": "/nonexistent", "GH_PROMPT_DISABLED": "1"},
            )
            if proc.returncode or len(proc.stdout) > 2_000_000:
                raise SupplyChainBlocked("T090 SUPPLY_CHAIN_BLOCKED: signed attestation rejected")
            results = json.loads(proc.stdout)
        except (OSError, subprocess.TimeoutExpired, UnicodeError, ValueError) as error:
            raise SupplyChainBlocked(
                "T090 SUPPLY_CHAIN_BLOCKED: attestation verification failed"
            ) from error
        if not isinstance(results, list) or not results:
            raise SupplyChainBlocked("T090 SUPPLY_CHAIN_BLOCKED: no verified attestations")
        accepted: dict[str, object] | None = None
        for result in results:
            if not isinstance(result, dict):
                continue
            verification = result.get("verificationResult")
            if not isinstance(verification, dict):
                continue
            statement = verification.get("statement")
            if not isinstance(statement, dict) or statement.get("predicateType") != predicate:
                continue
            subjects = statement.get("subject")
            if not isinstance(subjects, list):
                continue
            if any(
                isinstance(subj, dict)
                and subj.get("name") == image_reference.rsplit("@", 1)[0]
                and isinstance(subj.get("digest"), dict)
                and subj["digest"].get("sha256") == match.group(1)
                for subj in subjects
            ):
                accepted = statement
                break
        if accepted is None:
            raise SupplyChainBlocked("T090 SUPPLY_CHAIN_BLOCKED: attested image subject mismatch")
        statements.append(accepted)
    return statements[0], statements[1]



def require_production_build_inputs(
    *,
    requirements: Path,
    npm: Path,
    base_pins: Path,
    osv_pins: Path,
    os_package_snapshot: Path | None,
) -> None:
    """Host admission prerequisite; candidate declarations are never approval.

    This checks basic immutable-input completeness only. A successful return
    is NOT publisher, OCI, SBOM or independent signature verification.
    """
    if not python_lock_is_hash_complete(requirements):
        raise SupplyChainBlocked("T090 SUPPLY_CHAIN_BLOCKED: Python wheel hashes incomplete")
    if not npm_lock_has_integrities(npm):
        raise SupplyChainBlocked("T090 SUPPLY_CHAIN_BLOCKED: npm integrities incomplete")
    if os_package_snapshot is None:
        raise SupplyChainBlocked("T090 SUPPLY_CHAIN_BLOCKED: OS package snapshot missing")
    try:
        base = json.loads(_trusted_file(base_pins))
        osv = json.loads(_trusted_file(osv_pins))
        snapshot = json.loads(_trusted_file(os_package_snapshot))
    except (ValueError, UnicodeError, TypeError) as error:
        raise SupplyChainBlocked("T090 SUPPLY_CHAIN_BLOCKED: input evidence malformed") from error
    if (
        not isinstance(base, dict)
        or base.get("approval") != "independently-approved"
        or base.get("platform") != "linux/amd64"
        or not all(
            isinstance(base.get(name), str)
            and re.fullmatch(r"[a-z0-9._/-]+@sha256:[0-9a-f]{64}", base[name])
            for name in ("python", "node")
        )
    ):
        raise SupplyChainBlocked("T090 SUPPLY_CHAIN_BLOCKED: unapproved base images")
    if (
        not isinstance(osv, dict)
        or osv.get("approved") is not True
        or not isinstance(osv.get("archive_sha256"), dict)
        or not all(
            isinstance(osv["archive_sha256"].get(name), str)
            and _SHA.fullmatch(osv["archive_sha256"][name])
            for name in ("npm", "PyPI")
        )
    ):
        raise SupplyChainBlocked("T090 SUPPLY_CHAIN_BLOCKED: OSV archives unapproved")
    if (
        not isinstance(snapshot, dict)
        or snapshot.get("approved") is not True
        or not isinstance(snapshot.get("snapshot_sha256"), str)
        or not _SHA.fullmatch(snapshot["snapshot_sha256"])
        or not isinstance(snapshot.get("packages"), dict)
        or not snapshot["packages"]
        or not all(
            isinstance(name, str)
            and isinstance(record, dict)
            and isinstance(record.get("version"), str)
            and record["version"]
            and isinstance(record.get("artifact_sha256"), str)
            and _SHA.fullmatch(record["artifact_sha256"])
            for name, record in snapshot["packages"].items()
        )
    ):
        raise SupplyChainBlocked("T090 SUPPLY_CHAIN_BLOCKED: OS package snapshot incomplete")


def inspect_candidate_locks(requirements: Path, npm: Path) -> dict[str, bool]:
    """Diagnostic only: this report is NEVER approval evidence."""
    return {
        "python_artifact_hashes_pinned": python_lock_is_hash_complete(requirements),
        "npm_package_integrities_present": npm_lock_has_integrities(npm),
    }

"""Adversarial tests for Host-side candidate supply-chain checks."""

import hashlib
import json
import subprocess
from typing import Any
from pathlib import Path

import pytest
from scripts.t090_supply_chain import (
    SupplyChainBlocked,
    inspect_candidate_locks,
    verify_file_digest,
    verify_registry_attestations,
    verify_spdx_file,
)


def test_t090_supply_chain_candidate_lock_does_not_claim_version_pin_is_hash(
    tmp_path: Path,
) -> None:
    requirements = tmp_path / "requirements.lock"
    npm = tmp_path / "package-lock.json"
    requirements.write_text("pytest==9.1.1\n")
    npm.write_text('{"packages": {"": {}, "node_modules/demo": {"integrity": "sha512-abc"}}}')
    evidence = inspect_candidate_locks(requirements, npm)
    assert evidence == {
        "python_artifact_hashes_pinned": False,
        "npm_package_integrities_present": True,
    }
    requirements.write_text("pytest==9.1.1 --hash=sha256:" + "a" * 64 + "\n")
    assert inspect_candidate_locks(requirements, npm)["python_artifact_hashes_pinned"]


def test_t090_supply_chain_sbom_requires_real_pinned_bytes(tmp_path: Path) -> None:
    sbom = tmp_path / "image.spdx.json"
    payload = {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "documentNamespace": "https://example.invalid/sbom/1",
        "creationInfo": {"creators": ["Tool: synthetic"]},
        "packages": [{"name": "demo", "SPDXID": "SPDXRef-demo"}],
    }
    sbom.write_text(json.dumps(payload))
    pin = hashlib.sha256(sbom.read_bytes()).hexdigest()
    assert verify_spdx_file(sbom, pin)["spdxVersion"] == "SPDX-2.3"
    with pytest.raises(SupplyChainBlocked):
        verify_spdx_file(sbom, "a" * 64)
    sbom.write_text("{}")
    with pytest.raises(SupplyChainBlocked):
        verify_spdx_file(sbom, hashlib.sha256(sbom.read_bytes()).hexdigest())
    with pytest.raises(SupplyChainBlocked):
        verify_file_digest(sbom, "not-a-hash")
    sbom.unlink()
    sbom.symlink_to(tmp_path / "missing")
    with pytest.raises(SupplyChainBlocked):
        verify_file_digest(sbom, pin)


def test_t090_supply_chain_attestation_requires_pinned_gh_and_2_predicates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gh = tmp_path / "trusted-gh"
    gh.write_text("synthetic-gh-binary")
    gh_pin = hashlib.sha256(gh.read_bytes()).hexdigest()
    image = "ghcr.io/khanhpn308/english_web/t090-verifier@sha256:" + "a" * 64
    source = "b" * 64
    source_sha = "b" * 40
    commands: list[list[str]] = []

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        commands.append(argv)
        assert kwargs["shell"] is False
        predicate = argv[argv.index("--predicate-type") + 1]
        result = [
            {
                "verificationResult": {
                    "statement": {
                        "predicateType": predicate,
                        "subject": [
                            {"name": image.rsplit("@", 1)[0], "digest": {"sha256": "a" * 64}}
                        ],
                    }
                }
            }
        ]
        return subprocess.CompletedProcess(argv, 0, json.dumps(result), "")

    monkeypatch.setattr("scripts.t090_supply_chain.subprocess.run", fake_run)
    args: dict[str, Any] = {
        "image_reference": image,
        "repository": "khanhpn308/english_web",
        "signer_workflow": "khanhpn308/english_web/.github/workflows/t090-image-attestation.yml",
        "source_sha": source_sha,
        "source_ref": "refs/heads/feature/t090-provider-isolation-adjudication",
        "gh_executable": gh,
        "expected_gh_sha256": gh_pin,
    }
    provenance, sbom = verify_registry_attestations(**args)
    assert provenance["predicateType"] == "https://slsa.dev/provenance/v1"
    assert sbom["predicateType"] == "https://spdx.dev/Document/v2.3"
    assert len(commands) == 2
    with pytest.raises(SupplyChainBlocked):
        verify_registry_attestations(**{**args, "expected_gh_sha256": "0" * 64})
    with pytest.raises(SupplyChainBlocked):
        verify_registry_attestations(**{**args, "source_sha": source})
    gh_alias = tmp_path / "fake-gh-alias"
    gh_alias.symlink_to(gh)
    with pytest.raises(SupplyChainBlocked):
        verify_registry_attestations(**{**args, "gh_executable": gh_alias})


def test_t090_supply_chain_rejects_wrong_attested_image(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gh = tmp_path / "trusted-gh"
    gh.write_text("synthetic-gh-binary")

    def forged_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        predicate = argv[argv.index("--predicate-type") + 1]
        forged = [
            {
                "verificationResult": {
                    "statement": {
                        "predicateType": predicate,
                        "subject": [
                            {"name": "ghcr.io/attacker/other", "digest": {"sha256": "c" * 64}}
                        ],
                    }
                }
            }
        ]
        return subprocess.CompletedProcess(argv, 0, json.dumps(forged), "")

    monkeypatch.setattr("scripts.t090_supply_chain.subprocess.run", forged_run)
    with pytest.raises(SupplyChainBlocked, match="subject mismatch"):
        verify_registry_attestations(
            image_reference="ghcr.io/khanhpn308/english_web/t090-verifier@sha256:" + "a" * 64,
            repository="khanhpn308/english_web",
            signer_workflow="khanhpn308/english_web/.github/workflows/t090-image-attestation.yml",
            source_sha="b" * 40,
            source_ref="refs/heads/feature/t090-provider-isolation-adjudication",
            gh_executable=gh,
            expected_gh_sha256=hashlib.sha256(gh.read_bytes()).hexdigest(),
        )


def test_t090_production_inputs_reject_candidate_pins_and_missing_os_snapshot(
    tmp_path: Path,
) -> None:
    from scripts.t090_supply_chain import require_production_build_inputs

    requirements = tmp_path / "requirements.lock"
    npm = tmp_path / "package-lock.json"
    bases = tmp_path / "base-images.json"
    osv = tmp_path / "osv.json"
    snapshot = tmp_path / "os-packages.json"
    requirements.write_text("pytest==9.1.1 --hash=sha256:" + "a" * 64 + "\n")
    npm.write_text(
        '{"packages":{"":{"name":"demo"},"node_modules/demo":{"integrity":"sha512-abc"}}}'
    )
    bases.write_text(
        json.dumps(
            {
                "platform": "linux/amd64",
                "approval": "candidate-only",
                "python": "python@sha256:" + "b" * 64,
                "node": "node@sha256:" + "c" * 64,
            }
        )
    )
    osv.write_text(
        json.dumps(
            {
                "approved": False,
                "archive_sha256": {"npm": "d" * 64, "PyPI": "e" * 64},
            }
        )
    )
    snapshot.write_text(
        json.dumps(
            {
                "approved": True,
                "snapshot_sha256": "f" * 64,
                "packages": {"curl": {"version": "1.0", "artifact_sha256": "0" * 64}},
            }
        )
    )
    kwargs = {
        "requirements": requirements,
        "npm": npm,
        "base_pins": bases,
        "osv_pins": osv,
        "os_package_snapshot": snapshot,
    }
    with pytest.raises(SupplyChainBlocked, match="unapproved base"):
        require_production_build_inputs(**kwargs)
    bases.write_text(bases.read_text().replace("candidate-only", "independently-approved"))
    with pytest.raises(SupplyChainBlocked, match="OSV archives unapproved"):
        require_production_build_inputs(**kwargs)
    osv.write_text(osv.read_text().replace("false", "true"))
    with pytest.raises(SupplyChainBlocked, match="OS package snapshot missing"):
        require_production_build_inputs(**{**kwargs, "os_package_snapshot": None})
    snapshot.write_text(snapshot.read_text().replace('"artifact_sha256":', '"invalid_digest":'))
    with pytest.raises(SupplyChainBlocked, match="OS package snapshot incomplete"):
        require_production_build_inputs(**kwargs)
    snapshot.write_text(
        json.dumps(
            {
                "approved": True,
                "snapshot_sha256": "f" * 64,
                "packages": {"curl": {"version": "1.0", "artifact_sha256": "0" * 64}},
            }
        )
    )
    require_production_build_inputs(**kwargs)
    requirements.write_text("pytest==9.1.1\n")
    with pytest.raises(SupplyChainBlocked, match="Python wheel hashes"):
        require_production_build_inputs(**kwargs)


def test_t090_candidate_osv_snapshot_requires_immutable_signed_source_identity(
    tmp_path: Path,
) -> None:
    from scripts.t090_supply_chain import validate_candidate_osv_snapshot_source

    snapshot_file = tmp_path / "snapshot.json"
    pins_file = tmp_path / "pins.json"
    hashes = {"npm": "a" * 64, "PyPI": "b" * 64}
    pins_file.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "scope": "candidate-only",
                "approved": False,
                "archive_sha256": hashes,
            }
        )
    )
    valid = {
        "schema_version": 1,
        "scope": "candidate-only",
        "approved": False,
        "image_reference": "ghcr.io/khanhpn308/english_web/t090-verifier@sha256:" + "c" * 64,
        "source_repository": "khanhpn308/english_web",
        "source_sha": "d" * 40,
        "source_ref": "refs/heads/feature/t090-provider-isolation-adjudication",
        "signer_workflow": (
            "khanhpn308/english_web/.github/workflows/t090-image-attestation.yml"
        ),
        "osv_archive_sha256": hashes,
    }
    snapshot_file.write_text(json.dumps(valid))
    verified = validate_candidate_osv_snapshot_source(snapshot_file, pins_file)
    assert verified["image"] == valid["image_reference"]
    for bad in (
        {**valid, "image_reference": "ghcr.io/demo:latest"},
        {**valid, "approved": True},
        {**valid, "source_sha": "0" * 64},
        {**valid, "signer_workflow": "attacker/workflow.yml"},
        {**valid, "osv_archive_sha256": {**hashes, "PyPI": "f" * 64}},
    ):
        snapshot_file.write_text(json.dumps(bad))
        with pytest.raises(SupplyChainBlocked, match="snapshot source/pins mismatch"):
            validate_candidate_osv_snapshot_source(snapshot_file, pins_file)
    snapshot_file.write_text(json.dumps(valid))
    pins_file.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "scope": "candidate-only",
                "approved": False,
                "archive_sha256": {**hashes, "npm": "e" * 64},
            }
        )
    )
    with pytest.raises(SupplyChainBlocked, match="snapshot source/pins mismatch"):
        validate_candidate_osv_snapshot_source(snapshot_file, pins_file)

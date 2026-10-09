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

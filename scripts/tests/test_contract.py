import json
import subprocess
from pathlib import Path

import pytest
from scripts.export_contract import build_contract


def test_full_schema_matches_checked_in(tmp_path):
    # 1. Freshly generate full OpenAPI contract
    openapi_sorted = build_contract()

    # 2. Compare against checked-in artifact
    checked_in_json_path = Path("contracts/openapi.json")
    if not checked_in_json_path.exists():
        pytest.fail("Checked-in openapi.json does not exist. Run export:contract.")

    checked_in_json = json.loads(checked_in_json_path.read_text())

    # Compare structurally
    # fmt: off
    assert openapi_sorted == checked_in_json, "Generated OpenAPI schema drifted from checked-in version! Please run export:contract."  # noqa: E501
    # fmt: on

    # 3. Generate TypeScript into temporary output
    temp_openapi = tmp_path / "openapi.json"
    temp_openapi.write_text(json.dumps(openapi_sorted, indent=2) + "\n")

    temp_ts = tmp_path / "generated.ts"
    subprocess.run(
        ["npx", "openapi-typescript", str(temp_openapi), "-o", str(temp_ts)],
        check=True,
        stdout=subprocess.DEVNULL,
    )

    # 4. Compare TS output against checked-in generated.ts
    checked_in_ts_path = Path("frontend/src/shared/api/generated.ts")
    if not checked_in_ts_path.exists():
        pytest.fail("Checked-in generated.ts does not exist. Run export:contract.")

    # fmt: off
    assert temp_ts.read_text() == checked_in_ts_path.read_text(), "Generated TypeScript drifted from checked-in version! Please run export:contract."  # noqa: E501
    # fmt: on


def test_openapi_generation_is_deterministic():
    # Double-generation to prove determinism
    first_gen = build_contract()
    second_gen = build_contract()
    assert first_gen == second_gen, "OpenAPI generation is not deterministic (content changed)"


def test_no_bridge_url_in_artifacts():
    openapi_file = Path("contracts/openapi.json")
    ts_file = Path("frontend/src/shared/api/generated.ts")

    for path in [openapi_file, ts_file]:
        if not path.exists():
            continue
        content = path.read_text()
        assert "8045" not in content, f"Sensitive port 8045 found in {path}"
        assert "http://127.0.0.1" not in content, f"Loopback URL found in {path}"


def test_expected_schema_invariants():
    openapi_sorted = build_contract()

    # 1. OperationId is camelCase
    op_path = openapi_sorted["paths"].get("/api/v1/operations/{operationId}")
    assert op_path is not None, "Path parameter must be operationId (camelCase)"

    # 2. ErrorResponse exists
    schemas = openapi_sorted["components"]["schemas"]
    assert "ErrorResponse" in schemas, "ErrorResponse schema must be exported"
    assert "ErrorDetails" in schemas, "ErrorDetails schema must be exported"

    # 3. HTTPValidationError should not exist
    assert "HTTPValidationError" not in schemas, "HTTPValidationError must be stripped"


def test_required_nullable_fields():
    openapi_sorted = build_contract()
    op_schema = openapi_sorted["components"]["schemas"].get("Operation")
    if op_schema:
        required_fields = op_schema.get("required", [])
        assert "operationId" in required_fields
        assert "status" in required_fields

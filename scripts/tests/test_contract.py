import json
import subprocess
from pathlib import Path


def test_openapi_generation_is_deterministic():
    openapi_file = Path("contracts/openapi.json")
    ts_file = Path("frontend/src/shared/api/generated.ts")

    if not openapi_file.exists():
        subprocess.run(["npm", "run", "export:contract"], check=True, stdout=subprocess.DEVNULL)

    first_gen = openapi_file.read_text()
    first_ts = ts_file.read_text()

    subprocess.run(["npm", "run", "export:contract"], check=True, stdout=subprocess.DEVNULL)

    second_gen = openapi_file.read_text()
    second_ts = ts_file.read_text()

    assert first_gen == second_gen, "OpenAPI generation is not deterministic (content changed)"
    assert first_ts == second_ts, "TS generation is not deterministic (content changed)"


def test_no_bridge_url_in_artifacts():
    openapi_file = Path("contracts/openapi.json")
    ts_file = Path("frontend/src/shared/api/generated.ts")

    for path in [openapi_file, ts_file]:
        content = path.read_text()
        assert "8045" not in content, f"Sensitive port 8045 found in {path}"
        assert "http://127.0.0.1" not in content, f"Loopback URL found in {path}"


def test_expected_schema_invariants():
    openapi_file = Path("contracts/openapi.json")
    schema = json.loads(openapi_file.read_text())

    # 1. OperationId is camelCase
    op_path = schema["paths"].get("/api/v1/operations/{operationId}")
    assert op_path is not None, "Path parameter must be operationId (camelCase)"

    # 2. ErrorResponse exists
    schemas = schema["components"]["schemas"]
    assert "ErrorResponse" in schemas, "ErrorResponse schema must be exported"
    assert "ErrorDetails" in schemas, "ErrorDetails schema must be exported"

    # 3. HTTPValidationError should not exist
    assert "HTTPValidationError" not in schemas, "HTTPValidationError must be stripped"


def test_required_nullable_fields():
    # If a field is nullable and required, make sure it's exported correctly
    openapi_file = Path("contracts/openapi.json")
    schema = json.loads(openapi_file.read_text())

    op_schema = schema["components"]["schemas"].get("Operation")
    if op_schema:
        # Check that it doesn't accidentally make properties optional if they are required in OpenAPI  # noqa: E501
        # FastAPI might not output this strictly unless we configure it, but let's check
        required_fields = op_schema.get("required", [])
        assert "operationId" in required_fields
        assert "status" in required_fields

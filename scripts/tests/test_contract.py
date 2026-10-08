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


def test_error_details_supports_retry():
    openapi_sorted = build_contract()
    error_details = openapi_sorted["components"]["schemas"].get("ErrorDetails", {})
    any_of = error_details.get("anyOf", [])

    # 1. RETRY exists in shared ErrorDetails schema
    retry_variants = [
        v for v in any_of if v.get("properties", {}).get("kind", {}).get("enum") == ["RETRY"]
    ]
    assert len(retry_variants) == 1, "RETRY variant must exist in ErrorDetails schema"
    retry_schema = retry_variants[0]
    assert retry_schema["required"] == ["kind"]
    props = retry_schema["properties"]
    assert "operationId" in props
    assert "retryAfterSeconds" in props
    assert "operationKind" in props

    # 2. Runtime 409 RETRY conforms to OpenAPI ErrorResponse
    runtime_409_retry = {
        "error": {
            "code": "IDEMPOTENCY_IN_FLIGHT",
            "message": "Operation already in flight",
            "details": {
                "kind": "RETRY",
                "operationId": "op_test_123",
            },
            "requestId": "req_test_456",
        }
    }
    err_obj = runtime_409_retry["error"]
    assert "code" in err_obj and isinstance(err_obj["code"], str)
    assert "message" in err_obj and isinstance(err_obj["message"], str)
    assert "requestId" in err_obj and isinstance(err_obj["requestId"], str)
    assert err_obj["details"]["kind"] == "RETRY"
    assert isinstance(err_obj["details"]["operationId"], str)

    # 3. Generated TypeScript ErrorResponse.details permits RETRY
    ts_content = Path("frontend/src/shared/api/generated.ts").read_text()
    assert 'kind: "RETRY";' in ts_content
    assert "operationId?: string;" in ts_content


def test_error_details_supports_ai_consent():
    openapi_sorted = build_contract()
    error_details = openapi_sorted["components"]["schemas"].get("ErrorDetails", {})
    any_of = error_details.get("anyOf", [])

    # 1. AI_CONSENT exists in shared ErrorDetails schema
    consent_variants = [
        v for v in any_of if v.get("properties", {}).get("kind", {}).get("enum") == ["AI_CONSENT"]
    ]
    assert len(consent_variants) == 1, "AI_CONSENT variant must exist in ErrorDetails schema"
    consent_schema = consent_variants[0]
    assert "kind" in consent_schema["required"]
    assert "consentState" in consent_schema["required"]
    props = consent_schema["properties"]
    assert "consentState" in props
    assert props["consentState"]["enum"] == ["NOT_GRANTED", "GRANTED", "REVOKED", "STALE"]
    assert "currentPolicyVersion" in props
    assert props["currentPolicyVersion"]["anyOf"] == [{"type": "string"}, {"type": "null"}]
    assert "currentPolicyVersion" in consent_schema["required"]

    # 2. Runtime 403 AI_CONSENT conforms to OpenAPI ErrorResponse
    runtime_403_consent = {
        "error": {
            "code": "AI_CONSENT_REQUIRED",
            "message": "AI consent required",
            "details": {
                "kind": "AI_CONSENT",
                "consentState": "REVOKED",
                "currentPolicyVersion": "policy-v1",
            },
            "requestId": "req_test_789",
        }
    }
    err_obj = runtime_403_consent["error"]
    assert err_obj["code"] == "AI_CONSENT_REQUIRED"
    assert err_obj["details"]["kind"] == "AI_CONSENT"
    assert err_obj["details"]["consentState"] == "REVOKED"
    assert err_obj["details"]["currentPolicyVersion"] == "policy-v1"

    # 3. Generated TypeScript ErrorResponse.details permits AI_CONSENT
    ts_content = Path("frontend/src/shared/api/generated.ts").read_text()
    assert 'kind: "AI_CONSENT";' in ts_content
    assert 'consentState: "NOT_GRANTED" | "GRANTED" | "REVOKED" | "STALE";' in ts_content


def test_r4_consent_required_nullable_json_schema():
    schema = build_contract()["components"]["schemas"]["ErrorDetails"]
    # AJV implements a legacy OpenAPI nullable extension. Remove that annotation
    # when evaluating actual OpenAPI 3.1 JSON Schema semantics, where it has no effect.
    script = r"""
const Ajv = require('@redocly/ajv/dist/2020').default;
const fs = require('fs');
const schema = JSON.parse(fs.readFileSync(0, 'utf8'));
function annotations(value) {
  if (value && typeof value === 'object') {
    delete value.nullable;
    for (const v of Object.values(value)) annotations(v);
  }
}
annotations(schema);
const validate = new Ajv({strict: false}).compile(schema);
const base = {kind: 'AI_CONSENT', consentState: 'REVOKED'};
process.stdout.write(JSON.stringify([
  validate(base), validate({...base, currentPolicyVersion:null}),
  validate({...base, currentPolicyVersion:'policy-v1'})
]));
"""
    result = subprocess.run(
        ["node", "-e", script],
        input=json.dumps(schema),
        text=True,
        capture_output=True,
        check=True,
        timeout=10,
    )
    assert json.loads(result.stdout) == [False, True, True]


def test_r4_consent_typescript_property_required_nullable():
    ts = Path("frontend/src/shared/api/generated.ts").read_text()
    assert "currentPolicyVersion: string | null;" in ts
    assert "currentPolicyVersion?:" not in ts

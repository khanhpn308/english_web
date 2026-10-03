#!/usr/bin/env python3
import json
import subprocess
from pathlib import Path

from backend.app.main import create_app


def build_contract() -> dict:
    app = create_app()
    openapi = app.openapi()

    paths = openapi.get("paths", {})
    if "/api/v1/operations/{operation_id}" in paths:
        op_path = paths.pop("/api/v1/operations/{operation_id}")
        if "get" not in op_path:
            raise ValueError("Expected GET method for /api/v1/operations/{operation_id}")
        for _, operation in op_path.items():
            if "parameters" in operation:
                for param in operation["parameters"]:
                    if param.get("name") == "operation_id":
                        param["name"] = "operationId"
        paths["/api/v1/operations/{operationId}"] = op_path
    elif "/api/v1/operations/{operationId}" not in paths:
        # fmt: off
        raise ValueError("Backend route /api/v1/operations/{operation_id} is missing. Did it drift?")  # noqa: E501
        # fmt: on

    openapi.setdefault("components", {}).setdefault("schemas", {})

    # Project implemented error detail variants.
    error_details_schema = {
        "type": "object",
        "discriminator": {"propertyName": "kind"},
        "required": ["kind"],
        "anyOf": [
            {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": ["FIELD_ERRORS"]},
                    "fields": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "field": {"type": "string"},
                                "reason": {"type": "string"},
                            },
                            "required": ["field", "reason"],
                        },
                    },
                },
                "required": ["kind", "fields"],
            },
            {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": ["RETRY"]},
                    "retryAfterSeconds": {"type": "integer"},
                    "operationId": {"type": "string"},
                    "operationKind": {"type": "string"},
                },
                "required": ["kind"],
            },
            {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": ["AI_CONSENT"]},
                    "consentState": {
                        "type": "string",
                        "enum": ["NOT_GRANTED", "GRANTED", "REVOKED", "STALE"],
                    },
                    "currentPolicyVersion": {
                        "type": "string",
                        "nullable": True,
                    },
                },
                "required": ["kind", "consentState"],
            },
        ],
    }

    openapi["components"]["schemas"]["ErrorDetails"] = error_details_schema
    openapi["components"]["schemas"]["ErrorResponse"] = {
        "type": "object",
        "properties": {
            "error": {
                "type": "object",
                "properties": {
                    "code": {"type": "string"},
                    "message": {"type": "string"},
                    "details": {"$ref": "#/components/schemas/ErrorDetails"},
                    "requestId": {"type": "string"},
                },
                "required": ["code", "message", "requestId"],
            }
        },
        "required": ["error"],
    }

    if "OperationView" in openapi["components"]["schemas"]:
        op_schema = openapi["components"]["schemas"].pop("OperationView")
        op_schema["title"] = "Operation"
        openapi["components"]["schemas"]["Operation"] = op_schema
        # Update refs
        for p in paths.values():
            for _, operation in p.items():
                if "responses" in operation:
                    for resp in operation["responses"].values():
                        content = (
                            resp.get("content", {}).get("application/json", {}).get("schema", {})
                        )
                        if content.get("$ref") == "#/components/schemas/OperationView":
                            content["$ref"] = "#/components/schemas/Operation"

    for path_obj in paths.values():
        for _, operation in path_obj.items():
            if "responses" not in operation:
                operation["responses"] = {}
            if "422" in operation["responses"]:
                operation["responses"]["422"] = {
                    "description": "Validation Error",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                        }
                    },
                }
            for code in ["400", "401", "403", "404", "409", "413", "500", "502", "503"]:
                if code not in operation["responses"]:
                    operation["responses"][code] = {
                        "description": "Error Response",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                            }
                        },
                    }

    openapi["components"]["schemas"].pop("HTTPValidationError", None)
    openapi["components"]["schemas"].pop("ValidationError", None)

    def sort_dict(d):
        if isinstance(d, dict):
            return {k: sort_dict(v) for k, v in sorted(d.items())}
        if isinstance(d, list):
            return [sort_dict(v) for v in d]
        return d

    return sort_dict(openapi)


def main():
    openapi_sorted = build_contract()
    out_dir = Path("contracts")
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / "openapi.json"
    with open(out_file, "w") as f:
        json.dump(openapi_sorted, f, indent=2)
        f.write("\n")

    frontend_api_dir = Path("frontend/src/shared/api")
    frontend_api_dir.mkdir(parents=True, exist_ok=True)
    ts_out = frontend_api_dir / "generated.ts"

    print(f"Exported openapi to {out_file}")
    subprocess.run(["npx", "openapi-typescript", str(out_file), "-o", str(ts_out)], check=True)
    print(f"Exported typescript to {ts_out}")


if __name__ == "__main__":
    main()

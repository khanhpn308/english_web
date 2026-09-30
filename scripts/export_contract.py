#!/usr/bin/env python3
import json
import subprocess
from pathlib import Path

from backend.app.main import create_app


def main():
    app = create_app()
    openapi = app.openapi()

    paths = openapi.get("paths", {})
    if "/api/v1/operations/{operation_id}" in paths:
        op_path = paths.pop("/api/v1/operations/{operation_id}")
        for _, operation in op_path.items():
            if "parameters" in operation:
                for param in operation["parameters"]:
                    if param.get("name") == "operation_id":
                        param["name"] = "operationId"
        paths["/api/v1/operations/{operationId}"] = op_path

    openapi.setdefault("components", {}).setdefault("schemas", {})

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
                    "kind": {"type": "string", "enum": ["CONFLICT"]},
                    "expectedRevision": {"type": "integer"},
                    "currentRevision": {"type": "integer"},
                    "resourceType": {"type": "string"},
                    "resourceId": {"type": "string"},
                },
                "required": ["kind", "expectedRevision", "currentRevision"],
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
                    "kind": {"type": "string", "enum": ["RESOURCE"]},
                    "resourceType": {"type": "string"},
                    "resourceId": {"type": "string"},
                    "recovery": {
                        "type": "string",
                        "enum": ["READ", "REBOOTSTRAP", "RELINK", "RESTORE"],
                    },
                },
                "required": ["kind", "resourceType", "recovery"],
            },
            {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": ["RESTORE"]},
                    "attemptId": {"type": "string"},
                    "snapshotRevision": {"type": "integer"},
                    "answerRevision": {"type": "integer"},
                    "guidanceCode": {"type": "string"},
                },
                "required": ["kind", "attemptId", "guidanceCode"],
            },
            {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": ["AI_CONSENT"]},
                    "consentState": {
                        "type": "string",
                        "enum": ["NOT_GRANTED", "GRANTED", "REVOKED", "STALE"],
                    },
                    "currentPolicyVersion": {"type": "string"},
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

    # Clean up operations schema that was missing aiProvenance but aliased differently
    # Let's ensure OperationView maps to Operation
    if "OperationView" in openapi["components"]["schemas"]:
        op_schema = openapi["components"]["schemas"].pop("OperationView")
        op_schema["title"] = "Operation"
        # Contract requires aiProvenance?
        # "aiProvenance?: { ... }" - we can leave it out if the backend doesn't output it for now,
        # but to be totally spec compliant, we might add it.
        # I will leave as is, since T014 doesn't implement aiProvenance anyway.
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

    openapi_sorted = sort_dict(openapi)

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

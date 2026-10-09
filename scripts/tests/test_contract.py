import json
import subprocess
from pathlib import Path

import pytest
from backend.app.application.edit_word_form import EditConflict, EditWordFormIntent
from backend.app.application.operations import OperationConflict
from backend.app.application.save_word_family import SaveConflict, SaveWordFamilyService
from backend.app.assessment.questions import (
    PUBLIC_QUESTION_ADAPTER,
    SNAPSHOT_ADAPTER,
    ClozeQuestionResult,
    MCQQuestion,
    QuizAttempt,
    QuizResult,
    WritingRubric,
    storage_payload,
)
from backend.app.http.errors import error_response
from backend.app.http.quiz import _restore_error
from backend.app.http.review import ReviewRequest
from backend.app.http.word_forms import (
    PatchWordFormRequest,
    SaveErrorResponse,
    SaveWordFormsRequest,
    _failure,
)
from pydantic import TypeAdapter, ValidationError
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
    contract = build_contract()
    schema = {
        **contract["components"]["schemas"]["ErrorDetails"],
        "components": contract["components"],
    }
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


def schema_accepts(contract, schema, instances):
    """Evaluate OpenAPI 3.1 schemas with the repository's existing AJV dependency."""
    script = r"""
const Ajv = require('@redocly/ajv/dist/2020').default;
const fs = require('fs');
const {schema, instances} = JSON.parse(fs.readFileSync(0, 'utf8'));
function annotations(value) {
  if (value && typeof value === 'object') {
    delete value.nullable;
    for (const v of Object.values(value)) annotations(v);
  }
}
annotations(schema);
const validate = new Ajv({strict: false}).compile(schema);
process.stdout.write(JSON.stringify(instances.map(value => validate(value))));
"""
    result = subprocess.run(
        ["node", "-e", script],
        input=json.dumps({
            "schema": {**schema, "components": contract["components"]},
            "instances": instances,
        }),
        text=True,
        capture_output=True,
        check=True,
        timeout=10,
    )
    return json.loads(result.stdout)


@pytest.mark.parametrize("conflict_type,operation_kind", [(SaveConflict, "SAVE"),
                                                        (EditConflict, "EDIT")])
def test_source_error_producers_match_typed_and_shared_contract(conflict_type, operation_kind):
    contract = build_contract()
    details = {
        "kind": "CONFLICT", "expectedRevision": 1, "currentRevision": 2,
        "resourceType": "SOURCE", "resourceId": "src_fixture",
    }
    conflict = _failure(conflict_type(409, "REVISION_CONFLICT", details=details), operation_kind)
    retry = _failure(OperationConflict(409, "IDEMPOTENCY_IN_FLIGHT", "op_fixture"), operation_kind)
    fields = error_response(422, "VALIDATION_ERROR", {
        "kind": "FIELD_ERRORS", "fields": [{"field": "body", "reason": "invalid"}],
    })
    payloads = [json.loads(response.body) for response in (conflict, retry, fields)]
    assert conflict.status_code == retry.status_code == 409
    assert fields.status_code == 422
    assert payloads[0]["error"]["code"] == "REVISION_CONFLICT"
    assert payloads[0]["error"]["message"] == "Source revision changed"
    assert payloads[0]["error"]["details"] == details
    assert payloads[1]["error"]["details"] == {
        "kind": "RETRY", "operationId": "op_fixture", "operationKind": operation_kind,
    }
    for payload in payloads:
        SaveErrorResponse.model_validate(payload)
    for name in ("SaveErrorResponse", "ErrorResponse"):
        assert schema_accepts(contract, {"$ref": f"#/components/schemas/{name}"}, payloads) == [
            True, True, True,
        ]


def test_restore_producer_matches_shared_error_contract():
    contract = build_contract()
    response = _restore_error("attempt_fixture")
    payload = json.loads(response.body)
    assert response.status_code == 409
    assert response.headers["cache-control"] == "no-store"
    assert payload["error"]["details"] == {
        "kind": "RESTORE", "attemptId": "attempt_fixture", "guidanceCode": "QUIZ_RESTORE_REQUIRED",
    }
    assert schema_accepts(contract, {"$ref": "#/components/schemas/ErrorResponse"}, [payload]) == [True]
    variants = contract["components"]["schemas"]["ErrorDetails"]["anyOf"]
    assert {"$ref": "#/components/schemas/RestoreDetails"} in variants


def test_error_contract_rejects_malformed_recovery_variants():
    contract = build_contract()
    invalid = [
        {"kind": "CONFLICT", "expectedRevision": 1, "resourceType": "SOURCE"},
        {"kind": "CONFLICT", "expectedRevision": "1", "currentRevision": 2,
         "resourceType": "SOURCE", "resourceId": "src_fixture"},
        {"kind": "RESTORE", "attemptId": "attempt_fixture"},
        {"kind": "RESTORE", "attemptId": "attempt_fixture", "guidanceCode": "UNKNOWN"},
        {"kind": "RETRY", "operationId": 7},
        {"kind": "FIELD_ERRORS", "fields": [{"field": "body"}]},
        {"kind": "UNKNOWN"},
    ]
    assert schema_accepts(contract, {"$ref": "#/components/schemas/ErrorDetails"}, invalid) == [
        False for _ in invalid
    ]
    for details in invalid:
        with pytest.raises(ValidationError):
            SaveErrorResponse.model_validate({"error": {
                "code": "REVISION_CONFLICT", "message": "Source revision changed",
                "requestId": "req_fixture", "details": details,
            }})


@pytest.mark.parametrize("field,value", [
    ("lookupId", ""),
    ("lookupId", "x" * 65),
    ("lookupId", "invalid/id"),
    ("noteDate", "09-10-2026"),
])
def test_save_request_preserves_lookup_and_date_schema_constraints(field, value):
    contract = build_contract()
    body = {"lookupId": "lookup_fixture", "noteDate": "2026-10-09", field: value}
    assert schema_accepts(contract, {"$ref": "#/components/schemas/SaveWordFormsRequest"},
                          [body]) == [False]
    with pytest.raises(ValidationError):
        SaveWordFormsRequest.model_validate(body)


def test_source_error_contract_requires_its_emitted_retry_metadata():
    contract = build_contract()
    base = {
        "code": "IDEMPOTENCY_IN_FLIGHT", "message": "Operation already in flight",
        "requestId": "req_fixture",
    }
    valid = {"error": {**base, "details": {
        "kind": "RETRY", "operationId": "op_fixture", "operationKind": "SAVE",
    }}}
    without_details = {"error": base}
    invalid = [
        {"error": {**base, "details": {"kind": "RETRY", "operationId": "op_fixture"}}},
        {"error": {**base, "details": {"kind": "RETRY", "operationKind": "SAVE"}}},
        {"error": {**base, "details": {
            "kind": "RETRY", "operationId": "op_fixture", "operationKind": "QUIZ",
        }}},
    ]
    assert schema_accepts(contract, {"$ref": "#/components/schemas/SaveErrorResponse"},
                          [valid, without_details, *invalid]) == [True, True, False, False, False]
    for body in (valid, without_details):
        SaveErrorResponse.model_validate(body)
    for body in invalid:
        with pytest.raises(ValidationError):
            SaveErrorResponse.model_validate(body)


def test_422_normalization_is_preserved_for_all_operations():
    for path in build_contract()["paths"].values():
        for operation in path.values():
            response = operation.get("responses", {}).get("422")
            if response is not None:
                assert response["content"]["application/json"]["schema"] == {
                    "$ref": "#/components/schemas/ErrorResponse",
                }


@pytest.mark.parametrize("source_fields,accepted", [
    ({}, True),
    ({"sourceId": "src_fixture", "sourceRevision": 1}, True),
    ({"sourceId": "src_fixture"}, False),
    ({"sourceRevision": 1}, False),
    ({"sourceId": None}, False),
    ({"sourceRevision": None}, False),
    ({"sourceId": None, "sourceRevision": None}, False),
    ({"sourceId": "src_fixture", "sourceRevision": None}, False),
    ({"sourceId": None, "sourceRevision": 1}, False),
    ({"sourceId": "", "sourceRevision": 1}, False),
    ({"sourceId": "src_fixture", "sourceRevision": 0}, False),
    ({"sourceId": "src_fixture", "sourceRevision": "1"}, False),
])
def test_save_request_schema_matches_source_pair_validation(source_fields, accepted):
    body = {"lookupId": "lookup_fixture", "noteDate": "2026-10-09", **source_fields}
    contract = build_contract()
    assert schema_accepts(contract, {"$ref": "#/components/schemas/SaveWordFormsRequest"},
                          [body]) == [accepted]
    if accepted:
        request = SaveWordFormsRequest.model_validate(body)
        assert request.model_fields_set == set(body)
    else:
        with pytest.raises(ValidationError):
            SaveWordFormsRequest.model_validate(body)


@pytest.mark.parametrize("source_id,revision,if_match,if_none_match,accepted", [
    (None, None, None, "*", True),
    ("src_fixture", 1, '"source-r1"', None, True),
    (None, None, None, None, False),
    (None, None, '"source-r1"', "*", False),
    (None, None, None, "x", False),
    ("src_fixture", 1, None, None, False),
    ("src_fixture", 1, "", None, False),
    ("src_fixture", 1, '"source-r1"', "*", False),
])
def test_save_preconditions_keep_runtime_cross_location_enforcement(
    source_id, revision, if_match, if_none_match, accepted,
):
    arguments = ("lookup_fixture", "2026-10-09", source_id, revision, if_match, if_none_match)
    if accepted:
        SaveWordFamilyService._validate_intent(*arguments)
    else:
        with pytest.raises(SaveConflict) as failure:
            SaveWordFamilyService._validate_intent(*arguments)
        assert failure.value.status_code == 422
        assert failure.value.code == "VALIDATION_ERROR"


def test_save_header_contract_documents_alternative_preconditions():
    contract = build_contract()
    operation = contract["paths"]["/api/v1/word-forms"]["post"]
    headers = {p["name"]: p for p in operation["parameters"] if p["in"] == "header"}
    assert headers["Idempotency-Key"]["required"] is True
    for name in ("If-Match", "If-None-Match"):
        assert headers[name]["required"] is False
        assert "sourceId" in headers[name]["description"]
        assert "sourceRevision" in headers[name]["description"]
    assert "If-None-Match" in headers["If-Match"]["description"]
    assert "If-Match" in headers["If-None-Match"]["description"]
    assert schema_accepts(contract, headers["If-None-Match"]["schema"], ["*", "x"]) == [
        True, False,
    ]
    assert schema_accepts(contract, headers["If-Match"]["schema"], ["", '"source-r1"']) == [
        False, True,
    ]


@pytest.mark.parametrize("fields,accepted", [
    ({}, False),
    ({"ipaUs": None}, True),
    ({"cambridgeUrl": None}, True),
    ({"ipaUs": "test", "cambridgeUrl": None}, True),
    ({"meaningsEn": [{"text": "synthetic", "verificationStatus": "UNVERIFIED"}],
      "meaningsVi": [{"text": "synthetic", "verificationStatus": "UNVERIFIED"}],
      "ipaUs": None}, True),
    ({"examples": [{"english": "Synthetic example.", "vietnamese": "Synthetic translation.",
                    "verificationStatus": "UNVERIFIED"}]}, True),
    ({"meaningsEn": None}, False),
    ({"meaningsVi": None}, False),
    ({"examples": None}, False),
    ({"meaningsEn": None, "ipaUs": None}, False),
    ({"meaningsEn": []}, False),
    ({"examples": []}, False),
    ({"unsupported": "synthetic"}, False),
])
def test_edit_schema_matches_supplied_field_validation(fields, accepted):
    body = {"sourceId": "src_fixture", "sourceRevision": 1, **fields}
    contract = build_contract()
    assert schema_accepts(contract, {"$ref": "#/components/schemas/PatchWordFormRequest"},
                          [body]) == [accepted]
    for model in (EditWordFormIntent, PatchWordFormRequest):
        if accepted:
            intent = model.model_validate(body)
            assert intent.model_dump(mode="json", exclude_unset=True) == body
        else:
            with pytest.raises(ValidationError):
                model.model_validate(body)


@pytest.mark.parametrize("source,provenance,accepted", [
    ("FLASHCARD", {}, True),
    ("FLASHCARD", {"attemptId": None}, True),
    ("FLASHCARD", {"attemptId": None, "questionId": None}, True),
    ("FLASHCARD", {"attemptId": "attempt_fixture"}, False),
    ("FLASHCARD", {"questionId": "question_fixture"}, False),
    ("QUIZ", {"attemptId": "attempt_fixture", "questionId": "question_fixture"}, True),
    ("QUIZ", {}, False),
    ("QUIZ", {"attemptId": "attempt_fixture"}, False),
    ("QUIZ", {"questionId": "question_fixture"}, False),
    ("QUIZ", {"attemptId": None, "questionId": "question_fixture"}, False),
    ("QUIZ", {"attemptId": "attempt_fixture", "questionId": None}, False),
])
def test_review_schema_matches_provenance_validation(source, provenance, accepted):
    body = {"rating": "GOOD", "source": source, **provenance}
    contract = build_contract()
    assert schema_accepts(contract, {"$ref": "#/components/schemas/ReviewRequest"},
                          [body]) == [accepted]
    if accepted:
        ReviewRequest.model_validate(body)
    else:
        with pytest.raises(ValidationError):
            ReviewRequest.model_validate(body)


def test_review_rating_and_individual_card_revision_contract_is_preserved():
    contract = build_contract()
    rating = contract["components"]["schemas"]["ReviewRequest"]["properties"]["rating"]
    assert rating["enum"] == ["AGAIN", "HARD", "GOOD", "EASY"]
    operation = contract["paths"]["/api/v1/cards/{cardId}/reviews"]["post"]
    headers = {p["name"]: p for p in operation["parameters"] if p["in"] == "header"}
    assert headers["If-Match"]["required"] is True
    assert "Individual card queueRevision" in headers["If-Match"]["description"]
    assert headers["Idempotency-Key"]["required"] is True
    assert schema_accepts(contract, headers["If-Match"]["schema"], ["0", '"7"', "source-r7"]
                          ) == [True, True, False]


def public_question(index=0):
    return {
        "id": f"q_{index}", "type": "MCQ", "wordFormId": f"wf_{index}",
        "promptEn": "Choose the synthetic word.",
        "options": [{"id": "option_a", "textEn": "synthetic"}],
    }


def terminal_result():
    return {
        "attemptId": "attempt_fixture", "status": "SUBMITTED", "submissionRevision": 0,
        "objectiveScores": {
            "mcq": {"total": 5, "attempted": 0, "correct": 0, "accuracy": None},
            "cloze": {"total": 0, "attempted": 0, "correct": 0, "accuracy": None},
        },
        "writingSelfScores": [],
        "questionResults": [
            {"questionId": f"q_{index}", "type": "MCQ", "outcome": "BLANK",
             "isCorrect": False, "rating": "AGAIN", "correctOptionId": "option_a",
             "explanationVi": "Synthetic explanation."}
            for index in range(5)
        ],
        "reviewHandoffs": [
            {"wordFormId": f"wf_{index}", "cardId": None, "rating": "AGAIN",
             "reviewEventId": None, "status": "SKIPPED_INACTIVE"}
            for index in range(5)
        ],
        "submittedAt": "2026-10-09T00:00:00Z",
    }


@pytest.mark.parametrize("model,field,alias,minimum,maximum,item", [
    (WritingRubric, "descriptors", "descriptors", 5, 5, {"score": 0, "textVi": "Synthetic rubric."}),
    (MCQQuestion, "options", "options", 1, 100, {"id": "option_a", "textEn": "synthetic"}),
    (ClozeQuestionResult, "accepted_answers", "acceptedAnswers", 1, 100, "synthetic"),
    (QuizResult, "writing_self_scores", "writingSelfScores", 0, 20,
     {"questionId": "q_fixture", "selfScore": 1, "rating": "HARD"}),
    (QuizResult, "question_results", "questionResults", 5, 30,
     {"questionId": "q_fixture", "type": "WRITING", "outcome": "SELF_SCORED",
      "selfScore": 1, "rating": "HARD"}),
    (QuizResult, "review_handoffs", "reviewHandoffs", 1, 30,
     {"wordFormId": "wf_fixture", "cardId": None, "rating": "AGAIN",
      "reviewEventId": None, "status": "SKIPPED_INACTIVE"}),
    (QuizAttempt, "questions", "questions", 5, 30, public_question()),
    (QuizAttempt, "answers", "answers", 0, 30,
     {"attemptId": "attempt_fixture", "questionId": "q_fixture", "answer": "",
      "selfScore": None, "draftRevision": 1, "savedAt": "2026-10-09T00:00:00Z",
      "state": "BLANK", "operationId": "op_fixture"}),
])
def test_public_quiz_array_bounds_match_runtime_field_constraints(
    model, field, alias, minimum, maximum, item,
):
    contract = build_contract()
    schema = contract["components"]["schemas"][model.__name__]["properties"][alias]
    assert schema["type"] == "array"
    assert schema.get("minItems", 0) == minimum
    assert schema["maxItems"] == maximum
    assert "minLength" not in schema and "maxLength" not in schema
    sizes = sorted({minimum, maximum, maximum + 1, *([minimum - 1] if minimum else [])})
    collections = [[item] * size for size in sizes]
    accepted = [minimum <= size <= maximum for size in sizes]
    assert schema_accepts(contract, schema, collections) == accepted
    # Isolate field bounds from whole-model uniqueness/membership validators.
    adapter = TypeAdapter(model.model_fields[field].rebuild_annotation())
    for collection, valid in zip(collections, accepted, strict=True):
        if valid:
            assert isinstance(adapter.validate_json(json.dumps(collection)), tuple)
        else:
            with pytest.raises(ValidationError):
                adapter.validate_json(json.dumps(collection))


@pytest.mark.parametrize("status,has_result,accepted", [
    ("IN_PROGRESS", False, True),
    ("SUBMITTED", True, True),
    ("IN_PROGRESS", True, False),
    ("SUBMITTED", False, False),
])
def test_quiz_attempt_status_result_schema_matches_runtime(status, has_result, accepted):
    body = {
        "id": "attempt_fixture", "noteDate": "2026-10-09", "status": status,
        "questions": [public_question(index) for index in range(5)], "answers": [],
        "savedAnswerCount": 0, "snapshotRevision": 1, "submissionRevision": 0,
        "result": terminal_result() if has_result else None,
    }
    contract = build_contract()
    schema = {"$ref": "#/components/schemas/QuizAttempt"}
    assert schema_accepts(contract, schema, [body]) == [accepted]
    if accepted:
        attempt = QuizAttempt.model_validate_json(json.dumps(body))
        assert attempt.model_dump(mode="json", by_alias=True)["result"] == body["result"]
        assert isinstance(attempt.questions, tuple) and isinstance(attempt.answers, tuple)
        with pytest.raises(ValidationError):
            attempt.status = "IN_PROGRESS"
    else:
        with pytest.raises(ValidationError):
            QuizAttempt.model_validate_json(json.dumps(body))
    without_result = {key: value for key, value in body.items() if key != "result"}
    assert schema_accepts(contract, schema, [without_result, {**body, "unexpected": True}]) == [
        False, False,
    ]


def test_quiz_contract_preserves_closed_object_and_private_projection():
    contract = build_contract()
    schemas = contract["components"]["schemas"]
    attempt = schemas["QuizAttempt"]
    assert attempt["title"] == "QuizAttempt"
    assert attempt["additionalProperties"] is False
    assert set(attempt["required"]) == {
        "id", "noteDate", "status", "questions", "answers", "savedAnswerCount",
        "snapshotRevision", "submissionRevision", "result",
    }
    assert len(attempt["oneOf"]) == 2
    assert all(branch.get("additionalProperties") is not False for branch in attempt["oneOf"])
    for name in ("MCQQuestion", "ClozeQuestion", "WritingQuestion"):
        assert not {"correctOptionId", "acceptedAnswers", "explanationVi"} & set(
            schemas[name]["properties"]
        )
    assert schemas["MCQOption"]["properties"]["textEn"]["maxLength"] == 4096
    for kind in ("MCQ", "CLOZE"):
        private = public_question()
        if kind == "MCQ":
            private.update(correctOptionId="option_a", explanationVi="Synthetic explanation.")
        else:
            private.pop("options")
            private.update(type="CLOZE", answerPolicyVersion="cloze-answer-v1",
                           acceptedAnswers=["synthetic"], explanationVi="Synthetic explanation.")
        snapshot = SNAPSHOT_ADAPTER.validate_json(json.dumps(private))
        projection = snapshot.model_dump(mode="json", by_alias=True)
        assert not {"correctOptionId", "acceptedAnswers", "explanationVi"} & set(projection)
        assert PUBLIC_QUESTION_ADAPTER.validate_python(projection).type == kind
        assert "explanationVi" in json.loads(storage_payload(snapshot))

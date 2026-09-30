"""Redacted operation status read endpoint (T014)."""

from secrets import token_urlsafe

from backend.app.application.operations import OperationLedger, OperationStatus
from backend.app.http.errors import error_response
from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import JSONResponse


class OperationView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operationId: str
    kind: str
    status: OperationStatus
    resultRef: str | None = None
    errorCategory: str | None = None
    createdAt: str
    updatedAt: str


router = APIRouter(prefix="/api/v1", tags=["operations"])


@router.get(
    "/operations/{operation_id}",
    response_model=OperationView,
    response_model_exclude_none=True,
)
def get_operation(request: Request, operation_id: str) -> OperationView | JSONResponse:
    if request.query_params:
        return JSONResponse(
            {
                "error": {
                    "code": "INVALID_QUERY",
                    "message": "Syntax or query shape invalid",
                    "requestId": f"req_{token_urlsafe(12)}",
                }
            },
            status_code=400,
        )
    ledger = getattr(request.app.state, "operation_ledger", None)
    if not isinstance(ledger, OperationLedger):
        return error_response(503, "CONFIGURATION_REQUIRED")
    try:
        operation = ledger.get(operation_id)
    except SQLAlchemyError:
        return JSONResponse(
            {
                "error": {
                    "code": "STORAGE_BUSY",
                    "message": "Storage unavailable",
                    "requestId": f"req_{token_urlsafe(12)}",
                }
            },
            status_code=503,
        )
    if operation is None:
        return error_response(404, "NOT_FOUND")
    return OperationView(
        operationId=operation.operation_id,
        kind=operation.kind,
        status=operation.status,
        resultRef=operation.result_ref,
        errorCategory=operation.error_category,
        createdAt=operation.created_at,
        updatedAt=operation.updated_at,
    )

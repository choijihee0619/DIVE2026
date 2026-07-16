"""공통 성공/실패 응답 봉투. API_Contract_260714.yaml의 SuccessResponse/ErrorResponse를 그대로 따른다."""

from __future__ import annotations

from typing import Any

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse


def success_envelope(data: Any, request_id: str, status: str = "Success") -> dict[str, Any]:
    return {"status": status, "data": jsonable_encoder(data), "error": None, "request_id": request_id}


def error_envelope(
    error_code: str, message: str, request_id: str, details: dict[str, Any] | None = None
) -> dict[str, Any]:
    return {
        "status": "Failed",
        "data": None,
        "error": {"error_code": error_code, "message": message, "details": details or {}},
        "request_id": request_id,
    }


def success_response(
    data: Any,
    request_id: str,
    status_code: int = 200,
    status: str = "Success",
    extra_headers: dict[str, str] | None = None,
) -> JSONResponse:
    headers = {"X-Request-ID": request_id}
    if extra_headers:
        headers.update(extra_headers)
    return JSONResponse(
        content=success_envelope(data, request_id, status=status),
        status_code=status_code,
        headers=headers,
    )


def error_response(
    error_code: str,
    message: str,
    request_id: str,
    http_status: int,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    return JSONResponse(
        content=error_envelope(error_code, message, request_id, details),
        status_code=http_status,
        headers={"X-Request-ID": request_id},
    )

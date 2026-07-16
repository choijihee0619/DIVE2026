"""API_Contract_260714.yaml의 x-error-codes(ERROR-001~012)와 1:1 매핑되는 예외 계층."""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """공통 실패 응답으로 변환되는 애플리케이션 예외의 베이스 클래스."""

    error_code: str = "ERROR-001"
    http_status: int = 500
    default_message: str = "예상하지 못한 서버 오류가 발생했습니다."

    def __init__(self, message: str | None = None, details: dict[str, Any] | None = None):
        self.message = message or self.default_message
        self.details = details or {}
        super().__init__(self.message)


class ValidationAppError(AppError):
    error_code = "ERROR-002"
    http_status = 422
    default_message = "요청 값 검증에 실패했습니다."


class AuthenticationRequiredError(AppError):
    error_code = "ERROR-003"
    http_status = 401
    default_message = "인증 정보가 필요합니다."


class InvalidTokenError(AppError):
    error_code = "ERROR-004"
    http_status = 401
    default_message = "토큰이 만료되었거나 유효하지 않습니다."


class PermissionDeniedError(AppError):
    error_code = "ERROR-005"
    http_status = 403
    default_message = "이 작업을 수행할 권한이 없습니다."


class ResourceNotFoundError(AppError):
    error_code = "ERROR-006"
    http_status = 404
    default_message = "요청한 리소스를 찾을 수 없거나 본인 소유가 아닙니다."


class StateConflictError(AppError):
    error_code = "ERROR-007"
    http_status = 409
    default_message = "현재 상태에서는 처리할 수 없는 요청입니다."


class ExternalAPITimeoutError(AppError):
    error_code = "ERROR-008"
    http_status = 408
    default_message = "외부 API 응답이 지연되고 있습니다."


class ExternalAPIFailedError(AppError):
    error_code = "ERROR-009"
    http_status = 502
    default_message = "외부 API 호출에 실패했습니다."


class ModelInferenceFailedError(AppError):
    error_code = "ERROR-010"
    http_status = 500
    default_message = "모델 추론에 실패했습니다."


class ModelInsufficientDataError(AppError):
    error_code = "ERROR-011"
    http_status = 422
    default_message = "추론에 필요한 데이터가 부족합니다."


class BlockchainAnchorFailedError(AppError):
    error_code = "ERROR-012"
    http_status = 502
    default_message = "블록체인 공증에 실패했습니다."


class InternalServerError(AppError):
    error_code = "ERROR-001"
    http_status = 500
    default_message = "예상하지 못한 서버 오류가 발생했습니다."

"""공통 FastAPI Dependency: 인증된 사용자, 역할 검사, DB 세션, request_id."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.exceptions import AuthenticationRequiredError, InvalidTokenError, PermissionDeniedError
from app.core.security import decode_access_token
from app.db.mongodb import get_db as _get_db
from app.repositories.user_repository import UserRepository

bearer_scheme = HTTPBearer(
    auto_error=False,
    bearerFormat="JWT",
    scheme_name="BearerAuth",
    description="POST /api/v1/auth/login에서 발급받은 access_token을 입력하세요.",
)


@dataclass
class CurrentUser:
    user_id: str
    role: str
    display_name: str
    email: str | None = None


def get_db() -> AsyncIOMotorDatabase:
    return _get_db()


def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "req_unknown")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> CurrentUser:
    if not credentials:
        raise AuthenticationRequiredError()
    token = credentials.credentials
    try:
        payload = decode_access_token(token)
    except ValueError as exc:
        raise InvalidTokenError() from exc

    user_id = payload.get("sub")
    role = payload.get("role")
    if not user_id or not role:
        raise InvalidTokenError()

    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)
    if not user or not user.get("is_active", True):
        raise InvalidTokenError("사용자를 찾을 수 없거나 비활성화되었습니다.")
    current_role = user.get("role")
    if not current_role or current_role != role:
        raise InvalidTokenError("사용자 권한이 변경되었습니다. 다시 로그인해 주세요.")

    return CurrentUser(
        user_id=user_id,
        role=current_role,
        display_name=user.get("display_name", ""),
        email=user.get("email"),
    )


def require_roles(*roles: str):
    async def _checker(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if roles and current_user.role not in roles:
            raise PermissionDeniedError(
                f"role={current_user.role} 은(는) 이 작업에 필요한 권한({', '.join(roles)})이 없습니다."
            )
        return current_user

    return _checker

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import CurrentUser, get_current_user, get_db, get_request_id, require_roles
from app.core.exceptions import PermissionDeniedError
from app.core.responses import success_response
from app.services.auth_service import AuthService
from app.services.user_service import UserService

router = APIRouter(tags=["Admin"])


@router.get("/admin/users")
async def list_admin_users(
    search: str | None = None,
    role: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: CurrentUser = Depends(require_roles("system_admin")),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    users, pagination = await UserService(db).list_users(page, size, role, search)
    return success_response({"items": users, "pagination": pagination.model_dump()}, request_id)


@router.get("/users/{user_id}")
async def get_user(
    user_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    if current_user.user_id != user_id and current_user.role != "system_admin":
        raise PermissionDeniedError("본인 정보 또는 system_admin만 조회할 수 있습니다.")
    user = await AuthService(db).get_me(user_id)
    return success_response(user, request_id)

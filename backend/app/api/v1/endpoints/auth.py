from __future__ import annotations

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import CurrentUser, get_current_user, get_db, get_request_id
from app.core.responses import success_response
from app.schemas.auth import LoginRequest, SignupRequest
from app.services.auth_service import AuthService

router = APIRouter(tags=["Auth"])


@router.post("/auth/signup", status_code=201)
async def signup(
    payload: SignupRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    user = await AuthService(db).signup(payload)
    return success_response(user, request_id, status_code=201)


@router.post("/auth/login")
async def login(
    payload: LoginRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    data = await AuthService(db).login(payload)
    return success_response(data, request_id)


@router.get("/auth/me")
async def read_me(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    user = await AuthService(db).get_me(current_user.user_id)
    return success_response(user, request_id)


@router.post("/auth/logout")
async def logout(
    current_user: CurrentUser = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
):
    # MVP: 서버측 토큰 블랙리스트 없이 클라이언트가 토큰을 폐기하는 방식(9.1절 확인필요 항목).
    return success_response({"logged_out": True}, request_id)

"""알림함 엔드포인트.

- GET   /notifications            : 내 알림 목록 (+unread_count)
- PATCH /notifications/{id}/read  : 읽음 처리
- PATCH /notifications/read-all   : 전체 읽음 처리
- POST  /notifications/demo-seed  : MOCK_MODE 한정, 데모용 샘플 알림 3종 생성
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import CurrentUser, get_current_user, get_db, get_request_id
from app.core.responses import success_response
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["Notification"])


@router.get("")
async def list_notifications(
    unread_only: bool = False,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await NotificationService(db).list(current_user.user_id, page, size, unread_only)
    return success_response(result, request_id)


@router.patch("/read-all")
async def mark_all_read(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await NotificationService(db).mark_all_read(current_user.user_id)
    return success_response(result, request_id)


@router.patch("/{notification_id}/read")
async def mark_read(
    notification_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await NotificationService(db).mark_read(current_user.user_id, notification_id)
    return success_response(result, request_id)


@router.post("/demo-seed", status_code=201)
async def demo_seed(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await NotificationService(db).demo_seed(current_user.user_id)
    return success_response(result, request_id, status_code=201)

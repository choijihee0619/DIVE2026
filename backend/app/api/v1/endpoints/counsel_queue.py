"""상담사 큐 엔드포인트.

- POST  /counsel-queue        : 임차인 상담 이관 접수 (ML 자동분류 태깅 + 우선순위)
- GET   /counsel-queue        : 상담사·HUG=전체 큐(우선순위→오래된 순), 임차인=본인 요청
- GET   /counsel-queue/{id}   : 상세
- PATCH /counsel-queue/{id}   : 상담사 처리 (Waiting→InProgress→Answered→Closed, 답변 등록)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import CurrentUser, get_current_user, get_db, get_request_id, require_roles
from app.core.responses import success_response
from app.schemas.counsel import CounselQueueCreateRequest, CounselQueueUpdateRequest
from app.services.counsel_queue_service import CounselQueueService

router = APIRouter(prefix="/counsel-queue", tags=["Counsel"])


@router.post("", status_code=201)
async def create_counsel_request(
    payload: CounselQueueCreateRequest,
    current_user: CurrentUser = Depends(require_roles("tenant", "landlord")),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await CounselQueueService(db).create(current_user.user_id, payload)
    return success_response(result, request_id, status_code=201)


@router.get("")
async def list_counsel_queue(
    status: str | None = None,
    priority: str | None = Query(None, pattern="^(high|normal)$"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await CounselQueueService(db).list(
        current_user.role, current_user.user_id, page, size, status, priority
    )
    return success_response(result, request_id)


@router.get("/{counsel_id}")
async def get_counsel_request(
    counsel_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await CounselQueueService(db).get(counsel_id, current_user.role, current_user.user_id)
    return success_response(result, request_id)


@router.patch("/{counsel_id}")
async def update_counsel_request(
    counsel_id: str,
    payload: CounselQueueUpdateRequest,
    current_user: CurrentUser = Depends(require_roles("advisor", "hug_admin", "system_admin")),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await CounselQueueService(db).update(counsel_id, payload, current_user.user_id)
    return success_response(result, request_id)

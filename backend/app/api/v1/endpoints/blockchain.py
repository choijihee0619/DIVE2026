from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import CurrentUser, get_current_user, get_db, get_request_id, require_roles
from app.core.responses import success_response
from app.schemas.blockchain import AnchorRequest
from app.services.blockchain_service import BlockchainService

router = APIRouter(prefix="/blockchain", tags=["Blockchain"])


@router.post("/anchor", status_code=202)
async def anchor_blockchain(
    payload: AnchorRequest,
    # 계약상 "Backend 내부 서비스 전용"이나, Node.js Anchor 서비스가 아직 없어 이번 MVP는
    # advisor/hug_admin/system_admin이 직접 호출해 공증 이력을 시연할 수 있게 열어둔다.
    current_user: CurrentUser = Depends(require_roles("advisor", "hug_admin", "system_admin")),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await BlockchainService(db).anchor(payload)
    return success_response(result, request_id, status_code=202)


@router.get("/{tx_id}")
async def get_blockchain_transaction(
    tx_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await BlockchainService(db).get_transaction(tx_id)
    return success_response(result, request_id)


@router.get("")
async def list_blockchain_transactions(
    blockchain_status: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: CurrentUser = Depends(require_roles("system_admin")),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    items, pagination = await BlockchainService(db).list_transactions(page, size, blockchain_status)
    return success_response({"items": items, "pagination": pagination.model_dump()}, request_id)

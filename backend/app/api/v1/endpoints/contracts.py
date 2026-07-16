from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import CurrentUser, get_db, get_request_id, require_roles
from app.core.responses import success_response
from app.schemas.contract import ContractCreateRequest, ReturnPlanCreateRequest
from app.services.contract_service import ContractService

router = APIRouter(tags=["Contract"])


@router.post("/contracts", status_code=201)
async def create_contract(
    payload: ContractCreateRequest,
    current_user: CurrentUser = Depends(require_roles("tenant")),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await ContractService(db).create(current_user.user_id, payload)
    return success_response(result, request_id, status_code=201)


@router.get("/contracts")
async def list_contracts(
    contract_status: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: CurrentUser = Depends(require_roles("tenant", "landlord", "hug_admin", "system_admin")),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    service = ContractService(db)
    if current_user.role in ("hug_admin", "system_admin"):
        # 관리 역할은 소유 여부와 무관하게 전체 계약을 조회한다(HUG-01 채권관리 대시보드).
        items, pagination = await service.list_all(page, size, contract_status)
    else:
        items, pagination = await service.list_for_user(current_user.user_id, page, size, contract_status)
    return success_response({"items": items, "pagination": pagination.model_dump()}, request_id)


@router.get("/contracts/{contract_id}")
async def get_contract(
    contract_id: str,
    current_user: CurrentUser = Depends(require_roles("tenant", "landlord", "advisor", "hug_admin", "system_admin")),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await ContractService(db).get(contract_id, current_user.user_id)
    return success_response(result, request_id)


@router.get("/contracts/{contract_id}/timeline")
async def get_contract_timeline(
    contract_id: str,
    current_user: CurrentUser = Depends(require_roles("tenant", "landlord", "advisor", "hug_admin")),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await ContractService(db).get_timeline(contract_id, current_user.user_id)
    return success_response(result, request_id)


@router.get("/contracts/{contract_id}/return-plan")
async def get_return_plan(
    contract_id: str,
    current_user: CurrentUser = Depends(require_roles("tenant", "landlord")),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await ContractService(db).get_return_plan(contract_id, current_user.user_id)
    return success_response(result, request_id)


@router.post("/return-plans", status_code=201)
async def submit_return_plan(
    payload: ReturnPlanCreateRequest,
    current_user: CurrentUser = Depends(require_roles("landlord")),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await ContractService(db).submit_return_plan(current_user.user_id, payload)
    return success_response(result, request_id, status_code=201)

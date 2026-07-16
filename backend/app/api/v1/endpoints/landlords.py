from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import CurrentUser, get_current_user, get_db, get_request_id
from app.core.responses import success_response
from app.schemas.landlord import LandlordCreateRequest
from app.services.landlord_service import LandlordService

router = APIRouter(prefix="/landlords", tags=["Property-Risk"])


@router.post("", status_code=201)
async def create_landlord(
    payload: LandlordCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await LandlordService(db).create(payload)
    return success_response(result, request_id, status_code=201)


@router.get("")
async def list_landlords(
    landlord_type: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    items, pagination = await LandlordService(db).list(page, size, landlord_type)
    return success_response({"items": items, "pagination": pagination.model_dump()}, request_id)


@router.get("/{landlord_id}")
async def get_landlord(
    landlord_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await LandlordService(db).get(landlord_id)
    return success_response(result, request_id)

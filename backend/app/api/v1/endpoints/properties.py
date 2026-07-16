from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import CurrentUser, get_current_user, get_db, get_request_id
from app.core.responses import success_response
from app.schemas.property import PropertyCreateRequest
from app.services.property_service import PropertyService

router = APIRouter(prefix="/properties", tags=["Property-Risk"])


@router.post("", status_code=201)
async def create_property(
    payload: PropertyCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await PropertyService(db).create(payload)
    return success_response(result, request_id, status_code=201)


@router.get("")
async def list_properties(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    items, pagination = await PropertyService(db).list(page, size)
    return success_response({"items": items, "pagination": pagination.model_dump()}, request_id)


@router.get("/{property_id}")
async def get_property(
    property_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await PropertyService(db).get(property_id)
    return success_response(result, request_id)

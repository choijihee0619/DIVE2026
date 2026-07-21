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


@router.post("/{property_id}/registry/refresh", status_code=201)
async def refresh_registry(
    property_id: str,
    deposit: int | None = Query(None, ge=0, description="보증금(원). 지정 시 보증금 대비 채권최고액 비율 계산"),
    scenario: str | None = Query(None, description="mock 시나리오(normal|mortgage|complex_rights). 미지정 시 CODEF 실호출"),
    dong: str | None = Query(None, max_length=20, description="동 (집합건물 특정용). 지정 시 매물 주소에 저장"),
    ho: str | None = Query(None, max_length=20, description="호수 (집합건물 특정용). 지정 시 매물 주소에 저장"),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    """주소(동·호수 포함) 기반 등기부 조회 → registry_snapshots 저장. 실패 시 mock 폴백."""
    from app.services.registry_service import RegistryService

    result = await RegistryService(db).refresh(
        property_id, deposit=deposit, scenario=scenario, dong=dong, ho=ho
    )
    return success_response(result, request_id, status_code=201)


@router.post("/{property_id}/official-price/refresh", status_code=201)
async def refresh_official_price(
    property_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    """VWorld NED 공시가격 3종 live 조회 → official_price_snapshots 저장 (전세가율 신호 입력)."""
    from app.services.official_price_service import OfficialPriceService

    result = await OfficialPriceService(db).refresh(property_id)
    return success_response(result, request_id, status_code=201)


@router.get("/{property_id}/official-price/latest")
async def get_latest_official_price(
    property_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    from app.services.official_price_service import OfficialPriceService

    result = await OfficialPriceService(db).latest(property_id)
    return success_response(result, request_id)


@router.get("/{property_id}/registry/latest")
async def get_latest_registry(
    property_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    from app.services.registry_service import RegistryService

    result = await RegistryService(db).latest(property_id)
    return success_response(result, request_id)

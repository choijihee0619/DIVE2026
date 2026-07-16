from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.exceptions import ResourceNotFoundError
from app.repositories.property_repository import PropertyRepository
from app.schemas.common import build_pagination
from app.schemas.property import PropertyCreateRequest, PropertyResponse
from app.utils.datetime_utils import now_kst_iso, new_uuid


def _to_response(doc: dict) -> PropertyResponse:
    return PropertyResponse(
        property_id=doc["_id"],
        address=doc.get("address", {}),
        housing_type=doc.get("housing_type"),
        source_system=doc.get("source_system", "user_upload"),
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


class PropertyService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._properties = PropertyRepository(db)

    async def create(self, payload: PropertyCreateRequest) -> PropertyResponse:
        existing = await self._properties.find_by_road_address(payload.address.road_address)
        if existing:
            return _to_response(existing)

        now = now_kst_iso()
        doc = {
            "_id": new_uuid(),
            "address": payload.address.model_dump(exclude_none=True),
            "housing_type": payload.housing_type.value if payload.housing_type else None,
            "source_system": "user_upload",
            "created_at": now,
            "updated_at": now,
        }
        await self._properties.insert(doc)
        return _to_response(doc)

    async def get(self, property_id: str) -> PropertyResponse:
        doc = await self._properties.get_by_id(property_id)
        if not doc:
            raise ResourceNotFoundError("매물 정보를 찾을 수 없습니다.")
        return _to_response(doc)

    async def list(self, page: int, size: int):
        items, total = await self._properties.list_paginated((page - 1) * size, size)
        return [_to_response(i) for i in items], build_pagination(page, size, total)

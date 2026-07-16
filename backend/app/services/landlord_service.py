from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.exceptions import ResourceNotFoundError
from app.repositories.landlord_repository import LandlordRepository
from app.schemas.common import build_pagination
from app.schemas.landlord import LandlordCreateRequest, LandlordResponse
from app.utils.datetime_utils import now_kst_iso, new_uuid
from app.utils.hashing import sha256_bytes


def _to_response(doc: dict) -> LandlordResponse:
    return LandlordResponse(
        landlord_id=doc["_id"],
        landlord_type=doc["landlord_type"],
        display_name=doc["display_name"],
        business_registration_number_hash=doc.get("business_registration_number_hash"),
        dart_corp_name=doc.get("dart_corp_name"),
        business_status=doc.get("business_status"),
        source_system=doc.get("source_system", "user_upload"),
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


class LandlordService:
    """임대인 또는 대상 법인 CRUD. 사업자등록번호는 원문을 저장하지 않고 해시만 저장한다
    (개발설계보고서 8장/12장 개인정보 최소화 원칙, Backend_API_명세서 12장)."""

    def __init__(self, db: AsyncIOMotorDatabase):
        self._landlords = LandlordRepository(db)

    async def create(self, payload: LandlordCreateRequest) -> LandlordResponse:
        now = now_kst_iso()
        doc = {
            "_id": new_uuid(),
            "landlord_type": payload.landlord_type.value,
            "display_name": payload.display_name,
            "business_registration_number_hash": (
                sha256_bytes(payload.business_registration_number.encode("utf-8"))
                if payload.business_registration_number
                else None
            ),
            "dart_corp_name": payload.dart_corp_name,
            "business_status": None,
            "source_system": "user_upload",
            "created_at": now,
            "updated_at": now,
        }
        await self._landlords.insert(doc)
        return _to_response(doc)

    async def get(self, landlord_id: str) -> LandlordResponse:
        doc = await self._landlords.get_by_id(landlord_id)
        if not doc:
            raise ResourceNotFoundError("임대인/법인 정보를 찾을 수 없습니다.")
        return _to_response(doc)

    async def list(self, page: int, size: int, landlord_type: str | None):
        items, total = await self._landlords.list_paginated((page - 1) * size, size, landlord_type=landlord_type)
        return [_to_response(i) for i in items], build_pagination(page, size, total)

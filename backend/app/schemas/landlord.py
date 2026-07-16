from __future__ import annotations

from pydantic import BaseModel

from app.models.enums import LandlordType


class LandlordCreateRequest(BaseModel):
    landlord_type: LandlordType
    display_name: str
    business_registration_number: str | None = None
    dart_corp_name: str | None = None


class LandlordResponse(BaseModel):
    landlord_id: str
    landlord_type: str
    display_name: str
    business_registration_number_hash: str | None = None
    dart_corp_name: str | None = None
    business_status: str | None = None
    source_system: str
    created_at: str
    updated_at: str


class LandlordListResponse(BaseModel):
    items: list[LandlordResponse]
    pagination: dict

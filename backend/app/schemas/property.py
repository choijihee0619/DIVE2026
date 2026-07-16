from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.enums import HousingType


class AddressInput(BaseModel):
    road_address: str
    jibun_address: str | None = None
    adm_cd: str | None = None
    bd_mgt_sn: str | None = None
    zip_no: str | None = None
    dong: str | None = None
    ho: str | None = None


class PropertyCreateRequest(BaseModel):
    address: AddressInput
    housing_type: HousingType | None = None


class PropertyResponse(BaseModel):
    property_id: str
    address: dict
    housing_type: str | None = None
    source_system: str
    created_at: str
    updated_at: str


class PropertyListResponse(BaseModel):
    items: list[PropertyResponse]
    pagination: dict

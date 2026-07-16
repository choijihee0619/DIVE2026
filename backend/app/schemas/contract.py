from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from app.models.enums import HousingType, LandlordType


class ContractCreateRequest(BaseModel):
    property_id: str
    deposit: int = Field(gt=0)
    contract_start_date: date
    contract_end_date: date
    landlord_type: LandlordType
    housing_type: HousingType
    landlord_id: str | None = None


class ContractResponse(BaseModel):
    contract_id: str
    property_id: str
    tenant_user_id: str
    landlord_user_id: str | None = None
    landlord_id: str | None = None
    contract_status: str
    deposit: int
    contract_start_date: str
    contract_end_date: str
    landlord_type: str
    housing_type: str
    risk_assessment_id: str | None = None
    created_at: str
    updated_at: str


class ContractListResponse(BaseModel):
    items: list[ContractResponse]
    pagination: dict


class TimelineEventResponse(BaseModel):
    timeline_event_id: str
    event_type: str
    occurred_at: str
    blockchain_status: str
    blockchain_tx_id: str | None = None


class ContractTimelineResponse(BaseModel):
    contract_id: str
    contract_status: str
    events: list[TimelineEventResponse]


class ReturnPlanCreateRequest(BaseModel):
    contract_id: str
    planned_return_date: date
    return_method: str
    note: str | None = None


class ReturnPlanResponse(BaseModel):
    return_plan_id: str
    contract_id: str
    d_day: int | None = None
    landlord_response_status: str
    early_warning: bool
    planned_return_date: str | None = None
    return_method: str | None = None
    note: str | None = None
    created_at: str

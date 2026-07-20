from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

IncidentType = Literal[
    "DEPOSIT_NOT_RETURNED",  # 보증금 미반환
    "AUCTION_STARTED",  # 경매·공매 개시 통지
    "LANDLORD_UNREACHABLE",  # 임대인 연락 두절
    "FRAUD_SUSPECTED",  # 전세사기 의심
    "OTHER",
]

IncidentStatus = Literal["Received", "Reviewing", "TransferredToRecovery", "Closed"]

INCIDENT_TYPE_LABELS: dict[str, str] = {
    "DEPOSIT_NOT_RETURNED": "보증금 미반환",
    "AUCTION_STARTED": "경매·공매 개시",
    "LANDLORD_UNREACHABLE": "임대인 연락 두절",
    "FRAUD_SUSPECTED": "전세사기 의심",
    "OTHER": "기타",
}


class IncidentCreateRequest(BaseModel):
    incident_type: IncidentType
    description: str = Field(min_length=10, max_length=4000, description="상황 설명")
    contract_id: str | None = None
    property_id: str | None = None
    deposit_amount: int | None = Field(default=None, ge=0)
    occurred_date: date | None = None


class IncidentStatusUpdateRequest(BaseModel):
    status: IncidentStatus
    note: str | None = Field(default=None, max_length=1000)


class IncidentTimelineEntry(BaseModel):
    status: IncidentStatus
    note: str | None = None
    by_role: str
    at: str


class IncidentResponse(BaseModel):
    incident_id: str
    reporter_user_id: str
    incident_type: IncidentType
    incident_type_label: str
    description: str
    contract_id: str | None = None
    property_id: str | None = None
    deposit_amount: int | None = None
    occurred_date: date | None = None
    status: IncidentStatus
    timeline: list[IncidentTimelineEntry]
    next_steps: list[str]
    created_at: str
    updated_at: str

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel

from app.models.enums import EvidenceType


class EvidenceRequestCreateRequest(BaseModel):
    contract_id: str
    reason: str
    evidence_type: EvidenceType
    risk_assessment_id: str | None = None
    due_date: date | None = None


class EvidenceRequestResponse(BaseModel):
    evidence_request_id: str
    contract_id: str
    risk_assessment_id: str | None = None
    reason: str
    evidence_type: str
    due_date: str | None = None
    verification_status: str
    latest_evidence_id: str | None = None
    created_at: str
    updated_at: str


class EvidenceRequestListResponse(BaseModel):
    items: list[EvidenceRequestResponse]
    pagination: dict


class EvidenceResponse(BaseModel):
    evidence_id: str
    evidence_request_id: str
    file_name: str
    document_hash: str
    verification_status: str
    submitted_at: str


class VerificationResponse(BaseModel):
    verification_id: str
    evidence_id: str
    verification_status: str
    reviewer_comment: str | None = None
    resubmission_required: bool
    blockchain_tx_id: str | None = None


class VerificationDecisionRequest(BaseModel):
    decision: Literal["approve", "reject", "hold"]
    reviewer_comment: str | None = None

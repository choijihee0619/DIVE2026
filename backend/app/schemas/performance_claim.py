"""보증이행청구 상태머신의 요청/응답 스키마.

`incident`는 임차인의 사고 통지 원장이고, 이 모듈의 `performance_claim`은
청구 접수 이후 서류·심사·명도·대위변제·구상채권 등록을 관리하는 별도 원장이다.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import EvidenceType
PerformanceClaimStage = Literal[
    "ClaimReceived",
    "SupplementRequested",
    "UnderReview",
    "Approved",
    "OnHold",
    "Rejected",
    "HandoverScheduled",
    "HandoverCompleted",
    "SubrogationPaid",
    "RecoveryClaimRegistered",
    "TransferredToRecovery",
]

WorkflowType = Literal["JEONSE_RETURN_NONRETURN", "JEONSE_AUCTION_PUBLIC_SALE"]
OfficialAccidentType = Literal["CONTRACT_END_NONRETURN", "AUCTION_PUBLIC_SALE"]
ClaimDocumentStatus = Literal["Requested", "Submitted", "Verified", "Rejected", "Waived"]
RecoveryClaimType = Literal[
    "RECOURSE_STANDARD",
    "RECOURSE_NEW_PRODUCT",
    "LITIGATION_ADVANCE_COST",
]


class PerformanceClaimCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_amount: int = Field(gt=0)
    official_accident_type: OfficialAccidentType | None = None
    workflow_type: WorkflowType | None = None
    workflow_version: str = Field(default="JEONSE_RETURN_V1", min_length=1, max_length=100)
    product_name: str = Field(default="전세보증금반환보증", min_length=1, max_length=200)
    claim_sla_days: int = Field(default=30, ge=1, le=365)
    assignee_user_id: str | None = None
    handover_required: bool | None = None


class ClaimDocumentRequestItem(BaseModel):
    document_type: EvidenceType
    reason: str = Field(min_length=3, max_length=1000)
    due_at: datetime | None = None
    required: bool = True


class ClaimDocumentsRequest(BaseModel):
    documents: list[ClaimDocumentRequestItem] = Field(min_length=1, max_length=20)


class ClaimDocumentSubmitRequest(BaseModel):
    file_name: str = Field(min_length=1, max_length=255)
    document_hash: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    object_uri: str | None = Field(default=None, max_length=2000)
    note: str | None = Field(default=None, max_length=1000)


class ClaimDocumentDecisionRequest(BaseModel):
    decision: Literal["VERIFY", "REJECT", "WAIVE"]
    reason: str = Field(min_length=3, max_length=1000)


class ReviewStartRequest(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


class PerformanceClaimDecisionRequest(BaseModel):
    decision: Literal["APPROVE", "ON_HOLD", "REJECT"]
    approved_amount: int | None = Field(default=None, gt=0)
    reason: str = Field(min_length=3, max_length=2000)
    checklist_completed: bool = False

    @model_validator(mode="after")
    def validate_decision_fields(self):
        if self.decision == "APPROVE":
            if self.approved_amount is None:
                raise ValueError("승인 결정에는 approved_amount가 필요합니다.")
            if not self.checklist_completed:
                raise ValueError("승인 결정에는 심사 체크리스트 완료 확인이 필요합니다.")
        elif self.approved_amount is not None:
            raise ValueError("승인 외 결정에는 approved_amount를 입력할 수 없습니다.")
        if self.decision == "REJECT" and not self.checklist_completed:
            raise ValueError("거절 결정에는 심사 체크리스트 완료 확인이 필요합니다.")
        return self


class HandoverActionRequest(BaseModel):
    action: Literal["SCHEDULE", "COMPLETE"]
    moveout_due_at: datetime | None = None
    settlement_confirmed: bool = False
    reason: str = Field(min_length=3, max_length=1000)

    @model_validator(mode="after")
    def validate_action_fields(self):
        if self.action == "SCHEDULE" and self.moveout_due_at is None:
            raise ValueError("명도 일정 등록에는 moveout_due_at이 필요합니다.")
        if self.action == "COMPLETE" and not self.settlement_confirmed:
            raise ValueError("명도 완료에는 관리비·공과금 정산 확인이 필요합니다.")
        return self


class SubrogationPaymentRequest(BaseModel):
    payment_reference: str = Field(min_length=3, max_length=200)
    paid_amount: int = Field(gt=0)
    paid_at: date
    reason: str = Field(min_length=3, max_length=1000)


class RecoveryClaimCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_name: str = Field(default="전세보증금반환보증", min_length=1, max_length=200)
    claim_type: RecoveryClaimType
    principal: int = Field(gt=0)
    incurred_amount: int = Field(ge=0)
    incurred_date: date

    @model_validator(mode="after")
    def validate_cost_claim(self):
        if self.claim_type == "LITIGATION_ADVANCE_COST":
            if self.incurred_amount <= 0:
                raise ValueError("소송대지급금에는 양수의 incurred_amount가 필요합니다.")
            if self.principal != self.incurred_amount:
                raise ValueError("소송대지급금 principal은 incurred_amount와 같아야 합니다.")
        return self


class RecoveryTransferRequest(BaseModel):
    assignee_user_id: str = Field(min_length=1, max_length=200)
    next_action: str = Field(min_length=3, max_length=1000)
    reason: str = Field(min_length=3, max_length=1000)


class WorkflowEventResponse(BaseModel):
    event_id: str
    performance_claim_id: str
    action: str
    before_stage: str | None = None
    after_stage: str | None = None
    actor_user_id: str
    actor_role: str
    request_id: str
    reason: str | None = None
    metadata: dict = Field(default_factory=dict)
    occurred_at: str

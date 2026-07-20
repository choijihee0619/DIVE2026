from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

CounselStatus = Literal["Waiting", "InProgress", "Answered", "Closed"]
CounselSource = Literal["chatbot_escalation", "direct", "incident_followup"]
CounselPriority = Literal["high", "normal"]


class CounselQueueCreateRequest(BaseModel):
    text: str = Field(min_length=10, max_length=8000, description="상담 요청 본문")
    source: CounselSource = "chatbot_escalation"
    contract_id: str | None = None
    region_sido: str | None = None


class CounselQueueUpdateRequest(BaseModel):
    status: CounselStatus
    answer_note: str | None = Field(default=None, max_length=8000)


class CounselClassification(BaseModel):
    dispute_type: str | None = None
    dispute_confidence: float | None = None
    consultation_stage: str | None = None
    stage_confidence: float | None = None
    classified: bool = False


class CounselQueueItemResponse(BaseModel):
    counsel_id: str
    requester_user_id: str
    text: str
    source: CounselSource
    contract_id: str | None = None
    region_sido: str | None = None
    classification: CounselClassification
    priority: CounselPriority
    status: CounselStatus
    assignee_user_id: str | None = None
    answer_note: str | None = None
    created_at: str
    updated_at: str

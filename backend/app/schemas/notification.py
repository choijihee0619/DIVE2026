from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

NotificationCategory = Literal[
    "registry_change",  # 등기 변동 감지 (mock 모니터링)
    "contract_event",  # 계약 상태 변화
    "incident_update",  # 사고 접수 처리 현황
    "counsel_update",  # 상담 처리 현황
    "deadline",  # 보증만기·확정일자 등 일정
    "prevention_alert",  # 사고 전 예방 경보·증빙·신용보강
    "system",
]


class NotificationResponse(BaseModel):
    notification_id: str
    category: NotificationCategory
    title: str
    body: str
    link: str | None = None
    severity: Literal["info", "warning", "critical"] = "info"
    is_read: bool = False
    contract_id: str | None = None
    prevention_case_id: str | None = None
    action_id: str | None = None
    trigger_code: str | None = None
    target_role: str | None = None
    due_at: str | None = None
    delivery_status: Literal["created", "delivered", "failed"] = "created"
    delivered_at: str | None = None
    read_at: str | None = None
    acknowledged_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    source: dict[str, Any] | None = None
    created_at: str

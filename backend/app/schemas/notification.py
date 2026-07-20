from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

NotificationCategory = Literal[
    "registry_change",  # 등기 변동 감지 (mock 모니터링)
    "contract_event",  # 계약 상태 변화
    "incident_update",  # 사고 접수 처리 현황
    "counsel_update",  # 상담 처리 현황
    "deadline",  # 보증만기·확정일자 등 일정
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
    created_at: str

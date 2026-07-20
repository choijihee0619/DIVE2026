"""사고 접수 서비스.

임차인이 보증금 미반환 등 사고를 접수하면 Received 상태로 생성되고,
HUG 관리자가 Reviewing → TransferredToRecovery → Closed 순으로 처리한다.
계약이 연결된 경우 계약 상태를 INCIDENT_REPORTED로 전이하고 타임라인에 기록한다.
상태 변화마다 접수자에게 알림을 생성한다.
"""

from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.exceptions import PermissionDeniedError, ResourceNotFoundError, ValidationAppError
from app.models.enums import ContractStatus
from app.repositories.contract_repository import ContractRepository, TimelineRepository
from app.repositories.incident_repository import IncidentRepository
from app.schemas.common import build_pagination
from app.schemas.incident import (
    INCIDENT_TYPE_LABELS,
    IncidentCreateRequest,
    IncidentResponse,
    IncidentStatusUpdateRequest,
)
from app.services.notification_service import NotificationService
from app.utils.datetime_utils import new_uuid, now_kst_iso

# 허용 상태 전이 (UI 시안: 접수 → 검토 → 회수절차 이관 → 종결)
_TRANSITIONS: dict[str, set[str]] = {
    "Received": {"Reviewing", "Closed"},
    "Reviewing": {"TransferredToRecovery", "Closed"},
    "TransferredToRecovery": {"Closed"},
    "Closed": set(),
}

# 안심전세포털 피해지원 절차 기반 다음 행동 안내
_NEXT_STEPS: dict[str, list[str]] = {
    "Received": [
        "임대차계약서·내용증명 등 증빙을 준비하세요.",
        "HUG 전세피해지원센터(1533-8119) 상담 예약이 가능합니다.",
    ],
    "Reviewing": [
        "담당자가 접수 내용을 검토 중입니다.",
        "보증 가입자는 이행청구 요건(계약 종료·대항력 유지)을 확인하세요.",
    ],
    "TransferredToRecovery": [
        "채권 회수 절차(경공매 지원 등)로 이관되었습니다.",
        "경·공매 유예·정지, 우선매수권 양도 등 특별법 지원제도를 확인하세요.",
    ],
    "Closed": ["처리가 종결되었습니다. 추가 문의는 상담사 이관을 이용하세요."],
}


class IncidentService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._incidents = IncidentRepository(db)
        self._contracts = ContractRepository(db)
        self._timeline = TimelineRepository(db)
        self._notifications = NotificationService(db)

    async def create(self, user_id: str, payload: IncidentCreateRequest) -> IncidentResponse:
        now = now_kst_iso()
        contract_id = None
        if payload.contract_id:
            contract = await self._contracts.get_by_id(payload.contract_id)
            if not contract:
                raise ResourceNotFoundError("연결할 계약을 찾을 수 없습니다.")
            if contract.get("tenant_user_id") != user_id:
                raise PermissionDeniedError("본인 계약에만 사고를 접수할 수 있습니다.")
            contract_id = payload.contract_id

        doc = {
            "_id": new_uuid(),
            "reporter_user_id": user_id,
            "incident_type": payload.incident_type,
            "description": payload.description,
            "contract_id": contract_id,
            "property_id": payload.property_id,
            "deposit_amount": payload.deposit_amount,
            "occurred_date": payload.occurred_date.isoformat() if payload.occurred_date else None,
            "status": "Received",
            "timeline": [
                {"status": "Received", "note": "사고 접수 완료", "by_role": "tenant", "at": now}
            ],
            "created_at": now,
            "updated_at": now,
        }
        await self._incidents.insert(doc)

        if contract_id:
            await self._contracts.update_fields(
                contract_id,
                {"contract_status": ContractStatus.INCIDENT_REPORTED.value, "updated_at": now},
            )
            await self._timeline.append(
                {
                    "_id": new_uuid(),
                    "contract_id": contract_id,
                    "event_type": "IncidentReported",
                    "occurred_at": now,
                    "blockchain_status": "NotRequested",
                    "blockchain_tx_id": None,
                }
            )

        await self._notifications.notify(
            user_id=user_id,
            category="incident_update",
            title="사고 접수가 완료되었습니다",
            body=f"[{INCIDENT_TYPE_LABELS[payload.incident_type]}] 접수번호 {doc['_id'][:8]} — 담당자 검토 후 알림으로 안내드립니다.",
            severity="warning",
            link=f"/tenant/incidents/{doc['_id']}",
        )
        return _to_response(doc)

    async def get(self, incident_id: str, user_id: str, role: str) -> IncidentResponse:
        doc = await self._incidents.get_by_id(incident_id)
        if not doc:
            raise ResourceNotFoundError("사고 접수 내역을 찾을 수 없습니다.")
        if role not in ("hug_admin", "system_admin", "advisor") and doc["reporter_user_id"] != user_id:
            raise PermissionDeniedError("본인이 접수한 사고만 조회할 수 있습니다.")
        return _to_response(doc)

    async def list(
        self,
        user_id: str,
        role: str,
        page: int,
        size: int,
        status: str | None,
        incident_type: str | None,
    ) -> dict:
        reporter_filter = None if role in ("hug_admin", "system_admin") else user_id
        items, total = await self._incidents.list_paginated_filtered(
            (page - 1) * size, size,
            reporter_user_id=reporter_filter, status=status, incident_type=incident_type,
        )
        return {
            "items": [_to_response(d) for d in items],
            "pagination": build_pagination(page, size, total).model_dump(),
        }

    async def update_status(
        self, incident_id: str, payload: IncidentStatusUpdateRequest, by_role: str
    ) -> IncidentResponse:
        doc = await self._incidents.get_by_id(incident_id)
        if not doc:
            raise ResourceNotFoundError("사고 접수 내역을 찾을 수 없습니다.")
        allowed = _TRANSITIONS.get(doc["status"], set())
        if payload.status not in allowed:
            raise ValidationAppError(
                f"상태 전이 {doc['status']} → {payload.status} 는 허용되지 않습니다. 가능: {sorted(allowed)}"
            )
        now = now_kst_iso()
        timeline = doc.get("timeline", [])
        timeline.append(
            {"status": payload.status, "note": payload.note, "by_role": by_role, "at": now}
        )
        updated = await self._incidents.update_fields(
            incident_id, {"status": payload.status, "timeline": timeline, "updated_at": now}
        )

        status_labels = {
            "Reviewing": "담당자 검토가 시작되었습니다",
            "TransferredToRecovery": "채권 회수 절차로 이관되었습니다",
            "Closed": "사고 처리가 종결되었습니다",
        }
        await self._notifications.notify(
            user_id=doc["reporter_user_id"],
            category="incident_update",
            title=status_labels.get(payload.status, "사고 처리 상태가 변경되었습니다"),
            body=payload.note or f"접수번호 {incident_id[:8]}의 상태가 {payload.status}로 변경되었습니다.",
            severity="info",
            link=f"/tenant/incidents/{incident_id}",
        )
        return _to_response(updated)


def _to_response(doc: dict) -> IncidentResponse:
    return IncidentResponse(
        incident_id=doc["_id"],
        reporter_user_id=doc["reporter_user_id"],
        incident_type=doc["incident_type"],
        incident_type_label=INCIDENT_TYPE_LABELS[doc["incident_type"]],
        description=doc["description"],
        contract_id=doc.get("contract_id"),
        property_id=doc.get("property_id"),
        deposit_amount=doc.get("deposit_amount"),
        occurred_date=doc.get("occurred_date"),
        status=doc["status"],
        timeline=doc.get("timeline", []),
        next_steps=_NEXT_STEPS[doc["status"]],
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )

"""사고 접수 서비스.

임차인이 보증금 미반환 등 사고를 접수하면 Received 상태로 생성되고,
HUG 관리자가 Reviewing → TransferredToRecovery → Closed 순으로 처리한다.
계약이 연결된 경우 계약 상태를 INCIDENT_REPORTED로 전이하고 타임라인에 기록한다.
상태 변화마다 접수자에게 알림을 생성한다.
"""

from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from app.core.exceptions import (
    PermissionDeniedError,
    ResourceNotFoundError,
    StateConflictError,
    ValidationAppError,
)
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
from app.schemas.provenance import source_metadata
from app.services.notification_service import NotificationService
from app.utils.datetime_utils import new_uuid, now_kst_iso

# 허용 상태 전이 (UI 시안: 접수 → 검토 → 회수절차 이관 → 종결)
_TRANSITIONS: dict[str, set[str]] = {
    "Received": {"Reviewing", "Closed"},
    "Reviewing": {"TransferredToRecovery", "Closed"},
    "TransferredToRecovery": {"Closed"},
    "Closed": set(),
}

_INCIDENT_REPORTABLE_CONTRACT_STATUSES: frozenset[str] = frozenset(
    {
        ContractStatus.CONTRACT_FINALIZED.value,
        ContractStatus.MONITORING.value,
        ContractStatus.D90_REQUESTED.value,
        ContractStatus.RETURN_PLAN_SUBMITTED.value,
        ContractStatus.AT_RISK.value,
    }
)
_ACTIVE_PERFORMANCE_CLAIM_STAGES: tuple[str, ...] = (
    "ClaimReceived",
    "SupplementRequested",
    "UnderReview",
    "Approved",
    "OnHold",
    "HandoverScheduled",
    "HandoverCompleted",
    "SubrogationPaid",
    "RecoveryClaimRegistered",
)

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
        self._db = db
        self._incidents = IncidentRepository(db)
        self._contracts = ContractRepository(db)
        self._timeline = TimelineRepository(db)
        self._notifications = NotificationService(db)

    async def create(self, user_id: str, payload: IncidentCreateRequest) -> IncidentResponse:
        now = now_kst_iso()
        contract_id = None
        authoritative_property_id = payload.property_id
        authoritative_deposit_amount = payload.deposit_amount
        incident_source = source_metadata(
            data_mode="LIVE",
            source_type="user_submitted",
            source_dataset="platform_incidents",
            as_of_date=now[:10],
            basis="임차인이 제출하고 플랫폼이 접수한 사고통지 업무대장",
            is_demo=False,
        )
        if payload.contract_id:
            contract = await self._contracts.get_by_id(payload.contract_id)
            if not contract:
                raise ResourceNotFoundError("연결할 계약을 찾을 수 없습니다.")
            if contract.get("tenant_user_id") != user_id:
                raise PermissionDeniedError("본인 계약에만 사고를 접수할 수 있습니다.")
            current_status = contract.get("contract_status")
            if current_status not in _INCIDENT_REPORTABLE_CONTRACT_STATUSES:
                raise StateConflictError(
                    "사고 전 관리 상태의 계약에서만 사고를 접수할 수 있습니다.",
                    details={
                        "contract_id": payload.contract_id,
                        "current_status": current_status,
                        "allowed_statuses": sorted(_INCIDENT_REPORTABLE_CONTRACT_STATUSES),
                    },
                )
            existing_incident = await self._incidents.find_active_by_contract(payload.contract_id)
            if existing_incident:
                raise StateConflictError(
                    "해당 계약에 처리 중인 사고가 이미 존재합니다.",
                    details={"incident_id": existing_incident["_id"]},
                )
            active_claim = await self._db.performance_claims.find_one(
                {
                    "contract_id": payload.contract_id,
                    "stage": {"$in": list(_ACTIVE_PERFORMANCE_CLAIM_STAGES)},
                }
            )
            if active_claim:
                raise StateConflictError(
                    "해당 계약에 처리 중인 보증이행청구가 이미 존재합니다.",
                    details={"performance_claim_id": active_claim["_id"]},
                )
            contract_id = payload.contract_id
            contract_property_id = contract.get("property_id")
            if (
                payload.property_id
                and contract_property_id
                and payload.property_id != contract_property_id
            ):
                raise ValidationAppError("사고의 매물은 연결 계약의 매물과 일치해야 합니다.")
            authoritative_property_id = contract_property_id or payload.property_id

            contract_deposit = contract.get("deposit")
            if (
                payload.deposit_amount is not None
                and contract_deposit is not None
                and int(payload.deposit_amount) != int(contract_deposit)
            ):
                raise ValidationAppError(
                    "사고 보증금은 연결 계약의 임대차 보증금과 일치해야 합니다.",
                    details={
                        "submitted_deposit_amount": payload.deposit_amount,
                        "contract_deposit_amount": int(contract_deposit),
                    },
                )
            authoritative_deposit_amount = (
                int(contract_deposit) if contract_deposit is not None else payload.deposit_amount
            )
            inherited_source = contract.get("source") or contract.get("provenance")
            if isinstance(inherited_source, dict) and inherited_source.get("data_mode"):
                incident_source = inherited_source
            elif str(contract.get("_id", "")).startswith("demo-") or contract.get("is_demo"):
                incident_source = source_metadata(
                    data_mode="DEMO",
                    source_type="demo_scenario",
                    source_dataset="hug-workflow-v1.1.0",
                    as_of_date=now[:10],
                    scenario_id=contract.get("scenario_id"),
                    basis="시연 계약에서 파생된 사고통지 업무대장",
                    is_demo=True,
                )

        doc = {
            "_id": new_uuid(),
            "reporter_user_id": user_id,
            "incident_type": payload.incident_type,
            "description": payload.description,
            "contract_id": contract_id,
            "property_id": authoritative_property_id,
            "deposit_amount": authoritative_deposit_amount,
            "occurred_date": payload.occurred_date.isoformat() if payload.occurred_date else None,
            "status": "Received",
            "performance_claim_id": None,
            "current_stage": "AccidentNotified",
            "source": incident_source,
            "provenance": incident_source,
            "source_type": incident_source["source_type"],
            "basis": incident_source["basis"],
            "is_demo": incident_source["is_demo"],
            "scenario_id": incident_source.get("scenario_id"),
            "timeline": [
                {"status": "Received", "note": "사고 접수 완료", "by_role": "tenant", "at": now}
            ],
            "created_at": now,
            "updated_at": now,
        }
        try:
            await self._incidents.insert(doc)
        except DuplicateKeyError as exc:
            raise StateConflictError("해당 계약에 처리 중인 사고가 이미 존재합니다.") from exc

        if contract_id:
            # 검증 이후 계약 상태가 바뀌는 경쟁 요청도 CAS로 차단한다. 실패한 신고 문서는
            # 삭제해 한 계약에 두 개의 활성 사고가 남지 않도록 한다.
            transition = await self._contracts.collection.update_one(
                {
                    "_id": contract_id,
                    "contract_status": {
                        "$in": sorted(_INCIDENT_REPORTABLE_CONTRACT_STATUSES)
                    },
                },
                {
                    "$set": {
                        "contract_status": ContractStatus.INCIDENT_REPORTED.value,
                        "updated_at": now,
                    }
                },
            )
            if transition.matched_count == 0:
                await self._incidents.collection.delete_one({"_id": doc["_id"]})
                current = await self._contracts.get_by_id(contract_id)
                raise StateConflictError(
                    "다른 요청이 계약 상태를 먼저 변경했습니다. 최신 상태를 확인하세요.",
                    details={"current_status": (current or {}).get("contract_status")},
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
            source=incident_source,
        )
        return _to_response(doc)

    async def get(self, incident_id: str, user_id: str, role: str) -> IncidentResponse:
        doc = await self._incidents.get_by_id(incident_id)
        if not doc:
            raise ResourceNotFoundError("사고 접수 내역을 찾을 수 없습니다.")
        if role not in ("hug_admin", "system_admin") and doc["reporter_user_id"] != user_id:
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
        if doc.get("contract_id"):
            raise StateConflictError(
                "계약에 연결된 사고는 보증이행청구 업무 액션 API로만 처리할 수 있습니다."
            )
        performance_claim = await self._db.performance_claims.find_one({"incident_id": incident_id})
        if performance_claim:
            raise StateConflictError(
                "이행청구가 생성된 사고는 업무 액션 API로만 상태를 변경할 수 있습니다.",
                details={
                    "performance_claim_id": performance_claim["_id"],
                    "current_stage": performance_claim["stage"],
                },
            )
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
            source=doc.get("source") or doc.get("provenance"),
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
        performance_claim_id=doc.get("performance_claim_id"),
        current_stage=doc.get("current_stage", "AccidentNotified"),
        timeline=doc.get("timeline", []),
        next_steps=_NEXT_STEPS[doc["status"]],
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
        source=doc.get("source") or doc.get("provenance"),
    )

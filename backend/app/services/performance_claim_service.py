"""사고통지 이후 보증이행청구 업무를 처리하는 서비스.

사고통지(`incidents`)와 이행청구(`performance_claims`)를 분리하며, 심사·명도·
대위변제·채권등록은 일반 상태 PATCH가 아닌 선행조건을 검증하는 업무 액션으로만
전이한다. 모든 액션은 append-only 감사 이벤트를 남긴다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from app.core.exceptions import (
    PermissionDeniedError,
    ResourceNotFoundError,
    StateConflictError,
    ValidationAppError,
)
from app.models.enums import ContractStatus
from app.repositories.performance_claim_repository import (
    ClaimDocumentRepository,
    ClaimDocumentSubmissionRepository,
    PerformanceClaimEventRepository,
    PerformanceClaimRepository,
    RecoveryClaimRegistrationRepository,
    RecoveryOpeningLedgerRepository,
    SubrogationPaymentRepository,
)
from app.schemas.common import build_pagination
from app.schemas.incident import INCIDENT_TYPE_LABELS
from app.schemas.performance_claim import (
    ClaimDocumentDecisionRequest,
    ClaimDocumentSubmitRequest,
    ClaimDocumentsRequest,
    HandoverActionRequest,
    PerformanceClaimCreateRequest,
    PerformanceClaimDecisionRequest,
    RecoveryClaimCreateRequest,
    RecoveryTransferRequest,
    ReviewStartRequest,
    SubrogationPaymentRequest,
)
from app.schemas.provenance import source_metadata
from app.services.notification_service import NotificationService
from app.utils.datetime_utils import KST, new_uuid, now_kst_iso


SLA_POLICY_CODE = "DEMO_INTERNAL_V1"
SLA_POLICY_BASIS = "시연용 내부 목표기한이며 HUG 공식 이행 SLA가 아님"

_HUG_ROLES = {"hug_admin", "system_admin"}
_EARLY_DOCUMENT_STAGES = {"ClaimReceived", "SupplementRequested", "UnderReview", "OnHold"}
_HANDOVER_DOCUMENT_STAGES = {"Approved", "HandoverScheduled"}
_LEGAL_COST_DOCUMENT_STAGES = {"SubrogationPaid", "RecoveryClaimRegistered"}
_REVIEW_START_STAGES = {"ClaimReceived", "SupplementRequested", "OnHold"}
_PRIMARY_RECOVERY_TYPES = {"RECOURSE_STANDARD", "RECOURSE_NEW_PRODUCT"}

_REQUIRED_DOCUMENTS: dict[str, set[str]] = {
    "JEONSE_RETURN_NONRETURN": {
        "CONTRACT_DOCUMENT",
        "CONTRACT_TERMINATION_PROOF",
        "TENANT_RIGHTS_PROOF",
    },
    "JEONSE_AUCTION_PUBLIC_SALE": {
        "CONTRACT_DOCUMENT",
        "TENANT_RIGHTS_PROOF",
        "AUCTION_DISTRIBUTION_PROOF",
    },
}


@dataclass(frozen=True)
class WorkflowActor:
    user_id: str
    role: str


def _now() -> datetime:
    return datetime.now(KST)


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=KST)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=KST)


def _sla_snapshot(doc: dict[str, Any]) -> dict[str, Any]:
    now = _now()
    started = _parse_datetime(doc.get("claim_sla_started_at")) or now
    base_due = _parse_datetime(doc.get("claim_sla_due_at")) or now
    completed = _parse_datetime(doc.get("sla_completed_at"))
    paused = _parse_datetime(doc.get("sla_paused_at"))
    prior_pause_seconds = int(doc.get("sla_total_paused_seconds", 0) or 0)
    current_pause_seconds = max(0, int((now - paused).total_seconds())) if paused else 0
    total_pause_seconds = prior_pause_seconds + current_pause_seconds
    effective_due = base_due + timedelta(seconds=total_pause_seconds)
    end = completed or now
    elapsed = max(0, int((end - started).total_seconds()) - total_pause_seconds)
    remaining = int((effective_due - now).total_seconds())

    if completed:
        status = "COMPLETED"
    elif paused:
        status = "PAUSED"
    elif remaining < 0:
        status = "OVERDUE"
    elif remaining <= 72 * 60 * 60:
        status = "DUE_SOON"
    else:
        status = "ON_TRACK"

    return {
        "policy_code": doc.get("sla_policy_code", SLA_POLICY_CODE),
        "basis": doc.get("sla_policy_basis", SLA_POLICY_BASIS),
        "status": status,
        "started_at": started.isoformat(),
        "base_due_at": base_due.isoformat(),
        "effective_due_at": effective_due.isoformat(),
        "paused_at": paused.isoformat() if paused else None,
        "pause_reason": doc.get("sla_pause_reason"),
        "total_paused_seconds": total_pause_seconds,
        "elapsed_seconds": elapsed,
        "remaining_seconds": remaining,
        "completed_at": completed.isoformat() if completed else None,
    }


def _document_response(doc: dict[str, Any]) -> dict[str, Any]:
    result = dict(doc)
    result["document_id"] = result.pop("_id")
    return result


def _payment_response(doc: dict[str, Any]) -> dict[str, Any]:
    result = dict(doc)
    result["payment_id"] = result.pop("_id")
    return result


def _recovery_response(doc: dict[str, Any]) -> dict[str, Any]:
    result = dict(doc)
    result["recovery_claim_id"] = result.pop("_id")
    return result


def _event_response(doc: dict[str, Any]) -> dict[str, Any]:
    result = dict(doc)
    result["event_id"] = result.pop("_id")
    return result


class PerformanceClaimService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._db = db
        self._claims = PerformanceClaimRepository(db)
        self._documents = ClaimDocumentRepository(db)
        self._document_submissions = ClaimDocumentSubmissionRepository(db)
        self._payments = SubrogationPaymentRepository(db)
        self._recovery_claims = RecoveryClaimRegistrationRepository(db)
        self._recovery_ledger = RecoveryOpeningLedgerRepository(db)
        self._events = PerformanceClaimEventRepository(db)
        self._notifications = NotificationService(db)

    @staticmethod
    def _require_hug(actor: WorkflowActor) -> None:
        if actor.role not in _HUG_ROLES:
            raise PermissionDeniedError("HUG 보증이행 담당자만 수행할 수 있는 작업입니다.")

    async def _require_active_hug_assignee(self, user_id: str) -> dict[str, Any]:
        user = await self._db.users.find_one({"_id": user_id})
        if not user or not user.get("is_active", True) or user.get("role") not in _HUG_ROLES:
            raise ValidationAppError(
                "담당자는 활성 HUG 업무 사용자여야 합니다.",
                details={"assignee_user_id": user_id},
            )
        return user

    async def _authorize_read(self, claim: dict[str, Any], actor: WorkflowActor) -> None:
        if actor.role in _HUG_ROLES:
            return
        incident = await self._db.incidents.find_one({"_id": claim["incident_id"]})
        if not incident or incident.get("reporter_user_id") != actor.user_id:
            raise PermissionDeniedError("본인의 보증이행청구만 조회할 수 있습니다.")

    async def _get_claim(self, claim_id: str) -> dict[str, Any]:
        claim = await self._claims.get_by_id(claim_id)
        if not claim:
            raise ResourceNotFoundError("보증이행청구를 찾을 수 없습니다.")
        return claim

    async def _audit(
        self,
        *,
        claim_id: str,
        action: str,
        before_stage: str | None,
        after_stage: str | None,
        actor: WorkflowActor,
        request_id: str,
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        claim = await self._claims.get_by_id(claim_id)
        event_source = (claim or {}).get("source")
        if not event_source:
            event_source = source_metadata(
                data_mode="LIVE",
                source_type="user_submitted",
                source_dataset="performance_claim_events",
                as_of_date=now_kst_iso()[:10],
                basis="보증이행청구 업무 액션 감사이력",
                is_demo=False,
            )
        event = {
            "_id": new_uuid(),
            "performance_claim_id": claim_id,
            "action": action,
            "before_stage": before_stage,
            "after_stage": after_stage,
            "actor_user_id": actor.user_id,
            "actor_role": actor.role,
            "request_id": request_id[:200],
            "reason": reason,
            "metadata": metadata or {},
            "source": event_source,
            "provenance": event_source,
            "source_type": event_source["source_type"],
            "basis": event_source["basis"],
            "is_demo": event_source["is_demo"],
            "scenario_id": event_source.get("scenario_id"),
            "occurred_at": now_kst_iso(),
        }
        await self._events.insert(event)
        return event

    async def _sync_incident(
        self, claim: dict[str, Any], *, incident_status: str | None = None
    ) -> None:
        fields: dict[str, Any] = {
            "current_stage": claim["stage"],
            "performance_claim_id": claim["_id"],
            "updated_at": now_kst_iso(),
        }
        if incident_status:
            fields["status"] = incident_status
        await self._db.incidents.update_one({"_id": claim["incident_id"]}, {"$set": fields})

    async def _transition(
        self,
        claim: dict[str, Any],
        *,
        expected_stages: set[str],
        new_stage: str,
        fields: dict[str, Any],
        action: str,
        actor: WorkflowActor,
        request_id: str,
        reason: str | None,
        metadata: dict[str, Any] | None = None,
        incident_status: str | None = None,
    ) -> dict[str, Any]:
        before_stage = claim["stage"]
        now = now_kst_iso()
        fields = {
            **fields,
            "stage": new_stage,
            "stage_entered_at": now if new_stage != before_stage else claim.get("stage_entered_at", now),
            "updated_at": now,
        }
        updated = await self._claims.cas_update(
            claim["_id"],
            expected_stages=expected_stages,
            expected_version=int(claim.get("version", 1)),
            fields=fields,
        )
        if not updated:
            current = await self._claims.get_by_id(claim["_id"])
            raise StateConflictError(
                "다른 요청이 먼저 상태를 변경했거나 현재 단계에서는 수행할 수 없습니다.",
                details={
                    "expected_stages": sorted(expected_stages),
                    "current_stage": current.get("stage") if current else None,
                    "current_version": current.get("version") if current else None,
                },
            )
        await self._sync_incident(updated, incident_status=incident_status)
        await self._audit(
            claim_id=claim["_id"],
            action=action,
            before_stage=before_stage,
            after_stage=new_stage,
            actor=actor,
            request_id=request_id,
            reason=reason,
            metadata=metadata,
        )
        return updated

    def _default_source(self, now: str, *, incident_id: str) -> dict[str, Any]:
        return source_metadata(
            data_mode="LIVE",
            source_type="user_submitted",
            source_dataset="performance_claims",
            as_of_date=now[:10],
            basis="임차인 사고통지 후 HUG 담당자가 접수한 보증이행청구 업무대장",
            input_snapshot={"incident_id": incident_id},
            is_demo=False,
        )

    async def create_claim(
        self,
        incident_id: str,
        payload: PerformanceClaimCreateRequest,
        actor: WorkflowActor,
        request_id: str,
    ) -> dict[str, Any]:
        self._require_hug(actor)
        if payload.assignee_user_id:
            await self._require_active_hug_assignee(payload.assignee_user_id)
        incident = await self._db.incidents.find_one({"_id": incident_id})
        if not incident:
            raise ResourceNotFoundError("사고 접수 내역을 찾을 수 없습니다.")
        if incident.get("status") != "Received":
            raise StateConflictError("신규 접수 상태의 사고에서만 이행청구를 생성할 수 있습니다.")
        if not incident.get("contract_id"):
            raise StateConflictError("계약이 연결된 사고만 보증이행청구로 접수할 수 있습니다.")
        if await self._claims.find_by_incident(incident_id):
            raise StateConflictError("해당 사고에 이미 보증이행청구가 존재합니다.")

        contract = await self._db.contracts.find_one({"_id": incident["contract_id"]})
        if not contract:
            raise ResourceNotFoundError("연결된 계약을 찾을 수 없습니다.")
        exposure = int(contract.get("guarantee_amount") or contract.get("deposit") or 0)
        if exposure and payload.claim_amount > exposure:
            raise ValidationAppError(
                "청구금액은 보증 노출액을 초과할 수 없습니다.",
                details={"claim_amount": payload.claim_amount, "guarantee_exposure": exposure},
            )

        inferred = {
            "DEPOSIT_NOT_RETURNED": ("CONTRACT_END_NONRETURN", "JEONSE_RETURN_NONRETURN"),
            "AUCTION_STARTED": ("AUCTION_PUBLIC_SALE", "JEONSE_AUCTION_PUBLIC_SALE"),
        }.get(incident.get("incident_type"))
        if inferred:
            if payload.official_accident_type and payload.official_accident_type != inferred[0]:
                raise ValidationAppError("신고유형과 공식 사고유형이 일치하지 않습니다.")
            if payload.workflow_type and payload.workflow_type != inferred[1]:
                raise ValidationAppError("신고유형과 workflow_type이 일치하지 않습니다.")
            official_type = payload.official_accident_type or inferred[0]
            workflow_type = payload.workflow_type or inferred[1]
        elif payload.official_accident_type and payload.workflow_type:
            official_type = payload.official_accident_type
            workflow_type = payload.workflow_type
        else:
            raise ValidationAppError(
                "의심 신고는 HUG 담당자가 공식 사고유형과 workflow_type을 지정해야 합니다."
            )
        expected_workflow = {
            "CONTRACT_END_NONRETURN": "JEONSE_RETURN_NONRETURN",
            "AUCTION_PUBLIC_SALE": "JEONSE_AUCTION_PUBLIC_SALE",
        }[official_type]
        if workflow_type != expected_workflow:
            raise ValidationAppError("공식 사고유형과 workflow_type이 일치하지 않습니다.")

        handover_required = workflow_type == "JEONSE_RETURN_NONRETURN"
        if payload.handover_required is not None and payload.handover_required != handover_required:
            raise ValidationAppError("workflow_type과 handover_required가 일치하지 않습니다.")

        now_dt = _now()
        now = now_dt.isoformat()
        # 출처는 API 호출자가 지정하지 못한다. 연결 계약이 시연 Seed면 그 출처를
        # 상속하고, 그 외에는 서버가 LIVE 업무대장 출처를 생성한다.
        source = contract.get("source") or self._default_source(now, incident_id=incident_id)
        claim_id = new_uuid()
        claim = {
            "_id": claim_id,
            "incident_id": incident_id,
            "contract_id": incident["contract_id"],
            "reporter_user_id": incident["reporter_user_id"],
            "official_accident_type": official_type,
            "workflow_type": workflow_type,
            "workflow_version": payload.workflow_version,
            "product_name": payload.product_name,
            "stage": "ClaimReceived",
            "version": 1,
            "claim_amount": payload.claim_amount,
            "approved_amount": None,
            "paid_amount": 0,
            "decision": None,
            "decision_reason": None,
            "handover_required": handover_required,
            "moveout_due_at": None,
            "assignee_user_id": payload.assignee_user_id or actor.user_id,
            "sla_policy_code": SLA_POLICY_CODE,
            "sla_policy_basis": SLA_POLICY_BASIS,
            "claim_sla_started_at": now,
            "claim_sla_due_at": (now_dt + timedelta(days=payload.claim_sla_days)).isoformat(),
            "sla_paused_at": None,
            "sla_pause_reason": None,
            "sla_total_paused_seconds": 0,
            "sla_completed_at": None,
            "source": source,
            "is_demo": bool(source.get("is_demo", False)),
            "scenario_id": source.get("scenario_id"),
            "stage_entered_at": now,
            "created_at": now,
            "updated_at": now,
        }
        try:
            await self._claims.insert(claim)
        except DuplicateKeyError as exc:
            raise StateConflictError("해당 사고에 이미 보증이행청구가 존재합니다.") from exc

        incident_result = await self._db.incidents.update_one(
            {
                "_id": incident_id,
                "status": "Received",
                "$or": [
                    {"performance_claim_id": {"$exists": False}},
                    {"performance_claim_id": None},
                ],
            },
            {
                "$set": {
                    "status": "Reviewing",
                    "performance_claim_id": claim_id,
                    "current_stage": "ClaimReceived",
                    "updated_at": now,
                }
            },
        )
        if incident_result.matched_count == 0:
            await self._claims.collection.delete_one({"_id": claim_id})
            raise StateConflictError("다른 요청이 먼저 이행청구를 생성하거나 사고 상태를 변경했습니다.")

        await self._audit(
            claim_id=claim_id,
            action="CLAIM_RECEIVED",
            before_stage=None,
            after_stage="ClaimReceived",
            actor=actor,
            request_id=request_id,
            reason="보증이행청구 접수",
            metadata={
                "incident_id": incident_id,
                "claim_amount": payload.claim_amount,
                "workflow_type": workflow_type,
                "sla_policy_code": SLA_POLICY_CODE,
            },
        )
        await self._notifications.notify(
            user_id=incident["reporter_user_id"],
            category="incident_update",
            title="보증이행청구가 접수되었습니다",
            body=f"이행청구번호 {claim_id[:8]}의 서류 확인을 시작합니다.",
            severity="info",
            link=f"/tenant/incidents/{incident_id}",
            source=source,
        )
        return await self._claim_detail(claim)

    async def _claim_detail(self, claim: dict[str, Any]) -> dict[str, Any]:
        documents = await self._documents.list_for_claim(claim["_id"])
        payments = await self._payments.list_for_claim(claim["_id"])
        recovery_claims = await self._recovery_claims.list_for_performance_claim(claim["_id"])
        result = dict(claim)
        result["performance_claim_id"] = result.pop("_id")
        result["sla"] = _sla_snapshot(claim)
        result["documents"] = [_document_response(doc) for doc in documents]
        result["document_summary"] = {
            "total": len(documents),
            "required": sum(bool(doc.get("required", True)) for doc in documents),
            "verified_or_waived": sum(
                doc.get("verification_status") in {"Verified", "Waived"} for doc in documents
            ),
        }
        result["subrogation_payments"] = [_payment_response(doc) for doc in payments]
        result["recovery_claims"] = [_recovery_response(doc) for doc in recovery_claims]
        return result

    async def get_claim(
        self, claim_id: str, actor: WorkflowActor
    ) -> dict[str, Any]:
        claim = await self._get_claim(claim_id)
        await self._authorize_read(claim, actor)
        return await self._claim_detail(claim)

    async def list_events(self, claim_id: str, actor: WorkflowActor) -> dict[str, Any]:
        claim = await self._get_claim(claim_id)
        await self._authorize_read(claim, actor)
        events = await self._events.list_for_claim(claim_id)
        return {"items": [_event_response(event) for event in events], "total": len(events)}

    def _incident_response(self, incident: dict[str, Any]) -> dict[str, Any]:
        return {
            "incident_id": incident["_id"],
            "reporter_user_id": incident["reporter_user_id"],
            "incident_type": incident["incident_type"],
            "incident_type_label": INCIDENT_TYPE_LABELS.get(incident["incident_type"], "기타"),
            "description": incident["description"],
            "contract_id": incident.get("contract_id"),
            "property_id": incident.get("property_id"),
            "deposit_amount": incident.get("deposit_amount"),
            "occurred_date": incident.get("occurred_date"),
            "status": incident["status"],
            "performance_claim_id": incident.get("performance_claim_id"),
            "current_stage": incident.get("current_stage", "AccidentNotified"),
            "timeline": incident.get("timeline", []),
            "source": incident.get("source") or incident.get("provenance"),
            "created_at": incident["created_at"],
            "updated_at": incident["updated_at"],
        }

    async def list_hug_incidents(
        self,
        *,
        page: int,
        size: int,
        status: str | None,
        incident_type: str | None,
        stage: str | None,
        sla_status: str | None,
        actor: WorkflowActor,
    ) -> dict[str, Any]:
        self._require_hug(actor)
        query: dict[str, Any] = {}
        if status:
            query["status"] = status
        if incident_type:
            query["incident_type"] = incident_type
        cursor = self._db.incidents.find(query).sort("created_at", -1)
        incidents = [doc async for doc in cursor]
        # 화면 표시명은 주소로 통일한다(§20.1) — 목록용 property 일괄 조회.
        property_ids = list(
            {doc.get("property_id") for doc in incidents if doc.get("property_id")}
        )
        properties = {
            doc["_id"]: doc
            async for doc in self._db.properties.find({"_id": {"$in": property_ids}})
        }
        enriched: list[dict[str, Any]] = []
        for incident in incidents:
            claim = await self._claims.find_by_incident(incident["_id"])
            if stage and (not claim or claim.get("stage") != stage):
                continue
            claim_summary = None
            if claim:
                sla = _sla_snapshot(claim)
                if sla_status and sla["status"] != sla_status:
                    continue
                claim_summary = {
                    "performance_claim_id": claim["_id"],
                    "stage": claim["stage"],
                    "claim_amount": claim["claim_amount"],
                    "approved_amount": claim.get("approved_amount"),
                    "assignee_user_id": claim.get("assignee_user_id"),
                    "sla": sla,
                    "source": claim.get("source"),
                }
            elif sla_status:
                continue
            row = self._incident_response(incident)
            address = (properties.get(incident.get("property_id")) or {}).get("address", {})
            row["address_summary"] = address.get("road_address") or address.get("jibun_address")
            row["performance_claim"] = claim_summary
            enriched.append(row)
        total = len(enriched)
        start = (page - 1) * size
        return {
            "items": enriched[start : start + size],
            "pagination": build_pagination(page, size, total).model_dump(),
        }

    async def get_hug_incident(self, incident_id: str, actor: WorkflowActor) -> dict[str, Any]:
        self._require_hug(actor)
        incident = await self._db.incidents.find_one({"_id": incident_id})
        if not incident:
            raise ResourceNotFoundError("사고 접수 내역을 찾을 수 없습니다.")
        result = self._incident_response(incident)
        claim = await self._claims.find_by_incident(incident_id)
        result["performance_claim"] = await self._claim_detail(claim) if claim else None
        return result

    async def request_documents(
        self,
        claim_id: str,
        payload: ClaimDocumentsRequest,
        actor: WorkflowActor,
        request_id: str,
    ) -> dict[str, Any]:
        self._require_hug(actor)
        claim = await self._get_claim(claim_id)
        stage = claim["stage"]
        allowed = _EARLY_DOCUMENT_STAGES | _HANDOVER_DOCUMENT_STAGES | _LEGAL_COST_DOCUMENT_STAGES
        if stage not in allowed:
            raise StateConflictError("현재 단계에서는 서류를 요청할 수 없습니다.")

        now_dt = _now()
        requested_types = [item.document_type.value for item in payload.documents]
        if len(requested_types) != len(set(requested_types)):
            raise ValidationAppError("한 요청에 동일한 document_type을 중복할 수 없습니다.")
        for item in payload.documents:
            if item.due_at and _aware(item.due_at) <= now_dt:
                raise ValidationAppError("서류 제출기한은 현재보다 이후여야 합니다.")
            if await self._documents.find_by_type(claim_id, item.document_type.value):
                raise StateConflictError(
                    f"{item.document_type.value} 서류 요청이 이미 존재합니다. 기존 요청을 사용하세요."
                )
            if stage in _HANDOVER_DOCUMENT_STAGES and item.document_type.value != "HANDOVER_PROOF":
                raise StateConflictError("승인·명도 단계에서는 명도 증빙만 추가 요청할 수 있습니다.")
            if stage in _LEGAL_COST_DOCUMENT_STAGES and item.document_type.value != "LEGAL_COST_PROOF":
                raise StateConflictError("대위변제 이후에는 소송비용 증빙만 추가 요청할 수 있습니다.")

        now = now_dt.isoformat()
        docs: list[dict[str, Any]] = []
        try:
            for item in payload.documents:
                doc = {
                    "_id": new_uuid(),
                    "performance_claim_id": claim_id,
                    "document_type": item.document_type.value,
                    "required": item.required,
                    "request_reason": item.reason,
                    "due_at": _aware(item.due_at).isoformat() if item.due_at else None,
                    "verification_status": "Requested",
                    "version": 1,
                    "submissions": [],
                    "requested_by_user_id": actor.user_id,
                    "requested_at": now,
                    "submitted_at": None,
                    "verified_at": None,
                    "updated_at": now,
                }
                await self._documents.insert(doc)
                docs.append(doc)
        except DuplicateKeyError as exc:
            if docs:
                await self._documents.collection.delete_many(
                    {"_id": {"$in": [doc["_id"] for doc in docs]}}
                )
            raise StateConflictError(
                "다른 요청이 동일한 청구서류를 먼저 생성했습니다. 현재 목록을 새로고침하세요."
            ) from exc
        except Exception:
            if docs:
                await self._documents.collection.delete_many(
                    {"_id": {"$in": [doc["_id"] for doc in docs]}}
                )
            raise

        fields: dict[str, Any] = {}
        new_stage = stage
        if stage in _EARLY_DOCUMENT_STAGES:
            new_stage = "SupplementRequested"
            if not claim.get("sla_paused_at"):
                fields.update(
                    {
                        "sla_paused_at": now,
                        "sla_pause_reason": "보완서류 제출 대기",
                    }
                )
        try:
            updated = await self._transition(
                claim,
                expected_stages={stage},
                new_stage=new_stage,
                fields=fields,
                action="DOCUMENTS_REQUESTED",
                actor=actor,
                request_id=request_id,
                reason="; ".join(item.reason for item in payload.documents),
                metadata={
                    "document_ids": [doc["_id"] for doc in docs],
                    "document_types": requested_types,
                },
            )
        except Exception:
            await self._documents.collection.delete_many(
                {"_id": {"$in": [doc["_id"] for doc in docs]}}
            )
            raise
        await self._notifications.notify(
            user_id=claim["reporter_user_id"],
            category="incident_update",
            title="보증이행 보완서류가 요청되었습니다",
            body=f"요청서류 {len(docs)}건과 제출기한을 확인해 주세요.",
            severity="warning",
            link=f"/tenant/incidents/{claim['incident_id']}",
            source=claim.get("source"),
        )
        result = await self._claim_detail(updated)
        result["requested_documents"] = [_document_response(doc) for doc in docs]
        return result

    async def submit_document(
        self,
        claim_id: str,
        document_id: str,
        payload: ClaimDocumentSubmitRequest,
        actor: WorkflowActor,
        request_id: str,
    ) -> dict[str, Any]:
        claim = await self._get_claim(claim_id)
        if actor.role not in _HUG_ROLES and claim.get("reporter_user_id") != actor.user_id:
            raise PermissionDeniedError("청구인 본인만 서류를 제출할 수 있습니다.")
        document = await self._documents.get_by_id(document_id)
        if not document or document.get("performance_claim_id") != claim_id:
            raise ResourceNotFoundError("청구서류 요청을 찾을 수 없습니다.")
        document_hash = payload.document_hash.lower()
        if await self._documents.find_duplicate_hash(claim_id, document_hash):
            raise StateConflictError("동일한 문서가 이미 제출되었습니다.")

        now = now_kst_iso()
        reservation = {
            "_id": new_uuid(),
            "performance_claim_id": claim_id,
            "claim_document_id": document_id,
            "document_hash": document_hash,
            "status": "PENDING",
            "created_at": now,
            "updated_at": now,
        }
        try:
            await self._document_submissions.insert(reservation)
        except DuplicateKeyError as exc:
            raise StateConflictError("동일한 문서가 이미 제출 또는 처리 중입니다.") from exc
        submission = {
            "submission_id": new_uuid(),
            "file_name": payload.file_name,
            "document_hash": document_hash,
            "object_uri": payload.object_uri,
            "note": payload.note,
            "submitter_user_id": actor.user_id,
            "submitted_at": now,
        }
        updated = await self._documents.cas_update(
            document_id,
            expected_statuses={"Requested", "Rejected"},
            expected_version=int(document.get("version", 1)),
            fields={
                "verification_status": "Submitted",
                "submitted_at": now,
                "submitter_user_id": actor.user_id,
                "reviewer_user_id": None,
                "review_reason": None,
                "updated_at": now,
            },
            push_submission=submission,
        )
        if not updated:
            await self._document_submissions.collection.delete_one(
                {"_id": reservation["_id"], "status": "PENDING"}
            )
            raise StateConflictError("다른 요청이 먼저 서류 상태를 변경했습니다.")
        await self._document_submissions.collection.update_one(
            {"_id": reservation["_id"], "status": "PENDING"},
            {"$set": {"status": "COMMITTED", "updated_at": now}},
        )
        await self._audit(
            claim_id=claim_id,
            action="DOCUMENT_SUBMITTED",
            before_stage=claim["stage"],
            after_stage=claim["stage"],
            actor=actor,
            request_id=request_id,
            reason=payload.note,
            metadata={
                "document_id": document_id,
                "document_type": document["document_type"],
                "document_hash": document_hash,
            },
        )
        return _document_response(updated)

    async def decide_document(
        self,
        claim_id: str,
        document_id: str,
        payload: ClaimDocumentDecisionRequest,
        actor: WorkflowActor,
        request_id: str,
    ) -> dict[str, Any]:
        self._require_hug(actor)
        claim = await self._get_claim(claim_id)
        document = await self._documents.get_by_id(document_id)
        if not document or document.get("performance_claim_id") != claim_id:
            raise ResourceNotFoundError("청구서류를 찾을 수 없습니다.")

        status_map = {"VERIFY": "Verified", "REJECT": "Rejected", "WAIVE": "Waived"}
        expected = {"Submitted"} if payload.decision != "WAIVE" else {"Requested", "Rejected"}
        now = now_kst_iso()
        updated = await self._documents.cas_update(
            document_id,
            expected_statuses=expected,
            expected_version=int(document.get("version", 1)),
            fields={
                "verification_status": status_map[payload.decision],
                "reviewer_user_id": actor.user_id,
                "review_reason": payload.reason,
                "verified_at": now if payload.decision in {"VERIFY", "WAIVE"} else None,
                "updated_at": now,
            },
        )
        if not updated:
            raise StateConflictError(
                "현재 서류 상태에서는 해당 결정을 할 수 없습니다.",
                details={"current_status": document.get("verification_status")},
            )
        await self._audit(
            claim_id=claim_id,
            action=f"DOCUMENT_{payload.decision}",
            before_stage=claim["stage"],
            after_stage=claim["stage"],
            actor=actor,
            request_id=request_id,
            reason=payload.reason,
            metadata={"document_id": document_id, "document_type": document["document_type"]},
        )
        return _document_response(updated)

    async def start_review(
        self,
        claim_id: str,
        payload: ReviewStartRequest,
        actor: WorkflowActor,
        request_id: str,
    ) -> dict[str, Any]:
        self._require_hug(actor)
        claim = await self._get_claim(claim_id)
        if claim["stage"] not in _REVIEW_START_STAGES:
            raise StateConflictError("현재 단계에서는 심사를 시작할 수 없습니다.")
        documents = await self._documents.list_for_claim(claim_id)
        completed_types = {
            doc["document_type"]
            for doc in documents
            if doc.get("verification_status") in {"Verified", "Waived"}
        }
        required_types = _REQUIRED_DOCUMENTS[claim["workflow_type"]]
        missing = sorted(required_types - completed_types)
        if missing:
            raise StateConflictError(
                "필수 청구서류가 검증되지 않았습니다.",
                details={"missing_document_types": missing},
            )

        now_dt = _now()
        fields: dict[str, Any] = {"review_started_at": now_dt.isoformat()}
        if claim.get("sla_paused_at"):
            paused_at = _parse_datetime(claim["sla_paused_at"])
            pause_seconds = max(0, int((now_dt - paused_at).total_seconds())) if paused_at else 0
            fields.update(
                {
                    "sla_total_paused_seconds": int(claim.get("sla_total_paused_seconds", 0))
                    + pause_seconds,
                    "sla_paused_at": None,
                    "sla_pause_reason": None,
                }
            )
        updated = await self._transition(
            claim,
            expected_stages=_REVIEW_START_STAGES,
            new_stage="UnderReview",
            fields=fields,
            action="REVIEW_STARTED",
            actor=actor,
            request_id=request_id,
            reason=payload.note or "필수서류 확인 후 이행심사 시작",
            metadata={"verified_document_types": sorted(completed_types)},
        )
        return await self._claim_detail(updated)

    async def decide_claim(
        self,
        claim_id: str,
        payload: PerformanceClaimDecisionRequest,
        actor: WorkflowActor,
        request_id: str,
    ) -> dict[str, Any]:
        self._require_hug(actor)
        claim = await self._get_claim(claim_id)
        if claim["stage"] != "UnderReview":
            raise StateConflictError("심사중인 청구에만 결정을 기록할 수 있습니다.")
        if payload.approved_amount and payload.approved_amount > claim["claim_amount"]:
            raise ValidationAppError("승인금액은 청구금액을 초과할 수 없습니다.")

        now = now_kst_iso()
        if payload.decision == "APPROVE":
            new_stage = "Approved"
            fields = {
                "decision": "Approved",
                "decision_reason": payload.reason,
                "approved_amount": payload.approved_amount,
                "decision_at": now,
                "sla_completed_at": now,
            }
            incident_status = None
        elif payload.decision == "ON_HOLD":
            new_stage = "OnHold"
            fields = {
                "decision": "OnHold",
                "decision_reason": payload.reason,
                "decision_at": now,
                "sla_paused_at": now,
                "sla_pause_reason": payload.reason,
            }
            incident_status = None
        else:
            new_stage = "Rejected"
            contract = await self._db.contracts.find_one({"_id": claim["contract_id"]})
            contract_end = None
            if contract and contract.get("contract_end_date"):
                try:
                    contract_end = datetime.fromisoformat(
                        str(contract["contract_end_date"])
                    ).date()
                except ValueError:
                    contract_end = None
            rejection_contract_status = (
                ContractStatus.MONITORING.value
                if contract_end and contract_end >= _now().date()
                else ContractStatus.CONTRACT_FINALIZED.value
            )
            fields = {
                "decision": "Rejected",
                "decision_reason": payload.reason,
                "approved_amount": None,
                "decision_at": now,
                "sla_completed_at": now,
                "contract_status_after_rejection": rejection_contract_status,
            }
            incident_status = "Closed"

        updated = await self._transition(
            claim,
            expected_stages={"UnderReview"},
            new_stage=new_stage,
            fields=fields,
            action=f"CLAIM_{payload.decision}",
            actor=actor,
            request_id=request_id,
            reason=payload.reason,
            metadata={"approved_amount": payload.approved_amount},
            incident_status=incident_status,
        )
        if payload.decision == "REJECT":
            contract_result = await self._db.contracts.update_one(
                {
                    "_id": claim["contract_id"],
                    "contract_status": ContractStatus.INCIDENT_REPORTED.value,
                },
                {
                    "$set": {
                        "contract_status": rejection_contract_status,
                        "updated_at": now,
                    }
                },
            )
            if contract_result.matched_count:
                await self._db.timeline_events.insert_one(
                    {
                        "_id": new_uuid(),
                        "contract_id": claim["contract_id"],
                        "event_type": "PerformanceClaimRejected",
                        "occurred_at": now,
                        "blockchain_status": "NotRequested",
                        "blockchain_tx_id": None,
                    }
                )
        await self._notifications.notify(
            user_id=claim["reporter_user_id"],
            category="incident_update",
            title={
                "APPROVE": "보증이행청구가 승인되었습니다",
                "ON_HOLD": "보증이행청구가 유보되었습니다",
                "REJECT": "보증이행청구 심사결과를 확인해 주세요",
            }[payload.decision],
            body=payload.reason,
            severity="info" if payload.decision == "APPROVE" else "warning",
            link=f"/tenant/incidents/{claim['incident_id']}",
            source=claim.get("source"),
        )
        return await self._claim_detail(updated)

    async def handover(
        self,
        claim_id: str,
        payload: HandoverActionRequest,
        actor: WorkflowActor,
        request_id: str,
    ) -> dict[str, Any]:
        self._require_hug(actor)
        claim = await self._get_claim(claim_id)
        if not claim.get("handover_required"):
            raise StateConflictError("경·공매 이행 workflow에는 명도 단계가 적용되지 않습니다.")

        if payload.action == "SCHEDULE":
            if claim["stage"] != "Approved":
                raise StateConflictError("승인된 청구만 명도일을 예약할 수 있습니다.")
            moveout = _aware(payload.moveout_due_at)
            if moveout <= _now():
                raise ValidationAppError("명도 예정일은 현재보다 이후여야 합니다.")
            updated = await self._transition(
                claim,
                expected_stages={"Approved"},
                new_stage="HandoverScheduled",
                fields={"moveout_due_at": moveout.isoformat(), "handover_scheduled_at": now_kst_iso()},
                action="HANDOVER_SCHEDULED",
                actor=actor,
                request_id=request_id,
                reason=payload.reason,
                metadata={"moveout_due_at": moveout.isoformat()},
            )
        else:
            if claim["stage"] != "HandoverScheduled":
                raise StateConflictError("명도 예약 상태에서만 완료 처리할 수 있습니다.")
            documents = await self._documents.list_for_claim(claim_id)
            proof = next(
                (
                    doc
                    for doc in documents
                    if doc.get("document_type") == "HANDOVER_PROOF"
                    and doc.get("verification_status") in {"Verified", "Waived"}
                ),
                None,
            )
            if not proof:
                raise StateConflictError("검증된 명도 증빙이 필요합니다.")
            updated = await self._transition(
                claim,
                expected_stages={"HandoverScheduled"},
                new_stage="HandoverCompleted",
                fields={
                    "handover_completed_at": now_kst_iso(),
                    "settlement_confirmed": True,
                },
                action="HANDOVER_COMPLETED",
                actor=actor,
                request_id=request_id,
                reason=payload.reason,
                metadata={"handover_document_id": proof["_id"]},
            )
        return await self._claim_detail(updated)

    async def record_subrogation_payment(
        self,
        claim_id: str,
        payload: SubrogationPaymentRequest,
        actor: WorkflowActor,
        request_id: str,
    ) -> dict[str, Any]:
        self._require_hug(actor)
        claim = await self._get_claim(claim_id)
        allowed_stage = "HandoverCompleted" if claim.get("handover_required") else "Approved"
        if claim["stage"] != allowed_stage:
            raise StateConflictError(
                "명도 완료(경·공매 workflow는 승인) 후에만 대위변제를 기록할 수 있습니다."
            )
        if payload.paid_at > _now().date():
            raise ValidationAppError("미래 지급일을 기록할 수 없습니다.")
        if await self._payments.find_by_reference(payload.payment_reference):
            raise StateConflictError("이미 등록된 지급 참조번호입니다.")
        approved = int(claim.get("approved_amount") or 0)
        new_paid = int(claim.get("paid_amount") or 0) + payload.paid_amount
        if new_paid > approved:
            raise ValidationAppError(
                "누적 대위변제액은 승인금액을 초과할 수 없습니다.",
                details={"approved_amount": approved, "new_paid_amount": new_paid},
            )

        now = now_kst_iso()
        payment = {
            "_id": new_uuid(),
            "performance_claim_id": claim_id,
            "payment_reference": payload.payment_reference,
            "paid_amount": payload.paid_amount,
            "paid_at": payload.paid_at.isoformat(),
            "recorded_by_user_id": actor.user_id,
            "reason": payload.reason,
            "source": claim.get("source"),
            "created_at": now,
        }
        try:
            await self._payments.insert(payment)
        except DuplicateKeyError as exc:
            raise StateConflictError("이미 등록된 지급 참조번호입니다.") from exc

        new_stage = "SubrogationPaid" if new_paid == approved else allowed_stage
        try:
            updated = await self._transition(
                claim,
                expected_stages={allowed_stage},
                new_stage=new_stage,
                fields={
                    "paid_amount": new_paid,
                    "subrogation_paid_at": now if new_stage == "SubrogationPaid" else None,
                },
                action="SUBROGATION_PAYMENT_RECORDED",
                actor=actor,
                request_id=request_id,
                reason=payload.reason,
                metadata={
                    "payment_id": payment["_id"],
                    "payment_reference": payload.payment_reference,
                    "paid_amount": payload.paid_amount,
                    "cumulative_paid_amount": new_paid,
                },
            )
        except StateConflictError:
            await self._payments.collection.delete_one({"_id": payment["_id"]})
            raise
        if new_stage == "SubrogationPaid":
            await self._notifications.notify(
                user_id=claim["reporter_user_id"],
                category="incident_update",
                title="대위변제가 완료되었습니다",
                body=f"승인금액 {approved:,}원의 지급이 완료되었습니다.",
                severity="info",
                link=f"/tenant/incidents/{claim['incident_id']}",
                source=claim.get("source"),
            )
        return await self._claim_detail(updated)

    async def register_recovery_claim(
        self,
        claim_id: str,
        payload: RecoveryClaimCreateRequest,
        actor: WorkflowActor,
        request_id: str,
    ) -> dict[str, Any]:
        self._require_hug(actor)
        claim = await self._get_claim(claim_id)
        if claim["stage"] not in {"SubrogationPaid", "RecoveryClaimRegistered"}:
            raise StateConflictError("대위변제 완료 후에만 회수채권을 등록할 수 있습니다.")
        if await self._recovery_claims.find_by_type(claim_id, payload.claim_type):
            raise StateConflictError("동일한 채권구분이 이미 등록되어 있습니다.")

        existing = await self._recovery_claims.list_for_performance_claim(claim_id)
        has_primary = any(doc.get("claim_type") in _PRIMARY_RECOVERY_TYPES for doc in existing)
        if not has_primary and payload.claim_type not in _PRIMARY_RECOVERY_TYPES:
            raise StateConflictError("구상 원금채권을 먼저 등록해야 합니다.")
        if has_primary and payload.claim_type in _PRIMARY_RECOVERY_TYPES:
            raise StateConflictError(
                "구상채권과 구상채권(신상품)은 하나의 대위변제 원금 분류이므로 중복 등록할 수 없습니다."
            )
        if payload.claim_type in _PRIMARY_RECOVERY_TYPES and payload.principal > int(claim["paid_amount"]):
            raise ValidationAppError("구상채권 원금은 대위변제 누적액을 초과할 수 없습니다.")
        if payload.claim_type == "LITIGATION_ADVANCE_COST":
            documents = await self._documents.list_for_claim(claim_id)
            has_cost_proof = any(
                doc.get("document_type") == "LEGAL_COST_PROOF"
                and doc.get("verification_status") in {"Verified", "Waived"}
                for doc in documents
            )
            if not has_cost_proof:
                raise StateConflictError("소송대지급금 등록에는 검증된 소송비용 증빙이 필요합니다.")

        now = now_kst_iso()
        # 회수채권의 data_mode는 상위 이행청구에서만 상속한다. 호출자가 DEMO/LIVE를
        # 바꿔 운영 KPI 포함 여부를 조작할 수 없어야 한다.
        source = claim.get("source")
        zero_balance = {
            "principal": 0,
            "legal_cost": 0,
            "delay_damage": 0,
            "enforcement_cost": 0,
            "total": 0,
        }
        is_litigation_cost = payload.claim_type == "LITIGATION_ADVANCE_COST"
        opening_component = "legal_cost" if is_litigation_cost else "principal"
        opening_entry_type = "LEGAL_COST_ACCRUAL" if is_litigation_cost else "PRINCIPAL_ACCRUAL"
        opening_balance = {
            **zero_balance,
            opening_component: payload.principal,
            "total": payload.principal,
        }
        recovery = {
            "_id": new_uuid(),
            "performance_claim_id": claim_id,
            "contract_id": claim["contract_id"],
            "product_name": payload.product_name,
            "claim_type": payload.claim_type,
            "principal": payload.principal,
            "balance": payload.principal,
            "balances": opening_balance,
            "principal_balance": opening_balance["principal"],
            "legal_cost_balance": opening_balance["legal_cost"],
            "delay_damage_balance": 0,
            "enforcement_cost_balance": 0,
            "incurred_amount": payload.incurred_amount,
            "incurred_date": payload.incurred_date.isoformat(),
            "stage": "Registered",
            "recovery_stage": "Registered",
            "collection_route": "Voluntary",
            "legal_status": "None",
            "auction_status": "None",
            "repayment_plan_status": "None",
            "balance_status": "Unrecovered",
            # 기초 원장이 sequence 1을 차지하므로 회수원장 sequence 카운터를 함께
            # 초기화한다. 이후 원장 쓰기는 version CAS 안에서 이 값을 증가시킨다.
            "ledger_sequence": 1,
            "source": source,
            "is_demo": bool((source or {}).get("is_demo", claim.get("is_demo", False))),
            "scenario_id": (source or {}).get("scenario_id", claim.get("scenario_id")),
            "created_at": now,
            "updated_at": now,
        }
        opening_ledger = {
            "_id": new_uuid(),
            "recovery_claim_id": recovery["_id"],
            "entry_type": opening_entry_type,
            "direction": "INCREASE",
            "amount_won": payload.principal,
            "allocations": {opening_component: payload.principal},
            "allocation_policy": "SYSTEM_OPENING_BALANCE_V1",
            "balance_before": zero_balance,
            "balance_after": opening_balance,
            "note": (
                "소송대지급금 등록에 따른 기초 법적비용 인식"
                if is_litigation_cost
                else "회수채권 등록에 따른 기초 원금 인식"
            ),
            "reference_type": "PERFORMANCE_CLAIM",
            "reference_id": claim_id,
            "actor_user_id": actor.user_id,
            "actor_role": actor.role,
            "request_id": request_id[:200],
            "occurred_at": now,
            "idempotency_key": f"opening:{recovery['_id']}",
            "operation_status": "COMMITTED",
            "sequence": 1,
            "provenance": source,
        }
        try:
            await self._recovery_claims.insert(recovery)
            await self._recovery_ledger.insert(opening_ledger)
        except DuplicateKeyError as exc:
            await self._recovery_claims.collection.delete_one({"_id": recovery["_id"]})
            raise StateConflictError("동일한 채권구분이 이미 등록되어 있습니다.") from exc
        except Exception:
            await self._recovery_claims.collection.delete_one({"_id": recovery["_id"]})
            raise

        recovery_ids = [doc["_id"] for doc in existing] + [recovery["_id"]]
        try:
            updated = await self._transition(
                claim,
                expected_stages={claim["stage"]},
                new_stage="RecoveryClaimRegistered",
                fields={"recovery_claim_ids": recovery_ids},
                action="RECOVERY_CLAIM_REGISTERED",
                actor=actor,
                request_id=request_id,
                reason="대위변제 후 회수채권 등록",
                metadata={
                    "recovery_claim_id": recovery["_id"],
                    "claim_type": payload.claim_type,
                    "principal": payload.principal,
                },
            )
        except StateConflictError:
            await self._recovery_ledger.collection.delete_one({"_id": opening_ledger["_id"]})
            await self._recovery_claims.collection.delete_one({"_id": recovery["_id"]})
            raise
        result = await self._claim_detail(updated)
        result["registered_recovery_claim"] = _recovery_response(recovery)
        result["opening_ledger_entry"] = opening_ledger
        return result

    async def transfer_to_recovery(
        self,
        claim_id: str,
        payload: RecoveryTransferRequest,
        actor: WorkflowActor,
        request_id: str,
    ) -> dict[str, Any]:
        self._require_hug(actor)
        await self._require_active_hug_assignee(payload.assignee_user_id)
        claim = await self._get_claim(claim_id)
        if claim["stage"] != "RecoveryClaimRegistered":
            raise StateConflictError("회수채권 등록 후에만 채권관리로 인계할 수 있습니다.")
        recovery_claims = await self._recovery_claims.list_for_performance_claim(claim_id)
        if not any(doc.get("claim_type") in _PRIMARY_RECOVERY_TYPES for doc in recovery_claims):
            raise StateConflictError("인계할 구상 원금채권이 없습니다.")

        updated = await self._transition(
            claim,
            expected_stages={"RecoveryClaimRegistered"},
            new_stage="TransferredToRecovery",
            fields={
                "recovery_assignee_user_id": payload.assignee_user_id,
                "recovery_next_action": payload.next_action,
                "transferred_to_recovery_at": now_kst_iso(),
            },
            action="TRANSFERRED_TO_RECOVERY",
            actor=actor,
            request_id=request_id,
            reason=payload.reason,
            metadata={
                "assignee_user_id": payload.assignee_user_id,
                "next_action": payload.next_action,
                "recovery_claim_ids": [doc["_id"] for doc in recovery_claims],
            },
            incident_status="TransferredToRecovery",
        )
        await self._db.contracts.update_one(
            {"_id": claim["contract_id"]},
            {
                "$set": {
                    "contract_status": ContractStatus.RECOVERY_IN_PROGRESS.value,
                    "updated_at": now_kst_iso(),
                }
            },
        )
        return await self._claim_detail(updated)

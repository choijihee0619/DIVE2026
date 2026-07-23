"""사고 전 계약의 D-90/60/30 증빙 bundle과 예방 케이스 오케스트레이션."""

from __future__ import annotations

import hashlib
from datetime import date, timedelta
from typing import Any

import numpy as np
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from app.core.exceptions import (
    ModelInferenceFailedError,
    PermissionDeniedError,
    ResourceNotFoundError,
    StateConflictError,
    ValidationAppError,
)
from app.models.enums import ContractStatus, VerificationStatus
from app.repositories.contract_repository import ContractRepository, TimelineRepository
from app.repositories.evidence_repository import EvidenceRequestRepository
from app.repositories.prevention_repository import (
    AccidentPredictionRepository,
    EvidenceBundleRepository,
    PreventionCaseRepository,
    PreventiveActionRepository,
)
from app.repositories.user_repository import UserRepository
from app.schemas.hug_contract import (
    EvidenceBundleResponse,
    PreventionCaseResponse,
    PreventiveActionCreateRequest,
    PreventiveActionResponse,
    PreventiveActionUpdateRequest,
)
from app.schemas.provenance import source_metadata
from app.services.accident_prediction_service import AccidentPredictionService, PRE_INCIDENT_STATUSES
from app.services.notification_service import NotificationService
from app.utils.datetime_utils import new_uuid, now_kst_iso

POLICY_VERSION = "prevention-demo-v1"

# 항목은 프로젝트 제안 사전관리 정책이며 HUG 공식 사고성립 요건이 아니다.
BUNDLE_POLICY: dict[str, dict[str, Any]] = {
    "D90": {
        "sequence": 1,
        "due_offset": -60,
        "items": (
            ("return_plan", "임대인 반환계획", "RETURN_PLAN_DOCUMENT"),
            ("latest_registry", "최신 등기상태", "LATEST_REGISTRY_SNAPSHOT"),
            ("guarantee_status", "보증 유효상태", "GUARANTEE_STATUS_PROOF"),
        ),
    },
    "D60": {
        "sequence": 2,
        "due_offset": -30,
        "items": (
            ("return_funds", "반환재원 증빙", "RETURN_FUNDS_PROOF"),
            ("credit_enhancement", "신용보강 증빙", "CREDIT_ENHANCEMENT_PROOF"),
            ("rights_change", "근저당·압류 변동 점검", "RIGHTS_CHANGE_CHECK"),
        ),
    },
    "D30": {
        "sequence": 3,
        "due_offset": 0,
        "items": (
            ("move_out_schedule", "이사·반환 일정", "MOVE_OUT_SCHEDULE"),
            ("unresolved_risk_review", "미해소 위험 최종 점검", "UNRESOLVED_RISK_REVIEW"),
            ("final_documents", "필수서류 최종 확인", "FINAL_REQUIRED_DOCUMENTS"),
        ),
    },
}

_SUBMITTED = {
    VerificationStatus.SUBMITTED.value,
    VerificationStatus.REVIEWING.value,
    VerificationStatus.VERIFIED.value,
}
_VERIFIED = {VerificationStatus.VERIFIED.value}

_ACTION_TRANSITIONS: dict[str, set[str]] = {
    "Requested": {"InProgress", "Submitted", "Completed", "Cancelled", "Overdue"},
    "InProgress": {"Submitted", "Completed", "Cancelled", "Overdue"},
    "Submitted": {"Verifying", "Completed", "Rejected", "Overdue"},
    "Verifying": {"Completed", "Rejected", "Overdue"},
    "Rejected": {"InProgress", "Submitted", "Cancelled"},
    "Overdue": {"InProgress", "Submitted", "Completed", "Cancelled"},
    "Completed": set(),
    "Cancelled": set(),
}


def dday_stage(d_day: int) -> str | None:
    if d_day > 90:
        return None
    # §20.5 P4 — 만기 경과는 D30과 구분되는 별도 스테이지. 미반환 여부 확인·사고신고 안내 대상.
    if d_day < 0:
        return "OVERDUE"
    if d_day <= 30:
        return "D30"
    if d_day <= 60:
        return "D60"
    return "D90"


def checkpoints_due(d_day: int) -> list[str]:
    if d_day > 90:
        return []
    checkpoints = ["D90"]
    if d_day <= 60:
        checkpoints.append("D60")
    if d_day <= 30:
        checkpoints.append("D30")
    return checkpoints


def _urgency(d_day: int) -> float:
    if d_day <= 30:
        return 1.0
    if d_day <= 60:
        return 0.75
    if d_day <= 90:
        return 0.5
    return 0.0


def calculate_priority_components(
    *,
    risk_percentile: float | None,
    deposit_percentile: float,
    d_day: int,
    unresolved_severity: float,
) -> tuple[float, dict[str, float]]:
    """문서 §5.2 제안 가중치를 그대로 분해해 반환한다."""
    risk = float(np.clip(risk_percentile or 0.0, 0.0, 1.0))
    exposure = float(np.clip(deposit_percentile, 0.0, 1.0))
    urgency = _urgency(d_day)
    unresolved = float(np.clip(unresolved_severity, 0.0, 1.0))
    components = {
        "risk_percentile": round(risk, 6),
        "deposit_percentile": round(exposure, 6),
        "maturity_urgency": round(urgency, 6),
        "unresolved_severity": round(unresolved, 6),
        "risk_weighted": round(risk * 50.0, 2),
        "deposit_weighted": round(exposure * 20.0, 2),
        "maturity_weighted": round(urgency * 15.0, 2),
        "unresolved_weighted": round(unresolved * 15.0, 2),
    }
    score = sum(
        components[key]
        for key in ("risk_weighted", "deposit_weighted", "maturity_weighted", "unresolved_weighted")
    )
    return round(score, 2), components


def _stable_id(prefix: str, *parts: str) -> str:
    value = "|".join(parts).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(value).hexdigest()[:24]}"


def _is_demo(contract: dict[str, Any]) -> bool:
    return str(contract.get("_id", "")).startswith("demo-") or bool(contract.get("is_demo"))


def _workflow_source(contract: dict[str, Any], as_of: date, basis: str) -> dict[str, Any]:
    demo = _is_demo(contract)
    return source_metadata(
        data_mode="DEMO" if demo else "LIVE",
        source_type="demo_scenario" if demo else "user_submitted",
        source_dataset="prevention-demo-seed" if demo else "platform-contract-ledger",
        as_of_date=as_of.isoformat(),
        scenario_id=contract.get("scenario_id"),
        basis=basis,
        is_demo=demo,
    )


def _bundle_response(document: dict[str, Any]) -> EvidenceBundleResponse:
    return EvidenceBundleResponse(
        evidence_bundle_id=document["_id"],
        contract_id=document["contract_id"],
        checkpoint=document["checkpoint"],
        policy_version=document["policy_version"],
        status=document["status"],
        due_at=document["due_at"],
        required_count=document["required_count"],
        submitted_count=document["submitted_count"],
        verified_count=document["verified_count"],
        overdue_count=document["overdue_count"],
        completion_ratio=document["completion_ratio"],
        items=document["items"],
        created_at=document["created_at"],
        updated_at=document["updated_at"],
    )


def _case_response(document: dict[str, Any]) -> PreventionCaseResponse:
    return PreventionCaseResponse(
        prevention_case_id=document["_id"],
        contract_id=document["contract_id"],
        status=document["status"],
        triggers=document.get("triggers", []),
        priority_score=document.get("priority_score", 0.0),
        priority_components=document.get("priority_components", {}),
        owner_user_id=document.get("owner_user_id"),
        owner_center=document.get("owner_center"),
        next_action=document.get("next_action"),
        due_at=document.get("due_at"),
        policy_version=document.get("policy_version", POLICY_VERSION),
        created_at=document["created_at"],
        updated_at=document["updated_at"],
    )


def _action_response(document: dict[str, Any]) -> PreventiveActionResponse:
    return PreventiveActionResponse(
        action_id=document["_id"],
        prevention_case_id=document["prevention_case_id"],
        contract_id=document["contract_id"],
        action_type=document["action_type"],
        status=document["status"],
        actor_role=document["actor_role"],
        actor_user_id=document.get("actor_user_id"),
        target_role=document["target_role"],
        requested_at=document["requested_at"],
        due_at=document.get("due_at"),
        completed_at=document.get("completed_at"),
        note=document.get("note"),
        details=document.get("details", {}),
        audit_log=document.get("audit_log", []),
    )


class PreventionService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._db = db
        self._contracts = ContractRepository(db)
        self._timeline = TimelineRepository(db)
        self._evidence_requests = EvidenceRequestRepository(db)
        self._predictions = AccidentPredictionRepository(db)
        self._cases = PreventionCaseRepository(db)
        self._actions = PreventiveActionRepository(db)
        self._bundles = EvidenceBundleRepository(db)
        self._users = UserRepository(db)
        self._notifications = NotificationService(db)
        self._accident = AccidentPredictionService(db)

    async def _ensure_bundle(
        self, contract: dict[str, Any], checkpoint: str, as_of: date
    ) -> tuple[dict[str, Any], bool, int]:
        policy = BUNDLE_POLICY[checkpoint]
        contract_id = contract["_id"]
        end_date = date.fromisoformat(contract["contract_end_date"])
        due_at = end_date + timedelta(days=policy["due_offset"])
        stable_bundle_id = _stable_id("eb", contract_id, checkpoint, POLICY_VERSION)
        existing = await self._bundles.get_by_id(stable_bundle_id)
        if existing is None:
            existing = await self._bundles.find_checkpoint(
                contract_id, checkpoint, POLICY_VERSION
            )
        bundle_id = existing["_id"] if existing else stable_bundle_id
        now = now_kst_iso()
        items: list[dict[str, Any]] = []
        requests_created = 0

        for item_key, label, evidence_type in policy["items"]:
            request_id = _stable_id("er", bundle_id, item_key)
            request = await self._evidence_requests.get_by_id(request_id)
            if request is None:
                request = await self._evidence_requests.find_bundle_item(bundle_id, item_key)
            if request is None:
                request = {
                    "_id": request_id,
                    "contract_id": contract_id,
                    "risk_assessment_id": contract.get("risk_assessment_id"),
                    "reason": f"{checkpoint} 예방 점검 — {label}",
                    "evidence_type": evidence_type,
                    "due_date": due_at.isoformat(),
                    "verification_status": VerificationStatus.PENDING.value,
                    "bundle_id": bundle_id,
                    "item_key": item_key,
                    "checkpoint": checkpoint,
                    "created_at": now,
                    "updated_at": now,
                    "source": _workflow_source(
                        contract, as_of, f"{checkpoint} 사전예방 필수 증빙 자동 요청"
                    ),
                }
                try:
                    await self._evidence_requests.insert(request)
                    requests_created += 1
                except DuplicateKeyError:
                    request = await self._evidence_requests.find_bundle_item(
                        bundle_id, item_key
                    )
                    if request is None:
                        raise

            request_id = request["_id"]

            verification_status = request.get(
                "verification_status", VerificationStatus.PENDING.value
            )
            is_verified = verification_status in _VERIFIED
            is_overdue = as_of > due_at and not is_verified
            items.append(
                {
                    "item_key": item_key,
                    "label": label,
                    "evidence_type": evidence_type,
                    "evidence_request_id": request_id,
                    "verification_status": verification_status,
                    "due_at": due_at.isoformat(),
                    "is_verified": is_verified,
                    "is_overdue": is_overdue,
                }
            )

        required_count = len(items)
        submitted_count = sum(item["verification_status"] in _SUBMITTED for item in items)
        verified_count = sum(item["is_verified"] for item in items)
        overdue_count = sum(item["is_overdue"] for item in items)
        if verified_count == required_count:
            status = "Completed"
        elif overdue_count:
            status = "Overdue"
        elif submitted_count:
            status = "InReview"
        else:
            status = "Pending"
        document = {
            "_id": bundle_id,
            "contract_id": contract_id,
            "checkpoint": checkpoint,
            "sequence": policy["sequence"],
            "policy_version": POLICY_VERSION,
            "status": status,
            "due_at": due_at.isoformat(),
            "required_count": required_count,
            "submitted_count": submitted_count,
            "verified_count": verified_count,
            "overdue_count": overdue_count,
            "completion_ratio": round(verified_count / required_count, 4),
            "items": items,
            "created_at": existing["created_at"] if existing else now,
            "updated_at": now,
            "source": _workflow_source(contract, as_of, f"{checkpoint} 증빙 bundle"),
        }
        bundle_result = await self._bundles.collection.update_one(
            {"_id": bundle_id}, {"$set": document}, upsert=True
        )
        created = bundle_result.upserted_id is not None

        if created and checkpoint == "D90" and contract.get("contract_status") in {
            ContractStatus.CONTRACT_FINALIZED.value,
            ContractStatus.MONITORING.value,
        }:
            transition = await self._contracts.collection.update_one(
                {
                    "_id": contract_id,
                    "contract_status": {
                        "$in": [
                            ContractStatus.CONTRACT_FINALIZED.value,
                            ContractStatus.MONITORING.value,
                        ]
                    },
                },
                {
                    "$set": {
                        "contract_status": ContractStatus.D90_REQUESTED.value,
                        "updated_at": now,
                    }
                },
            )
            if transition.matched_count:
                timeline_id = _stable_id("te", contract_id, "D90Requested", POLICY_VERSION)
                await self._timeline.collection.update_one(
                    {"_id": timeline_id},
                    {"$setOnInsert": {
                    "_id": timeline_id,
                    "contract_id": contract_id,
                    "event_type": "D90Requested",
                    "occurred_at": now,
                    "blockchain_status": "NotRequested",
                    "blockchain_tx_id": None,
                    }},
                    upsert=True,
                )
        return document, created, requests_created

    async def _risk_assessment(self, contract: dict[str, Any]) -> dict[str, Any] | None:
        risk_id = contract.get("risk_assessment_id")
        if not risk_id:
            return None
        return await self._db.risk_assessments.find_one(
            {"$or": [{"_id": risk_id}, {"case_id": risk_id}]}
        )

    async def _derive_triggers(
        self,
        contract: dict[str, Any],
        prediction: dict[str, Any] | None,
        bundles: list[dict[str, Any]],
        d_day: int,
    ) -> tuple[list[dict[str, Any]], float]:
        triggers: list[dict[str, Any]] = []
        severity = 0.0
        if prediction:
            if prediction.get("prediction_status") != "SUCCESS":
                triggers.append(
                    {
                        "code": "PREDICTION_NOT_SCORABLE",
                        "severity": "medium",
                        "reason": ",".join(prediction.get("failure_reason", [])),
                    }
                )
                severity = max(severity, 0.4)
            elif float(prediction.get("risk_percentile") or 0) >= 0.9:
                triggers.append(
                    {
                        "code": "HIGH_POC_PERCENTILE",
                        "severity": "high",
                        "reason": f"PoC 상대위험 상위 {(1-float(prediction['risk_percentile']))*100:.1f}%",
                    }
                )
                severity = max(severity, 0.8)

        for bundle in bundles:
            if bundle["status"] == "Completed":
                continue
            if bundle["status"] == "Overdue":
                triggers.append(
                    {
                        "code": "EVIDENCE_OVERDUE",
                        "severity": "critical",
                        "checkpoint": bundle["checkpoint"],
                        "reason": f"{bundle['checkpoint']} 필수 증빙 {bundle['overdue_count']}개 기한초과",
                    }
                )
                severity = 1.0
            else:
                triggers.append(
                    {
                        "code": "CHECKPOINT_ACTION_REQUIRED",
                        "severity": "high" if bundle["checkpoint"] == "D30" else "medium",
                        "checkpoint": bundle["checkpoint"],
                        "reason": f"{bundle['checkpoint']} 필수 증빙 진행률 {bundle['completion_ratio']:.0%}",
                    }
                )
                severity = max(severity, 0.7 if bundle["checkpoint"] == "D30" else 0.5)

        assessment = await self._risk_assessment(contract)
        if assessment and assessment.get("risk_grade") == "HIGH":
            triggers.append(
                {
                    "code": "RULE_HIGH_RISK",
                    "severity": "high",
                    "reason": "Rule 기반 위험진단 HIGH",
                }
            )
            severity = max(severity, 0.9)
        if d_day < 0:
            triggers.append(
                {
                    "code": "CONTRACT_MATURITY_PASSED",
                    "severity": "critical",
                    "reason": f"계약 만기 {-d_day}일 경과, 사고요건 수동 확인 필요",
                }
            )
            severity = 1.0
        return triggers, severity

    async def _ensure_case(
        self,
        contract: dict[str, Any],
        triggers: list[dict[str, Any]],
        priority_score: float,
        priority_components: dict[str, float],
        bundles: list[dict[str, Any]],
        as_of: date,
    ) -> tuple[dict[str, Any] | None, bool]:
        existing = await self._cases.find_open_for_contract(contract["_id"])
        now = now_kst_iso()
        if not triggers:
            if existing:
                updated = await self._cases.update_fields(
                    existing["_id"],
                    {
                        "status": "Mitigated",
                        "triggers": [],
                        "priority_score": priority_score,
                        "priority_components": priority_components,
                        "next_action": "정상 모니터링",
                        "due_at": None,
                        "updated_at": now,
                        "mitigated_at": now,
                    },
                )
                return updated, False
            return None, False

        overdue = any(trigger["severity"] == "critical" for trigger in triggers)
        in_review = any(bundle["status"] == "InReview" for bundle in bundles)
        status = "EscalatedMonitoring" if overdue else ("Verifying" if in_review else "RiskDetected")
        if existing and status == "RiskDetected" and existing.get("status") in {
            "Notified",
            "ActionRequested",
            "EvidenceSubmitted",
        }:
            status = existing["status"]
        incomplete_due = sorted(
            bundle["due_at"] for bundle in bundles if bundle["status"] != "Completed"
        )
        maturity_passed = any(
            trigger["code"] == "CONTRACT_MATURITY_PASSED" for trigger in triggers
        )
        next_action = (
            "미반환 여부 확인·사고신고 안내"
            if maturity_passed
            else "기한초과 증빙 확인 및 임차인 권리보전 상담"
            if overdue
            else "필수 증빙 요청·검토 및 신용보강 확인"
        )
        if existing is None:
            existing = await self._cases.collection.find_one(
                {"contract_id": contract["_id"], "policy_version": POLICY_VERSION}
            )
        case_id = (
            existing["_id"]
            if existing
            else _stable_id("pc", contract["_id"], POLICY_VERSION)
        )
        document = {
            "_id": case_id,
            "contract_id": contract["_id"],
            "status": status,
            "triggers": triggers,
            "priority_score": priority_score,
            "priority_components": priority_components,
            "owner_user_id": (existing or {}).get("owner_user_id") or contract.get("assignee_user_id"),
            "owner_center": (existing or {}).get("owner_center")
            or contract.get("assigned_center")
            or contract.get("owner_center"),
            "next_action": next_action,
            "due_at": incomplete_due[0] if incomplete_due else None,
            "policy_version": POLICY_VERSION,
            "created_at": existing["created_at"] if existing else now,
            "updated_at": now,
            "source": _workflow_source(contract, as_of, "사전예방 정책 평가"),
        }
        result = await self._cases.collection.update_one(
            {"_id": document["_id"]}, {"$set": document}, upsert=True
        )
        return document, result.upserted_id is not None

    async def _sync_bundle_action(
        self, case: dict[str, Any], bundle: dict[str, Any], contract: dict[str, Any], as_of: date
    ) -> tuple[dict[str, Any], bool]:
        dedupe_key = f"bundle-action:{bundle['_id']}"
        existing = await self._actions.find_by_dedupe_key(dedupe_key)
        if bundle["status"] == "Completed":
            status = "Completed"
        elif bundle["status"] == "Overdue":
            status = "Overdue"
        elif bundle["status"] == "InReview":
            status = "Verifying"
        else:
            status = "Requested"
        now = now_kst_iso()
        action_id = existing["_id"] if existing else _stable_id("pa", dedupe_key)
        document = {
            "_id": action_id,
            "prevention_case_id": case["_id"],
            "contract_id": contract["_id"],
            "action_type": "EVIDENCE_REQUEST",
            "status": status,
            "actor_role": "system",
            "actor_user_id": None,
            "target_role": "landlord",
            "requested_at": existing["requested_at"] if existing else now,
            "due_at": bundle["due_at"],
            "completed_at": now if status == "Completed" else None,
            "note": f"{bundle['checkpoint']} 필수 증빙 bundle",
            "details": {
                "evidence_bundle_id": bundle["_id"],
                "checkpoint": bundle["checkpoint"],
                "completion_ratio": bundle["completion_ratio"],
            },
            "audit_log": (existing or {}).get("audit_log", []),
            "dedupe_key": dedupe_key,
            "updated_at": now,
            "source": _workflow_source(contract, as_of, "D-day 증빙 조치 자동 생성"),
        }
        result = await self._actions.collection.update_one(
            {"_id": document["_id"]}, {"$set": document}, upsert=True
        )
        return document, result.upserted_id is not None

    async def _notify_case(
        self,
        contract: dict[str, Any],
        case: dict[str, Any],
        triggers: list[dict[str, Any]],
        as_of: date,
    ) -> int:
        hug_admins, _ = await self._users.list_paginated(0, 1000, role="hug_admin")
        recipients: list[tuple[str, str, str]] = []
        if contract.get("tenant_user_id"):
            recipients.append((contract["tenant_user_id"], "tenant", f"/contracts/{contract['_id']}/manage"))
        if contract.get("landlord_user_id"):
            recipients.append((contract["landlord_user_id"], "landlord", f"/contracts/{contract['_id']}/manage"))
        recipients.extend(
            (admin["_id"], "hug_admin", f"/hug/contracts/{contract['_id']}") for admin in hug_admins
        )
        created = 0
        for trigger in triggers:
            checkpoint = trigger.get("checkpoint")
            severity = trigger.get("severity", "medium")
            notification_severity = (
                "critical" if severity == "critical" else "warning" if severity == "high" else "info"
            )
            due_at = case.get("due_at")
            for user_id, target_role, link in recipients:
                if target_role == "landlord":
                    action_text = "요청된 증빙 또는 신용보강 조치를 제출해 주세요."
                elif target_role == "tenant":
                    action_text = "현재 위험신호와 권장 권리보전 조치를 확인해 주세요."
                else:
                    action_text = "담당자 배정과 다음 예방조치를 검토해 주세요."
                result = await self._notifications.notify(
                    user_id=user_id,
                    category="prevention_alert",
                    title=f"사전예방 알림 — {trigger['reason']}",
                    body=(
                        f"계약 {contract['_id']}에 {trigger['reason']} 신호가 발생했습니다. "
                        f"{action_text}" + (f" 기한: {due_at}." if due_at else "")
                    ),
                    severity=notification_severity,
                    link=link,
                    dedupe_key=(
                        f"prevention:{case['_id']}:{trigger['code']}:{checkpoint or '-'}:{POLICY_VERSION}"
                    ),
                    contract_id=contract["_id"],
                    prevention_case_id=case["_id"],
                    trigger_code=trigger["code"],
                    target_role=target_role,
                    due_at=due_at,
                    metadata={"checkpoint": checkpoint, "policy_version": POLICY_VERSION},
                    source=_workflow_source(contract, as_of, "사전예방 위험신호 알림"),
                )
                if result:
                    created += 1
        return created

    async def run_sweep(
        self,
        as_of_date: date | None = None,
        contract_ids: list[str] | None = None,
        data_mode: str = "LIVE",
    ) -> dict[str, Any]:
        as_of = as_of_date or date.today()
        if data_mode not in {"LIVE", "DEMO"}:
            raise ValueError("data_mode must be LIVE or DEMO")
        mode_query = (
            {
                "$or": [
                    {"_id": {"$regex": "^demo-"}},
                    {"is_demo": True},
                    {"source.data_mode": "DEMO"},
                ]
            }
            if data_mode == "DEMO"
            else {
                "_id": {"$not": {"$regex": "^demo-"}},
                "is_demo": {"$ne": True},
                "source.data_mode": {"$ne": "DEMO"},
            }
        )
        # contract_ids를 최상위 "_id" 키로 병합하면 LIVE mode_query의 "^demo-"
        # 제외 조건("_id": {"$not": ...})을 덮어쓴다. $and로 결합해 명시 ID를
        # 지정해도 모집단 분리 조건이 항상 함께 적용되게 한다.
        filters: list[dict[str, Any]] = [
            {"contract_status": {"$in": list(PRE_INCIDENT_STATUSES)}},
            mode_query,
        ]
        if contract_ids is not None:
            filters.append({"_id": {"$in": contract_ids}})
        query: dict[str, Any] = {"$and": filters}
        contracts = [document async for document in self._contracts.collection.find(query)]
        population = [
            document
            async for document in self._contracts.collection.find(
                {
                    "contract_status": {"$in": list(PRE_INCIDENT_STATUSES)},
                    **mode_query,
                }
            )
        ]
        deposits = np.sort(
            np.asarray([max(float(contract.get("deposit") or 0), 0) for contract in population])
        )
        summary: dict[str, Any] = {
            "as_of_date": as_of.isoformat(),
            "checked": len(contracts),
            "predictions_refreshed": 0,
            "bundles_created": 0,
            "requests_created": 0,
            "cases_created": 0,
            "actions_created": 0,
            "notifications_sent": 0,
            "flagged": [],
            "data_mode_filter": data_mode,
        }
        for contract in contracts:
            try:
                end_date = date.fromisoformat(contract["contract_end_date"])
            except (KeyError, TypeError, ValueError):
                continue
            d_day = (end_date - as_of).days
            try:
                prediction_response = await self._accident.refresh_contract(contract["_id"])
            except ModelInferenceFailedError as exc:
                prediction_response = await self._accident.record_failure(contract["_id"], exc)
            summary["predictions_refreshed"] += 1
            prediction = await self._predictions.latest_for_contract(contract["_id"])

            bundles: list[dict[str, Any]] = []
            for checkpoint in checkpoints_due(d_day):
                bundle, created, requests_created = await self._ensure_bundle(
                    contract, checkpoint, as_of
                )
                bundles.append(bundle)
                summary["bundles_created"] += int(created)
                summary["requests_created"] += requests_created

            triggers, unresolved = await self._derive_triggers(
                contract, prediction, bundles, d_day
            )
            deposit = max(float(contract.get("deposit") or 0), 0)
            deposit_percentile = float(
                np.searchsorted(deposits, deposit, side="right") / max(len(deposits), 1)
            )
            priority, components = calculate_priority_components(
                risk_percentile=prediction_response.risk_percentile,
                deposit_percentile=deposit_percentile,
                d_day=d_day,
                unresolved_severity=unresolved,
            )
            case, case_created = await self._ensure_case(
                contract, triggers, priority, components, bundles, as_of
            )
            summary["cases_created"] += int(case_created)
            if case:
                for bundle in bundles:
                    _, action_created = await self._sync_bundle_action(
                        case, bundle, contract, as_of
                    )
                    summary["actions_created"] += int(action_created)
            if case and triggers:
                notification_count = await self._notify_case(contract, case, triggers, as_of)
                summary["notifications_sent"] += notification_count
                if case["status"] == "RiskDetected" and notification_count:
                    case = await self._cases.update_fields(
                        case["_id"], {"status": "Notified", "updated_at": now_kst_iso()}
                    )
                summary["flagged"].append(
                    {
                        "contract_id": contract["_id"],
                        "stage": dday_stage(d_day),
                        "d_day": d_day,
                        "prevention_case_id": case["_id"],
                        "status": case["status"],
                        "priority_score": priority,
                        "trigger_codes": [trigger["code"] for trigger in triggers],
                    }
                )
        return summary

    async def get_contract_prevention(self, contract_id: str) -> dict[str, Any]:
        if not await self._contracts.exists(contract_id):
            raise ResourceNotFoundError("계약 정보를 찾을 수 없습니다.")
        case = await self._cases.latest_for_contract(contract_id)
        bundles = await self._bundles.list_for_contract(contract_id)
        actions = await self._actions.list_for_contract(contract_id)
        prediction = await self._predictions.latest_for_contract(contract_id)
        return {
            "contract_id": contract_id,
            "prediction_id": prediction["_id"] if prediction else None,
            "case": _case_response(case) if case else None,
            "evidence_bundles": [_bundle_response(bundle) for bundle in bundles],
            "actions": [_action_response(action) for action in actions],
        }

    async def create_action(
        self,
        contract_id: str,
        payload: PreventiveActionCreateRequest,
        actor_user_id: str,
        actor_role: str,
    ) -> PreventiveActionResponse:
        contract = await self._contracts.get_by_id(contract_id)
        if not contract:
            raise ResourceNotFoundError("계약 정보를 찾을 수 없습니다.")
        if contract.get("contract_status") not in PRE_INCIDENT_STATUSES:
            raise StateConflictError("사고접수 전 계약에만 예방조치를 생성할 수 있습니다.")
        case = await self._cases.find_open_for_contract(contract_id)
        now = now_kst_iso()
        if not case:
            case = await self._cases.collection.find_one(
                {"contract_id": contract_id, "policy_version": POLICY_VERSION}
            )
            case_id = case["_id"] if case else _stable_id("pc", contract_id, POLICY_VERSION)
            case = {
                "_id": case_id,
                "contract_id": contract_id,
                "status": "ActionRequested",
                "triggers": [
                    {"code": "MANUAL_ACTION", "severity": "medium", "reason": payload.action_type}
                ],
                "priority_score": 0.0,
                "priority_components": {},
                "owner_user_id": actor_user_id,
                "owner_center": contract.get("assigned_center") or contract.get("owner_center"),
                "next_action": payload.action_type,
                "due_at": payload.due_at,
                "policy_version": POLICY_VERSION,
                "created_at": case.get("created_at", now) if case else now,
                "updated_at": now,
                "source": _workflow_source(contract, date.today(), "HUG 수동 예방조치"),
            }
            await self._cases.collection.update_one(
                {"_id": case_id}, {"$set": case}, upsert=True
            )
        action = {
            "_id": new_uuid(),
            "prevention_case_id": case["_id"],
            "contract_id": contract_id,
            "action_type": payload.action_type,
            "status": "Requested",
            "actor_role": actor_role,
            "actor_user_id": actor_user_id,
            "target_role": payload.target_role,
            "requested_at": now,
            "due_at": payload.due_at,
            "completed_at": None,
            "note": payload.note,
            "details": payload.details,
            "audit_log": [
                {"from": None, "to": "Requested", "actor_user_id": actor_user_id, "at": now}
            ],
            "updated_at": now,
            "source": _workflow_source(contract, date.today(), "HUG 수동 예방조치"),
        }
        await self._actions.insert(action)
        await self._cases.update_fields(
            case["_id"],
            {
                "status": "ActionRequested",
                "next_action": payload.action_type,
                "due_at": payload.due_at,
                "updated_at": now,
            },
        )
        return _action_response(action)

    async def update_action(
        self,
        action_id: str,
        payload: PreventiveActionUpdateRequest,
        actor_user_id: str,
        actor_role: str,
    ) -> PreventiveActionResponse:
        action = await self._actions.get_by_id(action_id)
        if not action:
            raise ResourceNotFoundError("예방조치를 찾을 수 없습니다.")
        contract = await self._contracts.get_by_id(action["contract_id"])
        if not contract:
            raise ResourceNotFoundError("연결 계약을 찾을 수 없습니다.")
        if contract.get("contract_status") not in PRE_INCIDENT_STATUSES:
            raise StateConflictError("사고접수 전 계약의 예방조치만 변경할 수 있습니다.")
        # §20.5 P3 — 임대인은 자기 계약에 요청된 조치의 착수·완료 제출만 등록할 수 있다.
        if actor_role == "landlord":
            if (
                action.get("target_role") != "landlord"
                or contract.get("landlord_user_id") != actor_user_id
            ):
                raise PermissionDeniedError("본인 계약에 요청된 조치만 등록할 수 있습니다.")
            if payload.status not in {"InProgress", "Submitted"}:
                raise PermissionDeniedError(
                    "임대인은 이행 착수·완료 제출까지만 등록할 수 있으며 검증·종결은 HUG가 처리합니다."
                )
        elif actor_role not in {"hug_admin", "system_admin"}:
            raise PermissionDeniedError("예방조치 변경 권한이 없습니다.")
        current = action["status"]
        if payload.status not in _ACTION_TRANSITIONS.get(current, set()):
            raise ValidationAppError(
                f"예방조치 상태 전이 {current} → {payload.status} 는 허용되지 않습니다."
            )
        now = now_kst_iso()
        audit = list(action.get("audit_log", []))
        audit.append(
            {
                "from": current,
                "to": payload.status,
                "actor_user_id": actor_user_id,
                "actor_role": actor_role,
                "note": payload.note,
                "at": now,
            }
        )
        details = {**action.get("details", {}), **payload.details}
        updated = await self._actions.cas_transition(
            action_id,
            expected_status=current,
            expected_updated_at=action["updated_at"],
            fields={
                "status": payload.status,
                "note": payload.note if payload.note is not None else action.get("note"),
                "details": details,
                "audit_log": audit,
                "completed_at": now if payload.status == "Completed" else None,
                "updated_at": now,
            },
        )
        if not updated:
            raise StateConflictError(
                "다른 요청이 예방조치를 먼저 변경했습니다. 최신 상태를 확인하세요."
            )
        case_status = {
            "Submitted": "EvidenceSubmitted",
            "Verifying": "Verifying",
            "Overdue": "EscalatedMonitoring",
            "Completed": "Monitoring",
        }.get(payload.status, "ActionRequested")
        await self._cases.update_fields(
            action["prevention_case_id"],
            {"status": case_status, "updated_at": now},
        )
        return _action_response(updated)

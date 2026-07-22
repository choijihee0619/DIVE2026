"""D-90/60/30 상환능력 사전 확보 스윕 (README §19.2).

관리 국면(계약 후) 계약의 만기 D-day를 점검해
① 만기 90일 이내인데 상환능력 증빙 요청이 없으면 기본 요청(소득·재직)을 자동 생성하고
② 상환능력 증빙이 미제출이면 임차인·임대인·HUG 관리자에게 단계별(D-90/60/30) 알림을 보낸다.

실서비스라면 스케줄러(cron)가 매일 실행할 작업을, 데모에서는 HUG 대시보드 버튼으로
트리거한다. 알림은 기존 notifications 컬렉션을 재사용하고 dedupe_key로 재실행에 안전하다.
"""

from __future__ import annotations

from datetime import date, timedelta

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.enums import (
    REPAYMENT_CAPABILITY_EVIDENCE_TYPES,
    ContractStatus,
    EvidenceType,
    VerificationStatus,
)
from app.repositories.contract_repository import ContractRepository
from app.repositories.evidence_repository import EvidenceRequestRepository
from app.repositories.user_repository import UserRepository
from app.schemas.evidence import EvidenceRequestCreateRequest
from app.services.evidence_service import EvidenceService
from app.services.notification_service import NotificationService

# 사전 확보 점검 대상 상태 — 사고 접수 이후(이관·회수·종결)는 D-노티 의미가 없어 제외한다.
WATCH_STATUSES: tuple[str, ...] = (
    ContractStatus.CONTRACT_FINALIZED.value,
    ContractStatus.MONITORING.value,
    ContractStatus.D90_REQUESTED.value,
    ContractStatus.RETURN_PLAN_SUBMITTED.value,
    ContractStatus.AT_RISK.value,
)

# 제출된 것으로 보는 요청 상태(제출~검증). Pending/Rejected/Expired는 미제출로 본다.
_SUBMITTED_STATUSES = {
    VerificationStatus.SUBMITTED.value,
    VerificationStatus.REVIEWING.value,
    VerificationStatus.VERIFIED.value,
}

_STAGE_SEVERITY = {"D-90": "info", "D-60": "warning", "D-30": "danger"}


def _stage_for(d_day: int) -> str | None:
    if d_day < 0 or d_day > 90:
        return None
    if d_day <= 30:
        return "D-30"
    if d_day <= 60:
        return "D-60"
    return "D-90"


class RepaymentWatchService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._contracts = ContractRepository(db)
        self._requests = EvidenceRequestRepository(db)
        self._users = UserRepository(db)
        self._evidence = EvidenceService(db)
        self._notifications = NotificationService(db)

    async def run_sweep(self) -> dict:
        """관리 국면 계약 전체를 점검한다. 재실행해도 요청·알림이 중복 생성되지 않는다."""
        today = date.today()
        checked = 0
        requests_created = 0
        notifications_sent = 0
        flagged: list[dict] = []

        hug_admins, _ = await self._users.list_paginated(0, 50, role="hug_admin")

        cursor = self._contracts.collection.find({"contract_status": {"$in": list(WATCH_STATUSES)}})
        async for contract in cursor:
            checked += 1
            try:
                end_date = date.fromisoformat(contract["contract_end_date"])
            except (KeyError, ValueError):
                continue
            d_day = (end_date - today).days
            stage = _stage_for(d_day)
            if stage is None:
                continue

            contract_id = contract["_id"]
            repayment_requests = await self._requests.collection.find(
                {
                    "contract_id": contract_id,
                    "evidence_type": {"$in": list(REPAYMENT_CAPABILITY_EVIDENCE_TYPES)},
                }
            ).to_list(length=50)

            # ① D-90 사전 확보: 상환능력 요청이 하나도 없으면 기본 요청(소득·재직)을 자동 생성
            if not repayment_requests:
                due = max(end_date - timedelta(days=30), today)
                await self._evidence.create_request(
                    EvidenceRequestCreateRequest(
                        contract_id=contract_id,
                        reason=f"계약 만기 {stage}({contract['contract_end_date']}) 도래 — 기본 상환능력 증빙 사전 제출 요청 (자동 점검)",
                        evidence_type=EvidenceType.INCOME_EMPLOYMENT_PROOF,
                        due_date=due,
                    )
                )
                requests_created += 1
                submitted = False
            else:
                submitted = any(
                    r.get("verification_status") in _SUBMITTED_STATUSES for r in repayment_requests
                )

            if submitted:
                continue

            # ② 미제출 단계별 노티 — 임차인·임대인·HUG 관리자 전원, dedupe_key로 중복 방지
            severity = _STAGE_SEVERITY[stage]
            link = f"/contracts/{contract_id}/manage"
            targets: list[tuple[str, str, str]] = []  # (user_id, title, body)
            short_id = contract_id if len(contract_id) <= 14 else f"{contract_id[:12]}…"
            if contract.get("tenant_user_id"):
                targets.append(
                    (
                        contract["tenant_user_id"],
                        f"보증금 반환 {stage} — 임대인 상환능력 증빙 미제출",
                        f"계약 {short_id} 만기가 {stage}입니다. 임대인의 상환능력 증빙이 아직 제출되지 않았습니다. 계약 후 관리 화면에서 확인하세요.",
                    )
                )
            if contract.get("landlord_user_id"):
                targets.append(
                    (
                        contract["landlord_user_id"],
                        f"보증금 반환 {stage} — 상환능력 증빙 제출 요청",
                        f"계약 {short_id} 만기가 {stage}입니다. 소득·재직 등 상환능력 증빙을 기한 내 제출해 주세요.",
                    )
                )
            for admin in hug_admins:
                targets.append(
                    (
                        admin["_id"],
                        f"[사전확보] {stage} 미제출 — 계약 {short_id}",
                        f"만기 {stage} 계약의 임대인 상환능력 증빙이 미제출 상태입니다. 사전 확보 조치를 검토하세요.",
                    )
                )

            contract_flagged = False
            for user_id, title, body in targets:
                created = await self._notifications.notify(
                    user_id=user_id,
                    # NotificationResponse.category Literal 준수 — 만기 D-노티는 deadline 버킷.
                    category="deadline",
                    title=title,
                    body=body,
                    severity=severity,
                    link=link,
                    dedupe_key=f"repayment_dday:{contract_id}:{stage}",
                )
                if created:
                    notifications_sent += 1
                    contract_flagged = True
            if contract_flagged or not repayment_requests:
                flagged.append({"contract_id": contract_id, "stage": stage, "d_day": d_day})

        return {
            "checked": checked,
            "requests_created": requests_created,
            "notifications_sent": notifications_sent,
            "flagged": flagged,
        }

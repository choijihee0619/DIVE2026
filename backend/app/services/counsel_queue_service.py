"""상담사 큐 서비스.

챗봇이 근거를 찾지 못했거나 임차인이 이관을 요청한 상담이 큐로 유입된다.
접수 시 ML 분류기(dispute_clf/stage_clf)로 분쟁유형·진행단계를 자동 태깅하고,
분쟁유형·단계 기반 규칙으로 우선순위(high/normal)를 매긴다. 모델이 없으면
태깅 없이 접수만 한다(큐 자체는 항상 동작).
"""

from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorDatabase
from starlette.concurrency import run_in_threadpool

from app.core.exceptions import PermissionDeniedError, ResourceNotFoundError, ValidationAppError
from app.repositories.counsel_queue_repository import CounselQueueRepository
from app.schemas.common import build_pagination
from app.schemas.counsel import (
    CounselClassification,
    CounselQueueCreateRequest,
    CounselQueueItemResponse,
    CounselQueueUpdateRequest,
)
from app.services import ml_service
from app.services.notification_service import NotificationService
from app.utils.datetime_utils import new_uuid, now_kst_iso

_HIGH_DISPUTES = {"보증금미반환", "경매·공매", "전세사기"}
_HIGH_STAGES = {"내용증명·공시송달", "소송제기", "판결·집행", "HUG이행청구"}

_TRANSITIONS: dict[str, set[str]] = {
    "Waiting": {"InProgress", "Closed"},
    "InProgress": {"Answered", "Closed"},
    "Answered": {"Closed"},
    "Closed": set(),
}


class CounselQueueService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._repo = CounselQueueRepository(db)
        self._notifications = NotificationService(db)

    async def create(self, user_id: str, payload: CounselQueueCreateRequest) -> CounselQueueItemResponse:
        classification = CounselClassification()
        try:
            result = await run_in_threadpool(ml_service.classify_counsel, payload.text)
            classification = CounselClassification(
                dispute_type=result["dispute_type"]["label"],
                dispute_confidence=result["dispute_type"]["confidence"],
                consultation_stage=result["consultation_stage"]["label"],
                stage_confidence=result["consultation_stage"]["confidence"],
                classified=True,
            )
        except Exception:  # noqa: BLE001 - 분류 실패해도 접수는 진행
            pass

        priority = "normal"
        if (classification.dispute_type in _HIGH_DISPUTES
                or classification.consultation_stage in _HIGH_STAGES):
            priority = "high"

        now = now_kst_iso()
        doc = {
            "_id": new_uuid(),
            "requester_user_id": user_id,
            "text": payload.text,
            "source": payload.source,
            "contract_id": payload.contract_id,
            "region_sido": payload.region_sido,
            "classification": classification.model_dump(),
            "priority": priority,
            "priority_rank": 0 if priority == "high" else 1,
            "status": "Waiting",
            "assignee_user_id": None,
            "answer_note": None,
            "created_at": now,
            "updated_at": now,
        }
        await self._repo.insert(doc)
        return _to_response(doc)

    async def list(
        self,
        role: str,
        user_id: str,
        page: int,
        size: int,
        status: str | None,
        priority: str | None,
    ) -> dict:
        requester_filter = None
        if role not in ("advisor", "hug_admin", "system_admin"):
            requester_filter = user_id  # 임차인은 본인 요청만
        items, total = await self._repo.list_paginated_filtered(
            (page - 1) * size, size,
            status=status, priority=priority, requester_user_id=requester_filter,
        )
        return {
            "items": [_to_response(d) for d in items],
            "pagination": build_pagination(page, size, total).model_dump(),
        }

    async def get(self, counsel_id: str, role: str, user_id: str) -> CounselQueueItemResponse:
        doc = await self._repo.get_by_id(counsel_id)
        if not doc:
            raise ResourceNotFoundError("상담 요청을 찾을 수 없습니다.")
        if role not in ("advisor", "hug_admin", "system_admin") and doc["requester_user_id"] != user_id:
            raise PermissionDeniedError("본인 상담 요청만 조회할 수 있습니다.")
        return _to_response(doc)

    async def update(
        self, counsel_id: str, payload: CounselQueueUpdateRequest, assignee_user_id: str
    ) -> CounselQueueItemResponse:
        doc = await self._repo.get_by_id(counsel_id)
        if not doc:
            raise ResourceNotFoundError("상담 요청을 찾을 수 없습니다.")
        allowed = _TRANSITIONS.get(doc["status"], set())
        if payload.status not in allowed:
            raise ValidationAppError(
                f"상태 전이 {doc['status']} → {payload.status} 는 허용되지 않습니다. 가능: {sorted(allowed)}"
            )
        fields = {
            "status": payload.status,
            "assignee_user_id": assignee_user_id,
            "updated_at": now_kst_iso(),
        }
        if payload.answer_note is not None:
            fields["answer_note"] = payload.answer_note
        updated = await self._repo.update_fields(counsel_id, fields)

        if payload.status == "Answered":
            await self._notifications.notify(
                user_id=doc["requester_user_id"],
                category="counsel_update",
                title="상담 답변이 등록되었습니다",
                body=(payload.answer_note or "상담사 답변을 확인하세요.")[:200],
                severity="info",
                link=f"/tenant/counsel/{counsel_id}",
            )
        return _to_response(updated)


def _to_response(doc: dict) -> CounselQueueItemResponse:
    return CounselQueueItemResponse(
        counsel_id=doc["_id"],
        requester_user_id=doc["requester_user_id"],
        text=doc["text"],
        source=doc["source"],
        contract_id=doc.get("contract_id"),
        region_sido=doc.get("region_sido"),
        classification=CounselClassification(**doc.get("classification", {})),
        priority=doc["priority"],
        status=doc["status"],
        assignee_user_id=doc.get("assignee_user_id"),
        answer_note=doc.get("answer_note"),
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )

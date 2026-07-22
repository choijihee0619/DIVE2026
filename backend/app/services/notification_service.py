"""알림함 서비스.

실제 외부 모니터링(등기 변동 감지 등)은 이 MVP 범위 밖이므로, 알림은
① 도메인 이벤트(사고 접수·상담 처리 등)에서 생성되거나
② MOCK_MODE에서 demo-seed로 생성된다(등기 변동·확정일자·보증만기 샘플).
"""

from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import get_settings
from app.core.exceptions import ResourceNotFoundError, ValidationAppError
from app.repositories.notification_repository import NotificationRepository
from app.schemas.common import build_pagination
from app.schemas.notification import NotificationResponse
from app.utils.datetime_utils import new_uuid, now_kst_iso

DEMO_NOTIFICATIONS = [
    {
        "category": "registry_change",
        "title": "등기 변동 감지 — 근저당 설정",
        "body": "거주지 건물 등기부에 근저당권 설정이 감지되었습니다. 상세 내역을 확인하세요. (모의 알림)",
        "severity": "warning",
        "link": "/tenant/report",
    },
    {
        "category": "contract_event",
        "title": "확정일자 처리 완료",
        "body": "임대차계약 확정일자 부여가 완료되었습니다. (모의 알림)",
        "severity": "info",
        "link": "/tenant/contract",
    },
    {
        "category": "deadline",
        "title": "보증 만기 D-214",
        "body": "전세보증금반환보증 만기가 다가옵니다. 갱신 조건을 미리 확인하세요. (모의 알림)",
        "severity": "info",
        "link": "/tenant",
    },
]


class NotificationService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._repo = NotificationRepository(db)

    async def notify(
        self,
        user_id: str,
        category: str,
        title: str,
        body: str,
        severity: str = "info",
        link: str | None = None,
        dedupe_key: str | None = None,
    ) -> dict | None:
        # dedupe_key가 있으면 동일 키 알림을 다시 만들지 않는다(D-90/60/30 스윕 재실행 대비, 19.2).
        if dedupe_key:
            existing = await self._repo.collection.find_one({"user_id": user_id, "dedupe_key": dedupe_key})
            if existing:
                return None
        doc = {
            "_id": new_uuid(),
            "user_id": user_id,
            "category": category,
            "title": title,
            "body": body,
            "severity": severity,
            "link": link,
            "is_read": False,
            "created_at": now_kst_iso(),
        }
        if dedupe_key:
            doc["dedupe_key"] = dedupe_key
        await self._repo.insert(doc)
        return doc

    async def list(self, user_id: str, page: int, size: int, unread_only: bool) -> dict:
        items, total = await self._repo.list_for_user(user_id, (page - 1) * size, size, unread_only)
        unread = await self._repo.unread_count(user_id)
        return {
            "items": [_to_response(d) for d in items],
            "unread_count": unread,
            "pagination": build_pagination(page, size, total).model_dump(),
        }

    async def mark_read(self, user_id: str, notification_id: str) -> dict:
        ok = await self._repo.mark_read(user_id, notification_id)
        if not ok:
            raise ResourceNotFoundError("알림을 찾을 수 없습니다.")
        return {"notification_id": notification_id, "is_read": True}

    async def mark_all_read(self, user_id: str) -> dict:
        modified = await self._repo.mark_all_read(user_id)
        return {"marked_read": modified}

    async def demo_seed(self, user_id: str) -> dict:
        if not get_settings().mock_mode:
            raise ValidationAppError("demo-seed는 MOCK_MODE에서만 사용할 수 있습니다.")
        created = []
        for sample in DEMO_NOTIFICATIONS:
            created.append(await self.notify(user_id=user_id, **sample))
        return {"created": len(created), "items": [_to_response(d) for d in created]}


def _to_response(doc: dict) -> NotificationResponse:
    return NotificationResponse(
        notification_id=doc["_id"],
        category=doc["category"],
        title=doc["title"],
        body=doc["body"],
        link=doc.get("link"),
        severity=doc.get("severity", "info"),
        is_read=doc.get("is_read", False),
        created_at=doc["created_at"],
    )

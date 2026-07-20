from __future__ import annotations

from typing import Any

from app.repositories.base_repository import BaseRepository


class CounselQueueRepository(BaseRepository):
    collection_name = "counsel_queue"

    async def list_paginated_filtered(
        self,
        skip: int,
        limit: int,
        status: str | None = None,
        priority: str | None = None,
        requester_user_id: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        query: dict[str, Any] = {}
        if status:
            query["status"] = status
        if priority:
            query["priority"] = priority
        if requester_user_id:
            query["requester_user_id"] = requester_user_id
        # 우선순위(high 먼저) → 접수 오래된 순
        return await super().list_paginated(
            query, skip, limit, sort=[("priority_rank", 1), ("created_at", 1)]
        )

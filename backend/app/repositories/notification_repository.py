from __future__ import annotations

from typing import Any

from app.repositories.base_repository import BaseRepository


class NotificationRepository(BaseRepository):
    collection_name = "notifications"

    async def list_for_user(
        self, user_id: str, skip: int, limit: int, unread_only: bool = False
    ) -> tuple[list[dict[str, Any]], int]:
        query: dict[str, Any] = {"user_id": user_id}
        if unread_only:
            query["is_read"] = False
        return await super().list_paginated(query, skip, limit, sort=[("created_at", -1)])

    async def mark_read(self, user_id: str, notification_id: str, read_at: str) -> bool:
        result = await self.collection.update_one(
            {"_id": notification_id, "user_id": user_id},
            {"$set": {"is_read": True, "read_at": read_at}},
        )
        return result.matched_count > 0

    async def mark_all_read(self, user_id: str, read_at: str) -> int:
        result = await self.collection.update_many(
            {"user_id": user_id, "is_read": False},
            {"$set": {"is_read": True, "read_at": read_at}},
        )
        return result.modified_count

    async def acknowledge(self, user_id: str, notification_id: str, acknowledged_at: str) -> bool:
        result = await self.collection.update_one(
            {"_id": notification_id, "user_id": user_id},
            {"$set": {"acknowledged_at": acknowledged_at, "is_read": True, "read_at": acknowledged_at}},
        )
        return result.matched_count > 0

    async def unread_count(self, user_id: str) -> int:
        return await self.collection.count_documents({"user_id": user_id, "is_read": False})

from __future__ import annotations

from typing import Any

from app.repositories.base_repository import BaseRepository


class UserRepository(BaseRepository):
    collection_name = "users"

    async def get_by_email(self, email: str) -> dict[str, Any] | None:
        return await self.collection.find_one({"email": email})

    async def list_paginated(
        self, skip: int, limit: int, role: str | None = None, search: str | None = None
    ) -> tuple[list[dict[str, Any]], int]:
        query: dict[str, Any] = {}
        if role:
            query["role"] = role
        if search:
            query["$or"] = [
                {"display_name": {"$regex": search, "$options": "i"}},
                {"email": {"$regex": search, "$options": "i"}},
            ]
        return await super().list_paginated(query, skip, limit, sort=[("created_at", -1)])

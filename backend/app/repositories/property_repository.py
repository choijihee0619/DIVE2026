from __future__ import annotations

from typing import Any

from app.repositories.base_repository import BaseRepository


class PropertyRepository(BaseRepository):
    collection_name = "properties"

    async def find_by_road_address(self, road_address: str) -> dict[str, Any] | None:
        return await self.collection.find_one({"address.road_address": road_address})

    async def list_paginated(self, skip: int, limit: int) -> tuple[list[dict[str, Any]], int]:
        return await super().list_paginated({}, skip, limit, sort=[("created_at", -1)])

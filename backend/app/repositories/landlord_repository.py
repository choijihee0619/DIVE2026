from __future__ import annotations

from typing import Any

from app.repositories.base_repository import BaseRepository


class LandlordRepository(BaseRepository):
    collection_name = "landlords"

    async def list_paginated(
        self, skip: int, limit: int, landlord_type: str | None = None
    ) -> tuple[list[dict[str, Any]], int]:
        query: dict[str, Any] = {}
        if landlord_type:
            query["landlord_type"] = landlord_type
        return await super().list_paginated(query, skip, limit, sort=[("created_at", -1)])

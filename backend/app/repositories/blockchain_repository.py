from __future__ import annotations

from typing import Any

from app.repositories.base_repository import BaseRepository


class BlockchainTransactionRepository(BaseRepository):
    collection_name = "blockchain_transactions"

    async def find_by_event(self, event_type: str, reference_id: str) -> dict[str, Any] | None:
        return await self.collection.find_one({"event_type": event_type, "reference_id": reference_id})

    async def list_paginated(
        self,
        skip: int,
        limit: int,
        blockchain_status: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        query: dict[str, Any] = {}
        if blockchain_status:
            query["blockchain_status"] = blockchain_status
        return await super().list_paginated(query, skip, limit, sort=[("created_at", -1)])

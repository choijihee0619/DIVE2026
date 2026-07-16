from __future__ import annotations

from typing import Any

from app.repositories.base_repository import BaseRepository


class ContractRepository(BaseRepository):
    collection_name = "contracts"

    async def list_for_user(
        self, user_id: str, skip: int, limit: int, contract_status: str | None = None
    ) -> tuple[list[dict[str, Any]], int]:
        query: dict[str, Any] = {"$or": [{"tenant_user_id": user_id}, {"landlord_user_id": user_id}]}
        if contract_status:
            query = {"$and": [query, {"contract_status": contract_status}]}
        return await self.list_paginated(query, skip, limit, sort=[("created_at", -1)])

    async def find_duplicate(self, tenant_user_id: str, property_id: str, contract_start_date: str) -> dict[str, Any] | None:
        return await self.collection.find_one(
            {
                "tenant_user_id": tenant_user_id,
                "property_id": property_id,
                "contract_start_date": contract_start_date,
            }
        )


class TimelineRepository(BaseRepository):
    collection_name = "timeline_events"

    async def list_for_contract(self, contract_id: str) -> list[dict[str, Any]]:
        cursor = self.collection.find({"contract_id": contract_id}).sort("occurred_at", 1)
        return [doc async for doc in cursor]

    async def append(self, event: dict[str, Any]) -> dict[str, Any]:
        return await self.insert(event)


class ReturnPlanRepository(BaseRepository):
    collection_name = "return_plans"

    async def find_by_contract(self, contract_id: str) -> dict[str, Any] | None:
        return await self.collection.find_one({"contract_id": contract_id})

    async def upsert(self, contract_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        await self.collection.update_one({"contract_id": contract_id}, {"$set": fields}, upsert=True)
        return await self.find_by_contract(contract_id)

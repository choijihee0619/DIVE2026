from __future__ import annotations

from typing import Any

from app.repositories.base_repository import BaseRepository


class RiskAssessmentRepository(BaseRepository):
    collection_name = "risk_assessments"

    async def find_by_case_id(self, case_id: str) -> dict[str, Any] | None:
        # 계약 문서에는 risk_assessment_id(_id)만 저장되므로 둘 다로 조회할 수 있게 한다.
        return await self.collection.find_one({"$or": [{"case_id": case_id}, {"_id": case_id}]})

    async def list_paginated(self, skip: int, limit: int, contract_id: str | None = None) -> tuple[list[dict[str, Any]], int]:
        query: dict[str, Any] = {}
        if contract_id:
            query["contract_id"] = contract_id
        return await super().list_paginated(query, skip, limit, sort=[("created_at", -1)])


class RegistrySnapshotRepository(BaseRepository):
    collection_name = "registry_snapshots"

    async def find_latest_by_property(self, property_id: str) -> dict[str, Any] | None:
        return await self.collection.find_one({"property_id": property_id}, sort=[("created_at", -1)])


class BuildingRegistrySnapshotRepository(BaseRepository):
    collection_name = "building_registry_snapshots"

    async def find_latest_by_property(self, property_id: str) -> dict[str, Any] | None:
        return await self.collection.find_one({"property_id": property_id}, sort=[("created_at", -1)])


class OfficialPriceSnapshotRepository(BaseRepository):
    collection_name = "official_price_snapshots"

    async def find_latest_by_property(self, property_id: str) -> dict[str, Any] | None:
        return await self.collection.find_one({"property_id": property_id}, sort=[("created_at", -1)])

from __future__ import annotations

from datetime import datetime, timezone
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


# MODIFIED 2026-07-21: created_at 타입 혼재(seed=BSON Date, 서비스=ISO 문자열) 시 MongoDB 타입
# 정렬 규칙상 Date가 항상 문자열보다 커서 seed mock이 최신 스냅샷으로 잘못 선택되던 버그 수정 —
# 파이썬에서 datetime으로 정규화해 최신 문서를 고른다(매물당 스냅샷 수가 적어 부담 없음).
def _created_at_key(doc: dict[str, Any]) -> datetime:
    value = doc.get("created_at")
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


async def _find_latest_by_property(collection, property_id: str) -> dict[str, Any] | None:
    docs = [doc async for doc in collection.find({"property_id": property_id})]
    return max(docs, key=_created_at_key) if docs else None


class RegistrySnapshotRepository(BaseRepository):
    collection_name = "registry_snapshots"

    async def find_latest_by_property(self, property_id: str) -> dict[str, Any] | None:
        return await _find_latest_by_property(self.collection, property_id)


class BuildingRegistrySnapshotRepository(BaseRepository):
    collection_name = "building_registry_snapshots"

    async def find_latest_by_property(self, property_id: str) -> dict[str, Any] | None:
        return await _find_latest_by_property(self.collection, property_id)


class OfficialPriceSnapshotRepository(BaseRepository):
    collection_name = "official_price_snapshots"

    async def find_latest_by_property(self, property_id: str) -> dict[str, Any] | None:
        return await _find_latest_by_property(self.collection, property_id)

"""사고 후 채권관리 MongoDB repository.

상태전이·원장 계산은 service가 담당하고 이 계층은 조회/원자적 갱신만 제공한다.
"""

from __future__ import annotations

from typing import Any

from pymongo import ReturnDocument

from app.repositories.base_repository import BaseRepository


class RecoveryClaimRepository(BaseRepository):
    collection_name = "recovery_claims"

    async def list_filtered(
        self,
        skip: int,
        limit: int,
        *,
        lifecycle: str | None = None,
        recovery_stage: str | None = None,
        claim_type: str | None = None,
        collection_route: str | None = None,
        data_mode: str = "LIVE",
        sort_by: str = "updated_at",
        descending: bool = True,
    ) -> tuple[list[dict[str, Any]], int]:
        query: dict[str, Any] = {}
        if lifecycle == "active":
            query["$and"] = [
                {"is_closed": {"$ne": True}},
                {"closed_at": None},
                {"$or": [{"closure": None}, {"closure": {"$exists": False}}]},
            ]
        elif lifecycle == "closed":
            query["$or"] = [
                {"is_closed": True},
                {"closed_at": {"$exists": True, "$ne": None}},
                {"closure": {"$exists": True, "$ne": None}},
            ]
        if recovery_stage:
            query["recovery_stage"] = recovery_stage
        if claim_type:
            query["claim_type"] = claim_type
        if collection_route:
            query["collection_route"] = collection_route
        demo_clause = {
            "$or": [
                {"is_demo": True},
                {"provenance.data_mode": "DEMO"},
                {"source.data_mode": "DEMO"},
                {"_id": {"$regex": "^demo-"}},
            ]
        }
        query.setdefault("$and", []).append(
            demo_clause if data_mode == "DEMO" else {"$nor": demo_clause["$or"]}
        )
        return await self.list_paginated(
            query,
            skip,
            limit,
            sort=[(sort_by, -1 if descending else 1), ("_id", 1)],
        )

    async def update_open_with_version(
        self,
        claim_id: str,
        expected_version: int,
        *,
        set_fields: dict[str, Any],
        inc_fields: dict[str, int] | None = None,
    ) -> dict[str, Any] | None:
        version_clause: dict[str, Any]
        if expected_version == 0:
            version_clause = {"$or": [{"version": 0}, {"version": {"$exists": False}}]}
        else:
            version_clause = {"version": expected_version}
        # ``is_closed``만 검사하면 과거 문서의 ``closed_at``/``closure`` 표기와
        # 경쟁하는 갱신이 종결 채권에 반영될 수 있다. 세 종결 표기를 모두 CAS
        # 조건에 포함해 조회 이후 종결된 문서도 갱신하지 않는다.
        query = {
            "$and": [
                {"_id": claim_id},
                {"is_closed": {"$ne": True}},
                {"$or": [{"closed_at": None}, {"closed_at": {"$exists": False}}]},
                {"$or": [{"closure": None}, {"closure": {"$exists": False}}]},
                version_clause,
            ]
        }
        update: dict[str, Any] = {"$set": set_fields, "$inc": {"version": 1}}
        if inc_fields:
            update["$inc"].update(inc_fields)
        return await self.collection.find_one_and_update(
            query,
            update,
            return_document=ReturnDocument.AFTER,
        )

    async def count_open_for_performance_claim(self, performance_claim_id: str) -> int:
        return await self.collection.count_documents(
            {
                "$and": [
                    {"performance_claim_id": performance_claim_id},
                    {"is_closed": {"$ne": True}},
                    {"$or": [{"closed_at": None}, {"closed_at": {"$exists": False}}]},
                    {"$or": [{"closure": None}, {"closure": {"$exists": False}}]},
                ]
            }
        )


class RecoveryEventRepository(BaseRepository):
    collection_name = "recovery_events"

    async def list_for_claim(self, claim_id: str, limit: int = 500) -> list[dict[str, Any]]:
        cursor = self.collection.find(
            {
                "$and": [
                    {"recovery_claim_id": claim_id},
                    {
                        "$or": [
                            {"operation_status": {"$exists": False}},
                            {"operation_status": "COMMITTED"},
                        ]
                    },
                ]
            }
        ).sort(
            [("occurred_at", 1), ("_id", 1)]
        ).limit(limit)
        return [doc async for doc in cursor]

    async def find_idempotent(self, claim_id: str, key: str | None) -> dict[str, Any] | None:
        if not key:
            return None
        return await self.collection.find_one(
            {"recovery_claim_id": claim_id, "idempotency_key": key}
        )

    async def mark_committed(self, event_id: str) -> bool:
        result = await self.collection.update_one(
            {"_id": event_id, "operation_status": "PENDING"},
            {"$set": {"operation_status": "COMMITTED"}},
        )
        return result.matched_count == 1

    async def discard_pending(self, event_id: str) -> None:
        await self.collection.delete_one({"_id": event_id, "operation_status": "PENDING"})


class RecoveryLedgerRepository(BaseRepository):
    collection_name = "recovery_ledger"

    async def list_for_claim(self, claim_id: str, limit: int = 1000) -> list[dict[str, Any]]:
        cursor = self.collection.find(
            {
                "$and": [
                    {"recovery_claim_id": claim_id},
                    {
                        "$or": [
                            {"operation_status": {"$exists": False}},
                            {"operation_status": "COMMITTED"},
                        ]
                    },
                ]
            }
        ).sort(
            [("occurred_at", 1), ("_id", 1)]
        ).limit(limit)
        return [doc async for doc in cursor]

    async def find_idempotent(self, claim_id: str, key: str | None) -> dict[str, Any] | None:
        if not key:
            return None
        return await self.collection.find_one(
            {"recovery_claim_id": claim_id, "idempotency_key": key}
        )

    async def latest_committed(self, claim_id: str) -> dict[str, Any] | None:
        return await self.collection.find_one(
            {
                "recovery_claim_id": claim_id,
                "$or": [
                    {"operation_status": {"$exists": False}},
                    {"operation_status": "COMMITTED"},
                ],
            },
            sort=[("occurred_at", -1), ("sequence", -1), ("_id", -1)],
        )

    async def mark_committed(self, entry_id: str, *, sequence: int | None = None) -> bool:
        # sequence는 PENDING 예약에 넣지 않고 claim version CAS로 직렬화된 값을
        # 확정 시점에만 기록한다. 예약 단계에서 부여하면 (claim_id, sequence)
        # unique 충돌이 다른 멱등키의 정상 요청까지 실패시킬 수 있다.
        fields: dict[str, Any] = {"operation_status": "COMMITTED"}
        if sequence is not None:
            fields["sequence"] = sequence
        result = await self.collection.update_one(
            {"_id": entry_id, "operation_status": "PENDING"},
            {"$set": fields},
        )
        return result.matched_count == 1

    async def discard_pending(self, entry_id: str) -> None:
        await self.collection.delete_one({"_id": entry_id, "operation_status": "PENDING"})


class RecoveryPredictionRepository(BaseRepository):
    collection_name = "recovery_predictions"

    async def list_for_claim(self, claim_id: str, limit: int = 200) -> list[dict[str, Any]]:
        cursor = self.collection.find({"recovery_claim_id": claim_id}).sort(
            [("predicted_at", -1), ("_id", -1)]
        ).limit(limit)
        return [doc async for doc in cursor]

    async def latest_for_claim(self, claim_id: str) -> dict[str, Any] | None:
        return await self.collection.find_one(
            {
                "recovery_claim_id": claim_id,
                "prediction_status": {"$nin": ["PENDING", "STALE"]},
            },
            sort=[("predicted_at", -1), ("_id", -1)],
        )

    async def find_idempotent(self, claim_id: str, key: str | None) -> dict[str, Any] | None:
        if not key:
            return None
        return await self.collection.find_one(
            {"recovery_claim_id": claim_id, "idempotency_key": key}
        )

    async def mark_status(
        self,
        prediction_id: str,
        *,
        expected_status: str,
        status: str,
        fields: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        set_fields = {"prediction_status": status, **(fields or {})}
        result = await self.collection.update_one(
            {"_id": prediction_id, "prediction_status": expected_status},
            {"$set": set_fields},
        )
        if result.matched_count == 0:
            return None
        return await self.get_by_id(prediction_id)

    async def discard_for_retry(self, prediction_id: str) -> None:
        await self.collection.delete_one(
            {"_id": prediction_id, "prediction_status": {"$in": ["PENDING", "STALE"]}}
        )


class _RecoveryCaseRepository(BaseRepository):
    async def list_for_claim(self, claim_id: str) -> list[dict[str, Any]]:
        cursor = self.collection.find({"recovery_claim_id": claim_id}).sort(
            [("created_at", 1), ("_id", 1)]
        )
        return [doc async for doc in cursor]

    async def find_by_case_number(
        self, claim_id: str, case_number: str
    ) -> dict[str, Any] | None:
        return await self.collection.find_one(
            {"recovery_claim_id": claim_id, "case_number": case_number}
        )

    async def cas_update(
        self,
        case_id: str,
        claim_id: str,
        expected_version: int,
        fields: dict[str, Any],
    ) -> dict[str, Any] | None:
        return await self.collection.find_one_and_update(
            {
                "_id": case_id,
                "recovery_claim_id": claim_id,
                "version": expected_version,
            },
            {"$set": fields, "$inc": {"version": 1}},
            return_document=ReturnDocument.AFTER,
        )

    async def rollback_update(
        self,
        case_id: str,
        claim_id: str,
        applied_version: int,
        fields: dict[str, Any],
        unset_fields: list[str] | None = None,
    ) -> bool:
        """상위 claim CAS 실패 시 하위 사건을 원래 값으로 되돌린다.

        version은 되감지 않고 한 번 더 증가시켜 ABA 재사용을 막는다.
        """

        update: dict[str, Any] = {"$set": fields, "$inc": {"version": 1}}
        if unset_fields:
            update["$unset"] = {field: "" for field in unset_fields}
        result = await self.collection.update_one(
            {
                "_id": case_id,
                "recovery_claim_id": claim_id,
                "version": applied_version,
            },
            update,
        )
        return result.matched_count == 1


class RecoveryLegalCaseRepository(_RecoveryCaseRepository):
    collection_name = "legal_cases"


class RecoveryAuctionCaseRepository(_RecoveryCaseRepository):
    collection_name = "auction_cases"

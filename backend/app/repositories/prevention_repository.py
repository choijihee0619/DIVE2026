"""사고 전 예측·예방 업무 컬렉션 Repository."""

from __future__ import annotations

from typing import Any

from pymongo import ReturnDocument

from app.repositories.base_repository import BaseRepository


class AccidentPredictionRepository(BaseRepository):
    collection_name = "accident_predictions"

    async def find_by_fingerprint(
        self, contract_id: str, feature_fingerprint: str
    ) -> dict[str, Any] | None:
        return await self.collection.find_one(
            {"contract_id": contract_id, "feature_fingerprint": feature_fingerprint}
        )

    async def latest_for_contract(self, contract_id: str) -> dict[str, Any] | None:
        return await self.collection.find_one(
            {"contract_id": contract_id}, sort=[("predicted_at", -1), ("_id", -1)]
        )

    async def list_for_contract(self, contract_id: str, limit: int = 50) -> list[dict[str, Any]]:
        cursor = (
            self.collection.find({"contract_id": contract_id})
            .sort([("predicted_at", -1), ("_id", -1)])
            .limit(limit)
        )
        return [document async for document in cursor]


class PreventionCaseRepository(BaseRepository):
    collection_name = "prevention_cases"

    _TERMINAL_STATUSES = ("Mitigated",)

    async def find_open_for_contract(self, contract_id: str) -> dict[str, Any] | None:
        return await self.collection.find_one(
            {
                "contract_id": contract_id,
                "status": {"$nin": list(self._TERMINAL_STATUSES)},
            },
            sort=[("updated_at", -1), ("_id", -1)],
        )

    async def latest_for_contract(self, contract_id: str) -> dict[str, Any] | None:
        return await self.collection.find_one(
            {"contract_id": contract_id}, sort=[("updated_at", -1), ("_id", -1)]
        )


class PreventiveActionRepository(BaseRepository):
    collection_name = "preventive_actions"

    async def find_by_dedupe_key(self, dedupe_key: str) -> dict[str, Any] | None:
        return await self.collection.find_one({"dedupe_key": dedupe_key})

    async def list_for_case(self, prevention_case_id: str) -> list[dict[str, Any]]:
        cursor = self.collection.find({"prevention_case_id": prevention_case_id}).sort(
            [("due_at", 1), ("requested_at", 1)]
        )
        return [document async for document in cursor]

    async def list_for_contract(self, contract_id: str) -> list[dict[str, Any]]:
        cursor = self.collection.find({"contract_id": contract_id}).sort(
            [("due_at", 1), ("requested_at", 1)]
        )
        return [document async for document in cursor]

    async def cas_transition(
        self,
        action_id: str,
        *,
        expected_status: str,
        expected_updated_at: str,
        fields: dict[str, Any],
    ) -> dict[str, Any] | None:
        return await self.collection.find_one_and_update(
            {
                "_id": action_id,
                "status": expected_status,
                "updated_at": expected_updated_at,
            },
            {"$set": fields},
            return_document=ReturnDocument.AFTER,
        )


class EvidenceBundleRepository(BaseRepository):
    collection_name = "evidence_bundles"

    async def find_checkpoint(
        self, contract_id: str, checkpoint: str, policy_version: str
    ) -> dict[str, Any] | None:
        return await self.collection.find_one(
            {
                "contract_id": contract_id,
                "checkpoint": checkpoint,
                "policy_version": policy_version,
            }
        )

    async def list_for_contract(self, contract_id: str) -> list[dict[str, Any]]:
        cursor = self.collection.find({"contract_id": contract_id}).sort(
            [("sequence", 1), ("created_at", 1)]
        )
        return [document async for document in cursor]

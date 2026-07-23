from __future__ import annotations

from typing import Any

from pymongo import ReturnDocument

from app.repositories.base_repository import BaseRepository


class EvidenceRequestRepository(BaseRepository):
    collection_name = "evidence_requests"

    async def find_bundle_item(self, bundle_id: str, item_key: str) -> dict[str, Any] | None:
        return await self.collection.find_one({"bundle_id": bundle_id, "item_key": item_key})

    async def list_paginated(
        self,
        skip: int,
        limit: int,
        case_id: str | None = None,
        contract_id: str | None = None,
        visible_contract_ids: list[str] | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        query: dict[str, Any] = {}
        if case_id:
            query["risk_assessment_id"] = case_id
        if contract_id:
            query["contract_id"] = contract_id
        elif visible_contract_ids is not None:
            query["contract_id"] = {"$in": visible_contract_ids}
        return await super().list_paginated(query, skip, limit, sort=[("created_at", -1)])


class EvidenceRepository(BaseRepository):
    collection_name = "evidences"

    async def find_duplicate(self, evidence_request_id: str, document_hash: str) -> dict[str, Any] | None:
        return await self.collection.find_one(
            {"evidence_request_id": evidence_request_id, "document_hash": document_hash}
        )

    async def list_for_request(self, evidence_request_id: str) -> list[dict[str, Any]]:
        cursor = self.collection.find({"evidence_request_id": evidence_request_id}).sort("submitted_at", -1)
        return [doc async for doc in cursor]

    async def acquire_decision_lock(
        self,
        evidence_id: str,
        *,
        expected_status: str,
        expected_version: int,
        lock: dict[str, Any],
    ) -> dict[str, Any] | None:
        """진행 중 증빙 하나에 대한 검증 결정권을 단일 CAS로 예약한다."""
        version_clause: dict[str, Any]
        if expected_version == 0:
            # version 도입 전 생성된 문서도 한 번만 안전하게 마이그레이션한다.
            version_clause = {
                "$or": [{"version": 0}, {"version": {"$exists": False}}]
            }
        else:
            version_clause = {"version": expected_version}
        return await self.collection.find_one_and_update(
            {
                "_id": evidence_id,
                "verification_status": expected_status,
                "$and": [
                    version_clause,
                    {
                        "$or": [
                            {"decision_lock": {"$exists": False}},
                            {"decision_lock": None},
                        ]
                    },
                ],
            },
            {"$set": {"decision_lock": lock}, "$inc": {"version": 1}},
            return_document=ReturnDocument.AFTER,
        )

    async def finalize_decision(
        self,
        evidence_id: str,
        *,
        lock_token: str,
        expected_version: int,
        fields: dict[str, Any],
    ) -> dict[str, Any] | None:
        """자신이 획득한 결정 잠금만 종결 상태로 확정한다."""
        return await self.collection.find_one_and_update(
            {
                "_id": evidence_id,
                "decision_lock.token": lock_token,
                "version": expected_version,
            },
            {
                "$set": fields,
                "$unset": {"decision_lock": ""},
                "$inc": {"version": 1},
            },
            return_document=ReturnDocument.AFTER,
        )

    async def release_decision_lock(
        self, evidence_id: str, *, lock_token: str, expected_version: int
    ) -> bool:
        """공증 등 확정 전 작업 실패 시 잠금을 해제하되 version은 증가시킨다."""
        result = await self.collection.update_one(
            {
                "_id": evidence_id,
                "decision_lock.token": lock_token,
                "version": expected_version,
            },
            {"$unset": {"decision_lock": ""}, "$inc": {"version": 1}},
        )
        return result.matched_count == 1


class VerificationRepository(BaseRepository):
    collection_name = "verifications"

    async def find_by_evidence(self, evidence_id: str) -> dict[str, Any] | None:
        return await self.collection.find_one({"evidence_id": evidence_id})

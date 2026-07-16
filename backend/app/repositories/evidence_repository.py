from __future__ import annotations

from typing import Any

from app.repositories.base_repository import BaseRepository


class EvidenceRequestRepository(BaseRepository):
    collection_name = "evidence_requests"

    async def list_paginated(
        self, skip: int, limit: int, case_id: str | None = None, contract_id: str | None = None
    ) -> tuple[list[dict[str, Any]], int]:
        query: dict[str, Any] = {}
        if case_id:
            query["risk_assessment_id"] = case_id
        if contract_id:
            query["contract_id"] = contract_id
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


class VerificationRepository(BaseRepository):
    collection_name = "verifications"

    async def find_by_evidence(self, evidence_id: str) -> dict[str, Any] | None:
        return await self.collection.find_one({"evidence_id": evidence_id})

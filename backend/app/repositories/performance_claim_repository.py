"""보증이행청구 원장 Repository.

상태 전이는 항상 `stage + version` 조건을 포함한 compare-and-set으로 수행한다.
동일 상태에서 발생하는 부분지급이나 문서 요청도 version을 증가시켜 동시 갱신의
lost update를 막는다.
"""

from __future__ import annotations

from typing import Any

from app.repositories.base_repository import BaseRepository


class PerformanceClaimRepository(BaseRepository):
    collection_name = "performance_claims"

    async def find_by_incident(self, incident_id: str) -> dict[str, Any] | None:
        return await self.collection.find_one({"incident_id": incident_id})

    async def cas_update(
        self,
        claim_id: str,
        *,
        expected_stages: set[str],
        expected_version: int,
        fields: dict[str, Any],
    ) -> dict[str, Any] | None:
        result = await self.collection.update_one(
            {
                "_id": claim_id,
                "stage": {"$in": sorted(expected_stages)},
                "version": expected_version,
            },
            {"$set": fields, "$inc": {"version": 1}},
        )
        if result.matched_count == 0:
            return None
        return await self.get_by_id(claim_id)

    async def list_paginated_filtered(
        self,
        skip: int,
        limit: int,
        *,
        stage: str | None = None,
        assignee_user_id: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        query: dict[str, Any] = {}
        if stage:
            query["stage"] = stage
        if assignee_user_id:
            query["assignee_user_id"] = assignee_user_id
        return await super().list_paginated(query, skip, limit, sort=[("updated_at", -1)])


class ClaimDocumentRepository(BaseRepository):
    collection_name = "claim_documents"

    async def list_for_claim(self, claim_id: str) -> list[dict[str, Any]]:
        cursor = self.collection.find({"performance_claim_id": claim_id}).sort("requested_at", 1)
        return [doc async for doc in cursor]

    async def find_by_type(self, claim_id: str, document_type: str) -> dict[str, Any] | None:
        return await self.collection.find_one(
            {"performance_claim_id": claim_id, "document_type": document_type}
        )

    async def find_duplicate_hash(self, claim_id: str, document_hash: str) -> dict[str, Any] | None:
        return await self.collection.find_one(
            {"performance_claim_id": claim_id, "submissions.document_hash": document_hash}
        )

    async def cas_update(
        self,
        document_id: str,
        *,
        expected_statuses: set[str],
        expected_version: int,
        fields: dict[str, Any],
        push_submission: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        update: dict[str, Any] = {"$set": fields, "$inc": {"version": 1}}
        if push_submission is not None:
            update["$push"] = {"submissions": push_submission}
        result = await self.collection.update_one(
            {
                "_id": document_id,
                "verification_status": {"$in": sorted(expected_statuses)},
                "version": expected_version,
            },
            update,
        )
        if result.matched_count == 0:
            return None
        return await self.get_by_id(document_id)


class ClaimDocumentSubmissionRepository(BaseRepository):
    """청구 단위 문서 hash를 원자 예약해 동시 중복 제출을 차단한다."""

    collection_name = "claim_document_submissions"

    async def find_by_hash(
        self, claim_id: str, document_hash: str
    ) -> dict[str, Any] | None:
        return await self.collection.find_one(
            {"performance_claim_id": claim_id, "document_hash": document_hash}
        )


class SubrogationPaymentRepository(BaseRepository):
    collection_name = "subrogation_payments"

    async def find_by_reference(self, payment_reference: str) -> dict[str, Any] | None:
        return await self.collection.find_one({"payment_reference": payment_reference})

    async def list_for_claim(self, claim_id: str) -> list[dict[str, Any]]:
        cursor = self.collection.find({"performance_claim_id": claim_id}).sort("created_at", 1)
        return [doc async for doc in cursor]


class RecoveryClaimRegistrationRepository(BaseRepository):
    collection_name = "recovery_claims"

    async def find_by_type(self, claim_id: str, claim_type: str) -> dict[str, Any] | None:
        return await self.collection.find_one(
            {"performance_claim_id": claim_id, "claim_type": claim_type}
        )

    async def list_for_performance_claim(self, claim_id: str) -> list[dict[str, Any]]:
        cursor = self.collection.find({"performance_claim_id": claim_id}).sort("created_at", 1)
        return [doc async for doc in cursor]


class RecoveryOpeningLedgerRepository(BaseRepository):
    collection_name = "recovery_ledger"


class PerformanceClaimEventRepository(BaseRepository):
    collection_name = "performance_claim_events"

    async def list_for_claim(self, claim_id: str) -> list[dict[str, Any]]:
        cursor = self.collection.find({"performance_claim_id": claim_id}).sort("occurred_at", 1)
        return [doc async for doc in cursor]

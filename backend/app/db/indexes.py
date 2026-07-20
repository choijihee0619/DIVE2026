"""앱 기동 시 필요한 인덱스를 idempotent하게 보장한다.

scripts/setup_mongodb.py가 이미 만든 인덱스와 충돌하지 않도록 동일한 컬렉션/키 조합을 재사용하고,
이번 MVP가 새로 추가하는 컬렉션(rag_search_logs)에 대해서만 신규 인덱스를 만든다.
"""

from __future__ import annotations

import logging

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import OperationFailure

logger = logging.getLogger(__name__)


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    async def safe_index(collection: str, keys, **kwargs) -> None:
        try:
            await db[collection].create_index(keys, **kwargs)
        except OperationFailure as exc:
            logger.warning("index skipped %s: %s", collection, exc)

    await safe_index("users", [("email", ASCENDING)], unique=True, sparse=True)
    await safe_index("users", [("role", ASCENDING)])

    await safe_index("properties", [("address.road_address", ASCENDING)])
    await safe_index("properties", [("address.adm_cd", ASCENDING)])

    await safe_index("landlords", [("landlord_type", ASCENDING)])
    await safe_index("landlords", [("business_registration_number_hash", ASCENDING)], sparse=True)

    await safe_index("contracts", [("property_id", ASCENDING)])
    await safe_index("contracts", [("tenant_user_id", ASCENDING)])
    await safe_index("contracts", [("landlord_user_id", ASCENDING)], sparse=True)
    await safe_index("contracts", [("contract_status", ASCENDING)])
    await safe_index(
        "contracts",
        [("tenant_user_id", ASCENDING), ("property_id", ASCENDING), ("contract_start_date", ASCENDING)],
        unique=True,
        sparse=True,
    )

    await safe_index("evidence_requests", [("contract_id", ASCENDING)])
    await safe_index("evidence_requests", [("risk_assessment_id", ASCENDING)])
    await safe_index("evidences", [("evidence_request_id", ASCENDING)])
    await safe_index("evidences", [("evidence_request_id", ASCENDING), ("document_hash", ASCENDING)], unique=True, sparse=True)
    await safe_index("verifications", [("evidence_id", ASCENDING)], unique=True, sparse=True)

    await safe_index("risk_assessments", [("case_id", ASCENDING)], unique=True, sparse=True)
    await safe_index("risk_assessments", [("contract_id", ASCENDING)], sparse=True)
    await safe_index("risk_assessments", [("risk_grade", ASCENDING)])

    await safe_index("rag_chunks", [("chunk_id", ASCENDING)], unique=True, sparse=True)
    await safe_index("rag_search_logs", [("user_id", ASCENDING), ("created_at", DESCENDING)])

    await safe_index("incidents", [("reporter_user_id", ASCENDING), ("created_at", DESCENDING)])
    await safe_index("incidents", [("status", ASCENDING)])
    await safe_index("counsel_queue", [("status", ASCENDING), ("priority_rank", ASCENDING), ("created_at", ASCENDING)])
    await safe_index("counsel_queue", [("requester_user_id", ASCENDING)])
    await safe_index("notifications", [("user_id", ASCENDING), ("created_at", DESCENDING)])
    await safe_index("notifications", [("user_id", ASCENDING), ("is_read", ASCENDING)])
    await safe_index("esign_sessions", [("contract_id", ASCENDING)])
    await safe_index("esign_sessions", [("session_code", ASCENDING)])

    await safe_index(
        "blockchain_transactions",
        [("event_type", ASCENDING), ("reference_id", ASCENDING)],
        unique=True,
        sparse=True,
    )
    await safe_index("blockchain_transactions", [("tx_hash", ASCENDING)], unique=True, sparse=True)

    await safe_index("timeline_events", [("contract_id", ASCENDING), ("occurred_at", DESCENDING)])
    await safe_index("return_plans", [("contract_id", ASCENDING)], unique=True, sparse=True)

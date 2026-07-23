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
            # 같은 키 패턴의 인덱스를 옵션만 바꿔 재정의하면(sparse→partial,
            # sparse 제거 등) 동일 자동 이름으로 IndexOptionsConflict(85/86)가
            # 난다. 키 패턴이 같은 경우에만 기존 인덱스를 드롭하고 재생성한다.
            if getattr(exc, "code", None) in {85, 86}:
                index_name = kwargs.get("name") or "_".join(
                    f"{field}_{direction}" for field, direction in keys
                )
                existing = (await db[collection].index_information()).get(index_name)
                if existing and list(existing.get("key", [])) == list(keys):
                    logger.warning(
                        "replacing legacy index options %s.%s", collection, index_name
                    )
                    await db[collection].drop_index(index_name)
                    await db[collection].create_index(keys, **kwargs)
                    return
            if kwargs.get("unique"):
                logger.error("critical unique index creation failed %s: %s", collection, exc)
                raise
            logger.warning("non-critical index skipped %s: %s", collection, exc)

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
    await safe_index(
        "incidents",
        [("contract_id", ASCENDING)],
        name="incidents_active_contract_unique",
        unique=True,
        partialFilterExpression={
            "contract_id": {"$type": "string"},
            "status": {"$in": ["Received", "Reviewing", "TransferredToRecovery"]},
        },
    )
    await safe_index("counsel_queue", [("status", ASCENDING), ("priority_rank", ASCENDING), ("created_at", ASCENDING)])
    await safe_index("counsel_queue", [("requester_user_id", ASCENDING)])
    await safe_index("notifications", [("user_id", ASCENDING), ("created_at", DESCENDING)])
    await safe_index("notifications", [("user_id", ASCENDING), ("is_read", ASCENDING)])
    await safe_index(
        "notifications",
        [("user_id", ASCENDING), ("dedupe_key", ASCENDING)],
        unique=True,
        partialFilterExpression={"dedupe_key": {"$type": "string"}},
    )
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

    # HUG 사고 전 예측·예방 업무
    await safe_index(
        "accident_predictions", [("contract_id", ASCENDING), ("predicted_at", DESCENDING)]
    )
    await safe_index(
        "accident_predictions",
        [("contract_id", ASCENDING), ("feature_fingerprint", ASCENDING)],
        unique=True,
        partialFilterExpression={"feature_fingerprint": {"$type": "string"}},
    )
    await safe_index(
        "prevention_cases",
        [("contract_id", ASCENDING), ("status", ASCENDING), ("updated_at", DESCENDING)],
    )
    await safe_index(
        "prevention_cases",
        [("contract_id", ASCENDING), ("policy_version", ASCENDING)],
        unique=True,
        partialFilterExpression={"policy_version": {"$type": "string"}},
    )
    await safe_index(
        "preventive_actions",
        [("prevention_case_id", ASCENDING), ("status", ASCENDING), ("due_at", ASCENDING)],
    )
    await safe_index("preventive_actions", [("dedupe_key", ASCENDING)], unique=True, sparse=True)
    await safe_index(
        "evidence_bundles",
        [("contract_id", ASCENDING), ("checkpoint", ASCENDING), ("policy_version", ASCENDING)],
        unique=True,
    )
    await safe_index(
        "evidence_requests",
        [("bundle_id", ASCENDING), ("item_key", ASCENDING)],
        unique=True,
        partialFilterExpression={
            "bundle_id": {"$type": "string"},
            "item_key": {"$type": "string"},
        },
    )

    # 보증이행 청구 상태머신·감사
    await safe_index("performance_claims", [("incident_id", ASCENDING)], unique=True)
    await safe_index("performance_claims", [("stage", ASCENDING), ("claim_sla_due_at", ASCENDING)])
    await safe_index(
        "claim_documents",
        [("performance_claim_id", ASCENDING), ("verification_status", ASCENDING)],
    )
    await safe_index(
        "claim_documents",
        [("performance_claim_id", ASCENDING), ("document_type", ASCENDING)],
        unique=True,
    )
    await safe_index(
        "claim_document_submissions",
        [("performance_claim_id", ASCENDING), ("document_hash", ASCENDING)],
        unique=True,
    )
    await safe_index(
        "performance_claim_events",
        [("performance_claim_id", ASCENDING), ("occurred_at", DESCENDING)],
    )
    await safe_index(
        "subrogation_payments",
        [("payment_reference", ASCENDING)],
        unique=True,
    )

    # 사고 후 채권관리 병렬 상태·원장·예측이력
    await safe_index("recovery_claims", [("performance_claim_id", ASCENDING)])
    # 두 필드 모두 등록 시 필수값이므로 compound sparse가 필요 없다. sparse는
    # 키 일부만 있어도 누락 키를 null로 인덱싱해 §4의 원칙과 어긋난다.
    await safe_index(
        "recovery_claims",
        [("performance_claim_id", ASCENDING), ("claim_type", ASCENDING)],
        unique=True,
    )
    await safe_index(
        "recovery_claims",
        [("is_closed", ASCENDING), ("recovery_stage", ASCENDING), ("updated_at", DESCENDING)],
    )
    await safe_index(
        "recovery_events", [("recovery_claim_id", ASCENDING), ("occurred_at", DESCENDING)]
    )
    await safe_index(
        "recovery_events",
        [("recovery_claim_id", ASCENDING), ("idempotency_key", ASCENDING)],
        unique=True,
        partialFilterExpression={"idempotency_key": {"$type": "string"}},
    )
    await safe_index(
        "recovery_ledger", [("recovery_claim_id", ASCENDING), ("occurred_at", DESCENDING)]
    )
    await safe_index(
        "recovery_ledger",
        [("recovery_claim_id", ASCENDING), ("idempotency_key", ASCENDING)],
        unique=True,
        partialFilterExpression={"idempotency_key": {"$type": "string"}},
    )
    await safe_index(
        "recovery_ledger",
        [("recovery_claim_id", ASCENDING), ("sequence", ASCENDING)],
        unique=True,
        partialFilterExpression={"sequence": {"$type": "int"}},
    )
    await safe_index(
        "recovery_predictions",
        [("recovery_claim_id", ASCENDING), ("predicted_at", DESCENDING)],
    )
    await safe_index(
        "recovery_predictions",
        [("recovery_claim_id", ASCENDING), ("idempotency_key", ASCENDING)],
        unique=True,
        partialFilterExpression={"idempotency_key": {"$type": "string"}},
    )
    await safe_index(
        "legal_cases", [("recovery_claim_id", ASCENDING), ("updated_at", DESCENDING)]
    )
    await safe_index(
        "legal_cases",
        [("recovery_claim_id", ASCENDING), ("case_number", ASCENDING)],
        unique=True,
    )
    await safe_index(
        "auction_cases", [("recovery_claim_id", ASCENDING), ("updated_at", DESCENDING)]
    )
    await safe_index(
        "auction_cases",
        [("recovery_claim_id", ASCENDING), ("case_number", ASCENDING)],
        unique=True,
    )
    await safe_index("demo_seed_manifests", [("template_version", ASCENDING)], unique=True)

from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import get_settings
from app.core.exceptions import ResourceNotFoundError
from app.repositories.blockchain_repository import BlockchainTransactionRepository
from app.schemas.blockchain import AnchorRequest, AnchorResponse, BlockchainTransactionResponse
from app.schemas.common import build_pagination
from app.services.blockchain.base import BlockchainAdapter
from app.services.blockchain.mock_adapter import MockBlockchainAdapter
from app.services.blockchain.polygon_adapter import PolygonBlockchainAdapter
from app.utils.datetime_utils import now_kst_iso, new_uuid
from app.utils.hashing import sha256_json


def _to_response(doc: dict) -> BlockchainTransactionResponse:
    return BlockchainTransactionResponse(
        blockchain_tx_id=doc["_id"],
        event_type=doc["event_type"],
        reference_id=doc["reference_id"],
        result_hash=doc["result_hash"],
        tx_hash=doc.get("tx_hash"),
        chain_id=doc.get("chain_id"),
        contract_address=doc.get("contract_address"),
        blockchain_status=doc["blockchain_status"],
        is_mock=doc.get("is_mock", False),
        created_at=doc["created_at"],
        confirmed_at=doc.get("confirmed_at"),
    )


def _select_adapter() -> BlockchainAdapter:
    settings = get_settings()
    if settings.blockchain_mode == "polygon":
        return PolygonBlockchainAdapter()
    return MockBlockchainAdapter()


class BlockchainService:
    """공증 요청 저장/조회 + 동일 payload 재요청 시 중복 처리(idempotent).

    Backend_API_명세서 10.5절: (event_type, reference_id) unique index로 중복 anchor를 차단하고,
    Blockchain_설계서 17장: 재전송 전 기존 tx_hash를 먼저 조회해 반환한다.
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        self._transactions = BlockchainTransactionRepository(db)
        self._adapter = _select_adapter()

    async def anchor(self, payload: AnchorRequest) -> AnchorResponse:
        existing = await self._transactions.find_by_event(payload.event_type, payload.reference_id)
        if existing:
            return AnchorResponse(
                blockchain_tx_id=existing["_id"],
                chain_id=existing.get("chain_id"),
                contract_address=existing.get("contract_address"),
                tx_hash=existing.get("tx_hash"),
                blockchain_status=existing["blockchain_status"],
                is_mock=existing.get("is_mock", False),
            )

        result_hash = payload.result_hash or sha256_json(
            {"event_type": payload.event_type, "reference_id": payload.reference_id, "payload": payload.payload}
        )
        result = await self._adapter.anchor(payload.event_type, payload.reference_id, result_hash)

        now = now_kst_iso()
        doc = {
            "_id": new_uuid(),
            "event_type": payload.event_type,
            "reference_id": payload.reference_id,
            "result_hash": result_hash,
            "tx_hash": result.tx_hash,
            "chain_id": result.chain_id,
            "contract_address": result.contract_address,
            "blockchain_status": result.blockchain_status,
            "is_mock": result.is_mock,
            "created_at": now,
            "confirmed_at": now if result.blockchain_status == "Confirmed" else None,
        }
        await self._transactions.insert(doc)
        return AnchorResponse(
            blockchain_tx_id=doc["_id"],
            chain_id=doc["chain_id"],
            contract_address=doc["contract_address"],
            tx_hash=doc["tx_hash"],
            blockchain_status=doc["blockchain_status"],
            is_mock=doc["is_mock"],
        )

    async def get_transaction(self, tx_id: str) -> BlockchainTransactionResponse:
        doc = await self._transactions.get_by_id(tx_id)
        if not doc:
            raise ResourceNotFoundError("블록체인 트랜잭션을 찾을 수 없습니다.")
        return _to_response(doc)

    async def list_transactions(self, page: int, size: int, blockchain_status: str | None):
        items, total = await self._transactions.list_paginated((page - 1) * size, size, blockchain_status)
        return [_to_response(i) for i in items], build_pagination(page, size, total)

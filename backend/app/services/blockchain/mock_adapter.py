"""Mock Chain Adapter. 외부 RPC 호출 없이 완전 로컬로 동작하며 오프라인 시연이 가능하다
(Blockchain_설계서_260714.md 28장 Mock Chain 설계 원칙과 동일)."""

from __future__ import annotations

import secrets

from app.services.blockchain.base import AnchorResult, BlockchainAdapter


class MockBlockchainAdapter(BlockchainAdapter):
    async def anchor(self, event_type: str, reference_id: str, result_hash: str) -> AnchorResult:
        tx_hash = "0x" + secrets.token_hex(32)
        return AnchorResult(
            tx_hash=tx_hash,
            blockchain_status="Confirmed",
            chain_id=80002,
            contract_address=None,
            is_mock=True,
        )

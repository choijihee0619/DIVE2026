"""Polygon(Amoy) Adapter skeleton — 이번 단계에서는 미구현이며 추후 연동 예정이다.

실제 연동 시 POLYGON_RPC_URL/POLYGON_CONTRACT_ADDRESS/POLYGON_CHAIN_ID(.env)를 사용하고,
서명 트랜잭션 전송은 별도 지갑/서비스가 담당해야 한다(Blockchain_설계서_260714.md 6.3절:
FastAPI는 개인키를 직접 보관하지 않는 것을 권장). 이 클래스는 인터페이스 자리표시자다.
"""

from __future__ import annotations

from app.core.config import get_settings
from app.core.exceptions import BlockchainAnchorFailedError
from app.services.blockchain.base import AnchorResult, BlockchainAdapter


class PolygonBlockchainAdapter(BlockchainAdapter):
    def __init__(self):
        self._settings = get_settings()

    async def anchor(self, event_type: str, reference_id: str, result_hash: str) -> AnchorResult:
        if not self._settings.polygon_rpc_url or not self._settings.polygon_contract_address:
            raise BlockchainAnchorFailedError(
                "Polygon 연동이 아직 구성되지 않았습니다. BLOCKCHAIN_MODE=mock으로 사용하세요.",
                details={"internal_reason": "POLYGON_NOT_CONFIGURED"},
            )
        # TODO(추후 연동): web3.py 또는 별도 서명 서비스로 실제 트랜잭션 전송.
        raise BlockchainAnchorFailedError(
            "Polygon 실연동은 아직 구현되지 않았습니다.",
            details={"internal_reason": "POLYGON_ADAPTER_NOT_IMPLEMENTED"},
        )

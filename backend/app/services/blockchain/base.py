"""블록체인 Adapter 공통 인터페이스. Backend는 실제 체인을 직접 호출하지 않고
이 인터페이스를 구현한 Adapter를 통해서만 접근한다(Blockchain_설계서_260714.md 4.3절 아키텍처 참고,
이번 MVP는 별도 Node.js 서비스 없이 mock/polygon 두 Adapter만 Python 내부에 둔다)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class AnchorResult:
    tx_hash: str | None
    blockchain_status: str  # Pending | Confirmed | Failed
    chain_id: int | None
    contract_address: str | None
    is_mock: bool


class BlockchainAdapter(ABC):
    @abstractmethod
    async def anchor(self, event_type: str, reference_id: str, result_hash: str) -> AnchorResult:
        """이벤트를 체인에 기록(또는 mock)하고 결과를 반환한다."""

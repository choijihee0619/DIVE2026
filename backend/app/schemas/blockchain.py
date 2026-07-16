from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class AnchorRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    event_type: str
    reference_id: str
    result_hash: str | None = None
    payload: dict | None = None
    model_version: str | None = None


class AnchorResponse(BaseModel):
    blockchain_tx_id: str
    chain_id: int | None = None
    contract_address: str | None = None
    tx_hash: str | None = None
    blockchain_status: str
    is_mock: bool


class BlockchainTransactionResponse(BaseModel):
    blockchain_tx_id: str
    event_type: str
    reference_id: str
    result_hash: str
    tx_hash: str | None = None
    chain_id: int | None = None
    contract_address: str | None = None
    blockchain_status: str
    is_mock: bool
    created_at: str
    confirmed_at: str | None = None


class BlockchainTransactionListResponse(BaseModel):
    items: list[BlockchainTransactionResponse]
    pagination: dict

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

EsignStatus = Literal["TermsAgreement", "Signing", "Anchored", "Cancelled"]
TermStatus = Literal["proposed", "agreed", "withdrawn"]
PartyRole = Literal["tenant", "landlord"]


class EsignSessionCreateRequest(BaseModel):
    contract_id: str


class EsignJoinRequest(BaseModel):
    session_code: str = Field(min_length=4, max_length=8, description="세션 초대 코드")


class TermProposeRequest(BaseModel):
    text: str = Field(min_length=5, max_length=500)


class TermActionRequest(BaseModel):
    action: Literal["agree", "withdraw"]


class EsignVerifyRequest(BaseModel):
    """위변조 검증 데모용: 필드를 넘기면 해당 값으로 변조된 문서의 해시를 비교한다."""

    tampered_fields: dict | None = Field(
        default=None, description='예: {"deposit": 200000000} — 지정 시 변조 시나리오 검증'
    )


class SpecialTerm(BaseModel):
    term_id: str
    text: str
    source: Literal["ai_recommend", "tenant", "landlord"]
    rationale: str | None = None
    status: TermStatus
    agreed_by: list[PartyRole] = []


class Participant(BaseModel):
    role: PartyRole
    user_id: str | None = None
    display_name: str | None = None
    joined: bool = False
    signed: bool = False
    signed_at: str | None = None


class EsignSessionResponse(BaseModel):
    session_id: str
    session_code: str
    contract_id: str
    status: EsignStatus
    participants: list[Participant]
    special_terms: list[SpecialTerm]
    contract_summary: dict
    contract_hash: str | None = None
    blockchain_tx_id: str | None = None
    tx_hash: str | None = None
    anchored_at: str | None = None
    created_at: str
    updated_at: str


class EsignVerifyResponse(BaseModel):
    contract_id: str
    stored_hash: str
    recomputed_hash: str
    match: bool
    tampered_fields: dict | None = None
    tx_hash: str | None = None
    blockchain_status: str | None = None
    verified_at: str

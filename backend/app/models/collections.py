"""MongoDB Collection(Document) 형태 정의.

Beanie 같은 ODM 대신 Motor를 직접 쓰기로 했으므로(README 참고) 여기서는 각 컬렉션 문서의
"정식 형태"를 TypedDict로 문서화하고, Repository 계층이 이 형태에 맞춰 dict를 조립/파싱한다.
필드명은 scripts/setup_mongodb.py, docs/MongoDB_사용_매뉴얼_260714.md, docs/Backend_API_명세서_260714.md
14장의 실제 컬렉션 설계를 그대로 따르며 임의로 새 이름을 만들지 않는다.
"""

from __future__ import annotations

from typing import Any, NotRequired, TypedDict


class UserDocument(TypedDict):
    _id: str  # user_id (UUID)
    email: str | None
    password_hash: str
    role: str
    display_name: str
    is_active: bool
    created_at: str
    last_login_at: NotRequired[str | None]


class PropertyDocument(TypedDict):
    _id: str  # property_id
    address: dict[str, Any]
    housing_type: NotRequired[str | None]
    coordinate: NotRequired[dict[str, Any] | None]
    source_system: str  # api_live | mock | user_upload
    created_at: str
    updated_at: str


class LandlordDocument(TypedDict):
    _id: str  # landlord_id
    landlord_type: str
    display_name: str
    business_registration_number_hash: NotRequired[str | None]
    dart_corp_name: NotRequired[str | None]
    business_status: NotRequired[str | None]
    source_system: str
    created_at: str
    updated_at: str


class ContractDocument(TypedDict):
    _id: str  # contract_id
    property_id: str
    tenant_user_id: str
    landlord_user_id: NotRequired[str | None]
    landlord_id: NotRequired[str | None]
    contract_status: str
    deposit: int
    contract_start_date: str
    contract_end_date: str
    landlord_type: str
    housing_type: str
    risk_assessment_id: NotRequired[str | None]
    created_at: str
    updated_at: str


class EvidenceRequestDocument(TypedDict):
    _id: str  # evidence_request_id
    contract_id: str
    risk_assessment_id: NotRequired[str | None]
    reason: str
    evidence_type: str
    due_date: NotRequired[str | None]
    verification_status: str
    created_at: str
    updated_at: str


class EvidenceDocument(TypedDict):
    _id: str  # evidence_id
    evidence_request_id: str
    uploader_id: str
    file_name: str
    content_type: str
    size_bytes: int
    object_uri: str
    document_hash: str
    verification_status: str
    submitted_at: str


class VerificationDocument(TypedDict):
    _id: str  # verification_id
    evidence_id: str
    evidence_request_id: str
    verification_status: str
    reviewer_user_id: NotRequired[str | None]
    reviewer_comment: NotRequired[str | None]
    resubmission_required: bool
    blockchain_tx_id: NotRequired[str | None]
    decided_at: NotRequired[str | None]
    created_at: str


class RiskAssessmentDocument(TypedDict):
    _id: str  # risk_assessment_id
    case_id: str
    contract_id: NotRequired[str | None]
    property_id: str
    risk_score: int
    risk_grade: str
    assessment_mode: str  # rule_based_fallback (이번 단계는 항상 이 값)
    confidence: float
    data_completeness: float
    risk_factors: list[dict[str, Any]]
    positive_factors: list[dict[str, Any]]
    missing_fields: list[str]
    required_documents: list[str]
    recommended_actions: list[str]
    source_status: dict[str, str]
    data_sources: list[str]
    fetched_at: str
    created_at: str


class RagSearchLogDocument(TypedDict):
    _id: str  # rag_search_log_id
    user_id: NotRequired[str | None]
    query: dict[str, Any]
    result_chunk_ids: list[str]
    result_count: int
    is_mock: bool
    answer_masked: NotRequired[str | None]
    created_at: str


class BlockchainTransactionDocument(TypedDict):
    _id: str  # blockchain_tx_id
    event_type: str
    reference_id: str
    result_hash: str
    tx_hash: NotRequired[str | None]
    chain_id: NotRequired[int | None]
    contract_address: NotRequired[str | None]
    blockchain_status: str
    is_mock: bool
    created_at: str
    confirmed_at: NotRequired[str | None]

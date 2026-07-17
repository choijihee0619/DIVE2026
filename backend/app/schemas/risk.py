from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel

from app.models.enums import HousingType, LandlordType


class RiskDiagnoseRequest(BaseModel):
    property_id: str
    deposit: int
    contract_start_date: date
    contract_end_date: date
    landlord_type: LandlordType
    housing_type: HousingType
    landlord_id: str | None = None
    contract_id: str | None = None


class RiskFactor(BaseModel):
    code: str
    title: str
    severity: Literal["low", "medium", "high"]
    description: str


class RiskAssessmentResponse(BaseModel):
    """API_Contract의 RiskAssessment 필드(risk_grade, risk_reasons, data_sources 등)와
    이번 과제가 요구하는 rule-based 투명성 필드(risk_score, confidence, data_completeness,
    missing_fields, source_status 등)를 함께 담는다. 계약 스키마의 additionalProperties 제한이
    없어 확장 필드 추가가 계약을 깨지 않는다(보고서의 충돌사항 참고).
    """

    diagnosis_id: str
    case_id: str
    risk_assessment_id: str
    contract_id: str | None = None
    property_id: str

    # API Contract 필드
    risk_grade: str  # LOW | MEDIUM | HIGH (계약 enum, A/B/C 아님)
    risk_reasons: list[str]
    resolvable_risks: list[str]
    unresolvable_risks: list[str]
    data_sources: list[str]

    # 이번 과제가 요구하는 rule-based fallback 투명성 필드
    risk_score: int
    assessment_mode: Literal["rule_based_fallback"] = "rule_based_fallback"
    confidence: float
    data_completeness: float
    risk_factors: list[RiskFactor]
    positive_factors: list[RiskFactor]
    missing_fields: list[str]
    required_documents: list[str]
    recommended_actions: list[str]
    source_status: dict[str, str]

    fetched_at: str
    created_at: str
    blockchain_tx_id: str | None = None

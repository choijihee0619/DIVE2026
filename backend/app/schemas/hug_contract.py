"""HUG 사고 전 계약관리, 사고위험 PoC, 사전예방 API DTO.

사고위험 모델의 출력은 실제 사고확률로 검증된 값이 아니다. ``accident_probability``은
HOUSTA 집계 prior에 평균을 맞춘 미검증 PoC 추정치이며, 응답의 ``calibration_status``와
``basis``를 함께 소비해야 한다.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.provenance import SourceMetadata


PredictionStatus = Literal["SUCCESS", "NOT_SCORABLE", "FAILED"]
PreventionStatus = Literal[
    "Monitoring",
    "RiskDetected",
    "Notified",
    "ActionRequested",
    "EvidenceSubmitted",
    "Verifying",
    "Mitigated",
    "Overdue",
    "EscalatedMonitoring",
]
PreventiveActionStatus = Literal[
    "Requested",
    "InProgress",
    "Submitted",
    "Verifying",
    "Completed",
    "Rejected",
    "Cancelled",
    "Overdue",
]


class AccidentPredictRequest(BaseModel):
    """DB 계약의 권위 있는 입력으로 단건 예측을 생성한다."""

    contract_id: str = Field(min_length=1, max_length=200)


class AccidentPredictionRefreshBatchRequest(BaseModel):
    contract_ids: list[str] | None = Field(default=None, max_length=500)
    data_mode: Literal["LIVE", "DEMO"] = "LIVE"


class AccidentPredictionFactor(BaseModel):
    feature: str
    label: str
    value: str | int | float | None
    importance: float
    explanation_method: Literal["ensemble_global_feature_importance"] = (
        "ensemble_global_feature_importance"
    )


class AccidentPredictionResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    prediction_id: str
    contract_id: str
    pu_risk_score: float | None = None
    risk_percentile: float | None = None
    accident_probability: float | None = None
    calibration_status: str
    prediction_status: PredictionStatus
    failure_reason: list[str] = Field(default_factory=list)
    model_version: str
    model_sha256: str
    feature_snapshot: dict[str, Any]
    top_factors: list[AccidentPredictionFactor] = Field(default_factory=list)
    data_completeness: float = Field(ge=0, le=1)
    basis: str
    predicted_at: str
    valid_until: str
    source: SourceMetadata


class PreventiveActionCreateRequest(BaseModel):
    action_type: Literal[
        "EVIDENCE_REQUEST",
        "CREDIT_ENHANCEMENT_REQUEST",
        "CALLBACK",
        "ASSIGN_OWNER",
        "RERUN_PREDICTION",
        "MANUAL_REVIEW",
    ]
    target_role: Literal["tenant", "landlord", "hug_admin"]
    due_at: str | None = None
    note: str | None = Field(default=None, max_length=2000)
    details: dict[str, Any] = Field(default_factory=dict)


class PreventiveActionUpdateRequest(BaseModel):
    status: PreventiveActionStatus
    note: str | None = Field(default=None, max_length=2000)
    details: dict[str, Any] = Field(default_factory=dict)


class PreventionSweepRequest(BaseModel):
    """`as_of_date`는 고정 시연과 회귀테스트를 위한 결정적 기준일이다."""

    as_of_date: date | None = None
    contract_ids: list[str] | None = Field(default=None, max_length=500)
    data_mode: Literal["LIVE", "DEMO"] = "LIVE"


class EvidenceBundleItemResponse(BaseModel):
    item_key: str
    label: str
    evidence_type: str
    evidence_request_id: str
    verification_status: str
    due_at: str
    is_verified: bool
    is_overdue: bool


class EvidenceBundleResponse(BaseModel):
    evidence_bundle_id: str
    contract_id: str
    checkpoint: Literal["D90", "D60", "D30"]
    policy_version: str
    status: Literal["Pending", "InReview", "Completed", "Overdue"]
    due_at: str
    required_count: int
    submitted_count: int
    verified_count: int
    overdue_count: int
    completion_ratio: float
    items: list[EvidenceBundleItemResponse]
    created_at: str
    updated_at: str


class PreventionCaseResponse(BaseModel):
    prevention_case_id: str
    contract_id: str
    status: PreventionStatus
    triggers: list[dict[str, Any]]
    priority_score: float
    priority_components: dict[str, float]
    owner_user_id: str | None = None
    owner_center: str | None = None
    next_action: str | None = None
    due_at: str | None = None
    policy_version: str
    created_at: str
    updated_at: str


class PreventiveActionResponse(BaseModel):
    action_id: str
    prevention_case_id: str
    contract_id: str
    action_type: str
    status: PreventiveActionStatus
    actor_role: str
    actor_user_id: str | None = None
    target_role: str
    requested_at: str
    due_at: str | None = None
    completed_at: str | None = None
    note: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    audit_log: list[dict[str, Any]] = Field(default_factory=list)

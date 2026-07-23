"""HUG 사고 후 채권관리 요청/공통 스키마.

회수업무는 법무·경매·상환이 병렬로 진행될 수 있으므로 하나의 선형 상태 enum으로
축약하지 않는다. ``status_axis``와 축별 값은 이 파일에서 함께 검증한다.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.provenance import SourceMetadata

# 기존 import 사용자를 위한 도메인 별칭. 실제 정의/검증은 공통 provenance 모듈 한 곳에서 한다.
DataProvenance = SourceMetadata

RecoveryStage = Literal[
    "Registered",
    "Investigation",
    "Preservation",
    "Collection",
    "Distribution",
    "Closing",
]
CollectionRoute = Literal[
    "None",
    "Voluntary",
    "PaymentPlan",
    "Litigation",
    "Auction",
    "PublicSale",
    "Insolvency",
]
LegalStatus = Literal["None", "PaymentOrder", "Lawsuit", "Judgment", "Enforcement"]
AuctionStatus = Literal[
    "None",
    "Filed",
    "InProgress",
    "Sold",
    "DividendScheduled",
    "Distributed",
]
RepaymentPlanStatus = Literal[
    "None",
    "Proposed",
    "Active",
    "Delinquent",
    "Completed",
    "Terminated",
]
BalanceStatus = Literal["Unrecovered", "PartiallyRecovered", "FullyRecovered"]

STATUS_AXIS_VALUES: dict[str, frozenset[str]] = {
    "recovery_stage": frozenset(RecoveryStage.__args__),
    "collection_route": frozenset(CollectionRoute.__args__),
    "legal_status": frozenset(LegalStatus.__args__),
    "auction_status": frozenset(AuctionStatus.__args__),
    "repayment_plan_status": frozenset(RepaymentPlanStatus.__args__),
    "balance_status": frozenset(BalanceStatus.__args__),
}


class RecoveryEventCreateRequest(BaseModel):
    event_type: str = Field(min_length=2, max_length=100)
    status_axis: str | None = Field(default=None, description="병렬 상태축. 단순 업무메모 이벤트는 생략 가능")
    after: str | None = Field(default=None, description="변경 후 축 값")
    note: str | None = Field(default=None, max_length=2000)
    occurred_at: datetime | None = None
    idempotency_key: str = Field(min_length=4, max_length=200)

    @field_validator("occurred_at")
    @classmethod
    def _timezone_aware(cls, value: datetime | None):
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("occurred_at은 timezone offset을 포함해야 합니다.")
        return value

    @model_validator(mode="after")
    def _validate_axis(self):
        if (self.status_axis is None) != (self.after is None):
            raise ValueError("status_axis와 after는 함께 지정해야 합니다.")
        if self.status_axis is None:
            return self
        allowed = STATUS_AXIS_VALUES.get(self.status_axis)
        if allowed is None:
            raise ValueError(f"status_axis는 {sorted(STATUS_AXIS_VALUES)} 중 하나여야 합니다.")
        if self.after not in allowed:
            raise ValueError(f"{self.status_axis} 값은 {sorted(allowed)} 중 하나여야 합니다.")
        return self


LedgerEntryType = Literal[
    "PRINCIPAL_ACCRUAL",
    "LEGAL_COST_ACCRUAL",
    "DELAY_DAMAGE_ACCRUAL",
    "ENFORCEMENT_COST_ACCRUAL",
    "RECEIPT",
    "DIVIDEND_RECEIPT",
    "ADJUSTMENT_INCREASE",
    "ADJUSTMENT_DECREASE",
]

LEDGER_COMPONENTS = frozenset({"principal", "legal_cost", "delay_damage", "enforcement_cost"})
_DIRECT_ACCRUAL_COMPONENT = {
    "PRINCIPAL_ACCRUAL": "principal",
    "LEGAL_COST_ACCRUAL": "legal_cost",
    "DELAY_DAMAGE_ACCRUAL": "delay_damage",
    "ENFORCEMENT_COST_ACCRUAL": "enforcement_cost",
}


class RecoveryLedgerEntryCreateRequest(BaseModel):
    entry_type: LedgerEntryType
    amount_won: int = Field(gt=0)
    allocations: dict[str, int] = Field(
        default_factory=dict,
        description="입금·배당·조정 금액의 원금/비용별 명시 배분. 자동 충당순서는 적용하지 않음",
    )
    note: str | None = Field(default=None, max_length=2000)
    reference_type: str | None = Field(default=None, max_length=100)
    reference_id: str | None = Field(default=None, max_length=200)
    occurred_at: datetime | None = None
    idempotency_key: str = Field(min_length=4, max_length=200)

    @field_validator("occurred_at")
    @classmethod
    def _timezone_aware(cls, value: datetime | None):
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("occurred_at은 timezone offset을 포함해야 합니다.")
        return value

    @model_validator(mode="after")
    def _validate_allocations(self):
        unknown = set(self.allocations) - LEDGER_COMPONENTS
        if unknown:
            raise ValueError(f"지원하지 않는 원장 구성항목입니다: {sorted(unknown)}")
        if any(not isinstance(v, int) or v <= 0 for v in self.allocations.values()):
            raise ValueError("allocations 금액은 0보다 큰 원 단위 정수여야 합니다.")

        if self.entry_type in _DIRECT_ACCRUAL_COMPONENT:
            if self.allocations:
                raise ValueError(f"{self.entry_type}는 allocations를 지정하지 않습니다.")
        else:
            if not self.allocations:
                raise ValueError(f"{self.entry_type}는 구성항목별 allocations가 필요합니다.")
            if sum(self.allocations.values()) != self.amount_won:
                raise ValueError("allocations 합계는 amount_won과 같아야 합니다.")
        return self


class RecoveryPredictRequest(BaseModel):
    auction_filed_date: date | None = Field(
        default=None,
        description="원장 신청일이 없거나 시나리오를 비교할 때만 지정하는 가정값",
    )
    assumption_reason: str | None = Field(default=None, max_length=500)
    idempotency_key: str = Field(min_length=4, max_length=200)

    @model_validator(mode="after")
    def _validate_assumption(self):
        if self.auction_filed_date is not None and not self.assumption_reason:
            raise ValueError("가정한 경·공매 신청일에는 assumption_reason이 필요합니다.")
        return self


CloseReason = Literal[
    "FULL_RECOVERY",
    "SOLD",
    "WRITTEN_OFF",
    "INSOLVENCY_DISCHARGE",
    "LEGAL_EXPIRY",
    "OTHER_APPROVED",
]


class RecoveryCloseRequest(BaseModel):
    reason: CloseReason
    note: str | None = Field(default=None, max_length=2000)
    confirm: bool = Field(default=False, description="종결 액션 명시 확인")
    idempotency_key: str = Field(min_length=4, max_length=200)

    @model_validator(mode="after")
    def _validate_close(self):
        if not self.confirm:
            raise ValueError("채권 종결에는 confirm=true가 필요합니다.")
        if self.reason != "FULL_RECOVERY" and not (self.note or "").strip():
            raise ValueError("전액회수 외 종결에는 승인 근거 note가 필요합니다.")
        return self


ManagedLegalStatus = Literal["PaymentOrder", "Lawsuit", "Judgment", "Enforcement"]
LegalCaseType = Literal["PaymentOrder", "Lawsuit", "Enforcement"]


class LegalCaseCreateRequest(BaseModel):
    case_type: LegalCaseType
    court: str = Field(min_length=2, max_length=200)
    case_number: str = Field(min_length=2, max_length=100)
    filing_date: date
    status: ManagedLegalStatus
    claimed_amount_won: int = Field(default=0, ge=0)
    legal_cost_won: int = Field(default=0, ge=0)
    judgment_amount_won: int | None = Field(default=None, ge=0)
    judgment: str | None = Field(default=None, max_length=2000)
    note: str | None = Field(default=None, max_length=2000)
    idempotency_key: str = Field(min_length=4, max_length=200)

    @model_validator(mode="after")
    def _validate_status(self):
        minimum = {"PaymentOrder": 0, "Lawsuit": 1, "Enforcement": 3}[self.case_type]
        order = {"PaymentOrder": 0, "Lawsuit": 1, "Judgment": 2, "Enforcement": 3}
        if order[self.status] < minimum:
            raise ValueError("법무 사건 상태가 사건 유형보다 앞설 수 없습니다.")
        if self.status in {"Judgment", "Enforcement"} and self.judgment_amount_won is None:
            raise ValueError("판결·집행 상태에는 judgment_amount_won이 필요합니다.")
        return self


class LegalCaseUpdateRequest(BaseModel):
    expected_version: int = Field(ge=1)
    status: ManagedLegalStatus | None = None
    legal_cost_won: int | None = Field(default=None, ge=0)
    judgment_amount_won: int | None = Field(default=None, ge=0)
    judgment: str | None = Field(default=None, max_length=2000)
    note: str | None = Field(default=None, max_length=2000)
    idempotency_key: str = Field(min_length=4, max_length=200)

    @model_validator(mode="after")
    def _validate_changes(self):
        if all(
            value is None
            for value in (
                self.status,
                self.legal_cost_won,
                self.judgment_amount_won,
                self.judgment,
            )
        ):
            raise ValueError("변경할 법무 사건 항목이 없습니다.")
        if self.status in {"Judgment", "Enforcement"} and self.judgment_amount_won is None:
            # 기존 판결금액이 있을 수 있으므로 최종 검증은 service에서 병합 후 수행한다.
            pass
        return self


ManagedAuctionStatus = Literal[
    "Filed",
    "InProgress",
    "Sold",
    "DividendScheduled",
    "Distributed",
]
AuctionCaseType = Literal["Auction", "PublicSale"]


class AuctionCaseCreateRequest(BaseModel):
    auction_type: AuctionCaseType
    case_number: str = Field(min_length=2, max_length=100)
    filing_date: date
    status: ManagedAuctionStatus = "Filed"
    appraisal_won: int = Field(default=0, ge=0)
    sale_date: date | None = None
    dividend_date: date | None = None
    dividend_amount_won: int = Field(default=0, ge=0)
    note: str | None = Field(default=None, max_length=2000)
    idempotency_key: str = Field(min_length=4, max_length=200)

    @model_validator(mode="after")
    def _validate_dates(self):
        _validate_auction_progress(
            filing_date=self.filing_date,
            status=self.status,
            sale_date=self.sale_date,
            dividend_date=self.dividend_date,
        )
        return self


class AuctionCaseUpdateRequest(BaseModel):
    expected_version: int = Field(ge=1)
    status: ManagedAuctionStatus | None = None
    appraisal_won: int | None = Field(default=None, ge=0)
    sale_date: date | None = None
    dividend_date: date | None = None
    dividend_amount_won: int | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=2000)
    idempotency_key: str = Field(min_length=4, max_length=200)

    @model_validator(mode="after")
    def _validate_changes(self):
        if all(
            value is None
            for value in (
                self.status,
                self.appraisal_won,
                self.sale_date,
                self.dividend_date,
                self.dividend_amount_won,
            )
        ):
            raise ValueError("변경할 경·공매 사건 항목이 없습니다.")
        return self


def _validate_auction_progress(
    *,
    filing_date: date,
    status: str,
    sale_date: date | None,
    dividend_date: date | None,
) -> None:
    if sale_date and sale_date < filing_date:
        raise ValueError("매각일은 신청일보다 빠를 수 없습니다.")
    if dividend_date and dividend_date < (sale_date or filing_date):
        raise ValueError("배당일은 신청일·매각일보다 빠를 수 없습니다.")
    if status in {"Sold", "DividendScheduled", "Distributed"} and sale_date is None:
        raise ValueError("매각 이후 상태에는 sale_date가 필요합니다.")
    if status in {"DividendScheduled", "Distributed"} and dividend_date is None:
        raise ValueError("배당 단계에는 dividend_date가 필요합니다.")


class DemoSeedRequest(BaseModel):
    use_model: bool = Field(default=True, description="실제 저장 모델 추론 사용. 실패 시 고정 캐시값 사용")
    purge: bool = Field(
        default=False,
        description="Seed 전에 demo 네임스페이스 전체 삭제(시연 중 생성 문서 포함, §20.3 완전 원복)",
    )
    include_scale: bool = Field(
        default=True,
        description="§20.2 규모감 시딩(RTMS 표본 가상 계약 + 배경 이행 사건 + PU 실추론) 포함",
    )

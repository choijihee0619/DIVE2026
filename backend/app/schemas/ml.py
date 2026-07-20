from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, field_validator

PRODUCTS = ["전세보증금반환보증", "개인임대사업자임대보증금보증"]
CLAIM_TYPES = ["소송대지급금", "구상채권(신상품)", "구상채권"]


class RecoveryPredictRequest(BaseModel):
    product_name: str = Field(description="상품명", examples=PRODUCTS)
    claim_type: str = Field(description="채권구분", examples=CLAIM_TYPES)
    claimed_amount: int = Field(ge=0, description="신청청구금액(원)")
    incurred_amount: int = Field(ge=0, description="발생금액(원)")
    auction_filed_date: date = Field(description="경/공매 신청일자")
    incurred_date: date = Field(description="채권 발생일자")

    @field_validator("product_name")
    @classmethod
    def _check_product(cls, v: str) -> str:
        if v not in PRODUCTS:
            raise ValueError(f"product_name은 {PRODUCTS} 중 하나여야 합니다.")
        return v

    @field_validator("claim_type")
    @classmethod
    def _check_claim(cls, v: str) -> str:
        if v not in CLAIM_TYPES:
            raise ValueError(f"claim_type은 {CLAIM_TYPES} 중 하나여야 합니다.")
        return v


class CounselClassifyRequest(BaseModel):
    text: str = Field(min_length=10, max_length=8000, description="상담 상황 요약 텍스트")

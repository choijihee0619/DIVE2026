"""HUG 회수 코크핏 대시보드 데이터 서비스.

데이터 소스 (전부 파일 기반, public_data 로더 캐시 사용):
- recovery_priority_scores_*.csv : 학습 모델로 스코어링한 전 채권 (합성데이터 기준)
- housta_region_risk_*.csv       : 시군구별 실집계 사고율 (HUG 빅데이터 개방 포털)
- housta_issuance_region_monthly_*.csv : 발급 시계열 (정상 모수)
- housta_victim_locations_*.csv  : 전세사기피해주택 시군구 분포
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.core.exceptions import ModelInsufficientDataError
from app.services import public_data
from app.services.ml_service import BASIS_NOTE, W_RECOVERY, W_SPEED


def _require(df: pd.DataFrame | None, name: str) -> pd.DataFrame:
    if df is None:
        raise ModelInsufficientDataError(f"{name} 데이터가 없습니다. 수집/학습 스크립트를 먼저 실행하세요.")
    return df


def summary() -> dict:
    scores = _require(public_data.priority_scores(), "priority_scores")
    grades = scores["pred_recovery_grade"].value_counts().to_dict()
    by_product = (
        scores.groupby("product_name")["claimed_amount"].agg(["count", "sum"]).reset_index()
        .rename(columns={"count": "cnt", "sum": "claimed_sum_won"})
        .to_dict(orient="records")
    )
    return {
        "portfolio_count": int(len(scores)),
        "claimed_total_won": int(scores["claimed_amount"].sum()),
        "expected_recovery_total_won": int(scores["expected_recovery_won"].sum()),
        "median_pred_recovery_ratio": float(scores["pred_recovery_ratio"].median()),
        "median_pred_days": int(scores["pred_days_to_dividend"].median()),
        "grade_counts": {k: int(v) for k, v in grades.items()},
        "by_product": by_product,
        "priority_weights": {"recovery": W_RECOVERY, "speed": W_SPEED},
        "basis": BASIS_NOTE,
    }


def priority_list(page: int, size: int, grade: str | None, claim_type: str | None) -> dict:
    scores = _require(public_data.priority_scores(), "priority_scores")
    df = scores
    if grade:
        df = df[df["pred_recovery_grade"] == grade]
    if claim_type:
        df = df[df["claim_type"] == claim_type]
    df = df.sort_values("priority_score", ascending=False)
    total = len(df)
    start = (page - 1) * size
    items = df.iloc[start : start + size].to_dict(orient="records")
    return {
        "items": items,
        "pagination": {"page": page, "size": size, "total": int(total),
                       "total_pages": int(np.ceil(total / size)) if size else 0},
        "basis": BASIS_NOTE,
    }


def region_risk_map(sido: str | None) -> dict:
    df = _require(public_data.region_risk(), "region_risk")
    detail = df[df["is_summary"] == 0].copy()
    summaries = df[df["is_summary"] == 1].copy()
    if sido:
        detail = detail[detail["sido"] == sido]
    return {
        "sido_summary": summaries[["sido", "accident_cnt", "accident_amt_won", "accident_rate_pct"]]
        .to_dict(orient="records"),
        "sigungu": detail[["adm_cd", "sido", "sigungu", "accident_cnt", "accident_amt_won", "accident_rate_pct"]]
        .to_dict(orient="records"),
        "basis": public_data.region_risk_basis(),
    }


def issuance_timeseries(sido: str | None, housing_type: str | None) -> dict:
    df = _require(public_data.issuance_monthly(), "issuance_monthly")
    if sido:
        df = df[df["sido"] == sido]
    if housing_type:
        df = df[df["housing_type"] == housing_type]
    grouped = (
        df.groupby("yyyymm")[["issue_cnt", "issue_amt_won"]].sum().reset_index().sort_values("yyyymm")
    )
    return {
        "series": grouped.to_dict(orient="records"),
        "filters": {"sido": sido, "housing_type": housing_type},
        "basis": "HUG 빅데이터 개방 포털 전세보증금반환보증 상세현황(실집계)",
    }


def victim_map(year: str | None) -> dict:
    df = _require(public_data.victim_locations(), "victim_locations")
    if year:
        df = df[df["year"].astype(str) == str(year)]
    grouped = (
        df.groupby(["year", "sido_short", "sigungu"])["victim_house_cnt"].sum().reset_index()
        .sort_values("victim_house_cnt", ascending=False)
    )
    return {
        "items": grouped.to_dict(orient="records"),
        "basis": "경공매지원서비스 신청자의 전세사기피해주택 소재지(HUG 실집계)",
    }

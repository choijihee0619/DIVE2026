"""HUG 채권회수 대시보드 대시보드 데이터 서비스.

데이터 소스 (전부 파일 기반, public_data 로더 캐시 사용):
- recovery_priority_scores_*.csv : 학습 모델로 스코어링한 전 채권 (합성데이터 기준)
- housta_region_risk_*.csv       : 시군구별 실집계 사고율 (HUG 빅데이터 개방 포털)
- housta_issuance_region_monthly_*.csv : 발급 시계열 (정상 모수)
- housta_victim_locations_*.csv  : 전세사기피해주택 시군구 분포
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import get_settings
from app.core.exceptions import ModelInsufficientDataError
from app.schemas.provenance import source_metadata
from app.services import public_data
from app.services.ml_service import BASIS_NOTE, W_RECOVERY, W_SPEED
from app.services.recovery_service import RecoveryService, claim_is_closed


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


def _as_of_from_latest(pattern: str, fallback: str | None = None) -> str:
    matches = sorted(Path(get_settings().data_dir).glob(pattern))
    if matches:
        match = re.search(r"(20\d{6})", matches[-1].name)
        if match:
            value = match.group(1)
            return f"{value[:4]}-{value[4:6]}-{value[6:]}"
    return fallback or date.today().isoformat()


def _is_demo_doc(doc: dict) -> bool:
    source = doc.get("provenance") or doc.get("source") or {}
    document_id = str(doc.get("_id") or "")
    return bool(
        doc.get("is_demo")
        or source.get("is_demo")
        or source.get("data_mode") == "DEMO"
        or document_id.startswith("demo-")
    )


async def overview(db: AsyncIOMotorDatabase) -> dict:
    """업무대장/합성 참조/공공 집계를 섞지 않는 통합 대시보드 KPI."""

    all_documents = {
        "contracts": [doc async for doc in db.contracts.find({})],
        "prevention_cases": [doc async for doc in db.prevention_cases.find({})],
        "incidents": [doc async for doc in db.incidents.find({})],
        "performance_claims": [doc async for doc in db.performance_claims.find({})],
        "recovery_claims": [doc async for doc in db.recovery_claims.find({})],
    }
    mode_breakdown_by_collection = {
        name: {
            "DEMO": sum(1 for doc in docs if _is_demo_doc(doc)),
            "LIVE": sum(1 for doc in docs if not _is_demo_doc(doc)),
        }
        for name, docs in all_documents.items()
    }
    demo_count = sum(item["DEMO"] for item in mode_breakdown_by_collection.values())
    live_count = sum(item["LIVE"] for item in mode_breakdown_by_collection.values())

    # 실제 업무문서가 하나라도 있으면 LIVE만 집계한다. LIVE가 전혀 없는 시연 환경에서만
    # DEMO를 선택해, 시연 seed가 실제 KPI를 부풀리지 않도록 한다.
    operational_mode = "LIVE" if live_count or not demo_count else "DEMO"
    selected_documents = {
        name: [
            doc for doc in docs
            if _is_demo_doc(doc) == (operational_mode == "DEMO")
        ]
        for name, docs in all_documents.items()
    }
    contracts = selected_documents["contracts"]
    prevention_cases = selected_documents["prevention_cases"]
    incidents = selected_documents["incidents"]
    performance_claims = selected_documents["performance_claims"]
    recovery_claims = selected_documents["recovery_claims"]
    selected_operational_docs = [
        doc for docs in selected_documents.values() for doc in docs
    ]

    pre_incident_statuses = {
        "ContractFinalized", "Monitoring", "D90Requested", "ReturnPlanSubmitted", "AtRisk"
    }
    action_needed_statuses = {"RiskDetected", "Notified", "ActionRequested", "Verifying", "Overdue", "EscalatedMonitoring"}
    performance_done = {"RecoveryClaimRegistered", "TransferredToRecovery", "Rejected"}
    active_recovery = [claim for claim in recovery_claims if not claim_is_closed(claim)]
    if operational_mode == "DEMO":
        operational_source_type = "demo_scenario"
        operational_dataset = "hug-workflow-v1.1.0"
        operational_basis = "명시적 S1~S7 시연 업무대장"
    else:
        operational_source_type = "user_submitted"
        operational_dataset = "hug_operational_register"
        operational_basis = "플랫폼 LIVE 업무대장(시연 문서는 KPI에서 제외)"
    selected_as_of = [
        (doc.get("provenance") or doc.get("source") or {}).get("as_of_date")
        or str(doc.get("updated_at") or doc.get("created_at") or "")[:10]
        for doc in selected_operational_docs
    ]
    operational_as_of = max(
        (str(value) for value in selected_as_of if value),
        default=date.today().isoformat(),
    )

    recovery_summary = await RecoveryService(db).summary(data_mode=operational_mode)
    recovery_kpis = {
        key: value
        for key, value in recovery_summary.items()
        if key not in {
            "provenance", "source_type", "basis", "is_demo", "data_mode_filter",
            "data_mode_breakdown", "excluded_claim_count",
        }
    }
    selected_count = len(selected_operational_docs)
    operational = {
        "guarantee_contract_count": len(contracts),
        "pre_incident_active_contract_count": sum(
            1 for contract in contracts if contract.get("contract_status") in pre_incident_statuses
        ),
        "high_risk_action_needed_contract_count": len(
            {
                case.get("contract_id")
                for case in prevention_cases
                if case.get("status") in action_needed_statuses
            }
            - {None}
        ),
        "performance_claim_in_progress_count": sum(
            1 for claim in performance_claims if claim.get("stage") not in performance_done
        ),
        **recovery_kpis,
        "pipeline_counts": {
            "prevention_action_needed": sum(
                1 for case in prevention_cases if case.get("status") in action_needed_statuses
            ),
            "accident_notified": sum(
                1 for incident in incidents if incident.get("status") == "Received"
            ),
            "performance_review": sum(
                1 for claim in performance_claims if claim.get("stage") in {"ClaimReceived", "SupplementRequested", "UnderReview", "OnHold"}
            ),
            "handover_waiting": sum(
                1 for claim in performance_claims if claim.get("stage") in {"Approved", "HandoverScheduled"}
            ),
            "subrogation_paid": sum(
                1 for claim in performance_claims if claim.get("stage") == "SubrogationPaid"
            ),
            "recovery_active": len(active_recovery),
        },
        "selected_data_mode": operational_mode,
        "selected_document_count": selected_count,
        "excluded_document_count": demo_count + live_count - selected_count,
        "data_mode_breakdown": {"DEMO": demo_count, "LIVE": live_count},
        "data_mode_breakdown_by_collection": mode_breakdown_by_collection,
        "provenance": source_metadata(
            data_mode=operational_mode,
            source_type=operational_source_type,
            source_dataset=operational_dataset,
            as_of_date=operational_as_of,
            is_demo=(operational_mode == "DEMO"),
            basis=operational_basis,
        ),
    }

    try:
        reference_values = summary()
        reference_status = "AVAILABLE"
    except ModelInsufficientDataError:
        reference_values = {}
        reference_status = "UNAVAILABLE"
    reference = {
        "status": reference_status,
        **reference_values,
        "provenance": source_metadata(
            data_mode="REFERENCE",
            source_type="provided_synthetic",
            source_dataset="recovery_priority_scores",
            as_of_date=_as_of_from_latest("processed/ml/recovery_priority_scores_*.csv"),
            is_demo=False,
            basis="발제사 제공 합성 배당 데이터 기반 참조 포트폴리오. 업무대장 KPI와 합산하지 않음",
        ),
    }
    public = {
        "region_risk_basis": public_data.region_risk_basis(),
        "issuance_available": public_data.issuance_monthly() is not None,
        "accident_annual_available": public_data.return_guarantee_accident_annual() is not None,
        "provenance": source_metadata(
            data_mode="REFERENCE",
            source_type="public_aggregate",
            source_dataset="HOUSTA_open_aggregate",
            as_of_date=_as_of_from_latest("processed/housta/housta_*.csv"),
            is_demo=False,
            basis="HUG 빅데이터 개방 포털 공개 집계. 개별 계약·피해자 업무대장이 아님",
        ),
    }
    return {
        "operational_register": operational,
        "reference_portfolio": reference,
        "public_aggregate": public,
        "population_policy": (
            "운영 KPI는 LIVE가 있으면 LIVE만, LIVE가 없으면 DEMO만 선택한다. "
            "운영·합성 참조·공공 집계 모집단의 건수·잔고·예상회수액을 서로 합산하지 않음"
        ),
    }


def issuance_incident_trend(year_from: int | None = None, year_to: int | None = None) -> dict:
    """동일 상품·전국 범위의 연도별 발급/사고 결합 시계열.

    발급 원천은 월별이지만 공개 사고 원천이 연도별뿐이므로 월별 사고를 0 또는 보간값으로
    만들지 않는다. 실제 제공 단위를 응답 메타데이터로 명확히 반환한다.
    """

    issuance = _require(public_data.issuance_monthly(), "issuance_monthly").copy()
    issuance["year"] = pd.to_numeric(issuance["year"], errors="coerce")
    issuance["issue_cnt"] = pd.to_numeric(issuance["issue_cnt"], errors="coerce").fillna(0)
    issuance["issue_amt_won"] = pd.to_numeric(
        issuance["issue_amt_won"], errors="coerce"
    ).fillna(0)
    issue_annual = (
        issuance.dropna(subset=["year"])
        .groupby("year")[["issue_cnt", "issue_amt_won"]]
        .sum()
        .reset_index()
    )
    accidents = public_data.return_guarantee_accident_annual()
    fallback_note = (
        "월별 사고 공개 원천이 없어 동일 상품·전국 범위의 연도별 사고자료로 폴백했습니다. "
        "월별 사고건수나 사고율을 보간하지 않습니다."
    )
    if accidents is None:
        if year_from is not None:
            issue_annual = issue_annual[issue_annual["year"] >= year_from]
        if year_to is not None:
            issue_annual = issue_annual[issue_annual["year"] <= year_to]
        return {
            "status": "PARTIAL",
            "requested_granularity": "month",
            "actual_granularity": "year",
            "series": [
                {"year": int(row.year), "issue_cnt": int(row.issue_cnt),
                 "issue_amt_won": int(row.issue_amt_won), "accident_cnt": None,
                 "accident_amt_won": None, "accident_rate_pct": None}
                for row in issue_annual.itertuples(index=False)
            ],
            "accident_series_status": "UNAVAILABLE",
            "fallback_note": fallback_note,
            "basis": "발급 집계만 확보; 동일상품 전국 연도별 사고 원천 미확보",
        }

    accidents = accidents.copy()
    accidents["year"] = pd.to_numeric(accidents["year"], errors="coerce")
    merged = issue_annual.merge(accidents, how="inner", on="year").sort_values("year")
    if year_from is not None:
        merged = merged[merged["year"] >= year_from]
    if year_to is not None:
        merged = merged[merged["year"] <= year_to]
    merged["accident_rate_pct"] = np.where(
        merged["issue_cnt"] > 0,
        merged["accident_cnt"] / merged["issue_cnt"] * 100,
        np.nan,
    )
    series = [
        {
            "year": int(row.year),
            "issue_cnt": int(row.issue_cnt),
            "issue_amt_won": int(row.issue_amt_won),
            "accident_cnt": int(row.accident_cnt),
            "accident_amt_won": int(row.accident_amt_won),
            "accident_rate_pct": round(float(row.accident_rate_pct), 3)
            if pd.notna(row.accident_rate_pct) else None,
        }
        for row in merged.itertuples(index=False)
    ]
    return {
        "status": "AVAILABLE_WITH_GRANULARITY_FALLBACK",
        "requested_granularity": "month",
        "actual_granularity": "year",
        "product": "전세보증금반환보증",
        "region_scope": "전국",
        "series": series,
        "accident_series_status": "AVAILABLE_ANNUAL_ONLY",
        "fallback_note": fallback_note,
        "filters": {"year_from": year_from, "year_to": year_to},
        "provenance": source_metadata(
            data_mode="REFERENCE",
            source_type="public_aggregate",
            source_dataset="HOUSTA_return_guarantee_issuance_and_accident",
            as_of_date=_as_of_from_latest("raw/housta/raw_housta_*_전세관련_현황.xlsx"),
            is_demo=False,
            basis=(
                "HUG 빅데이터 개방 포털 전세보증금반환보증 전국 발급현황 + "
                + public_data.return_guarantee_accident_annual_basis()
            ),
        ),
    }

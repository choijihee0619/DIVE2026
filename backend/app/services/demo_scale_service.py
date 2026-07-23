"""RTMS 실거래 표본 기반 규모감 시딩(§20.2).

- 사전 계약관리: RTMS 전월세 실거래 표본 N건을 **명시적 가상 보증계약**으로 시딩한다.
  입력 분포(시도·주택유형·보증금)만 실데이터를 참조하며, 계약 자체는 실존하지 않는다.
- 사고접수·보증이행: 발제사 파일에 공통 사건 ID가 없어 사건 단위 실데이터 구성이
  불가하므로(§20.2), 표본 중 고정 인덱스를 다양한 이행 단계의 배경 사건으로 구성한다.
- PU 사고위험 실추론은 seed 오케스트레이터가 AccidentPredictionService.refresh_batch로
  수행한다(입력이 시도·주택유형·보증금뿐이라 전량 스코어링 가능).

모든 문서는 demo-* 고정 ID·is_demo=True라 §20.3 purge/재시딩 대상이다. 시연 계약(S2,
priority 94)이 항상 우선순위 상위에 오도록 표본은 만기·증빙 미해결이 없는 일반 계약으로
만 구성한다(예방 케이스·기한초과 없음 → priority 구성요소가 낮게 산정된다).
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from app.core.config import get_settings
from app.schemas.provenance import source_metadata

SCALE_SEED = 260723
SCALE_SAMPLE_SIZE = 150
SCALE_AS_OF = date(2026, 7, 23)
_AS_OF_TS = "2026-07-23T09:00:00+09:00"

# RTMS 표본 housing_type → 플랫폼 계약 enum (accident_prediction_service.BACKEND_HOUSING_MAP 역방향)
_HOUSING_TO_ENUM = {
    "아파트": "APARTMENT",
    "연립다세대": "MULTI_FAMILY",
    "단독다가구": "MULTI_HOUSEHOLD",
    "오피스텔": "OFFICETEL",
}

# 배경 이행 사건 단계 구성(§20.2 10~30건). None은 사고통지만 접수된 상태(이행청구 전).
_BACKGROUND_STAGES: tuple[str | None, ...] = (
    None, None, None,
    "ClaimReceived", "ClaimReceived",
    "SupplementRequested", "SupplementRequested",
    "UnderReview", "UnderReview", "UnderReview",
    "OnHold",
    "Approved", "Approved",
    "HandoverScheduled",
    "HandoverCompleted",
    "SubrogationPaid",
)

# 이행 단계 → 사고통지 상태·계약 상태
_STAGE_INCIDENT_STATUS = {
    None: "Received",
    "ClaimReceived": "Reviewing",
    "SupplementRequested": "Reviewing",
    "UnderReview": "Reviewing",
    "OnHold": "Reviewing",
    "Approved": "Reviewing",
    "HandoverScheduled": "Reviewing",
    "HandoverCompleted": "Reviewing",
    "SubrogationPaid": "Reviewing",
}
_STAGE_CONTRACT_STATUS = {
    "SubrogationPaid": "RecoveryInProgress",
}

# 배경 청구의 단계 이력 사다리(앞에서부터 해당 단계까지 기록).
_STAGE_LADDER: tuple[tuple[str, str | None, str], ...] = (
    ("CLAIM_RECEIVED", None, "ClaimReceived"),
    ("DOCUMENTS_REQUESTED", "ClaimReceived", "SupplementRequested"),
    ("REVIEW_STARTED", "SupplementRequested", "UnderReview"),
    ("CLAIM_APPROVE", "UnderReview", "Approved"),
    ("HANDOVER_SCHEDULED", "Approved", "HandoverScheduled"),
    ("HANDOVER_COMPLETED", "HandoverScheduled", "HandoverCompleted"),
    ("SUBROGATION_PAYMENT_RECORDED", "HandoverCompleted", "SubrogationPaid"),
)
_LADDER_INDEX = {after: index for index, (_a, _b, after) in enumerate(_STAGE_LADDER)}
# OnHold는 UnderReview에서 파생된 보류 상태로 취급한다.
_LADDER_INDEX["OnHold"] = _LADDER_INDEX["UnderReview"]


def load_rtms_rows(
    sample_size: int = SCALE_SAMPLE_SIZE,
) -> tuple[list[dict[str, Any]], str] | None:
    """RTMS 표본 CSV에서 결정론적 표본을 뽑는다. 파일이 없으면 None(시딩 생략)."""
    data_dir = Path(get_settings().data_dir)
    matches = sorted(data_dir.glob("processed/control/rtms_jeonse_controls_*.csv"))
    if not matches:
        return None
    path = matches[-1]
    frame = pd.read_csv(path)
    frame = frame[frame["housing_type"].isin(_HOUSING_TO_ENUM)]
    frame = frame[frame["deposit_amount"] >= 30_000_000]
    if frame.empty:
        return None
    sample = frame.sample(
        n=min(sample_size, len(frame)), random_state=SCALE_SEED
    ).reset_index(drop=True)
    return sample.to_dict("records"), path.name


def _scale_source(source_dataset: str, *, source_type: str, basis: str) -> dict[str, Any]:
    return source_metadata(
        data_mode="DEMO",
        source_type=source_type,
        source_dataset=source_dataset,
        as_of_date=SCALE_AS_OF.isoformat(),
        is_demo=True,
        basis=basis,
    )


# housta 축약 표기 → 도로명 주소식 시군구 표기
_SIGUNGU_EXPANSION = {
    "성남분당": "성남시 분당구",
    "창원성산": "창원시 성산구",
}


def _address_from_row(row: dict[str, Any]) -> str:
    sido = str(row.get("sido") or "").strip()
    region_tokens = str(row.get("region_label") or "").split()
    sigungu = " ".join(region_tokens[1:]) if len(region_tokens) > 1 else ""
    sigungu = _SIGUNGU_EXPANSION.get(sigungu, sigungu)
    umd = str(row.get("umd_nm") or "").strip()
    jibun = row.get("jibun")
    jibun_text = "" if jibun is None or (isinstance(jibun, float) and pd.isna(jibun)) else str(jibun).strip()
    parts = [part for part in (sido, sigungu, umd, jibun_text) if part]
    return " ".join(parts)


def build_scale_documents(
    rows: list[dict[str, Any]],
    *,
    user_ids: dict[str, str],
    source_dataset: str,
) -> dict[str, list[dict[str, Any]]]:
    """표본 행 → 가상 보증계약·배경 이행 사건 문서. DB 접근 없는 결정론적 빌더."""
    contract_basis = (
        "RTMS 전월세 실거래 표본의 분포(시도·주택유형·보증금)를 참조해 생성한 "
        "명시적 가상 보증계약(규모감 시연용). 실존 계약이 아님"
    )
    incident_basis = (
        "발제사 파일에 공통 사건 ID가 없어 사건 단위 실데이터 구성이 불가해 "
        "명시적으로 구성한 가상 배경 이행 사건(규모감 시연용)"
    )
    contract_source = _scale_source(
        source_dataset, source_type="demo_scale_rtms", basis=contract_basis
    )
    incident_source = _scale_source(
        source_dataset, source_type="demo_scale_background", basis=incident_basis
    )

    tenants = (user_ids["tenant91"], user_ids["tenant92"])
    landlords = (user_ids["landlord91"], user_ids["landlord92"])
    hugadmin = user_ids["hugadmin01"]

    # 배경 사건 대상 인덱스: 고정 간격으로 선택해 재실행마다 같은 계약이 뽑힌다.
    background_indices = [
        index for index in range(len(rows)) if index % 9 == 4
    ][: len(_BACKGROUND_STAGES)]
    background_map = {
        contract_index: stage_index
        for stage_index, contract_index in enumerate(background_indices)
    }

    properties: list[dict[str, Any]] = []
    contracts: list[dict[str, Any]] = []
    incidents: list[dict[str, Any]] = []
    claims: list[dict[str, Any]] = []
    claim_events: list[dict[str, Any]] = []

    for index, row in enumerate(rows):
        rid = f"r{index + 1:03d}"
        deposit = int(row["deposit_amount"])
        housing_enum = _HOUSING_TO_ENUM[str(row["housing_type"])]
        # 만기 분포: D+25 ~ D+700을 결정론적으로 순회 — D30/D60/D90 구간에도 일부 배치.
        d_day = 25 + (index * 37) % 676
        end_date = SCALE_AS_OF + timedelta(days=d_day)
        start_date = end_date - timedelta(days=730)
        stage_index = background_map.get(index)
        stage = _BACKGROUND_STAGES[stage_index] if stage_index is not None else "PRE"
        if stage_index is not None:
            contract_status = _STAGE_CONTRACT_STATUS.get(stage, "IncidentReported")
            # 배경 사건 계약은 이미 만기 경과 상태가 자연스럽다.
            end_date = SCALE_AS_OF - timedelta(days=30 + (index % 90))
            start_date = end_date - timedelta(days=730)
        elif index % 47 == 3:
            # §20.5 P4 — 만기 경과·미신고 표본: "만기경과·사고요건 확인" 스테이지 시연 대상.
            contract_status = "Monitoring"
            end_date = SCALE_AS_OF - timedelta(days=5 + (index % 15))
            start_date = end_date - timedelta(days=730)
        else:
            contract_status = "ContractFinalized" if index % 9 == 0 else "Monitoring"

        properties.append(
            {
                "_id": f"demo-prop-{rid}",
                "address": {"road_address": _address_from_row(row), "adm_cd": str(row.get("lawd_cd") or "") or None},
                "housing_type": housing_enum,
                "coordinate": None,
                "source_system": "demo_scale_rtms",
                "source": contract_source,
                "provenance": contract_source,
                "is_demo": True,
                "created_at": _AS_OF_TS,
                "updated_at": _AS_OF_TS,
            }
        )
        contracts.append(
            {
                "_id": f"demo-ct-{rid}",
                "property_id": f"demo-prop-{rid}",
                "tenant_user_id": tenants[index % 2],
                "landlord_user_id": landlords[(index // 2) % 2],
                "landlord_id": None,
                "contract_status": contract_status,
                "deposit": deposit,
                "contract_start_date": start_date.isoformat(),
                "contract_end_date": end_date.isoformat(),
                "product_name": "전세보증금반환보증",
                "landlord_type": "INDIVIDUAL",
                "housing_type": housing_enum,
                "risk_assessment_id": None,
                "source": contract_source,
                "provenance": contract_source,
                "is_demo": True,
                "created_at": _AS_OF_TS,
                "updated_at": _AS_OF_TS,
            }
        )

        if stage_index is None:
            continue

        # --- 배경 이행 사건 ---
        bid = f"b{stage_index + 1:02d}"
        created_at = f"2026-{6 if stage_index % 2 else 7:02d}-{2 + stage_index:02d}T10:00:00+09:00"
        incident_status = _STAGE_INCIDENT_STATUS[_BACKGROUND_STAGES[stage_index]]
        claim_stage = _BACKGROUND_STAGES[stage_index]
        incidents.append(
            {
                "_id": f"demo-inc-{bid}",
                "reporter_user_id": tenants[index % 2],
                "incident_type": "DEPOSIT_NOT_RETURNED",
                "description": "계약 만기 후 보증금 미반환 신고",
                "contract_id": f"demo-ct-{rid}",
                "property_id": f"demo-prop-{rid}",
                "deposit_amount": deposit,
                "occurred_date": end_date.isoformat(),
                "status": incident_status,
                "performance_claim_id": f"demo-perf-{bid}" if claim_stage else None,
                "current_stage": claim_stage or "AccidentNotified",
                "workflow_stage": claim_stage or "AccidentNotified",
                "timeline": [
                    {"status": "Received", "note": "사고통지 접수", "by_role": "tenant", "at": created_at}
                ],
                "source": incident_source,
                "provenance": incident_source,
                "is_demo": True,
                "created_at": created_at,
                "updated_at": _AS_OF_TS,
            }
        )
        if not claim_stage:
            continue

        approved = claim_stage in {
            "Approved", "HandoverScheduled", "HandoverCompleted", "SubrogationPaid"
        }
        paid = claim_stage == "SubrogationPaid"
        # 처리기한 분포: 일부는 임박(D+2~), 일부는 여유 — 기한 임박 목록을 다양화한다.
        sla_due = SCALE_AS_OF + timedelta(days=2 + (stage_index * 5) % 45)
        claims.append(
            {
                "_id": f"demo-perf-{bid}",
                "performance_claim_id": f"demo-perf-{bid}",
                "incident_id": f"demo-inc-{bid}",
                "contract_id": f"demo-ct-{rid}",
                "reporter_user_id": tenants[index % 2],
                "official_accident_type": "CONTRACT_END_NONRETURN",
                "workflow_type": "JEONSE_RETURN_NONRETURN",
                "workflow_version": "JEONSE_RETURN_V1",
                "product_name": "전세보증금반환보증",
                "stage": claim_stage,
                "version": 1,
                "claim_amount": deposit,
                "approved_amount": deposit if approved else None,
                "paid_amount": deposit if paid else None,
                "decision": "Approved" if approved else None,
                "decision_reason": "심사 요건 충족" if approved else None,
                "handover_required": True,
                "moveout_due_at": f"{(SCALE_AS_OF + timedelta(days=20)).isoformat()}T18:00:00+09:00",
                "assignee_user_id": hugadmin,
                "sla_policy_code": "DEMO_INTERNAL_V1",
                "sla_policy_basis": "시연용 내부 목표기한이며 HUG 공식 SLA가 아님",
                "claim_sla_started_at": created_at,
                "claim_sla_due_at": f"{sla_due.isoformat()}T18:00:00+09:00",
                "sla_paused_at": None,
                "sla_pause_reason": None,
                "sla_total_paused_seconds": 0,
                "sla_completed_at": None,
                "recovery_claim_ids": [],
                "stage_entered_at": _AS_OF_TS,
                "source": incident_source,
                "provenance": incident_source,
                "is_demo": True,
                "created_at": created_at,
                "updated_at": _AS_OF_TS,
            }
        )
        ladder_end = _LADDER_INDEX[claim_stage]
        for step_index, (action, before_stage, after_stage) in enumerate(
            _STAGE_LADDER[: ladder_end + 1], start=1
        ):
            claim_events.append(
                {
                    "_id": f"demo-perf-event-{bid}-{step_index}",
                    "performance_claim_id": f"demo-perf-{bid}",
                    "action": action,
                    "before_stage": before_stage,
                    "after_stage": after_stage,
                    "actor_user_id": hugadmin,
                    "actor_role": "hug_admin",
                    "request_id": f"demo-scale:{bid}:{step_index}",
                    "reason": "배경 이행 사건 이력",
                    "metadata": {"background": True},
                    "source": incident_source,
                    "provenance": incident_source,
                    "is_demo": True,
                    "occurred_at": f"2026-07-{2 + step_index:02d}T09:00:00+09:00",
                }
            )

    return {
        "properties": properties,
        "contracts": contracts,
        "incidents": incidents,
        "performance_claims": claims,
        "performance_claim_events": claim_events,
    }

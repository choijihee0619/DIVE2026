"""S1~S7 HUG 업무흐름 시연 데이터를 고정 ID/기준일로 생성한다.

원본 제공 CSV의 행을 사건처럼 임의 연결하지 않는다. 금액과 모델 입력 범위만 참고한
명시적 가상 사건이며, 여러 번 실행해도 같은 문서 상태가 되도록 replace-upsert한다.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.core.exceptions import ResourceNotFoundError
from app.schemas.provenance import source_metadata
from app.services import ml_service
from app.services.recovery_service import recovery_model_metadata

DEMO_AS_OF_DATE = "2026-07-23"
DEMO_AS_OF_TS = "2026-07-23T09:00:00+09:00"
DEMO_TEMPLATE_VERSION = "hug-workflow-v1.1.0"
DEMO_SEED = 260723
MANIFEST_ID = "demo-manifest-hug-workflow-v1-1"

_SCENARIO_LABELS = {
    "S1": "정상 모니터링",
    "S2": "사고 전 고위험·증빙 기한초과",
    "S3": "위험 해소",
    "S4": "보증이행 심사중",
    "S5": "대위변제·채권등록",
    "S6": "경매·부분회수 진행",
    "S7": "전액회수 종결",
}

_MODEL_INPUTS = {
    "S5": {
        "product_name": "전세보증금반환보증",
        "claim_type": "구상채권",
        "claimed_amount": 210_000_000,
        "incurred_amount": 3_000_000,
        "auction_filed_date": date(2026, 5, 2),
        "incurred_date": date(2026, 4, 15),
    },
    "S6": {
        "product_name": "전세보증금반환보증",
        "claim_type": "구상채권(신상품)",
        "claimed_amount": 320_000_000,
        "incurred_amount": 5_000_000,
        "auction_filed_date": date(2025, 10, 14),
        "incurred_date": date(2025, 8, 28),
    },
    "S7": {
        "product_name": "전세보증금반환보증",
        "claim_type": "구상채권",
        "claimed_amount": 180_000_000,
        "incurred_amount": 2_000_000,
        "auction_filed_date": date(2025, 2, 3),
        "incurred_date": date(2024, 12, 20),
    },
}

_CACHED_RESULTS = {
    "S5": {"pred_recovery_ratio": 0.62, "pred_recovery_grade": "MED", "pred_days_to_dividend": 342,
           "expected_recovery_won": 130_200_000, "priority_score": 61.2,
           "priority_weights": {"recovery": 0.6, "speed": 0.4}, "portfolio_size": 28_961,
           "top_factors": [], "basis": ml_service.BASIS_NOTE},
    "S6": {"pred_recovery_ratio": 0.78, "pred_recovery_grade": "MED", "pred_days_to_dividend": 248,
           "expected_recovery_won": 249_600_000, "priority_score": 82.4,
           "priority_weights": {"recovery": 0.6, "speed": 0.4}, "portfolio_size": 28_961,
           "top_factors": [], "basis": ml_service.BASIS_NOTE},
    "S7": {"pred_recovery_ratio": 0.91, "pred_recovery_grade": "HIGH", "pred_days_to_dividend": 190,
           "expected_recovery_won": 163_800_000, "priority_score": 88.7,
           "priority_weights": {"recovery": 0.6, "speed": 0.4}, "portfolio_size": 28_961,
           "top_factors": [], "basis": ml_service.BASIS_NOTE},
}


def _demo_source(scenario_id: str) -> dict[str, Any]:
    return source_metadata(
        data_mode="DEMO",
        source_type="demo_scenario",
        source_dataset=DEMO_TEMPLATE_VERSION,
        as_of_date=DEMO_AS_OF_DATE,
        scenario_id=scenario_id,
        is_demo=True,
        basis="제공 데이터의 범주·분포를 참고해 생성한 명시적 가상 업무 시나리오",
    )


def _with_source(doc: dict[str, Any], scenario_id: str) -> dict[str, Any]:
    source = _demo_source(scenario_id)
    return {
        **doc,
        "scenario_id": scenario_id,
        "source": source,
        "provenance": source,
        "source_type": "demo_scenario",
        "basis": doc.get("basis", source["basis"]),
        "is_demo": True,
    }


def _with_cached_accident_prediction_source(
    doc: dict[str, Any], scenario_id: str
) -> dict[str, Any]:
    source = source_metadata(
        data_mode="DEMO",
        source_type="cached_demo_prediction",
        source_dataset="accident_clf_pu_poc_demo_snapshot",
        as_of_date=DEMO_AS_OF_DATE,
        scenario_id=scenario_id,
        model_version="accident_clf_pu_poc_260723",
        input_snapshot=doc.get("feature_snapshot"),
        is_demo=True,
        basis="PU Learning 사고위험 PoC의 고정 시연 스냅샷. 실제 운영 확률이 아님",
    )
    return {
        **doc,
        "scenario_id": scenario_id,
        "source": source,
        "provenance": source,
        "source_type": "cached_demo_prediction",
        "basis": source["basis"],
        "is_demo": True,
    }


def _prediction_doc(
    scenario_id: str,
    result: dict[str, Any],
    *,
    source_type: str,
    model_meta: dict[str, Any],
    current_balance: int,
) -> dict[str, Any]:
    inp = _MODEL_INPUTS[scenario_id]
    snapshot = {
        "product_name": inp["product_name"],
        "claim_type": inp["claim_type"],
        "claimed_amount": inp["claimed_amount"],
        "claimed_amount_origin": "demo_recovery_claim_register",
        "incurred_amount": inp["incurred_amount"],
        "incurred_amount_origin": "demo_recovery_claim_register",
        "auction_filed_date": inp["auction_filed_date"].isoformat(),
        "auction_filed_date_origin": "demo_recovery_claim_register",
        "incurred_date": inp["incurred_date"].isoformat(),
        "incurred_date_origin": "demo_recovery_claim_register",
    }
    full_result = {
        **result,
        "expected_recovery_on_current_balance_won": int(
            round(float(result["pred_recovery_ratio"]) * current_balance)
        ),
        "current_balance_won": current_balance,
    }
    provenance = source_metadata(
        data_mode="DEMO",
        source_type=source_type,
        source_dataset="provided_synthetic_dividend_training",
        as_of_date=DEMO_AS_OF_DATE,
        scenario_id=scenario_id,
        model_version=model_meta["model_version"],
        input_snapshot=snapshot,
        is_demo=True,
        basis=ml_service.BASIS_NOTE,
    )
    return {
        "_id": f"demo-pred-{scenario_id.lower()}",
        "recovery_claim_id": f"demo-rc-{scenario_id.lower()}",
        "result": full_result,
        "input_snapshot": snapshot,
        "model_version": model_meta["model_version"],
        "artifact_sha256": model_meta["artifact_sha256"],
        "prediction_status": "SUCCESS" if source_type == "model_poc" else "CACHED_DEMO",
        "delta_from_previous": None,
        "previous_prediction_id": None,
        "predicted_by": "demo-hug-admin",
        "predicted_at": DEMO_AS_OF_TS,
        "idempotency_key": f"seed:{DEMO_TEMPLATE_VERSION}:{scenario_id}",
        "provenance": provenance,
        "source_type": source_type,
        "basis": ml_service.BASIS_NOTE,
        "is_demo": True,
        "scenario_id": scenario_id,
    }


def build_demo_documents(
    prediction_results: dict[str, dict[str, Any]] | None = None,
    *,
    prediction_source_type: str = "cached_demo_prediction",
    model_meta: dict[str, Any] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """DB 접근 없는 결정론적 시연 문서 빌더. 테스트와 CLI가 동일 정의를 사용한다."""

    prediction_results = prediction_results or _CACHED_RESULTS
    model_meta = model_meta or {
        "model_version": "recovery_models_20260720",
        "artifact_sha256": {},
    }
    collections: dict[str, list[dict[str, Any]]] = {}

    # S1~S7은 HUG 화면뿐 아니라 임차인·임대인 권한으로도 연결 조회할 수 있어야 한다.
    # bcrypt hash는 공통 데모 비밀번호(P@ssw0rd!)의 고정 시연용 hash다.
    demo_password_hash = (
        "$2b$12$rgeFTzWt4uT4yplflotH3.XoZUxQ.QX3qg0ZT6e5mQFQRdspnTWzW"
    )
    collections["users"] = [
        _with_source(
            {
                "_id": user_id,
                "email": email,
                "password_hash": demo_password_hash,
                "role": role,
                "display_name": display_name,
                "is_active": True,
                "created_at": DEMO_AS_OF_TS,
                "last_login_at": None,
            },
            "S1",
        )
        for user_id, email, role, display_name in (
            ("demo-user-tenant", "workflow.tenant@example.com", "tenant", "업무시연 임차인"),
            ("demo-user-landlord", "workflow.landlord@example.com", "landlord", "업무시연 임대인"),
            ("demo-hug-admin", "workflow.hug@example.com", "hug_admin", "업무시연 HUG 담당자"),
        )
    ]

    properties = []
    contracts = []
    contract_specs = {
        "S1": ("Monitoring", 160_000_000, "2024-11-21", "2026-11-20"),
        "S2": ("AtRisk", 380_000_000, "2024-09-21", "2026-09-20"),
        "S3": ("Monitoring", 270_000_000, "2024-09-30", "2026-09-29"),
        "S4": ("IncidentReported", 250_000_000, "2024-05-01", "2026-04-30"),
        "S5": ("RecoveryInProgress", 210_000_000, "2024-04-16", "2026-04-15"),
        "S6": ("RecoveryInProgress", 320_000_000, "2023-08-29", "2025-08-28"),
        "S7": ("Closed", 180_000_000, "2022-12-21", "2024-12-20"),
    }
    regions = ["서울 강서구", "인천 미추홀구", "부산 남구", "대전 서구", "경기 수원시", "서울 관악구", "인천 부평구"]
    for index, (scenario_id, (status, deposit, start, end)) in enumerate(contract_specs.items()):
        sid = scenario_id.lower()
        properties.append(
            _with_source(
                {
                    "_id": f"demo-prop-{sid}",
                    "address": {"road_address": f"{regions[index]} 시연로 {10 + index}", "adm_cd": None},
                    "housing_type": "MULTI_HOUSEHOLD",
                    "coordinate": None,
                    "source_system": "demo_scenario",
                    "created_at": DEMO_AS_OF_TS,
                    "updated_at": DEMO_AS_OF_TS,
                },
                scenario_id,
            )
        )
        contracts.append(
            _with_source(
                {
                    "_id": f"demo-ct-{sid}",
                    "property_id": f"demo-prop-{sid}",
                    "tenant_user_id": "demo-user-tenant",
                    "landlord_user_id": "demo-user-landlord",
                    "landlord_id": None,
                    "contract_status": status,
                    "deposit": deposit,
                    "contract_start_date": start,
                    "contract_end_date": end,
                    "product_name": "전세보증금반환보증",
                    "landlord_type": "INDIVIDUAL",
                    "housing_type": "MULTI_HOUSEHOLD",
                    "risk_assessment_id": None,
                    "created_at": DEMO_AS_OF_TS,
                    "updated_at": DEMO_AS_OF_TS,
                },
                scenario_id,
            )
        )
    collections["properties"] = properties
    collections["contracts"] = contracts

    collections["accident_predictions"] = [
        _with_cached_accident_prediction_source({"_id": "demo-ap-s1", "prediction_id": "demo-ap-s1", "contract_id": "demo-ct-s1",
                      "pu_risk_score": 0.12, "risk_percentile": 0.18, "accident_probability": 0.12,
                      "calibration_status": "AGGREGATE_PRIOR_ALIGNED_UNVALIDATED",
                      "prediction_status": "SUCCESS", "model_version": "accident_clf_pu_poc_260723",
                      "model_sha256": "demo-seed-model-reference", "feature_fingerprint": "demo-s1-fixed",
                      "feature_snapshot": {"sido": "서울", "housing_type": "다가구주택", "deposit": 160_000_000},
                      "top_factors": [], "failure_reason": [], "data_completeness": 1.0,
                      "predicted_at": DEMO_AS_OF_TS, "valid_until": "2026-08-22T09:00:00+09:00"}, "S1"),
        _with_cached_accident_prediction_source({"_id": "demo-ap-s2", "prediction_id": "demo-ap-s2", "contract_id": "demo-ct-s2",
                      "pu_risk_score": 0.87, "risk_percentile": 0.97, "accident_probability": 0.87,
                      "calibration_status": "AGGREGATE_PRIOR_ALIGNED_UNVALIDATED",
                      "prediction_status": "SUCCESS", "model_version": "accident_clf_pu_poc_260723",
                      "model_sha256": "demo-seed-model-reference", "feature_fingerprint": "demo-s2-fixed",
                      "feature_snapshot": {"sido": "인천", "housing_type": "다가구주택", "deposit": 380_000_000},
                      "top_factors": [], "failure_reason": [], "data_completeness": 1.0,
                      "predicted_at": DEMO_AS_OF_TS, "valid_until": "2026-08-22T09:00:00+09:00"}, "S2"),
        _with_cached_accident_prediction_source({"_id": "demo-ap-s3", "prediction_id": "demo-ap-s3", "contract_id": "demo-ct-s3",
                      "pu_risk_score": 0.74, "risk_percentile": 0.91, "accident_probability": 0.74,
                      "calibration_status": "AGGREGATE_PRIOR_ALIGNED_UNVALIDATED",
                      "prediction_status": "SUCCESS", "model_version": "accident_clf_pu_poc_260723",
                      "model_sha256": "demo-seed-model-reference", "feature_fingerprint": "demo-s3-fixed",
                      "feature_snapshot": {"sido": "부산", "housing_type": "다가구주택", "deposit": 270_000_000},
                      "top_factors": [], "failure_reason": [], "data_completeness": 1.0,
                      "predicted_at": "2026-07-01T09:00:00+09:00", "valid_until": "2026-07-31T09:00:00+09:00"}, "S3"),
    ]
    collections["prevention_cases"] = [
        _with_source({"_id": "demo-pc-s2", "prevention_case_id": "demo-pc-s2", "contract_id": "demo-ct-s2",
                      "status": "Overdue",
                      "triggers": [{"code": "HIGH_POC_PERCENTILE", "severity": "high", "reason": "PoC 상대위험 상위 3%"},
                                   {"code": "EVIDENCE_OVERDUE", "severity": "critical", "checkpoint": "D90",
                                    "reason": "D90 필수 증빙 2개 기한초과"}],
                      "priority_score": 94.0,
                      "priority_components": {"risk_percentile": 48.5, "deposit_exposure": 20.0,
                                              "maturity_urgency": 12.0, "unresolved_actions": 13.5},
                      "owner_user_id": "demo-hug-admin", "owner_center": "인천관리센터",
                      "next_action": "기한초과 증빙 확인 및 임차인 권리보전 상담",
                      "due_at": "2026-07-22T18:00:00+09:00", "policy_version": "prevention-demo-v1",
                      "created_at": "2026-07-10T09:00:00+09:00", "updated_at": DEMO_AS_OF_TS}, "S2"),
        _with_source({"_id": "demo-pc-s3", "prevention_case_id": "demo-pc-s3", "contract_id": "demo-ct-s3",
                      "status": "Mitigated", "triggers": [], "priority_score": 22.0,
                      "priority_components": {"risk_percentile": 10.0, "deposit_exposure": 7.0,
                                              "maturity_urgency": 5.0, "unresolved_actions": 0.0},
                      "owner_user_id": "demo-hug-admin", "owner_center": "부산관리센터",
                      "next_action": "정상 모니터링", "due_at": None, "policy_version": "prevention-demo-v1",
                      "mitigated_at": "2026-07-14T15:00:00+09:00", "created_at": "2026-07-01T09:00:00+09:00",
                      "updated_at": "2026-07-14T15:00:00+09:00"}, "S3"),
    ]
    collections["preventive_actions"] = [
        _with_source({"_id": "demo-pa-s2", "action_id": "demo-pa-s2", "prevention_case_id": "demo-pc-s2",
                      "contract_id": "demo-ct-s2", "action_type": "EVIDENCE_REQUEST",
                      "actor_role": "hug_admin", "actor_user_id": "demo-hug-admin", "target_role": "landlord",
                      "status": "Overdue", "requested_at": "2026-07-10T09:00:00+09:00",
                      "due_at": "2026-07-22T18:00:00+09:00",
                      "completed_at": None, "note": "D90 필수 증빙 제출 요청", "details": {"checkpoint": "D90"},
                      "dedupe_key": "demo-action-s2-evidence", "audit_log": [{"from": None, "to": "Overdue",
                      "actor_user_id": "demo-hug-admin", "at": DEMO_AS_OF_TS}], "updated_at": DEMO_AS_OF_TS}, "S2"),
        _with_source({"_id": "demo-pa-s3", "action_id": "demo-pa-s3", "prevention_case_id": "demo-pc-s3",
                      "contract_id": "demo-ct-s3", "action_type": "CREDIT_ENHANCEMENT_REQUEST",
                      "actor_role": "landlord", "actor_user_id": "demo-user-landlord", "target_role": "landlord",
                      "status": "Completed",
                      "requested_at": "2026-07-01T09:00:00+09:00", "due_at": "2026-07-15T18:00:00+09:00",
                      "completed_at": "2026-07-14T14:30:00+09:00", "note": "근저당 감액 증빙 검증 완료",
                      "details": {"mitigation": "mortgage_reduction"}, "dedupe_key": "demo-action-s3-credit",
                      "audit_log": [{"from": "Verifying", "to": "Completed", "actor_user_id": "demo-hug-admin",
                      "at": "2026-07-14T14:30:00+09:00"}], "updated_at": "2026-07-14T14:30:00+09:00"}, "S3"),
    ]
    collections["evidence_bundles"] = [
        _with_source({"_id": "demo-eb-s2-d90", "contract_id": "demo-ct-s2", "checkpoint": "D90",
                      "sequence": 1, "policy_version": "prevention-demo-v1", "status": "Overdue",
                      "due_at": "2026-07-22T18:00:00+09:00", "required_count": 3, "submitted_count": 2,
                      "verified_count": 1, "overdue_count": 2, "completion_ratio": 0.3333,
                      "items": [{"item_key": "return_plan", "label": "임대인 반환계획",
                                 "evidence_type": "RETURN_PLAN_DOCUMENT", "evidence_request_id": "demo-er-s2-return-plan",
                                 "verification_status": "Pending", "due_at": "2026-07-22T18:00:00+09:00",
                                 "is_verified": False, "is_overdue": True},
                                {"item_key": "latest_registry", "label": "최신 등기상태",
                                 "evidence_type": "LATEST_REGISTRY_SNAPSHOT", "evidence_request_id": "demo-er-s2-registry",
                                 "verification_status": "Submitted", "due_at": "2026-07-22T18:00:00+09:00",
                                 "is_verified": False, "is_overdue": True},
                                {"item_key": "guarantee_status", "label": "보증 유효상태",
                                 "evidence_type": "GUARANTEE_STATUS_PROOF", "evidence_request_id": "demo-er-s2-guarantee",
                                 "verification_status": "Verified", "due_at": "2026-07-22T18:00:00+09:00",
                                 "is_verified": True, "is_overdue": False}],
                      "created_at": "2026-06-22T09:00:00+09:00", "updated_at": DEMO_AS_OF_TS}, "S2"),
        _with_source({"_id": "demo-eb-s2-d60", "contract_id": "demo-ct-s2", "checkpoint": "D60",
                      "sequence": 2, "policy_version": "prevention-demo-v1", "status": "Pending",
                      "due_at": "2026-08-21T18:00:00+09:00", "required_count": 3, "submitted_count": 0,
                      "verified_count": 0, "overdue_count": 0, "completion_ratio": 0.0,
                      "items": [{"item_key": "return_funds", "label": "반환재원 증빙",
                                 "evidence_type": "RETURN_FUNDS_PROOF", "evidence_request_id": "demo-er-s2-return-funds",
                                 "verification_status": "Pending", "due_at": "2026-08-21T18:00:00+09:00",
                                 "is_verified": False, "is_overdue": False},
                                {"item_key": "credit_enhancement", "label": "신용보강 증빙",
                                 "evidence_type": "CREDIT_ENHANCEMENT_PROOF", "evidence_request_id": "demo-er-s2-credit",
                                 "verification_status": "Pending", "due_at": "2026-08-21T18:00:00+09:00",
                                 "is_verified": False, "is_overdue": False},
                                {"item_key": "rights_change", "label": "근저당·압류 변동 점검",
                                 "evidence_type": "RIGHTS_CHANGE_CHECK", "evidence_request_id": "demo-er-s2-rights",
                                 "verification_status": "Pending", "due_at": "2026-08-21T18:00:00+09:00",
                                 "is_verified": False, "is_overdue": False}],
                      "created_at": "2026-07-22T09:00:00+09:00", "updated_at": DEMO_AS_OF_TS}, "S2"),
        _with_source({"_id": "demo-eb-s3-d90", "contract_id": "demo-ct-s3", "checkpoint": "D90",
                      "sequence": 1, "policy_version": "prevention-demo-v1", "status": "Completed",
                      "due_at": "2026-07-31T18:00:00+09:00", "required_count": 3, "submitted_count": 3,
                      "verified_count": 3, "overdue_count": 0, "completion_ratio": 1.0,
                      "items": [{"item_key": "return_plan", "label": "임대인 반환계획",
                                 "evidence_type": "RETURN_PLAN_DOCUMENT", "evidence_request_id": "demo-er-s3-return-plan",
                                 "verification_status": "Verified", "due_at": "2026-07-31T18:00:00+09:00",
                                 "is_verified": True, "is_overdue": False},
                                {"item_key": "latest_registry", "label": "최신 등기상태",
                                 "evidence_type": "LATEST_REGISTRY_SNAPSHOT", "evidence_request_id": "demo-er-s3-registry",
                                 "verification_status": "Verified", "due_at": "2026-07-31T18:00:00+09:00",
                                 "is_verified": True, "is_overdue": False},
                                {"item_key": "guarantee_status", "label": "보증 유효상태",
                                 "evidence_type": "GUARANTEE_STATUS_PROOF", "evidence_request_id": "demo-er-s3-guarantee",
                                 "verification_status": "Verified", "due_at": "2026-07-31T18:00:00+09:00",
                                 "is_verified": True, "is_overdue": False}],
                      "created_at": "2026-07-01T09:00:00+09:00", "updated_at": "2026-07-14T15:00:00+09:00"}, "S3"),
    ]

    evidence_request_specs = (
        ("S2", "demo-er-s2-return-plan", "demo-ct-s2", "demo-eb-s2-d90", "D90", "return_plan",
         "RETURN_PLAN_DOCUMENT", "임대인 반환계획 확인", "2026-07-22", "Pending"),
        ("S2", "demo-er-s2-registry", "demo-ct-s2", "demo-eb-s2-d90", "D90", "latest_registry",
         "LATEST_REGISTRY_SNAPSHOT", "최신 등기상태 확인", "2026-07-22", "Submitted"),
        ("S2", "demo-er-s2-guarantee", "demo-ct-s2", "demo-eb-s2-d90", "D90", "guarantee_status",
         "GUARANTEE_STATUS_PROOF", "보증 유효상태 확인", "2026-07-22", "Verified"),
        ("S2", "demo-er-s2-return-funds", "demo-ct-s2", "demo-eb-s2-d60", "D60", "return_funds",
         "RETURN_FUNDS_PROOF", "반환재원 증빙 제출 요청", "2026-08-21", "Pending"),
        ("S2", "demo-er-s2-credit", "demo-ct-s2", "demo-eb-s2-d60", "D60", "credit_enhancement",
         "CREDIT_ENHANCEMENT_PROOF", "신용보강 증빙 제출 요청", "2026-08-21", "Pending"),
        ("S2", "demo-er-s2-rights", "demo-ct-s2", "demo-eb-s2-d60", "D60", "rights_change",
         "RIGHTS_CHANGE_CHECK", "근저당·압류 변동 확인", "2026-08-21", "Pending"),
        ("S3", "demo-er-s3-return-plan", "demo-ct-s3", "demo-eb-s3-d90", "D90", "return_plan",
         "RETURN_PLAN_DOCUMENT", "임대인 반환계획 확인", "2026-07-31", "Verified"),
        ("S3", "demo-er-s3-registry", "demo-ct-s3", "demo-eb-s3-d90", "D90", "latest_registry",
         "LATEST_REGISTRY_SNAPSHOT", "최신 등기상태 확인", "2026-07-31", "Verified"),
        ("S3", "demo-er-s3-guarantee", "demo-ct-s3", "demo-eb-s3-d90", "D90", "guarantee_status",
         "GUARANTEE_STATUS_PROOF", "보증 유효상태 확인", "2026-07-31", "Verified"),
    )
    collections["evidence_requests"] = [
        _with_source(
            {
                "_id": request_id,
                "contract_id": contract_id,
                "risk_assessment_id": None,
                "reason": reason,
                "evidence_type": evidence_type,
                "due_date": due_date,
                "verification_status": status,
                "latest_evidence_id": None if status == "Pending" else f"demo-evidence-{request_id[8:]}",
                "bundle_id": bundle_id,
                "item_key": item_key,
                "checkpoint": checkpoint,
                "created_at": "2026-07-01T09:00:00+09:00",
                "updated_at": "2026-07-14T15:00:00+09:00" if status == "Verified" else DEMO_AS_OF_TS,
            },
            scenario_id,
        )
        for (scenario_id, request_id, contract_id, bundle_id, checkpoint, item_key, evidence_type,
             reason, due_date, status) in evidence_request_specs
    ]

    submitted_evidence_specs = [spec for spec in evidence_request_specs if spec[-1] != "Pending"]
    collections["evidences"] = [
        _with_source(
            {
                "_id": f"demo-evidence-{request_id[8:]}",
                "evidence_request_id": request_id,
                "uploader_id": "demo-user-landlord",
                "file_name": f"{item_key}.pdf",
                "content_type": "application/pdf",
                "size_bytes": 1024,
                "object_uri": f"demo://evidence/{request_id}.pdf",
                "document_hash": hashlib.sha256(request_id.encode("utf-8")).hexdigest(),
                "verification_status": status,
                "submitted_at": "2026-07-13T14:00:00+09:00",
            },
            scenario_id,
        )
        for (scenario_id, request_id, _contract_id, _bundle_id, _checkpoint, item_key, _evidence_type,
             _reason, _due_date, status) in submitted_evidence_specs
    ]
    verified_evidence_specs = [spec for spec in evidence_request_specs if spec[-1] == "Verified"]
    collections["verifications"] = [
        _with_source(
            {
                "_id": f"demo-verification-{request_id[8:]}",
                "evidence_id": f"demo-evidence-{request_id[8:]}",
                "evidence_request_id": request_id,
                "verification_status": "Verified",
                "reviewer_user_id": "demo-hug-admin",
                "reviewer_comment": "시연 시나리오 검증 완료",
                "resubmission_required": False,
                "blockchain_tx_id": None,
                "decided_at": "2026-07-14T15:00:00+09:00",
                "created_at": "2026-07-14T15:00:00+09:00",
            },
            scenario_id,
        )
        for (scenario_id, request_id, _contract_id, _bundle_id, _checkpoint, _item_key, _evidence_type,
             _reason, _due_date, _status) in verified_evidence_specs
    ]

    incidents = []
    performance_claims = []
    performance_stages = {"S4": "UnderReview", "S5": "RecoveryClaimRegistered", "S6": "TransferredToRecovery", "S7": "TransferredToRecovery"}
    incident_statuses = {"S4": "Reviewing", "S5": "TransferredToRecovery", "S6": "TransferredToRecovery", "S7": "Closed"}
    for scenario_id in ("S4", "S5", "S6", "S7"):
        sid = scenario_id.lower()
        spec = contract_specs[scenario_id]
        incidents.append(
            _with_source(
                {"_id": f"demo-inc-{sid}", "reporter_user_id": "demo-user-tenant",
                 "incident_type": "DEPOSIT_NOT_RETURNED", "description": f"{_SCENARIO_LABELS[scenario_id]} 시연용 보증금 미반환 신고",
                 "contract_id": f"demo-ct-{sid}", "property_id": f"demo-prop-{sid}", "deposit_amount": spec[1],
                 "occurred_date": spec[3], "status": incident_statuses[scenario_id],
                 "performance_claim_id": f"demo-perf-{sid}",
                 "current_stage": performance_stages[scenario_id],
                 "workflow_stage": performance_stages[scenario_id],
                 "timeline": [{"status": "Received", "note": "시연 사고통지", "by_role": "tenant", "at": "2026-05-01T09:00:00+09:00"}],
                 "created_at": "2026-05-01T09:00:00+09:00", "updated_at": DEMO_AS_OF_TS},
                scenario_id,
            )
        )
        performance_claims.append(
            _with_source(
                {"_id": f"demo-perf-{sid}", "performance_claim_id": f"demo-perf-{sid}",
                 "incident_id": f"demo-inc-{sid}", "contract_id": f"demo-ct-{sid}",
                 "reporter_user_id": "demo-user-tenant",
                 "official_accident_type": "CONTRACT_END_NONRETURN",
                 "workflow_type": "JEONSE_RETURN_NONRETURN",
                 "workflow_version": "JEONSE_RETURN_V1",
                 "product_name": "전세보증금반환보증",
                 "stage": performance_stages[scenario_id], "version": 1,
                 "claim_amount": spec[1], "approved_amount": spec[1] if scenario_id != "S4" else None,
                 "paid_amount": spec[1] if scenario_id in {"S5", "S6", "S7"} else None,
                 "decision": "Approved" if scenario_id != "S4" else None,
                 "decision_reason": "시연 승인" if scenario_id != "S4" else None,
                 "handover_required": True, "moveout_due_at": "2026-05-30T18:00:00+09:00",
                 "assignee_user_id": "demo-hug-admin",
                 "sla_policy_code": "DEMO_INTERNAL_V1",
                 "sla_policy_basis": "시연용 내부 목표기한이며 HUG 공식 SLA가 아님",
                 "claim_sla_started_at": "2026-05-02T09:00:00+09:00",
                 "claim_sla_due_at": "2026-07-30T18:00:00+09:00",
                 "sla_paused_at": None, "sla_pause_reason": None, "sla_total_paused_seconds": 0,
                 "sla_completed_at": DEMO_AS_OF_TS if scenario_id != "S4" else None,
                 "recovery_claim_ids": [f"demo-rc-{sid}"] if scenario_id in {"S5", "S6", "S7"} else [],
                 "stage_entered_at": DEMO_AS_OF_TS,
                 "created_at": "2026-05-02T09:00:00+09:00", "updated_at": DEMO_AS_OF_TS},
                scenario_id,
            )
        )
    collections["incidents"] = incidents
    collections["performance_claims"] = performance_claims

    claim_document_types = {
        "S4": ("CONTRACT_DOCUMENT", "CONTRACT_TERMINATION_PROOF", "TENANT_RIGHTS_PROOF"),
        "S5": ("CONTRACT_DOCUMENT", "CONTRACT_TERMINATION_PROOF", "TENANT_RIGHTS_PROOF", "HANDOVER_PROOF"),
        "S6": ("CONTRACT_DOCUMENT", "CONTRACT_TERMINATION_PROOF", "TENANT_RIGHTS_PROOF", "HANDOVER_PROOF"),
        "S7": ("CONTRACT_DOCUMENT", "CONTRACT_TERMINATION_PROOF", "TENANT_RIGHTS_PROOF", "HANDOVER_PROOF"),
    }
    claim_documents: list[dict[str, Any]] = []
    for scenario_id, document_types in claim_document_types.items():
        sid = scenario_id.lower()
        for index, document_type in enumerate(document_types, start=1):
            document_id = f"demo-claim-doc-{sid}-{index}"
            submitted_at = f"2026-05-{2 + index:02d}T10:00:00+09:00"
            verified_at = f"2026-05-{2 + index:02d}T15:00:00+09:00"
            claim_documents.append(
                _with_source(
                    {
                        "_id": document_id,
                        "performance_claim_id": f"demo-perf-{sid}",
                        "document_type": document_type,
                        "required": True,
                        "request_reason": "보증이행 심사 필수서류",
                        "due_at": "2026-05-20T18:00:00+09:00",
                        "verification_status": "Verified",
                        "version": 3,
                        "submissions": [
                            {
                                "submission_id": f"demo-submission-{sid}-{index}",
                                "file_name": f"{document_type.lower()}.pdf",
                                "document_hash": hashlib.sha256(document_id.encode("utf-8")).hexdigest(),
                                "object_uri": f"demo://performance-claim/{document_id}.pdf",
                                "note": "시연용 제출 문서",
                                "submitter_user_id": "demo-user-tenant",
                                "submitted_at": submitted_at,
                            }
                        ],
                        "requested_by_user_id": "demo-hug-admin",
                        "requested_at": "2026-05-02T09:00:00+09:00",
                        "submitted_at": submitted_at,
                        "submitter_user_id": "demo-user-tenant",
                        "verified_at": verified_at,
                        "reviewer_user_id": "demo-hug-admin",
                        "review_reason": "필수서류 진위 및 요건 확인 완료",
                        "updated_at": verified_at,
                    },
                    scenario_id,
                )
            )
    collections["claim_documents"] = claim_documents

    collections["subrogation_payments"] = [
        _with_source(
            {
                "_id": f"demo-payment-{scenario_id.lower()}",
                "performance_claim_id": f"demo-perf-{scenario_id.lower()}",
                "payment_reference": f"DEMO-PAY-{scenario_id}-260531",
                "paid_amount": contract_specs[scenario_id][1],
                "paid_at": "2026-05-31",
                "recorded_by_user_id": "demo-hug-admin",
                "reason": "시연 시나리오 대위변제 완료",
                "created_at": "2026-05-31T14:00:00+09:00",
            },
            scenario_id,
        )
        for scenario_id in ("S5", "S6", "S7")
    ]

    performance_event_paths = {
        "S4": (
            ("CLAIM_RECEIVED", None, "ClaimReceived"),
            ("DOCUMENTS_REQUESTED", "ClaimReceived", "SupplementRequested"),
            ("REVIEW_STARTED", "SupplementRequested", "UnderReview"),
        ),
        "S5": (
            ("CLAIM_RECEIVED", None, "ClaimReceived"),
            ("DOCUMENTS_REQUESTED", "ClaimReceived", "SupplementRequested"),
            ("REVIEW_STARTED", "SupplementRequested", "UnderReview"),
            ("CLAIM_APPROVE", "UnderReview", "Approved"),
            ("HANDOVER_SCHEDULED", "Approved", "HandoverScheduled"),
            ("HANDOVER_COMPLETED", "HandoverScheduled", "HandoverCompleted"),
            ("SUBROGATION_PAYMENT_RECORDED", "HandoverCompleted", "SubrogationPaid"),
            ("RECOVERY_CLAIM_REGISTERED", "SubrogationPaid", "RecoveryClaimRegistered"),
        ),
        "S6": (
            ("CLAIM_RECEIVED", None, "ClaimReceived"),
            ("DOCUMENTS_REQUESTED", "ClaimReceived", "SupplementRequested"),
            ("REVIEW_STARTED", "SupplementRequested", "UnderReview"),
            ("CLAIM_APPROVE", "UnderReview", "Approved"),
            ("HANDOVER_SCHEDULED", "Approved", "HandoverScheduled"),
            ("HANDOVER_COMPLETED", "HandoverScheduled", "HandoverCompleted"),
            ("SUBROGATION_PAYMENT_RECORDED", "HandoverCompleted", "SubrogationPaid"),
            ("RECOVERY_CLAIM_REGISTERED", "SubrogationPaid", "RecoveryClaimRegistered"),
            ("TRANSFERRED_TO_RECOVERY", "RecoveryClaimRegistered", "TransferredToRecovery"),
        ),
        "S7": (
            ("CLAIM_RECEIVED", None, "ClaimReceived"),
            ("DOCUMENTS_REQUESTED", "ClaimReceived", "SupplementRequested"),
            ("REVIEW_STARTED", "SupplementRequested", "UnderReview"),
            ("CLAIM_APPROVE", "UnderReview", "Approved"),
            ("HANDOVER_SCHEDULED", "Approved", "HandoverScheduled"),
            ("HANDOVER_COMPLETED", "HandoverScheduled", "HandoverCompleted"),
            ("SUBROGATION_PAYMENT_RECORDED", "HandoverCompleted", "SubrogationPaid"),
            ("RECOVERY_CLAIM_REGISTERED", "SubrogationPaid", "RecoveryClaimRegistered"),
            ("TRANSFERRED_TO_RECOVERY", "RecoveryClaimRegistered", "TransferredToRecovery"),
        ),
    }
    performance_events: list[dict[str, Any]] = []
    for scenario_id, path in performance_event_paths.items():
        sid = scenario_id.lower()
        for index, (action, before_stage, after_stage) in enumerate(path, start=1):
            performance_events.append(
                _with_source(
                    {
                        "_id": f"demo-perf-event-{sid}-{index}",
                        "performance_claim_id": f"demo-perf-{sid}",
                        "action": action,
                        "before_stage": before_stage,
                        "after_stage": after_stage,
                        "actor_user_id": "demo-hug-admin",
                        "actor_role": "hug_admin",
                        "request_id": f"demo:{scenario_id}:{index}",
                        "reason": f"{_SCENARIO_LABELS[scenario_id]} 시연 이력",
                        "metadata": {"scenario_id": scenario_id},
                        "occurred_at": f"2026-05-{index + 1:02d}T09:00:00+09:00",
                    },
                    scenario_id,
                )
            )
    collections["performance_claim_events"] = performance_events

    prevention_notification_specs = (
        ("demo-notification-s2-tenant", "demo-user-tenant", "tenant",
         "보증금 미반환 위험신호가 감지되었습니다", "임차인 권리보전 안내와 필수 확인사항을 확인하세요."),
        ("demo-notification-s2-landlord", "demo-user-landlord", "landlord",
         "보증금 반환 증빙 기한이 지났습니다", "반환재원 및 신용보강 증빙을 즉시 제출해 주세요."),
        ("demo-notification-s2-hug", "demo-hug-admin", "hug_admin",
         "고위험 계약 사전조치가 필요합니다", "D90 증빙 기한초과 계약을 확인하고 후속조치를 기록하세요."),
    )
    collections["notifications"] = [
        _with_source(
            {
                "_id": notification_id,
                "user_id": user_id,
                "category": "prevention_alert",
                "title": title,
                "body": body,
                "severity": "critical",
                "link": "/hug/contracts/demo-ct-s2/prevention",
                "is_read": False,
                "contract_id": "demo-ct-s2",
                "prevention_case_id": "demo-pc-s2",
                "action_id": "demo-pa-s2",
                "trigger_code": "EVIDENCE_OVERDUE",
                "target_role": target_role,
                "due_at": "2026-07-22T18:00:00+09:00",
                "delivery_status": "delivered",
                "delivered_at": DEMO_AS_OF_TS,
                "read_at": None,
                "acknowledged_at": None,
                "metadata": {"checkpoint": "D90", "scenario_id": "S2"},
                "dedupe_key": f"demo-s2-evidence-overdue:{target_role}",
                "created_at": DEMO_AS_OF_TS,
            },
            "S2",
        )
        for notification_id, user_id, target_role, title, body in prevention_notification_specs
    ]

    current_balances = {"S5": 210_000_000, "S6": 223_000_000, "S7": 0}
    recovery_claims = []
    claim_specs = {
        "S5": ("RECOURSE_STANDARD", 210_000_000, {"principal": 210_000_000, "legal_cost": 0, "delay_damage": 0, "enforcement_cost": 0, "total": 210_000_000}, "Registered", "Voluntary", False),
        "S6": ("RECOURSE_NEW_PRODUCT", 320_000_000, {"principal": 220_000_000, "legal_cost": 3_000_000, "delay_damage": 0, "enforcement_cost": 0, "total": 223_000_000}, "Collection", "Auction", False),
        "S7": ("RECOURSE_STANDARD", 180_000_000, {"principal": 0, "legal_cost": 0, "delay_damage": 0, "enforcement_cost": 0, "total": 0}, "Closing", "Auction", True),
    }
    prediction_docs = []
    for scenario_id, (claim_type, principal, balances, stage, route, closed) in claim_specs.items():
        sid = scenario_id.lower()
        pred = _prediction_doc(
            scenario_id,
            prediction_results[scenario_id],
            source_type=prediction_source_type,
            model_meta=model_meta,
            current_balance=current_balances[scenario_id],
        )
        prediction_docs.append(pred)
        closure = None
        if closed:
            closure = {"reason": "FULL_RECOVERY", "note": "시연 전액회수", "residual_balance_won": 0,
                       "closed_by": "demo-hug-admin", "closed_by_role": "hug_admin",
                       "closed_at": "2026-07-10T16:00:00+09:00", "idempotency_key": "seed-close-s7"}
        claim = _with_source(
            {"_id": f"demo-rc-{sid}", "performance_claim_id": f"demo-perf-{sid}", "contract_id": f"demo-ct-{sid}",
             "product_name": "전세보증금반환보증", "claim_type": claim_type, "principal": principal,
             "balance": balances["total"], "balances": balances, "recovered_total": principal - balances["principal"],
             "incurred_amount": _MODEL_INPUTS[scenario_id]["incurred_amount"],
             "incurred_date": _MODEL_INPUTS[scenario_id]["incurred_date"].isoformat(),
             "auction_filed_date": _MODEL_INPUTS[scenario_id]["auction_filed_date"].isoformat(),
             "stage": "Registered", "recovery_stage": stage, "collection_route": route, "legal_status": "None",
             "auction_status": "InProgress" if scenario_id == "S6" else ("Distributed" if scenario_id == "S7" else "Filed"),
             "repayment_plan_status": "None",
             "balance_status": "FullyRecovered" if closed else ("PartiallyRecovered" if scenario_id == "S6" else "Unrecovered"),
             "axis_status": {"recovery_stage": stage, "collection_route": route, "legal_status": "None",
                             "auction_status": "InProgress" if scenario_id == "S6" else ("Distributed" if scenario_id == "S7" else "Filed"),
                             "repayment_plan_status": "None",
                             "balance_status": "FullyRecovered" if closed else ("PartiallyRecovered" if scenario_id == "S6" else "Unrecovered")},
             "latest_prediction_id": pred["_id"], "latest_prediction": pred["result"],
             "pred_recovery_ratio": pred["result"]["pred_recovery_ratio"],
             "pred_recovery_grade": pred["result"]["pred_recovery_grade"],
             "pred_days_to_dividend": pred["result"]["pred_days_to_dividend"],
             "expected_recovery_won": pred["result"]["expected_recovery_on_current_balance_won"],
             "priority_score": pred["result"].get("priority_score"), "is_closed": closed, "closure": closure,
             "closed_at": closure["closed_at"] if closure else None, "version": 1,
             "created_at": "2026-06-01T09:00:00+09:00", "updated_at": DEMO_AS_OF_TS},
            scenario_id,
        )
        recovery_claims.append(claim)
    collections["recovery_claims"] = recovery_claims
    collections["recovery_predictions"] = prediction_docs

    events = []
    for scenario_id in ("S5", "S6", "S7"):
        sid = scenario_id.lower()
        events.append(_with_source({"_id": f"demo-rce-{sid}-registered", "recovery_claim_id": f"demo-rc-{sid}",
                                    "event_type": "RecoveryClaimRegistered", "status_axis": "recovery_stage",
                                    "before": None, "after": "Registered", "note": "구상채권 등록",
                                    "actor_user_id": "demo-hug-admin", "actor_role": "hug_admin",
                                    "occurred_at": "2026-06-01T09:00:00+09:00", "idempotency_key": f"seed-register-{sid}"}, scenario_id))
    events.extend([
        _with_source({"_id": "demo-rce-s6-auction", "recovery_claim_id": "demo-rc-s6", "event_type": "AuctionProgressed",
                      "status_axis": "auction_status", "before": "Filed", "after": "InProgress", "note": "경매 진행",
                      "actor_user_id": "demo-hug-admin", "actor_role": "hug_admin", "occurred_at": "2026-06-15T09:00:00+09:00",
                      "idempotency_key": "seed-auction-s6"}, "S6"),
        _with_source({"_id": "demo-rce-s7-close", "recovery_claim_id": "demo-rc-s7", "event_type": "RecoveryClaimClosed",
                      "status_axis": "recovery_stage", "before": "Distribution", "after": "Closing", "note": "전액회수 종결",
                      "actor_user_id": "demo-hug-admin", "actor_role": "hug_admin", "occurred_at": "2026-07-10T16:00:00+09:00",
                      "idempotency_key": "seed-close-s7"}, "S7"),
    ])
    collections["recovery_events"] = events

    def ledger(scenario_id: str, suffix: str, entry_type: str, direction: str, amount: int, allocations: dict[str, int],
               before: dict[str, int], after: dict[str, int], occurred_at: str) -> dict[str, Any]:
        sid = scenario_id.lower()
        return _with_source({"_id": f"demo-rcl-{sid}-{suffix}", "recovery_claim_id": f"demo-rc-{sid}",
                             "entry_type": entry_type, "direction": direction, "amount_won": amount,
                             "allocations": allocations, "allocation_policy": "EXPLICIT_MANUAL_POC",
                             "balance_before": before, "balance_after": after, "note": "시연 고정 원장",
                             "reference_type": "DEMO_SEED", "reference_id": f"{scenario_id}-{suffix}",
                             "actor_user_id": "demo-hug-admin", "actor_role": "hug_admin", "occurred_at": occurred_at,
                             "idempotency_key": f"seed-ledger-{sid}-{suffix}"}, scenario_id)

    z = {"principal": 0, "legal_cost": 0, "delay_damage": 0, "enforcement_cost": 0, "total": 0}
    s5 = {"principal": 210_000_000, "legal_cost": 0, "delay_damage": 0, "enforcement_cost": 0, "total": 210_000_000}
    s6p = {"principal": 320_000_000, "legal_cost": 0, "delay_damage": 0, "enforcement_cost": 0, "total": 320_000_000}
    s6c = {"principal": 320_000_000, "legal_cost": 3_000_000, "delay_damage": 0, "enforcement_cost": 0, "total": 323_000_000}
    s6r = {"principal": 220_000_000, "legal_cost": 3_000_000, "delay_damage": 0, "enforcement_cost": 0, "total": 223_000_000}
    s7p = {"principal": 180_000_000, "legal_cost": 0, "delay_damage": 0, "enforcement_cost": 0, "total": 180_000_000}
    collections["recovery_ledger"] = [
        ledger("S5", "principal", "PRINCIPAL_ACCRUAL", "INCREASE", 210_000_000, {"principal": 210_000_000}, z, s5, "2026-06-01T09:00:00+09:00"),
        ledger("S6", "principal", "PRINCIPAL_ACCRUAL", "INCREASE", 320_000_000, {"principal": 320_000_000}, z, s6p, "2025-09-01T09:00:00+09:00"),
        ledger("S6", "legal", "LEGAL_COST_ACCRUAL", "INCREASE", 3_000_000, {"legal_cost": 3_000_000}, s6p, s6c, "2025-10-01T09:00:00+09:00"),
        ledger("S6", "receipt", "DIVIDEND_RECEIPT", "DECREASE", 100_000_000, {"principal": 100_000_000}, s6c, s6r, "2026-06-30T09:00:00+09:00"),
        ledger("S7", "principal", "PRINCIPAL_ACCRUAL", "INCREASE", 180_000_000, {"principal": 180_000_000}, z, s7p, "2025-01-02T09:00:00+09:00"),
        ledger("S7", "receipt", "DIVIDEND_RECEIPT", "DECREASE", 180_000_000, {"principal": 180_000_000}, s7p, z, "2026-07-10T15:00:00+09:00"),
    ]
    collections["auction_cases"] = [
        _with_source({"_id": "demo-auction-s6", "recovery_claim_id": "demo-rc-s6", "auction_type": "Auction",
                      "case_number": "2025타경260723", "filing_date": "2025-10-14", "status": "InProgress",
                      "appraisal_won": 360_000_000, "sale_date": None, "dividend_date": None,
                      "dividend_amount": 100_000_000, "created_at": "2025-10-14T09:00:00+09:00",
                      "updated_at": DEMO_AS_OF_TS}, "S6")
    ]
    collections["legal_cases"] = [
        _with_source({"_id": "demo-legal-s6", "recovery_claim_id": "demo-rc-s6", "case_type": "PaymentOrder",
                      "court": "서울중앙지방법원", "case_number": "2025차전260723", "status": "Judgment",
                      "judgment": "Demo", "created_at": "2025-09-20T09:00:00+09:00", "updated_at": DEMO_AS_OF_TS}, "S6")
    ]
    collections["timeline_events"] = [
        _with_source({"_id": f"demo-timeline-{sid.lower()}", "contract_id": f"demo-ct-{sid.lower()}",
                      "event_type": "DemoScenarioSeeded", "occurred_at": DEMO_AS_OF_TS,
                      "blockchain_status": "NotRequested", "blockchain_tx_id": None}, sid)
        for sid in _SCENARIO_LABELS
    ]
    return collections


def _canonical_digest(collections: dict[str, list[dict[str, Any]]]) -> str:
    payload = json.dumps(collections, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _file_hashes() -> dict[str, str]:
    data_dir = Path(get_settings().data_dir)
    patterns = [
        "processed/ml/recovery_priority_scores_*.csv",
        "processed/housta/housta_issuance_region_monthly_*.csv",
        "processed/housta/housta_region_risk_*.csv",
    ]
    hashes: dict[str, str] = {}
    for pattern in patterns:
        matches = sorted(data_dir.glob(pattern))
        if matches:
            path = matches[-1]
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            hashes[str(path.relative_to(data_dir))] = digest
    return hashes


class DemoScenarioService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._db = db

    async def _prediction_results(self, use_model: bool) -> tuple[dict[str, dict[str, Any]], str, dict[str, Any]]:
        metadata = recovery_model_metadata()
        if not use_model:
            return _CACHED_RESULTS, "cached_demo_prediction", metadata
        results: dict[str, dict[str, Any]] = {}
        try:
            for scenario_id, values in _MODEL_INPUTS.items():
                results[scenario_id] = await run_in_threadpool(
                    ml_service.predict_recovery,
                    ml_service.RecoveryInput(**values),
                )
        except Exception:  # noqa: BLE001 - 오프라인 시연은 명시적 캐시로 계속 가능해야 한다.
            return _CACHED_RESULTS, "cached_demo_prediction", metadata
        return results, "model_poc", metadata

    async def seed(self, *, use_model: bool = True) -> dict[str, Any]:
        results, prediction_source, model_meta = await self._prediction_results(use_model)
        collections = build_demo_documents(
            results,
            prediction_source_type=prediction_source,
            model_meta=model_meta,
        )
        counts: dict[str, int] = {}
        ids: dict[str, list[str]] = {}
        for collection_name, documents in collections.items():
            for document in documents:
                await self._db[collection_name].replace_one(
                    {"_id": document["_id"]}, document, upsert=True
                )
            counts[collection_name] = len(documents)
            ids[collection_name] = sorted(str(document["_id"]) for document in documents)

        manifest = {
            "_id": MANIFEST_ID,
            "template_version": DEMO_TEMPLATE_VERSION,
            "demo_as_of_date": DEMO_AS_OF_DATE,
            "demo_as_of_timestamp": DEMO_AS_OF_TS,
            "seed": DEMO_SEED,
            "scenario_ids": sorted(_SCENARIO_LABELS),
            "scenario_labels": _SCENARIO_LABELS,
            "collection_counts": counts,
            "document_ids": ids,
            "document_digest_sha256": _canonical_digest(collections),
            "source_file_sha256": _file_hashes(),
            "model_version": model_meta["model_version"],
            "model_artifact_sha256": model_meta["artifact_sha256"],
            "prediction_source_type": prediction_source,
            "created_at": DEMO_AS_OF_TS,
            "provenance": source_metadata(
                data_mode="DEMO",
                source_type="demo_scenario",
                source_dataset=DEMO_TEMPLATE_VERSION,
                as_of_date=DEMO_AS_OF_DATE,
                is_demo=True,
                basis="S1~S7 재현 가능 시연 Seed manifest",
            ),
        }
        await self._db["demo_seed_manifests"].replace_one(
            {"_id": MANIFEST_ID}, manifest, upsert=True
        )
        return manifest

    async def manifest(self) -> dict[str, Any]:
        doc = await self._db["demo_seed_manifests"].find_one({"_id": MANIFEST_ID})
        if not doc:
            raise ResourceNotFoundError("HUG 시연 Seed manifest가 없습니다. 먼저 seed를 실행하세요.")
        return doc

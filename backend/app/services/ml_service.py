"""ML 추론 서비스 — scripts/train_ml_models.py가 저장한 joblib 모델을 서빙한다.

모델 4종 (전부 합성/비식별 데이터 기준 패턴 — 실제 HUG 성능 아님):
- recovery_ratio_lgbm: 예상 회수율(0~1) → LOW/MED/HIGH 등급
- days_to_dividend_lgbm: 예상 배당 소요일
- dispute_clf / stage_clf: 상담 텍스트 → 분쟁유형/진행단계

우선순위 스코어는 학습 시 산출한 포트폴리오 분포(recovery_priority_scores CSV)의
백분위 순위를 기준으로 계산해, 단건 예측도 전 채권 대비 상대 위치로 표현한다.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from app.core.config import get_settings
from app.core.exceptions import ModelInferenceFailedError
from app.services import public_data

logger = logging.getLogger(__name__)

BASIS_NOTE = "합성데이터 기준 시뮬레이션 (실데이터 재학습 전제)"

CAT_COLS = ["product_name", "claim_type"]
FEATS = CAT_COLS + ["log_claimed", "log_incurred", "filing_year", "filing_month", "incurred_gap_days"]
FEAT_LABELS = {
    "product_name": "상품",
    "claim_type": "채권구분",
    "log_claimed": "청구금액",
    "log_incurred": "발생금액",
    "filing_year": "경공매 신청연도",
    "filing_month": "경공매 신청월",
    "incurred_gap_days": "신청→채권발생 간격",
}
# 학습 시 카테고리 사전 (train_ml_models.py의 interim 데이터 기준)
PRODUCT_CATEGORIES = ["개인임대사업자임대보증금보증", "전세보증금반환보증"]
CLAIM_CATEGORIES = ["구상채권", "구상채권(신상품)", "소송대지급금"]
W_RECOVERY, W_SPEED = 0.6, 0.4


def _models_dir() -> Path:
    return Path(get_settings().data_dir) / "processed" / "ml" / "models"


@lru_cache(maxsize=8)
def _load_model(name: str):
    path = _models_dir() / name
    if not path.exists():
        raise ModelInferenceFailedError(
            f"모델 파일이 없습니다: {path.name}. scripts/train_ml_models.py를 먼저 실행하세요."
        )
    return joblib.load(path)


@lru_cache(maxsize=2)
def _tree_explainer(name: str):
    import shap  # 지연 임포트 (기동 시간 절약)

    return shap.TreeExplainer(_load_model(name))


@lru_cache(maxsize=1)
def _portfolio_context() -> dict | None:
    df = public_data.priority_scores()
    if df is None:
        return None
    return {
        "expected_recovery": np.sort(df["expected_recovery_won"].to_numpy()),
        "pred_days": np.sort(df["pred_days_to_dividend"].to_numpy()),
        "n": len(df),
    }


def _pct_rank(sorted_arr: np.ndarray, value: float) -> float:
    if sorted_arr is None or len(sorted_arr) == 0:
        return 0.5
    return float(np.searchsorted(sorted_arr, value, side="right")) / len(sorted_arr)


def _grade(ratio: float) -> str:
    if ratio >= 0.9:
        return "HIGH"
    if ratio >= 0.5:
        return "MED"
    return "LOW"


@dataclass
class RecoveryInput:
    product_name: str
    claim_type: str
    claimed_amount: int
    incurred_amount: int
    auction_filed_date: date
    incurred_date: date


def _feature_frame(inp: RecoveryInput) -> pd.DataFrame:
    row = {
        "product_name": pd.Categorical([inp.product_name], categories=PRODUCT_CATEGORIES),
        "claim_type": pd.Categorical([inp.claim_type], categories=CLAIM_CATEGORIES),
        "log_claimed": [float(np.log1p(max(inp.claimed_amount, 0)))],
        "log_incurred": [float(np.log1p(max(inp.incurred_amount, 0)))],
        "filing_year": [inp.auction_filed_date.year],
        "filing_month": [inp.auction_filed_date.month],
        "incurred_gap_days": [(inp.incurred_date - inp.auction_filed_date).days],
    }
    return pd.DataFrame(row)[FEATS]


def _fmt_val(feature: str, X: pd.DataFrame, inp: RecoveryInput) -> str:
    if feature == "log_claimed":
        return f"{inp.claimed_amount / 1e8:.1f}억" if inp.claimed_amount >= 1e7 else f"{inp.claimed_amount / 1e4:,.0f}만"
    if feature == "log_incurred":
        return f"{inp.incurred_amount / 1e8:.1f}억" if inp.incurred_amount >= 1e7 else f"{inp.incurred_amount / 1e4:,.0f}만"
    if feature == "incurred_gap_days":
        return f"{int(X.iloc[0]['incurred_gap_days'])}일"
    return str(X.iloc[0][feature])


def predict_recovery(inp: RecoveryInput) -> dict:
    rec_model = _load_model("recovery_ratio_lgbm.joblib")
    day_model = _load_model("days_to_dividend_lgbm.joblib")
    X = _feature_frame(inp)

    ratio = float(np.clip(rec_model.predict(X)[0], 0, 1))
    days = int(max(day_model.predict(X)[0], 0))
    expected = ratio * inp.claimed_amount

    ctx = _portfolio_context()
    if ctx:
        score = 100 * (W_RECOVERY * _pct_rank(ctx["expected_recovery"], expected)
                       + W_SPEED * (1 - _pct_rank(ctx["pred_days"], days)))
        portfolio_n = ctx["n"]
    else:
        score, portfolio_n = None, 0

    sv = _tree_explainer("recovery_ratio_lgbm.joblib").shap_values(X)[0]
    order = np.argsort(-np.abs(sv))[:3]
    factors = [
        {
            "feature": FEATS[j],
            "label": FEAT_LABELS[FEATS[j]],
            "value": _fmt_val(FEATS[j], X, inp),
            "shap": round(float(sv[j]), 4),
            "direction": "up" if sv[j] > 0 else "down",
        }
        for j in order
    ]

    return {
        "pred_recovery_ratio": round(ratio, 4),
        "pred_recovery_grade": _grade(ratio),
        "pred_days_to_dividend": days,
        "expected_recovery_won": int(round(expected)),
        "priority_score": round(score, 1) if score is not None else None,
        "priority_weights": {"recovery": W_RECOVERY, "speed": W_SPEED},
        "portfolio_size": portfolio_n,
        "top_factors": factors,
        "basis": BASIS_NOTE,
    }


def classify_counsel(text: str) -> dict:
    dispute = _load_model("dispute_clf.joblib")
    stage = _load_model("stage_clf.joblib")

    def _top(pipe, text: str) -> dict:
        proba = pipe.predict_proba([text])[0]
        classes = pipe.classes_
        order = np.argsort(-proba)[:3]
        return {
            "label": str(classes[order[0]]),
            "confidence": round(float(proba[order[0]]), 4),
            "top3": [{"label": str(classes[i]), "prob": round(float(proba[i]), 4)} for i in order],
        }

    return {
        "dispute_type": _top(dispute, text),
        "consultation_stage": _top(stage, text),
        "basis": "비식별 상담 935건 학습 (합성·비식별 데이터 기준)",
    }


def models_info() -> dict:
    metrics_path = sorted((Path(get_settings().data_dir) / "processed" / "ml").glob("ml_metrics_*.json"))
    metrics = None
    if metrics_path:
        import json

        metrics = json.loads(metrics_path[-1].read_text(encoding="utf-8"))
    available = {p.name: p.stat().st_size for p in _models_dir().glob("*.joblib")} if _models_dir().exists() else {}
    return {"available_models": available, "metrics": metrics, "basis": BASIS_NOTE}

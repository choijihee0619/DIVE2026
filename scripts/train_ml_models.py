#!/usr/bin/env python3
"""DIVE2026 ML 모델 학습 (합성데이터 기준 패턴 학습).

모델
1. 예상 회수율 회귀 + LOW/MED/HIGH 등급 (배당내역 recovery_ratio)
2. 예상 배당 소요기간 회귀 (days_filing_to_dividend, 음수 제외)
3. 회수 우선순위 스코어 (1·2 예측의 파생 — 전체 채권 스코어링 CSV)
4. 상담 분쟁유형·진행단계 텍스트 분류 (TF-IDF + LogisticRegression)

산출 (개별수집데이터 및 API/processed/ml/):
- models/*.joblib
- ml_metrics_<날짜>.json
- shap_global_<모델>_<날짜>.csv (전역 중요도)
- recovery_priority_scores_<날짜>.csv (전 채권 예측+스코어+상위요인, HUG 채권회수 대시보드 데모용)

주의: 전부 합성데이터 기준 패턴이며 실제 HUG 성능을 의미하지 않는다.

실행: backend/.venv/bin/python scripts/train_ml_models.py
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
import shap
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, classification_report, f1_score,
                             mean_absolute_error, r2_score)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

ROOT = Path(__file__).resolve().parent.parent
INTERIM = ROOT / "개별수집데이터 및 API" / "interim"
OUT = ROOT / "개별수집데이터 및 API" / "processed" / "ml"
MODELS = OUT / "models"
TODAY = date.today().strftime("%Y%m%d")
SEED = 42

CAT_COLS = ["product_name", "claim_type"]
NUM_COLS = ["log_claimed", "log_incurred", "filing_year", "filing_month", "incurred_gap_days"]
FEATS = CAT_COLS + NUM_COLS

FEAT_LABELS = {
    "product_name": "상품",
    "claim_type": "채권구분",
    "log_claimed": "청구금액",
    "log_incurred": "발생금액",
    "filing_year": "경공매 신청연도",
    "filing_month": "경공매 신청월",
    "incurred_gap_days": "신청→채권발생 간격",
}


def load_dividend() -> pd.DataFrame:
    df = pd.read_parquet(
        INTERIM / "dividend" / "interim_dividend_20260714_전세임대채무자_배당내역.parquet")
    df["auction_filed_date"] = pd.to_datetime(df["auction_filed_date"], errors="coerce")
    df["incurred_date"] = pd.to_datetime(df["incurred_date"], errors="coerce")
    df = df.dropna(subset=["auction_filed_date", "incurred_date"])
    df["log_claimed"] = np.log1p(df["claimed_amount"].clip(lower=0))
    df["log_incurred"] = np.log1p(df["incurred_amount"].clip(lower=0))
    df["filing_year"] = df["auction_filed_date"].dt.year
    df["filing_month"] = df["auction_filed_date"].dt.month
    df["incurred_gap_days"] = (df["incurred_date"] - df["auction_filed_date"]).dt.days
    for c in CAT_COLS:
        df[c] = df[c].astype("category")
    return df


def grade(ratio: pd.Series) -> pd.Series:
    return pd.cut(ratio, bins=[-0.001, 0.5, 0.9, 1.001], labels=["LOW", "MED", "HIGH"])


def train_regressor(df: pd.DataFrame, target: str, name: str, metrics: dict) -> lgb.LGBMRegressor:
    X, y = df[FEATS], df[target]
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=SEED)
    model = lgb.LGBMRegressor(
        n_estimators=400, learning_rate=0.05, num_leaves=63,
        random_state=SEED, verbose=-1)
    model.fit(X_tr, y_tr, categorical_feature=CAT_COLS)
    pred = model.predict(X_te)
    m = {
        "n_train": len(X_tr), "n_test": len(X_te),
        "mae": float(mean_absolute_error(y_te, pred)),
        "r2": float(r2_score(y_te, pred)),
    }
    if target == "recovery_ratio":
        pred_grade = grade(pd.Series(np.clip(pred, 0, 1), index=y_te.index)).astype(str)
        true_grade = grade(y_te).astype(str)
        m["grade_accuracy"] = float(accuracy_score(true_grade, pred_grade))
        m["grade_macro_f1"] = float(f1_score(true_grade, pred_grade, average="macro"))
    else:
        m["median_ae_days"] = float(np.median(np.abs(y_te - pred)))
    metrics[name] = m
    joblib.dump(model, MODELS / f"{name}_lgbm.joblib")

    explainer = shap.TreeExplainer(model)
    sv = explainer.shap_values(X_te)
    imp = pd.DataFrame({
        "feature": FEATS,
        "label": [FEAT_LABELS[f] for f in FEATS],
        "mean_abs_shap": np.abs(sv).mean(axis=0),
    }).sort_values("mean_abs_shap", ascending=False)
    imp.to_csv(OUT / f"shap_global_{name}_{TODAY}.csv", index=False, encoding="utf-8-sig")
    print(f"[OK] {name}: {m}")
    return model


def score_portfolio(df: pd.DataFrame, rec_model, day_model) -> None:
    X = df[FEATS]
    pred_ratio = np.clip(rec_model.predict(X), 0, 1)
    pred_days = np.clip(day_model.predict(X), 0, None)
    expected_recovery = pred_ratio * df["claimed_amount"].to_numpy()

    def pct_rank(a: np.ndarray) -> np.ndarray:
        return pd.Series(a).rank(pct=True).to_numpy()

    w_recovery, w_speed = 0.6, 0.4  # HUG 실무 협의로 조정 가능한 가중치
    score = 100 * (w_recovery * pct_rank(expected_recovery) + w_speed * (1 - pct_rank(pred_days)))

    # 건별 상위 3개 SHAP 요인 (회수율 모델 기준)
    sv = shap.TreeExplainer(rec_model).shap_values(X)
    order = np.argsort(-np.abs(sv), axis=1)[:, :3]
    def fmt_val(f: str, val) -> str:
        if f in ("log_claimed", "log_incurred"):
            won = np.expm1(val)
            return f"{won / 1e8:.1f}억" if won >= 1e7 else f"{won / 1e4:,.0f}만"
        if f == "incurred_gap_days":
            return f"{int(val)}일"
        return str(val)

    factors = []
    for i in range(len(X)):
        parts = []
        for j in order[i]:
            f = FEATS[j]
            val = fmt_val(f, X.iloc[i][f])
            direction = "+" if sv[i, j] > 0 else "-"
            parts.append(f"{FEAT_LABELS[f]}={val}({direction}{abs(sv[i, j]):.3f})")
        factors.append("; ".join(parts))

    out = pd.DataFrame({
        "source_row_id": df["source_row_id"].to_numpy(),
        "product_name": df["product_name"].astype(str).to_numpy(),
        "claim_type": df["claim_type"].astype(str).to_numpy(),
        "claimed_amount": df["claimed_amount"].to_numpy(),
        "pred_recovery_ratio": np.round(pred_ratio, 4),
        "pred_recovery_grade": grade(pd.Series(pred_ratio)).astype(str),
        "pred_days_to_dividend": np.round(pred_days, 0).astype(int),
        "expected_recovery_won": np.round(expected_recovery, 0).astype("int64"),
        "priority_score": np.round(score, 1),
        "top_factors": factors,
        "basis": "합성데이터 기준 시뮬레이션",
    }).sort_values("priority_score", ascending=False)
    out.to_csv(OUT / f"recovery_priority_scores_{TODAY}.csv", index=False, encoding="utf-8-sig")
    print(f"[OK] priority scores: {len(out)}건 → recovery_priority_scores_{TODAY}.csv")


def train_text_classifiers(metrics: dict) -> None:
    df = pd.read_parquet(INTERIM / "in" / "interim_in_20260714_비식별_임대차상담데이터.parquet")
    df = df.dropna(subset=["situation_summary"])

    merge_dispute = {"원상복구·정산": "기타·일반문의", "이중·다운계약": "기타·일반문의",
                     "전출선근저당후": "기타·일반문의"}
    merge_stage = {"상고심": "판결·집행"}
    tasks = [
        ("dispute_clf", df["dispute_type"].replace(merge_dispute), "분쟁유형"),
        ("stage_clf", df["consultation_stage"].replace(merge_stage), "진행단계"),
    ]
    for name, y, label in tasks:
        X_tr, X_te, y_tr, y_te = train_test_split(
            df["situation_summary"], y, test_size=0.2, random_state=SEED, stratify=y)
        pipe = Pipeline([
            ("tfidf", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4),
                                      min_df=2, max_features=50000, sublinear_tf=True)),
            ("clf", LogisticRegression(max_iter=2000, C=2.0, class_weight="balanced")),
        ])
        pipe.fit(X_tr, y_tr)
        pred = pipe.predict(X_te)
        metrics[name] = {
            "n_train": len(X_tr), "n_test": len(X_te),
            "accuracy": float(accuracy_score(y_te, pred)),
            "macro_f1": float(f1_score(y_te, pred, average="macro")),
            "labels": sorted(y.unique().tolist()),
        }
        joblib.dump(pipe, MODELS / f"{name}.joblib")
        print(f"[OK] {name}({label}): acc={metrics[name]['accuracy']:.3f} macroF1={metrics[name]['macro_f1']:.3f}")
        report = classification_report(y_te, pred, zero_division=0)
        (OUT / f"clf_report_{name}_{TODAY}.txt").write_text(report, encoding="utf-8")


def main() -> int:
    MODELS.mkdir(parents=True, exist_ok=True)
    metrics: dict = {"basis": "합성데이터/비식별 상담데이터 기준. 실제 HUG 성능 아님.",
                     "trained_at": TODAY, "seed": SEED}
    df = load_dividend()
    rec = train_regressor(df, "recovery_ratio", "recovery_ratio", metrics)
    df_days = df[df["days_filing_to_dividend"] >= 0]
    metrics["days_dropped_negative"] = int(len(df) - len(df_days))
    day = train_regressor(df_days, "days_filing_to_dividend", "days_to_dividend", metrics)
    score_portfolio(df, rec, day)
    train_text_classifiers(metrics)
    (OUT / f"ml_metrics_{TODAY}.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nmetrics → processed/ml/ml_metrics_{TODAY}.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())

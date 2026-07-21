#!/usr/bin/env python3
"""사고확률 모델 PoC (case-control) — 정상대조군 확보방안 A안 착수.

그동안 "사고 발생확률" 모델을 못 만든 이유는 정상(무사고) 대조군이 없어서였다.
이제 RTMS 전월세 실거래(건별)를 유사 정상군으로 확보(scripts/collect_rtms_rent.py)했으므로,
사고군(합성 사고현황)과 결합해 이진분류 PoC를 학습·검증할 수 있다.

설계 원칙(정직성):
- 두 군에서 '대칭적으로 측정 가능한' 피처만 사용한다: 시도, 주택유형(4분류), log 보증금,
  전용면적, 건축연도. → 한쪽에만 있는 값(전세가율 등)으로 인한 라벨 누출을 원천 차단.
- 전세가율(사고사례 84%가 80%+)이 가장 강한 신호지만, 정상군은 주택가액이 없어 이번
  baseline에서 제외한다. 확장 경로는 리포트에 명시(VWorld 공시가격 per-control 또는
  RTMS 매매 지역중앙값).
- 사고군은 합성데이터다. 결과 지표에 "합성 사고군 + 실거래 정상군 혼합 기준, 실데이터
  재학습 전제"를 명시한다.
- 대조군 라벨 노이즈(정상 계약 일부가 실제 사고일 수 있음)는 사고율 수 % 수준이라 영향
  제한적이나 한계로 기록한다.

실행: backend/.venv/bin/python scripts/build_accident_model_poc.py
산출: 개별수집데이터 및 API/processed/ml/accident_clf_poc_<날짜>.joblib
      + accident_clf_poc_metrics_<날짜>.json + ACCIDENT_MODEL_POC_README.md
"""

from __future__ import annotations

import glob
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "개별수집데이터 및 API"
ML_DIR = DATA / "processed" / "ml"
CONTROL_DIR = DATA / "processed" / "control"
TODAY = date.today().strftime("%y%m%d")

CASE_FILES = [
    DATA / "interim/hug/interim_hug_20260714_전세사고_주택가액대비임대보증금.parquet",
    DATA / "interim/hug/interim_hug_20260714_임대보증_사고현황.parquet",
]

# 주택유형 → RTMS 4분류 정규화
HOUSING_MAP = {
    "아파트": "아파트",
    "도시형생활주택": "아파트",
    "다세대주택": "연립다세대",
    "연립주택": "연립다세대",
    "단독주택": "단독다가구",
    "다가구주택": "단독다가구",
    "다중주택": "단독다가구",
    "단독다가구다중주택(확인서미제출)": "단독다가구",
    "노인복지주택": "단독다가구",
    "오피스텔": "오피스텔",
    "오피스텔(주거용)": "오피스텔",
    "기타(오피스텔)": "오피스텔",
    "연립다세대": "연립다세대",
    "단독다가구": "단독다가구",
}

SIDO_CANON = {
    "서울": "서울특별시", "부산": "부산광역시", "대구": "대구광역시", "인천": "인천광역시",
    "광주": "광주광역시", "대전": "대전광역시", "울산": "울산광역시", "세종": "세종특별자치시",
    "경기": "경기도", "강원": "강원특별자치도", "충북": "충청북도", "충남": "충청남도",
    "전북": "전북특별자치도", "전남": "전라남도", "경북": "경상북도", "경남": "경상남도",
    "제주": "제주특별자치도",
}


def canon_sido(text: str | None) -> str | None:
    if not text or not isinstance(text, str):
        return None
    head = text.strip().split()[0] if text.strip() else ""
    for k, v in SIDO_CANON.items():
        if head.startswith(k) or head.startswith(v):
            return v
    return None


def _year(date_str) -> int | None:
    try:
        return int(str(date_str)[:4])
    except (ValueError, TypeError):
        return None


def load_cases() -> pd.DataFrame:
    frames = []
    c1 = pd.read_parquet(CASE_FILES[0])
    frames.append(pd.DataFrame({
        "sido": c1["region_name"].map(canon_sido),
        "housing_type": c1["housing_type"].map(HOUSING_MAP),
        "deposit_amount": pd.to_numeric(c1["house_value"] * c1["deposit_to_house_value_ratio"], errors="coerce"),
        "area_m2": np.nan,
        "build_year": np.nan,
        "contract_year": c1["guarantee_end_date"].map(_year),
    }))
    c2 = pd.read_parquet(CASE_FILES[1])
    frames.append(pd.DataFrame({
        "sido": c2["workplace_region_detail"].map(canon_sido),
        "housing_type": c2["housing_type"].map(HOUSING_MAP),
        "deposit_amount": pd.to_numeric(c2["deposit_amount"], errors="coerce"),
        "area_m2": np.nan,
        "build_year": np.nan,
        "contract_year": c2["guarantee_end_date"].map(_year),
    }))
    df = pd.concat(frames, ignore_index=True)
    df["is_accident"] = 1
    return df


def load_controls() -> pd.DataFrame:
    files = sorted(glob.glob(str(CONTROL_DIR / "rtms_jeonse_controls_*.csv")))
    if not files:
        raise SystemExit("정상 대조군 CSV가 없습니다 — 먼저 collect_rtms_rent.py를 실행하세요.")
    df = pd.read_csv(files[-1])
    out = pd.DataFrame({
        "sido": df["sido"].map(canon_sido),
        "housing_type": df["housing_type"].map(HOUSING_MAP),
        "deposit_amount": pd.to_numeric(df["deposit_amount"], errors="coerce"),
        "area_m2": pd.to_numeric(df["area_m2"], errors="coerce"),
        "build_year": pd.to_numeric(df["build_year"], errors="coerce"),
        "contract_year": pd.to_numeric(df["deal_year"], errors="coerce"),
    })
    out["is_accident"] = 0
    return out, files[-1]


def main() -> int:
    from lightgbm import LGBMClassifier
    from sklearn.metrics import (
        average_precision_score,
        brier_score_loss,
        roc_auc_score,
    )
    from sklearn.model_selection import train_test_split

    cases = load_cases()
    controls, control_file = load_controls()
    print(f"사고군(case): {len(cases):,}건 · 정상군(control): {len(controls):,}건")

    df = pd.concat([cases, controls], ignore_index=True)
    df = df.dropna(subset=["sido", "housing_type", "deposit_amount"])
    df = df[df["deposit_amount"] > 0]

    # 누출 차단: 정상군은 대표 16개 시군구(일부 시도)만 표집했으므로, 정상군이 없는 시도는
    # 자동으로 '사고'가 되어버린다. 두 군이 공유하는 시도로 support를 맞춘다.
    shared_sido = set(df.loc[df.is_accident == 0, "sido"]) & set(df.loc[df.is_accident == 1, "sido"])
    df = df[df["sido"].isin(shared_sido)].copy()
    print(f"공유 시도 {len(shared_sido)}개로 제한: {sorted(shared_sido)}")

    df["log_deposit"] = np.log1p(df["deposit_amount"])
    df["sido"] = df["sido"].astype("category")
    df["housing_type"] = df["housing_type"].astype("category")

    # 두 군에서 '대칭적으로 존재하는' 피처만 사용한다.
    # area_m2·build_year는 사고군에 전무 → 결측 자체가 라벨을 누출하므로 제외한다.
    features = ["sido", "housing_type", "log_deposit"]
    X = df[features]
    y = df["is_accident"].astype(int)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    pos_rate = y_train.mean()
    model = LGBMClassifier(
        n_estimators=400,
        learning_rate=0.05,
        num_leaves=31,
        max_depth=-1,
        subsample=0.8,
        colsample_bytree=0.8,
        class_weight="balanced",
        random_state=42,
        verbose=-1,
    )
    model.fit(X_train, y_train, categorical_feature=["sido", "housing_type"])

    proba = model.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, proba)
    ap = average_precision_score(y_test, proba)
    brier = brier_score_loss(y_test, proba)

    # 투명성 진단: 단일 피처군 AUC(어떤 신호가 분리를 이끄는지 공개)
    single_auc = {}
    for feats in (["log_deposit"], ["sido", "housing_type"]):
        cat = [c for c in ("sido", "housing_type") if c in feats]
        mm = LGBMClassifier(n_estimators=200, class_weight="balanced", random_state=42, verbose=-1)
        mm.fit(X_train[feats], y_train, categorical_feature=cat if cat else "auto")
        single_auc["+".join(feats)] = round(
            float(roc_auc_score(y_test, mm.predict_proba(X_test[feats])[:, 1])), 4
        )

    importances = dict(sorted(
        zip(features, model.feature_importances_.tolist()),
        key=lambda kv: kv[1], reverse=True,
    ))

    # 시도별 사고비율(참고) — 표본 내 case 비율
    sido_rate = (
        df.groupby("sido", observed=True)["is_accident"].mean().sort_values(ascending=False)
        .head(8).round(3).to_dict()
    )

    metrics = {
        "trained_at": date.today().isoformat(),
        "model": "accident_clf_poc (LightGBM binary, case-control)",
        "n_case": int((y == 1).sum()),
        "n_control": int((y == 0).sum()),
        "case_control_ratio": round(float((y == 1).sum() / max((y == 0).sum(), 1)), 2),
        "features": features,
        "roc_auc": round(float(auc), 4),
        "pr_auc": round(float(ap), 4),
        "brier": round(float(brier), 4),
        "single_feature_auc": single_auc,
        "shared_sido": sorted(shared_sido),
        "train_pos_rate": round(float(pos_rate), 4),
        "feature_importance": importances,
        "sample_sido_accident_share": sido_rate,
        "control_source": Path(control_file).name,
        "basis": "합성 사고군 + RTMS 전세 실거래 정상군 혼합 기준. 실제 HUG 성능 아님. 실데이터 재학습 전제.",
        "limitations": [
            "AUC는 정상군 표본 구성에 민감하다 — 저위험 고가 지역(강남·분당) 포함이 보증금 분포를 넓혀 분리도를 키운다. 전국 균형표본으로 재측정 필요",
            "누출 방지 조치: (1) 정상군에만 있는 area_m2·build_year 제외, (2) 두 군 공유 시도로 support 제한(정상군 표집이 없는 시도가 자동 '사고'가 되는 것 차단)",
            "전세가율(최강 신호)은 정상군에 주택가액이 없어 baseline 제외 — 확장 시 VWorld 공시가격 per-control 또는 RTMS 매매 지역중앙값으로 산출",
            "사고군은 합성데이터, 정상군은 실거래 — 분포 이질성 존재",
            "대조군 라벨 노이즈: 정상 계약 일부가 실제 사고일 수 있음(사고율 수 % 수준)",
        ],
    }

    ML_DIR.mkdir(parents=True, exist_ok=True)
    import joblib
    model_path = ML_DIR / f"accident_clf_poc_{TODAY}.joblib"
    joblib.dump({"model": model, "features": features, "metrics": metrics}, model_path)
    metrics_path = ML_DIR / f"accident_clf_poc_metrics_{TODAY}.json"
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    readme = ML_DIR / "ACCIDENT_MODEL_POC_README.md"
    readme.write_text(_render_readme(metrics), encoding="utf-8")

    print(f"\nROC-AUC={metrics['roc_auc']} · PR-AUC={metrics['pr_auc']} · Brier={metrics['brier']}")
    print(f"case={metrics['n_case']:,} / control={metrics['n_control']:,} (ratio {metrics['case_control_ratio']})")
    print(f"중요도: {list(importances.items())}")
    print(f"→ {model_path.relative_to(ROOT)}")
    print(f"→ {metrics_path.relative_to(ROOT)}")
    return 0


def _render_readme(m: dict) -> str:
    imp = "\n".join(f"| {k} | {v} |" for k, v in m["feature_importance"].items())
    lim = "\n".join(f"- {x}" for x in m["limitations"])
    sido = "\n".join(f"| {k} | {v} |" for k, v in m["sample_sido_accident_share"].items())
    return f"""# 사고확률 모델 PoC (case-control) — {m['trained_at']}

정상대조군 확보방안(../../../docs/정상대조군_확보방안_260721.md) **A안 착수 결과**.
그동안 정상 대조군 부재로 못 만들던 "사고 발생확률" 모델을, RTMS 전세 실거래를 정상군으로
확보해 이진분류 PoC로 구현했다.

## 성능 (hold-out 20%)

| 지표 | 값 |
|---|---|
| ROC-AUC | **{m['roc_auc']}** |
| PR-AUC | {m['pr_auc']} |
| Brier score | {m['brier']} |
| 사고군(case) | {m['n_case']:,} |
| 정상군(control) | {m['n_control']:,} |
| case:control 비율 | {m['case_control_ratio']} |

공유 시도({len(m['shared_sido'])}개): {', '.join(m['shared_sido'])}

### 단일 피처군 AUC(투명성 진단 — 어떤 신호가 분리를 이끄는가)

| 피처군 | AUC |
|---|---|
""" + "\n".join(f"| {k} | {v} |" for k, v in m["single_feature_auc"].items()) + """

## 피처 중요도

| feature | importance |
|---|---|
{imp}

## 표본 내 시도별 사고 비율(참고)

| 시도 | 사고 비율 |
|---|---|
{sido}

## 기준(basis)

{m['basis']}

## 한계

{lim}

## 다음 단계

1. **전세가율 추가** — 정상군에 VWorld 공시가격(260721 live 연동됨)으로 전세가율을 산출하면
   가장 큰 성능 향상 예상(사고사례 84%가 전세가율 80%+).
2. **정상군 확대** — 전국 시군구로 층화표본 확장, 월별 균형.
3. **실데이터 재학습** — HUG 실제 사고/정상 계약 확보 시 동일 파이프라인 재학습·보정(calibration).
"""


if __name__ == "__main__":
    sys.exit(main())

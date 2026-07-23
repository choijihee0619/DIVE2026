#!/usr/bin/env python3
"""사고위험 PU Learning PoC 학습기.

발제사 제공 사고 데이터에는 확인된 사고(Positive)만 있고, RTMS 전월세 실거래는
사고 여부를 확인할 공통 계약키가 없다. 따라서 RTMS를 정상(Negative)으로 단정하지 않고
미라벨(Unlabeled)로 취급해 LightGBM bagging PU 모델을 학습한다.

이 모델의 기본 출력은 개별 계약의 검증된 사고확률이 아니다.

* ``pu_risk_score``: P와 U를 구분하는 미보정 상대위험 점수
* ``risk_percentile``: 참조 U 모집단 내 상대 백분위
* ``prior_aligned_estimate``: HOUSTA 집계 사고율에 평균을 맞춘 미검증 PoC 추정치

실행:
    backend/.venv/bin/python scripts/build_accident_model_pu.py

산출:
    개별수집데이터 및 API/processed/ml/accident_clf_pu_poc_<날짜>.joblib
    개별수집데이터 및 API/processed/ml/accident_clf_pu_poc_metrics_<날짜>.json
    개별수집데이터 및 API/processed/ml/ACCIDENT_MODEL_PU_POC_README.md
"""

from __future__ import annotations

import argparse
import glob
import hashlib
from importlib import metadata as importlib_metadata
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "개별수집데이터 및 API"
ML_DIR = DATA / "processed" / "ml"
UNLABELED_DIR = DATA / "processed" / "control"  # 기존 디렉터리명은 호환을 위해 유지
HOUSTA_DIR = DATA / "processed" / "housta"
TODAY = date.today().strftime("%y%m%d")

CASE_FILES = [
    DATA / "interim/hug/interim_hug_20260714_전세사고_주택가액대비임대보증금.parquet",
    DATA / "interim/hug/interim_hug_20260714_임대보증_사고현황.parquet",
]

FEATURES = ["sido", "housing_type", "log_deposit"]
CATEGORICAL_FEATURES = ["sido", "housing_type"]
HOUSING_LEVELS = ["아파트", "연립다세대", "단독다가구", "오피스텔"]

MODEL_HYPERPARAMETERS = {
    "objective": "binary",
    "n_estimators": 300,
    "learning_rate": 0.04,
    "num_leaves": 15,
    "max_depth": 5,
    "min_child_samples": 50,
    "subsample": 0.85,
    "colsample_bytree": 0.9,
    "reg_alpha": 0.5,
    "reg_lambda": 1.0,
    "n_jobs": -1,
    "verbose": -1,
}

HOUSING_MAP = {
    "아파트": "아파트",
    "도시형생활주택": "아파트",
    "다세대주택": "연립다세대",
    "연립주택": "연립다세대",
    "연립다세대": "연립다세대",
    "단독주택": "단독다가구",
    "다가구주택": "단독다가구",
    "다중주택": "단독다가구",
    "단독다가구": "단독다가구",
    "단독다가구다중주택(확인서미제출)": "단독다가구",
    "노인복지주택": "단독다가구",
    "오피스텔": "오피스텔",
    "오피스텔(주거용)": "오피스텔",
    "기타(오피스텔)": "오피스텔",
}

SIDO_CANON = {
    "서울": "서울특별시",
    "부산": "부산광역시",
    "대구": "대구광역시",
    "인천": "인천광역시",
    "광주": "광주광역시",
    "대전": "대전광역시",
    "울산": "울산광역시",
    "세종": "세종특별자치시",
    "경기": "경기도",
    "강원": "강원특별자치도",
    "충북": "충청북도",
    "충남": "충청남도",
    "전북": "전북특별자치도",
    "전남": "전라남도",
    "경북": "경상북도",
    "경남": "경상남도",
    "제주": "제주특별자치도",
}


def canon_sido_with_mapping(
    value: object, mapping: dict[str, str]
) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    head = value.strip().split()[0]
    for short, canonical in mapping.items():
        if head.startswith(short) or head.startswith(canonical):
            return canonical
    return None


def canon_sido(value: object) -> str | None:
    return canon_sido_with_mapping(value, SIDO_CANON)


def _year(value: object) -> int | None:
    try:
        return int(str(value)[:4])
    except (TypeError, ValueError):
        return None


def load_positives() -> pd.DataFrame:
    """합성 사고행을 알려진 P로 적재한다."""
    first = pd.read_parquet(CASE_FILES[0])
    p1 = pd.DataFrame(
        {
            "sido": first["region_name"].map(canon_sido),
            "housing_type": first["housing_type"].map(HOUSING_MAP),
            "deposit_amount": pd.to_numeric(
                first["house_value"] * first["deposit_to_house_value_ratio"],
                errors="coerce",
            ),
            "reference_year": first["guarantee_end_date"].map(_year),
            "source_dataset": "전세사고_주택가액대비임대보증금_합성",
        }
    )

    second = pd.read_parquet(CASE_FILES[1])
    p2 = pd.DataFrame(
        {
            "sido": second["workplace_region_detail"].map(canon_sido),
            "housing_type": second["housing_type"].map(HOUSING_MAP),
            "deposit_amount": pd.to_numeric(second["deposit_amount"], errors="coerce"),
            "reference_year": second["guarantee_end_date"].map(_year),
            "source_dataset": "임대보증_사고현황_합성",
        }
    )
    positives = pd.concat([p1, p2], ignore_index=True)
    positives["observed_label"] = 1
    positives["label_status"] = "positive"
    return positives


def _latest_unlabeled_file() -> Path:
    preferred = [
        Path(path)
        for path in glob.glob(str(UNLABELED_DIR / "rtms_jeonse_unlabeled_*.csv"))
    ]
    legacy = [
        Path(path)
        for path in glob.glob(str(UNLABELED_DIR / "rtms_jeonse_controls_*.csv"))
    ]
    files = preferred or legacy
    if not files:
        raise SystemExit("RTMS 미라벨 CSV가 없습니다. collect_rtms_rent.py를 먼저 실행하세요.")
    # 파일명은 기준기간으로 시작하므로 문자열 정렬이 실행 최신순을 보장하지 않는다.
    return max(files, key=lambda path: (path.stat().st_mtime_ns, path.name))


def load_unlabeled() -> tuple[pd.DataFrame, Path, dict[str, Any]]:
    """RTMS 행을 확정 정상값이 아닌 U로 적재한다."""
    path = _latest_unlabeled_file()
    source = pd.read_csv(path)
    is_new_collection = path.name.startswith("rtms_jeonse_unlabeled_")
    required_collection_columns = {"collection_complete", "source_manifest"}
    missing_collection_columns = required_collection_columns - set(source.columns)
    if is_new_collection and missing_collection_columns:
        raise SystemExit(
            f"새 RTMS U 파일에 완전성 필드가 없습니다: {path.name} "
            f"(missing={sorted(missing_collection_columns)})"
        )
    if "collection_complete" in source.columns:
        completion = (
            source["collection_complete"].dropna().astype(str).str.lower().unique().tolist()
        )
        if completion != ["true"]:
            raise SystemExit(
                f"미완료 RTMS 수집물은 학습할 수 없습니다: {path.name} "
                f"(collection_complete={completion})"
            )
    manifest: dict[str, Any] | None = None
    manifest_name: str | None = None
    if "source_manifest" in source.columns and not source.empty:
        candidate = source["source_manifest"].dropna()
        if not candidate.empty:
            manifest_name = str(candidate.iloc[0])
            manifest_path = path.parent / manifest_name
            if not manifest_path.exists():
                raise SystemExit(f"RTMS 수집 manifest가 없습니다: {manifest_path}")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not manifest.get("collection_complete"):
                raise SystemExit(f"미완료 RTMS manifest는 학습할 수 없습니다: {manifest_name}")
            if manifest.get("csv_file") != path.name:
                raise SystemExit(
                    f"RTMS manifest와 CSV가 일치하지 않습니다: {manifest_name}"
                )
    if is_new_collection and manifest is None:
        raise SystemExit(f"새 RTMS U 파일에는 완료 manifest가 필수입니다: {path.name}")
    unlabeled = pd.DataFrame(
        {
            "sido": source["sido"].map(canon_sido),
            "housing_type": source["housing_type"].map(HOUSING_MAP),
            "deposit_amount": pd.to_numeric(source["deposit_amount"], errors="coerce"),
            "reference_year": pd.to_numeric(source.get("deal_year"), errors="coerce"),
            "source_dataset": "RTMS_전세실거래_미라벨",
        }
    )
    unlabeled["observed_label"] = 0  # y=0가 아니라 관측상 미라벨(s=0)
    unlabeled["label_status"] = "unlabeled"
    source_metadata = {
        "manifest": manifest_name,
        "collection_complete": manifest.get("collection_complete") if manifest else None,
        "period": manifest.get("period") if manifest else {
            "start": (
                f"{int(source['deal_year'].min()):04d}{int(source['deal_month'].min()):02d}"
                if {"deal_year", "deal_month"}.issubset(source.columns) and not source.empty
                else None
            ),
            "end": (
                f"{int(source['deal_year'].max()):04d}{int(source['deal_month'].max()):02d}"
                if {"deal_year", "deal_month"}.issubset(source.columns) and not source.empty
                else None
            ),
        },
    }
    return unlabeled, path, source_metadata


def prepare_data() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    positives_raw = load_positives()
    unlabeled_raw, unlabeled_path, unlabeled_source_metadata = load_unlabeled()

    shared_sido = sorted(
        set(positives_raw["sido"].dropna()) & set(unlabeled_raw["sido"].dropna())
    )

    def clean(frame: pd.DataFrame) -> pd.DataFrame:
        output = frame.dropna(subset=["sido", "housing_type", "deposit_amount"]).copy()
        output = output[output["deposit_amount"] > 0]
        output = output[output["sido"].isin(shared_sido)]
        output["deposit_amount"] = output["deposit_amount"].round().astype("int64")
        output["log_deposit"] = np.log1p(output["deposit_amount"])
        output["feature_group"] = (
            output["sido"].astype(str)
            + "|"
            + output["housing_type"].astype(str)
            + "|"
            + output["deposit_amount"].astype(str)
        )
        return output.reset_index(drop=True)

    positives = clean(positives_raw)
    unlabeled = clean(unlabeled_raw)
    combined_deposits = pd.concat(
        [positives["deposit_amount"], unlabeled["deposit_amount"]], ignore_index=True
    ).to_numpy(dtype=float)

    sido_levels = shared_sido
    for frame in (positives, unlabeled):
        frame["sido"] = pd.Categorical(frame["sido"], categories=sido_levels)
        frame["housing_type"] = pd.Categorical(
            frame["housing_type"], categories=HOUSING_LEVELS
        )

    audit = {
        "positive_raw": int(len(positives_raw)),
        "unlabeled_raw": int(len(unlabeled_raw)),
        "positive_model_support": int(len(positives)),
        "unlabeled_model_support": int(len(unlabeled)),
        "positive_source_counts_raw": {
            str(key): int(value)
            for key, value in positives_raw["source_dataset"].value_counts().items()
        },
        "positive_source_counts_model_support": {
            str(key): int(value)
            for key, value in positives["source_dataset"].value_counts().items()
        },
        "shared_sido": shared_sido,
        "unlabeled_source": unlabeled_path.name,
        "unlabeled_source_kind": (
            "legacy_first_page_sample"
            if "controls_" in unlabeled_path.name
            else "pu_unlabeled_collection"
        ),
        "unlabeled_collection": unlabeled_source_metadata,
        "input_sources": {
            "positives": [
                {
                    "file": path.name,
                    "sha256": _sha256(path),
                }
                for path in CASE_FILES
            ],
            "unlabeled": {
                "file": unlabeled_path.name,
                "sha256": _sha256(unlabeled_path),
            },
        },
        "positive_reference_year_range": [
            int(positives["reference_year"].dropna().min()),
            int(positives["reference_year"].dropna().max()),
        ],
        "unlabeled_reference_year_range": [
            int(unlabeled["reference_year"].dropna().min()),
            int(unlabeled["reference_year"].dropna().max()),
        ],
        "deposit_amount_training_support": {
            "min": int(np.min(combined_deposits)),
            "max": int(np.max(combined_deposits)),
            "p001": int(np.quantile(combined_deposits, 0.001)),
            "p999": int(np.quantile(combined_deposits, 0.999)),
            "unit": "KRW",
        },
        "positive_exact_feature_duplicate_rate": round(
            float(positives.duplicated("feature_group").mean()), 4
        ),
        "unlabeled_exact_feature_duplicate_rate": round(
            float(unlabeled.duplicated("feature_group").mean()), 4
        ),
    }
    return positives, unlabeled, audit


def group_split(
    frame: pd.DataFrame, seed: int
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """동일 feature vector가 서로 다른 split에 들어가지 않게 70/15/15 분할한다."""
    from sklearn.model_selection import GroupShuffleSplit

    groups = frame["feature_group"]
    first = GroupShuffleSplit(n_splits=1, train_size=0.70, random_state=seed)
    train_idx, remaining_idx = next(first.split(frame, groups=groups))
    remaining = frame.iloc[remaining_idx]
    second = GroupShuffleSplit(n_splits=1, train_size=0.50, random_state=seed + 1)
    calibration_local, test_local = next(
        second.split(remaining, groups=remaining["feature_group"])
    )
    train = frame.iloc[train_idx].reset_index(drop=True)
    calibration = remaining.iloc[calibration_local].reset_index(drop=True)
    test = remaining.iloc[test_local].reset_index(drop=True)
    return train, calibration, test


def _multiplicity_weight(frame: pd.DataFrame) -> np.ndarray:
    """합성·API 반복행이 학습을 지배하지 않도록 exact feature 빈도의 제곱근 역가중."""
    counts = frame.groupby("feature_group", observed=True)["feature_group"].transform("size")
    weights = 1.0 / np.sqrt(counts.to_numpy(dtype=float))
    return weights / weights.mean()


def _model_frame(frame: pd.DataFrame, category_levels: dict[str, list[str]]) -> pd.DataFrame:
    output = frame[FEATURES].copy()
    for column in CATEGORICAL_FEATURES:
        output[column] = pd.Categorical(output[column], categories=category_levels[column])
    return output


def train_bagging_pu(
    positive_train: pd.DataFrame,
    unlabeled_train: pd.DataFrame,
    positive_calibration: pd.DataFrame,
    category_levels: dict[str, list[str]],
    n_bags: int,
    seed: int,
) -> tuple[list[Any], list[float]]:
    """P + bootstrap U temporary-negative bags; P_cal에서 Elkan–Noto c 추정."""
    from lightgbm import LGBMClassifier

    p_x = _model_frame(positive_train, category_levels)
    p_weights = _multiplicity_weight(positive_train)
    u_weights_all = _multiplicity_weight(unlabeled_train)
    p_cal_x = _model_frame(positive_calibration, category_levels)
    models: list[Any] = []
    c_estimates: list[float] = []

    for bag in range(n_bags):
        rng = np.random.default_rng(seed + bag)
        sampled = rng.choice(len(unlabeled_train), size=len(positive_train), replace=True)
        u_x = _model_frame(unlabeled_train.iloc[sampled], category_levels)
        train_x = pd.concat([p_x, u_x], ignore_index=True)
        train_y = np.concatenate(
            [np.ones(len(p_x), dtype=int), np.zeros(len(u_x), dtype=int)]
        )
        sample_weight = np.concatenate([p_weights, u_weights_all[sampled]])
        order = rng.permutation(len(train_x))

        model = LGBMClassifier(
            **MODEL_HYPERPARAMETERS,
            random_state=seed + bag,
        )
        model.fit(
            train_x.iloc[order],
            train_y[order],
            sample_weight=sample_weight[order],
            categorical_feature=CATEGORICAL_FEATURES,
        )
        c_value = float(model.predict_proba(p_cal_x)[:, 1].mean())
        models.append(model)
        c_estimates.append(float(np.clip(c_value, 0.05, 0.999)))
    return models, c_estimates


def ensemble_scores(
    models: list[Any],
    c_estimates: list[float],
    frame: pd.DataFrame,
    category_levels: dict[str, list[str]],
) -> dict[str, np.ndarray]:
    x = _model_frame(frame, category_levels)
    bag_matrix = np.vstack([model.predict_proba(x)[:, 1] for model in models])
    c_array = np.asarray(c_estimates, dtype=float)[:, None]
    en_matrix_unclipped = bag_matrix / c_array
    return {
        "pu_risk_score": bag_matrix.mean(axis=0),
        "bag_score_std": bag_matrix.std(axis=0),
        "en_corrected_score": np.clip(en_matrix_unclipped, 0.0, 1.0).mean(axis=0),
        "en_clip_mask": (en_matrix_unclipped > 1.0).any(axis=0),
        "bag_matrix": bag_matrix,
    }


def _sigmoid(value: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-value))


def apply_logit_shift(scores: np.ndarray, shift: float) -> np.ndarray:
    clipped = np.clip(np.asarray(scores, dtype=float), 1e-6, 1.0 - 1e-6)
    logits = np.log(clipped / (1.0 - clipped))
    return _sigmoid(logits + shift)


def fit_logit_shift(scores: np.ndarray, target_mean: float) -> float:
    """순위를 보존하면서 참조 집계 prior에 평균을 맞추는 intercept shift."""
    low, high = -30.0, 30.0
    for _ in range(120):
        middle = (low + high) / 2.0
        if float(apply_logit_shift(scores, middle).mean()) < target_mean:
            low = middle
        else:
            high = middle
    return (low + high) / 2.0


def load_reference_prior() -> tuple[float, str, str, str | None]:
    files = sorted(HOUSTA_DIR.glob("housta_region_risk_*.csv"))
    if not files:
        return 0.016, "fallback", "HOUSTA 전국 최근 3개월 사고율 기본값 1.6%", None
    source = files[-1]
    data = pd.read_csv(source)
    nationwide = data[(data["is_summary"] == 1) & (data["sido"] == "전국")]
    if nationwide.empty:
        return (
            0.016,
            source.name,
            "HOUSTA 전국 최근 3개월 사고율 기본값 1.6%",
            _sha256(source),
        )
    row = nationwide.iloc[0]
    prior = float(row["accident_rate_pct"]) / 100.0
    basis = str(row.get("basis") or "HOUSTA 전국 집계 사고율")
    return prior, source.name, basis, _sha256(source)


def _mean_pairwise_correlation(matrix: np.ndarray) -> float | None:
    if matrix.shape[0] < 2:
        return None
    correlation = np.corrcoef(matrix)
    upper = correlation[np.triu_indices_from(correlation, k=1)]
    finite = upper[np.isfinite(upper)]
    return float(finite.mean()) if len(finite) else None


def proxy_metrics(
    positive_scores: dict[str, np.ndarray],
    unlabeled_scores: dict[str, np.ndarray],
) -> dict[str, Any]:
    from sklearn.metrics import average_precision_score, roc_auc_score

    p = positive_scores["pu_risk_score"]
    u = unlabeled_scores["pu_risk_score"]
    labels = np.concatenate([np.ones(len(p), dtype=int), np.zeros(len(u), dtype=int)])
    scores = np.concatenate([p, u])
    ranking: dict[str, Any] = {}
    for top_fraction in (0.10, 0.20):
        threshold = float(np.quantile(u, 1.0 - top_fraction))
        u_selected = float(np.mean(u >= threshold))
        p_recall = float(np.mean(p >= threshold))
        ranking[f"top_{int(top_fraction * 100)}pct"] = {
            "unlabeled_threshold": round(threshold, 6),
            "unlabeled_selected_rate": round(u_selected, 4),
            "known_positive_recall": round(p_recall, 4),
            "proxy_lift": round(p_recall / max(u_selected, 1e-12), 2),
        }

    combined_bags = np.concatenate(
        [positive_scores["bag_matrix"], unlabeled_scores["bag_matrix"]], axis=1
    )
    pairwise = _mean_pairwise_correlation(combined_bags)
    return {
        "pu_proxy_roc_auc": round(float(roc_auc_score(labels, scores)), 4),
        "pu_proxy_pr_auc": round(float(average_precision_score(labels, scores)), 4),
        "ranking": ranking,
        "mean_bag_score_std": round(
            float(
                np.concatenate(
                    [positive_scores["bag_score_std"], unlabeled_scores["bag_score_std"]]
                ).mean()
            ),
            6,
        ),
        "mean_pairwise_bag_correlation": round(pairwise, 6) if pairwise is not None else None,
        "en_clip_rate": round(
            float(
                np.concatenate(
                    [positive_scores["en_clip_mask"], unlabeled_scores["en_clip_mask"]]
                ).mean()
            ),
            4,
        ),
        "metric_semantics": "P-vs-U proxy diagnostics; confirmed negative 기반 실제 성능이 아님",
    }


def _split_summary(
    positive_splits: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame],
    unlabeled_splits: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame],
) -> dict[str, Any]:
    names = ["train", "calibration", "test"]
    summary: dict[str, Any] = {}
    for label, splits in (("positive", positive_splits), ("unlabeled", unlabeled_splits)):
        summary[label] = {name: int(len(split)) for name, split in zip(names, splits)}
        group_sets = [set(split["feature_group"]) for split in splits]
        summary[label]["group_overlap_count"] = int(
            len(group_sets[0] & group_sets[1])
            + len(group_sets[0] & group_sets[2])
            + len(group_sets[1] & group_sets[2])
        )
    global_group_sets = [
        set(positive_splits[index]["feature_group"])
        | set(unlabeled_splits[index]["feature_group"])
        for index in range(3)
    ]
    summary["global_group_overlap_count"] = int(
        len(global_group_sets[0] & global_group_sets[1])
        + len(global_group_sets[0] & global_group_sets[2])
        + len(global_group_sets[1] & global_group_sets[2])
    )
    return summary


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    return value


def _dependency_versions() -> dict[str, str]:
    versions = {"python": sys.version.split()[0]}
    for package in ("numpy", "pandas", "scikit-learn", "lightgbm", "joblib"):
        try:
            versions[package] = importlib_metadata.version(package)
        except importlib_metadata.PackageNotFoundError:
            versions[package] = "not-installed"
    return versions


def predict_with_artifact(artifact: dict[str, Any], contracts: pd.DataFrame) -> pd.DataFrame:
    """저장 artifact의 최소 추론 계약. 범위 밖 입력은 점수 대신 NOT_SCORABLE을 반환한다."""
    required = {"sido", "housing_type", "deposit_amount"}
    missing = required - set(contracts.columns)
    if missing:
        raise ValueError(f"missing columns: {sorted(missing)}")
    preprocessing = artifact.get("preprocessing", {})
    sido_mapping = preprocessing.get("sido_canonical_mapping", SIDO_CANON)
    housing_mapping = preprocessing.get("housing_type_mapping", HOUSING_MAP)
    frame = contracts.copy()
    frame["sido"] = frame["sido"].map(
        lambda value: canon_sido_with_mapping(value, sido_mapping)
    )
    frame["housing_type"] = frame["housing_type"].map(
        lambda value: housing_mapping.get(value, value)
    )
    frame["deposit_amount"] = pd.to_numeric(frame["deposit_amount"], errors="coerce")
    supported_sido = set(artifact["category_levels"]["sido"])
    supported_housing = set(artifact["category_levels"]["housing_type"])

    reasons = pd.Series("", index=frame.index, dtype="object")

    def add_reason(mask: pd.Series, code: str) -> None:
        reasons.loc[mask] = reasons.loc[mask].map(
            lambda current: f"{current},{code}" if current else code
        )

    add_reason(frame["sido"].isna(), "MISSING_OR_INVALID_SIDO")
    add_reason(frame["sido"].notna() & ~frame["sido"].isin(supported_sido), "SIDO_OUT_OF_SUPPORT")
    add_reason(frame["housing_type"].isna(), "MISSING_HOUSING_TYPE")
    add_reason(
        frame["housing_type"].notna() & ~frame["housing_type"].isin(supported_housing),
        "HOUSING_TYPE_OUT_OF_SUPPORT",
    )
    invalid_deposit = (
        frame["deposit_amount"].isna()
        | ~np.isfinite(frame["deposit_amount"])
        | (frame["deposit_amount"] <= 0)
    )
    add_reason(invalid_deposit, "INVALID_DEPOSIT_AMOUNT")
    deposit_support = preprocessing.get("deposit_amount_training_support")
    if deposit_support:
        numeric_positive = ~invalid_deposit
        out_of_support = numeric_positive & (
            (frame["deposit_amount"] < float(deposit_support["min"]))
            | (frame["deposit_amount"] > float(deposit_support["max"]))
        )
        add_reason(out_of_support, "DEPOSIT_AMOUNT_OUT_OF_TRAINING_SUPPORT")
    valid = reasons.eq("")

    result = pd.DataFrame(
        {
            "pu_risk_score": np.nan,
            "risk_percentile": np.nan,
            "prior_aligned_estimate": np.nan,
            "prediction_status": np.where(valid, "SUCCESS", "NOT_SCORABLE"),
            "failure_reason": reasons.replace("", None),
            "calibration_status": np.where(
                valid,
                artifact["prediction_contract"]["calibration_status"],
                "NOT_APPLICABLE",
            ),
        },
        index=contracts.index,
    )
    if not valid.any():
        return result

    score_frame = frame.loc[valid].copy()
    score_frame["log_deposit"] = np.log1p(score_frame["deposit_amount"])
    scores = ensemble_scores(
        artifact["models"],
        artifact["c_estimates"],
        score_frame,
        artifact["category_levels"],
    )
    reference = np.asarray(artifact["unlabeled_reference_scores"], dtype=float)
    percentiles = np.searchsorted(np.sort(reference), scores["pu_risk_score"], side="right")
    percentiles = percentiles / max(len(reference), 1)
    result.loc[valid, "pu_risk_score"] = scores["pu_risk_score"]
    result.loc[valid, "risk_percentile"] = percentiles
    result.loc[valid, "prior_aligned_estimate"] = apply_logit_shift(
        scores["pu_risk_score"], artifact["prior_logit_shift"]
    )
    return result


def render_report(metrics: dict[str, Any]) -> str:
    ranking = metrics["proxy_metrics"]["ranking"]
    limitations = "\n".join(f"- {item}" for item in metrics["limitations"])
    sources = "\n".join(
        f"| {key} | {value:,} |"
        for key, value in metrics["data_audit"]["positive_source_counts_model_support"].items()
    )
    return f"""# 사고위험 PU Learning PoC — {metrics['trained_at']}

## 결론

발제사 조언에 따라 RTMS 전세 실거래를 확정 정상으로 두지 않고 **미라벨(U)** 로 처리했다.
실제 사고목록과 RTMS를 계약 단위로 제외 조인할 공통키가 없으므로, 기존 case-control은
비교 baseline으로만 유지하고 LightGBM bagging PU를 주 PoC로 사용한다.

출력은 검증된 개별 사고확률이 아니다. PoC 기본 출력은 `pu_risk_score`와 포트폴리오
`risk_percentile`이며, `prior_aligned_estimate`는 HOUSTA 집계 사고율에 평균을 맞춘
`aggregate_prior_aligned_unvalidated` 추정치다.

## 표본

| 구분 | 건수 |
|---|---:|
| 알려진 사고 P | {metrics['data_audit']['positive_model_support']:,} |
| RTMS 미라벨 U | {metrics['data_audit']['unlabeled_model_support']:,} |
| 공통 시도 | {len(metrics['data_audit']['shared_sido'])} |
| bag 수 | {metrics['n_bags']} |

### P 원천별 실제 모델 포함 건수

| 원천 | 건수 |
|---|---:|
{sources}

P와 U를 합친 뒤 동일 feature vector가 train/calibration/test 사이에 중복되지 않도록
전역 그룹 분할했다(global overlap={metrics['split']['global_group_overlap_count']}).
P split={metrics['split']['positive']}, U split={metrics['split']['unlabeled']}.

## Proxy 진단

확정 정상 라벨이 없으므로 아래 ROC/PR은 실제 사고예측 성능이 아니라 **P와 U의 분리도**다.
Brier·정확도·ECE는 계산하지 않았다.

| 지표 | 값 |
|---|---:|
| P-vs-U proxy ROC-AUC | {metrics['proxy_metrics']['pu_proxy_roc_auc']} |
| P-vs-U proxy PR-AUC | {metrics['proxy_metrics']['pu_proxy_pr_auc']} |
| U 상위 10% 기준 P recall | {ranking['top_10pct']['known_positive_recall']} |
| U 상위 10% 기준 proxy lift | {ranking['top_10pct']['proxy_lift']} |
| U 상위 20% 기준 P recall | {ranking['top_20pct']['known_positive_recall']} |
| 평균 bag score 표준편차 | {metrics['proxy_metrics']['mean_bag_score_std']} |
| bag 평균 상관 | {metrics['proxy_metrics']['mean_pairwise_bag_correlation']} |
| Elkan–Noto 1 초과 clip 비율 | {metrics['proxy_metrics']['en_clip_rate']} |
| c 평균 ± 표준편차 | {metrics['c_mean']} ± {metrics['c_std']} |

높은 proxy AUC는 합성 P와 RTMS U의 데이터 출처 차이를 포함하므로 기존 case-control
0.921보다 좋아졌다는 의미가 아니다.

## 집계 prior 정렬

| 항목 | 값 |
|---|---|
| 참조 prior | {metrics['reference_prior']:.4%} |
| 출처 | {metrics['reference_prior_source']} |
| 출처 SHA-256 | {metrics['reference_prior_sha256'] or 'fallback-no-file'} |
| 근거 | {metrics['reference_prior_basis']} |
| calibration U 평균 | {metrics['prior_alignment']['calibration_mean']:.4%} |
| 독립 test U 평균 | {metrics['prior_alignment']['test_mean']:.4%} |
| test 정렬 오차 | {metrics['prior_alignment']['test_gap']:.4%} |
| 상태 | `aggregate_prior_aligned_unvalidated` |

## 산출물

- 모델: `{metrics['artifact_file']}`
- 모델 SHA-256: `{metrics['artifact_sha256']}`
- 지표: `{metrics['metrics_file']}`
- 재현성: seed={metrics['seed']}, bag={metrics['n_bags']}

## 한계

{limitations}

## 운영 승격 조건

1. HUG 보증계약키·사고 여부·관찰종료일이 연결된 성숙 코호트를 확보한다.
2. 실제 정상 종료계약으로 시간순·임대인/물건 그룹 외부검증을 수행한다.
3. 실제 모집단 class prior를 다시 추정하고 Platt/isotonic calibration을 비교한다.
4. Brier·ECE·PR-AUC와 검토용량별 recall/precision을 검증한 뒤 API/UI에 연결한다.
"""


def run(n_bags: int, seed: int) -> dict[str, Any]:
    import joblib

    positives, unlabeled, audit = prepare_data()

    # P와 U를 따로 분할하면 동일 feature vector가 P_train↔U_test처럼 교차 출처로
    # 새어 들어갈 수 있다. 두 출처를 합친 뒤 feature_group을 전역 분할한다.
    combined = pd.concat([positives, unlabeled], ignore_index=True)
    combined_splits = group_split(combined, seed)
    p_splits = tuple(
        split[split["label_status"] == "positive"].reset_index(drop=True)
        for split in combined_splits
    )
    u_splits = tuple(
        split[split["label_status"] == "unlabeled"].reset_index(drop=True)
        for split in combined_splits
    )
    p_train, p_cal, p_test = p_splits
    u_train, u_cal, u_test = u_splits
    split = _split_summary(p_splits, u_splits)
    if split["global_group_overlap_count"]:
        raise RuntimeError("feature_group leakage detected")

    category_levels = {
        "sido": audit["shared_sido"],
        "housing_type": HOUSING_LEVELS,
    }
    models, c_estimates = train_bagging_pu(
        p_train, u_train, p_cal, category_levels, n_bags=n_bags, seed=seed
    )
    p_test_scores = ensemble_scores(models, c_estimates, p_test, category_levels)
    u_test_scores = ensemble_scores(models, c_estimates, u_test, category_levels)
    u_cal_scores = ensemble_scores(models, c_estimates, u_cal, category_levels)
    all_u_scores = ensemble_scores(models, c_estimates, unlabeled, category_levels)
    diagnostics = proxy_metrics(p_test_scores, u_test_scores)

    reference_prior, prior_source, prior_basis, prior_sha256 = load_reference_prior()
    prior_shift = fit_logit_shift(u_cal_scores["pu_risk_score"], reference_prior)
    prior_cal = apply_logit_shift(u_cal_scores["pu_risk_score"], prior_shift)
    prior_test = apply_logit_shift(u_test_scores["pu_risk_score"], prior_shift)

    historical: dict[str, Any] | None = None
    old_metrics = sorted(ML_DIR.glob("accident_clf_poc_metrics_*.json"))
    if old_metrics:
        old = json.loads(old_metrics[-1].read_text(encoding="utf-8"))
        historical = {
            "file": old_metrics[-1].name,
            "proxy_roc_auc": old.get("roc_auc"),
            "proxy_pr_auc": old.get("pr_auc"),
            "semantics": "RTMS를 확정 negative로 둔 과거 case-control 비교 baseline",
        }

    metrics: dict[str, Any] = {
        "trained_at": date.today().isoformat(),
        "model": "accident_clf_pu_poc",
        "algorithm": "LightGBM bagging PU + Elkan-Noto diagnostic",
        "model_hyperparameters": MODEL_HYPERPARAMETERS,
        "training_script": {
            "file": Path(__file__).name,
            "sha256": _sha256(Path(__file__).resolve()),
        },
        "seed": seed,
        "n_bags": n_bags,
        "features": FEATURES,
        "dependency_versions": _dependency_versions(),
        "data_audit": audit,
        "split": split,
        "proxy_metrics": diagnostics,
        "c_estimates": [round(value, 6) for value in c_estimates],
        "c_mean": round(float(np.mean(c_estimates)), 6),
        "c_std": round(float(np.std(c_estimates)), 6),
        "reference_prior": reference_prior,
        "reference_prior_source": prior_source,
        "reference_prior_sha256": prior_sha256,
        "reference_prior_basis": prior_basis,
        "prior_logit_shift": round(prior_shift, 8),
        "prior_alignment": {
            "calibration_mean": float(prior_cal.mean()),
            "test_mean": float(prior_test.mean()),
            "test_gap": float(prior_test.mean() - reference_prior),
        },
        "historical_case_control_baseline": historical,
        "probability_metrics_not_reported": ["brier", "ece", "accuracy"],
        "prediction_contract": {
            "primary_output": "pu_risk_score + risk_percentile",
            "probability_output": "prior_aligned_estimate",
            "calibration_status": "AGGREGATE_PRIOR_ALIGNED_UNVALIDATED",
            "invalid_input_behavior": "NOT_SCORABLE",
            "automatic_decision_allowed": False,
        },
        "limitations": [
            "P는 합성 사고군이며 임의 표집(SCAR) 가정을 충족한다고 검증되지 않았다.",
            "U는 HUG 보증가입 모집단이 아닌 RTMS 전체 전세실거래로 실제 사고가 일부 포함될 수 있다.",
            "P와 U의 지역·주택유형·보증금 분포가 달라 모델이 사고위험과 데이터 출처 차이를 함께 학습할 수 있다.",
            "P의 기준연도는 보증종료연도, U는 거래연도라 현 데이터로 시간순 외부검증을 할 수 없다.",
            "원본 P 95,122건 중 공통 지역 support에 남은 18,054건만 학습했으며, 세종에 집중된 전세가율 사고원천 69,435건은 U에 세종 표본이 없어 전량 제외됐다.",
            (
                "RTMS 기존 파일은 일부 시군구·월의 첫 페이지 중심 표본이라 전국 대표성이 없다."
                if audit["unlabeled_source_kind"] == "legacy_first_page_sample"
                else "RTMS U는 일부 대표 시군구 층화표본이라 전국 및 HUG 보증가입 모집단을 대표하지 않는다."
            ),
            "HOUSTA 1.6%는 공개 집계 기준의 참조 prior이며 RTMS 개별계약의 동일 코호트 사고율이 아니다.",
            "확정 정상 라벨이 없어 proxy ROC/PR을 실제 HUG 성능으로 해석할 수 없다.",
        ],
    }

    ML_DIR.mkdir(parents=True, exist_ok=True)
    artifact_path = ML_DIR / f"accident_clf_pu_poc_{TODAY}.joblib"
    metrics_path = ML_DIR / f"accident_clf_pu_poc_metrics_{TODAY}.json"
    report_path = ML_DIR / "ACCIDENT_MODEL_PU_POC_README.md"
    artifact = {
        "artifact_schema_version": 1,
        "model_name": metrics["model"],
        "models": models,
        "c_estimates": c_estimates,
        "features": FEATURES,
        "category_levels": category_levels,
        "preprocessing": {
            "version": 1,
            "sido_canonical_mapping": SIDO_CANON,
            "housing_type_mapping": HOUSING_MAP,
            "deposit_amount_rule": "finite numeric > 0; training rounds to KRW integer",
            "log_deposit_transform": "numpy.log1p",
            "feature_group": "sido|housing_type|rounded_deposit_amount",
            "deposit_amount_training_support": audit[
                "deposit_amount_training_support"
            ],
        },
        "model_hyperparameters": MODEL_HYPERPARAMETERS,
        "prior_logit_shift": prior_shift,
        "target_prior": reference_prior,
        "unlabeled_reference_scores": all_u_scores["pu_risk_score"].astype("float32"),
        "prediction_contract": metrics["prediction_contract"],
        "training_summary": {
            "trained_at": metrics["trained_at"],
            "seed": seed,
            "n_bags": n_bags,
            "positive_count": len(positives),
            "unlabeled_count": len(unlabeled),
            "unlabeled_source": audit["unlabeled_source"],
            "input_sources": audit["input_sources"],
            "reference_prior_source": {
                "file": prior_source,
                "sha256": prior_sha256,
            },
            "dependency_versions": metrics["dependency_versions"],
            "training_script": metrics["training_script"],
        },
    }
    joblib.dump(artifact, artifact_path, compress=3)

    # 저장/재로딩 및 최소 추론 계약 검증
    loaded = joblib.load(artifact_path)
    smoke_input = u_test[["sido", "housing_type", "deposit_amount"]].head(5).copy()
    smoke = predict_with_artifact(loaded, smoke_input)
    if (
        not smoke["prediction_status"].eq("SUCCESS").all()
        or not smoke["prior_aligned_estimate"].between(0, 1).all()
    ):
        raise RuntimeError("artifact smoke prediction failed")
    invalid_smoke = predict_with_artifact(
        loaded,
        pd.DataFrame(
            [
                {"sido": "제주특별자치도", "housing_type": "아파트", "deposit_amount": 1},
                {"sido": "서울특별시", "housing_type": "빌라", "deposit_amount": 1},
                {"sido": "서울특별시", "housing_type": "아파트", "deposit_amount": -1},
                {"sido": "서울특별시", "housing_type": "아파트", "deposit_amount": 1},
                {
                    "sido": "서울특별시",
                    "housing_type": "아파트",
                    "deposit_amount": 10**15,
                },
            ]
        ),
    )
    if (
        not invalid_smoke["prediction_status"].eq("NOT_SCORABLE").all()
        or invalid_smoke["prior_aligned_estimate"].notna().any()
    ):
        raise RuntimeError("artifact invalid-input guard failed")

    metrics["artifact_file"] = artifact_path.name
    metrics["artifact_sha256"] = _sha256(artifact_path)
    metrics["metrics_file"] = metrics_path.name
    metrics["report_file"] = report_path.name
    metrics["smoke_prediction_rows"] = int(len(smoke))
    metrics["invalid_input_smoke_rows"] = int(len(invalid_smoke))
    serializable = _json_ready(metrics)
    metrics_path.write_text(
        json.dumps(serializable, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    report_path.write_text(render_report(serializable), encoding="utf-8")
    return serializable


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="사고위험 bagging PU PoC 학습")
    parser.add_argument("--bags", type=int, default=10, help="PU bag 개수(default: 10)")
    parser.add_argument("--seed", type=int, default=42, help="재현 seed(default: 42)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.bags < 2:
        raise SystemExit("--bags는 2 이상이어야 합니다.")
    metrics = run(n_bags=args.bags, seed=args.seed)
    ranking = metrics["proxy_metrics"]["ranking"]
    print(
        f"P={metrics['data_audit']['positive_model_support']:,} / "
        f"U={metrics['data_audit']['unlabeled_model_support']:,}"
    )
    print(
        f"proxy ROC-AUC={metrics['proxy_metrics']['pu_proxy_roc_auc']} · "
        f"PR-AUC={metrics['proxy_metrics']['pu_proxy_pr_auc']}"
    )
    print(
        f"P recall@U top10%={ranking['top_10pct']['known_positive_recall']} · "
        f"prior test mean={metrics['prior_alignment']['test_mean']:.4%}"
    )
    print(f"→ {metrics['artifact_file']}")
    print(f"→ {metrics['metrics_file']}")
    print(f"→ {metrics['report_file']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

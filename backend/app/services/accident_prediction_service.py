"""사고 전 계약용 PU 사고위험 PoC 추론·저장 서비스.

학습 artifact에 포함된 전처리 사전, category support, bagging model, 참조 U 점수와 prior
shift만 사용한다. 학습 스크립트를 import하지 않으므로 배포 환경에서도 artifact 자체로 추론이
가능하다. 출력값은 담당자 보조용 PoC이며 사고 접수나 보증이행을 자동 생성하지 않는다.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from app.core.config import get_settings
from app.core.exceptions import (
    ModelInferenceFailedError,
    ResourceNotFoundError,
    StateConflictError,
)
from app.repositories.contract_repository import ContractRepository
from app.repositories.prevention_repository import AccidentPredictionRepository
from app.repositories.property_repository import PropertyRepository
from app.schemas.hug_contract import AccidentPredictionResponse
from app.schemas.provenance import source_metadata
from app.utils.datetime_utils import new_uuid, now_kst_iso

MODEL_BASIS = (
    "합성 사고군 P와 RTMS 사고여부 미확인 U를 사용한 bagging PU PoC. "
    "개별 계약의 검증된 실제 사고확률이 아니며 자동 업무판정에 사용할 수 없음"
)
VALIDITY_DAYS = 30

PRE_INCIDENT_STATUSES: tuple[str, ...] = (
    "ContractFinalized",
    "Monitoring",
    "D90Requested",
    "ReturnPlanSubmitted",
    "AtRisk",
)

# 플랫폼 계약 enum을 학습 artifact의 네 범주로 변환한다. OTHER는 안전하게 NOT_SCORABLE이다.
BACKEND_HOUSING_MAP: dict[str, str] = {
    "APARTMENT": "아파트",
    "MULTI_FAMILY": "연립다세대",
    "ROW_HOUSE": "연립다세대",
    "MULTI_HOUSEHOLD": "단독다가구",
    "SINGLE_FAMILY": "단독다가구",
    "OFFICETEL": "오피스텔",
}

FEATURE_LABELS = {
    "sido": "지역",
    "housing_type": "주택유형",
    "log_deposit": "보증금",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_path() -> Path:
    directory = Path(get_settings().data_dir) / "processed" / "ml"
    candidates = sorted(directory.glob("accident_clf_pu_poc_*.joblib"))
    if not candidates:
        raise ModelInferenceFailedError(
            "사고위험 PU 모델 artifact가 없습니다. build_accident_model_pu.py를 실행하세요."
        )
    return candidates[-1]


@lru_cache(maxsize=4)
def _load_artifact_cached(path_text: str, modified_ns: int) -> dict[str, Any]:
    del modified_ns  # cache key에만 사용해 파일 교체 시 자동 재로딩한다.
    path = Path(path_text)
    try:
        artifact = joblib.load(path)
    except Exception as exc:  # noqa: BLE001 - joblib/lightgbm 역직렬화 오류를 API 오류로 변환
        raise ModelInferenceFailedError(f"사고위험 모델을 읽을 수 없습니다: {path.name}") from exc
    required = {
        "artifact_schema_version",
        "model_name",
        "models",
        "features",
        "category_levels",
        "preprocessing",
        "prior_logit_shift",
        "unlabeled_reference_scores",
        "prediction_contract",
    }
    missing = sorted(required - set(artifact))
    if missing or artifact.get("artifact_schema_version") != 1:
        raise ModelInferenceFailedError(
            "사고위험 모델 artifact 계약이 맞지 않습니다.",
            details={"missing": missing, "schema_version": artifact.get("artifact_schema_version")},
        )
    if not artifact["models"] or artifact["features"] != ["sido", "housing_type", "log_deposit"]:
        raise ModelInferenceFailedError("지원하지 않는 사고위험 모델 artifact입니다.")
    return artifact


def _load_artifact() -> tuple[dict[str, Any], Path, str]:
    path = _artifact_path()
    artifact = _load_artifact_cached(str(path.resolve()), path.stat().st_mtime_ns)
    return artifact, path, _sha256(path)


def _canonical_sido(value: object, mapping: dict[str, str]) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    head = value.strip().split()[0]
    for short, canonical in mapping.items():
        if head.startswith(short) or head.startswith(canonical):
            return canonical
    return None


def _normalize_housing(value: object, artifact_mapping: dict[str, str]) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    backend_value = BACKEND_HOUSING_MAP.get(raw, raw)
    return artifact_mapping.get(backend_value, backend_value)


def _extract_sido(property_doc: dict[str, Any] | None) -> str | None:
    if not property_doc:
        return None
    address = property_doc.get("address") or {}
    for key in ("sido", "road_address", "jibun_address"):
        value = address.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().split()[0]
    return None


def _sigmoid(value: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-value))


def _apply_logit_shift(scores: np.ndarray, shift: float) -> np.ndarray:
    clipped = np.clip(np.asarray(scores, dtype=float), 1e-6, 1.0 - 1e-6)
    logits = np.log(clipped / (1.0 - clipped))
    return _sigmoid(logits + shift)


def _fingerprint(
    contract_id: str,
    model_sha256: str,
    snapshot: dict[str, Any],
    refresh_cycle: str | None = None,
) -> str:
    encoded = json.dumps(
        {
            "contract_id": contract_id,
            "model_sha256": model_sha256,
            "input": snapshot,
            "refresh_cycle": refresh_cycle,
        },
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _prediction_response(document: dict[str, Any]) -> AccidentPredictionResponse:
    return AccidentPredictionResponse(
        prediction_id=document["_id"],
        contract_id=document["contract_id"],
        pu_risk_score=document.get("pu_risk_score"),
        risk_percentile=document.get("risk_percentile"),
        accident_probability=document.get("accident_probability"),
        calibration_status=document["calibration_status"],
        prediction_status=document["prediction_status"],
        failure_reason=document.get("failure_reason", []),
        model_version=document["model_version"],
        model_sha256=document["model_sha256"],
        feature_snapshot=document.get("feature_snapshot", {}),
        top_factors=document.get("top_factors", []),
        data_completeness=document.get("data_completeness", 0.0),
        basis=document["basis"],
        predicted_at=document["predicted_at"],
        valid_until=document["valid_until"],
        source=document["source"],
    )


class AccidentPredictionService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._db = db
        self._contracts = ContractRepository(db)
        self._properties = PropertyRepository(db)
        self._predictions = AccidentPredictionRepository(db)

    def _predict_features(
        self,
        *,
        sido_raw: object,
        housing_raw: object,
        deposit_raw: object,
        artifact: dict[str, Any],
    ) -> dict[str, Any]:
        preprocessing = artifact["preprocessing"]
        sido = _canonical_sido(sido_raw, preprocessing["sido_canonical_mapping"])
        housing = _normalize_housing(housing_raw, preprocessing["housing_type_mapping"])
        try:
            deposit = float(deposit_raw) if deposit_raw is not None else float("nan")
        except (TypeError, ValueError):
            deposit = float("nan")

        supported_sido = set(artifact["category_levels"]["sido"])
        supported_housing = set(artifact["category_levels"]["housing_type"])
        failures: list[str] = []
        if sido is None:
            failures.append("MISSING_OR_INVALID_SIDO")
        elif sido not in supported_sido:
            failures.append("SIDO_OUT_OF_SUPPORT")
        if housing is None:
            failures.append("MISSING_HOUSING_TYPE")
        elif housing not in supported_housing:
            failures.append("HOUSING_TYPE_OUT_OF_SUPPORT")
        if not np.isfinite(deposit) or deposit <= 0:
            failures.append("INVALID_DEPOSIT_AMOUNT")
        else:
            support = preprocessing.get("deposit_amount_training_support")
            if support and not float(support["min"]) <= deposit <= float(support["max"]):
                failures.append("DEPOSIT_AMOUNT_OUT_OF_TRAINING_SUPPORT")

        snapshot = {
            "sido_raw": sido_raw,
            "sido": sido,
            "housing_type_raw": housing_raw,
            "housing_type": housing,
            "deposit_amount": int(deposit) if np.isfinite(deposit) else None,
        }
        completeness = round(
            sum(value is not None for value in (sido_raw, housing_raw, deposit_raw)) / 3.0, 4
        )
        if failures:
            return {
                "prediction_status": "NOT_SCORABLE",
                "failure_reason": failures,
                "feature_snapshot": snapshot,
                "data_completeness": completeness,
                "pu_risk_score": None,
                "risk_percentile": None,
                "accident_probability": None,
                "top_factors": [],
            }

        frame = pd.DataFrame(
            {
                "sido": pd.Categorical([sido], categories=artifact["category_levels"]["sido"]),
                "housing_type": pd.Categorical(
                    [housing], categories=artifact["category_levels"]["housing_type"]
                ),
                "log_deposit": [float(np.log1p(deposit))],
            }
        )[artifact["features"]]
        try:
            bag_scores = np.asarray(
                [model.predict_proba(frame)[:, 1][0] for model in artifact["models"]],
                dtype=float,
            )
        except Exception as exc:  # noqa: BLE001
            raise ModelInferenceFailedError("사고위험 PU 모델 추론에 실패했습니다.") from exc
        pu_score = float(bag_scores.mean())
        reference = np.sort(np.asarray(artifact["unlabeled_reference_scores"], dtype=float))
        percentile = float(np.searchsorted(reference, pu_score, side="right") / max(len(reference), 1))
        prior_aligned = float(
            _apply_logit_shift(np.asarray([pu_score]), float(artifact["prior_logit_shift"]))[0]
        )

        feature_importance = np.mean(
            [np.asarray(model.feature_importances_, dtype=float) for model in artifact["models"]],
            axis=0,
        )
        total_importance = float(feature_importance.sum()) or 1.0
        values = {"sido": sido, "housing_type": housing, "log_deposit": int(deposit)}
        order = np.argsort(-feature_importance)
        factors = [
            {
                "feature": artifact["features"][index],
                "label": FEATURE_LABELS[artifact["features"][index]],
                "value": values[artifact["features"][index]],
                "importance": round(float(feature_importance[index] / total_importance), 4),
                "explanation_method": "ensemble_global_feature_importance",
            }
            for index in order
        ]
        return {
            "prediction_status": "SUCCESS",
            "failure_reason": [],
            "feature_snapshot": snapshot,
            "data_completeness": completeness,
            "pu_risk_score": round(pu_score, 6),
            "risk_percentile": round(percentile, 6),
            "accident_probability": round(prior_aligned, 6),
            "top_factors": factors,
        }

    async def refresh_contract(self, contract_id: str) -> AccidentPredictionResponse:
        contract = await self._contracts.get_by_id(contract_id)
        if not contract:
            raise ResourceNotFoundError("사고위험을 예측할 계약을 찾을 수 없습니다.")
        current_status = contract.get("contract_status")
        if current_status not in PRE_INCIDENT_STATUSES:
            raise StateConflictError(
                "사고 전 관리 상태의 계약만 사고위험을 예측할 수 있습니다.",
                details={
                    "contract_id": contract_id,
                    "current_status": current_status,
                    "allowed_statuses": list(PRE_INCIDENT_STATUSES),
                },
            )
        property_doc = await self._properties.get_by_id(contract.get("property_id", ""))
        artifact, path, model_sha256 = _load_artifact()
        model_version = path.stem
        prediction = self._predict_features(
            sido_raw=_extract_sido(property_doc),
            housing_raw=contract.get("housing_type"),
            deposit_raw=contract.get("deposit"),
            artifact=artifact,
        )
        predicted_at = now_kst_iso()
        predicted_datetime = datetime.fromisoformat(predicted_at)
        fingerprint = _fingerprint(contract_id, model_sha256, prediction["feature_snapshot"])
        existing = await self._predictions.find_by_fingerprint(contract_id, fingerprint)
        if existing:
            try:
                if datetime.fromisoformat(existing["valid_until"]) >= predicted_datetime:
                    return _prediction_response(existing)
            except (KeyError, TypeError, ValueError):
                pass
            fingerprint = _fingerprint(
                contract_id,
                model_sha256,
                prediction["feature_snapshot"],
                refresh_cycle=predicted_at[:10],
            )
            refreshed_today = await self._predictions.find_by_fingerprint(
                contract_id, fingerprint
            )
            if refreshed_today:
                return _prediction_response(refreshed_today)

        valid_until = (predicted_datetime + timedelta(days=VALIDITY_DAYS)).isoformat()
        is_demo = contract_id.startswith("demo-") or bool(contract.get("is_demo"))
        scenario_id = contract.get("scenario_id")
        source = source_metadata(
            data_mode="DEMO" if is_demo else "REFERENCE",
            source_type="model_poc",
            source_dataset=artifact.get("training_summary", {}).get(
                "unlabeled_source", "accident_clf_pu_poc"
            ),
            as_of_date=predicted_at[:10],
            scenario_id=scenario_id,
            model_version=model_version,
            input_snapshot=prediction["feature_snapshot"],
            basis=MODEL_BASIS,
            is_demo=is_demo,
        )
        document = {
            "_id": new_uuid(),
            "contract_id": contract_id,
            **prediction,
            "calibration_status": artifact["prediction_contract"].get(
                "calibration_status", "AGGREGATE_PRIOR_ALIGNED_UNVALIDATED"
            ),
            "model_version": model_version,
            "model_sha256": model_sha256,
            "feature_fingerprint": fingerprint,
            "basis": MODEL_BASIS,
            "predicted_at": predicted_at,
            "valid_until": valid_until,
            "source": source,
        }
        try:
            await self._predictions.insert(document)
        except DuplicateKeyError:
            # 여러 워커가 동시에 같은 계약을 갱신한 경우 unique fingerprint 승자를 반환한다.
            winner = await self._predictions.find_by_fingerprint(contract_id, fingerprint)
            if winner:
                return _prediction_response(winner)
            raise
        return _prediction_response(document)

    async def record_failure(
        self, contract_id: str, error: ModelInferenceFailedError
    ) -> AccidentPredictionResponse:
        """모델 장애도 계약별 prediction 이력으로 남겨 업무목록에서 누락되지 않게 한다."""
        contract = await self._contracts.get_by_id(contract_id)
        if not contract:
            raise ResourceNotFoundError("사고위험을 예측할 계약을 찾을 수 없습니다.")
        property_doc = await self._properties.get_by_id(contract.get("property_id", ""))
        snapshot = {
            "sido_raw": _extract_sido(property_doc),
            "housing_type_raw": contract.get("housing_type"),
            "deposit_amount": contract.get("deposit"),
        }
        predicted_at = now_kst_iso()
        model_version = "accident_clf_pu_poc_unavailable"
        model_sha256 = "unavailable"
        fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "contract_id": contract_id,
                    "status": "FAILED",
                    "date": predicted_at[:10],
                    "reason": error.message,
                    "input": snapshot,
                },
                sort_keys=True,
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()
        existing = await self._predictions.find_by_fingerprint(contract_id, fingerprint)
        if existing:
            return _prediction_response(existing)
        present = sum(snapshot.get(key) is not None for key in snapshot)
        is_demo = contract_id.startswith("demo-") or bool(contract.get("is_demo"))
        source = source_metadata(
            data_mode="DEMO" if is_demo else "REFERENCE",
            source_type="model_poc",
            source_dataset="accident_clf_pu_poc",
            as_of_date=predicted_at[:10],
            scenario_id=contract.get("scenario_id"),
            model_version=model_version,
            input_snapshot=snapshot,
            basis=MODEL_BASIS,
            is_demo=is_demo,
        )
        document = {
            "_id": new_uuid(),
            "contract_id": contract_id,
            "pu_risk_score": None,
            "risk_percentile": None,
            "accident_probability": None,
            "calibration_status": "NOT_APPLICABLE",
            "prediction_status": "FAILED",
            "failure_reason": ["MODEL_INFERENCE_FAILED", error.message],
            "model_version": model_version,
            "model_sha256": model_sha256,
            "feature_snapshot": snapshot,
            "top_factors": [],
            "data_completeness": round(present / 3.0, 4),
            "feature_fingerprint": fingerprint,
            "basis": MODEL_BASIS,
            "predicted_at": predicted_at,
            "valid_until": (
                datetime.fromisoformat(predicted_at) + timedelta(days=1)
            ).isoformat(),
            "source": source,
        }
        try:
            await self._predictions.insert(document)
        except DuplicateKeyError:
            winner = await self._predictions.find_by_fingerprint(contract_id, fingerprint)
            if winner:
                return _prediction_response(winner)
            raise
        return _prediction_response(document)

    async def refresh_or_record_failure(
        self, contract_id: str
    ) -> AccidentPredictionResponse:
        """단건 API에서도 모델 장애를 계약별 FAILED 이력으로 반환한다."""
        try:
            return await self.refresh_contract(contract_id)
        except ModelInferenceFailedError as exc:
            return await self.record_failure(contract_id, exc)

    async def latest(self, contract_id: str) -> AccidentPredictionResponse:
        if not await self._contracts.exists(contract_id):
            raise ResourceNotFoundError("계약 정보를 찾을 수 없습니다.")
        document = await self._predictions.latest_for_contract(contract_id)
        if not document:
            raise ResourceNotFoundError("계약의 사고위험 예측 이력이 없습니다.")
        return _prediction_response(document)

    async def refresh_batch(
        self, contract_ids: list[str] | None = None, data_mode: str = "LIVE"
    ) -> dict[str, Any]:
        if data_mode not in {"LIVE", "DEMO"}:
            raise ValueError("data_mode must be LIVE or DEMO")
        mode_query = (
            {
                "$or": [
                    {"_id": {"$regex": "^demo-"}},
                    {"is_demo": True},
                    {"source.data_mode": "DEMO"},
                ]
            }
            if data_mode == "DEMO"
            else {
                "_id": {"$not": {"$regex": "^demo-"}},
                "is_demo": {"$ne": True},
                "source.data_mode": {"$ne": "DEMO"},
            }
        )
        # contract_ids를 최상위 "_id" 키로 병합하면 LIVE mode_query의 "^demo-"
        # 제외 조건("_id": {"$not": ...})을 덮어쓴다. $and로 결합해 명시 ID를
        # 지정해도 모집단 분리 조건이 항상 함께 적용되게 한다.
        filters: list[dict[str, Any]] = [
            {"contract_status": {"$in": list(PRE_INCIDENT_STATUSES)}},
            mode_query,
        ]
        if contract_ids is not None:
            filters.append({"_id": {"$in": contract_ids}})
        query: dict[str, Any] = {"$and": filters}
        contracts = [document async for document in self._contracts.collection.find(query)]
        items: list[AccidentPredictionResponse] = []
        failed: list[dict[str, str]] = []
        for contract in contracts:
            result = await self.refresh_or_record_failure(contract["_id"])
            items.append(result)
            if result.prediction_status == "FAILED":
                failed.append(
                    {
                        "contract_id": contract["_id"],
                        "reason": ", ".join(result.failure_reason),
                    }
                )
        return {
            "requested": len(contracts),
            "succeeded": len(items) - len(failed),
            "failed": len(failed),
            "items": items,
            "failures": failed,
            "data_mode_filter": data_mode,
        }

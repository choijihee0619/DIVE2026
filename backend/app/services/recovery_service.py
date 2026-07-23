"""등록 채권의 회수 상태·원장·예측·종결 유즈케이스.

중요 원칙
- 법무/경매/상환 상태는 병렬 축으로 기록한다.
- 원장은 append-only이며 입금 충당은 구성항목별 명시 배분만 허용한다.
- 종결 채권은 모든 변경/재예측을 거부하고 이력 조회만 제공한다.
- 기존 합성데이터 기반 LightGBM 모델을 재사용하되 입력, 버전, 산출물을 저장한다.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.core.exceptions import (
    ResourceNotFoundError,
    StateConflictError,
    ValidationAppError,
)
from app.repositories.recovery_repository import (
    RecoveryAuctionCaseRepository,
    RecoveryClaimRepository,
    RecoveryEventRepository,
    RecoveryLegalCaseRepository,
    RecoveryLedgerRepository,
    RecoveryPredictionRepository,
)
from app.schemas.common import build_pagination
from app.schemas.ml import CLAIM_TYPES, PRODUCTS
from app.schemas.provenance import source_metadata
from app.schemas.recovery import (
    LEDGER_COMPONENTS,
    STATUS_AXIS_VALUES,
    AuctionCaseCreateRequest,
    AuctionCaseUpdateRequest,
    LegalCaseCreateRequest,
    LegalCaseUpdateRequest,
    RecoveryCloseRequest,
    RecoveryEventCreateRequest,
    RecoveryLedgerEntryCreateRequest,
    RecoveryPredictRequest,
)
from app.services import ml_service
from app.utils.datetime_utils import new_uuid, now_kst_iso


CLAIM_TYPE_LABELS = {
    "RECOURSE_STANDARD": "구상채권",
    "RECOURSE_NEW_PRODUCT": "구상채권(신상품)",
    "LITIGATION_ADVANCE_COST": "소송대지급금",
    "구상채권": "구상채권",
    "구상채권(신상품)": "구상채권(신상품)",
    "소송대지급금": "소송대지급금",
}
PRODUCT_LABELS = {
    "JEONSE_RETURN_GUARANTEE": "전세보증금반환보증",
    "INDIVIDUAL_RENTAL_DEPOSIT_GUARANTEE": "개인임대사업자임대보증금보증",
    "전세보증금반환보증": "전세보증금반환보증",
    "개인임대사업자임대보증금보증": "개인임대사업자임대보증금보증",
}

_DIRECT_ACCRUAL_COMPONENT = {
    "PRINCIPAL_ACCRUAL": "principal",
    "LEGAL_COST_ACCRUAL": "legal_cost",
    "DELAY_DAMAGE_ACCRUAL": "delay_damage",
    "ENFORCEMENT_COST_ACCRUAL": "enforcement_cost",
}
_DECREASE_TYPES = {"RECEIPT", "DIVIDEND_RECEIPT", "ADJUSTMENT_DECREASE"}
_RECOVERY_STAGE_ORDER = {
    "Registered": 0,
    "Investigation": 1,
    "Preservation": 2,
    "Collection": 3,
    "Distribution": 4,
    "Closing": 5,
}
_LEGAL_STATUS_ORDER = {"PaymentOrder": 0, "Lawsuit": 1, "Judgment": 2, "Enforcement": 3}
_AUCTION_STATUS_ORDER = {
    "Filed": 0,
    "InProgress": 1,
    "Sold": 2,
    "DividendScheduled": 3,
    "Distributed": 4,
}


def _int_value(value: Any, default: int = 0) -> int:
    try:
        return int(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def normalize_claim_balances(claim: dict[str, Any]) -> dict[str, int]:
    """신규/레거시 performance claim 문서 모두를 네 구성항목 잔액으로 정규화한다."""

    nested = claim.get("balances") if isinstance(claim.get("balances"), dict) else {}
    raw_balance = claim.get("balance")
    if isinstance(raw_balance, dict):
        nested = {**raw_balance, **nested}
        raw_balance = raw_balance.get("total")

    principal = _int_value(
        nested.get(
            "principal",
            claim.get(
                "principal_balance",
                raw_balance if raw_balance is not None else claim.get("principal", 0),
            ),
        )
    )
    result = {
        "principal": max(principal, 0),
        "legal_cost": max(_int_value(nested.get("legal_cost", claim.get("legal_cost_balance", 0))), 0),
        "delay_damage": max(
            _int_value(nested.get("delay_damage", claim.get("delay_damage_balance", 0))), 0
        ),
        "enforcement_cost": max(
            _int_value(nested.get("enforcement_cost", claim.get("enforcement_cost_balance", 0))), 0
        ),
    }
    result["total"] = sum(result.values())
    return result


def claim_is_closed(claim: dict[str, Any]) -> bool:
    return bool(claim.get("is_closed") or claim.get("closed_at") or claim.get("closure"))


def _claim_is_demo(claim: dict[str, Any]) -> bool:
    provenance = claim.get("provenance") or claim.get("source") or {}
    claim_id = str(claim.get("_id") or claim.get("recovery_claim_id") or "")
    return bool(
        claim.get("is_demo")
        or provenance.get("is_demo")
        or provenance.get("data_mode") == "DEMO"
        or claim_id.startswith("demo-")
    )


def _claim_provenance(claim: dict[str, Any]) -> dict[str, Any]:
    existing = claim.get("provenance") or claim.get("source")
    if isinstance(existing, dict) and existing.get("source_type"):
        return existing
    is_demo = _claim_is_demo(claim)
    created = str(claim.get("created_at") or date.today().isoformat())[:10]
    return source_metadata(
        data_mode="DEMO" if is_demo else "LIVE",
        source_type="demo_scenario" if is_demo else "user_submitted",
        source_dataset="hug-workflow-v1.1.0" if is_demo else "hug_operational_register",
        as_of_date=created,
        scenario_id=claim.get("scenario_id"),
        is_demo=is_demo,
        basis="명시적 시연 업무대장" if is_demo else "플랫폼 업무대장",
    )


def _source_response_fields(provenance: dict[str, Any]) -> dict[str, Any]:
    return {
        "provenance": provenance,
        "source_type": provenance["source_type"],
        "basis": provenance["basis"],
        "is_demo": provenance["is_demo"],
    }


def _stable_action_id(prefix: str, claim_id: str, key: str | None) -> str:
    if not key:
        return new_uuid()
    digest = hashlib.sha256(f"{prefix}:{claim_id}:{key}".encode()).hexdigest()[:32]
    return f"{prefix}-{digest}"


def _payload_fingerprint(operation: str, payload: Any) -> str:
    if hasattr(payload, "model_dump"):
        body = payload.model_dump(mode="json", exclude={"idempotency_key"})
    else:
        body = payload
    canonical = json.dumps(
        {"operation": operation, "payload": body},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _receipt_key(operation_id: str) -> str:
    return hashlib.sha256(operation_id.encode("utf-8")).hexdigest()


def _receipt_field(operation_id: str) -> str:
    return f"operation_receipts.{_receipt_key(operation_id)}"


def _receipt_value(operation_id: str, operation: str, fingerprint: str, applied_at: str) -> dict[str, str]:
    return {
        "operation_id": operation_id,
        "operation": operation,
        "payload_fingerprint": fingerprint,
        "applied_at": applied_at,
    }


def _has_operation_receipt(claim: dict[str, Any], record: dict[str, Any]) -> bool:
    key = record.get("receipt_key") or _receipt_key(str(record.get("_id", "")))
    receipt = (claim.get("operation_receipts") or {}).get(key)
    return bool(
        isinstance(receipt, dict)
        and receipt.get("operation_id") == record.get("_id")
        and receipt.get("payload_fingerprint") == record.get("payload_fingerprint")
    )


def _assert_same_payload(record: dict[str, Any], fingerprint: str) -> None:
    stored = record.get("payload_fingerprint")
    if stored and stored != fingerprint:
        raise StateConflictError("동일한 멱등키를 다른 요청 내용에 재사용할 수 없습니다.")


def _normalized_percentile(values: list[float], value: float) -> float:
    """동률 중간순위를 포함한 0..1 정규화. 단건 포트폴리오는 중립 0.5다."""

    if len(values) <= 1:
        return 0.5
    lower = sum(item < value for item in values)
    equal = sum(item == value for item in values)
    return (lower + (equal - 1) / 2) / (len(values) - 1)


def _public_case(document: dict[str, Any], *, kind: str) -> dict[str, Any]:
    result = dict(document)
    result[f"{kind}_case_id"] = result.pop("_id")
    return result


def _date_value(value: Any, field: str) -> date:
    if isinstance(value, date):
        return value
    if value:
        try:
            return date.fromisoformat(str(value)[:10])
        except ValueError as exc:
            raise ValidationAppError(f"{field} 날짜 형식이 올바르지 않습니다.") from exc
    raise ValidationAppError(f"등록채권에 {field} 값이 없습니다.")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fp:
        for chunk in iter(lambda: fp.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@lru_cache(maxsize=1)
def recovery_model_metadata() -> dict[str, Any]:
    base = Path(get_settings().data_dir) / "processed" / "ml"
    metric_paths = sorted(base.glob("ml_metrics_*.json"))
    trained_at = "unknown"
    if metric_paths:
        try:
            trained_at = str(json.loads(metric_paths[-1].read_text(encoding="utf-8")).get("trained_at", "unknown"))
        except (OSError, json.JSONDecodeError):
            trained_at = "unknown"
    artifacts: dict[str, str] = {}
    for name in ("recovery_ratio_lgbm.joblib", "days_to_dividend_lgbm.joblib"):
        path = base / "models" / name
        if path.exists():
            artifacts[name] = _sha256(path)
    return {"model_version": f"recovery_models_{trained_at}", "artifact_sha256": artifacts}


def _public_claim(claim: dict[str, Any]) -> dict[str, Any]:
    item = dict(claim)
    item["recovery_claim_id"] = item.pop("_id")
    item["balances"] = normalize_claim_balances(claim)
    item["balance"] = item["balances"]["total"]
    item["claim_type_label"] = CLAIM_TYPE_LABELS.get(str(claim.get("claim_type")), str(claim.get("claim_type", "")))
    item["product_name_label"] = PRODUCT_LABELS.get(
        str(claim.get("product_name")), str(claim.get("product_name", ""))
    )
    item["is_closed"] = claim_is_closed(claim)
    item["provenance"] = _claim_provenance(claim)
    item.setdefault("source_type", item["provenance"]["source_type"])
    item.setdefault("basis", item["provenance"]["basis"])
    item.setdefault("is_demo", item["provenance"]["is_demo"])
    return item


class RecoveryService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._db = db
        self._claims = RecoveryClaimRepository(db)
        self._events = RecoveryEventRepository(db)
        self._ledger = RecoveryLedgerRepository(db)
        self._predictions = RecoveryPredictionRepository(db)
        self._legal_cases = RecoveryLegalCaseRepository(db)
        self._auction_cases = RecoveryAuctionCaseRepository(db)

    async def _get_claim(self, claim_id: str) -> dict[str, Any]:
        claim = await self._claims.get_by_id(claim_id)
        if not claim:
            raise ResourceNotFoundError("등록 채권을 찾을 수 없습니다.")
        return claim

    @staticmethod
    def _assert_open(claim: dict[str, Any]) -> None:
        if claim_is_closed(claim):
            raise StateConflictError("종결 채권은 읽기 전용입니다.")

    async def _reconcile_pending_event(
        self,
        record: dict[str, Any],
        fingerprint: str,
    ) -> dict[str, Any] | None:
        _assert_same_payload(record, fingerprint)
        claim = await self._get_claim(record["recovery_claim_id"])
        applied = _has_operation_receipt(claim, record)
        if applied:
            if not await self._events.mark_committed(record["_id"]):
                current = await self._events.get_by_id(record["_id"])
                if not current or current.get("operation_status") != "COMMITTED":
                    raise StateConflictError("적용된 회수 작업의 감사이력 확정에 실패했습니다.")
            current = await self._events.get_by_id(record["_id"])
            return current or {**record, "operation_status": "COMMITTED"}

        # receipt가 없으면 claim CAS가 적용되지 않은 예약이다. 삭제 후 최신 version으로
        # 같은 호출을 다시 계산할 수 있어 PENDING 영구잠금을 남기지 않는다.
        await self._events.discard_pending(record["_id"])
        return None

    async def _reconcile_pending_ledger(
        self, record: dict[str, Any], fingerprint: str
    ) -> dict[str, Any] | None:
        _assert_same_payload(record, fingerprint)
        claim = await self._get_claim(record["recovery_claim_id"])
        applied = _has_operation_receipt(claim, record)
        if applied:
            # CAS가 이미 적용된 예약이므로 receipt에 기록된 확정 sequence를 복원한다.
            receipt_key = record.get("receipt_key") or _receipt_key(str(record.get("_id", "")))
            receipt = (claim.get("operation_receipts") or {}).get(receipt_key) or {}
            receipt_sequence = receipt.get("sequence")
            sequence = (
                receipt_sequence
                if isinstance(receipt_sequence, int)
                else record.get("sequence")
            )
            if not await self._ledger.mark_committed(record["_id"], sequence=sequence):
                current = await self._ledger.get_by_id(record["_id"])
                if not current or current.get("operation_status") != "COMMITTED":
                    raise StateConflictError("적용된 회수 원장의 확정에 실패했습니다.")
            current = await self._ledger.get_by_id(record["_id"])
            return current or {**record, "operation_status": "COMMITTED", "sequence": sequence}
        await self._ledger.discard_pending(record["_id"])
        return None

    async def _reconcile_pending_prediction(
        self, record: dict[str, Any], fingerprint: str
    ) -> dict[str, Any] | None:
        _assert_same_payload(record, fingerprint)
        claim = await self._get_claim(record["recovery_claim_id"])
        applied = _has_operation_receipt(claim, record) or (
            claim.get("latest_prediction_id") == record.get("_id")
            and _int_value(claim.get("version"))
            >= _int_value(record.get("claim_version_at_inference")) + 1
        )
        if applied:
            stored = await self._predictions.mark_status(
                record["_id"],
                expected_status=str(record.get("prediction_status") or "PENDING"),
                status="SUCCESS",
                fields={"finalized_at": now_kst_iso(), "reconciled": True},
            )
            if stored:
                return stored
            current = await self._predictions.get_by_id(record["_id"])
            if current and current.get("prediction_status") == "SUCCESS":
                return current
            raise StateConflictError("적용된 회수 예측이력 확정에 실패했습니다.")
        await self._predictions.mark_status(
            record["_id"],
            expected_status="PENDING",
            status="STALE",
            fields={"stale_reason": "reconciled_not_applied", "finalized_at": now_kst_iso()},
        )
        await self._predictions.discard_for_retry(record["_id"])
        return None

    async def _dynamic_priority_view(
        self,
        *,
        target_override: tuple[str, float, int] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """현재 잔액과 최신 예측으로 LIVE/DEMO별 전체 활성 포트폴리오를 동적 정렬한다."""

        rows_by_mode: dict[str, list[dict[str, Any]]] = {"LIVE": [], "DEMO": []}
        async for item in self._claims.collection.find({}):
            if claim_is_closed(item):
                continue
            if target_override and item["_id"] == target_override[0]:
                ratio, days = target_override[1], target_override[2]
            else:
                latest = item.get("latest_prediction")
                if not isinstance(latest, dict):
                    latest_doc = await self._predictions.latest_for_claim(item["_id"])
                    latest = (latest_doc or {}).get("result")
                if not isinstance(latest, dict):
                    continue
                if latest.get("pred_recovery_ratio") is None or latest.get("pred_days_to_dividend") is None:
                    continue
                ratio = float(latest["pred_recovery_ratio"])
                days = int(latest["pred_days_to_dividend"])
            mode = "DEMO" if _claim_is_demo(item) else "LIVE"
            rows_by_mode[mode].append(
                {
                    "claim_id": item["_id"],
                    "expected": int(round(normalize_claim_balances(item)["total"] * ratio)),
                    "days": days,
                }
            )

        result: dict[str, dict[str, Any]] = {}
        calculated_at = now_kst_iso()
        for mode, rows in rows_by_mode.items():
            expected_values = [float(row["expected"]) for row in rows]
            day_values = [float(row["days"]) for row in rows]
            for row in rows:
                recovery_norm = _normalized_percentile(expected_values, float(row["expected"]))
                speed_norm = 1 - _normalized_percentile(day_values, float(row["days"]))
                row["recovery_normalized"] = recovery_norm
                row["speed_normalized"] = speed_norm
                row["score"] = round(
                    100
                    * (
                        ml_service.W_RECOVERY * recovery_norm
                        + ml_service.W_SPEED * speed_norm
                    ),
                    1,
                )
            ranked = sorted(
                rows,
                key=lambda row: (-row["score"], -row["expected"], row["days"], row["claim_id"]),
            )
            rank_by_id = {row["claim_id"]: index + 1 for index, row in enumerate(ranked)}
            for row in rows:
                result[row["claim_id"]] = {
                    "priority_score": row["score"],
                    "priority_rank": rank_by_id[row["claim_id"]],
                    "priority_portfolio_size": len(rows),
                    "priority_basis": "REGISTERED_CURRENT_BALANCE_PORTFOLIO_V1",
                    "priority_calculated_at": calculated_at,
                    "priority_components": {
                        "current_balance_expected_recovery_won": row["expected"],
                        "expected_recovery_normalized": round(row["recovery_normalized"], 6),
                        "speed_normalized": round(row["speed_normalized"], 6),
                        "pred_days_to_dividend": row["days"],
                        "weights": {
                            "recovery": ml_service.W_RECOVERY,
                            "speed": ml_service.W_SPEED,
                        },
                        "population_data_mode": mode,
                    },
                }
        return result

    async def _registered_priority_snapshot(
        self,
        target_claim: dict[str, Any],
        *,
        predicted_ratio: float,
        predicted_days: int,
    ) -> dict[str, Any]:
        view = await self._dynamic_priority_view(
            target_override=(target_claim["_id"], predicted_ratio, predicted_days)
        )
        return view[target_claim["_id"]]

    async def summary(self, data_mode: str = "LIVE") -> dict[str, Any]:
        """등록채권 KPI를 집계한다.

        ``LIVE``와 ``DEMO``는 어떤 호출 경로에서도 합산하지 않는다. 시연 집계는
        호출자가 ``data_mode=DEMO``를 명시해야 한다.
        """

        if data_mode not in {"LIVE", "DEMO"}:
            raise ValidationAppError("data_mode는 LIVE 또는 DEMO여야 합니다.")

        all_docs = [doc async for doc in self._claims.collection.find({})]
        mode_breakdown = {
            "DEMO": sum(1 for doc in all_docs if _claim_is_demo(doc)),
            "LIVE": sum(1 for doc in all_docs if not _claim_is_demo(doc)),
        }
        docs = [doc for doc in all_docs if _claim_is_demo(doc) == (data_mode == "DEMO")]
        active = [doc for doc in docs if not claim_is_closed(doc)]
        stage_counts: dict[str, int] = {}
        grade_counts: dict[str, int] = {}
        total_balance = 0
        principal_balance = 0
        subrogation_principal = 0
        expected_total = 0
        predicted_balance = 0

        for claim in active:
            balances = normalize_claim_balances(claim)
            total_balance += balances["total"]
            principal_balance += balances["principal"]
            if str(claim.get("claim_type")) in {
                "RECOURSE_STANDARD", "RECOURSE_NEW_PRODUCT", "구상채권", "구상채권(신상품)"
            }:
                subrogation_principal += balances["principal"]
            stage = str(claim.get("recovery_stage") or claim.get("stage") or "Registered")
            stage_counts[stage] = stage_counts.get(stage, 0) + 1
            latest = claim.get("latest_prediction")
            if not isinstance(latest, dict):
                latest_doc = await self._predictions.latest_for_claim(claim["_id"])
                latest = (latest_doc or {}).get("result")
            if isinstance(latest, dict) and latest.get("pred_recovery_ratio") is not None:
                ratio = float(latest["pred_recovery_ratio"])
                expected_total += int(round(ratio * balances["total"]))
                predicted_balance += balances["total"]
                grade = str(latest.get("pred_recovery_grade") or "UNKNOWN")
                grade_counts[grade] = grade_counts.get(grade, 0) + 1

        all_demo = bool(docs) and all(_claim_is_demo(doc) for doc in docs)
        summary_provenance = source_metadata(
            data_mode="DEMO" if all_demo else "LIVE",
            source_type="demo_scenario" if all_demo else "user_submitted",
            source_dataset="hug-workflow-v1.1.0" if all_demo else "hug_operational_register",
            as_of_date=max(
                (str(doc.get("updated_at") or doc.get("created_at") or "")[:10] for doc in docs),
                default=date.today().isoformat(),
            ),
            is_demo=all_demo,
            basis="등록채권 업무대장 기준. 합성 참조 포트폴리오와 합산하지 않음",
        )
        return {
            "managed_claim_count": len(active),
            "closed_claim_count": len(docs) - len(active),
            "principal_balance_won": principal_balance,
            "subrogation_principal_balance_won": subrogation_principal,
            "total_balance_won": total_balance,
            "expected_recovery_total_won": expected_total,
            "weighted_expected_recovery_ratio": (
                round(expected_total / predicted_balance, 4) if predicted_balance else None
            ),
            "predicted_balance_coverage_won": predicted_balance,
            "stage_counts": stage_counts,
            "grade_counts": grade_counts,
            "data_mode_filter": data_mode,
            "data_mode_breakdown": mode_breakdown,
            "excluded_claim_count": len(all_docs) - len(docs),
            **_source_response_fields(summary_provenance),
        }

    async def list_claims(
        self,
        page: int,
        size: int,
        *,
        lifecycle: str | None,
        recovery_stage: str | None,
        claim_type: str | None,
        collection_route: str | None,
        data_mode: str,
        sort_by: str,
        descending: bool,
    ) -> dict[str, Any]:
        priority_view = await self._dynamic_priority_view()
        if sort_by == "priority_score":
            max_rows = max(await self._claims.collection.count_documents({}), 1)
            all_items, total = await self._claims.list_filtered(
                0,
                max_rows,
                lifecycle=lifecycle,
                recovery_stage=recovery_stage,
                claim_type=claim_type,
                collection_route=collection_route,
                data_mode=data_mode,
                sort_by="updated_at",
                descending=True,
            )
            all_items.sort(
                key=lambda item: (
                    float(priority_view.get(item["_id"], {}).get("priority_score", -1)),
                    item["_id"],
                ),
                reverse=descending,
            )
            start = (page - 1) * size
            items = all_items[start : start + size]
        else:
            items, total = await self._claims.list_filtered(
                (page - 1) * size,
                size,
                lifecycle=lifecycle,
                recovery_stage=recovery_stage,
                claim_type=claim_type,
                collection_route=collection_route,
                data_mode=data_mode,
                sort_by=sort_by,
                descending=descending,
            )
        public_items = []
        for item in items:
            public = _public_claim(item)
            public.update(priority_view.get(item["_id"], {}))
            public_items.append(public)
        return {
            "items": public_items,
            "pagination": build_pagination(page, size, total).model_dump(),
            "data_mode_filter": data_mode,
        }

    async def detail(self, claim_id: str) -> dict[str, Any]:
        claim = await self._get_claim(claim_id)
        public_claim = _public_claim(claim)
        public_claim.update((await self._dynamic_priority_view()).get(claim_id, {}))
        return {
            "claim": public_claim,
            "events": await self._events.list_for_claim(claim_id),
            "ledger_entries": await self._ledger.list_for_claim(claim_id),
            "predictions": await self._predictions.list_for_claim(claim_id),
            "legal_cases": [
                _public_case(item, kind="legal")
                for item in await self._legal_cases.list_for_claim(claim_id)
            ],
            "auction_cases": [
                _public_case(item, kind="auction")
                for item in await self._auction_cases.list_for_claim(claim_id)
            ],
        }

    async def _sync_case_axis(
        self,
        claim_id: str,
        *,
        axis: str,
        after: str,
        occurred_at: str,
    ) -> None:
        order = _LEGAL_STATUS_ORDER if axis == "legal_status" else _AUCTION_STATUS_ORDER
        allowed_before = ["None", *[value for value, rank in order.items() if rank < order[after]]]
        result = await self._claims.collection.update_one(
            {
                "$and": [
                    {"_id": claim_id},
                    {"is_closed": {"$ne": True}},
                    {"$or": [{"closed_at": None}, {"closed_at": {"$exists": False}}]},
                    {"$or": [{"closure": None}, {"closure": {"$exists": False}}]},
                    {
                        "$or": [
                            {axis: {"$in": allowed_before}},
                            {axis: {"$exists": False}},
                        ]
                    },
                ]
            },
            {
                "$set": {
                    axis: after,
                    f"axis_status.{axis}": after,
                    "updated_at": occurred_at,
                },
                "$inc": {"version": 1},
            },
        )
        if result.matched_count:
            return
        current = await self._get_claim(claim_id)
        if claim_is_closed(current):
            raise StateConflictError("종결과 동시에 처리된 사건 변경은 확정할 수 없습니다.")
        current_value = (current.get("axis_status") or {}).get(axis) or current.get(axis) or "None"
        if current_value != "None" and order.get(str(current_value), -1) >= order[after]:
            return
        raise StateConflictError("채권 상태축이 동시에 변경되어 사건 진행을 반영하지 못했습니다.")

    async def _reconcile_pending_case_event(
        self,
        record: dict[str, Any],
        fingerprint: str,
        *,
        kind: str,
    ) -> tuple[dict[str, Any], dict[str, Any]] | None:
        _assert_same_payload(record, fingerprint)
        metadata = record.get("metadata") or {}
        case_id = metadata.get(f"{kind}_case_id")
        repository = self._legal_cases if kind == "legal" else self._auction_cases
        case = await repository.get_by_id(case_id) if case_id else None
        if case and _has_operation_receipt(case, record):
            claim = await self._get_claim(record["recovery_claim_id"])
            if claim_is_closed(claim):
                operation = metadata.get("case_operation")
                if operation == "CREATE":
                    deleted = await repository.collection.delete_one(
                        {
                            "_id": case["_id"],
                            "version": 1,
                            f"operation_receipts.{record['receipt_key']}.operation_id": record["_id"],
                        }
                    )
                    if deleted.deleted_count != 1:
                        raise StateConflictError(
                            "종결 경쟁 중 생성된 사건을 안전하게 취소하지 못했습니다."
                        )
                elif operation == "UPDATE":
                    before_snapshot = metadata.get("before_snapshot") or {}
                    expected = _int_value(metadata.get("case_version_before"), 1)
                    unset_fields = [_receipt_field(record["_id"])] + [
                        field
                        for field in metadata.get("changed_fields", [])
                        if field not in before_snapshot
                    ]
                    rolled_back = await repository.rollback_update(
                        case["_id"],
                        record["recovery_claim_id"],
                        expected + 1,
                        before_snapshot,
                        unset_fields=unset_fields,
                    )
                    if not rolled_back:
                        raise StateConflictError(
                            "종결 경쟁 중 변경된 사건을 안전하게 되돌리지 못했습니다."
                        )
                await self._events.discard_pending(record["_id"])
                raise StateConflictError("종결된 채권의 사건 변경 예약을 취소했습니다.")
            await self._sync_case_axis(
                record["recovery_claim_id"],
                axis=str(record["status_axis"]),
                after=str(record["after"]),
                occurred_at=str(record.get("occurred_at") or now_kst_iso()),
            )
            if not await self._events.mark_committed(record["_id"]):
                current = await self._events.get_by_id(record["_id"])
                if not current or current.get("operation_status") != "COMMITTED":
                    raise StateConflictError("적용된 사건 작업의 감사이력 확정에 실패했습니다.")
            event = await self._events.get_by_id(record["_id"])
            return case, event or {**record, "operation_status": "COMMITTED"}
        await self._events.discard_pending(record["_id"])
        return None

    async def _case_replay(
        self,
        claim_id: str,
        idempotency_key: str,
        fingerprint: str,
        *,
        kind: str,
        expected_event_types: set[str],
    ) -> dict[str, Any] | None:
        replay = await self._events.find_idempotent(claim_id, idempotency_key)
        if not replay:
            return None
        _assert_same_payload(replay, fingerprint)
        if replay.get("event_type") not in expected_event_types:
            raise StateConflictError("동일한 멱등키가 다른 회수 작업에 사용되었습니다.")
        if replay.get("operation_status") == "PENDING":
            recovered = await self._reconcile_pending_case_event(
                replay, fingerprint, kind=kind
            )
            if not recovered:
                return None
            case, event = recovered
            return {
                "case": _public_case(case, kind=kind),
                "event": event,
                "idempotent_replay": True,
                "reconciled": True,
            }
        metadata = replay.get("metadata") or {}
        repository = self._legal_cases if kind == "legal" else self._auction_cases
        case = await repository.get_by_id(metadata.get(f"{kind}_case_id"))
        if not case:
            raise StateConflictError("감사이력에 연결된 사건 문서를 찾을 수 없습니다.")
        return {
            "case": _public_case(case, kind=kind),
            "event": replay,
            "idempotent_replay": True,
        }

    async def _insert_case_event(
        self,
        *,
        claim: dict[str, Any],
        event_id: str,
        event_type: str,
        axis: str,
        before: str,
        after: str,
        note: str | None,
        actor_user_id: str,
        actor_role: str,
        idempotency_key: str,
        fingerprint: str,
        kind: str,
        case_id: str,
        occurred_at: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        event = {
            "_id": event_id,
            "recovery_claim_id": claim["_id"],
            "event_type": event_type,
            "status_axis": axis,
            "before": before,
            "after": after,
            "note": note,
            "actor_user_id": actor_user_id,
            "actor_role": actor_role,
            "occurred_at": occurred_at,
            "idempotency_key": idempotency_key,
            "claim_version_before": _int_value(claim.get("version")),
            "operation_status": "PENDING",
            "payload_fingerprint": fingerprint,
            "receipt_key": _receipt_key(event_id),
            "metadata": {f"{kind}_case_id": case_id, **(metadata or {})},
            **_source_response_fields(_claim_provenance(claim)),
        }
        try:
            await self._events.insert(event)
        except DuplicateKeyError as exc:
            raise StateConflictError("동일한 사건 작업이 이미 처리 중입니다. 다시 조회하세요.") from exc
        return event

    async def create_legal_case(
        self,
        claim_id: str,
        payload: LegalCaseCreateRequest,
        *,
        actor_user_id: str,
        actor_role: str,
    ) -> dict[str, Any]:
        fingerprint = _payload_fingerprint("legal_case_create", payload)
        replay = await self._case_replay(
            claim_id,
            payload.idempotency_key,
            fingerprint,
            kind="legal",
            expected_event_types={"LegalCaseRegistered"},
        )
        if replay:
            return replay
        claim = await self._get_claim(claim_id)
        self._assert_open(claim)
        if await self._legal_cases.find_by_case_number(claim_id, payload.case_number):
            raise StateConflictError("동일한 법무 사건번호가 이미 등록되어 있습니다.")
        now = now_kst_iso()
        event_id = _stable_action_id("rc-legal-create", claim_id, payload.idempotency_key)
        case_id = _stable_action_id("legal-case", claim_id, payload.idempotency_key)
        event = await self._insert_case_event(
            claim=claim,
            event_id=event_id,
            event_type="LegalCaseRegistered",
            axis="legal_status",
            before=str((claim.get("axis_status") or {}).get("legal_status") or claim.get("legal_status") or "None"),
            after=payload.status,
            note=payload.note,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            idempotency_key=payload.idempotency_key,
            fingerprint=fingerprint,
            kind="legal",
            case_id=case_id,
            occurred_at=now,
            metadata={"case_operation": "CREATE"},
        )
        case = {
            "_id": case_id,
            "recovery_claim_id": claim_id,
            **payload.model_dump(mode="json", exclude={"idempotency_key", "note"}),
            "latest_note": payload.note,
            "version": 1,
            "operation_receipts": {
                _receipt_key(event_id): _receipt_value(
                    event_id, "legal_case_create", fingerprint, now
                )
            },
            "created_by_user_id": actor_user_id,
            "created_at": now,
            "updated_at": now,
            **_source_response_fields(_claim_provenance(claim)),
        }
        try:
            await self._legal_cases.insert(case)
            await self._sync_case_axis(
                claim_id, axis="legal_status", after=payload.status, occurred_at=now
            )
        except DuplicateKeyError as exc:
            await self._legal_cases.collection.delete_one({"_id": case_id, "version": 1})
            await self._events.discard_pending(event_id)
            raise StateConflictError("동일한 법무 사건번호가 이미 등록되어 있습니다.") from exc
        except StateConflictError:
            await self._legal_cases.collection.delete_one({"_id": case_id, "version": 1})
            await self._events.discard_pending(event_id)
            raise
        except Exception:
            # 축 갱신 timeout은 적용 후 응답 유실일 수 있으므로 case receipt와
            # PENDING event를 보존해 동일 키 재호출이 수렴시킨다.
            raise
        if not await self._events.mark_committed(event_id):
            raise StateConflictError("법무 사건 감사이력 확정에 실패했습니다.")
        event["operation_status"] = "COMMITTED"
        return {
            "case": _public_case(case, kind="legal"),
            "event": event,
            "idempotent_replay": False,
        }

    async def update_legal_case(
        self,
        claim_id: str,
        case_id: str,
        payload: LegalCaseUpdateRequest,
        *,
        actor_user_id: str,
        actor_role: str,
    ) -> dict[str, Any]:
        fingerprint = _payload_fingerprint(f"legal_case_update:{case_id}", payload)
        replay = await self._case_replay(
            claim_id,
            payload.idempotency_key,
            fingerprint,
            kind="legal",
            expected_event_types={"LegalCaseUpdated"},
        )
        if replay:
            return replay
        claim = await self._get_claim(claim_id)
        self._assert_open(claim)
        current = await self._legal_cases.get_by_id(case_id)
        if not current or current.get("recovery_claim_id") != claim_id:
            raise ResourceNotFoundError("법무 사건을 찾을 수 없습니다.")
        if _int_value(current.get("version"), 1) != payload.expected_version:
            raise StateConflictError("법무 사건이 동시에 변경되었습니다.")
        after = payload.status or current["status"]
        if _LEGAL_STATUS_ORDER[after] < _LEGAL_STATUS_ORDER[str(current["status"])]:
            raise StateConflictError("법무 사건 상태를 이전 단계로 되돌릴 수 없습니다.")
        judgment_amount = (
            payload.judgment_amount_won
            if payload.judgment_amount_won is not None
            else current.get("judgment_amount_won")
        )
        if after in {"Judgment", "Enforcement"} and judgment_amount is None:
            raise ValidationAppError("판결·집행 상태에는 judgment_amount_won이 필요합니다.")
        now = now_kst_iso()
        event_id = _stable_action_id("rc-legal-update", claim_id, payload.idempotency_key)
        event = await self._insert_case_event(
            claim=claim,
            event_id=event_id,
            event_type="LegalCaseUpdated",
            axis="legal_status",
            before=str(current["status"]),
            after=after,
            note=payload.note,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            idempotency_key=payload.idempotency_key,
            fingerprint=fingerprint,
            kind="legal",
            case_id=case_id,
            occurred_at=now,
            metadata={
                "case_operation": "UPDATE",
                "case_version_before": payload.expected_version,
                "before_snapshot": {
                    key: value
                    for key, value in current.items()
                    if key not in {"_id", "recovery_claim_id", "version", "operation_receipts"}
                },
                "changed_fields": [
                    *payload.model_dump(
                        mode="json",
                        exclude={"expected_version", "idempotency_key", "note"},
                        exclude_none=True,
                    ).keys(),
                    "latest_note",
                    "updated_at",
                ],
            },
        )
        fields = payload.model_dump(
            mode="json",
            exclude={"expected_version", "idempotency_key", "note"},
            exclude_none=True,
        )
        fields.update(
            {
                "status": after,
                "latest_note": payload.note,
                _receipt_field(event_id): _receipt_value(
                    event_id, "legal_case_update", fingerprint, now
                ),
                "updated_at": now,
            }
        )
        updated = await self._legal_cases.cas_update(
            case_id, claim_id, payload.expected_version, fields
        )
        if not updated:
            await self._events.discard_pending(event_id)
            raise StateConflictError("법무 사건이 동시에 변경되었습니다.")
        try:
            await self._sync_case_axis(
                claim_id, axis="legal_status", after=after, occurred_at=now
            )
        except StateConflictError as exc:
            rollback_fields = {
                key: value
                for key, value in current.items()
                if key not in {"_id", "recovery_claim_id", "version", "operation_receipts"}
            }
            rolled_back = await self._legal_cases.rollback_update(
                case_id,
                claim_id,
                payload.expected_version + 1,
                rollback_fields,
                unset_fields=[
                    _receipt_field(event_id),
                    *[
                        key
                        for key in fields
                        if "." not in key and key not in current
                    ],
                ],
            )
            if not rolled_back:
                raise StateConflictError(
                    "법무 사건 상태축 충돌 후 원문을 복구하지 못했습니다."
                ) from exc
            await self._events.discard_pending(event_id)
            raise
        except Exception:
            # case CAS는 이미 적용되었다. 예약을 보존해 재호출 시 축 동기화와
            # 감사이력 확정을 이어간다.
            raise
        if not await self._events.mark_committed(event_id):
            raise StateConflictError("법무 사건 감사이력 확정에 실패했습니다.")
        event["operation_status"] = "COMMITTED"
        return {
            "case": _public_case(updated, kind="legal"),
            "event": event,
            "idempotent_replay": False,
        }

    async def create_auction_case(
        self,
        claim_id: str,
        payload: AuctionCaseCreateRequest,
        *,
        actor_user_id: str,
        actor_role: str,
    ) -> dict[str, Any]:
        fingerprint = _payload_fingerprint("auction_case_create", payload)
        replay = await self._case_replay(
            claim_id,
            payload.idempotency_key,
            fingerprint,
            kind="auction",
            expected_event_types={"AuctionCaseRegistered"},
        )
        if replay:
            return replay
        claim = await self._get_claim(claim_id)
        self._assert_open(claim)
        if await self._auction_cases.find_by_case_number(claim_id, payload.case_number):
            raise StateConflictError("동일한 경·공매 사건번호가 이미 등록되어 있습니다.")
        now = now_kst_iso()
        event_id = _stable_action_id("rc-auction-create", claim_id, payload.idempotency_key)
        case_id = _stable_action_id("auction-case", claim_id, payload.idempotency_key)
        event = await self._insert_case_event(
            claim=claim,
            event_id=event_id,
            event_type="AuctionCaseRegistered",
            axis="auction_status",
            before=str((claim.get("axis_status") or {}).get("auction_status") or claim.get("auction_status") or "None"),
            after=payload.status,
            note=payload.note,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            idempotency_key=payload.idempotency_key,
            fingerprint=fingerprint,
            kind="auction",
            case_id=case_id,
            occurred_at=now,
            metadata={"case_operation": "CREATE"},
        )
        case = {
            "_id": case_id,
            "recovery_claim_id": claim_id,
            **payload.model_dump(mode="json", exclude={"idempotency_key", "note"}),
            "latest_note": payload.note,
            "version": 1,
            "operation_receipts": {
                _receipt_key(event_id): _receipt_value(
                    event_id, "auction_case_create", fingerprint, now
                )
            },
            "created_by_user_id": actor_user_id,
            "created_at": now,
            "updated_at": now,
            **_source_response_fields(_claim_provenance(claim)),
        }
        try:
            await self._auction_cases.insert(case)
            await self._sync_case_axis(
                claim_id, axis="auction_status", after=payload.status, occurred_at=now
            )
        except DuplicateKeyError as exc:
            await self._auction_cases.collection.delete_one({"_id": case_id, "version": 1})
            await self._events.discard_pending(event_id)
            raise StateConflictError("동일한 경·공매 사건번호가 이미 등록되어 있습니다.") from exc
        except StateConflictError:
            await self._auction_cases.collection.delete_one({"_id": case_id, "version": 1})
            await self._events.discard_pending(event_id)
            raise
        except Exception:
            raise
        if not await self._events.mark_committed(event_id):
            raise StateConflictError("경·공매 사건 감사이력 확정에 실패했습니다.")
        event["operation_status"] = "COMMITTED"
        return {
            "case": _public_case(case, kind="auction"),
            "event": event,
            "idempotent_replay": False,
        }

    async def update_auction_case(
        self,
        claim_id: str,
        case_id: str,
        payload: AuctionCaseUpdateRequest,
        *,
        actor_user_id: str,
        actor_role: str,
    ) -> dict[str, Any]:
        fingerprint = _payload_fingerprint(f"auction_case_update:{case_id}", payload)
        replay = await self._case_replay(
            claim_id,
            payload.idempotency_key,
            fingerprint,
            kind="auction",
            expected_event_types={"AuctionCaseUpdated"},
        )
        if replay:
            return replay
        claim = await self._get_claim(claim_id)
        self._assert_open(claim)
        current = await self._auction_cases.get_by_id(case_id)
        if not current or current.get("recovery_claim_id") != claim_id:
            raise ResourceNotFoundError("경·공매 사건을 찾을 수 없습니다.")
        if _int_value(current.get("version"), 1) != payload.expected_version:
            raise StateConflictError("경·공매 사건이 동시에 변경되었습니다.")
        after = payload.status or current["status"]
        if _AUCTION_STATUS_ORDER[after] < _AUCTION_STATUS_ORDER[str(current["status"])]:
            raise StateConflictError("경·공매 사건 상태를 이전 단계로 되돌릴 수 없습니다.")
        filing_date = _date_value(current.get("filing_date"), "경·공매 신청일")
        sale_date = payload.sale_date or (
            _date_value(current.get("sale_date"), "매각일") if current.get("sale_date") else None
        )
        dividend_date = payload.dividend_date or (
            _date_value(current.get("dividend_date"), "배당일")
            if current.get("dividend_date")
            else None
        )
        if sale_date and sale_date < filing_date:
            raise ValidationAppError("매각일은 신청일보다 빠를 수 없습니다.")
        if dividend_date and dividend_date < (sale_date or filing_date):
            raise ValidationAppError("배당일은 신청일·매각일보다 빠를 수 없습니다.")
        if after in {"Sold", "DividendScheduled", "Distributed"} and sale_date is None:
            raise ValidationAppError("매각 이후 상태에는 sale_date가 필요합니다.")
        if after in {"DividendScheduled", "Distributed"} and dividend_date is None:
            raise ValidationAppError("배당 단계에는 dividend_date가 필요합니다.")
        now = now_kst_iso()
        event_id = _stable_action_id("rc-auction-update", claim_id, payload.idempotency_key)
        event = await self._insert_case_event(
            claim=claim,
            event_id=event_id,
            event_type="AuctionCaseUpdated",
            axis="auction_status",
            before=str(current["status"]),
            after=after,
            note=payload.note,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            idempotency_key=payload.idempotency_key,
            fingerprint=fingerprint,
            kind="auction",
            case_id=case_id,
            occurred_at=now,
            metadata={
                "case_operation": "UPDATE",
                "case_version_before": payload.expected_version,
                "before_snapshot": {
                    key: value
                    for key, value in current.items()
                    if key not in {"_id", "recovery_claim_id", "version", "operation_receipts"}
                },
                "changed_fields": [
                    *payload.model_dump(
                        mode="json",
                        exclude={"expected_version", "idempotency_key", "note"},
                        exclude_none=True,
                    ).keys(),
                    "latest_note",
                    "updated_at",
                ],
            },
        )
        fields = payload.model_dump(
            mode="json",
            exclude={"expected_version", "idempotency_key", "note"},
            exclude_none=True,
        )
        fields.update(
            {
                "status": after,
                "latest_note": payload.note,
                _receipt_field(event_id): _receipt_value(
                    event_id, "auction_case_update", fingerprint, now
                ),
                "updated_at": now,
            }
        )
        updated = await self._auction_cases.cas_update(
            case_id, claim_id, payload.expected_version, fields
        )
        if not updated:
            await self._events.discard_pending(event_id)
            raise StateConflictError("경·공매 사건이 동시에 변경되었습니다.")
        try:
            await self._sync_case_axis(
                claim_id, axis="auction_status", after=after, occurred_at=now
            )
        except StateConflictError as exc:
            rollback_fields = {
                key: value
                for key, value in current.items()
                if key not in {"_id", "recovery_claim_id", "version", "operation_receipts"}
            }
            rolled_back = await self._auction_cases.rollback_update(
                case_id,
                claim_id,
                payload.expected_version + 1,
                rollback_fields,
                unset_fields=[
                    _receipt_field(event_id),
                    *[
                        key
                        for key in fields
                        if "." not in key and key not in current
                    ],
                ],
            )
            if not rolled_back:
                raise StateConflictError(
                    "경·공매 사건 상태축 충돌 후 원문을 복구하지 못했습니다."
                ) from exc
            await self._events.discard_pending(event_id)
            raise
        except Exception:
            raise
        if not await self._events.mark_committed(event_id):
            raise StateConflictError("경·공매 사건 감사이력 확정에 실패했습니다.")
        event["operation_status"] = "COMMITTED"
        return {
            "case": _public_case(updated, kind="auction"),
            "event": event,
            "idempotent_replay": False,
        }

    async def add_event(
        self,
        claim_id: str,
        payload: RecoveryEventCreateRequest,
        *,
        actor_user_id: str,
        actor_role: str,
    ) -> dict[str, Any]:
        fingerprint = _payload_fingerprint("recovery_event", payload)
        replay = await self._events.find_idempotent(claim_id, payload.idempotency_key)
        if replay:
            _assert_same_payload(replay, fingerprint)
            if replay.get("operation_status") == "PENDING":
                recovered = await self._reconcile_pending_event(
                    replay,
                    fingerprint,
                )
                if recovered:
                    return {**recovered, "idempotent_replay": True, "reconciled": True}
            else:
                return {**replay, "idempotent_replay": True}
        claim = await self._get_claim(claim_id)
        self._assert_open(claim)

        before = None
        expected_version = _int_value(claim.get("version"))
        now = payload.occurred_at.isoformat() if payload.occurred_at else now_kst_iso()
        set_fields: dict[str, Any] | None = None
        if payload.status_axis:
            if payload.status_axis == "balance_status":
                raise ValidationAppError("balance_status는 원장 잔액에서 자동 계산됩니다.")
            if payload.status_axis in {"legal_status", "auction_status"}:
                raise ValidationAppError(
                    "법무·경공매 상태는 사건 전용 API에서 사건번호·금액·날짜와 함께 변경해야 합니다."
                )
            if payload.status_axis == "recovery_stage" and payload.after == "Closing":
                raise ValidationAppError("Closing 전환은 채권 종결 API를 사용해야 합니다.")
            before = (claim.get("axis_status") or {}).get(payload.status_axis)
            before = before or claim.get(payload.status_axis)
            if payload.status_axis == "recovery_stage":
                before = before or claim.get("stage") or "Registered"
                if _RECOVERY_STAGE_ORDER[payload.after] < _RECOVERY_STAGE_ORDER.get(str(before), 0):
                    raise StateConflictError("대표 회수단계를 이전 단계로 되돌릴 수 없습니다.")
            set_fields = {
                payload.status_axis: payload.after,
                f"axis_status.{payload.status_axis}": payload.after,
                "updated_at": now,
            }

        # 이벤트를 먼저 내구성 있게 예약한 뒤 claim CAS를 수행한다. 이 순서이면
        # 이벤트 저장 실패 뒤 상태축만 변경되는 불완전 기록이 생기지 않는다.
        event_provenance = _claim_provenance(claim)
        event_id = _stable_action_id("rc-event", claim_id, payload.idempotency_key)
        if set_fields is not None:
            set_fields[_receipt_field(event_id)] = _receipt_value(
                event_id, "recovery_event", fingerprint, now
            )
        event = {
            "_id": event_id,
            "recovery_claim_id": claim_id,
            "event_type": payload.event_type,
            "status_axis": payload.status_axis,
            "before": before,
            "after": payload.after,
            "note": payload.note,
            "actor_user_id": actor_user_id,
            "actor_role": actor_role,
            "occurred_at": now,
            "idempotency_key": payload.idempotency_key,
            "claim_version_before": expected_version,
            "operation_status": "PENDING" if payload.status_axis else "COMMITTED",
            "payload_fingerprint": fingerprint,
            "receipt_key": _receipt_key(event_id),
            **_source_response_fields(event_provenance),
        }
        if payload.idempotency_key is None:
            event.pop("idempotency_key")
        try:
            await self._events.insert(event)
        except DuplicateKeyError:
            replay = await self._events.get_by_id(event["_id"])
            if replay:
                _assert_same_payload(replay, fingerprint)
                if replay.get("operation_status") == "PENDING":
                    recovered = await self._reconcile_pending_event(
                        replay,
                        fingerprint,
                    )
                    if recovered:
                        return {**recovered, "idempotent_replay": True, "reconciled": True}
                    raise StateConflictError("동일한 이벤트 요청을 최신 상태로 다시 시도하세요.")
                return {**replay, "idempotent_replay": True}
            raise
        if set_fields is not None:
            try:
                updated = await self._claims.update_open_with_version(
                    claim_id,
                    expected_version,
                    set_fields=set_fields,
                )
            except Exception:
                # 네트워크 timeout은 CAS 적용 후 응답 유실일 수 있다. PENDING을
                # 보존해 동일 키 재호출이 claim receipt로 적용 여부를 판정한다.
                raise
            if not updated:
                await self._events.discard_pending(event["_id"])
                raise StateConflictError(
                    "동시에 채권이 변경되었습니다. 최신 상태를 조회한 뒤 다시 시도하세요."
                )
            if not await self._events.mark_committed(event["_id"]):
                raise StateConflictError("상태 변경 이벤트 확정에 실패했습니다. 운영 점검이 필요합니다.")
            event["operation_status"] = "COMMITTED"
        return {**event, "idempotent_replay": False}

    async def add_ledger_entry(
        self,
        claim_id: str,
        payload: RecoveryLedgerEntryCreateRequest,
        *,
        actor_user_id: str,
        actor_role: str,
    ) -> dict[str, Any]:
        fingerprint = _payload_fingerprint("recovery_ledger", payload)
        replay = await self._ledger.find_idempotent(claim_id, payload.idempotency_key)
        if replay:
            _assert_same_payload(replay, fingerprint)
            if replay.get("operation_status") == "PENDING":
                recovered = await self._reconcile_pending_ledger(replay, fingerprint)
                if recovered:
                    return {**recovered, "idempotent_replay": True, "reconciled": True}
            else:
                return {**replay, "idempotent_replay": True}
        claim = await self._get_claim(claim_id)
        self._assert_open(claim)
        expected_version = _int_value(claim.get("version"))
        before = normalize_claim_balances(claim)
        after = {component: before[component] for component in LEDGER_COMPONENTS}

        direction = "INCREASE"
        if payload.entry_type in _DIRECT_ACCRUAL_COMPONENT:
            after[_DIRECT_ACCRUAL_COMPONENT[payload.entry_type]] += payload.amount_won
            allocations = {_DIRECT_ACCRUAL_COMPONENT[payload.entry_type]: payload.amount_won}
        else:
            allocations = dict(payload.allocations)
            direction = "DECREASE" if payload.entry_type in _DECREASE_TYPES else "INCREASE"
            for component, amount in allocations.items():
                if direction == "DECREASE":
                    if amount > after[component]:
                        raise StateConflictError(
                            f"{component} 배분액이 현재 잔액을 초과합니다. 현재 {after[component]:,}원"
                        )
                    after[component] -= amount
                else:
                    after[component] += amount
        after["total"] = sum(after.values())

        recovered_after = _int_value(claim.get("recovered_total"))
        if payload.entry_type in {"RECEIPT", "DIVIDEND_RECEIPT"}:
            recovered_after += payload.amount_won
        if after["total"] == 0:
            balance_status = "FullyRecovered"
        elif recovered_after > 0:
            balance_status = "PartiallyRecovered"
        else:
            balance_status = "Unrecovered"

        now = payload.occurred_at.isoformat() if payload.occurred_at else now_kst_iso()
        latest_ledger = await self._ledger.latest_committed(claim_id)
        if latest_ledger and payload.occurred_at:
            latest_effective = str(latest_ledger.get("occurred_at") or "")
            try:
                latest_datetime = datetime.fromisoformat(latest_effective)
            except (TypeError, ValueError):
                latest_datetime = None
            if latest_datetime is not None and latest_datetime.tzinfo is None:
                latest_datetime = latest_datetime.replace(tzinfo=payload.occurred_at.tzinfo)
            if latest_datetime is not None and payload.occurred_at < latest_datetime:
                raise ValidationAppError("occurred_at은 최신 확정 원장보다 과거일 수 없습니다.")
        # sequence는 예약(PENDING) 시점에 부여하지 않는다. 예약 단계에서 부여하면
        # (recovery_claim_id, sequence) unique 인덱스가 CAS 이전에 충돌해 다른
        # 멱등키의 정상 요청이 409 대신 DuplicateKeyError(500)로 실패하고, 크래시로
        # 남은 고아 PENDING이 이후 모든 원장 쓰기를 잠글 수 있다. 대신 version
        # CAS로 직렬화되는 claim의 ledger_sequence 카운터를 사용해 COMMITTED 확정
        # 시점에만 기록한다. 카운터가 없는 레거시/Seed 문서는 확정 원장 기준으로
        # 1회 유도한다.
        next_sequence = _int_value(claim.get("ledger_sequence"))
        if next_sequence == 0:
            next_sequence = _int_value((latest_ledger or {}).get("sequence"))
            if next_sequence == 0 and latest_ledger:
                next_sequence = await self._ledger.collection.count_documents(
                    {
                        "recovery_claim_id": claim_id,
                        "operation_status": {"$ne": "PENDING"},
                    }
                )
        next_sequence += 1
        set_fields: dict[str, Any] = {
            "balances": after,
            "balance": after["total"],
            "principal_balance": after["principal"],
            "legal_cost_balance": after["legal_cost"],
            "delay_damage_balance": after["delay_damage"],
            "enforcement_cost_balance": after["enforcement_cost"],
            "balance_status": balance_status,
            "axis_status.balance_status": balance_status,
            "updated_at": now,
        }
        inc_fields = None
        if payload.entry_type in {"RECEIPT", "DIVIDEND_RECEIPT"}:
            inc_fields = {"recovered_total": payload.amount_won}
        # 원장도 claim 잔액보다 먼저 예약한다. 저장 실패 시 CAS가 실행되지 않으며,
        # CAS 경쟁에서 패한 예약은 즉시 제거해 멱등키 재시도를 허용한다.
        entry_provenance = _claim_provenance(claim)
        entry_id = _stable_action_id("rc-ledger", claim_id, payload.idempotency_key)
        # receipt에 sequence를 함께 저장해 ambiguous write 이후 reconciliation이
        # 확정 sequence를 복원할 수 있게 한다.
        set_fields["ledger_sequence"] = next_sequence
        set_fields[_receipt_field(entry_id)] = {
            **_receipt_value(entry_id, "recovery_ledger", fingerprint, now),
            "sequence": next_sequence,
        }
        entry = {
            "_id": entry_id,
            "recovery_claim_id": claim_id,
            "entry_type": payload.entry_type,
            "direction": direction,
            "amount_won": payload.amount_won,
            "allocations": allocations,
            "allocation_policy": "EXPLICIT_MANUAL_POC",
            "balance_before": before,
            "balance_after": after,
            "note": payload.note,
            "reference_type": payload.reference_type,
            "reference_id": payload.reference_id,
            "actor_user_id": actor_user_id,
            "actor_role": actor_role,
            "occurred_at": now,
            "idempotency_key": payload.idempotency_key,
            "claim_version_before": expected_version,
            "operation_status": "PENDING",
            "payload_fingerprint": fingerprint,
            "receipt_key": _receipt_key(entry_id),
            **_source_response_fields(entry_provenance),
        }
        if payload.idempotency_key is None:
            entry.pop("idempotency_key")
        try:
            await self._ledger.insert(entry)
        except DuplicateKeyError as exc:
            replay = await self._ledger.get_by_id(entry["_id"])
            if replay:
                _assert_same_payload(replay, fingerprint)
                if replay.get("operation_status") == "PENDING":
                    recovered = await self._reconcile_pending_ledger(replay, fingerprint)
                    if recovered:
                        return {**recovered, "idempotent_replay": True, "reconciled": True}
                    raise StateConflictError("동일한 원장 요청을 최신 잔액으로 다시 시도하세요.")
                return {**replay, "idempotent_replay": True}
            # 같은 멱등키의 예약이 직전에 정리된 극히 좁은 경쟁 구간이다. 원시
            # DuplicateKeyError(500) 대신 재시도 가능한 409로 반환한다.
            raise StateConflictError(
                "동일한 원장 요청이 동시에 처리되었습니다. 최신 잔액을 조회한 뒤 다시 시도하세요."
            ) from exc
        try:
            updated = await self._claims.update_open_with_version(
                claim_id,
                expected_version,
                set_fields=set_fields,
                inc_fields=inc_fields,
            )
        except Exception:
            # ambiguous write일 수 있으므로 예약을 남겨 receipt reconciliation에 맡긴다.
            raise
        if not updated:
            await self._ledger.discard_pending(entry["_id"])
            raise StateConflictError(
                "동시에 원장이 변경되었습니다. 최신 잔액을 조회한 뒤 다시 시도하세요."
            )
        if not await self._ledger.mark_committed(entry["_id"], sequence=next_sequence):
            raise StateConflictError("원장 항목 확정에 실패했습니다. 운영 점검이 필요합니다.")
        entry["operation_status"] = "COMMITTED"
        entry["sequence"] = next_sequence
        return {**entry, "idempotent_replay": False}

    async def predict(
        self,
        claim_id: str,
        payload: RecoveryPredictRequest,
        *,
        actor_user_id: str,
    ) -> dict[str, Any]:
        fingerprint = _payload_fingerprint("recovery_prediction", payload)
        replay = await self._predictions.find_idempotent(claim_id, payload.idempotency_key)
        if replay:
            _assert_same_payload(replay, fingerprint)
            replay_status = replay.get("prediction_status")
            if replay_status in {"PENDING", "STALE"}:
                recovered = await self._reconcile_pending_prediction(replay, fingerprint)
                if recovered:
                    return {**recovered, "idempotent_replay": True, "reconciled": True}
            else:
                return {**replay, "idempotent_replay": True}
        claim = await self._get_claim(claim_id)
        self._assert_open(claim)
        expected_version = _int_value(claim.get("version"))

        product = PRODUCT_LABELS.get(str(claim.get("product_name")), str(claim.get("product_name", "")))
        claim_type = CLAIM_TYPE_LABELS.get(str(claim.get("claim_type")), str(claim.get("claim_type", "")))
        if product not in PRODUCTS:
            raise ValidationAppError(f"회수모델이 지원하지 않는 상품입니다: {product or '미입력'}")
        if claim_type not in CLAIM_TYPES:
            raise ValidationAppError(f"회수모델이 지원하지 않는 채권구분입니다: {claim_type or '미입력'}")

        claimed_amount = _int_value(
            claim.get("original_claimed_amount", claim.get("claimed_amount", claim.get("principal")))
        )
        if claimed_amount < 0:
            raise ValidationAppError("신청청구금액은 음수일 수 없습니다.")
        incurred_amount = _int_value(claim.get("incurred_amount"))
        if incurred_amount < 0:
            raise ValidationAppError("발생금액은 음수일 수 없습니다.")
        incurred_date = _date_value(
            claim.get("incurred_date") or claim.get("registered_at") or claim.get("created_at"),
            "채권발생일",
        )
        if payload.auction_filed_date is not None:
            auction_date = payload.auction_filed_date
            auction_origin = "scenario_assumption"
        else:
            auction_date = _date_value(claim.get("auction_filed_date"), "경·공매 신청일")
            auction_origin = "recovery_claim_register"

        input_snapshot = {
            "product_name": product,
            "claim_type": claim_type,
            "claimed_amount": claimed_amount,
            "claimed_amount_origin": "recovery_claim_register",
            "incurred_amount": incurred_amount,
            "incurred_amount_origin": "recovery_claim_register",
            "auction_filed_date": auction_date.isoformat(),
            "auction_filed_date_origin": auction_origin,
            "auction_filed_date_assumption_reason": payload.assumption_reason,
            "incurred_date": incurred_date.isoformat(),
            "incurred_date_origin": "recovery_claim_register",
        }
        raw_result = await run_in_threadpool(
            ml_service.predict_recovery,
            ml_service.RecoveryInput(
                product_name=product,
                claim_type=claim_type,
                claimed_amount=claimed_amount,
                incurred_amount=incurred_amount,
                auction_filed_date=auction_date,
                incurred_date=incurred_date,
            ),
        )
        balances = normalize_claim_balances(claim)
        priority = await self._registered_priority_snapshot(
            claim,
            predicted_ratio=float(raw_result["pred_recovery_ratio"]),
            predicted_days=int(raw_result["pred_days_to_dividend"]),
        )
        result = {
            **raw_result,
            "model_reference_priority_score": raw_result.get("priority_score"),
            "model_reference_portfolio_size": raw_result.get("portfolio_size"),
            "expected_recovery_on_current_balance_won": int(
                round(float(raw_result["pred_recovery_ratio"]) * balances["total"])
            ),
            "current_balance_won": balances["total"],
            **priority,
            "portfolio_size": priority["priority_portfolio_size"],
        }
        previous = await self._predictions.latest_for_claim(claim_id)
        previous_result = (previous or {}).get("result") or {}
        delta = None
        if previous_result:
            delta = {
                "pred_recovery_ratio": round(
                    float(result["pred_recovery_ratio"])
                    - float(previous_result.get("pred_recovery_ratio", 0)),
                    4,
                ),
                "pred_days_to_dividend": int(result["pred_days_to_dividend"])
                - int(previous_result.get("pred_days_to_dividend", 0)),
                "expected_recovery_on_current_balance_won": int(
                    result["expected_recovery_on_current_balance_won"]
                ) - int(previous_result.get("expected_recovery_on_current_balance_won", 0)),
                "priority_score": round(
                    float(result["priority_score"])
                    - float(previous_result.get("priority_score", 0)),
                    1,
                ),
            }
        metadata = recovery_model_metadata()
        now = now_kst_iso()
        is_demo = _claim_is_demo(claim)
        provenance = source_metadata(
            data_mode="DEMO" if is_demo else "LIVE",
            source_type="model_poc",
            source_dataset="provided_synthetic_dividend_training",
            as_of_date=now[:10],
            scenario_id=claim.get("scenario_id"),
            model_version=metadata["model_version"],
            input_snapshot=input_snapshot,
            is_demo=is_demo,
            basis=ml_service.BASIS_NOTE,
        )
        prediction_id = _stable_action_id("rc-pred", claim_id, payload.idempotency_key)
        prediction = {
            "_id": prediction_id,
            "recovery_claim_id": claim_id,
            "result": result,
            "input_snapshot": input_snapshot,
            "model_version": metadata["model_version"],
            "artifact_sha256": metadata["artifact_sha256"],
            # 모델 추론 결과 저장과 claim의 latest 포인터 갱신은 서로 다른
            # 컬렉션이므로, 먼저 PENDING 이력을 남기고 open+version CAS가 성공한
            # 경우에만 SUCCESS로 확정한다.
            "prediction_status": "PENDING",
            "claim_version_at_inference": expected_version,
            "delta_from_previous": delta,
            "previous_prediction_id": previous.get("_id") if previous else None,
            "predicted_by": actor_user_id,
            "predicted_at": now,
            "idempotency_key": payload.idempotency_key,
            "payload_fingerprint": fingerprint,
            "receipt_key": _receipt_key(prediction_id),
            "provenance": provenance,
            "source_type": "model_poc",
            "basis": ml_service.BASIS_NOTE,
            "is_demo": is_demo,
        }
        if payload.idempotency_key is None:
            prediction.pop("idempotency_key")
        try:
            await self._predictions.insert(prediction)
        except DuplicateKeyError:
            replay = await self._predictions.get_by_id(prediction["_id"])
            if replay:
                _assert_same_payload(replay, fingerprint)
                if replay.get("prediction_status") in {"PENDING", "STALE"}:
                    recovered = await self._reconcile_pending_prediction(replay, fingerprint)
                    if recovered:
                        return {**recovered, "idempotent_replay": True, "reconciled": True}
                    raise StateConflictError("동일한 예측 요청을 최신 채권으로 다시 시도하세요.")
                return {**replay, "idempotent_replay": True}
            raise
        latest_fields = {
            "latest_prediction_id": prediction["_id"],
            "latest_prediction": result,
            "pred_recovery_ratio": result["pred_recovery_ratio"],
            "pred_recovery_grade": result["pred_recovery_grade"],
            "pred_days_to_dividend": result["pred_days_to_dividend"],
            "expected_recovery_won": result["expected_recovery_on_current_balance_won"],
            "priority_score": result["priority_score"],
            "priority_rank": result["priority_rank"],
            "priority_portfolio_size": result["priority_portfolio_size"],
            "priority_basis": result["priority_basis"],
            "priority_components": result["priority_components"],
            _receipt_field(prediction_id): _receipt_value(
                prediction_id, "recovery_prediction", fingerprint, now
            ),
            "updated_at": now,
        }
        try:
            updated = await self._claims.update_open_with_version(
                claim_id,
                expected_version,
                set_fields=latest_fields,
            )
        except Exception:
            # 네트워크 오류가 CAS 적용 뒤 발생했을 수 있으므로 PENDING을 보존한다.
            # 같은 멱등키 재호출이 claim receipt를 확인해 SUCCESS 또는 재시도로 수렴한다.
            raise
        if not updated:
            await self._predictions.mark_status(
                prediction["_id"],
                expected_status="PENDING",
                status="STALE",
                fields={
                    "stale_reason": "claim_closed_or_version_changed",
                    "finalized_at": now_kst_iso(),
                },
            )
            raise StateConflictError(
                "예측 중 채권이 변경되었거나 종결되어 결과를 최신 예측으로 반영하지 않았습니다."
            )
        stored = await self._predictions.mark_status(
            prediction["_id"],
            expected_status="PENDING",
            status="SUCCESS",
            fields={"finalized_at": now_kst_iso()},
        )
        if not stored:
            raise StateConflictError("예측 이력 확정에 실패했습니다. 운영 점검이 필요합니다.")
        return {**stored, "idempotent_replay": False}

    async def predictions(self, claim_id: str) -> dict[str, Any]:
        await self._get_claim(claim_id)
        items = await self._predictions.list_for_claim(claim_id)
        return {"items": items, "total": len(items)}

    async def _sync_parent_if_all_closed(
        self,
        claim: dict[str, Any],
        *,
        actor_user_id: str,
        actor_role: str,
        closed_at: str,
    ) -> dict[str, Any]:
        performance_claim_id = claim.get("performance_claim_id")
        if not performance_claim_id:
            return {"status": "NOT_LINKED", "remaining_open_recovery_claims": None}
        remaining = await self._claims.count_open_for_performance_claim(performance_claim_id)
        if remaining:
            return {"status": "WAITING_FOR_RELATED_CLAIMS", "remaining_open_recovery_claims": remaining}

        performance = await self._db.performance_claims.find_one({"_id": performance_claim_id})
        if not performance:
            return {"status": "PERFORMANCE_CLAIM_NOT_FOUND", "remaining_open_recovery_claims": 0}
        metadata = {
            "closed_by": actor_user_id,
            "closed_by_role": actor_role,
            "last_recovery_claim_id": claim["_id"],
            "basis": "동일 보증이행청구의 등록채권 전체 종결",
        }
        if not performance.get("recovery_closed_at"):
            expected_version = _int_value(performance.get("version"), 1)
            result = await self._db.performance_claims.update_one(
                {
                    "_id": performance_claim_id,
                    "version": expected_version,
                    "$or": [
                        {"recovery_closed_at": None},
                        {"recovery_closed_at": {"$exists": False}},
                    ],
                },
                {
                    "$set": {
                        "recovery_closed_at": closed_at,
                        "recovery_lifecycle_status": "Closed",
                        "recovery_closure": metadata,
                        "updated_at": closed_at,
                    },
                    "$inc": {"version": 1},
                },
            )
            if result.matched_count == 0:
                performance = await self._db.performance_claims.find_one(
                    {"_id": performance_claim_id}
                )
                if not performance or not performance.get("recovery_closed_at"):
                    raise StateConflictError(
                        "상위 보증이행청구가 동시에 변경되어 종결 상태를 동기화하지 못했습니다."
                    )

        # 아래 두 갱신은 단조 전이(CLOSED)이며 재호출해도 같은 결과다. 중간 실패 시
        # 동일 close 멱등키 재호출이 이 메서드를 다시 수행해 수렴시킨다.
        incident_id = performance.get("incident_id")
        if incident_id:
            incident_result = await self._db.incidents.update_one(
                {
                    "_id": incident_id,
                    "performance_claim_id": performance_claim_id,
                    "status": {"$in": ["Received", "Reviewing", "TransferredToRecovery"]},
                },
                {
                    "$set": {
                        "status": "Closed",
                        "current_stage": "RecoveryClosed",
                        "recovery_closed_at": closed_at,
                        "updated_at": closed_at,
                    }
                },
            )
            if incident_result.matched_count == 0:
                incident = await self._db.incidents.find_one({"_id": incident_id})
                if not incident or incident.get("status") != "Closed":
                    raise StateConflictError("연결 사고의 종결 상태를 동기화하지 못했습니다.")

        contract_id = performance.get("contract_id") or claim.get("contract_id")
        if contract_id:
            contract_result = await self._db.contracts.update_one(
                {
                    "_id": contract_id,
                    "contract_status": {
                        "$in": [
                            "IncidentReported",
                            "TransferredToHUG",
                            "RecoveryInProgress",
                            "Closed",
                        ]
                    },
                },
                {
                    "$set": {
                        "contract_status": "Closed",
                        "recovery_closed_at": closed_at,
                        "updated_at": closed_at,
                    }
                },
            )
            if contract_result.matched_count == 0:
                contract = await self._db.contracts.find_one({"_id": contract_id})
                if not contract or contract.get("contract_status") != "Closed":
                    raise StateConflictError("연결 계약의 종결 상태를 동기화하지 못했습니다.")
        return {"status": "CLOSED", "remaining_open_recovery_claims": 0}

    async def close(
        self,
        claim_id: str,
        payload: RecoveryCloseRequest,
        *,
        actor_user_id: str,
        actor_role: str,
    ) -> dict[str, Any]:
        fingerprint = _payload_fingerprint("recovery_close", payload)
        replay = await self._events.find_idempotent(claim_id, payload.idempotency_key)
        if replay:
            _assert_same_payload(replay, fingerprint)
            if replay.get("event_type") != "RecoveryClaimClosed":
                raise StateConflictError("동일한 멱등키가 다른 회수 작업에 사용되었습니다.")
            if replay.get("operation_status") == "PENDING":
                recovered = await self._reconcile_pending_event(
                    replay,
                    fingerprint,
                )
                if recovered:
                    claim = await self._get_claim(claim_id)
                    parent_sync = await self._sync_parent_if_all_closed(
                        claim,
                        actor_user_id=actor_user_id,
                        actor_role=actor_role,
                        closed_at=claim.get("closed_at") or now_kst_iso(),
                    )
                    return {
                        **_public_claim(claim),
                        "close_event": recovered,
                        "parent_sync": parent_sync,
                        "idempotent_replay": True,
                        "reconciled": True,
                    }
            else:
                claim = await self._get_claim(claim_id)
                parent_sync = await self._sync_parent_if_all_closed(
                    claim,
                    actor_user_id=actor_user_id,
                    actor_role=actor_role,
                    closed_at=claim.get("closed_at") or now_kst_iso(),
                )
                return {
                    **_public_claim(claim),
                    "close_event": replay,
                    "parent_sync": parent_sync,
                    "idempotent_replay": True,
                }
        claim = await self._get_claim(claim_id)
        if claim_is_closed(claim):
            closure = claim.get("closure") or {}
            if payload.idempotency_key and closure.get("idempotency_key") == payload.idempotency_key:
                stored_fingerprint = closure.get("payload_fingerprint")
                if stored_fingerprint and stored_fingerprint != fingerprint:
                    raise StateConflictError("동일한 멱등키를 다른 종결 내용에 재사용할 수 없습니다.")
                parent_sync = await self._sync_parent_if_all_closed(
                    claim,
                    actor_user_id=actor_user_id,
                    actor_role=actor_role,
                    closed_at=claim.get("closed_at") or now_kst_iso(),
                )
                return {
                    **_public_claim(claim),
                    "parent_sync": parent_sync,
                    "idempotent_replay": True,
                }
            raise StateConflictError("이미 종결된 채권입니다.")
        balances = normalize_claim_balances(claim)
        if payload.reason == "FULL_RECOVERY" and balances["total"] != 0:
            raise StateConflictError("전액회수 종결은 원장 잔액이 0원일 때만 가능합니다.")

        now = now_kst_iso()
        closure = {
            "reason": payload.reason,
            "note": payload.note,
            "residual_balance_won": balances["total"],
            "closed_by": actor_user_id,
            "closed_by_role": actor_role,
            "closed_at": now,
            "idempotency_key": payload.idempotency_key,
            "payload_fingerprint": fingerprint,
        }
        expected_version = _int_value(claim.get("version"))
        # 종결 이벤트 저장을 먼저 예약해 이벤트 insert 실패 뒤 채권만 종결되는
        # 상태를 방지한다. 실제 공개 이력에는 CAS 확정된 이벤트만 노출한다.
        close_provenance = _claim_provenance(claim)
        event_id = _stable_action_id("rc-close", claim_id, payload.idempotency_key)
        event = {
            "_id": event_id,
            "recovery_claim_id": claim_id,
            "event_type": "RecoveryClaimClosed",
            "status_axis": "recovery_stage",
            "before": claim.get("recovery_stage") or claim.get("stage") or "Registered",
            "after": "Closing",
            "note": payload.note or payload.reason,
            "actor_user_id": actor_user_id,
            "actor_role": actor_role,
            "occurred_at": now,
            "idempotency_key": payload.idempotency_key,
            "claim_version_before": expected_version,
            "operation_status": "PENDING",
            "payload_fingerprint": fingerprint,
            "receipt_key": _receipt_key(event_id),
            **_source_response_fields(close_provenance),
        }
        if payload.idempotency_key is None:
            event.pop("idempotency_key")
        try:
            await self._events.insert(event)
        except DuplicateKeyError:
            replay = await self._events.get_by_id(event["_id"])
            if replay and replay.get("operation_status") == "PENDING":
                raise StateConflictError("동일한 종결 요청이 처리 중입니다.")
            raise StateConflictError("이미 처리된 종결 이벤트입니다.")
        try:
            updated = await self._claims.update_open_with_version(
                claim_id,
                expected_version,
                set_fields={
                    "is_closed": True,
                    "recovery_stage": "Closing",
                    "axis_status.recovery_stage": "Closing",
                    "closure": closure,
                    "closed_at": now,
                    _receipt_field(event_id): _receipt_value(
                        event_id, "recovery_close", fingerprint, now
                    ),
                    "updated_at": now,
                },
            )
        except Exception:
            # close CAS 적용 후 응답만 유실될 수 있으므로 PENDING을 보존한다.
            raise
        if not updated:
            await self._events.discard_pending(event["_id"])
            raise StateConflictError("동시에 채권이 변경되었거나 이미 종결되었습니다.")
        if not await self._events.mark_committed(event["_id"]):
            raise StateConflictError("종결 이벤트 확정에 실패했습니다. 운영 점검이 필요합니다.")
        event["operation_status"] = "COMMITTED"
        parent_sync = await self._sync_parent_if_all_closed(
            updated,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            closed_at=now,
        )
        return {
            **_public_claim(updated),
            "close_event": event,
            "parent_sync": parent_sync,
            "idempotent_replay": False,
        }

"""HUG 사고 전 계약 목록·상세 조합 조회 서비스."""

from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.exceptions import ResourceNotFoundError
from app.repositories.contract_repository import ContractRepository, TimelineRepository
from app.repositories.prevention_repository import (
    AccidentPredictionRepository,
    EvidenceBundleRepository,
    PreventionCaseRepository,
    PreventiveActionRepository,
)
from app.repositories.property_repository import PropertyRepository
from app.schemas.provenance import source_metadata
from app.services.accident_prediction_service import (
    AccidentPredictionService,
    MODEL_BASIS,
    PRE_INCIDENT_STATUSES,
)
from app.services.prevention_service import calculate_priority_components, dday_stage


def _is_demo_contract(contract: dict[str, Any]) -> bool:
    return (
        str(contract.get("_id", "")).startswith("demo-")
        or bool(contract.get("is_demo"))
        or (contract.get("source") or {}).get("data_mode") == "DEMO"
    )


def _data_mode_query(data_mode: str) -> dict[str, Any]:
    if data_mode == "DEMO":
        return {
            "$or": [
                {"_id": {"$regex": "^demo-"}},
                {"is_demo": True},
                {"source.data_mode": "DEMO"},
            ]
        }
    return {
        "_id": {"$not": {"$regex": "^demo-"}},
        "is_demo": {"$ne": True},
        "source.data_mode": {"$ne": "DEMO"},
    }


def _prediction_view(document: dict[str, Any] | None) -> dict[str, Any] | None:
    if not document:
        return None
    return {
        "prediction_id": document["_id"],
        "pu_risk_score": document.get("pu_risk_score"),
        "risk_percentile": document.get("risk_percentile"),
        "accident_probability": document.get("accident_probability"),
        "calibration_status": document.get("calibration_status"),
        "prediction_status": document.get("prediction_status"),
        "failure_reason": document.get("failure_reason", []),
        "model_version": document.get("model_version"),
        "model_sha256": document.get("model_sha256"),
        "feature_snapshot": document.get("feature_snapshot", {}),
        "top_factors": document.get("top_factors", []),
        "data_completeness": document.get("data_completeness", 0.0),
        "basis": document.get("basis", MODEL_BASIS),
        "predicted_at": document.get("predicted_at"),
        "valid_until": document.get("valid_until"),
        "source": document.get("source"),
    }


def _bundle_summary(bundles: list[dict[str, Any]]) -> dict[str, Any]:
    if not bundles:
        return {
            "status": "NotStarted",
            "required_count": 0,
            "submitted_count": 0,
            "verified_count": 0,
            "overdue_count": 0,
            "completion_ratio": 0.0,
            "checkpoints": [],
        }
    required = sum(bundle.get("required_count", 0) for bundle in bundles)
    submitted = sum(bundle.get("submitted_count", 0) for bundle in bundles)
    verified = sum(bundle.get("verified_count", 0) for bundle in bundles)
    overdue = sum(bundle.get("overdue_count", 0) for bundle in bundles)
    status = (
        "Completed"
        if required and verified == required
        else "Overdue"
        if overdue
        else "InReview"
        if submitted
        else "Pending"
    )
    return {
        "status": status,
        "required_count": required,
        "submitted_count": submitted,
        "verified_count": verified,
        "overdue_count": overdue,
        "completion_ratio": round(verified / required, 4) if required else 0.0,
        "checkpoints": [
            {
                "evidence_bundle_id": bundle["_id"],
                "checkpoint": bundle["checkpoint"],
                "status": bundle["status"],
                "due_at": bundle["due_at"],
                "completion_ratio": bundle["completion_ratio"],
            }
            for bundle in bundles
        ],
    }


class HugContractService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._db = db
        self._contracts = ContractRepository(db)
        self._properties = PropertyRepository(db)
        self._timeline = TimelineRepository(db)
        self._predictions = AccidentPredictionRepository(db)
        self._cases = PreventionCaseRepository(db)
        self._actions = PreventiveActionRepository(db)
        self._bundles = EvidenceBundleRepository(db)
        self._accident = AccidentPredictionService(db)

    async def _prefetch_related(
        self, contracts: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """목록 조회용 연관 문서 일괄 조회.

        계약당 6회 개별 조회(§20.2 규모감 시딩 시 요청당 수백 roundtrip)를 컬렉션당
        1회 $in 조회로 줄인다. 정렬 후 첫 문서를 취해 per-contract 최신 선택 규칙
        (repository latest_for_contract)과 동일한 결과를 만든다.
        """
        contract_ids = [contract["_id"] for contract in contracts]
        property_ids = list(
            {contract.get("property_id") for contract in contracts if contract.get("property_id")}
        )
        risk_ids = list(
            {
                contract.get("risk_assessment_id")
                for contract in contracts
                if contract.get("risk_assessment_id")
            }
        )
        properties = {
            document["_id"]: document
            async for document in self._properties.collection.find(
                {"_id": {"$in": property_ids}}
            )
        }
        predictions: dict[str, dict[str, Any]] = {}
        async for document in self._predictions.collection.find(
            {"contract_id": {"$in": contract_ids}}
        ).sort([("predicted_at", -1), ("_id", -1)]):
            predictions.setdefault(document["contract_id"], document)
        cases: dict[str, dict[str, Any]] = {}
        async for document in self._cases.collection.find(
            {"contract_id": {"$in": contract_ids}}
        ).sort([("updated_at", -1), ("_id", -1)]):
            cases.setdefault(document["contract_id"], document)
        bundles: dict[str, list[dict[str, Any]]] = {}
        async for document in self._bundles.collection.find(
            {"contract_id": {"$in": contract_ids}}
        ).sort([("sequence", 1), ("created_at", 1)]):
            bundles.setdefault(document["contract_id"], []).append(document)
        actions: dict[str, list[dict[str, Any]]] = {}
        async for document in self._actions.collection.find(
            {"contract_id": {"$in": contract_ids}}
        ).sort([("due_at", 1), ("requested_at", 1)]):
            actions.setdefault(document["contract_id"], []).append(document)
        notifications: dict[str, list[dict[str, Any]]] = {}
        async for document in self._db.notifications.find(
            {"contract_id": {"$in": contract_ids}, "category": "prevention_alert"}
        ).sort("created_at", -1):
            notifications.setdefault(document["contract_id"], []).append(document)
        risks: dict[str, dict[str, Any]] = {}
        if risk_ids:
            async for document in self._db.risk_assessments.find(
                {"$or": [{"_id": {"$in": risk_ids}}, {"case_id": {"$in": risk_ids}}]}
            ):
                for key in (document.get("_id"), document.get("case_id")):
                    if key in risk_ids:
                        risks.setdefault(key, document)
        return {
            "properties": properties,
            "predictions": predictions,
            "cases": cases,
            "bundles": bundles,
            "actions": actions,
            "notifications": notifications,
            "risks": risks,
        }

    async def _rule_risk(
        self,
        contract: dict[str, Any],
        related: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        risk_id = contract.get("risk_assessment_id")
        if not risk_id:
            return None
        if related is not None:
            document = related["risks"].get(risk_id)
        else:
            document = await self._db.risk_assessments.find_one(
                {"$or": [{"_id": risk_id}, {"case_id": risk_id}]}
            )
        if not document:
            return None
        return {
            "risk_assessment_id": document["_id"],
            "risk_score": document.get("risk_score"),
            "risk_grade": document.get("risk_grade"),
            "risk_factors": document.get("risk_factors", []),
            "data_completeness": document.get("data_completeness"),
            "assessment_mode": document.get("assessment_mode"),
            "created_at": document.get("created_at"),
        }

    async def _notification_summary(
        self,
        contract_id: str,
        related: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if related is not None:
            notifications = related["notifications"].get(contract_id, [])
        else:
            notifications = [
                document
                async for document in self._db.notifications.find(
                    {"contract_id": contract_id, "category": "prevention_alert"}
                ).sort("created_at", -1)
            ]
        summary: dict[str, Any] = {}
        for role in ("tenant", "landlord", "hug_admin"):
            role_items = [item for item in notifications if item.get("target_role") == role]
            summary[role] = {
                "sent_count": len(role_items),
                "read_count": sum(bool(item.get("is_read")) for item in role_items),
                "acknowledged_count": sum(bool(item.get("acknowledged_at")) for item in role_items),
                "latest_sent_at": role_items[0].get("created_at") if role_items else None,
            }
        return summary

    async def _item(
        self,
        contract: dict[str, Any],
        *,
        as_of: date,
        deposit_percentile: float,
        include_detail: bool = False,
        related: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if related is not None:
            property_doc = related["properties"].get(contract.get("property_id"))
            prediction = related["predictions"].get(contract["_id"])
            prevention_case = related["cases"].get(contract["_id"])
            bundles = related["bundles"].get(contract["_id"], [])
            actions = related["actions"].get(contract["_id"], [])
        else:
            property_doc = await self._properties.get_by_id(contract.get("property_id", ""))
            prediction = await self._predictions.latest_for_contract(contract["_id"])
            prevention_case = await self._cases.latest_for_contract(contract["_id"])
            bundles = await self._bundles.list_for_contract(contract["_id"])
            actions = await self._actions.list_for_contract(contract["_id"])
        try:
            d_day = (date.fromisoformat(contract["contract_end_date"]) - as_of).days
        except (KeyError, TypeError, ValueError):
            d_day = 99999
        unresolved = 1.0 if any(bundle.get("overdue_count", 0) for bundle in bundles) else 0.5 if bundles else 0.0
        priority_score, priority_components = calculate_priority_components(
            risk_percentile=prediction.get("risk_percentile") if prediction else None,
            deposit_percentile=deposit_percentile,
            d_day=d_day,
            unresolved_severity=unresolved,
        )
        if prevention_case:
            # 오케스트레이터가 Rule 신호까지 포함해 산정한 저장값을 우선한다.
            priority_score = prevention_case.get("priority_score", priority_score)
            priority_components = prevention_case.get("priority_components", priority_components)
        is_demo = contract["_id"].startswith("demo-") or bool(contract.get("is_demo"))
        address = (property_doc or {}).get("address", {})
        result: dict[str, Any] = {
            "contract_id": contract["_id"],
            "property_id": contract.get("property_id"),
            "contract_status": contract.get("contract_status"),
            "address": address,
            "address_summary": address.get("road_address") or address.get("jibun_address"),
            "guarantee_product": contract.get("guarantee_product", "전세보증금반환보증"),
            "guarantee_amount": contract.get("guarantee_amount", contract.get("deposit")),
            "guarantee_status": contract.get("guarantee_status", "Active"),
            "deposit": contract.get("deposit"),
            "housing_type": contract.get("housing_type"),
            "contract_start_date": contract.get("contract_start_date"),
            "contract_end_date": contract.get("contract_end_date"),
            "d_day": d_day,
            "d_day_stage": dday_stage(d_day),
            "prediction": _prediction_view(prediction),
            "rule_risk": await self._rule_risk(contract, related),
            "prevention_case": (
                {
                    "prevention_case_id": prevention_case["_id"],
                    "status": prevention_case["status"],
                    "triggers": prevention_case.get("triggers", []),
                    "owner_user_id": prevention_case.get("owner_user_id"),
                    "owner_center": prevention_case.get("owner_center")
                    or contract.get("assigned_center")
                    or contract.get("owner_center"),
                    "next_action": prevention_case.get("next_action"),
                    "due_at": prevention_case.get("due_at"),
                }
                if prevention_case
                else None
            ),
            "prevention_priority": priority_score,
            "priority_components": priority_components,
            "evidence_bundle": _bundle_summary(bundles),
            "notification_status": await self._notification_summary(contract["_id"], related),
            "next_action": (
                prevention_case.get("next_action")
                if prevention_case
                # §20.5 P4 — 예방 케이스가 없어도 만기 경과 계약은 사고요건 확인을 안내한다.
                else ("미반환 여부 확인·사고신고 안내" if d_day < 0 else "정상 모니터링")
            ),
            "owner_center": contract.get("assigned_center") or contract.get("owner_center"),
            "assignee_user_id": contract.get("assignee_user_id"),
            "source": source_metadata(
                data_mode="DEMO" if is_demo else "LIVE",
                source_type="demo_scenario" if is_demo else "user_submitted",
                source_dataset="prevention-demo-seed" if is_demo else "platform-contract-ledger",
                as_of_date=as_of.isoformat(),
                scenario_id=contract.get("scenario_id"),
                basis="사고접수 전 보증계약 업무대장",
                is_demo=is_demo,
            ),
        }
        if include_detail:
            result["evidence_bundles"] = bundles
            result["preventive_actions"] = actions
            result["prediction_history"] = [
                _prediction_view(item)
                for item in await self._predictions.list_for_contract(contract["_id"])
            ]
            result["timeline"] = await self._timeline.list_for_contract(contract["_id"])
        return result

    async def list_contracts(
        self,
        *,
        page: int,
        size: int,
        as_of_date: date | None = None,
        contract_status: str | None = None,
        prediction_status: str | None = None,
        min_risk_percentile: float | None = None,
        prevention_status: str | None = None,
        checkpoint: str | None = None,
        region: str | None = None,
        data_mode: str = "LIVE",
    ) -> dict[str, Any]:
        as_of = as_of_date or date.today()
        if data_mode not in {"LIVE", "DEMO"}:
            raise ValueError("data_mode must be LIVE or DEMO")
        query: dict[str, Any] = {
            "contract_status": {"$in": list(PRE_INCIDENT_STATUSES)},
            **_data_mode_query(data_mode),
        }
        if contract_status:
            if contract_status not in PRE_INCIDENT_STATUSES:
                return {
                    "items": [],
                    "pagination": {"page": page, "size": size, "total_elements": 0, "total_pages": 0},
                    "as_of_date": as_of.isoformat(),
                    "data_mode_filter": data_mode,
                }
            query["contract_status"] = contract_status
        contracts = [document async for document in self._contracts.collection.find(query)]
        deposits = np.sort(
            np.asarray([max(float(contract.get("deposit") or 0), 0) for contract in contracts])
        )
        related = await self._prefetch_related(contracts) if contracts else None
        items = []
        for contract in contracts:
            deposit = max(float(contract.get("deposit") or 0), 0)
            percentile = float(
                np.searchsorted(deposits, deposit, side="right") / max(len(deposits), 1)
            )
            item = await self._item(
                contract, as_of=as_of, deposit_percentile=percentile, related=related
            )
            prediction = item.get("prediction")
            case = item.get("prevention_case")
            if prediction_status and (prediction or {}).get("prediction_status") != prediction_status:
                continue
            if min_risk_percentile is not None and float((prediction or {}).get("risk_percentile") or 0) < min_risk_percentile:
                continue
            if prevention_status and (case or {}).get("status") != prevention_status:
                continue
            if checkpoint and item.get("d_day_stage") != checkpoint:
                continue
            if region:
                address_text = " ".join(str(value) for value in item.get("address", {}).values())
                if region not in address_text:
                    continue
            items.append(item)
        items.sort(key=lambda item: (-float(item["prevention_priority"]), item["contract_id"]))
        total = len(items)
        start = (page - 1) * size
        page_items = items[start : start + size]
        return {
            "items": page_items,
            "pagination": {
                "page": page,
                "size": size,
                "total_elements": total,
                "total_pages": (total + size - 1) // size,
            },
            "as_of_date": as_of.isoformat(),
            "data_mode_filter": data_mode,
        }

    async def get_contract(
        self, contract_id: str, as_of_date: date | None = None
    ) -> dict[str, Any]:
        contract = await self._contracts.get_by_id(contract_id)
        if not contract or contract.get("contract_status") not in PRE_INCIDENT_STATUSES:
            raise ResourceNotFoundError("사고접수 전 계약을 찾을 수 없습니다.")
        data_mode = "DEMO" if _is_demo_contract(contract) else "LIVE"
        all_contracts = [
            document
            async for document in self._contracts.collection.find(
                {
                    "contract_status": {"$in": list(PRE_INCIDENT_STATUSES)},
                    **_data_mode_query(data_mode),
                }
            )
        ]
        deposits = np.sort(
            np.asarray([max(float(item.get("deposit") or 0), 0) for item in all_contracts])
        )
        deposit = max(float(contract.get("deposit") or 0), 0)
        percentile = float(
            np.searchsorted(deposits, deposit, side="right") / max(len(deposits), 1)
        )
        return await self._item(
            contract,
            as_of=as_of_date or date.today(),
            deposit_percentile=percentile,
            include_detail=True,
        )

    async def refresh_prediction(self, contract_id: str):
        return await self._accident.refresh_or_record_failure(contract_id)

    async def refresh_predictions(
        self, contract_ids: list[str] | None = None, data_mode: str = "LIVE"
    ):
        return await self._accident.refresh_batch(contract_ids, data_mode)

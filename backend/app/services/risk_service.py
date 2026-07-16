from __future__ import annotations

from datetime import date, datetime

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.exceptions import ResourceNotFoundError
from app.repositories.landlord_repository import LandlordRepository
from app.repositories.property_repository import PropertyRepository
from app.repositories.risk_repository import (
    BuildingRegistrySnapshotRepository,
    OfficialPriceSnapshotRepository,
    RegistrySnapshotRepository,
    RiskAssessmentRepository,
)
from app.schemas.risk import RiskAssessmentResponse, RiskDiagnoseRequest, RiskFactor
from app.services.risk_engine import RiskEngineInputs, evaluate
from app.utils.datetime_utils import now_kst_iso, new_uuid


def _status_of(doc: dict | None) -> str:
    if not doc:
        return "missing"
    return "live" if doc.get("source_system") == "api_live" else "mock"


def _building_age_years(doc: dict | None) -> int | None:
    if not doc or doc.get("source_system") != "api_live":
        return None
    response = doc.get("response")
    if isinstance(response, dict):
        approval = response.get("useAprDay") or response.get("use_approval_date")
        if approval:
            try:
                approved = datetime.strptime(str(approval)[:8], "%Y%m%d")
                return max(date.today().year - approved.year, 0)
            except ValueError:
                return None
    return None


class RiskService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._risk_assessments = RiskAssessmentRepository(db)
        self._properties = PropertyRepository(db)
        self._landlords = LandlordRepository(db)
        self._registry = RegistrySnapshotRepository(db)
        self._building = BuildingRegistrySnapshotRepository(db)
        self._official_price = OfficialPriceSnapshotRepository(db)

    async def diagnose(self, payload: RiskDiagnoseRequest, contract_id: str | None = None) -> RiskAssessmentResponse:
        property_doc = await self._properties.get_by_id(payload.property_id)
        if not property_doc:
            raise ResourceNotFoundError("매물 정보를 찾을 수 없습니다.")

        registry_doc = await self._registry.find_latest_by_property(payload.property_id)
        building_doc = await self._building.find_latest_by_property(payload.property_id)
        official_price_doc = await self._official_price.find_latest_by_property(payload.property_id)

        landlord_doc = None
        if payload.landlord_id:
            landlord_doc = await self._landlords.get_by_id(payload.landlord_id)

        registry_status = _status_of(registry_doc)
        official_price_status = _status_of(official_price_doc)
        building_status = _status_of(building_doc)

        has_seizure = mortgage_ratio = rights_burden_ratio = None
        if registry_status == "live":
            features = (registry_doc or {}).get("features") or {}
            has_seizure = features.get("has_seizure")
            mortgage_ratio = features.get("mortgage_ratio")
            rights_burden_ratio = features.get("rights_burden_ratio")

        official_price_value = None
        jeonse_ratio = None
        if official_price_status == "live":
            official_price_value = (official_price_doc or {}).get("official_price")
            if official_price_value:
                jeonse_ratio = round(payload.deposit / official_price_value, 4)

        business_status = "missing"
        business_closed_flag = None
        dart_status = "missing"
        dart_disclosure_flag = None
        if landlord_doc:
            if landlord_doc.get("business_status") is not None:
                business_status = "live"
                business_closed_flag = landlord_doc.get("business_status") == "폐업자"
            if landlord_doc.get("dart_corp_name") is not None:
                dart_status = "live"
                dart_disclosure_flag = bool(landlord_doc.get("dart_corp_name"))

        engine_inputs = RiskEngineInputs(
            deposit=payload.deposit,
            landlord_type=payload.landlord_type.value,
            housing_type=payload.housing_type.value,
            registry_status=registry_status,
            has_seizure=has_seizure,
            mortgage_ratio=mortgage_ratio,
            rights_burden_ratio=rights_burden_ratio,
            official_price_status=official_price_status,
            official_price=official_price_value,
            jeonse_ratio=jeonse_ratio,
            building_registry_status=building_status,
            building_age_years=_building_age_years(building_doc),
            business_status_source_status=business_status,
            business_closed_flag=business_closed_flag,
            dart_status=dart_status,
            dart_disclosure_flag=dart_disclosure_flag,
        )
        result = evaluate(engine_inputs)

        now = now_kst_iso()
        case_id = new_uuid()
        risk_assessment_id = new_uuid()
        data_sources = [
            f"{name}:{status}"
            for name, status in result.source_status.items()
            if status != "missing"
        ] or ["no_external_data_available"]

        doc = {
            "_id": risk_assessment_id,
            "case_id": case_id,
            "contract_id": contract_id,
            "property_id": payload.property_id,
            "risk_score": result.risk_score,
            "risk_grade": result.risk_grade,
            "assessment_mode": "rule_based_fallback",
            "confidence": result.confidence,
            "data_completeness": result.data_completeness,
            "risk_factors": [f.__dict__ for f in result.risk_factors],
            "positive_factors": [f.__dict__ for f in result.positive_factors],
            "missing_fields": result.missing_fields,
            "required_documents": result.required_documents,
            "recommended_actions": result.recommended_actions,
            "source_status": result.source_status,
            "risk_reasons": result.risk_reasons,
            "resolvable_risks": result.resolvable_risks,
            "unresolvable_risks": result.unresolvable_risks,
            "data_sources": data_sources,
            "fetched_at": now,
            "created_at": now,
            "blockchain_tx_id": None,
        }
        await self._risk_assessments.insert(doc)
        return _to_response(doc)

    async def get_by_case_id(self, case_id: str) -> RiskAssessmentResponse:
        doc = await self._risk_assessments.find_by_case_id(case_id)
        if not doc:
            raise ResourceNotFoundError("위험진단 결과를 찾을 수 없습니다.")
        return _to_response(doc)


def _to_response(doc: dict) -> RiskAssessmentResponse:
    return RiskAssessmentResponse(
        diagnosis_id=doc["_id"],
        case_id=doc["case_id"],
        risk_assessment_id=doc["_id"],
        contract_id=doc.get("contract_id"),
        property_id=doc["property_id"],
        risk_grade=doc["risk_grade"],
        risk_reasons=doc.get("risk_reasons", []),
        resolvable_risks=doc.get("resolvable_risks", []),
        unresolvable_risks=doc.get("unresolvable_risks", []),
        data_sources=doc.get("data_sources", []),
        risk_score=doc["risk_score"],
        confidence=doc["confidence"],
        data_completeness=doc["data_completeness"],
        risk_factors=[RiskFactor(**f) for f in doc.get("risk_factors", [])],
        positive_factors=[RiskFactor(**f) for f in doc.get("positive_factors", [])],
        missing_fields=doc.get("missing_fields", []),
        required_documents=doc.get("required_documents", []),
        recommended_actions=doc.get("recommended_actions", []),
        source_status=doc.get("source_status", {}),
        fetched_at=doc["fetched_at"],
        created_at=doc["created_at"],
        blockchain_tx_id=doc.get("blockchain_tx_id"),
    )

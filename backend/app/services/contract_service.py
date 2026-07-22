from __future__ import annotations

from datetime import date

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.exceptions import ResourceNotFoundError, StateConflictError
from app.models.enums import ContractStatus
from app.repositories.contract_repository import ContractRepository, ReturnPlanRepository, TimelineRepository
from app.repositories.property_repository import PropertyRepository
from app.schemas.common import build_pagination
from app.schemas.contract import (
    ContractCreateRequest,
    ContractResponse,
    ContractTimelineResponse,
    ReturnPlanCreateRequest,
    ReturnPlanResponse,
    TimelineEventResponse,
)
from app.utils.datetime_utils import now_kst_iso, new_uuid


def _to_response(doc: dict) -> ContractResponse:
    return ContractResponse(
        contract_id=doc["_id"],
        property_id=doc["property_id"],
        tenant_user_id=doc["tenant_user_id"],
        landlord_user_id=doc.get("landlord_user_id"),
        landlord_id=doc.get("landlord_id"),
        contract_status=doc["contract_status"],
        deposit=doc["deposit"],
        contract_start_date=doc["contract_start_date"],
        contract_end_date=doc["contract_end_date"],
        landlord_type=doc["landlord_type"],
        housing_type=doc["housing_type"],
        risk_assessment_id=doc.get("risk_assessment_id"),
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


class ContractService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._contracts = ContractRepository(db)
        self._properties = PropertyRepository(db)
        self._timeline = TimelineRepository(db)
        self._return_plans = ReturnPlanRepository(db)

    async def create(self, tenant_user_id: str, payload: ContractCreateRequest) -> ContractResponse:
        if not await self._properties.exists(payload.property_id):
            raise ResourceNotFoundError("매물 정보를 찾을 수 없습니다.")

        duplicate = await self._contracts.find_duplicate(
            tenant_user_id, payload.property_id, payload.contract_start_date.isoformat()
        )
        if duplicate:
            raise StateConflictError("동일한 매물·계약시작일로 이미 계약이 생성되어 있습니다.")

        now = now_kst_iso()
        contract_id = new_uuid()
        doc = {
            "_id": contract_id,
            "property_id": payload.property_id,
            "tenant_user_id": tenant_user_id,
            "landlord_user_id": None,
            "landlord_id": payload.landlord_id,
            "contract_status": ContractStatus.DRAFT.value,
            "deposit": payload.deposit,
            "contract_start_date": payload.contract_start_date.isoformat(),
            "contract_end_date": payload.contract_end_date.isoformat(),
            "landlord_type": payload.landlord_type.value,
            "housing_type": payload.housing_type.value,
            "risk_assessment_id": None,
            "created_at": now,
            "updated_at": now,
        }
        await self._contracts.insert(doc)
        await self._timeline.append(
            {
                "_id": new_uuid(),
                "contract_id": contract_id,
                "event_type": "ContractCreated",
                "occurred_at": now,
                "blockchain_status": "NotRequested",
                "blockchain_tx_id": None,
            }
        )
        return _to_response(doc)

    # 계약 후 관리 화면(19.1)의 3자 공동 열람: 관리·상담 역할은 소유 여부와 무관하게 열람만 허용한다.
    _VIEWER_ROLES = ("hug_admin", "system_admin", "advisor")

    async def _get_owned(self, contract_id: str, user_id: str, role: str | None = None) -> dict:
        doc = await self._contracts.get_by_id(contract_id)
        if not doc:
            raise ResourceNotFoundError("계약 정보를 찾을 수 없습니다.")
        if role in self._VIEWER_ROLES:
            return doc
        if user_id not in (doc.get("tenant_user_id"), doc.get("landlord_user_id")):
            raise ResourceNotFoundError("계약 정보를 찾을 수 없습니다.")
        return doc

    async def get(self, contract_id: str, user_id: str, role: str | None = None) -> ContractResponse:
        return _to_response(await self._get_owned(contract_id, user_id, role))

    async def list_for_user(self, user_id: str, page: int, size: int, contract_status: str | None):
        items, total = await self._contracts.list_for_user(user_id, (page - 1) * size, size, contract_status)
        return [_to_response(i) for i in items], build_pagination(page, size, total)

    async def list_all(self, page: int, size: int, contract_status: str | None):
        items, total = await self._contracts.list_all((page - 1) * size, size, contract_status)
        return [_to_response(i) for i in items], build_pagination(page, size, total)

    async def mark_diagnosed(self, contract_id: str, risk_assessment_id: str) -> None:
        contract = await self._contracts.get_by_id(contract_id)
        if not contract:
            return
        await self._contracts.update_fields(
            contract_id,
            {
                "risk_assessment_id": risk_assessment_id,
                "contract_status": ContractStatus.DIAGNOSED.value,
                "updated_at": now_kst_iso(),
            },
        )
        await self._timeline.append(
            {
                "_id": new_uuid(),
                "contract_id": contract_id,
                "event_type": "RiskAssessed",
                "occurred_at": now_kst_iso(),
                "blockchain_status": "NotRequested",
                "blockchain_tx_id": None,
            }
        )

    async def get_timeline(self, contract_id: str, user_id: str, role: str | None = None) -> ContractTimelineResponse:
        contract = await self._get_owned(contract_id, user_id, role)
        events = await self._timeline.list_for_contract(contract_id)
        return ContractTimelineResponse(
            contract_id=contract_id,
            contract_status=contract["contract_status"],
            events=[
                TimelineEventResponse(
                    timeline_event_id=e["_id"],
                    event_type=e["event_type"],
                    occurred_at=e["occurred_at"],
                    blockchain_status=e.get("blockchain_status", "NotRequested"),
                    blockchain_tx_id=e.get("blockchain_tx_id"),
                )
                for e in events
            ],
        )

    async def get_return_plan(self, contract_id: str, user_id: str, role: str | None = None) -> ReturnPlanResponse:
        await self._get_owned(contract_id, user_id, role)
        doc = await self._return_plans.find_by_contract(contract_id)
        if not doc:
            raise ResourceNotFoundError("반환계획 정보를 찾을 수 없습니다.")
        return _return_plan_response(doc)

    async def submit_return_plan(self, user_id: str, payload: ReturnPlanCreateRequest) -> ReturnPlanResponse:
        contract = await self._get_owned(payload.contract_id, user_id)
        existing = await self._return_plans.find_by_contract(payload.contract_id)
        d_day = (payload.planned_return_date - date.today()).days
        fields = {
            "_id": existing["_id"] if existing else new_uuid(),
            "contract_id": payload.contract_id,
            "landlord_response_status": "Responded",
            "early_warning": False,
            "planned_return_date": payload.planned_return_date.isoformat(),
            "return_method": payload.return_method,
            "note": payload.note,
            "d_day": d_day,
            "created_at": existing["created_at"] if existing else now_kst_iso(),
        }
        doc = await self._return_plans.upsert(payload.contract_id, fields)
        await self._timeline.append(
            {
                "_id": new_uuid(),
                "contract_id": payload.contract_id,
                "event_type": "ReturnPlanSubmitted",
                "occurred_at": now_kst_iso(),
                "blockchain_status": "NotRequested",
                "blockchain_tx_id": None,
            }
        )
        return _return_plan_response(doc)


def _return_plan_response(doc: dict) -> ReturnPlanResponse:
    return ReturnPlanResponse(
        return_plan_id=doc["_id"],
        contract_id=doc["contract_id"],
        d_day=doc.get("d_day"),
        landlord_response_status=doc.get("landlord_response_status", "NotResponded"),
        early_warning=doc.get("early_warning", False),
        planned_return_date=doc.get("planned_return_date"),
        return_method=doc.get("return_method"),
        note=doc.get("note"),
        created_at=doc["created_at"],
    )

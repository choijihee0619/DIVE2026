from __future__ import annotations

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import CurrentUser, get_db, get_request_id, require_roles
from app.core.responses import success_response
from app.schemas.risk import RiskDiagnoseRequest
from app.services.risk_service import RiskService

router = APIRouter(tags=["Property-Risk"])


@router.post("/risk/diagnose")
async def diagnose_risk(
    payload: RiskDiagnoseRequest,
    current_user: CurrentUser = Depends(require_roles("tenant")),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    # 과제 지시사항(4절)의 rule-based fallback 요구에 맞춰, 계약의 202(비동기 폴링) 대신
    # 규칙엔진 결과를 동시에 계산해 200으로 즉시 반환한다(README/보고서에 편차로 명시).
    result = await RiskService(db).diagnose(payload)
    return success_response(result, request_id, status_code=200)


@router.get("/risk/{case_id}")
async def get_risk_result(
    case_id: str,
    current_user: CurrentUser = Depends(require_roles("tenant")),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await RiskService(db).get_by_case_id(case_id)
    return success_response(result, request_id)

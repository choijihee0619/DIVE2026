"""HUG 사고 전 계약관리·예측·사전예방 엔드포인트."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import CurrentUser, get_db, get_request_id, require_roles
from app.core.responses import success_response
from app.schemas.hug_contract import (
    AccidentPredictionRefreshBatchRequest,
    PreventionSweepRequest,
    PreventiveActionCreateRequest,
    PreventiveActionUpdateRequest,
)
from app.services.accident_prediction_service import AccidentPredictionService
from app.services.hug_contract_service import HugContractService
from app.services.prevention_service import PreventionService

router = APIRouter(tags=["HUG-PreIncident-Contracts"])
_hug_only = require_roles("hug_admin", "system_admin")


@router.get("/hug/contracts")
async def list_hug_contracts(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    as_of_date: date | None = None,
    contract_status: str | None = None,
    prediction_status: str | None = Query(None, pattern="^(SUCCESS|NOT_SCORABLE|FAILED)$"),
    min_risk_percentile: float | None = Query(None, ge=0, le=1),
    prevention_status: str | None = None,
    checkpoint: str | None = Query(None, pattern="^(D90|D60|D30)$"),
    region: str | None = None,
    data_mode: str = Query("LIVE", pattern="^(LIVE|DEMO)$"),
    current_user: CurrentUser = Depends(_hug_only),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await HugContractService(db).list_contracts(
        page=page,
        size=size,
        as_of_date=as_of_date,
        contract_status=contract_status,
        prediction_status=prediction_status,
        min_risk_percentile=min_risk_percentile,
        prevention_status=prevention_status,
        checkpoint=checkpoint,
        region=region,
        data_mode=data_mode,
    )
    return success_response(result, request_id)


@router.post("/hug/contracts/predictions/refresh")
async def refresh_hug_contract_predictions(
    payload: AccidentPredictionRefreshBatchRequest,
    current_user: CurrentUser = Depends(_hug_only),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await HugContractService(db).refresh_predictions(
        payload.contract_ids, payload.data_mode
    )
    return success_response(result, request_id)


@router.post("/hug/contracts/prevention/sweep")
async def sweep_hug_contract_prevention(
    payload: PreventionSweepRequest,
    current_user: CurrentUser = Depends(_hug_only),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await PreventionService(db).run_sweep(
        payload.as_of_date, payload.contract_ids, payload.data_mode
    )
    return success_response(result, request_id)


@router.get("/hug/contracts/{contract_id}")
async def get_hug_contract(
    contract_id: str,
    as_of_date: date | None = None,
    current_user: CurrentUser = Depends(_hug_only),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await HugContractService(db).get_contract(contract_id, as_of_date)
    return success_response(result, request_id)


@router.get("/hug/contracts/{contract_id}/prediction")
async def get_hug_contract_prediction(
    contract_id: str,
    current_user: CurrentUser = Depends(_hug_only),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await AccidentPredictionService(db).latest(contract_id)
    return success_response(result, request_id)


@router.post("/hug/contracts/{contract_id}/prediction/refresh")
async def refresh_hug_contract_prediction(
    contract_id: str,
    current_user: CurrentUser = Depends(_hug_only),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await HugContractService(db).refresh_prediction(contract_id)
    return success_response(result, request_id)


@router.get("/hug/contracts/{contract_id}/prevention")
async def get_hug_contract_prevention(
    contract_id: str,
    current_user: CurrentUser = Depends(_hug_only),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await PreventionService(db).get_contract_prevention(contract_id)
    return success_response(result, request_id)


@router.post("/hug/contracts/{contract_id}/preventive-actions", status_code=201)
async def create_hug_contract_preventive_action(
    contract_id: str,
    payload: PreventiveActionCreateRequest,
    current_user: CurrentUser = Depends(_hug_only),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await PreventionService(db).create_action(
        contract_id, payload, current_user.user_id, current_user.role
    )
    return success_response(result, request_id, status_code=201)


@router.patch("/preventive-actions/{action_id}")
async def update_preventive_action(
    action_id: str,
    payload: PreventiveActionUpdateRequest,
    current_user: CurrentUser = Depends(_hug_only),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await PreventionService(db).update_action(
        action_id, payload, current_user.user_id, current_user.role
    )
    return success_response(result, request_id)

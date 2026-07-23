"""HUG 등록채권 회수관리 API (hug_admin/system_admin 전용)."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import CurrentUser, get_db, get_request_id, require_roles
from app.core.responses import success_response
from app.schemas.recovery import (
    AuctionCaseCreateRequest,
    AuctionCaseUpdateRequest,
    LegalCaseCreateRequest,
    LegalCaseUpdateRequest,
    RecoveryCloseRequest,
    RecoveryEventCreateRequest,
    RecoveryLedgerEntryCreateRequest,
    RecoveryPredictRequest,
)
from app.services.recovery_service import RecoveryService

router = APIRouter(prefix="/hug/recovery", tags=["HUG-Recovery"])
_hug_only = require_roles("hug_admin", "system_admin")


@router.get("/summary")
async def recovery_summary(
    data_mode: Literal["LIVE", "DEMO"] = "LIVE",
    current_user: CurrentUser = Depends(_hug_only),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    return success_response(await RecoveryService(db).summary(data_mode=data_mode), request_id)


@router.get("/claims")
async def list_recovery_claims(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    lifecycle: Literal["active", "closed", "all"] = "active",
    recovery_stage: str | None = None,
    claim_type: str | None = None,
    collection_route: str | None = None,
    data_mode: Literal["LIVE", "DEMO"] = "LIVE",
    sort_by: Literal["updated_at", "created_at", "priority_score", "balance", "due_at"] = "updated_at",
    descending: bool = True,
    current_user: CurrentUser = Depends(_hug_only),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await RecoveryService(db).list_claims(
        page,
        size,
        lifecycle=None if lifecycle == "all" else lifecycle,
        recovery_stage=recovery_stage,
        claim_type=claim_type,
        collection_route=collection_route,
        data_mode=data_mode,
        sort_by=sort_by,
        descending=descending,
    )
    return success_response(result, request_id)


@router.get("/claims/{claim_id}")
async def get_recovery_claim(
    claim_id: str,
    current_user: CurrentUser = Depends(_hug_only),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    return success_response(await RecoveryService(db).detail(claim_id), request_id)


@router.post("/claims/{claim_id}/events", status_code=201)
async def create_recovery_event(
    claim_id: str,
    payload: RecoveryEventCreateRequest,
    current_user: CurrentUser = Depends(_hug_only),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await RecoveryService(db).add_event(
        claim_id,
        payload,
        actor_user_id=current_user.user_id,
        actor_role=current_user.role,
    )
    return success_response(result, request_id, status_code=201)


@router.post("/claims/{claim_id}/ledger-entries", status_code=201)
async def create_recovery_ledger_entry(
    claim_id: str,
    payload: RecoveryLedgerEntryCreateRequest,
    current_user: CurrentUser = Depends(_hug_only),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await RecoveryService(db).add_ledger_entry(
        claim_id,
        payload,
        actor_user_id=current_user.user_id,
        actor_role=current_user.role,
    )
    return success_response(result, request_id, status_code=201)


@router.post("/claims/{claim_id}/legal-cases", status_code=201)
async def create_recovery_legal_case(
    claim_id: str,
    payload: LegalCaseCreateRequest,
    current_user: CurrentUser = Depends(_hug_only),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await RecoveryService(db).create_legal_case(
        claim_id,
        payload,
        actor_user_id=current_user.user_id,
        actor_role=current_user.role,
    )
    return success_response(result, request_id, status_code=201)


@router.patch("/claims/{claim_id}/legal-cases/{case_id}")
async def update_recovery_legal_case(
    claim_id: str,
    case_id: str,
    payload: LegalCaseUpdateRequest,
    current_user: CurrentUser = Depends(_hug_only),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await RecoveryService(db).update_legal_case(
        claim_id,
        case_id,
        payload,
        actor_user_id=current_user.user_id,
        actor_role=current_user.role,
    )
    return success_response(result, request_id)


@router.post("/claims/{claim_id}/auction-cases", status_code=201)
async def create_recovery_auction_case(
    claim_id: str,
    payload: AuctionCaseCreateRequest,
    current_user: CurrentUser = Depends(_hug_only),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await RecoveryService(db).create_auction_case(
        claim_id,
        payload,
        actor_user_id=current_user.user_id,
        actor_role=current_user.role,
    )
    return success_response(result, request_id, status_code=201)


@router.patch("/claims/{claim_id}/auction-cases/{case_id}")
async def update_recovery_auction_case(
    claim_id: str,
    case_id: str,
    payload: AuctionCaseUpdateRequest,
    current_user: CurrentUser = Depends(_hug_only),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await RecoveryService(db).update_auction_case(
        claim_id,
        case_id,
        payload,
        actor_user_id=current_user.user_id,
        actor_role=current_user.role,
    )
    return success_response(result, request_id)


@router.post("/claims/{claim_id}/predict", status_code=201)
async def predict_registered_recovery_claim(
    claim_id: str,
    payload: RecoveryPredictRequest,
    current_user: CurrentUser = Depends(_hug_only),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await RecoveryService(db).predict(
        claim_id,
        payload,
        actor_user_id=current_user.user_id,
    )
    return success_response(result, request_id, status_code=201)


@router.get("/claims/{claim_id}/predictions")
async def list_recovery_predictions(
    claim_id: str,
    current_user: CurrentUser = Depends(_hug_only),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    return success_response(await RecoveryService(db).predictions(claim_id), request_id)


@router.post("/claims/{claim_id}/close")
async def close_recovery_claim(
    claim_id: str,
    payload: RecoveryCloseRequest,
    current_user: CurrentUser = Depends(_hug_only),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await RecoveryService(db).close(
        claim_id,
        payload,
        actor_user_id=current_user.user_id,
        actor_role=current_user.role,
    )
    return success_response(result, request_id)

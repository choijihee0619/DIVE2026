from __future__ import annotations

from fastapi import APIRouter, Depends, File, Query, UploadFile
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import CurrentUser, get_db, get_request_id, require_roles
from app.core.responses import success_response
from app.schemas.evidence import EvidenceRequestCreateRequest, VerificationDecisionRequest
from app.services.evidence_service import EvidenceService

router = APIRouter(tags=["Evidence-Verification"])


@router.post("/evidence-requests", status_code=201)
async def create_evidence_request(
    payload: EvidenceRequestCreateRequest,
    # hug_admin은 상환능력 증빙(19.2)을 임대인에게 직접 요청할 수 있다.
    current_user: CurrentUser = Depends(require_roles("advisor", "system_admin", "tenant", "hug_admin")),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await EvidenceService(db).create_request(payload)
    return success_response(result, request_id, status_code=201)


@router.get("/evidence-requests")
async def list_evidence_requests(
    case_id: str | None = None,
    contract_id: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    # hug_admin은 계약 후 관리 화면(19.1)에서 증빙 현황을 공동 확인한다.
    current_user: CurrentUser = Depends(require_roles("tenant", "landlord", "advisor", "system_admin", "hug_admin")),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    items, pagination = await EvidenceService(db).list_requests(page, size, case_id, contract_id)
    return success_response({"items": items, "pagination": pagination.model_dump()}, request_id)


@router.get("/evidence-requests/{evidence_request_id}")
async def get_evidence_request(
    evidence_request_id: str,
    current_user: CurrentUser = Depends(require_roles("tenant", "landlord", "advisor")),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await EvidenceService(db).get_request(evidence_request_id)
    return success_response(result, request_id)


@router.post("/evidence", status_code=201)
async def submit_evidence(
    evidence_request_id: str,
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(require_roles("landlord")),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await EvidenceService(db).submit_evidence(evidence_request_id, current_user.user_id, file)
    return success_response(result, request_id, status_code=201)


@router.get("/verifications/{evidence_id}")
async def get_verification(
    evidence_id: str,
    current_user: CurrentUser = Depends(require_roles("landlord", "advisor", "verifier")),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await EvidenceService(db).get_verification(evidence_id)
    return success_response(result, request_id)


@router.post("/verifications/{evidence_id}/decision")
async def decide_verification(
    evidence_id: str,
    payload: VerificationDecisionRequest,
    current_user: CurrentUser = Depends(require_roles("advisor")),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await EvidenceService(db).decide_verification(evidence_id, current_user.user_id, payload)
    return success_response(result, request_id)

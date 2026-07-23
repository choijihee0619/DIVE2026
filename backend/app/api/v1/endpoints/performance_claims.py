"""HUG 사고접수·보증이행 업무 API.

상태를 임의 PATCH하지 않고 서류요청, 심사결정, 명도, 지급, 채권등록 같은
업무 액션별 엔드포인트에서 선행조건을 검증한다.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import CurrentUser, get_current_user, get_db, get_request_id, require_roles
from app.core.responses import success_response
from app.schemas.performance_claim import (
    ClaimDocumentDecisionRequest,
    ClaimDocumentSubmitRequest,
    ClaimDocumentsRequest,
    HandoverActionRequest,
    PerformanceClaimCreateRequest,
    PerformanceClaimDecisionRequest,
    RecoveryClaimCreateRequest,
    RecoveryTransferRequest,
    ReviewStartRequest,
    SubrogationPaymentRequest,
)
from app.services.performance_claim_service import PerformanceClaimService, WorkflowActor


router = APIRouter(tags=["HUG-Performance-Claims"])
_hug_only = require_roles("hug_admin", "system_admin")


def _actor(user: CurrentUser) -> WorkflowActor:
    return WorkflowActor(user_id=user.user_id, role=user.role)


@router.get("/hug/incidents")
async def list_hug_incidents(
    status: str | None = None,
    incident_type: str | None = None,
    stage: str | None = None,
    sla_status: str | None = Query(
        default=None, pattern="^(ON_TRACK|DUE_SOON|OVERDUE|PAUSED|COMPLETED)$"
    ),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: CurrentUser = Depends(_hug_only),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await PerformanceClaimService(db).list_hug_incidents(
        page=page,
        size=size,
        status=status,
        incident_type=incident_type,
        stage=stage,
        sla_status=sla_status,
        actor=_actor(current_user),
    )
    return success_response(result, request_id)


@router.get("/hug/incidents/{incident_id}")
async def get_hug_incident(
    incident_id: str,
    current_user: CurrentUser = Depends(_hug_only),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await PerformanceClaimService(db).get_hug_incident(incident_id, _actor(current_user))
    return success_response(result, request_id)


@router.post("/hug/incidents/{incident_id}/claims", status_code=201)
async def create_performance_claim(
    incident_id: str,
    payload: PerformanceClaimCreateRequest,
    current_user: CurrentUser = Depends(_hug_only),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await PerformanceClaimService(db).create_claim(
        incident_id, payload, _actor(current_user), request_id
    )
    return success_response(result, request_id, status_code=201)


@router.get("/performance-claims/{claim_id}")
async def get_performance_claim(
    claim_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await PerformanceClaimService(db).get_claim(claim_id, _actor(current_user))
    return success_response(result, request_id)


@router.get("/performance-claims/{claim_id}/events")
async def list_performance_claim_events(
    claim_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await PerformanceClaimService(db).list_events(claim_id, _actor(current_user))
    return success_response(result, request_id)


@router.post("/performance-claims/{claim_id}/documents/request", status_code=201)
async def request_claim_documents(
    claim_id: str,
    payload: ClaimDocumentsRequest,
    current_user: CurrentUser = Depends(_hug_only),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await PerformanceClaimService(db).request_documents(
        claim_id, payload, _actor(current_user), request_id
    )
    return success_response(result, request_id, status_code=201)


@router.post("/performance-claims/{claim_id}/documents/{document_id}/submit")
async def submit_claim_document(
    claim_id: str,
    document_id: str,
    payload: ClaimDocumentSubmitRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await PerformanceClaimService(db).submit_document(
        claim_id, document_id, payload, _actor(current_user), request_id
    )
    return success_response(result, request_id)


@router.post("/performance-claims/{claim_id}/documents/{document_id}/decision")
async def decide_claim_document(
    claim_id: str,
    document_id: str,
    payload: ClaimDocumentDecisionRequest,
    current_user: CurrentUser = Depends(_hug_only),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await PerformanceClaimService(db).decide_document(
        claim_id, document_id, payload, _actor(current_user), request_id
    )
    return success_response(result, request_id)


@router.post("/performance-claims/{claim_id}/review/start")
async def start_performance_claim_review(
    claim_id: str,
    payload: ReviewStartRequest,
    current_user: CurrentUser = Depends(_hug_only),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await PerformanceClaimService(db).start_review(
        claim_id, payload, _actor(current_user), request_id
    )
    return success_response(result, request_id)


@router.post("/performance-claims/{claim_id}/decision")
async def decide_performance_claim(
    claim_id: str,
    payload: PerformanceClaimDecisionRequest,
    current_user: CurrentUser = Depends(_hug_only),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await PerformanceClaimService(db).decide_claim(
        claim_id, payload, _actor(current_user), request_id
    )
    return success_response(result, request_id)


@router.post("/performance-claims/{claim_id}/handover")
async def process_handover(
    claim_id: str,
    payload: HandoverActionRequest,
    current_user: CurrentUser = Depends(_hug_only),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await PerformanceClaimService(db).handover(
        claim_id, payload, _actor(current_user), request_id
    )
    return success_response(result, request_id)


@router.post("/performance-claims/{claim_id}/subrogation-payment", status_code=201)
async def record_subrogation_payment(
    claim_id: str,
    payload: SubrogationPaymentRequest,
    current_user: CurrentUser = Depends(_hug_only),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await PerformanceClaimService(db).record_subrogation_payment(
        claim_id, payload, _actor(current_user), request_id
    )
    return success_response(result, request_id, status_code=201)


@router.post("/performance-claims/{claim_id}/recovery-claims", status_code=201)
async def register_recovery_claim(
    claim_id: str,
    payload: RecoveryClaimCreateRequest,
    current_user: CurrentUser = Depends(_hug_only),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await PerformanceClaimService(db).register_recovery_claim(
        claim_id, payload, _actor(current_user), request_id
    )
    return success_response(result, request_id, status_code=201)


@router.post("/performance-claims/{claim_id}/transfer")
async def transfer_performance_claim_to_recovery(
    claim_id: str,
    payload: RecoveryTransferRequest,
    current_user: CurrentUser = Depends(_hug_only),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await PerformanceClaimService(db).transfer_to_recovery(
        claim_id, payload, _actor(current_user), request_id
    )
    return success_response(result, request_id)


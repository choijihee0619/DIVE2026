"""사고 접수 엔드포인트.

- POST  /incidents               : 임차인 사고 접수 (계약 연동 시 INCIDENT_REPORTED 전이)
- GET   /incidents               : 임차인=본인 것, HUG=전체 큐 (상태·유형 필터)
- GET   /incidents/{id}          : 상세 + 처리 타임라인 + 다음 행동 안내
- PATCH /incidents/{id}/status   : HUG 상태 전이 (Received→Reviewing→TransferredToRecovery→Closed)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import CurrentUser, get_current_user, get_db, get_request_id, require_roles
from app.core.responses import success_response
from app.schemas.incident import IncidentCreateRequest, IncidentStatusUpdateRequest
from app.services.incident_service import IncidentService

router = APIRouter(prefix="/incidents", tags=["Incident"])


@router.post("", status_code=201)
async def create_incident(
    payload: IncidentCreateRequest,
    current_user: CurrentUser = Depends(require_roles("tenant")),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await IncidentService(db).create(current_user.user_id, payload)
    return success_response(result, request_id, status_code=201)


@router.get("")
async def list_incidents(
    status: str | None = None,
    incident_type: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await IncidentService(db).list(
        current_user.user_id, current_user.role, page, size, status, incident_type
    )
    return success_response(result, request_id)


@router.get("/{incident_id}")
async def get_incident(
    incident_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await IncidentService(db).get(incident_id, current_user.user_id, current_user.role)
    return success_response(result, request_id)


@router.patch("/{incident_id}/status")
async def update_incident_status(
    incident_id: str,
    payload: IncidentStatusUpdateRequest,
    current_user: CurrentUser = Depends(require_roles("hug_admin", "system_admin")),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await IncidentService(db).update_status(incident_id, payload, current_user.role)
    return success_response(result, request_id)

"""전자계약 공동세션 엔드포인트 (UI 시안 2-4 화면 대응).

- POST  /esign/sessions                       : 임차인이 계약으로 세션 생성 (AI 특약 추천 포함)
- POST  /esign/sessions/join                  : 임대인이 세션 코드로 참여
- GET   /esign/sessions/{id}                  : 세션 상태 폴링 (접속·특약·서명·앵커 상태)
- POST  /esign/sessions/{id}/terms            : 특약 수동 제안
- POST  /esign/sessions/{id}/terms/{term_id}  : 특약 agree/withdraw
- POST  /esign/sessions/{id}/sign             : 서명 (양측 완료 시 자동 앵커링)
- POST  /esign/contracts/{contract_id}/verify : 해시 재계산 검증 (tampered_fields로 변조 데모)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import CurrentUser, get_current_user, get_db, get_request_id, require_roles
from app.core.responses import success_response
from app.schemas.esign import (
    EsignJoinRequest,
    EsignSessionCreateRequest,
    EsignVerifyRequest,
    TermActionRequest,
    TermProposeRequest,
)
from app.services.esign_service import EsignService

router = APIRouter(prefix="/esign", tags=["Contract-Esign"])

_party_roles = require_roles("tenant", "landlord")


@router.post("/sessions", status_code=201)
async def create_session(
    payload: EsignSessionCreateRequest,
    current_user: CurrentUser = Depends(require_roles("tenant")),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await EsignService(db).create_session(
        current_user.user_id, payload.contract_id, current_user.display_name
    )
    return success_response(result, request_id, status_code=201)


@router.post("/sessions/join")
async def join_session(
    payload: EsignJoinRequest,
    current_user: CurrentUser = Depends(require_roles("landlord")),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await EsignService(db).join(
        current_user.user_id, current_user.display_name, payload.session_code
    )
    return success_response(result, request_id)


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    current_user: CurrentUser = Depends(_party_roles),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await EsignService(db).get(session_id, current_user.user_id, current_user.role)
    return success_response(result, request_id)


@router.post("/sessions/{session_id}/terms", status_code=201)
async def propose_term(
    session_id: str,
    payload: TermProposeRequest,
    current_user: CurrentUser = Depends(_party_roles),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await EsignService(db).propose_term(
        session_id, current_user.user_id, current_user.role, payload.text
    )
    return success_response(result, request_id, status_code=201)


@router.post("/sessions/{session_id}/terms/{term_id}")
async def act_on_term(
    session_id: str,
    term_id: str,
    payload: TermActionRequest,
    current_user: CurrentUser = Depends(_party_roles),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await EsignService(db).act_on_term(
        session_id, term_id, current_user.user_id, current_user.role, payload.action
    )
    return success_response(result, request_id)


@router.post("/sessions/{session_id}/sign")
async def sign_session(
    session_id: str,
    current_user: CurrentUser = Depends(_party_roles),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await EsignService(db).sign(session_id, current_user.user_id, current_user.role)
    return success_response(result, request_id)


@router.post("/contracts/{contract_id}/verify")
async def verify_contract(
    contract_id: str,
    payload: EsignVerifyRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await EsignService(db).verify(
        contract_id, current_user.user_id, current_user.role, payload.tampered_fields
    )
    return success_response(result, request_id)

from __future__ import annotations

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import CurrentUser, get_db, get_request_id, require_roles
from app.core.responses import success_response
from app.schemas.rag import RagAnswerRequest, RagSearchRequest
from app.services.rag_service import RagService

router = APIRouter(prefix="/rag", tags=["Property-Risk"])


@router.post("/search")
async def rag_search(
    payload: RagSearchRequest,
    current_user: CurrentUser = Depends(require_roles("tenant", "advisor")),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await RagService(db).search(current_user.user_id, payload)
    return success_response(result, request_id)


@router.post("/answer")
async def rag_answer(
    payload: RagAnswerRequest,
    current_user: CurrentUser = Depends(require_roles("tenant", "advisor")),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    result = await RagService(db).answer(current_user.user_id, payload)
    return success_response(result, request_id)

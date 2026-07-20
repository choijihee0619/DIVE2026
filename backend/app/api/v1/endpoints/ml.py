"""ML 추론 엔드포인트.

- POST /ml/recovery/predict : 채권 단건 회수율·소요기간·우선순위 예측 (HUG 관리자)
- POST /ml/counsel/classify : 상담 텍스트 분쟁유형·진행단계 분류 (상담사·HUG)
- GET  /ml/models/info      : 모델 아티팩트·지표 확인

동기 CPU 추론(수 ms~수십 ms)이므로 스레드풀로 위임한다.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from starlette.concurrency import run_in_threadpool

from app.api.deps import CurrentUser, get_request_id, require_roles
from app.core.responses import success_response
from app.schemas.ml import CounselClassifyRequest, RecoveryPredictRequest
from app.services import ml_service

router = APIRouter(prefix="/ml", tags=["ML"])


@router.post("/recovery/predict")
async def predict_recovery(
    payload: RecoveryPredictRequest,
    current_user: CurrentUser = Depends(require_roles("hug_admin", "system_admin")),
    request_id: str = Depends(get_request_id),
):
    result = await run_in_threadpool(
        ml_service.predict_recovery,
        ml_service.RecoveryInput(
            product_name=payload.product_name,
            claim_type=payload.claim_type,
            claimed_amount=payload.claimed_amount,
            incurred_amount=payload.incurred_amount,
            auction_filed_date=payload.auction_filed_date,
            incurred_date=payload.incurred_date,
        ),
    )
    return success_response(result, request_id)


@router.post("/counsel/classify")
async def classify_counsel(
    payload: CounselClassifyRequest,
    current_user: CurrentUser = Depends(require_roles("advisor", "hug_admin", "system_admin")),
    request_id: str = Depends(get_request_id),
):
    result = await run_in_threadpool(ml_service.classify_counsel, payload.text)
    return success_response(result, request_id)


@router.get("/models/info")
async def models_info(
    current_user: CurrentUser = Depends(require_roles("advisor", "hug_admin", "system_admin")),
    request_id: str = Depends(get_request_id),
):
    result = await run_in_threadpool(ml_service.models_info)
    return success_response(result, request_id)

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_request_id
from app.core.responses import success_response
from app.db.mongodb import MongoDB
from app.utils.datetime_utils import now_kst_iso

router = APIRouter(tags=["Admin"])


async def _health_payload() -> tuple[dict, str]:
    mongo_ok = await MongoDB.ping()
    dependencies = {
        "database": "ok" if mongo_ok else "down",
        "vector_store": "ok" if mongo_ok else "down",
        "external_api_gateway": "ok",
        "blockchain_adapter": "ok",
        "ml_inference_service": "degraded",  # 정식 ML 모델 미탑재, rule-based fallback만 운용 중
    }
    overall = "ok" if mongo_ok else "down"
    return {
        "status": overall,
        "checked_at": now_kst_iso(),
        "dependencies": dependencies,
    }, overall


@router.get("/health")
async def health(request_id: str = Depends(get_request_id)):
    payload, overall = await _health_payload()
    return success_response(payload, request_id, status_code=200 if overall == "ok" else 503)

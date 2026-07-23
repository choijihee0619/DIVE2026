"""HUG S1~S7 시연 시나리오 Seed/manifest API."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import CurrentUser, get_db, get_request_id, require_roles
from app.core.exceptions import PermissionDeniedError
from app.core.config import get_settings
from app.core.responses import success_response
from app.schemas.recovery import DemoSeedRequest
from app.services.demo_scenario_service import DemoScenarioService

router = APIRouter(prefix="/hug/demo", tags=["HUG-Demo"])
_hug_only = require_roles("hug_admin", "system_admin")


def _assert_demo_mode() -> None:
    if not get_settings().mock_mode:
        raise PermissionDeniedError("시연 Seed API는 MOCK_MODE=true 환경에서만 사용할 수 있습니다.")


@router.post("/seed")
async def seed_hug_demo_scenarios(
    payload: DemoSeedRequest | None = None,
    current_user: CurrentUser = Depends(_hug_only),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    _assert_demo_mode()
    request = payload or DemoSeedRequest()
    result = await DemoScenarioService(db).seed(
        use_model=request.use_model,
        purge=request.purge,
        include_scale=request.include_scale,
    )
    return success_response(result, request_id)


@router.get("/manifest")
async def get_hug_demo_manifest(
    current_user: CurrentUser = Depends(_hug_only),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    _assert_demo_mode()
    return success_response(await DemoScenarioService(db).manifest(), request_id)


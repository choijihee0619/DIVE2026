"""HUG 채권회수 대시보드 대시보드 엔드포인트 (hug_admin 전용).

- GET /hug/dashboard/summary     : KPI 요약(채권 수·잔고·예상 회수율/소요일 중앙값·등급 분포)
- GET /hug/dashboard/priority    : 회수 우선순위 채권 목록 (스코어 내림차순, 등급/채권구분 필터)
- GET /hug/dashboard/region-risk : 시군구별 실집계 사고율 지도 데이터
- GET /hug/dashboard/issuance    : 발급 시계열 (시도·주택유형 필터)
- GET /hug/dashboard/victims     : 전세사기피해주택 시군구 분포
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from starlette.concurrency import run_in_threadpool

from app.api.deps import CurrentUser, get_db, get_request_id, require_roles
from app.core.responses import success_response
from app.services import hug_dashboard_service as svc

router = APIRouter(prefix="/hug/dashboard", tags=["HUG-Dashboard"])

_hug_only = require_roles("hug_admin", "system_admin")


@router.get("/overview")
async def dashboard_overview(
    current_user: CurrentUser = Depends(_hug_only),
    db: AsyncIOMotorDatabase = Depends(get_db),
    request_id: str = Depends(get_request_id),
):
    """업무대장·합성 참조·공공 집계를 분리한 통합 KPI."""

    return success_response(await svc.overview(db), request_id)


@router.get("/issuance-incident-trend")
async def dashboard_issuance_incident_trend(
    year_from: int | None = Query(default=None, ge=2013, le=2100),
    year_to: int | None = Query(default=None, ge=2013, le=2100),
    current_user: CurrentUser = Depends(_hug_only),
    request_id: str = Depends(get_request_id),
):
    """월별 요청에 대해 실제 공개범위인 연도 단위 fallback을 명시해 반환."""

    result = await run_in_threadpool(svc.issuance_incident_trend, year_from, year_to)
    return success_response(result, request_id)


@router.get("/summary")
async def dashboard_summary(
    current_user: CurrentUser = Depends(_hug_only),
    request_id: str = Depends(get_request_id),
):
    return success_response(await run_in_threadpool(svc.summary), request_id)


@router.get("/priority")
async def dashboard_priority(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    grade: str | None = Query(None, pattern="^(LOW|MED|HIGH)$"),
    claim_type: str | None = None,
    current_user: CurrentUser = Depends(_hug_only),
    request_id: str = Depends(get_request_id),
):
    result = await run_in_threadpool(svc.priority_list, page, size, grade, claim_type)
    return success_response(result, request_id)


@router.get("/region-risk")
async def dashboard_region_risk(
    sido: str | None = None,
    current_user: CurrentUser = Depends(_hug_only),
    request_id: str = Depends(get_request_id),
):
    return success_response(await run_in_threadpool(svc.region_risk_map, sido), request_id)


@router.get("/issuance")
async def dashboard_issuance(
    sido: str | None = None,
    housing_type: str | None = None,
    current_user: CurrentUser = Depends(_hug_only),
    request_id: str = Depends(get_request_id),
):
    result = await run_in_threadpool(svc.issuance_timeseries, sido, housing_type)
    return success_response(result, request_id)


@router.get("/victims")
async def dashboard_victims(
    year: str | None = None,
    current_user: CurrentUser = Depends(_hug_only),
    request_id: str = Depends(get_request_id),
):
    return success_response(await run_in_threadpool(svc.victim_map, year), request_id)

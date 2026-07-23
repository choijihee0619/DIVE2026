"""기존 D-day sweep API의 사전예방 오케스트레이터 호환 wrapper.

실제 항목별 D-90/60/30 bundle, 예측, 예방 케이스, 조치와 3자 알림은
``PreventionService``가 담당한다. 이 이름은 기존 `/contracts/dday-sweep` 호출 호환을 위해 유지한다.
"""

from __future__ import annotations

from datetime import date

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.services.prevention_service import PreventionService


def _stage_for(d_day: int) -> str | None:
    """구 코드와 테스트를 위한 표시값 호환."""
    if d_day > 90:
        return None
    if d_day <= 30:
        return "D-30"
    if d_day <= 60:
        return "D-60"
    return "D-90"


class RepaymentWatchService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._prevention = PreventionService(db)

    async def run_sweep(self, as_of_date: date | None = None) -> dict:
        return await self._prevention.run_sweep(as_of_date=as_of_date)

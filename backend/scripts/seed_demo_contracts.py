#!/usr/bin/env python3
"""데모 편의용 계약 seed 스크립트 (HUG-01 채권관리 대시보드 시연용).

실행: cd backend && .venv/bin/python scripts/seed_demo_contracts.py
- 데모 사용자(tenant01/landlord01)와 기존 properties를 참조해 다양한 상태의 계약을 생성한다.
- _id가 고정되어 있어 여러 번 실행해도 중복 생성되지 않는다(idempotent).
"""

from __future__ import annotations

import asyncio
import sys
from datetime import timedelta, timezone
from pathlib import Path

import certifi

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.utils.datetime_utils import now_kst_iso, new_uuid  # noqa: E402

KST = timezone(timedelta(hours=9))

# (고정 _id, 상태, 보증금, 시작일, 종료일)
DEMO_CONTRACTS = [
    ("demo-ct-0001", "IncidentReported", 320_000_000, "2024-05-01", "2026-04-30"),
    ("demo-ct-0002", "TransferredToHUG", 450_000_000, "2024-03-15", "2026-03-14"),
    ("demo-ct-0003", "RecoveryInProgress", 280_000_000, "2023-11-01", "2025-10-31"),
    ("demo-ct-0004", "AtRisk", 380_000_000, "2024-09-01", "2026-08-31"),
    ("demo-ct-0005", "D90Requested", 250_000_000, "2024-10-20", "2026-10-19"),
    ("demo-ct-0006", "Monitoring", 300_000_000, "2025-02-01", "2027-01-31"),
    ("demo-ct-0007", "ContractFinalized", 420_000_000, "2025-06-01", "2027-05-31"),
]

STATUS_EVENT = {
    "IncidentReported": "IncidentReported",
    "TransferredToHUG": "TransferredToHUG",
    "RecoveryInProgress": "RecoveryStarted",
    "AtRisk": "RiskEscalated",
    "D90Requested": "D90Requested",
    "Monitoring": "MonitoringStarted",
    "ContractFinalized": "ContractFinalized",
}


async def main() -> None:
    settings = get_settings()
    if not settings.mongodb_uri:
        print("ERROR: MONGODB_URI가 설정되지 않았습니다.", file=sys.stderr)
        raise SystemExit(1)

    client = AsyncIOMotorClient(
        settings.mongodb_uri,
        tlsCAFile=certifi.where(),
        serverSelectionTimeoutMS=15000,
    )
    db = client[settings.mongodb_db_name]

    tenant = await db.users.find_one({"email": "tenant01@example.com"})
    landlord = await db.users.find_one({"email": "landlord01@example.com"})
    if not tenant:
        print("ERROR: 데모 사용자가 없습니다. scripts/seed_demo_users.py를 먼저 실행하세요.", file=sys.stderr)
        raise SystemExit(1)

    properties = [doc async for doc in db.properties.find().limit(len(DEMO_CONTRACTS))]
    if not properties:
        print("ERROR: properties 컬렉션이 비어 있어 계약을 연결할 매물이 없습니다.", file=sys.stderr)
        raise SystemExit(1)

    now = now_kst_iso()
    created = 0
    for idx, (contract_id, status, deposit, start, end) in enumerate(DEMO_CONTRACTS):
        if await db.contracts.find_one({"_id": contract_id}):
            print(f"skip (exists): {contract_id} ({status})")
            continue
        prop = properties[idx % len(properties)]
        await db.contracts.insert_one(
            {
                "_id": contract_id,
                "property_id": prop["_id"],
                "tenant_user_id": tenant["_id"],
                "landlord_user_id": landlord["_id"] if landlord else None,
                "landlord_id": None,
                "contract_status": status,
                "deposit": deposit,
                "contract_start_date": start,
                "contract_end_date": end,
                "landlord_type": "INDIVIDUAL",
                "housing_type": "MULTI_HOUSEHOLD",
                "risk_assessment_id": None,
                "created_at": now,
                "updated_at": now,
            }
        )
        await db.timeline_events.insert_one(
            {
                "_id": new_uuid(),
                "contract_id": contract_id,
                "event_type": STATUS_EVENT[status],
                "occurred_at": now,
                "blockchain_status": "NotRequested",
                "blockchain_tx_id": None,
            }
        )
        created += 1
        print(f"created: {contract_id} ({status})")

    print(f"\n{created}건 생성 완료 (총 {len(DEMO_CONTRACTS)}건 정의)")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())

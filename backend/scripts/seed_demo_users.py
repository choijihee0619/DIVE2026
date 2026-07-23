#!/usr/bin/env python3
"""데모 편의용 seed 계정 생성 스크립트.

실행: cd backend && source .venv/bin/activate && python scripts/seed_demo_users.py
이미 존재하는 이메일은 건너뛴다(idempotent).
"""

from __future__ import annotations

import asyncio
import sys
import uuid

import certifi
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.services.demo_scenario_service import _ACCOUNT_SPECS  # noqa: E402

KST = timezone(timedelta(hours=9))

# §20.1 시연 계정 체계는 demo_scenario_service._ACCOUNT_SPECS가 단일 원장이다.
# sysadmin01만 시나리오 밖 운영 편의 계정으로 여기서 추가 관리한다.
DEMO_USERS = [
    {"email": email, "display_name": display_name, "role": role}
    for _key, email, role, display_name, _story, _background in _ACCOUNT_SPECS
] + [
    {"email": "sysadmin01@example.com", "display_name": "시스템 관리자", "role": "system_admin"},
]
DEMO_PASSWORD = "P@ssw0rd!"


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

    for demo in DEMO_USERS:
        existing = await db.users.find_one({"email": demo["email"]})
        if existing:
            # 기존 계정도 비밀번호를 DEMO_PASSWORD로 재설정(idempotent upsert).
            await db.users.update_one(
                {"_id": existing["_id"]},
                {"$set": {
                    "password_hash": hash_password(DEMO_PASSWORD),
                    "role": demo["role"],
                    "display_name": demo["display_name"],
                    "is_active": True,
                }},
            )
            print(f"updated (password reset): {demo['email']} ({demo['role']})")
            continue
        doc = {
            "_id": str(uuid.uuid4()),
            "email": demo["email"],
            "password_hash": hash_password(DEMO_PASSWORD),
            "role": demo["role"],
            "display_name": demo["display_name"],
            "is_active": True,
            "created_at": datetime.now(KST).isoformat(),
            "last_login_at": None,
        }
        await db.users.insert_one(doc)
        print(f"created: {demo['email']} ({demo['role']})")

    print(f"\nDemo password for all accounts: {DEMO_PASSWORD}")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())

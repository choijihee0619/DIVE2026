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

KST = timezone(timedelta(hours=9))

DEMO_USERS = [
    {"email": "tenant01@example.com", "display_name": "임차인 데모", "role": "tenant"},
    {"email": "landlord01@example.com", "display_name": "임대인 데모", "role": "landlord"},
    {"email": "advisor01@example.com", "display_name": "아이엔 상담사 데모", "role": "advisor"},
    {"email": "hugadmin01@example.com", "display_name": "HUG 담당자 데모", "role": "hug_admin"},
    {"email": "sysadmin01@example.com", "display_name": "시스템 관리자 데모", "role": "system_admin"},
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

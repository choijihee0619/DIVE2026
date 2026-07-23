from __future__ import annotations

from httpx import AsyncClient

from app.core.security import hash_password
from app.db.mongodb import MongoDB
from app.utils.datetime_utils import new_uuid, now_kst_iso


async def signup_and_login(client: AsyncClient, email: str, role: str = "tenant", password: str = "P@ssw0rd!") -> str:
    if role in ("tenant", "landlord"):
        signup_resp = await client.post(
            "/api/v1/auth/signup",
            json={"email": email, "password": password, "display_name": "테스트유저", "role": role},
        )
        assert signup_resp.status_code == 201, signup_resp.text
    else:
        # 내부 역할은 공개 signup으로 만들지 않고 테스트 DB에 직접 프로비저닝한다.
        now = now_kst_iso()
        await MongoDB.db.users.insert_one(
            {
                "_id": new_uuid(),
                "email": email,
                "password_hash": hash_password(password),
                "role": role,
                "display_name": "테스트유저",
                "is_active": True,
                "created_at": now,
                "last_login_at": None,
            }
        )

    login_resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login_resp.status_code == 200, login_resp.text
    return login_resp.json()["data"]["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}

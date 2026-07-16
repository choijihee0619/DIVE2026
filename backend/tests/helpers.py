from __future__ import annotations

from httpx import AsyncClient


async def signup_and_login(client: AsyncClient, email: str, role: str = "tenant", password: str = "P@ssw0rd!") -> str:
    signup_resp = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": password, "display_name": "테스트유저", "role": role},
    )
    assert signup_resp.status_code == 201, signup_resp.text

    login_resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login_resp.status_code == 200, login_resp.text
    return login_resp.json()["data"]["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}

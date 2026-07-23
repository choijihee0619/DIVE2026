from __future__ import annotations

from tests.helpers import auth_headers, signup_and_login


async def test_signup_and_login_success(client):
    token = await signup_and_login(client, "tenant01@example.com")
    assert token

    me_resp = await client.get("/api/v1/auth/me", headers=auth_headers(token))
    assert me_resp.status_code == 200
    assert me_resp.json()["data"]["email"] == "tenant01@example.com"


async def test_signup_duplicate_email_conflicts(client):
    await signup_and_login(client, "dup@example.com")
    resp = await client.post(
        "/api/v1/auth/signup",
        json={"email": "dup@example.com", "password": "P@ssw0rd!", "display_name": "테스트", "role": "tenant"},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["error_code"] == "ERROR-007"


async def test_login_wrong_password_returns_401(client):
    await signup_and_login(client, "wrongpw@example.com")
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "wrongpw@example.com", "password": "incorrect-password"}
    )
    assert resp.status_code == 401
    body = resp.json()
    assert body["status"] == "Failed"
    assert body["error"]["error_code"] == "ERROR-004"


async def test_protected_endpoint_without_token_returns_401(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401
    assert resp.json()["error"]["error_code"] == "ERROR-003"


async def test_role_permission_denied(client):
    token = await signup_and_login(client, "tenantrole@example.com", role="tenant")
    # landlord 전용 return-plan 제출을 tenant 토큰으로 시도 -> 403
    resp = await client.post(
        "/api/v1/return-plans",
        json={
            "contract_id": "00000000-0000-0000-0000-000000000000",
            "planned_return_date": "2028-01-01",
            "return_method": "신규 임차인 보증금으로 반환",
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["error_code"] == "ERROR-005"


async def test_public_signup_rejects_privileged_role(client):
    resp = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": "public-admin@example.com",
            "password": "P@ssw0rd!",
            "display_name": "권한상승 시도",
            "role": "hug_admin",
        },
    )
    assert resp.status_code == 422


async def test_existing_token_is_rejected_after_role_change(client, mock_db):
    token = await signup_and_login(client, "role-changed@example.com", role="hug_admin")
    await mock_db.users.update_one(
        {"email": "role-changed@example.com"}, {"$set": {"role": "tenant"}}
    )

    response = await client.get(
        "/api/v1/hug/recovery/summary", headers=auth_headers(token)
    )
    assert response.status_code == 401, response.text
    assert response.json()["error"]["error_code"] == "ERROR-004"

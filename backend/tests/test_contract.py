from __future__ import annotations

from tests.helpers import auth_headers, signup_and_login


async def _create_property(client, token: str) -> str:
    resp = await client.post(
        "/api/v1/properties",
        json={"address": {"road_address": "서울특별시 강남구 테헤란로 000"}, "housing_type": "MULTI_HOUSEHOLD"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["property_id"]


async def test_create_and_get_contract(client):
    token = await signup_and_login(client, "tenant_contract@example.com")
    property_id = await _create_property(client, token)

    create_resp = await client.post(
        "/api/v1/contracts",
        json={
            "property_id": property_id,
            "deposit": 400000000,
            "contract_start_date": "2026-08-01",
            "contract_end_date": "2028-07-31",
            "landlord_type": "INDIVIDUAL",
            "housing_type": "MULTI_HOUSEHOLD",
        },
        headers=auth_headers(token),
    )
    assert create_resp.status_code == 201, create_resp.text
    contract_id = create_resp.json()["data"]["contract_id"]
    assert create_resp.json()["data"]["contract_status"] == "Draft"

    get_resp = await client.get(f"/api/v1/contracts/{contract_id}", headers=auth_headers(token))
    assert get_resp.status_code == 200
    assert get_resp.json()["data"]["contract_id"] == contract_id

    list_resp = await client.get("/api/v1/contracts", headers=auth_headers(token))
    assert list_resp.status_code == 200
    assert list_resp.json()["data"]["pagination"]["total_elements"] == 1


async def test_get_nonexistent_contract_returns_404(client):
    token = await signup_and_login(client, "tenant_404@example.com")
    resp = await client.get(
        "/api/v1/contracts/00000000-0000-0000-0000-000000000000", headers=auth_headers(token)
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["error_code"] == "ERROR-006"


async def test_duplicate_contract_conflicts(client):
    token = await signup_and_login(client, "tenant_dup@example.com")
    property_id = await _create_property(client, token)
    payload = {
        "property_id": property_id,
        "deposit": 400000000,
        "contract_start_date": "2026-08-01",
        "contract_end_date": "2028-07-31",
        "landlord_type": "INDIVIDUAL",
        "housing_type": "MULTI_HOUSEHOLD",
    }
    first = await client.post("/api/v1/contracts", json=payload, headers=auth_headers(token))
    assert first.status_code == 201
    second = await client.post("/api/v1/contracts", json=payload, headers=auth_headers(token))
    assert second.status_code == 409

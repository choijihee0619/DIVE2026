from __future__ import annotations

from tests.helpers import auth_headers, signup_and_login


async def _create_property(client, token: str) -> str:
    resp = await client.post(
        "/api/v1/properties",
        json={"address": {"road_address": "서울특별시 마포구 월드컵로 120"}, "housing_type": "MULTI_HOUSEHOLD"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["data"]["property_id"]


async def test_risk_diagnose_without_registry_data_is_not_marked_low(client):
    """등기부/공시가격 데이터가 없을 때 '위험 낮음(LOW)'으로 단정하지 않아야 한다(과제 지시사항 4절 핵심 원칙)."""
    token = await signup_and_login(client, "tenant_risk@example.com")
    property_id = await _create_property(client, token)

    resp = await client.post(
        "/api/v1/risk/diagnose",
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
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    assert data["assessment_mode"] == "rule_based_fallback"
    assert data["risk_grade"] in ("MEDIUM", "HIGH")  # 데이터 부족 상태에서 LOW 절대 불가
    assert data["risk_grade"] != "LOW"
    assert "registry" in data["missing_fields"]
    assert data["source_status"]["registry"] == "missing"
    assert data["data_completeness"] < 0.5
    assert any(f["code"] == "REGISTRY_DATA_MISSING" for f in data["risk_factors"])
    assert "등기사항전부증명서" in data["required_documents"]


async def test_get_risk_result_by_case_id(client):
    token = await signup_and_login(client, "tenant_risk2@example.com")
    property_id = await _create_property(client, token)

    diagnose_resp = await client.post(
        "/api/v1/risk/diagnose",
        json={
            "property_id": property_id,
            "deposit": 300000000,
            "contract_start_date": "2026-08-01",
            "contract_end_date": "2028-07-31",
            "landlord_type": "INDIVIDUAL",
            "housing_type": "APARTMENT",
        },
        headers=auth_headers(token),
    )
    case_id = diagnose_resp.json()["data"]["case_id"]

    get_resp = await client.get(f"/api/v1/risk/{case_id}", headers=auth_headers(token))
    assert get_resp.status_code == 200
    assert get_resp.json()["data"]["case_id"] == case_id


async def test_get_risk_result_not_found(client):
    token = await signup_and_login(client, "tenant_risk3@example.com")
    resp = await client.get(
        "/api/v1/risk/00000000-0000-0000-0000-000000000000", headers=auth_headers(token)
    )
    assert resp.status_code == 404

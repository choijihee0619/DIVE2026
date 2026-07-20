from __future__ import annotations

import pytest

from tests.helpers import auth_headers, signup_and_login


@pytest.mark.asyncio
async def test_recovery_predict_requires_hug_role(client):
    tenant = await signup_and_login(client, "tenant_ml@example.com", role="tenant")
    resp = await client.post(
        "/api/v1/ml/recovery/predict",
        json={
            "product_name": "전세보증금반환보증",
            "claim_type": "구상채권",
            "claimed_amount": 290000000,
            "incurred_amount": 5000000,
            "auction_filed_date": "2024-03-02",
            "incurred_date": "2024-05-01",
        },
        headers=auth_headers(tenant),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_recovery_predict_success(client):
    token = await signup_and_login(client, "hug_ml@example.com", role="hug_admin")
    resp = await client.post(
        "/api/v1/ml/recovery/predict",
        json={
            "product_name": "전세보증금반환보증",
            "claim_type": "구상채권",
            "claimed_amount": 290000000,
            "incurred_amount": 5000000,
            "auction_filed_date": "2024-03-02",
            "incurred_date": "2024-05-01",
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert 0 <= data["pred_recovery_ratio"] <= 1
    assert data["pred_recovery_grade"] in ("LOW", "MED", "HIGH")
    assert data["pred_days_to_dividend"] >= 0
    assert len(data["top_factors"]) == 3
    assert "합성데이터" in data["basis"]


@pytest.mark.asyncio
async def test_recovery_predict_rejects_unknown_product(client):
    token = await signup_and_login(client, "hug_ml2@example.com", role="hug_admin")
    resp = await client.post(
        "/api/v1/ml/recovery/predict",
        json={
            "product_name": "없는상품",
            "claim_type": "구상채권",
            "claimed_amount": 1,
            "incurred_amount": 1,
            "auction_filed_date": "2024-03-02",
            "incurred_date": "2024-05-01",
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_counsel_classify(client):
    token = await signup_and_login(client, "advisor_ml@example.com", role="advisor")
    resp = await client.post(
        "/api/v1/ml/counsel/classify",
        json={"text": "계약이 만료됐는데 임대인이 보증금을 돌려주지 않아 내용증명을 보냈습니다."},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["dispute_type"]["label"]
    assert len(data["dispute_type"]["top3"]) == 3
    assert data["consultation_stage"]["label"]


@pytest.mark.asyncio
async def test_hug_dashboard_summary_and_priority(client):
    token = await signup_and_login(client, "hug_dash@example.com", role="hug_admin")

    resp = await client.get("/api/v1/hug/dashboard/summary", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["portfolio_count"] > 0
    assert set(data["grade_counts"]) <= {"LOW", "MED", "HIGH"}

    resp = await client.get(
        "/api/v1/hug/dashboard/priority?size=5&grade=HIGH", headers=auth_headers(token)
    )
    assert resp.status_code == 200, resp.text
    items = resp.json()["data"]["items"]
    assert len(items) == 5
    assert all(i["pred_recovery_grade"] == "HIGH" for i in items)
    scores = [i["priority_score"] for i in items]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
async def test_hug_dashboard_region_risk_and_forbidden(client):
    token = await signup_and_login(client, "hug_dash2@example.com", role="hug_admin")
    resp = await client.get(
        "/api/v1/hug/dashboard/region-risk?sido=부산", headers=auth_headers(token)
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert all(row["sido"] == "부산" for row in data["sigungu"])
    assert any(row["sigungu"] == "남구" for row in data["sigungu"])

    tenant = await signup_and_login(client, "tenant_dash@example.com", role="tenant")
    resp = await client.get("/api/v1/hug/dashboard/summary", headers=auth_headers(tenant))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_registry_refresh_mock_scenario(client):
    token = await signup_and_login(client, "tenant_reg@example.com", role="tenant")
    resp = await client.post(
        "/api/v1/properties",
        json={"address": {"road_address": "부산 남구 문현금융로 40", "adm_cd": "2629010600"},
              "housing_type": "MULTI_HOUSEHOLD"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201, resp.text
    property_id = resp.json()["data"]["property_id"]

    resp = await client.post(
        f"/api/v1/properties/{property_id}/registry/refresh?scenario=mortgage&deposit=180000000",
        headers=auth_headers(token),
    )
    assert resp.status_code == 201, resp.text
    snap = resp.json()["data"]
    assert snap["source_system"] == "mock"
    assert snap["provider"] == "mock_registry_mortgage"

    resp = await client.get(
        f"/api/v1/properties/{property_id}/registry/latest", headers=auth_headers(token)
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["registry_snapshot_id"] == snap["registry_snapshot_id"]

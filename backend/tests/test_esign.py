from __future__ import annotations

import pytest

from tests.helpers import auth_headers, signup_and_login


async def _setup_contract(client, tenant_token: str) -> str:
    resp = await client.post(
        "/api/v1/properties",
        json={"address": {"road_address": "부산 남구 전자계약로 1"}, "housing_type": "APARTMENT"},
        headers=auth_headers(tenant_token),
    )
    property_id = resp.json()["data"]["property_id"]
    resp = await client.post(
        "/api/v1/contracts",
        json={
            "property_id": property_id,
            "deposit": 180000000,
            "contract_start_date": "2026-08-01",
            "contract_end_date": "2028-07-31",
            "landlord_type": "INDIVIDUAL",
            "housing_type": "APARTMENT",
        },
        headers=auth_headers(tenant_token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["contract_id"]


@pytest.mark.asyncio
async def test_esign_full_flow_and_verify(client):
    tenant = await signup_and_login(client, "tenant_es@example.com", role="tenant")
    landlord = await signup_and_login(client, "landlord_es@example.com", role="landlord")
    contract_id = await _setup_contract(client, tenant)

    # 1. 세션 생성 (AI 특약 추천 포함)
    resp = await client.post(
        "/api/v1/esign/sessions", json={"contract_id": contract_id}, headers=auth_headers(tenant)
    )
    assert resp.status_code == 201, resp.text
    session = resp.json()["data"]
    session_id, code = session["session_id"], session["session_code"]
    assert session["status"] == "TermsAgreement"
    assert len(session["special_terms"]) >= 2  # 기본 추천 특약
    assert all(t["source"] == "ai_recommend" for t in session["special_terms"])

    # 양측 접속 전 서명 시도 → 409
    resp = await client.post(f"/api/v1/esign/sessions/{session_id}/sign", headers=auth_headers(tenant))
    assert resp.status_code == 409

    # 2. 임대인 참여 (세션 코드)
    resp = await client.post(
        "/api/v1/esign/sessions/join", json={"session_code": code}, headers=auth_headers(landlord)
    )
    assert resp.status_code == 200, resp.text
    assert all(p["joined"] for p in resp.json()["data"]["participants"])

    # 미합의 특약 존재 시 서명 → 409
    resp = await client.post(f"/api/v1/esign/sessions/{session_id}/sign", headers=auth_headers(tenant))
    assert resp.status_code == 409

    # 3. 특약 전부 합의 (양측 agree)
    for term in session["special_terms"]:
        for tok in (tenant, landlord):
            resp = await client.post(
                f"/api/v1/esign/sessions/{session_id}/terms/{term['term_id']}",
                json={"action": "agree"},
                headers=auth_headers(tok),
            )
            assert resp.status_code == 200, resp.text
    assert all(t["status"] == "agreed" for t in resp.json()["data"]["special_terms"])

    # 4. 양측 서명 → 자동 앵커링
    resp = await client.post(f"/api/v1/esign/sessions/{session_id}/sign", headers=auth_headers(tenant))
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "Signing"
    resp = await client.post(f"/api/v1/esign/sessions/{session_id}/sign", headers=auth_headers(landlord))
    assert resp.status_code == 200, resp.text
    final = resp.json()["data"]
    assert final["status"] == "Anchored"
    assert final["contract_hash"].startswith("sha256:")
    assert final["tx_hash"].startswith("0x")

    # 계약 상태 전이 확인
    resp = await client.get(f"/api/v1/contracts/{contract_id}", headers=auth_headers(tenant))
    assert resp.json()["data"]["contract_status"] == "ContractFinalized"

    # 5. 검증: 원본 일치
    resp = await client.post(
        f"/api/v1/esign/contracts/{contract_id}/verify", json={}, headers=auth_headers(tenant)
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["match"] is True

    # 5-2. 변조 시나리오: 보증금을 2억으로 조작 → 불일치
    resp = await client.post(
        f"/api/v1/esign/contracts/{contract_id}/verify",
        json={"tampered_fields": {"deposit": 200000000}},
        headers=auth_headers(tenant),
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["match"] is False

    # 6. 제3자 임차인은 세션 접근 불가
    outsider = await signup_and_login(client, "tenant_es2@example.com", role="tenant")
    resp = await client.get(f"/api/v1/esign/sessions/{session_id}", headers=auth_headers(outsider))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_esign_manual_term_and_withdraw(client):
    tenant = await signup_and_login(client, "tenant_es3@example.com", role="tenant")
    landlord = await signup_and_login(client, "landlord_es3@example.com", role="landlord")
    contract_id = await _setup_contract(client, tenant)

    resp = await client.post(
        "/api/v1/esign/sessions", json={"contract_id": contract_id}, headers=auth_headers(tenant)
    )
    session = resp.json()["data"]
    session_id, code = session["session_id"], session["session_code"]
    await client.post("/api/v1/esign/sessions/join", json={"session_code": code}, headers=auth_headers(landlord))

    # 임차인 수동 특약 제안 (제안자는 자동 agree 상태)
    resp = await client.post(
        f"/api/v1/esign/sessions/{session_id}/terms",
        json={"text": "반려동물 1마리 사육을 허용한다."},
        headers=auth_headers(tenant),
    )
    assert resp.status_code == 201
    manual = resp.json()["data"]["special_terms"][-1]
    assert manual["source"] == "tenant"
    assert manual["agreed_by"] == ["tenant"]

    # 임대인이 상대방 특약 철회 시도 → 403
    resp = await client.post(
        f"/api/v1/esign/sessions/{session_id}/terms/{manual['term_id']}",
        json={"action": "withdraw"},
        headers=auth_headers(landlord),
    )
    assert resp.status_code == 403

    # 제안자 본인 철회는 가능
    resp = await client.post(
        f"/api/v1/esign/sessions/{session_id}/terms/{manual['term_id']}",
        json={"action": "withdraw"},
        headers=auth_headers(tenant),
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["special_terms"][-1]["status"] == "withdrawn"

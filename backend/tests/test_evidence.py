from __future__ import annotations

from tests.helpers import auth_headers, signup_and_login
from tests.test_contract import _create_property


async def _create_contract(client, tenant_token: str) -> str:
    property_id = await _create_property(client, tenant_token)
    resp = await client.post(
        "/api/v1/contracts",
        json={
            "property_id": property_id,
            "deposit": 400000000,
            "contract_start_date": "2026-08-01",
            "contract_end_date": "2028-07-31",
            "landlord_type": "INDIVIDUAL",
            "housing_type": "MULTI_HOUSEHOLD",
        },
        headers=auth_headers(tenant_token),
    )
    assert resp.status_code == 201
    return resp.json()["data"]["contract_id"]


async def test_evidence_request_submit_and_verify_flow(client):
    tenant_token = await signup_and_login(client, "tenant_evi@example.com", role="tenant")
    landlord_token = await signup_and_login(client, "landlord_evi@example.com", role="landlord")
    advisor_token = await signup_and_login(client, "advisor_evi@example.com", role="advisor")

    contract_id = await _create_contract(client, tenant_token)

    request_resp = await client.post(
        "/api/v1/evidence-requests",
        json={
            "contract_id": contract_id,
            "reason": "근저당 말소 확인",
            "evidence_type": "REGISTRY_CANCELLATION_PROOF",
        },
        headers=auth_headers(tenant_token),
    )
    assert request_resp.status_code == 201, request_resp.text
    evidence_request_id = request_resp.json()["data"]["evidence_request_id"]

    submit_resp = await client.post(
        f"/api/v1/evidence?evidence_request_id={evidence_request_id}",
        files={"file": ("proof.pdf", b"%PDF-1.4 fake content", "application/pdf")},
        headers=auth_headers(landlord_token),
    )
    assert submit_resp.status_code == 201, submit_resp.text
    evidence_id = submit_resp.json()["data"]["evidence_id"]
    assert submit_resp.json()["data"]["document_hash"].startswith("sha256:")

    verify_resp = await client.get(f"/api/v1/verifications/{evidence_id}", headers=auth_headers(landlord_token))
    assert verify_resp.status_code == 200
    assert verify_resp.json()["data"]["verification_status"] == "Submitted"

    decide_resp = await client.post(
        f"/api/v1/verifications/{evidence_id}/decision",
        json={"decision": "approve", "reviewer_comment": "확인 완료"},
        headers=auth_headers(advisor_token),
    )
    assert decide_resp.status_code == 200
    assert decide_resp.json()["data"]["verification_status"] == "Verified"


async def test_get_evidence_request_not_found(client):
    tenant_token = await signup_and_login(client, "tenant_evi2@example.com")
    resp = await client.get(
        "/api/v1/evidence-requests/00000000-0000-0000-0000-000000000000",
        headers=auth_headers(tenant_token),
    )
    assert resp.status_code == 404

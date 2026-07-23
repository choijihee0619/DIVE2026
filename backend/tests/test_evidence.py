from __future__ import annotations

from datetime import date

from app.db.mongodb import MongoDB
from app.services.prevention_service import PreventionService
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


async def test_evidence_request_submit_and_verify_flow(client, tmp_path, monkeypatch):
    storage_root = tmp_path / "evidence-storage"
    monkeypatch.setattr("app.services.evidence_service.STORAGE_ROOT", storage_root)
    tenant_token = await signup_and_login(client, "tenant_evi@example.com", role="tenant")
    landlord_token = await signup_and_login(client, "landlord_evi@example.com", role="landlord")
    advisor_token = await signup_and_login(client, "advisor_evi@example.com", role="advisor")

    contract_id = await _create_contract(client, tenant_token)
    landlord = await MongoDB.db.users.find_one({"email": "landlord_evi@example.com"})
    await MongoDB.db.contracts.update_one(
        {"_id": contract_id}, {"$set": {"landlord_user_id": landlord["_id"]}}
    )

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
        files={"file": ("../../escape.pdf", b"%PDF-1.4 fake content", "application/pdf")},
        headers=auth_headers(landlord_token),
    )
    assert submit_resp.status_code == 201, submit_resp.text
    evidence_id = submit_resp.json()["data"]["evidence_id"]
    assert submit_resp.json()["data"]["file_name"] == "escape.pdf"
    assert submit_resp.json()["data"]["document_hash"].startswith("sha256:")
    stored_files = list(storage_root.iterdir())
    assert len(stored_files) == 1
    assert stored_files[0].parent == storage_root
    assert stored_files[0].name == f"{evidence_id}.pdf"
    assert not (tmp_path / "escape.pdf").exists()

    verify_resp = await client.get(f"/api/v1/verifications/{evidence_id}", headers=auth_headers(landlord_token))
    assert verify_resp.status_code == 200
    assert verify_resp.json()["data"]["verification_status"] == "Submitted"

    held = await client.post(
        f"/api/v1/verifications/{evidence_id}/decision",
        json={"decision": "hold", "reviewer_comment": "원본 추가 확인 필요"},
        headers=auth_headers(advisor_token),
    )
    assert held.status_code == 200, held.text
    assert held.json()["data"]["verification_status"] == "Reviewing"
    held_contract = await MongoDB.db.contracts.find_one({"_id": contract_id})
    assert held_contract["contract_status"] == "EvidenceSubmitted"

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


async def test_evidence_request_is_not_visible_to_unrelated_tenant(client):
    owner = await signup_and_login(client, "evidence-owner@example.com")
    other = await signup_and_login(client, "evidence-other@example.com")
    contract_id = await _create_contract(client, owner)
    created = await client.post(
        "/api/v1/evidence-requests",
        json={
            "contract_id": contract_id,
            "reason": "소유권 검사",
            "evidence_type": "OWNERSHIP_PROOF",
        },
        headers=auth_headers(owner),
    )
    request_id = created.json()["data"]["evidence_request_id"]

    detail = await client.get(
        f"/api/v1/evidence-requests/{request_id}", headers=auth_headers(other)
    )
    assert detail.status_code == 403
    listing = await client.get("/api/v1/evidence-requests", headers=auth_headers(other))
    assert listing.status_code == 200
    assert listing.json()["data"]["items"] == []


async def test_bundle_verification_only_completes_contract_after_all_required_items(client):
    tenant_token = await signup_and_login(client, "tenant_bundle@example.com", role="tenant")
    landlord_token = await signup_and_login(
        client, "landlord_bundle@example.com", role="landlord"
    )
    advisor_token = await signup_and_login(client, "advisor_bundle@example.com", role="advisor")
    contract_id = await _create_contract(client, tenant_token)
    landlord = await MongoDB.db.users.find_one({"email": "landlord_bundle@example.com"})
    await MongoDB.db.contracts.update_one(
        {"_id": contract_id},
        {
            "$set": {
                "contract_status": "Monitoring",
                "contract_start_date": "2024-10-01",
                "contract_end_date": "2026-10-01",
                "landlord_user_id": landlord["_id"],
            }
        },
    )

    sweep = await PreventionService(MongoDB.db).run_sweep(date(2026, 7, 23), [contract_id])
    assert sweep["bundles_created"] == 1
    bundle = await MongoDB.db.evidence_bundles.find_one({"contract_id": contract_id})
    assert bundle["required_count"] == 3
    contract = await MongoDB.db.contracts.find_one({"_id": contract_id})
    assert contract["contract_status"] == "D90Requested"

    for index, item in enumerate(bundle["items"], start=1):
        submit = await client.post(
            f"/api/v1/evidence?evidence_request_id={item['evidence_request_id']}",
            files={
                "file": (
                    f"bundle-proof-{index}.pdf",
                    f"%PDF-1.4 bundle item {index}".encode(),
                    "application/pdf",
                )
            },
            headers=auth_headers(landlord_token),
        )
        assert submit.status_code == 201, submit.text
        evidence_id = submit.json()["data"]["evidence_id"]
        decision = await client.post(
            f"/api/v1/verifications/{evidence_id}/decision",
            json={"decision": "approve", "reviewer_comment": f"필수 증빙 {index} 확인"},
            headers=auth_headers(advisor_token),
        )
        assert decision.status_code == 200, decision.text

        current_bundle = await MongoDB.db.evidence_bundles.find_one({"_id": bundle["_id"]})
        current_contract = await MongoDB.db.contracts.find_one({"_id": contract_id})
        assert current_bundle["verified_count"] == index
        assert current_bundle["submitted_count"] == index
        assert current_bundle["completion_ratio"] == round(index / 3, 4)
        assert sum(item["is_verified"] for item in current_bundle["items"]) == index
        if index < 3:
            assert current_bundle["status"] == "InReview"
            assert current_contract["contract_status"] == "D90Requested"
        else:
            assert current_bundle["status"] == "Completed"
            assert current_contract["contract_status"] == "Monitoring"

    # bundle 없는 단일 상환능력 증빙은 전체 필수 증빙 완료로 간주하지 않는다.
    general_request = await client.post(
        "/api/v1/evidence-requests",
        json={
            "contract_id": contract_id,
            "reason": "추가 자산 확인",
            "evidence_type": "ASSET_PROOF",
        },
        headers=auth_headers(tenant_token),
    )
    assert general_request.status_code == 201, general_request.text
    general_request_id = general_request.json()["data"]["evidence_request_id"]
    general_submit = await client.post(
        f"/api/v1/evidence?evidence_request_id={general_request_id}",
        files={"file": ("asset.pdf", b"%PDF-1.4 asset", "application/pdf")},
        headers=auth_headers(landlord_token),
    )
    assert general_submit.status_code == 201, general_submit.text
    general_decision = await client.post(
        f"/api/v1/verifications/{general_submit.json()['data']['evidence_id']}/decision",
        json={"decision": "approve", "reviewer_comment": "개별 증빙 확인"},
        headers=auth_headers(advisor_token),
    )
    assert general_decision.status_code == 200, general_decision.text
    contract = await MongoDB.db.contracts.find_one({"_id": contract_id})
    assert contract["contract_status"] == "D90Requested"

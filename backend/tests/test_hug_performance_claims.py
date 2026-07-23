from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.db.mongodb import MongoDB
from app.utils.datetime_utils import KST
from tests.helpers import auth_headers, signup_and_login


def _headers(token: str, request_id: str) -> dict[str, str]:
    return {**auth_headers(token), "Request-ID": request_id}


async def _create_contract_and_incident(
    client,
    tenant_token: str,
    *,
    email_suffix: str,
    incident_type: str = "DEPOSIT_NOT_RETURNED",
    deposit: int = 180_000_000,
) -> tuple[str, str]:
    prop = await client.post(
        "/api/v1/properties",
        json={
            "address": {"road_address": f"서울특별시 중구 시연로 {email_suffix}"},
            "housing_type": "MULTI_HOUSEHOLD",
        },
        headers=auth_headers(tenant_token),
    )
    assert prop.status_code == 201, prop.text
    property_id = prop.json()["data"]["property_id"]
    contract = await client.post(
        "/api/v1/contracts",
        json={
            "property_id": property_id,
            "deposit": deposit,
            "guarantee_amount": deposit,
            "contract_start_date": "2024-07-01",
            "contract_end_date": "2026-06-30",
            "landlord_type": "INDIVIDUAL",
            "housing_type": "MULTI_HOUSEHOLD",
        },
        headers=auth_headers(tenant_token),
    )
    assert contract.status_code == 201, contract.text
    contract_id = contract.json()["data"]["contract_id"]
    # 이행청구 시나리오는 전자계약 완료 이후의 보증계약을 전제로 한다.
    await MongoDB.db.contracts.update_one(
        {"_id": contract_id}, {"$set": {"contract_status": "ContractFinalized"}}
    )
    incident = await client.post(
        "/api/v1/incidents",
        json={
            "incident_type": incident_type,
            "description": "보증계약의 사고요건이 발생하여 보증이행 절차를 요청합니다.",
            "contract_id": contract_id,
            "deposit_amount": deposit,
            "occurred_date": "2026-07-01",
        },
        headers=auth_headers(tenant_token),
    )
    assert incident.status_code == 201, incident.text
    return contract_id, incident.json()["data"]["incident_id"]


async def _request_submit_verify_documents(
    client,
    claim_id: str,
    document_types: list[str],
    tenant_token: str,
    hug_token: str,
    *,
    hash_offset: int = 0,
) -> list[str]:
    response = await client.post(
        f"/api/v1/performance-claims/{claim_id}/documents/request",
        json={
            "documents": [
                {"document_type": doc_type, "reason": f"{doc_type} 필수 확인"}
                for doc_type in document_types
            ]
        },
        headers=_headers(hug_token, f"req-doc-{hash_offset}"),
    )
    assert response.status_code == 201, response.text
    ids = [item["document_id"] for item in response.json()["data"]["requested_documents"]]
    for index, document_id in enumerate(ids):
        digit = format((hash_offset + index) % 16, "x")
        submitted = await client.post(
            f"/api/v1/performance-claims/{claim_id}/documents/{document_id}/submit",
            json={
                "file_name": f"proof-{hash_offset}-{index}.pdf",
                "document_hash": digit * 64,
                "object_uri": f"s3://demo/{claim_id}/{document_id}",
            },
            headers=_headers(tenant_token, f"submit-{hash_offset}-{index}"),
        )
        assert submitted.status_code == 200, submitted.text
        verified = await client.post(
            f"/api/v1/performance-claims/{claim_id}/documents/{document_id}/decision",
            json={"decision": "VERIFY", "reason": "원본 대조 및 형식 확인 완료"},
            headers=_headers(hug_token, f"verify-{hash_offset}-{index}"),
        )
        assert verified.status_code == 200, verified.text
        assert verified.json()["data"]["verification_status"] == "Verified"
    return ids


@pytest.mark.asyncio
async def test_nonreturn_claim_full_guarded_workflow(client, mock_db):
    tenant = await signup_and_login(client, "tenant_claim_full@example.com", role="tenant")
    hug = await signup_and_login(client, "hug_claim_full@example.com", role="hug_admin")
    other = await signup_and_login(client, "tenant_claim_other@example.com", role="tenant")
    contract_id, incident_id = await _create_contract_and_incident(
        client, tenant, email_suffix="101"
    )

    queue = await client.get("/api/v1/hug/incidents", headers=auth_headers(hug))
    assert queue.status_code == 200, queue.text
    assert any(row["incident_id"] == incident_id for row in queue.json()["data"]["items"])

    source = {
        "data_mode": "DEMO",
        "source_type": "demo_scenario",
        "source_dataset": "hug_workflow_scenarios_v1",
        "as_of_date": "2026-07-23",
        "scenario_id": "S5",
        "is_demo": True,
        "basis": "보증이행 상태전이 시연용 고정 시나리오",
    }
    spoofed = await client.post(
        f"/api/v1/hug/incidents/{incident_id}/claims",
        json={"claim_amount": 180_000_000, "source": source},
        headers=_headers(hug, "claim-create-s5"),
    )
    assert spoofed.status_code == 422, spoofed.text

    other_user = await mock_db.users.find_one({"email": "tenant_claim_other@example.com"})
    invalid_assignee = await client.post(
        f"/api/v1/hug/incidents/{incident_id}/claims",
        json={"claim_amount": 180_000_000, "assignee_user_id": other_user["_id"]},
        headers=_headers(hug, "claim-invalid-assignee"),
    )
    assert invalid_assignee.status_code == 422, invalid_assignee.text

    created = await client.post(
        f"/api/v1/hug/incidents/{incident_id}/claims",
        json={"claim_amount": 180_000_000},
        headers=_headers(hug, "claim-create-s5"),
    )
    assert created.status_code == 201, created.text
    claim = created.json()["data"]
    claim_id = claim["performance_claim_id"]
    assert claim["stage"] == "ClaimReceived"
    assert claim["workflow_type"] == "JEONSE_RETURN_NONRETURN"
    assert claim["sla"]["policy_code"] == "DEMO_INTERNAL_V1"
    assert claim["source"]["data_mode"] == "LIVE"
    assert claim["source"]["scenario_id"] is None

    # 이행청구가 생성된 뒤에는 구 4단계 PATCH로 회수이관을 우회할 수 없다.
    bypass = await client.patch(
        f"/api/v1/incidents/{incident_id}/status",
        json={"status": "TransferredToRecovery", "note": "우회 시도"},
        headers=auth_headers(hug),
    )
    assert bypass.status_code == 409, bypass.text

    # 승인·명도 전에 지급할 수 없다.
    premature_payment = await client.post(
        f"/api/v1/performance-claims/{claim_id}/subrogation-payment",
        json={
            "payment_reference": "PAY-PREMATURE",
            "paid_amount": 10_000,
            "paid_at": "2026-07-23",
            "reason": "선행조건 우회 시도",
        },
        headers=auth_headers(hug),
    )
    assert premature_payment.status_code == 409

    await _request_submit_verify_documents(
        client,
        claim_id,
        ["CONTRACT_DOCUMENT", "CONTRACT_TERMINATION_PROOF", "TENANT_RIGHTS_PROOF"],
        tenant,
        hug,
    )
    reviewed = await client.post(
        f"/api/v1/performance-claims/{claim_id}/review/start",
        json={"note": "필수서류 검증 완료"},
        headers=_headers(hug, "review-start-s5"),
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["data"]["stage"] == "UnderReview"

    decided = await client.post(
        f"/api/v1/performance-claims/{claim_id}/decision",
        json={
            "decision": "APPROVE",
            "approved_amount": 170_000_000,
            "reason": "사고성립·권리·금액 심사 완료",
            "checklist_completed": True,
        },
        headers=_headers(hug, "decision-approve-s5"),
    )
    assert decided.status_code == 200, decided.text
    assert decided.json()["data"]["stage"] == "Approved"
    assert decided.json()["data"]["sla"]["status"] == "COMPLETED"

    moveout_due = (datetime.now(KST) + timedelta(days=7)).isoformat()
    scheduled = await client.post(
        f"/api/v1/performance-claims/{claim_id}/handover",
        json={
            "action": "SCHEDULE",
            "moveout_due_at": moveout_due,
            "reason": "임차인과 명도 예정일 협의 완료",
        },
        headers=_headers(hug, "handover-schedule-s5"),
    )
    assert scheduled.status_code == 200, scheduled.text
    assert scheduled.json()["data"]["stage"] == "HandoverScheduled"

    await _request_submit_verify_documents(
        client, claim_id, ["HANDOVER_PROOF"], tenant, hug, hash_offset=8
    )
    completed = await client.post(
        f"/api/v1/performance-claims/{claim_id}/handover",
        json={
            "action": "COMPLETE",
            "settlement_confirmed": True,
            "reason": "빈집·열쇠 인도와 공과금 정산 확인",
        },
        headers=_headers(hug, "handover-complete-s5"),
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["data"]["stage"] == "HandoverCompleted"

    paid = await client.post(
        f"/api/v1/performance-claims/{claim_id}/subrogation-payment",
        json={
            "payment_reference": "PAY-S5-001",
            "paid_amount": 170_000_000,
            "paid_at": datetime.now(KST).date().isoformat(),
            "reason": "승인금액 계좌 지급 완료",
        },
        headers=_headers(hug, "payment-s5"),
    )
    assert paid.status_code == 201, paid.text
    assert paid.json()["data"]["stage"] == "SubrogationPaid"

    recovery_payload = {
        "claim_type": "RECOURSE_STANDARD",
        "principal": 170_000_000,
        "incurred_amount": 170_000_000,
        "incurred_date": datetime.now(KST).date().isoformat(),
    }
    spoofed_recovery = await client.post(
        f"/api/v1/performance-claims/{claim_id}/recovery-claims",
        json={**recovery_payload, "source": source},
        headers=_headers(hug, "recovery-register-source-spoof"),
    )
    assert spoofed_recovery.status_code == 422, spoofed_recovery.text

    registered = await client.post(
        f"/api/v1/performance-claims/{claim_id}/recovery-claims",
        json=recovery_payload,
        headers=_headers(hug, "recovery-register-s5"),
    )
    assert registered.status_code == 201, registered.text
    recovery = registered.json()["data"]["registered_recovery_claim"]
    assert recovery["stage"] == "Registered"
    assert recovery["balance"] == 170_000_000
    assert recovery["source"]["data_mode"] == "LIVE"
    opening = registered.json()["data"]["opening_ledger_entry"]
    assert opening["entry_type"] == "PRINCIPAL_ACCRUAL"
    assert opening["balance_before"]["total"] == 0
    assert opening["balance_after"]["principal"] == 170_000_000
    stored_opening = await mock_db.recovery_ledger.find_one(
        {"recovery_claim_id": recovery["recovery_claim_id"]}
    )
    assert stored_opening["amount_won"] == recovery["principal"]
    recovery_detail = await client.get(
        f"/api/v1/hug/recovery/claims/{recovery['recovery_claim_id']}",
        headers=auth_headers(hug),
    )
    assert recovery_detail.status_code == 200, recovery_detail.text
    detail_data = recovery_detail.json()["data"]
    assert detail_data["claim"]["balances"]["principal"] == 170_000_000
    assert detail_data["ledger_entries"][0]["entry_type"] == "PRINCIPAL_ACCRUAL"

    invalid_transfer = await client.post(
        f"/api/v1/performance-claims/{claim_id}/transfer",
        json={
            "assignee_user_id": other_user["_id"],
            "next_action": "채무자 자진상환 안내",
            "reason": "잘못된 역할 배정 차단 검증",
        },
        headers=_headers(hug, "transfer-invalid-assignee"),
    )
    assert invalid_transfer.status_code == 422, invalid_transfer.text

    hug_user = await mock_db.users.find_one({"email": "hug_claim_full@example.com"})
    transferred = await client.post(
        f"/api/v1/performance-claims/{claim_id}/transfer",
        json={
            "assignee_user_id": hug_user["_id"],
            "next_action": "채무자 자진상환 안내 및 재산조사",
            "reason": "구상채권 원장 등록 완료",
        },
        headers=_headers(hug, "transfer-s5"),
    )
    assert transferred.status_code == 200, transferred.text
    assert transferred.json()["data"]["stage"] == "TransferredToRecovery"

    incident_doc = await mock_db.incidents.find_one({"_id": incident_id})
    contract_doc = await mock_db.contracts.find_one({"_id": contract_id})
    assert incident_doc["status"] == "TransferredToRecovery"
    assert incident_doc["current_stage"] == "TransferredToRecovery"
    assert contract_doc["contract_status"] == "RecoveryInProgress"

    events = await client.get(
        f"/api/v1/performance-claims/{claim_id}/events", headers=auth_headers(hug)
    )
    assert events.status_code == 200
    event_items = events.json()["data"]["items"]
    actions = {item["action"] for item in event_items}
    assert {
        "CLAIM_RECEIVED",
        "DOCUMENTS_REQUESTED",
        "REVIEW_STARTED",
        "CLAIM_APPROVE",
        "HANDOVER_COMPLETED",
        "SUBROGATION_PAYMENT_RECORDED",
        "RECOVERY_CLAIM_REGISTERED",
        "TRANSFERRED_TO_RECOVERY",
    } <= actions
    assert any(item["request_id"] == "claim-create-s5" for item in event_items)
    assert all(item["actor_user_id"] and item["actor_role"] for item in event_items)
    assert all(item["source"]["data_mode"] == "LIVE" for item in event_items)

    own = await client.get(
        f"/api/v1/performance-claims/{claim_id}", headers=auth_headers(tenant)
    )
    forbidden = await client.get(
        f"/api/v1/performance-claims/{claim_id}", headers=auth_headers(other)
    )
    assert own.status_code == 200
    assert forbidden.status_code == 403


@pytest.mark.asyncio
async def test_auction_branch_sla_hold_and_cost_claim_guards(client, mock_db):
    tenant = await signup_and_login(client, "tenant_claim_auction@example.com", role="tenant")
    hug = await signup_and_login(client, "hug_claim_auction@example.com", role="hug_admin")
    _, incident_id = await _create_contract_and_incident(
        client,
        tenant,
        email_suffix="202",
        incident_type="AUCTION_STARTED",
        deposit=120_000_000,
    )
    created = await client.post(
        f"/api/v1/hug/incidents/{incident_id}/claims",
        json={"claim_amount": 120_000_000},
        headers=auth_headers(hug),
    )
    assert created.status_code == 201, created.text
    claim_id = created.json()["data"]["performance_claim_id"]
    assert created.json()["data"]["handover_required"] is False

    await _request_submit_verify_documents(
        client,
        claim_id,
        ["CONTRACT_DOCUMENT", "TENANT_RIGHTS_PROOF", "AUCTION_DISTRIBUTION_PROOF"],
        tenant,
        hug,
        hash_offset=3,
    )
    started = await client.post(
        f"/api/v1/performance-claims/{claim_id}/review/start",
        json={},
        headers=auth_headers(hug),
    )
    assert started.status_code == 200, started.text
    held = await client.post(
        f"/api/v1/performance-claims/{claim_id}/decision",
        json={"decision": "ON_HOLD", "reason": "배당표 정정 결과 확인 대기"},
        headers=auth_headers(hug),
    )
    assert held.status_code == 200, held.text
    assert held.json()["data"]["stage"] == "OnHold"
    assert held.json()["data"]["sla"]["status"] == "PAUSED"

    resumed = await client.post(
        f"/api/v1/performance-claims/{claim_id}/review/start",
        json={"note": "배당표 정정 확인 완료"},
        headers=auth_headers(hug),
    )
    assert resumed.status_code == 200, resumed.text
    approved = await client.post(
        f"/api/v1/performance-claims/{claim_id}/decision",
        json={
            "decision": "APPROVE",
            "approved_amount": 100_000_000,
            "reason": "경매 배당 후 미수령 보증금 확정",
            "checklist_completed": True,
        },
        headers=auth_headers(hug),
    )
    assert approved.status_code == 200, approved.text

    handover = await client.post(
        f"/api/v1/performance-claims/{claim_id}/handover",
        json={
            "action": "SCHEDULE",
            "moveout_due_at": (datetime.now(KST) + timedelta(days=5)).isoformat(),
            "reason": "경매 workflow 명도 우회 검증",
        },
        headers=auth_headers(hug),
    )
    assert handover.status_code == 409

    paid = await client.post(
        f"/api/v1/performance-claims/{claim_id}/subrogation-payment",
        json={
            "payment_reference": "PAY-AUCTION-001",
            "paid_amount": 100_000_000,
            "paid_at": datetime.now(KST).date().isoformat(),
            "reason": "경매 배당 부족액 지급",
        },
        headers=auth_headers(hug),
    )
    assert paid.status_code == 201, paid.text

    premature_cost = await client.post(
        f"/api/v1/performance-claims/{claim_id}/recovery-claims",
        json={
            "claim_type": "LITIGATION_ADVANCE_COST",
            "principal": 300_000,
            "incurred_amount": 300_000,
            "incurred_date": datetime.now(KST).date().isoformat(),
        },
        headers=auth_headers(hug),
    )
    assert premature_cost.status_code == 409

    primary = await client.post(
        f"/api/v1/performance-claims/{claim_id}/recovery-claims",
        json={
            "claim_type": "RECOURSE_NEW_PRODUCT",
            "principal": 100_000_000,
            "incurred_amount": 100_000_000,
            "incurred_date": datetime.now(KST).date().isoformat(),
        },
        headers=auth_headers(hug),
    )
    assert primary.status_code == 201, primary.text

    duplicate_primary = await client.post(
        f"/api/v1/performance-claims/{claim_id}/recovery-claims",
        json={
            "claim_type": "RECOURSE_STANDARD",
            "principal": 100_000_000,
            "incurred_amount": 100_000_000,
            "incurred_date": datetime.now(KST).date().isoformat(),
        },
        headers=auth_headers(hug),
    )
    assert duplicate_primary.status_code == 409

    await _request_submit_verify_documents(
        client, claim_id, ["LEGAL_COST_PROOF"], tenant, hug, hash_offset=12
    )
    cost = await client.post(
        f"/api/v1/performance-claims/{claim_id}/recovery-claims",
        json={
            "claim_type": "LITIGATION_ADVANCE_COST",
            "principal": 300_000,
            "incurred_amount": 300_000,
            "incurred_date": datetime.now(KST).date().isoformat(),
        },
        headers=auth_headers(hug),
    )
    assert cost.status_code == 201, cost.text
    cost_data = cost.json()["data"]
    assert cost_data["registered_recovery_claim"]["balance"] == 300_000
    assert cost_data["registered_recovery_claim"]["balances"] == {
        "principal": 0,
        "legal_cost": 300_000,
        "delay_damage": 0,
        "enforcement_cost": 0,
        "total": 300_000,
    }
    assert cost_data["opening_ledger_entry"]["entry_type"] == "LEGAL_COST_ACCRUAL"
    assert cost_data["opening_ledger_entry"]["allocations"] == {"legal_cost": 300_000}
    stored_cost = await mock_db.recovery_claims.find_one(
        {"_id": cost_data["registered_recovery_claim"]["recovery_claim_id"]}
    )
    assert stored_cost["principal_balance"] == 0
    assert stored_cost["legal_cost_balance"] == 300_000
    recovery_summary = await client.get(
        "/api/v1/hug/recovery/summary", headers=auth_headers(hug)
    )
    assert recovery_summary.status_code == 200, recovery_summary.text
    summary_data = recovery_summary.json()["data"]
    assert summary_data["principal_balance_won"] == 100_000_000
    assert summary_data["subrogation_principal_balance_won"] == 100_000_000
    assert summary_data["total_balance_won"] == 100_300_000

    duplicate = await client.post(
        f"/api/v1/performance-claims/{claim_id}/recovery-claims",
        json={
            "claim_type": "LITIGATION_ADVANCE_COST",
            "principal": 300_000,
            "incurred_amount": 300_000,
            "incurred_date": datetime.now(KST).date().isoformat(),
        },
        headers=auth_headers(hug),
    )
    assert duplicate.status_code == 409

    filtered = await client.get(
        "/api/v1/hug/incidents?stage=RecoveryClaimRegistered&sla_status=COMPLETED",
        headers=auth_headers(hug),
    )
    assert filtered.status_code == 200, filtered.text
    assert any(
        row["performance_claim_id"] == claim_id for row in filtered.json()["data"]["items"]
    )


@pytest.mark.asyncio
async def test_rejected_claim_closes_incident_and_returns_contract_to_reportable_state(
    client, mock_db
):
    tenant = await signup_and_login(client, "tenant_claim_rejected@example.com", role="tenant")
    hug = await signup_and_login(client, "hug_claim_rejected@example.com", role="hug_admin")
    contract_id, incident_id = await _create_contract_and_incident(
        client, tenant, email_suffix="303"
    )
    created = await client.post(
        f"/api/v1/hug/incidents/{incident_id}/claims",
        json={"claim_amount": 180_000_000},
        headers=auth_headers(hug),
    )
    assert created.status_code == 201, created.text
    claim_id = created.json()["data"]["performance_claim_id"]

    await _request_submit_verify_documents(
        client,
        claim_id,
        ["CONTRACT_DOCUMENT", "CONTRACT_TERMINATION_PROOF", "TENANT_RIGHTS_PROOF"],
        tenant,
        hug,
        hash_offset=5,
    )
    review = await client.post(
        f"/api/v1/performance-claims/{claim_id}/review/start",
        json={},
        headers=auth_headers(hug),
    )
    assert review.status_code == 200, review.text
    rejected = await client.post(
        f"/api/v1/performance-claims/{claim_id}/decision",
        json={
            "decision": "REJECT",
            "reason": "보증사고 성립요건 미충족 확인",
            "checklist_completed": True,
        },
        headers=auth_headers(hug),
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["data"]["stage"] == "Rejected"

    incident = await mock_db.incidents.find_one({"_id": incident_id})
    contract = await mock_db.contracts.find_one({"_id": contract_id})
    assert incident["status"] == "Closed"
    assert contract["contract_status"] == "ContractFinalized"

    reopened = await client.post(
        "/api/v1/incidents",
        json={
            "incident_type": "DEPOSIT_NOT_RETURNED",
            "description": "추가 자료 확보 후 보증사고 요건을 보완하여 다시 신고합니다.",
            "contract_id": contract_id,
            "deposit_amount": 180_000_000,
        },
        headers=auth_headers(tenant),
    )
    assert reopened.status_code == 201, reopened.text

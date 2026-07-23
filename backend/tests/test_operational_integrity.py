from __future__ import annotations

import asyncio

import pytest
from pymongo.errors import DuplicateKeyError

from app.db.indexes import ensure_indexes
from app.services.demo_scenario_service import DemoScenarioService
from app.services.hug_dashboard_service import overview
from app.services.hug_contract_service import HugContractService
from app.services.prevention_service import PreventionService
from app.services.recovery_service import RecoveryService
from tests.helpers import auth_headers, signup_and_login


INCIDENT_PAYLOAD = {
    "incident_type": "DEPOSIT_NOT_RETURNED",
    "description": "계약 종료 후 보증금이 반환되지 않아 보증사고를 신고합니다.",
    "deposit_amount": 180_000_000,
}


async def _tenant_and_user(client, mock_db, email: str) -> tuple[str, dict]:
    token = await signup_and_login(client, email, role="tenant")
    user = await mock_db.users.find_one({"email": email})
    assert user
    return token, user


async def _insert_contract(mock_db, contract_id: str, tenant_user_id: str, status: str) -> None:
    await mock_db.contracts.insert_one(
        {
            "_id": contract_id,
            "tenant_user_id": tenant_user_id,
            "contract_status": status,
            "created_at": "2026-07-01T09:00:00+09:00",
            "updated_at": "2026-07-01T09:00:00+09:00",
        }
    )


@pytest.mark.asyncio
async def test_dashboard_selects_live_population_and_excludes_demo_documents(client, mock_db):
    await DemoScenarioService(mock_db).seed(use_model=False)

    # source 메타데이터가 없어도 demo-* 식별자는 시연 자료로 분류되어야 한다.
    await mock_db.contracts.insert_one(
        {
            "_id": "demo-id-only-contract",
            "contract_status": "Monitoring",
            "created_at": "2026-07-01T09:00:00+09:00",
        }
    )
    await mock_db.contracts.insert_one(
        {
            "_id": "live-contract",
            "contract_status": "Monitoring",
            "created_at": "2026-07-22T09:00:00+09:00",
        }
    )
    await mock_db.prevention_cases.insert_one(
        {
            "_id": "live-prevention",
            "contract_id": "live-contract",
            "status": "Overdue",
            "created_at": "2026-07-22T09:00:00+09:00",
        }
    )
    await mock_db.incidents.insert_one(
        {
            "_id": "live-incident",
            "contract_id": "live-contract",
            "status": "Received",
            "created_at": "2026-07-22T09:00:00+09:00",
        }
    )
    await mock_db.performance_claims.insert_one(
        {
            "_id": "live-performance",
            "contract_id": "live-contract",
            "stage": "UnderReview",
            "created_at": "2026-07-22T09:00:00+09:00",
        }
    )
    await mock_db.recovery_claims.insert_one(
        {
            "_id": "live-recovery",
            "contract_id": "live-contract",
            "claim_type": "RECOURSE_STANDARD",
            "recovery_stage": "Collection",
            "balances": {
                "principal": 100_000_000,
                "legal_cost": 0,
                "delay_damage": 0,
                "enforcement_cost": 0,
                "total": 100_000_000,
            },
            "latest_prediction": {
                "pred_recovery_ratio": 0.8,
                "pred_recovery_grade": "HIGH",
            },
            "created_at": "2026-07-22T09:00:00+09:00",
        }
    )

    result = await overview(mock_db)
    operational = result["operational_register"]
    assert operational["selected_data_mode"] == "LIVE"
    assert operational["guarantee_contract_count"] == 1
    assert operational["high_risk_action_needed_contract_count"] == 1
    assert operational["performance_claim_in_progress_count"] == 1
    assert operational["managed_claim_count"] == 1
    assert operational["total_balance_won"] == 100_000_000
    assert operational["pipeline_counts"]["accident_notified"] == 1
    assert operational["selected_document_count"] == 5
    assert operational["excluded_document_count"] == operational["data_mode_breakdown"]["DEMO"]
    assert operational["data_mode_breakdown_by_collection"]["contracts"]["DEMO"] == 8
    assert operational["provenance"]["data_mode"] == "LIVE"

    live_recovery = await RecoveryService(mock_db).summary(data_mode="LIVE")
    assert live_recovery["managed_claim_count"] == 1
    assert live_recovery["excluded_claim_count"] == 3
    default_recovery = await RecoveryService(mock_db).summary()
    assert default_recovery["data_mode_filter"] == "LIVE"
    assert default_recovery["managed_claim_count"] == 1
    assert default_recovery["closed_claim_count"] == 0

    hug = await signup_and_login(client, "recovery_mode_summary@example.com", role="hug_admin")
    headers = auth_headers(hug)
    default_summary = await client.get("/api/v1/hug/recovery/summary", headers=headers)
    assert default_summary.status_code == 200, default_summary.text
    assert default_summary.json()["data"]["data_mode_filter"] == "LIVE"
    assert default_summary.json()["data"]["managed_claim_count"] == 1
    demo_summary = await client.get(
        "/api/v1/hug/recovery/summary?data_mode=DEMO", headers=headers
    )
    assert demo_summary.status_code == 200, demo_summary.text
    assert demo_summary.json()["data"]["managed_claim_count"] == 2
    assert demo_summary.json()["data"]["closed_claim_count"] == 1

    live_contracts = await HugContractService(mock_db).list_contracts(page=1, size=100)
    demo_contracts = await HugContractService(mock_db).list_contracts(
        page=1, size=100, data_mode="DEMO"
    )
    assert live_contracts["data_mode_filter"] == "LIVE"
    assert {item["contract_id"] for item in live_contracts["items"]} == {
        "live-contract"
    }
    assert demo_contracts["data_mode_filter"] == "DEMO"
    assert {item["contract_id"] for item in demo_contracts["items"]} == {
        "demo-ct-s1",
        "demo-ct-s2",
        "demo-ct-s3",
        "demo-id-only-contract",
    }

    default_contracts = await client.get("/api/v1/hug/contracts", headers=headers)
    demo_contracts_api = await client.get(
        "/api/v1/hug/contracts?data_mode=DEMO", headers=headers
    )
    assert default_contracts.status_code == 200, default_contracts.text
    assert default_contracts.json()["data"]["data_mode_filter"] == "LIVE"
    assert demo_contracts_api.status_code == 200, demo_contracts_api.text
    assert demo_contracts_api.json()["data"]["data_mode_filter"] == "DEMO"

    live_sweep = await PreventionService(mock_db).run_sweep()
    demo_sweep = await PreventionService(mock_db).run_sweep(
        contract_ids=["demo-id-only-contract"], data_mode="DEMO"
    )
    assert live_sweep["data_mode_filter"] == "LIVE"
    assert live_sweep["checked"] == 1
    assert demo_sweep["data_mode_filter"] == "DEMO"
    assert demo_sweep["checked"] == 1


@pytest.mark.asyncio
async def test_incident_created_from_demo_contract_inherits_demo_provenance(client, mock_db):
    await DemoScenarioService(mock_db).seed(use_model=False)
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "workflow.tenant@example.com", "password": "P@ssw0rd!"},
    )
    assert login.status_code == 200, login.text
    token = login.json()["data"]["access_token"]

    response = await client.post(
        "/api/v1/incidents",
        json={
            **INCIDENT_PAYLOAD,
            "contract_id": "demo-ct-s1",
            "property_id": "demo-prop-s1",
            "deposit_amount": 160_000_000,
        },
        headers=auth_headers(token),
    )
    assert response.status_code == 201, response.text
    assert response.json()["data"]["source"]["data_mode"] == "DEMO"
    stored = await mock_db.incidents.find_one({"_id": response.json()["data"]["incident_id"]})
    assert stored["is_demo"] is True
    assert stored["scenario_id"] == "S1"
    notification = await mock_db.notifications.find_one(
        {"user_id": "demo-user-tenant", "category": "incident_update"},
        sort=[("created_at", -1)],
    )
    assert notification["source"]["data_mode"] == "DEMO"


@pytest.mark.asyncio
async def test_incident_rejects_recovery_and_closed_contract_without_state_regression(
    client, mock_db
):
    token, user = await _tenant_and_user(client, mock_db, "incident_state_guard@example.com")
    for status in ("RecoveryInProgress", "Closed"):
        contract_id = f"contract-{status.lower()}"
        await _insert_contract(mock_db, contract_id, user["_id"], status)
        response = await client.post(
            "/api/v1/incidents",
            json={**INCIDENT_PAYLOAD, "contract_id": contract_id},
            headers=auth_headers(token),
        )
        assert response.status_code == 409, response.text
        contract = await mock_db.contracts.find_one({"_id": contract_id})
        assert contract["contract_status"] == status
        assert await mock_db.incidents.count_documents({"contract_id": contract_id}) == 0


@pytest.mark.asyncio
async def test_incident_allows_only_one_active_workflow_per_contract(client, mock_db):
    token, user = await _tenant_and_user(client, mock_db, "incident_duplicate_guard@example.com")
    contract_id = "contract-active-incident"
    await _insert_contract(mock_db, contract_id, user["_id"], "Monitoring")

    first = await client.post(
        "/api/v1/incidents",
        json={**INCIDENT_PAYLOAD, "contract_id": contract_id},
        headers=auth_headers(token),
    )
    assert first.status_code == 201, first.text

    hug = await signup_and_login(client, "incident_legacy_patch_guard@example.com", role="hug_admin")
    legacy_patch = await client.patch(
        f"/api/v1/incidents/{first.json()['data']['incident_id']}/status",
        json={"status": "Reviewing", "note": "레거시 상태 변경 시도"},
        headers=auth_headers(hug),
    )
    assert legacy_patch.status_code == 409, legacy_patch.text
    stored_incident = await mock_db.incidents.find_one(
        {"_id": first.json()["data"]["incident_id"]}
    )
    assert stored_incident["status"] == "Received"

    # 비정상 외부 갱신으로 계약상태만 되돌아간 경우에도 활성 사고 원장이 중복을 막는다.
    await mock_db.contracts.update_one(
        {"_id": contract_id}, {"$set": {"contract_status": "Monitoring"}}
    )
    duplicate = await client.post(
        "/api/v1/incidents",
        json={**INCIDENT_PAYLOAD, "contract_id": contract_id},
        headers=auth_headers(token),
    )
    assert duplicate.status_code == 409, duplicate.text
    assert await mock_db.incidents.count_documents({"contract_id": contract_id}) == 1

    claim_contract_id = "contract-active-performance"
    await _insert_contract(mock_db, claim_contract_id, user["_id"], "Monitoring")
    await mock_db.performance_claims.insert_one(
        {
            "_id": "active-performance-claim",
            "contract_id": claim_contract_id,
            "stage": "UnderReview",
        }
    )
    active_claim = await client.post(
        "/api/v1/incidents",
        json={**INCIDENT_PAYLOAD, "contract_id": claim_contract_id},
        headers=auth_headers(token),
    )
    assert active_claim.status_code == 409, active_claim.text
    assert await mock_db.incidents.count_documents({"contract_id": claim_contract_id}) == 0


@pytest.mark.asyncio
async def test_linked_incident_uses_contract_property_and_exposure(client, mock_db):
    token, user = await _tenant_and_user(client, mock_db, "incident_contract_truth@example.com")
    contract_id = "contract-authoritative-incident"
    await mock_db.contracts.insert_one(
        {
            "_id": contract_id,
            "tenant_user_id": user["_id"],
            "property_id": "property-authoritative",
            "contract_status": "Monitoring",
            "deposit": 180_000_000,
            "guarantee_amount": 170_000_000,
            "created_at": "2026-07-01T09:00:00+09:00",
            "updated_at": "2026-07-01T09:00:00+09:00",
        }
    )
    mismatched = await client.post(
        "/api/v1/incidents",
        json={
            **INCIDENT_PAYLOAD,
            "contract_id": contract_id,
            "property_id": "property-spoofed",
            "deposit_amount": 180_000_000,
        },
        headers=auth_headers(token),
    )
    assert mismatched.status_code == 422, mismatched.text
    assert await mock_db.incidents.count_documents({"contract_id": contract_id}) == 0

    mismatched_deposit = await client.post(
        "/api/v1/incidents",
        json={
            **INCIDENT_PAYLOAD,
            "contract_id": contract_id,
            "property_id": "property-authoritative",
            "deposit_amount": 170_000_000,
        },
        headers=auth_headers(token),
    )
    assert mismatched_deposit.status_code == 422, mismatched_deposit.text

    accepted = await client.post(
        "/api/v1/incidents",
        json={
            **INCIDENT_PAYLOAD,
            "contract_id": contract_id,
            "property_id": "property-authoritative",
            "deposit_amount": 180_000_000,
        },
        headers=auth_headers(token),
    )
    assert accepted.status_code == 201, accepted.text
    data = accepted.json()["data"]
    assert data["property_id"] == "property-authoritative"
    assert data["deposit_amount"] == 180_000_000
    assert data["source"]["data_mode"] == "LIVE"


@pytest.mark.asyncio
async def test_concurrent_incident_requests_leave_one_active_incident(client, mock_db):
    token, user = await _tenant_and_user(client, mock_db, "incident_race_guard@example.com")
    contract_id = "contract-concurrent-incident"
    await _insert_contract(mock_db, contract_id, user["_id"], "ContractFinalized")
    headers = auth_headers(token)
    payload = {**INCIDENT_PAYLOAD, "contract_id": contract_id}

    first, second = await asyncio.gather(
        client.post("/api/v1/incidents", json=payload, headers=headers),
        client.post("/api/v1/incidents", json=payload, headers=headers),
    )
    assert sorted((first.status_code, second.status_code)) == [201, 409]
    assert await mock_db.incidents.count_documents({"contract_id": contract_id}) == 1
    contract = await mock_db.contracts.find_one({"_id": contract_id})
    assert contract["contract_status"] == "IncidentReported"


@pytest.mark.asyncio
async def test_optional_idempotency_unique_indexes_do_not_treat_missing_keys_as_null(mock_db):
    await ensure_indexes(mock_db)

    await mock_db.notifications.insert_many(
        [
            {"_id": "notification-without-key-1", "user_id": "same-user"},
            {"_id": "notification-without-key-2", "user_id": "same-user"},
        ]
    )
    await mock_db.recovery_events.insert_many(
        [
            {"_id": "event-without-key-1", "recovery_claim_id": "same-claim"},
            {"_id": "event-without-key-2", "recovery_claim_id": "same-claim"},
        ]
    )
    await mock_db.evidence_requests.insert_many(
        [
            {
                "_id": "generic-evidence-request-1",
                "contract_id": "same-contract",
                "bundle_id": None,
                "item_key": None,
            },
            {
                "_id": "generic-evidence-request-2",
                "contract_id": "same-contract",
                "bundle_id": None,
                "item_key": None,
            },
        ]
    )
    await mock_db.accident_predictions.insert_many(
        [
            {
                "_id": "failed-prediction-1",
                "contract_id": "same-contract",
                "feature_fingerprint": None,
            },
            {
                "_id": "failed-prediction-2",
                "contract_id": "same-contract",
                "feature_fingerprint": None,
            },
        ]
    )

    assert await mock_db.notifications.count_documents({"user_id": "same-user"}) == 2
    assert await mock_db.recovery_events.count_documents(
        {"recovery_claim_id": "same-claim"}
    ) == 2
    await mock_db.notifications.insert_one(
        {"_id": "deduped-notification-1", "user_id": "same-user", "dedupe_key": "same-key"}
    )
    with pytest.raises(DuplicateKeyError):
        await mock_db.notifications.insert_one(
            {
                "_id": "deduped-notification-2",
                "user_id": "same-user",
                "dedupe_key": "same-key",
            }
        )
    await mock_db.subrogation_payments.insert_one(
        {
            "_id": "payment-reference-1",
            "performance_claim_id": "performance-1",
            "payment_reference": "BANK-TX-UNIQUE",
        }
    )
    with pytest.raises(DuplicateKeyError):
        await mock_db.subrogation_payments.insert_one(
            {
                "_id": "payment-reference-2",
                "performance_claim_id": "performance-2",
                "payment_reference": "BANK-TX-UNIQUE",
            }
        )


@pytest.mark.asyncio
async def test_critical_unique_index_failure_stops_startup(mock_db):
    await mock_db.users.insert_many(
        [
            {"_id": "duplicate-email-user-1", "email": "duplicate@example.com"},
            {"_id": "duplicate-email-user-2", "email": "duplicate@example.com"},
        ]
    )
    with pytest.raises(DuplicateKeyError):
        await ensure_indexes(mock_db)


@pytest.mark.asyncio
async def test_live_batch_refresh_with_explicit_ids_excludes_demo_contracts(mock_db):
    """LIVE 모드 일괄 예측에 명시 contract_ids를 넘겨도 demo 식별자 계약은
    모집단 분리 조건($and)에 걸려 선택되지 않아야 한다."""
    # source/is_demo 메타데이터가 없는 최악의 demo-* 계약: 남는 방어선은 ID regex뿐이다.
    await mock_db.contracts.insert_one(
        {
            "_id": "demo-id-only-refresh",
            "contract_status": "Monitoring",
            "deposit": 200_000_000,
            "created_at": "2026-07-01T09:00:00+09:00",
        }
    )
    result = await HugContractService(mock_db).refresh_predictions(
        ["demo-id-only-refresh"], "LIVE"
    )
    assert result["requested"] == 0
    assert result["items"] == []
    assert await mock_db.accident_predictions.count_documents(
        {"contract_id": "demo-id-only-refresh"}
    ) == 0


@pytest.mark.asyncio
async def test_live_prevention_sweep_with_explicit_ids_excludes_demo_contracts(mock_db):
    """LIVE 예방 sweep에 demo 계약 ID를 명시해도 bundle·알림이 생성되지 않아야 한다."""
    from datetime import date

    await mock_db.contracts.insert_one(
        {
            "_id": "demo-id-only-sweep",
            "contract_status": "Monitoring",
            "deposit": 200_000_000,
            "contract_end_date": "2026-08-31",
            "created_at": "2026-07-01T09:00:00+09:00",
        }
    )
    summary = await PreventionService(mock_db).run_sweep(
        as_of_date=date(2026, 7, 23),
        contract_ids=["demo-id-only-sweep"],
        data_mode="LIVE",
    )
    assert summary["checked"] == 0
    assert summary["bundles_created"] == 0
    assert await mock_db.evidence_bundles.count_documents(
        {"contract_id": "demo-id-only-sweep"}
    ) == 0

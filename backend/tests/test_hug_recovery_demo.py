from __future__ import annotations

import json

import pytest

from app.services.demo_scenario_service import DemoScenarioService, build_demo_documents
from tests.helpers import auth_headers, signup_and_login


async def _seed(mock_db):
    return await DemoScenarioService(mock_db).seed(use_model=False)


@pytest.mark.asyncio
async def test_demo_seed_is_deterministic_and_idempotent(mock_db):
    documents = build_demo_documents()
    first_docs = json.dumps(documents, ensure_ascii=False, sort_keys=True, default=str)
    second_docs = json.dumps(build_demo_documents(), ensure_ascii=False, sort_keys=True, default=str)
    assert first_docs == second_docs

    evidence_request_ids = {doc["_id"] for doc in documents["evidence_requests"]}
    for bundle in documents["evidence_bundles"]:
        assert bundle["required_count"] == 3
        assert {item["evidence_request_id"] for item in bundle["items"]} <= evidence_request_ids
    assert len(documents["claim_documents"]) == 15
    assert len(documents["subrogation_payments"]) == 3
    assert len(documents["performance_claim_events"]) == 29
    assert {doc["target_role"] for doc in documents["notifications"]} == {
        "tenant", "landlord", "hug_admin"
    }

    first = await _seed(mock_db)
    second = await _seed(mock_db)
    assert first["document_digest_sha256"] == second["document_digest_sha256"]
    assert first["document_ids"] == second["document_ids"]
    assert first["demo_as_of_date"] == "2026-07-23"
    assert first["scenario_ids"] == ["S1", "S2", "S3", "S4", "S5", "S6", "S7"]
    assert first["prediction_source_type"] == "cached_demo_prediction"
    for collection, expected in first["collection_counts"].items():
        assert await mock_db[collection].count_documents({"is_demo": True}) == expected


@pytest.mark.asyncio
async def test_demo_seed_and_manifest_endpoints(client, mock_db):
    token = await signup_and_login(client, "hug_demo_seed@example.com", role="hug_admin")
    response = await client.post(
        "/api/v1/hug/demo/seed",
        json={"use_model": False, "include_scale": False},
        headers=auth_headers(token),
    )
    assert response.status_code == 200, response.text
    manifest = response.json()["data"]
    assert manifest["template_version"] == "hug-workflow-v1.2.0"
    accounts = {account["key"]: account for account in manifest["accounts"]}
    assert accounts["tenant01"]["contract_ids"] == ["demo-ct-s2"]
    assert accounts["tenant02"]["contract_ids"] == ["demo-ct-s4"]
    assert accounts["landlord01"]["contract_ids"] == [
        "demo-ct-s2", "demo-ct-s3", "demo-ct-s4"
    ]
    assert manifest["collection_counts"]["recovery_claims"] == 3
    assert manifest["collection_counts"]["evidence_requests"] == 9
    assert manifest["collection_counts"]["claim_documents"] == 15
    assert manifest["collection_counts"]["performance_claim_events"] == 29

    workflow_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "hugadmin01@example.com", "password": "P@ssw0rd!"},
    )
    assert workflow_login.status_code == 200, workflow_login.text
    workflow_headers = auth_headers(workflow_login.json()["data"]["access_token"])
    claim = await client.get(
        "/api/v1/performance-claims/demo-perf-s4", headers=workflow_headers
    )
    assert claim.status_code == 200, claim.text
    assert claim.json()["data"]["document_summary"] == {
        "total": 3,
        "required": 3,
        "verified_or_waived": 3,
    }
    events = await client.get(
        "/api/v1/performance-claims/demo-perf-s4/events", headers=workflow_headers
    )
    assert events.status_code == 200, events.text
    assert events.json()["data"]["total"] == 3
    paid_claim = await client.get(
        "/api/v1/performance-claims/demo-perf-s5", headers=workflow_headers
    )
    assert paid_claim.status_code == 200, paid_claim.text
    assert len(paid_claim.json()["data"]["subrogation_payments"]) == 1

    response = await client.get("/api/v1/hug/demo/manifest", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    assert response.json()["data"]["document_digest_sha256"] == manifest["document_digest_sha256"]


@pytest.mark.asyncio
async def test_purge_removes_action_created_docs_but_keeps_live_docs_and_accounts(
    client, mock_db
):
    await _seed(mock_db)
    # 시연 중 액션이 만드는 무작위 ID 문서를 흉내낸다: is_demo 상속 또는 demo-* 참조.
    await mock_db.notifications.insert_one(
        {"_id": "rand-noti-1", "user_id": "demo-user-tenant01",
         "contract_id": "demo-ct-s2", "is_demo": True}
    )
    await mock_db.evidences.insert_one(
        {"_id": "rand-ev-1", "evidence_request_id": "demo-er-s2-return-plan"}
    )
    # 라이브 문서는 purge에서 보존돼야 한다.
    await mock_db.contracts.insert_one(
        {"_id": "live-ct-1", "contract_status": "Monitoring", "is_demo": False}
    )

    manifest = await DemoScenarioService(mock_db).seed(use_model=False, purge=True)

    assert manifest["purge_counts"]["contracts"] == 7
    assert await mock_db.notifications.count_documents({"_id": "rand-noti-1"}) == 0
    assert await mock_db.evidences.count_documents({"_id": "rand-ev-1"}) == 0
    assert await mock_db.contracts.count_documents({"_id": "live-ct-1"}) == 1
    # 고정 Seed 문서와 로스터 계정은 재생성·유지된다.
    assert await mock_db.contracts.count_documents({"_id": "demo-ct-s2"}) == 1
    assert await mock_db.users.count_documents({"email": "tenant01@example.com"}) == 1
    # 두 번 실행해도 결과 동일(멱등).
    again = await DemoScenarioService(mock_db).seed(use_model=False, purge=True)
    assert again["document_digest_sha256"] == manifest["document_digest_sha256"]


@pytest.mark.asyncio
async def test_scale_seeding_builds_preincident_scale_and_background_incidents(
    client, mock_db
):
    manifest = await DemoScenarioService(mock_db).seed(
        use_model=False, include_scale=True
    )
    scale = manifest["scale"]
    if scale["status"] == "skipped":
        pytest.skip("RTMS 표본 CSV가 없는 환경")
    assert scale["collection_counts"]["contracts"] == 150
    assert scale["collection_counts"]["incidents"] == 16
    assert scale["collection_counts"]["performance_claims"] == 13
    assert scale["prediction"]["requested"] == scale["collection_counts"]["contracts"] - 16
    # PU 실추론이 대부분 성공해야 규모감 화면이 채워진다(NOT_SCORABLE 소수 허용).
    assert scale["prediction"]["succeeded"] >= scale["prediction"]["requested"] * 0.8

    from app.services.hug_contract_service import HugContractService

    listing = await HugContractService(mock_db).list_contracts(
        page=1, size=200, data_mode="DEMO"
    )
    assert listing["pagination"]["total_elements"] >= 130
    # 시연 계약(S2, 저장 priority 94)이 규모감 표본 위에 있어야 한다.
    assert listing["items"][0]["contract_id"] == "demo-ct-s2"
    # 표본 계약도 PU 예측이 붙는다.
    scored = [
        item
        for item in listing["items"]
        if item["contract_id"].startswith("demo-ct-r") and item.get("prediction")
    ]
    assert len(scored) >= 100
    # 배경 이행 사건은 사전 목록에 나타나지 않는다.
    assert all(
        item["contract_status"] in {
            "ContractFinalized", "Monitoring", "D90Requested",
            "ReturnPlanSubmitted", "AtRisk",
        }
        for item in listing["items"]
    )
    # purge는 스케일 문서까지 제거한다.
    purged = await DemoScenarioService(mock_db).seed(use_model=False, purge=True)
    assert purged["purge_counts"]["contracts"] >= 150


@pytest.mark.asyncio
async def test_seed_endpoint_accepts_purge_flag(client, mock_db):
    token = await signup_and_login(client, "hug_demo_purge@example.com", role="hug_admin")
    response = await client.post(
        "/api/v1/hug/demo/seed",
        json={"use_model": False, "purge": True, "include_scale": False},
        headers=auth_headers(token),
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["purge_counts"] == {}


@pytest.mark.asyncio
async def test_seed_s1_s3_are_consumable_by_preincident_contract_apis(client, mock_db):
    await _seed(mock_db)
    hug = await signup_and_login(client, "hug_demo_preincident@example.com", role="hug_admin")
    headers = auth_headers(hug)
    response = await client.get(
        "/api/v1/hug/contracts?as_of_date=2026-07-23&data_mode=DEMO", headers=headers
    )
    assert response.status_code == 200, response.text
    items = {item["contract_id"]: item for item in response.json()["data"]["items"]}
    assert {"demo-ct-s1", "demo-ct-s2", "demo-ct-s3"} <= set(items)
    assert items["demo-ct-s1"]["prediction"]["accident_probability"] == 0.12
    assert items["demo-ct-s2"]["prevention_case"]["status"] == "Overdue"
    assert items["demo-ct-s2"]["prevention_priority"] == 94.0
    assert items["demo-ct-s2"]["evidence_bundle"]["overdue_count"] == 2
    assert items["demo-ct-s3"]["prevention_case"]["status"] == "Mitigated"

    detail = await client.get(
        "/api/v1/hug/contracts/demo-ct-s2/prevention", headers=headers
    )
    assert detail.status_code == 200, detail.text
    data = detail.json()["data"]
    assert data["case"]["priority_score"] == 94.0
    assert data["case"]["triggers"][1]["code"] == "EVIDENCE_OVERDUE"
    assert data["actions"][0]["action_type"] == "EVIDENCE_REQUEST"
    assert data["evidence_bundles"][0]["required_count"] == 3
    assert await mock_db.evidence_requests.count_documents(
        {"contract_id": "demo-ct-s2"}
    ) == 6


@pytest.mark.asyncio
async def test_recovery_access_list_detail_and_parallel_event(client, mock_db):
    await _seed(mock_db)
    tenant = await signup_and_login(client, "tenant_recovery@example.com", role="tenant")
    denied = await client.get("/api/v1/hug/recovery/summary", headers=auth_headers(tenant))
    assert denied.status_code == 403

    hug = await signup_and_login(client, "hug_recovery@example.com", role="hug_admin")
    live_only = await client.get("/api/v1/hug/recovery/claims", headers=auth_headers(hug))
    assert live_only.status_code == 200
    assert live_only.json()["data"]["items"] == []
    response = await client.get(
        "/api/v1/hug/recovery/claims?data_mode=DEMO", headers=auth_headers(hug)
    )
    assert response.status_code == 200, response.text
    assert {item["recovery_claim_id"] for item in response.json()["data"]["items"]} == {
        "demo-rc-s5", "demo-rc-s6"
    }

    payload = {
        "event_type": "CollectionRouteChanged",
        "status_axis": "collection_route",
        "after": "Litigation",
        "note": "법무 회수 병행",
        "idempotency_key": "event-s5-litigation",
    }
    first = await client.post(
        "/api/v1/hug/recovery/claims/demo-rc-s5/events",
        json=payload,
        headers=auth_headers(hug),
    )
    assert first.status_code == 201, first.text
    assert first.json()["data"]["before"] == "Voluntary"
    replay = await client.post(
        "/api/v1/hug/recovery/claims/demo-rc-s5/events",
        json=payload,
        headers=auth_headers(hug),
    )
    assert replay.status_code == 201
    assert replay.json()["data"]["idempotent_replay"] is True

    detail = await client.get(
        "/api/v1/hug/recovery/claims/demo-rc-s5", headers=auth_headers(hug)
    )
    assert detail.status_code == 200
    assert detail.json()["data"]["claim"]["collection_route"] == "Litigation"

    seeded_detail = await client.get(
        "/api/v1/hug/recovery/claims/demo-rc-s6", headers=auth_headers(hug)
    )
    assert seeded_detail.status_code == 200, seeded_detail.text
    assert seeded_detail.json()["data"]["legal_cases"][0]["case_number"] == "2025차전260723"
    assert seeded_detail.json()["data"]["auction_cases"][0]["case_number"] == "2025타경260723"

    invalid = await client.post(
        "/api/v1/hug/recovery/claims/demo-rc-s5/events",
        json={"event_type": "Bad", "status_axis": "auction_status", "after": "Invented"},
        headers=auth_headers(hug),
    )
    assert invalid.status_code == 422

    missing_key = await client.post(
        "/api/v1/hug/recovery/claims/demo-rc-s5/events",
        json={"event_type": "MemoAdded", "note": "멱등키 누락"},
        headers=auth_headers(hug),
    )
    assert missing_key.status_code == 422
    naive_time = await client.post(
        "/api/v1/hug/recovery/claims/demo-rc-s5/events",
        json={"event_type": "MemoAdded", "note": "timezone 누락",
              "occurred_at": "2026-07-23T12:00:00",
              "idempotency_key": "event-naive-time"},
        headers=auth_headers(hug),
    )
    assert naive_time.status_code == 422


@pytest.mark.asyncio
async def test_legal_and_auction_case_actions_are_guarded_audited_and_idempotent(
    client, mock_db
):
    await _seed(mock_db)
    hug = await signup_and_login(client, "hug_case_actions@example.com", role="hug_admin")
    headers = auth_headers(hug)

    legal_payload = {
        "case_type": "PaymentOrder",
        "court": "서울중앙지방법원",
        "case_number": "2026차전10001",
        "filing_date": "2026-07-23",
        "status": "PaymentOrder",
        "claimed_amount_won": 210_000_000,
        "legal_cost_won": 500_000,
        "note": "지급명령 접수",
        "idempotency_key": "legal-create-s5-1",
    }
    created = await client.post(
        "/api/v1/hug/recovery/claims/demo-rc-s5/legal-cases",
        json=legal_payload,
        headers=headers,
    )
    assert created.status_code == 201, created.text
    legal_case = created.json()["data"]["case"]
    assert legal_case["version"] == 1
    replay = await client.post(
        "/api/v1/hug/recovery/claims/demo-rc-s5/legal-cases",
        json=legal_payload,
        headers=headers,
    )
    assert replay.status_code == 201
    assert replay.json()["data"]["idempotent_replay"] is True

    updated = await client.patch(
        f"/api/v1/hug/recovery/claims/demo-rc-s5/legal-cases/{legal_case['legal_case_id']}",
        json={
            "expected_version": 1,
            "status": "Judgment",
            "judgment": "원고 승",
            "judgment_amount_won": 205_000_000,
            "idempotency_key": "legal-update-s5-judgment",
        },
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["case"]["status"] == "Judgment"

    bypass = await client.post(
        "/api/v1/hug/recovery/claims/demo-rc-s5/events",
        json={"event_type": "Bypass", "status_axis": "legal_status",
              "after": "Enforcement", "idempotency_key": "legal-axis-bypass"},
        headers=headers,
    )
    assert bypass.status_code == 422

    auction_payload = {
        "auction_type": "Auction",
        "case_number": "2026타경10002",
        "filing_date": "2026-07-23",
        "status": "Filed",
        "appraisal_won": 230_000_000,
        "idempotency_key": "auction-create-s5-1",
    }
    auction = await client.post(
        "/api/v1/hug/recovery/claims/demo-rc-s5/auction-cases",
        json=auction_payload,
        headers=headers,
    )
    assert auction.status_code == 201, auction.text
    auction_case = auction.json()["data"]["case"]
    invalid_date = await client.patch(
        f"/api/v1/hug/recovery/claims/demo-rc-s5/auction-cases/{auction_case['auction_case_id']}",
        json={"expected_version": 1, "status": "Sold", "sale_date": "2026-07-01",
              "idempotency_key": "auction-invalid-date"},
        headers=headers,
    )
    assert invalid_date.status_code == 422
    sold = await client.patch(
        f"/api/v1/hug/recovery/claims/demo-rc-s5/auction-cases/{auction_case['auction_case_id']}",
        json={"expected_version": 1, "status": "Sold", "sale_date": "2026-08-01",
              "idempotency_key": "auction-sold-s5"},
        headers=headers,
    )
    assert sold.status_code == 200, sold.text

    detail = await client.get(
        "/api/v1/hug/recovery/claims/demo-rc-s5", headers=headers
    )
    assert detail.status_code == 200
    assert len(detail.json()["data"]["legal_cases"]) == 1
    assert len(detail.json()["data"]["auction_cases"]) == 1
    event_types = {event["event_type"] for event in detail.json()["data"]["events"]}
    assert {"LegalCaseRegistered", "LegalCaseUpdated", "AuctionCaseRegistered",
            "AuctionCaseUpdated"} <= event_types

    closed_write = await client.post(
        "/api/v1/hug/recovery/claims/demo-rc-s7/legal-cases",
        json={**legal_payload, "case_number": "2026차전10003",
              "idempotency_key": "legal-create-closed-s7"},
        headers=headers,
    )
    assert closed_write.status_code == 409


@pytest.mark.asyncio
async def test_recovery_ledger_invariants_and_idempotency(client, mock_db):
    await _seed(mock_db)
    hug = await signup_and_login(client, "hug_ledger@example.com", role="hug_admin")
    headers = auth_headers(hug)

    accrual = {
        "entry_type": "LEGAL_COST_ACCRUAL",
        "amount_won": 1_000_000,
        "note": "지급명령 비용",
        "idempotency_key": "ledger-s5-legal-1",
    }
    first = await client.post(
        "/api/v1/hug/recovery/claims/demo-rc-s5/ledger-entries", json=accrual, headers=headers
    )
    assert first.status_code == 201, first.text
    assert first.json()["data"]["balance_after"]["total"] == 211_000_000
    replay = await client.post(
        "/api/v1/hug/recovery/claims/demo-rc-s5/ledger-entries", json=accrual, headers=headers
    )
    assert replay.status_code == 201
    assert replay.json()["data"]["idempotent_replay"] is True
    claim = await mock_db.recovery_claims.find_one({"_id": "demo-rc-s5"})
    assert claim["balance"] == 211_000_000

    receipt = await client.post(
        "/api/v1/hug/recovery/claims/demo-rc-s5/ledger-entries",
        json={"entry_type": "RECEIPT", "amount_won": 1_000_000,
              "allocations": {"legal_cost": 1_000_000}, "idempotency_key": "ledger-s5-receipt-1"},
        headers=headers,
    )
    assert receipt.status_code == 201, receipt.text
    assert receipt.json()["data"]["balance_after"]["legal_cost"] == 0

    overdraw = await client.post(
        "/api/v1/hug/recovery/claims/demo-rc-s5/ledger-entries",
        json={"entry_type": "RECEIPT", "amount_won": 999_000_000,
              "allocations": {"principal": 999_000_000},
              "idempotency_key": "ledger-s5-overdraw"},
        headers=headers,
    )
    assert overdraw.status_code == 409

    backdated = await client.post(
        "/api/v1/hug/recovery/claims/demo-rc-s5/ledger-entries",
        json={"entry_type": "LEGAL_COST_ACCRUAL", "amount_won": 100,
              "occurred_at": "2026-05-01T09:00:00+09:00",
              "idempotency_key": "ledger-s5-backdated"},
        headers=headers,
    )
    assert backdated.status_code == 422

    keeps_partial = await client.post(
        "/api/v1/hug/recovery/claims/demo-rc-s6/ledger-entries",
        json={"entry_type": "LEGAL_COST_ACCRUAL", "amount_won": 200_000_000,
              "idempotency_key": "ledger-s6-large-cost"},
        headers=headers,
    )
    assert keeps_partial.status_code == 201, keeps_partial.text
    assert keeps_partial.json()["data"]["balance_after"]["total"] > 320_000_000
    assert (await mock_db.recovery_claims.find_one({"_id": "demo-rc-s6"}))[
        "balance_status"
    ] == "PartiallyRecovered"


@pytest.mark.asyncio
async def test_registered_claim_prediction_is_saved_with_snapshot_and_delta(
    client, mock_db, monkeypatch
):
    await _seed(mock_db)

    def fake_predict(_input):
        return {
            "pred_recovery_ratio": 0.7,
            "pred_recovery_grade": "MED",
            "pred_days_to_dividend": 300,
            "expected_recovery_won": 147_000_000,
            "priority_score": 70.0,
            "priority_weights": {"recovery": 0.6, "speed": 0.4},
            "portfolio_size": 28_961,
            "top_factors": [],
            "basis": "합성데이터 기준 시뮬레이션",
        }

    monkeypatch.setattr("app.services.recovery_service.ml_service.predict_recovery", fake_predict)
    hug = await signup_and_login(client, "hug_predict_claim@example.com", role="hug_admin")
    headers = auth_headers(hug)
    response = await client.post(
        "/api/v1/hug/recovery/claims/demo-rc-s5/predict",
        json={"idempotency_key": "predict-s5-001"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    prediction = response.json()["data"]
    assert prediction["recovery_claim_id"] == "demo-rc-s5"
    assert prediction["input_snapshot"]["claim_type"] == "구상채권"
    assert prediction["result"]["expected_recovery_on_current_balance_won"] == 147_000_000
    assert prediction["result"]["priority_basis"] == "REGISTERED_CURRENT_BALANCE_PORTFOLIO_V1"
    assert prediction["result"]["priority_rank"] >= 1
    assert prediction["model_version"]
    assert prediction["provenance"]["source_type"] == "model_poc"
    assert prediction["delta_from_previous"] is not None

    replay = await client.post(
        "/api/v1/hug/recovery/claims/demo-rc-s5/predict",
        json={"idempotency_key": "predict-s5-001"},
        headers=headers,
    )
    assert replay.status_code == 201
    assert replay.json()["data"]["idempotent_replay"] is True
    history = await client.get(
        "/api/v1/hug/recovery/claims/demo-rc-s5/predictions", headers=headers
    )
    assert history.status_code == 200
    assert history.json()["data"]["total"] == 2


@pytest.mark.asyncio
async def test_dynamic_priority_list_reorders_all_active_claims_after_partial_recovery(
    client, mock_db
):
    await _seed(mock_db)
    hug = await signup_and_login(client, "hug_dynamic_priority@example.com", role="hug_admin")
    headers = auth_headers(hug)

    before = await client.get(
        "/api/v1/hug/recovery/claims?data_mode=DEMO&sort_by=priority_score&descending=true",
        headers=headers,
    )
    assert before.status_code == 200, before.text
    before_items = before.json()["data"]["items"]
    assert [item["recovery_claim_id"] for item in before_items[:2]] == [
        "demo-rc-s6", "demo-rc-s5"
    ]
    assert {item["priority_rank"] for item in before_items} == {1, 2}

    receipt = await client.post(
        "/api/v1/hug/recovery/claims/demo-rc-s6/ledger-entries",
        json={
            "entry_type": "RECEIPT",
            "amount_won": 180_000_000,
            "allocations": {"principal": 180_000_000},
            "idempotency_key": "priority-partial-recovery-s6",
        },
        headers=headers,
    )
    assert receipt.status_code == 201, receipt.text

    after = await client.get(
        "/api/v1/hug/recovery/claims?data_mode=DEMO&sort_by=priority_score&descending=true",
        headers=headers,
    )
    assert after.status_code == 200, after.text
    after_items = after.json()["data"]["items"]
    assert [item["recovery_claim_id"] for item in after_items[:2]] == [
        "demo-rc-s5", "demo-rc-s6"
    ]
    assert {item["priority_rank"] for item in after_items} == {1, 2}
    assert all(
        item["priority_basis"] == "REGISTERED_CURRENT_BALANCE_PORTFOLIO_V1"
        for item in after_items
    )


@pytest.mark.asyncio
async def test_recovery_close_requires_zero_balance_and_makes_claim_read_only(client, mock_db):
    await _seed(mock_db)
    primary = await mock_db.recovery_claims.find_one({"_id": "demo-rc-s5"})
    secondary = {
        **primary,
        "_id": "demo-rc-s5-legal-cost",
        "claim_type": "LITIGATION_ADVANCE_COST",
        "principal": 0,
        "balance": 0,
        "balances": {"principal": 0, "legal_cost": 0, "delay_damage": 0,
                     "enforcement_cost": 0, "total": 0},
        "is_closed": False,
        "closure": None,
        "closed_at": None,
        "version": 1,
    }
    await mock_db.recovery_claims.insert_one(secondary)
    hug = await signup_and_login(client, "hug_close_claim@example.com", role="hug_admin")
    headers = auth_headers(hug)
    missing_key = await client.post(
        "/api/v1/hug/recovery/claims/demo-rc-s5/close",
        json={"reason": "FULL_RECOVERY", "confirm": True},
        headers=headers,
    )
    assert missing_key.status_code == 422
    rejected = await client.post(
        "/api/v1/hug/recovery/claims/demo-rc-s5/close",
        json={"reason": "FULL_RECOVERY", "confirm": True,
              "idempotency_key": "close-s5-nonzero"},
        headers=headers,
    )
    assert rejected.status_code == 409

    paid = await client.post(
        "/api/v1/hug/recovery/claims/demo-rc-s5/ledger-entries",
        json={"entry_type": "RECEIPT", "amount_won": 210_000_000,
              "allocations": {"principal": 210_000_000}, "idempotency_key": "payoff-s5"},
        headers=headers,
    )
    assert paid.status_code == 201, paid.text
    closed = await client.post(
        "/api/v1/hug/recovery/claims/demo-rc-s5/close",
        json={"reason": "FULL_RECOVERY", "confirm": True, "idempotency_key": "close-s5"},
        headers=headers,
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["data"]["is_closed"] is True
    assert closed.json()["data"]["parent_sync"]["status"] == "WAITING_FOR_RELATED_CLAIMS"
    assert not (await mock_db.performance_claims.find_one({"_id": "demo-perf-s5"})).get(
        "recovery_closed_at"
    )
    replay = await client.post(
        "/api/v1/hug/recovery/claims/demo-rc-s5/close",
        json={"reason": "FULL_RECOVERY", "confirm": True, "idempotency_key": "close-s5"},
        headers=headers,
    )
    assert replay.status_code == 200
    assert replay.json()["data"]["idempotent_replay"] is True

    final_close = await client.post(
        "/api/v1/hug/recovery/claims/demo-rc-s5-legal-cost/close",
        json={"reason": "FULL_RECOVERY", "confirm": True,
              "idempotency_key": "close-s5-legal-cost"},
        headers=headers,
    )
    assert final_close.status_code == 200, final_close.text
    assert final_close.json()["data"]["parent_sync"]["status"] == "CLOSED"
    performance = await mock_db.performance_claims.find_one({"_id": "demo-perf-s5"})
    incident = await mock_db.incidents.find_one({"_id": "demo-inc-s5"})
    contract = await mock_db.contracts.find_one({"_id": "demo-ct-s5"})
    assert performance["recovery_lifecycle_status"] == "Closed"
    assert performance["recovery_closed_at"]
    assert incident["status"] == "Closed"
    assert contract["contract_status"] == "Closed"

    immutable = await client.post(
        "/api/v1/hug/recovery/claims/demo-rc-s5/ledger-entries",
        json={"entry_type": "LEGAL_COST_ACCRUAL", "amount_won": 1,
              "idempotency_key": "after-close"},
        headers=headers,
    )
    assert immutable.status_code == 409


@pytest.mark.asyncio
async def test_dashboard_overview_separates_populations_and_trend_declares_fallback(
    client, mock_db
):
    await _seed(mock_db)
    hug = await signup_and_login(client, "hug_overview@example.com", role="hug_admin")
    headers = auth_headers(hug)
    response = await client.get("/api/v1/hug/dashboard/overview", headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["operational_register"]["guarantee_contract_count"] == 7
    assert data["operational_register"]["managed_claim_count"] == 2
    assert data["operational_register"]["provenance"]["data_mode"] == "DEMO"
    assert data["reference_portfolio"]["provenance"]["source_type"] == "provided_synthetic"
    assert data["public_aggregate"]["provenance"]["source_type"] == "public_aggregate"
    assert "합산하지" in data["population_policy"]

    trend = await client.get(
        "/api/v1/hug/dashboard/issuance-incident-trend?year_from=2020&year_to=2024",
        headers=headers,
    )
    assert trend.status_code == 200, trend.text
    result = trend.json()["data"]
    assert result["requested_granularity"] == "month"
    assert result["actual_granularity"] == "year"
    assert result["status"] == "AVAILABLE_WITH_GRANULARITY_FALLBACK"
    assert result["series"]
    assert all(row["accident_cnt"] is not None for row in result["series"])
    assert "보간하지" in result["fallback_note"]

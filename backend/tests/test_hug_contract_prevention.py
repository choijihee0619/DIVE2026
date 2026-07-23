from __future__ import annotations

import asyncio
from datetime import date

import pytest

from app.core.exceptions import ModelInferenceFailedError, StateConflictError
from app.db.indexes import ensure_indexes
from app.repositories.prevention_repository import PreventiveActionRepository
from app.schemas.hug_contract import PreventiveActionCreateRequest, PreventiveActionUpdateRequest
from app.services.accident_prediction_service import AccidentPredictionService
from app.services.hug_contract_service import HugContractService
from app.services.notification_service import NotificationService
from app.services.prevention_service import PreventionService
from tests.helpers import auth_headers, signup_and_login


async def _managed_contract(
    client,
    db,
    *,
    suffix: str,
    end_date: str,
    status: str = "Monitoring",
    address: str = "서울특별시 강남구 테헤란로 100",
    deposit: int = 300_000_000,
):
    tenant_token = await signup_and_login(client, f"tenant_{suffix}@example.com", role="tenant")
    landlord_token = await signup_and_login(client, f"landlord_{suffix}@example.com", role="landlord")
    hug_token = await signup_and_login(client, f"hug_{suffix}@example.com", role="hug_admin")
    tenant = await db.users.find_one({"email": f"tenant_{suffix}@example.com"})
    landlord = await db.users.find_one({"email": f"landlord_{suffix}@example.com"})

    response = await client.post(
        "/api/v1/properties",
        json={"address": {"road_address": address}, "housing_type": "APARTMENT"},
        headers=auth_headers(tenant_token),
    )
    assert response.status_code == 201, response.text
    property_id = response.json()["data"]["property_id"]
    response = await client.post(
        "/api/v1/contracts",
        json={
            "property_id": property_id,
            "deposit": deposit,
            "contract_start_date": "2024-10-01",
            "contract_end_date": end_date,
            "landlord_type": "INDIVIDUAL",
            "housing_type": "APARTMENT",
        },
        headers=auth_headers(tenant_token),
    )
    assert response.status_code == 201, response.text
    contract_id = response.json()["data"]["contract_id"]
    await db.contracts.update_one(
        {"_id": contract_id},
        {
            "$set": {
                "contract_status": status,
                "landlord_user_id": landlord["_id"],
                "guarantee_product": "전세보증금반환보증",
                "guarantee_amount": deposit,
            }
        },
    )
    return {
        "contract_id": contract_id,
        "tenant_token": tenant_token,
        "landlord_token": landlord_token,
        "hug_token": hug_token,
        "tenant_id": tenant["_id"],
        "landlord_id": landlord["_id"],
    }


@pytest.mark.asyncio
async def test_accident_prediction_is_self_contained_persisted_and_idempotent(client, mock_db):
    context = await _managed_contract(
        client, mock_db, suffix="prediction", end_date="2026-10-01"
    )
    service = AccidentPredictionService(mock_db)
    first = await service.refresh_contract(context["contract_id"])
    second = await service.refresh_contract(context["contract_id"])

    assert first.prediction_status == "SUCCESS"
    assert first.prediction_id == second.prediction_id
    assert 0 <= first.pu_risk_score <= 1
    assert 0 <= first.risk_percentile <= 1
    assert 0 <= first.accident_probability <= 1
    assert first.calibration_status == "AGGREGATE_PRIOR_ALIGNED_UNVALIDATED"
    assert first.source.source_type == "model_poc"
    assert first.source.input_snapshot["housing_type"] == "아파트"
    assert await mock_db.accident_predictions.count_documents({}) == 1
    assert await mock_db.incidents.count_documents({}) == 0

    response = await client.post(
        "/api/v1/ml/accident/predict",
        json={"contract_id": context["contract_id"]},
        headers=auth_headers(context["hug_token"]),
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["prediction_id"] == first.prediction_id

    response = await client.post(
        "/api/v1/ml/accident/predict",
        json={"contract_id": context["contract_id"]},
        headers=auth_headers(context["tenant_token"]),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_single_prediction_refresh_rejects_post_incident_contracts(client, mock_db):
    context = await _managed_contract(
        client, mock_db, suffix="prediction_post_incident", end_date="2026-10-01"
    )
    endpoint = f"/api/v1/hug/contracts/{context['contract_id']}/prediction/refresh"
    for status in ("IncidentReported", "RecoveryInProgress", "Closed"):
        await mock_db.contracts.update_one(
            {"_id": context["contract_id"]}, {"$set": {"contract_status": status}}
        )
        response = await client.post(
            endpoint, headers=auth_headers(context["hug_token"])
        )
        assert response.status_code == 409, response.text
        assert response.json()["error"]["details"]["current_status"] == status
    assert await mock_db.accident_predictions.count_documents(
        {"contract_id": context["contract_id"]}
    ) == 0


@pytest.mark.asyncio
async def test_prediction_out_of_model_support_is_explicit_not_scorable(client, mock_db):
    context = await _managed_contract(
        client,
        mock_db,
        suffix="unsupported",
        end_date="2026-10-01",
        address="제주특별자치도 제주시 중앙로 1",
    )
    result = await AccidentPredictionService(mock_db).refresh_contract(context["contract_id"])
    assert result.prediction_status == "NOT_SCORABLE"
    assert "SIDO_OUT_OF_SUPPORT" in result.failure_reason
    assert result.accident_probability is None
    assert result.risk_percentile is None


@pytest.mark.asyncio
async def test_d90_bundle_tracks_each_required_item_and_sweep_is_idempotent(client, mock_db):
    context = await _managed_contract(
        client, mock_db, suffix="d90", end_date="2026-10-01"
    )
    service = PreventionService(mock_db)
    first = await service.run_sweep(date(2026, 7, 23), [context["contract_id"]])
    assert first["checked"] == 1
    assert first["bundles_created"] == 1
    assert first["requests_created"] == 3
    assert await mock_db.incidents.count_documents({}) == 0

    second = await service.run_sweep(date(2026, 7, 23), [context["contract_id"]])
    assert second["bundles_created"] == 0
    assert second["requests_created"] == 0
    assert second["notifications_sent"] == 0
    assert await mock_db.evidence_requests.count_documents(
        {"contract_id": context["contract_id"]}
    ) == 3

    requests = [
        document
        async for document in mock_db.evidence_requests.find(
            {"contract_id": context["contract_id"]}
        )
    ]
    await mock_db.evidence_requests.update_one(
        {"_id": requests[0]["_id"]}, {"$set": {"verification_status": "Verified"}}
    )
    await service.run_sweep(date(2026, 7, 23), [context["contract_id"]])
    bundle = await mock_db.evidence_bundles.find_one({"contract_id": context["contract_id"]})
    assert bundle["verified_count"] == 1
    assert bundle["completion_ratio"] == pytest.approx(1 / 3, abs=0.0001)
    assert bundle["status"] != "Completed"

    await mock_db.evidence_requests.update_many(
        {"contract_id": context["contract_id"]}, {"$set": {"verification_status": "Verified"}}
    )
    await service.run_sweep(date(2026, 7, 23), [context["contract_id"]])
    bundle = await mock_db.evidence_bundles.find_one({"contract_id": context["contract_id"]})
    action = await mock_db.preventive_actions.find_one(
        {"details.evidence_bundle_id": bundle["_id"]}
    )
    assert bundle["verified_count"] == 3
    assert bundle["completion_ratio"] == 1
    assert bundle["status"] == "Completed"
    assert action["status"] == "Completed"
    assert await mock_db.incidents.count_documents({}) == 0


@pytest.mark.asyncio
async def test_concurrent_sweeps_create_one_prevention_workflow(client, mock_db):
    context = await _managed_contract(
        client, mock_db, suffix="concurrent_sweep", end_date="2026-10-01"
    )
    await ensure_indexes(mock_db)

    first, second = await asyncio.gather(
        PreventionService(mock_db).run_sweep(
            date(2026, 7, 23), [context["contract_id"]]
        ),
        PreventionService(mock_db).run_sweep(
            date(2026, 7, 23), [context["contract_id"]]
        ),
    )
    assert first["checked"] == second["checked"] == 1
    assert await mock_db.prevention_cases.count_documents(
        {"contract_id": context["contract_id"], "status": {"$ne": "Mitigated"}}
    ) == 1
    assert await mock_db.evidence_bundles.count_documents(
        {"contract_id": context["contract_id"]}
    ) == 1
    assert await mock_db.evidence_requests.count_documents(
        {"contract_id": context["contract_id"]}
    ) == 3
    assert await mock_db.preventive_actions.count_documents(
        {"contract_id": context["contract_id"]}
    ) == 1
    notifications = [
        item
        async for item in mock_db.notifications.find(
            {"contract_id": context["contract_id"]}
        )
    ]
    keys = [(item["user_id"], item.get("dedupe_key")) for item in notifications]
    assert len(keys) == len(set(keys))


@pytest.mark.asyncio
async def test_overdue_d30_escalates_and_notifications_are_structured(client, mock_db):
    context = await _managed_contract(
        client, mock_db, suffix="d30", end_date="2026-07-20"
    )
    result = await PreventionService(mock_db).run_sweep(
        date(2026, 7, 23), [context["contract_id"]]
    )
    assert result["bundles_created"] == 3
    assert result["requests_created"] == 9
    assert result["flagged"][0]["status"] == "EscalatedMonitoring"
    assert await mock_db.incidents.count_documents({}) == 0

    bundles = [
        document
        async for document in mock_db.evidence_bundles.find(
            {"contract_id": context["contract_id"]}
        )
    ]
    assert {bundle["checkpoint"] for bundle in bundles} == {"D90", "D60", "D30"}
    assert all(bundle["status"] == "Overdue" for bundle in bundles)

    notification_result = await NotificationService(mock_db).list(
        context["tenant_id"], 1, 100, False
    )
    prevention_notifications = [
        item for item in notification_result["items"] if item.category == "prevention_alert"
    ]
    assert prevention_notifications
    assert any(item.severity == "critical" for item in prevention_notifications)
    assert all(item.contract_id == context["contract_id"] for item in prevention_notifications)
    assert all(item.prevention_case_id for item in prevention_notifications)
    assert all(item.target_role == "tenant" for item in prevention_notifications)

    acknowledged = await client.patch(
        f"/api/v1/notifications/{prevention_notifications[0].notification_id}/acknowledge",
        headers=auth_headers(context["tenant_token"]),
    )
    assert acknowledged.status_code == 200, acknowledged.text
    assert acknowledged.json()["data"]["acknowledged_at"]
    stored = await mock_db.notifications.find_one(
        {"_id": prevention_notifications[0].notification_id}
    )
    assert stored["is_read"] is True
    assert stored["acknowledged_at"] is not None


@pytest.mark.asyncio
async def test_hug_contract_list_excludes_incident_and_action_transition_is_audited(client, mock_db):
    active = await _managed_contract(
        client, mock_db, suffix="active", end_date="2026-10-01"
    )
    await _managed_contract(
        client,
        mock_db,
        suffix="incident",
        end_date="2026-10-01",
        status="IncidentReported",
        address="서울특별시 송파구 올림픽로 1",
    )
    await PreventionService(mock_db).run_sweep(date(2026, 7, 23), [active["contract_id"]])

    listed = await HugContractService(mock_db).list_contracts(
        page=1, size=20, as_of_date=date(2026, 7, 23)
    )
    assert listed["pagination"]["total_elements"] == 1
    assert listed["items"][0]["contract_id"] == active["contract_id"]
    assert listed["items"][0]["prediction"]["calibration_status"]
    assert listed["items"][0]["evidence_bundle"]["required_count"] == 3

    prevention = PreventionService(mock_db)
    action = await prevention.create_action(
        active["contract_id"],
        PreventiveActionCreateRequest(
            action_type="CALLBACK",
            target_role="tenant",
            due_at="2026-07-25",
            note="상담 일정 확인",
        ),
        actor_user_id="hug-user",
        actor_role="hug_admin",
    )
    updated = await prevention.update_action(
        action.action_id,
        PreventiveActionUpdateRequest(status="InProgress", note="통화 시도"),
        actor_user_id="hug-user",
        actor_role="hug_admin",
    )
    completed = await prevention.update_action(
        action.action_id,
        PreventiveActionUpdateRequest(status="Completed", note="상담 완료"),
        actor_user_id="hug-user",
        actor_role="hug_admin",
    )
    assert updated.status == "InProgress"
    assert completed.status == "Completed"
    assert len(completed.audit_log) == 3

    response = await client.get(
        "/api/v1/hug/contracts?as_of_date=2026-07-23",
        headers=auth_headers(active["hug_token"]),
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["pagination"]["total_elements"] == 1
    response = await client.get(
        "/api/v1/hug/contracts", headers=auth_headers(active["tenant_token"])
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_preventive_action_cas_and_post_incident_guard(client, mock_db):
    context = await _managed_contract(
        client, mock_db, suffix="action_cas", end_date="2026-10-01"
    )
    service = PreventionService(mock_db)
    action = await service.create_action(
        context["contract_id"],
        PreventiveActionCreateRequest(
            action_type="CALLBACK",
            target_role="tenant",
            due_at="2026-07-25",
        ),
        actor_user_id="hug-user",
        actor_role="hug_admin",
    )

    # 같은 클라이언트 스냅샷을 전제로 한 CAS 두 건 중 하나만 반영되어야 한다.
    repository = PreventiveActionRepository(mock_db)
    stored_snapshot = await repository.get_by_id(action.action_id)
    outcomes = await asyncio.gather(
        repository.cas_transition(
            action.action_id,
            expected_status=stored_snapshot["status"],
            expected_updated_at=stored_snapshot["updated_at"],
            fields={"status": "InProgress", "updated_at": "2026-07-23T10:00:00+09:00"},
        ),
        repository.cas_transition(
            action.action_id,
            expected_status=stored_snapshot["status"],
            expected_updated_at=stored_snapshot["updated_at"],
            fields={"status": "Completed", "updated_at": "2026-07-23T10:00:01+09:00"},
        ),
    )
    assert sum(result is not None for result in outcomes) == 1
    assert sum(result is None for result in outcomes) == 1

    stale = await service.create_action(
        context["contract_id"],
        PreventiveActionCreateRequest(
            action_type="MANUAL_REVIEW",
            target_role="landlord",
        ),
        actor_user_id="hug-user",
        actor_role="hug_admin",
    )
    await mock_db.contracts.update_one(
        {"_id": context["contract_id"]},
        {"$set": {"contract_status": "IncidentReported"}},
    )
    with pytest.raises(StateConflictError, match="사고접수 전"):
        await service.update_action(
            stale.action_id,
            PreventiveActionUpdateRequest(status="InProgress"),
            actor_user_id="hug-user",
            actor_role="hug_admin",
        )
    stored = await mock_db.preventive_actions.find_one({"_id": stale.action_id})
    assert stored["status"] == "Requested"


@pytest.mark.asyncio
async def test_prediction_failure_is_persisted_and_does_not_stop_sweep(
    client, mock_db, monkeypatch
):
    failing = await _managed_contract(
        client, mock_db, suffix="model_fail", end_date="2026-10-01"
    )
    healthy = await _managed_contract(
        client,
        mock_db,
        suffix="model_ok",
        end_date="2026-10-02",
        address="서울특별시 서초구 반포대로 1",
    )
    original_refresh = AccidentPredictionService.refresh_contract

    async def _flaky_refresh(self, contract_id: str):
        if contract_id == failing["contract_id"]:
            raise ModelInferenceFailedError("테스트 모델 장애")
        return await original_refresh(self, contract_id)

    monkeypatch.setattr(AccidentPredictionService, "refresh_contract", _flaky_refresh)
    direct = await client.post(
        "/api/v1/ml/accident/predict",
        json={"contract_id": failing["contract_id"]},
        headers=auth_headers(failing["hug_token"]),
    )
    assert direct.status_code == 200, direct.text
    assert direct.json()["data"]["prediction_status"] == "FAILED"

    result = await PreventionService(mock_db).run_sweep(
        date(2026, 7, 23), [failing["contract_id"], healthy["contract_id"]]
    )

    assert result["checked"] == 2
    assert result["bundles_created"] == 2
    failed_prediction = await mock_db.accident_predictions.find_one(
        {"contract_id": failing["contract_id"]}
    )
    healthy_prediction = await mock_db.accident_predictions.find_one(
        {"contract_id": healthy["contract_id"]}
    )
    assert failed_prediction["prediction_status"] == "FAILED"
    assert failed_prediction["failure_reason"][0] == "MODEL_INFERENCE_FAILED"
    assert healthy_prediction["prediction_status"] == "SUCCESS"
    assert await mock_db.incidents.count_documents({}) == 0

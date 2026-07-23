from __future__ import annotations

import pytest

from app.core.exceptions import StateConflictError
from app.schemas.recovery import (
    RecoveryCloseRequest,
    RecoveryEventCreateRequest,
    RecoveryLedgerEntryCreateRequest,
    RecoveryPredictRequest,
)
from app.services.demo_scenario_service import DemoScenarioService
from app.services.recovery_service import RecoveryService


async def _seed(mock_db):
    await DemoScenarioService(mock_db).seed(use_model=False)


@pytest.mark.asyncio
async def test_event_storage_failure_does_not_change_claim_axis(mock_db, monkeypatch):
    await _seed(mock_db)
    service = RecoveryService(mock_db)
    before = await mock_db.recovery_claims.find_one({"_id": "demo-rc-s5"})

    async def fail_insert(_document):
        raise RuntimeError("injected event storage failure")

    monkeypatch.setattr(service._events, "insert", fail_insert)
    with pytest.raises(RuntimeError, match="event storage failure"):
        await service.add_event(
            "demo-rc-s5",
            RecoveryEventCreateRequest(
                event_type="CollectionRouteChanged",
                status_axis="collection_route",
                after="Litigation",
                idempotency_key="event-storage-failure",
            ),
            actor_user_id="test-hug",
            actor_role="hug_admin",
        )

    after = await mock_db.recovery_claims.find_one({"_id": "demo-rc-s5"})
    assert after["version"] == before["version"]
    assert after["collection_route"] == before["collection_route"]
    assert await mock_db.recovery_events.count_documents(
        {"idempotency_key": "event-storage-failure"}
    ) == 0


@pytest.mark.asyncio
async def test_ledger_storage_failure_does_not_change_balance(mock_db, monkeypatch):
    await _seed(mock_db)
    service = RecoveryService(mock_db)
    before = await mock_db.recovery_claims.find_one({"_id": "demo-rc-s5"})

    async def fail_insert(_document):
        raise RuntimeError("injected ledger storage failure")

    monkeypatch.setattr(service._ledger, "insert", fail_insert)
    with pytest.raises(RuntimeError, match="ledger storage failure"):
        await service.add_ledger_entry(
            "demo-rc-s5",
            RecoveryLedgerEntryCreateRequest(
                entry_type="LEGAL_COST_ACCRUAL",
                amount_won=500_000,
                idempotency_key="ledger-storage-failure",
            ),
            actor_user_id="test-hug",
            actor_role="hug_admin",
        )

    after = await mock_db.recovery_claims.find_one({"_id": "demo-rc-s5"})
    assert after["version"] == before["version"]
    assert after["balance"] == before["balance"]
    assert after["balances"] == before["balances"]
    assert await mock_db.recovery_ledger.count_documents(
        {"idempotency_key": "ledger-storage-failure"}
    ) == 0


@pytest.mark.asyncio
async def test_ledger_cas_conflict_discards_pending_entry(mock_db, monkeypatch):
    await _seed(mock_db)
    service = RecoveryService(mock_db)
    before = await mock_db.recovery_claims.find_one({"_id": "demo-rc-s5"})

    async def lose_cas(*_args, **_kwargs):
        return None

    monkeypatch.setattr(service._claims, "update_open_with_version", lose_cas)
    with pytest.raises(StateConflictError, match="동시에 원장이 변경"):
        await service.add_ledger_entry(
            "demo-rc-s5",
            RecoveryLedgerEntryCreateRequest(
                entry_type="LEGAL_COST_ACCRUAL",
                amount_won=500_000,
                idempotency_key="ledger-cas-conflict",
            ),
            actor_user_id="test-hug",
            actor_role="hug_admin",
        )

    after = await mock_db.recovery_claims.find_one({"_id": "demo-rc-s5"})
    assert after["version"] == before["version"]
    assert after["balances"] == before["balances"]
    assert await mock_db.recovery_ledger.count_documents(
        {"idempotency_key": "ledger-cas-conflict"}
    ) == 0


@pytest.mark.asyncio
async def test_close_event_storage_failure_leaves_claim_open(mock_db, monkeypatch):
    await _seed(mock_db)
    service = RecoveryService(mock_db)
    before = await mock_db.recovery_claims.find_one({"_id": "demo-rc-s5"})

    async def fail_insert(_document):
        raise RuntimeError("injected close event storage failure")

    monkeypatch.setattr(service._events, "insert", fail_insert)
    with pytest.raises(RuntimeError, match="close event storage failure"):
        await service.close(
            "demo-rc-s5",
            RecoveryCloseRequest(
                reason="OTHER_APPROVED",
                note="테스트 승인 종결",
                confirm=True,
                idempotency_key="close-storage-failure",
            ),
            actor_user_id="test-hug",
            actor_role="hug_admin",
        )

    after = await mock_db.recovery_claims.find_one({"_id": "demo-rc-s5"})
    assert after["version"] == before["version"]
    assert after["is_closed"] is False
    assert after["closed_at"] is None


@pytest.mark.asyncio
async def test_prediction_becomes_stale_when_claim_closes_before_latest_cas(
    mock_db, monkeypatch
):
    await _seed(mock_db)
    service = RecoveryService(mock_db)
    before = await mock_db.recovery_claims.find_one({"_id": "demo-rc-s5"})

    def fake_predict(_input):
        return {
            "pred_recovery_ratio": 0.8,
            "pred_recovery_grade": "HIGH",
            "pred_days_to_dividend": 200,
            "expected_recovery_won": 168_000_000,
            "priority_score": 80.0,
            "priority_weights": {"recovery": 0.6, "speed": 0.4},
            "portfolio_size": 28_961,
            "top_factors": [],
            "basis": "테스트",
        }

    monkeypatch.setattr(
        "app.services.recovery_service.ml_service.predict_recovery", fake_predict
    )
    original_insert = service._predictions.insert

    async def insert_then_close(document):
        result = await original_insert(document)
        await mock_db.recovery_claims.update_one(
            {"_id": "demo-rc-s5"},
            {
                "$set": {
                    "is_closed": True,
                    "closed_at": "2026-07-23T12:00:00+09:00",
                    "closure": {"reason": "OTHER_APPROVED"},
                },
                "$inc": {"version": 1},
            },
        )
        return result

    monkeypatch.setattr(service._predictions, "insert", insert_then_close)
    with pytest.raises(StateConflictError, match="변경되었거나 종결"):
        await service.predict(
            "demo-rc-s5",
            RecoveryPredictRequest(idempotency_key="predict-close-race"),
            actor_user_id="test-hug",
        )

    after = await mock_db.recovery_claims.find_one({"_id": "demo-rc-s5"})
    assert after["latest_prediction_id"] == before["latest_prediction_id"]
    assert after["latest_prediction"] == before["latest_prediction"]
    stale = await mock_db.recovery_predictions.find_one(
        {"idempotency_key": "predict-close-race"}
    )
    assert stale["prediction_status"] == "STALE"
    assert stale["stale_reason"] == "claim_closed_or_version_changed"
    latest_valid = await service._predictions.latest_for_claim("demo-rc-s5")
    assert latest_valid["_id"] == before["latest_prediction_id"]


@pytest.mark.asyncio
async def test_pending_event_is_reconciled_after_commit_marker_failure_and_fingerprint_guarded(
    mock_db, monkeypatch
):
    await _seed(mock_db)
    service = RecoveryService(mock_db)
    original_mark = service._events.mark_committed
    calls = 0

    async def fail_once(event_id):
        nonlocal calls
        calls += 1
        if calls == 1:
            return False
        return await original_mark(event_id)

    monkeypatch.setattr(service._events, "mark_committed", fail_once)
    payload = RecoveryEventCreateRequest(
        event_type="CollectionRouteChanged",
        status_axis="collection_route",
        after="Litigation",
        idempotency_key="event-reconcile-after-marker-failure",
    )
    with pytest.raises(StateConflictError, match="확정에 실패"):
        await service.add_event(
            "demo-rc-s5", payload, actor_user_id="test-hug", actor_role="hug_admin"
        )
    applied = await mock_db.recovery_claims.find_one({"_id": "demo-rc-s5"})
    applied_version = applied["version"]
    assert applied["collection_route"] == "Litigation"

    replay = await service.add_event(
        "demo-rc-s5", payload, actor_user_id="test-hug", actor_role="hug_admin"
    )
    assert replay["idempotent_replay"] is True
    assert replay["reconciled"] is True
    assert (await mock_db.recovery_claims.find_one({"_id": "demo-rc-s5"}))["version"] == applied_version

    with pytest.raises(StateConflictError, match="다른 요청 내용"):
        await service.add_event(
            "demo-rc-s5",
            RecoveryEventCreateRequest(
                event_type="CollectionRouteChanged",
                status_axis="collection_route",
                after="PaymentPlan",
                idempotency_key="event-reconcile-after-marker-failure",
            ),
            actor_user_id="test-hug",
            actor_role="hug_admin",
        )


@pytest.mark.asyncio
async def test_ambiguous_ledger_cas_is_reconciled_without_double_application(
    mock_db, monkeypatch
):
    await _seed(mock_db)
    service = RecoveryService(mock_db)
    original_update = service._claims.update_open_with_version

    async def apply_then_timeout(*args, **kwargs):
        await original_update(*args, **kwargs)
        raise TimeoutError("simulated response loss after write")

    monkeypatch.setattr(service._claims, "update_open_with_version", apply_then_timeout)
    payload = RecoveryLedgerEntryCreateRequest(
        entry_type="LEGAL_COST_ACCRUAL",
        amount_won=700_000,
        idempotency_key="ledger-ambiguous-write-reconcile",
    )
    with pytest.raises(TimeoutError, match="response loss"):
        await service.add_ledger_entry(
            "demo-rc-s5", payload, actor_user_id="test-hug", actor_role="hug_admin"
        )
    applied = await mock_db.recovery_claims.find_one({"_id": "demo-rc-s5"})
    assert applied["balances"]["legal_cost"] == 700_000
    applied_version = applied["version"]

    monkeypatch.setattr(service._claims, "update_open_with_version", original_update)
    replay = await service.add_ledger_entry(
        "demo-rc-s5", payload, actor_user_id="test-hug", actor_role="hug_admin"
    )
    assert replay["idempotent_replay"] is True
    assert replay["reconciled"] is True
    final = await mock_db.recovery_claims.find_one({"_id": "demo-rc-s5"})
    assert final["balances"]["legal_cost"] == 700_000
    assert final["version"] == applied_version


@pytest.mark.asyncio
async def test_pending_ledger_never_commits_from_matching_balance_without_receipt(
    mock_db, monkeypatch
):
    await _seed(mock_db)
    service = RecoveryService(mock_db)
    original_mark = service._ledger.mark_committed

    async def lose_commit_marker(_entry_id, **_kwargs):
        return False

    monkeypatch.setattr(service._ledger, "mark_committed", lose_commit_marker)
    payload = RecoveryLedgerEntryCreateRequest(
        entry_type="LEGAL_COST_ACCRUAL",
        amount_won=500_000,
        idempotency_key="ledger-receipt-required",
    )
    with pytest.raises(StateConflictError, match="확정에 실패"):
        await service.add_ledger_entry(
            "demo-rc-s5", payload, actor_user_id="test-hug", actor_role="hug_admin"
        )
    pending = await mock_db.recovery_ledger.find_one(
        {"idempotency_key": "ledger-receipt-required"}
    )
    # 최종 잔액만 우연히 같아도 영수증이 없다면 원 작업이 적용됐다고 추정하면 안 된다.
    await mock_db.recovery_claims.update_one(
        {"_id": "demo-rc-s5"},
        {"$unset": {f"operation_receipts.{pending['receipt_key']}": ""}},
    )
    monkeypatch.setattr(service._ledger, "mark_committed", original_mark)
    replay = await service.add_ledger_entry(
        "demo-rc-s5", payload, actor_user_id="test-hug", actor_role="hug_admin"
    )
    assert replay["idempotent_replay"] is False
    final = await mock_db.recovery_claims.find_one({"_id": "demo-rc-s5"})
    assert final["balances"]["legal_cost"] == 1_000_000


@pytest.mark.asyncio
async def test_close_marker_failure_replay_finishes_parent_cascade(mock_db, monkeypatch):
    await _seed(mock_db)
    service = RecoveryService(mock_db)
    original_mark = service._events.mark_committed
    calls = 0

    async def fail_once(event_id):
        nonlocal calls
        calls += 1
        if calls == 1:
            return False
        return await original_mark(event_id)

    monkeypatch.setattr(service._events, "mark_committed", fail_once)
    payload = RecoveryCloseRequest(
        reason="OTHER_APPROVED",
        note="회수불능 승인 종결",
        confirm=True,
        idempotency_key="close-marker-reconcile-s5",
    )
    with pytest.raises(StateConflictError, match="확정에 실패"):
        await service.close(
            "demo-rc-s5", payload, actor_user_id="test-hug", actor_role="hug_admin"
        )
    assert (await mock_db.recovery_claims.find_one({"_id": "demo-rc-s5"}))["is_closed"] is True
    assert (await mock_db.incidents.find_one({"_id": "demo-inc-s5"}))["status"] != "Closed"

    replay = await service.close(
        "demo-rc-s5", payload, actor_user_id="test-hug", actor_role="hug_admin"
    )
    assert replay["idempotent_replay"] is True
    assert replay["reconciled"] is True
    assert replay["parent_sync"]["status"] == "CLOSED"
    assert (await mock_db.incidents.find_one({"_id": "demo-inc-s5"}))["status"] == "Closed"
    assert (await mock_db.contracts.find_one({"_id": "demo-ct-s5"}))["contract_status"] == "Closed"


@pytest.mark.asyncio
async def test_orphan_pending_ledger_has_no_sequence_and_does_not_block_other_writes(
    mock_db, monkeypatch
):
    """예약(PENDING) 단계는 sequence를 차지하지 않으므로, 크래시로 남은 고아
    PENDING이 다른 멱등키 원장 쓰기를 unique 충돌(500)로 잠그지 못한다."""
    await _seed(mock_db)
    service = RecoveryService(mock_db)
    original_update = service._claims.update_open_with_version

    async def crash_before_cas(*_args, **_kwargs):
        raise RuntimeError("simulated crash before claim CAS")

    monkeypatch.setattr(service._claims, "update_open_with_version", crash_before_cas)
    orphan_payload = RecoveryLedgerEntryCreateRequest(
        entry_type="LEGAL_COST_ACCRUAL",
        amount_won=400_000,
        idempotency_key="ledger-orphan-pending",
    )
    with pytest.raises(RuntimeError, match="crash before claim CAS"):
        await service.add_ledger_entry(
            "demo-rc-s5", orphan_payload, actor_user_id="test-hug", actor_role="hug_admin"
        )
    orphan = await mock_db.recovery_ledger.find_one(
        {"idempotency_key": "ledger-orphan-pending"}
    )
    assert orphan["operation_status"] == "PENDING"
    assert "sequence" not in orphan

    # 고아 PENDING이 남아 있어도 다른 멱등키의 원장 쓰기는 그대로 진행된다.
    monkeypatch.setattr(service._claims, "update_open_with_version", original_update)
    other = await service.add_ledger_entry(
        "demo-rc-s5",
        RecoveryLedgerEntryCreateRequest(
            entry_type="LEGAL_COST_ACCRUAL",
            amount_won=600_000,
            idempotency_key="ledger-after-orphan",
        ),
        actor_user_id="test-hug",
        actor_role="hug_admin",
    )
    assert other["operation_status"] == "COMMITTED"
    assert isinstance(other["sequence"], int)

    # 같은 키 재시도는 receipt 없는 고아를 정리하고 새 sequence로 확정한다.
    retried = await service.add_ledger_entry(
        "demo-rc-s5", orphan_payload, actor_user_id="test-hug", actor_role="hug_admin"
    )
    assert retried["operation_status"] == "COMMITTED"
    assert retried["sequence"] != other["sequence"]

    committed = [
        doc
        async for doc in mock_db.recovery_ledger.find(
            {"recovery_claim_id": "demo-rc-s5", "operation_status": "COMMITTED"}
        )
    ]
    sequences = [doc["sequence"] for doc in committed]
    assert len(sequences) == len(set(sequences))
    final = await mock_db.recovery_claims.find_one({"_id": "demo-rc-s5"})
    assert final["balances"]["legal_cost"] == 1_000_000
    assert final["ledger_sequence"] == max(sequences)


@pytest.mark.asyncio
async def test_ledger_sequence_uses_serialized_claim_counter(mock_db):
    """확정 sequence는 claim version CAS로 직렬화된 ledger_sequence 카운터에서
    나오며, receipt에도 남아 ambiguous write 복구에 사용된다."""
    await _seed(mock_db)
    service = RecoveryService(mock_db)
    first = await service.add_ledger_entry(
        "demo-rc-s6",
        RecoveryLedgerEntryCreateRequest(
            entry_type="ENFORCEMENT_COST_ACCRUAL",
            amount_won=200_000,
            idempotency_key="ledger-seq-first",
        ),
        actor_user_id="test-hug",
        actor_role="hug_admin",
    )
    second = await service.add_ledger_entry(
        "demo-rc-s6",
        RecoveryLedgerEntryCreateRequest(
            entry_type="ENFORCEMENT_COST_ACCRUAL",
            amount_won=300_000,
            idempotency_key="ledger-seq-second",
        ),
        actor_user_id="test-hug",
        actor_role="hug_admin",
    )
    assert second["sequence"] == first["sequence"] + 1

    claim = await mock_db.recovery_claims.find_one({"_id": "demo-rc-s6"})
    assert claim["ledger_sequence"] == second["sequence"]
    receipt = claim["operation_receipts"][second["receipt_key"]]
    assert receipt["sequence"] == second["sequence"]

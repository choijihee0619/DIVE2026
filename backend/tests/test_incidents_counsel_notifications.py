from __future__ import annotations

import pytest

from tests.helpers import auth_headers, signup_and_login

INCIDENT_PAYLOAD = {
    "incident_type": "DEPOSIT_NOT_RETURNED",
    "description": "계약이 만료되었는데 임대인이 보증금 1.8억을 돌려주지 않고 연락을 피하고 있습니다.",
    "deposit_amount": 180000000,
}


@pytest.mark.asyncio
async def test_incident_full_flow(client):
    tenant = await signup_and_login(client, "tenant_inc@example.com", role="tenant")
    hug = await signup_and_login(client, "hug_inc@example.com", role="hug_admin")

    # 접수
    resp = await client.post("/api/v1/incidents", json=INCIDENT_PAYLOAD, headers=auth_headers(tenant))
    assert resp.status_code == 201, resp.text
    incident = resp.json()["data"]
    incident_id = incident["incident_id"]
    assert incident["status"] == "Received"
    assert incident["incident_type_label"] == "보증금 미반환"
    assert incident["next_steps"]

    # 접수자 알림 생성 확인
    resp = await client.get("/api/v1/notifications", headers=auth_headers(tenant))
    assert resp.status_code == 200
    notes = resp.json()["data"]
    assert notes["unread_count"] >= 1
    assert any(n["category"] == "incident_update" for n in notes["items"])

    # HUG 큐 조회
    resp = await client.get("/api/v1/incidents?status=Received", headers=auth_headers(hug))
    assert resp.status_code == 200
    assert any(i["incident_id"] == incident_id for i in resp.json()["data"]["items"])

    # 잘못된 전이 거부 (Received → TransferredToRecovery 는 불가)
    resp = await client.patch(
        f"/api/v1/incidents/{incident_id}/status",
        json={"status": "TransferredToRecovery"},
        headers=auth_headers(hug),
    )
    assert resp.status_code == 422

    # 정상 전이: Reviewing → TransferredToRecovery
    for status in ("Reviewing", "TransferredToRecovery"):
        resp = await client.patch(
            f"/api/v1/incidents/{incident_id}/status",
            json={"status": status, "note": f"{status} 처리"},
            headers=auth_headers(hug),
        )
        assert resp.status_code == 200, resp.text
    detail = resp.json()["data"]
    assert detail["status"] == "TransferredToRecovery"
    assert len(detail["timeline"]) == 3

    # 임차인은 상태 전이 불가
    resp = await client.patch(
        f"/api/v1/incidents/{incident_id}/status",
        json={"status": "Closed"},
        headers=auth_headers(tenant),
    )
    assert resp.status_code == 403

    # 타인 사고 조회 불가
    other = await signup_and_login(client, "tenant_inc2@example.com", role="tenant")
    resp = await client.get(f"/api/v1/incidents/{incident_id}", headers=auth_headers(other))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_counsel_queue_flow_with_auto_classification(client):
    tenant = await signup_and_login(client, "tenant_cq@example.com", role="tenant")
    advisor = await signup_and_login(client, "advisor_cq@example.com", role="advisor")

    resp = await client.post(
        "/api/v1/counsel-queue",
        json={"text": "임대인이 보증금을 안 돌려줘서 내용증명을 보냈는데 다음 절차가 궁금합니다.",
              "source": "chatbot_escalation"},
        headers=auth_headers(tenant),
    )
    assert resp.status_code == 201, resp.text
    item = resp.json()["data"]
    counsel_id = item["counsel_id"]
    # ML 모델이 있으면 자동분류 + high 우선순위
    if item["classification"]["classified"]:
        assert item["classification"]["dispute_type"]
        assert item["priority"] == "high"

    # 상담사 큐 목록 (high 먼저)
    resp = await client.get("/api/v1/counsel-queue?status=Waiting", headers=auth_headers(advisor))
    assert resp.status_code == 200
    assert any(i["counsel_id"] == counsel_id for i in resp.json()["data"]["items"])

    # 임차인은 본인 요청만 보임
    resp = await client.get("/api/v1/counsel-queue", headers=auth_headers(tenant))
    assert all(i["requester_user_id"] for i in resp.json()["data"]["items"])

    # 상담사 처리: InProgress → Answered (답변 시 요청자 알림)
    resp = await client.patch(
        f"/api/v1/counsel-queue/{counsel_id}",
        json={"status": "InProgress"},
        headers=auth_headers(advisor),
    )
    assert resp.status_code == 200, resp.text
    resp = await client.patch(
        f"/api/v1/counsel-queue/{counsel_id}",
        json={"status": "Answered", "answer_note": "이행청구 요건을 확인한 뒤 지급명령을 검토하세요."},
        headers=auth_headers(advisor),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["answer_note"]

    resp = await client.get("/api/v1/notifications", headers=auth_headers(tenant))
    assert any(n["category"] == "counsel_update" for n in resp.json()["data"]["items"])

    # 임차인이 상담 상태 변경 시도 → 403
    resp = await client.patch(
        f"/api/v1/counsel-queue/{counsel_id}",
        json={"status": "Closed"},
        headers=auth_headers(tenant),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_notifications_demo_seed_and_read(client):
    tenant = await signup_and_login(client, "tenant_noti@example.com", role="tenant")

    resp = await client.post("/api/v1/notifications/demo-seed", headers=auth_headers(tenant))
    assert resp.status_code == 201, resp.text
    assert resp.json()["data"]["created"] == 3

    resp = await client.get("/api/v1/notifications?unread_only=true", headers=auth_headers(tenant))
    data = resp.json()["data"]
    assert data["unread_count"] == 3
    first_id = data["items"][0]["notification_id"]

    resp = await client.patch(f"/api/v1/notifications/{first_id}/read", headers=auth_headers(tenant))
    assert resp.status_code == 200

    resp = await client.patch("/api/v1/notifications/read-all", headers=auth_headers(tenant))
    assert resp.status_code == 200
    assert resp.json()["data"]["marked_read"] == 2

    resp = await client.get("/api/v1/notifications", headers=auth_headers(tenant))
    assert resp.json()["data"]["unread_count"] == 0

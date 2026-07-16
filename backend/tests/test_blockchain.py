from __future__ import annotations

from tests.helpers import auth_headers, signup_and_login


async def test_anchor_generates_mock_tx_hash(client):
    token = await signup_and_login(client, "advisor_bc@example.com", role="advisor")
    resp = await client.post(
        "/api/v1/blockchain/anchor",
        json={"event_type": "RiskAssessed", "reference_id": "10000000-0000-0000-0000-000000000001"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 202, resp.text
    data = resp.json()["data"]
    assert data["is_mock"] is True
    assert data["tx_hash"].startswith("0x")
    assert data["blockchain_status"] == "Confirmed"


async def test_anchor_duplicate_request_returns_same_tx(client):
    token = await signup_and_login(client, "advisor_bc2@example.com", role="advisor")
    payload = {"event_type": "EvidenceSubmitted", "reference_id": "20000000-0000-0000-0000-000000000002"}

    first = await client.post("/api/v1/blockchain/anchor", json=payload, headers=auth_headers(token))
    second = await client.post("/api/v1/blockchain/anchor", json=payload, headers=auth_headers(token))

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["data"]["tx_hash"] == second.json()["data"]["tx_hash"]
    assert first.json()["data"]["blockchain_tx_id"] == second.json()["data"]["blockchain_tx_id"]


async def test_get_blockchain_transaction(client):
    token = await signup_and_login(client, "advisor_bc3@example.com", role="advisor")
    anchor_resp = await client.post(
        "/api/v1/blockchain/anchor",
        json={"event_type": "VerificationCompleted", "reference_id": "30000000-0000-0000-0000-000000000003"},
        headers=auth_headers(token),
    )
    tx_id = anchor_resp.json()["data"]["blockchain_tx_id"]

    get_resp = await client.get(f"/api/v1/blockchain/{tx_id}", headers=auth_headers(token))
    assert get_resp.status_code == 200
    assert get_resp.json()["data"]["blockchain_tx_id"] == tx_id


async def test_get_blockchain_transaction_not_found(client):
    token = await signup_and_login(client, "advisor_bc4@example.com", role="advisor")
    resp = await client.get(
        "/api/v1/blockchain/00000000-0000-0000-0000-000000000000", headers=auth_headers(token)
    )
    assert resp.status_code == 404

from __future__ import annotations

import pytest


async def test_health_root(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "Success"
    assert body["data"]["dependencies"]["database"] == "ok"


async def test_health_v1(client):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "ok"


async def test_health_reports_down_when_mongo_disconnected(client, monkeypatch):
    from app.db.mongodb import MongoDB

    async def fake_ping(cls=None):
        return False

    monkeypatch.setattr(MongoDB, "ping", classmethod(lambda cls: fake_ping()))

    resp = await client.get("/health")
    assert resp.status_code == 503
    assert resp.json()["data"]["dependencies"]["database"] == "down"

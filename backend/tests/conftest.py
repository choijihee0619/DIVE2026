"""테스트 공통 fixture.

실제 Atlas 연결 없이 mongomock-motor로 MongoDB를 대체한다. FastAPI lifespan(MongoDB.connect())을
트리거하지 않기 위해 Starlette TestClient 대신 httpx.ASGITransport를 직접 사용한다.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

from app.db.mongodb import MongoDB


@pytest.fixture
async def mock_db():
    client = AsyncMongoMockClient()
    db = client["test_db"]
    MongoDB.client = client
    MongoDB.db = db
    yield db
    MongoDB.client = None
    MongoDB.db = None


@pytest.fixture(autouse=True)
def _patch_health_ping(monkeypatch):
    async def _fake_ping(cls=None):
        return MongoDB.db is not None

    monkeypatch.setattr(MongoDB, "ping", classmethod(lambda cls: _fake_ping()))


@pytest.fixture
async def client(mock_db):
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

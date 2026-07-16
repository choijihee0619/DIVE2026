"""Motor 기반 비동기 MongoDB 연결. lifespan에서 1회 연결하고 종료 시 close한다.

기존 scripts/setup_mongodb.py 로 이미 만들어진 Atlas `dive2026` 데이터베이스의 컬렉션/인덱스를
그대로 사용하며, 이 모듈에서 컬렉션명을 새로 만들지 않는다.
"""

from __future__ import annotations

import logging

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import get_settings

logger = logging.getLogger(__name__)

try:
    import certifi

    _CERTIFI_CA_FILE: str | None = certifi.where()
except ImportError:  # pragma: no cover - certifi는 requirements에 포함되어 있음
    _CERTIFI_CA_FILE = None


class MongoDB:
    client: AsyncIOMotorClient | None = None
    db: AsyncIOMotorDatabase | None = None

    @classmethod
    async def connect(cls) -> None:
        settings = get_settings()
        if not settings.mongodb_uri:
            raise RuntimeError("MONGODB_URI가 설정되지 않았습니다. backend/.env를 확인하세요.")
        client_kwargs: dict = {"serverSelectionTimeoutMS": 15000, "uuidRepresentation": "standard"}
        if _CERTIFI_CA_FILE:
            client_kwargs["tlsCAFile"] = _CERTIFI_CA_FILE
        cls.client = AsyncIOMotorClient(settings.mongodb_uri, **client_kwargs)
        cls.db = cls.client[settings.mongodb_db_name]
        # 연결 실패를 앱 시작 시점에 명확히 드러낸다.
        await cls.client.admin.command("ping")
        logger.info("MongoDB connected: db=%s", settings.mongodb_db_name)

    @classmethod
    async def close(cls) -> None:
        if cls.client is not None:
            cls.client.close()
            cls.client = None
            cls.db = None
            logger.info("MongoDB connection closed")

    @classmethod
    async def ping(cls) -> bool:
        if cls.client is None:
            return False
        try:
            await cls.client.admin.command("ping")
            return True
        except Exception:  # noqa: BLE001 - health check는 원인 불문 down으로만 보고
            return False


def get_db() -> AsyncIOMotorDatabase:
    if MongoDB.db is None:
        raise RuntimeError("MongoDB가 아직 연결되지 않았습니다.")
    return MongoDB.db

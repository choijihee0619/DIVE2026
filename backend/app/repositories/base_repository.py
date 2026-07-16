"""Repository 공통 베이스. Beanie 없이 Motor 컬렉션을 직접 감싸 CRUD/페이지네이션을 캡슐화한다.

Backend_API_명세서 6장 원칙: Repository는 상태전이·권한판단·외부API호출을 하지 않고 조회/CRUD만 담당한다.
"""

from __future__ import annotations

from typing import Any

from motor.motor_asyncio import AsyncIOMotorCollection, AsyncIOMotorDatabase


class BaseRepository:
    collection_name: str = ""

    def __init__(self, db: AsyncIOMotorDatabase):
        self._db = db

    @property
    def collection(self) -> AsyncIOMotorCollection:
        return self._db[self.collection_name]

    async def get_by_id(self, doc_id: str) -> dict[str, Any] | None:
        return await self.collection.find_one({"_id": doc_id})

    async def exists(self, doc_id: str) -> bool:
        return await self.collection.count_documents({"_id": doc_id}, limit=1) > 0

    async def insert(self, document: dict[str, Any]) -> dict[str, Any]:
        await self.collection.insert_one(document)
        return document

    async def update_fields(self, doc_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
        await self.collection.update_one({"_id": doc_id}, {"$set": fields})
        return await self.get_by_id(doc_id)

    async def list_paginated(
        self,
        query: dict[str, Any],
        skip: int,
        limit: int,
        sort: list[tuple[str, int]] | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        cursor = self.collection.find(query)
        if sort:
            cursor = cursor.sort(sort)
        cursor = cursor.skip(skip).limit(limit)
        items = [doc async for doc in cursor]
        total = await self.collection.count_documents(query)
        return items, total

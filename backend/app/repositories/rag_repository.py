"""rag_chunks(Atlas Vector Search 대상)와 rag_search_logs(검색/상담 이력) Repository.

rag_chunks 문서 필드명은 scripts/embed_rag_chunks.py가 실제로 쓰고 있는 이름
(text, region_sido, region_sigungu, embedding, embedding_model)을 그대로 따른다.
Backend_API_명세서 14장의 region_code/excerpt 표기와는 다르며, 이미 1,009건이 실제 코드 기준으로
임베딩되어 있으므로 문서 대신 실제 데이터를 기준으로 구현한다(충돌사항 5.3 참고).
"""

from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.repositories.base_repository import BaseRepository


class RagChunkRepository(BaseRepository):
    collection_name = "rag_chunks"

    async def vector_search(
        self,
        query_vector: list[float],
        top_k: int,
        topic: str | None = None,
        region: str | None = None,
    ) -> list[dict[str, Any]]:
        settings = get_settings()
        filters: list[dict[str, Any]] = []
        if topic:
            filters.append({"topic": topic})
        if region:
            filters.append({"$or": [{"region_sido": region}, {"region_sigungu": region}]})

        vector_search_stage: dict[str, Any] = {
            "index": settings.atlas_vector_index_name,
            "path": settings.atlas_vector_path,
            "queryVector": query_vector,
            "numCandidates": max(top_k * 20, 100),
            "limit": top_k,
        }
        if filters:
            vector_search_stage["filter"] = filters[0] if len(filters) == 1 else {"$and": filters}

        pipeline = [
            {"$vectorSearch": vector_search_stage},
            {
                "$project": {
                    "chunk_id": 1,
                    "doc_id": 1,
                    "source": 1,
                    "topic": 1,
                    "consultation_stage": 1,
                    "region_sido": 1,
                    "region_sigungu": 1,
                    "text": 1,
                    "metadata": 1,
                    "score": {"$meta": "vectorSearchScore"},
                }
            },
        ]
        return [doc async for doc in self.collection.aggregate(pipeline)]

    async def keyword_fallback_search(
        self, topic: str | None, region: str | None, top_k: int
    ) -> list[dict[str, Any]]:
        """Atlas Vector Search를 쓸 수 없을 때(OpenAI 키 없음 등) 사용하는 최소 키워드 검색."""
        query: dict[str, Any] = {}
        if topic:
            query["topic"] = topic
        if region:
            query["$or"] = [{"region_sido": region}, {"region_sigungu": region}]
        cursor = self.collection.find(query).limit(top_k)
        return [doc async for doc in cursor]


class RagSearchLogRepository(BaseRepository):
    collection_name = "rag_search_logs"

    async def list_for_user(self, user_id: str, skip: int, limit: int) -> tuple[list[dict[str, Any]], int]:
        return await self.list_paginated({"user_id": user_id}, skip, limit, sort=[("created_at", -1)])

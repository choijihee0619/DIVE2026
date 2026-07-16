"""RAG 검색/답변 서비스. Atlas Vector Search($vectorSearch) + OpenAI 임베딩을 사용한다.

scripts/embed_rag_chunks.py가 이미 만들어 둔 rag_chunks 컬렉션(1,009건, text-embedding-3-large,
1024차원, 인덱스 rag_chunks_vector_index)을 그대로 사용하고 새 임베딩 파이프라인을 만들지 않는다.
"""

from __future__ import annotations

import logging

from motor.motor_asyncio import AsyncIOMotorDatabase
from openai import APIError, AsyncOpenAI, OpenAIError

from app.core.config import get_settings
from app.core.exceptions import ExternalAPIFailedError
from app.repositories.rag_repository import RagChunkRepository, RagSearchLogRepository
from app.schemas.rag import (
    RagAnswerRequest,
    RagAnswerResponse,
    RagChunkResponse,
    RagSearchRequest,
    RagSearchResponse,
)
from app.utils.datetime_utils import now_kst_iso, new_uuid
from app.utils.pii_masking import truncate_snippet

logger = logging.getLogger(__name__)

DISCLAIMER = "본 답변은 법률 자문이 아니며 상담/검증 담당자의 판단을 돕기 위한 정보 제공입니다."


class RagService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._chunks = RagChunkRepository(db)
        self._logs = RagSearchLogRepository(db)
        self._settings = get_settings()
        self._client = AsyncOpenAI(api_key=self._settings.openai_api_key) if self._settings.openai_api_key else None

    async def _embed_query(self, text: str) -> list[float] | None:
        if not self._client:
            return None
        try:
            resp = await self._client.embeddings.create(
                model=self._settings.openai_embedding_model,
                input=[text],
                dimensions=self._settings.openai_embedding_dimensions,
                encoding_format="float",
            )
            return resp.data[0].embedding
        except (APIError, OpenAIError) as exc:
            logger.warning("OpenAI embedding failed: %s", exc)
            raise ExternalAPIFailedError(
                "임베딩 생성 중 외부 API(OpenAI) 오류가 발생했습니다.",
                details={"provider": "openai", "internal_reason": "EMBEDDING_FAILED"},
            ) from exc

    async def search(self, user_id: str | None, payload: RagSearchRequest) -> RagSearchResponse:
        query_text = " ".join(filter(None, [payload.topic, payload.region, payload.consultation_stage]))
        vector = await self._embed_query(query_text)

        is_mock = vector is None
        if vector is not None:
            docs = await self._chunks.vector_search(vector, payload.top_k, region=payload.region)
        else:
            docs = await self._chunks.keyword_fallback_search(payload.topic, payload.region, payload.top_k)

        chunks = [
            RagChunkResponse(
                chunk_id=d.get("chunk_id", d.get("_id", "")),
                source=d.get("source"),
                topic=d.get("topic"),
                consultation_stage=d.get("consultation_stage"),
                region=d.get("region_sido") or d.get("region_sigungu"),
                excerpt=truncate_snippet(d.get("text")),
                pii_removed=bool(d.get("metadata", {}).get("pii_removed", False)),
                score=d.get("score"),
            )
            for d in docs
        ]

        log_id = new_uuid()
        await self._logs.insert(
            {
                "_id": log_id,
                "user_id": user_id,
                "query": payload.model_dump(exclude_none=True),
                "result_chunk_ids": [c.chunk_id for c in chunks],
                "result_count": len(chunks),
                "is_mock": is_mock,
                "answer_masked": None,
                "created_at": now_kst_iso(),
            }
        )

        return RagSearchResponse(
            query=payload.model_dump(exclude_none=True),
            chunks=chunks,
            is_mock=is_mock,
            rag_search_log_id=log_id,
        )

    async def answer(self, user_id: str | None, payload: RagAnswerRequest) -> RagAnswerResponse:
        search_result = await self.search(
            user_id,
            RagSearchRequest(
                topic=payload.topic,
                region=payload.region,
                consultation_stage=payload.consultation_stage,
                top_k=payload.top_k,
            ),
        )

        if not search_result.chunks:
            answer_text = (
                "관련 근거 문서를 찾지 못했습니다. 추측으로 답변하지 않으며, "
                "아이엔 상담사에게 직접 문의하시길 권장합니다."
            )
        else:
            context = "\n".join(f"- {c.excerpt}" for c in search_result.chunks)
            answer_text = await self._generate_answer(payload.question, context, search_result.is_mock)

        await self._logs.update_fields(search_result.rag_search_log_id, {"answer_masked": truncate_snippet(answer_text, 300)})

        return RagAnswerResponse(
            answer=answer_text,
            is_mock=search_result.is_mock,
            sources=search_result.chunks,
            disclaimer=DISCLAIMER,
            rag_search_log_id=search_result.rag_search_log_id,
        )

    async def _generate_answer(self, question: str, context: str, is_mock: bool) -> str:
        if not self._client or is_mock:
            return (
                "다음 근거 문서를 참고하시길 권장합니다(자동 생성 답변이 아닌 근거 발췌):\n" + context
            )
        try:
            resp = await self._client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "너는 전세 임대차 상담 보조 도구다. 아래 근거 문서만 사용해 답하고, "
                            "근거에 없는 사실을 추측하지 마라. 법률 자문이 아닌 정보 제공 표현을 사용하라."
                        ),
                    },
                    {"role": "user", "content": f"질문: {question}\n\n근거 문서:\n{context}"},
                ],
                temperature=0.2,
                max_tokens=400,
            )
            return resp.choices[0].message.content or ""
        except (APIError, OpenAIError) as exc:
            logger.warning("OpenAI chat completion failed: %s", exc)
            raise ExternalAPIFailedError(
                "답변 생성 중 외부 API(OpenAI) 오류가 발생했습니다.",
                details={"provider": "openai", "internal_reason": "CHAT_COMPLETION_FAILED"},
            ) from exc

"""RAG 검색/답변 서비스. Atlas Vector Search($vectorSearch) + OpenAI 임베딩을 사용한다.

scripts/embed_rag_chunks.py가 이미 만들어 둔 rag_chunks 컬렉션(1,009건, text-embedding-3-large,
1024차원, 인덱스 rag_chunks_vector_index)을 그대로 사용하고 새 임베딩 파이프라인을 만들지 않는다.
"""

from __future__ import annotations

import json
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
    RagSourceResponse,
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
            sources: list[RagSourceResponse] = []
        elif self._client and not search_result.is_mock:
            answer_text, summaries = await self._generate_answer_package(payload.question, search_result.chunks)
            sources = _build_sources(search_result.chunks, summaries)
        else:
            # 오프라인/mock 경로: LLM 변환이 불가하므로 발췌를 그대로 요약 자리에 쓴다.
            answer_text = "다음 근거 문서를 참고하시길 권장합니다(자동 생성 답변이 아닌 근거 발췌):\n" + "\n".join(
                f"- {c.excerpt}" for c in search_result.chunks
            )
            sources = _build_sources(search_result.chunks, None)

        await self._logs.update_fields(search_result.rag_search_log_id, {"answer_masked": truncate_snippet(answer_text, 300)})

        return RagAnswerResponse(
            answer=answer_text,
            is_mock=search_result.is_mock,
            sources=sources,
            disclaimer=DISCLAIMER,
            rag_search_log_id=search_result.rag_search_log_id,
        )

    async def _generate_answer_package(
        self, question: str, chunks: list[RagChunkResponse]
    ) -> tuple[str, list[str] | None]:
        """답변과 사례별 요약을 한 번의 호출로 생성한다. 요약 파싱 실패 시 (원문 답변, None)을 반환한다."""
        numbered_cases = "\n\n".join(f"[사례 {i}]\n{c.excerpt}" for i, c in enumerate(chunks, start=1))
        try:
            resp = await self._client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "너는 전세 임대차 분야 상담 보조 AI다. 참고 사례(과거 상담 기록)와 "
                            "임대차보호법·전세보증금 반환 절차에 관한 일반 지식을 결합해, 질문자가 "
                            "바로 실행할 수 있는 구체적인 안내를 제공하라.\n"
                            "규칙:\n"
                            "1. 사례에 직접적인 해법이 없어도 '문서에 없다'는 식으로 회피하지 말고, "
                            "일반적으로 알려진 제도·절차(내용증명, 임차권등기명령, 지급명령, 전세보증금 "
                            "반환보증 이행청구, 주택임대차분쟁조정위원회, 소액사건심판 등)를 활용해 "
                            "단계별로 안내하라.\n"
                            "2. 확정적인 법률 판단이나 결과 보장은 하지 말고 정보 제공 어조를 유지하라.\n"
                            "3. 각 사례에 대해 이 질문과 관련된 시사점을 1~2문장으로 요약하라. 사례 원문 "
                            "표현을 그대로 옮기지 말고 답변 문장으로 바꿔 쓰고, 개인 식별 정보(이름·주소·"
                            "연락처)는 포함하지 마라.\n"
                            '4. 반드시 JSON 객체로만 출력하라: {"answer": "단계별 안내", '
                            '"source_summaries": ["사례1 요약", ...]} — source_summaries는 사례 수와 '
                            "동일하게 입력 순서를 유지하라."
                        ),
                    },
                    {"role": "user", "content": f"질문: {question}\n\n참고 사례:\n{numbered_cases}"},
                ],
                temperature=0.3,
                max_tokens=1200,
                response_format={"type": "json_object"},
            )
            raw = resp.choices[0].message.content or ""
        except (APIError, OpenAIError) as exc:
            logger.warning("OpenAI chat completion failed: %s", exc)
            raise ExternalAPIFailedError(
                "답변 생성 중 외부 API(OpenAI) 오류가 발생했습니다.",
                details={"provider": "openai", "internal_reason": "CHAT_COMPLETION_FAILED"},
            ) from exc

        try:
            parsed = json.loads(raw)
            answer_text = str(parsed.get("answer") or "").strip()
            summaries = parsed.get("source_summaries")
            if not answer_text:
                raise ValueError("empty answer")
            if not isinstance(summaries, list) or len(summaries) != len(chunks):
                summaries = None
            else:
                summaries = [str(s) for s in summaries]
            return answer_text, summaries
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("RAG answer JSON parse failed, falling back to raw text: %s", exc)
            return raw, None


def _build_sources(chunks: list[RagChunkResponse], summaries: list[str] | None) -> list[RagSourceResponse]:
    """내부 저장명(chunk_id) 대신 표시용 라벨을 붙인다. LLM 요약이 없으면 발췌를 요약 자리에 쓴다."""
    return [
        RagSourceResponse(
            label=f"참고 사례 {i}",
            topic=c.topic,
            consultation_stage=c.consultation_stage,
            region=c.region,
            summary=summaries[i - 1] if summaries else c.excerpt,
            score=c.score,
        )
        for i, c in enumerate(chunks, start=1)
    ]

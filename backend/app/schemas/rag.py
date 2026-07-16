from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RagSearchRequest(BaseModel):
    topic: str = Field(min_length=1)
    question: str | None = Field(default=None, description="임베딩 질의에 포함할 질문 원문(유사도 향상용)")
    region: str | None = None
    consultation_stage: Literal["계약전", "계약중", "사고후"] | None = None
    top_k: int = Field(default=3, ge=1, le=10)


class RagChunkResponse(BaseModel):
    chunk_id: str
    source: str | None = None
    topic: str | None = None
    consultation_stage: str | None = None
    region: str | None = None
    excerpt: str
    pii_removed: bool
    score: float | None = None


class RagSearchResponse(BaseModel):
    query: dict
    chunks: list[RagChunkResponse]
    is_mock: bool
    rag_search_log_id: str


class RagAnswerRequest(BaseModel):
    topic: str = Field(min_length=1)
    question: str = Field(min_length=1)
    region: str | None = None
    consultation_stage: Literal["계약전", "계약중", "사고후"] | None = None
    top_k: int = Field(default=3, ge=1, le=10)


class RagSourceResponse(BaseModel):
    """답변 화면용 참고 사례. 내부 저장명(chunk_id)과 상담 원문은 노출하지 않고
    LLM이 질문 맥락에 맞게 변환한 요약만 담는다."""

    label: str
    topic: str | None = None
    consultation_stage: str | None = None
    region: str | None = None
    summary: str
    score: float | None = None


class RagAnswerResponse(BaseModel):
    answer: str
    is_mock: bool
    sources: list[RagSourceResponse]
    disclaimer: str
    rag_search_log_id: str

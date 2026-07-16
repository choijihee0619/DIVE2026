from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RagSearchRequest(BaseModel):
    topic: str = Field(min_length=1)
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


class RagAnswerResponse(BaseModel):
    answer: str
    is_mock: bool
    sources: list[RagChunkResponse]
    disclaimer: str
    rag_search_log_id: str

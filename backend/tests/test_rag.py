from __future__ import annotations

import pytest

from app.core.config import get_settings
from tests.helpers import auth_headers, signup_and_login


@pytest.fixture(autouse=True)
def _force_offline_rag(monkeypatch):
    """OpenAI API 키 유무와 무관하게 테스트는 오프라인(키워드 fallback) 경로로 고정한다."""
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", "")


async def test_rag_search_validation_error(client):
    token = await signup_and_login(client, "advisor_rag@example.com", role="advisor")
    resp = await client.post(
        "/api/v1/rag/search",
        json={"topic": "보증금미반환", "top_k": 0},
        headers=auth_headers(token),
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["error_code"] == "ERROR-002"


async def test_rag_search_without_openai_key_falls_back_to_mock(client):
    token = await signup_and_login(client, "advisor_rag2@example.com", role="advisor")
    resp = await client.post(
        "/api/v1/rag/search",
        json={"topic": "보증금미반환", "region": "서울", "top_k": 3},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["is_mock"] is True
    assert isinstance(data["chunks"], list)
    assert "rag_search_log_id" in data


async def test_rag_answer_without_evidence_does_not_hallucinate(client):
    token = await signup_and_login(client, "advisor_rag3@example.com", role="advisor")
    resp = await client.post(
        "/api/v1/rag/answer",
        json={"topic": "존재하지않는주제_xyz", "question": "이 계약 위험한가요?"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "근거" in data["answer"] or "찾지 못" in data["answer"]
    assert data["disclaimer"]


async def test_rag_search_accepts_question_field(client):
    token = await signup_and_login(client, "advisor_rag4@example.com", role="advisor")
    resp = await client.post(
        "/api/v1/rag/search",
        json={"topic": "보증금미반환", "question": "보증금을 못 받고 있어요", "top_k": 3},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["is_mock"] is True

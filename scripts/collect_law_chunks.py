#!/usr/bin/env python3
"""국가법령정보센터(law.go.kr) DRF API → 법령 RAG 청크(jsonl) 생성.

대상 법령(260721 RAG 코퍼스 확장):
- 주택임대차보호법
- 전세사기피해자 지원 및 주거안정에 관한 특별법

청크 규칙: 조문 단위(제N조)를 기본으로 하고, 900자 초과 시 항 경계에서 분할한다.
각 청크 앞에 "법령명 제N조(제목)" 헤더를 붙여 검색 정확도를 높인다.

OC 파라미터는 law.go.kr OPEN API 사용자 ID다. 공개 예제 ID(test)로 동작을 확인했으며,
운영 전환 시 https://open.law.go.kr 에서 발급받은 개인 OC로 교체한다(LAW_GO_KR_OC 환경변수).

실행: backend/.venv/bin/python scripts/collect_law_chunks.py
산출: 개별수집데이터 및 API/processed/rag/rag_chunks_law_<날짜>.jsonl
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "개별수집데이터 및 API" / "processed" / "rag"
TODAY = date.today().strftime("%y%m%d")
OC = os.environ.get("LAW_GO_KR_OC", "test")
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}

# (법령명, chunk_id 접두어, topic, consultation_stage)
LAWS = [
    ("주택임대차보호법", "law_jt", "주택임대차보호법", "법령 근거"),
    ("전세사기피해자 지원 및 주거안정에 관한 특별법", "law_sp", "전세사기특별법", "법령 근거"),
]

MAX_CHUNK = 900


def _listify(v) -> list:
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def _ho_text(ho: dict) -> str:
    parts = [str(ho.get("호내용", "")).strip()]
    for mok in _listify(ho.get("목")):
        content = mok.get("목내용")
        for line in _listify(content):
            parts.append(str(line).strip())
    return "\n".join(p for p in parts if p)


def _hang_text(hang: dict) -> str:
    parts = [str(hang.get("항내용", "")).strip()]
    for ho in _listify(hang.get("호")):
        parts.append(_ho_text(ho))
    return "\n".join(p for p in parts if p)


def article_blocks(article: dict) -> tuple[str, list[str]]:
    """조문 하나를 (헤더, 본문 블록 리스트)로 변환한다. 블록은 항 단위."""
    no = str(article.get("조문번호", "")).strip()
    branch = str(article.get("조문가지번호", "") or "").strip()
    title = str(article.get("조문제목", "") or "").strip()
    label = f"제{no}조" + (f"의{branch}" if branch else "")
    header = f"{label}({title})" if title else label
    blocks: list[str] = []
    content = str(article.get("조문내용", "") or "").strip()
    if content:
        blocks.append(content)
    for hang in _listify(article.get("항")):
        text = _hang_text(hang)
        if text:
            blocks.append(text)
    return header, blocks


def chunk_article(law_name: str, header: str, blocks: list[str]) -> list[str]:
    """조문을 900자 이내 청크로 묶는다. 초과 시 항 경계 분할, 각 청크에 헤더를 반복한다."""
    prefix = f"[{law_name} {header}]\n"
    chunks: list[str] = []
    cur = ""
    for block in blocks:
        candidate = (cur + "\n" + block).strip() if cur else block
        if len(prefix) + len(candidate) <= MAX_CHUNK:
            cur = candidate
            continue
        if cur:
            chunks.append(prefix + cur)
        # 단일 항이 자체로 초과하면 강제 분할
        while len(prefix) + len(block) > MAX_CHUNK:
            cut = MAX_CHUNK - len(prefix)
            chunks.append(prefix + block[:cut])
            block = block[cut - 100:]  # overlap 100자
        cur = block
    if cur.strip():
        chunks.append(prefix + cur)
    return chunks


def fetch_law(name: str) -> dict:
    r = requests.get(
        "https://www.law.go.kr/DRF/lawService.do",
        params={"OC": OC, "target": "law", "LM": name, "type": "JSON"},
        headers=UA,
        timeout=60,
    )
    r.raise_for_status()
    body = r.json()
    if "법령" not in body:
        raise RuntimeError(f"{name}: 법령 응답 아님 — {str(body)[:200]}")
    return body["법령"]


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"rag_chunks_law_{TODAY}.jsonl"
    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for name, prefix, topic, stage in LAWS:
        law = fetch_law(name)
        info = law.get("기본정보", {})
        effective = str(info.get("시행일자", ""))
        promulgated = str(info.get("공포일자", ""))
        doc_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"https://www.law.go.kr/법령/{name}"))
        articles = _listify(law.get("조문", {}).get("조문단위"))
        n_chunks = 0
        for article in articles:
            if str(article.get("조문여부", "")) != "조문":
                continue  # 장·절 제목 등은 제외
            header, blocks = article_blocks(article)
            if not blocks:
                continue
            article_key = header.split("(")[0].replace("제", "").replace("조", "_").replace("의", "b")
            for j, chunk in enumerate(chunk_article(name, header, blocks)):
                rows.append({
                    "chunk_id": f"{prefix}_{article_key}{j}",
                    "doc_id": doc_id,
                    "source": "law",
                    "topic": topic,
                    "consultation_stage": stage,
                    "region_sido": None,
                    "region_sigungu": None,
                    "region_code": None,
                    "text": chunk,
                    "metadata": {
                        "law_name": name,
                        "article": header,
                        "effective_date": effective,
                        "promulgation_date": promulgated,
                        "url": f"https://www.law.go.kr/법령/{name}",
                        "crawled_at": now,
                        "license": "국가법령정보센터 OPEN API (법령정보 — 저작권 제한 없음)",
                        "pii_removed": True,
                        "pii_review_status": "법령 조문으로 개인정보 미포함",
                    },
                })
                n_chunks += 1
        print(f"[OK] {name}: 조문 {len(articles)}개 → {n_chunks}청크 (시행 {effective})")
    with out_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"\n총 {len(rows)}청크 → {out_path.relative_to(ROOT)}")
    return 0 if rows else 1


if __name__ == "__main__":
    sys.exit(main())

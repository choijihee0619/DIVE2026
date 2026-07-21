#!/usr/bin/env python3
"""HUG 안심전세포털 공개 콘텐츠 크롤링 → RAG 청크(jsonl) 생성.

대상: 전세사기 개념·유형별 사례(8p)·계약 단계별 유의사항(4p)·보증가입·컨설팅·
피해지원 프로그램·경공매 지원/원스톱 서비스(특별법) 등 공식 안내 페이지.

산출: 개별수집데이터 및 API/processed/rag/rag_chunks_khug_<날짜>.jsonl
청크 규칙: 500~900자, overlap 약 120자 (processed/rag/README.md 규칙 준수)

실행: backend/.venv/bin/python scripts/crawl_khug_portal.py
"""

from __future__ import annotations

import json
import re
import sys
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "개별수집데이터 및 API" / "processed" / "rag"
TODAY = date.today().strftime("%y%m%d")
BASE = "https://www.khug.or.kr/jeonse/web/"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}

# (경로, topic, consultation_stage)
PAGES = [
    ("s01/s010101.jsp", "전세사기 개념", "계약 전 검토"),
    ("s02/s020101.jsp", "전세사기 유형·대처", "개요"),
    ("s02/s020201.jsp", "전세사기 유형·대처", "집 고를 때"),
    ("s02/s020301.jsp", "전세사기 유형·대처", "임대인 확인할 때"),
    ("s02/s020401.jsp", "전세사기 유형·대처", "계약서 작성할 때"),
    ("s02/s020501.jsp", "전세사기 유형·대처", "계약한 직후"),
    ("s02/s020601.jsp", "전세사기 유형·대처", "입주한 이후"),
    ("s02/s020701.jsp", "전세사기 유형·대처", "계약기간이 끝난 후"),
    ("s02/s020801.jsp", "전세사기 유형·대처", "전세대출·보증사기"),
    ("s03/s030101.jsp", "계약 단계별 유의사항", "계약 체결 전"),
    ("s03/s030201.jsp", "계약 단계별 유의사항", "계약 체결"),
    ("s03/s030301.jsp", "계약 단계별 유의사항", "계약 체결 후"),
    ("s03/s030401.jsp", "계약 단계별 유의사항", "계약 종료·갱신"),
    ("s04/s040005.jsp", "안전계약 컨설팅", "계약 전 검토"),
    ("s04/s040201.jsp", "보증가입 안내", "보증 가입"),
    ("s01/s010001.jsp", "전세피해지원센터", "피해 지원"),
    ("s01/s010002.jsp", "피해지원 프로그램", "피해 지원"),
    ("s04/s040408.jsp", "경공매 지원서비스", "사고 후 회수"),
    ("s04/s040407.jsp", "경공매 지원서비스", "사고 후 회수"),
    ("s04/s040001.jsp", "경공매 원스톱 서비스(특별법)", "사고 후 회수"),
    ("s04/s040002.jsp", "경공매 유예·정지(특별법)", "사고 후 회수"),
    ("s04/s040003.jsp", "조세채권 안분(특별법)", "사고 후 회수"),
    ("s04/s040004.jsp", "우선매수권 양도(특별법)", "사고 후 회수"),
    # 260721 사이트맵(s06/s060101.jsp) 대조로 확인된 누락 페이지 추가
    ("s05/s050201.jsp", "자주하는 질문(FAQ)", "개요"),
    ("s05/s050201.jsp?currentPage=2", "자주하는 질문(FAQ)", "개요"),
    ("s01/s010303.jsp", "피해확인서 안내·신청", "피해 지원"),
    ("s01/s010320.jsp", "상습 채무불이행자 명단공개 제도", "임대인 확인할 때"),
    ("s04/s040501.jsp", "상속재산관리인 선임지원", "피해 지원"),
    ("s05/s050501.jsp", "도움 받을 수 있는 곳", "피해 지원"),
    ("s05/s050601.jsp", "보증료 지원사업(국토부)", "보증 가입"),
    ("s07/s070101.jsp", "든든전세주택 소개", "피해 지원"),
    ("s07/s070107.jsp", "든든전세주택 협의매입(임대인)", "피해 지원"),
    ("s08/s080101.jsp", "HUG 인정 감정평가", "보증 가입"),
]

# 본문 뒤에 붙는 공통 보일러플레이트 시작 문구
CUT_MARKERS = ["이 페이지에서 제공하는 정보에 만족하셨습니까", "주택정보포털 소개"]
MIN_CHUNK, MAX_CHUNK, OVERLAP = 500, 900, 120


def fetch_text(path: str) -> tuple[str, str]:
    r = requests.get(BASE + path, headers=UA, timeout=30)
    r.raise_for_status()
    html = r.content.decode("euc-kr", errors="replace")
    soup = BeautifulSoup(html, "html.parser")
    main = soup.select_one(".sub-content-wrap") or soup.body
    for tag in main.select("script, style, noscript"):
        tag.decompose()
    title_el = main.select_one("h3.h3-tit") or soup.select_one("h3")
    title = title_el.get_text(strip=True) if title_el else path
    text = main.get_text("\n")
    for marker in CUT_MARKERS:
        idx = text.find(marker)
        if idx > 0:
            text = text[:idx]
    lines = [re.sub(r"[ \t ]+", " ", ln).strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    return title, "\n".join(lines)


def chunk_text(text: str) -> list[str]:
    paras = [p for p in re.split(r"\n{1,}", text) if p.strip()]
    chunks: list[str] = []
    cur = ""
    for p in paras:
        candidate = (cur + "\n" + p).strip() if cur else p
        if len(candidate) <= MAX_CHUNK:
            cur = candidate
            continue
        if cur:
            chunks.append(cur)
            cur = (cur[-OVERLAP:] + "\n" + p).strip()
            while len(cur) > MAX_CHUNK:
                chunks.append(cur[:MAX_CHUNK])
                cur = cur[MAX_CHUNK - OVERLAP:]
        else:
            while len(p) > MAX_CHUNK:
                chunks.append(p[:MAX_CHUNK])
                p = p[MAX_CHUNK - OVERLAP:]
            cur = p
    if cur.strip():
        if chunks and len(cur) < MIN_CHUNK // 2:
            chunks[-1] = (chunks[-1] + "\n" + cur)[: MAX_CHUNK + OVERLAP]
        else:
            chunks.append(cur)
    return chunks


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"rag_chunks_khug_{TODAY}.jsonl"
    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for i, (path, topic, stage) in enumerate(PAGES, start=1):
        try:
            title, text = fetch_text(path)
        except Exception as exc:  # noqa: BLE001
            print(f"[ERR] {path}: {exc}")
            continue
        if len(text) < 200:
            print(f"[SKIP] {path}: 본문 {len(text)}자 (내용 부족)")
            continue
        doc_id = str(uuid.uuid5(uuid.NAMESPACE_URL, BASE + path))
        chunks = chunk_text(text)
        for j, chunk in enumerate(chunks):
            rows.append({
                "chunk_id": f"khug_{i:04d}_{j}",
                "doc_id": doc_id,
                "source": "khug_portal",
                "topic": topic,
                "consultation_stage": stage,
                "region_sido": None,
                "region_sigungu": None,
                "region_code": None,
                "text": chunk,
                "metadata": {
                    "url": BASE + path,
                    "page_title": title,
                    "crawled_at": now,
                    "license": "KHUG 안심전세포털 공개자료(공공데이터법 준수, 출처 표기)",
                    "pii_removed": True,
                    "pii_review_status": "공공 공개 안내자료로 개인정보 미포함",
                },
            })
        print(f"[OK] {path} ({title}): {len(text):,}자 → {len(chunks)}청크")
    with out_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"\n총 {len(rows)}청크 → {out_path.relative_to(ROOT)}")
    return 0 if rows else 1


if __name__ == "__main__":
    sys.exit(main())

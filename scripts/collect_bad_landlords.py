#!/usr/bin/env python3
"""안심전세포털 악성임대인 공개명단 수집.

법적 근거가 있는 공개 정보:
- 상습 채무불이행자 (주택도시기금법 §34의5, s010321.jsp)
- 보증금 미반환 임대사업자 (민간임대주택법 §60의2, s010503.jsp)

산출:
- raw/khug_disclosure/raw_khug_habitual_defaulters_<날짜>.csv
- raw/khug_disclosure/raw_khug_nonreturn_lessors_<날짜>.csv
- processed/khug_disclosure/bad_landlords_<날짜>.csv (두 명단 통합·시도 파싱)

주의: 본 명단은 임차인 보호 목적의 법정 공개 정보다. 서비스 내 임대인 위험신호
매칭 용도로만 사용하고, 명예훼손 소지가 있는 2차 가공·유포는 금지한다.

실행: backend/.venv/bin/python scripts/collect_bad_landlords.py
"""

from __future__ import annotations

import csv
import re
import sys
import time
from datetime import date
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "개별수집데이터 및 API" / "raw" / "khug_disclosure"
PROC = ROOT / "개별수집데이터 및 API" / "processed" / "khug_disclosure"
TODAY = date.today().strftime("%Y%m%d")
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}

SOURCES = {
    "habitual_defaulters": {
        "url": "https://www.khug.or.kr/jeonse/web/s01/s010321.jsp",
        "cols": ["name", "age", "addr", "deposit_debt_won", "due_date",
                 "default_days", "hug_payout_date", "recourse_debt_won",
                 "enforcement_cnt", "base_date"],
        "legal_basis": "주택도시기금법 제34조의5",
    },
    "nonreturn_lessors": {
        "url": "https://www.khug.or.kr/jeonse/web/s01/s010503.jsp",
        "cols": ["name", "reg_no", "addr", "cancel_reason", "cancel_date", "base_date"],
        "legal_basis": "민간임대주택법 제60조의2",
    },
}

SIDO_MAP = {
    "서울": "서울", "부산": "부산", "대구": "대구", "인천": "인천", "광주": "광주",
    "대전": "대전", "울산": "울산", "세종": "세종", "경기": "경기", "강원": "강원",
    "충북": "충북", "충남": "충남", "전북": "전북", "전남": "전남", "경북": "경북",
    "경남": "경남", "제주": "제주",
    "서울특별시": "서울", "부산광역시": "부산", "대구광역시": "대구", "인천광역시": "인천",
    "광주광역시": "광주", "대전광역시": "대전", "울산광역시": "울산", "세종특별자치시": "세종",
    "경기도": "경기", "강원도": "강원", "강원특별자치도": "강원", "충청북도": "충북",
    "충청남도": "충남", "전라북도": "전북", "전북특별자치도": "전북", "전라남도": "전남",
    "경상북도": "경북", "경상남도": "경남", "제주특별자치도": "제주",
}


def fetch_page(url: str, page: int) -> str:
    r = requests.post(f"{url}?cur_page={page}", headers=UA,
                      data={"CUST_NM": "", "cur_page": str(page)}, timeout=30)
    r.raise_for_status()
    return r.content.decode("euc-kr", errors="replace")


def parse_rows(html: str, ncols: int) -> list[list[str]]:
    tables = re.findall(r"<table[^>]*>.*?</table>", html, re.S)
    out = []
    for t in tables:
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", t, re.S):
            cells = [re.sub(r"<[^>]+>|&nbsp;|\s+", " ", c).strip()
                     for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
            if len(cells) == ncols and any(cells):
                out.append(cells)
    return out


def max_page(html: str) -> int:
    pages = [int(x) for x in re.findall(r"page\((\d+)\)", html)]
    return max(pages) if pages else 1


def sido_from_addr(addr: str) -> str:
    token = addr.split(" ")[0] if addr else ""
    return SIDO_MAP.get(token, "")


def collect(key: str) -> list[dict]:
    conf = SOURCES[key]
    first = fetch_page(conf["url"], 1)
    last = max_page(first)
    rows = parse_rows(first, len(conf["cols"]))
    for p in range(2, last + 1):
        rows += parse_rows(fetch_page(conf["url"], p), len(conf["cols"]))
        if p % 20 == 0:
            print(f"  {key}: {p}/{last} 페이지")
        time.sleep(0.2)
    records = [dict(zip(conf["cols"], r)) for r in rows]
    print(f"[OK] {key}: {last}페이지 → {len(records)}건")
    return records


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    PROC.mkdir(parents=True, exist_ok=True)
    merged = []
    for key, conf in SOURCES.items():
        records = collect(key)
        raw_path = RAW / f"raw_khug_{key}_{TODAY}.csv"
        with raw_path.open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=conf["cols"])
            w.writeheader()
            w.writerows(records)
        print(f"     → {raw_path.relative_to(ROOT)}")
        for r in records:
            merged.append({
                "list_type": key,
                "legal_basis": conf["legal_basis"],
                "name": r.get("name", ""),
                "age": r.get("age", ""),
                "addr": r.get("addr", ""),
                "sido": sido_from_addr(r.get("addr", "")),
                "amount_won": (r.get("recourse_debt_won") or r.get("deposit_debt_won") or "").replace(",", ""),
                "base_date": r.get("base_date", ""),
                "reg_no": r.get("reg_no", ""),
                "cancel_date": r.get("cancel_date", ""),
                "source_url": conf["url"],
            })
    proc_path = PROC / f"bad_landlords_{TODAY}.csv"
    with proc_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(merged[0].keys()))
        w.writeheader()
        w.writerows(merged)
    print(f"\n통합 {len(merged)}건 → {proc_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""HOUSTA(HUG 빅데이터 개방 포털) 공공데이터 파일 수집.

KHUG '전세 및 임대보증' 목록의 각 데이터셋 상세 페이지에서 data.go.kr 파일링크를 찾아
원본 파일을 `개별수집데이터 및 API/raw/housta/`에 내려받고,
수집 결과를 `metadata/housta_collect_<날짜>.json`에 기록한다.

실행: backend/.venv/bin/python scripts/collect_housta_data.py
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "개별수집데이터 및 API" / "raw" / "housta"
META_DIR = ROOT / "개별수집데이터 및 API" / "metadata"
TODAY = date.today().strftime("%Y%m%d")

KHUG_DETAIL = "https://www.khug.or.kr/houstar/web/p03/01/p030105.jsp?mode=S&currentPage=1&articleId={aid}"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}

# articleId -> (slug, 설명)
TARGETS = {
    34712: ("지역별_전세보증_사고현황", "시도·시군구별 최근 3개월 평균 사고건수·금액·사고율(%)"),
    34707: ("전세보증_발급현황", "전세보증금반환보증 발급현황(정상 모수)"),
    34706: ("전세보증_상세현황", "전세보증금반환보증 상세현황"),
    37002: ("서울_연도별_사고_대위변제", "연도별 서울특별시 사고 및 대위변제 현황"),
    35499: ("경공매지원_피해주택_소재지", "경공매지원서비스 신청자의 전세사기피해주택 소재지(시군구)"),
    34713: ("안심대출_신청_사고건수", "전세금안심대출보증 신청건수·보증사고건수 및 금액"),
    34711: ("안심대출_발급현황", "전세금안심대출보증 발급현황"),
    36986: ("임대보증_법인_발급현황", "임대보증금보증(사용검사 후_법인) 발급현황"),
    36982: ("임대보증_개인_발급현황", "개인임대사업자 임대보증금보증 발급현황"),
    36998: ("전세관련_현황", "전세관련 현황"),
}


def khug_detail_html(aid: int) -> str:
    r = requests.get(KHUG_DETAIL.format(aid=aid), headers=UA, timeout=30)
    r.raise_for_status()
    return r.content.decode("euc-kr", errors="replace")


def find_datago_url(html: str) -> str | None:
    m = re.search(r"https://www\.data\.go\.kr/data/(\d+)/fileData\.do", html)
    return m.group(0) if m else None


def find_download_params(datago_url: str, session: requests.Session) -> tuple[str, str] | None:
    r = session.get(datago_url, headers=UA, timeout=30)
    r.raise_for_status()
    m = re.search(r"fileDownload\.do\?atchFileId=([A-Z0-9_]+)&fileDetailSn=(\d+)", r.text)
    return (m.group(1), m.group(2)) if m else None


def download(atch: str, sn: str, referer: str, session: requests.Session) -> tuple[bytes, str]:
    url = f"https://www.data.go.kr/cmm/cmm/fileDownload.do?atchFileId={atch}&fileDetailSn={sn}&insertDataPrcus=N"
    r = session.get(url, headers={**UA, "Referer": referer}, timeout=60)
    r.raise_for_status()
    cd = r.headers.get("Content-Disposition", "")
    m = re.search(r'filename="?([^";]+)"?', cd)
    orig_name = m.group(1) if m else "download.bin"
    return r.content, orig_name


def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    META_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    results = []
    for aid, (slug, desc) in TARGETS.items():
        entry = {"articleId": aid, "slug": slug, "desc": desc}
        try:
            html = khug_detail_html(aid)
            datago = find_datago_url(html)
            entry["datago_url"] = datago
            if not datago:
                entry["status"] = "no_datago_link"
                results.append(entry)
                print(f"[SKIP] {slug}: data.go.kr 링크 없음")
                continue
            params = find_download_params(datago, session)
            if not params:
                entry["status"] = "no_download_params"
                results.append(entry)
                print(f"[SKIP] {slug}: 다운로드 파라미터 없음(로그인 필요 가능)")
                continue
            content, orig_name = download(*params, referer=datago, session=session)
            ext = Path(orig_name).suffix or ".bin"
            out = RAW_DIR / f"raw_housta_{TODAY}_{slug}{ext}"
            out.write_bytes(content)
            entry.update({
                "status": "ok",
                "orig_filename": orig_name,
                "saved": str(out.relative_to(ROOT)),
                "bytes": len(content),
            })
            print(f"[OK]   {slug}: {orig_name} ({len(content):,}B)")
        except Exception as exc:  # noqa: BLE001 - 수집 스크립트는 계속 진행
            entry["status"] = f"error: {exc}"
            print(f"[ERR]  {slug}: {exc}")
        results.append(entry)

    meta_path = META_DIR / f"housta_collect_{TODAY}.json"
    meta_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = sum(1 for r in results if r.get("status") == "ok")
    print(f"\n{ok}/{len(results)} 성공 → {meta_path.relative_to(ROOT)}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""국토부 실거래가(RTMS) 전월세 4종 API 수집 → 정상 대조군(전세계약) 표본 생성.

정상대조군 확보방안(docs/정상대조군_확보방안_260721.md) A안 착수용.
전월세 신고 건별 데이터의 절대다수는 정상 계약이므로, 이를 사고군에 대한
유사 정상군(pseudo-controls)으로 층화표집한다.

수집 범위: 대표 시군구(LAWD_CD) × 최근 N개월 × 주택유형 4종.
전세만 사용(월세 0 & 보증금>0). 결과는 공통 스키마로 정규화해 CSV 저장.

키: backend/.env DATA_GO_KR_API_KEY (전월세 4종 활용신청 완료 2026-07-21).
실행: backend/.venv/bin/python scripts/collect_rtms_rent.py
산출: 개별수집데이터 및 API/processed/control/rtms_jeonse_controls_<날짜>.csv
"""

from __future__ import annotations

import re
import sys
import time
from datetime import date
from pathlib import Path
from xml.etree import ElementTree as ET

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / "backend" / ".env"
OUT_DIR = ROOT / "개별수집데이터 및 API" / "processed" / "control"
RAW_DIR = ROOT / "개별수집데이터 및 API" / "raw" / "rtms_rent"
TODAY = date.today().strftime("%y%m%d")

# 전월세 4종 엔드포인트 (주택유형은 엔드포인트로 구분)
ENDPOINTS = {
    "아파트": "RTMSDataSvcAptRent/getRTMSDataSvcAptRent",
    "연립다세대": "RTMSDataSvcRHRent/getRTMSDataSvcRHRent",
    "단독다가구": "RTMSDataSvcSHRent/getRTMSDataSvcSHRent",
    "오피스텔": "RTMSDataSvcOffiRent/getRTMSDataSvcOffiRent",
}

# 대표 시군구 LAWD_CD(5자리) — 전세사기 다발지·거래량 상위·저위험 지역 혼합(층화표집).
# region_group은 발표용 라벨(참고). 시도는 LAWD 앞 2자리로 파생.
LAWD_STRATA = [
    ("11500", "서울 강서구", "고위험"),   # 화곡동 다세대 전세사기 다발
    ("11620", "서울 관악구", "고위험"),
    ("11680", "서울 강남구", "저위험"),
    ("11440", "서울 마포구", "중위험"),
    ("28177", "인천 미추홀구", "고위험"),  # 전세사기 최다 지역
    ("28245", "인천 서구", "중위험"),
    ("41190", "경기 부천시", "고위험"),
    ("41590", "경기 화성시", "중위험"),
    ("41135", "경기 성남분당", "저위험"),
    ("26230", "부산 부산진구", "중위험"),
    ("26440", "부산 강서구", "저위험"),
    ("27290", "대구 달서구", "중위험"),
    ("30200", "대전 유성구", "저위험"),
    ("48123", "경남 창원성산", "저위험"),
    ("47190", "경북 포항북구", "고위험"),
    ("44130", "충남 천안서북", "중위험"),
]

# 최근 5개월(수집 시점 기준 여유 두고 2025 하반기)
DEAL_YMDS = ["202506", "202505", "202504", "202503", "202502"]

SIDO_BY_LAWD2 = {
    "11": "서울특별시", "26": "부산광역시", "27": "대구광역시", "28": "인천광역시",
    "29": "광주광역시", "30": "대전광역시", "31": "울산광역시", "36": "세종특별자치시",
    "41": "경기도", "43": "충청북도", "44": "충청남도", "46": "전라남도", "47": "경상북도",
    "48": "경상남도", "50": "제주특별자치도", "51": "강원특별자치도", "52": "전북특별자치도",
}


def load_key() -> str:
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        m = re.match(r"DATA_GO_KR_API_KEY=(\S+)", line.strip())
        if m:
            return m.group(1)
    raise SystemExit("DATA_GO_KR_API_KEY가 backend/.env에 없습니다.")


def _to_int(text: str | None) -> int | None:
    if text is None:
        return None
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None


def parse_items(xml_text: str, housing_type: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    rows = []
    for item in root.iter("item"):
        def g(tag: str) -> str | None:
            el = item.find(tag)
            return el.text.strip() if el is not None and el.text else None

        deposit_manwon = _to_int(g("deposit"))          # 보증금(만원)
        monthly_manwon = _to_int(g("monthlyRent"))       # 월세(만원)
        if deposit_manwon is None:
            continue
        rows.append({
            "housing_type": housing_type,
            "deposit_amount": deposit_manwon * 10000 if deposit_manwon else 0,
            "monthly_rent": (monthly_manwon or 0) * 10000,
            "area_m2": _try_float(g("excluUseAr") or g("totalFloorAr")),
            "build_year": _to_int(g("buildYear")),
            "deal_year": _to_int(g("dealYear")),
            "deal_month": _to_int(g("dealMonth")),
            "umd_nm": g("umdNm"),
            "jibun": g("jibun"),
            "rent_gbn": g("rgstDate") and "신규" or None,  # 계약구분 없으면 None
            "contract_type": g("contractType"),
        })
    return rows


def _try_float(text: str | None) -> float | None:
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def main() -> int:
    key = load_key()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    all_rows: list[dict] = []
    calls = 0
    for lawd, label, group in LAWD_STRATA:
        sido = SIDO_BY_LAWD2.get(lawd[:2], "기타")
        for ymd in DEAL_YMDS:
            for htype, ep in ENDPOINTS.items():
                url = f"https://apis.data.go.kr/1613000/{ep}"
                params = {
                    "serviceKey": key,
                    "LAWD_CD": lawd,
                    "DEAL_YMD": ymd,
                    "pageNo": "1",
                    "numOfRows": "300",
                }
                try:
                    r = requests.get(url, params=params, timeout=30)
                    calls += 1
                    if r.status_code != 200:
                        print(f"[WARN] {label} {ymd} {htype}: HTTP {r.status_code}")
                        continue
                    rows = parse_items(r.text, htype)
                except Exception as exc:  # noqa: BLE001
                    print(f"[ERR] {label} {ymd} {htype}: {exc}")
                    continue
                for row in rows:
                    row.update({"lawd_cd": lawd, "region_label": label,
                                "region_group": group, "sido": sido})
                all_rows.extend(rows)
                time.sleep(0.1)  # 공공데이터포털 예의상 소폭 대기
        print(f"[OK] {label}({group}) 누적 {len(all_rows):,}건")

    df = pd.DataFrame(all_rows)
    # 전세만: 월세 0 & 보증금 > 0
    jeonse = df[(df["monthly_rent"] == 0) & (df["deposit_amount"] > 0)].copy()
    jeonse["is_accident"] = 0  # 정상 대조군 라벨
    out_path = OUT_DIR / f"rtms_jeonse_controls_{TODAY}.csv"
    jeonse.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"\nAPI 호출 {calls}회 · 수집 {len(df):,}건 중 전세 {len(jeonse):,}건")
    print(f"주택유형 분포: {jeonse['housing_type'].value_counts().to_dict()}")
    print(f"→ {out_path.relative_to(ROOT)}")
    return 0 if len(jeonse) else 1


if __name__ == "__main__":
    sys.exit(main())

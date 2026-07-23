#!/usr/bin/env python3
"""국토부 실거래가(RTMS) 전월세 4종 API 수집 → PU 미라벨 전세계약 표본 생성.

발제사 사고 데이터와 RTMS 사이에 공통 계약키가 없으므로 개별 사고를 제외할 수 없다.
따라서 RTMS 행을 확정 정상(y=0)이 아니라 사고 여부 미확인 미라벨(s=0)로 수집한다.

수집 범위: 대표 시군구(LAWD_CD) × 최근 N개월 × 주택유형 4종.
전세만 사용(월세 0 & 보증금>0). 결과는 공통 스키마로 정규화해 CSV 저장.

키: backend/.env DATA_GO_KR_API_KEY (전월세 4종 활용신청 완료 2026-07-21).
실행: backend/.venv/bin/python scripts/collect_rtms_rent.py
산출: 개별수집데이터 및 API/processed/control/
      rtms_jeonse_unlabeled_<시작월>_<종료월>_<실행시각>.csv + .manifest.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import date, datetime
from pathlib import Path
from xml.etree import ElementTree as ET

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / "backend" / ".env"
OUT_DIR = ROOT / "개별수집데이터 및 API" / "processed" / "control"
RAW_DIR = ROOT / "개별수집데이터 및 API" / "raw" / "rtms_rent"
RUN_STAMP = datetime.now().strftime("%y%m%dT%H%M%S")

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
    ("28245", "인천 계양구", "중위험"),
    ("41190", "경기 부천시", "고위험"),
    ("41590", "경기 화성시", "중위험"),
    ("41135", "경기 성남분당", "저위험"),
    ("26230", "부산 부산진구", "중위험"),
    ("26440", "부산 강서구", "저위험"),
    ("27290", "대구 달서구", "중위험"),
    ("30200", "대전 유성구", "저위험"),
    ("36110", "세종특별자치시", "중위험"),
    ("48123", "경남 창원성산", "저위험"),
    ("47190", "경북 구미시", "고위험"),
    ("44130", "충남 천안서북", "중위험"),
]

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
            # 누락 월세를 0으로 간주하면 미확인 거래가 전세로 섞이므로 None을 보존한다.
            "monthly_rent": (
                monthly_manwon * 10000 if monthly_manwon is not None else None
            ),
            "area_m2": _try_float(g("excluUseAr") or g("totalFloorAr")),
            "build_year": _to_int(g("buildYear")),
            "deal_year": _to_int(g("dealYear")),
            "deal_month": _to_int(g("dealMonth")),
            "umd_nm": g("umdNm"),
            "jibun": g("jibun"),
            "rent_gbn": g("contractType"),
            "contract_type": g("contractType"),
            "registration_date": g("rgstDate"),
        })
    return rows


def parse_total_count(xml_text: str) -> int | None:
    """공공데이터포털 응답의 전체 행 수. 없으면 현재 page만 사용한다."""
    root = ET.fromstring(xml_text)
    element = root.find(".//totalCount")
    return _to_int(element.text if element is not None else None)


def parse_item_count(xml_text: str) -> int:
    return len(list(ET.fromstring(xml_text).iter("item")))


def parse_api_result(xml_text: str) -> tuple[str | None, str | None]:
    root = ET.fromstring(xml_text)
    code = root.findtext(".//resultCode")
    message = root.findtext(".//resultMsg")
    return (code.strip() if code else None, message.strip() if message else None)


def _try_float(text: str | None) -> float | None:
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _shift_month(yyyymm: str, offset: int) -> str:
    year, month = int(yyyymm[:4]), int(yyyymm[4:])
    index = year * 12 + (month - 1) + offset
    return f"{index // 12:04d}{index % 12 + 1:02d}"


def _month_range(start: str, end: str) -> list[str]:
    if not re.fullmatch(r"\d{6}", start) or not re.fullmatch(r"\d{6}", end):
        raise SystemExit("기준월은 YYYYMM 형식이어야 합니다.")
    if not (1 <= int(start[4:]) <= 12 and 1 <= int(end[4:]) <= 12):
        raise SystemExit("기준월의 월은 01~12여야 합니다.")
    months: list[str] = []
    cursor = start
    while cursor <= end:
        months.append(cursor)
        cursor = _shift_month(cursor, 1)
    if not months:
        raise SystemExit("--from-ym은 --to-ym보다 늦을 수 없습니다.")
    return months


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RTMS 전세 미라벨 U 표본 수집")
    parser.add_argument("--from-ym", help="수집 시작월(YYYYMM); --to-ym과 함께 사용")
    parser.add_argument("--to-ym", help="수집 종료월(YYYYMM); --from-ym과 함께 사용")
    parser.add_argument(
        "--months", type=int, default=5, help="기본 수집 개월 수(default: 5)"
    )
    parser.add_argument(
        "--lag-months",
        type=int,
        default=2,
        help="미지정 시 현재월로부터 종료월 지연(default: 2)",
    )
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="실패 셀이 있어도 감사용 부분 CSV 저장(모델 학습에는 사용 불가)",
    )
    return parser.parse_args()


def resolve_months(args: argparse.Namespace) -> list[str]:
    if bool(args.from_ym) != bool(args.to_ym):
        raise SystemExit("--from-ym과 --to-ym은 함께 지정해야 합니다.")
    if args.months < 1 or args.lag_months < 0:
        raise SystemExit("--months는 1 이상, --lag-months는 0 이상이어야 합니다.")
    if args.from_ym and args.to_ym:
        return _month_range(args.from_ym, args.to_ym)
    current = date.today().strftime("%Y%m")
    end = _shift_month(current, -args.lag_months)
    start = _shift_month(end, -(args.months - 1))
    return _month_range(start, end)


def main() -> int:
    args = parse_args()
    deal_ymds = resolve_months(args)
    key = load_key()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    all_rows: list[dict] = []
    cells: list[dict] = []
    calls = 0
    for lawd, label, group in LAWD_STRATA:
        sido = SIDO_BY_LAWD2.get(lawd[:2], "기타")
        for ymd in deal_ymds:
            for htype, ep in ENDPOINTS.items():
                url = f"https://apis.data.go.kr/1613000/{ep}"
                rows: list[dict] = []
                page = 1
                page_size = 1000
                total_count: int | None = None
                received_item_count = 0
                status = "complete"
                error: str | None = None
                while True:
                    params = {
                        "serviceKey": key,
                        "LAWD_CD": lawd,
                        "DEAL_YMD": ymd,
                        "pageNo": str(page),
                        "numOfRows": str(page_size),
                    }
                    try:
                        r = requests.get(url, params=params, timeout=30)
                        calls += 1
                        raw_path = RAW_DIR / (
                            f"{RUN_STAMP}_{lawd}_{ymd}_{htype}_page{page}.xml"
                        )
                        raw_path.write_text(r.text, encoding="utf-8")
                        if r.status_code != 200:
                            raise RuntimeError(f"HTTP {r.status_code}")
                        result_code, result_message = parse_api_result(r.text)
                        if result_code not in (None, "0", "00", "000"):
                            raise RuntimeError(
                                f"API {result_code}: {result_message or 'unknown error'}"
                            )
                        page_rows = parse_items(r.text, htype)
                        page_item_count = parse_item_count(r.text)
                        page_total = parse_total_count(r.text)
                        if total_count is None:
                            total_count = page_total
                    except Exception as exc:  # noqa: BLE001
                        print(f"[ERR] {label} {ymd} {htype} page={page}: {exc}")
                        status = "failed"
                        error = str(exc)
                        break
                    rows.extend(page_rows)
                    received_item_count += page_item_count
                    if total_count is None:
                        status = "incomplete"
                        error = "totalCount missing"
                        break
                    if received_item_count >= total_count:
                        break
                    if page_item_count == 0:
                        status = "incomplete"
                        error = (
                            f"empty page before totalCount "
                            f"({received_item_count}/{total_count})"
                        )
                        break
                    page += 1
                if status == "complete" and (
                    total_count is None or received_item_count < total_count
                ):
                    status = "incomplete"
                    error = f"received {received_item_count}/{total_count}"
                for row in rows:
                    row.update(
                        {
                            "lawd_cd": lawd,
                            "region_label": label,
                            "region_group": group,
                            "sido": sido,
                            "collection_cell_status": status,
                        }
                    )
                if status == "complete" or args.allow_partial:
                    all_rows.extend(rows)
                cells.append(
                    {
                        "lawd_cd": lawd,
                        "region_label": label,
                        "deal_ym": ymd,
                        "housing_type": htype,
                        "status": status,
                        "total_count": total_count,
                        "received_item_count": received_item_count,
                        "parsed_row_count": len(rows),
                        "pages_requested": page,
                        "error": error,
                    }
                )
                time.sleep(0.1)  # 공공데이터포털 예의상 소폭 대기
        print(f"[OK] {label}({group}) 누적 {len(all_rows):,}건")

    df = pd.DataFrame(all_rows)
    # 전세만: 월세 0 & 보증금 > 0
    if df.empty:
        jeonse = df.copy()
    else:
        jeonse = df[
            df["monthly_rent"].notna()
            & df["monthly_rent"].eq(0)
            & df["deposit_amount"].gt(0)
        ].copy()
    # PU 관측라벨 s=0일 뿐 실제 사고여부 y=0가 아니다.
    jeonse["pu_observed_label"] = 0
    jeonse["label_status"] = "unlabeled"
    complete = all(cell["status"] == "complete" for cell in cells)
    jeonse["collection_complete"] = complete
    jeonse["collection_period_start"] = deal_ymds[0]
    jeonse["collection_period_end"] = deal_ymds[-1]

    tag = f"{deal_ymds[0]}_{deal_ymds[-1]}_{RUN_STAMP}"
    out_path = OUT_DIR / f"rtms_jeonse_unlabeled_{tag}.csv"
    manifest_path = out_path.with_suffix(".manifest.json")
    jeonse["source_manifest"] = manifest_path.name
    failed_cells = [cell for cell in cells if cell["status"] != "complete"]
    manifest = {
        "schema_version": 1,
        "run_stamp": RUN_STAMP,
        "period": {"start": deal_ymds[0], "end": deal_ymds[-1]},
        "requested_cells": len(cells),
        "complete_cells": len(cells) - len(failed_cells),
        "failed_or_incomplete_cells": len(failed_cells),
        "collection_complete": complete,
        "allow_partial": args.allow_partial,
        "api_calls": calls,
        "parsed_rows": len(df),
        "jeonse_rows": len(jeonse),
        "csv_file": out_path.name if complete or args.allow_partial else None,
        "cells": cells,
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if not complete and not args.allow_partial:
        print(
            f"\n[FAIL] {len(failed_cells)}개 셀이 미완료여서 학습용 CSV를 저장하지 않았습니다."
        )
        print(f"감사 manifest → {manifest_path.relative_to(ROOT)}")
        return 2

    jeonse.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"\nAPI 호출 {calls}회 · 수집 {len(df):,}건 중 전세 {len(jeonse):,}건")
    if not jeonse.empty:
        print(f"주택유형 분포: {jeonse['housing_type'].value_counts().to_dict()}")
    print(f"→ {out_path.relative_to(ROOT)}")
    print(f"→ {manifest_path.relative_to(ROOT)}")
    return 0 if len(jeonse) else 1


if __name__ == "__main__":
    sys.exit(main())

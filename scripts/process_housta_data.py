#!/usr/bin/env python3
"""raw/housta 원본 파일을 분석용 정규 테이블로 변환.

산출물 (개별수집데이터 및 API/processed/housta/):
- housta_region_risk_<날짜>.csv        시군구별 사고건수·금액·사고율(%) + 법정동코드
- housta_issuance_region_monthly_<날짜>.csv  지역×연월×주택유형 발급건수·보증금액
- housta_victim_locations_<날짜>.csv   연도별 시군구 전세사기피해주택 수
- housta_annual_seoul_<날짜>.csv       서울 연도별 사고·대위변제 건수·금액
- housta_product_accident_rate_<날짜>.csv    안심대출 연도별 신청·사고건수·사고율

실행: backend/.venv/bin/python scripts/process_housta_data.py
"""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "개별수집데이터 및 API" / "raw" / "housta"
OUT = ROOT / "개별수집데이터 및 API" / "processed" / "housta"
TODAY = date.today().strftime("%Y%m%d")
RAW_TAG = "20260720"  # 수집일


def region_risk() -> pd.DataFrame:
    df = pd.read_excel(RAW / f"raw_housta_{RAW_TAG}_지역별_전세보증_사고현황.xlsx",
                       sheet_name="시군구", header=None)
    df = df.iloc[5:].dropna(subset=[1, 3])
    df.columns = ["adm_cd", "sido", "sigungu", "accident_cnt", "accident_amt_won", "accident_rate_pct"]
    df["sido"] = df["sido"].astype(str).str.strip()
    df["sigungu"] = df["sigungu"].astype(str).str.strip()
    df["adm_cd"] = df["adm_cd"].apply(lambda v: str(int(v)) if pd.notna(v) and str(v).strip() not in ("", "nan") else "")
    for c in ["accident_cnt", "accident_amt_won", "accident_rate_pct"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["accident_cnt"])
    df["is_summary"] = (df["sigungu"] == "소계").astype(int)
    df["basis"] = "보증사고 '25.8월 최근3개월 평균"
    return df.reset_index(drop=True)


def issuance_monthly() -> pd.DataFrame:
    df = pd.read_csv(RAW / f"raw_housta_{RAW_TAG}_전세보증_상세현황.csv", encoding="cp949")
    df.columns = [c.strip() for c in df.columns]
    df = df.rename(columns={"상품명": "product", "발급년도": "year", "월": "month",
                            "주택유형": "housing_type", "지역": "sido",
                            "건수": "issue_cnt", "보증금액": "issue_amt_won"})
    df["month"] = pd.to_numeric(df["month"], errors="coerce")
    df["yyyymm"] = df["year"].astype(str) + "-" + df["month"].astype(int).astype(str).str.zfill(2)
    return df


def victim_locations() -> pd.DataFrame:
    xl = pd.ExcelFile(RAW / f"raw_housta_{RAW_TAG}_경공매지원_피해주택_소재지.xlsx")
    frames = []
    for sh in xl.sheet_names:
        d = xl.parse(sh)
        d.columns = ["sigungu_full", "victim_house_cnt"]
        year = re.search(r"(20\d{2})", sh).group(1)
        d["year"] = year
        d["period_note"] = sh
        frames.append(d)
    df = pd.concat(frames, ignore_index=True).dropna(subset=["sigungu_full"])
    parts = df["sigungu_full"].astype(str).str.strip().str.split(" ", n=1, expand=True)
    df["sido_short"] = parts[0]
    df["sigungu"] = parts[1].fillna("")
    df["victim_house_cnt"] = pd.to_numeric(df["victim_house_cnt"], errors="coerce")
    return df.dropna(subset=["victim_house_cnt"])


def annual_seoul() -> pd.DataFrame:
    path = RAW / f"raw_housta_{RAW_TAG}_서울_연도별_사고_대위변제.xlsx"
    rows = []
    for sheet, kind in [("사고현황", "accident"), ("대위변제 현황", "subrogation")]:
        d = pd.read_excel(path, sheet_name=sheet, header=None)
        years = [v for v in d.iloc[2] if isinstance(v, str) and v.endswith("년")]
        data = d.iloc[4:].dropna(subset=[0])
        for _, r in data.iterrows():
            region = str(r[0]).strip()
            if region in ("", "nan"):
                continue
            for i, y in enumerate(years):
                cnt, amt = r[1 + i * 2], r[2 + i * 2]
                rows.append({"kind": kind, "region": region, "year": int(y[:4]),
                             "cnt": pd.to_numeric(cnt, errors="coerce"),
                             "amt_100m_won": pd.to_numeric(amt, errors="coerce")})
    return pd.DataFrame(rows).dropna(subset=["cnt"])


def product_accident_rate() -> pd.DataFrame:
    d = pd.read_csv(RAW / f"raw_housta_{RAW_TAG}_안심대출_신청_사고건수.csv", encoding="cp949", index_col=0)
    d = d.T.reset_index().rename(columns={"index": "year"})
    d["year"] = d["year"].str[:4].astype(int)
    d = d.rename(columns={"보증신청건수": "apply_cnt", "보증발급금액(억원)": "issue_amt_100m",
                          "보증사고건수": "accident_cnt", "보증사고금액(억원)": "accident_amt_100m"})
    for c in ["apply_cnt", "issue_amt_100m", "accident_cnt", "accident_amt_100m"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d["accident_rate_pct"] = (d["accident_cnt"] / d["apply_cnt"] * 100).round(3)
    d["product"] = "전세금안심대출보증"
    return d


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    outputs = {
        f"housta_region_risk_{TODAY}.csv": region_risk(),
        f"housta_issuance_region_monthly_{TODAY}.csv": issuance_monthly(),
        f"housta_victim_locations_{TODAY}.csv": victim_locations(),
        f"housta_annual_seoul_{TODAY}.csv": annual_seoul(),
        f"housta_product_accident_rate_{TODAY}.csv": product_accident_rate(),
    }
    for name, df in outputs.items():
        path = OUT / name
        df.to_csv(path, index=False, encoding="utf-8-sig")
        print(f"[OK] {name}: {len(df)}행, cols={list(df.columns)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

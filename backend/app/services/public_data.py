"""수집 공공데이터(HOUSTA·악성임대인 명단·ML 스코어) 로더.

`processed/` 산출물 CSV를 프로세스당 1회 로드해 캐시한다. 파일명이 날짜 태그를 포함하므로
glob 패턴에서 사전순 최신 파일을 선택한다. 데이터가 없으면 None을 반환하고, 호출부는
"신호 미확보(missing)"로 처리한다 — 예외로 서비스 전체를 죽이지 않는다.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

import pandas as pd

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# 광역시도 전체명/축약명 → 축약명(악성임대인·HOUSTA CSV 공통 표기)
SIDO_SHORT = {
    "서울": "서울", "서울특별시": "서울", "부산": "부산", "부산광역시": "부산",
    "대구": "대구", "대구광역시": "대구", "인천": "인천", "인천광역시": "인천",
    "광주": "광주", "광주광역시": "광주", "대전": "대전", "대전광역시": "대전",
    "울산": "울산", "울산광역시": "울산", "세종": "세종", "세종특별자치시": "세종",
    "경기": "경기", "경기도": "경기", "강원": "강원", "강원도": "강원", "강원특별자치도": "강원",
    "충북": "충북", "충청북도": "충북", "충남": "충남", "충청남도": "충남",
    "전북": "전북", "전라북도": "전북", "전북특별자치도": "전북",
    "전남": "전남", "전라남도": "전남", "경북": "경북", "경상북도": "경북",
    "경남": "경남", "경상남도": "경남", "제주": "제주", "제주특별자치도": "제주",
}


def _latest(pattern: str) -> Path | None:
    base = Path(get_settings().data_dir)
    matches = sorted(base.glob(pattern))
    if not matches:
        logger.warning("public_data: %s 에 해당하는 파일 없음 (data_dir=%s)", pattern, base)
        return None
    return matches[-1]


def _load_csv(pattern: str) -> pd.DataFrame | None:
    path = _latest(pattern)
    if path is None:
        return None
    try:
        return pd.read_csv(path)
    except Exception:  # noqa: BLE001
        logger.exception("public_data: %s 로드 실패", path)
        return None


@lru_cache(maxsize=1)
def region_risk() -> pd.DataFrame | None:
    """시군구별 사고건수·금액·사고율(%). adm_cd는 5자리 법정동코드 문자열."""
    df = _load_csv("processed/housta/housta_region_risk_*.csv")
    if df is not None:
        df["adm_cd"] = df["adm_cd"].fillna("").astype(str).str.replace(r"\.0$", "", regex=True)
    return df


@lru_cache(maxsize=1)
def bad_landlords() -> pd.DataFrame | None:
    """법정 공개 악성임대인 명단(상습 채무불이행자 + 보증금 미반환 임대사업자)."""
    df = _load_csv("processed/khug_disclosure/bad_landlords_*.csv")
    if df is not None:
        df["name"] = df["name"].fillna("").astype(str).str.strip()
        df["sido"] = df["sido"].fillna("").astype(str)
    return df


@lru_cache(maxsize=1)
def priority_scores() -> pd.DataFrame | None:
    """학습된 회수율·소요기간 모델로 스코어링한 전 채권 목록(합성데이터 기준)."""
    return _load_csv("processed/ml/recovery_priority_scores_*.csv")


@lru_cache(maxsize=1)
def issuance_monthly() -> pd.DataFrame | None:
    """전세보증금반환보증 시도×연월×주택유형 발급현황."""
    return _load_csv("processed/housta/housta_issuance_region_monthly_*.csv")


@lru_cache(maxsize=1)
def victim_locations() -> pd.DataFrame | None:
    """경공매지원 신청자의 전세사기피해주택 시군구 분포."""
    return _load_csv("processed/housta/housta_victim_locations_*.csv")


def region_risk_basis() -> str:
    path = _latest("processed/housta/housta_region_risk_*.csv")
    return f"HUG 빅데이터 개방 포털 실집계({path.name})" if path else "미확보"


def find_region_row(road_address: str | None, adm_cd: str | None) -> dict | None:
    """주소(도로명) 또는 법정동코드로 시군구 사고율 행을 찾는다.

    우선순위: adm_cd 앞 5자리 일치 → 주소 토큰(시도+시군구) 일치 → 시도 소계 행.
    """
    df = region_risk()
    if df is None:
        return None
    detail = df[df["is_summary"] == 0]

    if adm_cd:
        code = str(adm_cd)[:5]
        hit = detail[detail["adm_cd"] == code]
        if not hit.empty:
            return hit.iloc[0].to_dict()

    if road_address:
        tokens = road_address.split()
        if tokens:
            sido = SIDO_SHORT.get(tokens[0])
            if sido:
                in_sido = detail[detail["sido"] == sido]
                for token in tokens[1:3]:
                    hit = in_sido[in_sido["sigungu"] == token]
                    if not hit.empty:
                        return hit.iloc[0].to_dict()
                summary = df[(df["sido"] == sido) & (df["is_summary"] == 1)]
                if not summary.empty:
                    return summary.iloc[0].to_dict()
    return None


def match_bad_landlord(name: str | None, road_address: str | None) -> dict | None:
    """임대인 성명(+주소 시도)으로 공개명단 일치 여부를 확인한다.

    반환: {"match_level": "name_sido"|"name_only", "count": n, "base_date": ..., "legal_basis": ...}
    개인정보 보호를 위해 명단의 상세 주소·전체 행은 반환하지 않는다(일치 여부와 근거만).
    """
    df = bad_landlords()
    if df is None or not name:
        return None
    hits = df[df["name"] == name.strip()]
    if hits.empty:
        return None
    level = "name_only"
    if road_address:
        tokens = road_address.split()
        sido = SIDO_SHORT.get(tokens[0]) if tokens else None
        if sido is not None:
            sido_hits = hits[hits["sido"] == sido]
            if not sido_hits.empty:
                hits = sido_hits
                level = "name_sido"
    row = hits.iloc[0]
    return {
        "match_level": level,
        "count": int(len(hits)),
        "base_date": str(row.get("base_date", "")),
        "legal_basis": str(row.get("legal_basis", "")),
        "list_type": str(row.get("list_type", "")),
    }

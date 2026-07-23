"""시군구 경계 GeoJSON 생성 (README §19.5 코로플레스 지도용).

VWorld Data API `LT_C_ADSIGG_INFO`(시군구 경계, 전국 256건)를 페이지네이션으로 수집해
shapely로 단순화한 뒤 `frontend/public/geo/sigungu.json`으로 저장한다.

- `sig_cd`(5자리)는 housta_region_risk의 `adm_cd`와 동일한 법정 시군구 코드 체계(260722 스파이크 검증).
- 키/도메인은 backend/.env의 OFFICIAL_PRICE_APT_API_KEY / OFFICIAL_PRICE_REGISTERED_SERVICE_URL 재사용
  (VWorld는 등록 서비스 URL의 domain 파라미터 필수 — 메모리/README 기록).
- properties: {sig_cd, name(시군구명), full_nm, cx, cy(대표점 = 최대 폴리곤 중심)} — cx/cy는 버블 오버레이용.

실행:  backend/.venv/bin/python scripts/build_sigungu_geojson.py
검증:  housta_region_risk adm_cd 252건과의 조인 커버리지를 출력한다.
"""

from __future__ import annotations

import asyncio
import csv
import glob
import json
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv
from shapely.geometry import mapping, shape

ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = ROOT / "frontend" / "public" / "geo" / "sigungu.json"
REGION_RISK_GLOB = str(ROOT / "개별수집데이터 및 API" / "processed" / "housta" / "housta_region_risk_*.csv")

API_URL = "https://api.vworld.kr/req/data"
PAGE_SIZE = 20  # geometry 포함 응답이 커서 페이지를 작게 유지한다
SIMPLIFY_TOLERANCE = 0.004  # 도 단위(~400m) — 전국 뷰 시각화에 충분, 파일 수 MB 이내
COORD_PRECISION = 4  # 소수 4자리(~10m)


def _round_coords(obj):
    if isinstance(obj, (list, tuple)):
        if obj and isinstance(obj[0], float):
            return [round(v, COORD_PRECISION) for v in obj]
        return [_round_coords(v) for v in obj]
    return obj


async def fetch_all() -> list[dict]:
    load_dotenv(ROOT / "backend" / ".env")
    key = os.environ["OFFICIAL_PRICE_APT_API_KEY"]
    domain = os.environ["OFFICIAL_PRICE_REGISTERED_SERVICE_URL"]
    base = {
        "service": "data",
        "request": "GetFeature",
        "data": "LT_C_ADSIGG_INFO",
        "key": key,
        "domain": domain,
        "format": "json",
        "crs": "EPSG:4326",
        "geometry": "true",
        "geomFilter": "BOX(124,33,132,39)",
        "size": str(PAGE_SIZE),
    }
    features: list[dict] = []
    async with httpx.AsyncClient(timeout=60.0) as client:
        page = 1
        while True:
            r = await client.get(API_URL, params={**base, "page": str(page)})
            r.raise_for_status()
            resp = r.json()["response"]
            if resp.get("status") != "OK":
                raise RuntimeError(f"VWorld 응답 오류(page={page}): {resp.get('status')}")
            batch = resp["result"]["featureCollection"]["features"]
            features.extend(batch)
            record = resp["record"]
            print(f"page {page}: +{len(batch)} (누적 {len(features)}/{record['total']})")
            if len(features) >= int(record["total"]) or not batch:
                break
            page += 1
    return features


def simplify_features(raw: list[dict]) -> list[dict]:
    out = []
    for f in raw:
        props = f["properties"]
        geom = shape(f["geometry"])
        simplified = geom.simplify(SIMPLIFY_TOLERANCE, preserve_topology=True)
        # 대표점: 가장 큰 폴리곤의 대표점(도서 지역이 중심을 끌고 가지 않게)
        largest = max(getattr(simplified, "geoms", [simplified]), key=lambda g: g.area)
        rep = largest.representative_point()
        out.append(
            {
                "type": "Feature",
                "properties": {
                    "sig_cd": props["sig_cd"],
                    "name": props["sig_kor_nm"],
                    "full_nm": props["full_nm"],
                    "cx": round(rep.x, COORD_PRECISION),
                    "cy": round(rep.y, COORD_PRECISION),
                },
                "geometry": {
                    "type": simplified.geom_type,
                    "coordinates": _round_coords(mapping(simplified)["coordinates"]),
                },
            }
        )
    return out


# 2026 행정구역 개편(VWorld 최신 경계) ↔ housta 2025-08 구코드 근사 매핑.
# - 인천 재편: 영종구(28155)←구 중구(28110), 서해구(28275)/검단구(28290)←구 서구(28260).
#   제물포구(28125)는 구 중구+동구 병합이라 1:1 통계 대응이 없어 매핑하지 않는다(회색 처리).
# - 화성 분구: 만세/효행/병점/동탄구 ← 구 화성시(41590). 사고율(%)은 시 전체 값 복제가 정보 보존.
MANUAL_SRC_CD = {
    "28155": "28110",
    "28275": "28260",
    "28290": "28260",
    "41591": "41590",
    "41593": "41590",
    "41595": "41590",
    "41597": "41590",
}


def load_region_rows() -> list[dict]:
    csv_paths = sorted(glob.glob(REGION_RISK_GLOB))
    if not csv_paths:
        return []
    with open(csv_paths[-1], encoding="utf-8-sig") as fh:
        return [r for r in csv.DictReader(fh) if r.get("is_summary") == "0"]


def assign_src_cd(features: list[dict], region_rows: list[dict]) -> None:
    """각 feature에 데이터 조인용 구코드 `src_cd`를 부여한다(없으면 None → 회색)."""
    data_codes = {r["adm_cd"] for r in region_rows}
    by_name = {(r["sido"], r["sigungu"]): r["adm_cd"] for r in region_rows}
    for f in features:
        p = f["properties"]
        cd = p["sig_cd"]
        src: str | None = cd if cd in data_codes else None
        if src is None and cd.startswith("12"):
            # 전남광주통합특별시(12xxx) — 구(區)는 구 광주, 시·군은 구 전남 소속. 이름 유일 매칭.
            sido = "광주" if p["name"].endswith("구") else "전남"
            src = by_name.get((sido, p["name"]))
        if src is None:
            src = MANUAL_SRC_CD.get(cd)
        p["src_cd"] = src


def check_coverage(features: list[dict], region_rows: list[dict]) -> None:
    if not region_rows:
        print("⚠️ region_risk CSV를 찾지 못해 커버리지 검증 생략")
        return
    joinable = {f["properties"]["src_cd"] for f in features if f["properties"]["src_cd"]}
    missing = [(r["adm_cd"], r["sido"], r["sigungu"]) for r in region_rows if r["adm_cd"] not in joinable]
    unmapped = [f["properties"]["name"] for f in features if not f["properties"]["src_cd"]]
    print(f"조인 커버리지: {len(region_rows) - len(missing)}/{len(region_rows)} 매칭")
    for m in missing:
        print("  데이터 미표시:", m)
    print(f"회색(매핑 없음) feature: {unmapped}")


async def main() -> None:
    raw = await fetch_all()
    features = simplify_features(raw)
    region_rows = load_region_rows()
    assign_src_cd(features, region_rows)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fc = {"type": "FeatureCollection", "features": features}
    OUT_PATH.write_text(json.dumps(fc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    size_mb = OUT_PATH.stat().st_size / 1_048_576
    print(f"저장: {OUT_PATH} ({size_mb:.2f} MB, {len(features)} features)")
    check_coverage(features, region_rows)


if __name__ == "__main__":
    asyncio.run(main())

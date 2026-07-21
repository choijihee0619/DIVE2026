"""공시가격 스냅샷 서비스 — VWorld NED 데이터 API 실호출(live)로 전세가율 신호를 활성화한다.

VWorld 인증키 3종(개발키)은 등록 서비스 URL을 `domain` 파라미터로 함께 보내야 인증된다
(260721 실호출 검증 완료 — 누락 시 INCORRECT_KEY).

엔드포인트 선택 규칙(주택유형 기준):
- 아파트·오피스텔·연립·다세대  → 공동주택가격 getApartHousingPriceAttr (호별, pblntfPc 원)
- 단독·다가구                 → 개별주택가격 getIndvdHousingPriceAttr (필지별, housePc 원)
- 주택가격 미조회 시           → 개별공시지가 getIndvdLandPriceAttr (pblntfPclnd 원/㎡)를
                                 참고값(reference)으로만 저장하고 official_price는 비운다.
                                 지가는 주택가격이 아니므로 전세가율 채점에 쓰지 않는다(데이터 정직성 원칙).

PNU(19자리) = 법정동코드 10 + 필지구분 1(일반=1/산=2) + 본번 4 + 부번 4.
법정동코드는 주소 정규화 시 저장된 address.adm_cd, 본·부번은 jibun_address 끝 지번에서 파싱한다.
공동주택은 address.dong/ho가 있으면 해당 세대를 매칭하고, 없으면 최신 기준연도 세대들의
중앙값을 사용한다(단지 대표값, price_basis에 명시).
"""

from __future__ import annotations

import logging
import re
import statistics
from datetime import date

import httpx
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import get_settings
from app.core.exceptions import ResourceNotFoundError, ValidationAppError
from app.repositories.property_repository import PropertyRepository
from app.repositories.risk_repository import OfficialPriceSnapshotRepository
from app.utils.datetime_utils import new_uuid, now_kst_iso

logger = logging.getLogger(__name__)

_BASE = "https://api.vworld.kr/ned/data"

# 공동주택가격 API가 커버하는 유형(집합건물)
_APT_TYPES = {"APARTMENT", "OFFICETEL", "MULTI_HOUSEHOLD", "ROW_HOUSE"}
# 개별주택가격 API가 커버하는 유형
_HOUSE_TYPES = {"SINGLE_FAMILY", "MULTI_FAMILY"}


def build_pnu(adm_cd: str | None, jibun_address: str | None) -> str | None:
    """법정동코드 + 지번주소 말미의 지번으로 19자리 PNU를 만든다."""
    if not adm_cd or len(adm_cd) < 10:
        return None
    ld_code = adm_cd[:10]
    if not jibun_address:
        return None
    tail = jibun_address.strip().split()[-1] if jibun_address.strip() else ""
    mountain = "2" if tail.startswith("산") or " 산" in jibun_address else "1"
    m = re.search(r"(\d+)(?:-(\d+))?$", tail)
    if not m:
        return None
    bonbun = int(m.group(1))
    bubun = int(m.group(2) or 0)
    return f"{ld_code}{mountain}{bonbun:04d}{bubun:04d}"


async def _call_ned(
    client: httpx.AsyncClient, endpoint: str, key: str, pnu: str, year: str
) -> list[dict]:
    settings = get_settings()
    resp = await client.get(
        f"{_BASE}/{endpoint}",
        params={
            "key": key,
            "pnu": pnu,
            "stdrYear": year,
            "format": "json",
            "numOfRows": "1000",
            "pageNo": "1",
            "domain": settings.official_price_domain,
        },
    )
    resp.raise_for_status()
    body = resp.json()
    root = next(iter(body.values())) if isinstance(body, dict) and body else {}
    result_code = str(root.get("resultCode") or "")
    if result_code and result_code not in ("", "OK", "00"):
        raise ValidationAppError(f"VWorld {endpoint} 오류: {result_code} {root.get('resultMsg')}")
    fields = root.get("field") or []
    return fields if isinstance(fields, list) else [fields]


def _years() -> list[str]:
    this_year = date.today().year
    return [str(this_year - i) for i in range(0, 3)]


class OfficialPriceService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._properties = PropertyRepository(db)
        self._snapshots = OfficialPriceSnapshotRepository(db)

    async def refresh(self, property_id: str) -> dict:
        prop = await self._properties.get_by_id(property_id)
        if not prop:
            raise ResourceNotFoundError("매물 정보를 찾을 수 없습니다.")
        settings = get_settings()
        if not settings.official_price_apt_api_key:
            raise ValidationAppError("공시가격 API 키가 설정되지 않았습니다(.env OFFICIAL_PRICE_*).")

        address = prop.get("address") or {}
        pnu = build_pnu(address.get("adm_cd"), address.get("jibun_address"))
        if not pnu:
            raise ValidationAppError(
                "PNU를 만들 수 없습니다 — 매물 주소에 adm_cd(법정동코드)와 지번주소가 필요합니다."
            )

        housing_type = (prop.get("housing_type") or "OTHER").upper()
        dong = (address.get("dong") or "").strip()
        ho = (address.get("ho") or "").strip()

        price: int | None = None
        price_basis: str | None = None
        stdr_year: str | None = None
        matched: dict | None = None
        reference_land_price_per_m2: int | None = None
        raw_sample: dict | None = None

        async with httpx.AsyncClient(timeout=30.0) as client:
            order = ["apt", "house"] if housing_type in _APT_TYPES else ["house", "apt"]
            if housing_type == "OTHER":
                order = ["apt", "house"]
            for kind in order:
                if price is not None:
                    break
                endpoint, key, field = {
                    "apt": ("getApartHousingPriceAttr", settings.official_price_apt_api_key, "pblntfPc"),
                    "house": ("getIndvdHousingPriceAttr", settings.official_price_house_api_key, "housePc"),
                }[kind]
                for year in _years():
                    try:
                        rows = await _call_ned(client, endpoint, key, pnu, year)
                    except Exception as exc:  # noqa: BLE001 - 다음 연도/엔드포인트 시도
                        logger.warning("VWorld %s %s년 조회 실패: %s", endpoint, year, exc)
                        continue
                    rows = [r for r in rows if r.get(field)]
                    if not rows:
                        continue
                    if kind == "apt":
                        unit = None
                        if dong or ho:
                            for r in rows:
                                dong_ok = not dong or str(r.get("dongNm", "")).strip() == dong
                                ho_ok = not ho or str(r.get("hoNm", "")).strip() == ho
                                if dong_ok and ho_ok:
                                    unit = r
                                    break
                        if unit:
                            price = int(unit[field])
                            price_basis = "공동주택가격(호별 매칭)"
                            matched = {
                                "dong": unit.get("dongNm"),
                                "ho": unit.get("hoNm"),
                                "prvuse_ar": unit.get("prvuseAr"),
                            }
                            raw_sample = unit
                        else:
                            values = sorted(int(r[field]) for r in rows)
                            price = int(statistics.median(values))
                            price_basis = f"공동주택가격(단지 {len(values)}세대 중앙값 — 동·호 미지정)"
                            raw_sample = rows[0]
                    else:
                        row = rows[0]
                        price = int(row[field])
                        price_basis = "개별주택가격(필지)"
                        raw_sample = row
                    stdr_year = year
                    break

            if price is None:
                # 주택가격 미확보 — 개별공시지가는 참고값으로만 저장
                for year in _years():
                    try:
                        rows = await _call_ned(
                            client,
                            "getIndvdLandPriceAttr",
                            settings.official_price_land_api_key,
                            pnu,
                            year,
                        )
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("VWorld 개별공시지가 %s년 조회 실패: %s", year, exc)
                        continue
                    rows = [r for r in rows if r.get("pblntfPclnd")]
                    if rows:
                        reference_land_price_per_m2 = int(rows[0]["pblntfPclnd"])
                        stdr_year = year
                        raw_sample = rows[0]
                        break

        doc = {
            "_id": new_uuid(),
            "property_id": property_id,
            # 데이터 정직성 원칙: 주택가격을 실제 확보했을 때만 live로 저장한다.
            "source_system": "api_live" if price is not None else "api_live_no_data",
            "provider": "vworld_ned",
            "pnu": pnu,
            "stdr_year": stdr_year,
            "official_price": price,
            "price_basis": price_basis,
            "matched_unit": matched,
            "reference_land_price_per_m2": reference_land_price_per_m2,
            "response_sample": raw_sample,
            "created_at": now_kst_iso(),
        }
        await self._snapshots.insert(doc)
        return _to_summary(doc)

    async def latest(self, property_id: str) -> dict:
        doc = await self._snapshots.find_latest_by_property(property_id)
        if not doc:
            raise ResourceNotFoundError("공시가격 스냅샷이 없습니다. refresh를 먼저 호출하세요.")
        return _to_summary(doc)


def _to_summary(doc: dict) -> dict:
    return {
        "official_price_snapshot_id": doc["_id"],
        "property_id": doc["property_id"],
        "source_system": doc["source_system"],
        "provider": doc.get("provider"),
        "pnu": doc.get("pnu"),
        "stdr_year": doc.get("stdr_year"),
        "official_price": doc.get("official_price"),
        "price_basis": doc.get("price_basis"),
        "matched_unit": doc.get("matched_unit"),
        "reference_land_price_per_m2": doc.get("reference_land_price_per_m2"),
        "created_at": doc["created_at"],
    }

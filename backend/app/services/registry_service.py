"""등기부 스냅샷 서비스 — "주소 입력 → 등기부 조회"를 백엔드에 연결한다.

경로 2가지:
1) live: CODEF 샌드박스 실호출(codef_client) → 응답을 파싱해 권리 신호 추출 →
   registry_snapshots에 source_system="api_live"로 저장 → 위험진단 엔진이 실제 계산 수행
2) mock: 시나리오(mock/mock_registry_*.json) 기반 스냅샷 — 데모/오프라인/실패 폴백

파서는 휴리스틱이다(전산화 등기부 텍스트 기반): 채권최고액 합산, 압류·가압류 행 중
같은 행에 '말소' 표기가 없는 것만 유효로 집계한다. 한계는 features.parser_note에 명시한다.

# MODIFIED 2026-07-21: (1) 등기부 조회 주소에 동·호수 반영(집합건물은 동·호까지 있어야 특정 가능),
#   refresh 시 dong/ho를 property.address에 저장. (2) CODEF 응답의 표제부/갑구/을구 원문을
#   화면 표시용 구조(register_detail)로 파싱해 스냅샷에 저장 — 임대인/임차인/상담사/HUG 등기부 열람 화면용.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import get_settings
from app.core.exceptions import ResourceNotFoundError, ValidationAppError
from app.repositories.property_repository import PropertyRepository
from app.repositories.risk_repository import RegistrySnapshotRepository
from app.services import codef_client
from app.utils.datetime_utils import new_uuid, now_kst_iso

logger = logging.getLogger(__name__)

MOCK_SCENARIOS = {
    "normal": "mock_registry_normal.json",
    "mortgage": "mock_registry_mortgage.json",
    "complex_rights": "mock_registry_complex_rights.json",
}

_KOR_NUM = {"영": 0, "일": 1, "이": 2, "삼": 3, "사": 4, "오": 5, "육": 6, "칠": 7, "팔": 8, "구": 9}
_KOR_UNIT = {"십": 10, "백": 100, "천": 1000}
_KOR_BIG = {"만": 10_000, "억": 100_000_000, "조": 1_000_000_000_000}


def _korean_amount_to_won(text: str) -> int | None:
    """'일천팔백이십만' 같은 한글 금액을 원 단위 정수로 변환한다."""
    total = section = digit = 0
    seen = False
    for ch in text:
        if ch in _KOR_NUM:
            digit = _KOR_NUM[ch]
            seen = True
        elif ch in _KOR_UNIT:
            section += (digit or 1) * _KOR_UNIT[ch]
            digit = 0
            seen = True
        elif ch in _KOR_BIG:
            total += (section + digit or 1) * _KOR_BIG[ch]
            section = digit = 0
            seen = True
        elif ch == "원":
            break
    total += section + digit
    return total if seen and total > 0 else None


def _iter_rows(entry: dict):
    for his in entry.get("resRegistrationHisList", []):
        for content in his.get("resContentsList", []):
            row = " ".join(
                str(d.get("resContents", "")) for d in content.get("resDetailList", [])
            )
            if row.strip():
                yield row


def parse_register_features(codef_body: dict) -> dict:
    """CODEF 등기부 응답에서 위험 신호 features를 추출한다(휴리스틱)."""
    data = codef_body.get("data", {})
    entries = data.get("resRegisterEntriesList", [])
    mortgage_amounts: list[int] = []
    seizure_active = 0
    seizure_total = 0
    rights_keywords: dict[str, int] = {}
    doc_title = realty = publish_date = ""

    for entry in entries:
        doc_title = entry.get("resDocTitle", doc_title)
        realty = entry.get("resRealty", realty)
        publish_date = entry.get("resPublishDate", publish_date)
        for row in _iter_rows(entry):
            # 채권최고액: 숫자 표기 우선, 없으면 한글 표기 변환
            for m in re.finditer(r"채권최고액\s*금\s*([0-9][0-9,]*)\s*원", row):
                mortgage_amounts.append(int(m.group(1).replace(",", "")))
            if "채권최고액" in row and not re.search(r"채권최고액\s*금\s*[0-9]", row):
                m = re.search(r"채권최고액\s*금\s*([가-힣]+?원)", row)
                if m:
                    won = _korean_amount_to_won(m.group(1))
                    if won:
                        mortgage_amounts.append(won)
            for kw in ("근저당권설정", "전세권설정", "신탁", "가처분", "임차권등기"):
                if kw in row:
                    rights_keywords[kw] = rights_keywords.get(kw, 0) + 1
            if "압류" in row:  # 가압류 포함
                seizure_total += 1
                if "말소" not in row and "해제" not in row:
                    seizure_active += 1

    # 같은 순위가 한글/숫자 표기로 중복 기재되는 경우 dedupe
    unique_amounts = sorted(set(mortgage_amounts), reverse=True)
    return {
        "has_seizure": seizure_active > 0,
        "seizure_rows_active": seizure_active,
        "seizure_rows_total": seizure_total,
        "mortgage_count": len(unique_amounts),
        "mortgage_max_total_won": int(sum(unique_amounts)),
        "rights_keywords": rights_keywords,
        "doc_title": doc_title,
        "realty_masked": realty,
        "publish_date": publish_date,
        "parser_note": (
            "전산화 등기부 텍스트 휴리스틱 파싱: 채권최고액 중복표기 dedupe, "
            "압류·가압류는 동일 행에 말소·해제 표기가 없는 것만 유효 집계. 최종 판단 전 원문 확인 필요."
        ),
    }


def _clean_cell(raw: str) -> str:
    """CODEF 등기부 셀 텍스트 정리: 말소 마커(&), 위치 마커(숫자^), 구분자(|)를 제거한다."""
    text = raw.replace("&", "")
    text = re.sub(r"\d+\^", "", text)
    text = text.replace("|", "\n")
    lines = [line.strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line)


def parse_register_detail(codef_body: dict) -> dict:
    """CODEF 응답의 표제부/갑구/을구 원문을 화면 표시용 표 구조로 변환한다.

    CODEF 표기 규칙: `&...&`로 감싼 내용은 말소된 기재사항(취소선 대상)이며,
    `숫자^`는 원문 지면상의 위치 마커라 표시에서 제거한다.
    """
    entries = codef_body.get("data", {}).get("resRegisterEntriesList", [])
    entry = entries[0] if entries else {}
    sections: list[dict] = []
    for his in entry.get("resRegistrationHisList", []):
        headers: list[str] = []
        rows: list[dict] = []
        for content in his.get("resContentsList", []):
            details = sorted(
                content.get("resDetailList", []),
                key=lambda d: int(d.get("resNumber", 0) or 0),
            )
            cells_raw = [str(d.get("resContents", "")) for d in details]
            if str(content.get("resType2", "")) == "1":
                headers = [_clean_cell(c) for c in cells_raw]
                continue
            non_empty = [c for c in cells_raw if c.strip()]
            canceled_count = sum(1 for c in non_empty if "&" in c)
            rows.append({
                "cells": [_clean_cell(c) for c in cells_raw],
                # 비어있지 않은 셀 과반이 말소 마커면 행 전체를 말소 기재로 본다
                "canceled": bool(non_empty) and canceled_count * 2 >= len(non_empty),
            })
        sections.append({
            "section": his.get("resType", ""),
            "title": his.get("resType1", ""),
            "headers": headers,
            "rows": rows,
        })
    return {
        "doc_title": entry.get("resDocTitle", ""),
        "realty": entry.get("resRealty", ""),
        "publish_date": entry.get("resPublishDate", ""),
        "publish_office": entry.get("resPublishRegistryOffice", ""),
        "unique_no": entry.get("commUniqueNo", ""),
        "competent_office": entry.get("commCompetentRegistryOffice", ""),
        "sections": sections,
    }


def build_register_query_address(address: dict) -> str:
    """등기부 조회용 주소 조합. 집합건물은 동·호수까지 있어야 특정 가능하다."""
    road = (address.get("road_address") or "").strip()
    parts = [road]
    dong = str(address.get("dong") or "").strip()
    ho = str(address.get("ho") or "").strip()
    if dong:
        parts.append(dong if dong.endswith("동") else f"{dong}동")
    if ho:
        parts.append(ho if ho.endswith("호") else f"{ho}호")
    return " ".join(part for part in parts if part)


class RegistryService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._properties = PropertyRepository(db)
        self._snapshots = RegistrySnapshotRepository(db)

    async def refresh(
        self,
        property_id: str,
        deposit: int | None = None,
        scenario: str | None = None,
        dong: str | None = None,
        ho: str | None = None,
    ) -> dict:
        prop = await self._properties.get_by_id(property_id)
        if not prop:
            raise ResourceNotFoundError("매물 정보를 찾을 수 없습니다.")

        address = dict(prop.get("address") or {})
        # 동·호수가 새로 입력되면 매물 주소에 저장해 이후 조회에 재사용한다
        updates = {}
        if dong and dong.strip():
            address["dong"] = dong.strip()
            updates["address.dong"] = dong.strip()
        if ho and ho.strip():
            address["ho"] = ho.strip()
            updates["address.ho"] = ho.strip()
        if updates:
            await self._properties.update_fields(property_id, updates)

        if scenario:
            if scenario not in MOCK_SCENARIOS:
                raise ValidationAppError(f"scenario는 {sorted(MOCK_SCENARIOS)} 중 하나여야 합니다.")
            return await self._mock_snapshot(property_id, scenario, deposit)

        query_address = build_register_query_address(address)
        try:
            body = await codef_client.fetch_register(query_address)
        except Exception as exc:  # noqa: BLE001 - 실패 시 mock 폴백 (기존 수집 정책과 동일)
            logger.warning("CODEF 등기부 호출 실패, mock 폴백: %s", exc)
            return await self._mock_snapshot(
                property_id, "normal", deposit, fallback_reason=str(exc)[:200]
            )

        features = parse_register_features(body)
        if deposit and deposit > 0:
            features["mortgage_to_deposit_ratio"] = round(
                features["mortgage_max_total_won"] / deposit, 4
            )
            # 위험엔진 호환 필드: 보증금 대비 채권최고액 비율을 근저당 비율로 사용
            features["mortgage_ratio"] = min(features["mortgage_to_deposit_ratio"], 1.0)

        doc = {
            "_id": new_uuid(),
            "property_id": property_id,
            "source_system": "api_live",
            "provider": f"codef_{get_settings().codef_env}",
            "transaction_id": body.get("result", {}).get("transactionId"),
            "query_address": query_address,
            "features": features,
            "register_detail": parse_register_detail(body),
            "created_at": now_kst_iso(),
        }
        await self._snapshots.insert(doc)
        return _to_summary(doc)

    async def latest(self, property_id: str) -> dict:
        doc = await self._snapshots.find_latest_by_property(property_id)
        if not doc:
            raise ResourceNotFoundError("등기부 스냅샷이 없습니다. refresh를 먼저 호출하세요.")
        return _to_summary(doc)

    async def _mock_snapshot(
        self, property_id: str, scenario: str, deposit: int | None, fallback_reason: str | None = None
    ) -> dict:
        mock_path = (
            Path(get_settings().data_dir) / "mock" / MOCK_SCENARIOS[scenario]
        )
        mock = json.loads(mock_path.read_text(encoding="utf-8"))
        features = dict(mock.get("features", {}))
        if deposit and deposit > 0 and features.get("mortgage_ratio") is None:
            features["mortgage_ratio"] = 0.0
        doc = {
            "_id": new_uuid(),
            "property_id": property_id,
            "source_system": "mock",
            "provider": f"mock_registry_{scenario}",
            "fallback_reason": fallback_reason,
            "features": features,
            "created_at": now_kst_iso(),
        }
        await self._snapshots.insert(doc)
        return _to_summary(doc)


def _to_summary(doc: dict) -> dict:
    return {
        "registry_snapshot_id": doc["_id"],
        "property_id": doc["property_id"],
        "source_system": doc["source_system"],
        "provider": doc.get("provider"),
        "fallback_reason": doc.get("fallback_reason"),
        "query_address": doc.get("query_address"),
        "features": doc.get("features", {}),
        "register_detail": doc.get("register_detail"),
        "created_at": doc["created_at"],
    }

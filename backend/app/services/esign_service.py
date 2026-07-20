"""전자계약 공동세션 서비스 (UI 시안 2-4 '전자계약 공동세션' 화면 대응).

플로우:
1. 임차인이 본인 계약으로 세션 생성 → 4자리 세션 코드 발급, AI 특약 추천 자동 생성
   (연결된 위험진단 risk_factors 기반 + 상담사례 빈출 특약)
2. 임대인이 세션 코드로 참여(join) — 계약에 landlord_user_id가 비어 있으면 바인딩
3. 특약 합의: 양측이 각 특약에 agree (또는 제안자가 withdraw) → 전부 정리되면 Signing 단계
4. 양측 sign → canonical JSON 계약문서의 SHA-256 해시를 BlockchainService로 앵커링
   (event_type="ContractSigned", 멱등) → 계약 상태 ContractFinalized + 타임라인 기록
5. verify: 저장된 계약문서 해시 재계산 vs 앵커된 해시 비교. tampered_fields를 넘기면
   변조 시나리오(불일치) 데모 가능.

동시접속 표시는 폴링(GET 세션)으로 처리한다(웹소켓은 프론트 단계에서 필요 시 추가).
"""

from __future__ import annotations

import secrets

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.exceptions import (
    PermissionDeniedError,
    ResourceNotFoundError,
    StateConflictError,
    ValidationAppError,
)
from app.models.enums import ContractStatus
from app.repositories.base_repository import BaseRepository
from app.repositories.contract_repository import ContractRepository, TimelineRepository
from app.repositories.risk_repository import RiskAssessmentRepository
from app.schemas.blockchain import AnchorRequest
from app.schemas.esign import (
    EsignSessionResponse,
    EsignVerifyResponse,
    Participant,
    SpecialTerm,
)
from app.services.blockchain_service import BlockchainService
from app.services.notification_service import NotificationService
from app.utils.datetime_utils import new_uuid, now_kst_iso
from app.utils.hashing import sha256_json

# 위험진단 risk_factor code → 추천 특약 템플릿
_RISK_TERM_TEMPLATES: dict[str, tuple[str, str]] = {
    "MORTGAGE_RATIO_HIGH": (
        "임대인은 잔금일 전까지 본 건 부동산의 근저당권을 말소하며, 미이행 시 임차인은 계약을 해제하고 계약금의 배액을 배상받는다.",
        "위험진단: 근저당 비율 높음",
    ),
    "MORTGAGE_RATIO_MEDIUM": (
        "임대인은 잔금일 전까지 근저당권 말소 또는 감액 등기를 완료하고 그 등기부를 임차인에게 제시한다.",
        "위험진단: 근저당 설정 확인",
    ),
    "JEONSE_RATIO_HIGH": (
        "임대인은 임차인의 전세보증금반환보증 가입에 필요한 서류 제공 등 절차에 협조한다.",
        "위험진단: 전세가율 높음 — 보증 가입 필수 권고",
    ),
    "REGION_ACCIDENT_RATE_HIGH": (
        "임대인은 임차인의 전세보증금반환보증 가입 절차에 협조하며, 가입이 거절되는 경우 임차인은 위약금 없이 계약을 해제할 수 있다.",
        "위험진단: 지역 보증사고율 높음",
    ),
    "LANDLORD_DISCLOSURE_NAME_MATCH": (
        "임대인은 계약 체결 시 신분증과 등기부상 소유자 일치 여부를 임차인이 확인할 수 있도록 협조한다.",
        "위험진단: 악성임대인 명단 동명 존재",
    ),
    "SEIZURE_CONFIRMED": (
        "임대인은 잔금일 전까지 압류·가압류를 해소하고 이를 증명하는 등기부를 제시하며, 미이행 시 계약은 무효로 하고 수령한 금원 전액을 즉시 반환한다.",
        "위험진단: 압류·가압류 확인",
    ),
}

# 상담사례 빈출 기본 특약 (938건 상담 데이터의 반복 분쟁 유형 기반)
_DEFAULT_TERMS: list[tuple[str, str]] = [
    (
        "임대인은 계약 기간 중 본 건 부동산을 매매하는 경우 매매계약 체결 전에 임차인에게 서면으로 고지한다.",
        "상담사례 빈출: 소유자 변경 미고지 분쟁",
    ),
    (
        "계약 종료 시 임대인은 보증금을 퇴거일에 즉시 반환하며, 지연 시 연 12%의 지연이자를 가산한다.",
        "상담사례 빈출: 보증금 반환 지연",
    ),
]


class EsignSessionRepository(BaseRepository):
    collection_name = "esign_sessions"

    async def find_by_code(self, code: str) -> dict | None:
        return await self.collection.find_one({"session_code": code, "status": {"$ne": "Cancelled"}})

    async def find_active_by_contract(self, contract_id: str) -> dict | None:
        return await self.collection.find_one(
            {"contract_id": contract_id, "status": {"$in": ["TermsAgreement", "Signing", "Anchored"]}}
        )


class EsignService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._sessions = EsignSessionRepository(db)
        self._contracts = ContractRepository(db)
        self._timeline = TimelineRepository(db)
        self._risk = RiskAssessmentRepository(db)
        self._blockchain = BlockchainService(db)
        self._notifications = NotificationService(db)

    # ---------- 세션 생성/참여/조회 ----------

    async def create_session(self, tenant_user_id: str, contract_id: str, display_name: str) -> EsignSessionResponse:
        contract = await self._contracts.get_by_id(contract_id)
        if not contract:
            raise ResourceNotFoundError("계약을 찾을 수 없습니다.")
        if contract.get("tenant_user_id") != tenant_user_id:
            raise PermissionDeniedError("본인 계약으로만 전자계약 세션을 만들 수 있습니다.")
        existing = await self._sessions.find_active_by_contract(contract_id)
        if existing:
            return _to_response(existing)

        terms = await self._recommend_terms(contract)
        now = now_kst_iso()
        doc = {
            "_id": new_uuid(),
            "session_code": secrets.token_hex(2).upper(),  # 예: '9F3A'
            "contract_id": contract_id,
            "status": "TermsAgreement",
            "participants": [
                {"role": "tenant", "user_id": tenant_user_id, "display_name": display_name,
                 "joined": True, "signed": False, "signed_at": None},
                {"role": "landlord", "user_id": contract.get("landlord_user_id"),
                 "display_name": None, "joined": False, "signed": False, "signed_at": None},
            ],
            "special_terms": terms,
            "contract_summary": _summary_of(contract),
            "contract_document": None,
            "contract_hash": None,
            "blockchain_tx_id": None,
            "tx_hash": None,
            "anchored_at": None,
            "created_at": now,
            "updated_at": now,
        }
        await self._sessions.insert(doc)
        return _to_response(doc)

    async def join(self, landlord_user_id: str, display_name: str, session_code: str) -> EsignSessionResponse:
        doc = await self._sessions.find_by_code(session_code.upper())
        if not doc:
            raise ResourceNotFoundError("세션 코드를 찾을 수 없습니다.")
        contract = await self._contracts.get_by_id(doc["contract_id"])
        bound = contract.get("landlord_user_id")
        if bound and bound != landlord_user_id:
            raise PermissionDeniedError("이 계약의 임대인으로 지정된 사용자가 아닙니다.")
        if not bound:
            await self._contracts.update_fields(
                doc["contract_id"], {"landlord_user_id": landlord_user_id, "updated_at": now_kst_iso()}
            )
        for p in doc["participants"]:
            if p["role"] == "landlord":
                p.update({"user_id": landlord_user_id, "display_name": display_name, "joined": True})
        doc["updated_at"] = now_kst_iso()
        await self._sessions.update_fields(
            doc["_id"], {"participants": doc["participants"], "updated_at": doc["updated_at"]}
        )
        tenant = _party(doc, "tenant")
        if tenant["user_id"]:
            await self._notifications.notify(
                user_id=tenant["user_id"], category="contract_event",
                title="임대인이 전자계약 세션에 참여했습니다",
                body=f"세션 {doc['session_code']} — 특약 합의를 진행하세요.",
                link=f"/contract/session/{doc['_id']}",
            )
        return _to_response(doc)

    async def get(self, session_id: str, user_id: str, role: str) -> EsignSessionResponse:
        doc = await self._require_participant(session_id, user_id, role)
        return _to_response(doc)

    # ---------- 특약 ----------

    async def propose_term(self, session_id: str, user_id: str, role: str, text: str) -> EsignSessionResponse:
        doc = await self._require_participant(session_id, user_id, role, statuses=("TermsAgreement",))
        doc["special_terms"].append({
            "term_id": new_uuid()[:8],
            "text": text,
            "source": role,
            "rationale": None,
            "status": "proposed",
            "agreed_by": [role],
        })
        return await self._save_terms(doc)

    async def act_on_term(
        self, session_id: str, term_id: str, user_id: str, role: str, action: str
    ) -> EsignSessionResponse:
        doc = await self._require_participant(session_id, user_id, role, statuses=("TermsAgreement",))
        term = next((t for t in doc["special_terms"] if t["term_id"] == term_id), None)
        if not term:
            raise ResourceNotFoundError("특약을 찾을 수 없습니다.")
        if action == "withdraw":
            if term["source"] not in ("ai_recommend", role):
                raise PermissionDeniedError("상대방이 제안한 특약은 철회할 수 없습니다. agree 하지 않으면 됩니다.")
            term["status"] = "withdrawn"
        else:  # agree
            if role not in term["agreed_by"]:
                term["agreed_by"].append(role)
            if {"tenant", "landlord"} <= set(term["agreed_by"]):
                term["status"] = "agreed"
        return await self._save_terms(doc)

    # ---------- 서명·앵커링 ----------

    async def sign(self, session_id: str, user_id: str, role: str) -> EsignSessionResponse:
        doc = await self._require_participant(session_id, user_id, role)
        if doc["status"] not in ("TermsAgreement", "Signing"):
            raise StateConflictError(f"현재 상태({doc['status']})에서는 서명할 수 없습니다.")
        if not all(p["joined"] for p in doc["participants"]):
            raise StateConflictError("양측이 모두 접속해야 서명할 수 있습니다.")
        pending = [t for t in doc["special_terms"] if t["status"] == "proposed"]
        if pending:
            raise StateConflictError(f"합의되지 않은 특약이 {len(pending)}건 있습니다. 합의 또는 철회 후 서명하세요.")

        now = now_kst_iso()
        me = _party(doc, role)
        if me["signed"]:
            return _to_response(doc)
        me.update({"signed": True, "signed_at": now})
        doc["status"] = "Signing"
        doc["updated_at"] = now

        other_role = "landlord" if role == "tenant" else "tenant"
        other = _party(doc, other_role)
        if other["user_id"]:
            await self._notifications.notify(
                user_id=other["user_id"], category="contract_event",
                title=f"{'임차인' if role == 'tenant' else '임대인'} 서명 완료",
                body="상대방이 서명했습니다. 서명을 완료하면 블록체인에 기록됩니다.",
                link=f"/contract/session/{doc['_id']}",
            )

        if all(p["signed"] for p in doc["participants"]):
            await self._anchor(doc)
        else:
            await self._sessions.update_fields(doc["_id"], {
                "participants": doc["participants"], "status": doc["status"], "updated_at": now,
            })
        return _to_response(doc)

    async def _anchor(self, doc: dict) -> None:
        now = now_kst_iso()
        document = {
            "contract_id": doc["contract_id"],
            "summary": doc["contract_summary"],
            "special_terms": [
                {"text": t["text"], "status": t["status"]}
                for t in doc["special_terms"] if t["status"] == "agreed"
            ],
            "signatures": [
                {"role": p["role"], "user_id": p["user_id"], "signed_at": p["signed_at"]}
                for p in doc["participants"]
            ],
        }
        contract_hash = sha256_json(document)
        anchor = await self._blockchain.anchor(AnchorRequest(
            event_type="ContractSigned",
            reference_id=doc["contract_id"],
            result_hash=contract_hash,
        ))
        doc.update({
            "status": "Anchored",
            "contract_document": document,
            "contract_hash": contract_hash,
            "blockchain_tx_id": anchor.blockchain_tx_id,
            "tx_hash": anchor.tx_hash,
            "anchored_at": now,
            "updated_at": now,
        })
        await self._sessions.update_fields(doc["_id"], {k: doc[k] for k in (
            "status", "participants", "contract_document", "contract_hash",
            "blockchain_tx_id", "tx_hash", "anchored_at", "updated_at",
        )})
        await self._contracts.update_fields(doc["contract_id"], {
            "contract_status": ContractStatus.CONTRACT_FINALIZED.value,
            "contract_hash": contract_hash,
            "updated_at": now,
        })
        await self._timeline.append({
            "_id": new_uuid(),
            "contract_id": doc["contract_id"],
            "event_type": "ContractSigned",
            "occurred_at": now,
            "blockchain_status": "Confirmed",
            "blockchain_tx_id": anchor.blockchain_tx_id,
        })
        for p in doc["participants"]:
            if p["user_id"]:
                await self._notifications.notify(
                    user_id=p["user_id"], category="contract_event",
                    title="전자계약이 블록체인에 기록되었습니다",
                    body=f"계약 해시 {contract_hash[:18]}… 가 앵커링되어 위변조를 검증할 수 있습니다.",
                    link=f"/contract/session/{doc['_id']}",
                )

    # ---------- 검증 ----------

    async def verify(
        self, contract_id: str, user_id: str, role: str, tampered_fields: dict | None
    ) -> EsignVerifyResponse:
        doc = await self._sessions.find_active_by_contract(contract_id)
        if not doc or doc["status"] != "Anchored":
            raise ResourceNotFoundError("앵커링된 전자계약이 없습니다.")
        if role not in ("hug_admin", "system_admin", "advisor"):
            if not any(p["user_id"] == user_id for p in doc["participants"]):
                raise PermissionDeniedError("계약 당사자만 검증할 수 있습니다.")

        document = dict(doc["contract_document"])
        if tampered_fields:
            summary = dict(document["summary"])
            summary.update(tampered_fields)
            document["summary"] = summary
        recomputed = sha256_json(document)
        tx = await self._blockchain.get_transaction(doc["blockchain_tx_id"])
        return EsignVerifyResponse(
            contract_id=contract_id,
            stored_hash=tx.result_hash,
            recomputed_hash=recomputed,
            match=recomputed == tx.result_hash,
            tampered_fields=tampered_fields,
            tx_hash=tx.tx_hash,
            blockchain_status=tx.blockchain_status,
            verified_at=now_kst_iso(),
        )

    # ---------- 내부 ----------

    async def _recommend_terms(self, contract: dict) -> list[dict]:
        terms: list[dict] = []
        risk_id = contract.get("risk_assessment_id")
        if risk_id:
            assessment = await self._risk.find_by_case_id(risk_id)
            if assessment:
                for factor in assessment.get("risk_factors", []):
                    template = _RISK_TERM_TEMPLATES.get(factor.get("code"))
                    if template:
                        terms.append(_term(template[0], template[1]))
        for text, rationale in _DEFAULT_TERMS:
            terms.append(_term(text, rationale))
        # 중복 텍스트 제거
        seen: set[str] = set()
        unique = []
        for t in terms:
            if t["text"] not in seen:
                seen.add(t["text"])
                unique.append(t)
        return unique

    async def _require_participant(
        self, session_id: str, user_id: str, role: str, statuses: tuple[str, ...] | None = None
    ) -> dict:
        doc = await self._sessions.get_by_id(session_id)
        if not doc:
            raise ResourceNotFoundError("전자계약 세션을 찾을 수 없습니다.")
        me = next((p for p in doc["participants"] if p["role"] == role), None)
        if not me or (me["user_id"] and me["user_id"] != user_id):
            raise PermissionDeniedError("이 세션의 당사자가 아닙니다.")
        if not me["user_id"]:
            raise PermissionDeniedError("세션 참여(join) 후 이용할 수 있습니다.")
        if statuses and doc["status"] not in statuses:
            raise StateConflictError(f"현재 상태({doc['status']})에서는 이 작업을 할 수 없습니다.")
        return doc

    async def _save_terms(self, doc: dict) -> EsignSessionResponse:
        doc["updated_at"] = now_kst_iso()
        await self._sessions.update_fields(
            doc["_id"], {"special_terms": doc["special_terms"], "updated_at": doc["updated_at"]}
        )
        return _to_response(doc)


def _term(text: str, rationale: str) -> dict:
    return {
        "term_id": new_uuid()[:8],
        "text": text,
        "source": "ai_recommend",
        "rationale": rationale,
        "status": "proposed",
        "agreed_by": [],
    }


def _party(doc: dict, role: str) -> dict:
    return next(p for p in doc["participants"] if p["role"] == role)


def _summary_of(contract: dict) -> dict:
    return {
        "property_id": contract["property_id"],
        "deposit": contract["deposit"],
        "contract_start_date": contract["contract_start_date"],
        "contract_end_date": contract["contract_end_date"],
        "landlord_type": contract["landlord_type"],
        "housing_type": contract["housing_type"],
    }


def _to_response(doc: dict) -> EsignSessionResponse:
    return EsignSessionResponse(
        session_id=doc["_id"],
        session_code=doc["session_code"],
        contract_id=doc["contract_id"],
        status=doc["status"],
        participants=[Participant(**p) for p in doc["participants"]],
        special_terms=[SpecialTerm(**t) for t in doc["special_terms"]],
        contract_summary=doc["contract_summary"],
        contract_hash=doc.get("contract_hash"),
        blockchain_tx_id=doc.get("blockchain_tx_id"),
        tx_hash=doc.get("tx_hash"),
        anchored_at=doc.get("anchored_at"),
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.exceptions import (
    PermissionDeniedError,
    ResourceNotFoundError,
    StateConflictError,
    ValidationAppError,
)
from app.models.enums import (
    MANAGED_CONTRACT_STATUSES,
    REPAYMENT_CAPABILITY_EVIDENCE_TYPES,
    ContractStatus,
    VerificationStatus,
)
from app.repositories.contract_repository import ContractRepository, TimelineRepository
from app.repositories.evidence_repository import (
    EvidenceRepository,
    EvidenceRequestRepository,
    VerificationRepository,
)
from app.repositories.prevention_repository import EvidenceBundleRepository
from app.schemas.common import build_pagination
from app.schemas.blockchain import AnchorRequest
from app.schemas.evidence import (
    EvidenceRequestCreateRequest,
    EvidenceRequestResponse,
    EvidenceResponse,
    VerificationDecisionRequest,
    VerificationResponse,
)
from app.services.blockchain_service import BlockchainService
from app.utils.datetime_utils import now_kst_iso, new_uuid
from app.utils.hashing import sha256_bytes

STORAGE_ROOT = Path(__file__).resolve().parents[2] / "storage_data" / "evidence"
ALLOWED_CONTENT_TYPES = {"application/pdf", "image/png", "image/jpeg"}
CONTENT_TYPE_EXTENSIONS = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
}
MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024

_BUNDLE_SUBMITTED_STATUSES = {
    VerificationStatus.SUBMITTED.value,
    VerificationStatus.REVIEWING.value,
    VerificationStatus.VERIFIED.value,
}


def _request_to_response(doc: dict, latest_evidence_id: str | None = None) -> EvidenceRequestResponse:
    return EvidenceRequestResponse(
        evidence_request_id=doc["_id"],
        contract_id=doc["contract_id"],
        risk_assessment_id=doc.get("risk_assessment_id"),
        reason=doc["reason"],
        evidence_type=doc["evidence_type"],
        due_date=doc.get("due_date"),
        verification_status=doc["verification_status"],
        latest_evidence_id=latest_evidence_id,
        bundle_id=doc.get("bundle_id"),
        item_key=doc.get("item_key"),
        checkpoint=doc.get("checkpoint"),
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


class EvidenceService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._requests = EvidenceRequestRepository(db)
        self._evidences = EvidenceRepository(db)
        self._verifications = VerificationRepository(db)
        self._contracts = ContractRepository(db)
        self._timeline = TimelineRepository(db)
        self._bundles = EvidenceBundleRepository(db)
        self._blockchain = BlockchainService(db)

    _INTERNAL_ROLES = {"advisor", "verifier", "hug_admin", "system_admin"}

    async def _authorize_contract(
        self, contract_id: str, user_id: str | None, role: str | None
    ) -> dict:
        contract = await self._contracts.get_by_id(contract_id)
        if not contract:
            raise ResourceNotFoundError("계약 정보를 찾을 수 없습니다.")
        if role in self._INTERNAL_ROLES or (user_id is None and role is None):
            return contract
        if user_id not in (contract.get("tenant_user_id"), contract.get("landlord_user_id")):
            raise PermissionDeniedError("해당 계약의 증빙에 접근할 권한이 없습니다.")
        return contract

    async def create_request(
        self,
        payload: EvidenceRequestCreateRequest,
        actor_user_id: str | None = None,
        actor_role: str | None = None,
    ) -> EvidenceRequestResponse:
        contract = await self._authorize_contract(payload.contract_id, actor_user_id, actor_role)
        now = now_kst_iso()
        doc = {
            "_id": new_uuid(),
            "contract_id": payload.contract_id,
            "risk_assessment_id": payload.risk_assessment_id,
            "reason": payload.reason,
            "evidence_type": payload.evidence_type.value,
            "due_date": payload.due_date.isoformat() if payload.due_date else None,
            "verification_status": VerificationStatus.PENDING.value,
            "bundle_id": payload.bundle_id,
            "item_key": payload.item_key,
            "checkpoint": payload.checkpoint,
            "created_at": now,
            "updated_at": now,
        }
        await self._requests.insert(doc)

        # 상태 전이(19.2): 관리 국면(계약 후) 계약은 진행중 상태로 강등하지 않는다.
        # 상환능력 트랙 요청이면 확정/모니터링 상태를 D90Requested로 올려 사전 확보 국면을 표시한다.
        current_status = contract["contract_status"]
        timeline_event = "EvidenceRequested"
        if current_status in MANAGED_CONTRACT_STATUSES:
            if payload.evidence_type.value in REPAYMENT_CAPABILITY_EVIDENCE_TYPES and current_status in (
                ContractStatus.CONTRACT_FINALIZED.value,
                ContractStatus.MONITORING.value,
            ):
                await self._contracts.update_fields(
                    payload.contract_id,
                    {"contract_status": ContractStatus.D90_REQUESTED.value, "updated_at": now},
                )
                timeline_event = "D90Requested"
            else:
                await self._contracts.update_fields(payload.contract_id, {"updated_at": now})
        else:
            await self._contracts.update_fields(
                payload.contract_id, {"contract_status": "EvidenceRequested", "updated_at": now}
            )
        await self._timeline.append(
            {
                "_id": new_uuid(),
                "contract_id": payload.contract_id,
                "event_type": timeline_event,
                "occurred_at": now,
                "blockchain_status": "NotRequested",
                "blockchain_tx_id": None,
            }
        )
        return _request_to_response(doc)

    async def get_request(
        self, evidence_request_id: str, user_id: str | None = None, role: str | None = None
    ) -> EvidenceRequestResponse:
        doc = await self._requests.get_by_id(evidence_request_id)
        if not doc:
            raise ResourceNotFoundError("보완요청 정보를 찾을 수 없습니다.")
        await self._authorize_contract(doc["contract_id"], user_id, role)
        return _request_to_response(doc, await self._latest_evidence_id(doc["_id"]))

    async def list_requests(
        self,
        page: int,
        size: int,
        case_id: str | None,
        contract_id: str | None,
        user_id: str | None = None,
        role: str | None = None,
    ):
        visible_contract_ids: list[str] | None = None
        if role not in self._INTERNAL_ROLES:
            if contract_id:
                await self._authorize_contract(contract_id, user_id, role)
            else:
                cursor = self._contracts.collection.find(
                    {"$or": [{"tenant_user_id": user_id}, {"landlord_user_id": user_id}]},
                    {"_id": 1},
                )
                visible_contract_ids = [doc["_id"] async for doc in cursor]
        items, total = await self._requests.list_paginated(
            (page - 1) * size,
            size,
            case_id=case_id,
            contract_id=contract_id,
            visible_contract_ids=visible_contract_ids,
        )
        responses = [_request_to_response(i, await self._latest_evidence_id(i["_id"])) for i in items]
        return responses, build_pagination(page, size, total)

    async def _latest_evidence_id(self, evidence_request_id: str) -> str | None:
        evidences = await self._evidences.list_for_request(evidence_request_id)
        return evidences[0]["_id"] if evidences else None

    @staticmethod
    def _is_overdue(due_at: Any, as_of: date, is_verified: bool) -> bool:
        if is_verified or not due_at:
            return False
        try:
            return as_of > date.fromisoformat(str(due_at)[:10])
        except ValueError:
            # 잘못된 기한 값은 검증 완료로 오인하지 않되 여기서 임의로 기한초과 처리하지 않는다.
            return False

    async def _sync_bundle_for_request(
        self, request_doc: dict[str, Any], *, now: str
    ) -> dict[str, Any] | None:
        """증빙 요청 상태를 소속 bundle 집계와 항목 스냅샷에 즉시 반영한다."""
        bundle_id = request_doc.get("bundle_id")
        if not bundle_id:
            return None
        bundle = await self._bundles.get_by_id(bundle_id)
        if not bundle or bundle.get("contract_id") != request_doc.get("contract_id"):
            return None

        items = list(bundle.get("items") or [])
        request_ids = [item.get("evidence_request_id") for item in items]
        if request_doc.get("_id") not in request_ids:
            # 클라이언트가 임의 bundle_id를 지정해 다른 bundle 집계를 바꾸지 못하게 한다.
            return None

        valid_request_ids = [request_id for request_id in request_ids if request_id]
        cursor = self._requests.collection.find({"_id": {"$in": valid_request_ids}})
        requests_by_id = {document["_id"]: document async for document in cursor}
        as_of = date.fromisoformat(now[:10])
        synchronized_items: list[dict[str, Any]] = []
        for item in items:
            synchronized = dict(item)
            linked_request = requests_by_id.get(item.get("evidence_request_id"))
            verification_status = (
                linked_request.get("verification_status", VerificationStatus.PENDING.value)
                if linked_request
                else VerificationStatus.PENDING.value
            )
            is_verified = verification_status == VerificationStatus.VERIFIED.value
            synchronized.update(
                {
                    "verification_status": verification_status,
                    "is_verified": is_verified,
                    "is_overdue": self._is_overdue(
                        item.get("due_at") or bundle.get("due_at"), as_of, is_verified
                    ),
                }
            )
            synchronized_items.append(synchronized)

        required_count = len(synchronized_items)
        submitted_count = sum(
            item["verification_status"] in _BUNDLE_SUBMITTED_STATUSES
            for item in synchronized_items
        )
        verified_count = sum(item["is_verified"] for item in synchronized_items)
        overdue_count = sum(item["is_overdue"] for item in synchronized_items)
        if required_count and verified_count == required_count:
            status = "Completed"
        elif overdue_count:
            status = "Overdue"
        elif submitted_count:
            status = "InReview"
        else:
            status = "Pending"

        fields = {
            "status": status,
            "required_count": required_count,
            "submitted_count": submitted_count,
            "verified_count": verified_count,
            "overdue_count": overdue_count,
            "completion_ratio": round(verified_count / required_count, 4)
            if required_count
            else 0.0,
            "items": synchronized_items,
            "updated_at": now,
        }
        return await self._bundles.update_fields(bundle_id, fields)

    async def _all_required_bundles_completed(self, contract_id: str) -> bool:
        bundles = await self._bundles.list_for_contract(contract_id)
        return bool(bundles) and all(
            bool(bundle.get("required_count"))
            and bundle.get("verified_count") == bundle.get("required_count")
            and bundle.get("status") == "Completed"
            for bundle in bundles
        )

    async def submit_evidence(
        self,
        evidence_request_id: str,
        uploader_id: str,
        file: UploadFile,
        uploader_role: str = "landlord",
    ) -> EvidenceResponse:
        request_doc = await self._requests.get_by_id(evidence_request_id)
        if not request_doc:
            raise ResourceNotFoundError("보완요청 정보를 찾을 수 없습니다.")
        contract = await self._authorize_contract(
            request_doc["contract_id"], uploader_id, uploader_role
        )
        if uploader_role == "landlord" and contract.get("landlord_user_id") != uploader_id:
            raise PermissionDeniedError("해당 계약의 임대인만 증빙을 제출할 수 있습니다.")

        if file.content_type not in ALLOWED_CONTENT_TYPES:
            raise ValidationAppError(
                "허용되지 않는 파일 형식입니다.", details={"allowed": sorted(ALLOWED_CONTENT_TYPES)}
            )

        content = await file.read()
        if len(content) > MAX_FILE_SIZE_BYTES:
            raise ValidationAppError("파일 크기가 20MB를 초과했습니다.")

        document_hash = sha256_bytes(content)
        duplicate = await self._evidences.find_duplicate(evidence_request_id, document_hash)
        if duplicate:
            raise StateConflictError("동일한 파일이 이미 제출되었습니다.")

        storage_root = STORAGE_ROOT.resolve()
        storage_root.mkdir(parents=True, exist_ok=True)
        evidence_id = new_uuid()
        # 저장 경로에는 client filename을 절대 사용하지 않는다. UUID와 검증된
        # content-type 확장자만 사용하고 resolve 결과가 storage root 바로 아래인지 확인한다.
        object_path = (storage_root / f"{evidence_id}{CONTENT_TYPE_EXTENSIONS[file.content_type]}").resolve()
        if object_path.parent != storage_root:
            raise ValidationAppError("안전한 증빙 저장 경로를 생성하지 못했습니다.")
        object_path.write_bytes(content)

        original_name = str(file.filename or "evidence").replace("\\", "/").rsplit("/", 1)[-1]
        if original_name in {"", ".", ".."}:
            original_name = f"evidence{CONTENT_TYPE_EXTENSIONS[file.content_type]}"
        original_name = original_name[:255]

        now = now_kst_iso()
        doc = {
            "_id": evidence_id,
            "evidence_request_id": evidence_request_id,
            "uploader_id": uploader_id,
            "file_name": original_name,
            "content_type": file.content_type,
            "size_bytes": len(content),
            "object_uri": f"file://{object_path}",
            "document_hash": document_hash,
            "verification_status": VerificationStatus.SUBMITTED.value,
            "submitted_at": now,
        }
        await self._evidences.insert(doc)
        await self._requests.update_fields(
            evidence_request_id,
            {
                "verification_status": VerificationStatus.SUBMITTED.value,
                "updated_at": now,
            },
        )
        request_doc = await self._requests.get_by_id(evidence_request_id) or request_doc
        await self._sync_bundle_for_request(request_doc, now=now)
        # 관리 국면(계약 후) 계약은 제출로 진행중 상태(EvidenceSubmitted)로 강등하지 않는다(19.2).
        contract = await self._contracts.get_by_id(request_doc["contract_id"])
        if contract and contract["contract_status"] in MANAGED_CONTRACT_STATUSES:
            await self._contracts.update_fields(request_doc["contract_id"], {"updated_at": now})
        else:
            await self._contracts.update_fields(
                request_doc["contract_id"], {"contract_status": "EvidenceSubmitted", "updated_at": now}
            )
        await self._timeline.append(
            {
                "_id": new_uuid(),
                "contract_id": request_doc["contract_id"],
                "event_type": "EvidenceSubmitted",
                "occurred_at": now,
                "blockchain_status": "NotRequested",
                "blockchain_tx_id": None,
            }
        )

        return EvidenceResponse(
            evidence_id=doc["_id"],
            evidence_request_id=doc["evidence_request_id"],
            file_name=doc["file_name"],
            document_hash=doc["document_hash"],
            verification_status=doc["verification_status"],
            submitted_at=doc["submitted_at"],
        )

    async def get_verification(
        self, evidence_id: str, user_id: str | None = None, role: str | None = None
    ) -> VerificationResponse:
        evidence_doc = await self._evidences.get_by_id(evidence_id)
        if not evidence_doc:
            raise ResourceNotFoundError("증빙 정보를 찾을 수 없습니다.")
        request_doc = await self._requests.get_by_id(evidence_doc["evidence_request_id"])
        if not request_doc:
            raise ResourceNotFoundError("보완요청 정보를 찾을 수 없습니다.")
        await self._authorize_contract(request_doc["contract_id"], user_id, role)
        verification = await self._verifications.find_by_evidence(evidence_id)
        if not verification:
            # 아직 결정 전이면 Evidence 상태만으로 가심사 상태를 구성한다.
            return VerificationResponse(
                verification_id="",
                evidence_id=evidence_id,
                verification_status=evidence_doc.get(
                    "verification_status", VerificationStatus.SUBMITTED.value
                ),
                reviewer_comment=None,
                resubmission_required=False,
                blockchain_tx_id=None,
            )
        return _verification_to_response(verification)

    async def decide_verification(
        self, evidence_id: str, reviewer_user_id: str, payload: VerificationDecisionRequest
    ) -> VerificationResponse:
        evidence = await self._evidences.get_by_id(evidence_id)
        if not evidence:
            raise ResourceNotFoundError("증빙 정보를 찾을 수 없습니다.")

        status_map = {
            "approve": VerificationStatus.VERIFIED.value,
            "reject": VerificationStatus.REJECTED.value,
            "hold": VerificationStatus.REVIEWING.value,
        }
        new_status = status_map[payload.decision]
        now = now_kst_iso()

        existing = await self._verifications.find_by_evidence(evidence_id)
        verification_id = existing["_id"] if existing else new_uuid()
        doc = {
            "_id": verification_id,
            "evidence_id": evidence_id,
            "evidence_request_id": evidence["evidence_request_id"],
            "verification_status": new_status,
            "reviewer_user_id": reviewer_user_id,
            "reviewer_comment": payload.reviewer_comment,
            "resubmission_required": payload.decision == "reject",
            "blockchain_tx_id": existing.get("blockchain_tx_id") if existing else None,
            "decided_at": now,
            "created_at": existing["created_at"] if existing else now,
        }
        # 승인 시 검증 결과 해시를 체인(현재 Mock)에 앵커해 위험 보완 사실을 공증한다(기획서 2절).
        if payload.decision == "approve" and not doc["blockchain_tx_id"]:
            anchor = await self._blockchain.anchor(
                AnchorRequest(
                    event_type="VerificationCompleted",
                    reference_id=verification_id,
                    result_hash=evidence.get("document_hash"),
                )
            )
            doc["blockchain_tx_id"] = anchor.blockchain_tx_id

        await self._verifications.collection.update_one({"_id": verification_id}, {"$set": doc}, upsert=True)
        await self._evidences.update_fields(evidence_id, {"verification_status": new_status})

        contract_status_by_decision = {
            "approve": ContractStatus.VERIFIED.value,
            "reject": ContractStatus.EVIDENCE_REQUESTED.value,
            "hold": ContractStatus.EVIDENCE_SUBMITTED.value,
        }
        await self._requests.update_fields(
            evidence["evidence_request_id"], {"verification_status": new_status, "updated_at": now}
        )

        request_doc = await self._requests.get_by_id(evidence["evidence_request_id"])
        if request_doc:
            synchronized_bundle = await self._sync_bundle_for_request(request_doc, now=now)
            # 관리 국면(계약 후) 계약은 검증 결정으로 진행중 상태로 강등하지 않는다(19.2).
            # bundle에 묶인 모든 필수 증빙이 완료된 경우에만 D90Requested → Monitoring으로 복귀한다.
            contract = await self._contracts.get_by_id(request_doc["contract_id"])
            if contract and contract["contract_status"] in MANAGED_CONTRACT_STATUSES:
                if (
                    payload.decision == "approve"
                    and contract["contract_status"] == ContractStatus.D90_REQUESTED.value
                    and synchronized_bundle is not None
                    and await self._all_required_bundles_completed(request_doc["contract_id"])
                ):
                    await self._contracts.update_fields(
                        request_doc["contract_id"],
                        {"contract_status": ContractStatus.MONITORING.value, "updated_at": now},
                    )
                else:
                    await self._contracts.update_fields(request_doc["contract_id"], {"updated_at": now})
            else:
                await self._contracts.update_fields(
                    request_doc["contract_id"],
                    {
                        "contract_status": contract_status_by_decision[payload.decision],
                        "updated_at": now,
                    },
                )
            await self._timeline.append(
                {
                    "_id": new_uuid(),
                    "contract_id": request_doc["contract_id"],
                    "event_type": {
                        "approve": "VerificationCompleted",
                        "reject": "VerificationRejected",
                        "hold": "VerificationHeld",
                    }[payload.decision],
                    "occurred_at": now,
                    "blockchain_status": "Confirmed" if doc["blockchain_tx_id"] else "NotRequested",
                    "blockchain_tx_id": doc["blockchain_tx_id"],
                }
            )

        return _verification_to_response(doc)


def _verification_to_response(doc: dict) -> VerificationResponse:
    return VerificationResponse(
        verification_id=doc["_id"],
        evidence_id=doc["evidence_id"],
        verification_status=doc["verification_status"],
        reviewer_comment=doc.get("reviewer_comment"),
        resubmission_required=doc.get("resubmission_required", False),
        blockchain_tx_id=doc.get("blockchain_tx_id"),
    )

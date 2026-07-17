from __future__ import annotations

from pathlib import Path

from fastapi import UploadFile
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.exceptions import ResourceNotFoundError, StateConflictError, ValidationAppError
from app.models.enums import VerificationStatus
from app.repositories.contract_repository import ContractRepository, TimelineRepository
from app.repositories.evidence_repository import EvidenceRepository, EvidenceRequestRepository, VerificationRepository
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
MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024


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
        self._blockchain = BlockchainService(db)

    async def create_request(self, payload: EvidenceRequestCreateRequest) -> EvidenceRequestResponse:
        if not await self._contracts.exists(payload.contract_id):
            raise ResourceNotFoundError("계약 정보를 찾을 수 없습니다.")
        now = now_kst_iso()
        doc = {
            "_id": new_uuid(),
            "contract_id": payload.contract_id,
            "risk_assessment_id": payload.risk_assessment_id,
            "reason": payload.reason,
            "evidence_type": payload.evidence_type.value,
            "due_date": payload.due_date.isoformat() if payload.due_date else None,
            "verification_status": VerificationStatus.PENDING.value,
            "created_at": now,
            "updated_at": now,
        }
        await self._requests.insert(doc)
        await self._contracts.update_fields(
            payload.contract_id, {"contract_status": "EvidenceRequested", "updated_at": now}
        )
        return _request_to_response(doc)

    async def get_request(self, evidence_request_id: str) -> EvidenceRequestResponse:
        doc = await self._requests.get_by_id(evidence_request_id)
        if not doc:
            raise ResourceNotFoundError("보완요청 정보를 찾을 수 없습니다.")
        return _request_to_response(doc, await self._latest_evidence_id(doc["_id"]))

    async def list_requests(self, page: int, size: int, case_id: str | None, contract_id: str | None):
        items, total = await self._requests.list_paginated((page - 1) * size, size, case_id=case_id, contract_id=contract_id)
        responses = [_request_to_response(i, await self._latest_evidence_id(i["_id"])) for i in items]
        return responses, build_pagination(page, size, total)

    async def _latest_evidence_id(self, evidence_request_id: str) -> str | None:
        evidences = await self._evidences.list_for_request(evidence_request_id)
        return evidences[0]["_id"] if evidences else None

    async def submit_evidence(self, evidence_request_id: str, uploader_id: str, file: UploadFile) -> EvidenceResponse:
        request_doc = await self._requests.get_by_id(evidence_request_id)
        if not request_doc:
            raise ResourceNotFoundError("보완요청 정보를 찾을 수 없습니다.")

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

        STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
        evidence_id = new_uuid()
        object_path = STORAGE_ROOT / f"{evidence_id}_{file.filename}"
        object_path.write_bytes(content)

        now = now_kst_iso()
        doc = {
            "_id": evidence_id,
            "evidence_request_id": evidence_request_id,
            "uploader_id": uploader_id,
            "file_name": file.filename,
            "content_type": file.content_type,
            "size_bytes": len(content),
            "object_uri": f"file://{object_path}",
            "document_hash": document_hash,
            "verification_status": VerificationStatus.SUBMITTED.value,
            "submitted_at": now,
        }
        await self._evidences.insert(doc)
        await self._requests.update_fields(
            evidence_request_id, {"verification_status": VerificationStatus.SUBMITTED.value, "updated_at": now}
        )
        await self._contracts.update_fields(
            request_doc["contract_id"], {"contract_status": "EvidenceSubmitted", "updated_at": now}
        )

        return EvidenceResponse(
            evidence_id=doc["_id"],
            evidence_request_id=doc["evidence_request_id"],
            file_name=doc["file_name"],
            document_hash=doc["document_hash"],
            verification_status=doc["verification_status"],
            submitted_at=doc["submitted_at"],
        )

    async def get_verification(self, evidence_id: str) -> VerificationResponse:
        verification = await self._verifications.find_by_evidence(evidence_id)
        if not verification:
            # 아직 결정 전이면 Evidence 상태만으로 가심사 상태를 구성한다.
            evidence = await self._evidences.get_by_id(evidence_id)
            if not evidence:
                raise ResourceNotFoundError("증빙 정보를 찾을 수 없습니다.")
            return VerificationResponse(
                verification_id="",
                evidence_id=evidence_id,
                verification_status=evidence.get("verification_status", VerificationStatus.SUBMITTED.value),
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

        request_status = "EvidenceRequested" if payload.decision == "reject" else "Verified"
        await self._requests.update_fields(
            evidence["evidence_request_id"], {"verification_status": new_status, "updated_at": now}
        )

        request_doc = await self._requests.get_by_id(evidence["evidence_request_id"])
        if request_doc:
            await self._contracts.update_fields(request_doc["contract_id"], {"contract_status": request_status, "updated_at": now})
            await self._timeline.append(
                {
                    "_id": new_uuid(),
                    "contract_id": request_doc["contract_id"],
                    "event_type": "VerificationCompleted",
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

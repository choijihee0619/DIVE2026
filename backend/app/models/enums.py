"""API_Contract_260714.yaml 공통 Enum (구현에 사용하는 것만 발췌). 값 표기는 계약과 동일하게 유지한다."""

from __future__ import annotations

from enum import StrEnum


class UserRole(StrEnum):
    TENANT = "tenant"
    LANDLORD = "landlord"
    ADVISOR = "advisor"
    HUG_ADMIN = "hug_admin"
    SYSTEM_ADMIN = "system_admin"
    VERIFIER = "verifier"


class ContractStatus(StrEnum):
    DRAFT = "Draft"
    DIAGNOSED = "Diagnosed"
    EVIDENCE_REQUESTED = "EvidenceRequested"
    EVIDENCE_SUBMITTED = "EvidenceSubmitted"
    VERIFIED = "Verified"
    CONTRACT_FINALIZED = "ContractFinalized"
    MONITORING = "Monitoring"
    D90_REQUESTED = "D90Requested"
    RETURN_PLAN_SUBMITTED = "ReturnPlanSubmitted"
    AT_RISK = "AtRisk"
    INCIDENT_REPORTED = "IncidentReported"
    TRANSFERRED_TO_HUG = "TransferredToHUG"
    RECOVERY_IN_PROGRESS = "RecoveryInProgress"
    CLOSED = "Closed"


class VerificationStatus(StrEnum):
    PENDING = "Pending"
    SUBMITTED = "Submitted"
    REVIEWING = "Reviewing"
    VERIFIED = "Verified"
    REJECTED = "Rejected"
    EXPIRED = "Expired"


class BlockchainStatus(StrEnum):
    NOT_REQUESTED = "NotRequested"
    PENDING = "Pending"
    CONFIRMED = "Confirmed"
    FAILED = "Failed"


class APIResultStatus(StrEnum):
    SUCCESS = "Success"
    PARTIAL = "Partial"
    FAILED = "Failed"
    MOCK_FALLBACK = "MockFallback"


class RiskGrade(StrEnum):
    """⚠ 위험등급은 A/B/C가 아니라 API_Contract의 LOW/MEDIUM/HIGH 3단계를 그대로 사용한다.

    (Backend_API_명세서 7.2절, ML개발가이드 21장 모두 LOW/MEDIUM/HIGH만 정의하며 A/B/C 표기는
    어떤 선행 문서에도 없다. 우선순위 규칙에 따라 계약 enum을 따른다.)
    """

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class LandlordType(StrEnum):
    INDIVIDUAL = "INDIVIDUAL"
    INDIVIDUAL_BUSINESS = "INDIVIDUAL_BUSINESS"
    CORPORATION = "CORPORATION"


class HousingType(StrEnum):
    MULTI_HOUSEHOLD = "MULTI_HOUSEHOLD"
    MULTI_FAMILY = "MULTI_FAMILY"
    APARTMENT = "APARTMENT"
    OFFICETEL = "OFFICETEL"
    SINGLE_FAMILY = "SINGLE_FAMILY"
    ROW_HOUSE = "ROW_HOUSE"
    OTHER = "OTHER"


class EvidenceType(StrEnum):
    REGISTRY_CANCELLATION_PROOF = "REGISTRY_CANCELLATION_PROOF"
    BUSINESS_STATUS_PROOF = "BUSINESS_STATUS_PROOF"
    OWNERSHIP_PROOF = "OWNERSHIP_PROOF"
    INSURANCE_PROOF = "INSURANCE_PROOF"
    RETURN_PLAN_DOCUMENT = "RETURN_PLAN_DOCUMENT"
    CONTRACT_DOCUMENT = "CONTRACT_DOCUMENT"
    OTHER = "OTHER"

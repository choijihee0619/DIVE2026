/**
 * backend/app/models/enums.py와 값 문자열까지 1:1로 맞춘 공통 식별자/상태 타입.
 * 이 파일이 아니라 enums.py가 바뀌면 이 파일을 갱신한다(문서-코드 불일치 방지, 명세서 14장).
 */

export const UserRole = {
  TENANT: "tenant",
  LANDLORD: "landlord",
  ADVISOR: "advisor",
  HUG_ADMIN: "hug_admin",
  SYSTEM_ADMIN: "system_admin",
  VERIFIER: "verifier",
} as const;
export type UserRole = (typeof UserRole)[keyof typeof UserRole];

export const ContractStatus = {
  DRAFT: "Draft",
  DIAGNOSED: "Diagnosed",
  EVIDENCE_REQUESTED: "EvidenceRequested",
  EVIDENCE_SUBMITTED: "EvidenceSubmitted",
  VERIFIED: "Verified",
  CONTRACT_FINALIZED: "ContractFinalized",
  MONITORING: "Monitoring",
  D90_REQUESTED: "D90Requested",
  RETURN_PLAN_SUBMITTED: "ReturnPlanSubmitted",
  AT_RISK: "AtRisk",
  INCIDENT_REPORTED: "IncidentReported",
  TRANSFERRED_TO_HUG: "TransferredToHUG",
  RECOVERY_IN_PROGRESS: "RecoveryInProgress",
  CLOSED: "Closed",
} as const;
export type ContractStatus = (typeof ContractStatus)[keyof typeof ContractStatus];

export const VerificationStatus = {
  PENDING: "Pending",
  SUBMITTED: "Submitted",
  REVIEWING: "Reviewing",
  VERIFIED: "Verified",
  REJECTED: "Rejected",
  EXPIRED: "Expired",
} as const;
export type VerificationStatus = (typeof VerificationStatus)[keyof typeof VerificationStatus];

export const BlockchainStatus = {
  NOT_REQUESTED: "NotRequested",
  PENDING: "Pending",
  CONFIRMED: "Confirmed",
  FAILED: "Failed",
} as const;
export type BlockchainStatus = (typeof BlockchainStatus)[keyof typeof BlockchainStatus];

export const APIResultStatus = {
  SUCCESS: "Success",
  PARTIAL: "Partial",
  FAILED: "Failed",
  MOCK_FALLBACK: "MockFallback",
} as const;
export type APIResultStatus = (typeof APIResultStatus)[keyof typeof APIResultStatus];

/** 위험등급은 A/B/C가 아니라 LOW/MEDIUM/HIGH 3단계다(backend/README.md 8절 충돌사항 1번). */
export const RiskGrade = {
  LOW: "LOW",
  MEDIUM: "MEDIUM",
  HIGH: "HIGH",
} as const;
export type RiskGrade = (typeof RiskGrade)[keyof typeof RiskGrade];

export const LandlordType = {
  INDIVIDUAL: "INDIVIDUAL",
  INDIVIDUAL_BUSINESS: "INDIVIDUAL_BUSINESS",
  CORPORATION: "CORPORATION",
} as const;
export type LandlordType = (typeof LandlordType)[keyof typeof LandlordType];

export const HousingType = {
  MULTI_HOUSEHOLD: "MULTI_HOUSEHOLD",
  MULTI_FAMILY: "MULTI_FAMILY",
  APARTMENT: "APARTMENT",
  OFFICETEL: "OFFICETEL",
  SINGLE_FAMILY: "SINGLE_FAMILY",
  ROW_HOUSE: "ROW_HOUSE",
  OTHER: "OTHER",
} as const;
export type HousingType = (typeof HousingType)[keyof typeof HousingType];

export const EvidenceType = {
  REGISTRY_CANCELLATION_PROOF: "REGISTRY_CANCELLATION_PROOF",
  BUSINESS_STATUS_PROOF: "BUSINESS_STATUS_PROOF",
  OWNERSHIP_PROOF: "OWNERSHIP_PROOF",
  INSURANCE_PROOF: "INSURANCE_PROOF",
  RETURN_PLAN_DOCUMENT: "RETURN_PLAN_DOCUMENT",
  CONTRACT_DOCUMENT: "CONTRACT_DOCUMENT",
  // 임대인 보증금 상환능력 트랙 (README §19.2)
  INCOME_EMPLOYMENT_PROOF: "INCOME_EMPLOYMENT_PROOF",
  DEPOSIT_RETURN_HISTORY: "DEPOSIT_RETURN_HISTORY",
  LOAN_LIMIT_PROOF: "LOAN_LIMIT_PROOF",
  ASSET_PROOF: "ASSET_PROOF",
  OTHER: "OTHER",
} as const;
export type EvidenceType = (typeof EvidenceType)[keyof typeof EvidenceType];

/** 임대인 보증금 상환능력 증빙 유형(19.2) — backend enums.py REPAYMENT_CAPABILITY_EVIDENCE_TYPES와 1:1. */
export const REPAYMENT_EVIDENCE_TYPES: EvidenceType[] = [
  EvidenceType.INCOME_EMPLOYMENT_PROOF,
  EvidenceType.DEPOSIT_RETURN_HISTORY,
  EvidenceType.LOAN_LIMIT_PROOF,
  EvidenceType.ASSET_PROOF,
];

/** 역할별 홈 라우트(AUTH-01 로그인 후 분기, Frontend_UIUX_명세서 5.23절). */
export const ROLE_HOME_ROUTE: Record<UserRole, string> = {
  [UserRole.TENANT]: "/tenant",
  [UserRole.LANDLORD]: "/landlord",
  [UserRole.ADVISOR]: "/advisor",
  [UserRole.HUG_ADMIN]: "/hug/dashboard",
  [UserRole.SYSTEM_ADMIN]: "/admin",
  [UserRole.VERIFIER]: "/advisor",
};

/** 라우트 그룹별 허용 role(Frontend_UIUX_명세서 3장). */
export const ROUTE_GROUP_ROLES: Record<string, UserRole[]> = {
  "/tenant": [UserRole.TENANT],
  "/landlord": [UserRole.LANDLORD],
  "/advisor": [UserRole.ADVISOR, UserRole.VERIFIER],
  "/hug": [UserRole.HUG_ADMIN],
  "/admin": [UserRole.SYSTEM_ADMIN],
};

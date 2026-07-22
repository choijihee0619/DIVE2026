/** backend/app/models/enums.py의 값과 1:1로 맞춘 한글 라벨(계약 상태 외 도메인). */

export const EVIDENCE_TYPE_LABEL: Record<string, string> = {
  REGISTRY_CANCELLATION_PROOF: "근저당 말소 증빙",
  BUSINESS_STATUS_PROOF: "사업자 상태 증빙",
  OWNERSHIP_PROOF: "소유권 증빙",
  INSURANCE_PROOF: "보증보험 증빙",
  RETURN_PLAN_DOCUMENT: "반환계획 문서",
  CONTRACT_DOCUMENT: "계약 문서",
  INCOME_EMPLOYMENT_PROOF: "소득·재직 증빙",
  DEPOSIT_RETURN_HISTORY: "보증금 반환 이력",
  LOAN_LIMIT_PROOF: "대환·여신 한도 증빙",
  ASSET_PROOF: "자산 증빙",
  OTHER: "기타",
};

export const VERIFICATION_STATUS_LABEL: Record<string, string> = {
  Pending: "제출 대기",
  Submitted: "제출됨",
  Reviewing: "검토 중",
  Verified: "승인",
  Rejected: "반려",
  Expired: "기한 만료",
};

export function verificationStatusBadgeVariant(
  status: string,
): "default" | "secondary" | "destructive" | "outline" {
  switch (status) {
    case "Verified":
      return "secondary";
    case "Rejected":
      return "destructive";
    case "Submitted":
    case "Reviewing":
      return "default";
    default:
      return "outline";
  }
}

export const RISK_GRADE_LABEL: Record<string, string> = {
  LOW: "낮음",
  MEDIUM: "보통",
  HIGH: "높음",
};

export function riskGradeBadgeVariant(grade: string): "default" | "secondary" | "destructive" | "outline" {
  switch (grade) {
    case "HIGH":
      return "destructive";
    case "MEDIUM":
      return "default";
    case "LOW":
      return "secondary";
    default:
      return "outline";
  }
}

export const SEVERITY_LABEL: Record<string, string> = {
  low: "낮음",
  medium: "보통",
  high: "높음",
};

export const LANDLORD_TYPE_LABEL: Record<string, string> = {
  INDIVIDUAL: "개인",
  INDIVIDUAL_BUSINESS: "개인사업자",
  CORPORATION: "법인",
};

export const HOUSING_TYPE_LABEL: Record<string, string> = {
  MULTI_HOUSEHOLD: "다세대",
  MULTI_FAMILY: "다가구",
  APARTMENT: "아파트",
  OFFICETEL: "오피스텔",
  SINGLE_FAMILY: "단독주택",
  ROW_HOUSE: "연립주택",
  OTHER: "기타",
};

export const TIMELINE_EVENT_LABEL: Record<string, string> = {
  ContractCreated: "계약 생성",
  RiskAssessed: "위험진단 완료",
  EvidenceRequested: "증빙 요청",
  EvidenceSubmitted: "증빙 제출",
  EvidenceVerified: "증빙 승인",
  EvidenceRejected: "증빙 반려",
  ReturnPlanSubmitted: "반환계획 제출",
  MonitoringStarted: "모니터링 시작",
  ContractFinalized: "계약 확정",
  D90Requested: "D-90 사전확보 요청",
  VerificationCompleted: "증빙 검증 완료",
  RiskEscalated: "위험 격상",
  IncidentReported: "사고 접수",
  TransferredToHUG: "HUG 이관",
  RecoveryStarted: "회수 개시",
};

export const BLOCKCHAIN_STATUS_LABEL: Record<string, string> = {
  NotRequested: "미기록",
  Pending: "기록 대기",
  Confirmed: "기록 완료",
  Failed: "기록 실패",
};

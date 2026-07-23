/**
 * HUG 업무화면(사고 전 계약관리 · 사고접수·보증이행 · 사고 후 채권관리) 공통 라벨 사전.
 * backend/app/schemas/{hug_contract,performance_claim,recovery}.py 의 Literal 값과 1:1.
 */

/* ── 사고 전 계약관리 ─────────────────────────────── */

export type PredictionStatus = "SUCCESS" | "NOT_SCORABLE" | "FAILED";

export const PREDICTION_STATUS_LABEL: Record<PredictionStatus, string> = {
  SUCCESS: "산정 완료",
  NOT_SCORABLE: "산정 불가",
  FAILED: "산정 실패",
};

export type PreventionStatus =
  | "Monitoring"
  | "RiskDetected"
  | "Notified"
  | "ActionRequested"
  | "EvidenceSubmitted"
  | "Verifying"
  | "Mitigated"
  | "Overdue"
  | "EscalatedMonitoring";

export const PREVENTION_STATUS_LABEL: Record<PreventionStatus, string> = {
  Monitoring: "정상 모니터링",
  RiskDetected: "위험 감지",
  Notified: "알림 발송",
  ActionRequested: "조치 요청",
  EvidenceSubmitted: "증빙 제출",
  Verifying: "검증 중",
  Mitigated: "위험 해소",
  Overdue: "기한 초과",
  EscalatedMonitoring: "집중 모니터링",
};

/** 예방상태 칩 톤 — 해소=민트, 진행=하늘, 주의=주황, 경보=빨강. */
export const PREVENTION_STATUS_TONE: Record<PreventionStatus, string> = {
  Monitoring: "bg-neutral-200 text-neutral-600",
  RiskDetected: "bg-warning-100 text-warning-700",
  Notified: "bg-hug-sky text-hug-blue",
  ActionRequested: "bg-warning-100 text-warning-700",
  EvidenceSubmitted: "bg-hug-sky text-hug-blue",
  Verifying: "bg-hug-sky text-hug-blue",
  Mitigated: "bg-hug-mint text-hug-green-deep",
  Overdue: "bg-danger-100 text-danger-600",
  EscalatedMonitoring: "bg-danger-100 text-danger-600",
};

export type PreventiveActionStatus =
  | "Requested"
  | "InProgress"
  | "Submitted"
  | "Verifying"
  | "Completed"
  | "Rejected"
  | "Cancelled"
  | "Overdue";

export const PREVENTIVE_ACTION_STATUS_LABEL: Record<PreventiveActionStatus, string> = {
  Requested: "요청됨",
  InProgress: "진행 중",
  Submitted: "제출됨",
  Verifying: "검증 중",
  Completed: "완료",
  Rejected: "반려",
  Cancelled: "취소",
  Overdue: "기한 초과",
};

export type PreventiveActionType =
  | "EVIDENCE_REQUEST"
  | "CREDIT_ENHANCEMENT_REQUEST"
  | "CALLBACK"
  | "ASSIGN_OWNER"
  | "RERUN_PREDICTION"
  | "MANUAL_REVIEW";

export const PREVENTIVE_ACTION_TYPE_LABEL: Record<PreventiveActionType, string> = {
  EVIDENCE_REQUEST: "증빙 제출 요청",
  CREDIT_ENHANCEMENT_REQUEST: "신용보강 요청",
  CALLBACK: "상담·콜백 등록",
  ASSIGN_OWNER: "담당자 배정",
  RERUN_PREDICTION: "예측 재실행",
  MANUAL_REVIEW: "수동 검토",
};

export type DdayCheckpoint = "D90" | "D60" | "D30";

export const CHECKPOINT_LABEL: Record<DdayCheckpoint, string> = {
  D90: "D-90",
  D60: "D-60",
  D30: "D-30",
};

export type BundleStatus = "Pending" | "InReview" | "Completed" | "Overdue" | "NotStarted";

export const BUNDLE_STATUS_LABEL: Record<BundleStatus, string> = {
  NotStarted: "대상 아님",
  Pending: "제출 대기",
  InReview: "검토 중",
  Completed: "완료",
  Overdue: "기한 초과",
};

export const BUNDLE_STATUS_TONE: Record<BundleStatus, string> = {
  NotStarted: "bg-neutral-200 text-neutral-600",
  Pending: "bg-hug-sky text-hug-blue",
  InReview: "bg-warning-100 text-warning-700",
  Completed: "bg-hug-mint text-hug-green-deep",
  Overdue: "bg-danger-100 text-danger-600",
};

/* ── 사고접수·보증이행 ────────────────────────────── */

export type PerformanceClaimStage =
  | "ClaimReceived"
  | "SupplementRequested"
  | "UnderReview"
  | "Approved"
  | "OnHold"
  | "Rejected"
  | "HandoverScheduled"
  | "HandoverCompleted"
  | "SubrogationPaid"
  | "RecoveryClaimRegistered"
  | "TransferredToRecovery";

export const CLAIM_STAGE_LABEL: Record<PerformanceClaimStage, string> = {
  ClaimReceived: "이행청구 접수",
  SupplementRequested: "보완 요청",
  UnderReview: "심사 중",
  Approved: "승인",
  OnHold: "유보",
  Rejected: "거절",
  HandoverScheduled: "명도 예정",
  HandoverCompleted: "명도 완료",
  SubrogationPaid: "대위변제 완료",
  RecoveryClaimRegistered: "채권 등록",
  TransferredToRecovery: "채권관리 인계",
};

export const CLAIM_STAGE_TONE: Record<PerformanceClaimStage, string> = {
  ClaimReceived: "bg-hug-sky text-hug-blue",
  SupplementRequested: "bg-warning-100 text-warning-700",
  UnderReview: "bg-warning-100 text-warning-700",
  Approved: "bg-hug-mint text-hug-green-deep",
  OnHold: "bg-warning-100 text-warning-700",
  Rejected: "bg-neutral-200 text-neutral-600",
  HandoverScheduled: "bg-hug-sky text-hug-blue",
  HandoverCompleted: "bg-hug-mint text-hug-green-deep",
  SubrogationPaid: "bg-hug-mint text-hug-green-deep",
  RecoveryClaimRegistered: "bg-hug-navy text-white",
  TransferredToRecovery: "bg-hug-navy text-white",
};

/** 미반환 사고(명도 필요) 기준 이행 절차 Stepper. */
export const NONRETURN_STAGE_FLOW: PerformanceClaimStage[] = [
  "ClaimReceived",
  "UnderReview",
  "Approved",
  "HandoverCompleted",
  "SubrogationPaid",
  "RecoveryClaimRegistered",
  "TransferredToRecovery",
];

/** 경·공매 사고(명도 불필요) 기준 이행 절차 Stepper. */
export const AUCTION_STAGE_FLOW: PerformanceClaimStage[] = [
  "ClaimReceived",
  "UnderReview",
  "Approved",
  "SubrogationPaid",
  "RecoveryClaimRegistered",
  "TransferredToRecovery",
];

/** Stepper 진행도 계산용 — 보완·유보는 이전 단계에 머무는 것으로 본다. */
export const STAGE_PROGRESS_ALIAS: Partial<Record<PerformanceClaimStage, PerformanceClaimStage>> = {
  SupplementRequested: "ClaimReceived",
  OnHold: "UnderReview",
  HandoverScheduled: "Approved",
};

export type OfficialAccidentType = "CONTRACT_END_NONRETURN" | "AUCTION_PUBLIC_SALE";

export const OFFICIAL_ACCIDENT_TYPE_LABEL: Record<OfficialAccidentType, string> = {
  CONTRACT_END_NONRETURN: "계약종료 후 미반환",
  AUCTION_PUBLIC_SALE: "경·공매 배당 부족",
};

export type SlaStatus = "ON_TRACK" | "DUE_SOON" | "OVERDUE" | "PAUSED" | "COMPLETED";

export const SLA_STATUS_LABEL: Record<SlaStatus, string> = {
  ON_TRACK: "정상 진행",
  DUE_SOON: "기한 임박",
  OVERDUE: "기한 초과",
  PAUSED: "보완 대기",
  COMPLETED: "처리 완료",
};

export const SLA_STATUS_TONE: Record<SlaStatus, string> = {
  ON_TRACK: "bg-hug-mint text-hug-green-deep",
  DUE_SOON: "bg-warning-100 text-warning-700",
  OVERDUE: "bg-danger-100 text-danger-600",
  PAUSED: "bg-neutral-200 text-neutral-600",
  COMPLETED: "bg-hug-sky text-hug-blue",
};

export type ClaimDocumentStatus = "Requested" | "Submitted" | "Verified" | "Rejected" | "Waived";

export const DOCUMENT_STATUS_LABEL: Record<ClaimDocumentStatus, string> = {
  Requested: "요청됨",
  Submitted: "제출됨",
  Verified: "검증 완료",
  Rejected: "반려",
  Waived: "면제",
};

export const DOCUMENT_STATUS_TONE: Record<ClaimDocumentStatus, string> = {
  Requested: "bg-hug-sky text-hug-blue",
  Submitted: "bg-warning-100 text-warning-700",
  Verified: "bg-hug-mint text-hug-green-deep",
  Rejected: "bg-danger-100 text-danger-600",
  Waived: "bg-neutral-200 text-neutral-600",
};

/** 이행청구 서류 유형 라벨 (EvidenceType 중 claim 트랙). */
export const CLAIM_DOCUMENT_TYPE_LABEL: Record<string, string> = {
  CONTRACT_DOCUMENT: "임대차 계약서",
  CONTRACT_TERMINATION_PROOF: "계약종료 증빙",
  TENANT_RIGHTS_PROOF: "권리보전 증빙(임차권등기 등)",
  AUCTION_DISTRIBUTION_PROOF: "경·공매 배당 증빙",
  HANDOVER_PROOF: "명도(주택 인도) 증빙",
  LEGAL_COST_PROOF: "법무비용 증빙",
  REGISTRY_CANCELLATION_PROOF: "등기 말소 증빙",
  BUSINESS_STATUS_PROOF: "사업자 상태 증빙",
  OWNERSHIP_PROOF: "소유권 증빙",
  INSURANCE_PROOF: "보증보험 증빙",
  RETURN_PLAN_DOCUMENT: "반환계획서",
  INCOME_EMPLOYMENT_PROOF: "소득·재직 증빙",
  DEPOSIT_RETURN_HISTORY: "보증금 반환 이력",
  LOAN_LIMIT_PROOF: "여신 한도 증빙",
  ASSET_PROOF: "자산 증빙",
  LATEST_REGISTRY_SNAPSHOT: "최신 등기부 확인",
  GUARANTEE_STATUS_PROOF: "보증 상태 확인",
  RETURN_FUNDS_PROOF: "반환재원 증빙",
  CREDIT_ENHANCEMENT_PROOF: "신용보강 증빙",
  RIGHTS_CHANGE_CHECK: "권리변동 확인",
  MOVE_OUT_SCHEDULE: "이사·반환일정 확인",
  UNRESOLVED_RISK_REVIEW: "미해소 위험 검토",
  FINAL_REQUIRED_DOCUMENTS: "필수서류 최종 확인",
  OTHER: "기타 서류",
};

/* ── 사고 후 채권관리 ─────────────────────────────── */

export type RecoveryClaimType =
  | "RECOURSE_STANDARD"
  | "RECOURSE_NEW_PRODUCT"
  | "LITIGATION_ADVANCE_COST";

export const RECOVERY_CLAIM_TYPE_LABEL: Record<RecoveryClaimType, string> = {
  RECOURSE_STANDARD: "구상채권",
  RECOURSE_NEW_PRODUCT: "구상채권(신상품)",
  LITIGATION_ADVANCE_COST: "소송대지급금",
};

export type RecoveryStage =
  | "Registered"
  | "Investigation"
  | "Preservation"
  | "Collection"
  | "Distribution"
  | "Closing";

export const RECOVERY_STAGE_LABEL: Record<RecoveryStage, string> = {
  Registered: "채권 등록",
  Investigation: "재산 조사",
  Preservation: "보전 조치",
  Collection: "회수 진행",
  Distribution: "배당·수령",
  Closing: "종결 처리",
};

export const RECOVERY_STAGE_FLOW: RecoveryStage[] = [
  "Registered",
  "Investigation",
  "Preservation",
  "Collection",
  "Distribution",
  "Closing",
];

export type CollectionRoute =
  | "None"
  | "Voluntary"
  | "PaymentPlan"
  | "Litigation"
  | "Auction"
  | "PublicSale"
  | "Insolvency";

export const COLLECTION_ROUTE_LABEL: Record<CollectionRoute, string> = {
  None: "경로 미지정",
  Voluntary: "자진 상환",
  PaymentPlan: "분할 상환",
  Litigation: "소송 회수",
  Auction: "경매",
  PublicSale: "공매",
  Insolvency: "회생·파산",
};

export type LegalStatus = "None" | "PaymentOrder" | "Lawsuit" | "Judgment" | "Enforcement";

export const LEGAL_STATUS_LABEL: Record<LegalStatus, string> = {
  None: "해당 없음",
  PaymentOrder: "지급명령",
  Lawsuit: "본안 소송",
  Judgment: "판결 확정",
  Enforcement: "강제집행",
};

export type AuctionStatus =
  | "None"
  | "Filed"
  | "InProgress"
  | "Sold"
  | "DividendScheduled"
  | "Distributed";

export const AUCTION_STATUS_LABEL: Record<AuctionStatus, string> = {
  None: "해당 없음",
  Filed: "신청",
  InProgress: "진행 중",
  Sold: "매각",
  DividendScheduled: "배당 예정",
  Distributed: "배당 완료",
};

export type RepaymentPlanStatus =
  | "None"
  | "Proposed"
  | "Active"
  | "Delinquent"
  | "Completed"
  | "Terminated";

export const REPAYMENT_PLAN_STATUS_LABEL: Record<RepaymentPlanStatus, string> = {
  None: "해당 없음",
  Proposed: "약정 협의",
  Active: "약정 이행 중",
  Delinquent: "연체",
  Completed: "약정 완료",
  Terminated: "약정 해지",
};

export type BalanceStatus = "Unrecovered" | "PartiallyRecovered" | "FullyRecovered";

export const BALANCE_STATUS_LABEL: Record<BalanceStatus, string> = {
  Unrecovered: "미회수",
  PartiallyRecovered: "부분 회수",
  FullyRecovered: "전액 회수",
};

export type LedgerEntryType =
  | "PRINCIPAL_ACCRUAL"
  | "LEGAL_COST_ACCRUAL"
  | "DELAY_DAMAGE_ACCRUAL"
  | "ENFORCEMENT_COST_ACCRUAL"
  | "RECEIPT"
  | "DIVIDEND_RECEIPT"
  | "ADJUSTMENT_INCREASE"
  | "ADJUSTMENT_DECREASE";

export const LEDGER_ENTRY_TYPE_LABEL: Record<LedgerEntryType, string> = {
  PRINCIPAL_ACCRUAL: "원금 발생",
  LEGAL_COST_ACCRUAL: "법무비용 발생",
  DELAY_DAMAGE_ACCRUAL: "지연배상금 발생",
  ENFORCEMENT_COST_ACCRUAL: "집행비용 발생",
  RECEIPT: "입금 충당",
  DIVIDEND_RECEIPT: "배당 수령",
  ADJUSTMENT_INCREASE: "조정 증액",
  ADJUSTMENT_DECREASE: "조정 감액",
};

/** 원장 항목이 잔액을 늘리는지(발생·증액) 줄이는지(입금·감액). */
export const LEDGER_ENTRY_IS_ACCRUAL: Record<LedgerEntryType, boolean> = {
  PRINCIPAL_ACCRUAL: true,
  LEGAL_COST_ACCRUAL: true,
  DELAY_DAMAGE_ACCRUAL: true,
  ENFORCEMENT_COST_ACCRUAL: true,
  RECEIPT: false,
  DIVIDEND_RECEIPT: false,
  ADJUSTMENT_INCREASE: true,
  ADJUSTMENT_DECREASE: false,
};

export const LEDGER_COMPONENT_LABEL: Record<string, string> = {
  principal: "원금",
  legal_cost: "법무비용",
  delay_damage: "지연배상금",
  enforcement_cost: "집행비용",
};

export type CloseReason =
  | "FULL_RECOVERY"
  | "SOLD"
  | "WRITTEN_OFF"
  | "INSOLVENCY_DISCHARGE"
  | "LEGAL_EXPIRY"
  | "OTHER_APPROVED";

export const CLOSE_REASON_LABEL: Record<CloseReason, string> = {
  FULL_RECOVERY: "전액 회수",
  SOLD: "채권 매각",
  WRITTEN_OFF: "상각",
  INSOLVENCY_DISCHARGE: "회생·파산 면책",
  LEGAL_EXPIRY: "법적 소멸",
  OTHER_APPROVED: "기타 승인 종결",
};

/* ── 공통 포맷터 ─────────────────────────────────── */

/**
 * 백엔드 업무 문자열의 내부 용어를 화면 표현으로 치환한다.
 * 트리거 사유·다음 조치 등 서버 생성 문구에 개발 용어가 남지 않도록 마지막에 한 번 거른다.
 */
export function toWorkText(text: string | null | undefined): string {
  if (!text) return "";
  return text
    .replace(/PoC\s*상대위험/gi, "사고위험")
    .replace(/PoC\s*/gi, "")
    .replace(/미보정/g, "")
    .trim();
}

/** 7.14e12 → "7.1조", 4.8e8 → "4.8억", 3200만 → "3,200만". */
export function formatWonShort(won: number): string {
  const abs = Math.abs(won);
  const sign = won < 0 ? "-" : "";
  if (abs >= 1e12) return `${sign}${(abs / 1e12).toFixed(1)}조`;
  if (abs >= 1e8) return `${sign}${(abs / 1e8).toFixed(1)}억`;
  if (abs >= 1e4) return `${sign}${Math.round(abs / 1e4).toLocaleString("ko-KR")}만`;
  return `${sign}${abs.toLocaleString("ko-KR")}`;
}

/** D-day 표시 — 양수: D-n, 0: D-Day, 음수: 만기 경과 n일. */
export function formatDday(dDay: number): string {
  if (dDay > 9000) return "—";
  if (dDay > 0) return `D-${dDay}`;
  if (dDay === 0) return "D-Day";
  return `경과 ${-dDay}일`;
}

/** ISO 문자열 → "2026-07-23" / null이면 "—". */
export function formatDate(iso: string | null | undefined): string {
  return iso ? iso.slice(0, 10) : "—";
}

/** ISO 문자열 → "07-23 14:05" (타임라인용). */
export function formatDateTime(iso: string | null | undefined): string {
  return iso ? iso.slice(5, 16).replace("T", " ") : "—";
}

/** 남은 초 → "3일" / "17시간" / "40분". */
export function formatRemaining(seconds: number): string {
  const abs = Math.abs(seconds);
  if (abs >= 86400) return `${Math.floor(abs / 86400)}일`;
  if (abs >= 3600) return `${Math.floor(abs / 3600)}시간`;
  return `${Math.max(1, Math.floor(abs / 60))}분`;
}

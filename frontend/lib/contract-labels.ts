import { ContractStatus } from "@/types/enums";

export const CONTRACT_STATUS_LABEL: Record<ContractStatus, string> = {
  [ContractStatus.DRAFT]: "작성 중",
  [ContractStatus.DIAGNOSED]: "진단 완료",
  [ContractStatus.EVIDENCE_REQUESTED]: "증빙 요청",
  [ContractStatus.EVIDENCE_SUBMITTED]: "증빙 제출",
  [ContractStatus.VERIFIED]: "검증 완료",
  [ContractStatus.CONTRACT_FINALIZED]: "계약 확정",
  [ContractStatus.MONITORING]: "모니터링",
  [ContractStatus.D90_REQUESTED]: "D-90 요청",
  [ContractStatus.RETURN_PLAN_SUBMITTED]: "반환계획 제출",
  [ContractStatus.AT_RISK]: "위험",
  [ContractStatus.INCIDENT_REPORTED]: "사고 접수",
  [ContractStatus.TRANSFERRED_TO_HUG]: "HUG 이관",
  [ContractStatus.RECOVERY_IN_PROGRESS]: "회수 진행",
  [ContractStatus.CLOSED]: "종결",
};

/** HUG 채권관리 대시보드의 사건 우선순위. 앞에 있을수록 긴급(명세서 HUG-01). */
export const HUG_CASE_PRIORITY: ContractStatus[] = [
  ContractStatus.INCIDENT_REPORTED,
  ContractStatus.TRANSFERRED_TO_HUG,
  ContractStatus.RECOVERY_IN_PROGRESS,
  ContractStatus.AT_RISK,
  ContractStatus.D90_REQUESTED,
  ContractStatus.RETURN_PLAN_SUBMITTED,
  ContractStatus.MONITORING,
  ContractStatus.CONTRACT_FINALIZED,
];

/** 임차인 홈에서 "주의 필요"로 강조하는 상태(위험~회수 단계). */
export const ATTENTION_STATUSES: ContractStatus[] = [
  ContractStatus.AT_RISK,
  ContractStatus.INCIDENT_REPORTED,
  ContractStatus.TRANSFERRED_TO_HUG,
  ContractStatus.RECOVERY_IN_PROGRESS,
  ContractStatus.D90_REQUESTED,
];

export function hugCasePriority(status: ContractStatus): number {
  const index = HUG_CASE_PRIORITY.indexOf(status);
  return index === -1 ? HUG_CASE_PRIORITY.length : index;
}

type BadgeVariant = "default" | "secondary" | "destructive" | "outline";

export function contractStatusBadgeVariant(status: ContractStatus): BadgeVariant {
  switch (status) {
    case ContractStatus.INCIDENT_REPORTED:
    case ContractStatus.TRANSFERRED_TO_HUG:
    case ContractStatus.AT_RISK:
      return "destructive";
    case ContractStatus.RECOVERY_IN_PROGRESS:
    case ContractStatus.D90_REQUESTED:
      return "default";
    case ContractStatus.CLOSED:
    case ContractStatus.DRAFT:
      return "outline";
    default:
      return "secondary";
  }
}

/** 보증금을 "4.5억"/"3,000만" 형태로 축약 표기한다. */
export function formatDeposit(amount: number): string {
  if (amount >= 100_000_000) {
    const eok = amount / 100_000_000;
    return `${Number.isInteger(eok) ? eok : eok.toFixed(1)}억 원`;
  }
  if (amount >= 10_000) {
    return `${Math.round(amount / 10_000).toLocaleString("ko-KR")}만 원`;
  }
  return `${amount.toLocaleString("ko-KR")}원`;
}

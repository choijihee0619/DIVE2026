import type { Pagination } from "@/types/contract";

/** backend/app/schemas/incident.py와 1:1. 사고 접수→회수 타임라인(축 B). */

export type IncidentType =
  | "DEPOSIT_NOT_RETURNED"
  | "AUCTION_STARTED"
  | "LANDLORD_UNREACHABLE"
  | "FRAUD_SUSPECTED"
  | "OTHER";

export type IncidentStatus = "Received" | "Reviewing" | "TransferredToRecovery" | "Closed";

export const INCIDENT_TYPE_LABEL: Record<IncidentType, string> = {
  DEPOSIT_NOT_RETURNED: "보증금 미반환",
  AUCTION_STARTED: "경매·공매 개시",
  LANDLORD_UNREACHABLE: "임대인 연락 두절",
  FRAUD_SUSPECTED: "전세사기 의심",
  OTHER: "기타",
};

export const INCIDENT_STATUS_LABEL: Record<IncidentStatus, string> = {
  Received: "접수 완료",
  Reviewing: "검토 중",
  TransferredToRecovery: "회수 절차 이관",
  Closed: "종결",
};

/** 상태 전이 순서(HUG 큐의 다음 단계 버튼용). */
export const INCIDENT_STATUS_FLOW: IncidentStatus[] = [
  "Received",
  "Reviewing",
  "TransferredToRecovery",
  "Closed",
];

export interface IncidentTimelineEntry {
  status: IncidentStatus;
  note: string | null;
  by_role: string;
  at: string;
}

export interface Incident {
  incident_id: string;
  reporter_user_id: string;
  incident_type: IncidentType;
  incident_type_label: string;
  description: string;
  contract_id: string | null;
  property_id: string | null;
  deposit_amount: number | null;
  occurred_date: string | null;
  status: IncidentStatus;
  timeline: IncidentTimelineEntry[];
  next_steps: string[];
  created_at: string;
  updated_at: string;
}

export interface IncidentListData {
  items: Incident[];
  pagination: Pagination;
}

export interface IncidentCreate {
  incident_type: IncidentType;
  description: string;
  contract_id?: string | null;
  property_id?: string | null;
  deposit_amount?: number | null;
  occurred_date?: string | null;
}

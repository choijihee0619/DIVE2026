/**
 * HUG 사고접수·보증이행 API 응답 타입.
 * backend/app/services/performance_claim_service.py 실응답(260723) 기준.
 */

import type {
  ClaimDocumentStatus,
  OfficialAccidentType,
  PerformanceClaimStage,
  SlaStatus,
} from "@/lib/hug-labels";
import type { IncidentStatus, IncidentType } from "@/types/incident";

export interface ClaimSla {
  status: SlaStatus;
  started_at: string;
  base_due_at: string;
  effective_due_at: string;
  paused_at: string | null;
  pause_reason: string | null;
  total_paused_seconds: number;
  elapsed_seconds: number;
  remaining_seconds: number;
  completed_at: string | null;
}

export interface ClaimDocument {
  document_id: string;
  performance_claim_id: string;
  document_type: string;
  required: boolean;
  reason: string | null;
  verification_status: ClaimDocumentStatus;
  requested_at: string | null;
  due_at: string | null;
  submitted_at: string | null;
  decided_at: string | null;
  file_name?: string | null;
  note?: string | null;
  [key: string]: unknown;
}

export interface SubrogationPayment {
  payment_id: string;
  performance_claim_id: string;
  payment_reference: string;
  paid_amount: number;
  paid_at: string;
  reason: string | null;
  [key: string]: unknown;
}

export interface RegisteredRecoveryClaim {
  recovery_claim_id: string;
  performance_claim_id?: string;
  claim_type: string;
  principal: number;
  incurred_amount?: number;
  incurred_date?: string;
  [key: string]: unknown;
}

export interface ClaimEvent {
  event_id: string;
  performance_claim_id: string;
  action: string;
  before_stage: string | null;
  after_stage: string | null;
  actor_role: string;
  reason: string | null;
  occurred_at: string;
}

/** 이행청구 상세 — GET /performance-claims/{id} · get_hug_incident.performance_claim. */
export interface PerformanceClaimDetail {
  performance_claim_id: string;
  incident_id: string;
  contract_id: string;
  official_accident_type: OfficialAccidentType;
  workflow_type: "JEONSE_RETURN_NONRETURN" | "JEONSE_AUCTION_PUBLIC_SALE";
  product_name: string;
  stage: PerformanceClaimStage;
  version: number;
  claim_amount: number;
  approved_amount: number | null;
  paid_amount: number;
  decision: string | null;
  decision_reason: string | null;
  handover_required: boolean;
  moveout_due_at: string | null;
  assignee_user_id: string | null;
  sla: ClaimSla;
  documents: ClaimDocument[];
  document_summary: { total: number; required: number; verified_or_waived: number };
  subrogation_payments: SubrogationPayment[];
  recovery_claims: RegisteredRecoveryClaim[];
  stage_entered_at: string;
  created_at: string;
  updated_at: string;
}

export interface ClaimSummary {
  performance_claim_id: string;
  stage: PerformanceClaimStage;
  claim_amount: number;
  approved_amount: number | null;
  assignee_user_id: string | null;
  sla: ClaimSla;
}

/** GET /hug/incidents 목록 행. */
export interface HugIncidentRow {
  incident_id: string;
  reporter_user_id: string;
  incident_type: IncidentType;
  incident_type_label: string;
  description: string;
  contract_id: string | null;
  property_id: string | null;
  /** 목록 표시명(주소 통일, §20.1) — 서버가 property를 조인해 내려준다. */
  address_summary?: string | null;
  deposit_amount: number | null;
  occurred_date: string | null;
  status: IncidentStatus;
  performance_claim_id: string | null;
  current_stage: string;
  timeline: { status: IncidentStatus; note: string | null; by_role: string; at: string }[];
  performance_claim: ClaimSummary | null;
  created_at: string;
  updated_at: string;
}

/** GET /hug/incidents/{id} — 목록 행 + 이행청구 상세 전체. */
export interface HugIncidentDetail extends Omit<HugIncidentRow, "performance_claim"> {
  performance_claim: PerformanceClaimDetail | null;
}

export interface HugIncidentListData {
  items: HugIncidentRow[];
  pagination: { page: number; size: number; total_elements: number; total_pages: number };
}

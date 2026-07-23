/**
 * HUG 사고 전 계약관리 API 응답 타입.
 * backend/app/services/hug_contract_service.py · schemas/hug_contract.py 실응답(260723) 기준.
 */

import type {
  DdayCheckpoint,
  PredictionStatus,
  PreventionStatus,
  PreventiveActionStatus,
} from "@/lib/hug-labels";

export interface AccidentPredictionFactor {
  feature: string;
  label: string;
  value: string | number | null;
  importance: number;
}

/** 계약별 사고위험 산정 결과 — 목록·상세·이력 공용 뷰. */
export interface AccidentPrediction {
  prediction_id: string;
  pu_risk_score: number | null;
  risk_percentile: number | null;
  accident_probability: number | null;
  prediction_status: PredictionStatus;
  failure_reason: string[];
  model_version: string;
  top_factors: AccidentPredictionFactor[];
  data_completeness: number;
  predicted_at: string | null;
  valid_until: string | null;
}

export interface RuleRisk {
  risk_assessment_id: string;
  risk_score: number | null;
  risk_grade: string | null;
  risk_factors: { factor?: string; description?: string; severity?: string; [key: string]: unknown }[];
  data_completeness: number | null;
  created_at: string | null;
}

export interface PreventionCaseSummary {
  prevention_case_id: string;
  status: PreventionStatus;
  triggers: { trigger?: string; reason?: string; [key: string]: unknown }[];
  owner_user_id: string | null;
  owner_center: string | null;
  next_action: string | null;
  due_at: string | null;
}

export interface EvidenceBundleItem {
  item_key: string;
  label: string;
  evidence_type: string;
  evidence_request_id: string;
  verification_status: string;
  due_at: string;
  is_verified: boolean;
  is_overdue: boolean;
}

export interface EvidenceBundle {
  _id?: string;
  evidence_bundle_id?: string;
  contract_id: string;
  checkpoint: DdayCheckpoint;
  status: "Pending" | "InReview" | "Completed" | "Overdue";
  due_at: string;
  required_count: number;
  submitted_count: number;
  verified_count: number;
  overdue_count: number;
  completion_ratio: number;
  items: EvidenceBundleItem[];
}

export interface EvidenceBundleSummary {
  status: "NotStarted" | "Pending" | "InReview" | "Completed" | "Overdue";
  required_count: number;
  submitted_count: number;
  verified_count: number;
  overdue_count: number;
  completion_ratio: number;
  checkpoints: {
    evidence_bundle_id: string;
    checkpoint: DdayCheckpoint;
    status: string;
    due_at: string;
    completion_ratio: number;
  }[];
}

export interface NotificationRoleSummary {
  sent_count: number;
  read_count: number;
  acknowledged_count: number;
  latest_sent_at: string | null;
}

export interface PreventiveAction {
  _id?: string;
  action_id?: string;
  prevention_case_id: string;
  contract_id: string;
  action_type: string;
  status: PreventiveActionStatus;
  actor_role: string;
  target_role: string;
  requested_at: string;
  due_at: string | null;
  completed_at: string | null;
  note: string | null;
}

/** GET /hug/contracts 목록 행 = 상세 공통 필드. */
export interface HugContractItem {
  contract_id: string;
  property_id: string | null;
  contract_status: string;
  address: Record<string, string>;
  address_summary: string | null;
  guarantee_product: string;
  guarantee_amount: number | null;
  guarantee_status: string;
  deposit: number | null;
  housing_type: string | null;
  contract_start_date: string | null;
  contract_end_date: string | null;
  d_day: number;
  d_day_stage: string | null;
  prediction: AccidentPrediction | null;
  rule_risk: RuleRisk | null;
  prevention_case: PreventionCaseSummary | null;
  prevention_priority: number;
  priority_components: Record<string, number>;
  evidence_bundle: EvidenceBundleSummary;
  notification_status: Record<"tenant" | "landlord" | "hug_admin", NotificationRoleSummary>;
  next_action: string | null;
  owner_center: string | null;
  assignee_user_id: string | null;
}

/** GET /hug/contracts/{id} — 목록 필드 + 상세 전용 필드. */
export interface HugContractDetail extends HugContractItem {
  evidence_bundles: EvidenceBundle[];
  preventive_actions: PreventiveAction[];
  prediction_history: AccidentPrediction[];
  timeline: { event?: string; description?: string; at?: string; created_at?: string; [key: string]: unknown }[];
}

export interface HugContractListData {
  items: HugContractItem[];
  pagination: { page: number; size: number; total_elements: number; total_pages: number };
  as_of_date: string;
  data_mode_filter: "LIVE" | "DEMO";
}

export interface PredictionRefreshBatchResult {
  requested: number;
  succeeded?: number;
  not_scorable?: number;
  failed?: number;
  [key: string]: unknown;
}

export interface PreventionSweepResult {
  checked?: number;
  cases_created?: number;
  actions_created?: number;
  notifications_sent?: number;
  [key: string]: unknown;
}

export interface ContractPreventionData {
  prevention_case?: PreventionCaseSummary | null;
  case?: PreventionCaseSummary | null;
  cases?: PreventionCaseSummary[];
  evidence_bundles?: EvidenceBundle[];
  actions?: PreventiveAction[];
  [key: string]: unknown;
}

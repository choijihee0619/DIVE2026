import type { ContractStatus } from "@/types/enums";

/** backend/app/schemas/common.py::Pagination 그대로. */
export interface Pagination {
  page: number;
  size: number;
  total_elements: number;
  total_pages: number;
}

/** backend/app/schemas/contract.py::ContractResponse 그대로. */
export interface Contract {
  contract_id: string;
  property_id: string;
  tenant_user_id: string;
  landlord_user_id: string | null;
  landlord_id: string | null;
  contract_status: ContractStatus;
  deposit: number;
  contract_start_date: string;
  contract_end_date: string;
  landlord_type: string;
  housing_type: string;
  risk_assessment_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface ContractListData {
  items: Contract[];
  pagination: Pagination;
}

export interface ContractCreate {
  property_id: string;
  deposit: number;
  contract_start_date: string;
  contract_end_date: string;
  landlord_type: string;
  housing_type: string;
  landlord_id?: string | null;
}

export interface TimelineEvent {
  timeline_event_id: string;
  event_type: string;
  occurred_at: string;
  blockchain_status: string;
  blockchain_tx_id: string | null;
}

export interface ContractTimeline {
  contract_id: string;
  contract_status: ContractStatus;
  events: TimelineEvent[];
}

export interface ReturnPlan {
  return_plan_id: string;
  contract_id: string;
  d_day: number | null;
  landlord_response_status: string;
  early_warning: boolean;
  planned_return_date: string | null;
  return_method: string | null;
  note: string | null;
  created_at: string;
}

export interface ReturnPlanCreate {
  contract_id: string;
  planned_return_date: string;
  return_method: string;
  note?: string;
}

/** POST /contracts/dday-sweep 결과 (README §19.2 D-90/60/30 사전 확보 점검). */
export interface DdaySweepResult {
  checked: number;
  requests_created: number;
  notifications_sent: number;
  flagged: { contract_id: string; stage: string; d_day: number }[];
}
